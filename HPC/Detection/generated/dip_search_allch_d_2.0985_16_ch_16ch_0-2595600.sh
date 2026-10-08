#!/bin/bash
#SBATCH --job-name=dip_search_allch_d_2.0985_16_ch_16ch_0-2595600
#SBATCH --chdir=/home/Student/s4699158/CNN
#SBATCH --output=/home/Student/s4699158/CNN/logs/dip_search_allch_d_2.0985_16_ch_16ch_0-2595600_%j.out
#SBATCH --error=/home/Student/s4699158/CNN/logs/dip_search_allch_d_2.0985_16_ch_16ch_0-2595600_%j.err
#SBATCH --time=00:20:00
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=4
# ---- what this job needs on the cluster (paths relative to --chdir; transfer with WinSCP) ----
# environment : conda env `aeon-env` (numpy, scipy, stumpy, aeon as the repo's requirements say)
# code        : the repo's own modules this job imports (git sync, or copy these files):
#     Adapters/__init__.py
#     Adapters/_sax_common.py
#     Adapters/base.py
#     Adapters/catalogue_classifier.py
#     Adapters/catalogue_cluster.py
#     Adapters/catalogue_cnn_score.py
#     Adapters/catalogue_gramian_fusion.py
#     Adapters/catalogue_gramian_gadf.py
#     Adapters/catalogue_gramian_gasf.py
#     Adapters/catalogue_gramian_recurrence.py
#     Adapters/catalogue_manual_labels.py
#     Adapters/catalogue_shape_cluster.py
#     Adapters/catalogue_window_images.py
#     Adapters/detection_dehshibi_spikes.py
#     Adapters/detection_drop_detection.py
#     Adapters/detection_freq_stft.py
#     Adapters/detection_matrix_profile.py
#     Adapters/detection_mp_motifs.py
#     Adapters/detection_rupture.py
#     Adapters/detection_sax_csax.py
#     Adapters/detection_sax_dsax.py
#     Adapters/detection_sax_psax.py
#     Adapters/detection_seed_matches.py
#     Adapters/detection_spike_v1.py
#     Adapters/detection_stage_encoding.py
#     Adapters/detection_summation_threshold.py
#     Adapters/detection_symbol_search.py
#     Adapters/detection_threshold.py
#     Adapters/detection_wavelet_scattering.py
#     Adapters/detection_wavelet_summation.py
#     Adapters/interrogation_event_shape.py
#     Adapters/interrogation_intervals.py
#     Adapters/preprocessing_bandpass.py
#     Adapters/preprocessing_detrend.py
#     Adapters/preprocessing_highpass.py
#     Adapters/preprocessing_invert.py
#     Adapters/preprocessing_lowpass.py
#     Adapters/preprocessing_sliding_windows.py
#     Adapters/preprocessing_surrogate.py
#     Adapters/preprocessing_trace_shape.py
#     Adapters/preprocessing_wavelet_bands.py
#     Adapters/preprocessing_wavelet_transform.py
#     Adapters/preprocessing_window_matrix.py
#     Adapters/preprocessing_window_pool.py
#     Adapters/registry.py
#     Pipelines/__init__.py
#     Pipelines/matrix_profile/__init__.py
#     Pipelines/matrix_profile/run_matrix_profile.py
#     Working/Catalogue/__init__.py
#     Working/Catalogue/aeon_classification/__init__.py
#     Working/Catalogue/aeon_classification/classification.py
#     Working/Catalogue/cnn/__init__.py
#     Working/Catalogue/cnn/apply_cnn.py
#     Working/Catalogue/cnn/cnn_fusion_prediction.py
#     Working/Catalogue/cnn/cnn_rangapur.py
#     Working/Catalogue/dendrogram/__init__.py
#     Working/Catalogue/dendrogram/dendrogram_cluster.py
#     Working/Catalogue/gramian/__init__.py
#     Working/Catalogue/gramian/gramian_calc.py
#     Working/Detection/__init__.py
#     Working/Detection/aeon_features/__init__.py
#     Working/Detection/aeon_features/transformations.py
#     Working/Detection/analysis/__init__.py
#     Working/Detection/analysis/dehshibi_authors.py
#     Working/Detection/analysis/dehshibi_detection_analysis.py
#     Working/Detection/analysis/entropy_analysis.py
#     Working/Detection/analysis/freq_analysis.py
#     Working/Detection/analysis/spike_analysis.py
#     Working/Detection/drop_motifs/__init__.py
#     Working/Detection/drop_motifs/cluster.py
#     Working/Detection/drop_motifs/detect.py
#     Working/Detection/drop_motifs/detect5.py
#     Working/Detection/drop_motifs/gradients.py
#     Working/Detection/drop_motifs/store.py
#     Working/Detection/matrix_profiling/__init__.py
#     Working/Detection/matrix_profiling/cost.py
#     Working/Detection/matrix_profiling/motif_groups.py
#     Working/Detection/rupture/__init__.py
#     Working/Detection/rupture/rupture_detect.py
#     Working/Detection/sax/__init__.py
#     Working/Detection/sax/csax_python/__init__.py
#     Working/Detection/sax/csax_python/csax.py
#     Working/Detection/sax/csax_python/csax_overlap.py
#     Working/Detection/sax/csax_python/meanshift/__init__.py
#     Working/Detection/sax/csax_python/meanshift/epanechfun.py
#     Working/Detection/sax/csax_python/meanshift/gaussfun.py
#     Working/Detection/sax/csax_python/meanshift/hg_meanshift_cluster.py
#     Working/Detection/sax/csax_python/normal_cutlines.py
#     Working/Detection/sax/csax_python/timeseries2symbol.py
#     Working/Detection/sax/csax_python/ts_paa.py
#     Working/Detection/sax/dsax_python/__init__.py
#     Working/Detection/sax/dsax_python/dsax.py
#     Working/Detection/sax/dsax_python/trend_estimators.py
#     Working/Detection/sax/psax_python/__init__.py
#     Working/Detection/sax/psax_python/kde.py
#     Working/Detection/sax/psax_python/kmeanspp.py
#     Working/Detection/sax/psax_python/lloydmax.py
#     Working/Detection/sax/psax_python/psax.py
#     Working/Detection/sax/psax_python/psax_overlap.py
#     Working/Detection/wavelet/__init__.py
#     Working/Detection/wavelet/plot_scattering.py
#     Working/Detection/wavelet/scattering_transform.py
#     Working/Preprocessing/__init__.py
#     Working/Preprocessing/detrend.py
#     Working/Preprocessing/manage_data/__init__.py
#     Working/Preprocessing/manage_data/load_data.py
#     Working/Preprocessing/window_matrix/__init__.py
#     Working/Preprocessing/window_matrix/build.py
#     Working/Preprocessing/window_matrix/cost.py
#     Working/Preprocessing/window_matrix/matrix_calc.py
#     Working/__init__.py
#     Working/block_cost.py
#     Working/chain_validation.py
#     Working/config.py
#     Working/cross_channel.py
#     Working/database/__init__.py
#     Working/database/adjudications.py
#     Working/database/matrix_profile_store.py
#     Working/database/queries.py
#     Working/database/runs.py
#     Working/database/schema.py
#     Working/database/similarity.py
#     Working/database/vocabulary.py
#     Working/database/window_matrix_store.py
#     Working/discovery/__init__.py
#     Working/discovery/channels.py
#     Working/discovery/divergence.py
#     Working/discovery/matching.py
#     Working/discovery/seed_job.py
#     Working/discovery/seeded_search.py
#     Working/discovery/spans.py
#     Working/distances.py
#     Working/hpc/__init__.py
#     Working/hpc/job_export.py
#     Working/interrogation/__init__.py
#     Working/interrogation/event_shape.py
#     Working/interrogation/intervals.py
#     Working/library/__init__.py
#     Working/library/dedupe.py
#     Working/library/features.py
#     Working/library/grouping/__init__.py
#     Working/library/grouping/bases.py
#     Working/library/grouping/engine.py
#     Working/library/grouping/methods/__init__.py
#     Working/library/grouping/methods/ward.py
#     Working/library/identity.py
#     Working/library/importers/__init__.py
#     Working/library/importers/event_store.py
#     Working/library/matching.py
#     Working/library/revisions.py
#     Working/library/rose_reference.py
#     Working/library/verdicts.py
#     Working/library/view_filter.py
#     Working/manifest.py
#     Working/recipes.py
#     Working/registration/__init__.py
#     Working/registration/core.py
#     Working/registration/excerpt.py
#     Working/registration/kinds.py
#     Working/registration/settings.py
#     Working/review/__init__.py
#     Working/review/artifact_queue.py
#     Working/review/queue_state.py
#     Working/review/queues.py
#     Working/side_inputs.py
#     Working/training/__init__.py
#     Working/training/blind.py
#     Working/training/cnn_job.py
#     Working/training/full_ward.py
#     Working/training/hpc_import.py
#     Working/training/metrics.py
#     Working/training/paired.py
#     Working/training/pool.py
#     Working/training/reference.py
#     Working/training/shape.py
#     Working/training/shape_cnn.py
#     Working/training/shape_forest.py
#     Working/training/store.py
#     Working/training/windows.py
#     Working/types/__init__.py
#     Working/types/encoding.py
#     Working/types/grouping.py
#     Working/types/model.py
#     Working/types/scores.py
#     Working/types/signal.py
#     Working/types/spanset.py
#     Working/types/windowset.py
#     Working/units.py
# inputs      : files the job reads:
#     HPC/Detection/generated/dip_search_allch_d_2.0985_16_ch_16ch_0-2595600.spec.json
#     DATA/derived/channels/M2_aug_concat_fs1/CH1.npy
#     DATA/derived/channels/M2_aug_concat_fs1/CH5.npy
#     DATA/derived/channels/M2_aug_concat_fs1/CH6.npy
#     DATA/derived/channels/M2_aug_concat_fs1/CH0.npy
#     DATA/derived/channels/M2_aug_concat_fs1/CH2.npy
#     DATA/derived/channels/M2_aug_concat_fs1/CH3.npy
#     DATA/derived/channels/M2_aug_concat_fs1/CH4.npy
#     DATA/derived/channels/M2_aug_concat_fs1/CH7.npy
#     DATA/derived/channels/M2_aug_concat_fs1/CH8.npy
#     DATA/derived/channels/M2_aug_concat_fs1/CH9.npy
#     DATA/derived/channels/M2_aug_concat_fs1/CH10.npy
#     DATA/derived/channels/M2_aug_concat_fs1/CH11.npy
#     DATA/derived/channels/M2_aug_concat_fs1/CH12.npy
#     DATA/derived/channels/M2_aug_concat_fs1/CH13.npy
#     DATA/derived/channels/M2_aug_concat_fs1/CH14.npy
#     DATA/derived/channels/M2_aug_concat_fs1/CH15.npy
# outputs     : files the job writes (bring back):
#     HPC/Detection/generated/dip_search_allch_d_2.0985_16_ch_16ch_0-2595600.result.json
# ---------------------------------------------------------------------------------------------

# Chain position, incremented on each resubmit: the job writes its result after
# every channel and every 10 draws, and continues it from where the
# wall cut it. Capped at 30 so a bug that always reads incomplete stops.
CHAIN_INDEX="${1:-1}"
MAX_CHAIN=30

echo "========================================"
echo "Job ID       : $SLURM_JOB_ID"
echo "Job name     : $SLURM_JOB_NAME"
echo "Node         : $SLURMD_NODENAME"
echo "Chain        : $CHAIN_INDEX / $MAX_CHAIN"
echo "Started      : $(date)"
echo "Working dir  : $(pwd)"
echo "========================================"

mkdir -p logs

source ~/miniconda3/etc/profile.d/conda.sh
conda activate aeon-env

python -m Working.discovery.seed_job --spec HPC/Detection/generated/dip_search_allch_d_2.0985_16_ch_16ch_0-2595600.spec.json --out HPC/Detection/generated/dip_search_allch_d_2.0985_16_ch_16ch_0-2595600.result.json

echo "========================================"
echo "Run finished : $(date)"

python -m Working.discovery.seed_job --status HPC/Detection/generated/dip_search_allch_d_2.0985_16_ch_16ch_0-2595600.result.json
STATUS=$?

if [ "$STATUS" -eq 0 ]; then
    echo ">>> Result complete: HPC/Detection/generated/dip_search_allch_d_2.0985_16_ch_16ch_0-2595600.result.json -- bring it back and import it on the Seed page."
elif [ "$CHAIN_INDEX" -ge "$MAX_CHAIN" ]; then
    echo ">>> Work remains but the chain cap ($MAX_CHAIN) is reached -- stopping."
    echo ">>> Resubmit manually if this is expected: sbatch HPC/Detection/generated/dip_search_allch_d_2.0985_16_ch_16ch_0-2595600.sh 1"
else
    NEXT=$((CHAIN_INDEX + 1))
    echo ">>> Work remains -- submitting job $NEXT of $MAX_CHAIN ..."
    sbatch HPC/Detection/generated/dip_search_allch_d_2.0985_16_ch_16ch_0-2595600.sh "$NEXT"
    echo ">>> Submitted. Monitor with: squeue -u $USER"
fi

echo "Finished     : $(date)"
echo "========================================"
