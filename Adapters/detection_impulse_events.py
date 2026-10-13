"""
detection_impulse_events.py
============================
`detection.impulse_events` — Scores -> SpanSet: one span per impulse of an
impulse-like score, with an extent the block computes from its own inputs. Built
for `detection.deconvolve` (W1-B), generic on purpose: any score that is mostly
zero with sharp impulses (a future energy operator, a derivative) can feed it.
The rule is `Working.Detection.deconvolution.impulses` (its docstring holds the
definitions and the "why not `detection.threshold`").

Drawn by the standard (`scores->spanset`): `threshold` is a float in the score's
units, so the block page draws it on the upstream curve and lets the researcher
drag it; `meta["events"]` carries span-relative `onset_idx` / `trough_idx` so the
slideshow marks each fall in its window and counts falls per window, and
`right_capped` marks an extent the `max_extent_s` cap set (a dashed edge).
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.Detection.deconvolution.impulses import impulse_events
from Working.types import SpanSet

RULES = [
    {"name": "impulse", "rule": "a sample whose score exceeds threshold; impulses closer than merge_within_s "
                                "are one event."},
    {"name": "onset", "rule": "the last sample before the event's first impulse — the level the event departs from."},
    {"name": "extent", "rule": "from pre_s before the onset to the next event's onset or max_extent_s after the "
                               "onset, whichever comes first, clipped to the span. Consecutive spans therefore overlap by pre_s: the "
                               "next span starts pre_s before the next onset, inside this one."},
    {"name": "trough", "rule": "the sample of largest |x - x[onset]| from the onset to the end of the extent."},
    {"name": "score", "rule": "the sum of the scores from the event's first impulse to its last (the whole jump, "
                              "in the score's units)."},
]


def _run(x, t, fs, threshold=4.0, merge_within_s=2.0, pre_s=10.0, max_extent_s=600.0, value=None):
    if value is None:
        raise ValueError("detection.impulse_events requires a Scores input from a prior step "
                         "(input_kind='scores'), e.g. detection.deconvolve.")
    score_fs = float(getattr(value, "fs", None) or fs)
    out = impulse_events(value.values, x, score_fs, threshold=threshold, merge_within_s=merge_within_s,
                         pre_s=pre_s, max_extent_s=max_extent_s)
    n = len(out.starts)
    n_capped = sum(1 for e in out.events if e["right_capped"])
    if n:
        summary = (f"{n:,} events from {out.n_impulse_samples:,} samples above {threshold:g}"
                   + (f" · {n_capped} of {n} ended by the {max_extent_s:g} s cap" if n_capped else ""))
    else:
        finite = np.asarray(value.values, float)
        top = float(np.nanmax(finite)) if np.isfinite(finite).any() else float("nan")
        summary = f"no impulse above {threshold:g} (the largest score is {top:.3g})"
    return AdapterResult(
        output_kind="spanset",
        value=SpanSet(starts=out.starts, ends=out.ends, scores=out.sizes),
        meta={
            "summary": summary,
            "events": out.events,
            "n_events": n,
            "n_capped": n_capped,
            "n_impulse_samples": out.n_impulse_samples,
            "threshold": float(threshold),
            "merge_within_s": float(merge_within_s),
            "pre_s": float(pre_s),
            "max_extent_s": float(max_extent_s),
            "rules": RULES,
        },
    )


SPEC = register(AdapterSpec(
    name="detection.impulse_events",
    display_name="Impulse events: one event per impulse, running to the next",
    stage="detection",
    category="detect",
    page_name="Impulse events",
    params=[
        ParamSpec("threshold", float, 4.0,
                  "The cut, in the score's units (for Deconvolve: the jump size in noise SDs); an impulse is a "
                  "sample above it", min=0.0),
        ParamSpec("merge_within_s", float, 2.0,
                  "Impulses closer than this many seconds are one event (a fall spread over a few samples)",
                  min=0.0),
        ParamSpec("pre_s", float, 10.0, "Seconds of context kept before each event's onset", min=0.0),
        ParamSpec("max_extent_s", float, 600.0,
                  "The longest an event may run after its onset when no next event ends it first", min=1.0),
    ],
    run=_run,
    input_kind="scores",
    output_kind="spanset",
    description=(
        "Turns an impulse-like score (mostly zero, sharp impulses — e.g. Deconvolve's jumps) into one event per "
        "impulse: from pre_s before the jump to the next jump or max_extent_s, whichever is first, so an event "
        "that starts before the last one ended is still its own event. Tune threshold first (drag it on the "
        "score); merge_within_s joins a fall spread over a few samples. Each event's onset and trough are "
        "marked, written to `detections`."
    ),
))
