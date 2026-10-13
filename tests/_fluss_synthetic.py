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


# ── jittered (realistic) recordings ──────────────────────────────────────────
#
# The clockwork regimes above put every event on a fixed grid with a fixed
# shape, which flatters any window. A real recording jitters: here every gap is
# log-normal around the regime's period (sd 0.4 in log space, mean preserved),
# every amplitude log-normal (sd 0.3), every drop's recovery time constant and
# every bump's width log-normal (sd 0.3 / 0.2). `NOISE_HIGH` is white noise at
# 0.3 — of the order of a single event's height.

NOISE_HIGH = 0.3
SPACING_SD = 0.4
AMP_SD = 0.3


def _lognormal(rng, sd):
    """A multiplicative factor with median exp(-sd²/2) and mean 1."""
    return float(np.exp(sd * rng.standard_normal() - 0.5 * sd * sd))


def _jittered_a(n, rng):
    t = np.arange(n, dtype=float)
    x = np.zeros(n)
    s = 100.0 * _lognormal(rng, SPACING_SD)
    while s < n:
        i = int(s)
        tau = 300.0 * _lognormal(rng, 0.3)
        x[i:] += -1.0 * _lognormal(rng, AMP_SD) * np.exp(-(t[i:] - i) / tau)
        s += 900.0 * _lognormal(rng, SPACING_SD)
    return x - x.mean()


def _jittered_b(n, rng):
    t = np.arange(n, dtype=float)
    x = np.zeros(n)
    c = 150.0 * _lognormal(rng, SPACING_SD)
    while c < n:
        sigma = 50.0 * _lognormal(rng, 0.2)
        x += 0.8 * _lognormal(rng, AMP_SD) * np.exp(-0.5 * ((t - c) / sigma) ** 2)
        c += 300.0 * _lognormal(rng, SPACING_SD)
    return x - x.mean()


def two_regimes_jittered(seed=0, noise=NOISE):
    """Jittered regime A (2 h) then jittered regime B (2 h), white noise at
    `noise`, the same slow linear drift. Boundary at `BOUNDARY`."""
    rng = np.random.default_rng(seed)
    n = 2 * HALF
    return (np.concatenate([_jittered_a(HALF, rng), _jittered_b(HALF, rng)])
            + noise * rng.standard_normal(n) + np.linspace(0.0, 3.0, n))


def one_regime_jittered(seed=0, noise=NOISE):
    """4 h of jittered regime A: no change."""
    rng = np.random.default_rng(seed)
    n = 2 * HALF
    return _jittered_a(n, rng) + noise * rng.standard_normal(n) + np.linspace(0.0, 3.0, n)


# ── nulls without events ──────────────────────────────────────────────────────

def pink_noise(seed=0):
    """4 h of 1/f noise (white noise shaped in the frequency domain), unit sd."""
    rng = np.random.default_rng(seed)
    n = 2 * HALF
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, d=1.0 / FS)
    f[0] = f[1]
    x = np.fft.irfft(spec / np.sqrt(f), n)
    return (x - x.mean()) / x.std()


def random_walk(seed=0):
    """4 h of a Gaussian random walk (step sd 0.05) — Brownian drift."""
    rng = np.random.default_rng(seed)
    return np.cumsum(0.05 * rng.standard_normal(2 * HALF))


def sinusoidal_drift(seed=0):
    """4 h of a slow sinusoid (period 100 min, amplitude 2, random phase) plus
    white noise at `NOISE`: a drift that is not a ramp."""
    rng = np.random.default_rng(seed)
    n = 2 * HALF
    t = np.arange(n, dtype=float) / FS
    return (2.0 * np.sin(2 * np.pi * t / 6000.0 + rng.uniform(0, 2 * np.pi))
            + NOISE * rng.standard_normal(n))
