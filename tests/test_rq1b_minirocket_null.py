"""The closed-form ridge of scripts/rq1b_minirocket_null.py must be sklearn's RidgeClassifierCV: the same chosen
penalty and the same held-out decisions, weighted (R4's balanced classes) and not, with more rows than columns
and fewer."""

import importlib.util
import os

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _mod():
    spec = importlib.util.spec_from_file_location("rq1b_null_under_test",
                                                  os.path.join(ROOT, "scripts", "rq1b_minirocket_null.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ALPHAS = np.logspace(-3, 3, 10)


def _data(n, p, seed):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n + 40, p))
    beta = rng.normal(size=p)
    y = ((X @ beta + rng.normal(scale=3.0, size=n + 40)) > 0.8).astype(int)
    mu, sd = X[:n].mean(0), X[:n].std(0)
    return (X[:n] - mu) / sd, y[:n], (X[n:] - mu) / sd


@pytest.mark.parametrize("n,p", [(120, 30), (40, 90)])
@pytest.mark.parametrize("balanced", [False, True])
def test_matches_sklearn(n, p, balanced):
    from sklearn.linear_model import RidgeClassifierCV
    m = _mod()
    Xtr, y, Xte = _data(n, p, seed=n + p)
    ref = RidgeClassifierCV(alphas=ALPHAS, class_weight="balanced" if balanced else None).fit(Xtr, y)
    rl = m.RidgeLOO(Xtr, ALPHAS, weights=m.balanced_weights(y) if balanced else None, dtype=np.float64, tol=1e-12)
    d, chosen = rl.fit_predict(y, rl.test_projection(Xte))
    assert ALPHAS[chosen[0]] == pytest.approx(ref.alpha_)
    np.testing.assert_allclose(d[:, 0], ref.decision_function(Xte), rtol=1e-6, atol=1e-8)


def test_many_label_columns_are_each_fitted_alone():
    m = _mod()
    Xtr, y, Xte = _data(80, 20, seed=3)
    rng = np.random.default_rng(0)
    Y = np.stack([y] + [rng.permutation(y) for _ in range(5)], axis=1)
    rl = m.RidgeLOO(Xtr, ALPHAS, dtype=np.float64, tol=1e-12)
    T = rl.test_projection(Xte)
    together, _ = rl.fit_predict(Y, T, chunk=4)
    for j in range(Y.shape[1]):
        alone, _ = rl.fit_predict(Y[:, j], T)
        np.testing.assert_allclose(together[:, j], alone[:, 0], rtol=1e-10)


def test_permutations_keep_each_blocks_counts():
    m = _mod()
    rows = pd.DataFrame({"group": list("aaaabbbbbb"), "kind": ["event"] * 6 + ["window"] * 4,
                         "label": [1, 0, 0, 1, 1, 1, 0, 1, 0, 0]})
    Y = m.permutations(rows, 20, seed=1)
    for (_g, _k), h in rows.groupby(["group", "kind"]):
        assert (Y[h.index].sum(axis=0) == h["label"].sum()).all()


def test_auc_and_ba_columns_match_the_scalar_forms():
    from sklearn.metrics import roc_auc_score
    m = _mod()
    rng = np.random.default_rng(2)
    y = rng.integers(0, 2, 50)
    D = rng.normal(size=(50, 3)) + y[:, None]
    for j in range(3):
        assert m.auc_columns(y, D)[j] == pytest.approx(roc_auc_score(y, D[:, j]))
        assert m.ba_columns(y, D)[j] == pytest.approx(m.balanced_accuracy(y, D[:, j]))
