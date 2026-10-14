"""
test_background_null.py
=========================
`Working.background_null.sample_background` (w3-b): windows of a trace's own
background, cut where nothing was detected. Generic — W3-G reuses it for the
Library's quiet-stretch null — so its contract is pinned here:

* windows never touch an avoided range or a NaN sample while a free stretch
  can hold them;
* lengths are drawn from the wanted lengths; count and seed are honoured,
  the same seed gives the same windows;
* a window that fits in no free stretch is cut anywhere and counted
  (`n_fallback`, `fell_back`); one longer than the trace is not cut;
* the report says how much background there was, in samples and seconds.
"""

import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from Working.background_null import BackgroundSample, sample_background  # noqa: E402


def test_windows_avoid_the_ranges_and_the_gaps():
    x = np.arange(10_000, dtype=float)
    x[7000:7100] = np.nan
    avoid = [(1000, 3000), (5000, 5200)]
    out = sample_background(x, avoid, [300, 500], 200, seed=1)
    assert isinstance(out, BackgroundSample)
    assert out.report["n_cut"] == 200 and out.report["n_fallback"] == 0 and not out.report["fell_back"]
    for s, L, w in zip(out.starts, out.lengths, out.windows):
        assert L in (300, 500)
        assert w.size == L and np.array_equal(w, x[s:s + L])
        for a, b in avoid + [(7000, 7100)]:
            assert s + L <= a or s >= b, (s, L, a, b)
    # the free samples: 10,000 minus 2,000 + 200 avoided minus 100 NaN
    assert out.report["background_samples"] == 10_000 - 2_200 - 100


def test_lengths_are_drawn_from_the_wanted_ones_and_cover_the_free_stretches():
    x = np.zeros(20_000)
    out = sample_background(x, [(0, 5000)], [100, 200, 400], 3000, seed=2)
    assert set(out.lengths.tolist()) == {100, 200, 400}
    assert out.starts.min() >= 5000
    # starts spread over the whole free stretch, not piled at one end
    assert out.starts.max() > 18_000 and np.median(out.starts) == pytest.approx(12_400, rel=0.1)


def test_the_same_seed_gives_the_same_windows_and_another_seed_does_not():
    x = np.random.default_rng(0).standard_normal(5000)
    a = sample_background(x, [(100, 200)], [50, 80], 30, seed=7)
    b = sample_background(x, [(100, 200)], [50, 80], 30, seed=7)
    c = sample_background(x, [(100, 200)], [50, 80], 30, seed=8)
    assert np.array_equal(a.starts, b.starts) and np.array_equal(a.lengths, b.lengths)
    assert not np.array_equal(a.starts, c.starts)


def test_a_window_too_long_for_any_free_stretch_falls_back_and_is_counted():
    x = np.zeros(3000)
    avoid = [(s, s + 10) for s in range(0, 3000, 400)]       # free stretches of 390 samples
    out = sample_background(x, avoid, [1000], 5, seed=0, fs=2.0)
    assert out.report["n_cut"] == 5
    assert out.report["n_fallback"] == 5 and out.report["fell_back"]
    assert out.report["background_samples"] == 3000 - 80
    assert out.report["background_s"] == pytest.approx((3000 - 80) / 2.0)


def test_a_window_longer_than_the_trace_is_not_cut_and_is_counted():
    out = sample_background(np.zeros(100), [], [50, 500], 40, seed=3)
    assert out.report["n_too_long"] + out.report["n_cut"] == 40
    assert out.report["n_too_long"] > 0 and (out.lengths == 50).all()


def test_bad_lengths_are_refused_loudly():
    with pytest.raises(ValueError, match="positive"):
        sample_background(np.zeros(10), [], [0], 1, seed=0)
    with pytest.raises(ValueError, match="at least one"):
        sample_background(np.zeros(10), [], [], 1, seed=0)


def test_the_report_names_its_rule_and_the_trace():
    out = sample_background(np.zeros(1000), [(0, 10)], [10], 3, seed=0)
    assert out.report["trace_samples"] == 1000 and out.report["n_wanted"] == 3
    assert "fallback" in out.report["rule"] and out.report["background_s"] is None


def test_the_report_names_the_longest_free_stretch():
    """w3-b fix round 1 (compatible extension): fragmented background versus too little."""
    x = np.zeros(10_000)
    avoid = [(s, s + 10) for s in range(0, 10_000, 500)]          # free stretches of 490 samples
    out = sample_background(x, avoid, [1000], 3, seed=0, fs=2.0)
    assert out.report["longest_free_samples"] == 490 and out.report["longest_free_s"] == pytest.approx(245.0)
    assert out.report["background_samples"] == 10_000 - 200          # plenty of background, all in pieces
    assert out.report["n_fallback"] == 3
    # the earlier keys are all still there
    for k in ("n_wanted", "n_cut", "n_fallback", "fell_back", "n_too_long", "background_samples", "background_s",
              "trace_samples", "rule"):
        assert k in out.report
    assert sample_background(np.zeros(100), [], [10], 1, seed=0).report["longest_free_s"] is None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
