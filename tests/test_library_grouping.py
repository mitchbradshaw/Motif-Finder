"""
test_library_grouping.py
==========================
Contract tests for the grouping engine and its feature bases
(`Working/library/grouping/engine.py`, `bases.py`) — stage-3 Prompt 03.

The engine answers spec 8.2's question: `unit x basis x method(params) ->
an assignment per member`, with the four "what does not fit" rules attached.
Two properties are load-bearing and tested here directly:

  * **Omitted entries are flagged, never deleted** — every input item comes
    back with an assignment, and an omitted one carries its reason
    (`outside_bins`, `past_cut`, `group_too_small`, `not_in_a_sequence`,
    `no_label`).
  * **The engine never touches the database.** `run_grouping` takes plain
    dicts, which is what lets the whole engine be tested without one.

The feature bases (`amplitude`, `timescale`, `frequency-content`,
`polarity`) are computed on demand and never stored — `LIBRARY_STORAGE.md`
3.4 and spec 4.4, which rejects measured features on Library rows outright.

Pure-numpy/scipy, no database and no UI. Runnable standalone:
    python tests/test_library_grouping.py
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

from Working.library.grouping import bases
from Working.library.grouping.engine import preview, run_grouping


# --------------------------------------------------------------------------
# Item fixtures — plain dicts, exactly what the bridge will hand over.
# --------------------------------------------------------------------------

def _bump(n, rng, amp=1.0):
    t = np.linspace(-3.0, 3.0, n)
    return amp * np.exp(-t ** 2) + rng.normal(0.0, 0.01, n)


def _ramp(n, rng, amp=1.0):
    return amp * np.linspace(0.0, 1.0, n) + rng.normal(0.0, 0.01, n)


def _wave(n, rng, amp=1.0):
    t = np.linspace(0.0, 4.0 * np.pi, n)
    return amp * np.sin(t) + rng.normal(0.0, 0.01, n)


def shape_items(per_family=8, seed=11):
    """24 library members in three unmistakable shape families."""
    rng = np.random.default_rng(seed)
    items = []
    for fam, maker in enumerate((_bump, _ramp, _wave)):
        for k in range(per_family):
            n = 90 + 17 * k
            items.append({
                "member_ref": 100 * (fam + 1) + k,
                "content_hash": f"h{fam}{k:02d}",
                "values": maker(n, rng),
                "fs": 1.0,
                "tags": ["drop" if fam == 0 else "other"],
                "recording_id": 1 + fam,
            })
    return items


# --------------------------------------------------------------------------
# bases — the four feature computations
# --------------------------------------------------------------------------

def test_amplitude_is_peak_to_peak():
    x = np.array([-2.0, 0.0, 5.0, 1.0])
    assert bases.amplitude(x) == pytest.approx(7.0)


def test_timescale_is_the_duration_in_seconds():
    assert bases.timescale(np.zeros(500), fs=10.0) == pytest.approx(50.0)


def test_frequency_content_finds_the_dominant_frequency():
    fs = 100.0
    t = np.arange(4096) / fs
    x = np.sin(2.0 * np.pi * 5.0 * t)
    assert bases.frequency_content(x, fs=fs) == pytest.approx(5.0, abs=0.6)


def test_polarity_separates_up_down_and_biphasic():
    rise = np.array([0.0, 0.0, 4.0, 0.0, 0.0])
    fall = -rise
    both = np.array([0.0, 3.0, 0.0, -3.0, 0.0])
    assert bases.polarity(rise) > 0.5
    assert bases.polarity(fall) < -0.5
    assert abs(bases.polarity(both)) < 0.3


def test_compute_feature_dispatches_by_basis_name():
    x = np.array([-1.0, 0.0, 3.0])
    assert bases.compute_feature("amplitude", x, fs=1.0) == pytest.approx(4.0)
    assert bases.compute_feature("timescale", x, fs=2.0) == pytest.approx(1.5)
    with pytest.raises(KeyError):
        bases.compute_feature("roughness", x, fs=1.0)


# --------------------------------------------------------------------------
# bases.distribution — what the grouping editor's histogram draws
# --------------------------------------------------------------------------

def test_distribution_quantiles_puts_a_quarter_in_each_bin():
    dist = bases.distribution(list(range(100)), bin_method="quantiles", count=4)
    assert len(dist.edges) == 5
    assert sum(dist.counts) == 100
    assert all(20 <= c <= 30 for c in dist.counts)


def test_distribution_log_spaced_edges_are_geometric():
    dist = bases.distribution([0.002, 0.05, 0.4], bin_method="log-spaced",
                              count=3, range=(0.001, 1.0))
    ratios = [dist.edges[i + 1] / dist.edges[i] for i in range(3)]
    assert ratios[0] == pytest.approx(ratios[1])
    assert ratios[1] == pytest.approx(ratios[2])


def test_distribution_fixed_edges_are_used_verbatim():
    dist = bases.distribution([0.005, 0.02, 0.2], bin_method="fixed edges",
                              range=(0.002, 0.01, 0.03, 0.5))
    assert list(dist.edges) == [0.002, 0.01, 0.03, 0.5]
    assert list(dist.counts) == [1, 1, 1]


def test_distribution_counts_what_falls_outside_the_range():
    dist = bases.distribution([0.005, 99.0], bin_method="fixed edges",
                              range=(0.002, 0.01))
    assert dist.n_outside == 1
    assert sum(dist.counts) == 1


def test_distribution_rejects_an_impossible_bin_count():
    with pytest.raises(ValueError):
        bases.distribution([1.0, 2.0], bin_method="quantiles", count=1)


def test_distribution_rejects_non_increasing_fixed_edges():
    with pytest.raises(ValueError):
        bases.distribution([1.0], bin_method="fixed edges", range=(0.01, 0.03, 0.03))


# --------------------------------------------------------------------------
# bases.applicable_bases — "disabled with its reason" (spec 8.2)
# --------------------------------------------------------------------------

def test_sequence_similarity_is_disabled_for_single_motifs_with_a_reason():
    applicable = bases.applicable_bases("single_motifs")
    entry = applicable["sequence-similarity"]
    assert entry["applies"] is False
    assert entry["reason"] and "sequence" in entry["reason"].lower()


def test_sequence_similarity_applies_to_sequences():
    assert bases.applicable_bases("sequences")["sequence-similarity"]["applies"] is True


def test_shape_distance_is_disabled_for_spike_trains_with_a_reason():
    entry = bases.applicable_bases("spike_trains")["shape-distance"]
    assert entry["applies"] is False
    assert entry["reason"]


def test_every_basis_is_reported_for_every_unit():
    for unit in ("single_motifs", "sequences", "spike_trains"):
        applicable = bases.applicable_bases(unit)
        assert set(applicable) == set(bases.BASES)
        for entry in applicable.values():
            assert entry["applies"] or entry["reason"]


def test_an_unknown_unit_is_loud():
    with pytest.raises(ValueError):
        bases.applicable_bases("families")


# --------------------------------------------------------------------------
# run_grouping — the shape-distance default (PRD Part 2)
# --------------------------------------------------------------------------

def test_shape_distance_grouping_finds_the_three_families():
    result = run_grouping(shape_items(), unit="single_motifs",
                          basis="shape-distance", method="ward",
                          params={"cut": 0.42, "min_group": 2})
    assert len(result.families) == 3
    assert result.n_assigned == 24
    assert result.n_omitted == 0
    assert sorted(f.size for f in result.families) == [8, 8, 8]


def test_every_item_comes_back_with_an_assignment():
    items = shape_items()
    result = run_grouping(items, unit="single_motifs", basis="shape-distance",
                          method="ward", params={"cut": 0.42, "min_group": 2})
    assert len(result.assignments) == len(items)
    assert [a.ref for a in result.assignments] == [i["member_ref"] for i in items]


def test_each_family_names_its_medoid_and_its_members_carry_a_distance():
    result = run_grouping(shape_items(), unit="single_motifs",
                          basis="shape-distance", method="ward",
                          params={"cut": 0.42, "min_group": 2})
    for family in result.families:
        assert family.medoid in family.members
        assert family.medoid_distance >= 0.0
    medoids = {f.medoid for f in result.families}
    for assignment in result.assignments:
        assert assignment.distance is not None
        assert assignment.is_medoid == (assignment.ref in medoids)


def test_min_group_omits_a_small_family_as_group_too_small():
    items = shape_items(per_family=8)
    rng = np.random.default_rng(3)
    # two members of a fourth, tiny shape family: the bump upside down, which
    # is anti-correlated with family one and so lands nowhere near it
    for k in range(2):
        items.append({"member_ref": 900 + k, "content_hash": f"inv{k}",
                      "values": -_bump(110 + 9 * k, rng), "fs": 1.0,
                      "tags": [], "recording_id": 9})
    result = run_grouping(items, unit="single_motifs", basis="shape-distance",
                          method="ward", params={"cut": 0.42, "min_group": 4})
    omitted = {a.ref: a.omit_reason for a in result.omitted}
    assert set(omitted) == {900, 901}
    assert set(omitted.values()) == {"group_too_small"}
    assert len(result.families) == 3


def test_omit_d_omits_a_far_outlier_as_past_cut():
    items = shape_items()
    rng = np.random.default_rng(5)
    items.append({"member_ref": 777, "content_hash": "noise",
                  "values": rng.normal(0.0, 1.0, 150), "fs": 1.0,
                  "tags": [], "recording_id": 9})
    result = run_grouping(items, unit="single_motifs", basis="shape-distance",
                          method="ward",
                          params={"cut": 0.42, "min_group": 2, "omit_d": 0.50})
    omitted = {a.ref: a.omit_reason for a in result.omitted}
    assert omitted == {777: "past_cut"}


def test_merge_heights_are_exposed_for_the_editors_histogram():
    result = run_grouping(shape_items(), unit="single_motifs",
                          basis="shape-distance", method="ward",
                          params={"cut": 0.42, "min_group": 2})
    assert len(result.merge_heights) == 23
    assert result.merge_heights == sorted(result.merge_heights)


# --------------------------------------------------------------------------
# run_grouping — feature bins and labels
# --------------------------------------------------------------------------

def test_feature_bins_group_by_amplitude_and_omit_what_is_outside():
    rng = np.random.default_rng(2)
    items = []
    for k, amp in enumerate((1.0, 1.1, 5.0, 5.2, 400.0)):
        items.append({"member_ref": k, "content_hash": f"a{k}", "fs": 1.0,
                      "values": _bump(120, rng, amp=amp)})
    result = run_grouping(items, unit="single_motifs", basis="amplitude",
                          method="feature_bins",
                          params={"bin_method": "fixed edges",
                              "range": (0.0, 3.0, 10.0), "min_group": 1})
    omitted = {a.ref: a.omit_reason for a in result.omitted}
    assert omitted == {4: "outside_bins"}
    assert len(result.families) == 2


def test_label_grouping_omits_an_unlabelled_member_as_no_label():
    items = [
        {"member_ref": 1, "tags": ["drop"]},
        {"member_ref": 2, "tags": ["drop"]},
        {"member_ref": 3, "tags": []},
    ]
    result = run_grouping(items, unit="single_motifs", basis="tag",
                          method="labels", params={"min_group": 1})
    omitted = {a.ref: a.omit_reason for a in result.omitted}
    assert omitted == {3: "no_label"}
    assert len(result.families) == 1
    assert result.families[0].label == "drop"


def test_provenance_groups_by_recording_run_or_spike_train():
    items = [
        {"member_ref": 1, "recording_id": 4, "spike_train": "t1"},
        {"member_ref": 2, "recording_id": 4, "spike_train": "t2"},
        {"member_ref": 3, "recording_id": 9, "spike_train": "t2"},
    ]
    by_recording = run_grouping(items, unit="single_motifs", basis="provenance",
                                method="labels",
                                params={"provenance_by": "recording", "min_group": 1})
    by_train = run_grouping(items, unit="single_motifs", basis="provenance",
                            method="labels",
                            params={"provenance_by": "spike_train", "min_group": 1})
    assert len(by_recording.families) == 2
    assert len(by_train.families) == 2
    assert {a.family_id for a in by_recording.assignments[:2]} == {
        by_recording.assignments[0].family_id}


# --------------------------------------------------------------------------
# run_grouping — the unit rules
# --------------------------------------------------------------------------

def test_a_motif_in_no_sequence_is_omitted_when_the_unit_is_sequences():
    items = [
        {"member_ref": 1, "sequence_id": 10, "tags": ["a"]},
        {"member_ref": 2, "sequence_id": 11, "tags": ["b"]},
        {"member_ref": 3, "tags": ["a"]},                 # belongs to no sequence
    ]
    result = run_grouping(items, unit="sequences", basis="tag", method="labels",
                          params={"min_group": 1})
    omitted = {a.ref: a.omit_reason for a in result.omitted}
    assert omitted == {3: "not_in_a_sequence"}


def test_a_basis_that_does_not_apply_to_the_unit_is_refused_with_its_reason():
    with pytest.raises(ValueError) as excinfo:
        run_grouping(shape_items(per_family=2), unit="single_motifs",
                     basis="sequence-similarity", method="ward", params={})
    assert "sequence" in str(excinfo.value).lower()


def test_a_method_that_does_not_serve_the_basis_is_refused():
    with pytest.raises(ValueError):
        run_grouping(shape_items(per_family=2), unit="single_motifs",
                     basis="shape-distance", method="labels", params={})


# --------------------------------------------------------------------------
# The recipe hash
# --------------------------------------------------------------------------

def test_the_recipe_hash_is_stable_across_runs():
    items = shape_items(per_family=3)
    params = {"cut": 0.42, "min_group": 2}
    a = run_grouping(items, unit="single_motifs", basis="shape-distance",
                     method="ward", params=params)
    b = run_grouping(items, unit="single_motifs", basis="shape-distance",
                     method="ward", params=dict(reversed(list(params.items()))))
    assert a.recipe_hash == b.recipe_hash
    assert len(a.recipe_hash) == 64


def test_the_recipe_hash_changes_when_a_parameter_changes():
    items = shape_items(per_family=3)
    a = run_grouping(items, unit="single_motifs", basis="shape-distance",
                     method="ward", params={"cut": 0.42, "min_group": 2})
    b = run_grouping(items, unit="single_motifs", basis="shape-distance",
                     method="ward", params={"cut": 0.30, "min_group": 2})
    c = run_grouping(items, unit="single_motifs", basis="tag",
                     method="labels", params={"cut": 0.42, "min_group": 2})
    assert a.recipe_hash != b.recipe_hash
    assert a.recipe_hash != c.recipe_hash


# --------------------------------------------------------------------------
# preview
# --------------------------------------------------------------------------

def test_preview_reports_groups_members_omitted_cost_and_hand_edits():
    items = shape_items()
    hand_edits = [
        {"content_hash": "h000", "kind": "add_member", "family_label": "F-01"},
        {"content_hash": "h001", "kind": "add_member", "family_label": "F-99"},
    ]
    report = preview(items, unit="single_motifs", basis="shape-distance",
                     method="ward", params={"cut": 0.42, "min_group": 2},
                     hand_edits=hand_edits)
    assert report.n_groups == 3
    assert report.n_members == 24
    assert report.n_omitted == 0
    assert report.recompute["seconds"] > 0
    assert report.recompute["where"] in ("local", "cluster")
    assert report.hand_edits["applies"] == 1
    assert report.hand_edits["orphaned"] == 1
    assert report.hand_edits["orphan_group_label"] == "F-99 additions"
    assert report.omitted_by_reason == {}


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
