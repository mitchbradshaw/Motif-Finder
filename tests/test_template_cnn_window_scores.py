"""
test_template_cnn_window_scores.py
====================================
The twelve CNN detection templates (W4-A): four trained CNNs × three window
lengths, each Sliding windows → CNN window scores → Threshold. They are
defined here as `TEMPLATES`; the managing session moves them into
`webui/server/templates.py::CANONICAL`.

All twelve run end to end through `Working.execution.execute_recipe` on a
two-hour synthetic recording in a temporary database, with `model_path`
swapped for random-weight two-class checkpoints of the same names in a temp
directory (`MODELS/` is gitignored). Random weights detect nothing in
particular, so the assertion is on the plumbing: each run ends in a SpanSet,
writes it to `detections`, and every span is a union of whole windows.

Runnable standalone:  python tests/test_template_cnn_window_scores.py
"""

import copy
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
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("torch")

import _cnn_checkpoints as ck  # noqa: E402
from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database.runs import list_detections  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.execution import execute_recipe  # noqa: E402
from Working.templates import apply_template  # noqa: E402

discover_adapters()
FS = 1.0

#: model key -> (image_type, checkpoint, what it was trained on, in plain words)
_MODELS = {
    "fusion3": ("fusion", os.path.join("MODELS", "fusion_cnn_3.pth"),
                "a fusion picture: GASF, GADF and the recurrence plot as one colour image"),
    "gadf": ("GADF", os.path.join("MODELS", "GADF_cnn.pth"),
             "a Gramian angular difference field (GADF) picture"),
    "gasf": ("GASF", os.path.join("MODELS", "GASF_cnn.pth"),
             "a Gramian angular summation field (GASF) picture"),
    "recurrence": ("recurrence", os.path.join("MODELS", "recurrence_cnn.pth"),
                   "a recurrence-plot picture"),
}
#: scale name -> window length (s)
_SCALES = {"1min": 60.0, "10min": 600.0, "60min": 3600.0}

_SCALE_WORDS = {
    "1min": "1-minute windows are outside that scale: each is stretched to 600 points, so the model sees ten "
            "times slower shapes than it learned on; read the scores as exploratory.",
    "10min": "10-minute windows are the training scale.",
    "60min": "1-hour windows are outside that scale: each is squeezed to 600 points (block means), so the model "
             "sees six times faster shapes than it learned on; read the scores as exploratory.",
}


def _template(model, scale):
    image_type, path, picture = _MODELS[model]
    window_s = _SCALES[scale]
    return {
        "name": f"cnn_{model}_{scale}",
        "kind": "detection",
        "version": 1,
        "description": (
            f"The researcher's trained CNN '{os.path.basename(path)}' slid along the recording in "
            f"{window_s / 60:g}-minute windows, marking the windows it is confident are interesting. It was "
            f"trained on 600-sample, 10-minute windows of M2_aug at 1 Hz, each turned into {picture}; every "
            f"window here is resampled to 600 points first. {_SCALE_WORDS[scale]} On M2_aug itself the scores "
            "are not out-of-sample (the model saw those recordings). Tune threshold first: 0.5 is a "
            "placeholder, not a calibrated cut; touching windows above it merge into one detection. A Discovery "
            "null of 20 surrogate draws re-runs the CNN 20 more times per channel, so it costs about 21 times "
            "one run."
        ),
        "steps": [
            {"stage": "preprocessing", "algorithm": "sliding_windows",
             "params": {"window_s": window_s, "gap_s": 0.0}},
            {"stage": "catalogue", "algorithm": "cnn_window_scores",
             "params": {"image_type": image_type, "model_path": path, "resample_to": 600}},
            {"stage": "detection", "algorithm": "threshold",
             "params": {"threshold": 0.5}},
        ],
    }


TEMPLATES = [_template(m, s) for m in _MODELS for s in _SCALES]


# ── the definitions ─────────────────────────────────────────────────────────

def test_there_are_twelve_named_cnn_model_scale():
    names = [t["name"] for t in TEMPLATES]
    assert len(names) == 12 and len(set(names)) == 12
    assert set(names) == {f"cnn_{m}_{s}" for m in ("fusion3", "gadf", "gasf", "recurrence")
                          for s in ("1min", "10min", "60min")}


@pytest.mark.parametrize("tpl", TEMPLATES, ids=lambda t: t["name"])
def test_each_is_a_three_step_detection_template_with_valid_params(tpl):
    assert tpl["kind"] == "detection" and tpl["version"] == 1
    assert [f"{s['stage']}.{s['algorithm']}" for s in tpl["steps"]] == [
        "preprocessing.sliding_windows", "catalogue.cnn_window_scores", "detection.threshold"]
    for s in tpl["steps"]:
        get_adapter(f"{s['stage']}.{s['algorithm']}").validate_params(s["params"])
    win, cnn, th = (s["params"] for s in tpl["steps"])
    assert win["gap_s"] == 0.0 and win["window_s"] in (60.0, 600.0, 3600.0)
    assert cnn["resample_to"] == 600 and th["threshold"] == 0.5
    stem = os.path.basename(cnn["model_path"]).lower()
    assert cnn["image_type"].lower() in stem


@pytest.mark.parametrize("tpl", TEMPLATES, ids=lambda t: t["name"])
def test_each_description_says_what_a_newcomer_needs(tpl):
    d = tpl["description"]
    assert "600-sample, 10-minute windows of M2_aug" in d
    assert "threshold first" in d
    assert "20 surrogate draws" in d
    if tpl["name"].endswith("10min"):
        assert "are the training scale" in d
    else:
        assert "outside that scale" in d


# ── end to end ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db_and_models():
    tmp = tempfile.mkdtemp(prefix="cnn_tpl_")
    models = ck.write_model_set(os.path.join(tmp, "MODELS"))
    rng = np.random.default_rng(0)
    n = 2 * 3600 + 137                                   # two hours and a ragged tail no window reaches
    x = np.cumsum(rng.standard_normal(n)) * 1e-4
    for c in (900, 3000, 5400):                          # three slow drops with recovery
        k = np.arange(n) - c
        x -= 5e-3 * np.where(k >= 0, np.exp(-k / 400.0), 0.0) * (k < 2400)
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
        yield db, models, n
    finally:
        cfg.STEP_CACHE_ROOT = old
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.parametrize("tpl", TEMPLATES, ids=lambda t: t["name"])
def test_each_template_runs_end_to_end_to_a_spanset(db_and_models, tpl):
    db, models, n = db_and_models
    tpl = copy.deepcopy(tpl)
    cnn = tpl["steps"][1]["params"]
    stem = os.path.basename(cnn["model_path"])
    cnn["model_path"] = next(p for p in models.values() if os.path.basename(p) == stem)
    recipe = apply_template(None, tpl, recording_id=1)
    out = execute_recipe(recipe, db_path=db, force=True)
    spans = out["result"].value
    assert out["result"].output_kind == "spanset"
    L = int(tpl["steps"][0]["params"]["window_s"] * FS)
    for s, e in zip(spans.starts, spans.ends):
        assert s % L == 0 and e % L == 0 and e <= (n // L) * L
    conn = init_db(db)
    try:
        rows = list_detections(conn, out["run_id"])
    finally:
        conn.close()
    assert len(rows) == len(spans.starts) == out["detections_written"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
