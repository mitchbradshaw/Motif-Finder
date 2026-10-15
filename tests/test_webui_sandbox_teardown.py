"""
test_webui_sandbox_teardown.py
==============================
A test's sandbox must not leak through its own teardown.

Every route-test fixture does the same three things: `Runtime.setup()` points
the core's write paths (the step cache, the adapters' `RESULTS_DIR`s, the
classifier's `MODEL_ROOT`, ...) into `tmp_path`, a `TestClient` serves the app,
and `rt.restore()` puts the paths back. The core reads those paths **at the
moment it writes**, and a job is a daemon thread nothing waited for. So a job
a test started and did not wait for is still running after `restore()`, and
its next write goes to the core's defaults: the checkout's `DATA/derived/` and
`Results/`. In the main checkout that is the real tree.

Found 2026-10-16: `tests/test_webui_discovery.py` alone left
`DATA/derived/step_cache/<hash>/1/scores.npz` and
`Results/Detection/matrix_profile/mp_v2_syn_CH0_WIN1min.npz` behind, written
one second apart by a Discovery sweep (`mp_threshold` on CH1) that
`test_a_plan_over_a_held_out_channel_refuses_before_any_run_row_is_written`
starts and never waits for.

Neither test here can write into the real tree, even while red: before the
runtime is set up, every core path a sandbox redirects is pointed at a
stand-in checkout under `tmp_path`, so `restore()` puts the paths back THERE,
and whatever escaped the sandbox lands where the test can count it.

FastAPI lives only in `webui/.venv`, so this file skips under the conda
pytest; run it with:

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_sandbox_teardown.py
"""

import importlib
import os
import sys
import threading
import time

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from fastapi.testclient import TestClient  # noqa: E402

from Working.database.schema import init_db  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402

FS = 1.0
N = 6000
M = 60

#: Every module path a sandbox redirects, as (module, attribute): what the core
#: and the adapters read at the moment they write.
CORE_PATHS = (("Working.config", "STEP_CACHE_ROOT"),
              ("Adapters.detection_matrix_profile", "RESULTS_DIR"),
              ("Adapters.preprocessing_window_matrix", "RESULTS_DIR"),
              ("Adapters.catalogue_classifier", "MODEL_ROOT"),
              ("Adapters.catalogue_cluster", "RESULTS_DIR"),
              ("Adapters.preprocessing_window_pool", "POOL_ROOT"),
              ("Adapters.preprocessing_trace_shape", "RESULTS_DIR"),
              ("Adapters.catalogue_shape_cluster", "RESULTS_DIR"),
              ("Working.Detection.matrix_profiling.cost", "CALIBRATION_PATH"),
              ("Working.block_cost", "CALIBRATION_PATH"))


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    """A stand-in for the checkout's `DATA/` and `Results/`: every core path a
    sandbox redirects points in here before the runtime is set up."""
    root = tmp_path / "checkout"
    for module, attr in CORE_PATHS:
        monkeypatch.setattr(importlib.import_module(module), attr,
                            str(root / module.rsplit(".", 1)[-1] / attr.lower()))
    return root


def _escaped(root):
    """Every file written into the stand-in checkout."""
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def _inside(path, root):
    return os.path.normcase(os.path.abspath(path)).startswith(os.path.normcase(os.path.abspath(root)) + os.sep)


def _planted(seed):
    """Noise with one dip planted three times: something for the matrix profile to find."""
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(N) * 0.02
    for at in (600, 1800, 3400):
        x[at:at + M] -= np.sin(np.linspace(0.0, np.pi, M))
    return x


def _runtime(tmp_path, stamp):
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    conn = init_db(str(db_dir / "annotations.sqlite"))
    for ch in range(2):
        npy = tmp_path / f"CH{ch}.npy"
        np.save(npy, _planted(ch))
        conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                     "VALUES ('syn.mat', ?, ?, ?, 0, ?)", (ch, FS, N, str(npy)))
    conn.commit()
    conn.close()
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    return Runtime(mode="sandbox", stamp=stamp, db_source=str(db_dir / "annotations.sqlite"),
                   runtime_root=str(tmp_path / "runtime"), client_dist=str(dist))


def _wait_until_finished(job, timeout=300):
    t0 = time.time()
    while job.status not in ("completed", "failed", "cancelled"):
        if time.time() - t0 > timeout:
            raise AssertionError(f"job {job.id} did not finish in {timeout} s")
        time.sleep(0.05)


def test_a_job_left_running_is_stopped_before_restore_puts_the_paths_back(tmp_path, checkout):
    """The leak reduced to its shape, deterministically: a job the test never
    waited for is still running when the fixture tears the sandbox down, and
    its next write reads the core's step-cache root at that moment."""
    import Working.config as cfg

    rt = _runtime(tmp_path, "20261016-teardown-probe")
    rt.setup()
    release = threading.Event()
    wrote = []

    def sweep(job):
        # a sweep between two channels: the next one writes its step-cache entry when it gets to it
        while not (job.cancel_event.is_set() or release.is_set()):
            time.sleep(0.01)
        out = os.path.join(cfg.STEP_CACHE_ROOT, "probe", "1", "scores.npz")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        np.savez(out, scores=np.zeros(3))
        wrote.append(out)
        return {"wrote": out}

    try:
        with TestClient(create_app(rt)) as c:
            job = c.app.state.manager.start_job("sweep", sweep, meta={"what": "a sweep the test never waits for"})
    finally:
        rt.restore()
    release.set()       # whatever is still running from here on writes after the paths went back
    _wait_until_finished(job)

    assert _escaped(checkout) == [], f"a job outlived restore() and wrote into the checkout: {wrote}"
    assert wrote and _inside(wrote[0], rt.dir), f"the job's write stayed inside its sandbox {rt.dir}: {wrote}"


def test_a_discovery_sweep_nobody_waited_for_writes_nothing_into_the_checkout(tmp_path, checkout):
    """The leak as found, through the real route: a template applied over a
    channel and never waited for (the shape of `test_webui_discovery.py`'s
    held-out test). Its matrix profiles and step-cache entries belong in the
    sandbox; nothing may land in the checkout after `restore()`."""
    rt = _runtime(tmp_path, "20261016-teardown-sweep")
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            r = c.put("/api/discovery/session", json={
                "name": "test", "recording": "syn", "channels": ["CH1"], "section": [0.0, N / FS / 3600.0],
                "null": {"method": "phase randomisation", "n": 2}})
            assert r.status_code == 200, r.text
            r = c.post("/api/discovery/templates/apply", json={
                "templates": ["mp_threshold"], "channels": ["CH1"], "t0": 0.0, "t1": N / FS / 3600.0})
            assert r.status_code == 200, r.text
            job_id = r.json()[0]["job_id"]
            assert job_id, r.json()
            job = c.app.state.manager.jobs[job_id]
    finally:
        rt.restore()
    _wait_until_finished(job)

    assert _escaped(checkout) == [], "the sweep wrote into the checkout after restore()"
