"""
rq1b_cnn_vs_minirocket.py
=========================
Round A_2, RQ1b / R4 (2026-10-26): the CNNs against MiniRocket R4, on exactly the items R4 was scored on.

In plain words
--------------
R4 (MiniRocket) was tested on 2,456 judged events, each recording held out in turn. Here the picture-reading CNNs
are shown the same events, cut the same way: the span plus a quarter of its length on each side, in mV. A CNN reads
a 600-point window drawn as a square picture, so each cut is resampled to 600 points first.

Two comparisons:

- **Quick (`score-reference`)**: the four reference CNNs already in `MODELS/` (GASF, GADF, recurrence, fusion_cnn_3)
  score every event. They were trained on M2_aug windows (their recipe is not recorded), so on M2_aug they are NOT
  out-of-sample; on every other recording they are. This is unfair to the CNNs in one way (they were trained on
  10-minute windows, not on these spans, and on another labelling) and unfair to R4 in another (M2_aug).
- **Fair (`export` → cluster `encode` / `train` → `import`)**: an EfficientNet-B0 trained on GASF, GADF and fusion
  pictures of the SAME rows (events and windows) with the SAME leave-one-recording-out folds as R4. Prepared here,
  run on rangpur by the researcher, imported back here.

The rules, each stated once
---------------------------
1. **The rows** are R4's own (`predictions.parquet` of the 20261020-2343 model): never collected afresh.
2. **The cut** is R4's (`scripts/rq1b_minirocket.py` rule 4): span + 0.25 x its length each side, clipped at the
   recording's ends, mV, gaps up to 5 % filled linearly. It is resampled to 600 points by the CNN block's own rule
   (`Working.Catalogue.cnn.window_scores.resample_window`: anti-aliased down, linear up). A flat cut is not scored.
3. **The quick scores** are `window_scores`' own path (picture, transform, softmax column 0 = "interesting"). A score
   above 0.5 is "interesting"; W4-A's lower cut, 0.1, is reported beside it.
4. **The fair model**: EfficientNet-B0 (ImageNet weights, `Working.training.cnn_job.build_model`), pictures by
   `cnn_job.encode_window` (the n x n image of the 600 points, resized to 224), 12 epochs, batch 64, Adam 1e-3 with a
   cosine schedule, balanced class weights, seed 42, no augmentation (a one-axis flip of a Gramian picture is not the
   picture of any signal), mixed precision on the GPU. Trained on every row of the other groups (events and windows,
   as R4), scored on the held-out group's events. Its cut is P(interesting) > 0.5.
5. **Comparison**: per held-out recording and pooled, AUC and balanced accuracy, with 95 % bootstrap intervals and a
   paired bootstrap of the AUC difference (R4 minus the CNN), resampling the same events for both models.

    python scripts/rq1b_cnn_vs_minirocket.py score-reference            # quick, local CPU (~10-15 min)
    python scripts/rq1b_cnn_vs_minirocket.py export                     # the fair job directory
    # on rangpur (see the job's README.txt):  sbatch encode.sh ; sbatch --dependency=afterok:<id> train.sh
    python scripts/rq1b_cnn_vs_minirocket.py import --job <job dir>     # the comparison, once out/ is back

The local subcommands read the real database read-only (recordings table only). The cluster subcommands (`encode`,
`train`, `status`) need only numpy, torch, torchvision and the repo's `Working` package.
"""

import os
import sys

if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] in ("score-reference", "export", "import"):
    for _k in ("NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ.setdefault(_k, os.environ.get("RQ1B_THREADS", "4"))

import argparse
import datetime
import hashlib
import importlib.util
import json
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def _repo_root():
    """The repo this file runs in: its own parent when it sits in scripts/, else the env `CNN_REPO` or the cwd (the
    copy that travels inside a job directory)."""
    up = os.path.dirname(HERE)
    if os.path.isdir(os.path.join(up, "Working")):
        return up
    return os.environ.get("CNN_REPO", os.getcwd())


ROOT = _repo_root()
sys.path.insert(0, ROOT)

R4_DIR = os.path.join(ROOT, "DATA", "derived", "models", "rq1b_minirocket", "20261020-2343")
LENGTH = 600
REFERENCE = (("GASF", "MODELS/GASF_cnn.pth"), ("GADF", "MODELS/GADF_cnn.pth"),
             ("recurrence", "MODELS/recurrence_cnn.pth"), ("fusion", "MODELS/fusion_cnn_3.pth"))
FAIR_ENCODINGS = ("GASF", "GADF", "fusion")
# which held-out groups the reference CNNs could have seen in training (W4-A; blind.CONTAMINATION)
IN_SAMPLE_FOR_REFERENCE = {"M2_aug_concat": "in-sample (the reference CNNs were trained on M2_aug windows)"}
OUT_OF_SAMPLE_NOTE = {
    "M2_concat": "probably out-of-sample: RQ1's blind.CONTAMINATION counts it unseen, but the training data is "
                 "unrecorded and M2_concat_fs1.mat (2 Apr 2026) predates the GASF/GADF/recurrence checkpoints "
                 "(12-13 Apr); it postdates fusion_cnn_3 (25 Mar)",
}
GROUP_ORDER = ("CO", "LM", "L_LM_Jul_26_J_raw", "Mushroom_260720_0509_4hrs_CH14", "M2_concat", "M2_aug_concat")
FAIR_CFG = {"epochs": 12, "batch_size": 64, "lr": 1e-3, "weight_decay": 0.0, "random_state": 42, "img_size": 224,
            "class_weight": "balanced", "pretrained": True, "augmentation": None, "cut": 0.5}


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _null_mod():
    return _load("rq1b_null_metrics", os.path.join(ROOT, "scripts", "rq1b_minirocket_null.py"))


# ── rows and cuts (local) ───────────────────────────────────────────────────

def r4_rows():
    return _null_mod().r4_rows(R4_DIR)


def cuts600(rows, length=LENGTH, log=print):
    """Rule 2: `(X n x length float32, ok bool)` for `rows` (R4's columns), NaN rows where a cut is unreadable or
    flat."""
    mr = _load("rq1b_minirocket_r4", os.path.join(ROOT, "scripts", "rq1b_minirocket.py"))
    from Working.Catalogue.cnn.window_scores import resample_window
    from Working.Catalogue.minirocket import MAX_GAP_FRAC
    from Working.units import read_as_mv
    conn = mr.GUARD._read_only(mr.GUARD.REAL_DB)
    try:
        recs = mr._recordings(conn)
    finally:
        conn.close()
    cache = {}
    X = np.full((len(rows), int(length)), np.nan, dtype=np.float32)
    ok = np.zeros(len(rows), dtype=bool)
    for i, r in enumerate(rows.itertuples(index=False)):
        rec = recs[int(r.recording_id)]
        factor, _ = read_as_mv(rec["units"])
        s, e = int(r.start), int(r.end)
        span = max(1, e - s)
        p = int(round(mr.PAD * span))
        a, b = max(0, s - p), min(rec["n_samples"], e + p)
        x = np.asarray(mr._array(rec, cache)[a:b], dtype=np.float64) * factor
        fin = np.isfinite(x)
        if x.size < 2 or (1.0 - fin.mean()) > MAX_GAP_FRAC:
            continue
        if not fin.all():
            k = np.arange(x.size)
            x[~fin] = np.interp(k[~fin], k[fin], x[fin])
        w = resample_window(x, int(length))
        if not np.isfinite(w).all() or w.max() == w.min():
            continue
        X[i], ok[i] = w, True
    log(f"cuts: {int(ok.sum())} of {len(rows)} readable and not flat")
    return X, ok


# ── metrics ─────────────────────────────────────────────────────────────────

def compare(ev, cnn_col, *, cnn_cut=0.5, n_boot=2000, seed=20261026):
    """Per group and pooled: R4 (decision > 0) and the CNN (P > cut), AUC and balanced accuracy with 95 % intervals,
    and the paired bootstrap of AUC(R4) - AUC(CNN). `ev` holds `label`, `group`, `channel`, `r4_decision`, `cnn_col`."""
    nm = _null_mod()
    rng = np.random.default_rng(seed)
    ev = ev[ev[cnn_col].notna()].reset_index(drop=True)
    out = {}
    if not len(ev):                                   # nothing returned yet for this model (a partial import)
        return out
    groups = [g for g in GROUP_ORDER if g in set(ev["group"])] + sorted(set(ev["group"]) - set(GROUP_ORDER))
    for name, part in [(g, ev[ev["group"] == g]) for g in groups] + [("pooled", ev)]:
        y = part["label"].to_numpy(int)
        r4 = part["r4_decision"].to_numpy(float)
        c = part[cnn_col].to_numpy(float)
        g_of = part["group"].to_numpy()
        res = {"n": int(len(y)), "interesting": int(y.sum()),
               "r4_auc": nm.auc(y, r4), "r4_balanced_accuracy": nm.balanced_accuracy(y, r4, 0.0),
               "cnn_auc": nm.auc(y, c), "cnn_balanced_accuracy": nm.balanced_accuracy(y, c, cnn_cut),
               "cnn_balanced_accuracy_at_0.1": nm.balanced_accuracy(y, c, 0.1)}
        if name == "pooled":
            idx = {k: np.flatnonzero(g_of == k) for k in sorted(set(g_of))}
        else:
            idx = {name: np.arange(len(y))}
        dA, aR, aC, bR, bC = [], [], [], [], []
        for _b in range(n_boot):
            ix = np.concatenate([v[rng.integers(0, len(v), len(v))] for v in idx.values()])
            if len(set(y[ix].tolist())) < 2:
                continue
            ar, ac = nm.auc(y[ix], r4[ix]), nm.auc(y[ix], c[ix])
            aR.append(ar), aC.append(ac), dA.append(ar - ac)
            bR.append(nm.balanced_accuracy(y[ix], r4[ix], 0.0)), bC.append(nm.balanced_accuracy(y[ix], c[ix], cnn_cut))
        if dA:
            res.update({"r4_auc_ci": nm._pct(aR), "cnn_auc_ci": nm._pct(aC), "r4_ba_ci": nm._pct(bR),
                        "cnn_ba_ci": nm._pct(bC), "auc_diff": res["r4_auc"] - res["cnn_auc"],
                        "auc_diff_ci": nm._pct(dA), "auc_diff_share_le_0": float(np.mean(np.asarray(dA) <= 0))})
        out[name] = res
    return out


# ── quick: the reference CNNs ───────────────────────────────────────────────

def score_reference(out_dir, *, models=REFERENCE, batch_size=32, threads=4, log=print):
    import pandas as pd
    import torch
    from Working.Catalogue.cnn.cnn_rangapur import get_transforms
    from Working.Catalogue.cnn.window_scores import load_scorer, predict, window_image
    torch.set_num_threads(int(threads))
    os.makedirs(out_dir, exist_ok=True)
    rows = r4_rows()
    ev = rows[rows["kind"] == "event"].reset_index(drop=True)
    order = {g: i for i, g in enumerate(GROUP_ORDER)}
    ev = ev.iloc[np.argsort([order.get(g, 99) for g in ev["group"]], kind="stable")].reset_index(drop=True)
    X, ok = cuts600(ev, log=log)
    path = os.path.join(out_dir, "reference_scores.parquet")
    scores = pd.read_parquet(path) if os.path.exists(path) else ev[["ref", "group", "channel", "label",
                                                                    "r4_decision"]].copy()
    timing = {}
    for image_type, mpath in models:
        col = f"p_{image_type}"
        if col in scores and scores[col].notna().sum() == ok.sum():
            log(f"{image_type}: already scored")
            continue
        model, _ = load_scorer(os.path.join(ROOT, mpath), image_type, 0, torch.device("cpu"))
        transform = get_transforms(224, is_train=False, is_rgb=(image_type == "fusion"))
        p = np.full(len(ev), np.nan)
        todo = np.flatnonzero(ok)
        t0 = time.perf_counter()
        for b in range(0, len(todo), batch_size):
            chunk = todo[b:b + batch_size]
            batch = [transform(window_image(X[i], image_type, 224, LENGTH)) for i in chunk]
            p[chunk] = predict(model, batch, 0)
            del batch
        secs = time.perf_counter() - t0
        timing[image_type] = {"seconds": round(secs, 1), "ms_per_event": round(1000 * secs / max(1, len(todo)), 1)}
        scores[col] = p
        scores.to_parquet(path, index=False)
        log(f"{image_type}: {len(todo)} events in {secs:.0f} s ({timing[image_type]['ms_per_event']} ms each)")
        del model
    res = {"created_at": _now(), "rows": "R4 20261020-2343 events (predictions.parquet)", "n_events": int(len(ev)),
           "n_scored": int(ok.sum()), "cut_rule": "span + 0.25 x span each side, mV, 600 points (window_scores rule)",
           "timing": timing, "flags": {g: IN_SAMPLE_FOR_REFERENCE.get(g, OUT_OF_SAMPLE_NOTE.get(
               g, "out-of-sample (recording postdates the checkpoints)")) for g in sorted(set(ev["group"]))},
           "models": {}}
    for image_type, mpath in models:
        res["models"][f"{image_type} ({os.path.basename(mpath)})"] = compare(scores, f"p_{image_type}")
    with open(os.path.join(out_dir, "reference_comparison.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    return res


# ── fair: the job directory (local) ─────────────────────────────────────────

def export(job_dir, *, log=print):
    import pandas as pd
    nm = _null_mod()
    rows = r4_rows()
    X, ok = cuts600(rows, log=log)
    folds = nm.folds_of(rows)
    os.makedirs(os.path.join(job_dir, "out"), exist_ok=True)
    os.makedirs(os.path.join(job_dir, "logs"), exist_ok=True)
    fold_arr = []
    for g, tr, te in folds:
        fold_arr.append({"group": g, "train": [int(i) for i in tr if ok[i]], "test": [int(i) for i in te if ok[i]]})
    np.savez_compressed(os.path.join(job_dir, "inputs.npz"), X=X, ok=ok, label=rows["label"].to_numpy(np.int8),
                        kind=rows["kind"].to_numpy(str), group=rows["group"].to_numpy(str),
                        ref=rows["ref"].to_numpy(str))
    tasks = [(enc, k) for enc in FAIR_ENCODINGS for k in range(len(fold_arr))]
    digest = hashlib.sha1(open(os.path.join(job_dir, "inputs.npz"), "rb").read()).hexdigest()
    job = {"kind": "rq1b_cnn_loro", "created_at": _now(), "inputs_sha1": digest, "n_rows": int(len(rows)),
           "n_readable": int(ok.sum()), "length": LENGTH, "encodings": list(FAIR_ENCODINGS), "cfg": FAIR_CFG,
           "folds": [{"group": f["group"], "n_train": len(f["train"]), "n_test": len(f["test"])} for f in fold_arr],
           "tasks": [{"task": i, "encoding": e, "fold": k, "group": fold_arr[k]["group"]} for i, (e, k) in
                     enumerate(tasks)],
           "r4": os.path.relpath(R4_DIR, ROOT).replace("\\", "/")}
    with open(os.path.join(job_dir, "job.json"), "w", encoding="utf-8") as fh:
        json.dump(job, fh, indent=1)
    with open(os.path.join(job_dir, "folds.json"), "w", encoding="utf-8") as fh:
        json.dump(fold_arr, fh)
    import shutil
    shutil.copy2(os.path.abspath(__file__), os.path.join(job_dir, "rq1b_cnn_vs_minirocket.py"))
    rel = os.path.relpath(job_dir, ROOT).replace("\\", "/")
    _write_slurm(job_dir, rel, job)
    pd.DataFrame(job["tasks"]).to_csv(os.path.join(job_dir, "tasks.csv"), index=False)
    log(f"job: {job_dir} ({len(tasks)} training tasks)")
    return job


def _estimate(job):
    n_train = sum(f["n_train"] for f in job["folds"])
    n_test = sum(f["n_test"] for f in job["folds"])
    imgs = len(job["encodings"]) * (n_train * FAIR_CFG["epochs"] + n_test)
    rate = 400.0                                                  # img/s on one A100, ASSUMED (the AI arm's)
    return {"training_images": int(imgs), "assumed_img_per_s": rate,
            "gpu_hours_compute": round(imgs / rate / 3600, 2),
            "gpu_hours_with_overhead": round(imgs / rate / 3600 + len(job["tasks"]) * 3 / 60, 2)}


def _write_slurm(job_dir, rel, job):
    est = _estimate(job)
    n_tasks = len(job["tasks"])
    head = ("source ~/miniconda3/etc/profile.d/conda.sh\nconda activate torch_env\nexport CNN_REPO=\"$PWD\"\n"
            "python -c \"import torch, torchvision, numpy, scipy, skimage, PIL; print('environment ok')\" || "
            "{ echo 'torch_env lacks a package named above'; exit 4; }\n")
    enc = f"""#!/bin/bash
# RQ1b: draw the GASF, GADF and fusion pictures of every row once (CPU). Run from the repo root.
#SBATCH --job-name=rq1b_cnn_enc
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=8
#SBATCH --time=00:20:00
#SBATCH --array=0-{len(job['encodings']) - 1}
#SBATCH --output={rel}/logs/encode_%A_%a.out
{head}ENCODINGS=({' '.join(job['encodings'])})
python {rel}/rq1b_cnn_vs_minirocket.py encode --job {rel} --encoding "${{ENCODINGS[$SLURM_ARRAY_TASK_ID]}}" --workers "$SLURM_CPUS_PER_TASK"
"""
    train = f"""#!/bin/bash
# RQ1b: one EfficientNet-B0 per (encoding, held-out recording): {n_tasks} tasks, three at a time.
# estimate: {est['training_images']:,} training images; at an ASSUMED {est['assumed_img_per_s']:.0f} img/s on an A100,
# about {est['gpu_hours_with_overhead']} GPU-hours in all (an estimate, not a measurement; each epoch prints its rate).
#SBATCH --job-name=rq1b_cnn_loro
#SBATCH --partition=a100
#SBATCH --gres=gpu:a100
#SBATCH --cpus-per-task=4
#SBATCH --time=01:00:00
#SBATCH --array=0-{n_tasks - 1}%3
#SBATCH --output={rel}/logs/train_%A_%a.out
module load cuda/12.2
{head}python {rel}/rq1b_cnn_vs_minirocket.py train --job {rel} --task "$SLURM_ARRAY_TASK_ID" --deadline-min 55
"""
    for name, text in (("encode.sh", enc), ("train.sh", train)):
        with open(os.path.join(job_dir, name), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    readme = f"""RQ1b fair CNN arm: EfficientNet-B0 on GASF, GADF and fusion pictures of R4's rows, R4's folds.
Prepared {job['created_at']}; NOT submitted. {job['n_readable']} of {job['n_rows']} rows readable; {n_tasks} training tasks.

On rangpur, from the repo root (/home/Student/s4699158/CNN), after `git pull` (needs Working/training/cnn_job.py
and Working/Catalogue/cnn/*, both on main):

  1. copy this folder:  scp -r {rel} s4699158@rangpur.compute.eait.uq.edu.au:CNN/{os.path.dirname(rel)}/
     (about {os.path.getsize(os.path.join(job_dir, 'inputs.npz')) / 1e6:.0f} MB; no channel arrays are needed: the cuts are inside inputs.npz)
  2. once, on the login node (compute nodes may have no network):
       conda activate torch_env && python -c "from torchvision.models import efficientnet_b0, EfficientNet_B0_Weights as W; efficientnet_b0(weights=W.DEFAULT)"
  3. ENC=$(sbatch --parsable {rel}/encode.sh)
  4. sbatch --dependency=afterok:$ENC {rel}/train.sh
  5. watch: squeue -u $USER ; tail {rel}/logs/train_*.out ; python {rel}/rq1b_cnn_vs_minirocket.py status --job {rel}
     A task stopped by its deadline resumes from its last epoch when the array (or that task: --array=<i>) is resubmitted.
  6. copy {rel}/out/ back into the same folder here (not cache/, which holds ~1.4 GB of pictures)
  7. here: python scripts/rq1b_cnn_vs_minirocket.py import --job {rel}

Estimate: {json.dumps(est)}
"""
    with open(os.path.join(job_dir, "README.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(readme)


# ── fair: the cluster side ──────────────────────────────────────────────────

def _inputs(job_dir):
    z = np.load(os.path.join(job_dir, "inputs.npz"), allow_pickle=False)
    return {k: z[k] for k in z.files}


def _encode_chunk(args):
    from Working.training.cnn_job import encode_window
    X, encoding, size = args
    return np.stack([encode_window(x, encoding, size) for x in X])


def encode(job_dir, encoding, *, workers=1, log=print):
    """Every readable row's picture, uint8 (n, size, size, c), as `cache/<encoding>.npy` (written once)."""
    inp = _inputs(job_dir)
    size = FAIR_CFG["img_size"]
    c = 3 if encoding == "fusion" else 1
    path = os.path.join(job_dir, "cache", f"{encoding}.npy")
    done = path + ".done"
    if os.path.exists(done):
        log(f"{encoding}: already encoded")
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    X, ok = inp["X"], inp["ok"]
    arr = np.lib.format.open_memmap(path, mode="w+", dtype=np.uint8, shape=(len(X), size, size, c))
    rows = np.flatnonzero(ok)
    chunks = [rows[a:a + 64] for a in range(0, len(rows), 64)]
    t0 = time.time()
    if workers > 1:
        from multiprocessing import Pool
        with Pool(int(workers)) as pool:
            for ch, imgs in zip(chunks, pool.imap(_encode_chunk, [(X[ch], encoding, size) for ch in chunks])):
                arr[ch] = imgs
    else:
        for ch in chunks:
            arr[ch] = _encode_chunk((X[ch], encoding, size))
    arr.flush()
    del arr
    open(done, "w").write(_now())
    log(f"{encoding}: {len(rows)} pictures in {time.time() - t0:.0f} s")
    return path


def _batch(imgs, idx, torch, device):
    t = torch.from_numpy(np.ascontiguousarray(imgs[np.sort(idx)])).to(device)
    idx = np.sort(idx)
    t = t.permute(0, 3, 1, 2).float()
    if t.shape[1] == 1:
        t = t.repeat(1, 3, 1, 1)
    return idx, (t / 255.0 - 0.5) / 0.5


def train_task(job_dir, task, *, deadline_min=None, device="auto", log=print):
    import torch
    from Working.training.cnn_job import _class_weights, build_model
    job = json.load(open(os.path.join(job_dir, "job.json"), encoding="utf-8"))
    folds = json.load(open(os.path.join(job_dir, "folds.json"), encoding="utf-8"))
    t = job["tasks"][int(task)]
    enc, fold = t["encoding"], folds[t["fold"]]
    tag = f"{enc}_{fold['group']}"
    out = os.path.join(job_dir, "out")
    os.makedirs(out, exist_ok=True)
    pred_path = os.path.join(out, f"pred_{tag}.npz")
    if os.path.exists(pred_path):
        log(f"{tag}: complete")
        return pred_path
    if not os.path.exists(os.path.join(job_dir, "cache", f"{enc}.npy.done")):
        raise SystemExit(f"{enc}: no picture cache; run encode.sh first (cache/{enc}.npy.done is missing)")
    imgs = np.load(os.path.join(job_dir, "cache", f"{enc}.npy"), mmap_mode="r")
    y_all = _inputs(job_dir)["label"].astype(np.int64)
    dev = torch.device(("cuda" if torch.cuda.is_available() else "cpu") if device == "auto" else device)
    cfg = job["cfg"]
    deadline = time.time() + 60 * float(deadline_min) if deadline_min else None
    torch.manual_seed(int(cfg["random_state"]))
    model = build_model(2, bool(cfg["pretrained"])).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=float(cfg["lr"]), weight_decay=float(cfg["weight_decay"]))
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=int(cfg["epochs"]), eta_min=1e-6)
    tr = np.asarray(fold["train"], dtype=np.int64)
    te = np.asarray(fold["test"], dtype=np.int64)
    cw = torch.tensor(_class_weights(y_all[tr], 2), dtype=torch.float32, device=dev)
    crit = torch.nn.CrossEntropyLoss(weight=cw)
    amp = dev.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=amp)
    ckpt = os.path.join(out, f"ckpt_{tag}.pt")
    history, start = [], 0
    if os.path.exists(ckpt):
        ck = torch.load(ckpt, map_location=dev, weights_only=False)
        model.load_state_dict(ck["model"]), opt.load_state_dict(ck["optimizer"]), sched.load_state_dict(ck["scheduler"])
        history, start = ck["history"], int(ck["epoch"]) + 1
    bs, last = int(cfg["batch_size"]), None
    for epoch in range(start, int(cfg["epochs"])):
        if deadline and last and time.time() + last > deadline:
            log(f"{tag}: deadline after epoch {epoch}; resubmit this task to resume")
            return None
        t0 = time.time()
        model.train()
        order = np.random.default_rng(int(cfg["random_state"]) + 1000 * epoch).permutation(tr)
        total = 0.0
        for a in range(0, len(order), bs):
            idx, xb = _batch(imgs, order[a:a + bs], torch, dev)
            yb = torch.as_tensor(y_all[idx], device=dev)
            opt.zero_grad(set_to_none=True)
            with torch.autocast("cuda", dtype=torch.float16, enabled=amp):
                loss = crit(model(xb), yb)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            total += float(loss.item()) * len(idx)
        sched.step()
        secs = time.time() - t0
        history.append({"epoch": epoch + 1, "loss": total / len(tr), "seconds": round(secs, 1),
                        "img_per_s": round(len(tr) / secs, 1)})
        log(f"{tag}: epoch {epoch + 1}/{cfg['epochs']} loss {history[-1]['loss']:.4f} "
            f"{history[-1]['img_per_s']:.0f} img/s")
        tmp = ckpt + ".tmp"
        torch.save({"model": model.state_dict(), "optimizer": opt.state_dict(), "scheduler": sched.state_dict(),
                    "epoch": epoch, "history": history}, tmp)
        os.replace(tmp, ckpt)
        last = time.time() - t0
    model.eval()
    p = np.zeros(len(te), dtype=np.float32)
    with torch.no_grad():
        for a in range(0, len(te), bs):
            idx, xb = _batch(imgs, te[a:a + bs], torch, dev)
            with torch.autocast("cuda", dtype=torch.float16, enabled=amp):
                logits = model(xb)
            pos = np.searchsorted(te, idx) if np.all(np.diff(te) >= 0) else [int(np.flatnonzero(te == i)[0]) for i in idx]
            p[pos] = torch.softmax(logits.float(), dim=1)[:, 1].cpu().numpy()
    np.savez(pred_path, row=te, p_interesting=p, encoding=enc, group=fold["group"],
             history=json.dumps(history), inputs_sha1=job["inputs_sha1"])
    torch.save(model.state_dict(), os.path.join(out, f"model_{tag}.pt"))
    if os.path.exists(ckpt):
        os.remove(ckpt)
    log(f"{tag}: complete, {len(te)} held-out events scored")
    return pred_path


def status(job_dir):
    job = json.load(open(os.path.join(job_dir, "job.json"), encoding="utf-8"))
    done = [t for t in job["tasks"]
            if os.path.exists(os.path.join(job_dir, "out", f"pred_{t['encoding']}_{t['group']}.npz"))]
    print(f"{len(done)} of {len(job['tasks'])} tasks complete")
    return 0 if len(done) == len(job["tasks"]) else 1


# ── fair: the import (local) ────────────────────────────────────────────────

def import_results(job_dir, out_dir, *, log=print):
    import glob
    import pandas as pd
    job = json.load(open(os.path.join(job_dir, "job.json"), encoding="utf-8"))
    rows = r4_rows()
    inp = _inputs(job_dir)
    if list(inp["ref"]) != list(rows["ref"]):
        raise SystemExit("the job's rows are not R4's rows: refusing to compare")
    ev = rows[rows["kind"] == "event"].copy()
    res = {"created_at": _now(), "job": job_dir, "inputs_sha1": job["inputs_sha1"], "models": {}, "missing": []}
    for enc in job["encodings"]:
        col = f"p_fair_{enc}"
        rows[col] = np.nan
        for t in [t for t in job["tasks"] if t["encoding"] == enc]:
            f = os.path.join(job_dir, "out", f"pred_{enc}_{t['group']}.npz")
            if not os.path.exists(f):
                res["missing"].append(os.path.basename(f))
                continue
            z = np.load(f, allow_pickle=False)
            if str(z["inputs_sha1"]) != job["inputs_sha1"]:
                raise SystemExit(f"{f}: made from other inputs")
            rows.loc[z["row"], col] = z["p_interesting"]
        ev[col] = rows.loc[ev.index, col]
        res["models"][f"EfficientNet-B0 {enc}, R4's folds"] = compare(ev.reset_index(drop=True), col)
    os.makedirs(out_dir, exist_ok=True)
    ev.to_parquet(os.path.join(out_dir, "fair_scores.parquet"), index=False)
    with open(os.path.join(out_dir, "fair_comparison.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    log(json.dumps({k: {g: (round(v["r4_auc"], 3), round(v["cnn_auc"], 3)) for g, v in m.items()}
                    for k, m in res["models"].items()}, indent=1))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score-reference")
    s.add_argument("--out", default=os.path.join(ROOT, "DATA", "derived", "models", "rq1b_cnn_vs_minirocket",
                                                 "reference_20261026"))
    e = sub.add_parser("export")
    e.add_argument("--job", default=os.path.join(ROOT, "DATA", "derived", "hpc", "rq1b_cnn_loro_20261026"))
    c = sub.add_parser("encode")
    c.add_argument("--job", required=True)
    c.add_argument("--encoding", required=True, choices=FAIR_ENCODINGS)
    c.add_argument("--workers", type=int, default=1)
    t = sub.add_parser("train")
    t.add_argument("--job", required=True)
    t.add_argument("--task", type=int, required=True)
    t.add_argument("--deadline-min", type=float)
    t.add_argument("--device", default="auto")
    st = sub.add_parser("status")
    st.add_argument("--job", required=True)
    i = sub.add_parser("import")
    i.add_argument("--job", required=True)
    i.add_argument("--out", default=os.path.join(ROOT, "DATA", "derived", "models", "rq1b_cnn_vs_minirocket",
                                                 "fair"))
    a = ap.parse_args(argv)
    if a.cmd == "score-reference":
        res = score_reference(a.out)
        print(json.dumps({m: {g: (round(v["r4_auc"], 3), round(v["cnn_auc"], 3)) for g, v in r.items()}
                          for m, r in res["models"].items()}, indent=1))
    elif a.cmd == "export":
        print(json.dumps(_estimate(export(a.job)), indent=1))
    elif a.cmd == "encode":
        encode(a.job, a.encoding, workers=a.workers)
    elif a.cmd == "train":
        train_task(a.job, a.task, deadline_min=a.deadline_min, device=a.device)
    elif a.cmd == "status":
        return status(a.job)
    else:
        import_results(a.job, a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
