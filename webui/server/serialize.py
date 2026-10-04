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

from Working.units import to_mv_factor

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
    if "funnel" in (meta or {}):
        out["funnel"] = _funnel(meta["funnel"], fs, ss)
    if feats is not None and "units" in ctx:
        # the core measured in mV on the assumption the samples are volts (detect5's
        # convention); say so where the recording's declared unit does not back it (fixup-b)
        u = ctx.get("units")
        out["features_unit_note"] = (None if u == "V" else
                                     "unit undeclared: amplitudes and slopes assume the samples are volts" if u is None else
                                     f"recording stored in {u}: amplitudes and slopes assume volts and read "
                                     f"{1000.0 / (to_mv_factor(u) or 1000.0):g}x off (QUESTIONS.md Q-X2.8)")
    return out


_SPANSET_META_VIEWS = ("rules", "rose", "interval_stats")


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


def _windowset(value, meta, ctx):
    fs = float(value.fs)
    starts = np.asarray(value.starts, dtype=np.int64)
    n = int(len(starts))
    # The split is metadata riding on the feature table (`preprocessing.sliding_windows`), not a
    # measure: it is shipped apart, and a table that held nothing else is no feature matrix (fixup-h).
    feats, split = value.features, None
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
        return {"type": "encoding", "kind": "image", "ndim": (4 if n_images else int(vals.ndim)), "shape": shape_out, "n_images": n_images,
                "display_shape": [int(u8.shape[0]), int(u8.shape[1])], "channels": chans,
                "value_range": rng, "pixels_b64": base64.b64encode(np.ascontiguousarray(u8).tobytes()).decode("ascii"),
                "all_nan": rng is None, "nan_cells": n_blank, "n_cells": n_cells,
                "nan_b64": (base64.b64encode(np.ascontiguousarray(blank, dtype=np.uint8).tobytes()).decode("ascii") if n_blank else None),
                "frames": frames, "summary": summary}
    return {"type": "encoding", "kind": value.kind, "shape": list(vals.shape), "summary": f"{value.kind} {vals.shape}"}


def _grouping(value, meta, ctx):
    meta = meta or {}
    labels = np.asarray(value.labels).astype(int).ravel()
    n = int(len(labels))
    ids, counts = np.unique(labels, return_counts=True) if n else (np.array([]), np.array([]))
    clusters = [{"id": int(i), "count": int(c)} for i, c in zip(ids, counts)]
    shown = min(n, SPAN_CAP)
    out = {"type": "grouping", "n": n, "k": int(len(ids)), "label_base": int(ids.min()) if n else 1,
           "linkage": meta.get("linkage"), "clusters": clusters, "labels": labels[:SPAN_CAP].tolist(),
           "capped": n > SPAN_CAP, "n_shown": int(shown), "strip": None, "exemplars": []}
    ws = ctx.get("windowset")
    if ws is not None and len(ws.starts) == n:
        out["strip"] = {"starts_s": (np.asarray(ws.starts) / float(ws.fs))[:SPAN_CAP].tolist(),
                        "length_s": int(ws.length) / float(ws.fs)}
        out["exemplars"] = _exemplars(labels, ids, ws)
    out["summary"] = (f"{len(ids)} clusters · sizes " + ", ".join(str(int(c)) for c in counts)
                      # the strip is capped; saying so is the difference between
                      # a short strip and a wrong one (fixup-a item 10)
                      + (f" · strip shows the first {shown:,} of {n:,} windows" if out["capped"] else ""))
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
                    "length_s": length / fs, "n": int(len(members)), "rule": rule})
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
