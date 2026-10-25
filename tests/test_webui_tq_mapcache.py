"""
test_webui_tq_mapcache.py
=========================
tq-mapcache (2026-10-25), the bridge half. Discovery › Map kept two hand-written stale-while-revalidate caches (the
overview's and the levels') that had drifted; they are one class now, and the bridge stops reaching into corpus's
private disk helpers. Pinned here:

* a level view whose off-request recompute is in flight but which is no longer held (dropped from the LRU meanwhile)
  waits for that recompute instead of computing a second time beside it (the old `_level` computed again);
* `discovery_map.py` holds one cache algorithm (no `_LV` copy) and calls corpus's public disk helpers.

FastAPI lives only in `webui/.venv`; under the conda pytest this file skips.
"""
import os
import sqlite3
import sys
import threading
import time

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
from server import discovery_map as DMAP  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402
from Working.discovery import detection_map as DM  # noqa: E402

SMALL = dict(n_channels=3, hours=24.0, n_druns=4, n_detections=6_000, n_annotations=200, n_templates=3,
             queue_size=50, n_adjudications=10, n_reviewed=20)
KEY = perf_fixture.SOURCE_FILE.rsplit(".", 1)[0]
A = f"/api/discovery/map/dataset?recording={KEY}&chunks=2"
B = f"/api/discovery/map/dataset?recording={KEY}&chunks=1"
NEW_VERDICT = ("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
               "SELECT MIN(id), 100, 110, 'interesting', 'tq-mapcache-test', '2026-10-25T12:00:00+00:00' "
               "FROM recordings")


@pytest.fixture(scope="module")
def bridge(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("tqmapcache")
    info = perf_fixture.build(str(tmp / "scale.sqlite"), **SMALL)
    rt = Runtime("sandbox", stamp="tq-mapcache", db_source=info["db"], runtime_root=str(tmp / "runtime")).setup()
    with TestClient(create_app(rt), raise_server_exceptions=False) as client:
        yield client, rt
    DMAP.reset_level_cache()
    DMAP.reset_map_cache()
    rt.restore()


def _view_compute_count(monkeypatch, go):
    """Counts every level compute (`DM.compute` with a view, or the old `DM.compute_level`); the off-request
    recompute waits for `go`."""
    calls = []
    for name in ("compute", "compute_level"):
        real = getattr(DM, name, None)
        if real is None:
            continue

        def counted(*a, _real=real, _name=name, **kw):
            if _name == "compute_level" or len(a) > 2 or "view" in kw:
                calls.append(threading.current_thread().name)
                if threading.current_thread().name.startswith("discovery-map-level"):
                    assert go.wait(120), "never released"
            return _real(*a, **kw)
        monkeypatch.setattr(DM, name, counted)
    return calls


def test_a_view_in_flight_but_no_longer_held_waits_for_the_recompute(bridge, monkeypatch):
    client, rt = bridge
    DMAP.reset_level_cache()
    assert client.get(B).status_code == 200
    size_b = DMAP.level_status()["bytes"]
    DMAP.reset_level_cache()
    assert client.get(A).status_code == 200
    size_a = DMAP.level_status()["bytes"]

    go = threading.Event()
    calls = _view_compute_count(monkeypatch, go)
    c = sqlite3.connect(rt.db_path)
    c.execute(NEW_VERDICT)
    c.commit()
    c.close()
    assert client.get(A).json().get("stale") is True       # the old answer; one recompute scheduled, held
    # B fits the budget, A + B do not: keeping B drops A (least recently read) while A's recompute is in flight
    monkeypatch.setattr(DMAP, "LEVEL_CACHE_BYTES", size_b + size_a // 2)
    assert client.get(B).status_code == 200
    assert DMAP.level_status()["held"] == 1

    got = {}
    t = threading.Thread(target=lambda: got.setdefault("r", client.get(A)))
    t.start()
    t0 = time.monotonic()
    while len(calls) < 3 and time.monotonic() - t0 < 3.0:
        time.sleep(0.05)
    go.set()
    t.join(120)
    assert DMAP.wait_levels_idle(120)
    assert got["r"].status_code == 200, got["r"].text
    assert "stale" not in got["r"].json(), "the answer is the recompute's, current"
    assert len(calls) == 2, f"A's recompute and B's first read only, not a second A beside the recompute: {calls}"
    DMAP.reset_level_cache()


def _src(name):
    with open(os.path.join(WEBUI_DIR, "server", name), encoding="utf-8") as fh:
        return fh.read()


def test_one_cache_algorithm_and_no_reach_into_corpus_privates():
    src = _src("discovery_map.py")
    for gone in ("_LV", "_LV_LOCK", "_recompute_level", "_schedule_level", "corpus._disk"):
        assert gone not in src, f"discovery_map.py still has {gone}"
    assert "def disk_read_any" in _src("corpus.py") and "def disk_write" in _src("corpus.py")
