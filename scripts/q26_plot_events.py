"""Plot a few id001 and id024 sharkfins with the trough, plateau and rise marked.

The judgement the numbers cannot make: is the slow climb after a sharkfin's trough a RECOVERY, or
is it slow baseline drift? `scripts/q26_sharkfin_recovery.py` measured it on the undetrended channel
on purpose -- the detrend window is shorter than the recovery on these two families -- so the climb
it measured could be either. These plates put the two side by side so it can be eyeballed.

Two figures per family:

  q26-<family>-events.png   per event: the raw trace from the onset to the NEXT onset, with the
                            detector's onset and trough, the plateau, the rise the detector
                            attributes to the NEXT event, where half recovery is reached, and
                            -- shaded -- the extent of the STORED SNIPPET, which is where
                            `recovery_time_s` stopped looking.
  q26-<family>-detrend.png  the same events, raw against the stored detrend window's rolling-mean
                            high pass, so the part of the climb detrending removes is visible.

Events are chosen BEFORE looking: the first, middle and last of each family in time order.

READ-ONLY on the data (database `mode=ro`, channels `mmap_mode='r'`). matplotlib only -- the one
drawing library the core keeps (CLAUDE.md rule 1). Writes to webui/screenshots/fixup/Q26/.
"""
import os
import sqlite3
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from Working.Detection.drop_motifs import store as S  # noqa: E402
from Working.Detection.drop_motifs.detect import detrend  # noqa: E402

SEED = os.path.join(ROOT, "DATA", "library_seed", "drop_motifs5", "motifs")
DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite")
OUT = os.path.join(ROOT, "webui", "screenshots", "fixup", "Q26")
FAMILIES = ("id001", "id024")
UNIT_FACTOR = {"V": 1000.0, "mV": 1.0}

C_TRACE = "#1f3b73"
C_FALL = "#c0392b"
C_PLATEAU = "#d9b166"
C_RISE = "#2e8b57"
C_STORED = "#9aa7bd"


def channel_for(rid):
    con = sqlite3.connect(f"file:{DB.replace(os.sep, '/')}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    r = con.execute("SELECT npy_path, units, fs FROM recordings WHERE id=?", (int(rid),)).fetchone()
    con.close()
    if r is None:
        return None
    path = os.path.join(ROOT, r["npy_path"].replace("/", os.sep))
    if not os.path.exists(path):
        return None
    return np.load(path, mmap_mode="r"), UNIT_FACTOR.get(r["units"], 1.0), float(r["fs"])


def pick(evs):
    """First, middle and last in time order -- chosen before looking at any of them."""
    if len(evs) <= 3:
        return list(range(len(evs)))
    return [0, len(evs) // 2, len(evs) - 1]


def panel(ax, e, nxt, arr, factor, fs, *, show_detrend=False):
    on, tr = int(e["onset_idx"]), int(e["trough_idx"])
    s0, s1 = int(e["snippet_start_idx"]), int(e["snippet_end_idx"])
    width = max(tr - on, 1)
    lead = int(2 * width)
    end = int(nxt["onset_idx"]) if nxt is not None else min(len(arr), tr + 20 * width)
    lo = max(0, on - lead)
    hi = int(min(len(arr), end + max(width, int(30 * fs))))
    t = (np.arange(lo, hi) - on) / fs
    v = np.asarray(arr[lo:hi], dtype=float) * factor

    if show_detrend:
        win = float(e.get("detrend_window_s") or 0) * fs
        d = detrend(v, win) if win >= 3 else v - v.mean()
        ax.plot(t, v - np.median(v), color=C_TRACE, lw=1.1, label="raw (median-centred)")
        ax.plot(t, d, color=C_FALL, lw=1.1, alpha=0.85,
                label=f"detrended, window {float(e.get('detrend_window_s') or 0):.0f} s")
        ax.axhline(0, color="#aaaaaa", lw=0.6, zorder=0)
        ax.legend(fontsize=6, loc="lower right", framealpha=0.9)
        ax.set_title(f"{e['event_id']} — the climb, and what detrending removes of it",
                     fontsize=7.5, loc="left")
        return

    v_on, v_tr = float(arr[on]) * factor, float(arr[tr]) * factor
    depth = v_on - v_tr
    half = v_tr + 0.5 * depth

    # the stored snippet: where recovery_time_s stopped looking
    ax.axvspan((s0 - on) / fs, (s1 - on) / fs, color=C_STORED, alpha=0.18, lw=0, zorder=0)
    ax.axvline((s1 - on) / fs, color=C_STORED, lw=1.0, ls=(0, (4, 2)), zorder=1)

    # the rise the detector hands to the NEXT event as its precursor
    if nxt is not None:
        u0, u1 = int(nxt.get("up_region_start_idx", -1)), int(nxt.get("up_region_end_idx", -1))
        if u0 >= 0 and u1 > u0:
            ax.axvspan((u0 - on) / fs, (u1 - on) / fs, color=C_RISE, alpha=0.16, lw=0, zorder=0)
            ax.axvspan((tr - on) / fs, (u0 - on) / fs, color=C_PLATEAU, alpha=0.20, lw=0, zorder=0)

    ax.plot(t, v, color=C_TRACE, lw=1.0, zorder=3)
    seg = slice(max(0, on - lo), max(0, tr - lo) + 1)
    ax.plot(t[seg], v[seg], color=C_FALL, lw=2.0, zorder=4)

    ax.axhline(v_on, color="#888888", lw=0.7, ls=(0, (5, 3)), zorder=2)
    ax.axhline(half, color="#2e8b57", lw=0.8, ls=(0, (2, 2)), zorder=2)
    ax.plot([0], [v_on], marker="v", ms=6, color=C_FALL, zorder=5)
    ax.plot([(tr - on) / fs], [v_tr], marker="o", ms=5, color=C_FALL, zorder=5)
    if nxt is not None:
        no = (int(nxt["onset_idx"]) - on) / fs
        ax.plot([no], [float(arr[int(nxt['onset_idx'])]) * factor], marker="v", ms=6,
                color="#555555", zorder=5)
        ax.annotate("next onset", ((no), float(arr[int(nxt['onset_idx'])]) * factor),
                    textcoords="offset points", xytext=(-4, 7), fontsize=6, ha="right", color="#555555")

    # where half recovery is first reached, searched to the next onset
    tail = np.asarray(arr[tr:end], dtype=float) * factor if end > tr else np.array([])
    reach = np.flatnonzero(tail >= half)
    hit = None if reach.size == 0 else (tr + int(reach[0]))
    if hit is not None:
        ax.plot([(hit - on) / fs], [half], marker="*", ms=11, color="#2e8b57", zorder=6)
        ax.annotate(f"half recovery  {(hit - tr) / fs:.0f} s after the trough",
                    ((hit - on) / fs, half), textcoords="offset points", xytext=(6, 6),
                    fontsize=6.5, color="#1e6b42")
    ax.annotate(f"stored snippet ends  {(s1 - on) / fs:.0f} s",
                ((s1 - on) / fs, ax.get_ylim()[0]), textcoords="offset points", xytext=(4, 10),
                fontsize=6.5, color="#5b6b7a")

    tag = "reaches half" if hit is not None else "does NOT reach half before the next onset"
    ax.set_title(f"{e['event_id']} — fall {width / fs:.0f} s, depth {depth:.1f} mV — {tag}",
                 fontsize=7.5, loc="left")
    ax.set_ylabel("mV", fontsize=7)


def figure(family, evs, arr, factor, fs, *, detrend_view, dest):
    chosen = pick(evs)
    n = len(chosen)
    fig, axes = plt.subplots(n, 1, figsize=(9.5, 2.5 * n), constrained_layout=True)
    axes = np.atleast_1d(axes)
    for ax, i in zip(axes, chosen):
        e = evs[i]
        nxt = evs[i + 1] if i + 1 < len(evs) else None
        panel(ax, e, nxt, arr, factor, fs, show_detrend=detrend_view)
        ax.tick_params(labelsize=6.5)
        ax.grid(alpha=0.12, lw=0.5)
    axes[-1].set_xlabel("seconds from the detector's onset", fontsize=7)
    if detrend_view:
        sub = ("raw against the stored detrend window. Where the window is shorter than the climb, "
               "detrending subtracts part of the recovery.")
    else:
        sub = ("red = the detector's fall (onset ▼ to trough ●).  gold = the plateau.  "
               "green = the rise the detector gives the NEXT event as its precursor.\n"
               "grey band = the STORED SNIPPET, which is where recovery_time_s stopped looking.  "
               "★ = half recovery, searched to the next onset.")
    fig.suptitle(f"{family} ({evs[0].get('morphology')}) — "
                 f"{'what detrending removes' if detrend_view else 'the trough, the plateau and the rise'}"
                 f"\n{sub}", fontsize=8, ha="left", x=0.01)
    fig.savefig(dest, dpi=150)
    plt.close(fig)
    print("wrote", os.path.relpath(dest, ROOT))


def main():
    events = S.load_events(SEED)
    os.makedirs(OUT, exist_ok=True)
    for family in FAMILIES:
        evs = sorted([e for e in events if e["span_key"] == family], key=lambda e: float(e["onset_h"]))
        if not evs:
            print("no events for", family)
            continue
        ch = channel_for(int(evs[0]["recording_id"]))
        if ch is None:
            print("no channel for", family)
            continue
        arr, factor, fs = ch
        figure(family, evs, arr, factor, fs, detrend_view=False,
               dest=os.path.join(OUT, f"q26-{family}-events.png"))
        figure(family, evs, arr, factor, fs, detrend_view=True,
               dest=os.path.join(OUT, f"q26-{family}-detrend.png"))


if __name__ == "__main__":
    main()
