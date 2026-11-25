"""
drop_plots_20261123.py
======================
Experimental plots of every reviewed drop event and of the CH14 and hand-labelled sequences (the researcher, 23 Nov:
"take what I have got and produce ... plots ... feel free to try your own experiments").

The events: every accepted individual span of the catalogue (its main drop, measured by the whole-drop rule,
`docs/library_analysis/20261123/revised/whole_drop.csv`) and every drop accepted (interesting or seed) in the
candidate-event queues today, measured by the same rule at its own moment (`whole_drop.measure(..., anchor=)`).
Spans whose biggest, fastest movement is a rise (spikes measured as drops) are left out of the drop plots.

The sequences: the CH14 candidate sequences of queue 48 (MJu26a and M2_aug) and the 30 hand-labelled sequences
(ids 119-148), approved or not. Their drops are found afresh by the whole-drop rule (79d0243e) over the whole sequence:
every drop at least MIN_SIGMAS x the channel's local noise whose core (top to half recovery) is at least
MIN_CORE_SAMPLES long - the candidate-event queues' floors - but WITHOUT the rule's relative floor (15 % of the span's
deepest drop), so a long sequence keeps its small drops next to its big ones. Drops the researcher judged noise or
artefact in the candidate-event queues are left out of every measure; accepted ones are marked.

Read-only (database `mode=ro`, channels memory-mapped). Writes `docs/library_analysis/20261123_plots/`.

    PYTHONIOENCODING=utf-8 "$PY" scripts/library_analysis/drop_plots_20261123.py [stage ...]

Stages: `events` (the table, cached as events.csv), `species`, `map`, `sequences` (the sequences' drops, cached as
sequence_events.csv, and one figure per sequence), `types`, `extra`, `index`, or `all` (the default).
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "thesis"))

import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402  (figstyle selected the Agg backend)
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, LogNorm, Normalize, PowerNorm, to_rgba  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from scipy.spatial.distance import cdist  # noqa: E402
from scipy.stats import gaussian_kde, mannwhitneyu, spearmanr  # noqa: E402

from Working.interrogation import whole_drop as WD  # noqa: E402
from Working.interrogation.intervals import kendall_trend  # noqa: E402

DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite").replace("\\", "/")
WHOLE = os.path.join(ROOT, "docs", "library_analysis", "20261123", "revised", "whole_drop.csv")
CATALOGUE = os.path.join(ROOT, "docs", "thesis", "data", "accepted_catalogue_20261109", "accepted_spans.csv")
OUT = os.path.join(ROOT, "docs", "library_analysis", "20261123_plots")
CAPTIONS_FILE = os.path.join(OUT, "captions.json")
ACCEPTED = ("interesting", "seed")
REJECTED = ("not_interesting", "artifact")
SPECIES_ORDER = ["oyster", "chocolate oyster", "snow oyster", "lion's mane", "Asian shiitake"]
DATASET_ORDER = ["M2_aug", "M2_concat", "M4", "CO", "SO", "LM", "MJu26a", "SH"]
SEED = 20261123
MAX_READ = 3_000_000       # longest stretch (samples) read for one drop's waveform

# the sequences
CH14_SEQUENCES = (254, 255, 569, 570, 571, 572, 573, 382, 383, 384, 385)
HAND_SEQUENCES = tuple(range(119, 149))
MIN_SIGMAS = 15.0          # the candidate-event queues' floor, calibrated on the researcher's verdicts
MIN_CORE_SAMPLES = 5       # the researcher's rule: a drop whose core is under 5 samples is noise
NOISE_HALF_S = 1800.0      # the local noise is read over this either side of a drop's top
SEQ_CONTEXT_S = 1800.0     # context read either side of a sequence
TYPES_MIN = 40             # a sequence needs this many drops for the two-kinds analysis
SHUFFLES = 5000
BLOCK = 10                 # the local shuffle keeps each drop within its block of this many

# the adaptive map
LEAF_MAX = 36              # a cell with more drops than this is split in four ...
LEVEL_MAX = 6              # ... at most this many times
MIN_GLYPH = 5              # a cell needs this many drops for a waveform
PRE_W, POST_W = 0.5, 2.5   # glyph window: from half a cell-width before the top to 2.5 after
NPTS = 101
Y_LO, Y_HI = -1.45, 0.5    # glyph range, in units of each drop's own depth (0 = its top, -1 = its bottom)

BLUE, RED, MID, ORANGE, PURPLE, GREEN = "#2a78d6", "#e34948", "#9a9893", "#eb6834", "#6250d6", "#1baf7a"
VAR_CMAP = LinearSegmentedColormap.from_list("agree_disagree", [BLUE, MID, RED])
DENSITY_CMAP = LinearSegmentedColormap.from_list("density", ["#ffffff", "#c9dcf3", "#2a78d6", "#0e2a52"])
TYPE_COLOURS = (BLUE, ORANGE)
SEQ_MEASURES = [("depth_mv", "Depth (mV)", "depth"), ("fall_s", "Fall time (s)", "fall time"),
                ("width_s", "Width, top to half recovery (s)", "width"),
                ("fall_rate_mv_s", "Fall rate (mV/s)", "fall rate"),
                ("interval_s", "Interval since the previous drop (s)", "interval")]
S_ANATOMY, S_SPECIES, S_MAP = "How a drop is measured", "Drops by species", "Shape map"
S_GRIDS, S_SEQ = "Shape grids (uniform 10 x 10)", "Sequences, one by one"
S_TYPES, S_EXTRA = "Two kinds of drop in one sequence", "Experiments"
SECTIONS = [S_ANATOMY, S_SPECIES, S_MAP, S_GRIDS, S_SEQ, S_TYPES, S_EXTRA]


# ── helpers ──────────────────────────────────────────────────────────────────

def to_mv(units):
    return {"mV": 1.0, "uV": 0.001}.get(units or "V", 1000.0)


def species_of(dataset):
    return fs.RECORDINGS.get(dataset, ("other", fs.NEUTRAL))[0]


def as_bool(s):
    return s.map(lambda v: str(v).strip().lower() == "true")


def recordings(conn):
    return {int(r[0]): {"npy": r[1], "fs": float(r[2]), "units": r[3], "file": r[4], "channel": int(r[5]),
                        "n": int(r[6])}
            for r in conn.execute("SELECT id, npy_path, fs, units, source_file, channel, n_samples FROM recordings")}


_ARRAYS = {}


def channel(recs, rid):
    if rid not in _ARRAYS:
        _ARRAYS[rid] = np.load(os.path.join(ROOT, recs[rid]["npy"]), mmap_mode="r")
    return _ARRAYS[rid]


def window(recs, rid, a, b):
    """Channel samples [a, b) in mV, or None when the window leaves the recording, is too long or holds a gap."""
    x = channel(recs, rid)
    a, b = int(a), int(b)
    if a < 0 or b > len(x) or b - a < 2 or b - a > MAX_READ:
        return None
    seg = np.asarray(x[a:b], dtype=float) * to_mv(recs[rid]["units"])
    return seg if np.all(np.isfinite(seg)) else None


def shape(recs, rid, top, unit_n, lo_u, hi_u, npts, depth=None):
    """The trace round sample `top` on `npts` points from `lo_u` to `hi_u` units of `unit_n` samples, in mV relative
    to the top (divided by `depth` when given), or None."""
    top, unit_n = int(top), float(unit_n)
    a = int(np.floor(top + lo_u * unit_n)) - 1
    b = int(np.ceil(top + hi_u * unit_n)) + 2
    seg = window(recs, rid, a, b)
    if seg is None:
        return None
    y = seg - seg[top - a]
    if depth:
        y = y / float(depth)
    return np.interp(np.linspace(lo_u, hi_u, npts), (np.arange(a, b) - top) / unit_n, y)


def log_ticks(ax, x=True, y=True, minor=True):
    """Ticks for an axis holding log10 values, labelled in real units (1-2-5 steps when the range is narrow)."""
    def ticks(lo, hi):
        out = []
        for e in range(int(np.floor(lo)) - 1, int(np.ceil(hi)) + 1):
            for m in ((1, 2, 5) if (hi - lo) < 4.5 and minor else (1,)):
                v = e + np.log10(m)
                if lo <= v <= hi:
                    out.append(v)
        return out

    def lab(v):
        r = 10 ** v
        return f"{r:g}" if r >= 0.01 else f"{r:.0e}"
    if x:
        t = ticks(*ax.get_xlim())
        ax.set_xticks(t)
        ax.set_xticklabels([lab(v) for v in t])
    if y:
        t = ticks(*ax.get_ylim())
        ax.set_yticks(t)
        ax.set_yticklabels([lab(v) for v in t])


def running_median(v, k):
    return pd.Series(v).rolling(k, center=True, min_periods=max(3, k // 3)).median().to_numpy()


def fmt_p(p):
    if p is None or not np.isfinite(p):
        return "n/a"
    return "< 0.001" if p < 0.001 else f"= {p:.2g}"


def _captions():
    if os.path.exists(CAPTIONS_FILE):
        with open(CAPTIONS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save(fig, name, section, caption, dpi=170):
    """Save a figure under OUT and record its caption for the index page."""
    path = os.path.join(OUT, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    caps = _captions()
    caps[name.replace("\\", "/")] = {"section": section, "caption": caption}
    with open(CAPTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(caps, f, indent=1, ensure_ascii=False)


def present(ev):
    have = set(ev["dataset"])
    return [d for d in DATASET_ORDER if d in have]


def species_present(ev, col=None, least=3):
    out = []
    for sp in SPECIES_ORDER:
        g = ev[ev["species"] == sp]
        if col is not None:
            g = g[g[col] > 0]
        if len(g) >= least:
            out.append(sp)
    return out


# ── the events ───────────────────────────────────────────────────────────────

def catalogue_events():
    w = pd.read_csv(WHOLE)
    cat = pd.read_csv(CATALOGUE)[["event_id", "acceptance_level", "source_verdict"]]
    w = w.merge(cat, on="event_id", how="left")
    keep = (w["acceptance_level"] == "individual_span") & w["whole_depth_mv"].notna()
    keep &= ~as_bool(w["whole_rise_dominated"])
    w = w[keep]
    return pd.DataFrame({
        "event_id": w["event_id"], "source": "catalogue", "dataset": w["dataset"].map(fs.name),
        "recording_id": w["recording_id"].astype(int), "fs": w["fs"].astype(float),
        "top_idx": w["whole_top_idx"].astype(int), "bottom_idx": w["whole_bottom_idx"].astype(int),
        "recovery_idx": w["whole_recovery_idx"], "depth_mv": w["whole_depth_mv"], "fall_s": w["whole_fall_s"],
        "width_s": w["whole_width_s"], "recovery_s": w["whole_half_recovery_s"], "steep_s": w["whole_steep_s"],
        "long_tail": as_bool(w["whole_long_tail"]), "events_in_span": w["whole_n_events"]})


def queue_events(conn, recs):
    """Drops accepted today in the candidate-event queues, measured by the whole-drop rule at their own top."""
    rows = conn.execute(
        "SELECT d.id, r.recording_id, d.start_idx, d.end_idx, d.meta_json, "
        "(SELECT a.verdict FROM adjudications a WHERE a.detection_id = d.id ORDER BY a.id DESC LIMIT 1) AS v "
        "FROM detections d JOIN runs r ON r.id = d.run_id JOIN configs c ON c.id = r.config_id "
        "WHERE (c.config_json LIKE '%candidate-events%' OR c.config_json LIKE '%ch14-small-drops%') "
        "AND d.id IN (SELECT detection_id FROM adjudications)").fetchall()
    out = []
    for did, rid, s, e, meta, verdict in rows:
        if verdict not in ACCEPTED:
            continue
        rec, m = recs[int(rid)], json.loads(meta)
        x = channel(recs, int(rid))
        r = WD.measure(x, int(s), int(e), rec["fs"], to_mv=to_mv(rec["units"]), anchor=int(m["top_idx"]))
        if not r.get("ok"):
            continue
        out.append({"event_id": f"queue-detection-{did}", "source": "queue", "dataset": fs.name(rec["file"]),
                    "recording_id": int(rid), "fs": rec["fs"], "top_idx": int(r["top_idx"]),
                    "bottom_idx": int(r["bottom_idx"]), "recovery_idx": r["recovery_idx"], "depth_mv": r["depth_mv"],
                    "fall_s": r["fall_s"], "width_s": r["width_s"], "recovery_s": r["half_recovery_s"],
                    "steep_s": r["steep_s"], "long_tail": bool(r["long_tail"]), "events_in_span": r["n_events"],
                    "group": m.get("group")})
    return pd.DataFrame(out)


def build_events(conn, recs):
    cat, q = catalogue_events(), queue_events(conn, recs)
    seen = {}
    for r in cat.itertuples():
        seen.setdefault(r.recording_id, []).append((r.top_idx, r.bottom_idx))
    fresh = [not any(min(r.bottom_idx, b) > max(r.top_idx, t) for t, b in seen.get(r.recording_id, ()))
             for r in q.itertuples()]
    ev = pd.concat([cat, q[fresh]], ignore_index=True)
    ev["species"] = ev["dataset"].map(species_of)
    ev["channel"] = ev["recording_id"].map(lambda r: recs[r]["channel"])
    ev["t_h"] = ev["top_idx"] / ev["fs"] / 3600.0
    ev["fall_rate_mv_s"] = ev["depth_mv"] / ev["fall_s"].clip(lower=1.0 / ev["fs"])
    return ev.sort_values(["dataset", "recording_id", "top_idx"]).reset_index(drop=True)


def load_events():
    ev = pd.read_csv(os.path.join(OUT, "events.csv"))
    ev["long_tail"] = as_bool(ev["long_tail"])
    return ev


# ── how a drop is measured ───────────────────────────────────────────────────

def fig_anatomy(ev, recs):
    """One ordinary drop with its four measures drawn on it."""
    g = ev[(ev["dataset"] == "MJu26a") & ev["width_s"].notna() & ~ev["long_tail"]
           & (ev["fall_s"] <= 1.3 * ev["steep_s"])].copy()
    g["score"] = (np.log(g["depth_mv"] / g["depth_mv"].median()) ** 2
                  + np.log(g["width_s"] / g["width_s"].median()) ** 2)
    r = g.sort_values("score").iloc[0]
    rid, f = int(r["recording_id"]), float(r["fs"])
    top, bottom, rec = int(r["top_idx"]), int(r["bottom_idx"]), float(r["recovery_idx"])
    w = rec - top
    a, b = int(top - 0.8 * w), int(top + 2.6 * w)
    y = window(recs, rid, a, b)
    t = (np.arange(a, b) - top) / f
    fig, ax = plt.subplots(figsize=(9.0, 4.6))
    ax.plot(t, y, color=fs.INK, lw=1.1)
    yt, yb = y[top - a], y[bottom - a]
    yh = yb + 0.5 * (yt - yb)
    tb, tr = (bottom - top) / f, (rec - top) / f
    ax.plot([0], [yt], "o", color=BLUE, ms=7, zorder=5)
    ax.plot([tb], [yb], "o", color=RED, ms=7, zorder=5)
    ax.plot([tr], [yh], "o", color=GREEN, ms=7, zorder=5)
    ax.axhline(yt, color=fs.GRID, lw=0.9, ls="--")
    ax.axhline(yh, color=GREEN, lw=0.8, ls=":")
    span = yt - yb
    ax.annotate("", xy=(-0.12 * w / f, yb), xytext=(-0.12 * w / f, yt),
                arrowprops={"arrowstyle": "<->", "color": RED, "lw": 1.4})
    ax.text(-0.15 * w / f, 0.5 * (yt + yb), f"amplitude\n{r['depth_mv']:.2g} mV", ha="right", va="center",
            color=RED, fontsize=9)
    for y0, x0, x1, lab, c in ((yt + 0.12 * span, 0, tb, f"fall time {r['fall_s']:.3g} s", RED),
                               (yt + 0.26 * span, 0, tr, f"width {r['width_s']:.3g} s", GREEN),
                               (yb - 0.12 * span, tb, tr, f"recovery {r['recovery_s']:.3g} s", PURPLE)):
        ax.annotate("", xy=(x1, y0), xytext=(x0, y0), arrowprops={"arrowstyle": "<->", "color": c, "lw": 1.3})
        ax.text(0.5 * (x0 + x1), y0 + 0.02 * span * (1 if y0 > yt else -1), lab, ha="center",
                va="bottom" if y0 > yt else "top", color=c, fontsize=9)
    ax.text(0, yt, "  top", color=BLUE, va="bottom", fontsize=9)
    ax.text(tb, yb, "  bottom", color=RED, va="top", fontsize=9)
    ax.text(tr, yh, "  half recovery", color=GREEN, va="top", fontsize=9)
    ax.set_xlabel("Seconds from the top of the drop")
    ax.set_ylabel("mV")
    ax.set_ylim(yb - 0.3 * span, yt + 0.42 * span)
    ax.set_title(f"How every drop is measured: one ordinary drop (MJu26a CH{int(r['channel']) + 1}, "
                 f"{r['t_h']:.1f} h)", loc="left")
    save(fig, "anatomy_example.png", S_ANATOMY,
         "One ordinary drop with its measures. Amplitude: the top to the bottom. Fall time: the top to the bottom. "
         "Width: the top to the moment it has climbed back half of the amplitude. Recovery: the bottom to that "
         "moment. The whole-drop rule (79d0243e) finds the top and the bottom; every figure here uses it.")


# ── per species ──────────────────────────────────────────────────────────────

MEASURES = [("depth_mv", "Amplitude: top to bottom (mV)"), ("width_s", "Width: top to half recovery (s)"),
            ("recovery_s", "Recovery: bottom to half recovery (s)"), ("fall_s", "Fall time: top to bottom (s)"),
            ("steep_s", "Steep part of the fall (s)")]


def _species_axis(ax, ds, pos, seps):
    for sx in seps:
        ax.axvline(sx, color=fs.GRID, lw=1.2, zorder=0)
    ax.set_xticks([pos[d] for d in ds])
    ax.set_xticklabels(ds, fontsize=7.5, rotation=30, ha="right")
    ax.grid(axis="x", visible=False)
    for sp in SPECIES_ORDER:
        members = [pos[d] for d in ds if species_of(d) == sp]
        if members:
            ax.text(np.mean(members), -0.2, sp.replace(" ", "\n", 1), transform=ax.get_xaxis_transform(),
                    ha="center", va="top", fontsize=7.5, color=fs.species_colour(sp), fontweight="bold")


def fig_species_boxes(ev):
    ds = present(ev)
    pos, x, seps, last = {}, 0.0, [], None
    for d in ds:
        sp = species_of(d)
        if last is not None and sp != last:
            x += 0.9
            seps.append(x - 0.95)
        pos[d] = x
        last = sp
        x += 1.0
    fig, axes = plt.subplots(2, 3, figsize=(16.0, 9.6))
    rng = np.random.default_rng(SEED)
    for ax, (col, label) in zip(axes.ravel(), MEASURES):
        for d in ds:
            v = ev.loc[(ev["dataset"] == d) & (ev[col] > 0), col].dropna().to_numpy(float)
            if not len(v):
                continue
            c = fs.colour(d)
            ax.scatter(pos[d] + rng.uniform(-0.28, 0.28, len(v)), v, s=4, color=c, alpha=0.28, linewidths=0, zorder=2)
            b = ax.boxplot([v], positions=[pos[d]], widths=0.62, whis=(5, 95), showfliers=False, patch_artist=True,
                           medianprops={"color": fs.INK, "lw": 1.8}, whiskerprops={"color": fs.INK_2},
                           capprops={"color": fs.INK_2}, boxprops={"edgecolor": fs.INK_2, "lw": 0.9}, zorder=3)
            b["boxes"][0].set_facecolor(to_rgba(c, 0.35))
            ax.text(pos[d], 1.01, f"n={len(v)}", transform=ax.get_xaxis_transform(), ha="center", va="bottom",
                    fontsize=6.5, color=fs.INK_2)
        ax.set_yscale("log")
        ax.set_ylabel(label)
        _species_axis(ax, ds, pos, seps)
    ax = axes.ravel()[-1]
    for d in ds:
        g = ev[ev["dataset"] == d]
        rec, tail = g["width_s"].notna().mean(), g["long_tail"].mean()
        ax.bar(pos[d] - 0.2, 100 * rec, width=0.38, color=to_rgba(fs.colour(d), 0.8))
        ax.bar(pos[d] + 0.2, 100 * tail, width=0.38, color=to_rgba(fs.colour(d), 0.35), hatch="///",
               edgecolor=fs.INK_2, lw=0.5)
    handles = [Rectangle((0, 0), 1, 1, facecolor=fs.MUTED, edgecolor="none"),
               Rectangle((0, 0), 1, 1, facecolor="white", hatch="///", edgecolor=fs.INK_2, lw=0.5)]
    ax.set_ylabel("% of the recording's drops")
    ax.set_ylim(0, 100)
    ax.legend(handles, ["climbed half-way back (has a width)", "long tail (fall > 10x its steep part)"],
              fontsize=7.5, loc="upper right", bbox_to_anchor=(1.0, 1.12), frameon=False)
    _species_axis(ax, ds, pos, seps)
    fig.suptitle(f"Every reviewed drop, by recording within each species ({len(ev):,} drops)", x=0.01, ha="left",
                 fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.97), h_pad=3.2)
    save(fig, "species_boxplots.png", S_SPECIES,
         "Amplitude, width, recovery, fall time and the steep part of the fall of every reviewed drop (the accepted "
         "catalogue plus today's accepted queue drops), one box per recording, recordings grouped by species. Box: "
         "the middle half; line: the median; whiskers: the 5th to 95th percentile; dots: every drop. Log scales. "
         "Width and recovery exist only where the drop climbed half-way back before the next drop or two hours "
         "(last panel: how often that happened, and how often the fall ran on as a long tail). The fall time runs "
         "from the top to the bottom, so it includes a slow shoulder or tail; the steep part is the fall's fast "
         "core alone.")


def fig_species_rainclouds(ev):
    """One row per species: a half-violin (the density of the log values), a box, and the drops themselves."""
    sps = species_present(ev)
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 5.4), sharey=True)
    rng = np.random.default_rng(SEED)
    for ax, (col, label) in zip(axes, MEASURES[:3]):
        for k, sp in enumerate(sps):
            v = ev.loc[(ev["species"] == sp) & (ev[col] > 0), col].dropna().to_numpy(float)
            if len(v) < 3:
                continue
            lv, c, y0 = np.log10(v), fs.species_colour(sp), len(sps) - 1 - k
            grid = np.linspace(lv.min() - 0.2, lv.max() + 0.2, 300)
            dens = gaussian_kde(lv)(grid)
            ax.fill_between(10 ** grid, y0 + 0.08, y0 + 0.08 + 0.55 * dens / dens.max(), color=c, alpha=0.55, lw=0)
            q = np.percentile(v, [5, 25, 50, 75, 95])
            ax.plot([q[0], q[4]], [y0, y0], color=fs.INK_2, lw=0.9)
            ax.add_patch(Rectangle((q[1], y0 - 0.06), q[3] - q[1], 0.12, facecolor=c, edgecolor=fs.INK_2, lw=0.8))
            ax.plot([q[2], q[2]], [y0 - 0.06, y0 + 0.06], color=fs.INK, lw=1.8)
            ax.scatter(v, y0 - 0.22 + rng.uniform(-0.09, 0.09, len(v)), s=3, color=c, alpha=0.35, linewidths=0)
            ax.text(q[2], y0 + 0.1, f"{q[2]:.3g}", fontsize=7.5, color=fs.INK, ha="center", va="bottom")
        ax.set_xscale("log")
        ax.set_xlabel(label)
        ax.set_yticks(range(len(sps)))
        ax.set_yticklabels(list(reversed([f"{sp}\n(n = {(ev['species'] == sp).sum()})" for sp in sps])),
                           fontsize=8.5)
        ax.grid(axis="y", visible=False)
    fig.suptitle("The spread of each species' drops (log scale; the number is the median)", x=0.01, ha="left",
                 fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "species_rainclouds.png", S_SPECIES,
         "The same drops, one row per species: the shaded hill is how the values are spread (a smoothed histogram "
         "of the log values), the box the middle half, the dots the drops. The number is the median.")


def _hdr_levels(zz, masses):
    """Density levels enclosing the given probability masses (highest-density regions), increasing."""
    z = np.sort(zz.ravel())[::-1]
    c = np.cumsum(z) / z.sum()
    return sorted(float(z[min(np.searchsorted(c, m), len(z) - 1)]) for m in masses)


def fig_species_plane(ev):
    """Each species in the width-amplitude plane, and every species' 50 % and 90 % outline on one panel."""
    g = ev[(ev["width_s"] > 0) & (ev["depth_mv"] > 0)].copy()
    g["lw"], g["ld"] = np.log10(g["width_s"]), np.log10(g["depth_mv"])
    sps = species_present(g, least=10)
    fig = plt.figure(figsize=(14.0, 7.6))
    gs = fig.add_gridspec(2, 4, width_ratios=[1, 1, 1, 1.7])
    xl = (g["lw"].quantile(0.002) - 0.2, g["lw"].quantile(0.998) + 0.2)
    yl = (g["ld"].quantile(0.002) - 0.2, g["ld"].quantile(0.998) + 0.2)
    big = fig.add_subplot(gs[:, 3])
    xx, yy = np.meshgrid(np.linspace(*xl, 160), np.linspace(*yl, 160))
    for k, sp in enumerate(sps):
        ax = fig.add_subplot(gs[k // 3, k % 3])
        h = g[g["species"] == sp]
        ax.scatter(g["lw"], g["ld"], s=2, color=fs.GRID, linewidths=0)
        for d in present(h):
            hd = h[h["dataset"] == d]
            ax.scatter(hd["lw"], hd["ld"], s=5, color=fs.colour(d), alpha=0.65, linewidths=0, label=f"{d} ({len(hd)})")
        ax.set_title(f"{sp} ({len(h)})", loc="left", fontsize=9.5, color=fs.species_colour(sp))
        ax.legend(fontsize=6.5, loc="lower right", markerscale=2, frameon=False)
        ax.set_xlim(xl)
        ax.set_ylim(yl)
        log_ticks(ax, minor=False)
        kde = gaussian_kde(np.vstack([h["lw"], h["ld"]]))
        zz = kde(np.vstack([xx.ravel(), yy.ravel()])).reshape(xx.shape)
        lv = _hdr_levels(zz, (0.9, 0.5))
        big.contourf(xx, yy, zz, levels=[lv[1], zz.max()], colors=[fs.species_colour(sp)], alpha=0.22)
        big.contour(xx, yy, zz, levels=lv, colors=[fs.species_colour(sp)], linewidths=[0.8, 1.9])
        big.plot([], [], color=fs.species_colour(sp), lw=2, label=sp)
    if len(sps) < 6:
        ax = fig.add_subplot(gs[1, 2])
        for d in present(g):
            hd = g[g["dataset"] == d]
            qx, qy = hd["lw"].quantile([0.25, 0.5, 0.75]).to_numpy(), hd["ld"].quantile([0.25, 0.5, 0.75]).to_numpy()
            ax.errorbar(qx[1], qy[1], xerr=[[qx[1] - qx[0]], [qx[2] - qx[1]]], yerr=[[qy[1] - qy[0]],
                                                                                   [qy[2] - qy[1]]],
                        fmt="o", color=fs.colour(d), ms=6, capsize=2, lw=1.2)
            ax.text(qx[1], qy[1], f"  {d}", fontsize=7.5, color=fs.colour(d), va="bottom")
        ax.set_xlim(xl)
        ax.set_ylim(yl)
        log_ticks(ax, minor=False)
        ax.set_title("Each recording's median (bars: middle half)", loc="left", fontsize=9.5)
    big.set_xlim(xl)
    big.set_ylim(yl)
    log_ticks(big, minor=False)
    big.set_title("Where each species' drops sit: 50 % (filled) and 90 % outlines", loc="left", fontsize=9.5)
    big.legend(fontsize=8, loc="lower right")
    fig.supxlabel("Width: top to half recovery (s, log)", fontsize=9)
    fig.supylabel("Amplitude (mV, log)", fontsize=9)
    fig.suptitle("Width against amplitude, species by species", x=0.01, ha="left", fontsize=11)
    fig.tight_layout(rect=(0.01, 0.01, 1, 0.96))
    save(fig, "species_width_amplitude.png", S_SPECIES,
         "Width against amplitude. Small panels: one species each (grey: every other drop), coloured by recording. "
         "Large panel: the region holding the densest half (filled) and 90 % (thin line) of each species' drops.")


def fig_species_asymmetry(ev):
    """Fast down, slow up? Fall time against recovery time."""
    g = ev[(ev["recovery_s"] > 0) & (ev["fall_s"] > 0)].copy()
    g["ratio"] = g["recovery_s"] / g["fall_s"]
    sps = species_present(g)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13.0, 5.2), gridspec_kw={"width_ratios": [1.15, 1]})
    for sp in sps:
        h = g[g["species"] == sp]
        a1.scatter(h["fall_s"], h["recovery_s"], s=6, alpha=0.45, color=fs.species_colour(sp), linewidths=0,
                   label=f"{sp} ({len(h)})")
    lo = 0.7 * min(g["fall_s"].min(), g["recovery_s"].min())
    hi = 1.4 * max(g["fall_s"].max(), g["recovery_s"].max())
    for m, lab in ((1, "recovers as fast as it fell"), (0.1, "10x faster"), (10, "10x slower")):
        a1.plot([lo, hi], [lo * m, hi * m], color=fs.INK_2 if m == 1 else fs.MUTED, lw=1 if m == 1 else 0.7,
                ls="--" if m == 1 else ":")
        xm = np.sqrt(lo * hi) * (3 if m < 1 else 0.3 if m > 1 else 1)
        a1.text(xm, xm * m, lab, rotation=37, fontsize=7.5, color=fs.INK_2, ha="center", va="bottom")
    a1.set_xscale("log")
    a1.set_yscale("log")
    a1.set_xlim(lo, hi)
    a1.set_ylim(lo, hi)
    a1.set_xlabel("Fall time: top to bottom (s)")
    a1.set_ylabel("Recovery: bottom to half recovery (s)")
    a1.legend(fontsize=7.5, loc="upper left", markerscale=2)
    a1.set_title("Fall time against recovery time, every drop that half-recovered", loc="left")
    rng = np.random.default_rng(SEED)
    for k, sp in enumerate(sps):
        v = g.loc[g["species"] == sp, "ratio"].to_numpy(float)
        y0 = len(sps) - 1 - k
        q = np.percentile(v, [5, 25, 50, 75, 95])
        a2.scatter(v, y0 + rng.uniform(-0.25, 0.25, len(v)), s=4, alpha=0.3, color=fs.species_colour(sp),
                   linewidths=0)
        a2.add_patch(Rectangle((q[1], y0 - 0.3), q[3] - q[1], 0.6, facecolor="none", edgecolor=fs.INK, lw=1.0))
        a2.plot([q[2]] * 2, [y0 - 0.3, y0 + 0.3], color=fs.INK, lw=2)
        a2.text(q[4] * 1.3, y0, f"median {q[2]:.2g}x\n{np.mean(v > 1):.0%} slower up", fontsize=7.5, va="center",
                color=fs.INK_2)
    a2.axvline(1, color=fs.INK_2, lw=1, ls="--")
    a2.set_xscale("log")
    a2.set_yticks(range(len(sps)))
    a2.set_yticklabels(list(reversed(sps)))
    a2.set_xlabel("Recovery time ÷ fall time (1 = symmetric; above 1 = slower up than down)")
    a2.set_title("How lopsided each species' drops are", loc="left")
    a2.grid(axis="y", visible=False)
    a2.set_xlim(right=a2.get_xlim()[1] * 4)
    fig.tight_layout()
    save(fig, "species_fall_vs_recovery.png", S_SPECIES,
         "Is a drop fast down and slow up? Left: fall time against the time to climb half-way back. On the dashed "
         "line a drop recovers as fast as it fell. Right: the ratio, one row per species.")


def fig_species_shapes(ev, recs):
    """The typical drop of each species, every drop stretched to a common size first."""
    panels = [("fall", -1.0, 6.0, "Time ÷ the drop's own fall time (0 = its top, 1 = its bottom)"),
              ("width", -0.5, 3.0, "Time ÷ the drop's own width (0 = its top, 1 = half recovered)")]
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 4.8))
    npts = 141
    for ax, (unit, lo, hi, label) in zip(axes, panels):
        t = np.linspace(lo, hi, npts)
        for sp in species_present(ev):
            rows = []
            for r in ev[ev["species"] == sp].itertuples():
                if unit == "fall":
                    n = max(r.bottom_idx - r.top_idx, 1)
                elif np.isfinite(r.recovery_idx):
                    n = max(r.recovery_idx - r.top_idx, 1)
                else:
                    continue
                w = shape(recs, r.recording_id, r.top_idx, n, lo, hi, npts, depth=r.depth_mv)
                if w is not None:
                    rows.append(w)
            if len(rows) < 5:
                continue
            q = np.percentile(np.array(rows), [25, 50, 75], axis=0)
            c = fs.species_colour(sp)
            ax.fill_between(t, q[0], q[2], color=c, alpha=0.12, lw=0)
            ax.plot(t, q[1], color=c, lw=2.2, label=f"{sp} (n = {len(rows)})")
        ax.axhline(0, color=fs.MUTED, lw=0.8)
        ax.axhline(-1, color=fs.GRID, lw=0.8, ls="--")
        ax.axvline(0, color=fs.GRID, lw=0.8)
        ax.axvline(1, color=fs.GRID, lw=0.8)
        ax.set_xlabel(label)
        ax.set_ylabel("Trace ÷ the drop's own amplitude (0 = top, -1 = bottom)")
        ax.set_ylim(-1.5, 0.6)
        ax.legend(fontsize=7.5, loc="lower right")
    axes[0].set_title("The typical drop of each species, scaled by its fall time", loc="left")
    axes[1].set_title("...and scaled by its width", loc="left")
    fig.tight_layout()
    save(fig, "species_typical_shape.png", S_SPECIES,
         "Every drop stretched to the same size (its amplitude becomes 1) and the same duration (its fall time, "
         "left, or its width, right), then the median across each species. Bands: the middle half of the drops. "
         "Left, after 1 the line shows how far each species climbs back in the time it took to fall.")


def species_table(ev):
    rows = []
    for (sp, d), g in ev.groupby(["species", "dataset"]):
        row = {"species": sp, "dataset": d, "drops": len(g), "half_recovered": int(g["width_s"].notna().sum()),
               "long_tail": int(g["long_tail"].sum())}
        for col in ("depth_mv", "fall_s", "width_s", "recovery_s", "fall_rate_mv_s"):
            v = g[col].dropna()
            row.update({f"{col}_median": v.median(), f"{col}_q25": v.quantile(0.25), f"{col}_q75": v.quantile(0.75)})
        rows.append(row)
    t = pd.DataFrame(rows)
    t["order"] = t["dataset"].map(DATASET_ORDER.index)
    t.sort_values("order").drop(columns="order").round(4).to_csv(os.path.join(OUT, "species_summary.csv"),
                                                                 index=False)


# ── the adaptive shape map ───────────────────────────────────────────────────

def quadtree(px, py, box, level=0):
    """Leaves `{box, level, idx}`: `box` split in four while it holds more than LEAF_MAX points."""
    x0, x1, y0, y1 = box
    inside = np.flatnonzero((px >= x0) & (px < x1) & (py >= y0) & (py < y1))
    if len(inside) > LEAF_MAX and level < LEVEL_MAX:
        xm, ym = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
        sx, sy = px[inside], py[inside]
        out = []
        for b in ((x0, xm, y0, ym), (xm, x1, y0, ym), (x0, xm, ym, y1), (xm, x1, ym, y1)):
            out += [dict(leaf, idx=inside[leaf["idx"]]) for leaf in quadtree(sx, sy, b, level + 1)]
        return out
    return [{"box": box, "level": level, "idx": inside}]


def adaptive_cells(ev, recs, xcol, post):
    g = ev[(ev[xcol] > 0) & (ev["depth_mv"] > 0)].reset_index(drop=True)
    lx, ly = np.log10(g[xcol].to_numpy(float)), np.log10(g["depth_mv"].to_numpy(float))
    xlo, xhi = np.percentile(lx, [0.5, 99.5])
    ylo, yhi = np.percentile(ly, [0.5, 99.5])
    px, py = np.clip(lx, xlo, xhi), np.clip(ly, ylo, yhi)
    mx, my = 0.02 * (xhi - xlo), 0.02 * (yhi - ylo)
    root = (xlo - mx, xhi + mx, ylo - my, yhi + my)
    leaves = quadtree(px, py, root)
    rid, top, depth, f = (g["recording_id"].to_numpy(), g["top_idx"].to_numpy(), g["depth_mv"].to_numpy(float),
                          g["fs"].to_numpy(float))
    for leaf in leaves:
        x0, x1 = leaf["box"][:2]
        wc = 10 ** (0.5 * (x0 + x1))
        W = []
        for i in leaf["idx"]:
            w = shape(recs, int(rid[i]), int(top[i]), wc * f[i], -PRE_W, post, NPTS, depth=depth[i])
            if w is not None:
                W.append(w)
        leaf["wc"] = wc
        if len(W) >= MIN_GLYPH:
            W = np.array(W)
            leaf.update(W=W, medoid=W[int(np.argmin(cdist(W, W).sum(axis=1)))], median=np.median(W, axis=0),
                        q25=np.percentile(W, 25, axis=0), q75=np.percentile(W, 75, axis=0),
                        sd=W.std(axis=0, ddof=1))
    return g, px, py, root, leaves


def glyph_box(box):
    x0, x1, y0, y1 = box
    mx, my = 0.07 * (x1 - x0), 0.09 * (y1 - y0)
    return x0 + mx, x1 - mx, y0 + my, y1 - my


def glyph_xy(box, y):
    gx0, gx1, gy0, gy1 = glyph_box(box)
    X = np.linspace(gx0, gx1, len(y))
    Y = gy0 + (np.clip(y, Y_LO, Y_HI) - Y_LO) / (Y_HI - Y_LO) * (gy1 - gy0)
    return X, Y


def _map_axes(ax, root, xlabel):
    ax.set_xlim(root[0], root[1])
    ax.set_ylim(root[2], root[3])
    log_ticks(ax)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Amplitude: top to bottom (mV, log)")
    ax.grid(False)


def zoom_box(leaves, root):
    """The region of the finest cells, widened by a quarter each side: where the map is hardest to read whole."""
    fine = [lf["box"] for lf in leaves if lf["level"] == max(l2["level"] for l2 in leaves)]
    x0, x1 = min(b[0] for b in fine), max(b[1] for b in fine)
    y0, y1 = min(b[2] for b in fine), max(b[3] for b in fine)
    mx, my = 0.25 * (x1 - x0), 0.25 * (y1 - y0)
    return max(root[0], x0 - mx), min(root[1], x1 + mx), max(root[2], y0 - my), min(root[3], y1 + my)


def fig_map_medoids(g, px, py, root, leaves, xlabel, stem, post, zoom=False):
    rel = np.concatenate([lf["sd"] for lf in leaves if "sd" in lf])
    norm = Normalize(0.0, float(np.round(np.percentile(rel, 90), 2)))
    view = zoom_box(leaves, root) if zoom else root
    lift = int(np.floor(np.log2((root[1] - root[0]) / (view[1] - view[0])))) if zoom else 0
    fig, ax = plt.subplots(figsize=(15.0, 11.0))
    for lf in leaves:
        x0, x1, y0, y1 = lf["box"]
        if x1 <= view[0] or x0 >= view[1] or y1 <= view[2] or y0 >= view[3]:
            continue
        lf = dict(lf, level=lf["level"] - lift)
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, edgecolor="#d3d2cd", lw=0.6, zorder=1))
        if "W" not in lf:
            ax.scatter(px[lf["idx"]], py[lf["idx"]], s=5, color=fs.MUTED, linewidths=0, zorder=2)
            continue
        X, Ya = glyph_xy(lf["box"], lf["q25"])
        _, Yb = glyph_xy(lf["box"], lf["q75"])
        ax.fill_between(X, Ya, Yb, color="#e7e6e1", lw=0, zorder=2)
        X0, Y0 = glyph_xy(lf["box"], np.zeros(2))
        ax.plot(X0, Y0, color="#cfcec8", lw=0.5, zorder=2)
        X, Y = glyph_xy(lf["box"], lf["medoid"])
        pts = np.column_stack([X, Y]).reshape(-1, 1, 2)
        lc = LineCollection(np.concatenate([pts[:-1], pts[1:]], axis=1), cmap=VAR_CMAP, norm=norm,
                            linewidths=max(0.7, 2.3 - 0.28 * lf["level"]), zorder=3, capstyle="round")
        lc.set_array(0.5 * (lf["sd"][:-1] + lf["sd"][1:]))
        ax.add_collection(lc)
        ax.text(x1 - 0.03 * (x1 - x0), y1 - 0.04 * (y1 - y0), f"{len(lf['idx'])}", ha="right", va="top",
                fontsize=max(4.0, 8.0 - 0.8 * lf["level"]), color=fs.INK_2, zorder=4, clip_on=True)
    _map_axes(ax, view, xlabel)
    cax = fig.add_axes([0.915, 0.3, 0.011, 0.4])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=VAR_CMAP), cax=cax, extend="max")
    cb.set_label("how much the cell's drops differ at that moment\n(SD, in units of each drop's own amplitude)",
                 fontsize=8)
    n_glyph = sum("W" in lf for lf in leaves)
    if zoom:
        ax.set_title(f"Close-up of the crowded middle of the {xlabel.split(':')[0].lower()}-amplitude map (its finest "
                     f"cells)", loc="left", fontsize=10.5)
        save(fig, f"map_{stem}_medoids_zoom.png", S_MAP,
             "The same map, zoomed on the region of its finest cells, where the glyphs are too small to read on the "
             "whole map.", dpi=200)
        return norm
    ax.set_title(f"The drop shape across the {xlabel.split(':')[0].lower()}-amplitude plane: {len(g):,} drops in "
                 f"{len(leaves)} cells, finer where drops crowd ({n_glyph} with a waveform)", loc="left",
                 fontsize=10.5)
    save(fig, f"map_{stem}_medoids.png", S_MAP,
         f"The plane cut into cells that split in four while they hold more than {LEAF_MAX} drops, so the grid is "
         f"finest where drops crowd. Each cell with at least {MIN_GLYPH} drops shows its medoid (its most typical "
         f"real drop), each drop first divided by its own amplitude (the glyph's height is the same everywhere; "
         f"its place on the map gives its size). The glyph runs from half a cell-width before the top to {post:g} "
         f"after; the thin line is the level of the top. Colour along the medoid: blue where the cell's drops "
         f"agree, red where they differ. Grey band: their middle half. Grey dots: cells too sparse for a waveform. "
         f"Drops beyond the 0.5th / 99.5th percentile sit on the edge cells.", dpi=200)
    return norm


def fig_map_heatmaps(g, px, py, root, leaves, xlabel, stem, post):
    fig, ax = plt.subplots(figsize=(15.0, 11.0))
    nt, ny = 50, 36
    for lf in leaves:
        x0, x1, y0, y1 = lf["box"]
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, edgecolor="#d3d2cd", lw=0.6, zorder=1))
        if "W" not in lf:
            ax.scatter(px[lf["idx"]], py[lf["idx"]], s=5, color=fs.MUTED, linewidths=0, zorder=2)
            continue
        W = lf["W"]          # samples beyond the glyph's range fall outside the histogram, not onto its edge
        cols = np.tile(np.linspace(0, nt - 1e-9, W.shape[1]), W.shape[0])
        H, _, _ = np.histogram2d(W.ravel(), cols, bins=[ny, nt], range=[[Y_LO, Y_HI], [0, nt]])
        H = H / np.maximum(H.sum(axis=0, keepdims=True), 1)
        gx0, gx1, gy0, gy1 = glyph_box(lf["box"])
        ax.imshow(H, extent=(gx0, gx1, gy0, gy1), origin="lower", aspect="auto", cmap=DENSITY_CMAP,
                  norm=PowerNorm(0.5, vmin=0, vmax=max(float(H.max()), 1e-9)), interpolation="bilinear", zorder=2)
        X, Y = glyph_xy(lf["box"], lf["median"])
        ax.plot(X, Y, color=ORANGE, lw=max(0.5, 1.3 - 0.15 * lf["level"]), zorder=3)
        ax.text(x1 - 0.03 * (x1 - x0), y1 - 0.04 * (y1 - y0), f"{len(lf['idx'])}", ha="right", va="top",
                fontsize=max(4.0, 8.0 - 0.8 * lf["level"]), color=fs.INK_2, zorder=4, clip_on=True)
    _map_axes(ax, root, xlabel)
    ax.set_title(f"Every drop's waveform at once: the density of the {len(g):,} traces in each cell", loc="left",
                 fontsize=10.5)
    save(fig, f"map_{stem}_heatmaps.png", S_MAP,
         "The same cells, but each glyph is a heat map of ALL the cell's drops overlaid (dark blue where many "
         "traces pass, white where none do), each time-column scaled to its own total; orange: the cell's median "
         "trace. A sharp dark line means the cell's drops share one shape; a smear means they differ.", dpi=200)


def fig_map_cells(g, px, py, root, leaves, xlabel, stem):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(16.0, 7.2))
    for sp in SPECIES_ORDER:
        m = (g["species"] == sp).to_numpy()
        a1.scatter(px[m], py[m], s=4, color=fs.species_colour(sp), alpha=0.55, linewidths=0, label=f"{sp} ({m.sum()})")
    for lf in leaves:
        x0, x1, y0, y1 = lf["box"]
        a1.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, edgecolor=fs.INK_2, lw=0.4, zorder=3))
        if not len(lf["idx"]):
            continue
        sp = g["species"].to_numpy()[lf["idx"]]
        vals, counts = np.unique(sp, return_counts=True)
        top = vals[int(np.argmax(counts))]
        purity = counts.max() / counts.sum()
        a2.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor=to_rgba(fs.species_colour(top),
                                                                            0.15 + 0.75 * purity),
                               edgecolor="white", lw=0.6))
        if lf["level"] <= 4:
            a2.text(0.5 * (x0 + x1), 0.5 * (y0 + y1), f"{len(lf['idx'])}", ha="center", va="center",
                    fontsize=max(4.0, 8.0 - 0.8 * lf["level"]), color="white" if purity > 0.6 else fs.INK)
    for ax in (a1, a2):
        _map_axes(ax, root, xlabel)
    a1.legend(fontsize=7.5, loc="lower right", markerscale=2.5)
    a1.set_title(f"The cells of the map over the drops ({len(leaves)} cells)", loc="left")
    a2.set_title("Each cell coloured by its most common species (paler: more mixed)", loc="left")
    fig.tight_layout()
    save(fig, f"map_{stem}_cells.png", S_MAP,
         "Left: the drops and the cells of the adaptive grid. Right: each cell coloured by the species most of its "
         "drops come from, pale where the species mix; the number is its drop count.")


# ── the sequences ────────────────────────────────────────────────────────────

def sequence_list(conn, recs):
    ids = list(CH14_SEQUENCES) + list(HAND_SEQUENCES)
    marks = ",".join("?" * len(ids))
    q48 = set(json.loads(conn.execute("SELECT filters_json FROM review_queues WHERE id = 48").fetchone()[0])
              ["sequence_ids"])
    out = []
    for sid, origin, kind, rid, a, b, ann in conn.execute(
            f"SELECT id, origin, source_kind, recording_id, start_idx, end_idx, annotation_id FROM sequences "
            f"WHERE id IN ({marks})", ids):
        rec = recs[int(rid)]
        verdict = note = None
        if ann:
            got = conn.execute("SELECT verdict, note, tag FROM annotations WHERE id = ?", (int(ann),)).fetchone()
            if got:
                verdict = got[0]
                note = " · ".join(str(v) for v in got[1:] if v)
        out.append({"sequence_id": int(sid), "group": "hand-labelled" if origin == "human" else f"CH14 {kind}",
                    "recording_id": int(rid), "dataset": fs.name(rec["file"]), "channel_1based": rec["channel"] + 1,
                    "fs": rec["fs"], "start_idx": int(a), "end_idx": int(b),
                    "duration_h": (int(b) - int(a)) / rec["fs"] / 3600.0, "hand_verdict": verdict,
                    "hand_note": note, "in_queue_48": int(sid) in q48})
    order = {sid: k for k, sid in enumerate(ids)}
    return sorted(out, key=lambda m: order[m["sequence_id"]])


def judged_drops(conn, ev):
    """`{recording: (tops, bottoms, verdicts)}`: every drop with a drop-level verdict - today's candidate-event
    detections, and the accepted catalogue and queue drops of the event table."""
    rows = conn.execute(
        "SELECT r.recording_id, d.meta_json, "
        "(SELECT a.verdict FROM adjudications a WHERE a.detection_id = d.id ORDER BY a.id DESC LIMIT 1) "
        "FROM detections d JOIN runs r ON r.id = d.run_id JOIN configs c ON c.id = r.config_id "
        "WHERE (c.config_json LIKE '%candidate-events%' OR c.config_json LIKE '%ch14-small-drops%') "
        "AND d.id IN (SELECT detection_id FROM adjudications)").fetchall()
    out = {}
    for rid, meta, v in rows:
        m = json.loads(meta)
        out.setdefault(int(rid), []).append((int(m["top_idx"]), int(m["bottom_idx"]), v))
    for r in ev.itertuples():
        out.setdefault(int(r.recording_id), []).append((int(r.top_idx), int(r.bottom_idx), "interesting"))
    return {rid: (np.array([t for t, _, _ in v]), np.array([b for _, b, _ in v]), np.array([x for _, _, x in v]))
            for rid, v in out.items()}


def status_of(judged, rid, top, bottom):
    got = judged.get(rid)
    if got is None:
        return "unjudged"
    tops, bottoms, verdicts = got
    hit = verdicts[np.minimum(bottoms, bottom) > np.maximum(tops, top)]
    if not len(hit):
        return "unjudged"
    if any(v in ACCEPTED for v in hit):
        return "accepted"
    if any(v in REJECTED for v in hit):
        return "rejected"
    return "unsure"


def sequence_drops(recs, rid, a, b):
    """Every whole-drop event of [a, b) at least MIN_SIGMAS x its local noise with a core of at least
    MIN_CORE_SAMPLES, in recording frame (no relative floor)."""
    rec, x = recs[rid], channel(recs, rid)
    f, k, n = rec["fs"], to_mv(rec["units"]), len(x)
    pad = int(SEQ_CONTEXT_S * f)
    lo, hi = max(0, a - pad), min(n, b + pad)
    rec_hi = min(n, hi + int(WD.RECOVERY_MAX_S * f))
    raw = np.asarray(x[lo:rec_hi], dtype=float) * k
    if not np.all(np.isfinite(raw)):
        raw = np.where(np.isfinite(raw), raw, np.nanmedian(raw))
    sigma = WD.noise_sigma(raw[a - lo:b - lo])
    found = WD.candidate_falls(raw[:hi - lo], f, sigma)
    h = int(NOISE_HALF_S * f)
    kept, local = [], []
    for fl in found:
        s_loc = WD.noise_sigma(raw[max(0, fl[0] - h):fl[0] + h])
        if fl[2] >= MIN_SIGMAS * s_loc:
            kept.append(fl)
            local.append(s_loc)
    out = []
    a_l, b_l = a - lo, b - lo
    for e, s_loc in zip(WD.with_recoveries(raw, f, kept), local):
        top, bottom = e["top"], e["bottom"]
        i, j = max(top, a_l), min(bottom, b_l)
        inside = (j > i and raw[i] - raw[i:j + 1].min() >= 0.5 * e["depth_mv"]) or \
            a_l <= WD._steepest(raw, top, bottom, f) < b_l
        end = e["recovery"] if np.isfinite(e["recovery"]) else bottom
        if not inside or end - top < MIN_CORE_SAMPLES:
            continue
        out.append({"top_idx": top + lo, "bottom_idx": bottom + lo,
                    "recovery_idx": e["recovery"] + lo if np.isfinite(e["recovery"]) else np.nan,
                    "depth_mv": e["depth_mv"], "fall_s": e["fall_s"], "width_s": e["width_s"],
                    "recovery_s": e["half_recovery_s"], "steep_s": e["steep_s"], "long_tail": e["long_tail"],
                    "sigma_mv": s_loc, "depth_sigmas": e["depth_mv"] / s_loc if s_loc else np.nan})
    return out


def build_sequence_events(conn, recs, ev):
    metas = sequence_list(conn, recs)
    judged = judged_drops(conn, ev)
    rows = []
    for m in metas:
        t0 = time.time()
        drops = sequence_drops(recs, m["recording_id"], m["start_idx"], m["end_idx"])
        for d in drops:
            d.update(sequence_id=m["sequence_id"], recording_id=m["recording_id"], fs=m["fs"],
                     status=status_of(judged, m["recording_id"], d["top_idx"], d["bottom_idx"]))
        rows += drops
        print(f"  sequence {m['sequence_id']} {m['dataset']} CH{m['channel_1based']} {m['duration_h']:.1f} h: "
              f"{len(drops)} drops ({time.time() - t0:.1f} s)", flush=True)
    sev = pd.DataFrame(rows)
    sev["t_s"] = sev["top_idx"] / sev["fs"]
    sev["fall_rate_mv_s"] = sev["depth_mv"] / sev["fall_s"].clip(lower=1.0 / sev["fs"])
    kept = sev["status"] != "rejected"
    sev["interval_s"] = np.nan
    sev.loc[kept, "interval_s"] = sev[kept].groupby("sequence_id")["t_s"].diff()
    sev.to_csv(os.path.join(OUT, "sequence_events.csv"), index=False)
    pd.DataFrame(metas).to_csv(os.path.join(OUT, "sequences.csv"), index=False)
    return metas, sev


def load_sequence_events():
    sev = pd.read_csv(os.path.join(OUT, "sequence_events.csv"))
    sev["long_tail"] = as_bool(sev["long_tail"])
    metas = pd.read_csv(os.path.join(OUT, "sequences.csv")).to_dict("records")
    return metas, sev


def envelope(t, y, bins=3000):
    """`(t, mean, low, high)` per bin for a long trace, or the trace itself (low, high None)."""
    if len(y) <= 3 * bins:
        return t, y, None, None
    k = len(y) // bins
    m = k * bins
    yy = y[:m].reshape(bins, k)
    return t[:m].reshape(bins, k).mean(axis=1), yy.mean(axis=1), yy.min(axis=1), yy.max(axis=1)


def time_unit(duration_h):
    return (3600.0, "hours") if duration_h >= 3 else (60.0, "minutes")


def seq_label(m):
    return f"seq {m['sequence_id']} · {m['dataset']} CH{m['channel_1based']}"


def draw_trace(ax, m, d, recs, unit_s, unit_name, colour_by=None, lw_fall=1.6):
    """The sequence's trace in mV with each drop's fall drawn over it in one colour (or by `colour_by`, an array of
    colours for the drops of `d`). Every drop is drawn alike, judged or not (the researcher, 24 Nov)."""
    rid, a, b, f = m["recording_id"], int(m["start_idx"]), int(m["end_idx"]), float(m["fs"])
    x = channel(recs, rid)
    pad = max(int(0.02 * (b - a)), int(20 * f))
    a0, b0 = max(0, a - pad), min(len(x), b + pad)
    y = np.asarray(x[a0:b0], dtype=float) * to_mv(recs[rid]["units"])
    t = (np.arange(a0, b0) - a) / f / unit_s
    tt, mean, lo, hi = envelope(t, y)
    if lo is not None:
        ax.fill_between(tt, lo, hi, color="#c9c8c2", lw=0, zorder=1)
        ax.plot(tt, mean, color=fs.INK_2, lw=0.4, zorder=2)
    else:
        ax.plot(t, y, color=fs.INK_2, lw=0.6, zorder=2)
    for edge in (a, b):
        ax.axvline((edge - a) / f / unit_s, color=fs.MUTED, lw=0.8, ls=(0, (3, 3)))
    segs, cols = [], []
    for k, r in enumerate(d.itertuples()):
        i, j = int(r.top_idx) - a0, int(r.bottom_idx) - a0
        if not (0 <= i < len(y) and 0 <= j < len(y)):
            continue
        seg_t = t[i:j + 1]
        seg_y = y[i:j + 1]
        if len(seg_t) > 400:
            step = len(seg_t) // 400 + 1
            seg_t, seg_y = seg_t[::step], seg_y[::step]
        segs.append(np.column_stack([seg_t, seg_y]))
        cols.append(colour_by[k] if colour_by is not None else BLUE)
    if segs:
        ax.add_collection(LineCollection(segs, colors=cols, linewidths=lw_fall, zorder=3))
    ax.set_xlim(t[0], t[-1])
    ax.set_ylabel("mV")
    ax.set_xlabel(f"{unit_name.capitalize()} from the start of the sequence")
    return y, a0


def seq_trends(d):
    out = {}
    t = d["t_s"].to_numpy()
    for col, _, short in SEQ_MEASURES:
        out[col] = kendall_trend(t, d[col].to_numpy(dtype=float))
    return out


def running_geomean(v, k):
    """The rolling geometric mean of k values: it runs smoothly between interleaved bands, where a running median
    would jump from one band to the other."""
    return 10 ** pd.Series(np.log10(v)).rolling(k, center=True, min_periods=max(3, k // 3)).mean().to_numpy()


def events_only(d_all):
    """The drops treated as events: every drop found, judged or not, less the few judged noise (the researcher,
    24 Nov: "assume all events are judged for now")."""
    return d_all[d_all["status"] != "rejected"].reset_index(drop=True)


def fig_sequence(m, d_all, recs):
    sid = m["sequence_id"]
    d = events_only(d_all)
    unit_s, unit_name = time_unit(m["duration_h"])
    fig = plt.figure(figsize=(14.0, 10.2))
    gs = fig.add_gridspec(3, 3, height_ratios=[1.35, 1, 1], hspace=0.55, wspace=0.26)
    ax = fig.add_subplot(gs[0, :])
    draw_trace(ax, m, d, recs, unit_s, unit_name)
    trends = seq_trends(d)
    tt = (d["t_s"].to_numpy() - m["start_idx"] / m["fs"]) / unit_s
    k = int(max(5, min(41, (len(d) // 12) * 2 + 1)))
    for n, (col, label, short) in enumerate(SEQ_MEASURES):
        a = fig.add_subplot(gs[1 + n // 3, n % 3])
        v = d[col].to_numpy(dtype=float)
        ok = np.isfinite(v) & (v > 0)
        a.scatter(tt[ok], v[ok], s=9 if len(d) < 200 else 5, color=BLUE, alpha=0.7, linewidths=0, zorder=3)
        if ok.sum() >= 10:
            a.plot(tt[ok], running_geomean(v[ok], k), color=fs.INK, lw=1.8, zorder=4)
        if ok.any():
            a.set_yscale("log")
        a.set_ylabel(label, fontsize=8)
        a.set_xlabel(f"{unit_name.capitalize()}", fontsize=8)
        tr = trends[col]
        if tr["tau"] is None:
            a.set_title(f"{short}: {tr['note'].split('·')[-1].strip()}", loc="left", fontsize=8.5)
        else:
            a.set_title(f"{short}: Kendall τ {tr['tau']:+.2f}, p {fmt_p(tr['p'])} (n {tr['n']})", loc="left",
                        fontsize=8.5)
    a = fig.add_subplot(gs[2, 2])
    for c, (col, label, short) in zip(fs.CATEGORICAL, SEQ_MEASURES):
        v = d[col].to_numpy(dtype=float)
        ok = np.isfinite(v) & (v > 0)
        if ok.sum() < 3:
            continue
        rel = v[ok] / np.exp(np.mean(np.log(v[ok])))
        if ok.sum() >= 10:
            a.plot(tt[ok], running_geomean(rel, k), color=c, lw=1.8, label=short)
        else:
            a.plot(tt[ok], rel, color=c, lw=1.2, marker="o", ms=3, label=short)
    a.axhline(1, color=fs.MUTED, lw=0.8)
    a.set_yscale("log", base=2)
    a.set_xlabel(unit_name.capitalize(), fontsize=8)
    a.set_ylabel("÷ its typical value along the sequence", fontsize=8)
    a.set_title("All five, each ÷ its typical value" + (f" (rolling geometric mean of {k})" if len(d) >= 10 else ""),
                loc="left", fontsize=8.5)
    if a.get_legend_handles_labels()[0]:
        a.legend(fontsize=6.5, ncol=2, loc="best")
    hand = ""
    if m["group"] == "hand-labelled":
        hand = f" · hand-labelled, your verdict: {m['hand_verdict']}"
        if isinstance(m.get("hand_note"), str) and m["hand_note"]:
            hand += f" · “{m['hand_note'][:80]}”"
    fig.suptitle(f"{seq_label(m)} · {m['duration_h']:.1f} h from {m['start_idx'] / m['fs'] / 3600:.1f} h · "
                 f"{len(d)} drops{hand}", x=0.01, y=0.995, ha="left", fontsize=11)
    fig.text(0.01, 0.955, f"Blue lines on the trace: each drop's fall (top to bottom) found by the whole-drop rule "
             f"({MIN_SIGMAS:g}x local noise, core at least {MIN_CORE_SAMPLES} samples, no relative floor). Below: "
             f"each measure per drop; black line: its rolling geometric mean (which runs between interleaved bands "
             f"rather than jumping from one to the other).", fontsize=7.5, color=fs.INK_2, ha="left")
    name = f"sequences/seq_{sid:03d}_{m['dataset']}_CH{m['channel_1based']:02d}.png"
    save(fig, name, S_SEQ,
         f"{seq_label(m)}, {m['duration_h']:.1f} h, {len(d)} drops. Top: the trace with each drop's fall drawn in "
         f"blue. Then depth, fall time, width, fall rate and the interval since the previous drop along the sequence, "
         f"with Kendall's tau (a value near +1 or -1 is a steady rise or fall over time; near 0, no trend). Last "
         f"panel: all five measures on one scale.", dpi=150)
    row = {"sequence_id": sid, "drops": len(d)}
    for col, _, short in SEQ_MEASURES:
        row[f"tau_{short.replace(' ', '_')}"] = trends[col]["tau"]
        row[f"p_{short.replace(' ', '_')}"] = trends[col]["p"]
    return row


def fig_sequences_overview(metas, sev):
    """Every sequence as one barcode: each drop a tick, coloured by its depth against the sequence's median."""
    fig = plt.figure(figsize=(15.5, 0.27 * len(metas) + 2.6))
    gs = fig.add_gridspec(2, 2, width_ratios=[3.2, 1], height_ratios=[1, 0.018], hspace=0.12, wspace=0.3)
    ax = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1], sharey=ax)     # the same rows as the barcodes
    cax = fig.add_subplot(gs[1, 0])
    norm = Normalize(-2, 2)
    cmap = plt.get_cmap("coolwarm")
    labels = []
    for k, m in enumerate(metas):
        d = sev[(sev["sequence_id"] == m["sequence_id"]) & (sev["status"] != "rejected")]
        y = len(metas) - 1 - k
        labels.append(f"{m['sequence_id']} {m['dataset']} CH{m['channel_1based']}"
                      f"{'  (hand)' if m['group'] == 'hand-labelled' else ''}")
        if not len(d):
            continue
        frac = (d["t_s"] - m["start_idx"] / m["fs"]) / max(1e-9, (m["end_idx"] - m["start_idx"]) / m["fs"])
        rel = np.log2(d["depth_mv"] / d["depth_mv"].median())
        ax.scatter(frac, np.full(len(d), y), c=cmap(norm(rel)), marker="|", s=90, linewidths=1.1)
        ax.text(1.01, y, f"{len(d)} drops · {m['duration_h']:.1f} h", va="center", fontsize=7, color=fs.INK_2,
                transform=ax.get_yaxis_transform())
        tr = seq_trends(d.reset_index(drop=True))
        for j, col in enumerate(("depth_mv", "width_s", "interval_s")):
            res = tr[col]
            if res["tau"] is not None:
                sig = res["p"] < 0.05
                ax2.scatter(res["tau"], y + (j - 1) * 0.22, color=fs.CATEGORICAL[j], s=22 if sig else 10,
                            alpha=1 if sig else 0.4, linewidths=0)
    ax.set_yticks(range(len(metas)))
    ax.set_yticklabels(list(reversed(labels)), fontsize=7)
    ax.set_xlim(-0.01, 1.0)
    ax.set_xlabel("Fraction of the sequence's duration")
    ax.grid(axis="y", visible=False)
    ax.set_title("Every sequence as a barcode: each tick a drop, red deeper and blue shallower than the sequence's "
                 "median", loc="left", fontsize=9.5)
    sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    cb = fig.colorbar(sm, cax=cax, orientation="horizontal")
    cb.set_ticks([-2, -1, 0, 1, 2])
    cb.set_ticklabels(["¼x", "½x", "median", "2x", "4x"])
    cb.set_label("depth against the sequence's median depth", fontsize=8)
    ax.set_ylim(-0.7, len(metas) - 0.3)
    ax2.axvline(0, color=fs.MUTED, lw=0.8)
    ax2.set_xlim(-1, 1)
    ax2.tick_params(axis="y", labelleft=False)
    ax2.grid(axis="y", visible=False)
    for j, name in enumerate(("depth", "width", "interval")):
        ax2.scatter([], [], color=fs.CATEGORICAL[j], s=22, label=name)
    ax2.legend(fontsize=7.5, loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=3, frameon=False)
    ax2.set_xlabel("Kendall's tau against time (big dot: p < 0.05)")
    ax2.set_title("Trend along each sequence", loc="left", fontsize=9.5, pad=18)
    save(fig, "sequences_overview.png", S_SEQ,
         "All 41 sequences at a glance. Left: each row a sequence stretched to the same length, each tick one drop "
         "coloured by its depth against that sequence's median (red deeper, blue shallower). Right: whether depth, "
         "width and the interval rise (tau > 0) or fall (tau < 0) along each sequence.", dpi=170)


def ch14_windows_sheet(conn, recs, ev):
    """The 32 interesting 10-min windows on M2_aug CH14 (queue 49), one small panel each."""
    rows = conn.execute("SELECT id, recording_id, start_idx, end_idx FROM sequences WHERE source_kind = "
                        "'interesting_10min_window' AND recording_id = 14 ORDER BY start_idx").fetchall()
    if not rows:
        return
    n = len(rows)
    nc = 6
    nr = int(np.ceil(n / nc))
    fig, axes = plt.subplots(nr, nc, figsize=(16.0, 2.2 * nr), squeeze=False)
    for ax, (sid, rid, a, b) in zip(axes.ravel(), rows):
        m = {"recording_id": rid, "start_idx": a, "end_idx": b, "fs": recs[rid]["fs"]}
        drops = pd.DataFrame(sequence_drops(recs, rid, a, b))
        draw_trace(ax, m, drops if len(drops) else pd.DataFrame(columns=["top_idx", "bottom_idx"]), recs,
                   60.0, "minutes", lw_fall=2.0)
        ax.set_title(f"seq {sid} · {a / 3600:.1f} h · {len(drops)} drops", loc="left", fontsize=7.5)
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.tick_params(labelsize=6)
    for ax in axes.ravel()[n:]:
        ax.axis("off")
    fig.suptitle("M2_aug CH14: the interesting 10-minute windows of queue 49, each drop's fall in blue", x=0.01,
                 ha="left", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    save(fig, "sequences/ch14_m2aug_windows.png", S_SEQ,
         "The 32 interesting 10-minute windows on M2_aug CH14 (queue 49) as a contact sheet: too short for trends "
         "one by one, so drawn together. x: minutes from the window's start.", dpi=140)


# ── two kinds of drop ────────────────────────────────────────────────────────

LOCAL_N = 21               # a drop's local level: the geometric mean of the LOCAL_N drops round it


def local_relative(v):
    """`(z, base)`: log10 of each value against the geometric mean of the LOCAL_N values round it, so a slow drift
    (the CH14 train deepens two-fold over 90 h) does not decide what counts as big."""
    lv = np.log10(np.asarray(v, dtype=float))
    base = pd.Series(lv).rolling(LOCAL_N, center=True, min_periods=5).mean().to_numpy()
    return lv - base, base


def two_groups(z):
    """`(labels, cut, note)` for log values `z`: 1 at or above the cut, 0 below. The cut is where a two-component
    Gaussian mixture's posterior passes from its lower component to its upper one, between their means (the median
    when that leaves under 10 % on one side)."""
    from sklearn.mixture import GaussianMixture
    v = np.asarray(z, dtype=float).reshape(-1, 1)
    g1 = GaussianMixture(1, random_state=SEED).fit(v)
    g2 = GaussianMixture(2, n_init=5, random_state=SEED).fit(v)
    dbic = g1.bic(v) - g2.bic(v)
    lo_c, hi_c = np.argsort(g2.means_[:, 0])
    grid = np.linspace(g2.means_[lo_c, 0], g2.means_[hi_c, 0], 401).reshape(-1, 1)
    up = np.flatnonzero(g2.predict_proba(grid)[:, hi_c] >= 0.5)
    cut = float(grid[up[0], 0]) if len(up) else float(np.median(v))
    lab = (v[:, 0] >= cut).astype(int)
    minority = min(lab.mean(), 1 - lab.mean())
    if minority < 0.10:
        cut = float(np.median(v))
        lab = (v[:, 0] >= cut).astype(int)
        return lab, cut, f"median split (a two-group fit left {minority:.0%} on one side; ΔBIC {dbic:+.0f})"
    verdict = ("two groups fit clearly better than one" if dbic > 10 else
               "two groups fit a little better" if dbic > 0 else "one group fits as well: a continuum cut in two")
    return lab, cut, f"{verdict} (ΔBIC {dbic:+.0f})"


def rel_ticks(ax, x=True, y=True):
    """Ticks for axes holding log10 ratios, labelled as factors."""
    for on, lim, setter, labeller in ((x, ax.get_xlim, ax.set_xticks, ax.set_xticklabels),
                                      (y, ax.get_ylim, ax.set_yticks, ax.set_yticklabels)):
        if not on:
            continue
        lo, hi = lim()
        steps = (0.125, 0.25, 0.5, 1, 2, 4, 8) if hi - lo < 1.6 else (0.0625, 0.25, 1, 4, 16)
        t = [np.log10(f) for f in steps if lo <= np.log10(f) <= hi]
        setter(t)
        labeller([f"×{10 ** v:g}" for v in t])


def switch_test(lab, block=None):
    """How often neighbours differ in kind, and P(kind 1 | previous kind), against shuffles of the order (all of it,
    or only within blocks of `block` drops, which keeps slow drifts)."""
    rng = np.random.default_rng(SEED)
    n = len(lab)
    keys = (np.arange(n) // block).astype(float) if block else np.zeros(n)

    def stats(p):
        prev, nxt = p[:-1], p[1:]
        return (np.mean(prev != nxt), nxt[prev == 1].mean() if (prev == 1).any() else np.nan,
                nxt[prev == 0].mean() if (prev == 0).any() else np.nan)
    obs = stats(lab)
    null = np.array([stats(lab[np.argsort(keys + rng.random(n), kind="stable")]) for _ in range(SHUFFLES)])
    return {"switch": obs[0], "p11": obs[1], "p01": obs[2], "null": null,
            "p_more_switching": (np.sum(null[:, 0] >= obs[0]) + 1) / (SHUFFLES + 1),
            "p_less_switching": (np.sum(null[:, 0] <= obs[0]) + 1) / (SHUFFLES + 1)}


def _transition_panel(ax, lab, names):
    glob, loc = switch_test(lab), switch_test(lab, BLOCK)
    xs = np.arange(2)
    obs = [glob["p01"], glob["p11"]]
    ax.bar(xs, obs, width=0.5, color=[TYPE_COLOURS[0], TYPE_COLOURS[1]], alpha=0.85)
    for res, dx, mk, lab_ in ((glob, -0.12, "s", "shuffled (whole order)"),
                              (loc, 0.12, "D", f"shuffled within blocks of {BLOCK}")):
        for j, col in enumerate((2, 1)):
            q = np.nanpercentile(res["null"][:, col], [2.5, 50, 97.5])
            ax.errorbar(j + dx, q[1], yerr=[[q[1] - q[0]], [q[2] - q[1]]], fmt=mk, color=fs.INK, ms=4, capsize=3,
                        label=lab_ if j == 0 else None)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"after a {names[0]}", f"after a {names[1]}"], fontsize=8)
    ax.set_ylabel(f"chance the next drop is {names[1]}", fontsize=8)
    ax.set_ylim(0, 1)
    ax.legend(fontsize=6.5, loc="upper left")
    verdict = ("alternate more than chance" if loc["p_more_switching"] < 0.05 else
               "clump more than chance" if loc["p_less_switching"] < 0.05 else "no order beyond chance")
    ax.set_title(f"What follows what: switch {glob['switch']:.0%} vs {np.mean(glob['null'][:, 0]):.0%} shuffled\n"
                 f"(local shuffle p {fmt_p(min(loc['p_more_switching'], loc['p_less_switching']))}: {verdict})",
                 loc="left", fontsize=8.5)
    return glob, loc


def _return_panel(ax, z, lab, cut, label):
    for j in (0, 1):
        mm = lab[:-1] == j
        ax.scatter(z[:-1][mm], z[1:][mm], s=8, color=TYPE_COLOURS[j], alpha=0.6, linewidths=0)
    lo, hi = float(np.nanmin(z)) - 0.03, float(np.nanmax(z)) + 0.03
    ax.plot([lo, hi], [lo, hi], color=fs.MUTED, lw=0.8, ls="--")
    ax.axvline(cut, color=fs.INK_2, lw=0.8, ls=":")
    ax.axhline(cut, color=fs.INK_2, lw=0.8, ls=":")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    rel_ticks(ax)
    rho = spearmanr(z[:-1], z[1:])
    ax.set_xlabel(f"{label} of a drop ÷ its local level", fontsize=8)
    ax.set_ylabel(f"{label} of the next ÷ its local level", fontsize=8)
    ax.set_title(f"Each drop against the next (Spearman ρ {rho.statistic:+.2f});\ntaking turns fills the top-left "
                 f"and bottom-right corners", loc="left", fontsize=8.5)


def _waveform_panel(ax, d, lab, recs, names, width_s):
    lo, hi = -0.6 * width_s, 3.0 * width_s
    t = np.linspace(lo, hi, 161)
    for j in (0, 1):
        rows = [shape(recs, int(r.recording_id), int(r.top_idx), float(r.fs), lo, hi, 161)
                for r in d[lab == j].itertuples()]
        rows = np.array([w for w in rows if w is not None])
        if len(rows) < 3:
            continue
        q = np.percentile(rows, [25, 50, 75], axis=0)
        ax.fill_between(t, q[0], q[2], color=TYPE_COLOURS[j], alpha=0.18, lw=0)
        ax.plot(t, q[1], color=TYPE_COLOURS[j], lw=2, label=f"{names[j]} (n {len(rows)})")
    ax.axhline(0, color=fs.MUTED, lw=0.7)
    ax.axvline(0, color=fs.GRID, lw=0.7)
    ax.set_xlabel("Seconds from the top", fontsize=8)
    ax.set_ylabel("mV from the top", fontsize=8)
    ax.legend(fontsize=7, loc="lower right")
    ax.set_title("The typical drop of each kind (median, middle half)", loc="left", fontsize=8.5)


def _interval_panel(ax, d, lab, names):
    t = d["t_s"].to_numpy()
    before = np.r_[np.nan, np.diff(t)]
    after = np.r_[np.diff(t), np.nan]
    data, pos, cols = [], [], []
    for j in (0, 1):
        for k, v in enumerate((before, after)):
            x = v[(lab == j) & np.isfinite(v)]
            data.append(x)
            pos.append(k * 2.6 + j)
            cols.append(TYPE_COLOURS[j])
    b = ax.boxplot(data, positions=pos, widths=0.7, showfliers=False, patch_artist=True, whis=(5, 95),
                   medianprops={"color": fs.INK, "lw": 1.6})
    for box, c in zip(b["boxes"], cols):
        box.set_facecolor(to_rgba(c, 0.4))
    ax.set_yscale("log")
    ax.set_xticks([0.5, 3.1])
    ax.set_xticklabels(["wait BEFORE the drop", "wait AFTER the drop"], fontsize=8)
    ax.set_ylabel("seconds to the neighbouring drop", fontsize=8)
    pb = mannwhitneyu(data[0], data[2]).pvalue if len(data[0]) and len(data[2]) else np.nan
    pa = mannwhitneyu(data[1], data[3]).pvalue if len(data[1]) and len(data[3]) else np.nan
    ax.set_title(f"Waits round each kind: before p {fmt_p(pb)}, after p {fmt_p(pa)}", loc="left", fontsize=8.5)
    ax.scatter([], [], color=TYPE_COLOURS[0], marker="s", label=names[0])
    ax.scatter([], [], color=TYPE_COLOURS[1], marker="s", label=names[1])
    ax.legend(fontsize=7, loc="upper right")


def fig_types(m, d_all, recs):
    d = events_only(d_all)
    if len(d) < TYPES_MIN:
        return None
    unit_s, unit_name = time_unit(m["duration_h"])
    tt = (d["t_s"].to_numpy() - m["start_idx"] / m["fs"]) / unit_s
    zs, base_s = local_relative(d["depth_mv"].to_numpy(float))
    size, size_cut, size_note = two_groups(zs)
    wd = d[d["width_s"] > 0].reset_index(drop=True)
    has_w = len(wd) >= TYPES_MIN // 2
    if has_w:
        zw, _ = local_relative(wd["width_s"].to_numpy(float))
        wide, wide_cut, wide_note = two_groups(zw)
    fig = plt.figure(figsize=(17.0, 13.0))
    gs = fig.add_gridspec(3, 4, hspace=0.55, wspace=0.3, top=0.93, bottom=0.05)
    sizes = ("small", "big")
    widths = ("thin", "wide")
    # row 0: where the kinds sit
    ax = fig.add_subplot(gs[0, 0])
    xcol = "width_s" if has_w else "fall_s"
    ok = d[xcol] > 0
    for j in (0, 1):
        mm = ok & (size == j)
        ax.scatter(d.loc[mm, xcol], d.loc[mm, "depth_mv"], s=10, color=TYPE_COLOURS[j], alpha=0.7, linewidths=0,
                   label=f"{sizes[j]} for its time ({int((size == j).sum())})")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Width (s)" if has_w else "Fall time (s)", fontsize=8)
    ax.set_ylabel("Depth (mV)", fontsize=8)
    ax.legend(fontsize=7, loc="lower right")
    ax.set_title("Depth against width, each drop coloured\nbig or small against its neighbours", loc="left",
                 fontsize=8.5)
    ax = fig.add_subplot(gs[0, 1:3])
    for j in (0, 1):
        mm = size == j
        ax.scatter(tt[mm], d.loc[mm, "depth_mv"], s=10, color=TYPE_COLOURS[j], alpha=0.75, linewidths=0)
    ax.plot(tt, d["depth_mv"], color=fs.GRID, lw=0.5, zorder=0)
    ax.plot(tt, 10 ** base_s, color=fs.INK, lw=1.4, zorder=4, label=f"local level (geometric mean of {LOCAL_N} drops)")
    ax.set_yscale("log")
    ax.legend(fontsize=7, loc="lower right")
    ax.set_xlabel(f"{unit_name.capitalize()} from the start", fontsize=8)
    ax.set_ylabel("Depth (mV)", fontsize=8)
    ax.set_title(f"Big and small drops through the sequence: {size_note}", loc="left", fontsize=8.5)
    ax = fig.add_subplot(gs[0, 3])
    ax.axis("off")
    lines = [f"{len(d)} drops",
             f"big = deeper than x{10 ** size_cut:.2f} its local level:",
             f"  {int(size.sum())} big, {int((1 - size).sum())} small"]
    if has_w:
        ct = pd.crosstab(pd.Series(size[(d["width_s"] > 0).to_numpy()], name="size"), pd.Series(wide, name="width"))
        lines.append(f"wide = wider than x{10 ** wide_cut:.2f} its local level:")
        lines.append(f"  {int(wide.sum())} wide, {int((1 - wide).sum())} thin (of {len(wd)} with a width)")
        lines.append(f"  ({wide_note})")
        lines.append("")
        lines.append("drops by kind (rows size, columns width):")
        lines.append("            thin   wide")
        for j in (0, 1):
            row = ct.loc[j] if j in ct.index else pd.Series({0: 0, 1: 0})
            lines.append(f"  {sizes[j]:>6}   {int(row.get(0, 0)):>4}   {int(row.get(1, 0)):>4}")
    ax.text(0, 1, "\n".join(lines), va="top", ha="left", fontsize=8.5, family="monospace", color=fs.INK)
    # rows 1 and 2: the two splits
    splits = [(d, size, sizes, "depth_mv", "Depth", zs, size_cut)]
    if has_w:
        splits.append((wd, wide, widths, "width_s", "Width", zw, wide_cut))
    stats = {}
    for row, (dd, lab, names, col, label, z, cut) in enumerate(splits, start=1):
        g_, l_ = _transition_panel(fig.add_subplot(gs[row, 0]), lab, names)
        stats[col] = (g_, l_)
        _return_panel(fig.add_subplot(gs[row, 1]), z, lab, cut, label)
        _waveform_panel(fig.add_subplot(gs[row, 2]), dd, lab, recs, names,
                        float(np.nanpercentile(d["width_s"], 75)) if d["width_s"].notna().any()
                        else 3 * float(np.median(d["fall_s"])))
        _interval_panel(fig.add_subplot(gs[row, 3]), dd, lab, names)
        fig.text(0.005, 0.64 - 0.305 * (row - 1), f"{names[1].upper()} vs {names[0].upper()}", rotation=90,
                 fontsize=11, color=fs.INK_2, va="center")
    which = f"every drop of at least {MIN_SIGMAS:g}x the noise"
    fig.suptitle(f"Two kinds of drop in {seq_label(m)} ({m['duration_h']:.1f} h, {which}): big against small, wide "
                 f"against thin", x=0.01, y=0.995, ha="left", fontsize=12)
    name = (f"types/types_seq_{m['sequence_id']:03d}_{m['dataset']}_CH{m['channel_1based']:02d}"
            ".png")
    save(fig, name, S_TYPES,
         f"{seq_label(m)} ({which}): are there two kinds of drop, and how do they take turns? Top: the cut between big and "
         f"small (and wide and thin) drops and the depth of every drop through time. Middle row, big vs small; "
         f"bottom row, wide vs thin: (1) the chance that the next drop is big after a small one and after a big "
         f"one, against the same drops shuffled; (2) each drop's size against the next one's; (3) the typical "
         f"waveform of each kind; (4) the waits before and after each kind.", dpi=150)
    out = {"sequence_id": m["sequence_id"], "drops": len(d),
           "size_cut_x_local": 10 ** size_cut, "size_note": size_note, "big": int(size.sum())}
    for col, (g_, l_) in stats.items():
        key = "size" if col == "depth_mv" else "width"
        out.update({f"{key}_switch": g_["switch"], f"{key}_switch_shuffled": float(np.mean(g_["null"][:, 0])),
                    f"{key}_p_alternate_local": l_["p_more_switching"], f"{key}_p_clump_local": l_["p_less_switching"],
                    f"{key}_p_next_high_after_high": g_["p11"], f"{key}_p_next_high_after_low": g_["p01"]})
    if has_w:
        out.update(width_cut_x_local=10 ** wide_cut, width_note=wide_note, wide=int(wide.sum()))
    return out


KIND_COLOURS = ["#2a78d6", "#1baf7a", "#eb6834", "#e34948", "#6250d6"]   # kinds in order of depth
NO_WIDTH = "#9a9893"
KINDS_MIN = 150            # drops with a width a sequence needs for the kinds figure
KIND_SHUFFLES = 2000


def kinds_of(d, kmax=4):
    """`(labels, k, bics)`: kinds from a Gaussian mixture on (log depth, log width), the number of kinds chosen by
    BIC, numbered by median depth; drops that never half-recovered (no width) are kind `k`."""
    from sklearn.mixture import GaussianMixture
    has = (d["width_s"] > 0).to_numpy()
    X = np.column_stack([np.log10(d.loc[has, "depth_mv"]), np.log10(d.loc[has, "width_s"])])
    Z = (X - X.mean(axis=0)) / X.std(axis=0)
    fits = [GaussianMixture(k, n_init=4, random_state=SEED).fit(Z) for k in range(1, kmax + 1)]
    bics = np.array([f.bic(Z) for f in fits])
    k = int(np.argmin(bics)) + 1
    raw = fits[k - 1].predict(Z)
    med = [np.median(X[raw == j, 0]) if (raw == j).any() else np.inf for j in range(k)]
    rank = np.empty(k, dtype=int)
    rank[np.argsort(med)] = np.arange(k)
    lab = np.full(len(d), k)
    lab[has] = rank[raw]
    return lab, k, bics


def transition_ratio(lab, K):
    """Observed pair counts (this kind, then that kind) against shuffles that move each drop only within its
    block of BLOCK drops (so the slow drift in which kinds are common is kept)."""
    rng = np.random.default_rng(SEED)
    n = len(lab)

    def counts(p):
        c = np.zeros((K, K))
        np.add.at(c, (p[:-1], p[1:]), 1)
        return c
    obs = counts(lab)
    keys = (np.arange(n) // BLOCK).astype(float)
    null = np.array([counts(lab[np.argsort(keys + rng.random(n), kind="stable")]) for _ in range(KIND_SHUFFLES)])
    p_hi = (np.sum(null >= obs, axis=0) + 1) / (KIND_SHUFFLES + 1)
    p_lo = (np.sum(null <= obs, axis=0) + 1) / (KIND_SHUFFLES + 1)
    return obs, null.mean(axis=0), p_hi, p_lo


def fig_kinds(m, d_all, recs):
    d = events_only(d_all)
    d = d.reset_index(drop=True)
    if (d["width_s"] > 0).sum() < KINDS_MIN:
        return None
    lab, k, bics = kinds_of(d)
    K = k + int((lab == k).any())
    colours = KIND_COLOURS[:k] + [NO_WIDTH]
    names = []
    for j in range(K):
        g = d[lab == j]
        names.append(f"no half recovery ({len(g)})" if j == k else
                     f"{chr(65 + j)}: {g['depth_mv'].median():.2g} mV, {g['width_s'].median():.2g} s ({len(g)})")
    unit_s, unit_name = time_unit(m["duration_h"])
    t0 = m["start_idx"] / m["fs"]
    tt = (d["t_s"].to_numpy() - t0) / unit_s
    fig = plt.figure(figsize=(17.0, 14.0))
    gs = fig.add_gridspec(3, 6, height_ratios=[1.1, 0.9, 1.1], hspace=0.42, wspace=0.75, top=0.94, bottom=0.05)
    # the kinds in the plane
    ax = fig.add_subplot(gs[0, 0:2])
    for j in range(k):
        mm = lab == j
        ax.scatter(d.loc[mm, "width_s"], d.loc[mm, "depth_mv"], s=9, color=colours[j], alpha=0.7, linewidths=0,
                   label=names[j])
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Width (s)", fontsize=8)
    ax.set_ylabel("Depth (mV)", fontsize=8)
    ax.legend(fontsize=7, loc="upper left", markerscale=1.8, framealpha=0.9)
    gain = " / ".join(f"{b:.0f}" for b in bics - bics.min())
    ax.set_title(f"{k} kinds found by a mixture model on depth and width\n(fit penalty BIC above the best for 1-"
                 f"{len(bics)} kinds: {gain})", loc="left", fontsize=8.5)
    # depth through time
    ax = fig.add_subplot(gs[0, 2:6])
    for j in range(K):
        mm = lab == j
        ax.scatter(tt[mm], d.loc[mm, "depth_mv"], s=7, color=colours[j], alpha=0.8, linewidths=0, label=names[j])
    ax.set_yscale("log")
    ax.set_xlabel(f"{unit_name.capitalize()} from the start", fontsize=8)
    ax.set_ylabel("Depth (mV)", fontsize=8)
    ax.set_title("Every drop through the sequence, coloured by its kind", loc="left", fontsize=9)
    # three close-ups of the trace
    gaps = np.diff(d["t_s"].to_numpy())
    span = float(np.clip(30 * np.median(gaps), 600, 4 * 3600))
    dur = (m["end_idx"] - m["start_idx"]) / m["fs"]
    for n, frac in enumerate((0.15, 0.5, 0.85)):
        ax = fig.add_subplot(gs[1, 2 * n:2 * n + 2])
        c0 = t0 + frac * dur - span / 2
        c0 = min(max(c0, t0), t0 + dur - span)
        a, b = int(c0 * m["fs"]), int((c0 + span) * m["fs"])
        mm = (d["top_idx"] >= a) & (d["top_idx"] < b)
        sub = {"recording_id": m["recording_id"], "start_idx": a, "end_idx": b, "fs": m["fs"]}
        draw_trace(ax, sub, d[mm], recs, 60.0, "minutes", colour_by=[colours[j] for j in lab[mm.to_numpy()]],
                   lw_fall=2.2)
        ax.set_title(f"Close-up at {(c0 - t0) / unit_s:.1f} {unit_name}: {int(mm.sum())} drops", loc="left",
                     fontsize=9)
        ax.set_xlabel("Minutes into the close-up", fontsize=8)
    # waveforms by kind
    ax = fig.add_subplot(gs[2, 0:2])
    w = float(np.nanpercentile(d["width_s"], 75))
    lo, hi = -0.6 * w, 3.0 * w
    t = np.linspace(lo, hi, 181)
    for j in range(K):
        rows = [shape(recs, int(r.recording_id), int(r.top_idx), float(r.fs), lo, hi, 181)
                for r in d[lab == j].itertuples()]
        rows = np.array([y for y in rows if y is not None])
        if len(rows) < 3:
            continue
        q = np.percentile(rows, [25, 50, 75], axis=0)
        ax.fill_between(t, q[0], q[2], color=colours[j], alpha=0.15, lw=0)
        ax.plot(t, q[1], color=colours[j], lw=2, label=names[j].split(" (")[0])
    ax.axhline(0, color=fs.MUTED, lw=0.7)
    ax.set_xlabel("Seconds from the top", fontsize=8)
    ax.set_ylabel("mV from the top", fontsize=8)
    ax.legend(fontsize=6.5, loc="lower right")
    ax.set_title("The typical drop of each kind (median, middle half)", loc="left", fontsize=9)
    # what follows what
    ax = fig.add_subplot(gs[2, 2:4])
    obs, exp, p_hi, p_lo = transition_ratio(lab, K)
    ratio = np.log2(np.maximum(obs, 0.5) / np.maximum(exp, 0.5))
    im = ax.imshow(ratio, cmap="coolwarm", vmin=-1.5, vmax=1.5)
    for i in range(K):
        for j in range(K):
            star = "*" if min(p_hi[i, j], p_lo[i, j]) < 0.01 else ""
            ax.text(j, i, f"{int(obs[i, j])}\n{obs[i, j] / max(exp[i, j], 1e-9):.2f}x{star}", ha="center",
                    va="center", fontsize=7, color=fs.INK)
    short = [n.split(":")[0] if ":" in n else "none" for n in names]
    ax.set_xticks(range(K))
    ax.set_xticklabels([f"then {s}" for s in short], fontsize=7.5)
    ax.set_yticks(range(K))
    ax.set_yticklabels([f"{s} first" for s in short], fontsize=7.5)
    ax.grid(False)
    fig.colorbar(im, ax=ax, fraction=0.04, ticks=[-1, 0, 1]).ax.set_yticklabels(["½x", "1x", "2x"], fontsize=7)
    ax.set_title(f"What follows what: count and observed ÷ expected\n(against shuffles within blocks of {BLOCK}; "
                 f"* p < 0.01)", loc="left", fontsize=8.5)
    # waits
    ax = fig.add_subplot(gs[2, 4:6])
    tops = d["t_s"].to_numpy()
    before, after = np.r_[np.nan, np.diff(tops)], np.r_[np.diff(tops), np.nan]
    data, pos, cols, which_kind = [], [], [], []
    for j in range(K):
        for s, v in enumerate((before, after)):
            x = v[(lab == j) & np.isfinite(v)]
            if len(x):
                data.append(x)
                pos.append(s * (K + 1.5) + j)
                cols.append(colours[j])
                which_kind.append(j)
    b = ax.boxplot(data, positions=pos, widths=0.75, showfliers=False, patch_artist=True, whis=(5, 95),
                   medianprops={"color": fs.INK, "lw": 1.6})
    for box, c in zip(b["boxes"], cols):
        box.set_facecolor(to_rgba(c, 0.45))
    ax.set_yscale("log")
    letters = [n.split(":")[0] if ":" in n else "-" for n in names]
    ax.set_xticks(pos)
    ax.set_xticklabels([letters[j] for j in which_kind], fontsize=8)
    ax.set_ylabel("seconds to the neighbouring drop", fontsize=8)
    ax.set_title("Waits BEFORE (left group) and AFTER (right group)\neach kind (- : no half recovery)", loc="left",
                 fontsize=8.5)
    which = f"every drop of at least {MIN_SIGMAS:g}x the noise"
    fig.suptitle(f"Kinds of drop in {seq_label(m)} ({m['duration_h']:.1f} h, {len(d)} drops, {which})", x=0.01,
                 y=0.995, ha="left", fontsize=12)
    name = (f"types/kinds_seq_{m['sequence_id']:03d}_{m['dataset']}_CH{m['channel_1based']:02d}"
            ".png")
    save(fig, name, S_TYPES,
         f"{seq_label(m)} ({which}): a mixture model sorts the drops into kinds by depth and width (the number of "
         f"kinds chosen by BIC; drops that never climbed half-way back form their own grey kind). Top: the kinds "
         f"in the width-depth plane and through time. Middle: three close-ups of the trace with each fall coloured "
         f"by its kind - the interleaving by eye. Bottom: each kind's typical drop; what kind follows what, against "
         f"the same drops shuffled only locally (red: more often than chance, blue: less); and the waits round "
         f"each kind.", dpi=150)
    rows = []
    for i in range(K):
        for j in range(K):
            rows.append({"sequence_id": m["sequence_id"], "first": short[i],
                         "then": short[j], "observed": int(obs[i, j]), "expected": round(float(exp[i, j]), 2),
                         "p_more": float(p_hi[i, j]), "p_fewer": float(p_lo[i, j])})
    return {"sequence_id": m["sequence_id"], "kinds": k,
            "names": " | ".join(names), "transitions": rows}


# ── experiments ──────────────────────────────────────────────────────────────

def fig_kymograph(m, d_all, recs):
    """Every drop of a sequence as one row of colour, in time order: the sequence's shape history in one image."""
    d = events_only(d_all)
    d = d.reset_index(drop=True)
    if len(d) < 60:
        return
    w = float(np.nanmedian(d["width_s"])) if d["width_s"].notna().any() else 3 * float(np.median(d["fall_s"]))
    lo, hi, npts = -1.0 * w, 4.0 * w, 300
    rows, keep = [], []
    for k, r in enumerate(d.itertuples()):
        y = shape(recs, int(r.recording_id), int(r.top_idx), float(r.fs), lo, hi, npts)
        if y is not None:
            rows.append(y)
            keep.append(k)
    M = np.array(rows)
    dk = d.iloc[keep].reset_index(drop=True)
    depth = dk["depth_mv"].to_numpy(float)
    vmax = float(np.percentile(depth, 95))
    hours = (dk["t_s"].to_numpy() - m["start_idx"] / m["fs"]) / 3600.0
    fig, axes = plt.subplots(1, 3, figsize=(17.0, 9.0), gridspec_kw={"wspace": 0.18})
    ext = (lo / 60.0, hi / 60.0, len(M), 0)
    im = axes[0].imshow(M, aspect="auto", cmap="magma", vmin=-vmax, vmax=0.3 * vmax, extent=ext,
                        interpolation="nearest")
    order = np.argsort(depth)[::-1]
    axes[1].imshow(M[order], aspect="auto", cmap="magma", vmin=-vmax, vmax=0.3 * vmax, extent=ext,
                   interpolation="nearest")
    im2 = axes[2].imshow(M / depth[:, None], aspect="auto", cmap="magma", vmin=-1.2, vmax=0.4, extent=ext,
                         interpolation="nearest")
    ticks = np.linspace(0, len(M) - 1, 9).astype(int)
    for ax in (axes[0], axes[2]):
        ax.set_yticks(ticks + 0.5)
        ax.set_yticklabels([f"{hours[i]:.0f} h" for i in ticks], fontsize=7.5)
    axes[1].set_yticks(ticks + 0.5)
    axes[1].set_yticklabels([f"{depth[order][i]:.2g} mV" for i in ticks], fontsize=7.5)
    for ax in axes:
        ax.set_xlabel("Minutes from the drop's top")
        ax.axvline(0, color="white", lw=0.6, alpha=0.6)
        ax.grid(False)
    axes[0].set_title("In time order (the hour of each drop at left)", loc="left", fontsize=9.5)
    axes[1].set_title("Sorted by depth, deepest at the top", loc="left", fontsize=9.5)
    axes[2].set_title("In time order, each drop ÷ its own depth", loc="left", fontsize=9.5)
    c1 = fig.colorbar(im, ax=axes[:2], orientation="horizontal", fraction=0.03, pad=0.07, aspect=60)
    c1.set_label("mV from the drop's top (dark: far below it)")
    c2 = fig.colorbar(im2, ax=axes[2], orientation="horizontal", fraction=0.03, pad=0.07, aspect=25)
    c2.set_label("÷ the drop's depth (-1 = its bottom)")
    which = f"every drop of at least {MIN_SIGMAS:g}x the noise"
    fig.suptitle(f"{seq_label(m)}: {len(M)} drops ({which}) as rows of colour - the sequence's shape history in one "
                 f"image", x=0.01, ha="left", fontsize=12)
    save(fig, f"extra/kymograph_seq_{m['sequence_id']:03d}.png", S_EXTRA,
         f"{seq_label(m)} ({which}): every drop is one thin row, its trace from {abs(lo) / 60:.2g} min before its top to "
         f"{hi / 60:.2g} min after, coloured by how far below its top the trace is (dark = deep). Left: in time "
         f"order, so slow changes of depth or shape show as gradual bands. Middle: sorted by depth, showing how the "
         f"shape changes with size. Right: each drop scaled to its own depth, showing shape alone.", dpi=170)


def fig_relaxation(metas, sev):
    """Does a longer wait give a bigger drop (charge then release), or does a big drop buy a longer rest?"""
    longs = []
    for m in metas:
        d = events_only(sev[sev["sequence_id"] == m["sequence_id"]])
        if len(d) >= TYPES_MIN:
            longs.append((m, d))
    longs = sorted(longs, key=lambda md: -len(md[1]))[:8]
    if not longs:
        return []
    fig, axes = plt.subplots(len(longs), 3, figsize=(13.5, 3.1 * len(longs)), squeeze=False)
    out = []
    for row, (m, d) in zip(axes, longs):
        t = d["t_s"].to_numpy()
        depth = d["depth_mv"].to_numpy(float)
        before, after = np.r_[np.nan, np.diff(t)], np.r_[np.diff(t), np.nan]
        res = {"sequence_id": m["sequence_id"], "drops": len(d)}
        for ax, (x, y, xl, yl, key) in zip(row, (
                (before, depth, "wait before (s)", "depth (mV)", "before"),
                (after, depth, "wait after (s)", "depth (mV)", "after"),
                (before[1:-1], after[1:-1], "wait before (s)", "wait after (s)", "poincare"))):
            ok = np.isfinite(x) & np.isfinite(y) & (x > 0) & (y > 0)
            ax.scatter(x[ok], y[ok], s=7, color=BLUE, alpha=0.55, linewidths=0)
            rho = spearmanr(x[ok], y[ok])
            res[f"rho_{key}"], res[f"p_{key}"] = float(rho.statistic), float(rho.pvalue)
            ax.set_xscale("log")
            ax.set_yscale("log")
            ax.set_xlabel(xl, fontsize=8)
            ax.set_ylabel(yl, fontsize=8)
            ax.set_title(f"Spearman ρ {rho.statistic:+.2f} (p {fmt_p(rho.pvalue)})", loc="left", fontsize=8)
        row[0].text(-0.32, 0.5, f"{seq_label(m)}\n{len(d)} drops", transform=row[0].transAxes,
                    rotation=90, va="center", ha="center", fontsize=8.5, color=fs.INK_2)
        out.append(res)
    axes[0, 0].set_title(f"LONGER WAIT, BIGGER DROP?\n{axes[0, 0].get_title(loc='left')}", loc="left", fontsize=8)
    axes[0, 1].set_title(f"BIGGER DROP, LONGER REST AFTER?\n{axes[0, 1].get_title(loc='left')}", loc="left", fontsize=8)
    axes[0, 2].set_title(f"DOES ONE WAIT PREDICT THE NEXT?\n{axes[0, 2].get_title(loc='left')}", loc="left", fontsize=8)
    fig.suptitle("Charge and release? The wait round each drop against its depth (the longest sequences)",
                 x=0.01, ha="left", fontsize=12)
    fig.tight_layout(rect=(0.02, 0, 1, 0.98))
    save(fig, "extra/wait_vs_depth.png", S_EXTRA,
         "If drops behaved like a capacitor that charges and discharges, a longer wait before a drop would give a "
         "deeper drop (left), or a deeper drop would need a longer rest after it (middle). Right: one wait against "
         "the next (a return map). One row per long sequence, every drop found. Spearman's rho: +1 perfectly "
         "together, 0 unrelated, -1 opposite.", dpi=150)
    return out


def fig_raster(ev):
    """Every reviewed drop on its channel's timeline."""
    keys = ev.groupby(["dataset", "channel"]).size()
    keys = keys[keys >= 3]
    order = sorted(keys.index, key=lambda k: (DATASET_ORDER.index(k[0]), k[1]))
    fig, ax = plt.subplots(figsize=(15.0, 0.17 * len(order) + 1.8))
    y = {k: len(order) - 1 - i for i, k in enumerate(order)}
    g = ev[ev.set_index(["dataset", "channel"]).index.isin(order)]
    norm = LogNorm(g["depth_mv"].quantile(0.02), g["depth_mv"].quantile(0.98))
    sc = ax.scatter(g["t_h"], [y[(d, c)] for d, c in zip(g["dataset"], g["channel"])], c=g["depth_mv"],
                    cmap="viridis", norm=norm, marker="|", s=40, linewidths=1.0)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([f"{d} CH{c + 1}" for d, c in reversed(order)], fontsize=6)
    for tick, (d, _) in zip(ax.get_yticklabels(), reversed(order)):
        tick.set_color(fs.colour(d))
    ax.set_xlabel("Hours into the recording")
    ax.set_ylim(-1, len(order))
    ax.grid(axis="y", visible=False)
    cb = fig.colorbar(sc, ax=ax, fraction=0.02, pad=0.01)
    cb.set_label("amplitude (mV)")
    ax.set_title(f"Where the {len(g):,} reviewed drops are: every channel's timeline (channels with 3+ drops)",
                 loc="left")
    save(fig, "extra/drop_raster.png", S_EXTRA,
         "Every reviewed drop as a tick on its channel's timeline, coloured by amplitude. This is where the review "
         "has looked as much as where the mycelium dropped: long empty stretches are mostly unreviewed, not quiet.",
         dpi=160)


def fig_ccdf(ev):
    """Size distributions on log-log axes: a straight line would be a power law (no typical size)."""
    fig, axes = plt.subplots(1, 3, figsize=(14.0, 4.5))
    for ax, (col, label) in zip(axes, MEASURES[:3]):
        for sp in species_present(ev, col, least=20):
            v = np.sort(ev.loc[(ev["species"] == sp) & (ev[col] > 0), col].to_numpy(float))
            p = 1.0 - np.arange(len(v)) / len(v)
            ax.step(v, p, where="post", color=fs.species_colour(sp), lw=1.7, label=f"{sp} ({len(v)})")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel(label)
        ax.set_ylabel("fraction of drops at least this big")
        ax.legend(fontsize=7, loc="lower left")
    fig.suptitle("Is there a typical size? The share of drops at least as big as x, log-log", x=0.01, ha="left",
                 fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    save(fig, "extra/size_distributions.png", S_EXTRA,
         "For each size x, the share of drops at least that big, on log-log axes. A curve that bends down steeply "
         "has a typical size; a long straight run would mean sizes with no typical scale (as in avalanches). The "
         "review sample and the noise floor shape the small end, so read the middle and the tail.")


def fig_shape_space(ev, recs):
    """Principal components and a t-SNE embedding of every drop's shape."""
    from sklearn.manifold import TSNE
    g = ev[ev["width_s"] > 0].reset_index(drop=True)
    lo, hi, npts = -0.5, 3.0, 121
    W, keep = [], []
    for k, r in enumerate(g.itertuples()):
        w = shape(recs, r.recording_id, r.top_idx, max(r.recovery_idx - r.top_idx, 1), lo, hi, npts, depth=r.depth_mv)
        if w is not None:
            W.append(np.clip(w, -2.5, 1.5))
            keep.append(k)
    W = np.array(W)
    g = g.iloc[keep].reset_index(drop=True)
    mean = W.mean(axis=0)
    U, S, Vt = np.linalg.svd(W - mean, full_matrices=False)
    pcs = U * S
    expl = S ** 2 / np.sum(S ** 2)
    emb = TSNE(n_components=2, perplexity=40, init="pca", random_state=SEED).fit_transform(pcs[:, :10])
    fig = plt.figure(figsize=(16.0, 10.0))
    gs = fig.add_gridspec(2, 3, height_ratios=[1.35, 1], hspace=0.32, wspace=0.25)
    cols = g["species"].map(fs.species_colour).to_numpy()
    a = fig.add_subplot(gs[0, 0])
    a.scatter(pcs[:, 0], pcs[:, 1], s=5, c=cols, alpha=0.6, linewidths=0)
    a.set_xlabel(f"shape component 1 ({expl[0]:.0%} of the variation)")
    a.set_ylabel(f"shape component 2 ({expl[1]:.0%})")
    a.set_title("Every drop's shape, its two main components, by species", loc="left", fontsize=9.5)
    for sp in species_present(g):
        a.scatter([], [], color=fs.species_colour(sp), s=20, label=sp)
    a.legend(fontsize=7, loc="best")
    a = fig.add_subplot(gs[0, 1])
    a.scatter(emb[:, 0], emb[:, 1], s=5, c=cols, alpha=0.6, linewidths=0)
    a.set_xticks([])
    a.set_yticks([])
    a.set_title("A t-SNE map of the shapes (near = alike), by species", loc="left", fontsize=9.5)
    a = fig.add_subplot(gs[0, 2])
    sc = a.scatter(emb[:, 0], emb[:, 1], s=5, c=g["depth_mv"], cmap="viridis",
                   norm=LogNorm(g["depth_mv"].quantile(0.02), g["depth_mv"].quantile(0.98)), alpha=0.7, linewidths=0)
    fig.colorbar(sc, ax=a, fraction=0.04).set_label("amplitude (mV)")
    a.set_xticks([])
    a.set_yticks([])
    a.set_title("...the same map coloured by amplitude", loc="left", fontsize=9.5)
    t = np.linspace(lo, hi, npts)
    for j in range(3):
        a = fig.add_subplot(gs[1, j])
        sd = pcs[:, j].std()
        for s, c in ((-2, BLUE), (0, fs.INK), (2, RED)):
            a.plot(t, mean + s * sd * Vt[j], color=c, lw=2 if s == 0 else 1.6,
                   label="average shape" if s == 0 else f"{'+' if s > 0 else '-'}2 SD along component {j + 1}")
        a.axhline(0, color=fs.GRID, lw=0.8)
        a.axvline(1, color=fs.GRID, lw=0.8, ls="--")
        a.set_xlabel("Time ÷ the drop's width (1 = half recovered)")
        a.set_ylabel("÷ the drop's amplitude")
        a.set_title(f"What component {j + 1} changes ({expl[j]:.0%})", loc="left", fontsize=9.5)
        a.legend(fontsize=7, loc="lower right")
    fig.suptitle(f"The space of drop shapes: {len(W):,} drops, each scaled to its own width and amplitude",
                 x=0.01, ha="left", fontsize=12)
    save(fig, "extra/shape_space.png", S_EXTRA,
         "Every drop scaled to the same width and amplitude, then compared. Top left: the two directions in which "
         "the shapes differ most (principal components). Top middle and right: a t-SNE map, which places drops of "
         "similar shape near each other. Bottom: what moving along each component does to the average drop.", dpi=160)


# ── uniform 10 x 10 grids, and fingerprints (the researcher, 24 Nov) ─────────

GRID_N = 10
TAU_LO, TAU_HI, TAU_N = -0.5, 5.0, 111      # the shape grids' window, in units of each drop's own fall time
SHAPES_FILE = os.path.join(OUT, "event_shapes.npz")
PROB_CMAP = LinearSegmentedColormap.from_list("probability", ["#ffffff", "#e3ecf8", "#a9c8ee", "#5b96df"])


def fall_anatomy(seg):
    """`(steepness, position)` of one fall, `seg` the raw trace from its top to its bottom (mV).

    Steepness: how many times steeper the fall's steepest moment is than its average slope - 1 for a straight ramp,
    large for a cliff. Position: when it has fallen half-way, as a fraction of its fall time - 0.5 for a ramp, near 0
    for a cliff at the start, near 1 for a cliff at the end. Both read on a copy smoothed over a thirtieth of the fall,
    so a single noisy sample does not make a cliff; neither depends on how long the drop lasts."""
    from scipy.ndimage import gaussian_filter1d
    seg = np.asarray(seg, dtype=float)
    n = len(seg) - 1
    if n < 2:
        return 1.0, 0.5
    sm = gaussian_filter1d(seg, max(0.5, n / 30.0), mode="nearest") if n >= 6 else seg
    span = sm[0] - sm.min()
    if span <= 0:
        return np.nan, np.nan
    steep = max(1.0, float(np.max(-np.diff(sm))) * n / span)
    fallen = (sm[0] - sm) / span
    k = int(np.argmax(fallen >= 0.5))
    if k == 0:
        return steep, 0.0
    f0, f1 = fallen[k - 1], fallen[k]
    return steep, ((k - 1) + ((0.5 - f0) / (f1 - f0) if f1 > f0 else 1.0)) / n


def build_shapes(ev, recs):
    """`(W, steepness, position)`: each drop's waveform on TAU_N points from TAU_LO to TAU_HI of its own fall time,
    divided by its own depth (0 = its top, -1 = its bottom), and its fall anatomy. Cached in SHAPES_FILE."""
    ids = ev["event_id"].astype(str).to_numpy().astype("U")    # fixed-width text: loads without pickle
    if os.path.exists(SHAPES_FILE):
        z = np.load(SHAPES_FILE)
        if len(z["event_id"]) == len(ids) and np.all(z["event_id"] == ids):
            return z["W"], z["steepness"], z["position"]
    W = np.full((len(ev), TAU_N), np.nan)
    S, P = np.full(len(ev), np.nan), np.full(len(ev), np.nan)
    for i, r in enumerate(ev.itertuples()):
        top, bottom = int(r.top_idx), int(r.bottom_idx)
        w = shape(recs, int(r.recording_id), top, max(bottom - top, 1), TAU_LO, TAU_HI, TAU_N, depth=float(r.depth_mv))
        if w is not None:
            W[i] = w
        seg = window(recs, int(r.recording_id), top, bottom + 1)
        if seg is not None:
            S[i], P[i] = fall_anatomy(seg)
    np.savez(SHAPES_FILE, W=W, steepness=S, position=P, event_id=ids)
    return W, S, P


def with_shape_measures(ev, recs):
    W, S, P = build_shapes(ev, recs)
    ev = ev.assign(steepness=S, position=P, recovery_ratio=ev["recovery_s"] / ev["fall_s"])
    return ev, W


def uniform_bins(v, log=True, n=GRID_N, pct=(1, 99), lohi=None):
    """`(edges, index)`: n equal bins between the given percentiles (in log10 when `log`) or the given `lohi`; values
    beyond them sit in the edge bins, missing values get -1."""
    x = np.log10(np.where(np.asarray(v, float) > 0, v, np.nan)) if log else np.asarray(v, dtype=float)
    ok = np.isfinite(x)
    lo, hi = lohi if lohi is not None else np.percentile(x[ok], pct)
    edges = np.linspace(lo, hi, n + 1)
    idx = np.full(len(x), -1)
    idx[ok] = np.clip(np.searchsorted(edges, x[ok], side="right") - 1, 0, n - 1)
    return edges, idx


def _glyph(ax, i, j, y, q25=None, q75=None, *, sd=None, norm=None, colour=None, alpha=1.0, lw=1.6, white_band=False):
    """Waveform `y` (0 = top, -1 = bottom) drawn inside the unit cell whose lower-left corner is (i, j)."""
    m = 0.08
    X = i + m + np.linspace(0.0, 1.0 - 2 * m, len(y))

    def Y(v):
        return j + m + (np.clip(v, Y_LO, Y_HI) - Y_LO) / (Y_HI - Y_LO) * (1.0 - 2 * m)
    if q25 is not None:
        ax.fill_between(X, Y(q25), Y(q75), color="white" if white_band else "#e4e3df",
                        alpha=(0.75 if white_band else 1.0) * alpha, lw=0, zorder=2)
    ax.plot([X[0], X[-1]], [Y(0.0), Y(0.0)], color="#b9b8b2", lw=0.5, alpha=alpha, zorder=2)
    if sd is not None:
        pts = np.column_stack([X, Y(y)]).reshape(-1, 1, 2)
        lc = LineCollection(np.concatenate([pts[:-1], pts[1:]], axis=1), cmap=VAR_CMAP, norm=norm, linewidths=lw,
                            zorder=3, alpha=alpha, capstyle="round")
        lc.set_array(0.5 * (sd[:-1] + sd[1:]))
        ax.add_collection(lc)
    else:
        ax.plot(X, Y(y), color=colour or fs.INK, lw=lw, alpha=alpha, zorder=3, solid_capstyle="round")


def _cell_frame(ax, nx, ny, counts, mode, total):
    """The grid's cells: shaded by the share of all drops they hold (mode 'shaded') or plain; returns the opacity
    and line width each cell's glyph gets (mode 'opacity': rarer cells fade)."""
    cmax = max(counts.values()) if counts else 1
    style = {}
    for i in range(nx):
        for j in range(ny):
            n = counts.get((i, j), 0)
            face = PROB_CMAP(min(1.0, (n / total) / (cmax / total))) if (mode == "shaded" and n) else "white"
            ax.add_patch(Rectangle((i, j), 1, 1, facecolor=face, edgecolor="#e4e3df", lw=0.8, zorder=1))
            r = np.sqrt(n / cmax) if cmax else 0.0
            style[(i, j)] = ((0.12 + 0.88 * r, 0.7 + 1.9 * r) if mode == "opacity" else (1.0, 1.7))
            if n:
                ax.text(i + 0.96, j + 0.95, f"{n}", ha="right", va="top", fontsize=6.5, color=fs.INK_2, zorder=4)
    ax.set_xlim(0, nx)
    ax.set_ylim(0, ny)
    ax.grid(False)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    return style


def nice_number(v):
    """A tick label without an exponent: 2,210 rather than 2.21e+03."""
    return f"{v:,.0f}" if v >= 100 else f"{v:.3g}"


def _prob_colorbar(fig, total, cmax, where):
    cax = fig.add_axes(where)
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=Normalize(0, 100 * cmax / total), cmap=PROB_CMAP), cax=cax)
    cb.set_label("share of all drops in the cell (%)", fontsize=8)
    cb.ax.tick_params(labelsize=7)


def _edge_labels(edges, log, fmt):
    return [fmt(10 ** e if log else e) for e in edges]


def fig_fall_grid10(ev, recs, mode):
    """map_fall_medoids on a uniform 10 x 10 grid: fall time against amplitude, each cell's medoid, and how common
    each cell is - as a shaded probability map, or as the glyph's opacity."""
    g = ev[(ev["fall_s"] > 0) & (ev["depth_mv"] > 0)].reset_index(drop=True)
    xe, xi = uniform_bins(g["fall_s"].to_numpy(float))
    ye, yi = uniform_bins(g["depth_mv"].to_numpy(float))
    post = 5.0
    cells = {}
    for k, r in enumerate(g.itertuples()):
        cells.setdefault((int(xi[k]), int(yi[k])), []).append(r)
    counts = {c: len(v) for c, v in cells.items()}
    stats = {}
    for (i, j), rows in cells.items():
        wc = 10 ** (0.5 * (xe[i] + xe[i + 1]))
        W = [shape(recs, int(r.recording_id), int(r.top_idx), wc * float(r.fs), -0.5, post, NPTS,
                   depth=float(r.depth_mv)) for r in rows]
        W = np.array([w for w in W if w is not None])
        if len(W) >= 3:
            stats[(i, j)] = {"medoid": W[int(np.argmin(cdist(W, W).sum(axis=1)))], "sd": W.std(axis=0, ddof=1),
                             "q25": np.percentile(W, 25, axis=0), "q75": np.percentile(W, 75, axis=0), "wc": wc}
    rel = np.concatenate([s["sd"] for s in stats.values()])
    norm = Normalize(0.0, float(np.round(np.percentile(rel, 90), 2)))
    fig, ax = plt.subplots(figsize=(15.5, 11.5))
    style = _cell_frame(ax, GRID_N, GRID_N, counts, mode, len(g))
    for (i, j), s in stats.items():
        alpha, lw = style[(i, j)]
        if mode == "shaded":
            _glyph(ax, i, j, s["medoid"], s["q25"], s["q75"], sd=s["sd"], norm=norm, lw=lw, white_band=True)
        else:
            _glyph(ax, i, j, s["medoid"], s["q25"], s["q75"], colour=fs.INK, alpha=alpha, lw=lw)
    ax.set_xticks(range(GRID_N + 1))
    ax.set_xticklabels(_edge_labels(xe, True, nice_number), fontsize=8)
    ax.set_yticks(range(GRID_N + 1))
    ax.set_yticklabels(_edge_labels(ye, True, nice_number), fontsize=8)
    ax.set_xlabel("Fall time: top to bottom (s; equal steps on a log scale; the edge columns hold everything beyond)")
    ax.set_ylabel("Amplitude (mV; equal steps on a log scale)")
    if mode == "shaded":
        _prob_colorbar(fig, len(g), max(counts.values()), [0.915, 0.55, 0.011, 0.3])
        cax = fig.add_axes([0.915, 0.15, 0.011, 0.3])
        cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=VAR_CMAP), cax=cax, extend="max")
        cb.set_label("how much the cell's drops differ\n(SD in units of each drop's amplitude)", fontsize=8)
        cb.ax.tick_params(labelsize=7)
        how = "cell shading: how common the cell is; line colour: blue where its drops agree, red where they differ"
    else:
        how = "the more drops a cell holds, the darker and thicker its waveform; rare cells fade"
    ax.set_title(f"Fall time against amplitude on a uniform 10 x 10 grid, {len(g):,} drops ({how})", loc="left",
                 fontsize=10.5)
    save(fig, f"grid10_fall_amplitude_{mode}.png", S_GRIDS,
         f"The fall-time map again, on a uniform 10 x 10 grid (equal steps on log scales between the 1st and 99th "
         f"percentiles; the edge cells hold everything beyond). Each cell shows its medoid, the most typical real "
         f"drop, divided by its own amplitude, from half a column-width before its top to {post:g} after, and the "
         f"middle half of its drops behind it. "
         + ("Each cell is shaded by the share of all drops it holds (a probability map); the medoid is coloured "
            "blue where the cell's drops agree and red where they differ."
            if mode == "shaded" else
            "Each waveform's darkness and thickness follow how many drops the cell holds, so the common shapes "
            "stand out and the rare ones fade."), dpi=200)


def fig_shape_grid(ev, W, xs, ys, name, title, caption, mode="shaded", tau_max=TAU_HI):
    """A uniform 10 x 10 grid of median waveforms over two shape measures that do not depend on how long a drop
    lasts. `xs` / `ys`: dicts with col, log, label, fmt, and for x `never` (a last column for drops with no value),
    for y `invert` (the first bin at the top)."""
    keep = np.isfinite(ev[ys["col"]].to_numpy(float))
    g, Wg = ev[keep].reset_index(drop=True), W[keep]
    nx_fin = GRID_N - 1 if xs.get("never") else GRID_N
    xe, xi = uniform_bins(g[xs["col"]].to_numpy(float), log=xs["log"], n=nx_fin, lohi=xs.get("lohi"))
    if xs.get("never"):
        xi = np.where(xi < 0, GRID_N - 1, xi)
    ye, yi = uniform_bins(g[ys["col"]].to_numpy(float), log=ys["log"], lohi=ys.get("lohi"))
    if ys.get("invert"):
        yi = GRID_N - 1 - yi
    tau = np.linspace(TAU_LO, TAU_HI, TAU_N)
    cols = tau <= tau_max
    ok = (xi >= 0) & (yi >= 0) & np.all(np.isfinite(Wg[:, cols]), axis=1)
    counts, stats = {}, {}
    for i in range(GRID_N):
        for j in range(GRID_N):
            m = ok & (xi == i) & (yi == j)
            if not m.any():
                continue
            counts[(i, j)] = int(m.sum())
            if m.sum() >= 3:
                w = Wg[m][:, cols]
                stats[(i, j)] = (np.median(w, axis=0), np.percentile(w, 25, axis=0), np.percentile(w, 75, axis=0))
    fig, ax = plt.subplots(figsize=(15.5, 11.5))
    style = _cell_frame(ax, GRID_N, GRID_N, counts, mode, int(ok.sum()))
    for (i, j), (med, q25, q75) in stats.items():
        alpha, lw = style[(i, j)]
        _glyph(ax, i, j, med, q25, q75, colour=fs.INK, alpha=alpha, lw=lw, white_band=(mode == "shaded"))
    xt = list(range(nx_fin + 1))
    ax.set_xticks(xt + ([GRID_N - 0.5] if xs.get("never") else []))
    ax.set_xticklabels(_edge_labels(xe, xs["log"], xs["fmt"]) + (["never"] if xs.get("never") else []), fontsize=8)
    if xs.get("never"):
        ax.axvline(GRID_N - 1, color=fs.INK_2, lw=1.2, zorder=5)
    yl = _edge_labels(ye, ys["log"], ys["fmt"])
    ax.set_yticks(range(GRID_N + 1))
    ax.set_yticklabels(list(reversed(yl)) if ys.get("invert") else yl, fontsize=8)
    ax.set_xlabel(xs["label"])
    ax.set_ylabel(ys["label"])
    if mode == "shaded":
        _prob_colorbar(fig, int(ok.sum()), max(counts.values()), [0.915, 0.3, 0.011, 0.4])
    ax.set_title(title + f" ({int(ok.sum()):,} drops)", loc="left", fontsize=10.5)
    save(fig, name, S_GRIDS, caption, dpi=200)


GRID_STEEP = {"col": "steepness", "log": True, "invert": True, "fmt": lambda v: f"{v:.2g}x",
              "label": "Steepness: the steepest moment ÷ the average slope of the fall\n(shallow ramps at the top, "
                       "sudden cliffs at the bottom)"}
GRID_RECOVERY = {"col": "recovery_ratio", "log": True, "never": True, "fmt": lambda v: f"{v:.2g}x",
                 "label": "Time to climb half-way back ÷ time it took to fall (quick recoveries left; the last column "
                          "never climbed half-way back)"}
GRID_POSITION = {"col": "position", "log": False, "lohi": (0.0, 1.0), "fmt": lambda v: f"{v:.1f}",
                 "label": "Where in the fall the drop happens: the moment it is half-way down, as a fraction of its "
                          "fall time\n(0 = all at the start, 0.5 = evenly, 1 = all at the end)"}


def shape_grids(ev, W):
    fig_shape_grid(
        ev, W, GRID_RECOVERY, GRID_STEEP, "grid10_steepness_recovery_shaded.png",
        "How drop shape changes with steepness and recovery: each cell's median drop, time in units of its own "
        "fall time",
        "Two measures that do not depend on how long a drop lasts. Down the grid: steepness - how many times "
        "steeper the fall's steepest moment is than its average slope (top: gentle straight ramps; bottom: sudden "
        "cliffs). Across: how long the drop took to climb half-way back, divided by how long it took to fall (left: "
        "quick recoveries, V shapes; right: slow ones; last column: never climbed half-way back). Every drop is "
        "scaled to its own fall time (the fall runs from 0 to 1 of the glyph's time) and its own amplitude, so "
        "the glyphs show shape alone. Line: the cell's median drop; white band: its middle half; cell shading: "
        "how common the cell is.")
    fig_shape_grid(
        ev, W, GRID_RECOVERY, GRID_STEEP, "grid10_steepness_recovery_opacity.png",
        "The same grid, each waveform as dark and thick as its cell is common",
        "The same steepness-by-recovery grid, without shading: each waveform's darkness and thickness follow how "
        "many drops its cell holds, so the common shapes stand out and the rare ones fade.", mode="opacity")
    fig_shape_grid(
        ev, W, GRID_POSITION, GRID_STEEP, "grid10_steepness_position_shaded.png",
        "The anatomy of the fall: where it happens and how sudden it is (time in units of each drop's own fall "
        "time)",
        "Down: steepness (gentle ramps at the top, cliffs at the bottom). Across: where in the fall the drop "
        "happens - the moment it is half-way down, as a fraction of its fall time (left: it plunges at once and then "
        "creeps; middle: an even fall; right: it creeps first and plunges at the end). The glyphs show two fall "
        "times after the top, so the fall itself fills the left part of each glyph.", tau_max=2.0)
    fig_shape_grid(
        ev, W, GRID_RECOVERY, {**GRID_POSITION, "invert": False,
                               "label": "Where in the fall the drop happens (0 = plunges at once, at the bottom; "
                                        "1 = plunges at the end, at the top)"},
        "grid10_position_recovery_shaded.png",
        "Where the fall happens against how quickly it recovers (time in units of each drop's own fall time)",
        "Down: where in the fall the drop happens (bottom row: it plunges at once; top row: it creeps and then "
        "plunges at the end). Across: recovery time divided by fall time (last column: never climbed half-way "
        "back). Each glyph is the cell's median drop scaled to its own fall time and amplitude.")


FINGER_PAIRS = [
    ("fall_s", True, "Fall time (s)", "depth_mv", True, "Amplitude (mV)"),
    ("recovery_s", True, "Recovery: bottom to half recovery (s)", "depth_mv", True, "Amplitude (mV)"),
    ("fall_s", True, "Fall time (s)", "recovery_s", True, "Recovery (s)"),
    ("steepness", True, "Steepness (steepest ÷ average slope)", "depth_mv", True, "Amplitude (mV)"),
    ("recovery_ratio", True, "Recovery time ÷ fall time", "steepness", True, "Steepness"),
    ("position", False, "Where the fall happens (0 at once - 1 at the end)", "steepness", True, "Steepness"),
]


def fig_fingerprints(ev):
    """The species fingerprint (each species' densest half) for six pairings of measures."""
    sps = species_present(ev, least=15)
    fig, axes = plt.subplots(2, 3, figsize=(15.5, 10.0))
    for ax, (xc, xlog, xlab, yc, ylog, ylab) in zip(axes.ravel(), FINGER_PAIRS):
        g = ev[[xc, yc, "species"]].replace([np.inf, -np.inf], np.nan).dropna()
        if xlog:
            g = g[g[xc] > 0]
        if ylog:
            g = g[g[yc] > 0]
        X = np.log10(g[xc].to_numpy(float)) if xlog else g[xc].to_numpy(float)
        Y = np.log10(g[yc].to_numpy(float)) if ylog else g[yc].to_numpy(float)
        xl = np.percentile(X, [1, 99]) + np.array([-0.15, 0.15]) * np.ptp(np.percentile(X, [1, 99]))
        yl = np.percentile(Y, [1, 99]) + np.array([-0.15, 0.15]) * np.ptp(np.percentile(Y, [1, 99]))
        xx, yy = np.meshgrid(np.linspace(*xl, 160), np.linspace(*yl, 160))
        for sp in sps:
            m = (g["species"] == sp).to_numpy()
            if m.sum() < 15:
                continue
            kde = gaussian_kde(np.vstack([X[m], Y[m]]))
            zz = kde(np.vstack([xx.ravel(), yy.ravel()])).reshape(xx.shape)
            lv = _hdr_levels(zz, (0.5,))[0]
            c = fs.species_colour(sp)
            ax.contourf(xx, yy, zz, levels=[lv, zz.max()], colors=[c], alpha=0.3)
            ax.contour(xx, yy, zz, levels=[lv], colors=[c], linewidths=1.8)
            ax.plot(np.median(X[m]), np.median(Y[m]), "o", color=c, ms=6, mec="white", mew=1.0, zorder=5)
        ax.set_xlim(xl)
        ax.set_ylim(yl)
        if xlog or ylog:
            log_ticks(ax, x=xlog, y=ylog, minor=False)
        ax.set_xlabel(xlab, fontsize=8.5)
        ax.set_ylabel(ylab, fontsize=8.5)
    for sp in sps:
        axes[0, 0].plot([], [], color=fs.species_colour(sp), lw=6, alpha=0.5, label=sp)
    axes[0, 0].legend(fontsize=8, loc="lower right")
    fig.suptitle("Species fingerprints: where the densest half of each species' drops sits, for six pairs of "
                 "measures (dot: the median drop)", x=0.01, ha="left", fontsize=11.5)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    save(fig, "species_fingerprints.png", S_SPECIES,
         "Each species' fingerprint - the region holding the densest half of its drops - for six pairs of "
         "measures. Top: amplitude against fall time and against recovery, and fall time against recovery. "
         "Bottom: the time-free shape measures - steepness (how sudden the fall is), recovery time over fall time, "
         "and where in the fall the drop happens. Where the shapes separate, the species drop differently; where "
         "they overlap, the measure does not tell them apart.")


# ── the index page ───────────────────────────────────────────────────────────

def write_index():
    caps = _captions()
    by = {s: [] for s in SECTIONS}
    for name, c in sorted(caps.items()):
        if os.path.exists(os.path.join(OUT, name)):
            by.setdefault(c["section"], []).append((name, c["caption"]))
    html = ["<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>",
            "<title>Drop plots 23 Nov</title><style>",
            ":root{--bg:#fbfaf7;--ink:#1b1b1a;--ink2:#52514e;--rule:#e4e3df}",
            "@media (prefers-color-scheme:dark){:root{--bg:#1d1d1c;--ink:#ecebe6;--ink2:#b5b4ae;--rule:#3a3a38}}",
            "body{background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif;margin:0 auto;"
            "max-width:1500px;padding:16px}",
            "h1{font-size:22px}h2{font-size:18px;border-top:1px solid var(--rule);padding-top:14px;margin-top:28px}",
            "figure{margin:18px 0}img{max-width:100%;background:#fff;border:1px solid var(--rule)}",
            "figcaption{color:var(--ink2);font-size:13.5px;max-width:1100px}nav a{margin-right:14px}</style></head>",
            "<body><h1>Drop events and sequences: experimental plots (23 Nov 2026)</h1>",
            "<p>Read <a href='README.md'>README.md</a> first: it explains every plot in plain words and lists "
            "what came out. Click a figure to open it full size.</p><nav>"]
    html += [f"<a href='#s{k}'>{s}</a>" for k, s in enumerate(SECTIONS) if by.get(s)]
    html.append("</nav>")
    for k, s in enumerate(SECTIONS):
        if not by.get(s):
            continue
        html.append(f"<h2 id='s{k}'>{s}</h2>")
        for name, cap in by[s]:
            html.append(f"<figure><a href='{name}'><img loading='lazy' src='{name}' alt='{name}'></a>"
                        f"<figcaption><b>{name}</b> - {cap}</figcaption></figure>")
    html.append("</body></html>")
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write("\n".join(html))


# ── main ─────────────────────────────────────────────────────────────────────

def main(stages):
    fs.apply()
    os.makedirs(OUT, exist_ok=True)
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    recs = recordings(conn)
    every = "all" in stages
    if "events" in stages or not os.path.exists(os.path.join(OUT, "events.csv")):
        ev = build_events(conn, recs)
        ev.to_csv(os.path.join(OUT, "events.csv"), index=False)
        print(f"events: {len(ev)} ({(ev.source == 'catalogue').sum()} catalogue, {(ev.source == 'queue').sum()} "
              f"accepted in today's queues); width measured {ev.width_s.notna().sum()}")
        print(ev.groupby(["species", "dataset"]).size().to_string())
    ev = load_events()
    if every or "species" in stages:
        fig_anatomy(ev, recs)
        fig_species_boxes(ev)
        fig_species_rainclouds(ev)
        fig_species_plane(ev)
        fig_species_asymmetry(ev)
        fig_species_shapes(ev, recs)
        species_table(ev)
        print("species figures written", flush=True)
    if every or "map" in stages:
        for xcol, xlabel, stem, post in (("width_s", "Width: top to half recovery (s, log)", "width", POST_W),
                                         ("fall_s", "Fall time: top to bottom (s, log)", "fall", 5.0)):
            t0 = time.time()
            g, px, py, root, leaves = adaptive_cells(ev, recs, xcol, post)
            fig_map_medoids(g, px, py, root, leaves, xlabel, stem, post)
            fig_map_medoids(g, px, py, root, leaves, xlabel, stem, post, zoom=True)
            fig_map_heatmaps(g, px, py, root, leaves, xlabel, stem, post)
            fig_map_cells(g, px, py, root, leaves, xlabel, stem)
            levels = pd.Series([lf["level"] for lf in leaves]).value_counts().sort_index().to_dict()
            print(f"map {stem}: {len(g)} drops, {len(leaves)} cells (by level {levels}), "
                  f"{sum('W' in lf for lf in leaves)} glyphs ({time.time() - t0:.0f} s)", flush=True)
    if every or "grids" in stages:
        t0 = time.time()
        evs, W = with_shape_measures(ev, recs)
        fig_fall_grid10(evs, recs, "shaded")
        fig_fall_grid10(evs, recs, "opacity")
        shape_grids(evs, W)
        fig_fingerprints(evs)
        print(f"grids and fingerprints written ({time.time() - t0:.0f} s); steepness median "
              f"{np.nanmedian(evs.steepness):.2f}, position median {np.nanmedian(evs.position):.2f}, never half "
              f"recovered {evs.recovery_ratio.isna().sum()}", flush=True)
    if every or "sequences" in stages:
        if "sequences" in stages or not os.path.exists(os.path.join(OUT, "sequence_events.csv")):
            build_sequence_events(conn, recs, ev)
        metas, sev = load_sequence_events()
        rows = [fig_sequence(m, sev[sev["sequence_id"] == m["sequence_id"]].reset_index(drop=True), recs)
                for m in metas]
        pd.DataFrame(rows).to_csv(os.path.join(OUT, "sequence_summary.csv"), index=False)
        fig_sequences_overview(metas, sev)
        ch14_windows_sheet(conn, recs, ev)
        print(f"sequence figures written: {len(rows)}", flush=True)
    if every or "types" in stages:
        metas, sev = load_sequence_events()
        rows = []
        for m in metas:
            rows.append(fig_types(m, sev[sev["sequence_id"] == m["sequence_id"]].reset_index(drop=True), recs))
        rows = [r for r in rows if r]
        pd.DataFrame(rows).to_csv(os.path.join(OUT, "types_summary.csv"), index=False)
        kinds, trans = [], []
        for m in metas:
            got = fig_kinds(m, sev[sev["sequence_id"] == m["sequence_id"]].reset_index(drop=True), recs)
            if got:
                trans += got.pop("transitions")
                kinds.append(got)
                print(f"  kinds seq {m['sequence_id']}: {got['names']}", flush=True)
        pd.DataFrame(kinds).to_csv(os.path.join(OUT, "kinds_summary.csv"), index=False)
        pd.DataFrame(trans).to_csv(os.path.join(OUT, "kinds_transitions.csv"), index=False)
        print(f"types figures written: {len(rows)}; kinds figures: {len(kinds)}", flush=True)
    if every or "extra" in stages:
        metas, sev = load_sequence_events()
        for m in metas:
            fig_kymograph(m, sev[sev["sequence_id"] == m["sequence_id"]].reset_index(drop=True), recs)
        rel = fig_relaxation(metas, sev)
        pd.DataFrame(rel).to_csv(os.path.join(OUT, "wait_vs_depth.csv"), index=False)
        fig_raster(ev)
        fig_ccdf(ev)
        fig_shape_space(ev, recs)
        print("extra figures written", flush=True)
    conn.close()
    write_index()


if __name__ == "__main__":
    main(set(sys.argv[1:]) or {"all"})
