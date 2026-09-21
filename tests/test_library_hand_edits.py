"""
test_library_hand_edits.py
==========================
`docs/LIBRARY_STORAGE.md` §3.3 `hand_edits` and spec §8.3 — the researcher's
decisions, and why a re-clustering does not throw them away.

    "Hand edits are stored apart from the computed grouping and re-applied on
    top of each one. A member removed by hand stays out of that family on
    every regroup until restored. An edit pointing at a family the new
    grouping lacks is kept as a hand group."

The single design decision this file exists to pin: **an edit is keyed by
content hash, not by member id.** A member id is an accident of when a row was
written — a re-import renumbers them — so an id-keyed edit would evaporate on
exactly the operation it is supposed to survive.

The central test is `test_edits_survive_a_regroup`: build one assignment, apply
the edits, then build a *different* assignment the way a re-clustering would,
apply the same edits, and assert the removal is still out and the addition
still in.

`apply_to_assignment` is pure — plain dicts in, plain dicts out, no connection
— which is what lets the grouping engine and the web bridge share one copy of
the rule, and lets this file test it without a database at all.
"""

import os
import sqlite3
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database.schema import init_db
from Working.library.hand_edits import (
    active_edits,
    apply_to_assignment,
    edits_for,
    record,
    undo,
)


@pytest.fixture()
def conn(tmp_path):
    db = tmp_path / "hand_edits.sqlite"
    init_db(str(db))
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    yield c
    c.close()


# ── the store ────────────────────────────────────────────────────────────────

def test_an_edit_is_keyed_by_content_hash(conn):
    edit_id = record(conn, content_hash="aaaa", kind="add_member",
                     family_label="F-03", actor="this installation")
    row = conn.execute("SELECT * FROM hand_edits WHERE id = ?", (edit_id,)).fetchone()
    assert row["content_hash"] == "aaaa"
    assert row["kind"] == "add_member"
    assert row["family_label"] == "F-03"
    assert row["active"] == 1
    assert row["created_at"]


def test_an_unknown_kind_is_refused(conn):
    with pytest.raises(ValueError):
        record(conn, content_hash="aaaa", kind="delete_member")


def test_undo_deactivates_rather_than_deletes(conn):
    """A removal that is restored stays on the record — §8.6 draws a
    'removed by hand' strip with Restore, which needs the row to still be
    there."""
    edit_id = record(conn, content_hash="aaaa", kind="remove_member",
                     family_label="F-03")
    undo(conn, edit_id)
    row = conn.execute("SELECT * FROM hand_edits WHERE id = ?", (edit_id,)).fetchone()
    assert row is not None
    assert row["active"] == 0
    assert edits_for(conn, "aaaa") == []


def test_edits_for_and_active_edits_scope_by_grouping(conn):
    record(conn, content_hash="aaaa", kind="tag", value="oyster")
    record(conn, content_hash="bbbb", kind="class", value="drop",
           grouping_id=None)
    assert len(edits_for(conn, "aaaa")) == 1
    assert len(active_edits(conn)) == 2
    # a global edit (grouping_id IS NULL) applies to every grouping
    assert len(active_edits(conn, grouping_id=7)) == 2


# ── the pure rule ────────────────────────────────────────────────────────────

def _assignment(content_hash, family_label, member_ref=None):
    return {"content_hash": content_hash, "family_label": family_label,
            "member_ref": member_ref, "unit": "single_motifs"}


def _edit(content_hash, kind, family_label=None, value=None):
    return {"content_hash": content_hash, "kind": kind,
            "family_label": family_label, "value": value}


def test_an_added_member_joins_its_family():
    """An omitted member (no family) put into a family that this grouping
    does have."""
    result = apply_to_assignment(
        [_assignment("aaaa", None), _assignment("dddd", "F-03")],
        [_edit("aaaa", "add_member", family_label="F-03")],
    )
    row = result["assignments"][0]
    assert row["family_label"] == "F-03"
    assert row["hand"] is True
    assert result["orphans"] == []


def test_a_removed_member_leaves_the_family_but_stays_listed():
    """§8.2: omitted entries are flagged, never deleted."""
    result = apply_to_assignment(
        [_assignment("aaaa", "F-03")],
        [_edit("aaaa", "remove_member", family_label="F-03")],
    )
    row = result["assignments"][0]
    assert row["family_label"] is None
    assert row["removed_by_hand"] is True
    assert row["omit_reason"] == "removed_by_hand"


def test_make_exemplar_marks_one_member():
    result = apply_to_assignment(
        [_assignment("aaaa", "F-03"), _assignment("bbbb", "F-03")],
        [_edit("bbbb", "make_exemplar", family_label="F-03")],
    )
    by_hash = {r["content_hash"]: r for r in result["assignments"]}
    assert by_hash["bbbb"]["is_exemplar"] is True
    assert by_hash["aaaa"].get("is_exemplar", False) is False


def test_tags_and_classes_attach():
    result = apply_to_assignment(
        [_assignment("aaaa", "F-03")],
        [_edit("aaaa", "tag", value="oyster"),
         _edit("aaaa", "tag", value="morphology:sharp"),
         _edit("aaaa", "class", value="drop")],
    )
    row = result["assignments"][0]
    assert row["tags"] == ["oyster", "morphology:sharp"]
    assert row["class_label"] == "drop"


def test_the_input_assignments_are_not_mutated():
    """Pure means pure: the engine keeps its computed answer intact so the
    preview can count the computed and the hand-edited side by side (§8.2)."""
    assignments = [_assignment("aaaa", "F-03")]
    apply_to_assignment(assignments, [_edit("aaaa", "remove_member",
                                            family_label="F-03")])
    assert assignments[0]["family_label"] == "F-03"


def test_edits_survive_a_regroup():
    """The property the whole module exists for.

    Two different groupings of the same three shapes — as a re-clustering at a
    new cut would produce — carry the same hand edits, because the edits are
    keyed on the shapes and not on the grouping's rows.
    """
    edits = [_edit("bbbb", "remove_member", family_label="F-03"),
             _edit("cccc", "add_member", family_label="F-03")]

    first = [_assignment("aaaa", "F-03", member_ref=1),
             _assignment("bbbb", "F-03", member_ref=2),
             _assignment("cccc", None, member_ref=3)]
    # the regroup: different member ids, one member moved family, same shapes
    second = [_assignment("aaaa", "F-03", member_ref=91),
              _assignment("bbbb", "F-03", member_ref=92),
              _assignment("cccc", "F-07", member_ref=93)]

    for assignments in (first, second):
        out = {r["content_hash"]: r for r in
               apply_to_assignment(assignments, edits)["assignments"]}
        assert out["bbbb"]["family_label"] is None, "the removal did not survive"
        assert out["bbbb"]["removed_by_hand"] is True
        assert out["cccc"]["family_label"] == "F-03", "the addition did not survive"
        assert out["aaaa"]["family_label"] == "F-03"


def test_an_edit_for_a_family_this_grouping_lacks_becomes_a_hand_group():
    """Spec §8.3's named case: 'F-03 additions'."""
    result = apply_to_assignment(
        [_assignment("aaaa", "F-11")],
        [_edit("zzzz", "add_member", family_label="F-03")],
    )
    assert len(result["orphans"]) == 1
    orphan = result["orphans"][0]
    assert orphan["family_label"] == "F-03"
    assert orphan["hand_group_label"] == "F-03 additions"
    assert orphan["content_hashes"] == ["zzzz"]
    # and it did not quietly land in the computed grouping
    assert [r["content_hash"] for r in result["assignments"]] == ["aaaa"]


def test_the_preview_counts_both_sides():
    """§8.2: 'Preview before applying' shows what happens to hand edits, so
    the counts must come back with the result rather than be recomputed by
    each caller."""
    result = apply_to_assignment(
        [_assignment("aaaa", "F-03"), _assignment("bbbb", "F-03")],
        [_edit("bbbb", "remove_member", family_label="F-03"),
         _edit("zzzz", "add_member", family_label="F-99")],
    )
    assert result["counts"]["applied"] == 1
    assert result["counts"]["orphaned"] == 1


def test_the_store_and_the_rule_meet(conn):
    """`active_edits` rows go straight into `apply_to_assignment` — the two
    halves of the module are one flow, not two shapes that need adapting."""
    record(conn, content_hash="bbbb", kind="remove_member", family_label="F-03")
    result = apply_to_assignment(
        [_assignment("aaaa", "F-03"), _assignment("bbbb", "F-03")],
        active_edits(conn),
    )
    by_hash = {r["content_hash"]: r for r in result["assignments"]}
    assert by_hash["bbbb"]["family_label"] is None
