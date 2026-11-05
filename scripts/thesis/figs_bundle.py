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
    bx.set_title("(b) After detection: your blind exam verdicts (triangles) and the events R4 accepts (bars)",
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
    h = [fs.plt.Line2D([], [], ls="", marker="v", color=fs.SPECIES_COLOUR["oyster"], label="you: event, R4 agrees"),
         fs.plt.Line2D([], [], ls="", marker="v", mfc="white", color=fs.SPECIES_COLOUR["oyster"],
                       label="you: not an event, R4 agrees"),
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
    groups = [("Hits: you and R4 both say event", (idx["human"] == 1) & (idx["r4_interesting"] == 1), False),
              ("False alarms: R4 says event, you said not", (idx["human"] == 0) & (idx["r4_interesting"] == 1), False),
              ("Misses: you said event, R4 said not", (idx["human"] == 1) & (idx["r4_interesting"] == 0), True)]
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
