"""Diagram: the whole drop (top of the deepest fall to its bottom) against event_shape's steep core, on real spans.

Read-only (database `mode=ro`, channels memory-mapped). Writes docs/library_analysis/20261123/:
whole_drop_vs_steep_core.png, whole_drop.csv (both measurements for every measured span) and whole_drop_summary.json.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/library_analysis/fig_whole_drop_vs_core_20261123.py
        [--out DIR]   (another folder, e.g. to redraw after a rule change without overwriting the approved diagram)
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
sys.path.insert(0, os.path.join(ROOT, "scripts", "thesis"))
sys.path.insert(0, os.path.dirname(__file__))

import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from Working.interrogation import whole_drop as WD  # noqa: E402

INV = os.path.join(ROOT, "docs", "thesis", "data", "ch9_inventory_20261109", "measures.csv")
SPANS = os.path.join(ROOT, "docs", "thesis", "data", "accepted_catalogue_20261109", "accepted_spans.csv")
DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite").replace("\\", "/")
OUT = os.path.join(ROOT, "docs", "library_analysis", "20261123")
OLD, NEW = "#eb6834", "#2a78d6"
SEED = 20261123


def to_mv(units):
    return {"mV": 1.0, "uV": 0.001}.get(units or "V", 1000.0)


def extra_steepness(x, rec, r, w):
    """How steep the part of the whole drop OUTSIDE the old core is, against the core's own steepest fall: a slow
    lead-in or tail is well under 1, a second steep fall (a staircase) is near 1 or above."""
    if not (np.isfinite(r.onset_idx) and np.isfinite(r.extremum_idx)) or r.polarity != -1:
        return {}
    on, ex, top, bot = int(r.onset_idx), int(r.extremum_idx), w["top_idx"], w["bottom_idx"]
    lo, hi = min(on, top), max(ex, bot) + 1
    k = max(2, int(round(2 * rec["fs"])))
    a0 = max(0, lo - k)
    seg = np.asarray(x[a0:hi + k], dtype=float) * to_mv(rec["units"])
    g = -np.gradient(WD.smoothed(seg, rec["fs"]))
    core = g[on - a0:ex - a0 + 1]
    if core.size == 0 or core.max() <= 0:
        return {}
    lead = g[top - a0:max(top, on) - a0]
    tail = g[min(ex, bot) - a0 + 1:bot - a0 + 1]
    return {"lead_steep_ratio": float(lead.max() / core.max()) if lead.size else 0.0,
            "tail_steep_ratio": float(tail.max() / core.max()) if tail.size else 0.0}


def measure_all(conn):
    recs = {int(r[0]): {"npy": r[1], "fs": float(r[2]), "units": r[3]}
            for r in conn.execute("SELECT id, npy_path, fs, units FROM recordings")}
    m = pd.read_csv(INV)
    s = pd.read_csv(SPANS)
    m = m.merge(s[["event_id", "channel", "span_s"]], on="event_id", how="left")
    m = m[m["status"].isin(["single", "multiple"])].copy()
    rows = []
    for rid, g in m.groupby("recording_id"):
        rec = recs[int(rid)]
        x = np.load(os.path.join(ROOT, rec["npy"]), mmap_mode="r")
        allspans = np.sort(s.loc[s["recording_id"] == rid, "start_idx"].to_numpy())
        for r in g.itertuples(index=False):
            j = np.searchsorted(allspans, r.start_idx, side="right")
            nxt = int(allspans[j]) if j < len(allspans) else None
            w = WD.measure(x, int(r.start_idx), int(r.end_idx), rec["fs"], to_mv=to_mv(rec["units"]), next_start=nxt)
            seg = np.asarray(x[int(r.start_idx):int(r.end_idx)], dtype=float) * to_mv(rec["units"])
            k = max(1, int(round(rec["fs"])))
            span_range = float(np.ptp(np.convolve(seg, np.ones(k) / k, mode="valid"))) if len(seg) > k else float(np.ptp(seg))
            row = {"event_id": r.event_id, "dataset": r.dataset, "recording_id": int(rid), "channel": int(r.channel),
                   "fs": rec["fs"], "status": r.status, "n_falls": r.n_falls, "start_idx": int(r.start_idx),
                   "end_idx": int(r.end_idx), "span_range_mv": span_range,
                   "core_polarity": r.polarity, "core_onset_idx": r.onset_idx, "core_extremum_idx": r.extremum_idx,
                   "core_recovery_idx": r.recovery_idx, "core_depth_mv": r.depth_mv, "core_fall_s": r.fall_s,
                   "core_width_s": r.duration_s}
            if w["ok"]:
                row.update({"whole_" + k2: v for k2, v in w.items() if k2 not in ("ok", "events")})
                row["whole_events"] = json.dumps([[int(e["top_idx"]), int(e["bottom_idx"]), round(e["depth_mv"], 4)]
                                                  for e in w["events"]])
                row.update(extra_steepness(x, rec, r, w))
            else:
                row["whole_why"] = w.get("why")
            rows.append(row)
    d = pd.DataFrame(rows)
    d["core_frac"] = d["core_depth_mv"] / d["span_range_mv"]
    d["whole_frac"] = d["whole_depth_mv"] / d["span_range_mv"]
    d["depth_ratio"] = d["whole_depth_mv"] / d["core_depth_mv"]
    return d, recs


#: The diagram's examples, chosen by eye from a contact sheet of rule-picked candidates (18-23 Nov), so each panel
#: shows what its label says. `pick_by_rule` is how the candidates were drawn.
CASES = [
    ("the two agree (most spans)", "accepted-b26a11907cfbeeb8"),
    ("CH14 square drop: the two agree", "accepted-368fe470f5ab5f81"),
    ("a typical span (median depth ratio)", "accepted-c49a40dc15ad1bba"),
    ("a slow decline, a pause, a sharp drop:\ntwo events (your correction)", "accepted-fd70c2540b84b100"),
    ("a steep start and a slow tail:\none event, to the bottom of the tail", "accepted-86b1a578aa82e2be"),
    ("window starts mid-fall (CH15 train):\nthe top is found before it", "accepted-d1fd6aab06a584b2"),
    ("10 Hz: the core lands on a noise wiggle", "accepted-943bdc9e393ee60f"),
    ("2 Hz: the core lands on a wiggle", "accepted-97ee1da3ccd74fd3"),
    ("1 Hz: the core lands on a wiggle", "accepted-2523b7c6212f0b63"),
    ("a staircase, fall-pause-fall:\ntwo events (your correction)", "accepted-22b811f0b7589aeb"),
    ("falls separated by rebounds:\nfour events (your correction)", "accepted-a534d565cd14128d"),
    ("rise first, then the fall runs on\nto its bottom (your correction)", "accepted-5fa3587d7bc76b5a"),
]


def pick(d):
    cases = []
    for label, eid in CASES:
        row = d[d["event_id"] == eid]
        if not row.empty:
            cases.append(row.iloc[0].to_dict() | {"case": label})
    return cases


def pick_by_rule(d):
    """One real span per kind of case, chosen by rule (seeded): the contact sheet's source. Only spans both rules
    read as a drop, so the two are compared on the same fall."""
    rng = np.random.default_rng(SEED)
    ok = d["whole_depth_mv"].notna() & (d["core_polarity"] == -1) & ~d["whole_rise_dominated"].fillna(True).astype(bool)
    single = d["status"] == "single"
    ext = d["whole_top_extended"].fillna(False).astype(bool)
    lead = (d["core_onset_idx"] - d["whole_top_idx"]) / (d["core_extremum_idx"] - d["core_onset_idx"]).clip(lower=1)
    tail = (d["whole_bottom_idx"] - d["core_extremum_idx"]) / (d["core_extremum_idx"] - d["core_onset_idx"]).clip(lower=1)

    def one(mask, label):
        c = d[mask & ok]
        if c.empty:
            return None
        return c.iloc[int(rng.integers(len(c)))].to_dict() | {"case": label}

    near = (d["whole_top_idx"] - d["core_onset_idx"]).abs() <= np.maximum(2, 0.5 * d["fs"])
    same = d["depth_ratio"].between(0.97, 1.05) & near
    median = d.loc[ok, "depth_ratio"].median()
    slow_lead = d["lead_steep_ratio"].fillna(9) < 0.3
    slow_tail = d["tail_steep_ratio"].fillna(9) < 0.3
    cases = [
        one(single & same & (d["dataset"] == "M2_aug") & d["whole_width_s"].notna(), "the two agree (most spans)"),
        one(single & same & (d["recording_id"] == 663) & d["whole_width_s"].notna(), "CH14 square drop: the two agree"),
        one(single & d["depth_ratio"].between(median - 0.03, median + 0.03) & (d["core_frac"] >= 0.3),
            f"a typical span (depth ratio ≈ {median:.2f})"),
        one(single & d["depth_ratio"].between(1.5, 3.0) & (d["core_frac"] >= 0.3) & (lead > 3) & (tail < 1)
            & slow_lead, "slow decline BEFORE the sharp drop:\nthe whole drop includes it"),
        one(single & d["depth_ratio"].between(1.5, 3.0) & (d["core_frac"] >= 0.3) & (tail > 3) & (lead < 1)
            & slow_tail, "slow fall AFTER the steep start:\nthe whole drop includes it"),
        one((d["recording_id"] == 664) & ext & (d["core_frac"] < 0.3), "window starts mid-fall (CH15 train)"),
        one((d["fs"] == 10) & (d["core_frac"] < 0.3) & ~ext & (d["recording_id"] != 664),
            "10 Hz: the core lands on a noise wiggle"),
        one((d["fs"] == 2) & (d["core_frac"] < 0.3), "2 Hz: the core lands on a wiggle"),
        one((d["fs"] == 1) & (d["core_frac"] < 0.3), "1 Hz: the core lands on a wiggle"),
        one((d["depth_ratio"] > 1.8) & (d["core_frac"] >= 0.3)
            & ((d["tail_steep_ratio"].fillna(0) > 0.6) | (d["lead_steep_ratio"].fillna(0) > 0.6)),
            "a staircase, two steep falls in one span:\nthe whole drop spans both"),
    ]
    return [c for c in cases if c is not None]


def draw_schematic(ax):
    t = np.linspace(0, 100, 1001)
    tt = np.clip(t - 20, 0, 50)
    fall_curve = 0.15 - 6.0 * (1 - np.exp(-tt / 3.0)) - 2.5 * (tt / 50.0)   # a steep start, then a slow tail
    y = np.where(t < 20, 0.15 * t / 20, fall_curve)
    y = np.where(t >= 70, fall_curve[np.searchsorted(t, 70)] + (t - 70) * 0.25, y)
    ax.plot(t, y, color=fs.INK_2, lw=1.4)
    # the knee: where the slope -2 e^(-tt/3) - 0.05 has eased to 5 % of its steepest (-2.05)
    core_on, core_ex = 20.0, 20.0 + 3.0 * np.log(2.0 / (0.05 * 2.05 - 0.05))
    i0, i1 = np.searchsorted(t, core_on), np.searchsorted(t, core_ex)
    ax.plot(t[i0:i1 + 1], y[i0:i1 + 1], color=OLD, lw=5, alpha=0.55, solid_capstyle="round")
    j1 = int(np.argmin(y))
    ax.plot(t[i0:j1 + 1], y[i0:j1 + 1], color=NEW, lw=2.2, alpha=0.95)
    ax.plot([core_on], [y[i0]], "o", color=OLD, ms=7, mfc="white", mew=2)
    ax.plot([core_ex], [y[i1]], "o", color=OLD, ms=7, mew=0)
    ax.plot([t[i0]], [y[i0]], "^", color=NEW, ms=8)
    ax.plot([t[j1]], [y[j1]], "v", color=NEW, ms=8)
    ax.annotate("", xy=(13, y[i1]), xytext=(13, y[i0]), arrowprops=dict(arrowstyle="<->", color=OLD, lw=1.6))
    ax.text(12, (y[i0] + y[i1]) / 2, "steep core\ndepth", color=OLD, ha="right", va="center", fontsize=8)
    ax.annotate("", xy=(77, y[j1]), xytext=(77, y[i0]), arrowprops=dict(arrowstyle="<->", color=NEW, lw=1.6))
    ax.text(78.5, (y[i0] + y[j1]) / 2, "whole drop\ndepth", color=NEW, ha="left", va="center", fontsize=8)
    ax.text(31, y[i1] + 0.3, "knee: the slope has eased to 5 % of its steepest", color=OLD, fontsize=7.5, va="bottom")
    ax.text(t[j1] - 1, y[j1] - 0.35, "bottom: the lowest point the fall reaches", color=NEW, fontsize=7.5, ha="right",
            va="top")
    ax.text(21, 0.35, "top: where the deepest fall starts", color=NEW, fontsize=7.5, va="bottom")
    ax.set_xlim(0, 100)
    ax.set_ylim(y.min() - 1.4, 1.2)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ("left", "bottom"):
        ax.spines[sp].set_visible(False)
    ax.grid(False)
    ax.set_title("What is measured: before (steep core, the drop detector's rule) and now (whole drop)", loc="left")


def draw_example(ax, c, recs):
    rec = recs[int(c["recording_id"])]
    f = rec["fs"]
    x = np.load(os.path.join(ROOT, rec["npy"]), mmap_mode="r")
    a, b = int(c["start_idx"]), int(c["end_idx"])
    events = json.loads(c["whole_events"]) if isinstance(c.get("whole_events"), str) else []
    pad = int(0.25 * (b - a))
    lo = int(min([a] + [e[0] for e in events])) - pad
    marks = [b] + [e[1] for e in events] + [v for v in (c.get("whole_recovery_idx"), c.get("core_recovery_idx"))
                                            if v is not None and np.isfinite(v)]
    hi = int(max(marks)) + pad
    lo, hi = max(0, lo), min(len(x), hi)
    y = np.asarray(x[lo:hi], dtype=float) * to_mv(rec["units"])
    t = (np.arange(lo, hi) - a) / f
    ax.axvspan(0, (b - a) / f, color="#efeeea", lw=0, zorder=0)
    ax.plot(t, y, color=fs.INK_2, lw=0.8, zorder=2)

    def seg(i, j, colour, lw, alpha, z):
        i, j = int(i) - lo, int(j) - lo
        ax.plot(t[i:j + 1], y[i:j + 1], color=colour, lw=lw, alpha=alpha, zorder=z, solid_capstyle="round")

    def mark(idx, mk, col, **kw):
        i = int(idx) - lo
        if 0 <= i < len(y):
            ax.plot(t[i], y[i], mk, color=col, ms=7, zorder=5, **kw)

    if c["core_polarity"] == -1:
        seg(c["core_onset_idx"], c["core_extremum_idx"], OLD, 5.5, 0.5, 3)
        mark(c["core_onset_idx"], "o", OLD, mfc="white", mew=1.8)
        mark(c["core_extremum_idx"], "o", OLD, mew=0)
    for n, (top, bottom, _) in enumerate(events, start=1):
        seg(top, bottom, NEW, 1.8, 0.95, 4)
        mark(top, "^", NEW)
        mark(bottom, "v", NEW)
        if len(events) > 1:
            i = int(top) - lo
            if 0 <= i < len(y):
                ax.annotate(str(n), (t[i], y[i]), textcoords="offset points", xytext=(4, 5), fontsize=8,
                            color=NEW, fontweight="bold")
    for idx, col in ((c.get("core_recovery_idx"), OLD), (c.get("whole_recovery_idx"), NEW)):
        if idx is not None and np.isfinite(idx):
            mark(round(idx), "x", col, mew=2)
    ch = int(c["channel"]) + 1
    core_w = "no half recovery" if not np.isfinite(c["core_width_s"]) else f"width {c['core_width_s']:.3g} s"
    new_w = ("no half recovery" if not np.isfinite(c.get("whole_width_s", np.nan))
             else f"width {c['whole_width_s']:.3g} s")
    many = f"{len(events)} events, deepest " if len(events) > 1 else ""
    ax.set_title(f"{c['case']}\n{c['dataset']} CH{ch} · {f:g} Hz", loc="left", fontsize=8.3)
    before = (f"before: {c['core_depth_mv']:.3g} mV, {core_w}" if c["core_polarity"] == -1
              else "before: measured as a rise (a spike)")
    ax.text(0.0, -0.30, before, transform=ax.transAxes, fontsize=7.6, color=OLD, va="top")
    ax.text(0.0, -0.40, f"now: {many}{c['whole_depth_mv']:.3g} mV,", transform=ax.transAxes, fontsize=7.6,
            color=NEW, va="top")
    ax.text(0.0, -0.50, f"     {new_w}", transform=ax.transAxes, fontsize=7.6, color=NEW, va="top")
    ax.set_xlabel("s from the accepted span's start", fontsize=7.3, labelpad=1)
    ax.tick_params(labelsize=7)
    ax.grid(False)


def main(out=OUT):
    fs.apply()
    os.makedirs(out, exist_ok=True)
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    d, recs = measure_all(conn)
    conn.close()
    d.to_csv(os.path.join(out, "whole_drop.csv"), index=False)
    cases = pick(d)
    fig = plt.figure(figsize=(21.0, 11.5))
    gs = fig.add_gridspec(3, 6, height_ratios=[0.8, 1, 1], hspace=0.98, wspace=0.3)
    draw_schematic(fig.add_subplot(gs[0, :]))
    for k, c in enumerate(cases[:12]):
        ax = fig.add_subplot(gs[1 + k // 6, k % 6])
        draw_example(ax, c, recs)
        if k % 6 == 0:
            ax.set_ylabel("mV (as recorded)", fontsize=7.5)
    handles = [plt.Line2D([], [], color=OLD, lw=5, alpha=0.5, marker="o", ms=6, mfc="white", mew=1.6,
                          label="before: steep core, onset ○ to knee trough ●  (× its half recovery)"),
               plt.Line2D([], [], color=NEW, lw=1.8, label="now: each drop event's whole drop, top ▲ to bottom ▼, "
                                                         "numbered when a span holds several  (× the deepest one's "
                                                         "half recovery)"),
               plt.Rectangle((0, 0), 1, 1, color="#efeeea", label="the accepted span")]
    fig.legend(handles=handles, loc="lower center", ncol=3, fontsize=8.5, bbox_to_anchor=(0.5, -0.035))
    ok = d["whole_depth_mv"].notna()
    summ = {
        "spans_measured": int(ok.sum()), "spans": int(len(d)),
        "rise_dominated": int(d["whole_rise_dominated"].fillna(False).astype(bool).sum()),
        "flagged_core_frac_lt_0.3": int((d["core_frac"] < 0.3).sum()),
        "flagged_whole_frac_lt_0.3": int((d["whole_frac"] < 0.3).sum()),
        "depth_ratio_median": float(d.loc[ok, "depth_ratio"].median()),
        "depth_within_10pct": int((d.loc[ok, "depth_ratio"].sub(1).abs() <= 0.10).sum()),
        "top_extended_back": int(d["whole_top_extended"].fillna(False).astype(bool).sum()),
        "bottom_extended_forward": int(d["whole_bottom_extended"].fillna(False).astype(bool).sum()),
        "width_measured_core": int(d["core_width_s"].notna().sum()),
        "width_measured_whole": int(d["whole_width_s"].notna().sum()),
        "spans_with_several_events": int((d["whole_n_events"].fillna(0) >= 2).sum()),
        "events_in_spans": int(d["whole_n_events"].fillna(0).sum()),
        "no_event_found": int(d["whole_depth_mv"].isna().sum()),
        "long_tail": int(d["whole_long_tail"].fillna(False).astype(bool).sum()) if "whole_long_tail" in d else 0,
        "cases": [{k: c[k] for k in ("case", "event_id", "dataset", "recording_id", "core_depth_mv",
                                     "whole_depth_mv")} for c in cases],
    }
    fig.text(0.01, 0.955, f"A drop event is one unbroken fall: a pause or a rebound ends it. Of {summ['spans']:,} "
             f"measured accepted spans, {summ['spans_with_several_events']:,} hold two or more events "
             f"({summ['events_in_spans']:,} events in all); the deepest event's depth agrees with the steep core "
             f"within 10 % on {summ['depth_within_10pct']:,} (median ratio {summ['depth_ratio_median']:.2f}).\n"
             f"Spans measured on under 30 % of their own range: {summ['flagged_core_frac_lt_0.3']} before, "
             f"{summ['flagged_whole_frac_lt_0.3']} now; no event found in {summ['no_event_found']}. Every span is "
             f"measured as a drop; {summ['rise_dominated']} whose biggest, fastest movement is a rise are flagged.",
             fontsize=8.5, color=fs.INK_2)
    fig.savefig(os.path.join(out, "whole_drop_vs_steep_core.png"), dpi=170, bbox_inches="tight")
    plt.close(fig)
    with open(os.path.join(out, "whole_drop_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summ, f, indent=2, default=float)
    print(json.dumps(summ, indent=1, default=float))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT, help="output folder (default: %(default)s)")
    main(os.path.abspath(ap.parse_args().out))
