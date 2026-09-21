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


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
