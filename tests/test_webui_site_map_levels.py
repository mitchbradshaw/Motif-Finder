"""
test_webui_site_map_levels.py
=============================
site-map (2026-10-20), item 1, the route half: `GET /api/discovery/map/dataset` (level 2) and
`GET /api/discovery/map/channel` (level 1) were computed on every read. Now they keep the last answer per
(level, recording, chunks | channel + bin) under the overview's fingerprint (`detection_map.overview_fingerprint`,
skipped while SQLite's change counter stands):

* a second read of the same view with nothing changed computes nothing and answers from memory;
* after a change the OLD answer is served at once with ``stale: true`` and ``stale_since``, exactly one recompute
  runs off the request, and the read after it lands is fresh (no ``stale``);
* a first read of a view never seen computes it on the request (no blank, no ``pending`` the page would have to
  poll), so the existing pages and smoke states read exactly what they read before;
* a different slice count or bin width is a view of its own.

FastAPI lives only in `webui/.venv`; under the conda pytest this file skips.
"""
import os
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
from server import discovery_map as DMAP  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402
from Working.discovery import detection_map as DM  # noqa: E402

SMALL = dict(n_channels=3, hours=24.0, n_druns=4, n_detections=6_000, n_annotations=200, n_templates=3,
             queue_size=50, n_adjudications=10, n_reviewed=20)
KEY = perf_fixture.SOURCE_FILE.rsplit(".", 1)[0]


@pytest.fixture(scope="module")
def bridge(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("maplevels")
    info = perf_fixture.build(str(tmp / "scale.sqlite"), **SMALL)
    rt = Runtime("sandbox", stamp="map-levels", db_source=info["db"], runtime_root=str(tmp / "runtime")).setup()
    with TestClient(create_app(rt), raise_server_exceptions=False) as client:
        yield client, rt, info
    DMAP.reset_level_cache()
    DMAP.reset_map_cache()
    rt.restore()


@pytest.fixture()
def fresh(bridge):
    DMAP.reset_level_cache()
    yield bridge
    DMAP.reset_level_cache()


class _Count:
    """Counts the level computes and can hold the off-request recompute until released."""

    def __init__(self, monkeypatch, hold=False):
        self.calls = 0
        self.go = threading.Event()
        if not hold:
            self.go.set()
        real = DM.compute_level

        def counted(*a, **kw):
            self.calls += 1
            if threading.current_thread().name.startswith("discovery-map-level"):   # the off-request recompute
                assert self.go.wait(120), "never released"
            return real(*a, **kw)
        monkeypatch.setattr(DM, "compute_level", counted)


def _edit(rt, sql, args=()):
    c = sqlite3.connect(rt.db_path)
    try:
        c.execute(sql, args)
        c.commit()
    finally:
        c.close()


def _strip(body):
    return {k: v for k, v in body.items() if k not in ("stale", "stale_since", "read_ms")}


def _urls(info):
    c = sqlite3.connect(info["db"])
    try:
        n = c.execute("SELECT COUNT(*) FROM recordings").fetchone()[0]
    finally:
        c.close()
    ch = perf_fixture.channel_names(n)[0]
    return [f"/api/discovery/map/dataset?recording={KEY}&chunks=2",
            f"/api/discovery/map/channel?recording={KEY}&channel={ch}&binH=3"]


@pytest.mark.parametrize("which", [0, 1])
def test_a_second_read_computes_nothing(fresh, monkeypatch, which):
    client, rt, info = fresh
    url = _urls(info)[which]
    count = _Count(monkeypatch)
    first = client.get(url)
    assert first.status_code == 200, first.text
    assert "stale" not in first.json() and "pending" not in first.json()
    assert count.calls == 1, "a view never seen is computed on the request"
    again = client.get(url)
    assert again.status_code == 200
    assert count.calls == 1, "nothing changed: the second read must not compute"
    assert _strip(again.json()) == _strip(first.json())
    assert again.json()["read_ms"] < 300, again.json()["read_ms"]


@pytest.mark.parametrize("which", [0, 1])
def test_a_change_serves_the_old_answer_stale_then_one_recompute(fresh, monkeypatch, which):
    client, rt, info = fresh
    url = _urls(info)[which]
    old = client.get(url).json()
    count = _Count(monkeypatch, hold=True)
    _edit(rt, "INSERT INTO detections (run_id, start_idx, end_idx, score) SELECT id, 10, 20, 0.5 FROM runs "
              "WHERE surrogate_of_run_id IS NULL ORDER BY id LIMIT 1")
    stale = client.get(url).json()
    assert stale.get("stale") is True and stale.get("stale_since"), stale.keys()
    assert _strip(stale) == _strip(old), "the OLD answer, as it was"
    client.get(url)                                    # a poll while the recompute is held schedules nothing more
    count.go.set()
    assert DMAP.wait_levels_idle(120)
    assert count.calls == 1, f"{count.calls} recomputes for one change"
    new = client.get(url).json()
    assert "stale" not in new, new.keys()
    assert count.calls == 1


def test_another_slice_count_is_a_view_of_its_own(fresh, monkeypatch):
    client, rt, info = fresh
    count = _Count(monkeypatch)
    a = client.get(f"/api/discovery/map/dataset?recording={KEY}&chunks=1").json()
    b = client.get(f"/api/discovery/map/dataset?recording={KEY}&chunks=4").json()
    assert a["chunks"] == 1 and b["chunks"] == 4
    assert count.calls == 2


def test_the_level_answers_still_say_which_session_is_open(fresh):
    client, rt, info = fresh
    for url in _urls(info):
        body = client.get(url).json()
        assert body["session"]["recording"] and body["key"] == KEY
        body = client.get(url).json()
        assert body["session"]["recording"] and body["key"] == KEY
