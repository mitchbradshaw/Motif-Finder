"""
minirocket.py
=============
w2-c: a MiniRocket shape fingerprint for every window of a `WindowSet`
(Dempster, Schmidt & Webb 2021, *MiniRocket: a very fast (almost) deterministic
transform for time series classification*, KDD '21, pp. 248-257; DOI
10.1145/3447548.3467231).

In plain words: every window is run through ~10,000 tiny fixed pattern
detectors, and for each one the fraction of the window where it fires is kept.
That list of numbers is a fingerprint of the window's shape; a simple classifier
learns from it in seconds. It answers "can this label be learned from the raw
shape at all?". The features mean nothing one by one.

The algorithm is aeon 1.4's `MiniRocket` transform, used as it is
(`aeon.transformations.collection.convolution_based.MiniRocket`, "directly adapted
from the original implementation ... with owner permission"; BSD-3-Clause). Read
from its source (`_minirocket.py`):

1. 84 kernels of length 9 — every choice of 3 of the 9 positions — with weight
   -1 everywhere and +2 at the three chosen positions (the weights sum to 0, so
   a constant offset never changes a convolution away from the zero-padded ends).
2. Up to `max_dilations` dilations per kernel, exponentially spaced up to the
   window length; the features are spread over (kernel, dilation) pairs.
3. A bias per feature: a golden-ratio quantile of the convolution output of
   ONE RANDOM TRAINING WINDOW (a different random window per kernel/dilation).
   This is the only thing `fit` learns, and it uses no labels.
4. PPV pooling: the feature is the proportion of the convolution output above
   its bias.
5. `n_kernels` is really the feature count, rounded down to a multiple of 84
   (84 when asked for fewer); `real_feature_count` mirrors that and the reported
   count is always the table's own width.

What this block adds around it, and why
---------------------------------------
* **Where a window comes from.** A window set with a `shape_file` column (a
  *Trace shape* step ran) is read from that file by `shape_row` — a pool's
  windows sit on many channels of many recordings and can never be sliced from
  one `x`. Otherwise the window is `x[start - round(t[0] * fs) : ... + length]`
  (`WindowSet.starts` are channel-absolute; `catalogue.window_images` does the
  same subtraction inline, so there is no slicing helper to import). A pool
  without a `shape_file` is refused, naming Trace shape as the fix.
* **Fit on the training windows only** (the leakage rule `catalogue.classifier`
  and the Trace-shape/pool split already follow): the rows whose `split` is
  train (`0` from Sliding windows, or the string `"train"`), else whose
  `pool_role` is `"train"`. With no split column at all it fits on every window
  and says, in `meta["warnings"]`, that a held-out score downstream is then
  optimistic. The transform itself uses no labels, so the leak a fit on all
  windows could carry is bounded to the biases' quantiles — but it is still a
  leak, and it is named.
* **`normalise`** (default on): each window is z-normalised before the
  transform, so the fingerprint is about shape, not level or scale. The paper's
  UCR archive data are z-normalised; fungal windows are not (their level drifts
  by orders of magnitude more than an event's size), so without this the
  fingerprint would largely encode where the trace happened to sit. A flat
  window (zero spread) normalises to zeros — kept and counted (`n_flat`), never
  a division by zero.
* **NaN** (aeon refuses it): a window whose non-finite samples are at most 5 %
  of it is linearly interpolated across its gaps (an end gap is held at the
  nearest finite value — `np.interp`'s own behaviour) and counted; a window with
  more is LEFT OUT and counted by reason (`gaps_over_5pct`). Every upstream
  column is kept on the windows that remain, as Trace shape does.
* **`keep_upstream_features`** (default on, fix round 1): off keeps only the
  fingerprint and the bookkeeping columns (`split`, `pool_*`, `shape_file`,
  `shape_row`, `shape_orig_start`, `shape_clamped`) and drops measured features
  (Catch22, entropies), counted — so a MiniRocket arm built on Window matrix's
  windows (the labels' 600/200 grid, where Window matrix must compute at least one
  family) trains its classifier on the fingerprint alone.
* **Refusals in words, never a blank:** an empty set; every window left out;
  windows shorter than 9 samples (aeon's own floor — said first, in words); a
  table of more than `max_cells` (windows x features) cells, naming
  `n_features` as the knob (10,000 features for 20,000 windows is 800 MB).
* **numpy's global random state**: aeon calls `np.random.seed` inside `fit`;
  this module saves and restores the global state around it, under a module
  lock so two MiniRocket runs never interleave. The state is restored within
  the calling thread; another thread drawing from numpy's global RNG during a
  fit is disturbed (its draws are reseeded, and the restore can roll its state
  back). The fingerprint itself does not depend on it — aeon picks the bias
  windows with numba's own per-thread generator — so concurrent runs give the
  same result as one run alone.

Why not reuse a sibling: `Working/Catalogue/aeon_classification/classification.py`
loads windows from labelled directories and returns reports, not a feature
table; `Working.Detection.aeon_features.transformations` wraps Catch22 only.
Neither takes an in-memory window matrix to a fitted MiniRocket.

No UI imports; aeon is imported lazily (it is a multi-second import), so loading
the adapter registry stays cheap.
"""

import os
import threading
import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

FEATURE_PREFIX = "mr_"
MIN_LENGTH = 9                 # aeon's MiniRocket refuses n_timepoints < 9
MAX_GAP_FRAC = 0.05            # the prompt's rule: interpolate gaps of <= 5 % of a window
KERNELS = 84                   # C(9, 3)
DEFAULT_N_FEATURES = 10_000    # the paper's
DEFAULT_MAX_DILATIONS = 32     # the paper's
DEFAULT_MAX_CELLS = 50_000_000
TRANSFORM_CHUNK = 4_096        # windows per transform call, to bound aeon's temporary copies

#: one aeon fit/transform at a time in this process (the bridge runs jobs on threads): aeon reseeds numpy's
#: global generator inside `fit`, and this module saves and restores it around the call
_AEON_LOCK = threading.Lock()

LEFT_OUT_GAPS = "gaps_over_5pct"
SPLIT_COLUMN = "split"
POOL_ROLE_COLUMN = "pool_role"
SHAPE_FILE_COLUMN = "shape_file"
SHAPE_ROW_COLUMN = "shape_row"

RULES = [
    {"name": "fingerprint",
     "rule": "MiniRocket (Dempster, Schmidt & Webb 2021, aeon 1.4): 84 fixed kernels of length 9 (weight -1, +2 at "
             "three of the nine positions), up to max_dilations dilations each; one feature per (kernel, dilation, "
             "bias): the proportion of the convolution output above the bias (PPV). The features mean nothing one "
             "by one — together they are a fingerprint of the window's shape"},
    {"name": "fit on",
     "rule": "the biases are quantiles of the convolution output of random TRAINING windows (split = train, or "
             "pool role = train) — the leakage rule the Classifier follows; no label is ever used. Without a split "
             "every window is used, and a held-out score downstream is optimistic"},
    {"name": "normalise",
     "rule": "on: each window is z-normalised (minus its mean, over its standard deviation) first, so the "
             "fingerprint is about shape, not level or size — as the paper's UCR data are; a flat window becomes "
             "zeros. off: the window as it is"},
    {"name": "gaps",
     "rule": "a window whose missing (NaN) samples are at most 5 % of it is filled by straight lines across each "
             "gap (an end gap holds the nearest value) and counted; a window with more is left out and counted"},
    {"name": "feature count",
     "rule": "aeon rounds the number asked for down to a multiple of 84 (84 at least); the count shown is the "
             "number of columns the table really has"},
    {"name": "upstream features",
     "rule": "keep_upstream_features on: every column the window set carried rides along. Off: only the "
             "fingerprint and the bookkeeping columns (split, pool_*, shape_file, shape_row, shape_orig_start, "
             "shape_clamped) are kept, and measured features (Catch22, entropies, ...) are dropped and counted, so a "
             "classifier downstream learns from the fingerprint alone"},
]

#: the columns `keep_upstream_features = False` keeps: identifiers and bookkeeping, never a measure
BOOKKEEPING_COLUMNS = (SPLIT_COLUMN, SHAPE_FILE_COLUMN, SHAPE_ROW_COLUMN, "shape_orig_start", "shape_clamped")
BOOKKEEPING_PREFIXES = ("pool_",)


def is_bookkeeping(column):
    return column in BOOKKEEPING_COLUMNS or column.startswith(BOOKKEEPING_PREFIXES)


@dataclass
class Fingerprint:
    """The output: the kept windows with the fingerprint columns added, and the run's `meta`."""
    windows: object
    meta: dict = field(default_factory=dict)


def real_feature_count(n_features):
    """The number of features aeon's MiniRocket really returns for `n_kernels = n_features`."""
    n = int(n_features)
    return KERNELS if n < KERNELS else (n // KERNELS) * KERNELS


def feature_names(n):
    width = max(4, len(str(max(n - 1, 0))))
    return [f"{FEATURE_PREFIX}{i:0{width}d}" for i in range(n)]


# ── where the windows come from ─────────────────────────────────────────────

def _is_pool(ws):
    from Working.training import shape as tshape
    return tshape.is_pool(ws)


def _read_shape_file(ws):
    """The Trace shape vectors of every window, by `shape_row`, from its `shape_file`."""
    from Working.training import shape as tshape
    feats = ws.features
    if SHAPE_ROW_COLUMN not in feats.columns:
        raise ValueError("the window set names a shape_file but no shape_row: re-run the Trace shape step")
    paths = feats[SHAPE_FILE_COLUMN].astype(str).to_numpy()
    rows = feats[SHAPE_ROW_COLUMN].to_numpy()
    out = None
    for path in pd.unique(paths):
        if not path or not os.path.isfile(path):
            raise ValueError(f"the Trace shape vectors are not on disk at {path!r}: re-run the Trace shape step")
        vectors = tshape.ShapeSet.load(path).vectors
        if out is None:
            out = np.empty((len(paths), vectors.shape[1]), dtype=float)
        elif vectors.shape[1] != out.shape[1]:
            raise ValueError(f"the Trace shape files hold vectors of different lengths ({out.shape[1]} and "
                             f"{vectors.shape[1]}): MiniRocket needs one length; re-run Trace shape on one pool")
        sel = np.flatnonzero(paths == path)
        r = rows[sel].astype(np.int64)
        if r.min() < 0 or r.max() >= len(vectors):
            raise ValueError(f"a window's shape_row is outside the {len(vectors)} vectors at {path!r}: "
                             "re-run the chain from Trace shape")
        out[sel] = vectors[r]
    return out


def _slice_x(ws, x, t, fs):
    if x is None:
        raise ValueError("MiniRocket slices its windows from the signal, and no signal was given")
    x = np.asarray(x, dtype=float)
    L = int(ws.length)
    span_start = int(round(float(t[0]) * float(fs))) if t is not None and len(t) else 0
    rel = np.asarray(ws.starts, dtype=np.int64) - span_start
    bad = np.flatnonzero((rel < 0) | (rel + L > len(x)))
    if len(bad):
        i = int(bad[0])
        raise ValueError(
            f"{len(bad):,} of {len(rel):,} windows lie outside this span (window {i} covers channel samples "
            f"{int(ws.starts[i]):,}-{int(ws.starts[i]) + L:,}; the span is {span_start:,}-{span_start + len(x):,}, "
            f"so it runs past the span): run MiniRocket on the span its windows were made on")
    idx = rel[:, None] + np.arange(L)[None, :]
    return x[idx]


def window_vectors(ws, x=None, t=None, fs=1.0):
    """`(M, source)`: one row per window (NaN kept) and where they came from (`shape_file` | `x`)."""
    feats = ws.features
    if feats is not None and SHAPE_FILE_COLUMN in feats.columns:
        return _read_shape_file(ws), "shape_file"
    if _is_pool(ws):
        raise ValueError(
            "these are the windows of a Window pool — they sit on many channels and recordings, so MiniRocket "
            "cannot slice them from one signal. Put a Trace shape step before MiniRocket: it saves every window's "
            "vector (shape_file), and MiniRocket reads them from there")
    return _slice_x(ws, x, t, fs), "x"


# ── gaps, the fit set, normalising ──────────────────────────────────────────

def repair_gaps(M, max_gap_frac=MAX_GAP_FRAC):
    """`(M, keep, interpolated)`: windows with at most `max_gap_frac` non-finite samples filled linearly."""
    M = np.array(M, dtype=float, copy=True)
    finite = np.isfinite(M)
    bad_frac = 1.0 - finite.mean(axis=1)
    keep = bad_frac <= max_gap_frac + 1e-12
    interpolated = keep & (bad_frac > 0)
    idx = np.arange(M.shape[1])
    for i in np.flatnonzero(interpolated):
        f = finite[i]
        M[i, ~f] = np.interp(idx[~f], idx[f], M[i, f])
    return M, keep, interpolated


def train_mask(features):
    """`(mask | None, column)`: which windows are training windows, read from `split` or `pool_role`."""
    if features is None:
        return None, None
    for col in (SPLIT_COLUMN, POOL_ROLE_COLUMN):
        if col in features.columns:
            v = features[col].to_numpy()
            if v.dtype.kind in "iuf":
                return v == 0, col
            return np.asarray([str(s).strip().lower() == "train" for s in v]), col
    return None, None


def znormalise(M):
    """Each row minus its mean over its standard deviation; a flat row becomes zeros. `(Z, flat)`."""
    mu = M.mean(axis=1, keepdims=True)
    sd = M.std(axis=1, keepdims=True)
    flat = (sd[:, 0] <= 1e-12 * np.maximum(1.0, np.abs(mu[:, 0])))
    Z = np.zeros_like(M)
    ok = ~flat
    Z[ok] = (M[ok] - mu[ok]) / sd[ok]
    return Z, flat


# ── the transform ───────────────────────────────────────────────────────────

def _check_shape(n_windows, length, n_features, max_cells):
    if n_windows == 0:
        raise ValueError("MiniRocket: the window set has no window — nothing to fingerprint")
    if length < MIN_LENGTH:
        raise ValueError(f"MiniRocket needs windows of at least {MIN_LENGTH} samples (its kernels are 9 samples "
                         f"long); these are {length}: use longer windows")
    real = real_feature_count(n_features)
    cells = int(n_windows) * real
    if max_cells is not None and cells > int(max_cells):
        head = (f"{n_windows:,} windows x {real:,} features = {cells:,} cells ({cells * 4 / 1e6:,.0f} MB) is over "
                f"max_cells = {int(max_cells):,}: ")
        fits = (int(max_cells) // max(n_windows, 1)) // KERNELS * KERNELS
        if fits >= KERNELS:
            raise ValueError(head + f"lower n_features (e.g. {fits:,}), use fewer windows, or raise max_cells")
        raise ValueError(head + f"even the fewest features ({KERNELS}) are over it for {n_windows:,} windows — use "
                                "fewer windows (a shorter span or a longer step), or raise max_cells")
    return real


def fingerprint_matrix(M, fit_mask=None, *, n_features=DEFAULT_N_FEATURES, max_dilations=DEFAULT_MAX_DILATIONS,
                       seed=0, normalise=True, timings=None):
    """The MiniRocket features `(n_windows, real_feature_count)` float32 of the rows of `M` (finite), fitted on
    the rows `fit_mask` selects (every row when None)."""
    from aeon.transformations.collection.convolution_based import MiniRocket
    M = np.asarray(M, dtype=float)
    if normalise:
        M, _ = znormalise(M)
    fit_rows = M if fit_mask is None else M[np.asarray(fit_mask, dtype=bool)]
    X3 = M.astype(np.float32)[:, None, :]
    with _AEON_LOCK:
        state = np.random.get_state()
        try:
            t0 = time.perf_counter()
            # n_jobs = numba's own thread cap, not -1: aeon turns -1 into every CPU and numba refuses more threads
            # than NUMBA_NUM_THREADS allows (a node capped at one thread failed outright, 2026-10-14)
            import numba
            mr = MiniRocket(n_kernels=int(n_features), max_dilations_per_kernel=int(max_dilations),
                            n_jobs=int(numba.config.NUMBA_NUM_THREADS), random_state=int(seed))
            mr.fit(fit_rows.astype(np.float32)[:, None, :])
            t1 = time.perf_counter()
            parts = [np.asarray(mr.transform(X3[i:i + TRANSFORM_CHUNK]), dtype=np.float32)
                     for i in range(0, len(X3), TRANSFORM_CHUNK)]
            t2 = time.perf_counter()
        finally:
            np.random.set_state(state)
    if timings is not None:
        timings.update({"fit": round(t1 - t0, 3), "transform": round(t2 - t1, 3)})
    return np.concatenate(parts, axis=0)


def fingerprint(ws, x=None, t=None, fs=1.0, *, n_features=DEFAULT_N_FEATURES, max_dilations=DEFAULT_MAX_DILATIONS,
                seed=0, normalise=True, max_cells=DEFAULT_MAX_CELLS, keep_upstream_features=True):
    """The windows of `ws` that could be fingerprinted, with `mr_0000 ...` added to their feature table (and,
    with `keep_upstream_features=False`, only the bookkeeping columns of the upstream table kept)."""
    from Working.types import WindowSet
    upstream_dropped = 0
    t_start = time.perf_counter()
    n_in = int(ws.n_windows)
    length = int(ws.length)
    if n_in == 0:
        _check_shape(0, length, n_features, max_cells)
    feats = ws.features
    from_file = feats is not None and SHAPE_FILE_COLUMN in feats.columns
    if not from_file:
        _check_shape(n_in, length, n_features, max_cells)
    M, source = window_vectors(ws, x, t, fs)
    t_read = time.perf_counter() - t_start
    real = _check_shape(n_in, M.shape[1], n_features, max_cells)

    M, keep, interpolated = repair_gaps(M)
    n_left = int((~keep).sum())
    if not keep.any():
        raise ValueError(f"every window ({n_in:,}) has more than 5 % of its samples missing (NaN): "
                         "nothing to fingerprint. Choose a span without the gap")
    mask, split_col = train_mask(feats)
    warnings = []
    if mask is None:
        fit_mask = None
        fit_on = "all"
        warnings.append("no split column (split or pool_role): the fingerprint was fitted on every window, so a "
                        "held-out score downstream is optimistic — put a blocked split before MiniRocket")
    else:
        fit_mask = mask[keep]
        fit_on = "train"
        if not fit_mask.any():
            raise ValueError(f"the {split_col} column marks no training window among the {int(keep.sum()):,} "
                             "kept windows, and MiniRocket fits on training windows only: give the split a "
                             "training block")
    M = M[keep]
    _, flat = znormalise(M) if normalise else (None, np.zeros(len(M), dtype=bool))
    timings = {"read": round(t_read, 3)}
    F = fingerprint_matrix(M, fit_mask, n_features=n_features, max_dilations=max_dilations, seed=seed,
                           normalise=normalise, timings=timings)
    if F.shape[1] != real:
        warnings.append(f"aeon returned {F.shape[1]:,} features where {real:,} were expected; the table carries "
                        f"what aeon returned")
    names = feature_names(F.shape[1])

    if feats is not None:
        upstream = feats.loc[keep].reset_index(drop=True)
        old = [c for c in upstream.columns if c.startswith(FEATURE_PREFIX)]
        if old:
            upstream = upstream.drop(columns=old)
            warnings.append(f"the window set already carried {len(old):,} {FEATURE_PREFIX}* columns (an earlier "
                            "MiniRocket step); they were replaced by this step's")
        if not keep_upstream_features:
            measured = [c for c in upstream.columns if not is_bookkeeping(str(c))]
            upstream = upstream.drop(columns=measured)
            upstream_dropped = len(measured)
        table = pd.concat([upstream, pd.DataFrame(F, columns=names)], axis=1)
    else:
        table = pd.DataFrame(F, columns=names)
    out = WindowSet(starts=np.asarray(ws.starts, dtype=np.int64)[keep], length=length, fs=float(ws.fs),
                    features=table)
    timings["total"] = round(time.perf_counter() - t_start, 3)

    n_kept = int(keep.sum())
    n_fit = int(fit_mask.sum()) if fit_mask is not None else n_kept
    n_interp = int(interpolated.sum())
    summary = (f"{n_kept:,} of {n_in:,} windows → {F.shape[1]:,} features each · fitted on {n_fit:,} "
               f"{'training' if fit_on == 'train' else '(all)'} windows")
    if n_left:
        summary += f" · {n_left:,} of {n_in:,} left out (more than 5 % missing)"
    if n_interp:
        summary += f" · {n_interp:,} with short gaps filled"
    if int(flat.sum()):
        summary += f" · {int(flat.sum()):,} flat"
    meta = {
        "n_features": int(F.shape[1]), "n_features_asked": int(n_features), "n_windows_in": n_in,
        "n_kept": n_kept, "n_fit_windows": n_fit, "fit_on": fit_on, "split_column": split_col,
        "n_left_out": {LEFT_OUT_GAPS: n_left} if n_left else {}, "n_interpolated": n_interp,
        "n_flat": int(flat.sum()), "seed": int(seed), "max_dilations": int(max_dilations),
        "normalise": bool(normalise), "source": source, "vector_length": int(M.shape[1]),
        "max_cells": int(max_cells) if max_cells is not None else None,
        "table_mb": round(n_kept * F.shape[1] * 4 / 1e6, 1),
        "keep_upstream_features": bool(keep_upstream_features), "upstream_dropped": int(upstream_dropped),
        "seconds": timings, "warnings": warnings, "rules": [dict(r) for r in RULES], "summary": summary,
    }
    return Fingerprint(windows=out, meta=meta)
