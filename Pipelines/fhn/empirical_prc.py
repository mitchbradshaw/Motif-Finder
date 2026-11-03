"""
The spontaneous phase-timing estimate (a PRC proxy) and the return map of a long drop train.

Nobody nudged a fungus, so no PRC can be measured. What a long train allows is weaker: do the signal's own
small deviations at a given phase of a cycle go with that cycle ending early or late?

* **Timing.** dT_i = L_i - median(L_{i-5..i+5}): cycle i's length (onset to next onset) minus a running
  median over +-5 cycles, which removes slow drift of the beat.
* **Wiggles.** r_i(phi) = C_i(phi) - mean(C_{i-5..i+5})(phi): the cycle's chord-detrended shape minus the
  running mean cycle, averaged into `N_BINS` phase bins. The cycle runs from 0.1 of its length before the
  drop to 0.1 before the next drop (`data.cut_cycle`), so every bin precedes the drop whose timing is dT_i.
* **Estimate.** dT_i ~ sum_k Z_k r_i(phi_k) by ridge regression on centred columns, lambda chosen by
  leave-one-out (closed form through the hat matrix) from a log grid, scored by the leave-one-out R2
  (`cv_r2`). Bootstrap over cycles (lambda fixed) gives 95 % bands.
* **Units.** Z is reported in rad/mV with advance positive: Z_rad = -2 pi Z_s / T, T the median cycle, so a
  positive value means a deviation of +1 mV at that phase goes with the next drop coming early.
* **Nulls.** (1) dT shuffled across cycles (`n_shuffle` draws, lambda re-chosen each draw); (2) the same
  estimator on fake trains - quiet, phase-scrambled and AAFT cycles - paired with the real dT. A bin clears
  when |Z_k| exceeds the 95th percentile of |Z_k| under every null; the train clears when cv_r2 exceeds the
  95th percentile of every null's cv_r2.
* **Return map.** (T_i, T_{i+1}) over consecutive cycles: Spearman rho against `n_shuffle` shuffles of the
  cycle order, raw and on dT (drift removed; a slow drift alone makes the raw map rise).

This is a correlation. Drift the running median does not remove, noise, and the detector placing an onset
late when the cycle before it is distorted can each produce one. Only a timed stimulus measures a PRC.
"""

import numpy as np
from scipy import stats

HALF = 5
N_BINS = 20
LAMBDAS = np.logspace(-4, 4, 33)
MIN_CYCLES = 60


def _consecutive_windows(kept, half):
    """For each kept cycle, the kept cycles within +-half of it in the ORIGINAL cycle index."""
    kept = np.asarray(kept)
    return [np.nonzero(np.abs(kept - k) <= half)[0] for k in kept]


def interior(kept, half=HALF):
    """Cycles whose centred +-half window lies inside the train. At the ends the window is one-sided, and a
    one-sided median under a drift leaves the drift's slope in the residual, so those cycles are left out."""
    kept = np.asarray(kept)
    return (kept - half >= kept.min()) & (kept + half <= kept.max())


def timing_residuals(lengths, kept=None, half=HALF):
    """dT_i (NaN for the first and last `half` cycles, see `interior`)."""
    L = np.asarray(lengths, float)
    kept = np.arange(L.size) if kept is None else np.asarray(kept)
    W = _consecutive_windows(kept, half)
    dT = np.array([L[i] - np.median(L[w]) for i, w in enumerate(W)])
    return np.where(interior(kept, half), dT, np.nan)


def wiggle_residuals(cycles, kept=None, half=HALF, n_bins=N_BINS):
    C = np.asarray(cycles, float)
    kept = np.arange(len(C)) if kept is None else np.asarray(kept)
    W = _consecutive_windows(kept, half)
    R = np.array([C[i] - C[w].mean(axis=0) for i, w in enumerate(W)])
    edges = np.linspace(0, C.shape[1], n_bins + 1).astype(int)
    return np.stack([R[:, edges[k]:edges[k + 1]].mean(axis=1) for k in range(n_bins)], axis=1)


def ridge_loo(X, y, lambdas=LAMBDAS):
    """Ridge on centred X, y with lambda chosen by leave-one-out. Returns (Z, lambda, cv_r2)."""
    X = np.asarray(X, float) - np.mean(X, axis=0)
    y = np.asarray(y, float) - np.mean(y)
    U, s, Vt = np.linalg.svd(X, full_matrices=False)
    uy = U.T @ y
    tss = float(y @ y)
    best = None
    for lam in lambdas:
        d = s * s / (s * s + lam)
        yhat = U @ (d * uy)
        h = np.sum(U * U * d, axis=1)
        e = (y - yhat) / np.maximum(1.0 - h, 1e-9)
        press = float(e @ e)
        if best is None or press < best[0]:
            best = (press, lam)
    press, lam = best
    Z = Vt.T @ (s / (s * s + lam) * uy)
    return Z, float(lam), (1.0 - press / tss) if tss > 0 else np.nan


def ridge_fixed(X, y, lam):
    X = np.asarray(X, float) - np.mean(X, axis=0)
    y = np.asarray(y, float) - np.mean(y)
    return np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ y)


def return_map(lengths, kept=None, n_shuffle=500, seed=0, half=HALF):
    """Spearman rho of T_{i+1} on T_i over consecutive cycles, raw and drift-removed, with shuffle nulls."""
    L = np.asarray(lengths, float)
    kept = np.arange(L.size) if kept is None else np.asarray(kept)
    dT = timing_residuals(L, kept, half)
    pair = np.nonzero(np.diff(kept) == 1)[0]
    rng = np.random.default_rng(seed)
    out = dict(n_pairs=int(pair.size))
    if pair.size < 8:
        return dict(out, why="fewer than 8 consecutive pairs")
    for name, v in (("raw", L), ("detrended", dT)):
        pr = pair[np.isfinite(v[pair]) & np.isfinite(v[pair + 1])]
        if pr.size < 8:
            out[name] = dict(why="fewer than 8 pairs")
            continue
        rho = float(stats.spearmanr(v[pr], v[pr + 1])[0])
        fin = np.nonzero(np.isfinite(v))[0]
        null = []
        for _ in range(n_shuffle):
            w = v.copy()
            w[fin] = rng.permutation(v[fin])
            null.append(stats.spearmanr(w[pr], w[pr + 1])[0])
        null = np.asarray(null)
        out[name] = dict(rho=rho, p_two=float((1 + np.sum(np.abs(null) >= abs(rho) - 1e-12)) / (1 + n_shuffle)),
                         null_q025=float(np.quantile(null, 0.025)), null_q975=float(np.quantile(null, 0.975)))
    out["T"] = L[pair].tolist()
    out["T_next"] = L[pair + 1].tolist()
    return out


def estimate(cycles, lengths, kept=None, fake_cycles=None, n_shuffle=500, n_boot=500, seed=0, half=HALF,
             n_bins=N_BINS, fs=1.0):
    """The spontaneous phase-timing estimate with its nulls. `lengths` in samples (fs converts to s);
    `fake_cycles` = {kind: [cycle arrays with the same rows as `cycles`]}, paired with the real timing."""
    C = np.asarray(cycles, float)
    L = np.asarray(lengths, float) / fs
    kept = np.arange(len(C)) if kept is None else np.asarray(kept)
    ok = interior(kept, half)
    dT = timing_residuals(L, kept, half)[ok]
    X = wiggle_residuals(C, kept, half, n_bins)[ok]
    T = float(np.median(L))
    to_rad = -2 * np.pi / T
    Z, lam, cv = ridge_loo(X, dT)
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(n_boot):
        i = rng.integers(0, len(dT), len(dT))
        boot.append(ridge_fixed(X[i], dT[i], lam))
    boot = np.asarray(boot) * to_rad
    nulls = {}
    sh_Z, sh_cv = [], []
    for _ in range(n_shuffle):
        z, _, c = ridge_loo(X, rng.permutation(dT))
        sh_Z.append(z)
        sh_cv.append(c)
    nulls["shuffle"] = (np.abs(np.asarray(sh_Z)) * abs(to_rad), np.asarray(sh_cv))
    for kind, draws in (fake_cycles or {}).items():
        fz, fc = [], []
        for Cf in draws:
            if Cf is None or len(Cf) != len(C):
                continue
            Xf = wiggle_residuals(Cf, kept, half, n_bins)[ok]
            z, _, c = ridge_loo(Xf, dT)
            fz.append(z)
            fc.append(c)
        if fz:
            nulls[kind] = (np.abs(np.asarray(fz)) * abs(to_rad), np.asarray(fc))
    Zr = Z * to_rad
    bins = (np.arange(n_bins) + 0.5) / n_bins * 2 * np.pi
    clear_bin = np.ones(n_bins, bool)
    null_rep = {}
    for kind, (az, cvs) in nulls.items():
        q = np.quantile(az, 0.95, axis=0)
        clear_bin &= np.abs(Zr) > q
        null_rep[kind] = dict(draws=int(len(cvs)), cv_r2_q95=float(np.quantile(cvs, 0.95)),
                              cv_r2_median=float(np.median(cvs)), absZ_q95=q.tolist(),
                              p_cv=float((1 + np.sum(cvs >= cv)) / (1 + len(cvs))))
    clears = bool(all(cv > r["cv_r2_q95"] for r in null_rep.values()))
    lo, hi = np.quantile(boot, [0.025, 0.975], axis=0)
    return dict(n_cycles=int(len(C)), n_used=int(ok.sum()), median_cycle_s=T, lambda_=lam, cv_r2=float(cv), phases=bins.tolist(),
                Z_rad_per_mV=Zr.tolist(), band_lo=lo.tolist(), band_hi=hi.tolist(),
                bins_clear=clear_bin.tolist(), n_bins_clear=int(clear_bin.sum()), train_clears=clears,
                nulls=null_rep, dT_sd_s=float(np.std(dT)), wiggle_sd_mV=float(np.std(X)))
