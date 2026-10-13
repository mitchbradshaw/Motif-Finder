"""
test_adapter_deconvolve.py
===========================
W1-B: `detection.deconvolve` (Signal -> Scores), the adapter over the OASIS core.
Pins the spec (types, category, page name, bounded parameters), the unit-free
output (jump size in noise SDs: scaling the input x1000 changes nothing), what
rides in meta (sigma in stored units, the gamma and half-time actually used,
whether they were estimated, the rules), the estimate of the recovery, and the
sharkfin misfit the plan wants measured rather than hidden.

Runnable standalone:  python tests/test_adapter_deconvolve.py
"""

import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.types import Scores  # noqa: E402
from tests._deconv_synthetic import FS, HALF_S, troughs_12h  # noqa: E402

discover_adapters()
NAME = "detection.deconvolve"


def _run(x, **params):
    spec = get_adapter(NAME)
    t = np.arange(len(x), dtype=float) / FS
    return spec.run(x, t, FS, **spec.validate_params(params))


def test_spec_types_category_and_page_name():
    spec = get_adapter(NAME)
    assert spec.input_kind == "signal" and spec.output_kind == "scores"
    assert spec.category == "detect"
    assert spec.page_name == "Deconvolve (OASIS)"
    assert spec.stage == "detection"
    assert "detrend" in spec.description.lower() or "beads" in spec.description.lower()


def test_parameters_defaults_and_bounds():
    spec = get_adapter(NAME)
    p = spec.validate_params({})
    assert p == {"polarity": "drop", "recovery_half_s": 0.0, "rise_s": 0.0, "min_jump_sigma": 3.0,
                 "baseline_window_s": 0.0, "noise_scale": "level"}
    with pytest.raises(ValueError):
        spec.validate_params({"polarity": "sideways"})
    with pytest.raises(ValueError):
        spec.validate_params({"recovery_half_s": -1.0})
    with pytest.raises(ValueError):
        spec.validate_params({"rise_s": -1.0})
    with pytest.raises(ValueError):
        spec.validate_params({"min_jump_sigma": -0.5})
    with pytest.raises(ValueError):
        spec.validate_params({"baseline_window_s": -1.0})


def test_one_score_per_sample_in_noise_sds_and_meta():
    x, onsets, _ = troughs_12h(seed=0)
    r = _run(x, recovery_half_s=HALF_S)
    assert r.output_kind == "scores"
    assert isinstance(r.value, Scores) and len(r.value.values) == len(x) and r.value.fs == FS
    m = r.meta
    for key in ("sigma", "gamma", "recovery_half_s_used", "recovery_estimated", "baseline", "polarity",
                "s_min", "n_jumps", "n_nan", "rules", "residual_sd_sigma"):
        assert key in m, key
    assert m["sigma"] == pytest.approx(1e-4, rel=0.25)          # stored units (volts)
    assert m["recovery_half_s_used"] == pytest.approx(HALF_S)
    assert m["recovery_estimated"] is False
    assert m["noise_scale"] == "level" and m["scale"] == pytest.approx(m["sigma_level"])
    assert m["s_min"] == pytest.approx(3.0 * m["scale"])
    assert {"name", "rule"} <= set(m["rules"][0])
    big = np.flatnonzero(r.value.values > 4.0)
    for o in onsets:
        assert np.any(np.abs(big - o) <= 2), f"onset {o} has no jump above 4 SD"


def test_scaling_the_input_leaves_the_scores_unchanged():
    x, _, _ = troughs_12h(seed=4)
    a = _run(x, recovery_half_s=0.0)
    b = _run(x * 1000.0, recovery_half_s=0.0)
    np.testing.assert_allclose(a.value.values, b.value.values, rtol=1e-6, atol=1e-6)
    assert b.meta["sigma"] == pytest.approx(1000.0 * a.meta["sigma"])


def test_recovery_estimated_when_zero():
    x, _, _ = troughs_12h(seed=2)
    r = _run(x, recovery_half_s=0.0)
    assert r.meta["recovery_estimated"] is True
    assert r.meta["recovery_half_s_used"] == pytest.approx(HALF_S, rel=0.20)


def test_ar2_rise_is_reported():
    x, _, _ = troughs_12h(seed=0)
    r = _run(x, recovery_half_s=HALF_S, rise_s=3.0)
    assert r.meta["model"] == "AR(2)"
    assert r.meta["rise_s"] == pytest.approx(3.0)
    assert len(r.meta["ar_coefficients"]) == 2


def test_running_baseline_is_reported_and_constant_by_default():
    x, _, _ = troughs_12h(seed=0)
    const = _run(x, recovery_half_s=HALF_S)
    assert const.meta["baseline_mode"] == "constant" and const.meta["baseline_range"] is None
    run = _run(x, recovery_half_s=HALF_S, baseline_window_s=1800.0)
    assert run.meta["baseline_mode"] == "running" and run.meta["baseline_window_s"] == 1800.0
    lo, hi = run.meta["baseline_range"]
    assert lo <= hi and abs(run.meta["baseline"] - 0.010) < 3e-4      # signal orientation, volts


def test_sharkfin_misfit_is_measured_not_hidden():
    """A sharkfin (drop -> floor held ~60 % of the interval -> slow climb) is not an
    AR(1) trough: the kernel recovers fastest first. The fit's residual says so."""
    n, period = 12_000, 1500
    x = np.full(n, 0.01)
    t = np.arange(period, dtype=float)
    fin = np.where(t < 0.6 * period, -4e-3, -4e-3 * (1 - (t - 0.6 * period) / (0.4 * period)))
    for k in range(1, n // period - 1):
        x[k * period:(k + 1) * period] += fin
    x += 1e-4 * np.random.default_rng(0).standard_normal(n)
    trough, _, _ = troughs_12h(seed=0)
    shark = _run(x, recovery_half_s=0.0)
    clean = _run(trough, recovery_half_s=0.0)
    assert clean.meta["residual_sd_sigma"] < 1.5        # the right kernel leaves noise
    assert shark.meta["residual_sd_sigma"] > clean.meta["residual_sd_sigma"]



# -- review fixes (F2-F5, F7, F9) ------------------------------------------------

def test_a_quiet_channel_with_estimation_on_returns_zero_scores_not_an_error():
    """F2: pure white noise has no recovery to estimate. That is a quiet channel, not a
    failed run: all-zero scores, recovery_estimated False, and a summary that says why."""
    x = 0.01 + 1e-4 * np.random.default_rng(3).standard_normal(20_000)
    r = _run(x, recovery_half_s=0.0)
    assert np.all(r.value.values[np.isfinite(r.value.values)] == 0.0)
    assert r.meta["recovery_estimated"] is False
    assert r.meta["n_jumps"] == 0
    assert "could not be estimated" in r.meta["summary"]


def test_a_quiet_ramp_with_estimation_on_returns_zero_scores_not_an_error():
    """F2: a slow ramp (rising, the way a drop-polarity fit cannot explain as jumps) on noise
    is drift, not recovery; with nothing to explain it is still a quiet channel."""
    n = 20_000
    x = 0.01 + 2e-3 * np.arange(n) / n + 1e-4 * np.random.default_rng(0).standard_normal(n)
    r = _run(x, recovery_half_s=0.0, baseline_window_s=1800.0)
    assert r.meta["recovery_estimated"] is False
    assert r.meta["n_jumps"] == 0
    assert "could not be estimated" in r.meta["summary"]


def test_sharkfin_residual_above_1_5_is_flagged_in_the_summary():
    """F3: a sharkfin fragments into many jumps; the residual SD says so, loudly."""
    n, period = 12_000, 1500
    x = np.full(n, 0.01)
    t = np.arange(period, dtype=float)
    fin = np.where(t < 0.6 * period, -4e-3, -4e-3 * (1 - (t - 0.6 * period) / (0.4 * period)))
    for k in range(1, n // period - 1):
        x[k * period:(k + 1) * period] += fin
    x += 1e-4 * np.random.default_rng(0).standard_normal(n)
    r = _run(x, recovery_half_s=HALF_S)
    assert r.meta["residual_sd_sigma"] > 1.5
    assert any("residual SD" in w for w in r.meta["warnings"])
    assert "residual SD" in r.meta["summary"] and "not a trough count" in r.meta["summary"]
    clean = _run(troughs_12h(seed=0)[0], recovery_half_s=HALF_S)
    assert not any("residual SD" in w for w in clean.meta["warnings"])


def test_descriptions_name_the_recovery_first_and_the_sharkfin_limit():
    d = get_adapter(NAME).description
    assert "recovery half-time is the first knob" in d
    assert "sharkfin" in d and "residual SD" in d and "1.5" in d
    assert "coloured" in d or "colored" in d                       # F4: sigma's blind spot named


def test_sigma_level_rides_beside_sigma_and_reads_coloured_noise():
    """F4: sigma (first differences) underestimates slow, coloured noise; sigma_level (the robust
    SD of the trace about its baseline) does not, so the two side by side show it."""
    rng = np.random.default_rng(5)
    n, phi = 40_000, 0.95
    e = rng.standard_normal(n) * 1e-4
    ar = np.zeros(n)
    for i in range(1, n):
        ar[i] = phi * ar[i - 1] + e[i]
    r = _run(0.01 + ar, recovery_half_s=HALF_S)
    true_sd = float(np.std(ar))
    assert r.meta["sigma"] < 0.4 * true_sd
    assert r.meta["sigma_level"] == pytest.approx(true_sd, rel=0.3)


def test_the_running_baseline_converges():
    """F5: the running baseline's refinement halves its step each pass; a tolerance of a
    twentieth of a noise SD is met well inside the pass budget."""
    from Working.Preprocessing.detrend import make_detrend_filter
    x, _, _ = troughs_12h(seed=0, drift=4e-3)
    xd = make_detrend_filter(FS, "rolling_mean", 3600.0)(x)
    r = _run(xd, recovery_half_s=HALF_S, baseline_window_s=1800.0)
    assert r.meta["baseline_converged"] is True
    assert r.meta["n_baseline_iter"] < 10
    assert "not converged" not in r.meta["summary"]


def test_a_run_that_starts_low_after_a_nan_gap_is_counted():
    """F7: a drop at the first sample after a NaN gap cannot be a jump (it is that run's
    initial level); the runs where that level is itself a jump-sized value are counted."""
    x, onsets, _ = troughs_12h(seed=0)
    x = x.copy()
    o = onsets[3]
    x[o - 50:o] = np.nan                         # the gap ends exactly at a drop
    r = _run(x, recovery_half_s=HALF_S)
    assert r.meta["n_runs_starting_above_min_jump"] == 1
    assert "1 run starts" in r.meta["summary"]
    clean = _run(troughs_12h(seed=0)[0], recovery_half_s=HALF_S)
    assert clean.meta["n_runs_starting_above_min_jump"] == 0


def test_a_cost_model_is_declared():
    """F9: the block's runtime is linear in the span (the estimate capped), calibrated like the others."""
    from Working import block_cost
    spec = get_adapter(NAME)
    assert NAME in block_cost.MODELS
    exponent, run_once = block_cost.MODELS[NAME]
    assert exponent == 1.0
    x = np.cumsum(np.random.default_rng(0).standard_normal(20_000)) * 1e-3   # calibrate()'s own signal
    run_once(x, 1.0)
    assert spec.estimate is not None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
