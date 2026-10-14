"""
kshape.py
===========
k-Shape (Paparrizos & Gravano 2015, SIGMOD) as a Library grouping method for
the `shape-distance` basis — and, as public functions, the one k-Shape
implementation the Library and Analyse share (`kshape_fit`, `kshape_predict`).

In plain words: two copies of one event cut a few seconds apart look different
point by point, so Ward's distance (point by point) calls them different shapes.
k-Shape slides one along the other to the best match before comparing (the
shape-based distance, `Working.distances.sbd`), and builds each family's centre
the same way, so misaligned copies land in one family.

The vectors are Ward's: `ward.shape_vectors` (resampled to 256 samples,
z-normalised), so the two methods group the same numbers and differ only in how
they compare them.

The algorithm (paper Alg. 1-3), as implemented in `kshape_fit`
--------------------------------------------------------------
1. z-normalise every row (the paper's precondition; the vectors already are).
2. Random initial assignment of every row to one of k clusters; the initial
   centres are k distinct random rows (they only steer the first alignment).
3. Shape extraction per cluster: align every member to the cluster's current
   centre by its best zero-padded shift (SBD), re-z-normalise the aligned rows
   (a zero-padded shift moves their mean and variance), S = Y'Y,
   M = P S P with P = I - 11'/L, and the new centre is M's leading eigenvector,
   sign-corrected towards the members and z-normalised (eq. 15, Alg. 2).
4. Assign every row to the centre of least SBD.
5. Stop when no membership changes, when the summed distance improves by less
   than `tol`, or after 100 iterations (Alg. 3). Repeat from `n_init` random
   starts and keep the run of least summed distance.

Why not aeon's `KShape` itself (the prompt named it)
----------------------------------------------------
aeon 1.4's `KShape` is the reference here and `tests/test_library_grouping_
methods.py` pins that this module reproduces its labels and centres exactly,
start for start, from the same `random_state`. It is not *called*, because at
the Library's size it does not finish: it aligns each member in a Python loop
with one FFT per call and assigns through `aeon.distances.sbd_pairwise_distance`,
which calls scipy once per pair from numba's object mode. Measured on this
machine: one start at k = 6 on 300 vectors of 256 samples took 49 s; the
Library's 3,603 vectors x 10 starts x 11 values of k would take most of a day.
This module is the same algorithm with the per-pair work batched: every
member's shift against every centre comes out of the assignment step's own
cross-correlation (`Working.distances.sbd_matrix`), so an iteration is one
batched SBD of n rows against k centres plus k eigen-decompositions.

The random-number sequence, the order of the steps, the empty-cluster rule (a
random row becomes the centre) and both stopping rules are aeon's, adapted from
`aeon/clustering/_k_shape.py` (aeon, BSD-3-Clause, Copyright (c) The aeon
developers; itself based on TheDatumOrg/kshape-python, MIT License, Copyright (c)
2022 TheDatumOrg). aeon is installed, not copied; the structure is re-written.

The distance scale
------------------
SBD lies in [0, 2]. Every distance this method reports (to a centroid, between
members, `omit_d`) is SBD / 2, so it sits on the grouping editor's [0, 1] cut
scale as Ward's normalised distance does: a copy is 0, an uncorrelated pair 0.5,
and 1 would need every shift to anti-correlate. `payload["distance_scale"]`
records the divisor (2.0).

Scale
-----
k-Shape itself is linear in n, but choosing k by silhouette needs a square SBD
matrix. The fit therefore runs on at most `sample` rows (default 5,000, seeded,
recorded); every other row is assigned to its nearest centroid by SBD — which
is exactly what aeon's `predict` does — and `payload` lists which rows were
fitted and which assigned. When k is chosen (`k = 0`), each candidate k is
fitted and scored on at most `SILHOUETTE_SAMPLE` (2,000) of the fitted rows
(seeded) — the silhouette is estimated on a subsample above a size, as the
site's dendrogram code does, and fitting eleven k at full size is what cost the
time — and the chosen k is then refitted on every fitted row. The SBDs are
computed in single precision (`FIT_DTYPE`).

Choosing k when `k = 0`
-----------------------
k = 2 ... 12 are each fitted, and scored by the mean silhouette under the
normalised SBD (`sklearn.metrics.silhouette_score`, precomputed). The rule is
the site's rule for Ward's proposal (`Working/training/shape.py`): **the best
silhouette among the k whose fit has at least two families of `min_group`+
members** (the floor scaled to the subsample's share of the rows) — so a k = 2 that is one family and a handful of stragglers cannot win
— falling back to the best silhouette overall, and saying so, when no k
qualifies. Every k's score, family sizes and summed distance are recorded in
`payload["k_scores"]`. Calinski-Harabasz (the WSF paper's rule) was not chosen:
it is defined on Euclidean centroids, which SBD's shifted centres are not.

The nulls (w2-b fix round 1; w3-g)
----------------------------------
k-Shape always returns k families and, on the SBD scale, a fixed `omit_d`
cannot tell noise from members: two unrelated white-noise windows sit at a
median 0.42 (so Ward's 0.50 never fires), and coloured noise sits *closer* to
a centroid than noisy real members do. So the yardstick is noise of the data's
own colour, two kinds of it:

* **the quiet-stretch null** (w3-g; the verdict wherever it is usable): when
  the engine hands `fit` a `background` (`Working.background_null.
  MemberBackground` — the caller's loader of each member's own recording),
  each family's members get windows of their own length cut from their own
  recordings where no event lies (`quiet_distances`), measured against the
  family's centroid; the family is `noise_like` unless its members' median
  distance is below `QUIET_MARGIN` x the min(5 %, m / 2n)-quantile of those
  distances (the selection a family of m among n went through — the comment
  above `QUIET_KIND` has the measurement), `unstable` when not below their
  median, and the automatic `omit_d` is their 5th percentile. Used when at
  least half the family's members got a window from their own recording.
* **the trend-kept null** (beside it, and the verdict otherwise): every fitted
  row (at most `NULL_ROWS`, seeded) gets `null_draws` trend-kept surrogates
  (`trend_kept_surrogates`: a cubic trend kept, the rest phase-randomised),
  each measured against the fitted centroids. A surrogate counts toward the
  family whose centre it lands nearest — the same "nearest of k" selection a
  real member went through — or, when fewer than `NULL_MIN_PER_FAMILY` land,
  every surrogate's distance to that centre is used. Per family: `omit_d = 0`
  (the default) omits a member further from its centre than the null's 5th
  percentile; the family is `noise_like` when its members' median distance is
  not below that 5th percentile, `unstable` when not below the null's median.
  w3-g replaced the plain phase surrogate here: it turns a coloured window's
  trend into a periodic wiggle, so its fake crowds were too loose, and on cut
  events of pure random-walk noise it left families unflagged (the W2-E
  critic: 132 + 108 members at n = 1,000). The trend-kept one keeps a smooth
  window-filling shape's curve in its own fake noise (`SMOOTH_CAVEAT_KSHAPE`),
  which is why the quiet-stretch null leads where it can.

Each family's flags say which null judged it (`null_kind`), carry both
(`nulls`), the sampler's report (`background`, `background_s`) and the
verdict in words (`why`). Families are flagged, never dissolved; the flags and
the null travel on the `GroupingResult` (`Family.flags`, `fit_summary["null"]`).
A fixed `omit_d` > 0 still works.

No tree
-------
k-Shape builds no hierarchy, so `merge_heights` is `[]` (LIBRARY_STORAGE.md 6.2
item 5: no fabricated distribution). The editor's cut slider means nothing to
this method; `omit_d` is its cut.
"""

import numpy as np

from Working.distances import sbd_matrix
from Working.library.grouping.engine import (OMIT_INFINITE_VALUES, OMIT_MISSING_VALUES,
                                             OMIT_PAST_CUT, GroupingCancelled)
from Working.library.grouping.methods import FitResult, register
from Working.library.grouping.methods.ward import RESAMPLE_LENGTH, shape_vectors

# SBD lies in [0, 2]; every distance this module reports is divided by this.
SBD_SCALE = 2.0

DEFAULT_K = 0                 # 0 = choose k by silhouette over K_RANGE
K_RANGE = (2, 12)             # the prompt's range for the automatic choice
DEFAULT_N_INIT = 10
DEFAULT_SEED = 0
# 0 = automatic: per family, the 5th percentile of the surrogate null's distance
# to that family's centroid (module docstring, "The surrogate null"). A fixed
# value > 0 still works — but Ward's 0.50 almost never fires on the SBD scale
# (two white-noise windows sit at a median 0.42; coloured noise nearer).
DEFAULT_OMIT_D = 0
DEFAULT_MIN_GROUP = 10        # spec 9.10's ten-member floor; the engine applies it
NULL_DRAWS = 3                # phase-randomised surrogate sets (the manager's R = 3)
NULL_ROWS = 2000              # fitted rows each draw is made from, at most (seeded)
NULL_PERCENTILE = 5.0         # a member must sit closer than 95 % of the null to stay
NULL_MIN_PER_FAMILY = 20      # surrogates landing in a family below which all are used
DEFAULT_SAMPLE = 5000         # rows fitted at most; the rest are assigned
SILHOUETTE_SAMPLE = 2000      # fitted rows the silhouette is measured on at most
MAX_ITER = 100                # Alg. 3
# The grouping method computes its SBDs in single precision (`kshape_fit`'s
# `dtype`): half the time on the Library's sizes, ~1e-6 on a [0, 1] scale.
FIT_DTYPE = np.float32
TOL = 1e-6                    # aeon's default stopping tolerance on the summed distance

# Cost (fix round 1, item 3), measured on this machine with FIT_DTYPE under load
# from other jobs (2026-10-14): one k-Shape start costs about C_START seconds per
# row x centre — 2,000 rows: 3.7 s at k = 3, 6.9 s at k = 6, 13.6 s at k = 12;
# 3,600 rows: 17.8 s at k = 6, 29.8 s at k = 12 (5.7e-4 to 8.3e-4). Measuring
# rows against centroids (predict, the null) costs C_PREDICT per row x centre.
# The square SBD the silhouette needs costs C_PAIR per ordered pair.
C_START = 8.0e-4
C_PREDICT = 2.0e-5
C_PAIR = 3.2e-6

# aeon's `z_normalise_series`: a row whose standard deviation is at or below
# this is centred but not scaled.
_STD_FLOOR = 1e-8


# --------------------------------------------------------------------------
# Shared with `hdbscan.py`: screening, sampling, distances on demand
# --------------------------------------------------------------------------

def screen_rows(waveforms):
    """`(ok_rows, reasons)`: the rows that can be resampled and z-normalised,
    and, for the rest, why not — `missing_values` for a NaN anywhere,
    `infinite_values` for a +-inf (sklearn HDBSCAN's -3 and -2). A row with
    no samples at all is `missing_values` too."""
    ok, reasons = [], {}
    for i, w in enumerate(waveforms):
        w = np.asarray(w, dtype=float).ravel()
        if w.size == 0 or np.isnan(w).any():
            reasons[i] = OMIT_MISSING_VALUES
        elif np.isinf(w).any():
            reasons[i] = OMIT_INFINITE_VALUES
        else:
            ok.append(i)
    return ok, reasons


def phase_randomised_rows(X, rng):
    """A Fourier surrogate of every row: each row's amplitude spectrum kept
    (so its colour — the AR(1) wander, the random-walk drift — is kept) and
    its phases drawn uniformly, which destroys any shape that is not just
    that colour. The DC bin and, for an even length, the Nyquist bin keep
    phase 0 so the inverse is real. The same transform as
    `Adapters/preprocessing_surrogate._phase_randomise`, batched over rows;
    not imported from there because the core does not import the adapter
    layer."""
    X = np.asarray(X, dtype=float)
    n = X.shape[1]
    F = np.fft.rfft(X, axis=1)
    angles = rng.uniform(0.0, 2.0 * np.pi, size=F.shape)
    angles[:, 0] = 0.0
    if n % 2 == 0:
        angles[:, -1] = 0.0
    return np.fft.irfft(F * np.exp(1j * angles), n=n, axis=1)


# The trend a surrogate keeps: a cubic per row. The manager asked for a line; it
# was measured and found one degree short (fix round 2, both uses):
#   HDBSCAN's per-family test, 10 pure-noise sets (AR(1) phi 0.95/0.99, random
#   walk, drift; 300 and 1,500 rows) and 8 real sets (three shifted shapes at
#   10/20 % noise on four backgrounds): with a line kept, one pure-noise family
#   (random walk, 300 rows) scored a ratio of 0.85 — confident at the 0.9 margin;
#   quadratic, one at 0.78; cubic, none — smallest noise ratio 1.05, largest real
#   ratio 0.66.
#   The coherence null, 100 pure-noise windows: with a line kept, AR(1) phi 0.99
#   scored 0.801 against a null p05 of 0.817 (random walk 0.813 / 0.837) — still
#   "more coherent than noise"; cubic, 0.801 / 0.794 and 0.813 / 0.807, while
#   real drop families stay far below (0.466-0.735 / 0.871).
# A window of coloured noise is mostly a slow curve, not only a slope; keeping
# the curve's first three polynomial moments is what makes the surrogate crowd
# like the real thing. The degree is a measured choice on synthetic data —
# check it on the Library's surrogates.
TREND_DEGREE = 3


def polynomial_trends(X, degree=TREND_DEGREE):
    """The least-squares polynomial of `degree` through each row, evaluated on
    the row's samples (on t in [-1, 1], for conditioning)."""
    X = np.asarray(X, dtype=float)
    t = np.linspace(-1.0, 1.0, X.shape[1])
    A = np.vander(t, int(degree) + 1)                          # (L, degree + 1)
    coef, *_ = np.linalg.lstsq(A, X.T, rcond=None)
    return (A @ coef).T


def trend_kept_surrogates(X, rng, degree=TREND_DEGREE):
    """The Library's shared noise surrogate (w2-b fix round 2): per row, fit a
    polynomial trend (`TREND_DEGREE`, a cubic — see the measurement above),
    phase-randomise what is left (`phase_randomised_rows`: its amplitude
    spectrum, so its colour, kept), add the trend back. NOT z-normalised — the
    caller does that, as for real rows.

    Why the trend is kept: a window of strongly coloured noise (AR(1) at phi
    0.99, a drifting background) is mostly a slow curve, and crowds of such
    curves are exactly what a clustering method finds in noise. Plain phase
    randomisation turns each curve into a periodic wiggle, so its null crowds
    less than real noise does and a test against it calls noise confident (the
    re-critique: null crowds of 11-141 against real-noise crowds of 73-553).
    Used by HDBSCAN's per-family test, k-Shape's (since w3-g) and the coherence
    null, beside the quiet-stretch null and as its fallback."""
    T = polynomial_trends(X, degree)
    return phase_randomised_rows(np.asarray(X, dtype=float) - T, rng) + T


# --------------------------------------------------------------------------
# The quiet-stretch null (w3-g), shared with `hdbscan.py`
# --------------------------------------------------------------------------
#
# The trend-kept surrogate keeps a cubic per row, so a smooth shape that fills its window keeps its curve in its own
# fake noise and reads noise-like (`coherence.SMOOTH_CAVEAT`). The quiet-stretch null replaces the surrogate with
# windows of the members' own recordings where no event lies (`Working.background_null.MemberBackground`): the
# recording's colour, drift and artefacts, none of the shapes.
#
# A quiet window does NOT inherit its member's selection, as a trend-kept surrogate does (it keeps the member's own
# trend, so it sits about as near the medoid as the member). A family is a selected crowd: on pure noise its members
# sit nearer their medoid than unselected windows of the same noise. So the rule matches the selection by a
# quantile: the members' median distance d_F must beat the q-quantile of the quiet windows' distances to the same
# centre, q = min(5 %, m / (2 n)) for a family of m found among n — the median of the m nearest of n background
# windows, capped at today's 5th percentile. Measured (w3-g, HDBSCAN at its defaults on cut events of pure noise,
# 600 s windows over 40-50 % of the span, 200 and 1,000 events, 8 seeds each): the nearest-m rule alone, min over 20
# draws, let pure random-walk crowds reach 0.85 x (0.68 x with 3 draws) — below the 0.9 margin; the capped quantile
# put every pure random-walk family at 1.4 x and above, AR(1) phi 0.98-0.99 families at 0.80 x and above (124
# families), while broad humps and slow ramps on the same backgrounds scored 0.01-0.54 x (the trend-kept null:
# 1.15-3.0 x, noise-like). The margin is therefore 0.7, not 0.9 (`QUIET_MARGIN`). Enough windows are drawn for the quantile:
# `QUIET_POINTS` pooled windows per q, at least `QUIET_MIN_DRAWS` draws per member, at most `QUIET_MAX_WINDOWS`.
QUIET_KIND = "quiet-stretch"
TREND_KIND = "trend-kept phase-randomised"
QUIET_PERCENTILE_CAP = 5.0          # q never above today's 5th percentile
QUIET_POINTS = 40                   # pooled windows per unit of q: the quantile rests on ~40 windows below it
QUIET_MIN_DRAWS = 10
QUIET_MAX_WINDOWS = 20000           # windows cut per family at most (cost)
# PLACEHOLDER, measured: confident iff d_F < 0.6 x the quiet q-quantile (the manager's decision 16, fix round 1).
# Under a selection-matched null a pure-noise family sits at about 1 x, so the margin is all the protection:
# 124 pure-noise HDBSCAN families (AR(1) phi 0.98 and 0.99, 200 / 400 / 1,000 cut events, 20-30 seeds) reached
# 0.80 x; the W3-G critic's worst case — the 10 nearest windows around the densest centres among 3,600 — reached
# 0.714 clean and 0.643 with uncatalogued events in the quiet stretches. Real shape families at 10 % noise scored
# 0.13-0.39 (the critic) and broad humps / slow ramps 0.01-0.54 (w3-g), so 0.6 costs them nothing measured.
QUIET_MARGIN = 0.6
# The verdict is EITHER null (the manager's decision 15): a family is confident when it passes the quiet-stretch
# null OR the trend-kept one. Their blind spots are opposite, both measured: the trend-kept null cannot see smooth
# window-filling shapes (humps and ramps 1.15-3.0 x), and the quiet null fails sharp families when the quiet
# stretches hold uncatalogued events of their own shape (drops / sharkfins 1.29-1.31 x where the trend-kept null gave
# 0.20-0.37 x, the critic). Each null's size on pure noise is small, so their union stays small.
EITHER_KIND = "quiet-stretch or trend-kept phase-randomised"
SMOOTH_CAVEAT_KSHAPE = ("a smooth shape that fills the window (a broad hump, a slow ramp) keeps its curve in its own "
                        "trend-kept noise and can read noise-like, so for such a family this flag is not evidence "
                        "that it is noise")


# Cost (w3-g), measured 2026-10-14 on this machine under load: one quiet window cut off a memmapped recording,
# decimated to the Library's 64-px envelope, resampled to 256 and measured against a centre costs ~5.3e-4 s (the
# resample was half of it until `batched_shape_vectors`: 3.6e-4 s after; a raw slice instead of the envelope, 2e-4 s).
C_QUIET_WINDOW = 4.0e-4
#: what an estimate assumes, before the families exist: this many families sharing the set equally
QUIET_ESTIMATE_FAMILIES = 20


def quiet_windows_estimate(n):
    """Quiet windows a run on `n` members is expected to cut: `QUIET_ESTIMATE_FAMILIES` families of
    n / (2 x that) members each (half the set placed), each drawn as `quiet_distances` would."""
    n = max(1, int(n))
    m = max(10, n // (2 * QUIET_ESTIMATE_FAMILIES))
    q = quiet_quantile(m, n)
    return QUIET_ESTIMATE_FAMILIES * m * quiet_draws(m, q)


def quiet_quantile(m, n_set):
    """q for a family of `m` found among `n_set` (module comment above)."""
    m, n_set = max(1, int(m)), max(1, int(n_set))
    return min(QUIET_PERCENTILE_CAP / 100.0, m / (2.0 * n_set))


def quiet_draws(m, q):
    """Draws per member so the pooled windows rest the q-quantile on ~`QUIET_POINTS` windows."""
    m = max(1, int(m))
    want = int(np.ceil(QUIET_POINTS / max(q, 1e-9) / m))
    return int(max(1, min(max(QUIET_MIN_DRAWS, want), QUIET_MAX_WINDOWS // m)))


def batched_shape_vectors(waveforms, n_samples=RESAMPLE_LENGTH):
    """`ward.shape_vectors`, batched over waveforms of one length (the quiet
    windows come in a few lengths, tens of thousands of them): the same linear
    resample onto `n_samples` points spanning the window and the same
    z-normalisation (`distances.z_normalize`: a flat row is all zeros), to
    ~1e-12 — the per-row loop cost ~0.25 ms a window, most of the null's time."""
    waveforms = list(waveforms)
    n_samples = int(n_samples)
    out = np.zeros((len(waveforms), n_samples))
    by_len = {}
    for i, w in enumerate(waveforms):
        by_len.setdefault(len(w), []).append(i)
    new = np.linspace(0.0, 1.0, n_samples)
    for n0, idx in by_len.items():
        X = np.asarray([np.asarray(waveforms[i], dtype=float).ravel() for i in idx])
        if n0 == n_samples:
            Y = X.copy()
        elif n0 == 1:
            Y = np.repeat(X, n_samples, axis=1)
        else:
            old = np.linspace(0.0, 1.0, n0)
            j = np.clip(np.searchsorted(old, new, side="right") - 1, 0, n0 - 2)
            frac = (new - old[j]) / (old[j + 1] - old[j])
            Y = X[:, j] * (1.0 - frac) + X[:, j + 1] * frac
        flat = np.ptp(Y, axis=1) == 0
        sd = Y.std(axis=1)
        Z = np.zeros_like(Y)
        ok = ~flat & (sd > 0)
        Z[ok] = (Y[ok] - Y[ok].mean(axis=1, keepdims=True)) / sd[ok, None]
        out[idx] = Z
    return out


def quiet_distances(background, rows, centre, resample_length, distance_fn, *, n_set, salt=0):
    """The quiet-stretch windows of `rows` (indices into `background`, a
    `MemberBackground`), prepared as the members were (`ward.shape_vectors`) and
    measured against `centre` (one vector) by `distance_fn(A, centre[None])`.
    Returns `(distances or None, q, report)`; `distances` is None when the draw
    is not usable (the report says why)."""
    rows = list(rows)
    q = quiet_quantile(len(rows), n_set)
    draws = quiet_draws(len(rows), q)
    dr = background.draw(rows, draws, salt=salt)
    report = dict(dr.report)
    report.update(quantile=q, n_set=int(n_set))
    if not dr.usable:
        return None, q, report
    waves = [w for d in dr.windows for w in d if w is not None]
    if len(waves) < 2:
        report.update(usable=False, reason="fewer than two quiet windows could be cut")
        return None, q, report
    B = batched_shape_vectors(waves, int(resample_length))
    d = np.asarray(distance_fn(B, np.asarray(centre, dtype=float)[None, :]))[:, 0]
    report["n_windows"] = int(d.size)
    return d, q, report


def quiet_verdict(d_F, d_bg, q, margin):
    """`(threshold, ratio, noise_like, unstable)`: the q-quantile of the quiet
    distances, d_F over it, d_F not below margin x it, d_F not below the quiet
    windows' median."""
    thr = float(np.quantile(d_bg, q))
    ratio = d_F / thr if thr > 0 else float("inf")
    return thr, float(ratio), bool(not (d_F < margin * thr)), bool(not (d_F < float(np.median(d_bg))))


def either_verdict(quiet, trend):
    """`(noise_like, unstable, passed_by, null_kind)` under decision 15: with a
    usable quiet-stretch result, the family passes if either null passes it
    (`passed_by` lists which, quiet first) and is unstable only when both call it
    so; without one, the trend-kept verdict alone (`null_kind` says which)."""
    if quiet is None:
        return (bool(trend["noise_like"]), bool(trend["unstable"]),
                [] if trend["noise_like"] else [TREND_KIND], TREND_KIND)
    passed = [k for k, v in ((QUIET_KIND, quiet), (TREND_KIND, trend)) if not v["noise_like"]]
    return (not passed, bool(quiet["unstable"] and trend["unstable"]), passed, EITHER_KIND)


def background_words(report):
    """`"<s> s of background on <k> recording(s)"` (or samples, without a rate), for a verdict's text."""
    s = report.get("background_s")
    k = report.get("n_recordings", 0)
    amount = (f"{s:,.0f} s" if s is not None else f"{report.get('background_samples', 0):,} samples")
    out = f"{amount} of event-free background on {k} recording(s)"
    if report.get("n_borrowed"):
        out += f"; {report['n_borrowed']} borrowed windows (members whose own recording had no room or was not on disk)"
    share = report.get("detection_overlap_share")
    if share is not None:
        out += f"; {share:.0%} of the quiet windows overlap a machine detection (detections are not avoided)"
    return out


def null_rng(seed, salt):
    """The seeded generator a method's null draws use — separate from the
    sample's and the starts' so adding a null changes neither."""
    return np.random.default_rng([int(seed), int(salt)])


def sample_positions(n, sample, seed):
    """`(fitted, assigned)` positions in 0..n-1: all of them fitted when
    n <= sample, else `sample` of them drawn without replacement by a seeded
    generator (sorted), the rest assigned."""
    every = np.arange(n)
    sample = int(sample) if sample else n
    if n <= sample:
        return every, every[:0]
    rng = np.random.default_rng(seed)
    fitted = np.sort(rng.choice(n, size=sample, replace=False))
    mask = np.ones(n, dtype=bool)
    mask[fitted] = False
    return fitted, every[mask]


class NormalisedSBD:
    """`fit.distances` for a method whose square matrix may not fit in memory:
    indexable as `D[i, j]` (and `D[indices, j]`) by input row, returning the
    normalised SBD (SBD / 2) of the two rows' vectors. Each column is computed
    once, against every row, the first time it is asked for — the engine asks
    for one column per family (its medoid), so a grouping of 20,000 members
    costs one 20,000 x 1 SBD per family rather than a 20,000^2 matrix."""

    def __init__(self, vectors, positions, n):
        self.vectors = vectors              # one row per screened-in input row
        self.positions = positions          # input row -> vector row (or -1)
        self.shape = (n, n)
        self._columns = {}

    def column(self, j):
        j = int(j)
        if j not in self._columns:
            pos = int(self.positions[j])
            out = np.full(self.shape[0], np.nan)
            if pos >= 0:
                d = sbd_matrix(self.vectors, self.vectors[pos:pos + 1], z_normalise=False)[:, 0]
                out[self.positions >= 0] = d[self.positions[self.positions >= 0]] / SBD_SCALE
            self._columns[j] = out
        return self._columns[j]

    def __getitem__(self, key):
        i, j = key
        return self.column(j)[i]


# --------------------------------------------------------------------------
# k-Shape
# --------------------------------------------------------------------------

def _z_rows(Y):
    """aeon's `z_normalise_series_2d`: each row centred, and scaled when its
    standard deviation clears `_STD_FLOOR`."""
    Y = np.asarray(Y, dtype=float)
    out = Y - Y.mean(axis=1, keepdims=True)
    sd = Y.std(axis=1)
    big = sd > _STD_FLOOR
    out[big] /= sd[big, None]
    return out


def _shift_rows(rows, shifts):
    """Each row moved by its own shift, zero-padded (`zero_pad_shift`, batched)."""
    L = rows.shape[1]
    src = np.arange(L)[None, :] - np.asarray(shifts)[:, None]
    valid = (src >= 0) & (src < L)
    return np.where(valid, np.take_along_axis(rows, np.clip(src, 0, L - 1), axis=1), 0.0)


def _leading_eigenvector(B, start):
    """The leading eigenvector of M = B'B (B = Y P, the centred aligned
    members), without forming more than it needs. M is PSD with rank at most
    the member count, so for a cluster smaller than the length the top
    eigenvector of the small Gram B B' gives it as B'u; otherwise ARPACK
    (`eigsh`, k = 1, from a fixed start — deterministic) on the L x L matrix.
    A full `eigh` was 75 % of an iteration (52 ms at 256 x 256 here); a full
    `eigh` remains the fallback should ARPACK not converge. The vector is
    defined up to sign, which `_shape_extraction` then fixes exactly as aeon
    does, so the centre is the same one aeon's `eigh(P S P)` gives."""
    n, L = B.shape
    if n < L:
        _, u = np.linalg.eigh(B @ B.T)
        v = B.T @ u[:, -1]
        norm = np.linalg.norm(v)
        return v / norm if norm > 0 else v
    from scipy.sparse.linalg import ArpackNoConvergence, eigsh
    M = B.T @ B
    v0 = start if (start is not None and np.any(start)) else np.ones(L)
    try:
        _, vecs = eigsh(M, k=1, which="LA", v0=v0)
        return vecs[:, 0].copy()
    except (ArpackNoConvergence, ValueError):
        _, vecs = np.linalg.eigh(M)
        return vecs[:, -1].copy()


def _shape_extraction(aligned, P, start=None):
    """Alg. 2: the leading eigenvector of M = P (Y'Y) P over the
    re-z-normalised aligned members Y — computed as B'B with B = Y P —
    sign-corrected towards the members, z-normalised."""
    Y = _z_rows(aligned)
    centre = _leading_eigenvector(Y @ P, start)
    d1 = np.linalg.norm(aligned - centre[None, :], axis=1).sum()
    d2 = np.linalg.norm(aligned + centre[None, :], axis=1).sum()
    if d1 >= d2:
        centre = -centre
    return _z_rows(centre[None, :])[0]


def _one_start(X, k, rng, max_iter, tol, dtype):
    n, L = X.shape
    P = np.eye(L) - np.full((L, L), 1.0 / L)
    centres = X[rng.choice(n, k, replace=False)].copy()
    labels = rng.randint(0, k, size=n, dtype=np.int64)
    # every row's best shift against every current centre (k, n)
    _, shifts = sbd_matrix(centres, X, z_normalise=False, return_shifts=True, dtype=dtype)

    prev_inertia = np.inf
    for it in range(max_iter):
        old_labels = labels.copy()
        for j in range(k):
            members = np.flatnonzero(labels == j)
            if members.size == 0:
                centres[j] = X[rng.randint(0, n)].copy()
                continue
            if np.all(centres[j] == 0):
                aligned = X[members]
            else:
                aligned = _shift_rows(X[members], shifts[j, members])
            centres[j] = _shape_extraction(aligned, P, centres[j])

        D, shifts = sbd_matrix(centres, X, z_normalise=False, return_shifts=True, dtype=dtype)
        labels = D.argmin(axis=0).astype(np.int64)
        inertia = float(D.min(axis=0).sum())
        if np.array_equal(labels, old_labels):
            return labels, centres, inertia, it + 1, D
        if 0 <= (prev_inertia - inertia) < tol:
            return labels, centres, inertia, it + 1, D
        prev_inertia = inertia
    # aeon reports the previous iteration's summed distance when it runs out of iterations
    return labels, centres, prev_inertia, max_iter, D


def kshape_fit(X, k, *, n_init=DEFAULT_N_INIT, seed=DEFAULT_SEED, max_iter=MAX_ITER, tol=TOL,
               dtype=np.float64, should_cancel=None):
    """k-Shape on the rows of `X` (n x L, equal lengths). Returns a dict:
    `labels` (n,) in 0..k-1, `centroids` (k x L, z-normalised), `inertia`
    (summed SBD to the own centroid, on SBD's [0, 2] scale), `n_iter`,
    `distances` (k x n SBD of every row to every centroid, [0, 2]).

    `seed` drives the starts exactly as aeon's `KShape(random_state=seed)`
    does, so the two agree start for start (module docstring). `dtype =
    np.float32` computes the SBDs in single precision (`sbd_matrix`): half
    the time, ~1e-6 on the distances, so a near-tie can break the other way;
    the grouping method uses it, the aeon comparison does not."""
    from sklearn.utils import check_random_state

    X = _z_rows(np.asarray(X, dtype=float))
    n = X.shape[0]
    k = int(k)
    if k < 1 or k > n:
        raise ValueError(f"k-Shape needs 1 <= k <= n; got k={k} for n={n}.")
    master = check_random_state(seed)
    best = None
    for _ in range(max(1, int(n_init))):
        if should_cancel is not None and should_cancel():
            raise GroupingCancelled("cancelled between k-Shape starts")
        rng = check_random_state(master.randint(0, np.iinfo(np.int32).max))
        run = _one_start(X, k, rng, int(max_iter), float(tol), dtype)
        if best is None or run[2] < best[2]:
            best = run
    labels, centres, inertia, n_iter, D = best
    return {"labels": labels, "centroids": centres, "inertia": float(inertia),
            "n_iter": int(n_iter), "distances": D}


def kshape_predict(centroids, X, *, dtype=np.float64):
    """`(labels, distances)`: each row of `X` to its nearest centroid by SBD
    (aeon's `predict`), and that SBD on [0, 2]. `X` is z-normalised here."""
    X = _z_rows(np.asarray(X, dtype=float))
    if X.shape[0] == 0:
        return np.zeros(0, dtype=np.int64), np.zeros(0)
    D = sbd_matrix(np.asarray(centroids, dtype=float), X, z_normalise=False, dtype=dtype)
    return D.argmin(axis=0).astype(np.int64), D.min(axis=0)


def _silhouette(D, labels):
    """Mean silhouette under a precomputed distance, or None where it is
    undefined (fewer than two clusters present, or every row its own)."""
    from sklearn.metrics import silhouette_score
    present = np.unique(labels)
    if present.size < 2 or present.size >= labels.size:
        return None
    return float(silhouette_score(D, labels, metric="precomputed"))


def choose_k(X, *, k_range=K_RANGE, n_init=1, seed=DEFAULT_SEED,
             min_group=DEFAULT_MIN_GROUP, silhouette_sample=SILHOUETTE_SAMPLE, dtype=np.float64,
             should_cancel=None):
    """Fit k-Shape at every k in `k_range` and pick one by the rule in the
    module docstring. Each k is fitted AND scored on the same seeded
    subsample of at most `silhouette_sample` rows (all rows when there are
    fewer): the silhouette needs that subsample's square SBD matrix anyway,
    and fitting eleven k at full size is what made the sweep slow.

    Returns `(chosen_k, fits, scores, rule, sweep_rows)`: `fits[k]` is the
    sweep's fit (on `sweep_rows`), `scores` one dict per k — `k`,
    `silhouette`, `sizes`, `inertia`, `qualifies` (two or more families of
    `min_group`+, the floor scaled to the subsample's share of the rows)."""
    X = np.asarray(X, dtype=float)
    n = X.shape[0]
    rows, _ = sample_positions(n, silhouette_sample, seed)
    Xs = X[rows]
    ns = Xs.shape[0]
    floor = max(2, int(round(min_group * ns / n))) if n else min_group
    lo, hi = int(k_range[0]), min(int(k_range[1]), ns - 1)
    D_sil = sbd_matrix(Xs, dtype=np.float32) / SBD_SCALE

    fits, scores = {}, []
    for k in range(lo, hi + 1):
        fit = kshape_fit(Xs, k, n_init=n_init, seed=seed, dtype=dtype, should_cancel=should_cancel)
        fits[k] = fit
        sizes = sorted(np.bincount(fit["labels"], minlength=k).tolist(), reverse=True)
        scores.append({
            "k": k,
            "silhouette": _silhouette(D_sil, fit["labels"]),
            "sizes": sizes,
            "inertia": fit["inertia"],
            "qualifies": sum(1 for size in sizes if size >= floor) >= 2,
            "starts": int(n_init),
        })

    scored = [sc for sc in scores if sc["silhouette"] is not None]
    pool = [sc for sc in scored if sc["qualifies"]]
    if pool:
        rule = (f"best silhouette under normalised SBD among k = {lo}..{hi} with at least two "
                f"families of {floor}+ members")
    else:
        pool = scored
        rule = (f"best silhouette under normalised SBD over k = {lo}..{hi}; NO k gave two families "
                f"of {floor}+ members, so this is the best of a set that all fail the rule")
    where = (f"; each k fitted and scored on {ns} of {n} rows (seeded), the chosen k then refitted "
             f"on all {n}" if ns < n else f"; each k fitted and scored on all {n} rows")
    if not pool:
        return None, fits, scores, "no k could be scored (too few distinct rows)" + where, rows
    best = max(pool, key=lambda sc: (sc["silhouette"], -sc["k"]))
    return best["k"], fits, scores, rule + where, rows


# --------------------------------------------------------------------------
# The grouping method
# --------------------------------------------------------------------------

class KShapeMethod:
    """k-Shape on Ward's shape vectors, under the shape-based distance."""

    name = "kshape"
    label = "k-Shape"
    description = ("k-Shape (Paparrizos & Gravano 2015): families of shapes compared after "
                   "sliding one along the other to the best match, so copies of one event cut "
                   "a few seconds apart still match. Tune k first (0 chooses it).")
    applies_to = ("shape-distance",)

    params = {
        "k": {
            "type": "int", "default": DEFAULT_K, "label": "families (k)",
            "help": "how many families to make. 0 chooses k from 2 to 12 by the best "
                    "silhouette among the k that give two or more families of the minimum "
                    "group size; every k's score is recorded with the grouping.",
        },
        "n_init": {
            "type": "int", "default": DEFAULT_N_INIT, "label": "random starts",
            "help": "k-Shape starts from a random assignment; it is run this many times and the "
                    "tightest run kept. More starts, steadier families, proportionally slower.",
        },
        "seed": {
            "type": "int", "default": DEFAULT_SEED, "label": "seed",
            "help": "the random seed for the starts and for the sample; the same seed gives the "
                    "same families.",
        },
        "omit_d": {
            "type": "float", "default": DEFAULT_OMIT_D, "label": "further from its centre than",
            "help": "0 (the default) = automatic: a member is omitted as past_cut when it sits "
                    "further from its family's centre than 95 % of noise does — windows of the "
                    "members' own recordings where no event lies, else trend-kept noise of the "
                    "same colour. A number > 0 is a fixed shape-based distance instead (0 = a "
                    "shifted copy); note that Ward's 0.5 almost never fires on this scale - two "
                    "unrelated noise windows already sit near 0.42.",
        },
        "null_draws": {
            "type": "int", "default": NULL_DRAWS, "label": "noise draws",
            "help": "how many trend-kept surrogate sets (each window's slow trend kept, the rest "
                    "phase-randomised: noise of its own colour) the families are measured against, "
                    "beside the recording's own quiet stretches (which judge wherever the members' "
                    "recordings leave enough of them). 0 = no null: families are reported untested "
                    "and the automatic omit_d omits nothing.",
        },
        "min_group": {
            "type": "int", "default": DEFAULT_MIN_GROUP, "label": "minimum group",
            "help": "families under this many members are omitted and flagged (spec 9.10). The "
                    "engine applies it, one rule for every method.",
        },
        "sample": {
            "type": "int", "default": DEFAULT_SAMPLE, "label": "fit on at most",
            "help": "members the fit is computed on; above this many a seeded sample is fitted "
                    "and the rest are assigned to their nearest family centre. Recorded with "
                    "the grouping.",
        },
        "resample_length": {
            "type": "int", "default": RESAMPLE_LENGTH, "label": "resample length",
            "help": "samples every span is resampled to before z-normalising — Ward's 256, so "
                    "the two methods compare the same vectors.",
        },
    }

    # ---------------------------------------------------------------- fit

    def fit(self, waveforms, *, params=None, should_cancel=None, background=None):
        """`background`, optional: a `Working.background_null.MemberBackground`
        over the same rows as `waveforms` (the engine passes it), for the
        quiet-stretch null; without it the trend-kept null is the verdict."""
        params = params or {}
        L = int(params.get("resample_length", RESAMPLE_LENGTH))
        k_param = int(params.get("k", DEFAULT_K))
        n_init = int(params.get("n_init", DEFAULT_N_INIT))
        seed = int(params.get("seed", DEFAULT_SEED))
        sample = int(params.get("sample", DEFAULT_SAMPLE))
        min_group = int(params.get("min_group", DEFAULT_MIN_GROUP))
        waveforms = list(waveforms)
        n = len(waveforms)

        ok, bad = screen_rows(waveforms)
        positions = np.full(n, -1, dtype=np.int64)
        positions[ok] = np.arange(len(ok))
        vectors = (shape_vectors([waveforms[i] for i in ok], L) if ok
                   else np.zeros((0, L)))
        payload = {"resample_length": L, "distance_scale": SBD_SCALE, "vectors": vectors,
                   "positions": positions, "n_init": n_init, "seed": seed, "sample": sample,
                   "k_param": k_param, "k_scores": [], "k_rule": None,
                   "cluster": np.full(n, -1, dtype=np.int64), "dist": np.full(n, np.nan),
                   "family_of_cluster": {}, "screened_out": dict(bad)}
        fit = FitResult(method=self.name, n=n, payload=payload)
        fit.omit_reasons.update(bad)
        fit.distances = NormalisedSBD(vectors, positions, n)

        n_ok = len(ok)
        fitted_pos, assigned_pos = sample_positions(n_ok, sample, seed)
        payload["fitted_rows"] = [int(ok[p]) for p in fitted_pos]
        payload["assigned_rows"] = [int(ok[p]) for p in assigned_pos]
        if n_ok == 0:
            payload["fit_summary"] = self._summary(payload, n, 0, None)
            return fit

        V_fit = vectors[fitted_pos]
        n_fit = V_fit.shape[0]
        if n_fit <= 2:
            k, result = 1, kshape_fit(V_fit, 1, n_init=1, seed=seed)
            payload["k_rule"] = f"k = 1: {n_fit} fitted row(s) are too few to choose k"
        elif k_param <= 0:
            # fix round 1: ONE start per candidate k on the subsample (a named
            # adaptation — ten starts x eleven k took 19 min at 3,603), then the
            # chosen k alone gets `n_init` starts on every fitted row
            k, fits, scores, rule, sweep_rows = choose_k(V_fit, n_init=1, seed=seed,
                                                         min_group=min_group, dtype=FIT_DTYPE,
                                                         should_cancel=should_cancel)
            payload["k_scores"] = scores
            payload["k_rule"] = rule + f"; one start per candidate k, then {n_init} for the chosen k"
            if k is None:
                k, result = 1, kshape_fit(V_fit, 1, n_init=1, seed=seed)
                payload["k_rule"] += "; k = 1"
            elif len(sweep_rows) == n_fit and n_init <= 1:
                result = fits[k]
            else:
                result = kshape_fit(V_fit, k, n_init=n_init, seed=seed, dtype=FIT_DTYPE,
                                    should_cancel=should_cancel)
        else:
            k = min(k_param, n_fit)
            result = kshape_fit(V_fit, k, n_init=n_init, seed=seed, dtype=FIT_DTYPE,
                                should_cancel=should_cancel)
            payload["k_rule"] = (f"k = {k} as set" if k == k_param
                                 else f"k = {k}: {k_param} asked for, only {n_fit} rows fitted")

        labels = np.empty(n_ok, dtype=np.int64)
        dist = np.empty(n_ok)
        labels[fitted_pos] = result["labels"]
        dist[fitted_pos] = result["distances"].min(axis=0)
        if assigned_pos.size:
            rest_labels, rest_d = kshape_predict(result["centroids"], vectors[assigned_pos],
                                                 dtype=FIT_DTYPE)
            labels[assigned_pos] = rest_labels
            dist[assigned_pos] = rest_d

        sizes = np.bincount(labels, minlength=k)
        order = sorted(range(k), key=lambda c: (-sizes[c], c))
        family_of_cluster = {c: rank + 1 for rank, c in enumerate(order) if sizes[c] > 0}
        payload["cluster"][ok] = labels
        payload["dist"][ok] = dist / SBD_SCALE
        payload.update(k=int(k), centroids=result["centroids"], inertia=result["inertia"],
                       n_iter=result["n_iter"], family_of_cluster=family_of_cluster,
                       final_starts=int(n_init) if not (k_param <= 0 and k == 1) else 1)
        draws = int(params.get("null_draws", NULL_DRAWS))
        payload["ok_rows"] = np.asarray(ok, dtype=np.int64)
        self._null(payload, V_fit, labels, dist / SBD_SCALE, k, seed, draws, should_cancel, background)
        payload["fit_summary"] = self._summary(payload, n, n_ok, k)
        return fit

    @staticmethod
    def _null(payload, V_fit, labels, dist, k, seed, draws, should_cancel=None, background=None):
        """The two nulls (module docstring): the trend-kept one per cluster (the
        distances of trend-kept surrogates that land nearest its centroid, their
        5th percentile and median), and, when a `background` is given, the
        quiet-stretch one per family (`quiet_distances`). The verdict and the
        automatic `omit_d` read the quiet-stretch null where it is usable, else
        the trend-kept one, and say which. `labels` and `dist` are over every
        screened-in row (fitted and assigned)."""
        family_of = payload["family_of_cluster"]
        payload["null_p05"], payload["family_flags"] = {}, {}
        if draws <= 0:
            payload["null"] = {"kind": "none", "draws": 0,
                               "rule": "no null drawn (null_draws = 0): families untested, "
                                       "the automatic omit_d omits nothing"}
            return
        # w3-g: trend-kept surrogates replace the plain phase ones. The plain surrogate turns a coloured window's
        # trend into a periodic wiggle, so its fake crowds are too loose: on cut events of pure random-walk noise it
        # left k-Shape families unflagged (the W2-E critic: 132 + 108 members at n = 1,000).
        rng = null_rng(seed, 11)
        sub, _ = sample_positions(V_fit.shape[0], NULL_ROWS, seed)
        Vs = V_fit[sub]
        landed = {c: [] for c in range(k)}
        every = {c: [] for c in range(k)}
        for _ in range(draws):
            if should_cancel is not None and should_cancel():
                raise GroupingCancelled("cancelled while drawing the k-Shape null")
            S = _z_rows(trend_kept_surrogates(Vs, rng))
            D = sbd_matrix(payload["centroids"], S, z_normalise=False, dtype=FIT_DTYPE) / SBD_SCALE
            near = D.argmin(axis=0)
            for c in range(k):
                landed[c].extend(D[c, near == c].tolist())
                every[c].extend(D[c].tolist())
        p05, p50, source = {}, {}, {}
        for c in range(k):
            use_landed = len(landed[c]) >= NULL_MIN_PER_FAMILY
            values = landed[c] if use_landed else every[c]
            source[c] = "landed" if use_landed else "all"
            p05[c] = float(np.percentile(values, NULL_PERCENTILE))
            p50[c] = float(np.median(values))

        ok_rows = payload.get("ok_rows")
        n_ok = int(labels.size)
        L = int(payload["resample_length"])
        kinds, backgrounds = {}, {}
        for c, fam in family_of.items():
            if should_cancel is not None and should_cancel():
                raise GroupingCancelled("cancelled while drawing the k-Shape null")
            members = np.flatnonzero(labels == c)
            med = float(np.median(dist[members]))
            t_noise, t_unstable = med >= p05[c], med >= p50[c]
            trend = {"kind": TREND_KIND, "null_p05": p05[c], "null_median": p50[c],
                     "ratio": (med / p05[c]) if p05[c] > 0 else float("inf"),
                     "noise_like": bool(t_noise), "unstable": bool(t_unstable), "caveat": SMOOTH_CAVEAT_KSHAPE}
            trend_why = (f"members' median distance to the centre {med:.3f} is "
                         + ("not below" if t_noise else "below")
                         + f" the 5th percentile {p05[c]:.3f} of trend-kept noise of their own colour ({draws} "
                         + f"draws of {len(sub)} rows; its median {p50[c]:.3f}); {SMOOTH_CAVEAT_KSHAPE}")
            quiet, report = None, None
            if background is not None and ok_rows is not None:
                pick, _ = sample_positions(members.size, NULL_ROWS, seed)
                d_bg, q, report = quiet_distances(
                    background, ok_rows[members[pick]].tolist(), payload["centroids"][c], L,
                    lambda A, B: sbd_matrix(A, B, z_normalise=False, dtype=FIT_DTYPE) / SBD_SCALE,
                    n_set=n_ok, salt=1000 + int(c))
                if d_bg is not None:
                    thr, ratio, q_noise, q_unstable = quiet_verdict(med, d_bg, q, QUIET_MARGIN)
                    quiet = {"kind": QUIET_KIND, "threshold": thr, "quantile": q, "ratio": ratio,
                             "noise_like": q_noise, "unstable": q_unstable, "margin": QUIET_MARGIN,
                             "omit_d": float(np.percentile(d_bg, NULL_PERCENTILE)),
                             "null_median": float(np.median(d_bg))}
            noise_like, unstable, passed_by, kinds[c] = either_verdict(quiet, trend)
            if quiet is not None:
                use_quiet = QUIET_KIND in passed_by or TREND_KIND not in passed_by
                p05_used, p50_used = ((quiet["omit_d"], quiet["null_median"]) if use_quiet else (p05[c], p50[c]))
                why = (f"passed by {' and '.join(passed_by) if passed_by else 'neither null'} (a family passes on "
                       f"either); the quiet-stretch null ({background_words(report)}): members' median distance "
                       f"to the centre {med:.3f} is {quiet['ratio']:.2f} x the {q:.2%} quantile {quiet['threshold']:.3f} "
                       f"of {report['n_windows']} windows cut where no event lies on the members' own recordings; "
                       f"passes below {QUIET_MARGIN} x (a placeholder margin). Trend-kept null: {trend['ratio']:.2f} x; "
                       + trend_why)
            else:
                p05_used, p50_used = p05[c], p50[c]
                fallback = (("quiet-stretch null not used: " + str(report.get("reason")) + "; ")
                            if report is not None else
                            ("quiet-stretch null not available (no recording was given); " if background is None
                             else ""))
                why = f"against the trend-kept null: {fallback}" + trend_why
            payload["null_p05"][c] = p05_used
            backgrounds[c] = report
            payload["family_flags"][fam] = {
                "noise_like": bool(noise_like), "unstable": bool(unstable), "tested": True,
                "why": ("no better than noise of the same colour: " + why) if noise_like else why,
                "median_distance": med, "null_p05": p05_used, "null_median": p50_used,
                "null_kind": kinds[c], "passed_by": passed_by, "background": report,
                "background_s": (report or {}).get("background_s"),
                "nulls": {"quiet_stretch": quiet, "trend_kept": trend}}
        # clusters with no family (empty) keep the trend-kept p05 for the automatic omit_d
        for c in range(k):
            payload["null_p05"].setdefault(c, p05[c])
        label = {c: f"F-{f:02d}" for c, f in family_of.items()}
        used = set(kinds.values())
        payload["null"] = {
            "kind": (EITHER_KIND if used == {EITHER_KIND} else
                     f"{EITHER_KIND}, {TREND_KIND} fallback" if EITHER_KIND in used else TREND_KIND),
            "draws": draws, "rows_per_draw": int(len(sub)),
            "percentile": NULL_PERCENTILE, "margin": QUIET_MARGIN,
            "omit_d_by_family": {label[c]: payload["null_p05"][c] for c in family_of},
            "median_by_family": {label[c]: payload["family_flags"][f]["null_median"] for c, f in family_of.items()},
            "from": {label[c]: source[c] for c in family_of},
            "kind_by_family": {label[c]: kinds[c] for c in family_of},
            "rule": (f"per family, a family passes on EITHER null. The quiet-stretch null, where at least half its "
                     f"members got a window from their own recording: members' median distance to the centre must "
                     f"be below {QUIET_MARGIN} x the q-quantile of quiet windows' distances to it, q = min(5 %, "
                     f"m / 2n) for a family of m among n (a placeholder margin); machine detections are not avoided, "
                     f"so a quiet window can hold an uncatalogued event (loosening the null for other shapes, "
                     f"tightening it for its own). Automatic omit_d = the 5th percentile of the null that passed "
                     f"(the quiet one when both or neither did). The trend-kept null (alone when the quiet one is not "
                     f"usable): each fitted row's cubic trend "
                     f"kept and the rest phase-randomised, {draws} times; a surrogate counts toward the family "
                     f"whose centre it lands nearest (all surrogates when fewer than {NULL_MIN_PER_FAMILY} land); "
                     f"automatic omit_d = their {NULL_PERCENTILE:g}th percentile; noise-like when the members' "
                     f"median distance is not below that, unstable when not below the noise's median. "
                     f"Caveat of the trend-kept null: {SMOOTH_CAVEAT_KSHAPE}")}

    @staticmethod
    def _summary(payload, n, n_ok, k):
        return {"rows": n, "screened_out": n - n_ok,
                "fitted": len(payload["fitted_rows"]), "assigned": len(payload["assigned_rows"]),
                "sample": payload["sample"], "seed": payload["seed"], "k": k,
                "k_rule": payload["k_rule"], "k_scores": payload.get("k_scores", []),
                "null": payload.get("null"),
                "assigned_by": "nearest family centroid by shape-based distance (k-Shape's predict)"}

    # ----------------------------------------------------------- estimate

    def estimate(self, n, params, basis=None):
        """Seconds to fit n items (coefficients above `C_START`): the auto-k
        sweep (one start per k = 2..12 on at most 2,000 rows, plus their
        square SBD for the silhouette), `n_init` starts of the final k on
        the fitted rows — priced at k = 12 when k is chosen, an upper bound —
        the rows assigned after the fit, the null draws, and the quiet-stretch
        null's windows (`quiet_windows_estimate`: priced whenever a null is drawn,
        since the estimate cannot know whether a background will be handed in)."""
        n = int(n)
        k = int(params.get("k", DEFAULT_K))
        n_init = max(1, int(params.get("n_init", DEFAULT_N_INIT)))
        n_fit = min(n, int(params.get("sample", DEFAULT_SAMPLE)) or n)
        draws = max(0, int(params.get("null_draws", NULL_DRAWS)))
        final_k = k if k > 0 else K_RANGE[1]
        seconds = 0.0
        if k <= 0:
            n_sweep = min(n_fit, SILHOUETTE_SAMPLE)
            seconds += sum(range(K_RANGE[0], K_RANGE[1] + 1)) * n_sweep * C_START
            seconds += n_sweep * n_sweep * C_PAIR
        seconds += n_init * final_k * n_fit * C_START
        seconds += (n - n_fit) * final_k * C_PREDICT
        seconds += draws * min(n_fit, NULL_ROWS) * final_k * C_PREDICT
        # w3-g: the quiet-stretch null's windows (when the caller hands the engine a background)
        if draws:
            seconds += quiet_windows_estimate(n) * C_QUIET_WINDOW
        return float(seconds)

    def cheaper(self, n, params):
        """What a refusal can offer instead, cheapest change first."""
        out = []
        if int(params.get("k", DEFAULT_K)) <= 0:
            out.append(("set k (6) instead of choosing it", {"k": 6}))
        if int(params.get("n_init", DEFAULT_N_INIT)) > 3:
            out.append(("3 random starts", {"n_init": 3}))
        if int(params.get("sample", DEFAULT_SAMPLE)) > 2000:
            out.append(("fit on 2,000 members, assign the rest", {"sample": 2000}))
        out.append(("k = 6, 3 starts, fit on 2,000", {"k": 6, "n_init": 3, "sample": 2000}))
        return out

    # ------------------------------------------------------------- assign

    def assign(self, fit, *, cut=None, omit_d=None):
        """A family id per row, `None` where the row fits no family. `cut` is
        accepted for the engine's sake and ignored (no tree). `omit_d` is this
        method's cut: None - no omission - when a direct caller leaves it out,
        exactly as Ward's `assign` does; 0 = automatic, each family's own null
        5th percentile (the engine passes the param's default, 0); a number
        > 0 is a fixed distance."""
        fit.omit_reasons.clear()
        fit.omit_reasons.update(fit.payload.get("screened_out", {}))
        if fit.n == 0:
            return []
        cluster = fit.payload["cluster"]
        dist = fit.payload["dist"]
        family_of = fit.payload["family_of_cluster"]
        p05 = fit.payload.get("null_p05") or {}
        automatic = omit_d is not None and float(omit_d) <= 0
        out = []
        for i in range(fit.n):
            if i in fit.omit_reasons:
                out.append(None)
                continue
            if automatic:
                limit = p05.get(int(cluster[i]))
            else:
                limit = None if omit_d is None else float(omit_d)
            if limit is not None and dist[i] > limit:
                fit.omit_reasons[i] = OMIT_PAST_CUT
                out.append(None)
                continue
            out.append(family_of[int(cluster[i])])
        fit.family_labels = {f: f"F-{f:02d}" for f in sorted(set(family_of.values()))}
        return out

    # ------------------------------------------------------------- medoid

    def medoid(self, fit, indices):
        """`(row, mean distance to the rest)`: the member nearest its family's
        centroid by SBD — k-Shape's centre is that centroid, and the drawing
        standard draws a member, never an average — and the mean normalised
        SBD from it to the other members."""
        indices = list(indices)
        if not indices:
            raise ValueError("A family with no members has no medoid.")
        dist = fit.payload["dist"]
        best = min(indices, key=lambda i: (dist[i], i))
        if len(indices) == 1:
            return best, 0.0
        column = fit.distances.column(best)
        others = [i for i in indices if i != best]
        return best, float(np.nanmean(column[others]))

    # ------------------------------------------------------ merge_heights

    def merge_heights(self, fit):
        """k-Shape builds no tree: `[]`, never a fabricated distribution."""
        return []


register(KShapeMethod())
