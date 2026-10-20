"""
test_webui_night_disc_recording_switch.py
=========================================
night-disc item 3 ("I get 49 matches, not 155"), at the bridge. A recording has ONE Discovery session; switching to a
recording opens that recording's session. The Scope card used to send the switch as `{recording, channels: first
three, section: [0, min(hours, 174)]}`, and `PUT /api/discovery/session` then wrote those defaults over the target
session's saved scope -- "demo · talk" (5 channels, 0-721 h) became 3 channels x 174 h, and the next seed search on it
found 49 instead of 155. The client now sends `{recording}` alone; this pins that the bridge then opens the target
session AS IT WAS LEFT (its channels and its section), and builds a new one with its own defaults when there is none.

FastAPI lives only in `webui/.venv`; under the conda `pytest` this file skips:

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_night_disc_recording_switch.py
"""

import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBUI_DIR = os.path.join(PROJECT_ROOT, "webui")
for p in (PROJECT_ROOT, WEBUI_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv; run this file with that interpreter")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from fastapi.testclient import TestClient  # noqa: E402

from Working.database.schema import init_db  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402

N_A = 3600 * 700      # 700 h at 1 Hz
N_B = 3600 * 300      # 300 h at 1 Hz


def _fresh_db(tmp_path):
    db_dir = tmp_path / "db"; db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    ins = "INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) VALUES (?, ?, ?, ?, 0, ?)"
    for ch in range(6):
        conn.execute(ins, ("Alpha_fs1.mat", ch, 1.0, N_A, f"Alpha_fs1/CH{ch}.npy"))
    for ch in range(4):
        conn.execute(ins, ("Beta_fs1.mat", ch, 1.0, N_B, f"Beta_fs1/CH{ch}.npy"))
    conn.commit(); conn.close()
    return db


@pytest.fixture
def bridge(tmp_path):
    db = _fresh_db(tmp_path)
    dist = tmp_path / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    rt = Runtime(mode="sandbox", stamp="20261020-nd", db_source=str(db), runtime_root=str(tmp_path / "runtime"), client_dist=str(dist))
    rt.setup()
    try:
        app = create_app(rt)
        app.state.registry_roots = {"recording": [str(tmp_path / "none")], "raw": [str(tmp_path / "none")]}
        with TestClient(app) as client:
            yield client
    finally:
        rt.restore()


def _key(client, file):
    return next(r["key"] for r in client.get("/api/discovery/session").json()["recordings"] if r["file"] == file)


def _put(client, **body):
    r = client.put("/api/discovery/session", json=body)
    assert r.status_code == 200, r.text
    return r.json()["session"]


def test_a_bare_recording_switch_opens_the_target_session_as_it_was_left(bridge):
    client = bridge
    a, b = _key(client, "Alpha_fs1.mat"), _key(client, "Beta_fs1.mat")
    # the talk's session: five channels, the whole recording
    _put(client, recording=a)
    talk = _put(client, recording=a, channels=["CH1", "CH2", "CH3", "CH4", "CH5"], section=[0.0, 700.0])
    assert talk["channels"] == ["CH1", "CH2", "CH3", "CH4", "CH5"]
    # away to another recording and back, the way the Scope card now switches: the recording alone
    other = _put(client, recording=b)
    assert other["recordingFile"] == "Beta_fs1.mat"
    back = _put(client, recording=a)
    assert back["recordingFile"] == "Alpha_fs1.mat"
    assert back["name"] == talk["name"]
    assert back["channels"] == ["CH1", "CH2", "CH3", "CH4", "CH5"], "the switch overwrote the session's channels"
    assert [round(x, 3) for x in back["section"]] == [0.0, 700.0], "the switch overwrote the session's section"


def test_a_bare_switch_to_a_recording_with_no_session_builds_one_with_its_own_defaults(bridge):
    client = bridge
    a, b = _key(client, "Alpha_fs1.mat"), _key(client, "Beta_fs1.mat")
    _put(client, recording=a)
    new = _put(client, recording=b)
    assert new["recordingFile"] == "Beta_fs1.mat"
    assert new["channels"] and all(c.startswith("CH") for c in new["channels"])
    assert 0 <= new["section"][0] < new["section"][1] <= 300.0 + 1e-6
