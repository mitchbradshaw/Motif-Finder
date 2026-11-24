"""
r4.py
=====
R4 - the MiniRocket classifier trained on the researcher's verdicts (RQ1b, `scripts/rq1b_minirocket.py`, model
2026-10-20 23:43) - as auto-detect scores with it, without the training script.

Inference only, by the training script's own rules, so a span scores here what it scores there
(`tests/test_autodetect_r4.py` checks the two agree):

    rule 4, the input   the span plus a quarter of its length each side, in millivolts, gaps under 5 % filled,
                        resampled to 512 points (bin means, or linear when shorter), and four side features:
                        duration (s), peak-to-peak (mV), noise (mV: median |diff| x 1.4826 / sqrt 2) and their ratio
    rule 5, the model   MiniRocket on the z-normalised input, the log10 side features, a scaler, a ridge, and Platt's
                        sigmoid for a probability

The script reads each span from the recording's file; here the caller hands the recording's samples (millivolts)
once, so a scan of thousands of windows does not reopen the file for each.

No plotting library - CLAUDE.md rule 1. numpy, pandas; joblib, aeon and scikit-learn when a model is loaded.
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd

from Working.Catalogue.minirocket import MAX_GAP_FRAC, znormalise

#: The model auto-detect uses (relative to the repository root, as every core path is).
MODEL = os.path.join("DATA", "derived", "models", "rq1b_minirocket", "20261020-2343", "model.joblib")
#: Rule 4: a quarter of the span's length either side, 512 points, four side features.
PAD = 0.25
LENGTH = 512
SIDE = ("duration_s", "p2p_mv", "noise_mv", "snr")


def load_model(path=MODEL):
    """The fitted model (a dict: ``minirocket``, ``use_side``, ``scaler``, ``ridge``, ``platt``)."""
    import joblib
    return joblib.load(path)


def resample(x, n):
    """`x` reduced to `n` points by bin means, or stretched to `n` linearly when shorter."""
    x = np.asarray(x, dtype=float)
    m = len(x)
    if m == n:
        return x.copy()
    if m > n:
        edges = np.round(np.linspace(0, m, n + 1)).astype(np.int64)
        return np.add.reduceat(x, edges[:-1]) / np.diff(edges)
    return np.interp(np.linspace(0, m - 1, n), np.arange(m), x)


def inputs(x_mv, fs, starts, ends, *, length=LENGTH, pad=PAD):
    """Rule 4 for spans of `x_mv` (absolute indices into it): ``(M, side, keep)`` - one `length`-point row per span
    (zeros where left out), the side features, and which spans could be read."""
    n = len(x_mv)
    starts = np.asarray(starts, dtype=np.int64)
    ends = np.asarray(ends, dtype=np.int64)
    M = np.zeros((len(starts), int(length)), dtype=np.float64)
    keep = np.ones(len(starts), dtype=bool)
    side = []
    for i, (s, e) in enumerate(zip(starts, ends)):
        span = max(1, int(e) - int(s))
        p = int(round(pad * span))
        a, b = max(0, int(s) - p), min(n, int(e) + p)
        x = np.asarray(x_mv[a:b], dtype=np.float64)
        finite = np.isfinite(x)
        if x.size < 2 or (1.0 - finite.mean()) > MAX_GAP_FRAC:
            keep[i] = False
            side.append({k: np.nan for k in SIDE})
            continue
        if not finite.all():
            k = np.arange(x.size)
            x = x.copy()
            x[~finite] = np.interp(k[~finite], k[finite], x[finite])
        M[i] = resample(x, length)
        p2p = float(np.ptp(x))
        noise = float(np.median(np.abs(np.diff(x)))) * 1.4826 / np.sqrt(2.0) if x.size > 1 else 0.0
        side.append({"duration_s": span / float(fs), "p2p_mv": p2p, "noise_mv": noise,
                     "snr": p2p / max(noise, 1e-9)})
    return M, pd.DataFrame(side, columns=list(SIDE)), keep


def side_matrix(side):
    return np.log10(np.maximum(side[list(SIDE)].to_numpy(dtype=float), 1e-9)).astype(np.float32)


def _transform(mr, M, chunk=4_096):
    Z, _flat = znormalise(np.asarray(M, dtype=float))
    X = Z.astype(np.float32)[:, None, :]
    state = np.random.get_state()
    try:
        return np.concatenate([np.asarray(mr.transform(X[i:i + chunk]), dtype=np.float32)
                               for i in range(0, len(X), chunk)], axis=0)
    finally:
        np.random.set_state(state)


def probability(model, M, side):
    """Rule 5: the model's probability that each span is interesting."""
    parts = []
    if model["minirocket"] is not None:
        parts.append(_transform(model["minirocket"], M))
    if model["use_side"]:
        parts.append(side_matrix(side))
    X = np.hstack(parts) if len(parts) > 1 else parts[0]
    d = np.asarray(model["ridge"].decision_function(model["scaler"].transform(X)), dtype=float)
    a, b = model["platt"] if model.get("platt") else (1.0, 0.0)
    return 1.0 / (1.0 + np.exp(-(a * d + b)))


class Scorer:
    """``score(starts, ends) -> p`` for spans relative to ``offset`` on a recording whose samples (millivolts) are
    ``x_mv`` - the pipeline's ``score_spans``. ``invert`` scores the inverted signal (the side features do not change
    sign). NaN where a span cannot be read."""

    def __init__(self, model, x_mv, fs, *, offset=0, invert=False, chunk=2048):
        self.model, self.x_mv, self.fs = model, x_mv, float(fs)
        self.offset, self.invert, self.chunk = int(offset), bool(invert), int(chunk)

    def __call__(self, starts, ends):
        starts = np.asarray(starts, dtype=np.int64) + self.offset
        ends = np.asarray(ends, dtype=np.int64) + self.offset
        out = np.full(len(starts), np.nan)
        for i in range(0, len(starts), self.chunk):
            M, side, keep = inputs(self.x_mv, self.fs, starts[i:i + self.chunk], ends[i:i + self.chunk])
            if keep.any():
                block = -M[keep] if self.invert else M[keep]
                sub = out[i:i + self.chunk]
                sub[keep] = probability(self.model, block, side[keep].reset_index(drop=True))
                out[i:i + self.chunk] = sub
        return out
