"""
noise_level.py
===============
The robust noise level of a trace: σ_n = median|x − median(x)| / 0.6745,
after Quian Quiroga, Nadasdy & Ben-Shaul (2004), *Neural Comput.* 16(8),
1661–1687, eq. 3.1 (doi:10.1162/089976604774201631). The ordinary standard
deviation is set by the very spikes a threshold is meant to find; the median
barely notices them "under the reasonable assumption that spikes amount to a
small fraction of all samples" (the paper's words, §3.1).

Two adaptations, each for a reason our data force:

1. **Median absolute DEVIATION, not median|x|.** The paper's signal is
   band-passed at 300–6000 Hz and so zero-mean by construction; ours is a
   1 Hz trace after a rolling-mean detrend, which can leave an offset (the
   rolling mean is pulled by the very events, the median is not). Subtracting
   the median first keeps σ_n blind to that offset, and the median is
   returned as the `centre` the cut is laid around.
2. **NaN samples are skipped** (a recording's gaps), and a `rolling` variant
   gives a noise level per sample for channels whose noise changes over days.

Why not a second copy of an existing helper: the MAD itself is
`Working.Detection.drop_motifs.detect.robust_sigma` (1.4826 × MAD; 1/0.6745 =
1.48258, the same constant to five figures), imported here rather than
rewritten. It is not NaN-aware and returns no centre, so this module wraps it;
it is not changed, because the drop detector's frozen numbers depend on it.
`Working.Detection.analysis.wavelet_analysis`'s `mad` threshold mode is a
whole-threshold rule on a summation curve, not a reusable estimator.

Imports no UI library.
"""

import warnings

import numpy as np

from Working.Detection.drop_motifs.detect import _MAD_TO_SIGMA, robust_sigma

#: rows of the strided rolling evaluation handled per numpy call (memory bound)
_CHUNK_ELEMENTS = 4_000_000


def noise_sigma(x):
    """σ_n of the finite samples of `x`: 1.4826 × median|x − median(x)|.

    NaN when `x` holds no finite sample; 0.0 for a trace that is constant on
    more than half its samples (the caller must treat that as "no noise level",
    never divide by it)."""
    return noise_level(x)[1]


def noise_level(x):
    """`(centre, sigma)` of the finite samples of `x`: the median, and σ_n
    around it. Both NaN when there is no finite sample."""
    v = np.asarray(x, dtype=float).ravel()
    v = v[np.isfinite(v)]
    if v.size == 0:
        return float("nan"), float("nan")
    return float(np.median(v)), float(robust_sigma(v))


def rolling_noise(x, window):
    """Per-sample `(centre, sigma)` arrays from a rolling median and MAD.

    The MAD is evaluated on full `window`-sample windows every
    `hop = max(1, window // 4)` samples, attributed to each window's centre,
    and linearly interpolated between those centres (held flat beyond the
    first and last), so the cost is about 4·n·log(window) rather than
    n·window. A window with fewer than half its samples finite gives no
    estimate and is interpolated across. A `window` at least as long as the
    trace is the whole-trace estimate, constant. Both arrays are NaN when no
    window could be judged."""
    v = np.asarray(x, dtype=float).ravel()
    n = v.size
    window = int(window)
    if window < 3:
        raise ValueError(f"rolling_noise: the window must be at least 3 samples, got {window}")
    if n == 0:
        return np.empty(0), np.empty(0)
    if window >= n:
        c, s = noise_level(v)
        return np.full(n, c), np.full(n, s)

    hop = max(1, window // 4)
    views = np.lib.stride_tricks.sliding_window_view(v, window)[::hop]
    anchors = np.arange(views.shape[0]) * hop + window // 2
    centres = np.full(views.shape[0], np.nan)
    sigmas = np.full(views.shape[0], np.nan)
    rows = max(1, _CHUNK_ELEMENTS // window)
    for a in range(0, views.shape[0], rows):
        block = views[a:a + rows]
        finite = np.isfinite(block).sum(axis=1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)   # an all-NaN window: masked out below
            med = np.nanmedian(block, axis=1)
            mad = np.nanmedian(np.abs(block - med[:, None]), axis=1)
        ok = finite >= (window + 1) // 2
        centres[a:a + rows] = np.where(ok, med, np.nan)
        sigmas[a:a + rows] = np.where(ok, _MAD_TO_SIGMA * mad, np.nan)
    good = np.isfinite(sigmas)
    if not good.any():
        return np.full(n, np.nan), np.full(n, np.nan)
    idx = np.arange(n)
    return (np.interp(idx, anchors[good], centres[good]),
            np.interp(idx, anchors[good], sigmas[good]))
