"""
test_webui_api.py
=================
Route-level guarantees of the FastAPI bridge that no page can be trusted to
catch:

* an unknown `/api/...` path is a JSON 404, never the SPA's `index.html`
  (the catch-all used to swallow typos as a 200 HTML page);
* a wrong method on a real `/api` route is a JSON 405, not a 404;
* the held-out recording is refused with 423 in BOTH runtime modes.

FastAPI lives only in `webui/.venv` (system-site-packages over conda), so
under the conda `pytest` this file skips with a message; run it with

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_api.py

to see it execute. Nothing here touches `DATA/`.
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
from server.runtime import HELD_OUT_FILE, Runtime  # noqa: E402


def _fresh_db(tmp_path):
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    conn.execute(
        "INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
        "VALUES (?, 0, 1.0, 10, 0, 'held.npy')", (HELD_OUT_FILE,))
    conn.execute(
        "INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
        "VALUES ('normal.mat', 0, 1.0, 10, 0, 'normal.npy')")
    conn.commit()
    held_id = conn.execute("SELECT id FROM recordings WHERE source_file = ?", (HELD_OUT_FILE,)).fetchone()[0]
    conn.close()
    return db, held_id


def _fake_dist(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    return dist


@pytest.fixture(params=["sandbox", "project"])
def bridge(request, tmp_path):
    db, held_id = _fresh_db(tmp_path)
    rt = Runtime(mode=request.param, stamp=f"20260921-{request.param}",
                 db_source=str(db), runtime_root=str(tmp_path / "runtime"),
                 client_dist=str(_fake_dist(tmp_path)))
    rt.setup()
    try:
        app = create_app(rt)
        with TestClient(app) as client:
            yield client, held_id, request.param
    finally:
        rt.restore()


def test_unknown_api_path_is_a_json_404_not_the_spa(bridge):
    client, _held, _mode = bridge
    r = client.get("/api/this-route-does-not-exist")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json"), r.text
    body = r.json()
    assert body["path"] == "/api/this-route-does-not-exist"
    assert "index.html" not in r.text and "<!doctype" not in r.text.lower()


def test_unknown_nested_api_path_with_any_method_is_a_json_404(bridge):
    client, _held, _mode = bridge
    for method in ("get", "post", "put", "delete"):
        r = getattr(client, method)("/api/runs/999/no/such/thing")
        assert r.status_code == 404, (method, r.status_code, r.text[:80])
        assert r.headers["content-type"].startswith("application/json")


def test_wrong_method_on_a_real_api_route_is_a_405_not_a_404(bridge):
    client, _held, _mode = bridge
    r = client.post("/api/health")
    assert r.status_code == 405, r.text[:120]
    assert r.headers["content-type"].startswith("application/json")


def test_non_api_paths_still_serve_the_spa(bridge):
    client, _held, _mode = bridge
    r = client.get("/some/client/route")
    assert r.status_code == 200
    assert "spa" in r.text


def test_runtime_endpoint_names_the_mode_loudly(bridge):
    client, _held, mode = bridge
    info = client.get("/api/runtime").json()
    assert info["mode"] == mode
    assert info["redirected"] is (mode == "sandbox")


def test_held_out_recording_is_refused_in_both_modes(bridge):
    client, held_id, _mode = bridge
    r = client.get(f"/api/channels/{held_id}")
    assert r.status_code == 423, r.text[:120]
    assert HELD_OUT_FILE in r.json()["detail"]
