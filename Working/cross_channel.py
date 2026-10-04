"""
cross_channel.py
=================
The UI-free core of cross-channel classification (ticket 41): given two
waveforms, compute the inter-channel lag from the cross-correlation peak and
the waveform identity from the correlation at that lag, then assign exactly
one of the three classification bins.

The classification is a statement about a motif *family*, not about a single
univariate `Signal`, so this is not an adapter and it imports no UI library.
It can be imported from a bare script, or run directly with
``python Working/cross_channel.py ENTRY_ID`` to classify a library entry's
cross-channel edges.

The bin boundaries are judgement calls that the recurrence claim rests on, so
they are named constants below rather than literals buried in the function —
and since fixup-W (2026-10-04) they are the researcher's decided rule, in
seconds, editable as three Settings keys (`rule_from_settings`).
"""

from dataclasses import dataclass

import numpy as np
from scipy import signal as _signal

from Working.distances import resample_to_length, z_normalize

# The three bins, in the exact spelling persisted on `motif_edge`.
ARTIFACT = "artifact"
PROPAGATION = "propagation"
INDEPENDENT_RECURRENCE = "independent_recurrence"
BINS = (ARTIFACT, PROPAGATION, INDEPENDENT_RECURRENCE)

# ── Bin boundaries — the researcher's rule (QUESTIONS.md Q40b, Round 10 Q-W5,
#    2026-10-03) ────────────────────────────────────────────────────────────
#
# Lag is in SECONDS and converted to samples with each recording's fs, and r
# is tested by its MAGNITUDE (its sign is stored on the edge, never binned):
#
# - `artifact`: |lag| <= 1 s and |r| >= 0.5, either sign. "Any events on
#   different electrodes at the exact same time are artifacts" — contamination
#   (a shared ground, common-mode pickup); a sub-second propagation is out of
#   reach at 1 Hz and would need its own study. An inverted copy at lag 0 is an
#   artifact too. There is no separate common-mode bin.
# - `propagation`: 1 s < |lag| <= 50 s and |r| >= 0.5 — the same event arriving
#   on the next electrode a little later, travelling through the mycelium.
# - `independent_recurrence`: everything else, INCLUDING any pair under the r
#   floor whatever its lag (before 2026-10-04 a pair at r 0.16 could be
#   "propagation": the bin had no floor).
#
# The three numbers are Settings keys (`SETTINGS_KEYS`); these are the defaults.
CROSS_CHANNEL_ARTIFACT_MAX_ABS_LAG_S = 1.0
CROSS_CHANNEL_MIN_ABS_CORRELATION = 0.5
CROSS_CHANNEL_PROPAGATION_MAX_ABS_LAG_S = 50.0

# ── fixup-AD (QUESTIONS.md Rounds 11-12, 2026-10-04): a match must beat chance ──
#
# Q40d measured that W's rule passes the same sibling cut at a RANDOM other
# moment as often as at the member's own (91 % vs 90 % on Fig2A): short clips
# of slow drift correlate with anything. So every bin now also needs:
#
# - **the chance test** — the same statistic `classify_waveforms` computes
#   (|r| at the cross-correlation peak), on the same sibling at K random other
#   times: windows of the member's length, at least `NULL_MIN_GAP_S` from it,
#   inside the recording, never over a human-marked artifact region. The match
#   counts only if its |r| exceeds the `null_percentile`th percentile of those.
#   The draw is seeded from the member id, so a re-run reproduces it.
# - **the noise floor on both sides** — the member's and the sibling's
#   peak-to-peak over the window, in mV by `recordings.units`, both at or above
#   the dataset's floor (Settings › Datasets, 0.1 mV where empty;
#   `Working.library.view_filter.dataset_floors`, the one reader).
# - **a minimum length** — a member under `min_samples` is *too short to tell*:
#   counted, never binned, never padded (padding adds shared drift).
#
# and the artifact test's r floor is raised to 0.98 (the researcher's number,
# Round 12 Q1). The 0.98 is the ARTIFACT test's only; propagation keeps 0.5
# plus the chance test (an assumption flagged in Round 12). The bin is still
# spelled `artifact` on the edge; it now means *suspected* — a human confirms
# it in Review (`Working.review.artifact_queue`).
CROSS_CHANNEL_ARTIFACT_MIN_ABS_CORRELATION = 0.98
CROSS_CHANNEL_NULL_K = 100
CROSS_CHANNEL_NULL_PERCENTILE = 95.0
CROSS_CHANNEL_MIN_SAMPLES = 30
#: The random windows sit at least this far from the member (decided, not a key).
CROSS_CHANNEL_NULL_MIN_GAP_S = 60.0

#: What a member under the minimum length is called, everywhere it is counted.
TOO_SHORT = "too_short"

#: Settings › Analysis defaults — the numbers, editable, recorded on every
#: classification they produce.
SETTINGS_PAGE = "analysis-defaults"
SETTINGS_KEYS = {
    "artifact_max_lag_s": "cross_channel.artifact_max_lag_s",
    "min_abs_r": "cross_channel.min_abs_r",
    "propagation_max_lag_s": "cross_channel.propagation_max_lag_s",
    "artifact_min_abs_r": "cross_channel.artifact_min_abs_r",
    "null_k": "cross_channel.null_k",
    "null_percentile": "cross_channel.null_percentile",
    "min_samples": "cross_channel.min_samples",
}
#: The whole-number keys (the rest are floats).
_INT_FIELDS = ("null_k", "min_samples")


def _fmt(v):
    return f"{float(v):g}"


@dataclass(frozen=True)
class CrossChannelRule:
    """The numbers the bins are cut at. Refuses a rule that is not one (a
    ceiling under the artifact line, an r floor outside 0..1, a percentile
    outside (0, 100), a null of no draws) rather than binning by it."""

    artifact_max_lag_s: float = CROSS_CHANNEL_ARTIFACT_MAX_ABS_LAG_S
    min_abs_r: float = CROSS_CHANNEL_MIN_ABS_CORRELATION
    propagation_max_lag_s: float = CROSS_CHANNEL_PROPAGATION_MAX_ABS_LAG_S
    artifact_min_abs_r: float = CROSS_CHANNEL_ARTIFACT_MIN_ABS_CORRELATION
    null_k: int = CROSS_CHANNEL_NULL_K
    null_percentile: float = CROSS_CHANNEL_NULL_PERCENTILE
    min_samples: int = CROSS_CHANNEL_MIN_SAMPLES

    def __post_init__(self):
        a, r, p = float(self.artifact_max_lag_s), float(self.min_abs_r), float(self.propagation_max_lag_s)
        ar, pct = float(self.artifact_min_abs_r), float(self.null_percentile)
        if not (a >= 0 and np.isfinite(a)):
            raise ValueError(f"the artifact lag line must be a non-negative number of seconds, got {a!r}")
        if not (0.0 <= r <= 1.0):
            raise ValueError(f"the r floor must lie in 0..1 (it is tested against |r|), got {r!r}")
        if not (0.0 <= ar <= 1.0):
            raise ValueError(f"the artifact test's r floor must lie in 0..1 (it is tested against |r|), got {ar!r}")
        if not (p >= a and np.isfinite(p)):
            raise ValueError(f"the propagation ceiling ({p!r} s) must be at or above the artifact line ({a!r} s)")
        if float(self.null_k) != int(self.null_k) or int(self.null_k) < 1:
            raise ValueError(f"the chance test needs a whole number of random windows, at least 1, got {self.null_k!r}")
        if not (0.0 < pct < 100.0):
            raise ValueError(f"the chance test's percentile must lie strictly between 0 and 100, got {pct!r}")
        if float(self.min_samples) != int(self.min_samples) or int(self.min_samples) < 4:
            raise ValueError(f"the minimum length must be a whole number of samples, at least 4, "
                             f"got {self.min_samples!r}")
        object.__setattr__(self, "artifact_max_lag_s", a)
        object.__setattr__(self, "min_abs_r", r)
        object.__setattr__(self, "propagation_max_lag_s", p)
        object.__setattr__(self, "artifact_min_abs_r", ar)
        object.__setattr__(self, "null_k", int(self.null_k))
        object.__setattr__(self, "null_percentile", pct)
        object.__setattr__(self, "min_samples", int(self.min_samples))

    def as_dict(self):
        return {"artifact_max_lag_s": self.artifact_max_lag_s, "min_abs_r": self.min_abs_r,
                "propagation_max_lag_s": self.propagation_max_lag_s,
                "artifact_min_abs_r": self.artifact_min_abs_r, "null_k": self.null_k,
                "null_percentile": self.null_percentile, "min_samples": self.min_samples,
                "null_min_gap_s": CROSS_CHANNEL_NULL_MIN_GAP_S}

    def chance_words(self):
        return (f"beats chance (|r| above the {_fmt(self.null_percentile)}th percentile of the same sibling at "
                f"{self.null_k} random other times, each at least {_fmt(CROSS_CHANNEL_NULL_MIN_GAP_S)} s from the "
                f"member and never over a human-marked artifact)")

    def describe(self):
        """Each bin's rule in words, from the values in use — what the page
        prints behind the info icon beside the count it produced."""
        a, r, p = _fmt(self.artifact_max_lag_s), _fmt(self.min_abs_r), _fmt(self.propagation_max_lag_s)
        ar = _fmt(self.artifact_min_abs_r)
        floor = "and both swings clear the dataset's noise floor (Settings › Datasets, 0.1 mV where empty)"
        return {
            ARTIFACT: (f"suspected artifact: |lag| ≤ {a} s and |r| ≥ {ar}, either sign of r, {self.chance_words()} "
                       f"{floor} — the same event on two electrodes at the same time. The machine only flags it; "
                       f"a human confirms it in Review"),
            PROPAGATION: (f"{a} s < |lag| ≤ {p} s and |r| ≥ {r}, {self.chance_words()} {floor} — the event "
                          f"arriving on the other electrode a little later"),
            INDEPENDENT_RECURRENCE: (f"everything else: |r| < {ar} at |lag| ≤ {a} s, |r| < {r} beyond it, "
                                     f"|lag| > {p} s, not beating chance, or a swing under the noise floor — not "
                                     f"shown to be the same event on two electrodes"),
        }

    def describe_too_short(self):
        return (f"too short to tell: a member under {self.min_samples} samples is not classified — counted, never "
                f"binned and never padded (padding adds shared drift, which correlates on its own)")


DEFAULT_RULE = CrossChannelRule()


def rule_from_settings(conn):
    """The rule as Settings › Analysis defaults holds it, a default for any key
    not saved. A saved value that does not make a rule raises."""
    from Working.registration.settings import get_settings

    saved = get_settings(conn, SETTINGS_PAGE)
    values = {}
    for field, key in SETTINGS_KEYS.items():
        v = saved.get(key)
        if v not in (None, ""):
            values[field] = float(v)
            if field in _INT_FIELDS and float(v) == int(float(v)):
                values[field] = int(float(v))
    return CrossChannelRule(**values)


def bin_for(lag_s, r, rule=DEFAULT_RULE, *, beats_chance=True, above_floor=True):
    """The one place a (lag in seconds, r) becomes a bin.

    `beats_chance` and `above_floor` are the pair's chance test and noise-floor
    test (fixup-AD); a pair that fails either is independent whatever its lag
    and r. They default to true for a caller holding only two waveforms
    (`classify_waveforms`), which has nothing to draw a null from."""
    abs_lag, abs_r = abs(float(lag_s)), abs(float(r))
    if not beats_chance or not above_floor:
        return INDEPENDENT_RECURRENCE
    if abs_lag <= rule.artifact_max_lag_s:
        return ARTIFACT if abs_r >= rule.artifact_min_abs_r else INDEPENDENT_RECURRENCE
    if abs_r < rule.min_abs_r:
        return INDEPENDENT_RECURRENCE
    if abs_lag <= rule.propagation_max_lag_s:
        return PROPAGATION
    return INDEPENDENT_RECURRENCE


# ── fixup-AD: the per-pair chance test ───────────────────────────────────────

def _allowed_starts(n, length, start, end, gap, forbidden):
    """The start positions a random window may take, as sorted disjoint
    half-open intervals: inside [0, n - length], at least `gap` samples clear
    of [start, end), and overlapping no `forbidden` span."""
    hi = n - length + 1                       # starts in [0, hi)
    if hi <= 0:
        return []
    cuts = [(start - gap - length + 1, end + gap)]
    cuts += [(int(a) - length + 1, int(b)) for a, b in (forbidden or ())]
    cuts = sorted((max(0, a), min(hi, b)) for a, b in cuts if b > 0 and a < hi)
    out, at = [], 0
    for a, b in cuts:
        if a > at:
            out.append((at, a))
        at = max(at, b)
    if at < hi:
        out.append((at, hi))
    return [(a, b) for a, b in out if b > a]


def chance_null(x, sibling, start, end, fs, rule=DEFAULT_RULE, seed=0, forbidden=()):
    """The pair's null: `rule.null_k` windows of `x`'s length cut from
    `sibling` at random other times, each scored with the statistic
    `classify_waveforms` uses (|r| at the cross-correlation peak).

    `x` is the member channel's window [start, end); `sibling` the WHOLE
    sibling channel (an mmap is fine); `forbidden` the sibling's human-marked
    artifact spans, `[(a, b), ...]` in samples. `seed` should come from the
    member id (and the sibling's) so a re-run reproduces the draw.

    Returns `{k, k_requested, starts, abs_r, threshold, at, min_gap_s,
    reason}` — `threshold` the `rule.null_percentile`th percentile of `abs_r`;
    None, with a reason, when the recording has no room for one window.
    """
    x = np.asarray(x, dtype=float).ravel()
    length = int(end) - int(start)
    n = int(len(sibling))
    gap = int(np.ceil(CROSS_CHANNEL_NULL_MIN_GAP_S * float(fs or 1.0)))
    out = {"k": 0, "k_requested": int(rule.null_k), "starts": [], "abs_r": [], "threshold": None,
           "at": float(rule.null_percentile), "min_gap_s": CROSS_CHANNEL_NULL_MIN_GAP_S, "reason": None}
    allowed = _allowed_starts(n, length, int(start), int(end), gap, forbidden)
    total = sum(b - a for a, b in allowed)
    if total <= 0:
        out["reason"] = (f"no room for a random window: the recording holds no {length}-sample window at least "
                         f"{_fmt(CROSS_CHANNEL_NULL_MIN_GAP_S)} s from the member outside a human-marked artifact")
        return out
    rng = np.random.default_rng(seed)
    k = int(rule.null_k)
    picks = rng.choice(total, size=k, replace=total < k)
    bounds = np.cumsum([0] + [b - a for a, b in allowed])
    starts = []
    for p in (int(v) for v in picks):
        i = int(np.searchsorted(bounds, p, side="right")) - 1
        starts.append(int(allowed[i][0] + (p - bounds[i])))
    kept_s, kept_r = [], []
    for s0 in starts:
        y = np.asarray(sibling[s0:s0 + length], dtype=float)
        if y.size != length or not np.isfinite(y).all() or y.std() == 0:
            continue
        kept_s.append(int(s0))
        kept_r.append(abs(cross_correlation_peak(x, y)[1]))
    out["starts"], out["abs_r"], out["k"] = kept_s, kept_r, len(kept_r)
    if kept_r:
        out["threshold"] = float(np.percentile(kept_r, rule.null_percentile))
    else:
        out["reason"] = "every random window was flat or non-finite"
    return out


def beats_chance(r, null):
    """Whether |r| exceeds the null's threshold. No null, no claim: a pair the
    test could not be drawn for does not beat chance."""
    if not null or null.get("threshold") is None:
        return False
    return abs(float(r)) > float(null["threshold"])


def chance_summary(r, null):
    """What is stored beside a result: the percentile of |r| within the pair's
    null, the threshold it had to exceed, K, and whether it did."""
    vals = np.asarray(null.get("abs_r") or [], dtype=float)
    pct = float(100.0 * np.mean(vals < abs(float(r)))) if vals.size else None
    return {"k": int(null.get("k") or 0), "k_requested": int(null.get("k_requested") or 0),
            "at": float(null.get("at")), "threshold": null.get("threshold"), "percentile": pct,
            "beats": beats_chance(r, null), "min_gap_s": null.get("min_gap_s"), "reason": null.get("reason")}


def cross_correlate(x, y):
    """Normalised cross-correlation between two waveforms.

    The two inputs are resampled to their common (longer) length and
    z-normalised before correlation, so the returned correlations are Pearson
    correlations at each integer sample lag and are directly comparable
    across pairs of unequal native length.

    Returns
    -------
    (lags, correlations) : (numpy.ndarray, numpy.ndarray)
        `lags` are the raw ``numpy.correlate(..., mode="full")`` lags in
        samples; `correlations` are the corresponding correlation values.
    """
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    if x.size == 0 or y.size == 0:
        raise ValueError("cross-correlation requires two non-empty waveforms")
    n = max(x.size, y.size)
    x = resample_to_length(x, n)
    y = resample_to_length(y, n)

    zx = z_normalize(x)
    zy = z_normalize(y)

    # scipy picks the direct sum for short windows and the FFT for long ones (fixup-AD: the chance test
    # correlates 100 random windows per pair, and an M2_aug member runs to 7,000 samples); same values
    correlations = _signal.correlate(zx, zy, mode="full", method="auto") / n
    lags = np.arange(-(n - 1), n)
    return lags, correlations


def cross_correlation_peak(x, y):
    """The inter-channel lag and waveform identity of two waveforms.

    The peak is the largest absolute correlation (the same shape may be
    inverted on another channel). The returned lag is signed: it is the lag
    of `y` relative to `x`, positive meaning `y` occurs later than `x`.

    Returns
    -------
    (lag, correlation) : (int, float)
    """
    lags, correlations = cross_correlate(x, y)
    peak = int(np.argmax(np.abs(correlations)))
    # `np.correlate(x, y)`'s positive lags mean `x` occurs later than `y`;
    # invert so the public lag reads as `y` relative to `x`.
    return int(-lags[peak]), float(correlations[peak])


def classify_waveforms(x, y, fs=1.0, rule=DEFAULT_RULE):
    """Classify a pair of waveforms into exactly one cross-channel bin.

    `x` and `y` must be the SAME absolute window on two channels (Q40a): the
    lag is then a time offset between electrodes. Two snippets cut from
    different times have no lag between them — `cross_correlate` would only
    report how far one cut-out must slide to align with the other.

    `fs` is the samples per second of the arrays as passed (a decimated window
    passes its decimated rate), so the rule's seconds compare with the lag.

    Returns
    -------
    (lag, waveform_correlation, classification) : (int, float, str)
        `lag` in samples of the arrays passed, `y` relative to `x`;
        `classification` is one of `BINS`.
    """
    lag, waveform_correlation = cross_correlation_peak(x, y)
    return lag, waveform_correlation, bin_for(lag / float(fs), waveform_correlation, rule)


if __name__ == "__main__":
    import argparse

    from Working.database.schema import init_db
    from Working.library import classify_cross_channel_edges

    parser = argparse.ArgumentParser(
        description="Classify one motif family's cross-channel edges.",
    )
    parser.add_argument("entry_id", type=int, help="motif_entry id to classify")
    parser.add_argument("--db", default=None,
                        help="database path (default: DATA/db/annotations.sqlite)")
    args = parser.parse_args()

    conn = init_db(args.db)
    try:
        results = classify_cross_channel_edges(conn, args.entry_id)
        print(f"classified {len(results)} cross-channel edge(s) for entry {args.entry_id}")
    finally:
        conn.close()
