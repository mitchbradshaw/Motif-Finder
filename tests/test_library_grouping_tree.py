"""
test_library_grouping_tree.py
===============================
fixup-an (AN-1): the Ward tree of a Library grouping is kept on disk, a cut is
previewed from the kept tree, and a second apply with the same members and fit
settings reuses the stored fit instead of building a second linkage.

What these pin, and why each could fail:

* the tree file exists after a Ward regroup, carries its key, and refuses to
  load when its contents no longer match that key (a silently swapped file
  would preview someone else's families);
* `cut_preview` at the grouping's own cut reproduces every assignment exactly
  (label, omission and its reason, medoid, distance) — on a set that includes
  coloured noise, so the past_cut and group_too_small rules are exercised, not
  only the easy three clean families;
* at another cut it matches a fresh `run_grouping` at that cut and Ward's own
  `assign` on a fresh fit;
* a second run whose members and fit settings are unchanged reuses the tree:
  `ward_linkage` is not called again, and the answer is identical to a fresh fit;
* a changed waveform or a changed fit setting (`resample_length`) is a new key;
  an assign-only setting (cut, omit_d, min_group) is not;
* a feature-bin grouping writes no tree;
* the preview counts the members that move against a current grouping, what
  `min_group` dissolves, and carries a handful of sample refs per family.

Pure numpy/scipy and a tmp directory: no database, no DATA/.
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

from Working.library.grouping import engine
from Working.library.grouping import tree as tree_mod
from Working.library.grouping.methods import ward as ward_mod


# --------------------------------------------------------------------------
# items: three clean shape families plus coloured noise (a random walk and an
# AR(1) background), so the omission rules have something to omit
# --------------------------------------------------------------------------

def _bump(n, rng):
    t = np.linspace(-3.0, 3.0, n)
    return np.exp(-t ** 2) + rng.normal(0.0, 0.03, n)


def _ramp(n, rng):
    return np.linspace(0.0, 1.0, n) + rng.normal(0.0, 0.03, n)


def _wave(n, rng):
    t = np.linspace(0.0, 4.0 * np.pi, n)
    return np.sin(t) + rng.normal(0.0, 0.03, n)


def _walk(n, rng):
    x = np.cumsum(rng.normal(0.0, 1.0, n))
    return x - np.linspace(x[0], x[-1], n)


def _ar1(n, rng, phi=0.97):
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + rng.normal()
    return x


def items(per_family=12, n_noise=10, seed=7):
    rng = np.random.default_rng(seed)
    out = []
    for fam, maker in enumerate((_bump, _ramp, _wave)):
        for k in range(per_family):
            out.append({"member_ref": 1000 * (fam + 1) + k, "content_hash": f"h{fam}-{k}",
                        "values": maker(80 + 7 * k, rng), "fs": 1.0})
    for k in range(n_noise):
        maker = _walk if k % 2 else _ar1
        out.append({"member_ref": 9000 + k, "content_hash": f"noise-{k}",
                    "values": maker(120 + 5 * k, rng), "fs": 1.0})
    return out


WARD = dict(unit="single_motifs", basis="shape-distance", method="ward")


def _rows(result):
    return [(a.ref, a.family_label, a.omit_reason, bool(a.is_medoid),
             None if a.distance is None else round(float(a.distance), 12))
            for a in result.assignments]


# --------------------------------------------------------------------------
# persisted
# --------------------------------------------------------------------------

def test_a_ward_regroup_writes_its_tree_with_its_key(tmp_path):
    its = items()
    result = engine.run_grouping(its, **WARD, params={"cut": 0.6, "min_group": 3}, tree_root=str(tmp_path))
    assert result.tree is not None, "a Ward regroup handed a tree root keeps its tree"
    path, key = result.tree["path"], result.tree["key"]
    assert result.tree["reused"] is False
    assert os.path.isfile(path) and path.endswith(".npz")
    assert os.path.dirname(os.path.abspath(path)) == os.path.abspath(str(tmp_path))
    t = tree_mod.GroupingTree.load(path)
    assert t.key == key
    n = len(its)
    assert t.linkage.shape == (n - 1, 4)
    assert sorted(int(r) for r in t.refs) == sorted(i["member_ref"] for i in its)
    # the leaf order is a permutation of the fitted rows, and the refs in leaf order are the dendrogram's leaves
    assert sorted(t.leaf_order.tolist()) == list(range(n))
    assert [int(r) for r in t.refs_in_leaf_order()] == [int(t.refs[t.fit_rows[i]]) for i in t.leaf_order]
    # the params minus the cut are what the fit was made with; the cut is not part of the tree
    assert "cut" not in t.fit_params
    assert t.method == "ward" and t.basis == "shape-distance"


def test_a_tree_whose_contents_do_not_match_its_key_is_refused(tmp_path):
    result = engine.run_grouping(items(), **WARD, params={"cut": 0.6}, tree_root=str(tmp_path))
    t = tree_mod.GroupingTree.load(result.tree["path"])
    t.refs = t.refs[::-1].copy()                 # someone else's member order under this key
    bad = os.path.join(str(tmp_path), "tampered.npz")
    t.save(bad)
    with pytest.raises(ValueError, match="key"):
        tree_mod.GroupingTree.load(bad)


def test_feature_bins_and_label_groupings_write_no_tree(tmp_path):
    its = items()
    r = engine.run_grouping(its, unit="single_motifs", basis="amplitude", method="feature_bins",
                            params={"count": 3}, tree_root=str(tmp_path))
    assert r.tree is None
    assert not [f for f in os.listdir(str(tmp_path)) if f.endswith(".npz")]


def test_without_a_tree_root_nothing_is_written(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = engine.run_grouping(items(), **WARD, params={"cut": 0.6})
    assert r.tree is None
    assert not os.listdir(str(tmp_path))


# --------------------------------------------------------------------------
# the cut preview reads the tree
# --------------------------------------------------------------------------

@pytest.mark.parametrize("params", [{"cut": 0.6, "min_group": 3},
                                    {"cut": 0.42},                      # the defaults: min_group 10, omit_d 0.5
                                    {"cut": 0.9, "min_group": 5, "omit_d": 0.35}])
def test_the_preview_at_the_groupings_own_cut_reproduces_it_exactly(tmp_path, params):
    its = items()
    made = engine.run_grouping(its, **WARD, params=params, tree_root=str(tmp_path))
    t = tree_mod.GroupingTree.load(made.tree["path"])
    again = engine.assign_from_tree(t, params["cut"], params)
    assert _rows(again) == _rows(made)
    assert [(f.label, f.size, f.medoid) for f in again.families] == \
           [(f.label, f.size, f.medoid) for f in made.families]
    # the set exercises the omission rules, so "exactly" covers them too
    assert made.n_omitted > 0


@pytest.mark.parametrize("other_cut", [0.3, 0.75, 1.4])
def test_the_preview_at_another_cut_matches_a_fresh_run_and_wards_assign(tmp_path, other_cut):
    its = items()
    base = {"cut": 0.6, "min_group": 2, "omit_d": 0.5}
    made = engine.run_grouping(its, **WARD, params=base, tree_root=str(tmp_path))
    t = tree_mod.GroupingTree.load(made.tree["path"])
    moved = {**base, "cut": other_cut}
    from_tree = engine.assign_from_tree(t, other_cut, moved)
    fresh = engine.run_grouping(its, **WARD, params=moved)
    assert _rows(from_tree) == _rows(fresh)
    # and Ward's own assign on a fresh fit, as a partition of the rows
    method = ward_mod.WardMethod()
    fit = method.fit([i["values"] for i in its], params={})
    raw = method.assign(fit, cut=other_cut, omit_d=0.5)
    # rows Ward assigned (before min_group): the preview's assigned + group_too_small rows
    kept = {a.ref for a in from_tree.assignments if a.omit_reason != "past_cut"}
    assert kept == {its[r]["member_ref"] for r, f in enumerate(raw) if f is not None}
    assert from_tree.n_families >= 1


def test_cut_preview_counts_moves_small_groups_and_carries_sample_refs(tmp_path):
    its = items()
    base = {"cut": 0.6, "min_group": 3}
    made = engine.run_grouping(its, **WARD, params=base, tree_root=str(tmp_path))
    t = tree_mod.GroupingTree.load(made.tree["path"])
    current = {a.ref: a.family_label for a in made.assignments}

    same = engine.cut_preview(t, 0.6, base, current=current, samples=5)
    assert same["n_families"] == made.n_families
    assert same["change"]["moved"] == 0 and same["change"]["newly_omitted"] == 0 \
        and same["change"]["newly_assigned"] == 0
    assert same["change"]["same_families"] is True

    low = engine.cut_preview(t, 0.2, {**base, "min_group": 4}, current=current, samples=5)
    assert low["n_families"] != made.n_families or low["change"]["moved"] > 0 \
        or low["n_omitted"] != made.n_omitted
    # brute-force the move count with the stated rule
    new = {a.ref: a.family_label for a in engine.assign_from_tree(t, 0.2, {**base, "min_group": 4}).assignments}
    fams = {}
    for ref, lab in new.items():
        if lab is not None:
            fams.setdefault(lab, []).append(ref)
    moved = 0
    for lab, refs in fams.items():
        was = [current[r] for r in refs if current.get(r) is not None]
        if was:
            best = max(sorted(set(was)), key=was.count)
            moved += sum(1 for w in was if w != best)
    assert low["change"]["moved"] == moved
    assert low["change"]["newly_omitted"] == sum(1 for r in new if new[r] is None and current.get(r) is not None)
    # what min_group dissolved is said, with its own numbers
    small = low["small_families"]
    assert small["min_group"] == 4
    assert small["members"] == low["omitted_by_reason"].get("group_too_small", 0)
    # every family carries its medoid first and a handful of its own members
    for fam in low["families"]:
        assert 1 <= len(fam["samples"]) <= 5
        assert fam["samples"][0] == fam["medoid"]
        assert set(fam["samples"]) <= set(fams[fam["label"]])
        assert len(set(fam["samples"])) == len(fam["samples"])
        assert fam["flags"]["tested"] is False, "Ward draws no null; the preview says so"
    assert low["sample_rule"]


def test_cut_preview_without_a_current_grouping_has_no_change_line(tmp_path):
    made = engine.run_grouping(items(), **WARD, params={"cut": 0.6, "min_group": 2}, tree_root=str(tmp_path))
    t = tree_mod.GroupingTree.load(made.tree["path"])
    out = engine.cut_preview(t, 0.6, {"min_group": 2})
    assert out["change"] is None
    assert out["n_families"] == made.n_families


def test_the_dendrogram_payload_draws_the_kept_tree(tmp_path):
    its = items()
    made = engine.run_grouping(its, **WARD, params={"cut": 0.6}, tree_root=str(tmp_path))
    t = tree_mod.GroupingTree.load(made.tree["path"])
    d = tree_mod.dendrogram(t, leaves=20)
    assert len(d["icoord"]) == len(d["dcoord"]) == len(d["leaves"]) - 1
    assert sum(d["counts"]) == len(its)
    # every merge height, high to low, so a cut line can snap to any number of families
    assert len(d["heights"]) == len(its) - 1
    assert d["heights"] == sorted(d["heights"], reverse=True)
    assert d["max_height"] == pytest.approx(float(t.linkage[:, 2].max()))
    assert d["n_leaves"] == len(its)


# --------------------------------------------------------------------------
# reuse — "use cached existing cuts"
# --------------------------------------------------------------------------

def test_a_second_apply_with_the_same_members_reuses_the_tree(tmp_path, monkeypatch):
    its = items()
    first = engine.run_grouping(its, **WARD, params={"cut": 0.6, "min_group": 3}, tree_root=str(tmp_path))
    calls = []
    real = ward_mod.ward_linkage
    monkeypatch.setattr(ward_mod, "ward_linkage", lambda c: (calls.append(1), real(c))[1])
    # another cut, another omit_d, another min_group: all applied after the fit
    params = {"cut": 0.8, "min_group": 2, "omit_d": 0.45}
    second = engine.run_grouping(its, **WARD, params=params, tree_root=str(tmp_path))
    assert not calls, "no second linkage is built when the members and fit settings are unchanged"
    assert second.tree["reused"] is True
    assert second.tree["key"] == first.tree["key"] and second.tree["path"] == first.tree["path"]
    monkeypatch.setattr(ward_mod, "ward_linkage", real)
    fresh = engine.run_grouping(its, **WARD, params=params)
    assert _rows(second) == _rows(fresh)
    assert second.recipe_hash == fresh.recipe_hash


def test_a_changed_member_or_fit_setting_is_a_new_tree(tmp_path):
    its = items()
    first = engine.run_grouping(its, **WARD, params={"cut": 0.6}, tree_root=str(tmp_path))
    changed = [dict(i) for i in its]
    changed[0]["values"] = np.asarray(changed[0]["values"]) * -1.0
    second = engine.run_grouping(changed, **WARD, params={"cut": 0.6}, tree_root=str(tmp_path))
    assert second.tree["reused"] is False and second.tree["key"] != first.tree["key"]
    fewer = engine.run_grouping(its[:-1], **WARD, params={"cut": 0.6}, tree_root=str(tmp_path))
    assert fewer.tree["key"] not in (first.tree["key"], second.tree["key"])
    resampled = engine.run_grouping(its, **WARD, params={"cut": 0.6, "resample_length": 128},
                                    tree_root=str(tmp_path))
    assert resampled.tree["reused"] is False and resampled.tree["key"] != first.tree["key"]
    # assign-only settings share a key
    k1 = tree_mod.tree_key(its, **WARD, params={"cut": 0.1, "omit_d": 0.2, "min_group": 4, "omit_small": False})
    k2 = tree_mod.tree_key(its, **WARD, params={"cut": 0.9})
    assert k1 == k2 == first.tree["key"]


def test_preview_carries_the_tree_through(tmp_path):
    p = engine.preview(items(), **WARD, params={"cut": 0.6}, tree_root=str(tmp_path))
    assert p.result.tree and os.path.isfile(p.result.tree["path"])
