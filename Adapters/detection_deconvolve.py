"""
detection_deconvolve.py
========================
`detection.deconvolve` — Signal -> Scores: OASIS deconvolution (Friedrich, Zhou
& Paninski 2017, PLoS Comput Biol 13(3):e1005423), written from the paper; the
work is `Working.Detection.deconvolution.oasis`, whose docstring names every
adaptation our recordings force (polarity, time constants in seconds, a unit-free
score, the robust noise level, the two-step recovery estimate, one baseline per
span, a fixed minimum jump, the initial level, NaN).

The score is the size of the sudden jump at every sample, in NOISE SDs — almost
all zero. Drawn by the standard (`signal->scores`): the curve under the trace on
the same x; `detection.impulse_events` cuts it, its `threshold` draggable on this
curve.

Why not reuse: no block in the registry fits a fade to the trace. The drop
detector (`detection.drop_detection`) and `detection.signal_threshold` find a
drop by its depth and so merge a second drop that starts before the first has
recovered; `detection.matrix_profile`'s Scores is a distance, not a jump size.
The noise level is not `drop_motifs.detect.robust_sigma` applied to x (that is
the MAD of the samples, which a trough train inflates); it is the MAD of the
first differences, defined in the core.
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.block_cost import estimate_seconds, register_cost_model
from Working.Detection.deconvolution import oasis as O
from Working.types import Scores

NAME = "detection.deconvolve"

RULES = [
    {"name": "jump (score)",
     "rule": "s_t / sigma: the size of the sudden jump at sample t in noise SDs, from the thresholded OASIS fit "
             "y = b + c + noise, c_t = g c_{t-1} [+ g2 c_{t-2}] + s_t, every non-zero s_t >= min_jump_sigma * sigma. "
             "For polarity=drop the signal is negated, so a drop is a positive jump. The first sample of the span "
             "(and of each run between NaN gaps) is the level carried in from before the span and scores 0."},
    {"name": "sigma",
     "rule": "the noise SD in the signal's stored units: 1.4826 x MAD of the first differences / sqrt(2) "
             "(the SD of the differences / sqrt 2 when most differences are zero). It sees fast noise only: "
             "slow, coloured noise (each sample close to the last) is underestimated -- for AR(1) noise with "
             "phi = 0.95 it reads about a fifth of the true SD -- so slow wander passes as jumps. sigma_level, "
             "the robust SD (1.4826 MAD) of y about its baseline, rides beside it: far above sigma on a "
             "quiet stretch means coloured noise."},
    {"name": "recovery half-time",
     "rule": "given (recovery_half_s > 0: g = 2^(-1/(half x fs))), or estimated: a first guess from the decay of "
             "the autocovariance over lags 1..2x its half-point, refined to the half-time that minimises "
             "RSS/sigma^2 + 2 ln(T) x (number of jumps) -- each jump pays a BIC price, so a short fade cannot win "
             "by explaining every wiggle as a jump -- searched from a third to three times the guess, recentred "
             "up to 3 times when the best lies on an edge (a warning if it still does; at most 400 000 samples). "
             "When no recovery can be estimated (white noise, a ramp) and a fit at 120 s finds no jump, the "
             "channel is quiet: all-zero scores, recovery_estimated false, and the summary says why."},
    {"name": "baseline",
     "rule": "baseline_window_s = 0 (the paper): one constant per span, the 15th percentile, then mean(y - c) "
             "until it moves < 0.001 sigma (at most 10 passes). baseline_window_s > 0: a slowly varying curve, "
             "started at a running 15th percentile over that window (two passes, cancelling a slope's bias) and "
             "refined as the running mean of y - c over the same window until its mean per-sample step is "
             "< 0.05 sigma (at most 10 passes; 'baseline not converged' in the summary otherwise -- usually a "
             "window shorter than ~15 recovery half-times)."},
    {"name": "residual SD",
     "rule": "the RMS of y - b - c in noise SDs: about 1 when every event is a jump followed by this fade; "
             "larger when the shape is not (a sharkfin's plateau, a slow fall). Above 1.5 the summary says the "
             "event count is not a trough count."},
    {"name": "warnings",
     "rule": "in meta and the summary: jumps faster than they recover (more than 30 per hour, or jumps x "
             "half-time > half the span: fragmentation, usually a wrong recovery half-time); an estimate still on "
             "the search's edge; residual SD > 1.5; a running baseline not converged; runs that start after a NaN "
             "gap at a level above min_jump_sigma (a drop absorbed into the run's initial level)."},
]


def _run(x, t, fs, polarity="drop", recovery_half_s=0.0, rise_s=0.0, min_jump_sigma=3.0, baseline_window_s=0.0):
    out = O.deconvolve(x, fs, polarity=polarity, recovery_half_s=recovery_half_s,
                       rise_s=rise_s, min_jump_sigma=min_jump_sigma, baseline_window_s=baseline_window_s)
    g1, g2 = out.ar_coefficients
    ar2 = out.rise > 0
    n_jumps = int(out.n_jumps)
    if out.estimate_note:
        how = "could not be estimated"
    else:
        how = "estimated" if out.estimated else "given"
    summary = (f"{n_jumps:,} jumps of at least {min_jump_sigma:g} noise SDs · recovery half-time "
               f"{out.half_s:.1f} s ({how}) · residual {out.residual_sd_sigma:.2f} SD")
    if out.estimate_note:
        summary += (f" · the recovery could not be estimated ({out.estimate_note}) and a fit at "
                    f"{O.FALLBACK_HALF_S:g} s finds no jump: a quiet channel")
    if out.n_nan:
        summary += f" · {out.n_nan:,} NaN samples in {out.n_segments} runs"
    for w in out.warnings:
        summary += f" · WARNING: {w}"
    return AdapterResult(
        output_kind="scores",
        value=Scores(values=out.scores, fs=float(fs)),
        meta={
            "summary": summary,
            "model": "AR(2)" if ar2 else "AR(1)",
            "polarity": polarity,
            "sigma": float(out.sigma),
            "sigma_level": float(out.sigma_level),
            "s_min": float(out.s_min),
            "min_jump_sigma": float(min_jump_sigma),
            "gamma": float(out.decay),
            "ar_coefficients": [g1, g2] if ar2 else [g1],
            "recovery_half_s_used": float(out.half_s),
            "recovery_estimated": bool(out.estimated),
            "recovery_estimate_note": out.estimate_note,
            "recovery_estimate_on_edge": bool(out.estimate_on_edge),
            "recovery_half_s_autocov": None if out.half_s_autocov is None else float(out.half_s_autocov),
            "rise_s": float(rise_s) if ar2 else 0.0,
            "baseline": float(out.sign * out.baseline),          # in the signal's own orientation and units
            "baseline_mode": "running" if out.floor is not None else "constant",
            "baseline_window_s": float(out.baseline_window_s),
            "baseline_range": (None if out.floor is None else
                               [float(np.nanmin(out.sign * out.floor)), float(np.nanmax(out.sign * out.floor))]),
            "baseline_converged": bool(out.baseline_converged),
            "n_baseline_iter": int(out.n_baseline_iter),
            "n_jumps": n_jumps,
            "n_nan": int(out.n_nan),
            "n_segments": int(out.n_segments),
            "initial_levels_sigma": [float(v) for v in out.initial_levels],
            "n_runs_starting_above_min_jump": int(out.n_runs_starting_above_min_jump),
            "warnings": list(out.warnings),
            "residual_sd_sigma": float(out.residual_sd_sigma),
            "rules": RULES,
        },
    )


def _time_once(x, fs):
    """A trough train the length of the calibration signal (its random walk is drift, which the
    estimate refuses), with the recovery estimated: the block's slowest ordinary path."""
    n = len(x)
    rng = np.random.default_rng(0)
    d = O.decay_from_half_time(120.0, fs)
    s = np.zeros(n)
    s[300::1500] = rng.uniform(20.0, 60.0, s[300::1500].size)
    from scipy.signal import lfilter
    y = 0.01 - 1e-4 * lfilter([1.0], [1.0, -d], s) + 1e-4 * rng.standard_normal(n)
    O.deconvolve(y, fs, recovery_half_s=0.0)


# O(n): the solver is linear; the recovery estimate runs on at most 400 000 samples
register_cost_model(NAME, 1.0, _time_once)


def _estimate(x, t, fs, **params):
    return estimate_seconds(NAME, len(x))


SPEC = register(AdapterSpec(
    name=NAME,
    display_name="Deconvolve: sudden jumps, each followed by the same fade (OASIS)",
    stage="detection",
    category="detect",
    page_name="Deconvolve (OASIS)",
    params=[
        ParamSpec("polarity", str, "drop",
                  "drop: a sudden fall then a recovery (the signal is negated); spike: a sudden rise then a decay",
                  choices=list(O.POLARITIES)),
        ParamSpec("recovery_half_s", float, 0.0,
                  "Seconds for the fade to recover half-way -- the FIRST knob: read it off a few of the recording's "
                  "own troughs. 0 estimates it from the span (reported in the readout, with a warning when it "
                  "cannot be trusted)", min=0.0),
        ParamSpec("rise_s", float, 0.0,
                  "Rise time constant in seconds for a jump that is not instant (makes the model AR(2)); "
                  "0 = an instant jump (AR(1)). Must be shorter than the recovery", min=0.0),
        ParamSpec("min_jump_sigma", float, 3.0,
                  "The smallest jump the fit may use, in noise SDs (the paper's s_min): raise it to stop noise "
                  "being explained as tiny jumps", min=0.0, max=1000.0),
        ParamSpec("baseline_window_s", float, 0.0,
                  "0 = one constant baseline per span (the paper). > 0 = a baseline that follows slow drift, "
                  "estimated over windows of this many seconds; make it several recoveries long (e.g. 15x the "
                  "recovery half-time) so it follows the drift, not the events", min=0.0),
    ],
    run=_run,
    estimate=_estimate,
    input_kind="signal",
    output_kind="scores",
    description=(
        "Explains the trace as sudden jumps, each followed by the same exponential fade, and scores every sample "
        "by the size of its jump in noise SDs (almost all zero). A drop followed by a recovery is the shape "
        "upside down; a second drop that starts before the first has recovered is a jump of its own, which a "
        "threshold would merge. The baseline is one constant per span unless baseline_window_s is set: put a "
        "long Baseline removal (or BEADS) first and/or set baseline_window_s, and Impulse events after it. "
        "The recovery half-time is the first knob to set: read it off a few of the recording's own troughs "
        "(the time a trough takes to climb half-way back); 0 estimates it, and a wrong one fragments every trough "
        "into many jumps, which the summary flags. Then min_jump_sigma. Events that are not a sudden drop "
        "followed by an exponential recovery -- a sharkfin's plateau and slow climb -- are split into many small "
        "events; check the residual SD: above ~1.5 the event count is not a trough count. The noise level is "
        "read from sample-to-sample differences, so slow, coloured noise is underestimated and its wander can "
        "pass as jumps (compare sigma_level with sigma in the readout). "
        "Friedrich, Zhou & Paninski 2017 (OASIS), written from the paper."
    ),
))
