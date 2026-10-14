"""
test_detrend_nan.py
=====================
`Working.Preprocessing.detrend._rolling_mean` and the two filter modes built
on it (`rolling_mean`, `rolling_z`) when samples are missing. The rolling mean
was a plain cumulative sum, so one NaN reached every later window: one NaN at
sample 100 of 1000 blanked 930 outputs, and `rolling_z` turned all of them
into 0 (its divide fills whatever it skips with 0). Every template that starts
with a rolling-mean detrend runs through it. No recording in the database held
a NaN on 2026-10-14, so no shipped result was wrong; a recording with gaps, or
a NaN from an upstream step, would have been.

`rolling_mean_nearest` is the drop detector's own filter
(`Working.Detection.drop_motifs.detect.detrend`: scipy's uniform_filter1d,
mode "nearest"), and its running sum did the same: one NaN blanked the span
from half a window before it to the end.

Pinned here, for both filters: each value is the mean of the finite samples in
its window, NaN only where the window holds none (a missing edge sample's
"nearest" copies are missing too); a missing sample stays missing in the
detrended output and no other sample is lost, so a gap keeps its own length;
finite input gives the numbers it gave before (to 1e-12 for the rolling modes,
bit for bit for the drop detector's filter, through which drop_detection_v1
reproduces its seed events); and `rolling_mean_nearest` is still exactly the
drop detector's filter.

Runnable standalone:  python tests/test_detrend_nan.py
"""

import os
import sys
import warnings

import numpy as np
import pytest
from scipy.ndimage import uniform_filter1d

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.Detection.drop_motifs.detect import detrend as drop_detrend  # noqa: E402
from Working.Preprocessing.detrend import _rolling_mean, make_detrend_filter  # noqa: E402

ROLLING_MODES = ["rolling_mean", "rolling_z"]
MISSING = pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf], ids=["nan", "+inf", "-inf"])


def _series(n, seed=0):
    """Noise on a slow drift, a recording's shape at 1 Hz."""
    t = np.arange(n, dtype=float)
    noise = np.random.default_rng(seed).normal(scale=0.1, size=n)
    return 0.5 * np.sin(2 * np.pi * t / 700.0) + 0.002 * t + noise


def _random_walk(n, seed=1):
    """A random series whose running sum grows large: the hardest case for 'the same numbers as before'."""
    return np.random.default_rng(seed).normal(size=n).cumsum()


def _todays_rolling_mean(w, window_samples):
    """The rolling mean as it stood before it was NaN-aware (2026-10-14), verbatim: finite input must not move from it."""
    n = len(w)
    half = max(1, window_samples // 2)
    csum = np.concatenate([[0.0], np.cumsum(w, dtype=np.float64)])
    idx = np.arange(n)
    lo = np.clip(idx - half, 0, n)
    hi = np.clip(idx + half + 1, 0, n)
    return (csum[hi] - csum[lo]) / (hi - lo)


def _todays_filter(w, window_samples, mode):
    """make_detrend_filter's rolling modes as they stood before, built on the rolling mean above."""
    trend = _todays_rolling_mean(w, window_samples)
    out = w - trend
    if mode == "rolling_z":
        std = np.sqrt(np.maximum(_todays_rolling_mean((w - trend) ** 2, window_samples), 0.0))
        out = np.divide(out, std, out=np.zeros_like(out), where=std > 1e-12)
    return out


def _window_mean_by_definition(w, window_samples):
    """One window at a time: the mean of the finite samples in [i - half, i + half], NaN when there are none."""
    n = len(w)
    half = max(1, window_samples // 2)
    out = np.full(n, np.nan)
    for i in range(n):
        seg = w[max(0, i - half):min(n, i + half + 1)]
        seg = seg[np.isfinite(seg)]
        if len(seg):
            out[i] = seg.mean()
    return out


def _detrended_by_definition(w, window_samples, mode):
    """The filter by definition: a missing sample stays what it was; rolling_z's flat windows give 0, as before."""
    out = w - _window_mean_by_definition(w, window_samples)
    if mode == "rolling_z":
        std = np.sqrt(_window_mean_by_definition(out ** 2, window_samples))
        z = np.zeros_like(out)
        ok = np.isfinite(std) & (std > 1e-12)
        z[ok] = out[ok] / std[ok]
        out = np.where(np.isfinite(out), z, out)
    return out


# ── finite input: the numbers it gave before ─────────────────────────────────

@pytest.mark.parametrize("window", [1, 2, 3, 60, 61, 20000])
def test_finite_input_gives_the_rolling_mean_it_gave_before(window):
    w = _random_walk(5000)
    np.testing.assert_allclose(_rolling_mean(w, window), _todays_rolling_mean(w, window), rtol=0, atol=1e-12)


@pytest.mark.parametrize("mode", ROLLING_MODES)
def test_finite_input_gives_the_detrended_output_it_gave_before(mode):
    fs, window_s = 2.0, 30.0
    w = _random_walk(4000)
    w[1000:1300] = w[1000]                       # a flat stretch: rolling_z's 0 branch
    got = make_detrend_filter(fs, mode=mode, window_s=window_s)(w)
    np.testing.assert_allclose(got, _todays_filter(w, int(round(window_s * fs)), mode), rtol=0, atol=1e-12)


# ── a missing sample stays missing, and nothing else is lost ─────────────────

@MISSING
def test_one_missing_sample_no_longer_blanks_the_rest_of_the_rolling_mean(bad):
    w = _series(1000)
    w[100] = bad
    got = _rolling_mean(w, 60)
    assert np.isfinite(got).all(), f"{int((~np.isfinite(got)).sum())} of 1000 outputs not finite"
    np.testing.assert_allclose(got, _window_mean_by_definition(w, 60), rtol=0, atol=1e-9)


@MISSING
@pytest.mark.parametrize("mode", ROLLING_MODES)
def test_one_missing_sample_is_missing_in_the_detrended_output_and_nowhere_else(mode, bad):
    w = _series(1000)
    w[100] = bad
    out = make_detrend_filter(1.0, mode=mode, window_s=60.0)(w)
    assert np.flatnonzero(~np.isfinite(out)).tolist() == [100]
    assert np.array_equal(out[100], w[100], equal_nan=True)
    np.testing.assert_allclose(out, _detrended_by_definition(w, 60, mode), rtol=0, atol=1e-9)


def test_the_rolling_mean_is_nan_only_where_its_window_holds_no_finite_sample():
    w = _series(3000)
    w[1000:1500] = np.nan                        # 500 missing samples, a 61-sample window (half 30)
    got = _rolling_mean(w, 61)
    expected = np.zeros(3000, dtype=bool)
    expected[1030:1470] = True                   # windows reaching neither side of the gap
    assert np.array_equal(np.isnan(got), expected)
    np.testing.assert_allclose(got, _window_mean_by_definition(w, 61), rtol=0, atol=1e-9)


@pytest.mark.parametrize("mode", ROLLING_MODES)
def test_a_gap_keeps_its_own_length_through_the_detrend(mode):
    w = _series(3000)
    w[1000:1500] = np.nan
    w[2990:] = np.nan                            # and one at the span's end
    out = make_detrend_filter(1.0, mode=mode, window_s=61.0)(w)
    assert np.array_equal(np.isnan(out), np.isnan(w))
    np.testing.assert_allclose(out, _detrended_by_definition(w, 61, mode), rtol=0, atol=1e-9)


def test_a_gap_in_a_flat_stretch_stays_missing_under_rolling_z():
    w = np.ones(400)
    w[150:170] = np.nan
    out = make_detrend_filter(1.0, mode="rolling_z", window_s=21.0)(w)
    assert np.array_equal(np.isnan(out), np.isnan(w))
    assert (out[np.isfinite(w)] == 0.0).all()   # flat windows score 0, as before


def test_an_all_nan_span_is_all_nan_and_warns_nothing():
    w = np.full(50, np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert np.isnan(_rolling_mean(w, 11)).all()
        for mode in [*ROLLING_MODES, "rolling_mean_nearest"]:
            assert np.isnan(make_detrend_filter(1.0, mode=mode, window_s=11.0)(w)).all(), mode
        assert np.isnan(drop_detrend(w, 500)).all()     # a window longer than the span: the whole-span mean


# ── rolling_mean_nearest: the drop detector's filter, NaN-aware too ──────────

def _todays_drop_detrend(x, window_samples):
    """The drop detector's filter as it stood before it was NaN-aware (2026-10-14), verbatim: finite input must
    not move from it by a single bit (drop_detection_v1 reproduces its seed events through it)."""
    x = np.asarray(x, dtype=float).ravel()
    window = max(3, int(round(window_samples)))
    if window >= len(x):
        return x - float(x.mean())
    return x - uniform_filter1d(x, size=window, mode="nearest")


def _nearest_by_definition(x, window_samples):
    """One window at a time: the `window` samples from i - window // 2 (scipy's alignment), the span's edge
    samples repeated beyond its ends (mode "nearest"), the mean of the finite ones subtracted; a window at or
    beyond the span's length subtracts the mean of every finite sample. NaN where no sample is finite."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    window = max(3, int(round(window_samples)))
    if window >= n:
        fin = x[np.isfinite(x)]
        return x - (fin.mean() if len(fin) else np.nan)
    trend = np.full(n, np.nan)
    for i in range(n):
        seg = x[np.clip(np.arange(i - window // 2, i - window // 2 + window), 0, n - 1)]
        seg = seg[np.isfinite(seg)]
        if len(seg):
            trend[i] = seg.mean()
    return x - trend


#: the filter's two entry points, both at 1 Hz so `k` is the window in samples
NEAREST = pytest.mark.parametrize("entry", [
    lambda x, k: drop_detrend(x, k),
    lambda x, k: make_detrend_filter(1.0, mode="rolling_mean_nearest", window_s=float(k))(x),
], ids=["detect.detrend", "rolling_mean_nearest"])


@pytest.mark.parametrize("window", [1, 3, 4, 60, 60.4, 61, 1999, 2000, 20000])
def test_finite_input_gives_the_drop_detectors_filter_it_gave_before_bit_for_bit(window):
    x = _random_walk(2000)
    got = drop_detrend(x, window)
    assert np.array_equal(got, _todays_drop_detrend(x, window))
    np.testing.assert_allclose(got, _nearest_by_definition(x, window), rtol=0, atol=1e-9)  # the definition below


@MISSING
@NEAREST
def test_one_missing_sample_is_missing_in_the_drop_detectors_filter_and_nowhere_else(entry, bad):
    x = _series(1000)
    x[100] = bad
    out = entry(x, 60)
    assert np.flatnonzero(~np.isfinite(out)).tolist() == [100], f"{int((~np.isfinite(out)).sum())} not finite"
    assert np.array_equal(out[100], x[100], equal_nan=True)
    np.testing.assert_allclose(out, _nearest_by_definition(x, 60), rtol=0, atol=1e-9)


@NEAREST
@pytest.mark.parametrize("window", [60, 61])
def test_a_gap_keeps_its_own_length_through_the_drop_detectors_filter(window, entry):
    x = _series(3000)
    x[:3] = np.nan                               # a missing first sample: its "nearest" copies are missing too
    x[1000:1500] = np.nan
    x[2990:] = np.nan
    out = entry(x, window)
    assert np.array_equal(np.isnan(out), np.isnan(x))
    np.testing.assert_allclose(out, _nearest_by_definition(x, window), rtol=0, atol=1e-9)


@pytest.mark.parametrize("window", [50, 500])
def test_a_window_as_long_as_the_span_subtracts_the_mean_of_the_finite_samples(window):
    x = _series(50)
    x[10] = np.nan
    out = drop_detrend(x, window)
    assert np.flatnonzero(np.isnan(out)).tolist() == [10]
    np.testing.assert_allclose(out, x - np.nanmean(x), rtol=0, atol=1e-12)


@pytest.mark.parametrize("with_nan", [False, True], ids=["finite", "one-nan"])
def test_rolling_mean_nearest_is_still_exactly_the_drop_detectors_filter(with_nan):
    fs, window_s = 10.0, 12.0
    w = _series(2000)
    if with_nan:
        w[500] = np.nan
    got = make_detrend_filter(fs, mode="rolling_mean_nearest", window_s=window_s)(w)
    assert np.array_equal(got, drop_detrend(w, int(round(window_s * fs))), equal_nan=True)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
