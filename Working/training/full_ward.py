"""
full_ward.py
============
fixup-ai: Ward over EVERY training window of a pool, on the cluster (the
researcher, 2026-10-05: "Ward on a 20,000-window sample locally; a SLURM script
for Ward over every window as well").

The local tree (`AG`, `Working.training.shape.cluster_shapes`) is built on a
seeded 20,000-window sample because Ward's distances grow with the square of
the window count. This module writes a job directory holding the pool's shape
vectors (`shapes.npz`, exactly the Trace shape step's file), runs the SAME
function with `sample=None` on the cluster, and writes the SAME tree artifact
(`tree.npz` + `manifest.json`). `hpc_import.import_results` puts it under the key
the Shape clustering block computes for "sample = every training window"
(`shape.tree_key(shapes, None, seed)`), so the block re-uses it instead of
building it here.

Memory (`memory_estimate`): the condensed distances of n windows are
n(n − 1)/2 float64 values — 8 bytes each, about 4 n² bytes (14.4 GB at 60,000) —
and scipy's Ward works on a copy of them, so the peak holds TWO copies (AG
measured 3.07 GB at 20,000 against 3.2 GB predicted), plus the vectors and the
interpreter. Headless: no UI or web library is imported here.
"""

from __future__ import annotations

import datetime as _dt
import json
import math
import os
import shutil
import time

RECIPE_KIND = "shape_tree_full"
#: AG measured the Library's Ward on 20,000 windows in 57.4 s on this machine (report part 1, §1)
MEASURED_N, MEASURED_S = 20_000, 57.4
OVERHEAD_BYTES = int(1.5 * 2 ** 30)
MARGIN = 1.2


def _now():
    return _dt.datetime.now().isoformat(timespec="seconds")


def memory_estimate(n, resample_length=256):
    n = int(n)
    d = 8 * n * (n - 1) // 2
    vec = n * int(resample_length) * (4 + 8)          # float32 on disk, float64 in the distance call
    peak = 2 * d + vec + OVERHEAD_BYTES
    req = int(math.ceil(peak * MARGIN / 2 ** 30))
    return {"n": n, "bytes_distances": d, "bytes_peak": peak, "request_gb": req,
            "rule": (f"2 x 8 x n(n-1)/2 bytes (the condensed float64 distances and scipy's working copy) + the "
                     f"vectors (n x {int(resample_length)} x 12 bytes) + 1.5 GB for Python, x {MARGIN} -> "
                     f"{req} GB for n = {n:,}")}


def seconds_estimate(n):
    """Ward is quadratic in n: scaled from AG's measurement here (an estimate; the cluster's CPUs differ)."""
    return MEASURED_S * (int(n) / MEASURED_N) ** 2


def full_tree_key(shape_key, seed):
    """`shape.tree_key(shapes, None, seed)` from the shape key alone."""
    from Working.training import shape as sh

    class _K:
        key = str(shape_key)
    return sh.tree_key(_K(), None, int(seed))


def export_job(shapes_path, job_dir, *, seed=0):
    """Copy the Trace shape vectors into a job directory with the recipe the cluster runs."""
    from Working.hpc.job_export import repo_relative
    from Working.recipes import short_hash
    from Working.training import shape as sh
    shapes = sh.ShapeSet.load(str(shapes_path))
    roles = shapes.frame["role"].astype(str).to_numpy()
    n = int((roles == "train").sum())
    pool_key = (str(shapes.frame["pool_key"].iloc[0]) if "pool_key" in shapes.frame.columns and len(shapes.frame)
                else None)
    os.makedirs(job_dir, exist_ok=True)
    src_dir = os.path.dirname(os.path.abspath(str(shapes_path)))
    shutil.copyfile(str(shapes_path), os.path.join(job_dir, "shapes.npz"))
    if os.path.isfile(os.path.join(src_dir, "manifest.json")):
        shutil.copyfile(os.path.join(src_dir, "manifest.json"), os.path.join(job_dir, "manifest.json"))
    mem = memory_estimate(n, shapes.vectors.shape[1])
    recipe = {"kind": RECIPE_KIND, "method": "ward", "library_method": "Working.library.grouping.methods.ward",
              "shape_key": shapes.key, "pool_key": pool_key, "seed": int(seed), "sample": None, "n_train": n,
              "resample_length": int(shapes.vectors.shape[1]),
              "rule": ("the Library's Ward (Working.training.shape.cluster_shapes with sample = None) over EVERY "
                       "training window of the pool, on the Trace shape vectors in shapes.npz; the same tree artifact")}
    h = short_hash(recipe)
    with open(os.path.join(job_dir, "recipe.json"), "w", encoding="utf-8") as fh:
        json.dump(recipe, fh, indent=1)
    meta = {"kind": RECIPE_KIND, "recipe_hash": h, "created_at": _now(), "n": n, "memory": mem,
            "seconds_estimate": seconds_estimate(n), "pool_key": pool_key,
            "returns": "copy <job>/out/ back, then: python -m Working.training import-results <job>"}
    with open(os.path.join(job_dir, "job.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)
    size = sum(os.path.getsize(os.path.join(job_dir, f)) for f in os.listdir(job_dir)
               if os.path.isfile(os.path.join(job_dir, f)))
    copy = [{"what": "job directory", "path": repo_relative(os.path.abspath(job_dir)), "bytes": int(size),
             "note": "shapes.npz (the pool's Trace shape vectors), its manifest, recipe.json, job.json, the script"}]
    return {"job_dir": os.path.abspath(job_dir), "recipe": recipe, "recipe_hash": h, "n": n, "memory": mem,
            "seconds_estimate": seconds_estimate(n), "copy": copy, "total_bytes": int(size), "pool_key": pool_key}


def job_status(job_dir):
    """(code, text): 0 complete, 1 not yet, 3 unreadable."""
    try:
        from Working.recipes import short_hash
        with open(os.path.join(job_dir, "recipe.json"), encoding="utf-8") as fh:
            h = short_hash(json.load(fh))
    except Exception as e:
        return 3, f"the job at {job_dir} cannot be read: {e}"
    p = os.path.join(job_dir, "out", "done.json")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        return (0, f"complete · {d.get('seconds')} s") if d.get("recipe_hash") == h else (3, "done.json is another job's")
    return 1, "not yet run"


def run_job(job_dir, progress=None):
    """On the cluster: the same Ward, every training window, the same tree artifact in out/tree/."""
    from Working.recipes import short_hash
    from Working.training import shape as sh
    if job_status(job_dir)[0] == 0:
        return {"status": "complete", "skipped": True}
    with open(os.path.join(job_dir, "recipe.json"), encoding="utf-8") as fh:
        recipe = json.load(fh)
    with open(os.path.join(job_dir, "job.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    h = short_hash(recipe)
    if meta.get("recipe_hash") != h:
        raise ValueError(f"recipe.json was changed after the job was written ({h} vs {meta.get('recipe_hash')})")
    shapes = sh.ShapeSet.load(os.path.join(job_dir, "shapes.npz"))
    if shapes.key != recipe["shape_key"]:
        raise ValueError(f"shapes.npz is not the job's shape vectors ({shapes.key} vs {recipe['shape_key']})")
    if progress:
        progress(0, 1, f"Ward over {recipe['n_train']:,} training windows")
    t0 = time.time()
    tree = sh.cluster_shapes(shapes, sample=None, seed=int(recipe["seed"]))
    secs = time.time() - t0
    tree.save(os.path.join(job_dir, "out", "tree"))
    with open(os.path.join(job_dir, "out", "done.json"), "w", encoding="utf-8") as fh:
        json.dump({"status": "complete", "recipe_hash": h, "seconds": round(secs, 1), "finished_at": _now(),
                   "n_leaves": int(len(tree.leaf_rows)), "peak_rss_mb": tree.meta.get("peak_rss_mb")}, fh, indent=1)
    return {"status": "complete", "seconds": secs}
