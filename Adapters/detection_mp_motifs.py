"""
detection_mp_motifs.py
========================
Scores → SpanSet: motif GROUPS from a matrix profile.

Wraps `Working.Detection.matrix_profiling.motif_groups.build_motif_groups`
— the seed-and-exclude walk of `argsort(mp)` with `stumpy.match` per seed —
so the browser's motif list is a chain step: `detection.matrix_profile →
detection.mp_motifs`. Every group's seed window and each of its neighbours
becomes one span of length `m`, labelled `G<k>:seed` / `G<k>:nn<j>` (k = the
group's rank, most similar first) and scored by its z-normalised distance
(the seed carries its profile value). The group structure rides in `meta`.

`m` (the window length in samples) is recovered from the profile itself:
`detection.matrix_profile` pads its `len(x) − m + 1` values with NaN to the
span length, so `m = nan_tail + 1`. Pass `window_min` to override when a
Scores came from elsewhere.

The persistence the browser used (`persist_motif_groups` → one `detections`
row per group) is not repeated here: the executor writes every span of a
SpanSet to `detections`, which is the same table and now also carries the
neighbours.
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.Detection.matrix_profiling.motif_groups import build_motif_groups
from Working.types import SpanSet


def window_from_profile(values, fs, window_min=0.0):
    """`m` for a Scores that is a NaN-padded matrix profile."""
    if window_min and window_min > 0:
        return int(round(window_min * 60 * float(fs)))
    v = np.asarray(values, dtype=float)
    nan_tail = int(np.isnan(v[::-1]).cumprod().sum())
    return nan_tail + 1


def _run(x, t, fs, max_motifs=5, n_neighbors=3, max_distance=0.0, window_min=0.0, value=None):
    if value is None:
        raise ValueError("detection.mp_motifs requires a Scores input from a prior step (input_kind='scores') — put Matrix profile before it.")
    x = np.asarray(x, dtype=float).ravel()
    vals = np.asarray(value.values, dtype=float).ravel()
    if len(vals) != len(x):
        raise ValueError(f"Scores has {len(vals)} values for a {len(x)}-sample span; they must align.")
    m = window_from_profile(vals, fs, window_min)
    if m < 3 or m >= len(x):
        raise ValueError(f"recovered window m={m} samples is not usable on a {len(x)}-sample span; pass window_min.")
    mp = vals[:len(x) - m + 1]
    groups = build_motif_groups(
        x, mp, m, max_motifs=int(max_motifs), n_neighbors=int(n_neighbors),
        max_distance=(float(max_distance) if max_distance and max_distance > 0 else None),
    )
    starts, ends, labels, scores = [], [], [], []
    for k, g in enumerate(groups):
        starts.append(int(g["seed_idx"])); ends.append(int(g["seed_idx"]) + m)
        labels.append(f"G{k}:seed"); scores.append(float(g["mp_distance"]))
        for j, (idx, dist) in enumerate(g["neighbours"]):
            if int(idx) == int(g["seed_idx"]):
                continue        # stumpy.match reports the query itself at distance 0; not a second span
            starts.append(int(idx)); ends.append(int(idx) + m)
            labels.append(f"G{k}:nn{j}"); scores.append(float(dist))
    return AdapterResult(
        output_kind="spanset",
        value=SpanSet(starts=tuple(starts), ends=tuple(ends), labels=tuple(labels), scores=tuple(scores)),
        meta={"m": int(m), "n_groups": len(groups),
              "groups": [{"rank": k, "seed_idx": int(g["seed_idx"]), "mp_distance": float(g["mp_distance"]),
                          "neighbours": [[int(i), float(d)] for i, d in g["neighbours"]]} for k, g in enumerate(groups)]},
    )


def _derive(x, t, fs, params, value=None):
    if value is None:
        return [("Window m", "run the matrix profile first", "warn")]
    m = window_from_profile(value.values, fs, params["window_min"])
    return [("Window m", f"{m} samples · {m / float(fs):.0f} s", ""),
            ("Groups × neighbours", f"{params['max_motifs']} × {params['n_neighbors']}", "")]


SPEC = register(AdapterSpec(
    name="detection.mp_motifs",
    display_name="Motif groups from a matrix profile (Scores -> SpanSet)",
    stage="detection",
    category="detect",
    page_name="Motif groups",
    params=[
        ParamSpec("max_motifs", int, 5, "How many groups to extract (most similar first)", min=1, max=200),
        ParamSpec("n_neighbors", int, 3, "Nearest neighbours retrieved per seed", min=1, max=50),
        ParamSpec("max_distance", float, 0.0, "Distance cutoff for a neighbour (0 = none)", min=0.0),
        ParamSpec("window_min", float, 0.0, "Window length in minutes (0 = recover from the profile's NaN tail)", min=0.0),
    ],
    run=_run,
    derive=_derive,
    input_kind="scores",
    output_kind="spanset",
    description=(
        "Seed-and-exclude motif groups over a matrix profile: each group is its seed "
        "window plus its nearest neighbours, all emitted as spans labelled by group."
    ),
))
