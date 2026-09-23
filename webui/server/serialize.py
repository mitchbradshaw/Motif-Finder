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
    return {
        "type": "signal", "fs": fs, "n": n, "t0_s": ss / fs, "t1_s": (ss + n) / fs,
        "y_range": yr, "envelope": env, "unit": unit,
        "summary": f"{n:,} samples · {'%.3f' % yr[0] if yr else '–'} … {'%.3f' % yr[1] if yr else '–'} {unit or '(unit undeclared)'}",
    }


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
    return {
        "type": "spanset", "fs": fs, "n": n, "capped": capped,
        "start_s": ((starts[sl] + ss) / fs).tolist(), "end_s": ((ends[sl] + ss) / fs).tolist(),
        "labels": labels, "scores": _clean(scores),
        "summary": (f"{n} span{'s' if n != 1 else ''}" + (f" · mean {dur.mean():.1f} s" if n else " · none found")),
    }


def _windowset(value, meta, ctx):
    fs = float(value.fs)
    starts = np.asarray(value.starts, dtype=np.int64)
    n = int(len(starts))
    out = {
        "type": "windowset", "fs": fs, "n_windows": n, "length": int(value.length),
        "length_s": int(value.length) / fs, "starts_s": (starts[:SPAN_CAP] / fs).tolist(),
        "capped": n > SPAN_CAP, "features": None,
    }
    if value.features is not None:
        df = value.features
        cols = [str(c) for c in df.columns]
        feat = {"n_columns": len(cols), "columns": cols, "matrix": None}
        if n * len(cols) <= FEATURE_CELL_CAP:
            mat = df.to_numpy(dtype=float)
            mat = np.where(np.isfinite(mat), np.round(mat, 4), np.nan)
            feat["matrix"] = [[None if np.isnan(c) else float(c) for c in row] for row in mat]
            colmin = np.nanmin(mat, axis=0) if n else np.array([])
            colmax = np.nanmax(mat, axis=0) if n else np.array([])
            feat["col_range"] = [[None if np.isnan(a) else float(a), None if np.isnan(b) else float(b)] for a, b in zip(colmin, colmax)]
        out["features"] = feat
    out["summary"] = f"{n} windows · {out['length_s']:g} s each" + (f" · {out['features']['n_columns']} features" if out["features"] else "")
    return out


def _encoding(value, meta, ctx):
    meta = meta or {}
    vals = np.asarray(value.values)
    fs = float(ctx.get("fs", 1.0))
    ss = int(ctx.get("span_start", 0))
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
            return {"type": "encoding", "kind": "image", "ndim": 4, "shape": list(vals.shape), "n_images": 0,
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
                "summary": summary}
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
           "capped": n > SPAN_CAP, "n_shown": int(shown), "strip": None}
    ws = ctx.get("windowset")
    if ws is not None and len(ws.starts) == n:
        out["strip"] = {"starts_s": (np.asarray(ws.starts) / float(ws.fs))[:SPAN_CAP].tolist(),
                        "length_s": int(ws.length) / float(ws.fs)}
    out["summary"] = (f"{len(ids)} clusters · sizes " + ", ".join(str(int(c)) for c in counts)
                      # the strip is capped; saying so is the difference between
                      # a short strip and a wrong one (fixup-a item 10)
                      + (f" · strip shows the first {shown:,} of {n:,} windows" if out["capped"] else ""))
    return out


def _model(value, meta, ctx):
    meta = meta or {}
    path = str(value.path)
    exists = os.path.isfile(path)
    keep = ("n_windows", "n_classes", "class_counts", "feature_names", "n_features_in",
            "n_features_kept", "n_train", "n_holdout", "holdout_accuracy", "holdout_reason",
            "params")
    card = {k: _clean(meta[k]) for k in keep if k in meta}
    acc = card.get("holdout_accuracy")
    return {"type": "model", "path": path, "exists": exists,
            "size_bytes": os.path.getsize(path) if exists else None, "card": card,
            "summary": (f"holdout accuracy {acc:.2f}" if isinstance(acc, (int, float)) else "model") +
                       (f" · {card['n_classes']} classes" if "n_classes" in card else "") +
                       (f" · {card['n_windows']} windows" if "n_windows" in card else "")}


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
