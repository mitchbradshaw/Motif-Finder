"""
test_adapter_fluss.py
=====================
`detection.fluss` — Signal -> Scores, the regime-change score (1 - CAC) of
FLUSS (Gharghabi et al. 2017) over the matrix-profile index of the span.

Pins: the spec (types, tab, name, parameters and bounds, a declared cost);
on the shared synthetic recording the score peaks within two windows of the
regime boundary with either idealised arc curve; a pure drift ramp fails safe
(the score stays under the template's cut); refusals are loud.

Runnable standalone:  python tests/test_adapter_fluss.py
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
from tests._fluss_synthetic import BOUNDARY, FS, drift_ramp, two_regimes  # noqa: E402

discover_adapters()

#: the cut `fluss_regimes` uses (tests/test_template_fluss_regimes.py)
CUT = 0.38


@pytest.fixture(scope="module")
def spec():
    return get_adapter("detection.fluss")


def _run(spec, x, **params):
    t = np.arange(len(x), dtype=float) / FS
    return spec.run(x, t, FS, **spec.validate_params(params))


@pytest.fixture(scope="module")
def two_result(spec):
    return _run(spec, two_regimes())


# ── the spec ──────────────────────────────────────────────────────────────────

def test_spec_types_tab_and_name(spec):
    assert spec.input_kind == "signal"
    assert spec.output_kind == "scores"
    assert spec.stage == "detection"
    assert spec.category == "detect"
    assert spec.page_name == "FLUSS regime change"


def test_parameters_and_defaults(spec):
    p = spec.validate_params({})
    assert p == {"window_s": 60.0, "n_regimes_readout": 3, "iac": "parabola", "excl_factor": 5}
    iac = next(ps for ps in spec.params if ps.name == "iac")
    assert set(iac.choices) == {"parabola", "beta"}


@pytest.mark.parametrize("bad", [{"window_s": 0.0}, {"iac": "cubic"}, {"excl_factor": 0},
                                 {"n_regimes_readout": 1}])
def test_out_of_bounds_parameters_are_refused(spec, bad):
    with pytest.raises(ValueError):
        spec.validate_params(bad)


def test_cost_is_declared_with_the_matrix_profile_model(spec):
    from Working.Detection.matrix_profiling import cost
    from tests._calibration_isolation import scratch_calibration
    assert spec.estimate is not None
    x = np.zeros(10_000)
    with scratch_calibration(cost):
        assert spec.estimate(x, np.arange(len(x), dtype=float), FS, **spec.validate_params({})) is None
        cost._save_calibration({cost._calibration_key("stump"): {"k": 2e-9}})
        got = spec.estimate(x, np.arange(len(x), dtype=float), FS, **spec.validate_params({}))
    assert got == pytest.approx(2e-9 * len(x) ** 2)


def test_description_tells_a_newcomer_to_detrend_first(spec):
    d = spec.description.lower()
    assert "detrend" in d and "window_s" in d


# ── on the synthetic recording ───────────────────────────────────────────────

def test_the_output_is_one_score_per_sample(two_result):
    r = two_result
    assert r.output_kind == "scores"
    assert isinstance(r.value, Scores)
    assert len(r.value.values) == 2 * 7200
    assert r.value.fs == FS


def test_the_score_peaks_within_two_windows_of_the_boundary(two_result):
    m = two_result.meta["m"]
    assert m == 60
    assert abs(int(np.nanargmax(two_result.value.values)) - BOUNDARY) <= 2 * m
    assert np.nanmax(two_result.value.values) > CUT
    assert abs(two_result.meta["regime_locs"][0] - BOUNDARY) <= 2 * m


def test_meta_carries_the_readout_and_the_rules(two_result):
    meta = two_result.meta
    for key in ("m", "window_s", "iac", "excl_factor", "cac_min", "cac_min_idx", "regime_locs",
                "regime_cac", "n_blanked_each_end", "n_no_neighbour", "backend", "rules"):
        assert key in meta, key
    assert len(meta["regime_locs"]) == 2                  # n_regimes_readout=3 -> two changes
    names = {r["name"] for r in meta["rules"]}
    assert {"regime-change score", "blanked edges"} <= names


def test_beta_iac_also_runs_and_agrees_on_the_boundary(spec):
    r = _run(spec, two_regimes(), iac="beta")
    assert r.meta["iac"] == "beta"
    assert abs(int(np.nanargmax(r.value.values)) - BOUNDARY) <= 2 * r.meta["m"]


def test_a_drift_ramp_fails_safe(spec):
    """z-normalised ramp windows match anywhere: arcs cross everywhere, CAC stays near 1."""
    r = _run(spec, drift_ramp())
    assert np.nanmax(r.value.values) < CUT


# ── refusals ──────────────────────────────────────────────────────────────────

def test_a_window_shorter_than_stumpy_allows_is_refused(spec):
    with pytest.raises(ValueError, match="window"):
        _run(spec, two_regimes(), window_s=2.0)


def test_a_span_too_short_for_the_window_is_refused(spec):
    with pytest.raises(ValueError, match="too short"):
        _run(spec, two_regimes()[:500])


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
