"""
excerpt.py
==========
Is one channel a block-mean-decimated excerpt of another?

The case this exists for (user decision 2026-09-21):
``Mushroom_260720_0509_4hrs_CH14_fs1`` (recordings row 385, 14,401 samples at
1 Hz) is a four-hour 10:1 excerpt of ``L_LM_Jul_26_J_raw_fs10`` CH2 at sample
15,777,590 — ``Pipelines/drop_motifs/lionsmane12.py`` measured r = 0.9995 with a
peak one sample wide (neighbours 0.979 / 0.971). A candidate that is such a
subset of a registered recording is an excerpt, not a new recording.

``find_excerpt(short, long, decimation)`` block-means ``long`` ``decimation``:1
and locates ``short`` inside it under a normalised cross-correlation, coarse
to fine: both sides are block-meaned a further ``COARSE``:1 for the FFT
search (a 23 M-sample channel becomes 1.4 M points), then the exact r is
computed at full rate at every lag within one coarse block of the coarse
peak, and the best of those is the answer, with its two neighbouring lags for
the sharpness test. Pure numpy/scipy; nothing else.
"""
from __future__ import annotations

import numpy as np

R_THRESHOLD = 0.99        # the correlation an excerpt must reach
SHARP_MARGIN = 0.001      # peak must beat both neighbours by at least this ...
SHARP_RELATIVE = 10.0     # ... and by 10x its own distance from 1 (a slow random walk is 0.999 one block away; a real excerpt is 0.9995 vs 0.979)
MIN_LEN = 8
COARSE = 16               # extra block-mean factor for the FFT search; the fine pass verifies at full rate


def block_mean(x, decimation: int):
    d = int(decimation)
    x = np.asarray(x, dtype=np.float64)
    if d <= 1:
        return x
    usable = (len(x) // d) * d
    return x[:usable].reshape(-1, d).mean(axis=1)


def _empty(d):
    return {"r": 0.0, "offset": None, "sharp": False, "decimation": d, "neighbours": [], "n_lags": 0}


def _xcorr_all(x, y):
    """Normalised cross-correlation of z-normed ``x`` against every window of ``y`` (FFT)."""
    from scipy.signal import fftconvolve
    m = len(x)
    y = y - y.mean()
    csum = np.concatenate([[0.0], np.cumsum(y)])
    csq = np.concatenate([[0.0], np.cumsum(y * y)])
    n_lags = len(y) - m + 1
    win_mean = (csum[m:m + n_lags] - csum[:n_lags]) / m
    win_var = np.maximum((csq[m:m + n_lags] - csq[:n_lags]) / m - win_mean ** 2, 0.0)
    num = fftconvolve(y, x[::-1], mode="valid")
    with np.errstate(divide="ignore", invalid="ignore"):
        r = num / (m * np.sqrt(win_var))
    r[~np.isfinite(r)] = 0.0
    return r


def _r_at(x, y, lag):
    """Exact r of z-normed ``x`` against ``y[lag:lag+m]``."""
    m = len(x)
    if lag < 0 or lag + m > len(y):
        return 0.0
    w = y[lag:lag + m]
    sd = w.std()
    if not np.isfinite(sd) or sd == 0:
        return 0.0
    return float(np.dot(x, (w - w.mean()) / sd) / m)


def find_excerpt(short, long, decimation: int = 1) -> dict:
    """Locate ``short`` inside ``block_mean(long, decimation)``.

    Returns ``{"r", "offset", "sharp", "decimation", "neighbours", "n_lags"}``:
    ``offset`` is in ``long``'s own samples (lag × decimation); ``sharp`` is
    True when the peak beats both neighbours by max(SHARP_MARGIN,
    SHARP_RELATIVE × (1 − r)). A pair that cannot be compared returns r = 0.
    """
    d = int(decimation) if decimation else 1
    x = np.asarray(short, dtype=np.float64)
    y = block_mean(long, d)
    m = len(x)
    if m < MIN_LEN or m > len(y):
        return _empty(d)
    x = x - x.mean()
    sx = x.std()
    if not np.isfinite(sx) or sx == 0:
        return _empty(d)
    x = x / sx
    n_lags = len(y) - m + 1
    kc = min(COARSE, max(1, m // 64))
    if kc > 1 and m // kc >= MIN_LEN:
        # coarse: both sides block-meaned kc:1, one FFT search; fine: exact r at every lag within a coarse block
        xc = block_mean(x, kc); xc = (xc - xc.mean()); sxc = xc.std()
        if not np.isfinite(sxc) or sxc == 0:
            return _empty(d)
        rc = _xcorr_all(xc / sxc, block_mean(y, kc))
        if not len(rc):
            return _empty(d)
        lc = int(np.argmax(rc))
        lo, hi = max(0, lc * kc - kc), min(n_lags - 1, lc * kc + 2 * kc)
        lags = np.arange(lo, hi + 1)
        rs = np.array([_r_at(x, y, int(l)) for l in lags])
        j = int(np.argmax(rs))
        i = int(lags[j])
        peak = float(rs[j])
        neighbours = [_r_at(x, y, i - 1) if i - 1 >= 0 else None, _r_at(x, y, i + 1) if i + 1 < n_lags else None]
        neighbours = [float(v) for v in neighbours if v is not None]
    else:
        r = _xcorr_all(x, y)
        if not len(r):
            return _empty(d)
        i = int(np.argmax(r))
        peak = float(r[i])
        neighbours = [float(r[j]) for j in (i - 1, i + 1) if 0 <= j < len(r)]
    need = max(SHARP_MARGIN, SHARP_RELATIVE * (1.0 - peak))
    sharp = bool(all(peak - nb >= need for nb in neighbours)) if neighbours else True
    return {"r": peak, "offset": i * d, "sharp": sharp, "decimation": d, "neighbours": neighbours, "n_lags": int(n_lags)}


def is_excerpt(hit: dict) -> bool:
    return bool(hit and hit.get("offset") is not None and hit["r"] > R_THRESHOLD and hit["sharp"])
