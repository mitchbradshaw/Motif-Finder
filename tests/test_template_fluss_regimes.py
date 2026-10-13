"""
test_template_fluss_regimes.py
================================
The `fluss_regimes` TEMPLATE: baseline removal (rolling mean, 600 s) →
`detection.fluss` (300 s window) → `detection.threshold` (a cut calibrated on
the synthetic regimes below), run end to end through `execute_recipe` in a
temporary database; the calibration sweep runs the same three blocks directly
(the same code without the database, which only adds time).

The template is defined here as a module-level constant; the manager moves it
into `webui/server/templates.py::CANONICAL` after merging (W1-F prompt).

Calibration (detrended as here; peak score over seeds 0-11 unless noted).
The first version used a 60 s window and a cut of 0.38, calibrated on
clockwork regimes (fixed spacing and shape); with realistic jitter the change
peaked at 0.35-0.40 (noise 0.05) and 0.12-0.17 (noise 0.3) and was missed. The
paper sets the window to about one period; the regimes' periods are 5 and
15 min, so the window is 300 s:

    two regimes, jittered, noise 0.05   0.65-0.82   (one span in all 12)
    two regimes, jittered, noise 0.3    0.49-0.68   (one span in all 12)
    two regimes, clockwork (0-5)        0.84-0.89
    one regime,  jittered, noise 0.05   0.05-0.43
    one regime,  jittered, noise 0.3    0.02-0.44
    one regime,  clockwork (0-5)        0.15-0.25
    pink noise                          0.00-0.37
    random walk (0-5)                   0.05-0.22
    sinusoidal drift (0-5)              0.11-0.18
    drift ramp (0-5)                    0.02-0.18

The cut 0.46 sits between the nulls' 0.44 and the changes' 0.49. The margin is
thin on both sides; the nulls' highest peaks sit at the edge of the blanked
stretch (the expected arc count is small there). `merge_gap_s` 1500 =
excl_factor x window: a window this long makes a broad, ragged dip, and with
the old 600 s gap one change came out as 2-3 spans; FLUSS cannot place two
changes closer than that anyway. `min_duration_s` 60 drops a one-window graze.

The calibration is for 4 h spans. A shorter span holds fewer events, so a run
of unusually spaced ones in a single regime weighs more: one 2.8 h jittered
single regime (seed 1, the first 10000 samples) peaked at 0.53-0.59, above the
cut. Treat a span on a short recording with suspicion.

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
from tests import _fluss_synthetic as syn  # noqa: E402
from tests._fluss_synthetic import BOUNDARY, FS, drift_ramp, one_regime, two_regimes  # noqa: E402

#: the fluss step's window, in samples at FS
M = int(300.0 * FS)
SEEDS = range(6)

TEMPLATE = {
    "name": "fluss_regimes", "kind": "detection", "version": 1,
    "description": "Where does the recording change behaviour? Baseline removal → FLUSS regime-change score "
                   "(Gharghabi et al. 2017: few nearest-neighbour arcs cross a change of behaviour; 300 s window, "
                   "about one event period of slow regimes) → threshold to one span per change. The cut 0.46 "
                   "is calibrated for this window, on 4 h recordings; on a shorter one a single regime can cross it. Each span is a candidate boundary to check in Review; "
                   "check the recording's NaN gaps first — the detrend keeps a gap to its own length, but FLUSS "
                   "leaves every window touching it unscored and reads its two sides as adjacent, so a change "
                   "near a long gap can come out as a span on each side of it.",
    "steps": [
        {"stage": "preprocessing", "algorithm": "detrend",
         "params": {"mode": "rolling_mean", "window_s": 600.0}},
        {"stage": "detection", "algorithm": "fluss",
         "params": {"window_s": 300.0, "n_regimes_readout": 3, "iac": "parabola", "excl_factor": 5}},
        {"stage": "detection", "algorithm": "threshold",
         "params": {"threshold": 0.46, "merge_gap_s": 1500.0, "min_duration_s": 60.0}},
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
    assert s - 2 * M <= BOUNDARY < e + 2 * M
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



# ── the calibration, pinned: jittered changes found, nulls left alone ────────

def _chain(x):
    """The template's three blocks, run directly (no database)."""
    from Adapters.registry import discover_adapters, get_adapter
    discover_adapters()
    t = np.arange(len(x), dtype=float) / FS
    value = None
    for step in TEMPLATE["steps"]:
        spec = get_adapter(f"{step['stage']}.{step['algorithm']}")
        kw = spec.validate_params(step["params"])
        res = spec.run(x, t, FS, **kw) if value is None else spec.run(x, t, FS, value=value, **kw)
        if res.output_kind == "signal":
            x = res.value.x
        else:
            value = res.value
    return value


@pytest.mark.parametrize("noise", [syn.NOISE, syn.NOISE_HIGH], ids=["noise0.05", "noise0.3"])
@pytest.mark.parametrize("seed", SEEDS)
def test_a_jittered_change_is_exactly_one_span_at_the_boundary(seed, noise):
    spans = _chain(syn.two_regimes_jittered(seed, noise))
    got = list(zip(spans.starts, spans.ends))
    assert len(got) == 1, got
    (s, e), = got
    assert s - 2 * M <= BOUNDARY < e + 2 * M


NULLS = {
    "one_regime_jittered_noise0.05": lambda s: syn.one_regime_jittered(s, syn.NOISE),
    "one_regime_jittered_noise0.3": lambda s: syn.one_regime_jittered(s, syn.NOISE_HIGH),
    "pink_noise": syn.pink_noise,
    "random_walk": syn.random_walk,
    "sinusoidal_drift": syn.sinusoidal_drift,
}


@pytest.mark.parametrize("name", sorted(NULLS))
@pytest.mark.parametrize("seed", SEEDS)
def test_a_null_recording_gives_no_span(seed, name):
    spans = _chain(NULLS[name](seed))
    assert len(spans.starts) == 0, list(zip(spans.starts, spans.ends))


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))


def test_the_shipped_template_is_the_one_tested_here():
    """The manager keeps TEMPLATE in webui/server/templates.py::EXPERIMENTAL (it did not beat its null); the two must not drift apart."""
    import os as _os
    import sys as _sys
    _root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    for _p in (_root, _os.path.join(_root, "webui")):
        if _p not in _sys.path:
            _sys.path.insert(0, _p)
    from server.templates import experimental
    assert experimental("fluss_regimes") == TEMPLATE
