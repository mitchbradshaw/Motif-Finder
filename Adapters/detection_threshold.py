"""
detection_threshold.py
========================
Generic `Scores` -> `SpanSet` block: thresholds a time-aligned `Scores`
(e.g. `detection.matrix_profile`'s output) into the spans where it exceeds
a cutoff. `Working.execution.execute_recipe` writes an `output_kind='spanset'`
result to `detections` directly, so any adapter that declares a `Scores`
output can chain into this one block rather than each detector inventing
its own interval-extraction step (CODING_STANDARDS 3.2's Scores/WindowSet
split is what makes this one generic block possible instead of one per
detector).

Two optional tidying parameters, both off at their 0.0 default so a recipe
that names neither runs exactly as before: `merge_gap_s` joins spans separated
by less than that many seconds into one (scoring the max of its parts), then
`min_duration_s` drops any span shorter than that. Merge first, then drop, so
an event fragmented by one sample's dip under the cut is one event long enough
to keep; either one turns a one-sample graze of the cut (a 1 s span at 1 Hz)
into nothing or into part of its neighbour. Seconds convert to samples at the
Scores' own fs, the index space the spans live in.

This module owns the two helpers its Signal -> SpanSet sibling
(`detection.signal_threshold`) imports — `spans_from_mask` and `tidy_spans`,
with `tidy_param_specs` declaring the two parameters once — so the blocks are
one rule applied to two types.

Not part of T08's declared file list -- no existing adapter or ticket owns
a generic threshold block (checked `docs/tickets/README.md`'s single-owner
rules), and the ticket's acceptance criteria explicitly require one exists
and is chained end to end from `matrix_profile`. Flagged here for the
reviewer per CLAUDE.md's out-of-scope-file rule.
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.types import SpanSet


def spans_from_mask(mask):
    """Contiguous runs of True in `mask` as (starts, ends) index arrays,
    half-open [start, end) -- SpanSet's convention, so no +/-1 adjustment
    is needed at either edge. Shared with `detection.signal_threshold`, the
    Signal -> SpanSet sibling of this block (one rule, two types)."""
    padded = np.concatenate(([False], mask, [False]))
    diff = np.diff(padded.astype(np.int8))
    starts = np.flatnonzero(diff == 1)
    ends = np.flatnonzero(diff == -1)
    return starts, ends


def tidy_spans(starts, ends, scores, fs, min_duration_s=0.0, merge_gap_s=0.0):
    """Join spans separated by fewer than `merge_gap_s` seconds, then drop
    those shorter than `min_duration_s`; both are off at 0.0, when this is the
    identity. Seconds convert to samples as round(seconds * fs). A merged span
    runs from the first part's start to the last part's end and scores the max
    of its parts' scores -- the gap between them contributes nothing. Merging
    runs before the floor so an event fragmented by one sample's recovery (or a
    NaN) is one event, long enough to keep. Takes sorted, disjoint, half-open
    spans; returns plain tuples of ints and floats, ready for a SpanSet.
    Shared with `detection.signal_threshold`."""
    starts = [int(s) for s in starts]
    ends = [int(e) for e in ends]
    scores = [float(v) for v in scores]
    if not (len(starts) == len(ends) == len(scores)):
        raise ValueError(
            f"tidy_spans: {len(starts)} starts, {len(ends)} ends and {len(scores)} scores must agree"
        )
    gap_samples = int(round(float(merge_gap_s) * float(fs)))
    floor_samples = int(round(float(min_duration_s) * float(fs)))

    merged = []                                   # [start, end, score] per span, in order
    for s, e, v in zip(starts, ends, scores):
        if merged and s - merged[-1][1] < gap_samples:
            merged[-1][1] = max(merged[-1][1], e)
            merged[-1][2] = max(merged[-1][2], v)
        else:
            merged.append([s, e, v])
    kept = [(s, e, v) for s, e, v in merged if e - s >= floor_samples]
    return (
        tuple(s for s, _, _ in kept),
        tuple(e for _, e, _ in kept),
        tuple(v for _, _, v in kept),
    )


def tidy_param_specs():
    """Fresh `ParamSpec`s for the two tidying parameters, declared once here
    and spliced into both threshold blocks' parameter lists."""
    return [
        ParamSpec("min_duration_s", float, 0.0,
                  "Drop a span shorter than this many seconds (0 keeps every run, however short); "
                  "applied after merging",
                  min=0.0),
        ParamSpec("merge_gap_s", float, 0.0,
                  "Join spans separated by less than this many seconds into one, scoring the max "
                  "of its parts (0 never joins); applied before the duration floor",
                  min=0.0),
    ]


def _run(x, t, fs, threshold=0.0, min_duration_s=0.0, merge_gap_s=0.0, value=None):
    if value is None:
        raise ValueError(
            "detection.threshold requires a Scores input from a prior step "
            "(input_kind='scores')."
        )

    scores = value.values
    mask = scores > threshold  # NaN > threshold is False -- a NaN-padded tail is excluded
    starts, ends = spans_from_mask(mask)
    span_scores = tuple(float(np.max(scores[s:e])) for s, e in zip(starts, ends))
    # the spans index the Scores, so seconds convert at the Scores' own rate
    starts, ends, span_scores = tidy_spans(starts, ends, span_scores, getattr(value, "fs", None) or fs,
                                           min_duration_s=min_duration_s, merge_gap_s=merge_gap_s)

    return AdapterResult(
        output_kind="spanset",
        value=SpanSet(starts=starts, ends=ends, scores=span_scores),
    )


SPEC = register(AdapterSpec(
    name="detection.threshold",
    display_name="Threshold (Scores -> SpanSet)",
    stage="detection",
    category="detect",
    page_name="Threshold to spans",
    params=[
        ParamSpec("threshold", float, 0.0,
                  "Spans are the contiguous runs where the score exceeds this value"),
        *tidy_param_specs(),
    ],
    run=_run,
    input_kind="scores",
    output_kind="spanset",
    plot=None,
    description=(
        "Generic block: thresholds any Scores (e.g. a matrix profile) into "
        "spans above a cutoff, written to `detections`. Any adapter that "
        "outputs Scores can chain into this one. Optionally join spans closer "
        "than `merge_gap_s` and drop those shorter than `min_duration_s` (both off at 0)."
    ),
))
