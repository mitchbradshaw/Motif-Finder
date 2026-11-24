"""
scan.py
=======
R4's own search: sliding windows over the channel, and the rule that keeps only the best of overlapping hits.

In plain words: R4 is a judge, not a searcher, so to let it find events nobody proposed we cut the channel into
overlapping windows at a few durations (2, 6, 10 and 30 minutes, the researcher's choice 2026-11-19) and ask it
about each one. A window becomes a candidate only if R4 gives it at least ``MIN_P`` (more likely than not) and no
overlapping window, at any duration, scores higher — like keeping only the summit of each hill.

Windows step by a quarter of their length (``STRIDE_FRAC``). Two windows overlap when their common stretch is at
least half of the shorter of the two (``Working.discovery.candidate_events.AGREE_SHARE``, the rule detector
agreement uses), so a 2-minute hit inside a 30-minute hit is the same place.
"""

from __future__ import annotations

import numpy as np

from Working.discovery.candidate_events import AGREE_SHARE

#: The window durations, seconds (2026-11-19: 30 s dropped; 2, 6, 10 and 30 min kept).
DURATIONS_S = (120.0, 360.0, 600.0, 1800.0)
#: Each window starts this fraction of its length after the previous one.
STRIDE_FRAC = 0.25
#: A window must score at least this to become a candidate (Q13 (a)).
MIN_P = 0.5


def windows(n, fs, durations_s=DURATIONS_S, stride_frac=STRIDE_FRAC):
    """Every window over ``n`` samples: ``(starts, ends, duration_s)`` arrays. A duration longer than the signal
    is skipped; the last window of each duration ends at or before ``n``."""
    starts, ends, dur = [], [], []
    for d in durations_s:
        L = int(round(float(d) * float(fs)))
        if L < 2 or L > n:
            continue
        step = max(1, int(round(L * float(stride_frac))))
        s = np.arange(0, n - L + 1, step, dtype=np.int64)
        starts.append(s)
        ends.append(s + L)
        dur.append(np.full(len(s), float(d)))
    if not starts:
        z = np.zeros(0, dtype=np.int64)
        return z, z.copy(), np.zeros(0)
    return np.concatenate(starts), np.concatenate(ends), np.concatenate(dur)


def overlaps(a_start, a_end, b_start, b_end, share=AGREE_SHARE):
    """Do two spans share at least ``share`` of the shorter one?"""
    inter = min(a_end, b_end) - max(a_start, b_start)
    shorter = max(1, min(a_end - a_start, b_end - b_start))
    return inter > 0 and inter >= share * shorter


def peaks(starts, ends, p, *, min_p=MIN_P, share=AGREE_SHARE):
    """Indices of the windows kept: score at least ``min_p``, best first, each one not overlapping (``share`` of the
    shorter) any window kept before it. Ties break on the earlier start, then the shorter window."""
    starts = np.asarray(starts, dtype=np.int64)
    ends = np.asarray(ends, dtype=np.int64)
    p = np.asarray(p, dtype=float)
    ok = np.flatnonzero(np.isfinite(p) & (p >= float(min_p)))
    order = ok[np.lexsort((ends[ok] - starts[ok], starts[ok], -p[ok]))]
    kept = []
    # kept spans sorted by start, for a bounded neighbour check
    k_starts, k_ends, k_idx = [], [], []
    longest = 0
    for i in order:
        s, e = int(starts[i]), int(ends[i])
        lo = np.searchsorted(k_starts, s - longest, side="left")
        hi = np.searchsorted(k_starts, e, side="left")
        if any(overlaps(s, e, k_starts[j], k_ends[j], share) for j in range(lo, hi)):
            continue
        pos = int(np.searchsorted(k_starts, s, side="left"))
        k_starts.insert(pos, s)
        k_ends.insert(pos, e)
        k_idx.insert(pos, int(i))
        longest = max(longest, e - s)
        kept.append(int(i))
    return np.asarray(sorted(kept, key=lambda j: (starts[j], ends[j])), dtype=np.int64)
