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
                 "baseline_window_s": 0.0}
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
    assert m["s_min"] == pytest.approx(3.0 * m["sigma"])
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


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
