"""
test_adapter_multiscale_entropy.py
==================================
w3-a: the `catalogue.multiscale_entropy` adapter — its spec (types, tab, page name, bounded
parameters), one run on a synthetic window set, the refusal without a window set, the derive
rows, the cost model (None until calibrated, then seconds that grow with the span, the warm-up
untimed), and the execution-time keywords (`should_cancel`, `on_progress`) that must never be
recipe parameters.

Runnable standalone:  python -m pytest tests/test_adapter_multiscale_entropy.py -q
"""

import inspect
import os
import sys

import numpy as np
import pytest
from scipy.signal import lfilter

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402

NAME = "catalogue.multiscale_entropy"


@pytest.fixture(scope="module")
def spec():
    discover_adapters()
    return get_adapter(NAME)


def _windows(n_hours=6, fs=1.0, window_h=2):
    spec_sw = get_adapter("preprocessing.sliding_windows")
    n = int(n_hours * 3600 * fs)
    x = lfilter([1.0], [1.0, -0.95], np.random.default_rng(0).standard_normal(n))
    t = np.arange(n) / fs
    ws = spec_sw.run(x, t, fs, **spec_sw.validate_params({"window_s": window_h * 3600.0})).value
    return x, t, ws


def test_spec_types_tab_and_page(spec):
    assert spec.input_kind == "windowset" and spec.output_kind == "windowset"
    assert spec.category == "encode" and spec.page_name == "Multiscale entropy"
    assert spec.stage == "catalogue"
    assert spec.estimate is not None
    d = spec.description.lower()
    assert "scale_max_s" in d and "amplitude-adjusted" in d and "aaft" in d


def test_parameters_are_bounded_and_runtime_hooks_are_not_parameters(spec):
    p = {ps.name: ps for ps in spec.params}
    assert p["method"].choices == ["rcmse", "mse"] and p["method"].default == "rcmse"
    assert p["r_scale"].choices == ["mad", "sd"] and p["r_scale"].default == "mad"
    assert (p["m"].min, p["m"].max, p["m"].default) == (1, 3, 2)
    assert p["r_frac"].default == 0.15 and p["min_coarse_len"].default == 1000
    assert p["max_points"].default == 20_000
    assert "placeholder" in p["max_gap_s"].description
    assert "should_cancel" not in p and "on_progress" not in p
    accepted = inspect.signature(spec.run).parameters
    assert "should_cancel" in accepted and "on_progress" in accepted
    with pytest.raises(ValueError):
        spec.validate_params({"m": 4})
    with pytest.raises(ValueError):
        spec.validate_params({"method": "fuzzy"})


def test_run_without_a_window_set_names_the_fix(spec):
    with pytest.raises(ValueError, match="Sliding windows"):
        spec.run(np.zeros(100), np.arange(100.0), 1.0, **spec.validate_params({}))


def test_one_run_carries_its_meta(spec):
    x, t, ws = _windows()
    seen = []
    r = spec.run(x, t, 1.0, **spec.validate_params({"scale_max_s": 4.0, "n_scales": 3}), value=ws,
                 on_progress=lambda d, n, s: seen.append(d))
    assert r.output_kind == "windowset"
    assert r.value.n_windows == ws.n_windows == 3 and seen == [1, 2, 3]
    F = r.value.features
    assert "split" in F.columns and {"mse_1s", "mse_2s", "mse_4s", "mse_ci"} <= set(F.columns)
    for k in ("scales_s", "taus", "method", "m", "r_rule", "defined_per_scale", "collapse", "left_out",
              "undefined_per_scale", "seconds", "rules", "curves", "summary", "warnings", "n_ci_scales"):
        assert k in r.meta, k
    assert {"name", "rule"} <= set(r.meta["rules"][0])


def test_derive_states_the_reach(spec):
    x, t, ws = _windows()
    rows = dict((a, b) for a, b, _ in spec.derive(x, t, 1.0, spec.validate_params({}), value=ws))
    assert "Defined scales" in rows and "reach" in rows["Defined scales"]
    rows0 = spec.derive(x, t, 1.0, spec.validate_params({}))
    assert any(sev == "warn" for _, _, sev in rows0)


def test_estimate_is_none_until_calibrated_then_grows_with_the_span(spec, tmp_path, monkeypatch):
    import Working.block_cost as bc
    monkeypatch.setattr(bc, "CALIBRATION_PATH", str(tmp_path / "cal.json"))
    p = spec.validate_params({})
    day = np.zeros(24 * 3600)
    assert spec.estimate(day, None, 1.0, **p) is None
    bc.calibrate(names=[NAME])
    e1 = spec.estimate(day, None, 1.0, **p)
    e3 = spec.estimate(np.zeros(73 * 3600), None, 1.0, **p)
    e30 = spec.estimate(np.zeros(721 * 3600), None, 1.0, **p)
    assert e1 > 0 and e3 > e1 and e30 > 5 * e3
    cal = bc._load()[bc._key(NAME)]
    assert cal["elapsed_s"] < 30, "the calibration timed something other than one 24 h window"


def test_cancel_through_the_adapter_raises_the_executors_cancellation(spec):
    from Working.execution import RecipeCancelled
    x, t, ws = _windows()
    with pytest.raises(RecipeCancelled):
        spec.run(x, t, 1.0, **spec.validate_params({"scale_max_s": 2.0, "n_scales": 2}), value=ws,
                 should_cancel=lambda: True)


@pytest.mark.parametrize("fs", [1.0, 10.0])
def test_the_estimate_assumes_the_costliest_tiling(spec, fs):
    """Fix round 1 (critic Q4, manager decision 3): in template pairs, no tiling of a 721 h span by
    1 h, 6 h, 24 h or 72 h windows costs more than the estimate assumes."""
    import Adapters.catalogue_multiscale_entropy as A
    ME = A._me()
    p = spec.validate_params({})
    n = int(721 * 3600 * fs)
    taus, _ = ME.scale_taus(fs, p["scale_min_s"], p["scale_max_s"], p["n_scales"])
    worst = A.estimate_pairs(n, fs, **p)
    tilings = {}
    for hours in (1, 2, 6, 24, 72):
        W = int(hours * 3600 * fs)
        tilings[hours] = (n // W) * ME.predicted_pairs(W, taus, p["method"], p["m"], p["min_coarse_len"],
                                                      p["max_points"])
        assert tilings[hours] <= worst, (hours, tilings[hours], worst)
    assert worst <= 1.05 * max(tilings.values()) * 2   # costliest, not absurd
