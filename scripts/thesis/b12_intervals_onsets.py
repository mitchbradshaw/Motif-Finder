"""
b12_intervals_onsets.py - B12's interval half re-read on the drop detector's true fall onsets (9 Nov), read-only.

B12 (3 Nov) and its 5 Nov species re-run compared each channel's LV and CV2 between recordings, species and strains.
Like B1, they took each event's time as its detection's start, which for ``drop_detection_v1`` is the start of the
window the detector framed (on the encoder's 98.33 s grid, typically ~10 min before the fall), not the fall itself.
This script keeps B12's own 45 channels (the runs listed in its 3 Nov ``intervals_by_channel.csv``), replaces only the
event times with the onsets ``b1_onsets.py`` recomputed and checked against the database, and repeats both sets of
tests with their own code (``b12_shapes_intervals.interval_tests`` and ``species_rerun_b6_b12.rerun_b12_intervals``).
The window-start versions are kept beside them, suffixed ``_windowstarts``.

Writes docs/thesis/data/ch10_b12/{intervals_by_channel, interval_tests, interval_tests_5nov}.csv (onsets) and their
``_windowstarts`` copies (first run only). Shapes are untouched.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/thesis/b12_intervals_onsets.py
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))

import b1_intervals as b1  # noqa: E402
import b12_shapes_intervals as b12  # noqa: E402
import species_rerun_b6_b12 as sr  # noqa: E402

D12 = b12.OUT


def keep_windowstarts(name):
    """Copy the window-start version of a B12 output aside once, and return the copy's path."""
    src = os.path.join(D12, f"{name}.csv")
    dst = os.path.join(D12, f"{name}_windowstarts.csv")
    if not os.path.exists(dst):
        shutil.copyfile(src, dst)
    return dst


def intervals_on_onsets(c, old):
    from Working.interrogation.intervals import interval_nulls
    rows = []
    for _, r in old.iterrows():
        on = b1.event_times(c, r.run, r.fs, "onset")
        nl = interval_nulls(on, resolution_s=1.0 / float(r.fs))
        po, sh = nl.get("poisson") or {}, nl.get("shuffle") or {}
        row = {k: r[k] for k in ("run", "recording_id", "dataset", "species", "channel", "fs", "complete", "hours")}
        row.update({"event_time": "onset", "n_events": nl["n_events"],
                    "lv": (po.get("lv") or {}).get("observed"), "cv2": (po.get("cv2") or {}).get("observed"),
                    "lv_poisson_lo": (po.get("lv") or {}).get("lo"), "lv_poisson_hi": (po.get("lv") or {}).get("hi"),
                    "lv_p_poisson": (po.get("lv") or {}).get("p"), "lv_p_shuffled": (sh.get("lv") or {}).get("p"),
                    "lv_shuffled_mean": (sh.get("lv") or {}).get("null_mean"),
                    "cv2_p_poisson": (po.get("cv2") or {}).get("p"), "caveat": nl.get("caveat") or nl.get("note")})
        if row["n_events"] != r["n_events"]:
            raise ValueError(f"run {r.run}: {row['n_events']} onsets for {r['n_events']} detections")
        rows.append(row)
    return pd.DataFrame(rows)


def plot_intervals(iv):
    """B12's diagnostic interval panel (b12_intervals_lv_cv2.png), redrawn from the onset intervals."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    dorder = [o for o in ["M2_aug", "CO_fs2", "M2_concat", "LM_fs2", "L_LM_fs2"] if o in set(iv["dataset"])]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    for ax, f in zip(axes, ("lv", "cv2")):
        for i, o in enumerate(dorder):
            v = iv.loc[iv.dataset == o, f].dropna().to_numpy()
            ax.scatter(np.full(v.size, i) + np.random.default_rng(i).normal(0, 0.06, v.size), v, s=14, color=f"C{i}")
        ax.axhline(1.0, color="grey", lw=0.8, ls="--")
        ax.set_xticks(range(len(dorder)))
        ax.set_xticklabels(dorder, fontsize=8)
        ax.set_ylabel(f"{f.upper()} per channel (drop_detection_v1, fall onsets)")
    fig.suptitle("B12: interval irregularity per channel, timed from fall onsets; dashed = Poisson expectation")
    fig.tight_layout()
    fig.savefig(os.path.join(D12, "b12_intervals_lv_cv2.png"), dpi=120)
    plt.close(fig)


def main():
    old = pd.read_csv(keep_windowstarts("intervals_by_channel"))
    keep_windowstarts("interval_tests")
    keep_windowstarts("interval_tests_5nov")
    db = os.path.join(ROOT, "DATA", "db", "annotations.sqlite").replace("\\", "/")
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    iv = intervals_on_onsets(c, old)
    c.close()
    iv.to_csv(os.path.join(D12, "intervals_by_channel.csv"), index=False)
    plot_intervals(iv)
    it = b12.interval_tests(iv)
    it.to_csv(os.path.join(D12, "interval_tests.csv"), index=False)
    it5 = sr.rerun_b12_intervals()                 # reads the onset intervals_by_channel.csv just written
    pd.set_option("display.width", 220)
    both = old[["run", "dataset", "channel", "n_events", "lv", "cv2"]].merge(
        iv[["run", "lv", "cv2"]], on="run", suffixes=("_windowstart", "_onset"))
    print(both.to_string(index=False))
    print(iv.groupby("dataset")[["lv", "cv2"]].median())
    for name, new in (("interval_tests", it), ("interval_tests_5nov", it5)):
        was = pd.read_csv(os.path.join(D12, f"{name}_windowstarts.csv"))
        cmp_ = was[["level", "feature", "p"]].merge(new[["level", "feature", "p", "eps2", "bh_pass_05"]],
                                                    on=["level", "feature"], suffixes=("_windowstart", "_onset"))
        print(name)
        print(cmp_.to_string(index=False))


if __name__ == "__main__":
    main()
