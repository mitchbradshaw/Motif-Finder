"""
Least-squares fits of one recorded cycle shape: FHN oscillator, FHN excitable excursion, and the
jump + exponential recovery kernel.

The data is one cycle `y` sampled at fractions `tau` in [0, 1) of the cycle (the mean cycle of a
drop sequence, see `data`). Every model is linear in an amplitude `gain` and an `offset`, which
are solved exactly inside the residual (variable projection), so least_squares only searches the
shape parameters.

**What the voltage alone can identify.** With w hidden, a and z enter v(t) only through
alpha = a + b z: the shift w -> w + z leaves v' unchanged and turns a into a + b z (tested). So
the fits search alpha, b, c and report a with z held at the paper's -0.4 (`Z_REPORT`); any other
z with the same alpha gives the same voltage trace and the same PRC with w held fixed.

**Oscillatory regime** (`fit_oscillator`). The FHN of Wilshin, Kvalheim & Revzen (2024), eq. 17.
b < 1 makes the fixed point unique; it is unstable — and so (Poincare-Bendixson, the cubic keeps
orbits bounded) a limit cycle exists — exactly when its v* lies inside (-s, s), s = sqrt(1 - b/c^2).
The fit is parameterised by u = v*/s in (-0.95, 0.95), so every trial parameter set oscillates;
alpha = v* + b (v*^3/3 - v*). The model observation is
    y(tau) = offset + gain * v_gamma(2 pi * time_ratio * tau + phase_shift)
with v_gamma the limit-cycle voltage in phase (phase 0 at its maximum). time_ratio is the time
scale: model cycles per recorded cycle (1 = the model's period equals the cycle's length); in
physical units the model advances time_ratio * T / L model time units per second.

**Excitable regime** (`fit_excitable`). The same equations with v* outside (-s, s) on the left
branch (a stable fixed point; the mirror image is covered by the sign of gain): rest until
t0_frac, an instantaneous voltage kick with w unchanged, one excursion and the return to rest.
`span` = model time units per recorded cycle.

**Competitor** (`fit_jump_exp`). The kernel of `detection.deconvolve` (OASIS, Friedrich, Zhou &
Paninski 2017): a sudden jump at t0 followed by one exponential recovery (AR(1)), optionally with
a finite rise (AR(2): difference of two exponentials), summed periodically so the cycle wraps.

AIC = n ln(RSS/n) + 2k, k counting every free parameter including gain and offset. The n
resampled points of a mean cycle are not independent, so AIC differences are a ranking, not a
likelihood-ratio test.
"""

import numpy as np
from scipy.optimize import brentq, least_squares

from Pipelines.fhn import model as M

Z_REPORT = M.PAPER["z"]
FIT_TOL = 1e-8
N_CYCLE = 1000
U_MAX = 0.98         # the paper's own parameters sit at u = 0.95; relaxing near u = 1 (Hopf) is capped in fast_cycle
BOUNDS_OSC = dict(u=(-U_MAX, U_MAX), b=(0.05, 0.95), c=(1.0, 12.0), time_ratio=(0.8, 1.25),
                  phase_shift=(-np.pi, 3 * np.pi))
BOUNDS_EXC = dict(e=(0.01, 1.0), b=(0.05, 0.95), c=(1.0, 12.0), kick=(0.05, 4.0), span=(1.0, 400.0),
                  t0_frac=(-0.2, 0.6))
V_EXC_MAX = 1.9        # the excitable fixed point lies in (-V_EXC_MAX, -s)
BIG = 1e6


def _s(b, c):
    return np.sqrt(1.0 - b / (c * c))


def alpha_from_vstar(v, b):
    return v + b * (v ** 3 / 3.0 - v)


def alpha_from_u(u, b, c):
    return alpha_from_vstar(u * _s(b, c), b)


def u_from_alpha(alpha, b, c):
    v = brentq(lambda x: alpha_from_vstar(x, b) - alpha, -6.0, 6.0)
    return v / _s(b, c)


def vstar_excitable(e, b, c):
    s = _s(b, c)
    return -(s + e * (V_EXC_MAX - s))


_WARM = {}


def fast_cycle(alpha, b, c, n=N_CYCLE, tol=FIT_TOL, warm=True, max_periods=30):
    """The limit cycle for (alpha, b, c), z = 0, at fitting accuracy (no fmin refinement).

    Period by upward crossings of v through the fixed point's v* (always inside the loop),
    relaxing period by period until successive crossing states agree; the last cycle found is
    reused as the start of the next call (a fit's trial parameters move little)."""
    osc = M.fhn(a=alpha, b=b, c=c, z=0.0)
    (vs, _), tr, _det = M.fixed_point(alpha, b, c, 0.0)
    if tr <= 0:
        raise RuntimeError("fast_cycle: the fixed point is stable; no limit cycle")
    if warm and "x" in _WARM:
        x, Tg = _WARM["x"].copy(), _WARM["T"]
    else:
        x, Tg = osc.x0.copy(), None
    if Tg is None:
        ts = np.arange(0.0, 200.0, 0.02)
        X = M.integrate(osc, x, ts, tol=tol)
        tc = M._up_crossings(ts, X[:, 0], vs)
        if len(tc) < 3:
            raise RuntimeError("fast_cycle: no oscillation in 200 time units")
        Tg = float(np.median(np.diff(tc[-3:])))
        x = X[-1]

    def first_crossing(x, window):
        for _ in range(6):
            ts = np.linspace(0.0, window, 2400)
            X = M.integrate(osc, x, ts, tol=tol)
            tc = M._up_crossings(ts, X[:, 0], vs)
            tc = tc[tc > 1e-9 * window]
            if len(tc):
                k = int(np.searchsorted(ts, tc[0]))
                f = (tc[0] - ts[k - 1]) / (ts[k] - ts[k - 1])
                return float(tc[0]), X[k - 1] + f * (X[k] - X[k - 1])
            window *= 2
        raise RuntimeError("fast_cycle: lost the oscillation")

    _, xc = first_crossing(x, 1.5 * Tg)          # onto the crossing section
    for _ in range(max_periods):
        Tn, xn = first_crossing(xc, 1.5 * Tg)     # one return to the section = one period
        done = np.max(np.abs(xn - xc)) < 1e-6
        Tg, xc = Tn, xn
        if done:
            break
    ts = np.linspace(0.0, Tg, 4 * n + 1)
    X = M.integrate(osc, xc, ts, tol=tol)
    _WARM["x"], _WARM["T"] = xc.copy(), Tg
    t = np.linspace(0.0, Tg, n, endpoint=False)
    S = np.stack([np.interp(t, ts, X[:, j]) for j in range(2)], axis=1)
    kmax = int(np.argmax(S[:, 0]))
    S = np.roll(S, -kmax, axis=0)
    return M.LimitCycle(osc=osc, T=Tg, states=S, phases=2 * np.pi * np.arange(n) / n, tol=tol)


def _linear(m, y):
    A = np.stack([m, np.ones_like(m)], axis=1)
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    return coef, y - A @ coef


def _stats(y, r, k):
    n = y.size
    rss = float(np.sum(r * r))
    tss = float(np.sum((y - y.mean()) ** 2))
    return dict(n=n, k=k, rss=rss, rmse=float(np.sqrt(rss / n)), r2=1.0 - rss / tss if tss > 0 else np.nan,
                nrmse=float(np.sqrt(rss / n) / np.std(y)) if np.std(y) > 0 else np.nan,
                aic=float(n * np.log(max(rss, 1e-300) / n) + 2 * k))


def _box(bounds, keys):
    lo = np.array([bounds[k][0] for k in keys])
    hi = np.array([bounds[k][1] for k in keys])
    return lo, hi


# ----------------------------------------------------------------------------- oscillator

OSC_KEYS = ("u", "b", "c", "time_ratio", "phase_shift")


def oscillator_model(tau, cyc, time_ratio, phase_shift):
    th = np.mod(2 * np.pi * time_ratio * np.asarray(tau) + phase_shift, 2 * np.pi)
    return np.interp(th, cyc.phases, cyc.states[:, 0], period=2 * np.pi)


def _best_phase(tau, y, cyc, n_grid=72):
    best = (-np.inf, 0.0)
    for phi in np.linspace(0, 2 * np.pi, n_grid, endpoint=False):
        m = oscillator_model(tau, cyc, 1.0, phi)
        cc = np.corrcoef(m, y)[0, 1]
        if np.isfinite(cc) and cc * cc > best[0]:
            best = (cc * cc, phi)
    return best[1]


def fit_oscillator(tau, y, restarts=6, seed=0, n_cycle=N_CYCLE, max_nfev=300, bounds=BOUNDS_OSC, init=None):
    """Fit the FHN limit-cycle voltage to one cycle. Returns the best of `restarts` starts."""
    tau, y = np.asarray(tau, float), np.asarray(y, float)
    rng = np.random.default_rng(seed)
    lo, hi = _box(bounds, OSC_KEYS)
    cache = {}

    def cycle_for(p):
        key = tuple(np.round(p[:3], 12))
        if key not in cache:
            if len(cache) > 64:
                cache.clear()
            u, b, c = p[:3]
            cache[key] = fast_cycle(alpha_from_u(u, b, c), b, c, n=n_cycle)
        return cache[key]

    def resid(p):
        try:
            cyc = cycle_for(p)
        except Exception:
            return np.full(y.size, BIG)
        _, r = _linear(oscillator_model(tau, cyc, p[3], p[4]), y)
        return r

    starts = []
    if init is not None:
        starts.append(np.asarray(init, float))
    while len(starts) < restarts:
        u = rng.uniform(-0.8, 0.8)
        b = rng.uniform(0.2, 0.9)
        c = float(np.exp(rng.uniform(np.log(1.2), np.log(8.0))))
        starts.append(np.array([u, b, c, 1.0, np.nan]))
    best = None
    tried = []
    for p0 in starts:
        p0 = p0.copy()
        if not np.isfinite(p0[4]):
            try:
                p0[4] = _best_phase(tau, y, cycle_for(p0))
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
    if best is None:
        raise RuntimeError("fit_oscillator: every start failed")
    p = best.x
    cyc = cycle_for(p)
    m = oscillator_model(tau, cyc, p[3], p[4])
    (gain, offset), r = _linear(m, y)
    u, b, c = p[:3]
    alpha = float(alpha_from_u(u, b, c))
    out = dict(model="fhn_oscillator", **_stats(y, r, k=len(OSC_KEYS) + 2))
    out["params"] = dict(alpha=alpha, a=alpha - b * Z_REPORT, z=Z_REPORT, b=float(b), c=float(c), u=float(u),
                         v_star=float(u * _s(b, c)), time_ratio=float(p[3]),
                         phase_shift=float(np.mod(p[4], 2 * np.pi)), gain=float(gain), offset=float(offset),
                         model_period=float(cyc.T))
    out["fitted"] = offset + gain * m
    out["restart_rss"] = tried
    out["status"] = int(best.status)
    out["nfev"] = int(best.nfev)
    return out


# ----------------------------------------------------------------------------- excitable

EXC_KEYS = ("e", "b", "c", "kick", "span", "t0_frac")


def excitable_trace(tau, e, b, c, kick, span, t0_frac, tol=FIT_TOL):
    """Model voltage: rest at the stable v* until t0_frac, then a voltage kick (w unchanged)."""
    tau = np.asarray(tau, float)
    v0 = vstar_excitable(e, b, c)
    alpha = alpha_from_vstar(v0, b)
    w0 = (alpha - v0) / b
    out = np.full(tau.size, v0)
    after = tau >= t0_frac
    if after.any():
        ts = np.concatenate([[0.0], span * (tau[after] - t0_frac)])
        X = M.integrate(M.fhn(a=alpha, b=b, c=c, z=0.0), [v0 + kick, w0], ts, tol=tol)
        out[after] = X[1:, 0]
    return out


def excitable_waveform(tau, u_ex, b, c, kick, span, t0_frac, gain=1.0, offset=0.0):
    return offset + gain * excitable_trace(tau, u_ex, b, c, kick, span, t0_frac)


def fit_excitable(tau, y, restarts=6, seed=0, max_nfev=300, bounds=BOUNDS_EXC):
    """Fit one FHN excursion from rest (stable fixed point) to one cycle."""
    tau, y = np.asarray(tau, float), np.asarray(y, float)
    rng = np.random.default_rng(seed)
    lo, hi = _box(bounds, EXC_KEYS)

    def resid(p):
        try:
            m = excitable_trace(tau, *p)
        except Exception:
            return np.full(y.size, BIG)
        if not np.all(np.isfinite(m)) or np.ptp(m) < 1e-9:
            return np.full(y.size, BIG)
        _, r = _linear(m, y)
        return r

    k_jump = int(np.argmax(np.abs(np.diff(y))))
    t_jump = float(tau[k_jump])
    best, tried = None, []
    for i in range(restarts):
        p0 = np.array([rng.uniform(0.05, 0.5), rng.uniform(0.3, 0.9),
                       float(np.exp(rng.uniform(np.log(1.5), np.log(8.0)))), rng.uniform(0.9, 2.5),
                       float(np.exp(rng.uniform(np.log(5.0), np.log(80.0)))),
                       t_jump - 0.01 if i % 2 == 0 else rng.uniform(0.0, 0.3)])
        p0 = np.clip(p0, lo + 1e-9, hi - 1e-9)
        try:
            sol = least_squares(resid, p0, bounds=(lo, hi), x_scale="jac", diff_step=1e-4, max_nfev=max_nfev)
        except Exception:
            continue
        tried.append(float(np.sum(sol.fun ** 2)))
        if best is None or sol.cost < best.cost:
            best = sol
    if best is None:
        raise RuntimeError("fit_excitable: every start failed")
    p = best.x
    m = excitable_trace(tau, *p)
    (gain, offset), r = _linear(m, y)
    e, b, c = p[:3]
    v0 = vstar_excitable(e, b, c)
    alpha = float(alpha_from_vstar(v0, b))
    out = dict(model="fhn_excitable", **_stats(y, r, k=len(EXC_KEYS) + 2))
    out["params"] = dict(alpha=alpha, a=alpha - b * Z_REPORT, z=Z_REPORT, b=float(b), c=float(c), e=float(e),
                         v_star=float(v0), kick=float(p[3]), span=float(p[4]), t0_frac=float(p[5]),
                         gain=float(gain), offset=float(offset))
    out["fitted"] = offset + gain * m
    out["restart_rss"] = tried
    out["status"] = int(best.status)
    return out


# ----------------------------------------------------------------------------- jump + exp

def jump_exp_kernel(tau, t0_frac, decay_frac, rise_frac=0.0):
    s = np.mod(np.asarray(tau, float) - t0_frac, 1.0)
    k = np.exp(-s / decay_frac) / (1.0 - np.exp(-1.0 / decay_frac))
    if rise_frac > 0:
        k = k - np.exp(-s / rise_frac) / (1.0 - np.exp(-1.0 / rise_frac))
    return k


def fit_jump_exp(tau, y, rise=False):
    """Periodic jump + exponential recovery (OASIS's AR(1) kernel; AR(2) with rise=True)."""
    tau, y = np.asarray(tau, float), np.asarray(y, float)

    def unpack(t0, p):
        return (t0, p[0], p[0] * p[1]) if rise else (t0, p[0], 0.0)

    def resid_at(t0):
        def resid(p):
            _, r = _linear(jump_exp_kernel(tau, *unpack(t0, p)), y)
            return r
        return resid

    lo = np.array([0.003] + ([0.001] if rise else []))
    hi = np.array([5.0] + ([0.95] if rise else []))
    # an instant jump is located only to the sample grid (the residual is flat between samples),
    # so t0 is searched on the samples and half-samples; the recovery (and rise) by least squares
    h = 0.5 / tau.size
    grid = []
    for t0 in np.concatenate([tau, tau - h]):
        for td in (0.01, 0.03, 0.1, 0.3, 1.0):
            p0 = np.array([td] + ([0.2] if rise else []))
            grid.append((float(np.sum(resid_at(t0)(p0) ** 2)), t0, p0))
    grid.sort(key=lambda g: g[0])
    best = None
    for _, t0, p0 in grid[:6]:
        sol = least_squares(resid_at(t0), np.clip(p0, lo + 1e-9, hi - 1e-9), bounds=(lo, hi), max_nfev=400)
        if best is None or sol.cost < best[0].cost:
            best = (sol, t0)
    sol, t0_best = best
    t0, td, tr = unpack(t0_best, sol.x)
    m = jump_exp_kernel(tau, t0, td, tr)
    (amp, base), r = _linear(m, y)
    out = dict(model="jump_exp_rise" if rise else "jump_exp", **_stats(y, r, k=len(lo) + 3))
    out["params"] = dict(t0_frac=float(np.mod(t0, 1.0)), decay_frac=float(td), rise_frac=float(tr),
                         amplitude=float(amp), baseline=float(base))
    out["fitted"] = base + amp * m
    return out


# ----------------------------------------------------------------------------- sinusoid

def fit_sinusoid(tau, y, harmonics=1):
    """Baseline: offset + the first `harmonics` Fourier harmonics of the cycle (linear). If FHN
    does no better than one sinusoid, its fit says nothing beyond 'it is periodic'."""
    tau, y = np.asarray(tau, float), np.asarray(y, float)
    cols = [np.ones_like(tau)]
    for h in range(1, harmonics + 1):
        cols += [np.cos(2 * np.pi * h * tau), np.sin(2 * np.pi * h * tau)]
    A = np.stack(cols, axis=1)
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    r = y - A @ coef
    out = dict(model=f"sinusoid_{harmonics}", **_stats(y, r, k=A.shape[1]))
    out["params"] = dict(coefficients=[float(c) for c in coef])
    out["fitted"] = A @ coef
    return out
