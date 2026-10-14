"""
_pan_synthetic.py
=================
Shared synthetic recordings for the pan-matrix-profile tests
(`test_pan_matrix_profile.py`, `test_adapter_pan_matrix_profile.py`,
`test_template_motif_lengths.py`), at 1 Hz unless a caller decimates.

- `planted`: an AR(1) phi 0.97 background (unit innovations, so its own
  spread is about 4.1) with a 90 s spike-like motif planted 12 times and a
  20 min slow motif (a sharkfin: a fall and an exponential recovery, with a
  ripple so it is not just a smooth curve) planted 6 times. Positions are
  returned so a test can look at the picture where the motifs are.
- the no-structure backgrounds the common rules ask for: `ar1` (phi 0.95-0.99),
  `random_walk` (cumulative white noise, a 1 h rolling mean removed — what the
  template's detrend leaves), `pink` (1/f spectrum), and `drift_sine` (AR(1)
  plus a slow sine, the "drift under the events" case).
"""

import numpy as np

FS = 1.0
SHORT_M = 90                 # the 90 s motif
LONG_M = 1200                # the 20 min motif
N_SHORT = 12
N_LONG = 6


def ar1(n, phi, seed=0):
    rng = np.random.default_rng(seed)
    e = rng.standard_normal(n)
    x = np.empty(n)
    x[0] = e[0] / np.sqrt(1.0 - phi * phi)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


def rolling_mean_removed(x, w):
    """x minus its centred rolling mean over `w` samples (edges: the mean of
    what the window holds)."""
    x = np.asarray(x, dtype=float)
    c = np.concatenate([[0.0], np.cumsum(x)])
    n = len(x)
    i = np.arange(n)
    lo = np.clip(i - w // 2, 0, n)
    hi = np.clip(i + w // 2 + 1, 0, n)
    return x - (c[hi] - c[lo]) / (hi - lo)


def random_walk(n, seed=0, detrend_w=3600):
    rng = np.random.default_rng(seed)
    return rolling_mean_removed(np.cumsum(rng.standard_normal(n)), detrend_w)


def pink(n, seed=0):
    rng = np.random.default_rng(seed)
    f = np.fft.rfftfreq(n)
    amp = np.zeros_like(f)
    amp[1:] = 1.0 / np.sqrt(f[1:])
    spec = amp * np.exp(1j * rng.uniform(0, 2 * np.pi, len(f)))
    x = np.fft.irfft(spec, n=n)
    return x / x.std()


def drift_sine(n, seed=0):
    t = np.arange(n, dtype=float)
    return ar1(n, 0.97, seed) + 8.0 * np.sin(2 * np.pi * t / (6 * 3600.0))


def short_motif():
    """90 s: a sharp spike up and a slower undershoot — a shape, not a bump."""
    t = np.arange(SHORT_M, dtype=float)
    return 30.0 * np.exp(-0.5 * ((t - 25) / 4.0) ** 2) - 15.0 * np.exp(-0.5 * ((t - 50) / 12.0) ** 2)


def long_motif():
    """20 min: a sudden fall, an exponential recovery and a ripple on it."""
    t = np.arange(LONG_M, dtype=float)
    fall = -60.0 * np.exp(-t / 300.0) * (t > 60)
    ripple = 30.0 * np.sin(2 * np.pi * t / 120.0) * np.exp(-t / 900.0)
    return fall + ripple


#: where the short motifs sit after the last long motif, in seconds from its
#: end — irregular, so a long window holding two of them does not repeat as a
#: periodic train would
_FREE_OFFSETS = (150, 800, 1650, 2050, 2900, 3500)


def planted(n=4 * 3600, seed=0, short_amp=1.0):
    """Returns (x, short_starts, long_starts).

    Layout: the six long motifs from 3 % of the span, 200 s apart; one short
    motif before them, five centred in the gaps between them, six more at irregular offsets
    after the last one; the last half hour or so of a 4 h span holds neither,
    so a window of 20 min or more can be found that holds a short motif and
    no long one, and one that holds no motif at all. A span too short for the
    whole layout keeps what fits."""
    x = ar1(n, 0.97, seed)
    gap = 200
    first = int(0.03 * n)
    long_starts = [first + k * (LONG_M + gap) for k in range(N_LONG)]
    long_starts = [s for s in long_starts if s + LONG_M <= n]
    lm = long_motif()
    for s in long_starts:
        x[s:s + LONG_M] += lm
    before = [max(0, first - SHORT_M - 150)]
    between = [s + LONG_M + (gap - SHORT_M) // 2 for s in long_starts[:-1]]
    after = long_starts[-1] + LONG_M
    free = [after + o for o in _FREE_OFFSETS]
    short_starts = [s for s in before + between + free if s + SHORT_M <= n][:N_SHORT]
    sm = short_amp * short_motif()
    for s in short_starts:
        x[s:s + SHORT_M] += sm
    return x, short_starts, long_starts


def no_structure(kind, n, seed=0):
    if kind == "ar95":
        return ar1(n, 0.95, seed)
    if kind == "ar97":
        return ar1(n, 0.97, seed)
    if kind == "ar99":
        return ar1(n, 0.99, seed)
    if kind == "random_walk":
        return random_walk(n, seed)
    if kind == "pink":
        return pink(n, seed)
    if kind == "drift_sine":
        return drift_sine(n, seed)
    raise ValueError(kind)


NO_STRUCTURE = ("ar95", "ar99", "random_walk", "pink", "drift_sine")


def spike_train(n, seed, amp_sd=3.0, width=60):
    """10-20 copies of a 60 s spike (a sharp peak and a slower undershoot) at
    irregular positions on a random walk; `amp_sd` x the spread the 2 h
    rolling-mean detrend leaves of the walk (the W3-C fix-round sweep's
    `rw_spikes_<amp>` case, same seeds)."""
    bg = np.cumsum(np.random.default_rng(seed).standard_normal(n))
    sd = np.std(rolling_mean_removed(bg, 7200))
    rng = np.random.default_rng(10_000 + seed)
    count = int(rng.integers(10, 21))
    t = np.arange(width, dtype=float)
    shape = np.exp(-0.5 * ((t - 12) / 3.0) ** 2) - 0.4 * np.exp(-0.5 * ((t - 30) / 8.0) ** 2)
    shape /= np.abs(shape).max()
    x = bg.copy()
    for p in np.sort(rng.choice(np.arange(200, n - 200, 300), size=count, replace=False)):
        x[p:p + width] += amp_sd * sd * shape
    return x
