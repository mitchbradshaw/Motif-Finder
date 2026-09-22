"""
test_template_dehshibi.py
===========================
The `dehshibi_spikes` TEMPLATE (stage-3 decision 2): wavelet transform →
summation → summation threshold, run end to end through `execute_recipe`
on a 30 s synthetic signal, reproduces the monolithic `detect_spikes`
detector and writes its spans to `detections`.

The canonical templates ship as code in `webui/server/templates.py` and are
seeded into the `templates` table (see `test_webui_templates.py`); this test
takes the template from the code and runs it through the ordinary executor.

Runnable standalone:  python tests/test_template_dehshibi.py
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
from Working.Detection.analysis.dehshibi_detection_analysis import detect_spikes  # noqa: E402
from Working.execution import execute_recipe  # noqa: E402
from Working.templates import apply_template  # noqa: E402
from server.templates import CANONICAL, canonical  # noqa: E402

FS = 10.0
SMALL = {"n_p": 10, "min_spike_duration": 10, "min_roi_wavelet": 5}


def synthetic(seconds=30.0, seed=0, fs=FS):
    """Two broad depolarisations each with a sharp core — the shape Algorithm 4
    confirms (an envelope region nested inside a wavelet region). Noise-free
    on purpose: a grid search over shapes found the monolithic detector
    confirms exactly this and nothing simpler (wiring report 01)."""
    n = int(fs * seconds)
    t = np.arange(n) / fs
    x = np.zeros(n)
    for centre in (0.3 * seconds, 0.7 * seconds):
        x += np.exp(-0.5 * ((t - centre) / (0.2 * seconds)) ** 2) + 0.3 * np.exp(-0.5 * ((t - centre) / (0.005 * seconds)) ** 2)
    return x


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


def test_template_runs_end_to_end_and_reproduces_the_monolith(db_and_signal):
    db, x = db_and_signal
    tpl = canonical("dehshibi_spikes")
    # the paper's sample-count defaults are for 1 Hz; the 30 s / 10 Hz synthetic needs smaller ones
    tpl["steps"][0]["params"]["min_chunk_samples"] = 2 * SMALL["n_p"]
    tpl["steps"][2]["params"].update(SMALL)
    recipe = apply_template(None, tpl, recording_id=1)
    out = execute_recipe(recipe, db_path=db, force=True)
    assert out["result"].output_kind == "spanset"
    spikes, _, _ = detect_spikes(x, fs=FS, **SMALL)
    assert len(spikes) >= 1
    got = list(zip(out["result"].value.starts, out["result"].value.ends))
    # the monolith speaks inclusive pairs; the template's last block converts to
    # SpanSet's half-open form at the seam (fixup-a item 3)
    assert got == [(s, e + 1) for s, e in spikes]
    conn = init_db(db)
    try:
        rows = list_detections(conn, out["run_id"])
    finally:
        conn.close()
    assert [(r["start_idx"], r["end_idx"]) for r in rows] == got
    assert out["detections_written"] == len(spikes)


def test_the_monolithic_adapter_is_deprecated_in_favour_of_the_template():
    from Adapters.registry import discover_adapters, get_adapter
    discover_adapters()
    spec = get_adapter("detection.dehshibi_spikes")
    assert "template" in (spec.description or "").lower()
    assert spec.category == "control", "deprecated monolith is filed under control, not detect"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
