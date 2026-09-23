"""
interrogation_intervals.py
============================
`interrogation.intervals` — SpanSet -> SpanSet (fixup-d). The inter-event
interval before and after every event, as two feature columns, and each
group's interval statistics in meta (median, CV with ddof=1, R² of interval
against index, drift of the last third over the first — `sequences11`'s
regularity gate, the tested thinking about when a run of events IS a train).

Intervals are measured per group and never pooled (store11's rule, carried
over): the group is an upstream `group` column when the SpanSet has one (a
sequence key), and otherwise the whole SpanSet — one chain is one channel's
span, which is one group. The anchor is the event's onset when an upstream
block measured one (`onset_idx`, from Event shape), else the span start; meta
says which it used.

Why not reuse: there were three implementations of the interval
(`store11.interval_stats`, `clusterk1.isi_by_channel`, the Interrogation
aggregate route), none of them a block; they are consolidated into
`Working.interrogation.intervals`, which this block and all three callers now
import. Nothing is re-derived here.

Composes after Event shape in the same linear chain, so one run gives the
shape AND the timing of the same events — the case Q-B-CHAIN wanted without
building a fan-out node (which stays deferred).
"""

import numpy as np
import pandas as pd

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.block_cost import estimate_seconds, register_cost_model
from Working.interrogation import intervals as IV
from Working.types import SpanSet

NAME = "interrogation.intervals"
ANCHORS = ("onset", "start")


def _require(value):
    if value is None:
        raise ValueError(f"{NAME} requires a SpanSet input from a prior step (input_kind='spanset').")
    if not isinstance(value, SpanSet):
        raise ValueError(f"{NAME} times the spans of a SpanSet; got {type(value).__name__}.")
    return value


def measure(starts, fs, *, onsets=None, groups=None):
    """`(before_s, after_s, stats_by_group)` for events at `starts` (samples)."""
    n = len(starts)
    anchor = np.asarray(onsets if onsets is not None else starts, dtype=float)
    keys = [str(g) for g in groups] if groups is not None else ["all"] * n
    before = np.full(n, np.nan)
    after = np.full(n, np.nan)
    stats = {}
    for key in dict.fromkeys(keys):
        idx = np.array([i for i in range(n) if keys[i] == key and np.isfinite(anchor[i])], dtype=int)
        if idx.size:
            idx = idx[np.argsort(anchor[idx], kind="stable")]
        onsets_s = anchor[idx] / float(fs)
        gaps = IV.inter_event_intervals(onsets_s)
        if idx.size > 1:
            before[idx[1:]] = gaps
            after[idx[:-1]] = gaps
        stats[key] = IV.interval_statistics(gaps, n_events=int(idx.size))
    return before, after, stats


def _run(x, t, fs, anchor="onset", value=None):
    spans = _require(value)
    up = spans.features
    use_onset = anchor == "onset" and up is not None and "onset_idx" in up.columns
    onsets = up["onset_idx"].to_numpy(dtype=float) if use_onset else None
    groups = up["group"].tolist() if up is not None and "group" in up.columns else None
    before, after, stats = measure(spans.starts, fs, onsets=onsets, groups=groups)
    cols = pd.DataFrame({"interval_before_s": before, "interval_after_s": after})
    if up is None:
        feats = cols
    else:
        feats = pd.concat([up.reset_index(drop=True).drop(columns=[c for c in cols.columns if c in up.columns]),
                           cols], axis=1)
    return AdapterResult(
        output_kind="spanset",
        value=SpanSet(starts=tuple(spans.starts), ends=tuple(spans.ends), labels=spans.labels, scores=spans.scores,
                      features=feats),
        meta={"interval_stats": stats, "rules": list(IV.RULES), "anchor_used": "onset_idx" if use_onset else "span_start",
              "n_events": len(spans.starts), "n_groups": len(stats)},
    )


def _time_once(x, fs):
    starts = np.arange(0, len(x), 50)
    measure(starts, fs)


register_cost_model(NAME, 1.0, _time_once)


def _estimate(x, t, fs, **params):
    # O(events log events) in the spans, bounded by O(n) in the span length
    return estimate_seconds(NAME, len(x))


SPEC = register(AdapterSpec(
    name=NAME,
    display_name="Inter-event intervals",
    stage="interrogation",
    category="control",
    page_name="Intervals",
    params=[
        ParamSpec("anchor", str, "onset", "Time each event from its measured onset (Event shape upstream) or its span start",
                  choices=list(ANCHORS)),
    ],
    run=_run,
    estimate=_estimate,
    input_kind="spanset",
    output_kind="spanset",
    description=(
        "The interval before and after every event, per group and never pooled across groups, with each group's "
        "median, CV (ddof=1), R² trend and drift ratio — the regularity gate that says when a run of events is a "
        "motif train. Put it after Event shape to time events from their onsets."
    ),
))
