"""
test_webui_explore_review.py
============================
explore-review (2026-10-18): Explore's two new write routes.

* ``POST /api/explore/span-review`` — the unjudged detections whose span
  intersects a window on the named channels go to ONE picked Review queue
  ("… · picked from Explore"), created on the first send and extended on every
  later one; what is already judged is counted and not added.
* ``POST /api/explore/artifact`` — one human ``annotations`` row with verdict
  ``artifact`` per selected channel over the window, and nothing else.

Both refuse the held-out recording while its lock is on, as every other
Explore write does (423).

FastAPI lives only in ``webui/.venv``; under the conda pytest this file skips.
Run it with

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_explore_review.py
"""

import datetime as _dt
import os
import sqlite3
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
from Working.review import queues as queues_mod  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import HELD_OUT_FILE, Runtime  # noqa: E402

FS, N = 1.0, 3000
NOW = "2026-10-18T09:00:00"

# detection id -> (recording id, start, end); recording 1 and 2 are syn.mat's two channels, 3 the held-out one
DETS = {
    1: (1, 100, 160),     # rec 1, outside the main window
    2: (1, 500, 560),     # rec 1, in the window, JUDGED
    3: (1, 1200, 1260),   # rec 1, in the window
    4: (2, 520, 580),     # rec 2, in the window
    5: (2, 2000, 2060),   # rec 2, a later window
    6: (1, 510, 540),     # rec 1, a SURROGATE run's span: never a detection
    7: (3, 500, 560),     # the held-out recording
}


def _db(tmp_path):
    db_dir = tmp_path / "db"; db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    rng = np.random.default_rng(0)
    for src, ch in (("syn.mat", 0), ("syn.mat", 1), (HELD_OUT_FILE, 0)):
        npy = tmp_path / f"{src[:-4]}_CH{ch}.npy"; np.save(npy, np.cumsum(rng.standard_normal(N)) * 0.01)
        conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                     "VALUES (?, ?, ?, ?, 0, ?)", (src, ch, FS, N, str(npy)))
    cfg = conn.execute("INSERT INTO configs (config_hash, config_json, created_at) VALUES ('c1', '{}', ?)", (NOW,)).lastrowid
    run = {}
    for rid in (1, 2, 3):
        run[rid] = conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
                                "VALUES (?, ?, 0, ?, ?, 'completed')", (cfg, rid, N, NOW)).lastrowid
    sur = conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status, surrogate_of_run_id) "
                       "VALUES (?, 1, 0, ?, ?, 'completed', ?)", (cfg, N, NOW, run[1])).lastrowid
    for did, (rid, a, b) in DETS.items():
        conn.execute("INSERT INTO detections (id, run_id, start_idx, end_idx, score, meta_json) VALUES (?, ?, ?, ?, 0.7, '{}')",
                     (did, sur if did == 6 else run[rid], a, b))
    conn.execute("INSERT INTO adjudications (detection_id, verdict, created_at) VALUES (2, 'interesting', ?)", (NOW,))
    conn.commit(); conn.close()
    return db


def _dist(tmp_path):
    dist = tmp_path / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    return dist


@pytest.fixture
def app(tmp_path):
    rt = Runtime(mode="sandbox", stamp="20261018-explore-review", db_source=str(_db(tmp_path)),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(_dist(tmp_path)))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            yield c, rt
    finally:
        rt.restore()


def _conn(rt):
    c = sqlite3.connect(rt.db_path)
    c.row_factory = sqlite3.Row
    return c


def _filter_ids(rt, qid):
    c = _conn(rt)
    try:
        return sorted(queues_mod.get_queue(c, qid)["filters"]["detection_ids"])
    finally:
        c.close()


def _counts(rt):
    c = _conn(rt)
    try:
        return {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("annotations", "adjudications", "detections", "review_queues", "runs")}
    finally:
        c.close()


# ── span-review ─────────────────────────────────────────────────────────────

def test_span_review_sends_exactly_the_unjudged_detections_in_the_window(app):
    client, rt = app
    r = client.post("/api/explore/span-review", json={"recording_ids": [1, 2], "t0_s": 400, "t1_s": 1300})
    assert r.status_code == 200, r.text
    body = r.json()
    # d2, d3, d4 intersect; d2 is judged; d1 is outside; d6 is a surrogate's and never counted
    assert body["total"] == 3
    assert body["added"] == 2 and body["already_judged"] == 1 and body["already_queued"] == 0
    assert sorted(body["added_ids"]) == [3, 4]
    assert _filter_ids(rt, body["queue_id"]) == [3, 4]
    assert "picked from Explore" in body["queue"]
    assert isinstance(body["message"], str) and "1 already judged" in body["message"]
    c = _conn(rt)
    try:
        q = queues_mod.get_queue(c, body["queue_id"])
        assert q["writes_to"] == "adjudications"          # rule 5: detections are judged in adjudications
        assert queues_mod.queue_counts(c, body["queue_id"])["remaining"] == 2
    finally:
        c.close()


def test_a_second_send_appends_to_the_same_picked_queue(app):
    client, rt = app
    first = client.post("/api/explore/span-review", json={"recording_ids": [1, 2], "t0_s": 400, "t1_s": 1300}).json()
    second = client.post("/api/explore/span-review", json={"recording_ids": [2], "t0_s": 1900, "t1_s": 2100})
    assert second.status_code == 200, second.text
    s = second.json()
    assert s["queue_id"] == first["queue_id"] and s["added"] == 1 and s["added_ids"] == [5]
    assert _filter_ids(rt, first["queue_id"]) == [3, 4, 5]
    again = client.post("/api/explore/span-review", json={"recording_ids": [1, 2], "t0_s": 400, "t1_s": 1300}).json()
    assert again["queue_id"] == first["queue_id"]
    assert again["added"] == 0 and again["already_queued"] == 2 and again["already_judged"] == 1
    assert _filter_ids(rt, first["queue_id"]) == [3, 4, 5]
    assert _counts(rt)["review_queues"] == 1


def test_a_window_with_no_detections_is_a_sentence_not_an_error(app):
    client, rt = app
    before = _counts(rt)
    r = client.post("/api/explore/span-review", json={"recording_ids": [1, 2], "t0_s": 2500, "t1_s": 2900})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["added"] == 0 and body["total"] == 0 and body["message"]
    assert _counts(rt) == before       # no queue made for nothing


def test_the_drawer_sends_named_detections_through_the_same_queue(app):
    client, rt = app
    r = client.post("/api/explore/span-review", json={"detection_ids": [1, 2]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["added_ids"] == [1] and body["already_judged"] == 1 and body["total"] == 2
    w = client.post("/api/explore/span-review", json={"recording_ids": [1], "t0_s": 400, "t1_s": 1300}).json()
    assert w["queue_id"] == body["queue_id"] and _filter_ids(rt, body["queue_id"]) == [1, 3]
    # a surrogate's span is not a detection anyone judges, and an unknown id is refused, writing nothing
    assert client.post("/api/explore/span-review", json={"detection_ids": [6]}).status_code == 422
    assert client.post("/api/explore/span-review", json={"detection_ids": [999]}).status_code == 422
    assert _filter_ids(rt, body["queue_id"]) == [1, 3]


def test_span_review_refuses_the_held_out_recording(app):
    client, rt = app
    before = _counts(rt)
    r = client.post("/api/explore/span-review", json={"recording_ids": [1, 3], "t0_s": 400, "t1_s": 1300})
    assert r.status_code == 423 and "held out" in r.text
    assert client.post("/api/explore/span-review", json={"detection_ids": [7]}).status_code == 423
    assert _counts(rt) == before


def test_span_review_refuses_a_malformed_window(app):
    client, _rt = app
    assert client.post("/api/explore/span-review", json={"recording_ids": [1], "t0_s": 500, "t1_s": 500}).status_code == 422
    assert client.post("/api/explore/span-review", json={"recording_ids": [], "t0_s": 0, "t1_s": 10}).status_code == 422
    assert client.post("/api/explore/span-review", json={"recording_ids": [404], "t0_s": 0, "t1_s": 10}).status_code == 404


# ── artifact ────────────────────────────────────────────────────────────────

def test_artifact_writes_one_artifact_annotation_per_channel_and_nothing_else(app):
    client, rt = app
    before = _counts(rt)
    r = client.post("/api/explore/artifact", json={"recording_ids": [1, 2], "t0_s": 400, "t1_s": 600, "note": "cable knock"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["ids"]) == 2 and body["verdict"] == "artifact"
    after = _counts(rt)
    assert after["annotations"] == before["annotations"] + 2
    assert {k: v for k, v in after.items() if k != "annotations"} == {k: v for k, v in before.items() if k != "annotations"}
    c = _conn(rt)
    try:
        rows = c.execute(f"SELECT * FROM annotations WHERE id IN ({','.join('?' * len(body['ids']))}) ORDER BY recording_id",
                         body["ids"]).fetchall()
    finally:
        c.close()
    assert [r["recording_id"] for r in rows] == [1, 2]
    for row in rows:
        assert row["verdict"] == "artifact" and row["source"] == "explore-cross-channel"
        assert (row["start_idx"], row["end_idx"]) == (400, 600) and row["note"] == "cable knock"
    spans = client.get("/api/channels/2/spans?t0=390&t1=610").json()
    assert any(a["verdict"] == "artifact" for a in spans["annotations"])


def test_artifact_refuses_held_out_and_an_empty_window_writing_nothing(app):
    client, rt = app
    before = _counts(rt)
    r = client.post("/api/explore/artifact", json={"recording_ids": [1, 3], "t0_s": 400, "t1_s": 600})
    assert r.status_code == 423 and "held out" in r.text
    assert client.post("/api/explore/artifact", json={"recording_ids": [1], "t0_s": 600, "t1_s": 600}).status_code == 422
    assert client.post("/api/explore/artifact", json={"recording_ids": [1], "t0_s": 4000, "t1_s": 5000}).status_code == 422
    assert client.post("/api/explore/artifact", json={"recording_ids": [], "t0_s": 0, "t1_s": 10}).status_code == 422
    assert _counts(rt) == before


# ── critic round (2026-10-18) ───────────────────────────────────────────────

def test_a_window_holding_too_many_unjudged_motifs_is_refused_writing_nothing(app, monkeypatch):
    """A whole-recording window on a busy channel would put tens of thousands of ids into one queue filter (a
    49k-id picked queue took 79 s to open in Review and 8 s on the queue list on a synthetic 16-channel DB). The
    route refuses a send above `SPAN_REVIEW_MAX` with a sentence naming the count, and writes nothing."""
    from server import explore_routes
    monkeypatch.setattr(explore_routes, "SPAN_REVIEW_MAX", 1)
    client, rt = app
    before = _counts(rt)
    r = client.post("/api/explore/span-review", json={"recording_ids": [1, 2], "t0_s": 400, "t1_s": 1300})
    assert r.status_code == 422, r.text
    msg = r.json()["detail"]["message"]
    assert "2 unjudged" in msg and "narrower" in msg
    assert client.post("/api/explore/span-review", json={"detection_ids": [1, 3]}).status_code == 422
    assert _counts(rt) == before
    # at the cap it goes through
    ok = client.post("/api/explore/span-review", json={"recording_ids": [2], "t0_s": 400, "t1_s": 1300})
    assert ok.status_code == 200 and ok.json()["added"] == 1


def test_a_detection_a_human_verdict_already_covers_is_reported_as_not_asked(app):
    """Review never serves a detection that is the same event as a span a person already judged (`prior_verdict`).
    The toast must not promise it: like Discovery's picked send, it is counted as *not asked*."""
    client, rt = app
    c = _conn(rt)
    try:
        c.execute("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
                  "VALUES (2, 2000, 2060, 'interesting', 'test', ?)", (NOW,))
        c.commit()
    finally:
        c.close()
    r = client.post("/api/explore/span-review", json={"recording_ids": [2], "t0_s": 1900, "t1_s": 2100})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["not_asked"] == 1 and body["unjudged_in_queue"] == 0
    assert "not asked" in body["message"] and "1 added" not in body["message"]


def test_artifact_reports_the_extent_it_wrote_clamped_to_the_channel(app):
    client, _rt = app
    r = client.post("/api/explore/artifact", json={"recording_ids": [1], "t0_s": 2900, "t1_s": 3500})
    assert r.status_code == 200, r.text
    assert (r.json()["start_s"], r.json()["end_s"]) == (2900, 3000)
