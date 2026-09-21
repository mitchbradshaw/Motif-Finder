"""
spans.py
========
The small span arithmetic Discovery's scoreboard and fan-out need, in one
place so the rules are stated once rather than re-derived per caller.

``absolute_bounds`` is the important one. A ``detections`` row written by a
spanned run **before 2026-09-21** is span-relative — the executor added no
offset — while every reader treats the table as channel-absolute. The
executor adds the offset on write now; a legacy row is recognisable because
its start lies below its run's ``span_start``. This was the P0 the data-truth
critic found in Prompt 01 and it is the same rule the bridge applies in
``webui/server/corpus.py::_absolute``, which delegates here.

Interval merging is not reimplemented: ``Working.database.queries.
merge_intervals`` is the codebase's one definition and is imported.
"""

from Working.database.queries import merge_intervals


def absolute_bounds(start_idx, end_idx, span_start):
    """Channel-absolute bounds for one ``detections`` row.

    Rows the executor writes now are absolute already; a legacy span-relative
    row (start below the run's ``span_start``) is shifted into the channel's
    index space. A whole-channel run has ``span_start = 0`` and is untouched.
    """
    s, e, o = int(start_idx), int(end_idx), int(span_start or 0)
    if o and s < o:
        return s + o, e + o
    return s, e


def clip(spans, lo, hi):
    """Every span intersected with ``[lo, hi)``, empty intersections dropped."""
    lo, hi = int(lo), int(hi)
    out = []
    for a, b in spans:
        a2, b2 = max(int(a), lo), min(int(b), hi)
        if b2 > a2:
            out.append((a2, b2))
    return out


def merged(spans):
    """Non-overlapping, ascending coverage from possibly overlapping spans."""
    return [tuple(s) for s in merge_intervals([(int(a), int(b)) for a, b in spans])]


def total_length(spans):
    """Total covered samples of an already-merged span list."""
    return sum(int(b) - int(a) for a, b in spans)


def contains(coverage, point):
    """Is ``point`` inside the merged, ascending ``coverage``? Binary search,
    so a 700-span coverage costs nothing per detection."""
    lo, hi = 0, len(coverage) - 1
    point = int(point)
    while lo <= hi:
        mid = (lo + hi) // 2
        a, b = coverage[mid]
        if point < a:
            hi = mid - 1
        elif point >= b:
            lo = mid + 1
        else:
            return True
    return False
