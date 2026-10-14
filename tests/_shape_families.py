"""
_shape_families.py
====================
Synthetic shape families for the Library's shape methods (w2-b): k-Shape,
HDBSCAN and the SVD-entropy coherence score. Not a test module (leading
underscore); imported by `test_library_grouping_methods.py` and
`test_library_coherence.py`.

Three families the prompt names, each member cut from its own window so the
event sits at a random offset (up to 20 % of the window either way — the
stored event edges are often off), at a random amplitude, on a COLOURED
background (00-common's lesson from wave 1: white noise alone is not a test):

  drop     a fast fall and a slow exponential recovery (negative-going)
  shark    a slow linear charge and a fast fall (a sharkfin)
  square   a square pulse

Backgrounds: AR(1) with phi = 0.95 or 0.99, a detrended random walk, and a
slow sine drift under AR(1). The background's standard deviation is
`noise` x the event's amplitude.
"""

import numpy as np


def _ar1(n, phi, rng):
    """Unit-variance AR(1)."""
    e = rng.normal(0.0, np.sqrt(1.0 - phi ** 2), n)
    x = np.empty(n)
    x[0] = rng.normal()
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


def _detrend(x):
    t = np.arange(x.size)
    return x - np.polyval(np.polyfit(t, x, 1), t)


def background(n, kind, rng):
    """A unit-scale coloured background of `n` samples."""
    if kind == "ar1_095":
        return _ar1(n, 0.95, rng)
    if kind == "ar1_099":
        return _ar1(n, 0.99, rng)
    if kind == "random_walk":
        x = _detrend(np.cumsum(rng.normal(size=n)))
        return x / (x.std() or 1.0)
    if kind == "drift":
        t = np.arange(n)
        return 0.7 * _ar1(n, 0.95, rng) + np.sin(2 * np.pi * t / (n * rng.uniform(1.5, 3.0))
                                                  + rng.uniform(0, 2 * np.pi))
    if kind == "white":
        return rng.normal(size=n)
    raise ValueError(kind)


def drop(u):
    return np.where(u < 0, 0.0, -np.exp(-np.clip(u, 0, None) / 0.25)) * (u < 1.5)


def shark(u):
    return (np.where((u >= 0) & (u < 1), u, 0.0)
            + np.where((u >= 1) & (u < 1.05), 1 - (u - 1) / 0.05, 0.0))


def square(u):
    return ((u >= 0) & (u < 0.35)).astype(float)


SHAPES = (drop, shark, square)


def member(shape, rng, *, noise=0.08, kind="ar1_095", max_shift=0.2):
    """One window of 120-179 samples holding `shape` at a random offset (up
    to `max_shift` of the window either way) and amplitude."""
    n = int(rng.integers(120, 180))
    t = np.arange(n) / n
    onset = 0.3 + rng.uniform(-max_shift, max_shift)
    amp = rng.uniform(0.5, 3.0)
    return amp * shape((t - onset) / 0.4) + noise * amp * background(n, kind, rng)


def three_families(per=30, seed=0, *, noise=0.08, kind="ar1_095", n_noise=0, max_shift=0.2):
    """`(waveforms, truth)`: `per` members of each family (truth 0, 1, 2) and
    `n_noise` pure-background windows (truth -1) of the same kind."""
    rng = np.random.default_rng(seed)
    waves, truth = [], []
    for f, shape in enumerate(SHAPES):
        for _ in range(per):
            waves.append(member(shape, rng, noise=noise, kind=kind, max_shift=max_shift))
            truth.append(f)
    for _ in range(n_noise):
        waves.append(background(int(rng.integers(120, 180)), kind, rng))
        truth.append(-1)
    return waves, np.array(truth)


def pure_noise(n=150, seed=0, kind="ar1_095"):
    rng = np.random.default_rng(seed)
    return [background(int(rng.integers(120, 180)), kind, rng) for _ in range(n)]
