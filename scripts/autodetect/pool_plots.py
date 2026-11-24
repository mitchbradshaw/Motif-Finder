"""
pool_plots.py
=============
The 24 Nov auto-detect drop pool through the NeurIPS session's drop plots (the researcher, 24 Nov: "feed them into
the plotting structures of the NeurIPS agent to see what larger pools of potential candidates show").

`scripts/library_analysis/drop_plots_20261123.py` is imported and used as it is - its figures, its measures (the
whole-drop rule's top, bottom, half recovery, fall, width and steep part), its style - with the pool's drops in place
of the reviewed ones. Every drop is treated alike, as those plots do (memory: experimental-plots-all-drops-alike).
What this file adds, and nothing else:

* the pool as that script's event table (`events.csv`), measured by the same whole-drop rule (`build_pool.py`);
* names and colours for the datasets the thesis never used; where nobody recorded a species, the dataset is its own
  row, marked "(species ?)", so no two unknown organisms are pooled;
* a random sample for the two figures that compare every drop with every other (the shape map's per-cell medoids,
  whose distance matrix grows with the square of a cell's drops, and the t-SNE shape space): `SAMPLE_MAP` and
  `SAMPLE_TSNE`, said in their captions;
* wording: where a figure or caption says "reviewed", it says what these drops are - candidates nobody has judged;
* the width-amplitude figure, which has room for six species, drawn once per six (`species_plane_in_sixes`);
* `POOL_MIN_P_ACCEPT=0.8`: only the drops the verdict model (`pool_summary.py`) puts at least that likely to be
  accepted, into `..._pool_plots_p80/` (and `events_p80.csv`, `event_shapes_p80.npz`), to see which patterns survive
  the noise; `POOL_TIERS=core,extended` draws both tiers (default: the core).

Writes docs/library_analysis/20261124_pool_plots/ (index.html, the figures, captions.json); the event table and every
drop's waveform go beside the pool (DATA/derived/autodetect/pool_20261124/events.csv, event_shapes.npz). Read-only
on the database and the channels.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/autodetect/pool_plots.py [sheets species map grids extra]
"""
from __future__ import annotations

import os
import sqlite3
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts", "library_analysis"))
import common as K  # noqa: E402

os.chdir(ROOT)
WHOLE_DROP_PIN = K.pin_whole_drop(os.environ.get("AUTODETECT_WHOLE_DROP_REV", "HEAD"))
import drop_plots_20261123 as dp  # noqa: E402
fs = dp.fs

POOL = os.path.join(ROOT, "DATA", "derived", "autodetect", "pool_20261124", "pool.parquet")
#: Draw only the drops the verdict model (`pool_summary.py`, `p_accept.parquet`) puts at least this likely to be
#: accepted - a cleaner subset, to see which patterns survive the noise. Unset: every drop of the tiers drawn.
MIN_P_ACCEPT = float(os.environ["POOL_MIN_P_ACCEPT"]) if os.environ.get("POOL_MIN_P_ACCEPT") else None
VARIANT = "" if MIN_P_ACCEPT is None else f"_p{round(MIN_P_ACCEPT * 100):02d}"
OUT = os.path.join(ROOT, "docs", "library_analysis", "20261124_pool_plots" + VARIANT)
SAMPLE_MAP = 30_000
SAMPLE_TSNE = 20_000
SEED = 20261124

#: The datasets the thesis figures never named: (species label, colour). An unrecorded species is the dataset's own
#: row, so different unknown organisms are never pooled into one.
NEW = {
    "S_commune": ("split gill", "#1f9e89"),
    "Cordyceps": ("Cordyceps", "#c98a00"),
    "Enoki": ("enoki", "#7f8a1f"),
    "Dwij_B": ("Dwij logger (species ?)", "#7d7a73"),
    "Dwij_C": ("Dwij logger (species ?)", "#7d7a73"),
    "Dwij_D": ("Dwij logger (species ?)", "#7d7a73"),
    "F2B": ("F2B (species ?)", "#5f4b8b"),
    "L_R_Aug_26_PD": ("L_R_Aug_26_PD (species ?)", "#b5651d"),
    "M1": ("M1 (species ?)", "#3d6b45"),
}
REWRITE = [
    ("(the accepted catalogue plus today's accepted queue drops)",
     "(the 24 Nov auto-detect pool: drops nobody has judged or been shown)"),
    ("This is where the review has looked as much as where the mycelium dropped: long empty stretches are mostly "
     "unreviewed, not quiet.",
     "Gaps are stretches where the pool's rules kept no drop: stretches already reviewed or queued, noisy ones, and "
     "quiet ones."),
    ("Every reviewed drop", "Every pool drop"), ("every reviewed drop", "every pool drop"),
    ("reviewed drops", "pool drops"), ("reviewed drop", "pool drop"),
]


def _rewrite(text):
    for a, b in REWRITE:
        text = text.replace(a, b)
    return text


_save = dp.save


#: A suffix for the next figure's file name (a figure drawn in parts: `species_plane_in_sixes`).
SUFFIX = [""]


def save(fig, name, section, caption, dpi=170):
    """`drop_plots.save`, after the figure's own words are made true of the pool."""
    if SUFFIX[0]:
        stem, ext = os.path.splitext(name)
        name = stem + SUFFIX[0] + ext
    for t in fig.texts:
        t.set_text(_rewrite(t.get_text()))
    for ax in fig.axes:
        for t in (ax.title, getattr(ax, "_left_title", None), getattr(ax, "_right_title", None)):
            if t is not None:
                t.set_text(_rewrite(t.get_text()))
    _save(fig, name, section, _rewrite(caption) + POOL_NOTE.get(name, ""), dpi=dpi)


POOL_NOTE = {}


def setup():
    dp.OUT = OUT
    dp.CAPTIONS_FILE = os.path.join(OUT, "captions.json")
    # the bulky by-products (every drop's waveform, the event table) stay with the pool, out of docs/
    dp.SHAPES_FILE = os.path.join(os.path.dirname(POOL), f"event_shapes{VARIANT}.npz")
    dp.save = save
    for d, (sp, colour) in NEW.items():
        fs.RECORDINGS[d] = (sp, colour)
        fs.ALIASES[d] = d
        fs.SPECIES_COLOUR.setdefault(sp, colour)
    dp.SPECIES_ORDER = list(dp.SPECIES_ORDER) + [sp for sp in dict.fromkeys(v[0] for v in NEW.values())
                                                 if sp not in dp.SPECIES_ORDER]
    dp.DATASET_ORDER = list(dp.DATASET_ORDER) + [d for d in NEW if d not in dp.DATASET_ORDER]
    if S_SHEETS not in dp.SECTIONS:
        dp.SECTIONS = [S_SHEETS] + list(dp.SECTIONS)
    os.makedirs(OUT, exist_ok=True)


def pool_events():
    """The pool as `drop_plots`' event table: one row per drop the whole-drop rule measured, its indices on the
    recording it was found on (a 10 Hz recording searched at 2 Hz: the centre of the five-sample block)."""
    p = pd.read_parquet(POOL)
    # the core tier: the queue's settings (the extended tier, 0.5-0.6 confidence or 10-15 clarity, stays out of the
    # figures; POOL_TIERS=core,extended draws both)
    p = p[p["tier"].isin(os.environ.get("POOL_TIERS", "core").split(",")) & p["wd_ok"].astype(bool)]
    if MIN_P_ACCEPT is not None:
        pa = pd.read_parquet(os.path.join(os.path.dirname(POOL), "p_accept.parquet"),
                             columns=["recording_id", "candidate_id", "p_accept"])
        p = p.merge(pa, on=["recording_id", "candidate_id"], how="left", validate="one_to_one")
        p = p[p["p_accept"] >= MIN_P_ACCEPT]
    p = p.reset_index(drop=True)
    d = p["decimation"].astype(int).to_numpy()

    def native(col):
        v = p[col].to_numpy(float)
        return np.where(np.isfinite(v), v * d + (d // 2) * (d > 1), np.nan)

    ev = pd.DataFrame({
        "event_id": [f"pool-{int(r)}-{int(c)}" for r, c in zip(p["recording_id"], p["candidate_id"])],
        "source": "pool", "dataset": p["dataset"].astype(str), "recording_id": p["recording_id"].astype(int),
        "fs": p["native_fs"].astype(float), "top_idx": native("wd_top"), "bottom_idx": native("wd_bottom"),
        "recovery_idx": native("wd_recovery"), "depth_mv": p["wd_depth_mv"].astype(float),
        "fall_s": p["wd_fall_s"].astype(float), "width_s": p["wd_width_s"].astype(float),
        "recovery_s": p["wd_recovery_s"].astype(float), "steep_s": p["wd_steep_s"].astype(float),
        "long_tail": p["wd_long_tail"].astype(bool), "events_in_span": p["wd_n_events"],
        "confidence": p["confidence"].astype(float), "priority": p["priority"].astype(float),
        "m4_like": p["m4_like"].astype(bool), "clarity": p["clarity"].astype(float),
        "channel": p["channel"].astype(int), "pool_rank": p["rank"].astype(int)})
    ev = ev[np.isfinite(ev["top_idx"]) & np.isfinite(ev["bottom_idx"]) & (ev["depth_mv"] > 0)].copy()
    ev["top_idx"] = ev["top_idx"].astype(np.int64)
    ev["bottom_idx"] = ev["bottom_idx"].astype(np.int64)
    ev["species"] = ev["dataset"].map(dp.species_of)
    ev["t_h"] = ev["top_idx"] / ev["fs"] / 3600.0
    ev["fall_rate_mv_s"] = ev["depth_mv"] / ev["fall_s"].clip(lower=1.0 / ev["fs"])
    return ev.sort_values(["dataset", "recording_id", "top_idx"]).reset_index(drop=True)


FAILED = []


def attempt(fn, *args, **kw):
    """One figure: a failure is printed with its traceback and listed at the end (and in failures.txt) - never
    silent - and the other figures still get drawn."""
    import traceback
    try:
        return fn(*args, **kw)
    except Exception as exc:  # noqa: BLE001 - reported loud below
        FAILED.append(f"{getattr(fn, '__name__', fn)}: {type(exc).__name__}: {exc}\n{traceback.format_exc()}")
        print(f"FIGURE FAILED {getattr(fn, '__name__', fn)}: {type(exc).__name__}: {exc}", flush=True)
        import matplotlib.pyplot as plt
        plt.close("all")
        return None


S_SHEETS = "What the pool's drops look like: random samples per dataset"
SHEET_N = 30
PAD_S = 120.0


def contact_sheets(ev, recs):
    """One sheet per dataset: `SHEET_N` pool drops drawn at random (spread over its channels), each with the window
    Review would show (its box +-120 s), the box shaded, the whole-drop top and bottom marked. A look at what a
    typical candidate is - not the best ones."""
    import matplotlib.pyplot as plt
    rng = np.random.default_rng(SEED)
    for d, g in ev.groupby("dataset"):
        pick = g.groupby("recording_id", group_keys=False).apply(
            lambda h: h.sample(n=min(len(h), max(1, SHEET_N // g["recording_id"].nunique() + 1)),
                               random_state=int(rng.integers(1 << 31))), include_groups=True)
        pick = pick.sample(n=min(SHEET_N, len(pick)), random_state=SEED).sort_values(["recording_id", "top_idx"])
        n = len(pick)
        cols = 5
        rows = int(np.ceil(n / cols))
        fig, axes = plt.subplots(rows, cols, figsize=(3.3 * cols, 2.0 * rows), squeeze=False)
        for ax, r in zip(axes.ravel(), pick.itertuples()):
            f = float(r.fs)
            a = int(r.top_idx - (PAD_S + 30) * f)
            b = int(r.bottom_idx + (PAD_S + 30) * f)
            seg = dp.window(recs, int(r.recording_id), max(0, a), b)
            if seg is None:
                ax.set_axis_off()
                continue
            t = (np.arange(len(seg)) + max(0, a) - r.top_idx) / f
            ax.plot(t, seg, lw=0.7, color="#1b1b1a")
            ax.axvspan(0, (r.bottom_idx - r.top_idx) / f, color="#2a78d6", alpha=0.15, lw=0)
            ax.set_title(f"CH{int(r.channel)} {r.t_h:.1f} h · {r.depth_mv:.2g} mV · c {r.confidence:.2f}",
                         fontsize=7.5)
            ax.tick_params(labelsize=6)
        for ax in axes.ravel()[n:]:
            ax.set_axis_off()
        fig.suptitle(f"{d}: {n} pool drops at random of {len(g):,} (time from the drop's top, s; mV)", x=0.01,
                     ha="left", fontsize=10)
        fig.tight_layout()
        save(fig, f"sheets/{d}.png", S_SHEETS,
             f"{n} of {d}'s {len(g):,} pool drops, drawn at random across its channels: each with 150 s either side "
             f"of the fall, the fall (whole-drop top to bottom) shaded. Title: channel, hours in, depth, confidence. "
             f"A look at a typical candidate, not the best ones.")


def species_plane_in_sixes(ev):
    """`drop_plots.fig_species_plane` has room for six species (a 2 x 3 grid of small panels beside the big one);
    the pool has more. Drawn once per six species, in the script's order, as `species_width_amplitude.png`,
    `species_width_amplitude_2.png`, ...; each part's grey background is its own species' drops."""
    g = ev[(ev["width_s"] > 0) & (ev["depth_mv"] > 0)]
    sps = dp.species_present(g, least=10)
    parts = [sps[i:i + 6] for i in range(0, len(sps), 6)]
    try:
        for k, part in enumerate(parts):
            SUFFIX[0] = "" if k == 0 else f"_{k + 1}"
            POOL_NOTE[f"species_width_amplitude{SUFFIX[0]}.png"] = (
                f" Part {k + 1} of {len(parts)}: {', '.join(part)} (the figure has room for six species; the grey "
                f"is this part's drops)." if len(parts) > 1 else "")
            attempt(dp.fig_species_plane, ev[ev["species"].isin(part)])
    finally:
        SUFFIX[0] = ""


def sample(ev, n):
    return ev if len(ev) <= n else ev.sample(n=n, random_state=SEED).sort_values(
        ["dataset", "recording_id", "top_idx"]).reset_index(drop=True)


def main(stages):
    t0 = time.time()
    setup()
    fs.apply()
    conn = sqlite3.connect(f"file:{dp.DB}?mode=ro", uri=True)
    recs = dp.recordings(conn)
    ev = pool_events()
    ev.to_csv(os.path.join(os.path.dirname(POOL), f"events{VARIANT}.csv"), index=False)
    print(f"pool events: {len(ev):,} drops in {ev['dataset'].nunique()} datasets ({time.time() - t0:.0f} s)",
          flush=True)
    print(ev.groupby(["species", "dataset"]).size().to_string(), flush=True)
    every = not stages or "all" in stages
    if every or "sheets" in stages:
        attempt(contact_sheets, ev, recs)
        print(f"sample sheets written ({time.time() - t0:.0f} s)", flush=True)
    if every or "species" in stages:
        attempt(dp.fig_anatomy, ev, recs)
        attempt(dp.fig_species_boxes, ev)
        attempt(dp.fig_species_rainclouds, ev)
        species_plane_in_sixes(ev)
        attempt(dp.fig_species_asymmetry, ev)
        attempt(dp.fig_species_shapes, ev, recs)
        attempt(dp.species_table, ev)
        print(f"species figures written ({time.time() - t0:.0f} s)", flush=True)
    if every or "map" in stages:
        g0 = sample(ev, SAMPLE_MAP)
        for xcol, xlabel, stem, post in (("width_s", "Width: top to half recovery (s, log)", "width", dp.POST_W),
                                         ("fall_s", "Fall time: top to bottom (s, log)", "fall", 5.0)):
            note = (f" Drawn from a random sample of {len(g0):,} of the pool's {len(ev):,} drops: each cell's medoid "
                    f"compares every drop in it with every other.") if len(g0) < len(ev) else ""
            for nm in (f"map_{stem}_medoids.png", f"map_{stem}_medoids_zoom.png", f"map_{stem}_heatmaps.png",
                       f"map_{stem}_cells.png"):
                POOL_NOTE[nm] = note
            got = attempt(dp.adaptive_cells, g0, recs, xcol, post)
            if got is None:
                continue
            g, px, py, root, leaves = got
            attempt(dp.fig_map_medoids, g, px, py, root, leaves, xlabel, stem, post)
            attempt(dp.fig_map_medoids, g, px, py, root, leaves, xlabel, stem, post, zoom=True)
            attempt(dp.fig_map_heatmaps, g, px, py, root, leaves, xlabel, stem, post)
            attempt(dp.fig_map_cells, g, px, py, root, leaves, xlabel, stem)
            print(f"map {stem}: {len(g):,} drops, {len(leaves)} cells ({time.time() - t0:.0f} s)", flush=True)
    if every or "grids" in stages:
        got = attempt(dp.with_shape_measures, ev, recs)
        if got is not None:
            evs, W = got
            attempt(dp.fig_fall_grid10, evs, recs, "shaded")
            attempt(dp.fig_fall_grid10, evs, recs, "opacity")
            attempt(dp.shape_grids, evs, W)
            attempt(dp.fig_fingerprints, evs)
        print(f"grids and fingerprints written ({time.time() - t0:.0f} s)", flush=True)
    if every or "extra" in stages:
        attempt(dp.fig_raster, ev)
        attempt(dp.fig_ccdf, ev)
        gt = sample(ev, SAMPLE_TSNE)
        if len(gt) < len(ev):
            POOL_NOTE["extra/shape_space.png"] = (f" Drawn from a random sample of {len(gt):,} of the pool's {len(ev):,} "
                                                  f"drops (t-SNE grows with the square of the drops it places).")
        attempt(dp.fig_shape_space, gt, recs)
        print(f"extra figures written ({time.time() - t0:.0f} s)", flush=True)
    conn.close()
    with open(os.path.join(OUT, "failures.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n\n".join(FAILED) if FAILED else "none\n")
    if FAILED:
        print(f"\n{len(FAILED)} FIGURE(S) FAILED (failures.txt):\n" + "\n".join(f.splitlines()[0] for f in FAILED),
              flush=True)
    dp.write_index()
    path = os.path.join(OUT, "index.html")
    with open(path, encoding="utf-8") as fh:
        html = fh.read()
    html = html.replace("<title>Drop plots 23 Nov</title>", "<title>Drop pool plots 24 Nov</title>").replace(
        "<h1>Drop events and sequences: experimental plots (23 Nov 2026)</h1>",
        f"<h1>The auto-detect drop pool: {len(ev):,} unjudged drops through the 23 Nov drop plots (24 Nov 2026)"
        + ("" if MIN_P_ACCEPT is None else f", only the drops the verdict model puts at {MIN_P_ACCEPT:.0%} or more")
        + "</h1>")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"index written; {time.time() - t0:.0f} s in all", flush=True)


if __name__ == "__main__":
    main(set(sys.argv[1:]))
