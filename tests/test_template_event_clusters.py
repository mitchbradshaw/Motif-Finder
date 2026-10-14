"""
test_template_event_clusters.py
=================================
The `event_clusters` TEMPLATE (w2-a): the `noise_threshold` template's two steps
(baseline removal -> noise threshold) -> Event shape -> Event windows -> Hierarchical
cluster on the carried Event-shape measures, run end to end through `execute_recipe`
on a synthetic recording in a temporary database: drops of three depths every 30 min
on an AR(1) background (phi = 0.97).

`TEMPLATE` is defined here; the manager moves it into
`webui/server/templates.py::CANONICAL` after merging.

Runnable standalone:  python tests/test_template_event_clusters.py
"""

import os
import shutil
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui"), os.path.join(PROJECT_ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from _event_windows_synthetic import chain  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.execution import execute_recipe  # noqa: E402
from Working.templates import apply_template  # noqa: E402


def _step(stage, algorithm, params=None):
    return {"stage": stage, "algorithm": algorithm, "params": dict(params or {})}


TEMPLATE = {
    "name": "event_clusters", "kind": "training", "version": 1,
    "description": "Detected events grouped by their shape measures: baseline removal → noise threshold (every "
                   "stretch more than 4 σ_n below the detrended trace's median, as the noise_threshold template) → "
                   "Event shape (amplitude, width, duration, FWHM, recovery, slopes per event) → Event windows (one "
                   "window around each event, its onset 20 % of the way in; length twice the median event "
                   "duration; a blocked-by-time split) → Hierarchical cluster (Ward, k = 3) on the measures each "
                   "window carries. Set k first: it is how many kinds of event you expect.",
    "steps": [
        _step("preprocessing", "detrend", {"mode": "rolling_mean", "window_s": 600.0}),
        _step("detection", "noise_threshold", {"k_sigma": 4.0, "direction": "below",
                                               "min_duration_s": 30.0, "merge_gap_s": 60.0}),
        _step("interrogation", "event_shape", {}),
        _step("catalogue", "event_windows", {}),
        _step("catalogue", "cluster", {}),
    ],
}

FS = 1.0
DEPTHS = [0.008, 0.02, 0.045]  # three kinds of drop: 8, 20 and 45 mV, on a -0.44 V (M2 volts) baseline
N_EVENTS = 15


def synthetic():
    return chain("ar1", n_events=N_EVENTS, spacing_s=1800, first=1500, depths=DEPTHS, seed=4)


def _db(tmp, x):
    npy = os.path.join(tmp, "rec.npy")
    np.save(npy, x)
    db = os.path.join(tmp, "rec.sqlite")
    conn = init_db(db)
    q.insert_recording(conn, "rec.mat", 0, FS, len(x), 0, npy, units="V")
    conn.close()
    return db


@pytest.fixture
def tmpdir_cache():
    tmp = tempfile.mkdtemp(prefix="evclus_tpl_")
    import Working.config as cfg
    old = cfg.STEP_CACHE_ROOT
    cfg.STEP_CACHE_ROOT = os.path.join(tmp, "cache")
    try:
        yield tmp
    finally:
        cfg.STEP_CACHE_ROOT = old
        shutil.rmtree(tmp, ignore_errors=True)


def test_template_is_the_noise_threshold_chain_then_shape_windows_cluster():
    assert [f"{s['stage']}.{s['algorithm']}" for s in TEMPLATE["steps"]] == [
        "preprocessing.detrend", "detection.noise_threshold", "interrogation.event_shape",
        "catalogue.event_windows", "catalogue.cluster"]
    from server.templates import canonical, kind_for_steps
    assert TEMPLATE["steps"][:2] == canonical("noise_threshold")["steps"], "the first two steps ARE noise_threshold"
    assert kind_for_steps(TEMPLATE["steps"]) == TEMPLATE["kind"] == "training"
    from Adapters.registry import discover_adapters, get_adapter
    discover_adapters()
    for s in TEMPLATE["steps"]:
        get_adapter(f"{s['stage']}.{s['algorithm']}").validate_params(s["params"])


def test_template_runs_end_to_end_and_groups_the_events_by_depth(tmpdir_cache):
    x, onsets = synthetic()
    db = _db(tmpdir_cache, x)
    out = execute_recipe(apply_template(None, TEMPLATE, recording_id=1), db_path=db, force=True)
    res = out["result"]
    assert res.output_kind == "grouping"
    labels = np.asarray(res.value.labels)
    assert len(labels) >= N_EVENTS - 2, len(labels)
    # the windows' features: the Event-shape measures survived the bridge
    windows = execute_recipe(apply_template(None, {**TEMPLATE, "steps": TEMPLATE["steps"][:4]}, recording_id=1),
                             db_path=db, force=True)["result"]
    ws = windows.value
    assert "event_amplitude_mv" in ws.features.columns and "onset_win" in ws.features.columns
    assert len(labels) == ws.n_windows
    # each depth class lands in one cluster: depth is the dominant measure difference between events
    k = ws.features["event_index"].to_numpy()
    starts = (ws.starts + ws.features["anchor_offset"].to_numpy())
    depth_of = []
    for s in starts:
        i = int(np.argmin(np.abs(np.asarray(onsets) - s)))
        depth_of.append(DEPTHS[i % len(DEPTHS)])
    for d in DEPTHS:
        got = set(labels[np.asarray(depth_of) == d])
        assert len(got) == 1, (d, got)
    assert len(set(labels)) == 3
    assert len(k) == len(labels)


def test_on_a_span_that_does_not_start_at_zero_the_windows_are_channel_absolute(tmpdir_cache):
    x, onsets = synthetic()
    db = _db(tmpdir_cache, x)
    span = (4000, len(x))
    recipe = apply_template(None, {**TEMPLATE, "steps": TEMPLATE["steps"][:4]}, recording_id=1, span=span)
    ws = execute_recipe(recipe, db_path=db, force=True)["result"].value
    assert ws.n_windows >= 10
    anchors = ws.starts + ws.features["anchor_offset"].to_numpy()
    inside = [o for o in onsets if o > span[0]]
    for a in anchors:
        # the onset Event shape found, in channel samples, lies within a minute of a planted onset
        assert min(abs(a - o) for o in inside) <= 60, a


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))


def test_the_shipped_template_is_the_one_tested_here():
    """The manager keeps TEMPLATE in webui/server/templates.py::EXPERIMENTAL (it did not beat its null, W2-evaluation.md); the two must not drift apart."""
    import os as _os
    import sys as _sys
    _root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    for _p in (_root, _os.path.join(_root, "webui")):
        if _p not in _sys.path:
            _sys.path.insert(0, _p)
    from server.templates import experimental
    assert experimental("event_clusters") == TEMPLATE
