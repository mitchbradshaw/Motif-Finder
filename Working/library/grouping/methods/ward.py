"""
ward.py
=========
Ward linkage on resampled, z-normalised vectors under the scale-invariant
distance — the project default, named as such in PIPELINE_PRD.md Part 2
("Library entries at two scales"): *"Ward linkage on resampled, z-normalised
vectors under the scale-invariant distance, with roughness kept as a separate
quality filter rather than folded into the distance."* Roughness is therefore
NOT a term in this distance; if a quality filter is wanted it belongs in the
grouping's filters, not here.

The vectors are built with `Working.distances.resample_to_length` and
`z_normalize` — the same pair `scale_invariant_distance` uses, and the same
pair `LIBRARY_STORAGE.md` 2.2 hashes with — so the tree, the recorded edge
distance and the content hash all agree on what "the same shape" means. The
Euclidean distance between two such vectors IS `scale_invariant_distance` at
a fixed `n_samples`; `fit` computes it with `scipy.spatial.distance.pdist`
because the pairwise form is O(n^2) calls otherwise.

Two numbers this module normalises rather than inherits
-------------------------------------------------------
`scale_invariant_distance` is an unnormalised Euclidean norm, so its scale
grows as sqrt(resample length): at 256 samples an uncorrelated pair sits near
22.6, not near 0.7. Spec 9.10's pinned defaults ("omit motifs whose nearest
family is past d > 0.50") and the editor's `cut` slider (0.10-1.00) are only
meaningful on a [0, 1] scale. So every distance here is divided by
`2 * sqrt(resample_length)`, the largest a distance between two z-normalised
vectors of that length can be (an exactly anti-correlated pair). Identical
shapes are 0, anti-correlated shapes are 1, and an uncorrelated pair is
1/sqrt(2). `fit.payload["distance_scale"]` records the divisor so a reader can
recover the raw distance, and the scale is part of the fit rather than a
hidden constant because changing it would silently move every saved cut.
"""

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import pdist, squareform

from Working.distances import resample_to_length, z_normalize
from Working.library.grouping.methods import FitResult, register

# Resample length. Matched deliberately to `LIBRARY_STORAGE.md` 2.2's
# HASH_LENGTH: the hash and the default distance must agree that a pair at
# distance 0 is one shape, and they only do so at the same length.
RESAMPLE_LENGTH = 256

# Spec 9.10, Settings > Library groupings.
DEFAULT_CUT = 0.42          # the editor's default cut on the Ward tree
DEFAULT_OMIT_D = 0.50       # "omit motifs whose nearest family is past d > 0.50"
DEFAULT_MIN_GROUP = 10      # "omit groups under 10 members"


# --------------------------------------------------------------------------
# The three pieces `fit` is made of, public so a caller with more items than a
# square distance matrix can hold (fixup-ag: RQ1's window pool, 20,000 windows)
# uses THIS method rather than a second one. `fit` is exactly these three plus
# the square matrix the Library's medoids read.
# --------------------------------------------------------------------------

def shape_vectors(waveforms, n_samples=RESAMPLE_LENGTH):
    """One resampled, z-normalised vector per waveform — `(n, n_samples)`."""
    return np.vstack([z_normalize(resample_to_length(w, n_samples)) for w in waveforms])


def distance_scale(n_samples):
    """The divisor that puts every distance on [0, 1] (module docstring)."""
    return 2.0 * np.sqrt(n_samples)


def condensed_distances(vectors):
    """The condensed scale-invariant distances between vectors, on [0, 1]. The
    division is in place: at 20,000 items the condensed array alone is 1.6 GB."""
    vectors = np.asarray(vectors, dtype=float)
    condensed = pdist(vectors, metric="euclidean")
    condensed /= distance_scale(vectors.shape[1])
    return condensed


def ward_linkage(condensed):
    """The Ward tree over condensed scale-invariant distances."""
    return linkage(condensed, method="ward")


class WardMethod:
    """Ward linkage over the scale-invariant distance, cut at a distance."""

    name = "ward"
    label = "Ward linkage"
    description = ("Ward linkage on resampled, z-normalised vectors under the "
                   "scale-invariant distance, cut at a distance.")
    applies_to = ("shape-distance", "sequence-similarity")
    # fixup-an: the fit is a tree the engine can keep on disk (`grouping/tree.py`)
    # and rebuild from it with `fit_from_tree`, so a cut is previewed without refitting
    builds_tree = True

    params = {
        "cut": {
            "type": "float", "default": DEFAULT_CUT, "label": "cut",
            "help": "the distance to cut the tree at; the merge-height "
                    "histogram shows where the tree actually merges.",
        },
        "min_group": {
            "type": "int", "default": DEFAULT_MIN_GROUP, "label": "minimum group",
            "help": "groups under this many members are omitted and flagged "
                    "(spec 9.10). The engine applies it, so it is one rule for "
                    "every method rather than one per method.",
        },
        "omit_d": {
            "type": "float", "default": DEFAULT_OMIT_D,
            "label": "nearest family past",
            "help": "a motif whose nearest family medoid is further than this "
                    "fits no family: omitted and flagged as past_cut (spec 9.10).",
        },
        "resample_length": {
            "type": "int", "default": RESAMPLE_LENGTH, "label": "resample length",
            "help": "samples every span is resampled to before z-normalising. "
                    "Changing it changes every distance in the tree.",
        },
    }

    # ---------------------------------------------------------------- fit

    def fit(self, waveforms, *, params=None):
        """Build the tree. `waveforms` is one waveform per item, of any
        lengths — resampling to a common length is what makes spans of
        different duration comparable at all."""
        params = params or {}
        n_samples = int(params.get("resample_length", RESAMPLE_LENGTH))
        waveforms = list(waveforms)
        n = len(waveforms)
        scale = distance_scale(n_samples)

        payload = {"resample_length": n_samples, "distance_scale": float(scale)}

        if n == 0:
            return FitResult(method=self.name, n=0, payload=payload)

        vectors = shape_vectors(waveforms, n_samples)
        payload["vectors"] = vectors

        if n == 1:
            return FitResult(method=self.name, n=1, distances=np.zeros((1, 1)),
                             payload=payload)

        condensed = condensed_distances(vectors)
        tree = ward_linkage(condensed)
        payload["linkage"] = tree
        return FitResult(
            method=self.name, n=n,
            distances=squareform(condensed),
            heights=sorted(float(h) for h in tree[:, 2]),
            payload=payload,
        )

    def fit_from_tree(self, tree):
        """The `FitResult` `fit` would have returned, rebuilt from a kept tree
        (`Working/library/grouping/tree.py`) without building a linkage: the
        stored linkage is the tree, and the distances are recomputed from the
        stored vectors exactly as `fit` computes them — so medoids and the
        `omit_d` rule read the same numbers."""
        vectors = np.asarray(tree.vectors, dtype=float)
        Z = np.asarray(tree.linkage, dtype=float)
        n = int(vectors.shape[0])
        n_samples = int(vectors.shape[1]) if vectors.ndim == 2 else RESAMPLE_LENGTH
        payload = {"resample_length": n_samples, "distance_scale": float(distance_scale(n_samples)),
                   "vectors": vectors, "linkage": Z}
        if Z.shape[0] != n - 1:
            raise ValueError(f"a kept tree of {n} vectors needs {n - 1} merges; it has {Z.shape[0]}")
        return FitResult(method=self.name, n=n, distances=squareform(condensed_distances(vectors)),
                         heights=sorted(float(h) for h in Z[:, 2]), payload=payload)

    # ------------------------------------------------------------- assign

    def assign(self, fit, *, cut=None, omit_d=None):
        """A family id per row, `None` where the row fits no family.

        `omit_d` defaults to None — *no* omission — rather than to spec
        9.10's 0.50, because a direct caller asking only for a cut should get
        the tree's own answer. The engine passes the 0.50 from `params`; that
        way the pinned default is applied in exactly one place.

        A row keeps the family the tree gave it, but is tested against the
        distance to its *nearest* family medoid. The two can differ — Ward
        merges on within-cluster variance, not on medoid proximity — and the
        spec's rule is worded about the nearest family, so that is what is
        measured.

        A row is never measured against itself. A far outlier lands in a
        family of its own and is therefore its own medoid at distance 0,
        which would make the omit rule unable to omit exactly the motif it
        exists to omit; so a family is measured from the medoid of its OTHER
        members, and a family that has none (the outlier alone) is not a
        family this row can belong to.
        """
        fit.omit_reasons.clear()
        if fit.n == 0:
            return []
        cut = DEFAULT_CUT if cut is None else float(cut)

        if fit.n == 1:
            fit.family_labels = {1: "F-01"}
            return [1]

        # fixup-an fix round: vectorised. The cut is now previewed interactively from a kept tree, and the
        # per-row x per-family Python loop this replaces took 3-6 s at low cuts on 3,000 members. The rule
        # and its output are unchanged (tests/test_library_grouping_tree.py pins it against that loop).
        lab = np.asarray(fcluster(fit.payload["linkage"], t=cut, criterion="distance"), dtype=np.int64)
        labels = [int(f) for f in lab]
        families = sorted(set(labels))
        order = np.argsort(lab, kind="stable")              # rows grouped by family, input order kept
        bounds = np.searchsorted(lab[order], families + [families[-1] + 1])
        members = {f: order[bounds[k]:bounds[k + 1]] for k, f in enumerate(families)}
        D = fit.distances
        medoids, runners_up = {}, {}
        for f in families:
            idx = members[f]
            medoids[f] = self._medoid_row(D, idx)
            rest = idx[idx != medoids[f]]
            # the medoid of each family's other members, for the row that is the family's own medoid;
            # None where the family is that row alone
            runners_up[f] = self._medoid_row(D, rest) if rest.size else None

        out = list(labels)
        if omit_d is not None:
            anchor = np.asarray([medoids[f] for f in families], dtype=np.int64)
            dist = np.array(D[:, anchor], dtype=float)                 # (n, families)
            for col, f in enumerate(families):
                own = medoids[f]                                       # the medoid row is measured from the runner-up
                dist[own, col] = D[own, runners_up[f]] if runners_up[f] is not None else np.inf
            nearest = dist.min(axis=1) if dist.shape[1] else np.full(fit.n, np.inf)
            for i in np.flatnonzero(nearest > float(omit_d)):
                fit.omit_reasons[int(i)] = "past_cut"
                out[int(i)] = None

        fit.family_labels = {f: f"F-{k + 1:02d}" for k, f in enumerate(families)}
        return out

    @staticmethod
    def _medoid_row(D, idx):
        """`medoid`'s choice, vectorised: the row of `idx` with the smallest summed distance to the others
        (ties to the first, as `min` does)."""
        idx = np.asarray(idx, dtype=np.int64)
        if idx.size == 1:
            return int(idx[0])
        sums = np.array([D[i, idx].sum() for i in idx]) if idx.size <= 64 else D[np.ix_(idx, idx)].sum(axis=1)
        return int(idx[int(np.argmin(sums))])

    # ----------------------------------------------------------- estimate

    def estimate(self, n, params, basis=None):
        """The engine's original formula, unchanged: n^2/2 pairs at
        `SECONDS_PER_PAIR` (the sequence basis's own rate) plus a per-item cost."""
        from Working.library.grouping.engine import _formula_seconds
        return _formula_seconds(n, basis or "shape-distance")

    # ------------------------------------------------------------- medoid

    def medoid(self, fit, indices):
        """`(row index, mean distance to the rest)` for the member with the
        smallest summed distance to the other members — the family's computed
        centre, which the Atlas and Family pages draw beside the human-chosen
        exemplar with the distance between them."""
        indices = list(indices)
        if not indices:
            raise ValueError("A family with no members has no medoid.")
        if len(indices) == 1:
            return indices[0], 0.0
        # fix round: the same choice as `_medoid_row` (and so as `assign`), one sub-matrix for a big family
        best = self._medoid_row(fit.distances, indices)
        return best, float(fit.distances[best, indices].sum()) / (len(indices) - 1)

    # ------------------------------------------------------ merge_heights

    def merge_heights(self, fit):
        """The tree's merge heights, sorted — what the grouping editor draws
        so the researcher can see where the tree actually merges before
        choosing a cut. Empty for fewer than two items: there is no tree."""
        return list(fit.heights)


register(WardMethod())
