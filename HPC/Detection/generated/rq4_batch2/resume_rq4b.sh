#!/bin/bash
# Resume RQ4 batch 2 (M2_concat, M4_aug, L_LM). Run from the repo root on the cluster (/home/Student/s4699158/CNN).
#
#   bash HPC/Detection/generated/rq4_batch2/resume_rq4b.sh                 every pack with work left
#   bash HPC/Detection/generated/rq4_batch2/resume_rq4b.sh cpu1 gpuA gpuB  only these
#
# What stopped it (2026-10-18, from sacct and the logs): at 18:06 AEST the cluster could no longer write.
#   - Three jobs failed at start with no log file (exit 0:53).
#   - The running ones stopped mid-task without writing a word, and rq4b_gpuA ended "every task crashed".
#   - About 16 GB of returned sweep results were in the home folder by then.
# Free space first: HPC/Detection/generated/rq4_batch2/cleanup_copied.sh deletes only what the PC already holds,
# checked file by file. The A100 packs now ask for 5 h (they got the partition's 1 h default before).
#
# Space each pack still needs here (measured from the returned tasks, 2026-10-18):
#   cpu1 (M2_concat + M4_aug CPU)   about 4.2 GB
#   cpu2 (L_LM CPU)                 about 39 GB   (about 331 MB a task: full-length intermediate signals)
#   gpuA / gpuB (CNN, matrix prof.) under 0.5 GB each
# What comes back here is copied once more into the app's cache when it is imported on the PC.
#
# - If any rq4b_ job is still queued or running, it submits NOTHING: two jobs must never write one result file.
# - Otherwise it submits each chosen pack that still has work. A finished task is skipped, and a task cut off
#   mid-run continues from its own cache.

B=HPC/Detection/generated/rq4_batch2
PACKS="${*:-cpu1 cpu2 gpuA gpuB}"

# conda's activate scripts are not `set -u` safe: activate first
source ~/miniconda3/etc/profile.d/conda.sh
conda activate aeon-env
set -eo pipefail

for P in $PACKS; do
    case "$P" in cpu1|cpu2|gpuA|gpuB) ;; *) echo "unknown pack '$P' (cpu1 cpu2 gpuA gpuB)"; exit 2;; esac
done

echo "---- space (check there is room for the packs above) ----"
quota -s 2>/dev/null || true
df -h "$HOME" | tail -1
echo "---------------------------------------------------------"

# read the queue outside any `if`: a failing squeue stops the script instead of reading as "nothing queued"
QUEUED="$(squeue -u "$(id -un)" -h -o "%i %j %T")"
LIVE="$(printf '%s\n' "$QUEUED" | awk '$2 ~ /^rq4b_/' || true)"
if [ -n "$LIVE" ]; then
    echo ">>> Batch 2 is still on the cluster: these jobs continue by themselves, nothing was submitted."
    printf '%s\n' "$LIVE"
    exit 1
fi

SUBMITTED=0
for P in $PACKS; do
    LEFT="$(python scripts/rq4_overnight.py pending "$B/tasks_rq4b_$P.txt" "$B/state/rq4b_$P.failed" | wc -l)"
    if [ "$LEFT" -gt 0 ]; then
        echo "rq4b_$P: $LEFT tasks left -- submitting"
        sbatch "$B/rq4b_$P.sh"
        SUBMITTED=$((SUBMITTED + 1))
    else
        echo "rq4b_$P: nothing left"
    fi
done
[ "$SUBMITTED" -gt 0 ] || echo ">>> Nothing to submit for: $PACKS"
