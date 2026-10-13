"""
trains.py
==========
Trains (bursts, Adamatzky's "words") of events, by three rules over one
group's event times (w1-e). The core of `interrogation.trains`; no plotting
library (CLAUDE.md rule 1).

In plain words: if events come in trains, the gaps between them are of two
kinds - short gaps inside a train, long gaps between trains - and a smoothed
histogram of the gaps on a log scale has two humps. `logisi` finds the valley
between the humps and uses it as the cut; one hump means no trains, and it
says so. `maxinterval` uses five fixed thresholds instead, and `adamatzky`
uses theta = a multiple of the mean gap.

Sources
-------
* logISI - Pasquale, Martinoia & Chiappalone 2010, J Comput Neurosci
  29:213-229, AS RESTATED by Cotterill et al. 2016, J Neurophysiol
  116:306-321 (the 2010 full text was not reachable;
  docs/research/analysis-blocks-primary-sources.md section 8a): the largest
  peak of the log-ISI histogram at an ISI <= 100 ms is the intra-burst peak
  (none -> no bursts); among the minima after it, the first whose void
  parameter 1 - g(min)/sqrt(g(p1) g(p2)) EXCEEDS 0.7 sets maxISI; a burst is
  >= 3 spikes with ISIs < maxISI; if maxISI > 100 ms, cores are found with
  100 ms and extended by spikes within maxISI of their edges.
* MaxInterval - the NeuroExplorer method as benchmarked by Cotterill et al.
  2016 (their first choice): a burst begins at an ISI <= the begin threshold,
  continues while ISIs <= the end threshold; bursts closer than the minimum
  inter-burst interval are merged; bursts shorter than the minimum duration or
  with fewer than the minimum number of spikes are removed.
* Words - Adamatzky 2022, R Soc Open Sci 9:211926: consecutive spikes belong to
  one word while their gap is not more than theta, theta = a or 2a, a = the
  mean interspike interval.

Adaptations, each forced by our data (named here as 00-common.md asks)
---------------------------------------------------------------------
1. **A kernel density, not a binned histogram.** Fungal recordings give tens
   to hundreds of events, not the tens of thousands of spikes the 2010 binning
   was tuned on; the bins-per-decade and smoothing of the original are
   themselves unverified. The density is a Gaussian KDE on log10(gap) with
   Silverman's robust bandwidth, 0.9 * min(sd, IQR/1.349) * n^-1/5 (sd when
   the IQR is 0), evaluated on 512 points; the bandwidth is printed. Not
   Scott's (sd * n^-1/5): the sd of a two-humped sample is inflated by the
   very bimodality being looked for, so Scott's rule smoothed real valleys
   away (irregular trains at a between/within ratio of 100: 85 % of train
   events found at n=300, 19 % at n=60, against 99 % and 87 % with
   Silverman's). Not narrower either: 0.6x the robust rule called trains in
   11-18 % of drifting-rate Poisson series; at 0.9x the false-train rate is
   about 2 % or less on Poisson and on 100x rate ramps at n=30-300.
   **What it can resolve.** When the timing inside a train is irregular
   (exponential gaps), the gaps between trains must be roughly 30-100x those
   inside before a valley deep enough (void > 0.7) can exist at all - even the
   true mixture density's void is only 0.51 at a ratio of 10 and 0.72 at 30.
   Below that, "no trains" means "not resolvable", not "absent".
2. **The 100 ms ceiling becomes `max_core_gap_s`**, in seconds, and is
   optional. A neuronal ceiling is physiology; nobody knows a fungal one.
   Given one (> 0), the rule runs as written: the intra-train peak is the
   largest prominent peak at or below it.
3. **Without one (0 = auto) the prominent peaks are tried left to right.**
   Each peak, shortest gap first, is paired with every prominent peak after
   it; the first valley whose void exceeds 0.7 is the cut. The leftmost hump
   is the within-train one - what the 100 ms ceiling encoded for neurons -
   and trying the next pair when a valley is too shallow lets a ripple on
   the left of the density not hide a real valley further right. An earlier
   version bounded the search by the median gap; that failed twice: when
   fewer than half the gaps are within trains the median lands in the
   inter-train hump and the inter-train peak was taken for the intra-train
   one ("one hump" over plain trains), and on a flat-topped within-train
   hump with many events the density's top can sit above its own median.
4. **In auto mode there is no core-and-extend step.** The 2010 cores exist
   because 100 ms is a physiological upper bound on a within-burst gap;
   without one there is nothing to cut cores at. With an explicit
   `max_core_gap_s` the step is applied as written.
5. **No valley -> no trains.** Pasquale's method falls back to the 100 ms
   threshold when no cut is found; here the absence is the result, said in
   words (the prompt and the research plan both ask for it).
6. **Peaks must be prominent.** A density peak counts only if its prominence
   is at least `PEAK_PROMINENCE_FRAC` of the density's maximum: a tiny ripple
   in the tail of a single hump otherwise makes a "valley" whose void ratio
   exceeds 0.7 merely because the ripple is low (the void parameter divides
   by the ripple's own height).
7. **Fewer than `MIN_GAPS_FOR_HISTOGRAM` (10) gaps -> logISI refuses**, in
   words; a density of nine numbers has no valley worth believing.
"""

from __future__ import annotations

import numpy as np

RULE_NAMES = ("logisi", "maxinterval", "adamatzky")

#: Fewer gaps than this and the histogram rule refuses (W1-E acceptance).
MIN_GAPS_FOR_HISTOGRAM = 10
#: The void parameter must EXCEED this (Cotterill et al. 2016's restatement).
VOID_THRESHOLD = 0.7
#: Points the log-gap density is evaluated on (and drawn with).
DENSITY_POINTS = 512
#: A density peak's prominence must be at least this fraction of the maximum.
PEAK_PROMINENCE_FRAC = 0.05
#: A ~0.005 Hz cycle appeared on no-fungus control channels (Buffi et al. 2025).
ARTEFACT_PERIOD_S = 200.0
#: "near" 200 s: within this fraction of it either side.
ARTEFACT_TOLERANCE = 0.25

#: MaxInterval placeholders (seconds). The neuronal values Cotterill et al. used
#: (begin 0.17, end 0.3, min IBI 0.2, min duration 0.01, 3 spikes) are for
#: neurons; these are PLACEHOLDERS for 1 Hz fungal recordings until the trains
#: logISI finds supply fungal values.
MI_DEFAULTS = {"mi_begin_gap_s": 60.0, "mi_end_gap_s": 120.0, "mi_min_ibi_s": 180.0, "mi_min_duration_s": 0.0}


# ── the shared assembly: gaps -> runs -> trains ────────────────────────────

def _runs_below(gaps, cut, *, strict=True):
    """Index runs `(first_event, last_event)` of consecutive events joined by
    gaps below `cut` (strictly, or <= when `strict` is False). Every event
    appears in exactly one run (a run of one when neither neighbour joins)."""
    n = len(gaps) + 1
    runs, first = [], 0
    for i, g in enumerate(gaps):
        joined = (g < cut) if strict else (g <= cut)
        if not joined:
            runs.append((first, i))
            first = i + 1
    runs.append((first, n - 1))
    return runs


def _labels_from_runs(n, runs, min_events):
    """`train_id` per sorted event: runs of >= `min_events` numbered 0.. in
    time order; every other event -1."""
    labels = np.full(n, -1, dtype=int)
    k = 0
    for a, b in runs:
        if b - a + 1 >= min_events:
            labels[a:b + 1] = k
            k += 1
    return labels


# ── logISI ──────────────────────────────────────────────────────────────────

def silverman_bandwidth(lg):
    """Silverman's robust rule of thumb, 0.9 * min(sd, IQR/1.349) * n^-1/5,
    on `lg` (log10 gaps); the sd alone when the IQR is 0 (most gaps equal)."""
    lg = np.asarray(lg, dtype=float)
    sd = float(lg.std(ddof=1))
    q75, q25 = np.percentile(lg, [75, 25])
    spread = min(sd, (q75 - q25) / 1.349) if q75 > q25 else sd
    return 0.9 * spread * lg.size ** -0.2


def log_gap_density(gaps):
    """`(grid_log10, density, bandwidth_log10)` - a Gaussian KDE (Silverman's
    robust bandwidth, `silverman_bandwidth`) of log10 of the positive gaps, on
    `DENSITY_POINTS` points spanning the data +- 3 bandwidths. Gaps <= 0
    (simultaneous events) have no logarithm and are left out of the density
    (they still count as within any cut)."""
    from scipy.stats import gaussian_kde

    lg = np.log10(np.asarray(gaps, dtype=float)[np.asarray(gaps) > 0])
    if lg.size < 2 or np.ptp(lg) == 0:
        return None, None, None
    # a scalar bw_method is the factor on the sample sd
    kde = gaussian_kde(lg, bw_method=silverman_bandwidth(lg) / float(lg.std(ddof=1)))
    bw = float(np.sqrt(kde.covariance[0, 0]))
    grid = np.linspace(lg.min() - 3 * bw, lg.max() + 3 * bw, DENSITY_POINTS)
    return grid, kde(grid), bw


def _peaks(g, prominent=True):
    """Indices of the density's peaks: those whose prominence is at least
    `PEAK_PROMINENCE_FRAC` of the maximum when `prominent`, else every local
    maximum."""
    from scipy.signal import find_peaks

    idx, _ = find_peaks(g, prominence=PEAK_PROMINENCE_FRAC * float(g.max()) if prominent else None)
    return [int(i) for i in idx]


def logisi_cut(gaps, max_core_gap_s=0.0, void_threshold=VOID_THRESHOLD):
    """The logISI cut for one group's gaps (seconds).

    Returns a dict: `cut_s` (None when there is no valley), `void`, the
    intra-train peak `intra_peak_s`, the ceiling used `max_core_gap_s` (None
    in auto mode) and whether it was `auto`, the density (`log10_gap_s`,
    `density`, `bandwidth_log10`) and `reason` (why there is no cut, in
    words) - never an invented split.
    """
    gaps = np.asarray(gaps, dtype=float)
    auto = not (max_core_gap_s and max_core_gap_s > 0)
    ceiling = None if auto else float(max_core_gap_s)
    out = {"cut_s": None, "void": None, "intra_peak_s": None, "max_core_gap_s": ceiling, "auto": auto,
           "log10_gap_s": None, "density": None, "bandwidth_log10": None, "reason": None, "n_peaks": 0}
    grid, g, bw = log_gap_density(gaps)
    if grid is None:
        out["reason"] = "the gaps do not vary - one value has no histogram, so no valley"
        return out
    out.update(log10_gap_s=[round(float(v), 5) for v in grid], density=[float("%.5g" % v) for v in g],
               bandwidth_log10=bw)  # 5 figures: a drawing, not a re-analysis
    peaks = _peaks(g)
    out["n_peaks"] = len(peaks)
    if auto:
        candidates = sorted(peaks)   # left to right: the shortest-gap hump first
    else:
        below = [p for p in peaks if grid[p] <= np.log10(ceiling)]
        if not below:
            out["reason"] = (f"no peak of the log-gap density at or below the within-train ceiling ({ceiling:.4g} s): "
                             "one kind of gap, no trains")
            return out
        candidates = [max(below, key=lambda p: g[p])]   # as written: the largest peak at or below the ceiling
    if not candidates:   # no interior peak at all (cannot happen on a +- 3 bandwidth grid; said, not crashed)
        out["reason"] = "the log-gap density has no peak, so no valley to cut at - no trains"
        return out
    out["intra_peak_s"] = float(10 ** grid[candidates[0]])
    best_void = None
    for p1 in candidates:
        for p2 in (p for p in peaks if p > p1):
            m = p1 + int(np.argmin(g[p1:p2 + 1]))
            void = 1.0 - g[m] / np.sqrt(g[p1] * g[p2])
            best_void = void if best_void is None else max(best_void, void)
            if void > void_threshold:
                out.update(cut_s=float(10 ** grid[m]), void=float(void), intra_peak_s=float(10 ** grid[p1]))
                return out
    if best_void is None:   # no candidate has a prominent peak after it
        first = min(candidates)
        if any(p > first for p in _peaks(g, prominent=False)):
            out["reason"] = (f"no second peak prominent enough (>= {PEAK_PROMINENCE_FRAC * 100:g} % of the "
                             f"maximum): after the peak at {10 ** grid[first]:.4g} s the log-gap density has only "
                             "a minor bump, so no valley worth cutting at - no trains")
        else:
            out["reason"] = ("one hump: the log-gap density has no peak after the intra-train peak at "
                             f"{10 ** grid[first]:.4g} s, so no valley to cut at - no trains")
        return out
    out["void"] = float(best_void)
    out["reason"] = (f"the valleys after the intra-train peak are too shallow: the deepest has void "
                     f"{best_void:.3f}, which does not exceed {void_threshold:g} - no trains")
    return out


def core_and_extend(gaps, ceiling, cut, min_events):
    """Pasquale 2010 as restated: cores = runs of >= `min_events` events with
    gaps < `ceiling`; each core grows over neighbours whose gap is < `cut`.
    Cores whose extensions meet become one train."""
    n = len(gaps) + 1
    member = np.zeros(n, dtype=bool)
    for a, b in _runs_below(gaps, ceiling):
        if b - a + 1 >= min_events:
            member[a:b + 1] = True
    # extend: an event joins when the gap to a member neighbour is < cut
    changed = True
    while changed:
        changed = False
        for i, gp in enumerate(gaps):
            if gp < cut and member[i] != member[i + 1]:
                member[i] = member[i + 1] = True
                changed = True
    labels = np.full(n, -1, dtype=int)
    k, i = 0, 0
    while i < n:
        if member[i]:
            j = i
            while j + 1 < n and member[j + 1] and gaps[j] < cut:
                j += 1
            labels[i:j + 1] = k
            k += 1
            i = j + 1
        else:
            i += 1
    return labels


def logisi_trains(gaps, *, min_events=3, max_core_gap_s=0.0, void_threshold=VOID_THRESHOLD):
    """`(labels, info)` for one group by logISI; `labels` per sorted event."""
    gaps = np.asarray(gaps, dtype=float)
    n = gaps.size + 1
    if gaps.size < MIN_GAPS_FOR_HISTOGRAM:
        info = {"cut_s": None, "void": None, "intra_peak_s": None, "max_core_gap_s": None, "auto": None,
                "log10_gap_s": None, "density": None, "bandwidth_log10": None, "n_peaks": 0,
                "reason": f"only {gaps.size} gap{'s' if gaps.size != 1 else ''} between events: the log-gap "
                          f"histogram needs at least {MIN_GAPS_FOR_HISTOGRAM}, so logISI refuses - no trains called"}
        return np.full(n, -1, dtype=int), info
    info = logisi_cut(gaps, max_core_gap_s=max_core_gap_s, void_threshold=void_threshold)
    if info["cut_s"] is None:
        return np.full(n, -1, dtype=int), info
    cut = info["cut_s"]
    if not info["auto"] and cut > info["max_core_gap_s"]:
        info["core_and_extend"] = True
        return core_and_extend(gaps, info["max_core_gap_s"], cut, min_events), info
    info["core_and_extend"] = False
    return _labels_from_runs(n, _runs_below(gaps, cut), min_events), info


# ── MaxInterval ─────────────────────────────────────────────────────────────

def maxinterval_trains(times_s, *, begin_gap_s, end_gap_s, min_ibi_s, min_duration_s, min_events=3):
    """`(labels, info)` for one group's SORTED times by MaxInterval.

    1. a burst begins at the first gap <= `begin_gap_s` (the two events either
       side are its first two) and continues while gaps are <= `end_gap_s`;
    2. consecutive bursts whose inter-burst interval (first event of the next
       minus last event of this one) is < `min_ibi_s` merge, with the events
       between them;
    3. a burst lasting < `min_duration_s` (last minus first event) or holding
       < `min_events` events is removed.
    """
    t = np.asarray(times_s, dtype=float)
    n = t.size
    gaps = np.diff(t)
    bursts, i = [], 0
    while i < n - 1:
        if gaps[i] <= begin_gap_s:
            j = i + 1
            while j < n - 1 and gaps[j] <= end_gap_s:
                j += 1
            bursts.append([i, j])
            i = j + 1
        else:
            i += 1
    merged = []
    for b in bursts:
        if merged and t[b[0]] - t[merged[-1][1]] < min_ibi_s:
            merged[-1][1] = b[1]
        else:
            merged.append(list(b))
    kept = [(a, b) for a, b in merged if (b - a + 1) >= min_events and (t[b] - t[a]) >= min_duration_s]
    labels = np.full(n, -1, dtype=int)
    for k, (a, b) in enumerate(kept):
        labels[a:b + 1] = k
    info = {"n_bursts_found": len(bursts), "n_after_merge": len(merged), "n_removed": len(merged) - len(kept),
            "reason": None if kept else "no run of gaps met the five thresholds - no trains"}
    return labels, info


# ── Adamatzky's words ───────────────────────────────────────────────────────

def adamatzky_words(gaps, *, theta_mult=1.0, min_events=3):
    """`(word_ids, labels, info)`: every event's word (words of one event
    allowed) and the train label of words of >= `min_events` events.
    Consecutive events share a word while their gap is <= theta =
    `theta_mult` x the mean gap."""
    gaps = np.asarray(gaps, dtype=float)
    n = gaps.size + 1
    theta = float(theta_mult * gaps.mean()) if gaps.size else None
    runs = _runs_below(gaps, theta, strict=False) if gaps.size else [(0, n - 1)]
    word_ids = np.empty(n, dtype=int)
    for k, (a, b) in enumerate(runs):
        word_ids[a:b + 1] = k
    labels = _labels_from_runs(n, runs, min_events)
    lengths = [b - a + 1 for a, b in runs]
    info = {"theta_s": theta, "mean_gap_s": float(gaps.mean()) if gaps.size else None,
            "word_lengths": lengths, "n_words": len(runs),
            "reason": None if gaps.size else "a single event has no gap, so theta is undefined"}
    return word_ids, labels, info


# ── summaries ───────────────────────────────────────────────────────────────

def lempel_ziv(sizes):
    """Kaspar-Schuster LZ76 over a sequence of train sizes (one symbol per
    train, its size), normalised by n / log2(n) - the routine and
    normalisation of `dehshibi_detection_analysis._lz76_complexity`, imported,
    not rewritten. None for fewer than two trains."""
    if len(sizes) < 2:
        return None
    # The private routine, not the public `compute_lempel_ziv_complexity`: that one takes spike regions and a
    # signal length and builds a BINARY string from them; a sequence of train sizes is a string over many
    # symbols, which only the underlying LZ76 routine accepts.
    from Working.Detection.analysis.dehshibi_detection_analysis import _lz76_complexity

    return float(_lz76_complexity("".join(chr(0x100 + int(s)) for s in sizes)))


def size_distribution(sizes):
    """`{str(size): count}` in ascending size, JSON-safe."""
    vals, counts = np.unique(np.asarray(sizes, dtype=int), return_counts=True)
    return {str(int(v)): int(c) for v, c in zip(vals, counts)}


def artefact_warning(within_gaps_s):
    """The Buffi et al. 2025 caution, when the typical within-train gap is
    near 200 s; else None."""
    w = np.asarray(within_gaps_s, dtype=float)
    w = w[np.isfinite(w)]
    if w.size == 0:
        return None
    med = float(np.median(w))
    if abs(med - ARTEFACT_PERIOD_S) <= ARTEFACT_TOLERANCE * ARTEFACT_PERIOD_S:
        return (f"the typical gap inside a train is {med:.0f} s - close to the ~200 s (0.005 Hz) cycle that "
                "appeared on no-fungus control channels (Buffi et al. 2025). Check another channel before "
                "believing these trains")
    return None


def find_trains(times_s, rule="logisi", *, min_events=3, max_core_gap_s=0.0, void_threshold=VOID_THRESHOLD,
                theta_mult=1.0, mi_begin_gap_s=MI_DEFAULTS["mi_begin_gap_s"],
                mi_end_gap_s=MI_DEFAULTS["mi_end_gap_s"], mi_min_ibi_s=MI_DEFAULTS["mi_min_ibi_s"],
                mi_min_duration_s=MI_DEFAULTS["mi_min_duration_s"]):
    """Trains among ONE group's event times (seconds, any order).

    Returns a dict, every per-event array aligned with the INPUT order:
    `train_id` (-1 = in no train; trains numbered 0.. in time order),
    `train_size` (0 when in no train), `position_in_train` (-1 when in none),
    `word_id` (adamatzky only, else None), plus the summary: `rule`, `cut_s`,
    `void`, the density, `n_trains`, `fraction_in_trains`,
    `train_size_distribution`, `lz_complexity`, `refused` (words, or None),
    `warnings`.
    """
    if rule not in RULE_NAMES:
        raise ValueError(f"unknown train rule {rule!r}; choose one of {list(RULE_NAMES)}")
    t = np.asarray(times_s, dtype=float).ravel()
    order = np.argsort(t, kind="stable")
    ts = t[order]
    n = ts.size
    gaps = np.diff(ts)
    word_sorted = None
    info = {}
    if n == 0:
        labels = np.zeros(0, dtype=int)
        info = {"reason": "no events"}
    elif rule == "logisi":
        labels, info = logisi_trains(gaps, min_events=min_events, max_core_gap_s=max_core_gap_s,
                                     void_threshold=void_threshold)
    elif rule == "maxinterval":
        labels, info = maxinterval_trains(ts, begin_gap_s=mi_begin_gap_s, end_gap_s=mi_end_gap_s,
                                          min_ibi_s=mi_min_ibi_s, min_duration_s=mi_min_duration_s,
                                          min_events=min_events)
    else:
        word_sorted, labels, info = adamatzky_words(gaps, theta_mult=theta_mult, min_events=min_events)

    # trains are contiguous runs of the sorted events, numbered 0.. in time order: one pass, no scan per train
    size_s = np.zeros(n, dtype=int)
    pos_s = np.full(n, -1, dtype=int)
    member = labels >= 0
    counts = np.bincount(labels[member]) if member.any() else np.zeros(0, dtype=int)
    sizes = [int(c) for c in counts]
    first_of = np.concatenate([[0], np.cumsum(counts)[:-1]]).astype(int)
    size_s[member] = counts[labels[member]]
    pos_s[member] = np.arange(int(member.sum())) - first_of[labels[member]]
    within = gaps[member[1:] & (labels[1:] == labels[:-1])].tolist() if n > 1 else []

    def unsort(a):
        out = np.empty_like(a)
        out[order] = a
        return out

    warnings = []
    w = artefact_warning(within)
    if w:
        warnings.append(w)
    refused = info.get("reason") if (rule == "logisi" and gaps.size < MIN_GAPS_FOR_HISTOGRAM) else None
    n_in = int((labels >= 0).sum())
    result = {
        "rule": rule, "n_events": int(n), "n_gaps": int(gaps.size),
        "train_id": unsort(labels), "train_size": unsort(size_s), "position_in_train": unsort(pos_s),
        "word_id": unsort(word_sorted) if word_sorted is not None else None,
        "n_trains": len(sizes), "n_in_trains": n_in, "fraction_in_trains": (n_in / n) if n else None,
        "train_size_distribution": size_distribution(sizes),
        "train_sizes": sizes,
        "lz_complexity": lempel_ziv(sizes) if rule != "adamatzky" else None,   # adamatzky: per word, below
        "median_within_gap_s": float(np.median(within)) if within else None,
        "refused": refused, "no_trains_reason": None if sizes else (info.get("reason") or "no run reached "
                                                                     f"{min_events} events"),
        "warnings": warnings,
        "cut_s": info.get("cut_s"), "void": info.get("void"), "intra_peak_s": info.get("intra_peak_s"),
        "max_core_gap_s": info.get("max_core_gap_s"), "core_and_extend": info.get("core_and_extend"),
        "density": ({"log10_gap_s": info["log10_gap_s"], "density": info["density"],
                     "bandwidth_log10": info["bandwidth_log10"]} if info.get("log10_gap_s") else None),
    }
    if rule == "adamatzky":
        result.update(theta_s=info.get("theta_s"), mean_gap_s=info.get("mean_gap_s"),
                      word_length_distribution=size_distribution(info.get("word_lengths") or []),
                      n_words=info.get("n_words"),
                      lz_complexity=lempel_ziv(info.get("word_lengths") or []))
    if rule == "maxinterval":
        result.update(thresholds_s={"begin_gap": mi_begin_gap_s, "end_gap": mi_end_gap_s, "min_ibi": mi_min_ibi_s,
                                    "min_duration": mi_min_duration_s, "min_events": min_events})
    return result


def rules(rule, **p):
    """`[{name, rule}]` - the rule behind every number this block reports."""
    common = [
        {"name": "event time", "rule": "the event's onset (an upstream onset_idx column, e.g. from Event shape) "
                                       "when present, else the span start - interrogation.intervals' anchor"},
        {"name": "gap_before_s", "rule": "onset-to-onset time from the previous event in the same group "
                                         "(interrogation.intervals' measure, imported); NaN for the first"},
        {"name": "train_id", "rule": "trains numbered 0.. in time order within the block's output; -1 = in no train. "
                                     "Trains never cross an upstream group (gaps are only meaningful inside one)"},
        {"name": "train_size", "rule": "events in the event's train; 0 when it is in none"},
        {"name": "position_in_train", "rule": "0-based order of the event in its train; -1 when in none"},
        {"name": "lz_complexity", "rule": "Kaspar-Schuster LZ76 phrase count over the sequence of train sizes in "
                                          "time order (one symbol per train; Adamatzky's rule: per word, every "
                                          "word), normalised by n/log2(n) as dehshibi_detection_analysis does; "
                                          "for more than two symbols it is not bounded by 1. None below 2 trains"},
    ]
    if rule == "logisi":
        ceiling = p.get("max_core_gap_s") or 0
        specific = [{"name": "cut (logISI)", "rule": (
            "Pasquale et al. 2010 as restated by Cotterill et al. 2016: a Gaussian kernel density of log10(gap) "
            "(Silverman's robust bandwidth 0.9 min(sd, IQR/1.349) n^-1/5, printed); only peaks whose prominence is "
            f">= {PEAK_PROMINENCE_FRAC:g} of the maximum count; the intra-train peak is "
            + ("each peak in turn from the left (auto: no ceiling), paired with every peak after it"
               if not ceiling else f"the largest peak at or below {ceiling:g} s")
            + f"; the first minimum after it whose void 1 - g(min)/sqrt(g(p1) g(p2)) exceeds "
            f"{p.get('void_threshold', VOID_THRESHOLD):g} is the cut; a train is >= {p.get('min_events', 3)} events "
            "with gaps below the cut"
            + ("" if not ceiling else "; if the cut exceeds the ceiling, cores are found with the ceiling and "
                                      "extended with the cut")
            + f". No valley -> no trains. Fewer than {MIN_GAPS_FOR_HISTOGRAM} gaps -> refused. When the timing "
            "inside a train is irregular, a valley needs the gaps between trains to be ~30-100x those inside, so "
            "'no trains' can mean 'not resolvable'")}]
    elif rule == "maxinterval":
        specific = [{"name": "trains (MaxInterval)", "rule": (
            f"begin at a gap <= {p.get('mi_begin_gap_s'):g} s, continue while gaps <= {p.get('mi_end_gap_s'):g} s; "
            f"merge trains less than {p.get('mi_min_ibi_s'):g} s apart; drop trains shorter than "
            f"{p.get('mi_min_duration_s'):g} s or with fewer than {p.get('min_events', 3)} events. The five "
            "thresholds are PLACEHOLDERS for fungal data (Cotterill et al.'s are neuronal: 0.17, 0.3, 0.2, 0.01 s, 3)")}]
    else:
        specific = [{"name": "words (Adamatzky 2022)", "rule": (
            f"consecutive events share a word while their gap <= theta = {p.get('theta_mult', 1.0):g} x the mean gap "
            f"of the group (the paper used 1 and 2); words of one event are allowed; a word of >= "
            f"{p.get('min_events', 3)} events is called a train")}]
    return common + specific
