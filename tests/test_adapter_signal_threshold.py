"""
test_adapter_signal_threshold.py
==================================
`detection.signal_threshold` — Signal → SpanSet: the sibling of
`detection.threshold` (Scores → SpanSet) that cuts the chain's current
SIGNAL at an absolute level in the signal's own units, so a baseline-removed
trace can be turned into events with no scoring stage in between.

Spans are the contiguous runs where the signal is `above` the cut (the
default), `below` it (a drop after detrending), or on `either` side of zero
by more than it. A span's score is how far past the cut it reaches, in the
signal's units, so a stronger event scores higher whichever side the cut is
on. A NaN sample never belongs to a span. No crossing is an empty SpanSet,
not an error.

Runnable standalone:  python tests/test_adapter_signal_threshold.py
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
NAME = "detection.signal_threshold"
FS = 1.0


def run(x, **params):
    spec = get_adapter(NAME)
    x = np.asarray(x, dtype=float)
    return spec.run(x, np.arange(len(x), dtype=float) / FS, FS, **spec.validate_params(params))


def spans(result):
    return list(zip(result.value.starts, result.value.ends))


def test_registered_with_the_standard_types_and_parameters():
    spec = get_adapter(NAME)
    assert spec.input_kind == "signal" and spec.output_kind == "spanset"
    assert spec.stage == "detection" and spec.category == "detect"
    assert {p.name for p in spec.params} == {"threshold", "direction", "min_duration_s", "merge_gap_s"}
    thr = next(p for p in spec.params if p.name == "threshold")
    assert thr.type is float, "the cut must be a float named `threshold` — the drawing standard's convention"
    d = spec.validate_params({})
    assert d == {"threshold": 0.0, "direction": "above", "min_duration_s": 0.0, "merge_gap_s": 0.0}, \
        "the two tidying parameters default to 0.0: off, so a recipe that names neither runs exactly as before"
    for name in ("min_duration_s", "merge_gap_s"):
        p = next(p for p in spec.params if p.name == name)
        assert p.type is float and p.default == 0.0
        with pytest.raises(ValueError, match=name):
            spec.validate_params({name: -1.0})
    direction = next(p for p in spec.params if p.name == "direction")
    assert direction.choices == ["above", "below", "either"]
    with pytest.raises(ValueError, match="direction"):
        spec.validate_params({"direction": "sideways"})


def test_spans_are_the_contiguous_runs_above_the_cut_half_open():
    x = np.zeros(30)
    x[5:9] = 1.0
    x[20] = 2.0
    r = run(x)
    assert r.output_kind == "spanset" and isinstance(r.value, SpanSet)
    assert spans(r) == [(5, 9), (20, 21)]
    assert r.value.scores == (1.0, 2.0)
    r = run(x, threshold=0.5)
    assert spans(r) == [(5, 9), (20, 21)]
    assert r.value.scores == (0.5, 1.5), "a span's score is how far past the cut it reaches"


def test_a_sample_exactly_at_the_cut_is_not_past_it():
    x = np.array([0.0, 1.0, 1.0, 0.0])
    assert spans(run(x, threshold=1.0)) == []
    assert spans(run(x, threshold=0.999)) == [(1, 3)]


def test_below_keeps_the_runs_under_a_negative_cut():
    """A drop after baseline removal: the cut is a level, so `below -0.005`
    reads as the signal falling under -5 mV of a trace stored in volts."""
    x = np.zeros(40)
    x[10:16] = -0.02
    x[30:32] = -0.004
    r = run(x, threshold=-0.005, direction="below")
    assert spans(r) == [(10, 16)]
    assert r.value.scores == pytest.approx((0.015,)), "score = threshold - min(x) in the span"
    # the default direction is `above`: the same level then keeps the baseline, not the drop
    assert spans(run(x, threshold=-0.005)) == [(0, 10), (16, 40)]   # -0.004 is above -0.005 too
    assert spans(run(x, threshold=0.0, direction="below")) == [(10, 16), (30, 32)]


def test_either_side_keeps_excursions_both_ways():
    x = np.zeros(40)
    x[3:6] = -1.0
    x[10:12] = 1.0
    x[20:22] = 0.4
    r = run(x, threshold=0.5, direction="either")
    assert spans(r) == [(3, 6), (10, 12)]
    assert r.value.scores == (0.5, 0.5), "score = max |x| - |threshold|"
    # a negative level means the same thing on `either`: the magnitude counts
    assert spans(run(x, threshold=-0.5, direction="either")) == [(3, 6), (10, 12)]


def test_a_nan_sample_never_belongs_to_a_span():
    x = np.zeros(20)
    x[5:9] = 1.0
    x[7] = np.nan
    r = run(x, threshold=0.5)
    assert spans(r) == [(5, 7), (8, 9)]
    assert r.meta["n_nan"] == 1
    x[:] = np.nan
    assert spans(run(x, threshold=-1.0, direction="either")) == []


def test_a_span_reaching_the_edges_is_still_half_open_and_in_bounds():
    x = np.ones(5)
    r = run(x, threshold=0.5)
    assert spans(r) == [(0, 5)]
    x[0] = 0.0
    assert spans(run(x, threshold=0.5)) == [(1, 5)]


def test_no_crossing_is_an_empty_spanset_not_an_error():
    r = run(np.zeros(100), threshold=1.0)
    assert r.output_kind == "spanset"
    assert spans(r) == [] and r.value.scores == ()
    assert r.meta["n_spans"] == 0


def test_meta_carries_what_the_page_needs():
    x = np.zeros(30)
    x[5:9] = 1.0
    r = run(x, threshold=0.25)
    assert r.meta["n_spans"] == 1
    assert r.meta["n_nan"] == 0
    assert r.meta["threshold"] == 0.25 and r.meta["direction"] == "above"
    assert r.meta["n_samples"] == 30


def test_agrees_with_the_scores_threshold_block_on_the_same_values():
    """The two blocks are one rule applied to two types: feeding the same
    values to `detection.threshold` as a Scores gives the same spans. Only the
    score differs — the Scores block reports the peak value, this one the
    excursion past the cut — by exactly the cut."""
    rng = np.random.default_rng(7)
    x = rng.standard_normal(500)
    thr = 1.2
    mine = run(x, threshold=thr)
    sib = get_adapter("detection.threshold")
    theirs = sib.run(x, np.arange(500.0), FS, value=Scores(values=x, fs=FS), **sib.validate_params({"threshold": thr}))
    assert spans(mine) == spans(theirs)
    assert len(spans(mine)) > 0
    assert np.allclose(np.asarray(mine.value.scores), np.asarray(theirs.value.scores) - thr)


def graze_then_drop():
    """The researcher's case (CH1_A1 336–338 h, the `signal_threshold` template):
    a one-sample graze of the cut, one sample of recovery, then the real drop."""
    x = np.zeros(60)
    x[10] = -0.006
    x[12:40] = -0.02
    x[20] = -0.03
    return x


def test_by_default_a_one_sample_graze_of_the_cut_is_a_one_second_span():
    r = run(graze_then_drop(), threshold=-0.005, direction="below")
    assert spans(r) == [(10, 11), (12, 40)]
    assert r.value.scores == pytest.approx((0.001, 0.025))
    assert r.meta["n_spans"] == 2


def test_min_duration_drops_the_graze_and_keeps_the_drop():
    r = run(graze_then_drop(), threshold=-0.005, direction="below", min_duration_s=2.0)
    assert spans(r) == [(12, 40)]
    assert r.value.scores == pytest.approx((0.025,))
    assert r.meta["n_spans"] == 1, "meta counts the spans that were kept"
    # the floor is in seconds, converted at fs: at 10 Hz two seconds is twenty samples
    spec = get_adapter(NAME)
    x = graze_then_drop()
    r10 = spec.run(x, np.arange(len(x)) / 10.0, 10.0,
                   **spec.validate_params({"threshold": -0.005, "direction": "below", "min_duration_s": 2.0}))
    assert spans(r10) == [(12, 40)]
    r10 = spec.run(x, np.arange(len(x)) / 10.0, 10.0,
                   **spec.validate_params({"threshold": -0.005, "direction": "below", "min_duration_s": 3.0}))
    assert spans(r10) == [], "thirty samples: the 28-sample drop is under the floor too"


def test_merge_gap_joins_the_graze_to_the_drop_and_scores_the_max_of_the_parts():
    r = run(graze_then_drop(), threshold=-0.005, direction="below", merge_gap_s=2.0)
    assert spans(r) == [(10, 40)]
    assert r.value.scores == pytest.approx((0.025,))
    assert r.meta["n_spans"] == 1
    # a gap exactly as wide as the setting is not 'less than' it
    assert spans(run(graze_then_drop(), threshold=-0.005, direction="below", merge_gap_s=1.0)) == [(10, 11), (12, 40)]


def test_merging_runs_before_the_floor_on_every_direction():
    """An event fragmented by one sample (a NaN, say) is one event once merged,
    and long enough to keep — whichever side of the cut it is on."""
    x = np.zeros(30)
    x[10:14] = 1.0
    x[14] = np.nan
    x[15:19] = 1.0
    r = run(x, threshold=0.5, merge_gap_s=2.0, min_duration_s=6.0)
    assert spans(r) == [(10, 19)]
    assert spans(run(x, threshold=0.5, min_duration_s=6.0)) == []
    r = run(-x, threshold=-0.5, direction="below", merge_gap_s=2.0, min_duration_s=6.0)
    assert spans(r) == [(10, 19)]
    r = run(x, threshold=0.5, direction="either", merge_gap_s=2.0, min_duration_s=6.0)
    assert spans(r) == [(10, 19)]


def test_tidying_is_the_scores_siblings_helper_and_the_blocks_still_agree():
    from Adapters import detection_signal_threshold as mine_mod
    from Adapters.detection_threshold import tidy_spans
    assert mine_mod.tidy_spans is tidy_spans
    rng = np.random.default_rng(11)
    x = rng.standard_normal(600)
    thr = 0.8
    tidy = {"min_duration_s": 2.0, "merge_gap_s": 3.0}
    mine = run(x, threshold=thr, **tidy)
    sib = get_adapter("detection.threshold")
    theirs = sib.run(x, np.arange(600.0), FS, value=Scores(values=x, fs=FS),
                     **sib.validate_params({"threshold": thr, **tidy}))
    assert spans(mine) == spans(theirs)
    assert 0 < len(spans(mine)) < len(spans(run(x, threshold=thr))), "the tidying did something on noise"
    assert np.allclose(np.asarray(mine.value.scores), np.asarray(theirs.value.scores) - thr)


def test_filed_as_a_detector_for_discovery_compare():
    """Discovery › Compare reads a block's role off its types and draws it with
    a closed set of glyphs; a threshold block is a `Detect` role drawn as
    `threshold`, like its Scores sibling."""
    from Working.discovery import compare as dc
    spec = get_adapter(NAME)
    assert dc.role_of(spec) == "Detect"
    assert dc.glyph_for(NAME) == "threshold"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
