"""
catalogue_shape_families.py
=============================
`catalogue.shape_families` — WindowSet -> Grouping (w2-e): the Library's clustering
(Ward, k-Shape, HDBSCAN — whatever the grouping registry offers for its
`shape-distance` basis) on a chain's windows, by the Library's own engine. The work
is `Working.Catalogue.shape_families` (one implementation, two surfaces: the
researcher's Q3); this file maps the chain onto it.

* **The vectors.** When a *Trace shape* step ran, its vectors (`shape_file`, row
  `shape_row` of each window) are clustered — the Library's preparation already
  applied. Otherwise each window is sliced from `x` (channel-absolute starts, so
  `round(t[0] * fs)` is subtracted, as `catalogue.window_images` does) and the engine
  prepares it (`ward.shape_vectors`). A window that does not lie inside the span is
  `outside_span` (-1), counted, not guessed.
* **The params.** `method` (choices read from the registry at import, so a future
  method appears without an edit) and every method's params flattened as
  `<method>_<param>` — the Analyse param form renders flat `ParamSpec`s, one control
  each, and a JSON `method_params` box would hide every default and every bound; the
  two the engine applies to every method (`min_group`, `resample_length`) are one
  control each, unprefixed. Only the chosen method's params are passed on.
* **Labels.** Family 1..K by size, largest first; -1 for a window in no family, its
  reason counted in `meta["omitted"]`.

Why not extend `catalogue.shape_cluster`: see the core's docstring (it is RQ1's
training-pool clusterer — split-aware, tree-keeping, mapping-carrying, freezable).
"""

import os
import time

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.Catalogue import event_windows as EW
from Working.Catalogue import shape_families as SF
from Working.types import Grouping, WindowSet

NAME = "catalogue.shape_families"
#: the estimate cannot see the upstream windows (it sees the span and these params): it assumes one window per
#: this many seconds of span — denser than the dense chains of drops (every 20-60 min) the recordings hold
ASSUMED_SECONDS_PER_ITEM = 300.0
ASSUMED_MIN_ITEMS = 50

_TYPES = {"int": int, "float": float, "str": str, "bool": bool}
#: tighter bounds than the generic ones, where a method's param sits on the 0-1 distance scale
_BOUNDS = {"epsilon": (0.0, 1.0), "omit_d": (0.0, 1.0), "cut": (0.0, 1000.0), "resample_length": (16, 4096),
           "min_group": (1, 100000), "null_draws": (0, 50)}


def _choices(method, param):
    if method == "hdbscan":
        from Working.library.grouping.methods import hdbscan as H
        return {"cluster_selection_method": list(H.SELECTIONS), "distance": list(H.DISTANCES)}.get(param)
    return None


def method_param_specs():
    """The flattened method params as `ParamSpec`s (read from the registry)."""
    out = []
    for f in SF.flat_param_specs():
        spec = f["spec"]
        typ = _TYPES.get(str(spec.get("type")), str)
        who = "every method" if f["method"] is None else f["method"]
        desc = f"{who}: {spec.get('label', f['param'])} — {spec.get('help', '')}".strip()
        kw = {}
        if typ in (int, float):
            lo, hi = _BOUNDS.get(f["param"], (0, 1_000_000) if typ is int else (0.0, 1.0e6))
            kw = {"min": lo, "max": hi}
        ch = spec.get("choices") or _choices(f["method"], f["param"])
        if ch:
            kw["choices"] = list(ch)
        out.append(ParamSpec(f["flat"], typ, spec.get("default"), desc, **kw))
    return out


def common_params():
    """`method`, the coherence seed and the method params — shared by both family blocks."""
    return [
        ParamSpec("method", str, SF.DEFAULT_METHOD,
                  "How families are made — the Library's methods for shape: hdbscan (crowds of similar shapes; "
                  "stragglers left out; no number of families to choose), kshape (k families compared after sliding "
                  "one shape along the other), ward (a tree cut at a distance; every event placed, no noise test)",
                  choices=list(SF.shape_methods())),
        ParamSpec("seed", int, 0, "Seed of each family's SVD-entropy noise draws (the method's own seed is its "
                  "<method>_seed)", min=0, max=2**31 - 1),
        *method_param_specs(),
    ]


def family_meta(fam, *, method, flat):
    """The meta both blocks share: the method, its params, k, sizes, omissions, every family's flags and SVD
    entropy beside its null, the fractions, warnings, notes and rules."""
    families = [SF.family_summary(f) for f in fam.families]
    return {
        "method": method, "method_params": dict(fam.params), "k": fam.k,
        "family_sizes": {str(f.family): int(f.size) for f in fam.families},
        "families": families, "omitted": dict(fam.omitted),
        "n_placed": fam.n_placed, "n_confident": fam.n_confident,
        "fraction_placed": fam.fraction_placed, "fraction_confident": fam.fraction_confident,
        "n_noise_like": sum(1 for f in families if f["noise_like"]),
        "n_gap_filled": fam.n_gap_filled, "fit_summary": fam.fit_summary, "recipe_hash": fam.recipe_hash,
        "warnings": SF.warnings_for(fam), "notes": list(fam.notes),
        "exemplar_rule": SF.EXEMPLAR_RULE,
        "rules": SF.rules(method, fam.params),
    }


def estimate_for(x, fs, method, flat):
    span_s = len(x) / float(fs) if fs else len(x)
    n = max(ASSUMED_MIN_ITEMS, int(np.ceil(span_s / ASSUMED_SECONDS_PER_ITEM)))
    return SF.estimate_seconds(n, method, SF.method_params(method, flat))


def _require(value):
    if value is None:
        raise ValueError(f"{NAME} requires a WindowSet from a prior step (input_kind='windowset'): put Event windows "
                         "(or Sliding windows) before it.")
    if not isinstance(value, WindowSet):
        raise ValueError(f"{NAME} groups the windows of a WindowSet; got {type(value).__name__}.")
    return value


def _vectors_from_shape_file(ws):
    from Working.training import shape as tshape
    f = ws.features
    path = str(f[tshape.SHAPE_META["shape_file"]].iloc[0])
    if not os.path.isfile(path):
        raise ValueError(f"the Trace shape vectors are not on disk at {path}: re-run the Trace shape step")
    shapes = tshape.ShapeSet.load(path)
    rows = (f[tshape.SHAPE_META["shape_row"]].to_numpy(dtype=np.int64) if tshape.SHAPE_META["shape_row"] in f.columns
            else np.arange(ws.n_windows))
    if len(rows) and (rows.max() >= len(shapes.vectors) or rows.min() < 0):
        raise ValueError(f"the shape vectors at {path} hold {len(shapes.vectors)} rows; the windows ask for row "
                         f"{int(rows.max())}: re-run the chain")
    return [np.asarray(shapes.vectors[r], dtype=float) for r in rows]


def _run(x, t, fs, method=SF.DEFAULT_METHOD, seed=0, value=None, **flat):
    t0 = time.time()
    ws = _require(value)
    n = ws.n_windows
    x = np.asarray(x, dtype=float)
    span_start = int(round(float(t[0]) * fs)) if t is not None and len(t) else 0
    has_shape = ws.features is not None and "shape_file" in ws.features.columns and n > 0
    inside = np.ones(n, dtype=bool)
    if has_shape:
        waves = _vectors_from_shape_file(ws)
        vectors_from = "shape_file"
    else:
        rel = np.asarray(ws.starts, dtype=np.int64) - span_start
        inside = (rel >= 0) & (rel + int(ws.length) <= len(x))
        waves = list(EW.cut(x, rel[inside], ws.length))
        vectors_from = "x"
    fam = SF.shape_families(waves, method=method, params=SF.method_params(method, flat), seed=seed)
    labels = np.full(n, -1, dtype=np.int64)
    labels[inside] = fam.labels
    win_of = np.flatnonzero(inside)
    meta = family_meta(fam, method=method, flat=flat)
    if (~inside).any():
        meta["omitted"] = {**meta["omitted"], SF.OMIT_OUTSIDE_SPAN: int((~inside).sum())}
    starts = np.asarray(ws.starts, dtype=np.int64)
    meta["exemplar_windows"] = [
        {"family": f.family, "window": int(win_of[f.medoid_row]), "start": int(starts[win_of[f.medoid_row]]),
         "start_s": float(starts[win_of[f.medoid_row]] / float(fs))} for f in fam.families]
    meta.update(n_windows=n, vectors_from=vectors_from, span_start=span_start, seconds=round(time.time() - t0, 3))
    if n == 0:
        meta["summary"] = "no windows to group: the step before produced none — see its meta for why"
    else:
        left = int((~inside).sum())
        meta["summary"] = SF.summary_line(fam, unit_word="window") + (
            f"; {left} window(s) outside the span" if left else "")
    return AdapterResult(output_kind="grouping", value=Grouping(labels=labels), meta=meta)


def _estimate(x, t, fs, method=SF.DEFAULT_METHOD, seed=0, **flat):
    return estimate_for(x, fs, method, flat)


SPEC = register(AdapterSpec(
    name=NAME,
    display_name="Shape families (WindowSet -> Grouping, the Library's methods)",
    stage="catalogue",
    category="cluster",
    page_name="Shape families",
    params=common_params(),
    run=_run,
    estimate=_estimate,
    input_kind="windowset",
    output_kind="grouping",
    description=(
        "Sorts windows into families of similar shape with the Library's own methods — the same code the Library's "
        "grouping editor runs, so a family here means what a family there means. Amplitude does not enter: every "
        "window is resampled and z-normalised. Each family carries the method's noise flag (is it better than "
        "phase-randomised noise of the same colour?) and its SVD entropy (how far its members are copies of one "
        "shape) beside what noise scores; windows in no family are -1 with their reason. Choose the method first; "
        "for hdbscan tune hdbscan_min_cluster_size, for kshape set kshape_k. Put Event windows before it."
    ),
))
