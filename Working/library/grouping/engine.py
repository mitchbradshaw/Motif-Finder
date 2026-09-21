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
Five reasons, and **every one of them flags, never deletes** — an omitted
item comes back in `assignments` with `family_id = None` and its reason, and
again in `omitted`, because the Library lists them in a strip under the atlas
with *Show omitted* and *Send omitted to Review as a queue*.

    outside_bins        outside every bin of a feature-bin basis
    past_cut            nearest family further than `omit_d` (spec 9.10: 0.50)
    group_too_small     in a group under `min_group` (spec 9.10: 10)
    not_in_a_sequence   a single motif, when the unit is `sequences`
    no_label            no label, on a label basis

`min_group` is applied here rather than inside each method, so the rule is
stated once and every method obeys the same one. `omit_d` belongs to the
method that has the distances, and the engine only passes it on.
"""

from dataclasses import dataclass, field

from Working.library.grouping import bases
from Working.library.grouping import methods as method_registry
from Working.recipes import recipe_hash

# Spec 9.10, Settings > Library groupings. Restated here (and not imported
# from `ward`) because these two apply to every method, not only to Ward.
DEFAULT_MIN_GROUP = 10
DEFAULT_OMIT_D = 0.50

# The five omission reasons of spec 8.2, as `grouping_assignments.omit_reason`
# spells them (LIBRARY_STORAGE.md 3.3).
OMIT_OUTSIDE_BINS = "outside_bins"
OMIT_PAST_CUT = "past_cut"
OMIT_GROUP_TOO_SMALL = "group_too_small"
OMIT_NOT_IN_A_SEQUENCE = "not_in_a_sequence"
OMIT_NO_LABEL = "no_label"

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


def run_grouping(items, *, unit, basis, method, params=None):
    """Group `items` and return a `GroupingResult`.

    `items` are plain dicts (see the module docstring for the keys). The
    result carries one `Assignment` per input item in input order — including
    the omitted ones, which is spec 8.2's rule that what does not fit is
    flagged rather than dropped.
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
        fit = method.fit(_extract([items[i] for i in taking_part], basis, params),
                         params=params)
        assign_kwargs = {"cut": params.get("cut")}
        if "omit_d" in method.params:
            assign_kwargs["omit_d"] = params.get("omit_d", DEFAULT_OMIT_D)
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

    result.assignments = assignments
    return result


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


def _sort_key(family_id):
    """Family ids are integers for every registered method, but a future
    method could name its families; sort numerically when we can and by text
    when we cannot, rather than raising on a mixed set."""
    return (0, family_id, "") if isinstance(family_id, int) \
        else (1, 0, str(family_id))


# --------------------------------------------------------------------------
# preview
# --------------------------------------------------------------------------

def _recompute_cost(n, basis):
    """An estimate of what applying this grouping costs, for the preview's
    `recompute` line and for the editor's decision to offer a cluster script
    instead of running it locally. Deliberately crude and deliberately
    visible: the spec gives no cost model, so this one is stated here rather
    than hidden behind a fixture."""
    kind = bases.BASES[basis][0]
    if kind == "distance":
        per_pair = (SECONDS_PER_PAIR_SEQUENCE if basis == "sequence-similarity"
                    else SECONDS_PER_PAIR)
        seconds = n * (n - 1) / 2.0 * per_pair + n * SECONDS_PER_ITEM
    else:
        seconds = n * SECONDS_PER_ITEM
    seconds = max(seconds, 1.0e-3)
    return {"seconds": float(seconds),
            "minutes": float(seconds / 60.0),
            "where": "local" if seconds <= LOCAL_LIMIT_SECONDS else "cluster"}


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


def preview(items, *, unit, basis, method, params=None, hand_edits=None):
    """Run the grouping without writing anything, and report what spec 8.2's
    preview panel shows: groups, members, omitted, recompute cost, and what
    happens to hand edits. The `GroupingResult` travels on the preview so the
    caller that decides to apply does not have to recompute it."""
    result = run_grouping(items, unit=unit, basis=basis, method=method,
                          params=params)
    return GroupingPreview(
        n_groups=result.n_families,
        n_members=result.n_assigned,
        n_omitted=result.n_omitted,
        omitted_by_reason=result.omitted_by_reason,
        recompute=_recompute_cost(len(result.assignments), basis),
        hand_edits=_hand_edit_outcome(hand_edits, result),
        recipe_hash=result.recipe_hash,
        result=result,
    )
