"""Figures for Chapter 9's inventory section (9 Nov), from ch9_inventory_events_20261109.py's outputs (read-only):
ch9_inventory_measures (depth, fall time and half-recovery by recording) and ch9_inventory_families (the Ward
dendrogram of the single events, cut into 12 families, and each family's members with their median shape)."""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from scripts.thesis import figstyle as style  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

D = os.path.join(ROOT, "docs", "thesis", "data", "ch9_inventory_20261109")
ORDER = ["M2_aug", "M2_concat", "M4", "LM", "CO", "MJu26a", "SH", "SO"]


def measures_figure(m):
    s = m[m["status"] == "single"]
    cols = [("depth_mv", "Depth (mV)"), ("fall_s", "Fall time, onset to trough (s)"),
            ("half_recovery_s", "Half-recovery time (s)")]
    fig, axes = plt.subplots(1, 3, figsize=(style.TEXT_WIDTH_IN, 2.9), layout="constrained")
    for ax, (c, title) in zip(axes, cols):
        data = [s.loc[s["dataset"] == d, c].dropna().clip(lower=1e-2).to_numpy() for d in ORDER]
        bp = ax.boxplot(data, vert=False, whis=(5, 95), showfliers=False, widths=0.6, patch_artist=True,
                        medianprops={"color": style.INK, "lw": 1.2})
        for patch, d in zip(bp["boxes"], ORDER):
            patch.set_facecolor(style.colour(d))
            patch.set_alpha(0.75)
            patch.set_edgecolor(style.INK)
        ax.set_xscale("log")
        ax.set_title(title, fontsize=8)
        ax.set_yticks(range(1, len(ORDER) + 1))
        ax.set_yticklabels([f"{d} ({int(((s['dataset'] == d) & s[c].notna()).sum())})" for d in ORDER]
                           if c == "depth_mv" else [""] * len(ORDER), fontsize=7)
        ax.invert_yaxis()
        ax.tick_params(labelsize=7)
        ax.grid(axis="x", color=style.GRID, lw=0.6)
    style.save(fig, "ch9_inventory_measures")
    plt.close(fig)


def families_figure(fam, X, Z, info):
    from scipy.cluster.hierarchy import dendrogram
    k = info["families"]
    fig = plt.figure(figsize=(style.TEXT_WIDTH_IN, 6.4), layout="constrained")
    grid = fig.add_gridspec(4, 4, height_ratios=[1.15, 1, 1, 1])
    ax = fig.add_subplot(grid[0, :])
    d = dendrogram(Z, truncate_mode="lastp", p=k, ax=ax, no_labels=True, color_threshold=0,
                   above_threshold_color=style.INK)
    ax.set_ylabel("Ward distance", fontsize=7)
    ax.tick_params(labelsize=7)
    ax.set_xticks([])
    ax.spines[["right", "top", "bottom"]].set_visible(False)
    # label each leaf of the truncated tree with the family it is (leaf order follows the dendrogram)
    labels = fam["family"].to_numpy()
    leaves = d["leaves"]
    xs = sorted(np.mean(icoord[1:3]) for icoord, dcoord in zip(d["icoord"], d["dcoord"]))
    leaf_x = np.arange(5, 10 * len(leaves), 10)
    from scipy.cluster.hierarchy import fcluster, leaves_list
    order = leaves_list(Z)
    seen = []
    for f in labels[order]:
        if f not in seen:
            seen.append(int(f))
    name = {f: i + 1 for i, f in enumerate(seen)}
    for x, f in zip(leaf_x, seen):
        n = int((labels == f).sum())
        ax.text(x, -0.02, f"F{name[f]}\n{n}", ha="center", va="top", fontsize=6.5, transform=ax.get_xaxis_transform())
    t = np.linspace(0, 1, X.shape[1])
    for i, f in enumerate(seen):
        a = fig.add_subplot(grid[1 + i // 4, i % 4])
        members = X[labels == f]
        rng = np.random.default_rng(i)
        show = members[rng.choice(len(members), size=min(40, len(members)), replace=False)]
        for v in show:
            a.plot(t, v, color=style.MUTED, lw=0.4, alpha=0.35)
        a.plot(t, np.median(members, axis=0), color=style.INK, lw=1.4)
        g = fam[fam["family"] == f]
        a.set_title(f"F{name[f]}: {len(g)} events, {g['dataset'].nunique()} recordings", fontsize=7)
        a.set_xticks([])
        a.set_yticks([])
        for sp in a.spines.values():
            sp.set_color(style.GRID)
    style.save(fig, "ch9_inventory_families")
    plt.close(fig)
    return {f: name[f] for f in seen}


def main():
    style.apply()
    m = pd.read_csv(os.path.join(D, "measures.csv"))
    measures_figure(m)
    fam = pd.read_csv(os.path.join(D, "families.csv"))
    X = np.load(os.path.join(D, "shape_vectors.npy"))
    Z = np.load(os.path.join(D, "linkage.npy"))
    info = json.load(open(os.path.join(D, "grouping.json"), encoding="utf-8"))
    names = families_figure(fam, X, Z, info)
    with open(os.path.join(D, "family_display_names.json"), "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in names.items()}, f, indent=1)
    print("display names (cluster -> F#):", names)


if __name__ == "__main__":
    main()
