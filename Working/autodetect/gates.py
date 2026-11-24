"""
gates.py
========
The tests a candidate must pass to be shown: it is not flat drift, it is not smaller than the noise floor, a rise is
sharp, and a drop can be told from noise (sharp, or steady and significant: `distinct`).

In plain words
--------------
**Flat drift.** Slow drift is a gentle curve: take away the best smooth curve (a cubic) and almost nothing is left. A
real drop or spike is not a gentle curve, so a big remainder is left. A candidate is kept when at least
`MIN_UNEXPLAINED` of its range is left over (the researcher's choice, 2026-11-23, Q2 (a)). Measured on the four
reference stretches' reviewed spans before the choice: at 0.15 it kept 99.5-100 % of accepted events and removed the
flat 30-minute window of the researcher's screenshot (0.035) and 30-53 % of rejected spans on M2_aug, CH15 and M4.
A sharpness test (the largest 1-second step over the noise) was measured too and lost 5-17 % of accepted events.

**The noise floor.** An event shallower than the dataset's noise floor (Settings > Datasets, the Library's own rule
for hiding members) is not shown; the seed matches already met it.
"""

from __future__ import annotations

import numpy as np

#: A candidate needs at least this share of its range left after removing the best cubic.
MIN_UNEXPLAINED = 0.15
#: The smooth curve's degree.
DEGREE = 3


def unexplained_fraction(x_mv, start, end, fs, *, degree=DEGREE):
    """Range of what the best ``degree`` polynomial leaves of ``x_mv[start:end]`` (after a 1-second moving average),
    as a fraction of that stretch's range. NaN when the stretch is too short to fit; 0 when it is flat."""
    seg = np.asarray(x_mv[max(0, int(start)):int(end)], dtype=float)
    seg = seg[np.isfinite(seg)]
    k = max(1, int(round(float(fs))))
    if k > 1 and len(seg) > 2 * k:
        seg = np.convolve(seg, np.ones(k) / k, mode="valid")
    if len(seg) < degree + 3:
        return float("nan")
    rng = float(np.ptp(seg))
    if rng <= 0:
        return 0.0
    t = np.linspace(-1.0, 1.0, len(seg))
    res = seg - np.polyval(np.polyfit(t, seg, degree), t)
    return float(np.ptp(res) / rng)


#: A rise must be SHARP (the researcher, 2026-11-23: "sharp rises only"): its steepest 1-second step at least this many
#: times the channel's 1-second step noise. A slow upward drift - a recovery, the rising stretch of the researcher's
#: CH15 306.7 h screenshot - is not a rise event.
MIN_RISE_SHARPNESS = 10.0


def step_noise(x_mv, fs):
    """The channel's robust noise of 1-second steps: MAD x 1.4826 of the differences of a 1-second moving average."""
    x = np.asarray(x_mv, dtype=float)
    x = x[np.isfinite(x)]
    k = max(1, int(round(float(fs))))
    if k > 1 and len(x) > 2 * k:
        x = np.convolve(x, np.ones(k) / k, mode="valid")[::k]
    d = np.diff(x)
    if d.size < 3:
        return float("nan")
    return float(1.4826 * np.median(np.abs(d - np.median(d))))


def sharpness(x_mv, onset, extremum, fs, noise):
    """The steepest 1-second step between ``onset`` and ``extremum`` (after a 1-second moving average), in units of
    ``noise`` (`step_noise`)."""
    a, b = int(onset), int(extremum)
    if b < a:
        a, b = b, a
    k = max(1, int(round(float(fs))))
    seg = np.asarray(x_mv[max(0, a - k):b + k + 1], dtype=float)
    seg = seg[np.isfinite(seg)]
    if len(seg) < 2 or not noise or not np.isfinite(noise) or noise <= 0:
        return float("nan")
    if k > 1 and len(seg) > k:
        seg = np.convolve(seg, np.ones(k) / k, mode="valid")
        steps = np.abs(seg[k:] - seg[:-k]) if len(seg) > k else np.abs(np.diff(seg))
    else:
        steps = np.abs(np.diff(seg))
    return float(steps.max() / noise) if len(steps) else float("nan")


#: A drop that is not sharp counts only when it falls STEADILY and SIGNIFICANTLY (the researcher, 2026-11-23: "a drop
#: over 5 samples minimum, and the samples ... consistently decreasing across all 5, and the drop distance ... a
#: significant depth greater than the rolling average of the surrounding points"): this many consecutive samples,
#: each lower than the last ...
MIN_STEADY_SAMPLES = 5
#: ... to a bottom at least this many times the fine noise below the average of the points either side - 6, the
#: whole-drop rule's own depth bar. Calibrated on the four reference stretches (2026-11-23): sharp-or-steady keeps
#: every accepted event at 4, 5, 6 and 8, and at 6 removes the researcher's four noise-scale screenshot cases (CH14
#: 470:57 and 479:04 h).
MIN_SIGNIFICANCE = 6.0
#: The points either side: this long before the top and after the event's end ...
SIDE_S = 10.0
#: ... and their fine noise: their robust spread about their own rolling average of this length (neighbouring
#: events in a train barely move it; a spread over the whole stretch would, and lost 60 accepted CH14 train events).
FINE_S = 2.0


def steady_run(x_mv, onset, extremum, *, falling=True):
    """The longest run of consecutive samples between ``onset`` and ``extremum``, each lower than the last
    (``falling``) or higher (a rise), counted in samples (a run of 5 has 4 steps)."""
    a, b = sorted((int(onset), int(extremum)))
    seg = np.asarray(x_mv[max(0, a):b + 1], dtype=float)
    if len(seg) < 2:
        return int(len(seg))
    d = np.diff(seg)
    ok = (d < 0) if falling else (d > 0)
    best = cur = 0
    for v in ok:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return int(best + 1)


def _movavg(p, m):
    if m < 2 or len(p) < m:
        return p
    pad = np.pad(p, (m // 2, m - 1 - m // 2), mode="edge")
    return np.convolve(pad, np.ones(m) / m, mode="valid")


def significance(x_mv, onset, extremum, end, fs, *, falling=True, side_s=SIDE_S, fine_s=FINE_S):
    """How far the event's bottom (a rise: its peak) lies beyond the average of the points either side - ``side_s``
    before ``onset`` and after ``end`` - in units of their fine noise (robust spread about their own ``fine_s``
    rolling average). NaN when there are no points either side."""
    x = np.asarray(x_mv, dtype=float)
    w = max(5, int(round(float(side_s) * float(fs))))
    m = max(2, int(round(float(fine_s) * float(fs))))
    o, e, n = int(onset), int(extremum), int(max(end, extremum))
    parts = [p[np.isfinite(p)] for p in (x[max(0, o - w):o + 1], x[n:n + w])]
    parts = [p for p in parts if len(p) >= 3]
    if not parts or not np.isfinite(x[e]):
        return float("nan")
    res = np.concatenate([p - _movavg(p, m) for p in parts])
    fine = 1.4826 * float(np.median(np.abs(res - np.median(res))))
    base = float(np.mean(np.concatenate(parts)))
    dist = (base - x[e]) if falling else (x[e] - base)
    return float(dist / max(fine, 1e-12))


def distinct(x_mv, fs, onset, extremum, end, sharp, *, falling=True, min_sharpness=MIN_RISE_SHARPNESS,
             min_steady=MIN_STEADY_SAMPLES, min_significance=MIN_SIGNIFICANCE):
    """Which events can be told from noise, by the researcher's rule for drops: SHARP (steepest 1-second step at least
    ``min_sharpness`` x the step noise, the sharp-rise bar - a 1.3 mV drop in 1.5 s is no noise), or STEADY
    (``min_steady`` samples each further than the last) to a bottom ``min_significance`` x the fine noise beyond the
    points either side. Arrays in (one value per event), a boolean mask out."""
    on, ex, en = (np.asarray(v, dtype=np.int64) for v in (onset, extremum, end))
    sh = np.asarray(sharp, dtype=float)
    out = np.zeros(len(on), dtype=bool)
    for k in range(len(on)):
        if sh[k] >= float(min_sharpness):
            out[k] = True
            continue
        if steady_run(x_mv, on[k], ex[k], falling=falling) < int(min_steady):
            continue
        out[k] = significance(x_mv, on[k], ex[k], en[k], fs, falling=falling) >= float(min_significance)
    return out


def flat_mask(x_mv, starts, ends, fs, *, min_unexplained=MIN_UNEXPLAINED, degree=DEGREE):
    """``(passes, fractions)`` for every box; a box too short to fit passes (it cannot be judged drift)."""
    fr = np.array([unexplained_fraction(x_mv, s, e, fs, degree=degree) for s, e in zip(starts, ends)], dtype=float)
    return (~(fr < float(min_unexplained))), fr
