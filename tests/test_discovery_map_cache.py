"""
test_discovery_map_cache.py
===========================
map-overview-cache (2026-10-20), the core half: Discovery › Map's overview (`detection_map.dataset_map`) took 17–21 s
on every read of the real database, inside the request. The bridge now serves the last computed overview and
recomputes it in its worker process (`webui/server/discovery_map.py`; route pins in `tests/test_webui_discovery_map.py`).
What the worker calls lives here, UI-free:

* ``compute(db_path, exclude_files)`` -> ``(fingerprint, overview)``, read on a read-only connection of its own, the
  overview identical to `dataset_map`'s and the fingerprint naming the state it READ;
* ``overview_fingerprint(conn, exclude_files)`` — a digest of every row the overview reads. It must move when a run
  is added, discarded or changes status, when a run gains detections and when a verdict is edited or deleted in
  place; it must not move for a setting the overview never reads;
* ``any_running(conn)`` — whether a Discovery run is still going (the page then says so and keeps polling).

Pure core, conda interpreter.
"""
import json
import os
import sqlite3
import subprocess
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(PROJECT_ROOT, "tests")
for p in (PROJECT_ROOT, TESTS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import perf_fixture  # noqa: E402
from Working.discovery import detection_map as DM  # noqa: E402

SMALL = dict(n_channels=3, hours=24.0, n_druns=4, n_detections=6_000, n_annotations=200, n_templates=3,
             queue_size=50, n_adjudications=10, n_reviewed=20, write_npy=False)


@pytest.fixture()
def db(tmp_path):
    info = perf_fixture.build(str(tmp_path / "map.sqlite"), **SMALL)
    return info


def _conn(path):
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    return c


def _fp(path, exclude=()):
    c = _conn(path)
    try:
        return DM.overview_fingerprint(c, exclude)
    finally:
        c.close()


def test_compute_returns_the_overview_and_the_fingerprint_of_what_it_read(db):
    c = _conn(db["db"])
    try:
        want = DM.dataset_map(c, exclude_files=())
        want_fp = DM.overview_fingerprint(c, ())
    finally:
        c.close()
    fp, got = DM.compute(db["db"], ())
    assert got == want
    assert fp == want_fp
    assert isinstance(fp, str) and len(fp) == 40, "a stable digest (sha1 hex), the same in every process"


def test_compute_leaves_out_the_excluded_files(db):
    fp, got = DM.compute(db["db"], (perf_fixture.SOURCE_FILE,))
    assert got["datasets"] == [] and got["heldOutOmitted"] == [perf_fixture.SOURCE_FILE]
    assert fp != DM.compute(db["db"], ())[0]


def _edit(path, sql, args=()):
    c = sqlite3.connect(path)
    try:
        c.execute(sql, args)
        c.commit()
    finally:
        c.close()


@pytest.mark.parametrize("what, sql", [
    ("a run gains detections", "INSERT INTO detections (run_id, start_idx, end_idx, score) "
                               "SELECT id, 10, 20, 0.5 FROM runs ORDER BY id LIMIT 1"),
    ("a run changes status", "UPDATE runs SET status = 'failed' WHERE id = (SELECT MIN(id) FROM runs)"),
    ("a run is discarded", "UPDATE runs SET superseded_at = '2026-10-20T10:00:00' WHERE id = (SELECT MIN(id) FROM runs)"),
    ("a Discovery run is discarded", "UPDATE discovery_runs SET superseded_at = '2026-10-20T10:00:00' "
                                     "WHERE id = (SELECT MIN(id) FROM discovery_runs)"),
    ("a Discovery run changes status", "UPDATE discovery_runs SET status = 'failed' WHERE id = (SELECT MIN(id) FROM discovery_runs)"),
    ("a verdict is edited in place", "UPDATE annotations SET verdict = CASE verdict WHEN 'seed' THEN 'interesting' "
                                     "ELSE 'seed' END WHERE id = (SELECT MIN(id) FROM annotations)"),
    ("a verdict is deleted", "UPDATE annotations SET deleted_at = '2026-10-20T10:00:00' WHERE id = (SELECT MIN(id) FROM annotations)"),
    ("a reviewed span is added", "INSERT INTO reviewed_spans (recording_id, start_idx, end_idx, source, reviewed_at) "
                                 "SELECT id, 0, 100, 'test', '2026-10-20' FROM recordings LIMIT 1"),
    ("a session is renamed", "UPDATE discovery_sessions SET name = 'renamed' WHERE id = (SELECT MIN(id) FROM discovery_sessions)"),
])
def test_the_fingerprint_moves_with_every_row_the_overview_reads(db, what, sql):
    before = _fp(db["db"])
    _edit(db["db"], sql)
    assert _fp(db["db"]) != before, f"{what}: the overview would be served stale"


def test_a_new_discovery_run_moves_the_fingerprint(db):
    before = _fp(db["db"])
    c = sqlite3.connect(db["db"])
    try:
        sid = c.execute("SELECT MIN(id) FROM discovery_sessions").fetchone()[0]
        rid = c.execute("SELECT MIN(id) FROM runs").fetchone()[0]
        c.execute("INSERT INTO discovery_runs (session_id, run_key, kind, label, colour, params_json, status, created_at, "
                  "updated_at) VALUES (?, 'extra', 'template', 'extra', '#000', ?, 'done', '2026-10-20', '2026-10-20')",
                  (sid, json.dumps({"run_ids": [rid]})))
        c.commit()
    finally:
        c.close()
    assert _fp(db["db"]) != before


def test_a_setting_the_overview_never_reads_leaves_the_fingerprint_alone(db):
    before = _fp(db["db"])
    _edit(db["db"], "INSERT OR REPLACE INTO settings (page, key, value_json, updated_at) "
                    "VALUES ('analysis-defaults', 'iou', '0.42', '2026-10-20')")
    assert _fp(db["db"]) == before


def test_any_running_says_whether_a_discovery_run_is_still_going(db):
    c = _conn(db["db"])
    try:
        assert DM.any_running(c) is False
        c.execute("UPDATE discovery_runs SET status = 'running' WHERE id = (SELECT MIN(id) FROM discovery_runs)")
        assert DM.any_running(c) is True
        c.execute("UPDATE discovery_runs SET superseded_at = '2026-10-20' WHERE status = 'running'")
        assert DM.any_running(c) is False, "a discarded run is not going"
    finally:
        c.close()


def test_the_map_module_imports_no_ui_module():
    """The worker child imports `detection_map`; it must never pull the bridge or FastAPI in."""
    code = ("import sys; import Working.discovery.detection_map; "
            "print(sorted(m for m in sys.modules if m.split('.')[0] in ('webui', 'server', 'fastapi', 'starlette', 'uvicorn')))")
    out = subprocess.run([sys.executable, "-c", code], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "[]", out.stdout
