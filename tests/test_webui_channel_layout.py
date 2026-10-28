"""
test_webui_channel_layout.py
============================
Cross-channel explorer S0: `GET /api/layout/{source_file}` serves `Working.channel_layout` - every
channel's pack (Settings, else the M2 letter, else unassigned) and position - and refuses the held-out
file with a 423 while its lock is on. A pack saved through the page's own audited path
(`PUT /api/settings/channels-events`) is what the reader then reports, which pins the key format end
to end.

Runs with webui/.venv (FastAPI).
"""

import os
import sys

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

N = 200


@pytest.fixture
def client(tmp_path):
    db_dir = tmp_path / "db"; db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    for sf, stem, n in (("M2_aug_concat_fs1.mat", "M2_aug_concat_fs1", 16), ("CO_fs2.mat", "CO_fs2", 4),
                        ("M4_aug_concat_fs1.mat", "M4_aug_concat_fs1", 16)):
        d = tmp_path / "channels" / stem; d.mkdir(parents=True)
        for ch in range(n):
            npy = d / f"CH{ch}.npy"; np.save(npy, np.zeros(N))
            conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path, units) "
                         "VALUES (?, ?, 1.0, ?, 0, ?, 'V')", (sf, ch, N, str(npy)))
    conn.commit(); conn.close()
    dist = tmp_path / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    rt = Runtime(mode="sandbox", stamp="20261028-channel-layout", db_source=str(db),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(dist))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            yield c
    finally:
        rt.restore()


def _names(body):
    return {row["name"]: row for row in body["channels"].values()}


def test_m2_packs_come_from_the_names(client):
    r = client.get("/api/layout/M2_aug_concat_fs1.mat")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rec"] == "M2_aug_concat_fs1" and body["packs"] == ["A", "B", "C", "D"]
    assert body["layout_known"] is True and body["positions_known"] is False and body["note"] is None
    assert _names(body)["CH7_B2"] == {"name": "CH7_B2", "channel": 6, "pack": "B", "pack_from": "name",
                                     "x_mm": None, "y_mm": None}


def test_an_unassigned_recording_says_layout_unknown(client):
    body = client.get("/api/layout/CO_fs2.mat").json()
    assert body["packs"] == ["unassigned"] and body["layout_known"] is False
    assert body["note"] == "packs not set — layout unknown"


def test_a_pack_saved_by_the_page_is_what_the_reader_reports(client):
    saved = client.put("/api/settings/channels-events",
                       json={"values": {"pack.CO_fs2.CH2": "east", "x_mm.CO_fs2.CH2": 12.5, "y_mm.CO_fs2.CH2": 3}})
    assert saved.status_code == 200, saved.text
    row = _names(client.get("/api/layout/CO_fs2.mat").json())["CH2"]
    assert (row["pack"], row["pack_from"], row["x_mm"], row["y_mm"]) == ("east", "settings", 12.5, 3.0)


def test_the_held_out_file_is_refused(client):
    r = client.get("/api/layout/M4_aug_concat_fs1.mat")
    assert r.status_code == 423


def test_an_unregistered_file_is_a_404(client):
    assert client.get("/api/layout/nope.mat").status_code == 404
