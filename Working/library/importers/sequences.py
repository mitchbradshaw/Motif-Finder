"""
sequences.py
============
`docs/LIBRARY_STORAGE.md` §4 and §5, row four: a detector's `sequences.csv`
(`Plots/drop_motifs11/sequences.csv`) becoming `sequences` rows with
`origin = 'machine'`, and — when its member events can be recovered —
`sequence_members` in time order with their gaps.

**A sequence is not a long motif.** Two sequences of the same six shapes with
different gaps are different sequences, and two sequences of different shapes
with the same gaps are also different. That is why the identity is
compositional, why it lives in `sequence_members`, and why these rows are not
`motif_entry` rows with a longer span.

`origin` picks the write door (§3.5)
------------------------------------
A sequence read out of a detector's CSV is a **machine** claim; a sequence read
out of `annotations` is a **person's**. Storing both in one table is only safe
because `origin` is on the row and never inferred: the core writes plain SQL
directly, the rule-5 door lives in the bridge, and either way `origin` is
written explicitly. Nothing in this module can produce a `human` row.

Recovering the member events
----------------------------
`sequences.csv` names only its two endpoints (`start_event_id`,
`end_event_id`) and a claimed count `n`. The rule that recovers everything in
between was verified against the real data by the scout and is implemented in
`resolve_sequence_events`:

    take the event store's rows, drop the control corpora, keep those with the
    sequence's own `catalogue_id` and `channel`, and select the ones whose
    `onset_idx / fs` falls in the INCLUSIVE range
    [`start_onset_s`, `end_onset_s`], ordered by onset.

With the 1 Hz control corpus excluded this reproduces the claimed `n` on
118/118 real sequences, exactly; with it included, on 52/118. That measurement
is the whole reason `exclude_corpora` is not optional decoration.

When it cannot be recovered
---------------------------
The sequence is still written, with `needs_extraction = 1` and **no members**.
This is the honest state (§4): the claim is recorded, the events are not
invented, and Review can offer the row as an "extract events" queue later. A
sequence whose members were guessed would be indistinguishable from one whose
members were measured, which is the failure this flag exists to prevent.

Nothing here imports a UI library (CLAUDE.md rule 1).
"""

import datetime

import numpy as np
import pandas as pd

from Working.library.identity import content_hash
from Working.library.importers.event_store import (
    DEFAULT_EXCLUDED_CORPORA,
    ImportReport,
    read_event_store,
    _repo_relative,
)

#: `sequences.source_kind` for every row this importer writes (§3.3).
SOURCE_KIND = "sequence_csv"

#: The only origin this module can write. Named rather than inlined so the one
#: place rule 5 could be broken here is greppable.
ORIGIN = "machine"

# The outcome vocabulary, one per CSV row.
RESOLVED = "resolved"
NEEDS_EXTRACTION = "needs_extraction"
ALREADY_PRESENT = "already_present"
SKIPPED = "skipped"


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def resolve_sequence_events(events, *, catalogue_id, channel,
                            start_onset_s, end_onset_s,
                            exclude_corpora=DEFAULT_EXCLUDED_CORPORA):
    """The member events of one sequence, in onset order — the verified rule.

    `events` is an event store's row list as
    `Working.Detection.drop_motifs.store.load_events` returns it.

    The range is **inclusive at both ends**, because the two endpoints named by
    the CSV are themselves members: an exclusive end would drop the last event
    of every sequence and quietly shorten all 118 of them by one.

    Public because Discovery reads sequence membership too, and a second copy
    of this rule elsewhere would be a second definition of what a sequence is.
    """
    excluded = {str(c).lower() for c in (exclude_corpora or ())}
    picked = []
    for event in events:
        if str(event.get("corpus") or "").lower() in excluded:
            continue
        if int(event["catalogue_id"]) != int(catalogue_id):
            continue
        if int(event["channel"]) != int(channel):
            continue
        fs = float(event.get("fs") or 0.0)
        if fs <= 0:
            continue
        onset_s = float(event["onset_idx"]) / fs
        if start_onset_s <= onset_s <= end_onset_s:
            picked.append(event)
    picked.sort(key=lambda e: int(e["onset_idx"]))
    return picked


def _gap_profile(members):
    """Seconds from each event's onset to the previous one's; None for the
    first.

    Onset to onset rather than end to start, because that is what the source's
    own `median_interval_s` measures — a gap defined against event ends would
    not be comparable to the number the detector reported alongside it.
    """
    gaps = [None]
    for previous, event in zip(members, members[1:]):
        fs = float(event.get("fs") or 0.0) or 1.0
        gaps.append((int(event["onset_idx"]) - int(previous["onset_idx"])) / fs)
    return gaps


def _sequence_hash(gaps):
    """`sequences.content_hash`: the shape of the gap profile (§3.3).

    The same hash the waveforms use, over the gap vector, so two sequences with
    the same rhythm at different speeds land together — the resample and
    z-normalise inside `content_hash` make the profile scale-free, which is the
    same choice §2.3 makes about sampling rate for a waveform.

    Returns None for fewer than two gaps: a one-gap profile has no shape, and a
    hash of it would claim a similarity it cannot support.
    """
    values = [g for g in gaps if g is not None]
    if len(values) < 2:
        return None
    return content_hash(np.asarray(values, dtype=float))


def _known_recordings(conn):
    return {row["id"] for row in conn.execute("SELECT id FROM recordings")}


def _member_row_id(conn, recording_id, start_idx, end_idx):
    """The `motif_member` for this occurrence, when the event store has already
    been imported. NULL when it has not — the schema allows it (§3.3) because a
    sequence's position, span and gap are knowable before its events have been
    promoted to members."""
    row = conn.execute(
        """SELECT id FROM motif_member
            WHERE recording_id = ? AND start_idx = ? AND end_idx = ?
            ORDER BY id LIMIT 1""",
        (int(recording_id), int(start_idx), int(end_idx)),
    ).fetchone()
    return row["id"] if row is not None else None


def _table_counts(conn):
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("sequences", "sequence_members")}


def import_sequences_csv(conn, csv_path, *, event_store_path=None,
                         exclude_corpora=DEFAULT_EXCLUDED_CORPORA,
                         dry_run=False, progress=None):
    """Import a detector's sequence table. Returns an `ImportReport`.

    `event_store_path` is the store the CSV's endpoints refer to
    (`Plots/drop_motifs10/motifs` for the real file — the scout matched
    118/118 endpoints against it and 0/118 against the seed). Without it, every
    sequence is recorded with `needs_extraction = 1`: the claims are kept and
    nothing is guessed.

    `dry_run=True` reports without writing, proven by comparing the row counts
    of both tables before and after.

    `progress(done, total, message)` is called once per CSV row.

    **Idempotent**: `UNIQUE (sequence_key, origin)` is the natural key, and a
    row already present is counted as `already_present` and left alone rather
    than rewritten — a re-import must not silently replace members a later
    extraction pass has since filled in.
    """
    frame = pd.read_csv(csv_path)
    report = ImportReport(source=_repo_relative(csv_path), dry_run=dry_run,
                          n_rows=int(len(frame)))
    store_ref = _repo_relative(csv_path)

    events, by_event_id = [], {}
    if event_store_path:
        events = read_event_store(event_store_path)["events"]
        by_event_id = {str(e["event_id"]): e for e in events}
    else:
        report.warnings.append(
            "No event store was given, so no sequence's member events can be "
            "resolved; every row is recorded with needs_extraction = 1."
        )

    recordings = _known_recordings(conn)
    before = _table_counts(conn)
    created_at = _now()

    for index, row in enumerate(frame.to_dict("records"), start=1):
        outcome, detail = _import_one(
            conn, row, by_event_id, events, recordings, report,
            store_ref=store_ref, exclude_corpora=exclude_corpora,
            dry_run=dry_run, created_at=created_at,
        )
        report.outcomes[outcome] += 1
        report.samples.append({
            "source_ref": str(row.get("sequence_key")),
            "n_events_claimed": int(row.get("n") or 0),
            "outcome": outcome,
            "detail": detail,
        })
        if progress is not None:
            progress(index, int(len(frame)),
                     f"{row.get('sequence_key')}: {outcome}")

    if dry_run:
        conn.rollback()
        after = _table_counts(conn)
        if after != before:
            raise RuntimeError(
                "A dry run wrote to the database — this is a bug in "
                f"import_sequences_csv. Before: {before}, after: {after}."
            )
    else:
        conn.commit()
    return report


def _import_one(conn, row, by_event_id, events, recordings, report, *,
                store_ref, exclude_corpora, dry_run, created_at):
    """One CSV row. Never raises for bad data — an unusable row is counted with
    a reason, because a sequence table that dies halfway has said nothing about
    its second half."""
    key = str(row.get("sequence_key") or "").strip()
    if not key:
        report.skipped["no_sequence_key"] += 1
        return SKIPPED, "the row carries no sequence_key"

    existing = conn.execute(
        "SELECT id FROM sequences WHERE sequence_key = ? AND origin = ?",
        (key, ORIGIN),
    ).fetchone()
    if existing is not None:
        return ALREADY_PRESENT, f"sequence {existing['id']}"

    n_claimed = int(row["n"]) if row.get("n") == row.get("n") else None

    members = []
    endpoints_known = (str(row.get("start_event_id")) in by_event_id
                       and str(row.get("end_event_id")) in by_event_id)
    if endpoints_known:
        members = resolve_sequence_events(
            events,
            catalogue_id=row["catalogue_id"], channel=row["channel"],
            start_onset_s=float(row["start_onset_s"]),
            end_onset_s=float(row["end_onset_s"]),
            exclude_corpora=exclude_corpora,
        )
    elif by_event_id:
        report.warnings.append(
            f"{key}: its endpoints {row.get('start_event_id')!r} / "
            f"{row.get('end_event_id')!r} are not in the given event store, so "
            "its member events were not resolved. The claim is recorded; the "
            "events are not invented."
        )

    if not members:
        return _write_sequence(
            conn, report, key=key, row=row, members=[], gaps=[],
            n_claimed=n_claimed, recordings=recordings, store_ref=store_ref,
            dry_run=dry_run, created_at=created_at,
        )

    if n_claimed is not None and len(members) != n_claimed:
        # Recorded, not corrected. `n_events` stays as the source CLAIMED it
        # (§3.3) and the recovered members stand beside it, so a disagreement
        # is visible on the row instead of being resolved by whichever number
        # the importer happened to trust.
        report.warnings.append(
            f"{key}: the source claims {n_claimed} events and the recovery "
            f"rule found {len(members)}. Both are kept — n_events is the "
            "claim, sequence_members is the measurement."
        )

    return _write_sequence(
        conn, report, key=key, row=row, members=members,
        gaps=_gap_profile(members), n_claimed=n_claimed, recordings=recordings,
        store_ref=store_ref, dry_run=dry_run, created_at=created_at,
    )


def _write_sequence(conn, report, *, key, row, members, gaps, n_claimed,
                    recordings, store_ref, dry_run, created_at):
    """The one write site, for both the resolved and the unresolved case.

    Keeping them in one function is deliberate: the two states differ only by
    `needs_extraction` and the presence of members, and splitting them into two
    writers is how the two drift into disagreeing about the rest of the row.
    """
    needs_extraction = 0 if members else 1

    if members:
        recording_id = int(members[0]["recording_id"])
        channel = int(members[0]["channel"])
        start_idx = int(members[0]["snippet_start_idx"])
        end_idx = int(members[-1]["snippet_end_idx"])
        if recording_id not in recordings:
            report.warnings.append(
                f"{key}: its events bind to recording_id {recording_id}, which "
                "is not in `recordings`; the sequence is stored with no "
                "recording pointer rather than with a dangling one."
            )
            recording_id = None
    else:
        # Without members there is nothing to measure a span from: the CSV
        # carries onsets in seconds and no sampling rate of its own, and
        # converting them with a guessed fs would write a made-up index.
        recording_id = None
        channel = int(row["channel"]) if row.get("channel") == row.get("channel") else None
        start_idx = end_idx = None

    outcome = NEEDS_EXTRACTION if needs_extraction else RESOLVED
    if dry_run:
        return outcome, f"would write {len(members)} member(s)"

    cursor = conn.execute(
        """INSERT INTO sequences
               (sequence_key, origin, recording_id, channel, start_idx, end_idx,
                n_events, needs_extraction, source_kind, source_store,
                source_ref, annotation_id, content_hash, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)""",
        (key, ORIGIN, recording_id, channel, start_idx, end_idx,
         n_claimed, needs_extraction, SOURCE_KIND, store_ref, key,
         _sequence_hash(gaps) if members else None, created_at),
    )
    sequence_id = cursor.lastrowid

    for position, (event, gap) in enumerate(zip(members, gaps)):
        conn.execute(
            """INSERT INTO sequence_members
                   (sequence_id, position, member_id, start_idx, end_idx, gap_before)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (sequence_id, position,
             _member_row_id(conn, event["recording_id"],
                            event["snippet_start_idx"], event["snippet_end_idx"]),
             int(event["snippet_start_idx"]), int(event["snippet_end_idx"]), gap),
        )

    return outcome, f"sequence {sequence_id}, {len(members)} member(s)"
