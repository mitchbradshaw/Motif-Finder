"""
test_adapter_noise_threshold.py
=================================
`detection.noise_threshold` — Signal → SpanSet: a cut in multiples of the
channel's own robust noise level (Quian Quiroga, Nadasdy & Ben-Shaul 2004,
eq. 3.1: Thr = 4 σ_n, σ_n = median|x| / 0.6745), so the researcher types a
unit-free `k_sigma` instead of a level in volts or millivolts.

What is pinned here:
  * the σ_n estimator — within 3 % of a white noise's σ, and within 10 % when
    5 % of the samples are large spikes that throw the plain SD far off;
  * unit freedom — the same spans whether the trace is stored in V or mV;
  * `direction` — exactly `detection.signal_threshold`'s semantics at the
    equivalent absolute cut;
  * honesty — the > 20 % "events are not a small fraction" warning, a flat
    trace's zero noise level, NaN samples;
  * `noise_from='rolling'` — a noise level that changes along the trace;
  * the tidying parameters are `detection.threshold`'s own, not a copy.

Runnable standalone:  python tests/test_adapter_noise_threshold.py
"""

import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
for _p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.types import SpanSet  # noqa: E402

discover_adapters()
NAME = "detection.noise_threshold"
FS = 1.0


def run(x, name=NAME, **params):
    spec = get_adapter(name)
    x = np.asarray(x, dtype=float)
    return spec.run(x, np.arange(len(x), dtype=float) / FS, FS, **spec.validate_params(params))


def spans(result):
    return list(zip(result.value.starts, result.value.ends))


def white(n, sigma=1.0, seed=0):
    return sigma * np.random.default_rng(seed).standard_normal(n)


# ── registration ─────────────────────────────────────────────────────────────

def test_registered_with_the_standard_types_and_parameters():
    spec = get_adapter(NAME)
    assert spec.input_kind == "signal" and spec.output_kind == "spanset"
    assert spec.stage == "detection" and spec.category == "detect"
    assert spec.page_name == "Noise threshold"
    names = {p.name for p in spec.params}
    assert names == {"k_sigma", "direction", "noise_from", "noise_window_s", "min_duration_s", "merge_gap_s"}
    assert "threshold" not in names, \
        "a float named `threshold` makes the view draw an absolute, draggable level — this cut is relative"
    d = spec.validate_params({})
    assert d["k_sigma"] == 4.0, "the paper's 4 σ_n"
    assert d["noise_from"] == "whole_span"
    assert d["min_duration_s"] == 0.0 and d["merge_gap_s"] == 0.0
    sibling = get_adapter("detection.signal_threshold")
    ours = next(p for p in spec.params if p.name == "direction")
    theirs = next(p for p in sibling.params if p.name == "direction")
    assert ours.choices == theirs.choices
    noise_from = next(p for p in spec.params if p.name == "noise_from")
    assert noise_from.choices == ["whole_span", "rolling"]
    with pytest.raises(ValueError, match="k_sigma"):
        spec.validate_params({"k_sigma": 0.0})
    assert spec.derive is not None, "the computed σ_n and cut are printed as derive rows"
    assert "k_sigma" in spec.description


def test_the_tidying_is_detection_thresholds_own_not_a_copy():
    from Adapters import detection_noise_threshold as mod
    from Adapters import detection_signal_threshold as sig
    from Adapters import detection_threshold as thr
    assert mod.tidy_spans is thr.tidy_spans
    assert mod.spans_from_mask is thr.spans_from_mask
    assert mod._mask_and_excursion is sig._mask_and_excursion
    ours = {p.name: p for p in get_adapter(NAME).params}
    for p in thr.tidy_param_specs():
        assert ours[p.name].default == p.default and ours[p.name].description == p.description


# ── the noise estimator ─────────────────────────────────────────────────────

def test_sigma_of_white_noise_is_within_three_percent():
    from Working.Detection.analysis.noise_level import noise_sigma
    x = white(200_000, sigma=2.0, seed=1)
    assert noise_sigma(x) == pytest.approx(2.0, rel=0.03)
    r = run(x)
    assert r.meta["sigma"] == pytest.approx(2.0, rel=0.03)


def test_sigma_ignores_five_percent_spikes_that_ruin_the_plain_sd():
    from Working.Detection.analysis.noise_level import noise_sigma
    x = white(200_000, sigma=1.0, seed=2)
    idx = np.random.default_rng(3).choice(len(x), size=len(x) // 20, replace=False)
    x[idx] = 40.0
    assert noise_sigma(x) == pytest.approx(1.0, rel=0.10)
    assert np.std(x) > 3.0, "the plain SD is far off — that is the point of the median"
    r = run(x, direction="above")
    assert r.meta["sigma"] == pytest.approx(1.0, rel=0.10)
    assert r.meta["plain_sd"] == pytest.approx(np.std(x), rel=1e-6)


def test_sigma_is_a_deviation_so_an_offset_cannot_bias_it():
    from Working.Detection.analysis.noise_level import noise_sigma
    x = white(50_000, sigma=1.0, seed=4)
    assert noise_sigma(x + 25.0) == pytest.approx(noise_sigma(x), rel=1e-9)
    a, b = run(x, direction="either"), run(x + 25.0, direction="either")
    assert spans(a) == spans(b)
    assert b.meta["centre"] == pytest.approx(a.meta["centre"] + 25.0)


def test_nan_samples_are_skipped_by_the_estimate_and_never_in_a_span():
    from Working.Detection.analysis.noise_level import noise_sigma
    x = white(20_000, sigma=1.0, seed=5)
    x[100:200] = np.nan
    assert np.isfinite(noise_sigma(x))
    x[300:305] = 10.0
    r = run(x, direction="above")
    assert r.meta["n_nan"] == 100
    assert (300, 305) in spans(r)
    for s, e in spans(r):
        assert not np.isnan(x[s:e]).any()


# ── unit freedom ─────────────────────────────────────────────────────────────

def test_volts_and_millivolts_give_the_same_spans():
    x = white(5_000, sigma=0.0002, seed=6) - 0.44
    x[1000:1060] -= 0.004
    x[3000:3010] += 0.003
    v = run(x, direction="either")
    mv = run(x * 1000.0, direction="either")
    assert spans(v) == spans(mv)
    assert len(spans(v)) >= 2
    np.testing.assert_allclose(v.value.scores, mv.value.scores, rtol=1e-9)
    assert mv.meta["sigma"] == pytest.approx(1000.0 * v.meta["sigma"])
    assert mv.meta["cut_below"] == pytest.approx(1000.0 * v.meta["cut_below"])


# ── direction: signal_threshold's semantics at the equivalent cut ───────────

@pytest.mark.parametrize("direction", ["above", "below", "either"])
def test_direction_matches_signal_threshold_at_the_equivalent_cut(direction):
    rng = np.random.default_rng(7)
    x = rng.standard_normal(4000)
    for a, amp in ((300, 9.0), (900, -9.0), (2000, 12.0), (3100, -7.0)):
        x[a:a + 6] = amp
    x -= np.median(x)                            # zero median: signal_threshold's `either` is |x| about zero
    r = run(x, direction=direction)
    sigma, k = r.meta["sigma"], r.meta["k_sigma"]
    assert r.meta["centre"] == pytest.approx(0.0, abs=1e-12)
    cut = {"above": k * sigma, "below": -k * sigma, "either": k * sigma}[direction]
    ref = run(x, name="detection.signal_threshold", threshold=cut, direction=direction)
    assert spans(r) == spans(ref)
    assert len(spans(r)) >= 2
    # the score is the same excursion, expressed in σ_n units
    np.testing.assert_allclose(r.value.scores, np.asarray(ref.value.scores) / sigma, rtol=1e-9)


def test_cut_above_and_below_are_in_stored_units_around_the_median():
    x = white(20_000, sigma=0.5, seed=8) + 3.0
    r = run(x, k_sigma=3.0)
    m, s = r.meta["centre"], r.meta["sigma"]
    assert m == pytest.approx(3.0, abs=0.02)
    assert r.meta["cut_above"] == pytest.approx(m + 3.0 * s)
    assert r.meta["cut_below"] == pytest.approx(m - 3.0 * s)
    assert any(rule["name"] == "score" for rule in r.meta["rules"])


# ── honesty on the face ──────────────────────────────────────────────────────

def test_the_twenty_percent_warning_fires_only_when_events_dominate():
    quiet = white(10_000, seed=9)
    quiet[::100] = 15.0                          # 1 % of samples: the paper's assumption holds
    r = run(quiet, direction="above")
    assert r.meta["fraction_past_cut"] < 0.2
    assert not any("20" in w for w in r.meta["warnings"]), r.meta["warnings"]

    busy = white(10_000, seed=10)
    busy[np.arange(len(busy)) % 10 < 4] += 30.0  # 40 % of samples are "events"
    r = run(busy, direction="either")
    assert r.meta["fraction_past_cut"] > 0.2
    assert any("small fraction" in w for w in r.meta["warnings"]), r.meta["warnings"]


def test_a_flat_trace_has_no_noise_level_and_says_so():
    r = run(np.full(500, -0.44))
    assert spans(r) == []
    assert r.meta["sigma"] == 0.0
    assert r.meta["n_unjudged"] == 500
    assert r.meta["warnings"], "a zero noise level is reported, not hidden"


def test_an_all_nan_trace_is_empty_with_a_warning():
    r = run(np.full(50, np.nan))
    assert spans(r) == [] and isinstance(r.value, SpanSet)
    assert r.meta["warnings"]


def test_tidying_joins_and_drops_like_the_sibling():
    x = np.zeros(400)
    x[:] = white(400, seed=11) * 0.01
    x[100:110] = 5.0
    x[112:120] = 5.0
    x[300] = 5.0
    r = run(x, direction="above", merge_gap_s=3.0, min_duration_s=2.0)
    assert spans(r) == [(100, 120)]


# ── rolling noise level ──────────────────────────────────────────────────────

def test_rolling_noise_follows_a_noise_level_that_changes():
    from Working.Detection.analysis.noise_level import rolling_noise
    n = 40_000
    rng = np.random.default_rng(12)
    x = np.concatenate([rng.standard_normal(n // 2), 3.0 * rng.standard_normal(n // 2)])
    centre, sigma = rolling_noise(x, 2000)
    assert centre.shape == sigma.shape == x.shape
    assert np.median(sigma[: n // 2 - 2000]) == pytest.approx(1.0, rel=0.1)
    assert np.median(sigma[n // 2 + 2000:]) == pytest.approx(3.0, rel=0.1)

    events = [(2000 + 3000 * i, 2005 + 3000 * i) for i in range(5)]   # all in the quiet half
    for a, b in events:
        x[a:b] = 6.0                             # 6 σ of the quiet half, but < 4 σ of the whole
    whole = run(x, direction="above")
    rolling = run(x, direction="above", noise_from="rolling", noise_window_s=2000.0)
    assert not any(ev in spans(whole) for ev in events), "a whole-span σ_n is inflated by the loud half"
    for ev in events:
        assert ev in spans(rolling), (ev, spans(rolling))
    assert rolling.meta["sigma_min"] == pytest.approx(1.0, rel=0.15)
    assert rolling.meta["sigma_max"] == pytest.approx(3.0, rel=0.15)
    loud_false = [sp for sp in spans(rolling) if sp[0] >= n // 2 + 2000]
    assert len(loud_false) <= 5, "the loud half is judged against its own noise, not the quiet half's"


def test_rolling_with_a_window_longer_than_the_span_is_the_whole_span():
    x = white(3000, seed=13)
    x[500:505] = 8.0
    a = run(x, direction="above")
    b = run(x, direction="above", noise_from="rolling", noise_window_s=10_000.0)
    assert spans(a) == spans(b)
    assert b.meta["sigma"] == pytest.approx(a.meta["sigma"])


# ── derive ───────────────────────────────────────────────────────────────────

def test_derive_prints_sigma_and_the_cut():
    spec = get_adapter(NAME)
    x = white(5000, sigma=0.002, seed=14)
    rows = spec.derive(x, np.arange(len(x), dtype=float), FS, spec.validate_params({"direction": "below"}))
    labels = [r[0] for r in rows]
    assert any("σ" in lab or "noise" in lab.lower() for lab in labels)
    assert any("cut" in lab.lower() for lab in labels)
    assert all(len(r) == 3 for r in rows)


def test_filed_as_a_threshold_detector_for_discovery_compare():
    from Working.discovery import compare as dc
    assert dc.role_of(get_adapter(NAME)) == "Detect"
    assert dc.glyph_for(NAME) == "threshold"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
