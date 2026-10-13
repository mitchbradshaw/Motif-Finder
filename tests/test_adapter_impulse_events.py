"""
test_adapter_impulse_events.py
===============================
W1-B: `detection.impulse_events` (Scores -> SpanSet) — one span per impulse in
an impulse-like score, with an extent computed from its own inputs: from
`pre_s` before the jump to the next jump or `max_extent_s` after it, whichever
is first, clipped to the span. `meta["events"]` carries span-relative
`onset_idx` (the last sample before the jump) and `trough_idx` (the sample of
largest |x - x[onset]| from the onset to the span's end) so the slideshow
counts falls per window.

The acceptance case: 12 h at 1 Hz, 30 troughs including 8 overlapping pairs,
deconvolve -> impulse events finds every onset within 2 samples and each pair
as TWO events, while `detection.signal_threshold` on the same trace merges
every pair into one span (the reason the block exists).

Runnable standalone:  python tests/test_adapter_impulse_events.py
"""

import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.Detection.deconvolution.impulses import impulse_events  # noqa: E402
from Working.types import Scores, SpanSet  # noqa: E402
from tests._deconv_synthetic import BASELINE_V, FS, HALF_S, troughs_12h  # noqa: E402

discover_adapters()
NAME = "detection.impulse_events"


def _run(x, scores, fs=FS, **params):
    spec = get_adapter(NAME)
    t = np.arange(len(x), dtype=float) / fs
    return spec.run(x, t, fs, value=Scores(values=np.asarray(scores, float), fs=fs), **spec.validate_params(params))


def _chain(x, **deconv):
    dec = get_adapter("detection.deconvolve")
    t = np.arange(len(x), dtype=float) / FS
    sc = dec.run(x, t, FS, **dec.validate_params(deconv))
    imp = get_adapter(NAME)
    return imp.run(x, t, FS, value=sc.value, **imp.validate_params({}))


# -- the spec ---------------------------------------------------------------------

def test_spec_types_category_page_name_and_the_draggable_threshold():
    spec = get_adapter(NAME)
    assert spec.input_kind == "scores" and spec.output_kind == "spanset"
    assert spec.category == "detect" and spec.stage == "detection"
    assert spec.page_name == "Impulse events"
    thr = [p for p in spec.params if p.name == "threshold"]
    assert thr and thr[0].type is float          # BLOCK_INTEGRATION §2: draggable on the upstream curve
    assert spec.validate_params({}) == {"threshold": 4.0, "merge_within_s": 2.0, "pre_s": 10.0,
                                        "max_extent_s": 600.0}
    for bad in ({"merge_within_s": -1.0}, {"pre_s": -1.0}, {"max_extent_s": 0.0}, {"threshold": -1.0}):
        with pytest.raises(ValueError):
            spec.validate_params(bad)


def test_missing_scores_input_is_a_clear_error():
    spec = get_adapter(NAME)
    with pytest.raises(ValueError, match="Scores"):
        spec.run(np.zeros(10), np.arange(10.0), FS, **spec.validate_params({}))


def test_scores_of_another_length_are_refused():
    with pytest.raises(ValueError, match="one value per sample"):
        _run(np.zeros(100), np.zeros(90))


# -- the extent rule --------------------------------------------------------------

def test_extent_runs_from_pre_s_before_to_the_next_jump_or_the_cap():
    n = 2000
    s = np.zeros(n)
    s[[100, 400, 1500]] = [6.0, 9.0, 5.0]
    x = np.zeros(n)
    r = _run(x, s, threshold=4.0, pre_s=10.0, max_extent_s=600.0)
    ss = r.value
    assert isinstance(ss, SpanSet)
    assert list(ss.starts) == [89, 389, 1489]
    # to the next jump (onset = the last sample before it), else the cap, else the span's end
    assert list(ss.ends) == [399, 999, 2000]
    assert list(ss.scores) == pytest.approx([6.0, 9.0, 5.0])
    ev = r.meta["events"]
    assert [e["onset_idx"] for e in ev] == [99, 399, 1499]
    assert [e["impulse_idx"] for e in ev] == [100, 400, 1500]
    assert [e["right_capped"] for e in ev] == [False, True, False]
    assert r.meta["n_events"] == 3 and r.meta["n_capped"] == 1


def test_impulses_closer_than_merge_within_are_one_event_scoring_their_sum():
    n = 500
    s = np.zeros(n)
    s[[100, 101, 102, 300]] = [5.0, 1.0, 4.5, 7.0]   # 101 is below the cut but inside the group
    r = _run(np.zeros(n), s, threshold=4.0, merge_within_s=3.0, pre_s=0.0)
    assert list(r.value.starts) == [99, 299]
    assert r.value.scores[0] == pytest.approx(10.5)
    assert r.meta["events"][0]["n_impulses"] == 3


def test_start_is_clipped_to_the_span():
    s = np.zeros(100)
    s[3] = 9.0
    r = _run(np.zeros(100), s, pre_s=10.0)
    assert r.value.starts[0] == 0


def test_trough_is_the_largest_departure_from_the_onset_level():
    n = 400
    x = np.zeros(n)
    x[50:] = -1.0
    x[60] = -3.0                  # the deepest point after the jump
    x[200:] = 0.0
    s = np.zeros(n)
    s[50] = 10.0
    r = _run(x, s, max_extent_s=100.0)
    e = r.meta["events"][0]
    assert e["onset_idx"] == 49 and e["trough_idx"] == 60


def test_no_impulse_is_an_empty_spanset_that_says_so():
    r = _run(np.zeros(50), np.zeros(50))
    assert len(r.value.starts) == 0
    assert r.meta["n_events"] == 0 and r.meta["events"] == []
    assert "4" in r.meta["summary"]               # names the cut nothing reached


def test_core_function_matches_the_adapter():
    s = np.zeros(300)
    s[[20, 150]] = [5.0, 8.0]
    out = impulse_events(s, np.zeros(300), FS, threshold=4.0, merge_within_s=2.0, pre_s=5.0, max_extent_s=100.0)
    assert list(out.starts) == [14, 144] and list(out.ends) == [119, 249]


# -- the acceptance case ----------------------------------------------------------

def test_every_onset_found_and_each_overlapping_pair_is_two_events():
    x, onsets, pairs = troughs_12h(seed=0)
    r = _chain(x, recovery_half_s=HALF_S)
    found = [e["impulse_idx"] for e in r.meta["events"]]
    assert len(found) == 30, f"expected 30 events, got {len(found)}"
    for o in onsets:
        assert min(abs(o - f) for f in found) <= 2, f"onset {o} not found within 2 samples"
    for a, b in pairs:
        near_a = [f for f in found if abs(f - a) <= 2]
        near_b = [f for f in found if abs(f - b) <= 2]
        assert near_a and near_b and near_a[0] != near_b[0]


def test_the_same_with_the_recovery_estimated():
    x, onsets, _ = troughs_12h(seed=0)
    r = _chain(x, recovery_half_s=0.0)
    found = [e["impulse_idx"] for e in r.meta["events"]]
    assert len(found) == 30
    for o in onsets:
        assert min(abs(o - f) for f in found) <= 2


def test_signal_threshold_merges_the_overlapping_pairs():
    x, onsets, pairs = troughs_12h(seed=0)
    spec = get_adapter("detection.signal_threshold")
    t = np.arange(len(x), dtype=float)
    r = spec.run(x, t, FS, **spec.validate_params({"threshold": BASELINE_V - 5e-4, "direction": "below"}))
    spans = list(zip(r.value.starts, r.value.ends))
    merged = sum(1 for a, b in pairs if any(s <= a and b < e for s, e in spans))
    assert merged == 8, "a plain threshold should see each overlapping pair as one blob"


def test_scaling_the_input_leaves_the_spans_unchanged():
    x, _, _ = troughs_12h(seed=0)
    a = _chain(x, recovery_half_s=0.0)
    b = _chain(x * 1000.0, recovery_half_s=0.0)
    assert a.value.starts == b.value.starts and a.value.ends == b.value.ends
    np.testing.assert_allclose(a.value.scores, b.value.scores, rtol=1e-6)



def test_the_extent_rule_says_consecutive_spans_overlap_by_pre_s():
    """F8: the next span starts pre_s before the next onset, which is before this one's end."""
    from Adapters.detection_impulse_events import RULES
    extent = [r["rule"] for r in RULES if r["name"] == "extent"][0]
    assert "overlap" in extent and "pre_s" in extent


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
