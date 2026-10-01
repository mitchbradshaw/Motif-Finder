"""
detection_wavelet_summation.py
================================
Stage 2 of the Dehshibi & Adamatzky (2021) template: Ω(τ), the sum over a
BAND of rows of a time-aligned image.

Encoding (image, rows × time) → Scores, one value per timepoint. The authors'
code (`iApplyWavelet.m`, method 2) does not sum every frequency: Ω is the sum
of the rows at or below a quarter of the frequency range. The band is given
here as a FRACTION of the image's rows (`row_from` … `row_to`, rows counted
from the low-frequency end) because an `Encoding` carries no frequency axis
and a block does not see the previous block's `meta` (fixup-J). The template
passes the authors' fraction for its default window; `Wavelet transform`
prints the fraction for any other window in its own readout.

**The image contract**: one column per sample of the span, rows ordered low
to high. Any block that emits such an image can feed this one — and any
block that emits a Scores with one value per sample can REPLACE this one in
front of `detection.summation_threshold`.

A column that is NaN in the input (a chunk the transform could not analyse)
stays NaN here, so the next block can tell "no evidence" from "zero evidence".
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.types import Scores


def band_rows(n_rows, row_from, row_to):
    """`[lo, hi)` in rows for a band given as fractions of the image height."""
    return int(round(row_from * n_rows)), int(round(row_to * n_rows))


def _run(x, t, fs, row_from=0.0, row_to=1.0, value=None):
    if value is None:
        raise ValueError("detection.wavelet_summation requires an Encoding input from a prior step (input_kind='encoding').")
    if getattr(value, "kind", None) != "image":
        raise ValueError(
            f"detection.wavelet_summation sums a rows × time image; got an Encoding of kind "
            f"{getattr(value, 'kind', None)!r}. Put Wavelet transform before it.")
    g = np.asarray(value.values)
    if g.ndim != 2 or g.shape[1] != len(x):
        raise ValueError(
            f"detection.wavelet_summation expects an image with one column per sample "
            f"(shape (rows, {len(x)})); got {g.shape}.")
    lo, hi = band_rows(g.shape[0], row_from, row_to)
    if hi <= lo:
        raise ValueError(
            f"detection.wavelet_summation: the band row_from={row_from:g} … row_to={row_to:g} holds no row "
            f"of a {g.shape[0]}-row image.")
    omega = g[lo:hi].astype(float).sum(axis=0)          # NaN columns stay NaN
    return AdapterResult(
        output_kind="scores",
        value=Scores(values=omega, fs=float(fs)),
        meta={"n_rows": int(g.shape[0]), "rows_used": [lo, hi], "n_nan": int(np.isnan(omega).sum())},
    )


SPEC = register(AdapterSpec(
    name="detection.wavelet_summation",
    display_name="Wavelet summation Ω(τ) (Dehshibi stage 2)",
    stage="detection",
    category="detect",
    page_name="Wavelet summation",
    params=[
        ParamSpec("row_from", float, 0.0, "Lowest row summed, as a fraction of the image height (0 = the lowest frequency)", min=0.0, max=1.0),
        ParamSpec("row_to", float, 1.0, "Highest row summed, as a fraction of the image height (the authors' low band is about 0.76 of a 3000 s Morse scalogram)", min=0.0, max=1.0),
    ],
    run=_run,
    input_kind="encoding",
    output_kind="scores",
    description=(
        "Ω(τ): sums a band of rows of a time-aligned image to one value per sample — the "
        "series the next block finds its extrema on. The authors of Dehshibi & Adamatzky 2021 "
        "sum only the low frequencies; the template sets that band."
    ),
))
