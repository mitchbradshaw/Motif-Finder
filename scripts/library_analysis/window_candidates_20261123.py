"""The interesting 10-minute windows as candidates (2026-11-23; the researcher: "Yes, add them").

In plain words: in August the researcher swept 11,234 ten-minute windows of M2_aug and called 2,333 of them
interesting. None became an accepted event span (the catalogue keeps fixed windows as context), and only 97 hold an
accepted event's onset. This puts them into the review pipeline:

1. windows that touch on one channel are merged into one REGION, so a drop crossing a window edge is not cut in two;
2. the drops inside each region are listed by the approved whole-drop rule (`Working.interrogation.whole_drop`,
   `span_events`: one unbroken fall per event, ended by a pause or a rebound);
3. a region holding TWO OR MORE drops is a sequence candidate and goes to a sequence-review queue of its own
   ("Sequences · interesting 10-min windows"), unless half or more of it already lies inside one of queue 48's
   candidates;
4. a region holding ONE drop is a single-event candidate: kept in `window_single_events.json` for the
   candidate-event queue that follows queue 48 (one drop is not a sequence);
5. a region holding none is counted.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/library_analysis/window_candidates_20261123.py
    ... --apply     backs the database up and sends the multi-drop regions to queue 48

Read-only without --apply. With it, writes machine `sequences` rows + `sequence_members` and widens the queue,
through `Working.review.sequence_queue.send_to_sequence_review` - no human verdict is written.
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

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from Working.interrogation import whole_drop as WD  # noqa: E402

DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite")
OUT = os.path.join(ROOT, "docs", "library_analysis", "20261123")
QUEUE_NAME = "Sequences · candidates (23 Nov)"          # queue 48: what is already asked about
TARGET_NAME = "Sequences · interesting 10-min windows (23 Nov)"   # these go to a queue of their own, so queue
# 48's 500 keep a clean progress count; a region mostly inside one of queue 48's candidates is still left out
PROVENANCE = "interesting_10min_window"
TARGET_NOTE = ("Is each region a sequence? Interesting 10-min windows of M2_aug (merged where they touch) holding two "
               "or more drops by the whole-drop rule. Candidates are machine proposals; an accepted one is stored as a "
               "human sequence in the Library. Windows holding one drop wait for the candidate-event queue.")


def to_mv(units):
    return {"mV": 1.0, "uV": 0.001}.get(units or "V", 1000.0)


def regions(conn):
    """Interesting 10-min windows merged where they touch on one recording: `[(rid, start, end, [annotation ids])]`."""
    out = []
    cur = None
    for r in conn.execute("SELECT id, recording_id, start_idx, end_idx FROM annotations WHERE deleted_at IS NULL "
                          "AND source = 'imported_10min' AND verdict IN ('interesting', 'seed') "
                          "ORDER BY recording_id, start_idx"):
        aid, rid, a, b = int(r[0]), int(r[1]), int(r[2]), int(r[3])
        if cur is not None and cur[0] == rid and a <= cur[2]:
            cur = (rid, cur[1], max(cur[2], b), cur[3] + [aid])
            continue
        if cur is not None:
            out.append(cur)
        cur = (rid, a, b, [aid])
    if cur is not None:
        out.append(cur)
    return out


def queued(conn, name):
    """`(queue_id, [(rid, start, end)])` of the open sequence-review queue called `name`."""
    row = conn.execute("SELECT id, filters_json FROM review_queues WHERE closed_at IS NULL AND source_kind = "
                       "'sequence-review' AND name = ? ORDER BY id DESC LIMIT 1", (name,)).fetchone()
    if row is None:
        raise SystemExit(f"no open sequence-review queue called {name!r}")
    ids = json.loads(row[1] or "{}").get("sequence_ids") or []
    spans = []
    for k in range(0, len(ids), 400):
        chunk = ids[k:k + 400]
        spans += [(int(r[0]), int(r[1]), int(r[2])) for r in conn.execute(
            f"SELECT recording_id, start_idx, end_idx FROM sequences WHERE id IN ({','.join('?' * len(chunk))})",
            chunk)]
    return int(row[0]), spans


def covered(rid, a, b, spans):
    return any(r2 == rid and max(0, min(b, e) - max(a, s)) >= 0.5 * (b - a) for r2, s, e in spans)


def build(conn):
    recs = {int(r[0]): {"npy": r[1], "fs": float(r[2]), "units": r[3]}
            for r in conn.execute("SELECT id, npy_path, fs, units FROM recordings")}
    qid, spans = queued(conn, QUEUE_NAME)
    multi, single, counts = [], [], Counter()
    cache = {}
    regs = regions(conn)
    for rid, a, b, ann in regs:
        rec = recs[rid]
        if rid not in cache:
            cache[rid] = np.load(os.path.join(ROOT, rec["npy"]), mmap_mode="r")
        x = cache[rid]
        if not np.all(np.isfinite(np.asarray(x[a:b], dtype=float))):
            counts["regions with gaps (not measured)"] += 1
            continue
        events = WD.span_events(x, a, b, rec["fs"], to_mv=to_mv(rec["units"]))
        n = len(events)
        counts[f"{min(n, 6)}{'+' if n >= 6 else ''} drops"] += 1
        label = (f"{n} drops inside an interesting 10-min window" if len(ann) == 1
                 else f"{n} drops inside a run of {len(ann)} touching interesting 10-min windows")
        if n >= 2:
            if covered(rid, a, b, spans):
                counts["multi-drop regions already inside a queued candidate"] += 1
                continue
            multi.append({"recording_id": rid, "start_idx": a, "end_idx": b,
                          "events": [{"start_idx": int(e["top_idx"]), "end_idx": int(e["bottom_idx"])} for e in events],
                          "note": label, "source_ref": str(ann[0]), "evidence": ann})
        elif n == 1:
            e = events[0]
            single.append({"recording_id": rid, "window_start_idx": a, "window_end_idx": b, "windows": ann,
                           "top_idx": int(e["top_idx"]), "bottom_idx": int(e["bottom_idx"]),
                           "depth_mv": round(float(e["depth_mv"]), 4), "fall_s": round(float(e["fall_s"]), 2)})
    summary = {"interesting_windows": sum(len(r[3]) for r in regs), "regions": len(regs),
               "regions_by_window_count": dict(sorted(Counter(len(r[3]) for r in regs).items())),
               "drops_per_region": dict(sorted(counts.items())),
               "multi_drop_candidates": len(multi), "multi_drop_events": sum(len(m["events"]) for m in multi),
               "single_drop_windows": len(single), "queue_id": qid}
    return summary, multi, single


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    db = DB.replace("\\", "/")
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        summary, multi, single = build(conn)
    finally:
        conn.close()
    print(json.dumps(summary, indent=1))
    with open(os.path.join(OUT, "window_candidates.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "multi_drop_regions": multi}, f, indent=1)
    with open(os.path.join(OUT, "window_single_events.json"), "w", encoding="utf-8") as f:
        json.dump({"note": "interesting 10-min windows (merged where touching) holding ONE drop event (whole-drop "
                           "rule): single-event candidates for the candidate-event queue that follows queue 48",
                   "events": single}, f, indent=1)
    if not args.apply:
        print("dry run: nothing written (pass --apply)")
        return
    from Working.review import sequence_queue as sq
    from Working.review.queues import queue_counts

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = os.path.join(ROOT, "DATA", "db", "backups", f"before_window_candidates_{stamp}.sqlite")
    with sqlite3.connect(DB) as src, sqlite3.connect(backup) as dst:
        src.backup(dst)
    print("backed up to", backup)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        out = sq.send_to_sequence_review(conn, spans=multi, provenance=PROVENANCE, name=TARGET_NAME, note=TARGET_NOTE)
        result = {**summary, "queue_id": out["queue_id"], "created_candidates": out["created"],
                  "counts": queue_counts(conn, out["queue_id"]), "backup": backup}
        with open(os.path.join(OUT, "window_candidates_applied.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, indent=1)
        print(json.dumps(result, indent=1))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
