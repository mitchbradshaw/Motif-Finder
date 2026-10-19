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
`OtherChannelRow`), built from real rows — and real decimated mV (converted from the
stored unit at `corpus.display_channel`, fixup-b) read off the
channel memmap through ``decimate.envelope``, never a synthesised trace
(rule 4: the bulk array never enters the database and never reaches the
client whole). Every trace is served WITH its time axis (fixup-g, U1/U2/U3):
`t` beside `v`, the window's edges, the sample count and the point count, sized
to the `px` the card measured — see `_trace_env`.

Loud failure is structural (CLAUDE.md, "Web UI"): nothing here catches an
error into a blank or an empty list. An unknown queue is a 404, a held-out
recording is a `refused` string on an otherwise empty item, and anything
unexpected raises and is turned into a 500 with the traceback by the app's
handler.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import sqlite3
import threading

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

#: Trace widths (fixup-g). `decimate.envelope` emits about 2*px points, and
#: `px` now comes from the CLIENT — the width of the card that will draw the
#: trace, measured with `charts/useSize.ts` — so a plot is never served fewer
#: points than it has pixels. `CONTEXT_PX = 320` and `SHAPE_PX = 60` were
#: constants that never saw the card: the ~816 px context card was served 440
#: points for 660 samples, and a 3600 s candidate got 120 points over ~380 px.
#: `DEFAULT_PX` is what a client that measured nothing gets; `MAX_PX` bounds the
#: payload (about 2*4096 points, ~130 KB), and a trace that hit it says so
#: (`capped: true`) rather than silently.
CONTEXT_PAD_S = 300           # the default; the client sends the pad it shows
DEFAULT_PX = 1200
MAX_PX = 4096
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


def _is_held_out(conn, source_file) -> bool:
    """The held-out recording, while Settings › Datasets' lock is on (a2-p1: read now; it used to answer by
    the name alone, whatever the lock said). The name is checked first, so no other file costs a read."""
    text = str(source_file or "").replace("\\", "/")
    base = os.path.basename(text)
    return (HELD_OUT_FILE in text or base.startswith(HELD_OUT_STEM)) and corpus.held_out_locked(conn)


def refusal(label: str) -> str:
    """The refusal the fixture serves (`api/review.ts`), and since a2-p1 how to unlock: it is only ever
    served while the lock is on."""
    return (f"{label} is held out (D6): it is locked for the final evaluation "
            f"and cannot be reviewed, plotted or queued — {corpus.HELD_OUT_UNLOCK_HINT}.")


def rec_key(source_file) -> str:
    stem = os.path.splitext(os.path.basename(str(source_file or "")))[0]
    return stem.replace("_concat", "")


def rec_label(conn, source_file) -> str:
    """What the dataset is called: the bridge's one naming seam (fixup-f). It
    used to prettify the file name here (`M2_aug fs1`), a second fallback."""
    return corpus.dataset_name(conn, source_file)


def _index(conn) -> dict:
    """`recording_id -> {...}`. One pass; every read below shares it."""
    out = {}
    for g in corpus.recordings(conn):
        for ch in g["channels"]:
            out[int(ch["id"])] = {
                "recording_id": int(ch["id"]), "source_file": g["source_file"],
                "label": g["display_name"], "channel": int(ch["channel"]),
                "name": ch["name"], "fs": float(g["fs"]), "n_samples": int(g["n_samples"]),
                "held_out": bool(g.get("held_out") or _is_held_out(conn, g["source_file"])),
            }
    return out


def _empty_trace(reason: str | None = None) -> dict:
    """A trace that draws nothing. The client draws nothing rather than a
    synthesised shape, because a synthetic trace beside a real one is a
    finding that is not there."""
    return {"t": [], "v": [], "t0_s": 0.0, "t1_s": 0.0, "fs": None, "n_source": 0,
            "n_points": 0, "decimated": False, "px": 0, "capped": False, "unit": None,
            "source": None, "reason": reason}


def _clamp_px(px) -> int:
    try:
        px = int(px)
    except (TypeError, ValueError):
        px = DEFAULT_PX
    return max(8, min(MAX_PX, px if px > 0 else DEFAULT_PX))


def _source_of(row: dict, *, kind: str = "self", decimation=None, offset=None) -> dict:
    """Which recording a trace was drawn from, and at what rate — the card has
    to say it, because "this event looks smooth" means something different at
    1 Hz and at 10 Hz (Q24)."""
    return {"recording_id": int(row["id"]), "label": rec_key(row["source_file"]),
            "source_file": os.path.basename(str(row["source_file"])),
            "channel": _channel_label({"source_file": row["source_file"], "name": row.get("name")}, {}),
            "fs": float(row["fs"] or 1.0), "n_samples": int(row["n_samples"] or 0),
            "kind": kind, "decimation": decimation, "offset": offset}


def _trace_env(row: dict | None, start_idx: int, end_idx: int, px_req, *, t_shift_s: float = 0.0,
               source: dict | None = None) -> dict:
    """Decimated mV for `[start_idx, end_idx)` of a recordings row, WITH its
    time axis: `t` (seconds, absolute in the recording — or shifted by
    `t_shift_s` into another recording's seconds) beside `v`, plus where the
    window sits (`t0_s`/`t1_s`, the window's own edges), how many samples it
    had and how many points it got, and whether the point budget was capped.

    The old contract — "the client's traces are values, the x axis is implied"
    — WAS the U2 defect: `decimate.envelope` returns fewer, non-uniformly
    spaced points once the window exceeds 2*px, and a client drawing them one
    per sample compressed everything right of `t0` by n_points/n_source while
    it drew the highlight band in true seconds. Band and trace on two axes.

    A channel whose `.npy` is missing yields an empty trace; so does a
    recording whose unit is undeclared (Review's axes say mV, and a stored
    number of unknown unit drawn on them would be the fixup-b error again).
    Converted at the one seam, `corpus.display_channel`.
    """
    if not row:
        return _empty_trace("no recording")
    path = row.get("npy_path")
    if not path or not os.path.isfile(path):
        return _empty_trace(f"the channel file for {rec_key(row['source_file'])} is missing")
    x = corpus.display_channel(row)
    if x.unit is None:
        return _empty_trace(f"{rec_key(row['source_file'])} declares no unit; nothing is drawn as mV")
    fs = float(row["fs"] or 1.0)
    px = _clamp_px(px_req)
    start_idx = max(0, int(start_idx))
    end_idx = max(start_idx, min(int(len(x)), int(end_idx)))
    env = decimate.envelope(x, fs, start_idx, end_idx, px)
    try:
        asked = int(px_req)
    except (TypeError, ValueError):
        asked = px
    return {
        "t": [round(float(a) + t_shift_s, 4) for a in env["t"]],
        "v": [None if a is None else round(float(a), 4) for a in env["v"]],
        "t0_s": round(start_idx / fs + t_shift_s, 4),
        "t1_s": round(end_idx / fs + t_shift_s, 4),
        "fs": fs,
        "n_source": int(env["n_source"]), "n_points": int(env["n_points"]),
        "decimated": bool(env["decimated"]),
        "px": px,
        # capped: the client asked for more width than the payload bound allows
        # AND the window had more samples than the bound serves — points were lost
        "capped": bool(asked > MAX_PX and env["decimated"]),
        "unit": x.unit,
        "source": source or _source_of(row),
        "reason": None,
    }


def _row_for(conn, rec: dict | None) -> dict | None:
    return corpus.recording_row(conn, int(rec["recording_id"])) if rec else None


NO_SOURCE = "no higher-resolution source is registered for this recording"


def _shape_source(conn, row: dict | None, start_idx: int, end_idx: int, px_req):
    """The Shape card's higher-resolution source, when one is registered
    (Q24, default ON in the client): `recordings.parent_recording_id`,
    `parent_offset` (in the parent's samples) and `decimation` link an excerpt
    to the channel it was block-mean decimated from — recording 385 is a 10:1
    decimation of `L_LM_Jul_26_J_raw` at 10 Hz, and Review had been judging
    event shape on a tenth of the detail that exists.

    Returns `(trace, None)` or `(None, reason)`. The trace is the parent's
    samples over the SAME window, in the CHILD's seconds (shifted by
    -offset/fs_parent) so it lines up with the context card, at the parent's
    own rate, converted through `corpus.display_channel` — the parent is a
    different recordings row with its own `units`, and a parent read raw would
    be 1000x out for a volts file. When there is no parent the answer is an
    explicit reason, never an inert toggle.
    """
    if not row:
        return None, NO_SOURCE
    pid = row.get("parent_recording_id")
    if not pid:
        return None, NO_SOURCE
    prow = corpus.recording_row(conn, int(pid))
    if prow is None:
        return None, f"the registered source recording {pid} no longer exists"
    if prow.get("held_out") or _is_held_out(conn, prow.get("source_file")):
        return None, refusal(rec_label(conn, prow["source_file"]))
    dec = int(row.get("decimation") or 0)
    off = int(row.get("parent_offset") or 0)
    if dec <= 0:
        return None, f"the link to {rec_key(prow['source_file'])} records no decimation factor"
    fs_c = float(row["fs"] or 1.0)
    fs_p = float(prow["fs"] or 1.0)
    if abs(fs_p - dec * fs_c) > 1e-6 * max(1.0, fs_p):
        return None, (f"{rec_key(prow['source_file'])} runs at {fs_p:g} Hz, which is not "
                      f"{dec} x this recording's {fs_c:g} Hz")
    j0 = off + int(start_idx) * dec
    j1 = off + int(end_idx) * dec
    tr = _trace_env(prow, j0, j1, px_req, t_shift_s=-off / fs_p,
                    source=_source_of(prow, kind="parent", decimation=dec, offset=off))
    if not tr["v"]:
        return None, tr.get("reason") or f"{rec_key(prow['source_file'])} could not be drawn"
    return tr, None


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


def _queue_payload(conn, q: dict, *, exclude_recording_ids=None, counts=None, filters=True,
                   detections=None) -> dict:
    """The stored queue columns plus its counts. The client derives icon,
    order text and rank kind from `source_kind`; nothing is invented here.

    AR (the speed pass): `counts` is passed in by a caller that already holds
    them (one resolve per request, not one per reader). `filters_json` is not
    served — it is `filters` again as a string, and a Discovery picked queue's
    filter is its whole detection list (10,000 ids twice over in every queue
    header). `filters=False` leaves the list itself out too: an item's queue
    header is read on every step and nothing on the item card reads it; the
    queue listing still carries it."""
    if counts is None:
        counts = q.get("counts") or queues_mod.queue_counts(
            conn, int(q["id"]),
            exclude_recording_ids=(exclude_recording_ids
                                   if exclude_recording_ids is not None
                                   else _held_out_ids(conn)))
    out = {k: v for k, v in q.items() if k != "filters_json" and (filters or k != "filters")}
    out["id"] = int(q["id"])
    out.update({"total": int(counts.get("total", 0)),
                "judged": int(counts.get("judged", 0)),
                "remaining": int(counts.get("remaining", 0)),
                # measured off `review_audit`, None until there are two
                # gestures to measure between (fixup-a item 8)
                "pace_s": queues_mod.queue_pace_s(conn, int(q["id"]))})
    # review-carry: a detection queue's item is an overlap set, so `total` counts events; `detections` is how many
    # detections stand behind them ("312 events from 340 detections"). Passed in by a caller that holds it.
    if detections is None:
        detections = q.get("detections")
    if detections is not None:
        out["detections"] = int(detections)
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


#: AR (the speed pass): a thumbnail is a function of the channel file, its unit and rate, and the span — none of
#: which a verdict changes — so it is kept, keyed on exactly those (the file by path and mtime, so a re-derived
#: channel is read again). A 10,000-row queue drew 10,000 thumbnails on every read, each with two queries and a
#: settings read for its recording row (26 s on the scale fixture). Bounded: an entry is a tuple of ~48 floats,
#: ~1.8 KB with its key, so 20,000 entries (two 10,000-item queues' rails) are ~36 MB (fix round S4: the first cap
#: of 100,000 was ~180 MB, not the ~50 MB its comment claimed).
_THUMB_CACHE: "OrderedDict" = None  # type: ignore[assignment]
_THUMB_CACHE_MAX = 20_000
_THUMB_LOCK = threading.Lock()


def _thumb_source(conn, rec: dict, memo: dict | None):
    """(recording row, cache key prefix) for one recording, once per request when the caller passes a memo."""
    rid = int(rec["recording_id"])
    if memo is not None and rid in memo:
        return memo[rid]
    row = _row_for(conn, rec)
    prefix = None
    if row and row.get("npy_path"):
        try:
            prefix = (row["npy_path"], os.stat(row["npy_path"]).st_mtime_ns, row.get("units"), float(row["fs"] or 1.0))
        except OSError:
            prefix = None                       # missing: drawn empty with its reason, never kept
    got = (row, prefix)
    if memo is not None:
        memo[rid] = got
    return got


def _thumb(conn, item: dict, rec: dict | None, unit: str, memo: dict | None = None) -> list:
    """A queue row's thumbnail: a bare value list (a sparkline with nothing drawn beside it, so there is no
    second coordinate system to disagree with). fixup-ah: a blind test queue's rows carry none — a sparkline
    list would let the eye find the window shown twice (and its first answer) before the card is read."""
    global _THUMB_CACHE
    if (rec or {}).get("held_out") or unit == "test window":
        return []
    start = int(item.get("start_idx") or 0)
    end = int(item.get("end_idx") or start)
    if not rec:
        return _trace_env(None, start, end, THUMB_PX)["v"]
    row, prefix = _thumb_source(conn, rec, memo)
    if prefix is None:
        return _trace_env(row, start, end, THUMB_PX)["v"]
    key = prefix + (start, end)
    with _THUMB_LOCK:
        if _THUMB_CACHE is None:
            from collections import OrderedDict
            _THUMB_CACHE = OrderedDict()
        hit = _THUMB_CACHE.get(key)
        if hit is not None:
            _THUMB_CACHE.move_to_end(key)
            return list(hit)
    v = _trace_env(row, start, end, THUMB_PX)["v"]
    with _THUMB_LOCK:
        _THUMB_CACHE[key] = tuple(v)
        while len(_THUMB_CACHE) > _THUMB_CACHE_MAX:
            _THUMB_CACHE.popitem(last=False)
    return v


def baseline_peak(values) -> float:
    """`charts/domain.ts::baselinePeak`, the same arithmetic: a trace's largest deviation from its own median,
    over its finite values. The Shape card's queue-wide reference bar is drawn from every row's, and since rows
    no longer carry their thumbnails (AR) the bridge sends the two ends of that range (`thumbPeaks`)."""
    finite = [float(v) for v in (values or ()) if v is not None and math.isfinite(float(v))]
    if not finite:
        return 0.0
    s = sorted(finite)
    n = len(s)
    mid = s[(n - 1) // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    return max(abs(v - mid) for v in finite)


def _entry_payload(conn, item: dict, queue: dict, index: dict, *, px: int = THUMB_PX,
                   rank: int | None = None, thumb: bool = True, memo: dict | None = None) -> dict:
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
    # fixup-f: the label is what the dataset is CALLED; the file is carried beside it (hover, provenance)
    # and is what anything that has to recognise the recording keys on — never the label
    row["recordingFile"] = (rec or {}).get("source_file")
    row["heldOut"] = bool((rec or {}).get("held_out"))
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
    # the thumbnail stays a bare value list: it is a sparkline with nothing
    # drawn beside it, so there is no second coordinate system to disagree with
    # fixup-ah: a blind test queue's rows carry no thumbnail — a sparkline list would let the eye find the window
    # shown twice (and its first answer) before the card is read
    # AR: `thumb=False` serves the row without it (`thumbsServed: false` on the read); `/thumbs` pages them
    row["thumb"] = _thumb(conn, item, rec, row["unit"], memo) if thumb else []
    row["family"] = str(item.get("family") or "")
    # The run that wrote this detection, and where the item sits in the queue.
    # Without them the inspector subtitle read "run undefined - rank undefined"
    # on every item: `review_queues.source_ref` is NULL whenever the queue's
    # filters name the run instead, and nothing computed a rank at all
    # (fixup-a item 7). Absent stays absent - the subtitle omits the clause.
    if item.get("run_id") is not None:
        row["runId"] = str(item["run_id"])
    if rank is not None:
        row["rank"] = int(rank)
    # review-carry: the overlap set behind a detection item — each member's band in the same seconds as the
    # context trace's axis (absolute in the recording), for the context card; the class label stored with the
    # verdict (R3); and, for a carried verdict, the detection whose human verdict it was carried from
    if item.get("members") is not None and item.get("member_spans") is not None:
        row["memberBands"] = [{"id": str(m), "t0_s": round(a / fs, 6), "t1_s": round(b / fs, 6)}
                              for m, (a, b) in zip(item["members"], item["member_spans"])]
    if item.get("class_label"):
        row["classLabel"] = item["class_label"]
    if item.get("carried_from_detection") is not None:
        row["carriedFrom"] = int(item["carried_from_detection"])
    return row


def _item_or_404(conn, queue: dict, item_id: str, held=None) -> dict:
    """`queues.item_view` for this item: the item, INCLUDING ones the default
    listing filters out, its position in the served list and the queue's counts.

    A rediscovery is excluded from the queue's rows on purpose, but a deep link
    to it must still open — "there must be a way to see what was auto-excluded"
    is the whole point of `include_prior_judged`.

    AR (the speed pass): one read of the queue's remembered structure, where it
    used to resolve the whole queue once to find the item and again to number it.
    """
    view = queues_mod.item_view(conn, int(queue["id"]), item_id,
                                exclude_recording_ids=_held_out_ids(conn) if held is None else held)
    if view["item"] is None:
        raise HTTPException(status_code=404, detail=f"no item {item_id!r} in queue {queue['id']}")
    return view


def _detail(conn, queue: dict, item: dict, index: dict, *, rank: int | None = None,
            px=DEFAULT_PX, pad_s=CONTEXT_PAD_S, counts=None, detections=None) -> dict:
    """The `ItemDetail` shape, key for key.

    `px` is the width of the plot that will draw the traces and `pad_s` the
    padding the context card is showing — both from the client, so the context
    is served over exactly the window drawn, symmetric about the candidate
    (U3: the client used to slice envelope points as though they were seconds),
    and at a resolution the card can use (fixup-g)."""
    rid = item.get("recording_id")
    rec = index.get(int(rid)) if rid is not None else None
    qp = _queue_payload(conn, queue, counts=counts, filters=False, detections=detections)
    entry = _entry_payload(conn, item, queue, index, rank=rank)
    if rec and rec["held_out"]:
        why = refusal(rec["label"])
        return {"entry": entry, "queue": qp, "context": _empty_trace(why),
                "shape": _empty_trace(why), "shapeSource": None, "shapeSourceReason": why,
                "nearest": [], "nearestComputed": False,
                "medoids": {}, "artifact": _artifact(item),
                "evidence": None, "thumb": [], "refused": why}

    start = int(item.get("start_idx") or 0)
    end = int(item.get("end_idx") or start)
    fs = float((rec or {}).get("fs") or 1.0)
    try:
        pad_s = max(0, int(pad_s))
    except (TypeError, ValueError):
        pad_s = CONTEXT_PAD_S
    pad = int(round(pad_s * fs))
    c0 = max(0, start - pad)
    c1 = min(int((rec or {}).get("n_samples") or end + pad), end + pad)
    row = _row_for(conn, rec)
    source, source_reason = _shape_source(conn, row, start, end, px)
    return {
        "entry": entry,
        "queue": qp,
        "context": _trace_env(row, c0, c1, px),
        "shape": _trace_env(row, start, end, px),
        "shapeSource": source,
        "shapeSourceReason": source_reason,
        "nearest": list(item.get("nearest") or []),
        "nearestComputed": bool(item.get("nearest_computed")),
        "medoids": dict(item.get("medoids") or {}),
        "artifact": _artifact(item),
        "evidence": _evidence(item, qp),
        "thumb": entry["thumb"],
        # keyed on the KIND, not the unit: a Library family queue's items are members too, and
        # carry no flags to draw (fixup-FQ)
        **({"suspectedArtifact": _suspected_artifact(conn, item, rec, index, px, pad_s)}
           if queue.get("source_kind") == "suspected-artifact" else {}),
    }


def _suspected_artifact(conn, item: dict, rec: dict, index: dict, px: int, pad_s: int) -> dict:
    """fixup-AD: a *Suspected artifact* card — every channel of the recording
    over the member's span plus padding, in true mV on ONE shared axis (the
    client draws them on one y), the member's channel marked, each flagging
    sibling's r, lag, amplitude ratio and chance percentile printed beside it
    (`webui/screenshots/fixup/Q40d/examples_gallery_mV.png`)."""
    start, end = int(item["start_idx"]), int(item["end_idx"])
    fs = float(rec["fs"] or 1.0)
    pad = max(end - start, 10)          # one span each side, as the Q40d gallery draws it
    c0, c1 = max(0, start - pad), min(int(rec["n_samples"]), end + pad)
    flags = {int(f["recording_id"]): f for f in item.get("flags") or []}
    channels = []
    for other in sorted((o for o in index.values() if o["source_file"] == rec["source_file"]),
                        key=lambda o: o["channel"]):
        f = flags.get(other["recording_id"])
        channels.append({
            "recording_id": other["recording_id"], "channel": other["name"], "channel_index": other["channel"],
            "member": other["recording_id"] == rec["recording_id"], "flagging": f is not None,
            "r": f.get("r") if f else None, "lag_s": f.get("lag_s") if f else None,
            "amplitude_ratio": f.get("amplitude_ratio") if f else None,
            "chance": f.get("chance") if f else None, "other_member": (f"m-{f['other_member']}"
                                                                       if f and f.get("other_member") else None),
            "trace": _trace_env(_row_for(conn, other), c0, c1, px),
        })
    units = {c["trace"].get("unit") for c in channels if c["trace"].get("unit")}
    return {"member": f"m-{item['member_id']}", "family": item.get("family"),
            "t0_s": c0 / fs, "t1_s": c1 / fs, "span_s": [start / fs, end / fs],
            "unit": units.pop() if len(units) == 1 else None, "shared_axis": True,
            "channels": channels, "note": (item.get("artifact") or {}).get("reason"),
            "verdictNote": ("answer artifact, or what the span really is (interesting / not_interesting), or unsure; "
                            "the row carries a note that it was flagged as a suspected artifact")}


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
            # `source_ref` is NULL on a queue whose filters name the run; the
            # item knows which run wrote it either way (fixup-a item 7)
            "runKind": queue.get("source_kind"),
            "runId": queue.get("source_ref") if queue.get("source_ref") is not None else item.get("run_id"),
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
    what a held-out file is while the counts still agree with the rows. Empty
    while Settings › Datasets' lock is off (a2-p1): one settings read, then none.
    """
    if not corpus.held_out_locked(conn):
        return set()
    return {int(r["id"]) for r in conn.execute(
        "SELECT id, source_file FROM recordings").fetchall()
        if _is_held_out(conn, r["source_file"])}


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
        "member": "SELECT recording_id FROM motif_member WHERE id = ?",
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
    # review-carry (R3): the class key's name (spike-train, burst, ...), stored on a detection's adjudication row
    class_label: str | None = None


class BatchBody(BaseModel):
    target_ids: list[str | int]
    verdict: str
    note: str | None = None
    tags: list[str] | None = None
    class_label: str | None = None


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
        held = _held_out_ids(conn)
        out = []
        # AR: one count per queue, with the held-out set (it was counted twice, once without it)
        for q in queues_mod.list_queues(conn, include_closed=bool(include_closed), exclude_recording_ids=held):
            counts = {k: q[k] for k in ("total", "judged", "remaining")}
            out.append(_queue_payload(conn, q, counts=counts, detections=q.get("detections")))
        return out
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
              include_prior_judged: int = Query(default=0), thumbs: int = Query(default=1)):
    """The queue's rows. `thumbs=0` (AR, the speed pass) serves them without their thumbnails — a trace per row
    is most of this read's cost (26 s for 10,000 rows on the scale fixture) — and says so (`thumbsServed`); the
    page then asks `/thumbs` for the rows it shows. Everything else on a row is what `thumbs=1` serves."""
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        index = _index(conn)
        held = _held_out_ids(conn)
        resolved = queues_mod.queue_view(conn, int(queue["id"]))
        served = queues_mod.select_items(queue, resolved, include_judged=True, exclude_recording_ids=held)
        items = queues_mod.select_items(queue, resolved, include_judged=bool(include_judged),
                                        include_prior_judged=bool(include_prior_judged),
                                        exclude_recording_ids=held)
        ranks = {str(it.get("target_id", it.get("id"))): i + 1 for i, it in enumerate(served)}
        memo: dict = {}
        rows = [_entry_payload(conn, it, queue, index, rank=ranks.get(str(it.get("target_id", it.get("id")))),
                               thumb=bool(thumbs), memo=memo)
                for it in items]
        # the Shape card's queue-wide reference bar: the smallest positive and the largest row peak, from every
        # row's thumbnail (`referenceScale` reads only those two ends). A rows-only read draws NO thumbnail (fix
        # round B1: it drew all of them to find the two ends, 13-27 s on the first open after a restart): it serves
        # the ends when they are already known for exactly these rows, else null, and `/peaks` works them out
        pkey = _peaks_key(conn, items, rows, index, memo)
        if thumbs:
            got = _peaks_of(row["thumb"] for row in rows if not row.get("heldOut"))
            with _THUMB_LOCK:
                _keep_peaks(pkey, got)
        else:
            with _THUMB_LOCK:
                got = _PEAKS.get(pkey)
        detections = (sum(len(it.get("members") or ()) for it in served)
                      if queue.get("source_kind") in queues_mod.CLUSTERLESS_KINDS else None)
        return {"queue": _queue_payload(conn, queue, counts=queues_mod.counts_of(served), detections=detections),
                "rows": rows, "clusters": _clusters(items, queue), "thumbsServed": bool(thumbs),
                "thumbPeaks": got}
    finally:
        conn.close()


#: fix round B1: the two ends of a row set's thumbnail peaks, keyed by exactly the rows (recording file, span,
#: unit) they were drawn from; `None` in a payload means "not worked out yet"
_PEAKS: dict = {}
_PEAKS_INFLIGHT: set = set()


def _keep_peaks(pkey, got):
    """Under `_THUMB_LOCK`. Bounded: a key per row set read, a few hundred at most in a session."""
    if len(_PEAKS) >= 512:
        _PEAKS.clear()
    _PEAKS[pkey] = got


def _peaks_of(thumbs) -> list:
    peaks = [p for p in (baseline_peak(v) for v in thumbs) if p > 0]
    return [min(peaks), max(peaks)] if peaks else []


def _peaks_key(conn, items, rows, index, memo):
    """What the peak range is a function of: every shown row's recording file (path, mtime, unit, rate), span and
    unit. Two reads of the same rows share it; a re-derived channel or a changed set does not."""
    parts = []
    for it, row in zip(items, rows):
        if row.get("heldOut"):
            continue
        rid = it.get("recording_id")
        rec = index.get(int(rid)) if rid is not None else None
        prefix = _thumb_source(conn, rec, memo)[1] if rec else None
        parts.append((prefix, int(it.get("start_idx") or 0), int(it.get("end_idx") or 0), row["unit"]))
    return hash(tuple(parts))


def _work_out_peaks(db_path, qid, include_judged, include_prior_judged, pkey):
    """Draw the rows' thumbnails (into `_THUMB_CACHE`) and keep the peak range: run in the background by `/peaks`,
    so the rows read itself never waits on it."""
    log = logging.getLogger("webui.review")
    try:
        conn = corpus.connect(db_path)
        try:
            queue = queues_mod.get_queue(conn, int(qid))
            index, held, memo = _index(conn), _held_out_ids(conn), {}
            items = queues_mod.select_items(queue, queues_mod.queue_view(conn, int(qid)),
                                            include_judged=include_judged, include_prior_judged=include_prior_judged,
                                            exclude_recording_ids=held)
            thumbs = []
            for it in items:
                rid = it.get("recording_id")
                rec = index.get(int(rid)) if rid is not None else None
                if rec and rec.get("held_out"):
                    continue
                thumbs.append(_thumb(conn, it, rec, queue.get("unit") or it.get("unit") or "detection", memo))
            with _THUMB_LOCK:
                _keep_peaks(pkey, _peaks_of(thumbs))
        finally:
            conn.close()
    except Exception:
        log.exception("working out the thumbnail peaks of queue %s failed", qid)
    finally:
        with _THUMB_LOCK:
            _PEAKS_INFLIGHT.discard(pkey)


@router.get("/queues/{qid}/peaks")
def get_peaks(request: Request, qid: str, include_judged: int = Query(default=1),
              include_prior_judged: int = Query(default=0), wait_s: float = Query(default=0.0)):
    """Fix round B1: the Shape card's reference-bar ends for the rows `GET /queues/{qid}` serves with the same
    parameters — `{"thumbPeaks": [lo, hi] | [] | null, "ready": bool}`. Not known yet: the work is started in the
    background (once) and `ready` is false; the page asks again. `wait_s` (tests) waits up to that long for it."""
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        index, held, memo = _index(conn), _held_out_ids(conn), {}
        items = queues_mod.select_items(queue, queues_mod.queue_view(conn, int(queue["id"])),
                                        include_judged=bool(include_judged),
                                        include_prior_judged=bool(include_prior_judged), exclude_recording_ids=held)
        rows = [{"heldOut": bool((index.get(int(it["recording_id"])) or {}).get("held_out"))
                 if it.get("recording_id") is not None else False,
                 "unit": queue.get("unit") or it.get("unit") or "detection"} for it in items]
        pkey = _peaks_key(conn, items, rows, index, memo)
    finally:
        conn.close()
    with _THUMB_LOCK:
        got = _PEAKS.get(pkey)
        start = got is None and pkey not in _PEAKS_INFLIGHT
        if start:
            _PEAKS_INFLIGHT.add(pkey)
    if start:
        threading.Thread(target=_work_out_peaks, name=f"queue-peaks-{qid}", daemon=True,
                         args=(request.app.state.rt.db_path, int(queue["id"]), bool(include_judged),
                               bool(include_prior_judged), pkey)).start()
    if got is None and wait_s > 0:
        import time as _time
        t0 = _time.monotonic()
        while _time.monotonic() - t0 < min(float(wait_s), 120.0):
            with _THUMB_LOCK:
                got = _PEAKS.get(pkey)
            if got is not None:
                break
            _time.sleep(0.05)
    return {"thumbPeaks": got, "ready": got is not None}


@router.get("/queues/{qid}/thumbs")
def get_thumbs(request: Request, qid: str, ids: str = Query(default="")):
    """AR: the thumbnails of the rows the page is showing, `{id: [values]}` — the same list a `thumbs=1` row
    carries. An id that is not in the queue is a 404 naming it, never an empty thumbnail (an empty one draws as
    a flat line, which is a shape)."""
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        want = [i for i in (x.strip() for x in ids.split(",")) if i][:200]
        index = _index(conn)
        held = _held_out_ids(conn)
        out, memo = {}, {}
        found = queues_mod.item_views(conn, int(queue["id"]), want, exclude_recording_ids=held)
        missing = [t for t in want if found.get(t) is None]
        if missing:
            raise HTTPException(status_code=404, detail=f"no item {missing[0]!r} in queue {queue['id']}")
        for tid in want:
            item = found[tid]
            rid = item.get("recording_id")
            rec = index.get(int(rid)) if rid is not None else None
            out[tid] = _thumb(conn, item, rec, queue.get("unit") or item.get("unit") or "detection", memo)
        return {"thumbs": out}
    finally:
        conn.close()


@router.get("/queues/{qid}/counts")
def get_queue_counts(request: Request, qid: str):
    """AR: the queue's counts and pace — what the toolbar and the queue list re-read after a verdict, in place of
    every row."""
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        held = _held_out_ids(conn)
        counts = queues_mod.queue_counts(conn, int(queue["id"]), exclude_recording_ids=held)
        out = {"id": int(queue["id"]), **{k: int(counts[k]) for k in ("total", "judged", "remaining")},
               "pace_s": queues_mod.queue_pace_s(conn, int(queue["id"]))}
        detections = queues_mod.served_detections(conn, int(queue["id"]), exclude_recording_ids=held)
        if detections is not None:          # review-carry: the detections behind the events
            out["detections"] = int(detections)
        return out
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
def get_item(request: Request, qid: str, item_id: str,
             px: int = Query(default=DEFAULT_PX), pad_s: int = Query(default=CONTEXT_PAD_S)):
    """`px`: the width of the plot that will draw the traces; `pad_s`: the
    context padding shown. Both come from the card (fixup-g)."""
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        view = _item_or_404(conn, queue, item_id)
        return _detail(conn, queue, view["item"], _index(conn), rank=view["rank"],
                       px=px, pad_s=pad_s, counts=view["counts"], detections=view.get("detections"))
    finally:
        conn.close()


@router.get("/queues/{qid}/items/{item_id}/channels")
def get_item_channels(request: Request, qid: str, item_id: str,
                      px: int = Query(default=DEFAULT_PX), pad_s: int = Query(default=CONTEXT_PAD_S)):
    """The other channels of the same recording over the item's window, each
    as a trace WITH its axis (`trace`), over the same padded window as the
    context card (the popover's band is drawn in the same seconds)."""
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        item = _item_or_404(conn, queue, item_id)["item"]
        index = _index(conn)
        rid = item.get("recording_id")
        rec = index.get(int(rid)) if rid is not None else None
        if not rec or rec["held_out"]:
            return []
        start = int(item.get("start_idx") or 0)
        end = int(item.get("end_idx") or start)
        fs = float(rec["fs"] or 1.0)
        pad = int(round(max(0, int(pad_s)) * fs))
        out = []
        for other in index.values():
            if other["source_file"] != rec["source_file"]:
                continue
            out.append({"channel": other["name"], "r": None,
                        "trace": _trace_env(_row_for(conn, other), max(0, start - pad),
                                            min(other["n_samples"], end + pad), px),
                        "current": other["recording_id"] == rec["recording_id"]})
        return out
    finally:
        conn.close()


@router.get("/queues/{qid}/cluster/{no}")
def get_cluster(request: Request, qid: str, no: int,
                px: int = Query(default=DEFAULT_PX), pad_s: int = Query(default=CONTEXT_PAD_S)):
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        index = _index(conn)
        if queue.get("source_kind") in queues_mod.CLUSTERLESS_KINDS:      # AR S6: nothing to resolve to find none
            raise HTTPException(status_code=404, detail=_no_clusters(queue, no))
        items = queues_mod.queue_items(conn, int(queue["id"]), include_judged=True)
        clusters = _clusters(items, queue)
        cluster = next((c for c in clusters if int(c["no"]) == int(no)), None)
        if cluster is None:
            raise HTTPException(status_code=404,
                                detail=_no_clusters(queue, no))
        members = [it for it in items
                   if str(it.get("target_id", it.get("id"))) in cluster["members"]]
        # AR: the queue's counts once for the page, not once more per member card
        counts = queues_mod.queue_counts(conn, int(queue["id"]), exclude_recording_ids=_held_out_ids(conn))
        return {"cluster": cluster, "queue": _queue_payload(conn, queue, counts=counts),
                "members": [_detail(conn, queue, it, index, px=px, pad_s=pad_s, counts=counts) for it in members]}
    finally:
        conn.close()


# ── writes (every one through Working.review) ───────────────────────────────

def _carry_free(result: dict) -> dict:
    """The verdict record without its per-member audit detail (`targets`: each member's prior and what it carried,
    which the core keeps for undo and promotion); everything else as the core returned it."""
    return {k: v for k, v in result.items() if k != "targets"}


@router.post("/queues/{qid}/verdict")
def post_verdict(request: Request, qid: str, body: VerdictBody):
    conn = _conn(request)
    try:
        queue = _queue_or_404(conn, qid)
        _refuse_held_out(conn, queue, [body.target_id])
        result = _core_call(verdicts_mod.write_verdict, conn, int(queue["id"]),
                            body.target_id, body.verdict, note=body.note,
                            tags=body.tags, window_index=body.window_index,
                            class_label=body.class_label)
        conn.commit()
        # review-carry: `carried` — how many other detections (other runs, same channel, the same event by the
        # scoreboard's rule) the verdict was written to; the page's toast says "carried to N other detections"
        carried = list(result.get("carried") or [])
        return {"verdict": _carry_free(result), "carried": len(carried), "carriedIds": carried,
                "counts": queues_mod.queue_counts(
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
                            tags=body.tags, class_label=body.class_label)
        conn.commit()
        carried = list(result.get("carried") or [])
        return {"batch": result, "carried": len(carried), "carriedIds": carried,
                "counts": queues_mod.queue_counts(
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
        if queue.get("source_kind") in queues_mod.CLUSTERLESS_KINDS:      # AR S6: nothing to resolve to find none
            raise HTTPException(status_code=404, detail=_no_clusters(queue, no))
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
