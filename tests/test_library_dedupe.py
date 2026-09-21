"""
test_library_dedupe.py
======================
`docs/LIBRARY_STORAGE.md` §2.4 — what happens when a span that is already in
the Library arrives again.

Three cases and three outcomes:

  exact duplicate   same content hash                  -> the existing entry
  near-duplicate    same recording AND channel, IoU    -> FLAGGED, never merged
                    >= 0.5, onset within 0.25 x the
                    candidate's own duration
  different shape   neither                            -> a new entry

The two numbers are one choice each and both are recorded on every flag, so a
flag raised under one rule is never silently compared against another. The
onset term scales with the **candidate's** duration (spec §4.6), not the
incumbent's — a four-hour drop may start twenty minutes out and be the same
event; a forty-second spike may not.

The rule this file guards hardest: a shape recurring on **another channel** is
never a near-duplicate. Cross-channel recurrence is the point of the library,
and a dedupe rule that swallowed it would delete the finding.

Headless: pure interval maths plus one in-memory database.
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
from Working.library.dedupe import (
    IOU_THRESHOLD,
    ONSET_TOLERANCE_FRACTION,
    classify,
    find_duplicates,
    find_near_duplicates,
    is_near_duplicate,
    onset_agrees,
    span_iou,
)


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def conn(tmp_path):
    db = tmp_path / "dedupe.sqlite"
    init_db(str(db))
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def _recording(conn, channel, source_file="M_test.mat"):
    return q.insert_recording(
        conn, source_file, channel, fs=1.0, n_samples=100_000,
        global_offset=0, npy_path=f"DATA/derived/{source_file}_ch{channel}.npy",
    )


def _member(conn, recording_id, channel, start_idx, end_idx, content_hash):
    """An entry with one member at a known span and hash — the incumbent a
    candidate is judged against."""
    entry_id = R.insert_motif_entry(conn, recording_id, start_idx, end_idx)
    member_id = R.get_or_create_motif_member(
        conn, entry_id, recording_id, start_idx, end_idx,
    )
    conn.execute(
        "UPDATE motif_entry SET content_hash = ?, channel = ? WHERE id = ?",
        (content_hash, channel, entry_id),
    )
    conn.execute(
        "UPDATE motif_member SET content_hash = ?, channel = ? WHERE id = ?",
        (content_hash, channel, member_id),
    )
    conn.commit()
    return entry_id, member_id


# ── the two numbers ──────────────────────────────────────────────────────────

def test_the_thresholds_are_the_documented_defaults():
    """§2.4: IoU >= 0.5 is read off spec §4.6; 0.25 is LIBRARY_STORAGE's own
    choice for a coefficient the spec leaves open. Both live here."""
    assert IOU_THRESHOLD == 0.5
    assert ONSET_TOLERANCE_FRACTION == 0.25


# ── half one: reciprocal overlap ─────────────────────────────────────────────

def test_identical_spans_have_iou_one():
    assert span_iou(1000, 1100, 1000, 1100) == pytest.approx(1.0)


def test_disjoint_spans_have_iou_zero():
    assert span_iou(0, 100, 500, 600) == 0.0


def test_touching_spans_do_not_overlap():
    assert span_iou(0, 100, 100, 200) == 0.0


def test_half_overlap_is_a_third_not_a_half():
    """100 samples of intersection over 300 of union. The arithmetic is worth
    a test because "half overlapping" reads like 0.5 and is not."""
    assert span_iou(0, 200, 100, 300) == pytest.approx(100 / 300)


def test_the_exact_half_boundary_is_included():
    """IoU >= 0.5, not > 0.5. Intersection 100, union 200."""
    assert span_iou(0, 150, 50, 200) == pytest.approx(0.5)
    a = {"recording_id": 1, "channel": 0, "start_idx": 0, "end_idx": 150}
    b = {"recording_id": 1, "channel": 0, "start_idx": 50, "end_idx": 200}
    assert is_near_duplicate(a, b, fraction=1.0) is True


# ── half two: onset agreement, scaled to the CANDIDATE ───────────────────────

def test_onset_tolerance_scales_with_the_candidate_not_the_incumbent():
    """The candidate is the first argument. A long candidate tolerates a gap
    that the same gap against a short candidate must not."""
    # candidate 4000 long, incumbent 40 long, onsets 400 apart:
    # 400 <= 0.25 * 4000 -> agrees.
    assert onset_agrees(400, 4400, 0, 40) is True
    # swap the roles and the same pair disagrees: 400 > 0.25 * 40.
    assert onset_agrees(0, 40, 400, 4400) is False


def test_onset_agreement_at_the_exact_tolerance_is_accepted():
    assert onset_agrees(25, 125, 0, 100) is True     # 25 == 0.25 * 100
    assert onset_agrees(26, 126, 0, 100) is False


# ── the two halves together ──────────────────────────────────────────────────

def _span(recording_id=1, channel=0, start_idx=1000, end_idx=1100):
    return {"recording_id": recording_id, "channel": channel,
            "start_idx": start_idx, "end_idx": end_idx}


def test_a_shifted_copy_on_the_same_channel_is_a_near_duplicate():
    assert is_near_duplicate(_span(start_idx=1010, end_idx=1110), _span()) is True


def test_a_span_that_overlaps_but_starts_far_out_is_not_a_near_duplicate():
    """IoU alone would accept this; the onset half is what rejects it."""
    a = _span(start_idx=1060, end_idx=1160)
    b = _span(start_idx=1000, end_idx=1160)
    assert span_iou(a["start_idx"], a["end_idx"],
                    b["start_idx"], b["end_idx"]) >= IOU_THRESHOLD
    assert is_near_duplicate(a, b) is False


def test_the_same_shape_on_another_channel_is_never_a_near_duplicate():
    """The rule that must not be softened: cross-channel recurrence is the
    library's whole purpose, not a duplicate to be swallowed."""
    assert is_near_duplicate(_span(channel=3), _span(channel=0)) is False


def test_the_same_span_in_another_recording_is_never_a_near_duplicate():
    assert is_near_duplicate(_span(recording_id=2), _span(recording_id=1)) is False


# ── over the database ────────────────────────────────────────────────────────

def test_find_duplicates_returns_the_entry_holding_that_hash(conn):
    rec = _recording(conn, channel=0)
    entry_id, _ = _member(conn, rec, 0, 1000, 1100, "abc123")
    assert find_duplicates(conn, "abc123") == entry_id
    assert find_duplicates(conn, "no-such-hash") is None


def test_find_near_duplicates_reports_the_evidence_and_the_rule(conn):
    rec = _recording(conn, channel=0)
    _, member_id = _member(conn, rec, 0, 1000, 1100, "abc123")

    flags = find_near_duplicates(
        conn, recording_id=rec, channel=0, start_idx=1010, end_idx=1110,
    )
    assert len(flags) == 1
    flag = flags[0]
    assert flag["member_id"] == member_id
    assert flag["iou"] == pytest.approx(90 / 110)
    assert flag["onset_delta"] == 10
    # the rule the flag was raised under travels with it
    assert flag["iou_threshold"] == IOU_THRESHOLD
    assert flag["onset_tolerance_fraction"] == ONSET_TOLERANCE_FRACTION


def test_find_near_duplicates_can_exclude_the_row_being_judged(conn):
    """A member re-examined against the catalogue must not flag itself."""
    rec = _recording(conn, channel=0)
    _, member_id = _member(conn, rec, 0, 1000, 1100, "abc123")
    flags = find_near_duplicates(
        conn, recording_id=rec, channel=0, start_idx=1000, end_idx=1100,
        exclude_entry_id=None, exclude_member_id=member_id,
    )
    assert flags == []


def test_find_near_duplicates_ignores_the_other_channel(conn):
    rec0 = _recording(conn, channel=0)
    _member(conn, rec0, 0, 1000, 1100, "abc123")
    rec3 = _recording(conn, channel=3)
    assert find_near_duplicates(
        conn, recording_id=rec3, channel=3, start_idx=1000, end_idx=1100,
    ) == []


# ── the one function an importer calls ───────────────────────────────────────

def test_classify_calls_a_matching_hash_exact(conn):
    rec = _recording(conn, channel=0)
    entry_id, _ = _member(conn, rec, 0, 1000, 1100, "abc123")
    result = classify(conn, content_hash="abc123", recording_id=rec, channel=0,
                      start_idx=5000, end_idx=5100)
    assert result["verdict"] == "exact"
    assert result["entry_id"] == entry_id


def test_classify_calls_an_overlapping_new_hash_near(conn):
    rec = _recording(conn, channel=0)
    _member(conn, rec, 0, 1000, 1100, "abc123")
    result = classify(conn, content_hash="def456", recording_id=rec, channel=0,
                      start_idx=1010, end_idx=1110)
    assert result["verdict"] == "near"
    assert result["entry_id"] is None
    assert len(result["flags"]) == 1


def test_classify_calls_an_unrelated_span_new(conn):
    rec = _recording(conn, channel=0)
    _member(conn, rec, 0, 1000, 1100, "abc123")
    result = classify(conn, content_hash="def456", recording_id=rec, channel=0,
                      start_idx=50_000, end_idx=50_100)
    assert result["verdict"] == "new"
    assert result["entry_id"] is None
    assert result["flags"] == []


def test_classify_never_deletes_or_merges_a_row(conn):
    """§2.4: near-duplicates are flagged, never merged. The row count before
    and after is the cheapest way to assert it."""
    rec = _recording(conn, channel=0)
    _member(conn, rec, 0, 1000, 1100, "abc123")
    before = (conn.execute("SELECT COUNT(*) FROM motif_entry").fetchone()[0],
              conn.execute("SELECT COUNT(*) FROM motif_member").fetchone()[0])
    classify(conn, content_hash="def456", recording_id=rec, channel=0,
             start_idx=1010, end_idx=1110)
    after = (conn.execute("SELECT COUNT(*) FROM motif_entry").fetchone()[0],
             conn.execute("SELECT COUNT(*) FROM motif_member").fetchone()[0])
    assert before == after
