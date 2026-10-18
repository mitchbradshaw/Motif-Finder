"""Explore's live regions (stage-3 prompt 01, block 8): tags and reviewed
coverage from `annotation_tags` / `reviewed_spans`, the runs on a recording
with their methods (for the coverage filters), cross-channel from the real
sibling channels, and "Take span for Review" as an `annotations` row with
verdict `seed` through the rule-5 human door.
"""
from __future__ import annotations

import datetime as _dt
import json

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from Working.cross_channel import DETRENDS, FlatWindow, classify_waveforms, drift_suspect, rule_from_settings
from Working.database import queries as q
from Working.database.runs import list_runs, load_recipe
from Working.review import queues as queues_mod

from . import corpus
from .corpus import run_methods          # lives there so the fastapi-free coverage path can use it
from .writes import write_human

router = APIRouter()
CROSS_MAX_SAMPLES = 200_000


def _conn(request: Request):
    return corpus.connect(request.app.state.rt.db_path)


def _rec(request: Request, recording_id: int) -> dict:
    c = _conn(request)
    try:
        rec = corpus.recording_row(c, recording_id)
    finally:
        c.close()
    if rec is None:
        raise HTTPException(404, f"no recording id {recording_id}")
    if rec["held_out"]:          # a2-p1: true only while Settings › Datasets' lock is on (corpus.recording_row)
        raise HTTPException(423, corpus.held_out_refusal("the web UI refuses it"))
    return rec


@router.get("/api/corpus/{source_file}/runs")
def get_runs_for_file(request: Request, source_file: str):
    c = _conn(request)
    try:
        if corpus.is_held_out(c, source_file):          # a2-p1: only while the lock is on
            raise HTTPException(423, corpus.held_out_refusal("its runs are not listed"))
        runs = run_methods(c, source_file)
    finally:
        c.close()
    methods = sorted({r["method"] for r in runs})
    return {"source_file": source_file, "runs": runs, "methods": methods}


@router.get("/api/channels/{recording_id}/tags")
def get_tags(request: Request, recording_id: int, t0: float = 0.0, t1: float | None = None):
    rec = _rec(request, recording_id)
    fs = float(rec["fs"])
    if t1 is None:
        t1 = rec["duration_s"]
    s0, s1 = int(np.floor(t0 * fs)), int(np.ceil(t1 * fs))
    c = _conn(request)
    try:
        ann = c.execute(
            "SELECT a.id, a.start_idx, a.end_idx, a.verdict, a.tag, a.note, a.source FROM annotations a "
            "WHERE a.recording_id = ? AND a.deleted_at IS NULL AND a.end_idx > ? AND a.start_idx < ? ORDER BY a.start_idx LIMIT 5001",
            (recording_id, s0, s1)).fetchall()
        ids = [a["id"] for a in ann]
        tags_by = {}
        if ids:
            marks = ",".join("?" for _ in ids)
            for r in c.execute(f"SELECT t.annotation_id, v.category, v.value FROM annotation_tags t JOIN tag_vocabulary v ON v.id = t.tag_id "
                               f"WHERE t.annotation_id IN ({marks})", ids):
                tags_by.setdefault(r["annotation_id"], []).append({"category": r["category"], "value": r["value"]})
        reviewed = c.execute("SELECT id, start_idx, end_idx, scale_viewed, source, reviewed_at FROM reviewed_spans WHERE recording_id = ? "
                             "AND end_idx > ? AND start_idx < ? ORDER BY start_idx LIMIT 5001", (recording_id, s0, s1)).fetchall()
        ann_capped, rev_capped = len(ann) > 5000, len(reviewed) > 5000
        ann, reviewed = ann[:5000], reviewed[:5000]
        reviewed_frac = q.reviewed_fraction(c, recording_id)
        vocab = c.execute("SELECT id, category, value, description, active FROM tag_vocabulary WHERE active = 1 ORDER BY category, value").fetchall()
    finally:
        c.close()
    counts = {}
    for tl in tags_by.values():
        for t in tl:
            counts[f"{t['category']}:{t['value']}"] = counts.get(f"{t['category']}:{t['value']}", 0) + 1
    return {
        "recording_id": recording_id, "t0_s": t0, "t1_s": t1,
        "annotations": [{"id": a["id"], "start_s": a["start_idx"] / fs, "end_s": a["end_idx"] / fs, "verdict": a["verdict"],
                         "tag": a["tag"], "note": a["note"], "source": a["source"], "tags": tags_by.get(a["id"], [])} for a in ann],
        "reviewed": [{"id": r["id"], "start_s": r["start_idx"] / fs, "end_s": r["end_idx"] / fs, "scale": r["scale_viewed"],
                      "source": r["source"], "at": r["reviewed_at"]} for r in reviewed],
        "reviewed_pct": float(reviewed_frac) * 100.0,
        "tag_counts": counts,
        "vocabulary": [dict(v) for v in vocab],
        "annotations_capped": ann_capped, "reviewed_capped": rev_capped,
    }


@router.get("/api/channels/{recording_id}/siblings")
def get_siblings(request: Request, recording_id: int):
    rec = _rec(request, recording_id)
    c = _conn(request)
    try:
        rows = [dict(r) for r in q.list_recordings(c, rec["source_file"])]
    finally:
        c.close()
    n = len(rows)
    return {"recording_id": recording_id, "source_file": rec["source_file"],
            "channels": [{"id": r["id"], "channel": r["channel"], "name": corpus.channel_name(rec["source_file"], r["channel"], n),
                          "npy_exists": bool(r["npy_path"]) and __import__("os").path.isfile(r["npy_path"])} for r in rows]}


@router.get("/api/cross/{recording_id}")
def get_cross_channel(request: Request, recording_id: int, t0: float = 0.0, t1: float | None = None, px: int = 900,
                      detrend: str = "none"):
    """The same window on every channel of the recording, each with its lag and
    waveform correlation against the reference channel (`Working.cross_channel`).

    fixup-W: binned by the Settings rule in SECONDS (Q40b/Q-W5), with the lag
    converted at the rate of the arrays actually correlated — the window is
    strided past CROSS_MAX_SAMPLES, and the strided lag used to be compared
    against thresholds written in samples. The rule's words travel with the
    answer, so the page prints the rule that produced each bin.

    fixup-AQ: `detrend=linear` hands the core's classifier each channel's
    window with its straight-line trend taken out — ONE call per pair, whose
    lag, r and bin are the row's. Over a ten-minute window two drifting
    channels otherwise read r near ±1 at lag 0 on every pair (the screenshot of
    2026-10-13). The as-recorded call rides beside it as `as_recorded`, a
    diagnostic the page prints so the drift's reading is never hidden; it never
    bins the row. The default stays "none": an edge's window opened from
    Library › Family must recompute exactly what the edge stores, and the
    Library classifies members as recorded. `rules` are the window's words
    (`CrossChannelRule.describe_window`), which do not claim the chance test or
    the noise floor — this route runs neither.

    Fix round (2026-10-16): `detrend=cubic` is offered too; a detrended pair
    still reading |r| ≥ 0.9 near lag 0, as it did as recorded, carries
    `drift_suspect` (a curve the line left); a channel that is its trend and
    nothing else reads "undefined" with `undefined_reason`."""
    if detrend not in DETRENDS:
        raise HTTPException(422, f"detrend must be one of {', '.join(DETRENDS)}, got {detrend!r}")
    rec = _rec(request, recording_id)
    fs = float(rec["fs"])
    if t1 is None:
        t1 = min(rec["duration_s"], t0 + 3600.0)
    if not (0 <= t0 < t1 <= rec["duration_s"] + 1e-9):
        raise HTTPException(422, f"window must satisfy 0 <= t0 < t1 <= {rec['duration_s']:.0f} s")
    px_used = max(16, min(4000, px))
    # fixup-W: tolerant of a decimal second times fs landing a hair under the sample it names (322.6 s x 10 Hz is
    # 3225.9999…), so an edge's window opened from Library › Family is cut on exactly the samples it was measured on
    s0, s1 = int(np.floor(t0 * fs + 1e-6)), int(np.floor(t1 * fs + 1e-6))
    c = _conn(request)
    try:
        sibs = [dict(r) for r in q.list_recordings(c, rec["source_file"])]
        rule = rule_from_settings(c)
        # lag and r are scale-free and come from the core: it is handed the stored samples
        ref_x = np.asarray(corpus.load_native(rec["npy_path"])[s0:s1], dtype=float)
        stride = max(1, int(np.ceil(len(ref_x) / CROSS_MAX_SAMPLES)))
        ref_d = ref_x[::stride]
        out = []
        for r in sibs:
            row = corpus.recording_row(c, r["id"])
            if row is None or row["held_out"]:
                continue
            item = {"id": r["id"], "channel": r["channel"], "name": corpus.channel_name(rec["source_file"], r["channel"], len(sibs)),
                    "is_reference": r["id"] == recording_id, "lag_s": 0.0, "r": 1.0, "classification": "reference"}
            try:
                w = corpus.window(c, row, t0, t1, px_used)
                item["envelope"] = w["envelope"]; item["y_range"] = corpus.y_range(row); item["unit"] = w["unit"]
            except Exception as e:
                # the item still carries the reference's lag 0.0 / r 1.0 / "reference" defaults; leaving
                # them would draw an unreadable channel as a second reference row, perfectly correlated
                item["error"] = f"{type(e).__name__}: {e}"
                if r["id"] != recording_id:
                    item.update({"lag_s": None, "r": None, "classification": "undefined"})
                out.append(item); continue
            if r["id"] != recording_id:
                y = np.asarray(corpus.load_native(row["npy_path"])[s0:s1], dtype=float)[::stride]
                n = min(len(y), len(ref_d))
                if n >= 4 and np.isfinite(ref_d[:n]).all() and np.isfinite(y[:n]).all() and ref_d[:n].std() > 0 and y[:n].std() > 0:
                    if detrend != "none":
                        lag0, corr0, cls0 = classify_waveforms(ref_d[:n], y[:n], fs=fs / stride, rule=rule)
                        item["as_recorded"] = {"lag_s": float(lag0 * stride / fs), "r": float(corr0), "classification": cls0}
                    try:
                        lag, corr, cls = classify_waveforms(ref_d[:n], y[:n], fs=fs / stride, rule=rule, detrend=detrend)
                    except FlatWindow as e:
                        # fix round: a window that is its trend and nothing else has no lag or r — said, not dusted
                        item.update({"lag_s": None, "r": None, "classification": "undefined", "drift_suspect": False,
                                     "undefined_reason": f"one channel is {e}"})
                    else:
                        lag_s = float(lag * stride / fs)
                        item.update({"lag_s": lag_s, "r": float(corr), "classification": cls,
                                     # fix round: a curve the trend treatment left reads like a shared drift — a
                                     # mark beside the bin (Working.cross_channel.drift_suspect), never a bin
                                     "drift_suspect": bool(drift_suspect(lag_s, corr, item.get("as_recorded", {}).get("r"), rule))})
                else:
                    item.update({"lag_s": None, "r": None, "classification": "undefined", "drift_suspect": False,
                                 "undefined_reason": "a flat or non-finite trace in this window"})
            out.append(item)
    finally:
        c.close()
    return {"reference_id": recording_id, "source_file": rec["source_file"], "t0_s": t0, "t1_s": t1, "fs": fs,
            "stride": stride, "channels": out, "unit": corpus.display_unit(rec),
            "rule": rule.as_dict(), "rules": rule.describe_window(detrend), "detrend": detrend}


class SeedBody(BaseModel):
    recording_id: int
    start_idx: int
    end_idx: int
    note: str | None = None
    scale_viewed: str | None = None


@router.post("/api/annotations/seed")
def take_span_for_review(request: Request, body: SeedBody):
    """'Take span for Review': a human-authored `annotations` row with verdict `seed`,
    written through the rule-5 human door (never a detection)."""
    rec = _rec(request, body.recording_id)
    if not (0 <= body.start_idx < body.end_idx <= rec["n_samples"]):
        raise HTTPException(422, f"span [{body.start_idx}, {body.end_idx}) is outside the channel (n={rec['n_samples']})")
    c = _conn(request)
    try:
        aid = write_human(c, "annotations", {
            "recording_id": body.recording_id, "start_idx": int(body.start_idx), "end_idx": int(body.end_idx),
            "verdict": "seed", "note": body.note, "scale_viewed": body.scale_viewed,
            "source": "explore.take_for_review", "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
        })
        c.commit()
        # fixup-y: the span is IN Review's Explore spans queue — one open queue
        # over every span taken in Explore, reused on each take (as fixup-L's
        # *Send to Review* reuses its queue), so the toast's *Open Review* lands
        # on a queue that holds it
        qid = queues_mod.find_open_queue(c, source_kind="explore-spans")
        if qid is None:
            qid = queues_mod.create_queue(c, name="Explore spans", source_kind="explore-spans",
                                          note="spans taken for Review in Explore › Signal")
    finally:
        c.close()
    fs = float(rec["fs"])
    return {"id": aid, "recording_id": body.recording_id, "start_s": body.start_idx / fs, "end_s": body.end_idx / fs,
            "verdict": "seed", "source": "explore.take_for_review", "note": body.note, "queue_id": int(qid),
            "seed_id": f"explore:{body.recording_id}:{int(body.start_idx)}:{int(body.end_idx)}",
            "banner": request.app.state.rt.banner()}


# ── explore-review (2026-10-18): send a span's unjudged motifs to Review; mark an artifact across channels ──────────
# One contiguous block, appended. Both routes are the shared action strip's (explore/SpanActions.tsx), mounted on
# Signal and on Cross-channel.

#: The note that identifies Explore's one picked queue. Its filter changes with every send, so `find_open_queue`
#: (which matches filters) cannot find it again; `find_open_queue_by_note` finds it by this — the pattern of
#: Discovery's per-session picked queue (`discovery._picked_note`, fixup-AL). Explore has no session row, so there is
#: one open picked queue for Explore until it is closed in Review; the next send after that starts a new one.
EXPLORE_PICKED_NOTE = "detections picked from Explore (Signal and Cross-channel) for Review"
EXPLORE_PICKED_NAME = "Unjudged motifs · picked from Explore"
#: The most unjudged detections one send may put into the picked queue. The queue is an exact id list in
#: `filters_json`, re-resolved on every Review read: on a synthetic 16-channel, 52k-detection database a
#: whole-recording send (49k ids) took 79 s to open in Review and slowed the queue list to 8 s, while 1.5k ids opened
#: in 4 s (critic round, 2026-10-18). Above this the send is refused with the count and a narrower window suggested.
SPAN_REVIEW_MAX = 2000


class SpanReviewBody(BaseModel):
    recording_ids: list[int] = []
    t0_s: float | None = None
    t1_s: float | None = None
    #: the drawer's *Send selected to Review*: these detections, no window
    detection_ids: list[int] | None = None
    note: str | None = None


def _live_recording(c, recording_id: int) -> dict:
    """`_rec` on an open connection: 404 for an unknown id, 423 for the held-out recording while the lock is on —
    the same predicate (`corpus.recording_row` → `corpus.is_held_out`) and the same refusal as every Explore read
    and *Take span*."""
    rec = corpus.recording_row(c, recording_id)
    if rec is None:
        raise HTTPException(404, f"no recording id {recording_id}")
    if rec["held_out"]:
        raise HTTPException(423, corpus.held_out_refusal("the web UI refuses it"))
    return rec


def _window_detection_ids(c, recs: list[dict], t0_s: float, t1_s: float) -> list[int]:
    """Every detection whose span intersects [t0, t1] on these channels: `corpus.spans`' own query (legacy relative
    rows shifted, surrogate and window-part runs left out), uncapped, minus a discarded run's rows (Review never
    serves those, `queues._superseded_run_ids`, so counting them would promise items the queue will not show)."""
    ids: list[int] = []
    for rec in recs:
        got = corpus.spans(c, rec["id"], t0_s, t1_s, float(rec["fs"]), cap=10 ** 9)["detections"]
        ids.extend(int(d["id"]) for d in got)
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    dropped = {int(r[0]) for r in c.execute(
        f"SELECT d.id FROM detections d JOIN runs r ON r.id = d.run_id WHERE d.id IN ({marks}) "
        "AND r.superseded_at IS NOT NULL", ids).fetchall()}
    return sorted(set(ids) - dropped)


def _named_detection_ids(c, detection_ids: list[int]) -> list[int]:
    """The drawer's ids, validated before anything is written: each must exist, belong to a real run (not a paired
    surrogate's, not a window part's), and lie on a recording the web UI may read."""
    want = list(dict.fromkeys(int(i) for i in detection_ids))
    if not want:
        raise HTTPException(422, {"message": "no detection named: detection_ids is empty"})
    marks = ",".join("?" * len(want))
    rows = {int(r["id"]): r for r in c.execute(
        f"SELECT d.id, r.recording_id, r.surrogate_of_run_id, "
        f"CASE WHEN {q.not_window_part('r')} THEN 0 ELSE 1 END AS window_part "
        f"FROM detections d JOIN runs r ON r.id = d.run_id WHERE d.id IN ({marks})", want).fetchall()}
    missing = [i for i in want if i not in rows]
    if missing:
        raise HTTPException(422, {"message": f"no detection {', '.join(map(str, missing))} in the database"})
    fake = [i for i in want if rows[i]["surrogate_of_run_id"] is not None or rows[i]["window_part"]]
    if fake:
        raise HTTPException(422, {"message": f"detection {', '.join(map(str, fake))} belongs to a paired surrogate "
                                             "or a window part of a stitched run — not a detection anyone judges"})
    for rid in sorted({int(rows[i]["recording_id"]) for i in want}):
        _live_recording(c, rid)
    return want


@router.post("/api/explore/span-review")
def send_span_to_review(request: Request, body: SpanReviewBody):
    """*Send unjudged to Review*: the detections whose span intersects [t0, t1] on the named channels (or the
    drawer's named detections) that carry no adjudication go to Explore's ONE picked queue — created on the first
    send, extended (`queues.extend_queue`) on every later one, as Discovery's browser does (fixup-AL). A detection
    already judged is counted in `already_judged` and not added; one already in the queue in `already_queued`.

    The queue is a `discovery-run` queue over an exact detection set — the kind `extend_queue` takes — so Review
    serves it with the detection resolver and its verdicts land in `adjudications` (rule 5). A window with nothing
    to send answers 200 with `added: 0` and a sentence; no queue is made for nothing."""
    c = _conn(request)
    try:
        if body.detection_ids is not None:
            ids = _named_detection_ids(c, body.detection_ids)
            where = f"the {len(ids)} selected detection{'' if len(ids) == 1 else 's'}"
        else:
            if not body.recording_ids:
                raise HTTPException(422, {"message": "no channel named: recording_ids is empty"})
            if body.t0_s is None or body.t1_s is None or not (body.t1_s > body.t0_s):
                raise HTTPException(422, {"message": f"the window [{body.t0_s}, {body.t1_s}] s is empty"})
            recs = [_live_recording(c, int(r)) for r in dict.fromkeys(body.recording_ids)]
            ids = _window_detection_ids(c, recs, float(body.t0_s), float(body.t1_s))
            where = f"this window on {len(recs)} channel{'' if len(recs) == 1 else 's'}"
        judged: set[int] = set()
        if ids:
            marks = ",".join("?" * len(ids))
            judged = {int(r[0]) for r in c.execute(
                f"SELECT detection_id FROM adjudications WHERE detection_id IN ({marks})", ids).fetchall()}
        unjudged = [i for i in ids if i not in judged]
        if len(unjudged) > SPAN_REVIEW_MAX:
            raise HTTPException(422, {"message": (
                f"{where} holds {len(unjudged):,} unjudged motifs — more than {SPAN_REVIEW_MAX:,} at once makes a "
                "Review queue too slow to work through; nothing was sent. Pick a narrower window (or fewer "
                "channels) and send it in parts.")})
        qid = queues_mod.find_open_queue_by_note(c, source_kind="discovery-run", note=EXPLORE_PICKED_NOTE)
        added: list[int] = []
        already: list[int] = []
        if unjudged:
            if qid is None:
                qid = queues_mod.create_queue(c, name=EXPLORE_PICKED_NAME, source_kind="discovery-run",
                                              filters={"detection_ids": unjudged}, note=EXPLORE_PICKED_NOTE)
                added = list(unjudged)
            else:
                res = queues_mod.extend_queue(c, qid, unjudged)
                added, already = [int(i) for i in res["added"]], [int(i) for i in res["already"]]
        queue = queues_mod.get_queue(c, qid) if qid is not None else None
        # what Review will NOT ask about although it is in the filter: the same event as a span a person already
        # judged (`prior_verdict`), read from the resolver Review itself uses — as Discovery's picked send does
        not_asked: list[int] = []
        if added:
            # review-carry: an item is an overlap set, so every member of a prior-judged item is not asked
            prior = {int(m) for it in queues_mod.queue_items(c, qid, include_judged=True, include_prior_judged=True)
                     if it.get("prior_verdict") is not None for m in (it.get("members") or [it["target_id"]])}
            not_asked = [i for i in added if i in prior]
        skip = set(not_asked)
        fresh = [i for i in added if i not in skip]
        if not ids:
            parts = [f"no detections in {where} — nothing to send"]
        else:
            parts = [f"{len(fresh)} added to '{queue['name'] if queue else EXPLORE_PICKED_NAME}'" if fresh else "none added"]
            if already:
                parts.append(f"{len(already)} already in the queue")
            if judged:
                parts.append(f"{len(judged)} already judged (not added)")
            if not_asked:
                parts.append(f"{len(not_asked)} not asked: a human verdict already covers it")
        counts = queues_mod.queue_counts(c, qid) if qid is not None else None
        return {"queue_id": None if qid is None else int(qid), "queue": queue["name"] if queue else EXPLORE_PICKED_NAME,
                "added": len(added), "added_ids": added, "not_asked": len(not_asked), "already_queued": len(already),
                "already_judged": len(judged), "total": len(ids),
                "unjudged_in_queue": None if counts is None else int(counts["remaining"]),
                "message": " · ".join(parts),
                "note": ("one queue for every motif sent from Explore; it is a filter over those detections, and a "
                         "verdict in Review lands in adjudications like any other")}
    finally:
        c.close()


class ArtifactBody(BaseModel):
    recording_ids: list[int] = []
    t0_s: float
    t1_s: float
    note: str | None = None
    #: which page marked it — Cross-channel (the default) or Signal; it becomes the row's `source`
    origin: str = "cross-channel"


ARTIFACT_SOURCES = {"cross-channel": "explore-cross-channel", "signal": "explore-signal"}


@router.post("/api/explore/artifact")
def mark_artifact(request: Request, body: ArtifactBody):
    """*Mark artifact*: one human `annotations` row with verdict `artifact` per selected channel over [t0, t1],
    written through the rule-5 human door (`write_human`) — the verdict word Review writes, never a sixth. Every
    channel is checked (404, or 423 for the held-out recording while the lock is on) and the window clamped to each
    channel before anything is written, so a refusal writes nothing. The channels must share one recording: a window
    in seconds names one place only on one recording's clock."""
    if body.origin not in ARTIFACT_SOURCES:
        raise HTTPException(422, {"message": f"origin must be one of {', '.join(ARTIFACT_SOURCES)}, got {body.origin!r}"})
    if not body.recording_ids:
        raise HTTPException(422, {"message": "no channel named: recording_ids is empty"})
    if not (body.t1_s > body.t0_s):
        raise HTTPException(422, {"message": f"the window [{body.t0_s:g}, {body.t1_s:g}] s is empty"})
    c = _conn(request)
    try:
        recs = [_live_recording(c, int(r)) for r in dict.fromkeys(body.recording_ids)]
        files = sorted({r["source_file"] for r in recs})
        if len(files) > 1:
            raise HTTPException(422, {"message": f"the channels come from {len(files)} recordings ({', '.join(files)}); "
                                                 "an artifact window is marked on the channels of one recording"})
        plan = []
        for rec in recs:
            fs, n = float(rec["fs"]), int(rec["n_samples"])
            a = max(0, int(np.floor(body.t0_s * fs))); b = min(n, int(np.ceil(body.t1_s * fs)))
            if not b > a:
                raise HTTPException(422, {"message": f"the window [{body.t0_s:g}, {body.t1_s:g}] s lies outside "
                                                     f"{rec['name']} (0 to {n / fs:g} s)"})
            plan.append((rec, a, b))
        now = _dt.datetime.now().isoformat(timespec="seconds")
        source = ARTIFACT_SOURCES[body.origin]
        ids = [write_human(c, "annotations", {
            "recording_id": int(rec["id"]), "start_idx": a, "end_idx": b, "verdict": "artifact",
            "note": body.note, "source": source, "created_at": now}) for rec, a, b in plan]
        c.commit()
    finally:
        c.close()
    names = [rec["name"] for rec, _a, _b in plan]
    return {"ids": [int(i) for i in ids], "recording_ids": [int(rec["id"]) for rec, _a, _b in plan],
            # the extent written, clamped to the channels (a window past a channel's end is cut there)
            "start_s": min(a / float(rec["fs"]) for rec, a, _b in plan),
            "end_s": max(b / float(rec["fs"]) for rec, _a, b in plan), "verdict": "artifact", "source": source,
            "message": f"artifact marked on {len(ids)} channel{'' if len(ids) == 1 else 's'} ({', '.join(names)})"}


# ── edit-span (2026-10-18): Review's "Edit span in Explore" ─────────────────
#
# One contiguous block, two routes. The item is named by a detection id (the
# Review item of a detection queue) or by a member ref ``m-<id>`` (a Library
# family queue, and the Family page's "Redraw in Explore").
#
# The save rule (rule 5 — detections are machine-only, annotations human-only):
#   * a Library MEMBER  -> a human `annotations` row with the corrected span,
#     then `revisions.add_revision(origin='human', annotation_id=...)`, which
#     makes it the member's current revision (rev 1, the matcher's, is kept);
#   * a plain DETECTION -> a human `annotations` row with the corrected span
#     and the item's verdict (``seed`` when it has none).
#   A member's annotation carries its verdict, ``unsure`` when it has none: it
#   backs the revision and is not itself a judgement (critic round).
# The `detections` row is never written, on either path.
#
# Its imports live here, with the block, so a sibling prompt appending routes
# to this file merges without touching the header (2026-10-18 wave).
import os  # noqa: E402

from Working.library import revisions as revisions_mod  # noqa: E402
from Working.review import family_queue  # noqa: E402

from . import decimate  # noqa: E402

SPAN_EDIT_SOURCE = "review-span-edit"
SPAN_EDIT_PX = 900


class SpanEditBody(BaseModel):
    start_idx: int
    end_idx: int
    note: str | None = None


def _span_edit_target(c, ref: str) -> dict:
    """Resolve ``ref`` (a detection id, or ``m-<member id>``) to
    `{recording_id, detection_id, det: (s, e) | None, member_id}`; 404 when it names nothing."""
    text = str(ref).strip()
    if text.lower().startswith("m-"):
        try:
            mid = int(text[2:])
        except ValueError:
            raise HTTPException(404, f"{ref!r} is not a member ref (m-<id>)") from None
        row = c.execute("SELECT id, recording_id, start_idx, end_idx FROM motif_member WHERE id = ?",
                        (mid,)).fetchone()
        if row is None:
            raise HTTPException(404, f"no Library member {text}")
        # the member's own detection, when one stands behind it: the latest machine revision's, else its entry's
        # — but the entry's only when this member IS that detection (same channel, overlapping): the entry's
        # detection is where the ENTRY came from, and another member of it, elsewhere, must not borrow its span,
        # its verdict, or write it as its rev 1's provenance (critic round, 2026-10-18)
        det = c.execute("SELECT detection_id FROM motif_member_revision WHERE member_id = ? AND detection_id "
                        "IS NOT NULL ORDER BY revision DESC LIMIT 1", (mid,)).fetchone()
        did = int(det[0]) if det is not None else None
        bounds = _detection_bounds(c, did) if did is not None else None
        if did is None:
            ent = c.execute("SELECT me.detection_id FROM motif_member mm JOIN motif_entry me ON me.id = mm.entry_id "
                            "WHERE mm.id = ? AND me.detection_id IS NOT NULL", (mid,)).fetchone()
            cand = _detection_bounds(c, int(ent[0])) if ent is not None else None
            if cand is not None and cand[0] == int(row["recording_id"])                     and cand[1] < int(row["end_idx"]) and cand[2] > int(row["start_idx"]):
                did, bounds = int(ent[0]), cand
        return {"recording_id": int(row["recording_id"]), "detection_id": did,
                "det": bounds[1:] if bounds else None, "member_id": mid}
    try:
        did = int(text)
    except ValueError:
        raise HTTPException(404, f"{ref!r} is neither a detection id nor a member ref (m-<id>)") from None
    bounds = _detection_bounds(c, did)
    if bounds is None:
        raise HTTPException(404, f"no detection {did}")
    rid, s, e = bounds
    return {"recording_id": rid, "detection_id": did, "det": (s, e),
            "member_id": _member_of_detection(c, did, rid, s, e)}


def _detection_bounds(c, did: int):
    """`(recording_id, start_idx, end_idx)` channel-absolute (a legacy span-relative row is shifted), or None."""
    row = c.execute("SELECT d.start_idx, d.end_idx, r.recording_id, r.span_start FROM detections d "
                    "JOIN runs r ON r.id = d.run_id WHERE d.id = ?", (int(did),)).fetchone()
    if row is None:
        return None
    s, e = corpus._absolute(row["start_idx"], row["end_idx"], row["span_start"])
    return int(row["recording_id"]), int(s), int(e)


def _member_of_detection(c, did: int, rid: int, s: int, e: int):
    """The Library member a detection IS, or None. A revision naming the detection is the precise link (the
    newest member wins); otherwise a member of an entry exemplified by this detection, on the same channel and
    overlapping it (the importer's link, `motif_entry.detection_id`)."""
    row = c.execute("SELECT member_id FROM motif_member_revision WHERE detection_id = ? "
                    "ORDER BY member_id DESC LIMIT 1", (int(did),)).fetchone()
    if row is not None:
        return int(row[0])
    row = c.execute("SELECT mm.id FROM motif_member mm JOIN motif_entry me ON me.id = mm.entry_id "
                    "WHERE me.detection_id = ? AND mm.recording_id = ? AND mm.start_idx < ? AND mm.end_idx > ? "
                    "ORDER BY mm.id LIMIT 1", (int(did), int(rid), int(e), int(s))).fetchone()
    return int(row[0]) if row is not None else None


def _member_current(c, mid: int) -> dict:
    """`{start_idx, end_idx, revision_no}` of the member's current revision; a member with no revision rows
    (written before revisions existed) answers its own span as revision 0."""
    cur = revisions_mod.current_revision(c, mid)
    if cur is not None:
        return {"start_idx": int(cur["start_idx"]), "end_idx": int(cur["end_idx"]),
                "revision_no": int(cur["revision"])}
    m = c.execute("SELECT start_idx, end_idx FROM motif_member WHERE id = ?", (int(mid),)).fetchone()
    return {"start_idx": int(m["start_idx"]), "end_idx": int(m["end_idx"]), "revision_no": 0}


def _span_edit_verdict(c, t: dict):
    """The item's verdict, or None: a member's Review verdict (Library family queue) first, then the
    adjudication on its detection."""
    if t["member_id"] is not None:
        v = family_queue.member_verdicts(c, [t["member_id"]]).get(int(t["member_id"]))
        if v:
            return v
    if t["detection_id"] is not None:
        row = c.execute("SELECT verdict FROM adjudications WHERE detection_id = ?",
                        (int(t["detection_id"]),)).fetchone()
        if row is not None:
            return row["verdict"]
    return None


def _span_edit_context(rec: dict, s: int, e: int, px: int) -> dict:
    """The channel over ±2 span lengths, as a time-axis envelope (the shape Review's context card gets:
    `t` in absolute seconds beside `v` in mV, `t0_s`/`t1_s` the window's edges). Empty, with a reason, when the
    channel file is missing or declares no unit — never a synthesised shape. Near-sibling:
    `review._trace_env`, not imported because the AR pass is rewriting `review.py`."""
    fs = float(rec["fs"] or 1.0)
    n = int(rec["n_samples"])
    length = max(1, int(e) - int(s))
    c0, c1 = max(0, int(s) - 2 * length), min(n, int(e) + 2 * length)
    empty = {"t": [], "v": [], "t0_s": c0 / fs, "t1_s": c1 / fs, "fs": fs, "n_source": 0, "n_points": 0,
             "decimated": False, "unit": None}
    path = rec.get("npy_path")
    if not path or not os.path.isfile(path):
        return {**empty, "reason": "the channel file is missing"}
    x = corpus.display_channel(rec)
    if x.unit is None:
        return {**empty, "reason": "the recording declares no unit; nothing is drawn as mV"}
    c1 = min(c1, int(len(x)))
    env = decimate.envelope(x, fs, c0, c1, max(8, min(4000, int(px))))
    return {"t": [round(float(a), 4) for a in env["t"]],
            "v": [None if a is None else round(float(a), 4) for a in env["v"]],
            "t0_s": round(c0 / fs, 4), "t1_s": round(c1 / fs, 4), "fs": fs,
            "n_source": int(env["n_source"]), "n_points": int(env["n_points"]),
            "decimated": bool(env["decimated"]), "unit": x.unit, "reason": None}


def _span_edit_payload(c, rec: dict, t: dict, px: int) -> dict:
    member = None
    if t["member_id"] is not None:
        member = {"ref": f"m-{t['member_id']}", "current": _member_current(c, t["member_id"])}
    shown = (member["current"]["start_idx"], member["current"]["end_idx"]) if member else t["det"]
    det = {"start_idx": t["det"][0], "end_idx": t["det"][1]} if t["det"] else None
    return {
        "recording_id": int(rec["id"]), "channel": rec.get("name") or f"CH{int(rec['channel']) + 1}",
        "source_file": rec["source_file"], "fs": float(rec["fs"]), "n_samples": int(rec["n_samples"]),
        "unit": corpus.display_unit(rec),
        "detection_id": t["detection_id"], "detection": det, "member": member,
        "verdict": _span_edit_verdict(c, t),
        "context_trace": _span_edit_context(rec, shown[0], shown[1], px),
    }


@router.get("/api/explore/span-edit/{ref}")
def get_span_edit(request: Request, ref: str, px: int = SPAN_EDIT_PX):
    """The span a Review item names, for the live editor: the detection's span, the Library member it is (with
    its current revision) or null, the item's verdict, and the channel around it (±2 lengths)."""
    c = _conn(request)
    try:
        t = _span_edit_target(c, ref)
    finally:
        c.close()
    rec = _rec(request, t["recording_id"])        # 404, or 423 on the held-out recording, as every Explore read
    c = _conn(request)
    try:
        return _span_edit_payload(c, rec, t, px)
    finally:
        c.close()


@router.post("/api/explore/span-edit/{ref}")
def post_span_edit(request: Request, ref: str, body: SpanEditBody):
    """Save a corrected span. A member gets a new human revision (backed by an annotation); a plain detection
    gets a human annotation with the item's verdict (``seed`` when it has none). Never the detections row."""
    c = _conn(request)
    try:
        t = _span_edit_target(c, ref)
    finally:
        c.close()
    rec = _rec(request, t["recording_id"])        # 423 on the held-out recording, before anything is written
    s, e, n = int(body.start_idx), int(body.end_idx), int(rec["n_samples"])
    if e - s < 2:
        raise HTTPException(422, f"span [{s}, {e}) is shorter than two samples: a span needs at least two")
    if s < 0 or e > n:
        raise HTTPException(422, f"span [{s}, {e}) is outside the channel (0 – {n} samples)")
    now = _dt.datetime.now().isoformat(timespec="seconds")
    c = _conn(request)
    try:
        verdict = _span_edit_verdict(c, t)
        # a plain detection: the item's verdict, `seed` when it has none (the prompt's rule). A member: its
        # verdict, `unsure` when it has none — the annotation there only backs the revision, a redrawn extent is
        # not a verdict, and `seed` is not a member's question (family_queue): it would count the member judged
        # "yes" by extent in Review and the Library, and put it in the Explore spans queue (critic round)
        fallback = "seed" if t["member_id"] is None else "unsure"
        word = verdict if verdict in q.VERDICTS else fallback
        note = body.note
        if verdict and word != verdict:
            note = f"{note + ' · ' if note else ''}item verdict {verdict!r} is not an annotation verdict"
        elif not verdict and t["member_id"] is not None:
            note = f"{note + ' · ' if note else ''}span correction only: no verdict given"
        if t["member_id"] is None:
            aid = q.insert_annotation(c, t["recording_id"], s, e, word, SPAN_EDIT_SOURCE, note=note,
                                      created_at=now, commit=False)
            c.commit()
            return {"kind": "annotation", "member": None,
                    "annotation": {"id": int(aid), "verdict": word, "source": SPAN_EDIT_SOURCE,
                                   "start_idx": s, "end_idx": e, "detection_id": t["detection_id"]}}
        mid = int(t["member_id"])
        try:
            # a member written before revisions existed: its own span becomes the machine rev 1 first, so the
            # matcher keeps comparing against what the machine found, never against this human edit
            seeded_rev1 = revisions_mod.current_revision(c, mid) is None
            if seeded_rev1:
                m = c.execute("SELECT start_idx, end_idx FROM motif_member WHERE id = ?", (mid,)).fetchone()
                revisions_mod.add_revision(c, mid, origin="machine", start_idx=int(m["start_idx"]),
                                           end_idx=int(m["end_idx"]), detection_id=t["detection_id"],
                                           created_at=now, commit=False)
            aid = q.insert_annotation(c, t["recording_id"], s, e, word, SPAN_EDIT_SOURCE, note=note,
                                      created_at=now, commit=False)
            rid = revisions_mod.add_revision(c, mid, origin="human", start_idx=s, end_idx=e,
                                             annotation_id=aid, created_at=now, commit=False)
        except ValueError as err:          # e.g. a span that does not overlap rev 1: a different motif
            c.rollback()
            raise HTTPException(422, str(err)) from None
        stale = revisions_mod.stale_edges(c, mid)
        c.commit()
        row = c.execute("SELECT revision FROM motif_member_revision WHERE id = ?", (rid,)).fetchone()
        return {"kind": "revision", "member": f"m-{mid}",
                "revision": {"id": int(rid), "revision_no": int(row["revision"]), "start_idx": s, "end_idx": e,
                             "annotation_id": int(aid)},
                "annotation": {"id": int(aid), "verdict": word, "source": SPAN_EDIT_SOURCE},
                # revisions.py: whoever writes the extent-edit route owns this list — the family's distances to
                # this member were computed on the old extent and are stale until recomputed
                "stale_edges": stale, "seeded_rev1": seeded_rev1}
    finally:
        c.close()
