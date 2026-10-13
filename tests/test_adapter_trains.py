"""
test_adapter_trains.py
========================
w1-e: `interrogation.trains` - SpanSet -> SpanSet, a feature block. The spans
pass through unchanged with every column they came with; it adds `train_id`
(-1 = in no train), `train_size`, `position_in_train` and `gap_before_s`. It
never overwrites an upstream `group` unless asked (`write_group`), and then
`interrogation.intervals` downstream measures timing within trains.

Runnable standalone:  python tests/test_adapter_trains.py
"""

import json
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
NAME = "interrogation.trains"
FS = 1.0


def _run(ss, n=None, name=NAME, **params):
    spec = get_adapter(name)
    n = n or (max(ss.ends) + 10 if ss.starts else 100)
    return spec.run(np.zeros(n), np.arange(n) / FS, FS, value=ss, **spec.validate_params(params))


def _trains_spanset(features=None, n_trains=4, per=4, inside=30, between=3000, width=5):
    starts = [k * between + i * inside for k in range(n_trains) for i in range(per)]
    return SpanSet(starts=tuple(starts), ends=tuple(s + width for s in starts), features=features)


# ── the spec ────────────────────────────────────────────────────────────────

def test_registered_as_a_spanset_to_spanset_feature_block():
    spec = get_adapter(NAME)
    assert spec.stage == "interrogation"
    assert spec.input_kind == "spanset" and spec.output_kind == "spanset"
    assert spec.category == get_adapter("interrogation.intervals").category == "control"
    assert spec.page_name == "Trains"
    assert spec.estimate is not None
    assert "logISI" in spec.description or "logisi" in spec.description.lower()


def test_defaults_and_bounds():
    spec = get_adapter(NAME)
    p = spec.validate_params({})
    assert p["rule"] == "logisi"
    assert p["min_events"] == 3
    assert p["max_core_gap_s"] == 0.0
    assert p["theta_mult"] == 1.0
    assert p["write_group"] is False
    assert p["anchor"] == "onset"
    for bad in ({"rule": "rank_surprise"}, {"min_events": 1}, {"theta_mult": 0.0}, {"max_core_gap_s": -1.0},
                {"anchor": "middle"}):
        with pytest.raises(ValueError):
            spec.validate_params(bad)


def test_a_missing_spanset_is_refused_in_words():
    spec = get_adapter(NAME)
    with pytest.raises(ValueError, match="SpanSet"):
        spec.run(np.zeros(10), np.arange(10.0), FS, **spec.validate_params({}))


# ── the columns ─────────────────────────────────────────────────────────────

def test_finds_the_trains_and_adds_the_four_columns():
    ss = _trains_spanset()
    r = _run(ss)
    f = r.value.features
    assert r.value.starts == ss.starts and r.value.ends == ss.ends
    assert list(f["train_id"]) == [k for k in range(4) for _ in range(4)]
    assert list(f["train_size"]) == [4] * 16
    assert list(f["position_in_train"]) == [0, 1, 2, 3] * 4
    assert np.isnan(f["gap_before_s"].iloc[0])
    assert list(f["gap_before_s"].iloc[1:4]) == [30.0, 30.0, 30.0]
    assert f["gap_before_s"].iloc[4] == pytest.approx(3000 - 90)
    assert r.meta["n_trains"] == 4 and r.meta["fraction_in_trains"] == 1.0
    assert 30.0 < r.meta["cut_s"] < 2910.0


def test_upstream_columns_including_group_survive():
    ss = _trains_spanset()
    up = pd.DataFrame({"event_amplitude_mv": np.arange(16.0), "group": ["chA"] * 16})
    r = _run(SpanSet(starts=ss.starts, ends=ss.ends, labels=tuple(f"e{i}" for i in range(16)), features=up))
    f = r.value.features
    assert list(f["event_amplitude_mv"]) == list(range(16))
    assert list(f["group"]) == ["chA"] * 16, "an upstream group is never overwritten by default"
    assert r.value.labels == tuple(f"e{i}" for i in range(16))


def test_event_times_come_from_an_upstream_onset_when_there_is_one():
    ss = _trains_spanset()
    onsets = np.array(ss.starts, dtype=float) + np.tile([0, 2, 4, 6], 4)   # gaps inside become 32 s
    r = _run(SpanSet(starts=ss.starts, ends=ss.ends, features=pd.DataFrame({"onset_idx": onsets})))
    assert list(r.value.features["gap_before_s"].iloc[1:4]) == [32.0, 32.0, 32.0]
    assert r.meta["anchor_used"] == "onset_idx"
    r2 = _run(SpanSet(starts=ss.starts, ends=ss.ends, features=pd.DataFrame({"onset_idx": onsets})), anchor="start")
    assert r2.meta["anchor_used"] == "span_start"


def test_trains_never_cross_an_upstream_group():
    # two channels interleaved in one SpanSet: each alone is 3 trains of 4; pooled, the gaps would mix
    a = [k * 3000 + i * 30 for k in range(3) for i in range(4)]
    b = [s + 7 for s in a]
    starts = a + b
    up = pd.DataFrame({"group": ["A"] * 12 + ["B"] * 12})
    ss = SpanSet(starts=tuple(starts), ends=tuple(s + 3 for s in starts), features=up)
    r = _run(ss, rule="adamatzky")
    f = r.value.features
    for g in ("A", "B"):
        ids = f.loc[f["group"] == g, "train_id"]
        assert ids.nunique() == 3
    assert set(f.loc[f["group"] == "A", "train_id"]).isdisjoint(set(f.loc[f["group"] == "B", "train_id"]))
    assert list(f.loc[f["group"] == "A", "gap_before_s"].iloc[1:4]) == [30.0, 30.0, 30.0]
    assert set(r.meta["groups"]) == {"A", "B"}


# ── write_group and the intervals block downstream ──────────────────────────

def test_write_group_lets_intervals_measure_within_trains():
    r = _run(_trains_spanset(), write_group=True)
    f = r.value.features
    assert list(f["group"]) == [str(k) for k in range(4) for _ in range(4)]
    iv = _run(r.value, name="interrogation.intervals")
    stats = iv.meta["interval_stats"]
    assert set(stats) == {"0", "1", "2", "3"}
    for k in stats:
        assert stats[k]["n_events"] == 4 and stats[k]["median_s"] == pytest.approx(30.0)
        assert stats[k]["max_s"] == pytest.approx(30.0), "an interval crossed a train boundary"


def test_write_group_with_an_upstream_group_keeps_it():
    ss = _trains_spanset(features=pd.DataFrame({"group": ["chA"] * 16}))
    f = _run(ss, write_group=True).value.features
    assert list(f["group_upstream"]) == ["chA"] * 16
    assert list(f["group"]) == [f"chA/{k}" for k in range(4) for _ in range(4)]


# ── honesty ─────────────────────────────────────────────────────────────────

def test_fewer_than_ten_gaps_refuses_in_words_and_passes_the_spans_through():
    ss = _trains_spanset(n_trains=2, per=4)   # 8 events, 7 gaps
    r = _run(ss)
    assert r.value.starts == ss.starts
    assert list(r.value.features["train_id"]) == [-1] * 8
    assert r.meta["refused"] and "7 gaps" in r.meta["refused"]
    assert r.meta["n_trains"] == 0


def test_poisson_spans_report_no_trains_in_words():
    rng = np.random.default_rng(7)
    starts = np.cumsum(rng.exponential(100.0, 300)).astype(int) + np.arange(300)  # strictly increasing
    r = _run(SpanSet(starts=tuple(int(s) for s in starts), ends=tuple(int(s) + 1 for s in starts)))
    assert r.meta["n_trains"] == 0
    assert r.meta["no_trains_reason"]


def test_meta_is_json_and_carries_what_a_page_draws():
    r = _run(_trains_spanset(n_trains=5))
    json.dumps(r.meta)
    m = r.meta
    for key in ("rule", "cut_s", "void", "density", "n_trains", "fraction_in_trains", "train_size_distribution",
                "lz_complexity", "rules", "refused", "warnings", "n_events", "n_gaps"):
        assert key in m, key
    assert len(m["density"]["log10_gap_s"]) <= 512
    assert m["train_size_distribution"] == {"4": 5}
    assert all(set(x) == {"name", "rule"} for x in m["rules"])


def test_the_three_rules_run_through_the_adapter():
    ss = _trains_spanset()
    for rule in ("logisi", "maxinterval", "adamatzky"):
        r = _run(ss, rule=rule)
        assert r.meta["rule"] == rule
        assert r.meta["n_trains"] == 4, rule
    r = _run(ss, rule="adamatzky")
    assert "word_id" in r.value.features.columns


def test_an_empty_spanset_passes_through():
    r = _run(SpanSet(starts=(), ends=()), n=50)
    assert r.value.starts == ()
    assert r.meta["n_trains"] == 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
