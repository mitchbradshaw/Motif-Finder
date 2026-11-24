"""
anchor.py
=========
Every candidate's box redrawn around the event it holds, and candidates that hold the same event made one.

In plain words
--------------
Each source draws its own box: a 15 s slice of the steep part of a fall (BEADS -> threshold), a fixed 400 s box
(BEADS-invert), a window starting minutes before the fall (drop v1), a 30-minute scan window. So the same kind of drop
got boxes of very different sizes, some only a slice of the drop and some several times wider. Here the box is
measured off the event itself, the same way for every source (the researcher's choice, 2026-11-23, Q1 (b)):

    from the TOP of the drop
    to where the signal has climbed HALF-WAY BACK, or - when it does not - to the BOTTOM of the drop
    plus a margin of a tenth of that length on each side.

The drop is the Library's **whole drop** (`Working.interrogation.whole_drop.measure`, the rule the researcher approved
on 2026-11-23): one unbroken fall, ended by a pause or a rebound; a steep start with a slow tail is one event,
measured to the tail's bottom; separate drops are never joined. The box is read with one box length of context each
side (two hours at most), so a 15 s slice of a fall gets its real top and bottom; the main event is the deepest whose
depth lies mostly inside the box. So a candidate's box and the Library's measure of an accepted span are one rule.

The polarity is chosen here (`polarity_of`): the box's fastest edge, or its first edge when the two are about equally
fast, so a square-bottomed drop's fast recovery is not read as an upward spike; a spike is measured as a rise.

Candidates whose redrawn boxes are one fall (same polarity, falls [top, bottom] overlapping by `FALL_OVERLAP` of the
shorter) are one event, drawn by the deepest of their boxes (`same_event`). An event's RETURN - the rise back after a
drop, the fall back after a spike - folds into it (`fold_returns`), and a much smaller box that is part of a deeper
event - a step part-way down its fall, or the other edge of a square drop read as a tiny spike - folds into it
(`fold_nested`); `fold` does both. Small events in a recovery stay their own events. A box's margins never reach into
a neighbouring event (`clip_margins`).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from Working.interrogation import whole_drop as WD

#: The margin added on each side of top -> end, as a fraction of that length.
MARGIN_FRAC = 0.1
#: More missing samples than this in a box and it is not measured (gaps up to it are filled linearly).
MAX_GAP_FRAC = 0.05

COLUMNS = ("ok", "why", "polarity", "onset", "extremum", "end", "recovered", "depth_mv", "box_start", "box_end")


def _filled(seg):
    seg = np.asarray(seg, dtype=float)
    ok = np.isfinite(seg)
    if ok.all():
        return seg
    if ok.mean() < 1.0 - MAX_GAP_FRAC or ok.sum() < 3:
        return None
    k = np.arange(len(seg))
    seg = seg.copy()
    seg[~ok] = np.interp(k[~ok], k[ok], seg[ok])
    return seg


#: When the steepest fall and the steepest rise in a box are within this factor of each other, the FIRST of the two
#: edges decides the polarity (a square-bottomed drop falls and recovers about equally fast: it is a drop).
EDGE_TIE = 1.5


def polarity_of(segment):
    """True for a drop. The fastest edge decides (`whole_drop.is_drop`'s and `event_shape`'s rule: a sharkfin's fall is
    far faster than its rise), unless the two edges are within `EDGE_TIE` of each other - then the earlier one does,
    so a square drop's fast recovery is not taken for an upward spike."""
    seg = np.asarray(segment, dtype=float)
    seg = seg[np.isfinite(seg)]
    if seg.size < 3:
        return True
    d = np.gradient(seg)
    fall, rise = -float(d.min()), float(d.max())
    if fall >= EDGE_TIE * rise:
        return True
    if rise >= EDGE_TIE * fall:
        return False
    return int(np.argmin(d)) <= int(np.argmax(d))


def anchor_one(x_mv, start, end, fs, *, margin_frac=MARGIN_FRAC):
    """The event inside ``[start, end)`` of ``x_mv`` (millivolts), every index absolute in ``x_mv``.

    ``onset`` and ``extremum`` are the whole drop's top and bottom; ``end`` its half recovery, or its bottom when it
    does not recover. Returns a dict with `COLUMNS`: ``ok`` False (and ``why``) when the box holds no event.
    """
    n = len(x_mv)
    s, e = max(0, int(start)), min(n, int(end))
    out = {c: None for c in COLUMNS}
    out.update(ok=False, why=None)
    if e - s < 4:
        out["why"] = "too_short"
        return out
    box = _filled(x_mv[s:e])
    if box is None:
        out["why"] = "gaps"
        return out
    pol = "drop" if polarity_of(box) else "spike"
    r = WD.measure(x_mv, s, e, fs, to_mv=1.0, polarity=pol)
    if not r.get("ok"):
        out["why"] = r.get("why") or "no_event"
        return out
    out.update(_event_row(r, pol, n, margin_frac))
    return out


#: A proposal is measured over its box widened by its own length on each side, and by at least this many seconds: a
#: 2-second threshold slice often sits at the bottom of its fall, and the whole-drop rule counts an event only when
#: most of its depth lies inside the window it is given.
MIN_PAD_S = 5.0


def _event_row(e, polarity, n, margin_frac):
    top, bottom = int(e["top_idx"]), int(e["bottom_idx"])
    rec = e.get("recovery_idx")
    recovered = rec is not None and math.isfinite(float(rec))
    end_abs = int(math.ceil(float(rec))) if recovered else bottom
    margin = max(1, int(round(margin_frac * max(end_abs - top, 1))))
    return {"ok": True, "why": None, "polarity": polarity, "onset": top, "extremum": bottom, "end": end_abs,
            "recovered": recovered, "depth_mv": float(e["depth_mv"]),
            "box_start": max(0, top - margin), "box_end": min(n, end_abs + margin + 1)}


def anchor_events(x_mv, start, end, fs, *, min_pad_s=MIN_PAD_S, margin_frac=MARGIN_FRAC):
    """EVERY whole-drop event a proposal's box points at, of either polarity: the box is widened by its own length on
    each side (at least ``min_pad_s``), measured with `whole_drop.measure` as drops and as rises, and each event a
    measure finds that overlaps the ORIGINAL box is returned, in the `COLUMNS` shape.

    So a long detector box that holds three train members gives three events, not just the deepest, and a 2-second
    threshold slice at the bottom of a fall gives that fall. Both polarities, always: a box round a 1 mV drop whose
    slow climb back was measured first used to give only the climb (M2_aug CH7_B2 283:24 h, 2026-11-23). Whether an
    event of the other polarity is a return, part of a bigger event or one of its own is decided after (`fold`).
    Empty when the box points at no event."""
    n = len(x_mv)
    s, e = max(0, int(start)), min(n, int(end))
    if e - s < 2:
        return []
    box = _filled(x_mv[s:e])
    if box is None:
        return []
    pad = max(e - s, int(round(float(min_pad_s) * float(fs))))
    ws, we = max(0, s - pad), min(n, e + pad)
    rows = []
    for pol in ("drop", "spike"):
        r = WD.measure(x_mv, ws, we, fs, to_mv=1.0, polarity=pol)
        if not r.get("ok"):
            continue
        rows += [_event_row(ev, pol, n, margin_frac) for ev in (r.get("events") or [])
                 if int(ev["top_idx"]) < e and (int(math.ceil(float(ev["recovery_idx"])))
                                                if ev.get("recovery_idx") is not None
                                                and math.isfinite(float(ev["recovery_idx"]))
                                                else int(ev["bottom_idx"])) >= s]
    return rows


def anchor_all(x_mv, starts, ends, fs, **kw):
    """`anchor_one` for every box: a frame with `COLUMNS`, one row per box, in the input order."""
    rows = [anchor_one(x_mv, s, e, fs, **kw) for s, e in zip(starts, ends)]
    return pd.DataFrame(rows, columns=list(COLUMNS))


#: Two boxes of one polarity are one event when their steep falls ([onset, trough]) overlap by this share of the
#: shorter fall: candidates that came from different boxes redraw to slightly different troughs on one fall (the M4
#: 218.5 h drop was drawn five times before this rule). The deepest box stands for the event (the whole drop).
FALL_OVERLAP = 0.5
#: A box at most 1/`NESTED_DEPTH_RATIO` as deep as another folds into it when it lies (`NESTED_SHARE`) inside that
#: event's steep FALL (same polarity: a step part-way down one fall) or inside its whole box (the other polarity: the
#: edge of a square drop read as a tiny spike). Small events of the same polarity in a recovery or a settle stay their
#: own events.
NESTED_SHARE = 0.9
NESTED_DEPTH_RATIO = 4.0
#: An event's RETURN - the rise back after a drop, the fall back after a spike - may come out a little deeper than the
#: event itself and still be its return: a trace seldom comes back to exactly where it left, and noise decides which
#: of two near-equal depths is larger (2026-11-23: M4 CH1 63:37 h, a 4.27 mV drop whose climb back measured 4.38; CH14
#: 395:37 h, a 1.23 mV spike whose fall back measured 1.29; CH14 396:39 h, a 5.86 mV drop and a 6.12 mV rise back,
#: boxed for 26 minutes over a spike train). Up to this factor deeper.
RETURN_TOL = 1.25
#: ... and it starts where the event bottoms out: within this many of the event's own fall durations after its bottom
#: (or peak). M4 CH1's 63:37 h drop fell for 3 minutes and its climb back began 84 s after the bottom; the next spike
#: of a CH14 train began 54 s after the bottom of an 11-sample fall, and is no return.
RETURN_GAP = 1.0


def _ok_rows(anchored):
    a = anchored.reset_index(drop=True)
    return a, np.flatnonzero(a["ok"].to_numpy(dtype=bool))


def same_event(anchored, priority=None, *, share=FALL_OVERLAP):
    """``into[i]``: the box that stands for box ``i``'s event — the deepest of every box of the same polarity whose
    steep fall overlaps its own (by ``share`` of the shorter fall, chained) — or itself. ``priority`` breaks ties in
    depth. Boxes that failed to anchor stay themselves."""
    a, idx = _ok_rows(anchored)
    into = np.arange(len(a))
    if len(idx) < 2:
        return into
    on = a.loc[idx, "onset"].to_numpy(dtype=np.int64)
    ex = np.maximum(a.loc[idx, "extremum"].to_numpy(dtype=np.int64), on + 1)
    pol = a.loc[idx, "polarity"].to_numpy(dtype=object)
    dep = a.loc[idx, "depth_mv"].to_numpy(dtype=float)
    pri = np.zeros(len(a)) if priority is None else np.asarray(priority, dtype=float)
    parent = list(range(len(idx)))

    def root(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    order = np.argsort(on, kind="stable")
    for u_pos, u in enumerate(order):                        # sweep by onset: only falls that start before u ends
        for v in order[u_pos + 1:]:
            if on[v] >= ex[u]:
                break
            if pol[u] != pol[v]:
                continue
            inter = min(ex[u], ex[v]) - max(on[u], on[v])
            if inter > 0 and inter >= share * min(ex[u] - on[u], ex[v] - on[v]):
                parent[root(v)] = root(u)
    groups = {}
    for k in range(len(idx)):
        groups.setdefault(root(k), []).append(k)
    for members in groups.values():
        best = max(members, key=lambda k: (dep[k], pri[idx[k]], -k))
        for k in members:
            into[idx[k]] = idx[best]
    return into


def fold_nested(anchored, into, *, share=NESTED_SHARE, ratio=NESTED_DEPTH_RATIO):
    """``into`` with every surviving box that is part of a much deeper surviving event folded into it: a box of the
    same polarity lying inside that event's steep fall, or one of the other polarity lying inside its whole box."""
    a, ok_idx = _ok_rows(anchored)
    into = np.asarray(into).copy()
    alive = np.array([i for i in ok_idx if into[i] == i], dtype=np.int64)
    if len(alive) < 2:
        return into
    bs = a.loc[alive, "box_start"].to_numpy(dtype=np.int64)
    be = a.loc[alive, "box_end"].to_numpy(dtype=np.int64)
    on = a.loc[alive, "onset"].to_numpy(dtype=np.int64)
    ex = a.loc[alive, "extremum"].to_numpy(dtype=np.int64)
    dep = a.loc[alive, "depth_mv"].to_numpy(dtype=float)
    pol = a.loc[alive, "polarity"].to_numpy(dtype=object)
    order = np.argsort(bs, kind="stable")
    bs_sorted = bs[order]
    longest = int((be - bs).max())
    for q in np.argsort(-dep, kind="stable"):            # deepest first: a box folds into the deepest that holds it
        i = alive[q]
        if into[i] != i:
            continue
        lo = np.searchsorted(bs_sorted, bs[q] - longest, side="left")
        hi = np.searchsorted(bs_sorted, be[q], side="left")
        for r in order[lo:hi]:
            j = alive[r]
            if r == q or into[j] != j:
                continue
            if dep[q] < ratio * dep[r]:
                continue
            if pol[r] == pol[q]:
                host_s, host_e = on[q], ex[q]                # inside the steep fall only
            else:
                host_s, host_e = bs[q], be[q]                # the other polarity: inside the whole box
            inter = min(host_e, be[r]) - max(host_s, bs[r])
            if inter >= share * max(1, be[r] - bs[r]):
                into[into == j] = i
    return into


def fold_returns(anchored, into, *, tol=RETURN_TOL, gap=RETURN_GAP):
    """``into`` with each surviving event's RETURN folded into it: of the events of the other polarity that START
    where it bottoms out (from its bottom, less a tenth of its fall, to ``gap`` falls after it, inside its box) and
    are at most ``tol`` times as deep, the deepest - the rise back after a drop, the fall back after a spike. Events
    are taken in time order and a return hosts nothing: so a climb back that came out deeper than its drop cannot
    carry the next drop off with it, and the next spike of a train, starting long after a slowly recovering drop's
    bottom, is not that drop's return (CH14 396:42 h, 2026-11-23)."""
    a, ok_idx = _ok_rows(anchored)
    into = np.asarray(into).copy()
    alive = np.array([i for i in ok_idx if into[i] == i], dtype=np.int64)
    if len(alive) < 2:
        return into
    on = a.loc[alive, "onset"].to_numpy(dtype=np.int64)
    ex = a.loc[alive, "extremum"].to_numpy(dtype=np.int64)
    be = a.loc[alive, "box_end"].to_numpy(dtype=np.int64)
    dep = a.loc[alive, "depth_mv"].to_numpy(dtype=float)
    pol = a.loc[alive, "polarity"].to_numpy(dtype=object)
    order = np.argsort(on, kind="stable")
    on_sorted = on[order]
    folded = np.zeros(len(alive), dtype=bool)
    for q in order:
        if folded[q]:
            continue
        fall = max(1, int(ex[q] - on[q]))
        lo = np.searchsorted(on_sorted, ex[q] - max(2, int(0.1 * fall)), side="left")
        hi = np.searchsorted(on_sorted, min(int(be[q]), int(ex[q] + max(2, int(round(gap * fall))))), side="right")
        best = -1
        for r in order[lo:hi]:
            if r == q or folded[r] or pol[r] == pol[q] or dep[r] > tol * dep[q]:
                continue
            if best < 0 or dep[r] > dep[best]:
                best = r
        if best >= 0:
            folded[best] = True
            i, j = alive[q], alive[best]
            into[into == j] = i
    return into


def fold(anchored, into, **kw):
    """`fold_returns`, then `fold_nested`: the boxes that stand for the events once returns and parts are folded."""
    return fold_nested(anchored, fold_returns(anchored, into), **kw)


def clip_margins(box_start, box_end, onset, event_end):
    """Boxes whose MARGINS reach into a neighbouring event, cut back to it: a box ends no later than the next event's
    top and starts no earlier than the previous event's end; the event itself (top to end) is never cut (M2_aug
    CH7_B2 282:58 h, 2026-11-23: a slow decline's 3.5-minute margin covered the sharp drop after it). Arrays in,
    ``(box_start, box_end)`` out, in the input order."""
    bs = np.asarray(box_start, dtype=np.int64).copy()
    be = np.asarray(box_end, dtype=np.int64).copy()
    on = np.asarray(onset, dtype=np.int64)
    en = np.maximum(np.asarray(event_end, dtype=np.int64), on)
    order = np.argsort(on, kind="stable")
    for k, i in enumerate(order):
        if k + 1 < len(order):
            j = order[k + 1]
            if on[j] > en[i]:
                be[i] = max(en[i] + 1, min(be[i], on[j]))
        if k > 0:
            j = order[k - 1]
            if en[j] < on[i]:
                bs[i] = min(on[i], max(bs[i], en[j]))
    return bs, be
