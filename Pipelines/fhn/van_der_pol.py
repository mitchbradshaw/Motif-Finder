"""
The van der Pol relaxation oscillator, in Lienard form, and its cycle fitter.

    v' = mu (v - v^3/3 - w),     w' = v / mu

mu is the relaxation parameter: near 0 the cycle is a sinusoid of period 2 pi and amplitude 2; for large mu
it is a relaxation oscillation (slow drift along the cubic's outer branches, fast jumps between them) of
period about (3 - 2 ln 2) mu. It is the simplest relaxation oscillator: a sanity bar between the sinusoid
(`fit.fit_sinusoid`) and FHN, which adds a recovery variable with its own linear term and an offset.

The fit (`fit_vdp`) is `oscfit.fit_planar`: free gain, offset, time scale and phase, plus mu. k = 5.
The PRC of any van der Pol cycle is two-signed (Type II: the fixed point loses stability in a Hopf).
"""

import numpy as np

from Pipelines.fhn import model as M
from Pipelines.fhn import oscfit as O

BOUNDS = dict(mu=(0.05, 12.0))
STARTS = ((0.5,), (1.5,), (4.0,), (9.0,))


def vdp(mu):
    def f(X):
        X = np.asarray(X, dtype=float)
        v, w = X[..., 0], X[..., 1]
        return np.stack([mu * (v - v ** 3 / 3.0 - w), v / mu], axis=-1)

    def jac(x):
        v = float(x[0])
        return np.array([[mu * (1.0 - v * v), -mu], [1.0 / mu, 0.0]])

    return M.Oscillator(f, jac, name="van_der_pol", params=dict(mu=mu), x0=(2.0, 0.0))


def fit_vdp(tau, y, restarts=4, max_nfev=200, init=None):
    starts = ([tuple(init)] if init is not None else []) + list(STARTS)
    return O.fit_planar(tau, y, vdp, ("mu",), BOUNDS, starts, "van_der_pol", restarts=restarts, max_nfev=max_nfev)
