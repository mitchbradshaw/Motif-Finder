"""
detection_drop_detection.py
=============================
Stage 3 of the canonical drop detector (`drop_detection_v1`, stage-3 D1):
Encoding (five-stage letters) → SpanSet. The first Encoding → SpanSet
detector in the registry, so the B24 chain runs as drawn.

`Working.Detection.drop_motifs.detect5.detect_from_letters` does the work:
candidate onsets from the up runs (rise trigger) or the fast-fall runs
(fall trigger), the morphology decided once per span, the trough by the
knee rule, the onset walked back to the shoulder, Gates A (rise) and B
(dominance), the shallow and duplicate filters, and the window bracketed
on the neighbouring runs. Nothing is re-implemented here.

What this block recovers from what it is given, and how:
* the detrended signal — the chain's current `x` (the detrend block ran);
* the segment length — `len(x) // n_symbols` (dSAX trims to whole segments);
* the slope-noise floor — recomputed from `x` with `noise_estimator`, the
  same deterministic MAD the encoder used. `slope_sigma` therefore appears
  on both blocks and must agree; the derive readout on each shows the cut.

Output: one span per confirmed drop, `[window_start, window_end)`, label
`onset=<i>;trough=<j>;<morphology>`, score = drop depth (mV). The full
`Drop5Event` rows, the counts and the diagnostics ride in `meta`, which is
what the block page's event cards and "removed" breakdown draw.
"""

import dataclasses

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.Detection.drop_motifs.detect import NOISE_ESTIMATORS, NOISE_SECOND_DIFFERENCE, slope_noise_sigma
from Working.Detection.drop_motifs.detect5 import (
    MORPHOLOGIES, STAGE_LETTERS, Detect5Params, detect_from_letters, morphology_from_letters,
)
from Working.types import SpanSet


def letters_from_encoding(value):
    if value is None:
        raise ValueError("detection.drop_detection requires an Encoding input from a prior step (input_kind='encoding').")
    if getattr(value, "kind", None) != "symbolic":
        raise ValueError(f"detection.drop_detection reads five-stage letters (a symbolic Encoding); got kind {value.kind!r}.")
    syms = np.asarray(value.values).ravel()
    if syms.size and (syms.min() < 0 or syms.max() >= len(STAGE_LETTERS)):
        raise ValueError(
            f"detection.drop_detection expects symbols 0..{len(STAGE_LETTERS) - 1} (d D S U u); got "
            f"{int(syms.min())}..{int(syms.max())}. Put Five-stage encoding before it, not a plain SAX block.")
    return "".join(STAGE_LETTERS[int(s)] for s in syms)


def _run(x, t, fs, slope_sigma=8.0, noise_estimator=NOISE_SECOND_DIFFERENCE, min_rise_frac=0.5,
         min_fall_dominance=0.5, min_depth_frac=0.10, min_separation_s=0.0, lookahead_mult=3.0,
         trough_knee_frac=0.05, morphology="auto", tighten_windows=True, walk_onset_back=True,
         bracket_on_up_runs=True, bracket_on_fall_runs=True, window_cap_mult=6.0, window_pad_frac=0.25,
         bracket_rise_on_separation=False, value=None):
    letters = letters_from_encoding(value)
    x = np.asarray(x, dtype=float).ravel()
    n_symbols = len(letters)
    if n_symbols == 0:
        raise ValueError("detection.drop_detection: the encoding has no symbols.")
    sps = max(1, len(x) // n_symbols)
    sigma = slope_noise_sigma(x, fs, noise_estimator)
    params = Detect5Params(
        detrend_window_s=0.0, segment_seconds=sps / float(fs), same_fraction=float("nan"),
        slope_sigma=float(slope_sigma), noise_estimator=str(noise_estimator),
        lookahead_mult=float(lookahead_mult), trough_knee_frac=float(trough_knee_frac),
        min_depth_frac=float(min_depth_frac), min_separation_s=float(min_separation_s),
        bracket_on_up_runs=bool(bracket_on_up_runs), bracket_on_fall_runs=bool(bracket_on_fall_runs),
        window_cap_mult=float(window_cap_mult), window_pad_frac=float(window_pad_frac),
        bracket_rise_on_separation=bool(bracket_rise_on_separation),
        min_rise_frac=float(min_rise_frac), min_fall_dominance=float(min_fall_dominance),
        tighten_windows=bool(tighten_windows), morphology=str(morphology), walk_onset_back=bool(walk_onset_back),
    )
    morph = morphology_from_letters(letters, x, sps, params)
    result = detect_from_letters(x, fs, letters, sps, sigma, morph, params)
    events = result.events
    starts = tuple(int(e.window_start_idx) for e in events)
    ends = tuple(int(e.window_end_idx) for e in events)
    labels = tuple(f"onset={e.onset_idx};trough={e.trough_idx};{e.morphology}" for e in events)
    scores = tuple(float(e.drop_depth_mv) for e in events)
    rows = [dataclasses.asdict(e) for e in events]
    for r in rows:
        r["same_fraction"] = None       # provenance the block does not know; the encoder does
    return AdapterResult(
        output_kind="spanset",
        value=SpanSet(starts=starts, ends=ends, labels=labels, scores=scores),
        meta={"events": rows, "counts": dict(result.counts), "diagnostics": dict(result.diagnostics),
              "morphology": morph, "samples_per_symbol": sps, "sigma_slope": float(sigma),
              "slope_threshold": float(-slope_sigma * sigma), "n_events": len(events)},
    )


def _derive(x, t, fs, params, value=None):
    x = np.asarray(x, dtype=float).ravel()
    sigma = slope_noise_sigma(x, fs, params["noise_estimator"]) if x.size >= 3 else 0.0
    rows = [("Onset slope threshold", f"{-params['slope_sigma'] * sigma * 1000:.4f} mV/s", "")]
    if value is None:
        rows.append(("Letters", "run the five-stage encoding first", "warn"))
    else:
        try:
            letters = letters_from_encoding(value)
            rows.append(("Letters", f"{len(letters)} segments · {letters.count('d')} fast falls", ""))
        except ValueError as e:
            rows.append(("Letters", str(e), "error"))
    return rows


SPEC = register(AdapterSpec(
    name="detection.drop_detection",
    display_name="Drop detection (five-stage, detect5)",
    stage="detection",
    category="detect",
    page_name="Drop detection",
    params=[
        ParamSpec("slope_sigma", float, 8.0, "Onset = first sample steeper than this many noise σ (must match the encoder)", min=0.5),
        ParamSpec("noise_estimator", str, NOISE_SECOND_DIFFERENCE, "How the slope-noise floor is measured (must match the encoder)", choices=list(NOISE_ESTIMATORS)),
        ParamSpec("min_rise_frac", float, 0.5, "Gate A: a rise-triggered fall's rise must climb this fraction of its depth", min=0.0, max=1.0),
        ParamSpec("min_fall_dominance", float, 0.5, "Gate B: the fall's depth over its window's peak-to-peak", min=0.0, max=1.0),
        ParamSpec("min_depth_frac", float, 0.10, "Drop candidates shallower than this fraction of the deepest", min=0.0, max=1.0),
        ParamSpec("min_separation_s", float, 0.0, "Dedupe: two onsets closer than this keep the deeper (0 = off)", min=0.0),
        ParamSpec("lookahead_mult", float, 3.0, "How far past a rise to look for its fall, in rise lengths", min=0.1),
        ParamSpec("trough_knee_frac", float, 0.05, "Knee rule for the trough (fraction of the steepest slope)", min=0.0, max=1.0),
        ParamSpec("morphology", str, "auto", "sharkfin (rise → fall) or trough (fall → rise); auto decides per span", choices=["auto", *MORPHOLOGIES]),
        ParamSpec("tighten_windows", bool, True, "Shrink a window holding more than one fall"),
        ParamSpec("walk_onset_back", bool, True, "Move the onset back onto the shoulder the fall departs from"),
        ParamSpec("bracket_on_up_runs", bool, True, "Bound the window on the neighbouring up runs"),
        ParamSpec("bracket_on_fall_runs", bool, True, "Bound the window and trough search on the neighbouring fall"),
        ParamSpec("window_cap_mult", float, 6.0, "Cap per side in fall durations when no run bounds it", min=0.5),
        ParamSpec("window_pad_frac", float, 0.25, "Air either side of the bracket, in fall durations", min=0.0),
        ParamSpec("bracket_rise_on_separation", bool, False, "Apply min_separation_s to the trough-search bound"),
    ],
    run=_run,
    derive=_derive,
    input_kind="encoding",
    output_kind="spanset",
    description=(
        "Candidate onsets from the letters, trough by the knee rule, Gates A and B, "
        "window bracketed on the neighbouring runs — detect5, block by block. One span "
        "per confirmed drop; the event anatomy rides in meta."
    ),
))
