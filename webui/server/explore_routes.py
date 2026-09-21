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

from Working.cross_channel import classify_waveforms
from Working.database import queries as q
from Working.database.runs import list_runs, load_recipe

from . import corpus
from .runtime import HELD_OUT_FILE
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
    if rec["held_out"]:
        raise HTTPException(423, f"{HELD_OUT_FILE} is held out; the web UI refuses it")
    return rec


def run_methods(conn, source_file: str) -> list[dict]:
    """Every run with detections on a recording file, with its method (the algorithms of its recipe)."""
    out = []
    recs = {r["id"]: dict(r) for r in q.list_recordings(conn, source_file)}
    for row in list_runs(conn):
        if row["recording_id"] not in recs:
            continue
        n = conn.execute("SELECT COUNT(*) FROM detections WHERE run_id = ?", (row["id"],)).fetchone()[0]
        try:
            recipe = load_recipe(conn, row["config_id"])
            algos = [s["algorithm"] for s in recipe["steps"]]
        except Exception:
            algos = []
        out.append({"id": row["id"], "recording_id": row["recording_id"], "channel": recs[row["recording_id"]]["channel"],
                    "status": row["status"], "started_at": row["started_at"], "name": row["name"] if "name" in row.keys() else None,
                    "algorithms": algos, "method": algos[-1] if algos else "?", "n_detections": int(n)})
    return out


@router.get("/api/corpus/{source_file}/runs")
def get_runs_for_file(request: Request, source_file: str):
    if source_file == HELD_OUT_FILE:
        raise HTTPException(423, f"{HELD_OUT_FILE} is held out")
    c = _conn(request)
    try:
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
            "WHERE a.recording_id = ? AND a.deleted_at IS NULL AND a.end_idx > ? AND a.start_idx < ? ORDER BY a.start_idx LIMIT 5000",
            (recording_id, s0, s1)).fetchall()
        ids = [a["id"] for a in ann]
        tags_by = {}
        if ids:
            marks = ",".join("?" for _ in ids)
            for r in c.execute(f"SELECT t.annotation_id, v.category, v.value FROM annotation_tags t JOIN tag_vocabulary v ON v.id = t.tag_id "
                               f"WHERE t.annotation_id IN ({marks})", ids):
                tags_by.setdefault(r["annotation_id"], []).append({"category": r["category"], "value": r["value"]})
        reviewed = c.execute("SELECT id, start_idx, end_idx, scale_viewed, source, reviewed_at FROM reviewed_spans WHERE recording_id = ? "
                             "AND end_idx > ? AND start_idx < ? ORDER BY start_idx LIMIT 5000", (recording_id, s0, s1)).fetchall()
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
def get_cross_channel(request: Request, recording_id: int, t0: float = 0.0, t1: float | None = None, px: int = 900):
    """The same window on every channel of the recording, each with its lag and
    waveform correlation against the reference channel (`Working.cross_channel`)."""
    rec = _rec(request, recording_id)
    fs = float(rec["fs"])
    if t1 is None:
        t1 = min(rec["duration_s"], t0 + 3600.0)
    if not (0 <= t0 < t1 <= rec["duration_s"] + 1e-9):
        raise HTTPException(422, f"window must satisfy 0 <= t0 < t1 <= {rec['duration_s']:.0f} s")
    px_used = max(16, min(4000, px))
    s0, s1 = int(t0 * fs), int(t1 * fs)
    c = _conn(request)
    try:
        sibs = [dict(r) for r in q.list_recordings(c, rec["source_file"])]
        ref_x = np.asarray(corpus.load_channel(rec["npy_path"])[s0:s1], dtype=float)
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
                item["envelope"] = w["envelope"]; item["y_range"] = corpus.y_range(row)
            except Exception as e:
                item["error"] = f"{type(e).__name__}: {e}"
                out.append(item); continue
            if r["id"] != recording_id:
                y = np.asarray(corpus.load_channel(row["npy_path"])[s0:s1], dtype=float)[::stride]
                n = min(len(y), len(ref_d))
                if n >= 4 and np.isfinite(ref_d[:n]).all() and np.isfinite(y[:n]).all() and ref_d[:n].std() > 0 and y[:n].std() > 0:
                    lag, corr, cls = classify_waveforms(ref_d[:n], y[:n])
                    item.update({"lag_s": float(lag * stride / fs), "r": float(corr), "classification": cls})
                else:
                    item.update({"lag_s": None, "r": None, "classification": "undefined"})
            out.append(item)
    finally:
        c.close()
    return {"reference_id": recording_id, "source_file": rec["source_file"], "t0_s": t0, "t1_s": t1, "fs": fs,
            "stride": stride, "channels": out}


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
    finally:
        c.close()
    fs = float(rec["fs"])
    return {"id": aid, "recording_id": body.recording_id, "start_s": body.start_idx / fs, "end_s": body.end_idx / fs,
            "verdict": "seed", "source": "explore.take_for_review", "note": request.app.state.rt.banner()}
