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
``webui/server/corpus.py::_absolute``, which delegates here. ``absolute_sql``
is the same rule as SQL, for the reads that must filter or merge in the query.

Interval merging is not reimplemented: ``Working.database.queries.
merge_intervals`` is the codebase's one definition and is imported;
``merged_rows`` is its numpy form for a recording's ~385 k detections.
"""

import json
import logging
from itertools import chain

import numpy as np

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


def absolute_sql(d="d", r="r"):
    """``absolute_bounds`` as SQL: ``(start_expr, end_expr)`` over a ``detections`` alias `d` joined to its
    ``runs`` alias `r` (tq-rules, 2026-10-25: the corpus window read, the library's detection union and
    Discovery's fires card each restated it). A NULL or 0 ``span_start`` shifts nothing."""
    shifted = f"(IFNULL({r}.span_start, 0) != 0 AND {d}.start_idx < {r}.span_start)"
    return (f"(CASE WHEN {shifted} THEN {d}.start_idx + {r}.span_start ELSE {d}.start_idx END)",
            f"(CASE WHEN {shifted} THEN {d}.end_idx + {r}.span_start ELSE {d}.end_idx END)")


# span-plot (2026-10-18): the one case the rule above cannot settle. A spanned run longer than its offset
# (``span_end - span_start > span_start``) can hold a relative index at or above ``span_start``, which then
# reads as absolute and is drawn between 0 and the span's length. The migration in
# ``Working.database.schema`` refuses such runs ("ambiguous") and leaves them alone. The database can say a run
# IS ambiguous, and that it was written before the executor added the offset (commit a8cea40, 2026-09-21 07:05
# UTC — the date is compared at day resolution, so the whole of the 21st counts as before); it cannot say
# which of its rows are relative. So the read path keeps the heuristic, names the run once, and the fix is a
# one-time, reviewed migration (proposed in docs/prompts/changes/reports/span-plot-report.md).

#: the first UTC day every spanned run's detections were written channel-absolute
EXECUTOR_ABSOLUTE_FROM = "2026-09-22"

#: run ids already warned about in this process (a test clears it)
_AMBIGUOUS_REPORTED: set = set()

_log = logging.getLogger(__name__)


def legacy_ambiguous(span_start, span_end, started_at):
    """Is this run one whose relative rows `absolute_bounds` cannot tell from absolute ones?

    True for a spanned run written before the executor added the offset whose span is longer than its offset.
    A whole-channel run, a span shorter than its offset, and any run written since are never ambiguous."""
    o = int(span_start or 0)
    if o <= 0 or span_end is None:
        return False
    return (int(span_end) - o) > o and str(started_at or "") < EXECUTOR_ABSOLUTE_FROM


def warn_if_ambiguous(run_id, span_start, span_end, started_at, algorithm=None):
    """Log, once per run per process, that `run_id`'s detections may be drawn at the wrong time."""
    if run_id in _AMBIGUOUS_REPORTED or not legacy_ambiguous(span_start, span_end, started_at):
        return False
    _AMBIGUOUS_REPORTED.add(run_id)
    _log.warning(
        "legacy detections: run %d (%s, started %s) spans [%d, %d), longer than its offset, and was written "
        "before 2026-09-21: rows at or above span_start may be span-relative and are drawn as absolute "
        "(the existing heuristic). A one-time migration is needed to place them.",
        int(run_id), algorithm or "unknown detector", str(started_at or "?")[:10], int(span_start), int(span_end))
    return True


def detector_of(config_json):
    try:
        steps = json.loads(config_json or "{}").get("steps") or []
    except (TypeError, ValueError):
        return None
    algos = [s.get("algorithm") for s in steps if isinstance(s, dict) and s.get("algorithm")]
    return algos[-1] if algos else None


def ambiguous_legacy_runs(conn):
    """Every run `legacy_ambiguous` names that holds detections, with its detector (the recipe's last
    algorithm), its start date, its row count and how many rows sit at or above ``span_start`` (the ones the
    heuristic leaves where they are). Read-only: what the proposed migration would act on."""
    rows = conn.execute(
        "SELECT r.id, r.span_start, r.span_end, r.started_at, c.config_json, COUNT(d.id) AS n, "
        "SUM(CASE WHEN d.start_idx >= r.span_start THEN 1 ELSE 0 END) AS n_hi "
        "FROM runs r JOIN detections d ON d.run_id = r.id LEFT JOIN configs c ON c.id = r.config_id "
        "WHERE r.span_start > 0 AND (r.span_end - r.span_start) > r.span_start AND r.started_at < ? "
        "GROUP BY r.id ORDER BY r.id", (EXECUTOR_ABSOLUTE_FROM,)).fetchall()
    return [{"run_id": int(r[0]), "span_start": int(r[1]), "span_end": int(r[2]), "started_at": str(r[3]),
             "detector": detector_of(r[4]), "n": int(r[5]), "n_at_or_above_span_start": int(r[6] or 0)}
            for r in rows]


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


def merged_rows(rows):
    """``merge_intervals`` (overlapping and touching spans merge) over many ``(start, end)`` rows, in numpy:
    `merge_intervals` over a scale recording's ~385 k detections costs seconds; this costs a fraction of one.
    The library's quiet-window null reads it (night-b)."""
    if not rows:
        return []
    # fromiter: np.asarray over 385 k tuples cost ~1.5 s a recording
    arr = np.fromiter(chain.from_iterable(rows), dtype=np.int64, count=2 * len(rows)).reshape(-1, 2)
    arr = arr[np.argsort(arr[:, 0], kind="stable")]      # sorted here: ORDER BY in SQL cost ~0.4 s more
    s, e = arr[:, 0], np.maximum.accumulate(arr[:, 1])
    first = np.flatnonzero(np.r_[True, s[1:] > e[:-1]])          # a row past every earlier end starts a new run
    last = np.r_[first[1:] - 1, len(s) - 1]
    return list(zip(s[first].tolist(), e[last].tolist()))


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
