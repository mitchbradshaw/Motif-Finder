"""
test_units_reach_the_blocks.py
================================
The drop detector and the event-shape block print millivolts by the unit the recording DECLARES
(`recordings.units`, Settings › Datasets), not by assuming that every file is stored in volts.

Found 2026-10-14 while the block page gained its readout: `detect5` multiplied every depth, slope
and noise floor by 1000 to report mV, and so did the readouts of `detection.stage_encoding`
("Slope-noise σ (MAD)", "Fast cut") and `detection.drop_detection` ("Onset slope threshold") —
right for the M2 exports (volts), 1000x too large on the four channels stored in mV
(L_LM_Jul_26_J, Schizophyllum commune, the two Dwij mfs2 loggers). Measured through the readout,
first 10 h of channel 0: M2_aug 0.0206 mV/s; L_LM 605.6 "mV/s"; Schizophyllum 4.71; mfs2 24.8 and
13.3. `interrogation.event_shape` carried the same factor (QUESTIONS.md Q-X2.8).

The researcher's choice (2026-10-15), over converting every mV file to volts on load (Q20): a run
TELLS the block the recording's unit and the block converts by it (`Working.units.read_as_mv`). A
unit nobody declared is read as volts, the core's convention, and the block says so beside the
number. Which events are found does not change — every rule the detector applies is relative —
only the millivolts it prints and the depth each event is scored with.

Pinned here, seam by seam:
* the core — `to_mv` on detect5 and event_shape; the default (1000, volts) is the path every
  shipped store and the id001 seed reproduction run on, bit for bit;
* the blocks — `units` on run and derive; volts when the caller names none, so a call that names
  no unit gets exactly what it got before;
* every path that runs a block hands it the recording's unit: `execute_recipe`, the block page's
  readout (`server.readout`), the window chain (`Working.discovery.window_chain`);
* the step cache, and the bridge's meta sidecar beside it, never serve a result computed under one
  unit to a recording now declared in another;
* the page's feature note no longer calls a millivolt recording's measures "1000x off".

Runs under the conda pytest (no FastAPI needed).
"""

import os
import re
import sys
import time

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui"), os.path.dirname(os.path.abspath(__file__))):
    if p not in sys.path:
        sys.path.insert(0, p)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.Detection.drop_motifs.detect5 import Detect5Params, detect_drops5, window_purity  # noqa: E402
from Working.types import SpanSet  # noqa: E402

discover_adapters()

FS = 1.0
N = 14_400                                   # four hours at 1 Hz
UNNAMED = object()                           # "the caller names no unit"


def millivolts(seed=1015):
    """A channel as a logger that stores mV writes it: a sudden 10 mV fall every 900 s with a tau-300 s
    recovery, N(0, 0.5 mV) noise and a 20 mV drift — test_drop_detection_nan's regime A, x10."""
    rng = np.random.default_rng(seed)
    t = np.arange(N, dtype=float)
    x = np.zeros(N)
    for s in range(100, N, 900):
        x[s:] += -10.0 * np.exp(-(t[s:] - s) / 300.0)
    return x - x.mean() + rng.normal(0.0, 0.5, N) + np.linspace(0.0, 20.0, N)


MV = millivolts()
V = MV / 1000.0                              # the same channel as the M2 exports store it


def _template(name):
    from server.templates import CANONICAL
    return [dict(s) for t in CANONICAL if t["name"] == name for s in t["steps"]]


DROP_STEPS = _template("drop_detection_v1")            # baseline removal -> five-stage encoding -> drop detection
FEATURE_STEPS = _template("drop_event_features")       # ... -> event shape -> intervals (the L_LM chains)


def _spec(step):
    return get_adapter(f"{step['stage']}.{step['algorithm']}")


def _params(step):
    return _spec(step).validate_params(step.get("params") or {})


def _named(units):
    return {} if units is UNNAMED else {"units": units}


def _blocks(x, units=UNNAMED):
    """drop_detection_v1's three blocks by hand: (t, detrended x, encoding result, detection result)."""
    t = np.arange(len(x)) / FS
    d, e, k = DROP_STEPS
    xd = _spec(d).run(x, t, FS, **_params(d)).value.x
    enc = _spec(e).run(xd, t, FS, **_params(e))
    det = _spec(k).run(xd, t, FS, **_params(k), value=enc.value, **_named(units))
    return t, xd, enc, det


def _derive(step, x, t, value=None, units=UNNAMED):
    kw = _named(units)
    if value is not None:
        kw["value"] = value
    return _spec(step).derive(x, t, FS, _params(step), **kw)


def _row(rows, label):
    hit = [r for r in rows if r[0] == label]
    assert len(hit) == 1, (label, rows)
    return hit[0]


def _mv(text):
    """The number a readout row prints before its unit: '0.6056 mV/s' -> 0.6056."""
    m = re.match(r"\s*(-?[0-9]+(?:\.[0-9]+)?)\s*mV/s", str(text))
    assert m, text
    return float(m.group(1))


def _anatomy(spans):
    return list(zip(spans.starts, spans.ends))


# ── the vocabulary ──────────────────────────────────────────────────────────

def test_a_declared_unit_converts_by_its_own_factor_and_an_undeclared_one_reads_as_volts():
    from Working.units import read_as_mv
    assert read_as_mv("V") == (1000.0, None)
    assert read_as_mv("mV") == (1.0, None)
    assert read_as_mv("uV") == (0.001, None)
    for undeclared in (None, "furlongs"):
        factor, note = read_as_mv(undeclared)
        assert factor == 1000.0, undeclared
        assert note and "read as volts" in note and "Settings › Datasets" in note, note
    assert "undeclared" in read_as_mv(None)[1]
    assert "furlongs" in read_as_mv("furlongs")[1]


# ── the core ────────────────────────────────────────────────────────────────

P5 = Detect5Params(detrend_window_s=4916.67, segment_seconds=98.33, same_fraction=0.6, slope_sigma=8.0)
MV_FIELDS = ("drop_depth_mv", "rise_height_mv", "peak_to_peak_mv")


def test_detect5_prints_the_same_millivolts_for_one_channel_stored_in_either_unit():
    rv = detect_drops5(V, FS, P5)
    rm = detect_drops5(MV, FS, P5, to_mv=1.0)
    assert len(rv.events) >= 10, "the synthetic channel must yield events for this test to mean anything"
    assert [(e.onset_idx, e.trough_idx, e.window_start_idx, e.window_end_idx) for e in rm.events] == \
           [(e.onset_idx, e.trough_idx, e.window_start_idx, e.window_end_idx) for e in rv.events]
    for f in MV_FIELDS:
        np.testing.assert_allclose([getattr(e, f) for e in rm.events], [getattr(e, f) for e in rv.events],
                                   rtol=1e-9, err_msg=f)
    depths = [e.drop_depth_mv for e in rm.events]
    assert 5.0 < float(np.median(depths)) < 15.0, depths            # ~10 mV falls read as ~10 mV, not 10 V
    for k in ("sigma_slope_mv_per_s", "slope_threshold_mv_per_s"):
        assert rm.diagnostics[k] == pytest.approx(rv.diagnostics[k], rel=1e-9), k
    assert rm.to_mv == 1.0 and rv.to_mv == 1000.0
    # the purity grade reads the detector's own slope gate back out of its diagnostics, in raw units
    assert window_purity(MV, FS, rm) == window_purity(V, FS, rv)


def test_detect5_with_no_factor_named_is_the_volts_path_bit_for_bit():
    """Against the verbatim frozen copy of detect5 (tests/_drop_nan_today.py) as well as against itself."""
    import dataclasses

    import _drop_nan_today as today
    drop = {"elapsed_s"}
    a, b, ref = detect_drops5(V, FS, P5), detect_drops5(V, FS, P5, to_mv=1000.0), today.detect_drops5(V, FS, P5)
    assert a.events == b.events and a.counts == b.counts and a.letters == b.letters
    assert [dataclasses.asdict(e) for e in a.events] == [dataclasses.asdict(e) for e in ref.events]
    assert {k: a.counts[k] for k in ref.counts} == ref.counts and a.letters == ref.letters   # + the gap counters
    for other in (b, ref):
        assert {k: v for k, v in a.diagnostics.items() if k not in drop} == \
               {k: v for k, v in other.diagnostics.items() if k not in drop}


# ── the blocks ──────────────────────────────────────────────────────────────

def test_the_encoding_readout_prints_true_millivolts_for_a_millivolt_channel():
    t = np.arange(N) / FS
    enc = DROP_STEPS[1]
    xdv, xdm = (_spec(DROP_STEPS[0]).run(x, t, FS, **_params(DROP_STEPS[0])).value.x for x in (V, MV))
    rv, rm = _derive(enc, xdv, t, units="V"), _derive(enc, xdm, t, units="mV")
    for label in ("Slope-noise σ (MAD)", "Fast cut (±slope_sigma·σ)"):
        assert _mv(_row(rm, label)[1]) == pytest.approx(_mv(_row(rv, label)[1]), abs=1e-4), label
        assert _row(rm, label)[2] == ""
    sigma = _mv(_row(rm, "Slope-noise σ (MAD)")[1])
    assert 0.1 < sigma < 5.0, sigma                    # ~0.5 mV of noise per sample: never ~1000 "mV/s"
    assert _row(rm, "Unit")[1].startswith("mV") and _row(rm, "Unit")[2] == ""
    assert _row(rv, "Unit")[1].startswith("V") and _row(rv, "Unit")[2] == ""


def test_the_drop_detection_block_scores_its_events_in_true_millivolts():
    _, _, _, dv = _blocks(V, units="V")
    _, _, _, dm = _blocks(MV, units="mV")
    assert len(dv.value.starts) >= 10
    assert _anatomy(dm.value) == _anatomy(dv.value)
    np.testing.assert_allclose(dm.value.scores, dv.value.scores, rtol=1e-9)
    for f in MV_FIELDS:
        np.testing.assert_allclose([e[f] for e in dm.meta["events"]], [e[f] for e in dv.meta["events"]], rtol=1e-9)
    assert dm.meta["units"] == "mV" and dm.meta["to_mv"] == 1.0 and dm.meta["units_note"] is None
    assert dv.meta["units"] == "V" and dv.meta["to_mv"] == 1000.0 and dv.meta["units_note"] is None
    assert dm.meta["diagnostics"]["sigma_slope_mv_per_s"] == pytest.approx(
        dv.meta["diagnostics"]["sigma_slope_mv_per_s"], rel=1e-9)


def test_the_drop_detection_readout_prints_its_threshold_in_true_millivolts():
    tv, xdv, ev, _ = _blocks(V)
    tm, xdm, em, _ = _blocks(MV)
    rv = _derive(DROP_STEPS[2], xdv, tv, value=ev.value, units="V")
    rm = _derive(DROP_STEPS[2], xdm, tm, value=em.value, units="mV")
    label = "Onset slope threshold"
    assert _mv(_row(rm, label)[1]) == pytest.approx(_mv(_row(rv, label)[1]), abs=1e-4)
    assert -50.0 < _mv(_row(rm, label)[1]) < 0.0
    assert _row(rm, "Unit")[1].startswith("mV")


def test_a_block_told_no_unit_is_the_volts_path_bit_for_bit():
    """Every caller that names no unit — the Pipelines, the frozen-copy tests, a script — gets what it got."""
    t, xd, enc, plain = _blocks(V)
    _, _, _, volts = _blocks(V, units="V")
    assert plain.value.scores == volts.value.scores and _anatomy(plain.value) == _anatomy(volts.value)
    assert plain.meta["events"] == volts.meta["events"]
    assert _derive(DROP_STEPS[1], xd, t) == _derive(DROP_STEPS[1], xd, t, units="V")
    assert _derive(DROP_STEPS[2], xd, t, value=enc.value) == _derive(DROP_STEPS[2], xd, t, value=enc.value, units="V")


def test_an_undeclared_unit_is_read_as_volts_and_says_so_beside_every_millivolt():
    """The researcher's choice for M1, M100, M101_t, MJu26a, M4: today's numbers, flagged."""
    t, xd, enc, volts = _blocks(V, units="V")
    _, _, _, undeclared = _blocks(V, units=None)
    assert undeclared.value.scores == volts.value.scores
    assert undeclared.meta["to_mv"] == 1000.0 and undeclared.meta["units"] is None
    assert "undeclared" in undeclared.meta["units_note"] and "read as volts" in undeclared.meta["units_note"]
    for step, value, labels in ((DROP_STEPS[1], None, ("Slope-noise σ (MAD)", "Fast cut (±slope_sigma·σ)")),
                                (DROP_STEPS[2], enc.value, ("Onset slope threshold",))):
        said = _derive(step, xd, t, value=value, units=None)
        known = _derive(step, xd, t, value=value, units="V")
        for label in labels:
            assert _mv(_row(said, label)[1]) == _mv(_row(known, label)[1]), label        # the same number ...
            assert _row(said, label)[2] == "warn" and "read as volts" in _row(said, label)[1], label   # ... flagged
        unit = _row(said, "Unit")
        assert unit[2] == "warn" and "undeclared" in unit[1] and "Settings › Datasets" in unit[1], unit


def _drop_event():
    """test_adapter_event_shape's hand-worked drop, in volts: depth 10 mV, steepest -5 mV/s at 10 Hz."""
    x = np.zeros(300)
    x[20:51] = np.linspace(0.0, 0.002, 31)
    x[50:71] = np.linspace(0.002, -0.008, 21)
    x[70:81] = -0.008
    x[80:121] = np.linspace(-0.008, 0.0, 41)
    return x


def _shape(x, units=UNNAMED, fs=10.0):
    spec = get_adapter("interrogation.event_shape")
    ss = SpanSet(starts=(0,), ends=(len(x),))
    return spec.run(x, np.arange(len(x)) / fs, fs, value=ss, **spec.validate_params({"rose_scale": "pooled"}),
                    **_named(units))


def _units_rule(meta):
    return next(r["rule"] for r in meta["rules"] if r["name"] == "units")


def test_event_shape_measures_true_millivolts_on_a_millivolt_channel():
    v, m = _shape(_drop_event(), units="V"), _shape(_drop_event() * 1000.0, units="mV")
    fv, fm = v.value.features, m.value.features
    assert fv.iloc[0]["event_amplitude_mv"] == pytest.approx(10.0)
    assert fv.iloc[0]["max_slope_mv_s"] == pytest.approx(-5.0)
    for col in ("event_amplitude_mv", "precursor_height_mv", "max_slope_mv_s", "onset_slope_mv_s",
                "chord_slope_mv_s", "span_ptp_mv", "event_width_s", "fwhm_s"):
        assert fm.iloc[0][col] == pytest.approx(fv.iloc[0][col], rel=1e-9), col
    assert m.meta["units"] == "mV" and m.meta["to_mv"] == 1.0 and m.meta["units_note"] is None
    assert "mV" in _units_rule(m.meta) and "Q-X2.8" not in _units_rule(m.meta)
    plain = _shape(_drop_event())
    assert plain.value.features.equals(v.value.features), "naming no unit is the volts path"
    undeclared = _shape(_drop_event(), units=None)
    assert undeclared.value.features.equals(v.value.features)
    assert "undeclared" in undeclared.meta["units_note"]
    assert "undeclared" in _units_rule(undeclared.meta) and "Settings › Datasets" in _units_rule(undeclared.meta)


def test_the_event_shape_readout_says_which_unit_it_reads():
    spec = get_adapter("interrogation.event_shape")
    x = _drop_event()
    t = np.arange(len(x)) / 10.0
    params = spec.validate_params({})
    ss = SpanSet(starts=(0,), ends=(300,))
    assert _row(spec.derive(x, t, 10.0, params, value=ss, units="mV"), "Unit")[1].startswith("mV")
    unit = _row(spec.derive(x, t, 10.0, params, value=ss, units=None), "Unit")
    assert unit[2] == "warn" and "undeclared" in unit[1]


# ── the paths that run a block ──────────────────────────────────────────────

@pytest.fixture
def store(tmp_path, monkeypatch):
    """Three registered channels: the synthetic channel stored in mV and declared mV, the same channel stored
    in volts and declared V, and the volts copy with no unit declared."""
    import Working.config as cfg
    from Working.database import queries as q
    from Working.database.schema import init_db
    monkeypatch.setattr(cfg, "STEP_CACHE_ROOT", str(tmp_path / "step_cache"))
    paths = {}
    for name, x in (("mv", MV), ("v", V)):
        paths[name] = str(tmp_path / f"{name}.npy")
        np.save(paths[name], x)
    db = str(tmp_path / "annotations.sqlite")
    conn = init_db(db)
    ids = {
        "mV": q.insert_recording(conn, "logger.csv", 0, FS, N, 0, paths["mv"], units="mV"),
        "V": q.insert_recording(conn, "export.mat", 0, FS, N, 0, paths["v"], units="V"),
        None: q.insert_recording(conn, "unknown.mat", 0, FS, N, 0, paths["v"]),
    }
    try:
        yield db, conn, ids
    finally:
        conn.close()


def _execute(db, rid, steps):
    from Working.execution import execute_recipe
    from Working.recipes import make_recipe
    seen = {}
    out = execute_recipe(make_recipe(rid, steps), db_path=db, force=True,
                         on_step_result=lambda i, r: seen.__setitem__(i, r))
    return out, seen


def _written_scores(conn, run_id):
    """The score each event was written to `detections` with: the drop depth, in mV."""
    return [float(r[0]) for r in conn.execute("SELECT score FROM detections WHERE run_id = ? ORDER BY start_idx",
                                              (run_id,))]


def test_execute_recipe_hands_each_block_its_recordings_unit(store):
    db, conn, ids = store
    runs = {u: _execute(db, rid, FEATURE_STEPS) for u, rid in ids.items()}
    (ov, sv), (om, sm), (ou, su) = runs["V"], runs["mV"], runs[None]
    assert len(sv[2].value.starts) >= 10
    assert _anatomy(sm[2].value) == _anatomy(sv[2].value)
    np.testing.assert_allclose(sm[2].value.scores, sv[2].value.scores, rtol=1e-9)
    assert 5.0 < float(np.median(sm[2].value.scores)) < 15.0
    for col in ("event_amplitude_mv", "max_slope_mv_s", "span_ptp_mv"):
        np.testing.assert_allclose(sm[3].value.features[col], sv[3].value.features[col], rtol=1e-9, err_msg=col)
    written = _written_scores(conn, om["run_id"])
    assert len(written) == len(sm[2].value.starts)
    np.testing.assert_allclose(written, _written_scores(conn, ov["run_id"]), rtol=1e-9)
    assert sm[2].meta["units"] == "mV" and sm[3].meta["units"] == "mV"
    # an undeclared recording: the volts numbers, and the run says why
    assert su[2].value.scores == sv[2].value.scores
    assert "undeclared" in su[2].meta["units_note"] and "undeclared" in su[3].meta["units_note"]


def test_a_cached_step_is_never_served_to_a_recording_now_declared_in_another_unit(store, monkeypatch):
    """A recording declared V that holds millivolts is re-declared mV: the next run must measure again."""
    import Working.config as cfg
    db, conn, ids = store
    monkeypatch.setattr(cfg, "STEP_CACHE_WRITE_THRESHOLD_S", 0.0)          # what a sandbox bridge sets: cache all
    conn.execute("UPDATE recordings SET units = 'V' WHERE id = ?", (ids["mV"],))
    conn.commit()
    _, as_volts = _execute(db, ids["mV"], FEATURE_STEPS)
    conn.execute("UPDATE recordings SET units = 'mV' WHERE id = ?", (ids["mV"],))
    conn.commit()
    out, as_mv = _execute(db, ids["mV"], FEATURE_STEPS)
    assert out["step_timings"][0] == 0.0 and out["step_timings"][1] == 0.0, \
        "the steps that never read the unit are still served from the cache"
    np.testing.assert_allclose(np.asarray(as_mv[2].value.scores) * 1000.0, as_volts[2].value.scores, rtol=1e-9)
    np.testing.assert_allclose(as_mv[3].value.features["event_amplitude_mv"] * 1000.0,
                               as_volts[3].value.features["event_amplitude_mv"], rtol=1e-9)


def test_the_cache_key_carries_the_unit_only_where_a_block_reads_it_and_only_when_it_is_not_volts():
    from Working.execution import _recipe_prefix_hash
    from Working.recipes import make_recipe
    recipe = make_recipe(7, FEATURE_STEPS)
    for i in (0, 1):                              # baseline removal, the encoding: no block in the prefix reads it
        assert _recipe_prefix_hash(recipe, i, units="mV") == _recipe_prefix_hash(recipe, i), i
    for i in (2, 3, 4):                           # drop detection onward
        plain = _recipe_prefix_hash(recipe, i)
        assert _recipe_prefix_hash(recipe, i, units="V") == plain, "a volts recording keeps every key it had"
        assert _recipe_prefix_hash(recipe, i, units=None) == plain, "an undeclared one is read as volts"
        assert _recipe_prefix_hash(recipe, i, units="mV") != plain, i
        assert _recipe_prefix_hash(recipe, i, units="uV") not in (plain, _recipe_prefix_hash(recipe, i, units="mV"))


def test_the_readout_hands_the_block_its_recordings_unit(store):
    from server import corpus, readout
    _, conn, ids = store
    rec = {u: corpus.recording_row(conn, rid) for u, rid in ids.items()}
    for index, label in ((1, "Slope-noise σ (MAD)"), (1, "Fast cut (±slope_sigma·σ)"), (2, "Onset slope threshold")):
        got = {u: {r["label"]: r for r in readout.block_readout(conn, rec[u], None, DROP_STEPS, index)["rows"]}
               for u in rec}
        assert _mv(got["mV"][label]["value"]) == pytest.approx(_mv(got["V"][label]["value"]), abs=1e-4), label
        assert got["mV"]["Unit"]["value"].startswith("mV") and got["V"]["Unit"]["value"].startswith("V")
        assert got[None][label]["severity"] == "warn" and got[None]["Unit"]["severity"] == "warn"


def test_the_window_chain_hands_the_block_the_unit_it_is_given():
    from Working.discovery.window_chain import run_window
    from Working.recipes import make_recipe
    recipe = make_recipe(1, DROP_STEPS)
    sv = run_window(None, recipe, V, FS, units="V")
    sm = run_window(None, recipe, MV, FS, units="mV")
    assert all(s["ok"] for s in sv + sm), [s["error"] for s in sv + sm]
    assert _anatomy(sm[2]["value"]) == _anatomy(sv[2]["value"]) and len(sv[2]["value"].starts) >= 10
    np.testing.assert_allclose(sm[2]["value"].scores, sv[2]["value"].scores, rtol=1e-9)
    plain = run_window(None, recipe, V, FS)
    assert plain[2]["value"].scores == sv[2]["value"].scores, "naming no unit is the volts path"


# ── what the page says ──────────────────────────────────────────────────────

def _features_payload(units, meta=UNNAMED, block="interrogation.event_shape"):
    from server.serialize import to_payload
    run = _shape(_drop_event(), units=units)
    ctx = {"fs": 10.0, "span_start": 0, "n_samples": 300, "units": units, "block": block}
    return to_payload("spanset", run.value, run.meta if meta is UNNAMED else meta, ctx)


def test_the_feature_note_no_longer_calls_a_millivolt_recordings_measures_1000x_off():
    assert _features_payload("mV").get("features_unit_note") is None
    assert _features_payload("V").get("features_unit_note") is None
    said = _features_payload(None).get("features_unit_note")
    assert said and "undeclared" in said and "read as volts" in said, said


def test_the_feature_note_holds_on_a_cache_hit_whose_meta_was_not_restored():
    """The core's step cache restores the value only; with no sidecar the meta is {}. The note still follows the
    recording's unit."""
    assert _features_payload("mV", meta={}).get("features_unit_note") is None
    said = _features_payload(None, meta={}).get("features_unit_note")
    assert said and "undeclared" in said


def test_a_block_after_event_shape_carries_its_columns_without_the_old_1000x_note():
    """drop_event_features ends Event shape -> Intervals: the Intervals stage's table carries Event shape's mV
    columns through, and Intervals itself is never told the unit."""
    from server.serialize import to_payload
    shaped = _shape(_drop_event(), units="mV").value
    intervals = get_adapter("interrogation.intervals")
    out = intervals.run(_drop_event(), np.arange(300) / 10.0, 10.0, value=shaped, **intervals.validate_params({}))
    assert "event_amplitude_mv" in out.value.features.columns
    for units, said in (("mV", False), (None, True)):
        ctx = {"fs": 10.0, "span_start": 0, "n_samples": 300, "units": units, "block": "interrogation.intervals"}
        note = to_payload("spanset", out.value, out.meta, ctx).get("features_unit_note")
        assert bool(note) is said and "1000x off" not in str(note), (units, note)
    no_mv = SpanSet(starts=(0,), ends=(300,), features=out.value.features[["interval_before_s", "interval_after_s"]])
    ctx = {"fs": 10.0, "span_start": 0, "n_samples": 300, "units": None, "block": "interrogation.intervals"}
    assert to_payload("spanset", no_mv, {}, ctx).get("features_unit_note") is None, "no mV column, nothing to say"


def test_the_bridge_keeps_a_steps_meta_under_the_unit_aware_cache_key(store, tmp_path, monkeypatch):
    import Working.config as cfg
    from server import chain as chain_mod
    from server.runs import RunManager
    from Working.execution import _recipe_prefix_hash
    db, conn, ids = store
    monkeypatch.setattr(cfg, "STEP_CACHE_WRITE_THRESHOLD_S", 0.0)
    rec = dict(conn.execute("SELECT * FROM recordings WHERE id = ?", (ids["mV"],)).fetchone())
    recipe = chain_mod.build_recipe(rec["id"], None, DROP_STEPS)
    meta_dir = str(tmp_path / "meta")
    job = RunManager(db, meta_dir=meta_dir).start(recipe, rec)
    t0 = time.time()
    while job.status == "running" and time.time() - t0 < 60:
        time.sleep(0.02)
    assert job.status == "completed", job.error
    key = _recipe_prefix_hash(recipe, 2, units="mV")
    assert os.path.isfile(os.path.join(meta_dir, key, "2.json")), "the sidecar sits under the key the cache uses"
    status = chain_mod.cache_status(recipe, conn)[2]            # what the page predicts before a re-run
    assert status["prefix_hash"] == key and status["cached"], status


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
