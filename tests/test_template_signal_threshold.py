"""
test_template_signal_threshold.py
===================================
The `signal_threshold` TEMPLATE: baseline removal → `detection.signal_threshold`,
the simplest detector the tool can express — a level on the detrended trace —
run end to end through `execute_recipe` on a synthetic 1 Hz recording with three
injected drops, and its spans written to `detections`.

The canonical templates ship as code in `webui/server/templates.py` and are
seeded into the `templates` table (see `test_webui_templates.py`); this test
takes the template from the code and runs it through the ordinary executor.

Runnable standalone:  python tests/test_template_signal_threshold.py
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
from server.templates import CANONICAL, canonical  # noqa: E402

FS = 1.0
#: three 60 s drops of 20 mV on a -0.44 V baseline (M2 is stored in volts), far enough apart
#: for a 600 s rolling mean to sit between them
DROPS = [(600, 660), (1500, 1560), (2400, 2460)]


def synthetic():
    rng = np.random.default_rng(3)
    x = -0.44 + 0.0002 * rng.standard_normal(3000) + 0.002 * np.sin(np.arange(3000) / 900.0)
    for a, b in DROPS:
        x[a:b] -= 0.02
    return x


@pytest.fixture
def db_and_signal():
    tmp = tempfile.mkdtemp(prefix="sigthr_tpl_")
    x = synthetic()
    npy = os.path.join(tmp, "CH0.npy")
    np.save(npy, x)
    db = os.path.join(tmp, "t.sqlite")
    conn = init_db(db)
    q.insert_recording(conn, "synthetic.mat", 0, FS, len(x), 0, npy, units="V")
    conn.close()
    import Working.config as cfg
    old = cfg.STEP_CACHE_ROOT
    cfg.STEP_CACHE_ROOT = os.path.join(tmp, "cache")
    try:
        yield db, x
    finally:
        cfg.STEP_CACHE_ROOT = old
        shutil.rmtree(tmp, ignore_errors=True)


def iou(a, b):
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union


def test_signal_threshold_is_a_canonical_detection_template_of_two_blocks():
    tpl = canonical("signal_threshold")
    assert tpl["kind"] == "detection"
    assert [f"{s['stage']}.{s['algorithm']}" for s in tpl["steps"]] == [
        "preprocessing.detrend", "detection.signal_threshold"]
    cut = tpl["steps"][1]["params"]
    assert cut["direction"] == "below" and cut["threshold"] < 0, "the shipped default looks for drops under the baseline"
    assert "signal_threshold" in {t["name"] for t in CANONICAL}


def test_template_runs_end_to_end_and_writes_its_spans(db_and_signal):
    db, x = db_and_signal
    tpl = canonical("signal_threshold")
    recipe = apply_template(None, tpl, recording_id=1)
    out = execute_recipe(recipe, db_path=db, force=True)
    assert out["result"].output_kind == "spanset"
    got = list(zip(out["result"].value.starts, out["result"].value.ends))
    assert len(got) == len(DROPS), got
    for span, drop in zip(got, DROPS):
        assert iou(span, drop) >= 0.8, (span, drop)
    assert all(s > 0 for s in out["result"].value.scores), "a span scores by how far under the cut it went"
    conn = init_db(db)
    try:
        rows = list_detections(conn, out["run_id"])
    finally:
        conn.close()
    assert [(r["start_idx"], r["end_idx"]) for r in rows] == got
    assert out["detections_written"] == len(got)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
