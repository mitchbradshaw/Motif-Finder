#!/bin/bash
#SBATCH --job-name=b2cnn_fusion
#SBATCH --chdir=/home/Student/s4699158/CNN
#SBATCH --output=/home/Student/s4699158/CNN/logs/b2cnn_fusion_c83b02ad_%j.out
#SBATCH --error=/home/Student/s4699158/CNN/logs/b2cnn_fusion_c83b02ad_%j.err
#SBATCH --time=00:20:00
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:a100
#SBATCH --partition=a100

# fixup-ai: arm B.2 (cluster labels, trace shape) with a CNN -- CNN · fusion · EfficientNet-B0 · 12 epochs
# job directory: HPC/Training/generated/b2cnn_fusion_c83b02ad  (recipe c83b02ad)
# estimate: about 1.0 h of work in all, so about 4 chained job(s) of 20 min -- an estimate, not a measurement
# Resumable: the run stops 3 min before the wall clock, checkpointed; the status
# check's exit code resubmits this script until the job is complete (at most 10 jobs).
CHAIN_INDEX="${1:-1}"
MAX_CHAIN=10

echo "========================================"
echo "Job ID       : $SLURM_JOB_ID"
echo "Node         : $SLURMD_NODENAME"
echo "Chain        : $CHAIN_INDEX / $MAX_CHAIN"
echo "Started      : $(date)"
echo "Working dir  : $(pwd)"
echo "========================================"

mkdir -p logs
module load cuda/12.2
source ~/miniconda3/etc/profile.d/conda.sh
conda activate torch_env

# the environment, checked before an hour is spent: a missing package is named here
python -c "import torch, torchvision, numpy, scipy, skimage, PIL, matplotlib; print('environment ok')" || { echo ">>> conda env torch_env lacks a package (above): conda install -n torch_env <package>"; exit 4; }

python -m Working.training cnn-run --job HPC/Training/generated/b2cnn_fusion_c83b02ad --workers "$SLURM_CPUS_PER_TASK" --deadline-min 17
RUN=$?
if [ "$RUN" -ne 0 ]; then
    # a crash is not "work remains": resubmitting would crash again -- stop and read the .err log
    echo ">>> The run failed (exit $RUN) -- stopping the chain; see logs/b2cnn_fusion_c83b02ad_$SLURM_JOB_ID.err"
    exit "$RUN"
fi

python -m Working.training cnn-status --job HPC/Training/generated/b2cnn_fusion_c83b02ad
STATUS=$?

if [ "$STATUS" -eq 0 ]; then
    echo ">>> Complete. Copy HPC/Training/generated/b2cnn_fusion_c83b02ad/out/ back into the same place on your machine, then run:"
    echo ">>>     python -m Working.training import-results HPC/Training/generated/b2cnn_fusion_c83b02ad"
elif [ "$STATUS" -ge 3 ]; then
    echo ">>> The job could not be read (exit $STATUS) -- stopping the chain."
    exit "$STATUS"
elif [ "$CHAIN_INDEX" -ge "$MAX_CHAIN" ]; then
    echo ">>> Work remains but the chain cap ($MAX_CHAIN) is reached -- stopping."
    echo ">>> Resubmit by hand to continue from the last checkpoint: sbatch HPC/Training/generated/b2cnn_fusion_c83b02ad/b2cnn_fusion_c83b02ad.sh 1"
else
    NEXT=$((CHAIN_INDEX + 1))
    echo ">>> Work remains -- submitting job $NEXT of $MAX_CHAIN ..."
    sbatch HPC/Training/generated/b2cnn_fusion_c83b02ad/b2cnn_fusion_c83b02ad.sh "$NEXT"
fi
echo "Finished     : $(date)"
