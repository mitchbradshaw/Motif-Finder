"""The three open questions about where a whole drop ENDS (README 20261123 section 1b), each on two accepted spans,
with roughly where each option would end the drop.

The questions were put on the rule committed as c2c5f1e2, and the PNG kept in revised/ was drawn on it. The researcher
chose Q1 (b), Q2 (a) with long tails flagged, and Q3 (a) (23 Nov); redrawn on the rule after that, the solid line on
the Q1 row is the step alone. The lettered marks are illustrations of the options, computed here with simple
stand-ins, not rules in the code:

  Q1 (b)  the step alone: from the step's own top (the highest point in the 2 minutes before its steepest moment) to
          the first moment its 2-minute pace is no more than 1.5 x the slide's pace over the 10 minutes before the step
     (c)  the step alone, to a fixed fraction: from the same top to the first moment its 1-minute pace falls
          under 5 % of its steepest 10-second pace
  Q2 (b)  where the tail stops slowing down: the first 5-minute window after the steepest point falling at least 80 %
          as fast as the window before it (the tail has turned into a steady slide)
     (c)  a cap: ten times the steep part's length after the top (steep part: while the 10-second pace stays above a
          fifth of its steepest)
  Q3      two drops (now) or one (the approved rule's answer)

Read-only (database `mode=ro`, channels memory-mapped). Writes docs/library_analysis/20261123/revised/
whole_drop_open_questions.png.

    PYTHONIOENCODING=utf-8 "$PY" scripts/library_analysis/fig_whole_drop_open_questions_20261123.py   (PY: conda python)
"""
from __future__ import annotations

import os
import sqlite3
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "thesis"))

import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from Working.interrogation import whole_drop as WD  # noqa: E402

SPANS = os.path.join(ROOT, "docs", "thesis", "data", "accepted_catalogue_20261109", "accepted_spans.csv")
DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite").replace("\\", "/")
OUT = os.path.join(ROOT, "docs", "library_analysis", "20261123", "revised", "whole_drop_open_questions.png")
NOW, OPT_B, OPT_C, ONE = "#2a78d6", "#1a9e5c", "#b8459c", "#eb6834"

ROWS = [
    ("Q1  A step on a slow slide that was already there. Does the drop end where the slide began again, or at the "
     "bottom of the slide?", "q1", ["accepted-99f61fa6", "accepted-725bbdbe"]),
    ("Q2  A sharp drop, then a decline that runs on for an hour or two (nothing was sliding before). Where does the "
     "drop end?", "q2", ["accepted-2a1dc6b4", "accepted-8d1f50aa"]),
    ("Q3  A fall that eases off, then plunges again. One drop, or two?", "q3",
     ["accepted-082f06a6", "accepted-337b9475"]),
]


def to_mv(units):
    return {"mV": 1.0, "uV": 0.001}.get(units or "V", 1000.0)


def pace(y, t, w):
    """Net fall per sample over the w samples ending at t (positive = falling)."""
    return (y[t - w] - y[t]) / w if t - w >= 0 else np.nan


def arrival(y, t0, t1):
    """Where the trace first reaches the lowest level of [t0, t1] (within a hair), as an index."""
    seg = y[t0:t1 + 1]
    return t0 + int(np.argmax(seg <= seg.min() + 0.02 * (y[t0] - seg.min() + 1e-9)))


def options(y, f, top, bottom, kind):
    """{letter: end index} for the question's options, on the smoothed copy y (read frame)."""
    s10, m1, m2, m5 = max(1, int(10 * f)), max(1, int(60 * f)), max(1, int(120 * f)), max(1, int(300 * f))
    p10 = np.array([pace(y, t, s10) for t in range(top + s10, bottom + 1)])
    steep_at = top + s10 + int(np.nanargmax(p10))
    steepest = np.nanmax(p10)
    out = {}
    if kind == "q1":
        # the step's own top: the highest point in the 2 minutes before its steepest moment; the slide's pace: the 10
        # minutes before that (the rule may have merged some of the slide in as the step's shoulder)
        s0 = max(0, steep_at - m2)
        step_top = s0 + int(np.argmax(y[s0:steep_at + 1]))
        w0 = max(0, step_top - int(600 * f))
        pre = max((y[w0] - y[step_top]) / max(1, step_top - w0), 0.0)
        for t in range(steep_at + m2, bottom + 1):
            if pace(y, t, m2) <= 1.5 * pre:
                out["b"] = arrival(y, step_top, t)
                out["b_top"] = step_top
                break
        for t in range(steep_at + m1, bottom + 1):
            if pace(y, t, m1) <= 0.05 * steepest:
                out["c"] = arrival(y, step_top, t)
                out["c_top"] = step_top
                break
    elif kind == "q2":
        prev = None
        for t in range(steep_at + m5, bottom + 1, m5):
            p = pace(y, t, m5)
            if prev is not None and p >= 0.8 * prev:
                out["b"] = arrival(y, top, t - m5)
                break
            prev = p
        steep_end = steep_at
        while steep_end + 1 <= bottom and pace(y, steep_end + 1, s10) >= steepest / 5.0:
            steep_end += 1
        out["c"] = arrival(y, top, min(bottom, top + 10 * (steep_end - top)))
    return out


def draw(ax, eid, kind, spans, recs):
    r = spans.loc[next(e for e in spans.index if e.startswith(eid))]
    rec = recs[int(r.recording_id)]
    f, k = rec["fs"], to_mv(rec["units"])
    x = np.load(os.path.join(ROOT, rec["npy"]), mmap_mode="r")
    a, b = int(r.start_idx), int(r.end_idx)
    m = WD.measure(x, a, b, f, to_mv=k)
    ev = m["events"]
    marks = [a, b] + [e[q] for e in ev for q in ("top_idx", "bottom_idx")]
    pad = max(int(0.12 * (max(marks) - min(marks))), int(60 * f))
    lo, hi = max(0, min(marks) - pad), min(len(x), max(marks) + pad)
    raw = np.asarray(x[lo:hi], dtype=float) * k
    y = WD.smoothed(raw, f)
    t = (np.arange(lo, hi) - a) / f / 60.0
    ax.axvspan(0, (b - a) / f / 60.0, color="#efeeea", lw=0, zorder=0)
    ax.plot(t, raw, color=fs.INK_2, lw=0.6, zorder=2)
    lines = []
    for n, e in enumerate(ev, start=1):
        i, j = e["top_idx"] - lo, e["bottom_idx"] - lo
        ax.plot(t[i:j + 1], raw[i:j + 1], color=NOW, lw=2.0, zorder=4)
        ax.plot(t[i], raw[i], "^", color=NOW, ms=7, zorder=5)
        ax.plot(t[j], raw[j], "v", color=NOW, ms=7, zorder=5)
        if len(ev) > 1:
            ax.annotate(str(n), (t[i], raw[i]), textcoords="offset points", xytext=(5, 4), color=NOW, fontsize=9,
                        fontweight="bold")
    main = max(ev, key=lambda e: e["depth_mv"])
    top, bottom = main["top_idx"] - lo, main["bottom_idx"] - lo
    if kind in ("q1", "q2"):
        dur = (bottom - top) / f / 60.0
        lines.append((NOW, f"(a) now - to the bottom of the tail: {main['depth_mv']:.3g} mV over {dur:.0f} min"))
        names = {"q1": {"b": "the step alone: from its top until the trace is back to the slide's pace",
                        "c": "the step alone, until its pace falls under 5 % of its steepest"},
                 "q2": {"b": "where the tail stops slowing down", "c": "capped at 10 x the steep part"}}[kind]
        opts = options(y, f, top, bottom, kind)
        for letter, col in (("b", OPT_B), ("c", OPT_C)):
            end = opts.get(letter)
            if end is None:
                lines.append((col, f"({letter}) {names[letter]}: no earlier end - same as (a)"))
                continue
            start = opts.get(f"{letter}_top", top)
            depth = float(raw[start] - raw[end])
            ax.axvline(t[end], color=col, lw=1.3, ls="--", zorder=3)
            ax.plot(t[end], raw[end], "v", color=col, ms=9, zorder=6)
            if start != top:
                ax.plot(t[start], raw[start], "^", color=col, ms=9, zorder=6)
            ax.annotate(letter, (t[end], raw[end]), textcoords="offset points", xytext=(4, -14), color=col,
                        fontsize=10, fontweight="bold")
            lines.append((col, f"({letter}) {names[letter]}: {depth:.3g} mV over {(end - start) / f / 60.0:.0f} min"))
    else:
        first, last = min(ev, key=lambda e: e["top_idx"]), max(ev, key=lambda e: e["bottom_idx"])
        i, j = first["top_idx"] - lo, last["bottom_idx"] - lo
        ax.plot([t[i], t[j]], [raw[i] + 0.0, raw[j]], color=ONE, lw=1.4, ls="--", zorder=3)
        parts = " + ".join(f"{e['depth_mv']:.3g}" for e in sorted(ev, key=lambda e: e["top_idx"]))
        lines.append((NOW, f"(a) now - two drops: {parts} mV"))
        lines.append((ONE, f"(b) one drop, top to bottom (dashed): {float(raw[i] - raw[j]):.3g} mV"))
    for n, (col, text) in enumerate(lines):
        ax.text(0.0, -0.17 - 0.085 * n, text, transform=ax.transAxes, fontsize=8.2, color=col, va="top")
    ax.set_title(f"{r.dataset} CH{int(r.channel)} · {f:g} Hz · {r.name[9:17]}", loc="left", fontsize=8.6)
    ax.set_xlabel("min from the accepted span's start (shaded)", fontsize=7.6, labelpad=1)
    ax.tick_params(labelsize=7.2)
    ax.grid(False)


def main():
    fs.apply()
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    recs = {int(r[0]): {"npy": r[1], "fs": float(r[2]), "units": r[3]}
            for r in conn.execute("SELECT id, npy_path, fs, units FROM recordings")}
    conn.close()
    spans = pd.read_csv(SPANS).set_index("event_id")
    fig = plt.figure(figsize=(16.5, 19.0))
    outer = fig.add_gridspec(3, 1, hspace=0.95)
    for row, (question, kind, ids) in enumerate(ROWS):
        inner = outer[row].subgridspec(1, 2, wspace=0.16)
        for col, eid in enumerate(ids):
            ax = fig.add_subplot(inner[0, col])
            draw(ax, eid, kind, spans, recs)
            if col == 0:
                ax.text(0.0, 1.16, question, transform=ax.transAxes, fontsize=11, fontweight="bold", va="bottom",
                        color=fs.INK)
    fig.text(0.01, 0.995, "Where does a drop end when nothing stops it cleanly? Solid blue: the rule as committed. "
             "Dashed marks: roughly where each option would end it (illustrations, not rules).", fontsize=10,
             color=fs.INK_2, va="top")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    main()
