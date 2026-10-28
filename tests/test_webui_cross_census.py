"""
test_webui_cross_census.py
==========================
Cross-channel explorer S1: the census routes (`webui/server/cross_routes.py`).

- `POST /api/cross/census {source_file, detector?}` starts a `cross_census` job with real progress; 423 for the
  held-out file, 422 in words when the detector has no real run on every channel.
- `GET /api/cross/census?source_file=&detector=` returns the latest census (summary, hash, stale and why, whether
  the layout is known, the rules in words, the detectors offered with their reasons), or `census: null`.
- `GET /api/cross/census/{id}/cooccurrences?bin=&a=&b=&instant=&limit=&offset=` returns its rows.

The census route must not be swallowed by `GET /api/cross/{recording_id}` (an int path parameter).

Runs with webui/.venv (FastAPI).
"""

import os
import sys
import time

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui"), os.path.join(PROJECT_ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from fastapi.testclient import TestClient  # noqa: E402

import _cross_census_synthetic as syn  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402

M2 = "M2_aug_census_w.mat"
HELD = "M4_aug_concat_fs1.mat"


@pytest.fixture
def client(tmp_path):
    db_dir = tmp_path / "db"; db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    onsets = syn.every(6, 7200.0)
    plant = {0: [(t, k) for k, t in enumerate(onsets)], 1: [(t + 12.0, k) for k, t in enumerate(onsets)]}
    syn.build(conn, tmp_path, M2, 16, plant, hours=20)
    syn.build(conn, tmp_path, HELD, 16, {}, hours=1)
    conn.close()
    dist = tmp_path / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    rt = Runtime(mode="sandbox", stamp="20261028-cross-census", db_source=str(db),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(dist))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            yield c
    finally:
        rt.restore()


def _wait(client, job_id, timeout=240):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["status"] in ("completed", "failed", "cancelled"):
            return j
        time.sleep(0.3)
    raise AssertionError(f"job {job_id} did not finish in {timeout} s")


def test_no_census_yet_says_so_and_offers_the_detectors(client):
    r = client.get("/api/cross/census", params={"source_file": M2})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["census"] is None
    assert body["detector"] == "drop_detection_v1"
    offered = {d["detector"]: d for d in body["detectors"]}
    assert offered["drop_detection_v1"]["full"] is True and offered["drop_detection_v1"]["reason"] is None
    assert body["layoutKnown"] is True
    assert body["rules"]["bins"]["shared_driver"]


def test_the_held_out_file_is_refused(client):
    assert client.post("/api/cross/census", json={"source_file": HELD}).status_code == 423
    assert client.get("/api/cross/census", params={"source_file": HELD}).status_code == 423


def test_a_detector_that_is_not_full_is_refused_in_words(client):
    r = client.post("/api/cross/census", json={"source_file": M2, "detector": "drop_detection_v5"})
    assert r.status_code == 422
    assert "drop_detection_v5 has a real run on 0 of 16 channels" in r.text


def test_the_census_runs_as_a_job_and_is_read_back(client):
    r = client.post("/api/cross/census", json={"source_file": M2})
    assert r.status_code == 200, r.text
    ack = r.json()
    assert ack["kind"] == "cross_census"
    job = _wait(client, ack["job_id"])
    assert job["status"] == "completed", job.get("error")
    assert job["progress"]["total"] and job["progress"]["done"] == job["progress"]["total"]

    body = client.get("/api/cross/census", params={"source_file": M2}).json()
    c = body["census"]
    assert c is not None and c["hash"] and c["stale"] is False and c["staleWhy"] == []
    assert c["summary"]["bins"]["propagation"] == 6
    (pair,) = [p for p in c["summary"]["pairs"] if p["n"] == 6]
    assert pair["timetable"]["count"] == 6

    rows = client.get(f"/api/cross/census/{c['id']}/cooccurrences", params={"bin": "propagation"}).json()
    assert rows["total"] == 6 and len(rows["rows"]) == 6
    assert {row["bin"] for row in rows["rows"]} == {"propagation"}
    page = client.get(f"/api/cross/census/{c['id']}/cooccurrences", params={"limit": 2, "offset": 0}).json()
    assert len(page["rows"]) == 2


def test_an_unknown_census_is_a_404(client):
    assert client.get("/api/cross/census/99999/cooccurrences").status_code == 404


def test_the_old_window_route_still_answers(client):
    rid = client.get("/api/layout/" + M2).json()["channels"]
    first = sorted(int(k) for k in rid)[0]
    assert client.get(f"/api/cross/{first}", params={"t0": 0, "t1": 600}).status_code == 200
