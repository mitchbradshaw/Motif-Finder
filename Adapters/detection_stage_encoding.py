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

Missing samples (NaN, inf; 2026-10-14): a segment that touches one has no
stage — symbol -1, letter '-' (`dsax.MISSING_SYMBOL` / `MISSING_LETTER`) —
and the cutlines and the noise floor are the recorded part's. Before, one
NaN made every segment 'U' and the floor NaN. The block page says how much
is missing before a run.

Units (2026-10-15): the readout prints σ and the cut in mV/s by the unit the
recording declares — a run hands `derive` the recording's ``units`` and it
converts by `Working.units.read_as_mv` (V ×1000, mV ×1). Before, it
multiplied by 1000 whatever the file held: on L_LM σ read 605.6 "mV/s" for
0.6056. An undeclared unit is read as volts and every mV row says so; naming
no unit at all (a script, a test) is volts, as it always was. The letters
themselves are unit-free.
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.detection_threshold import spans_from_mask
from Adapters.registry import register
from Working.Detection.drop_motifs.detect import (
    NOISE_ESTIMATORS, NOISE_SECOND_DIFFERENCE, THRESHOLD_MODE, TREND_ESTIMATOR, slope_noise_sigma,
)
from Working.Detection.drop_motifs.detect5 import STAGE_LETTERS, Detect5Params, stage_letters
from Working.Detection.sax.dsax_python.dsax import MISSING_LETTER, MISSING_SYMBOL
from Working.types import Encoding
from Working.units import VOLTS, read_as_mv

STAGE_INDEX = {letter: i for i, letter in enumerate(STAGE_LETTERS)}
STAGE_INDEX[MISSING_LETTER] = MISSING_SYMBOL          # a segment a gap touches: no stage


def missing_samples_row(x, t, fs, consequence):
    """The block page's readout of a span's gaps, or None when nothing is
    missing: `("Missing samples", "<n> in <k> gaps · first at h:mm:ss · <consequence>", "warn")`.
    Shared with `detection.drop_detection`."""
    gone = ~np.isfinite(np.asarray(x, dtype=float).ravel())
    if not gone.any():
        return None
    starts, _ = spans_from_mask(gone)
    first = float(t[int(starts[0])]) if t is not None and len(t) > int(starts[0]) else int(starts[0]) / float(fs)
    clock = f"{int(first // 3600)}:{int(first % 3600 // 60):02d}:{int(first % 60):02d}"
    k = len(starts)
    return ("Missing samples", f"{int(gone.sum()):,} in {k} gap{'s' if k != 1 else ''} · first at {clock} · "
            f"{consequence}", "warn")


def units_row(units):
    """The block page's readout of the unit its millivolts are read from: ``("Unit", "mV · ×1 to mV", "")``,
    or the `read_as_mv` note, flagged, for an undeclared unit. Shared with `detection.drop_detection` and
    `interrogation.event_shape`."""
    factor, note = read_as_mv(units)
    return ("Unit", note, "warn") if note else ("Unit", f"{units} · ×{factor:g} to mV", "")


def mv_per_s_row(label, value, units):
    """A slope readout row: `value` (stored unit per second) in mV/s by the recording's unit; read as volts and
    flagged where the unit is undeclared."""
    factor, note = read_as_mv(units)
    return (label, f"{value * factor:.4f} mV/s" + (" · read as volts" if note else ""), "warn" if note else "")


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
            "missing_segments": letters.count(MISSING_LETTER),
        },
    )


def _derive(x, t, fs, params, units=VOLTS):
    x = np.asarray(x, dtype=float).ravel()
    sigma = slope_noise_sigma(x, fs, params["noise_estimator"]) if x.size >= 3 else 0.0
    sps = max(1, int(round(params["segment_seconds"] * fs)))
    n_seg = max(1, len(x) // sps)
    cut = params["slope_sigma"] * sigma
    rows = [
        units_row(units),
        mv_per_s_row("Slope-noise σ (MAD)", sigma, units),
        mv_per_s_row("Fast cut (±slope_sigma·σ)", cut, units),
        ("Segments", f"{n_seg} × {sps} samples", "warn" if n_seg < 8 else ""),
    ]
    gap = missing_samples_row(x, t, fs, "a segment that touches a gap gets no letter (-); σ and the cutlines "
                                        "are the recorded part's")
    return rows + [gap] if gap else rows


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
