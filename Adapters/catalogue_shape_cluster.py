"""
catalogue_shape_cluster.py
==========================
fixup-ag: the *Shape clustering* block — WindowSet → Grouping (ticket
`docs/prompts/fixup/AG-…` "What to build" 3–5).

Why a sibling of `catalogue.cluster`, not a basis on it
-------------------------------------------------------
`catalogue.cluster` is "a window set's FEATURE MATRIX → k flat clusters" through
`Working.Catalogue.dendrogram`: it z-scores columns, clusters every window and
keeps no tree. This block's contract differs on every one of those: it reads the
SHAPE VECTORS a *Trace shape* step wrote (by path, rule 4), clusters TRAINING
windows only, on a seeded sample, with the Library's Ward
(`Working.library.grouping.methods.ward`), assigns every other training window to
the nearest centre, and KEEPS the tree, so the dendrogram, any later cut and the
proposal per k read one artifact. A basis switch on `catalogue.cluster` would put
an `if` on each of those paths, and run 79's frozen cut was made by that block.

What it does
------------
* the tree: `Working.training.shape.cluster_shapes` on `sample` training windows
  (default 20,000), stratified by recording × scale, seeded; kept under
  `RESULTS_DIR/<key>/` and RE-USED when the same windows, sample and seed come
  again (a new cut does not rebuild it);
* `tree_path`: a tree made elsewhere (an HPC Ward over every training window,
  written by `ShapeTree.save`) is loaded in place of the local one through the
  same reader, refused if it was built on other windows;
* the cut `k`: 0 = the proposal by the baseline's written rule (the best
  silhouette among cuts with at least two non-speck clusters);
* the labels: 1..k for every training window (sample and assigned), -1 for
  validation, test and exam windows — they never touch the tree; they are
  assigned only by running the trained model on them;
* `mapping`: the researcher's names and interesting / not per cluster, as JSON
  (`{"1": {"name": "...", "class": "interesting"}}`), carried in the recipe so the
  template and Models › Launch read the same mapping.
"""

import json
import os
import time

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register

#: where trees are kept; the bridge's sandbox redirects it (runtime.py)
RESULTS_DIR = os.path.join("DATA", "derived", "shape_trees")

CLASSES = ("interesting", "not_interesting")


def parse_mapping(text):
    """The researcher's mapping, from the param: `{"k": <the cut it was made at>, "clusters": {"<cluster>":
    {"name": str, "class": "interesting" | "not_interesting" | None}}}`. A bare `{"<cluster>": {...}}` is read
    as made at no particular cut. Empty -> no mapping yet."""
    text = str(text or "").strip()
    if not text:
        return {"k": None, "clusters": {}}
    try:
        raw = json.loads(text)
    except ValueError as e:
        raise ValueError(f"the mapping is not JSON ({e}); it maps each cluster to a name and interesting / not")
    raw = raw or {}
    k = raw.get("k") if isinstance(raw, dict) and "clusters" in raw else None
    body = raw.get("clusters") if isinstance(raw, dict) and "clusters" in raw else raw
    out = {}
    for key, v in (body or {}).items():
        v = v if isinstance(v, dict) else {"class": v}
        cls = v.get("class") or None
        if cls is not None and cls not in CLASSES:
            raise ValueError(f"cluster {key}: {cls!r} is not one of {', '.join(CLASSES)}")
        out[str(int(key))] = {"name": str(v.get("name") or ""), "class": cls}
    return {"k": None if k is None else int(k), "clusters": out}


def mapping_state(mapping, k):
    """Whether the mapping covers the cut: `complete` (every cluster at k is interesting / not, made at k),
    `stale` (made at another cut), `partial` or `none`."""
    if not mapping["clusters"]:
        return "none"
    if mapping["k"] is not None and int(mapping["k"]) != int(k):
        return "stale"
    have = {c for c, v in mapping["clusters"].items() if v.get("class")}
    return "complete" if have >= {str(c) for c in range(1, int(k) + 1)} else "partial"


def _load_shapes(value):
    from Working.training import shape as tshape
    if value is None or value.features is None or tshape.SHAPE_META["shape_file"] not in value.features.columns:
        raise ValueError("Shape clustering needs a Trace shape step before it: it clusters the shape vectors that "
                         "step wrote, not a feature matrix")
    path = str(value.features[tshape.SHAPE_META["shape_file"]].iloc[0]) if len(value.features) else None
    if not path or not os.path.isfile(path):
        raise ValueError(f"the shape vectors are not on disk at {path}: re-run the Trace shape step")
    shapes = tshape.ShapeSet.load(path)
    if len(shapes.frame) != value.n_windows:
        raise ValueError(f"the shape vectors at {path} hold {len(shapes.frame)} windows, the step before passed "
                         f"{value.n_windows}: re-run the chain")
    return shapes, path


def tree_for(shapes, sample, seed, tree_path=""):
    """`(tree, dir, reused, loaded_from)` — load a tree made elsewhere, re-use the kept one, or build it."""
    from Working.training import shape as tshape
    if str(tree_path or "").strip():
        src = str(tree_path).strip()
        tree = tshape.load_tree_for(src, shapes)
        # kept beside the local trees under its own key, so the dendrogram page and any later cut read it by key
        import hashlib
        key = "ext_" + hashlib.sha256(f"{os.path.abspath(src)}|{shapes.key}".encode("utf-8")).hexdigest()[:12]
        d = os.path.join(RESULTS_DIR, key)
        if not os.path.isfile(os.path.join(d, "tree.npz")):
            tree.meta = {**tree.meta, "loaded_from": os.path.abspath(src)}
            tree.save(d)
        return tree, d, True, src
    key = tshape.tree_key(shapes, None if int(sample) <= 0 else int(sample), int(seed))
    d = os.path.join(RESULTS_DIR, key)
    if os.path.isfile(os.path.join(d, "tree.npz")):
        try:
            return tshape.load_tree_for(d, shapes), d, True, None
        except ValueError:
            pass
    tree = tshape.cluster_shapes(shapes, sample=None if int(sample) <= 0 else int(sample), seed=int(seed))
    tree.save(d)
    return tree, d, False, None


def _run(x, t, fs, sample=20000, seed=0, k=0, tree_path="", mapping="", value=None, conn=None, recording=None):
    from Working.training import shape as tshape
    t0 = time.time()
    shapes, shape_file = _load_shapes(value)
    tree, d, reused, loaded_from = tree_for(shapes, sample, seed, tree_path)
    prop, prop_cached = tshape.propose_cached(tree, shapes, d)
    k_used = int(k) if int(k) > 0 else int(prop["suggested_k"] or 2)
    lab = tshape.labels_at(tree, shapes, k_used)
    mp = parse_mapping(mapping)
    # seam (iii): once a run on this pool has a test score, its cut and mapping are frozen — here as in Launch
    pool_key = str(shapes.frame["pool_key"].iloc[0]) if "pool_key" in shapes.frame.columns and len(shapes.frame) else None
    frozen = None
    if conn is not None and pool_key:
        from Working.training import shape_forest
        shape_forest.check_frozen(conn, pool_key, lab.k, mp if mapping_state(mp, lab.k) == "complete" else None)
        frozen = shape_forest.frozen_for(conn, pool_key)
    roles = shapes.frame["role"].to_numpy()
    not_clustered = {r: int((roles == r).sum()) for r in ("validation", "test", "exam")}
    summ = tshape.clusters_summary(tree, shapes, lab)
    meta = {
        "linkage": "ward",
        "tree": {
            "key": os.path.basename(d.rstrip("/\\")), "dir": os.path.abspath(d), "reused": bool(reused),
            "loaded_from": loaded_from, "shape_file": shape_file, "shape_key": shapes.key,
            "propose_cached": bool(prop_cached), "pool_key": pool_key, "frozen": frozen, "align": shapes.meta.get("align", "grid"),
            "detrend": shapes.meta.get("detrend", "off"),
            "k": int(lab.k), "k_param": int(k), "suggested_k": prop["suggested_k"], "cut_height": tshape.cut_height(tree, lab.k),
            "n_train": int(len(tree.train_rows)), "n_clustered": int(lab.n_clustered), "n_assigned": int(lab.n_assigned),
            "not_clustered": not_clustered, "sample": tree.meta.get("sample"), "seed": tree.meta.get("seed"),
            "stratified_by": tree.meta.get("stratified_by"), "ward_seconds": tree.meta.get("ward_seconds"),
            "peak_rss_mb": tree.meta.get("peak_rss_mb"), "method_text": tree.meta.get("method_text"),
            "library_method": tree.meta.get("library_method"), "resample_length": tree.meta.get("resample_length"),
            "dendrogram": tshape.dendrogram(tree), "propose": prop, "clusters": summ["clusters"],
            "small_below": summ["small_below"], "mapping": mp, "mapping_state": mapping_state(mp, lab.k),
            "seconds": round(time.time() - t0, 2),
            "rule": ("Ward (the Library's method) on a seeded sample of training windows, stratified by recording × "
                     "scale; every other training window assigned to the nearest cluster centre; validation, test "
                     "and exam windows are not clustered (-1) — the trained model assigns them"),
        },
    }
    from Working.types import Grouping
    return AdapterResult(output_kind="grouping", value=Grouping(labels=lab.labels), meta=meta)


def _estimate(x, t, fs, sample=20000, **params):
    """Ward's distances are quadratic in the sample: about 90 s at 20,000 windows on this machine (measured
    by fixup-ag), plus the proposal; a kept tree is re-used and costs seconds."""
    n = max(2, int(sample) if int(sample) > 0 else 20000)
    return 30.0 + 90.0 * (n / 20000.0) ** 2


def _persist(conn, run_id, config_hash, recording, span_start, span_end, params, result):
    """The kept tree is the run's artifact (rule 4: on disk, the row holds the path)."""
    tree = (result.meta or {}).get("tree") or {}
    p = os.path.join(tree.get("dir") or "", "tree.npz")
    return ("other", p) if os.path.isfile(p) else None


SPEC = register(AdapterSpec(
    name="catalogue.shape_cluster",
    display_name="Shape clustering (WindowSet -> Grouping, Ward on trace shape)",
    stage="catalogue",
    category="cluster",
    page_name="Shape clustering",
    params=[
        ParamSpec("sample", int, 20000, "Training windows the Ward tree is built on (seeded, stratified by "
                  "recording × scale); every other training window goes to the nearest cluster centre. 0 = every "
                  "training window (an HPC-sized tree).", min=0),
        ParamSpec("seed", int, 0, "The sample's seed.", min=0),
        ParamSpec("k", int, 0, "Clusters at the cut — move the cut on the dendrogram. 0 = the proposal (best "
                  "silhouette among cuts with at least two non-speck clusters).", min=0),
        ParamSpec("tree_path", str, "", "A tree made elsewhere (a directory holding tree.npz + manifest.json, e.g. "
                  "an HPC Ward over every training window), loaded in place of the local one."),
        ParamSpec("mapping", str, "", "Each cluster's name and interesting / not at a cut, as JSON "
                  '({"k": 6, "clusters": {"1": {"name": "...", "class": "interesting"}}}) — set in the mapping table '
                  "on this block's page."),
    ],
    run=_run,
    input_kind="windowset",
    output_kind="grouping",
    estimate=_estimate,
    persist=_persist,
    description=("Ward linkage on trace shape (the Library's method) over a seeded sample of the pool's training "
                 "windows, the rest assigned to the nearest centre, the tree kept; validation, test and exam "
                 "windows are not clustered."),
))
