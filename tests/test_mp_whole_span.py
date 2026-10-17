"""
test_mp_whole_span.py
=====================
Round A_2, P2: matrix profiles over the whole span (the researcher's decision of
2026-10-17: "the time limit only governs local runs").

* **The cap is routing, not a refusal.** `detection.matrix_profile` and FLUSS carry
  a `max_span_samples` calibrated from this machine's speed (the local background
  budget). It is now checked only when the step is about to COMPUTE: a cached
  profile is served whatever its length, and Discovery's plan sends an uncached
  over-cap chain to the cluster instead of refusing it.
* **A profile's file is named by what produced it**, as the window matrix's is:
  two spans and a surrogate draw of one chain write three files, not one.
* **`run_recipe.py` keeps the `surrogate` flag**, so a recipe file hashes as the
  run it came from.
* **Chunked profiles** (AB-joins over blocks, merged by the elementwise minimum,
  indices kept) equal the one-shot profile, and resume from their checkpoint.
* **Wall limits per partition** are recorded, the unverified ones said so.

    PYTHONIOENCODING=utf-8 python -m pytest tests/test_mp_whole_span.py -q -p no:cacheprovider
"""

import json
import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import Adapters.detection_matrix_profile as MPA  # noqa: E402
import Working.config as cfg  # noqa: E402
from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working import run_groups  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database import runs as R  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.discovery import fanout  # noqa: E402
from Working.execution import execute_recipe  # noqa: E402
from Working.recipes import make_recipe, short_hash  # noqa: E402

discover_adapters()

FS = 1.0
N = 3000
MP = [
    {"stage": "preprocessing", "algorithm": "detrend", "params": {"mode": "rolling_mean", "window_s": 300.0}},
    {"stage": "detection", "algorithm": "matrix_profile", "params": {"window_min": 1.0, "backend": "stump"}},
    {"stage": "detection", "algorithm": "threshold", "params": {"threshold": 3.0}},
]
CAP = 500


def _walk(seed, n=N):
    rng = np.random.default_rng(seed)
    x = np.cumsum(rng.standard_normal(n))
    return x - np.linspace(x[0], x[-1], n)


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "t.sqlite")
    conn = init_db(path)
    ids = []
    for ch in range(2):
        npy = tmp_path / f"CH{ch}.npy"
        np.save(npy, _walk(ch))
        ids.append(q.insert_recording(conn, "syn.mat", ch, FS, N, 0, str(npy), units="V"))
    conn.close()
    monkeypatch.setattr(cfg, "STEP_CACHE_ROOT", str(tmp_path / "cache"))
    monkeypatch.setattr(cfg, "STEP_CACHE_WRITE_THRESHOLD_S", 0.0)
    monkeypatch.setattr(MPA, "RESULTS_DIR", str(tmp_path / "mp"))
    return {"path": path, "ids": ids, "tmp": tmp_path}


def _cap(monkeypatch, value):
    monkeypatch.setattr(get_adapter("detection.matrix_profile"), "max_span_samples", value)


# ── the cap is checked where the step computes ──────────────────────────────

def test_a_cached_over_cap_profile_is_served(db, monkeypatch):
    recipe = make_recipe(db["ids"][0], MP, span=(0, N))
    _cap(monkeypatch, None)
    first = execute_recipe(recipe, db_path=db["path"])          # computed where no cap applies (the cluster)
    assert first["detections_written"] >= 0
    _cap(monkeypatch, CAP)
    again = execute_recipe(recipe, db_path=db["path"], force=True)
    assert float(again["step_timings"][1]) == 0.0, "the profile came from the step cache"
    # an uncached over-cap profile is still refused here, by name
    other = make_recipe(db["ids"][0], [MP[0], {**MP[1], "params": {"window_min": 2.0, "backend": "stump"}}, MP[2]],
                        span=(0, N))
    with pytest.raises(Exception, match="max_span_samples"):
        execute_recipe(other, db_path=db["path"])


def test_an_over_cap_profile_routes_to_the_cluster_instead_of_refusing(db, monkeypatch):
    _cap(monkeypatch, CAP)
    conn = init_db(db["path"])
    try:
        plan = fanout.plan(conn, steps=MP, recording_ids=db["ids"], span=(0, N), ceiling_s=1e9,
                           null_draws=0, surrogate=False)
    finally:
        conn.close()
    assert plan["runnable"] is True, "over the cap is not a refusal"
    assert plan["route"] == "cluster", "even under the time ceiling: the cap is this machine's budget"
    assert [(c["recording_id"], c["step"], c["name"]) for c in plan["capped"]] == \
        [(db["ids"][0], 1, "detection.matrix_profile"), (db["ids"][1], 1, "detection.matrix_profile")]
    assert plan["capped"][0]["cap"] == CAP and plan["capped"][0]["samples"] == N
    # computed elsewhere and cached: the same plan now runs here
    _cap(monkeypatch, None)
    for rid in db["ids"]:
        run_groups.run_paired_recipe(make_recipe(rid, MP, span=(0, N)), db_path=db["path"], surrogate=False)
    _cap(monkeypatch, CAP)
    conn = init_db(db["path"])
    try:
        again = fanout.plan(conn, steps=MP, recording_ids=db["ids"], span=(0, N), ceiling_s=1e9,
                            null_draws=0, surrogate=False)
    finally:
        conn.close()
    assert again["capped"] == [] and again["route"] != "cluster"
    assert all(1 in c["cached"] for c in again["costs"])


def test_the_plan_counts_only_the_steps_the_cache_does_not_hold(db, monkeypatch):
    """A cached step costs nothing, in the real run and in each null draw: the
    estimate is what will really be computed."""
    from Working.discovery import routing

    conn = init_db(db["path"])
    try:
        recipe = fanout.target_recipe(make_recipe(db["ids"][0], MP, span=(0, N),
                                                  fan_out={"kind": "channels", "targets": [db["ids"][0]]}),
                                      0, surrogate=True)
        cold = routing.target_cost(conn, recipe, samples=N, fs=FS, draws=2,
                                   surrogate_params={"method": "phase_randomize", "seed": 0})
    finally:
        conn.close()
    assert cold["cached"] == [] and cold["draws_cached"] == 0
    run_groups.run_paired_recipe(recipe, db_path=db["path"], surrogate=True,
                                 surrogate_params={"method": "phase_randomize", "seed": 0}, surrogate_draws=1)
    conn = init_db(db["path"])
    try:
        warm = routing.target_cost(conn, recipe, samples=N, fs=FS, draws=2,
                                   surrogate_params={"method": "phase_randomize", "seed": 0})
    finally:
        conn.close()
    assert warm["cached"] == [0, 1, 2]
    assert warm["draws_cached"] == 1, "one draw was made; the second is still to compute"


def test_the_route_helper_reads_cache_and_cap_in_one_place():
    from Working.discovery import routing

    assert routing.cap_kind("detection.matrix_profile") == "time"
    assert routing.cap_kind("detection.fluss") == "time"
    assert routing.cap_kind("catalogue.gramian_gasf") == "memory"
    assert routing.cap_kind("preprocessing.detrend") is None
    assert routing.step_route({"cached": True, "over_cap": True, "cap_kind": "time"}) == "cached"
    assert routing.step_route({"cached": False, "over_cap": True, "cap_kind": "time"}) == "cluster"
    assert routing.step_route({"cached": False, "over_cap": True, "cap_kind": "memory"}) == "refused"
    assert routing.step_route({"cached": False, "over_cap": False, "cap_kind": None}) == "local"


# ── persist names carry the producing prefix ────────────────────────────────

def test_two_spans_and_a_surrogate_draw_write_three_profile_files(db):
    rid = db["ids"][0]
    a = make_recipe(rid, MP, span=(0, 1500))
    b = make_recipe(rid, MP, span=(1500, 3000))
    out_a = run_groups.run_paired_recipe(a, db_path=db["path"], surrogate=True,
                                         surrogate_params={"method": "phase_randomize", "seed": 0}, surrogate_draws=1)
    out_b = execute_recipe(b, db_path=db["path"])
    conn = init_db(db["path"])
    try:
        paths = [r["path"] for rid_ in (out_a["run_id"], out_b["run_id"], out_a["surrogate_run_ids"][0])
                 for r in R.list_artifacts(conn, rid_)]
    finally:
        conn.close()
    assert len(paths) == 3 and len(set(paths)) == 3, paths
    assert all(os.path.isfile(p) for p in paths)
    names = [os.path.basename(p) for p in paths]
    assert "_span0-1500_" in names[0] and "_span1500-3000_" in names[1] and "_span0-1500_" in names[2]


def test_the_registration_scanner_reads_the_keyed_profile_name():
    from Working.registration.kinds import _MP_NAME

    m = _MP_NAME.match("mp_v2_syn_CH0_WIN1min_span0-1500_0a1b2c3d.npz")
    assert m and m.group("a") == "0" and m.group("b") == "1500"
    assert _MP_NAME.match("mp_v2_syn_CH0_WIN1min.npz"), "the old name still reads"


# ── run_recipe.py keeps the recipe it was given ─────────────────────────────

def test_run_recipe_keeps_the_surrogate_flag(db, tmp_path):
    from Pipelines.run_recipe.run_recipe import load_recipe_from_file

    recipe = make_recipe(db["ids"][0], MP, span=(0, N))
    recipe["surrogate"] = True
    path = tmp_path / "r.json"
    path.write_text(json.dumps(recipe), encoding="utf-8")
    loaded = load_recipe_from_file(str(path))
    assert loaded.get("surrogate") is True
    assert short_hash(loaded) == short_hash(recipe), "the file hashes as the run it came from"


# ── chunked profiles ────────────────────────────────────────────────────────

def _motif_walk(seed=3, n=N):
    x = _walk(seed, n)
    shape = 4.0 * np.sin(np.linspace(0, 2 * np.pi, 50))
    for a in (300, 1400, 2500):
        x[a:a + 50] += shape
    return x


@pytest.mark.parametrize("block", [300, 700, 2000])
def test_a_chunked_profile_equals_the_one_shot_profile(block):
    import stumpy
    from Working.Detection.matrix_profiling import mp_chunks

    x, m = _motif_walk(), 50
    one = stumpy.stump(x, m)
    p_one = one[:, 0].astype(float)
    out = mp_chunks.chunked_profile(x, m, block=block)
    assert out["complete"] is True and out["units"] >= 1
    p, i = out["P"], out["I"]
    assert p.shape == p_one.shape and i.dtype.kind == "i"
    np.testing.assert_allclose(p, p_one, rtol=1e-7, atol=1e-7)
    # every index points at a true neighbour at the reported distance
    from stumpy import core
    for k in range(0, len(p), 97):
        d = core.mass(x[k:k + m], x[i[k]:i[k] + m])[0]
        assert abs(d - p[k]) < 1e-6
    assert np.mean(i == one[:, 1].astype(int)) > 0.99


def test_a_chunked_profile_resumes_from_its_checkpoint(tmp_path):
    from Working.Detection.matrix_profiling import mp_chunks

    x, m = _motif_walk(), 50
    whole = mp_chunks.chunked_profile(x, m, block=400)
    calls = {"n": 0}

    def stop_after_three():
        calls["n"] += 1
        return calls["n"] > 3

    part = mp_chunks.chunked_profile(x, m, block=400, state_dir=str(tmp_path / "st"), should_stop=stop_after_three)
    assert part["complete"] is False and 0 < part["done"] < part["units"]
    rest = mp_chunks.chunked_profile(x, m, block=400, state_dir=str(tmp_path / "st"))
    assert rest["complete"] is True and rest["resumed"] == part["done"]
    np.testing.assert_array_equal(rest["P"], whole["P"])
    np.testing.assert_array_equal(rest["I"], whole["I"])


# ── the wall per partition ──────────────────────────────────────────────────

def test_wall_limits_are_recorded_per_partition_and_the_unverified_ones_say_so():
    from Working.hpc import job_export

    assert job_export.partition_wall_minutes("a100-test") == (20, True)
    minutes, verified = job_export.partition_wall_minutes("cpu")
    assert verified is False and minutes == cfg.HPC_MAX_WALLTIME_MINUTES
    assert isinstance(cfg.HPC_WALLTIME_MINUTES_BY_PARTITION, dict)
