"""Thesis figures drawn from the wave-1 bundle (signal excerpts and tables exported read-only from the real database).

    python scripts/thesis/figs_bundle.py --bundle <unzipped bundle folder> [m4 accepted rec385 pool handlabels ...]

Each function writes docs/thesis/figures/new/<stem>.pdf (+ a .png preview) in the thesis style (figstyle.py).
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import bundle_io as BI  # noqa: E402
import figstyle as fs  # noqa: E402
import matplotlib  # noqa: E402
fs.matplotlib = matplotlib

B: BI.Bundle = None


def _nms(df, start="start", end="end", score="score", max_len=None, overlap=0.5):
    """Greedy: highest score first; drop any span overlapping a kept one by more than `overlap` of the shorter."""
    d = df.copy()
    if max_len is not None:
        d = d[(d[end] - d[start]) <= max_len]
    d = d.sort_values(score, ascending=False)
    kept = []
    for r in d.itertuples(index=False):
        a, b = getattr(r, start), getattr(r, end)
        ok = True
        for ka, kb in kept:
            ov = min(b, kb) - max(a, ka)
            if ov > overlap * min(b - a, kb - ka):
                ok = False
                break
        if ok:
            kept.append((a, b))
    keep = pd.DataFrame(kept, columns=[start, end])
    return d.merge(keep, on=[start, end]).drop_duplicates([start, end])


def _scalebar(ax, x0, y0, dx_label, dy, dy_label, dx=None):
    """An L-shaped scale bar: vertical dy (mV) and, if given, horizontal dx."""
    ax.plot([x0, x0], [y0, y0 + dy], color=fs.INK, lw=1.2, solid_capstyle="butt")
    ax.text(x0, y0 + dy / 2, " " + dy_label, va="center", ha="left", fontsize=6.5, color=fs.INK)
    if dx is not None:
        ax.plot([x0, x0 + dx], [y0, y0], color=fs.INK, lw=1.2, solid_capstyle="butt")
        ax.text(x0 + dx / 2, y0, dx_label, va="top", ha="center", fontsize=6.5, color=fs.INK)


def _thumb(ax, t, y, a, b, colour, title=None):
    ax.plot(t, y, color=fs.INK, lw=0.8)
    ax.axvspan(a, b, color=colour, alpha=0.25, lw=0)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.grid(False)
    if title:
        ax.set_title(title, fontsize=6.5, pad=2)


# ------------------------------------------------------------------------------------------------ Chapter 8 --
def m4():
    """Figure 8.1: the held-out recording before and after detection, scored by the frozen R4."""
    stem = [f[:-4] for f in B.ls("m4_exam") if f.startswith("m4_exam__") and f.endswith(".npz")][0]
    x, meta = B.series(f"m4_exam/{stem}")
    t = B.time_h(meta, len(x))
    c = B.csv(f"m4_exam/{stem}__candidates_r4")
    c = c[c["r4_readable"] == True].copy()  # noqa: E712
    c["score"] = c["r4_decision"]
    pos = c[c["r4_interesting"] == 1]
    ev = _nms(pos, max_len=1800)           # event-sized R4-positive candidates, nested ones collapsed
    items = B.csv("m4_exam/exam_items")
    items = items[(items["recording_id"] == meta["recording_id"]) & (items["start"] >= meta["start_idx"])
                  & (items["end"] <= meta["end_idx"])].copy()
    items = items[items["exam_verdict"].isin(["interesting", "seed", "not_interesting", "artifact"])]
    items["human"] = items["exam_verdict"].isin(["interesting", "seed"]).astype(int)
    items["agree"] = (items["human"] == items["r4_interesting"].fillna(0).astype(int))

    fig = fs.plt.figure(figsize=(fs.TEXT_WIDTH_IN, 7.9))
    gs = fig.add_gridspec(6, 6, height_ratios=[1.0, 1.0, 0.22, 0.42, 0.7, 0.7], hspace=0.55, wspace=0.12)
    a = fig.add_subplot(gs[0, :])
    a.plot(t, x, color=fs.INK, lw=0.55)
    a.set_title(f"(a) Held-out M4, {meta['channel_name']}, as recorded", loc="left")
    a.set_ylabel("mV")
    a.set_xlim(t[0], t[-1])
    a.tick_params(labelbottom=False)
    bx = fig.add_subplot(gs[1, :], sharex=a)
    bx.plot(t, x, color=fs.INK, lw=0.55, zorder=2)
    lo, hi = np.nanmin(x), np.nanmax(x)
    rng = hi - lo
    ytick = hi + 0.1 * rng
    for r in items.itertuples():
        mid = (r.start + r.end) / 2 / 3600
        col = fs.SPECIES_COLOUR["oyster"] if r.agree else fs.CATEGORICAL[1]
        bx.scatter([mid], [ytick], marker="v", s=30, color=col if r.human else "white", edgecolor=col, lw=1.1,
                   zorder=4)
    bx.set_ylim(lo - 0.05 * rng, hi + 0.2 * rng)
    bx.set_ylabel("mV")
    bx.set_title("(b) After detection: the blind human exam verdicts (triangles) and the events R4 accepts (bars)",
                 loc="left")
    bx.tick_params(labelbottom=False)
    rx = fig.add_subplot(gs[2, :], sharex=a)
    for r in ev.itertuples():
        rx.axvspan(r.start / 3600, r.end / 3600, color=fs.SPECIES_COLOUR["oyster"],
                   alpha=0.25 + 0.6 * min(1.0, max(0.0, r.score)), lw=0)
    rx.set_yticks([])
    rx.set_ylabel("R4", rotation=0, ha="right", va="center", fontsize=8)
    rx.grid(False)
    rx.set_xlabel("time in the recording (h)")
    h = [fs.plt.Line2D([], [], ls="", marker="v", color=fs.SPECIES_COLOUR["oyster"], label="human: event, R4 agrees"),
         fs.plt.Line2D([], [], ls="", marker="v", mfc="white", color=fs.SPECIES_COLOUR["oyster"],
                       label="human: not an event, R4 agrees"),
         fs.plt.Line2D([], [], ls="", marker="v", color=fs.CATEGORICAL[1], label="R4 disagrees")]
    lx = fig.add_subplot(gs[3, :])
    lx.axis("off")
    lx.legend(handles=h, loc="upper center", ncol=3, fontsize=7.5)
    top = ev.sort_values("score", ascending=False).head(12)
    for k, r in enumerate(top.itertuples()):
        ax = fig.add_subplot(gs[4 + k // 6, k % 6])
        L = r.end - r.start
        i0 = int(max(0, r.start - L - meta["start_idx"]))
        i1 = int(min(len(x), r.end + L - meta["start_idx"]))
        tt = (meta["start_idx"] + np.arange(i0, i1)) / 60.0
        yy = x[i0:i1]
        _thumb(ax, tt, yy, r.start / 60, r.end / 60, fs.SPECIES_COLOUR["oyster"],
               f"{L / 60:.0f} min, {int(r.n_agree)} agree")
        if k == 0:
            ax.text(0, 1.38, "(c) The twelve events R4 is most confident of, with context either side",
                    transform=ax.transAxes, fontsize=9.5, color=fs.INK)
    return fs.save(fig, "ch8_m4_before_after")


def r4_examples():
    """Figure 8.2: R4 on the M4 exam - hits, false alarms and misses, as thumbnails."""
    st = B.stack("m4_exam/exam_item_windows")
    items = B.csv("m4_exam/exam_items")
    idx = st.index.merge(items[["event_id", "r4_interesting", "r4_decision"]], on="event_id", how="left")
    idx["human"] = idx["exam_verdict"].isin(["interesting", "seed"]).astype(int)
    idx = idx[idx["exam_verdict"].isin(["interesting", "seed", "not_interesting", "artifact"])
              & idx["r4_interesting"].notna()]
    groups = [("Hits: the human verdict and R4 both say event", (idx["human"] == 1) & (idx["r4_interesting"] == 1), False),
              ("False alarms: R4 says event, the human verdict says not", (idx["human"] == 0) & (idx["r4_interesting"] == 1), False),
              ("Misses: the human verdict says event, R4 says not", (idx["human"] == 1) & (idx["r4_interesting"] == 0), True)]
    fig, axes = fs.figure("full", 4.6, 3, 4)
    for row, (title, m, asc) in enumerate(groups):
        sub = idx[m].sort_values("r4_decision", ascending=asc).head(4)
        for col in range(4):
            ax = axes[row, col]
            if col >= len(sub):
                ax.axis("off")
                continue
            r = sub.iloc[col]
            tt, yy = st.window(int(r.name) if False else int(st.index.index[st.index["event_id"] == r["event_id"]][0]))
            _thumb(ax, tt / 60, yy, r["item_t0_s"] / 60, r["item_t1_s"] / 60,
                   fs.SPECIES_COLOUR["oyster"] if row == 0 else fs.CATEGORICAL[1],
                   f"R4 {r['r4_decision']:+.2f} · {(r['item_t1_s'] - r['item_t0_s']) / 60:.0f} min")
        txt = axes[row, 0].text(0, 1.36, f"{title} ({int(m.sum())})", transform=axes[row, 0].transAxes,
                                fontsize=8.5)
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.02, top=0.88, hspace=0.9, wspace=0.12)
    return fs.save(fig, "ch8_r4_examples")


# ------------------------------------------------------------------------------------------------ Chapter 9 --
REC_OF_FILE = {"M2_aug_concat_fs1.mat": "M2_aug", "M2_concat_fs1.mat": "M2_concat", "CO_fs2.mat": "CO",
               "LM_fs2.mat": "LM", "L_LM_Jul_26_J_raw_fs2.mat": "L_LM_fs2"}


def _thumb_scaled(ax, t_s, y, a_s, b_s, colour, label=None):
    """A thumbnail at its real scale: time in s from the event start, with a mV bar and a duration bar."""
    t = t_s - a_s
    ax.plot(t, y, color=fs.INK, lw=0.8)
    ax.axvspan(0, b_s - a_s, color=colour, alpha=0.22, lw=0)
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.grid(False)
    p2p = np.nanmax(y) - np.nanmin(y)
    bar = float(10 ** np.floor(np.log10(max(p2p, 1e-3) * 0.6)))
    if p2p / bar > 5:
        bar *= 2
    y0 = np.nanmin(y)
    x0 = t[-1]
    ax.plot([x0, x0], [y0, y0 + bar], color=fs.INK, lw=1.4, solid_capstyle="butt", clip_on=False)
    ax.text(x0, y0 + bar / 2, f" {bar:g} mV", fontsize=6, va="center", ha="left", clip_on=False)
    dur = b_s - a_s
    ax.set_title(label or (f"{dur:.0f} s" if dur < 120 else f"{dur / 60:.0f} min"), fontsize=6.5, pad=1)


def accepted():
    """Figure 9.2: 24 accepted events, six per recording, each at its own real scale."""
    st = B.stack("library_events/library_event_windows")
    ev = B.csv("library_events/events_with_family")
    acc = ev[ev["accepted_parts"] > 0]
    idx = st.index.reset_index().rename(columns={"index": "pos"}).merge(acc[["event_id", "recording"]], on="event_id")
    rng = np.random.default_rng(3)
    order = ["M2_aug_concat_fs1.mat", "M2_concat_fs1.mat", "CO_fs2.mat", "LM_fs2.mat"]
    fig, axes = fs.figure("full", 5.0, 4, 6)
    for row, f in enumerate(order):
        sub = idx[idx["recording"] == f]
        pick = sub.iloc[rng.choice(len(sub), size=min(6, len(sub)), replace=False)].sort_values("item_t0_s")
        name = REC_OF_FILE[f]
        for col in range(6):
            ax = axes[row, col]
            if col >= len(pick):
                ax.axis("off"); continue
            r = pick.iloc[col]
            t, y = st.window(int(r["pos"]))
            _thumb_scaled(ax, t, y, r["item_t0_s"], r["item_t1_s"], fs.colour(name))
        axes[row, 0].text(-0.08, 0.5, fs.label(name), transform=axes[row, 0].transAxes, rotation=90,
                          ha="right", va="center", fontsize=8, color=fs.colour(name))
    fig.subplots_adjust(left=0.05, right=0.95, bottom=0.02, top=0.95, hspace=0.45, wspace=0.35)
    return fs.save(fig, "ch9_accepted_gallery")


def rec385():
    """Figure 9.3: the 4-hour MJu26a CH14 excerpt with its Library members coloured by shape family."""
    x, meta = B.series("full_channels/Mushroom_260720__CH0__full")
    th = B.time_h(meta, len(x))
    mem = B.csv("library_events/rec385_members_g05")
    fams = mem["g05_family_label"].value_counts()
    top = [f for f in fams.index[:3]]
    cols = {f: c for f, c in zip(top, [fs.CATEGORICAL[0], fs.CATEGORICAL[1], fs.CATEGORICAL[2]])}
    fig = fs.plt.figure(figsize=(fs.TEXT_WIDTH_IN, 4.6))
    gs = fig.add_gridspec(2, 3, height_ratios=[1.0, 0.95], hspace=0.45, wspace=0.28)
    a = fig.add_subplot(gs[0, :])
    a.plot(th, x, color=fs.INK, lw=0.6, zorder=2)
    for r in mem.itertuples():
        c = cols.get(r.g05_family_label, fs.NEUTRAL)
        a.axvspan(r.start_s / 3600, r.end_s / 3600, color=c, alpha=0.35 if c != fs.NEUTRAL else 0.08,
                  lw=0, zorder=1)
    a.set_xlim(th[0], th[-1]); a.set_ylabel("mV"); a.set_xlabel("time in the excerpt (h)")
    a.set_title(f"(a) MJu26a CH14, a 4-hour excerpt: {len(mem)} Library members (the three largest families in colour)",
                loc="left")
    fsr = float(meta["fs"])
    for k, f in enumerate(top):
        ax = fig.add_subplot(gs[1, k])
        m = mem[mem["g05_family_label"] == f]
        for r in m.itertuples():
            i0 = int(r.start_idx); i1 = int(r.end_idx)
            seg = x[i0:i1]
            if len(seg) < 3:
                continue
            ax.plot((np.arange(len(seg))) / fsr, seg - seg[0], color=cols[f], lw=0.9, alpha=0.75)
        ax.set_title(f"({'bcd'[k]}) family {f}: {len(m)} members", loc="left", fontsize=8.5)
        ax.set_xlabel("s from onset")
        if k == 0:
            ax.set_ylabel("mV from onset")
    return fs.save(fig, "ch9_rec385")


def pool():
    """Figure 9.5: the unjudged high-agreement pool against the accepted events."""
    pc = B.csv("pool/pool_counts")
    recs = ["M2_aug", "M2_concat", "CO_fs2", "LM_fs2", "L_LM_fs2"]
    samp = pd.concat([B.csv(f"pool/pool_sample_{r}") for r in recs], ignore_index=True)
    samp["lv"] = samp["level"].astype(str)
    cat = pd.read_csv(os.path.join(fs.ROOT, "docs", "thesis", "data", "ch9_catalogue", "events.csv"))
    acc = cat[cat["set"].isin(["queue25", "queue28"]) & (cat["class"] == "accepted")]
    fig, axes = fs.figure("full", 4.8, 2, 2)
    (a, b), (c, d) = axes
    x = np.arange(len(recs))
    w = 0.2
    for k, (col, lab, colour) in enumerate([("n_ge5", "5+ agree, as proposed", fs.GRID),
                                             ("collapsed_ge5", "5+ agree, nested ones merged", fs.CATEGORICAL[0]),
                                             ("n_ge9", "9+ agree, as proposed", "#c9c7c1"),
                                             ("collapsed_ge9", "9+ agree, nested ones merged", "#164b8f")]):
        v = pc.set_index("recording").reindex(recs)[col].to_numpy(float)
        a.bar(x + (k - 1.5) * w, v, width=w, color=colour, label=lab, edgecolor="white", lw=0.5)
    a.set_yscale("log"); a.set_xticks(x)
    a.set_xticklabels([fs.label(r) for r in recs], fontsize=7, rotation=25, ha="right", rotation_mode="anchor")
    a.set_ylabel("candidate events"); a.legend(fontsize=6.5, loc="upper right")
    a.set_title("(a) How many", loc="left"); a.grid(axis="x", visible=False)
    levels = [("5-6", fs.CATEGORICAL[1]), ("7-8", fs.CATEGORICAL[2]), ("9+", fs.CATEGORICAL[0])]
    def ecdf(ax, v, **kw):
        v = np.sort(np.asarray(v, float)[np.isfinite(v)])
        v = v[v > 0]
        ax.plot(v, np.arange(1, len(v) + 1) / len(v), **kw)
    ecdf(b, acc["swing_mv"], color=fs.INK, lw=2.0, label=f"accepted ({len(acc)})")
    ecdf(c, acc["span_s"], color=fs.INK, lw=2.0, label="accepted")
    for lv, colour in levels:
        m = samp["lv"] == lv
        ecdf(b, samp.loc[m, "swing_mv"], color=colour, lw=1.5, label=f"pool, {lv} agree")
        ecdf(c, samp.loc[m, "span_s"], color=colour, lw=1.5, label=f"pool, {lv} agree")
    b.set_xscale("log"); b.set_xlabel("swing (mV)"); b.set_ylabel("share at or below"); b.legend(fontsize=6.5)
    b.set_xlim(1e-2, 1e3); b.set_title("(b) Size", loc="left")
    c.set_xscale("log"); c.set_xlabel("span (s)"); c.set_ylabel("share at or below"); c.set_xlim(1, 3e4)
    c.set_title("(c) Length", loc="left")
    share = samp.groupby(["recording", "lv"])["r4_interesting"].mean().unstack().reindex(recs) * 100
    for k, (lv, colour) in enumerate(levels):
        d.bar(x + (k - 1) * 0.26, share[lv].to_numpy(float), width=0.26, color=colour, label=f"{lv} agree",
              edgecolor="white", lw=0.5)
    d.set_xticks(x); d.set_xticklabels([fs.label(r) for r in recs], fontsize=7, rotation=25, ha="right",
                                       rotation_mode="anchor")
    d.set_ylim(0, 100); d.set_ylabel("R4 calls it an event (%)"); d.legend(fontsize=6.5, loc="upper left")
    d.set_title("(d) What R4 makes of them", loc="left"); d.grid(axis="x", visible=False)
    fig.tight_layout(h_pad=1.0)
    return fs.save(fig, "ch9_pool")


# ------------------------------------------------------------------------------------------------ Chapter 3 --
def handlabels():
    """Figure 3.1: hand-labelled 10-minute windows - four interesting, four not, two flagged - in 30 min context."""
    st = B.stack("hand_labels/hand_label_windows")
    idx = st.index.reset_index().rename(columns={"index": "pos"})
    groups = [("interesting", "interesting", fs.SPECIES_COLOUR["oyster"], 4),
              ("not_interesting", "not interesting", fs.NEUTRAL, 4), ("artifact", "flagged", fs.CATEGORICAL[1], 2)]
    fig, axes = fs.figure("full", 3.2, 2, 5)
    k = 0
    for lab, name, colour, n in groups:
        sub = idx[idx["label"] == lab].head(n)
        for _, r in sub.iterrows():
            ax = axes.ravel()[k]; k += 1
            t, y = st.window(int(r["pos"]))
            ax.plot((t - r["item_t0_s"]) / 60, y, color=fs.INK, lw=0.7)
            ax.axvspan(0, (r["item_t1_s"] - r["item_t0_s"]) / 60, color=colour, alpha=0.22, lw=0)
            ax.set_title(name, fontsize=7.5, color=colour if colour != fs.NEUTRAL else fs.INK_2, pad=2)
            ax.set_yticks([]); ax.grid(False)
            ax.tick_params(labelsize=6.5)
            for sp in ("left",):
                ax.spines[sp].set_visible(False)
            p2p = np.nanmax(y) - np.nanmin(y)
            ax.text(0.02, 0.04, f"{p2p:.1f} mV", transform=ax.transAxes, fontsize=6, color=fs.INK_2)
    for ax in axes[1]:
        ax.set_xlabel("min", fontsize=7)
    fig.subplots_adjust(left=0.02, right=0.99, bottom=0.14, top=0.92, hspace=0.55, wspace=0.12)
    return fs.save(fig, "ch3_hand_labels")


# ------------------------------------------------------------------------------------------------ Chapter 2 --
def mpintuition():
    """Figure 2.1: what a matrix profile shows - M2_concat CH0 with its April 10-minute profile (no new computation)."""
    x, meta = B.series("full_channels/M2_concat__CH0__full")
    z = np.load(os.path.join(fs.ROOT, "Results", "Detection", "matrix_profile", "_legacy", "1_mp_M2_concat_fs1_CH0.npz"))
    mp, mpi, m = z["mp"].astype(float), z["mpi"].astype(int), int(z["m"])
    n = len(mp)
    sep = np.abs(np.arange(n) - mpi)
    ok = np.isfinite(mp) & (sep > 6 * 3600)           # a pair at least six hours apart, not a neighbour of itself
    i = int(np.nanargmin(np.where(ok, mp, np.nan)))
    j = int(mpi[i])
    d = int(np.nanargmax(np.where(np.isfinite(mp), mp, np.nan)))
    th = np.arange(len(x)) / 3600.0
    fig = fs.plt.figure(figsize=(fs.TEXT_WIDTH_IN, 4.4))
    gs = fig.add_gridspec(2, 3, height_ratios=[1.0, 0.8], hspace=0.12, wspace=0.35)
    a = fig.add_subplot(gs[0, :2])
    a.plot(th, x, color=fs.INK, lw=0.4)
    ytop = np.nanmax(x) + 0.08 * (np.nanmax(x) - np.nanmin(x))
    for k, c in ((i, fs.CATEGORICAL[0]), (j, fs.CATEGORICAL[0]), (d, fs.CATEGORICAL[1])):
        a.scatter([(k + m / 2) / 3600], [ytop], marker="v", s=40, color=c, zorder=3)
    a.set_ylabel("mV"); a.tick_params(labelbottom=False)
    a.set_title("(a) M2_concat CH1, 282 hours", loc="left")
    b = fig.add_subplot(gs[1, :2], sharex=a)
    b.plot(np.arange(n) / 3600, mp, color=fs.INK_2, lw=0.4)
    b.scatter([i / 3600, j / 3600], [mp[i], mp[j]], color=fs.CATEGORICAL[0], s=18, zorder=3, label="closest pair")
    b.scatter([d / 3600], [mp[d]], color=fs.CATEGORICAL[1], s=18, zorder=3, label="most unusual (discord)")
    b.set_ylabel("distance to\nnearest match"); b.set_xlabel("time (h)"); b.legend(fontsize=7, loc="upper right")
    b.set_xlim(0, th[-1])
    c = fig.add_subplot(gs[:, 2])
    zn = lambda v: (v - v.mean()) / (v.std() + 1e-12)
    tt = np.arange(m) / 60
    c.plot(tt, zn(x[i:i + m]), color=fs.CATEGORICAL[0], lw=1.4, label=f"{i / 3600:.1f} h")
    c.plot(tt, zn(x[j:j + m]), color="#164b8f", lw=1.4, ls="--", label=f"{j / 3600:.1f} h")
    c.set_xlabel("minutes"); c.set_ylabel("z-score"); c.legend(fontsize=7, loc="lower right")
    c.set_title("(b) the closest pair,\nz-normalised", loc="left", fontsize=8.5)
    print(f"mp intuition: pair {i / 3600:.2f} h and {j / 3600:.2f} h, distance {mp[i]:.3f}; discord {d / 3600:.2f} h ({mp[d]:.2f}); m={m}")
    return fs.save(fig, "ch2_mp_intuition")


# ------------------------------------------------------------------------------------------------ Chapter 10 --
def b6species(families=("F-37", "F-38")):
    """Chapter 10, B6: one shape family's members from each strain, normalised and overlaid (median in bold)."""
    st = B.stack("library_events/library_event_windows")
    idx = st.index.reset_index().rename(columns={"index": "pos"})
    strains = [("oyster", ["M2_aug_concat_fs1.mat", "M2_concat_fs1.mat"], "M2_aug"),
               ("chocolate oyster", ["CO_fs2.mat"], "CO"), ("lion's mane", ["LM_fs2.mat"], "LM")]
    fig, axes = fs.figure("full", 3.6, len(families), 3, sharey=True)
    grid = np.linspace(-0.5, 1.5, 120)
    for r_, fam in enumerate(families):
        for c_, (name, files, rec) in enumerate(strains):
            ax = axes[r_, c_]
            sub = idx[(idx["family"] == fam) & idx["source_file"].isin(files)]
            ys = []
            for _, r in sub.iterrows():
                t, y = st.window(int(r["pos"]))
                a, b = r["item_t0_s"], r["item_t1_s"]
                u = (t - a) / max(b - a, 1e-9)               # 0 = start of the event, 1 = its end
                yy = np.interp(grid, u, y, left=np.nan, right=np.nan)
                core = (grid >= 0) & (grid <= 1)
                mu, sd = np.nanmean(yy[core]), np.nanstd(yy[core])
                if not np.isfinite(sd) or sd == 0:
                    continue
                yy = (yy - mu) / sd
                ys.append(yy)
                ax.plot(grid, yy, color=fs.species_colour(name), lw=0.6, alpha=0.35)
            if ys:
                ax.plot(grid, np.nanmedian(np.vstack(ys), axis=0), color=fs.species_colour(name), lw=2.2)
            ax.axvline(0, color=fs.MUTED, lw=0.7, ls="--"); ax.axvline(1, color=fs.MUTED, lw=0.7, ls="--")
            ax.set_title(f"{fam}, {name} ({len(ys)})", fontsize=8.5, loc="left")
            if r_ == len(families) - 1:
                ax.set_xlabel("event, start (0) to end (1)")
            if c_ == 0:
                ax.set_ylabel("z-score")
            ax.set_ylim(-3.5, 3.5)
    fig.tight_layout(h_pad=0.8)
    return fs.save(fig, "ch10_b6_species")


def dropfamily(cat="22"):
    """Figure 3.7a: one hand-catalogued drop family (catalogue 22, M2_aug) from the drop-motif store - the events in
    their place in the recording, then overlaid on their onsets."""
    d = B.csv("drop_motifs_store/store/motifs")
    z = np.load(B.path("drop_motifs_store/store/motifs.npz"))
    c = d[d["catalogue_id"].astype(str) == cat].sort_values("onset_idx")
    cmap = fs.plt.get_cmap("plasma")
    t_on = c["onset_h"].to_numpy(float)
    norm = fs.matplotlib.colors.Normalize(vmin=t_on.min(), vmax=t_on.max() + 1e-9)
    fig = fs.plt.figure(figsize=(fs.TEXT_WIDTH_IN, 4.6))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.1], hspace=0.45, wspace=0.25)
    a = fig.add_subplot(gs[0, :])
    b = fig.add_subplot(gs[1, 0])
    e = fig.add_subplot(gs[1, 1])
    for r in c.itertuples():
        t = z[r.snippet_key + "__t_s"] / 3600.0 / float(r.fs) if False else z[r.snippet_key + "__t_s"] / float(r.fs) / 3600.0
        y = z[r.snippet_key + "__raw_mv"]
        col = cmap(norm(r.onset_h))
        a.plot(t, y, color=fs.INK, lw=0.6)
        a.axvspan(t[0], t[-1], color=col, alpha=0.15, lw=0)
        on = (float(r.onset_idx) - float(r.snippet_start_idx))
        ts = (z[r.snippet_key + "__t_s"] - float(r.onset_idx)) / float(r.fs)
        y0 = y[int(max(0, min(len(y) - 1, on)))]
        if r.is_pure:
            b.plot(ts, y - y0, color=col, lw=0.9, alpha=0.85)
        e.plot(ts, y, color=col if r.is_pure else fs.NEUTRAL, lw=0.9, alpha=0.85)
    a.set_title(f"(a) Catalogue family {int(cat)} (trough), M2_aug CH0: {len(c)} events in their place in the recording",
                loc="left", fontsize=9)
    a.set_xlabel("time in the recording (h)"); a.set_ylabel("mV")
    for ax, ttl in ((b, f"(b) pure events ({int(c['is_pure'].sum())}), from their onset"),
                    (e, "(c) all events as recorded (impure in grey)")):
        ax.axvline(0, color=fs.MUTED, lw=0.8, ls="--")
        ax.set_xlabel("s from the onset of the fall")
        ax.set_title(ttl, loc="left", fontsize=8.5)
    b.set_ylabel("mV from onset"); e.set_ylabel("mV")
    sm = fs.plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    cb = fig.colorbar(sm, ax=[b, e], fraction=0.03, pad=0.02)
    cb.set_label("onset (h)", fontsize=8)
    return fs.save(fig, "ch3_drop_family")


# ------------------------------------------------------------------------------------------------ Chapter 6 --
FAM = [("drop_detection_v1", "drop v1"), ("drop_detection_v5", "drop v5"), ("cnn_10min", "CNN 10 min"),
       ("wavelet_encoded", "wavelet-encoded"), ("BEADs_invert_detect_v1", "BEADS"), ("symbol_search", "symbol search"),
       ("OASIS_Deconvolution", "OASIS"), ("cnn_60min", "CNN 60 min"), ("signal_threshold", "signal threshold"),
       ("noise_threshold", "noise threshold"), ("Wavelet_detection_prototype", "Dehshibi wavelet"),
       ("deconvolved_troughs", "deconvolved troughs"), ("matrix_profile", "matrix profile")]


def _window(name):
    x, meta = B.series(f"windows/{name}")
    return x, meta, B.time_h(meta, len(x))


def _spans(ax, df, y, colour, h=0.7, t0=0.0):
    if len(df):
        ax.broken_barh(list(zip(df["start_s"] / 3600 - t0, (df["end_s"] - df["start_s"]).clip(lower=1) / 3600)),
                       (y - h / 2, h), facecolors=colour, edgecolor="none")


def agreement():
    """Figure 6.2: what agreement looks like - 12 hours of M2_aug CH8, every family's detections, how many agree."""
    name = [f[:-4] for f in B.ls("windows") if f.startswith("agreement__") and f.endswith(".npz")][0]
    x, meta, th = _window(name)
    det = B.csv(f"detections_in_windows/{name}__detections")
    det = det[(det["is_surrogate"] == False) & (det["family"] != "seed_search")]  # noqa: E712
    ver = B.csv(f"detections_in_windows/{name}__verdicts")
    blind = ver[ver["queue"].notna()]
    fig = fs.plt.figure(figsize=(fs.TEXT_WIDTH_IN, 6.2))
    gs = fig.add_gridspec(3, 1, height_ratios=[1.0, 2.1, 0.9], hspace=0.22)
    a = fig.add_subplot(gs[0]); a.plot(th, x, color=fs.INK, lw=0.6)
    a.set_ylabel("mV"); a.tick_params(labelbottom=False); a.set_xlim(th[0], th[-1])
    a.set_title(f"(a) M2_aug channel index {meta.get('channel')}: 12 hours", loc="left", fontsize=8.5)
    b = fig.add_subplot(gs[1], sharex=a)
    rows = FAM + [("cnn_1min", "CNN 1 min (control)")]
    for k, (f, lab) in enumerate(rows):
        _spans(b, det[det["family"] == f], len(rows) - 1 - k, fs.NEUTRAL if f == "cnn_1min" else fs.INK_2)
    b.set_yticks(range(len(rows))); b.set_yticklabels([lab for _, lab in rows][::-1], fontsize=7)
    b.set_ylim(-0.7, len(rows) - 0.3); b.grid(axis="y", visible=False); b.tick_params(labelbottom=False)
    b.set_title("(b) every detector family's detections", loc="left", fontsize=8.5)
    c = fig.add_subplot(gs[2], sharex=a)
    cand = B.csv(f"detections_in_windows/{name}__candidates")
    cand = cand[(cand["end_s"] - cand["start_s"]) <= 1800]
    rng = np.random.default_rng(0)
    mid = (cand["start_s"] + cand["end_s"]) / 2 / 3600
    jit = cand["n_agree"] + rng.uniform(-0.3, 0.3, len(cand))
    cmap = fs.plt.get_cmap("Blues")
    c.scatter(mid, jit, s=3, c=cmap(0.25 + 0.75 * cand["n_agree"] / 13), lw=0, alpha=0.6, rasterized=True)
    m = blind.merge(cand[["anchor_detection_id", "n_agree"]], left_on="detection_id", right_on="anchor_detection_id",
                    how="inner")
    for r in m.itertuples():
        good = r.verdict in ("interesting", "seed")
        c.scatter([(r.start_s + r.end_s) / 2 / 3600], [r.n_agree], marker="o", s=38,
                  color=fs.CATEGORICAL[1] if good else "white", edgecolor=fs.INK, lw=1.0, zorder=4)
    c.set_ylim(0, 13.8); c.set_ylabel("families\nagreeing"); c.set_xlabel("time in the recording (h)")
    h = [fs.plt.Line2D([], [], ls="", marker="o", color=fs.CATEGORICAL[1], mec=fs.INK, label="blind verdict: event"),
         fs.plt.Line2D([], [], ls="", marker="o", mfc="white", color=fs.INK, label="blind verdict: not an event")]
    c.legend(handles=h, loc="lower right", fontsize=7, ncol=2, frameon=True, facecolor="white", edgecolor="white")
    return fs.save(fig, "ch6_agreement_excerpt")


def realsurr():
    """Figure 6.3: the same detectors on the recording and on its scrambled copy, over the same 12 hours."""
    name = [f[:-4] for f in B.ls("windows") if f.startswith("agreement__") and f.endswith(".npz")][0]
    x, meta, th = _window(name)
    det = B.csv(f"detections_in_windows/{name}__detections")
    rng = np.random.default_rng(1)
    Xf = np.fft.rfft(x - x.mean())
    ph = rng.uniform(0, 2 * np.pi, len(Xf)); ph[0] = 0
    xs = np.fft.irfft(np.abs(Xf) * np.exp(1j * ph), n=len(x)) + x.mean()
    fams = [("OASIS_Deconvolution", "OASIS"), ("deconvolved_troughs", "deconvolved troughs"),
            ("signal_threshold", "signal threshold"), ("symbol_search", "symbol search"),
            ("wavelet_encoded", "wavelet-encoded"), ("drop_detection_v1", "drop v1")]
    fig = fs.plt.figure(figsize=(fs.TEXT_WIDTH_IN, 5.4))
    gs = fig.add_gridspec(3, 1, height_ratios=[0.9, 0.9, 2.0], hspace=0.18)
    a = fig.add_subplot(gs[0]); a.plot(th, x, color=fs.INK, lw=0.6); a.set_ylabel("mV")
    a.set_title("(a) The recording (M2_aug, 12 hours)", loc="left", fontsize=8.5); a.tick_params(labelbottom=False)
    b = fig.add_subplot(gs[1], sharex=a); b.plot(th, xs, color=fs.INK_2, lw=0.6); b.set_ylabel("mV")
    b.set_title("(b) A phase-randomised copy: same frequencies, shapes scrambled (drawn for this figure)", loc="left",
                fontsize=8.5)
    b.tick_params(labelbottom=False)
    c = fig.add_subplot(gs[2], sharex=a)
    labels = []
    for k, (f, lab) in enumerate(fams):
        y = (len(fams) - 1 - k) * 2.6
        real = det[(det["family"] == f) & (det["is_surrogate"] == False)]  # noqa: E712
        sur = det[(det["family"] == f) & (det["is_surrogate"] == True)]  # noqa: E712
        _spans(c, real, y + 0.65, fs.SPECIES_COLOUR["oyster"], h=0.9)
        _spans(c, sur, y - 0.45, fs.CATEGORICAL[1], h=0.9)
        labels.append((y + 0.1, f"{lab}\n{len(real)} real / {len(sur)} copy"))
    c.set_yticks([p for p, _ in labels]); c.set_yticklabels([l for _, l in labels], fontsize=6.8)
    c.grid(axis="y", visible=False); c.set_xlabel("time in the recording (h)")
    c.set_title("(c) Each detector's spans on the recording (blue) and on its own scrambled copy from the sweep (orange)",
                loc="left", fontsize=8.5)
    c.set_xlim(th[0], th[-1])
    return fs.save(fig, "ch6_real_vs_surrogate")


# ------------------------------------------------------------------------------------------------ Chapter 7 --
def seeds(which=("drop30", "spike37")):
    """Figure 7.1: two library seeds, their blind-judged matches across M2_aug's channels, and random windows of the
    same length judged in the same blind queue."""
    sw = B.stack("queues/queue35_seed_windows")
    qw = B.stack("queues/queue35_windows")
    items = B.csv("queues/queue_items")
    items = items[items["queue"] == 35]
    qi = qw.index.reset_index().rename(columns={"index": "pos"})
    zn = lambda v: (v - np.nanmean(v)) / (np.nanstd(v) + 1e-12)
    fig = fs.plt.figure(figsize=(fs.TEXT_WIDTH_IN, 2.35 * len(which) + 0.3))
    gs = fig.add_gridspec(len(which), 4, width_ratios=[0.8, 1.4, 1.0, 1.0], wspace=0.42, hspace=0.62)
    for r_, key in enumerate(which):
        sr = sw.index[sw.index["seed_key"] == key].index[0]
        t, y = sw.window(int(sr))
        a0, a1 = sw.index.loc[sr, "item_t0_s"], sw.index.loc[sr, "item_t1_s"]
        m = (t >= a0) & (t <= a1)
        L = a1 - a0
        ax = fig.add_subplot(gs[r_, 0])
        ax.plot(t[m] - a0, y[m], color=fs.INK, lw=1.4)
        ax.set_title(f"seed {key}\n{L:.0f} s", fontsize=8, loc="left"); ax.set_xlabel("s"); ax.set_ylabel("mV")
        mt = qi[qi["stratum"] == key]
        ctl = qi[(qi["stratum"] == "control") & (np.isclose(qi["item_t1_s"] - qi["item_t0_s"], L))]
        bx = fig.add_subplot(gs[r_, 1])
        for _, rr in mt.iterrows():
            good = rr["verdict_own"] in ("interesting", "seed")
            bx.scatter([rr["item_t0_s"] / 3600], [rr["channel"]], s=14, color=fs.SPECIES_COLOUR["oyster"] if good
                       else "white", edgecolor=fs.SPECIES_COLOUR["oyster"], lw=0.8)
        bx.scatter([a0 / 3600], [sw.index.loc[sr, "channel"]], marker="*", s=90, color=fs.INK, zorder=4)
        bx.set_ylim(-0.8, 15.8); bx.set_xlim(0, 721); bx.set_yticks([0, 5, 10, 15])
        bx.set_xlabel("time in M2_aug (h)"); bx.set_ylabel("channel")
        n_ok = int(mt["verdict_own"].isin(["interesting", "seed"]).sum()); n_j = int(mt["verdict_own"].isin(
            ["interesting", "seed", "not_interesting"]).sum())
        bx.set_title(f"matches: {n_ok}/{n_j} accepted", fontsize=8, loc="left")
        cx = fig.add_subplot(gs[r_, 2]); dx = fig.add_subplot(gs[r_, 3], sharey=cx)
        grid = np.linspace(0, 1, 200)
        for _, rr in mt.iterrows():
            tt, yy = qw.window(int(rr["pos"]))
            mm = (tt >= rr["item_t0_s"]) & (tt <= rr["item_t1_s"])
            if mm.sum() > 3:
                u = (tt[mm] - rr["item_t0_s"]) / max(rr["item_t1_s"] - rr["item_t0_s"], 1)
                cx.plot(grid, zn(np.interp(grid, u, yy[mm])), color=fs.SPECIES_COLOUR["oyster"], lw=0.5, alpha=0.35)
        cx.plot(grid, zn(np.interp(grid, (t[m] - a0) / L, y[m])), color=fs.INK, lw=1.8)
        cx.set_title("matches (z)", fontsize=8, loc="left"); cx.set_xticks([])
        for _, rr in ctl.iterrows():
            tt, yy = qw.window(int(rr["pos"]))
            mm = (tt >= rr["item_t0_s"]) & (tt <= rr["item_t1_s"])
            if mm.sum() > 3:
                good = rr["verdict_own"] in ("interesting", "seed")
                u = (tt[mm] - rr["item_t0_s"]) / max(rr["item_t1_s"] - rr["item_t0_s"], 1)
                dx.plot(grid, zn(np.interp(grid, u, yy[mm])), color=fs.CATEGORICAL[1] if good else fs.NEUTRAL,
                        lw=0.7, alpha=0.6)
        c_ok = int(ctl["verdict_own"].isin(["interesting", "seed"]).sum())
        c_j = int(ctl["verdict_own"].isin(["interesting", "seed", "not_interesting"]).sum())
        dx.set_title(f"random: {c_ok}/{c_j} accepted", fontsize=8, loc="left"); dx.set_xticks([])
        dx.tick_params(labelleft=False)
    return fs.save(fig, "ch7_seeds")


# ------------------------------------------------------------------------------------------------ Chapter 5 --
GALLERY = [("M2_aug", "oyster, grow pack"), ("M2_concat", "oyster, grow pack"), ("M4_aug", "oyster, held out"),
           ("MJu26a_fs2", "lion's mane, jar"), ("LM_fs2", "lion's mane, grow pack"), ("CO_fs2", "chocolate oyster"),
           ("SO_fs2", "snow oyster"), ("SH_fs2", "Asian shiitake")]


def gallery():
    """Figure 5.1: one channel of each recording over a day, and its busiest 30 minutes."""
    files = {f.split("__")[1]: f[:-4] for f in B.ls("windows") if f.startswith("gallery__") and f.endswith(".npz")}
    rows = [(k, d) for k, d in GALLERY if k in files]
    fig, axes = fs.figure("full", 1.0 * len(rows) + 0.4, len(rows), 2, gridspec_kw={"width_ratios": [2.6, 1.0]})
    for r_, (k, desc) in enumerate(rows):
        x, meta, th = _window(files[k])
        col = fs.colour(k.replace("_aug", "") if k == "M4_aug" else k)
        a, b = axes[r_]
        a.plot(th - th[0], x, color=col, lw=0.6)
        w = int(1800 * float(meta["fs"]))
        if len(x) > w:
            # the 30 minutes with the largest range of values
            from numpy.lib.stride_tricks import sliding_window_view
            step = max(1, w // 6)
            v = sliding_window_view(np.nan_to_num(x, nan=np.nanmedian(x)), w)[::step]
            j = int(np.argmax(v.max(axis=1) - v.min(axis=1))) * step
        else:
            j = 0
        a.axvspan((th[j] - th[0]), (th[min(j + w, len(th) - 1)] - th[0]), color=fs.INK_2, alpha=0.18, lw=0)
        tz = (np.arange(min(w, len(x) - j)) / float(meta["fs"])) / 60
        b.plot(tz, x[j:j + w], color=col, lw=0.8)
        nm = {"M4_aug": "M4", "MJu26a_fs2": "MJu26a", "LM_fs2": "LM", "CO_fs2": "CO", "SO_fs2": "SO", "SH_fs2": "SH"}.get(k, k)
        a.set_ylabel("mV", fontsize=7)
        a.text(0.01, 0.95, f"{nm} ({desc}), channel index {meta['channel']}, {th[0]:.0f}–{th[-1]:.0f} h",
               transform=a.transAxes, fontsize=7, va="top", color=fs.INK,
               bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=1.0))
        for ax in (a, b):
            ax.tick_params(labelsize=6.5)
            ax.margins(x=0)
        if r_ < len(rows) - 1:
            a.tick_params(labelbottom=False); b.tick_params(labelbottom=False)
    axes[-1, 0].set_xlabel("hours from the start of the day shown")
    axes[-1, 1].set_xlabel("minutes (the shaded 30)")
    fig.subplots_adjust(left=0.08, right=0.99, bottom=0.06, top=0.99, hspace=0.18, wspace=0.18)
    return fs.save(fig, "ch5_gallery")


def anatomyevent():
    """Figure 5.2: how an event is measured, on one accepted drop (the tool's own event_shape measures)."""
    sys.path.insert(0, fs.ROOT)
    from Working.interrogation.event_shape import measure_events
    st = B.stack("library_events/library_event_windows")
    ev = B.csv("library_events/events_with_family")
    acc = set(ev.loc[ev["accepted_parts"] > 0, "event_id"])
    idx = st.index.reset_index().rename(columns={"index": "pos"})
    idx = idx[idx["event_id"].isin(acc) & ((idx["item_t1_s"] - idx["item_t0_s"]).between(60, 400))]
    best, score = None, -1
    for _, r in idx.iterrows():
        t, y = st.window(int(r["pos"]))
        fsr = 1.0 / float(r["dt_s"])
        s0 = int(round((r["item_t0_s"] - t[0]) * fsr)); s1 = int(round((r["item_t1_s"] - t[0]) * fsr))
        f, _ = measure_events(y, [s0], [s1], fsr, polarity="drop", to_mv=1.0)
        f = f.iloc[0]
        if not np.isfinite(f["recovery_idx"]) or not np.isfinite(f["fwhm_s"]):
            continue
        noise = np.nanstd(np.diff(y)) + 1e-9
        sc = f["event_amplitude_mv"] / noise
        if sc > score:
            best, score = (t, y, fsr, f, r), sc
    t, y, fsr, f, r = best
    tt = (t - t[0])
    on, ex, rc = int(f["onset_idx"]), int(f["extremum_idx"]), int(f["recovery_idx"])
    amp = float(f["event_amplitude_mv"])
    fig, ax = fs.figure("full", 3.2)
    ax.plot(tt, y, color=fs.INK, lw=1.2)
    rngv = np.nanmax(y) - np.nanmin(y)
    offs = {on: (8, 4), ex: (-46, -4), rc: (8, -12)}
    for k, lab, c in ((on, "onset", fs.CATEGORICAL[0]), (ex, "trough", fs.CATEGORICAL[1]), (rc, "half recovery", fs.CATEGORICAL[2])):
        ax.scatter([tt[k]], [y[k]], s=40, color=c, zorder=4)
        ax.annotate(lab, (tt[k], y[k]), xytext=offs[k], textcoords="offset points", fontsize=7.5, color=c)
    ytop = y[on]
    xa = tt[on] - 0.07 * (tt[-1] - tt[0])
    ax.annotate("", xy=(xa, y[ex]), xytext=(xa, ytop), arrowprops=dict(arrowstyle="<->", color=fs.INK_2, lw=1))
    ax.plot([xa, tt[on]], [ytop, ytop], color=fs.MUTED, lw=0.7, ls=":")
    ax.plot([xa, tt[ex]], [y[ex], y[ex]], color=fs.MUTED, lw=0.7, ls=":")
    ax.text(xa, (y[ex] + ytop) / 2, f"depth  \n{amp:.0f} mV  ", fontsize=7.5, va="center", ha="right", color=fs.INK_2)
    yb = np.nanmin(y) - 0.14 * rngv
    for (k0, k1, lab, off) in ((on, ex, f"fall {tt[ex] - tt[on]:.0f} s", 0.0),
                               (ex, rc, f"recovery {float(f['recovery_time_s']):.0f} s", 0.0),
                               (on, rc, f"duration {float(f['duration_s']):.0f} s", -0.12)):
        yy = yb + off * rngv
        ax.annotate("", xy=(tt[k0], yy), xytext=(tt[k1], yy), arrowprops=dict(arrowstyle="<->", color=fs.INK_2, lw=1))
        ax.text((tt[k0] + tt[k1]) / 2, yy + 0.01 * rngv, lab, fontsize=7, ha="center", va="bottom", color=fs.INK_2)
    half = y[on] - amp / 2 if np.isfinite(amp) else np.nan
    ax.axhline(half, color=fs.MUTED, lw=0.8, ls=":")
    ax.text(tt[0], half, f"half depth: the event is below this line for {float(f['fwhm_s']):.0f} s (FWHM)", fontsize=7,
            va="bottom", ha="left", color=fs.INK_2)
    ax.set_xlabel("seconds"); ax.set_ylabel("mV")
    ax.set_ylim(yb - 0.2 * rngv, np.nanmax(y) + 0.05 * rngv)
    print("anatomy event:", r["event_id"], r["source_file"], f[["event_amplitude_mv", "duration_s", "fwhm_s", "recovery_time_s"]].to_dict())
    return fs.save(fig, "ch5_anatomy_event")


def _train_window():
    best = None
    for f in B.ls("windows"):
        if f.startswith("b1_trains__") and f.endswith(".npz"):
            name = f[:-4]
            det = B.csv(f"detections_in_windows/{name}__detections")
            on = det[(det["variant"] == "drop_detection_v1") & (det["is_surrogate"] == False)]  # noqa: E712
            if best is None or len(on) > len(best[1]):
                best = (name, on.sort_values("start_s"))
    return best


def anatomytrain():
    """Figure 5.3: how a train is measured - four hours of drops with the interval between onsets written in."""
    name, on = _train_window()
    x, meta, th = _window(name)
    o = on["start_s"].to_numpy(float)
    g = np.diff(o)
    fig = fs.plt.figure(figsize=(fs.TEXT_WIDTH_IN, 2.9))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 0.42], hspace=0.05)
    a = fig.add_subplot(gs[0]); a.plot(th, x, color=fs.INK, lw=0.6)
    for v in o:
        a.axvline(v / 3600, color=fs.SPECIES_COLOUR["oyster"], lw=0.8, alpha=0.6)
    a.set_ylabel("mV"); a.tick_params(labelbottom=False); a.set_xlim(th[0], th[-1])
    rec = name.split("__")[1]
    a.set_title(f"{fs.label(rec)}, channel index {meta['channel']}: {len(o)} drops (drop detector v1) in four hours",
                loc="left", fontsize=8.5)
    b = fig.add_subplot(gs[1], sharex=a)
    for k, (v0, v1) in enumerate(zip(o[:-1], o[1:])):
        y = 0.65 if k % 2 == 0 else 0.25
        b.annotate("", xy=(v0 / 3600, y), xytext=(v1 / 3600, y), arrowprops=dict(arrowstyle="<->", color=fs.INK_2, lw=0.7))
        b.text((v0 + v1) / 2 / 3600, y + 0.06, f"{v1 - v0:.0f}", fontsize=6.3, ha="center", va="bottom")
    for v in o:
        b.axvline(v / 3600, color=fs.SPECIES_COLOUR["oyster"], lw=0.8, alpha=0.6, ymax=0.95)
    b.set_ylim(0, 1); b.set_yticks([]); b.grid(False)
    b.set_xlabel("time in the recording (h); numbers are the seconds between onsets")
    cv2 = np.mean(2 * np.abs(np.diff(g)) / (g[1:] + g[:-1]))
    lv = 3 * np.mean(((g[:-1] - g[1:]) / (g[:-1] + g[1:])) ** 2)
    print(f"anatomy train {name}: n={len(o)}, CV={np.std(g) / np.mean(g):.2f}, CV2={cv2:.2f}, LV={lv:.2f}")
    return fs.save(fig, "ch5_anatomy_train")


def main():
    global B
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("which", nargs="*")
    a = ap.parse_args()
    B = BI.Bundle(a.bundle)
    fs.apply()
    for w in a.which or ["m4", "r4_examples"]:
        print(globals()[w]())


if __name__ == "__main__":
    main()
