"""
engine.py
===========
The grouping engine: `unit x basis x method(params) -> an assignment per
member` (`docs/LIBRARY_STORAGE.md` section 6, spec 8.2).

**The engine does not touch the database.** `run_grouping` takes plain dicts;
the bridge loads the rows and hands them over, and writes the answer back into
`groupings` / `grouping_assignments` itself. That separation is what lets the
whole engine — every method, every omission rule — be tested on synthetic
waveforms with no database anywhere near it, and it is also what keeps rule 4
honest: waveforms arrive as arrays already read off disk, and none of them
goes back.

An item is a dict. The engine reads only these keys, and only the ones the
chosen basis needs:

    member_ref / id   the row this assignment is about
    content_hash      so a hand edit can key to it across regroups (3.3)
    values            the waveform, for a distance or feature basis
    fs                sampling rate, for `timescale` and `frequency-content`
    tags              for the `tag` basis
    recording_id / run_id / spike_train     for the `provenance` basis
    cluster_label     for the `custom` basis
    sequence_id       which sequence it belongs to, if any

What does not fit (spec 8.2)
----------------------------
Eight reasons, and **every one of them flags, never deletes** — an omitted
item comes back in `assignments` with `family_id = None` and its reason, and
again in `omitted`, because the Library lists them in a strip under the atlas
with *Show omitted* and *Send omitted to Review as a queue*.

    outside_bins           outside every bin of a feature-bin basis
    past_cut               nearest family further than `omit_d` (spec 9.10: 0.50)
    group_too_small        in a group under `min_group` (spec 9.10: 10)
    not_in_a_sequence      a single motif, when the unit is `sequences`
    no_label               no label, on a label basis
    not_in_a_dense_family  HDBSCAN found no crowd of shapes this one belongs to
                           (its noise label, -1): a straggler, not a family member
    infinite_values        the waveform holds a +-inf, so it has no shape to compare
                           (HDBSCAN's -2; k-Shape screens it out the same way)
    missing_values         the waveform holds a NaN or no samples at all
                           (HDBSCAN's -3; k-Shape screens it out the same way)

The first five are spec 8.2's; the last three came with the density and
shape-based methods (w2-b).

`min_group` is applied here rather than inside each method, so the rule is
stated once and every method obeys the same one. `omit_d` belongs to the
method that has the distances, and the engine only passes it on.
"""

import os
from dataclasses import dataclass, field

from Working.library.grouping import bases
from Working.library.grouping import tree as tree_mod
from Working.library.grouping import methods as method_registry
from Working.recipes import recipe_hash

# Spec 9.10, Settings > Library groupings. Restated here (and not imported
# from `ward`) because these two apply to every method, not only to Ward.
DEFAULT_MIN_GROUP = 10
DEFAULT_OMIT_D = 0.50

# The omission reasons, as `grouping_assignments.omit_reason` spells them
# (LIBRARY_STORAGE.md 3.3): spec 8.2's five, then w2-b's three.
OMIT_OUTSIDE_BINS = "outside_bins"
OMIT_PAST_CUT = "past_cut"
OMIT_GROUP_TOO_SMALL = "group_too_small"
OMIT_NOT_IN_A_SEQUENCE = "not_in_a_sequence"
OMIT_NO_LABEL = "no_label"
# w2-b: the density method's noise, and the two rows no shape method can read.
OMIT_NOT_IN_A_DENSE_FAMILY = "not_in_a_dense_family"
OMIT_INFINITE_VALUES = "infinite_values"
OMIT_MISSING_VALUES = "missing_values"

# Recompute-cost constants. The spec gives no formula and the prototype's
# minute counts are fixtures, so these are measured-order-of-magnitude
# guesses, stated in one place and labelled as such: a distance basis is
# quadratic in the member count, a bin or a label is linear.
SECONDS_PER_PAIR = 2.0e-6
SECONDS_PER_PAIR_SEQUENCE = 2.0e-4     # sequence similarity aligns two runs
SECONDS_PER_ITEM = 5.0e-4
LOCAL_LIMIT_SECONDS = 15 * 60          # past this, the editor offers SLURM


@dataclass
class Family:
    """One group: its id, the label the method gave it, its medoid and its
    members. The exemplar is NOT here — the exemplar is the human anchor and
    lives on the entry; the medoid is what this computation produced."""
    id: int
    label: str
    members: list
    medoid: object = None
    medoid_distance: float = 0.0
    # w2-b fix round 1: did this family beat the method's surrogate null?
    # `{"noise_like", "unstable", "why", "tested"}` (+ the method's numbers);
    # a method with no null says so (`tested: False`) rather than staying silent.
    flags: dict = field(default_factory=dict)

    @property
    def size(self):
        return len(self.members)


@dataclass
class Assignment:
    """One member's place in this grouping — the row shape of
    `grouping_assignments` (LIBRARY_STORAGE.md 3.3), minus the grouping id
    the caller assigns on write."""
    ref: object
    content_hash: object = None
    family_id: object = None
    family_label: object = None
    distance: object = None
    is_medoid: bool = False
    omit_reason: object = None


@dataclass
class GroupingResult:
    """The answer to one grouping question, with everything the Library
    needs to render it and everything the bridge needs to save it."""
    unit: str
    basis: str
    method: str
    params: dict
    families: list = field(default_factory=list)
    assignments: list = field(default_factory=list)
    merge_heights: list = field(default_factory=list)
    recipe_hash: str = ""
    # w2-b fix round 1: the method's own account of the fit — which rows were
    # fitted and which assigned, the k rule and scores, the surrogate null —
    # plus `family_flags` by label. JSON-safe: it is saved as
    # `groupings.fit_summary_json`.
    fit_summary: dict = field(default_factory=dict)
    # fixup-an: the kept tree, `{"key", "path", "reused"}` (+ `"replaced"` when a
    # file under the key failed its own check and was rebuilt), or None when no
    # tree root was given or the method builds no tree
    tree: object = None
    # fixup-an: the sizes of the families `min_group` dissolved, largest first
    dissolved: list = field(default_factory=list)

    @property
    def omitted(self):
        return [a for a in self.assignments if a.family_id is None]

    @property
    def n_families(self):
        return len(self.families)

    @property
    def n_assigned(self):
        return len(self.assignments) - len(self.omitted)

    @property
    def n_omitted(self):
        return len(self.omitted)

    @property
    def omitted_by_reason(self):
        counts = {}
        for a in self.omitted:
            counts[a.omit_reason] = counts.get(a.omit_reason, 0) + 1
        return counts


@dataclass
class GroupingPreview:
    """What spec 8.2's preview-before-applying panel shows: groups, members,
    omitted, recompute cost, and what happens to hand edits."""
    n_groups: int
    n_members: int
    n_omitted: int
    omitted_by_reason: dict
    recompute: dict
    hand_edits: dict
    recipe_hash: str
    result: object = None


# --------------------------------------------------------------------------
# Reading the items
# --------------------------------------------------------------------------

def _ref(item):
    if "member_ref" in item:
        return item["member_ref"]
    if "id" in item:
        return item["id"]
    raise KeyError("An item needs a `member_ref` (or `id`) to be assigned to "
                   "a family; the assignment is written against that row.")


def _waveform(item, basis):
    """The array a distance basis clusters. For `sequence-similarity` that is
    the sequence's gap profile if the caller supplied one — the identity of a
    sequence is its ordered composition and its gaps (LIBRARY_STORAGE.md 4),
    not one waveform — and the engine will not invent it from the events."""
    if basis == "sequence-similarity" and "gap_profile" in item:
        return item["gap_profile"]
    if "values" in item:
        return item["values"]
    raise KeyError(f"Item {_ref(item)!r} carries no `values`; the "
                   f"{basis!r} basis needs the waveform.")


def _label_of(item, basis, params):
    if basis == "tag":
        tags = item.get("tags") or []
        return tags[0] if tags else None
    if basis == "provenance":
        by = params.get("provenance_by", "recording")
        field_name = {"recording": "recording_id", "run": "run_id",
                      "spike_train": "spike_train"}.get(by)
        if field_name is None:
            raise ValueError(f"provenance_by must be recording, run or "
                             f"spike_train; got {by!r}.")
        return item.get(field_name)
    if basis == "custom":
        return item.get("cluster_label")
    raise ValueError(f"{basis!r} is not a label basis.")


def _extract(items, basis, params):
    """Items -> whatever the chosen basis's method wants to fit on. Doing the
    extraction here, rather than in each method, is what keeps a method free
    of item dicts and therefore free of the Library's storage shape."""
    kind = bases.BASES[basis][0]
    if kind == "distance":
        return [_waveform(item, basis) for item in items]
    if kind == "feature-bins":
        feature = params.get("feature") or basis
        if feature not in bases.FEATURES:
            feature = basis
        return [bases.compute_feature(feature, _waveform(item, basis),
                                      fs=item.get("fs"))
                for item in items]
    return [_label_of(item, basis, params) for item in items]


# --------------------------------------------------------------------------
# run_grouping
# --------------------------------------------------------------------------

def _validate(unit, basis, method_name):
    if basis not in bases.BASES:
        raise ValueError(f"Unknown grouping basis {basis!r}. "
                         f"Spec 8.2 names: {sorted(bases.BASES)}.")
    entry = bases.applicable_bases(unit)[basis]
    if not entry["applies"]:
        raise ValueError(f"The {basis!r} basis does not apply to the "
                         f"{unit!r} unit: {entry['reason']}.")
    method = method_registry.get(method_name)
    if basis not in method.applies_to:
        raise ValueError(f"Method {method_name!r} does not serve the {basis!r} "
                         f"basis; it serves {method.applies_to}.")
    return method


class GroupingCancelled(Exception):
    """Raised by a method between its starts or null draws when the caller's
    `should_cancel()` returns true; the regroup job turns it into a cancel."""


def _accepts_cancel(method, name="should_cancel"):
    import inspect
    try:
        return name in inspect.signature(method.fit).parameters
    except (TypeError, ValueError):
        return False


def run_grouping(items, *, unit, basis, method, params=None, should_cancel=None, background=None,
                 tree_root=None):
    """Group `items` and return a `GroupingResult`.

    `should_cancel`, a no-argument callable, is handed to a method whose `fit`
    accepts it (k-Shape checks it between starts and candidate k, HDBSCAN
    between null draws); it raises `GroupingCancelled`.

    `items` are plain dicts (see the module docstring for the keys). The
    result carries one `Assignment` per input item in input order — including
    the omitted ones, which is spec 8.2's rule that what does not fit is
    flagged rather than dropped.

    `background` (w3-g), optional: a `Working.background_null.MemberBackground`
    over `items` (same order) — the caller's loader of each member's own
    recording, so the engine stays free of file paths. A method whose `fit`
    accepts it draws its quiet-stretch null from it; it is not part of the
    recipe hash (it is where the data lives, not a setting).

    `tree_root` (fixup-an), optional: a directory. For a method that builds a
    tree (`builds_tree`, Ward), the fit is kept there as one `.npz` under its
    key (`tree.tree_key`), and a later call whose members and fit settings
    hash to the same key loads it instead of fitting again — only the cut and
    the other assign-only settings are applied afresh. `result.tree` says
    which happened. Without it nothing is written, as before.
    """
    params = dict(params or {})
    method_name = method
    method = _validate(unit, basis, method_name)
    items = list(items)

    hash_of = recipe_hash({"unit": unit, "basis": basis,
                           "method": method_name, "params": params})
    result = GroupingResult(unit=unit, basis=basis, method=method_name,
                            params=params, recipe_hash=hash_of)

    # Which items take part at all. Spec 8.2: "when the unit is `sequences`,
    # every single motif that belongs to no sequence" is omitted and flagged.
    taking_part, pre_omitted = [], {}
    for index, item in enumerate(items):
        if unit == "sequences" and item.get("sequence_id") is None:
            pre_omitted[index] = OMIT_NOT_IN_A_SEQUENCE
        else:
            taking_part.append(index)

    assignments = [Assignment(ref=_ref(item),
                              content_hash=item.get("content_hash"))
                   for item in items]
    for index, reason in pre_omitted.items():
        assignments[index].omit_reason = reason

    if taking_part:
        fit = None
        keeps_tree = (tree_root is not None and bool(getattr(method, "builds_tree", False))
                      and len(taking_part) >= 2)
        replaced = None
        if keeps_tree:
            key = tree_mod.tree_key(items, unit=unit, basis=basis, method=method_name, params=params)
            path = tree_mod.path_for(tree_root, key)
            if os.path.isfile(path):
                try:
                    kept = tree_mod.GroupingTree.load(path)
                except ValueError as exc:
                    # a file under this key that fails its own check is rebuilt, and the result says so
                    replaced = str(exc)
                else:
                    # fix round: a valid tree is not enough — it must be THIS key's tree, over these items
                    if kept.key != key or len(kept.refs) != len(items) or len(kept.fit_rows) != len(taking_part):
                        replaced = (f"the file under key {key} holds the tree of key {kept.key} over "
                                    f"{len(kept.refs)} items, not these {len(items)}")
                    else:
                        fit = method.fit_from_tree(kept)
                        result.tree = {"key": key, "path": path, "reused": True}
        if fit is None:
            fit_kwargs = {"params": params}
            if should_cancel is not None and _accepts_cancel(method):
                fit_kwargs["should_cancel"] = should_cancel
            if background is not None and _accepts_cancel(method, "background"):
                fit_kwargs["background"] = background.subset(taking_part)
            fit = method.fit(_extract([items[i] for i in taking_part], basis, params), **fit_kwargs)
            if keeps_tree and "linkage" in fit.payload:
                kept = tree_mod.from_fit(fit, items, unit=unit, basis=basis, method=method_name,
                                         params=params, taking_part=taking_part, pre_omitted=pre_omitted)
                if kept.key != key:
                    raise RuntimeError(f"the tree's key from its contents ({kept.key}) is not the key its "
                                       f"items hash to ({key}); tree.tree_key and tree.from_fit disagree")
                kept.save(path)
                result.tree = {"key": key, "path": path, "reused": False}
                if replaced:
                    result.tree["replaced"] = replaced
        _assign_and_build(result, assignments, taking_part, fit, method, method_name, params)

    result.assignments = assignments
    return result


def _assign_and_build(result, assignments, taking_part, fit, method, method_name, params):
    """Cut the fit, name each row's family or why it has none, apply
    `min_group`, measure the medoids and attach the flags — the one path both a
    fresh fit and a kept tree (`assign_from_tree`) go through, which is what
    makes a preview at a grouping's own cut reproduce it exactly."""
    assign_kwargs = {"cut": params.get("cut")}
    if "omit_d" in method.params:
        # the method's own default: Ward's is spec 9.10's 0.50, k-Shape's is
        # 0 = automatic (its surrogate null), which a 0.50 here would overrule
        assign_kwargs["omit_d"] = params.get(
            "omit_d", method.params["omit_d"].get("default", DEFAULT_OMIT_D))
    families = method.assign(fit, **assign_kwargs)

    for row, index in enumerate(taking_part):
        family_id = families[row]
        assignment = assignments[index]
        if family_id is None:
            assignment.omit_reason = fit.omit_reasons.get(row, OMIT_PAST_CUT)
        else:
            assignment.family_id = family_id
            assignment.family_label = fit.family_labels.get(
                family_id, f"F-{family_id:02d}")

    result.merge_heights = list(method.merge_heights(fit))
    _build_families(result, assignments, taking_part, fit, method, params)
    _attach_flags(result, fit, method_name)


def _build_families(result, assignments, taking_part, fit, method, params):
    """Group the assigned rows into families, apply `min_group`, then name
    each family's medoid and measure every member against it.

    `min_group` is applied BEFORE the medoids are computed, so a medoid is
    never chosen for a family that is about to be dissolved.
    """
    min_group = int(params.get("min_group", DEFAULT_MIN_GROUP))
    omit_small = bool(params.get("omit_small", True))

    rows_by_family = {}
    for row, index in enumerate(taking_part):
        family_id = assignments[index].family_id
        if family_id is not None:
            rows_by_family.setdefault(family_id, []).append((row, index))

    for family_id in sorted(rows_by_family, key=_sort_key):
        rows = rows_by_family[family_id]
        if omit_small and len(rows) < min_group:
            result.dissolved.append(len(rows))
            for _, index in rows:
                assignments[index].family_id = None
                assignments[index].family_label = None
                assignments[index].omit_reason = OMIT_GROUP_TOO_SMALL
            continue

        family = Family(id=family_id,
                        label=fit.family_labels.get(family_id,
                                                    f"F-{family_id:02d}"),
                        members=[assignments[i].ref for _, i in rows])
        if fit.distances is not None and hasattr(method, "medoid"):
            medoid_row, mean_distance = method.medoid(fit, [r for r, _ in rows])
            family.medoid = assignments[taking_part[medoid_row]].ref
            family.medoid_distance = float(mean_distance)
            for row, index in rows:
                assignments[index].distance = float(
                    fit.distances[row, medoid_row])
                assignments[index].is_medoid = (row == medoid_row)
        else:
            family.medoid = family.members[0]
        result.families.append(family)
    result.dissolved.sort(reverse=True)


def untested_flags(method_name):
    """The flags of a family whose method draws no null: not noise-like, but
    explicitly not tested, so no page reads the absence as a pass."""
    return {"noise_like": False, "unstable": False, "tested": False,
            "why": f"not tested: the {method_name} method has no null to compare a family with"}


def json_safe(value):
    """numpy scalars and arrays -> plain Python, recursively; dict keys -> str;
    a NaN or an infinity -> None (JSON has neither)."""
    import numpy as np
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (float, np.floating)):
        v = float(value)
        return v if np.isfinite(v) else None
    return value


def _attach_flags(result, fit, method_name):
    """Each family's flags from the method's `payload["family_flags"]` (keyed
    by family id), and the method's `payload["fit_summary"]` on the result,
    with the surviving families' flags by label beside it."""
    by_id = fit.payload.get("family_flags") or {}
    for family in result.families:
        family.flags = json_safe(by_id.get(family.id) or untested_flags(method_name))
    summary = json_safe(fit.payload.get("fit_summary") or {})
    summary["family_flags"] = {f.label: f.flags for f in result.families}
    result.fit_summary = summary


def _sort_key(family_id):
    """Family ids are integers for every registered method, but a future
    method could name its families; sort numerically when we can and by text
    when we cannot, rather than raising on a mixed set."""
    return (0, family_id, "") if isinstance(family_id, int) \
        else (1, 0, str(family_id))


# --------------------------------------------------------------------------
# preview
# --------------------------------------------------------------------------

def _formula_seconds(n, basis):
    """The original, method-blind formula: a distance basis is quadratic in
    the member count, a bin or a label linear. Ward's `estimate` is this, and
    it is the fallback for a method that carries no `estimate`."""
    kind = bases.BASES[basis][0] if basis in bases.BASES else "distance"
    if kind == "distance":
        per_pair = (SECONDS_PER_PAIR_SEQUENCE if basis == "sequence-similarity"
                    else SECONDS_PER_PAIR)
        return n * (n - 1) / 2.0 * per_pair + n * SECONDS_PER_ITEM
    return n * SECONDS_PER_ITEM


def estimate_seconds(n, basis, method=None, params=None):
    """Seconds this grouping would take on this machine, from the method's own
    `estimate(n, params, basis=...)` when it has one (fix round 1: k-Shape and
    HDBSCAN cost nothing like n^2 x 2 us), else from the formula."""
    params = dict(params or {})
    if method is not None:
        m = method_registry.get(method) if isinstance(method, str) else method
        if hasattr(m, "estimate"):
            full = {**{k: spec["default"] for k, spec in m.params.items()}, **params}
            return float(m.estimate(int(n), full, basis=basis))
    return float(_formula_seconds(int(n), basis))


def _recompute_cost(n, basis, method=None, params=None):
    """An estimate of what applying this grouping costs, for the preview's
    `recompute` line and for the bridge's decision to run it here at all.
    `method` and `params` make it the method's own estimate; without them it
    is the original formula. Deliberately visible: the coefficients are stated
    in each method module, measured on this machine."""
    seconds = max(estimate_seconds(n, basis, method, params), 1.0e-3)
    return {"seconds": float(seconds),
            "minutes": float(seconds / 60.0),
            "where": "local" if seconds <= LOCAL_LIMIT_SECONDS else "cluster"}


def cheaper_settings(n, basis, method, params=None):
    """Settings for the same method that the estimate says would run within
    `LOCAL_LIMIT_SECONDS` — what a refusal offers instead. Each is
    `{"change": words, "params": the full params, "seconds": estimate}`,
    slowest first — the offer that gives up the least of what was asked for
    comes first. A method lists its candidates in `cheaper(n, params)`; one
    that lists none gets only a smaller-`sample` offer when it takes a
    sample."""
    params = dict(params or {})
    m = method_registry.get(method) if isinstance(method, str) else method
    candidates = list(m.cheaper(n, params)) if hasattr(m, "cheaper") else []
    if not candidates and "sample" in m.params:
        candidates = [("fit on 2,000 members, assign the rest", {"sample": 2000})]
    out = []
    for change, update in candidates:
        trial = {**params, **update}
        seconds = estimate_seconds(n, basis, m, trial)
        if seconds <= LOCAL_LIMIT_SECONDS:
            out.append({"change": change, "params": trial, "seconds": float(seconds)})
    return sorted(out, key=lambda o: -o["seconds"])


def _hand_edit_outcome(hand_edits, result):
    """Spec 8.3: a hand edit whose family still exists is re-applied; one
    pointing at a family the new grouping lacks is kept as a hand group named
    after it ("F-03 additions"). The preview counts both — which is the whole
    reason this is computed before anything is written."""
    labels = {family.label for family in result.families}
    applies, orphans = 0, []
    for edit in hand_edits or []:
        family_label = edit.get("family_label")
        if family_label in labels:
            applies += 1
        else:
            orphans.append(family_label)
    return {
        "total": len(hand_edits or []),
        "applies": applies,
        "orphaned": len(orphans),
        "orphan_group_label": f"{orphans[0]} additions" if orphans else None,
        "orphan_labels": orphans,
    }


def preview(items, *, unit, basis, method, params=None, hand_edits=None, should_cancel=None, background=None,
            tree_root=None):
    """Run the grouping without writing anything, and report what spec 8.2's
    preview panel shows: groups, members, omitted, recompute cost, and what
    happens to hand edits. The `GroupingResult` travels on the preview so the
    caller that decides to apply does not have to recompute it."""
    result = run_grouping(items, unit=unit, basis=basis, method=method,
                          params=params, should_cancel=should_cancel, background=background,
                          tree_root=tree_root)
    return GroupingPreview(
        n_groups=result.n_families,
        n_members=result.n_assigned,
        n_omitted=result.n_omitted,
        omitted_by_reason=result.omitted_by_reason,
        recompute=_recompute_cost(len(result.assignments), basis, method, params),
        hand_edits=_hand_edit_outcome(hand_edits, result),
        recipe_hash=result.recipe_hash,
        result=result,
    )


# --------------------------------------------------------------------------
# fixup-an: a cut previewed from a kept tree
# --------------------------------------------------------------------------

#: How a family's sample members are chosen for its card (the researcher, 2026-10-13: "sample families at each cut").
SAMPLE_RULE = ("the medoid first, then members spread evenly along the family's distances from its medoid — "
               "nearest to farthest — so a card shows the family's range, not only its most typical members")

#: How "moved" is counted against the current grouping.
CHANGE_RULE = ("each family at this cut is matched to the current family holding most of its members; a member "
               "whose current family is another one has moved. A family that splits in two moves nobody "
               "(both halves match the old family), so the family count beside it says what split or merged.")

DEFAULT_SAMPLES = 6


def assign_from_tree(tree, cut, params=None, fit=None):
    """The grouping a kept tree gives at `cut`, through the same assign and
    family-building path as `run_grouping` — so at the grouping's own cut and
    settings it reproduces that grouping row for row. Nothing is refitted:
    `fit` is the method's `fit_from_tree(tree)`, rebuilt here when not given
    (the bridge holds it between calls). `params` are the assign-only settings
    (min_group, omit_d, omit_small); `cut` wins over a `cut` in them."""
    params = {**dict(params or {}), "cut": float(cut)}
    method = _validate(tree.unit, tree.basis, tree.method)
    if fit is None:
        fit = method.fit_from_tree(tree)
    full = {**tree.fit_params, **params}
    result = GroupingResult(unit=tree.unit, basis=tree.basis, method=tree.method, params=full,
                            recipe_hash=recipe_hash({"unit": tree.unit, "basis": tree.basis,
                                                     "method": tree.method, "params": full}))
    assignments = [Assignment(ref=r, content_hash=h)
                   for r, h in zip(tree.refs.tolist(), tree.content_hashes.tolist())]
    for index, reason in enumerate(tree.pre_omit.tolist()):
        if reason:
            assignments[index].omit_reason = reason
    _assign_and_build(result, assignments, [int(i) for i in tree.fit_rows], fit, method, tree.method, full)
    result.assignments = assignments
    result.tree = {"key": tree.key, "path": None, "reused": True}
    return result


def _samples(family, by_ref, n):
    members = [m for m in family.members if m != family.medoid]
    members.sort(key=lambda r: (by_ref[r].distance if by_ref[r].distance is not None else float("inf"), str(r)))
    ordered = [family.medoid] + members
    if len(ordered) <= n:
        return ordered
    import numpy as np
    idx = sorted(set(int(round(v)) for v in np.linspace(0, len(ordered) - 1, n)))
    return [ordered[i] for i in idx]


def _change(result, current):
    """Members that moved against `current` (`{ref: family label or None}`), by `CHANGE_RULE`."""
    now = {a.ref: a.family_label for a in result.assignments}
    moved = 0
    for family in result.families:
        was = [current.get(r) for r in family.members if current.get(r) is not None]
        if was:
            best = max(sorted(set(was)), key=was.count)
            moved += sum(1 for w in was if w != best)
    newly_omitted = sum(1 for r, lab in now.items() if lab is None and current.get(r) is not None)
    newly_assigned = sum(1 for r, lab in now.items() if lab is not None and current.get(r) is None)
    current_families = len({lab for lab in current.values() if lab is not None})
    return {"moved": int(moved), "newly_omitted": int(newly_omitted), "newly_assigned": int(newly_assigned),
            "current_families": int(current_families),
            "same_families": bool(moved == 0 and newly_omitted == 0 and newly_assigned == 0
                                  and current_families == len(result.families)),
            "rule": CHANGE_RULE}


def cut_preview(tree, cut, params=None, current=None, samples=DEFAULT_SAMPLES, fit=None):
    """What the families would be at `cut`, read from a kept tree in
    milliseconds: each family's size, medoid and a few sample members (by
    `SAMPLE_RULE`), what `min_group` dissolves, the omissions by reason, and —
    when `current` (`{ref: family label or None}`) is given — how many members
    move against it. JSON-safe."""
    params = dict(params or {})
    result = assign_from_tree(tree, cut, params, fit=fit)
    by_ref = {a.ref: a for a in result.assignments}
    n = max(1, int(samples))
    min_group = int(result.params.get("min_group", DEFAULT_MIN_GROUP))
    omit_small = bool(result.params.get("omit_small", True))
    return json_safe({
        "cut": float(cut),
        "method": tree.method, "basis": tree.basis, "unit": tree.unit, "key": tree.key,
        "n_items": len(result.assignments),
        "n_families": result.n_families, "n_assigned": result.n_assigned, "n_omitted": result.n_omitted,
        "omitted_by_reason": result.omitted_by_reason,
        "small_families": {"count": len(result.dissolved), "members": int(sum(result.dissolved)),
                           "sizes": list(result.dissolved), "min_group": min_group, "omit_small": omit_small},
        "families": [{"id": f.id, "label": f.label, "size": f.size, "medoid": f.medoid,
                      "medoid_distance": f.medoid_distance, "samples": _samples(f, by_ref, n),
                      "flags": f.flags} for f in result.families],
        "sample_rule": SAMPLE_RULE,
        "change": _change(result, dict(current)) if current is not None else None,
    })
