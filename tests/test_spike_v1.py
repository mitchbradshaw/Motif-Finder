"""
test_spike_v1.py
================
fixup-ak: the Spike detection block (Adamatzky 2023's neighbourhood-average
detector, `detection.spike_v1`) detects SPIKES, in either direction, with its
threshold in millivolts.

What is pinned:
  * the spans are the spikes (each span holds its spike's index), not the gaps
    between them;
  * the test is signed: a dip is found under `both` and `down`, not under `up`,
    and the answer does not depend on the sign or size of the DC baseline (the
    old `|x| - |a| > delta` saw one direction or the other by the baseline's sign);
  * `delta_mv` is millivolts, converted by the recording's declared unit; an
    undeclared unit is read as volts and the result says so;
  * the neighbourhood mean is vectorised and equals the per-sample loop, and a
    2.6 M-sample channel runs in under a second;
  * on coloured backgrounds (AR(1), a detrended random walk, a slow sine) the
    defaults find injected spikes of both signs and few others;
  * the page's plain words ride in meta (`explain`, `rules`) and reach the payload.

Runnable standalone:  python tests/test_spike_v1.py
"""

import os
import sys
import time

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.Detection.analysis import spike_analysis as sa  # noqa: E402

discover_adapters()
SPEC = get_adapter("detection.spike_v1")


def _run(x, fs=1.0, units="V", **params):
    t = np.arange(len(x)) / fs
    return SPEC.run(x, t, fs, **SPEC.validate_params(params), units=units)


def _dip_trace(baseline_v, n=2000, at=1000, depth_mv=5.0, width=3, seed=0):
    """A flat baseline in volts, a little white noise (0.02 mV), one dip of `depth_mv`."""
    rng = np.random.default_rng(seed)
    x = baseline_v + rng.normal(0.0, 0.02e-3, n)
    x[at:at + width] -= depth_mv * 1e-3
    return x


# --------------------------------------------------------------------- polarity

@pytest.mark.parametrize("baseline", [2.0, -2.0, 0.0, -0.43])
def test_a_dip_is_found_under_both_and_down_not_up_on_any_baseline(baseline):
    x = _dip_trace(baseline)
    for polarity, expect in (("both", True), ("down", True), ("up", False)):
        r = _run(x, delta_mv=2.0, polarity=polarity)
        idx = r.meta["spike_indices"]
        hit = any(1000 <= i < 1003 for i in idx)
        assert hit is expect, (baseline, polarity, idx)
        # nothing else on a flat trace: the dip is the only event
        assert all(995 <= i < 1008 for i in idx), (baseline, polarity, idx)


@pytest.mark.parametrize("baseline", [2.0, -2.0])
def test_a_rise_is_found_under_both_and_up_not_down(baseline):
    x = -(_dip_trace(-baseline)) # the dip mirrored: a 5 mV rise on +/-2 V
    assert any(1000 <= i < 1003 for i in _run(x, delta_mv=2.0, polarity="up").meta["spike_indices"])
    assert any(1000 <= i < 1003 for i in _run(x, delta_mv=2.0, polarity="both").meta["spike_indices"])
    assert _run(x, delta_mv=2.0, polarity="down").meta["spike_indices"] == []


def test_the_baseline_offset_does_not_change_the_answer():
    a = _run(_dip_trace(2.0), delta_mv=2.0)
    b = _run(_dip_trace(-2.0), delta_mv=2.0)
    assert a.meta["spike_indices"] == b.meta["spike_indices"] != []


# ------------------------------------------------------------------ spans = spikes

def test_spans_sit_on_the_spikes_not_between_them():
    rng = np.random.default_rng(3)
    x = -0.4 + rng.normal(0.0, 0.02e-3, 5000)
    at = [400, 1300, 2210, 3999]
    for i in at:
        x[i] += 4e-3
    r = _run(x, delta_mv=1.0)
    idx = r.meta["spike_indices"]
    assert idx == at
    assert r.meta["n_spikes"] == len(at)
    ss = r.value
    assert len(ss.starts) == len(at)
    for i, s, e in zip(idx, ss.starts, ss.ends):
        assert s <= i < e
        assert e - s == 30          # default span = the refractory gap d (30 samples)
    # the page's marks: one event per span, at its spike (span-relative, like the spans)
    assert [ev["onset_idx"] for ev in r.meta["events"]] == at
    assert [ev["trough_idx"] for ev in r.meta["events"]] == at


def test_span_s_sets_the_span_and_spans_clip_to_the_signal():
    x = np.zeros(300)
    x[2] = 5e-3
    x[297] = 5e-3
    r = _run(x, fs=2.0, delta_mv=1.0, span_s=10.0)   # 10 s at 2 Hz = 20 samples
    ss = r.value
    assert list(ss.starts) == [0, 287] and list(ss.ends) == [12, 300]
    for i, s, e in zip(r.meta["spike_indices"], ss.starts, ss.ends):
        assert s <= i < e


def test_no_spikes_is_an_empty_spanset_and_said():
    r = _run(np.full(500, -1.0), delta_mv=1.0)
    assert len(r.value.starts) == 0 and r.meta["n_spikes"] == 0


# ------------------------------------------------------------------- millivolts

def test_delta_is_millivolts_on_a_volts_recording():
    rng = np.random.default_rng(5)
    x = np.cumsum(rng.normal(0, 1e-3, 4000)) - 0.5
    r = _run(x, delta_mv=5.0, units="V")
    ref = sa.spike_detection_v1(x, width=20, delta=0.005, d=30, polarity="both")
    assert r.meta["spike_indices"] == ref.tolist()
    assert r.meta["delta_stored"] == pytest.approx(0.005)


def test_delta_is_millivolts_on_a_millivolts_recording():
    rng = np.random.default_rng(6)
    x = np.cumsum(rng.normal(0, 1.0, 4000))
    r = _run(x, delta_mv=5.0, units="mV")
    ref = sa.spike_detection_v1(x, width=20, delta=5.0, d=30, polarity="both")
    assert r.meta["spike_indices"] == ref.tolist()
    assert r.meta["delta_stored"] == pytest.approx(5.0)


def test_an_undeclared_unit_is_read_as_volts_and_says_so():
    x = _dip_trace(-2.0)
    r = _run(x, delta_mv=2.0, units=None)
    v = _run(x, delta_mv=2.0, units="V")
    assert r.meta["spike_indices"] == v.meta["spike_indices"]
    assert r.meta["units_note"] and "volts" in r.meta["units_note"]
    assert v.meta["units_note"] is None


def test_an_old_recipe_with_the_unitless_delta_is_refused_loudly():
    with pytest.raises(ValueError, match="delta"):
        SPEC.validate_params({"delta": 0.01})


# ------------------------------------------------------------------- vectorised

def _loop_mean(x, width):
    n = len(x)
    out = np.empty(n)
    for i in range(n):
        lo, hi = max(0, i - 2 * width), min(n - 1, i + 2 * width)
        out[i] = x[lo:hi + 1].mean()
    return out


@pytest.mark.parametrize("width", [1, 5, 20])
def test_the_vectorised_mean_equals_the_loop(width):
    x = np.random.default_rng(width).normal(-1.5, 0.3, 3000)
    np.testing.assert_allclose(sa.neighbourhood_mean(x, width), _loop_mean(x, width), atol=1e-9, rtol=0)


def test_a_nan_sample_is_skipped_never_a_spike():
    x = _dip_trace(-1.0)
    x[200:210] = np.nan
    r = _run(x, delta_mv=2.0)
    assert any(1000 <= i < 1003 for i in r.meta["spike_indices"])
    assert not any(200 <= i < 210 for i in r.meta["spike_indices"])
    assert r.meta["n_missing"] == 10
    m = sa.neighbourhood_mean(x, 20)
    assert np.isfinite(m[195:215]).all()   # neighbours of a gap keep a mean over their finite samples


def test_two_point_six_million_samples_run_in_under_a_second():
    rng = np.random.default_rng(7)
    x = np.cumsum(rng.normal(0, 2.5e-5, 2_600_000)) - 0.4
    sa.spike_detection_v1(x[:1000], width=20, delta=0.001, d=30)   # warm
    t0 = time.perf_counter()
    sa.spike_detection_v1(x, width=20, delta=0.001, d=30)
    assert time.perf_counter() - t0 < 1.0


# ------------------------------------------------------- coloured backgrounds

def _coloured(kind, n, rng):
    if kind == "ar1":
        e = rng.normal(0, 0.03e-3, n)
        y = np.empty(n)
        y[0] = 0.0
        for i in range(1, n):
            y[i] = 0.97 * y[i - 1] + e[i]
        return y
    if kind == "walk":
        y = np.cumsum(rng.normal(0, 0.025e-3, n))
        tt = np.arange(n)
        return y - np.polyval(np.polyfit(tt, y, 1), tt)
    if kind == "sine":
        return 20e-3 * np.sin(2 * np.pi * np.arange(n) / 21600.0) + rng.normal(0, 0.02e-3, n)
    raise ValueError(kind)


@pytest.mark.parametrize("kind", ["ar1", "walk", "sine"])
def test_the_defaults_find_spikes_of_both_signs_on_coloured_backgrounds(kind):
    rng = np.random.default_rng(11)
    n = 43200   # 12 h at 1 Hz
    x = -0.45 + _coloured(kind, n, rng)
    at = np.arange(2000, n - 2000, 4000)[:10]
    for k, i in enumerate(at):
        x[i:i + 2] += (4e-3 if k % 2 else -4e-3)
    r = _run(x)          # every default
    idx = np.asarray(r.meta["spike_indices"])
    found = sum(bool(np.any(np.abs(idx - i) <= 2)) for i in at)
    assert found == len(at), (kind, idx.tolist())
    extra = sum(not np.any(np.abs(at - j) <= 2) for j in idx)
    assert extra <= 2, (kind, extra)
    assert r.meta["n_up"] >= 5 and r.meta["n_down"] >= 5


# --------------------------------------------------------------- the page's words

def test_the_spec_names_the_knob_to_tune_first_in_millivolts():
    names = [p.name for p in SPEC.params]
    assert names[0] == "delta_mv"
    pol = next(p for p in SPEC.params if p.name == "polarity")
    assert pol.default == "both" and set(pol.choices) == {"both", "up", "down"}
    d = SPEC.description.lower()
    assert "delta_mv" in d and "first" in d and "mv" in d
    assert "each span is one spike" in d                 # the spans are the spikes, said in so many words
    assert "inter-spike" not in d
    # the knob is named on the face, not only behind the InfoTip
    r = _run(_dip_trace(-2.0), delta_mv=2.0)
    face = r.meta["explain"]["face"].lower()
    assert "tune delta_mv first" in face
    delta = next(p for p in SPEC.params if p.name == "delta_mv")
    assert "noisier" in delta.description.lower() and "placeholder" in delta.description.lower()


def test_the_explanation_and_rules_ride_in_meta_and_reach_the_payload():
    from server.serialize import to_payload
    r = _run(_dip_trace(-2.0), delta_mv=2.0)
    ex = r.meta["explain"]
    assert ex["face"] and ex["detail"] and ex["mark"]
    assert "delta_mv" in ex["detail"]
    rules = {x["name"]: x["rule"] for x in r.meta["rules"]}
    assert {"local_mean", "spike", "refractory_gap", "span"} <= set(rules)
    p = to_payload("spanset", r.value, r.meta, {"fs": 1.0, "span_start": 100})
    assert p["explain"] == ex
    assert p["rules"] and p["marks"] is not None
    assert p["marks"]["onset_s"] == [float(r.meta["spike_indices"][0] + 100)]


def test_the_readout_states_delta_in_the_stored_unit():
    x = _dip_trace(-2.0)
    rows = SPEC.derive(x, np.arange(len(x)), 1.0, SPEC.validate_params({"delta_mv": 5.0}), units="V")
    labels = {r[0]: r for r in rows}
    assert "Unit" in labels
    assert "0.005" in labels["δ as stored"][1]
    rows_none = SPEC.derive(x, np.arange(len(x)), 1.0, SPEC.validate_params({}), units=None)
    assert {r[0]: r for r in rows_none}["Unit"][2] == "warn"


# ------------------------------------------------- fix round: the halo of a wide event

def _event(baseline, n=3000, at=1000, depth_mv=-10.0, width_s=10, seed=1):
    rng = np.random.default_rng(seed)
    x = baseline + rng.normal(0.0, 0.025e-3, n)
    x[at:at + width_s] += depth_mv * 1e-3
    return x


@pytest.mark.parametrize("baseline", [-0.43, 2.0, -2.0])
@pytest.mark.parametrize("depth_mv,width_s", [(-10.0, 10), (-3.0, 30), (-30.0, 3), (-60.0, 5)])
def test_a_wide_or_deep_dip_is_one_spike_marked_as_a_dip_inside_it(baseline, depth_mv, width_s):
    x = _event(baseline, depth_mv=depth_mv, width_s=width_s)
    r = _run(x)                        # every default
    assert r.meta["n_spikes"] == 1, r.meta["spike_indices"]
    assert r.meta["n_down"] == 1 and r.meta["n_up"] == 0
    (i,) = r.meta["spike_indices"]
    assert 1000 <= i < 1000 + width_s
    assert _run(x, polarity="up").meta["n_spikes"] == 0
    assert _run(x, polarity="down").meta["spike_indices"] == [i]


def test_a_sixty_second_spike_is_one_spike_at_its_peak():
    rng = np.random.default_rng(4)
    n = 6000
    x = -0.43 + rng.normal(0.0, 0.025e-3, n)
    peaks = np.arange(500, 5600, 500)[:10]
    k = np.arange(-30, 31)
    bump = 4e-3 * (1 - np.abs(k) / 31.0)          # a 61-sample triangle, peak at its centre
    for c in peaks:
        x[c - 30:c + 31] += bump
    r = _run(x)
    idx = np.asarray(r.meta["spike_indices"])
    assert len(idx) == 10, idx.tolist()
    assert np.all(np.abs(idx - peaks) <= 1), idx.tolist()
    assert r.meta["n_up"] == 10


def test_the_readout_states_delta_against_this_spans_own_deviation():
    rng = np.random.default_rng(9)
    x = -0.4 + rng.normal(0.0, 0.1e-3, 5000)
    rows = {r[0]: r for r in SPEC.derive(x, np.arange(5000), 1.0, SPEC.validate_params({}), units="V")}
    row = rows["δ vs this span's deviation"]
    med = np.nanmedian(np.abs(sa.spike_deviation(x, 20)))
    assert f"{1e-3 / med:.1f}" in row[1]
    noisy = -0.4 + rng.normal(0.0, 1.0e-3, 5000)
    rows = {r[0]: r for r in SPEC.derive(noisy, np.arange(5000), 1.0, SPEC.validate_params({}), units="V")}
    assert rows["δ vs this span's deviation"][2] == "warn"


def test_units_note_and_the_up_down_counts_reach_the_payload_and_its_summary():
    from server.serialize import to_payload
    x = _event(-0.43, depth_mv=-10.0, width_s=10)
    x[2000] += 5e-3
    r = _run(x, units=None)
    p = to_payload("spanset", r.value, r.meta, {"fs": 1.0, "span_start": 0})
    assert p["n_up"] == 1 and p["n_down"] == 1
    assert p["units_note"] == r.meta["units_note"] and "volts" in p["units_note"]
    assert "1 up" in p["summary"] and "1 down" in p["summary"] and "read as volts" in p["summary"]
    q = to_payload("spanset", _run(x, units="V").value, _run(x, units="V").meta, {"fs": 1.0})
    assert q["units_note"] is None and "volts" not in q["summary"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
