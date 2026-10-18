"""
test_coverage_map_compute.py
============================
corpus-map-off-the-request: the corpus map's computation moves out of the bridge into the core
(`Working/discovery/coverage_map.py`) so a worker PROCESS can run it while the bridge keeps serving pages.

Two things are pinned here:

* the moved computation answers exactly what the bridge's `_coverage` answered before the move. The hashes below
  were taken from `webui/server/corpus.py::_coverage` at base `60d8c09`, on the same two fixtures (the `scored`
  fixture of `test_perf_scoring_reads.py` and its legacy span-relative one), so a drift in a cell, a key or a
  number fails here even though `_coverage` is now a thin call to the moved code;
* the worker child imports the core only: no `webui.server` module, no FastAPI, Starlette or uvicorn, even when
  the parent's `__main__` imports the bridge (as `webui/run_server.py` does, which a spawned child would
  otherwise re-run).

Runs under the conda interpreter (no FastAPI needed).
"""
import hashlib
import json
import os
import sys
import types

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database.schema import init_db  # noqa: E402
from tests.test_perf_scoring_reads import _build_scored, _legacy_db  # noqa: E402

UI_MODULES = ("webui", "server", "fastapi", "starlette", "uvicorn")

#: sha1 of the payload (less `compute_ms`) as `corpus._coverage` answered it at base 60d8c09
GOLDEN = {
    ("scored", "bins10"): "5321baf163ff54725d61d1407c363ad2966597ba",
    ("scored", "bins57-seed-interesting"): "7cecacbf2cd222280e520be60a24230b79997747",
    ("scored", "run0"): "1d586957be1339a49bd7d76716d0a9379cccf6f5",
    ("scored", "method-thresh"): "f4410a453d6b2ac476e30b748710749893712f8d",
    ("scored", "method-nope"): "d1849c76919ec0f8e3f3c476d177a895c6917cb6",
    ("legacy", "bins20"): "13830adf06b5d64232b18ecd0aeeab6c62f3af37",
    ("legacy", "bins20-runs"): "72dc09cc8649a7d3fd75f7e0b1b93041d267bb05",
}


def _digest(payload):
    p = {k: v for k, v in payload.items() if k != "compute_ms"}
    return hashlib.sha1(json.dumps(p, sort_keys=True).encode()).hexdigest()


@pytest.fixture
def dbs(tmp_path):
    sconn = init_db(str(tmp_path / "scored.sqlite"))
    s = _build_scored(sconn)
    lconn, _rec, lruns = _legacy_db(str(tmp_path / "legacy.sqlite"))
    cases = {
        ("scored", "bins10"): ("cache.mat", dict(bins=10)),
        ("scored", "bins57-seed-interesting"): ("cache.mat", dict(bins=57, verdicts=("seed", "interesting"))),
        ("scored", "run0"): ("cache.mat", dict(bins=10, run_ids=[s["runs"][0]])),
        ("scored", "method-thresh"): ("cache.mat", dict(bins=10, method="thresh")),
        ("scored", "method-nope"): ("cache.mat", dict(bins=10, method="nope")),
        ("legacy", "bins20"): ("legacy.mat", dict(bins=20)),
        ("legacy", "bins20-runs"): ("legacy.mat", dict(bins=20, run_ids=[lruns[1], lruns[2]])),
    }
    yield {"scored": (sconn, str(tmp_path / "scored.sqlite")), "legacy": (lconn, str(tmp_path / "legacy.sqlite")),
           "cases": cases}
    sconn.close()
    lconn.close()


def test_the_moved_computation_answers_what_the_bridge_answered(dbs):
    from Working.discovery import coverage_map as CM
    for (fixture, name), (sf, kw) in dbs["cases"].items():
        _conn, path = dbs[fixture]
        got = CM.compute(path, sf, **kw)
        assert _digest(got) == GOLDEN[(fixture, name)], f"{fixture}/{name}: the map changed"


def test_the_bridge_reads_the_same_map_through_its_thin_call(dbs):
    from webui.server import corpus
    for (fixture, name), (sf, kw) in dbs["cases"].items():
        conn, _path = dbs[fixture]
        assert _digest(corpus._coverage(conn, sf, **kw)) == GOLDEN[(fixture, name)], f"{fixture}/{name}"


def test_the_core_opens_the_database_read_only(dbs):
    """The worker reads; it never writes. A write through its connection must be refused."""
    import sqlite3

    from Working.discovery import coverage_map as CM
    conn = CM.connect_read_only(dbs["scored"][1])
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO settings (page, key, value_json, updated_at) VALUES ('x', 'y', '1', 'now')")
    finally:
        conn.close()


def test_a_channel_yield_is_called_between_channels(dbs):
    """The thread fallback yields to the pages between channels: the hook runs before every channel but the first."""
    from Working.discovery import coverage_map as CM
    calls = []
    conn, _ = dbs["scored"]
    out = CM.compute_conn(conn, "cache.mat", bins=10, between_channels=lambda: calls.append(1))
    assert len(calls) == len(out["rows"]) - 1 == 1
    assert _digest(out) == GOLDEN[("scored", "bins10")]


def _fake_main(tmp_path):
    """A `__main__` that imports the bridge at its top, as `webui/run_server.py` does."""
    path = tmp_path / "fake_run_server.py"
    path.write_text("import webui.server.corpus  # noqa: F401\n", encoding="utf-8")
    mod = types.ModuleType("__main__")
    mod.__file__ = str(path)
    mod.__spec__ = None
    return mod


def test_the_worker_child_imports_no_ui_module(tmp_path, monkeypatch):
    from Working.discovery import coverage_map as CM
    from webui.server import corpus
    monkeypatch.setitem(sys.modules, "__main__", _fake_main(tmp_path))
    corpus.shutdown_coverage_pool()
    try:
        pool = corpus.coverage_pool()
        assert pool is not None, "the worker pool did not start"
        loaded = pool.submit(CM.child_modules, UI_MODULES).result(timeout=180)
        assert loaded == [], f"the worker child imported UI modules: {loaded}"
        assert pool.submit(CM.child_modules, ("Working.discovery.coverage_map",)).result(timeout=60)
    finally:
        corpus.shutdown_coverage_pool()


def test_without_the_guard_a_spawned_child_would_import_the_bridge(tmp_path, monkeypatch):
    """The control for the test above: a plain spawned pool under the same `__main__` DOES import the bridge,
    so an empty list there is the guard working, not a check that cannot fail."""
    import multiprocessing as mp
    from concurrent.futures import ProcessPoolExecutor

    from Working.discovery import coverage_map as CM
    monkeypatch.setitem(sys.modules, "__main__", _fake_main(tmp_path))
    with ProcessPoolExecutor(max_workers=1, mp_context=mp.get_context("spawn")) as pool:
        loaded = pool.submit(CM.child_modules, UI_MODULES).result(timeout=180)
    assert "webui.server.corpus" in loaded
