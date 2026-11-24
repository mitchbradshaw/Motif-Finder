"""
autodetect_routes.py
====================
Auto-detect on the site (2026-11-23, the researcher: "integrate the auto-detect into the site"): one button on a
channel runs the reference line-up (`Working.autodetect.service`); the page draws the candidates over the signal,
shaded by confidence, with the sequences apart, and sends what the researcher picks to Review.

* ``GET  /api/autodetect/setup`` - whether a run can start here (R4's model and the seed bank on disk), the detector
  templates this database lacks, the rules, the seconds-per-sample estimate.
* ``POST /api/autodetect/runs {recording_id, t0_s?, t1_s?}`` - an ``autodetect`` job with real progress (permille of
  the stages, weighted by how long each took on the reference channels) and a time left in its message. 409 with
  the running job's id when one already runs on that channel (one run per channel: a second press is not a second
  run); 423 for the held-out recording while the lock is on; 422 for a bad stretch; 503 when the model or the seed
  bank is missing.
* ``GET  /api/autodetect/runs?recording_id=`` - saved results, newest first, and the job running on the channel.
* ``GET  /api/autodetect/runs/{job_id}`` - one result as the page draws it.
* ``GET  /api/autodetect/signal/{recording_id}?start_idx=&end_idx=`` - the stretch's samples in millivolts (read as
  auto-detect reads them) as 16-bit integers in base64, with the scale: one read, then every zoom is the page's own.
* ``POST /api/autodetect/runs/{job_id}/send {min_confidence, polarities, candidate_ids?, sequences}`` - into Review:
  the candidates as machine detections in a listed detection queue, the sequences into sequence review.

Results live on disk (CLAUDE.md rule 4): in the runtime's results folder for a sandbox bridge, the core's own
``DATA/derived/autodetect`` otherwise. A send writes machine rows only (rule 5).
"""
from __future__ import annotations

import base64
import os
import threading

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from . import corpus

router = APIRouter()

#: One send at a time: a send reads run.json's record of what went before and writes it back, so two at once (two
#: tabs, a double press that beat the button) would each send what the other was sending.
_SEND_LOCK = threading.Lock()


def _conn(request: Request):
    return corpus.connect(request.app.state.rt.db_path)


def results_root(rt):
    """Where this bridge keeps auto-detect results: inside the runtime for a sandbox, the core's folder otherwise."""
    from Working.autodetect import service
    return os.path.join(rt.results_dir, "autodetect") if getattr(rt, "results_dir", None) else service.RESULTS_DIR


def _recording(c, recording_id):
    rec = corpus.recording_row(c, int(recording_id))
    if rec is None:
        raise HTTPException(404, f"no recording id {recording_id}")
    if rec["held_out"]:
        raise HTTPException(423, corpus.held_out_refusal("auto-detect refuses it"))
    return rec


def _running(request: Request, recording_id):
    for job in list(request.app.state.manager.jobs.values()):
        meta = getattr(job, "meta", {}) or {}
        if getattr(job, "kind", None) == "autodetect" and job.status == "running" \
                and int(meta.get("recording_id", -1)) == int(recording_id):
            return job.snapshot()
    return None


def _fmt_left(s):
    if s is None or not np.isfinite(s):
        return ""
    s = max(0.0, float(s))
    return f"about {s / 60:.0f} min left" if s >= 90 else f"about {s:.0f} s left"


@router.get("/api/autodetect/setup")
def autodetect_setup(request: Request):
    from Working.autodetect import service
    c = _conn(request)
    try:
        out = service.setup(c)
    finally:
        c.close()
    out["results_root"] = results_root(request.app.state.rt)
    return out


class RunBody(BaseModel):
    recording_id: int
    t0_s: float | None = None
    t1_s: float | None = None


@router.post("/api/autodetect/runs")
def autodetect_start(body: RunBody, request: Request):
    from Working.autodetect import service
    rt, manager = request.app.state.rt, request.app.state.manager
    c = _conn(request)
    try:
        rec = _recording(c, body.recording_id)
        ready = service.setup(c)
    finally:
        c.close()
    if not ready["ready"]:
        raise HTTPException(503, "auto-detect cannot run here: " + "; ".join(ready["problems"]))
    busy = _running(request, body.recording_id)
    if busy is not None:
        raise HTTPException(409, {"message": f"auto-detect is already running on this channel (job {busy['job_id']})",
                                  "job_id": busy["job_id"]})
    fs, n = float(rec["fs"]), int(rec["n_samples"])
    a = 0 if body.t0_s is None else int(round(body.t0_s * fs))
    b = n if body.t1_s is None else int(round(body.t1_s * fs))
    if not (0 <= a < b <= n) or b - a < 10:
        raise HTTPException(422, f"the stretch must lie inside the channel (0-{n / fs:.0f} s) and be longer than "
                                 f"10 samples; got {a / fs:.1f}-{b / fs:.1f} s")
    root = results_root(rt)
    estimate = service.estimate_s(b - a)
    rid, db_path = int(rec["id"]), rt.db_path

    def work(job):
        conn = corpus.connect(db_path)
        try:
            row = corpus.recording_row(conn, rid)
            x = corpus.load_native(row["npy_path"])

            def on_progress(frac, message, left):
                job.progress(int(round(1000 * frac)), 1000, f"{message} · {_fmt_left(left)}")

            job.progress(0, 1000, f"loading R4 and the seed bank · {_fmt_left(estimate)}")
            try:
                res, meta = service.run(conn, row, x, start_idx=a, end_idx=b, on_progress=on_progress,
                                        cancelled=job.cancel_event.is_set)
            except service.Cancelled:
                return None
            meta["job_id"] = job.id
            out = service.result_dir(job.id, root)
            summary = service.save(out, res, meta)
            job.progress(1000, 1000, f"done: {summary['candidates']} candidates, {summary['at_05']} at 0.5 or more")
            return {"job_id": job.id, "recording_id": rid, **summary}
        finally:
            conn.close()

    job = manager.start_job("autodetect", work, meta={
        "what": "auto-detect", "recording_id": rid, "source_file": rec["source_file"], "channel": rec["channel"],
        "name": rec["name"], "t0_s": a / fs, "t1_s": b / fs, "estimate_s": estimate})
    return {"job_id": job.id, "estimate_s": estimate, "status": job.status}


@router.get("/api/autodetect/runs")
def autodetect_list(request: Request, recording_id: int | None = None):
    from Working.autodetect import service
    return {"results": service.results(results_root(request.app.state.rt), recording_id=recording_id),
            "running": _running(request, recording_id) if recording_id is not None else None}


def _result_dir(request: Request, job_id: int):
    from Working.autodetect import service
    out = service.result_dir(job_id, results_root(request.app.state.rt))
    if not os.path.isfile(os.path.join(out, "run.json")):
        raise HTTPException(404, f"no auto-detect result for job {job_id}")
    return out


@router.get("/api/autodetect/runs/{job_id}")
def autodetect_result(job_id: int, request: Request):
    from Working.autodetect import service
    out = _result_dir(request, job_id)
    cands, seqs, meta = service.load(out)
    c = _conn(request)
    try:
        _recording(c, meta["recording"]["id"])          # the lock as it stands now
        # the spans Review can match a sent candidate against: its rediscovery check reads this recording's own
        # annotations only, so a verdict given on another copy of the channel (another rate) is not among them
        judged = int(c.execute("SELECT COUNT(*) FROM annotations WHERE recording_id = ? AND deleted_at IS NULL",
                               (int(meta["recording"]["id"]),)).fetchone()[0])
    finally:
        c.close()
    body = service.payload(cands, seqs, meta)
    body["job_id"] = int(job_id)
    body["judged_here"] = judged
    return body


@router.get("/api/autodetect/signal/{recording_id}")
def autodetect_signal(recording_id: int, request: Request, start_idx: int = 0, end_idx: int | None = None):
    from Working.units import read_as_mv
    c = _conn(request)
    try:
        rec = _recording(c, recording_id)
    finally:
        c.close()
    n = int(rec["n_samples"])
    a, b = max(0, int(start_idx)), n if end_idx is None else min(n, int(end_idx))
    if not a < b:
        raise HTTPException(422, f"start_idx must be below end_idx inside 0-{n}; got {start_idx}-{end_idx}")
    factor, note = read_as_mv(rec.get("units"))
    x = np.asarray(corpus.load_native(rec["npy_path"])[a:b], dtype=np.float64) * factor
    finite = np.isfinite(x)
    lo, hi = (float(x[finite].min()), float(x[finite].max())) if finite.any() else (0.0, 1.0)
    scale = max(hi - lo, 1e-9) / 65000.0
    offset = (hi + lo) / 2.0
    q = np.full(len(x), -32768, dtype=np.int16)
    q[finite] = np.clip(np.round((x[finite] - offset) / scale), -32500, 32500).astype(np.int16)
    return {"recording_id": int(recording_id), "start_idx": a, "n": int(b - a), "fs": float(rec["fs"]),
            "unit": "mV", "unit_note": note, "scale": scale, "offset": offset, "missing": -32768,
            "b64": base64.b64encode(q.tobytes()).decode("ascii")}


class SendBody(BaseModel):
    min_confidence: float = 0.5
    polarities: list[str] = ["drop", "spike"]
    candidate_ids: list[int] | None = None
    sequences: bool = True
    name: str | None = None


@router.post("/api/autodetect/runs/{job_id}/send")
def autodetect_send(job_id: int, body: SendBody, request: Request):
    from Working.autodetect import service
    out = _result_dir(request, job_id)
    bad = [p for p in body.polarities if p not in ("drop", "spike")]
    if bad or not body.polarities:
        raise HTTPException(422, f"polarities must be drop and/or spike; got {body.polarities}")
    if not 0.0 <= float(body.min_confidence) <= 1.0:
        raise HTTPException(422, f"min_confidence must lie in 0-1; got {body.min_confidence}")
    with _SEND_LOCK:
        _cands, _seqs, meta = service.load(out)
        c = _conn(request)
        try:
            _recording(c, meta["recording"]["id"])
            return service.send_to_review(c, out, job_id=job_id, min_confidence=body.min_confidence,
                                          polarities=tuple(body.polarities), candidate_ids=body.candidate_ids,
                                          sequences=body.sequences, name=body.name)
        finally:
            c.close()
