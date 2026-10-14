"""
test_webui_family_views.py
============================
w2-f families: the two REAL W2-E blocks (`catalogue.shape_families`,
`interrogation.event_families`) run on synthetic two-shape recordings and
serialised exactly as the bridge does (`server.serialize.to_payload`).

Pinned:
* a Shape-families Grouping ships every family's summary (flags, `confident`,
  `null_caveat`, coherence beside its null with the block's own
  `svd_entropy_beyond_noise`, never re-derived), the block-named exemplars, and
  each named exemplar window's own label IS the family it is named for;
* an Event-families SpanSet ships each event's family / reason / noise mark,
  the family summaries, and its exemplar events — each one an event of the
  family it is named for (checked against the `family` column);
* a named exemplar event outside the events, or of another family, is a loud
  error; zero events is a payload that says so.

No FastAPI is imported, but run it with the venv python as the bridge does:
    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_family_views.py
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "tests"), os.path.join(ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

from _event_families_synthetic import equal_length, two_shapes  # noqa: E402
from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from server.serialize import to_payload  # noqa: E402
from Working.types import SpanSet, WindowSet  # noqa: E402

L, GAP = 150, 100


@pytest.fixture(scope="module")
def adapters():
    discover_adapters()
    return get_adapter("catalogue.shape_families"), get_adapter("interrogation.event_families")


def _recording(per=30, seed=0):
    waves, truth = two_shapes(per=per, seed=seed, kind="ar1_095")
    W = equal_length(waves, L)
    x = np.concatenate([np.concatenate([w, np.zeros(GAP)]) for w in W])
    starts = np.array([i * (L + GAP) for i in range(len(W))], dtype=np.int64)
    return x, starts, truth


@pytest.fixture(scope="module")
def shape_run(adapters):
    sf, _ = adapters
    x, starts, _ = _recording()
    ws = WindowSet(starts=starts, length=L, fs=1.0, features=pd.DataFrame({"split": [0] * len(starts)}))
    res = sf.run(x, np.arange(len(x), dtype=float), 1.0, **sf.validate_params({}), value=ws)
    p = to_payload("grouping", res.value, res.meta, {"fs": 1.0, "windowset": ws, "block": "catalogue.shape_families"})
    return res, ws, p


@pytest.fixture(scope="module")
def event_run(adapters):
    _, ef = adapters
    x, starts, _ = _recording()
    starts = list(starts) + [len(x) - 20]          # one event too near the end for a window
    spans = SpanSet(starts=tuple(starts), ends=tuple(s + 20 for s in starts),
                    features=pd.DataFrame({"polarity": [-1] * len(starts)}))
    params = ef.validate_params({"length_s": float(L), "pre_frac": 0.0})
    res = ef.run(x, np.arange(len(x), dtype=float), 1.0, **params, value=spans)
    p = to_payload("spanset", res.value, res.meta, {"fs": 1.0, "span_start": 0, "block": "interrogation.event_families"})
    return res, p


def test_shape_families_ship_every_family_with_its_verdicts_read_off(shape_run):
    res, _, p = shape_run
    fams = p["families"]
    assert len(fams) == len(res.meta["families"]) >= 1
    for shipped, made in zip(fams, res.meta["families"]):
        for k in ("family", "size", "noise_like", "tested", "confident", "null_caveat", "why", "svd_entropy_norm",
                  "svd_entropy_null_p05", "svd_entropy_null_median", "svd_entropy_beyond_noise",
                  "svd_entropy_null_margin", "svd_entropy_squared_norm", "top_share", "library_label"):
            assert k in shipped, k
        assert shipped["svd_entropy_beyond_noise"] == made["svd_entropy_beyond_noise"], "read off, never re-derived"
    assert p["family_summary"]["fraction_placed"] == res.meta["fraction_placed"]
    assert "warnings" in p["family_summary"] and "notes" in p["family_summary"]


def test_each_shape_family_exemplar_is_a_window_of_its_own_family(shape_run):
    res, ws, p = shape_run
    labels = np.asarray(res.value.labels)
    named = res.meta["exemplar_windows"]
    assert {e["cluster"] for e in p["exemplars"]} == {int(k) for k in named}
    for e in p["exemplars"]:
        assert e["by"] == "block" and e["rule"] == res.meta["exemplar_rule"]
        assert int(labels[e["window"]]) == e["cluster"], (
            f"W2-E's medoid for family {e['cluster']} is window {e['window']}, whose own label is "
            f"{int(labels[e['window']])}")
    if (labels == -1).any():
        assert next(c for c in p["clusters"] if c["id"] == -1)["name"] == "in no family"


def test_event_families_ship_each_events_family_and_reason(event_run):
    res, p = event_run
    f = res.value.features
    assert p["family"] == [int(v) for v in f["family"]]
    assert p["family_omit_reason"] == [str(v) for v in f["family_omit_reason"]]
    assert p["family_noise_like"] == [bool(v) for v in f["family_noise_like"]]
    assert p["family_omit_reason"][-1].startswith("no_window:"), "the event too near the end says why"
    assert p["family"][-1] == -1
    assert len(p["families"]) == len(res.meta["families"])
    assert p["family_summary"]["n_events"] == len(f)


def test_each_exemplar_event_is_an_event_of_its_own_family(event_run):
    res, p = event_run
    fam = np.asarray(res.value.features["family"])
    named = res.meta["exemplar_events"]
    assert {e["family"] for e in p["exemplar_events"]} == {int(k) for k in named}
    for e in p["exemplar_events"]:
        assert int(fam[e["event"]]) == e["family"], (
            f"W2-E's exemplar event for family {e['family']} is event {e['event']}, of family {int(fam[e['event']])}")
        assert e["start_s"] == float(res.value.starts[e["event"]]) and e["rule"] == res.meta["exemplar_rule"]


def _spans_with_families(fam):
    n = len(fam)
    return SpanSet(starts=tuple(range(0, 100 * n, 100)), ends=tuple(range(20, 100 * n + 20, 100)),
                   features=pd.DataFrame({"family": fam, "family_omit_reason": [""] * n,
                                          "family_distance": [0.1] * n, "family_noise_like": [False] * n}))


def test_a_named_exemplar_event_of_another_family_or_outside_the_events_is_loud():
    spans = _spans_with_families([1, 1, 2, 2])
    base = {"families": [{"family": 1}, {"family": 2}], "exemplar_rule": "the medoid"}
    with pytest.raises(ValueError, match="not of family"):
        to_payload("spanset", spans, {**base, "exemplar_events": {"1": 0, "2": 1}}, {"fs": 1.0})
    with pytest.raises(ValueError, match="outside"):
        to_payload("spanset", spans, {**base, "exemplar_events": {"1": 0, "2": 9}}, {"fs": 1.0})
    with pytest.raises(ValueError, match=r'\{"<label>": <window index>\}|\{"<family>": <event index>\}'):
        to_payload("spanset", spans, {**base, "exemplar_events": [0, 2]}, {"fs": 1.0, "block": "b"})


def test_zero_events_is_a_payload_that_says_so(adapters):
    _, ef = adapters
    x = np.random.default_rng(0).standard_normal(3000)
    empty = SpanSet(starts=(), ends=(), features=pd.DataFrame({"polarity": pd.Series([], dtype=int)}))
    res = ef.run(x, np.arange(3000, dtype=float), 1.0, **ef.validate_params({}), value=empty)
    p = to_payload("spanset", res.value, res.meta, {"fs": 1.0})
    assert p["families"] == [] and p["exemplar_events"] == []
    assert p["family_summary"]["n_events"] == 0 and "no events" in p["summary"]
