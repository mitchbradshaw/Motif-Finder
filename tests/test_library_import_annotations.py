"""
test_library_import_annotations.py
==================================
`docs/LIBRARY_STORAGE.md` §5 — the `annotations` importer, and the one rule it
exists to get right.

The live database holds 11,269 annotation rows, and **11,234 of them are not
library content**: they are the 10-minute triage grid a person swept once to
sort windows for the CNN. Every one is exactly 600 samples at
`scale_viewed = '10min'` with `source = 'imported_10min'`, and the scout's
contiguity test found the longest run of adjacent interesting windows is three
— the grid does not encode sequences and must never be imported as any. That
leaves 31 sequences and 4 single events.

So the rule under test is

    SEQUENCE  <=>  source != 'imported_10min' AND relation_kind IS NOT 'type_specimen'

and the three-way split it produces. A test that only counted sequences would
pass on an importer that quietly swept 11,234 grid windows into the library, so
the counts on all three sides are asserted, not just the one that matters.

The second thing worth a test of its own is `n_events`: the note says
`"16 cycles"` or `"4x sharkfin sequence"`, and it also says `"20 - 70 mV"` and
`"10 min/cycle at start"`. A greedy parser turns a voltage range into an event
count, so the parser is conservative and its refusals are asserted alongside
its successes.

Headless: one temp-file database per test built by `init_db()`, with a small
real `.npy` on disk so a type specimen can be hashed from its actual samples.
Nothing here reads or writes `DATA/db/annotations.sqlite`.
"""

import os
import sqlite3
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database import queries as q
from Working.database.schema import init_db
from Working.library.importers.annotations import (
    GRID,
    SEQUENCE,
    SINGLE_EVENT,
    classify_annotation,
    import_annotations,
    parse_event_count,
    sequences_needing_extraction,
)

N_SAMPLES = 40_000


@pytest.fixture()
def conn(tmp_path):
    """A temp database with one recording whose channel `.npy` really exists.

    The type-specimen half of the importer hashes its span off disk, so a
    recording row pointing at a path that is not there would exercise the skip
    path rather than the thing under test.
    """
    db = tmp_path / "annotations.sqlite"
    init_db(str(db))
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row

    npy = tmp_path / "M2_aug_concat_fs1_CH00.npy"
    rng = np.random.default_rng(7)
    np.save(str(npy), rng.normal(size=N_SAMPLES))
    q.insert_recording(
        c, "M2_aug_concat_fs1.mat", 0, fs=1.0, n_samples=N_SAMPLES,
        global_offset=0, npy_path=str(npy),
    )
    yield c
    c.close()


def _recording_id(conn):
    return q.get_recording(conn, "M2_aug_concat_fs1.mat", 0)["id"]


def _grid_window(conn, start_idx):
    """One 10-minute triage window, shaped exactly like the 11,234 real ones."""
    return q.insert_annotation(
        conn, _recording_id(conn), start_idx, start_idx + 600, "interesting",
        source="imported_10min", scale_viewed="10min",
    )


def _catalogue_sequence(conn, start_idx, end_idx, note):
    return q.insert_annotation(
        conn, _recording_id(conn), start_idx, end_idx, "interesting",
        source="excel_catalog", note=note, status="candidate",
    )


def _type_specimen(conn, parent_id, start_idx, end_idx):
    return q.insert_annotation(
        conn, _recording_id(conn), start_idx, end_idx, "interesting",
        source="manual_ui", scale_viewed="4.68h",
        parent_annotation_id=parent_id, relation_kind="type_specimen",
    )


# ── the rule ─────────────────────────────────────────────────────────────────

def test_the_sequence_rule_splits_three_ways(conn):
    """31-sequences / 4-events / 11,234-grid in miniature, with every side
    counted — a test that asserted only the sequences would pass on an
    importer that swept the grid in too."""
    for i in range(5):
        _grid_window(conn, 1000 + i * 600)
    a = _catalogue_sequence(conn, 20_000, 21_000, "16 cycles; 20 - 70 mV")
    _catalogue_sequence(conn, 22_000, 23_000, "nested sharkfin sequence")
    _type_specimen(conn, a, 20_100, 20_140)
    # A manual_ui span that is NOT a type specimen is library content.
    q.insert_annotation(
        conn, _recording_id(conn), 30_000, 31_000, "interesting",
        source="manual_ui", scale_viewed="87.26h",
    )

    report = import_annotations(conn)

    assert report.counts["sequences"] == 3
    assert report.counts["events"] == 1
    assert report.counts["grid_skipped"] == 5
    assert conn.execute("SELECT COUNT(*) FROM sequences").fetchone()[0] == 3
    assert conn.execute(
        "SELECT COUNT(*) FROM sequences WHERE origin = 'human'"
    ).fetchone()[0] == 3


def test_classify_annotation_names_all_three(conn):
    rows = {
        GRID: _grid_window(conn, 1000),
        SEQUENCE: _catalogue_sequence(conn, 20_000, 21_000, "sharkfin"),
    }
    rows[SINGLE_EVENT] = _type_specimen(conn, rows[SEQUENCE], 20_100, 20_140)
    for expected, annotation_id in rows.items():
        row = q.get_annotation(conn, annotation_id)
        assert classify_annotation(row) == expected


def test_grid_rows_are_never_imported(conn):
    """The whole point. A database of nothing but grid windows imports zero
    sequences, zero members and zero entries."""
    for i in range(20):
        _grid_window(conn, 1000 + i * 600)

    report = import_annotations(conn)

    assert report.counts["grid_skipped"] == 20
    assert report.counts["sequences"] == 0
    assert report.counts["events"] == 0
    for table in ("sequences", "sequence_members", "motif_entry", "motif_member"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


# ── the two products ─────────────────────────────────────────────────────────

def test_a_sequence_is_written_needing_extraction(conn):
    _catalogue_sequence(conn, 20_000, 21_000, "Regular sequence of 100 furrycaterpillars")
    import_annotations(conn)

    row = conn.execute("SELECT * FROM sequences").fetchone()
    assert row["origin"] == "human"
    assert row["source_kind"] == "annotation"
    assert row["annotation_id"] is not None
    assert row["needs_extraction"] == 1
    assert row["n_events"] == 100
    # No events were invented for it.
    assert conn.execute(
        "SELECT COUNT(*) FROM sequence_members WHERE sequence_id = ?", (row["id"],)
    ).fetchone()[0] == 0


def test_a_type_specimen_becomes_an_event_entry_with_a_real_hash(conn):
    parent = _catalogue_sequence(conn, 20_000, 21_000, "single cycle; type specimen")
    _type_specimen(conn, parent, 20_100, 20_140)

    import_annotations(conn)

    entry = conn.execute(
        "SELECT * FROM motif_entry WHERE source_kind = 'annotation'"
    ).fetchone()
    assert entry is not None
    assert entry["scale"] == "event"
    assert entry["start_idx"] == 20_100 and entry["end_idx"] == 20_140
    assert entry["content_hash"] and len(entry["content_hash"]) == 32
    member = conn.execute(
        "SELECT * FROM motif_member WHERE entry_id = ?", (entry["id"],)
    ).fetchone()
    assert member["content_hash"] == entry["content_hash"]
    revision = conn.execute(
        "SELECT * FROM motif_member_revision WHERE member_id = ?", (member["id"],)
    ).fetchone()
    assert revision["origin"] == "human"
    assert revision["annotation_id"] is not None
    assert revision["detection_id"] is None      # rule 5


def test_a_type_specimen_whose_channel_is_missing_is_skipped_not_crashed(conn, tmp_path):
    """A hash needs the samples. A clone with no `DATA/derived` must report the
    skip rather than raise out of the importer."""
    conn.execute(
        "UPDATE recordings SET npy_path = ?",
        (str(tmp_path / "not-here.npy"),),
    )
    conn.commit()
    parent = _catalogue_sequence(conn, 20_000, 21_000, "single cycle; type specimen")
    _type_specimen(conn, parent, 20_100, 20_140)

    report = import_annotations(conn)

    assert report.counts["events"] == 0
    assert len(report.skips) == 1
    assert "not-here.npy" in report.skips[0]["reason"] \
        or "cannot be read" in report.skips[0]["reason"]


# ── the note parser ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("note,expected", [
    ("amplitude modulation am increasing; frequency modulation fm decreasing; "
     "16 cycles; 20 - 70 mV", 16),
    ("Regular sequence of 100 furrycaterpillars", 100),
    ("4x sharkfin sequence", 4),
    ("60 spikes (7 mV, 10 min/cycle at start, 3 min/cycle at end)", 60),
    ("nested sharkfin sequence", None),
    ("single cycle; type specimen", None),
    ("20 - 70 mV", None),
    ("10 min/cycle at start, 3 min/cycle at end", None),
    ("", None),
    (None, None),
])
def test_parse_event_count_is_conservative(note, expected):
    assert parse_event_count(note) == expected


def test_counts_that_disagree_are_refused_rather_than_guessed():
    """Two different counts in one note is not a count — it is a sentence the
    parser does not understand, and inventing one would put a made-up number
    on a library row."""
    assert parse_event_count("16 cycles; 4x sharkfin sequence") is None


def test_how_many_got_a_count_is_reported(conn):
    _catalogue_sequence(conn, 20_000, 21_000, "16 cycles")
    _catalogue_sequence(conn, 22_000, 23_000, "nested sharkfin sequence")
    report = import_annotations(conn)
    assert report.counts["sequences"] == 2
    assert report.counts["n_events_parsed"] == 1


# ── idempotence, dry run, and the extraction queue ───────────────────────────

def test_re_running_imports_nothing_new(conn):
    parent = _catalogue_sequence(conn, 20_000, 21_000, "16 cycles")
    _type_specimen(conn, parent, 20_100, 20_140)
    import_annotations(conn)
    before = (
        conn.execute("SELECT COUNT(*) FROM sequences").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM motif_entry").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM motif_member_revision").fetchone()[0],
    )

    second = import_annotations(conn)

    after = (
        conn.execute("SELECT COUNT(*) FROM sequences").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM motif_entry").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM motif_member_revision").fetchone()[0],
    )
    assert after == before
    assert second.counts["sequences"] == 0
    assert second.counts["already_imported"] == 2


def test_dry_run_writes_nothing(conn):
    parent = _catalogue_sequence(conn, 20_000, 21_000, "16 cycles")
    _type_specimen(conn, parent, 20_100, 20_140)

    report = import_annotations(conn, dry_run=True)

    assert report.dry_run is True
    assert report.counts["sequences"] == 1
    assert conn.execute("SELECT COUNT(*) FROM sequences").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM motif_entry").fetchone()[0] == 0


def test_sequences_needing_extraction_is_the_review_queue(conn):
    _catalogue_sequence(conn, 20_000, 21_000, "16 cycles")
    _catalogue_sequence(conn, 22_000, 23_000, "4x sharkfin sequence")
    import_annotations(conn)
    conn.execute("UPDATE sequences SET needs_extraction = 0 WHERE start_idx = 22000")
    conn.commit()

    queue = sequences_needing_extraction(conn)

    assert [r["start_idx"] for r in queue] == [20_000]


def test_progress_is_called_per_row(conn):
    for i in range(3):
        _grid_window(conn, 1000 + i * 600)
    _catalogue_sequence(conn, 20_000, 21_000, "16 cycles")
    seen = []
    import_annotations(conn, progress=lambda done, total, what: seen.append((done, total)))
    assert seen and seen[-1] == (4, 4)
