"""
test_template_event_families.py
=================================
The `event_families` TEMPLATE (w2-e): the `noise_threshold` template's two
steps (baseline removal -> noise threshold) -> Event shape -> Event families
(HDBSCAN, defaults; `group = family`) -> Intervals, run end to end through
`execute_recipe` on a synthetic recording in a temporary database: inverted
sharkfins every 40 min and square dips every 3 h on an AR(1) background.

Acceptance: both families recovered (ARI >= 0.9 against the planted shapes),
and Intervals reports each family's own median gap within 10 % of its rhythm.

`TEMPLATE` is defined here; the manager moves it into
`webui/server/templates.py::CANONICAL` after merging.
"""

import os
import shutil
import sys
import tempfile

import numpy as np
import pytest
from sklearn.metrics import adjusted_rand_score

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui"), os.path.join(PROJECT_ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from _event_families_synthetic import (SHARK_GAP_S, SQUARE_GAP_S, truth_of,  # noqa: E402
                                       two_rhythms)
from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.execution import execute_recipe  # noqa: E402
from Working.templates import apply_template  # noqa: E402


def _step(stage, algorithm, params=None):
    return {"stage": stage, "algorithm": algorithm, "params": dict(params or {})}


TEMPLATE = {
    "name": "event_families", "kind": "interrogation", "version": 1,
    "description": "Families of detected events, each timed on its own — 'do family A events come every 40 "
                   "minutes and family B every 3 hours?' in one chain: baseline removal → noise threshold (every "
                   "stretch more than 4 σ_n below the detrended trace's median, as the noise_threshold template) → "
                   "Event shape → Event families (a window around each event, grouped by shape with the Library's "
                   "HDBSCAN; events in no dense family are left out, and a family no better than phase-randomised "
                   "noise of the same colour is flagged; each event's family becomes its group) → Intervals (the "
                   "gaps between events of the SAME family: one rhythm per family). Tune Event families' minimum "
                   "family size first; read each family's noise flag and SVD entropy beside its null before its "
                   "rhythm.",
    "steps": [
        _step("preprocessing", "detrend", {"mode": "rolling_mean", "window_s": 600.0}),
        _step("detection", "noise_threshold", {"k_sigma": 4.0, "direction": "below",
                                               "min_duration_s": 30.0, "merge_gap_s": 60.0}),
        _step("interrogation", "event_shape", {}),
        _step("interrogation", "event_families", {"method": "hdbscan"}),
        _step("interrogation", "intervals", {}),
    ],
}

FS = 1.0


def _db(tmp, x):
    npy = os.path.join(tmp, "rec.npy")
    np.save(npy, x)
    db = os.path.join(tmp, "rec.sqlite")
    conn = init_db(db)
    q.insert_recording(conn, "rec.mat", 0, FS, len(x), 0, npy, units="V")
    conn.close()
    return db


@pytest.fixture(scope="module")
def ran():
    tmp = tempfile.mkdtemp(prefix="evfam_tpl_")
    import Working.config as cfg
    old = cfg.STEP_CACHE_ROOT
    cfg.STEP_CACHE_ROOT = os.path.join(tmp, "cache")
    try:
        x, sharks, squares = two_rhythms(hours=48, seed=0)
        db = _db(tmp, x)
        out = execute_recipe(apply_template(None, TEMPLATE, recording_id=1), db_path=db, force=True)
        yield out, sharks, squares
    finally:
        cfg.STEP_CACHE_ROOT = old
        shutil.rmtree(tmp, ignore_errors=True)


def test_template_is_the_noise_threshold_chain_then_shape_families_intervals():
    assert [f"{s['stage']}.{s['algorithm']}" for s in TEMPLATE["steps"]] == [
        "preprocessing.detrend", "detection.noise_threshold", "interrogation.event_shape",
        "interrogation.event_families", "interrogation.intervals"]
    from server.templates import canonical, kind_for_steps
    assert TEMPLATE["steps"][:2] == canonical("noise_threshold")["steps"], "the first two steps ARE noise_threshold"
    assert kind_for_steps(TEMPLATE["steps"]) == TEMPLATE["kind"]
    from Adapters.registry import discover_adapters, get_adapter
    discover_adapters()
    for s in TEMPLATE["steps"]:
        get_adapter(f"{s['stage']}.{s['algorithm']}").validate_params(s["params"])


def test_the_estimate_is_far_inside_the_analyse_limit():
    from Adapters.registry import discover_adapters, get_adapter
    discover_adapters()
    spec = get_adapter("interrogation.event_families")
    n = 48 * 3600
    sec = spec.estimate(np.zeros(n), np.arange(n, dtype=float), FS, **spec.validate_params({"method": "hdbscan"}))
    assert 0 < sec < 60


def test_both_families_are_recovered(ran):
    out, sharks, squares = ran
    spans = out["result"].value
    f = spans.features
    truth = truth_of(np.asarray(spans.starts), sharks, squares)
    assert len(spans.starts) >= 0.9 * (len(sharks) + len(squares))
    fam = f["family"].to_numpy()
    assert adjusted_rand_score(truth, fam) >= 0.9, (adjusted_rand_score(truth, fam), f["family_omit_reason"].value_counts())
    assert len(set(fam[fam > 0])) == 2


def test_intervals_reports_each_familys_own_rhythm_within_ten_percent(ran):
    out, sharks, squares = ran
    spans = out["result"].value
    f = spans.features
    truth = truth_of(np.asarray(spans.starts), sharks, squares)
    stats = out["result"].meta["interval_stats"]
    for shape, rhythm in ((0, SHARK_GAP_S), (1, SQUARE_GAP_S)):
        groups = f["group"][truth == shape]
        key = groups.mode().iloc[0]
        assert key != "-1"
        med = stats[key]["median_s"]
        assert med == pytest.approx(rhythm, rel=0.10), (shape, key, med, rhythm)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
