"""
test_webui_db_lock.py
=====================
fixup-dblock, the route-level reproduction of the smoke walk's intermittent
``database is locked`` 500 on `POST /api/library/family/F-130/suspected-artifacts`
(AG Part 2 twice, AI once; the core half is `tests/test_db_write_lock.py`).

The walk's sequence, on `test_webui_cross_channel`'s synthetic recording: the
family is already classified (the real database the sandbox copies holds
F-130's classification, so AD's first state finds its flag line drawn and moves
on); a second *Classify across channels* job is started; while it is judging a
pair, *Send suspected artifacts to Review* is pressed. The pair's chance test is
slowed past SQLite's default 5 s busy timeout, as a busy machine slows it.

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_db_lock.py
"""

import os
import sqlite3
import sys
import threading

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui"), os.path.join(PROJECT_ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from fastapi.testclient import TestClient  # noqa: E402

import test_webui_cross_channel as base  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402

#: longer than SQLite's (and Python's) default 5 s busy timeout
SLOW_JUDGE_S = 6.5


@pytest.fixture
def client(tmp_path):
    db = base._db(tmp_path)
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")      # the real database is WAL; the sandbox copies it
    conn.close()
    rt = Runtime(mode="sandbox", stamp="20261007-db-lock", db_source=str(db),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(base._dist(tmp_path)))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            yield c
    finally:
        rt.restore()


def test_send_suspected_artifacts_while_a_classification_is_running_is_not_a_500(client, monkeypatch):
    base._classify(client)                     # F-01 classified once: two members flagged

    from Working.library import matching
    real_judge = matching._judge
    judging = threading.Event()
    calls = []

    def slow_judge(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            judging.set()
            threading.Event().wait(SLOW_JUDGE_S)
        return real_judge(*args, **kwargs)

    monkeypatch.setattr(matching, "_judge", slow_judge)
    r = client.post("/api/library/family/F-01/classify-cross-channel", json={"grouping": "g-01"})
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    assert judging.wait(60), "the second classification never reached a pair"

    r = client.post("/api/library/family/F-01/suspected-artifacts", json={"grouping": "g-01"})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Suspected artifact · F-01"

    snap = base._wait_job(client, job_id)
    assert snap["status"] == "completed", snap.get("error")
    # and the job polled meanwhile answered too: /api/jobs opens through init_db
    assert client.get("/api/jobs").status_code == 200
