"""
test_template_minirocket_manual_labels.py
=========================================
w2-c: the `minirocket_manual_labels` template — Sliding windows (600 s, blocked
split) → MiniRocket → Manual labels → Classifier (its `windows` side input bound
to the MiniRocket step) — run end to end through `execute_recipe` on a
synthetic recording in a temporary database whose human labels are written into
`annotations` exactly as `tests/test_catalogue_manual_labels.py` writes them.

The template is defined HERE as a module-level constant (00-common.md: the
manager moves it into `webui/server/templates.py::CANONICAL` after merging).

The recording: 600-sample windows laid end to end, each a drop with a slow
recovery (labelled `interesting`) or a symmetric dip (`not_interesting`) on an
AR(1) background, same mean and variance — a label learnable from the raw shape
and from nothing else.

Runnable standalone:  python -m pytest tests/test_template_minirocket_manual_labels.py -q
"""

import datetime as _dt
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
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui"), os.path.join(PROJECT_ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _minirocket_synthetic as syn  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.execution import execute_recipe  # noqa: E402
from Working.templates import apply_template  # noqa: E402
from server.templates import kind_for_steps  # noqa: E402


def _step(stage, algorithm, params=None, side_inputs=None):
    d = {"stage": stage, "algorithm": algorithm, "params": dict(params or {})}
    if side_inputs:
        d["side_inputs"] = side_inputs
    return d


TEMPLATE = {
    "name": "minirocket_manual_labels", "kind": "training", "version": 1,
    "description": "10-minute windows with a blocked split → MiniRocket (a shape fingerprint per window, fitted on "
                   "the training windows only) → manual labels (human verdicts, containment, non-overlapping) → "
                   "classifier on the fingerprint: can this label be learned from the raw shape at all?",
    "steps": [
        _step("preprocessing", "sliding_windows", {"window_s": 600.0, "split_rule": "blocked_by_time"}),
        _step("catalogue", "minirocket", {"n_features": 1_000}),
        _step("catalogue", "manual_labels", {"non_overlapping": True}),
        _step("catalogue", "classifier", {"n_estimators": 100},
              side_inputs={"windows": {"source_kind": "earlier_step", "step_index": 1}}),
    ],
}

L, FS = syn.L, syn.FS


def _recording(n_per_class=40, seed=31):
    """Drop-with-slow-recovery (1) and symmetric-dip (0) windows end to end on AR(1); `(x, labels)`."""
    W, y = syn.windows(n_per_class=n_per_class, background_kind="ar1", noise=1.0, seed=seed)
    keep = y < 2
    W, y = W[keep], y[keep]
    return W.ravel(), np.where(y == 0, 1, 0)


@pytest.fixture
def store(monkeypatch):
    import Adapters.catalogue_classifier as clf
    import Working.config as cfg
    tmp = tempfile.mkdtemp(prefix="w2c_tpl_")
    monkeypatch.setattr(clf, "MODEL_ROOT", os.path.join(tmp, "models"))
    monkeypatch.setattr(cfg, "STEP_CACHE_ROOT", os.path.join(tmp, "cache"))
    x, labels = _recording()
    npy = os.path.join(tmp, "CH0.npy")
    np.save(npy, x)
    db = os.path.join(tmp, "t.sqlite")
    conn = init_db(db)
    q.insert_recording(conn, "syn_mr.mat", 0, FS, len(x), 0, npy)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    for i, lab in enumerate(labels):
        conn.execute("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
                     "VALUES (1, ?, ?, ?, 'imported_10min', ?)",
                     (i * L, (i + 1) * L, "interesting" if lab == 1 else "not_interesting", now))
    conn.commit()
    conn.close()
    try:
        yield db, x, labels
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_the_template_is_a_training_chain_of_four_blocks():
    from Adapters.registry import discover_adapters
    discover_adapters()
    assert TEMPLATE["kind"] == kind_for_steps(TEMPLATE["steps"]) == "training"
    assert [f"{s['stage']}.{s['algorithm']}" for s in TEMPLATE["steps"]] == [
        "preprocessing.sliding_windows", "catalogue.minirocket", "catalogue.manual_labels", "catalogue.classifier"]
    assert TEMPLATE["steps"][3]["side_inputs"]["windows"]["step_index"] == 1, \
        "the classifier trains on the MiniRocket step's feature table"


def test_the_template_runs_end_to_end_and_learns_the_label_from_the_shape(store):
    db, x, labels = store
    recipe = apply_template(None, TEMPLATE, recording_id=1)
    out = execute_recipe(recipe, db_path=db, force=True)
    res = out["result"]
    assert res.output_kind == "model"
    meta = res.meta
    assert meta["n_windows"] == len(labels)
    assert meta["n_excluded"] == 0
    assert set(meta["class_counts"]) == {0, 1}
    assert meta["n_features_in"] == 924, "the classifier saw the fingerprint (924 = 1,000 rounded down to 84s)"
    assert all(f.startswith("mr_") for f in meta["feature_names"])
    assert meta["holdout_accuracy"] is not None and meta["holdout_accuracy"] >= 0.8, meta["holdout_accuracy"]
    assert os.path.isfile(res.value.path)


def test_the_minirocket_step_fitted_on_the_training_block_only(store):
    db, _, _ = store
    steps = TEMPLATE["steps"][:2]
    recipe = apply_template(None, {**TEMPLATE, "steps": steps}, recording_id=1)
    out = execute_recipe(recipe, db_path=db, force=True)
    meta = out["result"].meta
    split = out["result"].value.features["split"].to_numpy()
    assert meta["fit_on"] == "train"
    assert meta["n_fit_windows"] == int((split == 0).sum()) < len(split)
