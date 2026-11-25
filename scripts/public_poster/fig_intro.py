"""Public poster: the anatomy of one drop (a real oyster drop, M2_aug, from the 24 Nov pool).

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/public_poster/fig_intro.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import style as S  # noqa: E402
import seqdata as Q  # noqa: E402
from matplotlib.patches import FancyArrowPatch  # noqa: E402

EVENT = "pool-4-3130"


def anatomy(w_mm=186, h_mm=82):
    S.apply(base=15)
    ev = pd.read_parquet(os.path.join(S.DATA, "drops.parquet"))
    r = ev[ev["event_id"] == EVENT].iloc[0]
    fs = float(r.fs)
    a, b = int(r.top_idx - 150 * fs), int(r.top_idx + 330 * fs)
    idx, y = Q.trace(int(r.recording_id), a, b)
    t = (idx - r.top_idx) / fs
    y = y - y[np.searchsorted(idx, r.top_idx)]
    fig = S.figure(w_mm, h_mm)
    ax = fig.add_axes([0.03, 0.2, 0.94, 0.72])
    ax.plot(t, y, color=S.INK, lw=2.4, zorder=2)
    tb = (r.bottom_idx - r.top_idx) / fs
    m = (t >= 0) & (t <= tb)
    ax.plot(t[m], y[m], color=S.HOT, lw=5, zorder=3, solid_capstyle="round")
    yb = float(np.min(y[m]))
    half = yb / 2
    after = (t > tb) & (y >= half)
    t_half = float(t[after][0]) if after.any() else tb + r.recovery_s
    m2 = (t >= tb) & (t <= t_half)
    ax.plot(t[m2], y[m2], color=S.MAGENTA, lw=5, zorder=3, solid_capstyle="round")
    # depth, left of the drop
    xd = -22
    ax.add_patch(FancyArrowPatch((xd, 0), (xd, yb), arrowstyle="<|-|>", mutation_scale=22, lw=2.6,
                                 color=S.PURPLE, zorder=4))
    ax.plot([xd - 6, tb], [yb, yb], color=S.PURPLE, lw=1.3, ls=(0, (4, 3)), zorder=1)
    ax.text(xd - 9, yb * 0.52, f"Depth\n{abs(yb):.0f} mV", color=S.PURPLE, fontsize=17, fontweight="bold",
            ha="right", va="center")
    # fall, inside the V
    ax.text(16, yb * 0.16, f"Fall: {tb:.0f} s", color=S.HOT, fontsize=17, fontweight="bold", ha="left",
            va="center")
    # climb back, under the recovery
    ax.text(t_half + 10, half - 1.2, f"Half recovery:\n{t_half - tb:.0f} s", color=S.MAGENTA,
            fontsize=17, fontweight="bold", va="top")
    for s_ in ("left", "top", "right"):
        ax.spines[s_].set_visible(False)
    ax.set_yticks([])
    ax.set_xlim(-150, 330)
    ax.set_ylim(yb * 1.15, 1.6)
    ax.set_xticks([-120, -60, 0, 60, 120, 180, 240, 300])
    ax.set_xlabel("Time (s)")
    x0 = -145
    ax.plot([x0, x0], [yb, yb + 5], color=S.INK_2, lw=4, solid_capstyle="butt")
    ax.text(x0 + 6, yb + 2.5, "5 mV", fontsize=14, fontweight="bold", color=S.INK_2, va="center")
    S.save(fig, "intro_anatomy")
    return {"event": EVENT, "dataset": r.dataset, "depth_mv": float(abs(yb)), "fall_s": tb,
            "half_back_s": t_half - tb}


if __name__ == "__main__":
    print(anatomy())
