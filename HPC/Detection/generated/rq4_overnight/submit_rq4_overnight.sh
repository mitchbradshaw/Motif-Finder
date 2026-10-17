#!/bin/bash
# The RQ4 overnight sweep (scripts/rq4_overnight.py): four packs. The account runs three jobs at once, so the
# fourth waits in the queue until one finishes. Run from the repo root on the cluster (/home/Student/s4699158/CNN).
#
# Cancel the sweep:  squeue -u $USER -h -o "%i %j" | awk '$2 ~ /^rq4_/ {print $1}' | xargs -r scancel
# Progress:          python scripts/rq4_overnight.py report
# Bring back:        every HPC/Detection/generated/rq4_overnight/*_out/return/ folder (keep the paths)
set -euo pipefail

sbatch HPC/Detection/generated/rq4_overnight/rq4_cpu1.sh
sbatch HPC/Detection/generated/rq4_overnight/rq4_cpu2.sh
sbatch HPC/Detection/generated/rq4_overnight/rq4_gpuA.sh
sbatch HPC/Detection/generated/rq4_overnight/rq4_gpuB.sh
