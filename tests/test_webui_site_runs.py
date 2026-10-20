"""
test_webui_site_runs.py
=======================
site-runs (2026-10-20): the Discovery bridge half of the researcher's eve-of-demo list.

* Item 6 -- a NEW session is named after the dataset (its display name, or its file stem when Settings > Datasets
  gave it none), not "<stem> screen". An existing session keeps the name it has.

FastAPI lives only in `webui/.venv`; run with
    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_site_runs.py
"""
import os
import sqlite3
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui"), os.path.join(PROJECT_ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from test_webui_discovery import FS, N, _planted, client  # noqa: E402,F401  (the fixture)


def _add_other(client, tmp_path):
    other = tmp_path / "other.npy"
    np.save(other, _planted(5))
    conn = sqlite3.connect(client.app.state.rt.db_path)
    conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                 "VALUES ('other.mat', 0, ?, ?, 0, ?)", (FS, N, str(other)))
    conn.commit()
    conn.close()


def test_a_new_session_is_named_after_its_dataset_not_screen(client, tmp_path):
    _add_other(client, tmp_path)
    s = client.put("/api/discovery/session", json={"recording": "other", "channels": ["CH1"]}).json()["session"]
    assert "screen" not in s["name"]
    assert s["name"] == "other"


def test_an_existing_session_keeps_its_name(client, tmp_path):
    first = client.get("/api/discovery/session").json()["session"]
    _add_other(client, tmp_path)
    client.put("/api/discovery/session", json={"recording": "other", "channels": ["CH1"]})
    back = client.put("/api/discovery/session", json={"recording": "syn"}).json()["session"]
    assert back["name"] == first["name"]


def test_the_put_answers_with_the_opened_sessions_name(client, tmp_path):
    """The page now builds its scope from this answer (session.ts `scopeFromSession`), so it must name the session
    that was OPENED, not the one the write started from."""
    before = client.get("/api/discovery/session").json()["session"]["name"]
    _add_other(client, tmp_path)
    moved = client.put("/api/discovery/session", json={"recording": "other", "channels": ["CH1"]}).json()["session"]
    assert moved["name"] != before


# ── item 4: the Send button's count is a cheap read of its own ──────────────

from test_webui_discovery import CH, _apply  # noqa: E402


def test_the_unjudged_count_is_found_minus_the_detections_with_a_verdict(client, monkeypatch):
    """The scoreboard over the real session (16 channels x 52 runs, 721 h) took 461 s cold on a copy of the real
    database, and the button printed "Send 0 unjudged" all that while. The count now comes from its own read, which
    never scores (score_runs is made to explode here) and counts the run's real detections -- surrogates left out --
    that carry no adjudication: the detections a Send puts in the queue."""
    out = _apply(client)
    from server import discovery as disc
    monkeypatch.setattr(disc.SB, "score_runs", lambda *a, **k: (_ for _ in ()).throw(AssertionError("scored")))
    conn = sqlite3.connect(client.app.state.rt.db_path)
    conn.row_factory = sqlite3.Row
    try:
        dr = conn.execute("SELECT * FROM discovery_runs WHERE run_key = ? AND removed_at IS NULL ORDER BY id DESC",
                          (out["run_key"],)).fetchone()
        run_ids = ",".join(str(int(i)) for i in disc._run_ids(conn, dr))
        ids = [r[0] for r in conn.execute(
            "SELECT d.id FROM detections d JOIN runs r ON r.id = d.run_id WHERE r.id IN (" + run_ids + ") "
            "AND r.surrogate_of_run_id IS NULL ORDER BY d.id").fetchall()]
        assert ids, "the fixture run found nothing"
        conn.execute("INSERT INTO adjudications (detection_id, verdict, created_at) VALUES (?, 'interesting', ?)",
                     (ids[0], "2026-10-20T00:00:00+00:00"))
        conn.commit()
    finally:
        conn.close()
    r = client.get(f"/api/discovery/runs/{out['run_key']}/unjudged")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["found"] == len(ids)
    assert body["judged"] == 1
    assert body["unjudged"] == len(ids) - 1


def test_the_unjudged_count_of_an_unknown_run_is_a_404(client):
    assert client.get("/api/discovery/runs/nope/unjudged").status_code == 404
