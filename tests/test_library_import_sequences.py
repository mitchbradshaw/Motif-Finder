"""
test_library_import_sequences.py
================================
`docs/LIBRARY_STORAGE.md` §4 and §3.5 — a detector's sequence table becoming
`sequences` rows with `origin = 'machine'`.

A sequence is not a long motif: its identity is its ordered composition, which
is why it is its own table and why the members carry `position` and
`gap_before`. The two states a sequence can arrive in are both tested here:

  * **resolved** — the member events are recoverable out of the event store by
    the rule the scout verified (the store's rows for the same catalogue span
    and channel, between the two endpoint onsets, in onset order). Members are
    written in order with their gaps, `needs_extraction = 0`.
  * **unresolved** — the endpoints name events no store holds. The sequence is
    written with `needs_extraction = 1` and **no members**: the claim is
    recorded, the events are not invented.

`origin` is what picks the write door (§3.5), so it is asserted explicitly on
every row: a machine sequence that arrived labelled `human` would break rule 5
silently.

Runs against `tests/fixtures/library/sequences.csv` and the five-event fixture
store beside it, never against `Plots/`.
"""

import os
import sqlite3
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database import queries as q
from Working.database.schema import init_db
from Working.library.importers.event_store import import_event_store
from Working.library.importers.sequences import (
    import_sequences_csv,
    resolve_sequence_events,
)

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "fixtures", "library")
STORE = os.path.join(FIXTURES, "event_store")
SEQUENCES = os.path.join(FIXTURES, "sequences.csv")
ALL_CORPORA = ()


@pytest.fixture()
def conn(tmp_path):
    db = tmp_path / "sequences.sqlite"
    init_db(str(db))
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    q.insert_recording(c, "M2_aug_concat_fs1.mat", 0, fs=1.0, n_samples=100_000,
                       global_offset=0, npy_path="DATA/derived/ch0.npy")
    q.insert_recording(c, "M2_aug_concat_fs1.mat", 1, fs=1.0, n_samples=100_000,
                       global_offset=100_000, npy_path="DATA/derived/ch1.npy")
    yield c
    c.close()


def _counts(conn):
    return {t: conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
            for t in ("sequences", "sequence_members")}


# ── the recovery rule, on its own ────────────────────────────────────────────

def test_the_recovery_rule_selects_the_span_and_channel_in_onset_order():
    """The scout's verified rule reproduces 118/118 real sequences. Here it has
    to return ev1 then ev2 and leave ev4 out — ev4 sits between them in time on
    the same channel but belongs to a different catalogue span."""
    from Working.Detection.drop_motifs import store as S
    events = S.load_events(STORE)
    picked = resolve_sequence_events(events, catalogue_id=1, channel=0,
                                     start_onset_s=1000.0, end_onset_s=5000.0)
    assert [e["event_id"] for e in picked] == ["id001_r1_1000", "id001_r1_5000"]


def test_the_recovery_rule_is_inclusive_at_both_ends():
    from Working.Detection.drop_motifs import store as S
    events = S.load_events(STORE)
    assert len(resolve_sequence_events(events, catalogue_id=1, channel=0,
                                       start_onset_s=1000.0,
                                       end_onset_s=1000.0)) == 1


# ── the import ───────────────────────────────────────────────────────────────

def test_a_resolvable_sequence_gets_its_members_in_order_with_gaps(conn):
    report = import_sequences_csv(conn, SEQUENCES, event_store_path=STORE)

    assert report.n_rows == 2
    assert report.outcomes.get("resolved") == 1
    assert report.outcomes.get("needs_extraction") == 1

    row = conn.execute(
        "SELECT * FROM sequences WHERE sequence_key = 'oyster_id1_ch0_1000s'"
    ).fetchone()
    assert row["origin"] == "machine"
    assert row["source_kind"] == "sequence_csv"
    assert row["needs_extraction"] == 0
    assert row["n_events"] == 2
    assert (row["recording_id"], row["channel"]) == (1, 0)
    assert (row["start_idx"], row["end_idx"]) == (1000, 5120)

    members = conn.execute(
        "SELECT * FROM sequence_members WHERE sequence_id = ? ORDER BY position",
        (row["id"],)).fetchall()
    assert [m["position"] for m in members] == [0, 1]
    assert [(m["start_idx"], m["end_idx"]) for m in members] \
        == [(1000, 1100), (5000, 5120)]
    # Seconds from the previous event's ONSET, at fs = 1.0.
    assert members[0]["gap_before"] is None
    assert members[1]["gap_before"] == pytest.approx(4000.0)


def test_an_unresolvable_sequence_is_recorded_with_no_members(conn):
    """The honest state: the claim (`n_events = 9`) is kept, the events are
    not invented, and Review can be offered an "extract events" queue."""
    import_sequences_csv(conn, SEQUENCES, event_store_path=STORE)
    row = conn.execute(
        "SELECT * FROM sequences WHERE sequence_key = 'reishi_id77_ch2_999s'"
    ).fetchone()
    assert row["needs_extraction"] == 1
    assert row["n_events"] == 9
    assert row["content_hash"] is None
    assert conn.execute(
        "SELECT COUNT(*) FROM sequence_members WHERE sequence_id = ?",
        (row["id"],)).fetchone()[0] == 0


def test_without_an_event_store_every_sequence_needs_extraction(conn):
    report = import_sequences_csv(conn, SEQUENCES)
    assert report.outcomes.get("needs_extraction") == 2
    assert _counts(conn)["sequence_members"] == 0


def test_members_link_to_the_motif_members_the_event_store_import_wrote(conn):
    """When the store has already been imported, a sequence member points at
    the `motif_member` row for that occurrence instead of duplicating it."""
    import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA)
    import_sequences_csv(conn, SEQUENCES, event_store_path=STORE)
    member_ids = [r["member_id"] for r in conn.execute(
        "SELECT member_id FROM sequence_members ORDER BY position")]
    assert all(m is not None for m in member_ids)


def test_a_second_run_imports_nothing(conn):
    import_sequences_csv(conn, SEQUENCES, event_store_path=STORE)
    before = _counts(conn)
    again = import_sequences_csv(conn, SEQUENCES, event_store_path=STORE)
    assert again.outcomes.get("already_present") == 2
    assert _counts(conn) == before


def test_a_dry_run_writes_nothing(conn):
    before = _counts(conn)
    report = import_sequences_csv(conn, SEQUENCES, event_store_path=STORE,
                                  dry_run=True)
    assert report.dry_run is True
    assert report.outcomes.get("resolved") == 1
    assert _counts(conn) == before


def test_progress_is_called_once_per_sequence(conn):
    seen = []
    import_sequences_csv(conn, SEQUENCES, event_store_path=STORE,
                         progress=lambda done, total, message: seen.append(
                             (done, total, message)))
    assert [d for d, _, _ in seen] == [1, 2]
    assert all(t == 2 for _, t, _ in seen)
