"""
_minirocket_synthetic.py
========================
w2-c: synthetic windows for the `catalogue.minirocket` tests.

Three window classes that differ ONLY in shape — each template is z-normalised,
so every class has mean 0 and variance 1 before the background is added:

* 0 — a drop with a slow recovery (sharp fall, exponential return);
* 1 — a symmetric dip (a Gaussian bump downwards);
* 2 — a step (a fast sigmoid down that stays down).

The event sits at a random place in the middle half of its window. The
backgrounds are the coloured ones 00-common.md asks for (fungal recordings at
1 Hz are not white): AR(1) with phi = 0.97, a detrended random walk, and a slow
sine drift under white noise. Every background is scaled to unit variance per
window before it is added at `noise` times the shape's own spread.
"""

import numpy as np

L = 600          # 600 s windows at 1 Hz, the template's geometry
FS = 1.0
BACKGROUNDS = ("ar1", "random_walk", "drift")


def ar1(n, phi, rng):
    e = rng.standard_normal(n)
    out = np.empty(n)
    out[0] = e[0] / np.sqrt(1 - phi ** 2)
    for i in range(1, n):
        out[i] = phi * out[i - 1] + e[i]
    return out


def background(kind, n, rng):
    if kind == "ar1":
        b = ar1(n, 0.97, rng)
    elif kind == "random_walk":
        b = np.cumsum(rng.standard_normal(n))
        i = np.arange(n, dtype=float)
        b = b - np.polyval(np.polyfit(i, b, 1), i)
    elif kind == "drift":
        i = np.arange(n, dtype=float)
        b = 2.0 * np.sin(2 * np.pi * i / (n * rng.uniform(0.8, 1.6)) + rng.uniform(0, 2 * np.pi)) \
            + 0.5 * rng.standard_normal(n)
    else:
        raise ValueError(kind)
    return (b - b.mean()) / b.std()


def shape(k, rng, n=L):
    i = np.arange(n, dtype=float)
    c = rng.uniform(0.25, 0.75) * n
    if k == 0:
        y = np.where(i < c, 0.0, -np.exp(-(i - c) / (0.12 * n)))
    elif k == 1:
        y = -np.exp(-0.5 * ((i - c) / (0.05 * n)) ** 2)
    elif k == 2:
        y = -1.0 / (1.0 + np.exp(-(i - c) / 3.0))
    else:
        raise ValueError(k)
    return (y - y.mean()) / y.std()


def windows(n_per_class=60, background_kind="ar1", noise=1.0, seed=1, n=L):
    """`(W, y)`: `(3 * n_per_class, n)` windows in a shuffled order and their class."""
    rng = np.random.default_rng(seed)
    W, y = [], []
    for k in range(3):
        for _ in range(n_per_class):
            W.append(shape(k, rng, n) + noise * background(background_kind, n, rng))
            y.append(k)
    W = np.asarray(W)
    y = np.asarray(y)
    order = rng.permutation(len(y))
    return W[order], y[order]


def recording(n_per_class=60, background_kind="ar1", noise=1.0, seed=1, n=L, lead=0):
    """`(x, y)`: the windows laid end to end into one channel (after `lead` samples
    of background), so a tiling window set of length `n` slices them back."""
    W, y = windows(n_per_class, background_kind, noise, seed, n)
    head = background(background_kind, max(lead, 2), np.random.default_rng(seed + 99))[:lead]
    return np.concatenate([head, W.ravel()]), y
