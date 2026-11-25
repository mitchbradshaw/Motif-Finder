"""
candidate_events_20261123.py
============================
The candidate-event queues (23 Nov): every drop event inside the candidate sequences of queues 48 and 49, and the
one-drop interesting 10-minute windows, put to the researcher one event at a time.

In plain words
--------------
Queues 48 and 49 ask "is this a sequence?" of whole stretches. These queues ask the next question, of each drop
inside them: "is this drop interesting?". The drops are found by the Library's whole-drop rule
(`Working.interrogation.whole_drop.span_events`, as committed in 79d0243e). Each becomes a machine detection whose
box runs from the drop's top to where it has climbed half-way back - or, when it does not, its bottom - plus a fifth
of that length each side (the researcher, 23 Nov, after reviewing the first build: "padding +- about 10% to fully
capture the drop", on top of the tenth the first build had).

Left out (v2, the researcher's review of the first build, 23 Nov):
  - a drop shorter than MIN_CORE_SAMPLES samples from top to half recovery (or bottom): "omit any drops that are
    less than 5 samples" - a 4-sample blip is noise;
  - a drop shallower than MIN_QUEUE_SIGMAS x its channel's noise (the robust sample-to-sample spread over the hour
    round it). On the 44 window drops judged in the first build this kept all 12 interesting ones and removed 19 of
    the 25 not-interesting ones; it removed none of the 561 judged sequence drops;
  - a drop the researcher has already judged:
      - judged in an earlier build of these queues (its fall overlaps a judged detection's) - "not re-including what
        I have already reviewed";
      - the same event (IoU >= 0.5 of the boxes) as any judged machine detection, any verdict;
      - the ONLY drop in a span the researcher judged as an event - an accepted catalogue span, or a span drawn in
        Review, the Library or the Excel catalogue, of any verdict - or lying mostly inside such a span. A span
        holding several drops was judged as a whole, so its drops stay in. The window labels - the imported
        10-minute windows and the blind-test windows - judge a window, not a drop, and leave its drops in;
      - and Review's own matching rule (`queues._prior_verdicts`), which Review applies again whenever it serves.
A drop found twice (two overlapping candidates; their falls overlap) is put once.

One drop, one item. Review serves the overlapping detections of ONE run on one channel as one item (an overlap set,
judged with one key press). The padded boxes of neighbouring drops may overlap, so neighbouring drops go into
different runs ("lanes": a box joins the first run on its channel whose boxes it does not touch). A verdict carries
across runs only to the same event (the scoreboard's matching rule), never to a neighbour.

Two queues, like 48 and 49: the drops in the candidate sequences of queue 48 (the hand-labelled sequences, then the
chains of accepted drops, then the spans holding several drops), and the drops in the interesting 10-minute windows
(queue 49's regions, then the one-drop windows). Within a candidate, its drops in time order. The candidates' own
verdicts are not waited for: each drop is judged on its own, and accepted drops join their sequence once the
sequence itself is accepted.

Dry run by default (database read-only; writes `docs/library_analysis/20261123/candidate_events.json`). With
--apply it backs the database up; CLOSES the earlier builds' queues, keeping in each only the items already judged
(so the record of those verdicts stays), and deletes the earlier builds' detections that carry no verdict; then
writes the new detections and the two new listed queues. Detections only - no verdict is written or removed
(CLAUDE.md rule 5).

    PYTHONIOENCODING=utf-8 "$PY" scripts/library_analysis/candidate_events_20261123.py [--apply]
"""
from __future__ import annotations

import argparse
import bisect
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

from Working.database import runs as _runs  # noqa: E402
from Working.discovery.spans import absolute_bounds  # noqa: E402
from Working.interrogation import whole_drop as WD  # noqa: E402
from Working.review import queues as _queues  # noqa: E402

DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite")
OUT = os.path.join(ROOT, "docs", "library_analysis", "20261123")
SINGLES = os.path.join(OUT, "window_single_events.json")
CATALOGUE = os.path.join(ROOT, "docs", "thesis", "data", "accepted_catalogue_20261109", "accepted_spans.csv")
WINDOW_LABELS = ("imported_10min", "blind_test_review")
SOURCE_QUEUES = (48, 49)
MARGIN_FRAC = 0.2
MIN_CORE_SAMPLES = 5
MIN_QUEUE_SIGMAS = 15.0
NOISE_HALF_S = 1800.0
SAME_EVENT_IOU = 0.5
KIND = "candidate-events"
VERSION = "v2"
RUN_NAME = "candidate events v2 (whole drop)"
GROUPS = ("hand_labelled", "chain_accepted_1h", "multi_event_span", "interesting_10min_window", "one_drop_window")
BOX_NOTE = ("Each item is one drop event found by the whole-drop rule, boxed from its top to its half recovery (or "
            "its bottom) plus a fifth each side. Drops under 5 samples or under 15x their channel's noise are left "
            "out. Judge the drop itself. Drops of one candidate come together, in time order.")
QUEUES = (
    ("Events · drops in candidate sequences (v2, 23 Nov)", ("hand_labelled", "chain_accepted_1h", "multi_event_span"),
     "The drops inside queue 48's candidate sequences not yet judged: your hand-labelled sequences first, then the "
     "chains of accepted drops, then the accepted spans holding several drops. " + BOX_NOTE),
    ("Events · drops in interesting 10-min windows (v2, 23 Nov)", ("interesting_10min_window", "one_drop_window"),
     "The drops inside queue 49's interesting 10-minute regions not yet judged, then the one-drop interesting "
     "windows. " + BOX_NOTE),
)
#: the earlier builds' queues, closed (keeping their judged items) when this build is applied
REPLACES = ("Events · drops in candidate sequences (23 Nov)", "Events · drops in interesting 10-min windows (23 Nov)")


def to_mv(units):
    return {"mV": 1.0, "uV": 0.001}.get(units or "V", 1000.0)


def candidates(conn):
    """The candidate sequences of queues 48 and 49, in group order, then by recording and time."""
    out = []
    for qid in SOURCE_QUEUES:
        ids = json.loads(conn.execute("SELECT filters_json FROM review_queues WHERE id = ?",
                                      (qid,)).fetchone()[0])["sequence_ids"]
        marks = ",".join("?" * len(ids))
        for sid, origin, kind, rid, a, b in conn.execute(
                f"SELECT id, origin, source_kind, recording_id, start_idx, end_idx FROM sequences "
                f"WHERE id IN ({marks})", ids):
            group = "hand_labelled" if origin == "human" else kind
            out.append({"group": group, "queue": qid, "sequence_id": int(sid), "recording_id": int(rid),
                        "start": int(a), "end": int(b)})
    with open(SINGLES, encoding="utf-8") as f:
        for n, e in enumerate(json.load(f)["events"]):
            out.append({"group": "one_drop_window", "queue": None, "sequence_id": None, "window": n,
                        "recording_id": int(e["recording_id"]), "start": int(e["window_start_idx"]),
                        "end": int(e["window_end_idx"])})
    unknown = {c["group"] for c in out} - set(GROUPS)
    if unknown:
        raise ValueError(f"candidates of unknown provenance: {sorted(unknown)}")
    return sorted(out, key=lambda c: (GROUPS.index(c["group"]), c["recording_id"], c["start"]))


def core(e):
    """`(top, end)`: the drop from its top to its half recovery, or to its bottom when it does not recover."""
    top = int(e["top_idx"])
    return top, int(e["recovery_idx"]) if np.isfinite(e["recovery_idx"]) else int(e["bottom_idx"])


def box(top, end, n):
    """The core plus a fifth of its length each side (at least one sample)."""
    m = max(1, int(round(MARGIN_FRAC * max(end - top, 1))))
    return max(0, top - m), min(n, end + m + 1)


def iou(a0, a1, b0, b1):
    inter = min(a1, b1) - max(a0, b0)
    return inter / (max(a1, b1) - min(a0, b0)) if inter > 0 else 0.0


def judged_drops(conn, recs, arrays):
    """`({recording: sorted [(top, bottom)]}, {recording: sorted [(start, end)]})`: the drops the researcher judged
    as events - the only drop in an accepted catalogue span, or in a span drawn in Review, the Library or the Excel
    catalogue (any verdict) - and those spans themselves."""
    spans = [(int(r.recording_id), int(r.start_idx), int(r.end_idx)) for r in pd.read_csv(CATALOGUE).itertuples()]
    marks = ",".join("?" * len(WINDOW_LABELS))
    spans += [(int(r[0]), int(r[1]), int(r[2])) for r in conn.execute(
        f"SELECT recording_id, start_idx, end_idx FROM annotations WHERE deleted_at IS NULL "
        f"AND (source IS NULL OR source NOT IN ({marks}))", WINDOW_LABELS)]
    out, held = {}, {}
    for rid, a, b in sorted(set(spans)):
        rec = recs[rid]
        x = arrays.setdefault(rid, np.load(os.path.join(ROOT, rec["npy"]), mmap_mode="r"))
        if b - a < 4 or not np.all(np.isfinite(np.asarray(x[a:b], dtype=float))):
            continue
        m = WD.measure(x, a, b, rec["fs"], to_mv=to_mv(rec["units"]))
        if m.get("ok") and m["n_events"] == 1:
            out.setdefault(rid, []).append((int(m["top_idx"]), int(m["bottom_idx"])))
            held.setdefault(rid, []).append((a, b))
    return {rid: sorted(v) for rid, v in out.items()}, {rid: sorted(v) for rid, v in held.items()}


def judged_detections(conn):
    """`({recording: sorted [(start, end)]}, {recording: sorted [(top, bottom)]})`: every machine detection with a
    verdict (any, carried or not), channel-absolute; and, for those from earlier builds of these queues, the drop
    each one stood for (its top and bottom)."""
    rows = conn.execute(
        "SELECT r.recording_id, d.start_idx, d.end_idx, r.span_start, d.meta_json, c.config_json "
        "FROM detections d JOIN runs r ON r.id = d.run_id JOIN configs c ON c.id = r.config_id "
        "WHERE d.id IN (SELECT detection_id FROM adjudications)").fetchall()
    spans, drops = {}, {}
    for rid, s0, e0, span0, meta, cfg in rows:
        a, b = absolute_bounds(s0, e0, span0)
        spans.setdefault(int(rid), []).append((int(a), int(b)))
        if KIND in (cfg or "") and meta:
            m = json.loads(meta)
            drops.setdefault(int(rid), []).append((int(m["top_idx"]), int(m["bottom_idx"])))
    return {k: sorted(v) for k, v in spans.items()}, {k: sorted(v) for k, v in drops.items()}


def same_event(table, rid, a, b):
    """True when [a, b) is the same event (IoU >= SAME_EVENT_IOU) as any interval of `table[rid]`."""
    spans = table.get(rid) or []
    i = bisect.bisect_left(spans, (a - 4 * max(b - a, 1), -1))
    for s, e in spans[i:]:
        if s > b:
            return False
        if iou(a, b, s, e) >= SAME_EVENT_IOU:
            return True
    return False


def overlaps(table, rid, a, b):
    """True when [a, b] overlaps any interval of `table[rid]` (sharing more than an end point)."""
    spans = table.get(rid) or []
    i = bisect.bisect_right(spans, (b, b))
    return any(min(b, e) > max(a, s) for s, e in spans[max(0, i - 50):i])


def mostly_inside(table, rid, a, b):
    """True when at least half of [a, b) lies inside one interval of `table[rid]`."""
    spans = table.get(rid) or []
    i = bisect.bisect_right(spans, (b, b))
    return any(min(b, e) - max(a, s) >= 0.5 * max(b - a, 1) for s, e in spans[max(0, i - 50):i])


def lanes(items):
    """Each item's `lane`: the first run on its recording whose boxes it does not touch (a greedy interval colouring),
    so no two detections of one run overlap and Review serves every drop as its own item."""
    by = {}
    for it in items:
        by.setdefault(it["recording_id"], []).append(it)
    for mine in by.values():
        ends = []
        for it in sorted(mine, key=lambda it: (it["start"], it["end"])):
            lane = next((k for k, e in enumerate(ends) if e <= it["start"]), len(ends))
            if lane == len(ends):
                ends.append(it["end"])
            else:
                ends[lane] = it["end"]
            it["lane"] = lane


def build(conn):
    recs = {int(r[0]): {"npy": r[1], "fs": float(r[2]), "units": r[3], "n": int(r[4])}
            for r in conn.execute("SELECT id, npy_path, fs, units, n_samples FROM recordings")}
    cands = candidates(conn)
    items, kept, arrays = [], {}, {}
    found, skipped = Counter(), Counter()
    judged, held = judged_drops(conn, recs, arrays)
    judged_spans, reviewed = judged_detections(conn)
    for c in cands:
        rid, rec = c["recording_id"], recs[c["recording_id"]]
        x = arrays.setdefault(rid, np.load(os.path.join(ROOT, rec["npy"]), mmap_mode="r"))
        events = WD.span_events(x, c["start"], c["end"], rec["fs"], to_mv=to_mv(rec["units"]))
        found[c["group"]] += len(events)
        for k, e in enumerate(events):
            top, bottom = int(e["top_idx"]), int(e["bottom_idx"])
            mine = kept.setdefault(rid, [])
            i = bisect.bisect_left(mine, (top - (bottom - top) * 4, -1))
            if any(min(bottom, b) > max(top, t) for t, b in mine[max(0, i - 2):i + 40]):
                continue                                   # its fall overlaps one already put: the same drop again
            bisect.insort(mine, (top, bottom))
            t0, t1 = core(e)
            if t1 - t0 < MIN_CORE_SAMPLES:
                skipped[f"shorter than {MIN_CORE_SAMPLES} samples"] += 1
                continue
            h = int(NOISE_HALF_S * rec["fs"])
            sigma = WD.noise_sigma(np.asarray(x[max(0, top - h):top + h], dtype=float) * to_mv(rec["units"]))
            if e["depth_mv"] < MIN_QUEUE_SIGMAS * sigma:
                skipped[f"under {MIN_QUEUE_SIGMAS:g}x its channel's noise"] += 1
                continue
            s, t = box(t0, t1, rec["n"])
            if overlaps(reviewed, rid, top, bottom):
                skipped["judged in an earlier build of these queues"] += 1
                continue
            if same_event(judged_spans, rid, s, t):
                skipped["the same event as a judged detection"] += 1
                continue
            if same_event(judged, rid, top, bottom) or mostly_inside(held, rid, top, bottom):
                skipped["the only drop of a span judged as an event"] += 1
                continue
            items.append({"group": c["group"], "source_queue": c["queue"], "sequence_id": c["sequence_id"],
                          "window": c.get("window"), "event_in_candidate": k, "recording_id": rid,
                          "start": s, "end": t, "top_idx": top, "bottom_idx": bottom,
                          "depth_mv": round(float(e["depth_mv"]), 4),
                          "depth_sigmas": round(float(e["depth_mv"]) / sigma, 1) if sigma else None,
                          "fall_s": round(float(e["fall_s"]), 1), "long_tail": bool(e["long_tail"])})
    rows = [{"id": n, "run_id": -1, "recording_id": it["recording_id"], "start_idx": it["start"],
             "end_idx": it["end"]} for n, it in enumerate(items)]
    prior = set(_queues._prior_verdicts(conn, rows))
    skipped["Review's matching rule"] = len(prior)
    served = [it for n, it in enumerate(items) if n not in prior]
    lanes(served)
    for name, groups, _ in QUEUES:
        mine = [it for it in served if it["group"] in groups]
        for rank, it in enumerate(mine, start=1):
            it["queue"], it["serve_rank"] = name, rank
    summary = {"candidates": dict(Counter(c["group"] for c in cands)), "drops_found": dict(found),
               "left_out": dict(skipped), "to_review": len(served),
               "to_review_by_queue": dict(Counter(it["queue"] for it in served)),
               "to_review_by_group": dict(Counter(it["group"] for it in served)),
               "recordings": len({it["recording_id"] for it in served}),
               "runs": len({(it["recording_id"], it["lane"]) for it in served}),
               "long_tail": sum(it["long_tail"] for it in served)}
    return summary, served


def retire_earlier(conn):
    """Close the earlier builds' queues, each keeping only its judged items, and delete the earlier builds'
    detections that carry no verdict (and the runs and configs left empty). Returns what it did."""
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    done = {"closed": {}, "deleted_detections": 0, "deleted_runs": 0, "deleted_configs": 0}
    marks = ",".join("?" * len(REPLACES))
    with conn:
        for qid, name, f, note in conn.execute(
                f"SELECT id, name, filters_json, note FROM review_queues WHERE source_kind = 'discovery-run' "
                f"AND closed_at IS NULL AND name IN ({marks})", REPLACES).fetchall():
            ids = json.loads(f)["detection_ids"]
            have = {int(r[0]) for r in conn.execute(
                "SELECT DISTINCT detection_id FROM adjudications WHERE detection_id IN ({})".format(
                    ",".join("?" * len(ids))), ids)} if ids else set()
            keep = [d for d in ids if d in have]
            filters = dict(json.loads(f), detection_ids=keep)
            conn.execute("UPDATE review_queues SET filters_json = ?, closed_at = ?, note = ? WHERE id = ?",
                         (json.dumps(filters), now, (note or "") + f" Replaced by the {VERSION} build ({now[:10]}): "
                          f"holds the {len(keep)} items judged before then.", qid))
            done["closed"][int(qid)] = {"name": name, "judged_kept": len(keep), "of": len(ids)}
        old_runs = [int(r[0]) for r in conn.execute(
            "SELECT r.id FROM runs r JOIN configs c ON c.id = r.config_id WHERE c.config_json LIKE ?",
            (f"%{KIND}%",))]
        for i in range(0, len(old_runs), 400):
            chunk = old_runs[i:i + 400]
            done["deleted_detections"] += conn.execute(
                "DELETE FROM detections WHERE run_id IN ({}) AND id NOT IN (SELECT detection_id FROM "
                "adjudications)".format(",".join("?" * len(chunk))), chunk).rowcount
        done["deleted_runs"] = conn.execute(
            "DELETE FROM runs WHERE config_id IN (SELECT id FROM configs WHERE config_json LIKE ?) AND id NOT IN "
            "(SELECT DISTINCT run_id FROM detections)", (f"%{KIND}%",)).rowcount
        done["deleted_configs"] = conn.execute(
            "DELETE FROM configs WHERE config_json LIKE ? AND id NOT IN (SELECT DISTINCT config_id FROM runs)",
            (f"%{KIND}%",)).rowcount
    return done


def write(conn, items, stamp):
    """One machine run per recording and lane, a detection per item in serving order, the two listed queues."""
    cfg_id, _ = _runs.get_or_create_config(conn, {"kind": KIND, "version": VERSION, "stamp": stamp,
                                                   "rule_commit": "79d0243e",
                                                   "box": "top->half recovery or bottom, +20% each side",
                                                   "min_core_samples": MIN_CORE_SAMPLES,
                                                   "min_queue_sigmas": MIN_QUEUE_SIGMAS})
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
            meta = {k: it[k] for k in ("group", "sequence_id", "top_idx", "bottom_idx", "depth_mv", "depth_sigmas",
                                       "long_tail")}
            run_id = run_of[(it["recording_id"], it["lane"])]
            cur = conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score, meta_json) "
                               "VALUES (?, ?, ?, NULL, ?)", (run_id, it["start"], it["end"], json.dumps(meta)))
            it["detection_id"], it["run_id"] = int(cur.lastrowid), run_id
    queue_ids = {}
    for name, groups, note in QUEUES:
        ids = [it["detection_id"] for it in items if it["group"] in groups]
        queue_ids[name] = int(_queues.create_queue(conn, name=name, source_kind="discovery-run",
                                                   filters={"detection_ids": ids, "order": "listed"}, note=note))
    conn.commit()
    return {"queue_ids": queue_ids, "config_id": cfg_id, "runs": len(run_of)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--apply", action="store_true",
                    help="back up the database, retire the earlier build, write the runs and the queues")
    args = ap.parse_args()
    conn = sqlite3.connect(f"file:{DB.replace(os.sep, '/')}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row                          # Review's matching rule reads rows by name
    try:
        summary, items = build(conn)
    finally:
        conn.close()
    print(json.dumps(summary, indent=1))
    with open(os.path.join(OUT, "candidate_events.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "items": items}, f, indent=1)
    if not args.apply:
        print("dry run: nothing written to the database (pass --apply)")
        return
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = os.path.join(ROOT, "DATA", "db", "backups", f"before_candidate_events_{VERSION}_{stamp}.sqlite")
    with sqlite3.connect(DB) as src, sqlite3.connect(backup) as dst:
        src.backup(dst)
    print("backed up to", backup)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        retired = retire_earlier(conn)
        out = write(conn, items, stamp)
    finally:
        conn.close()
    result = {**summary, "retired": retired, **out, "backup": backup, "stamp": stamp}
    with open(os.path.join(OUT, "candidate_events_applied.json"), "w", encoding="utf-8") as f:
        json.dump({**result, "items": items}, f, indent=1)
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
