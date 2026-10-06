"""
test_webui_seed_estimate.py
===========================
The researcher's request of 2026-10-06, after the first real RQ2 seed search:
a time estimate before a seed search starts, and real progress while it runs,
instead of an indeterminate "searching for the seed" strip.

What it pins:

* **The estimate is work over a rate.** Work is channels × samples × (1 + the
  draws that will be drawn); the rate is a default until a search has been
  measured, then the measured one. A 549 h search reads as hours, a 4 h one as
  minutes, before the button is pressed.
* **A finished preview records its rate**, so the next estimate is measured.
* **Progress counts draws, not channels.** A job over three channels used to
  report 0/3 for the whole of the first channel's 200 draws.

FastAPI lives only in `webui/.venv`, so this file skips under the conda
pytest; run it with:

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_seed_estimate.py
"""

import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui"), os.path.join(PROJECT_ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from test_webui_seed_sources import CH, N, _review_entry, _wait_job, client  # noqa: E402,F401


def _seed_id(client):
    review = _review_entry(client)
    return f"library:{review['recording_id']}:{review['start_idx']}:{review['end_idx']}"


def _estimate(client, channels=(CH[0], CH[1]), t0=0.0, t1=N / 3600.0):
    r = client.get("/api/discovery/seed/estimate", params={"channels": ",".join(channels), "t0": t0, "t1": t1})
    assert r.status_code == 200, r.text
    return r.json()


def test_the_estimate_is_work_over_a_default_rate(client):
    e = _estimate(client)
    assert e["channels"] == 2 and e["samples"] == N
    # the session's null is 2 draws (the fixture's PUT), so the preview and the run each draw 2
    assert e["preview"]["draws"] == 2 and e["run"]["draws"] == 2
    assert e["preview"]["work"] == 2 * N * 3
    assert e["preview"]["seconds"] == pytest.approx(e["preview"]["work"] / e["preview"]["rate"])
    assert e["preview"]["measured"] is False and e["run"]["measured"] is False
    assert e["run"]["seconds"] > 0


def test_the_estimate_scales_with_the_section_and_the_channels(client):
    small = _estimate(client, channels=(CH[0],), t0=0.0, t1=N / 3600.0 / 2)
    big = _estimate(client, channels=(CH[0], CH[1]), t0=0.0, t1=N / 3600.0)
    assert big["run"]["seconds"] == pytest.approx(4 * small["run"]["seconds"])


def test_a_finished_preview_records_its_rate(client):
    body = {"seedId": _seed_id(client), "channels": [CH[0], CH[1]], "t0": 0.0, "t1": N / 3600.0, "k": 20}
    r = client.post("/api/discovery/seed/results", json=body)
    assert r.status_code == 200, r.text
    if not r.json()["ready"]:
        snap = _wait_job(client, r.json()["job_id"])
        assert snap["status"] == "completed", snap.get("error")
    e = _estimate(client)
    assert e["preview"]["measured"] is True
    assert e["preview"]["rate"] > 0


def test_progress_counts_draws_not_channels(client):
    # k=21: the result cache is process-wide and keyed by the query, and the test above ran k=20
    body = {"seedId": _seed_id(client), "channels": [CH[0], CH[1]], "t0": 0.0, "t1": N / 3600.0, "k": 21}
    r = client.post("/api/discovery/seed/results", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["ready"] is False, "nothing ran, so there is no progress to read"
    snap = _wait_job(client, r.json()["job_id"])
    assert snap["status"] == "completed", snap.get("error")
    # 2 channels × (1 matching step + 2 draws) = 6 units of work
    assert snap["progress"]["total"] == 6
