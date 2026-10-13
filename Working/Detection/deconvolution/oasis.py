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
given the previous pool's tail and not revisited.

**Exact vs greedy.** Only the PLAIN AR(1) form (s >= 0, and the l1 form) is an
exact optimum: it equals NNLS to 1e-6 in the tests. The THRESHOLDED form (every
non-zero jump >= s_min, the one the block uses) is a non-convex problem and the
merge-left rule is a greedy approximation of it, as in the paper: against brute
force on tiny problems it was suboptimal in 55 % of cases, with a median RSS gap
of 5 %. The AR(2) solver is greedy too (RSS gap up to 16.5 % on the same tests).
The fits are good, not optimal; a jump count is a property of the greedy fit.

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
3. **Unit-free output.** The score is s_t / scale -- the jump size in NOISE SDs --
   and s_min = min_jump_sigma * scale, so scaling the recording by 1000 (volts <->
   millivolts) changes nothing. Both noise SDs (stored units) are reported, and
   `noise_scale` names the one that is `scale`.
4. **The noise SD: the background's level, not its steps** (`noise_scale`).
   The paper reads the noise from the high-frequency PSD, i.e. assumes it WHITE.
   Smooth 1 Hz fungal recordings are not: each sample sits close to the last,
   so on three real channels behind the template's detrend the SD of the
   first differences / sqrt 2 (`sigma`) was 1/46, 1/38 and 1/3.4 of the
   background's own spread, and "3 sigma" jumps were noise wiggles (1,716
   jumps in 4 h on one; residual 164 sigma). So the default (`level`) is
   `sigma_level`: the samples minus a running floor (the running baseline's
   own floor, or -- one constant baseline -- a 15th percentile over 15
   recovery half-times, so drift slower than that stays a misfit of the
   constant, which the residual SD reports), then the median and 1.4826 MAD,
   recomputed on the samples within 3 SDs until the SD settles (sigma
   clipping: the troughs are cut away; their small tails inflate it ~1.2x on
   white noise). On AR(1) noise (phi 0.95, 0.99) and 1/f noise it reads the
   true SD within ~20 %, where `sigma` reads 0.1-0.4 of it. `diff` keeps the
   paper's reading -- 1.4826 MAD of the first differences / sqrt 2, which a
   jump barely moves; a quantised trace whose differences are mostly zero falls
   back to their SD. **Blind spot of `level`:** it needs quiet background
   between events. When events fill the trace (back-to-back sharkfins) it
   measures the events, and the threshold rises toward them (on the
   back-to-back sharkfin test: sigma_level 23x sigma, no jump at all). Such a
   trace's samples fill a band evenly instead of scattering like noise about
   a floor, so `level_spread` = (P97.5 - P2.5) / (3.92 sigma_level) -- about 1
   for Gaussian noise of any colour (0.95-1.01 on AR(1) and 1/f), larger with
   troughs (4.6-8.5) -- falls to ~0.6 there; below 0.75 it is a warning that
   names noise_scale = diff. The summary also prints sigma_level / sigma.
   **Only the unit changes, not the model.** The fit is least squares, which
   no noise SD enters; the SD sets s_min, the scores, the baseline's tolerance,
   the residual SD's unit and the recovery refinement's jump price (RSS /
   scale^2 + 2 ln T per jump: with `level` the RSS of a right fit on coloured
   noise is ~T scale^2, as the criterion assumes; with `diff` it is 10-100x
   that, and every wiggle was worth a jump). Modelling the colour itself (an
   AR noise term in the solver) would leave OASIS's O(T) pool algorithm.
5. **gamma estimate** (`recovery_half_s = 0`), the paper's two steps. First the
   autocovariance (lag 0 excluded: white noise only sits there): for c = h * s
   with WHITE s it decays as d^k, so log C(k) is fitted over lags 1 .. 2 k_half
   (k_half: the first lag where C falls to half of C(1)). Fungal events are not
   white — they come roughly regularly, which makes C fall faster than d^k (on
   the 12 h synthetic this first guess reads 88 s for a true 120 s). So, second,
   the paper's refinement, GUARDED: the half-time minimising a penalised
   criterion, RSS / sigma^2 + 2 ln(T) x n_jumps (BIC: two parameters per jump),
   NOT the RSS at the fixed s_min. The plain RSS keeps falling as the fade
   shortens, because a short fade lets small jumps follow every wiggle a detrend
   leaves: behind the template's 1 h rolling mean and 30 min running baseline
   it chose 48 s for a true 300 s (740 events for 30 troughs) and 51 s for a true
   600 s (1072). The fit inside the search is the block's real one (the running
   baseline when on). Searched on a coarse log grid from a third to three times
   the first guess, RECENTRED on the best point (up to 3 times) when that is an
   edge, then a bounded scalar search; at most 400 000 samples. Even guarded,
   an estimate is a fallback: the summary warns when it still sits on an edge,
   or when the jumps come faster than they recover (> 30 per hour, or
   n_jumps x half-time > half the span), and the template gives the half-time.
   When no estimate can be made (C never halves -- drift -- or C(1) <= 0) a
   fit at 120 s is tried: no jump there either is a QUIET channel (all-zero
   scores, `estimated` False, `estimate_note` saying why); jumps there raise
   and say to set `recovery_half_s` or detrend.
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
   several recoveries long. b is then refined on top of it as before, until its
   MEAN per-sample step is below 0.05 sigma: the largest step shrinks only
   0.5-0.8x per pass, so a per-sample-max test at 0.001 sigma never passed in 10
   passes while the jumps had stopped changing after one or two. Not converged
   in 10 passes (a window short of ~15 half-times) is said in the summary.
7. **Thresholded form with a fixed s_min.** The paper raises s_min until the RSS
   reaches sigma^2 T; here s_min is min_jump_sigma * scale, one readable knob.
   The residual SD (RMS of y - b - c in scale) is reported, and flagged above
   1.5: events that are not a sudden jump followed by this fade (a sharkfin's
   plateau and slow climb) are split into many small jumps, and the count is
   then not an event count. A kernel that recovers faster than the troughs
   splits each into a jump and smaller follow-ons that land on its fade: more
   than 35 % of the jumps being follow-ons is flagged (with the level noise SD
   a too-short kernel no longer makes enough jumps to trip the per-hour flag).
8. **The first sample is the initial level, not a jump.** A span that starts mid
   recovery has c_0 > 0; that "jump" is everything before the span. It is fitted
   (c_0 >= 0, never thresholded) but scored 0 and reported in `initial_levels`.
   The same holds at the first sample after a NaN gap, so a drop that lands
   there is absorbed into that run's initial level: the runs after a gap whose
   initial level exceeds min_jump_sigma are counted and named in the summary.
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
NOISE_SCALES = ("level", "diff")       # the unit of the score and of min_jump_sigma (adaptation 4)
LEVEL_CLIP_K = 3.0                     # level_sigma: samples beyond k robust SDs are events, not background
LEVEL_CLIP_MAX_ITER = 30
LEVEL_SPREAD_FLAG = 0.75               # (P97.5 - P2.5) / (3.92 sigma_level): ~1 for noise about a floor,
                                       # ~0.6 when events fill the trace evenly (back-to-back sharkfins)
LEVEL_WINDOW_HALF_TIMES = 15.0         # constant baseline: sigma_level is measured about a floor this many
                                       # recovery half-times wide (the running baseline's own advice)
_MAD_TO_SIGMA = 1.4826
BASELINE_PERCENTILE = 15.0
BASELINE_TOL_SIGMA = 1e-3              # the constant baseline: a thousandth of a noise SD
RUNNING_BASELINE_TOL_SIGMA = 0.05      # the running one: its MEAN per-sample step (adaptation 6b)
BASELINE_MAX_ITER = 10
REFINE_MAX_SAMPLES = 400_000
REFINE_GRID = 15
REFINE_BASELINE_ITER = 4
REFINE_MAX_SHIFTS = 3                  # times the search is recentred when its best lands on an edge
FALLBACK_HALF_S = 120.0                # the half-time tried when no recovery can be estimated (F2)
PLAUSIBLE_JUMPS_PER_HOUR = 30.0        # more than this reads as fragmentation, not troughs
MAX_JUMP_OCCUPANCY = 0.5               # jumps x half-time / duration: jumps closer than two half-times
FOLLOW_ON_FLAG = 0.35                  # share of jumps smaller than the fade they land on: a split trough
FOLLOW_ON_MIN_JUMPS = 10               # (the 12 h synthetic: 0.03-0.28 with the right half-time, 0.44-0.48
                                       #  with 120 s on 300-600 s troughs)
RESIDUAL_SD_FLAG = 1.5                 # above it the event count is not a trough count


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


def level_sigma(segments, k=LEVEL_CLIP_K, max_iter=LEVEL_CLIP_MAX_ITER):
    """Robust SD of the BACKGROUND about its baseline (pass y minus the floor): the median and
    1.4826 MAD of the samples, recomputed on those within k of these SDs of the median until the SD
    stops moving (iterative sigma clipping). Every sample counts, not just its step from the last,
    so slow coloured noise is measured at its full size; the troughs (one-sided, and far beyond k SDs
    near their onsets) are clipped away, leaving only their small tails to inflate it (x1.2 on the
    white-noise 12 h synthetic). A trace whose MAD is zero (quantised) falls back to its SD."""
    z = np.concatenate([np.asarray(sg, float) for sg in segments] or [np.zeros(0)])
    z = z[np.isfinite(z)]
    if z.size == 0:
        return 0.0
    m = float(np.median(z))
    sd = _MAD_TO_SIGMA * float(np.median(np.abs(z - m)))
    if sd <= 0:
        return float(np.std(z))
    for _ in range(int(max_iter)):
        keep = z[np.abs(z - m) <= k * sd]
        m_new = float(np.median(keep))
        sd_new = _MAD_TO_SIGMA * float(np.median(np.abs(keep - m_new)))
        if sd_new <= 0:
            break
        done = abs(sd_new - sd) <= 1e-4 * sd
        m, sd = m_new, sd_new
        if done:
            break
    return float(sd)


def level_spread(segments, sd):
    """(P97.5 - P2.5) of the samples / (3.92 sd): about 1 when the bulk of the samples scatters like
    Gaussian noise about the floor (troughs only widen it), well below 1 when they fill a band evenly
    -- events back to back with no quiet stretch, which level_sigma then measures instead of noise."""
    z = np.concatenate([np.asarray(sg, float) for sg in segments] or [np.zeros(0)])
    z = z[np.isfinite(z)]
    if z.size == 0 or sd <= 0:
        return float("nan")
    lo, hi = np.percentile(z, [2.5, 97.5])
    return float((hi - lo) / (3.92 * sd))


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
    sigma_level: float = 0.0      # robust SD of the background about its baseline (level_sigma), stored units
    noise_scale: str = "level"    # which of sigma / sigma_level is the score's unit and s_min's
    scale: float = 0.0            # that one, stored units: scores = s / scale, s_min = min_jump_sigma * scale
    follow_on_share: float = 0.0  # share of jumps smaller than the fade they land on (a split-trough flag)
    level_spread: float = float("nan")   # (P97.5 - P2.5) / (3.92 sigma_level): < LEVEL_SPREAD_FLAG, no quiet background
    n_jumps: int = 0
    n_runs_starting_above_min_jump: int = 0
    estimate_note: object = None  # why the recovery could not be estimated (None when it was, or was given)
    estimate_on_edge: bool = False
    warnings: List[str] = field(default_factory=list)

    @property
    def ar_coefficients(self):
        return ar_coefficients(self.decay, self.rise)


def _fit_segments(segments, decay, rise, s_min, sigma, b, max_iter, window=None, tol_sigma=None):
    """Deconvolve each finite segment around the baseline b, refining it until it moves by less than
    BASELINE_TOL_SIGMA * sigma (at most `max_iter` fits).

    window None: b is ONE constant shared by the segments, refined as mean(y - c) (the paper).
    window = w samples: b is a list of per-segment arrays, refined as the centred rolling mean of
    y - c over w samples (adaptation 6b) — the same update, local.
    Converged: the constant moves by at most BASELINE_TOL_SIGMA * sigma; the running curve's MEAN per-sample
    step is at most RUNNING_BASELINE_TOL_SIGMA * sigma (its largest step shrinks only 0.5-0.8x per pass, so
    the old per-sample-max test at 0.001 sigma never passed in 10, while the jumps had stopped changing after
    the first or second). `tol_sigma` overrides both.
    Returns (cs, ss, b, n_iter, converged, rss)."""
    if tol_sigma is None:
        tol_sigma = BASELINE_TOL_SIGMA if window is None else RUNNING_BASELINE_TOL_SIGMA
    tol = tol_sigma * sigma
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
            moved = float(np.mean(np.concatenate([np.abs(bn - bb) for bn, bb in zip(b_new, b)])))
        if moved <= tol:
            converged = True
            break
        b = b_new
    bs = b if window is None else np.concatenate(b)
    rss = float(np.sum((ys - bs - np.concatenate(cs)) ** 2))
    return cs, ss, b, n_iter, converged, rss


def _truncate(segments, max_samples, floors=None):
    """The longest segments (cut to fit) up to `max_samples` in all, with their floors when given."""
    order = sorted(range(len(segments)), key=lambda i: len(segments[i]), reverse=True)
    out, fl, left = [], [], int(max_samples)
    for i in order:
        if left <= 1:
            break
        out.append(segments[i][:left])
        if floors is not None:
            fl.append(floors[i][:left])
        left -= len(out[-1])
    return out, (fl if floors is not None else None)


def jump_penalty(n_samples):
    """The cost of one more jump in the refinement's criterion, in units of sigma^2: BIC's ln(T) per
    parameter, two parameters per jump (where and how big)."""
    return 2.0 * float(np.log(max(int(n_samples), 2)))


def refine_decay(segments, decay0, rise, s_min, sigma, fs, floors=None, window=None):
    """The paper's second step, guarded: the half-time minimising a PENALISED fit criterion,

        RSS / sigma^2 + jump_penalty(T) * n_jumps            (BIC-like),

    not the RSS at the fixed s_min. The plain RSS keeps falling as the half-time shortens -- a short
    fade lets a rash of small jumps follow every wiggle the detrend left -- so on a detrended trough
    train it chose 48 s for a true 300 s (740 events for 30 troughs); every jump must now pay for
    itself. The fit is the real one: the running baseline (`floors`, `window`) when the block uses it.

    Searched in log half-time on a coarse grid from a third to three times the autocovariance guess
    (the criterion is bumpy far from the truth); when the best grid point is an EDGE the grid is
    recentred on it (up to REFINE_MAX_SHIFTS times, never below two samples nor above a quarter of the
    longest segment), then a bounded scalar search between the best point's neighbours. At most
    REFINE_MAX_SAMPLES samples (the longest segments). A rise is kept fixed.

    Returns (decay, info) with info = {"on_edge": the best still lay on the grid's edge, "shifts": n}."""
    from scipy.optimize import minimize_scalar

    segs, fls = _truncate(segments, REFINE_MAX_SAMPLES, floors)
    T = sum(len(g) for g in segs)
    pen = jump_penalty(T)
    if fls is None:
        b0 = float(np.percentile(np.concatenate(segs), BASELINE_PERCENTILE))
    else:
        b0 = fls
    h0 = half_time_from_decay(decay0, fs)
    log_lo = np.log(2.0 / fs)                                  # a fade shorter than two samples is not a fade
    log_hi = np.log(max(4.0 / fs, max(len(g) for g in segs) / (4.0 * fs)))
    cache = {}

    def crit(log_h):
        key = round(float(log_h), 9)
        if key not in cache:
            d = decay_from_half_time(float(np.exp(log_h)), fs)
            if rise >= d:
                cache[key] = np.inf
            else:
                _, ss, _, _, _, rss = _fit_segments(segs, d, rise, s_min, sigma, b0, REFINE_BASELINE_ITER,
                                                    window=window, tol_sigma=0.0)
                n_jumps = sum(int(np.count_nonzero(si[1:] > 0)) for si in ss)
                cache[key] = rss / (sigma * sigma) + pen * n_jumps
        return cache[key]

    width = np.log(9.0)                                         # a third to three times
    centre = float(np.clip(np.log(h0), log_lo + width / 2, log_hi - width / 2)) if log_hi - log_lo > width         else (log_lo + log_hi) / 2
    shifts = 0
    while True:
        a, b = max(log_lo, centre - width / 2), min(log_hi, centre + width / 2)
        grid = np.linspace(a, b, REFINE_GRID)
        vals = np.array([crit(g) for g in grid])
        k = int(np.argmin(vals))
        low_edge = k == 0 and a > log_lo + 1e-9
        high_edge = k == len(grid) - 1 and b < log_hi - 1e-9
        if not (low_edge or high_edge) or shifts >= REFINE_MAX_SHIFTS:
            break
        centre = float(grid[k])
        shifts += 1
    on_edge = bool(low_edge or high_edge)
    lo, hi = grid[max(k - 1, 0)], grid[min(k + 1, len(grid) - 1)]
    best = minimize_scalar(crit, bounds=(lo, hi), method="bounded", options={"xatol": 1e-3})
    log_h = float(best.x) if best.fun <= vals[k] else float(grid[k])
    return decay_from_half_time(float(np.exp(log_h)), fs), {"on_edge": on_edge, "shifts": shifts}


def _warnings(n_jumps, half_s, duration_s, residual_sd, converged, n_iter, n_low, min_jump_sigma, on_edge,
              follow_on=0.0, flat_level=None):
    """The plain-language flags that ride in meta and the summary (F1, F3, F5, F7, and the follow-on share)."""
    out = []
    hours = duration_s / 3600.0
    rate = n_jumps / hours if hours > 0 else 0.0
    occupancy = n_jumps * half_s / duration_s if duration_s > 0 else 0.0
    if n_jumps and (rate > PLAUSIBLE_JUMPS_PER_HOUR or occupancy > MAX_JUMP_OCCUPANCY):
        out.append(f"{n_jumps:,} jumps in {hours:.1f} h ({rate:.0f}/h) with a {half_s:.0f} s recovery half-time: "
                   f"the jumps come faster than they recover, so the fit is explaining slow structure as a rash of "
                   f"small jumps; set recovery_half_s from the recording's own troughs")
    elif n_jumps >= FOLLOW_ON_MIN_JUMPS and follow_on > FOLLOW_ON_FLAG:
        out.append(f"{follow_on:.0%} of the {n_jumps:,} jumps are follow-ons, smaller than the fade they land on: "
                   f"the troughs recover slower than the {half_s:.0f} s recovery half-time, so each is split into a "
                   f"jump and its follow-ons; set recovery_half_s from the recording's own troughs")
    if flat_level is not None:
        out.append(f"the samples fill a band evenly instead of scattering like noise about a floor (spread "
                   f"{flat_level:.2f} < {LEVEL_SPREAD_FLAG:g}): events fill the trace with no quiet stretch between "
                   f"them, so sigma_level measures the events and the jump threshold rises toward them; try "
                   f"noise_scale = diff and read its residual SD")
    if on_edge:
        out.append(f"the estimated recovery half-time ({half_s:.0f} s) sits on the edge of the search even after "
                   f"widening it, so the estimate is not trustworthy; set recovery_half_s")
    if residual_sd > RESIDUAL_SD_FLAG:
        out.append(f"residual SD {residual_sd:.2f} > {RESIDUAL_SD_FLAG:g}: the events are not a sudden drop "
                   f"followed by an exponential recovery with this half-time (a sharkfin's plateau and slow climb "
                   f"are split into many small events), so the event count is not a trough count")
    if not converged:
        out.append(f"baseline not converged after {n_iter} passes")
    if n_low:
        out.append(f"{n_low} run{'s' if n_low != 1 else ''} start{'s' if n_low == 1 else ''} at a level above "
                   f"{min_jump_sigma:g} noise SDs after a NaN gap (a drop at the first sample after a gap is that "
                   f"run's initial level, not a jump, and is not scored)")
    return out


def _fallback_or_raise(err, segments, bounds, y, finite, fs, rise, s_min, sigma, window, floor0):
    """F2: the recovery cannot be estimated (no slow events, or drift). Fit at FALLBACK_HALF_S: if that
    finds no jump either, the channel is quiet and the decay is returned with a note saying why (the
    scores will be all zero); otherwise the estimate is needed and the original error stands."""
    decay = decay_from_half_time(FALLBACK_HALF_S, fs)
    if rise >= decay:
        raise err
    b0 = float(np.percentile(y[finite], BASELINE_PERCENTILE)) if window is None \
        else [floor0[a:e] for a, e in bounds]
    ss = _fit_segments(segments, decay, rise, s_min, sigma, b0, BASELINE_MAX_ITER, window=window)[1]
    n = sum(int(np.count_nonzero(si[1:] > 0)) for si in ss)
    if n:
        raise ValueError(f"{err} (A fit at a {FALLBACK_HALF_S:g} s recovery finds {n} jumps, so there is "
                         f"something to explain and the recovery matters.)") from err
    return decay, str(err).replace("detection.deconvolve: ", "")


def deconvolve(x, fs, polarity="drop", recovery_half_s=0.0, rise_s=0.0, min_jump_sigma=3.0,
               baseline_window_s=0.0, noise_scale="level"):
    """Thresholded OASIS on a whole span, with the adaptations named in the module docstring.
    `baseline_window_s` > 0 makes the baseline a slowly varying curve (adaptation 6b); 0 is the
    paper's one constant per span. `noise_scale` picks the unit of the score and of min_jump_sigma:
    'level' (sigma_level, the background's own SD) or 'diff' (sigma, from first differences)."""
    if polarity not in POLARITIES:
        raise ValueError(f"detection.deconvolve: polarity must be one of {POLARITIES}, got {polarity!r}")
    if noise_scale not in NOISE_SCALES:
        raise ValueError(f"detection.deconvolve: noise_scale must be one of {NOISE_SCALES}, got {noise_scale!r}")
    fs = float(fs)
    x = np.asarray(x, dtype=float).ravel()
    sign = -1.0 if polarity == "drop" else 1.0
    y = sign * x
    finite = np.isfinite(y)
    bounds = _finite_segments(finite)
    if not bounds:
        raise ValueError("detection.deconvolve: the span holds no finite sample.")
    window = None
    floor0 = None
    segments = [y[a:b] for a, b in bounds]
    z_segments = segments
    if baseline_window_s and baseline_window_s > 0:
        window = max(3, int(round(float(baseline_window_s) * fs)))
        floor0 = running_floor(y, window)
        z_segments = [(y - floor0)[a:b] for a, b in bounds]       # for sigma and the recovery estimate

    rise = rise_root(rise_s, fs)
    half_autocov, note, on_edge, est_err = None, None, False, None
    given = bool(recovery_half_s and recovery_half_s > 0)
    if given:
        half_guess = float(recovery_half_s)
    else:
        try:
            decay0, _ = estimate_decay(z_segments, fs)
        except ValueError as err:
            est_err, half_guess = err, FALLBACK_HALF_S
        else:
            half_autocov = half_guess = half_time_from_decay(decay0, fs)

    sigma_diff = noise_sigma(z_segments)
    # sigma_level: the background's robust SD about a running floor -- the baseline's own when it runs,
    # otherwise one LEVEL_WINDOW_HALF_TIMES recoveries long, so drift slower than that is not counted as
    # noise (it stays a misfit of the constant baseline, which the residual SD reports)
    if window is not None:
        level_segments = z_segments
    else:
        lw = max(3, int(round(LEVEL_WINDOW_HALF_TIMES * half_guess * fs)))
        lf = running_floor(y, lw)
        level_segments = [(y - lf)[a:b] for a, b in bounds]
    sigma_level = level_sigma(level_segments)
    spread = level_spread(level_segments, sigma_level)
    sigma = sigma_level if noise_scale == "level" else sigma_diff   # the unit everything below is in
    if sigma <= 0:
        raise ValueError("detection.deconvolve: the span is flat (no noise level, no jumps to measure).")
    s_min = float(min_jump_sigma) * sigma
    if given:
        decay, estimated = decay_from_half_time(recovery_half_s, fs), False
    elif est_err is not None:
        decay, note = _fallback_or_raise(est_err, segments, bounds, y, finite, fs, rise, s_min, sigma, window,
                                         floor0)
        estimated = False
    else:
        if window is None:
            decay, info = refine_decay(z_segments, decay0, rise, s_min, sigma, fs)
        else:
            decay, info = refine_decay(segments, decay0, rise, s_min, sigma, fs,
                                       floors=[floor0[a:e] for a, e in bounds], window=window)
        on_edge = info["on_edge"]
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
    n_jumps = int(np.count_nonzero(scores[np.isfinite(scores)] > 0))
    # F7: a run that begins after a NaN gap (not the span's own first sample, whose level is everything
    # before the span) at a jump-sized level hides a drop absorbed into that run's initial level
    n_low = int(sum(1 for (a, _), v in zip(bounds, initial) if a > 0 and v > float(min_jump_sigma)))
    half_s = half_time_from_decay(decay, fs)
    residual = float(np.sqrt(rss / n_fin) / sigma)
    # follow-ons: jumps smaller than the fitted fade just before them. A trough that recovers slower than
    # the kernel leaves the fit short, and the fit tops itself up with small jumps on the fade's tail;
    # true overlapping troughs do this too, but rarely for most of the jumps
    at = np.flatnonzero(np.nan_to_num(scores) > 0)
    follow_on = float(np.mean(c[at - 1] > s[at])) if at.size else 0.0
    warns = _warnings(n_jumps, half_s, n_fin / fs, residual, converged, n_iter, n_low, float(min_jump_sigma),
                      on_edge, follow_on,
                      spread if noise_scale == "level" and spread < LEVEL_SPREAD_FLAG else None)
    return Deconvolution(
        scores=scores, c=c, s=s, sign=sign, baseline=b, sigma=sigma_diff, decay=decay, rise=rise,
        half_s=half_s, estimated=estimated, half_s_autocov=half_autocov, s_min=s_min,
        n_nan=int((~finite).sum()), n_segments=len(bounds), n_baseline_iter=n_iter,
        baseline_converged=converged, residual_sd_sigma=residual,
        initial_levels=initial, floor=floor, baseline_window_s=float(baseline_window_s or 0.0),
        sigma_level=sigma_level, noise_scale=noise_scale, scale=sigma, follow_on_share=follow_on, level_spread=spread,
        n_jumps=n_jumps, n_runs_starting_above_min_jump=n_low,
        estimate_note=note, estimate_on_edge=on_edge, warnings=warns,
    )
