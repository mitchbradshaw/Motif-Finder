"""
test_template_dehshibi.py
===========================
The `dehshibi_spikes` TEMPLATE (stage-3 decision 2): wavelet transform →
summation → summation threshold, run end to end through `execute_recipe`
with its DEFAULT parameters on a synthetic recording with known events,
reproduces what the authors' MATLAB returned on that recording
(`tests/fixtures/dehshibi/reference.json`; fixup-J, Q33), agrees with the
core's `detect_spikes`, and writes its spans to `detections`.

The canonical templates ship as code in `webui/server/templates.py` and are
seeded into the `templates` table (see `test_webui_templates.py`); this test
takes the template from the code and runs it through the ordinary executor.

Runnable standalone:  python tests/test_template_dehshibi.py
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
from Working.Detection.analysis.dehshibi_authors import detect_spikes  # noqa: E402
from Working.execution import execute_recipe  # noqa: E402
from Working.templates import apply_template  # noqa: E402
from server.templates import CANONICAL, canonical  # noqa: E402

FS = 1.0

with open(os.path.join(PROJECT_ROOT, "tests", "fixtures", "dehshibi", "reference.json")) as _f:
    CASE = json.load(_f)["cases"]["a"]


def synthetic():
    """3000 s at 1 Hz with six injected events; the authors' code finds five."""
    return np.asarray(CASE["x"], dtype=float)


@pytest.fixture
def db_and_signal():
    tmp = tempfile.mkdtemp(prefix="dehshibi_tpl_")
    x = synthetic()
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
        yield db, x
    finally:
        cfg.STEP_CACHE_ROOT = old
        shutil.rmtree(tmp, ignore_errors=True)


def test_dehshibi_is_a_canonical_detection_template_of_three_blocks():
    tpl = canonical("dehshibi_spikes")
    assert tpl["kind"] == "detection"
    assert [f"{s['stage']}.{s['algorithm']}" for s in tpl["steps"]] == [
        "preprocessing.wavelet_transform", "detection.wavelet_summation", "detection.summation_threshold"]
    assert "dehshibi_spikes" in {t["name"] for t in CANONICAL}


def test_template_runs_end_to_end_and_reproduces_the_authors(db_and_signal):
    db, x = db_and_signal
    tpl = canonical("dehshibi_spikes")          # default parameters: nothing to tune for a 1 Hz recording
    recipe = apply_template(None, tpl, recording_id=1)
    out = execute_recipe(recipe, db_path=db, force=True)
    assert out["result"].output_kind == "spanset"
    got = list(zip(out["result"].value.starts, out["result"].value.ends))
    # MATLAB speaks 1-based inclusive pairs, SpanSet 0-based half-open
    assert got == [(a - 1, b) for a, b in CASE["spikes"]]
    assert len(got) == 5
    spikes, _, _ = detect_spikes(x, fs=FS)
    assert got == [(s, e + 1) for s, e in spikes], "the template and the core's one-call detector disagree"
    conn = init_db(db)
    try:
        rows = list_detections(conn, out["run_id"])
    finally:
        conn.close()
    assert [(r["start_idx"], r["end_idx"]) for r in rows] == got
    assert out["detections_written"] == len(got)


def test_the_monolith_adapter_agrees_with_the_template(db_and_signal):
    """Two entry points, one detector (fixup-J report 2.1)."""
    from Adapters.registry import discover_adapters, get_adapter
    discover_adapters()
    _, x = db_and_signal
    spec = get_adapter("detection.dehshibi_spikes")
    r = spec.run(x, np.arange(len(x), dtype=float), FS, **spec.validate_params({}))
    assert list(zip(r.value.starts, r.value.ends)) == [(a - 1, b) for a, b in CASE["spikes"]]


def test_the_monolithic_adapter_is_deprecated_in_favour_of_the_template():
    from Adapters.registry import discover_adapters, get_adapter
    discover_adapters()
    spec = get_adapter("detection.dehshibi_spikes")
    assert "template" in (spec.description or "").lower()
    assert spec.category == "control", "deprecated monolith is filed under control, not detect"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
