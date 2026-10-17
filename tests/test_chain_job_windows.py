"""
test_chain_job_windows.py
=========================
Round A_2, P3: a windowed application goes to the cluster as a chain job (`Working.discovery.chain_job`, P2) and comes
back as one stitched Discovery run, every window an ordinary run.

What has to hold at the researcher's scales (the RQ4 sweep: 10-minute and 1-hour windows over 721 h, 16 channels —
1,441 to 8,651 windows per channel):

* **The spec stays small.** One task per channel, as for a whole-span run; each task names its windows (their spans)
  and every window's config hash, so the cluster asserts each window's recipe before it runs it.
* **The cluster runs every window and its draws** on its scratch database, and its result carries each window's
  detections (and each draw's): the windows' steps are too quick for the step cache to keep, so the cache cannot
  carry them back.
* **The import checks every window** against the spec and this machine, writes the window runs, and the ordinary local
  sweep then computes nothing: it reuses every window and stitches. The stitched set equals a run made here from
  nothing.

    PYTHONIOENCODING=utf-8 python -m pytest tests/test_chain_job_windows.py -q -p no:cacheprovider
"""

import json
import os
import shutil
import sys

import numpy as np
import pytest
from scipy.signal import lfilter

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import Working.config as cfg  # noqa: E402
from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database import runs as R  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.discovery import chain_job, fanout  # noqa: E402
from Working.execution import _recipe_prefix_hash  # noqa: E402
from Working.recipes import short_hash  # noqa: E402

discover_adapters()

FS = 1.0
H = 3600
N = 12 * H
NT = [{"stage": "preprocessing", "algorithm": "detrend", "params": {"mode": "rolling_mean", "window_s": 300.0}},
      {"stage": "detection", "algorithm": "noise_threshold",
       "params": {"k_sigma": 3.5, "direction": "below", "min_duration_s": 20.0, "merge_gap_s": 30.0}}]
NULL = {"paired": True, "params": {"method": "phase_randomize", "seed": 0}, "draws": 1}
WINDOWS = {"window_s": 2 * H, "overlap_frac": 0.5}
PER_CHANNEL = 11                       # (12 h - 2 h) / 1 h + 1


def _coloured(seed, n=N):
    """AR(1) at phi 0.97, a slow drift, and a drop every 50 minutes."""
    rng = np.random.default_rng(seed)
    x = lfilter([1.0], [1.0, -0.97], rng.standard_normal(n) * 0.001)
    x += 0.02 * np.sin(np.linspace(0, 3 * np.pi, n))
    for a in range(600, n - 600, 3000):
        x[a:a + 120] -= 0.03 * np.exp(-np.linspace(0, 3, 120))
    return x


@pytest.fixture
def world(tmp_path, monkeypatch):
    root = tmp_path
    db = str(root / "a" / "annotations.sqlite")
    os.makedirs(os.path.dirname(db))
    conn = init_db(db)
    ids = []
    for ch in range(2):
        npy = root / f"syn_CH{ch}.npy"
        np.save(npy, _coloured(ch))
        ids.append(q.insert_recording(conn, "syn.mat", ch, FS, N, 0, str(npy), units="V"))
    conn.close()
    monkeypatch.setattr(cfg, "STEP_CACHE_ROOT", str(root / "cache_a"))
    return {"root": root, "db": db, "ids": ids, "hpc": str(root / "hpc")}


def _plan(conn, ids, windows=WINDOWS, null=NULL, span=(0, N)):
    return fanout.plan(conn, steps=NT, recording_ids=ids, span=span, ceiling_s=1200,
                       null_draws=(null["draws"] if null["paired"] else 0), surrogate=null["paired"],
                       surrogate_params=null["params"], windows=windows)


def _export(world, ids=None, *, label="win", windows=WINDOWS):
    conn = init_db(world["db"])
    try:
        plan = _plan(conn, ids or world["ids"], windows=windows)
        assert plan["runnable"], plan["reason"]
        spec = chain_job.build_spec(conn, plan, label=label, null=NULL)
    finally:
        conn.close()
    made = chain_job.write_job(spec, out_dir=world["hpc"], base_name=label)
    return plan, spec, made


def _run_all(spec, made):
    return [chain_job.run_task(spec, task=i, out_dir=made["result_dir"]) for i in range(spec["tasks"])]


def _stitched(conn, out):
    return [[(int(d["start_idx"]), int(d["end_idx"])) for d in R.list_detections(conn, r["run_id"])]
            for r in out["runs"]]


# ── the spec ────────────────────────────────────────────────────────────────

def test_a_windowed_spec_is_one_task_per_channel_naming_every_window(world):
    plan, spec, made = _export(world)
    assert spec["tasks"] == 2 and len(spec["targets"]) == 2, "one task per channel, as a whole-span run"
    assert spec["windows"]["scope"] == plan["windows"]["scope"]
    assert spec["windows"]["rule"] == plan["windows"]["rule"], "the stitch rule travels with the spec"
    assert "#SBATCH --array=0-1" in made["script"]
    for c, t in enumerate(spec["targets"]):
        mine = [i for i, pt in enumerate(plan["targets"]) if pt["recording_id"] == world["ids"][c]]
        assert len(mine) == PER_CHANNEL
        assert t["windows"]["spans"] == [list(plan["targets"][i]["span"]) for i in mine]
        assert t["windows"]["configHashes"] == [short_hash(fanout.target_recipe(plan["recipe"], i, True))
                                                for i in mine], "every window's config hash is in the spec"
        first = fanout.target_recipe(plan["recipe"], mine[0], True)
        assert t["recipe"] == first and t["configHash"] == short_hash(first)
        assert t["prefixHashes"] == [_recipe_prefix_hash(first, k, "V") for k in range(len(NT))]
        assert t["span"] == [0, N] and t["chunks"] == []


def test_a_whole_recording_of_short_windows_exports_as_a_small_spec(world):
    """10-minute windows over 721 h (M2_aug's length) are 8,651 windows on one channel: one task, a spec of well
    under a megabyte. One target per window would have been 8,651 array tasks, each its own scratch database."""
    n = 2595600
    npy = world["root"] / "long_CH0.npy"
    np.save(npy, np.zeros(n, dtype=np.float32))
    conn = init_db(world["db"])
    try:
        rid = q.insert_recording(conn, "long.mat", 0, FS, n, 0, str(npy), units="V")
        plan = _plan(conn, [rid], windows={"window_s": 600, "fit": True}, span=None)
        assert plan["runnable"], plan["reason"]
        assert plan["windows"]["per_channel"] == 8651
        spec = chain_job.build_spec(conn, plan, label="long", null=NULL)
    finally:
        conn.close()
    assert spec["tasks"] == 1 and len(spec["targets"][0]["windows"]["spans"]) == 8651
    size = len(json.dumps(spec, indent=2))
    assert size < 2_000_000, f"{size} bytes"


# ── the cluster ─────────────────────────────────────────────────────────────

def test_the_cluster_task_runs_every_window_and_its_draws(world):
    _, spec, made = _export(world)
    res = chain_job.run_task(spec, task=0, out_dir=made["result_dir"])
    assert res["complete"] is True, res.get("error")
    assert res["cache"] == [], "no step cache comes back: the window runs do"
    ws = res["windows"]
    assert [w["configHash"] for w in ws] == spec["targets"][0]["windows"]["configHashes"]
    assert [w["span"] for w in ws] == spec["targets"][0]["windows"]["spans"]
    assert all(len(w["draws"]) == 1 for w in ws)
    assert sum(len(w["detections"]) for w in ws) == res["run"]["detections"] > 0
    for w in ws:
        a, b = w["span"]
        assert all(a <= d[0] < d[1] <= b for d in w["detections"]), "channel-absolute, inside the window"


def test_a_task_stopped_between_windows_continues_where_it_stopped(world):
    _, spec, made = _export(world, ids=world["ids"][:1], label="resume")
    calls = {"n": 0}

    def cancel_after_three_windows():
        calls["n"] += 1
        return calls["n"] > 40

    first = chain_job.run_task(spec, task=0, out_dir=made["result_dir"], should_cancel=cancel_after_three_windows)
    assert first["complete"] is False and first["error"] is None
    done = len(first.get("windows") or [])
    assert 0 < done < PER_CHANNEL
    second = chain_job.run_task(spec, task=0, out_dir=made["result_dir"])
    assert second["complete"] is True
    fresh_out = str(world["root"] / "fresh_out")
    fresh = chain_job.run_task(spec, task=0, out_dir=fresh_out)
    assert [w["detections"] for w in second["windows"]] == [w["detections"] for w in fresh["windows"]]


# ── the import ──────────────────────────────────────────────────────────────

def test_the_import_writes_the_windows_and_the_local_sweep_computes_nothing(world, monkeypatch):
    twin_db = str(world["root"] / "b" / "annotations.sqlite")
    os.makedirs(os.path.dirname(twin_db))
    shutil.copyfile(world["db"], twin_db)

    plan, spec, made = _export(world)
    results = _run_all(spec, made)
    assert all(r["complete"] for r in results), [r.get("error") for r in results]
    conn = init_db(world["db"])
    try:
        assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0, "the cluster wrote nothing here"
        got = chain_job.import_results(conn, spec, made["result_dir"], cache_root=cfg.STEP_CACHE_ROOT)
        assert got["tasks"] == 2 and got["windowRuns"] == 2 * PER_CHANNEL * 2, "every window and its draw"
        local = chain_job.local_plan(conn, spec, ceiling_s=1200)
    finally:
        conn.close()
    assert local["estimate_s"] == 0.0 and local["route"] == "local", "nothing is left to compute here"

    nt = get_adapter("detection.noise_threshold")

    def boom(*a, **k):
        raise AssertionError("a window was computed here after the import")

    monkeypatch.setattr(nt, "run", boom)
    a_out = fanout.start(local, db_path=world["db"], surrogate=True, surrogate_params=NULL["params"],
                         surrogate_draws=1)
    monkeypatch.undo()
    monkeypatch.setattr(cfg, "STEP_CACHE_ROOT", str(world["root"] / "cache_b"))
    tconn = init_db(twin_db)
    try:
        twin_plan = _plan(tconn, world["ids"])
    finally:
        tconn.close()
    b_out = fanout.start(twin_plan, db_path=twin_db, surrogate=True, surrogate_params=NULL["params"],
                         surrogate_draws=1)
    aconn, bconn = init_db(world["db"]), init_db(twin_db)
    try:
        assert _stitched(aconn, a_out) == _stitched(bconn, b_out), "the imported run is the run made here"
        assert any(_stitched(aconn, a_out)), "and it found something"
        for ra, rb in zip(a_out["runs"], b_out["runs"]):
            da = [[(int(d["start_idx"]), int(d["end_idx"])) for d in R.list_detections(aconn, i)]
                  for i in ra["surrogate_run_ids"]]
            db_ = [[(int(d["start_idx"]), int(d["end_idx"])) for d in R.list_detections(bconn, i)]
                   for i in rb["surrogate_run_ids"]]
            assert da == db_, "so is its stitched null"
        counts = {c["recordingId"]: c["detections"] for c in got["counts"]}
        for r in a_out["runs"]:
            raw = sum(len(R.list_detections(aconn, w)) for w in r["window_run_ids"])
            assert counts[r["recording_id"]] == raw, "the cluster's count is the windows' own, before stitching"
    finally:
        aconn.close()
        bconn.close()


def test_the_import_refuses_a_window_computed_from_another_recipe(world):
    _, spec, made = _export(world, ids=world["ids"][:1], label="tamper")
    _run_all(spec, made)
    path = os.path.join(made["result_dir"], "return", "task0", "result.json")
    with open(path, encoding="utf-8") as f:
        res = json.load(f)
    res["windows"][3]["configHash"] = "deadbeef"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res, f)
    conn = init_db(world["db"])
    try:
        with pytest.raises(chain_job.ImportRefused) as e:
            chain_job.import_results(conn, spec, made["result_dir"], cache_root=cfg.STEP_CACHE_ROOT)
        assert "window 4" in str(e.value) and "deadbeef" in str(e.value)
        assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0, "nothing was recorded"
    finally:
        conn.close()


def test_the_import_refuses_when_the_local_windows_moved(world):
    _, spec, made = _export(world, ids=world["ids"][:1], label="moved")
    _run_all(spec, made)
    moved = json.loads(json.dumps(spec))
    moved["windows"]["scope"]["overlap_frac"] = 0.25
    conn = init_db(world["db"])
    try:
        with pytest.raises(chain_job.ImportRefused) as e:
            chain_job.local_plan(conn, moved, ceiling_s=1200)
        assert "window" in str(e.value)
    finally:
        conn.close()
