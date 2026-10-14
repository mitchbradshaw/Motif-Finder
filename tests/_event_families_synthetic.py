"""
_event_families_synthetic.py
==============================
Synthetic recordings for the W2-E family blocks (`catalogue.shape_families`,
`interrogation.event_families`) and the `event_families` template. Not a test
module (leading underscore).

* `two_rhythms` — the template's case: two event shapes at two rhythms on an
  AR(1) background (phi = 0.97, M2's stored unit, volts): inverted sharkfins
  (a 240 s linear fall, a 15 s return) every 40 min and square dips (240 s flat
  at the bottom) every 3 h, both about 20 mV deep, their onsets chosen so that
  no square lands on a sharkfin (sharkfins at 600 s + 2400 s k, squares at
  1200 s + 10800 s k: always 600 s from the nearest sharkfin).
* `noise_events` — the no-structure case: a coloured background (AR(1) or a
  detrended random walk) with events at fixed times whose waveforms are
  phase-randomised copies of that background (each window's amplitude spectrum
  kept, its shape destroyed), and the SpanSet that marks them.
* `two_shapes` — clear-cut waveform families for the core: drops and square
  pulses (`_shape_families.member`, coloured backgrounds, random offsets and
  amplitudes).
"""

import numpy as np
import pandas as pd

from _shape_families import drop, member, square
from Working.types import SpanSet

FS = 1.0
SHARK_GAP_S = 2400       # 40 min
SQUARE_GAP_S = 10800     # 3 h
SHARK_FIRST_S = 600
SQUARE_FIRST_S = 1200
DEPTH_V = 0.02


def ar1(n, phi, rng):
    e = rng.standard_normal(n)
    b = np.empty(n)
    b[0] = e[0]
    for i in range(1, n):
        b[i] = phi * b[i - 1] + e[i]
    return b


def _shark(n, onset, depth, fall_s=240, back_s=15):
    d = np.zeros(n)
    d[onset:onset + fall_s] = -depth * np.arange(fall_s) / fall_s
    d[onset + fall_s:onset + fall_s + back_s] = -depth * (1 - np.arange(back_s) / back_s)
    return d


def _square(n, onset, depth, width_s=240):
    d = np.zeros(n)
    d[onset:onset + width_s] = -depth
    return d


def two_rhythms(hours=48, seed=0):
    """`(x, shark_onsets, square_onsets)` in samples (1 Hz)."""
    rng = np.random.default_rng(seed)
    n = int(hours * 3600)
    x = -0.44 + 0.0005 * 0.25 * ar1(n, 0.97, rng)
    sharks = list(range(SHARK_FIRST_S, n - 1200, SHARK_GAP_S))
    squares = list(range(SQUARE_FIRST_S, n - 1200, SQUARE_GAP_S))
    for o in sharks:
        x = x + _shark(n, o, DEPTH_V * rng.uniform(0.8, 1.2))
    for o in squares:
        x = x + _square(n, o, DEPTH_V * rng.uniform(0.8, 1.2))
    return x, sharks, squares


def truth_of(starts, sharks, squares):
    """0 = sharkfin, 1 = square, by the nearest planted onset to each span start."""
    sh, sq = np.asarray(sharks), np.asarray(squares)
    return np.array([0 if np.abs(sh - s).min() < np.abs(sq - s).min() else 1 for s in starts])


def _background(kind, n, rng):
    if kind == "ar1":
        return ar1(n, 0.97, rng)
    if kind == "ar1_099":
        return ar1(n, 0.99, rng)
    if kind == "random_walk":
        b = np.cumsum(rng.standard_normal(n))
        t = np.arange(n)
        return b - np.polyval(np.polyfit(t, b, 1), t)
    raise ValueError(kind)


def phase_randomise(w, rng):
    F = np.fft.rfft(w)
    ang = rng.uniform(0, 2 * np.pi, F.size)
    ang[0] = 0.0
    if w.size % 2 == 0:
        ang[-1] = 0.0
    return np.fft.irfft(F * np.exp(1j * ang), n=w.size)


def noise_events(kind="ar1", n_events=80, spacing_s=900, width_s=140, seed=0):
    """`(x, spans)`: a background with `n_events` spans every `spacing_s`, each span's
    samples replaced by a phase-randomised copy of themselves (no shape of their own)."""
    rng = np.random.default_rng(seed)
    n = 600 + n_events * spacing_s + 600
    x = _background(kind, n, rng)
    starts = [600 + i * spacing_s for i in range(n_events)]
    for s in starts:
        x[s:s + width_s] = phase_randomise(x[s:s + width_s], rng)
    spans = SpanSet(starts=tuple(starts), ends=tuple(s + width_s for s in starts),
                    features=pd.DataFrame({"polarity": [-1] * n_events}))
    return x, spans


def two_shapes(per=40, seed=0, kind="ar1_095", noise=0.08):
    """`(waveforms, truth)`: `per` drops (0) and `per` square pulses (1)."""
    rng = np.random.default_rng(seed)
    w, t = [], []
    for f, shape in enumerate((drop, square)):
        for _ in range(per):
            w.append(member(shape, rng, noise=noise, kind=kind))
            t.append(f)
    return w, np.array(t)


def equal_length(waves, length=150):
    """Cut / pad every waveform to one length (a WindowSet's windows are all one length)."""
    out = []
    for w in waves:
        w = np.asarray(w, dtype=float)
        out.append(w[:length] if w.size >= length else np.concatenate([w, np.full(length - w.size, w[-1])]))
    return np.vstack(out)
