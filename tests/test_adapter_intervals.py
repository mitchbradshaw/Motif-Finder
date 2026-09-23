"""
test_adapter_intervals.py
===========================
`interrogation.intervals` (fixup-d, seam 3) — SpanSet -> SpanSet: the
inter-event interval before and after every event, per group, and the train's
statistics in `meta`. The interval arithmetic and the regularity gate are the
ONE consolidated implementation in `Working.interrogation.intervals`; the three
callers that each had their own (`store11`, `clusterk1`, the Interrogation
aggregate route) now import it, and `sequences11`'s regularity gate (CV with
ddof=1, R² of interval against index, drift of the last third over the first)
lives there too.

Runnable standalone:  python tests/test_adapter_intervals.py
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
NAME = "interrogation.intervals"
FS = 10.0


def _run(ss, n=400, **params):
    spec = get_adapter(NAME)
    return spec.run(np.zeros(n), np.arange(n) / FS, FS, value=ss, **spec.validate_params(params))


def test_registered_as_a_spanset_to_spanset_block():
    spec = get_adapter(NAME)
    assert spec.stage == "interrogation"
    assert spec.input_kind == "spanset" and spec.output_kind == "spanset"
    assert spec.category == "control"


def test_defaults_and_bounds():
    spec = get_adapter(NAME)
    p = spec.validate_params({})
    assert p["anchor"] == "onset"
    with pytest.raises(ValueError):
        spec.validate_params({"anchor": "middle"})


def test_intervals_from_span_starts_when_no_onset_is_known():
    r = _run(SpanSet(starts=(0, 100, 250, 300), ends=(50, 150, 280, 350)))
    f = r.value.features
    assert np.isnan(f["interval_before_s"].iloc[0])
    assert list(f["interval_before_s"].iloc[1:]) == [10.0, 15.0, 5.0]
    assert list(f["interval_after_s"].iloc[:3]) == [10.0, 15.0, 5.0]
    assert np.isnan(f["interval_after_s"].iloc[3])
    assert r.value.starts == (0, 100, 250, 300)


def test_the_statistics_are_the_sequences11_regularity_gate():
    from Working.interrogation.intervals import drift_ratio, regularity
    r = _run(SpanSet(starts=(0, 100, 250, 300), ends=(50, 150, 280, 350)))
    st = r.meta["interval_stats"]["all"]
    iv = np.array([10.0, 15.0, 5.0])
    assert st["n_events"] == 4 and st["n_intervals"] == 3
    assert st["median_s"] == pytest.approx(10.0)
    assert st["cv"] == pytest.approx(iv.std(ddof=1) / iv.mean())
    cv, r2 = regularity(iv)
    assert st["cv"] == pytest.approx(cv) and st["r2_trend"] == pytest.approx(r2)
    assert st["drift_ratio"] == pytest.approx(drift_ratio(iv)) == pytest.approx(0.5)


def test_an_upstream_onset_column_is_the_anchor():
    feats = pd.DataFrame({"onset_idx": [20, 130, 260], "event_amplitude_mv": [1.0, 2.0, 3.0]})
    r = _run(SpanSet(starts=(0, 100, 250), ends=(50, 150, 280), features=feats))
    f = r.value.features
    assert list(f["interval_before_s"].iloc[1:]) == [11.0, 13.0]
    assert "event_amplitude_mv" in f.columns       # upstream measures are kept
    assert r.meta["anchor_used"] == "onset_idx"


def test_intervals_are_never_pooled_across_groups():
    feats = pd.DataFrame({"group": ["a", "b", "a", "b"]})
    r = _run(SpanSet(starts=(0, 50, 100, 300), ends=(10, 60, 110, 310), features=feats))
    f = r.value.features
    assert np.isnan(f["interval_before_s"].iloc[0]) and np.isnan(f["interval_before_s"].iloc[1])
    assert f["interval_before_s"].iloc[2] == pytest.approx(10.0)    # a: 0 -> 100
    assert f["interval_before_s"].iloc[3] == pytest.approx(25.0)    # b: 50 -> 300
    assert set(r.meta["interval_stats"]) == {"a", "b"}


def test_unsorted_spans_are_ordered_before_differencing():
    r = _run(SpanSet(starts=(250, 0, 100), ends=(280, 50, 150)))
    f = r.value.features
    assert f["interval_before_s"].iloc[0] == pytest.approx(15.0)
    assert np.isnan(f["interval_before_s"].iloc[1])
    assert f["interval_before_s"].iloc[2] == pytest.approx(10.0)


def test_a_single_event_has_no_interval_and_no_statistics_but_no_error():
    r = _run(SpanSet(starts=(5,), ends=(9,)))
    assert np.isnan(r.value.features["interval_before_s"].iloc[0])
    assert r.meta["interval_stats"]["all"]["n_intervals"] == 0
    assert r.meta["interval_stats"]["all"]["cv"] is None


def test_the_rule_is_printed():
    r = _run(SpanSet(starts=(0, 100), ends=(50, 150)))
    assert any(rule["name"] == "interval" for rule in r.meta["rules"])
    assert any("per group" in rule["rule"] for rule in r.meta["rules"])


def test_a_30s_synthetic_train():
    starts = tuple(range(0, 300, 30))
    r = _run(SpanSet(starts=starts, ends=tuple(s + 10 for s in starts)), n=300)
    st = r.meta["interval_stats"]["all"]
    assert st["n_intervals"] == 9 and st["median_s"] == pytest.approx(3.0) and st["cv"] == pytest.approx(0.0)


def test_refuses_a_missing_input():
    spec = get_adapter(NAME)
    with pytest.raises(ValueError, match="SpanSet"):
        spec.run(np.zeros(10), np.arange(10) / FS, FS, **spec.validate_params({}))


# ── the three implementations, consolidated onto one ─────────────────────────

def test_one_interval_implementation_serves_every_caller():
    from Working.interrogation import intervals as core
    from Pipelines.drop_motifs import clusterk1, sequences11, store11
    assert store11.inter_event_intervals is core.inter_event_intervals
    assert clusterk1.inter_event_intervals is core.inter_event_intervals
    assert sequences11._regularity is core.regularity
    assert sequences11._drift is core.drift_ratio
    route = open(os.path.join(PROJECT_ROOT, "webui", "server", "interrogation_routes.py"), encoding="utf-8").read()
    assert "inter_event_intervals" in route and "np.diff(onsets" not in route


def test_inter_event_intervals_sorts_and_differences():
    from Working.interrogation.intervals import inter_event_intervals
    assert list(inter_event_intervals([5.0, 1.0, 3.0])) == [2.0, 2.0]
    assert inter_event_intervals([1.0]).size == 0


def test_the_callers_still_produce_what_they_did():
    from Pipelines.drop_motifs import clusterk1, store11
    rows = [{"catalogue_id": 1, "channel": "0", "onset_s": s, "fall_duration_s": 2.0, "species": "x"}
            for s in (0.0, 10.0, 25.0, 30.0)]
    st = store11.interval_stats(rows)[(1, "0")]
    assert st["median_iei_s"] == pytest.approx(10.0)
    crow = [{"channel": 0, "onset_idx": i, "fs": 1.0, "drop_depth_mv": 1.0, "fall_duration_s": 1.0}
            for i in (0, 10, 25, 30)]
    isi = clusterk1.isi_by_channel(crow)[0]["isi_s"]
    assert list(isi) == [10.0, 15.0, 5.0]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
