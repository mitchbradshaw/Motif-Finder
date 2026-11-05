"""
b1_intervals.py - round-B question B1's final read, read-only: are the intervals between events regular, bursty or
random, on every swept recording?

Protocol (fixed before the read; B1's first read was M2_aug only, Chapter 10):
  * unit: one channel's complete ``drop_detection_v1`` run (the same runs as B12: whole channel, not superseded, not a
    surrogate; the longest, latest run per channel); onsets = detection start / fs;
  * per channel, LV and CV2 against the two nulls of ``Working.interrogation.intervals.interval_nulls`` (1,000 seeded
    draws, the Intervals block's own code): a rate-matched Poisson train, and the channel's own gaps shuffled;
  * a two-sided p per channel, measure and null, with the direction (below the band = more regular than Poisson, or
    neighbouring gaps more alike than shuffled; above = burstier, or alternating);
  * Benjamini-Hochberg at 0.05 across all channels, separately for each measure x null (LV is primary, CV2 its
    companion); counts are also given per recording.
Data: M2_aug, M2_concat, CO_fs2, LM_fs2 and L_LM (the MJu26a channels until the 2 Hz sweep is imported). M4 and
S. commune are refused. Writes docs/thesis/data/ch10_b1/{b1_channels.csv, b1_summary.csv, b1_lv.png}.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/thesis/b1_intervals.py
"""
from __future__ import annotations

import os
import sqlite3
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))

from b12_shapes_intervals import REFUSED, SHORT, SPECIES, bh  # noqa: E402

OUT = os.path.join(ROOT, "docs", "thesis", "data", "ch10_b1")
TESTS = [(m, n) for m in ("lv", "cv2") for n in ("poisson", "shuffle")]


def channel_runs(c):
    q = ("SELECT DISTINCT r.id, r.recording_id, rec.source_file, rec.channel, rec.fs, r.span_start, r.span_end, "
         "rec.n_samples FROM runs r JOIN recordings rec ON rec.id = r.recording_id "
         "JOIN discovery_runs dr ON dr.run_group_id = r.run_group_id "
         "WHERE dr.template_name = 'drop_detection_v1' AND r.surrogate_of_run_id IS NULL AND r.status = 'completed' "
         "AND r.superseded_at IS NULL")
    runs = pd.DataFrame([tuple(r) for r in c.execute(q).fetchall()],
                        columns=["run", "recording_id", "source_file", "channel", "fs", "span_start", "span_end",
                                 "n_samples"])
    runs = runs[~runs["source_file"].isin(REFUSED) & runs["source_file"].isin(SHORT)]
    runs["len"] = runs["span_end"] - runs["span_start"]
    return runs.sort_values(["recording_id", "len", "run"]).drop_duplicates("recording_id", keep="last")


def measure(c, runs):
    from Working.interrogation.intervals import interval_nulls
    rows = []
    for _, r in runs.iterrows():
        on = np.array([s for (s,) in c.execute("SELECT start_idx FROM detections WHERE run_id = ?", (int(r.run),))],
                      dtype=float) / float(r.fs)
        nl = interval_nulls(on, resolution_s=1.0 / float(r.fs))
        row = {"run": int(r.run), "recording_id": int(r.recording_id), "dataset": SHORT[r.source_file],
               "species": SPECIES[SHORT[r.source_file]], "channel": int(r.channel),
               "hours": float(r.len / r.fs / 3600.0), "n_events": nl["n_events"],
               "caveat": nl.get("caveat") or nl.get("note")}
        for m, n in TESTS:
            s = (nl.get(n) or {}).get(m) or {}
            obs, lo, hi = s.get("observed"), s.get("lo"), s.get("hi")
            row[f"{m}"] = obs
            row[f"{m}_{n}_lo"], row[f"{m}_{n}_hi"], row[f"{m}_{n}_p"] = lo, hi, s.get("p")
            row[f"{m}_{n}_side"] = (None if obs is None or lo is None else
                                    "below" if obs < lo else "above" if obs > hi else "inside")
        rows.append(row)
    return pd.DataFrame(rows)


def correct(df):
    for m, n in TESTS:
        res = bh(df[f"{m}_{n}_p"].tolist())
        df[f"{m}_{n}_q"] = [q for q, _ in res]
        df[f"{m}_{n}_bh"] = [ok for _, ok in res]
    return df


def summary(df):
    rows = []
    for ds, g in list(df.groupby("dataset", sort=False)) + [("all", df)]:
        row = {"dataset": ds, "channels": len(g), "median_events": float(g["n_events"].median()),
               "median_lv": float(g["lv"].median()), "median_cv2": float(g["cv2"].median())}
        for m, n in TESTS:
            p = g[f"{m}_{n}_p"]
            row[f"{m}_{n}_p05"] = int((p < 0.05).sum())
            for side in ("below", "above"):
                row[f"{m}_{n}_bh_{side}"] = int((g[f"{m}_{n}_bh"] & (g[f"{m}_{n}_side"] == side)).sum())
        rows.append(row)
    return pd.DataFrame(rows)


def plot(df):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    order = list(dict.fromkeys(df["dataset"]))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, n, title in zip(axes, ("poisson", "shuffle"), ("against a rate-matched Poisson train",
                                                           "against the channel's own gaps, shuffled")):
        x = 0
        ticks = []
        for ds in order:
            g = df[df["dataset"] == ds].reset_index(drop=True)
            xs = x + np.arange(len(g))
            ax.vlines(xs, g[f"lv_{n}_lo"], g[f"lv_{n}_hi"], color="0.75", lw=4)
            col = np.where(g[f"lv_{n}_bh"], np.where(g[f"lv_{n}_side"] == "below", "tab:blue", "tab:red"), "0.3")
            ax.scatter(xs, g["lv"], c=col, s=18, zorder=3)
            ticks.append((x + (len(g) - 1) / 2, ds))
            x += len(g) + 2
        ax.axhline(1.0, ls="--", c="0.5", lw=0.8)
        ax.set_xticks([t for t, _ in ticks], [d for _, d in ticks], fontsize=8)
        ax.set_title(f"LV {title}", fontsize=9)
    axes[0].set_ylabel("LV per channel (drop_detection_v1)")
    fig.suptitle("B1: grey bar = the null's 95 % band; blue = below it, red = above it, after BH across 45 channels",
                 fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "b1_lv.png"), dpi=130)


def main():
    os.makedirs(OUT, exist_ok=True)
    db = os.path.join(ROOT, "DATA", "db", "annotations.sqlite").replace("\\", "/")
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    df = correct(measure(c, channel_runs(c)))
    df.to_csv(os.path.join(OUT, "b1_channels.csv"), index=False)
    s = summary(df)
    s.to_csv(os.path.join(OUT, "b1_summary.csv"), index=False)
    plot(df)
    pd.set_option("display.width", 250)
    print(s.to_string(index=False))


if __name__ == "__main__":
    main()
