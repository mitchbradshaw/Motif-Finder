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
`<n>~noise_like` for a family flagged noise-like, `<n>~untested` for one no null was
drawn for (Ward), so Intervals' table says it — an unmarked key is a family that was
tested and passed), and with an upstream `group` the key `<upstream>/<family>`, the original kept in
`group_upstream`.

**Defaults: the span start and a 600 s window** (adaptations of W2-A's onset and
auto length), both placeholders until checked on real recordings, both measured.
* Anchor. Shapes are compared by where the same point of every event sits in its
  window. On the template's synthetic recording Event shape's `onset_idx` landed 0 to
  230 s after a square dip's start (its knee rule meets a flat bottom): adjusted Rand
  0.13-0.27 with `onset` against 1.00 with `start`. The critic's 432-run sweep through
  the real chain (three shape pairs x AR(1) 0.97 / 0.99 / random walk x 2 seeds x
  SNR 10 and 40) agrees: `start` beat `onset` and `extremum` in every cell (onset at
  its best length 7-12/18, extremum 6-11/18).
* Length. In the same sweep, start + 600 s kept both shapes in distinct unmarked
  families with their medians within 10 % in 18/18 cases at SNR 10 and 18/18 at SNR
  40 (mean ARI 0.87 and 1.00); 300 s 18/18 and 16/18; 1200 s 8/18 and 16/18; the auto
  length (`length_s = 0`, twice Event shape's median duration) only 5/18 and 4/18 —
  the duration is fragile (unmeasured on clean drops -> the 7200 s ceiling, three
  events a window; 11 s at SNR 10 -> the 60 s floor). A caller who asks for the auto
  length gets W2-A's coverage warnings in `meta.warnings` and the summary: clamped to
  the floor or ceiling, more than a quarter of windows overlapping the next, more than
  a quarter ending before their recovery.

**k-Shape is not offered here.** Its families become Intervals keys, and its null (W2-B's
plain phase-randomised one) left unflagged families in pure random-walk events (132 +
108 members at n = 1,000, the W2-E critic): `SF.EVENT_FAMILIES_EXCLUDED`. The follow-up
is a trend-kept k-Shape null in the Library methods; `catalogue.shape_families` keeps
k-Shape but calls none of its families confident.
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
                                              "flagged no better than noise; '<n>~untested' for a family no null "
                                              "was drawn for, e.g. Ward's: an unmarked key was tested and passed)"
                                              + (" prefixed by the upstream group ('<group>/<family>'; the original "
                                                 "is kept in group_upstream)" if has_group else "")
                                              + ", so Intervals downstream measures each family's own rhythm; the "
                                                "-1 key's intervals are between events in no family")})
    return out


def _run(x, t, fs, anchor=DEFAULT_ANCHOR, length_s=SF.DEFAULT_EVENT_LENGTH_S, pre_frac=EW.DEFAULT_PRE_FRAC,
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
        cols.update(write_group_columns(up, [SF.group_key(f, nl, tt)
                                                for f, nl, tt in zip(ev.family, ev.noise_like, ev.tested)]))
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
    auto_warn, auto_short = SF.auto_length_warnings(spans, ew, length_s)
    meta["warnings"] = auto_warn + meta["warnings"]
    meta["rules"] = _rules(write_group, has_group) + meta["rules"] + EW.rules(
        anchor=anchor, pre_frac=pre_frac, max_nan_frac=max_nan_frac, length_s=length_s, length_basis=ew.length_basis)
    meta["seconds"] = round(time.time() - t0, 3)
    if n_ev == 0:
        meta["summary"] = "no events to sort into families: the step before found none — see its meta for why"
    else:
        no_win = {r.split(":", 1)[1]: c for r, c in ev.omitted.items() if r.startswith(SF.OMIT_NO_WINDOW + ":")}
        cut = sum(no_win.values())
        meta["summary"] = "; ".join(
            [SF.summary_line(fam, unit_word="event window")]
            + ([f"{cut} of {n_ev} event(s) without a window (" + ", ".join(f"{r} {c}" for r, c in no_win.items())
                + ")"] if cut else [])
            + auto_short)
    return AdapterResult(
        output_kind="spanset",
        value=SpanSet(starts=tuple(spans.starts), ends=tuple(spans.ends), labels=spans.labels, scores=spans.scores,
                      features=feats),
        meta=meta,
    )


def _estimate(x, t, fs, method=SF.DEFAULT_METHOD, **params):
    # one window per event; the estimate cannot see the events, so it assumes one per ASSUMED_SECONDS_PER_ITEM
    # (Ward past WARD_MAX_ITEMS is refused by the run, which counts the real events)
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
        ParamSpec("length_s", float, SF.DEFAULT_EVENT_LENGTH_S,
                  "Window length in seconds. 600 (a placeholder, measured on synthetic shapes: the length that kept "
                  "two shapes apart in every case of a 432-run sweep). 0 = auto, as Event windows (twice the median "
                  "event duration, clamped to 60-7200 s) - fragile, warned when it clamps, overlaps or cuts the "
                  "recovery", min=0.0, max=86400.0),
        ParamSpec("pre_frac", float, EW.DEFAULT_PRE_FRAC, "Share of the window before the anchor", min=0.0, max=0.95),
        ParamSpec("max_nan_frac", float, EW.DEFAULT_MAX_NAN_FRAC,
                  "Leave out a window with more than this fraction of missing samples (fewer are interpolated)",
                  min=0.0, max=1.0),
        ParamSpec("write_group", bool, True,
                  "Write group = family, so Intervals after this block times each family on its own"),
        *common_params(exclude=tuple(SF.EVENT_FAMILIES_EXCLUDED)),
    ],
    run=_run,
    estimate=_estimate,
    input_kind="spanset",
    output_kind="spanset",
    description=(
        "EXPERIMENTAL: its template beat the shape null on 1 of the 5 real spans that held events (rec 542's known "
        "chain). On rec 6's chain its two families passed their own noise tests and were far more coherent than "
        "noise, but phase-randomised copies of the same events were placed in families as often; on 24 h M2_aug "
        "spans it found no family at all (docs/prompts/blocks/reports/W2-evaluation.md). Read each family's noise "
        "flag and coherence before its rhythm. "
        "Sorts the events into families of similar shape with the Library's own methods (a window around each "
        "event, resampled and z-normalised, so amplitude does not enter) and writes each event's family onto it — "
        "and, by default, as its group, so Intervals after this block gives each family its own rhythm. Each "
        "family carries the method's noise flag (better than phase-randomised noise of the same colour?) and its "
        "SVD entropy beside what noise scores; events in no family are -1 with their reason. Read a family's "
        "noise flag before its rhythm: an Intervals key marked ~noise_like or ~untested is not a family rhythm. "
        "Tune the method's minimum family size first (hdbscan_min_cluster_size). k-Shape is not offered here: its "
        "noise test missed crowds of pure random-walk events. Put Event shape before it."
    ),
))
