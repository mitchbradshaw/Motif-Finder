"""
test_adapter_threshold.py
===========================
`detection.threshold` — Scores → SpanSet at an absolute cut — and the span
tidying it shares with its Signal sibling (`detection.signal_threshold`):

    min_duration_s   drop a span shorter than this (seconds, converted at fs)
    merge_gap_s      join spans separated by less than this; the merged span
                     scores the max of its parts

Both default to 0.0, which is exactly today's behaviour: every contiguous run
past the cut, however short, however close to the next — so a one-sample graze
of the cut is a one-second span at 1 Hz (seen on CH1_A1 336–338 h: span #5,
1 s at 337.824 h, right before a real drop). Merging runs first, then the
short ones are dropped, so a real event split by one sample's recovery is one
event long enough to keep. Seconds convert to samples as round(seconds * fs).

The helper is `tidy_spans`, in this block's module next to `spans_from_mask`,
imported by the sibling rather than written twice.

Runnable standalone:  python tests/test_adapter_threshold.py
"""

import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
for _p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.types import Scores, SpanSet  # noqa: E402

discover_adapters()
NAME = "detection.threshold"
FS = 1.0


def run(values, fs=FS, **params):
    spec = get_adapter(NAME)
    v = np.asarray(values, dtype=float)
    t = np.arange(len(v), dtype=float) / fs
    return spec.run(np.zeros_like(v), t, fs, value=Scores(values=v, fs=fs), **spec.validate_params(params))


def spans(result):
    return list(zip(result.value.starts, result.value.ends))


def graze_then_event():
    """A one-sample graze of the cut at 10, a one-sample gap, then a real event [12, 20)."""
    v = np.zeros(30)
    v[10] = 1.5
    v[12:20] = 3.0
    v[15] = 4.0
    return v


# ---------------------------------------------------------------------------
# the block's parameters
# ---------------------------------------------------------------------------

def test_registered_with_the_cut_and_the_two_optional_tidying_parameters():
    spec = get_adapter(NAME)
    assert spec.input_kind == "scores" and spec.output_kind == "spanset"
    assert {p.name for p in spec.params} == {"threshold", "min_duration_s", "merge_gap_s"}
    by_name = {p.name: p for p in spec.params}
    assert by_name["min_duration_s"].type is float and by_name["min_duration_s"].default == 0.0
    assert by_name["merge_gap_s"].type is float and by_name["merge_gap_s"].default == 0.0
    assert spec.validate_params({}) == {"threshold": 0.0, "min_duration_s": 0.0, "merge_gap_s": 0.0}
    # a negative duration means nothing: refused at the seam, not silently clamped
    with pytest.raises(ValueError, match="min_duration_s"):
        spec.validate_params({"min_duration_s": -1.0})
    with pytest.raises(ValueError, match="merge_gap_s"):
        spec.validate_params({"merge_gap_s": -0.5})


def test_the_defaults_keep_every_run_past_the_cut_however_short_or_close():
    """Today's behaviour, byte for byte: the graze is its own one-sample span."""
    r = run(graze_then_event(), threshold=1.0)
    assert r.output_kind == "spanset" and isinstance(r.value, SpanSet)
    assert spans(r) == [(10, 11), (12, 20)]
    assert r.value.scores == (1.5, 4.0)
    # passing the defaults explicitly is the same run
    assert spans(run(graze_then_event(), threshold=1.0, min_duration_s=0.0, merge_gap_s=0.0)) == [(10, 11), (12, 20)]


# ---------------------------------------------------------------------------
# min_duration_s
# ---------------------------------------------------------------------------

def test_min_duration_drops_spans_shorter_than_it():
    r = run(graze_then_event(), threshold=1.0, min_duration_s=2.0)
    assert spans(r) == [(12, 20)], "the one-second graze is gone, the eight-second event stays"
    assert r.value.scores == (4.0,)
    # 'shorter than': a span exactly as long as the floor is kept
    assert spans(run(graze_then_event(), threshold=1.0, min_duration_s=8.0)) == [(12, 20)]
    assert spans(run(graze_then_event(), threshold=1.0, min_duration_s=9.0)) == []


def test_durations_convert_to_samples_at_fs_by_rounding():
    """samples = round(seconds * fs): at 10 Hz a 0.3 s floor is 3 samples."""
    v = np.zeros(40)
    v[5:7] = 2.0      # 2 samples = 0.2 s
    v[20:23] = 2.0    # 3 samples = 0.3 s
    v[30:35] = 2.0    # 5 samples = 0.5 s
    assert spans(run(v, fs=10.0, threshold=1.0, min_duration_s=0.3)) == [(20, 23), (30, 35)]
    assert spans(run(v, fs=10.0, threshold=1.0, min_duration_s=0.31)) == [(20, 23), (30, 35)], "round(3.1) = 3 keeps the 3-sample span"
    assert spans(run(v, fs=10.0, threshold=1.0, min_duration_s=0.36)) == [(30, 35)], "round(3.6) = 4 drops it"
    # at 1 Hz the same floor in seconds is the same floor in samples
    assert spans(run(v, fs=1.0, threshold=1.0, min_duration_s=3.0)) == [(20, 23), (30, 35)]


# ---------------------------------------------------------------------------
# merge_gap_s
# ---------------------------------------------------------------------------

def test_merge_gap_joins_spans_closer_than_it_and_scores_the_max_of_the_parts():
    r = run(graze_then_event(), threshold=1.0, merge_gap_s=2.0)
    assert spans(r) == [(10, 20)], "the graze and the event, one sample apart, become one span"
    assert r.value.scores == (4.0,), "the merged span scores the max of its parts, not of the gap"
    # 'less than': a gap exactly as wide as the setting does not merge
    assert spans(run(graze_then_event(), threshold=1.0, merge_gap_s=1.0)) == [(10, 11), (12, 20)]


def test_merging_runs_along_a_chain_and_leaves_wider_gaps_alone():
    v = np.zeros(60)
    v[5:8] = 2.0      # gap 2
    v[10:12] = 5.0    # gap 2
    v[14:16] = 3.0    # gap 10
    v[26:30] = 2.5
    r = run(v, threshold=1.0, merge_gap_s=3.0)
    assert spans(r) == [(5, 16), (26, 30)]
    assert r.value.scores == (5.0, 2.5)


def test_merging_happens_before_the_duration_floor():
    """Two one-sample fragments of one event, one sample apart: merged first they
    are three samples long and survive a three-sample floor. Dropped first,
    neither would have been there to merge."""
    v = np.zeros(20)
    v[8] = 2.0
    v[10] = 2.0
    r = run(v, threshold=1.0, merge_gap_s=2.0, min_duration_s=3.0)
    assert spans(r) == [(8, 11)]
    assert r.value.scores == (2.0,)
    assert spans(run(v, threshold=1.0, min_duration_s=3.0)) == []


# ---------------------------------------------------------------------------
# the shared helper
# ---------------------------------------------------------------------------

def test_tidy_spans_is_one_helper_in_this_module_shared_with_the_signal_sibling():
    from Adapters import detection_signal_threshold as sibling
    from Adapters.detection_threshold import tidy_spans
    assert sibling.tidy_spans is tidy_spans, "one rule, two blocks: the sibling imports it rather than writing its own"


def test_tidy_spans_at_zero_is_the_identity():
    from Adapters.detection_threshold import tidy_spans
    starts, ends, scores = (2, 5, 9), (3, 7, 12), (1.0, 2.0, 0.5)
    out = tidy_spans(starts, ends, scores, fs=1.0)
    assert tuple(out[0]) == starts and tuple(out[1]) == ends and tuple(out[2]) == scores
    assert tidy_spans((), (), (), fs=1.0, min_duration_s=5.0, merge_gap_s=5.0) == ((), (), ())


def test_tidy_spans_merges_then_drops_and_returns_plain_ints_and_floats():
    from Adapters.detection_threshold import tidy_spans
    starts = np.array([2, 5, 20, 40])
    ends = np.array([3, 7, 21, 50])
    scores = np.array([1.0, 3.0, 9.0, 2.0])
    s, e, sc = tidy_spans(starts, ends, scores, fs=1.0, merge_gap_s=3.0, min_duration_s=4.0)
    assert (tuple(s), tuple(e), tuple(sc)) == ((2, 40), (7, 50), (3.0, 2.0))
    assert all(type(v) is int for v in (*s, *e)) and all(type(v) is float for v in sc)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
