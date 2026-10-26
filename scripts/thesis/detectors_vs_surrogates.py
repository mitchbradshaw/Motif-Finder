"""
detectors_vs_surrogates.py — every RQ4b sweep run against its own phase-randomised copy, read-only.

For each Discovery sweep session (M2_aug 2, LM_fs2 3, CO_fs2 4, L_LM fs2 5, M2_concat 6, L_LM 10 Hz 8; the M4
session 7 is never read) it takes each live Discovery run's run group, pairs every real run with the runs whose
``surrogate_of_run_id`` names it, and counts detections per run (indexed ``detections(run_id)``, one run at a time).
One row per (template variant, channel) = one cluster *task*; then per variant and recording, per family.

"real > surrogate" is strict: a task where the real signal gave no more detections than its copy is a "no".

Writes docs/thesis/data/detectors_vs_surrogates/{tasks.csv, by_variant_recording.csv, by_family.csv, summary.json}.

    "/c/ProgramData/anaconda3/python.exe" scripts/thesis/detectors_vs_surrogates.py
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite").replace("\\", "/")
OUT = os.path.join(ROOT, "docs", "thesis", "data", "detectors_vs_surrogates")
SESSIONS = {2: "M2_aug", 3: "LM_fs2", 4: "CO_fs2", 5: "L_LM_fs2", 6: "M2_concat", 8: "L_LM_10Hz"}
HELD_OUT_FILE = "M4_aug_concat_fs1.mat"
#: the three matrix-profile copies made locally from the cached profiles after each import (not cluster tasks)
LOCAL_MP_COPIES = ("mp_threshold__threshold_6__backend_auto", "mp_threshold__threshold_10__backend_auto",
                   "mp_motifs__backend_auto")


def family(name):
    base = re.sub(r"__.*$", "", name or "")
    if base.startswith("cnn_"):
        m = re.match(r"cnn_[a-z0-9]+_(\d+min)", base)
        return f"cnn_{m.group(1)}" if m else "cnn"
    if base.startswith("mp_"):
        return "matrix_profile"
    if base in ("dehshibi_spikes", "Wavelet_detection_prototype"):
        return base
    return base


def main():
    os.makedirs(OUT, exist_ok=True)
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = []
    for sid, rec_name in SESSIONS.items():
        drs = c.execute("SELECT id, template_name, label, run_group_id, created_at FROM discovery_runs "
                        "WHERE session_id = ? AND kind = 'template' AND removed_at IS NULL AND run_group_id IS NOT NULL "
                        "ORDER BY id", (sid,)).fetchall()
        seen = set()
        for dr_id, tname, label, rg, created in drs:
            if rg in seen:           # one run group read once per session (a re-adopted copy shares it)
                continue
            seen.add(rg)
            real = c.execute("SELECT r.id, r.recording_id, rec.channel, rec.source_file FROM runs r "
                             "JOIN recordings rec ON rec.id = r.recording_id WHERE r.run_group_id = ? "
                             "AND r.surrogate_of_run_id IS NULL AND rec.source_file != ?", (rg, HELD_OUT_FILE)).fetchall()
            for rid, rec_id, ch, sf in real:
                n_real = c.execute("SELECT COUNT(*) FROM detections WHERE run_id = ?", (rid,)).fetchone()[0]
                surs = [s[0] for s in c.execute("SELECT id FROM runs WHERE surrogate_of_run_id = ?", (rid,))]
                ns = [c.execute("SELECT COUNT(*) FROM detections WHERE run_id = ?", (s,)).fetchone()[0] for s in surs]
                rows.append({"session": sid, "recording": rec_name, "source_file": sf, "discovery_run": dr_id,
                             "template": tname or label, "family": family(tname or label), "run_group": rg,
                             "real_run": rid, "recording_id": rec_id, "channel": ch, "n_real": n_real,
                             "n_draws": len(ns), "n_surrogate_mean": float(np.mean(ns)) if ns else np.nan,
                             "n_surrogate_draws": ";".join(str(x) for x in ns),
                             "local_mp_copy": (tname or label) in LOCAL_MP_COPIES,
                             "is_1min_cnn": bool(re.match(r"cnn_.*_1min$", tname or ""))})
    t = pd.DataFrame(rows)
    t["real_gt_sur"] = t["n_real"] > t["n_surrogate_mean"]
    t["ratio"] = t["n_real"] / t["n_surrogate_mean"].replace(0, np.nan)
    t.to_csv(os.path.join(OUT, "tasks.csv"), index=False)

    def agg(g):
        return pd.Series({"tasks": len(g), "real": int(g.n_real.sum()), "surrogate": float(g.n_surrogate_mean.sum()),
                          "ratio": (g.n_real.sum() / g.n_surrogate_mean.sum()) if g.n_surrogate_mean.sum() else np.inf,
                          "tasks_real_gt_sur": int(g.real_gt_sur.sum()),
                          "tasks_real_le_sur": int((~g.real_gt_sur & g.n_draws.gt(0)).sum()),
                          "tasks_both_zero": int(((g.n_real == 0) & (g.n_surrogate_mean == 0)).sum())})
    by_vr = t.groupby(["template", "recording"]).apply(agg).reset_index()
    by_vr["real_exceeds"] = by_vr["real"] > by_vr["surrogate"]
    by_vr.to_csv(os.path.join(OUT, "by_variant_recording.csv"), index=False)
    by_fam = t.groupby(["family"]).apply(agg).reset_index()
    by_fam.to_csv(os.path.join(OUT, "by_family.csv"), index=False)
    tt = t[~t.local_mp_copy]
    g = tt.groupby(["family", "recording"]).agg(real=("n_real", "sum"), sur=("n_surrogate_mean", "sum"),
                                                 tasks=("real_run", "size"),
                                                 n_le=("real_gt_sur", lambda s: int((~s).sum()))).reset_index()
    g["cell"] = [("%.2f" % (r / s_) if s_ > 0 else ("inf" if r > 0 else "0/0")) + " (%d/%d)" % (k, n)
                 for r, s_, k, n in zip(g.real, g.sur, g.n_le, g.tasks)]
    g.to_csv(os.path.join(OUT, "by_family_recording.csv"), index=False)
    g.pivot(index="family", columns="recording", values="cell").fillna("-").to_csv(
        os.path.join(OUT, "family_recording_pivot.csv"))

    # the RQ4b statement: batch 3 (LM_fs2, CO_fs2, L_LM fs2), the cluster's tasks only (not the local MP copies)
    b3 = t[t.session.isin([3, 4, 5]) & ~t.local_mp_copy]
    b3_dedup = b3.drop_duplicates(["template", "recording_id"])
    stmt = {"tasks": int(len(b3_dedup)), "real_le_sur": int((~b3_dedup.real_gt_sur).sum()),
            "by_family": b3_dedup.groupby("family").apply(
                lambda g: {"tasks": int(len(g)), "real_le_sur": int((~g.real_gt_sur).sum()),
                           "both_zero": int(((g.n_real == 0) & (g.n_surrogate_mean == 0)).sum())}).to_dict(),
            "by_recording": b3_dedup.groupby("recording").apply(
                lambda g: {"tasks": int(len(g)), "real_le_sur": int((~g.real_gt_sur).sum())}).to_dict()}
    summary = {"n_tasks_all_sessions": int(len(t)), "n_tasks_real_le_sur_all": int((~t.real_gt_sur).sum()),
               "draws_per_task": t.n_draws.value_counts().to_dict(), "batch3_statement": stmt,
               "by_recording": t[~t.local_mp_copy].groupby("recording").apply(
                   lambda g: {"tasks": int(len(g)), "real_le_sur": int((~g.real_gt_sur).sum())}).to_dict()}
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, default=str)
    print(json.dumps(summary, indent=1, default=str))
    pd.set_option("display.width", 220)
    print(by_fam.to_string())


if __name__ == "__main__":
    main()
