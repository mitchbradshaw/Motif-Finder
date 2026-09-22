"""
detection_summation_threshold.py
==================================
Stage 3 of the Dehshibi & Adamatzky (2021) template: Algorithms 1–4 over
Ω(τ) and the signal.

Scores → SpanSet. Per histogram chunk (the same `slice_signal` rule the
transform used): Algorithm 1 pairs prominence-gated extrema of Ω into
candidate regions B; Algorithm 2 keeps the regions whose signal excursion
crosses its own endpoints (C) and sets the rest aside as pseudo-spikes (D);
Sect. 3.3 builds the analytic-signal envelope of the chunk and Algorithm 3
turns it into regions R; Algorithm 4 confirms a spike where C and R agree
and it is long enough. The confirmed spikes are the SpanSet (label `spike`,
score = signal depth in the span); the pseudo-spikes ride in `meta`.

Index convention: the paper's algorithms return INCLUSIVE `(start, end)`
pairs and `SpanSet` documents half-open `[start, end)`. `_run` converts at
the seam, for both the spans and `meta["pseudo_spikes"]`, so this block and
`detection.threshold` report the same two numbers for the same event.

Why not `detection.threshold`: that block cuts a Scores at an absolute
value. This one needs extrema PAIRS at a prominence relative to the chunk's
own range, and then the raw signal (Algorithm 2's excursion test and the
envelope) — the semantics do not match, so the standard says: a new block.
Every block receives `x`, the chain's current signal, so no side input is
needed for that.
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.Detection.analysis.dehshibi_detection_analysis import (
    MIN_ROI_WAVELET, MIN_SPIKE_DURATION, N_P,
    algorithm1_detect_candidate_regions, algorithm2_exclude_pseudospike_regions,
    algorithm3_detect_envelope_regions, algorithm4_extract_spike_events,
    compute_signal_envelope, slice_signal,
)
from Working.types import SpanSet


def spans_from_omega(x, omega, n_p=N_P, min_spike_duration=MIN_SPIKE_DURATION,
                     min_roi_wavelet=MIN_ROI_WAVELET, epsilon_factor=0.05, slice_by_state=True):
    """Algorithms 1–4 per chunk. Returns `(spikes, pseudo, info)` with the
    same shapes `detect_spikes` returns."""
    x = np.asarray(x, dtype=float).ravel()
    omega = np.asarray(omega, dtype=float).ravel()
    n = len(x)
    chunks = slice_signal(x) if slice_by_state else [(0, n - 1)]
    info = {"chunks": chunks, "B": [], "C": [], "D": [], "R": [], "chunks_skipped": 0}
    spikes, pseudo = [], []
    for c0, c1 in chunks:
        chunk = x[c0:c1 + 1]
        w = omega[c0:c1 + 1]
        if len(chunk) < 2 * n_p or not np.isfinite(w).all():
            info["chunks_skipped"] += 1
            continue
        B_local = algorithm1_detect_candidate_regions(w, epsilon_factor=epsilon_factor)
        B = [(c0 + s, c0 + e) for s, e in B_local]
        info["B"].extend(B)
        C, D = algorithm2_exclude_pseudospike_regions(B, x, min_duration=min_roi_wavelet)
        info["C"].extend(C); info["D"].extend(D)
        xi_mean, xi_upper, xi_lower = compute_signal_envelope(chunk, n_p=n_p)
        R = algorithm3_detect_envelope_regions(xi_mean, xi_upper, xi_lower, n_p=n_p)
        if R.shape[0] > 0:
            R = R.copy(); R[:, 0] += c0; R[:, 1] += c0
        info["R"].append(R)
        s, p = algorithm4_extract_spike_events(C, D, R, min_duration=min_spike_duration)
        spikes.extend(s); pseudo.extend(p)
    return spikes, pseudo, info


def _run(x, t, fs, n_p=N_P, min_spike_duration=MIN_SPIKE_DURATION, min_roi_wavelet=MIN_ROI_WAVELET,
         epsilon_factor=0.05, slice_by_state=True, value=None):
    if value is None:
        raise ValueError("detection.summation_threshold requires a Scores input from a prior step (input_kind='scores').")
    omega = np.asarray(value.values, dtype=float).ravel()
    if len(omega) != len(x):
        raise ValueError(f"Scores has {len(omega)} values for a {len(x)}-sample span; they must align.")
    spikes, pseudo, info = spans_from_omega(
        x, omega, n_p=n_p, min_spike_duration=min_spike_duration,
        min_roi_wavelet=min_roi_wavelet, epsilon_factor=epsilon_factor, slice_by_state=slice_by_state)
    xs = np.asarray(x, dtype=float)
    scores = tuple(float(np.ptp(xs[s:e + 1])) if e >= s else 0.0 for s, e in spikes)
    # Algorithms 1-4 speak inclusive (start, end) pairs; SpanSet documents
    # `[start, end)` and `detection.threshold` emits that, so the conversion
    # happens here, once, at the seam (fixup-a item 3 - before this the same
    # event's duration differed by one sample depending on which block found it).
    return AdapterResult(
        output_kind="spanset",
        value=SpanSet(
            starts=tuple(int(s) for s, _ in spikes),
            ends=tuple(int(e) + 1 for _, e in spikes),
            labels=tuple("spike" for _ in spikes),
            scores=scores,
        ),
        meta={"pseudo_spikes": [[int(s), int(e) + 1] for s, e in pseudo],
              "n_spikes": len(spikes), "n_pseudo_spikes": len(pseudo),
              "n_chunks": len(info["chunks"]), "n_chunks_skipped": info["chunks_skipped"],
              "n_candidates_B": len(info["B"]), "n_wavelet_C": len(info["C"]),
              "n_envelope_R": int(sum(r.shape[0] for r in info["R"]))},
    )


SPEC = register(AdapterSpec(
    name="detection.summation_threshold",
    display_name="Summation threshold: Algorithms 1–4 (Dehshibi stage 3)",
    stage="detection",
    category="detect",
    page_name="Summation threshold",
    params=[
        ParamSpec("epsilon_factor", float, 0.05, "Extremum prominence as a fraction of Ω's range in the chunk (paper: 0.05)", min=0.0, max=1.0),
        ParamSpec("n_p", int, N_P, "Minimum extrema separation for the envelope (samples; paper: 60 at 1 Hz)", min=1),
        ParamSpec("min_spike_duration", int, MIN_SPIKE_DURATION, "Shortest confirmed spike (samples; paper: 60)", min=1),
        ParamSpec("min_roi_wavelet", int, MIN_ROI_WAVELET, "Shortest wavelet region kept by Algorithm 2 (samples; paper: 30)", min=1),
        ParamSpec("slice_by_state", bool, True, "Apply the algorithms per histogram chunk (must match the transform block)"),
    ],
    run=_run,
    input_kind="scores",
    output_kind="spanset",
    description=(
        "Algorithms 1–4 of Dehshibi & Adamatzky 2021 over Ω(τ) and the signal: "
        "candidate regions from Ω's extrema, pseudo-spike exclusion, envelope "
        "confirmation. Emits the confirmed spikes as spans labelled 'spike'."
    ),
))
