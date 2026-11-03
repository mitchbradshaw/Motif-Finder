"""
The Morris-Lecar model with its two standard parameter sets, and a cycle fitter that tries both.

    C V' = I - gL (V - VL) - gCa m_inf(V) (V - VCa) - gK w (V - VK)
      w' = phi (w_inf(V) - w) / tau_w(V)
    m_inf = (1 + tanh((V - V1) / V2)) / 2,  w_inf = (1 + tanh((V - V3) / V4)) / 2,  tau_w = 1 / cosh((V - V3) / (2 V4))

Parameters as in Rinzel & Ermentrout (1998), "Analysis of neural excitability and oscillations", in Koch &
Segev (eds.), Methods in Neuronal Modeling, 2nd ed., MIT Press (also Ermentrout & Terman 2010, sect. 3.1):
C = 20, gK = 8, gL = 2, VCa = 120, VK = -84, VL = -60, V1 = -1.2, V2 = 18, and

* ``hopf``  (class II): gCa = 4.4, V3 = 2,  V4 = 30,   phi = 0.04  - oscillation is born in a Hopf
  bifurcation; its PRC near onset is two-signed (Type II);
* ``snic``  (class I):  gCa = 4,   V3 = 12, V4 = 17.4, phi = 1/15 - oscillation is born on a saddle-node on
  an invariant circle at I ~ 40; its PRC near onset is one-signed (Type I).

Time here is in units of 10 ms (the right-hand side is multiplied by `TIME_UNIT_MS`), so periods are tens of
units, like the other models'. The fit (`fit_ml`) frees the applied current I and phi in each class (with the
usual gain, offset, time scale and phase) and keeps the better class by RSS; the class is a discrete free
choice, counted in k (k = 7). Where the fit lands decides the PRC type - which is the point of fitting it.
"""

import numpy as np

from Pipelines.fhn import model as M
from Pipelines.fhn import oscfit as O

TIME_UNIT_MS = 10.0
COMMON = dict(C=20.0, gK=8.0, gL=2.0, VCa=120.0, VK=-84.0, VL=-60.0, V1=-1.2, V2=18.0)
CLASSES = {"hopf": dict(gCa=4.4, V3=2.0, V4=30.0, phi=0.04),
           "snic": dict(gCa=4.0, V3=12.0, V4=17.4, phi=1.0 / 15.0)}
BOUNDS = {"hopf": dict(I=(88.0, 260.0), phi=(0.01, 0.2)),
          "snic": dict(I=(39.7, 110.0), phi=(0.02, 0.25))}
STARTS = {"hopf": ((100.0, 0.04), (150.0, 0.04), (200.0, 0.08)),
          "snic": ((42.0, 1 / 15), (60.0, 1 / 15), (90.0, 0.12))}


def morris_lecar(I, phi=None, cls="snic"):
    p = COMMON | CLASSES[cls]
    if phi is not None:
        p["phi"] = float(phi)
    C, gK, gL, gCa = p["C"], p["gK"], p["gL"], p["gCa"]
    VCa, VK, VL, V1, V2, V3, V4, ph = p["VCa"], p["VK"], p["VL"], p["V1"], p["V2"], p["V3"], p["V4"], p["phi"]
    k = TIME_UNIT_MS

    def f(X):
        X = np.asarray(X, dtype=float)
        V, w = X[..., 0], X[..., 1]
        minf = 0.5 * (1 + np.tanh((V - V1) / V2))
        winf = 0.5 * (1 + np.tanh((V - V3) / V4))
        tau = 1.0 / np.cosh((V - V3) / (2 * V4))
        dV = (I - gL * (V - VL) - gCa * minf * (V - VCa) - gK * w * (V - VK)) / C
        dw = ph * (winf - w) / tau
        return k * np.stack([dV, dw], axis=-1)

    def jac(x):
        V, w = float(x[0]), float(x[1])
        sm, sw = 1.0 / np.cosh((V - V1) / V2) ** 2, 1.0 / np.cosh((V - V3) / V4) ** 2
        minf = 0.5 * (1 + np.tanh((V - V1) / V2))
        winf = 0.5 * (1 + np.tanh((V - V3) / V4))
        ch = np.cosh((V - V3) / (2 * V4))
        sh = np.sinh((V - V3) / (2 * V4))
        dVdV = (-gL - gCa * (0.5 * sm / V2) * (V - VCa) - gCa * minf - gK * w) / C
        dVdw = -gK * (V - VK) / C
        # dw = phi (winf - w) cosh(.)
        dwdV = ph * ((0.5 * sw / V4) * ch + (winf - w) * sh / (2 * V4))
        dwdw = -ph * ch
        return k * np.array([[dVdV, dVdw], [dwdV, dwdw]])

    return M.Oscillator(f, jac, name=f"morris_lecar_{cls}", params=dict(I=float(I), phi=ph, cls=cls),
                        x0=(0.0, 0.3))


def fit_ml(tau, y, restarts=2, max_nfev=150, classes=("hopf", "snic"), init=None):
    """Fit both classes; return the better one (by RSS), with the other's R2 and AIC kept beside it.
    `init`: {class: (I, phi)} tried first in that class."""
    fits = {}
    for cls in classes:
        starts = ([tuple(init[cls])] if init and cls in init else []) + list(STARTS[cls])
        try:
            fits[cls] = O.fit_planar(tau, y, lambda I, phi, _c=cls: morris_lecar(I, phi, _c), ("I", "phi"),
                                     BOUNDS[cls], starts, "morris_lecar", restarts=restarts, max_nfev=max_nfev,
                                     extra_k=1, extra_params=dict(cls=0.0 if cls == "hopf" else 1.0))
        except RuntimeError:
            continue
    if not fits:
        raise RuntimeError("fit_ml: neither class could be fitted")
    best_cls = min(fits, key=lambda c: fits[c]["rss"])
    out = dict(fits[best_cls])
    out["class"] = best_cls
    out["by_class"] = {c: dict(r2=f["r2"], aic=f["aic"], params=f["params"], on_bound=f["on_bound"])
                       for c, f in fits.items()}
    return out
