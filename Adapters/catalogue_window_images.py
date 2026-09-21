"""
catalogue_window_images.py
============================
WindowSet → Encoding (image stack): one Gramian-family image per window,
built exactly as the CNN training set was (`Working.Catalogue.cnn.apply_cnn.
_window_to_pil`: fusion RGB, or GASF / GADF / recurrence as L → RGB), at the
model's input size. Spec §6.8 "WindowSet → Encoding (image: GASF, GADF, RP,
fusion)", training block 04; the stack feeds `catalogue.cnn_score`.

The stack is `(n_windows, img_size, img_size, 3)` uint8 — the pixels the
CNN sees, so what the block page shows is what the model scores. A cap on
the number of windows keeps a whole-channel window set from allocating a
multi-gigabyte stack; the executor refuses over `max_windows` with the size.
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.types import Encoding

IMAGE_TYPES = ("fusion", "GASF", "GADF", "recurrence")


def _run(x, t, fs, image_type="fusion", img_size=224, max_windows=2000, value=None):
    if value is None:
        raise ValueError("catalogue.window_images requires a WindowSet input from a prior step (input_kind='windowset').")
    from PIL import Image
    from Working.Catalogue.cnn.apply_cnn import _window_to_pil

    starts = np.asarray(value.starts, dtype=np.int64)
    n = len(starts)
    if n > max_windows:
        raise ValueError(
            f"{n} windows × {img_size}×{img_size}×3 bytes = {n * img_size * img_size * 3 / 1e6:.0f} MB exceeds "
            f"max_windows={max_windows}; shorten the span, lengthen the stride, or raise max_windows.")
    x = np.asarray(x, dtype=float)
    L = int(value.length)
    stack = np.zeros((n, img_size, img_size, 3), dtype=np.uint8)
    for i, s in enumerate(starts):
        w = x[s:s + L]
        if len(w) < L:
            raise ValueError(f"window {i} at {s} runs past the span ({len(x)} samples).")
        pil = _window_to_pil(w, image_type).resize((img_size, img_size), Image.BILINEAR)
        stack[i] = np.asarray(pil, dtype=np.uint8)
    return AdapterResult(
        output_kind="encoding",
        value=Encoding(values=stack, kind="image"),
        meta={"image_type": image_type, "img_size": int(img_size), "n_windows": int(n), "window_length": L,
              "starts": starts[:4096].tolist(), "fs": float(value.fs)},
    )


def _derive(x, t, fs, params, value=None):
    if value is None:
        return [("Images", "run a windows block first", "warn")]
    n = len(value.starts); s = params["img_size"]
    mb = n * s * s * 3 / 1e6
    return [("Images", f"{n} × {s}×{s}×3", "error" if n > params["max_windows"] else ""),
            ("Stack size", f"{mb:.0f} MB", "warn" if mb > 500 else "")]


SPEC = register(AdapterSpec(
    name="catalogue.window_images",
    display_name="Window images (WindowSet -> Encoding stack)",
    stage="catalogue",
    category="encode",
    page_name="Encode windows",
    params=[
        ParamSpec("image_type", str, "fusion", "Which Gramian-family image (fusion is the RGB the CNNs were trained on)", choices=list(IMAGE_TYPES)),
        ParamSpec("img_size", int, 224, "Image side in pixels (the CNN input size)", min=8, max=1024),
        ParamSpec("max_windows", int, 2000, "Refuse a window set larger than this (memory guard)", min=1),
    ],
    run=_run,
    derive=_derive,
    input_kind="windowset",
    output_kind="encoding",
    description=(
        "One Gramian-family image per window, exactly as the CNN training set was built; "
        "the stack a CNN scoring block consumes."
    ),
))
