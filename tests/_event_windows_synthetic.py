"""
_event_windows_synthetic.py
=============================
Synthetic recordings for the `catalogue.event_windows` tests (w2-a): drops with
KNOWN onsets on the coloured backgrounds wave 1 taught us to test on (00-common.md
"Lessons from wave 1") — white noise, a detrended random walk, an AR(1) with
phi = 0.97, and a slow sine drift — plus the dense case, a chain of drops 30 min
apart on the AR(1).

A drop: flat until its onset, a linear fall over `fall_s` to `depth`, then an
exponential recovery with time constant `tau_s`. Units are volts (M2's stored unit).
"""

import numpy as np
import pandas as pd

from Working.types import SpanSet

FS = 1.0
BACKGROUNDS = ("white", "random_walk", "ar1", "sine_drift")


def background(kind, n, seed=0, scale=0.0005):
    rng = np.random.default_rng(seed)
    e = rng.standard_normal(n)
    if kind == "white":
        b = e
    elif kind == "random_walk":
        b = np.cumsum(e) * 0.05
        tt = np.arange(n)
        b = b - np.polyval(np.polyfit(tt, b, 1), tt)
    elif kind == "ar1":
        b = np.empty(n)
        b[0] = e[0]
        for i in range(1, n):
            b[i] = 0.97 * b[i - 1] + e[i]
        b = b * 0.25
    elif kind == "sine_drift":
        b = 0.3 * e + 4.0 * np.sin(np.arange(n) / 2000.0)
    else:
        raise ValueError(kind)
    return -0.44 + scale * b


def drop(n, onset, depth=0.01, fall_s=20, tau_s=200.0):
    """The drop's waveform alone (0 before the onset)."""
    d = np.zeros(n)
    fall = np.arange(1, fall_s + 1) / fall_s
    end_fall = min(n, onset + fall_s)
    d[onset:end_fall] = -depth * fall[: end_fall - onset]
    rest = np.arange(n - end_fall)
    d[end_fall:] = -depth * np.exp(-rest / tau_s)
    return d


def chain(kind="ar1", n=None, spacing_s=1800, first=1200, n_events=12, seed=0, depths=None, fall_s=20):
    """A recording with `n_events` drops every `spacing_s` seconds; returns (x, onsets)."""
    if n is None:
        n = first + spacing_s * n_events + 1200
    x = background(kind, n, seed=seed)
    onsets = [first + i * spacing_s for i in range(n_events)]
    for i, o in enumerate(onsets):
        dep = 0.01 if depths is None else depths[i % len(depths)]
        x = x + drop(n, o, depth=dep, fall_s=fall_s)
    return x, onsets


def spans_for(onsets, pre=30, post=600, with_onset_idx=True, extra=None):
    """A SpanSet with one span per onset, [o - pre, o + post), and (optionally) Event
    shape's span-relative `onset_idx` / `extremum_idx` columns."""
    starts = tuple(int(o - pre) for o in onsets)
    ends = tuple(int(o + post) for o in onsets)
    cols = {}
    if with_onset_idx:
        cols["onset_idx"] = [float(o) for o in onsets]
        cols["extremum_idx"] = [float(o + 20) for o in onsets]
        cols["event_amplitude_mv"] = [10.0 + i for i in range(len(onsets))]
        cols["duration_s"] = [float(post) for _ in onsets]
        cols["polarity"] = [-1] * len(onsets)
    if extra:
        cols.update(extra)
    feats = pd.DataFrame(cols) if cols else None
    return SpanSet(starts=starts, ends=ends, features=feats)
