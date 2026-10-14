"""
test_template_chain_cycles.py
===============================
The `chain_cycles` TEMPLATE (w3-b), run end to end through `execute_recipe` on a
synthetic recording in a temporary database: the `noise_threshold` template's two
steps (a 600 s rolling-mean baseline, every stretch 4 sigma_n below) -> Event shape
(drops) -> Trains (MaxInterval at chain-scale gaps) -> Cycle shapes (write_group on,
`waveform` bound to the ROOT signal, chord detrend) -> Intervals.

Why the root signal and not an earlier long-detrended step: the per-cycle chord
already removes the drift under each cycle, and a rolling mean as long as the
longest cycles (60 min here) still bends the floor of the longest ones; the 600 s
trace the detector needs flattens a 30-45 min climb (the core test
`test_a_600s_detrend_distorts_the_sharkfin_and_the_raw_waveform_restores_it`).

The manager moves `TEMPLATE` into `webui/server/templates.py::CANONICAL`.
"""

import os
import shutil
import sys
import tempfile

import numpy as np
import pytest
from sklearn.metrics import adjusted_rand_score

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _cycle_synthetic as syn  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.execution import execute_recipe  # noqa: E402
from Working.templates import apply_template  # noqa: E402

FS = 1.0
CHAIN_GAPS = {"mi_begin_gap_s": 5400.0, "mi_end_gap_s": 10800.0, "mi_min_ibi_s": 10800.0, "mi_min_duration_s": 0.0}


def _step(stage, algorithm, params=None, side_inputs=None):
    d = {"stage": stage, "algorithm": algorithm, "params": dict(params or {})}
    if side_inputs:
        d["side_inputs"] = side_inputs
    return d


TEMPLATE = {
    "name": "chain_cycles", "kind": "interrogation", "version": 1,
    "description": "The shape of every cycle of a chain of drops, and where it changes: baseline removal → noise "
                   "threshold (every stretch more than 4 σ_n below the detrended trace's median, as the "
                   "noise_threshold template) → Event shape (drops) → Trains (MaxInterval at chain-scale gaps: a "
                   "train begins at a gap ≤ 1.5 h, continues while gaps ≤ 3 h, trains < 3 h apart merge) → Cycle "
                   "shapes (each drop-to-drop cycle cut from the raw recording, its drift removed by the chord "
                   "between its two pre-drop levels, stretched to one length, lined up and sorted into shapes; "
                   "more than one shape only when the split is two modes, not one shape that varies; each shape "
                   "becomes its group, marked ~noise_like when no more coherent than pseudo-cycles cut from the "
                   "recording's quiet stretches) → Intervals (the rhythm of each cycle shape). Read each group's "
                   "mark before its rhythm. Tune Cycle shapes' max_cycle_s first if many cycles are left out as "
                   "gaps.",
    "steps": [_step("preprocessing", "detrend", {"mode": "rolling_mean", "window_s": 600.0}),
              _step("detection", "noise_threshold", {"k_sigma": 4.0, "direction": "below",
                                                     "min_duration_s": 30.0, "merge_gap_s": 60.0}),
              _step("interrogation", "event_shape", {"polarity": "drop"}),
              _step("interrogation", "trains", {"rule": "maxinterval", **CHAIN_GAPS}),
              _step("interrogation", "cycle_shapes", {"write_group": True},
                    side_inputs={"waveform": {"source_kind": "root_signal"}}),
              _step("interrogation", "intervals", {})],
}


@pytest.fixture(scope="module")
def recording():
    tmp = tempfile.mkdtemp(prefix="chain_cycles_tpl_")
    # 5 % noise: at 10 % the 600 s noise threshold finds only 20 of the 60 sharkfins (a detector fact, reported)
    x, st, en = syn.two_family_chain("ar1", seed=2, noise=0.05)
    npy = os.path.join(tmp, "CH0.npy")
    np.save(npy, x)
    db = os.path.join(tmp, "t.sqlite")
    conn = init_db(db)
    q.insert_recording(conn, "synthetic_chain.mat", 0, FS, len(x), 0, npy)
    conn.close()
    import Working.config as cfg
    old = cfg.STEP_CACHE_ROOT
    cfg.STEP_CACHE_ROOT = os.path.join(tmp, "cache")
    try:
        yield db, x, st
    finally:
        cfg.STEP_CACHE_ROOT = old
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="module")
def template_run(recording):
    db, x, st = recording
    out = execute_recipe(apply_template(None, TEMPLATE, recording_id=1), db_path=db, force=True)
    return out, st


def test_the_template_is_an_interrogation_chain_of_six_blocks():
    assert [f"{s['stage']}.{s['algorithm']}" for s in TEMPLATE["steps"]] == [
        "preprocessing.detrend", "detection.noise_threshold", "interrogation.event_shape", "interrogation.trains",
        "interrogation.cycle_shapes", "interrogation.intervals"]
    assert TEMPLATE["kind"] == "interrogation"


def test_the_template_runs_end_to_end_and_finds_the_two_shapes(template_run):
    out, st = template_run
    res = out["result"]
    assert res.output_kind == "spanset"
    f = res.value.features
    for c in ("onset_idx", "train_id", "cycle_group", "cycle_floor_frac", "group", "interval_before_s"):
        assert c in f.columns, c
    # one detected event per true drop (within a minute), most of them
    det = np.asarray(f["onset_idx"], dtype=float)
    near = np.array([np.min(np.abs(st - d)) for d in det])
    assert np.sum(near <= 120) >= 110
    # the groups agree with the truth on the matched events
    truth = np.array([1 if np.argmin(np.abs(st - d)) < 60 else 2 for d in det])
    g = f["cycle_group"].to_numpy()
    used = g > 0
    assert used.sum() >= 100
    assert adjusted_rand_score(truth[used], g[used]) >= 0.9
    # the sharkfins' floor read from the root signal
    shark = used & (truth == 1)
    assert 0.5 <= np.median(f["cycle_floor_frac"][shark]) <= 0.67


def test_intervals_time_each_cycle_shape_and_no_key_is_unmarked_by_accident(template_run):
    out, _ = template_run
    f = out["result"].value.features
    keys = set(f["group"].astype(str))
    real = {k for k in keys if k != "-1" and not k.endswith("/-1")}
    assert len(real) == 2, keys
    # the groups beat their background null here, so they are unmarked
    assert not any(k.endswith(("~noise_like", "~untested")) for k in real)


def test_the_template_runs_with_the_waveform_unbound(recording):
    db, x, st = recording
    tpl = {**TEMPLATE, "steps": [dict(s) for s in TEMPLATE["steps"]]}
    tpl["steps"][4] = _step("interrogation", "cycle_shapes", {"write_group": True, "null_draws": 0})
    out = execute_recipe(apply_template(None, tpl, recording_id=1), db_path=db, force=True)
    f = out["result"].value.features
    assert "cycle_group" in f.columns and (f["cycle_group"] > 0).any()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
