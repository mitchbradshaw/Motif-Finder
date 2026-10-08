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


@pytest.fixture(autouse=True)
def _fresh_result_cache():
    """The bridge keeps finished previews in a process-wide dict keyed by the
    query; a result this file stores (the import test) would otherwise be served
    to another file's test as "already computed"."""
    from server import discovery
    with discovery._results_lock:
        discovery._results.clear()
    yield
    with discovery._results_lock:
        discovery._results.clear()


def _seed_id(client):
    review = _review_entry(client)
    return f"library:{review['recording_id']}:{review['start_idx']}:{review['end_idx']}"


def _runs(client):
    r = client.get("/api/discovery/runs")
    assert r.status_code == 200, r.text
    return r.json()


def _ceiling(client, minutes):
    r = client.put(f"/api/settings/{fanout.CEILING_PAGE}", json={"values": {fanout.CEILING_KEY: minutes}})
    assert r.status_code == 200, r.text


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
    # the row is marked, not deleted: History still lists it and can bring it back
    marked = _q(client, "SELECT removed_at FROM discovery_runs WHERE run_key = ?", (key,))
    assert len(marked) == 1 and marked[0]["removed_at"]
    kept = _q(client, f"SELECT id, superseded_at FROM runs WHERE id IN ({','.join('?' * len(run_ids))})", run_ids)
    assert len(kept) == len(run_ids) and all(k["superseded_at"] is None for k in kept), \
        "removing a run from the session neither deletes nor supersedes its runs"
    hist = client.get("/api/discovery/history").json()
    h = next(x for x in hist if x["runKey"] == key)
    assert h["inSession"] is False and h["status"] == "removed"
    back = client.post(f"/api/discovery/history/{h['id']}/open")
    assert back.status_code == 200, back.text
    assert key in [x["key"] for x in _runs(client)], "opening it from History puts it back"


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


# ── a failed run is retried on its own row ─────────────────────────────────

def test_retrying_a_failed_seed_run_reuses_its_row(client):
    from test_webui_seed_page_repairs import _orphan
    out = _seed_run(client, label="again")
    _orphan(client, out["run_key"])                      # lost in a restart → reads failed
    before = [r["key"] for r in _runs(client) if r["kind"] == "seed"]
    body = {"seedId": _seed_id(client), "channels": [CH[0]], "t0": 0.0, "t1": N / 3600.0, "k": 20, "label": "again"}
    r = client.post("/api/discovery/seed/run", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["run_key"] == out["run_key"], "the same search, run again, is the same row — not a second card"
    assert r.json()["started"] is True
    assert _wait_job(client, r.json()["job_id"])["status"] == "completed"
    after = [r_["key"] for r_ in _runs(client) if r_["kind"] == "seed"]
    assert after == before
    assert next(x for x in _runs(client) if x["key"] == out["run_key"])["status"] == "done"


# ── 2026-10-09: the run reuses a full preview null; a saved template updates ──

def _preview(client, k=20, channels=(CH[0], CH[1])):
    body = {"seedId": _seed_id(client), "channels": list(channels), "t0": 0.0, "t1": N / 3600.0, "k": k}
    r = client.post("/api/discovery/seed/results", json=body)
    assert r.status_code == 200, r.text
    if not r.json()["ready"]:
        assert _wait_job(client, r.json()["job_id"])["status"] == "completed"
    got = client.get("/api/discovery/seed/results", params={"seedId": body["seedId"], "channels": ",".join(channels),
                                                           "t0": 0.0, "t1": N / 3600.0, "k": k}).json()
    assert got["ready"] is True
    return body, got


def test_the_estimate_says_a_full_preview_null_makes_the_run_seconds(client):
    body, got = _preview(client, k=24)
    assert got["null"]["draws"] == 2, "the fixture's null is 2 draws, and the preview drew them all"
    _tiny_ceiling(client)
    e = client.get("/api/discovery/seed/estimate", params={"channels": ",".join(body["channels"]), "t0": 0.0,
                                                           "t1": N / 3600.0, "seedId": body["seedId"], "k": 24}).json()
    assert e["run"]["reusesPreview"] is True
    assert e["run"]["draws"] == 0 and e["run"]["work"] == 2 * N, "the matches alone: channels x samples, no draws"
    # a query with no preview behind it, asked for the preview's null, draws that null first (costed with it)
    e2 = client.get("/api/discovery/seed/estimate", params={"channels": ",".join(body["channels"]), "t0": 0.0,
                                                            "t1": N / 3600.0, "seedId": body["seedId"], "k": 25}).json()
    assert e2["run"]["reusesPreview"] is False and e2["run"]["drawsPreviewFirst"] is True
    assert e2["run"]["previewDraws"] == 2
    # the rigorous run is costed with its paired draws, and is over this ceiling
    e3 = client.get("/api/discovery/seed/estimate", params={"channels": ",".join(body["channels"]), "t0": 0.0,
                                                            "t1": N / 3600.0, "seedId": body["seedId"], "k": 25, "nullMode": "paired"}).json()
    assert e3["run"]["reusesPreview"] is False and e3["run"]["draws"] == 2 and e3["route"] == "cluster"


def test_run_seed_search_reuses_the_previews_null_and_scores_it(client):
    body, got = _preview(client, k=26)
    cut = max(c["d"] for c in got["candidates"])            # keeps every candidate
    # one second (the ceiling is whole seconds): the matches alone are about 0.24 s at the assumed rate
    _ceiling(client, 0.02)
    r = client.post("/api/discovery/seed/run", json={**body, "cut": cut, "label": "reuse"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["started"] is True and out["route"] == "local", out
    assert out["nullFrom"] == "preview"
    assert _wait_job(client, out["job_id"])["status"] == "completed"
    row = _q(client, "SELECT params_json FROM discovery_runs WHERE run_key = ?", (out["run_key"],))[0]
    params = json.loads(row["params_json"])
    assert params["null"]["imported"] is True and params["null"]["source"] == "preview" and params["null"]["draws"] == 2
    ids = params["run_ids"]
    paired = _q(client, f"SELECT COUNT(*) AS n FROM runs WHERE surrogate_of_run_id IN ({','.join('?' * len(ids))})", ids)[0]["n"]
    assert paired == 0, "no surrogate chain runs: the null came from the preview"
    sb = client.get("/api/discovery/scoreboard", params={"runs": out["run_key"], "channels": ",".join(body["channels"]),
                                                         "t0": 0.0, "t1": N / 3600.0}).json()
    total = sb[0]["total"]
    assert total["nullRun"] is True and total["nullDraws"] == 2
    assert isinstance(total["nullExpects"], (int, float))
    assert all(ch["nullRun"] for ch in sb[0]["channels"])


def test_save_as_template_can_update_the_existing_one(client):
    body = {"seedId": _seed_id(client), "name": "seed_tpl_update", "k": 20, "cut": 2.0}
    assert client.post("/api/discovery/seed/template", json=body).status_code == 200
    again = client.post("/api/discovery/seed/template", json={**body, "cut": 3.5})
    assert again.status_code == 409, "without asking, a taken name is still refused"
    r = client.post("/api/discovery/seed/template", json={**body, "cut": 3.5, "replace": True})
    assert r.status_code == 200, r.text
    assert r.json()["updated"] is True
    rows = _q(client, "SELECT steps_json FROM templates WHERE name = ?", ("seed_tpl_update",))
    assert len(rows) == 1
    step = json.loads(rows[0]["steps_json"])[0]
    assert step["params"]["max_distance"] == 3.5


# ── 2026-10-09: the null is the researcher's choice on the run ─────────────

def test_a_run_with_the_null_off_is_a_real_run_that_review_can_take(client):
    body = {"seedId": _seed_id(client), "channels": [CH[0]], "t0": 0.0, "t1": N / 3600.0, "k": 20,
            "label": "nulloff", "nullMode": "off"}
    _ceiling(client, 0.02)                                 # one second: a paired run is over it; this one has no draws
    r = client.post("/api/discovery/seed/run", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["started"] is True and out["nullFrom"] == "off", out
    assert _wait_job(client, out["job_id"])["status"] == "completed"
    params = json.loads(_q(client, "SELECT params_json FROM discovery_runs WHERE run_key = ?", (out["run_key"],))[0]["params_json"])
    assert params["null"]["paired"] is False and params["null"].get("draws", 0) == 0 and params["null"]["source"] == "off"
    ids = params["run_ids"]
    assert _q(client, f"SELECT COUNT(*) AS n FROM runs WHERE surrogate_of_run_id IN ({','.join('?' * len(ids))})", ids)[0]["n"] == 0
    sb = client.get("/api/discovery/scoreboard", params={"runs": out["run_key"], "channels": CH[0], "t0": 0.0, "t1": N / 3600.0}).json()
    assert sb[0]["total"]["nullRun"] is False
    sent = client.post(f"/api/discovery/runs/{out['run_key']}/review", json={})
    assert sent.status_code == 200, sent.text
    assert sent.json()["total"] >= 1, "the run has detections Review can take"


def test_a_capped_preview_null_is_reused_when_the_run_asks_for_it(client, monkeypatch):
    from server import discovery
    # a 10-draw null over a budget of 1,000 samples: the preview draws the floor of 5
    r = client.put("/api/discovery/session", json={"null": {"method": "phase randomisation", "n": 10}})
    assert r.status_code == 200, r.text
    monkeypatch.setattr(discovery, "NULL_SAMPLE_BUDGET", 1000)
    body, got = _preview(client, k=27)
    assert got["null"]["draws"] == discovery.NULL_MIN_DRAWS < 10
    e = client.get("/api/discovery/seed/estimate", params={"channels": ",".join(body["channels"]), "t0": 0.0, "t1": N / 3600.0,
                                                           "seedId": body["seedId"], "k": 27, "nullMode": "preview"}).json()
    assert e["run"]["reusesPreview"] is True and e["run"]["previewDraws"] == discovery.NULL_MIN_DRAWS
    e2 = client.get("/api/discovery/seed/estimate", params={"channels": ",".join(body["channels"]), "t0": 0.0, "t1": N / 3600.0,
                                                            "seedId": body["seedId"], "k": 27, "nullMode": "paired"}).json()
    assert e2["run"]["reusesPreview"] is False and e2["run"]["draws"] == 10
    r = client.post("/api/discovery/seed/run", json={**body, "label": "capped", "nullMode": "preview"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["nullFrom"] == "preview" and out["started"] is True
    assert _wait_job(client, out["job_id"])["status"] == "completed"
    params = json.loads(_q(client, "SELECT params_json FROM discovery_runs WHERE run_key = ?", (out["run_key"],))[0]["params_json"])
    assert params["null"]["draws"] == discovery.NULL_MIN_DRAWS and params["null"]["source"] == "preview"
