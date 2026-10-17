"""
window_scores.py
=================
The trained CNNs' P(interesting) for every window of a window set, at any
window length — the core of `catalogue.cnn_window_scores` (W4-A), and the
batched inference `catalogue.cnn_score` shares (`score_stack`, moved here so
both blocks run one implementation).

**A public API.** RQ1's blind scoring (`Working/training/blind.py`) may call
`score_windows` later: its name, arguments and `meta` keys are kept stable.

    probs, meta = score_windows(x, starts, length, image_type="fusion",
                                model_path="MODELS/fusion_cnn_3.pth")

`starts` index `x` (span-relative); `probs[i]` is P(positive class) for
window i, NaN for a window left out (it holds NaN, or is flat).

What happens to one window
--------------------------
1. **Resampled to the training geometry** (`resample_to`, default 600 points:
   the four CNNs in `MODELS/` were trained on 600-sample, 10-minute windows of
   M2_aug at 1 Hz). Upsampling is linear (`Working.distances.resample_to_length`).
   Downsampling is anti-aliased, because a picture of a squeezed window must
   not show a slow wave that is really a fast ripple folded over: block means
   when the length is a whole multiple of the target (3,600 → 600: each point
   is the mean of 6 samples), else `scipy.signal.resample_poly`, a polyphase
   low-pass, with the window's ends extended along a straight line
   (`padtype="line"`) so the edges do not droop toward zero — a zero-padded
   filter draws a false drop at both ends of every window. An awkward ratio
   (36,001 → 600) designs a long filter, about 0.1 s a window; the lengths
   Sliding windows produces (60, 600, 3,600, 36,000 samples at 1 or 10 Hz)
   are whole multiples or divisors of 600. `resample_to = 0` keeps every
   window as is (16–2,048 samples), the convention `blind.py` scored RQ1 with.
2. **Encoded exactly as the training set was**: `apply_cnn._window_to_pil`
   (fusion RGB, or GASF / GADF / recurrence as grey → RGB), resized to
   `img_size` with PIL bilinear (as `catalogue.window_images` does), then the
   training's evaluation transform, `cnn_rangapur.get_transforms(img_size,
   is_train=False, is_rgb=(image_type == "fusion"))`. On these grey → RGB
   images the grey transform gives the same tensor as `cnn_score`'s RGB one
   (pinned in `tests/test_cnn_window_scores.py`).
3. **Scored** a batch at a time: softmax over the network's two outputs,
   column `positive_class` (0 = "interesting", ImageFolder's alphabetical
   order). At most `batch_size` pictures exist at once; nothing n-sized is
   ever allocated but the score vector.

Why not the existing chain (`sliding_windows → window_images → cnn_score`):
`window_images` holds every picture at once (6.5 GB for one 721-h channel at
1-minute windows) and refuses over 2,000 windows, and it never resamples — a
1-hour window at 10 Hz would be a 36,000 × 36,000 matrix.

Refusals (ValueError naming the file): a missing checkpoint; a file name that
names another image type than `image_type`; a checkpoint with other than two
classes (`fusion_cnn.pth` has one, so softmax[:, 0] is 1.0 for every window;
`fusion_prediction_cnn.pth` has fourteen, a binned predictor); a
`positive_class` out of range. Loading never downloads: the network is built
with `EEG_CNN(pretrained=False)` (`apply_cnn.load_model`).

Torch is imported inside the functions (seconds on first import), so
registering the block stays cheap. CUDA if available, else the CPU; no
`torch.set_num_threads` (it is process-wide, and the bridge runs jobs on
threads).
"""

import math
import os
import time

import numpy as np

IMAGE_TYPES = ("fusion", "GASF", "GADF", "recurrence")
TRAINING_LENGTH = 600           # samples per training window (10 min at 1 Hz)
MIN_POINTS = 16                 # the recurrence embedding (m = 3, tau = 4) needs more than 8 points
MAX_POINTS = 2048               # an L x L float64 matrix: 2048 -> 34 MB per picture
N_CLASSES = 2
META_CAP = 4096                 # window scores and starts kept in meta
CLASSIFIER_KEY = "backbone.classifier.1.weight"

TRAINING_SCALE = (
    "The CNNs in MODELS/ were trained on 600-sample, 10-minute windows of M2_aug at 1 Hz. Any other window "
    "length is outside that scale: each window is resampled to 600 points, so the model sees its shapes "
    "stretched or squeezed in time. Scores on M2_aug itself are not out-of-sample (the models were trained "
    "on those recordings).")

RULES = [
    {"name": "resampling",
     "rule": "Each window's L samples become resample_to points spanning the window. Longer windows are "
             "averaged down, anti-aliased so a ripple faster than the new grid cannot fold into a false slow "
             "wave: block means when L is a whole multiple of resample_to, else a polyphase low-pass "
             "(scipy.signal.resample_poly) with the ends extended along a straight line so they do not droop. "
             "Shorter windows are stretched by straight-line interpolation. L = resample_to is used as is; "
             "resample_to = 0 keeps every window as is (16 to 2048 samples)."},
    {"name": "picture",
     "rule": "Each resampled window becomes the picture the CNN was trained on (fusion: GASF, GADF and the "
             "recurrence plot as one RGB image; or one of the three as grey copied to RGB), resized to img_size "
             "with PIL bilinear, then the training's evaluation transform."},
    {"name": "score",
     "rule": "P(positive_class) = the softmax of the network's two outputs; class 0 = 'interesting' "
             "(ImageFolder's alphabetical order). Only two-class checkpoints are accepted."},
    {"name": "left out",
     "rule": "A window holding NaN (a gap) or a flat window (max = min, which the Gramian encoding would turn "
             "into an all-black picture that still gets a score) is not scored: its score is NaN and it is "
             "counted by reason in skipped ('nan', 'flat')."},
]


# ── resampling ──────────────────────────────────────────────────────────────

def resample_window(w, n):
    """`w`'s samples as `n` points spanning the window (the rule is `RULES[0]`)."""
    from Working.distances import resample_to_length
    w = np.asarray(w, dtype=float).ravel()
    L, n = len(w), int(n)
    if n == L:
        return w.copy()
    if n > L:
        return resample_to_length(w, n)
    if L % n == 0:
        return w.reshape(n, L // n).mean(axis=1)
    from scipy.signal import resample_poly
    g = math.gcd(L, n)
    return resample_poly(w, n // g, L // g, padtype="line")[:n]


# ── the picture ─────────────────────────────────────────────────────────────

def _pil(w, image_type):
    """The training pixels of one window (`apply_cnn._window_to_pil`), at its native size."""
    from Working.Catalogue.cnn.apply_cnn import _window_to_pil
    return _window_to_pil(w, image_type)


def window_image(w, image_type, img_size=224, resample_to=TRAINING_LENGTH):
    """One window as the RGB picture the CNN reads: resampled (unless `resample_to` is 0), encoded as in
    training, resized to `img_size` — the pixels `catalogue.window_images` stores for the same window."""
    from PIL import Image
    w = np.asarray(w, dtype=float)
    if resample_to:
        w = resample_window(w, resample_to)
    return _pil(w, image_type).resize((int(img_size), int(img_size)), Image.BILINEAR)


# ── the model ───────────────────────────────────────────────────────────────

def _device():
    import torch
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _check_name(model_path, image_type):
    if image_type is None:
        return
    stem = os.path.basename(str(model_path)).lower()
    named = [t.lower() for t in IMAGE_TYPES if t.lower() in stem]
    if named and image_type.lower() not in named:
        raise ValueError(
            f"{model_path}: the file name names the {' / '.join(named)} image type, but image_type is "
            f"{image_type!r}. A CNN only reads the kind of picture it was trained on: set image_type to match "
            f"the checkpoint, or pick the checkpoint trained on {image_type} pictures.")


def _check_classes(model_path, n_classes, positive_class):
    if n_classes != N_CLASSES:
        raise ValueError(
            f"{model_path}: the checkpoint has {n_classes} output class{'' if n_classes == 1 else 'es'}; scoring "
            f"needs a two-class 'interesting' / 'not interesting' model (with one class, P(interesting) is 1.0 "
            f"for every window). fusion_cnn.pth has one class and fusion_prediction_cnn.pth fourteen; pick "
            f"fusion_cnn_3, GADF_cnn, GASF_cnn or recurrence_cnn in Settings › Models & registration.")
    if not 0 <= int(positive_class) < n_classes:
        raise ValueError(
            f"positive_class={positive_class} is out of range for {model_path}, which has {n_classes} classes "
            f"(0 … {n_classes - 1}; 0 = 'interesting', ImageFolder's alphabetical order).")


def checkpoint_classes(model_path):
    """The number of output classes an `EEG_CNN` state dict was trained with, read off its classifier."""
    import torch
    ckpt = torch.load(model_path, map_location="cpu", weights_only=True)
    if CLASSIFIER_KEY not in ckpt:
        raise ValueError(f"{model_path}: not an EEG_CNN state dict (no {CLASSIFIER_KEY!r}); this block scores "
                         f"the EfficientNet-B0 checkpoints cnn_rangapur.py trains.")
    return int(ckpt[CLASSIFIER_KEY].shape[0])


def load_scorer(model_path, image_type=None, positive_class=0, device=None):
    """`(model, n_classes)` for a checkpoint that passes every refusal, in eval mode, built without
    downloading anything. `image_type=None` skips the file-name check (`catalogue.cnn_score` does not know
    which pictures its stack holds)."""
    if not os.path.isfile(str(model_path)):
        raise ValueError(f"model_path {model_path!r} does not exist; pick a checkpoint in "
                         f"Settings › Models & registration.")
    _check_name(model_path, image_type)
    n_classes = checkpoint_classes(model_path)
    _check_classes(model_path, n_classes, positive_class)
    from Working.Catalogue.cnn.apply_cnn import load_model
    return load_model(model_path, device or _device()), n_classes


def _n_classes_of(model):
    """The output count of an already-built network: its last Linear layer."""
    import torch.nn as nn
    linears = [m for m in model.modules() if isinstance(m, nn.Linear)]
    if not linears:
        raise ValueError("the model has no Linear output layer to count classes on")
    return int(linears[-1].out_features)


def predict(model, tensors, positive_class=0):
    """P(positive_class) for one batch of transformed pictures `[(3, H, W), ...]`."""
    import torch
    device = next(model.parameters()).device
    with torch.no_grad():
        logits = model(torch.stack(list(tensors)).to(device))
        return torch.softmax(logits, dim=1)[:, int(positive_class)].cpu().numpy().astype(float)


def _cancelled():
    from Working.execution import RecipeCancelled      # inside: the executor imports the adapters
    return RecipeCancelled


# ── the two entry points ────────────────────────────────────────────────────

def score_stack(stack, model_path, img_size=224, batch_size=32, positive_class=0, model=None):
    """P(positive_class) for each image of an `(n, H, W, 3)` uint8 stack — `catalogue.cnn_score`'s inference,
    with the same class check as `score_windows`."""
    from PIL import Image
    from Working.Catalogue.cnn.cnn_rangapur import get_transforms
    if model is None:
        model, _ = load_scorer(model_path, None, positive_class)
    else:
        _check_classes(model_path, _n_classes_of(model), positive_class)
    transform = get_transforms(int(img_size), is_train=False, is_rgb=True)
    out = np.zeros(len(stack), dtype=float)
    for b0 in range(0, len(stack), int(batch_size)):
        batch = [transform(Image.fromarray(np.asarray(img, dtype=np.uint8), mode="RGB"))
                 for img in stack[b0:b0 + int(batch_size)]]
        out[b0:b0 + len(batch)] = predict(model, batch, positive_class)
    return out


def _check_params(image_type, resample_to, img_size, batch_size):
    if image_type not in IMAGE_TYPES:
        raise ValueError(f"image_type {image_type!r} is not one of {', '.join(IMAGE_TYPES)}.")
    if resample_to and not MIN_POINTS <= int(resample_to) <= MAX_POINTS:
        raise ValueError(f"resample_to={resample_to}: use 0 (each window as is) or {MIN_POINTS}…{MAX_POINTS} "
                         f"points (the recurrence plot's embedding, m = 3 and τ = 4, needs more than 8; "
                         f"{TRAINING_LENGTH} is the training geometry).")
    if not 8 <= int(img_size) <= 1024:
        raise ValueError(f"img_size={img_size} must be 8…1024 pixels.")
    if not 1 <= int(batch_size) <= 1024:
        raise ValueError(f"batch_size={batch_size} must be 1…1024 windows.")


def score_windows(x, starts, length, *, image_type, model_path, resample_to=TRAINING_LENGTH, img_size=224,
                  batch_size=64, positive_class=0, on_progress=None, should_cancel=None, model=None):
    """P(positive_class) for every window `x[s:s + length]`, `s` in `starts` (span-relative), and the meta a
    page shows beside it. See the module docstring for the rules.

    `on_progress(done, total, label)` fires after every batch; `should_cancel()` is asked before every batch
    and on True the run raises `Working.execution.RecipeCancelled`. `model` (an already-built two-class
    network) skips loading `model_path`, which is then only recorded — for the cost calibration and tests."""
    from Working.Catalogue.cnn.cnn_rangapur import get_transforms

    _check_params(image_type, resample_to, img_size, batch_size)
    x = np.asarray(x, dtype=float)
    starts = np.asarray(starts, dtype=np.int64).ravel()
    L, n = int(length), len(starts)
    resample_to, batch_size = int(resample_to), int(batch_size)
    if n and not resample_to and not MIN_POINTS <= L <= MAX_POINTS:
        raise ValueError(
            f"resample_to=0 keeps each window's own {L} samples, but the encoder takes {MIN_POINTS}…{MAX_POINTS} "
            f"points (an L × L picture: {L} samples would be {L * L * 8 / 1e9:.2g} GB a matrix); set "
            f"resample_to ({TRAINING_LENGTH} is the training geometry).")
    for i, s in enumerate(starts):
        if s < 0:
            raise ValueError(f"window {i} starts at span sample {s}, before this span.")
        if s + L > len(x):
            raise ValueError(f"window {i} at span sample {s} runs past the span ({len(x)} samples, window {L}).")

    if model is None:
        model, n_classes = load_scorer(model_path, image_type, positive_class)
    else:
        _check_name(model_path, image_type)
        n_classes = _n_classes_of(model)
        _check_classes(model_path, n_classes, positive_class)

    probs = np.full(n, np.nan)
    skipped = {"nan": 0, "flat": 0}
    keep = []
    for i, s in enumerate(starts):
        w = x[s:s + L]
        if not np.isfinite(w).all():
            skipped["nan"] += 1
        elif w.max() == w.min():
            skipped["flat"] += 1
        else:
            keep.append(i)
    keep = np.asarray(keep, dtype=np.int64)

    transform = get_transforms(int(img_size), is_train=False, is_rgb=(image_type == "fusion"))
    n_batches = math.ceil(len(keep) / batch_size)
    t0 = time.perf_counter()
    for b in range(n_batches):
        if should_cancel is not None and should_cancel():
            raise _cancelled()(f"CNN window scores cancelled after {b} of {n_batches} batches "
                               f"({b * batch_size:,} of {len(keep):,} windows scored)")
        chunk = keep[b * batch_size:(b + 1) * batch_size]
        batch = [transform(window_image(x[starts[i]:starts[i] + L], image_type, img_size, resample_to))
                 for i in chunk]
        probs[chunk] = predict(model, batch, positive_class)
        del batch
        if on_progress is not None:
            on_progress(b + 1, n_batches, f"batch {b + 1} of {n_batches}")
    elapsed = time.perf_counter() - t0

    scored = probs[np.isfinite(probs)]
    meta = {
        "model_path": str(model_path), "n_classes": int(n_classes), "positive_class": int(positive_class),
        "image_type": image_type, "resample_to": resample_to,
        "resample_factor": float(resample_to / L) if resample_to and L else 1.0,
        "window_length": L, "n_windows": int(n), "n_scored": int(len(scored)), "skipped": skipped,
        "window_scores": [float(p) if np.isfinite(p) else None for p in probs[:META_CAP]],
        "p_range": [float(scored.min()), float(scored.max())] if len(scored) else None,
        "p_quantiles": ({k: float(np.quantile(scored, q)) for k, q in (("5", 0.05), ("50", 0.5), ("95", 0.95))}
                        if len(scored) else None),
        "seconds_per_window": float(elapsed / len(scored)) if len(scored) else None,
        "training_scale": TRAINING_SCALE,
        "rules": [dict(r) for r in RULES],
    }
    if n == 0:
        meta["note"] = ("no window to score: the window set is empty (no window fits the span, or the step "
                        "before produced none)")
    elif not len(scored):
        meta["note"] = (f"no window could be scored: {skipped['nan']} held NaN and {skipped['flat']} were flat")
    return probs, meta
