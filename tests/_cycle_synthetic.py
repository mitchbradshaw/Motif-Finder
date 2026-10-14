"""
_cycle_synthetic.py
=====================
Synthetic chains of cycles for the w3-b tests (`interrogation.cycle_shapes`).

Every cycle runs from one drop to the next and has amplitude 1 (a drop to -1
from a pre-drop level of 0). Three shapes, each a function of the phase p in
[0, 1):

* `sharkfin(p, floor)` — a drop over 2 % of the cycle, a flat floor for
  `floor` of it, then a straight climb back to 0 by p = 0.98 (the researcher:
  a sharkfin sits on its floor for 1/2-2/3 of the interval);
* `trough(p)` — the same drop, then an exponential recovery with a time
  constant of 5 % of the cycle: half back at p ~ 0.055, mostly back by 0.25;
* `hump(p)` — a broad smooth dip, -sin(pi p)^2, filling the cycle (the shape
  `Working.library.coherence.SMOOTH_CAVEAT` names).

Backgrounds (wave 1's lesson: never only white noise), each scaled so the
noise is ~`noise` x the drop within a cycle:
* `ar1` — AR(1), phi 0.98, sd `noise`;
* `rw` — a random walk, detrended over the whole recording, scaled so its
  step sd is 2 x noise / sqrt(1800) (a 30-min Brownian bridge of sd ~noise);
* `drift` — AR(1) phi 0.95 of sd `noise` under a 10-h sine of amplitude 2
  (twice the drop).

A chain has `lead_s` and `tail_s` of background with no event on either side
(the quiet stretches the background null cuts from).
"""

import numpy as np
from scipy.signal import lfilter

BACKGROUNDS = ("ar1", "rw", "drift")


def sharkfin(p, floor=0.5):
    p = np.asarray(p, float)
    d = 0.02
    c0, c1 = d + floor, 0.98
    y = np.zeros_like(p)
    y = np.where(p < d, -p / d, y)
    y = np.where((p >= d) & (p < c0), -1.0, y)
    y = np.where((p >= c0) & (p < c1), -1.0 + (p - c0) / (c1 - c0), y)
    return y


def trough(p, tau=0.05):
    p = np.asarray(p, float)
    d = 0.02
    return np.where(p < d, -p / d, -np.exp(-(p - d) / tau))


def hump(p):
    return -np.sin(np.pi * np.asarray(p, float)) ** 2


def background(n, kind, rng, noise, fs=1.0):
    """`n` samples of background at `fs` Hz (time constants scale with fs, so the
    same chain at 1 and 10 Hz has the same background in seconds)."""
    if kind == "white":
        return rng.standard_normal(n) * noise
    if kind == "ar1":
        phi = 0.98 ** (1.0 / fs)
        b = lfilter([1.0], [1.0, -phi], rng.standard_normal(n))
        return b / b.std() * noise
    if kind == "rw":
        b = np.cumsum(rng.standard_normal(n))
        t = np.arange(n)
        b = b - np.polyval(np.polyfit(t, b, 1), t)
        step = 2.0 * noise / np.sqrt(1800.0 * fs)
        return b / np.std(np.diff(b)) * step
    if kind == "drift":
        phi = 0.95 ** (1.0 / fs)
        b = lfilter([1.0], [1.0, -phi], rng.standard_normal(n))
        t = np.arange(n) / fs
        return b / b.std() * noise + 2.0 * np.sin(2 * np.pi * t / (10 * 3600.0))
    raise ValueError(kind)


def chain(shapes, periods_s, *, fs=1.0, bg="ar1", noise=0.15, seed=0, lead_s=3600.0, tail_s=3600.0):
    """`(x, starts, ends)`: one cycle per shape (callables of the phase), cycle k
    `periods_s[k]` long; an event at the start of every cycle and one closing
    the last (its span 5 % of the cycle)."""
    rng = np.random.default_rng(seed)
    lens = np.round(np.asarray(periods_s, dtype=float) * fs).astype(int)
    lead, tail = int(lead_s * fs), int(tail_s * fs)
    n = lead + int(lens.sum()) + tail
    x = np.zeros(n)
    starts = []
    s = lead
    for L, f in zip(lens, shapes):
        x[s:s + L] += f(np.arange(L) / L)
        starts.append(s)
        s += L
    starts.append(s)
    x = x + background(n, bg, rng, noise, fs)
    starts = np.asarray(starts, dtype=np.int64)
    ends = np.minimum(starts + np.maximum(2, (0.05 * np.r_[lens, lens[-1]]).astype(int)), n)
    return x, starts, ends


def drifting_periods(n=120, lo_s=1200.0, hi_s=3600.0):
    """A period drifting from 20 to 60 minutes over the chain."""
    return np.linspace(lo_s, hi_s, n)


def two_family_chain(bg, seed=1, fs=1.0, noise=0.15):
    """60 sharkfins then 60 troughs over a 20 -> 60 min period: the acceptance chain."""
    return chain([sharkfin] * 60 + [trough] * 60, drifting_periods(), fs=fs, bg=bg, noise=noise, seed=seed)


def plateau_drift_chain(bg, seed=1, noise=0.15):
    """120 sharkfins whose floor lengthens steadily from 0.3 to 0.7: one family that varies."""
    shapes = [(lambda p, f=f: sharkfin(p, f)) for f in np.linspace(0.3, 0.7, 120)]
    return chain(shapes, drifting_periods(), bg=bg, noise=noise, seed=seed)


def poisson_events(n_cycles, bg, seed=1, noise=0.15, mean_gap_s=1800.0, fs=1.0):
    """No structure: Poisson event times on coloured noise, `n_cycles` cycles."""
    rng = np.random.default_rng(seed + 100)
    starts = np.round((3600.0 + np.cumsum(rng.exponential(mean_gap_s, n_cycles + 1))) * fs).astype(np.int64)
    n = int(starts[-1] + 3600 * fs)
    x = background(n, bg, np.random.default_rng(seed), noise, fs)
    return x, starts, np.minimum(starts + int(30 * fs), n)


def regular_events(n_cycles, bg, seed=1, noise=0.15, mean_gap_s=1800.0, cv=0.3, fs=1.0, lead_s=3600.0,
                   span_frac=None):
    """No structure with chain-like timing (the W3-B critic's B1 case): event gaps lognormal with this CV
    around `mean_gap_s`, on coloured noise only. `span_frac` (e.g. 0.9) makes each event's span cover that
    share of its cycle, so no free stretch holds a cycle and the background null falls back."""
    rng = np.random.default_rng(seed + 200)
    sig = np.sqrt(np.log(1 + cv ** 2))
    gaps = mean_gap_s * np.exp(rng.normal(-0.5 * sig ** 2, sig, n_cycles + 1))
    starts = np.round((lead_s + np.r_[0.0, np.cumsum(gaps[:-1])]) * fs).astype(np.int64)
    n = int(starts[-1] + lead_s * fs)
    x = background(n, bg, np.random.default_rng(seed), noise, fs)
    if span_frac is None:
        ends = np.minimum(starts + int(30 * fs), n)
    else:
        nxt = np.r_[starts[1:], n]
        ends = starts + np.maximum(2, (span_frac * (nxt - starts)).astype(np.int64))
    return x, starts, ends


def mixed_colour_chain(n_cycles, seed=1, noise=0.15, margin_s=10 * 3600.0, shapes=None, cv=0.3,
                       margin_bg="ar095", chain_bg="rw"):
    """The W3-B re-critique's S-A case: quiet margins of one colour (AR(1) phi 0.95) either side of a chain
    region whose background is another (a random walk). `shapes` None = no events' shape at all (chain-timed
    noise); else one shape callable per cycle, added on the chain-region background."""
    rng = np.random.default_rng(seed + 300)
    sig = np.sqrt(np.log(1 + cv ** 2))
    gaps = 1800.0 * np.exp(rng.normal(-0.5 * sig ** 2, sig, n_cycles))
    lead = int(margin_s)
    starts = np.round(lead + np.r_[0.0, np.cumsum(gaps)]).astype(np.int64)
    n = int(starts[-1] + margin_s)
    brng = np.random.default_rng(seed)
    if margin_bg == "ar095":
        m = lfilter([1.0], [1.0, -0.95], brng.standard_normal(n))
        x = m / m.std() * noise
    else:
        x = background(n, margin_bg, brng, noise)
    a, b = int(starts[0]), int(starts[-1])
    x[a:b] = background(b - a, chain_bg, brng, noise)
    if shapes is not None:
        for k, f in enumerate(shapes):
            L = int(starts[k + 1] - starts[k])
            x[starts[k]:starts[k + 1]] += f(np.arange(L) / L)
    return x, starts, np.minimum(starts + 30, n)
