"""The job model (stage-3 prompt 01, "Long work").

``JobManager`` grows ``RunManager``: every chain run is a job of kind
``chain_run``, and any other long piece of work (``sweep | import | regroup
| training``) is a job too, started with ``start_job(kind, fn, meta)``. A
job is

* **persisted** — one row in the ``jobs`` table (``id, kind, status,
  created_at, started_at, finished_at, cancelled, meta_json, progress_json,
  error_json, run_id``), written when it starts and updated on every step and
  at the end, so a server restart can still answer ``GET /api/jobs/{id}``
  (**restart-safe snapshot**): a job the server no longer holds in memory is
  rebuilt from its row and, for a chain run, the ``runs`` row the core wrote
  (status, current step, error, step timings, detections);
* **streamed** — Server-Sent Events on ``GET /api/jobs/{id}/events``, with
  the full replay for a late subscriber (``subscribe`` is inherited: the same
  queue-per-subscriber mechanism as the run routes);
* **cancellable** — ``POST /api/jobs/{id}/cancel`` sets the job's
  ``threading.Event``; a chain run checks it before each step (cooperative),
  a generic job's ``fn`` reads ``job.cancel_event`` whenever it likes.

The existing ``/api/runs…`` routes keep working unchanged: they call the same
``start`` / ``cancel`` / ``subscribe`` and read the same ``jobs`` dict —
``RunManager``'s in-memory ``Job`` is now also a ``jobs`` row.

API for prompts 02–05
---------------------
    job = manager.start_job("import", fn, meta={"what": ...})   # fn(job) runs in a thread
    job.progress(done, total, message)                          # emits a 'progress' event, persists it
    job.cancel_event.is_set()                                   # cooperative cancel
    manager.snapshot(job_id)                                    # live or rebuilt from the row
    manager.subscribe(job) / manager.unsubscribe(job, q)        # SSE plumbing (async loop)
"""
from __future__ import annotations

import datetime as _dt
import itertools
import json
import logging
import sqlite3
import threading
import time
import traceback

from Working.database.schema import init_db

from .runs import Job, RunManager
from .serialize import _clean

log = logging.getLogger("webui.jobs")

KINDS = ("chain_run", "sweep", "import", "regroup", "training")
TERMINAL = ("completed", "failed", "cancelled")


def _now():
    return _dt.datetime.now().isoformat(timespec="seconds")


class GenericJob:
    """A non-chain job: a function run in a thread with progress and cancel."""

    def __init__(self, kind: str, meta: dict, manager: "JobManager"):
        self.id = next(Job._ids)
        self.kind = kind
        self.meta = dict(meta or {})
        self.status = "queued"
        self.started_at = time.time()
        self.finished_at: float | None = None
        self.error: dict | None = None
        self.result: dict | None = None
        self.progress_state = {"done": 0, "total": None, "message": ""}
        self.events: list[dict] = []
        self.subscribers: list = []
        self.cancel_event = threading.Event()
        self.log_lines: list[str] = []
        self.db_run_id = None
        self._manager = manager

    def progress(self, done, total=None, message=""):
        self.progress_state = {"done": int(done), "total": (int(total) if total is not None else None), "message": str(message)}
        self._manager._emit(self, {"event": "progress", **self.progress_state})
        self._manager._persist(self)

    def snapshot(self) -> dict:
        return {
            "job_id": self.id, "kind": self.kind, "status": self.status, "meta": _clean(self.meta),
            "progress": self.progress_state, "error": self.error, "result": _clean(self.result),
            "started_at": self.started_at, "finished_at": self.finished_at,
            "elapsed_s": (self.finished_at or time.time()) - self.started_at, "cancelled": self.status == "cancelled",
            "db_run_id": self.db_run_id,
        }


class JobManager(RunManager):
    def __init__(self, db_path: str, meta_dir: str | None = None):
        super().__init__(db_path, meta_dir)
        self._db_lock = threading.Lock()
        self._sync_id_counter()

    # ----------------------------------------------------------- table --
    def _conn(self) -> sqlite3.Connection:
        return init_db(self.db_path)

    def _sync_id_counter(self):
        """In-memory ids continue after the highest persisted id, so a restart
        never hands out an id a row already carries."""
        try:
            conn = self._conn()
            try:
                row = conn.execute("SELECT MAX(id) FROM jobs").fetchone()
            finally:
                conn.close()
            top = int(row[0] or 0)
            Job._ids = itertools.count(max(top + 1, next(Job._ids)))
        except Exception:
            log.exception("could not read the jobs table")

    def _persist(self, job):
        snap = job.snapshot()
        kind = getattr(job, "kind", "chain_run")
        meta = snap.get("meta") if kind != "chain_run" else {"recipe": snap.get("recipe"), "recording_id": snap.get("recording_id"), "px": getattr(job, "px", None)}
        progress = snap.get("progress") if kind != "chain_run" else {"current_step": snap.get("current_step"), "n_steps": snap.get("n_steps"),
                                                                     "steps": [{k: v for k, v in s.items() if k != "summary"} | {"summary": s.get("summary")} for s in snap.get("steps", [])],
                                                                     "step_timings": snap.get("step_timings"), "detections_written": snap.get("detections_written"),
                                                                     "config_hash": snap.get("config_hash")}
        row = (job.id, kind, job.status, _now(), _dt.datetime.fromtimestamp(job.started_at).isoformat(timespec="seconds"),
               (_dt.datetime.fromtimestamp(job.finished_at).isoformat(timespec="seconds") if job.finished_at else None),
               1 if job.status == "cancelled" else 0, json.dumps(_clean(meta)), json.dumps(_clean(progress)),
               json.dumps(_clean(job.error)) if job.error else None, getattr(job, "db_run_id", None))
        with self._db_lock:
            try:
                conn = self._conn()
                try:
                    conn.execute(
                        "INSERT INTO jobs (id, kind, status, created_at, started_at, finished_at, cancelled, meta_json, progress_json, error_json, run_id) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET status=excluded.status, finished_at=excluded.finished_at, "
                        "cancelled=excluded.cancelled, progress_json=excluded.progress_json, error_json=excluded.error_json, run_id=excluded.run_id", row)
                    conn.commit()
                finally:
                    conn.close()
            except Exception:
                log.exception("persisting job %s failed", job.id)

    # ------------------------------------------------------- publishing --
    def _publish(self, job, event: dict):
        super()._publish(job, event)
        if event.get("event") in ("step_done", "run_end", "job_end", "cancel_requested"):
            self._persist(job)

    # ---------------------------------------------------------- starts --
    def start(self, recipe: dict, recording: dict, px: int = 1200) -> Job:
        job = super().start(recipe, recording, px)
        job.kind = "chain_run"
        self._persist(job)
        return job

    def start_job(self, kind: str, fn, meta: dict | None = None) -> GenericJob:
        if kind not in KINDS:
            raise ValueError(f"job kind must be one of {KINDS}, got {kind!r}")
        job = GenericJob(kind, meta or {}, self)
        with self._lock:
            self.jobs[job.id] = job
        job.status = "running"
        self._persist(job)
        self._emit(job, {"event": "job_start", "kind": kind, "meta": _clean(job.meta)})

        def _run():
            try:
                job.result = fn(job)
                job.status = "cancelled" if job.cancel_event.is_set() and job.result is None else "completed"
            except Exception as e:
                tb = traceback.format_exc()
                job.log_lines.append(tb)
                job.status = "failed"
                job.error = {"message": f"{type(e).__name__}: {e}", "type": type(e).__name__, "traceback": tb}
                log.error("job %s (%s) failed: %s", job.id, kind, job.error["message"])
            job.finished_at = time.time()
            self._persist(job)        # the row is final before anyone hears job_end
            self._emit(job, {"event": "job_end", "status": job.status, "error": job.error, "result": _clean(job.result),
                             "elapsed_s": job.finished_at - job.started_at})

        threading.Thread(target=_run, name=f"job-{job.id}-{kind}", daemon=True).start()
        return job

    def cancel(self, job) -> bool:
        if isinstance(job, GenericJob):
            if job.status != "running":
                return False
            job.cancel_event.set()
            self._emit(job, {"event": "cancel_requested"})
            return True
        return super().cancel(job)

    # ------------------------------------------------------- snapshots --
    def list_jobs(self, limit: int = 50) -> list[dict]:
        live = {j.id: j.snapshot() for j in self.jobs.values()}
        conn = self._conn()
        try:
            rows = conn.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
        finally:
            conn.close()
        out = []
        for r in rows:
            out.append(live.get(r["id"]) or self._from_row(r))
        for jid, snap in live.items():
            if all(o["job_id"] != jid for o in out):
                out.append(snap)
        out.sort(key=lambda s: -s["job_id"])
        return out

    def snapshot(self, job_id: int) -> dict | None:
        job = self.jobs.get(job_id)
        if job is not None:
            return job.snapshot()
        conn = self._conn()
        try:
            r = conn.execute("SELECT * FROM jobs WHERE id = ?", (int(job_id),)).fetchone()
            if r is None:
                return None
            snap = self._from_row(r)
            if r["kind"] == "chain_run" and r["run_id"]:
                run = conn.execute("SELECT * FROM runs WHERE id = ?", (int(r["run_id"]),)).fetchone()
                if run is not None:
                    snap["run_row"] = {k: run[k] for k in run.keys()}
                    if run["status"] in ("completed", "failed"):
                        snap["status"] = "failed" if run["status"] == "failed" else "completed"
                    if run["error_text"] and not snap.get("error"):
                        snap["error"] = {"message": run["error_text"].strip().splitlines()[-1] if run["error_text"].strip() else "failed",
                                         "traceback": run["error_text"], "type": "RecipeExecutionError", "step": run["current_step"]}
                    snap["n_detections"] = conn.execute("SELECT COUNT(*) FROM detections WHERE run_id = ?", (int(r["run_id"]),)).fetchone()[0]
            return snap
        finally:
            conn.close()

    @staticmethod
    def _from_row(r) -> dict:
        meta = json.loads(r["meta_json"] or "{}")
        progress = json.loads(r["progress_json"] or "{}")
        snap = {"job_id": r["id"], "kind": r["kind"], "status": r["status"], "created_at": r["created_at"],
                "started_at": r["started_at"], "finished_at": r["finished_at"], "cancelled": bool(r["cancelled"]),
                "error": json.loads(r["error_json"]) if r["error_json"] else None, "db_run_id": r["run_id"],
                "in_memory": False, "restored": True}
        if r["kind"] == "chain_run":
            snap.update({"recipe": meta.get("recipe"), "recording_id": meta.get("recording_id"), "px": meta.get("px"),
                         "steps": progress.get("steps") or [], "n_steps": progress.get("n_steps"),
                         "current_step": progress.get("current_step"), "step_timings": progress.get("step_timings"),
                         "detections_written": progress.get("detections_written"), "config_hash": progress.get("config_hash")})
            # a run the server lost mid-flight (restart) is reported as failed, never as running forever
            if snap["status"] in ("running", "queued"):
                snap["status"] = "failed"
                snap["error"] = snap["error"] or {"message": "the server restarted while this job was running", "type": "ServerRestart", "step": snap.get("current_step")}
        else:
            snap.update({"meta": meta, "progress": progress, "result": None})
            if snap["status"] in ("running", "queued"):
                snap["status"] = "failed"
                snap["error"] = snap["error"] or {"message": "the server restarted while this job was running", "type": "ServerRestart"}
        return snap
