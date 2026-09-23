"""
fixup_d_backfill_features.py
=============================
Fill `motif_features` (fixup-d) for every Library entry whose snippet an event
store holds: Event shape's measures from the detector's own anchors, and the
detector's own numbers (`drop_depth_mv` first — the number Q-X2.5's floor
filter needs). Idempotent: an entry already measured is skipped.

Writes to the database named by --db. It REFUSES the real
`DATA/db/annotations.sqlite` unless --real is given: filling the real table is
the researcher's decision, not a side effect of running a script.

    python scripts/fixup_d_backfill_features.py --db webui/runtime/<stamp>/annotations.sqlite
    python scripts/fixup_d_backfill_features.py --real          # the real database, deliberately
"""

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from Working.database.schema import init_db  # noqa: E402
from Working.library.features import backfill_library  # noqa: E402

REAL = os.path.normcase(os.path.abspath(os.path.join(ROOT, "DATA", "db", "annotations.sqlite")))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", help="the sqlite file to fill")
    ap.add_argument("--real", action="store_true", help="fill the real DATA/db/annotations.sqlite")
    ap.add_argument("--remeasure", action="store_true", help="re-measure entries that already have features")
    a = ap.parse_args()
    db = REAL if a.real else a.db
    if not db:
        ap.error("name a database with --db, or pass --real for the real one")
    if os.path.normcase(os.path.abspath(db)) == REAL and not a.real:
        ap.error("that is the real database; pass --real to fill it deliberately")
    conn = init_db(db)
    try:
        report = backfill_library(conn, repo_root=ROOT, only_missing=not a.remeasure)
    finally:
        conn.close()
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
