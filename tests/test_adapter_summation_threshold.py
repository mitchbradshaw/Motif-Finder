"""
test_adapter_summation_threshold.py
=====================================
`detection.summation_threshold` — Scores → SpanSet: everything in the
Dehshibi & Adamatzky (2021) detector after Ω(τ), as the AUTHORS' code does it
(fixup-J, Q33): candidate regions between Ω's extrema, the spike /
pseudo-spike split on the signal, the envelope regions of the signal's
curvature, and the merge. The signal comes in as `x`, which every block
receives; the score may come from ANY block that emits one value per sample.

Not `detection.threshold`: that block cuts a Scores at an absolute value,
this one pairs prominence-gated extrema per window and confirms them against
the signal — different semantics, so a different block.

Runnable standalone:  python tests/test_adapter_summation_threshold.py
"""

import json
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
from Working.Detection.analysis import dehshibi_authors as A  # noqa: E402
from Working.types import Scores  # noqa: E402

discover_adapters()
NAME = "detection.summation_threshold"

with open(os.path.join(PROJECT_ROOT, "tests", "fixtures", "dehshibi", "reference.json")) as _f:
    REF = json.load(_f)


def case(name="a"):
    """A synthetic 1 Hz recording with known events and what the authors'
    MATLAB returned on it (see tests/test_dehshibi_authors.py)."""
    c = REF["cases"][name]
    x = np.asarray(c["x"], dtype=float)
    return c, x, np.arange(len(x), dtype=float)


def half_open(regions):
    """MATLAB 1-based inclusive -> SpanSet's 0-based half-open."""
    return [(int(a) - 1, int(b)) for a, b in regions]


def run(x, t, omega, fs=1.0, **params):
    spec = get_adapter(NAME)
    return spec.run(x, t, fs, value=Scores(values=np.asarray(omega, dtype=float), fs=fs), **spec.validate_params(params))


def test_registered_with_the_standard_types_and_parameters_in_seconds():
    spec = get_adapter(NAME)
    assert spec.input_kind == "scores" and spec.output_kind == "spanset"
    assert spec.category == "detect"
    names = {p.name for p in spec.params}
    assert {"epsilon_factor", "min_separation_s", "window_s", "slice_by_state"} <= names
    d = spec.validate_params({})
    assert d["epsilon_factor"] == 0.05 and d["min_separation_s"] == 60.0
    assert d["window_s"] == 3000.0 and d["slice_by_state"] is False


def test_an_old_recipes_parameters_are_still_accepted():
    """Before fixup-J the lengths were sample counts under these names; a saved
    recipe that carries them must still validate and run (Q32)."""
    c, x, t = case("a")
    r = run(x, t, c["omega"], n_p=60, min_spike_duration=60, min_roi_wavelet=30)
    assert list(zip(r.value.starts, r.value.ends)) == half_open(c["spikes"])


@pytest.mark.parametrize("name", sorted(REF["cases"]))
def test_reproduces_the_authors_spikes_from_their_omega(name):
    c, x, t = case(name)
    r = run(x, t, c["omega"], window_s=float(len(x)))
    assert r.output_kind == "spanset"
    assert list(zip(r.value.starts, r.value.ends)) == half_open(c["spikes"])
    assert r.meta["pseudo_spikes"] == [list(p) for p in half_open(c["ROI_ps"])]


def test_spans_are_labelled_spike_scored_by_depth_and_never_nested():
    c, x, t = case("c")
    r = run(x, t, c["omega"], window_s=float(len(x)))
    assert set(r.value.labels) == {"spike"}
    assert all(s >= 0 for s in r.value.scores)
    spans = list(zip(r.value.starts, r.value.ends))
    assert all(a < b for a, b in spans)
    assert all(spans[i][1] <= spans[i + 1][0] for i in range(len(spans) - 1)), "one spike per event, no staircase"


def test_the_funnel_reaches_meta_stage_by_stage():
    """What the block decided and why: every stage's regions, half-open, in span
    samples, with counts — the page draws this."""
    c, x, t = case("a")
    r = run(x, t, c["omega"])
    stages = {s["key"]: s for s in r.meta["funnel"]["stages"]}
    assert list(stages) == ["B", "C", "D", "R", "R_kept", "S"]
    assert [list(p) for p in half_open(c["ROIw"])] == stages["B"]["regions"]
    assert [list(p) for p in half_open(c["ROI_ws"])] == stages["C"]["regions"]
    assert [list(p) for p in half_open(c["ROIe"])] == stages["R"]["regions"]
    assert [list(p) for p in half_open(c["spikes"])] == stages["S"]["regions"]
    for s in stages.values():
        assert s["n"] == len(s["regions"]) and s["label"]
    assert r.meta["funnel"]["chunks"] == [[0, 3000]]
    assert r.meta["n_candidates_B"] == len(c["ROIw"]) and r.meta["n_spikes"] == len(c["spikes"])


def test_any_per_sample_score_can_stand_in_for_omega():
    """The block needs a score and the signal, nothing about how the score was
    made. A crude one — the rolling range of the signal — still yields spans,
    and they are the core's for that score."""
    _, x, t = case("b")
    w = 61
    pad = np.pad(x, w // 2, mode="edge")
    win = np.lib.stride_tricks.sliding_window_view(pad, w)
    score = win.max(axis=1) - win.min(axis=1)
    r = run(x, t, score)
    spikes, _ = A.detect_from_omega(x, score, fs=1.0)
    assert list(zip(r.value.starts, r.value.ends)) == [(a, b + 1) for a, b in spikes]
    assert len(spikes) >= 1


def test_lengths_follow_the_sample_rate():
    """60 s of separation is 600 samples at 10 Hz."""
    c, x, t = case("b")
    x10 = np.repeat(x, 10)
    om10 = np.repeat(np.asarray(c["omega"], dtype=float), 10)
    r = run(x10, np.arange(len(x10)) / 10.0, om10, fs=10.0)
    spikes, _ = A.detect_from_omega(x10, om10, fs=10.0, peak_width_s=60.0, window_s=3000.0)
    assert list(zip(r.value.starts, r.value.ends)) == [(a, b + 1) for a, b in spikes]
    assert r.meta["funnel"]["chunks"] == [[0, 30000]]


def test_refuses_a_missing_scores_input():
    spec = get_adapter(NAME)
    with pytest.raises(ValueError, match="Scores"):
        spec.run(np.zeros(50), np.arange(50.0), 1.0, **spec.validate_params({}))


def test_refuses_a_score_that_is_not_one_value_per_sample():
    with pytest.raises(ValueError, match="align"):
        run(np.zeros(50), np.arange(50.0), np.zeros(49))


def test_all_nan_scores_yield_no_spans_not_an_error():
    r = run(np.zeros(50), np.arange(50.0), np.full(50, np.nan))
    assert r.value.starts == ()
    assert r.meta["n_chunks_skipped"] == 1


# ---------------------------------------- the end convention (fixup-a item 3) --
# `SpanSet` documents its regions as `[start, end)` and `detection.threshold`
# emits exactly that; the core speaks MATLAB's inclusive pairs.

def test_the_two_detection_blocks_agree_on_the_same_events_bounds():
    """A Scores marking exactly the samples this block called a spike must be
    read back by `detection.threshold` as the very same span. Two blocks, one
    event, one pair of numbers."""
    c, x, t = case("a")
    rs = run(x, t, c["omega"])
    s0, e0 = rs.value.starts[0], rs.value.ends[0]
    mask = np.zeros(len(x)); mask[s0:e0] = 1.0
    th = get_adapter("detection.threshold")
    rt = th.run(x, t, 1.0, value=Scores(values=mask, fs=1.0), **th.validate_params({"threshold": 0.5}))
    assert (s0, e0) == (rt.value.starts[0], rt.value.ends[0])


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
