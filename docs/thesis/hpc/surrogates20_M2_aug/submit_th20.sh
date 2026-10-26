#!/bin/bash
# The RQ4 overnight sweep (scripts/rq4_overnight.py): four packs. The account runs three jobs at once, so the
# fourth waits in the queue until one finishes. Run from the repo root on the cluster (/home/Student/s4699158/CNN).
#
# Cancel the sweep:  squeue -u $USER -h -o "%i %j" | awk '$2 ~ /^th20_/ {print $1}' | xargs -r scancel
# Progress:          python scripts/rq4_overnight.py report --out docs/thesis/hpc/surrogates20_M2_aug
# Bring back:        every docs/thesis/hpc/surrogates20_M2_aug/**/*_out/return/ folder (keep the paths)
set -euo pipefail

sbatch docs/thesis/hpc/surrogates20_M2_aug/th20_cpu1.sh
sbatch docs/thesis/hpc/surrogates20_M2_aug/th20_cpu2.sh
sbatch docs/thesis/hpc/surrogates20_M2_aug/th20_gpuA.sh
sbatch docs/thesis/hpc/surrogates20_M2_aug/th20_gpuB.sh
