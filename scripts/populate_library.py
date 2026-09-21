"""
populate_library.py
===================
Fill the motif library from the extracted-event stores, the catalogue and the
annotations already in the database, then compute and save the default
grouping. Stage-3 Prompt 03; the standard it implements is
`docs/LIBRARY_STORAGE.md`.

This is dev tooling. Nothing in `Working/`, `Adapters/` or `webui/` imports it.
It exists so that "how this machine's library was populated" is a file someone
can read and re-run, rather than a command that happened once in a terminal.

What it imports, and what it deliberately does not
--------------------------------------------------
`DATA/library_seed/drop_motifs5/motifs`   410 events, tracked, not regenerable
`Plots/drop_motifs10/motifs`              3,511 events, with species/corpus
`Plots/drop_motifs11/sequences.csv`       118 sequences, keyed to drop_motifs10
`DATA/catalogue/signal_catalog.xlsx`      37 catalogued spans
the `annotations` table                   human sequences and type specimens

**`Plots/drop_motifs12a` is not imported.** Both its stores are marked
`partial` — region A of the Lion's mane recording was never detected — 844 of
its 1,077 rows carry `recording_id = -1`, and its two floor policies
(`derived_3x_amplitude_MAD` and `global_0.1mV`) are two views of one detection
that collide on `motif_entry`'s `UNIQUE (recording_id, start_idx, end_idx)`.
Importing it would ship a knowingly incomplete species and create two entries
for one event. `--include-12a` runs it anyway, for whoever wants to look.

**The `reishi_1hz` control corpus is excluded** from drop_motifs10 by default.
It is the same organism as `reishi_10hz` recorded at a second rate, sharing
`(catalogue_id, channel)` with it, so it double-counts: the sequence-recovery
rule reproduces 118 of 118 sequences with it excluded and 52 of 118 with it in.

Safety
------
Refuses to run unless a backup of the database exists that is newer than the
database itself, because the import writes several thousand rows into the one
file that cannot be regenerated. `--dry-run` reports what every importer would
do and writes nothing.

Usage
-----
    python scripts/populate_library.py --dry-run
    python scripts/populate_library.py
"""

import argparse
import glob
import os
import shutil
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Working.database.schema import DB_PATH, init_db          # noqa: E402
from Working.library.grouping import engine as grouping_engine  # noqa: E402
from Working.library.importers.annotations import import_annotations  # noqa: E402
from Working.library.importers.catalogue import import_catalogue      # noqa: E402
from Working.library.importers.event_store import import_event_store  # noqa: E402
from Working.library.importers.sequences import import_sequences_csv  # noqa: E402

BACKUP_DIR = os.path.join("DATA", "db", "backups")

#: Where to cut the Ward tree for the single-motif grouping.
#:
#: **Measured, not inherited.** The frontend fixture carried 0.42, and on the
#: real 3,603-entry catalogue that cut omits 29% of it — every one of them for
#: `group_too_small`, i.e. split into families below the ten-member floor.
#: Sweeping the cut over this catalogue:
#:
#:     cut   families  assigned  omitted
#:     0.30  116       1,660     54%
#:     0.42  151       2,545     29%     <- the fixture's number
#:     0.60  149       3,239     10%     <- this default
#:     0.80  115       3,480      3%
#:     1.00   92       3,570      1%
#:
#: The family count is flat across 0.42 -> 0.60 (151 against 149) while the
#: omitted fraction falls by two thirds. The extra omission at 0.42 therefore
#: buys no additional structure: it is the same families with a quarter of the
#: catalogue shaken out below the floor. 0.60 is the honest default for THIS
#: catalogue, and is a starting point for the grouping editor, not a constant of
#: nature — re-measure it when the catalogue changes.
DEFAULT_CUT = 0.60

#: Sequences are few (118 with resolved events) and a sequence family of two is
#: a real finding rather than noise, so the floor is 2 rather than 10.
DEFAULT_SEQUENCE_CUT = 0.60

EVENT_STORES = [
    "DATA/library_seed/drop_motifs5/motifs",
    "Plots/drop_motifs10/motifs",
]
STORE_12A = "Plots/drop_motifs12a/motifs_PARTIAL"
SEQUENCES_CSV = "Plots/drop_motifs11/sequences.csv"
SEQUENCES_STORE = "Plots/drop_motifs10/motifs"
CATALOGUE = "DATA/catalogue/signal_catalog.xlsx"


def _newest_backup():
    paths = glob.glob(os.path.join(BACKUP_DIR, "*.sqlite"))
    return max(paths, key=os.path.getmtime) if paths else None


def _require_backup(db_path, make_one):
    """A backup newer than the database, or refuse to run.

    The import writes thousands of rows into `DATA/db/annotations.sqlite`,
    which holds 11,269 human annotations that took a person weeks and cannot be
    regenerated. On 2026-09-21 a `git worktree remove` emptied `DATA/db`
    entirely and the file was only recovered because a sandbox copy happened to
    exist. That is the reason this check is a refusal and not a warning.
    """
    newest = _newest_backup()
    fresh = newest is not None and os.path.getmtime(newest) >= os.path.getmtime(db_path)
    if fresh:
        print("backup: {} ({:.1f} MB)".format(newest, os.path.getsize(newest) / 1e6))
        return newest
    if not make_one:
        raise SystemExit(
            "refusing to run: no backup in {} is newer than {}.\n"
            "Make one first, or pass --backup to have this script do it."
            .format(BACKUP_DIR, db_path))
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(BACKUP_DIR, "{}-pre-library.sqlite".format(stamp))
    shutil.copy2(db_path, dest)
    with sqlite3.connect("file:{}?mode=ro".format(dest), uri=True) as check:
        ok = check.execute("PRAGMA integrity_check").fetchone()[0]
    if ok != "ok":
        raise SystemExit("the backup just written fails integrity_check: {}".format(ok))
    print("backup: {} (written now, integrity ok)".format(dest))
    return dest


def _counts(conn):
    tables = ("motif_entry", "motif_member", "motif_member_revision",
              "motif_entry_tags", "sequences", "sequence_members",
              "groupings", "grouping_assignments", "annotations")
    out = {}
    for t in tables:
        try:
            out[t] = conn.execute('SELECT COUNT(*) FROM "{}"'.format(t)).fetchone()[0]
        except sqlite3.OperationalError:
            out[t] = None
    return out


def _report_line(name, report, elapsed):
    counts = getattr(report, "counts", None) or dict(getattr(report, "outcomes", {}) or {})
    skipped = dict(getattr(report, "skipped", {}) or {})
    flags = len(getattr(report, "flags", []) or [])
    bits = ["{:.1f}s".format(elapsed)]
    if counts:
        bits.append(" ".join("{}={}".format(k, v) for k, v in counts.items() if v))
    if skipped:
        bits.append("skipped(" + " ".join("{}={}".format(k, v) for k, v in skipped.items()) + ")")
    if flags:
        bits.append("flagged={}".format(flags))
    print("  {:<34} {}".format(name, "  ".join(bits)))
    for warning in (getattr(report, "warnings", []) or [])[:3]:
        print("      warn: {}".format(str(warning)[:150]))
    skips = getattr(report, "skips", []) or []
    for skip in skips[:6]:
        print("      skip: {}".format(str(skip)[:150]))


def _load_single_motifs(conn):
    """Every event-scale entry, with the waveform its grouping needs.

    The engine takes plain dicts and never touches a database — that is what
    lets it be tested without one — so loading is the caller's job. The
    waveform is read from the recording's channel `.npy` at the entry's
    absolute indices (CLAUDE.md rule 4: the array is on disk, the row holds
    the reference), which is also why an entry whose channel file is missing is
    dropped here with a count rather than failing the whole grouping.
    """
    import numpy as np

    rows = conn.execute(
        """SELECT e.id, e.recording_id, e.start_idx, e.end_idx, e.content_hash,
                  r.npy_path
             FROM motif_entry e
             JOIN recordings r ON r.id = e.recording_id
            WHERE e.scale IS NULL OR e.scale = 'event'
            ORDER BY e.id"""
    ).fetchall()

    items, unreadable = [], 0
    cache = {}
    for row in rows:
        path = row["npy_path"]
        if not path or not os.path.exists(path):
            unreadable += 1
            continue
        try:
            array = cache.get(path)
            if array is None:
                array = cache[path] = np.load(path, mmap_mode="r")
            values = np.asarray(array[row["start_idx"]:row["end_idx"]], dtype=float)
            if values.size == 0:
                unreadable += 1
                continue
        except Exception:
            unreadable += 1
            continue
        items.append({
            "member_ref": row["id"],
            "content_hash": row["content_hash"],
            "recording_id": row["recording_id"],
            "values": values,
        })
    return items, unreadable


def _load_sequences(conn):
    """Every sequence with resolved member events, as a gap profile.

    A sequence's identity is its ordered composition and its gaps, not one
    waveform (LIBRARY_STORAGE.md 4), so `sequence-similarity` clusters the gap
    profile and the engine refuses to invent one. A sequence still awaiting
    extraction has no members and therefore no profile: it is left out of the
    grouping rather than given a fabricated one, which is exactly what
    `needs_extraction` records.
    """
    rows = conn.execute(
        """SELECT s.id, s.content_hash, s.recording_id, s.needs_extraction,
                  m.position, m.gap_before
             FROM sequences s
             JOIN sequence_members m ON m.sequence_id = s.id
            WHERE s.needs_extraction = 0
            ORDER BY s.id, m.position"""
    ).fetchall()

    gaps, meta = {}, {}
    for row in rows:
        gaps.setdefault(row["id"], []).append(float(row["gap_before"] or 0.0))
        meta[row["id"]] = (row["content_hash"], row["recording_id"])
    return [{"member_ref": sid,
             "content_hash": meta[sid][0],
             "recording_id": meta[sid][1],
             "sequence_id": sid,
             "gap_profile": profile}
            for sid, profile in gaps.items() if len(profile) >= 2]


def _run_and_save_grouping(conn, items, *, name, unit, basis, params):
    """Compute one grouping and save it.

    Saved as a `groupings` row plus one `grouping_assignments` row per member,
    including the omitted ones with their reason — spec 8.2 is explicit that
    what does not fit is flagged and never deleted.
    """
    if not items:
        return "{}: nothing to group".format(name)

    result = grouping_engine.run_grouping(
        items, unit=unit, basis=basis, method="ward", params=params)

    import json
    gid = conn.execute(
        """INSERT INTO groupings
               (name, unit, basis, method, params_json, cut, filters_json,
                n_families, n_assigned, n_omitted, recipe_hash, created_at, actor)
           VALUES (?, ?, ?, 'ward', ?, ?, NULL,
                   ?, ?, ?, ?, datetime('now'), 'this installation')""",
        (name, unit, basis, json.dumps(params, sort_keys=True), params.get("cut"),
         result.n_families, result.n_assigned, result.n_omitted,
         result.recipe_hash),
    ).lastrowid

    conn.executemany(
        """INSERT INTO grouping_assignments
               (grouping_id, unit, member_ref, content_hash, family_id,
                family_label, distance, is_medoid, omit_reason)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [(gid, unit, a.ref, a.content_hash, a.family_id, a.family_label,
          a.distance, 1 if a.is_medoid else 0, a.omit_reason)
         for a in result.assignments],
    )
    return ("g-{:02d} {:<18} {} families, {} assigned, {} omitted ({}), from {}"
            .format(gid, name, result.n_families, result.n_assigned,
                    result.n_omitted, result.omitted_by_reason or "none", len(items)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[3])
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what each importer would do; write nothing")
    ap.add_argument("--backup", action="store_true",
                    help="write a backup first instead of refusing when none is fresh")
    ap.add_argument("--include-12a", action="store_true",
                    help="also import Plots/drop_motifs12a (partial; see the module docstring)")
    ap.add_argument("--no-grouping", action="store_true",
                    help="import only; do not compute and save the default grouping")
    args = ap.parse_args(argv)

    if not os.path.exists(args.db):
        raise SystemExit("no database at {}".format(args.db))
    if not args.dry_run:
        _require_backup(args.db, make_one=args.backup)

    init_db(args.db)
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    # A dry run of several stores in one invocation over-reports `created`.
    # Each importer resolves duplicates against the database plus what it has
    # itself decided, and a dry run writes nothing — so the second store cannot
    # see the first store's would-be entries and counts its duplicates of them
    # as new. Measured here: the two stores dry-run as 410 + 3,255 where a real
    # run writes 410 + 3,189, the 66 difference being 61 exact duplicates of
    # seed events and 5 span conflicts. The Import page is unaffected: it dry-
    # runs ONE bundle against the real database state, which is exact.

    before = _counts(conn)
    print("\nbefore: " + "  ".join("{}={}".format(k, v) for k, v in before.items()))
    print("\nimporting{}:".format(" (dry run)" if args.dry_run else ""))

    stores = list(EVENT_STORES) + ([STORE_12A] if args.include_12a else [])
    for store in stores:
        if not os.path.isdir(store):
            print("  {:<34} absent on this machine, skipped".format(store))
            continue
        t0 = time.time()
        report = import_event_store(conn, store, dry_run=args.dry_run)
        _report_line(store, report, time.time() - t0)

    if os.path.exists(SEQUENCES_CSV):
        t0 = time.time()
        report = import_sequences_csv(
            conn, SEQUENCES_CSV,
            event_store_path=SEQUENCES_STORE if os.path.isdir(SEQUENCES_STORE) else None,
            dry_run=args.dry_run)
        _report_line(SEQUENCES_CSV, report, time.time() - t0)
    else:
        print("  {:<34} absent on this machine, skipped".format(SEQUENCES_CSV))

    if os.path.exists(CATALOGUE):
        t0 = time.time()
        report = import_catalogue(conn, CATALOGUE, dry_run=args.dry_run)
        _report_line(CATALOGUE, report, time.time() - t0)

    t0 = time.time()
    report = import_annotations(conn, dry_run=args.dry_run)
    _report_line("the annotations table", report, time.time() - t0)

    if not args.dry_run:
        conn.commit()

    if not args.no_grouping and not args.dry_run:
        print("\ngroupings (Ward, per PRD Part 2's default):")
        motifs, unreadable = _load_single_motifs(conn)
        if unreadable:
            print("  {} entries have no readable channel array and cannot be grouped"
                  .format(unreadable))
        t0 = time.time()
        print("  " + _run_and_save_grouping(
            conn, motifs, name="shape families", unit="single_motifs",
            basis="shape-distance",
            params={"cut": DEFAULT_CUT, "min_group": 10, "omit_d": 0.50}))
        sequences = _load_sequences(conn)
        print("  " + _run_and_save_grouping(
            conn, sequences, name="sequence families", unit="sequences",
            basis="sequence-similarity",
            params={"cut": DEFAULT_SEQUENCE_CUT, "min_group": 2, "omit_d": 0.50}))
        conn.commit()
        print("  ({:.1f}s)".format(time.time() - t0))

    after = _counts(conn)
    print("\nafter:  " + "  ".join("{}={}".format(k, v) for k, v in after.items()))
    print("\ndelta:  " + "  ".join(
        "{}+{}".format(k, (after[k] or 0) - (before[k] or 0))
        for k in after if (after[k] or 0) != (before[k] or 0)) or "\ndelta:  nothing changed")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
