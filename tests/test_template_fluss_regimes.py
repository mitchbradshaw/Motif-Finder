"""
test_template_fluss_regimes.py
================================
The `fluss_regimes` TEMPLATE: baseline removal (rolling mean, 600 s) →
`detection.fluss` (60 s window) → `detection.threshold` (a cut calibrated on
the synthetic regimes below), run end to end through `execute_recipe` in a
temporary database.

The template is defined here as a module-level constant; the manager moves it
into `webui/server/templates.py::CANONICAL` after merging (W1-F prompt).

Calibration of the cut (6 seeds of each recording, detrended as here): the
two-regime recording's peak score was 0.475-0.546, the single regime's at
most 0.281, the drift ramp's at most 0.212. 0.38 sits between them with about
0.1 either side. `merge_gap_s` 600 joins the ragged edge of the one broad dip
into one span; `min_duration_s` 60 drops a one-window graze.

Runnable standalone:  python tests/test_template_fluss_regimes.py
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
from tests._fluss_synthetic import BOUNDARY, FS, drift_ramp, one_regime, two_regimes  # noqa: E402

TEMPLATE = {
    "name": "fluss_regimes", "kind": "detection", "version": 1,
    "description": "Where does the recording change behaviour? Baseline removal → FLUSS regime-change score "
                   "(Gharghabi et al. 2017: few nearest-neighbour arcs cross a change of behaviour; 60 s window) "
                   "→ threshold to one span per change. Each span is a candidate boundary to check in Review.",
    "steps": [
        {"stage": "preprocessing", "algorithm": "detrend",
         "params": {"mode": "rolling_mean", "window_s": 600.0}},
        {"stage": "detection", "algorithm": "fluss",
         "params": {"window_s": 60.0, "n_regimes_readout": 3, "iac": "parabola", "excl_factor": 5}},
        {"stage": "detection", "algorithm": "threshold",
         "params": {"threshold": 0.38, "merge_gap_s": 600.0, "min_duration_s": 60.0}},
    ],
}


@pytest.fixture
def run_on():
    tmp = tempfile.mkdtemp(prefix="fluss_tpl_")
    import Working.config as cfg
    old = cfg.STEP_CACHE_ROOT
    cfg.STEP_CACHE_ROOT = os.path.join(tmp, "cache")
    counter = {"n": 0}

    def _run(x):
        counter["n"] += 1
        npy = os.path.join(tmp, f"CH{counter['n']}.npy")
        np.save(npy, x)
        db = os.path.join(tmp, f"t{counter['n']}.sqlite")
        conn = init_db(db)
        q.insert_recording(conn, "synthetic.mat", 0, FS, len(x), 0, npy)
        conn.close()
        recipe = apply_template(None, TEMPLATE, recording_id=1)
        out = execute_recipe(recipe, db_path=db, force=True)
        conn = init_db(db)
        try:
            rows = list_detections(conn, out["run_id"])
        finally:
            conn.close()
        return out, rows

    try:
        yield _run
    finally:
        cfg.STEP_CACHE_ROOT = old
        shutil.rmtree(tmp, ignore_errors=True)


def test_template_is_a_three_step_detection_chain():
    assert TEMPLATE["kind"] == "detection"
    assert [f"{s['stage']}.{s['algorithm']}" for s in TEMPLATE["steps"]] == [
        "preprocessing.detrend", "detection.fluss", "detection.threshold"]


def test_two_regimes_give_exactly_one_span_at_the_boundary(run_on):
    out, rows = run_on(two_regimes())
    assert out["result"].output_kind == "spanset"
    spans = list(zip(out["result"].value.starts, out["result"].value.ends))
    assert len(spans) == 1, spans
    (s, e), = spans
    m = 60
    assert s - 2 * m <= BOUNDARY < e + 2 * m
    assert [(r["start_idx"], r["end_idx"]) for r in rows] == spans
    assert out["detections_written"] == 1


def test_a_single_regime_gives_no_span(run_on):
    out, rows = run_on(one_regime())
    assert len(out["result"].value.starts) == 0
    assert rows == []


def test_a_drift_ramp_gives_no_span(run_on):
    out, rows = run_on(drift_ramp())
    assert len(out["result"].value.starts) == 0
    assert rows == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
