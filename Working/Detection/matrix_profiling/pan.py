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
by computing the same profiles on phase-randomised copies of the span.

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
2. **Exact or approximate** (`percentage`). 1.0 = `stumpy.stump`, exact.
   Below 1, `stumpy.scrump` with `pre_scrump=True` and one `update()` (that
   fraction of the distance-matrix diagonals): approximate — a window's
   distance is an upper bound on the exact one, so the picture is darker
   than the truth and a repetition can be missed, never invented. scrump
   draws its diagonal order from numpy's GLOBAL random generator; the call is
   made under a module lock with the global state saved, seeded and restored,
   so a run is reproducible and other threads' draws are not disturbed
   (wave-2 lesson: the bridge runs jobs on threads).
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
5. **Gaps (adaptation).** stumpy cannot score a window touching NaN. NaN
   runs of at most `max_fill_s` are filled by a straight line
   (`Working.Detection.matrix_profiling.snippets.fill_nan`, imported); longer
   runs stay NaN, so every window touching one is NaN in the picture, left
   out of every statistic, and counted per length (`n_windows_nan`). The
   phase-randomised copies are built from the filled series and get the same
   long gaps back, so real and null lose the same windows.
6. **Which length repeats — the rule (this module's, not the paper's).**
   Per length, the windows are reduced to *distinct* ones: sort the profile,
   keep a window only if no kept window starts within m samples of it (no two
   kept windows overlap). Let N be how many there are, r_K the mean distance
   of the K = 3 best (three, so one lucky pair cannot carry it — a pair of
   look-alikes always gives two equal low values), and for the null copies
   z_K the same mean and z_med the median distance over their distinct
   windows (each averaged over the draws). Then

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
   long to judge on this span": a 4 h span judges up to 17 min); it **clears
   the null** when `gap >= GAP_MIN` and r_K is below every single draw's z_K.
   `suggested_window_s` = the cleared length with the largest gap; when none
   clears, `suggested_window_s` is None and the summary says "no length
   stands out". The shortest length is never a fallback: short windows find
   chance matches more easily, and long windows of coloured noise are smooth
   curves that match one another well — both effects are in the null, which
   is why only the gap to it decides. The calibration is beside `GAP_MIN`.
7. **Cost and stopping.** One profile per length per series (the span and
   each null draw): the adapter's estimate is the matrix-profile cost model
   (`cost.estimate_seconds`, k x n^2 per profile) times `profile_units` — the
   number of lengths x (1 + null_draws), each approximate profile weighted by
   `scrump_cost_factor(percentage, m)` (measured; beside the constants).
   `should_cancel()` is checked before every profile, and on True the run
   raises `Working.execution.RecipeCancelled` (the executor's own
   cancellation); `on_progress(done, total, stage)` fires after every profile.

What it cannot see: two occurrences must have the SAME length to match, so
"the same shape at two durations" (RQ3) is not answered here. The comparison
is z-normalised, so amplitude is invisible: a quiet stretch and a loud one of
the same shape match, and pure noise has no shape of its own. A motif that
occurs only twice in the span barely moves r_K (K = 3).

No UI imports; numpy and stumpy only (plus the core's own helpers).
"""

import threading

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
#: gap is noise: in the calibration below, at 12.4 windows per span (8 h at
#: 0.5 Hz, 39 min; N = 8) two of 36 no-structure spans reached 10.0 and 10.9,
#: and at 9.5 windows (4 h, 25 min) a random walk reached the old rule's 13.4.
MIN_WINDOWS = 14

#: the exponent of N in the gap (rule step 6; measured, see the docstring)
GAP_EXPONENT = 1.0 / 3.0

#: the gap a length must reach to clear the null. Calibrated 2026-10-14 on
#: synthetic spans, one null draw, the default ladder (30 s - 1 h, 12
#: lengths), judged lengths only (MIN_WINDOWS 14):
#:   no structure — AR(1) phi 0.95 / 0.97 / 0.99, detrended random walk, pink
#:   noise, AR(1) 0.97 + a 6 h sine: 2 h and 4 h at 1 Hz (seeds 100-107) and
#:   8 h at 0.5 Hz (decimated, seeds 100-105); 132 spans, about 1,100 judged
#:   lengths. 95th percentile of the gap 2.5 (1 Hz) and 3.1 (0.5 Hz). Spans
#:   with a gap >= 6: four (3 %) — a random walk at 4 h (16 min, 23.7), AR(1)
#:   0.97 and 0.95 on the SAME innovations at 2 h (3-4 min, 8.6 and 6.9), and
#:   pink noise at 8 h / 0.5 Hz (30 s, 7.1). The test file's own sweep (seed 7,
#:   random walk / AR 0.95 / AR 0.99 / pink at 2 h and 8 h / 0.5 Hz) added one
#:   more: AR(1) 0.99 at 2 h, 409 s, 6.9. So about 4 % of no-structure spans
#:   get a suggestion at one draw; more draws lower it.
#:   planted (tests/_pan_synthetic.planted, 4 h, seeds 0-7): the 16 min row
#:   (the 20 min motif) 7.5-68 in all eight; the 72 s or 111 s row (the 90 s
#:   motif) >= 6 in seven of eight (seed 6: 4.8 and 5.6, while its 30 s row
#:   reached 9.2).
#: The first version (sqrt(N), cut 10) was quieter on the 1 Hz nulls but gave
#: false suggestions at 30 s on 0.5 Hz noise; on linear distances instead of
#: ratios the planted lengths fell to 5.8 against nulls up to 6.4.
GAP_MIN = 6.0

#: scrump's cost relative to stump at the same n (`scrump_cost_factor`):
#: prescrump samples every (m/4)-th window and computes its whole distance
#: profile, so its share falls as m grows; the diagonals add `percentage`.
#: Measured 2026-10-14 on this machine (16 threads, loaded by other jobs), one
#: scrump(pre_scrump=True) + one update() against one stump, random walk:
#:     n = 20,000   m = 60: p 0.01-0.5 -> 1.49-1.65 x;  m = 600: 0.64-0.96 x
#:     n = 86,400   m = 60: p 0.1 / 0.5 -> 1.35 / 1.84 x;  m = 600: 0.39 / 0.69 x
#: fitted as p + 0.2 + 60 / m (m in samples). Approximate saves time only on
#: long windows; on the default ladder at p = 0.1 the whole run costs about
#: 0.8 x the exact one.
_SCRUMP_FIXED = 0.2
_SCRUMP_PRESCRUMP_M = 60.0

_RNG_LOCK = threading.Lock()


def scrump_cost_factor(percentage, m):
    """scrump's run time as a multiple of stump's at the same n, for window
    `m` (samples): 1.0 for an exact run, else the measured fit above."""
    p = float(percentage)
    if p >= 1.0:
        return 1.0
    return p + _SCRUMP_FIXED + _SCRUMP_PRESCRUMP_M / max(int(m), 1)


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


def prepare_gaps(x, max_fill):
    """Fill NaN runs of at most `max_fill` samples by a straight line; keep
    longer runs NaN. Returns `(series, n_filled, n_long_gap, long_mask)`."""
    x = np.asarray(x, dtype=np.float64)
    bad = ~np.isfinite(x)
    if not bad.any():
        return x.copy(), 0, 0, bad
    filled, _ = fill_nan(x)                       # raises, in words, if nothing is finite
    long_mask = np.zeros(len(x), dtype=bool)
    d = np.diff(np.concatenate([[0], bad.astype(np.int8), [0]]))
    for a, b in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)):
        if b - a > int(max_fill):
            long_mask[a:b] = True
    out = filled.copy()
    out[long_mask] = np.nan
    return out, int(bad.sum() - long_mask.sum()), int(long_mask.sum()), long_mask


def normalised_profile(x, m, percentage=1.0, seed=0):
    """The matrix profile of `x` at window `m`, d / (2 sqrt(m)) clipped at 1
    (stumpy's pan normalisation); NaN for a window touching NaN. Length
    n - m + 1."""
    m = int(m)
    if float(percentage) >= 1.0:
        with np.errstate(divide="ignore", invalid="ignore"):    # stumpy's 1/sigma over NaN windows; they come out NaN
            mp = stumpy.stump(x, m)
        P = np.asarray(mp[:, 0], dtype=np.float64)
    else:
        with _RNG_LOCK:
            state = np.random.get_state()
            try:
                np.random.seed(int(seed) % (2 ** 32))
                approx = stumpy.scrump(x, m, percentage=float(percentage), pre_scrump=True)
                approx.update()
                P = np.asarray(approx.P_, dtype=np.float64).copy()
            finally:
                np.random.set_state(state)
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


def _cancelled():
    from Working.execution import RecipeCancelled      # inside: the executor imports the adapters
    return RecipeCancelled


#: a distance this small is an exact repeat; floored so the ratio stays finite
_EXACT = 1e-6


def judgeable(n, m):
    """Is the span long enough (MIN_WINDOWS windows) for length `m` to be judged?"""
    return int(n) >= MIN_WINDOWS * int(m)


def length_verdict(real_distinct, null_distincts, n, m):
    """The rule of the module docstring, step 6, for one length `m` on an
    `n`-sample span.

    `real_distinct`: the real span's distinct values (best first);
    `null_distincts`: one such array per null draw (may be empty).
    Returns a dict: n_units, real_kbest, null_kbest (per draw), null_median,
    gap (None when not judged), judged, clears, reason."""
    r = np.asarray(real_distinct, dtype=np.float64)
    n_units = int(len(r))
    out = {"n_units": n_units,
           "real_kbest": float(r[:K_BEST].mean()) if n_units else None,
           "null_kbest": [], "null_median": None, "gap": None,
           "judged": False, "clears": False, "reason": ""}
    if not null_distincts:
        out["reason"] = "no null draws: nothing to compare with"
        return out
    zk = [float(np.asarray(q)[:K_BEST].mean()) for q in null_distincts if len(q)]
    zmed = [float(np.median(q)) for q in null_distincts if len(q)]
    out["null_kbest"] = zk
    out["null_median"] = float(np.mean(zmed)) if zmed else None
    n_null = min((len(q) for q in null_distincts), default=0)
    if not judgeable(n, m):
        out["reason"] = (f"too long to judge on this span: it holds {n / m:.1f} windows of this length, "
                         f"fewer than {MIN_WINDOWS}")
        return out
    if n_units < 2 * K_BEST or n_null < 2 * K_BEST:
        out["reason"] = (f"too few scorable windows ({min(n_units, n_null)} distinct; NaN gaps?) "
                         f"to compare the best {K_BEST} with the typical one")
        return out
    z_k, z_med = float(np.mean(zk)), float(np.mean(zmed))
    r_k = max(out["real_kbest"], _EXACT)
    reach = np.log(z_med / max(z_k, _EXACT))
    if reach <= 0:
        out["reason"] = "the null's best windows are no better than its typical one: no spread to measure in"
        return out
    gap = float(n_units ** GAP_EXPONENT * np.log(max(z_k, _EXACT) / r_k) / reach)
    out["gap"] = gap
    out["judged"] = True
    beats_every_draw = all(r_k < v for v in zk)
    out["clears"] = bool(gap >= GAP_MIN and beats_every_draw)
    if out["clears"]:
        out["reason"] = f"gap {gap:.1f} >= {GAP_MIN:g} and better than every draw"
    elif gap < GAP_MIN:
        out["reason"] = f"gap {gap:.1f} < {GAP_MIN:g}"
    else:
        out["reason"] = "not better than every null draw"
    return out


def pan_matrix_profile(x, fs, min_window_s=30.0, max_window_s=3600.0, n_lengths=12, percentage=1.0,
                       null_draws=1, seed=0, max_fill_s=5.0, on_progress=None, should_cancel=None):
    """The pan matrix profile of `x` and the per-length verdict against
    phase-randomised copies. See the module docstring for every rule.

    Returns a dict:
        image : float32 (n_rows, n), rows LONG first, 1 - normalised distance,
            NaN where no window starts or a window touches a long gap
        lengths_samples, lengths_s : the rows' window lengths (row order)
        lengths_dropped_samples : lengths of the ladder that could not be used
        per_length : list (row order) of dicts with the statistics and verdict
        suggested_window_s, suggested_row : None when no length stands out
        verdict : one sentence
        n_filled, n_long_gap, percentage, null_draws, seed
    """
    x = np.asarray(x, dtype=np.float64).ravel()
    fs = float(fs)
    n = len(x)
    null_draws = int(null_draws)
    if null_draws < 0:
        raise ValueError(f"null_draws must be 0 or more, got {null_draws}")
    p = float(percentage)
    if not 0.0 < p <= 1.0:
        raise ValueError(f"percentage must be in (0, 1], got {p:g}")
    ms, dropped = window_lengths(n, fs, min_window_s, max_window_s, n_lengths)
    if not ms:
        raise ValueError(
            f"no window length fits: {min_window_s:g}-{max_window_s:g} s at {fs:g} Hz gives "
            f"{sorted(dropped)} samples, but a window must be at least {MP_MIN_WINDOW_SAMPLES} samples "
            f"and at most half the span ({n // 2}). Shorten max_window_s or analyse a longer span.")

    series, n_filled, n_long, long_mask = prepare_gaps(x, int(round(float(max_fill_s) * fs)))
    finite = np.isfinite(series)
    if finite.sum() < 2 * ms[0]:
        raise ValueError(f"only {int(finite.sum())} usable samples after the long gaps; nothing to profile")

    base = fill_nan(series)[0] if null_draws else None          # the line across long gaps, for the FFT

    def null_copy(d):
        """Draw `d` (0-based), rebuilt per length from its own seed so every
        length sees the same copy without holding all of them in memory."""
        z = phase_randomised_rows(base[None, :], np.random.default_rng([int(seed), int(d)]))[0]
        z[long_mask] = np.nan
        return z

    rows_long_first = ms[::-1]
    image = np.full((len(ms), n), np.nan, dtype=np.float32)
    per_length = []
    total = len(ms) * (1 + null_draws)
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
        prof = normalised_profile(series, m, p, seed=int(seed) * 1000 + row)
        image[row, :len(prof)] = (1.0 - prof).astype(np.float32)
        _step(f"length {m / fs:g} s")
        null_d = []
        for d in range(null_draws):
            if should_cancel is not None and should_cancel():
                raise _cancelled()(f"pan matrix profile cancelled at null draw {d + 1} of the {m / fs:g} s "
                                   f"length ({done} of {total} profiles done)")
            zp = normalised_profile(null_copy(d), m, p, seed=int(seed) * 1000 + row + 100_000 * (d + 1))
            null_d.append(distinct_values(zp, m))
            _step(f"length {m / fs:g} s, null draw {d + 1}")
        ok = np.isfinite(prof)
        verdict = length_verdict(distinct_values(prof, m), null_d, n, m)
        per_length.append({
            "row": row, "m": int(m), "length_s": m / fs,
            "best": float(np.nanmin(prof)) if ok.any() else None,
            "best_idx": int(np.nanargmin(prof)) if ok.any() else None,
            "p05": float(np.nanpercentile(prof, 5)) if ok.any() else None,
            "median": float(np.nanmedian(prof)) if ok.any() else None,
            "n_windows": int(len(prof)), "n_windows_nan": int((~ok).sum()),
            **verdict,
        })

    cleared = [d for d in per_length if d["clears"]]
    if cleared:
        best = max(cleared, key=lambda d: d["gap"])
        suggested_s, suggested_row = best["length_s"], best["row"]
        verdict = (f"{best['length_s']:g} s repeats most clearly beyond noise of the same colour "
                   f"(gap {best['gap']:.1f}; {len(cleared)} of {len(per_length)} lengths clear the null)")
    else:
        suggested_s = suggested_row = None
        judged = sum(1 for d in per_length if d["judged"])
        if null_draws == 0:
            verdict = "no null drawn (null_draws = 0): no length can be judged against noise"
        else:
            verdict = (f"no length stands out: none of the {judged} judged lengths repeats more than "
                       f"phase-randomised noise of the same colour"
                       + (f" ({len(per_length) - judged} too long to judge on this span)"
                          if judged < len(per_length) else ""))

    return {
        "image": image,
        "lengths_samples": [int(m) for m in rows_long_first],
        "lengths_s": [m / fs for m in rows_long_first],
        "lengths_dropped_samples": [int(m) for m in dropped],
        "per_length": per_length,
        "suggested_window_s": suggested_s,
        "suggested_row": suggested_row,
        "verdict": verdict,
        "n_filled": n_filled, "n_long_gap": n_long,
        "percentage": p, "null_draws": null_draws, "seed": int(seed),
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


def profile_units(n, fs, min_window_s=30.0, max_window_s=3600.0, n_lengths=12, percentage=1.0,
                  null_draws=1):
    """How many exact n-sample matrix profiles a run costs: one per length per
    series (the span and each null draw), x the scrump factor when
    approximate. The adapter multiplies it by the matrix-profile cost model's
    seconds for one profile."""
    ms, _ = window_lengths(int(n), fs, min_window_s, max_window_s, n_lengths)
    return (1 + int(null_draws)) * sum(scrump_cost_factor(percentage, m) for m in ms)
