"""Public poster: every number the poster's text quotes, written to data/numbers.json (the poster's ledger).

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/public_poster/ledger.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import style as S  # noqa: E402

DATASETS = {"M2_aug": "M2_aug_concat_fs1.mat", "M4": "M4_aug_concat_fs1.mat", "MJu26a": "MJu26a_fs2.mat",
            "CO": "CO_fs2.mat", "LM": "LM_fs2.mat", "SH": "SH_fs2.mat", "SO": "SO_fs2.mat"}


def main():
    ev = pd.read_parquet(os.path.join(S.DATA, "drops.parquet"))
    db = os.path.join(S.ROOT, "DATA", "db", "annotations.sqlite").replace("\\", "/")
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rec = pd.read_sql("SELECT source_file, channel, fs, n_samples FROM recordings", c)
    hours, electrode_hours, electrodes = {}, 0.0, 0
    for ds, f in DATASETS.items():
        r = rec[rec["source_file"] == f]
        h = (r["n_samples"] / r["fs"] / 3600)
        hours[ds] = float(h.max())
        electrode_hours += float(h.sum())
        electrodes += len(r)
    sp = {}
    for s_, g in ev.groupby("species"):
        sp[s_] = {"drops": int(len(g)), "recordings": sorted(g["dataset"].unique().tolist()),
                  "fall_s_median": float(g["fall_s"].median()), "depth_mv_median": float(g["depth_mv"].median()),
                  "recovery_s_median": float(g["recovery_s"].median()),
                  "recovery_ratio_median": float(g["recovery_ratio"].median()),
                  "steepness_1hz_median": float(g["steepness_1hz"].median()),
                  "never_half_back": float((~np.isfinite(g["recovery_ratio"])).mean())}
    falls = {k: v["fall_s_median"] for k, v in sp.items()}
    out = {
        "drops": int(len(ev)), "drops_pool": int((ev["set"] == "pool").sum()),
        "drops_library": int((ev["set"] == "library").sum()), "p_min": 0.8,
        "recordings": len(DATASETS), "species": int(ev["species"].nunique()), "electrodes": electrodes,
        "electrodes_with_drops": int(ev["recording_id"].nunique()),
        "recording_hours": hours, "recording_hours_total": float(sum(hours.values())),
        "electrode_hours": electrode_hours,
        "never_half_back_share": float((~np.isfinite(ev["recovery_ratio"])).mean()),
        "species_stats": sp,
        "fastest_species": min(falls, key=falls.get), "slowest_species": max(falls, key=falls.get),
        "tempo_ratio": float(max(falls.values()) / min(falls.values())),
    }
    for f in ("wavemap.json", "ch14_kinds.json", "crescendo.json", "metronome.json"):
        p = os.path.join(S.DATA, f)
        if os.path.exists(p):
            out[f.replace(".json", "")] = json.load(open(p))
    json.dump(out, open(os.path.join(S.DATA, "numbers.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k not in ("species_stats",)}, indent=1)[:3000])
    for k, v in sp.items():
        print(k, {a: (round(b, 3) if isinstance(b, float) else b) for a, b in v.items()})


if __name__ == "__main__":
    main()
