"""
FitzHugh-Nagumo model core: vector field, period, limit cycle, phase, PRCs.

Everything follows S. Wilshin, M. D. Kvalheim & S. Revzen (2024), "Phase response curves and
the role of coordinates", Biol Cybern 118:311-330, doi:10.1007/s00422-024-00997-w:

* eq. 17, the FHN system   v' = c (v + w - v^3/3 + z),   w' = (a - v - b w) / c,
  with the paper's a = 0.7, b = 0.8, c = 3, z = -0.4 (`PAPER`). The right-hand side and its
  Jacobian are the standard ones printed in the paper's Appendix B.
* Appendix B / Sect. 6.1.1, the period: integrate with the Jacobian at tolerances of 1e-10,
  relax onto the cycle, then `scipy.optimize.fmin` on the distance between the start and the
  end of an integration of length tc (the "loop distance").
* Sect. 6.1.3, phase: the cycle is sampled uniformly in time, phase 2 pi t / T; a point's phase
  is found by projecting it orthogonally onto the segment joining its nearest cycle samples
  and interpolating their phases. The gauge (phase 0) is the sample of largest voltage here.
* Sect. 6.1.2 / 6.1.4, the "ground truth" PRC: perturb the voltage of a cycle point by a small
  amount with the gating variable unchanged, wait an integer number of periods (five), take the
  phase of the end point and divide the phase change by the perturbation. A central difference
  (+eps and -eps) is used; the paper perturbed "slightly above or below".
* Sect. 4.1, the Hopf-like oscillator theta' = omega, r' = 1 - r whose PRCs are known in closed
  form (eq. 9) — used by the tests as an exactly known system.
* Sect. 6.2 / Fig. 4, delay coordinates (v, v_d), v_d(t) = v(t - delta): the PRC "holding v_d
  constant" is not the PRC holding w constant; the delay map's Jacobian converts one into the
  other. Here both delay-coordinate partials are measured by perturbing along the directions
  that hold the other delay coordinate fixed, and converted with the Jacobian, so the corrected
  curve is computed independently of the ground truth it is compared with.

The adjoint PRC (Z' = -J^T Z along the cycle, normalised Z . f = 2 pi / T) is not the paper's
method — it needs the equations — and is here only as an independent check of the perturbation
estimate.
"""

from dataclasses import dataclass

import numpy as np
from scipy.integrate import odeint
from scipy.interpolate import CubicSpline
from scipy.optimize import fmin

PAPER = dict(a=0.7, b=0.8, c=3.0, z=-0.4)
TOL = 1e-10
TWO_PI = 2.0 * np.pi


def wrap(x):
    """Angle difference wrapped to (-pi, pi]."""
    return np.angle(np.exp(1j * np.asarray(x)))


class Oscillator:
    """A planar vector field f (vectorised over leading axes) with an optional Jacobian."""

    def __init__(self, f, jac=None, name="", params=None, x0=(1.0, 0.0)):
        self.f = f
        self._jac = jac
        self.name = name
        self.params = dict(params or {})
        self.x0 = np.asarray(x0, dtype=float)

    def jac(self, x):
        if self._jac is not None:
            return self._jac(x)
        x = np.asarray(x, dtype=float)
        h = 1e-7
        J = np.empty((2, 2))
        for j in range(2):
            e = np.zeros(2)
            e[j] = h
            J[:, j] = (self.f(x + e) - self.f(x - e)) / (2 * h)
        return J

    @property
    def has_jac(self):
        return self._jac is not None


def fhn(a=PAPER["a"], b=PAPER["b"], c=PAPER["c"], z=PAPER["z"]):
    """FHN of eq. 17 (Wilshin et al. 2024; RHS and Jacobian as in their Appendix B)."""

    def f(X):
        X = np.asarray(X, dtype=float)
        v, w = X[..., 0], X[..., 1]
        return np.stack([c * (v + w - v ** 3 / 3.0 + z), (a - v - b * w) / c], axis=-1)

    def jac(x):
        v = float(x[0])
        return np.array([[c * (1.0 - v * v), c], [-1.0 / c, -b / c]])

    return Oscillator(f, jac, name="fhn", params=dict(a=a, b=b, c=c, z=z), x0=(2.0, 0.0))


def hopf(omega=1.0):
    """Sect. 4.1's oscillator, theta' = omega, r' = 1 - r, in Cartesian (x, y)."""

    def f(X):
        X = np.asarray(X, dtype=float)
        x, y = X[..., 0], X[..., 1]
        r = np.sqrt(x * x + y * y)
        k = (1.0 - r) / r
        return np.stack([k * x - omega * y, k * y + omega * x], axis=-1)

    return Oscillator(f, None, name="hopf", params=dict(omega=omega), x0=(1.5, 0.0))


def fixed_point(a, b, c, z):
    """The FHN's unique fixed point (b < 1) and the trace / determinant of its Jacobian."""
    # v + (a - v)/b - v^3/3 + z = 0  ->  -v^3/3 + v (1 - 1/b) + a/b + z = 0
    roots = np.roots([-1.0 / 3.0, 0.0, 1.0 - 1.0 / b, a / b + z])
    v = float(np.real(roots[np.argmin(np.abs(np.imag(roots)))]))
    w = (a - v) / b
    J = np.array([[c * (1 - v * v), c], [-1 / c, -b / c]])
    return np.array([v, w]), float(np.trace(J)), float(np.linalg.det(J))


# ----------------------------------------------------------------------------- integration

def integrate(osc, x0, t, tol=TOL, mxstep=100000):
    """odeint with the Jacobian (when the oscillator has one) at tolerance `tol` (Appendix B)."""
    kw = dict(rtol=tol, atol=tol, mxstep=mxstep)
    if osc.has_jac:
        kw["Dfun"] = lambda y, _t: osc.jac(y)
    return odeint(lambda y, _t: osc.f(y), np.asarray(x0, dtype=float), np.asarray(t, dtype=float), **kw)


def integrate_many(osc, X0, t_end, tol=TOL, mxstep=500000):
    """Integrate many initial states at once for t_end: one stacked system whose Jacobian is
    block-diagonal (banded, ml = mu = 1), so the stiff solver stays cheap."""
    X0 = np.asarray(X0, dtype=float)
    y0 = X0.ravel()
    out = odeint(lambda y, _t: osc.f(y.reshape(-1, 2)).ravel(), y0, [0.0, float(t_end)], rtol=tol, atol=tol,
                 mxstep=mxstep, ml=1, mu=1)
    return out[-1].reshape(-1, 2)


def _up_crossings(t, v, level):
    i = np.nonzero((v[:-1] < level) & (v[1:] >= level))[0]
    return t[i] + (level - v[i]) * (t[i + 1] - t[i]) / (v[i + 1] - v[i])


def find_period(osc, x0=None, tol=TOL, refine=True, t_probe=150.0, n_relax=20, dt=0.01):
    """The period T and a point on the cycle (Appendix B): relax, estimate T from upward
    crossings of the first coordinate, then (refine) fmin on the loop distance."""
    x = osc.x0 if x0 is None else np.asarray(x0, dtype=float)
    t_span = t_probe
    for _ in range(6):
        ts = np.arange(0.0, t_span + dt / 2, dt)
        X = integrate(osc, x, ts, tol=tol)
        half = X[len(X) // 2:, 0]
        level = 0.5 * (half.max() + half.min())
        tc = _up_crossings(ts, X[:, 0], level)
        tc = tc[tc > t_span / 2]
        if len(tc) >= 3:
            break
        x = X[-1]
        t_span *= 2
    else:
        raise RuntimeError(f"{osc.name}: no sustained oscillation found (is the fixed point stable?)")
    T0 = float(np.median(np.diff(tc)))
    x = integrate(osc, X[-1], [0.0, n_relax * T0], tol=tol)[-1]
    ts = np.arange(0.0, 3 * T0, min(dt, T0 / 2000))
    X = integrate(osc, x, ts, tol=tol)
    tc = _up_crossings(ts, X[:, 0], level)
    if len(tc) < 2:
        raise RuntimeError(f"{osc.name}: lost the oscillation while relaxing")
    T1 = float(np.mean(np.diff(tc)))
    xc = integrate(osc, x, [0.0, tc[0]], tol=tol)[-1]
    if not refine:
        return T1, xc

    def loop(tcand):
        y1 = integrate(osc, xc, [0.0, float(np.ravel(tcand)[0])], tol=tol)[-1]
        return float(np.sum((xc - y1) ** 2))

    T = float(fmin(loop, T1, xtol=1e-12, ftol=1e-12, disp=False)[0])
    return T, xc


@dataclass
class LimitCycle:
    osc: Oscillator
    T: float
    states: np.ndarray      # (n, 2), uniform in time from phase 0
    phases: np.ndarray      # (n,), 2 pi k / n
    tol: float = TOL

    @property
    def n(self):
        return len(self.phases)

    def state_at(self, phase):
        p = np.mod(np.asarray(phase, dtype=float), TWO_PI)
        return np.stack([np.interp(p, self.phases, self.states[:, j], period=TWO_PI) for j in range(2)], axis=-1)

    def phase_of(self, P, chunk=500):
        """Phase of points near the cycle (Sect. 6.1.3): orthogonal projection onto the segment
        between the nearest cycle sample and its nearer neighbour, phases linearly interpolated."""
        P = np.atleast_2d(np.asarray(P, dtype=float))
        S, n, dphi = self.states, self.n, TWO_PI / self.n
        out = np.empty(len(P))
        for s in range(0, len(P), chunk):
            Q = P[s:s + chunk]
            d2 = ((Q[:, None, :] - S[None, :, :]) ** 2).sum(-1)
            i = np.argmin(d2, axis=1)
            best_d = np.full(len(Q), np.inf)
            best_p = np.zeros(len(Q))
            for step in (-1, 1):
                j = (i + step) % n
                a, b = S[i], S[j]
                ab = b - a
                tt = np.clip(((Q - a) * ab).sum(-1) / np.maximum((ab * ab).sum(-1), 1e-300), 0.0, 1.0)
                d = (((a + tt[:, None] * ab) - Q) ** 2).sum(-1)
                ph = self.phases[i] + step * tt * dphi
                take = d < best_d
                best_d[take], best_p[take] = d[take], ph[take]
            out[s:s + chunk] = best_p
        return np.mod(out, TWO_PI)


def limit_cycle(osc, n=2000, tol=TOL, refine=True, x0=None):
    """The limit cycle sampled uniformly in phase, phase 0 at the largest first coordinate."""
    T, xc = find_period(osc, x0=x0, tol=tol, refine=refine)
    t = np.linspace(0.0, T, n + 1)[:-1]
    X = integrate(osc, xc, t, tol=tol)
    k = int(np.argmax(X[:, 0]))
    X = np.roll(X, -k, axis=0)
    return LimitCycle(osc=osc, T=T, states=X, phases=TWO_PI * np.arange(n) / n, tol=tol)


# ----------------------------------------------------------------------------- PRCs

def base_indices(cycle, n_base):
    return np.unique(np.round(np.linspace(0, cycle.n, n_base, endpoint=False)).astype(int)) % cycle.n


def prc_perturbation(cycle, direction, eps=1e-2, n_base=200, n_periods=5, idx=None):
    """PRC along `direction` (a 2-vector, or one per base point) by finite perturbation
    (Sect. 6.1): states x +/- e d, e = eps / max(1, |d|), integrated n_periods periods, phase change / (2 eps).
    Returns (base phases, PRC in rad per unit of the perturbed coordinate)."""
    idx = base_indices(cycle, n_base) if idx is None else np.asarray(idx)
    X = cycle.states[idx]
    D = np.broadcast_to(np.asarray(direction, dtype=float), X.shape)
    # a long direction vector (e.g. (1, -g_v/g_w)) would move the state by much more than eps;
    # shrink the step so the state never moves more than eps (the derivative is unchanged)
    e = (eps / np.maximum(1.0, np.linalg.norm(D, axis=1)))[:, None]
    t_end = n_periods * cycle.T
    Xp = integrate_many(cycle.osc, X + e * D, t_end, tol=cycle.tol)
    Xm = integrate_many(cycle.osc, X - e * D, t_end, tol=cycle.tol)
    dth = wrap(cycle.phase_of(Xp) - cycle.phase_of(Xm))
    return cycle.phases[idx], dth / (2.0 * e[:, 0])


def prc_adjoint(cycle, n_periods=10):
    """Adjoint PRC Z (n, 2) on the cycle's samples: Z' = -J(gamma)^T Z integrated backward in
    time (where it is stable), normalised point by point so that Z . f = 2 pi / T."""
    T, n = cycle.T, cycle.n
    t = np.linspace(0.0, T, n + 1)
    S = np.vstack([cycle.states, cycle.states[:1]])
    spl = CubicSpline(t, S, bc_type="periodic")

    def rhs(Z, s):
        J = cycle.osc.jac(spl((-s) % T))
        return J.T @ Z

    s = np.arange((n_periods - 1) * n, n_periods * n + 1) * (T / n)
    s = np.concatenate([[0.0], s])
    Zs = odeint(rhs, np.array([1.0, 0.0]), s, rtol=1e-10, atol=1e-12, mxstep=500000)[1:]
    # s_j = (n_periods - 1) T + j T / n  ->  t = -s mod T = (n - j) T / n  -> index (n - j) mod n
    Z = np.empty((n, 2))
    j = np.arange(n + 1)
    Z[(n - j) % n] = Zs
    f = cycle.osc.f(cycle.states)
    Z *= ((TWO_PI / T) / np.sum(Z * f, axis=1))[:, None]
    return Z


def delay_jacobian(osc, X, delta, tol=TOL):
    """The delay map g(v, w) = v(t - delta) and its gradient (dg/dv|w, dg/dw|v) at states X, by
    integrating the state and its variational equation backward for delta."""

    def rhs(y, _t):
        x, P = y[:2], y[2:].reshape(2, 2)
        return np.concatenate([-osc.f(x), (-osc.jac(x) @ P).ravel()])

    g = np.empty(len(X))
    G = np.empty((len(X), 2))
    for k, x in enumerate(np.asarray(X, dtype=float)):
        y = odeint(rhs, np.concatenate([x, np.eye(2).ravel()]), [0.0, delta], rtol=tol, atol=tol, mxstep=100000)[-1]
        g[k] = y[0]
        G[k] = y[2:].reshape(2, 2)[0]
    return g, G


def delay_prcs(cycle, delta=0.1, eps=1e-2, n_base=200, n_periods=5, max_cond=1e3, hidden_lambda=None):
    """The voltage PRC in three coordinate systems, all at the same base points.

    * ground_truth   dtheta/dv | w fixed             (perturb v; the paper's "small perturbation")
    * w_prc          dtheta/dw | v fixed
    * constant_delay dtheta/dv | v_d fixed           (perturb along (1, -g_v/g_w): v_d unchanged)
    * vd_prc         dtheta/dv_d | v fixed           (perturb along (0, 1/g_w))
    * corrected      constant_delay + vd_prc * g_v   (Jacobian of (v, w) -> (v, v_d); ASSUMES the
                                                       hidden coordinate held fixed is w)
    * hidden_linear  dtheta/dv | h fixed, h = w + lambda v (a linear change of the hidden coordinate)
    `well_conditioned` marks base points where the delay map's Jacobian has condition < max_cond.
    """
    idx = base_indices(cycle, n_base)
    X = cycle.states[idx]
    ph, rv = prc_perturbation(cycle, [1.0, 0.0], eps, idx=idx, n_periods=n_periods)
    _, rw = prc_perturbation(cycle, [0.0, 1.0], eps, idx=idx, n_periods=n_periods)
    g, G = delay_jacobian(cycle.osc, X, delta, tol=cycle.tol)
    gv, gw = G[:, 0], G[:, 1]
    cond = np.array([np.linalg.cond(np.array([[1.0, 0.0], [a, b]])) for a, b in zip(gv, gw)])
    ok = np.isfinite(cond) & (cond < max_cond)
    gw_safe = np.where(np.abs(gw) > 1e-12, gw, np.nan)
    d_v = np.stack([np.ones_like(gv), -gv / gw_safe], axis=1)
    d_vd = np.stack([np.zeros_like(gv), 1.0 / gw_safe], axis=1)
    d_v[~ok] = [1.0, 0.0]
    d_vd[~ok] = [0.0, 1.0]
    _, rcd = prc_perturbation(cycle, d_v, eps, idx=idx, n_periods=n_periods)
    _, rvd = prc_perturbation(cycle, d_vd, eps, idx=idx, n_periods=n_periods)
    rcd[~ok] = np.nan
    rvd[~ok] = np.nan
    if hidden_lambda is None:
        v, w = cycle.states[:, 0], cycle.states[:, 1]
        hidden_lambda = float(np.ptp(w) / np.ptp(v))
    return dict(phases=ph, idx=idx, delta=float(delta), eps=float(eps), ground_truth=rv, w_prc=rw,
                constant_delay=rcd, vd_prc=rvd, corrected=rcd + rvd * gv,
                chain_rule_constant_delay=rv - rw * gv / gw_safe,
                hidden_linear=rv - hidden_lambda * rw, hidden_lambda=hidden_lambda,
                g=g, g_v=gv, g_w=gw, cond=cond, well_conditioned=ok)


def isochron_ticks(cycle, phases, prc_v, prc_w, length, scale=(1.0, 1.0)):
    """Short segments along the isochrons through the base points: the isochron's tangent t
    satisfies prc_v t_v + prc_w t_w = 0, so t = (-prc_w, prc_v) in (v, w). `scale` = the plot's
    (v, w) units per unit length, so ticks have one drawn length. Returns (k, 2, 2) in (v, w)."""
    P = cycle.state_at(phases)
    t = np.stack([-np.asarray(prc_w), np.asarray(prc_v)], axis=1) / np.asarray(scale)
    t /= np.linalg.norm(t, axis=1, keepdims=True)
    t *= length * np.asarray(scale)
    return np.stack([P - 0.5 * t, P + 0.5 * t], axis=1)


def simulated_noisy_prc(cycle, n_obs=600, eps=0.05, noise_sd=0.0, n_periods=5, seed=0):
    """A simulated perturbation experiment ON THE MODEL (Sect. 6.2's "phase change" cloud):
    random cycle points, a voltage step of +/-eps, the end point observed with Gaussian noise of
    noise_sd on both coordinates, phase change / step. Not a measurement of any recording."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, cycle.n, n_obs)
    sgn = rng.choice([-1.0, 1.0], n_obs)
    X = cycle.states[idx].copy()
    X[:, 0] += sgn * eps
    Xe = integrate_many(cycle.osc, X, n_periods * cycle.T, tol=max(cycle.tol, 1e-9))
    Xe = Xe + noise_sd * rng.standard_normal(Xe.shape)
    base_end = cycle.phases[idx]          # the base point returns to itself after whole periods
    return cycle.phases[idx], wrap(cycle.phase_of(Xe) - base_end) / (sgn * eps)


def rolling_median(x, y, window=0.15, n_out=200):
    """Windowed (circular) median of y against phase x in [0, 2 pi)."""
    grid = np.linspace(0.0, TWO_PI, n_out, endpoint=False)
    out = np.full(n_out, np.nan)
    for k, g in enumerate(grid):
        m = np.abs(wrap(x - g)) < window / 2
        if m.sum() >= 3:
            out[k] = np.median(y[m])
    return grid, out
