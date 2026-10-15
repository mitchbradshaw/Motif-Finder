"""
test_webui_library_tree.py
============================
fixup-an (AN-1, the bridge): a Library grouping's Ward tree is kept on disk and
served.

* a Ward regroup job keeps its tree under the runtime (never the real DATA/) and
  says whether it built or reused it; a second job on the same members reuses it;
* saving that grouping records the tree's key and path on the `groupings` row —
  a path, never an array (rule 4) — and refuses a key the server did not write;
* `GET /api/library/groupings/{id}/tree` draws it; a grouping made before trees
  were kept says so in words and offers to build one; a feature-bin grouping says
  it has no tree;
* `GET /api/library/groupings/{id}/cut?cut=` previews the families at a cut from
  the kept tree, without a job: at the grouping's own cut nothing moves, and each
  family carries sample members with their traces.

The fixture is `test_webui_library.py`'s seeded library (five members). Run with
the webui venv:

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_library_tree.py
"""

import os
import sqlite3
import sys
import time

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

WARD_BODY = {"unit": "motifs", "basis": "shape-distance", "method": "ward",
             "params": {"cut": 0.6, "min_group": 2}}


@pytest.fixture
def lib(tmp_path):
    rt, app, held, gid, member_ids = _bridge(tmp_path, "sandbox")
    try:
        with TestClient(app) as client:
            yield client, {"rt": rt, "gid": gid, "members": member_ids}
    finally:
        rt.restore()


def _run(client, body):
    job_id = _ok(client.post("/api/library/groupings/run", json=body))["job_id"]
    for _ in range(1200):
        snap = _ok(client.get(f"/api/jobs/{job_id}"))
        if snap["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.05)
    assert snap["status"] == "completed", snap.get("error") or snap
    return snap["result"]


def _save(client, result, **extra):
    body = {"unit": result["unit"], "basis": result["basis"], "method": result["method"],
            "params": result["params"], "cut": result["params"].get("cut"),
            "assignments": result["assignments"], "fit_summary": result.get("fitSummary")}
    if result.get("tree"):
        body["tree_key"] = result["tree"]["key"]
    body.update(extra)
    return client.post("/api/library/groupings", json=body)


def test_a_ward_regroup_keeps_its_tree_inside_the_runtime_and_reuses_it(lib):
    client, ctx = lib
    first = _run(client, WARD_BODY)
    tree = first["tree"]
    assert tree and tree["reused"] is False and tree["key"]
    path = tree["path"]
    full = path if os.path.isabs(path) else os.path.join(PROJECT_ROOT, path)
    assert os.path.isfile(full)
    assert os.path.abspath(full).lower().startswith(os.path.abspath(ctx["rt"].dir).lower()), \
        "a sandbox keeps its trees in its own runtime, never in the real DATA/"
    assert "built the tree" in first["treeNote"]

    second = _run(client, {**WARD_BODY, "params": {"cut": 0.9, "min_group": 2}})
    assert second["tree"]["reused"] is True and second["tree"]["key"] == tree["key"]
    assert "reused the tree" in second["treeNote"]


def test_saving_records_the_tree_by_path_and_the_database_holds_no_array(lib):
    client, ctx = lib
    result = _run(client, WARD_BODY)
    saved = _ok(_save(client, result))
    assert saved["treeKey"] == result["tree"]["key"]
    conn = sqlite3.connect(ctx["rt"].db_path)
    try:
        gid = int(saved["id"].split("-")[1])
        row = conn.execute("SELECT tree_path, tree_key FROM groupings WHERE id = ?", (gid,)).fetchone()
        assert row[0] and row[0].endswith(".npz") and row[1] == result["tree"]["key"]
        blobs = conn.execute("SELECT COUNT(*) FROM groupings g WHERE "
                             + " OR ".join(f"typeof({c}) = 'blob'" for c in
                                           [r[1] for r in conn.execute("PRAGMA table_info(groupings)")])
                             ).fetchone()[0]
        assert blobs == 0, "rule 4: the tree is a file on disk, the row holds its path"
    finally:
        conn.close()


def test_a_tree_key_the_server_did_not_write_is_refused(lib):
    client, _ = lib
    result = _run(client, WARD_BODY)
    for bad in ("../../DATA/db/annotations", "deadbeef" * 4):
        r = _save(client, result, tree_key=bad)
        assert r.status_code == 422, r.text[:300]


def test_the_tree_route_draws_a_kept_tree(lib):
    client, _ = lib
    saved = _ok(_save(client, _run(client, WARD_BODY)))
    body = _ok(client.get(f"/api/library/groupings/{saved['id']}/tree"))
    assert body["groupingId"] == saved["id"] and body["reason"] is None
    d = body["tree"]["dendrogram"]
    assert d["icoord"] and len(d["icoord"]) == len(d["dcoord"])
    assert d["heights"] == sorted(d["heights"], reverse=True)
    assert body["tree"]["nLeaves"] == d["n_leaves"] == 5
    assert body["cut"] == pytest.approx(0.6)


def test_a_grouping_made_before_trees_were_kept_says_so_and_offers_to_build_one(lib):
    client, ctx = lib
    body = _ok(client.get(f"/api/library/groupings/g-{ctx['gid']:02d}/tree"))
    assert body["tree"] is None
    assert "before" in body["reason"] and body["canBuild"] is True
    r = client.get(f"/api/library/groupings/g-{ctx['gid']:02d}/cut", params={"cut": 0.5})
    assert r.status_code == 404 and "tree" in r.text


def test_a_feature_bin_grouping_has_no_tree_and_says_why(lib):
    client, _ = lib
    result = _run(client, {"unit": "motifs", "basis": "amplitude", "method": "feature_bins",
                           "params": {"count": 2, "min_group": 1}})
    assert result["tree"] is None
    saved = _ok(_save(client, result))
    body = _ok(client.get(f"/api/library/groupings/{saved['id']}/tree"))
    assert body["tree"] is None and body["canBuild"] is False and "no tree" in body["reason"]


def test_the_cut_preview_reads_the_kept_tree_and_carries_sample_cards(lib):
    client, _ = lib
    result = _run(client, WARD_BODY)
    saved = _ok(_save(client, result))
    own = _ok(client.get(f"/api/library/groupings/{saved['id']}/cut", params={"cut": 0.6}))
    assert own["nFamilies"] == saved["families"]
    assert own["change"]["moved"] == 0 and own["change"]["sameFamilies"] is True
    assert own["change"]["rule"]
    for fam in own["families"]:
        assert fam["samples"] and fam["samples"][0]["ref"] == fam["medoid"]
        assert all(isinstance(s["trace"], list) for s in fam["samples"])
    assert own["sampleRule"]
    high = _ok(client.get(f"/api/library/groupings/{saved['id']}/cut", params={"cut": 50.0}))
    assert high["nFamilies"] <= own["nFamilies"]
    assert "smallFamilies" in high and high["smallFamilies"]["minGroup"] == 2
    r = client.get(f"/api/library/groupings/{saved['id']}/cut", params={"cut": -1})
    assert r.status_code == 422


def test_an_unknown_grouping_tree_is_a_404(lib):
    client, _ = lib
    assert client.get("/api/library/groupings/g-999/tree").status_code == 404


# ── fix round (critic) ──────────────────────────────────────────────────────

def test_a_row_whose_tree_file_holds_another_key_says_so(lib):
    client, ctx = lib
    saved = _ok(_save(client, _run(client, WARD_BODY)))
    conn = sqlite3.connect(ctx["rt"].db_path)
    try:
        conn.execute("UPDATE groupings SET tree_key = ? WHERE id = ?", ("0" * 32, int(saved["id"].split("-")[1])))
        conn.commit()
    finally:
        conn.close()
    body = _ok(client.get(f"/api/library/groupings/{saved['id']}/tree"))
    assert body["tree"] is None and "key" in body["reason"] and body["canBuild"] is True
    r = client.get(f"/api/library/groupings/{saved['id']}/cut", params={"cut": 0.6})
    assert r.status_code == 404


def test_saving_a_tree_whose_members_are_not_the_assignments_is_refused(lib):
    client, _ = lib
    result = _run(client, WARD_BODY)
    r = _save(client, {**result, "assignments": result["assignments"][:-1]})
    assert r.status_code == 422 and "member" in r.text


def test_the_library_dendrogram_reads_heights_on_a_square_root_axis():
    """Fix round: on a 3,000-member tree the cuts the researcher uses (0.1-1) sat in the bottom few pixels of a
    linear axis reaching 16. The Library passes a square-root height axis and an exact cut height; the Analyse page
    keeps the linear default; the slider stays a cut-sized range rather than the tree's full height."""
    src = os.path.join(PROJECT_ROOT, "webui", "client", "src")
    with open(os.path.join(src, "analyse", "views", "TreePage.tsx"), encoding="utf-8") as f:
        tree = f.read()
    with open(os.path.join(src, "library", "GroupingPage.tsx"), encoding="utf-8") as f:
        page = f.read()
    assert "heightScale = 'linear'" in tree
    assert 'heightScale="sqrt"' in page
    assert "treeMax * 1.05" not in page
