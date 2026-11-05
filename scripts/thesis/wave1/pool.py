"""
wave1.pool — step 13, the candidate-event pool, and the frozen R4 MiniRocket scorer (shared with step 14).

For each candidate-event table (``Working/discovery/candidate_events.py``'s ``events.parquet``) of a kept recording
(never M4, never *S. commune*; MJu26a_fs2 preferred over its five-channel L_LM fs2 copy when both have tables):

1. counts at n_agree >= 5 and >= 9, and per agreement level (5-6, 7-8, 9+);
2. nested candidates among n_agree >= 5 collapsed per channel by greedy suppression: ordered by n_agree descending,
   then span length ascending (then start, then event id, so the order is total); a candidate is kept unless at
   least 50 % of its span is already covered by kept ones (a boolean coverage array per channel at 1-s resolution).
   The order puts every >= 9 candidate before every < 9 one, so the kept >= 9 set is also the >= 9 set collapsed
   on its own;
3. a stratified random sample (seed 0) of up to 2,000 kept events per recording, an equal share per level (a
   level with fewer events gives its unused share to the others); each sampled event measured exactly as
   ``scripts/thesis/b12_shapes_intervals.py`` ``measure()`` does (``Working.interrogation.event_shape.measure_events``,
   polarity "auto", ``to_mv`` from ``read_as_mv``; per channel, all of that channel's sampled events in one call)
   with the 64-point normalised waveform; scored with the frozen R4 exactly as ``scripts/m4_exam_score.py``
   ``minirocket_scorer`` does (``rq1b_minirocket.extract`` + ``decision``, the model's own length and pad); and
   flagged when it overlaps any seed-search match (a live Discovery seed run's detections);
4. thumbnails: 20 random sampled events per level per recording, span +- one span length (at most 4,000 points).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import time

import numpy as np
import pandas as pd

from wave1 import common as C

WAVE_N = 64
LEVELS_DEFAULT = ((5, 6), (7, 8), (9, None))


# ── the frozen R4 MiniRocket ─────────────────────────────────────────────────────────────────────────────

class R4Unavailable(RuntimeError):
    pass


def _sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


class R4:
    """The frozen MiniRocket R4 (the M4 exam manifest's ``models.minirocket_R4``), applied as
    ``scripts/m4_exam_score.py`` ``minirocket_scorer`` applies it: ``rq1b_minirocket.extract(conn, rows,
    length=model['length'], pad=model.get('pad', PAD))`` then ``decision`` on the readable rows; decision > 0 is
    "interesting". Rows are scored in batches so the MiniRocket features of many events are never all in memory."""

    source = "R4"

    def __init__(self, ctx):
        cfg = ctx.spec.get("r4") or {}
        man = None
        for key in ("manifest", "manifest_tracked"):
            p = ctx.path(cfg.get(key) or "")
            if cfg.get(key) and os.path.isfile(p):
                with open(p, encoding="utf-8") as fh:
                    man = json.load(fh)
                self.manifest_path = p
                break
        model_dir = cfg.get("model_dir")
        want_sha = None
        if man is not None:
            m = (man.get("models") or {}).get("minirocket_R4") or {}
            model_dir = model_dir or m.get("dir")
            want_sha = ((m.get("files") or {}).get("model.joblib") or {}).get("sha256")
        if not model_dir:
            raise R4Unavailable("no R4 model directory: neither the exam manifest nor bundle_spec.json names one")
        path = model_dir if os.path.isabs(model_dir) else ctx.path(model_dir)
        path = os.path.join(path, "model.joblib")
        if not os.path.isfile(path):
            raise R4Unavailable(f"the R4 model file is absent: {path}")
        self.model_path = path
        self.sha256 = _sha_file(path)
        self.sha_ok = (want_sha is None) or (self.sha256 == want_sha)
        if not self.sha_ok:
            ctx.warn(f"R4 model sha256 {self.sha256} differs from the exam manifest's {want_sha}: scores are written "
                     "but flagged (r4_model_sha256_ok = False)")
        script = os.path.join(C.CODE_ROOT, "scripts", "rq1b_minirocket.py")
        if not os.path.isfile(script):
            script = ctx.path("scripts", "rq1b_minirocket.py")
        try:
            spec = importlib.util.spec_from_file_location("_wave1_rq1b_minirocket", script)
            mr = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mr)
            self.mr = mr
            self.model = mr.load_model(path)
            # extract() resolves a relative npy_path against the module's DATA_ROOT (the main checkout); point it at
            # the root this export reads, so R4 and every other step read the same channel files
            if os.path.abspath(str(getattr(mr, "DATA_ROOT", ""))) != os.path.abspath(ctx.root):
                ctx.log(f"R4 channel root {getattr(mr, 'DATA_ROOT', None)} -> {ctx.root}")
                mr.DATA_ROOT = ctx.root
        except ImportError as e:
            raise R4Unavailable(f"R4 cannot be loaded here ({e}): needs joblib, scikit-learn and aeon") from e
        self.length = int(self.model["length"])
        self.pad = float(self.model.get("pad", getattr(mr, "PAD", 0.25)))
        self.batch = int(cfg.get("batch", 256))
        self.ctx = ctx

    def score(self, rows):
        """`rows`: DataFrame(recording_id, start, end). Returns DataFrame(r4_decision, r4_readable, duration_s,
        p2p_mv, noise_mv, snr) in row order."""
        rows = rows[["recording_id", "start", "end"]].reset_index(drop=True)
        dec = np.full(len(rows), np.nan)
        keep_all = np.zeros(len(rows), bool)
        sides = []
        for a in range(0, len(rows), self.batch):
            self.ctx.tick()
            b = rows.iloc[a:a + self.batch].reset_index(drop=True)
            M, side, keep = self.mr.extract(self.ctx.conn, b, length=self.length, pad=self.pad)
            keep = np.asarray(keep, bool)
            if keep.any():
                dec[a:a + len(b)][keep] = self.mr.decision(self.model, M[keep], side[keep].reset_index(drop=True))
            keep_all[a:a + len(b)] = keep
            sides.append(side.reset_index(drop=True))
        side = pd.concat(sides, ignore_index=True) if sides else pd.DataFrame()
        out = pd.DataFrame({"r4_decision": dec, "r4_readable": keep_all})
        for c in side.columns:
            out[f"r4_side_{c}"] = side[c].to_numpy()
        out["r4_interesting"] = np.where(np.isfinite(dec), dec > 0, np.nan)
        out["r4_source"] = self.source
        out["r4_model_sha256_ok"] = self.sha_ok
        return out


def make_r4_scorer(ctx):
    """The R4 scorer, built once per run. Raises R4Unavailable with the reason when it cannot be built."""
    if "r4" not in ctx.cache:
        try:
            t = time.time()
            ctx.cache["r4"] = R4(ctx)
            ctx.log(f"R4 loaded from {ctx.cache['r4'].model_path} in {time.time() - t:.1f}s "
                    f"(sha256 ok: {ctx.cache['r4'].sha_ok})")
        except R4Unavailable as e:
            ctx.cache["r4"] = e
        except Exception as e:  # noqa: BLE001 - reported, the steps go on without scores
            ctx.log_exception("loading R4")
            ctx.cache["r4"] = R4Unavailable(f"R4 failed to load: {e!r}")
    got = ctx.cache["r4"]
    if isinstance(got, Exception):
        raise got
    return got


def r4_scores(ctx, rows):
    """R4 scores for `rows`, or NaN columns with the reason when R4 is unavailable."""
    try:
        sc = make_r4_scorer(ctx)
    except R4Unavailable as e:
        ctx.warn(f"R4 scores not computed: {e}")
        return pd.DataFrame({"r4_decision": np.full(len(rows), np.nan), "r4_readable": False,
                             "r4_interesting": np.nan, "r4_source": f"unavailable: {e}"})
    t = time.time()
    out = sc.score(rows)
    ctx.log(f"R4 scored {len(rows):,} spans in {time.time() - t:.1f}s")
    return out


# ── b12's measure(), per channel ─────────────────────────────────────────────────────────────────────────

FEATURES = ["amplitude_mv", "swing_mv", "span_s", "duration_s", "onset_to_extremum_s", "rise_time_s",
            "recovery_time_s", "fwhm_s", "max_slope_abs_mv_s", "peakedness", "asymmetry", "width_frac",
            "norm_slope", "is_drop"]


def measure_spans(x, starts, ends, fs, to_mv):
    """scripts/thesis/b12_shapes_intervals.py measure(), the per-event rows: event_shape features plus the
    64-point normalised waveform (span resampled to 64 points, median removed, divided by its peak-to-peak).
    `x` is the channel as stored (mmap), the spans channel-absolute. Returns (DataFrame, waves n x 64)."""
    from Working.interrogation import event_shape as ES
    s_, e_ = np.asarray(starts, int), np.asarray(ends, int)
    f, _ = ES.measure_events(x, s_, e_, fs, polarity="auto", to_mv=to_mv)
    rows, waves = [], []
    for i, (s, e) in enumerate(zip(s_, e_)):
        fr = f.iloc[i]
        amp = abs(float(fr["event_amplitude_mv"]))
        dur = float(fr["duration_s"])
        o2x = (float(fr["extremum_idx"]) - float(fr["onset_idx"])) / fs
        x2r = (float(fr["recovery_idx"]) - float(fr["extremum_idx"])) / fs
        slope = abs(float(fr["max_slope_mv_s"]))
        seg = np.asarray(x[s:e], dtype=float) * to_mv
        if seg.size >= 4 and np.isfinite(seg).all() and np.ptp(seg) > 0:
            w = np.interp(np.linspace(0, seg.size - 1, WAVE_N), np.arange(seg.size), seg)
            w = (w - np.median(w)) / np.ptp(w)
        else:
            w = np.full(WAVE_N, np.nan)
        waves.append(w)
        rows.append({
            "span_s": (e - s) / fs, "amplitude_mv": amp, "swing_mv": float(fr["span_ptp_mv"]), "duration_s": dur,
            "onset_to_extremum_s": o2x, "rise_time_s": float(fr["rise_time_s"]),
            "recovery_time_s": float(fr["recovery_time_s"]), "fwhm_s": float(fr["fwhm_s"]),
            "max_slope_abs_mv_s": slope, "peakedness": float(fr["peakedness"]),
            "asymmetry": o2x / (o2x + x2r) if np.isfinite(x2r) and (o2x + x2r) > 0 else np.nan,
            "width_frac": float(fr["fwhm_s"]) / dur if dur and np.isfinite(dur) and dur > 0 else np.nan,
            "norm_slope": slope * dur / amp if amp > 0 and np.isfinite(dur) else np.nan,
            "is_drop": 1.0 if int(fr["polarity"]) == ES.DROP else 0.0,
        })
    return pd.DataFrame(rows), (np.vstack(waves) if waves else np.zeros((0, WAVE_N)))


def measure_events_of(ctx, ev):
    """b12's measure() over `ev` (recording_id, start, end), one channel at a time. Returns (features in ev's order,
    waves in ev's order, note per row)."""
    feats = pd.DataFrame(index=ev.index, columns=FEATURES, dtype=float)
    waves = np.full((len(ev), WAVE_N), np.nan, dtype=np.float32)
    pos = {ix: k for k, ix in enumerate(ev.index)}
    notes = pd.Series("", index=ev.index, dtype=object)
    for rid, g in ev.groupby("recording_id"):
        ctx.tick()
        rec = ctx.rec(rid)
        to_mv, note = C.mv_factor(rec)
        try:
            x = C.channel_array(ctx, rec)
            f, w = measure_spans(x, g["start"].to_numpy(int), g["end"].to_numpy(int), float(rec["fs"]), to_mv)
        except Exception as e:  # noqa: BLE001 - one channel failing leaves its rows empty, with the reason
            ctx.log_exception(f"measure recording {rid}")
            notes.loc[g.index] = f"measure failed: {e!r}"[:200]
            continue
        f.index = g.index
        feats.loc[g.index, f.columns] = f.to_numpy()
        for k, ix in enumerate(g.index):
            waves[pos[ix]] = w[k]
        if note:
            notes.loc[g.index] = note
    return feats, waves, notes


# ── collapse and sample ──────────────────────────────────────────────────────────────────────────────────

def level_name(lo, hi):
    return f"{lo}-{hi}" if hi is not None else f"{lo}+"


def level_of(n_agree, levels):
    out = np.full(len(n_agree), None, dtype=object)
    for lo, hi in levels:
        m = (n_agree >= lo) & ((n_agree <= hi) if hi is not None else True)
        out[m] = level_name(lo, hi)
    return out


def collapse(ev, fs_of, n_of, min_agree=5):
    """Greedy suppression of nested candidates per channel (recording_id), among n_agree >= min_agree: n_agree
    descending, then span length ascending, then start, then event id; keep a candidate unless >= 50 % of its span
    (in 1-s bins) is already covered by kept ones. Returns a boolean Series (kept) over `ev`."""
    keep = pd.Series(False, index=ev.index)
    sel = ev[ev["n_agree"] >= min_agree]
    for rid, g in sel.groupby("recording_id"):
        fs = float(fs_of[int(rid)])
        n_bins = int(math.ceil(int(n_of[int(rid)]) / fs)) + 2
        a = np.floor(g["start"].to_numpy(np.int64) / fs).astype(np.int64)
        b = np.ceil(g["end"].to_numpy(np.int64) / fs).astype(np.int64)
        b = np.maximum(b, a + 1)
        a, b = np.clip(a, 0, n_bins - 1), np.clip(b, 1, n_bins)
        order = np.lexsort((g["event_id"].to_numpy(), g["start"].to_numpy(), b - a, -g["n_agree"].to_numpy()))
        cov = np.zeros(n_bins, dtype=bool)
        k = np.zeros(len(g), dtype=bool)
        for i in order:
            lo, hi = a[i], b[i]
            if 2 * np.count_nonzero(cov[lo:hi]) >= (hi - lo):
                continue
            k[i] = True
            cov[lo:hi] = True
        keep.loc[g.index] = k
    return keep


def allocate(sizes, total):
    """An equal share of `total` per level, capped by each level's size; unused shares go to the others."""
    out = {k: 0 for k in sizes}
    left = min(int(total), int(sum(sizes.values())))
    open_ = [k for k in sizes if sizes[k] > 0]
    while left > 0 and open_:
        share = max(1, left // len(open_))
        for k in list(open_):
            take = min(share, sizes[k] - out[k], left)
            out[k] += take
            left -= take
            if out[k] >= sizes[k]:
                open_.remove(k)
            if left <= 0:
                break
    return out


def seed_match_spans(ctx, recording_ids):
    """{recording_id: (starts, ends)} of every live seed search's matches (real runs) on these recordings: the runs
    of live Discovery seed runs, by run group or by ``params_json.run_ids`` (common.runs_on)."""
    runs = C.runs_on(ctx, recording_ids, kinds=("seed",))
    out = {}
    for run in runs.itertuples():
        det = C.detections_of_run(ctx, run.run_id, run.span_start)
        s, e = out.get(int(run.recording_id), (np.zeros(0, np.int64), np.zeros(0, np.int64)))
        out[int(run.recording_id)] = (np.r_[s, det["start"].to_numpy(np.int64)],
                                      np.r_[e, det["end"].to_numpy(np.int64)])
    return out


def choose_tables(ctx):
    """The tables the pool reads: the newest per kept recording, never M4 or S. commune; MJu26a_fs2 over its
    L_LM fs2 copy when both exist. Returns (list of (short, table), notes)."""
    cfg = ctx.spec.get("pool") or {}
    chosen, notes = [], []
    for short, sf in ctx.kept.items():
        if sf == C.HELD_OUT_FILE or C.is_refused(sf):
            continue
        t = C.newest_table(ctx, sf)
        if t is not None:
            chosen.append((short, t))
    names = {s for s, _ in chosen}
    for prefer, over in (cfg.get("prefer_over") or {}).items():
        if prefer in names and over in names:
            chosen = [(s, t) for s, t in chosen if s != over]
            notes.append(f"{prefer} used; its copy {over} left out (the same organism's channels)")
        elif over in names:
            notes.append(f"{prefer} has no table: {over} used in its place")
    return chosen, notes


def step_pool(ctx):
    d = ctx.step_dir()
    cfg = ctx.spec.get("pool") or {}
    levels = [tuple(x) for x in (cfg.get("levels") or LEVELS_DEFAULT)]
    per_rec = int(cfg.get("per_recording", 2000))
    n_thumb = int(cfg.get("thumbnails_per_level", 20))
    seed = int(cfg.get("seed", 0))
    chosen, notes = choose_tables(ctx)
    for n in notes:
        ctx.log(n)
    counts = []
    for short, tab in chosen:
        ctx.tick()
        t0 = time.time()
        sf = tab["source_file"]
        ev = C.read_events(tab, ["event_id", "recording_id", "channel", "start", "end", "n_agree", "label",
                                 "anchor_variant", "anchor_detection_id"])
        ev = ev[ev["recording_id"].isin([int(r["id"]) for r in ctx.channels_of(sf)])]
        fs_of = {int(r["id"]): float(r["fs"]) for r in ctx.channels_of(sf)}
        n_of = {int(r["id"]): int(r["n_samples"]) for r in ctx.channels_of(sf)}
        ev["level"] = level_of(ev["n_agree"].to_numpy(), levels)
        row = {"recording": short, "source_file": sf, "table_key": tab["key"], "table_created_at": tab["created_at"],
               "table_why": tab.get("why"),
               "n_events": int(len(ev)), "n_ge5": int((ev["n_agree"] >= 5).sum()),
               "n_ge9": int((ev["n_agree"] >= 9).sum())}
        for lo, hi in levels:
            row[f"n_{level_name(lo, hi)}"] = int((ev["level"] == level_name(lo, hi)).sum())
        tc = time.time()
        kept = collapse(ev, fs_of, n_of, min_agree=min(lo for lo, _ in levels))
        row["collapse_s"] = round(time.time() - tc, 1)
        kv = ev[kept]
        row["collapsed_ge5"] = int(len(kv))
        row["collapsed_ge9"] = int((kv["n_agree"] >= 9).sum())
        for lo, hi in levels:
            row[f"collapsed_{level_name(lo, hi)}"] = int((kv["level"] == level_name(lo, hi)).sum())
        ctx.log(f"pool {short}: {len(ev):,} candidates, {row['n_ge5']:,} at >=5 -> {len(kv):,} after collapse "
                f"({row['collapse_s']}s)")
        C.write_csv(os.path.join(d, f"collapsed_{short}.csv"),
                    kv[["event_id", "recording_id", "channel", "start", "end", "n_agree", "level", "label"]])
        # the stratified sample
        rng = np.random.default_rng(seed)
        sizes = {level_name(lo, hi): int((kv["level"] == level_name(lo, hi)).sum()) for lo, hi in levels}
        quota = allocate(sizes, per_rec)
        parts = []
        for lv, q in quota.items():
            g = kv[kv["level"] == lv].sort_values("event_id")
            if q:
                parts.append(g.iloc[np.sort(rng.choice(len(g), size=q, replace=False))])
        samp = pd.concat(parts) if parts else kv.iloc[0:0]
        samp = samp.sort_values(["recording_id", "start", "event_id"]).copy()
        for lv in quota:
            row[f"sampled_{lv}"] = int(quota[lv])
        extra = C.read_events(tab, ["event_id", "n_members", "n_matched_families", "matched_families",
                                    "agree_families", "label_kind", "label_basis", "inside_interesting"],
                              filters=[("event_id", "in", [int(x) for x in samp["event_id"]])]) if len(samp) else None
        if extra is not None and len(extra):
            samp = samp.merge(extra, on="event_id", how="left")
        samp.index = range(len(samp))
        samp.insert(0, "table_key", tab["key"])
        samp.insert(0, "source_file", sf)
        samp.insert(0, "recording", short)
        samp["fs"] = samp["recording_id"].map(fs_of)
        samp["start_s"], samp["end_s"] = samp["start"] / samp["fs"], samp["end"] / samp["fs"]
        # shape features (b12's measure)
        tm = time.time()
        feats, waves, mnotes = measure_events_of(ctx, samp)
        samp = pd.concat([samp, feats], axis=1)
        samp["measure_note"] = mnotes
        row["measure_s"] = round(time.time() - tm, 1)
        # R4
        tr = time.time()
        sc = r4_scores(ctx, samp[["recording_id", "start", "end"]])
        sc.index = samp.index
        samp = pd.concat([samp, sc], axis=1)
        row["r4_s"] = round(time.time() - tr, 1)
        row["r4_source"] = str(sc["r4_source"].iloc[0]) if len(sc) else None
        # seed-search overlap
        seeds = seed_match_spans(ctx, list(fs_of))
        samp["overlaps_seed_match"] = False
        for rid, g in samp.groupby("recording_id"):
            s, e = seeds.get(int(rid), (np.zeros(0), np.zeros(0)))
            samp.loc[g.index, "overlaps_seed_match"] = C.touched(g["start"], g["end"], s, e)
        C.write_csv(os.path.join(d, f"pool_sample_{short}.csv"), samp)
        meta = {"what": f"the 64-point normalised waveform of each sampled event of pool_sample_{short}.csv, in its "
                        "row order (b12 measure(): span resampled to 64 points, median removed, / peak-to-peak; "
                        "unitless)", "source_file": sf, "table_key": tab["key"], "rows": "pool_sample csv rows",
                "event_id": samp["event_id"].astype(int).tolist()}
        np.savez_compressed(os.path.join(d, f"pool_waveforms_{short}.npz"), waves=waves.astype(np.float32),
                            event_id=samp["event_id"].to_numpy(np.int64))
        C.write_json(os.path.join(d, f"pool_waveforms_{short}.json"), meta)
        # thumbnails
        trng = np.random.default_rng(seed)
        th = []
        for lv in quota:
            g = samp[samp["level"] == lv]
            k = min(n_thumb, len(g))
            if k:
                th.append(g.iloc[np.sort(trng.choice(len(g), size=k, replace=False))])
        th = pd.concat(th) if th else samp.iloc[0:0]
        items = [{"recording_id": int(r.recording_id), "start": int(r.start), "end": int(r.end),
                  "event_id": int(r.event_id), "level": r.level, "n_agree": int(r.n_agree)} for r in th.itertuples()]
        segs, idx, _ = C.window_rows(ctx, items)
        C.save_stack(ctx, os.path.join(d, f"pool_thumbnails_{short}"), segs, idx,
                     {"what": f"{n_thumb} random sampled events per level of {short}: span +- one span length (at most "
                              "4,000 points)", "table_key": tab["key"]})
        row["thumbnails"] = len(segs)
        row["total_s"] = round(time.time() - t0, 1)
        counts.append(row)
        C.write_csv(os.path.join(d, "pool_counts.csv"), pd.DataFrame(counts))
        ctx.log(f"pool {short}: sampled {len(samp)} in {row['total_s']}s")
    C.write_csv(os.path.join(d, "pool_counts.csv"), pd.DataFrame(counts))
    C.write_json(os.path.join(d, "pool_tables.json"), {"used": [{"recording": s, "table_key": t["key"],
                                                                  "source_file": t["source_file"]}
                                                                 for s, t in chosen], "notes": notes})
    return {"tables": len(chosen), "notes": notes,
            "per_recording": {r["recording"]: {k: r[k] for k in ("n_ge5", "n_ge9", "collapsed_ge5", "collapsed_ge9")}
                              for r in counts}}
