"""Thesis figures drawn from data already in the repository (no database, no recordings), in the thesis style.

    python scripts/thesis/figs_repo.py [ladder cnn catalogue b12]

ladder     Chapter 6, Figure 6.1: share of candidates judged real against agreeing detector families
           (docs/thesis/data/ledger_checks.json, the five estimate.json reads of 26 Oct).
cnn        Chapter 3, Figure 3.2(a): the early CNNs on blind labels - confusion matrices at 10 minutes (the two exams of
           queue 3 pooled, n = 429) and balanced accuracy by window length (rq1_v2_blind/run1613_blind_score.json).
catalogue  Chapter 9, Figure 9.1: swing, duration, polarity and intervals of the judged events
           (ch9_catalogue/events.csv).
b12        Chapter 10, Figure B12: six shape measures by recording, coloured by species (ch10_b12/events_shape.csv).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import figstyle as fs  # noqa: E402

DATA = os.path.join(fs.ROOT, "docs", "thesis", "data")
LEVELS = ["1-2", "3-4", "5-6", "7-8", "9+"]


def ladder():
    d = json.load(open(os.path.join(DATA, "ledger_checks.json")))["ladder"]
    order = ["M2_aug_concat_fs1", "M2_concat_fs1", "CO_fs2", "LM_fs2", "L_LM_Jul_26_J_raw_fs2"]
    keys = sorted(d, key=lambda k: next(i for i, o in enumerate(order) if k.startswith(o)))
    fig, ax = fs.figure("wide", 2.9)
    offs = np.linspace(-0.16, 0.16, len(keys))
    markers = ["o", "s", "D", "^", "v"]
    for j, k in enumerate(keys):
        g = d[k]["groups"]
        y = np.array([g[f"agree:{lv}"]["precision"] for lv in LEVELS]) * 100
        lo = np.array([g[f"agree:{lv}"]["ci"][0] for lv in LEVELS]) * 100
        hi = np.array([g[f"agree:{lv}"]["ci"][1] for lv in LEVELS]) * 100
        x = np.arange(len(LEVELS)) + offs[j]
        c = fs.colour(k)
        ax.errorbar(x, y, yerr=[y - lo, hi - y], color=c, marker=markers[j], ms=4.5, lw=1.4, capsize=0,
                    elinewidth=1.0, label=f"{fs.label(k)}  (n={d[k]['answered']})")
    ax.set_xticks(range(len(LEVELS)))
    ax.set_xticklabels(LEVELS)
    ax.set_xlabel("detector families agreeing on the candidate")
    ax.set_ylabel("candidates judged real (%)")
    ax.set_ylim(0, 80)
    ax.legend(loc="upper left", ncol=1, handlelength=1.6)
    return fs.save(fig, "ch6_ladder")


def seed_distribution():
    """All thresholded drop-query matches, with timing and channel totals."""
    df = pd.read_csv(os.path.join(DATA, "seed_drop_matches.csv"))
    names = (df[["channel", "channel_name"]].drop_duplicates()
             .sort_values("channel"))
    assert len(df) == 372 and len(names) == 16
    fig = fs.plt.figure(figsize=(fs.TEXT_WIDTH_IN, 5.1))
    gs = fig.add_gridspec(1, 2, width_ratios=[3.6, 1], wspace=0.05)
    ax = fig.add_subplot(gs[0, 0])
    bx = fig.add_subplot(gs[0, 1], sharey=ax)
    blue = fs.colour("M2_aug")
    for y, row in enumerate(names.itertuples(index=False)):
        matches = df[df["channel"] == row.channel]
        ax.vlines(matches["start_s"] / 3600, y - 0.25, y + 0.25,
                  color=blue, lw=0.85, alpha=0.85)
        seed = matches[matches["is_seed"]]
        if not seed.empty:
            ax.scatter(seed["start_s"] / 3600, np.full(len(seed), y),
                       marker="*", s=65, color=fs.INK, zorder=4)
        bx.barh(y, len(matches), height=0.55, color=blue, alpha=0.9)
        bx.text(len(matches) + 2, y, str(len(matches)), va="center", fontsize=8)
    ax.set(yticks=np.arange(16), yticklabels=names["channel_name"].tolist(),
           ylim=(15.65, -0.65), xlim=(0, 721),
           xlabel="Time in M2_aug (h)")
    ax.set_xticks(np.arange(0, 721, 120))
    ax.set_title("(a) Time of each match", loc="left")
    bx.set(xlim=(0, 129), xlabel="Matches")
    bx.set_xticks([0, 50, 100], ["", "50", "100"])
    bx.set_title("(b) Count", loc="left")
    bx.tick_params(axis="y", labelleft=False, left=False)
    bx.grid(axis="y", visible=False)
    for spine in ("left", "right", "top"):
        bx.spines[spine].set_visible(False)
    fig.suptitle("Drop seed · 377 s · 372 matches across 16 channels",
                 x=0.16, ha="left", fontsize=10)
    fig.text(0.16, 0.92, "Common shape-distance threshold: 2.208 · star: original seed",
             fontsize=8, color=fs.INK_2)
    fig.subplots_adjust(left=0.16, right=0.98, bottom=0.1, top=0.86)
    return fs.save(fig, "ch7_drop_distribution")


def _confusion(a):
    n, p, pp, rec = a["n"], a["human_interesting"], a["model_interesting"], a.get("recall") or 0.0
    tp = int(round(rec * p))
    fp, fn = pp - tp, p - tp
    return np.array([[tp, fn], [fp, n - tp - fp - fn]])


def cnn():
    d = json.load(open(os.path.join(DATA, "rq1_v2_blind", "run1613_blind_score.json")))["reference"]["rows"]
    models = [("GASF_cnn", "GASF"), ("GADF_cnn", "GADF"), ("recurrence_cnn", "Recurrence"), ("fusion_cnn_3", "Fusion")]
    by = {(r["model"], r["scale_min"]): r for r in d if r.get("status") == "scored"}
    fig = fs.plt.figure(figsize=(fs.TEXT_WIDTH_IN, 2.35))
    gs = fig.add_gridspec(1, 6, width_ratios=[1, 1, 1, 1, 0.25, 1.7], wspace=0.35)
    cmap = fs.plt.get_cmap("Blues")
    for i, (m, title) in enumerate(models):
        ax = fig.add_subplot(gs[0, i])
        ex = by[(m, 10.0)]["exams"]
        cm = _confusion(ex["i_later_block"]["all"]) + _confusion(ex["ii_unseen_channels"]["all"])
        ax.imshow(cm, cmap=cmap, vmin=0, vmax=cm.max() * 1.15)
        for (r, c), v in np.ndenumerate(cm):
            ax.text(c, r, str(v), ha="center", va="center", fontsize=8.5,
                    color="white" if v > cm.max() * 0.55 else fs.INK)
        sens, spec = cm[0, 0] / cm[0].sum(), cm[1, 1] / cm[1].sum()
        ax.set_title(f"{title}\nbal. acc. {0.5 * (sens + spec):.2f}", fontsize=8.5)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["int.", "not"], fontsize=7.5)
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["int.", "not"] if i == 0 else ["", ""], fontsize=7.5)
        if i == 0:
            ax.set_ylabel("blind verdict")
        ax.set_xlabel("model says", fontsize=8)
        ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(False)
    ax = fig.add_subplot(gs[0, 5])
    scales = [1.0, 10.0, 30.0]
    for (m, title), col in zip(models, fs.CATEGORICAL):
        ys = []
        for s in scales:
            ex = by[(m, s)]["exams"]
            cm = _confusion(ex["i_later_block"]["all"]) + _confusion(ex["ii_unseen_channels"]["all"])
            ys.append(0.5 * (cm[0, 0] / cm[0].sum() + cm[1, 1] / cm[1].sum()))
        ax.plot(range(3), ys, marker="o", ms=3.5, lw=1.4, color=col, label=title)
    ax.axhline(0.5, color=fs.MUTED, lw=0.9, ls="--")
    ax.text(2.05, 0.5, "chance", va="center", fontsize=7.5, color=fs.INK_2)
    ax.set_xticks(range(3))
    ax.set_xticklabels(["1 min", "10 min", "30 min"])
    ax.set_ylim(0.3, 1.0)
    ax.set_ylabel("balanced accuracy")
    ax.set_title("by window length", fontsize=8.5)
    ax.legend(fontsize=7, loc="lower right", handlelength=1.2)
    return fs.save(fig, "ch3_cnn_blind")


def catalogue():
    df = pd.read_csv(os.path.join(DATA, "ch9_catalogue", "events.csv"))
    q = df[df["set"].isin(["queue25", "queue28"])]
    fig, axes = fs.figure("full", 4.6, 2, 2)
    (a, b), (c, e) = axes
    for cl, col in (("accepted", fs.SPECIES_COLOUR["oyster"]), ("rejected", fs.NEUTRAL)):
        v = q.loc[(q["class"] == cl), "swing_mv"].dropna()
        v = v[v > 0]
        a.hist(v, bins=np.logspace(-2, 3, 41), histtype="step", lw=1.6, color=col, label=f"{cl} ({len(v)})")
        s = q.loc[(q["class"] == cl), "span_s"].dropna()
        b.hist(s, bins=np.logspace(0.5, 4.2, 38), histtype="step", lw=1.6, color=col, label=f"{cl} ({len(s)})")
    a.set_xscale("log"); a.set_xlabel("swing (mV, log scale)"); a.set_ylabel("events"); a.legend(loc="upper left")
    a.set_title("(a) size", loc="left")
    b.set_xscale("log"); b.set_xlabel("judged span (s, log scale)"); b.set_ylabel("events"); b.legend(loc="upper left")
    b.set_title("(b) duration", loc="left")
    acc = q[q["class"] == "accepted"].copy()
    acc["name"] = acc["recording"].map(fs.label)
    order = ["M2_aug", "M2_concat", "CO", "LM", "MJu26a (CH10, 13–16)"]
    share = acc.groupby("name")["polarity_auto"].apply(lambda s: (s == "drop").mean() * 100).reindex(order)
    nn = acc.groupby("name").size().reindex(order)
    recmap = {fs.label(r): r for r in acc["recording"].unique()}
    xs = np.arange(len(order))
    c.bar(xs, share.values, width=0.62, color=[fs.colour(recmap[o]) for o in order])
    for x, (o, v) in zip(xs, share.items()):
        c.text(x, v + 2, f"{v:.0f}%", ha="center", fontsize=8)
    c.set_xticks(xs); c.set_xticklabels([o.replace(" (", "\n(") for o in order], fontsize=7.5, rotation=30, ha="right",
                                        rotation_mode="anchor")
    c.set_ylim(0, 112); c.set_ylabel("accepted events that are falls (%)")
    c.set_title("(c) polarity (fastest edge)", loc="left"); c.grid(axis="x", visible=False)
    for st, col, lab in (("census_rg9", fs.SPECIES_COLOUR["oyster"], "105-s dip seed"),
                         ("census_rg12", fs.RECORDINGS["M2_concat"][1], "long dip seed")):
        m = df[(df["set"] == st) & (df["class"] == "accepted")]
        gaps = []
        for _rid, g in m.groupby("recording_id"):
            on = np.sort(g["start"].to_numpy(float)) / g["fs"].iloc[0]
            gaps.extend(np.diff(on).tolist())
        gaps = np.asarray(gaps)
        gaps = gaps[gaps > 0] / 3600.0
        med = np.median(gaps)
        medtxt = f"{med * 60:.0f} min" if med < 2 else f"{med:.0f} h"
        e.hist(gaps, bins=np.logspace(-2, 3, 41), histtype="step", lw=1.6, color=col,
               label=f"{lab} ({gaps.size} intervals, median {medtxt})")
    e.set_xscale("log"); e.set_xlabel("interval between accepted matches (h, log scale)")
    e.set_ylabel("intervals"); e.legend(loc="upper left", fontsize=7)
    e.set_title("(d) recurrence, fully judged seed searches", loc="left")
    fig.tight_layout(h_pad=1.2)
    return fs.save(fig, "ch9_catalogue")


def b12():
    df = pd.read_csv(os.path.join(DATA, "ch10_b12", "events_shape.csv"))
    feats = [("swing_mv", "swing (mV)", True), ("duration_s", "duration (s)", True),
             ("onset_to_extremum_s", "onset to extremum (s)", True), ("fwhm_s", "FWHM (s)", True),
             ("max_slope_abs_mv_s", "steepest slope (mV/s)", True), ("asymmetry", "asymmetry", False)]
    order = ["M2_aug", "M2_concat", "CO_fs2", "LM_fs2", "L_LM_fs2"]
    fig, axes = fs.figure("full", 4.4, 2, 3)
    for ax, (f, lab, logy) in zip(axes.ravel(), feats):
        vals = [df.loc[df["recording"] == r, f].dropna().to_numpy(float) for r in order]
        vals = [v[v > 0] if logy else v for v in vals]
        bp = ax.boxplot(vals, widths=0.6, patch_artist=True, showfliers=False,
                        medianprops=dict(color=fs.INK, lw=1.4), whiskerprops=dict(color=fs.INK_2, lw=0.9),
                        capprops=dict(color=fs.INK_2, lw=0.9))
        for patch, r in zip(bp["boxes"], order):
            patch.set_facecolor(fs.colour(r)); patch.set_alpha(0.85); patch.set_edgecolor(fs.INK_2)
        if logy:
            ax.set_yscale("log")
        ax.set_title(lab, fontsize=8.5)
        ax.set_xticks(range(1, len(order) + 1))
        ax.set_xticklabels(["M2_aug", "M2_concat", "CO", "LM", "MJu26a (5 ch)"], fontsize=7, rotation=30, ha="right",
                           rotation_mode="anchor")
        ax.grid(axis="x", visible=False)
    handles = [fs.plt.Rectangle((0, 0), 1, 1, color=fs.SPECIES_COLOUR[s]) for s in ("oyster", "chocolate oyster", "lion's mane")]
    fig.legend(handles, ["oyster", "chocolate oyster (both P. ostreatus)", "lion's mane (H. erinaceus)"],
               loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    return fs.save(fig, "ch10_b12_shape")


def b1():
    """Chapter 10, B1: each channel's LV and CV2 against its rate-matched Poisson band (grey), by recording."""
    d = pd.read_csv(os.path.join(DATA, "ch10_b1", "b1_channels.csv"))
    d = d[d["lv"].notna()].copy()
    order = ["M2_aug", "M2_concat", "CO_fs2", "LM_fs2", "MJu26a_fs2"]
    d["o"] = d["dataset"].map({k: i for i, k in enumerate(order)})
    d = d.sort_values(["o", "channel"]).reset_index(drop=True)
    x = np.arange(len(d)) + d["o"].to_numpy() * 1.5
    fig, axes = fs.figure("full", 4.2, 2, 1, sharex=True)
    for ax, null, lab in ((axes[0], "poisson", "LV against a\nrandom (Poisson) train"),
                          (axes[1], "shuffle", "LV against its own\ngaps shuffled")):
        f = "lv"
        ax.vlines(x, d[f"{f}_{null}_lo"], d[f"{f}_{null}_hi"], color=fs.GRID, lw=4.0, zorder=1)
        ax.axhline(1.0, color=fs.MUTED, lw=0.9, ls="--", zorder=1)
        for rec in order:
            m = (d["dataset"] == rec).to_numpy()
            out = m & d[f"{f}_{null}_bh"].astype(bool).to_numpy()
            ax.scatter(x[m & ~out], d.loc[m & ~out, f], s=14, color=fs.colour(rec), zorder=3, edgecolor="white", lw=0.4)
            ax.scatter(x[out], d.loc[out, f], s=26, color=fs.colour(rec), marker="D", zorder=4, edgecolor=fs.INK, lw=0.6)
        ax.set_ylabel(lab)
        ax.grid(axis="x", visible=False)
    axes[0].text(x[-1] + 1, 1.0, "LV = 1", va="center", fontsize=7.5, color=fs.INK_2)
    centres = [x[(d["dataset"] == r).to_numpy()].mean() for r in order]
    axes[1].set_xticks(centres)
    axes[1].set_xticklabels([fs.label(r) for r in order], fontsize=8)
    axes[1].tick_params(axis="x", length=0)
    fig.tight_layout(h_pad=0.6)
    return fs.save(fig, "ch10_b1_lv")


def surr20():
    """Chapter 6: real detections over the 20-draw surrogate mean, per channel of M2_aug, for six settings."""
    s = pd.read_csv(os.path.join(DATA, "ch06_20draw", "per_channel.csv"))
    names = {"drop_detection_v1": "drop v1", "cnn_gadf_10min": "CNN GADF 10 min",
             "cnn_recurrence_10min": "CNN recurrence 10 min", "drop_detection_v5__same_fraction_0p7": "drop v5 (0.7)",
             "drop_detection_v1__slope_sigma_4": "drop v1 (slope 4σ)", "wavelet_encoded__level_5": "wavelet-encoded L5"}
    order = list(names)
    fig, ax = fs.figure("wide", 3.0)
    rng = np.random.default_rng(0)
    finite = s["ratio"].replace([np.inf, -np.inf], np.nan)
    top = float(finite.max()) * 2.5
    for i, v in enumerate(order):
        g = s[s["variant"] == v]
        xs = i + rng.uniform(-0.18, 0.18, len(g))
        col = np.where(g["beats_all"], fs.SPECIES_COLOUR["oyster"], np.where(g["below_all"], fs.CATEGORICAL[1], fs.NEUTRAL))
        inf = ~np.isfinite(g["ratio"].to_numpy(float))
        ax.scatter(xs[~inf], g["ratio"][~inf], s=16, c=col[~inf], edgecolor="white", lw=0.4, zorder=3)
        if inf.any():
            ax.scatter(xs[inf], np.full(inf.sum(), top), s=22, c=col[inf], marker="^", edgecolor="white", lw=0.4,
                       zorder=3)
    ax.text(len(order) - 0.45, top, "▲ surrogates found none", fontsize=7, color=fs.INK_2, va="center", ha="right")
    ax.axhline(1.0, color=fs.MUTED, lw=0.9, ls="--")
    ax.set_yscale("log")
    ax.set_ylim(0.007, top * 1.8)
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([names[v] for v in order], rotation=25, ha="right", rotation_mode="anchor", fontsize=7.5)
    ax.set_ylabel("real ÷ surrogate mean (log)")
    ax.grid(axis="x", visible=False)
    h = [fs.plt.Line2D([], [], ls="", marker="o", color=c, label=l) for c, l in
         ((fs.SPECIES_COLOUR["oyster"], "above all 20 draws"), (fs.CATEGORICAL[1], "below all 20"), (fs.NEUTRAL, "within"))]
    ax.legend(handles=h, loc="lower left", fontsize=7.5, bbox_to_anchor=(0.0, 0.08))
    return fs.save(fig, "ch6_surr20")


def b4():
    """Chapter 10, B4: the cross-channel census - co-occurring events per recording, by what explains them."""
    d = pd.read_csv(os.path.join(DATA, "ch10_b4", "b4_bins.csv"))
    t = d.pivot_table(index="source_file", columns="bin", values="count", aggfunc="sum").fillna(0)
    bins = [("shared_driver", "shared driver"), ("independent_recurrence", "independent recurrence"),
            ("propagation", "propagation"), ("artifact", "artifact (a copy)")]
    order = ["M2_aug_concat_fs1.mat", "M2_concat_fs1.mat", "MJu26a_fs2.mat", "CO_fs2.mat", "LM_fs2.mat"]
    t = t.reindex(order).fillna(0)
    fig, ax = fs.figure("wide", 2.5)
    y = np.arange(len(order))[::-1]
    left = np.zeros(len(order))
    cols = [fs.CATEGORICAL[0], fs.CATEGORICAL[2], fs.CATEGORICAL[1], fs.NEUTRAL]
    for (b, lab), c in zip(bins, cols):
        v = t[b].to_numpy() if b in t else np.zeros(len(order))
        ax.barh(y, v, left=left, color=c, height=0.6, label=lab, edgecolor="white", lw=1.0)
        left += v
    for yy, tot in zip(y, left):
        ax.text(tot + 1, yy, f"{int(tot)}", va="center", fontsize=8, color=fs.INK_2)
    ax.set_yticks(y)
    ax.set_yticklabels([fs.label(o) for o in order])
    ax.set_xlabel("co-occurring events across channels")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", fontsize=7.5)
    return fs.save(fig, "ch10_b4_bins")


FAMILY_NAMES = {"drop_detection_v1": "drop detector v1", "drop_detection_v5": "drop detector v5",
                "wavelet_encoded": "wavelet-encoded", "symbol_search": "symbol search (dSAX)",
                "BEADs_invert_detect_v1": "BEADS", "signal_threshold": "signal threshold",
                "noise_threshold": "noise threshold", "Wavelet_detection_prototype": "Dehshibi wavelet",
                "cnn_60min": "CNN scores, 60 min", "cnn_10min": "CNN scores, 10 min",
                "deconvolved_troughs": "deconvolved troughs", "OASIS_Deconvolution": "OASIS",
                "matrix_profile": "matrix-profile threshold", "cnn_1min": "CNN scores, 1 min (control)"}


def detrates():
    """Chapter 6: detections per setting per channel-hour, detector family x recording, with each family's
    precision (share of its candidates judged real, pooled over the five recordings' blind queues)."""
    d = pd.read_csv(os.path.join(DATA, "detectors_vs_surrogates", "by_family_recording.csv"))
    hours = {"M2_aug": 721.0, "M2_concat": 282.5, "CO_fs2": 480.0, "LM_fs2": 480.0, "L_LM_fs2": 635.9}
    recs = ["M2_aug", "M2_concat", "CO_fs2", "LM_fs2", "L_LM_fs2"]
    d = d[d["recording"].isin(recs)].copy()
    d["rate"] = d["real"] / (d["tasks"] * d["recording"].map(hours))
    lad = json.load(open(os.path.join(DATA, "ledger_checks.json")))["ladder"]
    prec = {}
    for f in FAMILY_NAMES:
        num = den = 0.0
        for v in lad.values():
            g = v["groups"].get(f"family:{f}")
            if g and g.get("n_sampled"):
                num += g["precision"] * g["n_sampled"]
                den += g["n_sampled"]
        prec[f] = num / den if den else np.nan
    fams = sorted(FAMILY_NAMES, key=lambda f: (f == "cnn_1min", -(prec[f] if np.isfinite(prec[f]) else -1)))
    M = np.full((len(fams), len(recs)), np.nan)
    for i, f in enumerate(fams):
        for j, r in enumerate(recs):
            v = d[(d["family"] == f) & (d["recording"] == r)]["rate"]
            if len(v):
                M[i, j] = v.iloc[0]
    fig = fs.plt.figure(figsize=(fs.TEXT_WIDTH_IN, 4.3))
    gs = fig.add_gridspec(1, 2, width_ratios=[3.2, 1.3], wspace=0.08)
    ax = fig.add_subplot(gs[0, 0])
    L = np.log10(np.where(M > 0, M, np.nan))
    im = ax.imshow(L, cmap="Blues", aspect="auto", vmin=-3.5, vmax=1.5)
    for (i, j), v in np.ndenumerate(M):
        if np.isfinite(v):
            txt = "0" if v == 0 else (f"{v:.3f}" if v < 0.01 else f"{v:.2f}" if v < 1 else f"{v:.1f}")
            dark = np.isfinite(L[i, j]) and L[i, j] > 0.0
            ax.text(j, i, txt, ha="center", va="center", fontsize=7, color="white" if dark else fs.INK)
    ax.set_xticks(range(len(recs)))
    ax.set_xticklabels([fs.label(r).replace(" (", "\n(") for r in recs], fontsize=7.5)
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(fams)))
    ax.set_yticklabels([FAMILY_NAMES[f] for f in fams], fontsize=7.5)
    ax.grid(False)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_title("detections per setting per channel-hour", fontsize=8.5, pad=24)
    bx = fig.add_subplot(gs[0, 1], sharey=ax)
    pv = np.array([prec[f] * 100 for f in fams])
    bx.barh(range(len(fams)), np.nan_to_num(pv), color=fs.SPECIES_COLOUR["oyster"], height=0.6)
    for i, v in enumerate(pv):
        bx.text((0 if not np.isfinite(v) else v) + 2, i, "--" if not np.isfinite(v) else f"{v:.0f}%", va="center", fontsize=7)
    bx.set_xlim(0, 115)
    bx.tick_params(axis="y", left=False, labelleft=False)
    bx.set_xlabel("judged real (%)", fontsize=8)
    bx.grid(axis="y", visible=False)
    bx.set_title("precision", fontsize=8.5, pad=24)
    return fs.save(fig, "ch6_detrates")


def b12wave():
    """Chapter 10, B12: the median duration-normalised waveform of each recording's accepted events, with its IQR."""
    df = pd.read_csv(os.path.join(DATA, "ch10_b12", "events_shape.csv"))
    W = np.load(os.path.join(DATA, "ch10_b12", "waveforms_64.npy"))
    order = ["M2_aug", "M2_concat", "CO_fs2", "LM_fs2", "L_LM_fs2"]
    fig, axes = fs.figure("full", 2.2, 1, len(order), sharey=True)
    u = np.linspace(0, 1, W.shape[1])
    for ax, r in zip(axes, order):
        m = (df["recording"] == r).to_numpy()
        w = W[m]
        med = np.nanmedian(w, axis=0); q1, q3 = np.nanpercentile(w, [25, 75], axis=0)
        ax.fill_between(u, q1, q3, color=fs.colour(r), alpha=0.25, lw=0)
        ax.plot(u, med, color=fs.colour(r), lw=2.0)
        ax.set_title(f"{fs.label(r).replace(' (', chr(10) + '(')}  n={int(m.sum())}", fontsize=7.5, loc="left")
        ax.set_xticks([0, 1]); ax.set_xticklabels(["start", "end"], fontsize=7)
    axes[0].set_ylabel("normalised")
    fig.tight_layout(w_pad=0.4)
    return fs.save(fig, "ch10_b12_waveforms")


if __name__ == "__main__":
    fs.apply()
    which = sys.argv[1:] or ["ladder", "cnn", "catalogue", "b12", "b1", "surr20", "b4", "detrates", "b12wave"]
    for w in which:
        print(globals()[w]())
