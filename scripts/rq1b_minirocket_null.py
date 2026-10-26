"""
rq1b_minirocket_null.py
=======================
Round A_2, RQ1b / R4 (2026-10-26): how sure can we be of R4's held-out score? A label-shuffle null over R4's own
leave-one-recording-out protocol, and bootstrap 95 % intervals for its AUC and balanced accuracy.

In plain words
--------------
R4 agrees with the researcher on about 9 candidates in 10 on recordings it never saw. Two questions a reader asks:

1. *Could a model like this score that well by luck?* We shuffle the researcher's verdicts (within each recording,
   so each recording keeps its own share of "interesting"), retrain, and score again, many times. If the real score
   sits far above every shuffled score, luck is ruled out. The p-value is the share of shuffles that did as well.
2. *How much would the score move with a different sample of judged events?* We resample the judged events with
   replacement (a bootstrap) and read off the range that holds 95 % of the resampled scores.

The rules, each stated once
---------------------------
1. **The same rows.** R4's own rows are read back from its `predictions.parquet` (2,456 events, 3,000 windows), not
   collected afresh, so verdicts given since 2026-10-20 cannot creep in. Their inputs are extracted by R4's own
   `extract` (`scripts/rq1b_minirocket.py`, imported, never changed).
2. **The same folds.** One recording group held out at a time; only its events are scored; windows only ever train.
   A fold's MiniRocket transform is fitted on the training rows (it uses no label), exactly as R4 does, so it is
   computed once per fold and cached (`features/fold_<group>.npy`).
3. **What a shuffle refits.** The standardisation, then a ridge whose penalty is picked from R4's grid by
   leave-one-out error, as `RidgeClassifierCV` does. Platt calibration is a monotone map of the ridge score: it cannot
   change AUC, nor balanced accuracy at the ridge's own cut, so it is not refitted.
4. **One simplification, stated.** R4 weights the classes equally (`class_weight="balanced"`). Those weights follow
   the labels, so every shuffle would need a fresh 5,000 x 5,000 decomposition per fold (about 50 s each). The null
   therefore uses the *unweighted* ridge, decomposed once per fold, and every shuffle is closed-form arithmetic on
   that decomposition. The real labels are scored by the same unweighted procedure, and that is the score the null
   is compared with (a permutation test needs the same statistic on both sides). The exact, weighted R4 procedure is
   also recomputed here on the real labels and checked against R4's stored held-out scores.
5. **The shuffle.** Labels are permuted within each (recording group, kind) block: each recording keeps its count of
   interesting events and windows, so the null asks "does the model know more than each recording's base rate?".
   p = (1 + shuffles scoring at least the real score) / (1 + shuffles).
6. **The intervals.** On R4's stored held-out scores (the saved model's variant): 2,000 bootstrap resamples of the
   events, stratified by held-out recording (each keeps its size), percentile 95 % intervals, pooled and per
   recording. A second, more cautious pooled interval resamples whole channels (a channel's events are not
   independent of each other).

    python scripts/rq1b_minirocket_null.py null --shuffles 200        # features cached on first run
    python scripts/rq1b_minirocket_null.py ci
    python scripts/rq1b_minirocket_null.py report                     # both, as one JSON summary

Threads: 4 (env RQ1B_THREADS). Memory: one fold at a time, float64, about 0.8 GB at peak. (float32 was tried
first: forming X'X in float32 loses enough precision on the 5,000-row folds to move held-out scores by up to 1.0;
float64 with no eigenvalue cut reproduces R4's stored scores.) Reads the real database
read-only (recordings table only) and writes only under `--out`.
"""

import os
import sys

if __name__ == "__main__":
    for _k in ("NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ.setdefault(_k, os.environ.get("RQ1B_THREADS", "4"))

import argparse
import datetime
import gc
import importlib.util
import json
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

R4_DIR = os.path.join(ROOT, "DATA", "derived", "models", "rq1b_minirocket", "20261020-2343")
R4_COLUMN = "held-out score · events + windows · MiniRocket + side"
DEFAULT_OUT = os.path.join(ROOT, "DATA", "derived", "models", "rq1b_minirocket_null")
ROW_COLUMNS = ["source", "kind", "ref", "recording_id", "source_file", "group", "channel", "fs", "units", "start",
               "end", "t0", "t1", "verdict", "label"]


def _load_r4_module():
    spec = importlib.util.spec_from_file_location("rq1b_minirocket_r4", os.path.join(ROOT, "scripts",
                                                                                     "rq1b_minirocket.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


# ── the ridge, closed form ──────────────────────────────────────────────────

class RidgeLOO:
    """A ridge fitted the way sklearn's `RidgeClassifierCV` fits one (targets +1 / -1, an unpenalised intercept,
    the penalty chosen from `alphas` by the mean squared leave-one-out error in the weighted space), decomposed once
    so that any number of label vectors cost only matrix products.

    `X` is the standardised training design (n x p). `weights` are per-row sample weights (None: all 1). The
    decomposition is of the weighted, weighted-centred design; it does not depend on the labels unless the weights
    do."""

    def __init__(self, X, alphas, weights=None, dtype=np.float64, tol=1e-12):
        X = np.asarray(X, dtype=dtype)
        n, p = X.shape
        w = np.ones(n, dtype=np.float64) if weights is None else np.asarray(weights, dtype=np.float64)
        self.n, self.p, self.alphas = n, p, np.asarray(alphas, dtype=np.float64)
        self.w = w
        self.sw = np.sqrt(w).astype(dtype)
        self.x_mean = (w[:, None] * X).sum(axis=0, dtype=np.float64) / w.sum()
        Xt = X - self.x_mean.astype(dtype)
        Xt *= self.sw[:, None]                                  # the weighted, centred design (in place)
        from scipy.linalg import eigh
        if n >= p:
            C = Xt.T @ Xt
            lam, V = eigh(C, driver="evr", overwrite_a=True, check_finite=False)
            del C
            keep = lam > tol * max(lam.max(), 1e-30)
            lam, V = lam[keep].astype(np.float64), np.ascontiguousarray(V[:, keep])
            s = np.sqrt(lam)
            U = (Xt @ V) / s.astype(dtype)
            self._V, self._Xt = V, None
        else:
            K = Xt @ Xt.T
            lam, U = eigh(K, driver="evr", overwrite_a=True, check_finite=False)
            del K
            keep = lam > tol * max(lam.max(), 1e-30)
            lam, U = lam[keep].astype(np.float64), np.ascontiguousarray(U[:, keep])
            s = np.sqrt(lam)
            self._V, self._Xt = None, Xt                         # V = Xt.T U / s, applied lazily
        if self._Xt is None:
            del Xt
        self.U, self.s = U.astype(dtype), s
        # the hat matrix's diagonal for every alpha: the intercept's share plus sum_k U_ik^2 s_k^2/(s_k^2+alpha)
        D = (s[:, None] ** 2 / (s[:, None] ** 2 + self.alphas[None, :])).astype(dtype)
        h = np.empty((n, len(self.alphas)), dtype=np.float64)
        for a in range(0, n, 1024):
            h[a:a + 1024] = (self.U[a:a + 1024] ** 2) @ D
        self.h = h + (w / w.sum())[:, None]

    def test_projection(self, X_test):
        """`(X_test - mean) V`, the held-out rows in the decomposition's coordinates (n_test x r)."""
        Xc = np.asarray(X_test, dtype=self.U.dtype) - self.x_mean.astype(self.U.dtype)
        if self._V is not None:
            return Xc @ self._V
        return (Xc @ self._Xt.T) @ self.U / self.s.astype(self.U.dtype)

    def fit_predict(self, Y, T, chunk=64):
        """For each column of `Y` (n x S, labels 0/1), the chosen penalty and the held-out decisions on the rows `T`
        stands for (`test_projection`'s output). Returns `(decisions n_test x S, alpha index per column)`."""
        Y = np.asarray(Y)
        if Y.ndim == 1:
            Y = Y[:, None]
        n, S = Y.shape
        dtype = self.U.dtype
        s = self.s
        out = np.empty((T.shape[0], S), dtype=np.float64)
        chosen = np.empty(S, dtype=int)
        for c0 in range(0, S, chunk):
            Yb = np.where(Y[:, c0:c0 + chunk] > 0, 1.0, -1.0)
            y_mean = (self.w[:, None] * Yb).sum(axis=0) / self.w.sum()
            Yt = ((Yb - y_mean[None, :]) * np.sqrt(self.w)[:, None]).astype(dtype)
            B = self.U.T @ Yt                                    # r x s
            best = np.full(Yb.shape[1], np.inf)
            best_a = np.zeros(Yb.shape[1], dtype=int)
            for ai, alpha in enumerate(self.alphas):
                d = (s ** 2 / (s ** 2 + alpha)).astype(dtype)
                fitted = self.U @ (d[:, None] * B)
                e = (Yt - fitted) / (1.0 - self.h[:, ai])[:, None]
                mse = np.mean(np.asarray(e, dtype=np.float64) ** 2, axis=0)
                better = mse < best
                best[better], best_a[better] = mse[better], ai
            for ai in np.unique(best_a):
                cols = np.flatnonzero(best_a == ai)
                g = (s / (s ** 2 + self.alphas[ai])).astype(dtype)
                beta_coef = g[:, None] * B[:, cols]               # coefficients in V's coordinates
                out[:, c0 + cols] = np.asarray(T @ beta_coef, dtype=np.float64) + y_mean[cols][None, :]
            chosen[c0:c0 + Yb.shape[1]] = best_a
        return out, chosen


def balanced_weights(y):
    """sklearn's `class_weight="balanced"`: n / (2 * count of the row's class)."""
    y = np.asarray(y, dtype=int)
    counts = np.bincount(y, minlength=2).astype(float)
    return (len(y) / (2.0 * counts))[y]


# ── metrics ─────────────────────────────────────────────────────────────────

def auc(y, d):
    """Mann-Whitney AUC with ties counted half (equals sklearn's roc_auc_score)."""
    from scipy.stats import rankdata
    y = np.asarray(y, dtype=int)
    n1, n0 = int(y.sum()), int((1 - y).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(d)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def balanced_accuracy(y, d, cut=0.0):
    y = np.asarray(y, dtype=int)
    pred = np.asarray(d) > cut
    rec = [pred[y == 1].mean() if (y == 1).any() else np.nan, (~pred[y == 0]).mean() if (y == 0).any() else np.nan]
    return float(np.nanmean(rec))


def auc_columns(y, D):
    """AUC of every column of `D` against one `y`... or, with `y` 2-D, column against column."""
    from scipy.stats import rankdata
    D = np.asarray(D)
    Y = np.asarray(y, dtype=int)
    if Y.ndim == 1:
        Y = np.repeat(Y[:, None], D.shape[1], axis=1)
    R = rankdata(D, axis=0)
    n1 = Y.sum(axis=0)
    n0 = Y.shape[0] - n1
    return (np.where(Y == 1, R, 0).sum(axis=0) - n1 * (n1 + 1) / 2.0) / np.maximum(n1 * n0, 1)


def ba_columns(y, D, cut=0.0):
    Y = np.asarray(y, dtype=int)
    if Y.ndim == 1:
        Y = np.repeat(Y[:, None], D.shape[1], axis=1)
    P = np.asarray(D) > cut
    r1 = (P & (Y == 1)).sum(axis=0) / np.maximum((Y == 1).sum(axis=0), 1)
    r0 = (~P & (Y == 0)).sum(axis=0) / np.maximum((Y == 0).sum(axis=0), 1)
    return (r1 + r0) / 2.0


# ── rows, folds, features ───────────────────────────────────────────────────

def r4_rows(r4_dir=R4_DIR):
    preds = pd.read_parquet(os.path.join(r4_dir, "predictions.parquet"))
    col = [c for c in preds.columns if c.startswith("held-out score") and "events + windows" in c]
    rows = preds[ROW_COLUMNS].copy()
    rows["r4_decision"] = preds[col[0]].to_numpy() if col else np.nan
    return rows.reset_index(drop=True)


def folds_of(rows):
    """R4's `evaluate(split="recording", test_mask=events)`: `(group, train idx, test idx)`."""
    y = rows["label"].to_numpy(int)
    ev = (rows["kind"] == "event").to_numpy()
    out = []
    for g in sorted(rows["group"].unique()):
        te = np.flatnonzero((rows["group"] == g).to_numpy() & ev)
        if len(te) and len(set(y[te].tolist())) == 2:
            tr = np.flatnonzero((rows["group"] != g).to_numpy())
            out.append((g, tr, te))
    return out


def fold_features(mr, rows, M, side, group, tr, cache_dir, log=print):
    """The fold's design for every row (MiniRocket fitted on the training rows, then the side features), cached."""
    path = os.path.join(cache_dir, f"fold_{group}.npy")
    if os.path.exists(path):
        return np.load(path, mmap_mode="r")
    t = time.perf_counter()
    model = mr._minirocket_fit(M[tr], 4992, 0)
    parts = [mr._minirocket_transform(model, M[a:a + 512]) for a in range(0, len(M), 512)]
    F = np.hstack([np.concatenate(parts, axis=0), mr.side_matrix(side)]).astype(np.float32)
    del parts, model
    os.makedirs(cache_dir, exist_ok=True)
    np.save(path, F)
    log(f"  features for fold {group}: {F.shape} in {time.perf_counter() - t:.0f} s")
    del F
    gc.collect()
    return np.load(path, mmap_mode="r")


def standardise(F, tr, te):
    Xtr = np.asarray(F[tr], dtype=np.float64)
    mu = Xtr.mean(axis=0)
    sd = Xtr.std(axis=0)
    sd[sd == 0] = 1.0
    Xtr -= mu
    Xtr /= sd
    Xte = (np.asarray(F[te], dtype=np.float64) - mu) / sd
    return Xtr, Xte


def permutations(rows, n, seed):
    """`n` label vectors, each permuted within every (group, kind) block (rule 5)."""
    rng = np.random.default_rng(seed)
    y = rows["label"].to_numpy(int)
    blocks = [np.flatnonzero(m) for _k, m in
              ((k, (rows["group"] == k[0]).to_numpy() & (rows["kind"] == k[1]).to_numpy())
               for k in rows.groupby(["group", "kind"]).size().index)]
    Y = np.empty((len(y), n), dtype=np.int8)
    for j in range(n):
        yy = y.copy()
        for b in blocks:
            yy[b] = y[b][rng.permutation(len(b))]
        Y[:, j] = yy
    return Y


# ── the null ────────────────────────────────────────────────────────────────

def run_null(out_dir, *, shuffles=200, seed=20261026, exact_check=True, log=print):
    mr = _load_r4_module()
    rows = r4_rows()
    y = rows["label"].to_numpy(int)
    conn = mr.GUARD._read_only(mr.GUARD.REAL_DB)
    try:
        M, side, keep = mr.extract(conn, rows[ROW_COLUMNS])
    finally:
        conn.close()
    if not keep.all():
        raise RuntimeError(f"{int((~keep).sum())} of R4's rows could not be read again; the data moved")
    cache = os.path.join(out_dir, "features")
    folds = folds_of(rows)
    Y = np.concatenate([y[:, None].astype(np.int8), permutations(rows, shuffles, seed)], axis=1)  # column 0 = real
    test_idx = np.concatenate([te for _g, _tr, te in folds])
    D = np.empty((len(test_idx), Y.shape[1]), dtype=np.float64)
    exact = np.full(len(test_idx), np.nan)
    per_fold, pos = [], 0
    t_all = time.perf_counter()
    for g, tr, te in folds:
        t = time.perf_counter()
        F = fold_features(mr, rows, M, side, g, tr, cache, log=log)
        Xtr, Xte = standardise(F, tr, te)
        del F
        if exact_check:
            ex = RidgeLOO(Xtr, mr.ALPHAS, weights=balanced_weights(y[tr]))
            d_ex, a_ex = ex.fit_predict(y[tr], ex.test_projection(Xte))
            exact[pos:pos + len(te)] = d_ex[:, 0]
            del ex
            gc.collect()
        rl = RidgeLOO(Xtr, mr.ALPHAS)
        T = rl.test_projection(Xte)
        del Xtr, Xte
        d, chosen = rl.fit_predict(Y[tr], T)
        del rl, T
        gc.collect()
        D[pos:pos + len(te)] = d
        per_fold.append({"held_out": g, "n_test": int(len(te)), "n_train": int(len(tr)),
                         "alpha_real_unweighted": float(mr.ALPHAS[chosen[0]]),
                         "alpha_real_exact": float(mr.ALPHAS[a_ex[0]]) if exact_check else None,
                         "alpha_shuffles": {str(float(mr.ALPHAS[a])): int((chosen[1:] == a).sum())
                                            for a in np.unique(chosen[1:])},
                         "seconds": round(time.perf_counter() - t, 1)})
        log(f"fold {g}: n_train {len(tr)}, n_test {len(te)}, {per_fold[-1]['seconds']} s")
        pos += len(te)
    y_te = y[test_idx]
    groups = rows["group"].to_numpy()[test_idx]
    np.save(os.path.join(out_dir, "null_decisions.npy"), D.astype(np.float32))
    pd.DataFrame({"row": test_idx, "group": groups, "label": y_te, "r4_stored": rows["r4_decision"].to_numpy()[test_idx],
                  "exact_recomputed": exact, "unweighted_real": D[:, 0]}).to_parquet(
        os.path.join(out_dir, "real_decisions.parquet"), index=False)
    # the statistics: pooled over every held-out event, and per held-out recording
    Ynull = Y[test_idx]
    res = {"created_at": _now(), "shuffles": int(shuffles), "seed": int(seed), "folds": per_fold,
           "seconds": round(time.perf_counter() - t_all, 1),
           "procedure": "unweighted ridge, LOO alpha from R4's grid, per fold MiniRocket fitted on training rows; "
                        "labels permuted within (group, kind)"}
    r4 = rows["r4_decision"].to_numpy()[test_idx]
    res["r4_stored"] = {"auc": auc(y_te, r4), "balanced_accuracy": balanced_accuracy(y_te, r4)}
    if exact_check:
        res["exact_recomputed"] = {"auc": auc(y_te, exact), "balanced_accuracy": balanced_accuracy(y_te, exact),
                                   "max_abs_diff_vs_stored": float(np.nanmax(np.abs(exact - r4))),
                                   "corr_vs_stored": float(np.corrcoef(exact, r4)[0, 1])}
    res["pooled"] = _null_summary(Ynull, D)
    res["by_recording"] = {}
    for g in sorted(set(groups)):
        m = groups == g
        res["by_recording"][g] = _null_summary(Ynull[m], D[m])
    with open(os.path.join(out_dir, "null.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    return res


def _null_summary(Y, D):
    a = auc_columns(Y, D)
    b = ba_columns(Y, D)
    out = {"n": int(Y.shape[0]), "interesting": int(Y[:, 0].sum())}
    for name, v in (("auc", a), ("balanced_accuracy", b)):
        real, null = float(v[0]), v[1:]
        out[name] = {"real": real, "null_mean": float(null.mean()), "null_sd": float(null.std()),
                     "null_q": {q: float(np.quantile(null, float(q))) for q in ("0.025", "0.5", "0.975", "0.99")},
                     "null_max": float(null.max()), "n_null_ge_real": int((null >= real).sum()),
                     "p": float((1 + (null >= real).sum()) / (1 + len(null))),
                     "z": float((real - null.mean()) / null.std()) if null.std() > 0 else None}
    return out


# ── the intervals ───────────────────────────────────────────────────────────

def run_ci(out_dir, *, n_boot=2000, seed=20261026, r4_dir=R4_DIR, column=None, log=print):
    rows = r4_rows(r4_dir)
    if column is not None:
        preds = pd.read_parquet(os.path.join(r4_dir, "predictions.parquet"))
        rows["r4_decision"] = preds[column].to_numpy()
    ev = rows[(rows["kind"] == "event") & rows["r4_decision"].notna()].reset_index(drop=True)
    res = {"created_at": _now(), "n_boot": int(n_boot), "seed": int(seed), "n_events": int(len(ev)),
           "column": column or R4_COLUMN}
    res.update(bootstrap(ev, "r4_decision", n_boot=n_boot, seed=seed))
    with open(os.path.join(out_dir, "ci.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    return res


def bootstrap(ev, score_col, *, n_boot=2000, seed=0, cut=0.0, groups_only=None):
    """Percentile 95 % intervals: pooled (stratified by group), pooled by channel clusters, and per group."""
    rng = np.random.default_rng(seed)
    y = ev["label"].to_numpy(int)
    d = ev[score_col].to_numpy(float)
    g = ev["group"].to_numpy()
    idx_by_g = {k: np.flatnonzero(g == k) for k in sorted(set(g))}
    out = {"pooled": {"n": int(len(y)), "auc": auc(y, d), "balanced_accuracy": balanced_accuracy(y, d, cut)}}
    A, B = np.empty(n_boot), np.empty(n_boot)
    for b in range(n_boot):
        ix = np.concatenate([v[rng.integers(0, len(v), len(v))] for v in idx_by_g.values()])
        A[b], B[b] = auc(y[ix], d[ix]), balanced_accuracy(y[ix], d[ix], cut)
    out["pooled"]["auc_ci"] = _pct(A)
    out["pooled"]["balanced_accuracy_ci"] = _pct(B)
    keys = (ev["group"].astype(str) + ":" + ev["channel"].astype(str)).to_numpy()
    clusters = {k: np.flatnonzero(keys == k) for k in sorted(set(keys))}
    by_g = {}
    for k, v in clusters.items():
        by_g.setdefault(k.split(":")[0], []).append(v)
    A, B = np.empty(n_boot), np.empty(n_boot)
    for b in range(n_boot):
        parts = []
        for cl in by_g.values():                         # resample channels within each group
            for c in rng.integers(0, len(cl), len(cl)):
                parts.append(cl[c])
        ix = np.concatenate(parts)
        A[b], B[b] = auc(y[ix], d[ix]), balanced_accuracy(y[ix], d[ix], cut)
    out["pooled"]["n_channels"] = int(len(clusters))
    out["pooled"]["auc_ci_channel_clusters"] = _pct(A)
    out["pooled"]["balanced_accuracy_ci_channel_clusters"] = _pct(B)
    out["by_recording"] = {}
    for k, v in idx_by_g.items():
        yy, dd = y[v], d[v]
        A, B = np.full(n_boot, np.nan), np.empty(n_boot)
        for b in range(n_boot):
            ix = rng.integers(0, len(v), len(v))
            if len(set(yy[ix].tolist())) == 2:
                A[b] = auc(yy[ix], dd[ix])
            B[b] = balanced_accuracy(yy[ix], dd[ix], cut)
        out["by_recording"][k] = {"n": int(len(v)), "interesting": int(yy.sum()), "auc": auc(yy, dd),
                                  "balanced_accuracy": balanced_accuracy(yy, dd, cut),
                                  "auc_ci": _pct(A[np.isfinite(A)]) if np.isfinite(A).any() else None,
                                  "balanced_accuracy_ci": _pct(B),
                                  "n_channels": int(len(by_g.get(k, [])))}
    return out


def _pct(v):
    v = np.asarray(v, float)
    return [float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("null")
    n.add_argument("--shuffles", type=int, default=200)
    n.add_argument("--seed", type=int, default=20261026)
    n.add_argument("--out", default=DEFAULT_OUT)
    n.add_argument("--no-exact-check", action="store_true")
    c = sub.add_parser("ci")
    c.add_argument("--n-boot", type=int, default=2000)
    c.add_argument("--seed", type=int, default=20261026)
    c.add_argument("--out", default=DEFAULT_OUT)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    if a.cmd == "null":
        res = run_null(a.out, shuffles=a.shuffles, seed=a.seed, exact_check=not a.no_exact_check)
        print(json.dumps({k: res[k] for k in ("pooled", "r4_stored", "seconds") if k in res}, indent=1,
                         default=float))
    else:
        res = run_ci(a.out, n_boot=a.n_boot, seed=a.seed)
        print(json.dumps(res["pooled"], indent=1, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
