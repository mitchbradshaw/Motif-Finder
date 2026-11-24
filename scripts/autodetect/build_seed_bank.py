"""
build_seed_bank.py
==================
The auto-detect seed bank (2026-11-19): shape families rebuilt from the accepted catalogue's single events with
g-11's recipe, one medoid per family, each with its search durations and its match line.

In plain words
--------------
g-12, the latest Library grouping, groups the accepted catalogue by recording, not by shape, so it has no shape
medoids. This rebuilds a shape grouping of the same catalogue the way g-11 was built (shape distance, Ward, cut 0.6,
at least 10 members, omit beyond 0.5), on the single-event spans only: the 2,283 spans the 18 Nov Library analysis
found to hold one fall that the event-shape block measured correctly (multi-fall spans, hour-long regions and the
mis-measured 14 % are left out). Nothing is saved to the Library (researcher, 2026-11-19, Q6 (b)).

For each family:

* the **seed** is the medoid's own samples, in mV, at its own rate;
* the **search durations** are the 25th, 50th and 75th percentile of its members' durations;
* the **match line** ``min_corr`` is the correlation with the medoid that 90 % of the other members reach (each
  member and the medoid resampled to 256 points by bin means; Pearson correlation is what the search's
  z-normalised distance measures, `Working.autodetect.seeds`).

Inputs: ``docs/library_analysis/20261118/inventory_with_checks.csv`` (the 9 Nov catalogue with the 18 Nov checks)
and the channel files; the database is opened read-only for the recordings table. Writes only
``docs/autodetect/20261119/seed_bank/``.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/autodetect/build_seed_bank.py
"""

from __future__ import annotations

import collections
import json
import os
import sqlite3
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from webui.server.decimate import envelope  # noqa: E402  (numpy only: the Library's own waveform for grouping)
from Working.autodetect.seeds import correlation, to_length  # noqa: E402
from Working.library.grouping import engine as engine_mod  # noqa: E402
from Working.units import read_as_mv  # noqa: E402

INV = os.path.join(ROOT, "docs", "library_analysis", "20261118", "inventory_with_checks.csv")
DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite").replace("\\", "/")
OUT = os.path.join(ROOT, "docs", "autodetect", "20261119", "seed_bank")

UNIT, BASIS, METHOD = "single_motifs", "shape-distance", "ward"
PARAMS = {"cut": 0.6, "min_group": 10, "omit_d": 0.5}          # g-11's (make_events_grouping.py)
ENVELOPE_PX = 64                                               # the Library's grouping waveform
CORR_POINTS = 256
DURATION_QUANTILES = (0.25, 0.5, 0.75)
LINE_QUANTILE = 0.10                                           # 90 % of the members reach the line


def main():
    t0 = time.time()
    inv = pd.read_csv(INV)
    single = inv[(inv["status"] == "single") & (~inv["anatomy_suspect"].astype(bool)) & (inv["depth_mv"] > 0)]
    single = single.dropna(subset=["recording_id", "start_idx", "end_idx"]).reset_index(drop=True)
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    recs = {int(r[0]): {"npy": r[1], "fs": float(r[2]), "units": r[3], "file": r[4], "channel": int(r[5])}
            for r in conn.execute("SELECT id, npy_path, fs, units, source_file, channel FROM recordings")}
    arrays = {}

    def samples(rid):
        if rid not in arrays:
            arrays[rid] = np.load(os.path.join(ROOT, recs[rid]["npy"]), mmap_mode="r")
        return arrays[rid]

    items, rows = [], []
    for i, r in enumerate(single.itertuples(index=False)):
        rid, s, e = int(r.recording_id), int(r.start_idx), int(r.end_idx)
        rec = recs[rid]
        env = envelope(samples(rid), rec["fs"], s, e, ENVELOPE_PX)["v"]
        if not env or any(v is None for v in env):
            continue
        items.append({"member_ref": len(rows), "content_hash": None, "values": [float(v) for v in env],
                      "fs": rec["fs"], "recording_id": rid, "start_idx": s, "end_idx": e})
        rows.append({"event_id": r.event_id, "dataset": r.dataset, "recording_id": rid, "channel": rec["channel"],
                     "fs": rec["fs"], "start_idx": s, "end_idx": e, "duration_s": (e - s) / rec["fs"]})
    print(f"{len(single)} single events -> {len(items)} items", flush=True)

    result = engine_mod.run_grouping(items, unit=UNIT, basis=BASIS, method=METHOD, params=PARAMS)
    print(f"families {result.n_families}, assigned {result.n_assigned}, omitted {result.n_omitted} "
          f"{dict(result.omitted_by_reason)}  ({time.time() - t0:.0f} s)", flush=True)

    def mv(row):
        factor, _ = read_as_mv(recs[row["recording_id"]]["units"])
        return np.asarray(samples(row["recording_id"])[row["start_idx"]:row["end_idx"]], dtype=float) * factor

    os.makedirs(OUT, exist_ok=True)
    families, exemplars = [], {}
    for fam in result.families:
        med = rows[int(fam.medoid)]
        med_x = mv(med)
        med_z = to_length(med_x, CORR_POINTS)
        corrs, durs, datasets = [], [], collections.Counter()
        for ref in fam.members:
            m = rows[int(ref)]
            durs.append(m["duration_s"])
            datasets[m["dataset"]] += 1
            if int(ref) == int(fam.medoid):
                continue
            c = correlation(to_length(mv(m), CORR_POINTS), med_z)
            if np.isfinite(c):
                corrs.append(c)
        q = np.quantile(durs, DURATION_QUANTILES)
        line = float(np.quantile(corrs, LINE_QUANTILE)) if corrs else 0.9
        families.append({
            "label": fam.label, "n_members": len(fam.members),
            "durations_s": [round(float(v), 3) for v in q], "min_corr": round(line, 4),
            "member_corr_quantiles": {str(k): round(float(np.quantile(corrs, k)), 4) for k in (0.1, 0.5, 0.9)}
            if corrs else {},
            "datasets": dict(datasets.most_common()),
            "exemplar_fs": med["fs"], "exemplar_len": int(len(med_x)),
            "medoid": {k: med[k] for k in ("event_id", "dataset", "recording_id", "channel", "start_idx",
                                           "end_idx", "duration_s")},
        })
        exemplars[fam.label] = med_x
        print(f"  {fam.label}: {len(fam.members):4d} members  durations {np.round(q, 1).tolist()} s  "
              f"line r >= {line:.3f}  medoid {med['dataset']} rec {med['recording_id']}  {dict(datasets.most_common(3))}",
              flush=True)
    meta = {
        "built": time.strftime("%Y-%m-%dT%H:%M:%S"), "inventory": os.path.relpath(INV, ROOT).replace("\\", "/"),
        "rule": ("single-event spans (status single, anatomy check passed, depth > 0) of the 9 Nov accepted "
                 "catalogue; g-11's recipe: shape-distance Ward, cut 0.6, min_group 10, omit_d 0.5, on the "
                 "Library's 64-px envelope; seed = medoid's samples in mV; durations = member duration quartiles; "
                 "min_corr = 10th percentile of member-to-medoid Pearson r at 256 points"),
        "n_events": len(single), "n_items": len(items), "n_families": result.n_families,
        "n_assigned": result.n_assigned, "n_omitted": result.n_omitted,
        "omitted_by_reason": dict(result.omitted_by_reason), "families": families,
    }
    with open(os.path.join(OUT, "seed_bank.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1, default=str)
    np.savez_compressed(os.path.join(OUT, "seed_bank.npz"), **exemplars)
    print(f"wrote {OUT} ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
