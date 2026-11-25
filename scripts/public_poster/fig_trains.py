"""Public poster: the three exemplar drop trains.

* Heartbeat - MJu26a CH14 (lion's mane), seq 254: two kinds of big drop, thin and wide, that take turns.
* Crescendo - M2_aug CH1 (oyster), seq 119: each drop deeper and later than the one before.
* Metronome - M2_aug CH1 (oyster), seq 129: near-identical drops at a near-constant beat.
(The three picks and their framing are the NeurIPS session's, 25 Nov.)

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/public_poster/fig_trains.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import style as S  # noqa: E402
import seqdata as Q  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
import matplotlib.patheffects as pe  # noqa: E402

TRACE = "#3a3346"
GRAD = LinearSegmentedColormap.from_list("crescendo", ["#ffb000", "#ff6a00", "#e0187a", "#9b1d9e", "#4b1d73"])
METRO = "#0f9d8a"
RNG = np.random.default_rng(20261125)


def envelope(idx, y, per):
    """Min/max of every `per` samples (so a fall of any depth survives the thinning), as one line."""
    n = len(y) // per * per
    Y = y[:n].reshape(-1, per)
    X = idx[:n].reshape(-1, per)
    lo, hi = np.nanmin(Y, axis=1), np.nanmax(Y, axis=1)
    xs = np.repeat(X[:, 0], 2)
    ys = np.column_stack([hi, lo]).ravel()
    return xs, ys


def scalebar(ax, mv, where="left", color=None):
    """Replace a trace's millivolt axis (its absolute level means nothing) with a scale bar."""
    ax.spines["left"].set_visible(False)
    ax.set_yticks([])
    ax.set_ylabel("")
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    x = x0 + (x1 - x0) * (0.012 if where == "left" else 0.985)
    yb = y0 + (y1 - y0) * 0.08
    ax.plot([x, x], [yb, yb + mv], color=color or S.INK, lw=4, solid_capstyle="butt", zorder=6, clip_on=False)
    ax.text(x + (x1 - x0) * (0.012 if where == "left" else -0.012), yb + mv / 2, f"{mv:g} mV",
            ha="left" if where == "left" else "right", va="center", fontsize=14, fontweight="bold",
            color=color or S.INK, zorder=6)


def label(ax, text, x=0.0, y=1.02, size=16, color=None):
    ax.text(x, y, text, transform=ax.transAxes, fontsize=size, fontweight="bold", color=color or S.INK,
            ha="left", va="bottom")


# ── Heartbeat ─────────────────────────────────────────────────────────────────────────────────────────────────

def heartbeat(w_mm=392, h_mm=96):
    S.apply(base=15)
    info = json.load(open(os.path.join(S.DATA, "ch14_kinds.json")))
    big = pd.read_csv(os.path.join(S.DATA, "ch14_big_drops.csv"))
    rid, fs = info["recording_id"], info["fs"]
    t0 = info["start_idx"] / fs
    fig = S.figure(w_mm, h_mm)
    # (a) close-up: 16 big drops, nearly every one the other kind from the last
    i0, n = 197, 16
    sel = big.iloc[i0:i0 + n]
    a = int(sel["top_idx"].min() - 6 * 60 * fs)
    b = int(sel["top_idx"].max() + 6 * 60 * fs)
    idx, y = Q.trace(rid, a, b)
    ax = fig.add_axes([0.05, 0.17, 0.42, 0.66])
    xs, ys = envelope(idx, y, 10)
    ax.plot((xs - a) / fs / 60, ys, color=TRACE, lw=0.9, zorder=2)
    for r in sel.itertuples():
        c = S.KIND_WIDE if r.wide else S.KIND_THIN
        s0 = int(r.top_idx - 3 * fs)
        s1 = int((r.recovery_idx if np.isfinite(r.recovery_idx) else r.bottom_idx + 20 * fs) + 4 * fs)
        m = (idx >= s0) & (idx <= s1)
        ax.plot((idx[m] - a) / fs / 60, y[m], color=c, lw=2.6, zorder=3, solid_capstyle="round")
        ax.scatter([(r.bottom_idx - a) / fs / 60], [y[np.searchsorted(idx, r.bottom_idx)]], s=60, color=c,
                   edgecolor="white", lw=1.2, zorder=4)
    ax.set_xlabel("Time (min)")
    ax.set_xlim(-6, (b - a) / fs / 60)
    scalebar(ax, 5)
    label(ax, f"{n} large drops in {round((sel['t_s'].max() - sel['t_s'].min()) / 60)} minutes: shallow and deep alternate")
    # (b) the typical drop of each kind, in seconds
    ax = fig.add_axes([0.53, 0.17, 0.13, 0.66])
    pre, post = int(5 * fs), int(45 * fs)
    for k, c, name in ((0, S.KIND_THIN, "thin"), (1, S.KIND_WIDE, "wide")):
        rows = big[big["wide"] == k]
        W = []
        for r in rows.itertuples():
            i_, yy = Q.trace(rid, r.top_idx - pre, r.top_idx + post)
            if len(yy) == pre + post:
                W.append(yy - yy[pre])
        W = np.array(W)
        tt = (np.arange(-pre, post)) / fs
        med, q1, q3 = np.median(W, 0), np.percentile(W, 25, 0), np.percentile(W, 75, 0)
        ax.plot(tt, med, color=c, lw=4.0, solid_capstyle="round", zorder=3 + k)
    ax.set_xlim(-5, 45)
    ax.set_ylim(-11.5, 1.0)
    ax.set_xlabel("Time from onset (s)")
    ax.set_ylabel("mV from onset")
    ax.axhline(0, color=S.GRID, lw=1, zorder=0)
    ax.text(26, -6.4, "narrow", color=S.KIND_THIN, fontsize=15, fontweight="bold", va="center")
    ax.text(26, -8.9, "wide", color=S.KIND_WIDE, fontsize=15, fontweight="bold", va="center")
    label(ax, "Median drop by type")
    # (c) depth over the whole train
    ax = fig.add_axes([0.71, 0.17, 0.15, 0.66])
    th = (big["t_s"] - t0) / 3600
    for k, c in ((0, S.KIND_THIN), (1, S.KIND_WIDE)):
        m = big["wide"] == k
        ax.scatter(th[m], big.loc[m, "depth_mv"], s=9, color=c, alpha=0.85, lw=0)
    ax.set_xlabel("Time (h)")
    ax.set_ylabel("Depth (mV)")
    ax.set_xlim(0, info["hours"])
    ax.set_ylim(3, 18)
    label(ax, f"Depth over {round(info['hours'])} h")
    # (d) what comes after a wide drop
    ax = fig.add_axes([0.9, 0.17, 0.095, 0.5])
    real, rand = info["p_thin_after_wide"] * 100, info["p_thin_after_wide_full_null"] * 100
    ax.bar([0, 1], [rand, real], color=["#c9c3d1", S.KIND_THIN], width=0.74)
    for x_, v in ((0, rand), (1, real)):
        ax.text(x_, v + 3, f"{v:.0f}%", ha="center", va="bottom", fontsize=18, fontweight="bold",
                color=S.INK_2 if x_ == 0 else S.KIND_THIN)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["shuffled", "observed"], fontsize=13)
    ax.set_ylim(0, 100)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.text(-0.3, 1.36, "Next drop narrow,\nafter a wide drop", transform=ax.transAxes,
            fontsize=14, fontweight="bold", color=S.INK, va="top", linespacing=1.05)
    S.save(fig, "train_heartbeat")


# ── Crescendo ─────────────────────────────────────────────────────────────────────────────────────────────────

def crescendo(w_mm=392, h_mm=79):
    S.apply(base=15)
    d, m = Q.drops(119)
    d = d[(d["depth_mv"] > 10)].reset_index(drop=True)
    d = d[d.index <= int(np.argmax(d["depth_mv"].to_numpy()) + 0)].reset_index(drop=True)   # up to the deepest
    rid, fs = int(m["recording_id"]), float(m["fs"])
    a = int(d["top_idx"].min() - 25 * 60 * fs)
    b = int(d["top_idx"].max() + 70 * 60 * fs)
    idx, y = Q.trace(rid, a, b)
    fig = S.figure(w_mm, h_mm)
    ax = fig.add_axes([0.05, 0.2, 0.52, 0.64])
    xs, ys = envelope(idx, y, 5)
    ax.plot((xs - a) / fs / 3600, ys, color=TRACE, lw=1.0, zorder=2)
    n = len(d)
    for k, r in enumerate(d.itertuples()):
        c = GRAD(k / max(1, n - 1))
        s1 = r.recovery_idx if np.isfinite(r.recovery_idx) else r.bottom_idx + 0.3 * (r.bottom_idx - r.top_idx)
        msk = (idx >= r.top_idx - 10) & (idx <= s1)
        ax.plot((idx[msk] - a) / fs / 3600, y[msk], color=c, lw=3.0, zorder=3, solid_capstyle="round")
    ax.set_xlabel("Time (h)")
    ax.set_xlim(-0.15, (b - a) / fs / 3600)
    scalebar(ax, 20)
    label(ax, f"{n} drops in {(d['t_s'].max() - d['t_s'].min()) / 3600:.0f} hours: depth and interval increase together")
    # overlay, aligned at the top
    ax = fig.add_axes([0.64, 0.2, 0.2, 0.64])
    pre, post = int(3 * 60 * fs), int(55 * 60 * fs)
    for k, r in enumerate(d.itertuples()):
        i_, yy = Q.trace(rid, r.top_idx - pre, r.top_idx + post)
        ax.plot((i_ - r.top_idx) / fs / 60, yy - yy[pre], color=GRAD(k / max(1, n - 1)), lw=2.4)
    ax.set_xlabel("Time from onset (min)")
    ax.set_ylabel("mV")
    ax.set_xlim(-3, 55)
    label(ax, "Drops aligned at onset")
    # depth and gap, beat by beat
    ax = fig.add_axes([0.9, 0.2, 0.085, 0.64])
    gaps = d["interval_s"].to_numpy(float) / 60
    ax.scatter(np.arange(1, n + 1), d["depth_mv"], s=40, c=[GRAD(k / max(1, n - 1)) for k in range(n)], zorder=3)
    ax.set_xlabel("Drop number")
    ax.set_ylabel("Depth (mV)")
    ax.set_ylim(0, 65)
    label(ax, "Depth by drop", x=-0.3)
    out = {"drops": n, "depth_first": float(d["depth_mv"].iloc[0]), "depth_last": float(d["depth_mv"].iloc[-1]),
           "gap_first_min": float(gaps[1]), "gap_last_min": float(gaps[-1]),
           "hours": float((d["t_s"].max() - d["t_s"].min()) / 3600)}
    json.dump(out, open(os.path.join(S.DATA, "crescendo.json"), "w"), indent=1)
    S.save(fig, "train_crescendo")
    return out


# ── Metronome ─────────────────────────────────────────────────────────────────────────────────────────────────

def metronome(w_mm=392, h_mm=79):
    S.apply(base=15)
    d, m = Q.drops(129)
    rid, fs = int(m["recording_id"]), float(m["fs"])
    a = int(d["top_idx"].min() - 6 * 60 * fs)
    b = int(d["top_idx"].max() + 9 * 60 * fs)
    idx, y = Q.trace(rid, a, b)
    fig = S.figure(w_mm, h_mm)
    ax = fig.add_axes([0.05, 0.2, 0.52, 0.6])
    ax.plot((idx - a) / fs / 60, y, color=TRACE, lw=1.1, zorder=2)
    gaps = np.diff(d["t_s"].to_numpy(float)) / 60
    ylo, yhi = np.nanmin(y), np.nanmax(y)
    for k, r in enumerate(d.itertuples()):
        s1 = r.recovery_idx if np.isfinite(r.recovery_idx) else r.bottom_idx + 60
        msk = (idx >= r.top_idx - 5) & (idx <= s1)
        ax.plot((idx[msk] - a) / fs / 60, y[msk], color=METRO, lw=3.0, zorder=3)
    tops = (d["top_idx"].to_numpy() - a) / fs / 60
    for k, g in enumerate(gaps):
        xm = (tops[k] + tops[k + 1]) / 2
        ax.text(xm, yhi + (yhi - ylo) * 0.06, f"{g:.1f}", ha="center", va="bottom", fontsize=12.5,
                color=METRO, fontweight="bold")
    ax.set_ylim(ylo - (yhi - ylo) * 0.05, yhi + (yhi - ylo) * 0.22)
    ax.set_xlabel("Time (min)")
    ax.set_xlim(-3, (b - a) / fs / 60)
    scalebar(ax, 5)
    label(ax, f"{len(d)} drops at a mean interval of {gaps.mean():.1f} minutes (intervals in minutes)", y=1.03)
    # overlay
    ax = fig.add_axes([0.63, 0.2, 0.14, 0.6])
    pre, post = int(1.5 * 60 * fs), int(9 * 60 * fs)
    for r in d.itertuples():
        i_, yy = Q.trace(rid, r.top_idx - pre, r.top_idx + post)
        ax.plot((i_ - r.top_idx) / fs / 60, yy - yy[pre], color=METRO, lw=2.0, alpha=0.55)
    ax.set_xlabel("Time from onset (min)")
    ax.set_ylabel("mV")
    label(ax, "Drops aligned at onset", y=1.03)
    # regular vs random: the 14 drop times as a tick ruler, beside 14 random times over the same span (the NeurIPS
    # session's suggestion, 25 Nov). Random = a Poisson process: 14 uniform times, sorted; the seed is fixed, not
    # chosen.
    ax = fig.add_axes([0.81, 0.2, 0.18, 0.6])
    mean = gaps.mean()
    cv = gaps.std(ddof=1) / mean * 100
    t_real = (d["t_s"].to_numpy(float) - d["t_s"].iloc[0]) / 60
    span = t_real[-1]
    rr = np.random.default_rng(7)
    t_rand = np.sort(np.concatenate([[0.0, span], rr.uniform(0, span, len(t_real) - 2)]))
    for yrow, ts, c, lw in ((1.0, t_real, METRO, 4.0), (0.0, t_rand, "#9a93a6", 4.0)):
        ax.plot([0, span], [yrow, yrow], color=c, lw=1.6, alpha=0.6)
        ax.vlines(ts, yrow - 0.26, yrow + 0.26, color=c, lw=lw)
    ax.text(0, 1.42, f"Observed: ±{cv:.0f}%", color=METRO, fontsize=14.5, fontweight="bold", va="center")
    ax.text(0, 0.42, "Random process: ±100%", color=S.INK_2, fontsize=14.5, fontweight="bold", va="center")
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xlim(-3, span + 3)
    ax.set_ylim(-0.5, 1.7)
    ax.set_xlabel("Time (min)")
    label(ax, "Observed vs random timing", y=1.03)
    out = {"drops": int(len(d)), "mean_gap_min": float(mean), "cv_percent": float(cv),
           "gap_min": float(gaps.min()), "gap_max": float(gaps.max()),
           "depth_mv_median": float(d["depth_mv"].median()), "depth_cv_percent":
           float(d["depth_mv"].std(ddof=1) / d["depth_mv"].mean() * 100)}
    json.dump(out, open(os.path.join(S.DATA, "metronome.json"), "w"), indent=1)
    S.save(fig, "train_metronome")
    return out


if __name__ == "__main__":
    which = sys.argv[1:] or ["heartbeat", "crescendo", "metronome"]
    for w in which:
        print(w, globals()[w]())
