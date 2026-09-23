"""
preprocessing_invert.py
=========================
`preprocessing.invert` — Signal -> Signal, `-x` (fixup-d). Near-trivial and
high value: put it before the drop detector and every spike becomes a drop, so
every existing drop detector is a spike detector for one block's work. The
researcher has trialled exactly this with some success, and `drop_motifs10`'s
manifest already carries an `inverted` pass flag (set false) — this is that
flag as a block.

A chain that inverts before detecting should tell Event shape so
(`upstream_inverted=True`, as the `spike_event_features` template does): the
detector then sees drops, and Event shape reports them in the recorded frame
as the spikes they are.

Why not reuse: no block negates a signal; `preprocessing.detrend` and the
filters preserve polarity by design.
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec
from Adapters.registry import register
from Working.block_cost import estimate_seconds, register_cost_model
from Working.types import Signal

NAME = "preprocessing.invert"


def _run(x, t, fs):
    return AdapterResult(output_kind="signal", value=Signal(x=-np.asarray(x, dtype=float), fs=float(fs)))


register_cost_model(NAME, 1.0, lambda x, fs: -np.asarray(x, dtype=float))


def _estimate(x, t, fs, **params):
    return estimate_seconds(NAME, len(x))


SPEC = register(AdapterSpec(
    name=NAME,
    display_name="Invert (−x)",
    stage="preprocessing",
    category="preprocess",
    page_name="Invert",
    params=[],
    run=_run,
    estimate=_estimate,
    input_kind="signal",
    output_kind="signal",
    description=(
        "Multiplies the signal by −1. Before the drop detector, it turns spikes into drops — every drop detector "
        "becomes a spike detector. Tell Event shape (upstream_inverted) so it reports them as spikes."
    ),
))
