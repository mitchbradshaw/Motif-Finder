"""Figure 10.1 replacement (9 Nov, author's request): how a train of events is measured, on a stretch of the fully
reviewed MJu26a CH14 train, where every spike was judged, instead of a drop-detector census that misses events.
Reads docs/thesis/data/ch14_bands_20261109/spikes_bands.csv and the channel (read-only). Writes figure
ch10_train_example and data/ch14_bands_20261109/train_example.json."""
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

D = os.path.join(ROOT, "docs", "thesis", "data", "ch14_bands_20261109")
COL = {"upper": "#d4552b", "lower": "#2a78d6", "smallest": "#9a9893"}
T0 = float(sys.argv[1]) if len(sys.argv) > 1 else 440.0
SPAN_H = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0


def measures(on):
    i = np.diff(np.sort(on))
    cv = float(np.std(i) / np.mean(i))
    cv2 = float(np.mean(2 * np.abs(i[1:] - i[:-1]) / (i[1:] + i[:-1])))
    lv = float(3.0 / (len(i) - 1) * np.sum(((i[:-1] - i[1:]) / (i[:-1] + i[1:])) ** 2))
    return cv, cv2, lv


def main():
    d = pd.read_csv(os.path.join(D, "spikes_bands.csv"))
    rid = int(d["recording_id"].iloc[0])
    db = os.path.join(ROOT, "DATA", "db", "annotations.sqlite").replace("\\", "/")
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    npy, fs, units = c.execute("SELECT npy_path, fs, units FROM recordings WHERE id = ?", (rid,)).fetchone()
    c.close()
    x = np.load(os.path.join(ROOT, npy), mmap_mode="r")
    k = 1000.0 if (units or "V") == "V" else 1.0
    t1 = T0 + SPAN_H
    w = d[(d["t_h"] >= T0) & (d["t_h"] < t1)].sort_values("onset_s")
    a0, a1 = int(T0 * 3600 * fs), int(t1 * 3600 * fs)
    seg = np.asarray(x[a0:a1], dtype=float) * k
    th = (a0 + np.arange(len(seg))) / fs / 3600.0
    on = w["onset_s"].to_numpy()
    cv, cv2, lv = measures(on)
    gaps_min = np.diff(on) / 60.0

    style.apply()
    fig, ax = plt.subplots(figsize=(style.TEXT_WIDTH_IN, 2.5), layout="constrained")
    ax.plot(th, seg, color=style.INK, lw=0.4, rasterized=True)
    top = float(np.percentile(seg, 99.9))
    lo = float(seg.min())
    rng = top - lo
    for _, r in w.iterrows():
        ax.plot([r["t_h"]], [top + 0.06 * rng], marker="v", ms=4, color=COL[r["band"]], lw=0)
    for i, g in enumerate(gaps_min):
        mid = (on[i] + on[i + 1]) / 2 / 3600.0
        ax.text(mid, top + 0.15 * rng, f"{g:.0f}", ha="center", va="bottom", fontsize=6, color=style.INK)
    ax.set_ylim(lo - 0.03 * rng, top + 0.30 * rng)
    ax.set_xlim(T0, t1)
    ax.set_xlabel("Recording time (h)", fontsize=7)
    ax.set_ylabel("mV", fontsize=7)
    ax.tick_params(labelsize=7)
    for b, lab in (("lower", "lower band"), ("upper", "upper band"), ("smallest", "shallow")):
        if (w["band"] == b).any():
            ax.plot([], [], marker="v", ms=4, lw=0, color=COL[b], label=f"{lab} ({int((w['band'] == b).sum())})")
    ax.legend(fontsize=6.5, frameon=False, loc="lower left", ncol=3)
    style.save(fig, "ch10_train_example")
    plt.close(fig)
    out = {"t0_h": T0, "t1_h": t1, "n": int(len(w)), "n_lower": int((w["band"] == "lower").sum()),
           "n_upper": int((w["band"] == "upper").sum()), "n_small": int((w["band"] == "smallest").sum()),
           "gap_min_min": float(gaps_min.min()), "gap_max_min": float(gaps_min.max()),
           "gap_median_min": float(np.median(gaps_min)), "cv": cv, "cv2": cv2, "lv": lv,
           "lv_lower": measures(w.loc[w["band"] == "lower", "onset_s"].to_numpy())[2] if (w["band"] == "lower").sum() > 3 else None,
           "lv_upper": measures(w.loc[w["band"] == "upper", "onset_s"].to_numpy())[2] if (w["band"] == "upper").sum() > 3 else None}
    with open(os.path.join(D, "train_example.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
