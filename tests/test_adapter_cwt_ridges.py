"""
test_adapter_cwt_ridges.py
============================
`detection.cwt_ridges` — Signal -> SpanSet: multi-scale peaks and troughs by
CWT ridge lines (Du, Kibbe & Lin 2006), the adapter over
`Working.Detection.cwt_ridges`.

Pinned: the spec (types, category, page name, parameters with bounds, a
declared cost); one span per event, centred on it, scored by SNR, with the
feature table the template's Event shape reads; span-relative indices whatever
the span's offset; everything a page draws in `meta` (counts, scales, rules,
ridges in the recording's time, a coarse scalogram that survives the bridge's
JSON cleaner); an absence said out loud.

Runnable standalone:  python tests/test_adapter_cwt_ridges.py
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
NAME = "detection.cwt_ridges"
FS = 1.0
SIG = 2.0 * np.sqrt(2.0 * np.log(2.0))


def gauss(n, centre, fwhm, amp):
    t = np.arange(n)
    return amp * np.exp(-0.5 * ((t - centre) / (fwhm / SIG)) ** 2)


def four_hours(seed=0):
    """A 480 s spike at 1 h and a 24 s drop at 3 h on noise (volts, like M2)."""
    n = 4 * 3600
    rng = np.random.default_rng(seed)
    x = 1e-4 * rng.standard_normal(n) + gauss(n, 3600, 480, 2e-3) + gauss(n, 3 * 3600, 24, -1e-3)
    return x


def run(x, t0=0.0, **params):
    spec = get_adapter(NAME)
    x = np.asarray(x, dtype=float)
    return spec.run(x, t0 + np.arange(len(x), dtype=float) / FS, FS, **spec.validate_params(params))


def test_registered_with_the_standard_types_parameters_and_a_cost():
    spec = get_adapter(NAME)
    assert spec.input_kind == "signal" and spec.output_kind == "spanset"
    assert spec.stage == "detection" and spec.category == "detect"
    assert spec.page_name == "CWT ridges"
    assert spec.estimate is not None, "O(n log n x scales): not O(n)-cheap, so it declares a cost"
    d = spec.validate_params({})
    assert d == {"min_scale_s": 10.0, "max_scale_s": 7200.0, "n_scales": 40, "polarity": "both",
                 "min_snr": 3.0, "min_ridge_scales": 6, "max_gap_scales": 3, "noise_window_s": 3600.0}
    for p in spec.params:
        assert p.description, p.name
        if p.type in (int, float):
            assert p.min is not None and p.max is not None, f"{p.name} is unbounded"
    assert next(p for p in spec.params if p.name == "polarity").choices == ["both", "spike", "drop"]
    with pytest.raises(ValueError):
        spec.validate_params({"n_scales": 2})
    with pytest.raises(ValueError):
        spec.validate_params({"polarity": "up"})
    assert "min_snr" in spec.description and "Event shape" in spec.description


def test_one_span_per_event_centred_scored_by_snr_with_its_features():
    r = run(four_hours())
    ss = r.value
    assert isinstance(ss, SpanSet)
    f = ss.features
    assert len(ss.starts) == len(f) == 2
    for col in ("peak_idx", "best_scale_s", "duration_s", "cwt_duration_s", "ridge_scales", "snr", "polarity",
                "ridge_polarity",
                "edge_flag", "step_pair", "nan_in_support"):
        assert col in f.columns, col
    spike, drop = f.iloc[0], f.iloc[1]
    assert abs(spike["peak_idx"] - 3600) <= 30 and spike["ridge_polarity"] == "spike" and spike["polarity"] == 1
    assert abs(drop["peak_idx"] - 3 * 3600) <= 5 and drop["ridge_polarity"] == "drop" and drop["polarity"] == -1
    assert spike["duration_s"] == pytest.approx(480, rel=0.25)
    assert drop["duration_s"] == pytest.approx(24, rel=0.4)
    assert list(ss.scores) == pytest.approx(list(f["snr"]))
    assert list(ss.labels) == ["spike", "drop"]
    for s, e, pk in zip(ss.starts, ss.ends, f["peak_idx"]):
        assert s < pk < e


def test_indices_are_span_relative_whatever_the_spans_offset():
    x = four_hours()
    a = run(x).value
    b = run(x, t0=86400.0).value
    assert a == b, "the span's absolute time must not move a span-relative index"
    r = run(x, t0=86400.0)
    pts = r.meta["ridges"][0]["points"]
    assert all(p[0] >= 86400.0 - 7200 for p in pts), "ridge points are in the recording's time (t)"


def test_meta_carries_counts_scales_rules_ridges_and_a_coarse_scalogram():
    r = run(four_hours())
    m = r.meta
    assert m["n_events"] == 2
    assert m["counts_by_polarity"] == {"spike": 1, "drop": 1}
    assert m["n_edge_flagged"] == 0
    assert len(m["scales_s"]) + m["scales_dropped"] == 40
    assert m["scales_dropped"] > 0, "7200 s is too large for a 4 h span and is said to be"
    names = {d["name"] for d in m["rules"]}
    assert {"duration_s", "snr", "best_scale_s", "peak_idx", "polarity", "edge_flag", "step_pair"} <= names
    assert len(m["ridges"]) == 2 and "capped" in m["ridges_note"]
    pt = m["ridges"][0]["points"][0]
    assert len(pt) == 2
    sc = m["scalogram"]
    assert len(sc["rows"]) == len(m["scales_s"])
    assert all(len(row) <= 1024 for row in sc["rows"]), "at most 1024 columns (critic F4: meta size)"
    assert all(isinstance(v, float) and v == float(f"{v:.4g}") for row in sc["rows"] for v in row), \
        "plain floats at 4 significant figures (a float32 serialises with ~17 digits)"
    assert sc["samples_per_column"] * len(sc["rows"][0]) >= len(four_hours())
    assert "rejected" in m and m["rejected"]["side_lobes"] >= 1


def test_meta_survives_the_bridges_json_cleaner():
    """`webui/server/serialize._clean` omits a numpy array over 4096 elements; the
    scalogram travels as one row per scale so it is never silently dropped."""
    import json
    from server.serialize import _clean
    cleaned = _clean(run(four_hours()).meta)
    text = json.dumps(cleaned)
    assert "omitted" not in text
    assert len(cleaned["scalogram"]["rows"]) == len(cleaned["scales_s"])


def test_an_absence_is_said_with_its_reasons():
    x = 1e-4 * np.random.default_rng(5).standard_normal(4 * 3600)
    r = run(x)
    assert len(r.value.starts) == 0 and r.value.features is not None and len(r.value.features) == 0
    assert r.meta["n_events"] == 0
    assert "no ridge" in r.meta["absence"].lower()
    assert r.meta["rejected"]["below_snr"] > 0


def test_polarity_parameter_reports_one_side():
    x = four_hours()
    assert list(run(x, polarity="spike").value.labels) == ["spike"]
    assert list(run(x, polarity="drop").value.labels) == ["drop"]


def test_a_span_too_short_for_the_smallest_scales_is_refused_loudly():
    with pytest.raises(ValueError, match="too short"):
        run(np.zeros(30))



def test_a_days_meta_stays_under_half_a_megabyte():
    """Critic F4: the full-precision 40 x 4096 scalogram made meta ~3.5 MB a run."""
    import json
    from server.serialize import _clean
    n = 86400
    rng = np.random.default_rng(7)
    x = 1e-4 * rng.standard_normal(n) + np.cumsum(5e-6 * rng.standard_normal(n))
    for c in range(600, n - 600, 900):
        x += gauss(n, c, 24, -1e-3)
    m = run(x).meta
    assert m["n_events"] >= 50
    size = len(json.dumps(_clean(m)))
    assert size <= 500_000, f"meta is {size / 1e6:.2f} MB"


def test_the_small_scale_noise_rides_as_a_diagnostic_column():
    f = run(four_hours()).value.features
    assert "noise_min_scale" in f.columns
    assert (f["snr"] == f["peak_coef"] / f["noise"]).all()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
