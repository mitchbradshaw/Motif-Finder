"""
The Hindmarsh-Rose bursting model, and the test that decides whether a drop train has bursts to fit it to.

    x' = y - a x^3 + b x^2 - z + I,     y' = c - d x^2 - y,     z' = r (s (x - x_R) - z)

with the standard a = 1, b = 3, c = 1, d = 5, s = 4, x_R = -1.6 (Hindmarsh & Rose 1984, Proc. R. Soc. B
221:87-102). r sets the slow time scale; at r = 0.005 and I in about (1.4, 3.2) the orbit bursts: groups of
spikes separated by quiet stretches, the groups paced by the slow variable z.

**Bursts in a drop train** (`burst_structure`). Hindmarsh-Rose is only worth fitting where a train is made of
groups of drops. The rule, fixed before any train was looked at: split the onsets wherever a gap exceeds
`SPLIT` x the median gap; the train is bursting when at least `MIN_BURSTS` groups of at least `MIN_SIZE`
drops come out and the long gaps are at least `MIN_LONG_FRACTION` of all gaps. A regular train (one beat,
some jitter) has no gap three times its median and is not bursting.

`bursting_orbit` gives one period of a bursting orbit (burst onset to burst onset, found as upward crossings
of z through the middle of its range), for the per-burst fit and PRC.
"""

import numpy as np

from Pipelines.fhn import model as M

STD = dict(a=1.0, b=3.0, c=1.0, d=5.0, s=4.0, x_R=-1.6)
SPLIT = 3.0
MIN_BURSTS = 3
MIN_SIZE = 3
MIN_LONG_FRACTION = 0.05


def rhs(r, I, p=STD):
    a, b, c, d, s, xr = p["a"], p["b"], p["c"], p["d"], p["s"], p["x_R"]

    def f(X):
        X = np.asarray(X, dtype=float)
        x, y, z = X[..., 0], X[..., 1], X[..., 2]
        return np.stack([y - a * x ** 3 + b * x ** 2 - z + I, c - d * x ** 2 - y, r * (s * (x - xr) - z)], axis=-1)

    def jac(X):
        x = float(X[0])
        return np.array([[-3 * a * x * x + 2 * b * x, 1.0, -1.0], [-2 * d * x, -1.0, 0.0], [r * s, 0.0, -r]])

    return f, jac


def simulate(r, I, t_end, dt=0.05, x0=(-1.6, -10.0, 2.0), tol=1e-8):
    f, jac = rhs(r, I)
    t = np.arange(0.0, t_end, dt)
    from scipy.integrate import odeint
    X = odeint(lambda y, _t: f(y), np.asarray(x0, float), t, Dfun=lambda y, _t: jac(y), rtol=tol, atol=tol,
               mxstep=200000)
    return t, X


def spike_times(t, x, level=1.0):
    return M._up_crossings(t, x, level)


def burst_structure(onsets, split=SPLIT, min_bursts=MIN_BURSTS, min_size=MIN_SIZE, min_long=MIN_LONG_FRACTION):
    """Groups of events split at gaps > split x the median gap; `bursting` by the rule in the module doc."""
    on = np.sort(np.asarray(onsets, float))
    if on.size < min_bursts * min_size:
        return dict(bursting=False, n_groups=1, why=f"{on.size} events", group_sizes=[int(on.size)])
    g = np.diff(on)
    med = float(np.median(g))
    long_ = g > split * med
    cuts = np.nonzero(long_)[0]
    sizes = np.diff(np.concatenate([[0], cuts + 1, [on.size]])).astype(int)
    big = int(np.sum(sizes >= min_size))
    frac = float(long_.mean())
    bursting = bool(big >= min_bursts and frac >= min_long)
    return dict(bursting=bursting, n_groups=int(sizes.size), n_groups_of_min_size=big, long_gap_fraction=frac,
                median_gap=med, split=split, group_sizes=sizes.tolist(),
                why=("bursting" if bursting else f"{big} groups of >= {min_size} drops, long gaps {frac:.3f} of gaps"))


def bursting_orbit(r=0.005, I=2.0, n=2000, t_relax=3000.0, dt=0.02):
    """One period of the bursting orbit, burst onset to burst onset (upward crossings of z's middle)."""
    t, X = simulate(r, I, t_relax, dt=dt)
    z = X[:, 2]
    half = z[len(z) // 2:]
    level = 0.5 * (half.max() + half.min())
    tc = M._up_crossings(t, z, level)
    tc = tc[tc > t_relax / 2]
    if len(tc) < 3:
        raise RuntimeError("bursting_orbit: no slow oscillation")
    T = float(np.median(np.diff(tc[-3:])))
    t0 = tc[-2]
    ts = np.linspace(t0, t0 + T, n, endpoint=False)
    S = np.stack([np.interp(ts, t, X[:, j]) for j in range(3)], axis=1)
    sp = spike_times(t, X[:, 0])
    n_sp = int(np.sum((sp >= t0) & (sp < t0 + T)))
    return dict(T=T, states=S, phases=2 * np.pi * np.arange(n) / n, spikes_per_burst=n_sp)
