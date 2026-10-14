"""
test_webui_mpdist_edges.py
==========================
w3-d fix round 1, through the routes (FastAPI: run with webui/.venv's python):

* **F1.** An edge whose distance is not on the seed cut's footing (MPdist, and
  the symbolic distance — SAX MINDIST without its length factor) carries
  `threshold: None`, `within: None` and its `footing` on the Family page; the
  scale-invariant and native-length edges keep their cut and `within`.
* **F2.** *Add N matches* returns `edgesRefused` (each `{detection_id,
  member_id, function, reason}`) and a one-sentence `refusalSummary`, and the
  audit row's detail carries the refusal count.

Reuses `tests/test_webui_library_edges.py`'s scratch bridge (a temp database
and runtime; never DATA/).
"""

import json

import pytest

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from tests.test_webui_library_edges import _bank_run, _judge, _q, client  # noqa: E402,F401


def _added(client):
    out = _bank_run(client)
    _judge(client, out["run_key"])
    r = client.post(f"/api/library/runs/{out['run_key']}/matches", json={})
    assert r.status_code == 200, r.text
    return r.json()


def test_off_footing_edges_carry_no_cut_and_no_within(client):
    _added(client)
    d = client.get("/api/library/family/F-01").json()["detail"]
    seen = set()
    for m in d["matched"]:
        for e in m["edges"]:
            seen.add(e["function"])
            if e["function"] in ("mpdist", "symbolic_sax"):
                assert e["threshold"] is None and e["within"] is None, e
                assert isinstance(e["footing"], str) and e["footing"], e
            else:
                assert e["threshold"] == pytest.approx(6.0), e
                assert isinstance(e["within"], bool), e
                assert "footing" not in e
    assert seen == {"scale_invariant", "symbolic_sax", "native_length", "mpdist"}


def test_adding_matches_returns_the_refusals_and_audits_their_count(client):
    body = _added(client)
    assert body["edgesRefused"] == [], "the plantings are 48-75 samples: MPdist compares them all"
    assert body["refusalSummary"] is None
    assert body["edgesByFunction"]["mpdist"] == 3
    rows = _q(client, "SELECT detail_json FROM audit_log WHERE kind = 'library' ORDER BY id DESC LIMIT 1")
    detail = json.loads(rows[0]["detail_json"])
    assert detail["edges_refused"] == 0


def test_a_member_too_short_for_mpdist_is_refused_in_the_response(client):
    from tests.test_webui_library_edges import _real_detections, _x

    out = _bank_run(client)
    _judge(client, out["run_key"])
    run_id = _real_detections(client, out["run_key"])[0]["run_id"]
    # a 12-sample accepted match, far from every planting: too short for MPdist (16)
    _x(client, "INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, 5000, 5012, 1.0)", (run_id,))
    det = _q(client, "SELECT id FROM detections WHERE run_id = ? AND start_idx = 5000", (run_id,))[0]["id"]
    _x(client, "INSERT INTO adjudications (detection_id, verdict, created_at) VALUES (?, 'interesting', '2026-10-14')",
       (det,))
    body = client.post(f"/api/library/runs/{out['run_key']}/matches", json={}).json()
    assert len(body["edgesRefused"]) == 1, body["edgesRefused"]
    ref = body["edgesRefused"][0]
    assert set(ref) >= {"detection_id", "member_id", "function", "reason"}
    assert ref["detection_id"] == det and ref["function"] == "mpdist" and "short" in ref["reason"].lower()
    assert body["refusalSummary"] and "1 of 4" in body["refusalSummary"]
    rows = _q(client, "SELECT detail_json FROM audit_log WHERE kind = 'library' ORDER BY id DESC LIMIT 1")
    assert json.loads(rows[0]["detail_json"])["edges_refused"] == 1
