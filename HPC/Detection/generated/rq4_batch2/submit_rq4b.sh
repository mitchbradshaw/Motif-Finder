#!/bin/bash
# The RQ4 overnight sweep (scripts/rq4_overnight.py): four packs. The account runs three jobs at once, so the
# fourth waits in the queue until one finishes. Run from the repo root on the cluster (/home/Student/s4699158/CNN).
#
# Cancel the sweep:  squeue -u $USER -h -o "%i %j" | awk '$2 ~ /^rq4b_/ {print $1}' | xargs -r scancel
# Progress:          python scripts/rq4_overnight.py report --out HPC/Detection/generated/rq4_batch2
# Bring back:        every HPC/Detection/generated/rq4_batch2/**/*_out/return/ folder (keep the paths)
set -euo pipefail

# every channel array and model the tasks read must be here first: refuse, naming them, if not
MISSING=0
for F in DATA/derived/channels/L_LM_Jul_26_J_raw_fs10/CH0.npy DATA/derived/channels/L_LM_Jul_26_J_raw_fs10/CH1.npy DATA/derived/channels/L_LM_Jul_26_J_raw_fs10/CH2.npy DATA/derived/channels/L_LM_Jul_26_J_raw_fs10/CH3.npy DATA/derived/channels/L_LM_Jul_26_J_raw_fs10/CH4.npy DATA/derived/channels/M2_concat_fs1/CH0.npy DATA/derived/channels/M2_concat_fs1/CH1.npy DATA/derived/channels/M2_concat_fs1/CH10.npy DATA/derived/channels/M2_concat_fs1/CH11.npy DATA/derived/channels/M2_concat_fs1/CH12.npy DATA/derived/channels/M2_concat_fs1/CH13.npy DATA/derived/channels/M2_concat_fs1/CH14.npy DATA/derived/channels/M2_concat_fs1/CH15.npy DATA/derived/channels/M2_concat_fs1/CH2.npy DATA/derived/channels/M2_concat_fs1/CH3.npy DATA/derived/channels/M2_concat_fs1/CH4.npy DATA/derived/channels/M2_concat_fs1/CH5.npy DATA/derived/channels/M2_concat_fs1/CH6.npy DATA/derived/channels/M2_concat_fs1/CH7.npy DATA/derived/channels/M2_concat_fs1/CH8.npy DATA/derived/channels/M2_concat_fs1/CH9.npy DATA/derived/channels/M4_aug_concat_fs1/CH0.npy DATA/derived/channels/M4_aug_concat_fs1/CH1.npy DATA/derived/channels/M4_aug_concat_fs1/CH10.npy DATA/derived/channels/M4_aug_concat_fs1/CH11.npy DATA/derived/channels/M4_aug_concat_fs1/CH12.npy DATA/derived/channels/M4_aug_concat_fs1/CH13.npy DATA/derived/channels/M4_aug_concat_fs1/CH14.npy DATA/derived/channels/M4_aug_concat_fs1/CH15.npy DATA/derived/channels/M4_aug_concat_fs1/CH2.npy DATA/derived/channels/M4_aug_concat_fs1/CH3.npy DATA/derived/channels/M4_aug_concat_fs1/CH4.npy DATA/derived/channels/M4_aug_concat_fs1/CH5.npy DATA/derived/channels/M4_aug_concat_fs1/CH6.npy DATA/derived/channels/M4_aug_concat_fs1/CH7.npy DATA/derived/channels/M4_aug_concat_fs1/CH8.npy DATA/derived/channels/M4_aug_concat_fs1/CH9.npy MODELS/GADF_cnn.pth MODELS/GASF_cnn.pth MODELS/fusion_cnn_3.pth MODELS/recurrence_cnn.pth; do
    [ -f "$F" ] || { echo "missing: $F"; MISSING=$((MISSING + 1)); }
done
if [ "$MISSING" -gt 0 ]; then
    echo ">>> $MISSING input file(s) are not on the cluster: copy them to the same paths, then run this again"
    exit 1
fi

sbatch HPC/Detection/generated/rq4_batch2/rq4b_cpu1.sh
sbatch HPC/Detection/generated/rq4_batch2/rq4b_cpu2.sh
sbatch HPC/Detection/generated/rq4_batch2/rq4b_gpuA.sh
sbatch HPC/Detection/generated/rq4_batch2/rq4b_gpuB.sh
