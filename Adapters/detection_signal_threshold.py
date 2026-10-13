"""
detection_signal_threshold.py
===============================
Generic `Signal` -> `SpanSet` block: the sibling of `detection.threshold`
(Scores -> SpanSet) for a chain that has no scoring stage. It cuts the
chain's CURRENT signal — after any Signal -> Signal block, so typically the
baseline-removed trace — at an absolute level in the signal's own units, and
emits the contiguous runs past that level as spans. The simplest detector
the tool can express: "every stretch where the trace falls under -5 mV".

Three ways to read the cut (`direction`):

    above   x > threshold            a rise over the baseline
    below   x < threshold            a drop under it (threshold is then negative)
    either  |x| > |threshold|        an excursion on either side of zero

A span's score is how far past the cut it reaches, in the signal's units
(`max(x) - threshold`, `threshold - min(x)`, `max|x| - |threshold|`), so a
stronger event scores higher whichever side the cut is on and the slideshow
sorts the same way for a rise and for a drop. A NaN sample compares False on
every side and never belongs to a span. No crossing is an empty SpanSet, not
an error. `Working.execution.execute_recipe` writes the spans to
`detections`, span offset added, like any other spanset.

The run-finding is `detection.threshold`'s own helper (`spans_from_mask`),
so the two blocks are one rule applied to two types — `tests/
test_adapter_signal_threshold.py` checks they agree span for span when fed
the same values.

Drawn by the standard (`docs/BLOCK_INTEGRATION.md` §2): the SpanSet view
through the `signal->spanset` modifier; because the cut is one `float`
parameter named `threshold`, the block page draws it on the trace and lets
the researcher drag it.
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.detection_threshold import spans_from_mask
from Adapters.registry import register
from Working.types import SpanSet

DIRECTIONS = ["above", "below", "either"]


def _mask_and_excursion(x, threshold, direction):
    """The boolean mask of samples past the cut, and the rule that scores one
    span's samples by how far past it they reach."""
    if direction == "above":
        return x > threshold, lambda seg: float(np.max(seg)) - threshold
    if direction == "below":
        return x < threshold, lambda seg: threshold - float(np.min(seg))
    if direction == "either":
        level = abs(threshold)
        return np.abs(x) > level, lambda seg: float(np.max(np.abs(seg))) - level
    raise ValueError(f"detection.signal_threshold: direction must be one of {DIRECTIONS}, got {direction!r}")


def _run(x, t, fs, threshold=0.0, direction="above"):
    xs = np.asarray(x, dtype=float).ravel()
    threshold = float(threshold)
    with np.errstate(invalid="ignore"):          # a NaN sample compares False: never in a span
        mask, excursion = _mask_and_excursion(xs, threshold, direction)
    starts, ends = spans_from_mask(mask)
    scores = tuple(excursion(xs[s:e]) for s, e in zip(starts, ends))
    return AdapterResult(
        output_kind="spanset",
        value=SpanSet(
            starts=tuple(int(s) for s in starts),
            ends=tuple(int(e) for e in ends),
            scores=scores,
        ),
        meta={
            "n_spans": int(len(starts)),
            "n_samples": int(len(xs)),
            "n_nan": int(np.isnan(xs).sum()),
            "threshold": threshold,
            "direction": direction,
        },
    )


SPEC = register(AdapterSpec(
    name="detection.signal_threshold",
    display_name="Threshold (Signal -> SpanSet)",
    stage="detection",
    category="detect",
    page_name="Signal threshold to spans",
    params=[
        ParamSpec("threshold", float, 0.0,
                  "The cut: an absolute level in the signal's own units as stored "
                  "(M2 is stored in volts, so -0.005 reads as -5 mV)"),
        ParamSpec("direction", str, "above",
                  "Which side of the cut counts: `above` keeps x > threshold, `below` keeps "
                  "x < threshold (a drop after baseline removal), `either` keeps |x| > |threshold|",
                  choices=list(DIRECTIONS)),
    ],
    run=_run,
    input_kind="signal",
    output_kind="spanset",
    plot=None,
    description=(
        "Generic block: cuts the chain's current signal at an absolute level in its own "
        "units and keeps the contiguous runs above it, below it, or past it on either side "
        "of zero, written to `detections`. Put baseline removal before it; a span scores by "
        "how far past the cut it reaches."
    ),
))
