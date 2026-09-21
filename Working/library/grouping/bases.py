"""
bases.py
==========
The feature computations behind the Library's "feature bins, no distance"
grouping bases, and the two things the grouping editor needs to draw them:
a distribution, and which bases apply to which unit.

**Nothing here is ever stored.** `docs/LIBRARY_STORAGE.md` 3.4 states the rule
and spec 4.4 is where it comes from: *"Writing measured features onto Library
rows was rejected outright: it would make a row's meaning depend on whichever
interrogation happened to run last."* So amplitude, timescale, frequency
content and polarity are computed from the waveform every time the page asks,
and a number seen in a feature histogram was measured when it was drawn. There
is deliberately no cache and no write path in this module.

Spec 8.2 names the nine bases in three kinds:

    distance          shape distance, sequence similarity
    feature bins      amplitude, timescale, frequency content, polarity
    labels            tag, provenance, custom

and the three bin methods, exactly: `quantiles`, `log-spaced`, `fixed edges`.
`applicable_bases` implements the rule that *"a basis that does not apply to
the unit is shown disabled with its reason"* — the reason travels with the
refusal so the editor never has to invent one.
"""

from dataclasses import dataclass

import numpy as np
from scipy.signal import welch

# The three grouping units (`groupings.unit`, LIBRARY_STORAGE.md 3.3).
UNITS = ("single_motifs", "sequences", "spike_trains")

# The three bin methods, spelled as spec 8.2 spells them.
BIN_QUANTILES = "quantiles"
BIN_LOG_SPACED = "log-spaced"
BIN_FIXED_EDGES = "fixed edges"
BIN_METHODS = (BIN_QUANTILES, BIN_LOG_SPACED, BIN_FIXED_EDGES)

# Bin counts the editor accepts; its own validation message is "2 to 20 bins".
MIN_BINS, MAX_BINS = 2, 20


# --------------------------------------------------------------------------
# The four feature computations
# --------------------------------------------------------------------------

def _values(x):
    """The waveform as a 1-D float array, rejecting the empty and the
    non-finite loudly rather than returning a nan that spreads into a bin
    edge and quietly swallows a whole grouping."""
    x = np.asarray(x, dtype=float).ravel()
    if x.size == 0:
        raise ValueError("A feature cannot be measured on an empty waveform.")
    if not np.all(np.isfinite(x)):
        raise ValueError("Waveform contains NaN or inf; refusing to measure it.")
    return x


def amplitude(values, fs=None):
    """Peak-to-peak amplitude, in the waveform's own units (mV for a
    detrended library motif). Peak-to-peak rather than a peak height because
    the library holds both polarities and a drop's depth is as real as a
    spike's height. `fs` is accepted and ignored so every feature shares one
    call signature."""
    x = _values(values)
    return float(x.max() - x.min())


def timescale(values, fs):
    """Duration in seconds — spec 8.2's "timescale (duration)". Sample count
    over the sampling rate; a library spanning 1 Hz and 10 Hz recordings has
    no other honest common axis, which is also why `fs` is required here and
    optional everywhere else."""
    x = _values(values)
    fs = float(fs)
    if fs <= 0:
        raise ValueError(f"timescale needs a positive sampling rate, got {fs!r}.")
    return float(x.size / fs)


def frequency_content(values, fs, nperseg=None):
    """Dominant frequency in Hz, via Welch's PSD — spec 8.2 names the method
    ("frequency content (e.g. dominant frequency, Welch)") so it is Welch and
    not a bare periodogram.

    The DC bin is excluded: a drop motif's mean offset is not its frequency
    content, and leaving DC in makes every detrended-but-not-quite span
    answer "0 Hz". `nperseg` defaults to the whole span capped at 512, which
    keeps the resolution as fine as the span allows without asking the caller
    to reason about segment lengths.
    """
    x = _values(values)
    fs = float(fs)
    if fs <= 0:
        raise ValueError(f"frequency_content needs a positive fs, got {fs!r}.")
    if x.size < 4:
        raise ValueError("frequency_content needs at least 4 samples.")
    if nperseg is None:
        nperseg = min(x.size, 512)
    freqs, power = welch(x, fs=fs, nperseg=int(nperseg))
    if freqs.size < 2:
        return 0.0
    return float(freqs[1:][int(np.argmax(power[1:]))])


def polarity(values, fs=None):
    """Signed polarity in [-1, +1]: +1 a purely upward excursion, -1 a purely
    downward one, near 0 biphasic — which is the `up / down / biphasic`
    reading the grouping editor offers, with its `biphasic` parameter as the
    width of the band around zero.

    Measured against the median rather than the mean so that one long tail
    does not decide the polarity of a short excursion.
    """
    x = _values(values)
    baseline = float(np.median(x))
    up = max(0.0, float(x.max()) - baseline)
    down = max(0.0, baseline - float(x.min()))
    if up + down == 0.0:
        return 0.0
    return float((up - down) / (up + down))


# name -> (function, needs fs, unit label) for the four feature-bin bases.
FEATURES = {
    "amplitude": (amplitude, False, "mV"),
    "timescale": (timescale, True, "s"),
    "frequency-content": (frequency_content, True, "Hz"),
    "polarity": (polarity, False, ""),
}


def compute_feature(name, values, fs=None):
    """One feature by its basis name. Raises `KeyError` for anything that is
    not one of the four feature-bin bases — a typo must not silently become
    an empty grouping."""
    if name not in FEATURES:
        raise KeyError(f"Unknown feature basis '{name}'. "
                       f"Available: {sorted(FEATURES)}")
    func, needs_fs, _ = FEATURES[name]
    return func(values, fs) if needs_fs else func(values)


def feature_unit(name):
    """The unit string the histogram's axis is labelled with."""
    if name not in FEATURES:
        raise KeyError(f"Unknown feature basis '{name}'.")
    return FEATURES[name][2]


# --------------------------------------------------------------------------
# The distribution the grouping editor draws
# --------------------------------------------------------------------------

@dataclass
class Distribution:
    """Bin edges and the count in each, plus how many values fell outside
    every bin — the amber `outside range` bars in the editor's histogram.

    `edges` has one more entry than `counts`. A bin covers `[lo, hi)` except
    the last, which is closed at both ends so the maximum value is inside a
    bin rather than outside every one of them.
    """
    edges: list
    counts: list
    n_outside: int

    def as_dict(self):
        return {"edges": list(self.edges), "counts": list(self.counts),
                "n_outside": int(self.n_outside)}


def bin_edges(values, *, bin_method, count=None, range=None):
    """The bin edges alone, for a caller that wants to draw the edges over
    somebody else's histogram. Same validation as `distribution`.

    `range` means two different things on purpose, because the editor's one
    field does: for `quantiles` and `log-spaced` it is the `(lo, hi)` extent
    to bin over; for `fixed edges` it IS the increasing edge sequence and
    `count` is ignored.
    """
    if bin_method not in BIN_METHODS:
        raise ValueError(f"Unknown bin method {bin_method!r}. "
                         f"Spec 8.2 names exactly: {BIN_METHODS}.")

    if bin_method == BIN_FIXED_EDGES:
        if range is None or len(range) < 2:
            raise ValueError("'fixed edges' needs at least two edges in `range`.")
        edges = np.asarray([float(e) for e in range], dtype=float)
        flat = np.nonzero(np.diff(edges) <= 0)[0]
        if flat.size:
            i = int(flat[0]) + 1
            raise ValueError(f"edges must increase: {edges[i]:g} <= "
                             f"{edges[i - 1]:g} at position {i + 1}")
        return [float(e) for e in edges]

    if count is None:
        raise ValueError(f"{bin_method!r} needs a bin count.")
    count = int(count)
    if not MIN_BINS <= count <= MAX_BINS:
        raise ValueError(f"{MIN_BINS} to {MAX_BINS} bins (got {count}).")

    if bin_method == BIN_LOG_SPACED:
        if range is None:
            x = _finite(values)
            positive = x[x > 0]
            if positive.size == 0:
                raise ValueError("log-spaced bins need a range above 0.")
            lo, hi = float(positive.min()), float(positive.max())
        else:
            lo, hi = float(range[0]), float(range[1])
        if lo <= 0 or hi <= lo:
            raise ValueError("log-spaced bins need a range above 0.")
        return [float(e) for e in np.geomspace(lo, hi, count + 1)]

    # quantiles: edges at evenly spaced quantiles of the data itself, so each
    # bin holds about the same number of members.
    x = _finite(values)
    if range is not None:
        lo, hi = float(range[0]), float(range[1])
        x = x[(x >= lo) & (x <= hi)]
    if x.size == 0:
        raise ValueError("quantile bins need at least one value inside the range.")
    edges = np.quantile(x, np.linspace(0.0, 1.0, count + 1))
    edges = _nudge_ties(edges)
    return [float(e) for e in edges]


def _finite(values):
    x = np.asarray(list(values), dtype=float).ravel()
    x = x[np.isfinite(x)]
    if x.size == 0:
        raise ValueError("No finite values to bin.")
    return x


def _nudge_ties(edges):
    """Quantiles of a heavily tied distribution can repeat an edge, which
    would produce an empty bin whose `[lo, hi)` is empty. Nudge each repeat
    up by a hair so the edges stay strictly increasing and the bin count the
    researcher asked for is the bin count they get."""
    edges = np.asarray(edges, dtype=float).copy()
    for i in range(1, len(edges)):
        if edges[i] <= edges[i - 1]:
            edges[i] = np.nextafter(edges[i - 1], np.inf)
    return edges


def assign_bins(values, edges):
    """Bin index per value (0-based), or `None` for a value outside every
    bin. The last bin is closed at the top — see `Distribution`."""
    out = []
    for v in values:
        v = float(v)
        if not np.isfinite(v) or v < edges[0] or v > edges[-1]:
            out.append(None)
            continue
        index = int(np.searchsorted(edges, v, side="right")) - 1
        out.append(min(index, len(edges) - 2))
    return out


def distribution(values, *, bin_method, count=None, range=None):
    """The histogram the grouping editor draws: bin edges, the count in each
    bin, and how many values fell outside every bin."""
    edges = bin_edges(values, bin_method=bin_method, count=count, range=range)
    counts = [0] * (len(edges) - 1)
    n_outside = 0
    for index in assign_bins(values, edges):
        if index is None:
            n_outside += 1
        else:
            counts[index] += 1
    return Distribution(edges=edges, counts=counts, n_outside=n_outside)


# --------------------------------------------------------------------------
# Which bases apply to which unit
# --------------------------------------------------------------------------

# name -> (kind, label, one line for the editor)
BASES = {
    "shape-distance": ("distance", "shape distance",
                       "z-normalised, scale-invariant, Ward cut"),
    "sequence-similarity": ("distance", "sequence similarity",
                            "events in order, with gaps"),
    "amplitude": ("feature-bins", "amplitude", "peak-to-peak mV"),
    "timescale": ("feature-bins", "timescale", "duration"),
    "frequency-content": ("feature-bins", "frequency content",
                          "dominant frequency, Welch"),
    "polarity": ("feature-bins", "polarity", "up / down / biphasic"),
    "tag": ("labels", "tag", "morphology tags"),
    "provenance": ("labels", "provenance", "recording, run or spike train"),
    "custom": ("labels", "custom", "a clustering exported from Analyse"),
}

_NOT_A_SEQUENCE = ("sequence similarity compares events in order with the gaps "
                   "between them; a single motif is one event and belongs to no "
                   "sequence")
_NOT_ONE_SHAPE = ("a spike train is a whole train, not one shape")


def applicable_bases(unit):
    """basis name -> `{"applies": bool, "reason": str | None, ...}` for one
    unit. Spec 8.2: *"a basis that does not apply to the unit is shown
    disabled with its reason"* — so the reason is computed here, beside the
    rule, rather than written into the page.

    Every basis is reported for every unit; nothing is dropped from the list,
    because a basis that silently disappears cannot be explained.
    """
    if unit not in UNITS:
        raise ValueError(f"Unknown grouping unit {unit!r}. Spec 8.2 names "
                         f"exactly: {UNITS}.")
    out = {}
    for name, (kind, label, blurb) in BASES.items():
        reason = None
        if name == "sequence-similarity" and unit != "sequences":
            reason = _NOT_A_SEQUENCE
        elif name == "shape-distance" and unit == "spike_trains":
            reason = _NOT_ONE_SHAPE
        out[name] = {"basis": name, "kind": kind, "label": label,
                     "help": blurb, "applies": reason is None, "reason": reason}
    return out
