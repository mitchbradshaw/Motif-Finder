"""
annotations.py
==============
The `annotations` table -> `sequences` (human) and single-event `motif_entry`
rows. `docs/LIBRARY_STORAGE.md` §5, the `annotations` row of the importer
table.

This importer reads a table the project already has rather than a file, and
almost all of its work is **refusal**. The live `annotations` table holds
11,269 rows, and 11,234 of them are not library content: they are the
10-minute triage grid a person swept once to sort windows for the CNN. Sweeping
them in would flood the Library with eleven thousand identically-shaped
windows and bury the 35 rows that are real.

The rule that separates them, verified against the live table:

    SEQUENCE  <=>  source != 'imported_10min' AND relation_kind IS NOT 'type_specimen'

giving **31 sequences**, **4 single events** (the `type_specimen` children) and
**11,234 grid rows that are not imported at all**.

**Why the `source` test and not a length test.** Every grid row is exactly 600
samples at `scale_viewed = '10min'`, so "600 samples long" separates them today
— and would silently start importing the grid the day someone sweeps at a
different window size, which is a thing a researcher does on a Tuesday.
`source` records where the row came from, which is the thing actually being
tested; the length is a consequence of one sweep's settings.

**Why the grid does not encode sequences.** The obvious worry is that a run of
adjacent interesting windows *is* a sequence someone marked window by window.
The scout's contiguity test over the real table found the longest such run is
three, and three adjacent 10-minute windows is a half-hour of interest, not a
composition. The grid is a sort, not a transcript.

The two things this importer writes:

* a **sequence** per qualifying row — `origin = 'human'`, `source_kind =
  'annotation'`, `annotation_id` set, `needs_extraction = 1`, and `n_events`
  parsed from the note **only where the note states a count**. The events are
  not invented; `needs_extraction` is what says so, and
  `sequences_needing_extraction` is what hands them to Review's "extract
  events" queue (Prompt 05);
* a **single event** per `type_specimen` row — a `motif_entry` at `scale =
  'event'` with a real content hash taken from the span's own samples, its
  member, and revision 1 with `origin = 'human'`. The annotation's own tags
  come with it (`element`, `structure`, `provenance`) and its `element` names
  the entry: these four are the only *named* morphologies in the library —
  sharkfin, crestedwave, furrycaterpillar, halfdome — and an entry that
  arrived untagged was invisible to every tag filter and to a tag-basis
  grouping, which is the one thing a named specimen is for.

Every revision written here carries an `annotation_id` and never a
`detection_id`: detections are machine-only and annotations are human-only
(CLAUDE.md rule 5), and a type specimen is a person pointing at a waveform.

Nothing here imports a UI library (CLAUDE.md rule 1).
"""

import re

from Working.config import HELD_OUT_RECORDING_FILE
from Working.database import queries as q
from Working.database import runs as R
from Working.database import vocabulary as V
from Working.database.schema import ENTRY_SCALE_EVENT
from Working.library import dedupe, identity
from Working.library.importers.catalogue import ImportReport, sequence_key_for_span
from Working.library.revisions import add_revision

#: `annotations.source` for the 10-minute triage grid. The one value that
#: disqualifies a row from being library content.
GRID_SOURCE = q.SOURCE_IMPORTED_10MIN

#: `annotations.relation_kind` for a child row a person drew inside a
#: catalogued span to say "this, exactly, is the shape".
TYPE_SPECIMEN = "type_specimen"

#: The three answers `classify_annotation` gives.
GRID = "grid"
SEQUENCE = "sequence"
SINGLE_EVENT = "single_event"

# Patterns that state a count, each anchored to something being counted. The
# anchor is the whole point: the same notes carry `"20 - 70 mV"` and
# `"10 min/cycle at start"`, and a bare `\d+` turns a voltage range into an
# event count. Ordered longest-context first so `"sequence of 100"` is read as
# a count of the thing rather than as the number 100 next to a word.
_COUNT_PATTERNS = (
    re.compile(r"\bsequence\s+of\s+(\d+)\b", re.I),
    re.compile(r"\b(\d+)\s*x\s+\w", re.I),
    re.compile(r"\b(\d+)\s+cycles?\b", re.I),
    re.compile(r"\b(\d+)\s+spikes?\b", re.I),
    re.compile(r"\b(\d+)\s+events?\b", re.I),
)


def parse_event_count(note):
    """How many events a free-text note *states*, or None.

    Conservative on purpose. A count is only read where the number sits
    directly against something countable — `"16 cycles"`, `"4x sharkfin
    sequence"`, `"Regular sequence of 100 furrycaterpillars"`, `"60 spikes"` —
    and every other number in these notes (`"20 - 70 mV"`, `"10 min/cycle at
    start"`) is left alone.

    A note whose patterns disagree (`"16 cycles; 4x sharkfin sequence"`) yields
    None rather than a winner. Two counts in one sentence means the sentence is
    describing something this parser does not understand, and `n_events` is
    stored as *the source's claim* — a claim assembled by a regex picking a
    favourite would be this importer's claim wearing the source's name.
    """
    if not note:
        return None
    found = set()
    for pattern in _COUNT_PATTERNS:
        for match in pattern.finditer(str(note)):
            found.add(int(match.group(1)))
    if len(found) != 1:
        return None
    value = found.pop()
    return value if value > 0 else None


def classify_annotation(row):
    """Which of the three things an `annotations` row is: `GRID`, `SEQUENCE`
    or `SINGLE_EVENT`.

    `row` is a `sqlite3.Row` or any mapping carrying `source` and
    `relation_kind`. The order matters: a grid row is a grid row whatever else
    it carries, because the sweep is the provenance and nothing inside it was
    drawn by hand.
    """
    if _get(row, "source") == GRID_SOURCE:
        return GRID
    if _get(row, "relation_kind") == TYPE_SPECIMEN:
        return SINGLE_EVENT
    return SEQUENCE


def _get(row, key):
    """One field of a `sqlite3.Row` or a dict, without caring which it is."""
    try:
        return row[key]
    except (KeyError, IndexError):
        return None


def import_annotations(conn, *, dry_run=False, progress=None):
    """Import the human half of `annotations` into the Library.

    Applies the sequence rule above to every live (not soft-deleted)
    annotation: grid rows are counted and skipped, `type_specimen` rows become
    single events, and everything else becomes a human sequence that still
    `needs_extraction`.

    Idempotent. A sequence is keyed by `sequence_key_for_span` under
    `UNIQUE (sequence_key, origin)`, and a single event by its span's content
    hash resolving onto the entry that already holds it (§2.1, "same hash, the
    same `motif_entry`, never a second one"), so a second run reports
    `already_imported` and writes nothing.

    A row whose samples cannot be read — an unregistered channel, a `.npy` that
    is not on this clone — is reported as a skip with the reason, not raised:
    one missing channel file must not stop the other thirty rows importing.

    `dry_run=True` counts what a real run would write and writes nothing.
    `progress(done, total, what)` is called once per row.

    Returns an `ImportReport` whose counts are `sequences`, `events`,
    `grid_skipped`, `already_imported` and `n_events_parsed`.
    """
    report = ImportReport("annotations", dry_run=dry_run)
    for key in ("sequences", "events", "grid_skipped", "already_imported",
                "n_events_parsed", "skipped"):
        report.counts.setdefault(key, 0)

    rows = conn.execute(
        "SELECT * FROM annotations WHERE deleted_at IS NULL ORDER BY id"
    ).fetchall()
    total = len(rows)

    for i, row in enumerate(rows, start=1):
        ref = "annotation {}".format(row["id"])
        kind = classify_annotation(row)
        if kind == GRID:
            report.count("grid_skipped")
        else:
            recording = q.get_recording_by_id(conn, row["recording_id"])
            if recording is None:
                report.skip(ref, "recording {} is not registered".format(
                    row["recording_id"]))
            elif _is_held_out(recording):
                report.skip(ref, "{} is held out for evaluation and is refused "
                                 "on every route".format(HELD_OUT_RECORDING_FILE))
            elif kind == SEQUENCE:
                _import_sequence(conn, row, recording, report, dry_run)
            else:
                _import_single_event(conn, row, recording, report, dry_run)
        if progress is not None:
            progress(i, total, ref)

    if not dry_run:
        conn.commit()
    return report


def _is_held_out(recording):
    """Is this recording a channel of the held-out evaluation file?

    The lock keys on the source file, so every materialised channel of
    `M4_aug_concat_fs1.mat` is covered by the one config entry.
    """
    source_file = _get(recording, "source_file") or ""
    return str(source_file).endswith(HELD_OUT_RECORDING_FILE)


def _import_sequence(conn, row, recording, report, dry_run):
    """One `annotations` row -> one human sequence that still needs extraction.

    No `sequence_members` are written and `content_hash` stays NULL. A
    sequence's identity is its ordered composition, and this row's composition
    is not known — the note says *"16 cycles"*, not where the sixteen are.
    `needs_extraction = 1` is the honest record of exactly that (§4).
    """
    key = sequence_key_for_span(recording["id"], recording["channel"],
                                row["start_idx"])
    existing = conn.execute(
        "SELECT id FROM sequences WHERE sequence_key = ? AND origin = 'human'",
        (key,),
    ).fetchone()
    if existing is not None:
        report.count("already_imported")
        return

    n_events = row["event_count"]
    if n_events is None:
        n_events = parse_event_count(row["note"])
    if n_events is not None:
        report.count("n_events_parsed")
    report.count("sequences")
    if dry_run:
        return

    conn.execute(
        """INSERT INTO sequences
               (sequence_key, origin, recording_id, channel, start_idx,
                end_idx, n_events, needs_extraction, source_kind,
                source_store, source_ref, annotation_id, content_hash,
                created_at)
           VALUES (?, 'human', ?, ?, ?, ?, ?, 1, 'annotation', NULL, ?, ?,
                   NULL, datetime('now'))""",
        (key, recording["id"], recording["channel"], row["start_idx"],
         row["end_idx"], n_events, str(row["id"]), row["id"]),
    )


def _import_single_event(conn, row, recording, report, dry_run):
    """One `type_specimen` row -> one event-scale entry with a real hash.

    The hash is taken from the span's own samples via
    `Working.library.identity.hash_span`, not from its coordinates: a type
    specimen exists to *be* a shape, and an entry whose `content_hash` was
    derived from its row ids could never resolve onto the same shape found
    somewhere else, which is the whole point of the shape-first library (§2.1).

    `dedupe.find_duplicates` is asked first, so a specimen whose shape is
    already an entry becomes another member of it rather than a second entry.
    """
    try:
        span_hash = identity.hash_span(
            conn, recording["id"], recording["channel"],
            row["start_idx"], row["end_idx"])
    except ValueError as exc:
        report.skip("annotation {}".format(row["id"]), str(exc))
        return

    existing_member = conn.execute(
        """SELECT m.id FROM motif_member m
           JOIN motif_member_revision r ON r.member_id = m.id
           WHERE r.annotation_id = ? AND r.origin = 'human'""",
        (row["id"],),
    ).fetchone()
    if existing_member is not None:
        report.count("already_imported")
        return

    report.count("events")
    if dry_run:
        return

    entry_id = dedupe.find_duplicates(conn, span_hash)
    if entry_id is None:
        entry_id = R.insert_motif_entry(
            conn, recording["id"], row["start_idx"], row["end_idx"],
            notes=row["note"], commit=False)
        conn.execute(
            """UPDATE motif_entry
                  SET content_hash = ?, channel = ?, fs = ?, scale = ?,
                      source_kind = 'annotation', source_ref = ?
                WHERE id = ?""",
            (span_hash, recording["channel"], recording["fs"],
             ENTRY_SCALE_EVENT, str(row["id"]), entry_id),
        )

    _carry_over_tags(conn, entry_id, row)

    member_id = R.get_or_create_motif_member(
        conn, entry_id, recording["id"], row["start_idx"], row["end_idx"],
        commit=False)
    conn.execute(
        "UPDATE motif_member SET content_hash = ?, channel = ? WHERE id = ?",
        (span_hash, recording["channel"], member_id),
    )
    add_revision(conn, member_id, origin="human", annotation_id=row["id"],
                 start_idx=row["start_idx"], end_idx=row["end_idx"],
                 content_hash=span_hash, commit=False)


def _carry_over_tags(conn, entry_id, row):
    """The annotation's tags and its name, onto the entry it produced.

    A type specimen is a person pointing at a waveform and saying what it is:
    `element = sharkfin`, `structure = type_specimen`, `provenance =
    excel_catalog`. Those three are the whole of what makes the four named
    morphologies findable — an entry without them is invisible to every tag
    filter and to a tag-basis grouping (§3.4), which is the one thing a named
    specimen exists for.

    Tags are added, never replaced: two people naming one shape differently is
    a finding the library keeps (§3.4), exactly as the event-store importer
    keeps `trough` and `Stegasauras` on one entry. `label` is set only when the
    entry has none, so a second specimen adds a name without renaming the
    shape. Every term is already in `tag_vocabulary` — it came off an
    `annotation_tags` row — so nothing is created here.
    """
    tags = V.get_annotation_tags(conn, row["id"])
    for category in sorted(tags):
        for value in sorted(tags[category]):
            V.add_motif_entry_tag(conn, entry_id, category, value, commit=False)

    label = None
    for value in sorted(tags.get("element", [])):
        label = value
        break
    if label is None:
        label = _get(row, "tag")
    if label:
        conn.execute(
            """UPDATE motif_entry SET label = ?
                WHERE id = ? AND (label IS NULL OR label = '')""",
            (str(label), entry_id),
        )


def sequences_needing_extraction(conn, *, origin=None):
    """The "extract events" queue: sequences whose singular events are not
    resolved yet.

    This is what Review reads (Prompt 05). A row here is a claim someone made
    — *"60 spikes, 7 mV, 10 min/cycle at start"* — with no `sequence_members`
    behind it, waiting for a person to mark where the events actually are.
    Once they do, the extraction writes the members and clears the flag.

    `origin` narrows to `'human'` or `'machine'`; the default returns both,
    because a detector's sequence can need extraction too.
    """
    sql = "SELECT * FROM sequences WHERE needs_extraction = 1"
    params = []
    if origin is not None:
        sql += " AND origin = ?"
        params.append(origin)
    sql += " ORDER BY recording_id, start_idx, id"
    return conn.execute(sql, params).fetchall()
