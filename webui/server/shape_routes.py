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


# ── seam (ii) continued: one card per cluster at the cut (the researcher, 2026-10-06) ──

@router.get("/api/shape/trees/{key}/cards")
def shape_cards(key: str, k: int, seed: int = 0, n: int = 4):
    """Every cluster at k — one card each, medoid and a few members — from the kept tree, without a re-run."""
    from Working.training import shape as tshape
    tree, shapes = tree_and_shapes(key)
    if not 1 <= int(k) <= max(1, len(tree.leaf_rows)) or int(k) > 400:
        raise HTTPException(422, f"k = {k}: the tree has {len(tree.leaf_rows)} leaves (at most 400 cards are drawn)")
    lab = _labels(tree, shapes, k)
    n = max(1, min(12, int(n)))
    return {"key": key, "k": int(lab.k), "n_members": n, "cut_height": tshape.cut_height(tree, lab.k),
            "cards": tshape.cluster_cards(tree, shapes, lab, n_members=n, seed=int(seed)),
            "note": ("every training window at this cut (the sampled ones from the tree, the rest by the nearest "
                     "centre), read from the kept tree; the block's recorded Grouping changes only when the chain "
                     "is re-run with this k")}


# ── seam (iii): Models › Launch, arm B.2 ───────────────────────────────────

from pydantic import BaseModel  # noqa: E402


def _template(c, template_id):
    from . import templates as T
    try:
        return T.get(c, int(template_id))
    except KeyError as e:
        raise HTTPException(404, str(e))


def _pool_row(c, pool_id):
    from Working.training import pool as tpool
    try:
        row, pool = tpool.load_pool(c, int(pool_id))
    except ValueError as e:
        raise HTTPException(404, str(e))
    return row, pool


def _pool_view(c, row, pool):
    from Working.training import pool as tpool
    t = pool.table
    names = corpus.dataset_names(c)
    recs = []
    for sf, g in t.groupby("source_file", sort=True):
        n_ch = int(c.execute("SELECT COUNT(*) FROM recordings WHERE source_file = ?", (sf,)).fetchone()[0])
        chans = []
        for ch, gc in g.groupby("channel", sort=True):
            role = "exam" if (gc["role"] == "exam").all() else "train"
            chans.append({"channel": int(ch), "name": corpus.channel_name(sf, int(ch), n_ch), "role": role,
                          "n": int(len(gc)), "by_role": {r: int((gc["role"] == r).sum()) for r in tpool.ROLES}})
        recs.append({"source_file": sf, "name": names.get(sf, sf), "channels": chans})
    counts = pool.meta.get("counts") or tpool.pool_counts(pool)
    plan = pool.meta.get("plan") or {}
    return {"id": int(row["id"]), "name": row["name"], "version": int(row["version"] or 1), "key": pool.key,
            "n_windows": int(len(t)), "by": counts["by"], "by_role": counts["by_role"], "recordings": recs,
            "plan": {k: plan.get(k) for k in ("n_blocks", "test_frac", "validation_frac", "gap_s", "hold_out_pack")},
            "rule": pool.meta.get("rule")}


def _b2_checks(c, recipe_or_problem, pool_key, k, mapping):
    from Working.training import shape_forest as sf
    checks = []
    problem = sf.mapping_problem(k, mapping)
    checks.append({"name": "every cluster at the cut is mapped", "level": "error" if problem else "pass",
                   "detail": problem or f"k = {k}; every cluster has an interesting / not class"})
    try:
        sf.check_frozen(c, pool_key, k, mapping)
        fz = sf.frozen_for(c, pool_key)
        checks.append({"name": "cut and mapping not changed after a test score", "level": "pass",
                       "detail": (f"run {fz['run_id']} has a test score at this cut and mapping" if fz else
                                  "no run on this pool has a test score yet")})
    except Exception as e:      # CutFrozen
        checks.append({"name": "cut and mapping not changed after a test score", "level": "error", "detail": str(e)})
    checks.append({"name": "the model's inputs", "level": "pass", "detail": sf.INPUTS_RULE})
    return checks


@router.get("/api/models/b2/setup")
def b2_setup(request: Request, template: int, pool: int):
    """What Launch shows for arm B.2: the template, the pool as the sources, the cut and the mapping read-only."""
    from Working.training import shape_forest as sf
    c = _conn(request)
    try:
        t = _template(c, template)
        row, p = _pool_row(c, pool)
        try:
            shp, clu, mapping = sf.chain_settings(t["steps"])
        except ValueError as e:
            raise HTTPException(422, str(e))
        from Adapters.catalogue_shape_cluster import mapping_state
        k = int(clu["k"])
        return {"template": {"id": int(t["id"]), "name": t["name"], "steps": t["steps"]},
                "pool": _pool_view(c, row, p),
                "arm": {"name": "B.2", "label": sf.ARM_LABEL, "k": k, "mapping": mapping, "read_only": True,
                        "mapping_state": mapping_state(mapping, k) if k else "none",
                        "where": "Analyse › Chain › Shape clustering (the cut and the mapping table)"},
                "shape": {k2: shp[k2] for k2 in ("align", "detrend", "resample_length", "noise_floor")},
                "cluster": {"sample": int(clu["sample"]), "seed": int(clu["seed"])},
                "inputs": {"features": "raw samples at the re-cut bounds", "stages": list(sf.DEFAULT_STAGES),
                           "rule": sf.INPUTS_RULE},
                "frozen": sf.frozen_for(c, p.key), "checks": _b2_checks(c, None, p.key, k, mapping),
                "defaults": {"n_estimators": 300, "class_weight": "balanced", "random_state": 42},
                "runs": [r for r in sf.list_runs(c) if (r.get("pool") or {}).get("key") == p.key],
                "slurm": ("not offered for B.2: the forest trains locally in minutes; the HPC scripts (a full-pool "
                          "Ward, the CNN arm) are AI's")}
    finally:
        c.close()


class B2TrainBody(BaseModel):
    template: int
    pool: int
    n_estimators: int = 300
    class_weight: str = "balanced"
    random_state: int = 42


@router.post("/api/models/b2/train")
def b2_train(request: Request, body: B2TrainBody):
    """*Train locally*: the B.2 forest as a `training` job."""
    import Adapters.catalogue_shape_cluster as csc
    from Working.training import shape_forest as sf
    from Working.training.store import CutFrozen
    from .training_routes import _training_root
    rt, manager = request.app.state.rt, request.app.state.manager
    c = _conn(request)
    try:
        t = _template(c, body.template)
        row, p = _pool_row(c, body.pool)
        try:
            recipe = sf.make_recipe({"id": int(row["id"]), "name": row["name"], "version": int(row["version"] or 1),
                                     "key": p.key}, {"id": int(t["id"]), "name": t["name"], "steps": t["steps"]},
                                    n_estimators=body.n_estimators, class_weight=body.class_weight,
                                    random_state=body.random_state)
        except ValueError as e:
            raise HTTPException(422, str(e))
        try:
            sf.check_frozen(c, p.key, recipe["arm"]["k"], recipe["arm"]["mapping"])
        except CutFrozen as e:
            raise HTTPException(409, str(e))
    finally:
        c.close()
    root, tree_root = _training_root(rt), csc.RESULTS_DIR

    def work(job):
        cc = _conn(request)
        try:
            out = sf.run_and_record(cc, recipe, root, tree_root=tree_root,
                                    progress=lambda d, tt, m: job.progress(d, tt, m), cancel=job.cancel_event.is_set)
            return {"run_id": int(out["run_id"]), "results_path": out["results_path"],
                    "diagnostic": out["results"]["diagnostic"],
                    "exams": {k: {kk: v[kk] for kk in ("status", "n", "by_class")} for k, v in out["results"]["exams"].items()}}
        finally:
            cc.close()

    job = manager.start_job("training", work, meta={"stage": "B.2 forest", "pool": recipe["pool"], "k": recipe["arm"]["k"],
                                                    "template": recipe["template"]["name"], "where": "local"})
    return job.snapshot()


@router.get("/api/models/b2/runs")
def b2_runs(request: Request):
    from Working.training import shape_forest as sf
    c = _conn(request)
    try:
        return {"runs": sf.list_runs(c)}
    finally:
        c.close()


@router.get("/api/models/b2/frozen")
def b2_frozen(request: Request, pool_key: str):
    """For Analyse's cluster page: the scored run that fixes this pool's cut and mapping, if any."""
    from Working.training import shape_forest as sf
    c = _conn(request)
    try:
        return {"frozen": sf.frozen_for(c, pool_key)}
    finally:
        c.close()


# ── Library › Window sets: rename (the researcher, 2026-10-06) ──────────────

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


class RenameBody(BaseModel):
    name: str


@router.patch("/api/windowsets/{set_id}/name")
def rename_window_set(request: Request, set_id: int, body: RenameBody):
    """The name changes; the key, the version, the files and every pool that uses the set (by id) do not."""
    from Working.registration.settings import append_audit
    new = (body.name or "").strip()
    if not _NAME.match(new):
        raise HTTPException(422, "a window set's name is 1–64 letters, digits, _ . - (no spaces), starting with a "
                                 "letter or digit")
    c = _conn(request)
    try:
        row = c.execute("SELECT id, name, version, recipe_hash FROM window_sets WHERE id = ?", (int(set_id),)).fetchone()
        if row is None:
            raise HTTPException(404, f"no window set {set_id}")
        if new == row["name"]:
            return {"id": int(row["id"]), "name": new, "version": int(row["version"]), "key": row["recipe_hash"],
                    "changed": False}
        clash = c.execute("SELECT id FROM window_sets WHERE name = ? AND version = ? AND id != ?",
                          (new, int(row["version"]), int(set_id))).fetchone()
        if clash is not None:
            raise HTTPException(409, f"another window set is already called {new} v{row['version']}")
        c.execute("UPDATE window_sets SET name = ? WHERE id = ?", (new, int(set_id)))
        append_audit(c, "library", f"Window set renamed: {row['name']} v{row['version']} → {new} v{row['version']}",
                     "Library › Window sets", route=f"library/window-sets?set={new}",
                     detail={"id": int(set_id), "from": row["name"], "to": new, "version": int(row["version"]),
                             "key": row["recipe_hash"]}, commit=False)
        c.commit()
        return {"id": int(set_id), "name": new, "version": int(row["version"]), "key": row["recipe_hash"],
                "changed": True, "was": row["name"]}
    finally:
        c.close()
