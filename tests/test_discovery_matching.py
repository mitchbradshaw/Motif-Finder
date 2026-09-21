"""
test_discovery_matching.py
===========================
Spec §4.6 — the matching rule.

    "Reciprocal overlap **IoU >= 0.5** with onset agreement scaled to the
    candidate's own duration — not an absolute tolerance, since durations
    here run from seconds to hours. The rule is recorded on the run, because
    the precision figure is a function of it and an unstated matching rule
    makes the metric unfalsifiable."

Two halves, and the second is the one that is easy to lose: an IoU test
alone accepts a pair whose onsets are far apart relative to the candidate's
length. `Working.discovery.matching` implements both halves, records its own
name, and reads its defaults from Settings > Analysis defaults (§9.5, keys
`iou` and `onset` on the `analysis-defaults` page) rather than hard-coding
them in the scoreboard.

Headless: pure functions over (start, end) sample pairs, plus one in-memory
database for the settings read.
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

from Working.database.schema import init_db
from Working.discovery.matching import (
    DEFAULT_IOU,
    DEFAULT_ONSET_FRACTION,
    MATCHING_RULE,
    match_quality,
    match_span_sets,
    rule_from_settings,
    spans_match,
)
from Working.registration.settings import put_settings


# ── the rule names itself ────────────────────────────────────────────────────

def test_the_rule_has_a_name_and_the_spec_defaults():
    assert MATCHING_RULE == "reciprocal_iou_onset"
    assert DEFAULT_IOU == 0.5
    assert DEFAULT_ONSET_FRACTION == 0.25


# ── half one: reciprocal overlap ─────────────────────────────────────────────

def test_identical_spans_match_with_iou_one():
    q = match_quality((1000, 1100), (1000, 1100))
    assert q["iou"] == pytest.approx(1.0)
    assert q["onset_gap"] == 0
    assert q["ok"] is True


def test_iou_below_the_threshold_is_refused_even_with_the_same_onset():
    # candidate [0, 100), reference [0, 300): intersection 100, union 300 -> 1/3
    q = match_quality((0, 100), (0, 300))
    assert q["iou"] == pytest.approx(1 / 3)
    assert q["onset_gap"] == 0
    assert q["ok"] is False
    assert not spans_match((0, 100), (0, 300))


def test_disjoint_spans_do_not_match():
    assert match_quality((0, 100), (500, 600))["iou"] == 0.0
    assert not spans_match((0, 100), (500, 600))


# ── half two: onset agreement, scaled to the candidate's own duration ────────

def test_onset_agreement_is_scaled_to_the_candidates_duration_not_absolute():
    """The pair that separates §4.6 from a bare IoU test.

    Candidate [0, 100) is 100 samples long, so the onset tolerance is
    0.25 x 100 = 25 samples.

    * reference [25, 125): intersection 75, union 125 -> IoU 0.60, onset gap
      25 == the tolerance -> matches (the boundary is inclusive).
    * reference [26, 126): intersection 74, union 126 -> IoU 0.587, still
      over 0.5 -> a bare IoU test would accept it; the onset gap 26 exceeds
      the tolerance, so the rule refuses it.
    """
    ok = match_quality((0, 100), (25, 125))
    assert ok["iou"] > DEFAULT_IOU
    assert ok["onset_gap"] == 25
    assert ok["onset_tolerance"] == pytest.approx(25.0)
    assert ok["ok"] is True

    refused = match_quality((0, 100), (26, 126))
    assert refused["iou"] > DEFAULT_IOU, "the bare IoU half passes — that is the point"
    assert refused["onset_gap"] == 26
    assert refused["ok"] is False
    assert "onset" in refused["reason"]


def test_the_tolerance_grows_with_the_candidate_duration():
    """A one-hour candidate tolerates a far larger onset gap than a
    ten-second one — which is why the rule is a fraction, not a constant."""
    long_c = match_quality((0, 4000), (900, 4900))
    assert long_c["onset_tolerance"] == pytest.approx(1000.0)
    assert long_c["ok"] is True

    short_c = match_quality((0, 40), (9, 49))
    assert short_c["onset_tolerance"] == pytest.approx(10.0)
    assert short_c["ok"] is True

    # a 6-sample gap against a 20-sample candidate clears the IoU half and
    # still fails the onset half: the tolerance has shrunk to 5 samples
    shorter = match_quality((0, 20), (6, 26))
    assert shorter["iou"] > DEFAULT_IOU
    assert shorter["onset_tolerance"] == pytest.approx(5.0)
    assert shorter["ok"] is False
    assert "onset" in shorter["reason"]


def test_the_tolerance_is_the_candidates_duration_not_the_references():
    """The candidate is the first argument and owns the scale: swapping the
    pair can change the verdict, and the caller must pass (machine, human)."""
    assert match_quality((0, 1000), (200, 1200))["ok"] is True      # tol 250, gap 200
    assert match_quality((200, 1200), (0, 1000))["ok"] is True      # tol 250, gap 200
    # asymmetric case: a short candidate against a long reference
    assert match_quality((0, 100), (20, 220))["ok"] is False        # tol 25, IoU 80/220


def test_thresholds_are_overridable_per_call():
    assert spans_match((0, 100), (26, 126), onset_fraction=0.3) is True
    assert spans_match((0, 100), (25, 125), iou_threshold=0.9) is False


# ── set matching: one-to-one, best first, deterministic ──────────────────────

def test_match_span_sets_pairs_each_reference_at_most_once_best_iou_first():
    candidates = [(0, 100), (10, 110)]
    references = [(5, 105)]
    out = match_span_sets(candidates, references)
    # both candidates overlap the one reference; the better IoU wins it
    assert [(p["candidate"], p["reference"]) for p in out["pairs"]] == [(0, 0)]
    assert out["candidate_only"] == [1]
    assert out["reference_only"] == []


def test_match_span_sets_reports_both_exclusive_remainders():
    out = match_span_sets([(0, 100), (2000, 2100)], [(0, 100), (5000, 5100)])
    assert [(p["candidate"], p["reference"]) for p in out["pairs"]] == [(0, 0)]
    assert out["candidate_only"] == [1]
    assert out["reference_only"] == [1]


def test_match_span_sets_is_deterministic_under_input_order():
    a = match_span_sets([(0, 100), (10, 110), (20, 120)], [(5, 105), (18, 118)])
    b = match_span_sets([(0, 100), (10, 110), (20, 120)], [(5, 105), (18, 118)])
    assert a == b


def test_match_span_sets_records_the_rule_it_used():
    out = match_span_sets([(0, 100)], [(0, 100)], iou_threshold=0.7, onset_fraction=0.1)
    assert out["rule"] == {"criterion": MATCHING_RULE, "iou": 0.7, "onset": 0.1}


def test_match_span_sets_on_empty_input_is_empty_not_an_error():
    out = match_span_sets([], [])
    assert out["pairs"] == [] and out["candidate_only"] == [] and out["reference_only"] == []


# ── the default lives in one place: Settings > Analysis defaults ─────────────

def test_rule_from_settings_falls_back_to_the_spec_defaults():
    conn = init_db(":memory:")
    try:
        assert rule_from_settings(conn) == {"criterion": MATCHING_RULE, "iou": 0.5, "onset": 0.25}
    finally:
        conn.close()


def test_rule_from_settings_reads_the_saved_values():
    conn = init_db(":memory:")
    try:
        put_settings(conn, "analysis-defaults", {"iou": 0.7, "onset": 0.1})
        assert rule_from_settings(conn) == {"criterion": MATCHING_RULE, "iou": 0.7, "onset": 0.1}
    finally:
        conn.close()


def test_rule_from_settings_refuses_a_nonsense_saved_value_loudly():
    conn = init_db(":memory:")
    try:
        put_settings(conn, "analysis-defaults", {"iou": 3.0})
        with pytest.raises(ValueError, match="iou"):
            rule_from_settings(conn)
    finally:
        conn.close()
