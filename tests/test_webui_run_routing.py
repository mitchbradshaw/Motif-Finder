"""
test_webui_run_routing.py
=========================
A run that cannot finish on this machine is refused before it starts, and written as a SLURM job instead
(2026-10-14: a FLUSS run over a whole recording could not be cancelled — cancel is checked between steps — and the
bridge had to be killed by hand, because the matrix-profile cost model was uncalibrated, so FLUSS had no ceiling).

* `chain.route_local` calibrates the matrix-profile cost model on first need, then routes on the estimate
  (times 1 + null draws) against the Analyse limit (Settings › Compute & HPC `limit.Analyse`, else the core's
  `CLUSTER_ROUTING_CEILING_S`);
* POST /api/runs over the limit answers 422 with a SLURM script written by `Working.hpc.job_export` and starts
  no job; under the limit it runs as before;
* the sandbox writes its calibration inside its runtime, never into the real DATA/db.

FastAPI lives only in `webui/.venv`; under the conda pytest the route tests skip with a message:

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_run_routing.py
"""

import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBUI_DIR = os.path.join(PROJECT_ROOT, "webui")
for p in (PROJECT_ROOT, WEBUI_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from Working.Detection.matrix_profiling import cost  # noqa: E402

FLUSS_STEPS = [{"stage": "detection", "algorithm": "fluss",
                "params": {"window_s": 300.0, "n_regimes_readout": 3, "iac": "parabola", "excl_factor": 5}}]


@pytest.fixture
def fake_calibration(tmp_path, monkeypatch):
    """A calibration file in tmp, and a `calibrate` that writes a known k (1e-9 s per n²) instead of timing:
    deterministic, and never the real DATA/db."""
    path = tmp_path / "mp_calibration.json"
    monkeypatch.setattr(cost, "CALIBRATION_PATH", str(path))
    # detection.fluss fixes its span cap at IMPORT time from whatever calibration file was current then
    # (`max_span_samples_for_background()`). A module that imports the registry at collection (test_webui_chain_job_route)
    # did so from the main checkout's real DATA/db/mp_calibration.json, so the cap was 678,125 here and the over-the-limit
    # test met the cap refusal, not the SLURM route (gate, 2026-10-20). The cap is this test's calibration's: none yet.
    from Adapters.registry import get_adapter
    monkeypatch.setattr(get_adapter("detection.fluss"), "max_span_samples", cost.max_span_samples_for_background())
    calls = []

    def _calibrate(backend="stump", force=False, **kw):
        data = cost._load_calibration()
        key = cost._calibration_key(backend)
        data[key] = {"k": 1e-9, "n0": 20000, "elapsed_s": 0.4, "calibrated_at": "test"}
        cost._save_calibration(data)
        calls.append(backend)
        return data[key]

    monkeypatch.setattr(cost, "calibrate", _calibrate)
    return path, calls


def _recipe(n, steps=FLUSS_STEPS):
    from Working.recipes import make_recipe
    return make_recipe(1, [dict(s) for s in steps], span=[0, n])


def test_an_uncalibrated_fluss_is_calibrated_then_routed(fake_calibration):
    from server import chain
    path, calls = fake_calibration
    assert cost.estimate_seconds(1000) is None            # the state that let a days-long run start
    small = chain.route_local(_recipe(20_000), 20_000, 1.0, ceiling_s=900)
    assert calls == ["stump"] and os.path.isfile(path)
    assert small["route"] == "local" and small["estimate_real_s"] == pytest.approx(1e-9 * 20_000 ** 2)
    whole = chain.route_local(_recipe(2_595_600), 2_595_600, 1.0, ceiling_s=900)   # one M2_aug channel, 30 days
    assert calls == ["stump"], "calibrated once, not per request"
    assert whole["route"] == "cluster"
    assert whole["slowest"]["name"] == "detection.fluss"


def test_null_draws_multiply_the_cost(fake_calibration):
    from server import chain
    n = 600_000                                            # 1e-9 * n² = 360 s: under 900 s alone, over with draws
    assert chain.route_local(_recipe(n), n, 1.0, ceiling_s=900)["route"] == "local"
    with_null = chain.route_local(_recipe(n), n, 1.0, ceiling_s=900, draws=20)
    assert with_null["route"] == "cluster" and with_null["estimate_s"] == pytest.approx(21 * 360.0)


def test_the_longest_span_that_fits_is_found_by_bisection(fake_calibration):
    from server import chain
    chain.route_local(_recipe(1000), 1000, 1.0, ceiling_s=900)                  # calibrates: k = 1e-9
    n_max = chain.max_local_samples(_recipe(2_595_600), 1.0, ceiling_s=900, upper=2_595_600)
    assert abs(n_max - (900 / 1e-9) ** 0.5) <= 2                               # sqrt(ceiling / k) = 948,683
    with_null = chain.max_local_samples(_recipe(2_595_600), 1.0, ceiling_s=900, draws=20, upper=2_595_600)
    assert abs(with_null - (900 / 21 / 1e-9) ** 0.5) <= 2
    assert chain.max_local_samples(_recipe(5000), 1.0, ceiling_s=900, upper=5000) == 5000


def test_a_chain_without_matrix_profile_steps_is_never_calibrated(fake_calibration):
    from server import chain
    path, calls = fake_calibration
    steps = [{"stage": "preprocessing", "algorithm": "detrend", "params": {"mode": "rolling_mean", "window_s": 600.0}}]
    out = chain.route_local(_recipe(100_000, steps), 100_000, 1.0, ceiling_s=900)
    assert calls == [] and not os.path.exists(path)
    assert out["route"] == "local"


def test_the_analyse_limit_reads_settings(tmp_path):
    from server import chain
    from Working.config import CLUSTER_ROUTING_CEILING_S
    from Working.database.schema import init_db
    from Working.registration.settings import put_settings
    conn = init_db(str(tmp_path / "a.sqlite"))
    assert chain.analyse_ceiling_s(conn) == CLUSTER_ROUTING_CEILING_S
    put_settings(conn, "compute-hpc", {"limit.Analyse": 5})
    assert chain.analyse_ceiling_s(conn) == 300
    conn.close()


# ── W3-F item 2: every costed block is calibrated before it is routed ───────────
# `Working.block_cost` models (MSE, snippets, MiniRocket, cycle shapes, deconvolve, …) used to route "unknown" and
# run whatever their size: only the matrix-profile model was calibrated on first need. Calibration times measured
# 2026-10-15 range from 0.5 s to minutes (snippets ~20 s), so a model is calibrated in a background thread on first
# need and `route_local` waits up to `CALIBRATION_WAIT_S` for it; past that the step reads "calibrating".

DECONV = [{"stage": "detection", "algorithm": "deconvolve", "params": {}}]


@pytest.fixture
def fake_block_cost(tmp_path, monkeypatch):
    """block_cost's calibration file in tmp, and a `calibrate` that writes a known k (1e-3 s per sample) after an
    optional delay instead of timing a block: deterministic, and never the real DATA/db."""
    from Working import block_cost
    from server import chain
    monkeypatch.setattr(block_cost, "CALIBRATION_PATH", str(tmp_path / "block_calibration.json"))
    chain.reset_block_calibration()
    state = {"calls": [], "delay": 0.0, "fail": None}

    def _calibrate(names=None, force=False, **kw):
        import time as _t
        names = list(names or [])
        state["calls"].extend(names)
        if state["delay"]:
            _t.sleep(state["delay"])
        if state["fail"]:
            raise RuntimeError(state["fail"])
        data = block_cost._load()
        for name in names:
            data[block_cost._key(name)] = {"k": 1e-3, "exponent": block_cost.MODELS[name][0], "n": 20000,
                                           "elapsed_s": 0.4, "calibrated_at": "test"}
        block_cost._save(data)
        return {name: 1e-3 for name in names}

    monkeypatch.setattr(block_cost, "calibrate", _calibrate)
    yield state
    chain.reset_block_calibration()


def _wait_for(pred, timeout=10.0):
    import time as _t
    t0 = _t.time()
    while _t.time() - t0 < timeout:
        if pred():
            return True
        _t.sleep(0.02)
    return False


def test_an_uncalibrated_block_cost_step_is_calibrated_then_routed(fake_block_cost):
    from server import chain
    from Working import block_cost
    assert block_cost.estimate_seconds("detection.deconvolve", 1000) is None     # routed "unknown" and ran, before
    small = chain.route_local(_recipe(20_000, DECONV), 20_000, 1.0, ceiling_s=900)
    assert fake_block_cost["calls"] == ["detection.deconvolve"]
    assert small["route"] == "local" and small["estimate_real_s"] == pytest.approx(1e-3 * 20_000)
    cal = small["calibration"]
    assert cal and cal["block_cost"]["detection.deconvolve"]["state"] == "calibrated"
    again = chain.route_local(_recipe(20_000, DECONV), 20_000, 1.0, ceiling_s=900)
    assert fake_block_cost["calls"] == ["detection.deconvolve"], "calibrated once, not per request"
    assert again["route"] == "local"


def test_an_over_limit_chain_with_a_block_cost_step_is_routed_to_the_cluster(fake_block_cost):
    from server import chain
    whole = chain.route_local(_recipe(2_595_600, DECONV), 2_595_600, 1.0, ceiling_s=900)
    assert whole["route"] == "cluster" and whole["slowest"]["name"] == "detection.deconvolve"


def test_a_slow_calibration_reads_calibrating_then_lands(fake_block_cost, monkeypatch):
    from server import chain
    monkeypatch.setattr(chain, "CALIBRATION_WAIT_S", 0.05)
    fake_block_cost["delay"] = 0.6
    first = chain.route_local(_recipe(20_000, DECONV), 20_000, 1.0, ceiling_s=900)
    assert first["route"] == "unknown" and first["calibrating"] == [0], first
    assert first["per_step_s"][0] is None
    est = chain.estimate(_recipe(20_000, DECONV), 20_000, 1.0)
    assert est["calibrating"] == [0], "the validate payload's estimate says which steps are calibrating"
    assert _wait_for(lambda: chain.block_calibration_state("detection.deconvolve")["state"] == "calibrated")
    later = chain.route_local(_recipe(20_000, DECONV), 20_000, 1.0, ceiling_s=900)
    assert later["route"] == "local" and later["calibrating"] == []
    assert fake_block_cost["calls"] == ["detection.deconvolve"], "one background calibration, not one per request"


def test_a_background_calibration_writes_the_file_it_started_with(fake_block_cost, tmp_path, monkeypatch):
    """A runtime restored while a minutes-long timing runs must not send its result to the checkout's DATA/db:
    the thread is handed the path resolved when it started (block_cost.calibrate(path=...))."""
    import json
    import time as _t
    from server import chain
    from Working import block_cost
    started = block_cost.CALIBRATION_PATH
    seen = {}

    def slow(names=None, force=False, path=None, **kw):
        _t.sleep(0.4)
        seen["path"] = path
        data = block_cost._load(path)
        for name in names:
            data[block_cost._key(name)] = {"k": 1e-3, "exponent": 1.0, "n": 1, "elapsed_s": 0.1, "calibrated_at": "t"}
        block_cost._save(data, path)
    monkeypatch.setattr(block_cost, "calibrate", slow)
    monkeypatch.setattr(chain, "CALIBRATION_WAIT_S", 0.01)
    chain.route_local(_recipe(20_000, DECONV), 20_000, 1.0, ceiling_s=900)
    elsewhere = tmp_path / "restored" / "block_calibration.json"
    monkeypatch.setattr(block_cost, "CALIBRATION_PATH", str(elsewhere))    # a runtime restored mid-timing
    assert _wait_for(lambda: "path" in seen)
    _t.sleep(0.2)
    assert os.path.abspath(seen["path"]) == os.path.abspath(started)
    assert not elsewhere.exists()
    with open(started, encoding="utf-8") as f:
        assert block_cost._key("detection.deconvolve") in json.load(f)


def test_block_cost_calibrate_honours_a_path(tmp_path, monkeypatch):
    import json
    from Working import block_cost
    monkeypatch.setitem(block_cost.MODELS, "w3f.fake", (1.0, lambda x, fs: None))
    p = tmp_path / "c.json"
    block_cost.calibrate(["w3f.fake"], n=100, path=str(p))
    with open(p, encoding="utf-8") as f:
        assert block_cost._key("w3f.fake") in json.load(f)
    assert not os.path.exists(block_cost.CALIBRATION_PATH) or block_cost._key("w3f.fake") not in block_cost._load()


def test_a_calibration_that_fails_says_so_in_words(fake_block_cost):
    from server import chain
    fake_block_cost["fail"] = "model_path 'MODELS/x.pth' does not exist"
    out = chain.route_local(_recipe(20_000, DECONV), 20_000, 1.0, ceiling_s=900)
    assert out["route"] == "unknown"
    assert "does not exist" in out["errors"][0] and "calibrat" in out["errors"][0]


def test_an_estimator_that_raises_reports_its_own_words(fake_block_cost, monkeypatch):
    """W2-ledger decision 24: Analyse printed "uncalibrated" for any estimate that raised; the words reach it now."""
    from server import chain
    spec = chain.get_adapter("detection.deconvolve")

    def boom(*a, **k):
        raise ValueError("needs a registered model checkpoint")
    monkeypatch.setattr(spec, "estimate", boom)
    out = chain.route_local(_recipe(20_000, DECONV), 20_000, 1.0, ceiling_s=900)
    assert out["route"] == "unknown"
    assert out["errors"] == {0: "ValueError: needs a registered model checkpoint"}


def test_a_chain_without_costed_steps_starts_no_calibration(fake_block_cost):
    from server import chain
    steps = [{"stage": "preprocessing", "algorithm": "detrend", "params": {"mode": "rolling_mean", "window_s": 600.0}}]
    chain.route_local(_recipe(100_000, steps), 100_000, 1.0, ceiling_s=900)
    assert fake_block_cost["calls"] == []


def test_the_catalog_card_says_whether_a_side_input_is_required():
    """W3-B: cycle shapes' waveform is optional; the insert modal showed "needs waveform" as mandatory."""
    from server import chain
    card = chain.adapter_card(chain.get_adapter("interrogation.cycle_shapes"))
    assert card["side_inputs"] and card["side_inputs"][0]["required"] is False


# ── the routes ──────────────────────────────────────────────────────────────

fastapi = pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv; run this file with that interpreter")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")


@pytest.fixture
def bridge(tmp_path, fake_calibration):
    from fastapi.testclient import TestClient
    from server.app import create_app
    from server.runtime import Runtime
    from Working.database.schema import init_db
    n = 2_595_600
    npy = tmp_path / "ch.npy"
    np.save(npy, np.zeros(n, dtype=np.float32))
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    conn = init_db(str(db_dir / "annotations.sqlite"))
    conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                 "VALUES ('long.mat', 0, 1.0, ?, 0, ?)", (n, str(npy)))
    conn.commit()
    rid = conn.execute("SELECT id FROM recordings").fetchone()[0]
    conn.close()
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    rt = Runtime(mode="sandbox", stamp="20261014-routing", db_source=str(db_dir / "annotations.sqlite"),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(dist))
    rt.setup()
    try:
        # setup() redirected the calibration into the runtime; keep the fake calibrate writing there
        with TestClient(create_app(rt)) as client:
            yield client, rt, rid, n
    finally:
        rt.restore()


def test_the_sandbox_keeps_its_calibration_inside_the_runtime(bridge):
    client, rt, rid, n = bridge
    assert os.path.abspath(cost.CALIBRATION_PATH).lower().startswith(os.path.abspath(rt.dir).lower())


def test_the_sandbox_keeps_the_block_cost_calibration_inside_the_runtime(bridge):
    """block_cost's file is relative (DATA/db/block_calibration.json): calibrated from a sandbox bridge it would land
    in the real DATA/db of the checkout the bridge chdir'd to."""
    from Working import block_cost
    client, rt, rid, n = bridge
    assert os.path.abspath(block_cost.CALIBRATION_PATH).lower().startswith(os.path.abspath(rt.dir).lower())


def test_a_block_cost_run_over_the_limit_is_refused_with_a_slurm_job(bridge, fake_block_cost):
    client, rt, rid, n = bridge
    r = client.post("/api/runs", json={"recording_id": rid, "span": [0, n], "steps": DECONV})
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert detail["route"] == "cluster" and "detection.deconvolve" in detail["message"]
    assert os.path.isfile(detail["slurm"]["script_path"])


def test_a_run_over_the_limit_is_refused_with_a_slurm_job_and_no_job_starts(bridge):
    client, rt, rid, n = bridge
    r = client.post("/api/runs", json={"recording_id": rid, "span": [0, n], "steps": FLUSS_STEPS})
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert detail["route"] == "cluster" and "SLURM" in detail["message"] and "detection.fluss" in detail["message"]
    slurm = detail["slurm"]
    assert os.path.isfile(slurm["script_path"]) and os.path.isfile(slurm["recipe_path"])
    assert os.path.abspath(slurm["script_path"]).lower().startswith(os.path.abspath(rt.dir).lower())
    with open(slurm["script_path"], "rb") as f:
        body = f.read()
    assert b"\r\n" not in body and b"run_recipe.py" in body          # sbatch refuses CRLF
    assert slurm["sbatch_command"].startswith("sbatch ")
    # 1e-9 * 2.6M² ≈ 1.9 h: over the cluster's wall-time cap too, which the refusal must say, with spans that fit
    assert abs(detail["max_local_samples"] - (900 / 1e-9) ** 0.5) <= 2
    assert "killed" in detail["message"] and slurm["over_walltime"] is True
    from Working.config import HPC_MAX_WALLTIME_MINUTES
    assert abs(detail["max_cluster_samples"] - (HPC_MAX_WALLTIME_MINUTES * 60 / 1e-9) ** 0.5) <= 2
    assert client.get("/api/runs").status_code == 200
    jobs = client.get("/api/jobs").json()
    assert not [j for j in (jobs if isinstance(jobs, list) else jobs.get("jobs", []))
                if j.get("kind") in (None, "chain") and j.get("status") in ("running", "queued")]


def test_validate_reports_the_route_before_run(bridge):
    client, rt, rid, n = bridge
    v = client.post("/api/chain/validate", json={"recording_id": rid, "span": [0, n], "steps": FLUSS_STEPS}).json()
    assert v["route"]["route"] == "cluster" and v["route"]["slowest"]["name"] == "detection.fluss"
    short = client.post("/api/chain/validate", json={"recording_id": rid, "span": [0, 20_000], "steps": FLUSS_STEPS}).json()
    assert short["route"]["route"] == "local"


# ── W3-F fix round 1 ────────────────────────────────────────────────────────────

def test_a_run_whose_cost_model_is_still_calibrating_is_refused_with_409(bridge, fake_block_cost, monkeypatch):
    """Critic finding 5: the block page's Run was not held, and POST /api/runs then started blind after 10 s.
    Every entry point is covered server-side: a calibrating step answers 409 in words, and no job starts."""
    from server import chain
    client, rt, rid, n = bridge
    monkeypatch.setattr(chain, "CALIBRATION_WAIT_S", 0.05)
    fake_block_cost["delay"] = 1.5
    r = client.post("/api/runs", json={"recording_id": rid, "span": [0, 20_000], "steps": DECONV})
    assert r.status_code == 409, r.text
    assert "calibrating" in str(r.json()["detail"])
    jobs = client.get("/api/runs").json()["jobs"]
    assert not [j for j in jobs if j["status"] in ("running", "queued")]
    assert _wait_for(lambda: chain.block_calibration_state("detection.deconvolve")["state"] == "calibrated")
    ok = client.post("/api/runs", json={"recording_id": rid, "span": [0, 20_000], "steps": DECONV})
    assert ok.status_code == 200, ok.text


def test_one_slow_calibration_does_not_hold_another_model(fake_block_cost, monkeypatch):
    """Critic finding 4: one lock for every model meant rupture's 447 s calibration held MSE and snippets."""
    import time as _t
    from server import chain
    from Working import block_cost
    monkeypatch.setitem(block_cost.MODELS, "w3f.slow_model", (1.0, lambda x, fs: None))
    real_fake = block_cost.calibrate

    def calibrate(names=None, force=False, **kw):
        if "w3f.slow_model" in (names or []):
            _t.sleep(3.0)
        return real_fake(names, force, **kw)
    monkeypatch.setattr(block_cost, "calibrate", calibrate)
    slow = chain._ensure_block_calibration("w3f.slow_model")
    assert slow is not None
    _t.sleep(0.1)
    monkeypatch.setattr(chain, "CALIBRATION_WAIT_S", 1.0)
    out = chain.route_local(_recipe(20_000, DECONV), 20_000, 1.0, ceiling_s=900)
    assert out["calibrating"] == [] and out["route"] == "local", \
        "the fast model waited behind the slow one's calibration"
    slow.join(5)


def test_a_step_cancelled_from_inside_reads_cancelled_in_history(bridge, monkeypatch):
    """Critic finding 3: History flags a run cancelled only when its error text starts with "Cancelled"; a block's
    own words ("… cancelled after 3 of 55 windows") read as failed."""
    import time as _t
    from Adapters import registry
    from Adapters.base import AdapterResult, AdapterSpec
    from Working.execution import RecipeCancelled
    from Working.types import Scores
    client, rt, rid, n = bridge
    ticks = []

    def run(x, t, fs, should_cancel=None):
        for i in range(400):
            if should_cancel is not None and should_cancel():
                raise RecipeCancelled(f"fake block stopped after {i} of 400 iterations")
            ticks.append(i)
            _t.sleep(0.02)
        return AdapterResult(output_kind="scores", value=Scores(values=np.zeros(len(x)), fs=fs), meta={})
    monkeypatch.setitem(registry._REGISTRY, "detection.w3f_history_fake", AdapterSpec(
        name="detection.w3f_history_fake", display_name="fake", stage="detection", params=[], run=run,
        output_kind="scores", input_kind="signal", category="detect", description="fake"))
    steps = [{"stage": "detection", "algorithm": "w3f_history_fake", "params": {}}]
    job = client.post("/api/runs", json={"recording_id": rid, "span": [0, 2000], "steps": steps})
    assert job.status_code == 200, job.text
    jid = job.json()["job_id"]
    assert _wait_for(lambda: len(ticks) >= 3)
    client.post(f"/api/runs/{jid}/cancel")
    assert _wait_for(lambda: client.get(f"/api/runs/{jid}").json()["status"] != "running")
    assert client.get(f"/api/runs/{jid}").json()["status"] == "cancelled"
    rows = client.get("/api/runs").json()["db_runs"]
    mine = [r for r in rows if r["steps"] == ["detection.w3f_history_fake"]]
    assert mine and mine[0]["cancelled"] is True, mine[:1]
