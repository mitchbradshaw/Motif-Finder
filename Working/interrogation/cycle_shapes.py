"""
cycle_shapes.py
================
The shape of every cycle of a chain of events, sorted into kinds, with where
the kind changes (w3-b). The core of `interrogation.cycle_shapes`; no plotting
library (CLAUDE.md rule 1).

In plain words: a chain of drops is a drummer whose tempo drifts. Each stretch
from one drop to the next is a **cycle** (the drop, the floor, the slow climb
back). To compare cycles of different lengths every cycle is stretched to one
length, the stack is lined up, and the cycles are sorted into piles of "the
same beat". Per cycle the block also measures how long the trace sits on its
floor before it climbs (the sharkfin plateau) and where it is half back.

Source: Colominas & Wu 2023, *IEEE TSP* 71:701-712 ("an iterative warping and
clustering algorithm", Alg. 1) — **the back half only**. Written from the
paper; the authors' MATLAB (github.com/macolominas/WarpingWSF) carries no
licence and was not read or ported.

The algorithm as implemented (each adaptation named, with its reason)
---------------------------------------------------------------------
1. **Phase from the events, not an STFT ridge** (plan §4 A2: fungal recordings
   have no dominant slowly-varying harmonic; the detector has already found the
   beats). Event times are the Intervals anchor: `onset_idx` (Event shape) when
   present and `anchor="onset"`, else the span start. Sequences: by `train_id`
   when the column exists (events in no train open no cycle), else by `group`,
   else the whole span. Cycle k runs from event k's anchor to event k+1's,
   inside one sequence.
2. **Gaps and splits are not cycles.** A cycle longer than `max_cycle_s`, or
   (0 = auto) longer than `AUTO_MAX_MULT` (1.6) x the running median of the
   `LOCAL_CYCLES` (11) cycle lengths around it, is a gap (`gap_long`); one
   shorter than `min_cycle_s`, or (0 = auto) shorter than `AUTO_MIN_MULT` (0.4)
   x that running median or than `MIN_CYCLE_SAMPLES` samples, is a split
   (`too_short`). Both are left out and counted. The local median, not the
   sequence's: on a chain whose period drifts 20 -> 60 min, 3 x the sequence's
   median (40 min) is 120 min, which keeps a missed detection (two cycles read as
   one, ~2 x the local length) anywhere in the chain; 1.6 x the local median
   leaves most of them out. The price, measured by the W3-B critic (300 chains
   per cell; 30, 100 and 300 cycles alike; drift makes no difference) — true
   cycles lost at a jitter CV of 0.2 / 0.3 / 0.4 / 0.5: 1 / 5.5 / 11 / 17.5 %
   (CV 0.5 with 30 cycles: 90th percentile 27 %; correlated log-intervals, AR
   0.8: 0.5 % at CV 0.3, 4.9 % at 0.5). The factor's trade-off at CV 0.3 / 0.5:
   1.6 catches 80 / 69 % of missed detections and loses 4.8 / 13.6 % of true
   cycles; 1.8 -> 62 / 58 % and 2.2 / 9.3 %; 2.0 -> 44 / 46 % and 0.8 / 6.1 %.
   The cycles lost are the LONGEST — a bias against long plateaus — so when
   more than `GAP_WARN_SHARE` (10 %) of a sequence's cycles are gaps, a warning
   and the summary say so. The rule depends on event times only.
3. **The waveform.** Cycles are cut from the `waveform` (a side input; else from
   the chain's own signal), because a detector usually runs on a short-detrended
   trace that flattens a 30-45 min climb (measured: from a 600 s rolling-mean
   trace synthetic sharkfins read half back at 0.16 of the cycle — as troughs —
   against 0.69 from the raw trace). `cycle_detrend="chord"` subtracts the
   straight line between the pre-drop levels at the cycle's two ends, each the
   median of the `END_FRAC` (2 %, at least 2 samples) just BEFORE that anchor.
   Departure from the prompt's "first / last few samples of the cycle": the
   first samples after an onset anchor are already the drop (the drop of the
   synthetic sets lasts 2 % of the cycle, and Event shape's onsets sat 20-40 s
   into it), so the cycle's own first samples are mid-drop, not pre-drop. A
   cycle with more than `max_nan_frac` missing samples is left out
   (`missing_values`); fewer are interpolated.
4. **Warp and demodulate** (the paper's step 3): each cycle is resampled to
   `n_points` with the Library's own preparation
   (`Working.distances.resample_to_length`, as `ward.shape_vectors` does) and
   z-normalised. The size and duration the warp removes stay as columns
   (`cycle_amplitude` in the trace's stored unit, `cycle_length_s`).
5. **The refinement** (the paper's iteration, adapted). The paper re-estimates
   the phase until the SVD entropy stagnates; here the phase is the anchors, so
   one iteration aligns every cycle to the current working template (the
   pointwise median of the stack — a working template only, never drawn) by a
   zero-padded cross-correlation bounded by `max_shift_frac` of its length,
   moves its start anchor by that shift (the previous cycle's end moves with
   it), re-cuts and re-warps. An anchor never moves more than `max_shift_frac`
   of its cycle's length from where the detector put it. The iteration is kept
   while the entropy falls **by more than its own sampling noise** — the SD of
   the same entropy over `BOOTSTRAP_DRAWS` (5) seeded bootstrap resamples of the
   cycles, never a fixed epsilon; otherwise the previous anchors are kept and
   it stops; at most `max_iter` (8; the paper's examples needed 1-8). The
   stopping entropy is eq. 17, the paper's. On every synthetic set here the
   first round did not beat the spread (the anchors were already the phase):
   the history in meta shows it.
6. **Align** (the paper's step 5, replaced): zero-padded cross-correlation
   (bounded, as above) to the median template, then again to the stack's
   medoid — not the paper's cyclic shifts, because a fungal cycle does not wrap
   around. Vacated samples take the row's own edge value (as
   `Working.library.coherence` pads), then rows are re-z-normalised. The medoid
   is the cycle with the highest summed correlation to the others after the
   first alignment (SBD at zero lag: the stack is already aligned). After the
   grouping each group is aligned again to its OWN medoid (`cycle_shift_s`,
   `cycle_corr`, the stack payload's "after").
7. **Cluster.** Departures from the paper, each measured on the synthetic sets:
   * **on the refined, warped stack, not the aligned one.** Aligning a mixture
     of two shapes to one template shifts some members of one shape against the
     other's features, and the shifted and unshifted members then form groups
     of their own (troughs split 44/16 and 47/13 at 10 % noise); the anchors are
     already the phase, so the clustering reads the cycles as cut;
   * **K = 1 exists, and a split must beat the block's own null** (fix round 1,
     W3-B critic B1). z-normalised noise cycles are sign-bimodal: a cycle that
     is mostly one smooth component becomes roughly +-that component, so
     2-means on pure noise splits on the sign of PC1, and no test against a
     Gaussian or a uniform can see that its two modes are noise (the shipped
     gate said K = 2 in 4-5 of 10 chain-timed random-walk chains). So the best
     two-way split (2-means, `KMEANS_REPLICATES` (50) starts) is claimed only
     when ALL of:
     - its cluster index (within / total sum of squares) is below that of the
       same 2-means on EVERY stack of the K null and more than
       `VERDICT_SPREADS` robust SDs below their median (the verdict's rule).
       The K null is the background draws (they are cut, warped and refined like
       the real cycles, so they are sign-bimodal too); when the background fell
       back (step 10) it is per-cycle phase-randomised copies of the real cycles
       made before the chord (`phase_cycle_stacks`); `meta.k_null.source` and
       the summary say which;
     - it is two modes along its own direction: the cycles projected onto the
       line through the two centroids split better than uniform samples of the
       same size (the uniform is the least favourable one-mode shape, as in the
       calibration of Hartigan's dip test). This is what keeps one family that
       varies together: a steadily lengthening plateau beats the background's
       split, but is one mode (p 0.84-0.99);
     - each half holds at least `min_cycles` (so a sequence of fewer than
       2 x `min_cycles` cycles is K = 1 by construction, said in `k_note`).
     Measured with the gate (default settings, 15 % noise): chain-timed noise
     (~100 cycles, CV 0.3) K = 2 in 0/10 random walk, 0/10 AR(1), 0/10 drift;
     1,000 random-walk cycles K = 1; the same noise filling its span (phase
     null) 0/10, 0/10, 0/10; two shapes 120/120 cycles K = 2 on all three
     backgrounds (ARI 0.90-1.00), with or without the background (9/9 on the
     phase null); one drifting plateau K = 1 in 9/9 and 9/9 without it. The
     2-means runs on the top `SPLIT_COMPONENTS` (32) principal components, for
     the real stack and every null stack alike (with full-space fits the AR(1)
     span-filling noise read K = 2 in 1 of 10).
     **Both nulls when there is a background** (fix round 2, decision 17): the
     split must also beat the per-cycle phase copies (`K_GATE_BOTH`). With quiet
     margins of one colour (AR(0.95)) and a random walk under chain-timed noise,
     the background half passed 10/10 and only the mode test held (K = 2 in 5/10
     here); with both nulls K = 1 in 10/10. Real-like two-shape chains kept
     K = 2 in 24/24 (random walk, AR(1), drift; 15 and 30 % noise; with margins
     and filling the span) and in 6/6 on mixed-colour backgrounds.
     **The power given up for size** (the W3-B re-critique's measurements): a
     random walk at 30 % noise with 80/20 or 90/10 shape proportions now reads
     K = 1, and AR(0.98) at 90/10 with margins reads K = 1; 50/50 at 30 % keeps
     K = 2 (ARI 0.58-1.0 here).
   * **SigClust is reported, not used** (Liu, Hayes, Nobel & Marron 2008): the
     split's cluster index against a Gaussian with the stack's own sample
     eigenvalues (rank min(n - 1, d)). The paper's background-noise floor
     (sigma_N = MAD of the entries / 0.6745) is NOT applied: it is the estimate
     for sparse high-dimensional data, and on z-normalised smooth cycles, where
     every coordinate carries the curve, it inflated the null's variance
     1.4-2.1x and rejected a true one-cluster Gaussian 12/12 (critic B2). The
     first round's reading "our cycles are never one Gaussian" was that floor's
     artefact, not a property of the cycles; unfloored, SigClust's p on noise
     stacks was mostly 0.06-0.83, though it still rejects some (part of the
     non-Gaussianity is real), which is why it does not decide.
   * **K by bisection, not Calinski-Harabasz.** Past the gate, each group is
     split again only while its own split passes the same three tests at alpha x
     (n_node - 1) / (n - 1) (Kimes, Liu, Neill Hayes & Marron 2017, *Biometrics*
     73:811, the sequential family-wise rule for a hierarchy), the K null cut to
     the node's size; at most `k_max` groups, settled by one Lloyd pass from the
     leaves' centroids. The paper's CH choice is in meta (`k_ch`, `ch_curve`) but
     does not decide: on a two-shape chain over a random walk it chose 3
     (adjusted Rand 0.71) where the bisection kept 2. Groups are numbered 1..K
     by size.
   The k-means is a plain numpy Lloyd with k-means++ seeds (sklearn's KMeans
   gives the same answer but costs ~7 ms a run in thread start-up on stacks
   this small, and SigClust needs thousands of runs).
8. **Change points**: in time order within a sequence, a cycle whose group
   differs from the previous used cycle's. The order test counts the runs of
   equal groups against `n_perm` shuffles of the cycle order within the
   sequence: p = (1 + #shuffles with as few runs) / (1 + n_perm). Cycles do not
   overlap, so shuffling their order is a fair null for ORDER; it does not
   test shape — a slow drift of shape would also make runs.
9. **Plateau measures** (round B), on each warped, chord-detrended cycle after
   a running median of `SMOOTH_POINTS` points: `cycle_floor_frac` = the share
   of the cycle from the first sample within the lowest `floor_band` of the
   cycle's range to the last one before the climb's top (the highest point
   after the deepest one) — so a wander out of the band and back is not read as
   the climb, and the start of the next drop at the cycle's end (a late anchor)
   is not read as more floor; `cycle_half_recovery_frac` = where (0-1) the
   trace first gets back half way from the deepest point to its pre-drop level
   (0 on the chord); NaN when it never does (counted). A flat floor of share f
   climbing linearly over a share c reads about f + b c (+ the drop): the
   synthetic sharkfin (f 0.5, c 0.46) reads 0.56-0.58 (median) at 15 % noise.
10. **Coherence and its nulls.** SVD entropy (`Working.library.coherence.
    svd_entropy`) of the whole stack and of every group, at three points:
    fixed-length cuts from each anchor (the median cycle length; the plain
    baseline), after warping, after alignment — eq. 17 (`svd_entropy_norm`) and
    the sigma^2 variant (`svd_entropy_squared_norm`), **sigma^2 first** wherever
    it is shown (the researcher, 2026-10-14). `svd_entropy` is called with
    `align=False`: the stack is already aligned (step 6), and its own unbounded
    SBD alignment would line pure noise up more than the bounded one the nulls
    get. Three nulls:
    * **background** (the verdict): pseudo-cycles cut from the waveform where no
      event lies (`Working.background_null.sample_background`, the event spans
      avoided), lengths drawn from the real cycles', each `null_draws` draw
      through the identical chord, warp, refinement and alignment (the
      clustering is not repeated per draw); a group's null is a random subset
      of each draw of the group's size, aligned on its own. When the waveform
      holds too little event-free signal the windows are cut at random places
      in the whole span instead, and the meta and summary say so;
    * **trend-kept phase** (`svd_entropy`'s own): shown with `SMOOTH_CAVEAT` —
      it keeps a cycle's drop-floor-climb curve in its own fake noise;
    * **plain phase** (`kshape.phase_randomised_rows`, no trend kept).
    **The verdict** stays on eq. 17 (the researcher: until it is re-measured on
    sigma^2): `beyond_noise` = eq. 17 below EVERY background draw AND below the
    draws' median by more than `VERDICT_SPREADS` (3) robust SDs of the draws
    (1.4826 MAD, floored at `VERDICT_SPREAD_FLOOR` of the median). Departure from
    the Library's multiplicative margin (score < 0.9 x null p05, kept in meta as
    `beyond_noise_margin` for comparison): eq. 17 sits at 0.86-0.96 on cycles at
    15 % noise and its background null 0.01-0.05 above it, so the 0.9 margin
    failed a two-shape chain at z = 19 on AR(1) — a fixed yardstick at the wrong
    scale (wave 2's lesson). sigma^2's reading against the same null travels
    beside it (`beyond_noise_squared`). A group that fails is keyed
    `~noise_like`, one never tested `~untested` (the families' suffixes).
    **"Beyond the background" means unlike the quiet margins**, not
    necessarily unlike the chain's own noise. When the chain's background has
    another colour than the margins (a random walk under the chain, AR(0.95)
    around it), noise cycles beat the margins at z 17-50 on eq. 17 (10/10). So
    the whole stack's sigma^2 is also read against `null_draws` per-cycle
    phase copies of its own cycles (`phase_cycle_stacks`: each cycle's own
    spectrum, its local colour; reported as `whole.nulls.phase_cycles`, sigma^2
    ONLY — eq. 17 failed real-like chains against it 4 of 9 and is never read
    against it). Beating the background but not these copies sets
    `background_colour_mismatch`, warns "the chain's background differs in colour
    from the quiet margins: beyond the margins, not beyond its own noise", and
    keys every group `~untested`. Measured: mixed-colour noise flagged 10/10;
    real-like two-shape chains beat the copies (z 7-51) on random walk, AR(1)
    and mixed colour; but on the drifting background at 30 % noise a real two-
    shape chain did NOT (z 0.2-1.2, 2/2): the sine under each cycle stays in its
    copies, so the check raises a false alarm there (untested, never a false
    pass).
    **A group's key is unmarked only when eq. 17 AND sigma^2 both beat the
    background** (decision 18; stricter than eq. 17 alone, never looser).
    **A chain that fills its span** (fix round 1, critic B3): when more than
    `FALLBACK_LIMIT` (half) of the pseudo-cycles fitted no free stretch, the
    pseudo-cycles are random-phase cuts of the chain itself — shifted copies of
    the same shape — and a perfect chain read "no better than noise" on eq. 17.
    Then every verdict is `tested: False` with the reason, the groups are keyed
    `~untested` (not `~noise_like`), and the warning says "no free stretch as
    long as a cycle (longest free stretch N s, cycles M s)" — the sampler's
    `longest_free_s` tells fragmented background from too little.
    **A group's null matches its selection** (critic S2): on every background
    draw the same K-means (the real K) is run, each null group lined up on its
    own, and the real groups are judged against the null groups of their own
    rank (the lowest-entropy real group against the lowest-entropy null group;
    ranked separately for eq. 17 and sigma^2). The random-subset null of the
    first round passed sigma^2 in 9 of 36 groups forced out of noise. Every
    draw's value is in meta (`values`), with `draws_dropped` (draws with fewer
    than two preparable windows). The whole stack's verdict has no selection.
"""

import time

import numpy as np

from Working.background_null import sample_background
from Working.Catalogue.shape_families import NOISE_LIKE_SUFFIX, UNTESTED_SUFFIX
from Working.distances import resample_to_length, z_normalize
from Working.interrogation.intervals import kendall_trend
from Working.library.coherence import NULL_MARGIN, SMOOTH_CAVEAT, svd_entropy
from Working.library.grouping.methods.kshape import null_rng, phase_randomised_rows

N_POINTS = 256
STACK_POINTS = 128
STACK_MAX = 200
MAX_SHIFT_FRAC = 0.1
MAX_ITER = 8
K_MAX = 6
MIN_CYCLES = 10
KMEANS_REPLICATES = 50
SIGCLUST_DRAWS = 20
SPLIT_COMPONENTS = 32
NULL_KMEANS_REPLICATES = 10
K_NULL_DRAWS = 20
FALLBACK_LIMIT = 0.5
K_GATE_BOTH = True
GAP_WARN_SHARE = 0.1
SIGCLUST_REPLICATES = 3
CH_REPLICATES = 3
SIGCLUST_ALPHA = 0.05
BIMODAL_DRAWS = 200
NULL_DRAWS = 20
PHASE_NULL_DRAWS = 5
TREND_NULL_DRAWS = 5
N_PERM = 1000
FLOOR_BAND = 0.25
MAX_NAN_FRAC = 0.1
BOOTSTRAP_DRAWS = 5
LOCAL_CYCLES = 11
AUTO_MAX_MULT = 1.6
AUTO_MIN_MULT = 0.4
MIN_CYCLE_SAMPLES = 8
END_FRAC = 0.02
SMOOTH_POINTS = 5
VERDICT_SPREADS = 3.0
VERDICT_SPREAD_FLOOR = 0.002
ANCHORS = ("onset", "start")
DETRENDS = ("chord", "none")

OMIT_NO_CYCLE = "opens_no_cycle"
OMIT_NO_ANCHOR = "no_anchor"
OMIT_NO_SEQUENCE = "in_no_train"
OMIT_LONG = "gap_long"
OMIT_SHORT = "too_short"
OMIT_NAN = "missing_values"
OMIT_FLAT = "flat"
OMIT_FEW = "too_few_cycles"

EXEMPLAR_RULE = ("each group's medoid cycle: the member whose aligned, warped cycle has the highest summed correlation "
                 "with the group's other members (a member, never an average); named by the event that opens it")


def _check(should_cancel):
    if should_cancel is not None and should_cancel():
        from Working.execution import RecipeCancelled
        raise RecipeCancelled("Cycle shapes cancelled.")


# ── preparing cycles ────────────────────────────────────────────────────────

def _z_rows(Y):
    out = Y - Y.mean(axis=1, keepdims=True)
    sd = out.std(axis=1)
    big = sd > 1e-12
    out[big] /= sd[big, None]
    out[~big] = 0.0
    return out


def _level_before(trace, at, k, fallback):
    """The pre-drop level at an anchor: the median of the `k` samples just
    before it (NaN ignored), or of `fallback` when there are none."""
    pre = np.asarray(trace[max(0, at - k):at], dtype=float)
    pre = pre[np.isfinite(pre)]
    if pre.size == 0:
        pre = np.asarray(fallback, dtype=float)
    return _median(pre)


def _median(a):
    """np.median without its per-call overhead (it dominated the cut on short ends)."""
    a = np.sort(np.asarray(a, dtype=float).ravel())
    n = a.size
    return float(a[n // 2]) if n % 2 else float(0.5 * (a[n // 2 - 1] + a[n // 2]))


def prepare_cycle(trace, start, end, n_points=N_POINTS, detrend="chord", max_nan_frac=MAX_NAN_FRAC):
    """`(warped, amplitude, reason)` for one cycle `trace[start:end]`: the cut,
    chord-detrended (or not), resampled to `n_points`, NOT z-normalised; the
    amplitude (peak to peak of the detrended cut, in the trace's unit); `reason`
    None, or why the cycle cannot be used."""
    start, end = int(start), int(end)
    seg = np.asarray(trace[start:end], dtype=float)
    if seg.size < 2:
        return None, float("nan"), OMIT_SHORT
    bad = ~np.isfinite(seg)
    if bad.any():
        if bad.mean() > max_nan_frac or bad.all():
            return None, float("nan"), OMIT_NAN
        i = np.arange(seg.size)
        seg = seg.copy()
        seg[bad] = np.interp(i[bad], i[~bad], seg[~bad])
    if detrend == "chord":
        k = max(2, int(round(END_FRAC * seg.size)))
        a = _level_before(trace, start, k, seg[:k])
        b = _level_before(trace, end, k, seg[-k:])
        seg = seg - (a + (b - a) * np.linspace(0.0, 1.0, seg.size))
    amp = float(np.ptp(seg))
    if amp <= 0.0:
        return None, 0.0, OMIT_FLAT
    return resample_to_length(seg, int(n_points)), amp, None


def _prepare_all(trace, starts, ends, n_points, detrend, max_nan_frac):
    m = len(starts)
    W = np.zeros((m, int(n_points)))
    amps = np.full(m, np.nan)
    reasons = [None] * m
    for i in range(m):
        w, a, r = prepare_cycle(trace, starts[i], ends[i], n_points, detrend, max_nan_frac)
        amps[i] = a
        reasons[i] = r
        if w is not None:
            W[i] = w
    return W, amps, reasons


# ── shifting, aligning, entropy ─────────────────────────────────────────────

def bounded_shifts(Z, template, max_shift):
    """For every row of `Z`, the shift s in [-max_shift, max_shift] maximising the
    zero-padded cross-correlation sum_i template[i] row[i - s] (the convention of
    `Working.distances.sbd_shift`: the row moved right by s matches the template)."""
    Z = np.atleast_2d(np.asarray(Z, dtype=float))
    L = Z.shape[1]
    nfft = 1 << (2 * L - 1 - 1).bit_length()
    cc = np.fft.irfft(np.fft.rfft(np.asarray(template, dtype=float), nfft)[None, :]
                      * np.conj(np.fft.rfft(Z, nfft, axis=1)), nfft, axis=1)
    ms = int(max(0, min(int(max_shift), L - 1)))
    lags = np.arange(-ms, ms + 1)
    vals = cc[:, lags % nfft]
    return lags[np.argmax(vals, axis=1)].astype(np.int64)


def shift_rows(Z, shifts):
    """Every row moved right by its shift, vacated samples filled with the row's
    own edge value, then re-z-normalised."""
    Z = np.asarray(Z, dtype=float)
    L = Z.shape[1]
    src = np.clip(np.arange(L)[None, :] - np.asarray(shifts)[:, None], 0, L - 1)
    return _z_rows(np.take_along_axis(Z, src, axis=1))


def _median_template(Z):
    return z_normalize(np.median(Z, axis=0))


def medoid_row(A, max_ref=2000, seed=0):
    """The row with the highest summed correlation to the others (rows are
    z-normalised, so A A^T / L is the correlation). Past `max_ref` rows the sum
    runs over a seeded sample of reference rows."""
    A = np.asarray(A, dtype=float)
    n, L = A.shape
    ref = A
    if n > max_ref:
        ref = A[np.sort(np.random.default_rng(seed).choice(n, max_ref, replace=False))]
    return int(np.argmax((A @ ref.T).sum(axis=1)))


def align_stack(Z, max_shift, seed=0):
    """`(aligned, shifts, medoid)`: Z aligned to its median template, the medoid
    of that, then Z aligned again to the medoid (module docstring, step 6)."""
    Z = np.asarray(Z, dtype=float)
    if len(Z) < 2:
        return Z.copy(), np.zeros(len(Z), dtype=np.int64), 0
    A1 = shift_rows(Z, bounded_shifts(Z, _median_template(Z), max_shift))
    m = medoid_row(A1, seed=seed)
    shifts = bounded_shifts(Z, A1[m], max_shift)
    return shift_rows(Z, shifts), shifts, m


def entropy_pair(Z):
    """`(eq17_norm, squared_norm)` of the rows of Z — the numbers
    `coherence.svd_entropy` reports (`_entropies`), from the eigenvalues of the
    smaller Gram matrix instead of an SVD (4-10 x faster inside the loops;
    agreement pinned by a test); (nan, nan) for a flat stack."""
    Z = np.asarray(Z, dtype=float)
    if len(Z) < 2:
        return float("nan"), float("nan")
    G = Z @ Z.T if Z.shape[0] <= Z.shape[1] else Z.T @ Z
    lam = np.clip(np.linalg.eigvalsh(G), 0.0, None)
    sigma = np.sqrt(lam)
    if float(sigma.sum()) <= 0.0:
        return float("nan"), float("nan")
    scale = np.log(min(Z.shape))

    def h(w):
        p = w / float(w.sum())
        p = p[p > 0]
        return float(-(p * np.log(p)).sum() / scale) if scale > 0 else 0.0

    return h(sigma), h(lam)


def _boot_sd(Z, rng, draws=BOOTSTRAP_DRAWS):
    n = len(Z)
    vals = [entropy_pair(Z[rng.integers(0, n, n)])[0] for _ in range(int(draws))]
    vals = [v for v in vals if np.isfinite(v)]
    return float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0


# ── the refinement ──────────────────────────────────────────────────────────

def refine(trace, starts, ends, next_of, *, n_points=N_POINTS, detrend="chord", max_nan_frac=MAX_NAN_FRAC,
           max_shift_frac=MAX_SHIFT_FRAC, max_iter=MAX_ITER, seed=0, should_cancel=None):
    """The paper's iteration with the anchors as the phase (step 5). `next_of[i]`
    is the cycle whose start is cycle i's end (-1 when none: its end stays put).
    Every cycle must prepare (the caller has left out the ones that do not).

    Returns `(W, amps, starts, ends, history, stopped)`: the final warped,
    chord-detrended cycles (not z-normalised), their amplitudes, the refined
    anchors, the entropy at every iteration, and why it stopped."""
    starts0 = np.asarray(starts, dtype=np.int64).copy()
    ends0 = np.asarray(ends, dtype=np.int64).copy()
    next_of = np.asarray(next_of, dtype=np.int64)
    linked = next_of >= 0
    n_trace = len(trace)
    lens0 = ends0 - starts0
    bound = np.round(max_shift_frac * lens0).astype(np.int64)
    ms = max(1, int(round(max_shift_frac * n_points)))
    rng = null_rng(seed, 41)

    def ends_of(cur):
        e = ends0.copy()
        e[linked] = cur[next_of[linked]]
        return e

    cur = starts0.copy()
    W, amps, _ = _prepare_all(trace, cur, ends_of(cur), n_points, detrend, max_nan_frac)
    Z = _z_rows(W)
    H, Hs = entropy_pair(Z)
    sd = _boot_sd(Z, rng)
    history = [{"iteration": 0, "svd_entropy_squared_norm": Hs, "svd_entropy_norm": H, "spread": sd,
                "kept": True}]
    stopped = "max_iter" if max_iter > 0 else "no_iteration"
    for it in range(1, int(max_iter) + 1):
        _check(should_cancel)
        sh = bounded_shifts(Z, _median_template(Z), ms)
        e_cur = ends_of(cur)
        move = np.round(sh * (e_cur - cur) / float(n_points)).astype(np.int64)
        new = np.clip(cur - move, starts0 - bound, starts0 + bound)
        new = np.clip(new, 0, n_trace - 1)
        e_new = ends_of(new)
        ok = (e_new - new) >= MIN_CYCLE_SAMPLES
        new = np.where(ok, new, cur)
        e_new = ends_of(new)
        W2, amps2, reasons = _prepare_all(trace, new, e_new, n_points, detrend, max_nan_frac)
        bad = np.array([r is not None for r in reasons])
        if bad.any():   # a re-cut that no longer prepares keeps its previous cut
            new[bad] = cur[bad]
            W2[bad] = W[bad]
            amps2[bad] = amps[bad]
        Z2 = _z_rows(W2)
        H2, Hs2 = entropy_pair(Z2)
        fell = H - H2
        kept = bool(np.isfinite(fell) and fell > sd)
        history.append({"iteration": it, "svd_entropy_squared_norm": Hs2, "svd_entropy_norm": H2,
                        "spread": None, "kept": kept})
        if not kept:
            stopped = "stagnated" if np.isfinite(fell) and fell >= 0 else "rose"
            break
        cur, W, amps, Z, H = new, W2, amps2, Z2, H2
        sd = _boot_sd(Z, rng)
        history[-1]["spread"] = sd
    return W, amps, cur, ends_of(cur), history, stopped


# ── clustering ─────────────────────────────────────────────────────────────

def _kpp(X, k, rng, x2):
    """k-means++ seeding (Arthur & Vassilvitskii 2007)."""
    n = len(X)
    C = [X[int(rng.integers(n))]]
    d2 = np.maximum(x2 - 2 * X @ C[0] + C[0] @ C[0], 0.0)
    for _ in range(1, k):
        tot = float(d2.sum())
        i = int(rng.choice(n, p=d2 / tot)) if tot > 0 else int(rng.integers(n))
        C.append(X[i])
        d2 = np.minimum(d2, np.maximum(x2 - 2 * X @ X[i] + X[i] @ X[i], 0.0))
    return np.array(C)


def kmeans(X, k, n_init, seed, max_iter=100):
    """`(labels, inertia)` of the best of `n_init` Lloyd runs from k-means++
    seeds — plain k-means, the paper's (sklearn's KMeans gives the same answer
    but costs ~7 ms a run in thread start-up on stacks this small, and SigClust
    needs thousands of runs)."""
    X = np.asarray(X, dtype=float)
    n = len(X)
    k = int(min(k, n))
    rng = np.random.default_rng(int(seed))
    x2 = np.einsum("ij,ij->i", X, X)
    best_lab, best_in = None, np.inf
    for _ in range(int(n_init)):
        C = _kpp(X, k, rng, x2)
        lab = None
        for _ in range(int(max_iter)):
            D = x2[:, None] - 2 * X @ C.T + np.einsum("ij,ij->i", C, C)[None, :]
            new = np.argmin(D, axis=1)
            if lab is not None and np.array_equal(new, lab):
                break
            lab = new
            for c in range(k):
                mem = lab == c
                if mem.any():
                    C[c] = X[mem].mean(axis=0)
        inertia = float(np.maximum(D[np.arange(n), lab], 0.0).sum())
        if inertia < best_in:
            best_lab, best_in = lab.copy(), inertia
    return best_lab, best_in


_kmeans = kmeans


def sigclust(A, draws=SIGCLUST_DRAWS, seed=0, replicates=KMEANS_REPLICATES):
    """SigClust (Liu, Hayes, Nobel & Marron 2008) on the rows of A, REPORTED
    ONLY (it decides nothing here): the best two-way split's cluster index
    against draws from a Gaussian whose eigenvalues are the stack's own sample
    eigenvalues (rank min(n - 1, d)). No background-noise floor: the paper's
    sigma_N (MAD of all entries / 0.6745) assumes sparse high-dimensional data
    where most coordinates are noise; on z-normalised smooth cycles every
    coordinate carries the curve, and flooring every eigenvalue at it inflated
    the null's variance 1.4-2.1x and rejected a true one-cluster Gaussian 12/12
    (W3-B critic, B2). Returns `p`, `ci`, `null_ci_median`, `null_ci_p05`,
    `draws`, `rank`, `labels2` (the real 2-means, `replicates` starts)."""
    A = np.asarray(A, dtype=float)
    n = len(A)
    Xc = A - A.mean(axis=0)
    U, S, _ = np.linalg.svd(Xc, full_matrices=False)
    r = int(min(n - 1, A.shape[1]))
    scores = U[:, :r] * S[:r]
    total = float((scores ** 2).sum())
    labels2, inertia = _kmeans(scores, 2, replicates, seed)
    ci = inertia / total if total > 0 else 1.0
    lam = S[:r] ** 2 / max(1, n - 1)
    rng = null_rng(seed, 53)
    null = []
    for b in range(int(draws)):
        G = rng.standard_normal((n, r)) * np.sqrt(lam)[None, :]
        Gc = G - G.mean(axis=0)
        _, inn = _kmeans(Gc, 2, SIGCLUST_REPLICATES, seed + 1 + b)
        null.append(inn / float((Gc ** 2).sum()))
    null = np.asarray(null)
    p = float((1 + np.sum(null <= ci)) / (1 + len(null))) if len(null) else None
    return {"p": p, "ci": float(ci), "null_ci_median": float(np.median(null)) if len(null) else None,
            "null_ci_p05": float(np.percentile(null, 5)) if len(null) else None, "draws": int(len(null)),
            "rank": r, "alpha": SIGCLUST_ALPHA, "decides": False, "labels2": labels2}


def ci_1d(y):
    """The best two-way split's cluster index of 1-D values (within over total
    sum of squares, the split scanned exactly over the sorted values)."""
    y = np.sort(np.asarray(y, dtype=float))
    n = y.size
    tot = float(((y - y.mean()) ** 2).sum())
    if n < 2 or tot <= 0:
        return 1.0
    c1, c2 = np.cumsum(y), np.cumsum(y * y)
    k = np.arange(1, n)
    left = c2[:-1] - c1[:-1] ** 2 / k
    right = (c2[-1] - c2[:-1]) - (c1[-1] - c1[:-1]) ** 2 / (n - k)
    return float((left + right).min() / tot)


def bimodality_test(y, draws=None, seed=0):
    """Is the 1-D sample more split than any unimodal one? The best two-way
    split's cluster index (`ci_1d`) against the same on `draws` uniform samples
    of the same size — the uniform is the least favourable unimodal shape (a
    flat top splits best), as in the calibration of Hartigan's dip test.
    p = (1 + #uniform splits as good) / (1 + draws). Small p = two modes."""
    draws = BIMODAL_DRAWS if draws is None else draws
    y = np.asarray(y, dtype=float)
    y = y[np.isfinite(y)]
    n = y.size
    if n < 4 or np.ptp(y) <= 0:
        return {"ci": None, "p": None, "draws": 0, "null_median": None}
    obs = ci_1d(y)
    rng = null_rng(seed, 89)
    null = np.array([ci_1d(rng.uniform(size=n)) for _ in range(int(draws))])
    return {"ci": obs, "p": float((1 + np.sum(null <= obs)) / (1 + int(draws))), "draws": int(draws),
            "null_median": float(np.median(null))}


def _split_modes(A, lab, seed):
    """`bimodality_test` on the rows projected onto the line through the two
    2-means centroids: is the split two modes along its own direction, or one
    stretched family cut in half?"""
    if len(np.unique(lab)) < 2:
        return {"ci": None, "p": None, "draws": 0, "null_median": None}
    d = A[lab == 1].mean(axis=0) - A[lab == 0].mean(axis=0)
    return bimodality_test(A @ d, BIMODAL_DRAWS, seed)


def _ch(A, lab):
    """Calinski-Harabasz (between / within dispersion, each over its degrees of
    freedom) — sklearn's `calinski_harabasz_score`, without the import."""
    n, ks = len(A), np.unique(lab)
    k = len(ks)
    if k < 2 or k >= n:
        return float("nan")
    mu = A.mean(axis=0)
    b = w = 0.0
    for c in ks:
        X = A[lab == c]
        mc = X.mean(axis=0)
        b += len(X) * float(((mc - mu) ** 2).sum())
        w += float(((X - mc) ** 2).sum())
    return float(b * (n - k) / (w * (k - 1))) if w > 0 else float("inf")


def two_means_ci(X, n_init, seed, n_components=SPLIT_COMPONENTS):
    """`(labels, ci)`: 2-means on the rows of X and its cluster index (within
    over total sum of squares, in the full space). The 2-means runs on the
    rows' top `n_components` principal components (a split of z-normalised
    cycles lies along the first few; it costs 1/8 of the full-space fit on a
    1,000-cycle stack), the same for the real stack and every null stack."""
    X = np.asarray(X, dtype=float)
    Xc = X - X.mean(axis=0)
    tot = float((Xc ** 2).sum())
    if tot <= 0 or len(X) < 2:
        return np.zeros(len(X), dtype=int), 1.0
    q = int(min(n_components, X.shape[1], len(X) - 1))
    w, V = np.linalg.eigh(Xc.T @ Xc)
    P = Xc @ V[:, ::-1][:, :q]
    lab, _ = kmeans(P, 2, n_init, seed)
    within = 0.0
    for c in np.unique(lab):
        R = Xc[lab == c]
        within += float(((R - R.mean(axis=0)) ** 2).sum())
    return lab, within / tot


def _null_cis(null_stacks, size, seed):
    """2-means cluster indices of the K null's stacks, each cut to `size` rows
    (a seeded subset) so a node of a bisection meets a null of its own size."""
    out = []
    for b, N in enumerate(null_stacks):
        N = np.asarray(N, dtype=float)
        if len(N) > size:
            N = N[np.sort(null_rng(seed, 300 + b).choice(len(N), size, replace=False))]
        if len(N) < 4:
            continue
        out.append(two_means_ci(N, NULL_KMEANS_REPLICATES, seed + 7 * b)[1])
    return out


def _gate(X, lab, ci, null_stacks, alpha, min_size, seed):
    """One split's test (module docstring, step 7): below every null draw's
    cluster index, two modes along its own direction, both halves >= min_size."""
    nulls = _null_cis(null_stacks, len(X), seed)
    mode = _split_modes(X, lab, seed)
    sizes = sorted(int(np.sum(lab == c)) for c in (0, 1))
    # the verdict's own rule (`_beats`): below every draw AND more than VERDICT_SPREADS robust SDs below
    # their median - "below every one of 20" alone lets about one noise stack in 20 through
    below = bool(nulls) and bool(_beats(ci, _null_summary(nulls)))
    ok = bool(below and mode["p"] is not None and mode["p"] < alpha and sizes[0] >= int(min_size))
    return ok, {"size": int(len(X)), "children": sizes, "ci": float(ci),
                "null_ci_min": float(min(nulls)) if nulls else None,
                "null_ci_median": float(np.median(nulls)) if nulls else None, "null_draws": len(nulls),
                "null_ci_values": [float(v) for v in nulls], "below_every_null": below, "bimodal_p": mode["p"],
                "alpha": float(alpha), "split": ok}


def choose_groups(A, null_stacks=(), k_max=K_MAX, sigclust_draws=SIGCLUST_DRAWS, seed=0, min_size=MIN_CYCLES,
                  null_source=None, also_stacks=None):
    """`(labels 1..K by size, K, sigclust dict, extra)` (module docstring, step 7).

    The gate: the real stack's 2-means split must have a cluster index below
    every one of the K null's stacks' (`null_stacks`: the background draws, or
    phase-randomised copies of the cycles when the background fell back) — the
    null reproduces what z-normalising noise cycles does (they are sign-
    bimodal along their first component) — AND be two modes along its own
    direction (the uniform-calibrated mode test, which keeps one family that
    varies together), AND leave at least `min_size` cycles on each side. Past
    it, each group is split again under the same three tests at alpha x
    (n_node - 1) / (n - 1) (Kimes et al. 2017's sequential rule), the null cut
    to the node's size; at most `k_max` groups, settled by one Lloyd pass.
    SigClust and the paper's Calinski-Harabasz choice are reported, not used.
    No null stack -> K = 1 (`extra["k_reason"]` says why)."""
    A = np.asarray(A, dtype=float)
    n = len(A)
    null_stacks = list(null_stacks or [])
    sc = sigclust(A, sigclust_draws, seed, replicates=SIGCLUST_REPLICATES)
    sc.pop("labels2")
    labels2, ci2 = two_means_ci(A, KMEANS_REPLICATES, seed)
    ch, fits = {}, {}
    for kk in range(2, int(k_max) + 1):
        if kk >= n:
            break
        lab = labels2 if kk == 2 else kmeans(A, kk, CH_REPLICATES, seed)[0]   # reported only
        if len(np.unique(lab)) < 2:
            continue
        fits[kk] = lab
        ch[kk] = _ch(A, lab)
    k_ch = max(ch, key=ch.get) if ch else None
    labels = np.zeros(n, dtype=int)
    splits = []
    reason = None
    if not null_stacks:
        reason = "no null to calibrate a split against (no background draw and no phase copy): K = 1, not tested"
        ok = False
    else:
        ok, rec = _gate(A, labels2, ci2, null_stacks, SIGCLUST_ALPHA, min_size, seed)
        if also_stacks:
            ok2, rec2 = _gate(A, labels2, ci2, also_stacks, SIGCLUST_ALPHA, min_size, seed)
            rec["also"] = {k: rec2[k] for k in ("null_ci_min", "null_ci_median", "null_draws", "below_every_null")}
            ok = ok and ok2
            rec["split"] = ok
        splits.append(rec)
    sc["bimodality"] = {"p": splits[0]["bimodal_p"]} if splits else None
    if ok:
        leaves = [np.flatnonzero(labels2 == 0), np.flatnonzero(labels2 == 1)]
        queue = list(leaves)
        while queue and len(leaves) < int(k_max):
            node = queue.pop(0)
            if len(node) < 2 * int(min_size):
                continue
            alpha = SIGCLUST_ALPHA * (len(node) - 1) / float(n - 1)
            lab, ci = two_means_ci(A[node], NULL_KMEANS_REPLICATES, seed + len(splits))
            ok_n, rec = _gate(A[node], lab, ci, null_stacks, alpha, min_size, seed + len(splits))
            if also_stacks and ok_n:
                ok_n = _gate(A[node], lab, ci, also_stacks, alpha, min_size, seed + len(splits))[0]
                rec["split"] = ok_n
            splits.append(rec)
            if ok_n:
                kids = [node[lab == 0], node[lab == 1]]
                leaves = [lf for lf in leaves if lf is not node] + kids
                queue += kids
        for c, lf in enumerate(leaves):
            labels[lf] = c
        if len(leaves) > 2:   # one Lloyd pass from the leaves' centroids settles the boundaries
            C = np.array([A[lf].mean(axis=0) for lf in leaves])
            D = ((A[:, None, :] - C[None, :, :]) ** 2).sum(axis=2)
            new = np.argmin(D, axis=1)
            if len(np.unique(new)) == len(leaves):
                labels = new
    # 1..K by size, largest first; ties by first appearance
    uniq = list(dict.fromkeys(labels.tolist()))
    order = sorted(uniq, key=lambda u: (-int(np.sum(labels == u)), uniq.index(u)))
    remap = {u: i + 1 for i, u in enumerate(order)}
    extra = {"ch_curve": {str(k): v for k, v in ch.items()}, "k_ch": k_ch, "splits": splits,
             "k_null": {"source": null_source if null_stacks else None, "draws": len(null_stacks),
                        "values": (splits[0]["null_ci_values"] if splits else []),
                        "ci": float(ci2), "reason": reason}}
    return np.array([remap[v] for v in labels], dtype=int), len(order), sc, extra


# ── plateau measures ────────────────────────────────────────────────────────

def plateau(w, floor_band=FLOOR_BAND, ref=0.0):
    """`(floor_frac, half_recovery_frac)` of one warped cycle (module docstring,
    step 9). `ref` is the pre-drop level: 0 for a chord-detrended cycle (the
    chord runs through it at both ends); None = the median of its first
    `END_FRAC` (an undetrended cycle)."""
    from scipy.ndimage import median_filter
    w = np.asarray(w, dtype=float)
    n = w.size
    sm = median_filter(w, size=SMOOTH_POINTS, mode="nearest")
    m = int(np.argmin(sm))
    lo, hi = float(sm[m]), float(sm.max())
    R = hi - lo
    if R <= 0:
        return float("nan"), float("nan")
    # the floor: from the first sample in the band to the last one before the climb's top (the highest
    # point after the deepest one), so the start of the NEXT drop at a cycle's end (a late anchor) is
    # not read as more floor, and a wander out of the band and back is not read as the climb
    top = m + int(np.argmax(sm[m:]))
    inband = np.flatnonzero(sm[:top + 1] <= lo + floor_band * R)
    floor = (int(inband[-1]) - int(inband[0]) + 1) / float(n)
    if ref is None:
        ref = float(np.median(sm[:max(2, int(round(END_FRAC * n)))]))
    half = lo + 0.5 * (float(ref) - lo)
    after = np.flatnonzero(sm[m:] >= half) if ref > lo else np.array([], dtype=int)
    hr = (m + int(after[0])) / float(n) if after.size else float("nan")
    return float(floor), float(hr)


# ── sequences and cycles ────────────────────────────────────────────────────

def _local_median(lengths, window=LOCAL_CYCLES):
    lengths = np.asarray(lengths, dtype=float)
    h = int(window) // 2
    return np.array([np.median(lengths[max(0, i - h):i + h + 1]) for i in range(len(lengths))])


def sequences_of(features, n, anchors):
    """`(keys, basis)`: each event's sequence key (None = in no sequence) and what
    defined them ('train_id', 'group' or 'span')."""
    if features is not None and "train_id" in features.columns:
        tid = np.asarray(features["train_id"], dtype=float)
        keys = [int(t) if np.isfinite(t) and t >= 0 else None for t in tid]
        basis = "train_id"
    elif features is not None and "group" in features.columns:
        keys = [str(g) for g in features["group"]]
        basis = "group"
    else:
        keys = ["all"] * n
        basis = "span"
    return keys, basis


def _rules(floor_band, max_shift_frac, max_cycle_s, min_cycle_s):
    lim = (f"longer than {max_cycle_s:g} s" if max_cycle_s > 0
           else f"longer than {AUTO_MAX_MULT:g} x the running median of the {LOCAL_CYCLES} cycle lengths around it")
    low = (f"shorter than {min_cycle_s:g} s" if min_cycle_s > 0
           else f"shorter than {AUTO_MIN_MULT:g} x that running median")
    return [
        {"name": "cycle", "rule": "from one event's anchor (its onset, else its span start) to the next event's in the "
                                  "same sequence (a train, else a group, else the span); the event that opens a cycle "
                                  f"carries it. A cycle {lim} is a gap and one {low} (or under {MIN_CYCLE_SAMPLES} "
                                  "samples) a split: both are left out and counted, as are cycles more than the "
                                  "allowed fraction missing"},
        {"name": "cycle_index", "rule": "the cycle's position in its sequence, 0 first; -1 = the event opens no cycle "
                                        "(the last of its sequence, or in no train); bookkeeping, never a feature"},
        {"name": "cycle_length_s", "rule": "anchor to next anchor after the refinement, in seconds"},
        {"name": "cycle_amplitude", "rule": "peak to peak of the chord-detrended cycle, in the waveform's stored unit "
                                            "(the size the warp removes)"},
        {"name": "cycle_group", "rule": "1..K by size within its sequence, from k-means on the warped cycles. K > 1 only "
                                        "when the best two-way split splits better than the same 2-means on every "
                                        "draw of the K null (the background draws; per-cycle phase copies when the "
                                        "background fell back - meta k_null.source says which) by more than 3 robust "
                                        "SDs, AND is two modes along its own direction (against uniform samples, the "
                                        "flattest one-mode shape), AND leaves at least min_cycles on each side; groups "
                                        "are split again under the same tests at a stricter alpha (Kimes et al. 2017), "
                                        "at most k_max. A shape that drifts steadily stays one group. SigClust is "
                                        "reported, not used. -1 = no group (left out, opens no cycle, or the sequence "
                                        "had too few cycles); bookkeeping"},
        {"name": "cycle_change", "rule": "the cycle's group differs from the previous used cycle's in its sequence; "
                                         "bookkeeping"},
        {"name": "cycle_shift_s", "rule": f"seconds the cycle's content moved later to line up: the anchor refinement "
                                          f"plus the final alignment to its group's medoid, each bounded by "
                                          f"{max_shift_frac:g} of the cycle; bookkeeping"},
        {"name": "cycle_corr", "rule": "correlation of the aligned, warped cycle with its group's medoid cycle; "
                                       "bookkeeping (a clustering's answer, as family_distance)"},
        {"name": "cycle_floor_frac", "rule": f"share of the cycle (0-1) from the first sample within the lowest "
                                             f"{floor_band:g} of the cycle's range (a placeholder band) to the last one "
                                             f"before the climb's top (the highest point after the deepest one), on the "
                                             f"warped, chord-detrended cycle after a {SMOOTH_POINTS}-point running "
                                             f"median. A flat floor of share f climbing linearly over a share c reads "
                                             f"about f + {floor_band:g} c. A sharkfin sits on its floor for 1/2-2/3 of "
                                             f"the interval"},
        {"name": "cycle_half_recovery_frac", "rule": "where in the cycle (0-1) the trace first gets back half way from "
                                                     "its deepest point to its pre-drop level (the chord: the median of "
                                                     f"the {END_FRAC:g} of the cycle before each anchor); NaN = never "
                                                     "half back (counted per sequence). A trough is mostly back by the "
                                                     "quarter point"},
        {"name": "coherence", "rule": "SVD entropy of the stacked cycles: sigma^2 variant (p_i = sigma_i^2 / sum) "
                                      "first, eq. 17 (Colominas & Wu 2023, p_i = sigma_i / sum) beside it; 0 = copies "
                                      "of one shape; normalised by ln min(P, L). At three points: fixed-length cuts "
                                      "from each anchor, after warping, after alignment. The stack is aligned here, "
                                      "so svd_entropy runs with align=False"},
        {"name": "verdict", "rule": f"beyond_noise = eq. 17 below every draw of the background null AND below the "
                                    f"draws' median by more than {VERDICT_SPREADS:g} robust SDs of the draws - a "
                                    "1-in-20 test (20 draws: about one noise stack in 20 lies below all of them). The "
                                    "background null: pseudo-cycles cut where no event lies, lengths drawn from the "
                                    "real cycles', through the same chord, warp, refinement and alignment - so "
                                    "'beyond the background' means unlike the quiet margins, not necessarily unlike "
                                    "the chain's own noise. beyond_noise_squared = the same on sigma^2. A group's key "
                                    "is unmarked only when BOTH pass; else ~noise_like. A group's null went through "
                                    "the same K-means as the group on every background draw, groups matched by "
                                    "entropy rank (the lowest-entropy real group against the lowest-entropy null "
                                    "group). The colour check: sigma^2 of the stack against per-cycle phase copies of "
                                    "its own cycles (their local colour; sigma^2 only, eq. 17 is never read against "
                                    "them); beating the background but not these copies sets "
                                    "background_colour_mismatch and keys the groups ~untested. When more than half "
                                    "the pseudo-cycles fitted no free stretch the verdicts are untested (they would "
                                    "be random-phase cuts of the chain); below that they are tested, and "
                                    "background.fallback_share says how many pseudo-cycles were such random-phase "
                                    f"cuts. beyond_noise_margin is the Library's eq. 17 < {NULL_MARGIN} x null p05, "
                                    "for comparison only. The trend-kept null is shown with its caveat: "
                                    + SMOOTH_CAVEAT + "; the plain phase null destroys a smooth curve's shape"},
        {"name": "order", "rule": "runs of equal groups in time order against shuffles of the cycle order within the "
                                  "sequence; p = (1 + shuffles with as few runs) / (1 + shuffles). Tests order, not "
                                  "shape: a slow drift of shape also makes runs"},
    ]


def _null_summary(vals):
    vals = np.asarray([v for v in vals if v is not None and np.isfinite(v)], dtype=float)
    if not vals.size:
        return {"median": None, "p05": None, "min": None, "spread": None, "draws": 0}
    mad = float(np.median(np.abs(vals - np.median(vals)))) * 1.4826
    return {"median": float(np.median(vals)), "p05": float(np.percentile(vals, 5)), "min": float(vals.min()),
            "spread": mad, "draws": int(vals.size)}


def _coherence(rows, n_points, trend_draws=0, seed=0):
    out = svd_entropy(rows, align=False, resample_length=n_points, seed=seed, null_draws=trend_draws)
    return {k: out[k] for k in ("svd_entropy_squared_norm", "svd_entropy_norm", "top_share", "n_used",
                                 "null_median", "null_p05", "null_squared_median", "null_draws", "reason")}


def _phase_null(F, n_points, draws, seed):
    rng = null_rng(seed, 61)
    h, hs = [], []
    for _ in range(int(draws)):
        e = entropy_pair(_z_rows(phase_randomised_rows(F, rng)))
        h.append(e[0])
        hs.append(e[1])
    return h, hs


def _beats(h, s):
    """The verdict rule against one null summary (module docstring, step 10)."""
    if h is None or not np.isfinite(h) or s["draws"] == 0:
        return None
    floor = max(s["spread"], VERDICT_SPREAD_FLOOR * max(abs(s["median"]), 1e-12))
    return bool(h < s["min"] and (s["median"] - h) > VERDICT_SPREADS * floor)


def _verdict(h17, hsq, bg17, bgsq, reason=None):
    s17, ssq = _null_summary(bg17), _null_summary(bgsq)
    if reason is not None or s17["draws"] == 0 or h17 is None or not np.isfinite(h17):
        return {"tested": False, "beyond_noise": None, "beyond_noise_squared": None, "below_every_draw": None,
                "below_every_draw_squared": None, "beyond_noise_margin": None, "null_margin": NULL_MARGIN,
                "spreads": VERDICT_SPREADS,
                "reason": reason or ("no background draw" if s17["draws"] == 0 else "no entropy to test")}
    return {"tested": True, "reason": None, "beyond_noise": _beats(h17, s17), "beyond_noise_squared": _beats(hsq, ssq),
            "below_every_draw": bool(h17 < s17["min"]),
            "below_every_draw_squared": bool(hsq < ssq["min"]) if ssq["draws"] else None,
            "z": (float((s17["median"] - h17) / s17["spread"]) if s17["spread"] else None),
            "z_squared": (float((ssq["median"] - hsq) / ssq["spread"]) if ssq["draws"] and ssq["spread"] else None),
            # the Library coherence's multiplicative margin, for comparison only (not the verdict here)
            "beyond_noise_margin": bool(h17 < NULL_MARGIN * s17["p05"]), "null_margin": NULL_MARGIN,
            "spreads": VERDICT_SPREADS}


def _runs(g):
    g = np.asarray(g)
    return int(1 + np.sum(g[1:] != g[:-1])) if g.size else 0


def order_test(g, n_perm=N_PERM, seed=0):
    g = np.asarray(g)
    if g.size < 3 or len(np.unique(g)) < 2:
        return {"runs": _runs(g), "p": None, "n_perm": 0,
                "note": "one group (or under 3 cycles): no order to test"}
    rng = null_rng(seed, 71)
    obs = _runs(g)
    perm = [_runs(rng.permutation(g)) for _ in range(int(n_perm))]
    p = float((1 + np.sum(np.asarray(perm) <= obs)) / (1 + int(n_perm)))
    return {"runs": obs, "p": p, "n_perm": int(n_perm), "expected_runs": float(np.mean(perm)),
            "note": "tests order, not shape: a slow drift of shape would also make runs"}


def run_lengths(g):
    g = list(g)
    out = []
    for v in g:
        if out and out[-1][0] == v:
            out[-1][1] += 1
        else:
            out.append([v, 1])
    return [{"group": int(a), "cycles": int(b)} for a, b in out]


def group_key(base, verdict, colour_mismatch):
    """The Intervals key of a group: unmarked only when eq. 17 AND sigma^2 both beat the background null
    (decision 18 - eq. 17 stays in the verdict, sigma^2 is added, so stricter, never looser) and the
    background is of the chain's own colour (decision 17); `~untested` when no verdict could be drawn or
    the colours differ; `~noise_like` otherwise."""
    if not verdict.get("tested") or colour_mismatch:
        return base + UNTESTED_SUFFIX
    if not (verdict.get("beyond_noise") and verdict.get("beyond_noise_squared")):
        return base + NOISE_LIKE_SUFFIX
    return base


def _nan_last(v):
    return v if v is not None and np.isfinite(v) else np.inf


def group_nulls(null_stacks, K, max_shift, seed):
    """For each background draw: the same K-means (K groups) on the draw, each
    null group aligned on its own, and its `(eq17s, squareds)` sorted ascending
    — so a real group is judged against the null group of its own rank (the
    lowest-entropy real group against the lowest-entropy null group): a null
    that went through the same selection (W3-B critic, S2)."""
    out = []
    for b, N in enumerate(null_stacks):
        lab, _ = kmeans(N, K, NULL_KMEANS_REPLICATES, seed + 11 * b)
        e17, esq = [], []
        for c in range(K):
            rows = N[lab == c]
            if len(rows) < 2:
                e17.append(float("nan"))
                esq.append(float("nan"))
                continue
            e = entropy_pair(align_stack(rows, max_shift, seed)[0])
            e17.append(e[0])
            esq.append(e[1])
        out.append((sorted(e17, key=_nan_last), sorted(esq, key=_nan_last)))
    return out


def _bg_block(v17, vsq, dropped, matched=None):
    """The background null as meta: each statistic's summary plus every draw's
    value (NaN -> None in json_safe), and the draws dropped for holding fewer
    than two preparable windows."""
    e, q = _null_summary(v17), _null_summary(vsq)
    e["values"] = [float(v) for v in v17]
    q["values"] = [float(v) for v in vsq]
    out = {"eq17": e, "squared": q, "draws_dropped": int(dropped)}
    if matched is not None:
        out["matched"] = matched
    return out


def phase_cycle_stacks(trace, starts, ends, n_points, detrend, max_nan_frac, draws, seed):
    """The K null when the background fell back: per-cycle phase-randomised
    copies of the real cycles, made BEFORE the chord. Each cycle's raw cut is
    phase-randomised (its spectrum kept: `kshape.phase_randomised_rows`), then
    chord-detrended exactly as a real cycle (the copy spans the `END_FRAC` before
    the anchor too, so its start level is read where the real one is), warped and
    z-normalised like a real cycle. Randomising after the chord does NOT work:
    a chord-detrended noise cycle is bridge-like, its first component a
    half-sine that z-normalising maps to +-1 (sign-bimodal), while a Fourier
    phase surrogate of it turns that component into a ring of phases — real
    noise then splits better than every copy (K = 2 in 3 of 10 AR(1) chains
    that filled their span, measured). Copied before the chord, the copy is
    bridge-like again and splits like the real noise."""
    rng = null_rng(seed, 211)
    n_tr = len(trace)
    segs = []
    for a, b in zip(starts, ends):
        a, b = int(a), int(b)
        L = b - a
        k = max(2, int(round(END_FRAC * L)))
        lead = min(k, a)                       # the real chord's start level: the k samples BEFORE the anchor
        pad0 = min(L // 2, a - lead)           # half a cycle either side, so the copy's ends are not neighbours
        pad1 = min(L // 2, n_tr - b)           # on the FFT's circle (a circular copy has matching ends, a flat
        seg = np.asarray(trace[a - lead - pad0:b + pad1], dtype=float)   # chord and too weak a first component)
        bad = ~np.isfinite(seg)
        if bad.any():
            i = np.arange(seg.size)
            seg = seg.copy()
            seg[bad] = np.interp(i[bad], i[~bad], seg[~bad])
        q = max(1, L // (4 * int(n_points)))   # long cycles (10 Hz) are block-averaged by q first: the copy only
        if q > 1:                              # needs the resolution the warp keeps (and an FFT of ~6 x n_points)
            m = seg.size // q
            seg = seg[:m * q].reshape(m, q).mean(axis=1)
            pad0, lead, L, k = pad0 // q, max(1, lead // q) if lead else 0, max(2, L // q), max(1, k // q)
        segs.append((seg, pad0, lead, L, k))
    out = []
    for _ in range(int(draws)):
        rows = []
        for seg, pad0, lead, L, k in segs:
            sur = phase_randomised_rows(seg[None, :], rng)[0]
            cyc = sur[pad0 + lead:pad0 + lead + L]
            if detrend == "chord":
                a0 = _median(sur[pad0:pad0 + lead]) if lead else _median(cyc[:k])
                b0 = _median(cyc[-k:])
                cyc = cyc - (a0 + (b0 - a0) * np.linspace(0.0, 1.0, cyc.size))
            rows.append(resample_to_length(cyc, int(n_points)))
        out.append(_z_rows(np.asarray(rows)))
    return out


# ── the main entry ──────────────────────────────────────────────────────────

def cycle_shapes(x, fs, starts, ends, features=None, *, waveform=None, anchor="onset", max_cycle_s=0.0,
                 min_cycle_s=0.0, cycle_detrend="chord", n_points=N_POINTS, max_shift_frac=MAX_SHIFT_FRAC,
                 max_iter=MAX_ITER, k_max=K_MAX, min_cycles=MIN_CYCLES, sigclust_draws=SIGCLUST_DRAWS,
                 null_draws=NULL_DRAWS, n_perm=N_PERM, floor_band=FLOOR_BAND, max_nan_frac=MAX_NAN_FRAC, seed=0,
                 should_cancel=None):
    """The whole block (module docstring). `starts` / `ends` are the events'
    span-relative samples, `features` the SpanSet's table (or None).

    Returns `{"columns": {name: array per event}, "meta": {...}, "group_keys":
    [key per event, "-1" for none]}`."""
    t0 = time.time()
    if anchor not in ANCHORS:
        raise ValueError(f"cycle_shapes anchor must be one of {ANCHORS}; got {anchor!r}.")
    if cycle_detrend not in DETRENDS:
        raise ValueError(f"cycle_shapes cycle_detrend must be one of {DETRENDS}; got {cycle_detrend!r}.")
    fs = float(fs)
    trace = np.asarray(x if waveform is None else waveform, dtype=float).ravel()
    n_ev = len(starts)
    starts = np.asarray(starts, dtype=np.int64)
    ends = np.asarray(ends, dtype=np.int64)
    use_onset = anchor == "onset" and features is not None and "onset_idx" in features.columns
    anc = (np.asarray(features["onset_idx"], dtype=float) if use_onset else starts.astype(float))
    keys, basis = sequences_of(features, n_ev, anc)

    cols = {"cycle_index": np.full(n_ev, -1, dtype=np.int64), "cycle_length_s": np.full(n_ev, np.nan),
            "cycle_amplitude": np.full(n_ev, np.nan), "cycle_group": np.full(n_ev, -1, dtype=np.int64),
            "cycle_change": np.zeros(n_ev, dtype=bool), "cycle_shift_s": np.full(n_ev, np.nan),
            "cycle_corr": np.full(n_ev, np.nan), "cycle_floor_frac": np.full(n_ev, np.nan),
            "cycle_half_recovery_frac": np.full(n_ev, np.nan)}
    omit = [""] * n_ev
    group_keys = ["-1"] * n_ev
    exemplars = {}
    stack_rows = []
    seq_meta = []
    warnings = []

    # sequences, in first-seen order; events sorted by anchor within each
    order = {}
    for i in range(n_ev):
        if keys[i] is None:
            omit[i] = OMIT_NO_SEQUENCE
            continue
        if not np.isfinite(anc[i]):
            omit[i] = OMIT_NO_ANCHOR
            continue
        order.setdefault(keys[i], []).append(i)
    seq_list = list(order.items())
    prefix_train = basis == "train_id" and len(seq_list) > 1

    # the avoid list for the background: every event span, in the trace's frame
    avoid = list(zip(starts.tolist(), ends.tolist()))

    for si, (skey, idx) in enumerate(seq_list):
        _check(should_cancel)
        idx = np.asarray(idx, dtype=np.int64)
        idx = idx[np.argsort(anc[idx], kind="stable")]
        a_samp = np.round(anc[idx]).astype(np.int64)
        opener, cstart, cend = idx[:-1], a_samp[:-1], a_samp[1:]
        omit[int(idx[-1])] = OMIT_NO_CYCLE
        m = len(opener)
        sm = {"key": skey if not isinstance(skey, (np.integer,)) else int(skey), "n_events": int(len(idx)),
              "n_cycles": int(m), "n_used": 0, "omitted": {}, "k": None}
        for j in range(m):
            cols["cycle_index"][opener[j]] = j
        lens = (cend - cstart).astype(float)
        cols["cycle_length_s"][opener] = lens / fs
        reasons = [None] * m
        if m:
            loc = _local_median(lens)
            hi = max_cycle_s * fs if max_cycle_s > 0 else AUTO_MAX_MULT * loc
            lo = min_cycle_s * fs if min_cycle_s > 0 else AUTO_MIN_MULT * loc
            for j in range(m):
                if lens[j] < MIN_CYCLE_SAMPLES or lens[j] < (lo if np.isscalar(lo) else lo[j]):
                    reasons[j] = OMIT_SHORT
                elif lens[j] > (hi if np.isscalar(hi) else hi[j]):
                    reasons[j] = OMIT_LONG
                elif cend[j] > len(trace):
                    reasons[j] = OMIT_NAN
                else:
                    _, a, r = prepare_cycle(trace, cstart[j], cend[j], n_points, cycle_detrend, max_nan_frac)
                    cols["cycle_amplitude"][opener[j]] = a
                    reasons[j] = r
        used = np.array([r is None for r in reasons], dtype=bool)
        for j in range(m):
            if reasons[j]:
                omit[opener[j]] = reasons[j]
                sm["omitted"][reasons[j]] = sm["omitted"].get(reasons[j], 0) + 1
        n_long = sm["omitted"].get(OMIT_LONG, 0)
        if m and n_long > GAP_WARN_SHARE * m:
            warnings.append(f"sequence {sm['key']}: {n_long} of {m} cycles ({n_long / m:.0%}) left out as gaps - "
                            "the longest cycles are the ones lost (long plateaus); set max_cycle_s if they are real")
        u = np.flatnonzero(used)
        sm["n_used"] = int(u.size)
        if u.size == 0:
            sm["reason"] = "no usable cycle"
            seq_meta.append(sm)
            continue
        # contiguous links among the used cycles: cycle j's end is cycle j+1's start
        pos = {int(j): q for q, j in enumerate(u)}
        next_of = np.array([pos.get(int(j) + 1, -1) for j in u], dtype=np.int64)
        W, amps, rs, re_, history, stopped = refine(
            trace, cstart[u], cend[u], next_of, n_points=n_points, detrend=cycle_detrend, max_nan_frac=max_nan_frac,
            max_shift_frac=max_shift_frac, max_iter=max_iter, seed=seed, should_cancel=should_cancel)
        ev_u = opener[u]
        cols["cycle_length_s"][ev_u] = (re_ - rs) / fs
        cols["cycle_amplitude"][ev_u] = amps
        for q in range(len(u)):
            f, h = plateau(W[q], floor_band, 0.0 if cycle_detrend == "chord" else None)
            cols["cycle_floor_frac"][ev_u[q]] = f
            cols["cycle_half_recovery_frac"][ev_u[q]] = h
        sm.update(iterations=history, stopped=stopped,
                  refinement_moved_s={"median": float(np.median(np.abs(rs - cstart[u]))) / fs,
                                      "max": float(np.max(np.abs(rs - cstart[u]))) / fs})
        sm["floor_trend"] = kendall_trend(rs / fs, cols["cycle_floor_frac"][ev_u])
        sm["n_half_recovery_unmeasured"] = int(np.sum(~np.isfinite(cols["cycle_half_recovery_frac"][ev_u])))
        if u.size < int(min_cycles):
            sm["reason"] = (f"{u.size} usable cycle(s), fewer than the {int(min_cycles)} a shape grouping needs: no K "
                            "is reported, the cycles keep their measures and no group")
            for e in ev_u:
                omit[e] = OMIT_FEW
            seq_meta.append(sm)
            continue

        ms = max(1, int(round(max_shift_frac * n_points)))
        Z = _z_rows(W)
        A, gshift, gmed = align_stack(Z, ms, seed)
        _check(should_cancel)

        # fixed-length cuts from each anchor: the plain baseline
        Lfix = int(np.median(cend[u] - cstart[u]))
        fixed, _, rf = _prepare_all(trace, cstart[u], np.minimum(cstart[u] + Lfix, len(trace)), n_points,
                                    cycle_detrend, max_nan_frac)
        fixed_ok = np.array([r is None for r in rf])

        # the background null: whole-stack draws (drawn first: K is calibrated on them)
        bg17, bgsq, bg_W, bg_report, dropped = [], [], [], None, 0
        lens_u = (re_ - rs).astype(np.int64)
        for b in range(int(null_draws)):
            _check(should_cancel)
            smp = sample_background(trace, avoid, lens_u, len(u), seed=[int(seed), 97, si, b], fs=fs)
            if bg_report is None:
                bg_report = dict(smp.report)
                bg_report["n_fallback_total"] = 0
            bg_report["n_fallback_total"] += smp.report["n_fallback"]
            keep_b = []
            for q in range(len(smp.starts)):
                w, _, r = prepare_cycle(trace, smp.starts[q], smp.starts[q] + smp.lengths[q], n_points,
                                        cycle_detrend, max_nan_frac)
                if r is None:
                    keep_b.append(q)
            if len(keep_b) < 2:
                dropped += 1
                continue
            bs, be = smp.starts[keep_b], smp.starts[keep_b] + smp.lengths[keep_b]
            Wb, _, _, _, _, _ = refine(trace, bs, be, np.full(len(keep_b), -1), n_points=n_points,
                                       detrend=cycle_detrend, max_nan_frac=max_nan_frac,
                                       max_shift_frac=max_shift_frac, max_iter=max_iter, seed=seed + 1000 + b)
            Zb = _z_rows(Wb)
            Ab, _, _ = align_stack(Zb, ms, seed)
            e17, esq = entropy_pair(Ab)
            bg17.append(e17)
            bgsq.append(esq)
            bg_W.append(Zb)
        untested_reason = None
        if bg_report is not None:
            bg_report["draws"] = int(len(bg17))
            bg_report["draws_dropped"] = int(dropped)
            bg_report["fell_back_any"] = bool(bg_report["n_fallback_total"])
            bg_report["fallback_share"] = (bg_report["n_fallback_total"] / float(max(1, int(null_draws) * len(u))))
            cyc_s = float(np.median(lens_u)) / fs
            if bg_report["fallback_share"] > FALLBACK_LIMIT:
                lf = bg_report.get("longest_free_s") or 0.0
                untested_reason = (f"no free stretch as long as a cycle (longest free stretch {lf:.0f} s, cycles "
                                   f"{cyc_s:.0f} s); pseudo-cycles would be random-phase cuts of the chain")
                warnings.append(f"sequence {sm['key']}: {untested_reason} - "
                                f"{bg_report['fallback_share']:.0%} fell back; the verdicts are untested")
            elif bg_report["fell_back_any"]:
                warnings.append(f"sequence {sm['key']}: {bg_report['fallback_share']:.0%} of the background "
                                f"pseudo-cycles fitted no free stretch (longest {bg_report.get('longest_free_s') or 0:.0f} s, "
                                f"cycles {cyc_s:.0f} s) and were cut at random places in the whole span")
        elif int(null_draws) == 0:
            untested_reason = "null_draws = 0: no background null drawn"
        sm["background"] = bg_report
        bg_ok = bool(bg17) and untested_reason is None

        # the K null: the background draws, else per-cycle phase copies (each cycle's spectrum kept)
        # the per-cycle phase copies (local colour): the K null when the background fell back, and the
        # colour check of the background verdict (fix round 2, S-A) when it did not
        pc_stacks = phase_cycle_stacks(trace, rs, re_, n_points, cycle_detrend, max_nan_frac,
                                       int(null_draws) or K_NULL_DRAWS, seed)
        if bg_ok:
            k_stacks, k_source = bg_W, "background"
            k_also = pc_stacks if K_GATE_BOTH else None
        else:
            k_stacks, k_source, k_also = pc_stacks, "phase", None
        _check(should_cancel)
        labels, K, sc, extra = choose_groups(Z, k_stacks, k_max=k_max, sigclust_draws=sigclust_draws, seed=seed,
                                             min_size=min_cycles, null_source=k_source, also_stacks=k_also)
        sm.update(k=int(K), sigclust=sc, **extra)
        if u.size < 2 * int(min_cycles):
            sm["k_note"] = (f"{u.size} usable cycles: a split needs >= 2 x min_cycles ({2 * int(min_cycles)}), so "
                            "K = 1 by construction")

        whole = {"before_warp": _coherence(fixed[fixed_ok], n_points) if fixed_ok.sum() >= 2 else None,
                 "after_warp": _coherence(Z, n_points), "after_align": _coherence(A, n_points, TREND_NULL_DRAWS, seed)}
        ph, phs = _phase_null(A, n_points, PHASE_NULL_DRAWS, seed)
        bgv = (bg17, bgsq) if bg_ok else ([], [])
        whole["nulls"] = {"background": _bg_block(bg17, bgsq, dropped),
                          "trend_kept": {"eq17_median": whole["after_align"]["null_median"],
                                         "eq17_p05": whole["after_align"]["null_p05"],
                                         "squared_median": whole["after_align"]["null_squared_median"],
                                         "caveat": SMOOTH_CAVEAT},
                          "phase": {"eq17": _null_summary(ph), "squared": _null_summary(phs)}}
        whole["verdict"] = _verdict(whole["after_align"]["svd_entropy_norm"],
                                    whole["after_align"]["svd_entropy_squared_norm"], *bgv,
                                    reason=untested_reason)
        # the colour check (S-A): sigma^2 of the aligned stack against the per-cycle phase copies, which keep
        # each cycle's OWN spectrum. sigma^2 only - eq. 17 is never read against this null.
        pc_sq = [entropy_pair(align_stack(P, ms, seed)[0])[1] for P in pc_stacks]
        pcs = _null_summary(pc_sq)
        pcs["values"] = [float(v) for v in pc_sq]
        beats_pc = _beats(whole["after_align"]["svd_entropy_squared_norm"], pcs)
        whole["nulls"]["phase_cycles"] = {"squared": pcs, "beyond_squared": beats_pc,
                                          "rule": "sigma^2 only: per-cycle phase copies keep each cycle's own "
                                                  "spectrum (its local colour); eq. 17 is never read against them"}
        v = whole["verdict"]
        mismatch = bool(v["tested"] and (v["beyond_noise"] or v["beyond_noise_squared"]) and not beats_pc)
        v["beyond_phase_cycles_squared"] = beats_pc
        v["background_colour_mismatch"] = mismatch if v["tested"] else None
        sm["background_colour_mismatch"] = v["background_colour_mismatch"]
        if mismatch:
            warnings.append(f"sequence {sm['key']}: the chain's background differs in colour from the quiet margins: "
                            "beyond the margins, not beyond its own noise (groups keyed ~untested)")
        sm["whole"] = whole

        # per group: the group's null matches its selection (the same K-means on every background draw)
        prefix = f"t{sm['key']}:" if prefix_train else ""
        groups = []
        Ffinal = A.copy()
        fshift = gshift.copy()
        aligned = {}
        for g in range(1, K + 1):
            gi = np.flatnonzero(labels == g)
            if K > 1:
                aligned[g] = align_stack(Z[gi], ms, seed)
            else:
                aligned[g] = (A, gshift, gmed)
        matched = group_nulls(bg_W, K, ms, seed) if (bg_ok and K > 1) else None
        real_g = {g: entropy_pair(aligned[g][0]) for g in range(1, K + 1)}
        rank17 = {g: r for r, g in enumerate(sorted(real_g, key=lambda q: _nan_last(real_g[q][0])))}
        ranksq = {g: r for r, g in enumerate(sorted(real_g, key=lambda q: _nan_last(real_g[q][1])))}
        for g in range(1, K + 1):
            gi = np.flatnonzero(labels == g)
            Ag, sh_g, mg = aligned[g]
            Ffinal[gi] = Ag
            fshift[gi] = sh_g
            corr = (Ag @ Ag[mg]) / float(n_points)
            cols["cycle_corr"][ev_u[gi]] = corr
            if not bg_ok:
                g17, gsq = [], []
            elif K == 1:
                g17, gsq = bg17, bgsq
            else:
                g17 = [d[0][rank17[g]] for d in matched]
                gsq = [d[1][ranksq[g]] for d in matched]
            coh = {"before_warp": (_coherence(fixed[gi][fixed_ok[gi]], n_points)
                                   if fixed_ok[gi].sum() >= 2 else None),
                   "after_warp": _coherence(Z[gi], n_points) if len(gi) >= 2 else None,
                   "after_align": _coherence(Ag, n_points, TREND_NULL_DRAWS, seed) if len(gi) >= 2 else None}
            ph, phs = _phase_null(Ag, n_points, PHASE_NULL_DRAWS, seed + g) if len(gi) >= 2 else ([], [])
            aa = coh["after_align"] or {}
            verdict = _verdict(aa.get("svd_entropy_norm"), aa.get("svd_entropy_squared_norm"), g17, gsq,
                               reason=untested_reason)
            coh["nulls"] = {"background": _bg_block(g17, gsq, dropped if bg_ok else 0,
                                                    matched="K-means with the real K on every background draw, "
                                                            "groups matched by rank of entropy (lowest to lowest)"
                                                    if (bg_ok and K > 1) else ("the whole stack's" if bg_ok else None)),
                            "trend_kept": {"eq17_median": aa.get("null_median"), "eq17_p05": aa.get("null_p05"),
                                           "squared_median": aa.get("null_squared_median"),
                                           "caveat": SMOOTH_CAVEAT},
                            "phase": {"eq17": _null_summary(ph), "squared": _null_summary(phs)}}
            verdict["background_colour_mismatch"] = whole["verdict"]["background_colour_mismatch"]
            coh["verdict"] = verdict
            base = f"{prefix}{g}"
            key = group_key(base, verdict, whole["verdict"]["background_colour_mismatch"])
            med_event = int(ev_u[gi[mg]])
            exemplars[base] = med_event
            for e in ev_u[gi]:
                group_keys[int(e)] = key
            groups.append({"group": g, "key": key, "size": int(len(gi)), "medoid_event": med_event,
                           "floor_frac_median": float(np.nanmedian(cols["cycle_floor_frac"][ev_u[gi]])),
                           "half_recovery_frac_median": (float(np.nanmedian(cols["cycle_half_recovery_frac"][ev_u[gi]]))
                                                         if np.isfinite(cols["cycle_half_recovery_frac"][ev_u[gi]]).any()
                                                         else None),
                           "length_s_median": float(np.median((re_ - rs)[gi])) / fs,
                           "coherence": coh})
        sm["groups"] = groups
        cols["cycle_group"][ev_u] = labels
        tot_shift = (cstart[u] - rs) + np.round(fshift * (re_ - rs) / float(n_points))
        cols["cycle_shift_s"][ev_u] = tot_shift / fs
        change = np.zeros(len(u), dtype=bool)
        change[1:] = labels[1:] != labels[:-1]
        cols["cycle_change"][ev_u] = change
        sm["change_points"] = [int(e) for e in ev_u[change]]
        sm["change_points_s"] = [float(s) / fs for s in rs[change]]
        sm["run_lengths"] = run_lengths(labels)
        sm["order_test"] = order_test(labels, n_perm, seed)
        for q in range(len(u)):
            stack_rows.append((int(ev_u[q]), sm["key"], int(labels[q]), float(rs[q]) / fs,
                               float(re_[q] - rs[q]) / fs, Z[q], Ffinal[q]))
        seq_meta.append(sm)

    # the drawing payload for W3-F
    rng = null_rng(seed, 83)
    sampled = len(stack_rows) > STACK_MAX
    pick = (np.sort(rng.choice(len(stack_rows), STACK_MAX, replace=False)) if sampled
            else np.arange(len(stack_rows)))
    cycle_stack = {
        "n_points": STACK_POINTS, "n_rows": int(len(pick)), "n_cycles": int(len(stack_rows)),
        "sampled": bool(sampled), "seed": int(seed), "time_unit": "seconds from the span start",
        "rows": [{"event": stack_rows[i][0], "sequence": stack_rows[i][1], "group": stack_rows[i][2],
                  "start_s": stack_rows[i][3], "length_s": stack_rows[i][4],
                  "before": np.round(resample_to_length(stack_rows[i][5], STACK_POINTS), 3).tolist(),
                  "after": np.round(resample_to_length(stack_rows[i][6], STACK_POINTS), 3).tolist()}
                 for i in pick]}

    if waveform is None and n_ev:
        warnings.insert(0, "cycles cut from the chain's own signal; if the detector ran on a short-detrended trace, "
                           "bind waveform to the root signal")
    omitted = {}
    for r in omit:
        if r:
            omitted[r] = omitted.get(r, 0) + 1
    meta = {"n_events": int(n_ev), "sequence_basis": basis, "n_sequences": len(seq_list),
            "anchor_used": "onset_idx" if use_onset else "span_start",
            "waveform": "side input" if waveform is not None else "the chain's signal (x)",
            "cycle_detrend": cycle_detrend, "n_points": int(n_points), "headline": "svd_entropy_squared_norm",
            "omitted": omitted, "sequences": seq_meta, "exemplar_events": exemplars, "exemplar_rule": EXEMPLAR_RULE,
            "exemplar_form": '{"<group key without suffix>": <event index into the SpanSet>}',
            "cycle_stack": cycle_stack, "warnings": warnings,
            "rules": _rules(floor_band, max_shift_frac, max_cycle_s, min_cycle_s),
            "seconds": round(time.time() - t0, 3)}
    meta["n_cycles_used"] = int(sum(s.get("n_used", 0) for s in seq_meta))
    meta["summary"] = summary_line(meta)
    return {"columns": cols, "omit_reason": omit, "group_keys": group_keys, "meta": json_safe(meta)}


def json_safe(v):
    """Plain JSON: numpy scalars to Python, NaN / inf to None (a missing value
    says so as null, never as a number a page could draw)."""
    if isinstance(v, dict):
        return {str(k): json_safe(w) for k, w in v.items()}
    if isinstance(v, (list, tuple)):
        return [json_safe(w) for w in v]
    if isinstance(v, np.ndarray):
        return [json_safe(w) for w in v.tolist()]
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return float(v) if np.isfinite(v) else None
    return v


def _f(v, fmt="{:.2f}"):
    return "—" if v is None or (isinstance(v, float) and not np.isfinite(v)) else fmt.format(v)


def summary_line(meta):
    seqs = meta["sequences"]
    if meta["n_events"] == 0:
        return "no events: the step before found none — see its meta for why"
    parts = [f"{meta['n_cycles_used']} cycle(s) used of {sum(s['n_cycles'] for s in seqs)} in "
             f"{len(seqs)} sequence(s)"]
    if meta["omitted"]:
        parts.append("left out: " + ", ".join(f"{k} {v}" for k, v in meta["omitted"].items()))
    for s in seqs:
        if s.get("k") is None:
            if len(seqs) <= 3 and s.get("reason"):
                parts.append(f"sequence {s['key']}: {s['reason']}")
            continue
        w = s["whole"]
        aa = w["after_align"]
        bgn = w["nulls"]["background"]
        v = w["verdict"]
        kn = s.get("k_null") or {}
        line = (f"sequence {s['key']}: K = {s['k']} (split tested against the {kn.get('source') or 'no'} null"
                + (f"; {s['k_note']}" if s.get("k_note") else "") + ") · coherence "
                f"σ² {_f(aa['svd_entropy_squared_norm'])} (background {_f(bgn['squared']['median'])}) · eq. 17 "
                f"{_f(aa['svd_entropy_norm'])} (background {_f(bgn['eq17']['median'])}) · "
                + (f"untested ({v.get('reason')})" if not v["tested"]
                   else ("beyond noise" if v["beyond_noise"] else "no better than noise") + " on eq. 17, σ² "
                   + ("beyond" if v["beyond_noise_squared"] else "not beyond")))
        if s["k"] > 1:
            line += (f" · {len(s['change_points'])} change point(s) · order p "
                     f"{_f(s['order_test']['p'], '{:.3f}')}")
        nl = [g["key"] for g in s["groups"] if g["key"].endswith((NOISE_LIKE_SUFFIX, UNTESTED_SUFFIX))]
        if nl:
            line += " · marked: " + ", ".join(nl)
        parts.append(line)
    if len([s for s in seqs if s.get("k") is not None]) > 3:
        parts = parts[:3] + [f"… {len(seqs)} sequences in meta"]
    parts += meta["warnings"][:3]
    return "; ".join(parts)
