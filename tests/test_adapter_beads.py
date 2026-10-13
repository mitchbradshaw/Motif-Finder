"""
test_adapter_beads.py
======================
`preprocessing.beads` — Signal → Signal: the trace with its baseline removed by
BEADS (`Working.Preprocessing.beads.remove_baseline`). Pins the spec (types,
category, page name, the four parameters with their defaults and bounds), one
run on a synthetic span, what rides in `meta`, the cost estimate, and the
refusal of a span too short to solve.

Runnable standalone:  python tests/test_adapter_beads.py
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
from Working.types import Signal  # noqa: E402

discover_adapters()
NAME = "preprocessing.beads"
FS = 1.0


def run(x, fs=FS, **params):
    spec = get_adapter(NAME)
    x = np.asarray(x, dtype=float)
    return spec.run(x, np.arange(len(x), dtype=float) / fs, fs, **spec.validate_params(params))


def span(hours=3.0, fs=FS, seed=0):
    """A drifting span with three drops."""
    n = int(hours * 3600 * fs)
    t = np.arange(n) / fs
    y = 0.2 * np.sin(2 * np.pi * t / 14400.0) + 0.1 * t / t[-1] + np.random.default_rng(seed).normal(0, 0.005, n)
    for o in (0.2, 0.5, 0.8):
        i = int(o * n)
        k = np.arange(n - i)
        y[i:] -= 0.05 * np.exp(-k / (200.0 * fs))
    return y


def test_registered_with_the_standard_types_and_names():
    spec = get_adapter(NAME)
    assert spec.input_kind == "signal" and spec.output_kind == "signal"
    assert spec.stage == "preprocessing" and spec.category == "preprocess"
    assert spec.page_name == "BEADS baseline"
    assert spec.estimate is not None
    assert "baseline_period_s" in spec.description, "the description names the parameter to tune first"


def test_parameters_defaults_and_bounds():
    spec = get_adapter(NAME)
    assert [p.name for p in spec.params] == ["baseline_period_s", "polarity", "sparsity", "filter_order"]
    assert spec.validate_params({}) == {
        "baseline_period_s": 7200.0, "polarity": "drop", "sparsity": 1.0, "filter_order": 2,
    }
    by = {p.name: p for p in spec.params}
    assert by["polarity"].choices == ["drop", "spike", "both"]
    assert by["filter_order"].choices == [1, 2]
    assert by["baseline_period_s"].min is not None and by["baseline_period_s"].max is not None
    assert by["sparsity"].min > 0 and by["sparsity"].max is not None
    with pytest.raises(ValueError):
        spec.validate_params({"sparsity": 0.0})
    with pytest.raises(ValueError):
        spec.validate_params({"baseline_period_s": 1.0})
    with pytest.raises(ValueError):
        spec.validate_params({"polarity": "up"})
    with pytest.raises(ValueError):
        spec.validate_params({"filter_order": 3})


def test_a_run_returns_the_signal_with_its_baseline_removed():
    y = span()
    result = run(y, baseline_period_s=3600.0)
    assert result.output_kind == "signal"
    assert isinstance(result.value, Signal)
    out = result.value.x
    assert out.shape == y.shape and result.value.fs == FS
    assert np.isfinite(out).all()
    # the drift (0.3 units peak to peak) is gone; the 0.05 drops are kept
    quiet = np.r_[0:600, 2400:3000]
    assert np.ptp(np.convolve(out, np.ones(60) / 60, mode="valid")[quiet]) < 0.03
    i = int(0.5 * len(y))
    assert np.median(out[i - 300:i - 20]) - out[i:i + 100].min() > 0.04


def test_meta_carries_the_solve_and_its_rules():
    m = run(span(), baseline_period_s=3600.0).meta
    for key in ("fc_cycles_per_sample", "r", "lam0", "lam1", "lam2", "iterations", "converged",
                "sigma", "baseline_min", "baseline_max", "event_fraction_3sigma",
                "grid_factor", "grid_step_s", "n_nan", "polarity"):
        assert key in m, key
    assert m["fc_cycles_per_sample"] == pytest.approx(1 / 3600.0)
    names = {r["name"] for r in m["rules"]}
    assert {"sigma", "event_fraction_3sigma", "grid"} <= names
    assert all(isinstance(r["rule"], str) and r["rule"] for r in m["rules"])


def test_a_span_too_short_is_refused_with_a_reason():
    with pytest.raises(ValueError, match="at least 64 samples"):
        run(np.zeros(40))


def test_the_estimate_is_none_until_calibrated_or_a_number():
    spec = get_adapter(NAME)
    y = span(hours=1.0)
    est = spec.estimate(y, np.arange(len(y)) / FS, FS, **spec.validate_params({}))
    assert est is None or est >= 0.0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
