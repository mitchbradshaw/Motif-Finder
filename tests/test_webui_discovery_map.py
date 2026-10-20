"""
test_webui_discovery_map.py
===========================
map-overview-cache (2026-10-20), the route half: `GET /api/discovery/map` (Discovery › Map's overview) took 17–21 s
on every read of the real database (305 Discovery runs, 8 sessions), uncached, inside the request — the first
result of the talk and the page examiners click. Now:

* **a read never computes.** No stored overview: ``pending: true`` at once, and exactly one compute scheduled;
  a second read before it lands schedules nothing.
* after the compute a read returns the overview, fresh (neither ``stale`` nor ``pending``), at once;
* a change the overview reads (a run added or discarded) serves the OLD overview at once, ``stale: true`` with
  ``stale_since``, and the next compute replaces it; it is kept under the fingerprint the WORKER read;
* a Discovery run still going marks the served overview stale with ``running: true`` and the page's polls do not
  schedule a compute each;
* a compute that raises reaches the read as a 500 whose body names ``MapFailed`` — never a blank map;
* in the default mode the compute runs in the bridge's one worker process (`corpus.coverage_pool`), not the bridge.

Read timings are the route's own (`read_ms`), not the HTTP round trip. FastAPI lives only in `webui/.venv`; under
the conda pytest this file skips. The core half is `tests/test_discovery_map_cache.py`.
"""
import os
import shutil
import sqlite3
import sys
import threading

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBUI_DIR = os.path.join(PROJECT_ROOT, "webui")
TESTS_DIR = os.path.join(PROJECT_ROOT, "tests")
for p in (PROJECT_ROOT, WEBUI_DIR, TESTS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv; run this file with that interpreter")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from fastapi.testclient import TestClient  # noqa: E402

import perf_fixture  # noqa: E402
from server import corpus  # noqa: E402
from server import discovery_map as DMAP  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402
from Working.discovery import detection_map as DM  # noqa: E402

SMALL = dict(n_channels=3, hours=24.0, n_druns=4, n_detections=6_000, n_annotations=200, n_templates=3,
             queue_size=50, n_adjudications=10, n_reviewed=20)
URL = "/api/discovery/map"


@pytest.fixture(scope="module")
def bridge(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("mapcache")
    info = perf_fixture.build(str(tmp / "scale.sqlite"), **SMALL)
    rt = Runtime("sandbox", stamp="map-cache", db_source=info["db"], runtime_root=str(tmp / "runtime")).setup()
    with TestClient(create_app(rt), raise_server_exceptions=False) as client:
        yield client, rt, info
    DMAP.reset_map_cache()
    rt.restore()


@pytest.fixture()
def fresh(bridge, monkeypatch):
    """No overview held anywhere (memory or disk), nothing scheduled; the compute on a thread unless a test asks for
    the process."""
    client, rt, info = bridge
    monkeypatch.setattr(corpus, "COVERAGE_WORKER", "thread")
    DMAP.reset_map_cache()
    shutil.rmtree(os.path.join(rt.cache_dir, "map"), ignore_errors=True)
    yield client, rt, info
    DMAP.reset_map_cache()


class _Gate:
    """The thread-mode compute, held until released, counting its calls and recording the fingerprint it returns."""

    def __init__(self, monkeypatch):
        self.go = threading.Event()
        self.calls = 0
        self.fps = []
        real = DMAP._compute_here

        def held(db_path, exclude):
            self.calls += 1
            assert self.go.wait(120), "the gate was never opened"
            fp, out = real(db_path, exclude)
            self.fps.append(fp)
            return fp, out
        monkeypatch.setattr(DMAP, "_compute_here", held)


def _edit(rt, sql, args=()):
    c = sqlite3.connect(rt.db_path)
    try:
        c.execute(sql, args)
        c.commit()
    finally:
        c.close()


def _db_fp(rt):
    c = sqlite3.connect(rt.db_path)
    c.row_factory = sqlite3.Row
    try:
        return DM.overview_fingerprint(c, DMAP._exclude(c))
    finally:
        c.close()


def _strip(body):
    return {k: v for k, v in body.items() if k not in ("stale", "stale_since", "running", "read_ms", "pending")}


def test_a_first_read_is_pending_at_once_and_schedules_exactly_one_compute(fresh, monkeypatch):
    client, rt, info = fresh
    gate = _Gate(monkeypatch)
    got = client.get(URL)
    assert got.status_code == 200, got.text
    body = got.json()
    assert body.get("pending") is True
    assert body["read_ms"] < 100, f"a pending read took {body['read_ms']:.0f} ms: it computed something"
    assert "session" in body, "the page still learns which session is open"
    assert DMAP.map_status()["scheduled"] == 1

    again = client.get(URL).json()
    assert again.get("pending") is True
    assert DMAP.map_status()["scheduled"] == 1, "a second read before the compute lands must schedule nothing"

    gate.go.set()
    assert DMAP.wait_map_idle(120)
    assert gate.calls == 1
    done = client.get(URL).json()
    assert "pending" not in done and "stale" not in done, done.keys()
    assert done["read_ms"] < 50, f"a fresh read took {done['read_ms']:.0f} ms"
    assert done["datasets"] and done["datasets"][0]["file"] == perf_fixture.SOURCE_FILE
    assert done["datasets"][0]["key"], "datasets are keyed as every other Discovery route keys a recording"


def test_a_fresh_overview_is_the_one_the_core_computes(fresh):
    client, rt, info = fresh
    client.get(URL)
    assert DMAP.wait_map_idle(120)
    body = client.get(URL).json()
    c = sqlite3.connect(rt.db_path)
    c.row_factory = sqlite3.Row
    try:
        want = DM.dataset_map(c, exclude_files=DMAP._exclude(c))
    finally:
        c.close()
    assert body["rows"] == want["rows"]
    assert [d["cells"] for d in body["datasets"]] == [d["cells"] for d in want["datasets"]]


@pytest.mark.parametrize("change", [
    "INSERT INTO detections (run_id, start_idx, end_idx, score) SELECT id, 10, 20, 0.5 FROM runs "
    "WHERE surrogate_of_run_id IS NULL ORDER BY id LIMIT 1",
    "UPDATE discovery_runs SET superseded_at = '2026-10-20T10:00:00' WHERE id = (SELECT MAX(id) FROM discovery_runs)",
])
def test_a_change_serves_the_old_overview_stale_at_once_then_the_new_one(fresh, monkeypatch, change):
    client, rt, info = fresh
    client.get(URL)
    assert DMAP.wait_map_idle(120)
    old = client.get(URL).json()
    assert "stale" not in old

    gate = _Gate(monkeypatch)
    _edit(rt, change)
    asked_fp = _db_fp(rt)
    stale = client.get(URL).json()
    assert stale.get("stale") is True and stale.get("stale_since"), stale.keys()
    assert stale["read_ms"] < 100
    assert _strip(stale) == _strip(old), "the OLD overview, as it was"
    # a second change while the compute is held: the worker reads it, and the overview is kept under what it read
    _edit(rt, "INSERT INTO detections (run_id, start_idx, end_idx, score) SELECT id, 30, 40, 0.5 FROM runs "
              "WHERE surrogate_of_run_id IS NULL ORDER BY id DESC LIMIT 1")
    gate.go.set()
    assert DMAP.wait_map_idle(120)
    assert gate.calls == 1
    assert gate.fps[0] != asked_fp
    assert DMAP.map_status()["stored"] == gate.fps[0], "kept under the fingerprint the worker read"
    new = client.get(URL).json()
    assert "stale" not in new and "pending" not in new
    assert DMAP.map_status()["scheduled"] == 2, "the fresh read scheduled nothing more"


def test_a_running_discovery_run_marks_the_overview_stale_and_the_polls_coalesce(fresh, monkeypatch):
    client, rt, info = fresh
    client.get(URL)
    assert DMAP.wait_map_idle(120)
    _edit(rt, "UPDATE discovery_runs SET status = 'running' WHERE id = (SELECT MIN(id) FROM discovery_runs)")
    try:
        before = DMAP.map_status()["scheduled"]
        for i in range(6):
            # the run writes as it goes: each poll sees a new state
            _edit(rt, "INSERT INTO detections (run_id, start_idx, end_idx, score) SELECT id, ?, ?, 0.5 FROM runs "
                      "WHERE surrogate_of_run_id IS NULL ORDER BY id LIMIT 1", (100 + i, 110 + i))
            body = client.get(URL).json()
            assert body.get("stale") is True and body.get("running") is True, body.keys()
            assert body["read_ms"] < 100
        assert DMAP.wait_map_idle(120)
        assert DMAP.map_status()["scheduled"] - before <= 1, "the page's polls must not schedule a compute each"
    finally:
        _edit(rt, "UPDATE discovery_runs SET status = 'done' WHERE status = 'running'")


def test_a_compute_that_raises_is_a_500_naming_map_failed(fresh, monkeypatch):
    client, rt, info = fresh

    def broken(db_path, exclude):
        raise ValueError("the runs table could not be read")
    monkeypatch.setattr(DMAP, "_compute_here", broken)
    assert client.get(URL).json().get("pending") is True
    assert DMAP.wait_map_idle(120)
    got = client.get(URL)
    assert got.status_code == 500
    assert "MapFailed" in got.text and "the runs table could not be read" in got.text


def test_the_overview_survives_a_restart_from_disk(fresh):
    client, rt, info = fresh
    client.get(URL)
    assert DMAP.wait_map_idle(120)
    assert os.listdir(os.path.join(rt.cache_dir, "map")), "kept under <runtime root>/cache/map/"
    DMAP.reset_map_cache()             # a restart: memory gone, disk kept
    body = client.get(URL).json()
    assert "pending" not in body and "stale" not in body
    assert DMAP.map_status()["scheduled"] == 0


def test_by_default_the_compute_runs_in_the_worker_process(bridge, monkeypatch):
    client, rt, info = bridge
    DMAP.reset_map_cache()
    shutil.rmtree(os.path.join(rt.cache_dir, "map"), ignore_errors=True)

    def boom(*a, **kw):
        raise AssertionError("the bridge computed the overview itself")
    monkeypatch.setattr(DMAP, "_compute_here", boom)
    assert client.get(URL).json().get("pending") is True
    assert DMAP.wait_map_idle(600)
    body = client.get(URL).json()
    assert "pending" not in body and "stale" not in body, body.get("error")
    assert DMAP.map_status()["mode"] == "process"
    DMAP.reset_map_cache()
