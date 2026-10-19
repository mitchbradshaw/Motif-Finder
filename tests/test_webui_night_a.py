"""
test_webui_night_a.py
=====================
night pass A (2026-10-19), the bridge half: what the night's drive of Discovery and Review on the scale fixture
(`tests/perf_fixture.py`, 16 channels x 60 runs) found slow, pinned by counts rather than wall-clock.

* **The scoreboard read re-read every channel's human rows once per run.** Every Discovery page asks
  `/api/discovery/scoreboard` for every finished run on every scope channel. Even answered from the score cache,
  it took 54 s on the scale fixture: `score_runs_cached` was called per run with no `memo`, so
  `inputs_fingerprint` re-read each channel's annotations, reviewed spans and adjudications for every run (60 runs
  x 16 channels). One read pass shares one memo (the fingerprint's own docstring), so a channel is read once.

FastAPI lives only in `webui/.venv`; under the conda pytest this file skips.
"""
import os
import sys

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
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402
from Working.discovery import scoreboard as SB  # noqa: E402
from Working.review import queues as Q  # noqa: E402

SMALL = dict(n_channels=4, hours=24.0, n_druns=6, n_detections=20_000, n_annotations=400, n_templates=6,
             queue_size=200, n_adjudications=40, n_reviewed=40)


@pytest.fixture(scope="module")
def bridge(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("night_a")
    info = perf_fixture.build(str(tmp / "scale.sqlite"), **SMALL)
    rt = Runtime("sandbox", stamp="night-a", db_source=info["db"], runtime_root=str(tmp / "runtime")).setup()
    getattr(Q, "clear_resolver_cache", lambda: None)()
    with TestClient(create_app(rt)) as client:
        yield client, rt, info
    rt.restore()


def test_a_scoreboard_read_reads_each_channel_once(bridge, monkeypatch):
    client, rt, info = bridge
    keys = [d["key"] for d in info["druns"]]
    chans = ",".join(info["channel_names"])
    url = f"/api/discovery/scoreboard?runs={','.join(keys)}&channels={chans}&t0=0&t1=24"
    first = client.get(url)
    assert first.status_code == 200, first.text
    assert len(first.json()) == len(keys)
    reads = []
    real = SB._read_channel_rows
    monkeypatch.setattr(SB, "_read_channel_rows", lambda conn, rec_id: reads.append(rec_id) or real(conn, rec_id))
    again = client.get(url)
    assert again.status_code == 200, again.text
    assert again.json() == first.json(), "the cached read must serve exactly what the first one did"
    # one read per channel for the whole request; it was one per run per channel (6 x 4 = 24 here, 960 at scale)
    assert len(reads) <= len(info["channel_names"]), f"{len(reads)} channel reads for {len(info['channel_names'])} channels"


def test_two_identical_scoreboard_reads_score_each_run_once(bridge, monkeypatch):
    """* **Identical scoreboard reads piled up.** Runs, Seed search, Compare and Map each ask for the same
    scoreboard when they open; cold on the scale fixture one read took 8 min, and every page visit in that window
    started its own copy (four Discovery pages opened twice kept the bridge busy for half an hour after the browser
    was gone). A read that arrives while the same read is being worked out waits for it and is answered from the
    cache: each run is scored once."""
    import threading
    import time as _time
    client, rt, info = bridge
    keys = [d["key"] for d in info["druns"]][:3]
    chans = ",".join(info["channel_names"])
    url = f"/api/discovery/scoreboard?runs={','.join(keys)}&channels={chans}&t0=0&t1=12"
    SB.clear_score_cache()
    calls = []
    real = SB.score_runs

    def slow(conn, run_ids, **kw):
        calls.append(tuple(run_ids))
        _time.sleep(0.4)          # long enough that the second read arrives while the first is scoring
        return real(conn, run_ids, **kw)
    monkeypatch.setattr(SB, "score_runs", slow)
    out = []
    threads = [threading.Thread(target=lambda: out.append(client.get(url))) for _ in range(2)]
    for t in threads:
        t.start()
        _time.sleep(0.1)
    for t in threads:
        t.join(120)
    assert [r.status_code for r in out] == [200, 200], [r.text[:200] for r in out]
    assert out[0].json() == out[1].json()
    assert len(calls) == len(set(calls)) == len(keys), f"{len(calls)} scorings for {len(keys)} runs"
