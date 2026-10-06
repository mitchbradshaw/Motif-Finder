"""
test_webui_seed_page_repairs.py
===============================
Three defects the researcher hit on Discovery › Seed search on 2026-10-05.

What it pins:

* **A run whose job died with the server is failed, not running for ever.**
  Two seed runs read *running* for a day: their sweep jobs were lost when the
  bridge restarted, and nothing ever wrote the `discovery_runs` row again. The
  Seed page then refused *Run seed search* ("already run with this seed and
  cut") and the server would have handed the dead run back as "the same run".
* **Save as template writes a template.** The button wrote to the client's
  in-memory store only: the name was "taken" after the first press and
  Library › Templates never showed it.
* **The Library calls a seed-search template a seed search**, which is the
  kind its own filter offers.

FastAPI lives only in `webui/.venv`, so this file skips under the conda
pytest; run it with:

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_seed_page_repairs.py
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

from test_webui_seed_sources import CH, N, _q, _review_entry, _seed_run, _x, client  # noqa: E402,F401


def _orphan(client, run_key):
    """Make a finished run look like one the server lost mid-flight: still
    *running*, pointing at a job no live manager holds, with no runs recorded."""
    row = _q(client, "SELECT params_json FROM discovery_runs WHERE run_key = ?", (run_key,))[0]
    params = json.loads(row["params_json"])
    params.pop("run_ids", None)
    _x(client, "UPDATE discovery_runs SET status = 'running', job_id = 987654, run_group_id = NULL, "
               "params_json = ? WHERE run_key = ?", (json.dumps(params), run_key))


def _run_row(client, run_key):
    return next(r for r in client.get("/api/discovery/runs").json() if r["key"] == run_key)


# ── 1. a run the server lost is failed ─────────────────────────────────────

def test_a_run_whose_job_died_with_the_server_reads_failed(client):
    a = _seed_run(client, cut=5.0, label="seed x")
    _orphan(client, a["run_key"])
    row = _run_row(client, a["run_key"])
    assert row["status"] == "failed", "a run whose job no longer exists read 'running' for a day"
    assert "restart" in row["error"]


def test_a_lost_run_is_not_handed_back_as_the_same_run(client):
    a = _seed_run(client, cut=5.0, label="seed x")
    _orphan(client, a["run_key"])
    b = _seed_run(client, cut=5.0, label="seed x")
    assert b["reused"] is False
    assert b["run_key"] != a["run_key"]
    assert _run_row(client, b["run_key"])["status"] == "done"


def test_a_live_run_is_left_alone(client):
    a = _seed_run(client, cut=5.0, label="seed x")
    assert _run_row(client, a["run_key"])["status"] == "done"


# ── 2. Save as template writes a template ──────────────────────────────────

def _seed_id(client):
    review = _review_entry(client)
    return f"library:{review['recording_id']}:{review['start_idx']}:{review['end_idx']}"


def _save(client, name="my_seed_search", **extra):
    return client.post("/api/discovery/seed/template", json={"seedId": _seed_id(client), "name": name, **extra})


def test_save_as_template_writes_a_templates_row(client):
    r = _save(client, cut=5.0)
    assert r.status_code == 200, r.text
    rows = _q(client, "SELECT steps_json FROM templates WHERE name = 'my_seed_search'")
    assert len(rows) == 1
    step = json.loads(rows[0]["steps_json"])[-1]
    assert step["algorithm"] == "seed_matches"
    assert step["params"]["max_distance"] == 5.0
    assert step["side_inputs"]["exemplar"]["source_kind"] == "library_exemplar"


def test_a_taken_template_name_is_refused(client):
    assert _save(client).status_code == 200
    r = _save(client)
    assert r.status_code == 409, r.text
    assert len(_q(client, "SELECT id FROM templates WHERE name = 'my_seed_search'")) == 1


def test_the_library_lists_it_as_a_seed_search(client):
    assert _save(client).status_code == 200
    rows = client.get("/api/library/templates").json()
    mine = next(t for t in rows if t["name"] == "my_seed_search")
    assert mine["kind"] == "seed search"


def test_discovery_offers_it_as_a_seed_template(client):
    assert _save(client).status_code == 200
    rows = client.get("/api/discovery/templates").json()
    assert next(t for t in rows if t["name"] == "my_seed_search")["kind"] == "seed"
