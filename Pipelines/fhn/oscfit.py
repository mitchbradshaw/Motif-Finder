"""
Shared machinery for the post-freeze model zoo (research prompt 01): a fast limit cycle of any planar
`model.Oscillator`, a least-squares fit of its voltage to one recorded cycle shaped exactly like
`fit.fit_oscillator`, the model PRC bundle drawn by `figures.fig_cycle_isochrons`, the Type I / II call,
and the Izhikevich model's PRC (a hybrid system, so not an `Oscillator`).

**The observation**, as for the FHN oscillator: y(tau) = offset + gain * v_gamma(2 pi time_ratio tau + phase_shift),
v_gamma the limit-cycle voltage in phase (phase 0 at its maximum), gain and offset solved exactly inside the
residual (variable projection, `fit._linear`), time_ratio in (0.8, 1.25) model cycles per recorded cycle.
k counts every free parameter: the shape parameters, time_ratio, phase_shift, gain and offset.

**Type I / Type II** (`prc_type`): a PRC is one-signed (Type I: a kick can only advance, or only delay) when
the minority sign carries less than `MINORITY` of its absolute area, two-signed (Type II) otherwise. The
fraction is reported, so a borderline call can be read.
"""

import numpy as np
from scipy.optimize import least_squares

from Pipelines.fhn import fit as F
from Pipelines.fhn import izhikevich as IZ
from Pipelines.fhn import model as M

MINORITY = 0.05
BOUNDS_TIME = dict(time_ratio=(0.8, 1.25), phase_shift=(-np.pi, 3 * np.pi))
BIG = F.BIG


def _first_crossing(osc, x, window, level, tol, n=2400):
    for _ in range(6):
        ts = np.linspace(0.0, window, n)
        X = M.integrate(osc, x, ts, tol=tol)
        tc = M._up_crossings(ts, X[:, 0], level)
        tc = tc[tc > 1e-9 * window]
        if len(tc):
            k = int(np.searchsorted(ts, tc[0]))
            f = (tc[0] - ts[k - 1]) / (ts[k] - ts[k - 1])
            return float(tc[0]), X[k - 1] + f * (X[k] - X[k - 1])
        window *= 2
    raise RuntimeError("planar_cycle: lost the oscillation")


def planar_cycle(osc, n=F.N_CYCLE, tol=F.FIT_TOL, warm=None, t_probe=200.0, max_periods=30):
    """The limit cycle of a planar oscillator at fitting accuracy, phase 0 at the largest first coordinate.

    A probe integration gives the section level (the middle of v's range) and a period guess; then the
    upward crossings of v through that level are followed return by return until they agree (as
    `fit.fast_cycle`). `warm` (a dict, kept by the caller) carries the last state, period and level into the
    next call: a fit's trial parameters move little. Raises RuntimeError where nothing oscillates."""
    warm = {} if warm is None else warm
    x, Tg, level = warm.get("x"), warm.get("T"), warm.get("level")
    xc = None
    if Tg is not None:
        try:
            _, xc = _first_crossing(osc, x, 1.5 * Tg, level, tol)
        except Exception:
            xc = None
    if xc is None:
        x = osc.x0.copy()
        span = t_probe
        for _ in range(5):
            ts = np.linspace(0.0, span, 20001)
            X = M.integrate(osc, x, ts, tol=tol)
            half = X[len(X) // 2:, 0]
            if np.ptp(half) < 1e-6 * (1.0 + np.abs(half).max()):
                raise RuntimeError("planar_cycle: the orbit settles (no oscillation)")
            level = 0.5 * (half.max() + half.min())
            tc = M._up_crossings(ts, X[:, 0], level)
            tc = tc[tc > span / 2]
            if len(tc) >= 3:
                break
            x, span = X[-1], span * 4
        else:
            raise RuntimeError("planar_cycle: no sustained oscillation in the probe")
        Tg = float(np.median(np.diff(tc)))
        _, xc = _first_crossing(osc, X[-1], 1.5 * Tg, level, tol)
    for _ in range(max_periods):
        Tn, xn = _first_crossing(osc, xc, 1.5 * Tg, level, tol)
        done = np.max(np.abs(xn - xc)) < 1e-6 * (1.0 + np.max(np.abs(xc)))
        Tg, xc = Tn, xn
        if done:
            break
    ts = np.linspace(0.0, Tg, 4 * n + 1)
    X = M.integrate(osc, xc, ts, tol=tol)
    if np.ptp(X[:, 0]) < 1e-6:
        raise RuntimeError("planar_cycle: degenerate cycle")
    warm.update(x=xc.copy(), T=Tg, level=0.5 * (X[:, 0].max() + X[:, 0].min()))
    t = np.linspace(0.0, Tg, n, endpoint=False)
    S = np.stack([np.interp(t, ts, X[:, j]) for j in range(2)], axis=1)
    S = np.roll(S, -int(np.argmax(S[:, 0])), axis=0)
    return M.LimitCycle(osc=osc, T=Tg, states=S, phases=2 * np.pi * np.arange(n) / n, tol=tol)


def fit_planar(tau, y, make_osc, shape_keys, bounds, starts, name, restarts=None, max_nfev=200, n_cycle=F.N_CYCLE,
               extra_k=0, extra_params=None):
    """Fit the limit-cycle voltage of `make_osc(*shape)` to one cycle: the best of the `starts` (shape vectors).

    Returns the `fit.fit_oscillator`-style dict (model, n, k, rss, r2, aic, params, fitted, on_bound,
    restart_rss). `extra_k` adds discrete choices (e.g. a class switch) to k."""
    tau, y = np.asarray(tau, float), np.asarray(y, float)
    keys = tuple(shape_keys) + ("time_ratio", "phase_shift")
    allb = dict(bounds) | BOUNDS_TIME
    lo = np.array([allb[k][0] for k in keys])
    hi = np.array([allb[k][1] for k in keys])
    ns = len(shape_keys)
    cache, warm = {}, {}

    def cycle_for(p):
        key = tuple(np.round(p[:ns], 12))
        if key not in cache:
            if len(cache) > 64:
                cache.clear()
            cache[key] = planar_cycle(make_osc(*p[:ns]), n=n_cycle, warm=warm)
        return cache[key]

    def resid(p):
        try:
            cyc = cycle_for(p)
        except Exception:
            return np.full(y.size, BIG)
        return F._linear(F.oscillator_model(tau, cyc, p[ns], p[ns + 1]), y)[1]

    starts = list(starts)[:restarts] if restarts else list(starts)
    best, tried = None, []
    for sh in starts:
        p0 = np.array(list(sh) + [1.0, 0.0], float)
        warm.clear()
        try:
            p0[ns + 1] = F._best_phase(tau, y, cycle_for(p0))
        except Exception:
            continue
        p0 = np.clip(p0, lo + 1e-9, hi - 1e-9)
        try:
            sol = least_squares(resid, p0, bounds=(lo, hi), x_scale="jac", diff_step=1e-4, max_nfev=max_nfev)
        except Exception:
            continue
        tried.append(float(np.sum(sol.fun ** 2)))
        if best is None or sol.cost < best.cost:
            best = sol
    if best is None or best.cost >= 0.5 * y.size * BIG ** 2 * 0.99:
        raise RuntimeError(f"fit_planar({name}): every start failed")
    p = best.x
    warm.clear()
    cache.clear()
    cyc = cycle_for(p)
    m = F.oscillator_model(tau, cyc, p[ns], p[ns + 1])
    (gain, offset), r = F._linear(m, y)
    out = dict(model=name, **F._stats(y, r, k=len(keys) + 2 + extra_k))
    out["params"] = {k: float(v) for k, v in zip(keys, p)}
    out["params"].update(phase_shift=float(np.mod(p[ns + 1], 2 * np.pi)), gain=float(gain), offset=float(offset),
                         model_period=float(cyc.T), **(extra_params or {}))
    out["on_bound"] = [k for k, v, l, h in zip(keys[:ns], p[:ns], lo, hi) if min(v - l, h - v) < 1e-3 * (h - l)]
    out["fitted"] = offset + gain * m
    out["restart_rss"] = tried
    out["status"] = int(best.status)
    out["nfev"] = int(best.nfev)
    return out


# ----------------------------------------------------------------------------- PRCs

def prc_type(prc, minority=MINORITY):
    """'I' (one-signed) or 'II' (two-signed) by the minority sign's share of the absolute area."""
    z = np.asarray(prc, float)
    z = z[np.isfinite(z)]
    pos, neg = float(np.sum(np.clip(z, 0, None))), float(-np.sum(np.clip(z, None, 0)))
    tot = pos + neg
    frac = min(pos, neg) / tot if tot > 0 else np.nan
    return dict(type="I" if frac < minority else "II", minority_fraction=frac,
                sign="advance" if pos >= neg else "delay", min=float(z.min()), max=float(z.max()))


def prc_bundle(osc, delta=0.1, n_base=150, eps=None, n=2000):
    """The model PRC set of `figures.fig_cycle_isochrons` for a planar oscillator: the refined limit cycle,
    `delay_prcs` at the paper's delay and at a quarter period, the adjoint at the same base points, and
    their agreement. eps defaults to 1e-3 of the cycle's voltage range (the FHN runs' 1e-2 on a range of ~4)."""
    cyc = M.limit_cycle(osc, n=n)
    if eps is None:
        eps = 2.5e-3 * float(np.ptp(cyc.states[:, 0]))
    pr = M.delay_prcs(cyc, delta=delta, eps=eps, n_base=n_base)
    prq = M.delay_prcs(cyc, delta=cyc.T / 4, eps=eps, n_base=n_base)
    Z = M.prc_adjoint(cyc)
    adj_v = np.interp(pr["phases"], cyc.phases, Z[:, 0], period=2 * np.pi)
    gt = pr["ground_truth"]
    ok = pr["well_conditioned"]
    spread = np.abs(pr["constant_delay"] - gt)[ok]
    agree = dict(max_abs_adjoint_minus_perturbation=float(np.max(np.abs(adj_v - gt))),
                 relative=float(np.max(np.abs(adj_v - gt)) / max(np.max(np.abs(gt)), 1e-300)),
                 coordinate_spread_max_abs=float(np.nanmax(spread)) if spread.size else None,
                 coordinate_spread_ratio=(float(np.nanmax(np.abs(pr["constant_delay"][ok])) /
                                          max(np.max(np.abs(gt)), 1e-300)) if ok.any() else None),
                 n_ill_conditioned=int((~ok).sum()), eps=float(eps))
    return cyc, pr, prq, adj_v, agree


def izhikevich_prc(a, b, c, d, I, n_base=150, eps_frac=1e-2, n_spikes=5, n_orbit=2000):
    """The Izhikevich orbit's voltage PRC by perturbation with u held fixed: kick v by +/- eps at each base
    phase, run `n_spikes` spikes (resets included), and compare the last spike's time with the unperturbed
    one. Phase 0 is the reset (the model's own convention), advance positive. The model is hybrid (a reset),
    so there is no adjoint and no delay-coordinate version here."""
    orb = IZ.periodic_orbit(a, b, c, d, I, n=n_orbit)
    T = orb["T"]
    idx = np.unique(np.round(np.linspace(0, n_orbit, n_base, endpoint=False)).astype(int))
    eps = eps_frac * (IZ.V_PEAK - c)
    out = np.empty(len(idx))
    for j, k in enumerate(idx):
        t_end = []                     # the n-th spike after a +eps and a -eps kick (central difference)
        for s in (1.0, -1.0):
            v0, u0, t = orb["v"][k] + s * eps, orb["u"][k], 0.0
            for _ in range(n_spikes):
                tp, up, _ = IZ._to_peak(float(v0), float(u0), a, b, I, IZ.DT, IZ.T_MAX, False, IZ._EMPTY, IZ._EMPTY,
                                        IZ._EMPTY)
                if tp < 0:
                    raise RuntimeError("izhikevich_prc: the perturbed orbit stopped spiking")
                t += tp
                v0, u0 = c, up + d
            t_end.append(t)
        out[j] = 2 * np.pi * (t_end[1] - t_end[0]) / T / (2 * eps)      # earlier spike after +eps = advance
    return dict(phases=2 * np.pi * idx / n_orbit, ground_truth=out, T=float(T), eps=float(eps), orbit=orb)
