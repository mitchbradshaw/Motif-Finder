"""
detection_summation_threshold.py
==================================
Stage 3 of the Dehshibi & Adamatzky (2021) template: everything after Ω(τ).

Scores → SpanSet, window by window, as the AUTHORS' code does it (Zenodo
10.5281/zenodo.3997031; fixup-J, QUESTIONS.md Q33):

    B   candidate regions between consecutive prominent extrema of the score   iApplyWavelet.m
    C   those where the signal leaves the range of its own two ends            iClusterWaveletROI.m
    D   the rest, set aside as pseudo-spikes (the authors never use them)
    R   envelope regions of the signal's curvature                             iApplyEnvelope.m
    S   each C widened to the envelope regions it meets, overlaps merged       iLocateSpike.m

The confirmed spikes are the SpanSet (label `spike`, score = the signal's
range inside the span). **The whole funnel rides in `meta["funnel"]`** —
every stage's regions and counts — because the question the page has to
answer is what the block decided and why.

**What it needs from the block before it**: a `Scores` with one value per
sample of the span, and nothing else. The signal arrives as `x`, which every
block receives, and the envelope branch never looks at the score. So ANY
block that emits a per-sample score can stand in for the wavelet summation;
this block windows the score itself (`window_s`) and does not ask how it was
made. A window whose score is not finite throughout is skipped and counted.

Index convention: the core speaks MATLAB's INCLUSIVE `(start, end)` pairs and
`SpanSet` documents half-open `[start, end)`. `_run` converts at the seam,
for the spans and for every region in `meta`.

Lengths are in seconds (Q32). `n_p`, `min_spike_duration` and
`min_roi_wavelet` were sample counts before fixup-J; they are still accepted
so an old recipe runs: a non-zero `n_p` is the separation in samples, the
other two belonged to the printed Algorithm 4 and have no counterpart in the
authors' code.

Why not `detection.threshold`: that block cuts a Scores at an absolute
value. This one needs extrema PAIRS at a prominence relative to the window's
own range, and then the raw signal — the semantics do not match, so the
standard says: a new block.
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.Detection.analysis.dehshibi_authors import PEAK_WIDTH_S, THR, WINDOW_S, detect_from_omega
from Working.types import SpanSet

#: the funnel, in the order the page draws it: (info key, label)
STAGES = (
    ("B", "candidate regions — between extrema of the score"),
    ("C", "spike candidates — the signal leaves the range of its ends"),
    ("D", "pseudo-spikes — it does not; set aside"),
    ("R", "envelope regions — of the signal's curvature"),
    ("R_kept", "envelope regions kept — the weak ones dropped"),
    ("S", "spikes — candidates widened to the envelope regions they meet"),
)


def _half_open(regions):
    return [[int(a), int(b) + 1] for a, b in regions]


def _run(x, t, fs, epsilon_factor=THR, min_separation_s=PEAK_WIDTH_S, window_s=WINDOW_S, slice_by_state=False,
         n_p=0, min_spike_duration=0, min_roi_wavelet=0, value=None):
    if value is None:
        raise ValueError("detection.summation_threshold requires a Scores input from a prior step (input_kind='scores').")
    omega = np.asarray(value.values, dtype=float).ravel()
    if len(omega) != len(x):
        raise ValueError(f"Scores has {len(omega)} values for a {len(x)}-sample span; they must align.")
    separation_s = (n_p / float(fs)) if n_p else min_separation_s
    spikes, info = detect_from_omega(x, omega, fs=fs, thr=epsilon_factor, peak_width_s=separation_s,
                                     window_s=window_s, slice_by_state=slice_by_state)
    info["S"] = spikes
    xs = np.asarray(x, dtype=float)
    funnel = {
        "stages": [{"key": k, "label": label, "n": len(info[k]), "regions": _half_open(info[k])} for k, label in STAGES],
        "chunks": _half_open(info["chunks"]),
        "omega_peaks": [int(p) for p in info["peaks"]],
        "omega_valleys": [int(v) for v in info["valleys"]],
    }
    return AdapterResult(
        output_kind="spanset",
        value=SpanSet(
            starts=tuple(int(s) for s, _ in spikes),
            ends=tuple(int(e) + 1 for _, e in spikes),
            labels=tuple("spike" for _ in spikes),
            scores=tuple(float(np.ptp(xs[s:e + 1])) if e >= s else 0.0 for s, e in spikes),
        ),
        meta={"pseudo_spikes": _half_open(info["D"]),
              "n_spikes": len(spikes), "n_pseudo_spikes": len(info["D"]),
              "n_chunks": len(info["chunks"]), "n_chunks_skipped": info["chunks_skipped"],
              "n_candidates_B": len(info["B"]), "n_wavelet_C": len(info["C"]),
              "n_envelope_R": len(info["R"]),
              "funnel": funnel},
    )


SPEC = register(AdapterSpec(
    name="detection.summation_threshold",
    display_name="Summation threshold: regions, envelope, merge (Dehshibi stage 3)",
    stage="detection",
    category="detect",
    page_name="Summation threshold",
    params=[
        ParamSpec("epsilon_factor", float, THR, "Extremum prominence as a fraction of the score's range in the window (authors: 0.05)", min=0.0, max=1.0),
        ParamSpec("min_separation_s", float, PEAK_WIDTH_S, "Minimum distance between extrema, and the shortest region kept, in seconds (authors: 60)", min=0.1),
        ParamSpec("window_s", float, WINDOW_S, "Window length in seconds; prominence is relative to each window (paper: 3000 s pieces)", min=10.0),
        ParamSpec("slice_by_state", bool, False, "Cut at the recording's state transitions (the authors' iSplitSignal) instead of fixed windows"),
        ParamSpec("n_p", int, 0, "Old recipes only: the separation as a sample count; 0 = use min_separation_s", min=0),
        ParamSpec("min_spike_duration", int, 0, "Old recipes only: not used since fixup-J", min=0),
        ParamSpec("min_roi_wavelet", int, 0, "Old recipes only: not used since fixup-J", min=0),
    ],
    run=_run,
    input_kind="scores",
    output_kind="spanset",
    description=(
        "Everything in Dehshibi & Adamatzky 2021 after Ω(τ), as the authors' code does it: "
        "candidate regions from the score's extrema, the spike / pseudo-spike split on the "
        "signal, envelope regions, merge. Takes any per-sample score. Emits one span per "
        "spike, and every stage of the funnel in its payload."
    ),
))
