"""
test_webui_family_queue.py
==========================
Library › Family *Send N to Review as a queue*, the routes: `POST
/api/library/family/{id}/unjudged-queue` makes (once) a `library-family`
queue over the unjudged members the page shows; the family read carries the
open queue so the page can say *Open in Review · j of n judged*; a verdict
given in Review lands over the member's span and the family read then counts
that member judged. Review serves the item as an ordinary member item — no
suspected-artifact card, which belongs to the other member-unit queue.

Reuses `test_webui_cross_channel`'s synthetic recording: four members of
F-01, none with a detection, none judged.

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_family_queue.py
"""

import os
import sys

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

ROUTE = "/api/library/family/F-01/unjudged-queue"


@pytest.fixture
def client(tmp_path):
    db = base._db(tmp_path)
    rt = Runtime(mode="sandbox", stamp="20261009-family-queue", db_source=str(db),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(base._dist(tmp_path)))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            yield c
    finally:
        rt.restore()


def _family(client):
    r = client.get("/api/library/family/F-01", params={"floor": 0})
    assert r.status_code == 200, r.text
    return r.json()["detail"]


def _send(client):
    r = client.post(ROUTE, json={"grouping": "g-01", "floor": "0"})
    assert r.status_code == 200, r.text
    return r.json()


def test_send_unjudged_makes_one_queue_over_the_members_shown(client):
    assert _family(client)["unjudgedQueue"] is None
    out = _send(client)
    assert out["name"] == "Library · F-01 unjudged"
    assert out["total"] == 4 and out["judged"] == 0 and out["remaining"] == 4
    assert _send(client)["queueId"] == out["queueId"]           # a second press returns the same queue
    q = client.get(f"/api/review/queues/{out['queueId']}").json()
    assert q["queue"]["source_kind"] == "library-family" and q["queue"]["unit"] == "member"
    assert q["queue"]["writes_to"] == "annotations" and not q["queue"]["blind"]
    assert q["queue"]["verdict_options"] == ["interesting", "not_interesting", "artifact", "unsure"]
    assert q["queue"]["source_ref"] == "F-01"
    assert len(client.get("/api/review/queues").json()) == 1


def test_the_family_read_carries_the_open_queue(client):
    out = _send(client)
    uq = _family(client)["unjudgedQueue"]
    assert uq == {"id": out["queueId"], "total": 4, "judged": 0, "remaining": 4}


def test_a_verdict_in_review_judges_the_member_on_the_family_page(client):
    qid = _send(client)["queueId"]
    assert all(m["verdict"] == "unjudged" for m in _family(client)["members"])
    r = client.post(f"/api/review/queues/{qid}/verdict", json={"target_id": "2", "verdict": "interesting"})
    assert r.status_code == 200, r.text
    fam = _family(client)
    m2 = next(m for m in fam["members"] if m["id"] == "m-2")
    assert m2["verdict"] == "interesting" and m2["verdictBy"] == "extent"
    assert sum(1 for m in fam["members"] if m["verdict"] != "unjudged") == 1
    assert fam["unjudgedQueue"] == {"id": qid, "total": 4, "judged": 1, "remaining": 3}
    rows = base._q(client, "SELECT verdict, source, note, start_idx, end_idx FROM annotations "
                           "WHERE source = 'library_review'")
    assert len(rows) == 1 and rows[0]["verdict"] == "interesting"
    assert (rows[0]["start_idx"], rows[0]["end_idx"]) == (990, 1070) and "F-01" in rows[0]["note"]
    assert base._q(client, "SELECT COUNT(*) AS n FROM adjudications")[0]["n"] == 0     # rule 5


def test_the_item_is_an_ordinary_member_item_not_a_suspected_artifact_card(client):
    qid = _send(client)["queueId"]
    r = client.get(f"/api/review/queues/{qid}/items/3")
    assert r.status_code == 200, r.text
    d = r.json()
    assert "suspectedArtifact" not in d
    assert d["entry"]["id"] == "3" and d["queue"]["source_kind"] == "library-family"
    assert d["shape"]["v"] or d["context"]["v"]


def test_every_member_judged_is_a_409_not_a_second_queue(client):
    qid = _send(client)["queueId"]
    for t in ("1", "2", "3", "4"):
        r = client.post(f"/api/review/queues/{qid}/verdict", json={"target_id": t, "verdict": "not_interesting"})
        assert r.status_code == 200, r.text
    r = client.post(ROUTE, json={"grouping": "g-01", "floor": "0"})
    assert r.status_code == 409, r.text
    assert "F-01" in str(r.json()["detail"])
    assert len(client.get("/api/review/queues").json()) == 1
