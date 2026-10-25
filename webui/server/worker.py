"""tq-worker (2026-10-25): the bridge's worker processes, in one place.

Two kinds, both spawned children that import `Working` only (never this package) and watch the bridge
(`coverage_map.watch_parent`), so they end with it however it went:

* **the shared worker** (`run_in_worker`): ONE process, started lazily, that the corpus maps and Discovery › Map's
  overview both compute in, one job at a time — one pool, one timeout and one stop for both. When no process can be
  started (or `MODE` is "thread": tests, a sandbox that forbids processes) the caller's fallback runs on its thread.
* **a process of its own for one task** (`run_alone`): a block cost-model timing (`chain`), which must never queue
  behind a minutes-long map, stopped after its timeout.

Every one of them is stopped at interpreter exit, before `concurrent.futures` would join (and so wait out) a job in
flight. `OneFlight` (one flight per key) lives here too: the corpus maps' miss lock and the Discovery scoreboard's.

Moved out of `corpus.py` (where it grew as the corpus maps' pool) and `chain.py` (which kept a second copy of the same
lifecycle reaching into corpus's privates)."""
from __future__ import annotations

import contextlib
import logging
import multiprocessing as mp
import sys
import threading
import types
from concurrent.futures import CancelledError, ProcessPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from concurrent.futures.process import BrokenProcessPool

from Working.discovery import coverage_map as _CM

#: "process" (the default) or "thread" (no shared worker process; tests, and a sandbox that forbids processes)
MODE = "process"
#: how long the first start of the shared worker may take (a spawned interpreter importing numpy and the core)
POOL_START_TIMEOUT_S = 180.0
#: how long one job may take in the shared worker before it is given up as hung (the pool is replaced and the
#: failure raised) — a real corpus-map recompute is 100–260 s on the post-RQ4 database. The corpus maps' start-up warm
#: waits half of it (`corpus.WARM_WAIT_S` is derived from this)
RESULT_TIMEOUT_S = 3600.0

_POOL = {"pool": None, "pid": None, "failed": None, "gen": 0}
_POOL_LOCK = threading.Lock()
#: the `run_alone` processes in flight, stopped at interpreter exit
_ALONE: set = set()
#: called by `shutdown()` (Discovery › Map's overview closes its change-counter connection there, so the runtime's
#: `restore()` releases the sandbox copy; the corpus maps drop their queue)
_ON_STOP: list = []
#: one `__main__` swap at a time (two at once would restore each other's stand-in)
_MAIN_LOCK = threading.Lock()

_log = logging.getLogger("webui.worker")


class Stopped(Exception):
    """The shared worker was stopped on purpose (`shutdown`) while a job was queued or computing: nothing is kept and
    nothing is recorded as a failure; the next read schedules it again."""


@contextlib.contextmanager
def _main_hidden():
    """`sys.modules['__main__']` swapped for an empty module while a pool spawns its child, so the child does not
    re-run the parent's main script (`webui/run_server.py`, which imports the bridge; `multiprocessing.spawn` imports
    it by path or name). Held only for the `submit` that starts the process."""
    with _MAIN_LOCK:
        main = sys.modules.get("__main__")
        sys.modules["__main__"] = types.ModuleType("__main__")
        try:
            yield
        finally:
            if main is not None:
                sys.modules["__main__"] = main


def _spawn():
    return ProcessPoolExecutor(max_workers=1, mp_context=mp.get_context("spawn"), initializer=_CM.watch_parent)


def terminate(pool):
    """Stop `pool` now: queued work cancelled, its process terminated rather than joined (a job in flight is
    abandoned)."""
    procs = list((getattr(pool, "_processes", None) or {}).values())
    try:
        pool.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass
    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass
    for p in procs:
        try:
            p.join(5)
        except Exception:
            pass


def pool():
    """The shared worker process (started on first use), or None when `MODE` is "thread" or the process could not be
    started (then callers run their fallback on a thread)."""
    if MODE != "process":
        return None
    with _POOL_LOCK:
        if _POOL["pool"] is not None:
            return _POOL["pool"]
        if _POOL["failed"]:
            return None
        new = None
        try:
            new = _spawn()
            with _main_hidden():
                started = new.submit(_CM.ping)
            pid = started.result(timeout=POOL_START_TIMEOUT_S)
        except Exception as exc:
            _POOL["failed"] = f"{type(exc).__name__}: {exc}"
            _log.warning("worker: the worker process could not start (%s); recomputing on a background thread that "
                         "yields to the pages between channels", _POOL["failed"])
            if new is not None:
                terminate(new)
            return None
        _POOL.update(pool=new, pid=pid)
        _log.info("worker: the corpus maps and the map overview recompute in a worker process (pid %d), off the "
                  "request path", pid)
        return new


def status() -> dict:
    """The shared worker's pid (None when not running) and why it could not start (None when it could)."""
    return {"pid": _POOL["pid"], "failed": _POOL["failed"]}


def on_stop(fn):
    """Register `fn()` to run whenever the shared worker is stopped (`shutdown`). Idempotent."""
    if fn not in _ON_STOP:
        _ON_STOP.append(fn)


def shutdown():
    """Stop the shared worker at once (the runtime's `restore()`, interpreter exit, tests): queued jobs are dropped,
    a job in flight is abandoned, not waited for, and every `on_stop` hook runs. A later use starts a fresh worker."""
    with _POOL_LOCK:
        stopped = _POOL["pool"]
        _POOL.update(pool=None, pid=None, failed=None, gen=_POOL["gen"] + 1)
    # the hooks run before the terminate, so a caller's queue is dropped before its job in flight is abandoned (a
    # drain thread must not start a fresh worker for the next queued job)
    for fn in list(_ON_STOP):
        try:
            fn()
        except Exception:
            _log.exception("a worker-stop hook failed")
    if stopped is not None:
        terminate(stopped)


def run_in_worker(fn, *args, fallback, what: str, **kw):
    """``(mode, fn(*args, **kw))`` computed in the shared worker process, or ``("thread", fallback())`` on the calling
    thread when there is no pool or it broke. `fn` must be a top-level core function (the child imports `Working`
    only). Raises `Stopped` when the worker was stopped on purpose meanwhile (nothing is kept, nothing is a failure),
    and a RuntimeError when the worker hung past `RESULT_TIMEOUT_S`."""
    gen = _POOL["gen"]
    shared = pool()
    if shared is not None:
        try:
            fut = shared.submit(fn, *args, **kw)
        except RuntimeError as exc:          # shut down between `pool()` and here
            raise Stopped(str(exc)) from exc
        try:
            return "process", fut.result(timeout=RESULT_TIMEOUT_S)
        except FutureTimeout:
            _log.warning("worker: %s did not finish in %.0f s; the worker is replaced", what, RESULT_TIMEOUT_S)
            shutdown()
            raise RuntimeError(f"the worker process did not finish within {RESULT_TIMEOUT_S:.0f} s and was stopped")
        except CancelledError as exc:        # queued behind another job when the pool was shut down
            raise Stopped("the worker was stopped") from exc
        except BrokenProcessPool as exc:
            if _POOL["gen"] != gen:
                raise Stopped("the worker was stopped") from exc
            _log.warning("worker: the worker process died (%s); %s is recomputed on a background thread and the next "
                         "job starts a fresh worker", exc, what)
            shutdown()
    return "thread", fallback()


def run_alone(fn, *args, timeout: float):
    """``fn(*args)`` in a spawned process of its own, started for this call and ended after it. Raises TimeoutError
    when it has not answered within `timeout` s (the process is terminated). Blocks the calling thread throughout."""
    alone = _spawn()
    _ALONE.add(alone)
    try:
        with _main_hidden():
            fut = alone.submit(fn, *args)
        try:
            return fut.result(timeout=timeout)
        except FutureTimeout:
            terminate(alone)
            raise TimeoutError(f"no answer within {timeout:.0f} s") from None
    finally:
        _ALONE.discard(alone)
        alone.shutdown(wait=False)


def _stop_everything():
    """Interpreter exit: the shared worker and every `run_alone` process, stopped rather than joined."""
    for alone in list(_ALONE):
        _ALONE.discard(alone)
        terminate(alone)
    shutdown()


# `concurrent.futures.process` (imported above) registered its own exit hook, which joins every worker — waiting out
# a job in flight (a map: 100–260 s; a timing: up to 15 min). Hooks run last-registered first, so this one, registered
# after it, stops them before that join.
if hasattr(threading, "_register_atexit"):
    threading._register_atexit(_stop_everything)
else:   # pragma: no cover - every CPython this runs on has it
    import atexit
    atexit.register(_stop_everything)


class OneFlight:
    """One flight per key: ``with flight(key):`` waits while another thread holds the same key, and keys never wait on
    each other. The registry holds only the keys in use (a count of holders and waiters), so it never grows."""

    def __init__(self):
        self._guard = threading.Lock()
        self._locks: dict = {}

    @contextlib.contextmanager
    def __call__(self, key):
        with self._guard:
            entry = self._locks.setdefault(key, [threading.Lock(), 0])
            entry[1] += 1
        try:
            with entry[0]:
                yield
        finally:
            with self._guard:
                entry[1] -= 1
                if entry[1] == 0:
                    self._locks.pop(key, None)
