"""
test_webui_shape_b2.py
======================
fixup-ag seam (iii), the bridge: *Train model* hands the chain to Models ›
Launch prefilled with arm **B.2 cluster labels · trace shape** — the template,
the pool as the sources (its recordings, channels and roles), the cut and the
mapping read-only, the freeze — and *Train locally* runs the forest as a job.
Also the researcher's rename of a window set (Library › Window sets): the name
changes, the key and the version do not, and an audit row says so.

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_shape_b2.py -q
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


def _wait(c, url, timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = c.get(url).json()
        if s["status"] in ("completed", "failed", "cancelled"):
            return s
        time.sleep(0.3)
    raise AssertionError(f"{url} did not finish")


@pytest.fixture(scope="module")
def ran(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("b2")
    db = _db(tmp)
    dist = tmp / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    rt = Runtime(mode="sandbox", stamp="20261006-b2", db_source=str(db), runtime_root=str(tmp / "runtime"), client_dist=str(dist))
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
                      "params": {"window_sets": ",".join(map(str, ids)), "per_scale": 200}},
                     {"stage": "preprocessing", "algorithm": "trace_shape", "params": {}},
                     {"stage": "catalogue", "algorithm": "shape_cluster",
                      "params": {"sample": 150, "k": 2, "mapping": json.dumps(mapping)}}]
            job = c.post("/api/runs", json={"recording_id": rid, "span": [0, 1], "steps": steps}).json()["job_id"]
            s = _wait(c, f"/api/runs/{job}")
            assert s["status"] == "completed", s.get("error")
            pool = c.get(f"/api/runs/{job}/steps/0").json()["pool"]
            c.tree_key = c.get(f"/api/runs/{job}/steps/2").json()["tree"]["key"]
            tpl = c.post("/api/templates", json={"name": "shape_clusters_test", "steps": steps}).json()
            c.rt = rt
            yield c, pool, tpl, steps
    finally:
        rt.restore()


def test_launch_is_prefilled_with_the_template_the_pool_and_arm_b2(ran):
    c, pool, tpl, _steps = ran
    r = c.get("/api/models/b2/setup", params={"template": tpl["id"], "pool": pool["window_set_id"]})
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["template"]["id"] == tpl["id"] and s["template"]["name"] == "shape_clusters_test"
    assert s["pool"]["id"] == pool["window_set_id"] and s["pool"]["key"] == pool["key"]
    assert {(b["recording"], b["role"]) for b in s["pool"]["by"]} >= {(AUG, "train"), (AUG, "exam")}
    roles = {ch["role"] for rec in s["pool"]["recordings"] for ch in rec["channels"]}
    assert roles == {"train", "exam"}
    arm = s["arm"]
    assert arm["label"] == "B.2 cluster labels · trace shape" and arm["k"] == 2 and arm["read_only"] is True
    assert arm["mapping"]["clusters"]["1"]["class"] == "interesting" and arm["mapping_state"] == "complete"
    assert s["frozen"] is None and "raw" in s["inputs"]["rule"]
    assert s["checks"] and all(ch["level"] != "error" for ch in s["checks"])


def test_train_locally_runs_the_forest_as_a_job_and_lists_the_run(ran):
    c, pool, tpl, _steps = ran
    r = c.post("/api/models/b2/train", json={"template": tpl["id"], "pool": pool["window_set_id"], "n_estimators": 30})
    assert r.status_code == 200, r.text
    s = _wait(c, f"/api/jobs/{r.json()['job_id']}")
    assert s["status"] == "completed", s
    runs = c.get("/api/models/b2/runs").json()["runs"]
    assert runs and runs[0]["status"] == "completed" and runs[0]["k"] == 2
    d = runs[0]["diagnostic"]
    assert d["kind"] == "diagnostic" and 0.0 <= d["accuracy"] <= 1.0
    assert os.path.abspath(runs[0]["results_path"]).lower().startswith(os.path.abspath(c.rt.dir).lower())


def test_a_mapping_that_does_not_cover_the_cut_is_refused_before_training(ran):
    c, pool, _tpl, steps = ran
    steps = json.loads(json.dumps(steps))
    steps[2]["params"]["mapping"] = json.dumps({"k": 2, "clusters": {"1": {"name": "", "class": "interesting"}}})
    tpl = c.post("/api/templates", json={"name": "shape_clusters_partial", "steps": steps}).json()
    s = c.get("/api/models/b2/setup", params={"template": tpl["id"], "pool": pool["window_set_id"]}).json()
    assert any(ch["level"] == "error" and "map" in ch["detail"] for ch in s["checks"])
    r = c.post("/api/models/b2/train", json={"template": tpl["id"], "pool": pool["window_set_id"]})
    assert r.status_code == 422


def test_a_window_set_is_renamed_its_key_and_version_kept_and_audited(ran):
    c, _pool, _tpl, _steps = ran
    sets = c.get("/api/windowsets/library").json()["sets"]
    one = next(s for s in sets if s["name"] == "ws_syn_concat_fs1_30min")
    r = c.patch(f"/api/windowsets/{one['id']}/name", json={"name": "M2-like_30min"})
    assert r.status_code == 200, r.text
    after = next(s for s in c.get("/api/windowsets/library").json()["sets"] if s["id"] == one["id"])
    assert after["name"] == "M2-like_30min" and after["key"] == one["key"] and after["version"] == one["version"]
    con = sqlite3.connect(c.rt.db_path)
    try:
        audit = con.execute("SELECT what FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()[0]
    finally:
        con.close()
    assert "ws_syn_concat_fs1_30min" in audit and "M2-like_30min" in audit
    taken = next(s for s in sets if s["name"] == "ws_syn_concat_fs1_10min")
    assert c.patch(f"/api/windowsets/{taken['id']}/name", json={"name": "M2-like_30min"}).status_code == 409
    assert c.patch(f"/api/windowsets/{taken['id']}/name", json={"name": "has space"}).status_code == 422
    assert c.patch("/api/windowsets/99999/name", json={"name": "nope"}).status_code == 404


def test_the_cluster_cards_follow_the_cut_one_per_cluster_from_the_kept_tree(ran):
    """The researcher (2026-10-06): if the cut gives 24 classes there are 24 motifs shown — one card per cluster at
    the CURRENT cut, redrawn when the cut moves, read from the kept tree without re-running the chain."""
    c, _pool, _tpl, _steps = ran
    sizes = None
    for k in (2, 5, 9):
        r = c.get(f"/api/shape/trees/{c.tree_key}/cards", params={"k": k})
        assert r.status_code == 200, r.text
        cards = r.json()
        assert cards["k"] == k and len(cards["cards"]) == k
        assert [x["cluster"] for x in cards["cards"]] == list(range(1, k + 1))
        for x in cards["cards"]:
            assert len(x["medoid"]["shape"]) == 256 and 1 <= len(x["members"]) <= cards["n_members"]
            assert x["n"] > 0 and sum(x["scales"].values()) == x["n"]
        total = sum(x["n"] for x in cards["cards"])
        sizes = sizes or total
        assert total == sizes                      # every training window, at every cut
    assert c.get(f"/api/shape/trees/{c.tree_key}/cards", params={"k": 10_000}).status_code == 422
