"""
test_webui_reports.py
=====================
The reports bridge (`webui/server/reports.py`, docs/prompts/changes/reports.md)
against a synthetic database with one real Discovery run.

What it pins:

* the live report renders, with at least one embedded PNG and the scoreboard
  table;
* **the Markdown scoreboard is the scoreboard route's numbers**, formatted —
  read from the same route, for the same run, channels and section;
* the twelve examples are the same twelve on a second render;
* a snapshot writes the HTML, the Markdown and the PNGs under the results
  folder, records its PATH, and is listed;
* the held-out recording is refused as the pages refuse it (423).

FastAPI lives only in `webui/.venv`; run with
    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_reports.py
"""

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
from server.runtime import HELD_OUT_FILE, Runtime  # noqa: E402

FS = 1.0
N = 6000
M = 60
PLANTS = (600, 1800, 3400, 4500)
OLD = "2020-01-01T00:00:00+00:00"
CH = ["CH1", "CH2", "CH3"]
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _planted(seed):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(N) * 0.02
    shape = -np.sin(np.linspace(0.0, np.pi, M))
    for p in PLANTS:
        x[p:p + M] += shape
    return x


def _db(tmp_path):
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    for ch in range(3):
        npy = tmp_path / f"CH{ch}.npy"
        np.save(npy, _planted(ch))
        conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                     "VALUES ('syn.mat', ?, ?, ?, 0, ?)", (ch, FS, N, str(npy)))
    held = tmp_path / "held.npy"
    np.save(held, _planted(9))
    conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                 "VALUES (?, 0, ?, ?, 0, ?)", (HELD_OUT_FILE, FS, N, str(held)))
    for rid in (1, 2):
        conn.execute("INSERT INTO reviewed_spans (recording_id, start_idx, end_idx, source, reviewed_at) "
                     "VALUES (?, 0, 3000, 'test', ?)", (rid, OLD))
        conn.execute("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
                     "VALUES (?, ?, ?, 'interesting', 'test', ?)", (rid, PLANTS[0], PLANTS[0] + M, OLD))
        conn.execute("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
                     "VALUES (?, ?, ?, 'not_interesting', 'test', ?)", (rid, 2000, 2000 + M, OLD))
    conn.commit()
    conn.close()
    return db


def _dist(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    return dist


@pytest.fixture(scope="module")
def _env(tmp_path_factory):
    """One app and one real Discovery run for the whole file: applying the
    template is the slow part (a real fan-out with its paired nulls)."""
    tmp_path = tmp_path_factory.mktemp("reports")
    db = _db(tmp_path)
    rt = Runtime(mode="sandbox", stamp="20261019-reports", db_source=str(db),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(_dist(tmp_path)))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            r = c.put("/api/discovery/session", json={
                "name": "test", "recording": "syn", "channels": CH, "section": [0.0, N / FS / 3600.0],
                "null": {"method": "phase randomisation", "n": 2}})
            assert r.status_code == 200, r.text
            r = c.post("/api/discovery/templates/apply",
                       json={"templates": ["mp_threshold"], "channels": CH, "t0": 0.0, "t1": N / FS / 3600.0})
            assert r.status_code == 200, r.text
            out = r.json()[0]
            if out.get("job_id"):
                snap = _wait_job(c, out["job_id"])
                assert snap["status"] == "completed", snap.get("error")
            yield c, out["run_key"]
    finally:
        rt.restore()


@pytest.fixture
def client(_env):
    return _env[0]


@pytest.fixture
def run_key(_env):
    return _env[1]


def _wait_job(client, job_id, timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get(f"/api/jobs/{job_id}").json()
        if s["status"] in ("completed", "failed", "cancelled"):
            return s
        time.sleep(0.25)
    raise AssertionError(f"job {job_id} did not finish")


def _report(client, key):
    r = client.get(f"/api/reports/detection-run/{key}")
    assert r.status_code == 200, r.text
    return r.json()


def test_the_live_report_renders_with_figures_and_the_scoreboard_table(client, run_key):
    rep = _report(client, run_key)
    assert rep["runKey"] == run_key
    assert rep["fragment"].count("<img") >= 3
    assert "data:image/png;base64," in rep["fragment"]
    assert 'data-table="scoreboard"' in rep["fragment"]
    assert "<script" not in rep["html"]
    page = client.get(f"/api/reports/detection-run/{run_key}/html")
    assert page.status_code == 200 and page.headers["content-type"].startswith("text/html")
    assert "<img" in page.text


def test_the_markdown_scoreboard_is_the_scoreboard_routes_numbers(client, run_key):
    from Working.reports import formatting as F
    rep = _report(client, run_key)
    sb = client.get("/api/discovery/scoreboard", params={
        "runs": run_key, "channels": ",".join(CH), "t0": 0.0, "t1": N / FS / 3600.0}).json()[0]
    md = rep["markdown"]
    # the scoreboard's own section: the map's tables above it also have a row per channel
    lines = md[md.index("## 2. Scoreboard"):md.index("## 3.")].splitlines()

    def cells_of(label):
        line = next(ln for ln in lines if ln.startswith(f"| {label} |"))
        return [c.strip() for c in line.strip("|").split("|")][1:]

    total = cells_of("**total**")
    assert total == [F.score_cells(sb["total"])[k] for k in F.SCORE_COLUMNS]
    assert total[0] == str(sb["total"]["found"]) and total[2] == str(sb["total"]["reviewed"])
    for row in sb["channels"]:
        assert cells_of(row["channel"]) == [F.score_cells(row)[k] for k in F.SCORE_COLUMNS]
    assert sb["reviewedCriterion"] in rep["markdown"]


def test_the_twelve_examples_are_stable_across_two_renders(client, run_key):
    a = _report(client, run_key)["examples"]
    b = _report(client, run_key)["examples"]
    assert a and [e["detectionId"] for e in a] == [e["detectionId"] for e in b]
    assert len(a) <= 12


def test_a_snapshot_writes_under_the_results_folder_and_is_listed(client, run_key):
    r = client.post(f"/api/reports/detection-run/{run_key}/snapshot", json={"note": "for chapter 4"})
    assert r.status_code == 200, r.text
    snap = r.json()
    rt = client.app.state.rt
    root = os.path.join(rt.results_dir, "reports", "detection-run", run_key)
    assert os.path.normcase(os.path.abspath(snap["path"])).startswith(os.path.normcase(os.path.abspath(root)))
    files = os.listdir(snap["path"])
    assert "report.md" in files and "report.html" in files and "fig-01-map.png" in files
    with open(os.path.join(snap["path"], "fig-01-map.png"), "rb") as f:
        assert f.read(8) == PNG_MAGIC
    listed = client.get("/api/reports").json()
    row = next(x for x in listed if x["id"] == snap["id"])
    assert row["kind"] == "detection-run" and row["runKey"] == run_key and row["note"] == "for chapter 4"
    assert row["exists"] is True
    conn = sqlite3.connect(rt.db_path)
    try:
        stored = conn.execute("SELECT path FROM reports WHERE id = ?", (snap["id"],)).fetchone()[0]
    finally:
        conn.close()
    assert stored == snap["path"], "the database holds the snapshot's path, never its bytes"
    served = client.get(f"/api/reports/{snap['id']}/files/fig-01-map.png")
    assert served.status_code == 200 and served.content[:8] == PNG_MAGIC
    assert client.get(f"/api/reports/{snap['id']}/files/..%2F..%2Fsecret.txt").status_code in (400, 404)


def test_an_unknown_run_is_a_404_naming_it(client):
    r = client.get("/api/reports/detection-run/no_such_run")
    assert r.status_code == 404 and "no_such_run" in r.text


def test_a_report_on_the_held_out_recording_is_refused(client, run_key):
    conn = sqlite3.connect(client.app.state.rt.db_path)
    try:
        sid, sf, chj = conn.execute("SELECT id, source_file, channels_json FROM discovery_sessions "
                                    "ORDER BY id DESC LIMIT 1").fetchone()
        conn.execute("UPDATE discovery_sessions SET source_file = ?, channels_json = ? WHERE id = ?",
                     (HELD_OUT_FILE, json.dumps(["CH1"]), sid))
        conn.commit()
        r = client.get(f"/api/reports/detection-run/{run_key}")
        assert r.status_code == 423, r.text
        r = client.post(f"/api/reports/detection-run/{run_key}/snapshot", json={})
        assert r.status_code == 423, r.text
    finally:
        conn.execute("UPDATE discovery_sessions SET source_file = ?, channels_json = ? WHERE id = ?", (sf, chj, sid))
        conn.commit()
        conn.close()


def test_a_project_start_saves_snapshots_in_a_git_ignored_folder_not_the_tracked_results():
    """critic (2026-10-19): `Results/` is TRACKED in this repository, so a project start's snapshots there would sit
    in `git status` as untracked files and risk being committed. A project start (no sandbox results folder) writes
    under `DATA/derived/reports`, which `DATA/*` ignores; a sandbox keeps its own results folder."""
    from types import SimpleNamespace

    from server.reports import _results_root
    from server.runtime import REPO_ROOT

    def under(path, root):
        return os.path.normcase(os.path.abspath(path)).startswith(os.path.normcase(os.path.abspath(root)) + os.sep)

    project = _results_root(SimpleNamespace(results_dir=None))
    assert under(project, os.path.join(REPO_ROOT, "DATA", "derived")), project
    assert not under(project, os.path.join(REPO_ROOT, "Results")), project
    sandbox = _results_root(SimpleNamespace(results_dir=os.path.join("C:\\", "rt", "results")))
    assert under(sandbox, os.path.join("C:\\", "rt", "results")), sandbox
