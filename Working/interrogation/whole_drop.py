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

So a DROP EVENT is one unbroken stretch of falling: it ends at a pause (the trace stops reaching new lows) or a
rebound (it climbs back), and the next fall after that is the next event. A brief HESITATION is not a pause: a
flat bit short against the drop it interrupts, after which the fall carries on, stays inside the event; and wiggles
that only fall back to where the drop had already been do not carry it on (Auto-detect's checks, 23 Nov, on a quiet
channel - M4 CH1, sigma 0.034 mV: a 50 mV decline the researcher circled as one drop, 281:25-282:45 h, came out in
four, and once joined it ran on for an hour of wiggles and drift). A steep start with a slow tail is one event, its
whole drop running to the bottom of the tail; a rounded shoulder easing into a steep fall is one event too. (A first
version also split where a fall sped up again; it cut single smooth falls into pieces - MJu26a CH15's 45 mV fall
into three - and every case the researcher marked is already separated by a pause or a rebound, so that rule was
dropped.)

The rule, on one window of one channel (measured as drops; `polarity="spike"` measures rises the same way):

    smoothed copy   Gaussian of max(1 sample, SMOOTH_S): sample noise out, shape kept
    noise           sigma = robust spread (MAD x 1.4826) of the raw sample-to-sample differences / sqrt 2, read
                    over a fixed NOISE_HALF_S each side of the window's centre (or the window, if longer), so one
                    fall gives one answer whatever box it is measured in
    pieces          the smoothed copy as straight pieces: Ramer-Douglas-Peucker on the vertical distance, split
                    wherever the trace strays more than EPS_SIGMAS x sigma from a straight line
    a piece         FALLS when it drops by more than that tolerance, is FLAT when it moves less, RISES when it climbs
    an event        falling pieces that take the trace to NEW LOWS (more than the tolerance below the event's lowest
                    point so far). Three things end it:
                    - a REBOUND: the trace climbs back off that low by REBOUND_FRAC of the depth so far (the
                      researcher's four rebound-separated falls rose back 25-33 %) or by REBOUND_SIGMAS noise-widths,
                      whichever is less - so a quiet channel's 1 % wiggles do not end a drop, a clear climb ends any;
                    - a PAUSE: a STALL (time without a new low: flat pieces, small rises, falls that only wiggle back
                      down to where the event had already been) at least PAUSE_MIN_S long and at least PAUSE_FRAC of
                      the event's duration so far, in which the trace has stopped descending (`_flat`; a slow tail
                      creeping down through noise is still the drop), or at least HESITATION_FRAC of it with the next
                      fall SPEEDUP_AFTER_PAUSE x faster than the event's own pace (the researcher's slow decline, a
                      230 s pause, then a sharp drop: two events). Shorter, it is a hesitation and the event carries
                      on. A stall that ends in a slow creep, not a sharp fall, is a pause only if it lasts at least
                      PAUSE_MIN_S: one noise-flat second right after a 3 s fall was 15 % of the event so far, and a
                      sharp fall's slow settle came out as a second event (Auto-detect's drop B). A quick staircase -
                      a short flat ended by a fall as sharp as the first (LM 4486f15d, 10-20 s) - still pauses;
                    - an ONSET (`_onset`): a fall ONSET_CONTRAST x faster than the slow stretch before it - a slow
                      decline running into a sharp drop, or a drop's tail, slowed to a fifth of its own steep part,
                      running into a second one - that falls at least MIN_REL_DEPTH of the event's depth so far. A
                      slow decline shallower than LEAD_MERGE_FRAC of the drop it runs into is that drop's shoulder
                      and stays in it.
                    A drop on a SLIDE (`_on_slide`) - the trace fell steadily over the MIN_CONTEXT_S before its steep
                    part, and falls on at about that pace once the drop is over (within SLIDE_RATIO) - is the STEP
                    alone: from where its pace rises above SLIDE_MULT x the slide's to where it is back within it.
                    The slide before and after it are events of their own (the researcher, 23 Nov: a step on a
                    slide is the step - LM 99f61fa6, 725bbdbe). A drop with nothing sliding before it keeps its
                    whole tail, to its bottom (M4 CH1's 80-minute tail, which the researcher circled as the drop).
                    Shallower than MIN_DEPTH_SIGMAS x sigma is noise, and shallower than MIN_REL_DEPTH of the span's
                    deepest event is a wiggle on it: neither is an event (the researcher's smallest marked event was
                    ~17 % of its span's deepest)
    top / bottom    from the HIGHEST point of the smoothed copy over the event (a hesitation that rose slightly moves
                    the top onto the real shoulder): the bottom is where the fall first ARRIVES within one
                    noise-width (sigma) of its lowest level, the top the last point before it still within sigma of
                    the highest - the lowest single sample of a slow tail's flat end is decided by noise, the
                    arrival is not - each refined to the raw highest / lowest sample within one smoothing width
    depth           raw[top] - raw[bottom], mV;  fall time: bottom - top, s;  steep_s: top -> the end of its steep
                    part (falling at least 1/ONSET_CONTRAST as fast as its steepest), s;  long_tail: the fall time is
                    over LONG_TAIL_MULT x steep_s - a tail the Library can leave out of a plot (the researcher,
                    23 Nov: long tails are kept, and flagged)
    half recovery   the first return to raw[bottom] + 0.5 x depth after the bottom, interpolated; never searched into
                    the next event (or past `next_start`), and at most RECOVERY_MAX_S. Not reached -> NaN;  width:
                    top -> half recovery, s. (A cap of ten fall times, dropped 23 Nov, cost a sharp fall its slow
                    recovery: one sample more fall time decided whether a shark fin had a width at all.)
    a span's event  every event at least half of whose DEPTH falls inside the span counts (`n_events`) - by depth,
                    not time, because a slow tail can outlast its span many times - and every event whose STEEPEST
                    moment (`_steepest`) the span holds, so a sharp drop whose tail runs on for an hour is the event
                    of the span drawn round the drop. The MAIN event is the deepest -
                    or, given an `anchor` (a machine box naming the moment it is about), the event there, with the
                    relative floor taken against it. The window is read with one span length of context each side
                    (at least MIN_CONTEXT_S; a read that cuts one of the span's events is widened, up to
                    CONTEXT_MAX_S), so a fall that began before the span (MJu26a CH15's machine train windows start
                    mid-fall) keeps its real top, and a tail that runs past the span its real bottom. `span_events`
                    lists a long span's events the same way
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
RECOVERY_MAX_S = 7200.0
CONTEXT_MAX_S = 7200.0
MIN_CONTEXT_S = 600.0
NOISE_HALF_S = 1800.0
PAUSE_FRAC = 0.15
PAUSE_MIN_S = 30.0
HESITATION_FRAC = 0.05
SPEEDUP_AFTER_PAUSE = 5.0
REBOUND_FRAC = 0.10
REBOUND_SIGMAS = 10.0
ONSET_CONTRAST = 5.0
ONSET_SLOW_MULT = 10.0
ONSET_MIN_HISTORY = 3.0
LEAD_MERGE_FRAC = 0.35
SLIDE_RATIO = 3.0
SLIDE_MULT = 1.5
SLIDE_STEADY = 1.5
LONG_TAIL_MULT = 10.0
STEEPEST_SMOOTH_MAX_S = 60.0


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


def falls(y, eps, fs=1.0):
    """`[(first, last)]` breakpoint pairs of the drop events of `y`: runs of falls to new lows that a REBOUND or a
    PAUSE ends, and a brief hesitation does not (see the module rule). `last` is always the event's lowest
    breakpoint so far."""
    bp = breakpoints(y, eps)
    rebound_abs = eps * REBOUND_SIGMAS / EPS_SIGMAS
    min_pause = max(1.0, PAUSE_MIN_S * float(fs))
    out, lead = [], {}                                    # lead: events begun at a lead-in's onset -> run length
    first = last = None
    prog = []                                             # the event's falls to new lows: (start, end, pace)
    for i, j in zip(bp[:-1], bp[1:]):
        pace = (y[i] - y[j]) / max(j - i, 1)
        if first is None:
            if y[j] - y[i] < -eps:                        # the first falling piece starts an event
                first, last, prog = i, j, [(i, j, pace)]
            continue
        depth = y[first] - y[last]
        # a REBOUND ends the event: the trace climbs back off its low by REBOUND_FRAC of the depth so far, or by
        # REBOUND_SIGMAS noise-widths, whichever is less. A smaller climb (M4 CH1: 0.14-0.28 mV, 4-8 sigma, ~1 % of
        # its drop, cut it into pieces) is part of a hesitation; a clear one ends even a very deep drop (M2_aug
        # cf7ceb24: after a 105 mV artifact spike nothing short of 10 mV ended it, and it swallowed the real drop)
        if y[j] - y[last] >= max(eps, min(REBOUND_FRAC * depth, rebound_abs)):
            out.append((first, last))
            first = last = None
            continue
        # PROGRESS is a fall to a NEW LOW. Anything else - flat, a small rise, a fall that only wiggles back down to
        # where the event had already been - is a stall, and the event's low stays where it was
        if not (y[j] - y[i] < -eps and y[j] < y[last] - eps):
            continue
        run, dur = i - last, max(last - first, 1)
        sharp = pace * ONSET_CONTRAST >= max(p for _, _, p in prog)      # the stall ends in a sharp fall
        if run > 0 and (run >= min_pause or sharp) and ((run >= PAUSE_FRAC * dur and _flat(y, last, i, eps))
                        or (run >= HESITATION_FRAC * dur and pace >= SPEEDUP_AFTER_PAUSE * depth / dur)):
            out.append((first, last))                     # the stall was a pause: the next drop begins
            first, prog = i, []
        else:
            got = _onset(y, prog, i, j, pace, first)
            if got is not None:                           # a sharp fall out of a long slow stretch: a new drop
                r, after_lead_in, _ = got
                out.append((first, prog[r - 1][1]))
                if after_lead_in:
                    lead[len(out)] = True
                first, prog = prog[r][0] if r < len(prog) else i, prog[r:]
        last = j
        prog.append((i, j, pace))
    if first is not None:
        out.append((first, last))
    # a lead-in shallower than LEAD_MERGE_FRAC of the drop it ran into is that drop's shoulder, not a drop of its own
    # (the researcher's approved diagram: SO CH2's 0.26 mV lead-in to a 1.5 mV fall, 17 %, and the first of the four
    # rebound-separated falls, 28 %, are one event each; the slow declines that are drops of their own run 42-200 %
    # of the drop after them)
    # (a slide the drop sits on is taken apart afterwards, `_on_slide`)
    merged = []
    for n, (f, l) in enumerate(out):
        shoulder = n in lead and merged and merged[-1][1] <= f
        if shoulder and y[merged[-1][0]] - y[merged[-1][1]] < LEAD_MERGE_FRAC * (y[f] - y[l]):
            merged[-1] = (merged[-1][0], l)
        else:
            merged.append((f, l))
    return merged


def _same_pace(late, ref):
    """True when `late` falls at the pace `ref` did, within SLIDE_RATIO either way (and `ref` was falling)."""
    return ref > 0 and ref / SLIDE_RATIO <= late <= ref * SLIDE_RATIO


def _late_pace(y, first, last):
    """The net pace over the last third of [first, last], after its steep run: how fast it falls once it is over."""
    r1 = _steep_run(y, first, last)[1]
    third = max(1, (last - r1) // 3)
    return (y[last - third] - y[last]) / third if last - third > r1 else 0.0


def _steep_run(y, first, last):
    """`(start, end)` of the stretch round the fall's steepest moment (on `y`) falling at least 1/ONSET_CONTRAST as
    fast: its steep part."""
    if last - first < 2:
        return first, last
    g = -np.gradient(np.asarray(y[first:last + 1], dtype=float))
    peak = int(np.argmax(g))
    on = g >= g[peak] / ONSET_CONTRAST
    r0 = peak
    while r0 > 0 and on[r0 - 1]:
        r0 -= 1
    r1 = peak
    while r1 + 1 < len(g) and on[r1 + 1]:
        r1 += 1
    return first + r0, first + r1


def _on_slide(y, first, last, fs, sigma):
    """A drop on a SLIDE, taken apart: `[(first, last)]` pieces - the slide before the step (if the drop took it in as
    a shoulder), the step, the slide after it - or the drop whole.

    The trace was SLIDING before the drop when, over the MIN_CONTEXT_S before its steep part, it fell steadily: both
    halves of that stretch falling, within SLIDE_STEADY of each other's pace (a shoulder speeds up into its drop: M4
    CH1's eight minutes before its fall, 2.1x; a slide does not: LM 99f61fa6, 1.3x). It slides on after the drop when
    the drop's last third falls within SLIDE_RATIO of that pace, and goes on for at least half as long as the stretch
    before it (the last seconds of a fall before it turns back up are no slide: M4 62a49ab1). Then the drop is the
    STEP - if there is one: a steep part falling at least ONSET_CONTRAST x as fast as the slide, and more than the
    noise floor (a straight slow decline is no step on itself) - from where its pace first rises above SLIDE_MULT x
    the slide's to where it is back within it (the researcher, 23 Nov: a step on a slide is the step; the slide was
    already there). A drop with nothing sliding before it keeps its whole tail, to its bottom (M4 CH1's 80-minute
    tail, which the researcher circled as the drop)."""
    r0, r1 = _steep_run(y, first, last)
    p0 = max(0, r0 - int(MIN_CONTEXT_S * fs))
    if r0 - p0 < max(ONSET_MIN_HISTORY * max(r1 - r0, 1), 4):
        return [(first, last)]
    mid = (p0 + r0) // 2
    ref = (y[p0] - y[r0]) / (r0 - p0)
    halves = (y[p0] - y[mid]) / max(mid - p0, 1), (y[mid] - y[r0]) / max(r0 - mid, 1)
    if min(halves) <= 0 or max(halves) > SLIDE_STEADY * min(halves) or not _same_pace(_late_pace(y, first, last), ref):
        return [(first, last)]
    run_drop = y[r0] - y[r1]
    if run_drop < MIN_DEPTH_SIGMAS * sigma or run_drop / max(r1 - r0, 1) < ONSET_CONTRAST * ref:
        return [(first, last)]
    w = int(np.clip(ONSET_SLOW_MULT * max(r1 - r0, 1), 30.0 * fs, MIN_CONTEXT_S * fs))
    step = r0
    while step - w >= max(first, p0) and (y[step - w] - y[step]) / w > SLIDE_MULT * ref:
        step -= 1
    step = max(first, step)
    end = next((t for t in range(r1 + w, last) if (y[t - w] - y[t]) / w <= SLIDE_MULT * ref), None)
    if end is None or last - end < 0.5 * (r0 - p0):
        return [(first, last)]                            # nothing slides on after it for long
    return [piece for piece in ((first, step), (step, end), (end, last)) if piece[1] - piece[0] >= 2]


def _flat(y, i, j, eps):
    """True when the trace has stopped descending over [i, j]: its least-squares trend falls less than half the
    tolerance across it. A slow tail creeping down through noise (MJu26a b7b6e322: 0.55 mV over 12 minutes after a
    0.35 mV step) is still the drop; a pause - flat or turning up (M4 CH1 at 282:45) - is not."""
    seg = np.asarray(y[i:j + 1], dtype=float)
    if len(seg) < 3:
        return False                                      # too short to tell: not a pause
    t = np.arange(len(seg)) - (len(seg) - 1) / 2.0
    slope = float(np.dot(t, seg - seg.mean()) / np.dot(t, t))
    return -slope * (len(seg) - 1) < 0.5 * eps


def _onset(y, prog, i, j, pace, first):
    """ONSET: `(index in prog where a new drop begins, whether what it ends was a lead-in, the run's length)`, or
    None.

    The fall (i, j) and the falls just before it at least 1/ONSET_CONTRAST as steep are one STEEP RUN. Its pace (net
    descent over its length) is set against the SLOW STRETCH before it: back to the end of the event's last fall that
    steep (or the event's start), at most ONSET_SLOW_MULT and at least ONSET_MIN_HISTORY times the run's length. When
    the run is ONSET_CONTRAST x faster and has fallen at least MIN_REL_DEPTH of the event's depth before it, it is a
    new drop and the slow stretch the end of the earlier event:
      - after a drop's own steep part, a SECOND SHARP DROP after a stretch at most 1/ONSET_CONTRAST as fast as that
        part: a tail running into a second drop (M4 873cd70d, M2_aug d3ac70db, f238e01e). A drop still falling fast
        that speeds up again is one drop (M2_concat 082f06a6);
      - a slow decline running into a sharp drop (the researcher: two drops; separate drops are never joined). Such a
        lead-in under LEAD_MERGE_FRAC of the drop's depth is that drop's shoulder, and `falls` merges it back once the
        drop's depth is known (M4 CH1's six minutes before its 49 mV fall, SO CH2's 17 %, the researcher's first
        rebound-separated fall, 28 %).
    A wiggle in a near-flat tail is steep against the tail but shallow against the drop: not a new one.
    """
    floor = pace / ONSET_CONTRAST
    r = len(prog)
    while r > 0 and prog[r - 1][2] >= floor:              # the steep run: the falls just before this one
        r -= 1
    if r == 0:
        return None                                       # the event so far is all one steep run
    k = r
    while k > 0 and prog[k - 1][2] < floor:               # the slow stretch: back to the last fall that steep
        k -= 1
    run_start = prog[r][0] if r < len(prog) else i
    length = max(j - run_start, 1)
    w0 = max(first if k == 0 else prog[k - 1][1], run_start - int(ONSET_SLOW_MULT * length))
    if run_start - w0 < ONSET_MIN_HISTORY * length:
        return None                                       # too little before it to be a long slow stretch
    pre_pace = max(y[w0] - y[run_start], 0.0) / (run_start - w0)
    if (y[run_start] - y[j]) / length < ONSET_CONTRAST * pre_pace:
        return None
    if k > 0 and pre_pace * ONSET_CONTRAST > max(p for _, _, p in prog[:r]):
        return None                                       # still falling fast, not a tail: a drop speeding up
    before = y[first] - y[prog[r - 1][1]]                 # the event's depth before the run
    if y[run_start] - y[j] < MIN_REL_DEPTH * before:
        return None
    return r, k == 0, length


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
    """`[(top, bottom, depth, first, last, steep_end)]` - the drop events of the ORIENTED trace `z` (mV, a fall is a
    fall) deeper than the noise floor, as indices into `z`, in order; `first` / `last` are the event's first and last
    breakpoints (a `last` at the end of `z` means the fall was still running where the read ends); `steep_end` is
    where its steep part ends. A drop on a slide ends where the slide resumes, and the slide after it is an event of
    its own. The relative floor is the caller's (it needs the span)."""
    fs = float(fs)
    z = np.asarray(z, dtype=float)
    eps = max(EPS_SIGMAS * sigma, 1e-9)
    k = max(1, int(round(SMOOTH_S * fs)))
    out = []
    s = smoothed(z, fs)
    events = [piece for first, last in falls(s, eps, fs) for piece in _on_slide(s, first, last, fs, sigma)]
    for first, last in events:
        seg = s[first:last + 1]
        hi_at = int(np.argmax(seg))                               # the shoulder: the event's highest point ...
        lo_val = float(np.min(seg[hi_at:]))
        # ... and where it ARRIVES at its bottom: the first point within one noise-width of the lowest level, and the
        # last point before the fall still within one noise-width of the top. The lowest single sample of a slow
        # tail's near-flat end is decided by noise; the arrival is not (one fall, one bottom, whatever the window)
        arrive = hi_at + int(np.argmax(seg[hi_at:] <= lo_val + sigma))
        leave = int(np.flatnonzero(seg[:arrive + 1] >= seg[hi_at] - sigma)[-1])
        peak, low = first + leave, first + arrive
        t0, t1 = max(0, peak - k), min(len(z), peak + k + 1)
        top = t0 + int(np.nanargmax(z[t0:t1]))
        b0, b1 = max(top + 1, low - k), min(len(z), low + k + 1)
        if b1 <= b0:
            continue
        bottom = b0 + int(np.nanargmin(z[b0:b1]))
        depth = float(z[top] - z[bottom])
        if depth > 0 and depth >= MIN_DEPTH_SIGMAS * sigma:
            steep_end = _steep_run(s, top, bottom)[1]
            out.append((int(top), int(bottom), depth, int(first), int(last), int(steep_end)))
    return out


def with_recoveries(z, fs, kept, *, hard_bound=None):
    """Event dicts for `kept` falls (ordered), each with its half recovery searched up to the next kept fall's top,
    at most RECOVERY_MAX_S, and never past `hard_bound` (beyond its bottom)."""
    fs = float(fs)
    out = []
    for n, f in enumerate(kept):
        top, bottom, depth = f[0], f[1], f[2]
        fall_n = bottom - top
        limit = bottom + int(RECOVERY_MAX_S * fs) + 1
        if n + 1 < len(kept):
            limit = min(limit, kept[n + 1][0] + 1)
        if hard_bound is not None and hard_bound > bottom:
            limit = min(limit, int(hard_bound))
        limit = min(limit, len(z))
        rec = _crossing_up(z, bottom, limit, float(z[bottom]) + RECOVERY_FRAC * depth)
        steep_n = max((f[5] if len(f) > 5 else bottom) - top, 1)
        out.append({"top": top, "bottom": bottom, "first": f[3] if len(f) > 3 else top,
                    "last": f[4] if len(f) > 4 else bottom, "recovery": rec if rec is not None else float("nan"),
                    "steep_s": steep_n / fs, "long_tail": bool(fall_n > LONG_TAIL_MULT * steep_n),
                    "recovery_bound": int(limit), "depth_mv": depth, "fall_s": fall_n / fs,
                    "half_recovery_s": (rec - bottom) / fs if rec is not None else float("nan"),
                    "width_s": (rec - top) / fs if rec is not None else float("nan")})
    return out


def _steepest(z, top, bottom, fs):
    """The moment the fall [top, bottom] of `z` falls fastest, on a copy smoothed over a tenth of its length, at most
    STEEPEST_SMOOTH_MAX_S (so noise does not pick the moment on a straight ramp, a slow tail - however deep it runs -
    never holds it, and a one-minute step at the head of a two-hour tail is not smeared into the tail)."""
    from scipy.ndimage import gaussian_filter1d
    if bottom - top < 2:
        return top
    seg = np.asarray(z[top:bottom + 1], dtype=float)
    width = max(1.0, SMOOTH_S * float(fs), min((bottom - top) / 10.0, STEEPEST_SMOOTH_MAX_S * float(fs)))
    g = -np.gradient(gaussian_filter1d(seg, width, mode="nearest"))
    return top + int(np.argmax(g))


def _frame(e, lo):
    return {"top_idx": e["top"] + lo, "bottom_idx": e["bottom"] + lo,
            "recovery_idx": e["recovery"] + lo if np.isfinite(e["recovery"]) else float("nan"),
            "depth_mv": e["depth_mv"], "fall_s": e["fall_s"], "half_recovery_s": e["half_recovery_s"],
            "width_s": e["width_s"], "steep_s": e["steep_s"], "long_tail": e["long_tail"]}


def measure(x, a, b, fs, *, to_mv=1000.0, next_start=None, polarity="drop", anchor=None):
    """The drop events of window [a, b) of channel `x` (recording samples, any unit; `to_mv` turns it into mV), read
    with one span length of context each side (at least MIN_CONTEXT_S, at most CONTEXT_MAX_S), and the span's MAIN
    event: the deepest lying mostly inside it - or, with `anchor` (a recording-frame index, e.g. a machine box's own
    onset or trough), the event at that moment, even beside a deeper one.

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
    if not np.all(np.isfinite(np.asarray(x[a:b], dtype=float))):
        out["why"] = "non_finite"
        return out
    return _read(x, a, b, fs, to_mv, polarity, next_start, anchor)


def _read(x, a, b, fs, to_mv, polarity, next_start, anchor):
    """`measure`'s reading of [a, b): the noise, then reads widening until no event is cut by the read's edge."""
    n = len(x)
    # the noise from a fixed stretch round the window's centre, not the window: a short box that is mostly fall
    # would otherwise read its own fall as noise and move every tolerance with it
    centre, half = (a + b) // 2, int(NOISE_HALF_S * fs)
    s0, s1 = max(0, min(a, centre - half)), min(n, max(b, centre + half))
    sigma = noise_sigma(np.asarray(x[s0:s1], dtype=float) * to_mv)
    pad, cap = int(min(max(b - a, MIN_CONTEXT_S * fs), CONTEXT_MAX_S * fs)), int(CONTEXT_MAX_S * fs)
    while True:
        got = _measure_read(x, a, b, fs, to_mv, sigma, pad, polarity, next_start, anchor)
        if not got.get("ok"):
            return got
        # a fall still running where the read ends (or already running where it starts) may run further: read
        # wider, up to the cap
        if not got.pop("cut_by_read") or pad >= cap:
            return got
        pad = min(2 * pad, cap)


def _measure_read(x, a, b, fs, to_mv, sigma, pad, polarity, next_start, anchor):
    """`measure` over one read: [a - pad, b + pad), plus RECOVERY_MAX_S for the last recovery search."""
    n = len(x)
    out = {"ok": False}
    lo, hi = max(0, a - pad), min(n, b + pad)
    rec_hi = min(n, hi + int(RECOVERY_MAX_S * fs))
    raw = np.asarray(x[lo:rec_hi], dtype=float) * to_mv
    if not np.all(np.isfinite(raw)):                      # gaps in the context (or, for span_events, the span)
        raw = np.where(np.isfinite(raw), raw, np.nanmedian(raw))
    inside = raw[a - lo:b - lo]
    falls_fastest = is_drop(inside, fs)
    drop = falls_fastest if polarity == "auto" else polarity == "drop"
    z = raw if drop else -raw
    out.update(polarity=-1 if drop else 1, rise_dominated=not falls_fastest)
    found = candidate_falls(z[:hi - lo], fs, sigma)
    a_l, b_l = a - lo, b - lo

    def mostly_inside(f):
        # at least half its DEPTH falls inside the span. By depth, not time: a fall's slow tail can outlast the span
        # many times over while its drop happens inside it (132 spans were lost to a time rule); a span drawn round
        # the start of a long fall (SH CH2, the researcher's correction) holds that fall; a fall that began before a
        # span (MJu26a CH15's train windows) is held by the span it mostly falls in; a neighbour that merely begins
        # in the span's last moments is not. Or the span holds the moment it falls fastest (`_steepest`), so a sharp
        # drop whose tail runs on far past the span (M2_concat 8d1f50aa: 50 mV in six minutes, then 100 mV more over
        # forty; LM 2a1dc6b4: 4 mV in a minute, then 17 mV over two hours) is held by the span drawn round the drop
        i, j = max(f[0], a_l), min(f[1], b_l)
        if j > i and float(z[i] - np.min(z[i:j + 1])) >= 0.5 * f[2]:
            return True
        return a_l <= _steepest(z, f[0], f[1], fs) < b_l

    target = None
    if anchor is not None:
        at = int(anchor) - lo

        def distance(f):
            return 0 if f[0] <= at <= f[1] else min(abs(at - f[0]), abs(at - f[1]))
        if not found:
            out.update(why="no_fall", n_events=0, events=[])
            return out
        target = min(found, key=distance)
        floor = MIN_REL_DEPTH * target[2]
    else:
        inside_falls = [f for f in found if mostly_inside(f)]
        if not inside_falls:
            out.update(why="no_fall", n_events=0, events=[])
            return out
        floor = MIN_REL_DEPTH * max(f[2] for f in inside_falls)
    kept = [f for f in found if f[2] >= floor]
    bound = None if next_start is None else int(next_start) - lo
    measured = with_recoveries(z, fs, kept, hard_bound=bound)
    if target is not None:
        main = next(e for e in measured if (e["top"], e["bottom"]) == (target[0], target[1]))
        events = [e for e in measured if e is main or mostly_inside((e["top"], e["bottom"], e["depth_mv"]))]
    else:
        events = [e for e in measured if mostly_inside((e["top"], e["bottom"], e["depth_mv"]))]
        main = max(events, key=lambda e: e["depth_mv"])
    seg_n = hi - lo
    margin = max(3 * max(1, int(round(SMOOTH_S * fs))), 5)
    cut = any((e["last"] >= seg_n - 1 - margin and hi < n) or (e["first"] <= margin and lo > 0) for e in events)
    out.update(ok=True, **_frame(main, lo), top_extended=main["top"] < a_l, bottom_extended=main["bottom"] >= b_l,
               n_events=len(events), events=[_frame(e, lo) for e in events], cut_by_read=bool(cut))
    return out


def span_events(x, a, b, fs, *, to_mv=1000.0, polarity="drop"):
    """Every drop event of a long span (a sequence), in order, as recording-frame dicts: the events `measure` counts
    for the span, read the same way - with context each side, so an event at the span's edge keeps its real top and
    bottom (M4 CH1: a span starting 1.5 min into a 50 mV fall lost its first 6 mV without it), the relative floor
    taken against the span's own deepest event. Gaps (NaN) are filled with the read's median, not refused."""
    if polarity not in ("drop", "spike"):
        raise ValueError(f"polarity must be drop or spike, got {polarity!r}")
    a, b = max(0, int(a)), min(len(x), int(b))
    if b - a < 4:
        return []
    got = _read(x, a, b, float(fs), to_mv, polarity, None, None)
    return got["events"] if got.get("ok") else []
