"""Re-run the RQ4 overnight sweep's refused tasks, after the environment has been fixed.

The overnight sweep (scripts/rq4_overnight.py, 2026-10-17) came back with 627 of 674 tasks complete. The 47 refused
ones were the three `deconvolved_troughs` templates: `aeon-env` had no parquet engine. Their `event_shape` →
`intervals` steps write a table, and pandas found neither pyarrow nor fastparquet. The researcher installed
fastparquet on 2026-10-18.

A refused task is not retried by the packs: `rq4_overnight.py pending` skips it, so a reason is never lost to an
endless chain. This script writes ONE pack of exactly those tasks. Its first job sets each refused `result.json`
aside into the task's `work/` folder (which stays on the cluster), so the task reads as not yet run. P2's task
then continues from its own cache: the detrend, deconvolution and impulse steps of the failed attempt are reused,
and only the parquet-writing steps compute. A task that refuses again keeps its new reason, and the chain stops on
it, as before.

    python scripts/rq4_rerun.py build                   # on the PC: the refused tasks from the returned results
    python scripts/rq4_rerun.py retry-refused <tasks>   # on the cluster, the rerun pack's first job calls this

Dev tooling: not imported by the app.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

import rq4_overnight as SWEEP  # noqa: E402

NAME = "rq4_rerun"


def refused_tasks(out_rel=SWEEP.OUT_REL):
    """[(spec, out, task, label, reason)] for every task of the sweep whose result is a refusal."""
    import json
    from Working.discovery import chain_job
    out_dir = os.path.join(REPO, out_rel)
    with open(os.path.join(out_dir, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    out = []
    for j in manifest["jobs"]:
        for i, ch in enumerate(j["channels"]):
            st = chain_job.task_status(os.path.join(REPO, j["out"]), i)
            if st["state"] == "refused":
                out.append((j["spec"], j["out"], i, f"{j['label']}/{ch}", st["reason"]))
    return out


_RETRY = """
# The overnight refusals were 'Unable to find a usable engine' for parquet: check the engine is in THIS environment
# before setting anything aside
python -c "import fastparquet" 2>/dev/null || python -c "import pyarrow" 2>/dev/null || {{
    echo ">>> No parquet engine (fastparquet or pyarrow) in $CONDA_DEFAULT_ENV -- NOT running. Install it there first."
    exit 1; }}

# The first job of this chain sets each refused result aside (into the task's work/ folder, which stays here), so
# P2's task runs again from its own cache. Later jobs do not: a task that refuses again keeps its reason.
if [ "$CHAIN_INDEX" -eq 1 ]; then
    python scripts/rq4_rerun.py retry-refused "$TASKS" || {{
        echo ">>> Could not set the refused results aside -- NOT running (is scripts/rq4_rerun.py on the cluster?)"; exit 1; }}
fi
"""


def build(out_rel=SWEEP.OUT_REL, parallel=8):
    from Working.config import HPC_CONDA_ENV_CPU, HPC_CPU_PARTITION, HPC_REMOTE_REPO_ROOT

    tasks = refused_tasks(out_rel)
    out_dir = os.path.join(REPO, out_rel)
    rel = out_rel.replace(os.sep, "/")
    tasks_file = f"{rel}/tasks_{NAME}.txt"
    with open(os.path.join(out_dir, f"tasks_{NAME}.txt"), "w", newline="\n", encoding="utf-8") as f:
        for spec, out, task, label, _why in tasks:
            f.write(f"{spec} {out} {task} {label}\n")
    script_rel = f"{rel}/{NAME}.sh"
    text = SWEEP._PACK.format(
        name=NAME, remote_root=HPC_REMOTE_REPO_ROOT, n_tasks=len(tasks), parallel=parallel, cpus=parallel,
        tasks_file=tasks_file, failed_file=f"{rel}/state/{NAME}.failed", max_chain=20, min_launch=240,
        script=script_rel, time_line="#SBATCH --time=00:20:00\n",
        partition_lines=f"#SBATCH --partition={HPC_CPU_PARTITION}",
        wall_note=("Wall 20 min: the cpu partition's own limit is unverified (Working/config.py), so this is the "
                   "conservative floor; the pack chains through it."),
        module_line="", conda_env=HPC_CONDA_ENV_CPU, limit_block="LIMIT=1200")
    anchor = "export NUMBA_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1\n"
    if anchor not in text:
        raise SystemExit("the pack template changed: cannot place the retry step")
    text = text.replace(anchor, anchor + _RETRY.format())
    with open(os.path.join(out_dir, f"{NAME}.sh"), "w", newline="\n", encoding="utf-8") as f:
        f.write(text)
    submit = [
        "#!/bin/bash",
        f"# Re-runs the {len(tasks)} refused tasks of the RQ4 overnight sweep (scripts/rq4_rerun.py) as one CPU pack.",
        "# Needs a parquet engine in the CPU environment: the overnight refusals were 'Unable to find a usable",
        f"# engine' (fastparquet, installed 2026-10-18). Run from the repo root on the cluster ({HPC_REMOTE_REPO_ROOT}).",
        "#",
        f"# Cancel:     squeue -u $USER -h -o \"%i %j\" | awk '$2 == \"{NAME}\" {{print $1}}' | xargs -r scancel",
        "# Progress:   python scripts/rq4_overnight.py report",
        f"# Bring back: the return/task<i>/ folders named in {tasks_file}",
        "# The job checks for the parquet engine itself, in the environment its tasks run in.",
        "set -euo pipefail",
        "",
        f"sbatch {script_rel}",
        "",
    ]
    with open(os.path.join(out_dir, f"submit_{NAME}.sh"), "w", newline="\n", encoding="utf-8") as f:
        f.write("\n".join(submit))
    return tasks, script_rel


def retry_refused(tasks_file):
    """Set aside the result of each listed task that reads refused; print how many."""
    from Working.discovery import chain_job
    stamp = time.strftime("%Y%m%dT%H%M%S")
    moved = 0
    with open(tasks_file, encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 4:
                continue
            out, task = parts[1], int(parts[2])
            st = chain_job.task_status(out, task)
            if st["state"] != "refused":
                continue
            ret, work = chain_job._task_dirs(out, task)
            src = os.path.join(ret, chain_job.RESULT_NAME)
            os.makedirs(work, exist_ok=True)
            os.replace(src, os.path.join(work, f"result.refused-{stamp}.json"))
            moved += 1
    print(f"[rq4_rerun] set aside {moved} refused result(s); those tasks run again from their own cache", flush=True)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="re-run the RQ4 overnight sweep's refused tasks")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="write the rerun pack from the returned results")
    r = sub.add_parser("retry-refused", help="set aside the listed tasks' refused results (the pack calls this)")
    r.add_argument("tasks")
    args = ap.parse_args(argv)
    if args.cmd == "retry-refused":
        return retry_refused(args.tasks)
    tasks, script = build()
    reasons = {}
    for *_x, why in tasks:
        key = "no parquet engine" if "parquet" in why else why.splitlines()[0][:100]
        reasons[key] = reasons.get(key, 0) + 1
    print(f"{len(tasks)} refused tasks -> {script}")
    for k, v in reasons.items():
        print(f"    {v} x {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
