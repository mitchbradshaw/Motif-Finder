"""
test_legacy_detections_migration.py
===================================
Fixup M — the one-time migration of legacy span-relative `detections` rows.

A `detections` row written by a **spanned** run before 2026-09-21 was stored
span-relative (the executor added no offset) while every reader treats the
table as channel-absolute. `Working.discovery.spans.absolute_bounds` is the
rule three readers apply on the way out — a row whose `start_idx` lies below
its run's `span_start` is shifted by `span_start`. A fourth reader (Review)
was missed, which is what a latent data-format inconsistency does. The
migration rewrites the rows once, so the rule becomes a no-op on this
database, and it refuses the two cases where the rule cannot be trusted:

* **ambiguous** — `span_length > span_start`, so a relative index could land
  at or above `span_start` and be indistinguishable from an absolute one;
* **mixed** — some rows below `span_start` and some at or above it, so the
  heuristic is wrong about that run.

The migration runs inside `init_db()`, so the tests exercise it the way the
application does — by re-opening a scratch database — as well as through the
plan/apply functions directly. The fixture uses raw SQL for the rows so it
keeps testing pre-existing data regardless of which helper writes today.
"""

import json
import os
import sqlite3
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database.schema import init_db, migrate_legacy_detections, plan_legacy_detections
from Working.database import queries as q
from Working.discovery.scoreboard import _detections as scoreboard_detections
from Working.discovery.spans import absolute_bounds


# ----------------------------------------------------------------- fixture --

def _scratch_db():
    d = tempfile.mkdtemp(prefix="legacy_det_")
    return os.path.join(d, "annotations.sqlite")


def _open_without_migrating(path):
    """A plain connection, so a test can hold the pre-migration state that
    init_db() would otherwise rewrite on open."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _recording(conn, n=2_000_000):
    return q.insert_recording(conn, "fixture.mat", 0, 1.0, n, 0, "fixture_CH0.npy")


def _run(conn, recording_id, span_start, span_end):
    config_id = conn.execute(
        "INSERT INTO configs (config_hash, config_json, created_at) VALUES (?, ?, ?)",
        ("cfg-%d-%d" % (span_start, span_end), "{}", "2026-08-01T00:00:00")).lastrowid
    run_id = conn.execute(
        "INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (config_id, recording_id, span_start, span_end, "2026-08-01T00:00:00", "completed")).lastrowid
    conn.commit()
    return run_id


def _detection(conn, run_id, start, end, score=None):
    rid = conn.execute(
        "INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, ?)",
        (run_id, start, end, score)).lastrowid
    conn.commit()
    return rid


def _raw(conn, det_id):
    r = conn.execute("SELECT start_idx, end_idx FROM detections WHERE id = ?", (det_id,)).fetchone()
    return int(r["start_idx"]), int(r["end_idx"])


def _fixture():
    """A scratch database holding one of everything the migration must
    distinguish. Returns (path, ids)."""
    path = _scratch_db()
    conn = init_db(path)
    rec = _recording(conn)
    ids = {}
    # A legacy spanned run: span [1_209_600, 1_216_800), 7 200 long, rows relative.
    ids["legacy_run"] = _run(conn, rec, 1_209_600, 1_216_800)
    ids["legacy_a"] = _detection(conn, ids["legacy_run"], 2_468, 2_540, 1.5)
    ids["legacy_b"] = _detection(conn, ids["legacy_run"], 0, 7_200)          # whole span, start 0
    # A spanned run written after the executor fix: rows already absolute.
    ids["absolute_run"] = _run(conn, rec, 1_627_200, 1_641_600)
    ids["absolute_a"] = _detection(conn, ids["absolute_run"], 1_629_961, 1_630_100)
    # A whole-channel run: span_start = 0, rows are absolute by definition.
    ids["whole_run"] = _run(conn, rec, 0, 2_000_000)
    ids["whole_a"] = _detection(conn, ids["whole_run"], 3_266, 3_332)
    conn.close()
    return path, ids


# ------------------------------------------------------------ the refusals --

def test_an_ambiguous_run_is_refused_and_reported():
    """span_length > span_start: a relative index could land above span_start,
    so no row of that run can be told apart. Nothing is rewritten."""
    path = _scratch_db()
    conn = init_db(path)
    rec = _recording(conn)
    run = _run(conn, rec, 5_000, 100_000)            # length 95 000 > span_start 5 000
    det = _detection(conn, run, 100, 200)             # looks legacy, but cannot be trusted
    plan = plan_legacy_detections(conn)
    assert [r["run_id"] for r in plan["refused"]] == [run]
    assert plan["refused"][0]["reason"] == "ambiguous"
    assert plan["runs"] == []
    assert plan["n_rows"] == 0
    result = migrate_legacy_detections(conn)
    assert result["n_rows"] == 0
    assert _raw(conn, det) == (100, 200)
    assert [r["run_id"] for r in result["refused"]] == [run]
    conn.close()


def test_a_mixed_run_is_refused_and_reported():
    """Some rows below span_start and some at or above it: the heuristic is
    wrong about that run, so it is left exactly as it is."""
    path = _scratch_db()
    conn = init_db(path)
    rec = _recording(conn)
    run = _run(conn, rec, 1_209_600, 1_216_800)
    low = _detection(conn, run, 2_468, 2_540)
    high = _detection(conn, run, 1_210_000, 1_210_100)
    plan = plan_legacy_detections(conn)
    assert [r["run_id"] for r in plan["refused"]] == [run]
    assert plan["refused"][0]["reason"] == "mixed"
    assert plan["refused"][0]["n_legacy"] == 1 and plan["refused"][0]["n"] == 2
    result = migrate_legacy_detections(conn)
    assert result["n_rows"] == 0
    assert _raw(conn, low) == (2_468, 2_540)
    assert _raw(conn, high) == (1_210_000, 1_210_100)
    conn.close()


# ------------------------------------------------------------- the rewrite --

def test_the_plan_names_each_run_its_span_start_and_its_row_ids():
    path, ids = _fixture()
    conn = _open_without_migrating(path)
    plan = plan_legacy_detections(conn)
    assert plan["refused"] == []
    assert plan["n_rows"] == 2
    assert len(plan["runs"]) == 1
    r = plan["runs"][0]
    assert r["run_id"] == ids["legacy_run"]
    assert r["span_start"] == 1_209_600 and r["span_end"] == 1_216_800
    assert r["n"] == 2 and r["n_legacy"] == 2
    assert sorted(r["ids"]) == sorted([ids["legacy_a"], ids["legacy_b"]])
    conn.close()


def test_a_legacy_row_is_rewritten_to_start_plus_span_start():
    path, ids = _fixture()
    conn = _open_without_migrating(path)
    result = migrate_legacy_detections(conn)
    assert result["n_rows"] == 2
    assert _raw(conn, ids["legacy_a"]) == (2_468 + 1_209_600, 2_540 + 1_209_600)
    assert _raw(conn, ids["legacy_b"]) == (1_209_600, 1_216_800)
    conn.close()


def test_a_row_already_absolute_is_untouched():
    path, ids = _fixture()
    conn = _open_without_migrating(path)
    migrate_legacy_detections(conn)
    assert _raw(conn, ids["absolute_a"]) == (1_629_961, 1_630_100)
    conn.close()


def test_a_whole_channel_run_is_untouched():
    path, ids = _fixture()
    conn = _open_without_migrating(path)
    migrate_legacy_detections(conn)
    assert _raw(conn, ids["whole_a"]) == (3_266, 3_332)
    conn.close()


def test_a_second_pass_rewrites_nothing():
    """Idempotence: after the rewrite every row has start_idx >= span_start,
    so the plan is empty and a second pass reports zero rows."""
    path, ids = _fixture()
    conn = _open_without_migrating(path)
    first = migrate_legacy_detections(conn)
    assert first["n_rows"] == 2
    after_first = {k: _raw(conn, ids[k]) for k in ("legacy_a", "legacy_b", "absolute_a", "whole_a")}
    second = migrate_legacy_detections(conn)
    assert second["n_rows"] == 0 and second["runs"] == [] and second["refused"] == []
    assert {k: _raw(conn, ids[k]) for k in after_first} == after_first
    assert plan_legacy_detections(conn)["n_rows"] == 0
    conn.close()


def test_init_db_applies_it_on_reopen_and_only_once():
    """The application path: the migration runs inside init_db(), so simply
    re-opening the database rewrites the legacy rows; opening it again writes
    nothing more (one audit row, not two)."""
    path, ids = _fixture()
    conn = init_db(path)
    assert _raw(conn, ids["legacy_a"]) == (2_468 + 1_209_600, 2_540 + 1_209_600)
    assert _raw(conn, ids["absolute_a"]) == (1_629_961, 1_630_100)
    assert _raw(conn, ids["whole_a"]) == (3_266, 3_332)
    n_audit = conn.execute("SELECT COUNT(*) FROM audit_log WHERE kind = 'migration'").fetchone()[0]
    conn.close()
    conn = init_db(path)
    assert _raw(conn, ids["legacy_a"]) == (2_468 + 1_209_600, 2_540 + 1_209_600)
    assert conn.execute("SELECT COUNT(*) FROM audit_log WHERE kind = 'migration'").fetchone()[0] == n_audit == 1
    conn.close()


# ------------------------------------------------------------- the record --

def test_the_rewrite_is_recorded_in_the_audit_log():
    """A person in six months can see which rows were rewritten and by what
    rule: one `audit_log` row naming each run, its span_start, the row ids and
    the count."""
    path, ids = _fixture()
    conn = _open_without_migrating(path)
    migrate_legacy_detections(conn)
    rows = conn.execute("SELECT * FROM audit_log WHERE kind = 'migration'").fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert "2" in row["what"] and "span-relative" in row["what"]
    detail = json.loads(row["detail_json"])
    assert detail["n_rows"] == 2
    assert detail["rule"].startswith("start_idx < span_start")
    assert len(detail["runs"]) == 1
    r = detail["runs"][0]
    assert r["run_id"] == ids["legacy_run"] and r["span_start"] == 1_209_600
    assert r["n"] == 2 and sorted(r["ids"]) == sorted([ids["legacy_a"], ids["legacy_b"]])
    conn.close()


def test_a_refusal_alone_writes_no_audit_row():
    path = _scratch_db()
    conn = init_db(path)
    rec = _recording(conn)
    run = _run(conn, rec, 1_209_600, 1_216_800)
    _detection(conn, run, 2_468, 2_540)
    _detection(conn, run, 1_210_000, 1_210_100)
    migrate_legacy_detections(conn)
    assert conn.execute("SELECT COUNT(*) FROM audit_log WHERE kind = 'migration'").fetchone()[0] == 0
    conn.close()


# ----------------------------------------------------------- the round trip --

def test_round_trip_through_the_scoreboard_reader():
    """The migration and `absolute_bounds` agree: the reader's answer is the
    same before and after, the raw row was wrong before and is right after,
    and the reader is a no-op on the migrated row."""
    path, ids = _fixture()
    conn = _open_without_migrating(path)
    run = ids["legacy_run"]
    before_reader = scoreboard_detections(conn, run, 1_209_600)
    before_raw = _raw(conn, ids["legacy_a"])
    expect = (2_468 + 1_209_600, 2_540 + 1_209_600)
    by_id = {d["id"]: (d["start"], d["end"]) for d in before_reader}
    assert by_id[ids["legacy_a"]] == expect            # the reader shifted it
    assert before_raw != expect                          # the row itself was wrong
    migrate_legacy_detections(conn)
    after_reader = scoreboard_detections(conn, run, 1_209_600)
    after_raw = _raw(conn, ids["legacy_a"])
    assert after_raw == expect                           # the row is right now
    assert {d["id"]: (d["start"], d["end"]) for d in after_reader} == by_id
    assert absolute_bounds(after_raw[0], after_raw[1], 1_209_600) == after_raw   # rule is a no-op
    conn.close()
