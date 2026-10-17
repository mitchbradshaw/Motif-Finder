"""
backfill_seed_entry_ids.py
==========================
a2-p4 change 4.5: link the Discovery seed runs made from a catalogue span (the
Seed page's old "Family medoid" tab, seed ids `medoid:<recording>:<start>:<end>`)
to the Library entry at the same span, so Discovery › Runs › *Add N matches to
E-xxxx* can add their accepted matches to the Library. The rule and its
guarantees are `Working/discovery/seed_entry_backfill.py`'s: only
`params_json.entryId` changes, one audit row per run that changed something,
and a second run changes nothing.

A DRY RUN by default: it prints every catalogue-span seed run and what it would
do, and writes nothing. `--apply` writes. It REFUSES the real
`DATA/db/annotations.sqlite` unless `--real` is given: changing the real
database is the researcher's decision, not a side effect of running a script.

    python scripts/backfill_seed_entry_ids.py --db webui/runtime/<stamp>/annotations.sqlite          # dry run
    python scripts/backfill_seed_entry_ids.py --db webui/runtime/<stamp>/annotations.sqlite --apply  # a copy
    python scripts/backfill_seed_entry_ids.py --real                                                  # dry run, real
    python scripts/backfill_seed_entry_ids.py --real --apply                                          # the real one

Undo: the audit row (Settings › Audit, kind `library`) lists each run id with
its `before` (null) and `entryId`; setting `entryId` back to null in that run's
`params_json` is the whole undo.
"""

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from Working.database.schema import init_db  # noqa: E402
from Working.discovery.seed_entry_backfill import backfill  # noqa: E402

REAL = os.path.normcase(os.path.abspath(os.path.join(ROOT, "DATA", "db", "annotations.sqlite")))


def _line(r):
    return (f"  run {r['id']:>4}  {r['runKey']:<28} {r['seedId']:<34} entry {str(r['before']):>6} -> "
            f"{str(r['entryId']):>6}  ({r['runIds']} runs)" + (f"  {r['reason']}" if r.get("reason") else "")
            + ("  [off its session: Discovery › History brings it back, with its Add N matches]" if r.get("removed")
               else ""))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", help="the sqlite file to backfill")
    ap.add_argument("--real", action="store_true", help="the real DATA/db/annotations.sqlite, deliberately")
    ap.add_argument("--apply", action="store_true", help="write (without it: a dry run that writes nothing)")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    a = ap.parse_args(argv)
    db = REAL if a.real else a.db
    if not db:
        ap.error("name a database with --db, or pass --real for the real one")
    if os.path.normcase(os.path.abspath(db)) == REAL and not a.real:
        ap.error("that is the real database; pass --real to backfill it deliberately")
    if not os.path.isfile(db):
        ap.error(f"no database at {db}")
    conn = init_db(db)
    try:
        report = backfill(conn, apply=a.apply)
    finally:
        conn.close()
    if a.json:
        print(json.dumps(report, indent=1))
        return 0
    print(f"database {db}")
    print(f"{'APPLIED' if report['applied'] else 'DRY RUN - nothing written'} · rule: {report['rule']}")
    for name, title in (("linked", "linked" if report["applied"] else "would link"), ("already", "already linked"),
                        ("unmatched", "no Library entry at the seed's span (left as they are)"),
                        ("unreadable", "unreadable seed id (left as they are)")):
        print(f"{title}: {len(report[name])}")
        for r in report[name]:
            print(_line(r))
    if report["auditId"] is not None:
        print(f"audit_log row {report['auditId']} (kind library) records it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
