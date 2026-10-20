"""
test_night_analyse_payload.py
=============================
night-analyse (2026-10-20): the Intervals page's per-class scatter plots, for each event, the time until the NEXT
event of the same class (in its group). That number is the bridge's, an append-only field of the intervals
payload (`interval_classes.next_within_gap_s`): the previous-of-class distance (`within_gap_s`) of the next event
of the class, None for the last event of its class. No FastAPI needed; runs under the conda pytest.
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
from Working.types import SpanSet  # noqa: E402

discover_adapters()
FS = 1.0
STARTS = (0, 100, 200, 300, 400, 500, 600)
DEPTH = [-1.0, -9.0, -1.0, -9.0, -5.0, -9.0, -1.0]


def _payload(features, starts=STARTS):
    spec = get_adapter("interrogation.intervals")
    ss = SpanSet(starts=starts, ends=tuple(s + 5 for s in starts), features=features)
    n = max(ss.ends) + 10
    res = spec.run(np.zeros(n), np.arange(n) / FS, FS, value=ss, **spec.validate_params({}))
    return to_payload("spanset", res.value, res.meta, {"fs": FS, "span_start": 1000})["interval_classes"]


def test_the_time_until_the_next_event_of_the_same_class():
    ic = _payload(pd.DataFrame({"event_amplitude_mv": DEPTH}))
    nxt = ic["next_within_gap_s"]
    # small at 0, 200, 600; large at 100, 300, 500; medium alone at 400
    assert nxt[0] == pytest.approx(200) and nxt[2] == pytest.approx(400) and nxt[6] is None, nxt
    assert nxt[1] == pytest.approx(200) and nxt[3] == pytest.approx(200) and nxt[5] is None, nxt
    assert nxt[4] is None, nxt
    # the existing fields are untouched (append-only)
    assert ic["within_gap_s"][2] == pytest.approx(200)


def test_the_next_of_class_stays_inside_its_group():
    feats = pd.DataFrame({"event_amplitude_mv": DEPTH, "group": ["a", "a", "a", "b", "b", "b", "b"]})
    ic = _payload(feats)
    nxt = ic["next_within_gap_s"]
    # group a: small 0, large 100, small 200 -> small 0 -> 200; group b: large 300, medium 400, large 500, small 600
    assert nxt[0] == pytest.approx(200) and nxt[2] is None, nxt      # the small at 600 is in group b
    assert nxt[1] is None, nxt                                       # the large at 300 is in group b
    assert nxt[3] == pytest.approx(200) and nxt[5] is None and nxt[6] is None, nxt
