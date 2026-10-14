"""
test_adapter_cycle_shapes.py
==============================
`interrogation.cycle_shapes` (w3-b), SpanSet -> SpanSet: the spec, the columns it
adds (and that the spans and upstream columns pass through), `write_group` with
the Trains / families helper and suffixes, the optional `waveform` side input and
its loud refusals, the bookkeeping columns, and the meta a page reads (summary,
rules, exemplars, the stack payload).
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _cycle_synthetic as syn  # noqa: E402
from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.Catalogue.shape_families import NOISE_LIKE_SUFFIX, UNTESTED_SUFFIX  # noqa: E402
from Working.types import Signal, SpanSet  # noqa: E402
from Working.types.windowset import BOOKKEEPING_COLUMNS  # noqa: E402

NAME = "interrogation.cycle_shapes"
ADDED = ("cycle_index", "cycle_length_s", "cycle_amplitude", "cycle_group", "cycle_change", "cycle_shift_s",
         "cycle_corr", "cycle_floor_frac", "cycle_half_recovery_frac", "cycle_omit_reason")


@pytest.fixture(scope="module")
def spec():
    discover_adapters()
    return get_adapter(NAME)


def _spans(st, en, **cols):
    feats = pd.DataFrame(cols) if cols else None
    return SpanSet(starts=tuple(int(s) for s in st), ends=tuple(int(e) for e in en), features=feats)


def _go(spec, x, spans, waveform=None, **params):
    p = spec.validate_params(params)
    extra = {} if waveform is None else {"waveform": waveform}
    return spec.run(x, np.arange(len(x), dtype=float), 1.0, value=spans, **extra, **p)


def test_spec_types_category_and_side_input(spec):
    assert spec.stage == "interrogation" and spec.category == "cluster" and spec.page_name == "Cycle shapes"
    assert spec.input_kind == "spanset" and spec.output_kind == "spanset"
    [side] = spec.side_inputs
    assert side.name == "waveform" and side.type_kind == "signal"
    assert set(side.sources) == {"root_signal", "earlier_step"} and side.required is False
    assert spec.estimate is not None
    assert "EXPERIMENTAL" in spec.description and "max_cycle_s" in spec.description


def test_defaults_and_bounds(spec):
    p = spec.validate_params({})
    assert p["n_points"] == 256 and p["max_shift_frac"] == 0.1 and p["max_iter"] == 8 and p["k_max"] == 6
    assert p["min_cycles"] == 10 and p["floor_band"] == 0.25 and p["write_group"] is False
    assert p["cycle_detrend"] == "chord" and p["null_draws"] == 20
    with pytest.raises(ValueError):
        spec.validate_params({"max_shift_frac": 0.9})
    with pytest.raises(ValueError):
        spec.validate_params({"cycle_detrend": "spline"})


@pytest.fixture(scope="module")
def chain_run(spec):
    x, st, en = syn.two_family_chain("ar1")
    spans = _spans(st, en, span_score=np.ones(st.size), group=["A"] * st.size)
    return x, spans, _go(spec, x, spans, null_draws=3, write_group=True)


def test_the_spans_and_upstream_columns_pass_through_with_the_new_columns(chain_run):
    x, spans, r = chain_run
    out = r.value
    assert out.starts == spans.starts and out.ends == spans.ends
    f = out.features
    for c in ADDED + ("span_score", "group", "group_upstream"):
        assert c in f.columns, c
    assert len(f) == len(spans.starts)
    assert (f["cycle_group"].iloc[:-1] > 0).all() and f["cycle_group"].iloc[-1] == -1
    assert f["cycle_omit_reason"].iloc[-1] == "opens_no_cycle"


def test_write_group_prefixes_the_upstream_group_and_keeps_it(chain_run):
    _, _, r = chain_run
    f = r.value.features
    assert (f["group_upstream"] == "A").all()
    assert all(str(g).startswith("A/") for g in f["group"])
    assert set(f["group"]) >= {"A/1", "A/2", "A/-1"}
    assert any(rule["name"] == "group" for rule in r.meta["rules"])


def test_write_group_off_leaves_group_alone(spec):
    x, st, en = syn.chain([syn.sharkfin] * 12, syn.drifting_periods(12), bg="ar1", noise=0.1, seed=1)
    spans = _spans(st, en, group=["chan0"] * st.size)
    r = _go(spec, x, spans, null_draws=0)
    f = r.value.features
    assert list(f["group"]) == ["chan0"] * st.size and "group_upstream" not in f.columns


def test_untested_groups_are_marked_and_never_unmarked(spec):
    x, st, en = syn.chain([syn.sharkfin] * 12, syn.drifting_periods(12), bg="ar1", noise=0.1, seed=1)
    r = _go(spec, x, _spans(st, en), null_draws=0, write_group=True)
    keys = set(r.value.features["group"])
    assert keys <= {"-1", "1" + UNTESTED_SUFFIX}, keys
    assert "1" + UNTESTED_SUFFIX in keys


def test_noise_like_groups_are_marked(spec):
    x, st, en = syn.poisson_events(60, "ar1")
    r = _go(spec, x, _spans(st, en), write_group=True, min_cycles=8)
    keys = {k for k in r.value.features["group"] if k != "-1"}
    assert keys and all(k.endswith(NOISE_LIKE_SUFFIX) for k in keys), keys


def test_the_cycle_bookkeeping_columns_are_bookkeeping():
    for c in ("cycle_index", "cycle_group", "cycle_change", "cycle_omit_reason", "cycle_corr", "cycle_shift_s"):
        assert c in BOOKKEEPING_COLUMNS, c
    for c in ("cycle_length_s", "cycle_amplitude", "cycle_floor_frac", "cycle_half_recovery_frac"):
        assert c not in BOOKKEEPING_COLUMNS, c


def test_meta_carries_summary_rules_exemplars_and_the_stack(chain_run):
    _, spans, r = chain_run
    m = r.meta
    assert m["summary"] and "K = 2" in m["summary"]
    names = {rule["name"] for rule in m["rules"]}
    assert {"cycle", "cycle_floor_frac", "cycle_half_recovery_frac", "coherence", "verdict", "order"} <= names
    ex = m["exemplar_events"]
    g = r.value.features["cycle_group"].to_numpy()
    assert set(ex) == {"1", "2"} and all(g[i] == int(k) for k, i in ex.items())
    assert m["cycle_stack"]["n_rows"] == 120 and len(m["cycle_stack"]["rows"][0]["after"]) == 128
    assert m["write_group"] is True and m["waveform"] == "the chain's signal (x)"


def test_meta_is_plain_json_with_no_nan(chain_run):
    import json
    _, _, r = chain_run
    json.dumps(r.meta, allow_nan=False)


def test_the_waveform_side_input_is_used_and_checked(spec):
    x, st, en = syn.chain([syn.sharkfin] * 12, syn.drifting_periods(12), bg="ar1", noise=0.1, seed=1)
    spans = _spans(st, en)
    r = _go(spec, np.zeros_like(x), spans, null_draws=0, waveform=Signal(x=x, fs=1.0))
    assert r.meta["waveform"] == "side input"
    assert np.nanmedian(r.value.features["cycle_floor_frac"]) > 0.4
    with pytest.raises(ValueError, match="samples"):
        _go(spec, x, spans, waveform=Signal(x=x[:-5], fs=1.0))
    with pytest.raises(ValueError, match="Hz"):
        _go(spec, x, spans, waveform=Signal(x=x, fs=10.0))
    with pytest.raises(ValueError, match="must be a Signal"):
        _go(spec, x, spans, waveform=np.zeros(3))


def test_a_missing_or_wrong_input_is_refused_loudly(spec):
    with pytest.raises(ValueError, match="requires a SpanSet"):
        spec.run(np.zeros(10), np.arange(10.0), 1.0, **spec.validate_params({}))
    with pytest.raises(ValueError, match="got Signal"):
        spec.run(np.zeros(10), np.arange(10.0), 1.0, value=Signal(x=np.zeros(10), fs=1.0),
                 **spec.validate_params({}))


def test_the_estimate_answers_none_or_seconds(spec):
    est = spec.estimate(np.zeros(100_000), np.arange(100_000.0), 1.0, **spec.validate_params({}))
    assert est is None or est >= 0.0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
