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
    # gate, 2026-10-20: importing the registry imports every adapter, and detection.fluss reads the MP calibration
    # file at IMPORT time (`max_span_samples_for_background()`, a module-level default). From the main checkout that
    # relative path is the real DATA/db/mp_calibration.json, so FLUSS kept a 678,125-sample cap for the rest of the
    # session and test_webui_run_routing's over-the-limit test met the cap refusal instead of the SLURM route. Point
    # it at this test's tmp first, as the bridge's sandbox runtime does; nothing reads or writes the real file.
    import Working.Detection.matrix_profiling.cost as _mpc
    monkeypatch.setattr(_mpc, "CALIBRATION_PATH", str(tmp_path / "mp_calibration.json"))
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


def test_the_child_hands_its_timing_back_and_the_bridge_alone_writes_the_shared_calibration_file(fresh, monkeypatch):
    """The calibration file is read by every validate (`calibration_status`) and written by every timing. The child
    times into a scratch file of its own and RETURNS the entry; the bridge merges it into the shared file under
    `block_cost._FILE_LOCK`, as it always did — so two children timing two models never race a read-merge-write
    across processes, and an `os.replace` onto the shared file never happens outside the bridge. The child writes
    no database row and no cache."""
    chain, block_cost, path = fresh
    real_save = block_cost._save
    writes = []

    def spy(data, p=None):
        writes.append((os.getpid(), os.path.abspath(p or block_cost.CALIBRATION_PATH)))
        return real_save(data, p)
    monkeypatch.setattr(block_cost, "_save", spy)
    st = _calibrate(chain, path)
    assert st["state"] == "calibrated" and st["pid"] != os.getpid()
    assert writes == [(os.getpid(), os.path.abspath(str(path)))], writes
    data = json.load(open(path, encoding="utf-8"))
    assert data[block_cost._key(NAME)]["k"] > 0


# ── fix round (the critic, 2026-10-20) ──────────────────────────────────────────────────────────────────────────

def test_f1_the_child_times_a_warm_model_not_its_first_cold_call(fresh, tmp_path):
    """F1 (blocker): a fresh interpreter pays the model's lazy imports and numba compile inside the one timed
    run_once — interrogation.trains read k 2.2e-4..2.9e-4 in the child against 1.6e-6 on a warm thread, and an
    inflated k is merged into block_calibration.json for good (routing a long span to the cluster). The child warms
    the model untimed first; its k is within 5x of a warm in-process timing of the same model in this run."""
    chain, block_cost, path = fresh
    trains = "interrogation.trains"
    exponent, run_once = block_cost.MODELS[trains]
    import numpy as np
    if trains in block_cost.WARM_UPS:
        block_cost.WARM_UPS[trains]()
    run_once(np.cumsum(np.random.default_rng(1).standard_normal(1000)) * 1e-3, 1.0)     # warm, untimed
    here = tmp_path / "here.json"
    k_here = block_cost.calibrate([trains], path=str(here))[trains]
    gen = {"state": "calibrating", "seconds": None, "error": None}
    chain._BC_STATE[trains] = gen
    chain._calibrate_block_cost(trains, str(path), gen)
    assert chain._BC_STATE[trains]["state"] == "calibrated", chain._BC_STATE[trains]
    k_child = json.load(open(path, encoding="utf-8"))[block_cost._key(trains)]["k"]
    print(f"F1: child k {k_child:.3g}, warm in-process k {k_here:.3g}")
    assert k_child <= 5 * k_here, f"child k {k_child:.3g} vs warm in-process k {k_here:.3g}"


def test_f2_a_child_that_hangs_is_stopped_and_the_model_reads_failed_in_words(fresh, monkeypatch):
    """F2: fut.result() had no timeout — a hung child left the model 'calibrating' until a restart."""
    import time as _t
    chain, block_cost, path = fresh
    monkeypatch.setattr(chain, "CALIBRATION_TIMEOUT_S", 3.0)
    monkeypatch.setattr(chain, "_child_call", lambda name, module: (_t.sleep, (120,)))
    t0 = _t.time()
    st = _calibrate(chain, path)
    assert _t.time() - t0 < 30
    assert st["state"] == "failed" and "timed out after 3 s" in st["error"], st
    assert not chain._BC_POOLS, "the hung child's pool is terminated, not left running"


def test_f6_at_most_one_calibration_child_at_a_time_and_the_others_read_calibrating(fresh, monkeypatch):
    """F6: free RAM is ~1 GB; two models timing at once was two extra interpreters. One child at a time; a queued
    model reads 'calibrating' meanwhile."""
    import threading
    import time as _t
    chain, block_cost, path = fresh
    monkeypatch.setattr(chain, "_child_call", lambda name, module: (_t.sleep, (2,)))
    names = ["preprocessing.invert", "interrogation.intervals"]
    gens = {}
    threads = []
    for n in names:
        gens[n] = {"state": "calibrating", "seconds": None, "error": None}
        chain._BC_STATE[n] = gens[n]
        threads.append(threading.Thread(target=chain._calibrate_block_cost, args=(n, str(path), gens[n]), daemon=True))
    for t in threads:
        t.start()
    peak = 0
    while any(t.is_alive() for t in threads):
        peak = max(peak, len(chain._BC_POOLS))
        _t.sleep(0.05)
    assert peak == 1, f"{peak} calibration children ran at once"


def test_f6_the_starting_request_never_waits_past_calibration_wait_s_while_the_corpus_worker_starts(fresh, monkeypatch):
    """F6: corpus.coverage_pool() holds corpus._POOL_LOCK while it starts its worker (up to 180 s); the submit that
    needs it happens on the calibration's own thread, so the validate that started it still answers in time."""
    import time as _t
    chain, block_cost, path = fresh
    from server import corpus
    from Working.recipes import make_recipe
    monkeypatch.setattr(chain, "CALIBRATION_WAIT_S", 1.0)
    recipe = make_recipe(1, [{"stage": "preprocessing", "algorithm": "invert", "params": {}}], span=[0, 20_000])
    with corpus._POOL_LOCK:
        t0 = _t.time()
        out = chain.route_local(recipe, 20_000, 1.0, ceiling_s=900)
        waited = _t.time() - t0
    assert waited < 2.0 and out["route"] == "unknown", (waited, out["route"])


# ── gate round (2026-10-20, merged main d3ce03c) ─────────────────────────────────────────────────────────────────

def test_g1_a_run_waits_for_a_quick_model_another_request_started_and_is_routed_without_a_409(fresh, monkeypatch):
    """G1: zz_analyse_run › fixup-j-dehshibi-funnel. The validate after *use example* started timing
    preprocessing.wavelet_transform (uncalibrated in the real file); the Run click that followed found it running and,
    since the first fix, did not wait — POST /api/runs answered 409 "calibrating" and the run never started. A run
    now waits for a timing in flight up to RUN_CALIBRATION_WAIT_S (its own bound) before it answers; a stand-in child
    that takes ~12 s lands inside it."""
    import time as _t
    chain, block_cost, path = fresh
    from server import calibrate_child
    from Working.recipes import make_recipe
    monkeypatch.setattr(chain, "CALIBRATION_WAIT_S", 1.0)
    monkeypatch.setattr(chain, "_child_call", lambda name, module: (calibrate_child.calibrate_in_child, (name, module, 12.0)))
    recipe = make_recipe(1, [{"stage": "preprocessing", "algorithm": "invert", "params": {}}], span=[0, 20_000])
    validate = chain.route_local(recipe, 20_000, 1.0, ceiling_s=900)
    assert validate["route"] == "unknown" and validate["calibrating"] == [0], "the validate starts it and answers"
    t0 = _t.time()
    run = chain.route_local(recipe, 20_000, 1.0, ceiling_s=900, wait_s=chain.RUN_CALIBRATION_WAIT_S)
    assert run["route"] == "local" and run["calibrating"] == [], run
    assert _t.time() - t0 < chain.RUN_CALIBRATION_WAIT_S
    assert chain.RUN_CALIBRATION_WAIT_S >= 30


def test_g1_post_runs_asks_route_local_for_the_longer_wait():
    src = open(os.path.join(WEBUI_DIR, "server", "app.py"), encoding="utf-8").read()
    run = src[src.index('@app.post("/api/runs")'):]
    run = run[:run.index("@app.", 10)]
    assert "wait_s=chain_mod.RUN_CALIBRATION_WAIT_S" in run, "POST /api/runs waits the run's own bound for a timing"
