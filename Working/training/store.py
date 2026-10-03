"""
store.py
========
Where a paired training job leaves its trace (fixup-ab). Plain SQL, no ORM;
bulk arrays on disk, referenced by path (CLAUDE.md rules 3 and 4).

* A pooled window set is saved as ONE `window_sets` row (recording and channel
  NULL — it spans channels) with a `window_set_members` row per channel, and
  its files (`pooled_windows.npz`, `features.parquet`, `manifest.json`) under
  `<root>/<name>_v<version>/`. `recipe_hash` on the row is the set's content
  key, so a recipe naming the set can be checked against what is on disk.
* A paired run is a `configs` row (the recipe, so the job is reproducible from
  its hash), a `runs` row (status, timings, error), and `artifacts` rows: the
  results JSON (`other`) and the two fitted forests (`model`). The `runs` row
  names the first training channel's recording and its whole length: a run
  row needs one, and this job reads every channel of the set — the set row
  names them all.

Once a run on a set has a test score, the cut of arm B (k, linkage, translation)
is frozen on that set: a recipe with another cut is refused (`CutFrozen`).
Choosing the cut after seeing test scores is tuning on the test block.
"""

from __future__ import annotations

import datetime as _dt
import json
import os

from Working.database import runs as R
from Working.recipes import short_hash
from Working.training import paired as tp
from Working.training import windows as tw


class CutFrozen(ValueError):
    """A recipe would change arm B's cut on a set that already has a test score."""


def _now():
    return _dt.datetime.now().isoformat(timespec="seconds")


# ── window sets ─────────────────────────────────────────────────────────────

def save_window_set(conn, pooled, root, name, notes=None):
    """Write the pooled set's files and its `window_sets` + `window_set_members` rows."""
    top = conn.execute("SELECT MAX(version) FROM window_sets WHERE name = ?", (str(name),)).fetchone()[0]
    version = int(top or 0) + 1
    d = os.path.join(str(root), f"{name}_v{version}")
    pooled.save(d)
    meta = pooled.meta
    counts = tw.role_counts(pooled)
    split = dict(meta.get("split") or {})
    split_json = {**split, **{r: counts[r]["n"] for r in ("train", "validation", "test")},
                  "exam": counts["exam"]["n"],
                  "note": "blocked by time within each training channel; exam channels are never trained on"}
    class_counts = {c: sum(counts[r][c] for r in counts) for c in ("interesting", "not_interesting")}
    coverage = {
        "labelled_windows": int(len(pooled.table)),
        "class_counts_at_save": class_counts, "class_counts": class_counts,
        "by_role": counts,
        "by_split": {r: {"interesting": counts[r]["interesting"], "not_interesting": counts[r]["not_interesting"]}
                     for r in counts},
        "unlabelled": 0, "conflicting": 0, "artifact": 0,
        "dropped_for_overlap": sum(int(c.get("dropped_for_overlap", 0)) for c in meta["per_channel"]),
        "dropped_for_gap": sum(int(c.get("dropped_for_gap", 0)) for c in meta["per_channel"]),
        "non_overlap_rule": meta.get("non_overlap_rule"), "non_overlapping": True,
        "pool": meta.get("pool"), "stages": meta.get("stages"),
        "channels": meta.get("channels"), "exam_channels": meta.get("exam_channels"),
        "notes": notes,
    }
    cur = conn.execute(
        "INSERT INTO window_sets (name, version, path, recording_id, channel, fs, window_length, stride, gap, "
        "n_windows, split_json, spacing_json, coverage_json, labels_source, recipe_hash, created_at) "
        "VALUES (?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (str(name), version, d, float(meta.get("fs") or 1.0), int(meta["length"]), int(meta["grid"]),
         int(split.get("gap_windows", 1)) * int(meta["length"]), int(len(pooled.table)), json.dumps(split_json),
         json.dumps({"no two windows overlap": True, "gap >= one window between roles": True}),
         json.dumps(coverage, default=str),
         f"human verdicts (annotations + window verdicts) · Models › Launch · {meta['source_file']} · "
         f"{len(meta['channels'])} training + {len(meta['exam_channels'])} exam channel(s), pooled",
         pooled.key, _now()))
    ws_id = cur.lastrowid
    for c in meta["per_channel"]:
        conn.execute(
            "INSERT INTO window_set_members (window_set_id, recording_id, channel, role, n_windows, counts_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ws_id, int(c["recording_id"]), int(c["channel"]), c["kind"], int(c["n_windows"]),
             json.dumps({k: v for k, v in c.items() if k not in ("blocks",)}, default=str)))
    conn.commit()
    return ws_id


def window_set_row(conn, ref):
    """The `window_sets` row a recipe's `window_set` names: by id, else the latest version of a name."""
    ref = dict(ref or {})
    if ref.get("id") is not None:
        row = conn.execute("SELECT * FROM window_sets WHERE id = ?", (int(ref["id"]),)).fetchone()
    else:
        row = conn.execute("SELECT * FROM window_sets WHERE name = ? ORDER BY version DESC LIMIT 1",
                           (str(ref.get("name")),)).fetchone()
    if row is None:
        raise ValueError(f"no saved window set {ref}")
    return row


def load_window_set(conn, ref):
    row = window_set_row(conn, ref)
    members = conn.execute("SELECT COUNT(*) FROM window_set_members WHERE window_set_id = ?", (row["id"],)).fetchone()[0]
    if not members:
        raise ValueError(f"window set {row['name']} v{row['version']} is a one-channel set; the paired job needs a "
                         "set saved across channels (Models › Launch)")
    pooled = tw.PooledSet.load(row["path"])
    tw.refuse_held_out(pooled.meta.get("source_file"))
    return row, pooled


def members(conn, window_set_id):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM window_set_members WHERE window_set_id = ? ORDER BY role DESC, channel", (int(window_set_id),))]


# ── runs ────────────────────────────────────────────────────────────────────

def _paired_runs(conn, status=None):
    sql = ("SELECT r.*, c.config_hash, c.config_json FROM runs r JOIN configs c ON c.id = r.config_id "
           "WHERE json_extract(c.config_json, '$.kind') = 'paired_training'")
    args = []
    if status:
        sql += " AND r.status = ?"
        args.append(status)
    return conn.execute(sql + " ORDER BY r.id DESC", args).fetchall()


def _results_path(conn, run_id):
    row = conn.execute("SELECT path FROM artifacts WHERE run_id = ? AND kind = 'other' ORDER BY id LIMIT 1",
                       (int(run_id),)).fetchone()
    return row["path"] if row else None


def _read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check_cut_frozen(conn, recipe, pooled_key):
    """Refuse a recipe whose arm-B cut differs from one already scored on this set."""
    new = recipe["arms"]["B"]
    for r in _paired_runs(conn, status="completed"):
        old = json.loads(r["config_json"])
        if (old.get("window_set") or {}).get("key") != pooled_key:
            continue
        o = old["arms"]["B"]
        path = _results_path(conn, r["id"])
        scored_translation = None
        if path and os.path.isfile(path):
            scored_translation = _read(path).get("cluster", {}).get("translation")
        differs = (int(o["k"]) != int(new["k"]) or o.get("linkage", "ward") != new.get("linkage", "ward")
                   or (new.get("translation") and scored_translation
                       and dict(new["translation"]) != dict(scored_translation)))
        if differs:
            raise CutFrozen(
                f"run {r['id']} already scored this window set's test block with arm B's cut at k = {o['k']} "
                f"({o.get('linkage', 'ward')}, translation {scored_translation}). The cut is frozen once a test "
                "score exists — choosing it after seeing test scores is tuning on the test block. Keep the cut, "
                "or save a new window set and split.")


def run_and_record(conn, recipe, root, progress=None, cancel=None):
    """Load the set the recipe names, refuse a changed cut, run, and record."""
    row, pooled = load_window_set(conn, recipe["window_set"])
    want = (recipe.get("window_set") or {}).get("key")
    if want and want != row["recipe_hash"]:
        raise ValueError(f"the recipe names window set key {want}, but {row['name']} v{row['version']} has key "
                         f"{row['recipe_hash']}")
    if want and want != pooled.key:
        raise ValueError(f"the files of {row['name']} v{row['version']} no longer match key {want}")
    check_cut_frozen(conn, recipe, pooled.key)

    config_id, h = R.get_or_create_config(conn, recipe)
    first = [c for c in pooled.meta["per_channel"] if c["kind"] == "train"][0]
    run_id = R.insert_run(conn, config_id, int(first["recording_id"]), 0, int(first["n_samples"]),
                          status="running", name=f"paired · {row['name']} v{row['version']} · k={recipe['arms']['B']['k']}")
    out_dir = os.path.join(str(root), f"paired_{h}_run{run_id}")
    t0 = _dt.datetime.now()
    try:
        results = tp.run_paired(recipe, pooled, progress=progress, cancel=cancel, model_dir=out_dir)
        if recipe.get("reference", {}).get("enabled"):
            from Working.training import reference
            results["reference"] = reference.score_reference(conn, pooled, results, recipe["reference"],
                                                             progress=progress, cancel=cancel)
        else:
            results["reference"] = reference_rows_off()
        results["run_id"] = run_id
        results["window_set"]["id"] = int(row["id"])
        results["window_set"]["version"] = int(row["version"])
        path = os.path.join(out_dir, "results.json")
        results = jsonable(results)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results, f, allow_nan=False)
        R.insert_artifact(conn, run_id, "other", path)
        for arm in ("A", "B"):
            R.insert_artifact(conn, run_id, "model", results["training"][arm]["model_path"])
        dur = (_dt.datetime.now() - t0).total_seconds()
        conn.execute("UPDATE runs SET status = 'completed', finished_at = ?, duration_s = ?, step_timings_json = ? "
                     "WHERE id = ?", (_now(), dur, json.dumps(results["timings"]), run_id))
        conn.commit()
    except BaseException as e:
        import traceback
        status = "failed"
        conn.execute("UPDATE runs SET status = ?, finished_at = ?, error_text = ? WHERE id = ?",
                     (status, _now(), ("Cancelled: " if isinstance(e, InterruptedError) else "") + traceback.format_exc(),
                      run_id))
        conn.commit()
        raise
    return {"run_id": run_id, "results": results, "results_path": path, "config_hash": h}


def reference_rows_off():
    return [{"name": n, "status": "not scored", "reason": "the reference line was off for this run"}
            for n in REFERENCE_MODELS]


REFERENCE_MODELS = ("catch22_rf_prelabeled", "fusion_cnn", "GASF_cnn", "GADF_cnn", "recurrence_cnn")


def list_runs(conn):
    out = []
    for r in _paired_runs(conn):
        recipe = json.loads(r["config_json"])
        path = _results_path(conn, r["id"])
        head = None
        if r["status"] == "completed" and path and os.path.isfile(path):
            res = _read(path)
            ex = res["exams"].get(tp.EXAM_I) or {}
            if ex.get("status") == "scored":
                head = {arm: ex["arms"][arm]["macro_f1"] for arm in ("A", "B")}
                head["delta"] = ex["paired"]["delta_f1"]
        out.append({"run_id": int(r["id"]), "status": r["status"], "name": r["name"], "started_at": r["started_at"],
                    "finished_at": r["finished_at"], "duration_s": r["duration_s"], "config_hash": r["config_hash"],
                    "window_set": recipe.get("window_set"), "k": recipe["arms"]["B"]["k"],
                    "error": (r["error_text"] or "").strip().splitlines()[-1] if r["error_text"] else None,
                    "macro_f1": head, "results_path": path})
    return out


def get_run(conn, run_id):
    r = conn.execute("SELECT r.*, c.config_hash, c.config_json FROM runs r JOIN configs c ON c.id = r.config_id "
                     "WHERE r.id = ? AND json_extract(c.config_json, '$.kind') = 'paired_training'",
                     (int(run_id),)).fetchone()
    if r is None:
        return None
    path = _results_path(conn, r["id"])
    return {"run_id": int(r["id"]), "status": r["status"], "name": r["name"], "config_hash": r["config_hash"],
            "recipe": json.loads(r["config_json"]), "started_at": r["started_at"], "finished_at": r["finished_at"],
            "duration_s": r["duration_s"], "error": r["error_text"], "results_path": path,
            "results": _read(path) if path and os.path.isfile(path) else None}


def recipe_hash_of(recipe):
    return short_hash(recipe)


def jsonable(obj):
    """numpy scalars and arrays to Python, NaN/inf to None (a browser's JSON.parse refuses NaN)."""
    import math

    import numpy as np
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [jsonable(v) for v in obj.tolist()]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return v if math.isfinite(v) else None
    return obj
