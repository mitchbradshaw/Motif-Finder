"""
interrogation_trains.py
=========================
`interrogation.trains` - SpanSet -> SpanSet, a feature block (w1-e). Groups a
detector's events into trains (bursts, Adamatzky's "words") and adds four
columns: `train_id` (-1 = in no train), `train_size`, `position_in_train` and
`gap_before_s` (plus `word_id` under Adamatzky's rule). The spans pass through
unchanged with every column they came with. The algorithms are
`Working.interrogation.trains` (logISI by default, MaxInterval, Adamatzky's
words); this file maps the chain onto it.

* Event times: `interrogation.intervals`' anchor - the upstream `onset_idx`
  (Event shape) when present and `anchor='onset'`, else the span start - and
  its `measure` for `gap_before_s`, imported, so the gap this block reports is
  the interval Intervals reports.
* Groups: an upstream `group` column (a channel / sequence key) splits the
  events, and trains are found per group - an interval is only meaningful
  inside one group (store11's rule, `Working.interrogation.intervals`).
  Train ids are unique across groups.
* `write_group` (default off) writes `group = train_id` so Intervals
  downstream measures timing WITHIN trains. An upstream group is never lost:
  with one present the new key is `<upstream>/<train_id>` and the original
  stays in `group_upstream`. Events in no train share the key `-1`
  (`<upstream>/-1`), so their Intervals row is the timing between isolated
  events - said in the rules.

Why not reuse: `interrogation.intervals` measures the gaps but never groups
events by them; `sequences11`'s regularity gate judges a run already chosen.
Nothing in the registry decides train membership.
"""

import numpy as np
import pandas as pd

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.interrogation_intervals import ANCHORS
from Adapters.interrogation_intervals import measure as interval_measure
from Adapters.registry import register
from Working.block_cost import estimate_seconds, register_cost_model
from Working.interrogation import trains as TR
from Working.types import SpanSet

NAME = "interrogation.trains"
ADDED = ("train_id", "train_size", "position_in_train", "gap_before_s")
#: summary fields copied from one group's result into meta
_SUMMARY = ("cut_s", "void", "intra_peak_s", "max_core_gap_s", "core_and_extend", "density", "lz_complexity",
            "median_within_gap_s", "theta_s", "mean_gap_s", "word_length_distribution", "n_words", "thresholds_s")


def _require(value):
    if value is None:
        raise ValueError(f"{NAME} requires a SpanSet input from a prior step (input_kind='spanset'). "
                         "Put a detector (a block that emits spans) before it.")
    if not isinstance(value, SpanSet):
        raise ValueError(f"{NAME} groups the spans of a SpanSet into trains; got {type(value).__name__}.")
    return value


def _json(v):
    if isinstance(v, (np.floating, np.integer)):
        return v.item()
    return v


def _run(x, t, fs, rule="logisi", min_events=3, max_core_gap_s=0.0, theta_mult=1.0,
         mi_begin_gap_s=TR.MI_DEFAULTS["mi_begin_gap_s"], mi_end_gap_s=TR.MI_DEFAULTS["mi_end_gap_s"],
         mi_min_ibi_s=TR.MI_DEFAULTS["mi_min_ibi_s"], mi_min_duration_s=TR.MI_DEFAULTS["mi_min_duration_s"],
         write_group=False, anchor="onset", value=None):
    spans = _require(value)
    up = spans.features
    n = len(spans.starts)
    use_onset = anchor == "onset" and up is not None and "onset_idx" in up.columns
    anchor_idx = (up["onset_idx"].to_numpy(dtype=float) if use_onset
                  else np.asarray(spans.starts, dtype=float))
    has_group = up is not None and "group" in up.columns
    keys = [str(g) for g in up["group"]] if has_group else ["all"] * n
    gap_before, _, _ = interval_measure(spans.starts, fs, onsets=anchor_idx if use_onset else None,
                                        groups=keys if has_group else None)

    params = dict(min_events=int(min_events), max_core_gap_s=float(max_core_gap_s), theta_mult=float(theta_mult),
                  mi_begin_gap_s=float(mi_begin_gap_s), mi_end_gap_s=float(mi_end_gap_s),
                  mi_min_ibi_s=float(mi_min_ibi_s), mi_min_duration_s=float(mi_min_duration_s))
    train_id = np.full(n, -1, dtype=int)
    train_size = np.zeros(n, dtype=int)
    position = np.full(n, -1, dtype=int)
    word_id = np.full(n, -1, dtype=int) if rule == "adamatzky" else None
    groups, offset, word_offset = {}, 0, 0
    all_sizes, refusals, warnings, reasons = [], [], [], []
    n_unanchored = int((~np.isfinite(anchor_idx)).sum()) if n else 0
    grouped = []   # (key, its anchored events in input order), groups in first-seen order: one sort, not a scan each
    if n:
        uniq, first_seen, inverse = np.unique(np.asarray(keys), return_index=True, return_inverse=True)
        by_group = np.split(np.argsort(inverse, kind="stable"), np.cumsum(np.bincount(inverse))[:-1])
        finite = np.isfinite(anchor_idx)
        grouped = [(str(uniq[gi]), by_group[gi][finite[by_group[gi]]]) for gi in np.argsort(first_seen)]
    for key, idx in grouped:
        res = TR.find_trains(anchor_idx[idx] / float(fs), rule=rule, **params)
        lab = res["train_id"]
        member = lab >= 0
        train_id[idx[member]] = lab[member] + offset
        train_size[idx] = res["train_size"]
        position[idx] = res["position_in_train"]
        if word_id is not None and res["word_id"] is not None:
            word_id[idx] = res["word_id"] + word_offset
            word_offset += int(res["word_id"].max()) + 1 if idx.size else 0
        offset += res["n_trains"]
        all_sizes += res["train_sizes"]
        prefix = "" if not has_group else f"group {key}: "
        if res["refused"]:
            refusals.append(prefix + res["refused"])
        if res["no_trains_reason"]:
            reasons.append(prefix + res["no_trains_reason"])
        warnings += [prefix + w for w in res["warnings"]]
        groups[key] = {k: _json(res.get(k)) for k in
                       ("n_events", "n_gaps", "n_trains", "n_in_trains", "fraction_in_trains",
                        "train_size_distribution", "refused", "no_trains_reason", "warnings", *_SUMMARY)
                       if k in res}

    cols = {"train_id": train_id, "train_size": train_size, "position_in_train": position,
            "gap_before_s": gap_before}
    if word_id is not None:
        cols["word_id"] = word_id
    if write_group:
        cols["group"] = [str(tid) if not has_group else f"{g}/{tid}" for g, tid in zip(keys, train_id)]
        if has_group:
            cols["group_upstream"] = up["group"].to_numpy()
    added = pd.DataFrame(cols)
    if up is None:
        feats = added
    else:
        feats = pd.concat([up.reset_index(drop=True).drop(columns=[c for c in added.columns if c in up.columns]),
                           added], axis=1)

    n_in = int((train_id >= 0).sum())
    meta = {
        "rule": rule, "n_events": n, "n_gaps": int(sum(g["n_gaps"] for g in groups.values())),
        "n_groups": len(groups), "n_unanchored": n_unanchored,
        "anchor_used": "onset_idx" if use_onset else "span_start",
        "n_trains": int(offset), "n_in_trains": n_in, "fraction_in_trains": (n_in / n) if n else None,
        "train_size_distribution": TR.size_distribution(all_sizes),
        "refused": "; ".join(refusals) or None,
        "no_trains_reason": ("; ".join(reasons) or "no events") if offset == 0 else None,
        "warnings": warnings, "write_group": bool(write_group),
        "rules": TR.rules(rule, **params) + _group_rules(write_group, has_group),
        "groups": groups,
    }
    if len(groups) == 1:
        only = next(iter(groups.values()))
        meta.update({k: only[k] for k in _SUMMARY if k in only})
    else:
        meta.update({k: None for k in ("cut_s", "void", "intra_peak_s", "density", "lz_complexity")})
        meta["per_group_note"] = "trains are found per group; each group's cut, density and LZ are under 'groups'"
    if n_unanchored:
        meta["warnings"] = meta["warnings"] + [f"{n_unanchored} event(s) have no onset to time them by and are in "
                                               "no train"]
    return AdapterResult(
        output_kind="spanset",
        value=SpanSet(starts=tuple(spans.starts), ends=tuple(spans.ends), labels=spans.labels, scores=spans.scores,
                      features=feats),
        meta=meta,
    )


def _group_rules(write_group, has_group):
    if not write_group:
        return []
    return [{"name": "group", "rule": ("written = the train id" + (" prefixed by the upstream group "
                                                                   "('<group>/<train_id>'; the original is kept in "
                                                                   "group_upstream)" if has_group else "")
                                       + ", so Intervals downstream measures timing within trains; events in no "
                                         "train share the key -1, whose intervals are between isolated events")}]


def _time_once(x, fs):
    rng = np.random.default_rng(0)
    TR.find_trains(np.cumsum(rng.exponential(30.0, max(10, len(x) // 50))))


register_cost_model(NAME, 1.0, _time_once)


def _estimate(x, t, fs, **params):
    # O(events log events) plus a 512-point density over the gaps; bounded by O(n) in the span length
    return estimate_seconds(NAME, len(x))


SPEC = register(AdapterSpec(
    name=NAME,
    display_name="Trains of events (logISI, MaxInterval, Adamatzky's words)",
    stage="interrogation",
    category="control",
    page_name="Trains",
    params=[
        ParamSpec("rule", str, "logisi",
                  "How a train is decided: logisi (the valley of the log-gap histogram is the cut; Pasquale et al. "
                  "2010), maxinterval (five fixed thresholds; Cotterill et al. 2016), adamatzky (a gap <= theta x "
                  "the mean gap joins a word; Adamatzky 2022)", choices=list(TR.RULE_NAMES)),
        ParamSpec("min_events", int, 3, "Fewest events a train may hold (Pasquale and Cotterill: 3)", min=2, max=1000),
        ParamSpec("max_core_gap_s", float, 0.0,
                  "logisi: the largest gap that can be typical inside a train, in seconds (the neuronal 100 ms); "
                  "0 = auto = no ceiling (the peaks are tried from the shortest gap up). A value > 0 also makes the cut "
                  "grow cores found with it",
                  min=0.0, max=1e6),
        ParamSpec("theta_mult", float, 1.0, "adamatzky: theta = this x the mean gap (the paper used 1 and 2)",
                  min=0.01, max=100.0),
        ParamSpec("mi_begin_gap_s", float, TR.MI_DEFAULTS["mi_begin_gap_s"],
                  "maxinterval: a train begins at a gap <= this (s). Placeholder for fungal data", min=0.0, max=1e6),
        ParamSpec("mi_end_gap_s", float, TR.MI_DEFAULTS["mi_end_gap_s"],
                  "maxinterval: a train continues while gaps are <= this (s). Placeholder", min=0.0, max=1e6),
        ParamSpec("mi_min_ibi_s", float, TR.MI_DEFAULTS["mi_min_ibi_s"],
                  "maxinterval: trains closer than this (s) merge. Placeholder", min=0.0, max=1e6),
        ParamSpec("mi_min_duration_s", float, TR.MI_DEFAULTS["mi_min_duration_s"],
                  "maxinterval: trains shorter than this (s) are dropped. Placeholder", min=0.0, max=1e6),
        ParamSpec("write_group", bool, False,
                  "Write group = train id, so Intervals after this block measures timing within trains"),
        ParamSpec("anchor", str, "onset",
                  "Time each event from its measured onset (Event shape upstream) or its span start",
                  choices=list(ANCHORS)),
    ],
    run=_run,
    estimate=_estimate,
    input_kind="spanset",
    output_kind="spanset",
    description=(
        "Groups events into trains. If events come in trains, the gaps between them are of two kinds - short "
        "inside a train, long between - and a log-scale histogram of the gaps has two humps; the default rule "
        "(logISI) cuts at the valley between them, and when there is only one hump it says 'no trains' instead of "
        "inventing some. It uses Silverman's robust bandwidth; when timing inside a train is irregular it needs the "
        "gaps between trains to be ~30-100x those inside, so 'no trains' can mean 'not resolvable'. Adds train_id "
        "(-1 = none), train_size, position_in_train and gap_before_s; the spans and "
        "their columns pass through. Tune max_core_gap_s first (0 = no ceiling) if the valley lands in the "
        "wrong place; rule=adamatzky or maxinterval give comparable cuts. Put it after Event shape, and before "
        "Intervals with write_group on to time events within trains."
    ),
))
