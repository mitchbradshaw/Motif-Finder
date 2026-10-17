"""
test_chain_job.py
=================
Round A_2, P2: a Discovery template run sent to the cluster comes back as a real
Discovery run, its heavy steps left in the step cache for every later run.

The design under test (`docs/rq_roundA_2/prompts/P2-hpc-template-round-trip.md`):

* **The spec carries content, not the cluster's database.** Per target: the exact
  recipe the local sweep executes (`materialize_target` plus the `surrogate`
  flag), the recording's local id, source file, channel, units, `.npy` and its
  sha1, the expected config hash and step-prefix hashes; the null (draws, method,
  seed). Store-reading steps are refused for export by name.
* **The cluster computes on a scratch database** built with `init_db()` and the
  recording rows inserted under their LOCAL ids, so every hash equals the local
  one (asserted against the spec before anything runs). The real run and its null
  draws run in the same task; the result file and the step cache are per task.
* **The import restores the cache; the existing local path writes the rows.** It
  verifies the spec hash, every hash and the recording content, copies the
  task's cache entries into STEP_CACHE_ROOT with their `step_artifacts` rows, and
  the ordinary local sweep then runs: heavy steps are cache hits.

Headless and self-contained: temp sqlite, synthetic coloured signals, in-process
"cluster" tasks. The matrix-profile spans are a few thousand samples.

    PYTHONIOENCODING=utf-8 python -m pytest tests/test_chain_job.py -q -p no:cacheprovider
"""

import json
import os
import shutil
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import Adapters.detection_matrix_profile as MPA  # noqa: E402
import Working.config as cfg  # noqa: E402
from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database import runs as R  # noqa: E402
from Working.database.matrix_profile_store import compute_data_sha1  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.discovery import chain_job  # noqa: E402
from Working.discovery import fanout  # noqa: E402
from Working.execution import _recipe_prefix_hash  # noqa: E402
from Working.recipes import short_hash  # noqa: E402

discover_adapters()

FS = 1.0
N = 3000
#: the cheap chain: baseline removal, then every stretch 3 sigma below the median
CHEAP = [
    {"stage": "preprocessing", "algorithm": "detrend", "params": {"mode": "rolling_mean", "window_s": 300.0}},
    {"stage": "detection", "algorithm": "noise_threshold",
     "params": {"k_sigma": 3.0, "direction": "below", "min_duration_s": 5.0, "merge_gap_s": 10.0}},
]
#: the matrix-profile chain (m = 60 at 1 Hz), the step the cache has to carry
MP_STEP = 1
MP = [
    {"stage": "preprocessing", "algorithm": "detrend", "params": {"mode": "rolling_mean", "window_s": 300.0}},
    {"stage": "detection", "algorithm": "matrix_profile", "params": {"window_min": 1.0, "backend": "stump"}},
    {"stage": "detection", "algorithm": "threshold", "params": {"threshold": 3.0}},
]
#: the same profile, cut at another threshold: "a different threshold on the same profile"
MP_VARIANT = MP[:2] + [{"stage": "detection", "algorithm": "threshold", "params": {"threshold": 4.0}}]
#: a block that is told the recording's unit (its output depends on it)
SPIKE = [{"stage": "detection", "algorithm": "spike_v1", "params": {}}]
NULL = {"paired": True, "params": {"method": "phase_randomize", "seed": 0}, "draws": 1}


def _coloured(seed, n=N):
    """AR(1) at phi 0.97, a slow drift, and a train of planted drops: a background
    that is not white noise, with events in it."""
    rng = np.random.default_rng(seed)
    e = rng.standard_normal(n) * 0.01
    x = np.empty(n)
    x[0] = 0.0
    for i in range(1, n):
        x[i] = 0.97 * x[i - 1] + e[i]
    x += 0.05 * np.sin(np.linspace(0, 3 * np.pi, n))
    drop = -0.2 * np.exp(-np.linspace(0, 4, 90))
    for a in range(200, n - 200, 470):
        x[a:a + 90] += drop
    return x


@pytest.fixture
def world(tmp_path, monkeypatch):
    """Database A (the researcher's machine): three channels of a volts file, one
    channel of a millivolts file. The step cache and the profile results live in
    temp directories; every step is cached (the sandbox's threshold)."""
    root = tmp_path
    db = str(root / "a" / "annotations.sqlite")
    os.makedirs(os.path.dirname(db))
    conn = init_db(db)
    ids = []
    for ch in range(3):
        npy = root / f"syn_CH{ch}.npy"
        np.save(npy, _coloured(ch))
        ids.append(q.insert_recording(conn, "syn.mat", ch, FS, N, 0, str(npy), units="V"))
    npy_mv = root / "mv_CH0.npy"
    np.save(npy_mv, _coloured(7) * 1000.0)
    mv_id = q.insert_recording(conn, "mv.mat", 0, FS, N, 0, str(npy_mv), units="mV")
    conn.close()
    monkeypatch.setattr(cfg, "STEP_CACHE_ROOT", str(root / "cache_a"))
    monkeypatch.setattr(cfg, "STEP_CACHE_WRITE_THRESHOLD_S", 0.0)
    monkeypatch.setattr(MPA, "RESULTS_DIR", str(root / "mp_results"))
    return {"root": root, "db": db, "ids": ids, "mv_id": mv_id, "hpc": str(root / "hpc")}


def _plan(conn, steps, ids, span=(0, N), null=NULL):
    return fanout.plan(conn, steps=steps, recording_ids=ids, span=span, ceiling_s=1200,
                       null_draws=(null["draws"] if null["paired"] else 0), surrogate=null["paired"],
                       surrogate_params=null["params"])


def _export(world, steps, ids, *, label, null=NULL, chunk=None, span=(0, N)):
    conn = init_db(world["db"])
    try:
        plan = _plan(conn, steps, ids, span=span, null=null)
        assert plan["runnable"], plan["reason"]
        spec = chain_job.build_spec(conn, plan, label=label, null=null, chunk=chunk)
    finally:
        conn.close()
    made = chain_job.write_job(spec, out_dir=world["hpc"], base_name=label)
    return plan, spec, made


def _run_all(spec, made, tasks=None):
    out = []
    for i in (range(spec["tasks"]) if tasks is None else tasks):
        out.append(chain_job.run_task(spec, task=i, out_dir=made["result_dir"]))
    return out


def _boom(*a, **k):
    raise AssertionError("the matrix profile was recomputed: the imported cache entry was not used")


def _detections(conn, run_id):
    return [(int(d["start_idx"]), int(d["end_idx"])) for d in R.list_detections(conn, run_id)]


def _run_rows(conn, out):
    """Per target: (config hash, real detections, [draw detections...], the MP step's timing)."""
    rows = []
    for r in out["runs"]:
        run = R.get_run(conn, r["run_id"])
        draws = [_detections(conn, d) for d in r["surrogate_run_ids"]]
        rows.append({"config_hash": r["config_hash"], "real": _detections(conn, r["run_id"]), "draws": draws,
                     "timings": json.loads(run["step_timings_json"] or "{}"),
                     "draw_timings": [json.loads(R.get_run(conn, d)["step_timings_json"] or "{}")
                                      for d in r["surrogate_run_ids"]]})
    return rows


# ── the spec ────────────────────────────────────────────────────────────────

def test_the_spec_carries_the_exact_recipe_its_content_and_its_hashes(world):
    plan, spec, made = _export(world, MP, world["ids"][:2], label="mp_spec")
    assert spec["version"] == chain_job.SPEC_VERSION and spec["kind"] == "detection_chain"
    assert spec["tasks"] == 2 and len(spec["targets"]) == 2
    assert spec["null"]["paired"] is True and spec["null"]["draws"] == 1
    assert spec["null"]["params"]["method"] == "phase_randomize"
    conn = init_db(world["db"])
    try:
        for i, t in enumerate(spec["targets"]):
            rec = q.get_recording_by_id(conn, world["ids"][i])
            want = fanout.target_recipe(plan["recipe"], i, surrogate=True)
            assert t["recordingId"] == rec["id"] and t["sourceFile"] == "syn.mat" and t["channel"] == i
            assert t["units"] == "V" and t["fs"] == FS and t["nSamples"] == N
            assert t["recipe"] == want, "the cluster runs the recipe the local sweep would run, surrogate flag and all"
            assert t["recipe"]["surrogate"] is True
            assert t["configHash"] == short_hash(want)
            assert t["prefixHashes"] == [_recipe_prefix_hash(want, k, "V") for k in range(len(MP))]
            assert t["npySha1"] == compute_data_sha1(rec["npy_path"])
            assert t["npy"].endswith(f"syn_CH{i}.npy")
    finally:
        conn.close()
    # the spec is content: the same plan exported twice is the same spec
    _, again, _ = _export(world, MP, world["ids"][:2], label="mp_spec")
    assert chain_job.spec_hash(again) == chain_job.spec_hash(spec)
    with open(made["spec_path"], encoding="utf-8") as f:
        assert chain_job.spec_hash(json.load(f)) == chain_job.spec_hash(spec)


def test_a_null_of_one_draw_from_settings_is_one_draw_on_the_cluster(world):
    one = {"paired": True, "params": {"method": "phase_randomize", "seed": 0}, "draws": 1}
    _, spec, made = _export(world, CHEAP, world["ids"][:1], label="one_draw", null=one)
    res = _run_all(spec, made)[0]
    assert res["complete"] is True
    assert res["draws"]["asked"] == 1 and res["draws"]["drawn"] == 1
    assert len(res["draws"]["configHashes"]) == 1


def test_store_reading_steps_are_refused_for_export_by_name(world):
    labels = [
        {"stage": "preprocessing", "algorithm": "window_matrix",
         "params": {"window_min": 10.0, "step_frac": 0.334, "slow_entropy": False}},
        {"stage": "catalogue", "algorithm": "manual_labels", "params": {"non_overlapping": True}},
    ]
    seed = [{"stage": "detection", "algorithm": "seed_matches", "params": {},
             "side_inputs": {"exemplar": {"source_kind": "library_exemplar", "entry_id": 1, "source_file": "syn.mat",
                                          "channel": 0, "start_idx": 10, "end_idx": 70}}}]
    for steps, name in ((labels, "catalogue.manual_labels"), (seed, "detection.seed_matches")):
        conn = init_db(world["db"])
        try:
            plan = _plan(conn, steps, world["ids"][:1])
            with pytest.raises(chain_job.ExportRefused) as e:
                chain_job.build_spec(conn, plan, label="refused", null=NULL)
        finally:
            conn.close()
        assert name in str(e.value) and "database" in str(e.value)
        assert [s["name"] for s in e.value.steps] == [name]


def test_the_script_is_an_array_job_that_resubmits_its_own_task(world):
    _, spec, made = _export(world, MP, world["ids"][:2], label="mp_script")
    with open(made["script_path"], "rb") as f:
        raw = f.read()
    assert b"\r\n" not in raw, "sbatch refuses a script with DOS line breaks"
    s = raw.decode("utf-8")
    assert "#SBATCH --array=0-1" in s
    assert "python -m Working.discovery.chain_job --spec" in s and '--task "$TASK"' in s
    assert "--status" in s and 'sbatch --array="$TASK"' in s
    assert "timeout" in s, "a step that runs past the budget is stopped before the wall, so the chain resubmits"
    assert "--partition=cpu" in s, "backend stump is a CPU job"
    assert made["sbatch_command"].startswith("sbatch ")
    assert made["result_dir"].endswith("mp_script_out")
    gpu_steps = [MP[0], {**MP[1], "params": {"window_min": 1.0, "backend": "gpu_stump"}}, MP[2]]
    _, _, gmade = _export(world, gpu_steps, world["ids"][:1], label="mp_gpu")
    with open(gmade["script_path"], encoding="utf-8") as f:
        g = f.read()
    assert "--partition=a100" in g and "--gres=gpu:a100" in g


# ── the round trip ──────────────────────────────────────────────────────────

def test_the_round_trip_restores_the_cache_and_the_local_sweep_writes_equal_rows(world, monkeypatch):
    ids = world["ids"][:2]
    twin_db = str(world["root"] / "b" / "annotations.sqlite")
    os.makedirs(os.path.dirname(twin_db))
    shutil.copyfile(world["db"], twin_db)

    cheap_plan, cheap_spec, cheap_made = _export(world, CHEAP, ids, label="cheap_rt")
    mp_plan, mp_spec, mp_made = _export(world, MP, ids, label="mp_rt")
    results = _run_all(cheap_spec, cheap_made) + _run_all(mp_spec, mp_made)
    assert all(r["complete"] for r in results), [r.get("error") for r in results]
    assert {r["specHash"] for r in results[:2]} == {chain_job.spec_hash(cheap_spec)}
    local_cache = cfg.STEP_CACHE_ROOT
    assert not (os.path.isdir(local_cache) and os.listdir(local_cache)), \
        "the cluster writes its own task cache, never this machine's"
    assert _artifact_rows(world["db"]) == 0, "nor this machine's database"

    conn = init_db(world["db"])
    try:
        for spec, made in ((cheap_spec, cheap_made), (mp_spec, mp_made)):
            got = chain_job.import_results(conn, spec, made["result_dir"], cache_root=cfg.STEP_CACHE_ROOT)
            assert got["tasks"] == 2 and got["copied"] > 0
            n_rows = conn.execute("SELECT COUNT(*) FROM step_artifacts").fetchone()[0]
            assert n_rows >= got["copied"]
        local_cheap = chain_job.local_plan(conn, cheap_spec, ceiling_s=1200)
        local_mp = chain_job.local_plan(conn, mp_spec, ceiling_s=1200)
    finally:
        conn.close()
    assert local_mp["route"] != "cluster", "every heavy step is in the cache now"

    # the local sweep after the import: the profile must come from the cache
    mp_spec_obj = get_adapter("detection.matrix_profile")
    real_run = mp_spec_obj.run
    monkeypatch.setattr(mp_spec_obj, "run", _boom)
    a_cheap = fanout.start(local_cheap, db_path=world["db"], surrogate=True, surrogate_params=NULL["params"],
                           surrogate_draws=1)
    a_mp = fanout.start(local_mp, db_path=world["db"], surrogate=True, surrogate_params=NULL["params"],
                        surrogate_draws=1)
    monkeypatch.setattr(mp_spec_obj, "run", real_run)

    # the twin computes the same plan here, from nothing
    monkeypatch.setattr(cfg, "STEP_CACHE_ROOT", str(world["root"] / "cache_b"))
    tconn = init_db(twin_db)
    try:
        twin_cheap = _plan(tconn, CHEAP, ids)
        twin_mp = _plan(tconn, MP, ids)
    finally:
        tconn.close()
    b_cheap = fanout.start(twin_cheap, db_path=twin_db, surrogate=True, surrogate_params=NULL["params"],
                           surrogate_draws=1)
    b_mp = fanout.start(twin_mp, db_path=twin_db, surrogate=True, surrogate_params=NULL["params"],
                        surrogate_draws=1)

    aconn, bconn = init_db(world["db"]), init_db(twin_db)
    try:
        for a_out, b_out, spec in ((a_cheap, b_cheap, cheap_spec), (a_mp, b_mp, mp_spec)):
            a_rows, b_rows = _run_rows(aconn, a_out), _run_rows(bconn, b_out)
            assert [r["config_hash"] for r in a_rows] == [t["configHash"] for t in spec["targets"]]
            assert [r["config_hash"] for r in a_rows] == [r["config_hash"] for r in b_rows]
            assert [r["real"] for r in a_rows] == [r["real"] for r in b_rows]
            assert [r["draws"] for r in a_rows] == [r["draws"] for r in b_rows]
        assert any(r["real"] for r in _run_rows(aconn, a_mp)), "the profile chain finds something to compare"
        for r in _run_rows(aconn, a_mp):
            assert float(r["timings"][str(MP_STEP)]) == 0.0, "the real run's profile is a cache hit"
            assert all(float(t[str(MP_STEP + 1)]) == 0.0 for t in r["draw_timings"]), "so is every draw's"
        # the cluster's own counts match what the local sweep wrote
        for t, r in zip(results[2:], _run_rows(aconn, a_mp)):
            assert t["run"]["detections"] == len(r["real"])
    finally:
        aconn.close()
        bconn.close()

    # a second application (another threshold on the same profile) plans local and reuses the profile
    monkeypatch.setattr(cfg, "STEP_CACHE_ROOT", str(world["root"] / "cache_a"))
    conn = init_db(world["db"])
    try:
        variant = _plan(conn, MP_VARIANT, ids)
    finally:
        conn.close()
    assert variant["route"] != "cluster"
    assert all(MP_STEP in c["cached"] for c in variant["costs"])
    monkeypatch.setattr(mp_spec_obj, "run", _boom)
    again = fanout.start(variant, db_path=world["db"], surrogate=True, surrogate_params=NULL["params"],
                         surrogate_draws=1)
    assert len(again["runs"]) == 2 and not any(r["reused"] for r in again["runs"])


def test_units_reading_blocks_hash_the_same_on_the_cluster(world):
    """A block told the recording's unit keys its cache on it (`_recipe_prefix_hash`):
    the scratch database carries the local unit, so the cluster's hashes are the local
    ones, and a millivolt recording's entries are not a volts recording's."""
    _, spec, made = _export(world, SPIKE, [world["mv_id"]], label="spike_mv")
    t = spec["targets"][0]
    assert t["units"] == "mV"
    assert t["prefixHashes"][0] == _recipe_prefix_hash(t["recipe"], 0, "mV")
    assert t["prefixHashes"][0] != _recipe_prefix_hash(t["recipe"], 0, "V")
    res = _run_all(spec, made)[0]
    assert res["complete"] is True
    assert res["configHash"] == t["configHash"] and res["prefixHashes"] == t["prefixHashes"]
    assert {e["prefixHash"] for e in res["cache"]} >= {t["prefixHashes"][0]}


def test_the_surrogate_flag_survives_the_cluster_recipe(world):
    _, spec, made = _export(world, CHEAP, world["ids"][:1], label="flag")
    t = spec["targets"][0]
    without = {k: v for k, v in t["recipe"].items() if k != "surrogate"}
    assert t["configHash"] != short_hash(without), "the flag is part of what the run is"
    res = _run_all(spec, made)[0]
    assert res["configHash"] == t["configHash"]


# ── refusals ────────────────────────────────────────────────────────────────

def _cluster_done(world, steps=CHEAP, ids=None, label="ref"):
    _, spec, made = _export(world, steps, ids or world["ids"][:2], label=label)
    _run_all(spec, made)
    return spec, made


def _artifact_rows(db):
    conn = init_db(db)
    try:
        return conn.execute("SELECT COUNT(*) FROM step_artifacts").fetchone()[0]
    finally:
        conn.close()


def test_import_refuses_when_a_recordings_content_is_not_the_one_computed(world):
    spec, made = _cluster_done(world, label="content")
    conn = init_db(world["db"])
    try:
        npy = q.get_recording_by_id(conn, world["ids"][1])["npy_path"]
    finally:
        conn.close()
    np.save(npy, _coloured(99))          # the channel changed after the export
    before = _artifact_rows(world["db"])
    conn = init_db(world["db"])
    try:
        with pytest.raises(chain_job.ImportRefused, match="sha1"):
            chain_job.import_results(conn, spec, made["result_dir"], cache_root=cfg.STEP_CACHE_ROOT)
    finally:
        conn.close()
    assert _artifact_rows(world["db"]) == before, "a refusal records nothing"


def test_import_refuses_when_a_recordings_unit_changed_since_the_export(world):
    spec, made = _cluster_done(world, steps=SPIKE, ids=[world["mv_id"]], label="units")
    conn = init_db(world["db"])
    try:
        conn.execute("UPDATE recordings SET units = 'V' WHERE id = ?", (world["mv_id"],))
        conn.commit()
        with pytest.raises(chain_job.ImportRefused, match="unit"):
            chain_job.import_results(conn, spec, made["result_dir"], cache_root=cfg.STEP_CACHE_ROOT)
    finally:
        conn.close()


def test_import_refuses_a_result_computed_from_another_spec(world):
    spec, made = _cluster_done(world, label="spechash")
    other = json.loads(json.dumps(spec))
    other["label"] = "edited after the job ran"
    conn = init_db(world["db"])
    try:
        with pytest.raises(chain_job.ImportRefused, match="spec"):
            chain_job.import_results(conn, other, made["result_dir"], cache_root=cfg.STEP_CACHE_ROOT)
    finally:
        conn.close()


def test_import_refuses_incomplete_tasks_and_names_what_is_missing(world):
    _, spec, made = _export(world, CHEAP, world["ids"][:3], label="partial")
    _run_all(spec, made, tasks=[0])
    # task 1 stopped at its budget: a result file that says incomplete
    chain_job.run_task(spec, task=1, out_dir=made["result_dir"], budget_s=0.0)
    st = chain_job.collect(spec, made["result_dir"])
    assert st["complete"] is False
    assert [t["state"] for t in st["tasks"]] == ["complete", "partial", "missing"]
    before = _artifact_rows(world["db"])
    conn = init_db(world["db"])
    try:
        with pytest.raises(chain_job.ImportRefused) as e:
            chain_job.import_results(conn, spec, made["result_dir"], cache_root=cfg.STEP_CACHE_ROOT)
    finally:
        conn.close()
    msg = str(e.value)
    assert "1 of 3" in msg and "task 1" in msg and "task 2" in msg
    assert spec["targets"][2]["channelName"] in msg
    assert _artifact_rows(world["db"]) == before


def test_the_cluster_refuses_a_channel_file_that_is_not_the_exported_one(world):
    _, spec, made = _export(world, CHEAP, world["ids"][:1], label="npy")
    spec = json.loads(json.dumps(spec))
    spec["targets"][0]["npySha1"] = "0" * 40
    res = chain_job.run_task(spec, task=0, out_dir=made["result_dir"])
    assert res["complete"] is False and "sha1" in (res["error"] or "")
    assert chain_job.main(["--status", "--out", made["result_dir"], "--task", "0"]) == 3, \
        "a refusal stops the resubmit chain"


# ── resume ──────────────────────────────────────────────────────────────────

def test_a_task_killed_between_steps_resumes_from_its_own_cache(world, monkeypatch):
    """SLURM ends a job mid-chain (here: as the threshold step starts, after the
    profile was cached). The resubmitted job continues from the task's own cache:
    the profile is not computed again."""
    off = {"paired": False, "params": None, "draws": 0}
    _, spec, made = _export(world, MP, world["ids"][:1], label="resume", null=off)
    thr = get_adapter("detection.threshold")
    real_thr = thr.run

    def killed(*a, **k):
        raise SystemExit("SLURM ended the job here")

    monkeypatch.setattr(thr, "run", killed)
    with pytest.raises(SystemExit):
        chain_job.run_task(spec, task=0, out_dir=made["result_dir"])
    assert chain_job.main(["--status", "--out", made["result_dir"], "--task", "0"]) == 1
    monkeypatch.setattr(thr, "run", real_thr)
    monkeypatch.setattr(get_adapter("detection.matrix_profile"), "run", _boom)
    res = chain_job.run_task(spec, task=0, out_dir=made["result_dir"])
    assert res["complete"] is True, res.get("error")
    assert chain_job.main(["--status", "--out", made["result_dir"], "--task", "0"]) == 0


def test_a_budget_stop_is_incomplete_and_the_next_job_finishes_it(world):
    _, spec, made = _export(world, CHEAP, world["ids"][:1], label="budget")
    first = chain_job.run_task(spec, task=0, out_dir=made["result_dir"], budget_s=0.0)
    assert first["complete"] is False and not first.get("error")
    assert chain_job.main(["--status", "--out", made["result_dir"], "--task", "0"]) == 1
    second = chain_job.run_task(spec, task=0, out_dir=made["result_dir"])
    assert second["complete"] is True
    assert chain_job.main(["--status", "--out", made["result_dir"], "--task", "0"]) == 0
    assert chain_job.main(["--status", "--out", made["result_dir"]]) == 0


def test_a_task_that_makes_no_progress_twice_stops_its_chain(world):
    """A step longer than the wall is killed every time, and would resubmit until the
    cap. Two jobs in a row that cached nothing stop the chain with the reason."""
    _, spec, made = _export(world, CHEAP, world["ids"][:1], label="stall")
    for _ in range(2):
        chain_job.run_task(spec, task=0, out_dir=made["result_dir"], budget_s=0.0)
    res = chain_job.run_task(spec, task=0, out_dir=made["result_dir"], budget_s=0.0)
    assert res["complete"] is False and "progress" in (res["error"] or "")
    assert chain_job.main(["--status", "--out", made["result_dir"], "--task", "0"]) == 3


# ── the matrix profile over the whole span ──────────────────────────────────

def test_the_cluster_has_no_time_cap_on_the_matrix_profile(world, monkeypatch):
    """The cap is calibrated on this machine (the local background budget): on the
    cluster there is none."""
    monkeypatch.setattr(get_adapter("detection.matrix_profile"), "max_span_samples", 500)
    _, spec, made = _export(world, MP, world["ids"][:1], label="uncapped",
                            null={"paired": False, "params": None, "draws": 0})
    res = _run_all(spec, made)[0]
    assert res["complete"] is True, res.get("error")
    assert get_adapter("detection.matrix_profile").max_span_samples == 500, "the cap is put back after the task"


def test_a_chunked_profile_is_cached_as_the_one_shot_profile(world, monkeypatch):
    """AB-joins over blocks, merged by the elementwise minimum: the cache entry the
    import brings back is the profile a one-shot local run computes."""
    from Working.execution import execute_recipe
    from Working.types import Scores

    ids = world["ids"][:1]
    twin_db = str(world["root"] / "oneshot" / "annotations.sqlite")
    os.makedirs(os.path.dirname(twin_db))
    shutil.copyfile(world["db"], twin_db)
    off = {"paired": False, "params": None, "draws": 0}
    _, spec, made = _export(world, MP, ids, label="chunked", null=off, chunk={"blockSamples": 400})
    assert spec["targets"][0]["chunks"] == [{"step": MP_STEP, "blockSamples": 400}]
    res = _run_all(spec, made)[0]
    assert res["complete"] is True, res.get("error")
    assert res["chunked"] and res["chunked"][0]["units"] > 1
    h = spec["targets"][0]["prefixHashes"][MP_STEP]
    conn = init_db(world["db"])
    try:
        chain_job.import_results(conn, spec, made["result_dir"], cache_root=cfg.STEP_CACHE_ROOT)
        row = R.get_step_artifact(conn, h, MP_STEP)
    finally:
        conn.close()
    chunked = Scores.from_path(row["path"]).values
    # the one-shot profile, computed here on a copy of the database made before the import
    monkeypatch.setattr(cfg, "STEP_CACHE_ROOT", str(world["root"] / "cache_oneshot"))
    execute_recipe(spec["targets"][0]["recipe"], db_path=twin_db)
    conn = init_db(twin_db)
    try:
        oneshot_row = R.get_step_artifact(conn, h, MP_STEP)
    finally:
        conn.close()
    oneshot = Scores.from_path(oneshot_row["path"]).values
    assert chunked.dtype == oneshot.dtype and chunked.shape == oneshot.shape
    finite = np.isfinite(oneshot)
    assert np.array_equal(finite, np.isfinite(chunked))
    np.testing.assert_allclose(chunked[finite], oneshot[finite], rtol=1e-5, atol=1e-5)


# ── the command line the script runs ───────────────────────────────────────

def test_the_command_line_computes_a_task_from_the_spec_file_and_reports_the_job(world):
    """`python -m Working.discovery.chain_job --spec … --out … --task i`, then
    `--status` for one task and for the whole job (its job.json names the tasks)."""
    _, spec, made = _export(world, CHEAP, world["ids"][:2], label="cli")
    assert chain_job.main(["--status", "--out", made["result_dir"]]) == 1, "nothing is back yet"
    assert chain_job.main(["--spec", made["spec_path"], "--out", made["result_dir"], "--task", "0",
                           "--budget-s", "600"]) == 0
    assert chain_job.main(["--status", "--out", made["result_dir"], "--task", "0"]) == 0
    assert chain_job.main(["--status", "--out", made["result_dir"]]) == 1, "task 1 is still to run"
    assert chain_job.main(["--spec", made["spec_path"], "--out", made["result_dir"], "--task", "1"]) == 0
    assert chain_job.main(["--status", "--out", made["result_dir"]]) == 0
    with open(os.path.join(made["result_dir"], "return", "task1", "result.json"), encoding="utf-8") as f:
        res = json.load(f)
    assert res["complete"] is True and res["specHash"] == chain_job.spec_hash(spec)
    assert all(not e["path"].startswith("/") and "\\" not in e["path"] for e in res["cache"]), \
        "cache paths are relative to the task folder, with forward slashes, so the folder can move"


# ── fix round (2026-10-18): the critic's findings ───────────────────────────

def test_a_task_that_raises_anything_writes_a_result_that_says_why(world, monkeypatch):
    """F1 (a): an exception the task let through left no result.json, so Jobs read the task as missing with no
    reason. Here the executor's held-out guard (`HeldOutRecordingLocked`, a RuntimeError raised before any step)."""
    _, spec, made = _export(world, CHEAP, world["ids"][:1], label="raises")
    monkeypatch.setattr(cfg, "HELD_OUT_RECORDING_FILE", "syn.mat")      # the scratch recording now reads held out
    res = chain_job.run_task(spec, task=0, out_dir=made["result_dir"])
    assert res["complete"] is False
    assert res["error"].startswith("HeldOutRecordingLocked:"), res["error"]
    assert "Traceback" in res["traceback"]
    with open(os.path.join(made["result_dir"], "return", "task0", "result.json"), encoding="utf-8") as f:
        assert json.load(f)["error"] == res["error"]
    st = chain_job.task_status(made["result_dir"], 0, spec)
    assert st["state"] == "refused" and "HeldOutRecordingLocked" in st["reason"]
    assert chain_job.main(["--status", "--out", made["result_dir"], "--task", "0"]) == 3
    # a spec the code cannot read is a result too, not a crash
    res = chain_job.run_task(dict(spec, version=99), task=0, out_dir=made["result_dir"])
    assert res["complete"] is False and "version" in res["error"]


def test_an_m4_target_exported_with_the_lock_off_runs_on_its_scratch_database(world, monkeypatch):
    """F1 (b): the scratch database is built by `init_db()` and has no settings row, which the held-out lock reads
    as locked. A held-out target exported while the lock is off carries `heldOutUnlocked` (only such a target: every
    other spec keeps its hash), and its scratch database is written with the lock off."""
    from Working.registration import settings as S

    conn = init_db(world["db"])
    npy = world["root"] / "m4_CH0.npy"
    np.save(npy, _coloured(11))
    m4 = q.insert_recording(conn, S.HELD_OUT_FILE, 0, FS, N, 0, str(npy))
    S.put_settings(conn, S.HELD_OUT_PAGE, {S.HELD_OUT_ON_KEY: False}, confirm_name=S.held_out_state(conn)["name"])
    conn.close()
    # this branch's plan and executor read the lock from Working.config; P1's predicate reads the settings row
    monkeypatch.setattr(fanout, "HELD_OUT_UNLOCK", True, raising=False)
    monkeypatch.setattr(cfg, "HELD_OUT_UNLOCK", True, raising=False)
    off = {"paired": False, "params": None, "draws": 0}
    _, spec, made = _export(world, CHEAP, [m4, world["ids"][0]], label="m4_unlocked", null=off)
    t_m4, t_v = spec["targets"]
    assert t_m4.get("heldOutUnlocked") is True
    assert "heldOutUnlocked" not in t_v, "the key rides only on a held-out target exported with the lock off"
    res = chain_job.run_task(spec, task=0, out_dir=made["result_dir"])
    assert res["complete"] is True, res.get("error")
    sconn = init_db(os.path.join(made["result_dir"], "work", "task0", "scratch.sqlite"))
    try:
        assert S.held_out_state(sconn)["on"] is False, "the scratch database reads the lock as the export did"
    finally:
        sconn.close()
    # exported with the lock on, the same target carries no key and its scratch database reads locked
    conn = init_db(world["db"])
    S.put_settings(conn, S.HELD_OUT_PAGE, {S.HELD_OUT_ON_KEY: True})
    conn.close()
    _, spec2, made2 = _export(world, CHEAP, [m4], label="m4_locked", null=off)
    assert "heldOutUnlocked" not in spec2["targets"][0]
    chain_job.run_task(spec2, task=0, out_dir=made2["result_dir"])
    sconn = init_db(os.path.join(made2["result_dir"], "work", "task0", "scratch.sqlite"))
    try:
        assert S.held_out_state(sconn)["on"] is True
    finally:
        sconn.close()


def test_auto_and_stump_key_a_profile_apart(world):
    """F2: `backend` stays in the step-cache key — every overnight matrix-profile spec's prefix hashes include it,
    and removing it would refuse their import. So the overnight GPU profiles (`backend: auto`) are not the
    profiles `mp_threshold` and its variants (`backend: stump`) look up; the shared detrend is."""
    auto_steps = [MP[0], {**MP[1], "params": {"window_min": 1.0, "backend": "auto"}}, MP[2]]
    conn = init_db(world["db"])
    try:
        auto = fanout.target_recipe(_plan(conn, auto_steps, world["ids"][:1])["recipe"], 0, True)
        stump = fanout.target_recipe(_plan(conn, MP, world["ids"][:1])["recipe"], 0, True)
    finally:
        conn.close()
    assert _recipe_prefix_hash(auto, 0, "V") == _recipe_prefix_hash(stump, 0, "V")
    assert _recipe_prefix_hash(auto, MP_STEP, "V") != _recipe_prefix_hash(stump, MP_STEP, "V")


def _restorable(world, label, n=2):
    _, spec, made = _export(world, CHEAP, world["ids"][:n], label=label)
    _run_all(spec, made)
    return spec, made


def _rows(conn):
    return [(r["recipe_prefix_hash"], int(r["step_index"]), r["path"])
            for r in conn.execute("SELECT * FROM step_artifacts ORDER BY id")]


def test_a_restore_that_fails_half_way_serves_no_half_entry_and_the_next_one_completes(world, monkeypatch):
    """F3 (the core's part): the second entry's copy fails part-way (a full disk). The entries already restored
    stay (each a whole, valid cache entry); the half-copied one is neither registered nor sitting where the cache
    reads it; a second restore completes, with no debris in the entry."""
    spec, made = _restorable(world, "half_way")
    conn = init_db(world["db"])
    try:
        checked = chain_job.verify_results(conn, spec, made["result_dir"])
        real, calls = shutil.copytree, {"n": 0}

        def flaky(src, dst, *a, **k):
            calls["n"] += 1
            if calls["n"] == 2:
                os.makedirs(dst, exist_ok=True)
                with open(os.path.join(dst, "partial.bin"), "wb") as f:
                    f.write(b"x")
                raise OSError("disk full (simulated)")
            return real(src, dst, *a, **k)

        monkeypatch.setattr(chain_job.shutil, "copytree", flaky)
        with pytest.raises(OSError, match="disk full"):
            chain_job.restore_cache(conn, checked, cache_root=cfg.STEP_CACHE_ROOT)
        assert len(_rows(conn)) == 1
        h, k = checked["copy"][1][0], checked["copy"][1][1]
        assert R.get_step_artifact(conn, h, k) is None
        assert not os.path.exists(os.path.join(cfg.STEP_CACHE_ROOT, h, str(k))), "no half entry where it is read"
        monkeypatch.setattr(chain_job.shutil, "copytree", real)
        got = chain_job.restore_cache(conn, checked, cache_root=cfg.STEP_CACHE_ROOT)
        assert got["already"] == 1 and got["copied"] == len(checked["copy"]) - 1
        assert not os.path.exists(os.path.join(cfg.STEP_CACHE_ROOT, h, str(k), "partial.bin"))
    finally:
        conn.close()


def test_a_cancel_during_restore_stops_between_entries_and_serves_no_half_entry(world):
    """F4: the restore checks a cancel between entries: it stops, keeps the whole entries it restored, leaves
    none half-copied, and says it was cancelled (`RestoreCancelled`) rather than returning as if done."""
    spec, made = _restorable(world, "cancel_restore")
    conn = init_db(world["db"])
    try:
        checked = chain_job.verify_results(conn, spec, made["result_dir"])
        assert len(checked["copy"]) >= 3
        calls = {"n": 0}

        def stop():
            calls["n"] += 1
            return calls["n"] > 1                     # the first entry is restored, then the cancel lands

        with pytest.raises(chain_job.RestoreCancelled):
            chain_job.restore_cache(conn, checked, cache_root=cfg.STEP_CACHE_ROOT, should_cancel=stop)
        rows = _rows(conn)
        assert len(rows) == 1 and os.path.isdir(rows[0][2])
        for h, k, _src, _n in checked["copy"][1:]:
            dst = os.path.join(cfg.STEP_CACHE_ROOT, h, str(k))
            assert not os.path.exists(dst) and not os.path.exists(dst + ".part")
        got = chain_job.restore_cache(conn, checked, cache_root=cfg.STEP_CACHE_ROOT)
        assert got["already"] == 1 and got["copied"] == len(checked["copy"]) - 1
    finally:
        conn.close()


def test_collect_hashes_the_spec_once_per_job(world, monkeypatch):
    """F6: Jobs reads every chain job's state on every refresh; the spec's hash was recomputed once per task
    (0.30 s for the overnight sweep's 674 tasks)."""
    off = {"paired": False, "params": None, "draws": 0}
    _, spec, made = _export(world, CHEAP, world["ids"][:3], label="once", null=off)
    _run_all(spec, made)                              # a result on disk is what each task's state is read from
    real, calls = chain_job.spec_hash, {"n": 0}

    def counting(s):
        calls["n"] += 1
        return real(s)

    monkeypatch.setattr(chain_job, "spec_hash", counting)
    st = chain_job.collect(spec, made["result_dir"])
    assert st["total"] == 3 and [t["state"] for t in st["tasks"]] == ["complete"] * 3
    assert calls["n"] == 1
