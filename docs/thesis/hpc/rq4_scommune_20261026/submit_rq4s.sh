#!/bin/bash
# The RQ4 overnight sweep (scripts/rq4_overnight.py): four packs. The account runs three jobs at once, so the
# fourth waits in the queue until one finishes. Run from the repo root on the cluster (/home/Student/s4699158/CNN).
#
# Cancel the sweep:  squeue -u $USER -h -o "%i %j" | awk '$2 ~ /^rq4s_/ {print $1}' | xargs -r scancel
# Progress:          python scripts/rq4_overnight.py report --out docs/thesis/hpc/rq4_scommune_20261026
# Bring back:        every docs/thesis/hpc/rq4_scommune_20261026/**/*_out/return/ folder (keep the paths)
set -euo pipefail

# every channel array and model the tasks read must be here first: refuse, naming them, if not
MISSING=0
for F in DATA/derived/channels/Schizophyllum_commune_fs1/CH0.npy DATA/derived/channels/Schizophyllum_commune_fs1/CH1.npy DATA/derived/channels/Schizophyllum_commune_fs1/CH2.npy DATA/derived/channels/Schizophyllum_commune_fs1/CH3.npy DATA/derived/channels/Schizophyllum_commune_fs1/CH4.npy DATA/derived/channels/Schizophyllum_commune_fs1/CH5.npy DATA/derived/channels/Schizophyllum_commune_fs1/CH6.npy MODELS/GADF_cnn.pth MODELS/GASF_cnn.pth MODELS/fusion_cnn_3.pth MODELS/recurrence_cnn.pth; do
    [ -f "$F" ] || { echo "missing: $F"; MISSING=$((MISSING + 1)); }
done
if [ "$MISSING" -gt 0 ]; then
    echo ">>> $MISSING input file(s) are not on the cluster: copy them to the same paths, then run this again"
    exit 1
fi

sbatch docs/thesis/hpc/rq4_scommune_20261026/rq4s_cpu1.sh
sbatch docs/thesis/hpc/rq4_scommune_20261026/rq4s_cpu2.sh
sbatch docs/thesis/hpc/rq4_scommune_20261026/rq4s_gpuA.sh
sbatch docs/thesis/hpc/rq4_scommune_20261026/rq4s_gpuB.sh
