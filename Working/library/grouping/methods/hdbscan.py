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
   cluster_selection_method, cluster_selection_epsilon = cut,
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

Is a family real? (stability)
-----------------------------
HDBSCAN always answers, and on pure noise it can still find a "crowd" of two
by chance. sklearn exposes no cluster stability (its condensed tree is
private), so each family carries a plain, public check in
`payload["family_stability"]`: its members' median membership strength
(`probabilities_`) and its **separation** — the median distance from a member
to the fitted rows outside the family over the median distance between its own
members. On the synthetic tests a family of shifted copies separates at 3.3 or
more and a chance crowd in coloured noise at 2.8 or less. A family below
`UNSTABLE_SEPARATION` is flagged
`unstable: true` and `payload["unstable_families"]` names them — the families
are still returned (the method does not overrule HDBSCAN), but they are never
presented as confident.

No merge heights
----------------
`merge_heights` is `[]`. HDBSCAN does build a tree, but the values it selects
clusters on are the condensed tree's lambda = 1 / distance stabilities, read
off sklearn's private `_condense_tree`; drawing them under the editor's
distance-scale cut slider would be a different quantity on a misleading axis,
so none are given (LIBRARY_STORAGE.md 6.2 item 5). The `cut` here is
`cluster_selection_epsilon`: families closer than this are not split.
"""

import numpy as np
from scipy.spatial.distance import squareform

from Working.distances import sbd_matrix
from Working.library.grouping.engine import (OMIT_INFINITE_VALUES, OMIT_MISSING_VALUES,
                                             OMIT_NOT_IN_A_DENSE_FAMILY)
from Working.library.grouping.methods import FitResult, register
from Working.library.grouping.methods.kshape import (SBD_SCALE, NormalisedSBD, sample_positions,
                                                     screen_rows)
from Working.library.grouping.methods.ward import (RESAMPLE_LENGTH, condensed_distances,
                                                   shape_vectors)
from Working.library.grouping.methods.ward import distance_scale as ward_distance_scale

DEFAULT_MIN_CLUSTER_SIZE = 10     # the Library's ten-member floor (spec 9.10)
DEFAULT_MIN_SAMPLES = 0           # 0 = None = sklearn's default, min_cluster_size
DEFAULT_SELECTION = "eom"
DEFAULT_CUT = 0.0                 # cluster_selection_epsilon; sklearn's default
DEFAULT_DISTANCE = "sbd"
DEFAULT_SAMPLE = 5000
DEFAULT_SEED = 0
DEFAULT_MIN_GROUP = 10
SELECTIONS = ("eom", "leaf")
DISTANCES = ("sbd", "euclidean")

# A family whose members sit barely closer to each other than to everything
# else is a chance crowd. 3.0 is a PLACEHOLDER read off the synthetic tests,
# not a measurement on recordings: three shifted shape families on AR(1),
# random-walk and drift backgrounds separate at 3.3-13.5; the "families"
# HDBSCAN finds in pure coloured noise (AR(1) at phi 0.95-0.99, random walk,
# drift — windows that mostly drift up or drift down) at 1.6-2.8; white noise
# gives none. The margin (2.8 vs 3.3) is thin; measure it on real families
# and on surrogate recordings before trusting the flag.
UNSTABLE_SEPARATION = 3.0

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


def _hdbscan(D, *, min_cluster_size, min_samples, selection, cut):
    from sklearn.cluster import HDBSCAN
    n = D.shape[0]
    mcs = max(2, min(int(min_cluster_size), n))
    ms = None if not min_samples else max(1, min(int(min_samples), n))
    model = HDBSCAN(min_cluster_size=mcs, min_samples=ms, metric="precomputed",
                    cluster_selection_method=selection, cluster_selection_epsilon=float(cut),
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
                       "within": within, "between": between, "separation": separation,
                       "unstable": bool(np.isfinite(separation) and separation < UNSTABLE_SEPARATION)}
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
        "cut": {
            "type": "float", "default": DEFAULT_CUT, "label": "merge closer than",
            "help": "HDBSCAN's cluster_selection_epsilon on the 0-1 distance scale: families "
                    "closer than this are not split apart. 0 = HDBSCAN's own choice.",
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
    }

    # ---------------------------------------------------------------- fit

    def fit(self, waveforms, *, params=None):
        params = params or {}
        L = int(params.get("resample_length", RESAMPLE_LENGTH))
        distance = str(params.get("distance", DEFAULT_DISTANCE))
        selection = str(params.get("cluster_selection_method", DEFAULT_SELECTION))
        if distance not in DISTANCES:
            raise ValueError(f"hdbscan distance must be one of {DISTANCES}; got {distance!r}.")
        if selection not in SELECTIONS:
            raise ValueError(f"hdbscan cluster_selection_method must be one of {SELECTIONS}; "
                             f"got {selection!r}.")
        cut = params.get("cut", DEFAULT_CUT)
        cut = DEFAULT_CUT if cut is None else float(cut)
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
        if fitted_pos.size:
            payload["D_fit"] = _distance_matrix(vectors[fitted_pos], distance)
        self._cluster(fit, cut)
        return fit

    def _cluster(self, fit, cut):
        """Run the density step on the stored fitted matrix at `cut`, then
        place the rows not fitted. Kept apart from `fit` so `assign` at a new
        cut re-selects clusters without recomputing a single distance."""
        p = fit.payload
        n = fit.n
        ok_rows = np.flatnonzero(p["positions"] >= 0)
        labels_ok = np.full(ok_rows.size, -1, dtype=np.int64)
        p.update(cut=cut, family_stability={}, unstable_families=[], family_of_label={})
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
                                         selection=s["cluster_selection_method"], cut=cut)
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
        p["unstable_families"] = [f"F-{p['family_of_label'][c]:02d}"
                                  for c, st in p["family_stability"].items()
                                  if st["unstable"] and c in p["family_of_label"]]
        p["fit_summary"] = self._summary(p, n, ok_rows.size)

    @staticmethod
    def _summary(p, n, n_ok):
        return {"rows": n, "screened_out": n - n_ok, "fitted": len(p["fitted_rows"]),
                "assigned": len(p["assigned_rows"]), "sample": p["sample"], "seed": p["seed"],
                "distance": p["distance"], "cut": p.get("cut"),
                "families": len(p.get("family_of_label", {})),
                "unstable_families": list(p.get("unstable_families", [])),
                "assigned_by": ("the family of the nearest fitted member, when within that "
                                "family's largest core distance; else not_in_a_dense_family")}

    # ------------------------------------------------------------- assign

    def assign(self, fit, *, cut=None):
        """A family id per row; `None` for noise (`not_in_a_dense_family`) and
        for a screened-out row. A `cut` other than the fitted one re-selects
        the clusters on the stored distances (no distance is recomputed)."""
        fit.omit_reasons.clear()
        fit.omit_reasons.update(fit.payload.get("screened_out", {}))
        if fit.n == 0:
            return []
        if cut is not None and float(cut) != fit.payload.get("cut"):
            self._cluster(fit, float(cut))
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
