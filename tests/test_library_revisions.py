"""
test_library_revisions.py
=========================
`docs/LIBRARY_STORAGE.md` §2.5 / spec §4.2 — a member's span, re-described.

    "A `motif_member` row is the identity of a motif. It carries a current
    span pointer and a revision list. Revisions are spans, not edits to a
    span."

The two properties worth a test each:

1. **The pointer moves and the record stays.** Appending a revision moves
   `motif_member.current_revision_id`, stamps `superseded_at` on the one it
   replaces, and leaves every earlier row exactly where it was.
2. **`matching_revision` returns rev 1, not the current one.** A re-run of the
   detector reproduces the span it originally found; comparing that against a
   human's later redrawing would fail to recognise the member and write a
   duplicate. Rev 1 is what the matcher compares against; the current revision
   is what the researcher sees.

And the rule that must be refused rather than merely discouraged: a machine
revision carrying an `annotation_id`, or a human revision carrying a
`detection_id`. Detections are machine-only and annotations are human-only
(CLAUDE.md rule 5); the CHECK constraint polices the origin vocabulary but not
the pairing, so the pairing is checked in Python.

Headless: one temp-file database per test, no fixtures on disk.
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
from Working.database import runs as R
from Working.database.schema import init_db
from Working.library.revisions import (
    add_revision,
    current_revision,
    matching_revision,
    revision_list,
    stale_edges,
)


@pytest.fixture()
def conn(tmp_path):
    db = tmp_path / "revisions.sqlite"
    init_db(str(db))
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    yield c
    c.close()


@pytest.fixture()
def member_id(conn):
    """One entry with one member — the occurrence whose span gets revised."""
    recording_id = q.insert_recording(
        conn, "M_test.mat", 0, fs=1.0, n_samples=100_000, global_offset=0,
        npy_path="DATA/derived/M_test_ch0.npy",
    )
    entry_id = R.insert_motif_entry(conn, recording_id, 1000, 1100)
    return R.get_or_create_motif_member(conn, entry_id, recording_id, 1000, 1100)


def _detection(conn):
    """A machine detection to hang rev 1 on, with the run it belongs to."""
    config_id, _hash = R.get_or_create_config(conn, {"steps": [{"block": "noop"}]})
    recording_id = q.get_recording(conn, "M_test.mat", 0)["id"]
    run_id = R.insert_run(conn, config_id, recording_id, 0, 100_000)
    return R.insert_detection(conn, run_id, 1000, 1100)


def _annotation(conn, start_idx, end_idx):
    recording_id = q.get_recording(conn, "M_test.mat", 0)["id"]
    return q.insert_annotation(
        conn, recording_id, start_idx, end_idx, "interesting", source="test",
    )


# ── the chain ────────────────────────────────────────────────────────────────

def test_the_first_revision_is_rev_one_and_becomes_current(conn, member_id):
    detection_id = _detection(conn)
    revision_id = add_revision(conn, member_id, origin="machine",
                               detection_id=detection_id,
                               start_idx=1000, end_idx=1100)
    row = current_revision(conn, member_id)
    assert row["id"] == revision_id
    assert row["revision"] == 1
    assert row["superseded_at"] is None
    assert conn.execute(
        "SELECT current_revision_id FROM motif_member WHERE id = ?", (member_id,)
    ).fetchone()[0] == revision_id


def test_a_chain_of_three_moves_the_pointer_and_supersedes_the_rest(conn, member_id):
    """Three revisions: the detector's, and two human redrawings."""
    add_revision(conn, member_id, origin="machine",
                 detection_id=_detection(conn), start_idx=1000, end_idx=1100)
    add_revision(conn, member_id, origin="human",
                 annotation_id=_annotation(conn, 990, 1105),
                 start_idx=990, end_idx=1105)
    third = add_revision(conn, member_id, origin="human",
                         annotation_id=_annotation(conn, 995, 1102),
                         start_idx=995, end_idx=1102)

    rows = revision_list(conn, member_id)
    assert [r["revision"] for r in rows] == [1, 2, 3]
    assert [r["origin"] for r in rows] == ["machine", "human", "human"]
    # every earlier revision is stamped, the newest is not
    assert [r["superseded_at"] is None for r in rows] == [False, False, True]
    assert current_revision(conn, member_id)["id"] == third
    assert current_revision(conn, member_id)["start_idx"] == 995


def test_the_matcher_still_compares_against_rev_one(conn, member_id):
    """The sentence the module exists to keep true."""
    add_revision(conn, member_id, origin="machine",
                 detection_id=_detection(conn), start_idx=1000, end_idx=1100)
    add_revision(conn, member_id, origin="human",
                 annotation_id=_annotation(conn, 990, 1105),
                 start_idx=990, end_idx=1105)
    add_revision(conn, member_id, origin="human",
                 annotation_id=_annotation(conn, 995, 1102),
                 start_idx=995, end_idx=1102)

    rev1 = matching_revision(conn, member_id)
    assert rev1["revision"] == 1
    assert (rev1["start_idx"], rev1["end_idx"]) == (1000, 1100)
    assert rev1["id"] != current_revision(conn, member_id)["id"]


def test_a_human_edit_never_touches_the_detection(conn, member_id):
    """§2.5: the detection stays on its run, so the run still reproduces from
    its recipe."""
    detection_id = _detection(conn)
    add_revision(conn, member_id, origin="machine", detection_id=detection_id,
                 start_idx=1000, end_idx=1100)
    before = dict(R.get_detection(conn, detection_id))
    add_revision(conn, member_id, origin="human",
                 annotation_id=_annotation(conn, 990, 1105),
                 start_idx=990, end_idx=1105)
    assert dict(R.get_detection(conn, detection_id)) == before


# ── rule 5 ───────────────────────────────────────────────────────────────────

def test_a_machine_revision_carrying_an_annotation_is_refused(conn, member_id):
    with pytest.raises(ValueError, match="rule 5"):
        add_revision(conn, member_id, origin="machine",
                     annotation_id=_annotation(conn, 1000, 1100),
                     start_idx=1000, end_idx=1100)


def test_a_human_revision_carrying_a_detection_is_refused(conn, member_id):
    with pytest.raises(ValueError, match="rule 5"):
        add_revision(conn, member_id, origin="human",
                     detection_id=_detection(conn),
                     start_idx=1000, end_idx=1100)


def test_a_refused_revision_writes_nothing(conn, member_id):
    with pytest.raises(ValueError):
        add_revision(conn, member_id, origin="machine",
                     annotation_id=_annotation(conn, 1000, 1100),
                     start_idx=1000, end_idx=1100)
    assert revision_list(conn, member_id) == []
    assert current_revision(conn, member_id) is None


def test_an_unknown_origin_is_refused(conn, member_id):
    with pytest.raises(ValueError):
        add_revision(conn, member_id, origin="model",
                     start_idx=1000, end_idx=1100)


def test_an_unknown_member_is_refused(conn):
    with pytest.raises(ValueError, match="motif_member"):
        add_revision(conn, 9999, origin="machine", start_idx=1, end_idx=2)


# ── the obligation an extent edit creates ────────────────────────────────────

def test_editing_an_extent_names_the_edges_it_invalidated(conn, member_id):
    """Spec §4.2 rule 5: an extent edit invalidates that member's edge
    distances. They are reported, never silently kept as if still true."""
    recording_id = q.get_recording(conn, "M_test.mat", 0)["id"]
    entry_id = conn.execute(
        "SELECT entry_id FROM motif_member WHERE id = ?", (member_id,)
    ).fetchone()[0]
    other = R.get_or_create_motif_member(conn, entry_id, recording_id, 5000, 5100)
    edge_id = R.insert_motif_edge(
        conn, member_id, other, distance_function="scale_invariant",
        threshold=0.5, distance_value=0.12, recipe_hash="deadbeef",
    )
    assert stale_edges(conn, member_id) == [edge_id]
    assert stale_edges(conn, other) == [edge_id]
