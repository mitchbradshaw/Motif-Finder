"""
detection_cwt_ridges.py
=========================
`detection.cwt_ridges` — Signal -> SpanSet: spikes and troughs at every
duration at once, by continuous-wavelet-transform ridge lines (Du, Kibbe &
Lin 2006, *Bioinformatics* 22(17):2059-2065). The algorithm, and every way it
departs from the paper, is `Working/Detection/cwt_ridges.py`; this file maps
the chain onto it.

One span per accepted ridge maximum, centred on the event, `peak +/- duration_s`
wide, scored by its SNR, labelled `spike` / `drop`. The feature table carries
`peak_idx` (span-relative, like `starts`), `best_scale_s`, `duration_s`,
`ridge_scales`, `snr`, `peak_coef`, `noise`, `polarity` (+1 / -1, Event shape's
encoding), `edge_flag`, `step_pair` and `nan_in_support`. Event shape measures
a `polarity` and a `duration_s` of its own (onset to recovery) and replaces
its namesakes, so the two this block defines also ride as `ridge_polarity`
(in words) and `cwt_duration_s`, which survive the template's later blocks.
`meta` holds the counts (by polarity, flagged, rejected and why), the scales
used, the rules, the strongest events' ridges as `(time_s, scale_s)` points in
the recording's time, and a coarse scalogram (one float32 row of at most 4096
columns per scale — rows, not one array, because the bridge's JSON cleaner
omits any array over 4096 elements).

**One block, not two** (`docs/research/analysis-blocks-from-literature.md` §2):
an Encoding carries no axis and a block cannot read the previous block's
`meta`, so a separate ridge block could not know which width each row is.

Why not reuse: `preprocessing.wavelet_transform` (the Dehshibi image) is a
Morlet scalogram in rows of frequency with no ridge step; `detection.
wavelet_summation` / `summation_threshold` sum and cut it — none links maxima
across scales or reads a width off a scale. `scipy.signal.find_peaks_cwt` is
not the paper's algorithm (primary sources §7).

A span too short to hold three scales is refused with a ValueError, never an
empty result that would read as "no events".
"""

import numpy as np
import pandas as pd

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.block_cost import estimate_seconds, register_cost_model
from Working.Detection import cwt_ridges as CR
from Working.types import SpanSet

NAME = "detection.cwt_ridges"
FEATURES = ("peak_idx", "best_scale_s", "duration_s", "cwt_duration_s", "ridge_scales", "snr", "peak_coef", "noise",
            "polarity", "ridge_polarity", "edge_flag", "step_pair", "nan_in_support")


def _run(x, t, fs, min_scale_s=10.0, max_scale_s=7200.0, n_scales=40, polarity="both", min_snr=3.0,
         min_ridge_scales=6, max_gap_scales=3, noise_window_s=3600.0):
    xs = np.asarray(x, dtype=float).ravel()
    t = np.asarray(t, dtype=float).ravel()
    fs = float(fs)
    r = CR.detect(xs, fs, min_scale_s=min_scale_s, max_scale_s=max_scale_s, n_scales=n_scales, polarity=polarity,
                  min_snr=min_snr, min_ridge_scales=min_ridge_scales, max_gap_scales=max_gap_scales,
                  noise_window_s=noise_window_s)
    if len(r.scales_s) < 3:
        raise ValueError(
            f"{NAME}: the span ({len(xs)} samples at {fs:g} Hz) is too short for the scale range "
            f"{min_scale_s:g}-{max_scale_s:g} s: a scale's main lobe must fit in a quarter of the span and at "
            f"least 3 of the {n_scales} scales must; {len(r.scales_s)} do. Lengthen the span or lower min_scale_s.")
    ev = r.events
    features = pd.DataFrame([{k: e[k] for k in FEATURES} for e in ev], columns=list(FEATURES))
    if len(features):
        features = features.astype({"peak_idx": "int64", "ridge_scales": "int64", "polarity": "int64",
                                    "edge_flag": bool, "step_pair": bool, "nan_in_support": bool})
    spans = SpanSet(starts=tuple(e["start"] for e in ev), ends=tuple(e["end"] for e in ev),
                    labels=tuple(e["ridge_polarity"] for e in ev), scores=tuple(float(e["snr"]) for e in ev),
                    features=features)

    t0 = float(t[0]) if len(t) else 0.0
    ridges = [{"peak_s": t0 + rd["peak_idx"] / fs, "polarity": rd["polarity"],
               "points": [[t0 + c / fs, s] for c, s in zip(rd["cols"], rd["scales_s"])]}
              for rd in r.ridges]
    by_pol = {"spike": sum(e["ridge_polarity"] == "spike" for e in ev),
              "drop": sum(e["ridge_polarity"] == "drop" for e in ev)}
    meta = {
        "n_events": len(ev),
        "counts_by_polarity": by_pol,
        "n_edge_flagged": int(sum(e["edge_flag"] for e in ev)),
        "n_step_pair": int(sum(e["step_pair"] for e in ev)),
        "n_nan": int(r.n_nan),
        "n_chunks": int(r.n_chunks),
        "scales_s": [float(s) for s in r.scales_s],
        "scales_dropped": int(r.scales_dropped),
        "rejected": {k: int(v) for k, v in r.counts.items() if k != "ridges"},
        "n_ridges": int(r.counts.get("ridges", 0)),
        "rules": CR.rules(),
        "ridges": ridges,
        "ridges_note": (f"ridges of the {len(ridges)} strongest events (by SNR), capped at "
                        f"{CR.MAX_RIDGES_IN_META}; each point is (time_s in the recording's time, scale_s)"),
        "scalogram": {
            "rows": [row for row in r.scalogram["values"]],
            "scales_s": [float(s) for s in r.scales_s],
            "samples_per_column": int(r.scalogram["samples_per_column"]),
            "t0_s": t0, "dt_s": r.scalogram["samples_per_column"] / fs,
            "reduction": "signed value of the largest |coefficient| in each column's samples (never a stride); "
                         "coefficients after the per-scale baseline (rule: coefficient baseline)",
        },
    }
    if not ev:
        meta["absence"] = (f"No ridge passed: of {meta['n_ridges']} ridges, {meta['rejected']['ridges_too_short']} "
                           f"were shorter than {min_ridge_scales} scales, {meta['rejected']['below_snr']} maxima fell "
                           f"below SNR {min_snr:g}, {meta['rejected']['max_at_smallest_scale']} peaked at the smallest "
                           f"scale (noise) and {meta['rejected']['max_at_largest_scale']} at the largest "
                           f"(wider than {max_scale_s:g} s).")
    return AdapterResult(output_kind="spanset", value=spans, meta=meta)


def _time_once(x, fs):
    CR.detect(x, fs)


# Chunked, so linear in n at a fixed scale range (each chunk costs O(chunk log chunk x n_scales)).
register_cost_model(NAME, 1.0, _time_once)


def _estimate(x, t, fs, **params):
    """Seconds from the per-machine calibration (exponent 1: chunked), None until calibrated."""
    return estimate_seconds(NAME, len(x))


def _derive(x, t, fs, params, **_typed_inputs):
    n = len(x)
    scales = CR.scales_seconds(params["min_scale_s"], params["max_scale_s"], params["n_scales"])
    fit = scales * float(fs) <= n / 4.0
    rows = [("Scales", f"{int(fit.sum())} of {len(scales)} fit this span "
                       f"({scales[fit].min():.0f}-{scales[fit].max():.0f} s)" if fit.any() else "none fit this span",
             "" if fit.sum() >= 3 else "warn"),
            ("Durations it can report", f"about {CR.FWHM_PER_SCALE * params['min_scale_s']:.0f} s to "
                                        f"{CR.FWHM_PER_SCALE * (scales[fit].max() if fit.any() else 0):.0f} s", "")]
    return rows


SPEC = register(AdapterSpec(
    name=NAME,
    display_name="CWT ridges: spikes and troughs at every scale (Du, Kibbe & Lin 2006)",
    stage="detection",
    category="detect",
    page_name="CWT ridges",
    params=[
        ParamSpec("min_scale_s", float, 10.0,
                  "Smallest Mexican-hat scale, in seconds (an event's duration is about 1.67 x its scale)",
                  min=0.01, max=86400.0),
        ParamSpec("max_scale_s", float, 7200.0,
                  "Largest scale, in seconds. Keep it below the usual spacing of events: above it the hat spans "
                  "several events and can report their arrangement as one slow event",
                  min=0.02, max=864000.0),
        ParamSpec("n_scales", int, 40, "Number of scales, geometric between the two", min=3, max=200),
        ParamSpec("polarity", str, "both", "Report spikes, drops (troughs) or both — both are always traced, so "
                                           "one side's lobes never pass as the other's events",
                  choices=["both", "spike", "drop"]),
        ParamSpec("min_snr", float, 3.0,
                  "Tune this first. Keep an event whose ridge's largest coefficient is at least this many times "
                  "the local noise (95th percentile of the smallest scale's |coefficients| around it); about the "
                  "event's height over the noise's",
                  min=0.0, max=1000.0),
        ParamSpec("min_ridge_scales", int, 6, "A ridge must have a maximum on at least this many scales",
                  min=2, max=200),
        ParamSpec("max_gap_scales", int, 3, "A ridge may skip this many scales in a row before it ends",
                  min=0, max=20),
        ParamSpec("noise_window_s", float, 3600.0, "Width of the window the local noise is measured in, seconds",
                  min=1.0, max=864000.0),
    ],
    run=_run,
    estimate=_estimate,
    derive=_derive,
    input_kind="signal",
    output_kind="spanset",
    plot=None,
    description=(
        "Finds spikes and troughs of every duration in one pass, each with its own scale: a Mexican-hat template "
        "is slid along the trace at sizes from min_scale_s to max_scale_s, the bright points are joined across "
        "sizes into ridge lines, and a long, strong ridge is an event whose duration is read off the size at "
        "which it is brightest (Du, Kibbe & Lin 2006). A straight drift cancels without a detrend window. Tune "
        "min_snr first. A lopsided event (a sharkfin) is found with its scale but its centre sits toward the slow "
        "side: put Event shape after it for onset and recovery. Events at a span edge are flagged, not hidden."
    ),
))
