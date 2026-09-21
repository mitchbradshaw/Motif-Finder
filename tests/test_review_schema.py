"""The three tables stage-3 Prompt 05 adds for the Review workspace.

`review_queues` is the one place every queue kind can be named from, so the
Jobs page's queue group and the header's "N need you" are a single read rather
than five source-specific ones. `window_verdicts` exists because a training or
verification window is neither a detection nor a span a person drew: it has no
`detections` row to adjudicate and no human-chosen extent to annotate, so
writing its verdict into either table would be exactly the crossing CLAUDE.md
rule 5 forbids. `review_audit` is what makes undo a replayable fact instead of
client state, and what lets a batch action be one audit row covering N writes.

These assertions are about the *shape* of the migration — that it is additive,
idempotent, and constrains what it promises to constrain. The behaviour that
uses it is tested in `test_review_queues.py`, `test_review_verdicts.py`,
`test_review_promotion.py` and `test_review_window_verdicts.py`.
"""
import os
import sqlite3
import tempfile

import pytest

from Working.database import schema

REVIEW_TABLES = ("review_queues", "window_verdicts", "review_audit")


@pytest.fixture
def db_path():
    with tempfile.TemporaryDirectory() as d:
        yield os.path.join(d, "annotations.sqlite")


@pytest.fixture
def conn(db_path):
    c = schema.init_db(db_path)
    yield c
    c.close()


def _tables(conn):
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}


def _window_set(conn):
    """A minimal `window_sets` row — the four NOT NULL columns and nothing else."""
    cur = conn.execute(
        "INSERT INTO window_sets (name, version, path, created_at)"
        " VALUES ('ws', 1, 'MATRICES/ws.npz', 't')")
    return int(cur.lastrowid)


def _columns(conn, table):
    return {r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)}


def test_init_db_creates_the_three_review_tables(conn):
    assert REVIEW_TABLES[0] in _tables(conn)
    assert REVIEW_TABLES[1] in _tables(conn)
    assert REVIEW_TABLES[2] in _tables(conn)


def test_init_db_is_still_idempotent(db_path):
    """Rule 3: schema changes are additive and applied through an `init_db()`
    that stays idempotent. A second call must not raise and must not duplicate."""
    first = schema.init_db(db_path)
    before = _tables(first)
    first.close()
    second = schema.init_db(db_path)
    assert _tables(second) == before
    second.close()


def test_review_queues_names_its_source_kind_unit_and_write_target(conn):
    cols = _columns(conn, "review_queues")
    for expected in ("name", "source_kind", "source_ref", "unit", "writes_to",
                     "blind", "cap", "verdict_options", "filters_json",
                     "created_at", "closed_at"):
        assert expected in cols, expected


@pytest.mark.parametrize("kind", [
    "discovery-run", "seed-search", "explore-spans",
    "training-windows", "model-verification", "extract-events",
])
def test_review_queues_accepts_each_of_the_six_source_kinds(conn, kind):
    """Spec 10.1's five kinds plus Library's `extract events` (Prompt 03)."""
    conn.execute(
        "INSERT INTO review_queues (name, source_kind, unit, writes_to, created_at)"
        " VALUES (?, ?, 'detection', 'adjudications', 't')", ("q", kind))


def test_review_queues_refuses_an_invented_source_kind(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO review_queues (name, source_kind, unit, writes_to, created_at)"
            " VALUES ('q', 'telepathy', 'detection', 'adjudications', 't')")


def test_review_queues_write_target_is_constrained_to_the_verdict_tables(conn):
    """`writes_to` is the rule-5 decision made once, where a person can read it.
    A queue that claimed to write `detections` would be a machine-table write
    dressed as a verdict, so the CHECK refuses it at the storage layer."""
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO review_queues (name, source_kind, unit, writes_to, created_at)"
            " VALUES ('q', 'discovery-run', 'detection', 'detections', 't')")


def test_a_window_verdict_is_one_row_per_window_not_one_per_keypress(conn):
    """UNIQUE (window_set_id, window_index): re-judging a window is an upsert.
    Without it a reviewer who changed their mind would leave two contradictory
    verdicts on the same window and no rule for which one counts."""
    ws = _window_set(conn)
    conn.execute(
        "INSERT INTO window_verdicts (window_set_id, window_index, verdict, created_at)"
        " VALUES (?, 0, 'interesting', 't')", (ws,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO window_verdicts (window_set_id, window_index, verdict, created_at)"
            " VALUES (?, 0, 'artifact', 't')", (ws,))


def test_a_window_verdict_cannot_be_orphaned_from_its_window_set(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO window_verdicts (window_set_id, window_index, verdict, created_at)"
            " VALUES (999999, 0, 'interesting', 't')")


def test_review_audit_can_carry_many_targets_under_one_row(conn):
    """A batch action is one audit row covering N writes, not N rows: undoing a
    batch is one act, and an audit log that cannot say so cannot reverse it."""
    conn.execute(
        "INSERT INTO review_audit (action, target_table, target_ids, payload_json, created_at)"
        " VALUES ('batch', 'adjudications', '[1,2,3]', '{}', 't')")
    row = conn.execute(
        "SELECT target_ids, undone_at FROM review_audit").fetchone()
    assert row[0] == "[1,2,3]"
    assert row[1] is None


def test_the_migration_touches_no_existing_table(conn):
    """Additive means additive: the tables Prompt 05 adds are new ones, and the
    tables the rest of the app depends on are still there with their columns."""
    tables = _tables(conn)
    for untouched in ("detections", "annotations", "adjudications", "runs",
                      "motif_entry", "motif_member", "sequences", "window_sets"):
        assert untouched in tables, untouched
    assert "detection_id" in _columns(conn, "adjudications")
    assert "parent_annotation_id" in _columns(conn, "annotations")
