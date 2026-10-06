"""
shape.py
========
RQ1 version 2 (fixup-ag): cluster a window POOL on the SHAPE of the trace.

The pool is `AF`'s (`Working.training.pool.combine`): windows of 1, 10 and 30
minutes from several recordings, each with a role (train / validation / test /
exam) from a region-first plan. This module is the UI-free core of the three
Analyse blocks that turn it into categories:

    Window pool  ->  Trace shape  ->  Shape clustering
    (pool.combine)   (trace_shapes)   (cluster_shapes, labels_at, propose, ...)

The method is the Library's, not a second one
---------------------------------------------
`Working.library.grouping.methods.ward` is "Ward linkage on resampled,
z-normalised vectors under the scale-invariant distance", built on
`Working.distances.resample_to_length` and `z_normalize`. Every window, whatever
its length, goes through `ward.shape_vectors` at the Library's own length
(`ward.RESAMPLE_LENGTH`), so a 1-minute and a 30-minute window are compared by
shape and not by duration; the scale stays on every window. The tree is
`ward.ward_linkage(ward.condensed_distances(...))` — the same three calls
`WardMethod.fit` is made of, without the square matrix a 20,000-item tree
cannot afford.

The noise floor
---------------
Normalising throws amplitude away, so a 0.1 mV wiggle and a 50 mV drop would
look alike. Each window's raw range (peak to peak, in mV by the recording's
declared unit) is kept beside it, and a window whose range is under its
dataset's floor (`Working.library.view_filter.dataset_floors`: Settings ›
Datasets, 0.1 mV where empty) is LEFT OUT by default — counted per recording,
scale and role. A recording with no declared unit has no mV range: its windows
are *unmeasured*, kept and counted, never silently passed or dropped.

Training windows only, a sample, the rest assigned
--------------------------------------------------
Only TRAINING windows form clusters. Ward needs every pairwise distance
(20,000 windows: 1.6 GB), so the tree is built on a seeded sample stratified by
recording × scale (proportional, largest remainder), and every other training
window is assigned to the nearest cluster centre at the chosen cut (the mean of
the sampled members' vectors). Validation, test and exam windows never touch
the tree: they are assigned only by running the trained model on them.

The kept tree
-------------
`ShapeTree.save` writes `tree.npz` (the linkage, the leaf rows, the training
rows) and `manifest.json`. A tree made elsewhere — a Ward over every training
window on HPC — is written by the same writer and read by `load_tree_for`,
which refuses a tree built on other windows. The dendrogram, any later cut and
`propose` all read the one tree.

Headless: no UI or web library is imported here (CLAUDE.md rule 1).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from Working.library.grouping.methods import ward as _ward

RESAMPLE_LENGTH = _ward.RESAMPLE_LENGTH
DEFAULT_SAMPLE = 20_000
DEFAULT_MEMBERS = 12
DEFAULT_DENDROGRAM_LEAVES = 30
MEDOID_CAP = 1000          # the medoid is the most typical of at most this many members (seeded)
K_RANGE = (2, 20)

#: how a pool rides on a `WindowSet`: one metadata column per pool column. They are
#: metadata, never measures (like `split`), and every reader drops them.
POOL_META = {"recording_id": "pool_recording_id", "source_file": "pool_source_file", "channel": "pool_channel",
             "start": "pool_start", "length": "pool_length", "fs": "pool_fs", "scale_min": "pool_scale_min",
             "role": "pool_role", "set_id": "pool_set_id"}
#: the bounds (samples) of the role stretch each window lies in, from the pool's plan — what a re-cut must stay inside
POOL_STRETCH = {"stretch_a": "pool_stretch_a", "stretch_b": "pool_stretch_b",
                # seam (iii): the pool's content key, so a later step (the freeze in Analyse) knows which pool it is
                "pool_key": "pool_key"}
#: what the shape step adds to each window
SHAPE_META = {"raw_range_mv": "shape_raw_range_mv", "peak_frac": "shape_peak_frac", "shape_row": "shape_row",
              "shape_file": "shape_file", "orig_start": "shape_orig_start", "noise_mv": "shape_noise_mv",
              "clamped": "shape_clamped"}
SHAPE_EXTRA = ("orig_start", "noise_mv", "clamped")

# ── alignment (fixup-ag continuation, the researcher 2026-10-05) ────────────
ALIGNS = ("grid", "centre")
DETRENDS = ("off", "linear")
DEFAULT_ALIGN = "centre"     # the researcher chose centring (2026-10-05); measured: every pile an event shape (report part 2)
DEFAULT_DETREND = "linear"  # with the straight line removed, the drift is no longer the shape
SWING_RULE = ("the largest swing: the window's straight-line (least-squares) trend is removed, a running median of k "
              "samples is taken (k odd, at least 5, about a sixtieth of the window: 5 at 1 min, 11 at 10 min, 31 at "
              "30 min, so a glitch of a sample or two cannot be it), and the swing is the sample where that departs "
              "furthest from its own median")
ALIGN_RULE = {"grid": "the window as the pool cut it, on the grid",
              "centre": ("re-cut, the same length, centred on its largest swing — kept wholly inside its own role's "
                         "stretch on its own channel, inside the recording and clear of artifact spans; where the "
                         "centre cannot be reached it is shifted as far as allowed (clamped, counted); a window whose "
                         "re-cut overlaps an already-kept window of the same scale on the same channel by more than "
                         "half is a near-duplicate (one event twice) and is dropped, counted")}
DETREND_RULE = {"off": "no detrend: the shape is the trace as it is, drift included",
                "linear": "the window's least-squares straight line is removed before the resample and normalise"}
ROLES = ("train", "validation", "test", "exam")


def _key(header, arrays):
    h = hashlib.sha256(json.dumps(header, sort_keys=True, default=str).encode("utf-8"))
    for a in arrays:
        a = np.asarray(a)
        if a.dtype.kind in "OUS":
            h.update("\x00".join(map(str, a.tolist())).encode("utf-8"))
        else:
            h.update(np.ascontiguousarray(a.astype("<f8" if a.dtype.kind == "f" else "<i8")).tobytes())
        h.update(b"|")
    return h.hexdigest()[:16]


def peak_rss_mb():
    """The process's peak resident memory so far, in MB (None where it cannot be read)."""
    try:
        import psutil
        mi = psutil.Process().memory_info()
        peak = getattr(mi, "peak_wset", None) or getattr(mi, "peak_rss", None)
        if peak is None:
            import resource  # noqa: F401  (POSIX)
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        return round(float(peak) / 2 ** 20, 1)
    except Exception:
        return None


# ── the pool as a WindowSet ─────────────────────────────────────────────────

def pool_windowset(pool):
    """`AF`'s `Pool` as a `WindowSet`: starts as they are, the pool's columns as
    metadata columns. A pool mixes lengths (and may mix sample rates), so the
    WindowSet's `length` is the longest and its `fs` the lowest; the true values
    are per window in `pool_length` / `pool_fs`."""
    from Working.types import WindowSet
    t = pool.table
    feats = pd.DataFrame({POOL_META[c]: t[c].to_numpy() for c in POOL_META})
    plan = (pool.meta or {}).get("plan")
    if plan and len(t):
        a, b = stretch_bounds(plan, t)
        feats[POOL_STRETCH["stretch_a"]] = a
        feats[POOL_STRETCH["stretch_b"]] = b
    if len(t):
        feats[POOL_STRETCH["pool_key"]] = str(pool.key)
    return WindowSet(starts=t["start"].to_numpy().astype(np.int64),
                     length=int(t["length"].max()) if len(t) else 0,
                     fs=float(t["fs"].min()) if len(t) else 1.0, features=feats)


def stretch_bounds(plan, table):
    """Per window, `[a, b)` in samples: the role stretch of the plan it lies wholly inside."""
    from Working.training import pool as tpool
    a = np.zeros(len(table), dtype=np.int64)
    b = np.zeros(len(table), dtype=np.int64)
    t = table.reset_index(drop=True)
    for (sf, ch), g in t.groupby(["source_file", "channel"], sort=False):
        st = tpool.stretches_for(plan, sf, ch)
        s0 = np.array([x["start_s"] for x in st], dtype=float)
        s1 = np.array([x["end_s"] for x in st], dtype=float)
        fs = g["fs"].to_numpy(dtype=float)
        i = np.clip(np.searchsorted(s0, g["start"].to_numpy() / fs + 1e-9, side="right") - 1, 0, len(st) - 1)
        a[g.index.to_numpy()] = np.ceil(s0[i] * fs - 1e-6).astype(np.int64)
        b[g.index.to_numpy()] = np.floor(s1[i] * fs + 1e-6).astype(np.int64)
    return a, b


def is_pool(ws) -> bool:
    f = getattr(ws, "features", None)
    return f is not None and all(c in f.columns for c in POOL_META.values())


def pool_frame(ws) -> pd.DataFrame:
    """The per-window table of a pool WindowSet (any extra shape columns kept)."""
    if not is_pool(ws):
        raise ValueError("this block needs the windows of a Window pool: put a Window pool block (a chain source) "
                         "before it, so every window carries its recording, scale and role")
    f = ws.features
    out = pd.DataFrame({c: f[col].to_numpy() for c, col in POOL_META.items()})
    for c, col in {**POOL_STRETCH, **SHAPE_META}.items():
        if col in f.columns:
            out[c] = f[col].to_numpy()
    out = out.astype({"recording_id": np.int64, "channel": np.int64, "start": np.int64, "length": np.int64,
                      "fs": np.float64, "scale_min": np.float64, "set_id": np.int64})
    out["source_file"] = out["source_file"].astype(str)
    out["role"] = out["role"].astype(str)
    return out


def frame_windowset(frame, shape_file=None):
    """A pool table (with shape columns) back to a `WindowSet`."""
    from Working.types import WindowSet
    feats = pd.DataFrame({col: frame[c].to_numpy() for c, col in POOL_META.items()})
    for c, col in {**POOL_STRETCH, **SHAPE_META}.items():
        if c in frame.columns:
            feats[col] = frame[c].to_numpy()
    if shape_file is not None:
        feats[SHAPE_META["shape_file"]] = str(shape_file)
    return WindowSet(starts=frame["start"].to_numpy().astype(np.int64),
                     length=int(frame["length"].max()) if len(frame) else 0,
                     fs=float(frame["fs"].min()) if len(frame) else 1.0, features=feats)


# ── the shape vectors ───────────────────────────────────────────────────────

@dataclass
class ShapeSet:
    """`frame`: the kept windows (pool columns + raw_range_mv, peak_frac, shape_row).
    `vectors`: `(n_kept, resample_length)` float32 — row `shape_row` of each window."""
    frame: pd.DataFrame
    vectors: np.ndarray
    meta: dict = field(default_factory=dict)

    @property
    def key(self):
        f = self.frame
        return _key({"kind": "trace_shapes", "how": {k: self.meta.get(k) for k in
                                                     ("resample_length", "noise_floor", "floors_mv", "align", "detrend")}},
                    [f[c].to_numpy() for c in ("source_file", "channel", "start", "length", "role")])

    def save(self, d):
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "shapes.npz")
        f = self.frame
        cols = [*POOL_META, "raw_range_mv", "peak_frac", "shape_row",
                *[c for c in (*POOL_STRETCH, *SHAPE_EXTRA) if c in f.columns]]
        np.savez_compressed(path, vectors=np.asarray(self.vectors, dtype=np.float32),
                            **{c: (f[c].to_numpy().astype(str) if c in ("source_file", "role", "pool_key") else
                                   f[c].to_numpy().astype(np.float64) if c in ("fs", "scale_min", "raw_range_mv",
                                                                              "peak_frac", "noise_mv") else
                                   f[c].to_numpy().astype(np.int64))
                               for c in cols})
        with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump({"kind": "trace_shapes", "key": self.key, **self.meta}, fh, indent=2, default=str)
        return path

    @classmethod
    def load(cls, path):
        d = os.path.dirname(path)
        with np.load(path, allow_pickle=False) as z:
            vectors = z["vectors"]
            frame = pd.DataFrame({c: z[c] for c in (*POOL_META, "raw_range_mv", "peak_frac", "shape_row",
                                                    *POOL_STRETCH, *SHAPE_EXTRA) if c in z.files})
        frame["source_file"] = frame["source_file"].astype(str)
        frame["role"] = frame["role"].astype(str)
        if "pool_key" in frame.columns:
            frame["pool_key"] = frame["pool_key"].astype(str)
        meta = {}
        mp = os.path.join(d, "manifest.json")
        if os.path.isfile(mp):
            with open(mp, encoding="utf-8") as fh:
                meta = json.load(fh)
        saved = meta.pop("key", None)
        meta.pop("kind", None)
        out = cls(frame=frame, vectors=vectors, meta=meta)
        if saved is not None and saved != out.key:
            raise ValueError(f"the shape vectors at {path} do not match their own key ({saved} on disk, {out.key} "
                             "recomputed): the files were changed after they were written")
        return out


def _scale_label(v):
    v = round(float(v), 6)
    return int(v) if v.is_integer() else v


def _count_by(frame, mask):
    sub = frame.loc[mask]
    return [{"recording": sf, "scale_min": _scale_label(sc), "role": r, "n": int(n)}
            for (sf, sc, r), n in sub.groupby(["source_file", "scale_min", "role"]).size().items()]


def swing_width(length):
    """The running-median width of the swing rule: odd, at least 5, about a sixtieth of the window."""
    k = max(5, int(round(int(length) / 60.0)))
    return k if k % 2 else k + 1


def swing_index(seg):
    """The sample of a window's LARGEST SWING (`SWING_RULE`)."""
    from scipy.ndimage import median_filter
    from scipy.signal import detrend as _detrend
    seg = np.asarray(seg, dtype=float)
    if len(seg) < 3:
        return 0
    r = _detrend(seg, type="linear")
    k = min(swing_width(len(seg)), len(seg) if len(seg) % 2 else len(seg) - 1)
    f = median_filter(r, size=max(1, k), mode="nearest")
    return int(np.argmax(np.abs(f - np.median(f))))


def _detrended(seg):
    """The window less its least-squares straight line. What is left of an exact line is rounding dust, which
    z-normalising would blow up into a full-amplitude shape: below 1e-9 of the window's own range it is zero."""
    from scipy.signal import detrend as _detrend
    seg = np.asarray(seg, dtype=float)
    if len(seg) < 2:
        return seg
    r = _detrend(seg, type="linear")
    scale = float(np.ptp(seg)) or 1.0
    return np.zeros_like(r) if float(np.ptp(r)) <= 1e-9 * scale else r


def shape_of(seg, detrend="off", n_samples=RESAMPLE_LENGTH):
    """One window's shape vector: the Library's resample + z-normalise, after the detrend option."""
    seg = np.asarray(seg, dtype=float)
    if detrend == "linear":
        seg = _detrended(seg)
    return _ward.shape_vectors([seg], n_samples)[0]


def allowed_interval(a, length, *, stretch, n_samples, spans):
    """`[lo, hi)` a re-cut of window `[a, a + length)` may occupy: inside its role stretch, inside the
    recording, between the artifact spans either side of it. A span overlapping the window pins it."""
    a, length = int(a), int(length)
    lo = max(int(stretch[0]), 0)
    hi = min(int(stretch[1]), int(n_samples))
    for sa, sb in spans:
        sa, sb = int(sa), int(sb)
        if sa < a + length and sb > a:          # touches the window itself: no room to move
            return a, a + length
        if sb <= a:
            lo = max(lo, sb)
        elif sa >= a + length:
            hi = min(hi, sa)
    return lo, hi


def recut_start(a, length, swing, lo, hi):
    """`(start, clamped)`: the window re-cut centred on sample `swing` of it, shifted as far as `[lo, hi)` allows."""
    want = int(a) + int(swing) - int(length) // 2
    start = int(min(max(want, int(lo)), int(hi) - int(length)))
    return start, start != want


def near_duplicates(frame):
    """`(keep, n_duplicate, n_overlap)`: within one recording row and scale, a window overlapping the last kept one
    by more than half its length is a near-duplicate (dropped); a smaller overlap is counted and kept. `keep` is in
    the frame's own row order."""
    f = frame.reset_index(drop=True)
    keep = np.ones(len(f), dtype=bool)
    n_dup = n_ov = 0
    for _k, g in f.groupby(["recording_id", "scale_min"], sort=False):
        order = g.sort_values("start", kind="stable")
        prev = None
        for i, a, L in zip(order.index.to_numpy(), order["start"].to_numpy(), order["length"].to_numpy()):
            if prev is not None and a - prev < L / 2.0:
                keep[i] = False
                n_dup += 1
                continue
            if prev is not None and a - prev < L:
                n_ov += 1
            prev = int(a)
    return keep, int(n_dup), int(n_ov)


def check_recut(conn, frame):
    """The pool's guarantees for re-cut bounds: every window wholly inside its own role stretch, inside its
    recording, touching no artifact span. Raises `LeakageRefused`."""
    from Working.training import pool as tpool
    from Working.training.windows import LeakageRefused
    a = frame["start"].to_numpy()
    b = a + frame["length"].to_numpy()
    out_stretch = int(((a < frame["stretch_a"].to_numpy()) | (b > frame["stretch_b"].to_numpy())).sum())
    recs = {int(r["id"]): dict(r) for r in conn.execute("SELECT * FROM recordings")}
    ex = tpool._Exclusions(conn)
    out_rec = touching = 0
    for rid, g in frame.groupby("recording_id"):
        rec = recs[int(rid)]
        ga = g["start"].to_numpy()
        gb = ga + g["length"].to_numpy()
        out_rec += int(((ga < 0) | (gb > int(rec["n_samples"]))).sum())
        human, settings = ex.spans(rec)
        touching += int(tpool._touches(ga, g["length"].to_numpy(), human + settings).sum())
    if out_stretch or out_rec or touching:
        raise LeakageRefused(f"re-cut windows leave their bounds: {out_stretch} outside their own role's stretch, "
                             f"{out_rec} outside the recording, {touching} touching an artifact span")
    return {"outside own stretch": 0, "outside the recording": 0, "touching an artifact span": 0}


def trace_shapes(conn, frame, *, resample_length=RESAMPLE_LENGTH, noise_floor=True, align=DEFAULT_ALIGN,
                 detrend=DEFAULT_DETREND, progress=None):
    """Resample and z-normalise every window of a pool table (the Library's
    helpers, at the Library's length) after the alignment and detrend options,
    keep its raw range, its sample-to-sample noise and where its largest swing
    sits, and leave out the windows under their dataset's noise floor."""
    from Working.library.view_filter import dataset_floors
    from Working.training import pool as tpool
    from Working.units import to_mv_factor

    if align not in ALIGNS:
        raise ValueError(f"align must be one of {', '.join(ALIGNS)}; got {align!r}")
    if detrend not in DETRENDS:
        raise ValueError(f"detrend must be one of {', '.join(DETRENDS)}; got {detrend!r}")
    t0 = time.time()
    n_samples = int(resample_length)
    frame = frame.reset_index(drop=True).copy()
    if align == "centre" and not {"stretch_a", "stretch_b"} <= set(frame.columns):
        raise ValueError("centring needs each window's role stretch: re-run the Window pool block (it now carries them)")
    recs = {int(r["id"]): dict(r) for r in conn.execute("SELECT * FROM recordings")}
    floors_all = dataset_floors(conn)
    files = sorted(frame["source_file"].unique().tolist())
    floors = {sf: floors_all.get(sf, {"floor_mv": 0.1, "set": False, "from": "default"}) for sf in files}
    ex = tpool._Exclusions(conn) if align == "centre" else None

    ranges = np.full(len(frame), np.nan)
    noise = np.full(len(frame), np.nan)
    peaks = np.zeros(len(frame))
    starts = frame["start"].to_numpy().astype(np.int64).copy()
    clamped = np.zeros(len(frame), dtype=np.int64)
    pinned = 0
    vectors = np.zeros((len(frame), n_samples), dtype=np.float32)
    sa_col = frame["stretch_a"].to_numpy() if "stretch_a" in frame.columns else None
    sb_col = frame["stretch_b"].to_numpy() if "stretch_b" in frame.columns else None
    groups = list(frame.groupby("recording_id", sort=True))
    for gi, (rid, g) in enumerate(groups):
        if progress is not None:
            progress(gi, len(groups), f"reading recording row {rid}")
        rec = recs[int(rid)]
        factor = to_mv_factor(rec.get("units"))
        x = np.load(rec["npy_path"], mmap_mode="r")
        spans = []
        if ex is not None:
            human, settings = ex.spans(rec)
            spans = sorted(human + settings)
        segs = []
        for i, a, n in zip(g.index.to_numpy(), g["start"].to_numpy(), g["length"].to_numpy()):
            a, n = int(a), int(n)
            seg = np.asarray(x[a:a + n], dtype=float)
            if ex is not None:
                lo, hi = allowed_interval(a, n, stretch=(sa_col[i], sb_col[i]), n_samples=len(x), spans=spans)
                if (lo, hi) == (a, a + n):
                    pinned += 1
                new, cl = recut_start(a, n, swing_index(seg), lo, hi)
                if new != a:
                    a = new
                    seg = np.asarray(x[a:a + n], dtype=float)
                starts[i] = a
                clamped[i] = int(cl)
            peaks[i] = float(swing_index(seg)) / max(1, len(seg) - 1)
            if factor is not None:
                ranges[i] = float(np.ptp(seg)) * float(factor)
                noise[i] = float(1.4826 * np.median(np.abs(np.diff(seg))) / np.sqrt(2.0)) * float(factor)
            segs.append(_detrended(seg) if detrend == "linear" else seg)
        vectors[g.index.to_numpy()] = _ward.shape_vectors(segs, n_samples)
    frame["orig_start"] = frame["start"].to_numpy().astype(np.int64)
    frame["start"] = starts
    frame["clamped"] = clamped
    frame["raw_range_mv"] = ranges
    frame["noise_mv"] = noise
    frame["peak_frac"] = peaks

    floor_of = frame["source_file"].map({sf: float(floors[sf]["floor_mv"]) for sf in files}).to_numpy()
    measured = np.isfinite(ranges)
    under = measured & (ranges < floor_of)
    unmeasured = ~measured
    drop = under if noise_floor else np.zeros(len(frame), dtype=bool)
    dup = np.zeros(len(frame), dtype=bool)
    recut = {"n_moved": 0, "n_clamped": 0, "n_pinned_by_artifact": 0, "n_near_duplicate": 0,
             "n_overlap_within_scale": 0, "by_scale": {}, "rule": ALIGN_RULE[align]}
    if align == "centre":
        live = np.flatnonzero(~drop)
        keep, n_dup, n_ov = near_duplicates(frame.iloc[live])
        dup[live[~keep]] = True
        moved = frame["start"].to_numpy() != frame["orig_start"].to_numpy()
        cl = frame["clamped"].to_numpy().astype(bool)
        sc_col = frame["scale_min"].to_numpy()
        ok = ~drop & ~dup
        recut = {"n_moved": int((moved & ok).sum()), "n_clamped": int((cl & ok).sum()),
                 "n_pinned_by_artifact": int(pinned), "n_near_duplicate": int(n_dup),
                 "n_overlap_within_scale": int(n_ov),
                 "by_scale": {f"{_scale_label(sc)}": {"moved": int((moved & ok & (sc_col == sc)).sum()),
                                                      "clamped": int((cl & ok & (sc_col == sc)).sum()),
                                                      "near_duplicate": int((dup & (sc_col == sc)).sum())}
                              for sc in sorted(np.unique(sc_col))},
                 "rule": ALIGN_RULE["centre"]}
    meta = {
        "resample_length": n_samples, "noise_floor": bool(noise_floor), "align": align, "detrend": detrend,
        "align_rule": ALIGN_RULE[align], "detrend_rule": DETREND_RULE[detrend], "swing_rule": SWING_RULE,
        "recut": recut,
        "floors": {sf: {"floor_mv": float(floors[sf]["floor_mv"]), "from": floors[sf].get("from")} for sf in files},
        "floors_mv": {sf: float(floors[sf]["floor_mv"]) for sf in files},
        "n_in": int(len(frame)),
        "under_floor": {"n": int(drop.sum()), "by": _count_by(frame, drop),
                        "n_would_be": int(under.sum()),
                        "rule": ("a window whose raw range (peak to peak, in mV by the recording's declared unit) is "
                                 "under its dataset's noise floor (Settings › Datasets; 0.1 mV where empty) is left "
                                 "out: normalising throws amplitude away, so a wiggle and a drop would look alike")},
        "unmeasured": {"n": int(unmeasured.sum()), "by": _count_by(frame, unmeasured),
                       "rule": "no declared unit, so no mV range to compare with the floor: kept and counted"},
        "method": "Working.library.grouping.methods.ward.shape_vectors (resample_to_length + z_normalize)",
    }
    drop = drop | dup
    kept = frame.loc[~drop].reset_index(drop=True)
    vecs = vectors[~drop]
    kept["shape_row"] = np.arange(len(kept), dtype=np.int64)
    if align == "centre" and len(kept):
        check_recut(conn, kept)
    meta["n_kept"] = int(len(kept))
    meta["seconds"] = round(time.time() - t0, 2)
    return ShapeSet(frame=kept, vectors=vecs, meta=meta)


# ── the tree ────────────────────────────────────────────────────────────────

@dataclass
class ShapeTree:
    """`Z`: the Ward linkage over `leaf_rows` (rows of the shape frame, in leaf
    order). `train_rows`: every training row the tree's clusters cover."""
    Z: np.ndarray
    leaf_rows: np.ndarray
    train_rows: np.ndarray
    meta: dict = field(default_factory=dict)

    def save(self, d):
        os.makedirs(d, exist_ok=True)
        np.savez_compressed(os.path.join(d, "tree.npz"), Z=np.asarray(self.Z, dtype=np.float64),
                            leaf_rows=np.asarray(self.leaf_rows, dtype=np.int64),
                            train_rows=np.asarray(self.train_rows, dtype=np.int64))
        with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump({"kind": "shape_tree", **self.meta}, fh, indent=2, default=str)
        return d

    @classmethod
    def load(cls, d):
        with np.load(os.path.join(d, "tree.npz"), allow_pickle=False) as z:
            Z, leaf, train = z["Z"], z["leaf_rows"], z["train_rows"]
        meta = {}
        mp = os.path.join(d, "manifest.json")
        if os.path.isfile(mp):
            with open(mp, encoding="utf-8") as fh:
                meta = json.load(fh)
        meta.pop("kind", None)
        return cls(Z=Z, leaf_rows=leaf, train_rows=train, meta=meta)


def tree_key(shapes, sample, seed):
    return _key({"kind": "shape_tree", "shape_key": shapes.key, "sample": None if sample is None else int(sample),
                 "seed": int(seed), "method": "ward"}, [])


def stratified_sample(frame, rows, n, seed=0):
    """`n` of `rows`, seeded, in proportion to each recording × scale stratum
    (largest remainder), sorted. All of them when `n` is None or ≥ len(rows)."""
    rows = np.asarray(rows, dtype=np.int64)
    if n is None or int(n) >= len(rows):
        return np.sort(rows)
    n = int(n)
    sub = frame.iloc[rows]
    strata = list(sub.groupby(["source_file", "scale_min"], sort=True).indices.items())
    sizes = np.array([len(ix) for _k, ix in strata], dtype=float)
    want = sizes * n / sizes.sum()
    base = np.floor(want).astype(int)
    rem = n - base.sum()
    if rem > 0:
        base[np.argsort(-(want - base), kind="stable")[:rem]] += 1
    rng = np.random.default_rng(int(seed))
    out = [rows[ix][rng.choice(len(ix), size=int(b), replace=False)] for (_k, ix), b in zip(strata, base) if b > 0]
    return np.sort(np.concatenate(out)) if out else np.zeros(0, dtype=np.int64)


def cluster_shapes(shapes, *, sample=DEFAULT_SAMPLE, seed=0):
    """The Library's Ward on a seeded, stratified sample of the TRAINING windows."""
    roles = shapes.frame["role"].to_numpy().astype(str)
    train = np.flatnonzero(roles == "train")
    if len(train) < 2:
        raise ValueError(f"the pool holds {len(train)} training window(s) after the noise floor: a tree needs at "
                         "least two. Tick more window sets, or turn the floor off on the Trace shape block")
    leaf = stratified_sample(shapes.frame, train, sample, seed)
    t0 = time.time()
    vec = np.asarray(shapes.vectors[leaf], dtype=np.float64)
    condensed = _ward.condensed_distances(vec)
    Z = _ward.ward_linkage(condensed)
    del condensed
    seconds = time.time() - t0
    meta = {"method": "ward", "method_text": _ward.WardMethod.description, "library_method":
            "Working.library.grouping.methods.ward", "resample_length": int(shapes.vectors.shape[1]),
            "distance_scale": float(_ward.distance_scale(shapes.vectors.shape[1])),
            "sample": None if sample is None else int(sample), "seed": int(seed), "n_train": int(len(train)),
            "n_clustered": int(len(leaf)), "stratified_by": "recording × scale (proportional)",
            "shape_key": shapes.key, "ward_seconds": round(seconds, 2), "peak_rss_mb": peak_rss_mb(),
            "key": tree_key(shapes, sample, seed)}
    return ShapeTree(Z=Z, leaf_rows=leaf, train_rows=train, meta=meta)


def load_tree_for(d, shapes):
    """A kept tree (local or made elsewhere), refused unless it was built on these windows."""
    tree = ShapeTree.load(d)
    if tree.meta.get("shape_key") != shapes.key:
        raise ValueError(f"the tree at {d} was built on other windows (shape key {tree.meta.get('shape_key')}, "
                         f"these windows {shapes.key}): rebuild it on this pool, or open the pool it was built on")
    n = len(shapes.frame)
    if len(tree.leaf_rows) and (int(tree.leaf_rows.max()) >= n or int(tree.train_rows.max()) >= n):
        raise ValueError(f"the tree at {d} names rows past the {n} windows of this pool (other windows)")
    if len(tree.Z) != len(tree.leaf_rows) - 1:
        raise ValueError(f"the tree at {d} has {len(tree.Z) + 1} leaves but lists {len(tree.leaf_rows)} rows")
    return tree


# ── a cut ───────────────────────────────────────────────────────────────────

@dataclass
class Labels:
    labels: np.ndarray            # one per shape-frame row: 1..k for training rows, -1 elsewhere
    k: int
    n_clustered: int
    n_assigned: int
    centres: np.ndarray


def labels_at(tree, shapes, k):
    """Every training window's cluster at `k`: the sample's from the tree, the
    rest the nearest centre (the mean vector of the sampled members)."""
    from scipy.cluster.hierarchy import fcluster
    k = int(k)
    n_leaf = len(tree.leaf_rows)
    if not 1 <= k <= max(1, n_leaf):
        raise ValueError(f"k = {k}: the tree has {n_leaf} leaves")
    labels = np.full(len(shapes.frame), -1, dtype=np.int64)
    leaf_lab = (fcluster(tree.Z, t=k, criterion="maxclust").astype(np.int64) if n_leaf > 1
                else np.ones(n_leaf, dtype=np.int64))
    labels[tree.leaf_rows] = leaf_lab
    ids = np.unique(leaf_lab)
    vec = shapes.vectors
    centres = np.vstack([np.asarray(vec[tree.leaf_rows[leaf_lab == c]], dtype=np.float64).mean(axis=0) for c in ids])
    rest = np.setdiff1d(tree.train_rows, tree.leaf_rows, assume_unique=False)
    if len(rest):
        cc = (centres ** 2).sum(axis=1)
        for a in range(0, len(rest), 4096):
            part = rest[a:a + 4096]
            v = np.asarray(vec[part], dtype=np.float64)
            d = cc[None, :] - 2.0 * v @ centres.T
            labels[part] = ids[np.argmin(d, axis=1)]
    return Labels(labels=labels, k=int(len(ids)), n_clustered=int(n_leaf), n_assigned=int(len(rest)), centres=centres)


def propose(tree, shapes, k_range=K_RANGE, seed=0):
    """Per k: sizes over every training window, specks (`AB`'s rule), silhouette
    on the clustered sample; the suggested k by the baseline's rule."""
    from Working.training.paired import SMALL_CLUSTER_FRAC, SMALL_CLUSTER_MIN, _silhouette
    n_train = len(tree.train_rows)
    small_below = max(SMALL_CLUSTER_MIN, int(np.ceil(SMALL_CLUSTER_FRAC * n_train)))
    X = np.asarray(shapes.vectors[tree.leaf_rows], dtype=np.float64)
    by_k = []
    for k in range(int(k_range[0]), int(k_range[1]) + 1):
        if k > len(tree.leaf_rows):
            break
        lab = labels_at(tree, shapes, k)
        tr = lab.labels[tree.train_rows]
        sizes = {str(c): int((tr == c).sum()) for c in range(1, lab.k + 1)}
        small = [int(c) for c, n in sizes.items() if n < small_below]
        sil = _silhouette(X, lab.labels[tree.leaf_rows], seed=seed) if len(X) > 2 else None
        by_k.append({"k": k, "silhouette": sil, "sizes": sizes, "small_clusters": small,
                     "effective_k": lab.k - len(small), "cut_height": cut_height(tree, k)})
    scored = [r for r in by_k if r["silhouette"] is not None and r["effective_k"] >= 2]
    suggested = max(scored, key=lambda r: (round(r["silhouette"], 3), r["effective_k"]))["k"] if scored else None
    return {"by_k": by_k, "suggested_k": suggested, "small_below": small_below, "n_train": int(n_train),
            "suggestion_rule": (f"best silhouette among cuts with at least two clusters of {small_below}+ windows "
                                "(the baseline's written rule); smaller clusters are specks and do not count"),
            "note": "silhouette on the clustered sample (a stratified sample of it past 8,000), Euclidean on the "
                    "normalised shapes; a guide, the cut is the researcher's"}


def propose_cached(tree, shapes, d, k_range=K_RANGE, seed=0):
    """`(proposal, cached)`: `propose`, kept beside its tree (`propose.json`) and read back while the tree, the
    windows and the k range are the same — it costs tens of seconds on 20,000 windows."""
    path = os.path.join(d, "propose.json")
    stamp = {"tree": tree.meta.get("key"), "shape_key": shapes.key, "k_range": [int(k_range[0]), int(k_range[1])],
             "seed": int(seed), "n_leaves": int(len(tree.leaf_rows))}
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as fh:
                saved = json.load(fh)
            if saved.get("stamp") == stamp:
                return saved["proposal"], True
        except (ValueError, KeyError):
            pass
    prop = propose(tree, shapes, k_range=k_range, seed=seed)
    os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"stamp": stamp, "proposal": prop}, fh, default=float)
    return json.loads(json.dumps(prop, default=float)), False


def cut_height(tree, k):
    """A height that cuts the tree into exactly `k` clusters (the midpoint of the gap)."""
    h = np.sort(np.asarray(tree.Z[:, 2], dtype=float))
    n = len(h)
    if n == 0:
        return 0.0
    k = int(max(1, min(int(k), n + 1)))
    lo = h[n - k] if k <= n else 0.0
    hi = h[n - k + 1] if k >= 2 else h[-1] * 1.05 + 1e-9
    return float((lo + hi) / 2.0)


def k_at_height(tree, height):
    """How many clusters a cut at `height` makes."""
    h = np.asarray(tree.Z[:, 2], dtype=float)
    return int((h > float(height)).sum()) + 1


def dendrogram(tree, leaves=DEFAULT_DENDROGRAM_LEAVES):
    """The tree truncated to its last `leaves` merges, as drawing coordinates."""
    from scipy.cluster.hierarchy import dendrogram as _dg
    n = len(tree.leaf_rows)
    if n < 2:
        return {"icoord": [], "dcoord": [], "leaves": [], "counts": [], "heights": []}
    p = int(max(2, min(int(leaves), n)))
    d = _dg(tree.Z, truncate_mode="lastp", p=p, no_plot=True, count_sort=False, distance_sort=False)
    # the size of each truncated leaf: "(123)" for a merged one, else 1
    counts = []
    for lab in d["ivl"]:
        s = str(lab)
        counts.append(int(s.strip("()")) if s.startswith("(") else 1)
    return {"icoord": [[float(v) for v in r] for r in d["icoord"]], "dcoord": [[float(v) for v in r] for r in d["dcoord"]],
            "leaves": [str(v) for v in d["ivl"]], "counts": counts,
            "heights": [float(v) for v in np.sort(tree.Z[:, 2])[::-1][:max(40, p)]],
            "max_height": float(tree.Z[:, 2].max()), "n_leaves": int(n)}


# ── a cluster ───────────────────────────────────────────────────────────────

def _window(frame, vectors, row):
    r = frame.iloc[int(row)]
    rr = r.get("raw_range_mv")
    return {"row": int(row), "recording_id": int(r["recording_id"]), "source_file": str(r["source_file"]),
            "channel": int(r["channel"]), "start": int(r["start"]), "length": int(r["length"]), "fs": float(r["fs"]),
            "scale_min": _scale_label(r["scale_min"]), "role": str(r["role"]),
            "raw_range_mv": None if rr is None or not np.isfinite(rr) else float(rr),
            "peak_frac": float(r["peak_frac"]) if "peak_frac" in r and np.isfinite(r["peak_frac"]) else None,
            "shape": [round(float(v), 4) for v in vectors[int(row)]]}


def cluster_detail(tree, shapes, lab, cluster, *, n_members=DEFAULT_MEMBERS, seed=0):
    """What a clicked cluster shows: its medoid (the most typical REAL window — a
    centre in shape space is not a trace), a seeded handful of members, the mean
    normalised shape with its spread, the count, the scale and recording mix and
    the raw amplitude range."""
    labels = lab.labels
    idx = np.flatnonzero(labels == int(cluster))
    if not len(idx):
        raise ValueError(f"no cluster {cluster} at k = {lab.k} (clusters 1–{lab.k})")
    rng = np.random.default_rng(int(seed))
    pool_for_medoid = idx if len(idx) <= MEDOID_CAP else np.sort(rng.choice(idx, MEDOID_CAP, replace=False))
    V = np.asarray(shapes.vectors[pool_for_medoid], dtype=np.float64)
    sq = (V ** 2).sum(axis=1)
    D = np.sqrt(np.maximum(sq[:, None] + sq[None, :] - 2.0 * V @ V.T, 0.0))
    medoid = int(pool_for_medoid[int(np.argmin(D.sum(axis=1)))])
    rng2 = np.random.default_rng(int(seed) + 1)
    picks = np.sort(rng2.choice(idx, size=min(int(n_members), len(idx)), replace=False))
    allv = np.asarray(shapes.vectors[idx], dtype=np.float64)
    f = shapes.frame.iloc[idx]
    rr = f["raw_range_mv"].to_numpy(dtype=float) if "raw_range_mv" in f.columns else np.full(len(f), np.nan)
    fin = rr[np.isfinite(rr)]
    amp = ({"min": float(fin.min()), "q25": float(np.quantile(fin, 0.25)), "median": float(np.median(fin)),
            "q75": float(np.quantile(fin, 0.75)), "max": float(fin.max()), "n_measured": int(len(fin))}
           if len(fin) else {"min": None, "q25": None, "median": None, "q75": None, "max": None, "n_measured": 0})
    pk = f["peak_frac"].to_numpy(dtype=float) if "peak_frac" in f.columns else np.zeros(0)
    hist = np.histogram(pk, bins=10, range=(0.0, 1.0))[0].tolist() if len(pk) else []
    in_sample = int(np.isin(idx, tree.leaf_rows).sum())
    return {"cluster": int(cluster), "k": int(lab.k), "n": int(len(idx)), "n_in_sample": in_sample,
            "n_assigned": int(len(idx) - in_sample),
            "medoid": {**_window(shapes.frame, shapes.vectors, medoid),
                       "rule": (f"the member with the smallest summed distance to the others"
                                f"{'' if len(idx) <= MEDOID_CAP else f' (among {MEDOID_CAP:,} members drawn with seed {seed})'}")},
            "members": [_window(shapes.frame, shapes.vectors, r) for r in picks], "members_seed": int(seed),
            "mean": [round(float(v), 4) for v in allv.mean(axis=0)], "sd": [round(float(v), 4) for v in allv.std(axis=0)],
            "scales": [{"scale_min": _scale_label(s), "n": int(n)} for s, n in f["scale_min"].value_counts().sort_index().items()],
            "recordings": [{"recording": sf, "n": int(n)} for sf, n in f["source_file"].value_counts().sort_index().items()],
            "channels": [{"recording": sf, "channel": int(ch), "n": int(n)}
                         for (sf, ch), n in f.groupby(["source_file", "channel"]).size().items()],
            "amplitude_mv": amp, "peak_position_hist": hist}


def clusters_summary(tree, shapes, lab):
    """One line per cluster at this cut — what the mapping table lists."""
    from Working.training.paired import SMALL_CLUSTER_FRAC, SMALL_CLUSTER_MIN
    small_below = max(SMALL_CLUSTER_MIN, int(np.ceil(SMALL_CLUSTER_FRAC * len(tree.train_rows))))
    out = []
    f = shapes.frame
    for c in range(1, lab.k + 1):
        m = lab.labels == c
        sub = f.loc[m]
        rr = sub["raw_range_mv"].to_numpy(dtype=float) if "raw_range_mv" in sub.columns else np.zeros(0)
        fin = rr[np.isfinite(rr)]
        out.append({"cluster": c, "n": int(m.sum()), "speck": bool(m.sum() < small_below),
                    "scales": {f"{_scale_label(s)}": int(n) for s, n in sub["scale_min"].value_counts().sort_index().items()},
                    "recordings": {sf: int(n) for sf, n in sub["source_file"].value_counts().sort_index().items()},
                    "median_range_mv": float(np.median(fin)) if len(fin) else None,
                    "peak_frac_median": float(np.median(sub["peak_frac"])) if "peak_frac" in sub.columns and len(sub) else None})
    return {"clusters": out, "small_below": small_below}


CARD_MEMBERS = 4
CARD_MEDOID_CAP = 300


def cluster_cards(tree, shapes, lab, *, n_members=CARD_MEMBERS, medoid_cap=CARD_MEDOID_CAP, seed=0):
    """One card per cluster at this cut — EVERY cluster, so a cut of 24 shows 24 (the researcher, 2026-10-06): its
    medoid (among at most `medoid_cap` seeded members), `n_members` seeded members, its size and scale mix. Read from
    the kept tree and the shape vectors alone; nothing is re-run."""
    f = shapes.frame
    out = []
    for c in range(1, lab.k + 1):
        idx = np.flatnonzero(lab.labels == c)
        if not len(idx):
            out.append({"cluster": c, "n": 0, "error": f"cluster {c} has no members at k = {lab.k}"})
            continue
        rng = np.random.default_rng(int(seed) + c)
        pool_for_medoid = idx if len(idx) <= medoid_cap else np.sort(rng.choice(idx, medoid_cap, replace=False))
        V = np.asarray(shapes.vectors[pool_for_medoid], dtype=np.float64)
        sq = (V ** 2).sum(axis=1)
        D = np.sqrt(np.maximum(sq[:, None] + sq[None, :] - 2.0 * V @ V.T, 0.0))
        medoid = int(pool_for_medoid[int(np.argmin(D.sum(axis=1)))])
        rest = idx[idx != medoid]
        picks = np.sort(rng.choice(rest, size=min(int(n_members), len(rest)), replace=False)) if len(rest) else np.zeros(0, int)
        sub = f.iloc[idx]
        out.append({"cluster": c, "n": int(len(idx)),
                    "scales": {f"{_scale_label(s)}": int(n) for s, n in sub["scale_min"].value_counts().sort_index().items()},
                    "medoid": _window(f, shapes.vectors, medoid),
                    "members": [_window(f, shapes.vectors, r) for r in (picks if len(picks) else [medoid])]})
    return out
