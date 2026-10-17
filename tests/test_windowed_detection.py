"""
test_windowed_detection.py
==========================
Round A_2, P3: a detection run over sliding windows with overlap, each window judged on its own scale, the windows'
detections stitched into one result with nothing counted twice.

The design under test (`docs/rq_roundA_2/prompts/P3-windowed-detection.md`):

* **A window scope on the run** (`{kind: "windows", window_s, overlap_frac}`, overlap 0.5 by default), recorded in the
  run's recipe. ``window_s`` is at least 4 x the chain's longest internal window (a rolling mean, a baseline) or one
  whole piece of a block that cuts its input into pieces; a shorter window is refused naming the step. An explicit
  opt-in fits the chain's internal windows to the window length, which makes a different chain.
* **Targets:** windows start every ``window_s x (1 - overlap)``; the last ends at the section end; each window is one
  target per channel through the fan-out, so every window is an ordinary run, cached and reused.
* **Stitching** (`Working.discovery.windowed.stitch`): a window keeps a detection whose onset lies in its core (the
  part of the timeline nearer its centre than any other window's), the first and last windows keep their outer
  edges, duplicates merge by Compare's matching rule, and each kept span says which window produced it.
* **One Discovery run per application:** its runs are the stitched ones (one per channel), so Runs, Compare, Review,
  the Scoreboard and the Map read the stitched set; the window scope joins the Map's row key.
* **Null:** each window draws its own null; the windows' draws are stitched the same way into the stitched run's.

Headless and self-contained: temp sqlite, synthetic coloured signals (AR(1), random walk, a loud stretch beside a
quiet one), spans of two days at 1 Hz at most.

    PYTHONIOENCODING=utf-8 python -m pytest tests/test_windowed_detection.py -q -p no:cacheprovider
"""

import importlib
import json
import os
import sys

import numpy as np
import pytest
from scipy.signal import lfilter

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import Working.config as cfg  # noqa: E402
from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working import run_groups as RG  # noqa: E402
from Working.config import HELD_OUT_RECORDING_FILE  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database import runs as R  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.discovery import detection_map as DM  # noqa: E402
from Working.discovery import fanout  # noqa: E402
from Working.execution import _recipe_prefix_hash, execute_recipe  # noqa: E402
from Working.recipes import canonical_json, make_recipe, short_hash  # noqa: E402

discover_adapters()

FS = 1.0
H = 3600
#: noise threshold: a 600 s baseline, then every stretch 4 sigma_n below the median for 30 s or more
NT = [{"stage": "preprocessing", "algorithm": "detrend", "params": {"mode": "rolling_mean", "window_s": 600.0}},
      {"stage": "detection", "algorithm": "noise_threshold",
       "params": {"k_sigma": 4.0, "direction": "below", "min_duration_s": 30.0, "merge_gap_s": 60.0}}]
#: the canonical drop detector (webui/server/templates.py, drop_detection_v1)
D1 = [{"stage": "preprocessing", "algorithm": "detrend", "params": {"mode": "rolling_mean_nearest", "window_s": 4916.67}},
      {"stage": "detection", "algorithm": "stage_encoding",
       "params": {"segment_seconds": 98.33, "same_fraction": 0.6, "slope_sigma": 8.0}},
      {"stage": "detection", "algorithm": "drop_detection", "params": {}}]
#: the canonical dehshibi_spikes (webui/server/templates.py): 3000 s wavelet pieces
DEHSHIBI = [{"stage": "preprocessing", "algorithm": "wavelet_transform", "params": {}},
            {"stage": "detection", "algorithm": "wavelet_summation", "params": {"row_to": 0.7586}},
            {"stage": "detection", "algorithm": "summation_threshold", "params": {}}]
NULL = {"method": "phase_randomize", "seed": 0}


def _w():
    """The module under test, imported per test so a missing module fails each test, not the collection."""
    return importlib.import_module("Working.discovery.windowed")


def _ar1(n, phi, sd, rng):
    return lfilter([1.0], [1.0, -phi], rng.standard_normal(n) * sd)


def _loud_beside_quiet(seed=3):
    """48 h at 1 Hz: hours 0-32 carry ten times the noise (AR(1), phi 0.97) of hours 32-48, where seven weak drops
    (8 x the quiet stretch's own sigma, three minutes each) sit every two hours. A whole-span sigma_n is set by the
    loud two-thirds, so its 4 sigma_n cut is far below the weak drops; a window inside the quiet stretch measures the
    quiet sigma and finds them."""
    rng = np.random.default_rng(seed)
    n = 48 * H
    x = _ar1(n, 0.97, 0.00005, rng)
    x[:32 * H] += _ar1(32 * H, 0.97, 0.0005, rng)
    sigma_q = 0.00005 / np.sqrt(1 - 0.97 ** 2)
    onsets = list(range(33 * H, 47 * H, 2 * H))
    for a in onsets:
        x[a:a + 180] -= 8 * sigma_q
    return x, onsets


def _drop(depth, fall_s=20, tau_s=300):
    return np.concatenate([-depth * (np.arange(fall_s) / fall_s), -depth * np.exp(-np.arange(6 * tau_s) / tau_s)])


def _drops_loud_beside_quiet(seed=3):
    """48 h: hours 0-28 carry five times the noise and a deep drop (0.2) every hour; hours 28-48 a weak drop (0.02)
    every hour. The drop detector's slope floor and depth gate are fitted to the span it is given: over the whole
    span the loud stretch sets both, and the weak drops fall under them."""
    rng = np.random.default_rng(seed)
    n = 48 * H
    x = _ar1(n, 0.97, 0.00005, rng)
    x[:28 * H] += _ar1(28 * H, 0.97, 0.00025, rng)
    for a in range(1 * H, 27 * H, H):
        d = _drop(0.2)
        x[a:a + len(d)] += d
    weak = list(range(29 * H, 47 * H, H))
    for a in weak:
        d = _drop(0.02)
        x[a:a + len(d)] += d
    return x, weak


def _recall(spans, onsets, tol=600):
    return sum(1 for a in onsets if any(s - tol <= a <= e for s, e in spans))


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A database with whatever recordings a test adds (`add`), the step cache in a temp folder."""
    db = str(tmp_path / "annotations.sqlite")
    init_db(db).close()
    monkeypatch.setattr(cfg, "STEP_CACHE_ROOT", str(tmp_path / "cache"))

    def add(x, name="syn.mat", channel=0, units="V"):
        npy = tmp_path / f"{name.replace('.', '_')}_CH{channel}.npy"
        np.save(npy, np.asarray(x, dtype=float))
        conn = init_db(db)
        try:
            return q.insert_recording(conn, name, channel, FS, len(x), 0, str(npy), units=units)
        finally:
            conn.close()

    return {"db": db, "add": add, "tmp": tmp_path}


def _plan(world, steps, ids, span, windows=None, draws=0, ceiling=10 ** 6):
    conn = init_db(world["db"])
    try:
        return fanout.plan(conn, steps=steps, recording_ids=ids, span=span, ceiling_s=ceiling,
                           null_draws=draws, surrogate=draws > 0, surrogate_params=(NULL if draws else None),
                           windows=windows)
    finally:
        conn.close()


def _start(world, plan, draws=0):
    return fanout.start(plan, db_path=world["db"], surrogate=draws > 0, surrogate_params=(NULL if draws else None),
                        surrogate_draws=(draws or None))


def _spans(conn, run_id):
    return [(int(d["start_idx"]), int(d["end_idx"])) for d in R.list_detections(conn, run_id)]


# ── the scope ───────────────────────────────────────────────────────────────

def test_the_scope_defaults_to_half_overlap_and_bounds_the_overlap():
    W = _w()
    s = W.normalize_scope({"window_s": 3600})
    assert s == {"kind": "windows", "window_s": 3600.0, "overlap_frac": 0.5, "fit": False}
    assert W.DEFAULT_OVERLAP == 0.5
    assert W.normalize_scope({"kind": "windows", "window_s": 600, "overlap_frac": 0.0})["overlap_frac"] == 0.0
    assert W.normalize_scope({"window_s": 600, "overlap_frac": 0.9})["overlap_frac"] == 0.9
    for bad in ({"window_s": 600, "overlap_frac": 0.95}, {"window_s": 600, "overlap_frac": -0.1},
                {"window_s": 0}, {"window_s": -5}, {"kind": "bands", "window_s": 600}, {}):
        with pytest.raises(ValueError):
            W.normalize_scope(bad)


def test_windows_start_every_step_and_the_last_ends_at_the_section_end():
    W = _w()
    spans = W.window_spans(1000, 11000, 3600, 0.5)
    assert spans[:4] == [(1000, 4600), (2800, 6400), (4600, 8200), (6400, 10000)]
    assert spans[-1] == (7400, 11000), "the last window is moved back to end at the section end, at full length"
    assert all(b - a == 3600 for a, b in spans), "every window has the same length: one scale"
    assert W.window_spans(0, 7200, 3600, 0.0) == [(0, 3600), (3600, 7200)]
    assert W.window_spans(0, 3600, 3600, 0.5) == [(0, 3600)]
    assert W.window_spans(0, 3599, 3600, 0.5) == [], "a section shorter than one window holds no window"


def test_the_cores_tile_the_section_once_and_each_lies_in_its_window():
    W = _w()
    for overlap in (0.0, 0.25, 0.5, 0.75, 0.9):
        spans = W.window_spans(500, 40500, 3600, overlap)
        cores = W.window_cores(spans, 500, 40500)
        assert len(cores) == len(spans)
        assert cores[0][0] == 500 and cores[-1][1] == 40500, "the first and last windows keep their outer edges"
        for (lo, hi), (lo2, _) in zip(cores, cores[1:]):
            assert hi == lo2, "no gap and no overlap between neighbouring cores"
        for (lo, hi), (a, b) in zip(cores, spans):
            assert a <= lo < hi <= b
    spans = W.window_spans(0, 14400, 3600, 0.5)
    assert W.window_cores(spans, 0, 14400)[1] == (2700, 4500), "a core boundary is the middle of the overlap"


# ── the bound ───────────────────────────────────────────────────────────────

def test_a_window_shorter_than_four_times_the_detrend_window_is_refused_naming_the_step():
    W = _w()
    why = W.bound_refusal(NT, FS, 600.0)
    assert why is not None
    assert "step 01" in why and "detrend" in why.lower() and "600" in why
    assert "40 min" in why, "the minimum, in words"
    assert W.bound_refusal(NT, FS, 2400.0) is None, "4 x 600 s is allowed"
    m = W.minimum_window(NT, FS)
    assert m["step"] == 0 and m["param"] == "window_s" and m["minimum_s"] == 2400.0 and m["kind"] == "context"
    d1 = W.minimum_window(D1, FS)
    assert d1["step"] == 0 and abs(d1["minimum_s"] - 4 * 4916.67) < 1e-6
    assert "step 01" in W.bound_refusal(D1, FS, 3600.0)


def test_a_block_that_cuts_its_input_into_pieces_needs_one_whole_piece():
    """dehshibi_spikes cuts its span into 3000 s pieces, each normalised on its own: an outer window's edge is one more
    piece boundary, so the minimum is one piece, and the researcher's 1-hour windows fit (round A_2, P3)."""
    W = _w()
    assert W.bound_refusal(DEHSHIBI, FS, 3600.0) is None
    m = W.minimum_window(DEHSHIBI, FS)
    assert m["kind"] == "piece" and m["minimum_s"] == 3000.0
    why = W.bound_refusal(DEHSHIBI, FS, 1800.0)
    assert why is not None and "step 01" in why and "3000" in why


def test_fitting_the_internal_windows_makes_a_different_chain():
    W = _w()
    steps, changes = W.fit_steps(NT, FS, 600.0)
    assert steps[0]["params"]["window_s"] == 150.0, "a quarter of the 10-minute window"
    assert steps[1] == NT[1]
    assert changes == [{"step": 0, "name": "preprocessing.detrend", "param": "window_s", "from": 600.0, "to": 150.0}]
    assert W.bound_refusal(steps, FS, 600.0) is None
    same, none = W.fit_steps(NT, FS, 3600.0)
    assert same == NT and none == [], "a window the chain already fits changes nothing"
    with pytest.raises(ValueError) as e:
        W.fit_steps(DEHSHIBI, FS, 5.0)              # 5 s pieces: under the block's own 10 s minimum
    assert "step 01" in str(e.value)


def test_the_plan_refuses_a_short_window_and_fits_it_when_asked(world):
    rid = world["add"](np.zeros(8 * H))
    plan = _plan(world, NT, [rid], (0, 8 * H), windows={"window_s": 600})
    assert not plan["runnable"]
    assert "step 01" in plan["reason"] and "fit" in plan["reason"].lower(), "the refusal says how to go on"
    assert plan["windows"]["minimum"]["minimum_s"] == 2400.0
    fitted = _plan(world, NT, [rid], (0, 8 * H), windows={"window_s": 600, "fit": True})
    assert fitted["runnable"], fitted["reason"]
    assert fitted["windows"]["fitted"][0]["to"] == 150.0
    assert fitted["recipe"]["steps"][0]["params"]["window_s"] == 150.0, "the scaled chain is the one recorded"


def test_a_section_shorter_than_one_window_is_refused(world):
    rid = world["add"](np.zeros(3 * H))
    plan = _plan(world, NT, [rid], (0, 3 * H), windows={"window_s": 4 * H})
    assert not plan["runnable"] and "shorter than one window" in plan["reason"]


# ── the plan's targets, and what does not change ─────────────────────────────

def test_each_window_is_one_target_per_channel_with_an_ordinary_recipe(world):
    a = world["add"](np.zeros(12 * H), channel=0)
    b = world["add"](np.zeros(12 * H), channel=1)
    plan = _plan(world, NT, [a, b], (0, 12 * H), windows={"window_s": 4 * H}, draws=1)
    assert plan["runnable"], plan["reason"]
    w = plan["windows"]
    assert w["per_channel"] == 5 and w["targets"] == 10 and plan["n_channels"] == 2
    assert w["scope"] == {"kind": "windows", "window_s": 14400.0, "overlap_frac": 0.5, "fit": False}
    assert plan["recipe"]["windows"] == w["scope"], "the scope is in the run's recipe"
    assert plan["recipe"]["fan_out"]["kind"] == "windows"
    assert len(plan["targets"]) == 10
    t = plan["targets"][6]
    assert t["recording_id"] == b and t["span"] == [7200, 21600] and t["window"]["index"] == 1
    per = fanout.target_recipe(plan["recipe"], 6, True)
    want = make_recipe(b, NT, span=(7200, 21600))
    want["surrogate"] = True
    assert per == want, "a window's run is the ordinary run over that window: cached and reused like any other"
    assert "windows" not in per and "fan_out" not in per


def test_non_windowed_recipes_and_targets_are_byte_identical():
    """The overnight RQ4 specs import only while every hash they carry reproduces: nothing windowed may leak into an
    ordinary recipe (the values were computed at 91d6c94, before P3)."""
    plain = make_recipe(7, NT, span=(0, 1000))
    ch = make_recipe(7, NT, span=(0, 1000), fan_out={"kind": "channels", "targets": [7, 8]})
    bd = make_recipe(7, NT, span=None, fan_out={"kind": "bands", "targets": [{"low_hz": 0.01, "high_hz": 0.1}]})
    assert short_hash(plain) == "90f50148"
    assert short_hash(ch) == "b6f3c310"
    assert short_hash(bd) == "e692fb34"
    assert short_hash(RG.materialize_target(ch, 1)) == "ffae48b9"
    assert short_hash(RG.materialize_target(bd, 0)) == "61ce4ce0"
    assert DM.steps_key(canonical_json(plain)) == "steps:888e0cb56e42"
    assert [_recipe_prefix_hash(plain, k, "V")[:12] for k in range(2)] == ["55eff12d7899", "90f50148b733"]
    for r in (plain, ch, bd, RG.materialize_target(ch, 1)):
        assert "windows" not in r


def test_a_channel_plan_carries_no_window_field(world):
    rid = world["add"](np.zeros(2 * H))
    plan = _plan(world, NT, [rid], (0, 2 * H), draws=1)
    assert "windows" not in plan["recipe"] and plan["recipe"]["fan_out"]["kind"] == "channels"
    assert plan.get("windows") is None
    assert "window" not in plan["targets"][0]
    assert short_hash(fanout.target_recipe(plan["recipe"], 0, True)) == short_hash(
        dict(make_recipe(rid, NT, span=(0, 2 * H)), surrogate=True))


def test_the_estimate_counts_windows_times_one_plus_draws(world, monkeypatch):
    W = _w()
    for name in ("preprocessing.detrend", "detection.noise_threshold"):
        monkeypatch.setattr(get_adapter(name), "estimate", lambda x, t, fs, **p: 1e-5 * len(x))
    rid = world["add"](np.zeros(12 * H))
    plan = _plan(world, NT, [rid], (0, 12 * H), windows={"window_s": 4 * H}, draws=2)
    assert plan["windows"]["per_channel"] == 5 and plan["windows"]["runs"] == 15
    per_window = plan["windows"]["per_window_s"]
    assert per_window == pytest.approx(2 * 1e-5 * 4 * H + W.RUN_OVERHEAD_S, rel=1e-6), \
        "one window costs the chain over its length plus the run's own bookkeeping"
    assert plan["estimate_s"] == pytest.approx(5 * (1 + 2) * per_window, rel=1e-6)


def test_an_uncosted_chain_in_many_windows_routes_by_its_run_overhead(world):
    """Most detection blocks declare no estimate, so their plan reads `unknown` and runs here. A windowed application
    is thousands of runs, and each run's own bookkeeping is a floor under its cost: over the ceiling, the floor alone
    sends it to the cluster."""
    W = _w()
    rid = world["add"](np.zeros(200 * H, dtype=np.float32))
    plan = _plan(world, NT, [rid], (0, 200 * H), windows={"window_s": H}, draws=20, ceiling=1200)
    w = plan["windows"]
    assert w["per_channel"] == 399 and w["runs"] == 399 * 21
    assert plan["estimate_s"] is None, "the blocks declare no estimate"
    assert w["overhead_s"] == pytest.approx(399 * 21 * W.RUN_OVERHEAD_S)
    assert plan["route"] == "cluster"
    small = _plan(world, NT, [rid], (0, 8 * H), windows={"window_s": 4 * H}, draws=1, ceiling=1200)
    assert small["route"] == "unknown", "a few windows stay a local run whose cost the blocks cannot say"


# ── stitching ───────────────────────────────────────────────────────────────

def _two_windows(spans0, spans1):
    return [{"index": 0, "span": (0, 100), "core": (0, 75), "spans": spans0},
            {"index": 1, "span": (50, 150), "core": (75, 150), "spans": spans1}]


def test_an_event_both_windows_saw_in_their_overlap_is_kept_once():
    W = _w()
    out = W.stitch(_two_windows([(60, 70, 1.0)], [(60, 70, 1.0)]))
    assert [(s["start"], s["end"]) for s in out["spans"]] == [(60, 70)]
    assert out["spans"][0]["window"] == 0 and out["spans"][0]["owner"] == 0 and out["spans"][0]["members"] == [0, 1]
    assert out["found"] == 2 and out["kept"] == 1 and out["duplicates"] == 1


def test_an_event_straddling_a_window_edge_is_found_once_and_whole():
    """Window 0 sees the event cut at its own end; window 1 sees all of it. Its onset is in window 0's core, so
    window 0 decides that it is there; window 1's view, not cut, is the extent kept."""
    W = _w()
    out = W.stitch(_two_windows([(70, 100, 2.0)], [(70, 120, 3.0)]))
    assert [(s["start"], s["end"]) for s in out["spans"]] == [(70, 120)]
    s = out["spans"][0]
    assert s["owner"] == 0 and s["window"] == 1 and s["score"] == 3.0


def test_duplicates_with_different_edges_merge_by_the_matching_rule():
    W = _w()
    # onsets 70 and 76 lie in different cores; IoU 0.73, the onset gap 6 within 0.25 x the duration
    out = W.stitch(_two_windows([(70, 98, 1.0)], [(76, 100, 1.0)]))
    assert out["kept"] == 1
    # far apart (IoU < 0.5): two events, each in its own core
    out = W.stitch(_two_windows([(60, 68, 1.0)], [(90, 99, 1.0)]))
    assert [(s["start"], s["end"]) for s in out["spans"]] == [(60, 68), (90, 99)]


def test_a_detection_outside_its_windows_core_that_the_owner_did_not_make_is_dropped():
    W = _w()
    out = W.stitch(_two_windows([(80, 90, 1.0)], []))
    assert out["spans"] == [] and out["outside"] == 1


def test_the_first_and_last_windows_keep_their_outer_edges():
    W = _w()
    out = W.stitch(_two_windows([(2, 10, 1.0)], [(140, 149, 1.0)]))
    assert [(s["start"], s["end"]) for s in out["spans"]] == [(2, 10), (140, 149)]


def test_the_rule_is_stated():
    W = _w()
    names = [r["name"] for r in W.RULES]
    assert {"core", "duplicates", "provenance", "refit"} <= set(names)
    text = " ".join(r["rule"] for r in W.RULES).lower()
    assert "onset" in text and "iou" in text and "own thresholds" in text
    assert "a quiet window finds weaker events than the whole-span run would" in W.TRADE_OFF


# ── end to end: one Discovery run, the stitched set ─────────────────────────

@pytest.fixture
def stitched(world):
    """noise_threshold over the loud-beside-quiet recording: the whole span, then 4 h windows at 50 % with one null
    draw per window."""
    x, onsets = _loud_beside_quiet()
    rid = world["add"](x)
    whole_plan = _plan(world, NT, [rid], (0, len(x)), draws=1)
    whole = _start(world, whole_plan, draws=1)
    plan = _plan(world, NT, [rid], (0, len(x)), windows={"window_s": 4 * H}, draws=1)
    assert plan["runnable"], plan["reason"]
    out = _start(world, plan, draws=1)
    return {"world": world, "rid": rid, "x": x, "onsets": onsets, "whole": whole, "plan": plan, "out": out}


def test_the_windowed_run_finds_the_weak_events_the_whole_span_misses(stitched):
    conn = init_db(stitched["world"]["db"])
    try:
        whole = _spans(conn, stitched["whole"]["run_ids"][0])
        win = _spans(conn, stitched["out"]["run_ids"][0])
    finally:
        conn.close()
    assert _recall(whole, stitched["onsets"]) <= 1, "the loud stretch sets the whole span's bar"
    assert _recall(win, stitched["onsets"]) >= 6, "a window inside the quiet stretch sets its own"


def test_one_run_per_channel_holds_the_stitched_set_with_no_duplicates(stitched):
    W = _w()
    out = stitched["out"]
    assert len(out["runs"]) == 1 and out["run_ids"] == [out["runs"][0]["run_id"]]
    row = out["runs"][0]
    assert row["windows"] == stitched["plan"]["windows"]["per_channel"] == 23
    conn = init_db(stitched["world"]["db"])
    try:
        run = R.get_run(conn, row["run_id"])
        assert (int(run["span_start"]), int(run["span_end"])) == (0, len(stitched["x"]))
        assert run["status"] == "completed" and run["surrogate_of_run_id"] is None
        cfg_json = json.loads(R.get_config(conn, run["config_id"])["config_json"])
        assert cfg_json["windows"]["window_s"] == 14400.0 and cfg_json["windows"]["overlap_frac"] == 0.5
        dets = R.list_detections(conn, row["run_id"])
        spans = [(int(d["start_idx"]), int(d["end_idx"])) for d in dets]
        assert spans == sorted(spans)
        from Working.discovery.matching import spans_match
        for i, a in enumerate(spans):
            for b in spans[i + 1:]:
                assert not spans_match(a, b) and not spans_match(b, a), f"{a} and {b} are the same event twice"
        for d in dets:
            meta = json.loads(d["meta_json"])
            assert 0 <= meta["window"] < 23 and "windowRunId" in meta, "each kept span names its window"
        raw = sum(len(R.list_detections(conn, wid)) for wid in row["window_run_ids"])
        assert raw > len(spans), "the windows overlap, so the raw sum counts some events twice"
        prov = conn.execute("SELECT * FROM stitched_windows WHERE run_id = ? ORDER BY window_index",
                            (row["run_id"],)).fetchall()
        assert [p["window_index"] for p in prov] == list(range(23))
        assert [int(p["window_run_id"]) for p in prov] == row["window_run_ids"]
        assert sum(int(p["kept"]) for p in prov) == len(spans)
    finally:
        conn.close()
    assert W.normalize_scope(stitched["plan"]["windows"]["scope"])["window_s"] == 14400.0


def test_each_window_draws_its_own_null_and_the_stitched_null_is_linked(stitched):
    row = stitched["out"]["runs"][0]
    conn = init_db(stitched["world"]["db"])
    try:
        assert len(row["surrogate_run_ids"]) == 1
        draw = R.get_run(conn, row["surrogate_run_ids"][0])
        assert int(draw["surrogate_of_run_id"]) == row["run_id"] and draw["status"] == "completed"
        for wid in row["window_run_ids"]:
            n = conn.execute("SELECT COUNT(*) FROM runs WHERE surrogate_of_run_id = ? AND status = 'completed'",
                             (wid,)).fetchone()[0]
            assert n == 1, "every window drew its own null"
        summary = RG.null_summary(conn, row["run_id"])
        assert summary["null_draws"] == 1 and summary["method"] == "phase_randomize"
    finally:
        conn.close()


def test_reapplying_the_same_scope_reuses_every_window_and_computes_nothing(stitched, monkeypatch):
    spec = get_adapter("detection.noise_threshold")

    def boom(*a, **k):
        raise AssertionError("a window was computed again")

    monkeypatch.setattr(spec, "run", boom)
    plan = _plan(stitched["world"], NT, [stitched["rid"]], (0, len(stitched["x"])), windows={"window_s": 4 * H},
                 draws=1)
    assert plan["estimate_s"] == 0.0, "every window and its draw is already run: the plan says nothing is left"
    again = _start(stitched["world"], plan, draws=1)
    assert again["run_ids"] == stitched["out"]["run_ids"], "the stitched run is the same run"
    assert again["reused"] == again["run_ids"]
    assert again["runs"][0]["window_run_ids"] == stitched["out"]["runs"][0]["window_run_ids"]


def test_per_window_fitted_values_are_recorded(stitched):
    row = stitched["out"]["runs"][0]
    conn = init_db(stitched["world"]["db"])
    try:
        fits = {int(r["run_id"]): json.loads(r["fitted_json"]) for r in conn.execute("SELECT * FROM window_fits")}
    finally:
        conn.close()
    sigmas = [fits[w]["detection.noise_threshold"]["sigma"] for w in row["window_run_ids"]]
    assert len(set(round(s, 9) for s in sigmas)) > 5, "each window measured its own noise"
    assert max(sigmas) > 5 * min(sigmas), "the loud windows' sigma is not the quiet windows'"


def test_a_stitched_recipe_is_not_run_as_one_span(stitched):
    conn = init_db(stitched["world"]["db"])
    try:
        run = R.get_run(conn, stitched["out"]["run_ids"][0])
        recipe = R.load_recipe(conn, run["config_id"])
    finally:
        conn.close()
    with pytest.raises(ValueError) as e:
        execute_recipe(recipe, db_path=stitched["world"]["db"], force=True)
    assert "window" in str(e.value)


# ── the map ─────────────────────────────────────────────────────────────────

def _discovery_rows(conn, rows):
    conn.execute("INSERT INTO discovery_sessions (name, source_file, channels_json, created_at, updated_at) "
                 "VALUES ('s', 'syn.mat', '[\"CH1\"]', '2026-10-18T00:00:00', '2026-10-18T00:00:00')")
    sid = conn.execute("SELECT MAX(id) FROM discovery_sessions").fetchone()[0]
    for key, label, params in rows:
        conn.execute("INSERT INTO discovery_runs (session_id, run_key, kind, label, template_name, params_json, "
                     "status, created_at, updated_at) VALUES (?, ?, 'template', ?, 'noise_threshold', ?, 'done', "
                     "'2026-10-18T00:00:00', '2026-10-18T00:00:00')", (sid, key, label, json.dumps(params)))
    conn.commit()


def test_the_map_reads_a_windowed_application_as_its_own_row_without_double_counting(stitched):
    out = stitched["out"]
    conn = init_db(stitched["world"]["db"])
    try:
        scope = stitched["plan"]["windows"]["scope"]
        _discovery_rows(conn, [("whole", "noise_threshold", {"run_ids": stitched["whole"]["run_ids"]}),
                               ("win", "noise_threshold · 4 h windows · 50 %",
                                {"run_ids": out["run_ids"], "windows": {"scope": scope}})])
        m = DM.dataset_map(conn)
        machine = [r for r in m["rows"] if r["kind"] != "human"]
        assert len(machine) == 2, "the windowed application and the whole-span run are two rows"
        win = next(r for r in machine if r["windows"])
        assert "4 h windows" in win["label"] and "50 %" in win["label"]
        cells = m["datasets"][0]["cells"]
        n_stitched = len(R.list_detections(conn, out["run_ids"][0]))
        assert cells[win["key"]]["CH1"]["count"] == n_stitched, "the cell counts the stitched set, once"
    finally:
        conn.close()


def test_the_row_key_takes_the_window_scope():
    plain = make_recipe(7, NT, span=(0, 1000))
    a = dict(plain, windows={"kind": "windows", "window_s": 3600.0, "overlap_frac": 0.5, "fit": False})
    b = dict(plain, windows={"kind": "windows", "window_s": 600.0, "overlap_frac": 0.5, "fit": False})
    c = dict(plain, windows={"kind": "windows", "window_s": 3600.0, "overlap_frac": 0.25, "fit": False})
    keys = {DM.steps_key(canonical_json(r)) for r in (plain, a, b, c)}
    assert len(keys) == 4, "each scale is its own version of the algorithm"
    assert DM.steps_key(canonical_json(plain)) == "steps:888e0cb56e42"
    moved = dict(a, recording_id=8, span=[5, 99])
    assert DM.steps_key(canonical_json(moved)) == DM.steps_key(canonical_json(a)), "recording and span still stripped"


# ── noise ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("colour", ["ar1", "random_walk"])
def test_on_coloured_noise_the_windowed_run_finds_no_more_than_its_null(world, colour):
    rng = np.random.default_rng(11)
    n = 24 * H
    x = _ar1(n, 0.97, 0.0001, rng) if colour == "ar1" else np.cumsum(rng.standard_normal(n) * 0.0001)
    rid = world["add"](x, name=f"{colour}.mat")
    plan = _plan(world, NT, [rid], (0, n), windows={"window_s": 4 * H}, draws=3)
    out = _start(world, plan, draws=3)
    conn = init_db(world["db"])
    try:
        s = RG.null_summary(conn, out["run_ids"][0])
    finally:
        conn.close()
    assert s["null_draws"] == 3
    assert s["found"] <= s["null_expects"] + 2.0 * np.sqrt(s["null_expects"]) + 2.0, s


# ── drop detection, the held-out lock, dehshibi ──────────────────────────────

def test_drop_detection_in_windows_finds_the_weak_drops_the_whole_span_misses(world):
    x, weak = _drops_loud_beside_quiet()
    rid = world["add"](x)
    whole = _start(world, _plan(world, D1, [rid], (0, len(x))))
    plan = _plan(world, D1, [rid], (0, len(x)), windows={"window_s": 6 * H})
    assert plan["runnable"], plan["reason"]
    win = _start(world, plan)
    conn = init_db(world["db"])
    try:
        w_spans = _spans(conn, win["run_ids"][0])
        assert _recall(_spans(conn, whole["run_ids"][0]), weak) <= 2
        assert _recall(w_spans, weak) >= 9, "the slope floor and depth gate, fitted per window, let them through"
    finally:
        conn.close()


def test_a_windowed_plan_on_the_held_out_recording_follows_the_lock(world):
    from Working.registration.settings import HELD_OUT_ON_KEY, HELD_OUT_PAGE, held_out_state, put_settings

    rid = world["add"](np.zeros(8 * H), name=HELD_OUT_RECORDING_FILE)
    locked = _plan(world, NT, [rid], (0, 8 * H), windows={"window_s": 4 * H})
    assert not locked["runnable"] and "held out" in locked["reason"]
    conn = init_db(world["db"])
    try:
        st = held_out_state(conn)
        put_settings(conn, HELD_OUT_PAGE, {HELD_OUT_ON_KEY: False}, actor="test", confirm_name=st["name"])
    finally:
        conn.close()
    unlocked = _plan(world, NT, [rid], (0, 8 * H), windows={"window_s": 4 * H})
    assert unlocked["runnable"], unlocked["reason"]
    assert unlocked["windows"]["per_channel"] == 3


def test_dehshibi_runs_in_one_hour_windows_where_the_whole_span_is_refused(world):
    rid = world["add"](np.zeros(100 * H))                          # 360,000 samples: over the scalogram's cap
    whole = _plan(world, DEHSHIBI, [rid], (0, 100 * H))
    assert whole["memory_capped"], "the whole span is over the wavelet transform's 320,000-sample memory cap"
    plan = _plan(world, DEHSHIBI, [rid], (0, 100 * H), windows={"window_s": H})
    assert plan["runnable"], plan["reason"]
    assert not plan["memory_capped"], "a 1-hour window (3,600 samples) is far inside it"
    assert plan["windows"]["per_channel"] == 199


def test_dehshibi_one_hour_windows_run_and_stitch(world):
    rng = np.random.default_rng(5)
    x = _ar1(4 * H, 0.97, 0.0001, rng)
    for a in (2000, 7000, 11000):
        x[a:a + 120] -= 0.004
    rid = world["add"](x)
    plan = _plan(world, DEHSHIBI, [rid], (0, len(x)), windows={"window_s": H})
    out = _start(world, plan)
    assert out["runs"][0]["windows"] == 7
    conn = init_db(world["db"])
    try:
        run = R.get_run(conn, out["run_ids"][0])
        assert run["status"] == "completed"
        assert all(R.get_run(conn, w)["status"] == "completed" for w in out["runs"][0]["window_run_ids"])
    finally:
        conn.close()
