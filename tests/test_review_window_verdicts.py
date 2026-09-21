"""
test_review_window_verdicts.py
==============================
Tests for `Working/review/window_verdicts.py` (stage-3 wiring, fog A13).

A training/verification window is neither a machine detection nor a span a
human drew: it is one index into a saved `window_sets` row. It therefore has
no `detections` row to adjudicate and no human-chosen extent to annotate, and
writing a window verdict into either of those tables would be precisely the
crossing CLAUDE.md rule 5 forbids. The whole justification for the
`window_verdicts` table is that separation, so the first test here asserts it
directly: writing a window verdict leaves `detections`, `adjudications` and
`annotations` untouched.

Run from the project root:
    python -m pytest tests/test_review_window_verdicts.py -q
"""

import datetime
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
from Working.review import window_verdicts as wv


# ---------------------------------------------------------------- fixtures --

@pytest.fixture()
def conn():
    c = init_db(":memory:")
    yield c
    c.close()


def _window_set(conn, name="ws", version=1, n_windows=10):
    cur = conn.execute(
        "INSERT INTO window_sets (name, version, path, n_windows, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, version, f"DATA/derived/{name}_v{version}.npz", n_windows,
         datetime.datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    return cur.lastrowid


def _counts_of_the_other_tables(conn):
    return {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("detections", "adjudications", "annotations")
    }


# ------------------------------------------------------------------ rule 5 --

def test_window_verdict_touches_no_machine_or_human_table(conn):
    """Rule 5, the window case: a window verdict is its own kind of row."""
    ws = _window_set(conn)
    before = _counts_of_the_other_tables(conn)

    wv.write_window_verdict(conn, ws, 3, "interesting")

    assert _counts_of_the_other_tables(conn) == before
    assert conn.execute("SELECT COUNT(*) FROM window_verdicts").fetchone()[0] == 1


# ------------------------------------------------------------------- write --

def test_write_returns_row_id_and_stores_every_field(conn):
    ws = _window_set(conn)
    rid = wv.write_window_verdict(conn, ws, 0, "seed", note="clear burst")
    assert isinstance(rid, int) and rid > 0

    got = wv.get_window_verdict(conn, ws, 0)
    assert got["id"] == rid
    assert got["window_set_id"] == ws
    assert got["window_index"] == 0
    assert got["verdict"] == "seed"
    assert got["note"] == "clear burst"
    assert got["queue_id"] is None
    assert got["created_at"]


def test_queue_id_is_recorded_when_given(conn):
    ws = _window_set(conn)
    qid = conn.execute(
        "INSERT INTO review_queues (name, source_kind, unit, writes_to, blind, "
        "created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("windows", "training-windows", "window", "window_verdicts", 1,
         datetime.datetime.now().isoformat(timespec="seconds")),
    ).lastrowid
    conn.commit()

    wv.write_window_verdict(conn, ws, 1, "unsure", queue_id=qid)
    assert wv.get_window_verdict(conn, ws, 1)["queue_id"] == qid


def test_reverdict_is_an_upsert_not_a_second_row(conn):
    """UNIQUE (window_set_id, window_index): changing your mind edits the row."""
    ws = _window_set(conn)
    first = wv.write_window_verdict(conn, ws, 4, "interesting", note="maybe")
    second = wv.write_window_verdict(conn, ws, 4, "artifact", note="mains hum")

    assert second == first
    rows = conn.execute(
        "SELECT * FROM window_verdicts WHERE window_set_id = ? AND window_index = ?",
        (ws, 4),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["verdict"] == "artifact"
    assert rows[0]["note"] == "mains hum"


def test_reverdict_without_a_note_clears_the_old_note(conn):
    """The row means "the current verdict"; a stale note is not part of it."""
    ws = _window_set(conn)
    wv.write_window_verdict(conn, ws, 2, "interesting", note="looks real")
    wv.write_window_verdict(conn, ws, 2, "not_interesting")
    assert wv.get_window_verdict(conn, ws, 2)["note"] is None


def test_same_index_in_two_sets_are_different_rows(conn):
    ws_a = _window_set(conn, name="a")
    ws_b = _window_set(conn, name="b")
    wv.write_window_verdict(conn, ws_a, 0, "seed")
    wv.write_window_verdict(conn, ws_b, 0, "artifact")

    assert wv.get_window_verdict(conn, ws_a, 0)["verdict"] == "seed"
    assert wv.get_window_verdict(conn, ws_b, 0)["verdict"] == "artifact"
    assert conn.execute("SELECT COUNT(*) FROM window_verdicts").fetchone()[0] == 2


def test_unknown_window_set_raises_rather_than_orphaning(conn):
    with pytest.raises(sqlite3.IntegrityError):
        wv.write_window_verdict(conn, 999999, 0, "seed")
    assert conn.execute("SELECT COUNT(*) FROM window_verdicts").fetchone()[0] == 0


def test_unknown_verdict_is_refused(conn):
    ws = _window_set(conn)
    with pytest.raises(ValueError):
        wv.write_window_verdict(conn, ws, 0, "probably")
    assert conn.execute("SELECT COUNT(*) FROM window_verdicts").fetchone()[0] == 0


def test_negative_window_index_is_refused(conn):
    ws = _window_set(conn)
    with pytest.raises(ValueError):
        wv.write_window_verdict(conn, ws, -1, "seed")


def test_every_contract_verdict_is_accepted(conn):
    ws = _window_set(conn)
    assert wv.VERDICTS == ("seed", "interesting", "not_interesting",
                           "artifact", "unsure")
    for i, verdict in enumerate(wv.VERDICTS):
        wv.write_window_verdict(conn, ws, i, verdict)
    assert wv.window_verdict_counts(conn, ws)["judged"] == len(wv.VERDICTS)


# --------------------------------------------------------------------- get --

def test_get_returns_none_when_unjudged(conn):
    ws = _window_set(conn)
    assert wv.get_window_verdict(conn, ws, 7) is None
    assert wv.get_window_verdict(conn, 999999, 0) is None


# ------------------------------------------------------------------ delete --

def test_delete_removes_the_row_and_reports_it(conn):
    ws = _window_set(conn)
    wv.write_window_verdict(conn, ws, 5, "seed")
    assert wv.delete_window_verdict(conn, ws, 5) is True
    assert wv.get_window_verdict(conn, ws, 5) is None


def test_delete_of_nothing_returns_false(conn):
    """Undo has to be able to tell a reversal from a no-op."""
    ws = _window_set(conn)
    assert wv.delete_window_verdict(conn, ws, 5) is False
    wv.write_window_verdict(conn, ws, 5, "seed")
    assert wv.delete_window_verdict(conn, ws, 5) is True
    assert wv.delete_window_verdict(conn, ws, 5) is False


def test_delete_leaves_the_other_sets_alone(conn):
    ws_a = _window_set(conn, name="a")
    ws_b = _window_set(conn, name="b")
    wv.write_window_verdict(conn, ws_a, 0, "seed")
    wv.write_window_verdict(conn, ws_b, 0, "seed")
    wv.delete_window_verdict(conn, ws_a, 0)
    assert wv.get_window_verdict(conn, ws_b, 0) is not None


# ------------------------------------------------------------------ counts --

def test_counts_are_empty_for_an_unjudged_set(conn):
    ws = _window_set(conn)
    assert wv.window_verdict_counts(conn, ws) == {"judged": 0, "by_verdict": {}}


def test_counts_group_by_verdict(conn):
    ws = _window_set(conn)
    wv.write_window_verdict(conn, ws, 0, "seed")
    wv.write_window_verdict(conn, ws, 1, "seed")
    wv.write_window_verdict(conn, ws, 2, "artifact")

    counts = wv.window_verdict_counts(conn, ws)
    assert counts["judged"] == 3
    assert counts["by_verdict"] == {"seed": 2, "artifact": 1}


def test_counts_follow_upsert_and_delete(conn):
    ws = _window_set(conn)
    wv.write_window_verdict(conn, ws, 0, "seed")
    wv.write_window_verdict(conn, ws, 0, "artifact")
    assert wv.window_verdict_counts(conn, ws) == {
        "judged": 1, "by_verdict": {"artifact": 1}}

    wv.delete_window_verdict(conn, ws, 0)
    assert wv.window_verdict_counts(conn, ws) == {"judged": 0, "by_verdict": {}}


def test_counts_are_scoped_to_one_set(conn):
    ws_a = _window_set(conn, name="a")
    ws_b = _window_set(conn, name="b")
    wv.write_window_verdict(conn, ws_a, 0, "seed")
    wv.write_window_verdict(conn, ws_b, 0, "seed")
    wv.write_window_verdict(conn, ws_b, 1, "unsure")

    assert wv.window_verdict_counts(conn, ws_a)["judged"] == 1
    assert wv.window_verdict_counts(conn, ws_b)["judged"] == 2


# ------------------------------------------------------ no UI in the core --

def test_module_imports_no_ui_library():
    src = open(os.path.join(PROJECT_ROOT, "Working", "review",
                            "window_verdicts.py"), encoding="utf-8").read()
    for banned in ("panel", "holoviews", "bokeh", "fastapi"):
        assert banned not in src.lower()


# ------------------------------------------- what a reviewer would ask for --

def test_rewriting_the_same_verdict_is_idempotent(conn):
    """Double-tapping the key is not a second judgement."""
    ws = _window_set(conn)
    first = wv.write_window_verdict(conn, ws, 0, "seed", note="n")
    again = wv.write_window_verdict(conn, ws, 0, "seed", note="n")
    assert again == first
    assert wv.window_verdict_counts(conn, ws) == {
        "judged": 1, "by_verdict": {"seed": 1}}


def test_works_on_a_connection_without_a_row_factory(tmp_path):
    """The bridge may hand us a plain sqlite3 connection; dicts are ours to
    build, not the caller's to have configured."""
    db = str(tmp_path / "wv.sqlite")
    init_db(db).close()
    plain = sqlite3.connect(db)          # no row_factory, FKs default off
    plain.execute("PRAGMA foreign_keys = ON")
    try:
        ws = _window_set(plain)
        rid = wv.write_window_verdict(plain, ws, 0, "seed", note="n")
        got = wv.get_window_verdict(plain, ws, 0)
        assert isinstance(got, dict) and got["id"] == rid
        assert got["verdict"] == "seed"
        assert wv.window_verdict_counts(plain, ws) == {
            "judged": 1, "by_verdict": {"seed": 1}}
        assert wv.delete_window_verdict(plain, ws, 0) is True
    finally:
        plain.close()
