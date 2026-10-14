"""
pan.py
======
The pan matrix profile (Madrid F, Imani S, Mercer R, Zimmerman Z, Shakibay N,
Keogh E (2019) Matrix Profile XX: finding and visualizing time series motifs
of all lengths using the matrix profile. ICBK 2019, pp. 175-182): at which
window lengths does anything repeat?

In plain words: the matrix profile says, for every window of the recording,
how far it is from its most similar window elsewhere (after both are
z-normalised, so only the shape counts). It does so for one window length
chosen in advance. This module computes it for a ladder of lengths and stacks
the profiles into a picture: lengths up the side (longest at the top), time
along the bottom, bright where a window has a close look-alike. Then, per
length, it asks the question the picture cannot answer by eye — is the best
repetition at this length better than noise of the same colour manages? —
by computing the same profiles on amplitude-adjusted copies of the span (the
recording's own values, reshuffled so the spectrum is roughly kept and every
shape destroyed).

The algorithm, as implemented
-----------------------------
1. **Lengths.** `n_lengths` lengths from `min_window_s` to `max_window_s`,
   geometric (each a fixed ratio longer than the last), m = round(s x fs),
   deduplicated. A length shorter than stumpy's minimum
   (`Working.config.MP_MIN_WINDOW_SAMPLES`) or longer than half the span is
   dropped and named in `lengths_dropped`. **Choice:** one exact
   `stumpy.stump` per length, not `stumpy.stimp`. stimp's SKIMP visits a
   *linear* ladder (min_m, min_m + step, ...) breadth-first so the picture is
   "anytime"; our question is octave-like (30 s against 1 min against 1 h),
   so a linear ladder spends nearly all its rows on the long lengths, and
   stump's cost is flat in m (the sliding dot product), so each geometric row
   costs the same: one calibrated k x n^2. stimp's `PAN_` is also binarised at
   0.2 by default (stumpy `stimp.py:277/355`) — a picture, not distances — and
   this module never reads it.
2. **Exact only** (fix round 1). The first version offered `percentage` < 1
   (`stumpy.scrump`). scrump draws its diagonal order from numpy's GLOBAL
   random generator; a module lock with the state saved and restored did not
   protect it from another thread's draws (the critic: 20 of 20 runs differed
   beside a thread using `np.random`, and a seeded thread was disturbed 5 of
   5 times), and it saved only about 20 % on the default ladder. Removed:
   every profile is an exact `stumpy.stump`.
3. **Values.** Per window the z-normalised Euclidean distance d to its
   nearest non-trivial neighbour (stumpy's exclusion zone, m/4), normalised
   d / (2 sqrt(m)) and clipped at 1 — **stumpy's rule**
   (`stimp.py:39`, `_normalize_pan`); the paper gives no per-length rule. It
   puts every length on one 0-1 scale: 0 = an identical shape exists, about
   0.71 = what two independent white-noise windows score, 1 = anti-correlated.
   The image holds 1 - that, so **bright = repeated**.
4. **Layout.** Rows long first (row 0 = the longest window — the convention
   of `preprocessing.wavelet_transform`'s low-frequency-first rows, so
   `detection.wavelet_summation`'s `row_from`/`row_to` fractions count from
   the longest length the same way). One column per sample of the span,
   start-aligned: column i holds the window that starts at sample i, so each
   row's last m - 1 columns are NaN (no window starts there).
5. **Gaps and stalls (adaptation).** stumpy cannot score a window touching
   NaN. NaN runs of at most `max_fill_s` are filled by a straight line
   (`Working.Detection.matrix_profiling.snippets.fill_nan`, imported); longer
   runs stay NaN, so every window touching one is NaN in the picture, left
   out of every statistic, and counted per length (`n_windows_nan`). A
   stall — at least `stall_s` (default 60 s, a placeholder) of a held value
   (a stalled logger, a clipped stretch) — is made a long gap too and counted
   (`n_stalled`): a held value, detrended, is a ramp that matches itself
   exactly, and a 3-20 min flatline gave a confident suggestion (gaps 6-125,
   the critic). The block sees what the template's detrend hands it, where a
   held value is no longer constant but a near-straight line, so a stall is
   found by its second differences staying near zero (`stall_mask`,
   `STALL_TOL`), not by equal values (fix round 2: equality never fired
   through the template). It has its own threshold: with `max_fill_s` (5 s)
   a quantised logger lost up to a quarter of its samples. A constant span is reported as "no spread to measure". The
   null copies are built from the filled series and get the same long gaps
   back, so real and null lose the same windows.
6. **Which length repeats — the rule (this module's, not the paper's).**
   Per length, the windows are reduced to *distinct* ones: sort the profile,
   keep a window only if no kept window starts within m samples of it (no two
   kept windows overlap). Let N be how many there are, r_K the mean distance
   of the K = 3 best (three, so one lucky pair cannot carry it — a pair of
   look-alikes always gives two equal low values), and for the null copies
   z_K the same mean and z_med the median distance over their distinct
   windows (each averaged over the draws). The null copies are AAFT
   (`null="aaft"`, the default; `Adapters.preprocessing_surrogate.
   aaft_surrogate`): plain phase randomisation (`null="phase"`, kept for
   comparison) makes the values bell-shaped, and a lopsided recording with no
   structure (exp of an AR(1)) then out-repeats its copies at every length —
   a suggestion in 10 of 10 seeds at 1 and at 20 draws (the critic). Null
   copies are drawn only for lengths that can be judged. Then

       gap = N^(1/3) x ln(z_K / r_K) / ln(z_med / z_K)

   — how far the real recording's best look-alikes reach beyond noise's best,
   in units of how far noise's best reach beyond its typical window (the
   null's spread), measured as ratios because a distance is bounded below by
   0 and a clean repeat's distance shrinks by factors (0.03 against noise's
   0.08 is far, though only 0.05 apart); times N^(1/3) because with fewer
   distinct windows the best few vary more by chance. The exponent is
   measured, not derived: the null's spread of the ratio falls with N, but
   more slowly than 1/sqrt(N) on short windows (a 30 s window at 0.5 Hz is 15
   samples, and z-normalising 15 samples is itself noisy) — with sqrt(N), 30 s
   at 0.5 Hz gave false suggestions on pink noise. A length is **judged** only
   when the span is at least `MIN_WINDOWS` windows long (fewer and it is "too
   long to judge on this span"; only usable samples count — long gaps and
   stalls are not span: a gap-free 4 h span judges up to 17 min, 8 h up to
   34 min, 24 h up to 1 h 43 min); it **clears the null** when the gap
   reaches `gap_cut(n, m)` — `GAP_MIN` once the span holds `CUT_FULL_WINDOWS`
   windows, rising linearly to 1.42 x `GAP_MIN` at the minimum, because the
   false alarms gather at the longest judged rung — and r_K is below every
   single draw's z_K. The shortest length is never a fallback: short windows
   find chance matches more easily, and long windows of coloured noise are
   smooth curves that match one another well — both effects are in the null,
   which is why only the gap to it decides. The calibration is beside
   `GAP_MIN`.
7. **What the answer means.** The primary answer is the BAND of cleared
   lengths (`cleared_s`; "clears from A to B s, strongest at C"). A repeated
   event clears a band, not one rung: windows SHORTER than the event repeat
   too (pieces of it), and so do LONGER windows that hold it when it dominates
   them. `suggested_window_s` (named so for compatibility; the summary and the
   page say "strongest gap at") is the cleared length with the largest gap —
   the rule that landed within one rung of the planted scale most often
   (beside `SUGGESTION_RULE`) — and it is NOT the event's length, nor a
   window to hand another block (the re-critique: near either planted motif
   in 2 of 10 new seeds): it leans toward the
   longest judged window when an event dominates long windows, and toward an
   edge (the 30-72 s fall of a drop) on chains. An 8 h span judges only up to
   34 min, so a drop chain's ~30 min unit is out of reach there: expect "no
   length" or the fall edge; judge chains on spans of 24 h or more, or read
   the picture.
8. **Cost and stopping.** One profile per length for the span, plus
   `null_draws` per judged length: the adapter's estimate is the
   matrix-profile cost model (`cost.estimate_seconds`, k x n^2 per profile)
   times `profile_units`, plus stumpy's first-call compile.
   `should_cancel()` is checked before every profile, and on True the run
   raises `Working.execution.RecipeCancelled` (the executor's own
   cancellation); `on_progress(done, total, stage)` fires after every profile.

What it cannot see: two occurrences must have the SAME length to match, so
"the same shape at two durations" (RQ3) is not answered here. The comparison
is z-normalised, so amplitude is invisible: a quiet stretch and a loud one of
the same shape match, and pure noise has no shape of its own. A motif that
occurs only twice in the span barely moves r_K (K = 3). A quasi-periodic
chain keeps its spacing in its own null copies (the spectrum is kept), so its
period is partly in the null.

No UI imports; numpy and stumpy, the core's own helpers, and the AAFT
surrogate imported inside `null_copy` from `Adapters.preprocessing_surrogate`
(W3-A moved it there; the core imports it locally, as other `Working/`
modules import `Adapters`).
"""

import numpy as np
import stumpy

from Working.config import MP_MIN_WINDOW_SAMPLES
from Working.Detection.matrix_profiling.snippets import fill_nan
from Working.library.grouping.methods.kshape import phase_randomised_rows

#: how many of the best distinct windows are averaged per length (rule step 6)
K_BEST = 3

#: a length is judged only when the span is at least this many windows long.
#: Below it the greedy non-overlapping pick leaves fewer than about 10
#: distinct windows, the best three are three draws from a handful, and the
#: gap is noise (first calibration: at 12.4 windows, 8 h at 0.5 Hz, two of 36
#: no-structure spans reached 10.0 and 10.9 at one draw).
MIN_WINDOWS = 14

#: below this many windows per span the cut rises (`gap_cut`). Measured in fix
#: round 1 (beside GAP_MIN): with a flat cut at 3 draws the only false
#: suggestions in 147 no-structure spans sat at 17.6 windows (gaps 7.0, 6.1);
#: raising MIN_WINDOWS to 20 instead removed them too, but left the 20 min
#: planted motif unjudged on 4 h (its 976 s rung holds 14.8 windows) — the
#: planted set fell from 5/6 to 3/6 suggestions within one rung.
CUT_FULL_WINDOWS = 24

#: the exponent of N in the gap (rule step 6; measured, see the docstring)
GAP_EXPONENT = 1.0 / 3.0

#: the gap a length must reach (at CUT_FULL_WINDOWS windows or more). Fix round
#: 1 (2026-10-15), the defaults (AAFT, 3 draws, MIN_WINDOWS 14, the growing
#: cut), every span through the template's 2 h rolling-mean detrend, 4 numba
#: threads on a loaded machine (scratch `w3c_hold/fix1_sweep.py`):
#:
#:   no structure                          spans   suggestions
#:   2 h, 1 Hz: random walk                  30         0
#:   2 h, 1 Hz: AR(1) 0.99                   30         0
#:   2 h, 1 Hz: pink noise                   30         0
#:   4 h, 1 Hz: random walk, AR 0.95, AR
#:     0.99, pink, AR 0.97 + 6 h sine        50         0
#:   4 h, 1 Hz: exp(AR(1) 0.97), lopsided    10         0   (phase null: 10/10)
#:   total                                  150         0   (flat cut 6: 2, rw 2 h, 409 s)
#:
#:   planted (90 s x 12 + 20 min x 6, 4 h, seeds 0-5): 6/6 suggest, 5/6
#:   within one rung of 90 s or 20 min. 90 s spike x 12 alone: 6/6 suggest,
#:   only 1/6 within one rung (30, 46, 30, 976, 631, 976 s). 60 s spikes
#:   (10-20, 4 h) at 3 x SD on AR(1): 0/6; at 5 x SD: 3/6 (30 s); on a random
#:   walk at 3 and 5 x SD: 6/6 and 6/6, at 46-171 s. Drop chains (8 h, every
#:   20-60 min, depth CV 0.3, 8 min recovery, 3 x SD): on AR(1) 1/5 (1508 s); on
#:   a random walk 5/5, all at the fall edge (30-72 s). Sharkfins on AR(1):
#:   0/5; on a random walk 5/5, all at 30 s (the drop edge).
#:
#: First calibration (one phase draw, 2026-10-14): about 4 % of no-structure
#: spans got a suggestion; the critic measured 1.2-5.8 % at one draw and 0 at
#: three (1 Hz).
GAP_MIN = 6.0

#: the nulls on offer (rule step 6): "aaft" (default) keeps the recording's own
#: values and roughly its spectrum; "phase" keeps the spectrum exactly but
#: Gaussianises the values. Kept for comparison only: on a lopsided recording
#: with no structure (exp of an AR(1)) the phase null suggested a length in
#: 10 of 10 seeds at 1 and at 20 draws (the W3-C critic), because a skewed
#: recording's windows match each other better than Gaussian noise's do.
NULLS = ("aaft", "phase")

#: how the suggestion is picked among the cleared lengths (rule step 7). The
#: three candidates, on the power cases beside GAP_MIN (within one rung of the
#: planted scale, out of the spans that suggested anything):
#:   strongest gap                           20 of 38
#:   shortest within NEAR_BEST of the best   16 of 38
#:   shortest cleared length                 15 of 38
#: The shortest cleared length is NOT the event scale, against the critic's
#: expectation: a 30 s window inside a 90 s spike repeats as well as the
#: spike does, so it gave 30 s on all 6 of the 90 s motif's spans and on
#: every spike span (counted as a hit there only because 30 s is one rung
#: from 60 s). Neither rule recovers the event length; the band does hold it.
SUGGESTION_RULES = ("strongest", "shortest_near_best", "shortest")
SUGGESTION_RULE = "strongest"
NEAR_BEST = 0.5


def window_lengths(n, fs, min_window_s, max_window_s, n_lengths):
    """The ladder: `(kept, dropped)`, each a list of m in samples, ascending.
    A length is dropped when it is shorter than stumpy's minimum or longer
    than half the span (no window could have a non-overlapping look-alike)."""
    lo, hi, k = float(min_window_s), float(max_window_s), int(n_lengths)
    if lo <= 0 or hi <= 0:
        raise ValueError(f"window lengths must be positive; got {lo:g} s and {hi:g} s")
    if hi < lo:
        raise ValueError(f"max_window_s ({hi:g}) is shorter than min_window_s ({lo:g})")
    if k < 1:
        raise ValueError(f"n_lengths must be at least 1, got {k}")
    secs = np.geomspace(lo, hi, k) if k > 1 else np.array([lo])
    ms = sorted(set(int(round(s * float(fs))) for s in secs))
    kept = [m for m in ms if MP_MIN_WINDOW_SAMPLES <= m <= n // 2]
    dropped = [m for m in ms if m not in kept]
    return kept, dropped


def _runs(mask):
    """`(start, stop)` of every run of True in `mask`."""
    d = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


#: a stall (rule step 5) is a run of at least `stall_s` where every second
#: difference |x[i+2] - 2 x[i+1] + x[i]| is at most this fraction of the span's
#: 75th percentile of them: a held value is exactly 0, and the template's 2 h
#: rolling-mean detrend turns a held value into a near-straight line. Measured
#: (fix round 2, 4 h at 1 Hz, a 20 min hold in the raw trace, then the
#: template's detrend; random walk, AR(1) 0.97 and 0.99, pink, 3 seeds each):
#: inside the hold the largest ratio was 3.7e-4 - 5.1e-4; in the same spans the
#: flattest 60 s of real signal never went below 1.14 (its largest ratio). The
#: cut 0.01 sits 20x above the first and 100x below the second. A quantised
#: 1 Hz logger (AR(1) 0.97, ADC step 1, 1/2 or 1/5 of its SD) had no 60 s
#: window with every second difference 0 (at most 1 in 10,000 at a step of 1 SD).
STALL_TOL = 0.01


def stall_mask(x, stall):
    """Samples inside runs of at least `stall` samples whose second differences
    all stay within STALL_TOL of the span's typical one (a held value, or a held
    value after a rolling-mean detrend). NaN never counts as stalled."""
    x = np.asarray(x, dtype=np.float64)
    out = np.zeros(len(x), dtype=bool)
    if len(x) < 3 or int(stall) < 3:
        return out
    with np.errstate(invalid="ignore"):
        d2 = np.abs(np.diff(x, 2))
    finite = np.isfinite(d2)
    if not finite.any():
        return out
    typical = float(np.percentile(d2[finite], 75))
    flat = finite & (d2 <= STALL_TOL * typical)
    for a, b in _runs(flat):
        # second differences a..b-1 involve samples a..b+1
        if (b + 2) - a >= int(stall):
            out[a:b + 2] = True
    return out


def prepare_gaps(x, max_fill, stall):
    """Fill NaN runs of at most `max_fill` samples by a straight line; keep
    longer runs NaN. A stall — at least `stall` samples of a held value, or of
    a held value that a rolling-mean detrend has turned into a near-straight
    line (`stall_mask`) — is made a long gap too: every window inside it is
    (nearly) a line and matches every other line exactly.

    Returns `(series, n_filled, n_long_gap, n_stalled, long_mask)`; `n_long_gap`
    counts every sample left out, stalls included."""
    x = np.asarray(x, dtype=np.float64)
    max_fill = int(max_fill)
    bad = ~np.isfinite(x)
    if bad.all():
        raise ValueError("the span holds no finite sample (all NaN): nothing to profile")
    long_mask = np.zeros(len(x), dtype=bool)
    for a, b in _runs(bad):
        if b - a > max_fill:
            long_mask[a:b] = True
    stalled = stall_mask(x, stall) & ~bad
    n_stalled = int(stalled.sum())
    long_mask |= stalled
    out = x.copy()
    if bad.any() and not (bad & ~long_mask).sum() == 0:
        filled, _ = fill_nan(np.where(long_mask, np.nan, x))
        short = bad & ~long_mask
        out[short] = filled[short]
    out[long_mask] = np.nan
    n_filled = int((bad & ~long_mask).sum())
    return out, n_filled, int(long_mask.sum()), n_stalled, long_mask


def normalised_profile(x, m):
    """The exact matrix profile of `x` at window `m`, d / (2 sqrt(m)) clipped at
    1 (stumpy's pan normalisation); NaN for a window touching NaN. Length
    n - m + 1."""
    m = int(m)
    with np.errstate(divide="ignore", invalid="ignore"):    # stumpy's 1/sigma over NaN windows; they come out NaN
        mp = stumpy.stump(x, m)
    P = np.asarray(mp[:, 0], dtype=np.float64)
    P[~np.isfinite(P)] = np.nan
    return np.minimum(P / (2.0 * np.sqrt(m)), 1.0)


def distinct_values(p, m):
    """The profile reduced to non-overlapping windows, best first: a window
    is kept only if no kept window starts within `m` samples of it."""
    p = np.asarray(p, dtype=np.float64)
    order = np.argsort(np.where(np.isfinite(p), p, np.inf), kind="stable")
    taken = np.zeros(len(p), dtype=bool)
    out = []
    for i in order:
        v = p[i]
        if not np.isfinite(v):
            break
        if taken[i]:
            continue
        out.append(v)
        taken[max(0, i - m + 1):i + m] = True
    return np.asarray(out, dtype=np.float64)


def null_copy(base, long_mask, seed, d, null="aaft"):
    """Null draw `d` (0-based) of the filled series `base`, seeded by
    `(seed, d)` so every length sees the same copy; the long gaps put back."""
    rng = np.random.default_rng([int(seed), int(d)])
    if null == "aaft":
        from Adapters.preprocessing_surrogate import aaft_surrogate   # inside: the core keeps adapter imports local
        z = aaft_surrogate(base, rng)
    elif null == "phase":
        z = phase_randomised_rows(base[None, :], rng)[0]
    else:
        raise ValueError(f"null must be one of {NULLS}, got {null!r}")
    z = np.array(z, dtype=np.float64)
    z[long_mask] = np.nan
    return z


def _cancelled():
    from Working.execution import RecipeCancelled      # inside: the executor imports the adapters
    return RecipeCancelled


#: a distance at or below this is an exact repeat; floored so a ratio stays finite
_EXACT = 1e-6

#: the reason codes a length can carry (counted in `reasons`)
REASONS = ("clears", "below_cut", "not_every_draw", "too_long", "too_few_windows", "no_spread", "no_null")


def judgeable(n, m):
    """Is the span long enough (MIN_WINDOWS windows) for length `m` to be judged?"""
    return int(n) >= MIN_WINDOWS * int(m)


def gap_cut(n, m):
    """The gap length `m` must reach on an `n`-sample span: GAP_MIN once the
    span holds CUT_FULL_WINDOWS windows of it, rising linearly to
    GAP_MIN x (1 + (CUT_FULL_WINDOWS - MIN_WINDOWS) / CUT_FULL_WINDOWS) at the
    minimum (rule step 6; the measurement is beside CUT_FULL_WINDOWS)."""
    w = int(n) / max(int(m), 1)
    return GAP_MIN * (1.0 + max(0.0, CUT_FULL_WINDOWS - w) / CUT_FULL_WINDOWS)


def length_verdict(real_distinct, null_distincts, n, m):
    """The rule of the module docstring, step 6, for one length `m` on an
    `n`-sample span.

    `real_distinct`: the real span's distinct values (best first);
    `null_distincts`: one such array per null draw (may be empty).
    Returns a dict: n_units, real_kbest, null_kbest (per draw), null_median,
    gap (None when not judged), judged, clears, reason_code, reason."""
    r = np.asarray(real_distinct, dtype=np.float64)
    n_units = int(len(r))
    out = {"n_units": n_units,
           "real_kbest": float(r[:K_BEST].mean()) if n_units else None,
           "null_kbest": [], "null_median": None, "gap": None, "cut": None,
           "judged": False, "clears": False, "reason_code": "", "reason": ""}

    def _no(code, text):
        out["reason_code"], out["reason"] = code, text
        return out

    if not judgeable(n, m):
        return _no("too_long", f"too long to judge on this span: it holds {n / m:.1f} windows of this length, "
                               f"fewer than {MIN_WINDOWS}")
    if not null_distincts:
        return _no("no_null", "no null draws: nothing to compare with")
    zk = [float(np.asarray(q)[:K_BEST].mean()) for q in null_distincts if len(q)]
    zmed = [float(np.median(q)) for q in null_distincts if len(q)]
    out["null_kbest"] = zk
    out["null_median"] = float(np.mean(zmed)) if zmed else None
    n_null = min((len(q) for q in null_distincts), default=0)
    if n_units < 2 * K_BEST or n_null < 2 * K_BEST:
        return _no("too_few_windows", f"too few scorable windows ({min(n_units, n_null)} distinct; NaN gaps or "
                                      f"stalls?) to compare the best {K_BEST} with the typical one")
    z_k, z_med = float(np.mean(zk)), float(np.mean(zmed))
    if z_med <= _EXACT or z_k <= _EXACT or z_med <= z_k:
        return _no("no_spread", "no spread to measure: the null's best windows are no better than its typical "
                                "one (a constant or near-constant span)")
    r_k = max(out["real_kbest"], _EXACT)
    gap = float(n_units ** GAP_EXPONENT * np.log(z_k / r_k) / np.log(z_med / z_k))
    cut = gap_cut(n, m)
    out["gap"] = gap
    out["cut"] = cut
    out["judged"] = True
    beats_every_draw = all(r_k < v for v in zk)
    out["clears"] = bool(gap >= cut and beats_every_draw)
    if out["clears"]:
        return _no("clears", f"gap {gap:.1f} >= {cut:.2g} and better than every draw")
    if gap < cut:
        return _no("below_cut", f"gap {gap:.1f} < {cut:.2g}")
    return _no("not_every_draw", "not better than every null draw")


def suggest(per_length, rule=None):
    """The suggested row among the cleared lengths, by `rule` (default
    `SUGGESTION_RULE`): "strongest" = the largest gap; "shortest_near_best" =
    the shortest cleared length whose gap is at least NEAR_BEST x the largest;
    "shortest" = the shortest cleared length. None when nothing clears."""
    rule = SUGGESTION_RULE if rule is None else rule
    cleared = [d for d in per_length if d["clears"]]
    if not cleared:
        return None
    if rule == "strongest":
        return max(cleared, key=lambda d: d["gap"])
    if rule == "shortest_near_best":
        top = max(d["gap"] for d in cleared)
        return min((d for d in cleared if d["gap"] >= NEAR_BEST * top), key=lambda d: d["m"])
    if rule == "shortest":
        return min(cleared, key=lambda d: d["m"])
    raise ValueError(f"rule must be one of {SUGGESTION_RULES}, got {rule!r}")


def pan_matrix_profile(x, fs, min_window_s=30.0, max_window_s=3600.0, n_lengths=12, null_draws=3, null="aaft",
                       seed=0, max_fill_s=5.0, stall_s=60.0, on_progress=None, should_cancel=None):
    """The pan matrix profile of `x` and the per-length verdict against
    amplitude-adjusted (or phase-randomised) copies. See the module docstring
    for every rule.

    Returns a dict:
        image : float32 (n_rows, n), rows LONG first, 1 - normalised distance,
            NaN where no window starts or a window touches a long gap or stall
        lengths_samples, lengths_s : the rows' window lengths (row order)
        lengths_dropped_samples : lengths of the ladder that could not be used
        per_length : list (row order) of dicts with the statistics and verdict
        cleared_s : the cleared lengths, ascending
        suggested_window_s, suggested_row : None when no length stands out
        verdict, reasons (count per reason code), suggestion_rule
        n_filled, n_long_gap, n_stalled, null, null_draws, seed
    """
    x = np.asarray(x, dtype=np.float64).ravel()
    fs = float(fs)
    n = len(x)
    null_draws = int(null_draws)
    if null_draws < 0:
        raise ValueError(f"null_draws must be 0 or more, got {null_draws}")
    if null not in NULLS:
        raise ValueError(f"null must be one of {NULLS}, got {null!r}")
    ms, dropped = window_lengths(n, fs, min_window_s, max_window_s, n_lengths)
    if not ms:
        raise ValueError(
            f"no window length fits: {min_window_s:g}-{max_window_s:g} s at {fs:g} Hz gives "
            f"{sorted(dropped)} samples, but a window must be at least {MP_MIN_WINDOW_SAMPLES} samples "
            f"and at most half the span ({n // 2}). Shorten max_window_s or analyse a longer span.")
    rows_long_first = ms[::-1]
    common = {
        "lengths_samples": [int(m) for m in rows_long_first],
        "lengths_s": [m / fs for m in rows_long_first],
        "lengths_dropped_samples": [int(m) for m in dropped],
        "null": null, "null_draws": null_draws, "seed": int(seed),
        "suggestion_rule": SUGGESTION_RULE,
    }

    finite_x = x[np.isfinite(x)]
    if finite_x.size and np.ptp(finite_x) == 0:
        # a constant span: every window is constant, every distance 0 — nothing to compare
        per_length = [{"row": r, "m": int(m), "length_s": m / fs, "best": None, "best_idx": None, "p05": None,
                       "median": None, "n_windows": int(n - m + 1), "n_windows_nan": int(n - m + 1),
                       "n_units": 0, "real_kbest": None, "null_kbest": [], "null_median": None, "gap": None, "cut": None,
                       "judged": False, "clears": False, "reason_code": "no_spread",
                       "reason": "no spread to measure: the span holds one value throughout"}
                      for r, m in enumerate(rows_long_first)]
        return {**common, "image": np.full((len(ms), n), np.nan, dtype=np.float32), "per_length": per_length,
                "cleared_s": [], "suggested_window_s": None, "suggested_row": None,
                "verdict": "no spread to measure: the span holds one value throughout, nothing can be judged",
                "reasons": {"no_spread": len(ms)}, "n_filled": 0, "n_long_gap": 0, "n_stalled": int(n)}

    series, n_filled, n_long, n_stalled, long_mask = prepare_gaps(x, int(round(float(max_fill_s) * fs)),
                                                                int(round(float(stall_s) * fs)))
    finite = np.isfinite(series)
    if finite.sum() < 2 * ms[0]:
        raise ValueError(f"only {int(finite.sum())} usable samples after the long gaps and stalls; "
                         "nothing to profile")

    # a length is judged on the samples it can use: long gaps and stalls do not count as span
    n_usable = int(finite.sum())
    judged_ms = [m for m in rows_long_first if judgeable(n_usable, m)]
    draws_for = {m: (null_draws if m in judged_ms else 0) for m in rows_long_first}
    base = fill_nan(series)[0] if (null_draws and judged_ms) else None   # the line across long gaps, for the FFT
    image = np.full((len(ms), n), np.nan, dtype=np.float32)
    per_length = []
    total = len(ms) + sum(draws_for.values())
    done = 0

    def _step(label):
        nonlocal done
        done += 1
        if on_progress is not None:
            on_progress(done, total, label)

    for row, m in enumerate(rows_long_first):
        if should_cancel is not None and should_cancel():
            raise _cancelled()(f"pan matrix profile cancelled before the {m / fs:g} s length "
                               f"({done} of {total} profiles done)")
        prof = normalised_profile(series, m)
        image[row, :len(prof)] = (1.0 - prof).astype(np.float32)
        _step(f"length {m / fs:g} s")
        null_d = []
        for d in range(draws_for[m]):
            if should_cancel is not None and should_cancel():
                raise _cancelled()(f"pan matrix profile cancelled at null draw {d + 1} of the {m / fs:g} s "
                                   f"length ({done} of {total} profiles done)")
            zp = normalised_profile(null_copy(base, long_mask, seed, d, null), m)
            null_d.append(distinct_values(zp, m))
            _step(f"length {m / fs:g} s, null draw {d + 1}")
        ok = np.isfinite(prof)
        verdict = length_verdict(distinct_values(prof, m), null_d, n_usable, m)
        per_length.append({
            "row": row, "m": int(m), "length_s": m / fs,
            "best": float(np.nanmin(prof)) if ok.any() else None,
            "best_idx": int(np.nanargmin(prof)) if ok.any() else None,
            "p05": float(np.nanpercentile(prof, 5)) if ok.any() else None,
            "median": float(np.nanmedian(prof)) if ok.any() else None,
            "n_windows": int(len(prof)), "n_windows_nan": int((~ok).sum()),
            **verdict,
        })

    reasons = {}
    for d in per_length:
        reasons[d["reason_code"]] = reasons.get(d["reason_code"], 0) + 1
    cleared = sorted((d for d in per_length if d["clears"]), key=lambda d: d["m"])
    cleared_s = [d["length_s"] for d in cleared]
    pick = suggest(per_length)
    noun = "amplitude-adjusted" if null == "aaft" else "phase-randomised"
    if pick is not None:
        strongest = max(cleared, key=lambda d: d["gap"])
        band = (f"clears from {cleared_s[0]:g} to {cleared_s[-1]:g} s" if len(cleared_s) > 1
                else f"clears at {cleared_s[0]:g} s")
        verdict = (f"{band}; strongest gap at {strongest['length_s']:g} s (gap {strongest['gap']:.1f}; not an "
                   f"event length) — {len(cleared)} of {len(per_length)} lengths repeat beyond {noun} noise of "
                   f"the same colour")
        suggested_s, suggested_row = pick["length_s"], pick["row"]
    else:
        suggested_s = suggested_row = None
        judged = sum(1 for d in per_length if d["judged"])
        if null_draws == 0:
            verdict = "no null drawn (null_draws = 0): no length can be judged against noise"
        elif not judged:
            verdict = ("no length could be judged: " + ", ".join(f"{k} {v}" for k, v in sorted(reasons.items())))
        else:
            verdict = (f"no length stands out: none of the {judged} judged lengths repeats more than "
                       f"{noun} noise of the same colour"
                       + (f" ({len(per_length) - judged} not judged: "
                          + ", ".join(f"{k} {v}" for k, v in sorted(reasons.items()) if k not in
                                      ("below_cut", "not_every_draw")) + ")"
                          if judged < len(per_length) else ""))

    return {
        **common,
        "image": image,
        "per_length": per_length,
        "cleared_s": cleared_s,
        "suggested_window_s": suggested_s,
        "suggested_row": suggested_row,
        "verdict": verdict,
        "reasons": reasons,
        "n_filled": n_filled, "n_long_gap": n_long, "n_stalled": n_stalled,
    }


#: stumpy compiles its `stump` kernel (numba) on the first call in a process:
#: 35-46 s measured on this machine 2026-10-14 (loaded), against 0.02 s for the
#: same call warm. The matrix-profile cost model times warm calls only, so a
#: first run in a fresh bridge or job read 7x its estimate at 4 h (43.7 s
#: against 6.0 s) without this term.
FIRST_CALL_S = 40.0


def first_call_seconds():
    """FIRST_CALL_S while stumpy's `stump` kernel has not been compiled in
    this process, else 0 (read off numba's dispatcher; 0 if it cannot be read)."""
    import sys
    mod = sys.modules.get("stumpy.stump")
    dispatcher = getattr(mod, "_stump", None)
    sigs = getattr(dispatcher, "signatures", None)
    if sigs is None:
        return 0.0
    return 0.0 if len(sigs) else FIRST_CALL_S


def profile_units(n, fs, min_window_s=30.0, max_window_s=3600.0, n_lengths=12, null_draws=3):
    """How many n-sample matrix profiles a run costs: one per length for the
    span, plus `null_draws` per length that can be judged (no null is drawn
    for a length too long to judge). The adapter multiplies it by the
    matrix-profile cost model's seconds for one profile."""
    ms, _ = window_lengths(int(n), fs, min_window_s, max_window_s, n_lengths)
    return len(ms) + int(null_draws) * sum(1 for m in ms if judgeable(n, m))
