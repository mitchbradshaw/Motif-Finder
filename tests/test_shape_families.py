"""
test_shape_families.py
========================
The core under `catalogue.shape_families` and `interrogation.event_families`
(w2-e): `Working.Catalogue.shape_families`. One implementation, two surfaces —
it groups waveforms with the Library's own engine (`run_grouping`, basis
`shape-distance`) and reports, per family, the method's noise flags and the
SVD-entropy coherence with its null.

What is pinned:
* the method choice is the registry's (every method serving `shape-distance`),
  and the flattened params round-trip;
* Ward reproduces `run_grouping`'s Ward exactly on the same items (Q3);
* two clear-cut shapes on four coloured backgrounds -> two confident families
  (HDBSCAN and k-Shape), ARI >= 0.9, coherence below its own null;
* no structure (phase-randomised coloured noise) -> most events in no family;
* exemplars are medoid MEMBERS (the engine's medoid), at distance 0;
* gaps: a few NaNs are filled and counted, many -> missing_values, inf ->
  infinite_values; the counts add up;
* the sample cap passes through, Ward is refused past its cap in words;
* `event_families` (x + spans): events the cutter left out are `no_window`,
  and the per-event labels are the core's labels on the cut windows.
"""

import os
import sys

import numpy as np
import pytest
from sklearn.metrics import adjusted_rand_score

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from _event_families_synthetic import (equal_length, noise_events, phase_randomise,  # noqa: E402
                                       two_shapes)
from Working.Catalogue import shape_families as SF  # noqa: E402
from Working.library.coherence import svd_entropy  # noqa: E402
from Working.library.grouping import methods as registry  # noqa: E402
from Working.library.grouping.engine import run_grouping  # noqa: E402

BACKGROUNDS = ("ar1_095", "ar1_099", "random_walk", "drift")


def _items(waves):
    return [{"member_ref": i, "values": w} for i, w in enumerate(waves)]


# ── the method choice and its params come from the registry ────────────────

def test_the_methods_are_the_registrys_shape_distance_methods():
    want = tuple(m.name for m in registry.methods_for("shape-distance"))
    assert SF.shape_methods() == want
    assert {"ward", "kshape", "hdbscan"} <= set(want)
    assert SF.DEFAULT_METHOD == "hdbscan"


def test_every_method_param_is_flattened_and_round_trips():
    flat = SF.flat_param_specs()
    names = [f["flat"] for f in flat]
    assert len(names) == len(set(names)), "a flattened name is used twice"
    for m in SF.shape_methods():
        for p, spec in registry.get(m).params.items():
            want = p if p in SF.SHARED_PARAMS else f"{m}_{p}"
            assert want in names, (m, p)
    # the shared ones are the engine's rules, one control for every method
    assert {"min_group", "resample_length"} <= set(SF.SHARED_PARAMS)
    given = {"hdbscan_min_cluster_size": 7, "kshape_k": 3, "min_group": 5, "ward_cut": 0.3}
    assert SF.method_params("hdbscan", given) == {"min_cluster_size": 7, "min_group": 5}
    assert SF.method_params("kshape", given) == {"k": 3, "min_group": 5}
    assert SF.method_params("ward", given) == {"cut": 0.3, "min_group": 5}


# ── one implementation, two surfaces (Q3) ──────────────────────────────────

@pytest.mark.parametrize("kind", ["ar1_095", "random_walk"])
def test_ward_reproduces_run_grouping_exactly(kind):
    waves, _ = two_shapes(per=30, seed=3, kind=kind)
    params = {"cut": 0.42, "min_group": 5}
    lib = run_grouping(_items(waves), unit="single_motifs", basis="shape-distance", method="ward", params=params)
    got = SF.shape_families(waves, method="ward", params=params)
    want = np.array([-1 if a.family_id is None else a.family_id for a in lib.assignments])
    # the same partition, member for member, and the same omissions by reason
    assert adjusted_rand_score(want, got.labels) == 1.0
    assert ((want == -1) == (got.labels == -1)).all()
    assert [a.omit_reason for a in lib.assignments] == list(got.omit_reason)
    assert got.n == len(waves) and len(got.families) == lib.n_families
    by_label = {f.label: f for f in lib.families}
    for fam in got.families:
        lf = by_label[fam.library_label]
        assert sorted(fam.rows.tolist()) == sorted(lf.members)
        assert fam.medoid_row == lf.medoid
    for i, a in enumerate(lib.assignments):
        if a.distance is not None:
            assert got.distance[i] == pytest.approx(a.distance)


# ── clear-cut structure is found, and is not called noise ─────────────────

@pytest.mark.parametrize("kind", BACKGROUNDS)
@pytest.mark.parametrize("method,params", [("hdbscan", {}), ("kshape", {"k": 2})])
def test_two_clear_cut_shapes_give_two_confident_families(kind, method, params):
    waves, truth = two_shapes(per=40, seed=0, kind=kind)
    res = SF.shape_families(waves, method=method, params=params)
    assert adjusted_rand_score(truth, res.labels) >= 0.9
    assert len(res.families) == 2
    for fam in res.families:
        assert fam.flags["tested"] is True and fam.flags["noise_like"] is False, fam.flags
        c = fam.coherence
        # the family is more coherent than phase-randomised copies of its own members
        assert c["svd_entropy_norm"] < c["null_p05"], c
        assert c["svd_entropy_squared_norm"] < c["null_squared_median"], c
    assert res.fraction_placed >= 0.9 and res.fraction_confident >= 0.9


def test_families_are_numbered_by_size_largest_first():
    waves, truth = two_shapes(per=40, seed=1)
    waves = waves[:40] + waves[40:60]     # 40 drops, 20 squares
    res = SF.shape_families(waves, method="kshape", params={"k": 2})
    sizes = [f.size for f in res.families]
    assert [f.family for f in res.families] == [1, 2] and sizes == sorted(sizes, reverse=True)
    assert set(res.labels[:40].tolist()) == {1}


# ── no structure ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("kind", ["ar1", "ar1_099", "random_walk"])
@pytest.mark.parametrize("seed", [0, 1])
def test_phase_randomised_noise_is_mostly_in_no_family(kind, seed):
    x, spans = noise_events(kind, n_events=80, seed=seed)
    W = np.vstack([x[s:e] for s, e in zip(spans.starts, spans.ends)])
    res = SF.shape_families(W, method="hdbscan")
    assert res.fraction_placed < 0.5, (res.fraction_placed, [f.flags for f in res.families])
    assert res.fraction_confident <= res.fraction_placed
    assert res.omitted.get("not_in_a_dense_family", 0) == int((res.labels == -1).sum())


# ── exemplars and coherence ────────────────────────────────────────────────

def test_the_exemplar_is_the_engines_medoid_member_at_distance_zero():
    waves, _ = two_shapes(per=40, seed=2, kind="drift")
    res = SF.shape_families(waves, method="hdbscan")
    lib = run_grouping(_items(waves), unit="single_motifs", basis="shape-distance", method="hdbscan", params={})
    medoids = {f.label: f.medoid for f in lib.families}
    for fam in res.families:
        assert fam.medoid_row in fam.rows
        assert res.labels[fam.medoid_row] == fam.family
        assert fam.medoid_row == medoids[fam.library_label]
        assert res.distance[fam.medoid_row] == pytest.approx(0.0, abs=1e-6)
        # a member that is not the medoid sits further away
        others = [r for r in fam.rows if r != fam.medoid_row]
        assert np.nanmax(res.distance[others]) > 0


def test_coherence_is_w2bs_svd_entropy_on_the_members_aligned_to_the_medoid():
    waves, _ = two_shapes(per=40, seed=4, kind="ar1_099")
    res = SF.shape_families(waves, method="kshape", params={"k": 2}, seed=7)
    for fam in res.families:
        members = [waves[r] for r in fam.rows]
        want = svd_entropy(members, medoid=list(fam.rows).index(fam.medoid_row), seed=7)
        for key in ("svd_entropy", "svd_entropy_norm", "null_median", "null_p05", "svd_entropy_squared_norm",
                    "null_squared_median", "top_share", "n_members"):
            assert fam.coherence[key] == pytest.approx(want[key]), key


def test_a_mixed_family_scores_less_coherent_than_a_pure_one():
    waves, truth = two_shapes(per=40, seed=5, kind="ar1_095")
    res = SF.shape_families(waves, method="kshape", params={"k": 2})   # two pure families
    # the same coherence helper on a 'family' holding both shapes
    mixed = SF.coherence_of(waves, np.arange(len(waves)), medoid_row=0)
    for fam in res.families:
        assert mixed["svd_entropy_squared_norm"] > fam.coherence["svd_entropy_squared_norm"]
        assert mixed["top_share"] < fam.coherence["top_share"]


# ── gaps, omissions, counts ────────────────────────────────────────────────

def test_a_few_nans_are_filled_and_counted_many_are_missing_values():
    waves, truth = two_shapes(per=40, seed=6)
    waves = [np.asarray(w, dtype=float).copy() for w in waves]
    waves[3][10:14] = np.nan                     # under max_nan_frac: filled
    waves[50][:] = np.nan
    waves[51][: len(waves[51]) // 2] = np.nan    # half missing: refused
    waves[52][7] = np.inf
    res = SF.shape_families(waves, method="hdbscan", max_nan_frac=0.1)
    assert res.n_gap_filled == 1
    assert res.labels[3] != -1
    assert res.omit_reason[50] == "missing_values" and res.omit_reason[51] == "missing_values"
    assert res.omit_reason[52] == "infinite_values"
    assert sum(res.omitted.values()) == int((res.labels == -1).sum())
    assert res.n_placed == int((res.labels > 0).sum())
    assert res.fraction_placed == pytest.approx(res.n_placed / res.n)


def test_an_empty_input_is_an_empty_answer_that_says_so():
    res = SF.shape_families(np.empty((0, 50)), method="hdbscan")
    assert res.n == 0 and res.families == [] and len(res.labels) == 0
    assert res.fraction_placed is None
    assert res.notes and "no" in res.notes[0].lower()


def test_the_sample_cap_passes_through_and_the_rest_are_assigned():
    waves, truth = two_shapes(per=40, seed=0)
    res = SF.shape_families(waves, method="hdbscan", params={"sample": 50})
    assert res.fit_summary["fitted"] == 50 and res.fit_summary["assigned"] == 30
    assert adjusted_rand_score(truth, res.labels) >= 0.9


def test_ward_is_refused_past_its_cap_in_words(monkeypatch):
    monkeypatch.setattr(SF, "WARD_MAX_ITEMS", 50)
    waves, _ = two_shapes(per=40, seed=0)
    with pytest.raises(ValueError, match="hdbscan|kshape"):
        SF.shape_families(waves, method="ward")


def test_an_unknown_method_is_refused():
    with pytest.raises((ValueError, KeyError), match="method"):
        SF.shape_families([np.arange(10.0)] * 3, method="nope")


def test_the_same_seed_gives_the_same_families():
    waves, _ = two_shapes(per=40, seed=8, kind="random_walk")
    a = SF.shape_families(waves, method="kshape", params={"k": 2, "seed": 3})
    b = SF.shape_families(waves, method="kshape", params={"k": 2, "seed": 3})
    assert (a.labels == b.labels).all()
    assert [f.coherence["null_median"] for f in a.families] == [f.coherence["null_median"] for f in b.families]


def test_flags_and_fit_summary_reach_the_result():
    waves, _ = two_shapes(per=40, seed=0)
    res = SF.shape_families(waves, method="hdbscan")
    assert "null" in res.fit_summary and res.fit_summary["null"]["kind"] == "phase-randomised"
    for fam in res.families:
        assert {"noise_like", "unstable", "tested", "why"} <= set(fam.flags)
    ward = SF.shape_families(waves, method="ward", params={"min_group": 5})
    assert all(f.flags["tested"] is False and "not tested" in f.flags["why"] for f in ward.families)


def test_rules_name_the_method_the_distance_and_the_coherence():
    names = [r["name"] for r in SF.rules("hdbscan", {})]
    for want in ("families", "omitted", "family_distance", "svd_entropy", "noise_like", "exemplar"):
        assert want in names, want
    text = " ".join(r["rule"] for r in SF.rules("hdbscan", {}))
    assert "hdbscan" in text.lower() and "phase-randomised" in text


def test_the_estimate_is_the_methods_own_and_grows_with_the_count():
    a = SF.estimate_seconds(200, "hdbscan", {})
    b = SF.estimate_seconds(2000, "hdbscan", {})
    assert 0 < a < b
    from Working.library.grouping.engine import estimate_seconds
    assert b >= estimate_seconds(2000, "shape-distance", "hdbscan", {})


# ── event_families: x + spans -> per-event labels ──────────────────────────

def test_event_families_cuts_with_w2a_and_labels_every_event():
    from Working.Catalogue import event_windows as EW
    waves, truth = two_shapes(per=30, seed=0)
    W = equal_length(waves, 150)
    gap = 100
    x = np.concatenate([np.concatenate([w, np.zeros(gap)]) for w in W])
    starts = [i * (150 + gap) for i in range(len(W))]
    import pandas as pd
    from Working.types import SpanSet
    # one extra event too near the end for a 150 s window
    starts_all = starts + [len(x) - 20]
    spans = SpanSet(starts=tuple(starts_all), ends=tuple(s + 10 for s in starts_all),
                    features=pd.DataFrame({"polarity": [-1] * len(starts_all)}))
    ev = SF.event_families(x, 1.0, spans, anchor="start", length_s=150, pre_frac=0.0, method="hdbscan")
    assert len(ev.family) == len(starts_all)
    assert ev.family[-1] == -1 and ev.omit_reason[-1] == "no_window"
    assert adjusted_rand_score(truth, ev.family[:-1]) >= 0.9
    # the exact code path: the core on the cutter's windows
    ew = EW.event_windows(x, 1.0, spans, anchor="start", length_s=150, pre_frac=0.0)
    direct = SF.shape_families(EW.cut(x, ew.starts, ew.length), method="hdbscan")
    assert (ev.families.labels == direct.labels).all()
    assert (ev.family[ew.kept] == direct.labels).all()
    assert ev.families.omitted.get("no_window") is None and ev.omitted["no_window"] == 1


def test_the_core_imports_no_adapter_and_no_ui():
    import ast
    src = open(SF.__file__, encoding="utf-8").read()
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    assert not any(m.startswith(("Adapters", "webui", "panel", "fastapi", "holoviews", "bokeh")) for m in mods), mods


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
