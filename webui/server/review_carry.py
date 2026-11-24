"""
review_carry.py
===============
Review's carries, off the step (2026-11-24, the researcher: "it is related to 'carried to X other detections' ... any
chance this process can run in the background instead of between candidates?").

A verdict is written at once (its row and its audit entry, committed) and answered; copying it to the same event
found by other runs on the channel - the carry - waits on its audit entry (`carry_pending`) for this worker, one
thread that runs the pending carries in audit order (`verdicts.run_pending_carry`, which carries each verdict as it
was given). Order is the whole of the correctness: carries run in the order their verdicts were given end exactly as
carries done at once would, through re-judgements.

* `submit(audit_id)` queues one; it never waits for a carry.
* `drain()` runs everything queued, then holds the worker off while the caller works: the routes that reverse or
  carry at once (undo, a promotion and its reversal, an extraction) call it first, so they act on a history whose
  carries are all done - an undo then takes back exactly what its verdict carried.
* `start()` also queues what a stopped bridge left pending (the audit rows still flagged), so none is lost.
* A carry that fails is logged with its traceback and stays pending on its audit row, retried at the next start.
"""
from __future__ import annotations

import collections
import contextlib
import logging
import threading
import time

from . import corpus

log = logging.getLogger("webui.review_carry")


class CarryWorker:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._queued: collections.deque[int] = collections.deque()
        self._qlock = threading.Lock()          # the queue only: held for an append or a pop, never across a carry
        self._run = threading.RLock()           # one carry at a time; drain() holds it while its caller works
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.failed: dict[int, str] = {}        # audit id -> the error, for the status read
        self.done = 0

    # ── lifecycle ──────────────────────────────────────────────────────────
    def start(self) -> None:
        from Working.review import verdicts as V
        conn = corpus.connect(self.db_path)
        try:
            left = V.pending_carries(conn)
        finally:
            conn.close()
        if left:
            log.info("review carry: %d verdict(s) a stopped bridge had not carried, queued again", len(left))
        with self._qlock:
            self._queued.extend(left)
        self._thread = threading.Thread(target=self._loop, daemon=True, name="review-carry")
        self._thread.start()
        self._wake.set()

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout)

    # ── the queue ──────────────────────────────────────────────────────────
    def submit(self, audit_id: int) -> None:
        with self._qlock:
            self._queued.append(int(audit_id))
        self._wake.set()

    def queued(self) -> int:
        with self._qlock:
            return len(self._queued)

    def _pop(self) -> int | None:
        with self._qlock:
            return self._queued.popleft() if self._queued else None

    def _carry(self, audit_id: int) -> None:
        from Working.review import verdicts as V
        conn = corpus.connect(self.db_path)
        try:
            V.run_pending_carry(conn, audit_id)
            self.failed.pop(audit_id, None)
            self.done += 1
        except Exception as exc:  # noqa: BLE001 - logged loud and kept pending, never swallowed into a blank
            self.failed[audit_id] = f"{type(exc).__name__}: {exc}"
            log.exception("review carry: carrying the verdict of audit row %s failed; it stays pending and is "
                          "retried at the next start", audit_id)
        finally:
            conn.close()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._wake.wait(0.5)
            self._wake.clear()
            while not self._stop.is_set():
                # the pop happens under the run lock, so drain() can never run a later carry before this one
                with self._run:
                    audit_id = self._pop()
                    if audit_id is None:
                        break
                    self._carry(audit_id)

    @contextlib.contextmanager
    def drain(self):
        """Run every queued carry now, then keep the worker off until the block ends."""
        with self._run:
            while (audit_id := self._pop()) is not None:
                self._carry(audit_id)
            yield

    def flush(self, timeout: float = 30.0) -> bool:
        """Wait until nothing is queued and no carry is running (tests). True when it emptied in time."""
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            if self.queued() == 0 and self._run.acquire(timeout=0.05):
                try:
                    if self.queued() == 0:
                        return True
                finally:
                    self._run.release()
            time.sleep(0.02)
        return False
