"""
test_webui_jobs_board.py
========================
fixup-jobs: the Jobs page is one real board — what runs here, what waits on
the cluster, what waits in review — with no fixture half left. The bridge side
this file pins:

* ``GET /api/hpc/cluster`` — every job the site wrote for the cluster, whatever
  wrote it, in ONE list: the job directories (fixup-AI's CNN and Ward, read by
  ``/api/hpc/exported``), Discovery's seed searches sent to the cluster (their
  run rows, ``params.hpc``), and the flat recipe + script pairs Discovery's
  chain export and Models' paired-training export write. Each row says what it
  is, which workspace it belongs to, when it was written, its state —
  *written · partial (a checkpoint is back) · returned · importing · imported ·
  refused · failed* — and how its results come back (the Manifest inbox, the
  seed import, or not through the site at all, with the reason). ``counts``
  summarise the states for the page's chips.
* ``POST /api/hpc/seed/import`` — a seed job's result file, imported from Jobs
  by path through the Seed page's own import function (one implementation, two
  callers); a missing file is 404, the held-out recording 423, a file that is
  not JSON 422.

FastAPI lives only in ``webui/.venv``:

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_jobs_board.py -q
"""

import json
import os
import sys

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
from test_hpc_exported_jobs import CNN_KIND, make_cnn_job  # noqa: E402

NOW = "2026-10-09T09:00:00"


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
    rt = Runtime(mode="sandbox", stamp="20261009-jobs", db_source=str(db), runtime_root=str(tmp_path / "runtime"),
                 client_dist=str(dist))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            yield c, rt
    finally:
        rt.restore()


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _seed_out_dir(rt):
    """Where `/api/discovery/seed/slurm` writes in a sandbox (`_hpc_out_dir`)."""
    return os.path.join(rt.dir, "hpc")


def _training_dir(rt):
    from server.training_routes import _hpc_dir
    return _hpc_dir(rt)


def _seed_hpc_run(rt, *, base="drop_2ch_0-100", channels=2, created_at="2026-10-08T10:00:00", imported=False,
                  label="drop exemplar"):
    """A Discovery seed search sent to the cluster: the spec and script
    `seed_job.write_job` leaves, and the run row `/api/discovery/seed/slurm`
    marks *on cluster* with `params.hpc` pointing at them."""
    out = _seed_out_dir(rt)
    spec_path = os.path.join(out, base + ".spec.json")
    script_path = os.path.join(out, base + ".sh")
    result_path = os.path.join(out, base + ".result.json")
    spec = {"version": 1, "seedId": "library:1:0:10", "span": [0, 100], "k": 20,
            "channels": [{"name": f"CH{i}", "source_file": "a.mat", "channel": i, "fs": 1.0,
                          "npy_path": f"DATA/derived/channels/a/CH{i}.npy"} for i in range(channels)],
            "null": {"method": "block", "draws": 20, "seed": 0}}
    _write(spec_path, json.dumps(spec))
    _write(script_path, "#!/bin/bash\n#SBATCH --job-name=" + base + "\n")
    hpc = {"specPath": spec_path, "scriptPath": script_path, "resultPath": result_path,
           "sbatch": f"sbatch {script_path}", "createdAt": created_at, "specHash": "abcd1234", "draws": 20,
           "estimateS": 900.0,
           "dependencies": {"code": ["Working/discovery/seed_job.py"], "inputs": [spec_path], "outputs": [result_path]}}
    if imported:
        hpc["importedAt"] = NOW
    conn = init_db(rt.db_path)
    try:
        sid = conn.execute("INSERT INTO discovery_sessions (name, source_file, channels_json, created_at, updated_at) "
                           "VALUES ('s', 'a.mat', '[\"CH0\",\"CH1\"]', ?, ?)", (NOW, NOW)).lastrowid
        conn.execute("INSERT INTO discovery_runs (session_id, run_key, kind, label, params_json, status, created_at, "
                     "updated_at) VALUES (?, ?, 'seed', ?, ?, ?, ?, ?)",
                     (sid, base, label, json.dumps({"seedId": "library:1:0:10", "route": "cluster", "hpc": hpc}),
                      "done" if imported else "on cluster", created_at, created_at))
        conn.commit()
    finally:
        conn.close()
    return {"base": base, "spec": spec_path, "script": script_path, "result": result_path}


def _seed_result(path, *, complete, channels_done, spec_hash="abcd1234"):
    _write(path, json.dumps({"version": 1, "specHash": spec_hash, "seedId": "library:1:0:10", "sourceFile": "a.mat",
                             "span": [0, 100], "k": 20, "complete": complete,
                             "perChannel": [{"name": f"CH{i}", "candidates": [], "null": {"draws": 20}}
                                            for i in range(channels_done)],
                             "finishedAt": NOW if complete else None}))


def _paired_training_script(rt, base="paired_ws_k3_1234abcd"):
    d = _training_dir(rt)
    _write(os.path.join(d, base + ".json"), json.dumps({"window_set": "ws", "arms": {"A": {}, "B": {"k": 3}}}))
    _write(os.path.join(d, base + ".sh"), "#!/bin/bash\n#SBATCH --job-name=" + base + "\n")
    return base


def _chain_script(rt, base="sharkfin_3ch_0-100"):
    d = _seed_out_dir(rt)
    _write(os.path.join(d, base + ".json"), json.dumps({"steps": [{"algorithm": "bandpass"}],
                                                        "fan_out": {"targets": [{"recording_id": 1}]}}))
    _write(os.path.join(d, base + ".sh"), "#!/bin/bash\n#SBATCH --array=0-0\n")
    return base


def _board(c):
    r = c.get("/api/hpc/cluster")
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body.get("jobs"), list) and isinstance(body.get("counts"), dict), body
    return body


def _by_name(c):
    return {row["name"]: row for row in _board(c)["jobs"]}


# ── one list, three writers ────────────────────────────────────────────────

def test_the_cluster_list_unifies_job_dirs_seed_searches_and_flat_scripts(app):
    c, rt = app
    make_cnn_job(_training_dir(rt), "b2cnn_fusion_x")
    seed = _seed_hpc_run(rt)
    paired = _paired_training_script(rt)
    chain = _chain_script(rt)

    rows = _by_name(c)
    assert {"b2cnn_fusion_x", seed["base"], paired, chain} <= set(rows), sorted(rows)

    cnn = rows["b2cnn_fusion_x"]
    assert cnn["source"] == "job_dir" and cnn["kind"] == CNN_KIND and cnn["workspace"] == "Models"
    assert cnn["state"] == "written" and cnn["import_how"] == "inbox" and cnn["import_path"] == cnn["job_dir"]
    assert cnn["copy"] and cnn["sbatch_command"], cnn        # the exported row's own fields travel with it

    s = rows[seed["base"]]
    assert s["source"] == "seed" and s["workspace"] == "Discovery" and s["kind"] == "seed_search"
    assert s["state"] == "written" and s["import_how"] == "seed" and s["import_path"] == seed["result"]
    assert s["label"] == "drop exemplar" and s["run_key"] == seed["base"]
    assert s["written_at"] == "2026-10-08T10:00:00" and s["recipe_hash"] == "abcd1234"
    assert s["sbatch_command"].startswith("sbatch ") and s["scripts"][0]["name"] == seed["base"] + ".sh"
    assert any(x["what"] == "spec" for x in s["copy"]), s["copy"]
    assert s["result_path"] == seed["result"]

    p = rows[paired]
    assert p["source"] == "script" and p["kind"] == "paired_training" and p["workspace"] == "Models"
    assert p["state"] == "written" and p["import_how"] is None and p["import_note"]
    assert p["written_at"] and p["sbatch_command"].startswith("sbatch ")

    ch = rows[chain]
    assert ch["source"] == "script" and ch["kind"] == "detection_chain" and ch["workspace"] == "Discovery"
    assert ch["state"] == "written" and ch["import_how"] is None and ch["import_note"]

    # the seed job's own .sh is not listed a second time as a flat script
    assert sum(1 for r in _board(c)["jobs"] if r["name"] == seed["base"]) == 1
    # every row names what it is and where it belongs
    for r in _board(c)["jobs"]:
        assert r["kind_label"] and r["workspace"] in ("Models", "Analyse", "Discovery"), r


def test_the_list_is_newest_first_and_the_exported_route_is_unchanged(app):
    c, rt = app
    make_cnn_job(_training_dir(rt), "older", created_at="2026-10-01T10:00:00")
    _seed_hpc_run(rt, base="newer_2ch_0-100", created_at="2026-10-09T08:00:00")
    names = [r["name"] for r in _board(c)["jobs"]]
    assert names.index("newer_2ch_0-100") < names.index("older")
    exported = c.get("/api/hpc/exported").json()["jobs"]
    assert [r["name"] for r in exported] == ["older"]        # the job-dir route lists job directories only


# ── the seed search's states, read from disk and the run row ──────────────

def test_a_seed_search_reads_written_partial_returned_imported(app):
    c, rt = app
    seed = _seed_hpc_run(rt, channels=2)
    assert _by_name(c)[seed["base"]]["state"] == "written"

    _seed_result(seed["result"], complete=False, channels_done=1)
    row = _by_name(c)[seed["base"]]
    assert row["state"] == "partial", row
    assert row["progress"] == {"channels_done": 1, "channels": 2}
    assert row["returned"] and row["returned"]["status"] == "partial"

    _seed_result(seed["result"], complete=True, channels_done=2)
    row = _by_name(c)[seed["base"]]
    assert row["state"] == "returned" and row["returned"]["status"] == "complete"
    assert row["returned"]["finished_at"] == NOW and row["imported"] is None

    conn = init_db(rt.db_path)
    try:
        p = json.loads(conn.execute("SELECT params_json FROM discovery_runs WHERE run_key = ?",
                                    (seed["base"],)).fetchone()[0])
        p["hpc"]["importedAt"] = NOW
        conn.execute("UPDATE discovery_runs SET params_json = ?, status = 'done' WHERE run_key = ?",
                     (json.dumps(p), seed["base"]))
        conn.commit()
    finally:
        conn.close()
    row = _by_name(c)[seed["base"]]
    assert row["state"] == "imported" and row["imported"] and row["open"]["route"].startswith("discovery/")


def test_a_result_file_for_another_spec_is_not_this_jobs_result(app):
    c, rt = app
    seed = _seed_hpc_run(rt)
    _seed_result(seed["result"], complete=True, channels_done=2, spec_hash="ffff0000")
    row = _by_name(c)[seed["base"]]
    assert row["state"] == "written", row       # another spec's file: nothing came back for THIS job
    assert "ffff0000" in (row["reason"] or ""), row


def test_counts_summarise_the_states(app):
    c, rt = app
    make_cnn_job(_training_dir(rt), "cnn_written")
    make_cnn_job(_training_dir(rt), "cnn_returned", out=True)
    _seed_hpc_run(rt, base="seed_imported_2ch_0-100", imported=True)
    _paired_training_script(rt)
    counts = _board(c)["counts"]
    assert counts["written"] == 2 and counts["returned"] == 1 and counts["imported"] == 1
    assert counts["to_import"] == 1                 # returned and importable through the site
    assert counts["waiting"] == 2                   # written, no result back yet


# ── importing a seed result from Jobs ─────────────────────────────────────

def test_a_seed_result_imported_from_jobs_goes_through_the_seed_pages_import(app, monkeypatch):
    from server import discovery
    c, rt = app
    seed = _seed_hpc_run(rt)
    _seed_result(seed["result"], complete=True, channels_done=2)
    seen = {}

    def fake(request, result):
        seen["result"] = result
        return {"run_key": seed["base"], "job_id": 7, "note": "imported by the fake"}

    monkeypatch.setattr(discovery, "import_seed_result_dict", fake)
    r = c.post("/api/hpc/seed/import", json={"path": seed["result"]})
    assert r.status_code == 200, r.text
    assert r.json()["run_key"] == seed["base"] and r.json()["job_id"] == 7
    assert seen["result"]["specHash"] == "abcd1234" and seen["result"]["complete"] is True


def test_the_seed_import_refuses_what_it_cannot_read(app, monkeypatch):
    from server import discovery
    from server.runtime import HELD_OUT_FILE
    c, rt = app
    monkeypatch.setattr(discovery, "import_seed_result_dict", lambda request, result: {"ok": True})
    missing = os.path.join(_seed_out_dir(rt), "no_such.result.json")
    assert c.post("/api/hpc/seed/import", json={"path": missing}).status_code == 404
    assert c.post("/api/hpc/seed/import", json={"path": f"x/{HELD_OUT_FILE}.result.json"}).status_code == 423
    bad = os.path.join(_seed_out_dir(rt), "bad.result.json")
    _write(bad, "not json")
    assert c.post("/api/hpc/seed/import", json={"path": bad}).status_code == 422
    assert c.post("/api/hpc/seed/import", json={"path": ""}).status_code == 422
