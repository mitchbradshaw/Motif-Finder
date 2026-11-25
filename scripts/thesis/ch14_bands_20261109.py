"""The MJu26a CH14 train's two amplitude bands (9 Nov, author's request), read-only.

The 530 measured spikes (event_hierarchy_20261108/ch14_individual_proposals.csv) fall in two depth bands that both
drift upward along the train. Each spike is placed by its depth relative to the local level of the lower band (the
rolling median depth of spikes of at least 4 mV within +-2 h, which the lower band dominates): upper band above 1.2x
that level, lower band otherwise; spikes under 4 mV are kept apart as the smallest. Per band: counts, depth, half
recovery, the gaps to the next spike of the same band and their LV; and how the bands interleave.
Writes docs/thesis/data/ch14_bands_20261109/ and figures ch10_ch14_train_bands, ch10_ch14_band_measures.
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
from scripts.thesis import figstyle as style  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

SRC = os.path.join(ROOT, "docs", "thesis", "data", "event_hierarchy_20261108", "ch14_individual_proposals.csv")
OUT = os.path.join(ROOT, "docs", "thesis", "data", "ch14_bands_20261109")
COL = {"upper": "#d4552b", "lower": "#2a78d6", "smallest": "#9a9893"}


def lv(t):
    i = np.diff(np.sort(t))
    i = i[i > 0]
    if len(i) < 3:
        return float("nan")
    return float(3.0 / (len(i) - 1) * np.sum(((i[:-1] - i[1:]) / (i[:-1] + i[1:])) ** 2))


def main():
    os.makedirs(OUT, exist_ok=True)
    d = pd.read_csv(SRC).sort_values("onset_s").reset_index(drop=True)
    d["t_h"] = d["onset_s"] / 3600.0
    d["depth"] = d["event_amplitude_mv"]
    big = d[d["depth"] >= 4.0]
    level = []
    for t in d["t_h"]:
        w = big[(big["t_h"] >= t - 2) & (big["t_h"] <= t + 2)]["depth"]
        level.append(float(w.median()) if len(w) else np.nan)
    d["lower_level"] = pd.Series(level).interpolate().bfill().ffill()
    # the median of a window holding both bands sits between them; take the lower band's level as the median of the
    # spikes below that first median, which the lower band dominates
    lev2 = []
    for t, m0 in zip(d["t_h"], d["lower_level"]):
        w = big[(big["t_h"] >= t - 2) & (big["t_h"] <= t + 2) & (big["depth"] <= m0 * 1.1)]["depth"]
        lev2.append(float(w.median()) if len(w) else m0)
    d["lower_level"] = lev2
    d["ratio"] = d["depth"] / d["lower_level"]
    d["band"] = np.where(d["depth"] < 4.0, "smallest", np.where(d["ratio"] > 1.2, "upper", "lower"))
    d.to_csv(os.path.join(OUT, "spikes_bands.csv"), index=False)

    split_h = float(d.loc[d["band"] == "upper", "t_h"].quantile(0.02))
    rows = []
    for b in ("upper", "lower", "smallest"):
        g = d[d["band"] == b]
        gaps = np.diff(g["onset_s"].to_numpy()) / 60.0
        rows.append({"band": b, "n": len(g), "first_h": float(g["t_h"].min()), "last_h": float(g["t_h"].max()),
                     "depth_median": float(g["depth"].median()), "depth_p5": float(g["depth"].quantile(.05)),
                     "depth_p95": float(g["depth"].quantile(.95)),
                     "half_recovery_median_s": float(g["recovery_time_s"].median()),
                     "gap_median_min": float(np.median(gaps)) if len(gaps) else np.nan,
                     "lv": lv(g["onset_s"].to_numpy())})
    late = d[d["t_h"] >= split_h]
    rows.append({"band": "all, from first upper", "n": len(late), "lv": lv(late["onset_s"].to_numpy()),
                 "gap_median_min": float(np.median(np.diff(late["onset_s"]) / 60))})
    early = d[d["t_h"] < split_h]
    rows.append({"band": "all, before first upper", "n": len(early), "lv": lv(early["onset_s"].to_numpy()),
                 "gap_median_min": float(np.median(np.diff(early["onset_s"]) / 60)) if len(early) > 1 else np.nan})
    tab = pd.DataFrame(rows)
    tab.to_csv(os.path.join(OUT, "bands_summary.csv"), index=False)
    # interleaving after the upper band appears: what follows an upper spike, against shuffled band labels
    ll = late[late["band"] != "smallest"]["band"].to_numpy()
    obs = float(np.mean(ll[1:][ll[:-1] == "upper"] == "lower"))
    rng = np.random.default_rng(20261109)
    null = []
    for _ in range(2000):
        s = rng.permutation(ll)
        null.append(np.mean(s[1:][s[:-1] == "upper"] == "lower"))
    null = np.array(null)
    inter = {"split_h": split_h, "upper_followed_by_lower": obs, "shuffled_mean": float(null.mean()),
             "p_more_alternation": (1 + int((null >= obs).sum())) / (len(null) + 1)}
    with open(os.path.join(OUT, "interleaving.json"), "w", encoding="utf-8") as f:
        json.dump(inter, f, indent=1)
    pd.set_option("display.width", 200)
    print(tab.round(3).to_string(index=False))
    print(inter)
    figures(d, split_h)


def figures(d, split_h):
    style.apply()
    db = os.path.join(ROOT, "DATA", "db", "annotations.sqlite").replace("\\", "/")
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    npy, fs, units = c.execute("SELECT npy_path, fs, units FROM recordings WHERE id = ?", (int(d["recording_id"].iloc[0]),)).fetchone()
    c.close()
    x = np.load(os.path.join(ROOT, npy), mmap_mode="r")
    k = 1000.0 if (units or "V") == "V" else 1.0
    a0, a1 = int((d["t_h"].min() - 0.5) * 3600 * fs), int((d["t_h"].max() + 0.5) * 3600 * fs)
    seg = np.asarray(x[a0:a1], dtype=float) * k
    step = int(60 * fs)
    nb = len(seg) // step
    blk = seg[:nb * step].reshape(nb, step)
    th = (a0 + np.arange(nb) * step + step / 2) / fs / 3600

    fig = plt.figure(figsize=(style.TEXT_WIDTH_IN, 5.6), layout="constrained")
    gs = fig.add_gridspec(3, 2, height_ratios=[1, 1.1, 1])
    ax = fig.add_subplot(gs[0, :])
    ax.fill_between(th, blk.min(1), blk.max(1), color=style.MUTED, lw=0)
    ax.set_ylabel("mV", fontsize=7)
    ax.set_title("(a) The 90.7-hour train on MJu26a CH14 (one-minute minimum and maximum)", fontsize=8, loc="left")
    ax.tick_params(labelsize=7)
    ax2 = fig.add_subplot(gs[1, :], sharex=ax)
    for b in ("smallest", "lower", "upper"):
        g = d[d["band"] == b]
        ax2.scatter(g["t_h"], g["depth"], s=6, color=COL[b], label=f"{b} ({len(g)})", lw=0)
    ax2.axvline(split_h, color=style.INK, lw=0.8, ls=":")
    ax2.set_ylabel("Depth, onset to trough (mV)", fontsize=7)
    ax2.set_title("(b) Each spike's depth, coloured by band; dotted: the upper band appears", fontsize=8, loc="left")
    ax2.legend(fontsize=6.5, loc="upper left", frameon=False)
    ax2.tick_params(labelsize=7)
    ax3 = fig.add_subplot(gs[2, :], sharex=ax)
    for b in ("lower", "upper"):
        g = d[d["band"] == b]
        ax3.scatter(g["t_h"].iloc[1:], np.diff(g["onset_s"]) / 60, s=6, color=COL[b], lw=0)
    ax3.set_ylabel("Gap to next spike\nof the same band (min)", fontsize=7)
    ax3.set_xlabel("Recording time (h)", fontsize=7)
    ax3.set_ylim(0, 40)
    ax3.set_title("(c) Spacing within each band", fontsize=8, loc="left")
    ax3.tick_params(labelsize=7)
    style.save(fig, "ch10_ch14_train_bands")
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(style.TEXT_WIDTH_IN, 2.4), layout="constrained")
    for b in ("lower", "upper"):
        g = d[d["band"] == b]
        axes[0].hist(g["ratio"], bins=np.arange(0.6, 2.0, 0.04), color=COL[b], alpha=0.8, label=b)
        axes[1].hist(g["recovery_time_s"].dropna(), bins=np.arange(0, 30, 1), color=COL[b], alpha=0.6, label=b)
        gaps = np.diff(g["onset_s"]) / 60
        axes[2].hist(gaps[gaps < 40], bins=np.arange(0, 40, 1.5), color=COL[b], alpha=0.6, label=b)
    axes[0].set_xlabel("Depth / local lower-band level", fontsize=7)
    axes[1].set_xlabel("Half-recovery time (s)", fontsize=7)
    axes[2].set_xlabel("Gap to next same-band spike (min)", fontsize=7)
    for a in axes:
        a.tick_params(labelsize=7)
    axes[0].set_ylabel("Spikes", fontsize=7)
    axes[0].legend(fontsize=6.5, frameon=False)
    style.save(fig, "ch10_ch14_band_measures")
    plt.close(fig)


if __name__ == "__main__":
    main()
