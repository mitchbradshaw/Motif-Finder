"""
multiscale_entropy.py
=====================
w3-a: a multiscale-entropy curve for every window of a `WindowSet` — a complexity
fingerprint (Costa, Goldberger & Peng 2005, *Multiscale entropy analysis of biological
signals*, Phys. Rev. E 71:021906, DOI 10.1103/PhysRevE.71.021906; refined composite MSE
after Wu, Wu, Lin, Lee & Peng 2014, Phys. Lett. A 378:1369, DOI
10.1016/j.physleta.2014.03.034).

In plain words: sample entropy asks "how surprising is the next value?". Multiscale
entropy blurs the signal more and more — averaging 2, 3, ... many points at a time — and
asks the same question at every blur level. White noise loses its surprise as it is
blurred; a signal with structure at many time-scales keeps it. The shape of the curve is
the fingerprint. It needs hours of signal per curve, so it describes recordings, species
and conditions, not events. Coloured noise has a curve of its own (pink noise's is flat),
so a curve means something only against noise of the same spectrum: the comparison this
block is built to make stable (deterministic, no random draw anywhere).

The algorithm as implemented
----------------------------
1. **Windows** are sliced from `x` (starts are channel-absolute; the bounds rule is the
   shared `Working.types.windowset.span_relative_starts`, promoted from MiniRocket's
   slicer), one window at a time so a few 72 h windows at 10 Hz never sit in memory as
   one matrix. A Window pool (windows on many channels) is refused: a curve needs hours of
   one contiguous signal.
2. **Gaps.** Runs of non-finite samples of at most `max_gap_s` are filled by straight lines
   (an end gap holds the nearest value — `np.interp`) and the window is counted as
   interpolated; a window with a longer run is LEFT OUT (a NaN row), counted with its reason
   (`gap_over_max`). A window with zero spread is left out too (`flat`: r would be 0).
3. **Tolerance** r = `r_frac` x a spread of the window as it arrives (after the gap fill),
   computed ONCE and held fixed across scales, as the authors' `mse.c` does: `r_scale="mad"`
   (default, 1.4826 x the median absolute deviation) or `"sd"` (Costa's standard deviation).
   The block never detrends; a template detrends upstream.
4. **Scales in seconds**, geometric from `scale_min_s` to `scale_max_s` (`n_scales` points);
   tau = max(1, round(scale x fs)), deduplicated; the scale reported is tau / fs, so a 1 Hz
   and a 10 Hz recording mean the same thing.
5. **Coarse-graining** by non-overlapping means (Costa eq. 16), via one cumulative sum.
6. **Sample entropy** (Richman & Moorman 2000, as in `mse.c`): over the first N - m template
   starts, B = pairs whose m-point templates match (Chebyshev distance <= r), A = pairs whose
   (m+1)-point templates match; SampEn = -ln(A / B). Self-matches never count. Counted EXACTLY
   with numba and the sorted-template trick (templates sorted on their first coordinate; a pair
   is compared only while the first coordinates differ by <= r), pinned against a naive O(N^2)
   loop in the tests.
7. **`method`**: `"mse"` — Costa's: SampEn of the offset-0 coarse series. `"rcmse"` (default) —
   at scale tau, the counts of the coarse series at every offset k = 0..tau-1 are POOLED and
   RCMSE = -ln(sum_k A_k / sum_k B_k). This is the restatement in Azami et al. 2017, Med Biol
   Eng Comput (DOI 10.1007/s11517-017-1647-5); **Wu 2014's own equation was not reached** and
   is unverified.
8. **The cost cap** (`max_points`, default 20,000 — Costa's own N): SampEn is O(N^2) in the
   coarse series' length, so the small scales of a long window are the expensive ones (259,200
   points at tau = 1 for 72 h at 1 Hz). Each coarse series is evaluated on at most `max_points`
   templates: when it has more, the templates come from 10 contiguous stretches spread evenly
   across the window (all pairs between them are compared — a template is a template wherever
   it sits), so the estimate still covers the whole window. RCMSE pools only as many offsets
   as keep the work at about `max_points`^2 pairs: n_offsets = min(tau, floor((max_points /
   L)^2)) for a coarse length L, evenly spaced — every offset when the coarse series are short
   (where pooling matters), one when they are already long. Every scale therefore costs about
   the same and is estimated from about the same number of pairs. Departure from the papers,
   named: they use every template and every offset; the cap is ours, for cost.
9. **Undefined is NaN, never extrapolated**: a scale whose coarse series is shorter than
   `min_coarse_len` (default 1,000, Costa section VI) is NaN (`too_short`); a scale with no
   m-match or no (m+1)-match is NaN (`no_m_match` / `no_m1_match`). Each counted per scale.
10. **Collapse guard.** When r is many times larger than the step a coarse value typically
   takes, nearly every template match extends to the next point and the entropy collapses
   towards 0 for a reason that is not surprise — drift or a few outliers inflated the spread
   r was taken from (Costa App. B; the probable cause of the sqrt(t) preprint's "mean MSE
   0.0028"). Rule: rho = r / (1.4826 x the median absolute deviation of the coarse series'
   first differences); rho > `collapse_ratio` flags that window at that scale. The step is
   measured at the scale judged (wave-1 lesson), robustly, so the events cannot raise it. The
   value is kept and flagged, never blanked; `meta["collapse"]` counts per scale. The default 4
   is a measurement, not the paper's: on synthetic AR(1) (phi 0.95, 0.99), random walks and
   drifting versions of them, every scale with rho near 4 had entropy 0.10-0.14 nats and every
   scale beyond it less — the curve's floor, whatever the signal — while detrended AR(1) sat at
   rho 0.2-1.1. A random walk detrended over 2 h still wanders by several steps and flags its
   1 s scale (rho 4.2; 6.5 under a 6 h detrend): that is the guard working (r there is the
   wander's, not the noise's).
   The guard does not use the global match fraction B / pairs: under drift that stays small
   (templates far apart in time sit at different levels) while A / B -> 1.
11. **Drift share** per window (`mse_drift_share`): the variance share of a least-squares
   straight line, 1 - var(residual) / var(window). Near 1: the window is mostly a ramp and
   an SD-based r is mostly the ramp's.

Columns added per window: `mse_<scale>s` per scale (the name formats tau / fs with up to 4
significant digits — stable for a given parameter set and fs); `mse_ci` (complexity index:
the SUM of the entropies over the scales defined in EVERY kept window of the set; NaN, loud,
when there is none); `mse_slope_small` / `mse_slope_large` (least-squares slope of entropy
against log10 of the scale in seconds over the lower floor(n/2) and the upper remaining
scales of those same common scales — Costa Fig. 8's two slopes, per tenfold of seconds; NaN
with fewer than 2 points in a half); `mse_r` (the tolerance, in the signal's stored units);
`mse_n_scales` (defined scales in this window); `mse_drift_share`; `mse_n_collapsed`.
Upstream features pass through; earlier `mse_*` columns are replaced and said so.

Why not extend `preprocessing.window_matrix`: its entropy families are single-scale
(`Working/Detection/analysis/entropy_analysis.py:163`, a SampEn that also counts its m- and
(m+1)-templates over different template sets), they are RQ1's feature arm, and changing them
would move RQ1's numbers and every saved window-matrix recipe hash. This block is a separate
WindowSet -> WindowSet step that leaves them untouched.

Cancellation: `should_cancel()` is checked before every window; on True the run raises
`Working.execution.RecipeCancelled` (imported inside the function: execution imports the
adapters' registry). `on_progress(done, total, "multiscale_entropy")` fires once per window.

No UI imports; numba compiles the counting kernel on first use (`warm_up()` pays that once).
"""

import math
import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from numba import njit

from Working.types.windowset import WindowSet, span_relative_starts

METHODS = ("rcmse", "mse")
R_SCALES = ("mad", "sd")
DEFAULT_METHOD = "rcmse"
DEFAULT_M = 2
DEFAULT_R_FRAC = 0.15            # Costa 2005
DEFAULT_R_SCALE = "mad"
DEFAULT_SCALE_MIN_S = 1.0
DEFAULT_SCALE_MAX_S = 1200.0     # 20 min
DEFAULT_N_SCALES = 12
DEFAULT_MIN_COARSE_LEN = 1000    # Costa section VI: 2 x 10^4 points kept 10^3 at scale 20
DEFAULT_MAX_POINTS = 20_000      # Costa's N
DEFAULT_MAX_GAP_S = 30.0         # placeholder
DEFAULT_COLLAPSE_RATIO = 4.0
N_STRETCHES = 10
MAX_CURVES = 64
MAD_K = 1.4826
STAGE = "multiscale_entropy"
PREFIX = "mse_"

LEFT_OUT_GAP = "gap_over_max"
LEFT_OUT_FLAT = "flat"
UNDEF_SHORT = "too_short"
UNDEF_NO_M = "no_m_match"
UNDEF_NO_M1 = "no_m1_match"


def _rules(m, r_frac, r_scale, min_coarse_len, max_points, collapse_ratio, max_gap_s, method):
    spread = ("1.4826 x the median absolute deviation (robust to outliers and to the events)" if r_scale == "mad"
              else "the standard deviation (Costa's)")
    how = ("refined composite (RCMSE): the template-match counts of the coarse series at every offset are pooled "
           "before the log (Wu et al. 2014 as restated by Azami et al. 2017; Wu's own equation was not reached)"
           if method == "rcmse" else "Costa 2005: sample entropy of the coarse series starting at the first sample")
    return [
        {"name": "entropy", "rule": f"sample entropy, m = {m}: -ln(A / B), B = pairs of {m}-point templates within r "
                                    f"(largest difference), A = pairs of {m + 1}-point templates within r, over the "
                                    f"first N - {m} templates, no self-matches. Method: {how}"},
        {"name": "scale", "rule": "the signal averaged over non-overlapping blocks of tau samples (Costa eq. 16); "
                                  "the scale shown is tau / fs seconds"},
        {"name": "r", "rule": f"r = {r_frac:g} x {spread} of the window as it arrives, computed once and held fixed "
                              "across every scale (the authors' mse.c); in the signal's stored units. This block "
                              "never detrends"},
        {"name": "undefined", "rule": f"a scale whose averaged series is shorter than {min_coarse_len:,} points is "
                                      "blank (too short, never extrapolated); so is a scale with no template match "
                                      "(no m-match / no m+1-match)"},
        {"name": "cost cap", "rule": f"each averaged series is scored on at most {max_points:,} templates, taken "
                                     f"from {N_STRETCHES} stretches spread across the window; RCMSE pools only as "
                                     f"many offsets as keep the work near {max_points:,}^2 pairs (all of them when "
                                     "the averaged series are short)"},
        {"name": "collapse", "rule": f"flagged when r is more than {collapse_ratio:g} x the step an averaged value "
                                    "typically takes (1.4826 x the median absolute deviation of its first "
                                    "differences): nearly every match then extends, and the entropy falls towards 0 "
                                    "because drift or outliers inflated r, not because the signal is regular. The "
                                    "value is kept, flagged"},
        {"name": "complexity index", "rule": "the sum of the entropies over the scales defined in every kept window "
                                             "of the set (the count is shown)"},
        {"name": "slopes", "rule": "least-squares slope of entropy against log10(scale in seconds), over the lower "
                                   "and the upper half of those common scales (Costa Fig. 8's two slopes); "
                                   "per tenfold of scale"},
        {"name": "drift share", "rule": "the share of the window's variance a straight line explains, 1 - "
                                        "var(residual) / var(window): near 1 the window is mostly a ramp"},
        {"name": "gaps", "rule": f"missing samples in runs of at most {max_gap_s:g} s are bridged by straight lines; "
                                 "a window with a longer run is left out (a blank row), counted"},
    ]


# ── the counting kernel ─────────────────────────────────────────────────────

@njit(cache=True, nogil=True)
def _count_sorted(y, starts, m, r):
    """Exact (A, B) over the templates at `starts`, which are sorted by their first value."""
    n = starts.shape[0]
    a_count = 0
    b_count = 0
    for a in range(n):
        i = starts[a]
        yi = y[i]
        for b in range(a + 1, n):
            j = starts[b]
            if y[j] - yi > r:
                break
            ok = True
            for k in range(1, m):
                if abs(y[i + k] - y[j + k]) > r:
                    ok = False
                    break
            if ok:
                b_count += 1
                if abs(y[i + m] - y[j + m]) <= r:
                    a_count += 1
    return a_count, b_count


def warm_up():
    """Compile (or load) the numba kernel; untimed in the cost calibration."""
    y = np.random.default_rng(0).standard_normal(64)
    sampen_counts(y, 2, 0.2)


def template_starts(L, m, max_points=None):
    """Template start indices of a series of length `L` (each start + m < L): all `L - m` of them,
    or at most `max_points` taken from `N_STRETCHES` contiguous stretches spread evenly."""
    n_t = int(L) - int(m)
    if n_t <= 0:
        return np.empty(0, dtype=np.int64)
    if max_points is None or n_t <= int(max_points):
        return np.arange(n_t, dtype=np.int64)
    seg = max(1, int(max_points) // N_STRETCHES)
    firsts = np.round(np.linspace(0, n_t - seg, N_STRETCHES)).astype(np.int64)
    return np.unique((firsts[:, None] + np.arange(seg, dtype=np.int64)[None, :]).ravel())


def sampen_counts(y, m, r, starts=None):
    """`(A, B)`: exact pair counts of (m+1)- and m-point template matches (Chebyshev <= r) among the
    templates starting at `starts` (default: all N - m)."""
    y = np.ascontiguousarray(y, dtype=np.float64)
    if starts is None:
        starts = template_starts(len(y), m)
    starts = np.asarray(starts, dtype=np.int64)
    if len(starts) < 2:
        return 0, 0
    order = np.argsort(y[starts], kind="mergesort")
    a, b = _count_sorted(y, np.ascontiguousarray(starts[order]), int(m), float(r))
    return int(a), int(b)


def coarse_offsets(x, tau, offsets):
    """The coarse-grained series of `x` at scale `tau` for each offset (non-overlapping means)."""
    x = np.asarray(x, dtype=np.float64)
    c = np.concatenate(([0.0], np.cumsum(x - np.median(x))))
    out = []
    for k in offsets:
        n_k = (len(x) - int(k)) // int(tau)
        idx = int(k) + int(tau) * np.arange(n_k + 1)
        out.append(np.diff(c[idx]) / float(tau))
    return out


def coarse_grain(x, tau, offset=0):
    return coarse_offsets(x, tau, [offset])[0]


def n_offsets_for(tau, L, max_points):
    """RCMSE offsets pooled at scale `tau` for a coarse length `L` under the cost cap."""
    if max_points is None or L <= 0:
        return int(tau)
    return int(min(int(tau), max(1, math.floor((float(max_points) / float(L)) ** 2))))


def step_scale(y):
    """1.4826 x the median absolute deviation of the first differences of `y`."""
    d = np.diff(np.asarray(y, dtype=float))
    if len(d) == 0:
        return float("nan")
    return float(MAD_K * np.median(np.abs(d - np.median(d))))


def spread(w, r_scale):
    w = np.asarray(w, dtype=float)
    if r_scale == "sd":
        return float(np.std(w))
    if r_scale == "mad":
        return float(MAD_K * np.median(np.abs(w - np.median(w))))
    raise ValueError(f"r_scale must be one of {R_SCALES}, not {r_scale!r}")


def drift_share(w):
    w = np.asarray(w, dtype=float)
    v = float(np.var(w))
    if len(w) < 3 or v <= 0:
        return float("nan")
    tt = np.arange(len(w), dtype=float)
    coef = np.polyfit(tt, w, 1)
    return float(max(0.0, 1.0 - np.var(w - np.polyval(coef, tt)) / v))


def scale_taus(fs, scale_min_s, scale_max_s, n_scales):
    """`(taus, scales_s)`: geometric scales in seconds as integer block sizes, deduplicated."""
    if not (scale_min_s > 0 and scale_max_s >= scale_min_s):
        raise ValueError(f"scales must satisfy 0 < scale_min_s <= scale_max_s; got {scale_min_s:g} and "
                         f"{scale_max_s:g} s")
    n = max(1, int(n_scales))
    req = np.geomspace(float(scale_min_s), float(scale_max_s), n) if n > 1 else np.array([float(scale_min_s)])
    taus = np.unique(np.maximum(1, np.round(req * float(fs))).astype(np.int64))
    return taus, taus / float(fs)


def scale_label(scale_s):
    s = float(f"{float(scale_s):.4g}")
    return f"{PREFIX}{int(s)}s" if s == int(s) else f"{PREFIX}{s:g}s"


def entropy_at_scale(x, tau, m, r, method=DEFAULT_METHOD, min_coarse_len=DEFAULT_MIN_COARSE_LEN,
                     max_points=DEFAULT_MAX_POINTS, collapse_ratio=DEFAULT_COLLAPSE_RATIO):
    """One scale of one window: a dict with `value` (NaN when undefined), `reason`, `A`, `B`,
    `n_offsets`, `n_templates`, `rho` and `collapsed`."""
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}, not {method!r}")
    N = len(x)
    L = N // int(tau)
    out = {"value": float("nan"), "reason": None, "A": 0, "B": 0, "n_offsets": 0, "n_templates": 0,
           "rho": float("nan"), "collapsed": False, "coarse_len": int(L)}
    if L < max(int(min_coarse_len), int(m) + 2):
        out["reason"] = UNDEF_SHORT
        return out
    if method == "mse":
        offsets = [0]
    else:
        n_off = n_offsets_for(tau, min(L, max_points) if max_points else L, max_points)
        offsets = np.unique(np.floor(np.arange(n_off) * (float(tau) / n_off)).astype(np.int64)).tolist()
    series = coarse_offsets(x, tau, offsets)
    A = B = n_t = 0
    for y in series:
        st = template_starts(len(y), m, max_points)
        a, b = sampen_counts(y, m, r, st)
        A += a
        B += b
        n_t += len(st)
    step = step_scale(series[0])
    rho = float("inf") if step == 0 else float(r) / step
    out.update(A=int(A), B=int(B), n_offsets=len(offsets), n_templates=int(n_t), rho=rho,
               collapsed=bool(rho > float(collapse_ratio)))
    if B == 0:
        out["reason"] = UNDEF_NO_M
    elif A == 0:
        out["reason"] = UNDEF_NO_M1
    else:
        out["value"] = float(-np.log(A / B))
    return out


def fill_gaps(w, max_gap):
    """`(w_filled, n_missing, longest_run)`: runs of non-finite samples bridged linearly when every
    run is at most `max_gap` samples; otherwise `w_filled` is None."""
    w = np.asarray(w, dtype=float)
    bad = ~np.isfinite(w)
    n_bad = int(bad.sum())
    if n_bad == 0:
        return w, 0, 0
    if n_bad == len(w):
        return None, n_bad, n_bad
    edges = np.diff(np.concatenate(([0], bad.view(np.int8), [0])))
    run_starts = np.flatnonzero(edges == 1)
    run_ends = np.flatnonzero(edges == -1)
    longest = int((run_ends - run_starts).max())
    if longest > int(max_gap):
        return None, n_bad, longest
    idx = np.arange(len(w))
    out = w.copy()
    out[bad] = np.interp(idx[bad], idx[~bad], w[~bad])
    return out, n_bad, longest


def window_curve(w, fs, taus, m=DEFAULT_M, r_frac=DEFAULT_R_FRAC, r_scale=DEFAULT_R_SCALE,
                 method=DEFAULT_METHOD, min_coarse_len=DEFAULT_MIN_COARSE_LEN, max_points=DEFAULT_MAX_POINTS,
                 collapse_ratio=DEFAULT_COLLAPSE_RATIO):
    """The curve of one gap-free window: `{"r", "drift_share", "scales": [entropy_at_scale dicts]}`."""
    w = np.asarray(w, dtype=float)
    r = float(r_frac) * spread(w, r_scale)
    scales = [entropy_at_scale(w, int(tau), m, r, method, min_coarse_len, max_points, collapse_ratio)
              for tau in taus]
    return {"r": r, "drift_share": drift_share(w), "scales": scales}


def mse_curve(x, fs=1.0, scale_min_s=DEFAULT_SCALE_MIN_S, scale_max_s=DEFAULT_SCALE_MAX_S,
              n_scales=DEFAULT_N_SCALES, **kw):
    """`(scales_s, values)` for one series — a convenience for checks and notebooks."""
    taus, scales_s = scale_taus(fs, scale_min_s, scale_max_s, n_scales)
    c = window_curve(x, fs, taus, **kw)
    return scales_s, np.array([s["value"] for s in c["scales"]])


def predicted_pairs(window_samples, taus, method=DEFAULT_METHOD, m=DEFAULT_M, min_coarse_len=DEFAULT_MIN_COARSE_LEN,
                    max_points=DEFAULT_MAX_POINTS):
    """The template pairs one window of `window_samples` costs (sum over defined scales and pooled
    offsets of T^2 / 2) — the cost model's unit. The share of them actually compared (the sorted
    trick's candidates within r) depends on the data and is what calibration measures."""
    total = 0.0
    for tau in taus:
        L = int(window_samples) // int(tau)
        if L < max(int(min_coarse_len), int(m) + 2):
            continue
        T = min(L - int(m), int(max_points)) if max_points else L - int(m)
        n_off = 1 if method == "mse" else n_offsets_for(int(tau), min(L, max_points) if max_points else L, max_points)
        total += n_off * T * T / 2.0
    return total


# ── the block ───────────────────────────────────────────────────────────────

@dataclass
class Fingerprint:
    windows: object
    meta: dict = field(default_factory=dict)


def _slope(scales_s, vals):
    if len(vals) < 2:
        return float("nan")
    return float(np.polyfit(np.log10(scales_s), vals, 1)[0])


def _is_pool(ws):
    feats = ws.features
    return feats is not None and any(str(c).startswith("pool_") for c in feats.columns)


def _nanmedian_cols(M, n_cols):
    """Column medians over the finite values; NaN for a column with none (a blank scale is the answer)."""
    out = np.full(n_cols, np.nan)
    for j in range(n_cols):
        col = M[:, j] if len(M) else np.empty(0)
        col = col[np.isfinite(col)]
        if len(col):
            out[j] = float(np.median(col))
    return out


def _json_list(a):
    return [None if not np.isfinite(v) else round(float(v), 6) for v in np.asarray(a, dtype=float)]


def multiscale_entropy(ws, x, t, fs, m=DEFAULT_M, r_frac=DEFAULT_R_FRAC, r_scale=DEFAULT_R_SCALE,
                       method=DEFAULT_METHOD, scale_min_s=DEFAULT_SCALE_MIN_S, scale_max_s=DEFAULT_SCALE_MAX_S,
                       n_scales=DEFAULT_N_SCALES, min_coarse_len=DEFAULT_MIN_COARSE_LEN,
                       max_points=DEFAULT_MAX_POINTS, max_gap_s=DEFAULT_MAX_GAP_S,
                       collapse_ratio=DEFAULT_COLLAPSE_RATIO, seed=0, should_cancel=None, on_progress=None):
    """The block: every window of `ws` gets its multiscale-entropy curve and summaries. Returns a
    `Fingerprint(windows, meta)`; the windows are the same (left-out ones as NaN rows)."""
    t_start = time.perf_counter()
    if ws is None:
        raise ValueError("Multiscale entropy needs a WindowSet from a prior step: put Sliding windows before it")
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}, not {method!r}")
    if r_scale not in R_SCALES:
        raise ValueError(f"r_scale must be one of {R_SCALES}, not {r_scale!r}")
    if _is_pool(ws):
        raise ValueError("these are the windows of a Window pool, spread over many channels: a multiscale-entropy "
                         "curve needs hours of ONE contiguous signal. Use Sliding windows on a recording instead")
    if x is None:
        raise ValueError("Multiscale entropy slices its windows from the signal, and no signal was given")
    n_in = int(ws.n_windows)
    if n_in == 0:
        raise ValueError("the window set is empty: there is nothing to measure")
    x = np.asarray(x, dtype=float)
    fs = float(fs)
    L = int(ws.length)
    rel = span_relative_starts(ws, len(x), t, fs, block="Multiscale entropy")
    taus, scales_s = scale_taus(fs, scale_min_s, scale_max_s, n_scales)
    n_sc = len(taus)
    max_gap = int(round(float(max_gap_s) * fs))

    E = np.full((n_in, n_sc), np.nan)
    R = np.full(n_in, np.nan)
    D = np.full(n_in, np.nan)
    collapsed = np.zeros((n_in, n_sc), dtype=bool)
    reasons = {UNDEF_SHORT: np.zeros(n_sc, int), UNDEF_NO_M: np.zeros(n_sc, int), UNDEF_NO_M1: np.zeros(n_sc, int)}
    rho = np.full((n_in, n_sc), np.nan)
    n_offsets = np.zeros(n_sc, dtype=int)
    n_templates = np.zeros(n_sc, dtype=int)
    left = {LEFT_OUT_GAP: 0, LEFT_OUT_FLAT: 0}
    kept = np.zeros(n_in, dtype=bool)
    n_interp = 0
    longest_gap = 0

    for i in range(n_in):
        if should_cancel is not None and should_cancel():
            from Working.execution import RecipeCancelled
            raise RecipeCancelled(f"Multiscale entropy cancelled after {i:,} of {n_in:,} windows")
        w, n_bad, longest = fill_gaps(x[rel[i]:rel[i] + L], max_gap)
        longest_gap = max(longest_gap, longest)
        if w is None:
            left[LEFT_OUT_GAP] += 1
        elif spread(w, r_scale) <= 0:
            left[LEFT_OUT_FLAT] += 1
        else:
            n_interp += int(n_bad > 0)
            c = window_curve(w, fs, taus, m, r_frac, r_scale, method, min_coarse_len, max_points, collapse_ratio)
            kept[i] = True
            R[i] = c["r"]
            D[i] = c["drift_share"]
            for j, s in enumerate(c["scales"]):
                E[i, j] = s["value"]
                rho[i, j] = s["rho"]
                collapsed[i, j] = s["collapsed"] and np.isfinite(s["value"])
                if s["reason"]:
                    reasons[s["reason"]][j] += 1
                n_offsets[j] = max(n_offsets[j], s["n_offsets"])
                n_templates[j] = max(n_templates[j], s["n_templates"])
        if on_progress is not None:
            on_progress(i + 1, n_in, STAGE)

    n_kept = int(kept.sum())
    defined = np.isfinite(E)
    common = np.flatnonzero(defined[kept].all(axis=0)) if n_kept else np.empty(0, dtype=int)
    n_common = len(common)
    lo, hi = common[: n_common // 2], common[n_common // 2:]
    ci = np.full(n_in, np.nan)
    s_small = np.full(n_in, np.nan)
    s_large = np.full(n_in, np.nan)
    for i in np.flatnonzero(kept):
        if n_common:
            ci[i] = float(E[i, common].sum())
        if len(lo) >= 2:
            s_small[i] = _slope(scales_s[lo], E[i, lo])
        if len(hi) >= 2:
            s_large[i] = _slope(scales_s[hi], E[i, hi])

    names = [scale_label(s) for s in scales_s]
    cols = {nm: E[:, j] for j, nm in enumerate(names)}
    n_scales_col = np.where(kept, defined.sum(axis=1), np.nan)
    n_coll_col = np.where(kept, collapsed.sum(axis=1), np.nan)
    cols.update({f"{PREFIX}ci": ci, f"{PREFIX}slope_small": s_small, f"{PREFIX}slope_large": s_large,
                 f"{PREFIX}r": R, f"{PREFIX}n_scales": n_scales_col, f"{PREFIX}drift_share": D,
                 f"{PREFIX}n_collapsed": n_coll_col})
    table = pd.DataFrame(cols)
    warnings = []
    if ws.features is not None:
        upstream = ws.features.reset_index(drop=True)
        old = [c for c in upstream.columns if str(c).startswith(PREFIX)]
        if old:
            upstream = upstream.drop(columns=old)
            warnings.append(f"the window set already carried {len(old):,} {PREFIX}* columns (an earlier "
                            "Multiscale entropy step); they were replaced by this step's")
        table = pd.concat([upstream, table], axis=1)
    out = WindowSet(starts=np.asarray(ws.starts, dtype=np.int64), length=L, fs=float(ws.fs), features=table)

    # ── honesty on the face ──
    n_left = n_in - n_kept
    n_def = defined[kept].sum(axis=0) if n_kept else np.zeros(n_sc, int)
    coll = collapsed[kept].sum(axis=0) if n_kept else np.zeros(n_sc, int)
    never = [float(scales_s[j]) for j in range(n_sc) if n_def[j] == 0]
    if n_kept == 0:
        warnings.append(f"every window was left out ({left[LEFT_OUT_GAP]:,} with a gap over {max_gap_s:g} s, "
                        f"{left[LEFT_OUT_FLAT]:,} flat): there is no curve")
    elif n_common == 0:
        warnings.append("no scale is defined in every window, so there is no complexity index and no slope: "
                        "lengthen the windows, lower scale_max_s, or raise scale_min_s")
    elif n_common < 4:
        warnings.append(f"only {n_common} scale(s) are defined in every window: too few to compare curves or to "
                        "fit both slopes")
    if reasons[UNDEF_SHORT].any():
        reach = L / fs / max(int(min_coarse_len), 1)
        warnings.append(f"{int((reasons[UNDEF_SHORT] > 0).sum())} of {n_sc} scales are blank: a {L / fs / 3600:g} h "
                        f"window keeps {min_coarse_len:,} averaged points only up to about {reach:g} s")
    n_coll_any = int(collapsed[kept].any(axis=1).sum()) if n_kept else 0
    if n_coll_any:
        warnings.append(f"collapse: {n_coll_any:,} of {n_kept:,} windows have a scale where r is over "
                        f"{collapse_ratio:g}x the averaged series' own step — their entropy there is low because r "
                        "was inflated (drift or outliers), not because the signal is regular. Detrend upstream or "
                        "use r_scale = mad")
    if n_left:
        warnings.append(f"{n_left:,} of {n_in:,} windows left out: "
                        + ", ".join(f"{v:,} {k.replace('_', ' ')}" for k, v in left.items() if v))

    # ── the drawing payload: at most MAX_CURVES windows (a seeded sample beyond) plus the median ──
    kept_idx = np.flatnonzero(kept)
    sampled = len(kept_idx) > MAX_CURVES
    show = np.sort(np.random.default_rng(int(seed)).choice(kept_idx, MAX_CURVES, replace=False)) if sampled \
        else kept_idx
    median = _nanmedian_cols(E[kept], n_sc)
    curves = {
        "scales_s": [float(s) for s in scales_s], "n_windows": n_kept, "sampled": bool(sampled), "seed": int(seed),
        "windows": [{"index": int(i), "start_s": float(ws.starts[i]) / float(ws.fs), "values": _json_list(E[i]),
                     "collapsed": [bool(v) for v in collapsed[i]]} for i in show],
        "median": _json_list(median),
        "form": "values[j] is the entropy at scales_s[j]; null where undefined",
    }
    summary = (f"{n_kept:,} of {n_in:,} windows · {n_sc} scales {scales_s[0]:g}–{scales_s[-1]:g} s · "
               f"{n_common} defined in every window · {method.upper()} m={m} r={r_frac:g}×{r_scale.upper()}")
    if n_coll_any:
        summary += f" · collapse in {n_coll_any:,}"
    if n_left:
        summary += f" · {n_left:,} left out"

    meta = {
        "scales_s": [float(s) for s in scales_s], "taus": [int(v) for v in taus], "columns": names,
        "method": method, "m": int(m), "r_frac": float(r_frac), "r_scale": r_scale,
        "r_rule": f"r = {r_frac:g} x {'1.4826 x MAD' if r_scale == 'mad' else 'SD'} of each window, fixed across "
                  "scales, stored units",
        "r_median": float(np.nanmedian(R)) if n_kept else None,
        "min_coarse_len": int(min_coarse_len), "max_points": int(max_points) if max_points else None,
        "n_windows_in": n_in, "n_kept": n_kept, "n_interpolated": int(n_interp), "longest_gap_samples": int(longest_gap),
        "left_out": {k: int(v) for k, v in left.items() if v},
        "defined_per_scale": [int(v) for v in n_def],
        "undefined_per_scale": {k: [int(v) for v in arr] for k, arr in reasons.items()},
        "blank_scales_s": never,
        "collapse": [int(v) for v in coll], "collapse_ratio": float(collapse_ratio),
        "rho_median": _json_list(_nanmedian_cols(rho[kept], n_sc)),
        "n_offsets": [int(v) for v in n_offsets], "n_templates": [int(v) for v in n_templates],
        "ci_scales_s": [float(scales_s[j]) for j in common], "n_ci_scales": int(n_common),
        "slope_small_scales_s": [float(scales_s[j]) for j in lo], "slope_large_scales_s": [float(scales_s[j]) for j in hi],
        "drift_share_median": float(np.nanmedian(D)) if n_kept else None,
        "seconds": round(time.perf_counter() - t_start, 3),
        "warnings": warnings, "summary": summary, "curves": curves,
        "rules": _rules(m, r_frac, r_scale, min_coarse_len, max_points, collapse_ratio, max_gap_s, method),
    }
    return Fingerprint(windows=out, meta=meta)
