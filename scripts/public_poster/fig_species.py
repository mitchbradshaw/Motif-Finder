"""Public poster: how the five species converge and separate (fingerprints) and how they compare (box plots).

Fingerprints: each species' densest half of drops (the 50 % highest-density region of a kernel density estimate on
log axes), drawn as a filled blob with its median drop as a dot.
* left: shape alone (steepness against recovery speed, both read at 1 Hz so the 1 Hz and 2 Hz recordings compare
  fairly) - where the species converge;
* right: size and speed (depth against fall time) - where they separate.
Box plots: fall time and depth by species, every drop as a faint dot behind the box (a random sample where a species
has thousands), and how often drops come (per electrode per day).

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/public_poster/fig_species.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import style as S  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import to_rgba  # noqa: E402
import matplotlib.patheffects as pe  # noqa: E402

RNG = np.random.default_rng(20261125)
HOURS = {"M2_aug": 721, "M4": 505, "MJu26a": 636, "CO": 480, "LM": 480, "SH": 480, "SO": 480}   # per channel
CHANNELS = {"M2_aug": 16, "M4": 16, "MJu26a": 16, "CO": 4, "LM": 4, "SH": 4, "SO": 4}
BW = 1.5      # smoother than Scott's rule: one blob per species, not every small island
ORDER = ["chocolate oyster", "oyster", "snow oyster", "lion's mane", "Asian shiitake"]   # by median fall time


def load():
    ev = pd.read_parquet(os.path.join(S.DATA, "drops.parquet"))
    return ev


def hdr(x, y, frac=0.5, n_max=5000, grid=200, pad=0.25):
    """Grid, density and the level that encloses `frac` of the points (x, y already on log axes)."""
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if len(x) > n_max:
        k = RNG.choice(len(x), n_max, replace=False)
        x, y = x[k], y[k]
    kde = gaussian_kde(np.vstack([x, y]))
    kde.set_bandwidth(kde.factor * BW)
    xg = np.linspace(x.min() - pad, x.max() + pad, grid)
    yg = np.linspace(y.min() - pad, y.max() + pad, grid)
    X, Y = np.meshgrid(xg, yg)
    Z = kde(np.vstack([X.ravel(), Y.ravel()])).reshape(X.shape)
    dens = np.sort(kde(np.vstack([x, y])))
    level = dens[int((1 - frac) * len(dens))]
    return X, Y, Z, level, (np.median(x), np.median(y))


def log_axis(ax, which, ticks, fmt="{:g}"):
    t = np.log10(ticks)
    if which == "x":
        ax.set_xticks(t)
        ax.set_xticklabels([fmt.format(v) for v in ticks])
    else:
        ax.set_yticks(t)
        ax.set_yticklabels([fmt.format(v) for v in ticks])


def blobs(ax, ev, xcol, ycol, label_offsets=None):
    for sp in ORDER:
        g = ev[ev["species"] == sp]
        x = np.log10(g[xcol].to_numpy(float))
        y = np.log10(g[ycol].to_numpy(float))
        X, Y, Z, level, (mx, my) = hdr(x, y)
        c = S.SPECIES_COLOUR[sp]
        ax.contourf(X, Y, Z, levels=[level, Z.max() * 2], colors=[to_rgba(c, 0.18)], zorder=1)
        ax.contour(X, Y, Z, levels=[level], colors=[c], linewidths=3.2, zorder=2)
        ax.scatter([mx], [my], s=150, color=c, edgecolor="white", linewidth=2.2, zorder=4)


def fingerprints(w_mm=232, h_mm=115):
    S.apply(base=16)
    ev = load()
    ev = ev[np.isfinite(ev["recovery_ratio"])]
    fig = S.figure(w_mm, h_mm)
    ax1 = fig.add_axes([0.095, 0.17, 0.375, 0.6])
    ax2 = fig.add_axes([0.6, 0.17, 0.375, 0.6])
    x = 0.02
    for sp in S.SPECIES_ORDER:
        fig.text(x, 0.955, "●", color=S.SPECIES_COLOUR[sp], fontsize=24, va="center")
        t = fig.text(x + 0.032, 0.952, S.SPECIES_LABEL[sp], color=S.SPECIES_COLOUR[sp], fontsize=17,
                     fontweight="bold", va="center")
        x += 0.05 + 0.0135 * len(S.SPECIES_LABEL[sp])
    blobs(ax1, ev, "recovery_ratio", "steepness_1hz",
          {"chocolate oyster": (0.12, 0.09), "oyster": (0.1, -0.06), "snow oyster": (0.12, 0.12),
           "lion's mane": (-0.08, 0.1), "Asian shiitake": (-0.08, 0.09)})
    log_axis(ax1, "x", [0.2, 0.5, 1, 2, 5, 10, 20], "{:g}×")
    log_axis(ax1, "y", [1, 1.5, 2, 3, 4], "{:g}×")
    ax1.set_xlim(np.log10(0.15), np.log10(30))
    ax1.set_ylim(np.log10(1.0), np.log10(4.5))
    ax1.set_xlabel("Half recovery ÷ fall time")
    ax1.set_ylabel("Steepness")
    ax1.set_title("SHAPE: species converge", loc="left", fontsize=19, fontweight="bold", color=S.PURPLE, pad=10)
    blobs(ax2, ev, "fall_s", "depth_mv",
          {"chocolate oyster": (-0.06, 0.12), "oyster": (0.08, 0.17), "snow oyster": (0.1, -0.2),
           "lion's mane": (-0.1, -0.22), "Asian shiitake": (0.1, 0.12)})
    log_axis(ax2, "x", [1, 3, 10, 30, 100, 300])
    log_axis(ax2, "y", [0.3, 1, 3, 10])
    ax2.set_xlim(np.log10(1.0), np.log10(400))
    ax2.set_ylim(np.log10(0.2), np.log10(15))
    ax2.set_xlabel("Fall time (s)")
    ax2.set_ylabel("Depth (mV)")
    ax2.set_title("TIME SCALE: species separate", loc="left", fontsize=19, fontweight="bold", color=S.PURPLE,
                  pad=10)
    for ax in (ax1, ax2):
        ax.grid(True, color=S.GRID, lw=1.0, zorder=0)
    S.save(fig, "species_fingerprints")


def boxes(w_mm=166, h_mm=115):
    """Horizontal box plots, species down the side (labelled once), three measures across."""
    S.apply(base=16)
    ev = load()
    fig = S.figure(w_mm, h_mm)
    axes = [fig.add_axes([0.285 + k * 0.245, 0.17, 0.21, 0.68]) for k in range(3)]
    panels = [("fall_s", "Fall time", "s", [1, 10, 100]),
              ("recovery_s", "Recovery", "s", [1, 10, 100]),
              ("depth_mv", "Depth", "mV", [0.3, 3, 30])]
    rows = list(reversed(ORDER))
    for ax, (col, title, unit, ticks) in zip(axes, panels):
        for k, sp in enumerate(rows):
            v = ev.loc[ev["species"] == sp, col].to_numpy(float)
            v = v[np.isfinite(v) & (v > 0)]
            lv = np.log10(v)
            c = S.SPECIES_COLOUR[sp]
            s_ = RNG.choice(len(lv), min(350, len(lv)), replace=False)
            ax.scatter(lv[s_], k + RNG.uniform(-0.3, 0.3, len(s_)), s=6, color=c, alpha=0.28, lw=0, zorder=1)
            q1, q2, q3 = np.percentile(lv, [25, 50, 75])
            lo, hi = np.percentile(lv, [5, 95])
            ax.add_patch(plt.Rectangle((q1, k - 0.34), q3 - q1, 0.68, facecolor=to_rgba(c, 0.9), edgecolor=c, lw=2,
                                       zorder=2))
            ax.plot([q2, q2], [k - 0.34, k + 0.34], color="white", lw=4, zorder=3, solid_capstyle="butt")
            ax.plot([lo, q1], [k, k], color=c, lw=2.6, zorder=2)
            ax.plot([q3, hi], [k, k], color=c, lw=2.6, zorder=2)
        log_axis(ax, "x", ticks)
        ax.set_xlim(np.log10(ticks[0]) - 0.35, np.log10(ticks[-1]) + 0.6)
        ax.set_ylim(-0.6, len(rows) - 0.4)
        ax.set_title(title, fontsize=18, fontweight="bold", color=S.INK, loc="left", pad=8)
        ax.set_xlabel(unit, fontsize=15, color=S.INK_2)
        ax.grid(True, axis="x", color=S.GRID, lw=1.0, zorder=0)
        ax.set_yticks(range(len(rows)))
        if ax is axes[0]:
            ax.set_yticklabels([S.SPECIES_LABEL[sp] for sp in rows], fontsize=16)
            for t, sp in zip(ax.get_yticklabels(), rows):
                t.set_color(S.SPECIES_COLOUR[sp])
                t.set_fontweight("bold")
        else:
            ax.set_yticklabels([])
            ax.tick_params(axis="y", length=0)
    S.save(fig, "species_boxes")


if __name__ == "__main__":
    fingerprints()
    boxes()
