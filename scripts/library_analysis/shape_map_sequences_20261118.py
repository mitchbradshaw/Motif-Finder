"""Shape map of the accepted individual events, and shape trends along sequences (prototype, 18 Nov 2026).

In plain words: every accepted single event in the 9 Nov inventory already has a depth (onset of the fall to the
trough) and a width (onset to the point where it has climbed half way back), measured by the tool's own event-shape
block. Part 1 plots width against depth for every event, cuts that plane into a 5 x 5 grid, and for each cell draws
the medoid waveform (the real event most like all the others in the cell), aligned at the onset and coloured by how
much the cell's events disagree at each moment: blue where they agree, red where they do not.

Part 2 chains accepted events that sit next to each other on one channel (next onset within GAP_MAX_S) into
sequences, measures how depth, fall time, width, fall rate and the interval to the previous event change along each
sequence (Kendall's tau against time, the Interrogation block's `kendall_trend`), and draws the two measures whose
trends are the most consistent, raw and normalised.

Read-only: the database is opened `mode=ro` and the channel files are memory-mapped. Writes only OUT.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/library_analysis/shape_map_sequences_20261118.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "thesis"))

import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402  (figstyle selected the Agg backend)
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, Normalize  # noqa: E402
from scipy.spatial.distance import cdist  # noqa: E402

from Working.interrogation.event_shape import RECOVERY_MAX_MULT  # noqa: E402
from Working.interrogation.intervals import kendall_trend  # noqa: E402

INV = os.path.join(ROOT, "docs", "thesis", "data", "ch9_inventory_20261109", "measures.csv")
SPANS = os.path.join(ROOT, "docs", "thesis", "data", "accepted_catalogue_20261109", "accepted_spans.csv")
DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite").replace("\\", "/")
OUT = os.path.join(ROOT, "docs", "library_analysis", "20261118")

ORDER = ["M2_aug", "M2_concat", "M4", "LM", "CO", "MJu26a", "SH", "SO"]
MAX_SPAN_S = 3600.0        # the inventory's region cut (spans longer than this were not measured)
NBINS = 5
PCT = (1.0, 99.0)          # the grid spans these percentiles; events outside fall into the open edge cells
PRE, POST = 0.5, 2.5       # waveform window around the onset, in units of the column's centre width
NPTS = 121
MIN_CELL = 3               # fewer events than this in a cell: no medoid drawn
GAP_MAX_S = 3600.0         # two accepted events are adjacent when the next onset is within this
MIN_EVENTS = 5             # a sequence needs this many events for its trends to be read
SENS_GAPS = (900.0, 1800.0, 3600.0, 7200.0)
TOP_LINES = 8              # the longest sequences get a colour each; the rest are drawn grey
SUSPECT_FRAC = 0.3         # measured depth below this fraction of the span's own range: anatomy probably missed
ALT_MIN = 20               # sequences with this many measured widths get the alternation test
ALT_DRAWS = 5000
SEED = 20261118

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
BLUE, RED, MID = "#2a78d6", "#e34948", "#9a9893"
VAR_CMAP = LinearSegmentedColormap.from_list("agree_disagree", [BLUE, MID, RED])
PICKED = ["depth_mv", "isi_s"]   # the headline pair (see main)

VARS = {
    "depth_mv": ("Drop depth (mV)", "depth"),
    "fall_s": ("Fall time, onset to trough (s)", "fall time"),
    "duration_s": ("Width, onset to half recovery (s)", "width"),
    "fall_rate_mv_s": ("Fall rate, depth / fall time (mV/s)", "fall rate"),
    "isi_s": ("Interval since the previous event (s)", "interval"),
}


def to_mv(units):
    return {"mV": 1.0, "uV": 0.001}.get(units or "V", 1000.0)


# ── the events ──────────────────────────────────────────────────────────────


def load_events(m):
    s = pd.read_csv(SPANS)
    m = m.merge(s[["event_id", "channel", "train_id", "span_s"]], on="event_id", how="left")
    # where the inventory's recovery search stopped: the trough + 10 fall widths + 1 sample, or the next measured
    # window's start, whichever came first (event_shape.measure_events). A drop that had not climbed half way back
    # by then has a width of AT LEAST (limit - onset) / fs, not an unknown one.
    measured = s[s["span_s"] <= MAX_SPAN_S]
    nxt = {}
    for _, g in measured.groupby("recording_id"):
        starts = np.sort(g["start_idx"].to_numpy())
        for eid, a, e in zip(g["event_id"], g["start_idx"], g["end_idx"]):
            j = np.searchsorted(starts, a, side="right")
            nxt[eid] = max(e, starts[j]) if j < len(starts) else np.inf
    m["search_end"] = m["event_id"].map(nxt)
    width = (m["extremum_idx"] - m["onset_idx"]).clip(lower=1)
    limit = np.minimum(m["search_end"], m["extremum_idx"] + RECOVERY_MAX_MULT * width + 1)
    m["width_lower_bound_s"] = (limit - m["onset_idx"]) / m["fs"]
    m["fall_rate_mv_s"] = m["depth_mv"] / m["fall_s"].where(m["fall_s"] > 0)
    m["t_s"] = m["onset_idx"] / m["fs"]
    return m


def recordings(conn):
    return {int(r[0]): {"npy": r[1], "fs": float(r[2]), "units": r[3]}
            for r in conn.execute("SELECT id, npy_path, fs, units FROM recordings")}


def anatomy_check(m, recs):
    """The measured fall as a fraction of the span's own range (after a 1-s moving average).

    The block's anatomy starts from the steepest sample of the span. In a span of several minutes at 10 Hz that
    can be a noise wiggle rather than the fall the reviewer accepted: by eye, a 0.1 mV, 0.5 s 'event' measured
    inside a span whose drop is 10 mV. Below SUSPECT_FRAC the event is flagged and left out of both parts.
    """
    frac = np.full(len(m), np.nan)
    cache = {}
    for i, r in enumerate(m.itertuples(index=False)):
        if r.status not in ("single", "multiple") or not np.isfinite(r.depth_mv):
            continue
        rid = int(r.recording_id)
        rec = recs[rid]
        if rid not in cache:
            cache[rid] = np.load(os.path.join(ROOT, rec["npy"]), mmap_mode="r")
        seg = np.asarray(cache[rid][int(r.start_idx):int(r.end_idx)], dtype=float) * to_mv(rec["units"])
        k = max(1, int(round(rec["fs"])))
        sm = np.convolve(seg, np.ones(k) / k, mode="valid") if len(seg) > k else seg
        rngv = float(np.ptp(sm)) if len(sm) and np.all(np.isfinite(sm)) else float("nan")
        frac[i] = r.depth_mv / rngv if rngv > 0 else np.nan
    m = m.copy()
    m["depth_frac_of_span"] = frac
    m["anatomy_suspect"] = frac < SUSPECT_FRAC
    return m


# ── part 1: the shape map ──────────────────────────────────────────────────


def assign_cells(ev):
    lw, ld = np.log10(ev["duration_s"].to_numpy()), np.log10(ev["depth_mv"].to_numpy())
    xe = np.linspace(*np.percentile(lw, PCT), NBINS + 1)
    ye = np.linspace(*np.percentile(ld, PCT), NBINS + 1)
    ev = ev.copy()
    ev["col"] = np.clip(np.searchsorted(xe, lw, side="right") - 1, 0, NBINS - 1)
    ev["row"] = np.clip(np.searchsorted(ye, ld, side="right") - 1, 0, NBINS - 1)
    return ev, xe, ye


def waveforms(ev, recs, xe):
    """Each event's oriented trace in mV, onset at t = 0 and at 0 mV, on its column's common time grid."""
    centres = 10 ** ((xe[:-1] + xe[1:]) / 2)
    W = np.full((len(ev), NPTS), np.nan)
    cache = {}
    for k, r in enumerate(ev.itertuples(index=False)):
        rid = int(r.recording_id)
        rec = recs[rid]
        if rid not in cache:
            cache[rid] = np.load(os.path.join(ROOT, rec["npy"]), mmap_mode="r")
        x, f = cache[rid], rec["fs"]
        wc = centres[int(r.col)]
        on = int(r.onset_idx)
        a = int(np.floor(on - PRE * wc * f)) - 1
        b = int(np.ceil(on + POST * wc * f)) + 2
        if a < 0 or b > len(x):
            continue
        orient = 1.0 if r.polarity < 0 else -1.0
        seg = np.asarray(x[a:b], dtype=float) * orient * to_mv(rec["units"])
        if not np.all(np.isfinite(seg)):
            continue
        ts = (np.arange(a, b) - on) / f
        W[k] = np.interp(np.linspace(-PRE * wc, POST * wc, NPTS), ts, seg - seg[on - a])
    return W, centres


def cell_stats(ev, W, centres):
    cells = []
    for (row, col), g in ev.groupby(["row", "col"]):
        idx = g.index.to_numpy()
        w = W[idx]
        ok = np.all(np.isfinite(w), axis=1)
        w, ids = w[ok], g["event_id"].to_numpy()[ok]
        c = {"row": int(row), "col": int(col), "n": int(len(g)), "n_waveforms": int(len(w)),
             "median_depth_mv": float(g["depth_mv"].median()), "median_width_s": float(g["duration_s"].median()),
             "median_fall_s": float(g["fall_s"].median()), "centre_width_s": float(centres[col]),
             "datasets": "; ".join(f"{d} {n}" for d, n in g["dataset"].value_counts().items())}
        if len(w) >= MIN_CELL:
            med = int(np.argmin(cdist(w, w).sum(axis=1)))
            # spread of SHAPE: each event divided by its own depth first, so the colour says where the events
            # differ in form and timing, not that a cell's depths still span a factor of ~4
            wn = w / g["depth_mv"].to_numpy()[ok][:, None]
            sd = wn.std(axis=0, ddof=1)
            t = np.linspace(-PRE * centres[col], POST * centres[col], NPTS)
            fall_end = c["median_fall_s"]
            c.update(medoid_event_id=str(ids[med]), medoid=w[med].tolist(), q25=np.percentile(w, 25, axis=0).tolist(),
                     q75=np.percentile(w, 75, axis=0).tolist(), rel_sd=sd.tolist(),
                     rel_sd_before=float(sd[t < 0].mean()), rel_sd_fall=float(sd[(t >= 0) & (t <= fall_end)].mean())
                     if np.any((t >= 0) & (t <= fall_end)) else float("nan"),
                     rel_sd_after=float(sd[t > fall_end].mean()))
        cells.append(c)
    return cells


def fig_scatter(ev, cen, xe, ye):
    fig, ax = fs.figure(width=6.6, height=5.0)
    ax.scatter(cen["width_lower_bound_s"], cen["depth_mv"], marker=">", s=14, facecolors="none",
               edgecolors=fs.NEUTRAL, linewidths=0.6, alpha=0.55,
               label=f"not half-recovered within the search, at its lower bound (n = {len(cen):,})")
    ax.scatter(ev["duration_s"], ev["depth_mv"], s=9, color=BLUE, alpha=0.45, linewidths=0,
               label=f"half recovery measured (n = {len(ev):,})")
    ax.set_xscale("log")
    ax.set_yscale("log")
    for e in xe[1:-1]:
        ax.axvline(10 ** e, color=fs.INK_2, lw=0.7, ls=(0, (3, 3)), zorder=1)
    for e in ye[1:-1]:
        ax.axhline(10 ** e, color=fs.INK_2, lw=0.7, ls=(0, (3, 3)), zorder=1)
    counts = ev.groupby(["row", "col"]).size()
    xl, yl = ax.get_xlim(), ax.get_ylim()
    xb = np.r_[np.log10(xl[0]), xe[1:-1], np.log10(xl[1])]
    yb = np.r_[np.log10(yl[0]), ye[1:-1], np.log10(yl[1])]
    for (r, c), n in counts.items():
        ax.text(10 ** (xb[c] + 0.04 * (xb[c + 1] - xb[c])), 10 ** (yb[r + 1] - 0.05 * (yb[r + 1] - yb[r])),
                f"{n}", fontsize=7, color=fs.INK_2, va="top", ha="left")
    ax.set_xlim(xl)
    ax.set_ylim(yl)
    ax.set_xlabel("Width: onset of the fall to half recovery (s)")
    ax.set_ylabel("Depth: onset of the fall to the trough (mV)")
    ax.set_title(f"Accepted single events, width against depth ({len(ev) + len(cen):,} events, 8 recordings)",
                 loc="left")
    ax.legend(loc="upper left", fontsize=7.5, bbox_to_anchor=(0.0, 0.93))
    ax.grid(False)
    fig.text(0.01, -0.02, "Dashed lines: the 5 x 5 grid of the waveform figure (log-spaced between the 1st and 99th "
             "percentiles; the edge cells are open). Numbers: measured events per cell.", fontsize=7, color=fs.INK_2)
    fig.savefig(os.path.join(OUT, "shape_map_scatter.png"), dpi=200)
    plt.close(fig)


def fig_by_dataset(ev, cen):
    fig, axes = plt.subplots(2, 4, figsize=(9.5, 4.8), sharex=True, sharey=True)
    for ax, d in zip(axes.ravel(), ORDER):
        ax.scatter(ev["duration_s"], ev["depth_mv"], s=4, color="#d6d5d0", linewidths=0)
        g, gc = ev[ev["dataset"] == d], cen[cen["dataset"] == d]
        ax.scatter(gc["width_lower_bound_s"], gc["depth_mv"], marker=">", s=9, facecolors="none",
                   edgecolors=fs.colour(d), linewidths=0.5, alpha=0.5)
        ax.scatter(g["duration_s"], g["depth_mv"], s=7, color=fs.colour(d), alpha=0.75, linewidths=0)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_title(f"{d}\n{len(g)} measured · {len(gc)} not recovered", loc="left", fontsize=8)
        ax.grid(True, which="major")
    for ax in axes[1]:
        ax.set_xlabel("Width (s)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Depth (mV)")
    fig.suptitle("The same plane, one recording at a time (grey: every recording; triangles: lower bounds)",
                 x=0.01, ha="left", fontsize=9.5)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "shape_map_by_recording.png"), dpi=200)
    plt.close(fig)


def fig_grid(cells, xe, ye):
    rel = np.concatenate([c["rel_sd"] for c in cells if "rel_sd" in c])
    vmax = float(np.round(np.percentile(rel, 90), 2))
    norm = Normalize(0.0, vmax)
    fig, axes = plt.subplots(NBINS, NBINS, figsize=(11.0, 9.2), gridspec_kw={"hspace": 0.42, "wspace": 0.28})
    by = {(c["row"], c["col"]): c for c in cells}

    def rng(lo, hi, unit, first, last):
        a, b = 10 ** lo, 10 ** hi
        f = (lambda v: f"{v:.2g}") if unit == "mV" else (lambda v: f"{v:.3g}")
        if first:
            return f"< {f(b)} {unit}"
        if last:
            return f"> {f(a)} {unit}"
        return f"{f(a)}–{f(b)} {unit}"

    for i in range(NBINS):
        r = NBINS - 1 - i          # top row = deepest
        for c in range(NBINS):
            ax = axes[i, c]
            ax.grid(False)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
            cell = by.get((r, c))
            if i == 0:
                ax.set_title("width " + rng(xe[c], xe[c + 1], "s", c == 0, c == NBINS - 1), fontsize=8,
                             color=fs.INK)
            if c == 0:
                ax.set_ylabel("depth " + rng(ye[r], ye[r + 1], "mV", r == 0, r == NBINS - 1), fontsize=8)
            if cell is None or "medoid" not in cell:
                ax.text(0.5, 0.5, f"n = {cell['n'] if cell else 0}", transform=ax.transAxes, ha="center",
                        va="center", fontsize=8, color=fs.MUTED)
                ax.set_xticks([])
                ax.set_yticks([])
                continue
            wc = cell["centre_width_s"]
            t = np.linspace(-PRE * wc, POST * wc, NPTS)
            ax.fill_between(t, cell["q25"], cell["q75"], color="#e4e3df", lw=0, zorder=1)
            y = np.asarray(cell["medoid"])
            pts = np.column_stack([t, y]).reshape(-1, 1, 2)
            seg = np.concatenate([pts[:-1], pts[1:]], axis=1)
            sd = np.asarray(cell["rel_sd"])
            lc = LineCollection(seg, cmap=VAR_CMAP, norm=norm, linewidths=2.2, zorder=3, capstyle="round")
            lc.set_array(0.5 * (sd[:-1] + sd[1:]))
            ax.add_collection(lc)
            ax.axvline(0, color=fs.MUTED, lw=0.6, ls=(0, (2, 2)), zorder=2)
            lo = min(np.min(cell["q25"]), y.min())
            hi = max(np.max(cell["q75"]), y.max())
            pad = 0.08 * (hi - lo if hi > lo else 1)
            ax.set_xlim(t[0], t[-1])
            ax.set_ylim(lo - pad, hi + pad)
            ax.set_xticks([0, wc])
            ax.set_xticklabels(["0", f"{wc:.3g} s"], fontsize=7)
            ax.tick_params(axis="y", labelsize=6.5)
            ax.text(0.98, 0.96, f"n = {cell['n']}", transform=ax.transAxes, ha="right", va="top", fontsize=7.5,
                    color=fs.INK)
    cax = fig.add_axes([0.93, 0.25, 0.012, 0.5])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=VAR_CMAP), cax=cax, extend="max")
    cb.set_label("spread of shape across the cell's events\n(SD of each event ÷ its own depth)", fontsize=8)
    cb.ax.tick_params(labelsize=7)
    fig.suptitle("Medoid waveform of each region of the width–depth plane, aligned at the onset of the fall",
                 x=0.06, y=0.965, ha="left", fontsize=10.5)
    fig.text(0.06, 0.935, "Line: the medoid (the cell's most typical real event; mV, falls drawn as falls, 0 mV at "
             "the onset). Colour along it: how much the cell's events differ in shape at that moment, blue agree, "
             "red disagree;\nevery event is pinned to 0 at the onset, so the spread is 0 there by construction. "
             "Grey band: the middle 50 % of the cell's events (mV). Each column has its own time axis "
             "(ticks at the onset and the column's centre width).",
             fontsize=7.5, color=fs.INK_2, ha="left", va="top")
    fig.savefig(os.path.join(OUT, "shape_map_medoid_grid.png"), dpi=200, bbox_inches="tight")
    plt.close(fig)
    return vmax


# ── part 2: sequences ──────────────────────────────────────────────────────


def chains(ev, gap_max, min_events):
    out = []
    for rid, g in ev.groupby("recording_id"):
        g = g.sort_values("t_s")
        t = g["t_s"].to_numpy()
        for run in np.split(np.arange(len(g)), np.where(np.diff(t) > gap_max)[0] + 1):
            if len(run) >= min_events:
                out.append(g.iloc[run].copy())
    return out


def trend_rows(seqs):
    rows = []
    for sid, g in seqs:
        t = g["t_s"].to_numpy()
        vals = {k: g[k].to_numpy(dtype=float) for k in VARS if k != "isi_s"}
        isi = np.r_[np.nan, np.diff(t)]
        vals["isi_s"] = isi
        for k, v in vals.items():
            res = kendall_trend(t, v)
            fin = v[np.isfinite(v)]
            third = len(fin) // 3
            ratio = (float(np.median(fin[-third:]) / np.median(fin[:third]))
                     if third >= 2 and np.median(fin[:third]) > 0 else float("nan"))
            rows.append({"sequence_id": sid, "variable": k, "n": res["n"], "tau": res["tau"], "p": res["p"],
                         "last_third_over_first_third": ratio, "note": res["note"]})
    return pd.DataFrame(rows)


def human_overlaps(conn, g):
    rid, a, b = int(g["recording_id"].iloc[0]), int(g["onset_idx"].min()), int(g["onset_idx"].max())
    rows = conn.execute("SELECT s.id FROM sequences s JOIN annotations an ON an.id = s.annotation_id "
                        "WHERE s.origin = 'human' AND an.verdict IN ('interesting', 'seed') AND s.recording_id = ? "
                        "AND s.start_idx <= ? AND s.end_idx >= ?", (rid, b, a)).fetchall()
    return [int(r[0]) for r in rows]


def fig_trend_summary(tr, picked):
    fig, ax = fs.figure(width=6.6, height=2.8)
    keys = list(VARS)
    rng = np.random.default_rng(20261118)
    for i, k in enumerate(keys):
        d = tr[(tr["variable"] == k) & tr["tau"].notna()]
        sig = d["p"] < 0.05
        y = i + rng.uniform(-0.18, 0.18, len(d))
        ax.scatter(d.loc[~sig, "tau"], y[~sig.to_numpy()], s=16, color="#c9c8c2", linewidths=0, label=None)
        ax.scatter(d.loc[sig, "tau"], y[sig.to_numpy()], s=18, color=BLUE, linewidths=0)
        ax.plot([d["tau"].median()] * 2, [i - 0.32, i + 0.32], color=fs.INK, lw=2)
        ax.text(1.04, i, f"{int(sig.sum())}/{len(d)} at p < 0.05", va="center", fontsize=7.5, color=fs.INK_2,
                transform=ax.get_yaxis_transform())
    ax.axvline(0, color=fs.MUTED, lw=0.8)
    ax.set_yticks(range(len(keys)))
    ax.set_yticklabels([VARS[k][1] + (" *" if k in picked else "") for k in keys])
    ax.set_xlim(-1, 1)
    ax.set_xlabel("Kendall's tau of the measure against time, one dot per sequence (blue: p < 0.05)")
    ax.set_title("Which measures change along a sequence (black bar: median tau; * in the headline figure)",
                 loc="left")
    ax.grid(axis="y", visible=False)
    fig.savefig(os.path.join(OUT, "sequence_trend_summary.png"), dpi=200)
    plt.close(fig)


def _values(g, k):
    t = g["t_s"].to_numpy()
    v = np.r_[np.nan, np.diff(t)] if k == "isi_s" else g[k].to_numpy(dtype=float)
    return t, v, np.isfinite(v) & (v > 0)


def fig_trends(seqs, meta, picked, name="sequence_trends.png"):
    """Per variable: [as measured, every sequence but the longest] [as measured, the longest alone]
    [normalised, all]. The longest (90 h) would squash every other sequence into the first sixth of a shared
    time axis, so it gets its own panel rather than a clipped one."""
    fig, axes = plt.subplots(len(picked), 3, figsize=(14.0, 3.4 * len(picked)), squeeze=False,
                             gridspec_kw={"width_ratios": [1, 1.25, 1]})
    top = meta.sort_values("n_events", ascending=False)["sequence_id"].tolist()[:TOP_LINES]
    colour = {sid: SERIES[i] for i, sid in enumerate(top)}
    longest = meta.sort_values("duration_h", ascending=False)["sequence_id"].iloc[0]
    lmeta = meta.set_index("sequence_id").loc[longest]
    for row, k in zip(axes, picked):
        ax_raw, ax_long, ax_norm = row
        binned = []
        for sid, g in sorted(seqs, key=lambda s: s[0] in colour):
            t, v, keep = _values(g, k)
            if keep.sum() < 3:
                continue
            th = (t - t[0]) / 3600.0
            frac = (t - t[0]) / (t[-1] - t[0])
            rel = v / np.median(v[keep])
            col = colour.get(sid, "#c9c8c2")
            lw, al, z = (1.4, 0.95, 3) if sid in colour else (0.8, 0.7, 2)
            if sid == longest:
                ax_long.plot(th[keep], v[keep], color=col, lw=0.6, alpha=0.55, marker="o", ms=1.8, zorder=2)
                roll = pd.Series(v[keep]).rolling(25, center=True, min_periods=8).median()
                ax_long.plot(th[keep], roll, color=fs.INK, lw=2.2, zorder=3, label="running median of 25 events")
            else:
                ax_raw.plot(th[keep], v[keep], color=col, lw=lw, alpha=al, zorder=z, marker="o",
                            ms=2.2 if sid in colour else 1.5)
            ax_norm.plot(frac[keep], rel[keep], color=col, lw=lw if sid != longest else 0.6,
                         alpha=al if sid != longest else 0.5, zorder=z)
            binned.append(pd.DataFrame({"frac": frac[keep], "rel": rel[keep], "sid": sid}))
        b = pd.concat(binned)
        b["bin"] = np.minimum((b["frac"] * 10).astype(int), 9)
        # each sequence counts once per bin, so the long sequences do not outvote the short ones
        med = b.groupby(["bin", "sid"])["rel"].median().groupby("bin").median()
        ax_norm.plot((med.index + 0.5) / 10, med.values, color=fs.INK, lw=2.6, zorder=5,
                     label="median across sequences")
        ax_raw.set_yscale("log")
        ax_long.set_yscale("log")
        ax_norm.set_yscale("log", base=2)
        ax_norm.axhline(1, color=fs.MUTED, lw=0.8)
        ax_raw.set_ylabel(VARS[k][0])
        ax_norm.set_ylabel(f"{VARS[k][1]} ÷ the sequence's median")
        for ax in (ax_raw, ax_long):
            ax.set_xlabel("Hours since the sequence's first event")
        ax_norm.set_xlabel("Fraction of the sequence's duration")
        ax_raw.set_title(f"{VARS[k][1].capitalize()}, as measured: {len(seqs) - 1} sequences", loc="left")
        ax_long.set_title(f"…and the longest, {longest} {lmeta['dataset']} CH{lmeta['channel_1based']} "
                          f"({lmeta['n_events']} events)", loc="left")
        ax_norm.set_title(f"{VARS[k][1].capitalize()}, normalised per sequence", loc="left")
        ax_norm.legend(loc="upper left", fontsize=7.5)
        ax_long.legend(loc="best", fontsize=7.5)
    handles = [plt.Line2D([], [], color=colour[sid], lw=1.6) for sid in top]
    labels = [meta.set_index("sequence_id").loc[sid, "label"] for sid in top]
    handles.append(plt.Line2D([], [], color="#c9c8c2", lw=1))
    labels.append(f"the other {len(seqs) - len(top)} sequences")
    fig.legend(handles, labels, loc="lower center", ncol=3, fontsize=7.5, bbox_to_anchor=(0.5, -0.07))
    fig.suptitle(f"Shape change along {len(seqs)} sequences of adjacent accepted events "
                 f"(next onset within {GAP_MAX_S / 60:.0f} min, at least {MIN_EVENTS} events)", x=0.01, ha="left",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, name), dpi=200 if len(picked) <= 2 else 150, bbox_inches="tight")
    plt.close(fig)


def alternation(seqs):
    """Does a wide event tend to be followed by a narrow one? 'Wide' = more than twice the sequence's median
    width. The switch rate (how often neighbours differ in class) is compared with the same sequence shuffled;
    a strictly alternating wide-narrow-wide train switches every time, a clumped one rarely."""
    rng = np.random.default_rng(SEED)
    rows = []
    for sid, g in seqs:
        w_all = g["duration_s"].to_numpy(dtype=float)
        f = np.isfinite(w_all)
        w = w_all[f]
        if len(w) < ALT_MIN:
            continue
        wide = (w > 2 * np.median(w)).astype(int)
        if wide.sum() < 3 or wide.sum() > len(wide) - 3:
            continue
        gap = np.r_[np.nan, np.diff(g["t_s"].to_numpy())][f]     # to the previous accepted event, any width
        depth = g["depth_mv"].to_numpy(dtype=float)[f]
        obs = float(np.mean(np.diff(wide) != 0))
        null = np.array([np.mean(np.diff(rng.permutation(wide)) != 0) for _ in range(ALT_DRAWS)])
        rows.append({"sequence_id": sid, "n_widths": len(w), "n_wide": int(wide.sum()),
                     "wide_after_wide": int(np.sum((wide[1:] == 1) & (wide[:-1] == 1))),
                     "switch_rate": obs, "shuffled_switch_rate": float(null.mean()),
                     "p_switch_ge": float((np.sum(null >= obs) + 1) / (ALT_DRAWS + 1)),
                     "median_width_wide_s": float(np.median(w[wide == 1])),
                     "median_width_narrow_s": float(np.median(w[wide == 0])),
                     "median_depth_wide_mv": float(np.median(depth[wide == 1])),
                     "median_depth_narrow_mv": float(np.median(depth[wide == 0])),
                     "median_gap_before_wide_s": float(np.nanmedian(gap[wide == 1])),
                     "median_gap_before_narrow_s": float(np.nanmedian(gap[wide == 0]))})
    return pd.DataFrame(rows)


# ── main ───────────────────────────────────────────────────────────────────


def main():
    fs.apply()
    os.makedirs(OUT, exist_ok=True)
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    recs = recordings(conn)
    m = anatomy_check(load_events(pd.read_csv(INV)), recs)
    m.drop(columns=["search_end"]).to_csv(os.path.join(OUT, "inventory_with_checks.csv"), index=False)
    single = m[(m["status"] == "single") & ~m["anatomy_suspect"]]
    ev = single[single["duration_s"].notna() & (single["depth_mv"] > 0)].reset_index(drop=True)
    cen = single[single["duration_s"].isna() & (single["depth_mv"] > 0)].reset_index(drop=True)

    # part 1
    ev, xe, ye = assign_cells(ev)
    W, centres = waveforms(ev, recs, xe)
    cells = cell_stats(ev, W, centres)
    fig_scatter(ev, cen, xe, ye)
    fig_by_dataset(ev, cen)
    vmax = fig_grid(cells, xe, ye)
    ev.drop(columns=["search_end"]).to_csv(os.path.join(OUT, "events_shape_map.csv"), index=False)
    pd.DataFrame([{k: v for k, v in c.items() if k not in ("medoid", "q25", "q75", "rel_sd")} for c in cells]) \
        .to_csv(os.path.join(OUT, "grid_cells.csv"), index=False)

    # part 2: chains over every measured accepted event (single, and the main fall of a multi-fall span)
    timed = m[m["status"].isin(["single", "multiple"]) & m["onset_idx"].notna() & ~m["anatomy_suspect"]].copy()
    sens = []
    for gmax in SENS_GAPS:
        for mn in (3, MIN_EVENTS):
            cs = chains(timed, gmax, mn)
            sens.append({"gap_max_s": gmax, "min_events": mn, "sequences": len(cs),
                         "events_in_sequences": int(sum(len(c) for c in cs)),
                         "largest": int(max((len(c) for c in cs), default=0))})
    cs = chains(timed, GAP_MAX_S, MIN_EVENTS)
    seqs, meta, members = [], [], []
    for i, g in enumerate(sorted(cs, key=lambda c: (-len(c), c["recording_id"].iloc[0], c["t_s"].iloc[0]))):
        sid = f"S{i + 1:02d}"
        d, ch, rid = g["dataset"].iloc[0], int(g["channel"].iloc[0]), int(g["recording_id"].iloc[0])
        dur_h = (g["t_s"].iloc[-1] - g["t_s"].iloc[0]) / 3600.0
        trains = sorted(set(g["train_id"].dropna()))
        meta.append({"sequence_id": sid, "dataset": d, "recording_id": rid, "channel_1based": ch + 1,
                     "n_events": len(g), "n_multi_fall_spans": int((g["status"] == "multiple").sum()),
                     "start_s": float(g["t_s"].iloc[0]), "end_s": float(g["t_s"].iloc[-1]), "duration_h": dur_h,
                     "median_gap_s": float(np.median(np.diff(g["t_s"]))),
                     "approved_train_members": int(g["train_id"].notna().sum()), "approved_trains": "; ".join(trains),
                     "human_sequence_ids": "; ".join(map(str, human_overlaps(conn, g))),
                     "label": f"{sid} {d} CH{ch + 1} · {len(g)} events · {dur_h:.1f} h"})
        g = g.assign(sequence_id=sid, position=np.arange(len(g)), isi_s=np.r_[np.nan, np.diff(g["t_s"])])
        members.append(g)
        seqs.append((sid, g))
    meta = pd.DataFrame(meta)
    tr = trend_rows(seqs)
    summ = []
    for k in VARS:
        d = tr[(tr["variable"] == k) & tr["tau"].notna()]
        sig = d[d["p"] < 0.05]
        summ.append({"variable": k, "testable": len(d), "p_lt_0.05": len(sig), "up": int((sig["tau"] > 0).sum()),
                     "down": int((sig["tau"] < 0).sum()), "expected_by_chance": round(0.05 * len(d), 1),
                     "median_tau": float(d["tau"].median()), "median_abs_tau": float(d["tau"].abs().median()),
                     "median_ratio_last_first_third": float(d["last_third_over_first_third"].median())})
    summ = pd.DataFrame(summ)
    # The score ranks how many sequences trend beyond chance. No measure shares a direction across sequences
    # (every median tau is ~0), so the headline pair is the researcher's own drop height and interval, both strong
    # in the longest sequence (CH14: tau +0.49 and -0.28); every measure is drawn in the companion figure.
    summ["score"] = summ["p_lt_0.05"] / summ["testable"] + 0.01 * summ["median_tau"].abs()
    picked = PICKED
    fig_trend_summary(tr, picked)
    fig_trends(seqs, meta, picked)
    fig_trends(seqs, meta, list(VARS), name="sequence_trends_all_measures.png")
    alt = alternation(seqs)
    alt.to_csv(os.path.join(OUT, "sequence_width_alternation.csv"), index=False)
    meta.to_csv(os.path.join(OUT, "sequences.csv"), index=False)
    pd.concat(members)[["sequence_id", "position", "event_id", "dataset", "recording_id", "status", "onset_idx",
                        "extremum_idx", "t_s", "isi_s", "depth_mv", "fall_s", "duration_s", "fall_rate_mv_s",
                        "train_id"]].to_csv(os.path.join(OUT, "sequence_members.csv"), index=False)
    tr.to_csv(os.path.join(OUT, "sequence_trends.csv"), index=False)
    summ.drop(columns="score").to_csv(os.path.join(OUT, "sequence_trend_summary.csv"), index=False)

    out = {
        "inventory": {k: int(v) for k, v in m["status"].value_counts().items()},
        "anatomy_suspect": {"threshold_frac": SUSPECT_FRAC, "single": int((m["anatomy_suspect"] &
                                                                           (m["status"] == "single")).sum()),
                            "multiple": int((m["anatomy_suspect"] & (m["status"] == "multiple")).sum()),
                            "by_dataset": {k: int(v) for k, v in
                                           m.loc[m["anatomy_suspect"], "dataset"].value_counts().items()}},
        "single_measured": len(ev), "single_not_half_recovered": len(cen),
        "multi_fall_spans": int((m["status"] == "multiple").sum()),
        "falls_in_multi_fall_spans": int(m.loc[m["status"] == "multiple", "n_falls"].sum()),
        "grid": {"width_edges_s": (10 ** xe).round(3).tolist(), "depth_edges_mv": (10 ** ye).round(3).tolist(),
                 "colour_max_rel_sd": vmax},
        "chain_sensitivity": sens, "gap_max_s": GAP_MAX_S, "min_events": MIN_EVENTS, "sequences": len(meta),
        "events_in_sequences": int(meta["n_events"].sum()), "picked": picked,
        "trend_summary": summ.drop(columns="score").to_dict("records"),
        "width_alternation": alt.to_dict("records"),
    }
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=float)
    conn.close()
    pd.set_option("display.width", 220)
    print(json.dumps({k: v for k, v in out.items() if k not in ("trend_summary",)}, indent=1, default=float))
    print(summ.round(3).to_string(index=False))
    print(meta.drop(columns="label").round(2).to_string(index=False))
    cdf = pd.DataFrame([{k: v for k, v in c.items() if k not in ("medoid", "q25", "q75", "rel_sd", "datasets")}
                        for c in cells])
    print(cdf.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
