"""Review routes (stage-3 Prompt 05) — `/api/review/...`.

Thin over ``Working.review``: queues, verdicts, promotion and window verdicts
all live in the core and are *called* here, never reimplemented. In
particular this module holds **no verdict logic and no second rule-5 check**.
The decision about which table a verdict lands in was made once, at queue
creation, and is stored on `review_queues.writes_to`; a bridge-side copy of
that rule could only drift from the core's, and a drifted rule-5 check is
exactly the silent crossing CLAUDE.md rule 5 forbids. A ``PermissionError``
out of the core becomes an HTTP 409 whose body carries the core's message
verbatim, so the line that was refused is the one the researcher reads.

What this module *does* add is presentation: the payload shapes
``webui/client/src/api/review.ts`` declares (`QueueData`, `ItemDetail`,
`OtherChannelRow`), built from real rows — and real decimated mV read off the
channel memmap through ``decimate.envelope``, never a synthesised trace
(rule 4: the bulk array never enters the database and never reaches the
client whole).

Loud failure is structural (CLAUDE.md, "Web UI"): nothing here catches an
error into a blank or an empty list. An unknown queue is a 404, a held-out
recording is a `refused` string on an otherwise empty item, and anything
unexpected raises and is turned into a 500 with the traceback by the app's
handler.
"""
from __future__ import annotations

import json
import os
import sqlite3

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from Working.review import promotion as promotion_mod
from Working.review import queues as queues_mod
from Working.review import verdicts as verdicts_mod

from . import corpus, decimate
from .runtime import HELD_OUT_FILE

router = APIRouter(prefix="/api/review")

#: The recording token inside the held-out file name — see `library.py`.
HELD_OUT_STEM = HELD_OUT_FILE.split("_concat")[0]

#: Trace widths. `decimate.envelope` emits about 2*px points.
CONTEXT_PAD_S = 300           # matches the client's CONTEXT_PAD_MAX
CONTEXT_PX = 320
SHAPE_PX = 60
THUMB_PX = 24

#: `review_queues.source_kind` -> the client's `ReviewQueue.icon`/`rankKind`
#: are derived client-side; the bridge emits the stored columns unchanged.


# ── small helpers ───────────────────────────────────────────────────────────

def _rt(request: Request):
    return request.app.state.rt


def _conn(request: Request) -> sqlite3.Connection:
    rt = _rt(request)
    if not getattr(request.app.state, "schema_ensured", False):
        from Working.database.schema import init_db
        init_db(rt.db_path).close()
        request.app.state.schema_ensured = True
    return corpus.connect(rt.db_path)


def _is_held_out(source_file) -> bool:
    text = str(source_file or "").replace("\\", "/")
    base = os.path.basename(text)
    return HELD_OUT_FILE in text or base.startswith(HELD_OUT_STEM)


def refusal(label: str) -> str:
    """The refusal the fixture serves, verbatim (`api/review.ts`)."""
    return (f"{label} is held out (D6): it is locked for the final evaluation "
            f"and cannot be reviewed, plotted or queued.")


def rec_key(source_file) -> str:
    stem = os.path.splitext(os.path.basename(str(source_file or "")))[0]
    return stem.replace("_concat", "")


def rec_label(source_file) -> str:
    import re
    return re.sub(r"_(fs\d+)$", r" \1", rec_key(source_file))


def _index(conn) -> dict:
    """`recording_id -> {...}`. One pass; every read below shares it."""
    out = {}
    for g in corpus.recordings(conn):
        for ch in g["channels"]:
            out[int(ch["id"])] = {
                "recording_id": int(ch["id"]), "source_file": g["source_file"],
                "label": rec_label(g["source_file"]), "channel": int(ch["channel"]),
                "name": ch["name"], "fs": float(g["fs"]), "n_samples": int(g["n_samples"]),
                "held_out": bool(g.get("held_out") or _is_held_out(g["source_file"])),
            }
    return out


def _trace(conn, rec: dict | None, start_idx: int, end_idx: int, px: int) -> list:
    """Decimated mV for `[start_idx, end_idx)` of a channel, as a bare value
    list (the client's traces are values, the x axis is implied). A channel
    whose `.npy` is missing yields an empty list — the client draws nothing
    rather than a synthesised shape, because a synthetic trace beside a real
    one is a finding that is not there."""
    if not rec:
        return []
    row = corpus.recording_row(conn, int(rec["recording_id"]))
    path = (row or {}).get("npy_path")
    if not path or not os.path.isfile(path):
        return []
    x = corpus.load_channel(path)
    env = decimate.envelope(x, float(rec["fs"] or 1.0), int(start_idx), int(end_idx), px)
    return [None if v is None else round(float(v), 4) for v in env["v"]]


def _queue_or_404(conn, qid) -> dict:
    q = queues_mod.get_queue(conn, _qid(qid))
    if q is None:
        raise HTTPException(status_code=404, detail=f"no review queue {qid!r}")
    return q


def _qid(value) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        raise HTTPException(status_code=404, detail=f"no review queue {value!r}")


def _queue_payload(conn, q: dict) -> dict:
    """The stored queue columns plus its counts. The client derives icon,
    order text and rank kind from `source_kind`; nothing is invented here."""
    counts = q.get("counts") or queues_mod.queue_counts(conn, int(q["id"]))
    out = dict(q)
    out["id"] = int(q["id"])
    out.update({"total": int(counts.get("total", 0)),
                "judged": int(counts.get("judged", 0)),
                "remaining": int(counts.get("remaining", 0))})
    return out


def _entry_payload(conn, item: dict, queue: dict, index: dict, *, px: int = THUMB_PX) -> dict:
    """One queue row in the client's `QueueEntry` shape, with its thumbnail."""
    rid = item.get("recording_id")
    rec = index.get(int(rid)) if rid is not None else None
    start = int(item.get("start_idx") or 0)
    end = int(item.get("end_idx") or start)
    fs = float((rec or {}).get("fs") or 1.0)
    row = dict(item)
    # The core keys an item by `target_id` (what a verdict is written against);
    # the client's `QueueEntry.id` is that same identity as a string.
    row["id"] = str(item.get("target_id", item.get("id")))
    row["queueId"] = str(queue["id"])
    row["unit"] = queue.get("unit") or item.get("unit") or "detection"
    row["recording"] = (rec or {}).get("label") or str(item.get("recording") or "")
    row["channel"] = (rec or {}).get("name") or str(item.get("channel") or "")
    row["startH"] = round(start / fs / 3600.0, 6)
    row["durationS"] = round(max(0, end - start) / fs, 3)
    row["shape"] = item.get("shape") or ("window" if row["unit"] == "window" else "doublet")
    row["seed"] = int(item.get("seed") or abs(hash(row["id"])) % 10000)
    row["tags"] = list(item.get("tags") or [])
    if item.get("score") is not None:
        row["score"] = float(item["score"])
    if item.get("verdict"):
        row["baseVerdict"] = item["verdict"]
    row["thumb"] = [] if (rec or {}).get("held_out") else _trace(conn, rec, start, end, px)
    row["family"] = str(item.get("family") or "")
    return row


def _item_or_404(conn, queue: dict, item_id: str) -> dict:
    items = queues_mod.queue_items(conn, int(queue["id"]), include_judged=True)
    for it in items:
        if str(it.get("target_id", it.get("id"))) == str(item_id):
            return it
    raise HTTPException(status_code=404, detail=f"no item {item_id!r} in queue {queue['id']}")


def _detail(conn, queue: dict, item: dict, index: dict) -> dict:
    """The `ItemDetail` shape, key for key."""
    rid = item.get("recording_id")
    rec = index.get(int(rid)) if rid is not None else None
    qp = _queue_payload(conn, queue)
    entry = _entry_payload(conn, item, queue, index)
    if rec and rec["held_out"]:
        return {"entry": entry, "queue": qp, "context": {"values": [], "t0_s": 0.0},
                "shape": [], "nearest": [], "medoids": {}, "artifact": None,
                "evidence": None, "thumb": [], "refused": refusal(rec["label"])}

    start = int(item.get("start_idx") or 0)
    end = int(item.get("end_idx") or start)
    fs = float((rec or {}).get("fs") or 1.0)
    pad = int(CONTEXT_PAD_S * fs)
    c0 = max(0, start - pad)
    c1 = min(int((rec or {}).get("n_samples") or end + pad), end + pad)
    return {
        "entry": entry,
        "queue": qp,
        "context": {"values": _trace(conn, rec, c0, c1, CONTEXT_PX), "t0_s": round(c0 / fs, 3)},
        "shape": _trace(conn, rec, start, end, SHAPE_PX),
        "nearest": list(item.get("nearest") or []),
        "medoids": dict(item.get("medoids") or {}),
        "artifact": item.get("artifact"),
        "evidence": _evidence(item, qp),
        "thumb": entry["thumb"],
    }


def _evidence(item: dict, queue: dict) -> dict:
    """The provenance panel. Every field is read off the item and the queue —
    an absent one is None, never a plausible-looking default."""
    return {
        "origin": {
            "runKind": queue.get("source_kind"), "runId": queue.get("source_ref"),
            "template": item.get("template"), "stages": list(item.get("stages") or []),
            "recipeHash": item.get("recipe_hash"), "ran": item.get("created_at") or "",
            "by": item.get("by") or "", "scope": item.get("scope") or "",
        },
        "detection": ({"score": item.get("score"), "threshold": item.get("threshold"),
                       "recommended": None, "rank": item.get("rank"), "nullExpects": None,
                       "samples": f"{item.get('start_idx')} → {item.get('end_idx')}",
                       "fs": str(item.get("fs") or "")}
                      if item.get("score") is not None else None),
        "alsoFoundBy": {"runs": [], "human": "", "prior": ""},
        "history": {"revisions": "", "queues": ""},
        "writeTarget": queue.get("writes_to") or "",
    }


def _core_call(fn, *args, **kw):
    """Every write goes through the core. A rule-5 refusal is a 409 carrying
    the core's own message — the bridge never re-words it and never decides
    for itself whether a write crosses the line."""
    try:
        return fn(*args, **kw)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── bodies ──────────────────────────────────────────────────────────────────

class QueueBody(BaseModel):
    name: str
    source_kind: str
    source_ref: str | None = None
    unit: str | None = None
    writes_to: str | None = None
    blind: bool | None = None
    cap: int | None = None
    verdict_options: list[str] | None = None
    filters: dict | None = None
    note: str | None = None


class VerdictBody(BaseModel):
    target_id: str | int
    verdict: str
    note: str | None = None
    tags: list[str] | None = None
    window_index: int | None = None


class BatchBody(BaseModel):
    target_ids: list[str | int]
    verdict: str
    note: str | None = None
    tags: list[str] | None = None


class PromoteBody(BaseModel):
    target_id: str | int
    verdict: str = "seed"
    note: str | None = None
    tags: list[str] | None = None


class ExtractEvent(BaseModel):
    start_idx: int
    end_idx: int


class ExtractBody(BaseModel):
    sequence_id: str | int
    events: list[ExtractEvent] = []
    complete: bool = False


# ── reads ───────────────────────────────────────────────────────────────────

@router.get("/counts")
def get_counts(request: Request):
    """The header's "N need you" — one read, straight off the core."""
    conn = _conn(request)
    try:
        return queues_mod.header_counts(conn)
    finally:
        conn.close()


@router.get("/queues")
def get_queues(request: Request, include_closed: int = Query(default=0)):
    conn = _conn(request)
    try:
        return [_queue_payload(conn, q)
                for q in queues_mod.list_queues(conn, include_closed=bool(include_closed))]
    finally:
        conn.close()


@router.post("/queues")
def post_queue(request: Request, body: QueueBody):
    conn = _conn(request)
    try:
        qid = _core_call(queues_mod.create_queue, conn, name=body.name,
                         source_kind=body.source_kind, source_ref=body.source_ref,
                         unit=body.unit, writes_to=body.writes_to, blind=body.blind,
                         cap=body.cap, verdict_options=body.verdict_options,
                         filters=body.filters, note=body.note)
        return {"queue": _queue_payload(conn, _queue_or_404(conn, qid))}
    finally:
        conn.close()


@router.get("/queues/{qid}")
def get_queue(request: Request, qid: str, include_judged: int = Query(default=1)):
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        index = _index(conn)
        items = queues_mod.queue_items(conn, int(queue["id"]),
                                       include_judged=bool(include_judged))
        # A held-out recording never appears as a row: it is refused, not listed.
        items = [it for it in items
                 if not index.get(int(it.get("recording_id") or -1), {}).get("held_out")]
        rows = [_entry_payload(conn, it, queue, index) for it in items]
        return {"queue": _queue_payload(conn, queue), "rows": rows, "clusters": _clusters(items, queue)}
    finally:
        conn.close()


def _clusters(items: list, queue: dict) -> list:
    """Cluster rows the queue's items already carry (`clusterNo`/`cluster_no`).
    A queue whose source produced no clusters has none — an empty list here is
    an absence the source reported, not an error swallowed."""
    byno: dict = {}
    for it in items:
        no = it.get("clusterNo", it.get("cluster_no"))
        if no is None:
            continue
        byno.setdefault(int(no), []).append(str(it.get("target_id", it.get("id"))))
    return [{"no": no, "queueId": str(queue["id"]), "kind": "family set",
             "badge": queue.get("source_kind") or "", "members": members,
             "defaultMember": members[0], "nearestMember": members[0],
             "stripCaption": f"cluster {no}", "previousLine": None}
            for no, members in sorted(byno.items())]


@router.get("/queues/{qid}/items/{item_id}")
def get_item(request: Request, qid: str, item_id: str):
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        item = _item_or_404(conn, queue, item_id)
        return _detail(conn, queue, item, _index(conn))
    finally:
        conn.close()


@router.get("/queues/{qid}/items/{item_id}/channels")
def get_item_channels(request: Request, qid: str, item_id: str):
    """The other channels of the same recording over the item's window."""
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        item = _item_or_404(conn, queue, item_id)
        index = _index(conn)
        rid = item.get("recording_id")
        rec = index.get(int(rid)) if rid is not None else None
        if not rec or rec["held_out"]:
            return []
        start = int(item.get("start_idx") or 0)
        end = int(item.get("end_idx") or start)
        fs = float(rec["fs"] or 1.0)
        pad = int(CONTEXT_PAD_S * fs)
        out = []
        for other in index.values():
            if other["source_file"] != rec["source_file"]:
                continue
            out.append({"channel": other["name"], "r": None,
                        "values": _trace(conn, other, max(0, start - pad),
                                         min(other["n_samples"], end + pad), CONTEXT_PX),
                        "current": other["recording_id"] == rec["recording_id"]})
        return out
    finally:
        conn.close()


@router.get("/queues/{qid}/cluster/{no}")
def get_cluster(request: Request, qid: str, no: int):
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        index = _index(conn)
        items = queues_mod.queue_items(conn, int(queue["id"]), include_judged=True)
        clusters = _clusters(items, queue)
        cluster = next((c for c in clusters if int(c["no"]) == int(no)), None)
        if cluster is None:
            raise HTTPException(status_code=404, detail=f"no cluster {no} in queue {queue['id']}")
        members = [it for it in items
                   if str(it.get("target_id", it.get("id"))) in cluster["members"]]
        return {"cluster": cluster, "queue": _queue_payload(conn, queue),
                "members": [_detail(conn, queue, it, index) for it in members]}
    finally:
        conn.close()


# ── writes (every one through Working.review) ───────────────────────────────

@router.post("/queues/{qid}/verdict")
def post_verdict(request: Request, qid: str, body: VerdictBody):
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        result = _core_call(verdicts_mod.write_verdict, conn, int(queue["id"]),
                            body.target_id, body.verdict, note=body.note,
                            tags=body.tags, window_index=body.window_index)
        conn.commit()
        return {"verdict": result, "counts": queues_mod.queue_counts(conn, int(queue["id"]))}
    finally:
        conn.close()


@router.post("/queues/{qid}/batch")
def post_batch(request: Request, qid: str, body: BatchBody):
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        result = _core_call(verdicts_mod.write_batch, conn, int(queue["id"]),
                            list(body.target_ids), body.verdict, note=body.note,
                            tags=body.tags)
        conn.commit()
        return {"batch": result, "counts": queues_mod.queue_counts(conn, int(queue["id"]))}
    finally:
        conn.close()


@router.post("/queues/{qid}/undo")
def post_undo(request: Request, qid: str):
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        result = _core_call(verdicts_mod.undo_last, conn, int(queue["id"]))
        conn.commit()
        return {"undone": result, "counts": queues_mod.queue_counts(conn, int(queue["id"]))}
    finally:
        conn.close()


@router.post("/queues/{qid}/promote")
def post_promote(request: Request, qid: str, body: PromoteBody):
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        result = _core_call(promotion_mod.promote, conn, int(queue["id"]), body.target_id,
                            verdict=body.verdict, note=body.note, tags=body.tags)
        conn.commit()
        return result
    finally:
        conn.close()


@router.post("/queues/{qid}/cluster/{no}/accept")
def post_cluster_accept(request: Request, qid: str, no: int):
    return _cluster_batch(request, qid, no, "interesting")


@router.post("/queues/{qid}/cluster/{no}/reject")
def post_cluster_reject(request: Request, qid: str, no: int):
    return _cluster_batch(request, qid, no, "not_interesting")


def _cluster_batch(request: Request, qid: str, no: int, verdict: str):
    """Accepting or rejecting a cluster is a batch: ONE audit row covering the
    N members, so undo takes the whole gesture back the way it was made."""
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        items = queues_mod.queue_items(conn, int(queue["id"]), include_judged=True)
        cluster = next((c for c in _clusters(items, queue) if int(c["no"]) == int(no)), None)
        if cluster is None:
            raise HTTPException(status_code=404, detail=f"no cluster {no} in queue {queue['id']}")
        result = _core_call(verdicts_mod.write_batch, conn, int(queue["id"]),
                            cluster["members"], verdict, note=f"cluster {no}")
        conn.commit()
        return {"batch": result, "counts": queues_mod.queue_counts(conn, int(queue["id"]))}
    finally:
        conn.close()


@router.post("/queues/{qid}/extract")
def post_extract(request: Request, qid: str, body: ExtractBody):
    """Extract events from a sequence: each event is a human span, written
    through the core's promotion door (queue `writes_to` = annotations)."""
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        written = []
        for ev in body.events:
            written.append(_core_call(
                verdicts_mod.write_verdict, conn, int(queue["id"]),
                body.sequence_id, "interesting",
                note=json.dumps({"start_idx": ev.start_idx, "end_idx": ev.end_idx})))
        if body.complete:
            _core_call(verdicts_mod.write_verdict, conn, int(queue["id"]),
                       body.sequence_id, "interesting", note="extraction complete")
        conn.commit()
        return {"written": written, "counts": queues_mod.queue_counts(conn, int(queue["id"]))}
    finally:
        conn.close()
