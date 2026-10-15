"""
tree.py
=========
fixup-an: a grouping's tree, kept on disk.

A Ward grouping builds a tree — the two most alike shapes join first, then the
next, until everything is one trunk — and cuts it at a height to make the
families. Until fixup-an the engine kept only the merge heights and threw the
tree away, so seeing what another cut would do meant re-running the whole
regroup. This module keeps the tree: one `.npz` per fit, found again by a key,
so a cut can be previewed from it in milliseconds and a second apply with the
same members and settings reuses it rather than building a second linkage.

What the file holds (rule 4: bulk arrays never enter the database; the
`groupings` row holds only the path and the key):

    linkage       the scipy Ward linkage, (n - 1, 4) float64
    vectors       the resampled, z-normalised vectors the linkage was built on,
                  float64 — the distances (medoids, the `omit_d` rule) are
                  recomputed from them, deterministically, rather than stored
                  as an n^2 matrix
    refs          every item's ref, in input order (the fitted rows and the
                  ones the unit omitted before any fit, e.g. a single motif
                  outside every sequence)
    content_hashes, pre_omit    per item, beside the refs
    fit_rows      which items were fitted, in fit-row order
    leaf_order    the dendrogram's leaf order over the fitted rows
    meta_json     unit, basis, method, the fit params (the params minus the
                  assign-only ones) and the key

The key
-------
`tree_key` hashes (unit, basis, method, the fit params, and per item its ref,
its content hash, a digest of the waveform the fit is handed, and any pre-fit
omission). The prompt asked for the member content hashes; the waveform digest
is added because the bridge derives the engine's waveform from the stored
samples (decimated, in the stored unit), and a change in that derivation is a
different tree even when no content hash moved. The refs are in it because the
tree's rows are assigned back to refs: a re-import that renumbered members
under the same shapes must not hand the new ids someone else's rows.

Which params are "fit params": everything except `ASSIGN_ONLY_PARAMS` — the
cut, `omit_d`, `min_group`, `omit_small` — which are applied after the fit and
change no merge in the tree. The prompt said "params minus the cut"; leaving
the other three out too means a regroup that only changes the minimum family
size still reuses the tree, which is the same tree.

Why not `Working/training/shape.py`'s `ShapeTree`: that tree is over a window
pool's shape frame (pool rows, a sampled training set, nearest-centre
assignment of the rest) and is keyed on the pool; this one is over Library
members and is keyed on their identities. The save/load pattern (`.npz` plus
a key checked on load) is the same one.
"""

import hashlib
import json
import os
from dataclasses import dataclass, field

import numpy as np

# Where the bridge's project mode keeps the trees: the library's derived store,
# beside the window sets (`DATA/derived/window_sets`). The bridge's sandbox
# hands the engine a root inside its own runtime instead; nothing here writes
# unless a caller passes a root.
TREE_ROOT = os.path.join("DATA", "derived", "library", "grouping_trees")

# Applied after the fit; they change no merge in the tree.
ASSIGN_ONLY_PARAMS = ("cut", "omit_d", "min_group", "omit_small")

# Bumped if the file layout or the key's recipe changes.
TREE_VERSION = 1

DEFAULT_DENDROGRAM_LEAVES = 40


def fit_params(params):
    """The params minus the assign-only ones, as a plain sorted dict."""
    return {k: params[k] for k in sorted(params or {}) if k not in ASSIGN_ONLY_PARAMS}


def _digest(values):
    x = np.ascontiguousarray(np.asarray(values, dtype="<f8").ravel())
    return hashlib.blake2b(x.tobytes(), digest_size=12).hexdigest()


def _key_of(unit, basis, method, fparams, members):
    header = {"kind": "grouping_tree", "version": TREE_VERSION, "unit": unit, "basis": basis,
              "method": method, "fit_params": fparams, "members": members}
    h = hashlib.sha256(json.dumps(header, sort_keys=True, default=str).encode("utf-8"))
    return h.hexdigest()[:32]


def member_signature(items, basis):
    """Per item `[ref, content hash, waveform digest]` — what the key hashes.
    A pre-fit omission is added by `tree_key`, which knows the unit."""
    from Working.library.grouping import engine
    out = []
    for item in items:
        try:
            wave = engine._waveform(item, basis)
            dig = _digest(wave)
        except KeyError:
            dig = None
        h = item.get("content_hash")
        out.append([str(engine._ref(item)), None if h is None else str(h), dig])
    return out


def tree_key(items, *, unit, basis, method, params=None):
    """The key a fit of `items` under these settings is kept by (module docstring)."""
    from Working.library.grouping import engine
    members = member_signature(items, basis)
    for row, item in zip(members, items):
        row.append(engine.OMIT_NOT_IN_A_SEQUENCE if unit == "sequences" and item.get("sequence_id") is None else "")
    return _key_of(unit, basis, method, fit_params(dict(params or {})), members)


def path_for(root, key):
    return os.path.join(root, f"{key}.npz")


@dataclass
class GroupingTree:
    """One kept fit. `refs`, `content_hashes` and `pre_omit` are per item, in
    the order the engine was handed the items; `fit_rows` picks the fitted
    items, and the linkage's rows are those, in that order."""
    method: str
    unit: str
    basis: str
    fit_params: dict
    linkage: np.ndarray
    vectors: np.ndarray
    refs: np.ndarray
    content_hashes: np.ndarray
    pre_omit: np.ndarray
    fit_rows: np.ndarray
    leaf_order: np.ndarray
    member_digests: list = field(default_factory=list)
    key: str = ""

    # ------------------------------------------------------------ key
    def computed_key(self):
        members = [[str(r), (None if h == "" else str(h)), (None if d == "" else str(d)), str(p)]
                   for r, h, d, p in zip(self.refs.tolist(), self.content_hashes.tolist(),
                                         self.member_digests, self.pre_omit.tolist())]
        return _key_of(self.unit, self.basis, self.method, dict(self.fit_params), members)

    def refs_in_leaf_order(self):
        """The member refs as the dendrogram lays its leaves out."""
        return [self.refs[int(self.fit_rows[i])] for i in self.leaf_order]

    # ------------------------------------------------------------ disk
    def save(self, path):
        d = os.path.dirname(os.path.abspath(path))
        os.makedirs(d, exist_ok=True)
        meta = {"kind": "grouping_tree", "version": TREE_VERSION, "method": self.method, "unit": self.unit,
                "basis": self.basis, "fit_params": self.fit_params, "key": self.key,
                "ref_type": "int" if all(isinstance(r, (int, np.integer)) for r in self.refs.tolist()) else "str"}
        tmp = path + ".part.npz"
        np.savez_compressed(
            tmp, linkage=np.asarray(self.linkage, dtype=np.float64),
            vectors=np.asarray(self.vectors, dtype=np.float64),
            refs=np.asarray([str(r) for r in self.refs.tolist()], dtype=str),
            content_hashes=np.asarray(["" if h is None else str(h) for h in self.content_hashes.tolist()], dtype=str),
            digests=np.asarray(["" if g is None else str(g) for g in self.member_digests], dtype=str),
            pre_omit=np.asarray([str(p) for p in self.pre_omit.tolist()], dtype=str),
            fit_rows=np.asarray(self.fit_rows, dtype=np.int64),
            leaf_order=np.asarray(self.leaf_order, dtype=np.int64),
            meta_json=np.asarray(json.dumps(meta, sort_keys=True, default=str)))
        os.replace(tmp, path)
        return path

    @classmethod
    def load(cls, path):
        """Read a kept tree and check it against its own key: a file whose
        contents do not hash to the key it carries is refused, loudly."""
        with np.load(path, allow_pickle=False) as z:
            meta = json.loads(str(z["meta_json"]))
            refs = [str(r) for r in z["refs"].tolist()]
            if meta.get("ref_type") == "int":
                refs = [int(r) for r in refs]
            out = cls(method=meta["method"], unit=meta["unit"], basis=meta["basis"],
                      fit_params=dict(meta.get("fit_params") or {}),
                      linkage=np.asarray(z["linkage"], dtype=np.float64),
                      vectors=np.asarray(z["vectors"], dtype=np.float64),
                      refs=np.asarray(refs, dtype=object),
                      content_hashes=np.asarray([h if h != "" else None for h in z["content_hashes"].tolist()],
                                                dtype=object),
                      pre_omit=np.asarray(z["pre_omit"].tolist(), dtype=object),
                      fit_rows=np.asarray(z["fit_rows"], dtype=np.int64),
                      leaf_order=np.asarray(z["leaf_order"], dtype=np.int64),
                      member_digests=[g if g != "" else None for g in z["digests"].tolist()],
                      key=str(meta.get("key") or ""))
        if out.computed_key() != out.key:
            raise ValueError(f"the grouping tree at {path} does not match its own key ({out.key} on disk, "
                             f"{out.computed_key()} from its contents): it was changed after it was written. "
                             f"Regroup to build it again.")
        return out


def from_fit(fit, items, *, unit, basis, method, params, taking_part, pre_omitted):
    """A `GroupingTree` from a fresh fit whose payload carries a linkage."""
    from scipy.cluster.hierarchy import leaves_list
    members = member_signature(items, basis)
    Z = np.asarray(fit.payload["linkage"], dtype=np.float64)
    t = GroupingTree(
        method=method, unit=unit, basis=basis, fit_params=fit_params(params),
        linkage=Z, vectors=np.asarray(fit.payload["vectors"], dtype=np.float64),
        refs=np.asarray([_plain_ref(it) for it in items], dtype=object),
        content_hashes=np.asarray([m[1] for m in members], dtype=object),
        pre_omit=np.asarray([pre_omitted.get(i, "") for i in range(len(items))], dtype=object),
        fit_rows=np.asarray(taking_part, dtype=np.int64),
        leaf_order=np.asarray(leaves_list(Z), dtype=np.int64),
        member_digests=[m[2] for m in members])
    t.key = t.computed_key()
    return t


def _plain_ref(item):
    """The item's ref as the tree keeps it: an int stays an int, anything else is text."""
    from Working.library.grouping import engine
    r = engine._ref(item)
    return int(r) if isinstance(r, (int, np.integer)) and not isinstance(r, bool) else str(r)


def dendrogram(tree, leaves=DEFAULT_DENDROGRAM_LEAVES):
    """The kept tree truncated to its last `leaves` merges, as drawing
    coordinates — the payload `webui/client/src/analyse/views/TreePage.tsx`'s
    dendrogram draws (`Working/training/shape.py::dendrogram`'s shape), with
    EVERY merge height (high to low) so a dragged cut can land between any two."""
    from scipy.cluster.hierarchy import dendrogram as _dg
    Z = tree.linkage
    n = int(Z.shape[0]) + 1 if Z.size else len(tree.fit_rows)
    if n < 2 or not Z.size:
        return {"icoord": [], "dcoord": [], "leaves": [], "counts": [], "heights": [],
                "max_height": 0.0, "n_leaves": int(n)}
    p = int(max(2, min(int(leaves), n)))
    d = _dg(Z, truncate_mode="lastp", p=p, no_plot=True, count_sort=False, distance_sort=False)
    counts = []
    for lab in d["ivl"]:
        s = str(lab)
        counts.append(int(s.strip("()")) if s.startswith("(") else 1)
    return {"icoord": [[float(v) for v in r] for r in d["icoord"]],
            "dcoord": [[float(v) for v in r] for r in d["dcoord"]],
            "leaves": [str(v) for v in d["ivl"]], "counts": counts,
            "heights": [float(v) for v in np.sort(Z[:, 2])[::-1]],
            "max_height": float(Z[:, 2].max()), "n_leaves": int(n)}
