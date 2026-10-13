"""
test_library_grouping_methods.py
==================================
Contract tests for the clustering-method registry and the three registered
methods behind `Working.library.grouping` (stage-3 Prompt 03, spec 8.2).

A grouping is `unit x basis x method(params) -> an assignment per member`
(`docs/LIBRARY_STORAGE.md` section 6). Spec 8.2 names three KINDS of basis,
and each kind needs its own method:

  ward            distance bases     shape distance, sequence similarity
  feature_bins    "feature bins, no distance"   amplitude, timescale,
                  frequency content, polarity
  labels          label bases        tag, provenance, custom

The registry is deliberately shaped like `Adapters/registry.py` — a name ->
spec map with a `register` that refuses a duplicate name — so a researcher
who has added an analysis block recognises how to add a clustering method.

Pure-numpy/scipy, no database and no UI. Runnable standalone:
    python tests/test_library_grouping_methods.py
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pytest

from Working.library.grouping import methods as method_registry
from Working.library.grouping.methods import FitResult


# --------------------------------------------------------------------------
# Synthetic shapes: three obviously different families, at three different
# native lengths, so that anything that finds three families has found them
# by SHAPE and not by duration (that is what scale-invariance means here).
# --------------------------------------------------------------------------

def _bump(n, rng):
    t = np.linspace(-3.0, 3.0, n)
    return np.exp(-t ** 2) + rng.normal(0.0, 0.01, n)


def _ramp(n, rng):
    return np.linspace(0.0, 1.0, n) + rng.normal(0.0, 0.01, n)


def _wave(n, rng):
    t = np.linspace(0.0, 2.0 * np.pi * 2.0, n)
    return np.sin(t) + rng.normal(0.0, 0.01, n)


def three_shape_families(per_family=8, seed=7):
    """24 waveforms in three unmistakable shape families, at lengths that
    differ within each family so duration cannot stand in for shape."""
    rng = np.random.default_rng(seed)
    waves, truth = [], []
    for fam, maker in enumerate((_bump, _ramp, _wave)):
        for k in range(per_family):
            n = 90 + 17 * k
            waves.append(maker(n, rng))
            truth.append(fam)
    return waves, truth


# --------------------------------------------------------------------------
# The registry
# --------------------------------------------------------------------------

class _Dummy:
    name = "dummy_method_for_tests"
    label = "Dummy"
    applies_to = ("tag",)
    description = "only ever registered inside a test"
    params = {}

    def fit(self, data, *, params):
        return FitResult(method=self.name, n=len(data))

    def assign(self, fit, *, cut=None):
        return [1] * fit.n

    def merge_heights(self, fit):
        return []


def test_register_and_get_round_trip():
    method = _Dummy()
    try:
        method_registry.register(method)
        assert method_registry.get("dummy_method_for_tests") is method
    finally:
        method_registry._REGISTRY.pop("dummy_method_for_tests", None)


def test_duplicate_registration_is_an_error_not_a_silent_overwrite():
    method = _Dummy()
    try:
        method_registry.register(method)
        with pytest.raises(ValueError):
            method_registry.register(_Dummy())
    finally:
        method_registry._REGISTRY.pop("dummy_method_for_tests", None)


def test_get_unknown_name_raises_and_names_what_is_available():
    with pytest.raises(KeyError) as excinfo:
        method_registry.get("no_such_method")
    assert "ward" in str(excinfo.value)


def test_available_has_the_three_built_ins_with_a_spec_each():
    available = method_registry.available()
    for name in ("ward", "feature_bins", "labels"):
        assert name in available, f"{name} should be registered on import"
        spec = available[name]
        assert spec["name"] == name
        assert isinstance(spec["label"], str) and spec["label"]
        assert isinstance(spec["description"], str) and spec["description"]
        assert isinstance(spec["applies_to"], tuple) and spec["applies_to"]
        for pname, pspec in spec["params"].items():
            assert set(("type", "default", "label", "help")) <= set(pspec), pname


def test_the_three_basis_kinds_are_covered_between_them():
    covered = set()
    for spec in method_registry.available().values():
        covered.update(spec["applies_to"])
    assert {"shape-distance", "sequence-similarity"} <= covered
    assert {"amplitude", "timescale", "frequency-content", "polarity"} <= covered
    assert {"tag", "provenance"} <= covered


# --------------------------------------------------------------------------
# ward
# --------------------------------------------------------------------------

def test_ward_finds_exactly_three_obvious_shape_families():
    ward = method_registry.get("ward")
    waves, truth = three_shape_families()
    fit = ward.fit(waves, params={})
    families = ward.assign(fit, cut=0.42)
    assert len(families) == len(waves)
    assert len(set(families)) == 3
    # and they agree with the truth: same family iff same generator
    for i in range(len(waves)):
        for j in range(len(waves)):
            assert (families[i] == families[j]) == (truth[i] == truth[j])


def test_a_tighter_cut_yields_more_families():
    ward = method_registry.get("ward")
    waves, _ = three_shape_families()
    fit = ward.fit(waves, params={})
    loose = len(set(ward.assign(fit, cut=3.0)))
    canon = len(set(ward.assign(fit, cut=0.42)))
    tight = len(set(ward.assign(fit, cut=0.005)))
    assert loose < canon < tight


def test_merge_heights_are_the_tree_and_come_back_sorted():
    ward = method_registry.get("ward")
    waves, _ = three_shape_families()
    fit = ward.fit(waves, params={})
    heights = ward.merge_heights(fit)
    assert len(heights) == len(waves) - 1
    assert heights == sorted(heights)
    assert all(h >= 0.0 for h in heights)


def test_ward_distances_are_the_projects_scale_invariant_distance():
    """The vectors ward clusters are `resample_to_length` + `z_normalize` —
    the same pair `scale_invariant_distance` uses — so its pairwise distance
    must BE that distance at the fixed resample length, up to the documented
    normalisation."""
    from Working.distances import scale_invariant_distance
    ward = method_registry.get("ward")
    waves, _ = three_shape_families(per_family=2)
    fit = ward.fit(waves, params={})
    n = fit.payload["resample_length"]
    scale = fit.payload["distance_scale"]
    expected = scale_invariant_distance(waves[0], waves[3], n_samples=n) / scale
    assert fit.distances[0, 3] == pytest.approx(expected, rel=1e-9)


def test_medoid_is_the_member_nearest_the_rest():
    ward = method_registry.get("ward")
    waves, _ = three_shape_families()
    fit = ward.fit(waves, params={})
    families = ward.assign(fit, cut=0.42)
    members = [i for i, f in enumerate(families) if f == families[0]]
    index, mean_distance = ward.medoid(fit, members)
    brute = min(members, key=lambda i: fit.distances[i, members].sum())
    assert index == brute
    assert mean_distance == pytest.approx(
        fit.distances[index, members].sum() / max(1, len(members) - 1))


def test_omit_d_omits_a_far_outlier_as_past_cut():
    ward = method_registry.get("ward")
    waves, _ = three_shape_families()
    rng = np.random.default_rng(99)
    waves = waves + [rng.normal(0.0, 1.0, 140)]        # pure noise, near nothing
    fit = ward.fit(waves, params={})
    families = ward.assign(fit, cut=0.42, omit_d=0.50)
    assert families[-1] is None
    assert fit.omit_reasons[len(waves) - 1] == "past_cut"
    assert all(f is not None for f in families[:-1])


def test_ward_handles_a_single_item_without_a_tree():
    ward = method_registry.get("ward")
    waves, _ = three_shape_families(per_family=1)
    fit = ward.fit(waves[:1], params={})
    assert ward.assign(fit, cut=0.42) == [1]
    assert ward.merge_heights(fit) == []


# --------------------------------------------------------------------------
# feature_bins
# --------------------------------------------------------------------------

def test_feature_bins_quantiles_split_evenly():
    binner = method_registry.get("feature_bins")
    values = list(range(100))
    fit = binner.fit(values, params={"bin_method": "quantiles", "count": 4})
    families = binner.assign(fit)
    counts = {f: families.count(f) for f in set(families)}
    assert len(counts) == 4
    assert all(20 <= c <= 30 for c in counts.values()), counts


def test_feature_bins_log_spaced_needs_a_positive_range():
    binner = method_registry.get("feature_bins")
    with pytest.raises(ValueError):
        binner.fit([1.0, 2.0], params={"bin_method": "log-spaced", "count": 3,
                                       "range": (0.0, 1.0)})


def test_feature_bins_log_spaced_puts_decades_in_their_own_bins():
    binner = method_registry.get("feature_bins")
    values = [0.0015, 0.015, 0.15]
    fit = binner.fit(values, params={"bin_method": "log-spaced", "count": 3,
                                     "range": (0.001, 1.0)})
    assert binner.assign(fit) == [1, 2, 3]


def test_feature_bins_fixed_edges_uses_the_edges_given():
    binner = method_registry.get("feature_bins")
    values = [0.005, 0.02, 0.2]
    fit = binner.fit(values, params={"bin_method": "fixed edges",
                                     "range": (0.002, 0.01, 0.03, 0.5)})
    assert binner.assign(fit) == [1, 2, 3]


def test_a_value_outside_every_bin_is_omitted_as_outside_bins():
    binner = method_registry.get("feature_bins")
    values = [0.005, 0.02, 99.0]
    fit = binner.fit(values, params={"bin_method": "fixed edges",
                                     "range": (0.002, 0.01, 0.03, 0.5)})
    families = binner.assign(fit)
    assert families[2] is None
    assert fit.omit_reasons[2] == "outside_bins"


def test_feature_bins_has_no_tree_so_no_merge_heights():
    binner = method_registry.get("feature_bins")
    fit = binner.fit([1.0, 2.0, 3.0], params={"bin_method": "quantiles", "count": 2})
    assert binner.merge_heights(fit) == []


def test_feature_bin_families_are_labelled_by_their_edges():
    binner = method_registry.get("feature_bins")
    fit = binner.fit([0.005, 0.02], params={"bin_method": "fixed edges",
                                            "range": (0.002, 0.01, 0.03)})
    assert "0.002" in fit.family_labels[1]
    assert "0.01" in fit.family_labels[1]


# --------------------------------------------------------------------------
# labels
# --------------------------------------------------------------------------

def test_labels_makes_one_group_per_label():
    labels = method_registry.get("labels")
    fit = labels.fit(["drop", "spike", "drop", "spike", "drop"], params={})
    families = labels.assign(fit)
    assert len(set(families)) == 2
    assert families[0] == families[2] == families[4]
    assert families[1] == families[3]
    assert set(fit.family_labels.values()) == {"drop", "spike"}


def test_an_unlabelled_member_is_omitted_as_no_label():
    labels = method_registry.get("labels")
    fit = labels.fit(["drop", None, "spike", ""], params={})
    families = labels.assign(fit)
    assert families[1] is None and fit.omit_reasons[1] == "no_label"
    assert families[3] is None and fit.omit_reasons[3] == "no_label"


def test_labels_applies_to_tag_and_provenance():
    spec = method_registry.available()["labels"]
    assert "tag" in spec["applies_to"]
    assert "provenance" in spec["applies_to"]


# --------------------------------------------------------------------------
# w2-b: kshape and hdbscan (LIBRARY_STORAGE.md 6.2)
#
# The families are three shapes — a drop with a slow recovery, a sharkfin, a
# square pulse — each member cut from its own window with the event up to 20 %
# of the window off-centre and at a random amplitude, on coloured backgrounds
# (`tests/_shape_families.py`). That shift is what point-by-point Ward cannot
# see past and the shape-based distance can.
# --------------------------------------------------------------------------

import warnings  # noqa: E402

from scipy.cluster.hierarchy import fcluster  # noqa: E402
from sklearn.metrics import adjusted_rand_score  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shape_families import pure_noise, three_families  # noqa: E402

BACKGROUNDS = ("ar1_095", "ar1_099", "random_walk", "drift")


def _families_of(assigned):
    return np.array([-1 if f is None else f for f in assigned])


def _ward_ari(waves, truth, k=3):
    from Working.library.grouping.methods import ward as ward_mod
    vectors = ward_mod.shape_vectors(waves)
    tree = ward_mod.ward_linkage(ward_mod.condensed_distances(vectors))
    return adjusted_rand_score(truth, fcluster(tree, k, criterion="maxclust"))


def test_kshape_and_hdbscan_are_registered_for_shape_distance_only():
    available = method_registry.available()
    for name in ("kshape", "hdbscan"):
        assert name in available
        spec = available[name]
        assert spec["applies_to"] == ("shape-distance",)
        assert spec["label"] and spec["description"]
        for pname, pspec in spec["params"].items():
            assert set(("type", "default", "label", "help")) <= set(pspec), (name, pname)
    assert available["kshape"]["params"]["n_init"]["default"] == 10
    assert available["kshape"]["params"]["omit_d"]["default"] == 0       # 0 = automatic (fix round 1)
    assert available["hdbscan"]["params"]["min_cluster_size"]["default"] == 10
    assert available["hdbscan"]["params"]["sample"]["default"] == 5000


def test_the_new_omission_reasons_are_the_engines():
    from Working.library.grouping import engine
    assert engine.OMIT_NOT_IN_A_DENSE_FAMILY == "not_in_a_dense_family"
    assert engine.OMIT_INFINITE_VALUES == "infinite_values"
    assert engine.OMIT_MISSING_VALUES == "missing_values"
    for reason in ("not_in_a_dense_family", "infinite_values", "missing_values"):
        assert reason in engine.__doc__, f"{reason} has its one-line meaning in the engine's list"


# ---- kshape --------------------------------------------------------------

def test_kshape_reproduces_aeons_kshape_start_for_start():
    """The implementation is aeon 1.4's `KShape` with the per-pair work
    batched; from the same random_state it must give the same labels, the
    same centres and the same summed distance."""
    from aeon.clustering import KShape
    from Working.library.grouping.methods.kshape import kshape_fit
    rng = np.random.default_rng(3)
    X = rng.normal(size=(40, 64)).cumsum(axis=1)
    for seed, k in ((0, 4), (2, 7)):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ref = KShape(n_clusters=k, n_init=3, random_state=seed).fit(X[:, None, :])
        ours = kshape_fit(X, k, n_init=3, seed=seed)
        assert (ref.labels_ == ours["labels"]).all(), (seed, k)
        assert np.allclose(ref.cluster_centres_[:, 0, :], ours["centroids"], atol=1e-9)
        assert ours["inertia"] == pytest.approx(ref.inertia_, abs=1e-9)
        assert ours["n_iter"] == ref.n_iter_


@pytest.mark.parametrize("kind", BACKGROUNDS)
def test_kshape_recovers_shifted_families_where_ward_does_not(kind):
    kshape = method_registry.get("kshape")
    waves, truth = three_families(per=30, seed=1, kind=kind, noise=0.1)
    fit = kshape.fit(waves, params={"k": 3})
    families = _families_of(kshape.assign(fit))
    ari_k = adjusted_rand_score(truth, families)
    ari_w = _ward_ari(waves, truth)
    assert ari_k >= 0.9, f"{kind}: k-Shape ARI {ari_k:.3f} (Ward {ari_w:.3f})"
    assert ari_w <= ari_k - 0.3, f"{kind}: Ward ARI {ari_w:.3f} is not measurably worse than {ari_k:.3f}"


def test_kshape_chooses_k_by_silhouette_and_records_every_k():
    kshape = method_registry.get("kshape")
    waves, truth = three_families(per=20, seed=2)
    fit = kshape.fit(waves, params={"k": 0, "n_init": 2})
    scores = fit.payload["k_scores"]
    assert [s["k"] for s in scores] == list(range(2, 13))
    assert all(s["silhouette"] is not None for s in scores)
    qualifying = [s for s in scores if s["qualifies"]]
    best = max(qualifying, key=lambda s: s["silhouette"])
    assert fit.payload["k"] == best["k"]
    assert "silhouette" in fit.payload["k_rule"]
    # the silhouette merges the two positive shapes or keeps them apart; it never shatters three families
    assert fit.payload["k"] in (2, 3)


def test_kshape_omit_d_omits_what_is_far_from_its_centre_as_past_cut():
    kshape = method_registry.get("kshape")
    waves, truth = three_families(per=20, seed=2, n_noise=10)
    fit = kshape.fit(waves, params={"k": 3})
    dist = fit.payload["dist"]
    assert dist[truth >= 0].max() < dist[truth < 0].min(), "noise sits further from every centre"
    cut = float((dist[truth >= 0].max() + dist[truth < 0].min()) / 2)
    families = kshape.assign(fit, omit_d=cut)
    assert all(families[i] is None and fit.omit_reasons[i] == "past_cut"
               for i in np.flatnonzero(truth < 0))
    assert all(families[i] is not None for i in np.flatnonzero(truth >= 0))
    assert kshape.assign(fit, omit_d=None).count(None) == 0


def test_kshape_medoid_is_the_member_nearest_its_centroid_and_there_is_no_tree():
    from Working.distances import sbd
    kshape = method_registry.get("kshape")
    waves, _ = three_families(per=15, seed=5)
    fit = kshape.fit(waves, params={"k": 3})
    families = kshape.assign(fit)
    members = [i for i, f in enumerate(families) if f == families[0]]
    row, mean_d = kshape.medoid(fit, members)
    centroid = fit.payload["centroids"][fit.payload["cluster"][row]]
    vectors = fit.payload["vectors"]
    by_centroid = {i: sbd(vectors[i], centroid) for i in members}
    assert row == min(by_centroid, key=by_centroid.get)
    expected = np.mean([sbd(vectors[row], vectors[i]) / 2 for i in members if i != row])
    assert mean_d == pytest.approx(expected, abs=1e-5)
    assert kshape.merge_heights(fit) == []
    assert fit.payload["distance_scale"] == 2.0


def test_kshape_fits_a_sample_and_assigns_the_rest_by_nearest_centroid():
    kshape = method_registry.get("kshape")
    waves, truth = three_families(per=30, seed=6)
    fit = kshape.fit(waves, params={"k": 3, "sample": 45, "seed": 3})
    p = fit.payload
    assert len(p["fitted_rows"]) == 45 and len(p["assigned_rows"]) == 45
    assert sorted(p["fitted_rows"] + p["assigned_rows"]) == list(range(90))
    assert p["fit_summary"]["fitted"] == 45 and p["fit_summary"]["assigned"] == 45
    assert adjusted_rand_score(truth, _families_of(kshape.assign(fit))) >= 0.9
    again = kshape.fit(waves, params={"k": 3, "sample": 45, "seed": 3})
    assert again.payload["fitted_rows"] == p["fitted_rows"], "the sample is seeded"


@pytest.mark.parametrize("name", ["kshape", "hdbscan"])
def test_a_waveform_with_nan_or_inf_is_omitted_with_its_own_reason(name):
    method = method_registry.get(name)
    waves, _ = three_families(per=12, seed=7)
    bad_nan = waves[0].copy()
    bad_nan[5] = np.nan
    bad_inf = waves[1].copy()
    bad_inf[9] = np.inf
    waves = waves + [bad_nan, bad_inf, np.array([])]
    n = len(waves)
    fit = method.fit(waves, params={"k": 3} if name == "kshape" else {"min_cluster_size": 5})
    families = method.assign(fit)
    assert families[n - 3] is None and fit.omit_reasons[n - 3] == "missing_values"
    assert families[n - 2] is None and fit.omit_reasons[n - 2] == "infinite_values"
    assert families[n - 1] is None and fit.omit_reasons[n - 1] == "missing_values"


# ---- hdbscan -------------------------------------------------------------

@pytest.mark.parametrize("kind", BACKGROUNDS)
def test_hdbscan_finds_the_three_families_and_leaves_the_noise_out(kind):
    hdbscan = method_registry.get("hdbscan")
    waves, truth = three_families(per=30, seed=3, kind=kind, n_noise=39)   # 30 % noise
    fit = hdbscan.fit(waves, params={})
    families = _families_of(hdbscan.assign(fit))
    events, noise = truth >= 0, truth < 0
    assert len(set(families[events]) - {-1}) == 3
    assert adjusted_rand_score(truth[events], families[events]) >= 0.9
    omitted_noise = [fit.omit_reasons.get(i) for i in np.flatnonzero(noise)]
    assert omitted_noise.count("not_in_a_dense_family") >= 0.8 * noise.sum(), omitted_noise
    flags = fit.payload["family_flags"]
    assert len(flags) == 3 and not any(f["noise_like"] for f in flags.values()), flags


def test_hdbscan_assigns_the_rows_not_fitted_through_the_nearest_dense_member():
    hdbscan = method_registry.get("hdbscan")
    waves, truth = three_families(per=40, seed=8, n_noise=50)
    fit = hdbscan.fit(waves, params={"sample": 100, "seed": 1})
    p = fit.payload
    assert len(p["fitted_rows"]) == 100 and len(p["assigned_rows"]) == len(waves) - 100
    families = _families_of(hdbscan.assign(fit))
    assigned = np.array(p["assigned_rows"])
    events = assigned[truth[assigned] >= 0]
    noise = assigned[truth[assigned] < 0]
    assert adjusted_rand_score(truth[events], families[events]) >= 0.9
    assert np.mean(families[noise] == -1) >= 0.8
    assert all(fit.omit_reasons[i] == "not_in_a_dense_family" for i in noise if families[i] == -1)


def test_hdbscan_cut_selection_and_distance_are_honoured():
    hdbscan = method_registry.get("hdbscan")
    waves, truth = three_families(per=30, seed=9, n_noise=20)
    fit = hdbscan.fit(waves, params={})
    base = len(set(hdbscan.assign(fit)) - {None})
    # a large epsilon merges what sits closer than it: never more families
    merged = len(set(hdbscan.assign(fit, cut=0.4)) - {None})
    assert fit.payload["cut"] == 0.4 and merged <= base
    leaf = hdbscan.fit(waves, params={"cluster_selection_method": "leaf"})
    assert len(set(hdbscan.assign(leaf)) - {None}) >= base
    euclid = hdbscan.fit(waves, params={"distance": "euclidean"})
    assert euclid.payload["distance"] == "euclidean"
    hdbscan.assign(euclid)
    with pytest.raises(ValueError):
        hdbscan.fit(waves, params={"distance": "dtw"})
    assert hdbscan.merge_heights(fit) == []


def test_hdbscan_medoid_is_a_fitted_member_nearest_the_rest():
    hdbscan = method_registry.get("hdbscan")
    waves, _ = three_families(per=20, seed=10)
    fit = hdbscan.fit(waves, params={"min_cluster_size": 5})
    families = hdbscan.assign(fit)
    members = [i for i, f in enumerate(families) if f == 1]
    row, _ = hdbscan.medoid(fit, members)
    D = fit.payload["D_fit"]
    pos = {r: k for k, r in enumerate(fit.payload["fitted_rows"])}
    sums = {i: D[pos[i], [pos[j] for j in members]].sum() for i in members}
    assert row == min(sums, key=sums.get)


# ---- both, through the engine (6.2 items 6 and 8) ------------------------

@pytest.mark.parametrize("name,params,changed", [
    ("kshape", {"k": 3, "min_group": 5}, {"k": 4}),
    ("hdbscan", {"min_group": 5}, {"min_cluster_size": 6}),
])
def test_both_run_through_run_grouping_with_reasons_and_a_moving_hash(name, params, changed):
    from Working.library.grouping.engine import run_grouping
    waves, truth = three_families(per=30, seed=11, n_noise=18)
    waves = waves + [np.full(50, np.nan)]
    items = [{"member_ref": f"m{i}", "content_hash": f"h{i}", "values": w}
             for i, w in enumerate(waves)]
    result = run_grouping(items, unit="single_motifs", basis="shape-distance",
                          method=name, params=params)
    assert len(result.assignments) == len(items)
    assert [a.ref for a in result.assignments] == [it["member_ref"] for it in items]
    assert result.n_families >= 3
    reasons = result.omitted_by_reason
    assert reasons.get("missing_values") == 1
    if name == "hdbscan":
        assert reasons.get("not_in_a_dense_family", 0) >= 6
    for fam in result.families:
        medoid = next(a for a in result.assignments if a.ref == fam.medoid)
        assert medoid.is_medoid and medoid.distance == pytest.approx(0.0, abs=1e-6)
        assert all(0.0 <= a.distance <= 1.0 for a in result.assignments
                   if a.family_id == fam.id)
    assert result.merge_heights == []
    other = run_grouping(items, unit="single_motifs", basis="shape-distance",
                         method=name, params={**params, **changed})
    assert other.recipe_hash != result.recipe_hash


def test_neither_new_method_serves_sequence_similarity():
    from Working.library.grouping.engine import run_grouping
    for name in ("kshape", "hdbscan"):
        with pytest.raises(ValueError):
            run_grouping([{"member_ref": 1, "values": [1.0, 2.0]}], unit="sequences",
                         basis="sequence-similarity", method=name)


# ---- fix round 1: the surrogate null and the flags that carry it ---------
#
# A family must beat what the members' own noise produces. Both methods fit the
# same way on phase-randomised surrogates of the vectors (each row's amplitude
# spectrum kept, so the colour is kept): HDBSCAN calls a family confident only
# if its separation AND its size beat every surrogate family; k-Shape's
# automatic `omit_d` is, per family, the 5th percentile of the surrogates'
# distance to that family's centroid. The verdict travels on each `Family` as
# `flags` and the null on `GroupingResult.fit_summary`, so the editor and the
# Library see it (critic finding 1: it used to stay on the fit).

import json  # noqa: E402

NULL_METHODS = [("hdbscan", {}), ("kshape", {"k": 3})]


def _items(waves):
    return [{"member_ref": i, "content_hash": f"h{i}", "values": w} for i, w in enumerate(waves)]


def _run(name, params, waves):
    from Working.library.grouping.engine import run_grouping
    return run_grouping(_items(waves), unit="single_motifs", basis="shape-distance",
                        method=name, params=params)


def test_phase_randomised_rows_keep_each_rows_amplitude_spectrum():
    from Working.library.grouping.methods.kshape import phase_randomised_rows
    rng = np.random.default_rng(0)
    X = rng.normal(size=(6, 64)).cumsum(axis=1)
    S = phase_randomised_rows(X, np.random.default_rng(1))
    assert S.shape == X.shape
    assert np.allclose(np.abs(np.fft.rfft(S, axis=1)), np.abs(np.fft.rfft(X, axis=1)), atol=1e-9)
    assert not np.allclose(S, X)
    again = phase_randomised_rows(X, np.random.default_rng(1))
    assert np.array_equal(S, again), "seeded"


@pytest.mark.parametrize("name,params", NULL_METHODS)
@pytest.mark.parametrize("kind", BACKGROUNDS)
@pytest.mark.parametrize("seed", (0, 1))
def test_pure_coloured_noise_is_flagged_noise_like_through_run_grouping(name, params, kind, seed):
    result = _run(name, params, pure_noise(300, seed, kind))
    report = [(f.label, f.size, f.flags) for f in result.families]
    assert all(f.flags["noise_like"] for f in result.families), report
    assert all(f.flags["tested"] and f.flags["why"] for f in result.families), report
    null = result.fit_summary["null"]
    assert null["draws"] == 3 and null["kind"] == "phase-randomised"
    json.dumps(result.fit_summary)                    # it is saved as JSON


@pytest.mark.parametrize("name,params", NULL_METHODS)
@pytest.mark.parametrize("kind", BACKGROUNDS)
def test_three_shifted_families_are_confident_through_run_grouping(name, params, kind):
    waves, truth = three_families(per=30, seed=1, kind=kind, noise=0.1)
    result = _run(name, params, waves)
    report = [(f.label, f.size, f.flags) for f in result.families]
    # HDBSCAN's eom selection may keep the sharkfin and the square (the two positive
    # shapes) as one crowd at 90 members; whatever it finds must be confident
    assert result.n_families == 3 or (name == "hdbscan" and result.n_families == 2), report
    assert not any(f.flags["noise_like"] for f in result.families), report
    assert all(f.flags["tested"] for f in result.families)
    assert result.n_assigned >= 0.9 * len(waves), result.omitted_by_reason


def test_kshape_automatic_omit_d_is_the_default_and_omits_noise_members():
    spec = method_registry.available()["kshape"]["params"]["omit_d"]
    assert spec["default"] == 0
    assert "0.5" in spec["help"], "the help says a fixed 0.5 almost never fires on the SBD scale"
    waves, truth = three_families(per=30, seed=2, n_noise=20, kind="ar1_099")
    result = _run("kshape", {"k": 3}, waves)
    omitted = np.array([a.family_id is None for a in result.assignments])
    assert omitted[truth < 0].mean() >= 0.5, "most noise windows are past their family's null"
    assert omitted[truth >= 0].mean() <= 0.1
    per_family = result.fit_summary["null"]["omit_d_by_family"]
    assert set(per_family) == {f.label for f in result.families}
    assert all(0.0 < v < 0.5 for v in per_family.values())
    fixed = _run("kshape", {"k": 3, "omit_d": 0.5}, waves)
    assert fixed.n_omitted == 0, "a fixed 0.5 keeps everything — which is why it is not the default"


def test_the_fit_summary_reaches_the_result_with_the_k_rule():
    waves, _ = three_families(per=15, seed=4)
    result = _run("kshape", {"k": 0}, waves)
    fs = result.fit_summary
    assert fs["fitted"] == len(waves) and fs["assigned"] == 0
    assert "silhouette" in fs["k_rule"] and len(fs["k_scores"]) == 11
    json.dumps(fs)


def test_a_method_without_a_null_says_its_families_were_not_tested():
    waves, _ = three_families(per=15, seed=4)
    result = _run("ward", {"cut": 1.0, "min_group": 2}, waves)
    assert result.families
    for f in result.families:
        assert f.flags["tested"] is False and f.flags["noise_like"] is False
        assert "no null" in f.flags["why"]
    assert isinstance(result.fit_summary, dict)


def test_hdbscan_has_no_fixed_separation_floor_and_reports_separation():
    from Working.library.grouping.methods import hdbscan as hdbscan_mod
    assert not hasattr(hdbscan_mod, "UNSTABLE_SEPARATION")
    waves, _ = three_families(per=30, seed=3, n_noise=20)
    result = _run("hdbscan", {}, waves)
    null = result.fit_summary["null"]
    assert {"max_separation", "max_size", "families_per_draw"} <= set(null)
    for f in result.families:
        assert "separation" in f.flags and f.flags["separation"] > null["max_separation"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
