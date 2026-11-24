"""
write_review_queue.py
=====================
The write half of ``build_review_queue.py --write`` (24 Nov 2026).

1. Back up the research database with the sqlite backup API, so the WAL comes along
   (``DATA/db/backups/before_autodetect_queue_<stamp>.sqlite``).
2. Add the chosen candidates as machine rows only:
   - one config (kind ``autodetect``);
   - per channel, one completed run per lane (`service.write_detections`), so two candidates that overlap never share
     a run and Review asks about each one;
   - one detection per candidate, its details in ``meta_json``.
3. Make one listed Review queue in priority order.

It never writes a verdict, and it refuses to make the queue twice. It checks that Review serves one item per
detection, then records everything it wrote in ``docs/autodetect/20261124_queue/written.json``.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import sqlite3

QUEUE_NAME = "Auto-detect · unreviewed drops and rises, 4 channels (24 Nov)"
NOTE = ("Auto-detect (v4) candidates on M2_aug CH7_B2, MJu26a CH14 and CH15 (the 2 Hz copies) and M4 CH1_A1 that you "
        "have not reviewed on any copy of the channel, with clean windows. In priority order: confidence, with members "
        "of sequences like M4's ranked as if 0.1 more confident. Built by scripts/autodetect/build_review_queue.py; "
        "what was left out and why: docs/autodetect/20261124_queue/README.md. A verdict here is yours; the candidate "
        "stays the machine's.")
#: The rule the candidates were made with (docs/autodetect/20261123_v4/*/run.json, rule_files).
WHOLE_DROP = {"commit": "79d0243e", "blob": "b860988e871a"}


def _num(v, nd=4):
    """A finite number rounded, else None (the database's JSON is read by a browser, which has no NaN)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return round(f, nd) if math.isfinite(f) else None


def backup(db):
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(os.path.dirname(os.path.abspath(db)), "backups", f"before_autodetect_queue_{stamp}.sqlite")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    src, dst = sqlite3.connect(db), sqlite3.connect(path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        raise SystemExit(f"the backup at {path} was not written; nothing else was done")
    return path


def write(p, *, db, out, settings):
    from Working.autodetect import service
    from Working.database import runs as R
    from Working.review import queues as Q

    sel = p["selected"].sort_values("rank")
    conn = sqlite3.connect(db, timeout=60)
    conn.row_factory = sqlite3.Row
    try:
        dup = conn.execute("SELECT id FROM review_queues WHERE name = ?", (QUEUE_NAME,)).fetchone()
    finally:
        conn.close()
    if dup is not None:
        raise SystemExit(f"queue {dup['id']} is already called {QUEUE_NAME!r}; not writing it twice")
    path = backup(db)
    conn = sqlite3.connect(db, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 60000")
    try:
        cfg = {"kind": "autodetect", "version": "v4", "build": "review_queue_20261124",
               "candidates_from": "docs/autodetect/20261123_v4", "whole_drop": WHOLE_DROP, "selection": settings}
        cfg_id, _h = R.get_or_create_config(conn, cfg)
        det_of_rank, runs_of = {}, {}
        for ref, g in sel.groupby("ref", sort=False):
            g = g.sort_values("rank")
            boxes = [{"start_idx": int(r.start_idx), "end_idx": int(r.end_idx), "score": _num(r.confidence),
                      "meta": {"source": "autodetect", "build": "review_queue_20261124", "ref": ref,
                               "candidate_id": int(r.candidate_id), "rank": int(r.rank), "polarity": r.polarity,
                               "confidence": _num(r.confidence), "priority": _num(r.priority),
                               "m4_like": bool(r.m4_like), "clarity": _num(r.clarity, 1),
                               "noise_free": bool(r.clarity == math.inf), "p_r4": _num(r.p_r4),
                               "sources": r.sources if isinstance(r.sources, str) else "",
                               "sequence_id": int(r.sequence_id) if r.sequence_id == r.sequence_id else -1,
                               "depth_mv": _num(r.depth_mv, 3), "sharpness": _num(r.sharpness, 1)}}
                     for r in g.itertuples(index=False)]
            ids, run_ids = service.write_detections(conn, int(g["rec"].iloc[0]), boxes, config_id=cfg_id,
                                                    name=f"Auto-detect queue 24 Nov · {ref}")
            det_of_rank.update(zip(g["rank"].tolist(), ids))
            runs_of[ref] = run_ids
        conn.commit()
        det_ids = [det_of_rank[int(r)] for r in sel["rank"]]
        qid = Q.create_queue(conn, name=QUEUE_NAME, source_kind="discovery-run",
                             filters={"detection_ids": det_ids, "order": "listed"}, note=NOTE)
        conn.commit()
        every = Q.queue_items(conn, qid, include_prior_judged=True)
        asked = Q.queue_items(conn, qid)
        ckpt = conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
    finally:
        conn.close()
    rec = {"written": dt.datetime.now().isoformat(timespec="seconds"), "backup": path, "queue_id": int(qid),
           "queue_name": QUEUE_NAME, "config_id": int(cfg_id), "detections": len(det_ids),
           "first_detection_id": min(det_ids), "last_detection_id": max(det_ids), "runs": runs_of,
           "review_items": len(every), "review_items_asked": len(asked),
           "held_back_by_review": len(every) - len(asked),
           "one_item_per_detection": len(every) == len(det_ids), "wal_checkpoint": list(ckpt) if ckpt else None}
    with open(os.path.join(out, "written.json"), "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
    return rec


def _boxes(g, ref):
    return [{"start_idx": int(r.start_idx), "end_idx": int(r.end_idx), "score": _num(r.confidence),
             "meta": {"source": "autodetect", "build": "review_queue_20261124", "ref": ref,
                      "candidate_id": int(r.candidate_id), "rank": int(r.rank), "polarity": r.polarity,
                      "confidence": _num(r.confidence), "priority": _num(r.priority), "m4_like": bool(r.m4_like),
                      "clarity": _num(r.clarity, 1), "noise_free": bool(r.clarity == math.inf),
                      "p_r4": _num(r.p_r4), "sources": r.sources if isinstance(r.sources, str) else "",
                      "sequence_id": int(r.sequence_id) if r.sequence_id == r.sequence_id else -1,
                      "depth_mv": _num(r.depth_mv, 3), "sharpness": _num(r.sharpness, 1)}}
            for r in g.itertuples(index=False)]


def update(p, *, db, out, settings, reason):
    """Bring the written queue in line with a new plan: take the candidates the plan no longer picks off the queue's
    list (their machine rows stay, unqueued, as most detections are; a candidate with a verdict stays on the list),
    write the newly picked ones as machine rows in runs of their own, and list everything in the new plan's order.
    Backs up first. Records the change in written.json under ``updates``."""
    from Working.autodetect import service
    from Working.database import runs as R
    from Working.review import queues as Q

    sel = p["selected"].sort_values("rank")
    conn = sqlite3.connect(db, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 60000")
    try:
        q = conn.execute("SELECT id, filters_json FROM review_queues WHERE name = ?", (QUEUE_NAME,)).fetchone()
        if q is None:
            raise SystemExit(f"no queue called {QUEUE_NAME!r} to update; write it first")
        qid, filters = int(q["id"]), json.loads(q["filters_json"] or "{}")
        listed = [int(i) for i in filters.get("detection_ids") or []]
        key_of = {}
        for chunk in range(0, len(listed), 900):
            ids = listed[chunk:chunk + 900]
            for r in conn.execute("SELECT id, meta_json FROM detections WHERE id IN (" + ",".join("?" * len(ids)) + ")", ids):
                m = json.loads(r["meta_json"] or "{}")
                key_of[int(r["id"])] = (m.get("ref"), int(m.get("candidate_id", -1)))
        judged = {int(r[0]) for chunk in range(0, len(listed), 900) for r in conn.execute(
            "SELECT DISTINCT detection_id FROM adjudications WHERE detection_id IN (" +
            ",".join("?" * len(listed[chunk:chunk + 900])) + ")", listed[chunk:chunk + 900])}
    finally:
        conn.close()
    want = list(zip(sel["ref"], sel["candidate_id"].astype(int)))
    have = {k: d for d, k in key_of.items()}
    removed = [d for d, k in key_of.items() if k not in set(want) and d not in judged]
    kept_judged = [d for d, k in key_of.items() if k not in set(want) and d in judged]
    to_add = sel[[k not in have for k in want]]
    path = backup(db)
    conn = sqlite3.connect(db, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 60000")
    try:
        cfg_id, _h = R.get_or_create_config(conn, {"kind": "autodetect", "version": "v4",
                                                   "build": "review_queue_20261124",
                                                   "candidates_from": "docs/autodetect/20261123_v4",
                                                   "whole_drop": WHOLE_DROP, "selection": settings})
        added, runs_added = {}, {}
        for ref, g in to_add.groupby("ref", sort=False):
            g = g.sort_values("rank")
            ids, run_ids = service.write_detections(conn, int(g["rec"].iloc[0]), _boxes(g, ref), config_id=cfg_id,
                                                    name=f"Auto-detect queue 24 Nov · {ref} · additions")
            added.update({(ref, int(c)): d for c, d in zip(g["candidate_id"], ids)})
            runs_added[ref] = run_ids
        conn.commit()
        ids_of = {**have, **added}
        order = [ids_of[k] for k in want] + kept_judged
        filters["detection_ids"] = order
        filters["order"] = "listed"
        conn.execute("UPDATE review_queues SET filters_json = ? WHERE id = ?", (json.dumps(filters), qid))
        conn.commit()
        every = Q.queue_items(conn, qid, include_prior_judged=True)
        asked = Q.queue_items(conn, qid)
        ckpt = conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
    finally:
        conn.close()
    rec_path = os.path.join(out, "written.json")
    with open(rec_path, encoding="utf-8") as fh:
        rec = json.load(fh)
    rec.setdefault("updates", []).append({
        "at": dt.datetime.now().isoformat(timespec="seconds"), "why": reason, "backup": path,
        "taken_off_the_list": sorted(removed), "kept_because_judged": sorted(kept_judged),
        "added_detection_ids": sorted(added.values()), "runs_added": runs_added, "listed_now": len(order),
        "review_items": len(every), "review_items_asked": len(asked), "held_back_by_review": len(every) - len(asked),
        "one_item_per_detection": len(every) == len(order), "wal_checkpoint": list(ckpt) if ckpt else None,
        "note": "meta_json 'rank' is the rank when the row was written; the queue's list is the plan's current order"})
    with open(rec_path, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
    return rec["updates"][-1]
