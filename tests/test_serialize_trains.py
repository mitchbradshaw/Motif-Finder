"""
test_serialize_trains.py
==========================
ig-pages: a trains block's page draws three figures - the log-interval density
with its cut, the train-size histogram and the trains on the timeline. The
numbers are the adapter's (`interrogation.trains`); `serialize.py` passes them
through under one additive key:

    trains: {n_trains, sizes: [..], log_isi: {edges, density, cut} | None, lz}

`edges` are the log10-seconds points the adapter's density was evaluated on,
`cut` is the cut in seconds (None when the density had no valley). A payload
without the trains meta (any other block, or a cached old run) carries no
`trains` key and still serialises.

No FastAPI needed; runs under the conda pytest.
"""

import os
import sys

import numpy as np
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


def _bursts(n_trains=8, per=6, inside=30, between=3000, seed=0):
    rng = np.random.default_rng(seed)
    starts = sorted(int(k * between + i * inside + rng.integers(0, 8)) for k in range(n_trains) for i in range(per))
    return SpanSet(starts=tuple(starts), ends=tuple(s + 5 for s in starts))


def _run(ss, **params):
    spec = get_adapter("interrogation.trains")
    n = max(ss.ends) + 10
    return spec.run(np.zeros(n), np.arange(n) / FS, FS, value=ss, **spec.validate_params(params))


def test_a_trains_payload_carries_the_adapters_numbers():
    res = _run(_bursts())
    m = res.meta
    assert m["n_trains"] > 0 and m["cut_s"] is not None   # the fixture has trains to find
    p = to_payload("spanset", res.value, m, {"fs": FS})
    tr = p["trains"]
    assert tr["n_trains"] == m["n_trains"]
    assert sorted(tr["sizes"]) == sorted(int(k) for k, c in m["train_size_distribution"].items() for _ in range(c))
    assert len(tr["sizes"]) == m["n_trains"]
    assert tr["lz"] == pytest.approx(m["lz_complexity"])
    li = tr["log_isi"]
    assert li["edges"] == m["density"]["log10_gap_s"]
    assert li["density"] == m["density"]["density"]
    assert li["cut"] == pytest.approx(m["cut_s"])


def test_the_sizes_are_in_time_order_as_the_adapter_found_them():
    res = _run(_bursts())
    assert res.meta["train_sizes"] == [6] * 8
    p = to_payload("spanset", res.value, res.meta, {"fs": FS})
    assert p["trains"]["sizes"] == res.meta["train_sizes"]


def test_an_old_trains_payload_without_the_sizes_list_still_serialises():
    res = _run(_bursts())
    old = {k: v for k, v in res.meta.items() if k != "train_sizes"}
    p = to_payload("spanset", res.value, old, {"fs": FS})
    assert sorted(p["trains"]["sizes"]) == [6] * 8


def test_per_group_trains_have_no_single_density_and_say_so():
    import pandas as pd
    ss = _bursts()
    n = len(ss.starts)
    grouped = SpanSet(starts=ss.starts, ends=ss.ends,
                      features=pd.DataFrame({"group": ["a" if i % 2 else "b" for i in range(n)]}))
    res = _run(grouped)
    p = to_payload("spanset", res.value, res.meta, {"fs": FS})
    assert p["trains"]["log_isi"] is None
    assert "group" in p["trains"]["log_isi_note"]


def test_a_spanset_without_trains_meta_has_no_trains_key():
    p = to_payload("spanset", SpanSet(starts=(10, 40), ends=(20, 50)), {"rules": []}, {"fs": FS})
    assert "trains" not in p
    q = to_payload("spanset", SpanSet(starts=(10, 40), ends=(20, 50)), {}, {"fs": FS})
    assert "trains" not in q and q["n"] == 2
