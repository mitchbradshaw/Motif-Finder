"""
test_webui_window_set_save.py
==============================
fixup-aa item 2: *Save window set* makes a real `window_sets` row (§6.9) —
the one Library › Window sets reads — instead of only a `registered_artifacts`
row the Library never looks at (`window_sets` had 0 rows on 2026-10-03).

The saved row carries what §6.9 lists: the split assignment and its rule, the
spacing check, human-verdict coverage per split and per class AT SAVE TIME, and
the producing recipe's hash; the window bounds live on disk and the row holds
the path (rule 4). A training set keeps no two overlapping windows by default
(Q-W1): on the labels' 600/200 grid that is a stride-600 subset on the phase
that keeps the most labelled windows, the offset recorded, the dropped counted.
Coverage is live: the Library shows it now and at save.

FastAPI lives only in `webui/.venv`:

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_window_set_save.py -q
"""

import datetime as _dt
import json
import os
import sqlite3
import sys
import time

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from fastapi.testclient import TestClient  # noqa: E402

from Working.database.schema import init_db  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402

N = 7200
PHASE200 = list(range(200, N - 600, 600))     # 11 labelled windows on the 200-mod-600 phase


def _db(tmp_path):
    db_dir = tmp_path / "db"; db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    rng = np.random.default_rng(1)
    npy = tmp_path / "CH0.npy"
    np.save(npy, np.cumsum(rng.standard_normal(N)) * 0.01)
    conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                 "VALUES ('syn_fs1.mat', 0, 1.0, ?, 0, ?)", (N, str(npy)))
    now = _dt.datetime.now().isoformat(timespec="seconds")
    for k, s in enumerate(PHASE200):
        conn.execute("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
                     "VALUES (1, ?, ?, ?, 'imported_10min', ?)",
                     (s, s + 600, "interesting" if k % 3 == 0 else "not_interesting", now))
    conn.commit(); conn.close()
    return db


def _dist(tmp_path):
    dist = tmp_path / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    return dist


@pytest.fixture
def client(tmp_path):
    db = _db(tmp_path)
    rt = Runtime(mode="sandbox", stamp="20261003-aa", db_source=str(db), runtime_root=str(tmp_path / "runtime"),
                 client_dist=str(_dist(tmp_path)))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            c.rt = rt
            yield c
    finally:
        rt.restore()


def _wait_job(client, job_id, timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get(f"/api/jobs/{job_id}").json()
        if s["status"] in ("completed", "failed", "cancelled"):
            assert s["status"] == "completed", s
            return s
        time.sleep(0.2)
    raise AssertionError("job did not finish")


STEPS = [
    {"stage": "preprocessing", "algorithm": "window_matrix",
     "params": {"window_min": 10.0, "step_frac": 0.334, "catch22": False, "fast_entropy": True,
                "slow_entropy": False, "cnn": False, "rf": False}},
    {"stage": "catalogue", "algorithm": "manual_labels", "params": {}},
]


def _run(client):
    job = client.post("/api/runs", json={"recording_id": 1, "span": [0, N], "steps": STEPS}).json()
    _wait_job(client, job["job_id"])
    return job["job_id"]


def _row(client, name):
    conn = sqlite3.connect(client.rt.db_path); conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM window_sets WHERE name = ?", (name,)).fetchone()
    finally:
        conn.close()


def test_save_window_set_makes_a_window_sets_row_with_what_6_9_lists(client):
    job_id = _run(client)
    r = client.post("/api/windowsets", json={"job_id": job_id, "step": 0, "name": "ws_aa"})
    assert r.status_code == 200, r.text
    row = _row(client, "ws_aa")
    assert row is not None, "the Library reads window_sets; a save that does not write it is invisible"
    assert row["recording_id"] == 1 and row["channel"] == 0 and row["window_length"] == 600
    assert row["recipe_hash"]
    assert os.path.isdir(row["path"]), "bounds on disk, the row holds the path"

    split = json.loads(row["split_json"])
    assert split["rule"] == "none", "a window matrix carries no split; the row says so rather than inventing one"
    spacing = json.loads(row["spacing_json"])
    assert spacing and all(spacing.values()), spacing
    cov = json.loads(row["coverage_json"])
    assert cov["phase_offset"] == 200
    assert row["n_windows"] == len(PHASE200) == cov["labelled_windows"]
    assert cov["dropped_for_overlap"] > 0
    assert cov["class_counts_at_save"] == {"interesting": 4, "not_interesting": 7}
    assert cov["by_split"]["all"]["interesting"] == 4

    from Working.types import WindowSet
    ws = WindowSet.from_path(row["path"])
    assert ws.n_windows == row["n_windows"]
    assert np.all(np.diff(ws.starts) >= ws.length), "no two saved windows overlap"
    assert set(int(s) % 600 for s in ws.starts) == {200}


def test_overlap_is_kept_only_when_asked(client):
    job_id = _run(client)
    r = client.post("/api/windowsets", json={"job_id": job_id, "step": 0, "name": "ws_all", "non_overlapping": False})
    assert r.status_code == 200, r.text
    row = _row(client, "ws_all")
    assert row["n_windows"] > len(PHASE200)
    spacing = json.loads(row["spacing_json"])
    assert not all(spacing.values()), "an overlapping set fails its own spacing check"


def test_the_library_lists_it_with_coverage_now_and_at_save(client):
    job_id = _run(client)
    assert client.post("/api/windowsets", json={"job_id": job_id, "step": 0, "name": "ws_lib"}).status_code == 200
    sets = client.get("/api/library/windowsets").json()
    row = next(s for s in sets if s["id"] == "ws_lib")
    assert row["labelledWindows"] == len(PHASE200)
    assert row["classCounts"]["atSave"] == {"interesting": 4, "not_interesting": 7}
    assert row["classCounts"]["now"] == {"interesting": 4, "not_interesting": 7}
    assert row["spacingChecks"] and all(c["ok"] for c in row["spacingChecks"])

    # the researcher changes one label after saving: "now" moves, "at save" does not
    conn = sqlite3.connect(client.rt.db_path)
    conn.execute("UPDATE annotations SET verdict = 'interesting' WHERE id = "
                 "(SELECT MIN(id) FROM annotations WHERE verdict = 'not_interesting')")
    conn.commit(); conn.close()
    row = next(s for s in client.get("/api/library/windowsets").json() if s["id"] == "ws_lib")
    assert row["classCounts"]["now"] == {"interesting": 5, "not_interesting": 6}
    assert row["classCounts"]["atSave"] == {"interesting": 4, "not_interesting": 7}
