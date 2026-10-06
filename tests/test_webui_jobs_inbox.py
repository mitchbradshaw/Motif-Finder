"""
test_webui_jobs_inbox.py
========================
fixup-AJ, the bridge side of Jobs as far as RQ1 needs it:

* ``GET /api/hpc/exported`` — every job directory the site wrote for the
  cluster (fixup-AI's B.2 CNN and full-pool Ward), with its recipe hash, when
  it was written, what to copy and its state: *written · results copied back ·
  results imported (the run, a link) · import refused (why)*;
* ``POST /api/hpc/inbox/import`` — the Manifest inbox: a returned job
  directory is imported as a local job of kind ``import`` that calls
  ``Working.training.hpc_import.import_results`` — the CLI's function, one
  implementation with two callers — and a refusal is the job's error, kept, so
  the exported row says why;
* ``GET /api/hpc/inbox`` — the import attempts, newest first;
* ``GET /api/jobs`` — the bridge's real local jobs carry what the page shows:
  kind, stage, progress, started, and a failure's traceback.

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_jobs_inbox.py -q
"""

import json
import os
import sys
import time

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui"), os.path.join(PROJECT_ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from fastapi.testclient import TestClient  # noqa: E402

from Working.database.schema import init_db  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402
from test_hpc_exported_jobs import CNN_KIND, make_cnn_job, make_ward_job  # noqa: E402


def _wait(c, url, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = c.get(url).json()
        if s["status"] in ("completed", "failed", "cancelled"):
            return s
        time.sleep(0.1)
    raise AssertionError(f"{url} did not finish")


@pytest.fixture()
def app(tmp_path):
    db_dir = tmp_path / "db"; db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path, units) "
                 "VALUES ('a.mat', 0, 1.0, 10, 0, 'x.npy', 'V')")
    conn.commit()
    conn.close()
    dist = tmp_path / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    rt = Runtime(mode="sandbox", stamp="20261007-aj", db_source=str(db), runtime_root=str(tmp_path / "runtime"),
                 client_dist=str(dist))
    rt.setup()
    try:
        from server.training_routes import _hpc_dir
        with TestClient(create_app(rt)) as c:
            yield c, rt, _hpc_dir(rt)
    finally:
        rt.restore()


def _rows(c):
    r = c.get("/api/hpc/exported")
    assert r.status_code == 200, r.text
    return {x["name"]: x for x in r.json()["jobs"]}


def test_the_written_scripts_are_listed_with_what_to_copy(app):
    c, _rt, hpc = app
    make_cnn_job(hpc)
    make_ward_job(hpc)
    make_cnn_job(os.path.join(hpc, "smoke"), "b2cnn_fusion_smoke_y", smoke={"n_train": 10, "n_predict": 4})
    rows = _rows(c)
    assert set(rows) == {"b2cnn_fusion_x", "ward_full_x", "b2cnn_fusion_smoke_y"}
    cnn = rows["b2cnn_fusion_x"]
    assert cnn["state"] == "written" and cnn["recipe_hash"] and cnn["written_at"]
    assert {x["what"] for x in cnn["copy"]} == {"job directory", "channel array"} and cnn["total_bytes"] > 0
    assert rows["ward_full_x"]["state"] == "written" and rows["ward_full_x"]["kind_label"]
    assert rows["b2cnn_fusion_smoke_y"]["smoke"] is True


def test_a_directory_from_a_different_recipe_is_refused_with_its_reason_and_the_row_says_why(app):
    c, _rt, hpc = app
    d, _recipe, h = make_cnn_job(hpc, out=True)
    # the out/ copied back is another job's: its done.json was made from a different recipe
    with open(os.path.join(d, "out", "done.json"), "w", encoding="utf-8") as fh:
        json.dump({"recipe_hash": "deadbeef", "status": "complete"}, fh)
    assert _rows(c)["b2cnn_fusion_x"]["state"] == "returned"
    r = c.post("/api/hpc/inbox/import", json={"path": d})
    assert r.status_code == 200, r.text
    j = _wait(c, f"/api/jobs/{r.json()['job_id']}")
    assert j["kind"] == "import" and j["status"] == "failed"
    assert j["error"]["type"] == "ImportRefused" and "deadbeef" in j["error"]["message"]
    row = _rows(c)["b2cnn_fusion_x"]
    assert row["state"] == "refused" and "deadbeef" in row["reason"]
    att = c.get("/api/hpc/inbox").json()["attempts"]
    assert att and att[0]["outcome"] == "refused" and os.path.normcase(att[0]["job_dir"]) == os.path.normcase(d)
    # nothing was recorded: no run carries the job's recipe hash
    con = init_db(_rt.db_path)
    try:
        assert con.execute("SELECT COUNT(*) FROM configs WHERE config_hash = ?", (h,)).fetchone()[0] == 0
    finally:
        con.close()


def test_the_inbox_imports_through_the_clis_function_and_the_row_opens_the_run(app, monkeypatch):
    c, rt, hpc = app
    d, recipe, h = make_cnn_job(hpc, out=True)
    from Working.database import runs as R
    from Working.training import hpc_import
    calls = []

    def fake(conn, job_dir, *, root, tree_root=None, where=None):
        calls.append({"job_dir": job_dir, "root": root, "tree_root": tree_root})
        cid, _h = R.get_or_create_config(conn, recipe)
        run = R.insert_run(conn, cid, 1, 0, 10, status="completed", name="B.2 CNN fusion · test")
        conn.commit()
        return {"kind": CNN_KIND, "run_id": run, "created": True, "config_hash": h, "results_path": "x",
                "name": "B.2 CNN fusion · test", "message": f"imported as run {run}"}

    monkeypatch.setattr(hpc_import, "import_results", fake)
    r = c.post("/api/hpc/inbox/import", json={"path": d})
    assert r.status_code == 200, r.text
    j = _wait(c, f"/api/jobs/{r.json()['job_id']}")
    assert j["status"] == "completed", j
    assert len(calls) == 1 and os.path.normcase(calls[0]["job_dir"]) == os.path.normcase(d)
    assert calls[0]["root"].startswith(rt.dir)                     # the sandbox's training root, never the real one
    row = _rows(c)["b2cnn_fusion_x"]
    assert row["state"] == "imported" and row["imported"]["run_id"] > 0
    assert row["open"]["route"] == f"models/results/b2/{row['imported']['run_id']}"
    att = c.get("/api/hpc/inbox").json()["attempts"]
    assert att[0]["outcome"] == "imported" and "imported as run" in att[0]["message"]


def test_an_empty_path_is_refused_before_any_job(app):
    c, _rt, _hpc = app
    assert c.post("/api/hpc/inbox/import", json={"path": "  "}).status_code == 422


def test_local_jobs_carry_kind_stage_progress_and_a_failures_traceback(app):
    c, _rt, _hpc = app
    manager = c.app.state.manager

    def boom(job):
        job.progress(1, 4, "reading the windows")
        raise RuntimeError("the window set is gone")

    jid = manager.start_job("training", boom, meta={"stage": "window set", "where": "local"}).id
    j = _wait(c, f"/api/jobs/{jid}")
    listed = {x["job_id"]: x for x in c.get("/api/jobs").json()}
    row = listed[jid]
    assert row["kind"] == "training" and row["meta"]["stage"] == "window set" and row["status"] == "failed"
    assert row["progress"]["message"] == "reading the windows" and row["started_at"]
    assert "RuntimeError" in row["error"]["traceback"] and j["error"]["message"].endswith("the window set is gone")
