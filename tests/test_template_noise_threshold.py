"""
test_template_noise_threshold.py
==================================
The `noise_threshold` TEMPLATE: baseline removal → `detection.noise_threshold`
at 4 σ_n below the baseline, run end to end through `execute_recipe` on a
synthetic recording in a temporary database. Its spans are written to
`detections`, and the same recording stored in millivolts instead of volts
gives the same spans with the same template — nothing in the chain names a
level in either unit.

`TEMPLATE` is defined here; the manager moves it into
`webui/server/templates.py::CANONICAL` after merging.

Runnable standalone:  python tests/test_template_noise_threshold.py
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
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

from Working.database import queries as q  # noqa: E402
from Working.database.runs import list_detections  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.execution import execute_recipe  # noqa: E402
from Working.templates import apply_template  # noqa: E402


def _step(stage, algorithm, params=None):
    return {"stage": stage, "algorithm": algorithm, "params": dict(params or {})}


TEMPLATE = {
    "name": "noise_threshold", "kind": "detection", "version": 1,
    "description": "Baseline → noise threshold: every stretch of the detrended trace more than 4 σ_n below its "
                   "median, σ_n = median|x − median(x)| / 0.6745 (Quian Quiroga et al. 2004). The cut is in "
                   "multiples of the channel's own noise, so the same template runs on a trace stored in V or mV.",
    "steps": [
        _step("preprocessing", "detrend", {"mode": "rolling_mean", "window_s": 600.0}),
        _step("detection", "noise_threshold", {"k_sigma": 4.0, "direction": "below",
                                               "min_duration_s": 30.0, "merge_gap_s": 60.0}),
    ],
}

FS = 1.0
#: three 60 s drops of 20 mV on a -0.44 V baseline (M2 is stored in volts), far enough apart
#: for a 600 s rolling mean to sit between them — the same recording as the signal_threshold template test
DROPS = [(600, 660), (1500, 1560), (2400, 2460)]


def synthetic():
    rng = np.random.default_rng(3)
    x = -0.44 + 0.0002 * rng.standard_normal(3000) + 0.002 * np.sin(np.arange(3000) / 900.0)
    for a, b in DROPS:
        x[a:b] -= 0.02
    return x


def _db(tmp, x, units, name):
    npy = os.path.join(tmp, f"{name}.npy")
    np.save(npy, x)
    db = os.path.join(tmp, f"{name}.sqlite")
    conn = init_db(db)
    q.insert_recording(conn, f"{name}.mat", 0, FS, len(x), 0, npy, units=units)
    conn.close()
    return db


@pytest.fixture
def tmpdir_cache():
    tmp = tempfile.mkdtemp(prefix="noisethr_tpl_")
    import Working.config as cfg
    old = cfg.STEP_CACHE_ROOT
    cfg.STEP_CACHE_ROOT = os.path.join(tmp, "cache")
    try:
        yield tmp
    finally:
        cfg.STEP_CACHE_ROOT = old
        shutil.rmtree(tmp, ignore_errors=True)


def iou(a, b):
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union


def test_template_is_a_two_block_detection_chain_with_no_absolute_level():
    assert TEMPLATE["kind"] == "detection"
    assert [f"{s['stage']}.{s['algorithm']}" for s in TEMPLATE["steps"]] == [
        "preprocessing.detrend", "detection.noise_threshold"]
    cut = TEMPLATE["steps"][1]["params"]
    assert cut == {"k_sigma": 4.0, "direction": "below", "min_duration_s": 30.0, "merge_gap_s": 60.0}
    from Adapters.registry import discover_adapters, get_adapter
    discover_adapters()
    for s in TEMPLATE["steps"]:
        get_adapter(f"{s['stage']}.{s['algorithm']}").validate_params(s["params"])


def test_template_runs_end_to_end_and_writes_its_spans(tmpdir_cache):
    x = synthetic()
    db = _db(tmpdir_cache, x, "V", "volts")
    recipe = apply_template(None, TEMPLATE, recording_id=1)
    out = execute_recipe(recipe, db_path=db, force=True)
    res = out["result"]
    assert res.output_kind == "spanset"
    got = list(zip(res.value.starts, res.value.ends))
    assert len(got) == len(DROPS), got
    for span, drop in zip(got, DROPS):
        assert iou(span, drop) >= 0.8, (span, drop)
    assert all(s > 0 for s in res.value.scores), "a span scores by how many σ_n past the cut it went"
    assert res.meta["cut_below"] < res.meta["centre"]
    conn = init_db(db)
    try:
        rows = list_detections(conn, out["run_id"])
    finally:
        conn.close()
    assert [(r["start_idx"], r["end_idx"]) for r in rows] == got
    assert out["detections_written"] == len(got)


def test_the_same_template_finds_the_same_spans_in_millivolts(tmpdir_cache):
    x = synthetic()
    v = execute_recipe(apply_template(None, TEMPLATE, recording_id=1),
                       db_path=_db(tmpdir_cache, x, "V", "volts"), force=True)
    mv = execute_recipe(apply_template(None, TEMPLATE, recording_id=1),
                        db_path=_db(tmpdir_cache, x * 1000.0, "mV", "millivolts"), force=True)
    assert list(zip(v["result"].value.starts, v["result"].value.ends)) == \
        list(zip(mv["result"].value.starts, mv["result"].value.ends))


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))


def test_the_shipped_template_is_the_one_tested_here():
    """The manager moved TEMPLATE into webui/server/templates.py::CANONICAL; the two must not drift apart."""
    import os as _os
    import sys as _sys
    _root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    for _p in (_root, _os.path.join(_root, "webui")):
        if _p not in _sys.path:
            _sys.path.insert(0, _p)
    from server.templates import canonical
    assert canonical("noise_threshold") == TEMPLATE
