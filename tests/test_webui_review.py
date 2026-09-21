"""
test_webui_review.py
====================
Route-level guarantees of the Review bridge (`webui/server/review.py`,
stage-3 Prompt 05). What the page cannot be trusted to catch:

* every route answers, with the keys `webui/client/src/api/review.ts` declares
  on `ItemDetail` — a missing key renders as `undefined`, which draws as an
  empty panel rather than as an error;
* a verdict written through the route lands in the table the queue's
  `writes_to` names **and nowhere else** — CLAUDE.md rule 5, checked by
  counting the *other* table's rows before and after;
* undo reverses the write;
* a batch of N is ONE `review_audit` row, not N indistinguishable ones;
* the held-out recording is refused.

FastAPI lives only in `webui/.venv`, so under the conda `pytest` this file
skips; run it with

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_review.py
"""

import json
import os
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

from Working.database.schema import init_db  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import HELD_OUT_FILE, Runtime  # noqa: E402

FS = 1.0
N_SAMPLES = 20000


def _write_channel(dir_path, name, n=N_SAMPLES):
    t = np.arange(n, dtype=float)
    x = 0.2 * np.sin(t / 97.0) + 0.02 * np.cos(t / 7.0)
    path = os.path.join(dir_path, f"{name}.npy")
    np.save(path, x.astype(np.float32))
    return path


def _seed(tmp_path):
    """One recording with two channels, one held-out recording, one run with
    six detections on each — enough for a discovery-run queue."""
    npy_dir = tmp_path / "npy"
    npy_dir.mkdir()
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))

    rec_ids = []
    for ch in range(2):
        path = _write_channel(str(npy_dir), f"norm_{ch}")
        rec_ids.append(conn.execute(
            "INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
            "VALUES ('M2_aug_concat_fs1.mat', ?, ?, ?, 0, ?)", (ch, FS, N_SAMPLES, path)).lastrowid)
    held_path = _write_channel(str(npy_dir), "held")
    held_rec = conn.execute(
        "INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
        "VALUES (?, 0, ?, ?, 0, ?)", (HELD_OUT_FILE, FS, N_SAMPLES, held_path)).lastrowid

    cfg = conn.execute(
        "INSERT INTO configs (config_hash, config_json, created_at) "
        "VALUES ('cfg-review', '{}', '2026-09-22T09:00:00')").lastrowid
    run_ids, det_ids = [], []
    for rid in rec_ids:
        run = conn.execute(
            "INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
            "VALUES (?, ?, 0, ?, '2026-09-22T09:00:00', 'ok')", (cfg, rid, N_SAMPLES)).lastrowid
        run_ids.append(run)
        for k in range(3):
            a = 1000 + k * 600
            det_ids.append(conn.execute(
                "INSERT INTO detections (run_id, start_idx, end_idx, score, meta_json) "
                "VALUES (?, ?, ?, ?, ?)", (run, a, a + 40, 0.9 - 0.01 * k, json.dumps({}))).lastrowid)
    held_run = conn.execute(
        "INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
        "VALUES (?, ?, 0, ?, '2026-09-22T09:00:00', 'ok')", (cfg, held_rec, N_SAMPLES)).lastrowid
    held_det = conn.execute(
        "INSERT INTO detections (run_id, start_idx, end_idx, score, meta_json) "
        "VALUES (?, 500, 560, 0.7, '{}')", (held_run,)).lastrowid
    conn.commit()
    conn.close()
    return {"db": str(db), "recordings": rec_ids, "held_recording": held_rec,
            "runs": run_ids, "detections": det_ids, "held_detection": held_det}


@pytest.fixture()
def seeded(tmp_path):
    info = _seed(tmp_path)
    rt = Runtime("sandbox", stamp="test-review", db_source=info["db"],
                 runtime_root=str(tmp_path / "runtime")).setup()
    app = create_app(rt)
    with TestClient(app) as client:
        yield client, rt, info
    rt.restore()


def _rows(rt, table):
    import sqlite3
    conn = sqlite3.connect(rt.db_path)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def _make_queue(client, info, **kw):
    body = {"name": "Discovery · review test", "source_kind": "discovery-run",
            "source_ref": str(info["runs"][0])}
    body.update(kw)
    r = client.post("/api/review/queues", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# ── the routes answer ───────────────────────────────────────────────────────

def test_counts_and_queues_answer(seeded):
    client, rt, info = seeded
    counts = client.get("/api/review/counts")
    assert counts.status_code == 200, counts.text
    assert "need_you" in counts.json() and "by_queue" in counts.json()

    q = _make_queue(client, info)
    assert q["queue"]["writes"] == "adjudications"
    assert q["queue"]["unit"] == "detection"
    assert q["queue"]["blind"] is False

    listing = client.get("/api/review/queues")
    assert listing.status_code == 200, listing.text
    assert any(x["queue"]["id"] == q["queue"]["id"] for x in listing.json()["queues"])

    one = client.get(f"/api/review/queues/{q['queue']['id']}")
    assert one.status_code == 200, one.text
    assert one.json()["rows"], "a discovery-run queue over a seeded run must resolve rows"


def test_item_detail_carries_the_client_shape(seeded):
    client, rt, info = seeded
    q = _make_queue(client, info)
    qid = q["queue"]["id"]
    row = client.get(f"/api/review/queues/{qid}").json()["rows"][0]
    item = client.get(f"/api/review/queues/{qid}/items/{row['id']}")
    assert item.status_code == 200, item.text
    d = item.json()
    for key in ("entry", "queue", "context", "shape", "nearest", "medoids",
                "artifact", "evidence", "thumb"):
        assert key in d, f"ItemDetail.{key} missing: the panel would draw blank"
    assert "values" in d["context"] and "t0_s" in d["context"]
    assert d["context"]["values"], "context trace must be real decimated mV, never empty"


# ── rule 5: the verdict lands in one table and not the other ────────────────

def test_verdict_lands_in_adjudications_and_not_annotations(seeded):
    client, rt, info = seeded
    q = _make_queue(client, info)
    qid = q["queue"]["id"]
    row = client.get(f"/api/review/queues/{qid}").json()["rows"][0]
    before_h = _rows(rt, "annotations")
    before_m = _rows(rt, "adjudications")

    r = client.post(f"/api/review/queues/{qid}/verdict",
                    json={"target_id": row["id"], "verdict": "interesting"})
    assert r.status_code == 200, r.text
    assert _rows(rt, "adjudications") == before_m + 1
    assert _rows(rt, "annotations") == before_h, "a machine adjudication must never become a human row"

    undo = client.post(f"/api/review/queues/{qid}/undo")
    assert undo.status_code == 200, undo.text
    assert _rows(rt, "adjudications") == before_m, "undo must reverse the write"


def test_batch_is_one_audit_row(seeded):
    client, rt, info = seeded
    q = _make_queue(client, info)
    qid = q["queue"]["id"]
    rows = client.get(f"/api/review/queues/{qid}").json()["rows"]
    assert len(rows) >= 3
    before_audit = _rows(rt, "review_audit")
    targets = [x["id"] for x in rows[:3]]
    r = client.post(f"/api/review/queues/{qid}/batch",
                    json={"target_ids": targets, "verdict": "not_interesting"})
    assert r.status_code == 200, r.text
    assert _rows(rt, "review_audit") == before_audit + 1, "a batch is ONE audit row, not N"


def test_held_out_item_is_refused(seeded):
    client, rt, info = seeded
    q = _make_queue(client, info, name="held", source_ref=None,
                    source_kind="discovery-run")
    qid = q["queue"]["id"]
    item = client.get(f"/api/review/queues/{qid}/items/d-{info['held_detection']}")
    assert item.status_code in (200, 423), item.text
    if item.status_code == 200:
        assert item.json().get("refused"), "a held-out recording must be refused, not served"
