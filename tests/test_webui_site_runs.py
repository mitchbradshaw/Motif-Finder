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


def test_the_unjudged_count_is_what_send_would_queue_and_writes_nothing(client, monkeypatch):
    """The scoreboard over the real session (16 channels x 52 runs, 721 h) took 461 s cold on a copy of the real
    database, and the button printed "Send 0 unjudged" all that while. The count comes from its own read, which never
    scores (score_runs is made to explode here).

    Fix round F1 (the critic, 2026-10-20): it must be exactly what *Send* would queue -- Review's own count, over
    overlap sets (review-carry), with the items a human verdict already covers left out -- not raw detections minus
    adjudicated ones (50 of 54 runs disagreed on the real copy; dip_search_allch read 11 and queued 0). The case here
    has an overlap set, a detection with a prior human verdict, and one adjudicated detection; the route's answer
    before the send equals the send's own count, the route writes no queue, and after the send it reads the open
    queue's count."""
    out = _apply(client)
    from server import discovery as disc
    from Working.review import queues as Q
    monkeypatch.setattr(disc.SB, "score_runs", lambda *a, **k: (_ for _ in ()).throw(AssertionError("scored")))
    conn = sqlite3.connect(client.app.state.rt.db_path)
    conn.row_factory = sqlite3.Row
    try:
        dr = conn.execute("SELECT * FROM discovery_runs WHERE run_key = ? AND removed_at IS NULL ORDER BY id DESC",
                          (out["run_key"],)).fetchone()
        run_ids = [int(i) for i in disc._run_ids(conn, dr)]
        on_rec1 = conn.execute("SELECT id FROM runs WHERE id IN (" + ",".join(map(str, run_ids)) + ") "
                               "AND recording_id = 1 AND surrogate_of_run_id IS NULL").fetchone()[0]
        # an overlap set where no human has looked (4500..4600), and a detection a human verdict covers (PLANTS[0])
        conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, 4500, 4560, 1.0)", (on_rec1,))
        conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, 4530, 4600, 1.0)", (on_rec1,))
        conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, 600, 660, 1.0)", (on_rec1,))
        lone = conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, 5200, 5230, 1.0)",
                            (on_rec1,)).lastrowid
        conn.execute("INSERT INTO adjudications (detection_id, verdict, created_at) VALUES (?, 'interesting', ?)",
                     (lone, "2026-10-20T00:00:00+00:00"))
        conn.commit()
        queues_before = conn.execute("SELECT COUNT(*) FROM review_queues").fetchone()[0]
        n_det = conn.execute("SELECT COUNT(*) FROM detections d JOIN runs r ON r.id = d.run_id WHERE r.id IN ("
                             + ",".join(map(str, run_ids)) + ") AND r.surrogate_of_run_id IS NULL").fetchone()[0]
    finally:
        conn.close()

    r = client.get(f"/api/discovery/runs/{out['run_key']}/unjudged")
    assert r.status_code == 200, r.text
    before = r.json()
    conn = sqlite3.connect(client.app.state.rt.db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM review_queues").fetchone()[0] == queues_before,             "counting wrote a queue"
    finally:
        conn.close()
    assert before["queueId"] is None

    sent = client.post(f"/api/discovery/runs/{out['run_key']}/review", json={})
    assert sent.status_code == 200, sent.text
    sent = sent.json()
    assert (before["total"], before["judged"], before["unjudged"]) == (sent["total"], sent["judged"], sent["unjudged"])
    assert before["judged"] >= 1
    assert before["total"] < n_det, "the overlap set and the covered detection must make this differ from raw rows"

    # the case really holds an overlap set and a prior verdict
    conn = sqlite3.connect(client.app.state.rt.db_path)
    conn.row_factory = sqlite3.Row
    try:
        st = Q._detection_structure(conn, Q.get_queue(conn, sent["queue_id"]))
    finally:
        conn.close()
    assert any(len(Q._members(x)) > 1 for x in st) and any(x[7] is not None for x in st)

    after = client.get(f"/api/discovery/runs/{out['run_key']}/unjudged").json()
    assert after["queueId"] == sent["queue_id"]
    assert (after["total"], after["judged"], after["unjudged"]) == (sent["total"], sent["judged"], sent["unjudged"])


def test_the_unjudged_count_of_an_unknown_run_is_a_404(client):
    assert client.get("/api/discovery/runs/nope/unjudged").status_code == 404
