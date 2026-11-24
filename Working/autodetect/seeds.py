"""
seeds.py
========
The seed bank — one medoid per shape family of the accepted catalogue — searched over one channel.

In plain words
--------------
A seed is a "find me more like this" example, and a family's medoid is its most typical member. Each medoid is
searched at the family's typical durations (the 25th, 50th and 75th percentile of its members' durations), because
a search only finds stretches of the seed's own length and a family's members vary in length. A stretch counts as a
match when it resembles the medoid at least as closely as 90 % of the family's own members do (``min_corr``): tight
families get a strict line, loose ones a looser line, and no surrogate is needed (the researcher's choice,
2026-11-19, Q7 (a)). Matching compares shapes after scaling each stretch to the same size, so a tiny wiggle can pass
for a deep drop: a match smaller than the dataset's noise floor is dropped.

The distance
------------
The search is the seed-match block's own (`Adapters.detection_seed_matches.match_exemplar`, stumpy's FFT match with
the block's exclusion zone). Its z-normalised Euclidean distance over ``L`` samples is ``d = sqrt(2 L (1 - r))``,
``r`` the Pearson correlation, so "at least as close as the family's members" is a correlation line that holds at
any length: ``max_distance = sqrt(2 L (1 - min_corr))``. Matches of one family at different durations that overlap
are reduced to the best (`reduce_overlaps`, policy ``lowest``, on the length-free distance ``sqrt(2 (1 - r))``).
Matches of different families stay apart here; `candidates` merges them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from Adapters.detection_seed_matches import DEFAULT_EXCLUSION, match_exemplar, reduce_overlaps

#: The source name every seed match carries (one source for the blend, however many families match).
SOURCE = "seed"
#: A variant name is ``seed__<family label>``, so `candidate_events.family_of` maps every one to ``seed``.
VARIANT_PREFIX = SOURCE + "__"
#: At most this many matches per family and duration (stumpy's own ``max_matches``); a capped search is reported.
MAX_MATCHES = 1000
#: A seed shorter than this many samples at the channel's rate is not searched (too few points to be a shape).
MIN_LENGTH = 10
#: A family proposes matches only when its own members are alike: 90 % of them correlate with the medoid at least
#: this well (its ``min_corr``). Added 2026-11-19 after the first reference run: with every family searched, the
#: loose families (members r 0.69-0.93 with their medoid) matched ordinary drift — 48,165 matches on 528 h of
#: M2_aug CH7_B2 (91 an hour), reaching all 27 rejected spans there — while the 17 families at or above 0.95 gave
#: 1,754 (3.3 an hour) reaching 186 of the 212 accepted events and 4 of the 27 rejected. A loose family is reported,
#: not searched. None turns the gate off.
MIN_FAMILY_LINE = 0.95


@dataclass(frozen=True)
class SeedFamily:
    """One family's seed."""
    label: str
    exemplar_mv: np.ndarray = field(repr=False)
    exemplar_fs: float
    durations_s: tuple
    min_corr: float
    n_members: int = 0
    provenance: dict = field(default_factory=dict)

    @property
    def exemplar_duration_s(self):
        return len(self.exemplar_mv) / float(self.exemplar_fs)


def to_length(x, n):
    """``x`` at ``n`` points: bin means when shrinking (as the 2 Hz copies were made, block means of the 10 Hz
    samples), linear interpolation when stretching."""
    x = np.asarray(x, dtype=float).ravel()
    m = len(x)
    n = int(n)
    if m == n:
        return x.copy()
    if m > n:
        edges = np.round(np.linspace(0, m, n + 1)).astype(np.int64)
        return np.add.reduceat(x, edges[:-1]) / np.diff(edges)
    return np.interp(np.linspace(0, m - 1, n), np.arange(m), x)


def correlation(a, b):
    """Pearson correlation of two equal-length arrays (NaN when either is flat)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    sa, sb = a.std(), b.std()
    if sa == 0 or sb == 0:
        return float("nan")
    return float(np.mean((a - a.mean()) * (b - b.mean())) / (sa * sb))


def depth_mv(x_mv, start, end, fs):
    """The span's range after a 1-second moving average (the Library analysis's measure), mV."""
    seg = np.asarray(x_mv[int(start):int(end)], dtype=float)
    seg = seg[np.isfinite(seg)]
    k = max(1, int(round(float(fs))))
    if len(seg) > k:
        seg = np.convolve(seg, np.ones(k) / k, mode="valid")
    return float(np.ptp(seg)) if len(seg) else float("nan")


def search(x_mv, fs, families, *, floor_mv, max_matches=MAX_MATCHES, min_length=MIN_LENGTH,
           exclusion=DEFAULT_EXCLUSION, min_family_line=MIN_FAMILY_LINE):
    """Every family's matches over ``x_mv`` (millivolts, sampled at ``fs``).

    Returns ``(matches, report)``: one row per kept match (``start``, ``end`` relative to ``x_mv``, ``variant``,
    ``source``, ``family``, ``corr``, ``duration_s``, ``depth_mv``), and per family what was searched, how many
    matches the line let through, how many the noise floor removed, and whether a duration hit ``max_matches``.
    A family whose own line is below ``min_family_line`` is reported (``skipped``) and not searched.
    """
    x = np.asarray(x_mv, dtype=float)
    n = len(x)
    rows, report = [], []
    for fam in families:
        if min_family_line is not None and float(fam.min_corr) < float(min_family_line):
            report.append({"family": fam.label, "n_members": fam.n_members, "min_corr": float(fam.min_corr),
                           "lengths": [], "capped_lengths": [], "matches_before_floor": 0, "below_floor": 0,
                           "kept": 0, "skipped": f"members too unlike their medoid (line r {fam.min_corr:.3f} "
                                                 f"< {min_family_line:g})"})
            continue
        fam_rows, searched, capped = [], [], []
        for d in fam.durations_s:
            L = int(round(float(d) * float(fs)))
            if L < int(min_length) or L > n or L in searched:   # a family whose quartiles coincide searches once
                continue
            q = to_length(fam.exemplar_mv, L)
            if not np.all(np.isfinite(q)) or np.ptp(q) == 0:
                continue
            md = math.sqrt(2.0 * L * max(0.0, 1.0 - float(fam.min_corr)))
            found = match_exemplar(x, q, k=int(max_matches), max_distance=md, exclusion=exclusion)
            searched.append(L)
            if len(found) >= int(max_matches):
                capped.append(L)
            for dist, idx in found:
                r = 1.0 - float(dist) ** 2 / (2.0 * L)
                fam_rows.append({"index": int(idx), "length": L, "distance": math.sqrt(max(0.0, 2.0 * (1.0 - r))),
                                 "corr": r, "duration_s": float(d)})
        kept = reduce_overlaps(fam_rows, "lowest") if fam_rows else []
        below = 0
        for r in kept:
            s, e = r["index"], r["index"] + r["length"]
            dep = depth_mv(x, s, e, fs)
            if not np.isfinite(dep) or dep < float(floor_mv):
                below += 1
                continue
            rows.append({"start": s, "end": e, "variant": VARIANT_PREFIX + fam.label, "source": SOURCE,
                         "family": fam.label, "corr": r["corr"], "duration_s": r["duration_s"], "depth_mv": dep})
        report.append({"family": fam.label, "n_members": fam.n_members, "min_corr": float(fam.min_corr),
                       "lengths": searched, "capped_lengths": capped, "matches_before_floor": len(kept),
                       "below_floor": below, "kept": len(kept) - below, "skipped": None})
    cols = ["start", "end", "variant", "source", "family", "corr", "duration_s", "depth_mv"]
    out = pd.DataFrame(rows, columns=cols)
    if len(out):
        out = out.sort_values(["start", "end", "variant"]).reset_index(drop=True)
    return out, report
