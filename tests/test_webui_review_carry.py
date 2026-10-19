"""
test_webui_review_carry.py
==========================
review-carry (2026-10-18), the bridge half: Review shows an overlapping set of a
run's detections as ONE item (`members`, `memberBands`), a verdict on it writes
every member, carries to the same event found by other runs (`carried: N` on the
ack), the class label travels in the verdict body and comes back on the row,
and the queue header counts events and the detections behind them.

FastAPI lives only in `webui/.venv`; under the conda pytest this file skips.
"""
import os
import sqlite3
import sys

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

from Working.database import queries as _queries  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.review import queues as Q  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402

NOW = "2026-10-18T09:00:00"
N = 20000


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

    def det(run, a, b):
        return conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, 0.5)",
                            (run, a, b)).lastrowid
    d = {"a1": det(runs[0], 1000, 1100), "a2": det(runs[0], 1050, 1150), "a3": det(runs[0], 6000, 6100),
         "b1": det(runs[1], 1005, 1105), "b2": det(runs[1], 9000, 9100)}
    conn.commit()
    conn.close()
    return {"db": db, "runs": runs, "d": d, "rec": rec}


@pytest.fixture()
def seeded(tmp_path):
    info = _seed(tmp_path)
    rt = Runtime("sandbox", stamp="test-carry", db_source=info["db"], runtime_root=str(tmp_path / "runtime")).setup()
    Q.clear_resolver_cache()
    with TestClient(create_app(rt)) as client:
        yield client, rt, info
    rt.restore()


def _queue(client, run_id):
    r = client.post("/api/review/queues", json={"name": f"run {run_id}", "source_kind": "discovery-run",
                                                "filters": {"run_ids": [run_id]}})
    assert r.status_code == 200, r.text
    return r.json()["queue"]["id"]


def _adj(rt, did):
    conn = sqlite3.connect(rt.db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM adjudications WHERE detection_id = ?", (did,)).fetchone()
    finally:
        conn.close()


def test_a_queue_over_overlapping_windows_serves_one_item_per_set(seeded):
    client, rt, info = seeded
    d = info["d"]
    qa = _queue(client, info["runs"][0])
    got = client.get(f"/api/review/queues/{qa}").json()
    rows = got["rows"]
    assert [r["id"] for r in rows] == [str(d["a1"]), str(d["a3"])]
    assert rows[0]["members"] == [d["a1"], d["a2"]]
    assert [b["id"] for b in rows[0]["memberBands"]] == [str(d["a1"]), str(d["a2"])]
    assert rows[0]["memberBands"][1] == {"id": str(d["a2"]), "t0_s": 1050.0, "t1_s": 1150.0}
    assert got["queue"]["total"] == 2 and got["queue"]["detections"] == 3
    item = client.get(f"/api/review/queues/{qa}/items/{d['a1']}?px=200&pad_s=30").json()
    assert item["entry"]["members"] == [d["a1"], d["a2"]]
    assert item["queue"]["detections"] == 3
    listing = next(q for q in client.get("/api/review/queues").json() if q["id"] == qa)
    assert listing["total"] == 2 and listing["detections"] == 3
    counts = client.get(f"/api/review/queues/{qa}/counts").json()
    assert counts["total"] == 2 and counts["detections"] == 3


def test_a_verdict_writes_every_member_carries_and_the_second_run_no_longer_asks(seeded):
    client, rt, info = seeded
    d = info["d"]
    qa, qb = _queue(client, info["runs"][0]), _queue(client, info["runs"][1])
    before = [r["id"] for r in client.get(f"/api/review/queues/{qb}?include_judged=0").json()["rows"]]
    assert str(d["b1"]) in before
    ack = client.post(f"/api/review/queues/{qa}/verdict", json={"target_id": str(d["a1"]), "verdict": "interesting"})
    assert ack.status_code == 200, ack.text
    assert ack.json()["carried"] == 1
    assert _adj(rt, d["a1"])["verdict"] == _adj(rt, d["a2"])["verdict"] == "interesting"
    assert _adj(rt, d["b1"])["carried_from"] == _adj(rt, d["a1"])["id"]
    after = [r["id"] for r in client.get(f"/api/review/queues/{qb}?include_judged=0").json()["rows"]]
    assert str(d["b1"]) not in after and str(d["b2"]) in after
    # the carried row says where it came from
    item = client.get(f"/api/review/queues/{qb}/items/{d['b1']}?px=200&pad_s=30").json()
    assert item["entry"]["carriedFrom"] == d["a1"]
    assert item["entry"]["baseVerdict"] == "interesting"
    # undo takes back the members and the carried row
    assert client.post(f"/api/review/queues/{qa}/undo").status_code == 200
    assert _adj(rt, d["a1"]) is None and _adj(rt, d["a2"]) is None and _adj(rt, d["b1"]) is None


def test_a_batch_reports_what_it_carried(seeded):
    client, rt, info = seeded
    d = info["d"]
    qa = _queue(client, info["runs"][0])
    ack = client.post(f"/api/review/queues/{qa}/batch",
                      json={"target_ids": [str(d["a1"]), str(d["a3"])], "verdict": "not_interesting"})
    assert ack.status_code == 200, ack.text
    assert ack.json()["carried"] == 1
    assert _adj(rt, d["b1"])["verdict"] == "not_interesting"


def test_the_class_label_round_trips(seeded):
    client, rt, info = seeded
    d = info["d"]
    qa = _queue(client, info["runs"][0])
    ack = client.post(f"/api/review/queues/{qa}/verdict",
                      json={"target_id": str(d["a3"]), "verdict": "interesting", "class_label": "burst"})
    assert ack.status_code == 200, ack.text
    assert _adj(rt, d["a3"])["class_label"] == "burst"
    row = next(r for r in client.get(f"/api/review/queues/{qa}").json()["rows"] if r["id"] == str(d["a3"]))
    assert row["classLabel"] == "burst"
    item = client.get(f"/api/review/queues/{qa}/items/{d['a3']}?px=200&pad_s=30").json()
    assert item["entry"]["classLabel"] == "burst"
    bad = client.post(f"/api/review/queues/{qa}/verdict",
                      json={"target_id": str(d["a3"]), "verdict": "interesting", "class_label": "x" * 200})
    assert bad.status_code == 400, "an over-long class label is refused, not truncated"


def test_a_carried_row_is_seen_without_rebuilding_the_structure(seeded, monkeypatch):
    client, rt, info = seeded
    d = info["d"]
    qa, qb = _queue(client, info["runs"][0]), _queue(client, info["runs"][1])
    client.get(f"/api/review/queues/{qa}?thumbs=0")
    client.get(f"/api/review/queues/{qb}?thumbs=0")
    calls = {"n": 0}
    real = _queries.queue_candidates

    def counted(*a, **kw):
        calls["n"] += 1
        return real(*a, **kw)
    monkeypatch.setattr(_queries, "queue_candidates", counted)
    client.get(f"/api/review/queues/{qb}?thumbs=0")
    assert calls["n"] == 0
    assert client.post(f"/api/review/queues/{qa}/verdict",
                       json={"target_id": str(d["a1"]), "verdict": "interesting"}).json()["carried"] == 1
    n = calls["n"]
    row = next(r for r in client.get(f"/api/review/queues/{qb}?thumbs=0").json()["rows"] if r["id"] == str(d["b1"]))
    # the structure reads no adjudication: the carried row is laid over it fresh, and nothing is rebuilt
    assert calls["n"] == n, "a carried verdict rebuilt run B's remembered structure"
    assert row["judged"] is True
    assert client.get(f"/api/review/queues/{qb}/counts").json()["judged"] == 1


def test_a_picked_overlap_set_reads_as_one_item_in_discoverys_marks(seeded):
    """manager, review-carry merge: Discovery's picked marks map an overlap set's every member to the set's item.
    Before the fix a non-first member (a2) read "not asked" because the marks were keyed by the item's target id."""
    from server import discovery as disc
    client, rt, info = seeded
    d = info["d"]
    conn = sqlite3.connect(rt.db_path)
    conn.row_factory = sqlite3.Row
    try:
        qid = Q.create_queue(conn, name="picked", source_kind="discovery-run",
                             filters={"detection_ids": [d["a1"], d["a2"]]}, note=disc._picked_note(1))
        conn.commit()
        Q.clear_resolver_cache()
        assert disc._picked_states(conn, 1) == {d["a1"]: ("waiting", None), d["a2"]: ("waiting", None)}
    finally:
        conn.close()
    ack = client.post(f"/api/review/queues/{qid}/verdict", json={"target_id": str(d["a1"]), "verdict": "interesting"})
    assert ack.status_code == 200, ack.text
    conn = sqlite3.connect(rt.db_path)
    conn.row_factory = sqlite3.Row
    try:
        Q.clear_resolver_cache()
        assert disc._picked_states(conn, 1) == {d["a1"]: ("judged", "interesting"), d["a2"]: ("judged", "interesting")}
    finally:
        conn.close()
