"""
test_template_deconvolved_troughs.py
=====================================
W1-B: the `deconvolved_troughs` template, end to end through `execute_recipe`
on a synthetic recording in a temporary database (the pattern of
`test_template_dehshibi.py`):

    Baseline removal (a rolling mean far longer than the recovery)
      -> Deconvolve (OASIS) -> Impulse events -> Event shape -> Intervals

The constant `TEMPLATE` below is what the manager moves into
`webui/server/templates.py::CANONICAL`. The synthetic is the 12-hour trough
train with a slow drift added, which is why the detrend comes first (OASIS's
baseline is one constant per span; the paper says drifting baselines are not
handled), and why Deconvolve's own running baseline (`baseline_window_s`) is
on: a rolling MEAN is dragged down by every trough that enters its window, and
the 1-2 noise-SD steps it leaves read as hundreds of small jumps against a
constant baseline (823 events for 30 troughs before the running baseline).

Runnable standalone:  python tests/test_template_deconvolved_troughs.py
"""

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
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database import queries as q  # noqa: E402
from Working.database.runs import list_detections  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.execution import execute_recipe  # noqa: E402
from Working.templates import apply_template  # noqa: E402
from tests._deconv_synthetic import FS, troughs_12h  # noqa: E402

TEMPLATE = {
    "name": "deconvolved_troughs", "kind": "detection", "version": 1,
    "description": "Troughs as deconvolved jumps (Friedrich, Zhou & Paninski 2017, OASIS): a long baseline "
                   "removal (1 h rolling mean, far longer than a recovery) → Deconvolve (OASIS): the size of the "
                   "sudden drop at every sample, in noise SDs, each followed by the same exponential recovery, "
                   "over a baseline that follows what drift the rolling mean left (30 min windows) → "
                   "Impulse events: one event per drop, running to the next drop, so a trough that starts before "
                   "the last one recovered is its own event → Event shape → Intervals.",
    "steps": [
        {"stage": "preprocessing", "algorithm": "detrend", "params": {"mode": "rolling_mean", "window_s": 3600.0}},
        {"stage": "detection", "algorithm": "deconvolve", "params": {"baseline_window_s": 1800.0}},
        {"stage": "detection", "algorithm": "impulse_events", "params": {}},
        {"stage": "interrogation", "algorithm": "event_shape", "params": {}},
        {"stage": "interrogation", "algorithm": "intervals", "params": {}},
    ],
}


@pytest.fixture
def db_and_signal():
    tmp = tempfile.mkdtemp(prefix="deconv_tpl_")
    x, onsets, pairs = troughs_12h(seed=0, drift=4e-3)
    npy = os.path.join(tmp, "CH0.npy")
    np.save(npy, x)
    db = os.path.join(tmp, "t.sqlite")
    conn = init_db(db)
    q.insert_recording(conn, "synthetic.mat", 0, FS, len(x), 0, npy)
    conn.close()
    import Working.config as cfg
    old = cfg.STEP_CACHE_ROOT
    cfg.STEP_CACHE_ROOT = os.path.join(tmp, "cache")
    try:
        yield db, x, onsets, pairs
    finally:
        cfg.STEP_CACHE_ROOT = old
        shutil.rmtree(tmp, ignore_errors=True)


def test_template_shape():
    assert TEMPLATE["name"] == "deconvolved_troughs" and TEMPLATE["version"] == 1
    assert [f"{s['stage']}.{s['algorithm']}" for s in TEMPLATE["steps"]] == [
        "preprocessing.detrend", "detection.deconvolve", "detection.impulse_events",
        "interrogation.event_shape", "interrogation.intervals"]
    assert TEMPLATE["steps"][0]["params"]["window_s"] >= 10 * 120.0   # far longer than the recovery
    assert TEMPLATE["steps"][1]["params"]["baseline_window_s"] >= 10 * 120.0


def test_template_runs_end_to_end_and_writes_its_spans_to_detections(db_and_signal):
    db, x, onsets, pairs = db_and_signal
    recipe = apply_template(None, TEMPLATE, recording_id=1, span=(0, len(x)))
    out = execute_recipe(recipe, db_path=db, force=True)
    res = out["result"]
    assert res.output_kind == "spanset"
    ss = res.value
    assert ss.features is not None and len(ss.features) == len(ss.starts)
    assert {"onset_idx", "extremum_idx"} <= set(ss.features.columns)
    assert len(ss.starts) == 30
    # each detected window holds the drop it was made for (onset = the sample before the jump)
    for o in onsets:
        assert any(s <= o - 1 < e for s, e in zip(ss.starts, ss.ends))
    conn = init_db(db)
    try:
        rows = list_detections(conn, out["run_id"])
    finally:
        conn.close()
    assert out["detections_written"] == len(ss.starts) == len(rows)
    assert sorted(r["start_idx"] for r in rows) == sorted(int(s) for s in ss.starts)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
