"""
test_discovery_scoreboard.py
=============================
Spec §7.3 — Discovery's scoreboard, on a hand-built detections/annotations
fixture whose every cell is computed by hand in the docstring below.

    "Columns: run, found, already judged, reviewed, interesting, precision,
    recall, null expects, x null. A run row expands into one row per channel.
    **Precision is labelled precision.** **Recall is per channel, scoped to
    that channel's reviewed overlap** ('0.71 over 14 h'). With no reviewed
    overlap it reads `no reviewed overlap`, not blank. The run total states
    the hours it pooled. An algorithm with nothing reviewed reads `not yet
    scored`. **Already judged** is its own column — how many of this run's
    detections had a verdict before the run started."

The arithmetic is the point, so the fixture is small and every number here
is derived in a comment rather than read back out of the implementation.

The fixture (fs = 1 Hz, so one sample is one second)
----------------------------------------------------
Recording R0, 10 000 samples. The run's span is the whole channel.

reviewed_spans   [0, 2000)  [5000, 6000)              -> 3000 s = 0.8333 h

annotations      A1 [ 100,  200) interesting      (inside reviewed)
                 A2 [1000, 1100) interesting      (inside reviewed)
                 A3 [1500, 1600) not_interesting  (inside reviewed)
                 A4 [5200, 5300) interesting      (inside reviewed)
                 A5 [7000, 7100) interesting      (OUTSIDE reviewed)
                 A6 [1200, 1300) interesting      (inside reviewed, no detection)

detections of    D1 [ 100,  200)  matches A1            -> reviewed, interesting
run R            D2 [1000, 1098)  IoU 0.98 vs A2        -> reviewed, interesting
                 D3 [1500, 1600)  matches A3            -> reviewed, not interesting
                 D4 [1800, 1900)  matches nothing       -> reviewed, a false positive
                 D5 [3000, 3100)  OUTSIDE reviewed      -> found only
                 D6 [5200, 5260)  IoU 0.60 vs A4        -> reviewed, interesting

found            6
reviewed         5   (D1 D2 D3 D4 D6 — D5 is where nobody looked)
interesting      3   (D1 D2 D6)
precision        3 / 5 = 0.60
already judged   4   (D1 D2 D3 D6 — each matches an annotation written
                      before the run started; D4 and D5 do not)
recall           3 of the 4 interesting annotations inside reviewed coverage
                 (A1 A2 A4 A6; A5 is outside it and is not counted)
                 -> 0.75 over 0.8333 h
null expects     2   (the paired surrogate run's detections)
x null           6 / 2 = 3.0
"""

import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database import queries as q
from Working.database import runs as run_db
from Working.database.schema import init_db
from Working.discovery.matching import MATCHING_RULE
from Working.discovery.scoreboard import channel_score, group_score, run_total, shape_mismatch

SOURCE = "manual_ui"
BEFORE = "2026-09-01T00:00:00"
AFTER = "2026-09-20T00:00:00"


def _recording(conn, channel=0, n=10_000):
    return q.insert_recording(conn, "fixture.mat", channel, 1.0, n, 0, f"fixture_CH{channel}.npy")


def _run(conn, recording_id, *, span=(0, 10_000), started_at=AFTER, status="completed",
         steps=None, run_group_id=None):
    config_id, _ = run_db.get_or_create_config(
        conn, {"steps": steps or [{"stage": "detection", "algorithm": "threshold", "params": {}}]})
    run_id = run_db.insert_run(conn, config_id, recording_id, span[0], span[1],
                               started_at=started_at, status=status)
    if run_group_id is not None:
        run_db.update_run(conn, run_id, run_group_id=run_group_id)
    return run_id


def _fixture():
    """The database described in the module docstring."""
    conn = init_db(":memory:")
    rec = _recording(conn)
    for a, b in ((0, 2000), (5000, 6000)):
        q.insert_reviewed_span(conn, rec, a, b, SOURCE, reviewed_at=BEFORE)
    for a, b, v in ((100, 200, "interesting"), (1000, 1100, "interesting"),
                    (1500, 1600, "not_interesting"), (5200, 5300, "interesting"),
                    (7000, 7100, "interesting"), (1200, 1300, "interesting")):
        q.insert_annotation(conn, rec, a, b, v, SOURCE, created_at=BEFORE)
    run_id = _run(conn, rec)
    for a, b in ((100, 200), (1000, 1098), (1500, 1600), (1800, 1900), (3000, 3100), (5200, 5260)):
        run_db.insert_detection(conn, run_id, a, b, score=0.9)
    null_id = _run(conn, rec)
    for a, b in ((400, 500), (6100, 6200)):
        run_db.insert_detection(conn, null_id, a, b, score=0.5)
    run_db.update_run(conn, null_id, surrogate_of_run_id=run_id)
    return conn, rec, run_id, null_id


# ── every cell of one channel row ───────────────────────────────────────────

def test_the_channel_row_is_the_hand_computed_arithmetic():
    conn, rec, run_id, _ = _fixture()
    try:
        row = channel_score(conn, run_id)
        assert row["found"] == 6
        assert row["reviewed"] == 5
        assert row["interesting"] == 3
        assert row["already_judged"] == 4
        assert row["precision"] == pytest.approx(0.6)
        assert row["recall"] == pytest.approx(0.75)
        assert row["recall_over_h"] == pytest.approx(3000 / 3600)
        assert row["reviewed_h"] == pytest.approx(3000 / 3600)
    finally:
        conn.close()


def test_precision_is_labelled_precision_and_is_interesting_over_reviewed():
    conn, _, run_id, _ = _fixture()
    try:
        row = channel_score(conn, run_id)
        assert row["precision_label"] == "precision"
        assert row["precision"] == pytest.approx(row["interesting"] / row["reviewed"])
    finally:
        conn.close()


def test_the_null_run_fills_null_expects_and_x_null():
    conn, _, run_id, null_id = _fixture()
    try:
        row = channel_score(conn, run_id, null_run_id=null_id)
        assert row["null_expects"] == 2
        assert row["x_null"] == pytest.approx(3.0)
    finally:
        conn.close()


def test_the_surrogate_pairing_is_found_without_being_told():
    """`runs.surrogate_of_run_id` already records the pairing; the scoreboard
    reads it rather than making the caller thread the null run id through."""
    conn, _, run_id, _ = _fixture()
    try:
        assert channel_score(conn, run_id)["null_expects"] == 2
    finally:
        conn.close()


def test_the_row_records_the_matching_rule_it_was_computed_under():
    conn, _, run_id, _ = _fixture()
    try:
        assert channel_score(conn, run_id)["rule"]["criterion"] == MATCHING_RULE
        assert channel_score(conn, run_id)["rule"]["iou"] == 0.5
    finally:
        conn.close()


# ── the §4.6 rule actually bites ────────────────────────────────────────────

def test_a_detection_that_clears_iou_but_misses_the_onset_is_not_interesting():
    """Candidate [8000, 8100) against interesting [8026, 8126): IoU 0.587,
    over the 0.5 threshold, but the onset gap 26 exceeds 0.25 x 100 = 25.
    A bare-IoU scoreboard would score this run 1/1; §4.6 scores it 0/1."""
    conn = init_db(":memory:")
    try:
        rec = _recording(conn)
        q.insert_reviewed_span(conn, rec, 7900, 8300, SOURCE, reviewed_at=BEFORE)
        q.insert_annotation(conn, rec, 8026, 8126, "interesting", SOURCE, created_at=BEFORE)
        run_id = _run(conn, rec)
        run_db.insert_detection(conn, run_id, 8000, 8100)
        row = channel_score(conn, run_id)
        assert row["reviewed"] == 1
        assert row["interesting"] == 0
        assert row["precision"] == pytest.approx(0.0)
        # and it is not "already judged" either — no verdict attaches to it
        assert row["already_judged"] == 0
    finally:
        conn.close()


def test_a_looser_rule_passed_in_changes_the_cells():
    conn = init_db(":memory:")
    try:
        rec = _recording(conn)
        q.insert_reviewed_span(conn, rec, 7900, 8300, SOURCE, reviewed_at=BEFORE)
        q.insert_annotation(conn, rec, 8026, 8126, "interesting", SOURCE, created_at=BEFORE)
        run_id = _run(conn, rec)
        run_db.insert_detection(conn, run_id, 8000, 8100)
        row = channel_score(conn, run_id, rule={"criterion": MATCHING_RULE, "iou": 0.5, "onset": 0.3})
        assert row["interesting"] == 1
        assert row["rule"]["onset"] == 0.3
    finally:
        conn.close()


# ── the empty and absent states read as words, never as blanks ──────────────

def test_no_reviewed_overlap_reads_no_reviewed_overlap_not_blank():
    conn = init_db(":memory:")
    try:
        rec = _recording(conn)
        run_id = _run(conn, rec)
        run_db.insert_detection(conn, run_id, 100, 200)
        row = channel_score(conn, run_id)
        assert row["recall"] is None
        assert row["recall_note"] == "no reviewed overlap"
        assert row["precision"] is None
        assert row["note"] == "not yet scored"
        assert row["found"] == 1
    finally:
        conn.close()


def test_reviewed_coverage_with_no_interesting_annotation_still_gives_precision():
    """The human looked and marked nothing interesting: precision 0, not
    'not yet scored'. Recall has no positives to find and says so."""
    conn = init_db(":memory:")
    try:
        rec = _recording(conn)
        q.insert_reviewed_span(conn, rec, 0, 2000, SOURCE, reviewed_at=BEFORE)
        run_id = _run(conn, rec)
        run_db.insert_detection(conn, run_id, 100, 200)
        row = channel_score(conn, run_id)
        assert row["precision"] == pytest.approx(0.0)
        assert row["note"] is None
        assert row["recall"] is None
        assert row["recall_note"] == "nothing marked interesting in the reviewed overlap"
    finally:
        conn.close()


def test_a_running_run_says_so_across_the_row():
    conn = init_db(":memory:")
    try:
        rec = _recording(conn)
        run_id = _run(conn, rec, status="running")
        row = channel_score(conn, run_id)
        assert row["status"] == "running"
        assert row["note"] == "running"
        assert row["precision"] is None and row["recall"] is None
    finally:
        conn.close()


def test_reviewed_coverage_is_clipped_to_the_runs_span():
    """A run over [0, 1000) must not claim the reviewed hours of [5000, 6000):
    recall is scoped to *that channel's reviewed overlap with this run*."""
    conn, rec, _, _ = _fixture()
    try:
        short = _run(conn, rec, span=(0, 1000))
        run_db.insert_detection(conn, short, 100, 200)
        row = channel_score(conn, short)
        assert row["reviewed_h"] == pytest.approx(1000 / 3600)
        assert row["recall_over_h"] == pytest.approx(1000 / 3600)
        assert row["recall"] == pytest.approx(1.0)      # A1 is the only positive in [0, 1000)
    finally:
        conn.close()


# ── the run total pools the channels and states the hours ───────────────────

def test_the_total_pools_channels_and_states_the_hours_it_pooled():
    conn = init_db(":memory:")
    try:
        group_id = run_db.create_run_group(conn)
        run_ids = []
        for ch, (rev_end, n_int) in enumerate([(2000, 2), (1000, 1)]):
            rec = _recording(conn, channel=ch)
            q.insert_reviewed_span(conn, rec, 0, rev_end, SOURCE, reviewed_at=BEFORE)
            for i in range(n_int):
                q.insert_annotation(conn, rec, 100 + 300 * i, 200 + 300 * i, "interesting",
                                    SOURCE, created_at=BEFORE)
            run_id = _run(conn, rec, run_group_id=group_id)
            for i in range(n_int):
                run_db.insert_detection(conn, run_id, 100 + 300 * i, 200 + 300 * i)
            run_ids.append(run_id)

        total = run_total(conn, run_ids)
        assert total["found"] == 3
        assert total["reviewed"] == 3
        assert total["interesting"] == 3
        assert total["precision"] == pytest.approx(1.0)
        assert total["pooled_h"] == pytest.approx(3000 / 3600)
        assert total["recall"] == pytest.approx(1.0)
        assert total["n_channels"] == 2
    finally:
        conn.close()


def test_the_pooled_recall_pools_the_counts_not_the_ratios():
    """The fixture that separates the two rules, which the hours-weighted
    version could not be told apart from.

    Channel A: 10 positives in 1 h, all 10 found — recall 1.0.
    Channel B: 10 positives in 10 h, none found — recall 0.0.

    Count-pooled: 10 of 20 = **0.50**, which is what the run did.
    Hours-weighted: (1.0 x 1 + 0.0 x 10) / 11 = **0.09**, which is a statement
    about where the hours are, not about what the run found. A plain mean is
    0.50 too, which is why the fixture has to have unequal positive density per
    hour for the test to discriminate at all."""
    conn = init_db(":memory:")
    try:
        rec_a = _recording(conn, channel=0, n=50_000)
        q.insert_reviewed_span(conn, rec_a, 0, 3600, SOURCE, reviewed_at=BEFORE)
        run_a = _run(conn, rec_a, span=(0, 50_000))
        for i in range(10):
            at = 100 + i * 300
            q.insert_annotation(conn, rec_a, at, at + 100, "interesting", SOURCE, created_at=BEFORE)
            run_db.insert_detection(conn, run_a, at, at + 100)

        rec_b = _recording(conn, channel=1, n=50_000)
        q.insert_reviewed_span(conn, rec_b, 0, 36_000, SOURCE, reviewed_at=BEFORE)
        run_b = _run(conn, rec_b, span=(0, 50_000))
        for i in range(10):
            at = 100 + i * 3000
            q.insert_annotation(conn, rec_b, at, at + 100, "interesting", SOURCE, created_at=BEFORE)

        total = run_total(conn, [run_a, run_b])
        assert total["recall_positives"] == 20 and total["recall_found"] == 10
        assert total["recall"] == pytest.approx(0.5)
        assert total["recall"] != pytest.approx((1.0 * 1 + 0.0 * 10) / 11, abs=0.01)
        assert total["pooled_h"] == pytest.approx((3600 + 36_000) / 3600)
    finally:
        conn.close()


def test_the_total_states_the_hours_it_pooled_without_weighting_by_them():
    """Channel A: 1 of 2 found over 2000 s. Channel B: 1 of 1 over 1000 s.
    Counts pool to 2 of 3 = 0.667, and the row still states the 3000 s."""
    conn = init_db(":memory:")
    try:
        run_ids = []
        rec_a = _recording(conn, channel=0)
        q.insert_reviewed_span(conn, rec_a, 0, 2000, SOURCE, reviewed_at=BEFORE)
        q.insert_annotation(conn, rec_a, 100, 200, "interesting", SOURCE, created_at=BEFORE)
        q.insert_annotation(conn, rec_a, 900, 1000, "interesting", SOURCE, created_at=BEFORE)
        run_a = _run(conn, rec_a)
        run_db.insert_detection(conn, run_a, 100, 200)
        run_ids.append(run_a)

        rec_b = _recording(conn, channel=1)
        q.insert_reviewed_span(conn, rec_b, 0, 1000, SOURCE, reviewed_at=BEFORE)
        q.insert_annotation(conn, rec_b, 100, 200, "interesting", SOURCE, created_at=BEFORE)
        run_b = _run(conn, rec_b)
        run_db.insert_detection(conn, run_b, 100, 200)
        run_ids.append(run_b)

        total = run_total(conn, run_ids)
        assert total["recall"] == pytest.approx(2 / 3)
        assert total["pooled_h"] == pytest.approx(3000 / 3600)
    finally:
        conn.close()


def test_a_channel_with_no_reviewed_overlap_is_left_out_of_the_pooled_recall():
    conn = init_db(":memory:")
    try:
        rec_a = _recording(conn, channel=0)
        q.insert_reviewed_span(conn, rec_a, 0, 2000, SOURCE, reviewed_at=BEFORE)
        q.insert_annotation(conn, rec_a, 100, 200, "interesting", SOURCE, created_at=BEFORE)
        run_a = _run(conn, rec_a)
        run_db.insert_detection(conn, run_a, 100, 200)

        rec_b = _recording(conn, channel=1)      # nothing reviewed at all
        run_b = _run(conn, rec_b)
        run_db.insert_detection(conn, run_b, 100, 200)

        total = run_total(conn, [run_a, run_b])
        assert total["recall"] == pytest.approx(1.0)
        assert total["pooled_h"] == pytest.approx(2000 / 3600)
        assert total["found"] == 2
    finally:
        conn.close()


def test_group_score_expands_a_run_group_into_one_row_per_channel():
    conn = init_db(":memory:")
    try:
        group_id = run_db.create_run_group(conn)
        for ch in range(3):
            rec = _recording(conn, channel=ch)
            q.insert_reviewed_span(conn, rec, 0, 1000, SOURCE, reviewed_at=BEFORE)
            run_id = _run(conn, rec, run_group_id=group_id)
            run_db.insert_detection(conn, run_id, 100, 200)
        out = group_score(conn, group_id)
        assert [c["channel"] for c in out["channels"]] == [0, 1, 2]
        assert out["total"]["found"] == 3
        assert out["run_group_id"] == group_id
    finally:
        conn.close()


def test_group_score_leaves_the_surrogate_runs_out_of_the_channel_rows():
    """A fan-out with the null on writes 2N runs into the group; the
    scoreboard must show N channel rows, with the nulls in `null expects`."""
    conn = init_db(":memory:")
    try:
        group_id = run_db.create_run_group(conn)
        rec = _recording(conn, channel=0)
        run_id = _run(conn, rec, run_group_id=group_id)
        run_db.insert_detection(conn, run_id, 100, 200)
        null_id = _run(conn, rec, run_group_id=group_id)
        run_db.insert_detection(conn, null_id, 400, 500)
        run_db.update_run(conn, null_id, surrogate_of_run_id=run_id)
        out = group_score(conn, group_id)
        assert len(out["channels"]) == 1
        assert out["channels"][0]["null_expects"] == 1
        assert out["total"]["null_expects"] == 1
        assert out["total"]["x_null"] == pytest.approx(1.0)
    finally:
        conn.close()


# ── the section on screen, not the whole run ────────────────────────────────

def test_a_span_narrows_the_row_to_the_section_on_screen():
    """The page scores the section in the scope, not the run's whole span: a
    precision computed over hours the researcher is not looking at is not the
    number the page claims."""
    conn, _, run_id, _ = _fixture()
    try:
        whole = channel_score(conn, run_id)
        section = channel_score(conn, run_id, span=(0, 2000))
        assert whole["found"] == 6 and section["found"] == 4      # D1 D2 D3 D4
        assert section["reviewed"] == 4
        assert section["interesting"] == 2                        # D1 D2
        assert section["precision"] == pytest.approx(0.5)
        assert section["reviewed_h"] == pytest.approx(2000 / 3600)
        assert section["recall"] == pytest.approx(2 / 3)          # A1 A2 found, A6 missed
    finally:
        conn.close()


def test_a_span_is_intersected_with_the_run_never_widened():
    conn, rec, _, _ = _fixture()
    try:
        short = _run(conn, rec, span=(0, 1000))
        run_db.insert_detection(conn, short, 100, 200)
        row = channel_score(conn, short, span=(0, 10_000))
        assert row["span"] == [0, 1000]
        assert row["reviewed_h"] == pytest.approx(1000 / 3600)
    finally:
        conn.close()


def test_a_run_the_section_does_not_reach_reads_words_not_zeroes():
    conn, rec, _, _ = _fixture()
    try:
        elsewhere = _run(conn, rec, span=(5000, 6000))
        run_db.insert_detection(conn, elsewhere, 5200, 5300)
        row = channel_score(conn, elsewhere, span=(0, 2000))
        assert row["found"] == 0
        assert row["precision"] is None and row["recall"] is None
        assert "does not reach" in row["note"]
    finally:
        conn.close()


def test_the_null_is_counted_over_the_same_section():
    conn, _, run_id, null_id = _fixture()
    try:
        # the null's two detections are at 400 and 6100: only the first is in [0, 2000)
        row = channel_score(conn, run_id, span=(0, 2000))
        assert row["null_expects"] == 1
        assert row["x_null"] == pytest.approx(4.0)
    finally:
        conn.close()


# ── a precision of 0 that is about the span shapes, not the algorithm ───────

def test_shape_mismatch_names_the_two_medians_and_the_best_reachable_iou():
    """11,234 of this project's 11,269 annotations are the fixed 600-sample
    windows of the 10-minute CNN window set — window labels, not event spans —
    while a real drop runs 21 to 4,875 samples, median 179. Nested as well as
    they can be, 179 against 600 reaches IoU 0.30, so under §4.6 no alignment
    can ever count one. A scoreboard printing 0.00 without saying that would be
    the most misleading number on the page."""
    note = shape_mismatch([179] * 5, [600] * 5, 0.5)
    assert note is not None
    assert "179" in note and "600" in note and "0.30" in note
    assert "not" in note and "algorithm" in note


def test_shape_mismatch_is_silent_when_the_spans_can_match():
    assert shape_mismatch([600] * 3, [600] * 3, 0.5) is None
    assert shape_mismatch([500] * 3, [600] * 3, 0.5) is None      # best 0.83
    assert shape_mismatch([], [600], 0.5) is None


def test_a_zero_precision_over_window_labels_carries_the_warning():
    conn = init_db(":memory:")
    try:
        rec = _recording(conn)
        q.insert_reviewed_span(conn, rec, 0, 6000, SOURCE, reviewed_at=BEFORE)
        # the human's fixed 600-sample windows
        for a in (600, 1800, 3000):
            q.insert_annotation(conn, rec, a, a + 600, "interesting", SOURCE, created_at=BEFORE)
        run_id = _run(conn, rec)
        # the machine's real events, 180 samples each, right inside them
        for a in (700, 1900, 3100):
            run_db.insert_detection(conn, run_id, a, a + 180)
        row = channel_score(conn, run_id)
        assert row["reviewed"] == 3
        assert row["interesting"] == 0
        assert row["precision"] == pytest.approx(0.0)
        assert row["precision_note"] and "cannot match" in row["precision_note"]
    finally:
        conn.close()


def test_a_zero_precision_the_shapes_allow_carries_no_warning():
    """The same run against annotations of its own width scores 0 honestly:
    the detections simply sit somewhere the human did not mark."""
    conn = init_db(":memory:")
    try:
        rec = _recording(conn)
        q.insert_reviewed_span(conn, rec, 0, 6000, SOURCE, reviewed_at=BEFORE)
        for a in (600, 1800, 3000):
            q.insert_annotation(conn, rec, a, a + 180, "interesting", SOURCE, created_at=BEFORE)
        run_id = _run(conn, rec)
        for a in (1000, 2200, 3400):
            run_db.insert_detection(conn, run_id, a, a + 180)
        row = channel_score(conn, run_id)
        assert row["interesting"] == 0 and row["precision"] == pytest.approx(0.0)
        assert row["precision_note"] is None
    finally:
        conn.close()


# ── the null is a draw count, and x null is one scope ──────────────────────

def test_the_row_says_how_many_null_draws_it_averaged():
    """A column called "null expects" carrying one surrogate realisation is not
    an expectation. The row states the draw count beside it so the page can
    say so (§9.4 asks for 200; `run_paired_recipe` writes one today)."""
    conn, _, run_id, null_id = _fixture()
    try:
        row = channel_score(conn, run_id)
        assert row["null_draws"] == 1
        assert row["null_expects"] == 2
        assert row["null_run_ids"] == [null_id]
    finally:
        conn.close()


def test_two_paired_nulls_are_averaged_rather_than_summed():
    conn, rec, run_id, null_id = _fixture()
    try:
        second = _run(conn, rec)
        for a, b in ((700, 800), (900, 1000), (1100, 1200), (1300, 1400)):
            run_db.insert_detection(conn, second, a, b)
        run_db.update_run(conn, second, surrogate_of_run_id=run_id)
        row = channel_score(conn, run_id)
        assert row["null_draws"] == 2
        assert row["null_expects"] == 3            # (2 + 4) / 2
        assert row["x_null"] == pytest.approx(2.0)  # 6 found / 3 expected
    finally:
        conn.close()


def test_the_totals_x_null_divides_one_scope_by_the_same_scope():
    """Dividing every channel's `found` by only the channels that carry a
    surrogate printed 4.0 under four rows that each read 2.0."""
    conn = init_db(":memory:")
    try:
        run_ids = []
        for ch in range(4):
            rec = _recording(conn, channel=ch)
            run_id = _run(conn, rec)
            for i in range(10):
                run_db.insert_detection(conn, run_id, 100 + i * 200, 180 + i * 200)
            if ch < 2:                       # only two channels get a null
                null_id = _run(conn, rec)
                for i in range(5):
                    run_db.insert_detection(conn, null_id, 150 + i * 400, 230 + i * 400)
                run_db.update_run(conn, null_id, surrogate_of_run_id=run_id)
            run_ids.append(run_id)
        rows = [channel_score(conn, r) for r in run_ids]
        assert [r["x_null"] for r in rows[:2]] == [pytest.approx(2.0)] * 2
        assert [r["x_null"] for r in rows[2:]] == [None, None]
        total = run_total(conn, run_ids, rows=rows)
        assert total["x_null"] == pytest.approx(2.0), "not 4.0 — the numerator is the same two channels"
        assert "2 of 4 channels" in total["x_null_scope"]
    finally:
        conn.close()


def test_a_detection_that_matched_an_annotation_in_coverage_is_judge_able():
    """Gating precision on the detection's onset and recall on the
    annotation's let one row print 'no detections in the reviewed overlap'
    beside a recall of 0.167 derived from exactly such a detection. One
    criterion now: the human could have judged it either way."""
    conn = init_db(":memory:")
    try:
        rec = _recording(conn)
        # the human reviewed [1000, 2000) and marked one long event inside it
        q.insert_reviewed_span(conn, rec, 1000, 2000, SOURCE, reviewed_at=BEFORE)
        q.insert_annotation(conn, rec, 1100, 1900, "interesting", SOURCE, created_at=BEFORE)
        run_id = _run(conn, rec)
        # the detection starts just before the reviewed window and matches it
        run_db.insert_detection(conn, run_id, 900, 1850)
        row = channel_score(conn, run_id)
        assert row["reviewed"] == 1, "it matched an annotation the human did judge"
        assert row["interesting"] == 1
        assert row["precision"] == pytest.approx(1.0)
        assert row["recall"] == pytest.approx(1.0)
        assert row["precision"] is not None and row["recall"] is not None
    finally:
        conn.close()
