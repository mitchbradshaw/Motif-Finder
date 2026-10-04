"""
test_webui_library_view.py
==========================
fixup-AE through the bridge: the Library's routes read through the view filter,
the hand edits a person wrote, the one verdict resolver and the stored rose
reference. The fixture is `test_webui_library.py`'s seeded library:

    F-01  members[0] hash0 (rec 0, 100-160)   members[1] hash1 (rec 0, 900-962)
    F-02  members[2] hash2 (rec 1)            members[3] hash3 (rec 1)

and these tests add detector depths to it: hash0 0.05 mV (under the default
0.1 mV floor), hash1 0.5, hash2 and hash3 0.05 — so F-02 is entirely under
the floor.

Runs under webui/.venv (FastAPI); skipped elsewhere, like its siblings.
"""

import os
import sqlite3
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui"), os.path.dirname(os.path.abspath(__file__))):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv; run this file with that interpreter")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from fastapi.testclient import TestClient  # noqa: E402

from test_webui_library import _bridge, _ok  # noqa: E402
from Working.library import features as F  # noqa: E402

DEPTHS = {"hash0": 0.05, "hash1": 0.5, "hash2": 0.05, "hash3": 0.05}


@pytest.fixture
def lib(tmp_path):
    rt, app, held, gid, member_ids = _bridge(tmp_path, "sandbox")
    try:
        with TestClient(app) as client:
            _ok(client.get("/api/library/counts"))             # schema ensured
            conn = sqlite3.connect(rt.db_path)
            F.write_features(conn, [{"content_hash": h, "fs": 1.0, "measures": {"max_slope_mv_s": -1.0 - i},
                                     "detector": {"drop_depth_mv": d, "fall_duration_s": 20.0 + i, "is_pure": 1}}
                                    for i, (h, d) in enumerate(DEPTHS.items())])
            conn.close()
            yield client, {"rt": rt, "members": member_ids, "gid": gid}
    finally:
        rt.restore()


def _ids(families):
    return {f["id"]: f for f in families}


def test_the_atlas_hides_sub_floor_members_and_a_family_entirely_under_it(lib):
    client, _ = lib
    fams = _ids(_ok(client.get("/api/library/families")))
    assert set(fams) == {"F-01"}, "F-02 is all sub-floor: gone from the grid"
    assert fams["F-01"]["members"] == 1
    assert fams["F-01"]["view"]["subFloor"] == 1 and fams["F-01"]["view"]["total"] == 2
    every = _ids(_ok(client.get("/api/library/families?floor=0")))
    assert set(every) == {"F-01", "F-02"} and every["F-01"]["members"] == 2


def test_the_view_route_counts_what_the_floor_hid_by_store_and_dataset(lib):
    client, _ = lib
    v = _ok(client.get("/api/library/view"))
    assert v["floorOn"] is True and v["subFloor"] == 3
    assert v["families"] == {"before": 2, "after": 1, "allSubFloor": 1}
    assert v["familiesAllSubFloor"] == ["F-02"]
    assert sum(d["sub_floor"] for d in v["byDataset"].values()) == 3
    assert "noise floor" in v["rule"] and v["judgedRule"]
    off = _ok(client.get("/api/library/view?floor=0"))
    assert off["floorOn"] is False and off["subFloor"] == 3 and off["families"]["after"] == 2


def test_the_filters_reach_the_routes(lib):
    client, _ = lib
    fams = _ids(_ok(client.get("/api/library/families?floor=0&fallMin=20.5&fallMax=300")))
    assert fams["F-01"]["members"] == 1, "hash0 falls in 20 s, under the range"
    rec = _ok(client.get("/api/library/recurrence?floor=0&fallMin=20.5"))
    assert rec["view"]["fall"]["hidden"] == 1


def test_a_family_the_view_hid_entirely_opens_and_says_so(lib):
    client, _ = lib
    body = _ok(client.get("/api/library/family/F-02"))
    assert body["kind"] == "motif"
    assert body["detail"]["view"]["hiddenByView"] is True and body["detail"]["members"] == []


def test_a_member_removed_by_hand_is_gone_after_a_reload_and_back_after_undo(lib):
    client, info = lib
    before = _ok(client.get("/api/library/family/F-01?floor=0"))["detail"]
    target = next(m for m in before["members"] if m["contentHash"] == "hash1")
    edit = _ok(client.post("/api/library/hand-edits", json={
        "contentHash": "hash1", "kind": "remove_member", "familyLabel": "F-01", "grouping": f"g-{info['gid']:02d}"}))
    after = _ok(client.get("/api/library/family/F-01?floor=0"))["detail"]
    assert target["id"] not in {m["id"] for m in after["members"]}
    assert target["id"] in {r["id"] for r in after["removed"]}
    assert _ids(_ok(client.get("/api/library/families?floor=0")))["F-01"]["members"] == 1
    _ok(client.delete(f"/api/library/hand-edits/{edit['id']}"))
    back = _ok(client.get("/api/library/family/F-01?floor=0"))["detail"]
    assert target["id"] in {m["id"] for m in back["members"]}


def test_a_removal_holds_in_a_later_grouping_that_relabels_the_family(lib):
    """§8.3: "a member removed by hand stays out of that family on every regroup until restored". The regroup job
    only counts the edits, so the read must apply them — matched by the family's identity (its medoid's hash),
    not by its label, which every grouping numbers afresh."""
    client, info = lib
    _ok(client.post("/api/library/hand-edits", json={
        "contentHash": "hash1", "kind": "remove_member", "familyLabel": "F-01", "grouping": f"g-{info['gid']:02d}"}))
    conn = sqlite3.connect(info["rt"].db_path)
    new = conn.execute(
        "INSERT INTO groupings (name, unit, basis, method, params_json, cut, n_families, n_assigned, n_omitted, "
        "recipe_hash, created_at, actor) SELECT name || ' (regrouped)', unit, basis, method, params_json, cut, "
        "n_families, n_assigned, n_omitted, 'regrouped', '2026-10-04T12:00:00', actor FROM groupings WHERE id = ?",
        (info["gid"],)).lastrowid
    conn.execute(
        "INSERT INTO grouping_assignments (grouping_id, unit, member_ref, content_hash, family_id, family_label, "
        "distance, is_medoid, omit_reason) SELECT ?, unit, member_ref, content_hash, family_id, "
        "CASE family_label WHEN 'F-01' THEN 'F-07' WHEN 'F-02' THEN 'F-08' ELSE family_label END, distance, "
        "is_medoid, omit_reason FROM grouping_assignments WHERE grouping_id = ?", (new, info["gid"]))
    conn.commit()
    conn.close()
    d = _ok(client.get(f"/api/library/family/F-07?grouping=g-{new:02d}&floor=0"))["detail"]
    assert "hash1" not in {m["contentHash"] for m in d["members"]}, "the removal followed F-01 into its new label"
    assert [r["contentHash"] for r in d["removed"]] == ["hash1"]


def test_judged_is_the_resolvers_and_says_which_rule(lib):
    client, info = lib
    conn = sqlite3.connect(info["rt"].db_path)
    rec0 = conn.execute("SELECT recording_id FROM motif_member WHERE content_hash = 'hash0'").fetchone()[0]
    conn.execute("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
                 "VALUES (?, 0, 600, 'interesting', 'imported_10min', '2026-09-01T00:00:00')", (rec0,))
    conn.commit()
    conn.close()
    d = _ok(client.get("/api/library/family/F-01?floor=0"))["detail"]
    m = next(x for x in d["members"] if x["contentHash"] == "hash0")
    assert m["verdict"] == "interesting" and m["verdictBy"] == "containment"
    assert d["family"]["judged"] == 1 and "containment" in d["judgedRule"]


def test_members_carry_what_the_slideshow_loads(lib):
    client, _ = lib
    m = _ok(client.get("/api/library/family/F-01?floor=0"))["detail"]["members"][0]
    assert {"recordingId", "startS", "endS", "floorStatus", "depthMv", "fallS", "isPure"} <= set(m)


def test_the_rose_reference_is_read_and_stored_on_an_explicit_act(lib):
    client, info = lib
    r = _ok(client.get("/api/library/rose-reference"))
    assert r["stored"] is False and r["population"] == "above_floor" and r["n"] == 1
    s = _ok(client.post("/api/library/rose-reference", json={}))
    assert s["stored"] is True
    again = _ok(client.get("/api/library/rose-reference"))
    assert again["stored"] is True and again["value_mv_s"] == pytest.approx(2.0)
    conn = sqlite3.connect(info["rt"].db_path)
    assert conn.execute("SELECT COUNT(*) FROM settings WHERE page = 'analysis-defaults' AND key = "
                        "'rose.reference_mv_s'").fetchone()[0] == 1
    conn.close()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
