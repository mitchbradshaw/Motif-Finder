"""
preprocessing_wavelet_transform.py
====================================
Stage 1 of the Dehshibi & Adamatzky (2021) spike detector as its own block
(stage-3 decision 2: a multi-stage detector is a TEMPLATE of typed blocks,
not one adapter). The template `dehshibi_spikes` is

    preprocessing.wavelet_transform   Signal   → Encoding (image, scales × time)
    detection.wavelet_summation       Encoding → Scores   (Ω(τ) = Σ_s g(τ, s))
    detection.summation_threshold     Scores   → SpanSet  (Algorithms 1–4)

This block: slice the span into chunks on histogram state transitions
(Sect. 3.1, `slice_signal`), take the Morse continuous wavelet transform of
each chunk (Sect. 3.2, Eq. 2) and normalise it per scale (Eq. 3), exactly as
`detect_spikes` does per chunk. The output is the normalised coefficient
matrix g(τ, s) laid back onto the span's time axis — an `Encoding` of kind
`image` with one column per sample, `NaN` for a chunk too short to analyse
(the monolith skips those chunks; here the gap is explicit so the next block
can see it).

Why an Encoding and not Scores: the paper's next step consumes the whole
scale × time matrix (it sums it); emitting only the sum here would fold two
steps into one block and hide the picture the researcher tunes β/γ against.

*** MEMORY GUARD ***: the output is a 64 x n float matrix and the transform
holds another ~2.5 KB per sample while it builds each chunk, so the block
declares `max_span_samples` (see the constant below for the arithmetic) and
`Working.execution.execute_recipe` refuses a longer span with the reason
before anything is allocated.

Chunking lives here and is recomputed in `detection.summation_threshold`
from the same signal with the same rule (`slice_signal` is deterministic and
parameter-free), so the two blocks agree without a hidden side channel.
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.block_cost import estimate_seconds, register_cost_model
from Working.Detection.analysis.dehshibi_detection_analysis import (
    BETA, ETA, GAMMA, N_P,
    compute_morse_wavelet_transform, normalise_wavelet_coefficients, slice_signal,
)
from Working.types import Encoding

N_SCALES = 64          # what `compute_morse_wavelet_transform` builds when scales=None
COST_MODEL = "preprocessing.wavelet_transform"

#: *** MEMORY GUARD ***, same budget and same mechanism as the four gramian
#: blocks (`catalogue_gramian_gasf.py`: 5,000 samples for a 5000x5000x8 B =
#: 200 MB matrix). Peak live bytes per span sample, worst case - one chunk
#: covering the whole span, which is exactly what `slice_signal` returns when
#: it finds no transition:
#:
#:     g_all          N_SCALES x 8 B  =   512 B/sample   held for the whole run
#:     phi            N_SCALES x 16 B =  1024 B/sample   complex, alive while g is built
#:     kappa = |phi|            x 8 B =   512 B/sample
#:     the Eq. (3) temporary          =   512 B/sample
#:     g                              =   512 B/sample
#:                                      ----------------
#:                                       3072 B/sample
#:
#: 200,000,000 / 3,072 = 65,104 -> 65,000 samples (18.06 h at 1 Hz), peaking at
#: 199.7 MB. `Working.execution.execute_recipe` checks this before calling
#: `run` and refuses the span with the reason, rather than allocating the
#: 1.33 GB `g_all` a whole 2,595,600-sample channel would ask for and then
#: handing all of it to `np.savez_compressed` through the step cache.
PEAK_BYTES_PER_SAMPLE = N_SCALES * (8 + 16 + 8 + 8 + 8)     # 3072
BLOCK_MEMORY_BUDGET_BYTES = 5000 * 5000 * 8                 # the gramian blocks' 200 MB
MAX_SPAN_SAMPLES = 65_000


def transform_span(x, fs, beta=BETA, gamma=GAMMA, eta=ETA, min_chunk_samples=2 * N_P,
                   slice_by_state=True):
    """g(τ, s) over the whole span, NaN where a chunk is shorter than
    `min_chunk_samples`. Returns `(g, chunks, skipped)`."""
    x = np.asarray(x, dtype=float).ravel()
    n = len(x)
    chunks = slice_signal(x) if slice_by_state else [(0, n - 1)]
    g_all = np.full((N_SCALES, n), np.nan, dtype=float)
    skipped = 0
    for c0, c1 in chunks:
        chunk = x[c0:c1 + 1]
        if len(chunk) < min_chunk_samples:
            skipped += 1
            continue
        phi, _scales = compute_morse_wavelet_transform(chunk, scales=None, beta=beta, gamma=gamma, fs=fs)
        g, _g_sum = normalise_wavelet_coefficients(phi, eta=eta)
        g_all[:, c0:c1 + 1] = g
    return g_all, chunks, skipped


def _run(x, t, fs, beta=BETA, gamma=GAMMA, eta=ETA, min_chunk_samples=2 * N_P, slice_by_state=True):
    g, chunks, skipped = transform_span(x, fs, beta=beta, gamma=gamma, eta=eta,
                                        min_chunk_samples=min_chunk_samples, slice_by_state=slice_by_state)
    return AdapterResult(
        output_kind="encoding",
        value=Encoding(values=g, kind="image"),
        meta={"n_chunks": len(chunks), "n_chunks_skipped": skipped, "n_scales": N_SCALES,
              "chunks": [[int(a), int(b)] for a, b in chunks]},
    )


def _estimate(x, t, fs, **params):
    return estimate_seconds(COST_MODEL, len(x))


register_cost_model(COST_MODEL, 1.1, lambda x, fs: transform_span(x, fs))


def _derive(x, t, fs, params):
    chunks = slice_signal(np.asarray(x, dtype=float).ravel())
    short = sum(1 for a, b in chunks if (b - a + 1) < params["min_chunk_samples"])
    return [
        ("Chunks (histogram state transitions)", str(len(chunks)), ""),
        ("Chunks below the floor (left NaN)", str(short), "warn" if short else ""),
        ("Scales", str(N_SCALES), ""),
    ]


SPEC = register(AdapterSpec(
    name="preprocessing.wavelet_transform",
    display_name="Morse wavelet transform (Dehshibi stage 1)",
    stage="preprocessing",
    category="encode",
    page_name="Wavelet transform",
    params=[
        ParamSpec("beta", float, BETA, "Morse wavelet β (paper: 20; P² = βγ = 60)", min=1.0),
        ParamSpec("gamma", float, GAMMA, "Morse wavelet γ (paper: 3)", min=1.0),
        ParamSpec("eta", float, ETA, "Eq. (3) scaling factor η (paper: 240)", min=1e-6),
        ParamSpec("min_chunk_samples", int, 2 * N_P,
                  "A chunk shorter than this is left NaN (the paper's 2·n_p = 120 samples at 1 Hz)", min=4),
        ParamSpec("slice_by_state", bool, True,
                  "Slice the span on histogram state transitions (Sect. 3.1) before transforming; off = one chunk"),
    ],
    run=_run,
    estimate=_estimate,
    derive=_derive,
    input_kind="signal",
    output_kind="encoding",
    max_span_samples=MAX_SPAN_SAMPLES,
    description=(
        "Sect. 3.1–3.2 of Dehshibi & Adamatzky 2021: histogram-sliced chunks, Morse "
        "continuous wavelet transform, per-scale normalisation. Emits g(τ, s) as a "
        f"scales × time image; feed it to Wavelet summation. Holds {N_SCALES} scales "
        f"in memory per sample, so it is capped at {MAX_SPAN_SAMPLES:,} samples "
        "(the same 200 MB budget the gramian blocks cap at)."
    ),
))
