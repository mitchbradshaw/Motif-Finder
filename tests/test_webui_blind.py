"""
test_webui_blind.py
===================
fixup-AH, the bridge: Models › Results → *Label test windows blind* makes a
blind Review queue over a B.2 run's test and exam windows; the labelling card's
payload carries NOTHING that could tip the answer; a label goes through Review's
own verdict route into the human store; the first label freezes the pool's cut
and mapping (Launch's 409); and Results reads the run "against a blind human".

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_blind.py -q
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
#: keys that would tip a blind answer, anywhere in a payload the labelling card reads
FORBIDDEN = {"cluster", "class", "p_interesting", "score", "weight", "role", "exam", "prior_verdict", "modelCall",
             "model", "first_showing", "repeat", "stratum_size", "stratum_drawn", "mapping", "predictions_path"}


def _keys(obj):
    out = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(k)
            out |= _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            out |= _keys(v)
    return out


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


def _wait(c, url, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = c.get(url).json()
        if s["status"] in ("completed", "failed", "cancelled"):
            return s
        time.sleep(0.3)
    raise AssertionError(f"{url} did not finish")


@pytest.fixture(scope="module")
def ran(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("blind_routes")
    db = _db(tmp)
    dist = tmp / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    rt = Runtime(mode="sandbox", stamp="20261006-ah", db_source=str(db), runtime_root=str(tmp / "runtime"), client_dist=str(dist))
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
            tpl = c.post("/api/templates", json={"name": "shape_clusters_ah", "steps": steps}).json()
            r = c.post("/api/models/b2/train", json={"template": tpl["id"], "pool": pool["window_set_id"], "n_estimators": 30})
            assert r.status_code == 200, r.text
            j = _wait(c, f"/api/jobs/{r.json()['job_id']}")
            assert j["status"] == "completed", j
            run_id = c.get("/api/models/b2/runs").json()["runs"][0]["run_id"]
            c.rt = rt
            yield c, pool, tpl, steps, run_id
    finally:
        rt.restore()


def test_label_test_windows_blind_makes_one_blind_queue_per_run(ran):
    c, _pool, _tpl, _steps, run_id = ran
    r = c.post(f"/api/models/b2/runs/{run_id}/blind", json={"n": 40, "repeat_frac": 0.1, "seed": 0})
    assert r.status_code == 200, r.text
    made = r.json()
    assert made["queue_id"] and made["summary"]["n"] == 40 and made["summary"]["n_repeats"] == 4
    again = c.post(f"/api/models/b2/runs/{run_id}/blind", json={"n": 40, "repeat_frac": 0.1, "seed": 0}).json()
    assert again["queue_id"] == made["queue_id"]
    assert c.post(f"/api/models/b2/runs/{run_id}/blind", json={"n": 41}).status_code == 409   # the sample is fixed
    assert c.post(f"/api/models/b2/runs/{run_id}/blind", json={"n": 2001}).status_code == 422
    qs = {q["id"]: q for q in c.get("/api/review/queues").json()}
    q = qs[made["queue_id"]]
    assert q["source_kind"] == "blind-test" and q["unit"] == "test window" and q["writes_to"] == "annotations"
    assert q["total"] == 44 and q["judged"] == 0


def test_nothing_the_labelling_card_reads_could_tip_the_answer(ran):
    c, _pool, _tpl, _steps, run_id = ran
    qid = c.post(f"/api/models/b2/runs/{run_id}/blind", json={"n": 40, "repeat_frac": 0.1, "seed": 0}).json()["queue_id"]
    page = c.get(f"/api/models/b2/blind/{qid}")
    assert page.status_code == 200, page.text
    p = page.json()
    assert len(p["showings"]) == 44 and not _keys(p) & FORBIDDEN, _keys(p) & FORBIDDEN
    one = c.get(f"/api/models/b2/blind/{qid}/showings/0", params={"px": 600, "pad": 1})
    assert one.status_code == 200, one.text
    w = one.json()
    assert not _keys(w) & FORBIDDEN, _keys(w) & FORBIDDEN
    assert w["unit"] == "mV" and w["trace"]["t"] and w["duration_s"] > 0 and w["scale_text"]
    # the window's own bounds, with context either side
    assert w["trace"]["t0_s"] < w["window"]["t0_s"] < w["window"]["t1_s"] <= w["trace"]["t1_s"]
    # Review's generic queue read carries no machine call and no thumbnails (a repeat would be found by eye)
    gq = c.get(f"/api/review/queues/{qid}").json()
    rows = gq.get("items") or gq.get("rows") or []
    assert rows and all(not (set(r) & FORBIDDEN) for r in rows)
    assert all(not r.get("thumb") for r in rows)


def test_a_label_lands_in_the_human_store_freezes_the_cut_and_results_read_it(ran):
    c, pool, tpl, steps, run_id = ran
    qid = c.post(f"/api/models/b2/runs/{run_id}/blind", json={"n": 40, "repeat_frac": 0.1, "seed": 0}).json()["queue_id"]
    assert c.get("/api/models/b2/frozen", params={"pool_key": pool["key"]}).json()["frozen"] is None
    for i in range(10):
        r = c.post(f"/api/review/queues/{qid}/verdict", json={"target_id": i, "verdict": "interesting" if i % 3 else "not_interesting"})
        assert r.status_code == 200, r.text
    con = sqlite3.connect(c.rt.db_path)
    try:
        n = con.execute("SELECT COUNT(*) FROM annotations WHERE source = 'blind_test_review' AND deleted_at IS NULL").fetchone()[0]
    finally:
        con.close()
    assert n == 10
    fz = c.get("/api/models/b2/frozen", params={"pool_key": pool["key"]}).json()["frozen"]
    assert fz and fz["run_id"] == run_id
    # Launch: a different cut is now refused with the run named (409)
    other = json.loads(json.dumps(steps))
    other[2]["params"]["k"] = 3
    other[2]["params"]["mapping"] = json.dumps({"k": 3, "clusters": {str(i): {"name": "", "class": "interesting" if i == 1 else "not_interesting"} for i in (1, 2, 3)}})
    tpl3 = c.post("/api/templates", json={"name": "shape_clusters_ah_k3", "steps": other}).json()
    r = c.post("/api/models/b2/train", json={"template": tpl3["id"], "pool": pool["window_set_id"]})
    assert r.status_code == 409 and f"run {run_id}" in r.text
    # Results: against a blind human
    sc = c.get(f"/api/models/b2/runs/{run_id}/blind")
    assert sc.status_code == 200, sc.text
    s = sc.json()
    assert s["queue_id"] == qid and s["progress"]["judged"] == 10
    assert set(s["exams"]) == {"i_later_block", "ii_unseen_channels"}
    assert sum(e["n_scored"] for e in s["exams"].values()) <= 10
    for e in s["exams"].values():
        assert "self_agreement" in e and "null" in e and "per_cluster" in e
    assert s["reference"]["status"] in ("not computed", "computed")
    # the step-through of disagreements
    d = c.get(f"/api/models/b2/runs/{run_id}/blind/disagreements", params={"exam": "i_later_block", "kind": "model_yes_human_no"})
    assert d.status_code == 200 and isinstance(d.json()["windows"], list)
    # a run with no queue reads as not yet labelled, not as an error
    assert c.get("/api/models/b2/runs/99999/blind").status_code == 404
