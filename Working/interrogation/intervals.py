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


# ── B1 (round B): LV and CV2 against two nulls ──────────────────────────────

#: Draws per null (B1, "about 1,000"). Enough for a 2.5-97.5 % band and a p
#: down to about 0.002; a caller may ask for more or fewer.
NULL_DRAWS = 1000
#: The default seed, so the same group always gets the same null.
NULL_SEED = 2003
#: Elements per vectorised chunk of draws (memory bound: draws x events).
_NULL_CHUNK = 2_000_000
#: Below this many gaps the caveat says "indicative only" (module docstring).
FEW_GAPS = 10


def _local_rows(iv):
    """Row-wise LV and CV2 of a `(draws, gaps)` array, by `_local_ratios`' rule:
    a pair of two 0-s gaps is left out, and a row with no kept pair is NaN."""
    a, b = iv[:, :-1], iv[:, 1:]
    sm = a + b
    keep = sm > 0
    r = np.where(keep, np.abs(a - b) / np.where(keep, sm, 1.0), 0.0)
    n = keep.sum(axis=1).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        lv = np.where(n > 0, 3.0 * (r * r).sum(axis=1) / n, np.nan)
        cv2 = np.where(n > 0, 2.0 * r.sum(axis=1) / n, np.nan)
    return lv, cv2


def _null_summary(observed, draws):
    """`{observed, null_mean, lo, hi, p, n_used}`: the null's mean and 2.5-97.5 %
    band, and the two-sided p = 2 min(P(null <= obs), P(null >= obs)) with the
    +1 correction (a p of exactly 0 is never reported), capped at 1."""
    d = np.asarray(draws, dtype=float)
    d = d[np.isfinite(d)]
    if observed is None or d.size == 0:
        return {"observed": observed, "null_mean": None, "lo": None, "hi": None, "p": None, "n_used": int(d.size)}
    tol = 1e-12 * max(1.0, abs(observed))
    below = int((d <= observed + tol).sum())
    above = int((d >= observed - tol).sum())
    p = min(1.0, 2.0 * (1 + min(below, above)) / (d.size + 1))
    lo, hi = np.percentile(d, [2.5, 97.5])
    return {"observed": float(observed), "null_mean": float(d.mean()), "lo": float(lo), "hi": float(hi),
            "p": float(p), "n_used": int(d.size)}


def _null_block(observed, sample_rows, n_draws, rng, n_cols):
    """Draw `n_draws` null rows of gaps in chunks, and summarise LV and CV2."""
    lvs, cv2s = [], []
    per = max(1, _NULL_CHUNK // max(1, n_cols))
    left = n_draws
    first = None
    while left > 0:
        k = min(per, left)
        rows = sample_rows(k, rng)
        if first is None:
            first = rows[0]
        lv, cv2 = _local_rows(rows)
        lvs.append(lv)
        cv2s.append(cv2)
        left -= k
    lv = np.concatenate(lvs) if lvs else np.array([])
    cv2 = np.concatenate(cv2s) if cv2s else np.array([])
    return {"n_draws": int(n_draws), "lv": _null_summary(observed["lv"], lv),
            "cv2": _null_summary(observed["cv2"], cv2)}, first


def interval_nulls(onsets, n_draws=NULL_DRAWS, seed=NULL_SEED, resolution_s=None, keep_draws=False):
    """LV and CV2 of ONE group's onsets against two nulls (round-B B1).

    In plain words, an LV or CV2 means little on its own; it means something
    beside what the same number of events would have given by chance. So two
    references, each drawn `n_draws` times (seeded with `seed`):

    * **Rate-matched Poisson** - the same number of onsets dropped uniformly at
      random over the group's own observed span (first onset to last): a
      homogeneous Poisson process conditioned on n. It asks: *is the timing more
      regular, or burstier, than random?* Both measures are about 1 for it; an
      observed value below the band is more regular than random, above it
      burstier. With `resolution_s` (the onsets' sampling step) the drawn onsets
      are put on the same grid, so the null carries the same sampling
      quantisation as the observed ones (module docstring).
    * **Shuffled intervals** - the group's own gaps, in random order. The gap
      distribution is kept exactly; only the order is lost. It asks: *is the
      order of the gaps more regular than the gap distribution alone implies?*
      An LV below the band means neighbouring gaps are more alike than chance
      (slow drifts of rate, runs of similar gaps); above it, long and short gaps
      alternate.

    Each null reports, for `lv` and `cv2`: `observed`, `null_mean`, the 2.5-97.5 %
    band `lo`..`hi`, a two-sided `p` (+1 corrected) and `n_used` (draws with a
    defined value). The module's rules carry over unchanged: per group only (the
    caller passes one group's onsets); a pair of two 0-s gaps is left out of the
    observed value AND of every draw (`n_local_pairs`, `local_note` are the
    observed value's); fewer than 3 events is not measured - every measure None,
    `note` saying why; with fewer than `FEW_GAPS` gaps, or gaps of a few grid
    steps, `caveat` says the comparison is indicative only.

    `keep_draws` adds the first draw of each null (`draws_onsets` /
    `draws_intervals`) for a test to inspect; never sent to a page.
    """
    t = np.sort(np.asarray(onsets, dtype=float).ravel())
    t = t[np.isfinite(t)]
    iv = np.diff(t)
    n_events = int(t.size)
    obs = _local_summary(iv, n_events)
    n_draws = int(n_draws)
    res = None if resolution_s is None else float(resolution_s)
    caveats = []
    if 0 < iv.size < FEW_GAPS:
        caveats.append(f"{iv.size} gaps: fewer than {FEW_GAPS}, so LV, CV2 and their nulls are indicative only")
    if res and iv.size and float(np.median(iv)) < 5 * res:
        caveats.append(f"median gap {float(np.median(iv)):.3g} s is under five sampling steps ({res:.3g} s): "
                       "LV and CV2 carry grid noise (the Poisson null is drawn on the same grid)")
    out = {"n_events": n_events, "n_intervals": int(iv.size), "seed": int(seed), "resolution_s": res,
           "n_local_pairs": obs["n_local_pairs"], "local_note": obs["local_note"],
           "caveat": "; ".join(caveats) or None}
    if obs["lv"] is None or n_draws <= 0:
        why = obs["local_note"] or "no draws asked for"
        empty = {"n_draws": max(0, n_draws), "lv": None, "cv2": None, "note": why}
        out.update({"poisson": dict(empty), "shuffle": dict(empty)})
        return out

    rng = np.random.default_rng(int(seed))
    t0, t1 = float(t[0]), float(t[-1])

    kept = {}

    def poisson_rows(k, g):
        u = g.uniform(t0, t1, size=(k, n_events))
        if res:
            u = t0 + np.round((u - t0) / res) * res
        u.sort(axis=1)
        kept.setdefault("onsets", u[0].copy())
        return np.diff(u, axis=1)

    def shuffle_rows(k, g):
        return g.permuted(np.broadcast_to(iv, (k, iv.size)), axis=1)

    pois, p_first = _null_block(obs, poisson_rows, n_draws, rng, n_events)
    shuf, s_first = _null_block(obs, shuffle_rows, n_draws, rng, iv.size)
    pois["note"] = ("{} onsets uniform over the observed span {:.6g} s to {:.6g} s{}".format(
        n_events, t0, t1, f", on a {res:.3g} s grid" if res else ""))
    shuf["note"] = f"the group's own {iv.size} gaps in random order"
    if keep_draws:
        pois["draws_onsets"] = kept["onsets"].tolist()
        pois["draws_intervals"] = p_first.tolist()
        shuf["draws_intervals"] = s_first.tolist()
    out.update({"poisson": pois, "shuffle": shuf})
    return out


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
    {"name": "null_poisson", "rule": "rate-matched Poisson null (round-B B1): the group's number of onsets drawn "
                                     "uniformly over its own observed span (first to last onset), on the onsets' "
                                     "sampling grid, 1,000 seeded draws by default; asks whether the timing is more "
                                     "regular (below the band) or burstier (above it) than random; both measures are "
                                     "about 1 for it; mean, 2.5-97.5 % band and two-sided p (+1 corrected) per group"},
    {"name": "null_shuffle", "rule": "shuffled-interval null (round-B B1): the group's own gaps in seeded random "
                                     "order, the gap distribution kept exactly; asks whether the ORDER of the gaps is "
                                     "more regular than the gap distribution alone implies (LV below the band: "
                                     "neighbouring gaps more alike than chance; above: long and short alternate); "
                                     "0-s pairs are left out of every draw as of the observed value"},
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


def write_group_columns(upstream, keys):
    """The `group` column a feature block writes so Intervals downstream times events
    within its new keys (trains, families), without losing an upstream group: with an
    upstream `group` the new key is `<upstream>/<key>` and the original is kept as
    `group_upstream` (an interval is only meaningful inside one group, so the upstream
    split must survive). `upstream` is the SpanSet's feature table (or None); `keys` one
    per event. Returns the columns to add: `{"group": [...]}` (+ `"group_upstream"`).
    Shared by `interrogation.trains` and `interrogation.event_families`."""
    keys = [str(k) for k in keys]
    if upstream is None or "group" not in upstream.columns:
        return {"group": keys}
    up = upstream["group"]
    return {"group": [f"{g}/{k}" for g, k in zip(up.astype(str), keys)], "group_upstream": up.to_numpy()}
