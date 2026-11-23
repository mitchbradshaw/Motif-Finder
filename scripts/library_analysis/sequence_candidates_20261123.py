"""Candidate sequences for the first sequence-review queue (2026-11-23), and - with --apply - the queue itself.

In plain words: a sequence is a run of drop events in order on one channel. Three kinds of candidate go to the
researcher, each asked once, "is this a sequence?":

1. the hand-labelled sequences of the September catalogue (27 judged interesting or seed; the 3 judged not
   interesting are left out) - existing `sequences` rows, sent by id;
2. CHAINS of neighbouring accepted events: every drop event of every accepted span (whole-drop rule,
   `Working.interrogation.whole_drop`) on one channel, chained while the next event's top follows within 1 h, kept
   at 5 events or more. The 1 h rule is `Working.autodetect.sequences.find_sequences`' own fallback, built from the
   same `trains` functions; its logISI first pass is skipped here because on ACCEPTED events it cuts at gaps of
   19 h and 64 h - accepted events are a sample of what was reviewed, so their gaps have no within/between split;
3. MULTI-EVENT SPANS: accepted spans holding two or more drop events.

A chain lying mostly (half its length or more) inside a hand-labelled sequence, and a multi-event span lying mostly
inside a kept chain or hand-labelled sequence, is left out: it is already asked about. Every candidate carries its
events, which Review draws inside it.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/library_analysis/sequence_candidates_20261123.py
    ... --apply     backs the database up, applies its migrations (init_db), and sends the candidates to Review

Read-only without --apply. With it, writes: machine `sequences` rows + `sequence_members` (the candidates) and one
`review_queues` row, through `Working.review.sequence_queue.send_to_sequence_review` - no human verdict is written.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
from collections import Counter

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from Working.interrogation.trains import _labels_from_runs, _runs_below  # noqa: E402

SPANS = os.path.join(ROOT, "docs", "thesis", "data", "accepted_catalogue_20261109", "accepted_spans.csv")
WHOLE = os.path.join(ROOT, "docs", "library_analysis", "20261123", "whole_drop.csv")
DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite")
OUT = os.path.join(ROOT, "docs", "library_analysis", "20261123")
GAP_S = 3600.0
MIN_EVENTS = 5
QUEUE_NAME = "Sequences · candidates (23 Nov)"


def events_by_recording(spans, whole):
    """Every drop event of every accepted span, per recording: `[(top, bottom, depth, event_id)]` in time order.
    A span the whole-drop rule found no event in stands as itself."""
    w = whole.set_index("event_id")
    out = {}
    for r in spans.itertuples(index=False):
        rid = int(r.recording_id)
        ev = []
        if r.event_id in w.index and isinstance(w.at[r.event_id, "whole_events"], str):
            ev = [(int(t), int(b), float(d), r.event_id) for t, b, d in json.loads(w.at[r.event_id, "whole_events"])]
        if not ev:
            ev = [(int(r.start_idx), int(r.end_idx), float("nan"), r.event_id)]
        out.setdefault(rid, []).extend(ev)
    for rid in out:
        out[rid].sort()
    return out


def chains(events, fs_of):
    """Runs of events whose next top follows within GAP_S, MIN_EVENTS or more: `[(rid, [events])]`."""
    found = []
    for rid, ev in events.items():
        if len(ev) < MIN_EVENTS:
            continue
        t = np.array([e[0] for e in ev], dtype=float) / fs_of[rid]
        labels = _labels_from_runs(len(t), _runs_below(np.diff(t), GAP_S, strict=False), MIN_EVENTS)
        for lab in sorted(set(labels[labels >= 0].tolist())):
            found.append((rid, [e for e, l in zip(ev, labels) if l == lab]))
    return found


def covered(rid, a, b, regions):
    """Half or more of [a, b) lies inside one of `regions` on the same recording."""
    for r2, s, e in regions:
        if r2 == rid and max(0, min(b, e) - max(a, s)) >= 0.5 * (b - a):
            return True
    return False


def build(conn):
    spans = pd.read_csv(SPANS)
    spans = spans[spans["thesis_scope"].astype(bool) & (spans["span_s"] <= 3600)]
    whole = pd.read_csv(WHOLE)
    recs = {int(r[0]): {"fs": float(r[1]), "n": int(r[2]), "label": r[3]}
            for r in conn.execute("SELECT id, fs, n_samples, source_file FROM recordings")}
    fs_of = {rid: v["fs"] for rid, v in recs.items()}
    human = [dict(r) for r in conn.execute(
        "SELECT s.id, s.recording_id, s.start_idx, s.end_idx, s.n_events, a.verdict FROM sequences s "
        "JOIN annotations a ON a.id = s.annotation_id WHERE s.origin = 'human' AND s.source_kind = 'annotation' "
        "AND a.deleted_at IS NULL AND a.verdict IN ('interesting', 'seed') ORDER BY s.id")]
    regions = [(h["recording_id"], h["start_idx"], h["end_idx"]) for h in human]
    ev = events_by_recording(spans, whole)

    chain_spans, skipped = [], Counter()
    for rid, members in chains(ev, fs_of):
        a, b = min(m[0] for m in members), max(m[1] for m in members)
        if covered(rid, a, b, regions):
            skipped["chain inside a hand-labelled sequence"] += 1
            continue
        chain_spans.append({"recording_id": rid, "start_idx": a, "end_idx": b,
                            "events": [{"start_idx": m[0], "end_idx": m[1]} for m in members],
                            "note": f"{len(members)} accepted drop events, each next top within 1 h",
                            "evidence": sorted({m[3] for m in members})})
    regions += [(c["recording_id"], c["start_idx"], c["end_idx"]) for c in chain_spans]

    multi_spans = []
    w = whole.set_index("event_id")
    for r in spans.itertuples(index=False):
        if r.event_id not in w.index or not isinstance(w.at[r.event_id, "whole_events"], str):
            continue
        e = json.loads(w.at[r.event_id, "whole_events"])
        if len(e) < 2:
            continue
        a = min(int(r.start_idx), min(int(x[0]) for x in e))
        b = max(int(r.end_idx), max(int(x[1]) for x in e))
        rid = int(r.recording_id)
        if covered(rid, a, b, regions):
            skipped["multi-event span inside a chain or hand-labelled sequence"] += 1
            continue
        multi_spans.append({"recording_id": rid, "start_idx": a, "end_idx": b,
                            "events": [{"start_idx": int(x[0]), "end_idx": int(x[1])} for x in e],
                            "note": f"an accepted span holding {len(e)} drop events", "source_ref": r.event_id,
                            "evidence": [r.event_id]})
    return human, chain_spans, multi_spans, skipped, recs


def describe(human, chain_spans, multi_spans, skipped, recs):
    ds = lambda rid: recs[rid]["label"].split("_fs")[0].replace("_aug_concat", "_aug").replace("_concat", "_concat")  # noqa: E731
    dur = lambda s: (s["end_idx"] - s["start_idx"]) / recs[s["recording_id"]]["fs"] / 3600.0  # noqa: E731
    return {
        "hand_labelled": len(human), "chains": len(chain_spans), "multi_event_spans": len(multi_spans),
        "total": len(human) + len(chain_spans) + len(multi_spans), "skipped": dict(skipped),
        "chain_events": sum(len(c["events"]) for c in chain_spans),
        "multi_span_events": sum(len(c["events"]) for c in multi_spans),
        "chains_by_recording": dict(Counter(ds(c["recording_id"]) for c in chain_spans)),
        "multi_by_recording": dict(Counter(ds(c["recording_id"]) for c in multi_spans)),
        "chain_hours_median": float(np.median([dur(c) for c in chain_spans])) if chain_spans else None,
        "chain_hours_max": float(max(dur(c) for c in chain_spans)) if chain_spans else None,
        "multi_events_histogram": dict(sorted(Counter(len(c["events"]) for c in multi_spans).items())),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    db = DB.replace("\\", "/")
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        human, chain_spans, multi_spans, skipped, recs = build(conn)
    finally:
        conn.close()
    summary = describe(human, chain_spans, multi_spans, skipped, recs)
    print(json.dumps(summary, indent=1))
    with open(os.path.join(OUT, "sequence_candidates.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "hand_labelled_ids": [h["id"] for h in human], "chains": chain_spans,
                   "multi_event_spans": multi_spans}, f, indent=1)
    if not args.apply:
        print("dry run: nothing written (pass --apply)")
        return
    from Working.database.schema import init_db
    from Working.review import sequence_queue as sq
    from Working.review.queues import queue_counts

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = os.path.join(ROOT, "DATA", "db", "backups", f"before_sequence_review_{stamp}.sqlite")
    with sqlite3.connect(DB) as src, sqlite3.connect(backup) as dst:
        src.backup(dst)
    print("backed up to", backup)
    conn = init_db(DB)                                   # the review_queues migration (it backs up again, its own way)
    try:
        out = sq.send_to_sequence_review(conn, spans=chain_spans, sequence_ids=[h["id"] for h in human],
                                         provenance="chain_accepted_1h", name=QUEUE_NAME)
        out2 = sq.send_to_sequence_review(conn, spans=multi_spans, provenance="multi_event_span", name=QUEUE_NAME)
        assert out2["queue_id"] == out["queue_id"]
        counts = queue_counts(conn, out["queue_id"])
        result = {"queue_id": out["queue_id"], "created_candidates": out["created"] + out2["created"],
                  "counts": counts, "backup": backup, **summary}
        with open(os.path.join(OUT, "sequence_queue.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, indent=1)
        print(json.dumps(result, indent=1))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
