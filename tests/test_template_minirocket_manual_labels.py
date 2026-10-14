"""
test_template_minirocket_manual_labels.py
=========================================
w2-c: the `minirocket_manual_labels` template — Window matrix on the labels'
600/200 grid (Catch22 only, the cheapest family it allows) → MiniRocket (the
upstream measures dropped, so only the fingerprint reaches the classifier) →
Manual labels (non-overlapping, labelled first) → Classifier (its `windows` side
input bound to the MiniRocket step) — run end to end through `execute_recipe` on
a synthetic recording in a temporary database whose human labels are written
into `annotations` exactly as `tests/test_catalogue_manual_labels.py` writes them.

Fix round 1 (critic finding 3, manager's decision): the template sits on the same
windows as `manual_labels_model`, so RQ1's two arms differ only in their
features. Sliding windows cannot (gap >= window): on labels spread over the
grid's three phases it keeps about a third of them, which is pinned here.

The template is defined HERE as a module-level constant (00-common.md: the
manager moves it into `webui/server/templates.py::CANONICAL` after merging).

The recording: labelled 600-sample spans on a 200-sample grid, spread over all
three phases, each holding a drop with a slow recovery (`interesting`) or a
symmetric dip (`not_interesting`) on an AR(1) background, same mean and
variance — a label learnable from the raw shape and from nothing else.

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
    "description": "RQ1's manual-label arm on a shape fingerprint: 10-minute windows on the labels' 600/200 grid "
                   "(the same windows as manual_labels_model) → MiniRocket (1,000 features, only the fingerprint "
                   "kept) → manual labels → classifier. Can this label be learned from the raw shape at all? A 'no' "
                   "at 1,000 features is not a 'no': fewer features lose real accuracy on weak shapes, and a whole "
                   "channel at 10,000 is over MiniRocket's memory guard — the decisive run is 10,000 features on a "
                   "shorter span. MiniRocket fits on every window here (Window matrix carries no split): its fit "
                   "never sees a label, so that cannot leak a label into the score. Read balanced accuracy against "
                   "the majority baseline, not plain accuracy.",
    "steps": [
        _step("preprocessing", "window_matrix", {"window_min": 10.0, "step_frac": 0.334, "slow_entropy": False,
                                                 "fast_entropy": False}),
        _step("catalogue", "minirocket", {"n_features": 1_000, "keep_upstream_features": False}),
        _step("catalogue", "manual_labels", {"non_overlapping": True}),
        _step("catalogue", "classifier", {"n_estimators": 100},
              side_inputs={"windows": {"source_kind": "earlier_step", "step_index": 1}}),
    ],
}

#: the template as it stood before fix round 1 (Sliding windows, end to end), for the grid comparison
SLIDING_STEPS = [_step("preprocessing", "sliding_windows", {"window_s": 600.0, "split_rule": "blocked_by_time"}),
                 TEMPLATE["steps"][1], TEMPLATE["steps"][2]]

L, FS = syn.L, syn.FS
GRID = 200


def _recording(n_spans=90, seed=31):
    """`(x, spans)`: labelled 600-sample spans on the 200-sample grid, 0-2 grid steps apart (so they fall on all
    three phases), a drop (interesting) or a dip (not_interesting) in each, on AR(1) everywhere."""
    rng = np.random.default_rng(seed)
    starts, s = [], 0
    for _ in range(n_spans):
        s += GRID * int(rng.integers(0, 3))
        starts.append(s)
        s += L
    n = s + L
    x = syn.ar1(n, 0.97, rng)
    x = (x - x.mean()) / x.std()
    spans = []
    for a in starts:
        k = int(rng.integers(0, 2))                  # 0 drop -> interesting, 1 dip -> not_interesting
        x[a:a + L] += syn.shape(k, rng)
        spans.append((a, a + L, "interesting" if k == 0 else "not_interesting"))
    return x, spans


@pytest.fixture
def store(monkeypatch):
    import Adapters.catalogue_classifier as clf
    import Adapters.preprocessing_window_matrix as wm
    import Working.config as cfg
    tmp = tempfile.mkdtemp(prefix="w2c_tpl_")
    monkeypatch.setattr(clf, "MODEL_ROOT", os.path.join(tmp, "models"))
    monkeypatch.setattr(wm, "RESULTS_DIR", os.path.join(tmp, "wm"))
    monkeypatch.setattr(cfg, "STEP_CACHE_ROOT", os.path.join(tmp, "cache"))
    x, spans = _recording()
    npy = os.path.join(tmp, "CH0.npy")
    np.save(npy, x)
    db = os.path.join(tmp, "t.sqlite")
    conn = init_db(db)
    q.insert_recording(conn, "syn_mr.mat", 0, FS, len(x), 0, npy)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    for a, b, verdict in spans:
        conn.execute("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
                     "VALUES (1, ?, ?, ?, 'imported_10min', ?)", (a, b, verdict, now))
    conn.commit()
    conn.close()
    try:
        yield db, x, spans
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _run(db, steps):
    recipe = apply_template(None, {**TEMPLATE, "steps": steps}, recording_id=1)
    return execute_recipe(recipe, db_path=db, force=True)["result"]


def test_the_template_is_a_training_chain_of_four_blocks_on_the_labels_grid():
    from Adapters.registry import discover_adapters
    discover_adapters()
    assert TEMPLATE["kind"] == kind_for_steps(TEMPLATE["steps"]) == "training"
    assert [f"{s['stage']}.{s['algorithm']}" for s in TEMPLATE["steps"]] == [
        "preprocessing.window_matrix", "catalogue.minirocket", "catalogue.manual_labels", "catalogue.classifier"]
    assert TEMPLATE["steps"][3]["side_inputs"]["windows"]["step_index"] == 1, \
        "the classifier trains on the MiniRocket step's feature table"
    d = TEMPLATE["description"]
    assert "is not a 'no'" in d and "shorter span" in d and "never sees a label" in d


def test_the_template_runs_end_to_end_and_learns_the_label_from_the_shape(store):
    db, _, spans = store
    res = _run(db, TEMPLATE["steps"])
    assert res.output_kind == "model"
    meta = res.meta
    assert set(meta["class_counts"]) == {0, 1}
    # the classifier saw the fingerprint (924 = 1,000 rounded down to 84s), less any column its clean-up drops
    # as constant or correlated on this recording (one, here)
    assert 900 <= meta["n_features_in"] <= 924, meta["n_features_in"]
    assert all(f.startswith("mr_") for f in meta["feature_names"]), "no Catch22 column rode through"
    assert meta["holdout_accuracy"] is not None and meta["holdout_accuracy"] >= 0.8, meta["holdout_accuracy"]
    assert os.path.isfile(res.value.path)


def test_minirocket_fits_on_every_window_here_and_says_so(store):
    db, _, _ = store
    res = _run(db, TEMPLATE["steps"][:2])
    assert res.meta["fit_on"] == "all"
    assert any("optimistic" in w for w in res.meta["warnings"])
    cols = list(res.value.features.columns)
    assert cols and all(c.startswith("mr_") for c in cols), "keep_upstream_features=False dropped Catch22"


def test_the_grid_keeps_more_labelled_windows_than_sliding_windows(store):
    db, _, spans = store
    phases = {a % L // GRID for a, _, _ in spans}
    assert phases == {0, 1, 2}, "the labels sit on all three phases of the grid"
    grid = _run(db, TEMPLATE["steps"][:3]).meta["coverage"]
    sliding = _run(db, SLIDING_STEPS).meta["coverage"]
    assert grid["labelled"] == len(spans), "on the grid every labelled span is wholly inside a kept window"
    assert sliding["labelled"] < 0.5 * len(spans), sliding["labelled"]
    assert grid["labelled"] > sliding["labelled"]


def test_the_shipped_template_is_the_one_tested_here():
    """The manager moved TEMPLATE into webui/server/templates.py::CANONICAL (it beat its label-permutation null on all three M2_aug recordings, W2-evaluation.md); the two must not drift apart."""
    import os as _os
    import sys as _sys
    _root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    for _p in (_root, _os.path.join(_root, "webui")):
        if _p not in _sys.path:
            _sys.path.insert(0, _p)
    from server.templates import canonical
    assert canonical("minirocket_manual_labels") == TEMPLATE
