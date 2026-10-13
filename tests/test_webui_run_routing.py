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
