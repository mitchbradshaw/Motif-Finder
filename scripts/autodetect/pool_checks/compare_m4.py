"""Does the pool driver's drops-only pass reproduce v4's M4 CH1_A1 drops?

A side check of the 24 Nov drop pool (scripts/autodetect/run_pool.py, build_pool.py): does the pool's drops-only pass reproduce v4's M4 CH1_A1 drops? (output: checks/compare_m4.out.txt).
Read-only on the database. Kept from the session that built the pool; queue 57's detections are ids 13389236-13394543.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/autodetect/pool_checks/compare_m4.py
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # the repo
sys.path.insert(0, ROOT)
from Working.discovery.candidate_events import _caught  # noqa: E402

new = pd.read_parquet(os.path.join(ROOT, "DATA", "derived", "autodetect", "pool_20261124", "raw", "49",
                                   "candidates.parquet"))
old = pd.read_csv(os.path.join(ROOT, "docs", "autodetect", "20261123_v4", "M4_CH1_A1", "candidates.csv"))
acc = pd.read_csv(os.path.join(ROOT, "docs", "autodetect", "20261123_v4", "M4_CH1_A1", "known_accepted.csv"))
print("new columns:", list(new.columns))
for t in (0.5, 0.6):
    n = new[(new["polarity"] == "drop") & (new["confidence"] >= t) & (new["kind"] == "proposal")]
    o = old[(old["polarity"] == "drop") & (old["confidence"] >= t) & (old["kind"] == "proposal")]
    a = lambda d, c: d[c].to_numpy(np.int64)  # noqa: E731
    o_in_n = _caught(a(o, "start_idx"), a(o, "end_idx"), a(n, "start_idx"), a(n, "end_idx"))
    n_in_o = _caught(a(n, "start_idx"), a(n, "end_idx"), a(o, "start_idx"), a(o, "end_idx"))
    found_new = _caught(a(acc, "start"), a(acc, "end"), a(n, "start_idx"), a(n, "end_idx"))
    found_old = _caught(a(acc, "start"), a(acc, "end"), a(o, "start_idx"), a(o, "end_idx"))
    print(f">= {t}: v4 drops {len(o)}, new drops {len(n)}; v4's found by new {o_in_n.mean():.1%}; "
          f"new's found in v4 {n_in_o.mean():.1%}; accepted found new {found_new.sum()}/{len(acc)} vs v4 "
          f"{found_old.sum()}/{len(acc)}")
    lost = o[~o_in_n]
    if len(lost):
        print("   v4 drops the new run misses (first 8):")
        print(lost[["candidate_id", "start_idx", "end_idx", "confidence", "sources", "depth_mv", "runs"]].head(8).to_string())
