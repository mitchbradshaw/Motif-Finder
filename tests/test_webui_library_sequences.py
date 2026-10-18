"""
test_webui_library_sequences.py
===============================
The Library's *Build sequences* routes (`webui/server/library.py`, prompt
`sequences`, 2026-10-18):

* `POST /api/library/sequences/preview` lists the sequences a join WOULD make
  and writes nothing — every table it could touch keeps its row count;
* `POST /api/library/sequences/keep` writes them, and the atlas's sequence
  families list the new label-chain family;
* `GET /api/library/sequences/{family}` carries the family page's figures, and
  its gap distribution is the joiner's gaps, not a second measurement;
* the held-out recording is refused (423).

FastAPI lives only in `webui/.venv`; under the conda pytest this file skips.
Run it with `webui/.venv/Scripts/python.exe -m pytest tests/test_webui_library_sequences.py`.
The database is `test_webui_library._seed`'s synthetic one, plus a handful of
adjacent members on the first channel.
"""

import os
import sqlite3
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv; run this file with that interpreter")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from fastapi.testclient import TestClient  # noqa: E402

import test_webui_library as base  # noqa: E402
from Working.library import sequences as S  # noqa: E402

#: (start, end, label) on the first channel, on top of the base seed's members (100-160 and 900-962, both F-01).
#: Three touching or nearly touching (2 s < 10 % of 58 s) make F-01 F-02 F-01; a pair 12 s apart (20 % of 60 s)
#: does not join; and a touching F-01 F-02 pair is the near-match family one element shorter.
EXTRA = [(12000, 12060, "F-01"), (12060, 12120, "F-02"), (12122, 12180, "F-01"),
         (15000, 15060, "F-02"), (15072, 15132, "F-01"),
         (20000, 20060, "F-01"), (20060, 20120, "F-02")]
CHAIN = S.label_key(["F-01", "F-02", "F-01"])
PAIR = S.label_key(["F-01", "F-02"])
TABLES = ("sequences", "sequence_members", "groupings", "grouping_assignments", "hand_edits")


def _add_members(db_path, gid):
    conn = sqlite3.connect(db_path)
    try:
        rid = conn.execute("SELECT MIN(id) FROM recordings").fetchone()[0]
        for i, (a, b, label) in enumerate(EXTRA):
            entry = conn.execute(
                "INSERT INTO motif_entry (recording_id, start_idx, end_idx, scale, created_at) "
                "VALUES (?, ?, ?, 'event', '2026-10-18T09:00:00')", (rid, a, b)).lastrowid
            mid = conn.execute(
                "INSERT INTO motif_member (entry_id, recording_id, start_idx, end_idx, content_hash) "
                "VALUES (?, ?, ?, ?, ?)", (entry, rid, a, b, f"seqhash{i}")).lastrowid
            conn.execute(
                "INSERT INTO grouping_assignments (grouping_id, unit, member_ref, content_hash, family_id, "
                "family_label, distance) VALUES (?, 'single_motifs', ?, ?, ?, ?, 0.2)",
                (gid, mid, f"seqhash{i}", 1 if label == "F-01" else 2, label))
        conn.commit()
        return rid
    finally:
        conn.close()


@pytest.fixture
def seqb(tmp_path):
    rt, app, held, gid, member_ids = base._bridge(tmp_path, "sandbox")
    rid = _add_members(rt.db_path, gid)
    try:
        with TestClient(app) as client:
            yield client, {"rid": rid, "held": held, "db": rt.db_path}
    finally:
        rt.restore()


def _counts(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}
    finally:
        conn.close()


def _ok(r):
    assert r.status_code == 200, r.text[:600]
    return r.json()


BODY = {"rule": "fixed", "gap_s": 0.0, "tol_frac": 0.1}


def test_preview_lists_the_sequences_and_writes_nothing(seqb):
    client, ctx = seqb
    before = _counts(ctx["db"])
    body = _ok(client.post("/api/library/sequences/preview", json={**BODY, "recording_id": ctx["rid"]}))
    assert _counts(ctx["db"]) == before, "a preview must write nothing"
    keys = [s["key"] for s in body["sequences"]]
    assert keys == [CHAIN, PAIR]
    first = body["sequences"][0]
    assert first["labels"] == ["F-01", "F-02", "F-01"]
    assert first["gapsS"] == [0.0, 2.0]
    assert [e["label"] for e in first["elements"]] == first["labels"]
    assert first["elements"][0]["startS"] == 0.0, "element times are relative to the sequence's start"
    assert all(e["colour"].startswith("#") for e in first["elements"])
    assert {f["key"]: f["count"] for f in body["families"]} == {CHAIN: 1, PAIR: 1}
    assert body["nMembers"] >= 9
    assert not any(s["kept"] for s in body["sequences"])
    assert any(c["recordingId"] == ctx["rid"] for c in body["candidates"])


def test_a_preview_with_no_recording_picks_the_busiest_channel(seqb):
    client, ctx = seqb
    body = _ok(client.post("/api/library/sequences/preview", json=BODY))
    assert body["recordingId"] == ctx["rid"]
    only = _ok(client.post("/api/library/sequences/preview", json={**BODY, "candidates_only": True}))
    assert only["sequences"] == [] and only["candidates"]


def test_keep_writes_and_the_atlas_lists_the_family(seqb):
    client, ctx = seqb
    before = _counts(ctx["db"])
    kept = _ok(client.post("/api/library/sequences/keep", json={**BODY, "recording_id": ctx["rid"]}))
    assert kept["created"] == 2 and kept["already"] == 0
    after = _counts(ctx["db"])
    assert after["sequences"] == before["sequences"] + 2
    assert after["sequence_members"] == before["sequence_members"] + 5
    assert kept["grouping"]
    fams = _ok(client.get(f"/api/library/sequence-families?grouping={kept['grouping']}"))
    assert {f["id"] for f in fams} == {CHAIN, PAIR}
    # the new grouping is the newest of its unit, so the default read (the atlas with no ?grouping=) shows it
    assert {f["id"] for f in _ok(client.get("/api/library/sequence-families"))} == {CHAIN, PAIR}
    assert any(g["id"] == kept["grouping"] and g["unit"] == "sequences"
               for g in _ok(client.get("/api/library/groupings")))

    again = _ok(client.post("/api/library/sequences/keep", json={**BODY, "recording_id": ctx["rid"]}))
    assert again["created"] == 0 and again["already"] == 2
    assert _counts(ctx["db"]) == after, "keeping the same sequences again writes nothing"
    preview = _ok(client.post("/api/library/sequences/preview", json={**BODY, "recording_id": ctx["rid"]}))
    assert all(s["kept"] for s in preview["sequences"])


def test_the_family_route_carries_the_joiners_gaps(seqb):
    client, ctx = seqb
    kept = _ok(client.post("/api/library/sequences/keep", json={**BODY, "recording_id": ctx["rid"]}))
    fam = _ok(client.get(f"/api/library/sequences/{CHAIN}?grouping={kept['grouping']}"))
    preview = _ok(client.post("/api/library/sequences/preview", json={**BODY, "recording_id": ctx["rid"]}))
    joiner_gaps = [g for s in preview["sequences"] if s["key"] == CHAIN for g in s["gapsS"]]
    assert sorted(fam["gaps"]) == sorted(joiner_gaps) == [0.0, 2.0]
    assert fam["lengths"] == [3]
    assert sum(b["count"] for b in fam["gapBins"]) == 2
    assert sum(b["count"] for b in fam["lengthBins"]) == 1
    assert len(fam["sequences"]) == 1 and fam["sequences"][0]["labels"] == ["F-01", "F-02", "F-01"]
    assert [m["position"] for m in fam["medoids"]] == [0, 1, 2]
    assert all(len(m["trace"]) > 10 for m in fam["medoids"]), "the base seed's channels are on disk"
    assert fam["examples"] and len(fam["examples"][0]["bands"]) == 3
    assert fam["nearest"] == {"id": PAIR, "name": "F-01 → F-02", "distance": 1}
    missing = client.get(f"/api/library/sequences/F-09.F-09?grouping={kept['grouping']}")
    assert missing.status_code == 404


def test_removing_a_sequence_from_its_family_is_a_hand_edit_and_restorable(seqb):
    client, ctx = seqb
    kept = _ok(client.post("/api/library/sequences/keep", json={**BODY, "recording_id": ctx["rid"]}))
    fam = _ok(client.get(f"/api/library/sequences/{CHAIN}?grouping={kept['grouping']}"))
    seq = fam["sequences"][0]
    edit = _ok(client.post("/api/library/hand-edits", json={
        "contentHash": seq["contentHash"], "kind": "remove_member", "familyLabel": CHAIN}))
    after = _ok(client.get(f"/api/library/sequences/{CHAIN}?grouping={kept['grouping']}"))
    assert after["sequences"] == [] and after["removed"][0]["editId"] == edit["id"]
    _ok(client.delete(f"/api/library/hand-edits/{edit['id']}"))
    assert len(_ok(client.get(f"/api/library/sequences/{CHAIN}?grouping={kept['grouping']}"))["sequences"]) == 1


def test_the_held_out_recording_is_refused(seqb):
    client, ctx = seqb
    for route in ("preview", "keep"):
        r = client.post(f"/api/library/sequences/{route}", json={**BODY, "recording_id": ctx["held"]})
        assert r.status_code == 423, r.text[:300]


def test_a_bad_rule_is_refused_in_words(seqb):
    client, ctx = seqb
    r = client.post("/api/library/sequences/preview", json={**BODY, "rule": "nope", "recording_id": ctx["rid"]})
    assert r.status_code == 400 and "rule" in r.text
