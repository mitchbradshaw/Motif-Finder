"""
test_all_nan_feature_rows.py
============================
w3-a fix round 1 (critic F3, manager decision 7): a window whose features are all NaN once the
bookkeeping columns are dropped — a window a feature block left out (Multiscale entropy's gap,
flat or over-filled windows) — is never fitted, imputed or scored by `catalogue.cluster` or
`catalogue.classifier`. It is left out, counted in `meta` and the summary line, and gets the "no
label / not scored" value each block already uses (label -1: the value `catalogue.manual_labels`
gives an excluded window and the classifier already skips).

Before this, `preprocess_window_matrix` median-imputed such a row and the cluster block labelled it
like an average window, saying nothing.

Runnable standalone:  python -m pytest tests/test_all_nan_feature_rows.py -q
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.types import Grouping, WindowSet  # noqa: E402

discover_adapters()

N = 40
LEFT_OUT = [5, 17, 30]


def _windows():
    rng = np.random.default_rng(0)
    a = np.r_[rng.normal(0, 1, N // 2), rng.normal(6, 1, N // 2)]
    b = np.r_[rng.normal(0, 1, N // 2), rng.normal(-6, 1, N // 2)]
    c = rng.normal(0, 1, N)
    feats = pd.DataFrame({"split": np.zeros(N, dtype=int), "f_a": a, "f_b": b, "f_c": c,
                          "mse_r": np.full(N, 1e-3), "mse_n_scales": np.full(N, 7.0)})
    feats.loc[LEFT_OUT, ["f_a", "f_b", "f_c", "mse_r"]] = np.nan     # left out upstream: only bookkeeping survives
    feats.loc[LEFT_OUT, "mse_n_scales"] = np.nan
    return WindowSet(starts=np.arange(N) * 100, length=100, fs=1.0, features=feats)


def test_cluster_leaves_all_nan_rows_out_labels_them_minus_one_and_counts_them():
    spec = get_adapter("catalogue.cluster")
    ws = _windows()
    r = spec.run(np.zeros(10), np.arange(10.0), 1.0, **spec.validate_params({"k": 2}), value=ws)
    labels = np.asarray(r.value.labels)
    assert len(labels) == N
    assert (labels[LEFT_OUT] == -1).all()
    keep = np.setdiff1d(np.arange(N), LEFT_OUT)
    assert (labels[keep] >= 1).all()
    assert r.meta["n_left_out"] == len(LEFT_OUT)
    assert "3 of 40" in r.meta["left_out_reason"] and "3 of 40" in r.meta["summary"]
    assert r.meta["n_windows"] == N and r.meta["n_clustered"] == N - len(LEFT_OUT)
    # the kept rows cluster exactly as they would alone
    alone = WindowSet(starts=ws.starts[keep], length=100, fs=1.0,
                      features=ws.features.iloc[keep].reset_index(drop=True))
    r2 = spec.run(np.zeros(10), np.arange(10.0), 1.0, **spec.validate_params({"k": 2}), value=alone)
    assert np.array_equal(labels[keep], np.asarray(r2.value.labels))
    assert -1 not in r.meta["cluster_counts"]


def test_cluster_without_left_out_rows_is_unchanged():
    spec = get_adapter("catalogue.cluster")
    ws = _windows()
    full = ws.features.copy()
    full.loc[LEFT_OUT, ["f_a", "f_b", "f_c"]] = 0.0
    ws2 = WindowSet(starts=ws.starts, length=100, fs=1.0, features=full)
    r = spec.run(np.zeros(10), np.arange(10.0), 1.0, **spec.validate_params({"k": 2}), value=ws2)
    assert r.meta["n_left_out"] == 0 and r.meta["left_out_reason"] is None
    assert (np.asarray(r.value.labels) >= 1).all()


def test_classifier_never_fits_or_scores_an_all_nan_row(tmp_path, monkeypatch):
    import Adapters.catalogue_classifier as C
    monkeypatch.setattr(C, "MODEL_ROOT", str(tmp_path))
    spec = get_adapter("catalogue.classifier")
    ws = _windows()
    labels = np.r_[np.zeros(N // 2, dtype=int), np.ones(N // 2, dtype=int)]
    r = spec.run(np.zeros(10), np.arange(10.0), 1.0,
                 **spec.validate_params({"n_estimators": 20, "holdout_frac": 0.25}),
                 value=Grouping(labels=labels), windows=ws)
    m = r.meta
    assert m["n_no_features"] == len(LEFT_OUT)
    assert m["n_train"] + m["n_holdout"] == N - len(LEFT_OUT)
    assert sum(m["class_counts"].values()) == N - len(LEFT_OUT)
    assert "3 of 40" in m["no_features_reason"] and "3 of 40" in m["summary"]


def test_classifier_counts_grouping_exclusions_and_all_nan_rows_apart(tmp_path, monkeypatch):
    import Adapters.catalogue_classifier as C
    monkeypatch.setattr(C, "MODEL_ROOT", str(tmp_path))
    spec = get_adapter("catalogue.classifier")
    ws = _windows()
    labels = np.r_[np.zeros(N // 2, dtype=int), np.ones(N // 2, dtype=int)]
    labels[[0, 1]] = -1
    r = spec.run(np.zeros(10), np.arange(10.0), 1.0,
                 **spec.validate_params({"n_estimators": 20, "holdout_frac": 0.25}),
                 value=Grouping(labels=labels), windows=ws)
    assert r.meta["n_excluded"] == 2 and r.meta["n_no_features"] == len(LEFT_OUT)
    assert r.meta["n_train"] + r.meta["n_holdout"] == N - 2 - len(LEFT_OUT)


def test_classifier_refuses_when_every_row_is_empty(tmp_path, monkeypatch):
    import Adapters.catalogue_classifier as C
    monkeypatch.setattr(C, "MODEL_ROOT", str(tmp_path))
    spec = get_adapter("catalogue.classifier")
    ws = _windows()
    feats = ws.features.copy()
    feats[["f_a", "f_b", "f_c", "mse_r"]] = np.nan
    ws = WindowSet(starts=ws.starts, length=100, fs=1.0, features=feats)
    with pytest.raises(ValueError, match="no features"):
        spec.run(np.zeros(10), np.arange(10.0), 1.0, **spec.validate_params({}),
                 value=Grouping(labels=np.r_[np.zeros(20, int), np.ones(20, int)]), windows=ws)
