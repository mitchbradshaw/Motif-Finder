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

A DRY RUN by default: it opens the database READ-ONLY, runs no migration,
prints every catalogue-span seed run and what it would do, and writes nothing.
`--apply` opens it through `init_db` (the application path) and writes; the
migrations' log lines are counted and summed up in one line rather than printed
over the report.

The REAL database is the main checkout's `DATA/db/annotations.sqlite` (found
through `git rev-parse --git-common-dir`, so a worktree's copy of this script
protects it too; the script's own checkout when git is not there to ask). It is
written only with `--real`, and `--real` takes no `--db`: a `--db` that names the
real file by any other name — another case, the other slash, a `..`, the Win32
long-path prefix, a junction, a hard link — is refused, because the paths are
compared as files, not as strings.

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
import logging
import os
import pathlib
import sqlite3
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from Working.database.schema import init_db  # noqa: E402
from Working.discovery.seed_entry_backfill import backfill  # noqa: E402

#: the Win32 long-path prefix (two backslashes, "?", one backslash), which names the same file
LONG_PREFIX = chr(92) * 2 + "?" + chr(92)


def main_checkout(root=ROOT):
    """The main checkout this script belongs to. A worktree's own tree is not where the real database lives:
    `git rev-parse --git-common-dir` names the shared `.git`, whose parent is the main checkout. The script's own
    checkout when git cannot be asked."""
    try:
        out = subprocess.run(["git", "-C", root, "rev-parse", "--git-common-dir"], capture_output=True, text=True,
                             timeout=30)
        common = out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        common = ""
    if common:
        common = os.path.normpath(common if os.path.isabs(common) else os.path.join(root, common))
        if os.path.basename(common).lower() == ".git":
            return os.path.dirname(common)
    return root


REAL_DB = os.path.join(main_checkout(), "DATA", "db", "annotations.sqlite")


def _canonical(path):
    """A path as one spelling: absolute, links and junctions resolved, the long-path prefix dropped, case folded."""
    p = os.path.realpath(os.path.abspath(path))
    if p.startswith(LONG_PREFIX):
        p = p[len(LONG_PREFIX):]
    return os.path.normcase(os.path.normpath(p))


def is_the_real_database(path, real=REAL_DB):
    """True when `path` names the real database by any name. The spellings are compared once resolved; then the
    files themselves (`os.path.samefile`: the same file on disk, which also catches a hard link)."""
    if _canonical(path) == _canonical(real):
        return True
    try:
        return os.path.samefile(path, real)
    except OSError:
        # one of them does not exist, so they are not one file
        return False


def _read_only(path):
    """The database opened read-only, with no migration: a dry run writes nothing. (`init_db` runs every migration
    on the file it opens; on a snapshot of the real database that printed some 300 lines of a legacy-detections
    migration over the report.)"""
    return sqlite3.connect(pathlib.Path(os.path.abspath(path)).as_uri() + "?mode=ro", uri=True)


class _Held(logging.Handler):
    """Holds a migration's log records instead of printing them."""

    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)


def _open_for_apply(path):
    """`init_db` — the application path, every migration — with the schema module's log lines held back and counted,
    so the report is not buried under them. `init_db` itself is not touched."""
    log = logging.getLogger("Working.database.schema")
    held, propagate = _Held(), log.propagate
    log.addHandler(held)
    log.propagate = False
    try:
        conn = init_db(path)
    finally:
        log.removeHandler(held)
        log.propagate = propagate
    return conn, held.records


def _line(r):
    return (f"  run {r['id']:>4}  {r['runKey']:<28} {r['seedId']:<34} entry {str(r['before']):>6} -> "
            f"{str(r['entryId']):>6}  ({r['runIds']} runs)" + (f"  {r['reason']}" if r.get("reason") else "")
            + ("  [off its session: Discovery › History brings it back, with its Add N matches]" if r.get("removed")
               else ""))


def main(argv=None, real=None):
    """`real`: the real database's path (the main checkout's by default); a test hands in a stand-in."""
    real = real or REAL_DB
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", help="the sqlite file to backfill (never the real one: that is --real)")
    ap.add_argument("--real", action="store_true", help="the real database, deliberately (takes no --db)")
    ap.add_argument("--apply", action="store_true", help="write (without it: a read-only dry run that writes nothing)")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    a = ap.parse_args(argv)
    if a.db and a.real:
        ap.error("give --db or --real, not both: --real is the real database, --db any other file")
    db = real if a.real else a.db
    if not db:
        ap.error("name a database with --db, or pass --real for the real one")
    if not a.real and is_the_real_database(db, real):
        ap.error(f"{db} is the real database ({real}); pass --real, and no --db, to backfill it deliberately")
    if not os.path.isfile(db):
        ap.error(f"no database at {db}")
    held = []
    if a.apply:
        conn, held = _open_for_apply(db)
    else:
        conn = _read_only(db)
    try:
        report = backfill(conn, apply=a.apply)
    finally:
        conn.close()
    if a.json:
        print(json.dumps(dict(report, migrationMessagesHeld=len(held)), indent=1))
        return 0
    print(f"database {db}")
    print(f"{'APPLIED' if report['applied'] else 'DRY RUN - read-only, nothing written'} · rule: {report['rule']}")
    if held:
        print(f"init_db: {len(held)} migration message(s) held back, not printed (the first: "
              f"{held[0].getMessage()})")
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
