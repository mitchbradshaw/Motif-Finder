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

#: the shortest rolling window, in SAMPLES. A MAD from fewer samples is itself
#: noisy (relative SE ~ 1.17/sqrt(window)), and a cut at k·σ_n turns every low
#: draw into false spans: on white noise at k = 4 a 3-sample window gave ~1300×
#: the whole-span false positives, 60 samples ~7×, 300 samples ~1.8× (measured
#: on 5 × 200k samples). 300 is where that cost stops mattering.
MIN_ROLLING_WINDOW = 300


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
    estimate and is interpolated across. A window whose MAD is 0 (flat, or
    more than half its samples on one value) has no noise level: it is never
    an interpolation anchor — blending a 0 into its neighbours would hand the
    noisy samples beside a flat stretch a tiny σ_n and fire on them. Every
    sample within half a window (plus one hop) of such a window gets sigma 0,
    i.e. "not judged": its own window reaches into the flat stretch, so its
    MAD is deflated even where it is not 0, and the windows touching that zone
    are not anchors either. A flat stretch shorter than half a window never
    makes a σ = 0 window and is not caught here; it deflates its windows'
    MAD in proportion, as it would the whole-span estimate. A `window` at least
    as long as the trace is the whole-trace estimate, constant. Both arrays
    are NaN when no window could be judged.

    `window` below `MIN_ROLLING_WINDOW` samples is refused: a library call does
    not silently change its argument (the adapter clamps and says so)."""
    v = np.asarray(x, dtype=float).ravel()
    n = v.size
    window = int(window)
    if window < MIN_ROLLING_WINDOW:
        raise ValueError(
            f"rolling_noise: the window must be at least {MIN_ROLLING_WINDOW} samples, got {window} — a MAD "
            "from fewer samples is too noisy an estimate of σ_n, and a cut at k·σ_n then fires on noise")
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
    idx = np.arange(n)
    zero = np.isfinite(sigmas) & (sigmas == 0)
    # Samples whose window reaches into a flat stretch: within half a window (plus
    # one hop, the anchor spacing) of a σ = 0 window's centre. Their windows are
    # partly flat, so their MAD is deflated even where it is not 0.
    flat_zone = np.zeros(n, dtype=bool)
    if zero.any():
        hits = np.zeros(n + 1)
        hits[anchors[zero]] = 1.0
        reach = window // 2 + hop
        c = np.concatenate([[0.0], np.cumsum(hits[:n])])
        flat_zone = (c[np.minimum(idx + reach + 1, n)] - c[np.maximum(idx - reach, 0)]) > 0
    good = np.isfinite(sigmas) & (sigmas > 0) & ~flat_zone[anchors]
    if not good.any():
        if zero.any():                          # every judged window flat or touching flat: σ_n 0
            return np.interp(idx, anchors[zero], centres[zero]), np.zeros(n)
        return np.full(n, np.nan), np.full(n, np.nan)
    centre = np.interp(idx, anchors[good | zero], centres[good | zero])
    sigma = np.interp(idx, anchors[good], sigmas[good])
    sigma[flat_zone] = 0.0                     # not judged — never a neighbour's σ, never a deflated one
    return centre, sigma
