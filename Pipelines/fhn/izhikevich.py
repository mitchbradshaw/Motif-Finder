"""
The Izhikevich (2003) simple model, and a cycle fitter shaped like `fit.fit_oscillator`.

    v' = 0.04 v^2 + 5 v + 140 - u + I,     u' = a (b v - u),
    if v >= 30 (V_PEAK):  v <- c,  u <- u + d

E. M. Izhikevich (2003), "Simple model of spiking neurons", IEEE Trans. Neural Netw. 14:1569-1572
(time in ms, v in mV in the original; here both are model units, mapped to the recording by a free
time scale and a free gain).

Integration: classical RK4 at `DT` model ms, the step shrunk where v is fast (h <= 0.25 / |v'|) so
the quadratic blow-up into the peak is followed, and the crossing of V_PEAK found by linear
interpolation inside the step; v is cut at the peak (never past it) and reset there. Compiled with
numba (already in the environment) because a fit evaluates the orbit hundreds of times.

**Periodic orbit** (`periodic_orbit`): with constant I above rheobase the reset map
u_k -> u_{k+1} (start at v = c, u = u_k, run to the peak, add d) settles to a fixed point; one
inter-spike interval from that reset is the cycle, sampled uniformly in time, phase 0 at the reset.
Below rheobase there is no orbit (RuntimeError) — the fitter treats that as a failed trial.

**Fit** (`fit_izhikevich`): the observation is, as for the FHN oscillator,
    y(tau) = offset + gain * v_orbit(2 pi * time_ratio * tau + phase_shift)
with gain and offset solved exactly (variable projection), time_ratio in (0.8, 1.25) model cycles per
recorded cycle and phase_shift free; the shape parameters are a, b, c, d and I. k = 9.

What the voltage can identify: the free time scale removes the orbit's period, so I and the time
constants are traded against each other, and the free gain/offset remove the absolute voltage
scale, so c is identifiable only relative to the peak and the orbit's floor. Expect a, d and I to be
poorly identified jointly; the fitter reports each restart's RSS and parameters so that can be read.
"""

import numpy as np
from numba import njit
from scipy.optimize import least_squares

V_PEAK = 30.0
DT = 0.05
T_MAX = 5000.0           # model ms without a spike = no orbit
BOUNDS = dict(a=(0.003, 0.3), b=(-0.1, 0.3), c=(-75.0, -40.0), d=(0.0, 12.0), I=(0.0, 60.0),
              time_ratio=(0.8, 1.25), phase_shift=(-np.pi, 3 * np.pi))
KEYS = ("a", "b", "c", "d", "I", "time_ratio", "phase_shift")
STARTS = ((0.02, 0.2, -65.0, 8.0, 10.0),    # regular spiking
          (0.02, 0.2, -55.0, 4.0, 10.0),    # intrinsically bursting
          (0.02, 0.2, -50.0, 2.0, 10.0),    # chattering
          (0.1, 0.2, -65.0, 2.0, 10.0),     # fast spiking
          (0.02, 0.25, -65.0, 2.0, 10.0))   # low-threshold spiking
BIG = 1e6


@njit(cache=True)
def _f(v, u, a, b, I):
    return 0.04 * v * v + 5.0 * v + 140.0 - u + I, a * (b * v - u)


@njit(cache=True)
def _step(v, u, a, b, I, h):
    k1v, k1u = _f(v, u, a, b, I)
    k2v, k2u = _f(v + 0.5 * h * k1v, u + 0.5 * h * k1u, a, b, I)
    k3v, k3u = _f(v + 0.5 * h * k2v, u + 0.5 * h * k2u, a, b, I)
    k4v, k4u = _f(v + h * k3v, u + h * k3u, a, b, I)
    return v + h * (k1v + 2 * k2v + 2 * k3v + k4v) / 6.0, u + h * (k1u + 2 * k2u + 2 * k3u + k4u) / 6.0


@njit(cache=True)
def _to_peak(v, u, a, b, I, dt, t_max, record, out_t, out_v, out_u):
    """Integrate from (v, u) until v reaches V_PEAK or t_max. Returns (t_peak or -1, u at peak, n
    recorded samples). With record, every step is written to out_* (sized by the caller)."""
    t = 0.0
    n = 0
    cap = out_t.shape[0]
    if record and n < cap:
        out_t[n] = t
        out_v[n] = v
        out_u[n] = u
        n += 1
    while t < t_max:
        fv, _ = _f(v, u, a, b, I)
        h = dt
        if abs(fv) * h > 0.25:
            h = 0.25 / abs(fv)
        if h < 1e-7:
            h = 1e-7
        v1, u1 = _step(v, u, a, b, I, h)
        if v1 >= V_PEAK or not np.isfinite(v1):
            if np.isfinite(v1) and v1 > v:
                f = (V_PEAK - v) / (v1 - v)
            else:
                f = 1.0
            tp = t + f * h
            up = u + f * (u1 - u)
            if record and n < cap:
                out_t[n] = tp
                out_v[n] = V_PEAK
                out_u[n] = up
                n += 1
            return tp, up, n
        v, u, t = v1, u1, t + h
        if record and n < cap:
            out_t[n] = t
            out_v[n] = v
            out_u[n] = u
            n += 1
    return -1.0, u, n


_EMPTY = np.zeros(1)


def simulate(a, b, c, d, I, t_end, dt=DT, v0=None, u0=None):
    """Simulate from (v0, u0) (default: the resting point if it exists, else (c, b c)) for t_end.

    Returns t, v, u on the integrator's steps (v at a peak is V_PEAK, the next sample is the reset),
    spike_times, reset_index (the sample right after each reset) and u_before_reset."""
    if v0 is None:
        disc = (5.0 - b) ** 2 - 4 * 0.04 * (140.0 + I)
        v0 = (-(5.0 - b) + np.sqrt(disc)) / 0.08 if disc >= 0 else c
    if u0 is None:
        u0 = b * v0
    cap = int(t_end / min(dt, 1e-3) / 4) + 100000
    T, V, U = np.empty(cap), np.empty(cap), np.empty(cap)
    t_all, v_all, u_all, spikes, resets, u_before = [], [], [], [], [], []
    t0, v, u, n_total = 0.0, float(v0), float(u0), 0
    while t0 < t_end:
        tp, up, n = _to_peak(v, u, a, b, I, dt, t_end - t0, True, T, V, U)
        t_all.append(t0 + T[:n].copy())
        v_all.append(V[:n].copy())
        u_all.append(U[:n].copy())
        n_total += n
        if tp < 0:
            break
        spikes.append(t0 + tp)
        u_before.append(up)
        resets.append(n_total)            # the first sample of the next segment is the reset
        t0, v, u = t0 + tp, float(c), float(up + d)
    t = np.concatenate(t_all)
    keep = t <= t_end + 1e-9
    resets = [k for k in resets if k < keep.sum()]
    return dict(t=t[keep], v=np.concatenate(v_all)[keep], u=np.concatenate(u_all)[keep],
                spike_times=np.array(spikes), reset_index=np.array(resets, dtype=int),
                u_before_reset=np.array(u_before[:len(resets)]))


def periodic_orbit(a, b, c, d, I, n=1000, dt=DT, tol=1e-7, max_iter=400, u_start=None):
    """The settled inter-spike interval: T and v (and u) at n uniform times from the reset."""
    u = b * c if u_start is None else float(u_start)
    T_prev = None
    for _ in range(max_iter):
        tp, up, _ = _to_peak(float(c), u, a, b, I, dt, T_MAX, False, _EMPTY, _EMPTY, _EMPTY)
        if tp < 0:
            raise RuntimeError("periodic_orbit: no spike (below rheobase, or the time limit)")
        u_new = up + d
        done = abs(u_new - u) < tol * (1.0 + abs(u)) and T_prev is not None and abs(tp - T_prev) < 1e-6 * tp
        u, T_prev = u_new, tp
        if done:
            break
    else:
        raise RuntimeError("periodic_orbit: the reset map did not settle (bursting or chaotic)")
    cap = 2 * int(T_prev / dt) + 200000
    Tr, Vr, Ur = np.empty(cap), np.empty(cap), np.empty(cap)
    tp, _, m = _to_peak(float(c), u, a, b, I, dt, T_MAX, True, Tr, Vr, Ur)
    ts = np.linspace(0.0, tp, n, endpoint=False)
    return dict(T=float(tp), v=np.interp(ts, Tr[:m], Vr[:m]), u=np.interp(ts, Tr[:m], Ur[:m]),
                phases=2 * np.pi * np.arange(n) / n, u_reset=float(u))


def waveform(tau, orbit, time_ratio, phase_shift):
    th = np.mod(2 * np.pi * time_ratio * np.asarray(tau, float) + phase_shift, 2 * np.pi)
    return np.interp(th, orbit["phases"], orbit["v"], period=2 * np.pi)


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


def _best_phase(tau, y, orb, n_grid=72):
    best = (-np.inf, 0.0)
    for phi in np.linspace(0, 2 * np.pi, n_grid, endpoint=False):
        cc = np.corrcoef(waveform(tau, orb, 1.0, phi), y)[0, 1]
        if np.isfinite(cc) and cc * cc > best[0]:
            best = (cc * cc, phi)
    return best[1]


def fit_izhikevich(tau, y, restarts=5, seed=0, n_orbit=600, max_nfev=200, bounds=BOUNDS, init=None):
    """Fit the Izhikevich periodic orbit to one cycle; the best of the starts (the canonical
    2003 classes first, then random). `init`: a shape vector (a, b, c, d, I) tried first."""
    tau, y = np.asarray(tau, float), np.asarray(y, float)
    rng = np.random.default_rng(seed)
    lo = np.array([bounds[k][0] for k in KEYS])
    hi = np.array([bounds[k][1] for k in KEYS])
    cache = {}

    def orbit_for(p):
        key = tuple(np.round(p[:5], 10))
        if key not in cache:
            if len(cache) > 128:
                cache.clear()
            cache[key] = periodic_orbit(*p[:5], n=n_orbit)
        return cache[key]

    def resid(p):
        try:
            orb = orbit_for(p)
        except Exception:
            return np.full(y.size, BIG)
        m = waveform(tau, orb, p[5], p[6])
        if np.ptp(m) < 1e-9:
            return np.full(y.size, BIG)
        return _linear(m, y)[1]

    shapes = ([] if init is None else [tuple(init)]) + list(STARTS)
    while len(shapes) < restarts:
        shapes.append((float(np.exp(rng.uniform(np.log(0.005), np.log(0.2)))), rng.uniform(0.0, 0.28),
                       rng.uniform(-72, -45), rng.uniform(0.5, 10.0), rng.uniform(5.0, 40.0)))
    shapes = shapes[:max(restarts, 1)]
    best, tried = None, []
    for sh in shapes:
        p0 = np.array(list(sh) + [1.0, 0.0])
        try:
            p0[6] = _best_phase(tau, y, orbit_for(p0))
        except Exception:
            continue
        p0 = np.clip(p0, lo + 1e-9, hi - 1e-9)
        try:
            sol = least_squares(resid, p0, bounds=(lo, hi), x_scale="jac", diff_step=1e-4, max_nfev=max_nfev)
        except Exception:
            continue
        tried.append(dict(rss=float(np.sum(sol.fun ** 2)), **{k: float(v) for k, v in zip(KEYS, sol.x)}))
        if best is None or sol.cost < best.cost:
            best = sol
    if best is None:
        raise RuntimeError("fit_izhikevich: every start failed")
    p = best.x
    orb = orbit_for(p)
    m = waveform(tau, orb, p[5], p[6])
    (gain, offset), r = _linear(m, y)
    out = dict(model="izhikevich", **_stats(y, r, k=len(KEYS) + 2))
    out["params"] = {k: float(v) for k, v in zip(KEYS, p)}
    out["params"].update(phase_shift=float(np.mod(p[6], 2 * np.pi)), gain=float(gain), offset=float(offset),
                         model_period=float(orb["T"]))
    out["on_bound"] = [k for k, v, l, h in zip(KEYS, p, lo, hi) if min(v - l, h - v) < 1e-3 * (h - l)]
    out["fitted"] = offset + gain * m
    out["restarts"] = tried
    out["status"] = int(best.status)
    out["nfev"] = int(best.nfev)
    return out
