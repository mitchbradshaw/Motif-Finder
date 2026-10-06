"""
test_webui_seed_hpc_route.py
============================
The researcher's report of 2026-10-06 on RQ2's seed search:

* **The preview piled up.** A 4 h × 3-channel preview read "6 h left": the
  live server held twenty copies of the same search, started seconds apart,
  each sharing the CPU with the others. One copy runs in under a minute. A
  POST for a query whose search is already running JOINS that job.
* **A run can be removed from the session.** `DELETE /api/discovery/runs/<key>`
  takes the row off the session; the runs and their detections stay, and
  History can bring it back. The human reference cannot be removed.
* **Over the ceiling, a seed search is a SLURM job.** Its cost is the measured
  rate's, the ceiling is Settings › Compute & HPC's (10 minutes by default for
  a seed search), `/api/discovery/seed/run` does not start it, and
  `/api/discovery/seed/slurm` writes the spec and the script. The result the
  cluster writes is imported through `/api/discovery/seed/import`: the page's
  histogram and cut come from it, and the run row is finished locally with the
  real search alone (seconds), carrying the imported null.

FastAPI lives only in `webui/.venv`, so this file skips under the conda
pytest; run it with:

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_seed_hpc_route.py
"""

import json
import os
import sys
import threading

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui"), os.path.join(PROJECT_ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from Working.discovery import fanout, seed_job  # noqa: E402
from test_webui_seed_page_repairs import _seed_run  # noqa: E402,F401
from test_webui_seed_sources import CH, M, N, _q, _review_entry, _wait_job, client  # noqa: E402,F401


def _seed_id(client):
    review = _review_entry(client)
    return f"library:{review['recording_id']}:{review['start_idx']}:{review['end_idx']}"


def _runs(client):
    r = client.get("/api/discovery/runs")
    assert r.status_code == 200, r.text
    return r.json()


def _tiny_ceiling(client):
    """A ceiling no search fits under: a tenth of a second."""
    r = client.put(f"/api/settings/{fanout.CEILING_PAGE}", json={"values": {fanout.CEILING_KEY: 0.001}})
    assert r.status_code == 200, r.text


# ── the pile-up ────────────────────────────────────────────────────────────

def test_a_second_post_while_the_search_runs_joins_it(client, monkeypatch):
    from server import discovery
    gate = threading.Event()
    real = discovery._seed_search

    def slow(*a, **k):
        gate.wait(30)
        return real(*a, **k)

    monkeypatch.setattr(discovery, "_seed_search", slow)
    body = {"seedId": _seed_id(client), "channels": [CH[0], CH[1]], "t0": 0.0, "t1": N / 3600.0, "k": 23}
    first = client.post("/api/discovery/seed/results", json=body).json()
    second = client.post("/api/discovery/seed/results", json=body).json()
    assert first["ready"] is False and second["ready"] is False
    assert second["job_id"] == first["job_id"], "the second POST must join the running search, not start another"
    assert second.get("joined") is True
    live = [j for j in client.get("/api/jobs").json() if (j.get("meta") or {}).get("key") == first["key"]]
    assert len(live) == 1
    gate.set()
    assert _wait_job(client, first["job_id"])["status"] == "completed"


# ── removing a run from the session ────────────────────────────────────────

def test_remove_takes_the_run_off_the_session_and_keeps_its_runs(client):
    out = _seed_run(client, label="to_remove")
    key = out["run_key"]
    row = _q(client, "SELECT params_json FROM discovery_runs WHERE run_key = ?", (key,))[0]
    run_ids = json.loads(row["params_json"])["run_ids"]
    assert run_ids, "the run wrote runs"
    r = client.delete(f"/api/discovery/runs/{key}")
    assert r.status_code == 200, r.text
    assert r.json()["removed"] == key
    assert key not in [x["key"] for x in _runs(client)]
    assert not _q(client, "SELECT 1 FROM discovery_runs WHERE run_key = ?", (key,))
    kept = _q(client, f"SELECT id, superseded_at FROM runs WHERE id IN ({','.join('?' * len(run_ids))})", run_ids)
    assert len(kept) == len(run_ids) and all(k["superseded_at"] is None for k in kept), \
        "removing a run from the session neither deletes nor supersedes its runs"
    # History still lists it, so it can be brought back
    hist = client.get("/api/discovery/history").json()
    rows = hist if isinstance(hist, list) else hist.get("runs") or hist.get("history") or []
    assert any(h.get("run_key") == key or h.get("key") == key or h.get("label") == "to_remove" for h in rows)


def test_the_human_reference_cannot_be_removed(client):
    ref = next(r for r in _runs(client) if r["kind"] == "reference")
    r = client.delete(f"/api/discovery/runs/{ref['key']}")
    assert r.status_code in (409, 422), r.text


# ── over the ceiling: the cluster ──────────────────────────────────────────

def test_the_estimate_knows_the_ceiling_and_the_route(client):
    r = client.get("/api/discovery/seed/estimate", params={"channels": ",".join(CH[:2]), "t0": 0.0, "t1": N / 3600.0})
    assert r.status_code == 200, r.text
    e = r.json()
    assert e["ceilingS"] == 600, "a seed search's default ceiling is ten minutes"
    assert e["route"] == "local"
    _tiny_ceiling(client)
    e = client.get("/api/discovery/seed/estimate", params={"channels": ",".join(CH[:2]), "t0": 0.0, "t1": N / 3600.0}).json()
    assert e["route"] == "cluster" and e["ceilingS"] < 1


def test_a_seed_run_over_the_ceiling_is_not_started_locally(client):
    _tiny_ceiling(client)
    body = {"seedId": _seed_id(client), "channels": [CH[0]], "t0": 0.0, "t1": N / 3600.0, "k": 20}
    r = client.post("/api/discovery/seed/run", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["route"] == "cluster" and out["started"] is False and out["job_id"] is None
    row = next(x for x in _runs(client) if x["key"] == out["run_key"])
    assert row["status"] == "new"


def test_create_slurm_writes_the_spec_and_the_script(client):
    _tiny_ceiling(client)
    body = {"seedId": _seed_id(client), "channels": [CH[0], CH[1]], "t0": 0.0, "t1": N / 3600.0, "k": 20}
    r = client.post("/api/discovery/seed/slurm", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert "#SBATCH" in out["script"] and "Working.discovery.seed_job" in out["script"]
    assert os.path.isfile(out["spec_path"]) and os.path.isfile(out["script_path"])
    with open(out["spec_path"], encoding="utf-8") as f:
        spec = json.load(f)
    assert len(spec["exemplar"]) == M
    assert [c["name"] for c in spec["channels"]] == [CH[0], CH[1]]
    assert spec["null"]["draws"] == 2, "the session's null travels with the job"
    assert out["result_path"].endswith(".result.json")
    row = next(x for x in _runs(client) if x["key"] == out["run_key"])
    assert row["status"] == "on cluster"


def test_importing_the_result_fills_the_preview_and_finishes_the_run(client):
    _tiny_ceiling(client)
    body = {"seedId": _seed_id(client), "channels": [CH[0], CH[1]], "t0": 0.0, "t1": N / 3600.0, "k": 20}
    made = client.post("/api/discovery/seed/slurm", json=body).json()
    with open(made["spec_path"], encoding="utf-8") as f:
        spec = json.load(f)
    # what the cluster would do, done here
    result = seed_job.run_spec(spec, loader=seed_job.db_loader(client.app.state.rt.db_path))
    r = client.post("/api/discovery/seed/import", json=result)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["run_key"] == made["run_key"] and out["nullDraws"] == 2
    assert out["job_id"], "the real search runs locally in seconds; only the null came from the cluster"
    assert _wait_job(client, out["job_id"])["status"] == "completed"
    row = next(x for x in _runs(client) if x["key"] == made["run_key"])
    assert row["status"] == "done"
    # the page's own query is served from the import
    got = client.get("/api/discovery/seed/results", params={
        "seedId": body["seedId"], "channels": ",".join(body["channels"]), "t0": 0.0, "t1": N / 3600.0, "k": 20}).json()
    assert got["ready"] is True and got.get("imported") is True
    assert got["null"]["draws"] == 2 and len(got["candidates"]) > 0
    assert all("trace" in c for c in got["candidates"]), "the match cards still draw the match's own samples"


def test_a_result_for_another_scope_is_refused(client):
    body = {"seedId": _seed_id(client), "channels": [CH[0]], "t0": 0.0, "t1": N / 3600.0, "k": 20}
    made = client.post("/api/discovery/seed/slurm", json=body).json()
    with open(made["spec_path"], encoding="utf-8") as f:
        spec = json.load(f)
    # a result computed over another recording's channels is not this session's
    result = seed_job.run_spec(spec, loader=seed_job.db_loader(client.app.state.rt.db_path))
    result["sourceFile"] = "other.mat"
    r = client.post("/api/discovery/seed/import", json=result)
    assert r.status_code == 422, r.text
    assert "other.mat" in r.text
