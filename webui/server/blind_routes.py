"""fixup-ah: the bridge side of the BLIND check of a B.2 run (ticket
`docs/prompts/fixup/AH-blind-test-labelling.md`; the core is
`Working/training/blind.py`).

* ``POST /api/models/b2/runs/{run_id}/blind`` — Models › Results › *Label test
  windows blind*: the run's fixed, seeded sample and the Review queue over it
  (the same queue on a second press; a different sample is a 409).
* ``GET /api/models/b2/blind/{qid}`` and ``…/showings/{i}`` — what the labelling
  card reads: the showings (answered or not, and THIS showing's own answer) and
  one window's raw trace in mV with context either side. Neither carries
  anything that could tip the answer: no prediction, cluster, class, score,
  weight or exam, no recording or channel name, no earlier label on the span.
  The answer itself goes through Review's own verdict route
  (``POST /api/review/queues/{qid}/verdict``), so undo, the audit and rule 5 are
  the core's.
* ``GET /api/models/b2/runs/{run_id}/blind`` — Results "against a blind human",
  per exam, never pooled; ``…/blind/disagreements`` the step-through;
  ``POST …/blind/reference`` scores the comparison line (a job).
"""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from . import corpus
from .runtime import REPO_ROOT

router = APIRouter()


def _conn(request: Request):
    return corpus.connect(request.app.state.rt.db_path)


def _call(fn, *a, **kw):
    from Working.training.blind import SampleFixed
    try:
        return fn(*a, **kw)
    except SampleFixed as e:
        raise HTTPException(409, str(e))
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


class BlindBody(BaseModel):
    n: int = 1000
    repeat_frac: float = 0.10
    seed: int = 0


@router.post("/api/models/b2/runs/{run_id}/blind")
def make_blind_queue(request: Request, run_id: int, body: BlindBody):
    from Working.training import blind as bl
    c = _conn(request)
    try:
        return _call(bl.make_queue, c, run_id, n=body.n, repeat_frac=body.repeat_frac, seed=body.seed)
    finally:
        c.close()


@router.get("/api/models/b2/runs/{run_id}/blind")
def blind_scores(request: Request, run_id: int, n_boot: int = Query(default=1000, ge=0, le=5000),
                 n_null: int = Query(default=1000, ge=0, le=5000)):
    from Working.training import blind as bl
    c = _conn(request)
    try:
        out = _call(bl.score, c, run_id, n_boot=n_boot, n_null=n_null)
        names = corpus.dataset_names(c)
        for ex in (out.get("exams") or {}).values():
            for r in ex.get("per_recording") or []:
                r["name"] = names.get(r["recording"], r["recording"])
        from Working.training.store import jsonable
        return jsonable(out)
    finally:
        c.close()


@router.get("/api/models/b2/runs/{run_id}/blind/disagreements")
def blind_disagreements(request: Request, run_id: int, exam: str, kind: str):
    from Working.training import blind as bl
    c = _conn(request)
    try:
        rows = _call(bl.disagreements, c, run_id, exam, kind)
        q = bl.queue_for_run(c, run_id)
        for r in rows:
            rec = corpus.recording_row(c, r["recording_id"]) or {}
            r["recording"] = corpus.dataset_names(c).get(r["source_file"], r["source_file"])
            r["channel_name"] = rec.get("name") or f"CH{r['channel']}"
        return {"run_id": run_id, "exam": exam, "kind": kind, "queue_id": int(q["id"]) if q else None, "windows": rows}
    finally:
        c.close()


@router.post("/api/models/b2/runs/{run_id}/blind/reference")
def blind_reference(request: Request, run_id: int):
    """Score the comparison line — the manual-label models on the sample's windows, at every scale — as a job."""
    from Working.training import blind as bl
    manager = request.app.state.manager
    c = _conn(request)
    try:
        if bl.queue_for_run(c, run_id) is None:
            raise HTTPException(409, f"B.2 run {run_id} has no blind sample yet: Label test windows blind first")
    finally:
        c.close()
    models_dir = os.path.join(REPO_ROOT, "MODELS")

    def work(job):
        cc = _conn(request)
        try:
            out = bl.run_reference(cc, run_id, models_dir, progress=lambda d, t, m: job.progress(d, t, m),
                                   cancel=job.cancel_event.is_set)
            return {"run_id": run_id, "n_windows": out["n_windows"],
                    "models": {k: {kk: v.get(kk) for kk in ("status", "reason")} for k, v in out["models"].items()}}
        finally:
            cc.close()

    job = manager.start_job("training", work, meta={"stage": "blind comparison line", "run_id": run_id, "where": "local"})
    return job.snapshot()


# ── the labelling card ──────────────────────────────────────────────────────

def _blind_queue(c, qid):
    from Working.review import queues as Q
    q = Q.get_queue(c, int(qid))
    if q is None or q["source_kind"] != "blind-test":
        raise HTTPException(404, f"no blind test queue {qid}")
    return q


@router.get("/api/models/b2/blind/{qid}")
def blind_queue_page(request: Request, qid: int):
    """The labelling page's queue: progress, and each showing answered or not (its OWN answer only)."""
    from Working.review import queues as Q
    from Working.training import blind as bl
    c = _conn(request)
    try:
        q = _blind_queue(c, qid)
        items = bl.resolve_items(c, q)
        counts = Q.queue_counts(c, int(q["id"]))
        nxt = next((it["showing"] for it in items if not it["judged"]), None)
        return {"queue": {"id": int(q["id"]), "name": q["name"], "total": counts["total"], "judged": counts["judged"],
                          "remaining": counts["remaining"], "pace_s": Q.queue_pace_s(c, int(q["id"])),
                          "verdict_options": q.get("verdict_options") or list(bl.VERDICT_OPTIONS),
                          "run_id": int(q["filters"].get("run_id")), "closed": bool(q.get("closed_at"))},
                "showings": [{"showing": it["showing"], "judged": it["judged"], "verdict": it["verdict"]} for it in items],
                "next_unjudged": nxt,
                "hidden": ("the model's answer, its cluster and score, which exam the window is from, the recording and "
                           "channel, where in the recording it sits, any earlier human label on the span, and your "
                           "first answer when a window comes round a second time")}
    finally:
        c.close()


def _scale_text(length: int, fs: float) -> str:
    s = length / fs
    dur = f"{s / 60:g}-minute" if s >= 60 and abs(s / 60 - round(s / 60)) < 1e-9 else f"{s:g}-second"
    return f"a {dur} window · {length:,} samples at {fs:g} Hz"


@router.get("/api/models/b2/blind/{qid}/showings/{i}")
def blind_showing(request: Request, qid: int, i: int, px: int = Query(default=1200), pad: float = Query(default=1.0, ge=0, le=3)):
    """One showing's raw trace in true mV, the window shaded and `pad` window-lengths of context either side."""
    from .review import _trace_env
    from Working.training import blind as bl
    c = _conn(request)
    try:
        q = _blind_queue(c, qid)
        items = bl.resolve_items(c, q)
        if not 0 <= i < len(items):
            raise HTTPException(404, f"blind queue {qid} has {len(items)} showings; there is no showing {i}")
        it = items[i]
        rec = corpus.recording_row(c, it["recording_id"])
        if rec is None:
            raise HTTPException(404, f"recording {it['recording_id']} is not in the database")
        if rec.get("held_out"):
            raise HTTPException(409, "the held-out recording is never shown")
        ln, fs = int(it["length"]), float(it["fs"])
        ctx = int(round(pad * ln))
        c0 = max(0, it["start_idx"] - ctx)
        c1 = min(int(rec["n_samples"]), it["end_idx"] + ctx)
        tr = _trace_env(rec, c0, c1, px)
        tr["source"] = None              # the recording and channel are not shown (see `hidden`)
        return {"showing": it["showing"], "n_showings": len(items), "judged": it["judged"], "verdict": it["verdict"],
                "window": {"t0_s": it["start_idx"] / fs, "t1_s": it["end_idx"] / fs},
                "duration_s": it["duration_s"], "length": ln, "fs": fs, "scale_text": _scale_text(ln, fs),
                "pad_windows": pad, "unit": tr.get("unit") or None, "trace": tr}
    finally:
        c.close()
