"""Compare every PC-recomputed 2 Hz task (rq4n_recompute_missing_20261109.py) with the cluster's result.json.

A recomputed task is accepted only when its real AND surrogate detection counts equal the cluster's, and its spec
hash, config hash and step-prefix hashes are the same. Writes docs/thesis/data/ch10_2hz_complete/recompute_check.csv
and prints the tasks that do not match. Read-only.

    RQ4N_RECOMPUTE=<folder> python scripts/thesis/rq4n_recompute_check_20261109.py
"""
import json
import os
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MAIN = Path("C:/Users/mmebr/Documents/CNN")
RECOMP = Path(os.environ["RQ4N_RECOMPUTE"])

a = json.loads((ROOT / "docs/thesis/data/recovery_latest_20261109/audit.json").read_text())
rows = []
for r in a["all_tasks"]:
    p = RECOMP / r["recording"] / Path(r["out"]).name / "return" / f"task{r['task']}" / "result.json"
    if not p.exists():
        continue
    pc = json.loads(p.read_text())
    cl = json.loads((MAIN / r["result"]).read_text())
    row = {"recording": r["recording"], "setting": r["setting"], "task": r["task"], "channel": r["channel"],
           "pc_complete": pc.get("complete"), "pc_error": pc.get("error"),
           "cluster_real": (cl.get("run") or {}).get("detections"),
           "pc_real": (pc.get("run") or {}).get("detections"),
           "cluster_surrogate": (cl.get("draws") or {}).get("detections"),
           "pc_surrogate": (pc.get("draws") or {}).get("detections"),
           "same_hashes": pc.get("specHash") == cl.get("specHash") and pc.get("configHash") == cl.get("configHash")
           and pc.get("prefixHashes") == cl.get("prefixHashes"),
           "pc_elapsed_s": pc.get("elapsedS"), "cluster_elapsed_s": cl.get("elapsedS")}
    row["accepted"] = bool(row["pc_complete"] and row["same_hashes"] and row["pc_real"] == row["cluster_real"]
                           and row["pc_surrogate"] == row["cluster_surrogate"])
    rows.append(row)
df = pd.DataFrame(rows)
df.to_csv(ROOT / "docs/thesis/data/ch10_2hz_complete/recompute_check.csv", index=False)
print(f"{len(df)} recomputed result files; accepted {int(df.accepted.sum())}; complete {int(df.pc_complete.sum())}")
bad = df[~df.accepted]
if len(bad):
    print(bad.to_string())
sys.exit(0)
