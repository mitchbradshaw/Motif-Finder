"""
intervals.py
=============
Inter-event intervals, and the statistics that say whether a run of events is
a train. THE one implementation: before fixup-d there were three
(`Pipelines/drop_motifs/store11.py::interval_stats`,
`Pipelines/drop_motifs/clusterk1.py::isi_by_channel`, and the Interrogation
aggregate route), each differencing its own sorted onsets; all three now call
`inter_event_intervals`. `sequences11`'s regularity gate moved here too, and
`sequences11` imports it back under its old names.

The rule that is not negotiable (store11.py `group_key`, carried over):
**inter-event intervals are only meaningful inside one group**, and the three
species' intervals differ by two orders of magnitude, so nothing about timing
may be pooled before it has been measured per group. Every function here takes
one group's onsets; a caller with several groups calls it once per group.

No plotting library - CLAUDE.md rule 1.
"""

import numpy as np


def inter_event_intervals(onsets):
    """Successive differences of the SORTED onsets, in the onsets' own unit.

    Sorted first: a store written channel-major is onset-ascending within a
    channel, but an unsorted input would otherwise produce negative intervals
    rather than an error, and a sort costs nothing.
    """
    a = np.sort(np.asarray(onsets, dtype=float).ravel())
    return np.diff(a)


def regularity(intervals):
    """`(cv, r2)` for one run's intervals (moved from `sequences11._regularity`).

    CV uses the sample standard deviation (ddof=1): these are samples of a
    process, not a population, and on a five-event run - four intervals -
    the difference between the two definitions is 15%, which is large
    enough to move runs across a 0.5 threshold.
    """
    intervals = np.asarray(intervals, dtype=float)
    mean = float(intervals.mean()) if intervals.size else 0.0
    if intervals.size < 2 or mean <= 0:
        return float("inf"), 0.0
    cv = float(intervals.std(ddof=1) / mean)
    if float(intervals.std()) == 0.0:
        # A perfectly constant gap has no trend to fit, and R-squared of a
        # flat line is undefined rather than 1. CV already qualifies it.
        return cv, 0.0
    index = np.arange(intervals.size, dtype=float)
    r = float(np.corrcoef(index, intervals)[0, 1])
    return cv, float(r * r)


def drift_ratio(intervals):
    """Last third's mean interval over the first third's (moved from
    `sequences11._drift`).

    1.0 is no drift, above 1 is widening, below 1 is tightening. Thirds
    rather than first-against-last interval because a single interval is
    noise and a third is a measurement.
    """
    intervals = np.asarray(intervals, dtype=float)
    if intervals.size < 2:
        return float("nan")
    third = max(1, intervals.size // 3)
    head = float(intervals[:third].mean())
    tail = float(intervals[-third:].mean())
    return tail / head if head > 0 else float("nan")


def _num(v):
    v = float(v)
    return v if np.isfinite(v) else None


def interval_statistics(intervals, n_events=None):
    """One group's interval summary as plain JSON: counts, median / mean / range,
    and the regularity gate. Undefined values are None, never inf or NaN."""
    iv = np.asarray(intervals, dtype=float).ravel()
    iv = iv[np.isfinite(iv)]
    n_events = int(iv.size + 1 if n_events is None else n_events)
    if iv.size == 0:
        return {"n_events": n_events, "n_intervals": 0, "median_s": None, "mean_s": None, "min_s": None,
                "max_s": None, "cv": None, "r2_trend": None, "drift_ratio": None}
    cv, r2 = regularity(iv)
    return {"n_events": n_events, "n_intervals": int(iv.size), "median_s": _num(np.median(iv)),
            "mean_s": _num(iv.mean()), "min_s": _num(iv.min()), "max_s": _num(iv.max()),
            "cv": _num(cv), "r2_trend": _num(r2) if iv.size >= 2 else None, "drift_ratio": _num(drift_ratio(iv))}


RULES = [
    {"name": "interval", "rule": "onset-to-onset time between successive events, measured per group and never "
                                 "pooled across groups (store11.group_key: the three species' intervals differ by two "
                                 "orders of magnitude); interval_before_s is from the previous event in the group, "
                                 "interval_after_s to the next; the first / last is NaN"},
    {"name": "anchor", "rule": "the event's onset (an upstream onset_idx column, e.g. from Event shape) when present, "
                               "else the span start"},
    {"name": "cv", "rule": "sample standard deviation (ddof=1) / mean of the group's intervals (sequences11)"},
    {"name": "r2_trend", "rule": "R² of interval against event index; 0 for a perfectly constant gap (sequences11)"},
    {"name": "drift_ratio", "rule": "mean of the last third of intervals / mean of the first third; 1 = no drift (sequences11)"},
]
