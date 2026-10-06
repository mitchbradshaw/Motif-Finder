#!/bin/bash
#SBATCH --job-name=ward_full_pool
#SBATCH --chdir=/home/Student/s4699158/CNN
#SBATCH --output=/home/Student/s4699158/CNN/logs/ward_full_ee39ae58_%j.out
#SBATCH --error=/home/Student/s4699158/CNN/logs/ward_full_ee39ae58_%j.err
#SBATCH --time=00:20:00
#SBATCH --cpus-per-task=4
#SBATCH --partition=largecpu
#SBATCH --mem=10G

# fixup-ai: Ward over EVERY training window of the pool (29,370 windows) -- the same Ward as the
# Shape clustering block (the Library's method), the same tree artifact.
# job directory: HPC/Training/generated/ward_full_ee39ae58  (recipe ee39ae58)
# memory: 2 x 8 x n(n-1)/2 bytes (the condensed float64 distances and scipy's working copy) + the vectors (n x 256 x 12 bytes) + 1.5 GB for Python, x 1.2 -> 10 GB for n = 29,370
# time: about 2.1 min (AG's 57 s at 20,000 scaled by n squared -- an estimate), x 3 for another machine, clamped to the account's 20 min
# If sbatch answers "Memory specification can not be satisfied": run  sinfo -o "%P %m %c"  and
# pick a partition whose memory per node (MB) exceeds 10 GB; this account refused --mem on
# `cpu` before (HPC/README.md).

echo "Job ID : $SLURM_JOB_ID   Node : $SLURMD_NODENAME   Started : $(date)"
mkdir -p logs
source ~/miniconda3/etc/profile.d/conda.sh
conda activate aeon-env

# the environment, checked before an hour is spent: a missing package is named here
python -c "import numpy, scipy, pandas; print('environment ok')" || { echo ">>> conda env aeon-env lacks a package (above): conda install -n aeon-env <package>"; exit 4; }

python -m Working.training ward-run --job HPC/Training/generated/ward_full_ee39ae58
python -m Working.training ward-status --job HPC/Training/generated/ward_full_ee39ae58
STATUS=$?
if [ "$STATUS" -eq 0 ]; then
    echo ">>> Complete. Copy HPC/Training/generated/ward_full_ee39ae58/out/ back into the same place on your machine, then run:"
    echo ">>>     python -m Working.training import-results HPC/Training/generated/ward_full_ee39ae58"
fi
echo "Finished : $(date)"
exit "$STATUS"
