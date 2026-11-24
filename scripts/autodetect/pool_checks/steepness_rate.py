"""
steepness_rate.py
=================
Is "steepness" (the 23 Nov drop plots' fall anatomy: the fall's steepest moment against its average slope) a property
of the drops, or of the sampling rate?

In the pool's plots the 10 Hz recordings (M1, L_R_Aug_26_PD, F2B) form their own group of cliff-like falls, apart from
every 1-2 Hz recording. The measure reads the stored trace from top to bottom (`drop_plots_20261123.fall_anatomy`),
and a fall resolved at 10 Hz has five times the samples of the same fall at 2 Hz. So this check re-measures a random
sample of the 10 Hz drops on their own trace thinned to 2 Hz (block means of five, as the search saw it) and compares.
It also prints each dataset's median steepness and the share of M1's drops whose width sits at the long end
(>= 900 s), the ceiling seen in its boxplots.

A side check of the 24 Nov drop pool. Read-only: the pool's events.csv and event_shapes.npz (pool_plots.py), the
channels. Output: docs/autodetect/20261124_pool/checks/steepness_rate.out.txt.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/autodetect/pool_checks/steepness_rate.py
"""
from __future__ import annotations

import os
import sqlite3
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # the repo
sys.path.insert(0, os.path.join(ROOT, "scripts", "library_analysis"))
os.chdir(ROOT)
import drop_plots_20261123 as dp  # noqa: E402

POOL = os.path.join(ROOT, "DATA", "derived", "autodetect", "pool_20261124")
N = 3000
SEED = 20261125


def main():
    ev = pd.read_csv(os.path.join(POOL, "events.csv"))
    z = np.load(os.path.join(POOL, "event_shapes.npz"))
    ids = z["event_id"].astype(str)
    st = pd.Series(z["steepness"], index=ids)
    ev["steepness"] = ev["event_id"].map(st)
    print("== median steepness by dataset (core events; the stored rate) ==")
    print(ev.groupby(["fs", "dataset"])["steepness"].agg(["size", "median"]).round(2).to_string(), "\n")

    conn = sqlite3.connect(f"file:{dp.DB}?mode=ro", uri=True)
    recs = dp.recordings(conn)
    ten = ev[(ev["fs"] == 10.0) & ev["steepness"].notna()]
    pick = ten.sample(n=min(N, len(ten)), random_state=SEED)
    rows = []
    for r in pick.itertuples():
        top, bottom = int(r.top_idx), int(r.bottom_idx)
        a = top - (top % 5)
        b = bottom + 5 - (bottom % 5)
        seg10 = dp.window(recs, int(r.recording_id), top, bottom + 1)
        segw = dp.window(recs, int(r.recording_id), a, b)
        if seg10 is None or segw is None or len(segw) < 10:
            continue
        seg2 = segw.reshape(-1, 5).mean(axis=1)
        s10, _ = dp.fall_anatomy(seg10)
        s2, _ = dp.fall_anatomy(seg2)
        rows.append({"dataset": r.dataset, "steep_10hz": s10, "steep_2hz": s2, "fall_s": r.fall_s})
    d = pd.DataFrame(rows)
    print(f"== {len(d):,} random 10 Hz core drops, steepness on the stored 10 Hz trace and on the same trace at 2 Hz ==")
    print(d.groupby("dataset")[["steep_10hz", "steep_2hz"]].median().round(2).to_string())
    print(f"all: median {d['steep_10hz'].median():.2f} at 10 Hz, {d['steep_2hz'].median():.2f} at 2 Hz; "
          f"share above 4: {(d['steep_10hz'] > 4).mean():.0%} at 10 Hz, {(d['steep_2hz'] > 4).mean():.0%} at 2 Hz\n")
    one2 = ev[ev["fs"] <= 2.0]
    print(f"1-2 Hz recordings: median steepness {one2['steepness'].median():.2f}; share above 4: "
          f"{(one2['steepness'] > 4).mean():.0%}\n")

    m1 = ev[ev["dataset"] == "M1"]
    long_w = (m1["width_s"] >= 900).mean()
    long_f = (m1["fall_s"] >= 600).mean()
    print(f"M1: {len(m1):,} core events; width >= 900 s: {long_w:.1%}; fall >= 600 s: {long_f:.1%}; "
          f"their median depth {m1.loc[m1['fall_s'] >= 600, 'depth_mv'].median():.1f} mV against "
          f"{m1['depth_mv'].median():.2f} mV for all M1")
    for d_ in ("L_R_Aug_26_PD", "MJu26a", "M2_aug", "Cordyceps"):
        g = ev[ev["dataset"] == d_]
        print(f"{d_}: width >= 900 s {(g['width_s'] >= 900).mean():.1%}; fall >= 600 s {(g['fall_s'] >= 600).mean():.1%}")


if __name__ == "__main__":
    main()
