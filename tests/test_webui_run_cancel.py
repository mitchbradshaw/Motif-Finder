"""
test_webui_run_cancel.py
========================
W3-F item 1: a long step can be stopped, and followed, from inside.

On 2026-10-14 a FLUSS run over a whole recording had to be ended by killing the bridge: the run manager checked
*cancel* between steps only, and `webui/server/runs.py` passed no `run_kwargs`, so a block that declares
`should_cancel` / `on_progress` on its `_run` (window matrix, multiscale entropy, the pan matrix profile) never
received them. What these tests pin, on a fake slow block that declares both:

* a cancel stops the step within one iteration; the job reads *cancelled*, not failed; the step is marked
  cancelled; no step-cache entry is written for it (a control run of the same block, uncancelled, writes one —
  so the absence is the cancel's doing);
* `on_progress(done, total, stage)` from inside the step reaches the job's status (`steps[i]["progress"]`) and
  the event stream (`step_progress`);
* the paired null's draws receive the same callbacks: a cancel during a draw stops that draw within one iteration,
  and the null says it was cut short;
* window matrix's own cancellation is the one exception the executor treats as a cancel
  (`Working.execution.RecipeCancelled`), not a failure;
* `_emit` after the event loop has closed does not raise ("event loop closed", a wave-2 follow-up).

The run manager imports no FastAPI, so this file runs under the conda pytest.
"""
import asyncio
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

from Adapters import registry  # noqa: E402
from Adapters.base import AdapterResult, AdapterSpec, ParamSpec  # noqa: E402
from Working.execution import RecipeCancelled  # noqa: E402
from Working.types import Scores  # noqa: E402

FAKE = "detection.w3f_fake_slow"
N_ITER = 60
TICK_S = 0.03


class _Probe:
    """What the fake block saw: one list of iteration indices per call, and the iteration a cancel was observed at."""

    def __init__(self):
        self.calls: list[list[int]] = []
        self.lock = threading.Lock()

    def begin(self):
        with self.lock:
            self.calls.append([])
            return len(self.calls) - 1

    def tick(self, call, i):
        with self.lock:
            self.calls[call].append(i)


PROBE = _Probe()


def _fake_run(x, t, fs, n_iter=N_ITER, should_cancel=None, on_progress=None):
    call = PROBE.begin()
    for i in range(int(n_iter)):
        if should_cancel is not None and should_cancel():
            raise RecipeCancelled(f"{FAKE}: cancelled at iteration {i}")
        PROBE.tick(call, i)
        time.sleep(TICK_S)
        if on_progress is not None:
            on_progress(i + 1, int(n_iter), "fake")
    return AdapterResult(output_kind="scores", value=Scores(values=np.asarray(x, dtype=float), fs=fs), meta={})


@pytest.fixture
def fake_block(monkeypatch):
    spec = AdapterSpec(name=FAKE, display_name="Fake slow", stage="detection",
                       params=[ParamSpec("n_iter", int, N_ITER, "iterations", min=1, max=10_000)],
                       run=_fake_run, output_kind="scores", input_kind="signal", category="detect",
                       description="a test block that declares should_cancel and on_progress")
    monkeypatch.setitem(registry._REGISTRY, FAKE, spec)
    PROBE.calls.clear()
    return spec


@pytest.fixture
def bridge_db(tmp_path, monkeypatch):
    """A database with one 2,000-sample recording, and a step cache in tmp that caches every step (threshold 0),
    so an uncancelled step DOES leave an entry."""
    import Working.config as cfg
    from Working.database.schema import init_db
    monkeypatch.setattr(cfg, "STEP_CACHE_ROOT", str(tmp_path / "step_cache"))
    monkeypatch.setattr(cfg, "STEP_CACHE_WRITE_THRESHOLD_S", 0.0)
    npy = tmp_path / "ch.npy"
    np.save(npy, np.random.default_rng(0).standard_normal(2000).cumsum().astype(np.float32))
    db = str(tmp_path / "a.sqlite")
    conn = init_db(db)
    conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                 "VALUES ('fake.mat', 0, 1.0, 2000, 0, ?)", (str(npy),))
    conn.commit()
    rid = conn.execute("SELECT id FROM recordings").fetchone()[0]
    rec = dict(conn.execute("SELECT * FROM recordings WHERE id = ?", (rid,)).fetchone())
    conn.close()
    return db, rec


def _recipe(rid, n_iter=N_ITER):
    from server import chain as chain_mod
    return chain_mod.build_recipe(rid, (0, 2000), [{"stage": "detection", "algorithm": "w3f_fake_slow",
                                                    "params": {"n_iter": n_iter}}])


def _wait(pred, timeout=20.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(0.01)
    return False


def _manager(db):
    from server.runs import RunManager
    return RunManager(db)


def _cached(recipe, db, index=0):
    from server import chain as chain_mod
    from Working.database.schema import init_db
    conn = init_db(db)
    try:
        return chain_mod.cache_status(recipe, conn)[index]["cached"]
    finally:
        conn.close()


def test_an_uncancelled_fake_step_is_cached_the_control(fake_block, bridge_db):
    db, rec = bridge_db
    recipe = _recipe(rec["id"], n_iter=3)
    job = _manager(db).start(recipe, rec)
    assert _wait(lambda: job.status != "running")
    assert job.status == "completed", job.error
    assert _cached(recipe, db), "the control: an uncancelled step of this block writes a step-cache entry"


def test_a_cancel_stops_the_step_within_one_iteration_and_the_job_reads_cancelled(fake_block, bridge_db):
    db, rec = bridge_db
    recipe = _recipe(rec["id"])
    mgr = _manager(db)
    job = mgr.start(recipe, rec)
    assert _wait(lambda: PROBE.calls and len(PROBE.calls[0]) >= 3), "the fake never started"
    assert mgr.cancel(job)
    at_cancel = len(PROBE.calls[0])
    assert _wait(lambda: job.status != "running"), "the job never ended"
    assert job.status == "cancelled", f"{job.status}: {job.error}"
    assert len(PROBE.calls[0]) - at_cancel <= 1, (
        f"the step ran {len(PROBE.calls[0]) - at_cancel} more iterations after the cancel: should_cancel never "
        "reached the block (the bridge passes no run_kwargs)")
    assert len(PROBE.calls[0]) < N_ITER
    assert job.steps[0]["status"] == "cancelled"
    assert job.error and job.error["type"] == "RecipeCancelled"
    assert not _cached(recipe, db), "a step cancelled from inside left a step-cache entry"
    ends = [e for e in job.events if e["event"] == "run_end"]
    assert ends and ends[-1]["status"] == "cancelled"


def test_progress_from_inside_a_step_reaches_the_job_and_the_stream(fake_block, bridge_db):
    db, rec = bridge_db
    recipe = _recipe(rec["id"], n_iter=8)
    job = _manager(db).start(recipe, rec)
    seen = []
    _wait(lambda: (seen.append(dict(job.steps[0].get("progress") or {})) or False) or job.status != "running")
    assert job.status == "completed", job.error
    fractions = [s for s in seen if s]
    assert fractions, "steps[0]['progress'] was never set while the step ran"
    assert all(s["total"] == 8 and s["stage"] == "fake" for s in fractions)
    assert job.steps[0]["progress"]["done"] == 8, "the last progress the step reported is kept on the job"
    events = [e for e in job.events if e["event"] == "step_progress"]
    assert events, "no step_progress event reached the stream"
    assert events[-1]["step"] == 0 and events[-1]["done"] == 8 and events[-1]["total"] == 8
    assert all(0 < e["fraction"] <= 1 for e in events)


def test_a_cancel_during_a_null_draw_stops_the_draw_within_one_iteration(fake_block, bridge_db):
    db, rec = bridge_db
    recipe = _recipe(rec["id"], n_iter=40)
    mgr = _manager(db)
    job = mgr.start(recipe, rec, null={"params": {"method": "phase_randomize", "seed": 0}, "draws": 3})
    assert _wait(lambda: len(PROBE.calls) >= 2 and len(PROBE.calls[1]) >= 3, timeout=40), "the first draw never ran"
    assert job.status == "running"
    assert mgr.cancel(job)
    at_cancel = len(PROBE.calls[1])
    assert _wait(lambda: job.status != "running", timeout=40)
    assert len(PROBE.calls[1]) - at_cancel <= 1, "the null draw did not receive should_cancel"
    assert len(PROBE.calls) == 2, "a draw after the cancel started"
    assert job.status == "completed", "the real run finished before the cancel; only its null was cut short"
    assert job.null is not None and job.null.get("cancelled") is True
    assert job.null["null_draws"] == 0


def test_window_matrix_cancelled_from_inside_raises_the_one_cancellation_exception():
    """Settled (W3 decision 1): RecipeCancelled. Window matrix used to hand back a partial table with
    meta['cancelled'] True, which the executor then cached as if whole."""
    import Adapters.preprocessing_window_matrix as wm
    x = np.random.default_rng(1).standard_normal(6 * 600).cumsum()
    t = np.arange(len(x), dtype=float)
    with pytest.raises(RecipeCancelled):
        wm._run(x, t, 1.0, window_min=10.0, catch22=False, fast_entropy=True, slow_entropy=False,
                should_cancel=lambda: True)


def test_emit_after_the_event_loop_closed_does_not_raise(bridge_db):
    from server.runs import Job, RunManager
    db, rec = bridge_db
    mgr = RunManager(db)
    loop = asyncio.new_event_loop()
    mgr.attach_loop(loop)
    loop.close()
    job = Job({"steps": [], "recording_id": rec["id"]}, rec, 1200)
    mgr._emit(job, {"event": "step_done", "step": 0})       # used to raise RuntimeError: Event loop is closed
    assert job.events and job.events[-1]["event"] == "step_done"


# ── W3-F fix round 1 ────────────────────────────────────────────────────────────
# Critic finding 1 (blocker): a null draw cancelled mid-step kept its runs row with surrogate_of_run_id NULL, so
# `not_surrogate()` read it as a real run and the spans its detector step had already written as real detections.
# Critic finding 3: a step cancelled from inside stored its block's own words ("… cancelled after 3 of 55 windows"),
# which History (`error_text.startswith("Cancelled")`) read as a failure.

SPANS = "detection.w3f_fake_spans"
SLOW_SS = "interrogation.w3f_fake_slow_spans"
N_SPANS = 3


def _fake_spans(x, t, fs):
    from Working.types import SpanSet
    return AdapterResult(output_kind="spanset", value=SpanSet(starts=(10, 400, 900), ends=(40, 450, 960)), meta={})


def _fake_slow_spans(x, t, fs, n_iter=N_ITER, value=None, should_cancel=None, on_progress=None):
    call = PROBE.begin()
    for i in range(int(n_iter)):
        if should_cancel is not None and should_cancel():
            raise RecipeCancelled(f"{SLOW_SS}: stopped at iteration {i}")   # a block's own words, not "Cancelled…"
        PROBE.tick(call, i)
        time.sleep(TICK_S)
    return AdapterResult(output_kind="spanset", value=value, meta={})


@pytest.fixture
def fake_detector_chain(monkeypatch):
    a = AdapterSpec(name=SPANS, display_name="Fake spans", stage="detection", params=[], run=_fake_spans,
                    output_kind="spanset", input_kind="signal", category="detect", description="three spans")
    b = AdapterSpec(name=SLOW_SS, display_name="Fake slow spans", stage="interrogation",
                    params=[ParamSpec("n_iter", int, N_ITER, "iterations", min=1, max=10_000)], run=_fake_slow_spans,
                    output_kind="spanset", input_kind="spanset", category="detect", description="slow, cancellable")
    monkeypatch.setitem(registry._REGISTRY, SPANS, a)
    monkeypatch.setitem(registry._REGISTRY, SLOW_SS, b)
    PROBE.calls.clear()


def _detector_recipe(rid, n_iter=N_ITER):
    from server import chain as chain_mod
    return chain_mod.build_recipe(rid, (0, 2000), [
        {"stage": "detection", "algorithm": "w3f_fake_spans", "params": {}},
        {"stage": "interrogation", "algorithm": "w3f_fake_slow_spans", "params": {"n_iter": n_iter}}])


def _real_detections(db):
    from Working.database.queries import not_surrogate
    from Working.database.schema import init_db
    conn = init_db(db)
    try:
        return conn.execute("SELECT COUNT(*) FROM detections d JOIN runs r ON r.id = d.run_id WHERE "
                            + not_surrogate("r")).fetchone()[0]
    finally:
        conn.close()


def test_a_draw_cancelled_mid_step_is_linked_to_its_run_and_leaks_no_detection(fake_detector_chain, bridge_db):
    """The core, directly: draw_paired_null with should_cancel firing inside the draw's slow step."""
    from Working import run_groups
    from Working.database.schema import init_db
    from Working.execution import execute_recipe
    db, rec = bridge_db
    recipe = _detector_recipe(rec["id"], n_iter=3)
    real = execute_recipe(recipe, db_path=db, force=True)
    assert _real_detections(db) == N_SPANS
    PROBE.calls.clear()
    flag = {"stop": False}

    def stop():
        if PROBE.calls and len(PROBE.calls[0]) >= 2:
            flag["stop"] = True
        return flag["stop"]
    out = run_groups.draw_paired_null(recipe, real["run_id"], db_path=db, draws=2, should_cancel=stop,
                                      should_cancel_draws=stop, run_kwargs={"should_cancel": stop})
    assert out["draws"] == 0
    assert _real_detections(db) == N_SPANS, "the cancelled draw's spans were counted as real detections"
    conn = init_db(db)
    try:
        rows = conn.execute("SELECT id, surrogate_of_run_id FROM runs WHERE id != ?", (real["run_id"],)).fetchall()
    finally:
        conn.close()
    assert rows and all(r["surrogate_of_run_id"] == real["run_id"] for r in rows), \
        "the partial draw's run row is not linked to the run it is the null of"


def test_recipe_cancelled_carries_the_run_id_and_the_row_reads_cancelled(fake_block, bridge_db):
    from Working.database.schema import init_db
    from Working.execution import execute_recipe
    db, rec = bridge_db
    with pytest.raises(RecipeCancelled) as err:
        execute_recipe(_recipe(rec["id"]), db_path=db, force=True,
                       run_kwargs={"should_cancel": lambda: bool(PROBE.calls and len(PROBE.calls[0]) >= 2)})
    run_id = getattr(err.value, "run_id", None)
    assert run_id is not None, "RecipeCancelled does not say which run row it stopped"
    conn = init_db(db)
    try:
        text = conn.execute("SELECT error_text FROM runs WHERE id = ?", (run_id,)).fetchone()[0]
    finally:
        conn.close()
    assert text.startswith("Cancelled"), f"History reads this as a failure: {text!r}"
    assert "w3f_fake_slow" in text, "the block's own words are kept after the prefix"


def test_the_run_manager_cancelling_a_draw_leaks_no_detection(fake_detector_chain, bridge_db):
    db, rec = bridge_db
    recipe = _detector_recipe(rec["id"], n_iter=40)
    mgr = _manager(db)
    job = mgr.start(recipe, rec, null={"params": {"method": "phase_randomize", "seed": 0}, "draws": 3})
    assert _wait(lambda: len(PROBE.calls) >= 2 and len(PROBE.calls[1]) >= 3, timeout=40), "the first draw never ran"
    assert mgr.cancel(job)
    assert _wait(lambda: job.status != "running", timeout=40)
    assert job.status == "completed"
    assert _real_detections(db) == N_SPANS
