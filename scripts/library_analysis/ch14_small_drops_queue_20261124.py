"""
ch14_small_drops_queue_20261124.py
==================================
A review queue of 50 of the small, sharp drops in the MJu26a CH14 train (the researcher, 24 Nov: "Yes, queue 50").

In plain words
--------------
The drop plots of 23 Nov (`docs/library_analysis/20261123_plots/`) found the CH14 train (sequence 254, MJu26a_fs10 CH14,
90 h) holding a third kind of drop besides its thin and wide ones: 232 small sharp drops (about 1.8 mV, 2 s wide)
running as a smooth band through the whole train. Nobody has judged them - the candidate-event queues left out drops
under 15 % of the biggest drop round them. This queue puts 50 of them, spread evenly over the 90 hours, to the
researcher one at a time, to see whether the band is real before any analysis leans on it.

The drops are the plots' own (`sequence_events.csv`, the whole-drop rule 79d0243e at >= 15x local noise, core >= 5
samples, no relative floor), and "kind B" is the plots' own mixture-model kind (`drop_plots_20261123.kinds_of`). Left
out before sampling: a drop already in any candidate-event queue (judged or waiting; its fall overlaps), the same
event as any judged machine detection (IoU >= 0.5), the only drop of a span judged as an event, and Review's own
matching rule. Boxes as in the v2 candidate queues: the top to the half recovery (or the bottom) plus a fifth each side.

Dry run by default (database read-only). With --apply it backs the database up and writes one config, the runs (one per
lane: no two boxes of one run overlap, so Review serves every drop as its own item), 50 detections and one listed
queue. Detections only - no verdict is written (CLAUDE.md rule 5).

    PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 "$PY" scripts/library_analysis/ch14_small_drops_queue_20261124.py [--apply]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))

import candidate_events_20261123 as CE  # noqa: E402
import drop_plots_20261123 as DP  # noqa: E402
from Working.database import runs as _runs  # noqa: E402
from Working.interrogation import whole_drop as WD  # noqa: E402
from Working.review import queues as _queues  # noqa: E402

DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite")
OUT = os.path.join(ROOT, "docs", "library_analysis", "20261123_plots")
SEQUENCE_ID = 254
SAMPLE = 50
KIND = "ch14-small-drops"          # deliberately NOT containing "candidate-events": the v2 script's retire step
VERSION = "v1"                     # deletes unjudged detections of every run whose config matches that string
RUN_NAME = "CH14 small drops sample (whole drop)"
QUEUE_NAME = "Events · CH14 small drops, sample of 50 (24 Nov)"
QUEUE_NOTE = ("A sample of 50 of the 232 small, sharp drops (about 1.8 mV, 2 s wide) that the 23 Nov drop plots found "
              "running as a steady band through the MJu26a CH14 train (sequence 254, 90 h), between its big thin and "
              "wide drops. None was in an earlier queue: those left out drops under 15 % of the biggest drop round "
              "them. Spread evenly over the 90 hours, in time order. Judge the drop itself: is it a real event, or "
              "noise? Each box runs from the drop's top to its half recovery plus a fifth each side.")


def kind_b(sev):
    """The sequence's drops labelled with the plots' kinds; returns (drops, kind-B mask, kind names)."""
    d = sev[(sev["sequence_id"] == SEQUENCE_ID) & (sev["status"] != "rejected")].reset_index(drop=True)
    lab, k, _ = DP.kinds_of(d)
    names = {}
    for j in range(k):
        g = d[lab == j]
        names[j] = (float(g["depth_mv"].median()), float(g["width_s"].median()), len(g))
    # kind B: the small sharp band - median depth 1-3 mV, median width under 5 s (the plots: 1.8 mV, 2 s, 232 drops)
    hits = [j for j, (dep, wid, n) in names.items() if 1.0 <= dep <= 3.0 and wid < 5.0]
    if len(hits) != 1:
        raise SystemExit(f"expected one small sharp kind, found {hits} among {names}")
    return d, lab == hits[0], names, hits[0]


def queued_drops(conn):
    """`{recording: [(top, bottom)]}` of every candidate-event detection, judged or still waiting in a queue."""
    out = {}
    for rid, meta in conn.execute(
            "SELECT r.recording_id, d.meta_json FROM detections d JOIN runs r ON r.id = d.run_id "
            "JOIN configs c ON c.id = r.config_id WHERE c.config_json LIKE '%candidate-events%' "
            "OR c.config_json LIKE ?", (f"%{KIND}%",)):
        m = json.loads(meta)
        out.setdefault(int(rid), []).append((int(m["top_idx"]), int(m["bottom_idx"])))
    return {k: sorted(v) for k, v in out.items()}


def judged_single_drops(conn, recs, rid):
    """CE.judged_drops restricted to one recording: (only drops of spans judged as events, those spans)."""
    spans = [(int(r.recording_id), int(r.start_idx), int(r.end_idx)) for r in pd.read_csv(CE.CATALOGUE).itertuples()
             if int(r.recording_id) == rid]
    marks = ",".join("?" * len(CE.WINDOW_LABELS))
    spans += [(int(r[0]), int(r[1]), int(r[2])) for r in conn.execute(
        f"SELECT recording_id, start_idx, end_idx FROM annotations WHERE deleted_at IS NULL AND recording_id = ? "
        f"AND (source IS NULL OR source NOT IN ({marks}))", (rid, *CE.WINDOW_LABELS))]
    x = np.load(os.path.join(ROOT, recs[rid]["npy"]), mmap_mode="r")
    drops, held = [], []
    for _, a, b in sorted(set(spans)):
        if b - a < 4 or not np.all(np.isfinite(np.asarray(x[a:b], dtype=float))):
            continue
        m = WD.measure(x, a, b, recs[rid]["fs"], to_mv=CE.to_mv(recs[rid]["units"]))
        if m.get("ok") and m["n_events"] == 1:
            drops.append((int(m["top_idx"]), int(m["bottom_idx"])))
            held.append((a, b))
    return {rid: sorted(drops)}, {rid: sorted(held)}


def build(conn):
    recs = DP.recordings(conn)
    metas, sev = DP.load_sequence_events()
    d, is_b, names, b = kind_b(sev)
    rid = int(d["recording_id"].iloc[0])
    n_samples = recs[rid]["n"]
    cand = d[is_b & (d["status"] == "unjudged")].sort_values("top_idx").reset_index(drop=True)
    queued = queued_drops(conn)
    judged_spans, _ = CE.judged_detections(conn)
    judged, held = judged_single_drops(conn, recs, rid)
    left, why = [], {}
    for r in cand.itertuples():
        top, bottom = int(r.top_idx), int(r.bottom_idx)
        end = int(r.recovery_idx) if np.isfinite(r.recovery_idx) else bottom
        s, t = CE.box(top, end, n_samples)
        reason = ("already in a candidate-event queue" if CE.overlaps(queued, rid, top, bottom) else
                  "the same event as a judged detection" if CE.same_event(judged_spans, rid, s, t) else
                  "the only drop of a span judged as an event" if (CE.same_event(judged, rid, top, bottom)
                                                                   or CE.mostly_inside(held, rid, top, bottom))
                  else None)
        if reason:
            why[reason] = why.get(reason, 0) + 1
            continue
        left.append({"recording_id": rid, "start": s, "end": t, "top_idx": top, "bottom_idx": bottom,
                     "depth_mv": round(float(r.depth_mv), 4), "width_s": round(float(r.width_s), 2)
                     if np.isfinite(r.width_s) else None, "depth_sigmas": round(float(r.depth_sigmas), 1),
                     "long_tail": bool(r.long_tail), "hour": round(float(r.t_s) / 3600.0, 3)})
    rows = [{"id": n, "run_id": -1, "recording_id": it["recording_id"], "start_idx": it["start"],
             "end_idx": it["end"]} for n, it in enumerate(left)]
    prior = set(_queues._prior_verdicts(conn, rows))
    why["Review's matching rule"] = len(prior)
    left = [it for n, it in enumerate(left) if n not in prior]
    pick = sorted(set(np.round(np.linspace(0, len(left) - 1, min(SAMPLE, len(left)))).astype(int)))
    items = [dict(left[i], group="ch14_small_drops", sequence_id=SEQUENCE_ID, kind="B") for i in pick]
    CE.lanes(items)
    summary = {"kinds": {chr(65 + j): {"median_depth_mv": round(v[0], 2), "median_width_s": round(v[1], 2),
                                       "drops": v[2]} for j, v in names.items()},
               "kind_b": int(is_b.sum()), "kind_b_unjudged": len(cand), "left_out": why,
               "eligible": len(left), "sampled": len(items),
               "hours": [items[0]["hour"], items[-1]["hour"]] if items else None,
               "runs": len({it["lane"] for it in items}),
               "depth_mv": {"min": min(it["depth_mv"] for it in items), "max": max(it["depth_mv"] for it in items)}}
    return summary, items


def write(conn, items, stamp):
    cfg_id, _ = _runs.get_or_create_config(conn, {"kind": KIND, "version": VERSION, "stamp": stamp,
                                                   "rule_commit": "79d0243e", "sequence_id": SEQUENCE_ID,
                                                   "box": "top->half recovery or bottom, +20% each side",
                                                   "sample": "evenly spread in time"})
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    run_of = {}
    with conn:
        for rid, lane in sorted({(it["recording_id"], it["lane"]) for it in items}):
            n = conn.execute("SELECT n_samples FROM recordings WHERE id = ?", (rid,)).fetchone()[0]
            cur = conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status, "
                               "name, finished_at) VALUES (?, ?, 0, ?, ?, 'completed', ?, ?)",
                               (cfg_id, rid, int(n), now, RUN_NAME, now))
            run_of[(rid, lane)] = int(cur.lastrowid)
        for it in items:
            meta = {k: it[k] for k in ("group", "sequence_id", "kind", "top_idx", "bottom_idx", "depth_mv", "width_s",
                                       "depth_sigmas", "long_tail")}
            run_id = run_of[(it["recording_id"], it["lane"])]
            cur = conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score, meta_json) "
                               "VALUES (?, ?, ?, NULL, ?)", (run_id, it["start"], it["end"], json.dumps(meta)))
            it["detection_id"], it["run_id"] = int(cur.lastrowid), run_id
    qid = int(_queues.create_queue(conn, name=QUEUE_NAME, source_kind="discovery-run",
                                   filters={"detection_ids": [it["detection_id"] for it in items], "order": "listed"},
                                   note=QUEUE_NOTE))
    conn.commit()
    return {"queue_id": qid, "config_id": cfg_id, "runs": len(run_of)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--apply", action="store_true", help="back up the database, write the runs and the queue")
    args = ap.parse_args()
    conn = sqlite3.connect(f"file:{DB.replace(os.sep, '/')}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row                          # Review's matching rule reads rows by name
    try:
        summary, items = build(conn)
    finally:
        conn.close()
    print(json.dumps(summary, indent=1))
    path = os.path.join(OUT, "ch14_small_drops_queue.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "items": items}, f, indent=1)
    if not args.apply:
        print("dry run: nothing written to the database (pass --apply)")
        return
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = os.path.join(ROOT, "DATA", "db", "backups", f"before_ch14_small_drops_{stamp}.sqlite")
    with sqlite3.connect(DB) as src, sqlite3.connect(backup) as dst:
        src.backup(dst)
    print("backed up to", backup)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        out = write(conn, items, stamp)
    finally:
        conn.close()
    result = {**summary, **out, "backup": backup, "stamp": stamp}
    with open(path, "w", encoding="utf-8") as f:
        json.dump({**result, "items": items}, f, indent=1)
    print(json.dumps(out | {"backup": backup}, indent=1))


if __name__ == "__main__":
    main()
