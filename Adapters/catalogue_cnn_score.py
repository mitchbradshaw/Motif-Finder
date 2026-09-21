"""
catalogue_cnn_score.py
========================
Encoding (image stack) + WindowSet → Scores: P("interesting") per window
from a trained CNN, laid onto the time axis (stage-3 D2, the researcher's
answer: CNN scoring from `apply_cnn.py` as encoding → scores).

`Working.Catalogue.cnn.apply_cnn` is used as-is: `load_model` (an
`EEG_CNN` state dict) and the same `get_transforms(img_size, is_train=False,
is_rgb=True)` pipeline over the images `catalogue.window_images` built. The
window geometry comes back as the `windows` side input (the WindowSet the
images were cut from), because an Encoding carries no time. Each window's
score fills its samples; samples no window covers are NaN; where windows
overlap the later window wins (the same convention `add_cnn_scores` uses
for the window matrix).

`model_path` is a parameter: the registry Prompt 02 built
(`registered_artifacts(kind='model')`, `docs/DATA_REGISTRATION.md`) lists
the checkpoints and the block page offers them; the recipe records the path
so a run is reproducible without the registry. Inference is torch on CPU
unless a GPU is present; `estimate` answers from the calibration file.
"""

import os

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec, SideInputSpec
from Adapters.registry import register
from Working.block_cost import estimate_seconds, register_cost_model
from Working.types import Scores

DEFAULT_MODEL = os.path.join("MODELS", "fusion_cnn.pth")
COST_MODEL = "catalogue.cnn_score"


def _time_once(x, fs):
    """Score one 600 s window per 600 samples of the calibration signal (needs the default checkpoint)."""
    n = len(x); L = min(600, max(8, n // 20)); k = max(1, n // L)
    stack = np.random.default_rng(0).integers(0, 255, size=(min(k, 32), 224, 224, 3), dtype=np.uint8)
    score_stack(stack, DEFAULT_MODEL, img_size=224, batch_size=32)


register_cost_model(COST_MODEL, 1.0, _time_once)


def score_stack(stack, model_path, img_size=224, batch_size=32):
    """P(interesting) for each image of an `(n, H, W, 3)` uint8 stack."""
    import torch
    from PIL import Image
    from Working.Catalogue.cnn.apply_cnn import load_model
    from Working.Catalogue.cnn.cnn_rangapur import get_transforms

    if not os.path.isfile(model_path):
        raise ValueError(f"catalogue.cnn_score: model_path {model_path!r} does not exist; register a checkpoint in Settings › Models.")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_model(model_path, device)
    transform = get_transforms(img_size, is_train=False, is_rgb=True)
    out = np.zeros(len(stack), dtype=float)
    with torch.no_grad():
        for b0 in range(0, len(stack), batch_size):
            imgs = [transform(Image.fromarray(np.asarray(img, dtype=np.uint8), mode="RGB")).unsqueeze(0) for img in stack[b0:b0 + batch_size]]
            logits = model(torch.cat(imgs, dim=0).to(device))
            probs = torch.softmax(logits, dim=1)[:, 0].cpu().numpy()   # class 0 = "interesting" (ImageFolder order)
            out[b0:b0 + len(probs)] = probs
    return out


def _run(x, t, fs, model_path=DEFAULT_MODEL, img_size=224, batch_size=32, value=None, windows=None):
    if value is None or getattr(value, "kind", None) != "image":
        raise ValueError("catalogue.cnn_score requires an image-stack Encoding from Window images (input_kind='encoding').")
    if windows is None:
        raise ValueError("catalogue.cnn_score needs its 'windows' side input: bind {'windows': {'source_kind': 'earlier_step', 'step_index': <the windows step>}}.")
    stack = np.asarray(value.values)
    if stack.ndim != 4 or stack.shape[-1] != 3:
        raise ValueError(f"catalogue.cnn_score expects an (n, H, W, 3) image stack; got shape {stack.shape}.")
    if len(stack) != windows.n_windows:
        raise ValueError(f"{len(stack)} images for {windows.n_windows} windows — the stack and the window set must come from the same step.")
    probs = score_stack(stack, model_path, img_size=img_size, batch_size=batch_size)
    scores = np.full(len(x), np.nan)
    L = int(windows.length)
    # WindowSet.starts are channel-absolute; the Scores are over the span
    span_start = int(round(float(t[0]) * fs)) if t is not None and len(t) else 0
    for s, p in zip(np.asarray(windows.starts, dtype=np.int64) - span_start, probs):
        if 0 <= s < len(x):
            scores[s:s + L] = p
    return AdapterResult(
        output_kind="scores",
        value=Scores(values=scores, fs=float(fs)),
        meta={"model_path": model_path, "n_windows": int(len(probs)), "window_scores": probs.tolist()[:4096],
              "starts": np.asarray(windows.starts)[:4096].tolist(), "length": L,
              "p_range": [float(probs.min()), float(probs.max())] if len(probs) else None},
    )


def _estimate(x, t, fs, **params):
    return estimate_seconds(COST_MODEL, len(x))


SPEC = register(AdapterSpec(
    name="catalogue.cnn_score",
    display_name="CNN score (image stack + windows -> Scores)",
    stage="catalogue",
    category="model",
    page_name="Model stage (CNN)",
    params=[
        ParamSpec("model_path", str, DEFAULT_MODEL, "Checkpoint (.pth, EEG_CNN state dict) — pick from Settings › Models & registration"),
        ParamSpec("img_size", int, 224, "CNN input size (the images are resized to this)", min=8, max=1024),
        ParamSpec("batch_size", int, 32, "Windows per inference batch", min=1, max=1024),
    ],
    run=_run,
    estimate=_estimate,
    input_kind="encoding",
    output_kind="scores",
    side_inputs=[SideInputSpec(name="windows", type_kind="windowset", sources=["earlier_step"])],
    description=(
        "P(interesting) per window from a trained fusion CNN, laid onto the time axis; "
        "feed it to Threshold to spans to detect with a model."
    ),
))
