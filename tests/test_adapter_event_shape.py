"""
test_adapter_event_shape.py
=============================
`interrogation.event_shape` (fixup-d, seam 2) — SpanSet -> SpanSet. One block
emits every per-event shape measure, polarity-neutral, as `SpanSet.features`.

The synthetic event is built so every measure has a number worked out by hand
(fs = 10 Hz, volts, as the core receives a volts channel):

    idx   0-20   flat at 0
    idx  20-50   rise to +0.002 V            (the shoulder the drop departs from)
    idx  50-70   fall to -0.008 V            (-0.0005 V/sample = -5 mV/s; depth 10 mV)
    idx  70-80   flat at -0.008 V
    idx  80-120  recover linearly to 0 V     (+0.0002 V/sample)
    idx 120-300  flat at 0

detect5's rules, reused, put the onset at 50 (the knee read backwards from the
steepest sample, then the shoulder) and the end of the fall at 71 (the knee
rule: the first of three samples shallower than 5 % of the steepest). The
extremum is the lowest sample between the steepest and that knee: 70, the
first sample of the flat bottom. Half level = onset level - depth/2 = -0.003 V:
crossed at 60 on the way down and at 105 on the way back, so FWHM = 4.5 s; half
recovery (the default `recovery_frac = 0.5`) is the same landmark, 105, so
recovery = 3.5 s and duration (onset -> recovery) = 5.5 s.

Runnable standalone:  python tests/test_adapter_event_shape.py
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.types import SpanSet  # noqa: E402

discover_adapters()
NAME = "interrogation.event_shape"
FS = 10.0

COLUMNS = ("polarity", "onset_idx", "extremum_idx", "recovery_idx", "event_amplitude_mv",
           "precursor_height_mv", "event_width_s", "duration_s", "fwhm_s", "recovery_time_s",
           "max_slope_mv_s", "onset_slope_mv_s", "chord_slope_mv_s", "peakedness", "span_ptp_mv")


def drop(n=300):
    x = np.zeros(n)
    x[20:51] = np.linspace(0.0, 0.002, 31)
    x[50:71] = np.linspace(0.002, -0.008, 21)
    x[70:81] = -0.008
    x[80:121] = np.linspace(-0.008, 0.0, 41)
    return x


def _run(x, spans=((0, 300),), **params):
    spec = get_adapter(NAME)
    ss = SpanSet(starts=tuple(s for s, _ in spans), ends=tuple(e for _, e in spans))
    return spec.run(x, np.arange(len(x)) / FS, FS, value=ss, **spec.validate_params(params))


def test_registered_as_the_first_spanset_consumer():
    spec = get_adapter(NAME)
    assert spec.stage == "interrogation"
    assert spec.input_kind == "spanset" and spec.output_kind == "spanset"
    assert spec.category == "control"
    assert spec.page_name and spec.description


def test_defaults_and_bounds():
    spec = get_adapter(NAME)
    p = spec.validate_params({})
    assert p["polarity"] == "drop" and p["recovery_frac"] == 0.5 and p["knee_frac"] == 0.05
    assert p["upstream_inverted"] is False and p["walk_onset_back"] is True
    for bad in ({"recovery_frac": 0.0}, {"recovery_frac": 1.5}, {"knee_frac": 1.2}, {"polarity": "sideways"},
                {"recovery_max_mult": 0.0}):
        with pytest.raises(ValueError):
            spec.validate_params(bad)


def test_a_drop_is_measured_by_the_stated_rules():
    r = _run(drop())
    assert r.output_kind == "spanset"
    f = r.value.features
    assert tuple(f.columns[:len(COLUMNS)]) == COLUMNS
    row = f.iloc[0]
    assert row["polarity"] == -1
    assert (row["onset_idx"], row["extremum_idx"]) == (50, 70)
    assert row["event_amplitude_mv"] == pytest.approx(10.0)
    assert row["precursor_height_mv"] == pytest.approx(2.0)
    assert row["event_width_s"] == pytest.approx(2.0)
    assert row["fwhm_s"] == pytest.approx(4.5)
    assert row["recovery_idx"] == pytest.approx(105.0)
    assert row["recovery_time_s"] == pytest.approx(3.5)
    assert row["duration_s"] == pytest.approx(5.5)
    assert row["max_slope_mv_s"] == pytest.approx(-5.0)
    assert row["chord_slope_mv_s"] == pytest.approx(-5.0)
    assert row["peakedness"] == pytest.approx(1.0)
    # np.gradient at the onset straddles the rise (+0.002/30 per sample) and the fall (-0.0005)
    assert row["onset_slope_mv_s"] == pytest.approx(10.0 * (-0.0005 + 0.002 / 30) / 2 * 1000.0)
    assert row["span_ptp_mv"] == pytest.approx(10.0)


def test_the_spans_are_passed_through_unchanged():
    x = drop()
    r = _run(x)
    assert r.value.starts == (0,) and r.value.ends == (300,)


def test_a_spike_is_the_same_measurement_about_the_opposite_sign():
    d = _run(drop()).value.features.iloc[0]
    s = _run(-drop(), polarity="spike").value.features.iloc[0]
    assert s["polarity"] == 1
    for k in ("event_amplitude_mv", "precursor_height_mv", "event_width_s", "fwhm_s", "recovery_time_s",
              "duration_s", "peakedness", "span_ptp_mv"):
        assert s[k] == pytest.approx(d[k]), k
    for k in ("max_slope_mv_s", "onset_slope_mv_s", "chord_slope_mv_s"):
        assert s[k] == pytest.approx(-d[k]), k


def test_auto_polarity_is_decided_by_the_fastest_edge():
    assert _run(drop(), polarity="auto").value.features.iloc[0]["polarity"] == -1
    assert _run(-drop(), polarity="auto").value.features.iloc[0]["polarity"] == 1


def test_the_default_is_drop_because_every_detector_here_finds_drops():
    """auto misread 50 of the 410 seed drops (their windows hold a rise and a fall of
    similar size); the default measures what the registry's detectors find."""
    assert _run(-drop()).value.features.iloc[0]["polarity"] == -1


def test_upstream_anchors_define_the_event():
    """A block upstream that already located each event (onset_idx / extremum_idx) is
    believed; the anatomy search is for spans nobody anatomised."""
    spec = get_adapter(NAME)
    feats = pd.DataFrame({"onset_idx": [48.0], "extremum_idx": [66.0]})
    ss = SpanSet(starts=(0,), ends=(300,), features=feats)
    r = spec.run(drop(), np.arange(300) / FS, FS, value=ss, **spec.validate_params({}))
    row = r.value.features.iloc[0]
    assert (row["onset_idx"], row["extremum_idx"]) == (48, 66)
    x = drop()
    assert row["event_amplitude_mv"] == pytest.approx((x[48] - x[66]) * 1000.0)
    assert any(rule["name"] == "anchors" and "upstream" in rule["rule"] for rule in r.meta["rules"])


def test_upstream_inversion_is_reported_in_the_recorded_frame():
    """The spike template inverts before the drop detector; the block then sees a drop
    and must report the spike it really is."""
    f = _run(drop(), upstream_inverted=True).value.features.iloc[0]
    assert f["polarity"] == 1
    assert f["max_slope_mv_s"] == pytest.approx(5.0)
    assert f["event_amplitude_mv"] == pytest.approx(10.0)


def test_an_event_that_never_recovers_is_nan_and_counted():
    r = _run(drop(), recovery_frac=1.0)
    row = r.value.features.iloc[0]
    assert np.isnan(row["recovery_time_s"]) and np.isnan(row["duration_s"]) and np.isnan(row["recovery_idx"])
    assert not np.isnan(row["fwhm_s"])
    assert r.meta["n_not_recovered"] == 1


def test_the_recovery_search_stops_at_the_next_event():
    x = np.concatenate([drop(), drop()])
    r = _run(x, spans=((0, 100), (100, 300), (300, 600)))
    f = r.value.features
    # the first span holds the fall; its recovery (sample 105) lies past the next span's start
    assert np.isnan(f.iloc[0]["recovery_time_s"])
    assert r.value.features.shape[0] == 3


def test_the_rules_are_in_the_meta_for_every_defined_measure():
    meta = _run(drop()).meta
    names = {r["name"] for r in meta["rules"]}
    assert {"onset", "extremum", "recovery", "fwhm", "event_width", "duration", "precursor_height",
            "polarity", "units"} <= names
    rec = next(r for r in meta["rules"] if r["name"] == "recovery")
    assert "0.5" in rec["rule"]


def test_the_rose_is_gradients_rose_data_over_the_events():
    meta = _run(np.concatenate([drop(), drop(), -drop()]), spans=((0, 300), (300, 600), (600, 900)), polarity="auto").meta
    rose = meta["rose"]
    assert rose["n"] == 3 and len(rose["counts"]) == 18 and sum(rose["counts"]) == 3
    assert rose["caption"].startswith("45°")
    assert rose["field"] == "max_slope_mv_s"
    assert set(rose["groups"]) == {"all"}
    # polarity-neutral: a spike's steepest rise lands in the same falling quadrant
    assert all(-90.0 <= a <= 0.0 for a in rose["angles_deg"])


def test_a_group_column_upstream_splits_the_rose():
    x = np.concatenate([drop(), drop(), drop()])
    feats = pd.DataFrame({"group": ["seq-1", "seq-1", "seq-2"]})
    spec = get_adapter(NAME)
    ss = SpanSet(starts=(0, 300, 600), ends=(300, 600, 900), features=feats)
    r = spec.run(x, np.arange(len(x)) / FS, FS, value=ss, **spec.validate_params({}))
    assert set(r.meta["rose"]["groups"]) == {"seq-1", "seq-2"}
    assert list(r.value.features["group"]) == ["seq-1", "seq-1", "seq-2"]


def test_upstream_feature_columns_are_kept():
    spec = get_adapter(NAME)
    ss = SpanSet(starts=(0,), ends=(300,), labels=("a",), scores=(3.0,),
                 features=pd.DataFrame({"interval_before_s": [np.nan]}))
    r = spec.run(drop(), np.arange(300) / FS, FS, value=ss, **spec.validate_params({}))
    assert "interval_before_s" in r.value.features.columns
    assert r.value.labels == ("a",) and r.value.scores == (3.0,)


def test_an_empty_spanset_is_an_empty_table_not_a_traceback():
    spec = get_adapter(NAME)
    r = spec.run(drop(), np.arange(300) / FS, FS, value=SpanSet(starts=(), ends=()), **spec.validate_params({}))
    assert len(r.value.features) == 0 and r.meta["rose"]["n"] == 0


def test_a_30s_synthetic_train():
    """The standard's 'one run on a synthetic ~30 s signal': three drops in 30 s at 10 Hz."""
    one = np.zeros(100)
    one[10:21] = np.linspace(0.0, 0.002, 11)
    one[20:31] = np.linspace(0.002, -0.008, 11)
    one[30:61] = np.linspace(-0.008, 0.0, 31)
    x = np.tile(one, 3) + 1e-7 * np.random.default_rng(0).standard_normal(300)
    r = _run(x, spans=((0, 100), (100, 200), (200, 300)))
    f = r.value.features
    assert len(f) == 3
    assert np.allclose(f["event_amplitude_mv"], 10.0, atol=0.01)
    assert (f["polarity"] == -1).all()


def test_refuses_a_missing_input():
    spec = get_adapter(NAME)
    with pytest.raises(ValueError, match="SpanSet"):
        spec.run(drop(), np.arange(300) / FS, FS, **spec.validate_params({}))


def test_why_not_reuse_is_written_down():
    import Adapters.interrogation_event_shape as mod
    doc = mod.__doc__
    assert "half_width" in doc and "Why not" in doc


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
