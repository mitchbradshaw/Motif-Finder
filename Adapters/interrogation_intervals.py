"""
interrogation_intervals.py
============================
`interrogation.intervals` — SpanSet -> SpanSet (fixup-d). The inter-event
interval before and after every event, as two feature columns, and each
group's interval statistics in meta (median, CV with ddof=1, R² of interval
against index, drift of the last third over the first — `sequences11`'s
regularity gate, the tested thinking about when a run of events IS a train),
and the local measures LV (Shinomoto et al. 2003) and CV2 (Holt et al. 1996),
which compare each gap only with the next so a slow change of rate does not
read as irregularity (W1-G). A group with fewer than three events gets null LV
and CV2 with its reason, and meta counts such groups. Pairs of two 0-s gaps
(coincident onsets, 0/0) are left out of both; each group reports the kept
pairs as `n_local_pairs` and its `local_note` counts the dropped ones (the
caveats - duplicates, few gaps, sampling grid - are in the core module).

Round-B B1: each group's LV and CV2 also stand against two nulls
(`IV.interval_nulls`) - a rate-matched Poisson (is the timing more regular, or
burstier, than random?) and the group's own gaps shuffled (is the ORDER of the
gaps more regular than their distribution implies?) - as `nulls` in the
group's stats: null mean, 2.5-97.5 % band and two-sided p, `null_draws`
seeded draws (default 1,000; 0 = off).

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


def measure(starts, fs, *, onsets=None, groups=None, null_draws=0, null_seed=IV.NULL_SEED):
    """`(before_s, after_s, stats_by_group)` for events at `starts` (samples).

    `null_draws` > 0 adds each group's LV/CV2 nulls (`IV.interval_nulls`, round-B
    B1) as `stats[group]["nulls"]`, drawn on the onsets' sampling grid (1/fs);
    0 sets it to None. The serializer's per-class split calls this without nulls."""
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
        if null_draws:
            stats[key]["nulls"] = IV.interval_nulls(onsets_s, n_draws=int(null_draws), seed=int(null_seed),
                                                    resolution_s=1.0 / float(fs))
    return before, after, stats


def _run(x, t, fs, anchor="onset", null_draws=IV.NULL_DRAWS, null_seed=IV.NULL_SEED, value=None):
    spans = _require(value)
    up = spans.features
    use_onset = anchor == "onset" and up is not None and "onset_idx" in up.columns
    onsets = up["onset_idx"].to_numpy(dtype=float) if use_onset else None
    groups = up["group"].tolist() if up is not None and "group" in up.columns else None
    before, after, stats = measure(spans.starts, fs, onsets=onsets, groups=groups, null_draws=null_draws,
                                   null_seed=null_seed)
    if not null_draws:
        for s in stats.values():
            s["nulls"] = None
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
              "n_events": len(spans.starts), "n_groups": len(stats),
              "n_groups_local_unmeasured": sum(1 for s in stats.values() if s["lv"] is None)},
    )


def _time_once(x, fs):
    starts = np.arange(0, len(x), 50)
    measure(starts, fs, null_draws=IV.NULL_DRAWS)   # the default block run draws its nulls (B1)


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
        ParamSpec("null_draws", int, IV.NULL_DRAWS, "Draws per null for LV and CV2 (rate-matched Poisson and shuffled "
                  "intervals, per group); 0 turns the nulls off", min=0, max=20000),
        ParamSpec("null_seed", int, IV.NULL_SEED, "Seed of the null draws, so a group always gets the same null",
                  min=0, max=2**31 - 1),
    ],
    run=_run,
    estimate=_estimate,
    input_kind="spanset",
    output_kind="spanset",
    description=(
        "The interval before and after every event, per group and never pooled across groups, with each group's "
        "median, CV (ddof=1), R² trend and drift ratio — the regularity gate that says when a run of events is a "
        "motif train — plus LV and CV2, which compare each gap only with the next, so a slow speed-up over the day "
        "does not read as irregular (about 0 = clockwork, 1 = random), each against a rate-matched Poisson null and a "
        "shuffled-interval null (mean, 95 % band, p). Put it after Event shape to time events from their onsets."
    ),
))
