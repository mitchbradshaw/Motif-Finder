"""
test_webui_review_momentum.py
=============================
AS (2026-11-24), the bridge half: what lets Review feed the next candidate first and save the verdicts behind it.

* `POST /queues/{qid}/verdicts` saves an ordered list: one audit row per verdict, in the list's order (undo still
  reverses one gesture at a time), a refused verdict refused alone, the queue's counts once after the last.
* A verdict carries a client id. One whose id is already among the queue's audit rows is answered with the original
  ack and not written again - two tabs, or a replayed journal racing a slow POST, cannot double a verdict.
* `GET /queues/{qid}/items?ids=` reads several items in one request (the queue's verdict overlay once, not per item),
  each exactly as the single read serves it.
* `GET /queues/{qid}/carries?ids=` answers several carries at once (one poller on the page, not one per verdict).
* The carry worker yields to page requests (`corpus.wait_for_quiet`), capped, so carries keep up and still run during
  a long burst.

FastAPI lives only in `webui/.venv`; under the conda pytest this file skips.
"""
import os
import sqlite3
import sys
import time

import numpy as np
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
from Working.review import queues as Q  # noqa: E402
from server import corpus  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402

NOW = "2026-11-24T09:00:00"
N = 40000


def _seed(tmp_path):
    npy = tmp_path / "npy"
    npy.mkdir()
    (tmp_path / "db").mkdir()
    db = str(tmp_path / "db" / "annotations.sqlite")
    conn = init_db(db)
    path = str(npy / "ch0.npy")
    np.save(path, (0.2 * np.sin(np.arange(N) / 97.0)).astype(np.float32))
    rec = conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                       "VALUES ('M2_aug_concat_fs1.mat', 0, 1.0, ?, 0, ?)", (N, path)).lastrowid
    cfg = conn.execute("INSERT INTO configs (config_hash, config_json, created_at) VALUES ('c', '{}', ?)",
                       (NOW,)).lastrowid
    runs = [conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
                         "VALUES (?, ?, 0, ?, ?, 'ok')", (cfg, rec, N, NOW)).lastrowid for _ in range(2)]
    a = [conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, 0.5)",
                      (runs[0], 1000 + k * 1500, 1100 + k * 1500)).lastrowid for k in range(8)]
    # the second run finds the same events as the first's first three: their verdicts carry there
    b = [conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, 0.5)",
                      (runs[1], 1005 + k * 1500, 1105 + k * 1500)).lastrowid for k in range(3)]
    conn.commit()
    conn.close()
    return {"db": db, "runs": runs, "a": a, "b": b}


@pytest.fixture()
def seeded(tmp_path):
    info = _seed(tmp_path)
    rt = Runtime("sandbox", stamp="test-momentum", db_source=info["db"], runtime_root=str(tmp_path / "runtime")).setup()
    Q.clear_resolver_cache()
    with TestClient(create_app(rt)) as client:
        yield client, rt, info
    rt.restore()


def _queue(client, run_id):
    r = client.post("/api/review/queues", json={"name": f"run {run_id}", "source_kind": "discovery-run",
                                                "filters": {"run_ids": [run_id]}})
    assert r.status_code == 200, r.text
    return r.json()["queue"]["id"]


def _audit(rt, qid):
    conn = sqlite3.connect(rt.db_path)
    try:
        return conn.execute("SELECT id, action, target_ids, undone_at FROM review_audit WHERE queue_id = ? ORDER BY id",
                            (qid,)).fetchall()
    finally:
        conn.close()


def _v(did, verdict="not_interesting", cid=None):
    return {"client_id": cid or f"c-{did}-{verdict}", "target_id": str(did), "verdict": verdict}


# ── the ordered bulk save ────────────────────────────────────────────────────

def test_a_bulk_save_writes_each_verdict_in_order_under_its_own_audit_row(seeded):
    client, rt, info = seeded
    qa = _queue(client, info["runs"][0])
    ids = info["a"][:5]
    r = client.post(f"/api/review/queues/{qa}/verdicts", json={"verdicts": [_v(d) for d in ids]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [x["ok"] for x in body["results"]] == [True] * 5
    assert [x["client_id"] for x in body["results"]] == [f"c-{d}-not_interesting" for d in ids]
    assert body["counts"]["judged"] == 5 and body["counts"]["total"] == 8
    rows = _audit(rt, qa)
    assert [r[1] for r in rows] == ["verdict"] * 5, "a bulk save wrote one audit row for several gestures"
    assert [r[2] for r in rows] == [f"[{d}]" for d in ids], "the audit rows are not in the gestures' order"
    # undo reverses ONE gesture: the last of the list
    u = client.post(f"/api/review/queues/{qa}/undo")
    assert u.status_code == 200, u.text
    rows = _audit(rt, qa)
    assert [r[3] is not None for r in rows[:5]] == [False, False, False, False, True]


def test_a_refused_verdict_in_the_list_is_refused_alone_and_the_rest_are_written(seeded):
    client, rt, info = seeded
    qa = _queue(client, info["runs"][0])
    a = info["a"]
    lst = [_v(a[0]), {"client_id": "bad-1", "target_id": "999999", "verdict": "not_interesting"},
           _v(a[1]), {"client_id": "bad-2", "target_id": str(a[2]), "verdict": "not_a_verdict"}, _v(a[3])]
    r = client.post(f"/api/review/queues/{qa}/verdicts", json={"verdicts": lst})
    assert r.status_code == 200, r.text
    res = r.json()["results"]
    assert [x["ok"] for x in res] == [True, False, True, False, True]
    assert res[1]["status"] in (400, 404) and "999999" in res[1]["error"], "the refusal does not name what it refused"
    assert res[3]["status"] == 400
    assert [r[2] for r in _audit(rt, qa)] == [f"[{a[0]}]", f"[{a[1]}]", f"[{a[3]}]"]


def test_a_bulk_save_queues_each_carry_and_the_carries_are_answered_together(seeded):
    client, rt, info = seeded
    qa = _queue(client, info["runs"][0])
    a = info["a"]
    r = client.post(f"/api/review/queues/{qa}/verdicts", json={"verdicts": [_v(a[0]), _v(a[1]), _v(a[5])]})
    res = r.json()["results"]
    assert all(x["carryPending"] for x in res) and all(x["carried"] == 0 for x in res)
    ids = [x["carryAuditId"] for x in res]
    assert client.app.state.carry.flush(), "the carry worker did not finish"
    st = client.get(f"/api/review/queues/{qa}/carries?ids={','.join(map(str, ids))}")
    assert st.status_code == 200, st.text
    got = {s["auditId"]: s for s in st.json()["carries"]}
    assert set(got) == set(ids) and not any(s["pending"] for s in got.values())
    assert got[ids[0]]["carried"] == 1 and got[ids[1]]["carried"] == 1 and got[ids[2]]["carried"] == 0


# ── exactly once ────────────────────────────────────────────────────────────

def test_a_verdict_sent_twice_is_written_once_and_answered_with_the_original_ack(seeded):
    client, rt, info = seeded
    qa = _queue(client, info["runs"][0])
    a = info["a"]
    first = client.post(f"/api/review/queues/{qa}/verdicts", json={"verdicts": [_v(a[0], cid="x-1"), _v(a[1], cid="x-2")]}).json()
    again = client.post(f"/api/review/queues/{qa}/verdicts", json={"verdicts": [_v(a[1], cid="x-2"), _v(a[2], cid="x-3")]}).json()
    assert len(_audit(rt, qa)) == 3, "a verdict replayed with its client id was written again"
    assert again["results"][0]["ok"] and again["results"][0]["duplicate"] is True
    assert again["results"][0]["auditId"] == first["results"][1]["auditId"], "the duplicate is not answered with the original"
    assert again["results"][1].get("duplicate") is not True
    # the single-verdict route keeps the same rule, and an undone verdict replayed is not written again either
    one = client.post(f"/api/review/queues/{qa}/verdict", json={**_v(a[3], cid="y-1")}).json()
    client.post(f"/api/review/queues/{qa}/undo")
    rep = client.post(f"/api/review/queues/{qa}/verdict", json={**_v(a[3], cid="y-1")}).json()
    assert rep.get("duplicate") is True and rep["auditId"] == one["auditId"]
    rows = _audit(rt, qa)
    assert len(rows) == 4 and rows[-1][3] is not None, "the replayed verdict undid the undo"


# ── reads in one request ─────────────────────────────────────────────────────

def test_several_items_are_read_in_one_request_exactly_as_one_at_a_time(seeded):
    client, rt, info = seeded
    qa = _queue(client, info["runs"][0])
    a = info["a"]
    client.post(f"/api/review/queues/{qa}/verdict", json=_v(a[1]))
    want = [a[0], a[2], a[3]]
    r = client.get(f"/api/review/queues/{qa}/items?ids={','.join(map(str, want))},888888&px=200&pad_s=30")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    for d in want:
        one = client.get(f"/api/review/queues/{qa}/items/{d}?px=200&pad_s=30").json()
        assert items[str(d)] == one, f"the batched read of {d} differs from its own read"
    assert items["888888"]["status"] == 404 and "888888" in items["888888"]["error"], \
        "an id not in the queue was not refused by name"


# ── the carry worker yields to the page ──────────────────────────────────────

def test_the_carry_worker_waits_for_a_quiet_moment_but_not_for_ever(seeded, monkeypatch):
    client, rt, info = seeded
    qa = _queue(client, info["runs"][0])
    worker = client.app.state.carry
    assert worker.flush()
    from server import review_carry
    assert hasattr(review_carry, "QUIET_S") and hasattr(review_carry, "MAX_YIELD_S")
    monkeypatch.setattr(review_carry, "MAX_YIELD_S", 1.5)
    ack = client.post(f"/api/review/queues/{qa}/verdict", json=_v(info["a"][0])).json()
    aid = ack["carryAuditId"]
    corpus.REQUEST_CLOCK["inflight"] += 1          # a page read in flight
    try:
        time.sleep(0.6)
        conn = sqlite3.connect(rt.db_path)
        try:
            from Working.review import verdicts as V
            held_off = V.carry_status(conn, aid)["pending"]
        finally:
            conn.close()
        assert held_off, "the carry ran while a page read was in flight"
        assert worker.flush(timeout=10), "the carry waited for a quiet moment for ever"
    finally:
        corpus.REQUEST_CLOCK["inflight"] -= 1
