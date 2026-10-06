"""
hpc_import.py
=============
fixup-ai: bringing a cluster job's results back — ONE function,
`import_results(conn, job_dir, *, root, tree_root=None)`, called by

* the command line: `python -m Working.training import-results <job dir>`;
* the local smoke (`shape_cnn.run_local_smoke`), so the smoke proves the round trip;
* Jobs › Manifest inbox (ticket `AJ`), which puts this same function on a page.

It reads a job directory written by `shape_cnn.export_job` (the B.2 CNN) or
`full_ward.export_job` (Ward over every training window), with the cluster's
`out/` copied back into it, and:

1. validates: `recipe.json`'s short hash is the one the job was written with
   (`job.json`) and the one the results were made from (`out/done.json`); the
   windows are the windows the recipe names (their content key); the pool is in
   this database under the same key; every prediction is for a window of the
   job; the cut and mapping are not a change on a pool that already has a test
   score (`shape_forest.check_frozen`, `store.CutFrozen`);
2. records the run as the forest's is: a `configs` row (the recipe), a `runs`
   row, `artifacts` rows (the results JSON, the model, the predictions on disk);
3. writes the forest's results shape (`shape_forest.run_forest`): the results
   JSON and the predictions parquet with the same columns — so Models › Results
   and `AH`'s blind queue read it with no second reader.

The same job imported twice is one run (the recipe hash is its identity).
Headless: no UI or web library is imported here (CLAUDE.md rule 1).
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import shutil

import numpy as np


class ImportRefused(ValueError):
    """The returned job cannot be recorded: the reason says what to do."""


def _now():
    return _dt.datetime.now().isoformat(timespec="seconds")


def _read(path, what):
    if not os.path.isfile(path):
        raise ImportRefused(f"{what} is missing: {path}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def import_results(conn, job_dir, *, root, tree_root=None, where=None):
    """Validate a returned job directory against its recipe hash and record it.

    Returns `{"kind", "run_id", "created", "config_hash", "results_path" | "tree_dir", "name", "message"}`;
    raises `ImportRefused` (or `store.CutFrozen`) with the reason."""
    job_dir = os.path.abspath(str(job_dir))
    if not os.path.isdir(job_dir):
        raise ImportRefused(f"no job directory at {job_dir}")
    recipe = _read(os.path.join(job_dir, "recipe.json"), "the job's recipe.json")
    kind = recipe.get("kind")
    from Working.training import cnn_job, full_ward
    if kind == cnn_job.RECIPE_KIND:
        return _import_cnn(conn, job_dir, recipe, root=root, tree_root=tree_root, where=where)
    if kind == full_ward.RECIPE_KIND:
        return _import_ward(conn, job_dir, recipe, root=root, tree_root=tree_root)
    raise ImportRefused(f"{job_dir} holds a {kind!r} job; this import knows the B.2 CNN ({cnn_job.RECIPE_KIND}) and "
                        f"the full-pool Ward ({full_ward.RECIPE_KIND})")


def _check_hashes(job_dir, recipe):
    from Working.recipes import short_hash
    h = short_hash(recipe)
    meta = _read(os.path.join(job_dir, "job.json"), "the job's job.json")
    if meta.get("recipe_hash") != h:
        raise ImportRefused(f"recipe.json was changed after the job was written: its hash is {h}, the job was written "
                            f"for recipe {meta.get('recipe_hash')}. Export the job again from the site.")
    done_path = os.path.join(job_dir, "out", "done.json")
    if not os.path.isfile(done_path):
        raise ImportRefused(f"the job has not finished: no results in {done_path}. Copy the cluster's out/ back into "
                            "the job directory once the job's log says it is complete.")
    done = _read(done_path, "out/done.json")
    if done.get("recipe_hash") != h or done.get("status") != "complete":
        raise ImportRefused(f"out/done.json was made from recipe {done.get('recipe_hash')} (status "
                            f"{done.get('status')}), not this job's recipe {h}: these are not this job's results")
    return h, meta, done


def _existing(conn, h):
    row = conn.execute("SELECT r.id FROM runs r JOIN configs c ON c.id = r.config_id WHERE c.config_hash = ? AND "
                       "r.status = 'completed' ORDER BY r.id LIMIT 1", (h,)).fetchone()
    return int(row[0]) if row else None


def _pool_row(conn, key):
    row = conn.execute("SELECT * FROM window_sets WHERE recipe_hash = ? ORDER BY id DESC LIMIT 1", (str(key),)).fetchone()
    return row


def _run_recording(conn, pool_id):
    first = conn.execute("SELECT recording_id FROM window_set_channels WHERE window_set_id = ? ORDER BY recording_id "
                         "LIMIT 1", (int(pool_id),)).fetchone()
    rec = (conn.execute("SELECT id, n_samples FROM recordings WHERE id = ?", (int(first[0]),)).fetchone() if first
           else conn.execute("SELECT id, n_samples FROM recordings ORDER BY id LIMIT 1").fetchone())
    return int(rec[0]), int(rec[1])


# ── the B.2 CNN ─────────────────────────────────────────────────────────────

def _import_cnn(conn, job_dir, recipe, *, root, tree_root, where):
    import pandas as pd
    from Working.database import runs as R
    from Working.training import cnn_job
    from Working.training import shape_cnn as sc
    from Working.training import shape_forest as sf
    from Working.training.store import jsonable
    h, meta, done = _check_hashes(job_dir, recipe)
    w = cnn_job.load_windows(job_dir)
    key = cnn_job.windows_key(w)
    if key != (recipe.get("bundle") or {}).get("windows_key"):
        raise ImportRefused(f"the windows in windows.npz (key {key}) are not the windows the recipe names "
                            f"({(recipe.get('bundle') or {}).get('windows_key')}): the job directory was changed")
    pool_key = recipe["pool"]["key"]
    prow = _pool_row(conn, pool_key)
    if prow is None:
        raise ImportRefused(f"the pool {recipe['pool'].get('name')} v{recipe['pool'].get('version')} (key {pool_key}) "
                            "is not in this database: import into the database the job was exported from")
    arm = recipe["arm"]
    k = int(arm["k"])
    sf.check_frozen(conn, pool_key, k, arm["mapping"])           # CutFrozen: a changed cut on a scored pool
    old = _existing(conn, h)
    if old is not None:
        path, _res = sf._results_of(conn, old)
        return {"kind": cnn_job.RECIPE_KIND, "run_id": old, "created": False, "config_hash": h, "results_path": path,
                "name": None, "message": f"already imported as run {old}: the same recipe is the same run"}

    # the predictions: one row per non-training window of the job, P(cluster) for clusters 1..k
    pp = os.path.join(job_dir, "out", "predictions.npz")
    if not os.path.isfile(pp):
        raise ImportRefused(f"the job says it finished but {pp} is missing")
    with np.load(pp, allow_pickle=False) as z:
        idx, rowids, probs, classes = z["index"], z["row"], np.asarray(z["probs"], dtype=np.float64), z["classes"]
    roles = np.asarray(w["role"]).astype(str)
    want = np.flatnonzero(roles != "train")
    if len(idx) != len(want) or not np.array_equal(np.sort(idx), want) or not np.array_equal(
            rowids, np.asarray(w["row"])[idx]):
        raise ImportRefused(f"predictions.npz names {len(idx):,} windows; the job's non-training windows are "
                            f"{len(want):,} — these predictions are not for this job's windows")
    if probs.shape != (len(idx), k) or list(classes) != list(range(1, k + 1)) or not np.isfinite(probs).all():
        raise ImportRefused(f"predictions.npz holds probabilities of shape {probs.shape} for classes {list(classes)}; "
                            f"the recipe's cut is k = {k}")
    recs ={int(r[0]): (r[1], int(r[2])) for r in conn.execute("SELECT id, source_file, channel FROM recordings")}
    for rid, sfile, ch in set(zip(np.asarray(w["recording_id"]).tolist(), np.asarray(w["source_file"]).tolist(),
                                  np.asarray(w["channel"]).tolist())):
        if recs.get(int(rid)) != (str(sfile), int(ch)):
            raise ImportRefused(f"recording {rid} is {recs.get(int(rid))} in this database, the job names it "
                                f"{sfile} channel {ch}: import into the database the job was exported from")

    config_id, h2 = R.get_or_create_config(conn, recipe)
    rec_id, n_samples = _run_recording(conn, prow["id"])
    smoke = recipe.get("smoke")
    name = (f"B.2 CNN {recipe['inputs']['encoding']} · {recipe['pool']['name']} v{recipe['pool']['version']} · "
            f"k={k}" + (" · smoke" if smoke else ""))
    run_id = R.insert_run(conn, config_id, rec_id, 0, n_samples, status="running", name=name)
    out_dir = os.path.join(str(root), f"shape_cnn_{h}_run{run_id}")
    try:
        os.makedirs(out_dir, exist_ok=True)
        src = os.path.join(job_dir, "out")
        for fn in ("model.pt", "model.json", "history.json", "diagnostic.json", "done.json"):
            if os.path.isfile(os.path.join(src, fn)):
                shutil.copyfile(os.path.join(src, fn), os.path.join(out_dir, fn))
        interesting = [int(c) for c, v in arm["mapping"]["clusters"].items() if v.get("class") == "interesting"]
        pred = classes[np.argmax(probs, axis=1)].astype(np.int64)
        p_int = probs[:, np.isin(classes, interesting)].sum(axis=1)
        cls = np.array([arm["mapping"]["clusters"][str(int(c))]["class"] for c in pred], dtype=object)

        def col(f):
            return np.asarray(w[f])[idx]
        preds = pd.DataFrame({"recording_id": col("recording_id").astype(np.int64),
                              "source_file": col("source_file").astype(str), "channel": col("channel").astype(np.int64),
                              "start": col("start").astype(np.int64), "orig_start": col("orig_start").astype(np.int64),
                              "length": col("length").astype(np.int64), "fs": col("fs").astype(np.float64),
                              "scale_min": col("scale_min").astype(np.float64), "role": col("role").astype(str),
                              "cluster": pred, "class": cls.astype(str), "p_interesting": p_int.astype(np.float64)})
        pred_path = os.path.join(out_dir, "predictions.parquet")
        preds.to_parquet(pred_path, index=False)
        exams = {}
        for ename, role in ((sf.EXAM_I, "test"), (sf.EXAM_II, "exam")):
            p = preds[preds["role"] == role]
            exams[ename] = {"status": sf.PREDICTED, "role": role, "n": int(len(p)),
                            "by_cluster": {str(c): int((p["cluster"] == c).sum()) for c in range(1, k + 1)},
                            "by_class": {c: int((p["class"] == c).sum()) for c in sf.CLASSES},
                            "by_scale": {f"{float(s):g}": int(n) for s, n in p["scale_min"].value_counts().sort_index().items()},
                            "note": ("assigned by the trained CNN only; scored when AH's blind queue has labelled a "
                                     "sample of these windows")}
        lab = np.asarray(w["label"])
        train_lab = lab[roles == "train"]
        diag = _read(os.path.join(src, "diagnostic.json"), "out/diagnostic.json")
        null = _null(job_dir, out_dir, w, k, h)
        b = recipe["bundle"]
        tdir = os.path.join(str(tree_root), b["tree_key"]) if tree_root else None
        model_path = os.path.join(out_dir, "model.pt")
        results = {
            "kind": cnn_job.RECIPE_KIND, "arm": {"name": "B.2", "label": sf.ARM_LABEL, "k": k, "linkage": "ward"},
            "model": sc.model_label(recipe),
            "pool": {"id": int(prow["id"]), "name": prow["name"], "version": int(prow["version"] or 1), "key": pool_key},
            "template": {"id": recipe["template"].get("id"), "name": recipe["template"].get("name")},
            "shape": recipe["shape"], "inputs": recipe["inputs"], "mapping": arm["mapping"],
            "tree": {"key": b["tree_key"], "dir": os.path.abspath(tdir) if tdir else None,
                     "n_clustered": b.get("n_clustered"), "n_assigned": b.get("n_assigned"), "shape_key": b["shape_key"]},
            "training": {"n_train": int(len(train_lab)),
                         "cluster_sizes": {str(c): int((train_lab == c).sum()) for c in range(1, k + 1)},
                         "model_path": model_path, "cnn": recipe["cnn"], "training_rule": recipe.get("training_rule"),
                         "classes_interesting": sorted(interesting), "n_fit_diagnostic": done.get("n_fit_diagnostic"),
                         "n_fit_final": done.get("n_fit_final"), "history_path": os.path.join(out_dir, "history.json")},
            "diagnostic": diag, "exams": exams, "predictions_path": pred_path, "model_path": model_path,
            "yardstick_A": {"status": "no arm A", "reason": "the pool is unlabelled: there is no manual-label arm here; "
                                                            "AH's reference line is the comparison"},
            "yardstick_B": {"status": "not yet labelled", "reason": "AH's blind interesting / not queue over these "
                                                                    "test and exam windows scores them"},
            "null": null, "smoke": smoke, "where": where or ("local" if not str(
                (done.get("measured") or {}).get("device", "")).startswith("cuda") else "HPC"),
            "measured": done.get("measured"), "timings": done.get("timings"),
            "hpc": {"job_dir": job_dir, "recipe_hash": h, "imported_at": _now(), "finished_at": done.get("finished_at"),
                    "jobs": done.get("jobs"), "torch": done.get("torch")},
            "run_id": run_id,
        }
        path = os.path.join(out_dir, "results.json")
        results = jsonable(results)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(results, fh, allow_nan=False)
        R.insert_artifact(conn, run_id, "other", path)
        R.insert_artifact(conn, run_id, "model", model_path)
        R.insert_artifact(conn, run_id, "other", pred_path)
        for npath in (null or {}).get("predictions_paths", []):
            R.insert_artifact(conn, run_id, "other", npath)
        tot = float((done.get("timings") or {}).get("total") or 0.0)
        conn.execute("UPDATE runs SET status = 'completed', finished_at = ?, duration_s = ?, step_timings_json = ? "
                     "WHERE id = ?", (_now(), tot, json.dumps(done.get("timings") or {}), run_id))
        conn.commit()
    except BaseException:
        import traceback
        conn.execute("UPDATE runs SET status = 'failed', finished_at = ?, error_text = ? WHERE id = ?",
                     (_now(), traceback.format_exc(), run_id))
        conn.commit()
        raise
    return {"kind": cnn_job.RECIPE_KIND, "run_id": run_id, "created": True, "config_hash": h, "results_path": path,
            "name": name, "message": f"imported as run {run_id} · {name}"}


def _null(job_dir, out_dir, w, k, h):
    """The label-shuffle null's predictions, if the array job ran: copied beside the run, listed, not yet scored."""
    d = os.path.join(job_dir, "out", "null")
    if not os.path.isdir(d):
        return {"status": "not run", "n": 0, "note": "the label-shuffle null (5 full trainings) was not run: it is "
                                                     "an array job, off by default"}
    paths = []
    for fn in sorted(os.listdir(d)):
        if fn.startswith("shuffle_") and fn.endswith(".npz"):
            meta = os.path.join(d, fn[:-4] + ".json")
            if not os.path.isfile(meta) or _read(meta, fn).get("recipe_hash") != h:
                raise ImportRefused(f"{fn} in out/null was not made from this job's recipe {h}")
            dest = os.path.join(out_dir, "null")
            os.makedirs(dest, exist_ok=True)
            shutil.copyfile(os.path.join(d, fn), os.path.join(dest, fn))
            paths.append(os.path.join(dest, fn))
    return {"status": "predicted · not yet scored", "n": len(paths), "predictions_paths": paths,
            "note": "each shuffle is one full training on permuted cluster labels; scored against the blind human "
                    "labels once those exist"}


# ── the full-pool Ward ──────────────────────────────────────────────────────

def _import_ward(conn, job_dir, recipe, *, root, tree_root):
    from Working.database import runs as R
    from Working.training import full_ward as fw
    from Working.training import shape as sh
    from Working.training import shape_forest as sf
    h, meta, done = _check_hashes(job_dir, recipe)
    tdir = os.path.join(job_dir, "out", "tree")
    if not os.path.isfile(os.path.join(tdir, "tree.npz")):
        raise ImportRefused(f"the job says it finished but {tdir}/tree.npz is missing")
    tree = sh.ShapeTree.load(tdir)
    if tree.meta.get("shape_key") != recipe["shape_key"]:
        raise ImportRefused(f"the returned tree was built on shape vectors {tree.meta.get('shape_key')}, the job's are "
                            f"{recipe['shape_key']}")
    if tree.meta.get("sample") is not None or len(tree.leaf_rows) != int(recipe["n_train"]):
        raise ImportRefused(f"the returned tree has {len(tree.leaf_rows):,} leaves (sample {tree.meta.get('sample')}); "
                            f"the job asked for every one of {int(recipe['n_train']):,} training windows")
    pool_key = recipe.get("pool_key")
    if pool_key:
        fz = sf.frozen_for(conn, pool_key)
        if fz is not None:
            raise ImportRefused(f"run {fz['run_id']} already has a test score on this pool at k = {fz['k']}: a new tree "
                                "changes every cluster, so it is refused like any changed cut. Make a new pool to use it.")
    if tree_root is None:
        import Adapters.catalogue_shape_cluster as csc
        tree_root = csc.RESULTS_DIR
    key = fw.full_tree_key(recipe["shape_key"], int(recipe["seed"]))
    dest = os.path.join(str(tree_root), key)
    old = _existing(conn, h)
    if old is not None and os.path.isfile(os.path.join(dest, "tree.npz")):
        return {"kind": fw.RECIPE_KIND, "run_id": old, "created": False, "config_hash": h, "tree_dir": dest,
                "name": None, "message": f"already imported as run {old}"}
    os.makedirs(dest, exist_ok=True)
    tree.meta = {**tree.meta, "key": key, "imported_from": job_dir, "imported_at": _now(), "where": "HPC",
                 "recipe_hash": h}
    tree.save(dest)
    config_id, _h = R.get_or_create_config(conn, recipe)
    prow = _pool_row(conn, pool_key) if pool_key else None
    rec_id, n_samples = (_run_recording(conn, prow["id"]) if prow is not None
                         else _run_recording(conn, -1))
    name = f"Ward · every training window ({int(recipe['n_train']):,}) · pool {pool_key or '?'}"
    run_id = R.insert_run(conn, config_id, rec_id, 0, n_samples, status="running", name=name)
    R.insert_artifact(conn, run_id, "other", os.path.join(dest, "tree.npz"))
    conn.execute("UPDATE runs SET status = 'completed', finished_at = ?, duration_s = ?, step_timings_json = ? "
                 "WHERE id = ?", (_now(), float(done.get("seconds") or 0.0), json.dumps({"ward": done.get("seconds")}),
                                  run_id))
    conn.commit()
    return {"kind": fw.RECIPE_KIND, "run_id": run_id, "created": True, "config_hash": h, "tree_dir": dest,
            "name": name, "message": (f"imported as run {run_id}: the tree over every training window is kept under "
                                      f"{key} — set the Shape clustering block's sample to 0 (every training window) "
                                      "and re-run; the cut and the mapping must be chosen again on the new tree")}
