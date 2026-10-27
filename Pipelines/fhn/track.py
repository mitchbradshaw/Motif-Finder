"""
Per-cycle model tracking: judge a cycle model by how well it predicts a cycle it was not fitted to,
and test whether its fitted parameters drift across the cycles of a train.

**Blocks.** The cycles of a train (in time order) are cut into contiguous, non-overlapping blocks of
`block` cycles (a short tail joins the last block). One fit per block, to the block's mean cycle:
three cycles share every shape parameter, which a single 20-sample reishi cycle cannot support on its
own, and the blocks are disjoint, so their parameters are independent estimates (what a drift test
needs; overlapping sliding windows would make neighbouring estimates correlated and the shuffle null
anti-conservative).

**Held-out-cycle prediction** (`heldout`). Cycle i, in block b, is predicted from the blocks either
side of it (b - 1 and b + 1, whichever exist) — never from a fit that saw it:
    model prediction    = the mean of those blocks' fitted curves
    baseline prediction = the mean of those blocks' mean cycles (the mean of the other cycles)
Errors are mean squared over the cycle's points. The baseline is model-free and has no parameters;
a model beats it only if its fitted shape is closer to a new cycle than the raw average of its
neighbours is — by smoothing away their noise, or by fitting the shape the cycles share. Ratios < 1
favour the model. Reported: the median per-cycle ratio, the pooled ratio (sum of model errors over
sum of baseline errors) and the fraction of cycles the model predicts better.

**Drift** (`drift_test`). A parameter's series over blocks against `n_perm` seeded shuffles of the
block order: |Spearman rho with block index| (a monotone trend) and the von Neumann ratio (sum of
squared successive differences over (n - 1) x variance, ~2 for an exchangeable series, small for a
trend or any slow wander). p = (1 + #{as extreme}) / (1 + n_perm).
"""

import numpy as np
from scipy import stats

MIN_DRIFT = 5


def blocks(n_cycles, size):
    """Contiguous index blocks of `size`; a tail shorter than `size` joins the last block."""
    n_full = max(1, n_cycles // size)
    out = [np.arange(k * size, (k + 1) * size) for k in range(n_full)]
    out[-1] = np.arange(out[-1][0], n_cycles)
    return [b for b in out if b.size]


def heldout(tau, cycles, fit_curve, block=3):
    """Leave-a-cycle-out prediction from the neighbouring blocks' fits. `fit_curve(tau, y)` returns
    (fitted curve, params dict) or raises (the block then has no fit: NaN params, and its neighbours
    predict without it)."""
    C = np.asarray(cycles, float)
    B = blocks(len(C), block)
    curves, means, params, fails = [], [], [], []
    for b in B:
        m = C[b].mean(axis=0)
        means.append(m)
        try:
            cv, pr = fit_curve(tau, m)
            curves.append(np.asarray(cv, float))
            params.append(dict(pr))
        except Exception as e:                      # a failed fit is reported, never silently replaced
            curves.append(None)
            params.append({})
            fails.append(dict(block=int(len(curves) - 1), error=f"{type(e).__name__}: {e}"))
    rows = []
    for bi, b in enumerate(B):
        nb = [j for j in (bi - 1, bi + 1) if 0 <= j < len(B) and curves[j] is not None]
        nb_base = [j for j in (bi - 1, bi + 1) if 0 <= j < len(B)]
        for i in b:
            if not nb:
                rows.append(dict(cycle=int(i), train_cycles=[], err_model=np.nan, err_base=np.nan))
                continue
            pm = np.mean([curves[j] for j in nb], axis=0)
            pb = np.mean([means[j] for j in nb], axis=0)       # the same blocks: a like-for-like baseline
            rows.append(dict(cycle=int(i), train_cycles=[int(k) for j in nb for k in B[j]],
                             err_model=float(np.mean((C[i] - pm) ** 2)), err_base=float(np.mean((C[i] - pb) ** 2)),
                             n_base_blocks_possible=len(nb_base)))
    em = np.array([r["err_model"] for r in rows])
    eb = np.array([r["err_base"] for r in rows])
    ok = np.isfinite(em) & np.isfinite(eb) & (eb > 0)
    ratio = em[ok] / eb[ok]
    keys = sorted({k for p in params for k in p})
    par = {k: np.array([p.get(k, np.nan) for p in params], float) for k in keys}
    summary = dict(n_cycles=int(len(C)), n_blocks=len(B), n_scored=int(ok.sum()), n_failed_blocks=len(fails),
                   median_ratio=float(np.median(ratio)) if ratio.size else np.nan,
                   pooled_ratio=float(em[ok].sum() / eb[ok].sum()) if ok.any() else np.nan,
                   fraction_model_better=float(np.mean(ratio < 1)) if ratio.size else np.nan,
                   median_err_model=float(np.median(em[ok])) if ok.any() else np.nan,
                   median_err_base=float(np.median(eb[ok])) if ok.any() else np.nan)
    return dict(cycles=rows, summary=summary, params=par, block_index=[b.tolist() for b in B], failures=fails,
                curves=curves, block_means=means)


def _von_neumann(x):
    v = np.var(x)
    return float(np.sum(np.diff(x) ** 2) / ((x.size - 1) * v)) if v > 0 else np.nan


def drift_test(series, n_perm=1000, seed=0, min_n=MIN_DRIFT):
    """Trend and wander of one parameter's series against shuffles of its order (NaN entries dropped)."""
    x = np.asarray(series, float)
    x = x[np.isfinite(x)]
    n = int(x.size)
    if n < min_n or np.ptp(x) == 0:
        return dict(n=n, rho=None, why=f"{n} finite values (needs {min_n}, not all equal)")
    idx = np.arange(n)
    rho = float(stats.spearmanr(idx, x)[0])
    vn = _von_neumann(x)
    rng = np.random.default_rng(seed)
    rx = stats.rankdata(x)
    ri = idx - idx.mean()
    perms = np.argsort(rng.random((n_perm, n)), axis=1)
    R = rx[perms]
    R = R - R.mean(axis=1, keepdims=True)
    null_rho = (R @ ri) / (np.sqrt(np.sum(R * R, axis=1)) * np.sqrt(ri @ ri))
    X = x[perms]
    null_vn = np.sum(np.diff(X, axis=1) ** 2, axis=1) / ((n - 1) * np.var(x))
    return dict(n=n, rho=rho, p_rho=float((1 + np.sum(np.abs(null_rho) >= abs(rho) - 1e-12)) / (1 + n_perm)),
                von_neumann=vn, p_sssd=float((1 + np.sum(null_vn <= vn + 1e-12)) / (1 + n_perm)), n_perm=int(n_perm),
                first=float(x[0]), last=float(x[-1]), median=float(np.median(x)))
