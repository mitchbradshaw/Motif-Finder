"""
detection_seed_matches.py
===========================
Signal + an exemplar → SpanSet: where else does this shape occur?

Wraps `stumpy.match` the way `Working.Detection.matrix_profiling.segments.
seed_matches` does — the distance from one query window to every position
in the chain's signal, FFT-based, fast enough to run interactively on a full
channel. The query is the block's one side input, `exemplar`, a `Signal`
bound at composition time to a library exemplar, the root signal or an
earlier step (`Adapters.base.SideInputSpec`; resolved by
`Working.side_inputs`). Discovery's seeded search (prompt 04) calls this
block with a `library_exemplar` binding and a template mode of `carry` or
`rebind` (`Working/templates.py`).

Signature kept deliberately small: `run(x, t, fs, k, max_distance,
exemplar)` → the `k` best matches as spans of the exemplar's length, scored
by z-normalised distance (closest first), labelled `match<rank>`.
"""

import numpy as np
import stumpy

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec, SideInputSpec
from Adapters.registry import register
from Working.types import SpanSet


def match_exemplar(x, exemplar_x, k=10, max_distance=None):
    """`(n_matches, 2)` array of `[distance, index]`, closest first."""
    x = np.asarray(x, dtype=float).ravel()
    q = np.asarray(exemplar_x, dtype=float).ravel()
    if len(q) < 3:
        raise ValueError(f"the exemplar has {len(q)} samples; a match needs at least 3.")
    if len(q) > len(x):
        raise ValueError(f"the exemplar ({len(q)} samples) is longer than the span ({len(x)}).")
    md = float(max_distance) if max_distance is not None else np.inf
    return stumpy.match(q, x, max_matches=int(k), max_distance=md)


def _run(x, t, fs, k=10, max_distance=0.0, exemplar=None):
    if exemplar is None:
        raise ValueError("detection.seed_matches needs its `exemplar` side input bound (a Signal: a library exemplar, the root signal or an earlier step).")
    q = np.asarray(exemplar.x, dtype=float).ravel()
    matches = match_exemplar(x, q, k=k, max_distance=(max_distance if max_distance and max_distance > 0 else None))
    m = len(q)
    starts = tuple(int(row[1]) for row in matches)
    return AdapterResult(
        output_kind="spanset",
        value=SpanSet(starts=starts, ends=tuple(s + m for s in starts),
                      labels=tuple(f"match{i}" for i in range(len(starts))),
                      scores=tuple(float(row[0]) for row in matches)),
        meta={"m": int(m), "exemplar_fs": float(getattr(exemplar, "fs", fs)), "n_matches": len(starts),
              "distances": [float(r[0]) for r in matches]},
    )


SPEC = register(AdapterSpec(
    name="detection.seed_matches",
    display_name="Seed matches (Signal + exemplar -> SpanSet)",
    stage="detection",
    category="detect",
    page_name="Seeded search",
    params=[
        ParamSpec("k", int, 10, "How many matches to keep (closest first)", min=1, max=10000),
        ParamSpec("max_distance", float, 0.0, "Z-normalised distance cutoff (0 = none)", min=0.0),
    ],
    run=_run,
    input_kind="signal",
    output_kind="spanset",
    side_inputs=[SideInputSpec(name="exemplar", type_kind="signal",
                               sources=["library_exemplar", "root_signal", "earlier_step"])],
    description=(
        "The k closest occurrences of an exemplar shape anywhere in the span "
        "(stumpy.match, z-normalised). The exemplar is a side input bound to a library "
        "entry, the root signal or an earlier step."
    ),
))
