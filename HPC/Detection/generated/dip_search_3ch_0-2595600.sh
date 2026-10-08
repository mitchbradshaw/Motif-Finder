#!/bin/bash
#SBATCH --job-name=dip_search_3ch_0-2595600
#SBATCH --chdir=/home/Student/s4699158/CNN
#SBATCH --output=/home/Student/s4699158/CNN/logs/dip_search_3ch_0-2595600_%j.out
#SBATCH --error=/home/Student/s4699158/CNN/logs/dip_search_3ch_0-2595600_%j.err
#SBATCH --time=00:20:00
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=4


echo "========================================"
echo "Job ID       : $SLURM_JOB_ID"
echo "Job name     : $SLURM_JOB_NAME"
echo "Node         : $SLURMD_NODENAME"
echo "Started      : $(date)"
echo "Working dir  : $(pwd)"
echo "========================================"

mkdir -p logs

source ~/miniconda3/etc/profile.d/conda.sh
conda activate aeon-env

python -m Working.discovery.seed_job --spec HPC/Detection/generated/dip_search_3ch_0-2595600.spec.json --out HPC/Detection/generated/dip_search_3ch_0-2595600.result.json

echo "========================================"
echo "Finished : $(date)"
echo "========================================"
