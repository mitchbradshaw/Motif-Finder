"""
test_webui_site_x_calibration.py
================================
site-x item 3 (the researcher, 2026-10-20: "pulled span into analyse, loading forever, whole website lagging, working
again after ~2 minutes").

Measured on a main-checkout sandbox bridge (port 8769, the real database copied): Signal › Open in Analyse and
Cross-channel › Open in Analyse answer in under half a second, cold or warm, with an empty chain, the drop chain, a
whole-recording span and a run. The one path that reproduced "loading forever" and a site-wide slowdown is a chain
holding a block whose cost model is not yet calibrated on this machine: `chain.route_local` starts the model's
timing (`Working.block_cost.calibrate`) on a THREAD of the bridge, every POST /api/chain/validate then holds for
CALIBRATION_WAIT_S (10 s) and answers "calibrating" (the page re-validates), and the timing's Python holds the GIL
against every other request — with `detection.rupture` (≈447 s to time) GET /api/review/counts went from 1.0-1.5 s to
2.5-7.3 s for as long as the timing ran. Nine of the eighteen registered models are uncalibrated in the real
database's block_calibration.json (rupture, trains, cycle_shapes, snippets, cnn window scores, ...).

The fix keeps the estimate and the cache keys exactly as they were and moves only WHERE the timing runs: in a
process of its own, so the bridge's request threads never wait on its GIL. A stand-in `calibrate` (the tests' fake
in test_webui_run_routing.py) cannot cross a process boundary and still runs on the thread.

    python -m pytest tests/test_webui_site_x_calibration.py
"""
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBUI_DIR = os.path.join(PROJECT_ROOT, "webui")
for p in (PROJECT_ROOT, WEBUI_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

NAME = "preprocessing.invert"     # a registered cost model that times in milliseconds


@pytest.fixture
def fresh(tmp_path, monkeypatch):
    from Working import block_cost
    from Adapters import registry  # noqa: F401 - registers every adapter's cost model
    from server import chain
    monkeypatch.setattr(block_cost, "CALIBRATION_PATH", str(tmp_path / "block_calibration.json"))
    chain.reset_block_calibration()
    yield chain, block_cost, tmp_path / "block_calibration.json"
    chain.reset_block_calibration()


def _calibrate(chain, path):
    gen = {"state": "calibrating", "seconds": None, "error": None}
    chain._BC_STATE[NAME] = gen
    chain._calibrate_block_cost(NAME, str(path), gen)
    return chain._BC_STATE[NAME]


def test_a_block_calibration_is_timed_in_a_process_of_its_own_not_on_a_bridge_thread(fresh):
    chain, block_cost, path = fresh
    st = _calibrate(chain, path)
    assert st["state"] == "calibrated", st
    assert st.get("pid") and st["pid"] != os.getpid(), "the timing ran in the bridge's own process"
    data = json.load(open(path, encoding="utf-8"))
    assert block_cost._key(NAME) in data, "the child wrote the file the request resolved, with the same key"
    assert data[block_cost._key(NAME)]["k"] > 0


def test_a_stand_in_calibrate_cannot_cross_a_process_and_runs_on_the_thread(fresh, monkeypatch):
    chain, block_cost, path = fresh
    calls = []

    def fake(names=None, force=False, path=None, **kw):
        calls.append(list(names))
        data = block_cost._load(path)
        data[block_cost._key(NAME)] = {"k": 1e-3, "exponent": 1.0, "n": 1, "elapsed_s": 0.1, "calibrated_at": "t"}
        block_cost._save(data, path)
        return {NAME: 1e-3}
    monkeypatch.setattr(block_cost, "calibrate", fake)
    st = _calibrate(chain, path)
    assert calls == [[NAME]] and st["state"] == "calibrated"
    assert st.get("pid") == os.getpid()


def test_a_calibration_child_that_fails_says_why_in_words(fresh, monkeypatch):
    chain, block_cost, path = fresh
    gen = {"state": "calibrating", "seconds": None, "error": None}
    chain._BC_STATE["no.such_block"] = gen
    chain._calibrate_block_cost("no.such_block", str(path), gen)
    st = chain._BC_STATE["no.such_block"]
    assert st["state"] == "failed" and "no.such_block" in st["error"], st


def test_only_the_request_that_starts_a_timing_waits_for_it_a_re_validate_answers_calibrating_at_once(fresh, monkeypatch):
    """The page re-validates every 3 s while a step reads "calibrating" (analyse/useValidation.ts); each request
    used to wait CALIBRATION_WAIT_S (10 s) again for the same timing, so for a 7-minute rupture timing every
    validate took 10 s — the chain page "loading forever". The request that starts the timing still waits (a quick
    model lands inside it); one that finds it already running answers at once."""
    import threading
    import time as _t
    chain, block_cost, path = fresh
    from Working.recipes import make_recipe
    release = threading.Event()

    def slow(names=None, force=False, path=None, **kw):
        release.wait(20)
        data = block_cost._load(path)
        for n in names:
            data[block_cost._key(n)] = {"k": 1e-3, "exponent": 1.0, "n": 1, "elapsed_s": 0.1, "calibrated_at": "t"}
        block_cost._save(data, path)
        return {n: 1e-3 for n in names}
    monkeypatch.setattr(block_cost, "calibrate", slow)
    monkeypatch.setattr(chain, "CALIBRATION_WAIT_S", 1.0)
    recipe = make_recipe(1, [{"stage": "detection", "algorithm": "deconvolve", "params": {}}], span=[0, 20_000])
    try:
        t0 = _t.time()
        first = chain.route_local(recipe, 20_000, 1.0, ceiling_s=900)
        assert first["route"] == "unknown" and _t.time() - t0 >= 0.9, "the starting request waits for the timing"
        t1 = _t.time()
        again = chain.route_local(recipe, 20_000, 1.0, ceiling_s=900)
        assert again["route"] == "unknown" and again["calibrating"] == [0]
        assert _t.time() - t1 < 0.5, "a re-validate while the same timing runs does not wait for it again"
    finally:
        release.set()
