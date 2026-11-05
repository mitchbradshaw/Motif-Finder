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
