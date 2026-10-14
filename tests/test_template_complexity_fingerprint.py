"""
test_template_complexity_fingerprint.py
=======================================
w3-a: the `complexity_fingerprint` template — Detrend (rolling mean, 2 h) → Sliding windows (72 h,
gap 0) → Multiscale entropy (defaults) — run end to end through `execute_recipe` on a synthetic
73 h recording in a temporary database, as `tests/test_template_dehshibi.py` does.

The template is defined HERE as a module-level constant (00-common.md: the manager moves it into
`webui/server/templates.py::CANONICAL` after merging).

Why a 2 h detrend (measured here, `test_a_2h_detrend_...`): Costa (App. B) warns that removing a
trend reshapes multiscale structure, and that NOT removing it inflates r and collapses the curve.
A centred rolling mean of 2 h is 6x the block's largest default scale (20 min) and 28x the largest
scale a 72 h window defines (~4 min). On a stationary AR(1) with dense drops (24 h) it moves the
curve by under 0.03 nats at every defined scale; under a drift 40x the signal's SD (a ramp plus an
18 h sine) it restores the drift-free curve within 0.06, while the raw window with an SD-based r
collapses towards 0 and is flagged. 6 h behaved the same on the stationary signal (< 0.02) but left
0.7-1.1 nats of that drift in; 1 h was within 0.015 of both. Of the three, 2 h is the one that keeps
the most room above the defined scales while still removing the drift. A random-walk-like channel
keeps wandering under any detrend: the guard then flags its 1 s scale (see the core's tests).

Why 72 h windows: a scale of s seconds needs 1,000 averaged points, so a 72 h window at 1 Hz reaches
~4 min; it also gives exactly one curve for each 73 h S. commune recording. A recording shorter than
72 h gets no window: Sliding windows refuses it in words (pinned below) — lower its window_s.

Runnable standalone:  python -m pytest tests/test_template_complexity_fingerprint.py -q
"""

import os
import shutil
import sys
import tempfile

import numpy as np
import pytest
from scipy.signal import lfilter

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

from Working.Catalogue import multiscale_entropy as ME  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.execution import RecipeCancelled, RecipeExecutionError, execute_recipe  # noqa: E402
from Working.Preprocessing.detrend import make_detrend_filter  # noqa: E402
from Working.templates import apply_template  # noqa: E402
from server.templates import kind_for_steps  # noqa: E402

FS = 1.0
HOUR = 3600


def _step(stage, algorithm, params=None):
    return {"stage": stage, "algorithm": algorithm, "params": dict(params or {})}


TEMPLATE = {
    "name": "complexity_fingerprint", "kind": "training", "version": 1,
    "description": "A complexity fingerprint per recording: the slow drift is removed (a 2 h rolling mean), the "
                   "recording is cut into 72 h windows, and each window gets a multiscale-entropy curve — how "
                   "surprising the next value is after blurring the signal over 1 s, 2 s, ... minutes. Tune the "
                   "coarsest blur first (scale_max_s): a 72 h window reaches about 4 minutes, scales beyond are "
                   "blank and say so. A curve shows how irregular the signal is at each time-scale and can tell "
                   "recordings, species and conditions apart; it cannot show events, and coloured noise has a "
                   "curve of its own — compare a curve with phase-randomised copies of the same recording before "
                   "reading anything into it. A recording shorter than 72 h gets no window: shorten window_s.",
    "steps": [
        _step("preprocessing", "detrend", {"mode": "rolling_mean", "window_s": 7200.0}),
        _step("preprocessing", "sliding_windows", {"window_s": 72.0 * HOUR, "gap_s": 0.0}),
        _step("catalogue", "multiscale_entropy", {}),
    ],
}


def _drops(n, amp, seed, rec_s=300.0):
    rng = np.random.default_rng(seed)
    out = np.zeros(n)
    t = 200
    while t < n:
        out[t:] -= amp * np.exp(-np.arange(n - t) / rec_s)
        t += int(rng.uniform(1200, 3600))
    return out


def _signal(hours, seed=7, drift=True):
    n = int(hours * HOUR)
    bg = lfilter([1.0], [1.0, -0.97], np.random.default_rng(seed).standard_normal(n))
    x = bg + _drops(n, 5 * np.std(bg), seed + 1)
    if drift:
        tt = np.arange(n)
        x = x + 40 * np.std(x) * (0.6 * tt / n + 0.4 * np.sin(2 * np.pi * tt / (n / 1.3)))
    return x * 1e-3                                                    # volts, as M2 stores them


def _db(x):
    tmp = tempfile.mkdtemp(prefix="mse_tpl_")
    npy = os.path.join(tmp, "CH0.npy")
    np.save(npy, x)
    db = os.path.join(tmp, "t.sqlite")
    conn = init_db(db)
    q.insert_recording(conn, "synthetic.mat", 0, FS, len(x), 0, npy)
    conn.close()
    return tmp, db


@pytest.fixture
def cache_root():
    import Working.config as cfg
    tmp = tempfile.mkdtemp(prefix="mse_cache_")
    old = cfg.STEP_CACHE_ROOT
    cfg.STEP_CACHE_ROOT = tmp
    try:
        yield tmp
    finally:
        cfg.STEP_CACHE_ROOT = old
        shutil.rmtree(tmp, ignore_errors=True)


def test_the_template_is_a_training_chain_and_names_its_first_knob():
    assert kind_for_steps(TEMPLATE["steps"]) == TEMPLATE["kind"] == "training"
    d = TEMPLATE["description"]
    assert "scale_max_s" in d and "phase-randomised" in d and "cannot show events" in d


def test_the_template_runs_end_to_end_on_a_73_hour_recording(cache_root):
    tmp, db = _db(_signal(73))
    try:
        out = execute_recipe(apply_template(None, TEMPLATE, recording_id=1), db_path=db, force=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    r = out["result"]
    assert r.output_kind == "windowset" and r.value.n_windows == 1
    F = r.value.features
    meta = r.meta
    assert meta["n_ci_scales"] >= 8, meta["blank_scales_s"]
    assert meta["blank_scales_s"] and all(s > 250 for s in meta["blank_scales_s"])
    assert any("blank" in w for w in meta["warnings"])
    assert sum(meta["collapse"]) == 0 and not any("collapse" in w for w in meta["warnings"])
    assert np.isfinite(F["mse_ci"].iloc[0]) and F["mse_drift_share"].iloc[0] < 0.05
    assert F["mse_r"].iloc[0] < 1e-2                                   # stored units (volts), not mV


def test_a_shorter_recording_is_refused_in_words(cache_root):
    tmp, db = _db(_signal(24))
    try:
        with pytest.raises(RecipeExecutionError, match="no window fits"):
            execute_recipe(apply_template(None, TEMPLATE, recording_id=1), db_path=db, force=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_cancel_through_the_executor_is_a_cancellation_not_a_failure(cache_root):
    tmp, db = _db(_signal(73))
    try:
        with pytest.raises(RecipeCancelled):
            execute_recipe(apply_template(None, TEMPLATE, recording_id=1), db_path=db, force=True,
                           run_kwargs={"should_cancel": lambda: True})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_a_2h_detrend_keeps_the_curve_and_removes_the_drift():
    taus, _ = ME.scale_taus(FS, ME.DEFAULT_SCALE_MIN_S, ME.DEFAULT_SCALE_MAX_S, ME.DEFAULT_N_SCALES)

    def curve(x, r_scale="mad"):
        c = ME.window_curve(x, FS, taus, r_scale=r_scale)
        return np.array([s["value"] for s in c["scales"]]), [s["collapsed"] for s in c["scales"]]

    det = make_detrend_filter(FS, "rolling_mean", 7200.0)
    clean = _signal(24, drift=False)
    drifting = _signal(24, drift=True)
    base, _ = curve(clean)
    ok = np.isfinite(base)
    assert ok.sum() >= 6
    kept, _ = curve(det(clean))
    assert np.max(np.abs(kept[ok] - base[ok])) < 0.03
    restored, coll = curve(det(drifting))
    assert np.max(np.abs(restored[ok] - base[ok])) < 0.06 and not any(coll)
    raw, raw_coll = curve(drifting, r_scale="sd")
    assert np.all(raw[ok] < base[ok] - 0.5) and raw_coll[0]
