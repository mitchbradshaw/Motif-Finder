"""
test_template_event_trains.py
===============================
w1-e: the `event_trains` template - the three `drop_detection_v1` blocks ->
Event shape -> Trains -> Intervals - run end to end through `execute_recipe`
on a synthetic recording of four trains of four drops (12 s apart inside a
train, ~114 s between trains, 10 Hz).

The template is defined HERE as a module-level constant (00-common.md: the
manager moves it into `webui/server/templates.py::CANONICAL` after merging);
its first three steps are copied from `canonical("drop_detection_v1")` so they
cannot drift from the shipped detector. Trains writes `group = train_id`
(`write_group`), so Intervals measures timing WITHIN each train.

Runnable standalone:  python tests/test_template_event_trains.py
"""

import json
import os
import shutil
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

from Working.database import queries as q  # noqa: E402
from Working.database.runs import list_detections  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.execution import execute_recipe  # noqa: E402
from Working.templates import apply_template  # noqa: E402
from server.templates import canonical, kind_for_steps  # noqa: E402

FS = 10.0


def _step(stage, algorithm, params=None):
    return {"stage": stage, "algorithm": algorithm, "params": dict(params or {})}


TEMPLATE = {
    "name": "event_trains", "kind": "interrogation", "version": 1,
    "description": "The drop detector (drop_detection_v1's three blocks) → Event shape (each event's onset) → "
                   "Trains (logISI: the valley of the log-gap histogram is the cut; one hump → no trains, said so) "
                   "→ Intervals, grouped by train, so the regularity numbers are WITHIN trains. Every rule is "
                   "printed beside its numbers.",
    "steps": [*canonical("drop_detection_v1")["steps"],
              _step("interrogation", "event_shape", {}),
              _step("interrogation", "trains", {"rule": "logisi", "write_group": True}),
              _step("interrogation", "intervals", {})],
}

ONSETS_S = [20 + k * 150 + 12 * i for k in range(4) for i in range(4)]


def trains_signal(onsets_s=ONSETS_S, seconds=650.0, fs=FS, seed=0):
    """Flat trace with one sharkfin drop (8.5 s rise, 1.5 s fall, 10 mV) per onset."""
    n = int(seconds * fs)
    t = np.arange(n) / fs
    x = np.zeros(n)
    for o in onsets_s:
        ph = (t - o) / 10.0
        m = (ph >= 0) & (ph < 1)
        x[m] = np.where(ph[m] < 0.85, ph[m] / 0.85, 1.0 - (ph[m] - 0.85) / 0.15) * 0.01
    return x + 0.00002 * np.random.default_rng(seed).standard_normal(n)


@pytest.fixture
def scratch():
    tmp = tempfile.mkdtemp(prefix="trains_tpl_")
    import Working.config as cfg
    old = cfg.STEP_CACHE_ROOT
    cfg.STEP_CACHE_ROOT = os.path.join(tmp, "cache")
    try:
        yield tmp
    finally:
        cfg.STEP_CACHE_ROOT = old
        shutil.rmtree(tmp, ignore_errors=True)


def _db(tmp, x):
    npy = os.path.join(tmp, "CH0.npy")
    np.save(npy, x)
    db = os.path.join(tmp, "t.sqlite")
    conn = init_db(db)
    q.insert_recording(conn, "synthetic.mat", 0, FS, len(x), 0, npy)
    conn.close()
    return db


def _tuned():
    """The template with the detrend window and segment length a 10 Hz, 10 s-event synthetic needs (the
    tuning `test_template_event_features.py` applies to the same detector)."""
    tpl = json.loads(json.dumps(TEMPLATE))
    for s in tpl["steps"]:
        if s["algorithm"] == "detrend":
            s["params"]["window_s"] = 12.0
        if s["algorithm"] == "stage_encoding":
            s["params"]["segment_seconds"] = 0.5
    return tpl


def test_the_template_is_an_interrogation_chain_of_six_blocks():
    assert [f"{s['stage']}.{s['algorithm']}" for s in TEMPLATE["steps"]] == [
        "preprocessing.detrend", "detection.stage_encoding", "detection.drop_detection",
        "interrogation.event_shape", "interrogation.trains", "interrogation.intervals"]
    assert TEMPLATE["steps"][:3] == canonical("drop_detection_v1")["steps"]
    assert kind_for_steps(TEMPLATE["steps"]) == TEMPLATE["kind"] == "interrogation"


def test_the_template_runs_end_to_end_and_finds_the_four_trains(scratch):
    x = trains_signal()
    db = _db(scratch, x)
    recipe = apply_template(None, _tuned(), recording_id=1, span=(0, len(x)))
    out = execute_recipe(recipe, db_path=db, force=True)
    ss = out["result"].value
    f = ss.features
    assert len(ss.starts) == 16
    for col in ("event_amplitude_mv", "onset_idx", "train_id", "train_size", "position_in_train", "gap_before_s",
                "interval_before_s", "group"):
        assert col in f.columns, col
    assert list(f["train_id"]) == [k for k in range(4) for _ in range(4)]
    assert list(f["group"]) == [str(k) for k in range(4) for _ in range(4)]
    # Intervals grouped by train: no interval crosses a train boundary
    assert f["interval_before_s"].max() == pytest.approx(12.0, abs=0.5)
    assert int(np.isnan(f["interval_before_s"]).sum()) == 4
    conn = init_db(db)
    try:
        assert len(list_detections(conn, out["run_id"])) == 16, "a feature block re-wrote the detector's spans"
    finally:
        conn.close()


def test_the_trains_meta_survives_into_the_run(scratch):
    """The Trains step's own result (cut, density) is the second-to-last step's; run the chain up to it."""
    x = trains_signal()
    db = _db(scratch, x)
    tpl = _tuned()
    tpl["steps"] = tpl["steps"][:5]
    out = execute_recipe(apply_template(None, tpl, recording_id=1, span=(0, len(x))), db_path=db, force=True)
    m = out["result"].meta
    assert m["rule"] == "logisi" and m["n_trains"] == 4
    assert 12.0 < m["cut_s"] < 114.0
    assert m["anchor_used"] == "onset_idx"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))


def test_the_shipped_template_is_the_one_tested_here():
    """The manager moved TEMPLATE into webui/server/templates.py::CANONICAL; the two must not drift apart."""
    import os as _os
    import sys as _sys
    _root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    for _p in (_root, _os.path.join(_root, "webui")):
        if _p not in _sys.path:
            _sys.path.insert(0, _p)
    from server.templates import canonical
    assert canonical("event_trains") == TEMPLATE
