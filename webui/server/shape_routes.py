"""fixup-ag: the bridge side of the RQ1 version-2 chain — *Window pool* → *Trace
shape* → *Shape clustering* (ticket `docs/prompts/fixup/AG-…`).

* ``GET /api/windowsets/library`` — what the *Window pool* block's page lists: the
  library of EVERY saved window set (unlabelled sets, pools, the baseline's
  labelled set), each with its kind, recording(s), scale and counts, from
  ``Working.training.pool.list_sets`` — nothing assumes six. The held-out
  recording is never listed.

The core does the work (``Working.training.pool``, ``Working.training.shape``);
these routes hand it a connection and hand its answers back.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Request

from . import corpus
from .runtime import HELD_OUT_FILE

router = APIRouter()


def _conn(request: Request):
    return corpus.connect(request.app.state.rt.db_path)


def _per_recording(c, row) -> dict:
    out: dict[str, int] = {}
    for sf, n in c.execute("SELECT r.source_file, SUM(w.n_windows) FROM window_set_channels w JOIN recordings r "
                           "ON r.id = w.recording_id WHERE w.window_set_id = ? GROUP BY r.source_file", (row["id"],)):
        out[str(sf)] = int(n or 0)
    if not out:
        for sf, n in c.execute("SELECT r.source_file, COUNT(*) FROM window_set_members m JOIN recordings r "
                               "ON r.id = m.recording_id WHERE m.window_set_id = ? GROUP BY r.source_file", (row["id"],)):
            out[str(sf)] = int(n or 0)
    return out


@router.get("/api/windowsets/library")
def windowset_library(request: Request):
    """Every saved window set, as the Window pool block lists them."""
    from Adapters.registry import discover_adapters, get_adapter
    from Working.training import pool as tpool
    discover_adapters()
    spec = get_adapter("preprocessing.window_pool")
    c = _conn(request)
    try:
        out = []
        for s in tpool.list_sets(c):
            if HELD_OUT_FILE in (s.get("source_files") or []):
                continue
            row = c.execute("SELECT * FROM window_sets WHERE id = ?", (s["id"],)).fetchone()
            try:
                cov = json.loads(row["coverage_json"] or "{}") or {}
            except (TypeError, ValueError):
                cov = {}
            n_ch = c.execute("SELECT COUNT(*) FROM window_set_channels WHERE window_set_id = ?", (s["id"],)).fetchone()[0] \
                or c.execute("SELECT COUNT(*) FROM window_set_members WHERE window_set_id = ?", (s["id"],)).fetchone()[0] \
                or (1 if row["recording_id"] is not None else 0)
            out.append({**{k: s[k] for k in ("id", "name", "version", "kind", "scale_min", "scales_min", "n_windows",
                                             "source_files", "key", "created_at")},
                        "n_channels": int(n_ch), "per_recording": _per_recording(c, row),
                        "counts": cov.get("counts"), "hold_out_pack": cov.get("hold_out_pack"),
                        "labels_source": row["labels_source"], "rule": cov.get("rule"),
                        "dropped": cov.get("dropped")})
    finally:
        c.close()
    defaults = {p.name: p.default for p in spec.params}
    return {"sets": out, "defaults": defaults, "rules": tpool.RULES, "packs": {k: [c + 1 for c in v] for k, v in tpool.PACKS.items()},
            "note": ("tick the sets to combine; the first listed wins a duplicate or an overlap. Library › Window sets "
                     "› New window set makes more.")}


# ── seam (ii): the dendrogram page reads the KEPT tree by its key ──────────
#
# Moving the cut never rebuilds the tree: the page asks for the clusters at k (a
# fast assignment over the kept tree and the shape vectors), and for one cluster's
# medoid, members, mean shape and mix. The tree and its vectors are found by key,
# under the paths the sandbox redirects (`catalogue_shape_cluster.RESULTS_DIR`,
# `preprocessing_trace_shape.RESULTS_DIR`), never by a path from the browser.

import os  # noqa: E402
import re  # noqa: E402
import threading  # noqa: E402
from collections import OrderedDict  # noqa: E402

from fastapi import HTTPException  # noqa: E402

_KEY = re.compile(r"^[A-Za-z0-9_]{6,48}$")
_LOADED: "OrderedDict[str, tuple]" = OrderedDict()
_LOCK = threading.Lock()
_HELD = 3


def tree_and_shapes(key: str):
    """`(tree, shapes)` for a kept tree, by key (the three most recent held in memory)."""
    import Adapters.catalogue_shape_cluster as csc
    import Adapters.preprocessing_trace_shape as tsh
    from Working.training import shape as tshape
    if not _KEY.match(key or ""):
        raise HTTPException(422, f"{key!r} is not a tree key")
    d = os.path.join(csc.RESULTS_DIR, key)
    with _LOCK:
        if key in _LOADED:
            _LOADED.move_to_end(key)
            return _LOADED[key]
    if not os.path.isfile(os.path.join(d, "tree.npz")):
        raise HTTPException(404, f"no kept tree {key} under {csc.RESULTS_DIR}: run the Shape clustering block")
    tree = tshape.ShapeTree.load(d)
    sk = tree.meta.get("shape_key")
    sp = os.path.join(tsh.RESULTS_DIR, str(sk), "shapes.npz")
    if not sk or not os.path.isfile(sp):
        raise HTTPException(404, f"the tree {key} was built on shape vectors {sk} that are not on disk: re-run the Trace shape step")
    shapes = tshape.ShapeSet.load(sp)
    tree = tshape.load_tree_for(d, shapes)
    with _LOCK:
        _LOADED[key] = (tree, shapes)
        while len(_LOADED) > _HELD:
            _LOADED.popitem(last=False)
    return tree, shapes


def _labels(tree, shapes, k: int):
    from Working.training import shape as tshape
    try:
        return tshape.labels_at(tree, shapes, int(k))
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/api/shape/trees/{key}/cut")
def shape_cut(key: str, k: int):
    """The clusters at k: a line each (count, speck, scale and recording mix, median raw range)."""
    from Working.training import shape as tshape
    tree, shapes = tree_and_shapes(key)
    lab = _labels(tree, shapes, k)
    summ = tshape.clusters_summary(tree, shapes, lab)
    return {"key": key, "k": int(lab.k), "cut_height": tshape.cut_height(tree, lab.k), "clusters": summ["clusters"],
            "small_below": summ["small_below"], "n_clustered": int(lab.n_clustered), "n_assigned": int(lab.n_assigned),
            "n_train": int(len(tree.train_rows))}


def _raw_mv(conn, w, n=256):
    """A window's raw trace in mV, resampled to n points for drawing only (the shape was the Library's vector)."""
    from Working.distances import resample_to_length
    from Working.units import to_mv_factor
    row = conn.execute("SELECT npy_path, units FROM recordings WHERE id = ?", (int(w["recording_id"]),)).fetchone()
    if row is None:
        return None, None
    import numpy as np
    x = np.load(row[0], mmap_mode="r")
    seg = np.asarray(x[int(w["start"]):int(w["start"]) + int(w["length"])], dtype=float)
    f = to_mv_factor(row[1])
    v = resample_to_length(seg, n) * (f if f is not None else 1.0)
    return [round(float(a), 5) for a in v], ("mV" if f is not None else None)


@router.get("/api/shape/trees/{key}/cluster")
def shape_cluster_detail(request: Request, key: str, k: int, c: int, seed: int = 0, n: int = 12):
    """One cluster at k: its medoid (a real window), `n` seeded members, the mean shape and its spread, the count,
    the scale and recording mix, the raw amplitude range, where the event sits — and each window's raw trace in
    mV, so the amplitude the normalisation threw away is on the page."""
    from Working.training import shape as tshape
    tree, shapes = tree_and_shapes(key)
    lab = _labels(tree, shapes, k)
    try:
        d = tshape.cluster_detail(tree, shapes, lab, int(c), n_members=max(1, min(48, int(n))), seed=int(seed))
    except ValueError as e:
        raise HTTPException(404, str(e))
    con = _conn(request)
    try:
        for w in [d["medoid"], *d["members"]]:
            w["raw_mv"], w["unit"] = _raw_mv(con, w)
    finally:
        con.close()
    return {"key": key, **d}
