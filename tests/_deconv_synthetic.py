"""
_deconv_synthetic.py
=====================
Synthetic troughs for the W1-B deconvolution tests (`test_oasis.py`,
`test_adapter_deconvolve.py`, `test_adapter_impulse_events.py`,
`test_template_deconvolved_troughs.py`). Not a test module.

A trough here is the shape OASIS models, upside down: an instant drop of depth
`a` at sample `onset`, then an exponential recovery with half-time `half_s`
(x = baseline - a * gamma ** (t - onset) for t >= onset). Stored in volts, the
way M2 is, so a test can also check that nothing assumes millivolts.
"""

import numpy as np

FS = 1.0
HALF_S = 120.0
N_12H = 12 * 3600
BASELINE_V = 0.010
NOISE_V = 1e-4                       # 0.1 mV; the troughs are 2-6 mV deep (20-60 noise SDs)


def gamma_for(half_s=HALF_S, fs=FS):
    return 2.0 ** (-1.0 / (half_s * fs))


def kernel_sum(n, onsets, depths, gamma):
    """sum_k depth_k * gamma ** (t - onset_k) for t >= onset_k: the troughs' depth below baseline."""
    t = np.arange(n, dtype=float)
    out = np.zeros(n)
    for o, a in zip(onsets, depths):
        tail = t[o:] - o
        out[o:] += a * gamma ** tail
    return out


def troughs_12h(seed=0, noise=NOISE_V, half_s=HALF_S, drift=0.0):
    """12 h at 1 Hz with 30 troughs: 14 alone and 8 overlapping PAIRS whose second
    trough starts 30-100 s after the first, i.e. before the first has half
    recovered (half-time 120 s). Returns (x, onsets, pairs) with `onsets` sorted
    sample indices of each drop's first low sample and `pairs` the 8 (first,
    second) onset pairs. `drift` adds a slow sinusoid of that amplitude (volts)."""
    rng = np.random.default_rng(seed)
    kinds = ["pair"] * 8 + ["single"] * 14
    rng.shuffle(kinds)
    onsets, depths, pairs = [], [], []
    t = 600
    for kind in kinds:
        onsets.append(t)
        depths.append(rng.uniform(2e-3, 6e-3))
        if kind == "pair":
            gap = int(rng.integers(30, 100))
            onsets.append(t + gap)
            depths.append(rng.uniform(2e-3, 6e-3))
            pairs.append((t, t + gap))
            t += gap
        t += int(rng.integers(1300, 1800))
    assert t < N_12H - 300, "the synthetic layout overran 12 h"
    assert len(onsets) == 30 and len(pairs) == 8
    x = BASELINE_V - kernel_sum(N_12H, onsets, depths, gamma_for(half_s))
    x = x + noise * rng.standard_normal(N_12H)
    if drift:
        tt = np.arange(N_12H, dtype=float)
        x = x + drift * np.sin(2 * np.pi * tt / (6 * 3600.0))
    return x, onsets, pairs


def ar1_noise(n, phi, sd, seed=0):
    """AR(1) noise x_t = phi x_{t-1} + e_t with a stationary SD of `sd`: slow, coloured
    background, each sample close to the last (phi 0.99 at 1 Hz: a ~70 s half-life)."""
    from scipy.signal import lfilter
    rng = np.random.default_rng(seed)
    e = rng.standard_normal(n) * sd * np.sqrt(1.0 - phi * phi)
    return lfilter([1.0], [1.0, -phi], e)


def pink_noise(n, sd, seed=0):
    """1/f noise (power ~ 1/f, random phases) scaled to an SD of `sd`."""
    rng = np.random.default_rng(seed)
    f = np.fft.rfftfreq(n)
    spec = rng.standard_normal(f.size) + 1j * rng.standard_normal(f.size)
    spec[1:] /= np.sqrt(f[1:])
    spec[0] = 0.0
    x = np.fft.irfft(spec, n)
    return x / np.std(x) * sd
