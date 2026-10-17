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


def test_every_preprocessing_and_detection_block_says_whether_it_has_an_internal_window():
    """The bound reads a table, not the parameter names: a new block that reads a stretch of signal around each point
    and is in neither list would let a window shorter than its own through without a word."""
    from Adapters.registry import list_adapters

    W = _w()
    names = {s.name for s in list_adapters()}
    known = set(W.INTERNAL_WINDOWS) | set(W.NO_INTERNAL_WINDOW)
    missing = sorted(n for n in names if n.split(".")[0] in ("preprocessing", "detection") and n not in known)
    assert not missing, f"classify these in Working/discovery/windowed.py (INTERNAL_WINDOWS or NO_INTERNAL_WINDOW): {missing}"
    assert not (set(W.INTERNAL_WINDOWS) & set(W.NO_INTERNAL_WINDOW))
    for name, entries in W.INTERNAL_WINDOWS.items():
        spec = get_adapter(name)
        for e in entries:
            if not e["param"].startswith("(") and e["unit"] != "exemplar":
                assert e["param"] in {p.name for p in spec.params}, f"{name} has no parameter {e['param']}"


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


def test_running_a_short_window_as_it_is_is_an_explicit_choice_the_run_says(world):
    """The third answer to the bound (the researcher's decision, RQ4b): keep the chain as it is in a window shorter
    than it allows. Only when asked; the plan and the run carry the bound's warning, naming the step."""
    W = _w()
    assert W.normalize_scope({"window_s": 600, "allow_short": True})["allow_short"] is True
    assert "allow_short" not in W.normalize_scope({"window_s": 600}), "never a default"
    assert "allow_short" not in W.normalize_scope({"window_s": 600, "allow_short": True, "fit": True}), "fit wins"
    rid = world["add"](np.zeros(8 * H))
    plan = _plan(world, NT, [rid], (0, 8 * H), windows={"window_s": 600, "allow_short": True})
    assert plan["runnable"], plan["reason"]
    w = plan["windows"]
    assert w["warning"] and "step 01" in w["warning"] and "distorted" in w["warning"]
    assert plan["recipe"]["steps"] == make_recipe(rid, NT)["steps"], "the chain as it is, not fitted"
    assert plan["recipe"]["windows"]["allow_short"] is True, "and the choice is in the run's recipe"
    assert w["fitted"] == [] and w["label"].endswith("as is, warned")
    assert "run it as it is" in W.bound_refusal(NT, FS, 600.0), "the refusal names all three ways on"


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
    """The core rule as first built: the window whose core holds the onset decides. (The rescue, below, keeps such a
    view when that window found nothing there at all.)"""
    W = _w()
    out = W.stitch(_two_windows([(80, 90, 1.0)], []), rescue=False)
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

#: a sensitive cut (2.5 sigma_n, 10 s), so pure noise gives the windows something to find and the comparison with
#: the null is not 0 against 0
SENSITIVE = [NT[0], {"stage": "detection", "algorithm": "noise_threshold",
                     "params": {"k_sigma": 2.5, "direction": "below", "min_duration_s": 10.0, "merge_gap_s": 10.0}}]


@pytest.mark.parametrize("colour", ["ar1", "random_walk"])
def test_on_coloured_noise_the_windowed_run_finds_no_more_than_its_null(world, colour):
    rng = np.random.default_rng(11)
    n = 24 * H
    x = _ar1(n, 0.97, 0.0001, rng) if colour == "ar1" else np.cumsum(rng.standard_normal(n) * 0.0001)
    rid = world["add"](x, name=f"{colour}.mat")
    plan = _plan(world, SENSITIVE, [rid], (0, n), windows={"window_s": 4 * H}, draws=3)
    out = _start(world, plan, draws=3)
    conn = init_db(world["db"])
    try:
        s = RG.null_summary(conn, out["run_ids"][0])
        raw = sum(len(R.list_detections(conn, w)) for w in out["runs"][0]["window_run_ids"])
    finally:
        conn.close()
    assert s["null_draws"] == 3 and s["null_expects"] >= 10, "the noise gives the cut something to find"
    assert s["found"] <= s["null_expects"] + 2.0 * np.sqrt(s["null_expects"]) + 2.0, s
    assert raw > s["found"], "the raw windows count overlapping events twice; the stitched set does not"


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
    _start(world, unlocked)
    conn = init_db(world["db"])
    try:
        put_settings(conn, HELD_OUT_PAGE, {HELD_OUT_ON_KEY: True}, actor="test", confirm_name=held_out_state(conn)["name"])
    finally:
        conn.close()
    from Working.execution import HeldOutRecordingLocked
    with pytest.raises(HeldOutRecordingLocked):
        _start(world, unlocked)              # every window is reused, and still the lock is read


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


# ── what thousands of window runs cost every database open ───────────────────

def test_init_db_does_not_rescan_every_run_for_legacy_rows_on_every_open(world, monkeypatch):
    """A windowed application writes thousands of runs, and `init_db` scanned every spanned run's detections for
    legacy (span-relative) rows on every open — once per window run. After the first scan in a process only the rows
    written since are looked at, and a legacy row written since is still migrated."""
    from Working.database import schema as S

    db = world["db"]
    rid = world["add"](np.zeros(10 * H))
    conn = init_db(db)
    try:
        cfg_id, _ = R.get_or_create_config(conn, make_recipe(rid, NT, span=(0, 600)))
        for k in range(200):
            run = R.insert_run(conn, cfg_id, rid, 1800 * (k + 1), 1800 * (k + 1) + 3600, status="completed")
            R.insert_detection(conn, run, 1800 * (k + 1) + 10, 1800 * (k + 1) + 20)
    finally:
        conn.close()
    calls = []
    real = S.migrate_legacy_detections
    monkeypatch.setattr(S, "migrate_legacy_detections", lambda c: calls.append(1) or real(c))
    init_db(db).close()
    init_db(db).close()
    assert calls == [], "rows written since the last scan are absolute: nothing for the migration to do"
    conn = init_db(db)
    try:
        legacy = R.insert_run(conn, cfg_id, rid, 1_000_000, 1_007_200, status="completed")
        det = R.insert_detection(conn, legacy, 2_468, 2_540)
    finally:
        conn.close()
    conn = init_db(db)
    try:
        assert calls == [1], "a row below its run's span_start is a legacy row: the full migration runs"
        row = conn.execute("SELECT start_idx FROM detections WHERE id = ?", (det,)).fetchone()
        assert int(row[0]) == 2_468 + 1_000_000
    finally:
        conn.close()


# ── the fix round (critic, 2026-10-18): the stitch at every overlap ─────────

def _views(event, spans):
    """What each window sees of one event: the event clipped to the window, as that window's own detection."""
    s, e = event
    return [[(max(s, a), min(e, b), 1.0)] if min(e, b) > max(s, a) else [] for a, b in spans]


def _stitch_events(events, n=2000, window=200, overlap=0.0, **kw):
    W = _w()
    spans = W.window_spans(0, n, window, overlap)
    cores = W.window_cores(spans, 0, n)
    per = [[] for _ in spans]
    for ev in events:
        for k, v in enumerate(_views(ev, spans)):
            per[k] += v
    wins = [{"index": k, "span": sp, "core": co, "spans": sorted(per[k])}
            for k, (sp, co) in enumerate(zip(spans, cores))]
    return W.stitch(wins, **kw)


def test_two_halves_cut_at_one_boundary_at_zero_overlap_are_one_event():
    """M2: at 0 % overlap each core is its whole window, so both halves of an event straddling a boundary start in
    their own window's core; IoU 0 never matched them, and the event was counted twice."""
    W = _w()
    wins = [{"index": 0, "span": (0, 100), "core": (0, 100), "spans": [(80, 100, 1.0)]},
            {"index": 1, "span": (100, 200), "core": (100, 200), "spans": [(100, 130, 2.0)]}]
    out = W.stitch(wins)
    assert [(x["start"], x["end"]) for x in out["spans"]] == [(80, 130)], "one event, the union of its halves"
    assert out["spans"][0]["cut"] is True and out["spans"][0]["merged"] is True
    assert out["kept"] == 1 and out["duplicates"] == 1 and out["merged"] == 1


@pytest.mark.parametrize("overlap", [0.0, 0.25, 0.5, 0.75, 0.9])
def test_every_event_is_found_exactly_once_and_whole_at_every_overlap(overlap):
    """Events of 30-150 samples at seeded places, many across a window boundary, some longer than the overlap; each
    window reports the event clipped to itself. One kept span per event, its extent the whole event (a window that
    held it whole, or its pieces joined), and no two kept spans overlapping."""
    rng = np.random.default_rng(int(overlap * 100) + 1)
    events, t = [], 10
    while t < 1850:
        d = int(rng.integers(30, 150))
        events.append((t, t + d))
        t += d + int(rng.integers(5, 60))
    out = _stitch_events(events, overlap=overlap)
    kept = [(x["start"], x["end"]) for x in out["spans"]]
    for ev in events:
        hits = [k for k in kept if k[0] < ev[1] and ev[0] < k[1]]
        assert hits == [ev], f"overlap {overlap}: event {ev} kept as {hits}"
    assert len(kept) == len(events)


def test_a_cut_view_inside_a_whole_one_is_the_same_event():
    """m1: window 0's view is cut at its end and covers less than half of window 1's whole view (IoU 0.375), so IoU
    alone left the whole view outside its core and kept the cut one. A cut view inside another window's view, its
    uncut edge where that view's is, is the same event: kept once, as the view no edge cut."""
    W = _w()
    out = W.stitch(_two_windows([(70, 100, 1.0)], [(70, 150, 2.0)]))
    assert [(x["start"], x["end"]) for x in out["spans"]] == [(70, 150)]
    assert out["spans"][0]["cut"] is False and out["spans"][0]["owner"] == 0 and out["kept"] == 1


def test_two_detections_of_one_window_are_never_one_event():
    """The nit: a window's two near-duplicate detections were merged through a third window's detection that matched
    both (a transitive cluster), and kept apart without it. An event holds at most one detection from each window,
    paired best match first, as Compare pairs one to one."""
    W = _w()
    alone = W.stitch(_two_windows([(60, 80, 1.0), (62, 82, 1.0)], []))
    with_third = W.stitch(_two_windows([(60, 80, 1.0), (62, 82, 1.0)], [(61, 81, 1.0)]))
    assert alone["kept"] == 2
    assert with_third["kept"] == 2, [(x["start"], x["end"], x["members"]) for x in with_third["spans"]]
    assert sorted(len(x["members"]) for x in with_third["spans"]) == [1, 2]


def _three_windows(spans0, spans1, spans2):
    return [{"index": 0, "span": (0, 100), "core": (0, 75), "spans": spans0},
            {"index": 1, "span": (50, 150), "core": (75, 125), "spans": spans1},
            {"index": 2, "span": (100, 200), "core": (125, 200), "spans": spans2}]


def test_an_event_its_owner_missed_is_kept_from_the_neighbour_that_saw_it_whole():
    """m2, the rescue: window 0's core holds onset 60 and window 0 found nothing there; window 1 saw the event whole,
    10 samples inside its own edge. Kept once, flagged. Not when that view lies within the edge margin (the chain's
    context windows distort it there), and not when the owner found something there: it decided."""
    W = _w()
    out = W.stitch(_three_windows([], [(60, 70, 1.0)], []), rescue=True, edge_margin=5)
    assert [(x["start"], x["end"]) for x in out["spans"]] == [(60, 70)]
    x = out["spans"][0]
    assert x["rescued"] is True and x["window"] == 1 and x["owner"] == 0
    assert out["rescued"] == 1 and out["outside"] == 0
    assert W.stitch(_three_windows([], [(60, 70, 1.0)], []), rescue=True, edge_margin=20)["spans"] == []
    owner_saw = W.stitch(_three_windows([(40, 66, 1.0)], [(60, 70, 1.0)], []), rescue=True, edge_margin=5)
    assert [(x["start"], x["end"]) for x in owner_saw["spans"]] == [(40, 66)], "the owner's own detection, once"
    assert W.stitch(_three_windows([], [(60, 70, 1.0)], []), rescue=False)["spans"] == []
    cut = W.stitch(_three_windows([], [(50, 70, 1.0)], []), rescue=True, edge_margin=0)
    assert cut["spans"] == [], "a view a window edge cut is never rescued"


def test_the_stitch_rule_states_the_joins_the_rescue_and_the_nulls_scale():
    W = _w()
    text = " ".join(r["rule"] for r in W.RULES)
    assert "within one scale, not across scales" in text, "m3: x null compares like with like within one scale"
    assert ("found nothing" in text) is bool(W.RESCUE), "the rescue is stated exactly when it is the rule"
    assert "abut" in text and "one detection from each window" in text
    assert W.STITCH_VERSION >= 2, "stitched runs made by the first rule are not reused as this one's"


# the critic's probe (24 h at 1 Hz): AR(1) noise and a drift, a loud 6 h, 2-min dips and 8-min drops, some weak; at
# 0 % overlap one drop across a window boundary was kept twice
def _probe_signal(n=24 * H, seed=7):
    rng = np.random.default_rng(seed)
    x = lfilter([1.0], [1.0, -0.97], rng.standard_normal(n) * 0.0005)
    x += 0.01 * np.sin(np.linspace(0, 4 * np.pi, n))
    x[10 * H:16 * H] += lfilter([1.0], [1.0, -0.97], rng.standard_normal(6 * H) * 0.002)
    truth, t = [], 300
    while t < n - 1200:
        kind = rng.choice(["dip", "drop"], p=[0.6, 0.4])
        d = 120 if kind == "dip" else 480
        depth = float(rng.choice([0.02, 0.04]))
        x[t:t + d] -= depth * np.hanning(d)
        truth.append((int(t), int(t + d)))
        t += int(d + rng.integers(300, 1800))
    return x, truth


@pytest.fixture(scope="module")
def probe_world(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("probe")
    db = str(tmp / "annotations.sqlite")
    init_db(db).close()
    x, truth = _probe_signal()
    npy = tmp / "probe_CH0.npy"
    np.save(npy, x)
    conn = init_db(db)
    try:
        rid = q.insert_recording(conn, "probe.mat", 0, FS, len(x), 0, str(npy), units="V")
    finally:
        conn.close()
    return {"db": db, "rid": rid, "n": len(x), "truth": truth, "cache": str(tmp / "cache")}


@pytest.mark.parametrize("overlap", [0.0, 0.25, 0.5, 0.75, 0.9])
def test_on_a_real_chain_no_event_is_kept_twice_at_any_overlap(probe_world, overlap, monkeypatch):
    monkeypatch.setattr(cfg, "STEP_CACHE_ROOT", probe_world["cache"])
    NT600 = [NT[0], NT[1]]
    conn = init_db(probe_world["db"])
    try:
        plan = fanout.plan(conn, steps=NT600, recording_ids=[probe_world["rid"]], span=(0, probe_world["n"]),
                           ceiling_s=10 ** 6, windows={"window_s": H, "overlap_frac": overlap})
    finally:
        conn.close()
    out = fanout.start(plan, db_path=probe_world["db"])
    conn = init_db(probe_world["db"])
    try:
        spans = _spans(conn, out["run_ids"][0])
    finally:
        conn.close()
    twice = [ev for ev in probe_world["truth"] if sum(1 for s, e in spans if s < ev[1] and ev[0] < e) > 1]
    assert twice == [], f"overlap {overlap}: kept twice: {twice}"
    for i, a in enumerate(spans):
        for b in spans[i + 1:]:
            assert not (a[0] < b[1] and b[0] < a[1]), f"overlap {overlap}: {a} and {b} overlap"


# ── the fix round: an opt-in that changes nothing is not recorded ───────────

def test_an_opt_in_that_changes_nothing_is_the_same_run(world):
    """m5: a 4-hour window breaks no bound of a 600 s detrend chain, so "fit" and "run as it is" change nothing. They
    no longer label the run or hash its stitched run apart: the three are one computation, one stitched run."""
    rid = world["add"](np.random.default_rng(3).standard_normal(8 * H) * 0.001)
    plans = [_plan(world, NT, [rid], (0, 8 * H), windows=dict({"window_s": 4 * H}, **extra))
             for extra in ({}, {"fit": True}, {"allow_short": True})]
    for p in plans:
        assert p["windows"]["scope"] == {"kind": "windows", "window_s": 14400.0, "overlap_frac": 0.5, "fit": False}
        assert p["windows"]["label"] == "4 h windows · 50 %"
        assert p["windows"]["fitted"] == [] and p["windows"]["warning"] is None
    outs = [_start(world, p) for p in plans]
    assert outs[1]["run_ids"] == outs[0]["run_ids"] == outs[2]["run_ids"], "one stitched run, reused"
    assert outs[1]["reused"] == outs[1]["run_ids"] and outs[2]["reused"] == outs[2]["run_ids"]
    fitted = _plan(world, NT, [rid], (0, 8 * H), windows={"window_s": 600, "fit": True})
    assert fitted["windows"]["scope"]["fit"] is True and fitted["windows"]["label"].endswith("· fitted")
    warned = _plan(world, NT, [rid], (0, 8 * H), windows={"window_s": 600, "allow_short": True})
    assert warned["windows"]["scope"].get("allow_short") is True
    assert warned["windows"]["label"].endswith("· as is, warned")


def test_a_fitted_chain_stitches_to_the_same_run_however_it_was_reached(world):
    """m5: the stitched run is the computation — the chain it ran and the windows — not the tick that produced the
    chain: the 600 s chain fitted to 10-minute windows and the same chain written with a 150 s detrend are one run."""
    rid = world["add"](np.random.default_rng(4).standard_normal(4 * H) * 0.001)
    by_fit = _start(world, _plan(world, NT, [rid], (0, 4 * H), windows={"window_s": 600, "fit": True}))
    by_hand = [dict(NT[0], params=dict(NT[0]["params"], window_s=150.0)), NT[1]]
    plan = _plan(world, by_hand, [rid], (0, 4 * H), windows={"window_s": 600})
    assert plan["windows"]["scope"]["fit"] is False
    again = _start(world, plan)
    assert again["run_ids"] == by_fit["run_ids"] and again["reused"] == again["run_ids"]


# ── the fix round: the windowed plan at the sweep's scale ───────────────────

def test_a_window_hash_reads_the_same_as_the_recipe_hash_over_that_span():
    """m10: the plan hashed every window's whole recipe (the chain's canonical JSON, per window and per draw); it
    hashes the chain once and the span per window. The two agree to the last character, real runs and draws."""
    W = _w()
    base = dict(make_recipe(7, D1, span=(0, 3600)), surrogate=True)
    spans = W.window_spans(0, 200000, 3600, 0.5)
    real = W.window_hasher(base)
    assert [real(sp) for sp in spans] == [short_hash(W.with_span(base, sp)) for sp in spans]
    assert [real.canonical(sp) for sp in spans[:20]] == [canonical_json(W.with_span(base, sp)) for sp in spans[:20]]
    for p in ({"method": "phase_randomize", "seed": 3}, {"method": "block_shuffle", "seed": 0, "block_s": 44.0}):
        draw = W.window_hasher(RG.surrogate_recipe(W.with_span(base, spans[0]), p))
        assert [draw(sp) for sp in spans] == [short_hash(RG.surrogate_recipe(W.with_span(base, sp), p))
                                              for sp in spans]


def test_planning_exporting_and_replanning_hash_the_chain_per_channel_not_per_window(world, monkeypatch):
    """m10: 8,651 windows a channel at 10 minutes over 721 h took the plan most of a minute (16 channels), the export
    and the import's re-plan as long again — every window's recipe and every draw's serialised and hashed. Now each
    channel's chain is serialised a handful of times, whatever its number of windows."""
    import Working.recipes as RC
    from Working.discovery import chain_job

    n = 900_300                                                     # 3,000 ten-minute windows at 50 %
    npy = world["tmp"] / "long.npy"
    np.save(npy, np.zeros(n, dtype=np.float32))
    conn = init_db(world["db"])
    try:
        ids = [q.insert_recording(conn, "long.mat", ch, FS, n, 0, str(npy), units="V") for ch in range(2)]
    finally:
        conn.close()
    calls = {"n": 0}
    real = RC.canonical_json

    def counted(recipe):
        calls["n"] += 1
        return real(recipe)

    monkeypatch.setattr(RC, "canonical_json", counted)
    conn = init_db(world["db"])
    try:
        plan = fanout.plan(conn, steps=NT, recording_ids=ids, span=None, ceiling_s=1200, null_draws=1,
                           surrogate=True, surrogate_params=NULL, windows={"window_s": 600, "fit": True})
        assert plan["windows"]["per_channel"] == 3000
        planned = calls["n"]
        spec = chain_job.build_spec(conn, plan, label="long", null={"paired": True, "params": NULL, "draws": 1})
        exported = calls["n"] - planned
        chain_job.local_plan(conn, spec, ceiling_s=1200)
        replanned = calls["n"] - planned - exported
    finally:
        conn.close()
    assert planned < 100 and exported < 100 and replanned < 200, (planned, exported, replanned)


# ── the fix round: a database put back at the same path ─────────────────────

@pytest.mark.parametrize("restore", ["moved over", "copied over"])
def test_a_database_restored_over_its_path_is_scanned_for_legacy_rows_again(tmp_path, restore):
    """m9: the incremental legacy scan remembered a high-water mark per path. A backup put back at that path — moved
    over it, or copied over it — whose legacy row lies below the mark was never scanned: the mark said the rows up to
    it were seen. The mark is kept per file and checked against the row it names."""
    import shutil

    a = str(tmp_path / "a" / "annotations.sqlite")
    os.makedirs(os.path.dirname(a))
    conn = init_db(a)
    try:
        rec = q.insert_recording(conn, "x.mat", 0, FS, 10 ** 6, 0, "x.npy")
        cfg_id, _ = R.get_or_create_config(conn, make_recipe(rec, NT, span=(0, 600)))
        run = R.insert_run(conn, cfg_id, rec, 0, 600, status="completed")
        for k in range(3):
            R.insert_detection(conn, run, 10 + k, 20 + k)
    finally:
        conn.close()
    init_db(a).close()                                    # this process has scanned a: its mark is detection 3
    b = str(tmp_path / "b" / "annotations.sqlite")
    os.makedirs(os.path.dirname(b))
    conn = init_db(b)
    try:
        rec = q.insert_recording(conn, "x.mat", 0, FS, 10 ** 6, 0, "x.npy")
        cfg_id, _ = R.get_or_create_config(conn, make_recipe(rec, NT, span=(0, 600)))
        legacy = R.insert_run(conn, cfg_id, rec, 500_000, 507_200, status="completed")
        R.insert_detection(conn, legacy, 2_468, 2_540)    # span-relative: a backup from before 2026-09-21
        plain = R.insert_run(conn, cfg_id, rec, 0, 600, status="completed")
        for k in range(5):
            R.insert_detection(conn, plain, 100 + k, 110 + k)
    finally:
        conn.close()
    if restore == "moved over":
        shutil.copyfile(b, a + ".restore")
        os.replace(a + ".restore", a)
    else:
        shutil.copyfile(b, a)
    conn = init_db(a)
    try:
        row = conn.execute("SELECT start_idx FROM detections WHERE id = 1").fetchone()
        assert int(row[0]) == 2_468 + 500_000, "the restored database's legacy row was migrated"
    finally:
        conn.close()


# ── the fix round: a block-shuffle null in windows ──────────────────────────

BLOCK = {"method": "block_shuffle", "seed": 0}


def _quiet_with_two_drops(n=8 * H, seed=12):
    """White noise far under a 4 sigma, 30 s cut, and two deep two-minute drops: at 0:30 and at 7:30. In 2-hour
    windows at 50 % the first window and the last find a drop; the five between find nothing."""
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n) * 0.0001
    for a in (1800, 27000):
        x[a:a + 120] -= 0.01
    return x


def _block_shuffled(world, rid):
    conn = init_db(world["db"])
    try:
        plan = fanout.plan(conn, steps=NT, recording_ids=[rid], span=(0, 8 * H), ceiling_s=10 ** 6, null_draws=1,
                           surrogate=True, surrogate_params=BLOCK, windows={"window_s": 2 * H})
    finally:
        conn.close()
    return fanout.start(plan, db_path=world["db"], surrogate=True, surrogate_params=BLOCK,
                        surrogate_draws=1)["runs"][0]


def test_a_block_shuffle_null_is_drawn_in_every_window_with_one_block_per_channel(world):
    """m3: a block shuffle's block is twice the longest motif under test. Sized per window, a window that found
    nothing had no block and drew no null, and the stitched null counted nothing there: measured on pure noise (1-h
    windows) that left out 16 % (AR(1)) and 26 % (random walk) of the null, so x null read high. One block per channel
    — twice the longest detection any of its windows found — and every window draws."""
    rid = world["add"](_quiet_with_two_drops())
    row = _block_shuffled(world, rid)
    conn = init_db(world["db"])
    try:
        longest = max(int(conn.execute("SELECT COALESCE(MAX(end_idx - start_idx), 0) FROM detections WHERE run_id = ?",
                                       (w,)).fetchone()[0]) for w in row["window_run_ids"])
        found = [conn.execute("SELECT COUNT(*) FROM detections WHERE run_id = ?", (w,)).fetchone()[0]
                 for w in row["window_run_ids"]]
        assert longest > 0 and 0 in found, "some windows found the drops, some found nothing"
        block = max(2.0 * longest / FS, 2.0 / FS)
        for w in row["window_run_ids"]:
            draws = conn.execute("SELECT c.config_json FROM runs r JOIN configs c ON c.id = r.config_id "
                                 "WHERE r.surrogate_of_run_id = ? AND r.status = 'completed'", (w,)).fetchall()
            assert len(draws) == 1, f"window run {w} drew {len(draws)} nulls"
            assert json.loads(draws[0][0])["steps"][0]["params"]["block_s"] == block
        stitched_draw = R.get_run(conn, row["surrogate_run_ids"][0])
        assert R.load_recipe(conn, stitched_draw["config_id"])["steps"][0]["params"]["block_s"] == block
    finally:
        conn.close()
    assert row["surrogate_skipped"] is None


def test_a_channel_whose_windows_found_nothing_draws_no_block_shuffle_null(world):
    rid = world["add"](np.random.default_rng(13).standard_normal(8 * H) * 0.0001)
    row = _block_shuffled(world, rid)
    assert row["surrogate_run_ids"] == [] and "no window" in (row["surrogate_skipped"] or "")
