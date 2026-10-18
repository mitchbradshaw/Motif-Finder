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
        if not ids:
            parts = [f"no detections in {where} — nothing to send"]
        else:
            parts = [f"{len(added)} added to '{queue['name'] if queue else EXPLORE_PICKED_NAME}'" if added else "none added"]
            if already:
                parts.append(f"{len(already)} already in the queue")
            if judged:
                parts.append(f"{len(judged)} already judged (not added)")
        counts = queues_mod.queue_counts(c, qid) if qid is not None else None
        return {"queue_id": None if qid is None else int(qid), "queue": queue["name"] if queue else EXPLORE_PICKED_NAME,
                "added": len(added), "added_ids": added, "already_queued": len(already),
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
            "start_s": body.t0_s, "end_s": body.t1_s, "verdict": "artifact", "source": source,
            "message": f"artifact marked on {len(ids)} channel{'' if len(ids) == 1 else 's'} ({', '.join(names)})"}
