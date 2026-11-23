"""What changed in the whole-drop rule after Auto-detect's checks (23 Nov, evening): the approved rule (commit 5e07deff)
against the revised one, on the cases that moved.

Read-only (database `mode=ro`, channels memory-mapped). The approved rule is loaded from git, so the comparison is
reproducible. Writes docs/library_analysis/20261123/revised/whole_drop_revision.png.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/library_analysis/fig_whole_drop_revision_20261123.py
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import types

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "thesis"))

import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from Working.interrogation import whole_drop as NOW  # noqa: E402

APPROVED_COMMIT = "5e07deff"
SPANS = os.path.join(ROOT, "docs", "thesis", "data", "accepted_catalogue_20261109", "accepted_spans.csv")
DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite").replace("\\", "/")
OUT = os.path.join(ROOT, "docs", "library_analysis", "20261123", "revised", "whole_drop_revision.png")
OLD, NEW = "#eb6834", "#2a78d6"

#: (caption, accepted span id prefix - or ("rec", recording id, start h, end h) for a window that is not a span)
CASES = [
    ("Auto-detect's check: a 50 mV decline you circled as one\ndrop came out in four; now one", ("rec", 49, 281.4, 283.0)),
    ("a slow decline running straight into a sharp drop, no pause\nbetween: the decline is its own event now (outside the span)",
     "accepted-4a863d57"),
    ("a drop's slow tail running into a second sharp drop:\nnow two (the second outside the span)", "accepted-873cd70d"),
    ("the same, over 40 minutes: the first drop and its\ntail end where the second drop starts", "accepted-d3ac70db"),
    ("a sharp drop the approved rule missed\n(its depth mostly ran on past the span)", "accepted-81caf9bb"),
    ("a 3 s fall recovering half-way 43 s later: measured now\n(the half-recovery search stopped after 10 fall times)",
     "accepted-d7b6ca60"),
    ("OPEN: a step on a slow drift - the tail now runs\nto the end of the drift (the drift was there before)", "accepted-99f61fa6"),
    ("OPEN: a sharp drop, then a decline for two hours -\nto the bottom of the tail is two hours later", "accepted-2a1dc6b4"),
    ("OPEN: a fall that eases to a fifth of its pace and\nplunges again - two drops by the rule, or one?", "accepted-082f06a6"),
]


def to_mv(units):
    return {"mV": 1.0, "uV": 0.001}.get(units or "V", 1000.0)


def approved_rule():
    """The rule the researcher approved on 23 Nov, loaded from its commit."""
    src = subprocess.check_output(["git", "show", f"{APPROVED_COMMIT}:Working/interrogation/whole_drop.py"], cwd=ROOT)
    mod = types.ModuleType("whole_drop_approved")
    exec(compile(src.decode("utf-8"), "whole_drop_approved.py", "exec"), mod.__dict__)
    return mod


def hm(i, fs_):
    t = i / fs_ / 3600.0
    return f"{int(t)}:{(t - int(t)) * 60:04.1f}"


def draw(ax, caption, case, spans, recs, v2):
    if isinstance(case, tuple):
        _, rid, h0, h1 = case
        rec = recs[rid]
        a, b = int(h0 * 3600 * rec["fs"]), int(h1 * 3600 * rec["fs"])
        where = f"M4 CH1 (recording {rid}), {hm(a, rec['fs'])}-{hm(b, rec['fs'])} h: Auto-detect's window"
    else:
        eid = next(e for e in spans.index if e.startswith(case))
        r = spans.loc[eid]
        rec = recs[int(r.recording_id)]
        a, b = int(r.start_idx), int(r.end_idx)
        where = f"{r.dataset} CH{int(r.channel)} · {rec['fs']:g} Hz · {eid[9:17]}"
    f = rec["fs"]
    x = np.load(os.path.join(ROOT, rec["npy"]), mmap_mode="r")
    old, new = (m.measure(x, a, b, f, to_mv=to_mv(rec["units"])) for m in (v2, NOW))
    marks = [a, b] + [e[k] for m in (old, new) for e in m.get("events", []) for k in ("top_idx", "bottom_idx")]
    pad = max(int(0.15 * (max(marks) - min(marks))), int(30 * f))
    lo, hi = max(0, min(marks) - pad), min(len(x), max(marks) + pad)
    y = np.asarray(x[lo:hi], dtype=float) * to_mv(rec["units"])
    scale = 3600.0 if (hi - lo) / f > 4 * 3600 else 60.0
    t = (np.arange(lo, hi) - a) / f / scale
    ax.axvspan(0, (b - a) / f / scale, color="#efeeea", lw=0, zorder=0)
    ax.plot(t, y, color=fs.INK_2, lw=0.7, zorder=2)
    for m, col, lw, alpha, z in ((old, OLD, 5.0, 0.45, 3), (new, NEW, 1.7, 0.95, 4)):
        for e in m.get("events", []):
            i, j = int(e["top_idx"]) - lo, int(e["bottom_idx"]) - lo
            if 0 <= i < len(y) and 0 <= j < len(y):
                ax.plot(t[i:j + 1], y[i:j + 1], color=col, lw=lw, alpha=alpha, zorder=z, solid_capstyle="round")
                if col == NEW:
                    ax.plot(t[i], y[i], "^", color=NEW, ms=6, zorder=5)
                    ax.plot(t[j], y[j], "v", color=NEW, ms=6, zorder=5)
        rec_i = m.get("recovery_idx", float("nan"))
        if np.isfinite(rec_i) and 0 <= int(rec_i) - lo < len(y):
            ax.plot(t[int(rec_i) - lo], y[int(rec_i) - lo], "x", color=col, ms=8, mew=2, zorder=6)

    def says(m):
        if not m.get("ok"):
            return "no drop found"
        ev = ", ".join(f"{e['depth_mv']:.3g}" for e in m["events"])
        w = f"width {m['width_s']:.0f} s" if np.isfinite(m["width_s"]) else "no half recovery"
        return f"{m['n_events']} event{'s' if m['n_events'] != 1 else ''}: {ev} mV; main event {w}"
    ax.set_title(f"{caption}\n{where}", loc="left", fontsize=8.0)
    ax.text(0.0, -0.24, f"approved rule: {says(old)}", transform=ax.transAxes, fontsize=7.6, color=OLD, va="top")
    ax.text(0.0, -0.34, f"revised rule: {says(new)}", transform=ax.transAxes, fontsize=7.6, color=NEW, va="top")
    ax.set_xlabel(f"{'h' if scale == 3600 else 'min'} from the window's start", fontsize=7.3, labelpad=1)
    ax.tick_params(labelsize=7)
    ax.grid(False)


def main():
    fs.apply()
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    recs = {int(r[0]): {"npy": r[1], "fs": float(r[2]), "units": r[3]}
            for r in conn.execute("SELECT id, npy_path, fs, units FROM recordings")}
    conn.close()
    spans = pd.read_csv(SPANS).set_index("event_id")
    v2 = approved_rule()
    fig, axes = plt.subplots(3, 3, figsize=(17.0, 13.5))
    for ax, (caption, case) in zip(axes.flat, CASES):
        draw(ax, caption, case, spans, recs, v2)
    fig.subplots_adjust(hspace=0.78, wspace=0.22)
    handles = [plt.Line2D([], [], color=OLD, lw=5, alpha=0.45, label=f"approved rule ({APPROVED_COMMIT})"),
               plt.Line2D([], [], color=NEW, lw=1.7, marker="^", ms=6, label="revised rule: each drop event, top ▲ to "
                                                                            "bottom ▼  (× half recovery)"),
               plt.Rectangle((0, 0), 1, 1, color="#efeeea", label="the accepted span (or the checked window)")]
    fig.legend(handles=handles, loc="lower center", ncol=3, fontsize=9, bbox_to_anchor=(0.5, 0.0))
    fig.text(0.01, 0.985, "The whole-drop rule after Auto-detect's checks. Separate drops stay separate even with no "
             "pause between them; a quiet channel's wiggles no longer cut a drop; a clear climb ends any drop; a span "
             "holds the drop whose steepest moment it holds.\nThe three OPEN panels are questions for you, not "
             "settled behaviour.", fontsize=9.5, color=fs.INK_2, va="top")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    main()
