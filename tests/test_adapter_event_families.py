"""
test_adapter_event_families.py
================================
`interrogation.event_families` (w2-e), SpanSet -> SpanSet: each event's
waveform cut with W2-A's cutter, grouped with the Library's engine, and its
family written onto the event (`family`, `family_omit_reason`,
`family_distance`, `family_noise_like`) — and, by default, `group = family`
so Intervals after it times each family separately.

Pinned: the spec; the columns and that the spans pass through; `no_window`
for events the cutter left out; `write_group` (default on) writes the family,
prefixing an upstream group the way `interrogation.trains` does (with the
SAME helper) and keeping it as `group_upstream`; off leaves `group` alone;
the new columns are bookkeeping; the per-family flags, SVD entropy and
member exemplars in meta; the no-structure case through Intervals.
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import adjusted_rand_score

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from _event_families_synthetic import equal_length, noise_events, two_shapes  # noqa: E402
from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.Catalogue import event_windows as EW  # noqa: E402
from Working.Catalogue import shape_families as SF  # noqa: E402
from Working.types import SpanSet  # noqa: E402
from Working.types.windowset import BOOKKEEPING_COLUMNS  # noqa: E402

NAME = "interrogation.event_families"
L = 150
GAP = 100
ADDED = ("family", "family_omit_reason", "family_distance", "family_noise_like")


@pytest.fixture(scope="module")
def spec():
    discover_adapters()
    return get_adapter(NAME)


def _recording(per=30, seed=0, kind="ar1_095", group=None, extra_end=True):
    waves, truth = two_shapes(per=per, seed=seed, kind=kind)
    W = equal_length(waves, L)
    x = np.concatenate([np.concatenate([w, np.zeros(GAP)]) for w in W])
    starts = [i * (L + GAP) for i in range(len(W))]
    if extra_end:
        starts.append(len(x) - 20)          # too near the end for a whole window
    cols = {"polarity": [-1] * len(starts), "event_amplitude_mv": np.arange(len(starts), dtype=float)}
    if group is not None:
        cols["group"] = group(len(starts))
    spans = SpanSet(starts=tuple(starts), ends=tuple(s + 20 for s in starts), features=pd.DataFrame(cols))
    return x, spans, truth


def _run(spec, x, spans, **params):
    p = spec.validate_params({"length_s": float(L), "pre_frac": 0.0, **params})
    return spec.run(x, np.arange(len(x), dtype=float), 1.0, **p, value=spans)


def test_the_spec(spec):
    assert spec.stage == "interrogation" and spec.page_name == "Event families"
    assert spec.input_kind == "spanset" and spec.output_kind == "spanset"
    d = spec.validate_params({})
    assert d["write_group"] is True and d["method"] == "hdbscan" and d["anchor"] == "start"
    assert d["length_s"] == 0.0 and d["pre_frac"] == EW.DEFAULT_PRE_FRAC
    names = [p.name for p in spec.params]
    for want in ("anchor", "length_s", "pre_frac", "max_nan_frac", "method", "write_group"):
        assert want in names
    for f in SF.flat_param_specs():
        assert f["flat"] in names
    for p in spec.params:
        if p.type in (int, float):
            assert p.min is not None and p.max is not None, f"{p.name} has no bounds"
    assert spec.estimate is not None
    assert "Intervals" in spec.description and "noise" in spec.description


def test_the_family_columns_are_written_and_the_spans_pass_through(spec):
    x, spans, truth = _recording()
    res = _run(spec, x, spans)
    out = res.value
    assert out.starts == spans.starts and out.ends == spans.ends
    f = out.features
    for c in ADDED:
        assert c in f.columns, c
    assert "event_amplitude_mv" in f.columns and (f["event_amplitude_mv"].to_numpy() == np.arange(len(f))).all()
    fam = f["family"].to_numpy()
    assert adjusted_rand_score(truth, fam[:-1]) >= 0.9
    assert fam[-1] == -1 and f["family_omit_reason"].iloc[-1] == "no_window"
    assert np.isnan(f["family_distance"].iloc[-1])
    placed = fam > 0
    assert (f["family_omit_reason"][placed] == "").all()
    assert np.isfinite(f["family_distance"][placed]).all()
    assert res.meta["omitted"]["no_window"] == 1


def test_it_is_the_core_path_the_manager_feeds_surrogates(spec):
    x, spans, truth = _recording(seed=3, kind="random_walk")
    res = _run(spec, x, spans, seed=5)
    ev = SF.event_families(x, 1.0, spans, anchor="start", length_s=float(L), pre_frac=0.0, method="hdbscan",
                           params={}, seed=5)
    assert (res.value.features["family"].to_numpy() == ev.family).all()
    ew = EW.event_windows(x, 1.0, spans, anchor="start", length_s=float(L), pre_frac=0.0)
    direct = SF.shape_families(EW.cut(x, ew.starts, ew.length), method="hdbscan", seed=5)
    assert (ev.family[ew.kept] == direct.labels).all()
    assert res.meta["fraction_placed"] == pytest.approx(direct.n_placed / len(spans.starts))


def test_write_group_writes_the_family_and_off_leaves_group_alone(spec):
    x, spans, truth = _recording()
    on = _run(spec, x, spans).value.features
    assert not on["family_noise_like"].any()
    assert (on["group"] == on["family"].astype(str)).all()
    assert "group_upstream" not in on.columns
    off = _run(spec, x, spans, write_group=False).value.features
    assert "group" not in off.columns

    xg, sg, _ = _recording(group=lambda n: [f"ch{i % 2}" for i in range(n)])
    on_g = _run(spec, xg, sg).value.features
    assert list(on_g["group_upstream"]) == list(sg.features["group"])
    for g, up, fm in zip(on_g["group"], on_g["group_upstream"], on_g["family"]):
        assert g == f"{up}/{fm}"
    off_g = _run(spec, xg, sg, write_group=False).value.features
    assert list(off_g["group"]) == list(sg.features["group"]) and "group_upstream" not in off_g.columns


def test_the_group_helper_is_shared_with_trains():
    import Adapters.interrogation_trains as trains_adapter
    from Working.interrogation import intervals as IV
    import Adapters.interrogation_event_families as fam_adapter
    assert trains_adapter.write_group_columns is IV.write_group_columns
    assert fam_adapter.write_group_columns is IV.write_group_columns
    up = pd.DataFrame({"group": ["a", "b"]})
    cols = IV.write_group_columns(up, ["1", "-1"])
    assert cols["group"] == ["a/1", "b/-1"] and list(cols["group_upstream"]) == ["a", "b"]
    assert IV.write_group_columns(None, ["1", "2"]) == {"group": ["1", "2"]}


def test_a_noise_like_family_is_marked_in_its_group_key():
    assert SF.group_key(2, noise_like=False) == "2"
    assert SF.group_key(-1, noise_like=False) == "-1"
    k = SF.group_key(2, noise_like=True)
    assert k != "2" and k.startswith("2") and "noise" in k


def test_the_new_columns_are_bookkeeping():
    for c in ADDED + ("group_upstream",):
        assert c in BOOKKEEPING_COLUMNS, c


def test_meta_carries_flags_coherence_and_member_exemplars(spec):
    x, spans, truth = _recording()
    res = _run(spec, x, spans)
    m = res.meta
    fam = res.value.features["family"].to_numpy()
    assert m["method"] == "hdbscan" and m["k"] == 2
    for f in m["families"]:
        assert {"noise_like", "tested", "why", "svd_entropy_norm", "svd_entropy_null_p05"} <= set(f)
    for ex in m["exemplar_events"]:
        assert fam[ex["event"]] == ex["family"]
        assert ex["start"] == spans.starts[ex["event"]]
    assert m["write_group"] is True and "window" in m and m["window"]["length_s"] == float(L)
    names = [r["name"] for r in m["rules"]]
    for want in ("family", "group", "anchor", "svd_entropy"):
        assert want in names, want
    assert "families" in m["summary"] and "SVD entropy" in m["summary"]


def test_noise_events_are_mostly_in_no_family_and_intervals_claims_no_family_rhythm(spec):
    iv = get_adapter("interrogation.intervals")
    for kind, seed in (("ar1", 0), ("random_walk", 1)):
        x, spans = noise_events(kind, n_events=80, seed=seed)
        res = spec.run(x, np.arange(len(x), dtype=float), 1.0,
                       **spec.validate_params({"length_s": 140.0, "pre_frac": 0.0}), value=spans)
        fam = res.value.features["family"].to_numpy()
        assert (fam == -1).mean() > 0.5, (kind, seed, res.meta["summary"])
        stats = iv.run(x, np.arange(len(x), dtype=float), 1.0, **iv.validate_params({}),
                       value=res.value).meta["interval_stats"]
        confident = [k for k in stats if k != "-1" and "noise" not in k]
        # any family a timing is reported for must have passed its null; here none should
        assert confident == [], (kind, seed, list(stats))


def test_an_empty_spanset_passes_through_with_the_reason(spec):
    x = np.zeros(2000)
    res = _run(spec, x, SpanSet(starts=(), ends=()))
    assert len(res.value.starts) == 0 and res.meta["k"] == 0
    assert "no event" in res.meta["summary"].lower()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
