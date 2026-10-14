"""
catalogue_multiscale_entropy.py
===============================
w3-a: the *Multiscale entropy* block — WindowSet → WindowSet, a feature block: the same
windows (a left-out one as a blank row, counted), with a multiscale-entropy curve and its
summaries added to the feature table (`mse_<scale>s`, `mse_ci`, `mse_slope_small`,
`mse_slope_large`, `mse_r`, `mse_n_scales`, `mse_drift_share`, `mse_n_collapsed`). The
core, and every adaptation with its reason, is `Working/Catalogue/multiscale_entropy.py`.

Chain: Detrend → Sliding windows (hours long) → Multiscale entropy → Cluster / Classifier /
compare. The template `complexity_fingerprint` is that chain with a 2 h detrend and 72 h
windows.

Cost: every scale of a window costs about `max_points`^2 / 2 template pairs (the cost cap),
times the share the sorted-template trick actually compares (data-dependent). The calibration
(`Working.block_cost`) first runs an untimed warm-up — numba compiling (about 1.5 s) or loading
from its cache the counting kernel, once per process — then times one 24 h window at 1 Hz of a
detrended AR(1) (phi 0.99) background at the defaults (about 1.6 s). `estimate` sees the span and the parameters, not the window set, so since fix round 1 (critic Q4)
it ASSUMES THE COSTLIEST TILING: n_samples x the largest pairs(W) / W over every window length W
(`costliest_pairs`). It never under-estimates; it over-estimates a 72 h tiling by up to ~3x at
1 Hz. First-round measurements (2026-10-14, this machine, warm), under the old 72 h assumption:
24 h at 1 Hz 1.6 s estimated / 1.3 s actual; 73 h at 1 Hz 2.4 / 2.0 s; 24 h at 10 Hz 1.8 / 2.1 s;
6 h windows over 73 h 2.4 / 7.1 s — the under-run this rule removes. The first run in a process
pays about 1.3 s more (1.5 s more again if numba's cache is absent).

`should_cancel` / `on_progress` are execution-time keyword arguments on `_run` (never recipe
parameters), forwarded by `Working.execution.execute_recipe(run_kwargs=...)` as
`preprocessing.window_matrix` does; a cancel between windows raises
`Working.execution.RecipeCancelled`, which the executor re-raises as a cancellation.
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.block_cost import CALIBRATION_N, estimate_seconds, register_cost_model

NAME = "catalogue.multiscale_entropy"
COST_MODEL = NAME
_CAL_FS = 1.0
_CAL_N = 24 * 3600


def _me():
    from Working.Catalogue import multiscale_entropy as ME
    return ME


def _cal_signal():
    from scipy.signal import lfilter
    from Working.Preprocessing.detrend import make_detrend_filter
    x = lfilter([1.0], [1.0, -0.99], np.random.default_rng(0).standard_normal(_CAL_N))
    return make_detrend_filter(_CAL_FS, "rolling_mean", 7200.0)(x)


def _cal_pairs():
    ME = _me()
    taus, _ = ME.scale_taus(_CAL_FS, ME.DEFAULT_SCALE_MIN_S, ME.DEFAULT_SCALE_MAX_S, ME.DEFAULT_N_SCALES)
    return ME.predicted_pairs(_CAL_N, taus)


def _warm_up():
    """Untimed: compile (or load) the numba kernel."""
    _me().warm_up()


def _time_once(x, fs):
    """The calibration run: one 24 h window at 1 Hz of a detrended AR(1) background, the defaults
    (`x` is ignored: the work must be the realistic one, not the calibrator's raw random walk)."""
    ME = _me()
    w = _cal_signal()
    taus, _ = ME.scale_taus(_CAL_FS, ME.DEFAULT_SCALE_MIN_S, ME.DEFAULT_SCALE_MAX_S, ME.DEFAULT_N_SCALES)
    ME.window_curve(w, _CAL_FS, taus)


register_cost_model(COST_MODEL, 1.0, _time_once, warm_up=_warm_up)


def estimate_pairs(n_samples, fs, method="rcmse", m=2, scale_min_s=1.0, scale_max_s=1200.0, n_scales=12,
                   min_coarse_len=1000, max_points=20_000, **params):
    """Template pairs for a span of `n_samples` under the costliest tiling (the estimate's unit)."""
    ME = _me()
    taus, _ = ME.scale_taus(float(fs), scale_min_s, scale_max_s, n_scales)
    return ME.costliest_pairs(int(n_samples), taus, method, m, min_coarse_len, max_points)


def _estimate(x, t, fs, **params):
    """Seconds for this span under the costliest tiling of it; None until calibrated."""
    n = len(x) if x is not None else 0
    if n == 0:
        return 0.0
    return estimate_seconds(COST_MODEL, CALIBRATION_N * estimate_pairs(n, fs, **params) / _cal_pairs())


def _run(x, t, fs, method="rcmse", m=2, r_frac=0.15, r_scale="mad", scale_min_s=1.0, scale_max_s=1200.0,
         n_scales=12, min_coarse_len=1000, max_points=20_000, max_gap_s=30.0, inflation_limit=1.5, seed=0,
         value=None, should_cancel=None, on_progress=None):
    if value is None:
        raise ValueError("Multiscale entropy needs a WindowSet from a prior step (input_kind='windowset'): put "
                         "Sliding windows before it, hours long")
    out = _me().multiscale_entropy(
        value, x, t, fs, m=m, r_frac=r_frac, r_scale=r_scale, method=method, scale_min_s=scale_min_s,
        scale_max_s=scale_max_s, n_scales=n_scales, min_coarse_len=min_coarse_len, max_points=max_points,
        max_gap_s=max_gap_s, inflation_limit=inflation_limit, seed=seed, should_cancel=should_cancel,
        on_progress=on_progress)
    return AdapterResult(output_kind="windowset", value=out.windows, meta=out.meta)


def _derive(x, t, fs, params, value=None):
    ME = _me()
    try:
        taus, scales = ME.scale_taus(float(fs), params["scale_min_s"], params["scale_max_s"], params["n_scales"])
    except ValueError as e:
        return [("Scales", str(e), "error")]
    rows = [("Scales", f"{len(taus)} · {scales[0]:g} – {scales[-1]:g} s", "")]
    if value is None:
        return rows + [("Windows", "run a windows block first", "warn")]
    L = int(value.length)
    reach = L / float(fs) / max(int(params["min_coarse_len"]), 1)
    n_ok = int((L // taus >= int(params["min_coarse_len"])).sum())
    rows += [("Windows", f"{int(value.n_windows):,} × {L / float(fs) / 3600:g} h", ""),
             ("Defined scales", f"{n_ok} of {len(taus)} (reach ≈ {reach:g} s)", "warn" if n_ok < 4 else "")]
    return rows


SPEC = register(AdapterSpec(
    name=NAME,
    display_name="Multiscale entropy: a complexity fingerprint per window (WindowSet -> WindowSet + features)",
    stage="catalogue",
    category="encode",
    page_name="Multiscale entropy",
    params=[
        ParamSpec("scale_max_s", float, 1200.0,
                  "Tune this first — the coarsest blur, in seconds (default 20 min, the plan's). A scale needs "
                  "min_coarse_len averaged points, so a window of W seconds reaches about W / min_coarse_len: a 24 h "
                  "window at the default ~86 s, a 72 h window ~4 min, a whole 721 h channel ~43 min. Scales beyond "
                  "the reach are blank, and said so.", min=0.001),
        ParamSpec("scale_min_s", float, 1.0, "The finest scale, in seconds (one sample at 1 Hz).", min=0.001),
        ParamSpec("n_scales", int, 12, "How many scales, spaced evenly on a log axis between the two (block sizes "
                  "that round to the same number of samples are merged).", min=1, max=60),
        ParamSpec("r_frac", float, 0.15,
                  "The match tolerance r as a fraction of the window's spread (the paper's 0.15; it suggests "
                  "0.10-0.20). Larger r: more matches, lower entropy everywhere.", min=0.01, max=1.0),
        ParamSpec("r_scale", str, "mad",
                  "The spread r is taken from, once per window and fixed across scales: mad (1.4826 × the median "
                  "absolute deviation — robust to outliers and to the events themselves) or sd (Costa's standard "
                  "deviation — inflated by drift and outliers, which makes entropy collapse).",
                  choices=["mad", "sd"]),
        ParamSpec("method", str, "rcmse",
                  "rcmse (refined composite, Wu et al. 2014 as restated by Azami et al. 2017: pools the matches of "
                  "every offset, so fewer scales are undefined on short series) or mse (Costa 2005's original, for "
                  "fidelity checks).", choices=["rcmse", "mse"]),
        ParamSpec("m", int, 2, "Template length (the paper's 2).", min=1, max=3),
        ParamSpec("min_coarse_len", int, 1000,
                  "A scale whose averaged series is shorter than this is blank (Costa's section VI kept 1,000 "
                  "points at its coarsest scale). Lowering it reaches coarser scales with noisier, biased values; "
                  "no lower default has been measured.", min=10),
        ParamSpec("max_points", int, 20_000,
                  "Cost cap: each averaged series is scored on at most this many templates (Costa's N), taken "
                  "from 10 stretches spread across the window, so every scale costs about the same. Raise it for "
                  "a steadier estimate at the cost of time (the work grows as its square).", min=1_000,
                  max=200_000),
        ParamSpec("max_gap_s", float, 30.0,
                  "Missing-sample runs up to this long are bridged by straight lines; a window with a longer run "
                  "is left out (a blank row), counted, as is a window more than 5 % filled. Both are "
                  "placeholders, not measured.", min=0.0, max=86_400.0),
        ParamSpec("inflation_limit", float, 1.5,
                  "The collapse guard: a window's spread as it arrives over its spread after a 2 h rolling mean is "
                  "taken out. Above this, drift or outliers inflated r and every scale of the window is flagged "
                  "(its entropy is low for a reason that is not the signal's). A placeholder from synthetic "
                  "measurements: stationary and detrended backgrounds scored 0.95-1.22, collapsed ones 2.8-13.",
                  min=1.0, max=100.0),
        ParamSpec("seed", int, 0, "Which windows the page draws when there are more than 64 (the values never "
                  "depend on it).", min=0),
    ],
    run=_run,
    estimate=_estimate,
    derive=_derive,
    input_kind="windowset",
    output_kind="windowset",
    description=(
        "A complexity fingerprint per window: the signal is blurred more and more (averaged over 1 s, 2 s, ... "
        "minutes) and at every blur the block asks how surprising the next value is (sample entropy; Costa, "
        "Goldberger & Peng 2005, refined composite form). White noise loses its surprise as it is blurred; a "
        "signal with structure at many time-scales keeps it — the curve's shape is the fingerprint. It needs "
        "hours per curve, so it describes recordings, species and conditions, not events. Coloured noise has a "
        "curve of its own, so judge a curve against amplitude-adjusted (aaft) copies of the same recording "
        "(Surrogate generator, method aaft) — not plain phase-randomised ones, which also change the value "
        "distribution this measure reads, so a non-Gaussian recording would beat them on its distribution "
        "alone. Tune scale_max_s first (the coarsest blur; long windows reach further). An undetrended "
        "recording collapses the curve towards 0 (drift inflates r); the block flags it — detrend upstream."
    ),
))
