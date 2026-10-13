"""
impulses.py
============
The extent rule of `detection.impulse_events`: one event per impulse in an
impulse-like score (the deconvolved jumps of `detection.deconvolve`, and any
future energy operator or derivative), computed from the block's own inputs
only — never a parameter the researcher must keep equal in two blocks.

    impulse      a sample whose score exceeds `threshold`; impulses closer than
                 `merge_within_s` are ONE event (a fall spread over a few
                 samples deconvolves into a few adjacent jumps)
    onset_idx    the last sample before the event's first impulse — the level
                 the event departs from (the jump happens between it and the next)
    extent       from `pre_s` before the onset to the next event's onset or
                 `max_extent_s` after the onset, whichever is first, clipped to
                 the span; `right_capped` says the cap set the end. Consecutive
                 spans overlap by `pre_s` (the next one starts `pre_s` before
                 the next onset, which is where this one ends)
    trough_idx   the sample of largest |x - x[onset]| from the onset to the end
                 of the extent (the deepest point of a drop, the top of a spike)
    size         the sum of the scores from the first to the last impulse of the
                 event (sub-threshold jumps between them included): the whole
                 jump, in the score's units

Why not `detection.threshold` (BLOCK_INTEGRATION.md §8): it emits the runs
where the score exceeds the cut, and an impulse score exceeds it for one sample
— a one-sample span with no recovery in it. This block gives each impulse the
event that follows it. Its run-merging is not `tidy_spans` either: that joins
SPANS by the gap between them, this groups IMPULSE SAMPLES and then sets the
extent from the next group, so the helpers do not fit.

All indices are span-relative (index 0 = the span's first sample), like a
SpanSet's starts. No UI imports.
"""

from dataclasses import dataclass, field
from typing import List

import numpy as np


@dataclass
class ImpulseEvents:
    starts: tuple
    ends: tuple
    sizes: tuple
    events: List[dict] = field(default_factory=list)
    n_impulse_samples: int = 0          # samples above the cut, before merging


def impulse_events(scores, x, fs, threshold=4.0, merge_within_s=2.0, pre_s=10.0, max_extent_s=600.0):
    sc = np.asarray(scores, dtype=float).ravel()
    xs = np.asarray(x, dtype=float).ravel()
    n = sc.size
    if xs.size != n:
        raise ValueError(f"detection.impulse_events: the score must have one value per sample of the signal "
                         f"({n} scores for {xs.size} samples).")
    fs = float(fs)
    merge = int(round(float(merge_within_s) * fs))
    pre = int(round(float(pre_s) * fs))
    cap = max(1, int(round(float(max_extent_s) * fs)))

    with np.errstate(invalid="ignore"):
        above = np.flatnonzero(sc > float(threshold))     # NaN compares False: never an impulse
    if above.size == 0:
        return ImpulseEvents(starts=(), ends=(), sizes=(), events=[], n_impulse_samples=0)

    breaks = np.flatnonzero(np.diff(above) >= max(merge, 1)) + 1
    groups = np.split(above, breaks)
    firsts = [int(g[0]) for g in groups]
    lasts = [int(g[-1]) for g in groups]
    onsets = [max(f - 1, 0) for f in firsts]

    starts, ends, sizes, events = [], [], [], []
    for k, (first, last, onset) in enumerate(zip(firsts, lasts, onsets)):
        block = sc[first:last + 1]
        size = float(np.nansum(block))
        nxt = onsets[k + 1] if k + 1 < len(onsets) else n
        cap_end = onset + cap
        end = min(nxt, cap_end, n)
        end = max(end, onset + 1)
        start = max(onset - pre, 0)
        right_capped = bool(cap_end < min(nxt, n))
        seg = xs[onset:end]
        ref = xs[onset]
        if np.isfinite(ref) and np.isfinite(seg).any():
            trough = onset + int(np.nanargmax(np.abs(seg - ref)))
        else:
            trough = onset
        starts.append(int(start))
        ends.append(int(end))
        sizes.append(size)
        events.append({
            "onset_idx": int(onset), "trough_idx": int(trough),
            "impulse_idx": int(first), "last_impulse_idx": int(last),
            "n_impulses": int(np.count_nonzero(np.nan_to_num(block) > 0)),
            "size": size, "start_idx": int(start), "end_idx": int(end),
            "left_capped": False, "right_capped": right_capped,
        })
    return ImpulseEvents(starts=tuple(starts), ends=tuple(ends), sizes=tuple(sizes), events=events,
                         n_impulse_samples=int(above.size))
