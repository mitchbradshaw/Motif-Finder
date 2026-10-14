"""
test_null_draws_completed.py
============================
W3-F fix round 2 (re-critique finding 1, decision 27): ONE rule for "a completed null draw", read by every reader.

A paired-null draw stopped part-way (a cancel, W3-F's in-step cancel) is linked to its run (so its spans never read as
real), but it is not a draw of the null: it ran part of the chain. Before this fix `run_groups.null_summary` counted
completed draws only while the Discovery scoreboard, the Library's scale read-out and family null and the export
counted every linked row — on the critic's case the Analyse toolbar read "2 draws, null expects 34.5" and the
scoreboard "3 draws, 30.33" for the same run. Pinned here, on that case (a real run with 82 spans; draws of 13 and
56 spans completed; a third stopped with 22):

* `queries.completed_null_draw(alias)` is the one SQL statement of the rule;
* `null_summary` and `scoreboard.channel_score` agree: 2 draws, 34.5;
* `matching.scale_readout`'s `nullDraws` / `nullPerDraw` count completed draws only;
* `library._family_null` (FastAPI module: skipped under conda) counts completed draws only;
* `export._surrogate_block` prefers a completed draw, and with only a stopped one says so instead of naming it the
  surrogate control.

Runs under the conda pytest (the family-null test skips without FastAPI).
"""
import os
import sys
import tempfile

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui"), os.path.dirname(os.path.abspath(__file__))):
    if p not in sys.path:
        sys.path.insert(0, p)

from Working.database import queries as q  # noqa: E402
from Working.database import runs as run_db  # noqa: E402
from Working.database.schema import init_db  # noqa: E402

REAL, DONE_A, DONE_B, STOPPED = 82, 13, 56, 22


def _critic_case(conn):
    rec = q.insert_recording(conn, "fixture.mat", 0, 1.0, 100_000, 0, "fixture_CH0.npy")
    cfg, _ = run_db.get_or_create_config(conn, {"steps": [{"stage": "detection", "algorithm": "threshold", "params": {}}]})
    sur_cfg, _ = run_db.get_or_create_config(conn, {"steps": [
        {"stage": "preprocessing", "algorithm": "surrogate", "params": {"method": "phase_randomize", "seed": 0}},
        {"stage": "detection", "algorithm": "threshold", "params": {}}]})

    def run(n, status, cfg_id, surrogate_of=None):
        rid = run_db.insert_run(conn, cfg_id, rec, 0, 100_000, status=status, started_at="2026-09-20T00:00:00")
        for i in range(n):
            run_db.insert_detection(conn, rid, 100 + i * 1000, 150 + i * 1000)
        if surrogate_of is not None:
            run_db.update_run(conn, rid, surrogate_of_run_id=surrogate_of)
        return rid
    real = run(REAL, "completed", cfg)
    a = run(DONE_A, "completed", sur_cfg, real)
    b = run(DONE_B, "completed", sur_cfg, real)
    stopped = run(STOPPED, "failed", sur_cfg, real)
    run_db.update_run(conn, stopped, error_text="Cancelled: Cycle shapes cancelled.")
    return rec, real, (a, b), stopped


def test_the_rule_is_one_sql_statement_beside_not_surrogate():
    assert hasattr(q, "completed_null_draw"), "no shared rule for a completed null draw"
    clause = q.completed_null_draw("r")
    assert "r.surrogate_of_run_id IS NOT NULL" in clause and "r.status = 'completed'" in clause


def test_null_summary_and_the_scoreboard_agree_on_the_same_run():
    from Working.discovery.scoreboard import channel_score
    from Working.run_groups import null_summary
    conn = init_db(":memory:")
    try:
        _rec, real, _done, _stopped = _critic_case(conn)
        ns = null_summary(conn, real)
        row = channel_score(conn, real)
        assert ns["null_draws"] == 2 and ns["null_expects"] == pytest.approx(34.5)
        assert row["null_draws"] == 2, f"the scoreboard counted the stopped draw: {row['null_draws']} draws"
        assert row["null_expects"] == pytest.approx(34.5), row["null_expects"]
        assert row["null_expects"] == pytest.approx(ns["null_expects"])
    finally:
        conn.close()


def test_the_library_scale_readout_counts_completed_draws_only():
    from Working.library import matching
    import test_library_seed_edges as seed
    with tempfile.TemporaryDirectory() as tmp:
        lib = seed.Lib(tmp)
        lib.resolve()
        run_db.update_run(lib.conn, lib.nulls[1], status="failed", error_text="Cancelled: stopped part-way")
        out = matching.scale_readout(lib.conn, lib.entry, [lib.run, lib.run1])
        rows = {r["scale"]: r for r in out["rows"]}
        assert out["nullDraws"] == 1, "a stopped draw was counted as a draw of the null"
        # only nulls[0] is a draw now: one span at 1.25x and one at 0.8x over ONE draw
        assert rows[1.25]["nullPerDraw"] == pytest.approx(1.0)
        assert rows[0.8]["nullPerDraw"] == pytest.approx(1.0)


def test_the_family_null_counts_completed_draws_only():
    pytest.importorskip("fastapi", reason="server.library imports FastAPI (webui/.venv)")
    from server import library as lib_routes
    import test_library_seed_edges as seed
    with tempfile.TemporaryDirectory() as tmp:
        lib = seed.Lib(tmp)
        lib.resolve()
        ids = [int(r["id"]) for r in lib.members()]
        before = lib_routes._family_null(lib.conn, ids)
        run_db.update_run(lib.conn, lib.nulls[1], status="failed", error_text="Cancelled: stopped part-way")
        after = lib_routes._family_null(lib.conn, ids)
        assert after["drawsTotal"] == before["drawsTotal"] - 1
        assert after["draws"] == 1
        assert after["nullDetections"] == before["nullDetections"] - 1     # nulls[1] held one span


def test_the_export_prefers_a_completed_draw():
    from Working import export
    conn = init_db(":memory:")
    try:
        rec = q.insert_recording(conn, "f.mat", 0, 1.0, 1000, 0, "f.npy")
        cfg, _ = run_db.get_or_create_config(conn, {"steps": []})
        real = run_db.insert_run(conn, cfg, rec, 0, 1000, status="completed")
        # the stopped draw has the LOWEST id: the one `ORDER BY id LIMIT 1` used to pick
        part = run_db.insert_run(conn, cfg, rec, 0, 1000, status="failed")
        run_db.update_run(conn, part, surrogate_of_run_id=real, error_text="Cancelled: stopped")
        done = run_db.insert_run(conn, cfg, rec, 0, 1000, status="completed")
        run_db.update_run(conn, done, surrogate_of_run_id=real)
        block = export._surrogate_block(conn, run_db.get_run(conn, real))
        assert block["run_id"] == done and block["status"] == "completed"
    finally:
        conn.close()


def test_an_export_with_only_a_stopped_draw_says_so():
    from Working import export
    conn = init_db(":memory:")
    try:
        rec = q.insert_recording(conn, "f.mat", 0, 1.0, 1000, 0, "f.npy")
        cfg, _ = run_db.get_or_create_config(conn, {"steps": []})
        real = run_db.insert_run(conn, cfg, rec, 0, 1000, status="completed")
        part = run_db.insert_run(conn, cfg, rec, 0, 1000, status="failed")
        run_db.insert_detection(conn, part, 1, 5)
        run_db.update_run(conn, part, surrogate_of_run_id=real, error_text="Cancelled: stopped")
        block = export._surrogate_block(conn, run_db.get_run(conn, real))
        assert block is not None, "a stopped draw exists: the export must say so, not print null"
        assert block["run_id"] is None, "a stopped draw is named as the surrogate control"
        assert block["completed"] is False and part in block["stopped_run_ids"]
        assert "stopped" in block["note"]
    finally:
        conn.close()
