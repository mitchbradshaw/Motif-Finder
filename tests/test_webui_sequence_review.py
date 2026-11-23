"""
test_webui_sequence_review.py
==============================
The sequence-review queue's routes (2026-11-23): `POST /api/review/sequence-review` registers proposed sequence
spans (machine candidates, with their events) and puts them - and any existing sequences named by id - in one
open queue; Review serves each as a `sequence` item whose events are drawn inside it (`memberBands`); a verdict
lands over the span, and an accepted one is a human sequence the Library lists as awaiting extraction.

The entry point other tools use (Auto-detect, 2026-11-23): spans in absolute samples with their events,
a provenance, a queue name.

Reuses `test_webui_cross_channel`'s synthetic recording.

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_sequence_review.py
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

ROUTE = "/api/review/sequence-review"
EVENTS = [(990, 1070), (1400, 1460), (2000, 2060)]


@pytest.fixture
def client(tmp_path):
    db = base._db(tmp_path)
    rt = Runtime(mode="sandbox", stamp="20261123-sequence-review", db_source=str(db),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(base._dist(tmp_path)))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            yield c
    finally:
        rt.restore()


def _send(client, events=EVENTS, name="Sequences · test"):
    body = {"name": name, "provenance": "chain_1h",
            "spans": [{"recording_id": 1, "start_idx": events[0][0], "end_idx": events[-1][1],
                       "events": [{"start_idx": a, "end_idx": b} for a, b in events],
                       "note": "3 accepted events, next onset within 1 h"}]}
    r = client.post(ROUTE, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_a_send_makes_one_queue_and_a_second_send_returns_it(client):
    out = _send(client)
    assert out["created"] == 1 and len(out["sequenceIds"]) == 1
    assert (out["total"], out["judged"], out["remaining"]) == (1, 0, 1)
    again = _send(client)
    assert again["queueId"] == out["queueId"] and again["created"] == 0
    q = client.get(f"/api/review/queues/{out['queueId']}").json()
    assert q["queue"]["source_kind"] == "sequence-review" and q["queue"]["unit"] == "sequence"
    assert q["queue"]["writes_to"] == "annotations"
    assert q["queue"]["verdict_options"] == ["interesting", "not_interesting", "artifact", "unsure"]


def test_the_item_carries_its_events_as_bands_inside_the_span(client):
    out = _send(client)
    q = client.get(f"/api/review/queues/{out['queueId']}").json()
    row = q["rows"][0]
    assert row["unit"] == "sequence" and row["id"] == str(out["sequenceIds"][0])
    assert row["durationS"] == pytest.approx(2060 - 990)
    assert [(b["t0_s"], b["t1_s"]) for b in row["memberBands"]] == [(float(a), float(b)) for a, b in EVENTS]
    detail = client.get(f"/api/review/queues/{out['queueId']}/items/{row['id']}")
    assert detail.status_code == 200, detail.text
    assert len(detail.json()["entry"]["memberBands"]) == 3


def test_an_accepted_sequence_is_listed_by_the_library_as_awaiting_extraction(client):
    out = _send(client)
    sid = str(out["sequenceIds"][0])
    r = client.post(f"/api/review/queues/{out['queueId']}/verdict", json={"target_id": sid, "verdict": "interesting"})
    assert r.status_code == 200, r.text
    assert r.json()["counts"]["judged"] == 1
    listed = client.get("/api/library/sequences", params={"needs_extraction": 1}).json()
    stored = [s for s in listed if s["sourceKind"] == "sequence_review"]
    assert len(stored) == 1 and stored[0]["origin"] == "human" and stored[0]["nEvents"] == 3
    undo = client.post(f"/api/review/queues/{out['queueId']}/undo")
    assert undo.status_code == 200, undo.text
    assert not [s for s in client.get("/api/library/sequences").json() if s["sourceKind"] == "sequence_review"]


def test_unreviewed_candidates_are_not_library_content(client):
    """A candidate is a proposal awaiting review: the Library neither lists it, counts it, nor groups it - only an
    accepted one (a human sequence) is Library content."""
    before = client.get("/api/library/counts").json()["sequences"]
    out = _send(client)
    assert client.get("/api/library/counts").json()["sequences"] == before
    assert not [s for s in client.get("/api/library/sequences").json() if s["sequenceKey"].startswith("candidate:")]
    client.post(f"/api/review/queues/{out['queueId']}/verdict",
                json={"target_id": str(out["sequenceIds"][0]), "verdict": "interesting"})
    assert client.get("/api/library/counts").json()["sequences"] == before + 1


def test_seed_and_a_malformed_span_are_400s_not_tracebacks(client):
    out = _send(client)
    r = client.post(f"/api/review/queues/{out['queueId']}/verdict",
                    json={"target_id": str(out["sequenceIds"][0]), "verdict": "seed"})
    assert r.status_code == 400 and "single event" in r.text
    bad = client.post(ROUTE, json={"name": "x", "provenance": "p", "spans": [
        {"recording_id": 1, "start_idx": 100, "end_idx": 200, "events": [{"start_idx": 150, "end_idx": 250}]}]})
    assert bad.status_code == 400 and "outside" in bad.text
