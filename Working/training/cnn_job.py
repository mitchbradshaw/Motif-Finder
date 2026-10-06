"""
cnn_job.py
==========
fixup-ai: the CLUSTER side of arm B.2's CNN — what `python -m Working.training
cnn-run --job <dir>` runs on a GPU node, and what the local smoke runs on this
CPU. It reads a job directory written by `shape_cnn.export_job` and needs NO
database: the windows (raw bounds, role, cluster at the frozen cut), the recipe
and the channel arrays are all it touches.

    <job>/recipe.json    the recipe (its short hash is the run's identity)
    <job>/job.json       what was exported: the hash, the channels, the counts
    <job>/windows.npz    one row per window: raw bounds, role, cluster, hold-back
    <job>/cache/         the encoded images (bulk arrays, on disk, by path —
                         rule 4); not copied back
    <job>/out/           what comes back: done.json, model.pt (+ model.json),
                         predictions.npz, history.json, diagnostic.json,
                         null/shuffle_<i>.npz

The phases, each resumable (a SLURM job on this account ends at 20 minutes):

1. **encode** — every window's RAW samples at its re-cut bounds → the n × n
   image of its encoding (`Working.Catalogue.cnn.apply_cnn._window_to_pil`, the
   very function the manual-label CNNs were fed through) → resized AS AN IMAGE
   to the network's input by `torchvision.transforms.Resize` (the manual-label
   CNNs' own transform). The signal is never resampled. Cached in chunks; a
   chunk already encoded is skipped.
2. **diagnostic** — the network fitted on the training windows minus the
   forest's seeded 20 % hold-back, scored on that hold-back after each epoch
   (how well it reproduces its own answer key: a diagnostic, never a result).
3. **final** — refitted on every training window (as the forest's final model),
   unless the recipe says `refit: false`.
4. **predict** — P(cluster) for every validation, test and exam window.

A checkpoint per epoch; `deadline_s` stops cleanly between chunks / epochs so
the next job in the chain resumes. Headless: no UI or web library; torch is
imported only when a job runs.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import time

import numpy as np

RECIPE_KIND = "shape_cluster_cnn"
ENCODINGS = ("fusion", "GASF", "GADF", "recurrence")
JOB_FILE, RECIPE_FILE, WINDOWS_FILE = "job.json", "recipe.json", "windows.npz"
OUT, CACHE = "out", "cache"
#: the windows file, field by field (the key is computed over them in this order)
WINDOW_FIELDS = ("row", "recording_id", "source_file", "channel", "start", "orig_start", "length", "fs",
                 "scale_min", "role", "label", "holdback", "chan")
_STR = ("source_file", "role")
_FLOAT = ("fs", "scale_min")
_BOOL = ("holdback",)
ENCODE_CHUNK = 128
NULL_SEED_BASE = 10_000


def _now():
    return _dt.datetime.now().isoformat(timespec="seconds")


def short_hash(obj):
    from Working.recipes import short_hash as _sh
    return _sh(obj)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _write(path, obj):
    """Atomic: a job killed mid-write never leaves half a file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, default=_json_default)
    os.replace(tmp, path)


def _json_default(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


# ── the windows file ────────────────────────────────────────────────────────

def save_windows(path, w):
    arrs = {}
    for f in WINDOW_FIELDS:
        a = np.asarray(w[f])
        arrs[f] = (a.astype(str) if f in _STR else a.astype(np.float64) if f in _FLOAT else
                   a.astype(bool) if f in _BOOL else a.astype(np.int64))
    np.savez_compressed(path, **arrs)


def load_windows(job_dir):
    with np.load(os.path.join(job_dir, WINDOWS_FILE), allow_pickle=False) as z:
        return {f: z[f] for f in WINDOW_FIELDS}


def windows_key(w):
    """A content key over every field of every window (bounds, role, cluster, hold-back, channel)."""
    h = hashlib.sha256(b"b2-cnn-windows")
    for f in WINDOW_FIELDS:
        a = np.asarray(w[f])
        h.update(f.encode("utf-8") + b"=")
        if a.dtype.kind in "OUS":
            h.update("\x00".join(map(str, a.tolist())).encode("utf-8"))
        elif a.dtype.kind == "b":
            h.update(np.ascontiguousarray(a.astype(np.uint8)).tobytes())
        elif a.dtype.kind == "f":
            h.update(np.ascontiguousarray(a.astype("<f8")).tobytes())
        else:
            h.update(np.ascontiguousarray(a.astype("<i8")).tobytes())
        h.update(b"|")
    return h.hexdigest()[:16]


# ── one window → one image ──────────────────────────────────────────────────

def encode_window(x, encoding, size):
    """The window AS IT IS (its n raw samples) → the n × n image of `encoding` → resized as an image to
    `size` × `size` by the network's own transform. uint8, (size, size, 3) for fusion, (size, size, 1) else
    (a grey image; the network sees it repeated on three channels, as `ImageFolder` + `Grayscale(3)` did)."""
    from torchvision import transforms
    from Working.Catalogue.cnn.apply_cnn import _window_to_pil
    if encoding not in ENCODINGS:
        raise ValueError(f"encoding {encoding!r}: one of {', '.join(ENCODINGS)}")
    img = transforms.Resize((int(size), int(size)))(_window_to_pil(np.asarray(x, dtype=np.float64), encoding))
    a = np.asarray(img, dtype=np.uint8)
    if a.ndim == 2:
        a = a[..., None]
    return a if encoding == "fusion" else a[..., :1]


_ARRAYS = {}


def _encode_rows(args):
    """One chunk, in a worker process: [(path, start, length)] → stacked images and per-window seconds."""
    rows, encoding, size = args
    out, secs = [], []
    for path, start, length in rows:
        t = time.perf_counter()
        x = _ARRAYS.get(path)
        if x is None:
            x = _ARRAYS[path] = np.load(path, mmap_mode="r")
        out.append(encode_window(x[int(start):int(start) + int(length)], encoding, size))
        secs.append(time.perf_counter() - t)
    return np.stack(out), np.asarray(secs)


def _channel_path(job_dir, p):
    """A channel array named repo-relative resolves from the working directory (the job's `--chdir`)."""
    if os.path.isabs(p):
        return p
    return os.path.abspath(p)


# ── the job ─────────────────────────────────────────────────────────────────

class Job:
    def __init__(self, job_dir):
        self.dir = os.path.abspath(job_dir)
        self.recipe = _read(os.path.join(self.dir, RECIPE_FILE))
        self.meta = _read(os.path.join(self.dir, JOB_FILE))
        self.hash = short_hash(self.recipe)
        if self.meta.get("recipe_hash") != self.hash:
            raise ValueError(f"{RECIPE_FILE} in {self.dir} was changed after the job was written (hash {self.hash}, "
                             f"{JOB_FILE} says {self.meta.get('recipe_hash')}): export the job again")
        self.cfg = self.recipe["cnn"]
        self.encoding = self.recipe["inputs"]["encoding"]
        self.size = int(self.cfg["img_size"])
        self.channels_c = 3 if self.encoding == "fusion" else 1
        self.k = int(self.recipe["arm"]["k"])
        self.out = os.path.join(self.dir, OUT)
        self.cache = os.path.join(self.dir, CACHE)
        self.w = load_windows(self.dir)
        key = windows_key(self.w)
        if key != (self.recipe.get("bundle") or {}).get("windows_key"):
            raise ValueError(f"the windows in {WINDOWS_FILE} (key {key}) are not the windows the recipe names "
                             f"({(self.recipe.get('bundle') or {}).get('windows_key')}): export the job again")
        self.n = len(self.w["row"])
        self.roles = np.asarray(self.w["role"]).astype(str)
        self.state_path = os.path.join(self.out, "state.json")
        self.state = _read(self.state_path) if os.path.isfile(self.state_path) else {
            "recipe_hash": self.hash, "phase": "encode", "timings": {}, "measured": {}, "started_at": _now(), "jobs": 0}

    # paths
    @property
    def images_path(self):
        return os.path.join(self.cache, f"images_{self.encoding}_{self.size}.npy")

    @property
    def mask_path(self):
        return os.path.join(self.cache, f"encoded_{self.encoding}_{self.size}.npy")

    def save_state(self):
        _write(self.state_path, self.state)

    def add_time(self, phase, seconds):
        t = self.state.setdefault("timings", {})
        t[phase] = round(float(t.get(phase, 0.0)) + float(seconds), 2)

    # ── 1. encode ──
    def encoded_mask(self):
        return np.load(self.mask_path) if os.path.isfile(self.mask_path) else np.zeros(self.n, dtype=bool)

    def encode(self, *, workers=0, deadline=None, progress=None, cancel=None):
        """Encode every window not yet in the cache. Returns True when every window is encoded."""
        os.makedirs(self.cache, exist_ok=True)
        shape = (self.n, self.size, self.size, self.channels_c)
        if os.path.isfile(self.images_path):
            imgs = np.load(self.images_path, mmap_mode="r+")
            if imgs.shape != shape:
                raise ValueError(f"the image cache {self.images_path} holds {imgs.shape}, the job needs {shape}")
        else:
            imgs = np.lib.format.open_memmap(self.images_path, mode="w+", dtype=np.uint8, shape=shape)
        mask = self.encoded_mask()
        todo = np.flatnonzero(~mask)
        if not len(todo):
            return True
        chans = self.meta["channels"]
        paths = [_channel_path(self.dir, c["path"]) for c in chans]
        chan, start, length = (np.asarray(self.w[f]) for f in ("chan", "start", "length"))
        scale = np.asarray(self.w["scale_min"], dtype=float)
        meas = self.state.setdefault("measured", {})
        per = meas.setdefault("encode_s_by_scale", {})
        cnt = meas.setdefault("encode_n_by_scale", {})
        chunk = ENCODE_CHUNK * max(1, int(workers))
        pool = None
        if workers and int(workers) > 1:
            from concurrent.futures import ProcessPoolExecutor
            pool = ProcessPoolExecutor(max_workers=int(workers))
        t_phase = time.time()
        try:
            for a in range(0, len(todo), chunk):
                if deadline is not None and time.time() >= deadline:
                    return False
                if cancel is not None and cancel():
                    raise InterruptedError("cancelled while encoding")
                idx = todo[a:a + chunk]
                rows = [(paths[int(chan[i])], int(start[i]), int(length[i])) for i in idx]
                if pool is None:
                    got, secs = _encode_rows((rows, self.encoding, self.size))
                else:
                    parts = [rows[j:j + ENCODE_CHUNK] for j in range(0, len(rows), ENCODE_CHUNK)]
                    res = list(pool.map(_encode_rows, [(p, self.encoding, self.size) for p in parts]))
                    got = np.concatenate([r[0] for r in res])
                    secs = np.concatenate([r[1] for r in res])
                imgs[idx] = got
                imgs.flush()
                mask[idx] = True
                tmp = self.mask_path + ".tmp.npy"
                np.save(tmp, mask)
                os.replace(tmp, self.mask_path)
                for s in np.unique(scale[idx]):
                    m = scale[idx] == s
                    key = f"{float(s):g}"
                    per[key] = round(float(per.get(key, 0.0)) + float(secs[m].sum()), 4)
                    cnt[key] = int(cnt.get(key, 0)) + int(m.sum())
                meas["encode_ms_by_scale"] = {k2: round(1000.0 * per[k2] / max(1, cnt[k2]), 2) for k2 in per}
                self.add_time("encode", time.time() - t_phase)
                t_phase = time.time()
                self.save_state()
                if progress is not None:
                    progress(int(mask.sum()), self.n, f"encoded {int(mask.sum()):,} of {self.n:,} windows "
                                                      f"({self.encoding}, {self.size} px)")
        finally:
            if pool is not None:
                pool.shutdown()
        return bool(mask.all())

    # ── 2-3. train ──
    def images(self):
        return np.load(self.images_path, mmap_mode="r")

    def batch(self, imgs, idx, torch, device):
        idx = np.sort(np.asarray(idx))
        a = np.asarray(imgs[idx], dtype=np.float32)                    # (b, S, S, C) uint8 → float
        t = torch.from_numpy(a).permute(0, 3, 1, 2)
        if t.shape[1] == 1:
            t = t.repeat(1, 3, 1, 1)
        t = (t / 255.0 - 0.5) / 0.5                                    # ToTensor + Normalize(0.5, 0.5)
        return idx, t.to(device, non_blocking=True)


def build_model(k, pretrained=True):
    """The manual-label CNNs' own network (`cnn_rangapur.EEG_CNN`: EfficientNet-B0, ImageNet weights, a dropout +
    linear head) with k outputs. Its state dict loads with `apply_cnn.load_model` like theirs."""
    import torch.nn as nn
    from Working.Catalogue.cnn.cnn_rangapur import EEG_CNN
    if pretrained:
        try:
            return EEG_CNN(int(k))
        except Exception as e:      # no network on a compute node and no cached weights
            raise RuntimeError(
                "the ImageNet weights for EfficientNet-B0 are not in the torch hub cache and could not be "
                "downloaded (a compute node often has no network). On the login node, once: python -c \"from "
                "torchvision.models import efficientnet_b0, EfficientNet_B0_Weights as W; "
                f"efficientnet_b0(weights=W.DEFAULT)\" — then resubmit. ({type(e).__name__}: {e})") from e
    from torchvision.models import efficientnet_b0
    m = EEG_CNN.__new__(EEG_CNN)
    nn.Module.__init__(m)
    m.backbone = efficientnet_b0(weights=None)
    in_features = m.backbone.classifier[1].in_features
    m.backbone.classifier = nn.Sequential(nn.Dropout(p=0.3), nn.Linear(in_features, int(k)))
    return m


def _device(torch, device):
    if device in (None, "auto"):
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(device)


def _class_weights(y, k):
    """sklearn's `balanced`: n / (k_present · count) per class present, 0 for a class absent from the fit."""
    counts = np.bincount(y, minlength=k).astype(float)
    present = counts > 0
    w = np.zeros(k)
    w[present] = len(y) / (present.sum() * counts[present])
    return w


def _macro_f1(y, p, k):
    f1s = []
    for c in range(k):
        tp = int(((p == c) & (y == c)).sum())
        fp = int(((p == c) & (y != c)).sum())
        fn = int(((p != c) & (y == c)).sum())
        if tp + fp + fn == 0:
            continue
        f1s.append(2 * tp / (2 * tp + fp + fn))
    return float(np.mean(f1s)) if f1s else 0.0


def _save_torch(torch, obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    torch.save(obj, tmp)
    os.replace(tmp, path)


def _predict(job, model, rows, torch, device, bs):
    imgs = job.images()
    model.eval()
    probs = np.zeros((len(rows), job.k), dtype=np.float32)
    pos = {int(r): i for i, r in enumerate(rows)}
    with torch.no_grad():
        for a in range(0, len(rows), bs):
            idx, xb = job.batch(imgs, rows[a:a + bs], torch, device)
            if device.type == "cuda":
                with torch.autocast("cuda", dtype=torch.float16):
                    logits = model(xb)
            else:
                logits = model(xb)
            p = torch.softmax(logits.float(), dim=1).cpu().numpy()
            probs[[pos[int(i)] for i in idx]] = p
    return probs


def _train_phase(job, phase, fit_rows, y_all, *, torch, device, deadline, progress, cancel, eval_rows=None,
                 ckpt_path=None, seed_offset=0):
    """Fit `cfg.epochs` epochs on `fit_rows` (labels `y_all[row]`, 0-based), a checkpoint per epoch. Returns
    (model, history, complete)."""
    cfg = job.cfg
    k, bs, epochs = job.k, int(cfg["batch_size"]), int(cfg["epochs"])
    seed = int(cfg["random_state"]) + seed_offset
    torch.manual_seed(seed)
    model = build_model(k, bool(cfg.get("pretrained", True))).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=float(cfg["lr"]), weight_decay=float(cfg.get("weight_decay", 0.0)))
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, epochs), eta_min=1e-6)
    y_fit = y_all[fit_rows]
    cw = torch.tensor(_class_weights(y_fit, k), dtype=torch.float32, device=device)
    crit = torch.nn.CrossEntropyLoss(weight=cw if cfg.get("class_weight") == "balanced" else None)
    use_amp = device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    ckpt_path = ckpt_path or os.path.join(job.out, f"ckpt_{phase}.pt")
    history, start = [], 0
    if os.path.isfile(ckpt_path):
        ck = torch.load(ckpt_path, map_location=device, weights_only=False)
        model.load_state_dict(ck["model"])
        opt.load_state_dict(ck["optimizer"])
        sched.load_state_dict(ck["scheduler"])
        history, start = list(ck["history"]), int(ck["epoch"]) + 1
    imgs = job.images()
    last = None
    for epoch in range(start, epochs):
        if deadline is not None and (time.time() >= deadline or (last is not None and time.time() + last > deadline)):
            return model, history, False
        if cancel is not None and cancel():
            raise InterruptedError(f"cancelled in the {phase} phase")
        t0 = time.time()
        model.train()
        order = np.random.default_rng(seed + 1000 * epoch).permutation(fit_rows)
        total, n_seen = 0.0, 0
        for a in range(0, len(order), bs):
            idx, xb = job.batch(imgs, order[a:a + bs], torch, device)
            yb = torch.as_tensor(y_all[idx], dtype=torch.long, device=device)
            opt.zero_grad(set_to_none=True)
            if use_amp:
                with torch.autocast("cuda", dtype=torch.float16):
                    loss = crit(model(xb), yb)
                scaler.scale(loss).backward()
                scaler.step(opt)
                scaler.update()
            else:
                loss = crit(model(xb), yb)
                loss.backward()
                opt.step()
            total += float(loss.item()) * len(idx)
            n_seen += len(idx)
        sched.step()
        secs = time.time() - t0
        row = {"epoch": epoch + 1, "loss": total / max(1, n_seen), "seconds": round(secs, 2),
               "img_per_s": round(n_seen / max(secs, 1e-9), 2), "n_fit": int(n_seen)}
        if eval_rows is not None and len(eval_rows):
            te = time.time()
            p = _predict(job, model, eval_rows, torch, device, bs)
            pred = p.argmax(axis=1)
            yt = y_all[eval_rows]
            row.update({"diagnostic_accuracy": float((pred == yt).mean()), "diagnostic_macro_f1": _macro_f1(yt, pred, k),
                        "eval_seconds": round(time.time() - te, 2)})
            model.train()
        history.append(row)
        _save_torch(torch, {"model": model.state_dict(), "optimizer": opt.state_dict(), "scheduler": sched.state_dict(),
                            "epoch": epoch, "history": history, "recipe_hash": job.hash}, ckpt_path)
        job.add_time(phase, secs + row.get("eval_seconds", 0.0))
        job.save_state()
        last = time.time() - t0
        if progress is not None:
            progress(epoch + 1, epochs, f"{phase}: epoch {epoch + 1}/{epochs} · loss {row['loss']:.4f}"
                     + (f" · hold-back accuracy {row['diagnostic_accuracy']:.3f}" if "diagnostic_accuracy" in row else "")
                     + f" · {row['img_per_s']:.0f} img/s")
    return model, history, True


def _labels0(job):
    """0-based cluster labels per window (training windows only; -1 elsewhere)."""
    lab = np.asarray(job.w["label"], dtype=np.int64)
    return np.where(lab > 0, lab - 1, -1)


def job_status(job_dir):
    """(code, text): 0 complete, 1 work remains, 3 the job cannot be read. The chain resubmits on 1."""
    try:
        job = Job(job_dir)
    except Exception as e:
        return 3, f"the job at {job_dir} cannot be read: {type(e).__name__}: {e}"
    done = os.path.join(job.out, "done.json")
    if os.path.isfile(done):
        d = _read(done)
        if d.get("recipe_hash") == job.hash and d.get("status") == "complete":
            return 0, f"complete · recipe {job.hash} · results in {job.out}"
        return 3, f"{done} names recipe {d.get('recipe_hash')}, the job is {job.hash}"
    mask = job.encoded_mask()
    st = job.state
    return 1, (f"incomplete · phase {st.get('phase')} · encoded {int(mask.sum()):,} of {job.n:,} · "
               f"{len(st.get('history', {}).get('diagnostic', []))} diagnostic and "
               f"{len(st.get('history', {}).get('final', []))} final epoch(s) of {job.cfg['epochs']}")


def run_job(job_dir, *, device="auto", workers=0, deadline_s=None, progress=None, cancel=None):
    """Run (or resume) the job. `deadline_s`: seconds from now after which no new chunk or epoch starts.
    Returns {"status": "complete" | "incomplete", "phase": ..., ...}."""
    t_start = time.time()
    deadline = None if deadline_s is None else t_start + float(deadline_s)
    job = Job(job_dir)
    code, text = job_status(job_dir)
    if code == 0:
        return {"status": "complete", "skipped": True, "phase": "done", "text": text}
    job.state["jobs"] = int(job.state.get("jobs", 0)) + 1
    say = progress or (lambda *a: None)

    if not job.encode(workers=workers, deadline=deadline, progress=progress, cancel=cancel):
        job.state["phase"] = "encode"
        job.save_state()
        return {"status": "incomplete", "phase": "encode", "text": job_status(job_dir)[1]}
    import torch
    dev = _device(torch, device)
    if dev.type == "cuda":
        torch.backends.cudnn.benchmark = True
    y = _labels0(job)
    train = np.flatnonzero(job.roles == "train")
    hold = np.asarray(job.w["holdback"], dtype=bool)
    fit_d, held = train[~hold[train]], train[hold[train]]
    hist = job.state.setdefault("history", {})

    job.state["phase"] = "diagnostic"
    job.save_state()
    say(0, 3, "the diagnostic: the network against its own answer key")
    model, h, ok = _train_phase(job, "diagnostic", fit_d, y, torch=torch, device=dev, deadline=deadline,
                                progress=progress, cancel=cancel, eval_rows=held)
    hist["diagnostic"] = h
    job.save_state()
    if not ok:
        return {"status": "incomplete", "phase": "diagnostic", "text": job_status(job_dir)[1]}
    last = h[-1] if h else {}
    chance = float(np.bincount(y[held], minlength=job.k).max() / max(1, len(held))) if len(held) else None
    _write(os.path.join(job.out, "diagnostic.json"), {
        "kind": "diagnostic", "n_held_back": int(len(held)), "n_fit": int(len(fit_d)),
        "accuracy": last.get("diagnostic_accuracy"), "macro_f1": last.get("diagnostic_macro_f1"),
        "chance_largest_cluster": chance, "epochs": len(h),
        "note": ("how well the CNN reproduces the clustering on training windows it did not fit (the forest's seeded "
                 "20 %, after the last epoch) — a network imitating its own answer key: a diagnostic, not a result")})

    if job.cfg.get("refit", True):
        job.state["phase"] = "final"
        job.save_state()
        model, h, ok = _train_phase(job, "final", train, y, torch=torch, device=dev, deadline=deadline,
                                    progress=progress, cancel=cancel, seed_offset=1)
        hist["final"] = h
        job.save_state()
        if not ok:
            return {"status": "incomplete", "phase": "final", "text": job_status(job_dir)[1]}
        n_fit_final = int(len(train))
    else:
        hist["final"] = []
        n_fit_final = int(len(fit_d))

    if deadline is not None and time.time() >= deadline:
        return {"status": "incomplete", "phase": "predict", "text": job_status(job_dir)[1]}
    job.state["phase"] = "predict"
    job.save_state()
    say(2, 3, "predicting the validation, test and exam windows")
    t = time.time()
    rows = np.flatnonzero(job.roles != "train")
    probs = _predict(job, model, rows, torch, dev, int(job.cfg["batch_size"]))
    secs = time.time() - t
    job.add_time("predict", secs)
    np.savez_compressed(os.path.join(job.out, "predictions.npz"), index=rows.astype(np.int64),
                        row=np.asarray(job.w["row"])[rows].astype(np.int64), probs=probs,
                        classes=np.arange(1, job.k + 1, dtype=np.int64))
    _save_torch(torch, model.state_dict(), os.path.join(job.out, "model.pt"))
    _write(os.path.join(job.out, "model.json"), {
        "kind": "EEG_CNN state dict (Working.Catalogue.cnn.cnn_rangapur) · loads with apply_cnn.load_model",
        "classes": [f"cluster {c}" for c in range(1, job.k + 1)], "output_index_is": "cluster - 1",
        "encoding": job.encoding, "img_size": job.size, "recipe_hash": job.hash,
        "mapping": job.recipe["arm"]["mapping"]})
    _write(os.path.join(job.out, "history.json"), {"diagnostic": hist.get("diagnostic", []),
                                                   "final": hist.get("final", [])})
    meas = job.state.setdefault("measured", {})
    all_epochs = (hist.get("diagnostic") or []) + (hist.get("final") or [])
    if all_epochs:
        meas["train_img_per_s"] = round(float(np.median([e["img_per_s"] for e in all_epochs])), 2)
    meas["predict_img_per_s"] = round(len(rows) / max(secs, 1e-9), 2)
    meas["device"] = dev.type + (f" · {torch.cuda.get_device_name(0)}" if dev.type == "cuda" else "")
    meas["workers"] = int(workers or 0)
    job.state["phase"] = "done"
    job.save_state()
    timings = dict(job.state.get("timings") or {})
    timings.setdefault("final", 0.0)
    timings["total"] = round(sum(v for k2, v in timings.items() if k2 != "total"), 2)
    _write(os.path.join(job.out, "done.json"), {
        "status": "complete", "recipe_hash": job.hash, "finished_at": _now(), "started_at": job.state.get("started_at"),
        "jobs": job.state.get("jobs"), "timings": timings, "measured": meas, "torch": torch.__version__,
        "n_fit_diagnostic": int(len(fit_d)), "n_fit_final": n_fit_final, "n_held_back": int(len(held)),
        "n_predicted": int(len(rows)), "epochs": int(job.cfg["epochs"])})
    return {"status": "complete", "phase": "done", "text": job_status(job_dir)[1]}


# ── the label-shuffle null: one full training on shuffled cluster labels ────

def null_status(job_dir, shuffle):
    p = os.path.join(job_dir, OUT, "null", f"shuffle_{int(shuffle)}.json")
    return (0, f"shuffle {shuffle} complete") if os.path.isfile(p) else (1, f"shuffle {shuffle} incomplete")


def run_null(job_dir, shuffle, *, device="auto", workers=0, deadline_s=None, progress=None, cancel=None):
    """One of the label-shuffle null's full trainings (§9.4): the training windows' cluster labels permuted
    (seeded by the shuffle number), the same network and epochs, predictions on the same windows."""
    t_start = time.time()
    deadline = None if deadline_s is None else t_start + float(deadline_s)
    shuffle = int(shuffle)
    job = Job(job_dir)
    if null_status(job_dir, shuffle)[0] == 0:
        return {"status": "complete", "skipped": True}
    if not job.encode(workers=workers, deadline=deadline, progress=progress, cancel=cancel):
        return {"status": "incomplete", "phase": "encode"}
    import torch
    dev = _device(torch, device)
    y = _labels0(job)
    train = np.flatnonzero(job.roles == "train")
    ys = y.copy()
    ys[train] = np.random.default_rng(NULL_SEED_BASE + shuffle).permutation(y[train])
    d = os.path.join(job.out, "null")
    model, h, ok = _train_phase(job, f"null_{shuffle}", train, ys, torch=torch, device=dev, deadline=deadline,
                                progress=progress, cancel=cancel, ckpt_path=os.path.join(d, f"ckpt_{shuffle}.pt"),
                                seed_offset=100 + shuffle)
    if not ok:
        return {"status": "incomplete", "phase": "train"}
    rows = np.flatnonzero(job.roles != "train")
    probs = _predict(job, model, rows, torch, dev, int(job.cfg["batch_size"]))
    np.savez_compressed(os.path.join(d, f"shuffle_{shuffle}.npz"), index=rows.astype(np.int64),
                        row=np.asarray(job.w["row"])[rows].astype(np.int64), probs=probs,
                        classes=np.arange(1, job.k + 1, dtype=np.int64))
    _write(os.path.join(d, f"shuffle_{shuffle}.json"), {"shuffle": shuffle, "seed": NULL_SEED_BASE + shuffle,
                                                        "recipe_hash": job.hash, "history": h, "finished_at": _now()})
    return {"status": "complete"}
