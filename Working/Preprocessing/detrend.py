"""
detrend.py
===========
Plain numpy/scipy detrending — headless, no Panel/HoloViews/Bokeh imports
(the standing rule for everything under `Working/`).

Added (2026-08) because Stage 3's benchmark found preprocessing dominated
every matcher choice for the SAX encoding view (recall 0.22 raw vs 0.85
detrended) — reachable from the UI's Run algorithm tab via
`Adapters/preprocessing_detrend.py`, which wraps `make_detrend_filter`
exactly like `Working.Detection.analysis.freq_analysis.make_bandpass_filter`
wraps its own scipy call.
"""

import numpy as np


def _finite_window_mean(v, lo, hi):
    """The mean of the finite samples of each window `v[lo[i]:hi[i]]`, from
    cumulative sums of the finite values and of their count, so a NaN or inf
    reaches no window but its own; NaN where a window holds no finite sample.
    Shared by `_rolling_mean` and the drop detector's filter
    (`Working.Detection.drop_motifs.detect.detrend`)."""
    finite = np.isfinite(v)
    csum = np.concatenate([[0.0], np.cumsum(np.where(finite, v, 0.0), dtype=np.float64)])
    cfinite = np.concatenate([[0], np.cumsum(finite, dtype=np.int64)])
    n_finite = cfinite[hi] - cfinite[lo]
    out = np.full(len(lo), np.nan)
    np.divide(csum[hi] - csum[lo], n_finite, out=out, where=n_finite > 0)
    return out


def _rolling_mean(w, window_samples):
    """Centred rolling mean via a cumulative-sum trick — O(n), edges use
    whatever window actually fits (no NaN padding, no shrinking the
    output length).

    Each value is the mean of the finite samples in its window, so a gap is
    treated like the span's ends, and the output is NaN only where a window
    holds no finite sample. A plain cumulative sum carried one NaN into every
    later window (one NaN at sample 100 of 1000 blanked 930 outputs,
    2026-10-14). Finite input gives the same numbers as before
    (tests/test_detrend_nan.py)."""
    w = np.asarray(w, dtype=np.float64)
    n = len(w)
    half = max(1, window_samples // 2)
    idx = np.arange(n)
    lo = np.clip(idx - half, 0, n)
    hi = np.clip(idx + half + 1, 0, n)
    return _finite_window_mean(w, lo, hi)


def make_detrend_filter(fs, mode="rolling_mean", window_s=600.0):
    """
    Factory: returns fn(w) that removes a slow trend from a window.

    Parameters
    ----------
    fs        : float  Sampling frequency (Hz) — converts `window_s` to samples.
    mode      : str    "rolling_mean" (subtract a centred rolling mean),
                        "rolling_z" (rolling_mean subtracted, then divided
                        by a matching centred rolling std), or "linear"
                        (subtract a single least-squares line over the
                        whole span — ignores `window_s`).
    window_s  : float  Rolling-window width in seconds (ignored for "linear").

    Missing samples: in the three rolling modes a NaN (or inf) sample stays as
    it is and the samples beside it are detrended against the finite samples
    in their window, so a gap keeps its own length. "linear" raises on NaN
    (np.polyfit).
    """
    if mode not in ("rolling_mean", "rolling_mean_nearest", "rolling_z", "linear"):
        raise ValueError(f"Unknown detrend mode {mode!r} — must be 'rolling_mean', 'rolling_mean_nearest', 'rolling_z', or 'linear'")

    def _detrend(w):
        w = np.asarray(w, dtype=np.float64)
        if mode == "linear":
            idx = np.arange(len(w))
            coeffs = np.polyfit(idx, w, 1)
            return w - np.polyval(coeffs, idx)

        window_samples = max(1, int(round(window_s * fs)))
        if mode == "rolling_mean_nearest":
            # The drop detector's own filter (uniform_filter1d, mode="nearest",
            # window >= 3, mean subtraction when the window covers the span):
            # numerically different at the edges from the cumulative-sum
            # rolling mean above, and the drop_detection_v1 template must
            # reproduce the seed events exactly, so it is imported rather than
            # re-implemented (one filter, two entry points; NaN-aware the same
            # way, finite input untouched).
            from Working.Detection.drop_motifs.detect import detrend as _drop_detrend
            return _drop_detrend(w, window_samples)
        trend = _rolling_mean(w, window_samples)
        out = w - trend
        if mode == "rolling_z":
            rolling_var = _rolling_mean((w - trend) ** 2, window_samples)
            rolling_std = np.sqrt(np.maximum(rolling_var, 0.0))
            z = np.divide(out, rolling_std, out=np.zeros_like(out), where=rolling_std > 1e-12)
            # The divide leaves 0 wherever it does not divide (a flat window, as
            # before, but also a gap): a missing sample stays missing, not 0.
            out = np.where(np.isfinite(out), z, out)
        return out

    return _detrend
