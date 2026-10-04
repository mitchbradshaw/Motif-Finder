"""
test_webui_suspected_artifact.py
================================
fixup-AD, the routes: Library › Family *Classify across channels* reports the
too-short count and each bin's chance test; *Send suspected artifacts to
Review* makes (once) a `suspected-artifact` queue through `create_queue`;
Review serves its items with every channel of the recording and what flagged
them; a verdict there moves the family's recurrence by exactly the confirmed
ones and the flagged / confirmed / rejected / unjudged line with it.

Reuses `test_webui_cross_channel`'s synthetic recording (ch0/ch1 a simultaneous
copy, ch2 ten seconds later, ch3 a pulse with no member and one an hour later),
plus a fifth member too short to tell.

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_suspected_artifact.py
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


@pytest.fixture
def client(tmp_path):
    db = base._db(tmp_path)
    import sqlite3
    conn = sqlite3.connect(str(db))
    # m5: 16 samples on ch2 — a Fig2A-sized member, too short to tell
    conn.execute("INSERT INTO motif_entry (recording_id, start_idx, end_idx, label, scale) VALUES (3, 3000, 3016, 'm5', 'event')")
    conn.execute("INSERT INTO motif_member (entry_id, recording_id, start_idx, end_idx, channel, content_hash) "
                 "VALUES (5, 3, 3000, 3016, 2, 'h5')")
    conn.execute("INSERT INTO grouping_assignments (grouping_id, unit, member_ref, content_hash, family_id, "
                 "family_label, distance, is_medoid) VALUES (1, 'single_motifs', 5, 'h5', 1, 'F-01', 0.5, 0)")
    conn.commit()
    conn.close()
    rt = Runtime(mode="sandbox", stamp="20261005-suspected-artifact", db_source=str(db),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(base._dist(tmp_path)))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            yield c
    finally:
        rt.restore()


def _family(client, floor=0):
    r = client.get("/api/library/family/F-01", params={"floor": floor})
    assert r.status_code == 200, r.text
    return r.json()["detail"]


def test_classify_reports_too_short_and_the_chance_test(client):
    snap = base._classify(client)
    assert snap["result"]["counts"]["tooShort"] == 1
    cc = _family(client)["crossChannel"]
    assert cc["tooShort"] == 1
    assert "30 samples" in cc["tooShortRule"]
    assert cc["rule"]["artifact_min_abs_r"] == 0.98 and cc["rule"]["null_k"] == 100
    m1 = next(m for m in _family(client)["members"] if m["id"] == "m-1")
    e12 = next(e for e in m1["edges"] if e["other"] == "m-2")
    assert e12["chance"]["k"] == 100 and e12["chance"]["percentile"] > 95


def test_send_suspected_artifacts_makes_one_queue(client):
    base._classify(client)
    r = client.post("/api/library/family/F-01/suspected-artifacts", json={"grouping": "g-01"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["name"] == "Suspected artifact · F-01" and out["flagged"] == 2
    again = client.post("/api/library/family/F-01/suspected-artifacts", json={"grouping": "g-01"}).json()
    assert again["queueId"] == out["queueId"]
    q = client.get(f"/api/review/queues/{out['queueId']}").json()
    assert q["queue"]["source_kind"] == "suspected-artifact"
    assert q["queue"]["verdict_options"] == ["artifact", "interesting", "not_interesting", "unsure"]


def test_a_card_carries_every_channel_on_one_axis_and_what_flagged_it(client):
    base._classify(client)
    qid = client.post("/api/library/family/F-01/suspected-artifacts", json={"grouping": "g-01"}).json()["queueId"]
    d = client.get(f"/api/review/queues/{qid}/items/1").json()
    flag = d["suspectedArtifact"]
    assert len(flag["channels"]) == 4                        # every channel of the recording
    assert sum(1 for c in flag["channels"] if c["member"]) == 1
    assert flag["unit"] == "mV" and flag["shared_axis"] is True
    sib = next(c for c in flag["channels"] if c["channel_index"] == 1)
    assert abs(sib["r"]) >= 0.98 and sib["chance"]["percentile"] > 95 and sib["amplitude_ratio"] is not None


def test_a_verdict_moves_recurrence_by_the_confirmed_ones(client):
    base._classify(client)
    qid = client.post("/api/library/family/F-01/suspected-artifacts", json={"grouping": "g-01"}).json()["queueId"]
    before = _family(client)["crossChannel"]["recurrence"]
    assert before["excluding_artifacts"] == 5 and before["flagged"] == 2 and before["unjudged"] == 2
    r = client.post(f"/api/review/queues/{qid}/verdict", json={"target_id": "1", "verdict": "artifact"})
    assert r.status_code == 200, r.text
    after = _family(client)["crossChannel"]["recurrence"]
    assert after["confirmed"] == 1 and after["unjudged"] == 1           # m2 is not judged...
    assert after["excluding_artifacts"] == 3                            # ...but goes with its member twin (Q40d-2)
    rows = base._q(client, "SELECT verdict, source, note FROM annotations WHERE source = 'cross_channel_review'")
    assert len(rows) == 1 and "suspected artifact" in rows[0]["note"]
