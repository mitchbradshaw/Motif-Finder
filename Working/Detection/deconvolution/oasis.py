"""
oasis.py
=========
OASIS — Friedrich J, Zhou P, Paninski L (2017) "Fast online deconvolution of
calcium imaging data", PLoS Comput Biol 13(3):e1005423 (arXiv:1609.00639).
**Written from the paper's text.** The authors' code (github.com/j-friedrich/OASIS)
is GPL-3.0 and was neither read nor copied; fidelity is checked instead against
a generic solver of the same optimisation (`tests/test_oasis.py`, scipy NNLS).

In plain words
--------------
Every event is modelled as a sudden jump followed by the same fade. Given a
trace, OASIS answers "what list of non-negative jumps, each followed by that
fade, best explains this?" — one number per sample, almost all zero. A fungal
trough is the shape upside down (a sudden drop, then a recovery), so the trace is
negated first; and because the fade belongs to the jump that caused it, a second
drop that starts before the first has recovered is a new jump of its own — the
case a plain threshold merges into one blob.

The model and the solver (the paper)
------------------------------------
y_t = b + c_t + noise, with the "calcium" c an autoregressive process driven by
non-negative jumps s_t:

    AR(1)  c_t = g c_{t-1} + s_t                      (instant rise)
    AR(2)  c_t = g1 c_{t-1} + g2 c_{t-2} + s_t         (finite rise)

and c minimises ||c - (y - b)||^2 subject to s >= 0 (optionally + lam*sum(s),
the l1 form, or with every non-zero jump >= s_min, the thresholded form). The
solver is the paper's active-set generalisation of pool-adjacent-violators: the
trace is cut into POOLS, each one jump followed by pure decay, so a pool is
described by its start and one value v (c_{t0+k} = v h_k [+ the previous pool's
tail]); samples are added left to right as one-sample pools, and while the
newest pool's jump is below s_min (0 for the plain form: a negative jump) it is
merged into the pool before it and that pool's v re-fitted. O(T) amortised.

Here the AR(2) kernel is parametrised by its two roots: `decay` d (the slow
recovery) and `rise` r (the fast rise; r = 0 is AR(1)), g1 = d + r, g2 = -d r,
and h_k = (d^{k+1} - r^{k+1}) / (d - r). Every pool sum the fit needs
(sum h_k y, sum h_k^2, sum h_k h_{k-1}) is then a pair of exponentially weighted
sums of y and closed-form geometric series, so merging two pools is O(1) for
AR(2) too. As in the paper, the AR(2) solver is greedy: a pool's value is fitted
given the previous pool's tail and not revisited (exact for AR(1); the AR(1)
solution equals NNLS to 1e-6 in the tests).

The l1 form is solved through the identity lam*sum(s) = lam * w.c with
w_t = 1 - g1[t <= T-2] - g2[t <= T-3] (sum s telescopes), i.e. the unpenalised
problem on y - lam*w. The trace-level wrapper uses the thresholded form.

Adaptations our data force (each named, with its reason)
---------------------------------------------------------
1. **Polarity.** `polarity='drop'` (default) negates the signal so a drop is a
   positive jump; `'spike'` reads it as stored.
2. **Time constants in seconds.** `recovery_half_s` > 0 sets d = 2^(-1/(half fs));
   0 estimates d from the data (below). `rise_s` > 0 is the rise TIME CONSTANT in
   seconds, r = exp(-1/(rise_s fs)), and makes the model AR(2); 0 is AR(1).
   The γ actually used and its half-time are reported.
3. **Unit-free output.** The score is s_t / sigma — the jump size in NOISE SDs —
   and s_min = min_jump_sigma * sigma, so scaling the recording by 1000 (volts ↔
   millivolts) changes nothing. sigma (stored units) is reported.
4. **sigma** is a robust MAD estimate on first differences (1.4826 MAD / sqrt 2)
   rather than the paper's high-frequency PSD: at 1 Hz the drops themselves put
   power in every band, while in the differences they are a handful of outliers
   the median ignores. A quantised trace whose differences are mostly zero falls
   back to their SD.
5. **gamma estimate** (`recovery_half_s = 0`), the paper's two steps. First the
   autocovariance (lag 0 excluded: white noise only sits there): for c = h * s
   with WHITE s it decays as d^k, so log C(k) is fitted over lags 1 .. 2 k_half
   (k_half: the first lag where C falls to half of C(1)). Fungal events are not
   white — they come roughly regularly, which makes C fall faster than d^k (on
   the 12 h synthetic this first guess reads 88 s for a true 120 s). So, second,
   the paper's refinement: the half-time minimising the thresholded fit's RSS,
   searched from a third to three times the first guess on a coarse log grid and
   then by a bounded scalar search (the RSS is bumpy far from the truth), on at
   most 400 000 samples. An estimate that cannot be made (C never halves —
   drift — or C(1) <= 0) raises and says to set `recovery_half_s` or detrend.
6. **Drift is not handled** (the paper says so): the baseline b is ONE constant
   per span, started at the paper's low percentile (15th) and refined as
   mean(y - c) until it moves by less than 0.001 sigma (at most 10 passes). Put
   BEADS first, or use 6b.
6b. **An optional running floor** (`baseline_window_s` > 0; 0 = the paper). The
   paper notes that drifting baselines "could be generalized" but does not do
   it, and a rolling-MEAN detrend upstream is a poor substitute on a trough
   train: every trough drags the window's mean down as it enters and up as it
   leaves, leaving 1-2 noise-SD steps that a constant b can only explain as a
   rash of small jumps (on the 12 h synthetic with a 1 h rolling mean: ~800
   events for 30 troughs). So the block can put the paper's own starting
   baseline -- the 15th percentile -- under b LOCALLY: the 15th percentile of
   y in a centred window, every window/4 samples, interpolated (calcium
   imaging's running-percentile F0). A trough sits on the high side of y, so
   the floor follows the drift and not the troughs, provided the window is
   several recoveries long. b is then refined on top of it as before.
7. **Thresholded form with a fixed s_min.** The paper raises s_min until the RSS
   reaches sigma^2 T; here s_min is min_jump_sigma * sigma, one readable knob.
8. **The first sample is the initial level, not a jump.** A span that starts mid
   recovery has c_0 > 0; that "jump" is everything before the span. It is fitted
   (c_0 >= 0, never thresholded) but scored 0 and reported in `initial_levels`.
9. **NaN.** Missing samples split the trace into finite segments, each
   deconvolved on its own (sharing b, sigma and γ); the scores are NaN there.
"""

from dataclasses import dataclass, field
from typing import List

import numpy as np

from Working.Preprocessing.detrend import _rolling_mean

try:                                   # numba is in the environment; the plain-Python path is identical
    from numba import njit as _njit

    def _jit(fn):
        return _njit(cache=True)(fn)
except Exception:                      # pragma: no cover - only without numba
    def _jit(fn):
        return fn

POLARITIES = ("drop", "spike")
_MAD_TO_SIGMA = 1.4826
BASELINE_PERCENTILE = 15.0
BASELINE_TOL_SIGMA = 1e-3
BASELINE_MAX_ITER = 10
REFINE_MAX_SAMPLES = 400_000
REFINE_GRID = 15
REFINE_BASELINE_ITER = 4


# -- parameters ----------------------------------------------------------------

def decay_from_half_time(half_s, fs):
    """The per-sample factor d with d ** (half_s * fs) == 1/2."""
    half_s, fs = float(half_s), float(fs)
    if half_s <= 0 or fs <= 0:
        raise ValueError(f"decay_from_half_time: half_s and fs must be > 0, got {half_s}, {fs}")
    return 2.0 ** (-1.0 / (half_s * fs))


def half_time_from_decay(decay, fs):
    return float(np.log(0.5) / (np.log(decay) * fs))


def rise_root(rise_s, fs):
    """The fast root r of the AR(2) kernel for a rise time constant `rise_s` (0 -> AR(1))."""
    rise_s = float(rise_s)
    if rise_s <= 0:
        return 0.0
    return float(np.exp(-1.0 / (rise_s * float(fs))))


def ar_coefficients(decay, rise=0.0):
    """(g1, g2) of c_t = g1 c_{t-1} + g2 c_{t-2} + s_t from the kernel's two roots."""
    return float(decay + rise), float(-decay * rise)


# -- the solver ----------------------------------------------------------------

@_jit
def _fit_value(Ad, Ar, dl, rl, u, d, r, g2, first):
    """The least-squares value v of a pool of length l (dl = d^l, rl = r^l) given its weighted
    sums Ad = sum d^k y, Ar = sum r^k y and the value u just before it. Every sum over the
    pool is a closed-form geometric series, so no power is taken here."""
    dr = d - r
    dr2 = dr * dr
    gdd = (1.0 - dl * dl) / (1.0 - d * d)          # sum_{k<l} d^{2k}
    gdr = (1.0 - dl * rl) / (1.0 - d * r)          # sum_{k<l} (dr)^k
    grr = (1.0 - rl * rl) / (1.0 - r * r)          # sum_{k<l} r^{2k}
    yh = (d * Ad - r * Ar) / dr                    # sum h_k y_k
    hh = (d * d * gdd - 2.0 * d * r * gdr + r * r * grr) / dr2   # sum h_k^2
    v = yh
    if g2 != 0.0 and u != 0.0:
        hh1 = (d * (gdd - 1.0) - (d + r) * (gdr - 1.0) + r * (grr - 1.0)) / dr2   # sum h_k h_{k-1}
        v = yh - g2 * u * hh1
    v = v / hh
    if first and v < 0.0:
        v = 0.0
    return v


@_jit
def _tail(v, u, dl, rl, ln, d, r, g2):
    """The last two values of a pool, c_{l-1} and c_{l-2} (c_{-1} = u)."""
    dr = d - r
    # d^{l-1}, d^{l-2}, r^{l-1}, r^{l-2}
    d1 = dl / d
    d2 = d1 / d
    if r == 0.0:
        r1 = 1.0 if ln == 1 else 0.0
        r2 = 1.0 if ln == 2 else 0.0
    else:
        r1 = rl / r
        r2 = r1 / r
    h_l1 = (dl - rl) / dr            # h_{l-1}
    h_l2 = (d1 - r1) / dr            # h_{l-2} (0 when l = 1)
    last = v * h_l1 + g2 * u * h_l2
    if ln >= 2:
        h_l3 = (d2 - r2) / dr        # h_{l-3} (0 when l = 2)
        second = v * h_l2 + g2 * u * h_l3
    else:
        second = u
    return last, second


@_jit
def _oasis_kernel(y, d, r, s_min):
    T = y.shape[0]
    g1 = d + r
    g2 = -d * r
    t0 = np.empty(T, np.int64)
    ln = np.empty(T, np.int64)
    Ad = np.empty(T)
    Ar = np.empty(T)
    dl = np.empty(T)
    rl = np.empty(T)
    v = np.empty(T)
    u = np.empty(T)
    u2 = np.empty(T)
    n = 0
    for t in range(T):
        t0[n] = t
        ln[n] = 1
        Ad[n] = y[t]
        Ar[n] = y[t]
        dl[n] = d
        rl[n] = r
        if n == 0:
            u[n] = 0.0
            u2[n] = 0.0
        else:
            i = n - 1
            u[n], u2[n] = _tail(v[i], u[i], dl[i], rl[i], ln[i], d, r, g2)
        v[n] = _fit_value(Ad[n], Ar[n], dl[n], rl[n], u[n], d, r, g2, n == 0)
        n += 1
        while n > 1:
            j = n - 1
            s_j = v[j] - g1 * u[j] - g2 * u2[j]
            if s_j >= s_min:
                break
            i = j - 1
            Ad[i] += dl[i] * Ad[j]
            Ar[i] += rl[i] * Ar[j]
            dl[i] *= dl[j]
            rl[i] *= rl[j]
            ln[i] += ln[j]
            v[i] = _fit_value(Ad[i], Ar[i], dl[i], rl[i], u[i], d, r, g2, i == 0)
            n -= 1
    c = np.empty(T)
    s = np.zeros(T)
    dr = d - r
    for p in range(n):
        dk, rk = 1.0, 1.0            # d^k, r^k
        vp, up = v[p], g2 * u[p]
        base = t0[p]
        for k in range(ln[p]):
            dk1 = dk * d
            rk1 = rk * r
            c[base + k] = (vp * (dk1 - rk1) + up * (dk - rk)) / dr
            dk, rk = dk1, rk1
        s[base] = v[p] - g1 * u[p] - g2 * u2[p]
    return c, s


def oasis(y, decay, rise=0.0, s_min=0.0, lam=0.0):
    """Deconvolve `y` (baseline already removed) into calcium `c` and jumps `s`.

    `decay`, `rise`: the kernel's roots (rise = 0 is AR(1)); `s_min`: the
    thresholded form's minimum non-zero jump (the first sample, the initial
    level, is exempt); `lam`: the l1 penalty. Returns (c, s), s[0] = c[0]."""
    y = np.ascontiguousarray(np.asarray(y, dtype=float).ravel())
    d, r = float(decay), float(rise)
    if not 0.0 < d < 1.0:
        raise ValueError(f"oasis: decay must lie in (0, 1), got {d}")
    if not 0.0 <= r < d:
        raise ValueError(f"oasis: the rise root ({r:.6g}) must be >= 0 and faster than the decay "
                         f"({d:.6g}) — a rise time no shorter than the recovery is not a rise")
    if y.size == 0:
        return np.zeros(0), np.zeros(0)
    if not np.all(np.isfinite(y)):
        raise ValueError("oasis: y holds NaN or inf; split the trace into finite segments first")
    if lam:
        g1, g2 = ar_coefficients(d, r)
        w = np.ones_like(y)
        w[: max(y.size - 1, 0)] -= g1
        w[: max(y.size - 2, 0)] -= g2
        y = y - float(lam) * w
    return _oasis_kernel(y, d, r, float(s_min))


# -- noise, decay and baseline ---------------------------------------------------

def _finite_segments(finite):
    padded = np.concatenate(([False], finite, [False])).astype(np.int8)
    diff = np.diff(padded)
    return list(zip(np.flatnonzero(diff == 1), np.flatnonzero(diff == -1)))


def noise_sigma(segments):
    """Robust noise SD from first differences: 1.4826 MAD(diff) / sqrt(2) (a jump is an outlier the
    median ignores). Falls back to SD(diff)/sqrt(2) when most differences are zero (a quantised trace)."""
    diffs = np.concatenate([np.diff(s) for s in segments if len(s) > 1] or [np.zeros(0)])
    if diffs.size == 0:
        return 0.0
    mad = float(np.median(np.abs(diffs - np.median(diffs))))
    sigma = _MAD_TO_SIGMA * mad / np.sqrt(2.0)
    if sigma <= 0:
        sigma = float(np.std(diffs)) / np.sqrt(2.0)
    return float(sigma)


def autocovariance(segments, max_lag):
    """C(k), k = 0..max_lag, pooled over finite segments (mean removed once, over all of them)."""
    mean = float(np.mean(np.concatenate(segments)))
    num = np.zeros(max_lag + 1)
    cnt = np.zeros(max_lag + 1)
    for seg in segments:
        z = np.asarray(seg, float) - mean
        m = len(z)
        if m < 2:
            continue
        nfft = 1 << int(np.ceil(np.log2(2 * m)))
        f = np.fft.rfft(z, nfft)
        ac = np.fft.irfft(f * np.conj(f), nfft)[: min(m, max_lag + 1)]
        num[: ac.size] += ac
        cnt[: ac.size] += m - np.arange(ac.size)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(cnt > 0, num / np.maximum(cnt, 1), np.nan)


def estimate_decay(segments, fs):
    """The recovery factor d from the autocovariance (lag 0 excluded): log C(k) fitted linearly over
    lags 1 .. 2*k_half, k_half the first lag where C has fallen to half of C(1). Raises when the
    autocovariance does not decay (drift, or no events) instead of guessing."""
    longest = max(len(s) for s in segments)
    max_lag = max(4, longest // 4)
    C = autocovariance(segments, max_lag)
    if not np.isfinite(C[1]) or C[1] <= 0:
        raise ValueError("detection.deconvolve: cannot estimate the recovery — the lag-1 autocovariance is not "
                         "positive (no slow events in this span). Set recovery_half_s.")
    below = np.flatnonzero(C[1:] <= 0.5 * C[1])
    if below.size == 0:
        raise ValueError(f"detection.deconvolve: cannot estimate the recovery — the autocovariance never halves "
                         f"within {max_lag} samples ({max_lag / fs:g} s), which is drift rather than recovery. Put a "
                         f"long detrend (or BEADS) first, or set recovery_half_s.")
    k_half = int(below[0]) + 1
    ks = np.arange(1, min(2 * k_half, max_lag) + 1)
    keep = C[ks] > 0
    ks = ks[keep]
    if ks.size < 2:
        raise ValueError("detection.deconvolve: cannot estimate the recovery — too few positive lags. Set recovery_half_s.")
    slope = np.polyfit(ks.astype(float), np.log(C[ks]), 1)[0]
    if slope >= 0:
        raise ValueError("detection.deconvolve: cannot estimate the recovery — the autocovariance does not decay. "
                         "Set recovery_half_s.")
    return float(np.exp(slope)), k_half



def running_floor(y, window_samples, q=BASELINE_PERCENTILE):
    """A slowly varying floor under y: a running q-th percentile, in two passes.

    One pass is the q-th percentile of the finite samples in a centred window of `window_samples`,
    evaluated every window/4 samples and linearly interpolated (about 4 n work, in row chunks so
    memory stays bounded). On a sloping baseline that percentile sits (0.5 - q/100) x slope x window
    BELOW the line (a ramp's own spread), which on a drifting recording is several noise SDs; so a
    second pass takes the same running percentile of y minus the first floor — now nearly flat — and
    adds it back, cancelling the slope bias up to a constant (the noise quantile, which the refined
    constant b absorbs). NaN samples are skipped; NaN where y is NaN."""
    y = np.asarray(y, dtype=float)
    first = _running_percentile(y, window_samples, q)
    return first + _running_percentile(y - first, window_samples, q)


def _running_percentile(y, window_samples, q):
    y = np.asarray(y, dtype=float)
    n = y.size
    w = max(3, int(window_samples))
    half = w // 2
    stride = max(1, w // 4)
    centres = np.arange(0, n, stride)
    if centres[-1] != n - 1:
        centres = np.append(centres, n - 1)
    padded = np.concatenate((np.full(half, np.nan), y, np.full(w - half, np.nan)))
    view = np.lib.stride_tricks.sliding_window_view(padded, w)     # row i = y[i-half : i-half+w]
    vals = np.empty(centres.size)
    rows = max(1, int(2e7 // w))
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)              # an all-NaN window -> NaN, dropped below
        for k in range(0, centres.size, rows):
            vals[k:k + rows] = np.nanpercentile(view[centres[k:k + rows]], q, axis=1)
    ok = np.isfinite(vals)
    if not ok.any():
        raise ValueError("detection.deconvolve: no finite sample to put a running baseline under.")
    out = np.interp(np.arange(n, dtype=float), centres[ok].astype(float), vals[ok])
    out[~np.isfinite(y)] = np.nan
    return out


# -- the trace-level wrapper -----------------------------------------------------

@dataclass
class Deconvolution:
    scores: np.ndarray            # s / sigma, one per sample, NaN where x is NaN, 0 at each segment's first sample
    c: np.ndarray                 # the fitted fade (y orientation, baseline removed), NaN where x is NaN
    s: np.ndarray                 # the jumps in stored units (y orientation)
    sign: float                   # y = sign * x
    baseline: float               # b, in y orientation (the median of `floor` when the baseline runs)
    sigma: float                  # noise SD, stored units
    decay: float
    rise: float
    half_s: float
    estimated: bool
    half_s_autocov: object        # the autocovariance's first guess (None when given)
    s_min: float
    n_nan: int
    n_segments: int
    n_baseline_iter: int
    baseline_converged: bool
    residual_sd_sigma: float
    initial_levels: List[float] = field(default_factory=list)   # c at each segment's first sample, in sigma
    floor: object = None          # the running baseline (y orientation, NaN at NaN), None for one constant
    baseline_window_s: float = 0.0

    @property
    def ar_coefficients(self):
        return ar_coefficients(self.decay, self.rise)


def _fit_segments(segments, decay, rise, s_min, sigma, b, max_iter, window=None):
    """Deconvolve each finite segment around the baseline b, refining it until it moves by less than
    BASELINE_TOL_SIGMA * sigma (at most `max_iter` fits).

    window None: b is ONE constant shared by the segments, refined as mean(y - c) (the paper).
    window = w samples: b is a list of per-segment arrays, refined as the centred rolling mean of
    y - c over w samples (adaptation 6b) — the same update, local.
    Returns (cs, ss, b, n_iter, converged, rss)."""
    tol = BASELINE_TOL_SIGMA * sigma
    ys = np.concatenate(segments)
    converged, n_iter, cs, ss = False, 0, [], []
    for n_iter in range(1, max_iter + 1):
        if window is None:
            fits = [oasis(seg - b, decay, rise, s_min) for seg in segments]
        else:
            fits = [oasis(seg - bb, decay, rise, s_min) for seg, bb in zip(segments, b)]
        cs, ss = [f[0] for f in fits], [f[1] for f in fits]
        if window is None:
            b_new = float(np.mean(ys - np.concatenate(cs)))
            moved = abs(b_new - b)
        else:
            b_new = [_rolling_mean(seg - ci, window) for seg, ci in zip(segments, cs)]
            moved = max(float(np.max(np.abs(bn - bb))) for bn, bb in zip(b_new, b))
        if moved <= tol:
            converged = True
            break
        b = b_new
    bs = b if window is None else np.concatenate(b)
    rss = float(np.sum((ys - bs - np.concatenate(cs)) ** 2))
    return cs, ss, b, n_iter, converged, rss


def _truncate(segments, max_samples):
    out, left = [], int(max_samples)
    for seg in sorted(segments, key=len, reverse=True):
        if left <= 1:
            break
        out.append(seg[:left])
        left -= len(out[-1])
    return out


def refine_decay(segments, decay0, rise, s_min, sigma, fs):
    """The paper's refinement: the decay minimising the fit's RSS, searched in log half-time from a third
    to three times the autocovariance estimate — a coarse grid first (the RSS is bumpy far from the
    truth), then a bounded scalar search between the best grid point's neighbours. Runs on at most
    REFINE_MAX_SAMPLES samples (the longest segments). A rise is kept fixed."""
    from scipy.optimize import minimize_scalar

    segs = _truncate(segments, REFINE_MAX_SAMPLES)
    b0 = float(np.percentile(np.concatenate(segs), BASELINE_PERCENTILE))
    h0 = half_time_from_decay(decay0, fs)
    lo_h = max(h0 / 3.0, 2.0 / fs)                     # a fade shorter than two samples is not a fade

    def rss(log_h):
        d = decay_from_half_time(float(np.exp(log_h)), fs)
        if rise >= d:
            return np.inf
        return _fit_segments(segs, d, rise, s_min, sigma, b0, REFINE_BASELINE_ITER)[5]

    grid = np.linspace(np.log(lo_h), np.log(3.0 * h0), REFINE_GRID)
    vals = np.array([rss(g) for g in grid])
    k = int(np.argmin(vals))
    lo, hi = grid[max(k - 1, 0)], grid[min(k + 1, len(grid) - 1)]
    best = minimize_scalar(rss, bounds=(lo, hi), method="bounded", options={"xatol": 1e-3})
    log_h = float(best.x) if best.fun <= vals[k] else float(grid[k])
    return decay_from_half_time(float(np.exp(log_h)), fs)


def deconvolve(x, fs, polarity="drop", recovery_half_s=0.0, rise_s=0.0, min_jump_sigma=3.0,
               baseline_window_s=0.0):
    """Thresholded OASIS on a whole span, with the adaptations named in the module docstring.
    `baseline_window_s` > 0 makes the baseline a slowly varying curve (adaptation 6b); 0 is the
    paper's one constant per span."""
    if polarity not in POLARITIES:
        raise ValueError(f"detection.deconvolve: polarity must be one of {POLARITIES}, got {polarity!r}")
    fs = float(fs)
    x = np.asarray(x, dtype=float).ravel()
    sign = -1.0 if polarity == "drop" else 1.0
    y = sign * x
    finite = np.isfinite(y)
    bounds = _finite_segments(finite)
    if not bounds:
        raise ValueError("detection.deconvolve: the span holds no finite sample.")
    window = None
    segments = [y[a:b] for a, b in bounds]
    z_segments = segments
    if baseline_window_s and baseline_window_s > 0:
        window = max(3, int(round(float(baseline_window_s) * fs)))
        floor0 = running_floor(y, window)
        z_segments = [(y - floor0)[a:b] for a, b in bounds]       # for sigma and the recovery estimate

    sigma = noise_sigma(z_segments)
    if sigma <= 0:
        raise ValueError("detection.deconvolve: the span is flat (no noise level, no jumps to measure).")
    s_min = float(min_jump_sigma) * sigma
    rise = rise_root(rise_s, fs)
    half_autocov = None
    if recovery_half_s and recovery_half_s > 0:
        decay, estimated = decay_from_half_time(recovery_half_s, fs), False
    else:
        decay0, _ = estimate_decay(z_segments, fs)
        half_autocov = half_time_from_decay(decay0, fs)
        decay = refine_decay(z_segments, decay0, rise, s_min, sigma, fs)
        estimated = True
    if rise >= decay:
        raise ValueError(f"detection.deconvolve: rise_s={rise_s:g} s is not shorter than the recovery "
                         f"(half-time {half_time_from_decay(decay, fs):g} s); a rise must be faster than the fade.")

    if window is None:
        b0 = float(np.percentile(y[finite], BASELINE_PERCENTILE))
    else:
        b0 = [floor0[a:e] for a, e in bounds]
    cs, ss, b, n_iter, converged, rss = _fit_segments(segments, decay, rise, s_min, sigma, b0,
                                                      BASELINE_MAX_ITER, window=window)
    floor = None
    if window is not None:
        floor = np.full(y.size, np.nan)
        for (a, e), bb in zip(bounds, b):
            floor[a:e] = bb
        b = float(np.nanmedian(floor))
    c = np.full(y.size, np.nan)
    s = np.full(y.size, np.nan)
    for (a, e), ci, si in zip(bounds, cs, ss):
        c[a:e], s[a:e] = ci, si

    initial = [float(c[a] / sigma) for a, _ in bounds]
    scores = s / sigma
    for a, _ in bounds:
        scores[a] = 0.0
    n_fin = int(finite.sum())
    return Deconvolution(
        scores=scores, c=c, s=s, sign=sign, baseline=b, sigma=sigma, decay=decay, rise=rise,
        half_s=half_time_from_decay(decay, fs), estimated=estimated, half_s_autocov=half_autocov, s_min=s_min,
        n_nan=int((~finite).sum()), n_segments=len(bounds), n_baseline_iter=n_iter,
        baseline_converged=converged, residual_sd_sigma=float(np.sqrt(rss / n_fin) / sigma),
        initial_levels=initial, floor=floor, baseline_window_s=float(baseline_window_s or 0.0),
    )
