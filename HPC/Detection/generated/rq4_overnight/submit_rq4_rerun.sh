#!/bin/bash
# Re-runs the 47 refused tasks of the RQ4 overnight sweep (scripts/rq4_rerun.py) as one CPU pack.
# Needs a parquet engine in the CPU environment: the overnight refusals were 'Unable to find a usable
# engine' (fastparquet, installed 2026-10-18). Run from the repo root on the cluster (/home/Student/s4699158/CNN).
#
# Cancel:     squeue -u $USER -h -o "%i %j" | awk '$2 == "rq4_rerun" {print $1}' | xargs -r scancel
# Progress:   python scripts/rq4_overnight.py report
# Bring back: the return/task<i>/ folders named in HPC/Detection/generated/rq4_overnight/tasks_rq4_rerun.txt
# The job checks for the parquet engine itself, in the environment its tasks run in.
set -euo pipefail

sbatch HPC/Detection/generated/rq4_overnight/rq4_rerun.sh
