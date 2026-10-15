"""The **one server-side dispatch seam** over the seven interchange types.

``to_payload(kind, value, meta, ctx)`` turns a ``Working.types`` value (plus
the ``AdapterResult.meta`` that only exists at run time) into a compact,
JSON-safe payload keyed on ``payload["type"]``. The client has the matching
single seam ``renderByType`` in ``client/src/analyse/Renderer.tsx``.

Transport rules (DECISIONS.md §3): bulk arrays never cross. A Signal or
Scores ships as a peak-preserving polyline sized to the viewport; a SpanSet
ships absolute seconds (capped); an Encoding ships a symbol strip or a
block-averaged uint8 image; a WindowSet ships its geometry and a capped,
rounded feature matrix; a Grouping ships labels + sizes (+ a time strip when
the WindowSet it was computed over is at hand); a Model ships a metadata
card, never the joblib.

Index conventions differ per type and are handled here, once:
* Signal / Scores: sample i of the value is absolute sample ``span_start + i``.
* SpanSet: producers emit **span-relative** indices; ``execution.py`` adds the
  span's offset when it writes ``detections`` (since 2026-09-21), and this
  module adds ``span_start`` to the in-memory result it serialises.
* WindowSet.starts are already **channel-absolute**.
* Grouping has no time; it borrows the WindowSet's starts.
"""
from __future__ import annotations

import base64
import os
import warnings
from typing import Any

import numpy as np
import pandas as pd

from Working.Detection.sax.dsax_python.dsax import MISSING_LETTER, MISSING_SYMBOL
from Working.types.windowset import BOOKKEEPING_COLUMNS
from Working.units import read_as_mv, to_mv_factor

from .decimate import envelope

SPAN_CAP = 5000
FEATURE_CELL_CAP = 200_000
IMAGE_SIDE = 256
SYMBOL_CAP = 20_000
STACK_TILES = 16          # images shown from a 4-D stack
TILE = 64                 # px per tile in the contact sheet

_LETTERS = "abcdefghijklmnopqrstuvwxyz"


def _letter(i: int) -> str:
    i = int(i)
    if i == MISSING_SYMBOL:
        return MISSING_LETTER       # a segment a gap touches (dSAX); -1 used to index 'z'
    if i < 26:
        return _LETTERS[i]
    return _LETTERS[i // 26 - 1] + _LETTERS[i % 26]


def _clean(v: Any) -> Any:
    """Recursively make a meta value JSON-safe (numpy scalars/arrays, NaN)."""
    if isinstance(v, (np.floating,)):
        f = float(v)
        return None if np.isnan(f) or np.isinf(f) else f
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, float):
        return None if (v != v or v in (float("inf"), float("-inf"))) else v
    if isinstance(v, np.ndarray):
        if v.size > 4096:
            return {"_array": True, "shape": list(v.shape), "dtype": str(v.dtype), "omitted": True}
        return [_clean(a) for a in v.ravel().tolist()] if v.ndim == 1 else _clean(v.tolist())
    if isinstance(v, dict):
        return {str(k): _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    if isinstance(v, (str, int, bool)) or v is None:
        return v
    return str(v)


def _block_nanmean(blocks: np.ndarray) -> np.ndarray:
    """Average each (axis 1, axis 3) block ignoring NaN, leaving NaN only where a
    block holds no finite value at all.

    A plain `.mean()` here was the Dehshibi stage-1 black image (fixup-a item 1):
    `preprocessing.wavelet_transform` leaves roughly half its columns NaN by
    design, so on any real span - where the block factor is far above 1 - every
    single output cell caught a NaN and the whole image went NaN. An all-NaN
    block is genuinely unknown, stays NaN, and is marked by the caller rather
    than painted as a value."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)   # "Mean of empty slice" is the answer here, not a fault
        return np.nanmean(blocks, axis=(1, 3))


def _finite_range(a: np.ndarray) -> list | None:
    a = np.asarray(a, dtype=float)
    f = a[np.isfinite(a)]
    if f.size == 0:
        return None
    return [float(f.min()), float(f.max())]


# ---------------------------------------------------------------- per type --

def _signal(value, meta, ctx):
    """Every Signal-producing block (detrend, band/high/low-pass, surrogate)
    preserves units, so a chain's Signal is in the recording's STORED unit
    (``ctx["units"]``). It is converted to mV here for drawing only — the core's
    value is not touched — and an undeclared unit is drawn as stored and says so."""
    fs = float(value.fs)
    n = int(len(value.x))
    ss = int(ctx.get("span_start", 0))
    factor = to_mv_factor(ctx.get("units"))
    unit = "mV" if factor is not None else None
    x = np.asarray(value.x, dtype=float) * (factor if factor is not None else 1.0)
    env = envelope(x, fs, 0, n, ctx.get("px", 1200))
    # envelope() reports t from index 0; shift to absolute seconds.
    env["t"] = [tt + ss / fs for tt in env["t"]]
    yr = _finite_range(x)
    out = {
        "type": "signal", "fs": fs, "n": n, "t0_s": ss / fs, "t1_s": (ss + n) / fs,
        "y_range": yr, "envelope": env, "unit": unit,
        # the factor between the stored unit and the drawn one (None when undeclared: drawn as stored), so a
        # view can place a stored-unit parameter such as a threshold on this trace and write a drag back
        "unit_factor": factor, "stored_unit": ctx.get("units"),
        "summary": f"{n:,} samples · {'%.3f' % yr[0] if yr else '–'} … {'%.3f' % yr[1] if yr else '–'} {unit or '(unit undeclared)'}",
    }
    if meta and "wavelet" in meta and "levels" in meta:
        out.update(_signal_layers(meta, fs, ss, factor))
    return out


def _signal_layers(meta, fs, ss, factor):
    """fixup-ac: a Signal block that passes ONE layer of a decomposition on
    (`preprocessing.wavelet_bands`) puts every layer in ``meta["layers"]`` as a
    min/max envelope over span-relative sample indices. Each ships on the
    channel's absolute seconds and in the trace's display unit, beside its Hz
    range and whether it is the layer that went on. A record that lost them (a
    sidecar written without them) says so rather than drawing a plain signal."""
    f = factor if factor is not None else 1.0
    layers = []
    for L in meta.get("layers") or []:
        env = L.get("envelope") or {}
        if not isinstance(env.get("i"), list):
            continue
        layers.append({
            "name": L.get("name"), "level": L.get("level"), "kind": L.get("kind"), "label": L.get("label"),
            "low_hz": L.get("low_hz"), "high_hz": L.get("high_hz"), "chosen": bool(L.get("chosen")),
            "rms": None if L.get("rms") is None else float(L["rms"]) * f,
            "envelope": {"t": [(ss + int(i)) / fs for i in env["i"]],
                         "v": [None if v is None else float(v) * f for v in env["v"]],
                         "n_source": env.get("n_source"), "n_points": env.get("n_points"),
                         "decimated": bool(env.get("decimated"))},
        })
    out = {"layers": layers,
           "decomposition": {k: _clean(meta.get(k)) for k in
                             ("wavelet", "levels", "levels_auto", "level", "layer", "layer_label", "padding",
                              "padding_note", "boundary_note", "edges_note", "reconstruction_error")}}
    if not layers:
        out["layers_note"] = ("the layers are not in this step's record (a cached result whose sidecar predates "
                              "them) — re-run with this step changed to draw every layer")
    return out


def _scores(value, meta, ctx):
    fs = float(value.fs)
    vals = np.asarray(value.values, dtype=float)
    n = int(len(vals))
    ss = int(ctx.get("span_start", 0))
    env = envelope(vals, fs, 0, n, ctx.get("px", 1200))
    env["t"] = [tt + ss / fs for tt in env["t"]]
    nan_tail = int(np.isnan(vals[::-1]).cumprod().sum()) if n else 0
    finite = vals[np.isfinite(vals)]
    # top-k lowest (motif-like) and highest (discord-like) locations
    top = {"low": [], "high": []}
    if finite.size:
        order = np.argsort(np.where(np.isfinite(vals), vals, np.inf))
        top["low"] = [{"t_s": (ss + int(i)) / fs, "v": float(vals[i])} for i in order[:3]]
        order_hi = np.argsort(np.where(np.isfinite(vals), -vals, np.inf))
        top["high"] = [{"t_s": (ss + int(i)) / fs, "v": float(vals[i])} for i in order_hi[:1]]
    hist = None
    if finite.size:
        counts, edges = np.histogram(finite, bins=40)
        hist = {"counts": counts.tolist(), "edges": edges.tolist()}
    m = meta.get("m") if meta else None
    if not m and ctx.get("params", {}).get("window_min"):
        m = int(round(float(ctx["params"]["window_min"]) * 60 * fs))   # matrix_profile: window_min is minutes
    return {
        "type": "scores", "fs": fs, "n": n, "t0_s": ss / fs, "t1_s": (ss + n) / fs,
        "nan_tail": nan_tail, "value_range": _finite_range(vals), "envelope": env,
        "top": top, "histogram": hist, "m": _clean(m),
        "summary": f"{n:,} values · one per {1 / fs:g} s" + (f" · m = {int(m)} samples" if m else ""),
    }


def _spanset(value, meta, ctx):
    fs = float(ctx.get("fs", (meta or {}).get("fs", 1.0)))
    ss = int(ctx.get("span_start", 0))
    starts = np.asarray(value.starts, dtype=np.int64)
    ends = np.asarray(value.ends, dtype=np.int64)
    n = int(len(starts))
    capped = n > SPAN_CAP
    sl = slice(0, SPAN_CAP)
    scores = list(value.scores)[sl] if value.scores is not None else None
    labels = list(value.labels)[sl] if value.labels is not None else None
    dur = (ends - starts) / fs if n else np.array([])
    feats = _feature_table(getattr(value, "features", None), n)
    out = {
        "type": "spanset", "fs": fs, "n": n, "capped": capped,
        "start_s": ((starts[sl] + ss) / fs).tolist(), "end_s": ((ends[sl] + ss) / fs).tolist(),
        "labels": labels, "scores": _clean(scores), "features": feats,
        "summary": (f"{n} span{'s' if n != 1 else ''}" + (f" · mean {dur.mean():.1f} s" if n else " · none found")
                    + (f" · {feats['n_columns']} features" if feats else "")),
    }
    # the feature blocks' own printed rules, rose and interval statistics (fixup-d):
    # passed through so the page draws the measurement it was given
    out.update(_span_anatomy(value, meta or {}, starts, ends, fs, ss, sl))
    for key in _SPANSET_META_VIEWS:
        if key in (meta or {}):
            out[key] = _clean(meta[key])
    # fixup-ak: a detector's plain-words explanation (`{face, detail, mark}`), drawn on its block page
    if isinstance((meta or {}).get("explain"), dict):
        out["explain"] = {k: str(v) for k, v in meta["explain"].items() if k in ("face", "detail", "mark")}
    # fixup-ak fix round: a detector that counts its spikes by direction and reads its threshold by the recording's
    # unit says both on the chain row's summary line, not only on its block page's readout
    if "n_up" in (meta or {}) and "n_down" in (meta or {}):
        out["n_up"], out["n_down"] = int(meta["n_up"]), int(meta["n_down"])
        out["summary"] += f" · {out['n_up']} up, {out['n_down']} down"
    if "units_note" in (meta or {}):
        out["units_note"] = None if meta["units_note"] is None else str(meta["units_note"])
        if out["units_note"]:
            out["summary"] += f" · {out['units_note']}"
    if "funnel" in (meta or {}):
        out["funnel"] = _funnel(meta["funnel"], fs, ss)
    if isinstance((meta or {}).get("families"), list):
        out.update(_event_families(value, meta, ctx, fs, ss))
    if isinstance((meta or {}).get("cycle_stack"), dict):
        out.update(_cycle_shapes(value, meta, ctx, fs, ss))
    if feats is not None and "units" in ctx:
        out["features_unit_note"] = _features_unit_note(feats, ctx)
    return out


#: A feature column the page reads as millivolts (event shape's amplitudes and slopes).
MV_COLUMN_SUFFIXES = ("_mv", "_mv_s")


def _features_unit_note(feats: dict, ctx: dict) -> str | None:
    """What the page says beside a feature table's millivolt columns (fixup-b). Every block that measures mV is
    told the recording's declared unit and reads by it (2026-10-15: `interrogation.event_shape`; a SpanSet ->
    SpanSet block after it, such as Intervals, carries its columns through), so the note is the recording's:
    nothing for a declared unit, "read as volts" for an undeclared one, and nothing for a table with no mV
    column. Before, it said "1000x off" for every recording stored in mV (QUESTIONS.md Q-X2.8)."""
    if not any(str(c).endswith(MV_COLUMN_SUFFIXES) for c in feats.get("columns") or []):
        return None
    return read_as_mv(ctx.get("units"))[1]


_SPANSET_META_VIEWS = ("rules", "rose", "interval_stats")

CYCLE_EXEMPLAR_FORM = '{"<group key without suffix>": <event index into the SpanSet>}'


def _scores_of(coh):
    """σ² first, eq. 17 beside it (the researcher's headline, decision 3), as the block scored them."""
    aa = (coh or {}).get("after_align") or {}
    return {"squared": _clean(aa.get("svd_entropy_squared_norm")), "eq17": _clean(aa.get("svd_entropy_norm"))}


def _cycle_shapes(value, meta, ctx, fs, ss):
    """W3-F: an `interrogation.cycle_shapes` SpanSet (read off `meta["cycle_stack"]`, a payload convention).

    * `cycle_stack` — the block's rows as it wrote them (before / after alignment, one per cycle in time order);
    * `cycle_sequences` — per sequence, the verdicts EXACTLY as the block gave them (`whole.verdict`, each group's
      `key` with its `~noise_like` / `~untested` suffix and `coherence.verdict`), σ² and eq. 17 beside them, the
      change points and the order test; nothing here compares a score with a null;
    * `cycle_exemplars` — each group's medoid cycle as a member: the event the block named
      (`meta["exemplar_events"]`, keyed `"<g>"` or `"t<train>:<g>"` — not the families' int keys), its whole
      cycle (anchor → anchor + `cycle_length_s`), and its group's marked key. An exemplar naming no event is
      refused loudly, naming the form."""
    block = (ctx or {}).get("block") or "this block"
    n = int(len(value.starts))
    f = getattr(value, "features", None)
    out: dict = {"cycle_stack": _clean(meta["cycle_stack"]), "cycle_sequences": [], "cycle_exemplars": []}
    # the rows' start_s are seconds from the span start (the block's `time_unit`); the page's axis is absolute
    out["cycle_stack"]["span_start_s"] = ss / fs
    marked: dict[str, str] = {}
    for s in meta.get("sequences") or []:
        whole = s.get("whole") or {}
        groups = []
        for g in s.get("groups") or []:
            coh = g.get("coherence") or {}
            key = str(g.get("key"))
            base = key.split("~", 1)[0]
            marked[base] = key
            groups.append({"group": _clean(g.get("group")), "key": key, "size": _clean(g.get("size")),
                           "medoid_event": _clean(g.get("medoid_event")),
                           "floor_frac_median": _clean(g.get("floor_frac_median")),
                           "half_recovery_frac_median": _clean(g.get("half_recovery_frac_median")),
                           "length_s_median": _clean(g.get("length_s_median")),
                           "verdict": _clean(coh.get("verdict")), "scores": _scores_of(coh)})
        out["cycle_sequences"].append({
            "key": _clean(s.get("key")), "n_cycles": _clean(s.get("n_cycles")), "n_used": _clean(s.get("n_used")),
            "k": _clean(s.get("k")), "k_note": _clean(s.get("k_note")),
            "k_null": _clean({k: (s.get("k_null") or {}).get(k) for k in ("source", "draws", "reason")}),
            "omitted": _clean(s.get("omitted")),
            "background_colour_mismatch": _clean(s.get("background_colour_mismatch")),
            "change_points_s": [(float(c) + ss / fs) for c in (s.get("change_points_s") or [])],
            "order_test": _clean(s.get("order_test")),
            "whole_verdict": _clean(whole.get("verdict")), "whole_scores": _scores_of(whole),
            "groups": groups})
    named = meta.get("exemplar_events")
    if named is not None:
        if not isinstance(named, dict):
            raise ValueError(f"{block}: meta['exemplar_events'] must be {CYCLE_EXEMPLAR_FORM}, got "
                             f"{type(named).__name__}: {str(named)[:80]}")
        col = lambda name: (np.asarray(pd.to_numeric(f[name], errors="coerce"), dtype=float)
                            if f is not None and name in f.columns else None)
        length_s, onset = col("cycle_length_s"), col("onset_idx")
        for key, w in named.items():
            try:
                whole_i = not isinstance(w, bool) and float(w) == int(w)
            except (TypeError, ValueError):
                whole_i = False
            if not whole_i or not 0 <= int(w) < n:
                raise ValueError(f"{block}: exemplar event {w!r} named for cycle group {key!r} is not an event of "
                                 f"this SpanSet (0..{n - 1}); meta['exemplar_events'] must be {CYCLE_EXEMPLAR_FORM}")
            i = int(w)
            a = onset[i] if onset is not None and np.isfinite(onset[i]) else float(value.starts[i])
            start_s = (a + ss) / fs
            span_len = (int(value.ends[i]) - int(value.starts[i])) / fs
            L = float(length_s[i]) if length_s is not None and np.isfinite(length_s[i]) else span_len
            seq, _, g = str(key).rpartition(":")
            out["cycle_exemplars"].append({
                "key": str(key), "group_key": marked.get(str(key), str(key)), "sequence": seq[1:] if seq else None,
                "group": int(g) if g.lstrip("-").isdigit() else None, "event": i,
                "start_s": start_s, "end_s": start_s + L,
                "rule": str(meta.get("exemplar_rule") or "the group's medoid cycle")})
    if meta.get("summary"):
        out["summary"] = str(meta["summary"])
    if meta.get("warnings"):
        out["warnings"] = [str(w) for w in meta["warnings"]]
    out["cycle_omitted"] = _clean(meta.get("omitted") or {})
    return out


def _span_anatomy(value, meta, starts, ends, fs, ss, sl):
    """Where each span's event sits inside it, and how many events each span's
    window holds (fixup-h).

    A span's *anchors* are the onset and the extremum of the event it brackets,
    when something measured them: a feature block's own `onset_idx` /
    `extremum_idx` columns, else the detector's `meta["events"]` rows (`onset_idx`
    / `trough_idx`). Both are span-relative, like the spans.

    `window_counts[i]` is how many events lie in span i's SAMPLE RANGE - never a
    lookup by window index, which undercounts (`DETECTION_AND_FIGURES.md` 5b: 11
    shown where 21 exist). With anchors it counts FALLS (onset..extremum), because
    overlapping windows are shared context and not double-counting; without them
    it counts the spans that share samples with this one. More than one is the
    slideshow's impurity flag."""
    n = len(starts)
    onset = extremum = None
    feats = getattr(value, "features", None)
    if feats is not None and {"onset_idx", "extremum_idx"} <= set(map(str, feats.columns)) and len(feats) == n:
        onset = pd.to_numeric(feats["onset_idx"], errors="coerce").to_numpy(dtype=float)
        extremum = pd.to_numeric(feats["extremum_idx"], errors="coerce").to_numpy(dtype=float)
    else:
        events = meta.get("events")
        if isinstance(events, (list, tuple)) and len(events) == n and n and all(
                isinstance(e, dict) and "onset_idx" in e and "trough_idx" in e for e in events):
            onset = np.array([float(e["onset_idx"]) for e in events])
            extremum = np.array([float(e["trough_idx"]) for e in events])
    if onset is not None and not (np.isfinite(onset).all() and np.isfinite(extremum).all()):
        onset = extremum = None
    if n == 0:
        return {"marks": None, "window_counts": [], "window_count_of": "spans"}
    if onset is not None:
        lo, hi = np.minimum(onset, extremum), np.maximum(onset, extremum)
        # a fall [lo, hi] lies in window [a, b) when it starts at or after a and ends before b
        inside = (lo[None, :] >= starts[:, None]) & (hi[None, :] < ends[:, None]) if n <= SPAN_CAP else None
        counts = inside.sum(axis=1) if inside is not None else np.array(
            [int(((lo >= a) & (hi < b)).sum()) for a, b in zip(starts[sl], ends[sl])])
        marks = {"onset_s": ((onset[sl] + ss) / fs).tolist(), "extremum_s": ((extremum[sl] + ss) / fs).tolist()}
        return {"marks": marks, "window_counts": [int(c) for c in counts[sl]], "window_count_of": "falls"}
    # spans sharing samples with [a, b): every span that starts before b, less those that end at or before a
    s_sorted, e_sorted = np.sort(starts), np.sort(ends)
    counts = np.searchsorted(s_sorted, ends[sl], side="left") - np.searchsorted(e_sorted, starts[sl], side="right")
    return {"marks": None, "window_counts": [int(c) for c in counts], "window_count_of": "spans"}


def _funnel(funnel, fs, span_start):
    """A detector's own account of what it decided (fixup-j): each stage's
    regions, from span samples (half-open) to the absolute seconds the spans
    are drawn in, under the spans' own cap, with the count that was found."""
    sec = lambda v: (float(v) + span_start) / fs
    stages = []
    for st in funnel.get("stages", []):
        regs = st.get("regions", [])
        stages.append({"key": st["key"], "label": st["label"], "n": int(st.get("n", len(regs))),
                       "capped": len(regs) > SPAN_CAP,
                       "start_s": [sec(a) for a, _ in regs[:SPAN_CAP]],
                       "end_s": [sec(b) for _, b in regs[:SPAN_CAP]]})
    return {"stages": stages,
            "chunks_s": [[sec(a), sec(b)] for a, b in funnel.get("chunks", [])[:SPAN_CAP]],
            "peaks_s": [sec(v) for v in funnel.get("omega_peaks", [])[:SPAN_CAP]],
            "valleys_s": [sec(v) for v in funnel.get("omega_valleys", [])[:SPAN_CAP]]}


def _feature_table(df, n):
    """A per-row feature table as the page draws it — columns, the matrix while
    it fits under FEATURE_CELL_CAP, per-column finite ranges. One shape for a
    WindowSet's features and a SpanSet's (fixup-d)."""
    if df is None:
        return None
    cols = [str(c) for c in df.columns]
    feat = {"n_columns": len(cols), "columns": cols, "matrix": None}
    if n * len(cols) <= FEATURE_CELL_CAP:
        mat = df.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
        mat = np.where(np.isfinite(mat), np.round(mat, 4), np.nan)
        feat["matrix"] = [[None if np.isnan(c) else float(c) for c in row] for row in mat]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)      # an all-NaN column has no range: None, said so
            colmin = np.nanmin(mat, axis=0) if n else np.full(len(cols), np.nan)
            colmax = np.nanmax(mat, axis=0) if n else np.full(len(cols), np.nan)
        feat["col_range"] = [[None if np.isnan(a) else float(a), None if np.isnan(b) else float(b)] for a, b in zip(colmin, colmax)]
    return feat


_POOL_COLS = ("pool_recording_id", "pool_source_file", "pool_channel", "pool_start", "pool_length", "pool_fs",
              "pool_scale_min", "pool_role", "pool_set_id")
_SHAPE_COLS = ("shape_raw_range_mv", "shape_peak_frac", "shape_row", "shape_file")


def _hist(vals, bins, range_=None, log=False):
    v = np.asarray(vals, dtype=float)
    v = v[np.isfinite(v)]
    if log:
        v = v[v > 0]
        if not v.size:
            return {"counts": [0] * bins, "edges": (10 ** np.linspace(range_[0], range_[1], bins + 1)).tolist(), "log": True} if range_ else None
        counts, edges = np.histogram(np.log10(v), bins=bins, range=range_)
        return {"counts": counts.tolist(), "edges": (10 ** edges).tolist(), "log": True}
    if not v.size:
        return None
    counts, edges = np.histogram(v, bins=bins, range=range_)
    return {"counts": counts.tolist(), "edges": edges.tolist(), "log": False}


def _pool_windowset(value, meta, ctx):
    """fixup-ag: a WindowSet that is a POOL (its features are the pool's per-window metadata, never measures)
    ships the pool as its page draws it — windows per recording × scale × role, what was dropped and why, the
    members, the plan — and, after a Trace shape step, what the floor left out and each window's raw range."""
    f = value.features
    n = int(value.n_windows)
    roles = f["pool_role"].astype(str).to_numpy()
    scales = f["pool_scale_min"].to_numpy(dtype=float)
    files = f["pool_source_file"].astype(str).to_numpy()
    by = [{"recording": sf, "scale_min": (int(sc) if float(sc).is_integer() else float(sc)), "role": r, "n": int(c)}
          for (sf, sc, r), c in pd.DataFrame({"sf": files, "sc": scales, "r": roles}).groupby(["sf", "sc", "r"]).size().items()]
    out = {"type": "windowset", "fs": float(value.fs), "n_windows": n, "length": int(value.length),
           "length_s": int(value.length) / float(value.fs) if value.fs else 0.0, "starts_s": [], "capped": n > 0,
           "features": None, "split": None,
           "pool_windows": {"n": n, "by": by, "by_role": {r: int((roles == r).sum()) for r in ("train", "validation", "test", "exam")},
                            "by_scale": {f"{(int(sc) if float(sc).is_integer() else float(sc))}": int((scales == sc).sum()) for sc in np.unique(scales)}}}
    if meta.get("pool"):
        out["pool"] = _clean(meta["pool"])
    if meta.get("shape_file"):
        shp = {k: _clean(meta.get(k)) for k in ("resample_length", "noise_floor", "floors", "n_in", "n_kept", "under_floor",
                                                 "unmeasured", "method", "seconds", "shape_file", "shape_key", "align",
                                                 "detrend", "align_rule", "detrend_rule", "swing_rule", "recut",
                                                 "anchor_frac", "anchor_rule")}
        if "shape_raw_range_mv" in f.columns:
            rr = pd.to_numeric(f["shape_raw_range_mv"], errors="coerce").to_numpy(dtype=float)
            shp["raw_range_hist"] = _hist(rr, 40, log=True)
            # fixup-ag: one small histogram per recording x scale, on SHARED log bins, each with its recording's floor —
            # what the researcher reads to choose a floor in Settings › Datasets
            pos = rr[np.isfinite(rr) & (rr > 0)]
            if pos.size:
                lo, hi = np.log10(pos.min()), np.log10(pos.max())
                floors = meta.get("floors") or {}
                lo = min(lo, *(np.log10(v["floor_mv"]) for v in floors.values() if v.get("floor_mv")))
                rng = (float(np.floor(lo * 4) / 4), float(np.ceil(hi * 4) / 4 + 1e-9))
                shp["raw_range_by"] = {
                    sf: {"floor_mv": (floors.get(sf) or {}).get("floor_mv"), "from": (floors.get(sf) or {}).get("from"),
                         "scales": {f"{(int(sc) if float(sc).is_integer() else float(sc))}":
                                    _hist(rr[(files == sf) & (scales == sc)], 32, range_=rng, log=True)
                                    for sc in np.unique(scales[files == sf])}}
                    for sf in sorted(set(files.tolist()))}
            shp["raw_range_by_scale"] = {f"{(int(sc) if float(sc).is_integer() else float(sc))}": _hist(rr[scales == sc], 30, log=True) for sc in np.unique(scales)}
        if "shape_peak_frac" in f.columns:
            pk = pd.to_numeric(f["shape_peak_frac"], errors="coerce").to_numpy(dtype=float)
            shp["peak_frac_hist"] = _hist(pk, 20, (0.0, 1.0))
            shp["peak_frac_by_scale"] = {f"{(int(sc) if float(sc).is_integer() else float(sc))}": _hist(pk[scales == sc], 20, (0.0, 1.0)) for sc in np.unique(scales)}
        out["shape"] = shp
    head = (f"{n:,} windows · " + " · ".join(f"{k} {v:,}" for k, v in out["pool_windows"]["by_role"].items() if v)
            + " · " + " / ".join(f"{k} min" for k in out["pool_windows"]["by_scale"]))
    if out.get("shape"):
        u = (out["shape"].get("under_floor") or {}).get("n") or 0
        head += f" · {u:,} under the noise floor left out" if out["shape"].get("noise_floor") else " · noise floor off"
    elif out.get("pool"):
        head += f" · pool {out['pool'].get('name')} ({out['pool'].get('saved')})"
    out["summary"] = head
    return out


def _windowset(value, meta, ctx):
    if value.features is not None and all(c in value.features.columns for c in _POOL_COLS):
        return _pool_windowset(value, meta or {}, ctx)
    fs = float(value.fs)
    starts = np.asarray(value.starts, dtype=np.int64)
    n = int(len(starts))
    # The split is metadata riding on the feature table (`preprocessing.sliding_windows`), not a
    # measure: it is shipped apart, and a table that held nothing else is no feature matrix (fixup-h).
    feats, split = value.features, None
    meta = meta or {}
    # w2-f: a window set cut around events (`catalogue.event_windows`) names its anchor in meta. Its
    # bookkeeping columns (which event, where the anchor sits, overlap) are geometry, not measures: they leave
    # the heatmap and ship apart, so the page can draw each window around its event with the anchor inside it.
    anchored = "anchor_offset" in meta
    event_index = None
    if anchored and feats is not None:
        if "event_index" in feats.columns:
            event_index = pd.to_numeric(feats["event_index"], errors="coerce").fillna(-1).astype(int).to_numpy()
        drop = [c for c in BOOKKEEPING_COLUMNS if c in feats.columns and c != SPLIT_COLUMN]
        feats = feats.drop(columns=drop)
    elif isinstance(meta.get("curves"), dict) and feats is not None:
        # W3-F: multiscale entropy's bookkeeping (mse_r in stored units, drift share, inflation, counts) is not a
        # measure to colour beside the entropies; the curves and the block's warnings carry it
        drop = [c for c in BOOKKEEPING_COLUMNS if c in feats.columns and c != SPLIT_COLUMN]
        feats = feats.drop(columns=drop) if drop else feats
    if feats is not None and SPLIT_COLUMN in feats.columns:
        labels = pd.to_numeric(feats[SPLIT_COLUMN], errors="coerce").fillna(-1).astype(int).to_numpy()
        names = {str(k): SPLIT_NAMES.get(int(k), f"split {int(k)}") for k in np.unique(labels)}
        split = {"labels": labels[:SPAN_CAP].tolist(), "names": names,
                 "counts": {names[str(k)]: int((labels == k).sum()) for k in np.unique(labels)}}
        feats = feats.drop(columns=[SPLIT_COLUMN])
        if feats.shape[1] == 0:
            feats = None
    out = {
        "type": "windowset", "fs": fs, "n_windows": n, "length": int(value.length),
        "length_s": int(value.length) / fs, "starts_s": (starts[:SPAN_CAP] / fs).tolist(),
        "capped": n > SPAN_CAP, "features": _feature_table(feats, n), "split": split,
    }
    out["summary"] = (f"{n} windows · {out['length_s']:g} s each"
                      + (f" · {out['features']['n_columns']} features" if out["features"] else " · no features")
                      + (" · " + " / ".join(f"{c} {k}" for k, c in split["counts"].items()) if split else ""))
    if anchored:
        offset = int(meta["anchor_offset"])
        out["anchor"] = {"offset": offset, "offset_s": offset / fs, "used": meta.get("anchor_used"),
                         "requested": meta.get("anchor"), "pre_frac": _clean(meta.get("pre_frac")),
                         "fallback": _clean(meta.get("anchor_fallback"))}
        out["event_index"] = event_index[:SPAN_CAP].tolist() if event_index is not None else None
        out["events"] = {k: _clean(meta.get(k)) for k in (
            "n_events", "omitted", "omitted_rows", "omitted_rows_cut", "n_overlapping", "n_split_leaks",
            "n_recovery_outside_window", "n_duration_unmeasured", "length_basis", "warnings", "notes")}
        out["rules"] = _clean(meta.get("rules") or [])
        if meta.get("summary"):
            out["summary"] = f"{meta['summary']} · {out['summary']}"
    else:
        # W3-F: a block's own summary and warnings reach the face of ANY window set (multiscale entropy's blank
        # scales, collapse flags and left-out windows used to stay in meta: only an anchored set showed them)
        if meta.get("summary"):
            out["summary"] = f"{meta['summary']} · {out['summary']}"
        if meta.get("warnings"):
            out["warnings"] = [str(w) for w in meta["warnings"]]
        if meta.get("rules"):
            out["rules"] = _clean(meta["rules"])
    if isinstance(meta.get("curves"), dict):
        # W3-F (a payload convention, like a Signal's `layers`): one curve per sampled window over a shared x
        # (`scales_s`), `null` where a scale is undefined — shipped as the block wrote it; the page breaks the
        # line at a null, never joins across it
        c = meta["curves"]
        for key in ("scales_s", "windows", "median"):
            if key not in c:
                raise ValueError(f"{ctx.get('block') or 'this block'}: meta['curves'] needs {key!r} "
                                 f"(form: {{scales_s, windows: [{{index, start_s, values, collapsed}}], median}})")
        out["curves"] = _clean(c)
        out["curve_flags"] = {k: _clean(meta.get(k)) for k in (
            "collapse", "blank_scales_s", "inflation_limit", "inflation_median", "inflation_max",
            "defined_per_scale", "method", "r_rule")}
    return out


SPLIT_COLUMN = "split"
SPLIT_NAMES = {0: "train", 1: "validation", 2: "test"}


# ------------------------------------------------------- image frames (fixup-h) --
# The Encoding view draws "3 sampled images, scan through the rest". What one
# image IS depends on the value's shape, and it is decided here, once:
#
#   stack   a 4-D stack (n, H, W[, C]): frame k is image k, and it came from window k
#           of the WindowSet the stack was made over (when that is at hand);
#   time    a time-aligned image, one column per sample of the span: frame k is the
#           k-th chunk of FRAME_COLUMNS columns AT THE IMAGE'S OWN RESOLUTION - the
#           whole span block-averaged to 256 px is a smear of what the block computed;
#   whole   any other 2-D / 3-D image: one frame, the whole span.
#
# Every frame of a result is scaled to ONE value range - the result's own - so the
# colour bar on the page is true of every frame and a later frame can be compared
# with an earlier one. A cell with no finite value is marked, never painted.

FRAME_COLUMNS = 256
FRAMES_SHOWN = 3


def _frame_plan(vals, ctx):
    """`(axis, n_frames)` for an image-kind value, or `(None, 0)` when it has no frames."""
    if vals.ndim == 4:
        return "stack", int(vals.shape[0])
    if vals.ndim in (2, 3):
        n_samples = ctx.get("n_samples")
        if n_samples and int(n_samples) == int(vals.shape[1]) and vals.shape[1] > 1:
            return "time", int(np.ceil(vals.shape[1] / FRAME_COLUMNS))
        return "whole", 1
    return None, 0


def _value_range(vals):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        lo, hi = np.nanmin(vals), np.nanmax(vals)
    if not (np.isfinite(lo) and np.isfinite(hi)):
        f = np.asarray(vals, dtype=float)
        f = f[np.isfinite(f)]
        return None if f.size == 0 else [float(f.min()), float(f.max())]
    return [float(lo), float(hi)]


def _shrink(img, max_h, max_w):
    """Block-average an (H, W, C) float image to at most max_h x max_w, ignoring NaN."""
    h, w = img.shape[0], img.shape[1]
    fh = max(1, int(np.ceil(h / max_h))); fw = max(1, int(np.ceil(w / max_w)))
    if fh == 1 and fw == 1:
        return img
    hh, ww = max(fh, h // fh * fh), max(fw, w // fw * fw)
    img = img[:hh, :ww]
    hh, ww = img.shape[0] // fh * fh, img.shape[1] // fw * fw
    return _block_nanmean(img[:hh, :ww].reshape(hh // fh, fh, ww // fw, fw, img.shape[2]))


def _one_frame(vals, axis, index, rng, ctx):
    fs = float(ctx.get("fs", 1.0))
    ss = int(ctx.get("span_start", 0))
    t0 = t1 = None
    if axis == "stack":
        img = np.asarray(vals[index], dtype=float)
        ws = ctx.get("windowset")
        if ws is not None and len(ws.starts) == vals.shape[0]:
            t0 = float(ws.starts[index]) / float(ws.fs)          # WindowSet.starts are channel-absolute
            t1 = t0 + int(ws.length) / float(ws.fs)
        label = f"image {index + 1} of {vals.shape[0]}"
    elif axis == "time":
        c0 = index * FRAME_COLUMNS
        c1 = min(int(vals.shape[1]), c0 + FRAME_COLUMNS)
        img = np.asarray(vals[:, c0:c1], dtype=float)
        t0, t1 = (ss + c0) / fs, (ss + c1) / fs
        label = f"columns {c0:,}–{c1:,} of {vals.shape[1]:,}"
    else:
        img = np.asarray(vals, dtype=float)
        n_samples = ctx.get("n_samples")
        if n_samples:
            t0, t1 = ss / fs, (ss + int(n_samples)) / fs
        label = "the whole span"
    if img.ndim == 2:
        img = img[:, :, None]
    chans = 3 if img.shape[2] == 3 else 1
    img = img[:, :, :chans]
    img = _shrink(img, IMAGE_SIDE, FRAME_COLUMNS if axis == "time" else IMAGE_SIDE)
    blank = ~np.isfinite(img).any(axis=-1)
    if rng is None:
        u8 = np.zeros(img.shape, dtype=np.uint8)
    else:
        u8 = np.clip(np.nan_to_num((img - rng[0]) / ((rng[1] - rng[0]) or 1.0) * 255), 0, 255).astype(np.uint8)
    n_blank = int(blank.sum())
    return {"index": int(index), "label": label, "shape": [int(u8.shape[0]), int(u8.shape[1])], "channels": chans,
            "t0_s": t0, "t1_s": t1, "nan_cells": n_blank, "n_cells": int(blank.size),
            "pixels_b64": base64.b64encode(np.ascontiguousarray(u8).tobytes()).decode("ascii"),
            "nan_b64": (base64.b64encode(np.ascontiguousarray(blank, dtype=np.uint8).tobytes()).decode("ascii") if n_blank else None)}


def _frames(vals, ctx):
    axis, n = _frame_plan(vals, ctx)
    if axis is None or n == 0:
        return None
    rng = _value_range(vals)
    picks = list(range(n)) if n <= FRAMES_SHOWN else [0, (n - 1) // 2, n - 1]
    return {"axis": axis, "n": n, "value_range": rng, "frame_columns": FRAME_COLUMNS if axis == "time" else None,
            "shown": [_one_frame(vals, axis, k, rng, ctx) for k in picks]}


def frame_payload(value, meta, ctx, index: int) -> dict:
    """One frame of an image Encoding by index - what the settings page asks for when it scans past the
    three that were sampled. `IndexError` for an index the value does not have."""
    vals = np.asarray(value.values)
    axis, n = _frame_plan(vals, ctx or {})
    if axis is None or not (0 <= int(index) < n):
        raise IndexError(f"frame {index} of {n}")
    return _one_frame(vals, axis, int(index), _value_range(vals), ctx or {})


#: W3-F: an image whose rows are not pixels names them in meta — ONE convention for every such block
#: (docs/BLOCK_INTEGRATION.md §2): `meta[key]` lists one value per image row, row 0 first (the top row drawn).
ROW_AXIS_KEYS = (("lengths_s", "s", "window length"), ("freqs_hz", "Hz", "frequency"))


#: The pan matrix profile's own caveat (W3-C), said on the face beside its suggestion.
SUGGESTION_CAVEAT = ("the answer is the band of lengths that clear; the suggested length is the strongest of the "
                     "band and not the event's length — it leans long when an event dominates long windows and "
                     "toward an edge on chains. Read the band and the picture before handing a length on")


def _row_axis(meta, n_rows, ctx):
    """`row_axis` (and, for a block that judged its rows, `row_verdict`) of a 2-D image, or {}."""
    out: dict = {}
    for key, unit, label in ROW_AXIS_KEYS:
        vals = meta.get(key)
        if vals is None:
            continue
        vals = [float(v) for v in vals]
        if len(vals) != n_rows:
            raise ValueError(f"{(ctx or {}).get('block') or 'this block'}: meta[{key!r}] names {len(vals)} rows "
                             f"but the image has {n_rows} rows (one value per row, row 0 first)")
        out["row_axis"] = {"values": vals, "unit": unit, "label": label, "source": key}
        break
    per = meta.get("per_length")
    if isinstance(per, list) and "row_axis" in out:
        # the pan matrix profile's per-length verdict, as the block gave it — never re-derived from gap and draws
        # (W3-C's final form, 617edc2: the band `cleared_s`, the rule that picked the suggestion, per-length `cut`
        # and `reason_code`; scrump and its `approximate_note` are gone)
        out["row_verdict"] = {
            "verdict": _clean(meta.get("verdict")), "suggested_window_s": _clean(meta.get("suggested_window_s")),
            "suggested_row": _clean(meta.get("suggested_row")), "cleared_s": _clean(meta.get("cleared_s") or []),
            "suggestion_rule": _clean(meta.get("suggestion_rule")), "reasons": _clean(meta.get("reasons") or {}),
            # the block's own words when it sends them (its "suggested window" rule), else the copy
            "caveat": next((str(r.get("rule")) for r in (meta.get("rules") or [])
                            if isinstance(r, dict) and r.get("name") == "suggested window" and r.get("rule")),
                           SUGGESTION_CAVEAT),
            "rows": [{k: _clean(r.get(k)) for k in ("row", "length_s", "judged", "clears", "cut", "gap", "reason",
                                                     "reason_code", "n_windows_nan")} for r in per]}
    if out and meta.get("summary"):
        out["_summary"] = str(meta["summary"])
    if out and meta.get("rules"):
        out["rules"] = _clean(meta["rules"])
    return out


def _encoding(value, meta, ctx):
    meta = meta or {}
    vals = np.asarray(value.values)
    fs = float(ctx.get("fs", 1.0))
    ss = int(ctx.get("span_start", 0))
    frames = _frames(vals, ctx) if value.kind != "symbolic" else None
    if value.kind == "symbolic":
        details = meta.get("details", {}) or {}
        syms = vals.astype(int).ravel()
        n = int(len(syms))
        sps = details.get("samples_per_symbol") or ctx.get("samples_per_symbol")
        if not sps and n:
            sps = max(1, int(round(ctx.get("n_samples", n) / n)))
        alphabet = details.get("alphabet_size")
        if alphabet is None:
            alphabet = int(syms.max()) + 1 if n else 0
        # an encoder that names its own alphabet (five-stage d D S U u) is shown in it; else a b c …
        own = meta.get("letters")
        letters = (own[:SYMBOL_CAP] if isinstance(own, str) and len(own) == n else "".join(_letter(s) for s in syms[:SYMBOL_CAP]))
        return {
            "type": "encoding", "kind": "symbolic", "n_symbols": n, "alphabet_size": int(alphabet),
            "symbols": syms[:SYMBOL_CAP].tolist(), "letters": letters, "capped": n > SYMBOL_CAP,
            "samples_per_symbol": int(sps) if sps else None,
            "seconds_per_symbol": (int(sps) / fs) if sps else None,
            "t0_s": ss / fs, "fs": fs,
            "cutlines": _clean(details.get("cutlines")), "cutline_domain": details.get("cutline_domain"),
            "representatives": _clean(details.get("representatives")),
            "paa": _clean(np.asarray(details["paa"])[:SYMBOL_CAP]) if details.get("paa") is not None else None,
            "n_trimmed": _clean(details.get("n_trimmed")), "alphabet": meta.get("alphabet"),
            "summary": f"{n} symbols · alphabet {int(alphabet)} · {(int(sps) / fs) if sps else 0:g} s per symbol",
        }
    # image kinds
    n_images = None
    if vals.ndim == 4:
        # a stack (n, H, W[, C]) — e.g. catalogue.window_images: ship a contact sheet of the first
        # STACK_TILES images tiled in a grid, each block-averaged to TILE px, so the pane paints
        # what the model saw; the full stack stays on disk (rule 4)
        n_images = int(vals.shape[0])
        if n_images == 0:
            return {"type": "encoding", "kind": "image", "ndim": 4, "shape": list(vals.shape), "n_images": 0, "frames": None,
                    "summary": "0 images · the window set was empty"}
        k = min(n_images, STACK_TILES)
        cols = int(np.ceil(np.sqrt(k))); rows_ = int(np.ceil(k / cols))
        h, w = int(vals.shape[1]), int(vals.shape[2])
        fh = max(1, int(np.ceil(h / TILE))); fw = max(1, int(np.ceil(w / TILE)))
        hh, ww = h // fh * fh, w // fw * fw
        chans = int(vals.shape[3]) if vals.ndim == 4 and vals.shape[-1] in (1, 3) else 1
        tile_h, tile_w = hh // fh, ww // fw
        sheet = np.zeros((rows_ * tile_h, cols * tile_w, chans), dtype=float)
        for i in range(k):
            img = np.asarray(vals[i], dtype=float)[:hh, :ww]
            if img.ndim == 2:
                img = img[:, :, None]
            img = _block_nanmean(img[:, :, :chans].reshape(tile_h, fh, tile_w, fw, chans))
            r_, c_ = divmod(i, cols)
            sheet[r_ * tile_h:(r_ + 1) * tile_h, c_ * tile_w:(c_ + 1) * tile_w] = img
        vals = sheet if chans == 3 else sheet[:, :, 0]
    if vals.ndim == 1:
        return {"type": "encoding", "kind": "image", "ndim": 1, "shape": list(vals.shape),
                "series": _clean(vals), "bin_freqs": _clean(meta.get("bin_freqs")),
                "summary": f"{vals.shape[0]} log-frequency bins"}
    if vals.ndim in (2, 3):
        h, w = vals.shape[0], vals.shape[1]
        fh = max(1, int(np.ceil(h / IMAGE_SIDE))); fw = max(1, int(np.ceil(w / IMAGE_SIDE)))
        hh, ww = h // fh * fh, w // fw * fw
        img = vals[:hh, :ww]
        if vals.ndim == 2:
            img = _block_nanmean(img.reshape(hh // fh, fh, ww // fw, fw))
            blank = ~np.isfinite(img)
            chans = 1
        else:
            img = _block_nanmean(img.reshape(hh // fh, fh, ww // fw, fw, vals.shape[2]))
            blank = ~np.isfinite(img).any(axis=-1)
            chans = int(vals.shape[2])
        rng = _finite_range(img)
        u8 = (np.zeros(img.shape, dtype=np.uint8) if rng is None else
              np.clip(np.nan_to_num((img - rng[0]) / ((rng[1] - rng[0]) or 1.0) * 255), 0, 255).astype(np.uint8))
        n_blank = int(blank.sum()); n_cells = int(blank.size)
        shape_out = list(value.values.shape) if n_images else list(vals.shape)
        summary = (f"{n_images} images · {shape_out[1]}×{shape_out[2]} · contact sheet of the first {min(n_images, STACK_TILES)}"
                   if n_images else f"{h}×{w}" + (f"×{vals.shape[2]}" if vals.ndim == 3 else "") + f" image · shown at {u8.shape[0]}×{u8.shape[1]}")
        if rng is None:
            summary += " · no finite values: every cell of this image is NaN, so there is nothing to paint"
        elif n_blank:
            summary += f" · {n_blank:,} of {n_cells:,} cells have no data"
        out = {"type": "encoding", "kind": "image", "ndim": (4 if n_images else int(vals.ndim)), "shape": shape_out, "n_images": n_images,
               "display_shape": [int(u8.shape[0]), int(u8.shape[1])], "channels": chans,
               "value_range": rng, "pixels_b64": base64.b64encode(np.ascontiguousarray(u8).tobytes()).decode("ascii"),
               "all_nan": rng is None, "nan_cells": n_blank, "n_cells": n_cells,
               "nan_b64": (base64.b64encode(np.ascontiguousarray(blank, dtype=np.uint8).tobytes()).decode("ascii") if n_blank else None),
               "frames": frames, "summary": summary}
        if not n_images:
            ra = _row_axis(meta, int(h), ctx)
            block_summary = ra.pop("_summary", None)
            out.update(ra)
            if block_summary:      # the block's own line leads; the image's no-data count stays beside it
                out["summary"] = f"{block_summary} · {summary}"
        return out
    return {"type": "encoding", "kind": value.kind, "shape": list(vals.shape), "summary": f"{value.kind} {vals.shape}"}


def _grouping(value, meta, ctx):
    meta = meta or {}
    labels = np.asarray(value.labels).astype(int).ravel()
    n = int(len(labels))
    ids, counts = np.unique(labels, return_counts=True) if n else (np.array([]), np.array([]))
    clusters = [{"id": int(i), "count": int(c)} for i, c in zip(ids, counts)]
    shown = min(n, SPAN_CAP)
    # the lowest REAL label (-1 is "no label", drawn grey): a left-out window must not shift every cluster's colour
    real = ids[ids >= 0] if n else ids
    out = {"type": "grouping", "n": n, "k": int(len(ids)),
           "label_base": int(real.min()) if len(real) else (int(ids.min()) if n else 1),
           "linkage": meta.get("linkage"), "clusters": clusters, "labels": labels[:SPAN_CAP].tolist(),
           "capped": n > SPAN_CAP, "n_shown": int(shown), "strip": None, "exemplars": []}
    ws = ctx.get("windowset")
    # a pool's windows sit on many channels: no one time strip, no exemplar by feature (fixup-ag)
    if ws is not None and len(ws.starts) == n and not meta.get("tree"):
        out["strip"] = {"starts_s": (np.asarray(ws.starts) / float(ws.fs))[:SPAN_CAP].tolist(),
                        "length_s": int(ws.length) / float(ws.fs)}
        named = meta.get("exemplar_windows")
        out["exemplars"] = (_named_exemplars(labels, ids, ws, _exemplar_form(named, ctx), meta.get("exemplar_rule"))
                            if named is not None else _exemplars(labels, ids, ws))
    out["summary"] = (f"{len(ids)} clusters · sizes " + ", ".join(str(int(c)) for c in counts)
                      # the strip is capped; saying so is the difference between
                      # a short strip and a wrong one (fixup-a item 10)
                      + (f" · strip shows the first {shown:,} of {n:,} windows" if out["capped"] else ""))
    if meta.get("exemplar_windows") is not None:
        named = _exemplar_form(meta["exemplar_windows"], ctx)
        # fix 1 (critic 4): a label >= 0 the block named no exemplar for says so on its cluster — a gap is a note
        if ws is not None:
            for c in out["clusters"]:
                if c["id"] >= 0 and str(c["id"]) not in named:
                    c["exemplar_note"] = "the block named no exemplar for this label"
        # w2-f: a block that names its own exemplars (snippets, families) writes its own summary and rules;
        # they are the result (k and how it was chosen, the coverage, the run lengths), not commentary
        if meta.get("summary"):
            out["summary"] = str(meta["summary"]) + (
                f" · strip shows the first {shown:,} of {n:,} windows" if out["capped"] else "")
        if meta.get("rules"):
            out["rules"] = _clean(meta["rules"])
        for c in out["clusters"]:
            if c["id"] == -1 and "-1" not in named:
                # fix 1 (critic 10): snippets' -1 holds the mostly-NaN windows AND the ones no position voted for;
                # the name counts the NaN ones rather than calling them all NaN
                if "n_windows_nan" in meta:
                    c["name"] = f"unlabelled · {int(meta['n_windows_nan'] or 0)} of {c['count']} mostly NaN"
                else:
                    c["name"] = str(meta.get("unlabelled_name") or "unlabelled")
    if meta.get("n_left_out") is not None and not meta.get("class_names") and not meta.get("tree"):
        # W3-A / decision 7: `catalogue.cluster` leaves out (and labels -1) a window whose features are all NaN —
        # drawn as "no label" (grey), never as a cluster; its summary says how many
        for c in out["clusters"]:
            if c["id"] == -1 and "name" not in c:
                why = meta.get("left_out_reason")
                c["name"] = "no label · left out" + (f" ({why})" if why else "")
        if meta.get("summary") and meta.get("exemplar_windows") is None:
            out["summary"] = str(meta["summary"]) + (
                f" · strip shows the first {shown:,} of {n:,} windows" if out["capped"] else "")
    if isinstance(meta.get("families"), list):
        # w2-f: a Grouping made by the Library's methods (`catalogue.shape_families`): every family's summary as
        # the block made it — flags, `confident`, `null_caveat`, coherence beside its null with the block's own
        # verdict — read off, never re-derived; -1 is "in no family"
        out["families"] = [_family_row(f) for f in meta["families"]]
        out["family_summary"] = _family_summary(meta)
        for c in out["clusters"]:
            if c["id"] == -1:
                c["name"] = "in no family"
    if meta.get("tree"):
        # fixup-ag: a Grouping that KEPT its tree (Shape clustering) ships it: the truncated dendrogram, the
        # proposal per k, a line per cluster at the cut and the mapping. -1 = not clustered (validation, test and
        # exam windows never touch the tree; the trained model assigns them).
        out["tree"] = _clean(meta["tree"])
        for c in out["clusters"]:
            if c["id"] == -1:
                c["name"] = "not clustered · validation / test / exam"
        t = meta["tree"]
        out["summary"] = (f"{t.get('k')} clusters · clustered {int(t.get('n_clustered') or 0):,} · assigned "
                          f"{int(t.get('n_assigned') or 0):,} · not clustered {sum((t.get('not_clustered') or {}).values()):,}"
                          + (" · tree re-used" if t.get("reused") else ""))
    if meta.get("class_names"):
        # a labelled Grouping (fixup-aa, `catalogue.manual_labels`): the groups are
        # named classes, -1 is "excluded", and the coverage line is the summary —
        # it is the result (class sizes and what was left out), not commentary
        names = {int(k): str(v) for k, v in meta["class_names"].items()}
        excluded = meta.get("excluded_label")
        if excluded is not None:
            names[int(excluded)] = "excluded"
        for c in out["clusters"]:
            c["name"] = names.get(c["id"])
        out["class_names"] = {str(k): v for k, v in names.items()}
        out["coverage"] = _clean(meta.get("coverage") or {})
        out["rules"] = _clean(meta.get("rules") or [])
        out["summary"] = str(meta.get("summary") or out["summary"]) + (
            f" · strip shows the first {shown:,} of {n:,} windows" if out["capped"] else "")
    return out


def _exemplars(labels, ids, ws):
    """One member window per cluster, to be DRAWN (fixup-h): the window nearest its
    cluster's centroid in the z-scored feature space, or the cluster's first window
    when the window set carries no features. A member, never an average - a mean
    of windows is a waveform the recording does not contain."""
    feats = ws.features
    if feats is not None and SPLIT_COLUMN in feats.columns:
        feats = feats.drop(columns=[SPLIT_COLUMN])
    z = None
    if feats is not None and feats.shape[1] and len(feats) == len(labels):
        m = feats.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            mu, sd = np.nanmean(m, axis=0), np.nanstd(m, axis=0)
        z = np.nan_to_num((m - mu) / np.where(sd > 0, sd, 1.0))
    fs, length = float(ws.fs), int(ws.length)
    out = []
    for cid in ids:
        members = np.flatnonzero(labels == cid)
        if z is not None:
            d = np.linalg.norm(z[members] - z[members].mean(axis=0), axis=1)
            pick, rule = int(members[int(np.argmin(d))]), "the member nearest its cluster's centroid in z-scored feature space"
        else:
            pick, rule = int(members[0]), "the cluster's first window (the window set carries no features)"
        out.append({"cluster": int(cid), "window": pick, "start_s": float(ws.starts[pick]) / fs,
                    "length_s": length / fs, "n": int(len(members)), "rule": rule,
                    "by": "centroid" if z is not None else "first"})
    return out


EXEMPLAR_FORM = '{"<label>": <window index>}'
EVENT_EXEMPLAR_FORM = '{"<family>": <event index>}'

#: what the page reads off each family of the W2-E blocks (`Working.Catalogue.shape_families.family_summary`)
FAMILY_KEYS = ("family", "library_label", "size", "medoid_distance", "noise_like", "unstable", "tested", "why",
               "confident", "null_caveat", "svd_entropy", "svd_entropy_norm", "svd_entropy_null_median",
               "svd_entropy_null_p05", "svd_entropy_squared_norm", "svd_entropy_squared_null_median", "top_share",
               "coherence_reason", "svd_entropy_beyond_noise", "svd_entropy_null_margin", "svd_entropy_rule",
               # W3-G / W3-F (decision 3): σ² leads, eq. 17 beside it; which null passed, and how much background
               "svd_entropy_squared_null_p05", "svd_entropy_variants", "passed_by", "svd_entropy_passed_by",
               "null_kind", "svd_entropy_null_kind", "background_s", "background", "svd_entropy_background",
               "svd_entropy_why")


def _family_row(f):
    return {k: _clean(f.get(k)) for k in FAMILY_KEYS}


def _family_summary(meta):
    keep = ("method", "k", "n_placed", "n_confident", "fraction_placed", "fraction_confident", "n_noise_like",
            "omitted", "warnings", "notes", "n_events", "n_windows", "window", "write_group", "exemplar_rule")
    return {k: _clean(meta.get(k)) for k in keep}


def _event_families(value, meta, ctx, fs, ss):
    """w2-f: an `interrogation.event_families` SpanSet. Each event's family, reason (incl. `no_window:<reason>`)
    and noise mark (capped as the spans are), every family's summary, and the exemplar EVENTS the block named —
    each checked to be an event of the family it is named for, against the `family` column, loudly."""
    f = getattr(value, "features", None)
    n = int(len(value.starts))
    col = (lambda name, conv: [conv(v) for v in f[name].tolist()[:SPAN_CAP]]
           if f is not None and name in f.columns else None)
    out = {"families": [_family_row(x) for x in meta["families"]], "family_summary": _family_summary(meta),
           "family": col("family", int), "family_omit_reason": col("family_omit_reason", lambda v: "" if v is None else str(v)),
           "family_noise_like": col("family_noise_like", bool), "group": col("group", str),
           "exemplar_events": []}
    out["family_summary"]["n_events"] = n
    named = meta.get("exemplar_events")
    if named is not None:
        if not isinstance(named, dict):
            raise ValueError(f"{(ctx or {}).get('block') or 'this block'}: meta['exemplar_events'] must be "
                             f"{EVENT_EXEMPLAR_FORM} (family -> event index into the SpanSet), got "
                             f"{type(named).__name__}: {str(named)[:80]}")
        fam = (np.asarray(pd.to_numeric(f["family"], errors="coerce").fillna(-1), dtype=np.int64)
               if f is not None and "family" in f.columns else None)
        rule = str(meta.get("exemplar_rule") or "the event the block itself named as this family's exemplar")
        for k, w in sorted(named.items(), key=lambda kv: int(kv[0])):
            try:
                whole = not isinstance(w, bool) and float(w) == int(w)
            except (TypeError, ValueError):
                whole = False
            if not whole:
                raise ValueError(f"exemplar event {w!r} named for family {k} is not a whole event index")
            i = int(w)
            if not 0 <= i < n:
                raise ValueError(f"exemplar event {i} named for family {k} is outside the events (0..{n - 1})")
            if fam is not None and int(fam[i]) != int(k):
                raise ValueError(f"exemplar event {i} named for family {k} is not of family {k} "
                                 f"(its own family is {int(fam[i])})")
            out["exemplar_events"].append({
                "family": int(k), "event": i, "start_s": (int(value.starts[i]) + ss) / fs,
                "end_s": (int(value.ends[i]) + ss) / fs, "rule": rule})
    if meta.get("summary"):
        out["summary"] = str(meta["summary"])
    return out


def _exemplar_form(named, ctx):
    """`meta["exemplar_windows"]` as `{str(label): index}`, or a ValueError naming the one form and the block.
    Snippets and families both write that dict (W2-E 2c016e3); a list, a string or a number is a block bug, said
    as one rather than as Python's own `dict()` complaint."""
    if not isinstance(named, dict):
        block = (ctx or {}).get("block") or "this block"
        raise ValueError(f"{block}: meta['exemplar_windows'] must be {EXEMPLAR_FORM} (label -> window index into "
                         f"the window set), got {type(named).__name__}: {str(named)[:80]}")
    return {str(k): v for k, v in named.items()}


def _named_exemplars(labels, ids, ws, named, rule):
    """w2-f: the exemplars the BLOCK chose (`meta["exemplar_windows"]`, label -> window index): the snippet
    itself, a family's medoid. Still a member, never an average — so a named window outside the window set, or
    one whose own label is not the label it is named for, is a loud error rather than a silent fallback to the
    centroid rule (the page would then draw a window the block never picked). A label the block names no
    exemplar for (snippets' -1, the windows too NaN to label) gets none."""
    fs, length, n = float(ws.fs), int(ws.length), len(labels)
    rule = str(rule or "the window the block itself named as this label's exemplar")
    by_label = dict(named)
    present = {str(int(c)) for c in ids}
    ghosts = sorted(set(by_label) - present)
    if ghosts:
        raise ValueError(f"exemplar_windows names label(s) {', '.join(ghosts)}, which are not in the grouping "
                         f"(its labels: {', '.join(sorted(present))})")
    out = []
    for cid in ids:
        if str(int(cid)) not in by_label:
            continue
        w = by_label[str(int(cid))]
        try:
            whole = not isinstance(w, bool) and float(w) == int(w)
        except (TypeError, ValueError):
            whole = False
        if not whole:
            raise ValueError(f"exemplar window {w!r} named for label {int(cid)} is not a whole window index")
        pick = int(w)
        if not 0 <= pick < n:
            raise ValueError(f"exemplar window {w!r} named for label {int(cid)} is outside the window set "
                             f"(0..{n - 1}): the block's exemplar_windows does not match its windows")
        if int(labels[pick]) != int(cid):
            raise ValueError(f"exemplar window {pick} named for label {int(cid)} is not a member of it "
                             f"(its own label is {int(labels[pick])})")
        out.append({"cluster": int(cid), "window": pick, "start_s": float(ws.starts[pick]) / fs,
                    "length_s": length / fs, "n": int((labels == cid).sum()), "rule": rule, "by": "block"})
    return out


def _model(value, meta, ctx):
    meta = meta or {}
    path = str(value.path)
    exists = os.path.isfile(path)
    keep = ("n_windows", "n_classes", "class_counts", "feature_names", "n_features_in",
            "n_features_kept", "n_train", "n_holdout", "holdout_accuracy", "holdout_reason",
            "per_class_accuracy", "holdout_class_counts", "params", "n_excluded", "excluded_reason")
    card = {k: _clean(meta[k]) for k in keep if k in meta}
    acc = card.get("holdout_accuracy")
    return {"type": "model", "path": path, "exists": exists,
            "size_bytes": os.path.getsize(path) if exists else None, "card": card,
            "summary": (f"holdout accuracy {acc:.2f}" if isinstance(acc, (int, float)) else "model") +
                       (f" · {card['n_classes']} classes" if "n_classes" in card else "") +
                       (f" · {card['n_windows']} windows" if "n_windows" in card else "") +
                       # fixup-aa: a labelled Grouping leaves windows out; the card says how many
                       (f" · trained on {card['n_windows'] - card['n_excluded']} labelled, "
                        f"{card['n_excluded']} excluded" if card.get("n_excluded") else "")}


_DISPATCH = {
    "signal": _signal, "scores": _scores, "spanset": _spanset, "windowset": _windowset,
    "encoding": _encoding, "grouping": _grouping, "model": _model,
}
TYPE_KINDS = tuple(sorted(_DISPATCH))


def to_payload(kind: str, value, meta: dict | None = None, ctx: dict | None = None) -> dict:
    """Serialise one typed value. ``ctx`` carries fs, span_start (samples), px,
    n_samples and optionally the WindowSet a Grouping was computed over."""
    fn = _DISPATCH.get(str(kind).lower())
    if fn is None:
        raise ValueError(f"unknown interchange type {kind!r}; known: {TYPE_KINDS}")
    return fn(value, meta or {}, ctx or {})
