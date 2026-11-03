"""
b10_cnn_scales.py - B10 from existing data: at which CNN time scale (1, 10, 60 min) does a recording give more
detections than its one phase-randomised copy?

Reads docs/thesis/data/detectors_vs_surrogates/by_variant_recording.csv (written by detectors_vs_surrogates.py from
the RQ4b sweeps, read-only), keeps the cnn_* rows, and drops L_LM_10Hz (the same MJu26a channels as L_LM_fs2, at a
different rate; L_LM_fs2 stands in for MJu26a, which the sweep did not run as itself). Writes
docs/thesis/data/ch10_b10/cnn_scales.csv (one row per encoding x scale x recording) and cnn_scales_pivot.csv.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/thesis/b10_cnn_scales.py
"""
import os
import re

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "docs", "thesis", "data", "detectors_vs_surrogates", "by_variant_recording.csv")
OUT = os.path.join(ROOT, "docs", "thesis", "data", "ch10_b10")


def main():
    d = pd.read_csv(SRC)
    d = d[d.template.str.startswith("cnn_") & (d.recording != "L_LM_10Hz")].copy()
    m = d.template.str.extract(r"cnn_([a-z0-9]+)_(\d+)min")
    d["encoding"], d["scale_min"] = m[0], m[1].astype(int)
    d["recording"] = d.recording.replace({"L_LM_fs2": "MJu26a (as L_LM_fs2)"})
    d["frac_tasks_real_gt"] = d.tasks_real_gt_sur / d.tasks
    cols = ["encoding", "scale_min", "recording", "tasks", "real", "surrogate", "ratio", "tasks_real_gt_sur",
            "frac_tasks_real_gt"]
    d = d[cols].sort_values(["scale_min", "encoding", "recording"])
    os.makedirs(OUT, exist_ok=True)
    d.to_csv(os.path.join(OUT, "cnn_scales.csv"), index=False)
    piv = d.pivot_table(index=["scale_min", "encoding"], columns="recording", values="ratio")
    piv.to_csv(os.path.join(OUT, "cnn_scales_pivot.csv"))
    pd.set_option("display.width", 200)
    print(piv.round(2))
    # per scale: how many (encoding, recording) cells beat the copy (ratio > 1 AND most tasks real > surrogate)
    d["beats"] = (d.ratio > 1) & (d.frac_tasks_real_gt > 0.5)
    print(d.groupby(["scale_min", "recording"]).beats.agg(["sum", "count"]).unstack())
    print(d.groupby("scale_min").agg(cells=("beats", "size"), beats=("beats", "sum"),
                                     median_ratio=("ratio", "median")))


if __name__ == "__main__":
    main()
