"""
interrogation_event_families.py
=================================
`interrogation.event_families` — SpanSet -> SpanSet, a feature block (w2-e). Cuts a
window around each event with W2-A's cutter, sorts the windows into families of
similar shape with the Library's own engine, and writes each event's family onto the
event, so Intervals after it times each family on its own — "do family A events come
every 40 minutes and family B every 3 hours?" in one straight chain.

The work is `Working.Catalogue.shape_families.event_families` — the exact function a
caller feeds surrogates to; this file maps the chain onto it. Added columns (all
bookkeeping, `Working.types.windowset.BOOKKEEPING_COLUMNS`, so a later clustering or
classifier never learns this one's answer):

* `family` — 1..K by size, largest first; -1 = none;
* `family_omit_reason` — "" for a placed event, else why: the method's own
  (`not_in_a_dense_family`, `past_cut`, `group_too_small`), `missing_values` /
  `infinite_values`, or `no_window` (the cutter left the event out: too near a span
  end, too many missing samples);
* `family_distance` — to the family's medoid on the method's 0-1 scale (NaN off a family);
* `family_noise_like` — the event's family is flagged no better than noise.

`write_group` (default ON — timing per family is this block's reason to exist) writes
`group` with `Working.interrogation.intervals.write_group_columns`, the helper
`interrogation.trains` uses: the family's key (`group_key`: the number, `-1` for none,
`<n>~noise_like` for a family flagged noise-like, so Intervals' table says it), and
with an upstream `group` the key `<upstream>/<family>`, the original kept in
`group_upstream`.

**Anchor default: the span start, not the onset** (an adaptation of W2-A's default).
Shapes are compared by where the same point of every event sits in its window; on
the template's synthetic recording Event shape's `onset_idx` landed anywhere from 0 to
230 s after a square dip's start (its knee rule meets a flat bottom), which pushed
whole events out of a 140 s window: adjusted Rand 0.13-0.27 with `onset`, 1.00 with
`start` (both HDBSCAN and k-Shape, measured). The span start is where the detector's
own cut crossed, the same point for every event of one shape. `anchor` stays a param.
"""

import time

import numpy as np
import pandas as pd

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.catalogue_shape_families import common_params, estimate_for, family_meta
from Adapters.registry import register
from Working.Catalogue import event_windows as EW
from Working.Catalogue import shape_families as SF
from Working.interrogation.intervals import write_group_columns
from Working.types import SpanSet

NAME = "interrogation.event_families"
ADDED = ("family", "family_omit_reason", "family_distance", "family_noise_like")
DEFAULT_ANCHOR = "start"


def _require(value):
    if value is None:
        raise ValueError(f"{NAME} requires a SpanSet input from a prior step (input_kind='spanset'): put a detector "
                         "(and Event shape) before it.")
    if not isinstance(value, SpanSet):
        raise ValueError(f"{NAME} sorts the events of a SpanSet into families; got {type(value).__name__}.")
    return value


def _rules(write_group, has_group):
    out = [{"name": "family", "rule": "each event's family, 1..K by size (largest first), -1 = none, with "
                                      "family_omit_reason (\"\" when placed), family_distance (to the family's "
                                      "medoid) and family_noise_like; bookkeeping columns, never features"}]
    if write_group:
        out.append({"name": "group", "rule": ("written = the family (-1 for none; '<n>~noise_like' for a family "
                                              "flagged no better than noise)"
                                              + (" prefixed by the upstream group ('<group>/<family>'; the original "
                                                 "is kept in group_upstream)" if has_group else "")
                                              + ", so Intervals downstream measures each family's own rhythm; the "
                                                "-1 key's intervals are between events in no family")})
    return out


def _run(x, t, fs, anchor=DEFAULT_ANCHOR, length_s=0.0, pre_frac=EW.DEFAULT_PRE_FRAC,
         max_nan_frac=EW.DEFAULT_MAX_NAN_FRAC, write_group=True, method=SF.DEFAULT_METHOD, seed=0, value=None,
         **flat):
    t0 = time.time()
    spans = _require(value)
    up = spans.features
    x = np.asarray(x, dtype=float)
    ev = SF.event_families(x, fs, spans, anchor=anchor, length_s=length_s, pre_frac=pre_frac,
                           max_nan_frac=max_nan_frac, method=method, params=SF.method_params(method, flat), seed=seed)
    fam = ev.families
    cols = {"family": ev.family, "family_omit_reason": [r or "" for r in ev.omit_reason],
            "family_distance": ev.distance, "family_noise_like": ev.noise_like}
    has_group = up is not None and "group" in up.columns
    if write_group:
        cols.update(write_group_columns(up, [SF.group_key(f, nl) for f, nl in zip(ev.family, ev.noise_like)]))
    added = pd.DataFrame(cols)
    feats = added if up is None else pd.concat(
        [up.reset_index(drop=True).drop(columns=[c for c in added.columns if c in up.columns]), added], axis=1)

    ew = ev.windows
    meta = family_meta(fam, method=method, flat=flat)
    meta["omitted"] = dict(ev.omitted)
    n_ev = ev.n_events
    meta.update(n_events=n_ev, n_windows=int(len(ew.starts)), fraction_placed=ev.fraction_placed,
                fraction_confident=ev.fraction_confident, write_group=bool(write_group))
    kept = np.asarray(ew.kept, dtype=np.int64)
    # the serializer's format ({"<family>": event index} + exemplar_rule); the richer list under `exemplars`
    meta["exemplars"] = [
        {"family": f.family, "event": int(kept[f.medoid_row]), "start": int(spans.starts[kept[f.medoid_row]]),
         "start_s": float(spans.starts[kept[f.medoid_row]] / float(fs))} for f in fam.families]
    meta["exemplar_events"] = {str(e["family"]): e["event"] for e in meta["exemplars"]}
    meta["window"] = {"length_s": ew.length_s, "length": int(ew.length), "anchor": anchor,
                      "anchor_used": ew.anchor_used, "anchor_offset": int(ew.anchor_offset),
                      "anchor_fallback": int(ew.n_fallback), "pre_frac": float(pre_frac),
                      "length_basis": ew.length_basis, "omitted": dict(ew.omitted)}
    meta["notes"] = list(ew.notes) + meta["notes"]
    meta["rules"] = _rules(write_group, has_group) + meta["rules"] + EW.rules(
        anchor=anchor, pre_frac=pre_frac, max_nan_frac=max_nan_frac, length_s=length_s, length_basis=ew.length_basis)
    meta["seconds"] = round(time.time() - t0, 3)
    if n_ev == 0:
        meta["summary"] = "no events to sort into families: the step before found none — see its meta for why"
    else:
        cut = int(ev.omitted.get(SF.OMIT_NO_WINDOW, 0))
        meta["summary"] = SF.summary_line(fam, unit_word="event window") + (
            f"; {cut} of {n_ev} event(s) without a window (no_window)" if cut else "")
    return AdapterResult(
        output_kind="spanset",
        value=SpanSet(starts=tuple(spans.starts), ends=tuple(spans.ends), labels=spans.labels, scores=spans.scores,
                      features=feats),
        meta=meta,
    )


def _estimate(x, t, fs, method=SF.DEFAULT_METHOD, **params):
    # one window per event; the estimate cannot see the events, so it assumes one per ASSUMED_SECONDS_PER_ITEM
    flat = {k: v for k, v in params.items()
            if k not in ("anchor", "length_s", "pre_frac", "max_nan_frac", "write_group", "seed")}
    return estimate_for(x, fs, method, flat)


SPEC = register(AdapterSpec(
    name=NAME,
    display_name="Event families (SpanSet -> SpanSet + family, the Library's methods)",
    stage="interrogation",
    category="cluster",
    page_name="Event families",
    params=[
        ParamSpec("anchor", str, DEFAULT_ANCHOR,
                  "What each event's window is lined up on: its span start (default: where the detector's cut "
                  "crossed, the same point for every event of one shape), Event shape's onset, or its extremum",
                  choices=list(EW.ANCHORS)),
        ParamSpec("length_s", float, 0.0,
                  "Window length in seconds. 0 = auto, as Event windows: twice the median event duration, rounded "
                  "up to 10 s, clamped to 60-7200 s (it holds the onset and about half the recovery)",
                  min=0.0, max=86400.0),
        ParamSpec("pre_frac", float, EW.DEFAULT_PRE_FRAC, "Share of the window before the anchor", min=0.0, max=0.95),
        ParamSpec("max_nan_frac", float, EW.DEFAULT_MAX_NAN_FRAC,
                  "Leave out a window with more than this fraction of missing samples (fewer are interpolated)",
                  min=0.0, max=1.0),
        ParamSpec("write_group", bool, True,
                  "Write group = family, so Intervals after this block times each family on its own"),
        *common_params(),
    ],
    run=_run,
    estimate=_estimate,
    input_kind="spanset",
    output_kind="spanset",
    description=(
        "Sorts the events into families of similar shape with the Library's own methods (a window around each "
        "event, resampled and z-normalised, so amplitude does not enter) and writes each event's family onto it — "
        "and, by default, as its group, so Intervals after this block gives each family its own rhythm. Each "
        "family carries the method's noise flag (better than phase-randomised noise of the same colour?) and its "
        "SVD entropy beside what noise scores; events in no family are -1 with their reason. Read a family's "
        "noise flag before its rhythm. Tune the method's minimum family size first (hdbscan_min_cluster_size). "
        "Put Event shape before it."
    ),
))
