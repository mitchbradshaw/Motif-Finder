"""
interrogation_cycle_shapes.py
===============================
`interrogation.cycle_shapes` — SpanSet -> SpanSet, a feature block (w3-b). Every
cycle of a chain (one event's anchor to the next's) is cut, stretched to one length,
lined up, and sorted into shapes; the event that opens a cycle carries the cycle's
columns. The work is `Working.interrogation.cycle_shapes` (the algorithm, every
adaptation of Colominas & Wu 2023 and its measurements are in its docstring); this file
maps the chain onto it.

* **The waveform** is an optional side input (`waveform`: the root signal, or an earlier
  step's signal). Unbound, cycles are cut from the chain's current signal `x` — usually
  a short-detrended trace that flattens a 30-45 min climb, so the template binds the
  root signal and lets the per-cycle chord remove the drift.
* **Columns** (the event that opens cycle k carries it): `cycle_index`, `cycle_length_s`,
  `cycle_amplitude`, `cycle_group`, `cycle_change`, `cycle_shift_s`, `cycle_corr`,
  `cycle_floor_frac`, `cycle_half_recovery_frac`, and `cycle_omit_reason` ("" when the
  cycle was used). The index, group, change, shift, correlation and omit reason are
  bookkeeping (`Working.types.windowset.BOOKKEEPING_COLUMNS`): where a cycle sits and
  what this block decided, not what it looks like.
* **`write_group`** (default off, as Trains) writes `group` = the cycle group's key with
  `Working.interrogation.intervals.write_group_columns` (`<upstream>/<key>`, the original
  kept in `group_upstream`), so Intervals times each cycle shape on its own. A group that
  did not beat its background null is keyed `<g>~noise_like`, one never tested
  `<g>~untested` (the families' suffixes); with several trains the key is `t<train>:<g>`.
  Events whose cycle was left out, or that open none, share `-1`.
* **Exemplars**: `meta["exemplar_events"]` = `{"<group key without suffix>": <event index
  into the SpanSet>}` — each group's medoid cycle, a member, never an average
  (`meta["exemplar_rule"]`).
* **The drawing payload** for the stacked-cycles picture: `meta["cycle_stack"]` (its form
  is in the core's `cycle_shapes` and in the report).

Why not reuse: `interrogation.event_families` cuts a fixed window around each event and
groups by HDBSCAN; it neither stretches inter-event cycles to one length, nor refines the
anchors, nor asks whether a split is one family that varies. The Library's
`svd_entropy`, SBD, surrogates and group keys are imported, not rewritten.
"""

import numpy as np
import pandas as pd

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec, SideInputSpec
from Adapters.registry import register
from Working.block_cost import estimate_seconds, register_cost_model
from Working.interrogation import cycle_shapes as CS
from Working.interrogation.intervals import write_group_columns
from Working.types import SpanSet

NAME = "interrogation.cycle_shapes"
ADDED = ("cycle_index", "cycle_length_s", "cycle_amplitude", "cycle_group", "cycle_change", "cycle_shift_s",
         "cycle_corr", "cycle_floor_frac", "cycle_half_recovery_frac", "cycle_omit_reason")
#: the calibration chain's cycle length; the estimate assumes real chains have one cycle per ASSUMED_CYCLE_S
CALIBRATION_CYCLE_S = 200.0
ASSUMED_CYCLE_S = 1800.0


def _require(value):
    if value is None:
        raise ValueError(f"{NAME} requires a SpanSet input from a prior step (input_kind='spanset'): put a detector "
                         "(and Event shape, and Trains) before it.")
    if not isinstance(value, SpanSet):
        raise ValueError(f"{NAME} measures the cycles between the events of a SpanSet; got {type(value).__name__}.")
    return value


def _waveform(waveform, x, fs):
    if waveform is None:
        return None
    w = getattr(waveform, "x", None)
    if w is None:
        raise ValueError(f"{NAME}: the 'waveform' side input must be a Signal (the root signal or an earlier step's "
                         f"signal); got {type(waveform).__name__}.")
    w = np.asarray(w, dtype=float).ravel()
    if w.size != len(x):
        raise ValueError(f"{NAME}: the 'waveform' side input has {w.size} samples but the chain's span has {len(x)}; "
                         "bind the root signal or a Signal -> Signal step of the same chain.")
    wfs = float(getattr(waveform, "fs", fs))
    if abs(wfs - float(fs)) > 1e-9 * max(1.0, float(fs)):
        raise ValueError(f"{NAME}: the 'waveform' side input is sampled at {wfs:g} Hz but the chain at {fs:g} Hz.")
    return w


def _run(x, t, fs, anchor="onset", max_cycle_s=0.0, min_cycle_s=0.0, cycle_detrend="chord", n_points=CS.N_POINTS,
         max_shift_frac=CS.MAX_SHIFT_FRAC, max_iter=CS.MAX_ITER, k_max=CS.K_MAX, min_cycles=CS.MIN_CYCLES,
         sigclust_draws=CS.SIGCLUST_DRAWS, null_draws=CS.NULL_DRAWS, n_perm=CS.N_PERM, floor_band=CS.FLOOR_BAND,
         max_nan_frac=CS.MAX_NAN_FRAC, write_group=False, seed=0, value=None, waveform=None, should_cancel=None):
    spans = _require(value)
    up = spans.features
    x = np.asarray(x, dtype=float)
    wf = _waveform(waveform, x, fs)
    res = CS.cycle_shapes(x, fs, spans.starts, spans.ends, up, waveform=wf, anchor=anchor, max_cycle_s=max_cycle_s,
                          min_cycle_s=min_cycle_s, cycle_detrend=cycle_detrend, n_points=n_points,
                          max_shift_frac=max_shift_frac, max_iter=max_iter, k_max=k_max, min_cycles=min_cycles,
                          sigclust_draws=sigclust_draws, null_draws=null_draws, n_perm=n_perm, floor_band=floor_band,
                          max_nan_frac=max_nan_frac, seed=seed, should_cancel=should_cancel)
    cols = dict(res["columns"])
    cols["cycle_omit_reason"] = list(res["omit_reason"])
    has_group = up is not None and "group" in up.columns
    if write_group:
        cols.update(write_group_columns(up, res["group_keys"]))
    added = pd.DataFrame(cols)
    feats = added if up is None else pd.concat(
        [up.reset_index(drop=True).drop(columns=[c for c in added.columns if c in up.columns]), added], axis=1)
    meta = res["meta"]
    meta["write_group"] = bool(write_group)
    if write_group:
        meta["rules"] = meta["rules"] + [{"name": "group", "rule": (
            "written = the cycle group's key ('<g>~noise_like' for a group no more coherent than its background "
            "null, '<g>~untested' for one no null was drawn for; 't<train>:<g>' with several trains; -1 for an "
            "event whose cycle was left out or that opens none: an unmarked key was tested and passed)"
            + (" prefixed by the upstream group ('<group>/<key>'; the original is kept in group_upstream)"
               if has_group else "")
            + ", so Intervals downstream times each cycle shape on its own")}]
    return AdapterResult(
        output_kind="spanset",
        value=SpanSet(starts=tuple(spans.starts), ends=tuple(spans.ends), labels=spans.labels, scores=spans.scores,
                      features=feats),
        meta=meta,
    )


def _time_once(x, fs):
    # a chain of drops every CALIBRATION_CYCLE_S over the calibration signal, at the defaults (null included)
    n = len(x)
    period = int(CALIBRATION_CYCLE_S)
    starts = np.arange(period, n - period, period)

    y = np.asarray(x, dtype=float) * 0.1
    for s in starts:
        y[s:s + period] -= np.exp(-np.arange(period) / (0.1 * period))
    CS.cycle_shapes(y, 1.0, starts, starts + 10, None)


# Exponent 1.4, measured (2026-10-14, a loaded 20-thread machine): the calibration chain (98 cycles) took 7.3 s,
# 400 cycles at the defaults 55 s fresh and 53 s warm; with exponent 1 the estimate said 29 s. The cost grows faster
# than the cycles because the Gram matrices and k-means grow with min(cycles, n_points) as well.
register_cost_model(NAME, 1.4, _time_once)


def _estimate(x, t, fs, **params):
    # the cost is per cycle, not per sample: it assumes one cycle per ASSUMED_CYCLE_S of span (the real chains'
    # 25-45 min) and scales the calibration (one cycle per CALIBRATION_CYCLE_S at 1 Hz) to that density
    span_s = len(x) / float(fs)
    return estimate_seconds(NAME, int(span_s * CALIBRATION_CYCLE_S / ASSUMED_CYCLE_S))


SPEC = register(AdapterSpec(
    name=NAME,
    display_name="Cycle shapes (stretch each cycle of a chain, sort the shapes, find where they change)",
    stage="interrogation",
    category="cluster",
    page_name="Cycle shapes",
    params=[
        ParamSpec("anchor", str, "onset",
                  "Where a cycle starts: each event's measured onset (Event shape upstream) or its span start",
                  choices=list(CS.ANCHORS)),
        ParamSpec("max_cycle_s", float, 0.0,
                  "A cycle longer than this (s) is a gap, not a cycle: left out and counted. 0 = auto: longer than "
                  f"{CS.AUTO_MAX_MULT:g} x the running median of the {CS.LOCAL_CYCLES} cycle lengths around it (a "
                  "missed detection reads ~2x)", min=0.0, max=1e7),
        ParamSpec("min_cycle_s", float, 0.0,
                  f"A cycle shorter than this (s) is a split drop: left out and counted. 0 = auto: shorter than "
                  f"{CS.AUTO_MIN_MULT:g} x that running median", min=0.0, max=1e7),
        ParamSpec("cycle_detrend", str, "chord",
                  "chord: subtract the straight line between the pre-drop levels at the cycle's two ends (the "
                  "median of the 2 % before each anchor), so drift does not tilt a cycle; none: cut as is",
                  choices=list(CS.DETRENDS)),
        ParamSpec("n_points", int, CS.N_POINTS, "Points every cycle is stretched to (the Library's 256)",
                  min=32, max=2048),
        ParamSpec("max_shift_frac", float, CS.MAX_SHIFT_FRAC,
                  "Most a cycle may be shifted to line up, as a fraction of its length (both the anchor refinement "
                  "and the alignment)", min=0.0, max=0.4),
        ParamSpec("max_iter", int, CS.MAX_ITER,
                  "Most refinement rounds (the paper's examples needed 1-8); a round is kept only while the SVD "
                  "entropy falls by more than its own bootstrap spread", min=0, max=50),
        ParamSpec("k_max", int, CS.K_MAX, "Most shape groups one sequence may be split into", min=2, max=20),
        ParamSpec("min_cycles", int, CS.MIN_CYCLES,
                  "Fewest usable cycles a sequence needs before it is grouped (and the smallest group a split may "
                  "make)", min=4, max=100000),
        ParamSpec("sigclust_draws", int, CS.SIGCLUST_DRAWS,
                  "Gaussian draws of SigClust's null (the stack's own covariance). Reported only: it does not "
                  "decide K", min=0, max=5000),
        ParamSpec("null_draws", int, CS.NULL_DRAWS,
                  "Background-null draws: pseudo-cycles cut where no event lies, through the same pipeline; they "
                  "calibrate the split (K) and the groups' verdict. 0 = untested (every key ~untested; K is then "
                  "calibrated on 20 phase copies of the cycles)", min=0, max=1000),
        ParamSpec("n_perm", int, CS.N_PERM, "Shuffles of the cycle order for the order test", min=0, max=100000),
        ParamSpec("floor_band", float, CS.FLOOR_BAND,
                  "The floor is the lowest this fraction of a cycle's range (a placeholder: 0.25)", min=0.01,
                  max=0.9),
        ParamSpec("max_nan_frac", float, CS.MAX_NAN_FRAC,
                  "Leave out a cycle with more than this fraction of missing samples (fewer are interpolated)",
                  min=0.0, max=1.0),
        ParamSpec("write_group", bool, False,
                  "Write group = the cycle group, so Intervals after this block times each cycle shape on its own"),
        ParamSpec("seed", int, 0, "Seed of every random draw (nulls, k-means starts, the stack sample)", min=0,
                  max=2 ** 31 - 1),
    ],
    run=_run,
    estimate=_estimate,
    input_kind="spanset",
    output_kind="spanset",
    side_inputs=[SideInputSpec(name="waveform", type_kind="signal", sources=["root_signal", "earlier_step"],
                               required=False)],
    description=(
        "EXPERIMENTAL: not yet run on a real recording. "
        "For a chain of drops: every cycle (one drop to the next) is stretched to one length, lined up, and "
        "sorted into shapes (Colominas & Wu 2023, the back half), so you can see whether all cycles share one "
        "shape or a few kinds, and where in the chain the kind changes. More than one kind is claimed only when "
        "the best split beats the same split on pseudo-cycles cut from the recording's quiet stretches and is two "
        "modes along its own direction - a shape that drifts steadily (a plateau that lengthens) stays one "
        "family, visible in the per-cycle measures. A chain that fills its span has no quiet stretch: its "
        "verdicts are then untested and said so. Per "
        "cycle: length, size, the share of the cycle on its floor (a sharkfin sits there for 1/2-2/3) and where "
        "it is half back. Coherence is SVD entropy, sigma^2 first and the paper's eq. 17 beside it, each against "
        "pseudo-cycles cut from the recording's own quiet stretches; a group no better than those is marked "
        "~noise_like. Bind 'waveform' to the root signal when the detector ran on a short-detrended trace. Tune "
        "max_cycle_s first if many cycles are left out as gaps. Put it after Event shape and Trains (maxinterval at "
        "chain-scale gaps), before Intervals."
    ),
))
