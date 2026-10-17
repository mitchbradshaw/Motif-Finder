"""
test_webui_chain_job_route.py
=============================
Round A_2, P2, the bridge side: a Discovery template run sent to the cluster
comes back as a real Discovery run.

* ``POST /api/discovery/slurm`` takes the run's key: it writes the chain job
  (`Working.discovery.chain_job`: the spec and an array script, one task per
  channel, the null in the same task) and marks THAT row *on cluster* with its
  ``params.hpc`` — server-side, as the seed export does. ``dryRun`` shows the
  script and writes nothing (the modal's preview).
* ``GET /api/hpc/cluster`` lists the chain job from its run row: *written*,
  *partial* (some tasks back), *returned*, *imported*, read off the task result
  files; it imports through the same function as Discovery's button.
* ``POST /api/discovery/chain/import`` (Discovery) and ``POST /api/hpc/chain/import``
  (Jobs, by the spec's path): verify, restore the step cache, then the ordinary
  local sweep writes every row. An incomplete or mismatched result is refused
  with what is missing, and nothing is recorded.
* After the import, the same template applied again plans **local** and runs
  from the imported cache — the profile is not computed again.

FastAPI lives only in ``webui/.venv``:

    "C:/Users/mmebr/Documents/CNN/webui/.venv/Scripts/python.exe" -m pytest tests/test_webui_chain_job_route.py -q -p no:cacheprovider
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

from Adapters.registry import get_adapter  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.discovery import chain_job  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402

FS = 1.0
N = 3000
CH = ["CH1", "CH2"]
SECTION = [0.0, N / 3600.0]


def _coloured(seed, n=N):
    rng = np.random.default_rng(seed)
    e = rng.standard_normal(n) * 0.01
    x = np.empty(n)
    x[0] = 0.0
    for i in range(1, n):
        x[i] = 0.97 * x[i - 1] + e[i]
    drop = -0.2 * np.exp(-np.linspace(0, 4, 90))
    for a in range(200, n - 200, 470):
        x[a:a + 90] += drop
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
    rt = Runtime(mode="sandbox", stamp="20261017-chain-job", db_source=str(db),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(dist))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            r = c.put("/api/discovery/session", json={"name": "chain", "recording": "syn", "channels": CH,
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


def _add(client, template, run=False):
    r = client.post("/api/discovery/templates/apply", json={"templates": [template], "channels": CH,
                                                            "t0": SECTION[0], "t1": SECTION[1], "run": run})
    assert r.status_code == 200, r.text
    return r.json()[0]


def _export(client, key, template, dry=False):
    r = client.post("/api/discovery/slurm", json={"template": template, "channels": CH, "t0": SECTION[0],
                                                  "t1": SECTION[1], "runKey": key, "dryRun": dry})
    assert r.status_code == 200, r.text
    return r.json()


def _row(client, key):
    rows = _q(client, "SELECT * FROM discovery_runs WHERE run_key = ?", (key,))
    assert len(rows) == 1
    return rows[0]


def _params(client, key):
    return json.loads(_row(client, key)["params_json"] or "{}")


def _spec(made):
    with open(made["spec_path"], encoding="utf-8") as f:
        return json.load(f)


def _cluster(client):
    r = client.get("/api/hpc/cluster")
    assert r.status_code == 200, r.text
    return r.json()


def _chain_row(client, key):
    rows = [j for j in _cluster(client)["jobs"] if j.get("run_key") == key and j.get("source") == "chain"]
    assert len(rows) == 1, [(j["name"], j["source"], j.get("run_key")) for j in _cluster(client)["jobs"]]
    return rows[0]


def _runs(client):
    r = client.get("/api/discovery/runs")
    assert r.status_code == 200, r.text
    return {x["key"]: x for x in r.json()}


# ── the export ─────────────────────────────────────────────────────────────

def test_create_slurm_script_marks_that_run_on_the_cluster_with_its_record(client):
    added = _add(client, "noise_threshold")
    key = added["run_key"]
    made = _export(client, key, "noise_threshold")
    assert made["run_key"] == key and made["tasks"] == 2 and made["draws"] == 1
    assert os.path.isfile(made["spec_path"]) and os.path.isfile(made["script_path"])
    assert "#SBATCH --array=0-1" in made["script"]
    row = _row(client, key)
    assert row["status"] == "on cluster"
    hpc = json.loads(row["params_json"])["hpc"]
    assert hpc["kind"] == "chain" and hpc["tasks"] == 2 and hpc["draws"] == 1
    assert hpc["specHash"] == chain_job.spec_hash(_spec(made))
    assert hpc["resultPath"] and hpc["specPath"] and hpc["scriptPath"] and hpc["sbatch"].startswith("sbatch ")
    run = _runs(client)[key]
    assert run["status"] == "on cluster" and run["hpc"]["kind"] == "chain"


def test_a_dry_run_shows_the_script_and_writes_nothing(client):
    key = _add(client, "noise_threshold")["run_key"]
    made = _export(client, key, "noise_threshold", dry=True)
    assert made["dryRun"] is True and "#SBATCH --array=0-1" in made["script"]
    assert not os.path.exists(made["spec_path"]) and not os.path.exists(made["script_path"])
    assert _row(client, key)["status"] == "new"
    assert "hpc" not in _params(client, key)


def test_a_store_reading_template_is_refused_for_export_by_name(client):
    r = client.post("/api/discovery/slurm", json={"template": "manual_labels_model", "channels": CH,
                                                  "t0": SECTION[0], "t1": SECTION[1]})
    assert r.status_code == 422, r.text
    assert "catalogue.manual_labels" in r.text


# ── Jobs: the chain job's states ───────────────────────────────────────────

def test_jobs_lists_the_chain_job_and_reads_its_state_off_the_task_results(client):
    key = _add(client, "noise_threshold")["run_key"]
    made = _export(client, key, "noise_threshold")
    spec = _spec(made)
    row = _chain_row(client, key)
    assert row["kind"] == "detection_chain" and row["workspace"] == "Discovery"
    assert row["state"] == "written" and row["import_how"] == "chain" and row["import_path"] == made["spec_path"]
    assert row["progress"] == {"tasks_done": 0, "tasks": 2}
    assert any(c["what"] == "spec" for c in row["copy"]) and any(c["what"] == "channel array" for c in row["copy"])
    # the script is listed once, from its run row, not again as a flat recipe script
    assert sum(1 for j in _cluster(client)["jobs"] if j["name"] == row["name"]) == 1
    chain_job.run_task(spec, task=0, out_dir=made["result_dir"])
    row = _chain_row(client, key)
    assert row["state"] == "partial" and row["progress"] == {"tasks_done": 1, "tasks": 2}
    chain_job.run_task(spec, task=1, out_dir=made["result_dir"])
    row = _chain_row(client, key)
    assert row["state"] == "returned" and row["returned"]["status"] == "complete"
    assert _cluster(client)["counts"]["to_import"] >= 1


# ── the import ─────────────────────────────────────────────────────────────

def test_the_import_from_discovery_runs_the_sweep_here_and_the_run_is_done(client):
    key = _add(client, "noise_threshold")["run_key"]
    made = _export(client, key, "noise_threshold")
    spec = _spec(made)
    results = [chain_job.run_task(spec, task=i, out_dir=made["result_dir"]) for i in range(2)]
    r = client.post("/api/discovery/chain/import", json={"runKey": key})
    assert r.status_code == 200, r.text
    ack = r.json()
    assert ack["run_key"] == key and ack["copied"] > 0
    assert _wait_job(client, ack["job_id"])["status"] == "completed"
    run = _runs(client)[key]
    assert run["status"] == "done"
    assert run["found"] == sum(t["run"]["detections"] for t in results), "the rows say what the cluster found"
    assert run.get("hpcImported") is True
    params = _params(client, key)
    assert params["hpc"]["importedAt"] and len(params["run_ids"]) == 2
    assert params["null"]["drawn"] == 1
    row = _chain_row(client, key)
    assert row["state"] == "imported" and row["open"]["route"].startswith("discovery/")


def test_an_incomplete_result_is_refused_with_what_is_missing(client):
    key = _add(client, "noise_threshold")["run_key"]
    made = _export(client, key, "noise_threshold")
    chain_job.run_task(_spec(made), task=0, out_dir=made["result_dir"])
    n_cache = _q(client, "SELECT COUNT(*) AS n FROM step_artifacts")[0]["n"]
    r = client.post("/api/discovery/chain/import", json={"runKey": key})
    assert r.status_code == 422, r.text
    assert "task 1" in r.text and CH[1] in r.text
    assert _row(client, key)["status"] == "on cluster"
    assert _q(client, "SELECT COUNT(*) AS n FROM step_artifacts")[0]["n"] == n_cache, "nothing was recorded"
    row = _chain_row(client, key)
    assert row["state"] == "partial" and "task 1" in (row["reason"] or "")


def test_jobs_imports_a_chain_job_by_its_spec(client):
    key = _add(client, "noise_threshold")["run_key"]
    made = _export(client, key, "noise_threshold")
    spec = _spec(made)
    for i in range(2):
        chain_job.run_task(spec, task=i, out_dir=made["result_dir"])
    r = client.post("/api/hpc/chain/import", json={"path": made["spec_path"]})
    assert r.status_code == 200, r.text
    assert _wait_job(client, r.json()["job_id"])["status"] == "completed"
    assert _runs(client)[key]["status"] == "done"


def test_an_over_cap_profile_goes_to_the_cluster_and_comes_back_reusable(client, monkeypatch):
    """The whole acceptance loop on the matrix-profile template: over this machine's
    cap the run is added and routed to the cluster (not refused); exported, computed,
    imported; then the same template applied again plans local and runs from the
    imported cache without computing the profile."""
    mp = get_adapter("detection.matrix_profile")
    monkeypatch.setattr(mp, "max_span_samples", 500)
    added = _add(client, "mp_threshold", run=True)
    assert added["route"] == "cluster" and added["started"] is False, added
    key = added["run_key"]
    made = _export(client, key, "mp_threshold")
    spec = _spec(made)
    for i in range(2):
        assert chain_job.run_task(spec, task=i, out_dir=made["result_dir"])["complete"] is True
    real_run = mp.run

    def boom(*a, **k):
        raise AssertionError("the profile was computed here; the imported cache entry was not used")

    monkeypatch.setattr(mp, "run", boom)
    r = client.post("/api/discovery/chain/import", json={"runKey": key})
    assert r.status_code == 200, r.text
    job = _wait_job(client, r.json()["job_id"])
    assert job["status"] == "completed", job
    assert _runs(client)[key]["status"] == "done"
    again = _add(client, "mp_threshold", run=True)
    assert again["route"] != "cluster" and again["started"] is True, again
    assert _wait_job(client, again["job_id"])["status"] == "completed"
    assert _runs(client)[again["run_key"]]["status"] == "done"
    monkeypatch.setattr(mp, "run", real_run)
