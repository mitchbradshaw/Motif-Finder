"""Recompute, on this PC, the classical 2 Hz sweep tasks whose geometry never came back (9 Nov 2026).

Why: 312 complete tasks' result.json files hold only counts — their cheap steps were never cached and their
scratch.sqlite stayed on the cluster. `chain_job.run_task` is the cluster's own task runner: it builds a fresh
scratch database and step cache inside the given out folder (here the session scratchpad), checks every hash
against the spec, and runs the real chain plus its paired phase-randomised surrogate. Nothing is written under
DATA/ or into the live DB. The recomputed geometry is accepted only where its real and surrogate counts equal the
cluster's result.json (checked by rq4n_complete_20261109.py geom). The 1-minute CNNs (negative controls) are not
recomputed.

    python scripts/thesis/rq4n_recompute_missing_20261109.py [workers]
"""
import json
from multiprocessing import Pool
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
MAIN = Path("C:/Users/mmebr/Documents/CNN")
OUT = Path(os.environ.get("RQ4N_RECOMPUTE", "C:/Users/mmebr/AppData/Local/Temp/claude/9d11021b66984e2e/"
                          "55c783cf-2a76-451d-bb08-e09ff21dd7b9/scratchpad/recompute"))


def one(job):
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("NUMBA_CACHE_DIR", str(OUT / "_numba"))
    from Working.discovery.chain_job import run_task, spec_hash
    spec_path, task, out_dir, expect = job
    spec = json.loads(Path(spec_path).read_text())
    assert spec_hash(spec) == expect, spec_path
    r = run_task(spec, task, out_dir, repo_root=str(MAIN))
    return spec_path, task, r.get("complete"), r.get("error"), (r.get("run") or {}).get("detections"), \
        (r.get("draws") or {}).get("detections"), r.get("elapsedS")


def jobs():
    import pandas as pd
    cov = pd.read_csv(ROOT / "docs/thesis/data/ch10_2hz_complete/geometry_coverage_tasks.csv")
    a = json.loads((ROOT / "docs/thesis/data/recovery_latest_20261109/audit.json").read_text())
    idx = {(r["recording"], r["setting"], r["task"]): r for r in a["all_tasks"]}
    out = []
    for _, m in cov[cov.real_src.isna() | cov.sur_src.isna()].iterrows():
        if m.setting.startswith("cnn_") and m.setting.endswith("_1min"):
            continue
        r = idx[(m.recording, m.setting, int(m.task))]
        res = json.loads((MAIN / r["result"]).read_text())
        out.append((str(MAIN / r["spec"]), int(m.task), str(OUT / m.recording / Path(r["out"]).name),
                    res["specHash"], (0 if pd.isna(m.real_src) else 1, (res.get("elapsedS") or 0) * (-1 if pd.isna(m.real_src) else 1))))
    out.sort(key=lambda j: j[4])            # missing real geometry first (longest first), then surrogate-only (shortest first)
    return [j[:4] for j in out]


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    todo = jobs()
    print(len(todo), "tasks", flush=True)
    with Pool(n, maxtasksperchild=8) as p:
        for i, r in enumerate(p.imap_unordered(one, todo), 1):
            print(i, *r, flush=True)
