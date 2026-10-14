"""
hdbscan.py
============
HDBSCAN (Campello, Moulavi & Sander 2013, PAKDD) as a Library grouping method
for the `shape-distance` basis — `sklearn.cluster.HDBSCAN` (1.7.2) on a
precomputed matrix of normalised shape-based distances.

In plain words: instead of "split everything into k piles", HDBSCAN looks for
the places where shapes crowd together and leaves the stragglers out as "no
family" — there is no number of families to choose. A straggler is omitted
with the reason `not_in_a_dense_family`, which is the clustering version of
the background class the round-B discussion asked for: forcing noise into a
motif family is the failure this method exists to avoid.

What is computed
----------------
1. Ward's shape vectors (`ward.shape_vectors`: resampled to 256 samples,
   z-normalised). A waveform holding a NaN or an inf has no shape; it is
   screened out before any distance with `missing_values` / `infinite_values`,
   the reasons sklearn's -3 / -2 labels stand for (and, should sklearn itself
   emit -2 or -3, they map to the same two reasons).
2. A square distance matrix over the fitted rows: by default SBD / 2
   (`Working.distances.sbd_matrix`, computed in single precision — ~1e-6 on a
   [0, 1] scale, half the time), or, with `distance = euclidean`, Ward's own
   normalised scale-invariant distance (`ward.condensed_distances`). Both sit
   on the editor's [0, 1] scale.
3. `HDBSCAN(metric="precomputed", min_cluster_size, min_samples,
   cluster_selection_method, cluster_selection_epsilon = epsilon,
   allow_single_cluster=False, copy=True)`. `min_samples = 0` means sklearn's
   default (None), which equals `min_cluster_size`.
4. Families are numbered by size, largest first.

Scale
-----
The square matrix is n^2: the fit runs on at most `sample` rows (default
5,000, seeded, recorded). Every other row joins the family of its nearest
fitted *member* (never a noise row) if that distance is within the family's
largest core distance — the core distance of a fitted row being, as in
sklearn's brute-force path, its distance to its `min_samples`-th nearest row
counting itself — and is otherwise `not_in_a_dense_family`. That is the
"would it have been inside the crowd" test, not a nearest-centroid one,
because a density family has no centre. `payload` lists the fitted and the
assigned rows.

Is a family real? (the per-family null, fix round 2)
----------------------------------------------------
HDBSCAN always answers, and on coloured noise it reliably finds crowds:
windows of AR(1) or random-walk background are mostly a trend, and trends
crowd. Round 1 re-ran HDBSCAN on phase-randomised surrogates and compared
crowd sizes and separations; the re-critique showed that fails both ways,
because phase randomisation turns each trend into a periodic wiggle, so the
fake noise crowds less than real noise does (and a size-matched variant was
worse: 16 of 26 pure-noise families confident). The test is now k-Shape's,
run per family, against noise of the family's own colour:

1. m = the family's medoid (least summed distance among its fitted members).
2. d_F = the median normalised SBD from the family's members to m.
3. `NULL_DRAWS` (3) seeded draws of **trend-kept** phase-randomised
   surrogates of the family's own members (`kshape.trend_kept_surrogates`: a
   cubic trend kept per row, the rest phase-randomised, then z-normalised),
   measured against m; p05 = their 5th percentile. The manager asked for a
   line; a cubic is used because a line left one pure-noise family confident
   (the measurement is beside `kshape.TREND_DEGREE`).
4. The family is confident iff d_F < `NULL_MARGIN` x p05; otherwise
   `noise_like`, and `unstable` when d_F is not even below p05.

`NULL_MARGIN` = 0.9 is a PLACEHOLDER: the selection effect (a family's
members were chosen for being close to each other) puts a noise crowd right at
p05 on a random-walk background (ratios 1.001-1.07), and noise rows inside a
mixed family reached 0.89-0.92. With the cubic trend kept, 10 pure-noise sets
gave ratios of 1.05 and up, 8 real sets 0.66 and below. The flags carry
d_F (`median_distance`), `null_p05` and `ratio`. Families are flagged, never
dissolved. The test needs |F| x 3 SBDs against one row per family —
milliseconds — so no surrogate matrix is stored and HDBSCAN runs once.

The separation is still reported per family — the median distance from a
member to the fitted rows outside the family over the median distance between
its own members — as a number to read, not a decider.

No merge heights
----------------
`merge_heights` is `[]`. HDBSCAN does build a tree, but the values it selects
clusters on are the condensed tree's lambda = 1 / distance stabilities, read
off sklearn's private `_condense_tree`; drawing them under the editor's
distance-scale cut slider would be a different quantity on a misleading axis,
so none are given (LIBRARY_STORAGE.md 6.2 item 5).

`epsilon` is `cluster_selection_epsilon`: families closer than this are not
split. It was called `cut` in round 1, which invited wiring the editor's tree
cut (default 0.42) into it and silently merging families (critic finding 6);
`assign(cut=...)` now ignores the tree cut — HDBSCAN has no tree to cut — and
`assign(epsilon=...)` re-selects on the stored distances.
"""

import numpy as np
from scipy.spatial.distance import squareform

from Working.distances import sbd_matrix
from Working.library.grouping.engine import (OMIT_INFINITE_VALUES, OMIT_MISSING_VALUES,
                                             OMIT_NOT_IN_A_DENSE_FAMILY)
from Working.library.grouping.methods import FitResult, register
from Working.library.grouping.engine import GroupingCancelled
from Working.library.grouping.methods.kshape import (SBD_SCALE, NormalisedSBD,
                                                     _z_rows, null_rng, sample_positions,
                                                     screen_rows, trend_kept_surrogates)
from Working.library.grouping.methods.ward import (RESAMPLE_LENGTH, condensed_distances,
                                                   shape_vectors)
from Working.library.grouping.methods.ward import distance_scale as ward_distance_scale

DEFAULT_MIN_CLUSTER_SIZE = 10     # the Library's ten-member floor (spec 9.10)
DEFAULT_MIN_SAMPLES = 0           # 0 = None = sklearn's default, min_cluster_size
DEFAULT_SELECTION = "eom"
DEFAULT_EPSILON = 0.0             # cluster_selection_epsilon; sklearn's default
DEFAULT_DISTANCE = "sbd"
DEFAULT_SAMPLE = 5000
DEFAULT_SEED = 0
DEFAULT_MIN_GROUP = 10
SELECTIONS = ("eom", "leaf")
DISTANCES = ("sbd", "euclidean")

NULL_DRAWS = 3                    # trend-kept surrogate draws per family member
NULL_MARGIN = 0.9                 # PLACEHOLDER: confident iff d_F < 0.9 x the null's p05
NULL_PERCENTILE = 5.0
NULL_MEMBERS = 2000               # members of one family the null is drawn from, at most

# Cost (fix round 1, item 3), measured on this machine (2026-10-14, loaded by
# other jobs; the earlier unloaded runs were ~2x faster): the square SBD matrix
# 3.2e-6 s per ordered pair at 2,000 rows (12.8 s; 4.9 s unloaded), sklearn's
# HDBSCAN on it 1.4e-6 s per pair (5.5 s); the rows assigned after the fit
# 2.3e-6 s per (row, fitted member) — the 20,000-item run's 15,000 x 5,000
# pairs. Mid-range values are used: a refusal on a loaded machine is cheaper
# than a 20-minute run that was promised as 8.
C_SQUARE = 2.0e-6
C_CLUSTER = 1.0e-6
C_CROSS = 2.5e-6
C_NULL_ROW = 2.0e-4               # one surrogate row made and measured against a medoid

# rows of the not-fitted set compared against the fitted members at once
_ASSIGN_BLOCK = 2000


def _distance_matrix(V, distance):
    if distance == "sbd":
        return sbd_matrix(V, z_normalise=False, dtype=np.float32) / SBD_SCALE
    return squareform(condensed_distances(V))


def _cross_distances(A, B, distance):
    if distance == "sbd":
        return sbd_matrix(A, B, z_normalise=False, dtype=np.float32) / SBD_SCALE
    from scipy.spatial.distance import cdist
    return cdist(A, B) / ward_distance_scale(A.shape[1])


def _hdbscan(D, *, min_cluster_size, min_samples, selection, epsilon):
    from sklearn.cluster import HDBSCAN
    n = D.shape[0]
    mcs = max(2, min(int(min_cluster_size), n))
    ms = None if not min_samples else max(1, min(int(min_samples), n))
    model = HDBSCAN(min_cluster_size=mcs, min_samples=ms, metric="precomputed",
                    cluster_selection_method=selection, cluster_selection_epsilon=float(epsilon),
                    allow_single_cluster=False, copy=True)
    model.fit(D)
    return model.labels_.astype(np.int64), model.probabilities_.astype(float), (ms or mcs)


def _stability(D, labels, probabilities):
    """Per cluster label: median membership strength and separation (module
    docstring), on the fitted rows."""
    out = {}
    for c in sorted(set(labels.tolist()) - {-1, -2, -3}):
        inside = np.flatnonzero(labels == c)
        outside = np.flatnonzero(labels != c)
        block = D[np.ix_(inside, inside)]
        within = float(np.median(block[np.triu_indices(inside.size, 1)])) if inside.size > 1 else 0.0
        between = float(np.median(D[np.ix_(inside, outside)])) if outside.size else float("nan")
        separation = (between / within) if within > 0 else float("inf")
        out[int(c)] = {"size_fitted": int(inside.size),
                       "median_probability": float(np.median(probabilities[inside])),
                       "within": within, "between": between, "separation": separation}
    return out


class HDBSCANMethod:
    """HDBSCAN on a precomputed shape-distance matrix; stragglers omitted."""

    name = "hdbscan"
    label = "HDBSCAN (density)"
    description = ("HDBSCAN (Campello et al. 2013): families are the places where shapes crowd "
                   "together; stragglers are left out as 'no family' and no number of families "
                   "is chosen. Tune the minimum family size first.")
    applies_to = ("shape-distance",)

    params = {
        "min_cluster_size": {
            "type": "int", "default": DEFAULT_MIN_CLUSTER_SIZE, "label": "minimum family size",
            "help": "the smallest crowd of shapes that counts as a family — the Library's "
                    "ten-member floor. Larger finds fewer, bigger families.",
        },
        "min_samples": {
            "type": "int", "default": DEFAULT_MIN_SAMPLES, "label": "neighbours for a core shape",
            "help": "how many close neighbours a shape needs to sit inside a crowd; 0 uses the "
                    "minimum family size (sklearn's default). Larger leaves more out as noise.",
        },
        "cluster_selection_method": {
            "type": "str", "default": DEFAULT_SELECTION, "label": "selection",
            "help": "eom keeps the most persistent crowds (fewer, larger families); leaf keeps "
                    "the finest ones (more, smaller, more homogeneous families).",
        },
        "epsilon": {
            "type": "float", "default": DEFAULT_EPSILON, "label": "merge closer than (epsilon)",
            "help": "HDBSCAN's cluster_selection_epsilon on the 0-1 distance scale: families "
                    "closer than this are not split apart. 0 = HDBSCAN's own choice. Not the "
                    "tree cut — HDBSCAN has no tree to cut; even 0.1 merges similar shapes.",
        },
        "distance": {
            "type": "str", "default": DEFAULT_DISTANCE, "label": "distance",
            "help": "sbd compares shapes after sliding one along the other to the best match "
                    "(k-Shape's distance); euclidean compares them point by point (Ward's "
                    "scale-invariant distance).",
        },
        "min_group": {
            "type": "int", "default": DEFAULT_MIN_GROUP, "label": "minimum group",
            "help": "families under this many members are omitted and flagged (spec 9.10); "
                    "applied by the engine after the rows not fitted are assigned.",
        },
        "sample": {
            "type": "int", "default": DEFAULT_SAMPLE, "label": "fit on at most",
            "help": "members the density fit is computed on (its distance matrix is n x n); "
                    "above this many a seeded sample is fitted and the rest join the family of "
                    "their nearest fitted member if they sit within its crowd.",
        },
        "seed": {
            "type": "int", "default": DEFAULT_SEED, "label": "seed",
            "help": "the random seed for the sample; HDBSCAN itself is deterministic.",
        },
        "resample_length": {
            "type": "int", "default": RESAMPLE_LENGTH, "label": "resample length",
            "help": "samples every span is resampled to before z-normalising — Ward's 256.",
        },
        "null_draws": {
            "type": "int", "default": NULL_DRAWS, "label": "noise draws",
            "help": "how many trend-kept surrogates of each family member (its slow trend kept, the "
                    "rest phase-randomised: noise of its own colour) the family is measured "
                    "against; a family is confident only if its members sit closer to its medoid "
                    "than 0.9 x (a placeholder margin) the 5th percentile of those surrogates. 0 = "
                    "no null: families are reported untested. Cheap: milliseconds per family.",
        },
    }

    # ---------------------------------------------------------------- fit

    def fit(self, waveforms, *, params=None, should_cancel=None):
        params = params or {}
        L = int(params.get("resample_length", RESAMPLE_LENGTH))
        distance = str(params.get("distance", DEFAULT_DISTANCE))
        selection = str(params.get("cluster_selection_method", DEFAULT_SELECTION))
        if distance not in DISTANCES:
            raise ValueError(f"hdbscan distance must be one of {DISTANCES}; got {distance!r}.")
        if selection not in SELECTIONS:
            raise ValueError(f"hdbscan cluster_selection_method must be one of {SELECTIONS}; "
                             f"got {selection!r}.")
        epsilon = params.get("epsilon", DEFAULT_EPSILON)
        epsilon = DEFAULT_EPSILON if epsilon is None else float(epsilon)
        sample = int(params.get("sample", DEFAULT_SAMPLE))
        seed = int(params.get("seed", DEFAULT_SEED))
        waveforms = list(waveforms)
        n = len(waveforms)

        ok, bad = screen_rows(waveforms)
        positions = np.full(n, -1, dtype=np.int64)
        positions[ok] = np.arange(len(ok))
        vectors = shape_vectors([waveforms[i] for i in ok], L) if ok else np.zeros((0, L))
        fitted_pos, assigned_pos = sample_positions(len(ok), sample, seed)
        payload = {
            "resample_length": L,
            "distance_scale": SBD_SCALE if distance == "sbd" else float(ward_distance_scale(L)),
            "distance": distance, "vectors": vectors, "positions": positions,
            "screened_out": dict(bad), "sample": sample, "seed": seed,
            "settings": {"min_cluster_size": int(params.get("min_cluster_size", DEFAULT_MIN_CLUSTER_SIZE)),
                         "min_samples": int(params.get("min_samples", DEFAULT_MIN_SAMPLES) or 0),
                         "cluster_selection_method": selection},
            "fitted_rows": [int(ok[p]) for p in fitted_pos],
            "assigned_rows": [int(ok[p]) for p in assigned_pos],
            "fitted_pos": fitted_pos, "assigned_pos": assigned_pos,
        }
        fit = FitResult(method=self.name, n=n, payload=payload)
        fit.omit_reasons.update(bad)
        on_demand = NormalisedSBD if distance == "sbd" else _EuclideanOnDemand
        fit.distances = on_demand(vectors, positions, n)
        payload["null_draws"] = int(params.get("null_draws", NULL_DRAWS))
        if fitted_pos.size:
            payload["D_fit"] = _distance_matrix(vectors[fitted_pos], distance)
            if should_cancel is not None and should_cancel():
                raise GroupingCancelled("cancelled after the HDBSCAN distance matrix")
        self._cluster(fit, epsilon)
        return fit

    def _cluster(self, fit, epsilon):
        """Run the density step on the stored fitted matrix at `epsilon`, then
        place the rows not fitted. Kept apart from `fit` so `assign` at a new
        epsilon re-selects clusters without recomputing a single distance."""
        p = fit.payload
        n = fit.n
        ok_rows = np.flatnonzero(p["positions"] >= 0)
        labels_ok = np.full(ok_rows.size, -1, dtype=np.int64)
        p.update(epsilon=epsilon, family_stability={}, family_of_label={}, family_flags={}, null=None)
        p["label"] = np.full(n, -1, dtype=np.int64)
        p["placed_by"] = {}
        fitted_pos, assigned_pos = p["fitted_pos"], p["assigned_pos"]
        if fitted_pos.size == 0:
            p["fit_summary"] = self._summary(p, n, 0)
            return
        D = p["D_fit"]
        s = p["settings"]
        if fitted_pos.size == 1:
            labels, probs, ms = np.zeros(1, dtype=np.int64), np.ones(1), 1
        else:
            labels, probs, ms = _hdbscan(D, min_cluster_size=s["min_cluster_size"],
                                         min_samples=s["min_samples"],
                                         selection=s["cluster_selection_method"], epsilon=epsilon)
        labels_ok[fitted_pos] = labels
        p["probabilities"] = probs
        p["family_stability"] = _stability(D, labels, probs) if fitted_pos.size > 1 else {}

        if assigned_pos.size:
            k = min(ms, fitted_pos.size)
            core = np.partition(D, k - 1, axis=1)[:, k - 1]
            member = np.flatnonzero(labels >= 0)
            if member.size:
                reach = {int(c): float(core[labels == c].max()) for c in set(labels[member].tolist())}
                V_members = p["vectors"][fitted_pos[member]]
                for b0 in range(0, assigned_pos.size, _ASSIGN_BLOCK):
                    block = assigned_pos[b0:b0 + _ASSIGN_BLOCK]
                    Dr = _cross_distances(p["vectors"][block], V_members, p["distance"])
                    nearest = Dr.argmin(axis=1)
                    near_d = Dr[np.arange(block.size), nearest]
                    near_label = labels[member][nearest]
                    inside = near_d <= np.array([reach[int(c)] for c in near_label])
                    labels_ok[block[inside]] = near_label[inside]

        sizes = {}
        for c in labels_ok.tolist():
            if c >= 0:
                sizes[c] = sizes.get(c, 0) + 1
        order = sorted(sizes, key=lambda c: (-sizes[c], c))
        p["family_of_label"] = {c: rank + 1 for rank, c in enumerate(order)}
        p["label"][ok_rows] = labels_ok
        self._null(p, epsilon)
        p["fit_summary"] = self._summary(p, n, ok_rows.size)

    @staticmethod
    def _null(p, epsilon):
        """The per-family trend-kept null (module docstring)."""
        draws = int(p.get("null_draws", NULL_DRAWS))
        rule = (f"per family: d_F = the members' median normalised distance to the family medoid; "
                f"p05 = the {NULL_PERCENTILE:g}th percentile of the distances of {draws} draws of "
                f"trend-kept phase-randomised surrogates of the family's own members (a cubic trend "
                f"kept per row, the rest phase-randomised, z-normalised) to the same medoid; confident "
                f"iff d_F < {NULL_MARGIN} x p05 ({NULL_MARGIN} is a placeholder margin)")
        if draws <= 0 or not p.get("family_of_label"):
            p["null"] = {"kind": "none" if draws <= 0 else "trend-kept phase-randomised",
                         "draws": max(draws, 0), "margin": NULL_MARGIN, "by_family": {},
                         "rule": ("no null drawn (null_draws = 0): families untested"
                                  if draws <= 0 else rule)}
            return
        vectors, positions = p["vectors"], p["positions"]
        ok_rows = np.flatnonzero(positions >= 0)
        label_ok = p["label"][ok_rows]
        fitted_pos = p["fitted_pos"]
        fitted_label = label_ok[fitted_pos]
        D = p["D_fit"]
        by_family = {}
        for c, fam in p["family_of_label"].items():
            fitted_members = np.flatnonzero(fitted_label == c)
            m_fit = fitted_members[int(np.argmin(D[np.ix_(fitted_members, fitted_members)].sum(axis=1)))]
            m_vec = vectors[fitted_pos[m_fit]][None, :]
            members = np.flatnonzero(label_ok == c)                 # vector positions
            d = _cross_distances(vectors[members], m_vec, p["distance"])[:, 0]
            d_F = float(np.median(d))
            rng = null_rng(p["seed"], 13 + int(c))
            pick, _ = sample_positions(members.size, NULL_MEMBERS, p["seed"])
            surrogate_d = []
            for _ in range(draws):
                S = _z_rows(trend_kept_surrogates(vectors[members[pick]], rng))
                surrogate_d.append(_cross_distances(S, m_vec, p["distance"])[:, 0])
            p05 = float(np.percentile(np.concatenate(surrogate_d), NULL_PERCENTILE))
            ratio = d_F / p05 if p05 > 0 else float("inf")
            noise_like = not (d_F < NULL_MARGIN * p05)
            st = p["family_stability"].get(c, {})
            why = (f"members' median distance to the medoid {d_F:.3f} is {ratio:.2f} x the 5th "
                   f"percentile {p05:.3f} of trend-kept noise of their own colour ({draws} draws); "
                   f"confident below {NULL_MARGIN} x (a placeholder margin)")
            p["family_flags"][fam] = {
                "noise_like": bool(noise_like), "unstable": bool(not (d_F < p05)), "tested": True,
                "why": ("no better than noise of the same colour: " + why) if noise_like else why,
                "median_distance": d_F, "null_p05": p05, "ratio": float(ratio),
                "margin": NULL_MARGIN,
                "separation": float(st.get("separation", float("nan"))),
                "size_fitted": int(st.get("size_fitted", fitted_members.size))}
            by_family[f"F-{fam:02d}"] = {"median_distance": d_F, "null_p05": p05, "ratio": float(ratio)}
        p["null"] = {"kind": "trend-kept phase-randomised", "draws": draws, "margin": NULL_MARGIN,
                     "percentile": NULL_PERCENTILE, "by_family": by_family, "rule": rule}

    @staticmethod
    def _summary(p, n, n_ok):
        return {"rows": n, "screened_out": n - n_ok, "fitted": len(p["fitted_rows"]),
                "assigned": len(p["assigned_rows"]), "sample": p["sample"], "seed": p["seed"],
                "distance": p["distance"], "epsilon": p.get("epsilon"),
                "families": len(p.get("family_of_label", {})),
                "null": p.get("null"),
                "assigned_by": ("the family of the nearest fitted member, when within that "
                                "family's largest core distance; else not_in_a_dense_family")}

    # ----------------------------------------------------------- estimate

    def estimate(self, n, params, basis=None):
        """Seconds: the fitted matrix and its clustering, once for the data and
        once per null draw, plus the rows assigned after the fit."""
        n = int(n)
        n_fit = min(n, int(params.get("sample", DEFAULT_SAMPLE)) or n)
        draws = max(0, int(params.get("null_draws", NULL_DRAWS)))
        square = n_fit * n_fit * (C_SQUARE + C_CLUSTER)
        # the per-family null: every member's surrogates against one medoid
        return float(square + (n - n_fit) * n_fit * C_CROSS + draws * n * C_NULL_ROW)

    def cheaper(self, n, params):
        out = []
        if int(params.get("sample", DEFAULT_SAMPLE)) > 2000:
            out.append(("fit on 2,000 members, assign the rest", {"sample": 2000}))
        out.append(("fit on 1,000 members, assign the rest", {"sample": 1000}))
        return out

    # ------------------------------------------------------------- assign

    def assign(self, fit, *, cut=None, epsilon=None):
        """A family id per row; `None` for noise (`not_in_a_dense_family`) and
        for a screened-out row. `cut` — the editor's tree cut, which the
        engine always passes — is ignored: HDBSCAN has no tree. An `epsilon`
        other than the fitted one re-selects the clusters on the stored
        distances (no distance is recomputed)."""
        fit.omit_reasons.clear()
        fit.omit_reasons.update(fit.payload.get("screened_out", {}))
        if fit.n == 0:
            return []
        if epsilon is not None and float(epsilon) != fit.payload.get("epsilon"):
            self._cluster(fit, float(epsilon))
        label = fit.payload["label"]
        family_of = fit.payload["family_of_label"]
        out = []
        for i in range(fit.n):
            if i in fit.omit_reasons:
                out.append(None)
                continue
            c = int(label[i])
            if c >= 0:
                out.append(family_of[c])
                continue
            fit.omit_reasons[i] = {-2: OMIT_INFINITE_VALUES,
                                   -3: OMIT_MISSING_VALUES}.get(c, OMIT_NOT_IN_A_DENSE_FAMILY)
            out.append(None)
        fit.family_labels = {f: f"F-{f:02d}" for f in sorted(family_of.values())}
        return out

    # ------------------------------------------------------------- medoid

    def medoid(self, fit, indices):
        """`(row, mean distance to the rest)`: the member with the least summed
        distance to the family's other FITTED members (a density family has no
        centroid; the rows assigned after the fit are not in the matrix, and
        a family always holds fitted members, because the assigned rows only
        join through one). The drawing standard draws a member, never an
        average."""
        indices = list(indices)
        if not indices:
            raise ValueError("A family with no members has no medoid.")
        if len(indices) == 1:
            return indices[0], 0.0
        p = fit.payload
        fitted = set(p["fitted_rows"])
        pool = [i for i in indices if i in fitted] or indices
        pos_in_fit = {row: k for k, row in enumerate(p["fitted_rows"])}
        if all(i in pos_in_fit for i in pool):
            idx = [pos_in_fit[i] for i in pool]
            sums = p["D_fit"][np.ix_(idx, idx)].sum(axis=1)
            best = pool[int(np.argmin(sums))]
        else:
            best = min(pool, key=lambda i: float(np.nansum(fit.distances.column(i)[pool])))
        column = fit.distances.column(best)
        others = [i for i in indices if i != best]
        return best, float(np.nanmean(column[others]))

    # ------------------------------------------------------ merge_heights

    def merge_heights(self, fit):
        """`[]` — see the module docstring for why the tree's lambdas are not given."""
        return []


class _EuclideanOnDemand(NormalisedSBD):
    """`fit.distances` under `distance = euclidean`: Ward's normalised
    distance, one column at a time."""

    def column(self, j):
        j = int(j)
        if j not in self._columns:
            pos = int(self.positions[j])
            out = np.full(self.shape[0], np.nan)
            if pos >= 0:
                d = _cross_distances(self.vectors, self.vectors[pos:pos + 1], "euclidean")[:, 0]
                out[self.positions >= 0] = d[self.positions[self.positions >= 0]]
            self._columns[j] = out
        return self._columns[j]


register(HDBSCANMethod())
