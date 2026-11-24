"""
test_webui_autodetect.py
========================
Auto-detect's routes (2026-11-23): a run is an ``autodetect`` job whose result lands in the sandbox's results
folder; a second press on a running channel is refused; the held-out recording is refused while the lock is on; the
page reads the result and the channel's samples; a send to Review writes a listed detection queue and candidate
sequences. The run itself is stood in for (`service.run` takes minutes on a real channel; `tests/
test_autodetect_service.py` and the reference runs cover it).
"""

import base64
import os
import sqlite3
import sys
import threading
import time

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from fastapi.testclient import TestClient  # noqa: E402

from Working.autodetect import service  # noqa: E402
from Working.autodetect.pipeline import AutoDetectResult  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import HELD_OUT_FILE, Runtime  # noqa: E402

N = 4000


def _db(tmp_path):
    db_dir = tmp_path / "db"; db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    rng = np.random.default_rng(0)
    for src in ("syn.mat", HELD_OUT_FILE):
        npy = tmp_path / f"{src[:-4]}.npy"
        np.save(npy, np.cumsum(rng.standard_normal(N)) * 0.01)
        conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path, units) "
                     "VALUES (?, 0, 1.0, ?, 0, ?, 'mV')", (src, N, str(npy)))
    conn.commit()
    conn.close()
    return db


def _dist(tmp_path):
    dist = tmp_path / "dist"; dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    return dist


def _fake_run(gate=None):
    def run(conn, rec, x, *, start_idx=0, end_idx=None, on_progress=None, cancelled=None, **kw):
        if on_progress:
            on_progress(0.5, "the signal: boxes", 30.0)
        if gate is not None:
            assert gate.wait(10)
        a, b = int(start_idx), int(end_idx if end_idx is not None else len(x))
        c = pd.DataFrame({"candidate_id": [0, 1, 2], "start": [10, 200, 900], "end": [40, 260, 930],
                          "confidence": [0.9, 0.6, 0.2], "p_r4": [0.8, 0.5, 0.2], "kind": "proposal",
                          "sources": ["seed", "event_rule", ""], "sequence_id": [-1, -1, -1],
                          "polarity": ["drop", "spike", "drop"], "depth_mv": [1.0, 0.5, 0.2], "onset": [12, 205, 905],
                          "extremum": [20, 210, 910], "event_end": [35, 250, 925], "recovered": True,
                          "run": ["normal", "inverted", "normal"], "runs": ["normal", "both", "normal"],
                          "sharpness": [12.0, 30.0, 2.0], "member_variants": ["seed__F-01", "event_rule", ""],
                          "lifts": "[]", "scan_p": np.nan})
        res = AutoDetectResult(candidates=c, sequences=pd.DataFrame(columns=["sequence_id", "start", "end"]),
                               proposals=pd.DataFrame(), scan_windows=0, scan_hits=pd.DataFrame(), timings={}, info={})
        meta = {"version": "v4", "recording": {k: rec[k] for k in ("id", "source_file", "channel", "fs", "units",
                                                                     "n_samples")},
                "stretch": {"start_idx": a, "end_idx": b, "n_samples": b - a}, "floor_mv": 0.1, "floor_source": "t",
                "missing_detectors": [], "wall_s": 1.0, "timings": {}, "scan_windows": 0, "info": {},
                "whole_drop": {}, "created_at": "2026-11-23T23:00:00"}
        return res, meta
    return run


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "setup", lambda conn, **kw: {"ready": True, "problems": [], "missing_detectors": [],
                                                              "version": "v4", "rules": {}, "seconds_per_sample": 2.6e-4})
    rt = Runtime(mode="sandbox", stamp="20261123-autodetect", db_source=str(_db(tmp_path)),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(_dist(tmp_path)))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            yield c, rt
    finally:
        rt.restore()


def _wait(c, job_id, timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = c.get(f"/api/jobs/{job_id}").json()
        if j["status"] in ("completed", "failed", "cancelled"):
            return j
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish")


def test_a_run_lands_in_the_sandbox_and_the_page_reads_it(app, monkeypatch):
    c, rt = app
    monkeypatch.setattr(service, "run", _fake_run())
    r = c.post("/api/autodetect/runs", json={"recording_id": 1, "t0_s": 1000, "t1_s": 3000})
    assert r.status_code == 200, r.text
    job = _wait(c, r.json()["job_id"])
    assert job["status"] == "completed" and job["kind"] == "autodetect", job
    out = service.result_dir(job["job_id"], os.path.join(rt.results_dir, "autodetect"))
    assert os.path.isfile(os.path.join(out, "run.json"))                  # inside the runtime, never DATA/
    listed = c.get("/api/autodetect/runs?recording_id=1").json()
    assert [x["job_id"] for x in listed["results"]] == [job["job_id"]] and listed["running"] is None
    body = c.get(f"/api/autodetect/runs/{job['job_id']}").json()
    assert body["start_idx"] == 1000 and body["n"] == 2000 and body["candidates"]["s"] == [10, 200, 900]
    # what Review can match a sent candidate against: this recording's own judged spans (none in the fixture)
    assert body["judged_here"] == 0
    sig = c.get("/api/autodetect/signal/1?start_idx=1000&end_idx=3000").json()
    q = np.frombuffer(base64.b64decode(sig["b64"]), dtype=np.int16)
    assert len(q) == sig["n"] == 2000 and sig["unit"] == "mV"
    x = np.load(c.get("/api/channels/1").json()["npy_path"])[1000:3000]
    np.testing.assert_allclose(q * sig["scale"] + sig["offset"], x, atol=sig["scale"])


def test_a_second_press_on_a_running_channel_is_refused(app, monkeypatch):
    c, _rt = app
    gate = threading.Event()
    monkeypatch.setattr(service, "run", _fake_run(gate))
    first = c.post("/api/autodetect/runs", json={"recording_id": 1}).json()["job_id"]
    again = c.post("/api/autodetect/runs", json={"recording_id": 1})
    assert again.status_code == 409 and again.json()["detail"]["job_id"] == first
    t0 = time.time()
    while time.time() - t0 < 10:            # the job's thread posts its first progress a moment after the start
        running = c.get("/api/autodetect/runs?recording_id=1").json()["running"]
        if running["progress"]["total"] == 1000:
            break
        time.sleep(0.05)
    assert running["job_id"] == first and running["progress"]["total"] == 1000
    assert "left" in running["progress"]["message"]
    gate.set()
    assert _wait(c, first)["status"] == "completed"


def test_the_held_out_recording_and_a_bad_stretch_are_refused(app):
    c, _rt = app
    assert c.post("/api/autodetect/runs", json={"recording_id": 2}).status_code == 423
    assert c.get("/api/autodetect/signal/2").status_code == 423
    assert c.post("/api/autodetect/runs", json={"recording_id": 1, "t0_s": 3000, "t1_s": 1000}).status_code == 422
    assert c.post("/api/autodetect/runs", json={"recording_id": 99}).status_code == 404
    assert c.get("/api/autodetect/runs/12345").status_code == 404


def test_a_send_makes_a_listed_detection_queue_of_machine_rows(app, monkeypatch):
    c, rt = app
    monkeypatch.setattr(service, "run", _fake_run())
    job = _wait(c, c.post("/api/autodetect/runs", json={"recording_id": 1, "t0_s": 1000}).json()["job_id"])
    assert c.post(f"/api/autodetect/runs/{job['job_id']}/send", json={"polarities": ["up"]}).status_code == 422
    got = c.post(f"/api/autodetect/runs/{job['job_id']}/send", json={"min_confidence": 0.5}).json()
    assert got["detections"] == 2 and got["queue_id"]
    conn = sqlite3.connect(rt.db_path)
    try:
        spans = conn.execute("SELECT start_idx, end_idx FROM detections ORDER BY start_idx").fetchall()
        assert spans == [(1010, 1040), (1200, 1260)]
        assert conn.execute("SELECT source_kind FROM review_queues WHERE id = ?", (got["queue_id"],)).fetchone()[0] \
            == "discovery-run"
        assert conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0] == 0
    finally:
        conn.close()
    assert c.get(f"/api/review/queues/{got['queue_id']}").status_code == 200
    body = c.get(f"/api/autodetect/runs/{job['job_id']}").json()
    assert body["sent"][0]["queue_id"] == got["queue_id"]
