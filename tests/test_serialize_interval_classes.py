"""
test_serialize_interval_classes.py
====================================
ig-pages: the intervals timeline colours events by similarity and can restrict
the written distances and the interval statistics to one colour class
("purple-to-purple"). The classes and every number are the bridge's
(`serialize.py`, through the intervals adapter's own `measure`), never the
browser's. The class rule (recommendation (c), Q43 pending):

* a `family` column with every event in a family (>= 0) -> the family;
* else the depth (|event_amplitude_mv|, else the detector's span score) in
  thirds of its range: small, medium, large;
* else one class, and the payload says there is nothing to colour by.

Within one class, an event's distance is to the previous event OF THAT CLASS
in its group, and the class's statistics are the core's over those distances.

No FastAPI needed; runs under the conda pytest.
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from server.serialize import to_payload  # noqa: E402
from Working.interrogation.intervals import interval_statistics  # noqa: E402
from Working.types import SpanSet  # noqa: E402

discover_adapters()
FS = 1.0


def _intervals(ss, **params):
    spec = get_adapter("interrogation.intervals")
    n = max(ss.ends) + 10
    return spec.run(np.zeros(n), np.arange(n) / FS, FS, value=ss, **spec.validate_params(params))


# events every 100 s; depths alternate small (1) and large (9), with one medium (5)
STARTS = (0, 100, 200, 300, 400, 500, 600)
DEPTH = [-1.0, -9.0, -1.0, -9.0, -5.0, -9.0, -1.0]


def _depth_set():
    return SpanSet(starts=STARTS, ends=tuple(s + 5 for s in STARTS),
                   features=pd.DataFrame({"event_amplitude_mv": DEPTH}))


def test_depth_thirds_colour_the_events_and_the_legend_names_the_rule():
    res = _intervals(_depth_set())
    p = to_payload("spanset", res.value, res.meta, {"fs": FS, "span_start": 1000})
    ic = p["interval_classes"]
    assert ic["rule"] == "depth" and ic["column"] == "event_amplitude_mv"
    assert "thirds" in ic["rule_words"]
    assert ic["edges"] == pytest.approx([1.0, 1 + 8 / 3, 1 + 16 / 3, 9.0])
    assert ic["event_class"] == ["small", "large", "small", "large", "medium", "large", "small"]
    assert [c["key"] for c in ic["classes"]] == ["small", "medium", "large"]
    assert {c["key"]: c["n"] for c in ic["classes"]} == {"small": 3, "medium": 1, "large": 3}
    assert ic["event_t_s"] == pytest.approx([1000 + s for s in STARTS])


def test_within_a_class_the_distance_is_to_the_previous_event_of_that_class():
    res = _intervals(_depth_set())
    ic = to_payload("spanset", res.value, res.meta, {"fs": FS})["interval_classes"]
    assert ic["gap_s"][0] is None and ic["gap_s"][1:] == pytest.approx([100.0] * 6)
    # small at 0, 200, 600; large at 100, 300, 500; medium alone at 400
    w = ic["within_gap_s"]
    assert w[0] is None and w[2] == pytest.approx(200) and w[6] == pytest.approx(400)
    assert w[1] is None and w[3] == pytest.approx(200) and w[5] == pytest.approx(200)
    assert w[4] is None


def test_the_class_statistics_are_the_cores_over_the_within_class_distances():
    res = _intervals(_depth_set())
    ic = to_payload("spanset", res.value, res.meta, {"fs": FS})["interval_classes"]
    assert ic["stats"]["small"]["all"] == interval_statistics([200.0, 400.0], n_events=3)
    assert ic["stats"]["large"]["all"] == interval_statistics([200.0, 200.0], n_events=3)
    assert ic["stats"]["medium"]["all"]["n_intervals"] == 0


def test_a_family_on_every_event_is_the_class():
    feats = pd.DataFrame({"family": [0, 1, 0, 1, 1, 0, 0], "event_amplitude_mv": DEPTH})
    res = _intervals(SpanSet(starts=STARTS, ends=tuple(s + 5 for s in STARTS), features=feats))
    ic = to_payload("spanset", res.value, res.meta, {"fs": FS})["interval_classes"]
    assert ic["rule"] == "family" and ic["event_class"][:2] == ["family 0", "family 1"]


def test_a_family_missing_on_one_event_falls_back_to_depth():
    feats = pd.DataFrame({"family": [0, 1, 0, -1, 1, 0, 0], "event_amplitude_mv": DEPTH})
    res = _intervals(SpanSet(starts=STARTS, ends=tuple(s + 5 for s in STARTS), features=feats))
    ic = to_payload("spanset", res.value, res.meta, {"fs": FS})["interval_classes"]
    assert ic["rule"] == "depth"


def test_groups_keep_their_own_distances_within_a_class():
    feats = pd.DataFrame({"group": ["a", "b", "a", "b", "a", "b", "a"], "event_amplitude_mv": DEPTH})
    res = _intervals(SpanSet(starts=STARTS, ends=tuple(s + 5 for s in STARTS), features=feats))
    ic = to_payload("spanset", res.value, res.meta, {"fs": FS})["interval_classes"]
    assert ic["event_group"] == ["a", "b", "a", "b", "a", "b", "a"]
    assert set(ic["stats"]["small"]) == {"a"} and set(ic["stats"]["large"]) == {"b"}


def test_no_depth_and_no_family_is_one_class_and_says_so():
    res = _intervals(SpanSet(starts=STARTS, ends=tuple(s + 5 for s in STARTS)))
    ic = to_payload("spanset", res.value, res.meta, {"fs": FS})["interval_classes"]
    assert ic["rule"] == "none" and ic["event_class"] == ["all"] * 7 and "nothing" in ic["rule_words"]


def test_a_spanset_without_interval_stats_has_no_classes():
    p = to_payload("spanset", SpanSet(starts=(10, 40), ends=(20, 50)), {}, {"fs": FS})
    assert "interval_classes" not in p
