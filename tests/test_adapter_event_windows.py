"""
test_adapter_event_windows.py
===============================
`catalogue.event_windows` (w2-a), SpanSet -> WindowSet: the spec, channel-absolute
starts on a span that does not start at 0, the split as `preprocessing.sliding_windows`
computes it (the same function), the meta a page reads, the empty case, and the
downstream window blocks (`catalogue.cluster`, `catalogue.window_images`,
`catalogue.classifier`'s feature matrix) accepting the output without treating its
bookkeeping columns as features.
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

from _event_windows_synthetic import FS, chain, spans_for  # noqa: E402
from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.types import Grouping, SpanSet, WindowSet  # noqa: E402

NAME = "catalogue.event_windows"


@pytest.fixture(scope="module")
def spec():
    discover_adapters()
    return get_adapter(NAME)


def _run(spec, x, t, spans, **params):
    p = spec.validate_params(params)
    return spec.run(x, t, FS, **p, value=spans)


def test_the_spec(spec):
    assert spec.stage == "catalogue" and spec.category == "cluster" and spec.page_name == "Event windows"
    assert spec.input_kind == "spanset" and spec.output_kind == "windowset"
    names = [p.name for p in spec.params]
    for want in ("anchor", "length_s", "pre_frac", "split_rule", "n_blocks", "holdout_frac", "validation_frac",
                 "allow_random_split", "seed", "max_nan_frac"):
        assert want in names, want
    for p in spec.params:
        if p.type in (int, float):
            assert p.min is not None and p.max is not None, f"{p.name} has no bounds"
    d = spec.validate_params({})
    assert d["anchor"] == "onset" and d["length_s"] == 0.0 and d["pre_frac"] == 0.2
    assert d["split_rule"] == "blocked_by_time" and d["max_nan_frac"] == 0.1
    assert "length_s" in spec.description and "Event shape" in spec.description


def test_starts_are_channel_absolute_on_a_span_that_does_not_start_at_zero(spec):
    x, onsets = chain("ar1", n_events=6)
    offset = 50_000
    t = (np.arange(len(x)) + offset) / FS
    res = _run(spec, x, t, spans_for(onsets), length_s=600.0)
    ws = res.value
    assert isinstance(ws, WindowSet) and ws.length == 600 and ws.fs == FS
    anchor = ws.features["anchor_offset"].to_numpy()
    for s, k, a in zip(ws.starts, ws.features["event_index"], anchor):
        assert s - offset + a == onsets[k]
    assert res.meta["span_start"] == offset


def test_the_split_is_sliding_windows_rule_for_the_same_starts(spec):
    import Adapters.catalogue_event_windows as A
    import Adapters.preprocessing_sliding_windows as SW
    assert A.assign_split is SW.assign_split, "import assign_split, do not copy it"
    x, onsets = chain("ar1", n_events=20)
    offset = 1000
    t = (np.arange(len(x)) + offset) / FS
    for params in ({}, {"n_blocks": 4, "holdout_frac": 0.25, "validation_frac": 0.25},
                   {"split_rule": "random", "allow_random_split": True, "holdout_frac": 0.3, "seed": 7}):
        res = _run(spec, x, t, spans_for(onsets), length_s=600.0, **params)
        ws = res.value
        p = spec.validate_params({"length_s": 600.0, **params})
        want, _ = SW.assign_split(ws.starts - offset, len(x), p["split_rule"], p["n_blocks"], p["holdout_frac"],
                                  p["validation_frac"], p["seed"])
        assert list(ws.features["split"]) == list(want)
    assert sum(res.meta["split_counts"].values()) == ws.n_windows


def test_a_random_split_is_refused_unless_accepted(spec):
    x, onsets = chain("ar1", n_events=4)
    with pytest.raises(ValueError, match="leak"):
        _run(spec, x, None, spans_for(onsets), split_rule="random")


def test_the_meta_a_page_reads(spec):
    x, onsets = chain("ar1", n_events=3, first=100, spacing_s=1000, n=2400)
    res = _run(spec, x, None, spans_for(onsets, pre=10, post=200), length_s=600.0)
    m = res.meta
    assert m["n_events"] == 3 and m["n_windows"] == 1
    assert m["omitted"] == {"past_start": 1, "past_end": 1, "too_much_nan": 0}
    assert m["length_s"] == 600.0 and m["length"] == 600 and m["anchor_used"] == "onset_idx"
    assert m["n_overlapping"] == 0 and m["anchor_fallback"] == 0
    assert {r["name"] for r in m["rules"]} >= {"length", "anchor", "left out"}
    assert m["span_start"] == 0
    assert "summary" in m and "1 of 3" in m["summary"]


def test_an_empty_spanset_gives_an_empty_windowset_and_says_why(spec):
    res = _run(spec, np.zeros(2000), None, SpanSet(starts=(), ends=()))
    ws = res.value
    assert ws.n_windows == 0 and ws.features is not None and len(ws.features) == 0
    assert res.meta["n_events"] == 0 and res.meta["n_windows"] == 0
    assert res.meta["notes"] and "no events" in res.meta["notes"][0]


def test_requires_a_spanset(spec):
    with pytest.raises(ValueError, match="SpanSet"):
        _run(spec, np.zeros(100), None, None)
    with pytest.raises(ValueError, match="SpanSet"):
        _run(spec, np.zeros(100), None, WindowSet(starts=np.array([0]), length=10, fs=1.0))


def test_derive_reads_out_before_the_run(spec):
    x, onsets = chain("ar1", n_events=5)
    rows = spec.derive(x, None, FS, spec.validate_params({}), value=spans_for(onsets))
    labels = [r[0] for r in rows]
    assert "Windows" in labels and "Length" in labels
    rows = spec.derive(x, None, FS, spec.validate_params({}))
    assert rows[0][2] == "warn"


def _event_set(n_events=12):
    # two kinds of event: shallow (10 mV) and deep (30 mV) - the only real difference between windows
    x, onsets = chain("ar1", n_events=n_events, depths=[0.01, 0.03])
    spans = spans_for(onsets, extra={"event_amplitude_mv": [10.0 if i % 2 == 0 else 30.0 for i in range(n_events)]})
    return x, spans


def test_catalogue_cluster_accepts_the_output_and_ignores_its_bookkeeping(spec):
    x, spans = _event_set()
    ws = _run(spec, x, None, spans, length_s=600.0).value
    discover_adapters()
    cl = get_adapter("catalogue.cluster")
    res = cl.run(x, None, FS, **cl.validate_params({"k": 2}), value=ws)
    assert isinstance(res.value, Grouping) and len(res.value.labels) == ws.n_windows
    # event_index (a time order) and the other bookkeeping columns are not features: only the amplitude varies
    assert res.meta["n_features"] == 1
    lab = np.asarray(res.value.labels)
    assert len(set(lab[0::2])) == 1 and len(set(lab[1::2])) == 1 and lab[0] != lab[1]


def test_catalogue_classifier_does_not_train_on_the_bookkeeping():
    import Adapters.catalogue_classifier as C
    x, spans = _event_set()
    discover_adapters()
    spec = get_adapter(NAME)
    ws = _run(spec, x, None, spans, length_s=600.0).value
    labels = np.array([0 if i % 2 == 0 else 1 for i in range(ws.n_windows)])
    pre, *_ = C._feature_matrix(ws, Grouping(labels=labels))
    assert not set(pre.feature_names) & {"event_index", "anchor_offset", "overlaps_next", "split"}


def test_catalogue_window_images_accepts_the_output(spec):
    pytest.importorskip("PIL")
    x, spans = _event_set(4)
    offset = 3000
    t = (np.arange(len(x)) + offset) / FS
    ws = _run(spec, x, t, spans, length_s=600.0).value
    discover_adapters()
    wi = get_adapter("catalogue.window_images")
    res = wi.run(x, t, FS, **wi.validate_params({"img_size": 16}), value=ws)
    assert res.value.values.shape == (ws.n_windows, 16, 16, 3)


def test_the_output_round_trips_through_the_step_cache(spec, tmp_path):
    x, spans = _event_set(4)
    ws = _run(spec, x, None, spans, length_s=600.0).value
    ws.to_path(str(tmp_path))
    back = WindowSet.from_path(str(tmp_path))
    assert back == ws
    assert back.features["overlaps_next"].dtype == bool
