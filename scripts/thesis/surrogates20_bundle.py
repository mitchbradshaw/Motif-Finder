"""
surrogates20_bundle.py — PREPARE (never submit) a rangpur SLURM bundle that re-runs the most precise RQ4b detector
variants on M2_aug with 20 phase-randomised null draws per channel (the RQ4b read-out's step 3, "one variant per
template re-run with 20 null draws").

It uses the same machinery as the overnight sweep (`scripts/rq4_overnight.py`, P2's `Working.discovery.chain_job`
specs, the packed pack scripts) on a SANDBOX copy of the database in the session scratchpad
(`webui.server.runtime.Runtime(mode="sandbox")`: the step cache, the adapters' RESULTS_DIRs, the classifier
MODEL_ROOT and the cost calibrations are all redirected there). Nothing is written to DATA/ or the real database;
the bundle is written to docs/thesis/hpc/surrogates20_M2_aug/.

The six variants (precision on M2_aug from queue 25's stratified blind sample, per setting,
DATA/derived/candidate_events/M2_aug_concat_fs1_bf098c00/sample_seed0_l100_f50/estimate.json):
  drop_detection_v1__slope_sigma_4 0.99 · drop_detection_v1 0.94 · wavelet_encoded__level_5 0.92 ·
  cnn_gadf_10min 0.97 · cnn_recurrence_10min 0.96 · drop_detection_v5__same_fraction_0p7 0.81
(four families; the highest-precision setting of each, plus the base drop detector and a second CNN).

    "/c/ProgramData/anaconda3/python.exe" scripts/thesis/surrogates20_bundle.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
SCRATCH = r"C:\Users\mmebr\AppData\Local\Temp\claude\C--Users-mmebr-Documents-CNN\ee7dfe78-0c27-48d6-91e6-dd2ef2948732\scratchpad\analyses_cache"
OUT_REL = os.path.join("docs", "thesis", "hpc", "surrogates20_M2_aug")
PREFIX = "th20"
DRAWS = 20
SIX = ["drop_detection_v1__slope_sigma_4", "drop_detection_v1", "wavelet_encoded__level_5", "cnn_gadf_10min",
       "cnn_recurrence_10min", "drop_detection_v5__same_fraction_0p7"]


def main():
    from webui.server.runtime import Runtime
    rt = Runtime(mode="sandbox", runtime_root=SCRATCH).setup()
    print("sandbox database:", rt.db_path)
    spec = importlib.util.spec_from_file_location("rq4o", os.path.join(ROOT, "scripts", "rq4_overnight.py"))
    R = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(R)
    from Working.database.schema import init_db
    conn = init_db(rt.db_path)
    templates = R._load_templates(conn)
    entries = [e for e in R.sweep_entries(templates, mp_channels=[]) if e[0] in SIX]
    missing = sorted(set(SIX) - {e[0] for e in entries})
    if missing:
        raise SystemExit(f"not in the sweep entries: {missing}")
    out_dir = os.path.join(ROOT, OUT_REL)
    manifest, tasks = R._build_source(conn, templates, source=R.SOURCE, out_dir=out_dir, entries=entries,
                                      span=R.SPAN, null_draws=DRAWS)
    manifest["packs"] = R._write_packs(out_dir, OUT_REL, tasks, prefix=PREFIX)
    # the inputs every task reads: the 16 channel arrays (and the CNN checkpoints, already on the cluster)
    inputs = sorted({t["npy"] for j in manifest["jobs"]
                     for t in json.load(open(os.path.join(ROOT, j["spec"]), encoding="utf-8"))["targets"]})
    manifest["inputs"] = inputs
    manifest["draws"] = DRAWS
    manifest["note"] = ("prepared by scripts/thesis/surrogates20_bundle.py on a sandbox copy; NOT submitted. "
                        "Estimates per pack are the overnight script's balancing figures (real + 1 draw, measured "
                        "on a loaded PC, halved) scaled by the chain's run count; see the findings file")
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    conn.close()
    print(f"{len(manifest['jobs'])} chain jobs, refused {len(manifest['refused'])}")
    for j in manifest["jobs"]:
        print("  ", j["label"], j["specHash"][:8], len(j["channels"]), "channels", j["draws"], "draws", j["kind"])
    for r in manifest["refused"]:
        print("   refused:", r)
    for p in manifest["packs"]:
        print("  pack", p)


if __name__ == "__main__":
    main()
