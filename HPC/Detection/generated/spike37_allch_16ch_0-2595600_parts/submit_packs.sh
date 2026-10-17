#!/bin/bash
# Submits 3 packs that between them run all 16 one-channel parts of spike37_allch_16ch_0-2595600, each part on its own
# core (6, 5, 5 per pack); written by scripts/seed_job_parallel.py pack. The parts' own
# one-channel jobs must not be queued or running at the same time (two jobs would write one result file):
# this script refuses while any is.
# Run from the repo root on the cluster (/home/Student/s4699158/CNN).
#
# Cancel the one-channel parts:  squeue -u $USER -h -o "%i %j" | awk '$2 ~ /^spike37_allch_16ch_0-2595600__CH/ {print $1}' | xargs -r scancel
# Cancel the packs:  squeue -u $USER -h -o "%i %j" | awk '$2 ~ /^spike37_allch_16ch_0-2595600__pack/ {print $1}' | xargs -r scancel
# When every part is done, bring back HPC/Detection/generated/spike37_allch_16ch_0-2595600_parts/*.result.json and on the PC run:
#   python scripts/seed_job_parallel.py merge HPC/Detection/generated/spike37_allch_16ch_0-2595600.spec.json
set -euo pipefail

# read the queue first, outside the `if`: a failing squeue then stops the script (set -e) instead of
# reading as 'nothing queued'
QUEUED="$(squeue -u "$(id -un)" -h -o "%j")"
if printf '%s\n' "$QUEUED" | grep -q '^spike37_allch_16ch_0-2595600__CH'; then
    echo 'One-channel parts of this search are still queued or running. Cancel them first: the command is at the top of this script.'
    exit 1
fi

sbatch HPC/Detection/generated/spike37_allch_16ch_0-2595600_parts/spike37_allch_16ch_0-2595600__pack1of3.sh
sbatch HPC/Detection/generated/spike37_allch_16ch_0-2595600_parts/spike37_allch_16ch_0-2595600__pack2of3.sh
sbatch HPC/Detection/generated/spike37_allch_16ch_0-2595600_parts/spike37_allch_16ch_0-2595600__pack3of3.sh
