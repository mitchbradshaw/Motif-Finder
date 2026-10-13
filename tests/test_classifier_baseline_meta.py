"""
test_classifier_baseline_meta.py
================================
w2-c fix 4 (critic finding 4): plain holdout accuracy on imbalanced labels reads
as learning when nothing was learned (0.66 against a 0.67 majority class).
`catalogue.classifier`'s meta carries `balanced_accuracy` (the mean of the
per-class accuracies) and `majority_baseline` (the holdout's majority-class
share) beside `holdout_accuracy` — outputs only: no parameter, no hash change.
"""

import os
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.types import Grouping, WindowSet  # noqa: E402


def _inputs(n=120, seed=0):
    rng = np.random.default_rng(seed)
    labels = (np.arange(n) % 3 == 0).astype(int)              # one third class 1: imbalanced
    feats = pd.DataFrame(rng.standard_normal((n, 6)), columns=[f"f{i}" for i in range(6)])   # no signal
    ws = WindowSet(starts=np.arange(n, dtype=np.int64) * 10, length=10, fs=1.0, features=feats)
    return ws, Grouping(labels=labels)


def test_balanced_accuracy_and_the_majority_baseline_sit_beside_the_accuracy(monkeypatch, tmp_path):
    import Adapters.catalogue_classifier as clf
    monkeypatch.setattr(clf, "MODEL_ROOT", str(tmp_path / "models"))
    ws, g = _inputs()
    meta = clf._run(None, None, 1.0, n_estimators=20, value=g, windows=ws).meta
    counts = meta["holdout_class_counts"]
    assert meta["majority_baseline"] == max(counts.values()) / sum(counts.values())
    assert np.isclose(meta["balanced_accuracy"], np.mean(list(meta["per_class_accuracy"].values())))
    weighted = sum(meta["per_class_accuracy"][c] * counts[c] for c in counts) / sum(counts.values())
    assert np.isclose(meta["holdout_accuracy"], weighted)


def test_no_holdout_means_none_never_a_zero(monkeypatch, tmp_path):
    import Adapters.catalogue_classifier as clf
    monkeypatch.setattr(clf, "MODEL_ROOT", str(tmp_path / "models"))
    ws, g = _inputs()
    meta = clf._run(None, None, 1.0, n_estimators=5, holdout_frac=0.0, value=g, windows=ws).meta
    assert meta["balanced_accuracy"] is None and meta["majority_baseline"] is None
