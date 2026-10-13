"""
preprocessing_beads.py
========================
`preprocessing.beads` — Signal -> Signal: the trace with its baseline removed
by BEADS (Ning, Selesnick & Duval 2014), a thin wrapper over
`Working.Preprocessing.beads.remove_baseline`, where the algorithm, its BSD-3
provenance (Laurent Duval's `beads.m`) and every adaptation to our recordings
are documented.

BEADS splits the trace into three layers at once — a slow baseline, a sparse
layer of events (mostly zero, with mostly-zero slopes) and noise — and lets
each explain only what it is good at. The block passes on `y − baseline`.

Why not reuse: `preprocessing.detrend` subtracts a rolling mean, which is
dragged down by every big drop and leaves a fake overshoot beside it, and
whose window has repeatedly been the wrong length; BEADS has no window to
guess, only the period below which a change counts as drift.
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.block_cost import estimate_seconds, register_cost_model
from Working.Preprocessing.beads import (FC_GRID, LAMBDA_RATIOS, MIN_SAMPLES, POLARITIES, beads,
                                         grid_factor, remove_baseline)
from Working.types import Signal

NAME = "preprocessing.beads"


def _time_once(x, fs):
    """Cost is the MM solve on the grid: time it on `x` taken as grid points."""
    z = np.asarray(x, dtype=float)
    z = (z - np.linspace(z[0], z[-1], len(z))) / (np.std(np.diff(z)) or 1.0)
    lam0, lam1, lam2 = LAMBDA_RATIOS
    beads(z, fc=FC_GRID, d=2, lam0=lam0, lam1=lam1, lam2=lam2, max_iter=30)


# Seconds ~ grid points × iterations; the grid is the span over `grid_factor`
# plus one baseline period of padding at each end.
register_cost_model(NAME, 1.0, _time_once)


def _estimate(x, t, fs, baseline_period_s=7200.0, **params):
    n = len(x)
    period = float(baseline_period_s) * float(fs)
    if period <= 2.0 or n < MIN_SAMPLES:
        return None
    q = grid_factor(n, 1.0 / period)
    ng = -(-n // q)
    return estimate_seconds(NAME, ng + 2 * min(ng - 1, int(round(period / q))))


def _rules(meta):
    rules = [{"name": "warnings", "rule": " ".join(meta["warnings"])}] if meta["warnings"] else []
    return rules + [
        {"name": "sigma",
         "rule": "Scale: the robust level (median absolute deviation ÷ 0.6745) of the high-passed grid — "
                 "the noise as it averages onto the grid plus whatever slow drift the filter lets through — "
                 "never below the white-noise level σ/√samples-per-point (σ: MAD of the first difference "
                 "÷ (0.6745·√2)). The grid is divided by it before solving, so `sparsity` means the same in "
                 "volts and millivolts, and drift far larger than the noise is not mistaken for events."},
        {"name": "grid",
         "rule": f"BEADS is solved on means of {meta['grid_factor']} samples "
                 f"({meta['grid_step_s']:g} s), so the cut-off sits at {meta['fc_grid_cycles_per_sample']:.3g} "
                 "cycles per grid point where the solve is well conditioned; the baseline is interpolated "
                 "back to every sample. The corrected signal keeps every sample's own detail."},
        {"name": "baseline",
         "rule": f"Baseline: everything slower than {meta['baseline_period_s']:g} s (fc = 1 / period) that the "
                 "sparse event layer does not explain. An event as slow as that period is baseline — raise "
                 "`baseline_period_s` above the slowest event you care about."},
        {"name": "event_fraction_3sigma",
         "rule": "Fraction of grid points where the sparse event layer x exceeds 3 × the scale: how much of "
                 "the span BEADS treated as events. Above 0.8 on a drop or spike run it is drift, not "
                 "events, and a warning says so."},
        {"name": "converged",
         "rule": f"Converged: the cost changed by less than 0.1 % between iterations before the cap of "
                 f"{meta['max_iter']}. If false, the baseline is the last iterate."},
    ]


def _run(x, t, fs, baseline_period_s=7200.0, polarity="drop", sparsity=1.0, filter_order=2):
    out = remove_baseline(x, fs, baseline_period_s=baseline_period_s, polarity=polarity,
                          sparsity=sparsity, filter_order=int(filter_order))
    meta = dict(out["meta"])
    meta["rules"] = _rules(meta)
    return AdapterResult(output_kind="signal", value=Signal(x=out["corrected"], fs=float(fs)), meta=meta)


SPEC = register(AdapterSpec(
    name=NAME,
    display_name="BEADS baseline removal (Ning, Selesnick & Duval 2014)",
    stage="preprocessing",
    category="preprocess",
    page_name="BEADS baseline",
    params=[
        ParamSpec("baseline_period_s", float, 7200.0,
                  "Anything slower than this period (seconds) is baseline drift and is removed. Set it above "
                  "the slowest event you want to keep — an event as slow as the period is removed with the drift.",
                  min=60.0, max=30 * 86400.0),
        ParamSpec("polarity", str, "drop",
                  "Which way the events point: drop (troughs), spike (peaks), or both (no preference).",
                  choices=list(POLARITIES)),
        ParamSpec("sparsity", float, 1.0,
                  "How rare events must be (unit-free). Higher: fewer, larger events, more left to the baseline "
                  "and the noise; lower: more of the trace counted as events.",
                  min=0.05, max=50.0),
        ParamSpec("filter_order", int, 2,
                  "Sharpness of the drift / event split. Only 2 is offered: order 1 let 7 % of a drift three "
                  "times slower than the period through as signal, and 15 % of one twice as slow.",
                  choices=[2]),
    ],
    run=_run,
    estimate=_estimate,
    input_kind="signal",
    output_kind="signal",
    description=(
        "Removes slow baseline drift without a rolling window: BEADS splits the trace into a smooth baseline, "
        "a sparse layer of events and noise, and passes on the trace minus the baseline — so big drops are "
        "not dragged into the baseline and leave no overshoot beside them. Tune `baseline_period_s` first: "
        "drift slower than it is removed, events faster than it are kept. Set `polarity` to the way your "
        "events point. On a span made mostly of events the baseline settles partway into them: event shapes "
        "and depths are kept, absolute levels are not reliable there."
    ),
))
