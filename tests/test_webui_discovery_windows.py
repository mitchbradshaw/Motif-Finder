"""
test_webui_discovery_windows.py
===============================
Round A_2, P3, the bridge side: *Apply template* takes a window scope (length and overlap, 50 % recommended) beside
Channels and Bands.

* ``POST /api/discovery/plan`` with ``windows`` says how many windows each channel has, how many runs that is with
  the null, what it costs and the route; a window shorter than the chain allows is refused naming the step, and the
  explicit opt-in fits the chain to it (a different chain). The answer is small: no per-window list.
* ``POST /api/discovery/templates/apply`` with ``windows`` makes ONE Discovery run whose runs are the stitched ones,
  so Runs, the Scoreboard and the Map read the stitched set; its label names the scale.
* The Map reads the windowed application as its own row beside the whole-span run.
* ``POST /api/discovery/slurm`` exports a windowed run as one task per channel.

FastAPI lives only in ``webui/.venv``:

    "C:/Users/mmebr/Documents/CNN/webui/.venv/Scripts/python.exe" -m pytest tests/test_webui_discovery_windows.py -q -p no:cacheprovider
"""

import json
import os
import sqlite3
import sys
import time

import numpy as np
import pytest
from scipy.signal import lfilter

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

FS = 1.0
H = 3600
N = 8 * H
CH = ["CH1", "CH2"]
SECTION = [0.0, 8.0]
TWO_HOURS = {"window_s": 2 * H}


def _coloured(seed, n=N):
    rng = np.random.default_rng(seed)
    x = lfilter([1.0], [1.0, -0.97], rng.standard_normal(n) * 0.001)
    for a in range(900, n - 900, 2700):
        x[a:a + 120] -= 0.03
    return x


@pytest.fixture
def client(tmp_path):
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    for ch in range(2):
        npy = tmp_path / f"CH{ch}.npy"
        np.save(npy, _coloured(ch))
        conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path, units) "
                     "VALUES ('syn.mat', ?, ?, ?, 0, ?, 'V')", (ch, FS, N, str(npy)))
    conn.commit()
    conn.close()
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    rt = Runtime(mode="sandbox", stamp="20261018-windows", db_source=str(db),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(dist))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            r = c.put("/api/discovery/session", json={"name": "windows", "recording": "syn", "channels": CH,
                                                      "section": SECTION})
            assert r.status_code == 200, r.text
            r = c.put("/api/settings/nulls", json={"values": {"null.detection.draws": 1}})
            assert r.status_code == 200, r.text
            yield c
    finally:
        rt.restore()


def _q(client, sql, args=()):
    conn = sqlite3.connect(client.app.state.rt.db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def _wait_job(client, job_id, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get(f"/api/jobs/{job_id}").json()
        if s["status"] in ("completed", "failed", "cancelled"):
            return s
        time.sleep(0.25)
    raise AssertionError(f"job {job_id} did not finish")


def _plan(client, windows=None, template="noise_threshold"):
    body = {"template": template, "channels": CH, "t0": SECTION[0], "t1": SECTION[1]}
    if windows is not None:
        body["windows"] = windows
    r = client.post("/api/discovery/plan", json=body)
    assert r.status_code == 200, r.text
    return r


def _apply(client, windows=None, run=True, template="noise_threshold"):
    body = {"templates": [template], "channels": CH, "t0": SECTION[0], "t1": SECTION[1], "run": run}
    if windows is not None:
        body["windows"] = windows
    r = client.post("/api/discovery/templates/apply", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert len(out) == 1
    if run:
        assert out[0]["started"], out[0]
        s = _wait_job(client, out[0]["job_id"])
        assert s["status"] == "completed", s
    return out[0]


def test_the_plan_says_how_many_windows_and_what_they_cost(client):
    r = _plan(client, TWO_HOURS)
    plan = r.json()
    assert plan["runnable"], plan["reason"]
    w = plan["windows"]
    assert w["scope"] == {"kind": "windows", "window_s": 7200.0, "overlap_frac": 0.5, "fit": False}
    assert w["per_channel"] == 7 and w["targets"] == 14 and w["runs"] == 28, "7 windows x 2 channels x (1 + 1 draw)"
    assert w["recommendedOverlap"] == 0.5
    assert w["minimum"]["minimum_s"] == 2400.0 and w["minimum"]["step"] == 0
    assert w["overhead_s"] > 0 and plan["route"] in ("local", "unknown")
    assert "own thresholds" in w["tradeOff"]
    assert len(r.content) < 30_000, "the plan answers counts, not a list of every window"
    assert "targets" not in plan or len(plan["targets"]) <= 2


def test_a_window_under_the_chains_minimum_is_refused_naming_the_step_and_can_be_fitted(client):
    plan = _plan(client, {"window_s": 600}).json()
    assert not plan["runnable"]
    assert "step 01" in plan["reason"] and "40 min" in plan["reason"]
    fitted = _plan(client, {"window_s": 600, "fit": True}).json()
    assert fitted["runnable"], fitted["reason"]
    assert fitted["windows"]["fitted"] == [{"step": 0, "name": "preprocessing.detrend", "param": "window_s",
                                            "from": 600.0, "to": 150.0}]
    r = client.post("/api/discovery/templates/apply", json={"templates": ["noise_threshold"], "channels": CH,
                                                            "t0": SECTION[0], "t1": SECTION[1], "run": False,
                                                            "windows": {"window_s": 600}})
    assert r.status_code == 422 and "step 01" in r.text


def test_a_windowed_application_is_one_discovery_run_of_stitched_runs(client):
    out = _apply(client, TWO_HOURS)
    rows = client.get("/api/discovery/runs").json()
    row = next(r for r in rows if r["key"] == out["run_key"])
    assert row["status"] == "done"
    assert "2 h windows" in row["label"] and "50 %" in row["label"]
    assert row["windows"]["per_channel"] == 7 and row["windows"]["scope"]["window_s"] == 7200.0
    dr = _q(client, "SELECT params_json FROM discovery_runs WHERE run_key = ?", (out["run_key"],))[0]
    ids = json.loads(dr["params_json"])["run_ids"]
    assert len(ids) == 2, "one stitched run per channel"
    for rid in ids:
        cfg = _q(client, "SELECT c.config_json FROM runs r JOIN configs c ON c.id = r.config_id WHERE r.id = ?",
                 (rid,))[0]
        assert json.loads(cfg["config_json"])["windows"]["window_s"] == 7200.0
    found = sum(_q(client, "SELECT COUNT(*) AS n FROM detections WHERE run_id = ?", (rid,))[0]["n"] for rid in ids)
    assert row["found"] == found > 0
    board = client.get("/api/discovery/scoreboard", params={"runs": out["run_key"], "channels": ",".join(CH),
                                                             "t0": SECTION[0], "t1": SECTION[1]})
    assert board.status_code == 200, board.text


def test_the_map_has_the_windowed_row_beside_the_whole_span_row(client):
    whole = _apply(client)
    win = _apply(client, TWO_HOURS)
    m = client.get("/api/discovery/map").json()
    labels = {r["label"] for r in m["rows"] if r["kind"] != "human"}
    assert len(labels) == 2, labels
    assert any("2 h windows" in lb for lb in labels) and "noise_threshold v1" in labels
    assert whole["run_key"] != win["run_key"]


def test_a_windowed_run_exports_one_task_per_channel(client):
    out = _apply(client, TWO_HOURS, run=False)
    r = client.post("/api/discovery/slurm", json={"template": "noise_threshold", "channels": CH, "t0": SECTION[0],
                                                  "t1": SECTION[1], "runKey": out["run_key"], "dryRun": True})
    assert r.status_code == 200, r.text
    assert r.json()["tasks"] == 2
    r = client.post("/api/discovery/slurm", json={"template": "noise_threshold", "channels": CH, "t0": SECTION[0],
                                                  "t1": SECTION[1], "runKey": out["run_key"]})
    assert r.status_code == 200, r.text
    with open(r.json()["spec_path"], encoding="utf-8") as f:
        spec = json.load(f)
    assert spec["windows"]["scope"]["window_s"] == 7200.0
    assert [len(t["windows"]["spans"]) for t in spec["targets"]] == [7, 7]


def test_the_preview_measures_one_window_and_costs_every_window_with_its_draws(client):
    r = client.post("/api/discovery/preview", json={"template": "noise_threshold", "channels": CH, "t0": SECTION[0],
                                                    "t1": SECTION[1], "sampleHours": 4, "windows": TWO_HOURS})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["sample_samples"] == 2 * H, "the sample is one window"
    assert p["runs"] == 28 and p["windows"] == 14
    assert p["estimate_s"] == pytest.approx(p["per_window_s"] * 28)


def test_running_a_short_window_as_it_is_is_asked_for_and_said(client):
    plan = _plan(client, {"window_s": 600, "allow_short": True}).json()
    assert plan["runnable"], plan["reason"]
    assert "step 01" in plan["windows"]["warning"]
    out = _apply(client, {"window_s": 600, "allow_short": True}, run=False)
    rows = client.get("/api/discovery/runs").json()
    row = next(r for r in rows if r["key"] == out["run_key"])
    assert "as is, warned" in row["label"] and "step 01" in row["windows"]["warning"]


def test_a_windowed_run_comes_back_from_the_cluster_as_one_stitched_run(client):
    from Working.discovery import chain_job

    out = _apply(client, TWO_HOURS, run=False)
    key = out["run_key"]
    r = client.post("/api/discovery/slurm", json={"template": "noise_threshold", "channels": CH, "t0": SECTION[0],
                                                  "t1": SECTION[1], "runKey": key})
    assert r.status_code == 200, r.text
    made = r.json()
    with open(made["spec_path"], encoding="utf-8") as f:
        spec = json.load(f)
    results = [chain_job.run_task(spec, task=i, out_dir=made["result_dir"]) for i in range(spec["tasks"])]
    assert all(res["complete"] for res in results), [res.get("error") for res in results]
    r = client.post("/api/discovery/chain/import", json={"runKey": key})
    assert r.status_code == 200, r.text
    assert _wait_job(client, r.json()["job_id"])["status"] == "completed"
    rows = client.get("/api/discovery/runs").json()
    row = next(x for x in rows if x["key"] == key)
    assert row["status"] == "done" and row["hpcImported"] is True
    assert row["clusterAgrees"] is True, row.get("clusterCheck")
    params = json.loads(_q(client, "SELECT params_json FROM discovery_runs WHERE run_key = ?", (key,))[0]["params_json"])
    assert len(params["run_ids"]) == 2 and params["hpc"]["imported"]["windowRuns"] == 2 * 7 * 2
    raw = sum(sum(len(w["detections"]) for w in res["windows"]) for res in results)
    assert row["found"] <= raw, "the run holds the stitched set, never more than the windows found"
    assert [s["windows"] for s in params["windows"]["stitch"]] == [7, 7]
