"""
whole_drop.py
=============
Drop EVENTS of a span, and the WHOLE DROP of each - separate drops are never joined (researcher, 2026-11-23;
the rule approved on `docs/library_analysis/20261123/whole_drop_vs_steep_core.png`).

In plain words: `Working.interrogation.event_shape` measures a fall's STEEP CORE - from the steepest point to the
"knee", where the slope has eased to 5 % of it. That is the drop detector's own definition and right for detector
events (93-99.6 % of the 3,511 `drop_motifs10` troughs). A person who accepts a span is looking at the whole descent:
from the highest point a drop falls from to the lowest point it reaches. But a span can hold more than one drop, and
those must stay separate (the researcher, reviewing the first diagram: a slow decline followed by a sharp drop is two
drops; a staircase is two; four falls separated by small rebounds are four).

So a DROP EVENT is one unbroken stretch of falling: it ends at a pause (the trace goes flat) or a rebound (it climbs
back), and the next fall after that is the next event. A steep start with a slow tail is one event, its whole drop
running to the bottom of the tail; a rounded shoulder easing into a steep fall is one event too. (A first version
also split where a fall sped up again; it cut single smooth falls into pieces - MJu26a CH15's 45 mV fall into three -
and every case the researcher marked is already separated by a pause or a rebound, so that rule was dropped.)

The rule, on one window of one channel (measured as drops; `polarity="spike"` measures rises the same way):

    smoothed copy   Gaussian of max(1 sample, SMOOTH_S): sample noise out, shape kept
    noise           sigma = robust spread (MAD x 1.4826) of the raw sample-to-sample differences / sqrt 2
    pieces          the smoothed copy as straight pieces: Ramer-Douglas-Peucker on the vertical distance, split
                    wherever the trace strays more than EPS_SIGMAS x sigma from a straight line
    a piece         FALLS when it drops by more than that tolerance, is FLAT when it moves less, RISES when it climbs
    an event        consecutive falling pieces; a flat or rising piece ends it. Shallower than MIN_DEPTH_SIGMAS x
                    sigma is noise, and shallower than MIN_REL_DEPTH of the span's deepest event is a wiggle on it:
                    neither is an event (the researcher's smallest marked event was ~17 % of its span's deepest)
    top / bottom    the raw highest / lowest sample within one smoothing width of the event's first / last breakpoint
    depth           raw[top] - raw[bottom], mV;  fall time: bottom - top, s
    half recovery   the first return to raw[bottom] + 0.5 x depth after the bottom, interpolated; never searched into
                    the next event (or past `next_start`), at most RECOVERY_MAX_MULT fall times and RECOVERY_MAX_S.
                    Not reached -> NaN;  width: top -> half recovery, s
    a span's event  every event at least half of whose DEPTH falls inside the span counts (`n_events`) - by depth,
                    not time, because a slow tail can outlast its span many times. The MAIN event is the deepest. The window is read with one span length of context
                    each side, so a fall that began before the span (MJu26a CH15's machine train windows start
                    mid-fall) keeps its real top, and a tail that runs past the span its real bottom
    rise_dominated  the window's fastest edge, on the smoothed copy, is a rise (6 % of accepted spans): flagged, not
                    silently flipped

Used by the Library analysis (`scripts/library_analysis`), the sequence queues and Auto-detect, so a
candidate's box and the Library's measure are one rule. `event_shape` (the steep core) is unchanged.

No plotting library - CLAUDE.md rule 1. numpy + scipy.
"""
from __future__ import annotations

import numpy as np

SMOOTH_S = 0.5
EPS_SIGMAS = 4.0
MIN_DEPTH_SIGMAS = 6.0
MIN_REL_DEPTH = 0.15
RECOVERY_FRAC = 0.5
RECOVERY_MAX_MULT = 10.0
RECOVERY_MAX_S = 7200.0
CONTEXT_MAX_S = 7200.0


def smoothed(x, fs):
    """Gaussian of max(1 sample, SMOOTH_S): the copy the pieces are fitted to."""
    from scipy.ndimage import gaussian_filter1d
    return gaussian_filter1d(np.asarray(x, dtype=float), max(1.0, SMOOTH_S * float(fs)), mode="nearest")


def noise_sigma(raw):
    """Robust sample-to-sample noise: MAD of the first differences x 1.4826 / sqrt 2."""
    d = np.diff(np.asarray(raw, dtype=float))
    d = d[np.isfinite(d)]
    if d.size < 3:
        return 0.0
    return float(1.4826 * np.median(np.abs(d - np.median(d))) / np.sqrt(2.0))


def is_drop(x, fs):
    """The window's fastest edge on the smoothed copy: a drop when its steepest fall is at least as steep as its
    steepest rise."""
    d = np.gradient(smoothed(x, fs))
    return bool(-d.min() >= d.max())


def breakpoints(y, eps):
    """Ramer-Douglas-Peucker on the vertical distance: indices where `y` is split into straight pieces, each
    within `eps` of its chord. Always holds the first and last index."""
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < 3:
        return np.arange(n)
    keep = np.zeros(n, dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        seg = y[i:j + 1]
        line = y[i] + (y[j] - y[i]) * np.arange(j - i + 1) / (j - i)
        dev = np.abs(seg - line)
        k = int(np.argmax(dev))
        if dev[k] > eps:
            m = i + k
            keep[m] = True
            stack.append((i, m))
            stack.append((m, j))
    return np.flatnonzero(keep)


def falls(y, eps):
    """`[(first, last)]` breakpoint pairs of the unbroken falls of `y`: runs of falling pieces, ended by a flat or
    rising one."""
    bp = breakpoints(y, eps)
    out, cur = [], None
    for i, j in zip(bp[:-1], bp[1:]):
        if y[j] - y[i] >= -eps:                      # flat or rising: the fall (if any) ends
            if cur is not None:
                out.append(cur)
                cur = None
            continue
        cur = (i, j) if cur is None else (cur[0], j)
    if cur is not None:
        out.append(cur)
    return out


def _crossing_up(z, start, stop, level):
    """Fractional index of the first sample at or above `level` in (start, stop), interpolated back; None if none."""
    if stop <= start + 1:
        return None
    hit = np.flatnonzero(z[start + 1:stop] >= level)
    if hit.size == 0:
        return None
    j = start + 1 + int(hit[0])
    if z[j] == z[j - 1]:
        return float(j)
    return float(j - 1 + (level - z[j - 1]) / (z[j] - z[j - 1]))


def candidate_falls(z, fs, sigma):
    """`[(top, bottom, depth)]` - the unbroken falls of the ORIENTED trace `z` (mV, a fall is a fall) deeper than
    the noise floor, as indices into `z`, in order. The relative floor is the caller's (it needs the span)."""
    fs = float(fs)
    z = np.asarray(z, dtype=float)
    eps = max(EPS_SIGMAS * sigma, 1e-9)
    k = max(1, int(round(SMOOTH_S * fs)))
    out = []
    for first, last in falls(smoothed(z, fs), eps):
        t0, t1 = max(0, first - k), min(len(z), first + k + 1)
        top = t0 + int(np.nanargmax(z[t0:t1]))
        b0, b1 = max(top + 1, last - k), min(len(z), last + k + 1)
        if b1 <= b0:
            continue
        bottom = b0 + int(np.nanargmin(z[b0:b1]))
        depth = float(z[top] - z[bottom])
        if depth > 0 and depth >= MIN_DEPTH_SIGMAS * sigma:
            out.append((int(top), int(bottom), depth))
    return out


def with_recoveries(z, fs, kept, *, hard_bound=None):
    """Event dicts for `kept` falls (ordered), each with its half recovery searched up to the next kept fall's top,
    at most RECOVERY_MAX_MULT fall times / RECOVERY_MAX_S, and never past `hard_bound` (beyond its bottom)."""
    fs = float(fs)
    out = []
    for n, (top, bottom, depth) in enumerate(kept):
        fall_n = bottom - top
        limit = bottom + int(min(RECOVERY_MAX_MULT * max(fall_n, 1), RECOVERY_MAX_S * fs)) + 1
        if n + 1 < len(kept):
            limit = min(limit, kept[n + 1][0] + 1)
        if hard_bound is not None and hard_bound > bottom:
            limit = min(limit, int(hard_bound))
        limit = min(limit, len(z))
        rec = _crossing_up(z, bottom, limit, float(z[bottom]) + RECOVERY_FRAC * depth)
        out.append({"top": top, "bottom": bottom, "recovery": rec if rec is not None else float("nan"),
                    "recovery_bound": int(limit), "depth_mv": depth, "fall_s": fall_n / fs,
                    "half_recovery_s": (rec - bottom) / fs if rec is not None else float("nan"),
                    "width_s": (rec - top) / fs if rec is not None else float("nan")})
    return out


def _frame(e, lo):
    return {"top_idx": e["top"] + lo, "bottom_idx": e["bottom"] + lo,
            "recovery_idx": e["recovery"] + lo if np.isfinite(e["recovery"]) else float("nan"),
            "depth_mv": e["depth_mv"], "fall_s": e["fall_s"], "half_recovery_s": e["half_recovery_s"],
            "width_s": e["width_s"]}


def measure(x, a, b, fs, *, to_mv=1000.0, next_start=None, polarity="drop"):
    """The drop events of window [a, b) of channel `x` (recording samples, any unit; `to_mv` turns it into mV), read
    with one span length of context each side (at most CONTEXT_MAX_S), and the span's MAIN event (the deepest lying
    mostly inside it).

    Returns a dict: the main event's recording-frame `top_idx`, `bottom_idx`, `recovery_idx`, `depth_mv`, `fall_s`,
    `half_recovery_s`, `width_s`; `top_extended` / `bottom_extended` (it reaches past the span's edge);
    `n_events` and `events` (every event mostly inside the span, recording frame, in order); `rise_dominated`;
    `polarity` (-1 drop, +1 spike); and `ok`.
    """
    if polarity not in ("drop", "spike", "auto"):
        raise ValueError(f"polarity must be drop, spike or auto, got {polarity!r}")
    fs = float(fs)
    n = len(x)
    a, b = max(0, int(a)), min(n, int(b))
    out = {"ok": False}
    if b - a < 4:
        out["why"] = "too_short"
        return out
    pad = int(min(b - a, CONTEXT_MAX_S * fs))
    lo, hi = max(0, a - pad), min(n, b + pad)
    rec_hi = min(n, hi + int(RECOVERY_MAX_S * fs))
    raw = np.asarray(x[lo:rec_hi], dtype=float) * to_mv
    inside = raw[a - lo:b - lo]
    if not np.all(np.isfinite(inside)):
        out["why"] = "non_finite"
        return out
    falls_fastest = is_drop(inside, fs)
    drop = falls_fastest if polarity == "auto" else polarity == "drop"
    z = raw if drop else -raw
    if not np.all(np.isfinite(z)):
        z = np.where(np.isfinite(z), z, np.nanmedian(z))
    out.update(polarity=-1 if drop else 1, rise_dominated=not falls_fastest)
    found = candidate_falls(z[:hi - lo], fs, noise_sigma(inside))
    a_l, b_l = a - lo, b - lo

    def mostly_inside(f):
        # at least half its DEPTH falls inside the span. By depth, not time: a fall's slow tail can outlast the span
        # many times over while its drop happens inside it (132 spans were lost to a time rule); a span drawn round
        # the start of a long fall (SH CH2, the researcher's correction) holds that fall; a fall that began before a
        # span (MJu26a CH15's train windows) is held by the span it mostly falls in; a neighbour that merely begins
        # in the span's last moments is not
        i, j = max(f[0], a_l), min(f[1], b_l)
        if j <= i:
            return False
        return float(z[i] - np.min(z[i:j + 1])) >= 0.5 * f[2]

    inside_falls = [f for f in found if mostly_inside(f)]
    if not inside_falls:
        out.update(why="no_fall", n_events=0, events=[])
        return out
    floor = MIN_REL_DEPTH * max(f[2] for f in inside_falls)
    kept = [f for f in found if f[2] >= floor]
    bound = None if next_start is None else int(next_start) - lo
    events = [e for e in with_recoveries(z, fs, kept, hard_bound=bound)
              if mostly_inside((e["top"], e["bottom"], e["depth_mv"]))]
    main = max(events, key=lambda e: e["depth_mv"])
    out.update(ok=True, **_frame(main, lo), top_extended=main["top"] < a_l, bottom_extended=main["bottom"] >= b_l,
               n_events=len(events), events=[_frame(e, lo) for e in events])
    return out


def span_events(x, a, b, fs, *, to_mv=1000.0, polarity="drop"):
    """Every drop event inside a long span (a sequence), without context padding: recording-frame dicts, with the
    relative floor taken against the span's own deepest event."""
    a, b = max(0, int(a)), min(len(x), int(b))
    raw = np.asarray(x[a:b], dtype=float) * to_mv
    z = raw if polarity == "drop" else -raw
    z = np.where(np.isfinite(z), z, np.nanmedian(z))
    found = candidate_falls(z, fs, noise_sigma(z))
    if not found:
        return []
    floor = MIN_REL_DEPTH * max(f[2] for f in found)
    return [_frame(e, a) for e in with_recoveries(z, fs, [f for f in found if f[2] >= floor])]
