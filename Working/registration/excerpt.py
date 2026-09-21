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
and slides ``short`` along it under a normalised cross-correlation (FFT), and
reports the best lag, its r, and whether the peak is single-sample sharp.
Pure numpy/scipy; nothing else.
"""
from __future__ import annotations

import numpy as np

R_THRESHOLD = 0.99        # the correlation an excerpt must reach
SHARP_MARGIN = 0.001      # peak must beat both neighbours by at least this ...
SHARP_RELATIVE = 10.0     # ... and by 10x its own distance from 1 (a slow random walk is 0.999 one block away; a real excerpt is 0.9995 vs 0.979)
MIN_LEN = 8


def block_mean(x, decimation: int):
    d = int(decimation)
    if d <= 1:
        return np.asarray(x, dtype=np.float64)
    x = np.asarray(x, dtype=np.float64)
    usable = (len(x) // d) * d
    return x[:usable].reshape(-1, d).mean(axis=1)


def find_excerpt(short, long, decimation: int = 1) -> dict:
    """Locate ``short`` inside ``block_mean(long, decimation)``.

    Returns ``{"r", "offset", "sharp", "decimation", "neighbours", "n_lags"}``:
    ``offset`` is in ``long``'s own samples (lag × decimation); ``sharp`` is
    True when the peak beats both neighbours by ``SHARP_MARGIN``. A pair that
    cannot be compared (short longer than long, or too short) returns r = 0.
    """
    from scipy.signal import fftconvolve

    d = int(decimation) if decimation else 1
    x = np.asarray(short, dtype=np.float64)
    y = block_mean(long, d)
    m = len(x)
    if m < MIN_LEN or m > len(y):
        return {"r": 0.0, "offset": None, "sharp": False, "decimation": d, "neighbours": [], "n_lags": 0}
    x = x - x.mean()
    sx = x.std()
    if not np.isfinite(sx) or sx == 0:
        return {"r": 0.0, "offset": None, "sharp": False, "decimation": d, "neighbours": [], "n_lags": 0}
    x = x / sx
    y = y - y.mean()                                    # reduces cancellation in the running sums
    # sliding sums of y and y^2 over windows of m (valid lags)
    ones = np.ones(m)
    csum = np.concatenate([[0.0], np.cumsum(y)])
    csq = np.concatenate([[0.0], np.cumsum(y * y)])
    n_lags = len(y) - m + 1
    win_sum = csum[m:m + n_lags] - csum[:n_lags]
    win_sq = csq[m:m + n_lags] - csq[:n_lags]
    win_mean = win_sum / m
    win_var = np.maximum(win_sq / m - win_mean ** 2, 0.0)
    win_sd = np.sqrt(win_var)
    num = fftconvolve(y, x[::-1], mode="valid")         # sum over the window of y * x (x already zero-mean)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = num / (m * win_sd)
    r[~np.isfinite(r)] = 0.0
    if not len(r):
        return {"r": 0.0, "offset": None, "sharp": False, "decimation": d, "neighbours": [], "n_lags": 0}
    i = int(np.argmax(r))
    peak = float(r[i])
    neighbours = [float(r[j]) for j in (i - 1, i + 1) if 0 <= j < len(r)]
    need = max(SHARP_MARGIN, SHARP_RELATIVE * (1.0 - peak))
    sharp = bool(all(peak - nb >= need for nb in neighbours)) if neighbours else True
    del ones
    return {"r": peak, "offset": i * d, "sharp": sharp, "decimation": d, "neighbours": neighbours, "n_lags": int(n_lags)}


def is_excerpt(hit: dict) -> bool:
    return bool(hit and hit.get("offset") is not None and hit["r"] > R_THRESHOLD and hit["sharp"])
