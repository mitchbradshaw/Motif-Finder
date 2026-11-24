"""
pool_rhythm.py
==============
Is a drop a drop, or one swing of something that goes up and down all the time?

The pool's random sheets (25 Nov) showed that most of Cordyceps' and Enoki's drops are down-swings of a steady
oscillation: a 10-20 s period, rising as fast as it falls, no level between. They also showed tiny blips riding on a
slope or on noise, in M1, L_R_Aug_26_PD and MJu26a. The rules do not see either: each swing is clear against the
noise of its own window, a detector or seed vouches for it, and its box does not run into a bigger event.

Two measures, for each drop. Each reads the trace from 150 s before its top to 150 s after, at the rate it was searched
(10 Hz channels as block means of five):

* `fast_rises`: how many times, in that window, the trace climbs back by at least half the drop's own fall within the
  drop's own fall time. A drop that recovers slowly has none, or one (its own rebound); so does a train of sharp drops
  with slow recoveries. A steady oscillation, or a train of fast down-and-up spikes, has one per cycle, as does a tiny
  blip on a slope or on noise. **This one is used**: a feature of the acceptance model (`pool_summary.py`). The
  judged drops were accepted 88-93 % with 0-1 fast rises around them, 71 % with 3, and about 60 % with 6 or more.
* `rhythm_r`: the highest autocorrelation, with the straight-line trend removed, at a lag of 4-60 s after it first
  dips below zero; `rhythm_period_s` is that lag. A steady oscillation repeats, so its autocorrelation climbs back
  near 1 one period later. It misses an oscillation whose period wanders, adds nothing to the model, and is kept only
  as a description.

Neither needs units or the database. Computed for every pool drop and every judged drop that passes the loosest
settings (the model's training drops). Writes DATA/derived/autodetect/pool_20261124/rhythm.parquet (recording_id,
candidate_id, rhythm_r, rhythm_period_s, fast_rises, set). Prints, to docs/autodetect/20261124_pool/checks/rhythm.out.txt:
the verdicts by band of each measure, and each dataset's share of drops above each line. Draws random sheets by
`fast_rises` band, and the Cordyceps and Enoki drops it would leave at 0-1, to checks/rhythm_*.png. Read-only on the
database and the channels; about 2 minutes. Run it after `build_pool.py choose` and before `pool_summary.py`.

    PYTHONIOENCODING=utf-8 MPLBACKEND=Agg "/c/ProgramData/anaconda3/python.exe" scripts/autodetect/pool_rhythm.py
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # the repo
sys.path.insert(0, os.path.join(ROOT, "scripts", "autodetect"))
POOL = os.path.join(ROOT, "DATA", "derived", "autodetect", "pool_20261124")
CHECKS = os.path.join(ROOT, "docs", "autodetect", "20261124_pool", "checks")
HALF_S = 150.0
LAG_MIN_S, LAG_MAX_S = 4.0, 60.0
SEED = 20261125


def channels():
    """{recording_id: (npy path, decimation, run fs)} from each channel's run record - no database."""
    out = {}
    for f in glob.glob(os.path.join(POOL, "raw", "*", "run.json")):
        with open(f, encoding="utf-8") as fh:
            j = json.load(fh)
        out[int(j["recording"]["id"])] = (os.path.join(ROOT, j["recording"]["npy_path"]), int(j["decimation"]),
                                          float(j["run_fs"]))
    return out


_ARR = {}


def run_window(ch, rid, centre_run, half_run):
    """Run-frame samples [centre - half, centre + half) of a channel (block means of `decimation` stored samples),
    or None where the window leaves the recording or holds a gap."""
    path, d, _fs = ch[rid]
    if rid not in _ARR:
        _ARR[rid] = np.load(path, mmap_mode="r")
    x = _ARR[rid]
    a, b = int(centre_run - half_run), int(centre_run + half_run)
    if a < 0 or b * d > len(x):
        return None
    seg = np.asarray(x[a * d:b * d], dtype=float)
    if d > 1:
        seg = seg.reshape(-1, d).mean(axis=1)
    return seg if np.all(np.isfinite(seg)) else None


def rhythm(seg, fs):
    """(rhythm_r, rhythm_period_s) of one window: see the module's docstring."""
    n = len(seg)
    t = np.arange(n)
    x = seg - np.polyval(np.polyfit(t, seg, 1), t)
    if not np.any(x):
        return np.nan, np.nan
    f = np.fft.rfft(x, 2 * n)
    ac = np.fft.irfft(f * np.conj(f))[:n]
    ac = ac / ac[0]
    lo, hi = max(1, int(round(LAG_MIN_S * fs))), min(n - 1, int(round(LAG_MAX_S * fs)))
    below = np.flatnonzero(ac[1:hi + 1] < 0)
    if not len(below):
        return 0.0, np.nan
    start = max(lo, int(below[0]) + 1)
    if start > hi:
        return 0.0, np.nan
    k = start + int(np.argmax(ac[start:hi + 1]))
    return float(max(0.0, ac[k])), float(k / fs)


def fast_rises(seg, top_w, bottom_w):
    """How often the window climbs back as fast as the drop fell: the number of separate episodes in which the trace
    rises by at least half the drop's own fall (`seg[top] - seg[bottom]`) within the drop's own fall time. A drop that
    recovers slowly has none (or one, its own rebound); a steady oscillation or a train of fast down-and-up spikes has
    one per cycle."""
    tau = max(2, int(bottom_w - top_w))
    fall = seg[top_w] - seg[bottom_w]
    if not np.isfinite(fall) or fall <= 0 or tau >= len(seg) // 2:
        return np.nan
    up = seg[tau:] - seg[:-tau]
    hit = up >= 0.5 * fall
    return float(np.count_nonzero(hit[1:] & ~hit[:-1]) + int(hit[0]))


def measure(frame, ch):
    r, per, fr = np.full(len(frame), np.nan), np.full(len(frame), np.nan), np.full(len(frame), np.nan)
    tops = pd.to_numeric(frame["wd_top"], errors="coerce").to_numpy(float)
    bots = pd.to_numeric(frame["wd_bottom"], errors="coerce").to_numpy(float)
    starts = pd.to_numeric(frame["start_idx"], errors="coerce").to_numpy(float)
    for i, (rid, top, bot, st) in enumerate(zip(frame["recording_id"].astype(int), tops, bots, starts)):
        fs = ch[rid][2]
        centre = top if np.isfinite(top) and top >= 0 else st
        half = int(round(HALF_S * fs))
        seg = run_window(ch, rid, centre, half)
        if seg is not None:
            r[i], per[i] = rhythm(seg, fs)
            if np.isfinite(top) and top >= 0 and np.isfinite(bot) and bot > top and bot - top < half:
                fr[i] = fast_rises(seg, half, int(half + bot - top))
    return r, per, fr


def sheet(frame, ch, title, path, n=30):
    import matplotlib.pyplot as plt
    pick = frame.sample(n=min(n, len(frame)), random_state=SEED).sort_values(["dataset", "recording_id"])
    cols = 5
    rows = int(np.ceil(len(pick) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(3.3 * cols, 2.0 * rows), squeeze=False)
    for ax, r in zip(axes.ravel(), pick.itertuples()):
        fs = ch[int(r.recording_id)][2]
        top = r.wd_top if np.isfinite(r.wd_top) and r.wd_top >= 0 else r.start_idx
        seg = run_window(ch, int(r.recording_id), top, int(round(HALF_S * fs)))
        if seg is None:
            ax.set_axis_off()
            continue
        tt = (np.arange(len(seg)) - len(seg) // 2) / fs
        ax.plot(tt, seg, lw=0.7, color="#1b1b1a")
        if np.isfinite(r.wd_bottom) and r.wd_bottom >= 0:
            ax.axvspan(0, (r.wd_bottom - top) / fs, color="#2a78d6", alpha=0.15, lw=0)
        ax.set_title(f"{r.dataset} CH{int(r.channel)} · r {r.rhythm_r:.2f} · T {r.rhythm_period_s:.0f} s",
                     fontsize=7.5)
        ax.tick_params(labelsize=6)
    for ax in axes.ravel()[len(pick):]:
        ax.set_axis_off()
    fig.suptitle(title, x=0.01, ha="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main():
    import build_pool as BP
    t0 = time.time()
    ch = channels()
    pool = pd.read_parquet(os.path.join(POOL, "pool.parquet"))
    allc = BP.load_flags()
    j = allc[allc["label"] != ""].copy()
    loose = BP.rule_mask(j.assign(reviewed=False, seen=False), with_overlap=False,
                         min_confidence=BP.MEASURE_FROM["confidence"],
                         clarity_min=BP.MEASURE_FROM["clarity"]).to_numpy(bool)
    j = j[loose].copy()
    for name, fr in (("pool", pool), ("judged", j)):
        r, per, rises = measure(fr, ch)
        fr["rhythm_r"], fr["rhythm_period_s"], fr["fast_rises"] = r, per, rises
        print(f"{name}: {len(fr):,} drops measured in {time.time() - t0:.0f} s "
              f"({int(np.isnan(r).sum()):,} windows left the recording or held a gap; "
              f"{int(np.isnan(rises).sum()):,} without fast_rises)", flush=True)
    keep = ["recording_id", "candidate_id", "rhythm_r", "rhythm_period_s", "fast_rises"]
    both = pd.concat([pool[keep].assign(set="pool"), j[keep].assign(set="judged")], ignore_index=True)
    both.drop_duplicates(["recording_id", "candidate_id"]).to_parquet(os.path.join(POOL, "rhythm.parquet"), index=False)
    core_ok = BP.rule_mask(j.assign(reviewed=False, seen=False), with_overlap=False).to_numpy(bool)
    jc = j[core_ok]
    core = pool[pool["tier"] == "core"]

    def acc(v):
        return (v == "accepted").mean()

    for key, bins in (("rhythm_r", [-0.01, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0]),
                      ("fast_rises", [-0.5, 0.5, 1.5, 2.5, 3.5, 5.5, 9.5, 1e6])):
        print()
        print(f"== judged drops passing the loosest settings, by {key} ==")
        print(j.groupby(pd.cut(j[key], bins), observed=True).agg(
            judged=("label", "size"), accepted=("label", acc),
            rejected=("label", lambda v: (v == "rejected").mean())).round(3).to_string())
        print()
        print(f"== judged drops passing the core's settings, by {key} ==")
        print(jc.groupby(pd.cut(jc[key], bins), observed=True).agg(
            judged=("label", "size"), accepted=("label", acc)).round(3).to_string())
    print()
    print("== judged drops with fast_rises >= 4, by dataset ==")
    print(j[j["fast_rises"] >= 4].groupby("dataset").agg(judged=("label", "size"), accepted=("label", acc))
          .round(3).to_string())

    print()
    print("== the pool: share of each dataset's drops by each measure (core | extended) ==")
    rows = []
    for (d, tier), g in pool.groupby(["dataset", "tier"]):
        rows.append({"dataset": d, "tier": tier, "drops": len(g),
                     **{f"r>={t}": float((g["rhythm_r"] >= t).mean()) for t in (0.3, 0.5)},
                     **{f"rises>={t}": float((g["fast_rises"] >= t).mean()) for t in (2, 4, 8)},
                     "median rises": float(g["fast_rises"].median())})
    print(pd.DataFrame(rows).round(3).to_string(index=False))
    for t in (2, 4, 8):
        m = core["fast_rises"] >= t
        print(f"core drops with fast_rises >= {t}: {int(m.sum()):,} ({m.mean():.1%}); by dataset "
              f"{core.loc[m, 'dataset'].value_counts().head(6).to_dict()}")

    sheet(core[core["fast_rises"] >= 8], ch, "Core drops with fast_rises >= 8 (the trace climbs back as fast as the "
          "drop fell, 8+ times in +-150 s), at random", os.path.join(CHECKS, "rhythm_rises_8plus.png"))
    sheet(core[(core["fast_rises"] >= 4) & (core["fast_rises"] < 8)], ch, "Core drops with fast_rises 4-7, at random",
          os.path.join(CHECKS, "rhythm_rises_4to7.png"))
    sheet(core[(core["fast_rises"] >= 2) & (core["fast_rises"] < 4)], ch, "Core drops with fast_rises 2-3, at random",
          os.path.join(CHECKS, "rhythm_rises_2to3.png"))
    for d in ("Cordyceps", "Enoki"):
        sheet(core[(core["dataset"] == d) & (core["fast_rises"] <= 1)], ch,
              f"{d} core drops with fast_rises 0-1 (what a rule at 2 would leave), at random",
              os.path.join(CHECKS, f"rhythm_{d}_rises_0to1.png"))
    sheet(j[j["fast_rises"] >= 4], ch, "Judged drops with fast_rises >= 4, at random (their verdicts: the tables "
          "above)", os.path.join(CHECKS, "rhythm_judged_rises_4plus.png"))
    print()
    print(f"sheets written; {time.time() - t0:.0f} s in all")


if __name__ == "__main__":
    main()
