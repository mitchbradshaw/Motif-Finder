"""Public poster: the 20 x 20 waveform map (the hero figure of the waveform half).

Every drop is stretched so that it falls for exactly one unit of time and is exactly one unit deep: what is left is
pure shape. Two shape numbers place it on the grid:
* down: steepness - how many times steeper the fall's steepest moment is than its average slope (1 = a straight
  ramp; 10 = a sudden cliff);
* across: recovery - the time to climb half-way back divided by the time it took to fall (0.1 = snaps straight back;
  10 = creeps back; the last column never climbed half-way back).
Each cell's colour is how many drops land in it; its line is the cell's median drop, its band the middle half.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/public_poster/fig_wavemap.py [light|dark]
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import style as S  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, LogNorm, to_rgb  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

N = 20
TAU_LO, TAU_HI, TAU_N = -0.5, 5.0, 111
TAU_SHOW = 5.0
Y_TOP, Y_BOT = 0.35, -1.25        # glyph value range drawn in a cell (0 = top of the drop, -1 = its bottom)
MIN_N = 6
Y_PCT = 99.0
X_PCT = (1.0, 99.0)

LIGHT = LinearSegmentedColormap.from_list(
    "poster_heat", ["#fff6d5", "#ffd36b", "#ff9a3d", "#f2545b", "#c42a7e", "#7d1f8c", "#3d0f5e", "#1c0533"])
DARK = plt.get_cmap("magma")


def load():
    ev = pd.read_parquet(os.path.join(S.DATA, "drops.parquet"))
    W = np.load(os.path.join(S.DATA, "drop_shapes.npy"))
    return ev, W


def bins(ev):
    """Uniform log bins. Steepness: 1x (a straight ramp) to its 99th percentile; recovery: its 1st to 99th
    percentile. Values beyond either end go into the end cells, so no drop is dropped."""
    st = ev["steepness"].to_numpy(float)
    rr = ev["recovery_ratio"].to_numpy(float)
    ok = np.isfinite(st)
    ly = np.log10(np.clip(st, 1.0, None))
    y_lo, y_hi = 0.0, float(np.nanpercentile(ly[ok], Y_PCT))
    yi = np.clip(np.floor((ly - y_lo) / (y_hi - y_lo) * N), 0, N - 1)
    yi = np.where(ok, yi, -1).astype(int)
    fin = np.isfinite(rr) & (rr > 0)
    lx = np.where(fin, np.log10(np.where(fin, rr, 1.0)), np.nan)
    x_lo, x_hi = float(np.nanpercentile(lx, X_PCT[0])), float(np.nanpercentile(lx, X_PCT[1]))
    xi = np.clip(np.floor((lx - x_lo) / (x_hi - x_lo) * (N - 1)), 0, N - 2)
    xi = np.where(fin, xi, N - 1).astype(int)          # the last column: never climbed half-way back
    return xi, yi, (x_lo, x_hi), (y_lo, y_hi)


def cell_stats(ev, W, xi, yi):
    tau = np.linspace(TAU_LO, TAU_HI, TAU_N)
    cols = tau <= TAU_SHOW + 1e-9
    ok = np.asarray(ev["shape_ok"]) & (xi >= 0) & (yi >= 0)
    counts, stats = np.zeros((N, N), int), {}
    for i in range(N):
        for j in range(N):
            m = ok & (xi == i) & (yi == j)
            counts[j, i] = int(m.sum())
            if m.sum() >= MIN_N:
                w = W[m][:, cols]
                stats[(i, j)] = (np.median(w, axis=0), np.percentile(w, 25, axis=0), np.percentile(w, 75, axis=0))
    return tau[cols], counts, stats, int(ok.sum())


def luminance(rgb):
    r, g, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


#: Call-outs on the map: (number, column, row). Column 19 is "never came back"; row 0 the gentlest falls.
BADGES = [(1, 8, 5), (2, 19, 9), (3, 0, 19), (4, 4, 12), (5, 1, 0)]
#: Where each badge sits, in cell units from the cell's top-left corner.
BADGE_AT = {1: (0.0, 0.0), 2: (0.0, 0.0), 3: (1.0, 0.0), 4: (0.0, 0.0), 5: (0.5, 1.0)}


def badge(ax, num, i, j):
    dx, dy = BADGE_AT.get(num, (0.0, 0.0))
    cx, cy = i + dx, j + dy
    ax.scatter([cx], [cy], s=560, marker="o", facecolor="white", edgecolor=S.PURPLE, linewidths=3.0, zorder=8,
               clip_on=False)
    ax.text(cx, cy + 0.03, str(num), ha="center", va="center", fontsize=17, fontweight="bold", color=S.PURPLE,
            zorder=9, clip_on=False)


def draw(theme="light", w_mm=318, h_mm=210, name=None):
    S.apply(base=17)
    ev, W = load()
    xi, yi, (x_lo, x_hi), (y_lo, y_hi) = bins(ev)
    tau, counts, stats, n_drawn = cell_stats(ev, W, xi, yi)
    cmap = LIGHT if theme == "light" else DARK
    norm = LogNorm(vmin=1, vmax=counts.max())
    fig = S.figure(w_mm, h_mm)
    ax = fig.add_axes([0.085, 0.125, 0.905, 0.86])
    ax.set_xlim(0, N)
    ax.set_ylim(N, 0)                 # row 0 (gentle ramps) at the top
    gap = 0.045
    for j in range(N):
        for i in range(N):
            n = counts[j, i]
            if n == 0:
                continue
            face = cmap(norm(n))
            ax.add_patch(Rectangle((i + gap, j + gap), 1 - 2 * gap, 1 - 2 * gap, facecolor=face, edgecolor="none",
                                   zorder=1))
            if (i, j) not in stats:
                continue
            med, q25, q75 = stats[(i, j)]
            dark_bg = luminance(to_rgb(face)) < 0.28
            line = "white" if dark_bg else S.INK
            xs = i + 0.08 + (tau - tau[0]) / (tau[-1] - tau[0]) * 0.84

            def yv(v):
                return j + 0.1 + (Y_TOP - np.clip(v, Y_BOT, Y_TOP)) / (Y_TOP - Y_BOT) * 0.8
            ax.fill_between(xs, yv(q25), yv(q75), color=line, alpha=0.2, lw=0, zorder=2)
            lw = 1.1 + 1.5 * norm(n)
            ax.plot(xs, yv(med), color=line, lw=lw, solid_capstyle="round", zorder=3)
    ax.axvline(N - 1, color=S.INK_2, lw=2.4, zorder=4)
    for num, i, j in BADGES:
        badge(ax, num, i, j)
    xe = np.linspace(x_lo, x_hi, N)
    xt = [k for k in range(0, N - 1, 3)]
    ax.set_xticks(xt + [N - 0.5])
    ax.set_xticklabels([f"{10 ** xe[k]:.2g}×" for k in xt] + ["never"])
    ye = np.linspace(y_lo, y_hi, N + 1)
    yt = list(range(0, N + 1, 4))
    ax.set_yticks(yt)
    ax.set_yticklabels([f"{10 ** ye[k]:.2g}×" for k in yt])
    ax.set_xlabel("Recovery rate:  time to half recovery ÷ fall time", labelpad=6)
    ax.set_ylabel("Steepness:  steepest gradient ÷ mean gradient of the fall", labelpad=6)
    S.save(fig, name or "wavemap")
    # the colour key, on its own
    fig = S.figure(80, 22)
    cax = fig.add_axes([0.06, 0.55, 0.88, 0.22])
    sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    cb = fig.colorbar(sm, cax=cax, orientation="horizontal")
    cb.outline.set_visible(False)
    ticks = [t for t in (1, 3, 10, 30, 100, 300, 1000) if t <= counts.max()]
    cb.set_ticks(ticks)
    cb.set_ticklabels([str(t) for t in ticks])
    cb.ax.tick_params(labelsize=13)
    S.save(fig, "wavemap_colorbar", transparent=True)
    # the legend's little drops: each badge cell's median shape
    for num, i, j in BADGES:
        if (i, j) not in stats:
            continue
        med, q25, q75 = stats[(i, j)]
        fig = S.figure(34, 20)
        a2 = fig.add_axes([0.02, 0.06, 0.96, 0.88])
        a2.fill_between(tau, q25, q75, color=S.PURPLE, alpha=0.15, lw=0)
        a2.plot(tau, med, color=S.PURPLE, lw=3.4, solid_capstyle="round")
        a2.set_ylim(Y_BOT, Y_TOP)
        a2.axis("off")
        S.save(fig, f"wavemap_icon_{num}", transparent=True)
    occupied = (counts > 0).sum()
    info = {"drops_on_map": int(n_drawn), "occupied_cells": int(occupied), "glyph_cells": len(stats),
            "busiest_cell": int(counts.max()), "badge_counts": {str(n): int(counts[j, i]) for n, i, j in BADGES},
            "never_share": float(counts[:, N - 1].sum() / counts.sum()),
            "x_range": [float(10 ** x_lo), float(10 ** x_hi)], "y_range": [1.0, float(10 ** y_hi)]}
    import json
    json.dump(info, open(os.path.join(S.DATA, "wavemap.json"), "w"), indent=1)
    np.save(os.path.join(S.DATA, "wavemap_counts.npy"), counts)
    print(info)
    return counts, stats


if __name__ == "__main__":
    draw(sys.argv[1] if len(sys.argv) > 1 else "light")
