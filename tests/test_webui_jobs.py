"""
test_webui_jobs.py
====================
The job model (stage-3 prompt 01, block 9): a `jobs` table written through
`init_db()`; a chain run is a persisted job; a generic job of another kind
runs a function with progress and cooperative cancel; SSE replay is the
full event history; a job the server no longer holds is rebuilt from its
row (restart-safe snapshot). No FastAPI needed — `server.jobs` is threads
and sqlite over the core — so the conda pytest runs it.

Runnable standalone:  python tests/test_webui_jobs.py
"""

import os
import shutil
import sys
import tempfile
import threading
import time

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.recipes import make_recipe  # noqa: E402
from server.jobs import KINDS, JobManager  # noqa: E402


@pytest.fixture
def env():
    tmp = tempfile.mkdtemp(prefix="jobs_")
    import Working.config as cfg
    old = cfg.STEP_CACHE_ROOT
    cfg.STEP_CACHE_ROOT = os.path.join(tmp, "cache")
    x = np.cumsum(np.random.default_rng(0).standard_normal(600))
    npy = os.path.join(tmp, "CH0.npy"); np.save(npy, x)
    db = os.path.join(tmp, "t.sqlite")
    conn = init_db(db)
    q.insert_recording(conn, "synthetic.mat", 0, 1.0, len(x), 0, npy)
    rec = dict(conn.execute("SELECT * FROM recordings").fetchone())
    conn.close()
    try:
        yield db, rec, tmp
    finally:
        cfg.STEP_CACHE_ROOT = old
        shutil.rmtree(tmp, ignore_errors=True)


def _wait(job, timeout=60):
    """Until the terminal event has been published (the row is written just before it)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if job.events and job.events[-1]["event"] in ("job_end", "run_end"):
            return job.status
        time.sleep(0.05)
    return job.status


def test_jobs_table_exists_with_the_persisted_columns(env):
    db, _, _ = env
    conn = init_db(db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(jobs)")}
    conn.close()
    assert {"id", "kind", "status", "created_at", "started_at", "finished_at", "cancelled", "meta_json", "progress_json", "error_json", "run_id"} <= cols


def test_kinds_are_the_five_the_prompts_share():
    assert set(KINDS) == {"chain_run", "sweep", "import", "regroup", "training"}


def test_a_chain_run_is_a_persisted_job_with_a_restart_safe_snapshot(env):
    db, rec, tmp = env
    m = JobManager(db, meta_dir=os.path.join(tmp, "meta"))
    recipe = make_recipe(rec["id"], [{"stage": "preprocessing", "algorithm": "detrend", "params": {"mode": "linear"}}])
    job = m.start(recipe, rec, px=200)
    assert _wait(job) == "completed"
    snap = m.snapshot(job.id)
    assert snap["status"] == "completed" and snap["db_run_id"]
    # a fresh manager (server restart) rebuilds the job from its row + the runs row
    m2 = JobManager(db)
    restored = m2.snapshot(job.id)
    assert restored["restored"] is True and restored["kind"] == "chain_run"
    assert restored["status"] == "completed" and restored["db_run_id"] == snap["db_run_id"]
    assert restored["recipe"]["steps"][0]["algorithm"] == "detrend"
    assert restored["run_row"]["status"] == "completed"
    assert any(j["job_id"] == job.id for j in m2.list_jobs())


def test_a_job_lost_in_a_restart_is_reported_failed_not_running(env):
    db, rec, _ = env
    conn = init_db(db)
    conn.execute("INSERT INTO jobs (id, kind, status, created_at, started_at, meta_json, progress_json) VALUES (77, 'import', 'running', 'x', 'x', '{}', '{}')")
    conn.commit(); conn.close()
    snap = JobManager(db).snapshot(77)
    assert snap["status"] == "failed" and snap["error"]["type"] == "ServerRestart"


def test_a_generic_job_reports_progress_and_can_be_cancelled(env):
    db, _, _ = env
    m = JobManager(db)
    seen = []

    def work(job):
        for i in range(50):
            if job.cancel_event.is_set():
                return None
            job.progress(i + 1, 50, f"step {i + 1}")
            seen.append(i)
            time.sleep(0.02)
        return {"done": True}

    job = m.start_job("import", work, meta={"what": "seed events"})
    time.sleep(0.15)
    assert m.cancel(job) is True
    assert _wait(job) == "cancelled"
    assert 0 < len(seen) < 50
    kinds = [e["event"] for e in job.events]
    assert kinds[0] == "job_start" and "progress" in kinds and "cancel_requested" in kinds and kinds[-1] == "job_end"
    row = m.snapshot(job.id)
    assert row["status"] == "cancelled" and row["cancelled"] is True
    conn = init_db(db)
    assert conn.execute("SELECT status, cancelled FROM jobs WHERE id = ?", (job.id,)).fetchone()[:2] == ("cancelled", 1)
    conn.close()


def test_a_generic_job_that_raises_is_failed_with_the_traceback(env):
    db, _, _ = env
    m = JobManager(db)
    job = m.start_job("regroup", lambda j: 1 / 0, meta={})
    assert _wait(job) == "failed"
    assert "ZeroDivisionError" in job.error["message"] and "Traceback" in job.error["traceback"]
    with pytest.raises(ValueError):
        m.start_job("bogus", lambda j: None)


def test_sse_replay_is_the_full_history_for_a_late_subscriber(env):
    db, _, _ = env
    m = JobManager(db)
    job = m.start_job("sweep", lambda j: [j.progress(i, 3) for i in range(3)] and {"ok": 1}, meta={})
    assert _wait(job) == "completed"
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        m.attach_loop(loop)
        q_ = m.subscribe(job)
        replay = []
        while not q_.empty():
            replay.append(q_.get_nowait()["event"])
    finally:
        m.unsubscribe(job, q_)
        loop.close()
    assert replay == [e["event"] for e in job.events]
    assert replay[0] == "job_start" and replay[-1] == "job_end" and replay.count("progress") == 3


def test_ids_continue_after_the_persisted_rows(env):
    db, _, _ = env
    conn = init_db(db)
    conn.execute("INSERT INTO jobs (id, kind, status, created_at, started_at, meta_json, progress_json) VALUES (500, 'import', 'completed', 'x', 'x', '{}', '{}')")
    conn.commit(); conn.close()
    m = JobManager(db)
    job = m.start_job("import", lambda j: None, meta={})
    _wait(job)
    assert job.id > 500


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
