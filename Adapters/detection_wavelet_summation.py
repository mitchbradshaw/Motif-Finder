"""
detection_wavelet_summation.py
================================
Stage 2 of the Dehshibi & Adamatzky (2021) template: Ω(τ) = Σ_s g(τ, s).

Encoding (image, scales × time) → Scores, one value per timepoint. The first
block in the registry that consumes an `Encoding` (stage-3 D2: encodings are
no longer terminal display blocks). A column that is NaN in the input (a
chunk the transform skipped) stays NaN here, so the threshold block can tell
"no evidence" from "zero evidence".

Any scales × time image whose columns are the span's samples is accepted —
a future transform block with the same output shape can feed the same
summation and threshold.
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec
from Adapters.registry import register
from Working.types import Scores


def _run(x, t, fs, value=None):
    if value is None:
        raise ValueError("detection.wavelet_summation requires an Encoding input from a prior step (input_kind='encoding').")
    if getattr(value, "kind", None) != "image":
        raise ValueError(
            f"detection.wavelet_summation sums a scales × time image; got an Encoding of kind "
            f"{getattr(value, 'kind', None)!r}. Put Wavelet transform before it.")
    g = np.asarray(value.values, dtype=float)
    if g.ndim != 2 or g.shape[1] != len(x):
        raise ValueError(
            f"detection.wavelet_summation expects an image with one column per sample "
            f"(shape (scales, {len(x)})); got {g.shape}.")
    omega = g.sum(axis=0)           # NaN columns stay NaN
    return AdapterResult(
        output_kind="scores",
        value=Scores(values=omega, fs=float(fs)),
        meta={"n_scales": int(g.shape[0]), "n_nan": int(np.isnan(omega).sum())},
    )


SPEC = register(AdapterSpec(
    name="detection.wavelet_summation",
    display_name="Wavelet summation Ω(τ) (Dehshibi stage 2)",
    stage="detection",
    category="detect",
    page_name="Wavelet summation",
    params=[],
    run=_run,
    input_kind="encoding",
    output_kind="scores",
    description=(
        "Ω(τ) = Σ_s g(τ, s): collapses the normalised Morse coefficients to one "
        "value per sample — the series Algorithm 1 finds its extrema on."
    ),
))
