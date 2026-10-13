"""
test_correlation_filter_ceiling.py
==================================
w2-c fix 2 (critic finding 2): `preprocess_window_matrix`'s correlation filter
(`df.corr()` plus a Python double loop) is quadratic in columns — 13 min at
MiniRocket's 9,996 features on 60 windows — and dropped 0 MiniRocket columns at
every width the critic measured. Above `CORRELATION_FILTER_MAX_COLUMNS` (2,000)
it is skipped, the result says so, and `catalogue.classifier` /
`catalogue.cluster` print it in their meta. Below the ceiling nothing changes,
and no existing producer of a feature table reaches it.
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

from Working.Catalogue.dendrogram import dendrogram_cluster as DC  # noqa: E402


def _frame(n_cols, n_rows=40, seed=0, duplicate=True):
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n_rows, n_cols))
    if duplicate:
        X[:, 1] = X[:, 0] * 2.0 + 1.0           # r = 1 with column 0
    return pd.DataFrame(X, columns=[f"f{i:05d}" for i in range(n_cols)])


def test_the_ceiling_is_2000_columns():
    assert DC.CORRELATION_FILTER_MAX_COLUMNS == 2_000


def test_over_the_ceiling_the_filter_is_skipped_and_the_result_says_so():
    r = DC.preprocess_window_matrix(_frame(2_001))
    assert "f00001" in r.feature_names, "the duplicate survives: the filter did not run"
    assert r.correlation_filter_skipped == 2_001
    assert r.removed_summary.get("correlated", []) == []


def test_under_the_ceiling_the_filter_runs_as_before(monkeypatch):
    r = DC.preprocess_window_matrix(_frame(30))
    assert "f00001" not in r.feature_names
    assert r.correlation_filter_skipped is None
    monkeypatch.setattr(DC, "CORRELATION_FILTER_MAX_COLUMNS", 29)
    r2 = DC.preprocess_window_matrix(_frame(30))
    assert "f00001" in r2.feature_names and r2.correlation_filter_skipped == 30


def test_no_existing_window_matrix_reaches_the_ceiling():
    """Every Window matrix family switched on together is far under 2,000 columns, so every chain that
    existed before MiniRocket runs the filter exactly as it did."""
    from Working.database import window_matrix_store as store
    total = sum(len(list(store.STAGE_COLUMNS[s]())) for s in store.ALL_STAGES)
    assert total < DC.CORRELATION_FILTER_MAX_COLUMNS, total


def _windows_and_grouping(n_cols, n_rows=40):
    from Working.types import Grouping, WindowSet
    feats = _frame(n_cols, n_rows)
    ws = WindowSet(starts=np.arange(n_rows, dtype=np.int64) * 10, length=10, fs=1.0, features=feats)
    labels = np.arange(n_rows) % 2
    return ws, Grouping(labels=labels)


def test_the_classifier_meta_says_the_filter_was_skipped(monkeypatch, tmp_path):
    import Adapters.catalogue_classifier as clf
    monkeypatch.setattr(clf, "MODEL_ROOT", str(tmp_path / "models"))
    monkeypatch.setattr(DC, "CORRELATION_FILTER_MAX_COLUMNS", 20)
    ws, g = _windows_and_grouping(25)
    meta = clf._run(None, None, 1.0, n_estimators=5, value=g, windows=ws).meta
    assert meta["correlation_filter"] == "skipped: 25 columns (over 20; the filter is quadratic in columns)"
    ws2, g2 = _windows_and_grouping(15)
    assert clf._run(None, None, 1.0, n_estimators=5, value=g2, windows=ws2).meta["correlation_filter"] == "applied"


def test_the_cluster_meta_says_the_filter_was_skipped(monkeypatch):
    import Adapters.catalogue_cluster as cl
    monkeypatch.setattr(DC, "CORRELATION_FILTER_MAX_COLUMNS", 20)
    ws, _ = _windows_and_grouping(25)
    meta = cl._run(None, None, 1.0, k=2, value=ws).meta
    assert meta["correlation_filter"].startswith("skipped: 25 columns")
