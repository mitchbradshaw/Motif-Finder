"""
test_webui_shape_tree.py
========================
fixup-ag seam (ii): the cluster block's page is the DENDROGRAM — a cut the
researcher moves (k follows), each cluster at the cut clickable, showing its
medoid (a real window), a seeded handful of members, its mean shape with its
spread, its count, its scale and recording mix and its raw amplitude range — and
the MAPPING table (each cluster -> a name and interesting / not; specks listed
and mapped like the rest), carried in the block's `mapping` parameter.

The page reads the KEPT tree by its key: moving the cut never rebuilds it.

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_shape_tree.py -q
"""

import json
import os
import sys
import time

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from fastapi.testclient import TestClient  # noqa: E402

from Working.database.schema import init_db  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402

AUG = "syn_aug_concat_fs1.mat"
PLAIN = "syn_concat_fs1.mat"


def _db(tmp_path):
    db_dir = tmp_path / "db"; db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    for source, n in ((AUG, 36_000), (PLAIN, 18_000)):
        d = tmp_path / "channels" / os.path.splitext(source)[0]
        d.mkdir(parents=True)
        for ch in range(16):
            npy = d / f"CH{ch}.npy"
            t = np.arange(n)
            np.save(npy, 0.05 * np.random.default_rng(ch).standard_normal(n) + 0.2 * ((t % 2400) / 2400.0) ** 3)
            conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path, units) "
                         "VALUES (?, ?, 1.0, ?, 0, ?, 'V')", (source, ch, n, str(npy)))
    conn.commit()
    from Working.training import pool as tpool
    from Working.training import store as ts
    for src in (AUG, PLAIN):
        for scale in (1, 10, 30):
            u = tpool.build_unlabelled_set(conn, src, scale_min=scale)
            ts.save_window_set(conn, u, str(tmp_path / "window_sets"), f"ws_{os.path.splitext(src)[0]}_{scale}min")
    conn.close()
    return db


@pytest.fixture(scope="module")
def ran(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("tree")
    db = _db(tmp_path)
    dist = tmp_path / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    rt = Runtime(mode="sandbox", stamp="20261005-agt", db_source=str(db), runtime_root=str(tmp_path / "runtime"),
                 client_dist=str(dist))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            import sqlite3
            con = sqlite3.connect(rt.db_path)
            rid = con.execute("SELECT id FROM recordings WHERE source_file = ? AND channel = 0", (AUG,)).fetchone()[0]
            con.close()
            ids = [s["id"] for s in c.get("/api/windowsets/library").json()["sets"]]
            steps = [{"stage": "preprocessing", "algorithm": "window_pool",
                      "params": {"window_sets": ",".join(map(str, ids)), "per_scale": 200}},
                     {"stage": "preprocessing", "algorithm": "trace_shape", "params": {}},
                     {"stage": "catalogue", "algorithm": "shape_cluster", "params": {"sample": 150, "k": 3}}]
            job = c.post("/api/runs", json={"recording_id": rid, "span": [0, 1], "steps": steps}).json()["job_id"]
            t0 = time.time()
            while time.time() - t0 < 180:
                s = c.get(f"/api/runs/{job}").json()
                if s["status"] in ("completed", "failed"):
                    break
                time.sleep(0.2)
            assert s["status"] == "completed", s.get("error")
            tree = c.get(f"/api/runs/{job}/steps/2").json()["tree"]
            yield c, tree, rid, steps
    finally:
        rt.restore()


def test_moving_the_cut_reads_the_kept_tree_and_k_follows(ran):
    c, tree, _rid, _steps = ran
    mtime = os.path.getmtime(os.path.join(tree["dir"], "tree.npz"))
    for k in (2, 4, 6):
        r = c.get(f"/api/shape/trees/{tree['key']}/cut", params={"k": k})
        assert r.status_code == 200, r.text
        cut = r.json()
        assert cut["k"] == k and len(cut["clusters"]) == k
        assert sum(x["n"] for x in cut["clusters"]) == tree["n_train"]
        assert cut["n_clustered"] == tree["n_clustered"] and cut["n_assigned"] == tree["n_assigned"]
        assert {"speck", "scales", "recordings", "median_range_mv"} <= set(cut["clusters"][0])
    assert os.path.getmtime(os.path.join(tree["dir"], "tree.npz")) == mtime, "a new cut must not rebuild the tree"


def test_a_clicked_cluster_shows_medoid_members_mean_shape_mix_and_amplitude(ran):
    c, tree, _rid, _steps = ran
    r = c.get(f"/api/shape/trees/{tree['key']}/cluster", params={"k": 3, "c": 1})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["cluster"] == 1 and d["k"] == 3 and d["n"] > 0
    assert len(d["members"]) == min(12, d["n"])
    for w in [d["medoid"], *d["members"]]:
        assert len(w["shape"]) == 256 and len(w["raw_mv"]) > 1
        assert {"recording_id", "source_file", "channel", "start", "length", "scale_min", "raw_range_mv"} <= set(w)
    assert len(d["mean"]) == len(d["sd"]) == 256
    assert sum(x["n"] for x in d["scales"]) == d["n"]
    assert d["amplitude_mv"]["min"] <= d["amplitude_mv"]["max"]
    # seeded: the same members twice
    again = c.get(f"/api/shape/trees/{tree['key']}/cluster", params={"k": 3, "c": 1}).json()
    assert [m["row"] for m in again["members"]] == [m["row"] for m in d["members"]]
    assert c.get(f"/api/shape/trees/{tree['key']}/cluster", params={"k": 3, "c": 9}).status_code == 404


def test_an_unknown_tree_is_a_404_and_a_bad_key_is_refused(ran):
    c, _tree, _rid, _steps = ran
    assert c.get("/api/shape/trees/0000000000000000/cut", params={"k": 2}).status_code == 404
    assert c.get("/api/shape/trees/..%2F..%2Fx/cut", params={"k": 2}).status_code in (404, 422)


def test_the_mapping_rides_in_the_block_parameter_and_says_whether_it_covers_the_cut(ran):
    c, tree, rid, steps = ran
    mapping = {"k": 3, "clusters": {"1": {"name": "rise", "class": "interesting"},
                                    "2": {"name": "", "class": "not_interesting"},
                                    "3": {"name": "flat", "class": "not_interesting"}}}
    steps = json.loads(json.dumps(steps))
    steps[2]["params"]["mapping"] = json.dumps(mapping)
    job = c.post("/api/runs", json={"recording_id": rid, "span": [0, 1], "steps": steps}).json()["job_id"]
    t0 = time.time()
    while time.time() - t0 < 180:
        s = c.get(f"/api/runs/{job}").json()
        if s["status"] in ("completed", "failed"):
            break
        time.sleep(0.2)
    assert s["status"] == "completed", s.get("error")
    t = c.get(f"/api/runs/{job}/steps/2").json()["tree"]
    assert t["reused"] is True and t["key"] == tree["key"]
    assert t["mapping_state"] == "complete"
    assert t["mapping"]["clusters"]["1"] == {"name": "rise", "class": "interesting"}
    # made at another cut: stale, and said so
    steps[2]["params"]["k"] = 4
    job = c.post("/api/runs", json={"recording_id": rid, "span": [0, 1], "steps": steps}).json()["job_id"]
    t0 = time.time()
    while time.time() - t0 < 180:
        s = c.get(f"/api/runs/{job}").json()
        if s["status"] in ("completed", "failed"):
            break
        time.sleep(0.2)
    assert c.get(f"/api/runs/{job}/steps/2").json()["tree"]["mapping_state"] == "stale"


def test_a_mapping_naming_a_class_that_is_not_interesting_or_not_is_refused():
    from Adapters.catalogue_shape_cluster import mapping_state, parse_mapping
    with pytest.raises(ValueError, match="interesting"):
        parse_mapping(json.dumps({"k": 2, "clusters": {"1": {"class": "maybe"}}}))
    m = parse_mapping(json.dumps({"k": 2, "clusters": {"1": {"class": "interesting"}}}))
    assert mapping_state(m, 2) == "partial" and mapping_state(parse_mapping(""), 2) == "none"
