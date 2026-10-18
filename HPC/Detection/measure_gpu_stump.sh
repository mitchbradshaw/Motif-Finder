#!/bin/bash
#SBATCH --job-name=gpu_stump_check
#SBATCH --chdir=/home/Student/s4699158/CNN
#SBATCH --output=/home/Student/s4699158/CNN/logs/gpu_stump_check_%j.out
#SBATCH --error=/home/Student/s4699158/CNN/logs/gpu_stump_check_%j.err
#SBATCH --time=00:20:00
#SBATCH --gres=gpu:a100
#SBATCH --partition=a100
#SBATCH --cpus-per-task=8

# Round A_2 (P2): stump (CPU) against gpu_stump (the a100) on synthetic coloured series, so the
# researcher can decide whether `backend` may leave the step cache's key. Thin on purpose: the
# measurement is scripts/measure_gpu_stump.py. Read the .out log, or logs/gpu_stump_check.json.
#   sbatch HPC/Detection/measure_gpu_stump.sh            (compare at 50k and 200k samples)
#   then, to time one whole channel on the GPU alone:
#   sbatch --wrap "python scripts/measure_gpu_stump.py --gpu-only 2596000" ... (or edit the line below)

echo "Job $SLURM_JOB_ID on $SLURMD_NODENAME · $(date)"
mkdir -p logs
module load cuda/12.2
source ~/miniconda3/etc/profile.d/conda.sh
conda activate torch_env

python scripts/measure_gpu_stump.py --sizes 50000,200000 --out logs/gpu_stump_check.json
echo "Finished $(date)"
