"""
detection_spike_v1.py
========================
Adapter for `Working.Detection.analysis.spike_analysis.spike_detection_v1`
(Adamatzky 2023's neighbourhood-average spike detector). Not to be merged with
`detection.dehshibi_spikes` (Dehshibi's wavelet route): two papers, two blocks.

fixup-ak (2026-10-15), from the researcher's "what does it do, why does it not
pull spikes out, what do I tune":

* **The spans are the spikes.** One span per kept spike, ``span_s`` wide
  (0 = the refractory gap d), centred on its index and clipped to the span in
  hand. Before, the block returned the stretches BETWEEN spikes (a "policy" for
  turning points into intervals), so the page drew the quiet gaps as its
  detections. `meta["spike_indices"]` / `n_spikes` are kept, and
  `meta["events"]` (one ``{onset_idx, trough_idx}`` per span, both the spike's
  index, span-relative) marks each spike inside its span on the SpanSet view.
* **Either direction.** The core's test is signed with a ``polarity``
  (`spike_analysis` docstring: the paper's ``|x| - |a|`` saw dips or rises by
  the sign of the DC baseline).
* **delta in millivolts.** ``delta_mv`` is converted to the samples' stored
  unit by the recording's declared unit (`Working.units.read_as_mv`, the way
  `detection.drop_detection` reads its millivolts). An undeclared unit is read
  as volts and `meta["units_note"]` and the readout say so - the researcher's
  2026-10-15 choice for undeclared recordings (QUESTIONS.md Q20), used here
  rather than a refusal (see the fixup-ak report). The old unitless ``delta``
  is gone, so a saved recipe that still names it is refused by
  `validate_params` instead of silently changing meaning by x1000.

Default delta_mv = 1.0 mV is a PLACEHOLDER, not the paper's value: the paper's
delta = 0.01 is in its logger's millivolts (S. commune, spikes ~0.4 mV); on M2
(per-sample noise ~0.025 mV MAD, drops 1.2-98 mV, median 9 mV) 0.01 mV fires on
noise. 1 mV sits under the smallest catalogued M2 drop and ~8x the local
wander of an AR(1)/random-walk background at M2's noise level.
"""

from Adapters.base import AdapterSpec, AdapterResult, ParamSpec
from Adapters.registry import register
from Adapters.detection_stage_encoding import units_row
from Working.Detection.analysis.spike_analysis import (
    POLARITIES, refractory_filter, spike_candidates, spike_deviation,
)
from Working.types import SpanSet
from Working.units import VOLTS, read_as_mv

import numpy as np

FACE = ("Compares every sample with the average of its neighbours and calls it a spike when it stands out "
        "from that local average by more than delta_mv (in mV); spikes closer than d samples are thinned to one.")

DETAIL = (
    "Adamatzky's 2023 spike rule. What to tune: delta_mv first - how far (in millivolts) a sample must stand from "
    "its local average; raise it if it fires on noise, lower it if it misses spikes you can see. Then width (w): "
    "the local average spans 4w+1 samples, so it sees changes faster than that and is blind to slower ones - a drop "
    "that takes minutes is mostly invisible to it (use Drop detection for those). Then d: how close two spikes may "
    "sit before the later one is dropped. polarity picks rises (up), dips (down) or both. Each span drawn is one "
    "spike, span_s wide (0 = d samples), the spike marked inside it."
)

MARK = "the spike's sample inside its span"


def _rules(width, delta_mv, d, polarity, span_len, fs):
    test = {"both": "|x - a| > delta", "up": "x - a > delta", "down": "x - a < -delta"}[polarity]
    return [
        {"name": "local_mean", "rule": f"a = the mean of the {4 * width + 1} samples around each sample "
                                       f"(w = {width}: {(4 * width + 1) / fs:g} s), over the finite ones; the "
                                       "paper's 1/(4w) is replaced by the true mean so a baseline away from zero "
                                       "adds no bias"},
        {"name": "spike", "rule": f"{test}, delta = {delta_mv:g} mV converted to the stored unit; the sign of the "
                                  "baseline no longer decides which direction is seen"},
        {"name": "refractory_gap", "rule": f"of spikes closer than d = {d} samples ({d / fs:g} s), the first is kept"},
        {"name": "span", "rule": f"each spike is one span of {span_len} samples ({span_len / fs:g} s) centred on it, "
                                 "clipped to the span in hand"},
    ]


def _span_len(span_s, d, fs):
    return int(d) if not span_s else max(1, int(round(float(span_s) * float(fs))))


def _run(x, t, fs, delta_mv=1.0, width=20, d=30, polarity="both", span_s=0.0, units=VOLTS):
    to_mv, units_note = read_as_mv(units)
    delta = float(delta_mv) / to_mv
    x = np.asarray(x, dtype=float)
    n = len(x)
    dev = spike_deviation(x, width)
    spikes = refractory_filter(spike_candidates(dev, delta, polarity), d)
    L = _span_len(span_s, d, fs)
    half = L // 2
    starts = np.maximum(0, spikes - half)
    ends = np.minimum(n, spikes - half + L)
    sign = np.sign(dev[spikes]) if spikes.size else np.array([])
    idx = [int(i) for i in spikes]
    return AdapterResult(
        output_kind="spanset",
        value=SpanSet(starts=tuple(int(s) for s in starts), ends=tuple(int(e) for e in ends)),
        meta={
            "n_spikes": len(idx), "spike_indices": idx,
            "n_up": int((sign > 0).sum()), "n_down": int((sign < 0).sum()),
            "events": [{"onset_idx": i, "trough_idx": i} for i in idx],
            "delta_mv": float(delta_mv), "delta_stored": delta, "units": units, "to_mv": float(to_mv),
            "units_note": units_note, "polarity": polarity, "span_samples": L,
            "n_missing": int((~np.isfinite(x)).sum()),
            "rules": _rules(int(width), float(delta_mv), int(d), polarity, L, float(fs)),
            "explain": {"face": FACE, "detail": DETAIL, "mark": MARK},
        },
    )


def _derive(x, t, fs, params, value=None, units=VOLTS):
    """The readout beside the parameters: the unit, delta as the block will cut in the stored unit, and the
    local window and span in seconds. O(1) - no detection runs here."""
    to_mv, note = read_as_mv(units)
    stored = units if note is None else "V (read as volts)"
    w, d = int(params["width"]), int(params["d"])
    L = _span_len(params["span_s"], d, fs)
    return [
        units_row(units),
        ("δ as stored", f"{params['delta_mv']:g} mV = {params['delta_mv'] / to_mv:.6g} {stored}", ""),
        ("Local average", f"{4 * w + 1} samples = {(4 * w + 1) / fs:g} s", ""),
        ("Refractory gap", f"{d} samples = {d / fs:g} s", ""),
        ("Span per spike", f"{L} samples = {L / fs:g} s", ""),
    ]


SPEC = register(AdapterSpec(
    name="detection.spike_v1",
    display_name="Spike detection (Adamatzky 2023)",
    stage="detection",
    category="detect",
    page_name="Spike detection (v1)",
    params=[
        ParamSpec("delta_mv", float, 1.0,
                  "Tune this first. How far (mV) a sample must stand from its local average to be a spike; "
                  "converted by the recording's declared unit. 1 mV is a placeholder (the paper's 0.01 is in its "
                  "logger's mV and fires on M2's noise)", min=0.0),
        ParamSpec("width", int, 20, "Neighbourhood half-width w (samples): the local average spans 4w+1 samples; "
                                    "changes slower than that are invisible to this test (paper: 20)", min=1),
        ParamSpec("d", int, 30, "Refractory gap (samples): of spikes closer than this, the first is kept "
                                "(paper: 30)", min=1),
        ParamSpec("polarity", str, "both", "Which direction counts: both, up (rises) or down (dips)",
                  choices=list(POLARITIES)),
        ParamSpec("span_s", float, 0.0, "Width of the span drawn round each spike, seconds; 0 = the refractory "
                                        "gap d", min=0.0),
    ],
    run=_run,
    derive=_derive,
    input_kind="signal",
    output_kind="spanset",
    plot=None,
    description=(
        FACE + " Tune delta_mv first (raise it if it fires on noise, lower it if it misses spikes you can see), "
        "then width (how local the average is; it is blind to changes slower than 4w+1 samples, so use Drop "
        "detection for slow drops), then d. Each span is one spike, marked inside it."
    ),
))
