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
import re
import sqlite3

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from Working.review import extraction as extraction_mod
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


def _queue_payload(conn, q: dict, *, exclude_recording_ids=None) -> dict:
    """The stored queue columns plus its counts. The client derives icon,
    order text and rank kind from `source_kind`; nothing is invented here."""
    counts = q.get("counts") or queues_mod.queue_counts(
        conn, int(q["id"]),
        exclude_recording_ids=(exclude_recording_ids
                               if exclude_recording_ids is not None
                               else _held_out_ids(conn)))
    out = dict(q)
    out["id"] = int(q["id"])
    out.update({"total": int(counts.get("total", 0)),
                "judged": int(counts.get("judged", 0)),
                "remaining": int(counts.get("remaining", 0))})
    return out


_CH_IN_FILE = re.compile(r"_(CH\d+)(?:_|\.|$)", re.IGNORECASE)


def _channel_label(rec: dict | None, item: dict) -> str:
    """What to call this trace's channel.

    A single-channel export names its electrode in the file
    (`Mushroom_260720_0509_4hrs_CH14_fs1.mat`), and `recordings.name` for such a
    file is the within-file index — "CH1", because there is only one. Showing
    that contradicts the queue's own title and the file on disk, and a reviewer
    comparing the two has no way to tell which is lying. The file wins where it
    says so.
    """
    src = (rec or {}).get("source_file") or ""
    m = _CH_IN_FILE.search(str(src))
    if m:
        return m.group(1).upper()
    return (rec or {}).get("name") or str(item.get("channel") or "")


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
    row["channel"] = _channel_label(rec, item)
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
    """The item, INCLUDING ones the default listing filters out.

    A rediscovery is excluded from the queue's rows on purpose, but a deep link
    to it must still open — "there must be a way to see what was auto-excluded"
    is the whole point of `include_prior_judged`.
    """
    items = queues_mod.queue_items(conn, int(queue["id"]), include_judged=True,
                                   include_prior_judged=True)
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
                "shape": [], "nearest": [], "nearestComputed": False,
                "medoids": {}, "artifact": _artifact(item),
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
        "nearestComputed": bool(item.get("nearest_computed")),
        "medoids": dict(item.get("medoids") or {}),
        "artifact": _artifact(item),
        "evidence": _evidence(item, qp),
        "thumb": entry["thumb"],
    }


#: Artifact likelihood is a real analysis (cross-channel coherence, clipping,
#: step change, electrode flag) and NOTHING computes it yet. It is served as a
#: typed absence rather than `null` or a plausible number: `null` is what
#: `d.artifact.level` crashed the whole workspace on, and a made-up likelihood
#: beside a real waveform is a finding that is not there. `computed: false` is
#: the honest answer, and the words are what a reviewer reads in the pill.
_NOT_COMPUTED = "not computed"


def _artifact(item: dict) -> dict:
    got = item.get("artifact")
    if isinstance(got, dict) and got.get("computed"):
        return got
    return {"computed": False, "level": None, "p": None, "coherence": None,
            "clipping": _NOT_COMPUTED, "stepChange": _NOT_COMPUTED,
            "electrodeFlag": _NOT_COMPUTED,
            "reason": "artifact factors are not computed for this queue yet; "
                      "no likelihood is being withheld and none is being "
                      "guessed at"}


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


def _held_out_ids(conn) -> set:
    """Recording ids the final evaluation has locked (D6).

    Computed here and passed DOWN into the core, so the core never has to know
    what a held-out file is while the counts still agree with the rows.
    """
    return {int(r["id"]) for r in conn.execute(
        "SELECT id, source_file FROM recordings").fetchall()
        if _is_held_out(r["source_file"])}


def _refuse_held_out(conn, queue, target_ids):
    """A held-out item is refused on the WRITE path too.

    The read routes have always refused it; without this, a verdict on one was
    accepted and written, which is the one direction that actually damages the
    evaluation.
    """
    # A window has no recording of its own; every other unit does, and ALL of
    # them must be refused. Covering only `detection` left a held-out
    # recording's annotations and sequences writable, which is the half of D6
    # that actually damages the final evaluation.
    unit = queue.get("unit")
    sql = {
        # `detections` has no `recording_id`: a detection belongs to a run and
        # the run names the recording.
        "detection": "SELECT r.recording_id AS recording_id FROM detections d "
                     "JOIN runs r ON r.id = d.run_id WHERE d.id = ?",
        "human span": "SELECT recording_id FROM annotations WHERE id = ?",
        "sequence": "SELECT recording_id FROM sequences WHERE id = ?",
    }.get(unit)
    if sql is None:
        return
    held = _held_out_ids(conn)
    if not held:
        return
    index = _index(conn)
    for tid in target_ids:
        try:
            row = conn.execute(sql, (int(tid),)).fetchone()
        except (TypeError, ValueError):
            continue
        rid = row["recording_id"] if row else None
        if rid is not None and int(rid) in held:
            label = (index.get(int(rid)) or {}).get("label") or str(rid)
            raise HTTPException(status_code=409, detail=refusal(label))


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
    except sqlite3.IntegrityError as exc:
        # A CHECK constraint refusing a malformed row is the caller's mistake,
        # not the server falling over: a 500 traceback would say otherwise.
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
        return queues_mod.header_counts(
            conn, exclude_recording_ids=_held_out_ids(conn))
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
def get_queue(request: Request, qid: str, include_judged: int = Query(default=1),
              include_prior_judged: int = Query(default=0)):
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        index = _index(conn)
        held = _held_out_ids(conn)
        items = queues_mod.queue_items(
            conn, int(queue["id"]), include_judged=bool(include_judged),
            include_prior_judged=bool(include_prior_judged),
            exclude_recording_ids=held)
        rows = [_entry_payload(conn, it, queue, index) for it in items]
        return {"queue": _queue_payload(conn, queue, exclude_recording_ids=held),
                "rows": rows, "clusters": _clusters(items, queue)}
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
            raise HTTPException(status_code=404,
                                detail=_no_clusters(queue, no))
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
        _refuse_held_out(conn, queue, [body.target_id])
        result = _core_call(verdicts_mod.write_verdict, conn, int(queue["id"]),
                            body.target_id, body.verdict, note=body.note,
                            tags=body.tags, window_index=body.window_index)
        conn.commit()
        return {"verdict": result, "counts": queues_mod.queue_counts(
                    conn, int(queue["id"]),
                    exclude_recording_ids=_held_out_ids(conn))}
    finally:
        conn.close()


@router.post("/queues/{qid}/batch")
def post_batch(request: Request, qid: str, body: BatchBody):
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        _refuse_held_out(conn, queue, list(body.target_ids))
        result = _core_call(verdicts_mod.write_batch, conn, int(queue["id"]),
                            list(body.target_ids), body.verdict, note=body.note,
                            tags=body.tags)
        conn.commit()
        return {"batch": result, "counts": queues_mod.queue_counts(
                    conn, int(queue["id"]),
                    exclude_recording_ids=_held_out_ids(conn))}
    finally:
        conn.close()


@router.post("/queues/{qid}/undo")
def post_undo(request: Request, qid: str):
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        result = _core_call(verdicts_mod.undo_last, conn, int(queue["id"]))
        conn.commit()
        return {"undone": result, "counts": queues_mod.queue_counts(
                    conn, int(queue["id"]),
                    exclude_recording_ids=_held_out_ids(conn))}
    finally:
        conn.close()


@router.post("/queues/{qid}/promote")
def post_promote(request: Request, qid: str, body: PromoteBody):
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        _refuse_held_out(conn, queue, [body.target_id])
        result = _core_call(promotion_mod.promote, conn, int(queue["id"]), body.target_id,
                            verdict=body.verdict, note=body.note, tags=body.tags)
        conn.commit()
        return result
    finally:
        conn.close()


class UnpromoteBody(BaseModel):
    audit_id: int


@router.post("/queues/{qid}/unpromote")
def post_unpromote(request: Request, qid: str, body: UnpromoteBody):
    """Take back a promotion: the Library rows AND the verdict that made them.

    Without this route the client could mint a `motif_entry` with S and had no
    way to reverse it — and `undo_last` reversed only half, leaving a Library
    motif whose originating judgement no longer existed, which is the
    fabricated entry P21 says only a human verdict may create.
    """
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        out = _core_call(promotion_mod.unpromote, conn, int(body.audit_id))
        conn.commit()
        return {"unpromoted": out,
                "counts": queues_mod.queue_counts(
                    conn, int(queue["id"]),
                    exclude_recording_ids=_held_out_ids(conn))}
    finally:
        conn.close()


@router.post("/queues/{qid}/cluster/{no}/accept")
def post_cluster_accept(request: Request, qid: str, no: int):
    return _cluster_batch(request, qid, no, "interesting")


@router.post("/queues/{qid}/cluster/{no}/reject")
def post_cluster_reject(request: Request, qid: str, no: int):
    return _cluster_batch(request, qid, no, "not_interesting")


def _no_clusters(queue: dict, no: int) -> str:
    """Why a cluster route cannot answer.

    "no cluster 3" reads as a bad number and sends the reader looking for the
    right one. The truth is that no resolver for this queue's source kind emits
    a cluster at all, so there is no number that would work — say that.
    """
    return (f"review queue {queue['id']} has no clusters: its source kind "
            f"{queue.get('source_kind')!r} resolves items individually and "
            f"nothing groups them, so there is no cluster {no} or any other. "
            f"Cluster review needs a queue built from a Grouping.")


def _cluster_batch(request: Request, qid: str, no: int, verdict: str):
    """Accepting or rejecting a cluster is a batch: ONE audit row covering the
    N members, so undo takes the whole gesture back the way it was made."""
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        items = queues_mod.queue_items(conn, int(queue["id"]), include_judged=True)
        cluster = next((c for c in _clusters(items, queue) if int(c["no"]) == int(no)), None)
        if cluster is None:
            raise HTTPException(status_code=404,
                                detail=_no_clusters(queue, no))
        result = _core_call(verdicts_mod.write_batch, conn, int(queue["id"]),
                            cluster["members"], verdict, note=f"cluster {no}")
        conn.commit()
        return {"batch": result, "counts": queues_mod.queue_counts(
                    conn, int(queue["id"]),
                    exclude_recording_ids=_held_out_ids(conn))}
    finally:
        conn.close()


@router.post("/queues/{qid}/extract")
def post_extract(request: Request, qid: str, body: ExtractBody):
    """Resolve a catalogued sequence into the singular events it claims.

    Each event becomes a NEW annotation linked to the sequence's own span
    through `parent_annotation_id`; `complete` clears `needs_extraction` so the
    item can leave the queue; one gesture is one audit row. All of that is the
    core's (`Working.review.extraction`) — this route only carries it.
    """
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        _refuse_held_out(conn, queue, [body.sequence_id])
        out = _core_call(
            extraction_mod.extract_events, conn, int(queue["id"]),
            body.sequence_id,
            [{"start_idx": e.start_idx, "end_idx": e.end_idx}
             for e in body.events],
            complete=bool(body.complete))
        out["counts"] = queues_mod.queue_counts(conn, int(queue["id"]))
        return out
    finally:
        conn.close()
