"""
test_webui_cnn_slurm.py
=======================
fixup-AI, the bridge: Models › Launch, arm B.2, model *CNN (fusion / GASF /
GADF / recurrence)* → *Create SLURM script* writes the job directory and the
script and lists what must be copied to the cluster and how big it is; *Run the
local smoke* trains the same recipe on a few windows on this CPU, imports it
through the same function the cluster's results return by, and the run is
listed with the B.2 runs (Results reads it); the Shape clustering page's
*Create SLURM script · Ward over every training window* writes the high-memory
CPU job.

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_cnn_slurm.py -q
"""

import json
import os
import sqlite3
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
            np.save(npy, 0.01 * np.random.default_rng(ch).standard_normal(n) + 0.3 * t / n
                    - 0.5 * np.exp(-(((t - 777) % 2400) / 15.0) ** 2))
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


def _wait(c, url, timeout=900):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = c.get(url).json()
        if s["status"] in ("completed", "failed", "cancelled"):
            return s
        time.sleep(0.3)
    raise AssertionError(f"{url} did not finish")


@pytest.fixture(scope="module")
def ran(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("cnn_routes")
    db = _db(tmp)
    dist = tmp / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    rt = Runtime(mode="sandbox", stamp="20261006-ai", db_source=str(db), runtime_root=str(tmp / "runtime"),
                 client_dist=str(dist))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            con = sqlite3.connect(rt.db_path)
            rid = con.execute("SELECT id FROM recordings WHERE source_file = ? AND channel = 0", (AUG,)).fetchone()[0]
            con.close()
            ids = [s["id"] for s in c.get("/api/windowsets/library").json()["sets"]]
            mapping = {"k": 2, "clusters": {"1": {"name": "drop", "class": "interesting"},
                                            "2": {"name": "", "class": "not_interesting"}}}
            steps = [{"stage": "preprocessing", "algorithm": "window_pool",
                      "params": {"window_sets": ",".join(map(str, ids)), "per_scale": 150}},
                     {"stage": "preprocessing", "algorithm": "trace_shape", "params": {}},
                     {"stage": "catalogue", "algorithm": "shape_cluster",
                      "params": {"sample": 150, "k": 2, "mapping": json.dumps(mapping)}}]
            job = c.post("/api/runs", json={"recording_id": rid, "span": [0, 1], "steps": steps}).json()["job_id"]
            s = _wait(c, f"/api/runs/{job}")
            assert s["status"] == "completed", s.get("error")
            pool = c.get(f"/api/runs/{job}/steps/0").json()["pool"]
            tree = c.get(f"/api/runs/{job}/steps/2").json()["tree"]
            tpl = c.post("/api/templates", json={"name": "shape_clusters_ai", "steps": steps}).json()
            yield c, rt, tpl["id"], pool["window_set_id"], tree
    finally:
        rt.restore()


def test_launch_offers_the_cnn_arm_and_its_encodings(ran):
    c, _rt, tpl, pool, _tree = ran
    s = c.get("/api/models/b2/setup", params={"template": tpl, "pool": pool}).json()
    cnn = s["cnn"]
    assert cnn["encodings"][0] == "fusion" and set(cnn["encodings"]) == {"fusion", "GASF", "GADF", "recurrence"}
    assert cnn["defaults"]["img_size"] == 224 and "never" in cnn["images_rule"].lower()
    assert cnn["null"]["default_on"] is False and cnn["null"]["n"] == 5
    assert "import-results" in cnn["returns"]                  # the line on how results come back


def test_create_slurm_script_writes_the_job_and_lists_what_to_copy(ran):
    c, rt, tpl, pool, _tree = ran
    r = c.post("/api/models/b2/cnn/slurm", json={"template": tpl, "pool": pool, "encoding": "fusion"})
    assert r.status_code == 200, r.text
    j = _wait(c, f"/api/jobs/{r.json()['job_id']}")
    assert j["status"] == "completed", j
    res = j["result"]
    assert "--gres=gpu:a100" in res["script"] and "cnn-run" in res["script"]
    assert os.path.isfile(res["script_path"]) and res["script_path"].startswith(rt.dir)
    whats = {x["what"] for x in res["copy"]}
    assert {"job directory", "channel array"} <= whats and res["total_bytes"] > 0
    assert res["estimate"]["label"].lower().startswith("estimate")
    assert res["steps"] and any("sbatch" in s for s in res["steps"])
    assert any("import-results" in s for s in res["steps"])
    assert res["null_script"] is None


def test_the_local_smoke_runs_here_and_its_run_is_listed_with_the_b2_runs(ran):
    pytest.importorskip("torch")
    c, _rt, tpl, pool, _tree = ran
    r = c.post("/api/models/b2/cnn/smoke", json={"template": tpl, "pool": pool, "encoding": "GASF",
                                                  "smoke": {"n_train": 16, "n_predict": 6},
                                                  "cnn": {"img_size": 32, "pretrained": False, "batch_size": 8}})
    assert r.status_code == 200, r.text
    j = _wait(c, f"/api/jobs/{r.json()['job_id']}")
    assert j["status"] == "completed", j
    rid = j["result"]["run_id"]
    runs = {x["run_id"]: x for x in c.get("/api/models/b2/runs").json()["runs"]}
    assert rid in runs and "CNN" in runs[rid]["model"] and runs[rid]["status"] == "completed"
    assert runs[rid]["smoke"] is True
    assert j["result"]["measured"]["encode_ms_by_scale"]


def test_the_ward_script_for_every_training_window(ran):
    c, _rt, _tpl, _pool, tree = ran
    r = c.post(f"/api/shape/trees/{tree['key']}/ward-slurm", json={})
    assert r.status_code == 200, r.text
    res = r.json()
    assert "--mem=" in res["script"] and "ward-run" in res["script"] and "--gres" not in res["script"]
    assert res["n"] == tree["n_train"] and res["memory"]["request_gb"] >= 1
    assert {x["what"] for x in res["copy"]} >= {"job directory"}
    assert any("import-results" in s for s in res["steps"])
