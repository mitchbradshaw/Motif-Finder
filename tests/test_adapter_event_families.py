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
    assert d["length_s"] == 600.0 and d["pre_frac"] == EW.DEFAULT_PRE_FRAC   # F1: a placeholder, not auto
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
    assert fam[-1] == -1 and f["family_omit_reason"].iloc[-1] == "no_window:past_end"
    assert np.isnan(f["family_distance"].iloc[-1])
    placed = fam > 0
    assert (f["family_omit_reason"][placed] == "").all()
    assert np.isfinite(f["family_distance"][placed]).all()
    assert res.meta["omitted"]["no_window:past_end"] == 1
    assert "past_end" in res.meta["summary"]


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
    ex_map = m["exemplar_events"]          # {"<family>": <event index>}, the serializer's format
    assert isinstance(ex_map, dict) and set(ex_map) == {"1", "2"}
    for label, ev in ex_map.items():
        assert isinstance(label, str) and isinstance(ev, int)
        assert fam[ev] == int(label)
    assert isinstance(m["exemplar_rule"], str) and "medoid" in m["exemplar_rule"]
    for ex in m["exemplars"]:
        assert ex_map[str(ex["family"])] == ex["event"]
        assert ex["start"] == spans.starts[ex["event"]]
    assert m["write_group"] is True and "window" in m and m["window"]["length_s"] == float(L)
    names = [r["name"] for r in m["rules"]]
    for want in ("family", "group", "anchor", "svd_entropy"):
        assert want in names, want
    assert "families" in m["summary"] and "SVD entropy" in m["summary"]


def _unmarked_keys(spec, x, spans, method):
    """Intervals' keys for this block's output at its DEFAULTS, minus -1 and the marked ones."""
    iv = get_adapter("interrogation.intervals")
    t = np.arange(len(x), dtype=float)
    res = spec.run(x, t, 1.0, **spec.validate_params({"method": method}), value=spans)
    stats = iv.run(x, t, 1.0, **iv.validate_params({}), value=res.value).meta["interval_stats"]
    return [k for k in stats if k != "-1" and SF.NOISE_LIKE_SUFFIX not in k and SF.UNTESTED_SUFFIX not in k], res


def _methods(spec):
    return next(p for p in spec.params if p.name == "method").choices


# F5: no structure, at the block's defaults, for every method it offers: no Intervals key without a mark
@pytest.mark.parametrize("method", ["hdbscan", "ward"])
@pytest.mark.parametrize("kind", ["ar1_095", "ar1", "ar1_099", "random_walk"])
def test_noise_events_at_defaults_n200_leave_no_unmarked_intervals_key(spec, method, kind):
    assert method in _methods(spec)
    x, spans = noise_events(kind, n_events=200, seed=2)
    keys, res = _unmarked_keys(spec, x, spans, method)
    assert keys == [], (method, kind, keys, res.meta["summary"])


@pytest.mark.parametrize("method", ["hdbscan", "ward"])
def test_noise_events_at_defaults_n1000_random_walk_leave_no_unmarked_intervals_key(spec, method):
    x, spans = noise_events("random_walk", n_events=1000, seed=3)
    keys, res = _unmarked_keys(spec, x, spans, method)
    assert keys == [], (method, keys, res.meta["summary"])


# F2: k-Shape is left out of this block's methods (its plain-phase null missed random-walk crowds), Ward is marked
def test_kshape_is_not_offered_here_and_the_core_refuses_it_with_the_reason(spec):
    assert _methods(spec) == [m for m in SF.shape_methods() if m != "kshape"]
    assert "kshape" in SF.EVENT_FAMILIES_EXCLUDED
    x, spans, truth = _recording()
    with pytest.raises(ValueError, match="k-Shape|kshape"):
        SF.event_families(x, 1.0, spans, anchor="start", length_s=float(L), method="kshape")
    assert "k-Shape" in spec.description


def test_ward_families_are_keyed_untested_and_the_rule_says_so(spec):
    x, spans, truth = _recording()
    res = _run(spec, x, spans, method="ward", min_group=5)
    f = res.value.features
    placed = f["family"] > 0
    assert placed.any()
    assert all(g.endswith(SF.UNTESTED_SUFFIX) for g in f["group"][placed]), set(f["group"])
    rule = next(r["rule"] for r in res.meta["rules"] if r["name"] == "group")
    assert "untested" in rule
    assert SF.group_key(3, noise_like=False, tested=False) == "3" + SF.UNTESTED_SUFFIX
    assert SF.group_key(3, noise_like=True, tested=True) == "3" + SF.NOISE_LIKE_SUFFIX
    assert SF.group_key(3, noise_like=False, tested=True) == "3"


# F1: when a caller asks for the auto length, W2-A's coverage warnings reach meta and the summary
def _auto_spans(n_events, spacing, duration_s, recovery_after=None):
    starts = [1000 + i * spacing for i in range(n_events)]
    dur = list(duration_s) if np.ndim(duration_s) else [duration_s] * n_events
    cols = {"polarity": [-1] * n_events, "onset_idx": [float(s) for s in starts], "duration_s": dur}
    if recovery_after is not None:
        cols["recovery_idx"] = [float(s + recovery_after) for s in starts]
    return SpanSet(starts=tuple(starts), ends=tuple(s + 30 for s in starts), features=pd.DataFrame(cols))


def _auto_run(spec, spans, n, **params):
    x = np.random.default_rng(0).standard_normal(n)
    p = spec.validate_params({"length_s": 0.0, **params})
    return spec.run(x, np.arange(n, dtype=float), 1.0, **p, value=spans).meta


def test_auto_length_clamped_to_the_ceiling_and_overlapping_is_warned(spec):
    # most durations unmeasured (longer than measurable) -> the median is too, and the length the 7200 s ceiling
    spans = _auto_spans(30, 3000, [float("nan")] * 20 + [100.0] * 10)
    m = _auto_run(spec, spans, 1000 + 30 * 3000 + 9000)
    w = " ".join(m["warnings"])
    assert m["window"]["length_s"] == 7200.0
    assert "ceiling" in w and "overlap" in w
    assert "ceiling" in m["summary"] and "overlap" in m["summary"]


def test_auto_length_clamped_to_the_floor_is_warned(spec):
    m = _auto_run(spec, _auto_spans(30, 600, 5.0), 1000 + 30 * 600 + 2000)
    assert m["window"]["length_s"] == 60.0
    assert any("floor" in w for w in m["warnings"]) and "floor" in m["summary"]


def test_auto_length_that_cuts_off_the_recovery_is_warned(spec):
    m = _auto_run(spec, _auto_spans(30, 2000, 100.0, recovery_after=900), 1000 + 30 * 2000 + 2000)
    assert m["window"]["length_s"] == 200.0
    assert any("recover" in w for w in m["warnings"]) and "recover" in m["summary"]


def test_a_set_length_carries_no_auto_warning(spec):
    spans = _auto_spans(30, 3000, [float("nan")] * 20 + [100.0] * 10)
    n = 1000 + 30 * 3000 + 9000
    x = np.random.default_rng(0).standard_normal(n)
    m = spec.run(x, np.arange(n, dtype=float), 1.0, **spec.validate_params({}), value=spans).meta
    assert m["window"]["length_s"] == 600.0
    assert not any("ceiling" in w or "floor" in w for w in m["warnings"])


# F3: the coherence verdict is read off svd_entropy (its margin), never re-derived
def test_the_coherence_verdict_and_rule_are_svd_entropys(spec):
    from Working.library import coherence
    x, spans, truth = _recording()
    m = _run(spec, x, spans).meta
    for f in m["families"]:
        assert "coherent_beyond_noise" not in f
        want = f["svd_entropy_norm"] < coherence.NULL_MARGIN * f["svd_entropy_null_p05"]
        assert f["svd_entropy_beyond_noise"] is bool(want)
    rule = next(r["rule"] for r in m["rules"] if r["name"] == "svd_entropy")
    assert f"{coherence.NULL_MARGIN} x null_p05" in rule and coherence.SMOOTH_CAVEAT in rule


# F7 + F8: Ward's estimate refuses past its cap; tight bounds
def test_wards_estimate_refuses_past_its_cap(spec):
    n = 722 * 3600
    with pytest.raises(ValueError, match="hdbscan"):
        spec.estimate(np.zeros(n), np.arange(n, dtype=float), 1.0, **spec.validate_params({"method": "ward"}))


def test_the_param_bounds_are_tight(spec):
    by = {p.name: p for p in spec.params}
    assert by["ward_cut"].max <= 2.0
    assert by["hdbscan_min_cluster_size"].min >= 2
    sf = get_adapter("catalogue.shape_families")
    assert {p.name: p for p in sf.params}["kshape_n_init"].min >= 1


def test_an_empty_spanset_passes_through_with_the_reason(spec):
    x = np.zeros(2000)
    res = _run(spec, x, SpanSet(starts=(), ends=()))
    assert len(res.value.starts) == 0 and res.meta["k"] == 0
    assert "no event" in res.meta["summary"].lower()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
