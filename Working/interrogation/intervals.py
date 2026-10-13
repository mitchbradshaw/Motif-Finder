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

The local measures LV (Shinomoto, Shima & Tanji 2003) and CV2 (Holt et al.
1996) compare each gap only with the next, so a slow change of rate does not
read as irregularity the way CV does (W1-G). Four things a reader should know:

- **Coincident onsets.** A neighbouring pair of two 0-s gaps (three events at
  the same instant) has a 0/0 ratio. Such pairs are left out, and n-1 in
  Shinomoto's 3/(n-1) is then the number of KEPT pairs; each group reports
  `n_local_pairs` and its `local_note` says how many pairs were dropped.
- **Duplicate onsets.** One duplicated onset in an otherwise regular train
  (gaps 30, 30, 0, 30, 30, 30) gives LV 1.20 and CV2 0.80 - it reads as random.
  A surprising LV or CV2 is worth checking for duplicate onsets upstream.
- **Few gaps.** Both are very noisy on short runs (Poisson sd of LV: 0.89 at 2
  gaps, 0.59 at 4, 0.37 at 9; Shinomoto used fragments of >= 100 gaps). With
  fewer than ~10 gaps, read them as indicative only, beside `n_intervals`.
- **Sampling quantisation.** Onsets on a 1 Hz grid jitter short gaps: a strictly
  periodic 2.5 s train rounded to whole seconds reads CV2 0.20 (0.016 at a
  30.5 s period). For gaps of a few samples, a small LV/CV2 is grid noise.

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


#: LV and CV2 compare neighbouring gaps, so they need at least this many gaps
#: (three events). Fewer is "not measured", never 0.
MIN_LOCAL_INTERVALS = 2


def _local_ratios(intervals):
    """`(ratios, n_dropped)`: `|I_i - I_{i+1}| / (I_i + I_{i+1})` for every
    neighbouring pair whose sum is positive, and how many pairs were left out
    because both gaps were 0 s (0/0). `ratios` is None when fewer than
    `MIN_LOCAL_INTERVALS` gaps, or when every pair was dropped.
    """
    iv = np.asarray(intervals, dtype=float).ravel()
    iv = iv[np.isfinite(iv)]
    if iv.size < MIN_LOCAL_INTERVALS:
        return None, 0
    a, b = iv[:-1], iv[1:]
    sm = a + b
    keep = sm > 0
    n_dropped = int((~keep).sum())
    if not keep.any():
        return None, n_dropped
    return np.abs(a[keep] - b[keep]) / sm[keep], n_dropped


def local_variation(intervals):
    """LV (Shinomoto, Shima & Tanji 2003; Shinomoto et al. 2009 eq. 2):
    3/(n-1) * sum_{i=1}^{n-1} ((I_i - I_{i+1}) / (I_i + I_{i+1}))^2, n gaps,
    where n-1 is the number of KEPT pairs (pairs of two 0-s gaps are left out;
    see the module docstring).

    0 for clockwork, 1 for a Poisson train, and - because each gap is compared
    only with the next - blind to a slow change of rate that inflates CV.
    None below two gaps. LvR (the 2009 refractory-corrected form) is not
    offered: its constant R = 5 ms was fitted to cortical neurons.
    """
    r, _ = _local_ratios(intervals)
    return None if r is None else float(3.0 * np.mean(r * r))


def local_cv2(intervals):
    """CV2 (Holt, Softky, Koch & Douglas 1996, J. Neurophysiol. 75:1806):
    mean over the kept pairs of 2|I_{i+1} - I_i| / (I_{i+1} + I_i). 0 for
    clockwork, 1 for Poisson; local in the same sense as LV. None below two
    gaps."""
    r, _ = _local_ratios(intervals)
    return None if r is None else float(2.0 * np.mean(r))


def _local_summary(iv, n_events):
    """`{lv, cv2, n_local_pairs, local_note}` for one group's finite gaps."""
    r, n_dropped = _local_ratios(iv)
    n_kept = 0 if r is None else int(r.size)
    if iv.size < MIN_LOCAL_INTERVALS:
        note = "{} events · LV and CV2 need at least {} events ({} gaps), not measured".format(
            n_events, MIN_LOCAL_INTERVALS + 1, MIN_LOCAL_INTERVALS)
    elif r is None:
        note = ("{} events · all {} neighbouring pairs of gaps are two 0-s gaps (coincident onsets), "
                "LV and CV2 undefined".format(n_events, n_dropped))
    elif n_dropped:
        note = ("{} of {} neighbouring pairs left out: both gaps 0 s (coincident onsets); LV and CV2 are over "
                "the {} kept pairs".format(n_dropped, n_dropped + n_kept, n_kept))
    else:
        note = None
    if r is None:
        return {"lv": None, "cv2": None, "n_local_pairs": n_kept, "local_note": note}
    return {"lv": float(3.0 * np.mean(r * r)), "cv2": float(2.0 * np.mean(r)), "n_local_pairs": n_kept,
            "local_note": note}


def _num(v):
    v = float(v)
    return v if np.isfinite(v) else None


def interval_statistics(intervals, n_events=None):
    """One group's interval summary as plain JSON: counts, median / mean / range,
    the regularity gate, and the local measures LV and CV2 with the number of
    neighbouring pairs they used (`n_local_pairs`; `local_note` says why they
    are None, or how many pairs were left out). Undefined values are None, never inf or
    NaN."""
    iv = np.asarray(intervals, dtype=float).ravel()
    iv = iv[np.isfinite(iv)]
    n_events = int(iv.size + 1 if n_events is None else n_events)
    if iv.size == 0:
        return {"n_events": n_events, "n_intervals": 0, "median_s": None, "mean_s": None, "min_s": None,
                "max_s": None, "cv": None, "r2_trend": None, "drift_ratio": None,
                **_local_summary(iv, n_events)}
    cv, r2 = regularity(iv)
    return {"n_events": n_events, "n_intervals": int(iv.size), "median_s": _num(np.median(iv)),
            "mean_s": _num(iv.mean()), "min_s": _num(iv.min()), "max_s": _num(iv.max()),
            "cv": _num(cv), "r2_trend": _num(r2) if iv.size >= 2 else None, "drift_ratio": _num(drift_ratio(iv)),
            **_local_summary(iv, n_events)}


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
    {"name": "lv", "rule": "local variation, 3/(n-1) · Σ ((I_i - I_i+1)/(I_i + I_i+1))² over the n gaps (Shinomoto, "
                           "Shima & Tanji 2003): each gap compared only with the next, so a slow change of rate does "
                           "not read as irregular the way CV does; 0 = clockwork, 1 = random (Poisson); needs 3 events, "
                           "else not measured (never 0); pairs of two 0-s gaps (coincident onsets) are left out and "
                           "n-1 is then the number of kept pairs (n_local_pairs; local_note counts the dropped); "
                           "with fewer than ~10 gaps read it as indicative only (Poisson sd 0.6 at 4 gaps); a "
                           "surprising value is worth checking for duplicate onsets upstream; the refractory-corrected LvR is not used (its constant was "
                           "fitted to cortex)"},
    {"name": "cv2", "rule": "local CV2, the mean of 2|I_i+1 - I_i|/(I_i+1 + I_i) over neighbouring gaps (Holt, "
                            "Softky, Koch & Douglas 1996); local like LV; 0 = clockwork, 1 = random (Poisson); needs "
                            "3 events, else not measured (never 0); pairs of two 0-s gaps are left out and the mean is "
                            "over the kept pairs; with fewer than ~10 gaps read it as indicative only; gaps of a few "
                            "samples are inflated by the sampling grid (a 2.5 s period on 1 Hz onsets reads 0.20)"},
]


#: Below this many events a rank correlation is not a test of anything.
MIN_TREND_N = 3


def kendall_trend(times, values):
    """Kendall's tau between when events happened and a measure of them.

    `{"tau", "p", "n", "note"}`: the rank correlation and its two-sided p, over
    the events whose measure is finite. Fewer than `MIN_TREND_N` such events, or
    a measure that never varies, has no tau - `tau` and `p` are None and `note`
    says why, because "no trend" and "not testable" are different results.
    """
    from scipy.stats import kendalltau

    t = np.asarray(times, dtype=float)
    v = np.asarray(values, dtype=float)
    keep = np.isfinite(t) & np.isfinite(v)
    t, v = t[keep], v[keep]
    n = int(len(t))
    if n < MIN_TREND_N:
        return {"tau": None, "p": None, "n": n, "note": "n {} · fewer than {} measured events, not tested".format(n, MIN_TREND_N)}
    if np.ptp(v) == 0 or np.ptp(t) == 0:
        return {"tau": None, "p": None, "n": n, "note": "n {} · the measure does not vary, no rank to correlate".format(n)}
    tau, p = kendalltau(t, v)
    return {"tau": _num(tau), "p": _num(p), "n": n, "note": None}
