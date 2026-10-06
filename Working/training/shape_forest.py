"""
shape_forest.py
===============
fixup-ag seam (iii): arm **B.2 cluster labels · trace shape** — a random forest
trained on the CLUSTER categories of a window pool (RQ1 version 2).

The chain decides the categories: *Window pool* → *Trace shape* → *Shape
clustering* (its cut `k` and the researcher's interesting / not `mapping`). This
module trains the model on them and records the run, through the same tables the
paired job uses (`configs`, `runs`, `artifacts`; `store.CutFrozen` for the
freeze).

The model's inputs (the researcher, 2026-10-06)
-----------------------------------------------
"Windows should be fed into the model-trainer as their original raw signal, not
a detrended version." Centring decides WHICH samples a window covers (its re-cut
bounds); detrend and normalise exist only to compare shapes for clustering. The
forest's features are the window-matrix measures (catch22 + fast entropy, the
baseline's) of the RAW samples at the re-cut bounds
(`Working.Preprocessing.window_matrix.build.features_at`), so they do not depend
on the detrend option. A CNN (`AI`) makes its images from the same raw samples:
the recipe says so (`INPUTS_RULE`).

What the run does
-----------------
1. the pool (a saved `window_sets` row, key checked) through Trace shape's own
   function with the template's options → the windows and their re-cut bounds;
2. the kept tree (`<tree_root>/<tree key>`, built and kept if absent) cut at `k`
   → a cluster for every TRAINING window (sampled + assigned);
3. a DIAGNOSTIC: a forest on 80 % of the training windows predicts the other 20 %
   — how well the forest reproduces its own answer key. Labelled as such, never a
   result;
4. the forest on every training window; the validation, test and exam windows are
   assigned only by it — their predicted cluster, the mapped class and P(interesting)
   (the summed probability of the interesting clusters), on disk by path;
5. exams: (i) the later block (role test), (ii) unseen channels (role exam), each
   "predicted · not yet labelled" with per-cluster and per-class counts; the
   yardstick-(B) row "not yet labelled" — `AH`'s blind queue labels these windows.

The freeze: once any run on the pool has a test SCORE (an exam whose status is
`scored`, which `AH` writes), a recipe whose cut or interesting / not mapping
differs is refused with the run named.

Headless: no UI or web library is imported here (CLAUDE.md rule 1).
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import time

import numpy as np
import pandas as pd

from Working.training.store import CutFrozen

RECIPE_KIND = "shape_cluster_forest"
ARM_LABEL = "B.2 cluster labels · trace shape"
DEFAULT_STAGES = ("catch22", "fast_entropy")
EXAM_I, EXAM_II = "i_later_block", "ii_unseen_channels"
HOLDBACK_FRAC = 0.2
INPUTS_RULE = ("the model is trained on the ORIGINAL RAW signal of each window: its features are measured on the raw "
               "samples at the window's re-cut bounds (centring decides which samples a window covers); detrend and "
               "normalise exist only to compare shapes for clustering and never reach the model. A CNN arm makes its "
               "images from the same raw samples at the same bounds.")
PREDICTED = "predicted · not yet labelled"
CLASSES = ("interesting", "not_interesting")


def _now():
    return _dt.datetime.now().isoformat(timespec="seconds")


# ── the recipe ──────────────────────────────────────────────────────────────

def _step(steps, algorithm):
    for s in steps:
        if s.get("algorithm") == algorithm:
            return s
    raise ValueError(f"the template has no {algorithm} step: B.2 trains on a Window pool → Trace shape → Shape "
                     "clustering chain")


def chain_settings(steps):
    """The Trace shape and Shape clustering parameters of a template, defaults filled."""
    from Adapters.registry import discover_adapters, get_adapter
    from Adapters.catalogue_shape_cluster import parse_mapping
    discover_adapters()
    shp = get_adapter("preprocessing.trace_shape").validate_params(_step(steps, "trace_shape").get("params") or {})
    clu = get_adapter("catalogue.shape_cluster").validate_params(_step(steps, "shape_cluster").get("params") or {})
    return shp, clu, parse_mapping(clu.get("mapping"))


def mapping_problem(k, mapping):
    """None when the mapping gives every cluster 1..k a class at this cut, else what is wrong."""
    if not k or int(k) < 2:
        return "no cut: set k on the Shape clustering block (move the cut on its page) before training"
    if mapping.get("k") is not None and int(mapping["k"]) != int(k):
        return f"the mapping was made at k = {mapping['k']} and the cut is k = {k}: map the clusters again"
    missing = [c for c in range(1, int(k) + 1) if not (mapping["clusters"].get(str(c)) or {}).get("class")]
    if missing:
        return (f"map every cluster at the cut: cluster(s) {missing} have no interesting / not class yet "
                "(the mapping table on the Shape clustering page)")
    return None


def make_recipe(pool_ref, template, *, stages=DEFAULT_STAGES, n_estimators=300, class_weight="balanced",
                random_state=42, holdback_frac=HOLDBACK_FRAC):
    """The B.2 recipe: the pool, the template (its steps carry the cut and the mapping), the forest."""
    shp, clu, mapping = chain_settings(template["steps"])
    k = int(clu["k"])
    problem = mapping_problem(k, mapping)
    if problem:
        raise ValueError(problem)
    return {
        "kind": RECIPE_KIND,
        "pool": {k2: pool_ref.get(k2) for k2 in ("id", "name", "version", "key")},
        "template": {"id": template.get("id"), "name": template.get("name"), "steps": template["steps"]},
        "shape": {k2: shp[k2] for k2 in ("align", "detrend", "resample_length", "noise_floor")},
        "cluster": {"sample": int(clu["sample"]), "seed": int(clu["seed"]), "tree_path": clu.get("tree_path") or ""},
        "arm": {"name": "B.2", "label": ARM_LABEL, "k": k, "mapping": mapping, "linkage": "ward"},
        "inputs": {"features": "raw samples at the re-cut bounds", "stages": list(stages), "rule": INPUTS_RULE},
        "forest": {"n_estimators": int(n_estimators), "class_weight": class_weight, "random_state": int(random_state)},
        "diagnostic": {"holdback_frac": float(holdback_frac)},
        "exams": {EXAM_I: "on", EXAM_II: "on"},
    }


# ── features on the raw samples ─────────────────────────────────────────────

def raw_features(conn, frame, stages=DEFAULT_STAGES, progress=None, cancel=None):
    """The window-matrix measures of the RAW samples at each window's (re-cut) bounds, in frame order."""
    from Working.Preprocessing.window_matrix.build import features_at
    from Working.database import window_matrix_store as wm
    columns = list(wm.measure_columns(tuple(stages)))
    out = np.full((len(frame), len(columns)), np.nan, dtype=np.float64)
    npy = {int(r[0]): r[1] for r in conn.execute("SELECT id, npy_path FROM recordings")}
    f = frame.reset_index(drop=True)
    groups = list(f.groupby(["recording_id", "length"], sort=True))
    for gi, ((rid, length), g) in enumerate(groups):
        if cancel is not None and cancel():
            raise InterruptedError("cancelled while measuring the windows")
        if progress is not None:
            progress(gi, len(groups), f"measuring {len(g):,} raw windows of {int(length)} samples")
        x = np.load(npy[int(rid)], mmap_mode="r")
        vals, _computed, cols = features_at(x, g["start"].to_numpy(), int(length), tuple(stages))
        idx = [columns.index(c) for c in cols]
        out[np.ix_(g.index.to_numpy(), idx)] = np.asarray(vals, dtype=np.float64)
    return pd.DataFrame(out, columns=columns)


# ── the run ─────────────────────────────────────────────────────────────────

def _load(conn, recipe, tree_root, progress=None):
    from Working.training import pool as tpool
    from Working.training import shape as sh
    row, pool = tpool.load_pool(conn, int(recipe["pool"]["id"]))
    if recipe["pool"].get("key") and recipe["pool"]["key"] != pool.key:
        raise ValueError(f"the recipe names pool key {recipe['pool']['key']}, but {row['name']} v{row['version']} "
                         f"has key {pool.key}")
    s = recipe["shape"]
    shapes = sh.trace_shapes(conn, sh.pool_frame(sh.pool_windowset(pool)), resample_length=int(s["resample_length"]),
                             noise_floor=bool(s["noise_floor"]), align=s["align"], detrend=s["detrend"],
                             progress=progress)
    c = recipe["cluster"]
    if c.get("tree_path"):
        tree, tree_dir = sh.load_tree_for(c["tree_path"], shapes), c["tree_path"]
    else:
        sample = None if int(c["sample"]) <= 0 else int(c["sample"])
        tree_dir = os.path.join(str(tree_root), sh.tree_key(shapes, sample, int(c["seed"])))
        if os.path.isfile(os.path.join(tree_dir, "tree.npz")):
            tree = sh.load_tree_for(tree_dir, shapes)
        else:
            tree = sh.cluster_shapes(shapes, sample=sample, seed=int(c["seed"]))
            tree.save(tree_dir)
    return row, pool, shapes, tree, tree_dir


def _forest(cfg):
    from Working.training.paired import _forest as paired_forest
    return paired_forest(cfg)


def run_forest(conn, recipe, *, tree_root, out_dir, progress=None, cancel=None):
    """Train the B.2 forest and predict every non-training window; returns the results dict (written by the caller)."""
    import joblib
    from sklearn.metrics import accuracy_score, f1_score
    from Working.training import shape as sh
    t0 = time.time()
    timings = {}
    say = (lambda d, t, m: progress(d, t, m)) if progress else (lambda *a: None)
    say(0, 6, "the windows and their re-cut bounds")
    row, pool, shapes, tree, tree_dir = _load(conn, recipe, tree_root)
    timings["shapes_and_tree"] = round(time.time() - t0, 1)
    arm = recipe["arm"]
    k = int(arm["k"])
    lab = sh.labels_at(tree, shapes, k)
    f = shapes.frame.reset_index(drop=True)
    roles = f["role"].to_numpy().astype(str)
    train = np.flatnonzero(roles == "train")
    y_train = lab.labels[train]

    t = time.time()
    say(1, 6, "measuring the raw samples at the re-cut bounds")
    X = raw_features(conn, f, recipe["inputs"]["stages"], cancel=cancel)
    timings["features"] = round(time.time() - t, 1)
    medians = X.iloc[train].median()
    Xf = X.fillna(medians).fillna(0.0).to_numpy(dtype=np.float64)

    t = time.time()
    say(2, 6, "the diagnostic: the forest against its own answer key")
    rng = np.random.default_rng(int(recipe["forest"]["random_state"]))
    held = np.zeros(len(train), dtype=bool)
    held[rng.choice(len(train), size=max(1, int(round(recipe["diagnostic"]["holdback_frac"] * len(train)))),
                    replace=False)] = True
    diag_model = _forest(recipe["forest"]).fit(Xf[train[~held]], y_train[~held])
    pred_held = diag_model.predict(Xf[train[held]])
    diagnostic = {"kind": "diagnostic", "n_held_back": int(held.sum()), "n_fit": int((~held).sum()),
                  "accuracy": float(accuracy_score(y_train[held], pred_held)),
                  "macro_f1": float(f1_score(y_train[held], pred_held, average="macro")),
                  "chance_largest_cluster": float(np.bincount(y_train[held]).max() / held.sum()),
                  "note": ("how well the forest reproduces the clustering on training windows it did not fit (a "
                           "seeded 20 %) — a forest imitating its own answer key: a diagnostic, not a result")}
    timings["diagnostic"] = round(time.time() - t, 1)

    t = time.time()
    say(3, 6, "the forest on every training window")
    model = _forest(recipe["forest"]).fit(Xf[train], y_train)
    timings["train"] = round(time.time() - t, 1)
    os.makedirs(out_dir, exist_ok=True)
    model_path = os.path.join(out_dir, "forest_b2.joblib")
    joblib.dump({"model": model, "columns": list(X.columns), "medians": medians.to_dict(), "k": k,
                 "mapping": arm["mapping"], "inputs": recipe["inputs"]}, model_path, compress=3)
    # (uncompressed, 300 fully grown trees on ~30,000 windows and 8 clusters were 611 MB on the sandbox pool)

    say(4, 6, "assigning the validation, test and exam windows")
    other = np.flatnonzero(roles != "train")
    proba = model.predict_proba(Xf[other]) if len(other) else np.zeros((0, len(model.classes_)))
    classes_ = np.asarray(model.classes_)
    pred = classes_[np.argmax(proba, axis=1)] if len(other) else np.zeros(0, dtype=int)
    interesting = [int(c) for c, v in arm["mapping"]["clusters"].items() if v.get("class") == "interesting"]
    p_int = proba[:, np.isin(classes_, interesting)].sum(axis=1) if len(other) else np.zeros(0)
    cls = np.array([arm["mapping"]["clusters"][str(int(c))]["class"] for c in pred], dtype=object)
    fo = f.iloc[other]
    preds = pd.DataFrame({"recording_id": fo["recording_id"].to_numpy(), "source_file": fo["source_file"].to_numpy(),
                          "channel": fo["channel"].to_numpy(), "start": fo["start"].to_numpy(),
                          "orig_start": (fo["orig_start"].to_numpy() if "orig_start" in fo.columns else fo["start"].to_numpy()),
                          "length": fo["length"].to_numpy(), "fs": fo["fs"].to_numpy(),
                          "scale_min": fo["scale_min"].to_numpy(), "role": fo["role"].to_numpy(),
                          "cluster": pred.astype(np.int64), "class": cls.astype(str),
                          "p_interesting": p_int.astype(np.float64)})
    pred_path = os.path.join(out_dir, "predictions.parquet")
    preds.to_parquet(pred_path, index=False)

    say(5, 6, "the results")
    exams = {}
    for name, role in ((EXAM_I, "test"), (EXAM_II, "exam")):
        p = preds[preds["role"] == role]
        exams[name] = {"status": PREDICTED, "role": role, "n": int(len(p)),
                       "by_cluster": {str(c): int((p["cluster"] == c).sum()) for c in range(1, k + 1)},
                       "by_class": {c: int((p["class"] == c).sum()) for c in CLASSES},
                       "by_scale": {f"{float(s):g}": int(n) for s, n in p["scale_min"].value_counts().sort_index().items()},
                       "note": ("assigned by the trained model only; scored when AH's blind queue has labelled a "
                                "sample of these windows")}
    sizes = {str(c): int((y_train == c).sum()) for c in range(1, k + 1)}
    results = {
        "kind": RECIPE_KIND, "arm": {"name": "B.2", "label": ARM_LABEL, "k": k, "linkage": "ward"},
        "pool": {"id": int(row["id"]), "name": row["name"], "version": int(row["version"] or 1), "key": pool.key},
        "template": {"id": recipe["template"].get("id"), "name": recipe["template"].get("name")},
        "shape": recipe["shape"], "inputs": recipe["inputs"], "mapping": arm["mapping"],
        "tree": {"key": os.path.basename(str(tree_dir).rstrip("/\\")), "dir": os.path.abspath(tree_dir),
                 "n_clustered": int(lab.n_clustered), "n_assigned": int(lab.n_assigned), "shape_key": shapes.key},
        "training": {"n_train": int(len(train)), "cluster_sizes": sizes, "features": list(X.columns),
                     "model_path": model_path, "forest": recipe["forest"],
                     "classes_interesting": sorted(interesting)},
        "diagnostic": diagnostic, "exams": exams, "predictions_path": pred_path, "model_path": model_path,
        "yardstick_A": {"status": "no arm A", "reason": "the pool is unlabelled: there is no manual-label arm here; "
                                                        "AH's reference line is the comparison"},
        "yardstick_B": {"status": "not yet labelled", "reason": "AH's blind interesting / not queue over these test "
                                                                "and exam windows scores them"},
        "timings": {**timings, "total": round(time.time() - t0, 1)},
    }
    return results


# ── recording, listing, the freeze ──────────────────────────────────────────

def _runs(conn, status=None):
    sql = ("SELECT r.*, c.config_hash, c.config_json FROM runs r JOIN configs c ON c.id = r.config_id "
           "WHERE json_extract(c.config_json, '$.kind') = ?")
    args = [RECIPE_KIND]
    if status:
        sql += " AND r.status = ?"
        args.append(status)
    return conn.execute(sql + " ORDER BY r.id DESC", args).fetchall()


def _results_of(conn, run_id):
    row = conn.execute("SELECT path FROM artifacts WHERE run_id = ? AND kind = 'other' AND path LIKE '%results.json' "
                       "ORDER BY id LIMIT 1", (int(run_id),)).fetchone()
    if row is None or not os.path.isfile(row[0]):
        return None, None
    with open(row[0], encoding="utf-8") as fh:
        return row[0], json.load(fh)


def _scored(res):
    return bool(res) and any((e or {}).get("status") == "scored" for e in (res.get("exams") or {}).values())


def frozen_for(conn, pool_key):
    """The scored run that fixes this pool's cut and mapping, or None."""
    for r in _runs(conn, status="completed"):
        rec = json.loads(r["config_json"])
        if (rec.get("pool") or {}).get("key") != pool_key:
            continue
        _path, res = _results_of(conn, r["id"])
        if _scored(res):
            return {"run_id": int(r["id"]), "k": int(rec["arm"]["k"]), "mapping": rec["arm"]["mapping"],
                    "name": r["name"]}
    return None


def _classes(mapping):
    return {str(c): (v or {}).get("class") for c, v in (mapping or {}).get("clusters", {}).items()}


def check_frozen(conn, pool_key, k, mapping):
    """Refuse a cut or an interesting / not mapping that differs from one already scored on this pool."""
    fz = frozen_for(conn, pool_key)
    if fz is None:
        return
    if int(k) != fz["k"]:
        raise CutFrozen(f"run {fz['run_id']} already has a test score on this pool at k = {fz['k']}: the cut is "
                        "frozen once a test score exists — choosing it after seeing test scores is tuning on the test "
                        "windows. Keep k, or make a new pool.")
    if mapping is not None and _classes(mapping) != _classes(fz["mapping"]):
        raise CutFrozen(f"run {fz['run_id']} already has a test score on this pool: its interesting / not mapping is "
                        "frozen (names may change; classes may not). Keep the mapping, or make a new pool.")


def run_and_record(conn, recipe, root, *, tree_root, progress=None, cancel=None):
    """Refuse a frozen change, run, and record (configs / runs / artifacts) as the paired job does."""
    from Working.database import runs as R
    check_frozen(conn, recipe["pool"]["key"], recipe["arm"]["k"], recipe["arm"]["mapping"])
    config_id, h = R.get_or_create_config(conn, recipe)
    first = conn.execute("SELECT recording_id FROM window_set_channels WHERE window_set_id = ? ORDER BY recording_id "
                         "LIMIT 1", (int(recipe["pool"]["id"]),)).fetchone()
    rec = conn.execute("SELECT id, n_samples FROM recordings WHERE id = ?", (int(first[0]),)).fetchone()
    run_id = R.insert_run(conn, config_id, int(rec[0]), 0, int(rec[1]), status="running",
                          name=f"B.2 · {recipe['pool']['name']} v{recipe['pool']['version']} · k={recipe['arm']['k']}")
    out_dir = os.path.join(str(root), f"shape_forest_{h}_run{run_id}")
    t0 = _dt.datetime.now()
    try:
        from Working.training.store import jsonable
        results = run_forest(conn, recipe, tree_root=tree_root, out_dir=out_dir, progress=progress, cancel=cancel)
        results["run_id"] = run_id
        path = os.path.join(out_dir, "results.json")
        results = jsonable(results)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(results, fh, allow_nan=False)
        R.insert_artifact(conn, run_id, "other", path)
        R.insert_artifact(conn, run_id, "model", results["model_path"])
        R.insert_artifact(conn, run_id, "other", results["predictions_path"])
        dur = (_dt.datetime.now() - t0).total_seconds()
        conn.execute("UPDATE runs SET status = 'completed', finished_at = ?, duration_s = ?, step_timings_json = ? "
                     "WHERE id = ?", (_now(), dur, json.dumps(results["timings"]), run_id))
        conn.commit()
    except BaseException:
        import traceback
        conn.execute("UPDATE runs SET status = 'failed', finished_at = ?, error_text = ? WHERE id = ?",
                     (_now(), traceback.format_exc(), run_id))
        conn.commit()
        raise
    return {"run_id": run_id, "results": results, "results_path": path, "config_hash": h}


def list_runs(conn):
    out = []
    for r in _runs(conn):
        rec = json.loads(r["config_json"])
        path, res = _results_of(conn, r["id"]) if r["status"] == "completed" else (None, None)
        out.append({"run_id": int(r["id"]), "status": r["status"], "name": r["name"], "started_at": r["started_at"],
                    "finished_at": r["finished_at"], "duration_s": r["duration_s"], "config_hash": r["config_hash"],
                    "pool": rec.get("pool"), "template": {k2: (rec.get("template") or {}).get(k2) for k2 in ("id", "name")},
                    "k": int(rec["arm"]["k"]), "mapping": rec["arm"]["mapping"], "shape": rec.get("shape"),
                    "scored": _scored(res), "diagnostic": (res or {}).get("diagnostic"),
                    "exams": {k2: {kk: v.get(kk) for kk in ("status", "n", "by_class")} for k2, v in ((res or {}).get("exams") or {}).items()},
                    "results_path": path,
                    "error": (r["error_text"] or "").strip().splitlines()[-1] if r["error_text"] else None})
    return out
