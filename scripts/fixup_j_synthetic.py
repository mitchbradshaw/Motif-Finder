"""
fixup_j_synthetic.py
====================
A synthetic fungal recording with a KNOWN set of events, for fixup-J: the
reference fixture the authors' MATLAB is run on, and the trace the
detection-rate figure counts against.

Shapes follow the paper's own description (Dehshibi & Adamatzky 2021,
Fig. 1d): a depolarisation ramp, a repolarisation that overshoots the base
level, and a slow refractory return; amplitudes 0.5-6 mV, lengths in the
hundreds of seconds, on a slowly drifting base potential with the
sample-to-sample noise measured on M2 (0.025 mV MAD, fixup-b).

Dev tooling; nothing in the app imports it.
"""
from __future__ import annotations

import numpy as np

NOISE_V = 0.025e-3 * 1.4826          # MAD -> sigma


def spike_shape(length: int, amp_v: float, polarity: int = 1) -> np.ndarray:
    """One event, `length` samples: rise over a fifth, fall past the base over
    a fifth, exponential refractory return over the rest."""
    dep = max(2, length // 5)
    rep = max(2, length // 5)
    ref = max(2, length - dep - rep)
    y = np.concatenate([
        np.linspace(0.0, 1.0, dep, endpoint=False),
        np.linspace(1.0, -0.25, rep, endpoint=False),
        -0.25 * np.exp(-4.0 * np.linspace(0.0, 1.0, ref)),
    ])[:length]
    return polarity * amp_v * y


def synthetic_recording(n: int = 3000, n_events: int = 6, seed: int = 0, fs: float = 1.0):
    """Returns `(x_volts, events)`; `events` is a list of dicts with `start`,
    `end` (half-open, samples), `amp_mv`, `polarity`. Events never overlap."""
    rng = np.random.default_rng(seed)
    t = np.arange(n) / fs
    dur = n / fs
    base = (-0.110
            + 1.5e-3 * np.sin(2 * np.pi * t / (1.7 * dur) + rng.uniform(0, 6.28))
            + 0.6e-3 * np.sin(2 * np.pi * t / (0.45 * dur) + rng.uniform(0, 6.28)))
    walk = np.cumsum(rng.normal(0.0, 2.0e-6, n))
    x = base + walk + rng.normal(0.0, NOISE_V, n)
    slot = n // n_events
    events = []
    for k in range(n_events):
        length = int(rng.integers(int(150 * fs), int(min(420 * fs, 0.8 * slot))))
        start = k * slot + int(rng.integers(int(0.05 * slot), max(int(0.05 * slot) + 1, slot - length - int(0.05 * slot))))
        amp_mv = float(rng.uniform(0.6, 5.0))
        pol = 1 if rng.random() < 0.75 else -1
        x[start:start + length] += spike_shape(length, amp_mv * 1e-3, pol)
        events.append({"start": int(start), "end": int(start + length), "amp_mv": round(amp_mv, 3), "polarity": pol})
    return x, events


if __name__ == "__main__":
    import json
    import sys
    from scipy.io import savemat
    out = sys.argv[1]
    cases = {"a": dict(n=3000, n_events=6, seed=0), "b": dict(n=3000, n_events=4, seed=7),
             "c": dict(n=4200, n_events=8, seed=3)}
    meta = {}
    for name, kw in cases.items():
        x, ev = synthetic_recording(**kw)
        savemat(f"{out}/sig_{name}.mat", {"x": x.reshape(-1, 1)})
        meta[name] = {"kwargs": kw, "events": ev}
    # a pulse train for the slicing check: three clear low/high states
    rng = np.random.default_rng(1)
    p = np.concatenate([np.full(800, 0.0), np.full(600, 1.0), np.full(900, 0.0), np.full(500, 1.0),
                        np.full(700, 0.0), np.full(400, 1.0), np.full(600, 0.0)]) + rng.normal(0, 0.02, 4500)
    savemat(f"{out}/sig_pulse.mat", {"x": p.reshape(-1, 1)})
    json.dump(meta, open(f"{out}/cases.json", "w"), indent=1)
    print({k: len(v["events"]) for k, v in meta.items()})
