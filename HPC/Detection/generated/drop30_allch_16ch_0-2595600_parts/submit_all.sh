#!/bin/bash
# Submits the 16 one-channel parts of drop30_allch_16ch_0-2595600 at once (scripts/seed_job_parallel.py split).
# The channels are independent: SLURM's own queue decides how many run together. Each part is the
# Seed page's chained seed job for one channel, so it resubmits itself if a channel outlasts the wall.
# Run from the repo root on the cluster (/home/Student/s4699158/CNN).
#
# Cancel them all:  squeue -u $USER -h -o "%i %j" | awk '$2 ~ /^drop30_allch_16ch_0-2595600__/ {print $1}' | xargs -r scancel
# When every part is done, bring back HPC/Detection/generated/drop30_allch_16ch_0-2595600_parts/*.result.json and on the PC run:
#   python scripts/seed_job_parallel.py merge HPC/Detection/generated/drop30_allch_16ch_0-2595600.spec.json
# then import the merged result on the Seed page.
set -euo pipefail

sbatch HPC/Detection/generated/drop30_allch_16ch_0-2595600_parts/drop30_allch_16ch_0-2595600__CH2_A1.sh
sbatch HPC/Detection/generated/drop30_allch_16ch_0-2595600_parts/drop30_allch_16ch_0-2595600__CH1_A1.sh
sbatch HPC/Detection/generated/drop30_allch_16ch_0-2595600_parts/drop30_allch_16ch_0-2595600__CH3_A2.sh
sbatch HPC/Detection/generated/drop30_allch_16ch_0-2595600_parts/drop30_allch_16ch_0-2595600__CH4_A2.sh
sbatch HPC/Detection/generated/drop30_allch_16ch_0-2595600_parts/drop30_allch_16ch_0-2595600__CH5_B1.sh
sbatch HPC/Detection/generated/drop30_allch_16ch_0-2595600_parts/drop30_allch_16ch_0-2595600__CH6_B1.sh
sbatch HPC/Detection/generated/drop30_allch_16ch_0-2595600_parts/drop30_allch_16ch_0-2595600__CH7_B2.sh
sbatch HPC/Detection/generated/drop30_allch_16ch_0-2595600_parts/drop30_allch_16ch_0-2595600__CH8_B2.sh
sbatch HPC/Detection/generated/drop30_allch_16ch_0-2595600_parts/drop30_allch_16ch_0-2595600__CH9_C1.sh
sbatch HPC/Detection/generated/drop30_allch_16ch_0-2595600_parts/drop30_allch_16ch_0-2595600__CH10_C1.sh
sbatch HPC/Detection/generated/drop30_allch_16ch_0-2595600_parts/drop30_allch_16ch_0-2595600__CH11_C2.sh
sbatch HPC/Detection/generated/drop30_allch_16ch_0-2595600_parts/drop30_allch_16ch_0-2595600__CH12_C2.sh
sbatch HPC/Detection/generated/drop30_allch_16ch_0-2595600_parts/drop30_allch_16ch_0-2595600__CH13_D1.sh
sbatch HPC/Detection/generated/drop30_allch_16ch_0-2595600_parts/drop30_allch_16ch_0-2595600__CH14_D1.sh
sbatch HPC/Detection/generated/drop30_allch_16ch_0-2595600_parts/drop30_allch_16ch_0-2595600__CH15_D2.sh
sbatch HPC/Detection/generated/drop30_allch_16ch_0-2595600_parts/drop30_allch_16ch_0-2595600__CH16_D2.sh
