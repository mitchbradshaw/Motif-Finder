"""
cross_routes.py
===============
Cross-channel explorer S1: the census's routes, over `Working.cross_census` (the core computes and stores every
number; this file only starts the job and reads the rows back).

- `POST /api/cross/census {source_file, detector?}` — a `cross_census` job with real progress (done of total). 423
  for the held-out recording (the core refuses it by name, whatever the lock says); 422 in words when the detector
  is not full on the recording ("drop_detection_v5 has a real run on 2 of 16 channels").
- `GET /api/cross/census?source_file=&detector=` — the latest census of that detector (summary, hash, stale and
  why, the layout, the rules in words, the detectors offered with their reasons, a running job), or `census: null`.
  The page never computes the census on load (D20).
- `GET /api/cross/census/{census_id}/cooccurrences?bin=&a=&b=&instant=&limit=&offset=` — its rows (for S7).

This router is registered BEFORE `explore_routes`: `GET /api/cross/{recording_id}` would otherwise take
`/api/cross/census` and answer a 422 for a non-integer id.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from Working import cross_census as cc

from . import corpus
from .runtime import HELD_OUT_FILE

router = APIRouter()


class CensusBody(BaseModel):
    source_file: str
    detector: str | None = None


def _conn(request: Request):
    return corpus.connect(request.app.state.rt.db_path)


def _refuse_held_out(conn, source_file):
    if source_file == HELD_OUT_FILE:
        why = (corpus.held_out_refusal("no census is made from it") if corpus.is_held_out(conn, source_file)
               else f"{source_file} is the held-out recording: no census is made from it, whatever the lock says")
        raise HTTPException(423, why)


def _running(request: Request, source_file, detector):
    manager = request.app.state.manager
    for job in list(manager.jobs.values()):
        meta = getattr(job, "meta", {}) or {}
        if getattr(job, "kind", None) == "cross_census" and job.status == "running" \
                and meta.get("source_file") == source_file and meta.get("detector") == detector:
            return job.snapshot()
    return None


def _census_payload(conn, row):
    st = cc.is_stale(conn, row)
    return {"id": int(row["id"]), "sourceFile": row["source_file"], "detector": row["detector"], "hash": row["hash"],
            "status": row["status"], "createdAt": row["created_at"], "finishedAt": row["finished_at"],
            "actor": row["actor"], "summary": row["summary"], "rule": row["rule"], "consts": row["consts"],
            "nullPath": row["null_path"], "stale": st["stale"], "staleWhy": st["why"]}


@router.get("/api/cross/census")
def get_census(request: Request, source_file: str, detector: str | None = None):
    detector = detector or cc.DEFAULT_DETECTOR
    c = _conn(request)
    try:
        _refuse_held_out(c, source_file)
        from Working.channel_layout import channel_layout
        try:
            layout = channel_layout(c, source_file)
        except LookupError as e:
            raise HTTPException(404, str(e)) from None
        offered = cc.detectors_offered(c, source_file, layout=layout)
        row = cc.latest_census(c, source_file, detector)
        rule = cc.xc.rule_from_settings(c)
        return {"sourceFile": source_file, "detector": detector,
                "census": _census_payload(c, row) if row else None,
                "detectors": [{"detector": d["detector"], "full": d["full"], "reason": d["reason"],
                               "nWithRun": d["n_with_run"], "nChannels": d["n_channels"]} for d in offered],
                "layoutKnown": bool(layout["layout_known"]), "layoutNote": layout.get("note"),
                "packs": layout["packs"], "rules": cc.rules_in_words(rule, cc.DEFAULT_CONSTANTS),
                "running": _running(request, source_file, detector)}
    finally:
        c.close()


@router.post("/api/cross/census")
def post_census(request: Request, body: CensusBody):
    rt = request.app.state.rt
    detector = body.detector or cc.DEFAULT_DETECTOR
    source_file = body.source_file
    c = _conn(request)
    try:
        _refuse_held_out(c, source_file)
        from Working.channel_layout import channel_layout
        try:
            layout = channel_layout(c, source_file)
        except LookupError as e:
            raise HTTPException(404, str(e)) from None
        status = cc.detector_status(c, source_file, detector, layout=layout)
    finally:
        c.close()
    if not status["full"]:
        raise HTTPException(422, status["reason"])
    running = _running(request, source_file, detector)
    if running is not None:
        raise HTTPException(409, f"a census of {source_file} by {detector} is already running (job "
                                 f"{running['job_id']})")

    def _work(job):
        conn = corpus.connect(rt.db_path)
        try:
            out = cc.run_census(conn, source_file, detector, progress=job.progress, cancel=job.cancel_event.is_set,
                                actor="Explore › Cross-channel")
            if out is None:
                return None
            s = out["summary"]
            from Working.registration.settings import append_audit
            append_audit(conn, "explore", f"Cross-channel census of {source_file} by {detector}: "
                         + " · ".join(f"{b} {s['bins'][b]}" for b in cc.CENSUS_BINS),
                         "Explore › Cross-channel", route="explore/cross",
                         detail={"census_id": out["census_id"], "hash": out["hash"], "bins": s["bins"]})
        finally:
            conn.close()
        return {"census_id": out["census_id"], "hash": out["hash"], "bins": s["bins"],
                "n_cooccurrences": s["n_cooccurrences"], "timing_s": s.get("timing_s")}

    job = request.app.state.manager.start_job("cross_census", _work, meta={
        "what": "cross-channel census", "stage": f"census · {source_file} · {detector}", "source_file": source_file,
        "detector": detector})
    return {"job_id": job.id, "kind": "cross_census", "status": job.status, "sourceFile": source_file,
            "detector": detector}


@router.get("/api/cross/census/{census_id}/cooccurrences")
def get_cooccurrences(request: Request, census_id: int, bin: str | None = None, a: int | None = None,
                      b: int | None = None, instant: int | None = None, limit: int = 200, offset: int = 0):
    if bin is not None and bin not in cc.CENSUS_BINS:
        raise HTTPException(422, f"bin must be one of {', '.join(cc.CENSUS_BINS)}, got {bin!r}")
    c = _conn(request)
    try:
        row = c.execute("SELECT source_file FROM cross_census WHERE id = ?", (int(census_id),)).fetchone()
        if row is None:
            raise HTTPException(404, f"no census {census_id}")
        _refuse_held_out(c, row[0])
        return {"censusId": int(census_id),
                **cc.cooccurrence_rows(c, census_id, bin=bin, a=a, b=b, instant=instant,
                                       limit=max(1, min(2000, limit)), offset=offset)}
    finally:
        c.close()
