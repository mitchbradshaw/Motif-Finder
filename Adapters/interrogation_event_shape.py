"""
interrogation_event_shape.py
==============================
`interrogation.event_shape` — SpanSet -> SpanSet (fixup-d). Every per-event
shape measure from ONE block, because the researcher asked to see all measures
from a single block rather than run three to characterise one event
(QUESTIONS.md Q13): amplitude (a drop's depth, a spike's height), precursor
height, event width (onset -> extremum), duration (onset -> recovery), FWHM,
recovery time, steepest / onset / chord slope and peakedness. Polarity-neutral:
one block, polarity handled inside (Q12). The first block in the registry that
consumes a SpanSet.

The spans are passed through unchanged (starts, ends, labels, scores); the
measures ride on `SpanSet.features`, one row per span, and any feature columns
the input already carried are kept. The work is
`Working.interrogation.event_shape` — this file maps the chain onto it.

What rides in meta: `rules` (the rule behind every measure, printed the way
`interrogation_routes.py`'s slope route prints its own — a measure whose rule
is unstated cannot be argued with), the counts of events with no fall / no
recovery / no FWHM, and `rose`: `gradients.rose_data` over the events' steepest
slopes, split by an upstream `group` column when there is one (a sequence key)
and pooled as `all` otherwise.

Why not reuse, measure by measure (BLOCK_INTEGRATION.md §8):
* depth, fall duration, max / onset slope — detect5 measures them, but only
  inside `detect_from_letters` for the events IT finds, and only for drops;
  this block measures any SpanSet (a Dehshibi spike, a threshold span, an
  inverted-signal drop) with detect5's own anatomy functions (`find_trough`,
  `refine_onset`, `walk_back_to_shoulder`) and `gradients.fall_gradients`,
  imported, not copied.
* half width — `Working/Detection/analysis/data_analysis.py::half_width` exists,
  but finds the most prominent PEAK with `find_peaks` (a drop needs inverting)
  and returns `min(left, right)` in samples: the narrower half, not the full
  width at half maximum. Why not use it: it answers a different question; the
  FWHM here is defined beside it.
* recovery, duration, precursor — nothing measured them; defined in
  `Working.interrogation.event_shape` and printed in meta.
* the rose — `gradients.rose_data`, unchanged, handed the oriented snippets.
  `Pipelines/drop_motifs/store11.py` has a second, parallel angle
  implementation for report figures and is deliberately not used.
* `detection.drop_detection` packs onset / trough into its label string; this
  block does not extend that pattern — its anatomy is columns.

Index convention: `onset_idx`, `extremum_idx`, `recovery_idx` are in the
SpanSet's own frame (span-relative, like `starts`).
"""

import numpy as np
import pandas as pd

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.block_cost import estimate_seconds, register_cost_model
from Working.Detection.drop_motifs.gradients import DEFAULT_SLOPE_REF_MV_S, SLOPE_SCALES
from Working.interrogation import event_shape as ES
from Working.types import SpanSet

NAME = "interrogation.event_shape"


def _require(value):
    if value is None:
        raise ValueError(f"{NAME} requires a SpanSet input from a prior step (input_kind='spanset').")
    if not isinstance(value, SpanSet):
        raise ValueError(f"{NAME} measures the spans of a SpanSet; got {type(value).__name__}. "
                         "Put a detector (a block that emits spans) before it.")
    return value


def _merge(upstream, measured):
    """Upstream feature columns kept; a column this block measures replaces its namesake."""
    if upstream is None:
        return measured
    keep = upstream.reset_index(drop=True).drop(columns=[c for c in measured.columns if c in upstream.columns])
    return pd.concat([measured.reset_index(drop=True), keep], axis=1)


def _run(x, t, fs, polarity="drop", upstream_inverted=False, knee_frac=ES.KNEE_FRAC,
         recovery_frac=ES.RECOVERY_FRAC, recovery_max_mult=ES.RECOVERY_MAX_MULT, walk_onset_back=True,
         rose_scale="raw", rose_reference_mv_s=DEFAULT_SLOPE_REF_MV_S, value=None):
    spans = _require(value)
    up = spans.features
    # an upstream block that already located each event (its own onset_idx / extremum_idx
    # columns) defines the event; the anatomy rules are for spans nobody anatomised
    anchored = up is not None and {"onset_idx", "extremum_idx"} <= set(up.columns)
    anchors = list(zip(up["onset_idx"].to_numpy(dtype=float), up["extremum_idx"].to_numpy(dtype=float))) if anchored else None
    feats, detail = ES.measure_events(
        x, spans.starts, spans.ends, fs, polarity=polarity, upstream_inverted=bool(upstream_inverted),
        knee_frac=knee_frac, recovery_frac=recovery_frac, recovery_max_mult=recovery_max_mult,
        walk_onset_back=bool(walk_onset_back), anchors=anchors)
    groups = (up["group"].astype(str).tolist() if up is not None and "group" in up.columns
              else ["all"] * len(spans.starts))
    rose = ES.event_rose(detail, groups, fs, scale=rose_scale, reference=rose_reference_mv_s)
    out = SpanSet(starts=tuple(spans.starts), ends=tuple(spans.ends), labels=spans.labels, scores=spans.scores,
                  features=_merge(up, feats))
    return AdapterResult(
        output_kind="spanset", value=out,
        meta={"rules": ES.rules(knee_frac=knee_frac, recovery_frac=recovery_frac,
                                recovery_max_mult=recovery_max_mult, walk_onset_back=bool(walk_onset_back),
                                upstream_inverted=bool(upstream_inverted), polarity=polarity,
                                anchors_used=("the upstream onset_idx / extremum_idx columns: the event was already located"
                                              if anchored else None)),
              "rose": rose, "n_events": len(spans.starts), "n_no_fall": detail["n_no_fall"],
              "n_not_recovered": detail["n_not_recovered"], "n_no_fwhm": detail["n_no_fwhm"],
              "measures": list(ES.COLUMNS)},
    )


def _time_once(x, fs):
    starts = np.arange(0, len(x) - 200, 200)
    ES.measure_events(x, starts, starts + 200, fs)


register_cost_model(NAME, 1.0, _time_once)


def _estimate(x, t, fs, **params):
    # O(n): each event's window plus its recovery search reaches at most the next event's start
    return estimate_seconds(NAME, len(x))


def _derive(x, t, fs, params, value=None):
    if value is None:
        return [("Events", "run a detector first — this block measures the spans it is given", "warn")]
    return [("Events", f"{len(value.starts)} spans to measure", ""),
            ("Recovery level", f"{params['recovery_frac']:g} of the amplitude back from the extremum", "")]


SPEC = register(AdapterSpec(
    name=NAME,
    display_name="Event shape (per-event measures)",
    stage="interrogation",
    category="control",
    page_name="Event shape",
    params=[
        ParamSpec("polarity", str, "drop", "drop (every detector here finds drops), spike, or auto (the window's fastest edge decides; unreliable on windows with context)",
                  choices=list(ES.POLARITIES)),
        ParamSpec("upstream_inverted", bool, False,
                  "The chain inverted the signal before detection (the spike template): report in the recorded frame"),
        ParamSpec("knee_frac", float, ES.KNEE_FRAC, "Knee rule for the end of the fall and the onset (detect5's)",
                  min=0.001, max=1.0),
        ParamSpec("recovery_frac", float, ES.RECOVERY_FRAC,
                  "Recovered when the trace is back this fraction of the amplitude from the extremum", min=0.01, max=1.0),
        ParamSpec("recovery_max_mult", float, ES.RECOVERY_MAX_MULT,
                  "Search for recovery at most this many event widths past the extremum", min=0.5),
        ParamSpec("walk_onset_back", bool, True, "Move the onset back onto the shoulder the event departs from (detect5)"),
        ParamSpec("rose_scale", str, "raw", "What 45° means on the rose (gradients.SLOPE_SCALES)",
                  choices=list(SLOPE_SCALES)),
        ParamSpec("rose_reference_mv_s", float, DEFAULT_SLOPE_REF_MV_S,
                  "The stated reference for the raw scale: 45° = this many mV/s", min=1e-6),
    ],
    run=_run,
    derive=_derive,
    estimate=_estimate,
    input_kind="spanset",
    output_kind="spanset",
    description=(
        "Every shape measure of every event in one block, polarity-neutral: amplitude, precursor, width, "
        "duration, FWHM, recovery time, steepest / onset / chord slope, peakedness. The spans pass through; the "
        "measures ride on the SpanSet as a feature table, with the rule for each printed beside it and the "
        "steepest-slope rose in meta."
    ),
))
