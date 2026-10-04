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

**The scale bank (fixup-v).** `scales` searches several stretched copies of
the exemplar: the exemplar resampled to `round(m * s)` samples for each factor
`s`, `stumpy.match` at each length. A z-normalised Euclidean distance grows
with the square root of the length it is measured over, so a raw distance at
1.25x is not comparable with one at 0.8x; every distance in a bank is put on
the native length's footing, `d * sqrt(m / L)`, which leaves a 1x distance
exactly as it was and lets one cut mean one thing across lengths. Matches of
two different lengths that overlap are reduced by `overlap` (the Seed page's
policy: `lowest` distance wins, the `first` onset wins, or keep `all`); two
matches of one length are left to `stumpy.match`'s own exclusion zone. A match
is as long as the copy that found it, and its label says its scale
(`match3@1.25x`). The default bank, `"1"`, is the search this block always
ran, byte for byte, and a recipe that does not name `scales` hashes as before.

**The exclusion zone (fixup-AD, Round 11).** `exclusion` is the trivial-match
guard as a fraction of the query's length: two matches closer than
`ceil(exclusion * m)` samples are one match. Default **m/2** (§7.6). Until
2026-10-05 the block exposed none, so `stumpy.match` ran under its own m/4 while
the Seed page printed §7.6's m/2 beside it. `stumpy.match` takes no zone
argument — it reads `config.STUMPY_EXCL_ZONE_DENOM` — so the zone is passed by
setting that denominator to `1 / exclusion` for the call, under a lock, and
putting it back.
"""

import threading

import numpy as np
import stumpy

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec, SideInputSpec
from Adapters.registry import register
from Working.types import SpanSet


#: §7.6 / Round 11: the exclusion zone is half the exemplar.
DEFAULT_EXCLUSION = 0.5
#: The zone is a fraction of m in (0, MAX_EXCLUSION].
MAX_EXCLUSION = 2.0
_STUMPY_CONFIG_LOCK = threading.Lock()


def check_exclusion(exclusion):
    """The zone as a float, or a ValueError naming what a zone must be."""
    try:
        v = float(exclusion)
    except (TypeError, ValueError):
        raise ValueError(f"the exclusion zone {exclusion!r} is not a number (a fraction of m, e.g. 0.5).") from None
    if not np.isfinite(v) or v <= 0 or v > MAX_EXCLUSION:
        raise ValueError(f"the exclusion zone must be a fraction of m in (0, {MAX_EXCLUSION:g}], got {exclusion!r}.")
    return v


def exclusion_samples(m, exclusion=DEFAULT_EXCLUSION):
    """The zone in samples for a query of `m` samples — stumpy's own rounding."""
    return int(np.ceil(int(m) * check_exclusion(exclusion)))


def match_exemplar(x, exemplar_x, k=10, max_distance=None, exclusion=DEFAULT_EXCLUSION):
    """`(n_matches, 2)` array of `[distance, index]`, closest first, no two
    within `ceil(exclusion * m)` samples of each other."""
    excl = check_exclusion(exclusion)
    x = np.asarray(x, dtype=float).ravel()
    q = np.asarray(exemplar_x, dtype=float).ravel()
    if len(q) < 3:
        raise ValueError(f"the exemplar has {len(q)} samples; a match needs at least 3.")
    if len(q) > len(x):
        raise ValueError(f"the exemplar ({len(q)} samples) is longer than the span ({len(x)}).")
    md = float(max_distance) if max_distance is not None else np.inf
    with _STUMPY_CONFIG_LOCK:
        before = stumpy.config.STUMPY_EXCL_ZONE_DENOM
        stumpy.config.STUMPY_EXCL_ZONE_DENOM = 1.0 / excl
        try:
            return stumpy.match(q, x, max_matches=int(k), max_distance=md)
        finally:
            stumpy.config.STUMPY_EXCL_ZONE_DENOM = before


OVERLAP_POLICIES = ("lowest", "first", "all")


def parse_scales(text):
    """`"0.8, 1, 1.25"` → `(0.8, 1.0, 1.25)`: sorted, de-duplicated, every factor
    positive. A list or tuple of numbers is taken as it is."""
    if isinstance(text, (list, tuple)):
        parts = [str(v) for v in text]
    else:
        parts = [p.strip() for p in str(text or "").split(",") if p.strip()]
    if not parts:
        raise ValueError("a scale bank needs at least one factor (e.g. '0.8,1,1.25').")
    out = set()
    for p in parts:
        try:
            v = float(p)
        except ValueError:
            raise ValueError(f"scale factor {p!r} is not a number.") from None
        if not np.isfinite(v) or v <= 0:
            raise ValueError(f"scale factor {p!r} must be a positive number.")
        out.add(round(v, 6))
    return tuple(sorted(out))


def format_scales(scales):
    """The recipe's spelling of a bank: `(0.8, 1.0, 1.25)` → `"0.8,1,1.25"`."""
    return ",".join(f"{float(s):g}" for s in parse_scales(scales))


def reduce_overlaps(rows, policy="lowest"):
    """Drop a match that overlaps a match of a DIFFERENT length which wins under
    `policy`. Two matches of one length are `stumpy.match`'s business (its
    exclusion zone), not this policy's. `rows` are dicts with `index`, `length`
    and `distance`; the survivors come back closest first."""
    if policy not in OVERLAP_POLICIES:
        raise ValueError(f"unknown overlap policy {policy!r}; one of {OVERLAP_POLICIES}.")
    rows = [dict(r) for r in rows]
    if policy == "all":
        return sorted(rows, key=lambda r: (r["distance"], r["index"]))
    order = (lambda r: (r["distance"], r["index"])) if policy == "lowest" else (lambda r: (r["index"], r["distance"]))
    kept = []
    for r in sorted(rows, key=order):
        a, b = r["index"], r["index"] + r["length"]
        if any(k["length"] != r["length"] and a < k["index"] + k["length"] and k["index"] < b for k in kept):
            continue
        kept.append(r)
    return sorted(kept, key=lambda r: (r["distance"], r["index"]))


def match_exemplar_bank(x, exemplar_x, scales, k=10, max_distance=None, overlap="lowest",
                        exclusion=DEFAULT_EXCLUSION):
    """The bank: `[{index, length, scale, distance}]`, closest first, at most `k`.

    `distance` is on the native length's footing (`d * sqrt(m / L)`), and so is
    `max_distance`. `k` is applied per length and again after the reduction."""
    from Working.distances import resample_to_length

    x = np.asarray(x, dtype=float).ravel()
    q = np.asarray(exemplar_x, dtype=float).ravel()
    m = len(q)
    rows = []
    for s in parse_scales(scales):
        length = int(round(m * s))
        qs = q if length == m else resample_to_length(q, length)
        footing = float(np.sqrt(m / length))
        md = None if max_distance is None else float(max_distance) / footing
        for d, i in match_exemplar(x, qs, k=k, max_distance=md, exclusion=exclusion):
            rows.append({"index": int(i), "length": length, "scale": float(s), "distance": float(d) * footing})
    return reduce_overlaps(rows, overlap)[:int(k)]


def _run(x, t, fs, k=10, max_distance=0.0, exemplar=None, scales="1", overlap="lowest",
         exclusion=DEFAULT_EXCLUSION):
    if exemplar is None:
        raise ValueError("detection.seed_matches needs its `exemplar` side input bound (a Signal: a library exemplar, the root signal or an earlier step).")
    q = np.asarray(exemplar.x, dtype=float).ravel()
    excl = check_exclusion(exclusion)
    zone = {"exclusion": excl, "exclusion_samples": exclusion_samples(len(q), excl)}
    bank = parse_scales(scales)
    if bank != (1.0,):
        rows = match_exemplar_bank(x, q, bank, k=k, overlap=overlap, exclusion=excl,
                                   max_distance=(max_distance if max_distance and max_distance > 0 else None))
        per_scale = {float(s): 0 for s in bank}
        for r in rows:
            per_scale[r["scale"]] += 1
        return AdapterResult(
            output_kind="spanset",
            value=SpanSet(starts=tuple(r["index"] for r in rows),
                          ends=tuple(r["index"] + r["length"] for r in rows),
                          labels=tuple(f"match{i}@{r['scale']:g}x" for i, r in enumerate(rows)),
                          scores=tuple(r["distance"] for r in rows)),
            meta={"m": int(len(q)), "exemplar_fs": float(getattr(exemplar, "fs", fs)), "n_matches": len(rows),
                  "distances": [r["distance"] for r in rows], "scales": list(bank),
                  "per_scale": per_scale, "overlap": overlap, **zone,
                  "footing": "every distance is d * sqrt(m / L): on the native length's footing"},
        )
    matches = match_exemplar(x, q, k=k, exclusion=excl,
                             max_distance=(max_distance if max_distance and max_distance > 0 else None))
    m = len(q)
    starts = tuple(int(row[1]) for row in matches)
    return AdapterResult(
        output_kind="spanset",
        value=SpanSet(starts=starts, ends=tuple(s + m for s in starts),
                      labels=tuple(f"match{i}" for i in range(len(starts))),
                      scores=tuple(float(row[0]) for row in matches)),
        meta={"m": int(m), "exemplar_fs": float(getattr(exemplar, "fs", fs)), "n_matches": len(starts),
              "distances": [float(r[0]) for r in matches], **zone},
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
        ParamSpec("scales", str, "1", "Scale bank: the exemplar stretched to each factor, comma-separated "
                  "(e.g. '0.8,1,1.25'); '1' searches at the native length only"),
        ParamSpec("overlap", str, "lowest", "When matches of two lengths overlap, which survives",
                  choices=list(OVERLAP_POLICIES)),
        ParamSpec("exclusion", float, DEFAULT_EXCLUSION, "Exclusion zone as a fraction of the exemplar's length: "
                  "two matches closer than this are one (0.5 = m/2, §7.6)", min=0.01, max=MAX_EXCLUSION),
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
