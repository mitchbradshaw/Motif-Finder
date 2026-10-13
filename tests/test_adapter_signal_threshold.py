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
    assert {p.name for p in spec.params} == {"threshold", "direction"}
    thr = next(p for p in spec.params if p.name == "threshold")
    assert thr.type is float, "the cut must be a float named `threshold` — the drawing standard's convention"
    d = spec.validate_params({})
    assert d == {"threshold": 0.0, "direction": "above"}
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
    assert spans(run(x, threshold=-0.005)) == [(0, 10), (16, 30), (32, 40)]
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
