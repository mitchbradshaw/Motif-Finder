"""
test_webui_night_b_family_cold.py
=================================
night-b: the first open of a Library family on a scale database took 44-54 s (night fixture = tests/perf_fixture.py
FULL plus a 12-family grouping; profiled: `_library_detections` 18 s of it, 12 recordings x ~385 k detections each,
a Python `absolute_bounds` call per row, then `background_null._Recording` looping over every one of them again to
build its mask).

What the quiet-window null needs from the detections is only their UNION on the recording (a cumulative mask: "does
this window touch a detection"). `_library_detections` now shifts legacy span-relative rows in SQL, sorts there,
and hands back the merged intervals — the same mask from far fewer, already-merged pairs.

webui/.venv (library.py imports FastAPI); skips under conda.
"""
import os
import sqlite3
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv; run this file with that interpreter")

from server.library import _library_detections  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.discovery.spans import absolute_bounds  # noqa: E402


def _db(tmp_path, rows):
    conn = init_db(str(tmp_path / "a.sqlite"))
    rec = conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                       "VALUES ('X.mat', 0, 1.0, 100000, 0, 'x.npy')").lastrowid
    cfg = conn.execute("INSERT INTO configs (config_hash, config_json, created_at) VALUES ('h', '{}', 'now')").lastrowid
    runs = {}
    for span_start in sorted({r[2] for r in rows}):
        runs[span_start] = conn.execute(
            "INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
            "VALUES (?, ?, ?, 100000, 'now', 'completed')", (cfg, rec, span_start)).lastrowid
    conn.executemany("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, 0.5)",
                     [(runs[o], a, b) for a, b, o in rows])
    conn.commit()
    return conn, rec


def _mask(pairs, n=100000):
    m = np.zeros(n, bool)
    for a, b in pairs:
        m[max(0, a):min(n, b)] = True
    return m


def test_the_detections_come_back_as_their_merged_union(tmp_path):
    # overlapping, nested, touching, apart; one whole-channel run and one legacy span-relative run (offset 50 000)
    rows = [(100, 200, 0), (150, 260, 0), (170, 180, 0), (260, 300, 0), (900, 950, 0),
            (10, 40, 50000), (30, 60, 50000), (51000, 51100, 50000)]
    conn, rec = _db(tmp_path, rows)
    got = _library_detections(conn, rec)
    want = _mask([absolute_bounds(a, b, o) for a, b, o in rows])
    assert np.array_equal(_mask(got), want), "the union on the recording is unchanged"
    assert got == [(100, 300), (900, 950), (50010, 50060), (51000, 51100)]
    assert all(isinstance(v, int) for p in got for v in p)


def test_no_detection_is_an_empty_list(tmp_path):
    conn, rec = _db(tmp_path, [])
    assert _library_detections(conn, rec) == []
