"""
promote_blind_accepted.py — put the accepted events of blind queues 25 and 28 in the Library, verdict-free
(researcher, 2026-10-26, Q5 A).

Which detections: every detection id in queue 25's and queue 28's `filters_json.detection_ids` whose newest OWN
adjudication (`carried_from IS NULL`) is `interesting` or `seed`. A carried copy is not a look and is ignored.
Which recordings: only ACTIVE ones (`recordings.active = 1`), never the held-out M4_aug_concat_fs1 nor
L_R_Aug_26_PD_raw (humidity-actuator contamination). Queue 28's L_LM_Jul_26_J_raw_fs2 items sit on an inactive
recording and are reported, not promoted.

How: `Working.review.promotion.promote_to_library` — hash, `dedupe.classify`, entry + member + revision 1 (machine,
with `detection_id`), one `audit_log` row (kind `library-promote`). No verdict and no annotation is written.
Exact or near duplicates of what the Library holds (including an earlier item of this same batch) are skipped.
Order: queue 25 then 28, detection id ascending, so a re-run is deterministic.

    "/c/ProgramData/anaconda3/python.exe" scripts/thesis/promote_blind_accepted.py           # dry run, writes nothing
    "/c/ProgramData/anaconda3/python.exe" scripts/thesis/promote_blind_accepted.py --apply   # backup, then promote

--apply first takes a backup through the bridge (POST http://127.0.0.1:8765/api/backups) and refuses to write if
that fails. Output: docs/thesis/data/library_events/promote_blind_accepted.json (counts, entry id range, audit ids).

Undo (each promotion):  Working.review.promotion.unpromote_to_library(conn, audit_id) for every audit id in the
output, or in SQL, for the recorded entry-id range [lo, hi] (all created by this run, source_kind 'review-accepted'):
    DELETE FROM motif_member_revision WHERE member_id IN (SELECT id FROM motif_member WHERE entry_id BETWEEN lo AND hi);
    DELETE FROM motif_member WHERE entry_id BETWEEN lo AND hi;
    DELETE FROM motif_entry WHERE id BETWEEN lo AND hi AND source_kind = 'review-accepted';
(delete any grouping that assigns those members first, e.g. g-11).
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sqlite3
import sys
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from Working.database.queries import is_surrogate_run  # noqa: E402
from Working.library import dedupe  # noqa: E402
from Working.library.identity import hash_span  # noqa: E402
from Working.review import promotion  # noqa: E402

DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite")
OUT = os.path.join(ROOT, "docs", "thesis", "data", "library_events", "promote_blind_accepted.json")
BRIDGE = "http://127.0.0.1:8765"
QUEUES = (25, 28)
ACCEPT = ("interesting", "seed")
NEVER = {"M4_aug_concat_fs1.mat": "held-out recording", "L_R_Aug_26_PD_raw.mat": "excluded (humidity PID artefact)"}
ACTOR = "thesis script (promote_blind_accepted.py)"


def accepted(conn):
    """[(queue, detection_id, verdict, recording_id, source_file, active)] — newest own look per detection."""
    out = []
    for qid in QUEUES:
        f = json.loads(conn.execute("SELECT filters_json FROM review_queues WHERE id = ?", (qid,)).fetchone()[0])
        ids = sorted({int(x) for x in f["detection_ids"]})
        for k in range(0, len(ids), 500):
            chunk = ids[k:k + 500]
            ph = ",".join("?" * len(chunk))
            for r in conn.execute(
                    f"""SELECT d.id det, rec.id rid, rec.source_file file, rec.active active,
                               (SELECT a.verdict FROM adjudications a WHERE a.detection_id = d.id
                                  AND a.carried_from IS NULL ORDER BY a.id DESC LIMIT 1) v
                          FROM detections d JOIN runs r ON r.id = d.run_id JOIN recordings rec ON rec.id = r.recording_id
                         WHERE d.id IN ({ph}) ORDER BY d.id""", chunk):
                if r["v"] in ACCEPT:
                    out.append((qid, r["det"], r["v"], r["rid"], r["file"], int(r["active"] or 0)))
    return out


def eligible(file, active):
    if file in NEVER:
        return NEVER[file]
    if not active:
        return "inactive recording"
    return None


def dry_run(conn, rows):
    """Classify every eligible item against the Library as it stands plus the items before it in this batch."""
    batch = collections.defaultdict(list)   # (rec, ch) -> spans accepted so far in this dry run
    hashes = set()
    res = []
    for qid, det, v, rid, file, active in rows:
        why = eligible(file, active)
        if why:
            res.append((qid, det, file, "refused", why))
            continue
        d = conn.execute("SELECT d.start_idx s, d.end_idx e, d.run_id, rec.channel ch FROM detections d "
                         "JOIN runs r ON r.id = d.run_id JOIN recordings rec ON rec.id = r.recording_id "
                         "WHERE d.id = ?", (det,)).fetchone()
        if is_surrogate_run(conn, d["run_id"]):
            res.append((qid, det, file, "refused", "surrogate run"))
            continue
        digest = hash_span(conn, rid, d["ch"], d["s"], d["e"])
        c = dedupe.classify(conn, content_hash=digest, recording_id=rid, channel=d["ch"], start_idx=d["s"],
                            end_idx=d["e"])
        span = (rid, d["ch"], d["s"], d["e"])
        if c["verdict"] != dedupe.NEW:
            res.append((qid, det, file, "skipped", c["verdict"] + " (Library)"))
        elif digest in hashes:
            res.append((qid, det, file, "skipped", "exact (batch)"))
        elif any(dedupe.is_near_duplicate(span, o) for o in batch[(rid, d["ch"])]):
            res.append((qid, det, file, "skipped", "near (batch)"))
        else:
            res.append((qid, det, file, "promoted", "new"))
            batch[(rid, d["ch"])].append(span)
            hashes.add(digest)
    return res


def apply(conn, rows):
    res, audits, entries = [], [], []
    for qid, det, v, rid, file, active in rows:
        why = eligible(file, active)
        if why:
            res.append((qid, det, file, "refused", why))
            continue
        try:
            out = promotion.promote_to_library(conn, det, actor=ACTOR, note=f"blind queue {qid}, own verdict {v}",
                                               source_store=f"review_queue:{qid}")
        except ValueError as exc:
            res.append((qid, det, file, "refused", str(exc)[:120]))
            continue
        if out["status"] == "promoted":
            res.append((qid, det, file, "promoted", "new"))
            audits.append(out["audit_id"])
            entries.append(out["entry_id"])
        else:
            res.append((qid, det, file, "skipped", f"{out['dedupe']} (entry {out['entry_id']})"))
    return res, audits, entries


def tally(res):
    t = collections.defaultdict(collections.Counter)
    for qid, det, file, status, why in res:
        t[f"q{qid} · {file}"][status] += 1
        t[f"q{qid} · {file}"][f"{status}: {why.split(' (entry')[0]}"] += 1
    return {k: dict(v) for k, v in sorted(t.items())}


def bridge_backup():
    req = urllib.request.Request(BRIDGE + "/api/backups", data=b"{}", method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.loads(r.read().decode("utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--db", default=DB)
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if not args.apply:
        conn = sqlite3.connect("file:" + args.db.replace("\\", "/") + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            rows = accepted(conn)
            res = dry_run(conn, rows)
        finally:
            conn.close()
        report = {"mode": "dry run", "accepted_own_looks": len(rows),
                  "totals": dict(collections.Counter(r[3] for r in res)), "per_recording": tally(res)}
        print(json.dumps(report, indent=1))
        return 0

    backup = bridge_backup()
    if not backup or not os.path.isfile(str(backup.get("path") or "")):
        raise SystemExit(f"bridge backup did not report a file: {backup!r}; nothing written")
    print("backup", backup.get("path"))
    conn = sqlite3.connect(args.db, timeout=120)
    conn.row_factory = sqlite3.Row
    try:
        rows = accepted(conn)
        res, audits, entries = apply(conn, rows)
    finally:
        conn.close()
    report = {"mode": "apply", "backup": backup.get("path"), "accepted_own_looks": len(rows),
              "totals": dict(collections.Counter(r[3] for r in res)), "per_recording": tally(res),
              "entry_id_range": [min(entries), max(entries)] if entries else None,
              "audit_log_ids": audits, "entry_ids": entries,
              "items": [{"queue": q, "detection_id": d, "recording": f, "status": s, "why": w} for q, d, f, s, w in res],
              "undo": "promotion.unpromote_to_library(conn, audit_id) for each of audit_log_ids (newest first); "
                      "see this script's docstring for the SQL form"}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    print(json.dumps({k: report[k] for k in ("backup", "accepted_own_looks", "totals", "per_recording",
                                             "entry_id_range")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
