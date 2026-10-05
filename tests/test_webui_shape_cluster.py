"""
test_webui_shape_cluster.py
===========================
fixup-ag: the bridge side of the *Window pool* → *Trace shape* → *Shape
clustering* chain (ticket `docs/prompts/fixup/AG-…`).

* the *Window pool* block's page lists the LIBRARY of every saved window set —
  unlabelled sets, pools, the baseline's labelled set — each with its recording,
  scale and counts, from `Working.training.pool.list_sets` (nothing assumes six);
* the block's catalog card says it is a chain source;
* a chain that starts from the pool runs through `POST /api/runs` like any other
  chain, every path it writes inside the sandbox;
* the three payloads carry what their pages draw: the pool's windows per recording
  × scale × role and what was dropped; the shape step's noise-floor count; the
  cluster step's tree (clustered N, assigned M, the truncated dendrogram, the
  proposal per k).

FastAPI lives only in `webui/.venv`:

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_shape_cluster.py -q
"""

import datetime as _dt
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

from Working.config import HELD_OUT_RECORDING_FILE  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402

AUG = "syn_aug_concat_fs1.mat"
PLAIN = "syn_concat_fs1.mat"


def _db(tmp_path):
    db_dir = tmp_path / "db"; db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    for source, n, chans in ((AUG, 36_000, range(16)), (PLAIN, 18_000, range(16)), (HELD_OUT_RECORDING_FILE, 3600, (0,))):
        d = tmp_path / "channels" / os.path.splitext(source)[0]
        d.mkdir(parents=True)
        for ch in chans:
            npy = d / f"CH{ch}.npy"
            np.save(npy, 0.05 * np.random.default_rng(ch).standard_normal(n))
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


def _dist(tmp_path):
    dist = tmp_path / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    return dist


@pytest.fixture
def client(tmp_path):
    db = _db(tmp_path)
    rt = Runtime(mode="sandbox", stamp="20261005-ag", db_source=str(db), runtime_root=str(tmp_path / "runtime"),
                 client_dist=str(_dist(tmp_path)))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            c.rt = rt
            yield c
    finally:
        rt.restore()


def _run(client, steps, timeout=180):
    import sqlite3
    c = sqlite3.connect(client.rt.db_path)
    try:
        rid = c.execute("SELECT id FROM recordings WHERE source_file = ? AND channel = 0", (AUG,)).fetchone()[0]
    finally:
        c.close()
    r = client.post("/api/runs", json={"recording_id": rid, "span": [0, 1], "steps": steps})
    assert r.status_code == 200, r.text
    job = r.json()["job_id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get(f"/api/runs/{job}").json()
        if s["status"] in ("completed", "failed", "cancelled"):
            assert s["status"] == "completed", s.get("error")
            return job, s
        time.sleep(0.2)
    raise AssertionError("run did not finish")


def test_the_pool_block_lists_every_saved_window_set_with_recording_scale_and_counts(client):
    r = client.get("/api/windowsets/library")
    assert r.status_code == 200, r.text
    sets = r.json()["sets"]
    assert len(sets) == 6
    one = next(s for s in sets if s["name"] == "ws_syn_aug_concat_fs1_10min")
    assert one["kind"] == "unlabelled" and one["scale_min"] == 10
    assert one["source_files"] == [AUG] and one["n_windows"] == 60 * 16
    assert "per_recording" in one
    # the held-out recording is never a member and never listed
    assert all(HELD_OUT_RECORDING_FILE not in s["source_files"] for s in sets)
    assert r.json()["defaults"]["per_scale"] == 20000


def test_the_window_pool_card_is_a_chain_source():
    from server import chain as chain_mod
    cards = {c["name"]: c for c in chain_mod.catalog()}
    assert cards["preprocessing.window_pool"]["source"] is True
    assert cards["preprocessing.trace_shape"]["source"] is False
    v = chain_mod.validate([{"stage": "preprocessing", "algorithm": "detrend", "params": {}},
                            {"stage": "preprocessing", "algorithm": "window_pool", "params": {}}])
    assert not v["ok"] and "source" in v["junctions"][1]["reason"]
    rows = {r["name"]: r for r in chain_mod.compatible_at([{"stage": "preprocessing", "algorithm": "detrend", "params": {}}], 1)["rows"]}
    assert rows["preprocessing.window_pool"]["ok"] is False


def test_a_pool_chain_runs_through_post_runs_and_ships_what_its_pages_draw(client):
    ids = [s["id"] for s in client.get("/api/windowsets/library").json()["sets"]]
    steps = [{"stage": "preprocessing", "algorithm": "window_pool",
              "params": {"window_sets": ",".join(map(str, ids)), "per_scale": 200}},
             {"stage": "preprocessing", "algorithm": "trace_shape", "params": {}},
             {"stage": "catalogue", "algorithm": "shape_cluster", "params": {"sample": 150, "k": 3}}]
    job, _snap = _run(client, steps)
    pool = client.get(f"/api/runs/{job}/steps/0").json()
    assert pool["type"] == "windowset" and pool["pool"]["n_windows"] == 600
    assert {(b["scale_min"]) for b in pool["pool"]["by"]} == {1, 10, 30}
    assert "dropped" in pool["pool"] and "members" in pool["pool"]
    shape = client.get(f"/api/runs/{job}/steps/1").json()
    assert shape["type"] == "windowset" and shape["shape"]["under_floor"]["n"] == 0
    assert shape["shape"]["resample_length"] == 256
    clus = client.get(f"/api/runs/{job}/steps/2").json()
    assert clus["type"] == "grouping"
    t = clus["tree"]
    assert t["n_clustered"] == 150 and t["k"] == 3 and t["key"]
    assert len(t["dendrogram"]["icoord"]) == len(t["dendrogram"]["dcoord"])
    assert [r["k"] for r in t["propose"]["by_k"]][:2] == [2, 3]
    # everything the chain wrote is inside the sandbox
    rt = client.rt
    for p in (t["dir"], shape["shape"]["shape_file"], pool["pool"]["path"]):
        assert os.path.abspath(p).lower().startswith(os.path.abspath(rt.dir).lower()), p
