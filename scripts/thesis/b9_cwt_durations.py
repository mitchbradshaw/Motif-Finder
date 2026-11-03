"""
b9_cwt_durations.py - B9: do CWT event durations cluster at preferred scales? Real spans against AAFT copies.

Runs the `cwt_events` template's detector (`detection.cwt_ridges`, polarity "drop", every other parameter at the
template's default) directly on the channel arrays - read-only, nothing is written to the database or the step cache.
Event shape and Intervals, the template's later blocks, measure events but never add or remove one, so the events
and their `best_scale_s` are the detector's.

The rule, fixed before any result was read (docs/rq_roundA_2/findings/b9-cwt-durations-2026-11-03.md, Protocol):
  * recordings: M2_aug (ids 1-16), M2_concat (33-48), CO_fs2 (641-644), LM_fs2 (637-640), MJu26a_fs2 (692-707);
  * every channel of the 4-channel recordings, the even channels (0, 2, ..., 14) of the 16-channel ones; 24 h spans starting at 20 %, 50 % and 80 % of (length - 24 h), rounded to a whole sample;
  * a span more than 10 % NaN is skipped (counted);
  * null: AAFT copies of the same span (Adapters.preprocessing_surrogate.aaft_surrogate), one draw per span (--draws), seeds
    fixed, plus one phase-randomised draw ("pr", the W1 evaluation's null) for comparison; NaN samples are linearly bridged for the surrogate only and set back to NaN after it, so the copy has the
    real span's gaps;
  * an event is "clean" unless it carries edge_flag or step_pair (the template test's own reading); both counts kept.

Writes docs/thesis/data/ch10_b9/{events.csv, spans.csv}.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/thesis/b9_cwt_durations.py [--draws 2]
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from Adapters.preprocessing_surrogate import _phase_randomise, aaft_surrogate  # noqa: E402
from Working.Detection import cwt_ridges as CR  # noqa: E402

DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite").replace("\\", "/")
OUT = os.path.join(ROOT, "docs", "thesis", "data", "ch10_b9")
FILES = {"M2_aug_concat_fs1.mat": "M2_aug", "M2_concat_fs1.mat": "M2_concat", "CO_fs2.mat": "CO_fs2",
         "LM_fs2.mat": "LM_fs2", "MJu26a_fs2.mat": "MJu26a_fs2"}
FRACS = (0.2, 0.5, 0.8)
BIG = ("M2_aug_concat_fs1.mat", "M2_concat_fs1.mat", "MJu26a_fs2.mat")
SPAN_H = 24.0
MAX_NAN = 0.10
COLS = ("best_scale_s", "duration_s", "snr", "edge_flag", "step_pair", "nan_in_support", "peak_idx")


def detect(x, fs):
    r = CR.detect(x, fs, polarity="drop")     # the template's only non-default parameter
    return [{k: e[k] for k in COLS} for e in r.events]


def surrogate(x, seed, method="aaft"):
    bad = ~np.isfinite(x)
    xf = x.copy()
    if bad.any():
        idx = np.arange(len(x))
        xf[bad] = np.interp(idx[bad], idx[~bad], x[~bad])
    rng = np.random.default_rng(seed)
    s = aaft_surrogate(xf, rng) if method == "aaft" else _phase_randomise(xf, rng)
    s[bad] = np.nan
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=1)
    ap.add_argument("--fracs", default="0.5", help="span starts as fractions of (length - 24 h), comma-separated")
    ap.add_argument("--ch-step", type=int, default=4, help="16-channel recordings: channels 0, ch_step, ...")
    ap.add_argument("--limit", type=int, default=0, help="stop after this many spans (timing)")
    a = ap.parse_args()
    fracs = tuple(float(f) for f in a.fracs.split(","))
    os.makedirs(OUT, exist_ok=True)
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    recs = c.execute("SELECT id, source_file, channel, fs, n_samples, npy_path FROM recordings WHERE source_file IN "
                     f"({','.join('?' * len(FILES))}) ORDER BY id", tuple(FILES)).fetchall()
    c.close()
    ev_rows, span_rows = [], []
    n_done = 0
    t_all = time.time()
    for rid, sf, ch, fs, n, npy in recs:
        assert "M4_aug" not in sf and "Schizophyllum" not in sf
        arr = np.load(os.path.join(ROOT, npy), mmap_mode="r")
        if sf in BIG and ch % a.ch_step:  # 16-channel recordings: every ch_step-th channel only (time budget)
            continue
        L = int(round(SPAN_H * 3600 * fs))
        for frac in fracs:
            s0 = int(round(frac * (n - L)))
            x = np.asarray(arr[s0:s0 + L], dtype=float)
            nan_frac = float((~np.isfinite(x)).mean())
            row = {"recording": FILES[sf], "recording_id": rid, "channel": ch, "fs": fs, "start_idx": s0,
                   "end_idx": s0 + L, "nan_frac": nan_frac}
            if nan_frac > MAX_NAN or np.nanstd(x) == 0:
                row["skipped"] = True
                span_rows.append(row)
                continue
            row["skipped"] = False
            for kind, draw in [("real", -1)] + [("aaft", d) for d in range(a.draws)] + [("pr", 0)]:
                t0 = time.time()
                xx = x if kind == "real" else surrogate(x, seed=1000 * rid + int(100 * frac) + draw,
                                                        method="aaft" if kind == "aaft" else "phase")
                evs = detect(xx, fs)
                dt = time.time() - t0
                clean = sum(1 for e in evs if not (e["edge_flag"] or e["step_pair"]))
                row[f"n_{kind}{'' if draw < 0 else draw}"] = len(evs)
                row[f"clean_{kind}{'' if draw < 0 else draw}"] = clean
                row[f"sec_{kind}{'' if draw < 0 else draw}"] = round(dt, 2)
                for e in evs:
                    ev_rows.append({"recording": FILES[sf], "recording_id": rid, "channel": ch, "start_idx": s0,
                                    "kind": kind, "draw": draw, **e})
            span_rows.append(row)
            n_done += 1
            print(f"{FILES[sf]} rec {rid} @{frac}: real {row['n_real']} (clean {row['clean_real']}), aaft "
                  f"{[row.get(f'n_aaft{d}') for d in range(a.draws)]}, pr {row['n_pr0']}  {time.time() - t_all:.0f}s", flush=True)
            if a.limit and n_done >= a.limit:
                break
        if a.limit and n_done >= a.limit:
            break
        pd.DataFrame(ev_rows).to_csv(os.path.join(OUT, "events.csv"), index=False)
        pd.DataFrame(span_rows).to_csv(os.path.join(OUT, "spans.csv"), index=False)
    pd.DataFrame(ev_rows).to_csv(os.path.join(OUT, "events.csv"), index=False)
    pd.DataFrame(span_rows).to_csv(os.path.join(OUT, "spans.csv"), index=False)
    print(f"done: {n_done} spans in {time.time() - t_all:.0f} s")


if __name__ == "__main__":
    main()
