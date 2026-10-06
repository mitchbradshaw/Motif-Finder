"""
shape_cnn.py
============
fixup-ai: arm **B.2 cluster labels · trace shape** with a CNN in place of the
forest (RQ1 version 2, the researcher 2026-10-05: "forest first, CNN second —
but the CNN path is wanted now, as a SLURM script the site writes").

Only the model differs from `shape_forest`: the same pool, the same Trace shape
options (so the same windows and re-cut bounds), the same kept tree, the same
frozen cut k and interesting / not mapping, the same diagnostic hold-back (the
forest's seed → the same 20 % of training windows), the same exams, and results
written in the forest's JSON + parquet shape, so Models › Results and `AH`'s
blind queue read a CNN run with no second reader.

The images (the researcher, 2026-10-06: "windows should be fed into the
model-trainer as their original raw signal")
-------------------------------------------------------------------------------
Each window's RAW samples at its re-cut bounds — n = 60, 600 or 1,800 samples
at 1 Hz for the 1-, 10- and 30-minute scales — give the n × n image of the
encoding, the very encoding the manual-label CNNs were trained on
(`Working.Catalogue.cnn.apply_cnn._window_to_pil`); that IMAGE is resized to the
network's 224 × 224 input by the network's own transform. The signal is never
resampled; detrend and normalise stay with the clustering. Fusion first (GASF,
GADF and recurrence as the three colour channels); GASF, GADF and recurrence
alone are the other three encodings.

The split between here and the cluster
--------------------------------------
* here (`export_job`, needs the database): the pool, its kept tree, the cut →
  a job directory holding every window's raw bounds, role and cluster, the
  recipe (its short hash is the run's identity) and the list of channel arrays
  the job reads;
* there (`cnn_job.run_job`, no database): encode (cached), train, predict;
* here again (`hpc_import.import_results`): validate against the recipe hash and
  record the run — the function the CLI's `import-results` and Jobs › Manifest
  inbox call.

The local smoke (`run_local_smoke`) is the same round trip on a few hundred
windows, one epoch, this CPU. Headless: no UI or web library; torch only when a
job runs (CLAUDE.md rule 1).
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import time

import numpy as np

from Working.training.cnn_job import (  # noqa: F401  (re-exported: the cluster side's names)
    ENCODINGS, JOB_FILE, RECIPE_FILE, RECIPE_KIND, WINDOWS_FILE, encode_window, job_status, load_windows,
    null_status, run_job, run_null, save_windows, windows_key)

DEFAULT_ENCODING = "fusion"
#: the network and its training (mine to state; the forest's are its own): the manual-label CNNs' EfficientNet-B0
#: with ImageNet weights, their 224-pixel input and learning rate, class weights as the forest's `balanced`
CNN_DEFAULTS = {"backbone": "efficientnet_b0", "pretrained": True, "img_size": 224, "epochs": 12, "batch_size": 128,
                "lr": 1e-3, "weight_decay": 0.0, "schedule": "cosine", "class_weight": "balanced",
                "augmentation": "none", "random_state": 42, "refit": True}
CNN_KEYS = set(CNN_DEFAULTS)
#: the local smoke: a few hundred windows, one epoch, this CPU
SMOKE_DEFAULTS = {"n_train": 240, "n_predict": 120, "epochs": 1, "batch_size": 16}
NULL_SHUFFLES = 5
#: assumed A100 training throughput for EfficientNet-B0 at 224 px (images / s), used until a cluster run has been
#: imported and measured its own (`measured.train_img_per_s` in done.json) — an ASSUMPTION, said so on the page
ASSUMED_GPU_IMG_PER_S = 400.0
ASSUMED_GPU_PREDICT_FACTOR = 3.0
CLUSTER_ENCODE_WORKERS = 8
AUGMENTATION_NOTE = ("no augmentation: a flip of one axis of a Gramian or recurrence image is not the image of any "
                     "signal (only flipping both axes is time reversal), and colour jitter would move the fusion's "
                     "three encodings apart")


def _now():
    return _dt.datetime.now().isoformat(timespec="seconds")


def images_rule(encoding, img_size=224):
    rec = (" (the recurrence image is (n − 8) × (n − 8) — embedding m = 3, τ = 4 samples — resized to n × n inside "
           "fusion)" if encoding in ("fusion", "recurrence") else "")
    return (f"each window's RAW samples at its re-cut bounds (n = 60, 600 or 1,800 samples for the 1-, 10- and "
            f"30-minute scales) → the n × n {encoding} image of those n samples{rec} → resized as an IMAGE to the "
            f"network's {int(img_size)} × {int(img_size)} input by its own transform (bilinear, antialiased). The "
            "signal is never resampled; each pixel spans n / "
            f"{int(img_size)} samples, so the scales differ in detail per pixel, not in what is drawn. The same "
            "encoding the manual-label CNNs were trained on (Working.Catalogue.cnn.apply_cnn).")


def model_label(recipe):
    c = recipe.get("cnn") or {}
    s = (f"CNN · {recipe['inputs']['encoding']} · EfficientNet-B0 · {c.get('epochs')} epoch"
         f"{'' if c.get('epochs') == 1 else 's'}")
    return s + (" · smoke" if recipe.get("smoke") else "")


def make_recipe(pool_ref, template, *, encoding=DEFAULT_ENCODING, cnn=None, smoke=None):
    """The B.2 CNN recipe: the forest's pool, template, shape, cluster, arm and exams; the CNN in place of the forest."""
    from Working.training import shape_forest as sf
    if encoding not in ENCODINGS:
        raise ValueError(f"encoding {encoding!r}: one of {', '.join(ENCODINGS)} (fusion first)")
    base = sf.make_recipe(pool_ref, template)            # refuses an unmapped cut, as the forest does
    bad = set(cnn or {}) - CNN_KEYS
    if bad:
        raise ValueError(f"unknown CNN setting(s) {sorted(bad)}: one of {sorted(CNN_KEYS)}")
    cfg = {**CNN_DEFAULTS, **(cnn or {})}
    cfg = {k: (bool(v) if isinstance(CNN_DEFAULTS[k], bool) else int(v) if isinstance(CNN_DEFAULTS[k], int)
               else float(v) if isinstance(CNN_DEFAULTS[k], float) else v) for k, v in cfg.items()}
    sm = None
    if smoke is not None:          # {} = the smoke at its defaults
        sm = {**SMOKE_DEFAULTS, **smoke}
        sm = {k: int(v) for k, v in sm.items()}
        cfg["epochs"] = sm["epochs"]
        cfg["batch_size"] = min(cfg["batch_size"], sm["batch_size"])
    return {
        "kind": RECIPE_KIND,
        "pool": base["pool"], "template": base["template"], "shape": base["shape"], "cluster": base["cluster"],
        "arm": base["arm"],
        "inputs": {"features": "images of the raw samples at the re-cut bounds", "encoding": encoding,
                   "rule": sf.INPUTS_RULE, "images": images_rule(encoding, cfg["img_size"])},
        "cnn": cfg,
        "training_rule": ("cross-entropy with balanced class weights over the k clusters, Adam, cosine schedule, "
                          f"a fixed number of epochs (no early stopping: the hold-back stays a diagnostic); "
                          f"{AUGMENTATION_NOTE}; the final model is refitted on every training window, as the "
                          "forest's is" if cfg["refit"] else "the final model is the diagnostic model (80 %)"),
        "diagnostic": {"holdback_frac": float(base["diagnostic"]["holdback_frac"]), "seed": int(cfg["random_state"]),
                       "rule": "the forest's: a seeded share of the training windows held back (the same windows)"},
        "exams": base["exams"],
        "smoke": sm,
    }


# ── the job directory ───────────────────────────────────────────────────────

def _holdback(n_train, frac, seed):
    """The forest's diagnostic hold-back, drawn exactly as `shape_forest.run_forest` draws it."""
    rng = np.random.default_rng(int(seed))
    held = np.zeros(n_train, dtype=bool)
    if n_train:
        held[rng.choice(n_train, size=max(1, int(round(frac * n_train))), replace=False)] = True
    return held


def _dir_bytes(d, skip=("cache", "out")):
    tot = 0
    for root, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x not in skip]
        tot += sum(os.path.getsize(os.path.join(root, f)) for f in files)
    return tot


def export_job(conn, recipe, job_dir, *, tree_root, progress=None):
    """Write the job directory the cluster (or the local smoke) runs: the windows of the pool after Trace shape
    with their raw bounds, role and cluster at the cut; the recipe with the windows' key; the channel arrays it
    reads. Returns what was written, what must be copied and how big it is."""
    from Working.hpc.job_export import repo_relative
    from Working.recipes import short_hash
    from Working.training import shape as sh
    from Working.training import shape_forest as sf
    recipe = json.loads(json.dumps({k: v for k, v in recipe.items() if k != "bundle"}))
    k = int(recipe["arm"]["k"])
    if progress:
        progress(0, 3, "the pool, its windows and their re-cut bounds")
    _row, _pool, shapes, tree, tree_dir = sf._load(conn, recipe, tree_root)
    lab = sh.labels_at(tree, shapes, k)
    f = shapes.frame.reset_index(drop=True)
    roles = f["role"].to_numpy().astype(str)
    train = np.flatnonzero(roles == "train")
    dg = recipe["diagnostic"]
    held_all = np.zeros(len(f), dtype=bool)
    held_all[train[_holdback(len(train), dg["holdback_frac"], dg["seed"])]] = True
    sm = recipe.get("smoke")
    if sm:
        rng = np.random.default_rng(int(dg["seed"]))
        tr = np.sort(rng.choice(train, size=min(int(sm["n_train"]), len(train)), replace=False))
        held = np.zeros(len(f), dtype=bool)
        held[tr[_holdback(len(tr), dg["holdback_frac"], dg["seed"])]] = True
        pred = []
        for role in ("test", "exam"):
            r = np.flatnonzero(roles == role)
            pred.append(np.sort(rng.choice(r, size=min(int(sm["n_predict"]), len(r)), replace=False)))
        rows = np.sort(np.concatenate([tr, *pred]))
    else:
        held = held_all
        rows = np.arange(len(f))
    fr = f.iloc[rows]
    rids = fr["recording_id"].to_numpy().astype(np.int64)
    uniq = sorted(set(int(r) for r in rids))
    chans, cidx = [], {}
    for rid in uniq:
        r = conn.execute("SELECT id, source_file, channel, npy_path, n_samples FROM recordings WHERE id = ?",
                         (rid,)).fetchone()
        p = str(r["npy_path"])
        local = p if os.path.isabs(p) else os.path.abspath(p)
        cidx[rid] = len(chans)
        chans.append({"recording_id": rid, "source_file": r["source_file"], "channel": int(r["channel"]),
                      "path": repo_relative(local) if os.path.isabs(p) else p.replace(os.sep, "/"),
                      "n_samples": int(r["n_samples"]), "bytes": int(os.path.getsize(local))})
    labels = np.where(roles[rows] == "train", lab.labels[rows], -1).astype(np.int64)
    w = {"row": rows.astype(np.int64), "recording_id": rids, "source_file": fr["source_file"].to_numpy().astype(str),
         "channel": fr["channel"].to_numpy().astype(np.int64), "start": fr["start"].to_numpy().astype(np.int64),
         "orig_start": (fr["orig_start"] if "orig_start" in fr.columns else fr["start"]).to_numpy().astype(np.int64),
         "length": fr["length"].to_numpy().astype(np.int64), "fs": fr["fs"].to_numpy().astype(np.float64),
         "scale_min": fr["scale_min"].to_numpy().astype(np.float64), "role": roles[rows],
         "label": labels, "holdback": held[rows], "chan": np.array([cidx[int(r)] for r in rids], dtype=np.int64)}
    interesting = sorted(int(c) for c, v in recipe["arm"]["mapping"]["clusters"].items() if v.get("class") == "interesting")
    r_roles = roles[rows]
    by_scale = {f"{float(s):g}": int(n) for s, n in zip(*np.unique(w["scale_min"], return_counts=True))}
    recipe["bundle"] = {"windows_key": windows_key(w), "n_windows": int(len(rows)),
                        "n_train": int((r_roles == "train").sum()), "n_predict": int((r_roles != "train").sum()),
                        "by_scale": by_scale, "tree_key": os.path.basename(str(tree_dir).rstrip("/\\")),
                        "shape_key": shapes.key, "n_clustered": int(lab.n_clustered),
                        "n_assigned": int(lab.n_assigned), "classes": list(range(1, k + 1)),
                        "interesting": interesting, "channels": [c["path"] for c in chans]}
    h = short_hash(recipe)
    os.makedirs(job_dir, exist_ok=True)
    if progress:
        progress(2, 3, f"writing the job directory ({len(rows):,} windows)")
    save_windows(os.path.join(job_dir, WINDOWS_FILE), w)
    with open(os.path.join(job_dir, RECIPE_FILE), "w", encoding="utf-8") as fh:
        json.dump(recipe, fh, indent=1)
    meta = {"kind": RECIPE_KIND, "recipe_hash": h, "created_at": _now(), "encoding": recipe["inputs"]["encoding"],
            "model": model_label(recipe), "channels": chans, "n_windows": int(len(rows)),
            "n_train": recipe["bundle"]["n_train"], "n_predict": recipe["bundle"]["n_predict"], "by_scale": by_scale,
            "smoke": recipe.get("smoke"), "pool": recipe["pool"], "k": k,
            "returns": ("copy <job>/out/ back to the same place, then: python -m Working.training import-results <job>")}
    with open(os.path.join(job_dir, JOB_FILE), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)
    job_bytes = _dir_bytes(job_dir)
    copy = [{"what": "job directory", "path": repo_relative(os.path.abspath(job_dir)), "bytes": int(job_bytes),
             "note": "recipe.json, job.json, windows.npz (the windows, their raw bounds and their cluster at the cut)"
                     " and the script(s)"}]
    copy += [{"what": "channel array", "path": c["path"], "bytes": c["bytes"],
              "note": f"{c['source_file']} channel {c['channel']} ({c['n_samples']:,} samples)"} for c in chans]
    return {"job_dir": os.path.abspath(job_dir), "recipe": recipe, "recipe_hash": h, "copy": copy,
            "total_bytes": int(sum(c["bytes"] for c in copy)), "n_windows": int(len(rows)),
            "n_train": recipe["bundle"]["n_train"], "n_predict": recipe["bundle"]["n_predict"],
            "by_scale": by_scale, "tree_key": recipe["bundle"]["tree_key"], "channels": chans}


# ── the estimate ────────────────────────────────────────────────────────────

def latest_measurements(conn, encoding):
    """The newest measured encode / train rates of a CNN run with this encoding: the local smoke's (this CPU) and,
    once one has been imported, a cluster run's (its GPU)."""
    from Working.training import shape_forest as sf
    out = {"local": None, "cluster": None}
    for r in sf._runs(conn, status="completed"):
        rec = json.loads(r["config_json"])
        if rec.get("kind") != RECIPE_KIND or (rec.get("inputs") or {}).get("encoding") != encoding:
            continue
        _p, res = sf._results_of(conn, r["id"])
        m = (res or {}).get("measured") or {}
        if not m:
            continue
        slot = "cluster" if str(m.get("device", "")).startswith("cuda") else "local"
        if out[slot] is None:
            out[slot] = {**m, "run_id": int(r["id"])}
    return out


def image_bytes(n, encoding, img_size=224):
    return int(n) * int(img_size) ** 2 * (3 if encoding == "fusion" else 1)


def estimate(job, recipe, measured):
    """Seconds for the cluster job, in parts, LABELLED as an estimate: encoding from this machine's measured
    per-window times (per scale) spread over the cluster's encode workers; epochs from a cluster run's measured
    images / s, else an assumed A100 rate (said so)."""
    cfg = recipe["cnn"]
    loc, clu = (measured or {}).get("local"), (measured or {}).get("cluster")
    ms = (clu or {}).get("encode_ms_by_scale") or (loc or {}).get("encode_ms_by_scale")
    by_scale = job["by_scale"]
    assumptions = []
    if ms:
        # windows of a scale never measured take the slowest measured rate (n² grows with the scale)
        worst = max(ms.values())
        enc_cpu = sum(n * (ms.get(s, worst) / 1000.0) for s, n in by_scale.items())
        enc_s = enc_cpu / CLUSTER_ENCODE_WORKERS
        assumptions.append(f"encoding: this machine's measured time per window ({', '.join(f'{s} min {v:.0f} ms' for s, v in sorted(ms.items(), key=lambda kv: float(kv[0])))}) "
                           f"over {CLUSTER_ENCODE_WORKERS} cluster CPUs, assumed as fast per core")
    else:
        enc_cpu = enc_s = None
        assumptions.append("encoding: not measured yet — run the local smoke first")
    n_train = int(job["n_train"])
    frac = float(recipe["diagnostic"]["holdback_frac"])
    epochs = int(cfg["epochs"])
    fit_imgs = epochs * (n_train * (1 - frac) + (n_train if cfg.get("refit", True) else 0))
    eval_imgs = epochs * n_train * frac + int(job["n_predict"])
    if clu and clu.get("train_img_per_s"):
        rate = float(clu["train_img_per_s"])
        assumptions.append(f"training: {rate:.0f} images / s, measured by cluster run {clu['run_id']}")
    else:
        rate = ASSUMED_GPU_IMG_PER_S
        assumptions.append(f"training: {rate:.0f} images / s on an A100 — ASSUMED, not measured (the first cluster "
                           "run's log prints its own rate; once imported, this estimate uses it)")
    train_s = fit_imgs / rate
    pred_s = eval_imgs / (rate * ASSUMED_GPU_PREDICT_FACTOR)
    cpu_rate = (loc or {}).get("train_img_per_s")
    total = None if enc_s is None else enc_s + train_s + pred_s
    return {"label": "estimate (not a measurement of the cluster job)", "seconds": total,
            "parts": {"encode_s": enc_s, "encode_cpu_s": enc_cpu, "train_s": train_s, "predict_s": pred_s},
            "images": {"fit": int(fit_imgs), "eval": int(eval_imgs), "epochs": epochs},
            "cache_bytes": image_bytes(job["n_windows"], recipe["inputs"]["encoding"], cfg["img_size"]),
            "this_cpu_train_s": (fit_imgs / float(cpu_rate)) if cpu_rate else None,
            "assumptions": assumptions, "measured_from": {"local": (loc or {}).get("run_id"),
                                                          "cluster": (clu or {}).get("run_id")}}


# ── the local smoke: the same round trip, here ──────────────────────────────

def run_local_smoke(conn, recipe, *, job_root, root, tree_root, progress=None, cancel=None):
    """Export a smoke job, run it on this CPU, import it through `hpc_import.import_results` — the cluster's
    round trip on a few hundred windows. Returns the import's answer plus the timings measured."""
    from Working.recipes import short_hash
    from Working.training import hpc_import
    if not recipe.get("smoke"):
        raise ValueError("the local smoke needs a smoke recipe (make_recipe(..., smoke={...}))")
    t0 = time.time()
    name = f"b2cnn_{recipe['inputs']['encoding']}_smoke_{short_hash(recipe)}"
    job_dir = os.path.join(str(job_root), name)
    job = export_job(conn, recipe, job_dir, tree_root=tree_root, progress=progress)
    t_export = time.time() - t0
    out = run_job(job["job_dir"], device="cpu", workers=0, progress=progress, cancel=cancel)
    if out["status"] != "complete":
        raise RuntimeError(f"the local smoke did not finish: {out}")
    got = hpc_import.import_results(conn, job["job_dir"], root=root, tree_root=tree_root, where="local smoke")
    with open(os.path.join(job["job_dir"], "out", "done.json"), encoding="utf-8") as fh:
        done = json.load(fh)
    return {**got, "job_dir": job["job_dir"], "export_s": round(t_export, 2), "timings": done.get("timings"),
            "measured": done.get("measured"), "total_s": round(time.time() - t0, 2), "n_windows": job["n_windows"]}
