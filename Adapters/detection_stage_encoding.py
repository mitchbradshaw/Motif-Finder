"""
detection_stage_encoding.py
=============================
Stage 2 of the canonical drop detector (`drop_detection_v1`, stage-3 D1):

    preprocessing.detrend (rolling_mean_nearest)   Signal   → Signal
    detection.stage_encoding                       Signal   → Encoding (symbolic, alphabet 5)
    detection.drop_detection                       Encoding → SpanSet

This block is `Working.Detection.drop_motifs.detect5.stage_letters` run on
the signal the chain carries (already detrended by the block before it —
`detrend_window_s=0` tells `stage_letters` to leave the signal alone): dSAX
at k = 3 under `same_fraction`, then the D and U bands split by the
slope-noise floor into the five stages d D S U u. The floor is the MAD of the
second difference (`slope_noise_sigma`); `slope_sigma` says how many of
those sigmas make a segment "fast". Spec §6.5's "noise floor" is this
block's `derive` readout — in the code the floor is a control inside the
encoder, exactly as the spec notes.

Output: an `Encoding` of kind `symbolic`, one integer per segment
(0 = d fast-down, 1 = D down, 2 = S same, 3 = U up, 4 = u fast-up). The
segment length in samples is `len(x) // n_symbols` (dSAX trims the span to
a whole number of segments), so the next block recovers it from the shapes
alone — no side channel.
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.Detection.drop_motifs.detect import (
    NOISE_ESTIMATORS, NOISE_SECOND_DIFFERENCE, THRESHOLD_MODE, TREND_ESTIMATOR, slope_noise_sigma,
)
from Working.Detection.drop_motifs.detect5 import STAGE_LETTERS, Detect5Params, stage_letters
from Working.types import Encoding

STAGE_INDEX = {letter: i for i, letter in enumerate(STAGE_LETTERS)}


def params_for(fs, segment_seconds, same_fraction, slope_sigma, noise_estimator, merge_gap_segments,
               threshold_mode, trend_estimator):
    """A `Detect5Params` with the detrend switched off (the chain did it)."""
    return Detect5Params(
        detrend_window_s=0.0, segment_seconds=float(segment_seconds), same_fraction=float(same_fraction),
        merge_gap_segments=int(merge_gap_segments), slope_sigma=float(slope_sigma),
        noise_estimator=str(noise_estimator), threshold_mode=str(threshold_mode),
        trend_estimator=str(trend_estimator),
    )


def _run(x, t, fs, segment_seconds=60.0, same_fraction=0.6, slope_sigma=8.0,
         noise_estimator=NOISE_SECOND_DIFFERENCE, merge_gap_segments=0,
         threshold_mode=THRESHOLD_MODE, trend_estimator=TREND_ESTIMATOR):
    p = params_for(fs, segment_seconds, same_fraction, slope_sigma, noise_estimator, merge_gap_segments,
                   threshold_mode, trend_estimator)
    letters, details = stage_letters(x, fs, p)
    symbols = np.array([STAGE_INDEX[c] for c in letters], dtype=np.int64)
    hist = {c: letters.count(c) for c in STAGE_LETTERS}
    return AdapterResult(
        output_kind="encoding",
        value=Encoding(values=symbols, kind="symbolic"),
        meta={
            "letters": letters, "alphabet": "".join(STAGE_LETTERS),
            "details": {
                "samples_per_symbol": int(details["samples_per_symbol"]),
                "alphabet_size": 5,
                "cutlines": [float(-details["fast_cut_raw"]), float(details["fast_cut_raw"])],
                "cutline_domain": "slope (raw units / s)",
            },
            "segment_slopes": np.asarray(details["segment_slopes"], dtype=float),
            "sigma_slope": float(details["sigma_slope"]),
            "fast_cut_raw": float(details["fast_cut_raw"]),
            "same_fraction_observed": float(details.get("same_fraction_observed", float("nan"))),
            "stage_histogram": hist, "n_segments": len(letters),
        },
    )


def _derive(x, t, fs, params):
    x = np.asarray(x, dtype=float).ravel()
    sigma = slope_noise_sigma(x, fs, params["noise_estimator"]) if x.size >= 3 else 0.0
    sps = max(1, int(round(params["segment_seconds"] * fs)))
    n_seg = max(1, len(x) // sps)
    cut = params["slope_sigma"] * sigma
    return [
        ("Slope-noise σ (MAD)", f"{sigma * 1000:.4f} mV/s", ""),
        ("Fast cut (±slope_sigma·σ)", f"{cut * 1000:.4f} mV/s", ""),
        ("Segments", f"{n_seg} × {sps} samples", "warn" if n_seg < 8 else ""),
    ]


SPEC = register(AdapterSpec(
    name="detection.stage_encoding",
    display_name="Five-stage encoding (drop detector stage 2)",
    stage="detection",
    category="encode",
    page_name="Symbolic encoding (five-stage)",
    params=[
        ParamSpec("segment_seconds", float, 60.0, "Seconds per symbol (segment length)", min=0.01),
        ParamSpec("same_fraction", float, 0.6, "Occupancy of the SAME band (dSAX quantile mode)", min=0.05, max=0.95),
        ParamSpec("slope_sigma", float, 8.0, "A segment steeper than this many noise σ is fast (d / u)", min=0.5),
        ParamSpec("noise_estimator", str, NOISE_SECOND_DIFFERENCE, "How the slope-noise floor is measured", choices=list(NOISE_ESTIMATORS)),
        ParamSpec("merge_gap_segments", int, 0, "Bridge an S gap of up to this many segments inside an up run", min=0),
        ParamSpec("threshold_mode", str, THRESHOLD_MODE, "dSAX cutline mode (quantile = by occupancy)", choices=["quantile", "learned"]),
        ParamSpec("trend_estimator", str, TREND_ESTIMATOR, "dSAX per-segment trend estimator", choices=["ols_slope", "endpoint"]),
    ],
    run=_run,
    derive=_derive,
    input_kind="signal",
    output_kind="encoding",
    description=(
        "dSAX trend letters (D S U, by occupancy) with the D and U bands split at the "
        "slope-noise floor into d D S U u. The letters the drop detector reads; the "
        "noise floor is this block's readout."
    ),
))
