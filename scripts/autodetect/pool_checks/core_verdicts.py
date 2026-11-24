"""
core_verdicts.py
================
Do the researcher's past verdicts, over every dataset, back any rule beyond the ones the pool already uses?

The pool's rules were settled on 24 Nov evening, from queue 57's verdicts and the 2,535 judged drops of the first
38 channels. When all 144 channels were done, 4,794 judged drops of the run landed on judged spans, on nine datasets.
This check reads them again, restricted to the drops that pass the core's settings (every rule, with "already judged"
and "already in a queue" set aside, as `build_pool.calibration` does). For every measure the filter keeps, it prints
how often each band was accepted, and what a rule cutting that band would remove from the core.

A band is worth a rule only if all of these hold: it is a property one can say in a sentence; at least about 50
judged drops sit in it; it is accepted clearly less often than the rest (about half or less); and cutting it keeps
most of the core.

A side check of the 24 Nov drop pool (scripts/autodetect/run_pool.py, build_pool.py). Read-only: it reads the
pool's `flags/` and `pool.parquet`, and no database. Output: docs/autodetect/20261124_pool/checks/core_verdicts.out.txt.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/autodetect/pool_checks/core_verdicts.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # the repo
sys.path.insert(0, os.path.join(ROOT, "scripts", "autodetect"))
import build_pool as BP  # noqa: E402

BANDS = {
    "depth_mv": [0, 0.1, 0.25, 0.5, 1, 2, 5, 10, 1e12],
    "clarity": [15, 20, 25, 30, 50, 100, 300, 1e12],
    "confidence": [0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0001],
    "p_r4": [0, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 1.0001],
    "sharpness": [1, 2, 3, 5, 10, 20, 50, 1e12],
    "prominence": [0, 0.25, 0.5, 1, 2, 3, 1e12],
    "duration_s": [0, 10, 30, 60, 120, 300, 600, 1200],
    "n_sources": [0, 1, 2, 3, 4, 5, 1e3],
    "wd_n_events": [0, 1, 2, 3, 1e6],
}


def table(c, pool, key, bins=None):
    """Accepted share by band of `key` among the judged drops `c`, and the core drops each band holds."""
    kc = pd.cut(pd.to_numeric(c[key], errors="coerce"), bins) if bins is not None else c[key].astype(str)
    kp = pd.cut(pd.to_numeric(pool[key], errors="coerce"), bins) if bins is not None else pool[key].astype(str)
    rows = []
    core_n = pool.groupby(kp, observed=True).size()
    for k, g in c.groupby(kc, observed=True):
        acc = int((g["label"] == "accepted").sum())
        rows.append({"band": str(k), "judged": len(g), "accepted": acc,
                     "rejected": int((g["label"] == "rejected").sum()), "unsure": int((g["label"] == "unsure").sum()),
                     "accepted_share": acc / len(g), "core_drops": int(core_n.get(k, 0)),
                     "core_share": float(core_n.get(k, 0)) / max(1, len(pool))})
    return pd.DataFrame(rows)


def main():
    pd.set_option("display.width", 200)
    allc = BP.load_flags()
    judged = allc[allc["label"] != ""].copy()
    core_ok = BP.rule_mask(judged.assign(reviewed=False, seen=False), with_overlap=False).to_numpy(bool)
    c = judged[core_ok].copy()
    pool = pd.read_parquet(os.path.join(BP.POOL, "pool.parquet"))
    core = pool[pool["tier"] == "core"].copy()
    for d in (c, core):
        d["finder_only"] = d["finder_only"].astype(bool)
        d["glitch"] = d["glitch"].astype(bool)
        d["shoulder"] = d["shoulder"].astype(bool)
        d["wd_long_tail"] = d["wd_long_tail"].fillna(False).astype(bool)
    acc = (c["label"] == "accepted").mean()
    print(f"judged drops of the run: {len(judged):,}; passing the core's settings: {len(c):,}, accepted {acc:.1%} "
          f"(rejected {(c['label'] == 'rejected').mean():.1%}, unsure {(c['label'] == 'unsure').mean():.1%})")
    print(f"core tier: {len(core):,} drops\n")
    print("== by dataset ==")
    print(table(c, core, "dataset").to_string(index=False), "\n")
    for key, bins in BANDS.items():
        print(f"== by {key} ==")
        print(table(c, core, key, bins).to_string(index=False), "\n")
    for key in ("finder_only", "glitch", "shoulder", "wd_long_tail"):
        print(f"== by {key} ==")
        print(table(c, core, key).to_string(index=False), "\n")
    # two the first look suggested: is a small drop's lower acceptance a dataset's, or every dataset's?
    print("== depth <= 0.25 mV, by dataset (judged; accepted share) ==")
    small = c[pd.to_numeric(c["depth_mv"], errors="coerce") <= 0.25]
    print(small.groupby("dataset").agg(judged=("label", "size"),
                                       accepted=("label", lambda v: (v == "accepted").mean())).to_string(), "\n")
    print("== only the finder vouched, by dataset (judged; accepted share) ==")
    fo = c[c["finder_only"]]
    print(fo.groupby("dataset").agg(judged=("label", "size"),
                                    accepted=("label", lambda v: (v == "accepted").mean())).to_string(), "\n")
    # what each candidate rule would cost: core drops removed, and the verdicts' accepted share with it applied
    print("== candidate rules: what each would remove ==")
    tests = {
        "depth <= 0.25 mV": lambda d: pd.to_numeric(d["depth_mv"], errors="coerce") <= 0.25,
        "depth <= 0.1 mV": lambda d: pd.to_numeric(d["depth_mv"], errors="coerce") <= 0.1,
        "clarity < 20": lambda d: pd.to_numeric(d["clarity"], errors="coerce") < 20,
        "clarity < 30": lambda d: pd.to_numeric(d["clarity"], errors="coerce") < 30,
        "only the finder vouched": lambda d: d["finder_only"],
        "one source only": lambda d: pd.to_numeric(d["n_sources"], errors="coerce") <= 1,
        "sharpness <= 2": lambda d: pd.to_numeric(d["sharpness"], errors="coerce") <= 2,
        "confidence < 0.7": lambda d: d["confidence"] < 0.7,
    }
    rows = []
    for name, fn in tests.items():
        mc, mp = fn(c).fillna(False).to_numpy(bool), fn(core).fillna(False).to_numpy(bool)
        rows.append({"rule": name, "judged_cut": int(mc.sum()),
                     "cut_accepted_share": float((c.loc[mc, "label"] == "accepted").mean()) if mc.any() else np.nan,
                     "accepted_share_after": float((c.loc[~mc, "label"] == "accepted").mean()),
                     "accepted_lost": int((c.loc[mc, "label"] == "accepted").sum()),
                     "core_cut": int(mp.sum()), "core_cut_share": float(mp.mean()),
                     "core_left": int((~mp).sum())})
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
