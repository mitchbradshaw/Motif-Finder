"""
_fluss_synthetic.py
===================
Shared synthetic recordings for the FLUSS tests (`test_fluss.py`,
`test_adapter_fluss.py`, `test_template_fluss_regimes.py`), all at 1 Hz:

- `two_regimes`: 2 h of regime A (sharkfin-like drops — a sudden fall and a
  slow exponential recovery, tau 300 s — every 15 min) then 2 h of regime B
  (symmetric Gaussian bumps, sigma 50 s, every 5 min), plus white noise and a
  slow linear drift. The boundary is at sample `BOUNDARY` (7200).
- `one_regime`: 4 h of regime A, same noise and drift.
- `drift_ramp`: a pure linear ramp plus white noise, nothing else.

Each regime is zero-mean on its own: a recording's absolute level carries no
shape, and a level step at the boundary would be a second, easier change that
a rolling-mean detrend turns into a transient — the test is about a change of
*shape*, so the level is held fixed.
"""

import numpy as np

FS = 1.0
HALF = 7200                 # 2 h at 1 Hz
BOUNDARY = HALF
NOISE = 0.05


def _regime_a(n):
    t = np.arange(n, dtype=float)
    x = np.zeros(n)
    for s in range(100, n, 900):                       # a drop every 15 min
        seg = t[s:] - s
        x[s:] += -1.0 * np.exp(-seg / 300.0)           # sudden fall, slow recovery
    return x - x.mean()


def _regime_b(n):
    t = np.arange(n, dtype=float)
    x = np.zeros(n)
    for c in range(150, n, 300):                       # a bump every 5 min
        x += 0.8 * np.exp(-0.5 * ((t - c) / 50.0) ** 2)
    return x - x.mean()


def two_regimes(seed=0):
    rng = np.random.default_rng(seed)
    n = 2 * HALF
    return (np.concatenate([_regime_a(HALF), _regime_b(HALF)])
            + NOISE * rng.standard_normal(n) + np.linspace(0.0, 3.0, n))


def one_regime(seed=0):
    rng = np.random.default_rng(seed)
    n = 2 * HALF
    return _regime_a(n) + NOISE * rng.standard_normal(n) + np.linspace(0.0, 3.0, n)


def drift_ramp(seed=0):
    rng = np.random.default_rng(seed)
    n = 2 * HALF
    return np.linspace(0.0, 10.0, n) + NOISE * rng.standard_normal(n)
