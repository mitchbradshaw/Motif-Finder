"""
test_webui_worker.py
====================
tq-worker (2026-10-25): the bridge's worker processes live in one module, `webui/server/worker.py`, instead of
inside the corpus-coverage module with a second hand-copied lifecycle in `chain.py`:

* `run_in_worker` — the ONE shared worker process (the corpus maps and Discovery › Map's overview), or the caller's
  fallback on its own thread (`MODE = "thread"`, or no process could start); `Stopped` when it was stopped on purpose;
* `shutdown()` and the `on_stop` hooks;
* `run_alone` — a throwaway process for one task (a block cost-model timing), stopped after its timeout;
* `OneFlight` — one flight per key, the registry holding only the keys in use (the corpus maps' miss lock and the
  Discovery scoreboard's).

It imports no web library, so it runs under either interpreter.

    python -m pytest tests/test_webui_worker.py
"""
import os
import re
import sys
import threading
import time

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBUI_DIR = os.path.join(PROJECT_ROOT, "webui")
SERVER = os.path.join(WEBUI_DIR, "server")
for p in (PROJECT_ROOT, WEBUI_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from server import worker  # noqa: E402
from Working.discovery import coverage_map as CM  # noqa: E402


def _src(name):
    return open(os.path.join(SERVER, name), encoding="utf-8").read()


def test_thread_mode_runs_the_fallback_on_the_calling_thread(monkeypatch):
    monkeypatch.setattr(worker, "MODE", "thread")
    assert worker.run_in_worker(CM.ping, fallback=lambda: "here", what="a test") == ("thread", "here")


def test_process_mode_runs_every_job_in_one_shared_child():
    worker.shutdown()
    try:
        mode, pid = worker.run_in_worker(CM.ping, fallback=lambda: None, what="a test")
        assert mode == "process" and pid != os.getpid()
        assert worker.status()["pid"] == pid
        assert worker.run_in_worker(CM.ping, fallback=lambda: None, what="a test") == ("process", pid)
    finally:
        worker.shutdown()


def test_jobs_in_flight_or_queued_when_the_worker_is_stopped_raise_stopped():
    worker.shutdown()
    got = {}

    def job(tag, fn, *args):
        try:
            got[tag] = worker.run_in_worker(fn, *args, fallback=lambda: "fallback", what=tag)
        except worker.Stopped as exc:
            got[tag] = exc
    assert worker.pool() is not None
    busy = threading.Thread(target=job, args=("busy", time.sleep, 600))
    busy.start()
    time.sleep(0.5)
    queued = threading.Thread(target=job, args=("queued", CM.ping))
    queued.start()
    time.sleep(0.5)
    t0 = time.time()
    worker.shutdown()
    busy.join(30)
    queued.join(30)
    assert time.time() - t0 < 30
    assert isinstance(got["busy"], worker.Stopped), got
    assert isinstance(got["queued"], worker.Stopped), got


def test_an_on_stop_hook_runs_once_per_shutdown_however_often_it_was_registered():
    calls = []

    def hook():
        calls.append(1)
    worker.on_stop(hook)
    worker.on_stop(hook)
    try:
        worker.shutdown()
        assert calls == [1]
    finally:
        worker._ON_STOP.remove(hook)


def test_run_alone_answers_from_a_process_of_its_own_and_stops_one_that_hangs():
    pid = worker.run_alone(CM.ping, timeout=180)
    assert pid != os.getpid() and pid != worker.status()["pid"]
    t0 = time.time()
    with pytest.raises(TimeoutError):
        worker.run_alone(time.sleep, 120, timeout=3)
    assert time.time() - t0 < 30
    assert not worker._ALONE, "the hung process is stopped, not left running"


def test_one_flight_serialises_one_key_runs_others_side_by_side_and_forgets_idle_keys():
    flight = worker.OneFlight()

    def hold(key):
        with flight(key):
            time.sleep(0.4)

    def timed(keys):
        threads = [threading.Thread(target=hold, args=(k,)) for k in keys]
        t0 = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return time.time() - t0
    assert timed(["a", "a"]) >= 0.75, "two flights of one key ran at once"
    assert timed(["a", "b"]) < 0.75, "different keys waited on each other"
    assert flight._locks == {}, "an idle key is still held in the registry"


def test_the_duplicates_are_gone():
    corpus = _src("corpus.py")
    for gone in ("def run_in_worker", "class _MainHidden", "def _terminate", "def coverage_pool", "_COVERAGE_LOCKS",
                 "def on_worker_stop"):
        assert gone not in corpus, f"corpus.py still has {gone}"
    chain = _src("chain.py")
    for gone in ("_REAL_CALIBRATE", "_child_call", "CALIBRATION_WORKER", "_BC_ATEXIT", "_BC_POOLS"):
        assert gone not in chain, f"chain.py still has {gone}"
    assert not re.search(r"\b(block_cost|corpus)\._", chain), "chain.py reaches into a private of the core or corpus"
    child = _src("calibrate_child.py")
    for gone in ("tempfile", "_key", "hold_s", "WARM_UPS"):
        assert gone not in child, f"calibrate_child.py still has {gone}"
    assert "_SB_LOCKS" not in _src("discovery.py")
    dmap = _src("discovery_map.py")
    for gone in ("corpus._Stopped", "corpus.run_in_worker", "corpus.on_worker_stop"):
        assert gone not in dmap, f"discovery_map.py still has {gone}"
