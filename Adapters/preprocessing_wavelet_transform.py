"""
preprocessing_wavelet_transform.py
====================================
Stage 1 of the Dehshibi & Adamatzky (2021) spike detector as its own block
(stage-3 decision 2: a multi-stage detector is a TEMPLATE of typed blocks,
not one adapter). The template `dehshibi_spikes` is

    preprocessing.wavelet_transform   Signal   → Encoding (image, frequency × time)
    detection.wavelet_summation       Encoding → Scores   (Ω(τ), a band of rows summed)
    detection.summation_threshold     Scores   → SpanSet  (regions, split, envelope, merge)

This block is `iApplyWavelet.m` up to its `switch`: MATLAB's default `cwt`
(analytic Morse wavelet γ = 3, βγ = 60, ten voices per octave, the signal
extended by reflection), the modulus, and per frequency
`1 + fix(η · (|W| − min) / max)`. It follows the AUTHORS' code (Zenodo
10.5281/zenodo.3997031), not the printed Eq. (2)–(3) — fixup-J, QUESTIONS.md
Q33; `Working/Detection/analysis/dehshibi_authors.py` is the port and
`tests/test_dehshibi_authors.py` checks it against MATLAB.

**The image contract** (what `detection.wavelet_summation` relies on, and
what a replacement transform must honour): one column per sample of the
span, rows ordered LOW to HIGH frequency. `meta["freqs_hz"]` names the rows.

The span is transformed in fixed windows (`window_s`, the paper's 3000 s) or,
with `slice_by_state`, in the pieces the authors' `iSplitSignal` cuts at the
recording's state transitions. Either way EVERY sample is analysed — before
fixup-J the slicing discarded whatever sat above the span's mid-level, 87 %
of a typical four hours. The normalisation is per window, so the window
length is the method's real parameter.

Why an Encoding and not Scores: the next step sums a band of this matrix;
emitting only the sum would fold two steps into one block and hide the
picture the researcher reads the detector against.

*** MEMORY GUARD ***: the output is a rows × n float32 matrix, so the block
declares `max_span_samples` (the arithmetic is beside the constant) and
`Working.execution.execute_recipe` refuses a longer span with the reason
before anything is allocated.
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.block_cost import estimate_seconds, register_cost_model
from Working.Detection.analysis.dehshibi_authors import (
    BETA, ETA, GAMMA, WINDOW_S, low_band_rows, morse_scales, samples, transform,
)
from Working.types import Encoding

COST_MODEL = "preprocessing.wavelet_transform"

#: *** MEMORY GUARD ***, same budget and same mechanism as the four gramian
#: blocks (`catalogue_gramian_gasf.py`: 5,000 samples for a 5000x5000x8 B =
#: 200 MB matrix). Peak live bytes per span sample. The scalogram is built one
#: frequency at a time, so the transient is a few padded complex rows:
#:
#:     image       MAX_ROWS x 4 B (float32)  =  512 B/sample   held for the whole run
#:     transient   the padded chunk's FFT, one filter, one product, one inverse
#:                 (2x the chunk, complex)   ~  112 B/sample
#:                                             ----------------
#:                                              624 B/sample
#:
#: 200,000,000 / 624 = 320,512 -> 320,000 samples (88.9 h at 1 Hz). A 3000 s
#: window makes 87 rows; a window long enough to need more than MAX_ROWS is
#: refused in `_run`, so the arithmetic above cannot be outrun by a parameter.
MAX_ROWS = 128
PEAK_BYTES_PER_SAMPLE = MAX_ROWS * 4 + 112                  # 624
BLOCK_MEMORY_BUDGET_BYTES = 5000 * 5000 * 8                 # the gramian blocks' 200 MB
MAX_SPAN_SAMPLES = 320_000


def _rows_for(n, fs, window_s, slice_by_state, beta, gamma):
    w = samples(window_s, fs)
    return len(morse_scales(w if slice_by_state else min(w, max(n, 1)), beta=beta, gamma=gamma))


def _run(x, t, fs, window_s=WINDOW_S, slice_by_state=False, beta=BETA, gamma=GAMMA, eta=ETA,
         min_chunk_samples=0):
    x = np.asarray(x, dtype=float).ravel()
    rows = _rows_for(len(x), fs, window_s, slice_by_state, beta, gamma)
    if rows > MAX_ROWS:
        raise ValueError(
            f"preprocessing.wavelet_transform: a {window_s:g} s window at {fs:g} Hz needs {rows} rows of "
            f"frequencies; the block holds at most {MAX_ROWS} (its span cap is computed from that). "
            f"Shorten the window.")
    img, freqs, chunks = transform(x, fs=fs, window_s=window_s, slice_by_state=slice_by_state,
                                   eta=eta, beta=beta, gamma=gamma)
    k = int(low_band_rows(freqs).sum())
    skipped = sum(1 for a, b in chunks if not np.isfinite(img[0, a:b + 1]).all())
    return AdapterResult(
        output_kind="encoding",
        value=Encoding(values=img, kind="image"),
        meta={"n_chunks": len(chunks), "n_chunks_skipped": skipped, "n_rows": int(img.shape[0]),
              "chunks": [[int(a), int(b) + 1] for a, b in chunks],
              "freqs_hz": [float(f) for f in freqs],
              # the rows the authors sum into Omega (frequencies <= a quarter of the range),
              # as the fraction `detection.wavelet_summation` takes for `row_to`
              "authors_band": {"rows": k, "row_to": k / float(img.shape[0])}},
    )


def _estimate(x, t, fs, **params):
    return estimate_seconds(COST_MODEL, len(x))


register_cost_model(COST_MODEL, 1.1, lambda x, fs: transform(x, fs=fs))


def _derive(x, t, fs, params):
    n = len(x)
    rows = _rows_for(n, fs, params["window_s"], params["slice_by_state"], params["beta"], params["gamma"])
    w = samples(params["window_s"], fs)
    freqs = (params["beta"] / params["gamma"]) ** (1.0 / params["gamma"]) / (
        2.0 * np.pi * morse_scales(min(w, max(n, 1)), beta=params["beta"], gamma=params["gamma"])) * fs
    k = int(low_band_rows(freqs).sum())
    return [
        ("Windows", "by state transitions" if params["slice_by_state"] else str(max(1, int(round(n / w)))), ""),
        ("Frequency rows", str(rows), "warn" if rows > MAX_ROWS else ""),
        ("Authors' low band (row_to for Wavelet summation)", f"{k} of {rows} rows = {k / rows:.4f}", ""),
    ]


SPEC = register(AdapterSpec(
    name="preprocessing.wavelet_transform",
    display_name="Morse wavelet transform (Dehshibi stage 1)",
    stage="preprocessing",
    category="encode",
    page_name="Wavelet transform",
    params=[
        ParamSpec("window_s", float, WINDOW_S,
                  "Window length in seconds; each window is normalised on its own (paper: 3000 s pieces)", min=10.0),
        ParamSpec("slice_by_state", bool, False,
                  "Cut at the recording's state transitions (the authors' iSplitSignal) instead of fixed windows"),
        ParamSpec("beta", float, BETA, "Morse wavelet β (authors: 20; βγ = 60)", min=1.0),
        ParamSpec("gamma", float, GAMMA, "Morse wavelet γ (authors: 3)", min=1.0),
        ParamSpec("eta", float, ETA, "Scaling factor η (authors: 240)", min=1e-6),
        ParamSpec("min_chunk_samples", int, 0,
                  "Not used since fixup-J (every sample is analysed); accepted so an old recipe still runs", min=0),
    ],
    run=_run,
    estimate=_estimate,
    derive=_derive,
    input_kind="signal",
    output_kind="encoding",
    max_span_samples=MAX_SPAN_SAMPLES,
    description=(
        "The scalogram of Dehshibi & Adamatzky 2021 as the authors' code builds it: analytic "
        "Morse transform with reflected ends, modulus, scaled per frequency to 1–241, window "
        "by window. A frequency × time image, low frequencies first, one column per sample; "
        f"feed it to Wavelet summation. Capped at {MAX_SPAN_SAMPLES:,} samples (the 200 MB "
        "budget the gramian blocks cap at)."
    ),
))
