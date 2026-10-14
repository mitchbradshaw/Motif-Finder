"""
_snippets_synthetic.py
=======================
Synthetic recordings for `catalogue.snippets` (W2-D), defined in seconds and
sampled at `FS`. `FS` is 0.1 Hz — one sample per 10 s — so a 1-hour piece is
360 samples and a 48 h recording 17 280: the method's O(n²) cost stays at a
few seconds per test, while every duration (pieces, periods, regimes, drift)
is the real one. The block takes its window from the WindowSet, so nothing in
it depends on the rate.

Three kinds of behaviour, 8 h each:

* `"drops"`  — sawtooth drops: a slow rise over ~30 min (jittered ±25 %),
  then a fall over ~1 min, amplitude 1, white noise 0.05.
* `"quiet"`  — quiet coloured noise: AR(1) with a 60 s correlation time
  (φ = exp(-1 / (60 fs)), φ ≈ 0.85 at 0.1 Hz, 0.98 at 1 Hz), sd 0.25.
* `"wave"`   — a slow oscillation: a sine of period ~20 min (the period
  wanders ±10 %), amplitude 0.7, white noise 0.05.

`three_regimes` concatenates them twice in two different orders (drops,
quiet, wave, then wave, drops, quiet) and can add a strong drift (a 20-hour
sine of amplitude 3 plus a ramp of 2 over the recording) — within one hour it
moves the level by about as much as the behaviour itself.

The nulls have no regimes at all: one AR(1) process throughout (φ for a 60 s
or a 10 min correlation time), a detrended random walk, and pink noise.
"""

import numpy as np

FS = 0.1
HOUR = 3600.0
PIECE = int(round(HOUR * FS))          # samples per 1-hour piece
REGIME_H = 8
ORDER = ("drops", "spikes", "wave", "wave", "drops", "spikes")
ORDER_QUIET = ("drops", "quiet", "wave", "wave", "drops", "quiet")
LABEL_OF = {"drops": 0, "quiet": 1, "spikes": 1, "wave": 2}


def _n(hours, fs=FS):
    return int(round(hours * HOUR * fs))


def drops(rng, hours=REGIME_H, fs=FS):
    n = _n(hours, fs)
    out = np.empty(n)
    i = 0
    while i < n:
        period = 1800.0 * rng.uniform(0.75, 1.25)
        rise = int(round((period - 60.0) * fs))
        fall = max(1, int(round(60.0 * fs)))
        seg = np.concatenate([np.linspace(0.0, 1.0, rise, endpoint=False),
                              np.linspace(1.0, 0.0, fall, endpoint=False)])
        take = min(len(seg), n - i)
        out[i:i + take] = seg[:take]
        i += take
    return out - 0.5 + 0.05 * rng.standard_normal(n)


def ar1(rng, n, tau_s=60.0, sd=0.25, fs=FS):
    phi = float(np.exp(-1.0 / (tau_s * fs)))
    e = rng.standard_normal(n) * sd * np.sqrt(1.0 - phi ** 2)
    out = np.empty(n)
    out[0] = rng.standard_normal() * sd
    for i in range(1, n):
        out[i] = phi * out[i - 1] + e[i]
    return out


def quiet(rng, hours=REGIME_H, fs=FS):
    return ar1(rng, _n(hours, fs), tau_s=60.0, sd=0.25, fs=fs)


def wave(rng, hours=REGIME_H, fs=FS):
    n = _n(hours, fs)
    t = np.arange(n) / fs
    period = 1200.0 * (1.0 + 0.1 * np.sin(2 * np.pi * t / (hours * HOUR / 3.0) + rng.uniform(0, 2 * np.pi)))
    phase = 2 * np.pi * np.cumsum(1.0 / (period * fs))
    return 0.7 * np.sin(phase + rng.uniform(0, 2 * np.pi)) + 0.05 * rng.standard_normal(n)


def spikes(rng, hours=REGIME_H, fs=FS):
    """A quiet AR(1) baseline (sd 0.1) with a brief spike — a 2-minute bump of
    height 1 — every ~12 min (±30 %)."""
    n = _n(hours, fs)
    out = ar1(rng, n, tau_s=60.0, sd=0.1, fs=fs)
    t = np.arange(n) / fs
    at = rng.uniform(0, 720.0)
    while at < t[-1]:
        out += np.exp(-0.5 * ((t - at) / 30.0) ** 2)
        at += 720.0 * rng.uniform(0.7, 1.3)
    return out


MAKERS = {"drops": drops, "quiet": quiet, "wave": wave, "spikes": spikes}


def drift(n, fs=FS, amplitude=3.0, ramp=2.0, period_h=20.0):
    t = np.arange(n) / fs
    return amplitude * np.sin(2 * np.pi * t / (period_h * HOUR)) + ramp * t / t[-1]


def three_regimes(seed=0, with_drift=True, fs=FS, order=ORDER, hours=REGIME_H):
    """`(x, truth)`: x the recording, truth the regime (0 drops, 1 quiet, 2
    wave) of every 1-hour piece."""
    rng = np.random.default_rng(seed)
    parts = [MAKERS[name](rng, hours, fs) for name in order]
    x = np.concatenate(parts)
    if with_drift:
        x = x + drift(len(x), fs)
    truth = np.repeat([LABEL_OF[name] for name in order], hours)
    return x, truth


def ar1_null(seed=0, hours=48, tau_s=60.0, fs=FS):
    rng = np.random.default_rng(seed)
    return ar1(rng, _n(hours, fs), tau_s=tau_s, sd=1.0, fs=fs)


def random_walk_null(seed=0, hours=48, fs=FS):
    rng = np.random.default_rng(seed)
    w = np.cumsum(rng.standard_normal(_n(hours, fs)))
    t = np.arange(len(w))
    return w - np.polyval(np.polyfit(t, w, 1), t)


def pink_null(seed=0, hours=48, fs=FS):
    rng = np.random.default_rng(seed)
    n = _n(hours, fs)
    f = np.fft.rfftfreq(n)
    spec = rng.standard_normal(len(f)) + 1j * rng.standard_normal(len(f))
    spec[1:] /= np.sqrt(f[1:])
    spec[0] = 0.0
    return np.fft.irfft(spec, n)


def agreement(labels, truth):
    """Best agreement of window labels (1..k) with the truth (0..2) over every
    one-to-one matching of labels to regimes (labels <= 0 count as wrong)."""
    from itertools import permutations
    labels = np.asarray(labels)
    truth = np.asarray(truth)
    ks = sorted(set(int(v) for v in labels if v > 0))
    best = 0.0
    regimes = sorted(set(int(v) for v in truth))
    for perm in permutations(regimes, min(len(ks), len(regimes))):
        mapping = dict(zip(ks, perm))
        hit = np.array([mapping.get(int(lab), -99) == tr for lab, tr in zip(labels, truth)])
        best = max(best, float(hit.mean()))
    return best
