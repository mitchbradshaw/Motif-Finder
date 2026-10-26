"""
miss_rate.py — of the old manual 10-minute windows on M2_aug (annotations, source 'imported_10min', the 2025-26
labels: interesting / not_interesting / artifact, 600 samples each), how many does NO detector touch, and how much
more often does each detector touch an interesting window than a not-interesting one (the lift)?

Detectors: every live template run of Discovery session 2 (M2_aug), one row per run group = one template variant,
real runs only (no surrogate). A detection [s, e) touches a window [ws, we) when s < we and e > ws (any overlap).
A variant is scored only on the channels it ran on (four base templates ran on CH1_A1 and CH2_A1 only).

Caveat built into the read-out: the twelve CNN templates were very likely trained on these same windows (W4-A), so
their rows and any union that includes them are in-sample; the union is reported with and without them, and with
and without the 1-minute CNNs (W4-A's negative control, which cover ~90 % of the recording).

Read-only (mode=ro); writes docs/thesis/data/miss_rate/{per_variant.csv, summary.json}.

    "/c/ProgramData/anaconda3/python.exe" scripts/thesis/miss_rate.py
"""
from __future__ import annotations

import json
import os
import sqlite3

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite").replace("\\", "/")
OUT = os.path.join(ROOT, "docs", "thesis", "data", "miss_rate")
SESSION = 2
SOURCE_FILE = "M2_aug_concat_fs1.mat"


def touched(win_s, win_e, det_s, det_e):
    if len(det_s) == 0:
        return np.zeros(len(win_s), dtype=bool)
    o = np.argsort(det_s, kind="stable")
    ds, de = det_s[o], np.maximum.accumulate(det_e[o])
    idx = np.searchsorted(ds, win_e, side="left")          # detections starting before the window ends
    out = np.zeros(len(win_s), dtype=bool)
    ok = idx > 0
    out[ok] = de[idx[ok] - 1] > win_s[ok]
    return out


def fam(name):
    import re
    base = re.sub(r"__.*$", "", name)
    if base.startswith("cnn_"):
        return "cnn_" + base.rsplit("_", 1)[-1]
    if base.startswith("mp_"):
        return "matrix_profile"
    return base


def main():
    os.makedirs(OUT, exist_ok=True)
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    lab = pd.read_sql_query(
        "SELECT a.id, a.recording_id, a.start_idx s, a.end_idx e, a.verdict FROM annotations a "
        "JOIN recordings r ON r.id = a.recording_id WHERE a.source = 'imported_10min' AND a.deleted_at IS NULL "
        "AND r.source_file = ?", c, params=(SOURCE_FILE,))
    drs = c.execute("SELECT id, template_name, run_group_id FROM discovery_runs WHERE session_id = ? "
                    "AND kind = 'template' AND removed_at IS NULL AND run_group_id IS NOT NULL ORDER BY id",
                    (SESSION,)).fetchall()
    seen, variants = set(), []
    for dr_id, name, rg in drs:
        if rg in seen:
            continue
        seen.add(rg)
        variants.append((name, rg))
    cols = {}
    covered = {}
    for name, rg in variants:
        t = np.zeros(len(lab), dtype=bool)
        cov = np.zeros(len(lab), dtype=bool)
        for run_id, rec_id, s0 in c.execute("SELECT id, recording_id, span_start FROM runs WHERE run_group_id = ? "
                                            "AND surrogate_of_run_id IS NULL", (rg,)).fetchall():
            m = (lab["recording_id"] == rec_id).to_numpy()
            if not m.any():
                continue
            d = np.array(c.execute("SELECT start_idx, end_idx FROM detections WHERE run_id = ?", (run_id,)).fetchall(),
                         dtype=np.int64).reshape(-1, 2)
            cov |= m
            t[m] |= touched(lab["s"].to_numpy()[m], lab["e"].to_numpy()[m], d[:, 0], d[:, 1])
        cols[name] = t
        covered[name] = cov
    T = pd.DataFrame(cols)
    C = pd.DataFrame(covered)
    v = lab["verdict"].to_numpy()
    rows = []
    for name, _rg in variants:
        cov = C[name].to_numpy()
        ti = T[name].to_numpy()
        ni = int(((v == "interesting") & cov).sum())
        nn = int(((v == "not_interesting") & cov).sum())
        ri = float((ti & (v == "interesting") & cov).sum() / ni) if ni else np.nan
        rn = float((ti & (v == "not_interesting") & cov).sum() / nn) if nn else np.nan
        rows.append({"variant": name, "family": fam(name), "channels_covered": int(lab.loc[cov, "recording_id"].nunique()),
                     "n_interesting": ni, "n_not": nn, "touch_interesting": ri, "touch_not": rn,
                     "lift": ri / rn if rn and rn > 0 else np.inf, "miss_interesting": 1 - ri if ni else np.nan,
                     "cnn_in_sample": name.startswith("cnn_")})
    pv = pd.DataFrame(rows).sort_values("lift", ascending=False)
    pv.to_csv(os.path.join(OUT, "per_variant.csv"), index=False)

    def union(select):
        names = [n for n, _ in variants if select(n)]
        u = T[names].any(axis=1).to_numpy()
        allcov = C[names].all(axis=1).to_numpy()   # a window every one of them looked at (all 16 channels for most)
        out = {"variants": len(names)}
        for nm, mask in (("all_windows", np.ones(len(lab), bool)), ("windows_on_CH1_CH2", allcov)):
            ni = int(((v == "interesting") & mask).sum())
            nn = int(((v == "not_interesting") & mask).sum())
            out[nm] = {"n_interesting": ni, "n_not": nn,
                       "interesting_touched_by_none": int(((~u) & (v == "interesting") & mask).sum()),
                       "share_interesting_untouched": float(((~u) & (v == "interesting") & mask).sum() / ni) if ni else None,
                       "share_not_untouched": float(((~u) & (v == "not_interesting") & mask).sum() / nn) if nn else None}
        return out

    summary = {
        "labels": lab["verdict"].value_counts().to_dict(), "source": "annotations.source = 'imported_10min' "
        "(created 2026-08-03 by the importer; the 2025-26 manual 10-minute window labels, 600 samples at 1 Hz)",
        "n_variants": len(variants),
        "union_all": union(lambda n: True),
        "union_no_cnn": union(lambda n: not n.startswith("cnn_")),
        "union_no_1min_cnn": union(lambda n: not (n.startswith("cnn_") and n.endswith("_1min"))),
        "union_selective": union(lambda n: fam(n) in ("drop_detection_v1", "drop_detection_v5", "wavelet_encoded")),
    }
    nocnn = [n for n, _ in variants if not n.startswith("cnn_")]
    miss = lab[(~T[nocnn].any(axis=1).to_numpy()) & (v == "interesting")]
    summary["untouched_interesting_no_cnn"] = miss[["id", "recording_id", "s", "e"]].to_dict("records")
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, default=str)
    print(json.dumps(summary, indent=1, default=str))
    pd.set_option("display.width", 220)
    print(pv.to_string(index=False, float_format=lambda x: f"{x:.3f}"))


if __name__ == "__main__":
    main()
