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

The surrogate null (w2-b fix round 1)
-------------------------------------
k-Shape always returns k families and, on the SBD scale, a fixed `omit_d`
cannot tell noise from members: two unrelated white-noise windows sit at a
median 0.42 (so Ward's 0.50 never fires), and coloured noise sits *closer* to
a centroid than noisy real members do. So the yardstick is the data's own
colour: every fitted row (at most `NULL_ROWS`, seeded) is phase-randomised
`null_draws` times (`phase_randomised_rows`: amplitude spectrum kept, shape
destroyed) and each surrogate is measured against the fitted centroids. A
surrogate counts toward the family whose centre it lands nearest — the same
"nearest of k" selection a real member went through — or, when fewer than
`NULL_MIN_PER_FAMILY` land, every surrogate's distance to that centre is used.
Per family:

* `omit_d = 0` (the default, the site's "0 = auto"): a member further from its
  centre than the null's 5th percentile is omitted `past_cut`;
* the family is `noise_like` when its members' median distance is not below
  that 5th percentile, and `unstable` when it is not below the null's median.

Families are flagged, never dissolved; the flags and the null travel on the
`GroupingResult` (`Family.flags`, `fit_summary["null"]`). A fixed `omit_d`
> 0 still works.

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
                    "further from its family's centre than 95 % of phase-randomised noise of the "
                    "same colour does. A number > 0 is a fixed shape-based distance instead (0 = a "
                    "shifted copy); note that Ward's 0.5 almost never fires on this scale - two "
                    "unrelated noise windows already sit near 0.42.",
        },
        "null_draws": {
            "type": "int", "default": NULL_DRAWS, "label": "noise draws",
            "help": "how many phase-randomised surrogate sets (each window's colour kept, its "
                    "shape destroyed) the families are measured against. 0 = no null: families "
                    "are reported untested and the automatic omit_d omits nothing.",
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

    def fit(self, waveforms, *, params=None, should_cancel=None):
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
        self._null(payload, V_fit, labels, dist / SBD_SCALE, k, seed, draws, should_cancel)
        payload["fit_summary"] = self._summary(payload, n, n_ok, k)
        return fit

    @staticmethod
    def _null(payload, V_fit, labels, dist, k, seed, draws, should_cancel=None):
        """The surrogate null (module docstring): per cluster, the distances of
        phase-randomised surrogates to its centroid, their 5th percentile (the
        automatic `omit_d`) and median, and each family's flags. `labels` and
        `dist` are over every screened-in row (fitted and assigned)."""
        family_of = payload["family_of_cluster"]
        payload["null_p05"], payload["family_flags"] = {}, {}
        if draws <= 0:
            payload["null"] = {"kind": "none", "draws": 0,
                               "rule": "no null drawn (null_draws = 0): families untested, "
                                       "the automatic omit_d omits nothing"}
            return
        rng = null_rng(seed, 11)
        sub, _ = sample_positions(V_fit.shape[0], NULL_ROWS, seed)
        Vs = V_fit[sub]
        landed = {c: [] for c in range(k)}
        every = {c: [] for c in range(k)}
        for _ in range(draws):
            if should_cancel is not None and should_cancel():
                raise GroupingCancelled("cancelled while drawing the k-Shape null")
            S = _z_rows(phase_randomised_rows(Vs, rng))
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
        payload["null_p05"] = p05
        for c, fam in family_of.items():
            med = float(np.median(dist[labels == c]))
            noise_like = med >= p05[c]
            unstable = med >= p50[c]
            why = (f"members' median distance to the centre {med:.3f} is "
                   + ("not below" if noise_like else "below")
                   + f" the noise's 5th percentile {p05[c]:.3f} ({draws} phase-randomised draws "
                   + f"of {len(sub)} rows; the noise's median is {p50[c]:.3f})")
            payload["family_flags"][fam] = {
                "noise_like": bool(noise_like), "unstable": bool(unstable), "tested": True,
                "why": ("no better than noise of the same colour: " + why) if noise_like else why,
                "median_distance": med, "null_p05": p05[c], "null_median": p50[c]}
        label = {c: f"F-{f:02d}" for c, f in family_of.items()}
        payload["null"] = {
            "kind": "phase-randomised", "draws": draws, "rows_per_draw": int(len(sub)),
            "percentile": NULL_PERCENTILE,
            "omit_d_by_family": {label[c]: p05[c] for c in family_of},
            "median_by_family": {label[c]: p50[c] for c in family_of},
            "from": {label[c]: source[c] for c in family_of},
            "rule": (f"each fitted row phase-randomised (amplitude spectrum kept) {draws} times; a "
                     f"surrogate counts toward the family whose centre it lands nearest (all "
                     f"surrogates when fewer than {NULL_MIN_PER_FAMILY} land); automatic omit_d = "
                     f"their {NULL_PERCENTILE:g}th percentile; a family is noise-like when its "
                     f"members' median distance is not below that, unstable when not below the "
                     f"noise's median")}

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
        the rows assigned after the fit, and the null draws."""
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
