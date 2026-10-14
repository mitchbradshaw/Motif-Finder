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


def test_auto_length_coverage_is_reported_and_warned_when_recovery_falls_outside(spec):
    # fix round 1: windows whose recovery point lies outside them are counted; more than a quarter -> a warning
    x, onsets = chain("ar1", n_events=8)
    rec = [float(o + 100) for o in onsets]
    for i in (0, 1, 2):
        rec[i] = float(onsets[i] + 2000)  # 3 of 8 > a quarter
    spans = spans_for(onsets, extra={"recovery_idx": rec})
    res = _run(spec, x, None, spans, length_s=600.0)
    assert res.meta["n_recovery_outside_window"] == 3
    assert res.meta["n_duration_unmeasured"] == 0
    assert res.meta["warnings"] and "length_s" in res.meta["warnings"][0]
    rec = [float(o + 100) for o in onsets]
    rec[0] = float(onsets[0] + 2000)  # 1 of 8: counted, no warning
    res = _run(spec, x, None, spans_for(onsets, extra={"recovery_idx": rec}), length_s=600.0)
    assert res.meta["n_recovery_outside_window"] == 1 and res.meta["warnings"] == []
    # no recovery_idx column: not measured (None), never a reassuring 0
    res = _run(spec, x, None, spans_for(onsets), length_s=600.0)
    assert res.meta["n_recovery_outside_window"] is None


def test_the_length_help_text_says_what_auto_covers(spec):
    help_ = next(p for p in spec.params if p.name == "length_s").description
    assert "half" in help_ and "recovery" in help_ and "placeholder" in help_


def test_a_cut_omitted_rows_list_says_so(spec):
    # fix round 1 (critic finding 5): meta lists at most 4096 left-out rows per reason, and says when it cut
    n = 5000
    spans = SpanSet(starts=tuple([9990] * n), ends=tuple([9995] * n))
    m = _run(spec, np.zeros(10_000), None, spans, anchor="start", length_s=60.0).meta
    assert m["omitted"]["past_end"] == n
    assert len(m["omitted_rows"]["past_end"]) == 4096
    assert m["omitted_rows_cut"] == {"past_end": n - 4096}
    assert any("4096" in s for s in m["notes"])
    m = _run(spec, np.zeros(10_000), None, SpanSet(starts=(9990,), ends=(9995,)), anchor="start", length_s=60.0).meta
    assert m["omitted_rows_cut"] == {}


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


# ---- fix round 1 (critic findings 3 and 4): the bookkeeping list is the WindowSet contract's

BOOK = {"split", "event_index", "anchor_offset", "overlaps_next", "train_id", "word_id", "span_score",
        # w2-e: interrogation.event_families' answer columns and the group a feature block replaced
        "family", "family_omit_reason", "family_distance", "family_noise_like", "group_upstream",
        # w3-a: catalogue.multiscale_entropy's quality counts, units and drift measures (not complexity)
        "mse_n_scales", "mse_n_collapsed", "mse_r", "mse_drift_share", "mse_inflation"}


def test_the_bookkeeping_columns_live_beside_windowset():
    from Working.types.windowset import BOOKKEEPING_COLUMNS
    from Working.Catalogue import event_windows as EW
    assert set(BOOKKEEPING_COLUMNS) == BOOK
    assert EW.NOT_FEATURES is BOOKKEEPING_COLUMNS  # an alias, so W2-E can import either
    for mod in ("catalogue_cluster", "catalogue_classifier"):
        src = open(os.path.join(ROOT, "Adapters", f"{mod}.py"), encoding="utf-8").read()
        assert "Working.types.windowset import BOOKKEEPING_COLUMNS" in src, mod
        assert "event_windows import NOT_FEATURES" not in src, mod


def _book_window_set(n=24, seed=0):
    rng = np.random.default_rng(seed)
    f = pd.DataFrame({
        "event_amplitude_mv": np.where(np.arange(n) % 2 == 0, 10.0, 30.0) + rng.normal(0, 0.1, n),
        "interval_before_s": rng.uniform(600, 3000, n),  # a measurement: stays a feature
        "span_score": rng.uniform(4, 9, n),              # the detector's own decision
        "train_id": np.arange(n) // 4, "word_id": np.arange(n) // 2,  # time-ordered identifiers
        "event_index": np.arange(n), "split": np.zeros(n, dtype=int),
    })
    return WindowSet(starts=np.arange(n) * 1000, length=600, fs=FS, features=f)


def test_cluster_and_classifier_skip_the_bookkeeping_and_keep_measurements():
    discover_adapters()
    ws = _book_window_set()
    cl = get_adapter("catalogue.cluster")
    meta = cl.run(None, None, FS, **cl.validate_params({"k": 2}), value=ws).meta
    assert sorted(meta["feature_names"]) == ["event_amplitude_mv", "interval_before_s"]
    import Adapters.catalogue_classifier as C
    labels = np.arange(ws.n_windows) % 2
    pre, *_ = C._feature_matrix(ws, Grouping(labels=labels))
    assert sorted(pre.feature_names) == ["event_amplitude_mv", "interval_before_s"]


def test_span_score_and_upstream_identifiers_still_ride_on_the_windows(spec):
    x, onsets = chain("ar1", n_events=4)
    base = spans_for(onsets, extra={"train_id": [0, 0, 1, 1], "word_id": [0, 1, 2, 3]})
    spans = SpanSet(starts=base.starts, ends=base.ends, scores=(5.0, 6.0, 7.0, 8.0), features=base.features)
    f = _run(spec, x, None, spans, length_s=600.0).value.features
    assert list(f["span_score"]) == [5.0, 6.0, 7.0, 8.0]
    assert list(f["train_id"]) == [0, 0, 1, 1] and list(f["word_id"]) == [0, 1, 2, 3]


def test_a_table_of_bookkeeping_only_is_refused_naming_the_set():
    discover_adapters()
    n = 6
    f = pd.DataFrame({"split": np.zeros(n, int), "event_index": np.arange(n), "span_score": np.ones(n)})
    ws = WindowSet(starts=np.arange(n) * 100, length=50, fs=FS, features=f)
    cl = get_adapter("catalogue.cluster")
    with pytest.raises(ValueError) as e:
        cl.run(None, None, FS, **cl.validate_params({"k": 2}), value=ws)
    msg = str(e.value)
    assert "a `split` column alone" not in msg
    assert "event_index" in msg and "span_score" in msg and "train_id" in msg
