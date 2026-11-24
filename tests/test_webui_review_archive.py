"""
test_webui_review_archive.py
============================
The bridge's half of the queue archive (2026-11-24): ``POST /api/review/queues/{id}/archive`` takes a queue out of
Review's list and the header's count; ``GET /api/review/queues?archived=only`` is the Jobs page's *Archived queues*
block; ``POST /api/review/queues/{id}/restore`` puts it back. The core's rules are in `tests/test_review_archive.py`.
"""

import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from fastapi.testclient import TestClient  # noqa: E402

from Working.database.schema import init_db  # noqa: E402
from Working.review import queues as Q  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402


def _db(tmp_path):
    db_dir = tmp_path / "db"; db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    ids = {}
    for name, n in (("keep", 2), ("old", 3)):
        rid = conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                           "VALUES (?, 0, 1.0, 10000, 0, 'x.npy')", (f"{name}.mat",)).lastrowid
        cid = conn.execute("INSERT INTO configs (config_hash, config_json, created_at) VALUES (?, '{}', "
                           "'2026-01-01T00:00:00')", (f"h-{name}",)).lastrowid
        run = conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
                           "VALUES (?, ?, 0, 10000, '2026-01-01T00:00:00', 'done')", (cid, rid)).lastrowid
        dets = [conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, 0.9)",
                             (run, 1000 * k, 1000 * k + 50)).lastrowid for k in range(n)]
        conn.commit()
        ids[name] = Q.create_queue(conn, name=name, source_kind="discovery-run", filters={"detection_ids": dets})
    conn.close()
    return db, ids


@pytest.fixture
def app(tmp_path):
    db, ids = _db(tmp_path)
    dist = tmp_path / "dist"; dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    rt = Runtime(mode="sandbox", stamp="20261124-archive", db_source=str(db), runtime_root=str(tmp_path / "runtime"),
                 client_dist=str(dist))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            yield c, ids
    finally:
        rt.restore()


def _ids(rows):
    return sorted(int(r["id"]) for r in rows)


def test_archive_moves_a_queue_out_of_review_and_restore_brings_it_back(app):
    c, ids = app
    keep, old = ids["keep"], ids["old"]
    assert _ids(c.get("/api/review/queues").json()) == sorted([keep, old])
    assert c.get("/api/review/counts").json()["need_you"] == 5

    r = c.post(f"/api/review/queues/{old}/archive")
    assert r.status_code == 200 and r.json()["changed"] is True and r.json()["queue"]["archived_at"]
    assert _ids(c.get("/api/review/queues").json()) == [keep]
    archived = c.get("/api/review/queues?archived=only").json()
    assert _ids(archived) == [old] and archived[0]["total"] == 3          # the block shows its counts
    assert _ids(c.get("/api/review/queues?archived=include").json()) == sorted([keep, old])
    assert c.get("/api/review/counts").json()["need_you"] == 2
    assert c.get(f"/api/review/queues/{old}").status_code == 200            # a direct link still opens it
    assert c.post(f"/api/review/queues/{old}/archive").json()["changed"] is False

    r = c.post(f"/api/review/queues/{old}/restore")
    assert r.status_code == 200 and r.json()["changed"] is True and r.json()["queue"]["archived_at"] is None
    assert _ids(c.get("/api/review/queues").json()) == sorted([keep, old])
    assert c.get("/api/review/queues?archived=only").json() == []
    assert c.get("/api/review/counts").json()["need_you"] == 5


def test_an_unknown_queue_and_a_bad_filter_are_refused(app):
    c, _ids_ = app
    assert c.post("/api/review/queues/9999/archive").status_code == 404
    assert c.post("/api/review/queues/9999/restore").status_code == 404
    assert c.get("/api/review/queues?archived=sometimes").status_code == 422
