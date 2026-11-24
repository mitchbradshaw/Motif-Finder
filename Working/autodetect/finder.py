"""
finder.py
=========
Proposals from the researcher's own definition of an event (2026-11-23), for the small events no detector proposed:
the CH14 trains of 0.2-0.35 mV sawtooth drops (falling over 9-13 samples at 2 Hz) and of 0.2 mV spikes (in the run on
the inverted signal, where they are falls).

    a SHARP fall     its 1-second step (on the 1-second moving average, as `gates.sharpness` reads it) at least
                     `gates.MIN_RISE_SHARPNESS` times the channel's 1-second step noise
    a STEADY fall    at least `gates.MIN_STEADY_SAMPLES` samples each lower than the last, falling at least the noise
                     floor, to a bottom `gates.MIN_SIGNIFICANCE` times the fine noise below the points either side

Each place found gives a box (the fall, plus `PAD_S` each side; overlapping boxes merged) for the Library's whole drop
to redraw and the gates to judge like any other proposal. The source's precision in the blend is 0: it proposes and
never vouches, so a candidate it alone found keeps R4's score.

No plotting library - CLAUDE.md rule 1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from Working.autodetect import gates

SOURCE = "event_rule"
#: Seconds added each side of a fall found.
PAD_S = 2.0


def _runs(mask):
    """``(starts, ends)`` of the True runs of ``mask`` (``ends`` exclusive)."""
    m = np.r_[False, np.asarray(mask, dtype=bool), False].astype(np.int8)
    d = np.diff(m)
    return np.flatnonzero(d == 1), np.flatnonzero(d == -1)


def _merge(starts, ends):
    if not len(starts):
        return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64)
    order = np.argsort(starts, kind="stable")
    s, e = np.asarray(starts)[order], np.asarray(ends)[order]
    out_s, out_e = [int(s[0])], [int(e[0])]
    for a, b in zip(s[1:], e[1:]):
        if a <= out_e[-1]:
            out_e[-1] = max(out_e[-1], int(b))
        else:
            out_s.append(int(a))
            out_e.append(int(b))
    return np.asarray(out_s, dtype=np.int64), np.asarray(out_e, dtype=np.int64)


def find(x_mv, fs, *, floor_mv, noise=None, steady=True, min_sharpness=gates.MIN_RISE_SHARPNESS,
         min_steady=gates.MIN_STEADY_SAMPLES, min_significance=gates.MIN_SIGNIFICANCE):
    """Boxes round every sharp fall of ``x_mv`` (millivolts, sampled at ``fs``) and - when ``steady`` - every steady,
    significant one: a frame of proposals (``start``, ``end``, ``variant``, ``source``, ``score``) in the shape the
    pipeline's detectors give. ``noise`` is the channel's 1-second step noise (`gates.step_noise`, read when None)."""
    x = np.asarray(x_mv, dtype=float)
    n = len(x)
    noise = gates.step_noise(x, fs) if noise is None else float(noise)
    k = max(1, int(round(float(fs))))
    pad = max(1, int(round(PAD_S * float(fs))))
    starts, ends = [], []
    if n > k + 1 and np.isfinite(noise) and noise > 0:
        mv = np.convolve(x, np.ones(k) / k, mode="same") if k > 1 else x
        step = mv[k:] - mv[:-k]
        with np.errstate(invalid="ignore"):
            s1, e1 = _runs(step <= -float(min_sharpness) * noise)
        starts += list(np.maximum(0, s1 - pad))
        ends += list(np.minimum(n, e1 + k + pad))
    if steady and n > 2:
        with np.errstate(invalid="ignore"):
            s2, e2 = _runs(np.diff(x) < 0)             # e2 - s2 falling steps: a run of e2 - s2 + 1 samples
        keep = (e2 - s2 + 1) >= int(min_steady)
        for a, b in zip(s2[keep], e2[keep]):
            if not (x[a] - x[b] >= float(floor_mv)):
                continue
            if gates.significance(x, a, b, b, fs, falling=True) < float(min_significance):
                continue
            starts.append(max(0, a - pad))
            ends.append(min(n, b + 1 + pad))
    s, e = _merge(starts, ends)
    return pd.DataFrame({"start": s, "end": e, "variant": SOURCE, "source": SOURCE, "score": np.nan})
