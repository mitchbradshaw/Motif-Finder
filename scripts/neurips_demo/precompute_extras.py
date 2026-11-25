"""Everything the demo shows besides the builder grid: Auto-detect, the Library, the seed shelf, the statistics.

    "/c/ProgramData/anaconda3/python.exe" scripts/neurips_demo/precompute_extras.py [--stage auto,library,seeds,surrogates,stats]

Run from the demo worktree's root, after build_slices.py (and, for `stats`, after precompute_chains.py). Reads the
real checkout READ ONLY (the 24 Nov drop pool, the 23 Nov per-drop table) and writes under DATA/neurips_demo/store/:

    auto/<slice>.json           Auto-detect's drops on the slice (v4, drops only, confidence >= 0.5): the 24 Nov pool's
                                candidates, unchanged, in slice samples
    library.json                the researcher-accepted drops in the slices, their snippets, shape families, trains
    seeds.json                  the seed shelf, each seed searched over all 12 slices with its null and cut
    surrogates/<slice>.npy      3 phase-randomised copies per slice (float32), for the live seed search's null
    stats/<source>/<dataset>.json   Spike statistics per source (a builder setting, the library, Auto-detect)

Amplitudes are in mV everywhere in the store (a slice stored in V is multiplied by 1000 when it is read).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import demo_config as C  # noqa: E402

REAL = Path(C.REAL_ROOT)
DEMO = ROOT / C.DEMO_DATA
STORE = DEMO / "store"
DROP_TABLE = REAL / "docs/library_analysis/20261123_plots/events.csv"


# ── helpers ──────────────────────────────────────────────────────────────────────────────────────────────────────

def _slices():
    meta = json.loads((STORE / "slices.json").read_text())
    return meta["slices"]


def _mv(s):
    x = np.load(ROOT / s["npy"], mmap_mode="r")
    k = 1000.0 if (s["units"] or "V") == "V" else 1.0
    return np.asarray(x, dtype=np.float64) * k


def _num(v, nd=4):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if not math.isfinite(f) else round(f, nd)


def _write(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, separators=(",", ":")))
    os.replace(tmp, path)


def snippet(x, a, b, fs, *, n_max=160):
    """x[a:b] as at most n_max points (min/max-preserving stride), times in s from a, values in mV."""
    a, b = max(0, int(a)), min(len(x), int(b))
    seg = x[a:b]
    if len(seg) == 0:
        return {"t": [], "v": []}
    step = max(1, int(math.ceil(len(seg) / n_max)))
    idx = np.arange(0, len(seg), step)
    return {"dt": step / fs, "v": [round(float(v), 4) for v in seg[idx]]}


# ── Auto-detect (Explore + Discovery reference) ──────────────────────────────────────────────────────────────────

#: The 24 Nov pool's own quality rules (flags/): a drop is shown when none of these is set and its clarity (depth /
#: MAD of the residual about a 10 s median) is at least CLARITY. They take out lion's mane CH5's and split gill's
#: oscillation swings and the noisy stretches, as the pool's core tier did.
POOL_FLAGS = ["unclear", "swings_back", "too_long", "ctx_nan", "ctx_flat", "ctx_artifact", "ctx_jump", "glitch"]
CLARITY = 15.0


def _clean_pool(f):
    f = f[(f.polarity == "drop") & (f.confidence >= C.AUTO_MIN_CONFIDENCE)]
    bad = f[[c for c in POOL_FLAGS if c in f]].fillna(False).astype(bool).any(axis=1)
    return f[~bad & (f.clarity >= CLARITY)]


def stage_auto():
    for s in _slices():
        p = REAL / C.POOL_DIR / "flags" / f"{s['source_recording_id']}.parquet"
        f = _clean_pool(pd.read_parquet(p))
        off = s["source_start_idx"]
        f = f[(f.start_idx >= off) & (f.end_idx <= off + s["n"])].sort_values("start_idx")
        rows = []
        for r in f.itertuples():
            def rel(v):
                return None if v is None or (isinstance(v, float) and not math.isfinite(v)) else int(v) - off
            rows.append({"s": rel(r.start_idx), "e": rel(r.end_idx), "onset": rel(r.onset), "extremum": rel(r.extremum),
                         "end": rel(r.event_end), "depth_mv": _num(r.depth_mv), "confidence": _num(r.confidence, 3),
                         "p_r4": _num(r.p_r4, 3), "sources": str(r.sources), "label": str(r.label or ""),
                         "fall_s": _num(getattr(r, "wd_fall_s", None)), "width_s": _num(getattr(r, "wd_width_s", None))})
        _write(STORE / "auto" / f"{s['id']}.json", {"slice": s["id"], "n": len(rows), "events": rows})
        print(f"auto {s['dataset']:11s} {s['label']:5s} {len(rows)} drops")


# ── the Library ──────────────────────────────────────────────────────────────────────────────────────────────────

def _library_events():
    """The researcher-accepted drops inside the slices.

    Lion's mane and oyster: the 23 Nov per-drop table (catalogue main drops + accepted queue drops, the whole-drop
    rule). Split gill has no catalogue: its drops are Auto-detect's inside the windows the researcher called
    interesting (queue 37), i.e. pool candidates whose `label` is accepted."""
    sl = _slices()
    by_src = {}
    import sqlite3
    real = sqlite3.connect(f"file:{(REAL / 'DATA/db/annotations.sqlite').as_posix()}?mode=ro", uri=True)
    recs = {r[0]: (r[1], r[2], r[3]) for r in real.execute("SELECT id, source_file, channel, fs FROM recordings")}
    for s in sl:
        ds = next(d for d in C.DATASETS if d["key"] == s["dataset"])
        vs = ds["verdict_source"]
        for rid, (sf, ch, fs) in recs.items():
            if sf == vs["source_file"] and ch == s["channel"]:
                by_src[rid] = (s, vs["decimation"])
    t = pd.read_csv(DROP_TABLE)
    out = []
    for r in t.itertuples():
        hit = by_src.get(int(r.recording_id))
        if hit is None:
            continue
        s, dec = hit
        off = s["source_start_idx"]
        top = int(r.top_idx) // dec - off
        bot = int(r.bottom_idx) // dec - off
        rec = (int(r.recovery_idx) // dec - off) if isinstance(r.recovery_idx, float) and math.isfinite(r.recovery_idx) else None
        if top < 0 or bot >= s["n"]:
            continue
        out.append({"slice": s["id"], "dataset": s["dataset"], "top": top, "bottom": bot, "recovery": rec,
                    "depth_mv": _num(r.depth_mv), "fall_s": _num(r.fall_s), "width_s": _num(r.width_s),
                    "recovery_s": _num(r.recovery_s), "steep_s": _num(r.steep_s), "source": str(r.source),
                    "ref": str(r.event_id)})
    # Split gill: every drop (the approved whole-drop rule, its own floors) inside a window the researcher called
    # interesting in queue 37; the windows overlap, so the same drop is read once (the dedupe below).
    from Working.interrogation import whole_drop as WD

    yes = json.loads((STORE / "researcher_events.json").read_text())
    for s in sl:
        if s["dataset"] != "split_gill":
            continue
        x = np.asarray(np.load(ROOT / s["npy"], mmap_mode="r"), dtype=float)
        to_mv = 1000.0 if (s["units"] or "V") == "V" else 1.0
        for w in (w for w in yes if w["slice"] == s["id"] and w["verdict"] == "yes"):
            evs = WD.span_events(x, w["start"], w["end"], s["fs"], to_mv=to_mv, polarity="drop")
            for e in evs:
                if e.get("depth_mv") is None or not math.isfinite(e["depth_mv"]):
                    continue
                rv = e.get("recovery_idx")
                rec = int(rv) if rv is not None and math.isfinite(float(rv)) else None
                out.append({"slice": s["id"], "dataset": s["dataset"], "top": int(e["top_idx"]),
                            "bottom": int(e["bottom_idx"]), "recovery": rec, "depth_mv": _num(e["depth_mv"]),
                            "fall_s": _num(e.get("fall_s")), "width_s": _num(e.get("width_s")),
                            "recovery_s": _num(e.get("half_recovery_s")), "steep_s": _num(e.get("steep_s")),
                            "source": "drop-in-accepted-window", "ref": w["ref"]})
    # one drop per (slice, bottom): the table can list a drop under two sources
    seen, uniq = set(), []
    for e in sorted(out, key=lambda e: (e["slice"], e["bottom"])):
        k = (e["slice"], e["bottom"] // 4)
        if k in seen:
            continue
        seen.add(k)
        uniq.append(e)
    return uniq


def _shape_vector(x, e, fs, n=48):
    """The drop from half a fall before its top to its recovery (or two falls past the bottom), z-normalised."""
    fall = max(2, e["bottom"] - e["top"])
    a = max(0, e["top"] - fall // 2)
    b = e["recovery"] if e["recovery"] is not None and e["recovery"] > e["bottom"] else e["bottom"] + 2 * fall
    b = min(len(x), max(b, e["bottom"] + 2))
    seg = x[a:b]
    if len(seg) < 4:
        return None
    v = np.interp(np.linspace(0, len(seg) - 1, n), np.arange(len(seg)), seg)
    sd = v.std()
    return (v - v.mean()) / sd if sd > 0 else None


def _families(vecs, k):
    """Ward clustering of the z-normalised shapes; families ordered by size, each with its medoid."""
    from scipy.cluster.hierarchy import fcluster, linkage

    if len(vecs) < 3:
        return [list(range(len(vecs)))]
    Z = linkage(np.asarray(vecs), method="ward")
    lab = fcluster(Z, t=k, criterion="maxclust")
    fams = [list(np.flatnonzero(lab == c)) for c in sorted(set(lab))]
    fams.sort(key=len, reverse=True)
    return fams


def stage_library():
    sl = {s["id"]: s for s in _slices()}
    xs = {sid: _mv(s) for sid, s in sl.items()}
    ev = _library_events()
    for i, e in enumerate(ev):
        e["id"] = f"e{i + 1}"
    events, families, trains = [], [], []
    for ds in C.DATASETS:
        sub = [e for e in ev if e["dataset"] == ds["key"]]
        vecs, keep = [], []
        for e in sub:
            v = _shape_vector(xs[e["slice"]], e, sl[e["slice"]]["fs"])
            if v is not None:
                vecs.append(v)
                keep.append(e)
        k = max(2, min(5, len(keep) // 30))
        fams = _families(vecs, k)
        for j, members in enumerate(fams):
            fid = f"{ds['key']}-{chr(65 + j)}"
            M = np.asarray([vecs[m] for m in members])
            centre = M.mean(axis=0)
            med = members[int(np.argmin(((M - centre) ** 2).sum(axis=1)))]
            for m in members:
                keep[m]["family"] = fid
            depths = [keep[m]["depth_mv"] for m in members if keep[m]["depth_mv"] is not None]
            widths = [keep[m]["width_s"] for m in members if keep[m]["width_s"] is not None]
            families.append({"id": fid, "dataset": ds["key"], "name": f"{ds['name']} {chr(65 + j)}",
                             "n": len(members), "medoid": keep[med]["id"],
                             "shape": [round(float(v), 3) for v in centre],
                             "median_depth_mv": _num(np.median(depths)) if depths else None,
                             "median_width_s": _num(np.median(widths)) if widths else None})
        for e in keep:
            s = sl[e["slice"]]
            x = xs[e["slice"]]
            fall = max(2, e["bottom"] - e["top"])
            end = e["recovery"] if e["recovery"] is not None and e["recovery"] > e["bottom"] else e["bottom"] + 2 * fall
            pad = max(int(30 * s["fs"]), fall)
            a, b = max(0, e["top"] - pad), min(len(x), end + pad)
            e["snip"] = snippet(x, a, b, s["fs"])
            e["snip_a"] = a
            e["t_h"] = _num(e["top"] / s["fs"] / 3600.0, 4)
            events.append(e)
        # trains: drops <= 1 h apart, at least 5, per channel (the 18 Nov prototype's rule)
        for sid in sorted({e["slice"] for e in keep}):
            ch = sorted([e for e in keep if e["slice"] == sid], key=lambda e: e["top"])
            fs = sl[sid]["fs"]
            run = [ch[0]] if ch else []
            for prev, cur in zip(ch, ch[1:]):
                if (cur["top"] - prev["top"]) / fs <= 3600:
                    run.append(cur)
                else:
                    if len(run) >= 5:
                        trains.append(_train(run, sid, fs, ds["key"], len(trains)))
                    run = [cur]
            if len(run) >= 5:
                trains.append(_train(run, sid, fs, ds["key"], len(trains)))
        print(f"library {ds['key']:11s} {len(keep)} drops, {len(fams)} families, "
              f"{sum(1 for t in trains if t['dataset'] == ds['key'])} trains")
    totals = {"catalogue_spans": 2959, "species": 6, "hours": 1000}
    _write(STORE / "library.json", {"events": events, "families": families, "trains": trains, "totals": totals})


def _train(run, sid, fs, dataset, i):
    tops = np.asarray([e["top"] for e in run], dtype=float) / fs
    iv = np.diff(tops)
    cv = float(iv.std() / iv.mean()) if len(iv) > 1 and iv.mean() > 0 else None
    return {"id": f"T{i + 1}", "dataset": dataset, "slice": sid, "n": len(run), "members": [e["id"] for e in run],
            "start": int(run[0]["top"]), "end": int(run[-1]["recovery"] or run[-1]["bottom"]),
            "median_interval_s": _num(np.median(iv)) if len(iv) else None, "cv": _num(cv)}


# ── surrogates for the live seed search ──────────────────────────────────────────────────────────────────────────

LIVE_NULL_DRAWS = 3


def stage_surrogates():
    from Working.discovery.seeded_search import _surrogate

    for s in _slices():
        x = _mv(s)
        arr = np.stack([_surrogate(x, C.NULL_METHOD, 100 + i, s["fs"], 0.0) for i in range(LIVE_NULL_DRAWS)])
        p = STORE / "surrogates" / f"{s['id']}.npy"
        p.parent.mkdir(parents=True, exist_ok=True)
        np.save(p, arr.astype(np.float32))
        print("surrogates", s["dataset"], s["label"], arr.shape)


# ── the seed shelf ───────────────────────────────────────────────────────────────────────────────────────────────

SEED_K = 25            # matches kept per channel (closest first); the block's default is 10
SEED_NULL_DRAWS = 10   # surrogate draws per channel for the pre-searched shelf


def exemplar_window(e, fs):
    """A drop's seed: from a third of a fall before its top to its recovery (capped at 4 falls past the bottom)."""
    fall = max(3, e["bottom"] - e["top"])
    a = max(0, e["top"] - max(2, fall // 3))
    end = e["recovery"] if e["recovery"] is not None and e["recovery"] > e["bottom"] else e["bottom"] + 2 * fall
    b = min(end, e["bottom"] + 4 * fall)
    return a, max(b, e["bottom"] + 2)


def resample_to(ex, fs_from, fs_to):
    if abs(fs_from - fs_to) < 1e-9:
        return np.asarray(ex, dtype=float)
    n = max(8, int(round(len(ex) * fs_to / fs_from)))
    return np.interp(np.linspace(0, len(ex) - 1, n), np.arange(len(ex)), ex)


def search_all(ex, fs_ex, slices, xs, *, null_draws=SEED_NULL_DRAWS, surrogates=None, exclude=None):
    """The seed against every slice: matches (closest first), the pooled null, the recommended cut.

    The real search and its null are the core's (`seeded_search.candidates` / `null_distances`, the block's own
    match_exemplar). With `surrogates` (live), the null is read off stored phase-randomised copies instead of
    drawn, so the search stays under a second. `exclude` = (slice id, a, b): the seed's own place is not a match."""
    from Working.discovery import seeded_search as SS

    matches, null_d, draws = [], [], 0
    for s in slices:
        x = xs[s["id"]]
        e = resample_to(ex, fs_ex, s["fs"])
        if len(e) >= len(x) // 4:
            continue
        for c in SS.candidates(x, e, k=SEED_K + 1):
            i = int(c["index"])
            if exclude and exclude[0] == s["id"] and i < exclude[2] and i + len(e) > exclude[1]:
                continue
            matches.append({"slice": s["id"], "dataset": s["dataset"], "index": i, "length": len(e),
                            "distance": round(float(c["distance"]), 4)})
        if surrogates is not None:
            for y in surrogates[s["id"]]:
                null_d += [float(c["distance"]) for c in SS.candidates(np.asarray(y, dtype=float), e, k=SEED_K)]
                draws += 1
        else:
            nd = SS.null_distances(x, e, draws=null_draws, seed=0, method=C.NULL_METHOD, k=SEED_K, fs=s["fs"])
            null_d += [float(d) for d in nd["distances"]]
            draws += int(nd["draws"])
    matches.sort(key=lambda m: m["distance"])
    cut = SS.recommended_cut([m["distance"] for m in matches], {"distances": null_d, "draws": draws})
    return matches, sorted(round(d, 4) for d in null_d), draws, cut


def stage_seeds():
    lib = json.loads((STORE / "library.json").read_text())
    sl = _slices()
    by = {s["id"]: s for s in sl}
    xs = {s["id"]: _mv(s) for s in sl}
    ev = {e["id"]: e for e in lib["events"]}
    shelf = []
    for ds in C.DATASETS:
        fams = [f for f in lib["families"] if f["dataset"] == ds["key"]][:3]
        for f in fams:
            shelf.append((f"{f['name']} (typical drop)", ev[f["medoid"]], f["id"]))
    # lion's mane CH14's two alternating kinds (23 Nov): thin ~8.7 mV / 6.7 s and wide ~13 mV / 22 s
    ch14 = [e for e in lib["events"] if by[e["slice"]]["dataset"] == "lions_mane" and by[e["slice"]]["label"] == "CH14"
            and e["depth_mv"] and e["width_s"]]
    for name, depth, width in (("CH14 thin drop", 8.7, 6.7), ("CH14 wide drop", 13.0, 22.0)):
        if ch14:
            best = min(ch14, key=lambda e: (math.log(e["depth_mv"] / depth)) ** 2 + (math.log(e["width_s"] / width)) ** 2)
            shelf.append((name, best, best.get("family")))
    out = []
    for i, (name, e, fam) in enumerate(shelf):
        s = by[e["slice"]]
        a, b = exemplar_window(e, s["fs"])
        ex = xs[s["id"]][a:b]
        matches, null_d, draws, cut = search_all(ex, s["fs"], sl, xs, exclude=(s["id"], a, b))
        kept = [m for m in matches if cut is not None and m["distance"] <= cut]
        for m in matches[:60]:
            x = xs[m["slice"]]
            pad = m["length"] // 2
            m["snip"] = snippet(x, m["index"] - pad, m["index"] + m["length"] + pad, by[m["slice"]]["fs"], n_max=120)
            m["pad"] = pad
        out.append({"id": f"S{i + 1}", "name": name, "dataset": s["dataset"], "slice": s["id"], "event": e["id"],
                    "family": fam, "a": a, "b": b, "fs": s["fs"], "exemplar": snippet(xs[s["id"]], a, b, s["fs"], n_max=120),
                    "matches": matches[:60], "n_matches": len(matches), "null": null_d, "null_draws": draws, "cut": cut,
                    "n_kept": len(kept), "kept_by_dataset": {d["key"]: sum(1 for m in kept if m["dataset"] == d["key"])
                                                              for d in C.DATASETS}})
        print(f"seed {name:28s} m={len(ex):4d} matches={len(matches)} cut={cut} kept={len(kept)} "
              f"{out[-1]['kept_by_dataset']}")
    _write(STORE / "seeds.json", {"seeds": out, "k": SEED_K, "null_method": C.NULL_METHOD})


# ── Spike statistics ─────────────────────────────────────────────────────────────────────────────────────────────

ICICLES = 40


def _lv(iv):
    iv = np.asarray(iv, dtype=float)
    if len(iv) < 3:
        return None
    a, b = iv[:-1], iv[1:]
    return float(3.0 / (len(iv) - 1) * np.sum(((a - b) / (a + b)) ** 2))


def _stats_from(events_by_slice, slices, xs, *, key):
    """events_by_slice: {slice id: [{onset, bottom, end, depth_mv, width_s, slope}]} -> the page's numbers."""
    out = {}
    for ds in C.DATASETS:
        sub = [s for s in slices if s["dataset"] == ds["key"]]
        rate = np.zeros(24, dtype=int)
        ivs, lvs, cvs, scatter, ice, slopes = [], [], [], [], [], []
        n = 0
        for s in sub:
            evs = sorted(events_by_slice.get(s["id"], []), key=lambda e: e["onset"])
            fs = s["fs"]
            n += len(evs)
            for e in evs:
                h = int(min(23, max(0, e["onset"] / fs // 3600)))
                rate[h] += 1
                if e.get("depth_mv") is not None and e.get("width_s") is not None:
                    scatter.append([round(float(e["width_s"]), 3), round(abs(float(e["depth_mv"])), 4)])
                if e.get("slope") is not None:
                    slopes.append(abs(float(e["slope"])))
            t = np.asarray([e["onset"] for e in evs], dtype=float) / fs
            iv = np.diff(t)
            iv = iv[iv > 0]
            ivs += [float(v) for v in iv]
            lv = _lv(iv)
            if lv is not None:
                lvs.append((lv, len(iv)))
            if len(iv) > 2 and iv.mean() > 0:
                cvs.append((float(iv.std() / iv.mean()), len(iv)))
            # icicles: each drop from its onset, in mV relative to the onset, at its own scale
            x = xs[s["id"]]
            for e in evs:
                a = int(e["onset"])
                end = int(e.get("end") or e["bottom"] + 2 * max(2, e["bottom"] - a))
                end = min(len(x), max(end, int(e["bottom"]) + 2))
                pre = max(1, (end - a) // 6)
                seg = x[max(0, a - pre):end] - x[a]
                ice.append({"dt": 1.0 / fs, "t0": -pre / fs, "v": seg, "depth": abs(float(e.get("depth_mv") or 0.0))})
        ivs_a = np.asarray(ivs)
        # regularity within an electrode: pooling gaps across electrodes with different rates inflates CV
        cv = float(sum(c * w for c, w in cvs) / sum(w for _, w in cvs)) if cvs else None
        lv = float(sum(l * w for l, w in lvs) / sum(w for _, w in lvs)) if lvs else None
        hist = None
        if len(ivs_a) > 2:
            edges = np.logspace(np.log10(max(1.0, ivs_a.min())), np.log10(ivs_a.max() + 1), 20)
            c, _ = np.histogram(ivs_a, bins=edges)
            hist = {"edges_s": [round(float(v), 2) for v in edges], "counts": [int(v) for v in c]}
        # icicles: the ICICLES deepest-spread sample, each down to <= 120 points
        if ice:
            ice.sort(key=lambda r: r["depth"])
            pick = np.unique(np.linspace(0, len(ice) - 1, min(ICICLES, len(ice))).round().astype(int))
            ice = [ice[i] for i in pick]
            for r in ice:
                v = r["v"]
                step = max(1, int(math.ceil(len(v) / 120)))
                r["v"] = [round(float(z), 4) for z in v[::step]]
                r["dt"] = r["dt"] * step
        if len(scatter) > 400:
            idx = np.linspace(0, len(scatter) - 1, 400).round().astype(int)
            scatter = [scatter[i] for i in idx]
        sl_a = np.asarray(slopes)
        out[ds["key"]] = {
            "n": int(n), "rate_per_h": [int(v) for v in rate], "intervals": hist,
            "median_interval_s": _num(np.median(ivs_a)) if len(ivs_a) else None, "cv": _num(cv), "lv": _num(lv),
            "scatter": scatter, "icicles": ice,
            "slopes_mv_s": [round(float(v), 5) for v in np.sort(sl_a)] if len(sl_a) <= 600 else
                           [round(float(v), 5) for v in np.quantile(sl_a, np.linspace(0, 1, 600))],
        }
    return out


def stage_stats():
    sl = _slices()
    by = {s["id"]: s for s in sl}
    xs = {s["id"]: _mv(s) for s in sl}
    # the library
    lib = json.loads((STORE / "library.json").read_text())
    evs = {}
    for e in lib["events"]:
        fs = by[e["slice"]]["fs"]
        fall_s = (e["bottom"] - e["top"]) / fs
        slope = (abs(e["depth_mv"]) / e["steep_s"]) if e.get("steep_s") else (abs(e["depth_mv"] or 0) / fall_s if fall_s else None)
        evs.setdefault(e["slice"], []).append({"onset": e["top"], "bottom": e["bottom"], "end": e["recovery"],
                                               "depth_mv": e["depth_mv"], "width_s": e["width_s"], "slope": slope})
    _write(STORE / "stats" / "library.json", _stats_from(evs, sl, xs, key="library"))
    # Auto-detect
    evs = {}
    for s in sl:
        a = json.loads((STORE / "auto" / f"{s['id']}.json").read_text())
        for e in a["events"]:
            if e["onset"] is None or e["extremum"] is None:
                continue
            fall_s = max(1, e["extremum"] - e["onset"]) / s["fs"]
            evs.setdefault(s["id"], []).append({"onset": e["onset"], "bottom": e["extremum"], "end": e["end"],
                                                "depth_mv": e["depth_mv"], "width_s": e["width_s"] or fall_s,
                                                "slope": (abs(e["depth_mv"] or 0) / fall_s)})
    _write(STORE / "stats" / "auto.json", _stats_from(evs, sl, xs, key="auto"))
    # every builder setting
    n = 0
    for c in C.combos():
        evs = {}
        for s in sl:
            p = STORE / "chains" / c["id"] / f"{s['id']}.json"
            if not p.exists():
                continue
            r = json.loads(p.read_text())
            for e in r["events"]:
                on = e.get("onset_idx")
                ex = e.get("extremum_idx")
                if on is None or ex is None:
                    on, ex = e["s"], e["e"]
                evs.setdefault(s["id"], []).append({"onset": on, "bottom": ex, "end": e.get("recovery_idx") or e["e"],
                                                    "depth_mv": e.get("event_amplitude_mv"), "width_s": e.get("event_width_s"),
                                                    "slope": e.get("max_slope_mv_s")})
        _write(STORE / "stats" / "combos" / f"{c['id']}.json", _stats_from(evs, sl, xs, key=c["id"]))
        n += 1
    print(f"stats: library, auto, {n} settings")


def stage_manifest():
    """What the station and the client read first: the datasets, the slices, the builder menu, every setting."""
    meta = json.loads((STORE / "slices.json").read_text())
    menu = {
        "look_for": [{"key": "drops", "label": "Drops"}, {"key": "rises", "label": "Rises (flip the signal)"}],
        "clean_windows_s": C.CLEAN_WINDOWS_S,
        "detectors": [{"key": k, **v} for k, v in C.DETECTORS.items()],
    }
    m = {"datasets": C.DATASETS, "slices": meta["slices"], "menu": menu, "combos": C.combos(),
         "default_combo": C.default_combo_id(), "references": C.REFERENCE_RUNS,
         "null": {"method": C.NULL_METHOD, "draws": C.NULL_DRAWS}, "built": __import__("time").strftime("%Y-%m-%d %H:%M")}
    _write(STORE / "manifest.json", m)
    print("manifest:", len(m["combos"]), "settings,", len(m["slices"]), "slices")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="manifest,auto,library,surrogates,seeds,stats")
    a = ap.parse_args()
    os.chdir(ROOT)
    for st in a.stage.split(","):
        {"manifest": stage_manifest, "auto": stage_auto, "library": stage_library, "surrogates": stage_surrogates,
         "seeds": stage_seeds, "stats": stage_stats}[st.strip()]()


if __name__ == "__main__":
    main()
