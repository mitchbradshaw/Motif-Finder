"""Queue every unanswered g-11 representative, using the existing family-review writer.

This is the thesis's deduplicated shape grouping, not inactive historical store
fragments or the accepted-only source inventory g-12. A positive answer lands
in library_review annotations, which accepted_catalogue.py already collects.
"""
from __future__ import annotations
import argparse
import collections
import csv
import datetime as dt
import json
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from Working.library.verdicts import member_verdicts
from Working.review import family_queue, queues
from Working.registration.settings import append_audit

FAMILY = "g-11 · unjudged shape candidates"


def candidates(c):
    mm = [dict(r) for r in c.execute("""SELECT m.id member_id,m.recording_id,m.start_idx,m.end_idx,
        ga.family_label,r.source_file,r.channel FROM grouping_assignments ga
        JOIN motif_member m ON m.id=ga.member_ref JOIN recordings r ON r.id=m.recording_id
        WHERE ga.grouping_id=11 ORDER BY m.id""")]
    resolved = member_verdicts(c, mm)
    own = family_queue.member_verdicts(c, [m["member_id"] for m in mm])
    return [m for m in mm if not resolved[m["member_id"]]["judged"] and m["member_id"] not in own]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", type=pathlib.Path, required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    db = args.project_root / "DATA/db/annotations.sqlite"
    out = args.project_root / "DATA/derived/library_unjudged_review"
    out.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(db.resolve().as_uri()+"?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    todo = candidates(c)
    c.close()
    report = {"mode": "preview", "grouping": 11, "candidate_members": len(todo),
              "by_recording": dict(collections.Counter(m["source_file"] for m in todo)),
              "unassigned_to_a_shape_family": sum(m["family_label"] is None for m in todo),
              "includes": "unanswered representatives, including omitted shapes, without inactive store fragments",
              "judgements_written": 0}
    if args.apply:
        backup = db.parent / "backups" / ("library_unjudged_"+dt.datetime.now().strftime("%Y%m%d_%H%M%S")+".sqlite")
        src, dst = sqlite3.connect(str(db), timeout=120), sqlite3.connect(str(backup))
        src.backup(dst)
        src.close()
        dst.close()
        c = sqlite3.connect(str(db), timeout=120)
        c.row_factory = sqlite3.Row
        try:
            todo = candidates(c)
            qid = family_queue.create_family_queue(c, family=FAMILY,
                    member_ids=[m["member_id"] for m in todo], grouping="g-11")
            c.execute("UPDATE review_queues SET name=?,note=? WHERE id=?",
                      ("Library · unjudged shape candidates (g-11)",
                       "All unanswered g-11 representatives, including omitted shapes; original family links saved in DATA/derived/library_unjudged_review/members.csv. Selected Library proposals, not a random blind cohort. Accepted labels enter the curated catalogue at refresh.", qid))
            append_audit(c, "library-unjudged-review-queue", f"queue {qid}: {len(todo)} unanswered g-11 proposals",
                         "Review", actor="researcher request, 2026-11-08",
                         route="scripts.thesis.review_unjudged_library",
                         detail={"queue_id": qid, "grouping_id": 11, "member_ids": [m["member_id"] for m in todo]}, commit=False)
            c.commit()
            report.update(mode="created", queue_id=qid, backup=str(backup),
                          candidate_members=len(todo), counts=queues.queue_counts(c, qid),
                          url=f"http://127.0.0.1:8765/#/review/queue/{qid}")
        finally:
            c.close()
    if todo:
        with (out / "members.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(todo[0]))
            w.writeheader()
            w.writerows(todo)
    (out / "queue.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
