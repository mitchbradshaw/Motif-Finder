"""
test_tq_mapcache.py
===================
tq-mapcache (2026-10-25), the core half. Three copies of one WAL-snapshot block (`coverage_map.fingerprinted`,
`detection_map.compute`, `detection_map.compute_level`) become one `coverage_map.snapshot_read(conn, digest, compute)`;
`compute_level`'s string-and-dict protocol (a bridge cache key in the core's signature) goes, and the map's views are
read through `detection_map.compute(db_path, exclude, view, *args, **kw)` with the view function passed as itself;
the dead `PRAGMA table_info(discovery_runs)` guards (`init_db` guarantees `removed_at`) are gone.

Pure core, conda interpreter. The bridge half is `tests/test_webui_tq_mapcache.py`.
"""
import inspect
import os
import sqlite3
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(PROJECT_ROOT, "tests")
for p in (PROJECT_ROOT, TESTS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import perf_fixture  # noqa: E402
from Working.discovery import coverage_map as CM  # noqa: E402
from Working.discovery import detection_map as DM  # noqa: E402

SMALL = dict(n_channels=3, hours=24.0, n_druns=4, n_detections=6_000, n_annotations=200, n_templates=3,
             queue_size=50, n_adjudications=10, n_reviewed=20, write_npy=False)


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    return perf_fixture.build(str(tmp_path_factory.mktemp("tqmap") / "map.sqlite"), **SMALL)


def _conn(path):
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    return c


def test_snapshot_read_on_wal_reads_both_inside_one_transaction(tmp_path):
    path = str(tmp_path / "wal.sqlite")
    c = sqlite3.connect(path)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE t (x)")
    c.execute("INSERT INTO t VALUES (1)")
    c.commit()
    seen = []

    def digest(conn):
        seen.append(("digest", conn.in_transaction))
        return str(conn.execute("SELECT SUM(x) FROM t").fetchone()[0])

    def compute(conn):
        seen.append(("compute", conn.in_transaction))
        return {"sum": conn.execute("SELECT SUM(x) FROM t").fetchone()[0]}
    try:
        fp, out = CM.snapshot_read(c, digest, compute)
        assert (fp, out) == ("1", {"sum": 1})
        assert seen == [("digest", True), ("compute", True)], "one snapshot: both in the read transaction"
        assert not c.in_transaction
    finally:
        c.close()


def test_snapshot_read_off_wal_drops_the_fingerprint_when_the_database_moved(tmp_path):
    path = str(tmp_path / "del.sqlite")
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE t (x)")
    c.execute("INSERT INTO t VALUES (1)")
    c.commit()
    other = sqlite3.connect(path)

    def digest(conn):
        return str(conn.execute("SELECT SUM(x) FROM t").fetchone()[0])

    def compute(conn):
        other.execute("INSERT INTO t VALUES (2)")      # a writer lands while the map is computed
        other.commit()
        return "computed"
    try:
        assert CM.snapshot_read(c, digest, compute) == (None, "computed")
        assert CM.snapshot_read(c, digest, lambda conn: "again") == ("3", "again")
    finally:
        other.close()
        c.close()


def test_compute_reads_any_view_with_the_overview_fingerprint(db):
    c = _conn(db["db"])
    try:
        want2 = DM.channel_map(c, perf_fixture.SOURCE_FILE, chunks=4)
        ch = want2["channels"][0]["name"]
        want1 = DM.timeline_map(c, perf_fixture.SOURCE_FILE, ch, bin_h=3.0)
        want_fp = DM.overview_fingerprint(c, ())
    finally:
        c.close()
    fp2, got2 = DM.compute(db["db"], (), DM.channel_map, perf_fixture.SOURCE_FILE, chunks=4)
    fp1, got1 = DM.compute(db["db"], (), DM.timeline_map, perf_fixture.SOURCE_FILE, channel=ch, bin_h=3.0)
    assert got2 == want2 and got1 == want1
    assert fp2 == fp1 == want_fp == DM.compute(db["db"], ())[0]


def test_one_snapshot_block_and_no_stringly_typed_level():
    assert not hasattr(DM, "compute_level"), "the views are passed as functions, not named by a string"
    dm_src, cm_src = inspect.getsource(DM), inspect.getsource(CM)
    assert "journal_mode" not in dm_src, "detection_map repeats the snapshot block"
    assert cm_src.count("journal_mode") == 1, "coverage_map holds the snapshot block once"


def test_no_dead_removed_at_guard():
    """`init_db` adds `discovery_runs.removed_at` (schema `_DISCOVERY_RUNS_NEW_COLUMNS`) on every database the
    bridge opens; the core re-checking it on every read is dead."""
    assert "table_info(discovery_runs)" not in inspect.getsource(DM)
