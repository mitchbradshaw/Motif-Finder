"""
event_shape.py
===============
Every per-event shape measure, from one pass, polarity-neutral.

Given a trace and a set of event windows, each event is first ORIENTED so it
is a fall (a drop is measured as it stands; a spike is measured on `-x`), then
its anatomy is found with the drop detector's own rules, then everything is
measured off that anatomy, and finally the signed quantities are turned back
into the recorded signal's frame. So a spike's height and a drop's depth are
one number (`event_amplitude_mv`), and a spike's steepest rise is a positive
`max_slope_mv_s` where a drop's steepest fall is negative.

Where a detector (or any upstream block) already located the event — its
onset and trough — those ARE the event: `measures_events(anchors=...)`, and the
block's upstream `onset_idx` / `extremum_idx` columns. The Library's stored
features use the store's own anchors, so their depth is the detector's depth
to the last bit (410 / 410 seed events). The anatomy search below is for spans
nobody anatomised; on the 360 seed snippets it matched the detector's trough
within 3 samples on 345, and on 10 locked onto a steeper neighbouring fall in
the minutes of context a stored snippet carries.

Polarity defaults to `drop`: every detector in the registry finds drops, and
the spike route is `preprocessing.invert` + `upstream_inverted`. `auto` (the
window's fastest edge) exists and says in its rule where it fails.

The anatomy — reused, not re-derived
------------------------------------
    steepest   the most negative sample of `np.gradient(z)` in the window
    knee       `detect.find_trough`: walking on from the steepest sample, the
               first of three samples shallower than `knee_frac` of it. This
               is where the steep part of the fall ends (its docstring gives
               the two rules it replaced and why both failed)
    extremum   the lowest sample of `z` between the steepest sample and the
               knee. The knee on its own lands one sample PAST a V-shaped
               minimum (the rising sample is the first "shallow" one), so the
               extremum is the minimum the knee brackets; on a flat-bottomed
               fall it is the first sample of the floor
    onset      `detect5.refine_onset` (the knee rule read backwards from the
               steepest sample) and then, with `walk_onset_back`,
               `detect5.walk_back_to_shoulder` bounded by the window start —
               the same two steps detect5 applies before its gates

The measures this block had to DEFINE (nothing in the repo measured them)
------------------------------------------------------------------------
    recovery        the first time after the extremum that `z` climbs back to
                    `z[extremum] + recovery_frac * depth` (default 0.5: half
                    recovery), linearly interpolated between samples. Searched
                    forward past the window's end — a detector's window is
                    bracketed tightly around the fall — but never into the next
                    event (the next window's start) and never further than
                    `recovery_max_mult` event widths. Not reached -> NaN, and
                    counted. The only `recovery_s` that existed before was a UI
                    mock fixture (`webui/pages/inventory/interrogation-
                    training.md`) and is not a definition
    fwhm            full width at half maximum: the baseline is the onset level
                    and the maximum is the extremum, so the half level is
                    `z[onset] - depth / 2`; FWHM is the time between the last
                    crossing of it on the way down and the first on the way
                    back (same search bound as recovery), both interpolated
    event_width     onset -> extremum. For a drop this is detect5's
                    `fall_duration_s` (trough - onset) / fs
    duration        onset -> recovery
    precursor       the opposite-sign excursion that precedes the event: how
                    far the onset level stands above the lowest point of the
                    window before it (a drop's rise, a spike's dip). It is not
                    detect5's `rise_height_mv`, which is 0.0 unless the event
                    was rise-triggered (85.8 % of `drop_motifs10`)

Why `data_analysis.half_width` is not the FWHM here: it finds the most
prominent PEAK with `scipy.signal.find_peaks` (so a drop needs inverting), and
returns `min(left, right)` half-width IN SAMPLES — the narrower half, not the
full width at half maximum the researcher asked for. It stays where it is; this
is the electrophysiological measure beside it.

With depth = 0 (a window with no fall in it) every anatomy measure is NaN and
the event is counted, never guessed.

Units. `x` is taken to be in the core's native unit, volts (`detect5.py:81`):
`to_mv` (default 1000) turns amplitudes into mV and slopes into mV/s, with the
sample rate applied once (`np.gradient * fs`), never twice. A recording stored
in mV (`L_LM_Jul_26_J`) is 1000x large through this, exactly as it is through
detect5 — that is QUESTIONS.md Q-X2.8, open, and the printed `units` rule says
so rather than hiding it.

No plotting library - CLAUDE.md rule 1.
"""

import numpy as np
import pandas as pd

from Working.Detection.drop_motifs.detect import find_trough
from Working.Detection.drop_motifs.detect5 import refine_onset, walk_back_to_shoulder
from Working.Detection.drop_motifs.gradients import (
    DEFAULT_SLOPE_REF_MV_S, SLOPE_SCALES, fall_gradients, rose_data, rose_histogram,
)

POLARITIES = ("auto", "drop", "spike")
DROP, SPIKE = -1, 1

KNEE_FRAC = 0.05          # detect5's default, the same number the detector ran with
RECOVERY_FRAC = 0.5
RECOVERY_MAX_MULT = 10.0
TO_MV_FROM_VOLTS = 1000.0

# Index columns are in the SpanSet's own frame (span-relative, like `starts`).
COLUMNS = ("polarity", "onset_idx", "extremum_idx", "recovery_idx", "event_amplitude_mv",
           "precursor_height_mv", "event_width_s", "duration_s", "fwhm_s", "recovery_time_s",
           "max_slope_mv_s", "onset_slope_mv_s", "chord_slope_mv_s", "peakedness", "span_ptp_mv")

# The measures a stored motif carries (`motif_features`): everything but the indices,
# which only mean something against one trace.
MEASURES = tuple(c for c in COLUMNS if not c.endswith("_idx"))

UNLIT = {c: float("nan") for c in COLUMNS}


def rules(*, knee_frac=KNEE_FRAC, recovery_frac=RECOVERY_FRAC, recovery_max_mult=RECOVERY_MAX_MULT,
          walk_onset_back=True, to_mv=TO_MV_FROM_VOLTS, upstream_inverted=False, polarity="drop",
          anchors_used=None):
    """The rule behind every measure, as printed beside the numbers — a measure
    whose rule is unstated cannot be argued with."""
    unit = ("x is in volts, the core's convention (detect5.py:81): amplitudes x1000 -> mV, "
            "slopes are np.gradient(x) * fs x1000 -> mV/s (fs applied once). A recording stored "
            "in mV reads 1000x large here, as it does through detect5 (QUESTIONS.md Q-X2.8)"
            if to_mv == TO_MV_FROM_VOLTS else f"x is multiplied by {to_mv:g} to give mV; slopes in mV/s, fs applied once")
    return [
        {"name": "polarity", "rule": f"{polarity}: " + {
            "drop": "every event is a drop (-1) — the default, because every detector in the registry is a drop detector",
            "spike": "every event is a spike (+1), measured on -x and reported in the recorded frame",
            "auto": "the window's fastest edge decides — steepest fall at least as steep as the steepest rise -> drop, "
                    "else spike. Unreliable on a window holding a rise and a fall of similar size: it called 50 of the "
                    "410 seed drops spikes (their snippets carry minutes of context)"}[polarity]
                                     + (" · upstream_inverted: the chain inverted the signal, so the reported "
                                        "polarity and every slope are flipped back" if upstream_inverted else "")},
        {"name": "steepest", "rule": "the most negative sample of np.gradient over the window, on the oriented trace"},
        {"name": "extremum", "rule": f"the lowest sample between the steepest and the knee (detect.find_trough: "
                                     f"three samples shallower than {knee_frac:g} x the steepest)"},
        {"name": "anchors", "rule": anchors_used or "the anatomy rules below, on every event"},
        {"name": "onset", "rule": "detect5.refine_onset (the same knee read backwards from the steepest)"
                                  + (", then detect5.walk_back_to_shoulder to the local maximum, bounded by the window start"
                                     if walk_onset_back else "; no walk back to the shoulder")},
        {"name": "event_amplitude", "rule": "|x[onset] - x[extremum]|: a drop's depth, a spike's height"},
        {"name": "precursor_height", "rule": "x[onset] against the far side of the window before it: a drop's rise, "
                                             "a spike's dip (not detect5's rise_height, which is 0 unless rise-triggered)"},
        {"name": "event_width", "rule": "onset -> extremum, s (for a drop, detect5's fall_duration_s)"},
        {"name": "recovery", "rule": f"first return to extremum + {recovery_frac:g} x amplitude after the extremum, "
                                     "interpolated; searched past the window end but not into the next event's window, "
                                     f"and at most {recovery_max_mult:g} event widths; not reached -> NaN"},
        {"name": "recovery_time", "rule": "extremum -> recovery, s"},
        {"name": "duration", "rule": "onset -> recovery, s"},
        {"name": "fwhm", "rule": "full width at half maximum: the half level is onset level - amplitude/2; the last "
                                 "crossing on the way out to the first on the way back, interpolated (not "
                                 "data_analysis.half_width, which is the narrower half of the most prominent peak, in samples)"},
        {"name": "max_slope", "rule": "steepest np.gradient * fs over [onset, extremum], mV/s (gradients.fall_gradients); "
                                      "negative for a drop, positive for a spike"},
        {"name": "onset_slope", "rule": "np.gradient * fs at the onset sample, mV/s"},
        {"name": "chord_slope", "rule": "(x[extremum] - x[onset]) / event_width, mV/s"},
        {"name": "peakedness", "rule": "max_slope / chord_slope: 1.0 is a linear fall, larger is front-loaded"},
        {"name": "span_ptp", "rule": "peak-to-peak over the whole window, mV (the denominator of detect5's fall_dominance)"},
        {"name": "units", "rule": unit},
    ]


def _crossing_down(z, start, stop, level):
    """Fractional index of the LAST sample at or above `level` in [start, stop],
    interpolated towards the next sample. None if none is."""
    seg = z[start:stop + 1]
    above = np.flatnonzero(seg >= level)
    if above.size == 0:
        return None
    i = start + int(above[-1])
    if i >= stop or z[i] == z[i + 1]:
        return float(i)
    return float(i + (z[i] - level) / (z[i] - z[i + 1]))


def _crossing_up(z, start, stop, level):
    """Fractional index of the FIRST sample at or above `level` in (start, stop),
    interpolated back from it. None if none is."""
    if stop <= start + 1:
        return None
    seg = z[start + 1:stop]
    hit = np.flatnonzero(seg >= level)
    if hit.size == 0:
        return None
    j = start + 1 + int(hit[0])
    if z[j] == z[j - 1]:
        return float(j)
    return float(j - 1 + (level - z[j - 1]) / (z[j] - z[j - 1]))


def _is_drop(segment, polarity):
    """`auto`: the event is the window's FASTEST edge — a drop when the steepest
    fall is at least as steep as the steepest rise, a spike otherwise.

    Not `library.grouping.bases.polarity` (excursion below the median against
    above it), which was tried first and fails on the commonest drop there is: a
    sharkfin window holds a slow rise and a fast fall of about the same height,
    so the median sits mid-rise and the two excursions tie — measured, a third of
    a synthetic sharkfin train came out as spikes. What makes a drop a drop here
    is the speed of the fall, so that is what decides.
    """
    if polarity == "drop":
        return True
    if polarity == "spike":
        return False
    if polarity != "auto":
        raise ValueError(f"polarity must be one of {POLARITIES}, got {polarity!r}")
    seg = np.asarray(segment, dtype=float)
    seg = seg[np.isfinite(seg)]
    if seg.size < 3:
        return True
    d = np.gradient(seg)
    return bool(-d.min() >= d.max())


def measure_event(z, lo, hi, search_end, fs, *, knee_frac=KNEE_FRAC, recovery_frac=RECOVERY_FRAC,
                  recovery_max_mult=RECOVERY_MAX_MULT, walk_onset_back=True, anchor=None):
    """The anatomy and measures of one ORIENTED event (a fall) in mV.

    `z` is the oriented trace in mV over at least `[lo, search_end)`; the event
    window is `[lo, hi)`. `anchor = (onset, extremum)`, relative to `lo`, skips
    the anatomy search: a detector that located the event already said where it
    is (see `measure_events`). Returns a dict in the oriented frame (slopes
    negative) with indices relative to `lo`, and `ok = False` when there is no fall.
    """
    fs = float(fs)
    w = z[lo:hi]
    out = {"ok": False}
    if w.size < 3 or not np.all(np.isfinite(w)):
        out["why"] = "too_short" if w.size < 3 else "non_finite"
        return out
    if anchor is not None:
        onset, extremum = int(anchor[0]), int(anchor[1])
        if not (0 <= onset < extremum < len(w)):
            out["why"] = "anchor_outside_window"
            return out
    else:
        der = np.gradient(w)
        steepest = int(np.argmin(der))
        if der[steepest] >= 0:
            out["why"] = "no_fall"
            return out
        knee = int(find_trough(der, 0, len(w), knee_frac=knee_frac))
        knee = max(knee, steepest)
        extremum = steepest + int(np.argmin(w[steepest:knee + 1]))
        onset = int(refine_onset(der, 0, knee, knee_frac=knee_frac))
        if walk_onset_back:
            onset = int(walk_back_to_shoulder(w, onset, backstop=0))
    depth = float(w[onset] - w[extremum]) if extremum > onset else 0.0
    if depth <= 0:
        out["why"] = "no_fall"
        return out

    grads = fall_gradients(w, fs, onset, extremum)
    width = extremum - onset
    limit = int(min(search_end, lo + extremum + recovery_max_mult * max(width, 1) + 1, len(z)))
    ext_abs = lo + extremum
    half = float(w[onset]) - depth / 2.0
    left = _crossing_down(z, lo + onset, ext_abs, half)
    right = _crossing_up(z, ext_abs, limit, half)
    rec = _crossing_up(z, ext_abs, limit, float(w[extremum]) + recovery_frac * depth)
    nan = float("nan")
    out.update(
        ok=True, onset=onset, extremum=extremum, depth=depth,
        recovery=(rec - lo) if rec is not None else nan,
        precursor=float(w[onset] - np.min(w[:onset + 1])),
        event_width_s=width / fs,
        fwhm_s=(right - left) / fs if (left is not None and right is not None) else nan,
        recovery_time_s=(rec - ext_abs) / fs if rec is not None else nan,
        duration_s=(rec - (lo + onset)) / fs if rec is not None else nan,
        span_ptp=float(np.ptp(w)),
        **grads,
    )
    return out


def measure_events(x, starts, ends, fs, *, polarity="drop", upstream_inverted=False, knee_frac=KNEE_FRAC,
                   recovery_frac=RECOVERY_FRAC, recovery_max_mult=RECOVERY_MAX_MULT, walk_onset_back=True,
                   to_mv=TO_MV_FROM_VOLTS, anchors=None):
    """Measure every window `[starts[i], ends[i])` of `x`.

    `anchors`, when given, is one `(onset, extremum)` per window in `x`'s frame
    (or None for a window without one): where a detector located the event, its
    own onset and trough ARE the event's definition and the measures are taken
    from them; the anatomy rules above are for spans nobody anatomised.

    Returns `(features, detail)`: `features` is a DataFrame with one row per
    window in input order and `COLUMNS` as its columns (recorded frame, indices
    in `x`'s frame); `detail` carries per-event orientation and the oriented
    snippet each measure was taken on, for the rose, plus the counts.
    """
    x = np.asarray(x, dtype=float).ravel()
    starts = [int(s) for s in starts]
    ends = [int(e) for e in ends]
    n = len(x)
    order = sorted(range(len(starts)), key=lambda i: (starts[i], ends[i]))
    next_start = {}
    for k, i in enumerate(order):
        later = [starts[j] for j in order[k + 1:] if starts[j] > starts[i]]
        next_start[i] = min(later) if later else n
    flip = -1.0 if upstream_inverted else 1.0

    rows, events = [], []
    counts = {"n_no_fall": 0, "n_not_recovered": 0, "n_no_fwhm": 0}
    for i, (lo, hi) in enumerate(zip(starts, ends)):
        lo_c, hi_c = max(0, lo), min(n, hi)
        drop = _is_drop(x[lo_c:hi_c], polarity)
        orient = 1.0 if drop else -1.0
        # the oriented trace from the window start to where the recovery search must stop:
        # O(total) over all events, since each reaches at most the next one's start
        search_end = min(n, max(hi_c, next_start[i]))
        z = orient * x[lo_c:search_end] * to_mv
        a = anchors[i] if anchors is not None else None
        if a is not None and (a[0] is None or a[1] is None or not (np.isfinite(a[0]) and np.isfinite(a[1]))):
            a = None
        m = measure_event(z, 0, hi_c - lo_c, search_end - lo_c, fs, knee_frac=knee_frac,
                          recovery_frac=recovery_frac, recovery_max_mult=recovery_max_mult,
                          walk_onset_back=walk_onset_back,
                          anchor=None if a is None else (int(a[0]) - lo_c, int(a[1]) - lo_c))
        recorded = (DROP if drop else SPIKE) * (-1 if upstream_inverted else 1)
        row = dict(UNLIT, polarity=recorded)
        if not m["ok"]:
            counts["n_no_fall"] += 1
            row["span_ptp_mv"] = float(np.ptp(x[lo_c:hi_c]) * abs(to_mv)) if hi_c > lo_c else float("nan")
            rows.append(row)
            events.append(None)
            continue
        sign = orient * flip           # oriented frame -> recorded frame, for signed quantities
        row.update(
            onset_idx=float(lo_c + m["onset"]), extremum_idx=float(lo_c + m["extremum"]),
            recovery_idx=float(lo_c + m["recovery"]) if np.isfinite(m["recovery"]) else float("nan"),
            event_amplitude_mv=m["depth"], precursor_height_mv=m["precursor"],
            event_width_s=m["event_width_s"], duration_s=m["duration_s"], fwhm_s=m["fwhm_s"],
            recovery_time_s=m["recovery_time_s"],
            max_slope_mv_s=sign * m["max_slope_mv_s"], onset_slope_mv_s=sign * m["onset_slope_mv_s"],
            chord_slope_mv_s=sign * m["mean_slope_mv_s"], peakedness=m["peakedness"], span_ptp_mv=m["span_ptp"],
        )
        counts["n_not_recovered"] += int(not np.isfinite(m["recovery_time_s"]))
        counts["n_no_fwhm"] += int(not np.isfinite(m["fwhm_s"]))
        rows.append(row)
        events.append({"index": i, "snippet_mv": z[:hi_c - lo_c].copy(), "onset": m["onset"],
                       "extremum": m["extremum"], "depth": m["depth"], "width_s": m["event_width_s"],
                       "onset_s": (lo_c + m["onset"]) / float(fs)})
    features = pd.DataFrame(rows, columns=list(COLUMNS)) if rows else pd.DataFrame(columns=list(COLUMNS), dtype=float)
    features["polarity"] = features["polarity"].astype("int64") if len(features) else features["polarity"]
    return features, {"events": events, **counts}


def event_rose(detail, groups, fs, *, scale="raw", reference=DEFAULT_SLOPE_REF_MV_S):
    """`gradients.rose_data` over measured events, split by `groups` (one key per
    event, in input order). The oriented snippets are handed over, so every rose
    lives in the falling quadrant whatever the polarity — a spike's steepest rise
    is drawn as its mirror — and the angle is taken on exactly the slope the
    feature table reports (the same onset and extremum)."""
    if scale not in SLOPE_SCALES:
        raise ValueError(f"rose scale must be one of {SLOPE_SCALES}, got {scale!r}")
    evs, snips, index = [], {}, []
    for ev in detail["events"]:
        if ev is None:
            continue
        key = str(ev["index"])
        evs.append({"event_id": key, "snippet_start_idx": 0, "onset_idx": ev["onset"], "trough_idx": ev["extremum"],
                    "fs": float(fs), "span_key": str(groups[ev["index"]]), "span_label": str(groups[ev["index"]]),
                    "recording_id": 0, "source_file": "", "onset_h": ev["onset_s"] / 3600.0,
                    "drop_depth_mv": ev["depth"], "fall_duration_s": ev["width_s"]})
        snips[key] = {"detrended_mv": ev["snippet_mv"]}
        index.append(ev["index"])
    rd = rose_data(evs, snips, scale=scale, fixed=reference, field="max_slope_mv_s", split_by="span_key")
    return rose_payload(rd, index)


def _num(v):
    v = float(v)
    return v if np.isfinite(v) else None


def rose_payload(rd, event_index=None):
    """`rose_data`'s output as plain JSON: degrees, not radians; NaN as None; the
    per-event arrays dropped from the groups (they are in the event table)."""
    if not rd.get("n"):
        centres, counts, width = rose_histogram([])
        return {"n": 0, "counts": [int(c) for c in counts], "bin_centres_deg": np.rad2deg(centres).tolist(),
                "bin_width_deg": float(np.rad2deg(width)), "angles_deg": [], "event_index": [], "groups": {},
                "scale": rd.get("scale"), "field": rd.get("field"), "caption": rd.get("caption", ""),
                "mean_deg": None, "resultant_length": None, "circular_sd_deg": None, "uniformity_p": None}
    groups = {}
    for k, g in rd["groups"].items():
        groups[str(k)] = {"n": int(g["n"]), "counts": [int(c) for c in g["counts"]],
                          "mean_deg": _num(g["mean_deg"]), "resultant_length": _num(g["resultant_length"]),
                          "circular_sd_deg": _num(g["circular_sd_deg"]), "uniformity_p": _num(g["uniformity_p"]),
                          "median_slope_mv_s": _num(g["median_slope_mv_s"])}
    return {
        "n": int(rd["n"]), "counts": [int(c) for c in rd["counts"]],
        "bin_centres_deg": np.rad2deg(rd["bin_centres"]).tolist(), "bin_width_deg": float(np.rad2deg(rd["bin_width"])),
        "angles_deg": [float(a) for a in np.rad2deg(rd["angles"])],
        "event_index": list(event_index) if event_index is not None else list(range(int(rd["n"]))),
        "slopes_mv_s": [float(g[rd["field"]]) for g in rd["gradients"]],
        "groups": groups, "scale": rd["scale"], "field": rd["field"], "caption": rd["caption"],
        "mean_deg": _num(rd["mean_deg"]), "resultant_length": _num(rd["resultant_length"]),
        "circular_sd_deg": _num(rd["circular_sd_deg"]), "uniformity_p": _num(rd["uniformity_p"]),
        "note": "polarity-neutral: every event is drawn oriented as a fall, so a spike's steepest rise is its mirror",
    }
