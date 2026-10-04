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

#: Settings › Analysis defaults — the three numbers, editable, recorded on
#: every classification they produce.
SETTINGS_PAGE = "analysis-defaults"
SETTINGS_KEYS = {
    "artifact_max_lag_s": "cross_channel.artifact_max_lag_s",
    "min_abs_r": "cross_channel.min_abs_r",
    "propagation_max_lag_s": "cross_channel.propagation_max_lag_s",
}


def _fmt(v):
    return f"{float(v):g}"


@dataclass(frozen=True)
class CrossChannelRule:
    """The three numbers the bins are cut at. Refuses a rule that is not one
    (a ceiling under the artifact line, an r floor outside 0..1) rather than
    binning by it."""

    artifact_max_lag_s: float = CROSS_CHANNEL_ARTIFACT_MAX_ABS_LAG_S
    min_abs_r: float = CROSS_CHANNEL_MIN_ABS_CORRELATION
    propagation_max_lag_s: float = CROSS_CHANNEL_PROPAGATION_MAX_ABS_LAG_S

    def __post_init__(self):
        a, r, p = float(self.artifact_max_lag_s), float(self.min_abs_r), float(self.propagation_max_lag_s)
        if not (a >= 0 and np.isfinite(a)):
            raise ValueError(f"the artifact lag line must be a non-negative number of seconds, got {a!r}")
        if not (0.0 <= r <= 1.0):
            raise ValueError(f"the r floor must lie in 0..1 (it is tested against |r|), got {r!r}")
        if not (p >= a and np.isfinite(p)):
            raise ValueError(f"the propagation ceiling ({p!r} s) must be at or above the artifact line ({a!r} s)")
        object.__setattr__(self, "artifact_max_lag_s", a)
        object.__setattr__(self, "min_abs_r", r)
        object.__setattr__(self, "propagation_max_lag_s", p)

    def as_dict(self):
        return {"artifact_max_lag_s": self.artifact_max_lag_s, "min_abs_r": self.min_abs_r,
                "propagation_max_lag_s": self.propagation_max_lag_s}

    def describe(self):
        """Each bin's rule in words, from the values in use — what the page
        prints behind the info icon beside the count it produced."""
        a, r, p = _fmt(self.artifact_max_lag_s), _fmt(self.min_abs_r), _fmt(self.propagation_max_lag_s)
        return {
            ARTIFACT: (f"|lag| ≤ {a} s and |r| ≥ {r}, either sign of r — the same event on two electrodes at "
                       f"the same time: contamination, not two events"),
            PROPAGATION: (f"{a} s < |lag| ≤ {p} s and |r| ≥ {r} — the event arriving on the other electrode a "
                          f"little later"),
            INDEPENDENT_RECURRENCE: (f"everything else: |r| < {r} at any lag, or |lag| > {p} s — not the same "
                                     f"event on two electrodes"),
        }


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
    return CrossChannelRule(**values)


def bin_for(lag_s, r, rule=DEFAULT_RULE):
    """The one place a (lag in seconds, r) becomes a bin."""
    abs_lag, abs_r = abs(float(lag_s)), abs(float(r))
    if abs_r < rule.min_abs_r:
        return INDEPENDENT_RECURRENCE
    if abs_lag <= rule.artifact_max_lag_s:
        return ARTIFACT
    if abs_lag <= rule.propagation_max_lag_s:
        return PROPAGATION
    return INDEPENDENT_RECURRENCE


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

    correlations = np.correlate(zx, zy, mode="full") / n
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
