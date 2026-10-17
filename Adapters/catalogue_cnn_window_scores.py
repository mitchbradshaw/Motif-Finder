"""
catalogue_cnn_window_scores.py
================================
WindowSet → Scores: the researcher's trained CNNs' P(interesting) for every
window, at any window length (W4-A, 2026-10-17, for the RQ4 detection sweep
and Discovery › Map). Each window is resampled to the training geometry
(600 points), drawn as the picture its model was trained on, and scored a
batch at a time; the probability fills the window's samples, so Threshold
turns the confident windows into detections. The rules, the refusals and
the reasons are in `Working.Catalogue.cnn.window_scores`.

Why not `window_images → cnn_score`: that chain holds every picture at once
(it refuses over 2,000 windows; one 721-h channel at 1-minute windows is
43,260) and never resamples, so neither a 1-minute nor a 1-hour window
reaches the model at the geometry it learned on. This block keeps at most
`batch_size` pictures alive and checks for a cancel between batches.

WindowSet starts are channel-absolute; the span's offset, `round(t[0]·fs)`,
is subtracted before slicing `x` (as `catalogue.window_images` does). The
Scores have one value per sample of the span: each window's score fills its
own samples, the later window wins where windows overlap (as `cnn_score`),
and samples no window reaches are NaN.

**Cost.** `estimate` sees the span and this block's parameters, not the
windows, so it ASSUMES one window per 600 samples (the training geometry:
10-minute windows at 1 Hz) and the fusion picture (the dearest of the four,
about 2.4× the single-picture types). A 1-minute window set at 1 Hz has ten
times as many windows and costs about ten times the estimate; a 1-hour one
about a sixth. The calibration times the work on random weights held in
memory (no checkpoint file needed), with the torch import and the model build
as the untimed warm-up.
"""

import os

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.block_cost import estimate_seconds, register_cost_model
from Working.Catalogue.cnn import window_scores as WS
from Working.types import Scores

DEFAULT_MODEL = os.path.join("MODELS", "fusion_cnn_3.pth")
COST_MODEL = "catalogue.cnn_window_scores"
_CALIBRATION = {}


def _warm_up():
    """Untimed: import torch and build a random-weight two-class network (no download)."""
    if "model" not in _CALIBRATION:
        from Working.Catalogue.cnn.cnn_rangapur import EEG_CNN
        _CALIBRATION["model"] = EEG_CNN(num_classes=2, pretrained=False).to(WS._device()).eval()


def _time_once(x, fs):
    """Score the calibration signal's 600-sample windows (fusion, 224 px, the default batch)."""
    _warm_up()
    L = WS.TRAINING_LENGTH
    starts = np.arange(0, len(x) - L + 1, L)
    WS.score_windows(x, starts, L, image_type="fusion", model_path="(calibration: random weights)",
                     model=_CALIBRATION["model"])


register_cost_model(COST_MODEL, 1.0, _time_once, warm_up=_warm_up)


def _estimate(x, t, fs, **params):
    """Seconds for this span at one 600-sample fusion window per 600 samples (see the module docstring for
    what that assumes); None until `Working.block_cost.calibrate()` has timed it on this machine."""
    return estimate_seconds(COST_MODEL, len(x))


def _summary(meta, n_windows):
    if not n_windows:
        return "no window to score: the window set is empty"
    q = meta.get("p_quantiles")
    head = f"{meta['n_scored']:,} of {n_windows:,} windows scored"
    if q:
        head += f" · P(interesting) median {q['50']:.2f}, 95th percentile {q['95']:.2f}"
    left = [f"{k} {v}" for k, v in meta["skipped"].items() if v]
    return head + (f" · left out: {', '.join(left)}" if left else "")


def _warnings(meta, L, fs):
    out = []
    if meta["skipped"]["nan"]:
        out.append(f"{meta['skipped']['nan']} window(s) hold NaN (a gap) and were not scored")
    if meta["skipped"]["flat"]:
        out.append(f"{meta['skipped']['flat']} window(s) are flat (max = min) and were not scored")
    if L and (L != WS.TRAINING_LENGTH or float(fs) != 1.0):
        out.append(f"windows of {L / fs:g} s at {fs:g} Hz ({L} samples) are outside the training scale "
                   f"(600-sample, 10-minute windows at 1 Hz): read these scores as exploratory")
    return out


def _run(x, t, fs, image_type="fusion", model_path=DEFAULT_MODEL, resample_to=WS.TRAINING_LENGTH, img_size=224,
         batch_size=64, positive_class=0, value=None, on_progress=None, should_cancel=None):
    if value is None:
        raise ValueError("catalogue.cnn_window_scores needs a WindowSet from a prior step (input_kind='windowset'): "
                         "put Sliding windows before it.")
    x = np.asarray(x, dtype=float)
    L = int(value.length)
    abs_starts = np.asarray(value.starts, dtype=np.int64)
    # WindowSet.starts are channel-absolute; `x` is the span — subtract the span's offset (t[0] * fs)
    span_start = int(round(float(t[0]) * fs)) if t is not None and len(t) else 0
    starts = abs_starts - span_start
    probs, meta = WS.score_windows(
        x, starts, L, image_type=image_type, model_path=model_path, resample_to=resample_to, img_size=img_size,
        batch_size=batch_size, positive_class=positive_class, on_progress=on_progress,
        should_cancel=should_cancel)
    scores = np.full(len(x), np.nan)
    for s, p in zip(starts, probs):         # the later window wins where windows overlap
        scores[s:s + L] = p
    meta.update({
        "window_s": float(L / fs), "fs": float(fs), "span_start": span_start,
        "starts": abs_starts[:WS.META_CAP].tolist(),
        "summary": _summary(meta, len(starts)),
        "warnings": _warnings(meta, L, fs) if len(starts) else [],
    })
    meta["rules"].append({"name": "layout",
                          "rule": "Each window's score fills its own samples of the span; where windows overlap "
                                  "the later window wins; samples no window reaches are NaN."})
    return AdapterResult(output_kind="scores", value=Scores(values=scores, fs=float(fs)), meta=meta)


def _derive(x, t, fs, params, value=None):
    if value is None:
        return [("Windows", "run a windows block first", "warn")]
    n, L = len(value.starts), int(value.length)
    rs = int(params["resample_to"])
    rows = [("Windows", f"{n:,} × {L} samples ({L / fs:g} s)", "warn" if n == 0 else ""),
            ("Resampled to", f"{rs} points" if rs else f"{L} points (as is)",
             "error" if not rs and not WS.MIN_POINTS <= L <= WS.MAX_POINTS else "")]
    if L != WS.TRAINING_LENGTH or float(fs) != 1.0:
        rows.append(("Training scale", "outside it: trained on 600-sample, 10-minute windows at 1 Hz", "warn"))
    return rows


SPEC = register(AdapterSpec(
    name="catalogue.cnn_window_scores",
    display_name="CNN window scores (WindowSet -> Scores)",
    stage="catalogue",
    category="model",
    page_name="CNN window scores",
    params=[
        ParamSpec("image_type", str, "fusion", "Which picture the model reads: it must be the kind the checkpoint "
                  "was trained on (its file name says which)", choices=list(WS.IMAGE_TYPES)),
        ParamSpec("model_path", str, DEFAULT_MODEL, "Checkpoint (.pth, a two-class EEG_CNN state dict) — pick from "
                  "Settings › Models & registration"),
        ParamSpec("resample_to", int, WS.TRAINING_LENGTH, "Points each window is resampled to before it is drawn "
                  "(600 = the training windows; 0 = as is, 16–2048 samples)", min=0, max=WS.MAX_POINTS),
        ParamSpec("img_size", int, 224, "CNN input size in pixels (the training size is 224)", min=8, max=1024),
        ParamSpec("batch_size", int, 64, "Windows per inference batch (at most this many pictures in memory)",
                  min=1, max=1024),
        ParamSpec("positive_class", int, 0, "Which output is scored: 0 = 'interesting' (ImageFolder's alphabetical "
                  "order)", min=0, max=1),
    ],
    run=_run,
    estimate=_estimate,
    derive=_derive,
    input_kind="windowset",
    output_kind="scores",
    description=(
        "Asks one of the researcher's trained CNNs how interesting each window looks: every window is resampled "
        "to 600 points, drawn as the picture the model learned on, and scored P(interesting) from 0 to 1; the "
        "score fills the window on the time axis. Follow it with Threshold to turn the confident windows into "
        "detections, and tune Threshold's threshold first. The models were trained on 600-sample, 10-minute "
        "windows of M2_aug at 1 Hz: other window lengths are outside that scale, and M2_aug's own scores are not "
        "out-of-sample. Windows holding NaN or flat are left out and counted."
    ),
))
