#!/bin/bash
# Resume RQ4 batch 2 (M2_concat, M4_aug, L_LM). Run from the repo root on the cluster (/home/Student/s4699158/CNN).
#
# Why this exists (2026-10-18): the copy brought back at about 08:05 UTC was taken about 30 minutes into a run of
# about 3 hours. It held 527 of 1,543 tasks complete and nothing failed: no refusal and no crash. Every pack stopped
# at the same moment (cpu1 after 509 tasks in order, cpu2 after 18, gpuA had started its first 8, gpuB was still
# queued behind the three-job limit). The jobs were still running when the copy was made.
#
# What it does:
# - If any rq4b_ job is still queued or running, it submits NOTHING. Those packs continue on their own, and two
#   jobs must never write one result file.
# - Otherwise, per pack, it counts the tasks still to do from the cluster's own results and submits only the packs
#   that have work left. A finished task is skipped, and a task cut off mid-run continues from its own cache.
#
# Bring the results back only when `squeue -u $USER` lists no rq4b_ job and
#   python scripts/rq4_overnight.py report --out HPC/Detection/generated/rq4_batch2
# shows every pack complete.

B=HPC/Detection/generated/rq4_batch2

# conda's activate scripts are not `set -u` safe: activate first
source ~/miniconda3/etc/profile.d/conda.sh
conda activate aeon-env
set -eo pipefail

# read the queue outside any `if`: a failing squeue stops the script instead of reading as "nothing queued"
QUEUED="$(squeue -u "$(id -un)" -h -o "%i %j %T")"
LIVE="$(printf '%s\n' "$QUEUED" | awk '$2 ~ /^rq4b_/' || true)"
if [ -n "$LIVE" ]; then
    echo ">>> Batch 2 is still on the cluster: these jobs continue by themselves, nothing was submitted."
    printf '%s\n' "$LIVE"
    echo ">>> Wait for them to finish (squeue -u \$USER), check the report, then bring the results back."
    exit 1
fi

SUBMITTED=0
for P in cpu1 cpu2 gpuA gpuB; do
    LEFT="$(python scripts/rq4_overnight.py pending "$B/tasks_rq4b_$P.txt" "$B/state/rq4b_$P.failed" | wc -l)"
    if [ "$LEFT" -gt 0 ]; then
        echo "rq4b_$P: $LEFT tasks left -- submitting"
        sbatch "$B/rq4b_$P.sh"
        SUBMITTED=$((SUBMITTED + 1))
    else
        echo "rq4b_$P: nothing left"
    fi
done
if [ "$SUBMITTED" -eq 0 ]; then
    echo ">>> Every pack is done: run the report, then bring back every $B/*/*_out/return/ folder."
fi
