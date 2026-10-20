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
