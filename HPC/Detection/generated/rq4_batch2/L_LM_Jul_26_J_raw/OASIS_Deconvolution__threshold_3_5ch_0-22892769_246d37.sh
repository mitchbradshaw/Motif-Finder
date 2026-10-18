#!/bin/bash
#SBATCH --job-name=OASIS_Deconvolution__threshold_3_5ch_0-22892769_246d37
#SBATCH --chdir=/home/Student/s4699158/CNN
#SBATCH --output=/home/Student/s4699158/CNN/logs/OASIS_Deconvolution__threshold_3_5ch_0-22892769_246d37_%A_%a.out
#SBATCH --error=/home/Student/s4699158/CNN/logs/OASIS_Deconvolution__threshold_3_5ch_0-22892769_246d37_%A_%a.err
#SBATCH --time=00:20:00
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=8
#SBATCH --array=0-4
# ---- what this job needs on the cluster (paths relative to --chdir; transfer with WinSCP) ----
# environment : conda env `aeon-env` (numpy, scipy, stumpy, aeon as the repo's requirements say)
# code        : the repo's own modules this job imports (git sync, or copy these files):
#     Adapters/__init__.py
#     Adapters/_sax_common.py
#     Adapters/base.py
#     Adapters/catalogue_classifier.py
#     Adapters/catalogue_cluster.py
#     Adapters/catalogue_cnn_score.py
#     Adapters/catalogue_cnn_window_scores.py
#     Adapters/catalogue_event_windows.py
#     Adapters/catalogue_gramian_fusion.py
#     Adapters/catalogue_gramian_gadf.py
#     Adapters/catalogue_gramian_gasf.py
#     Adapters/catalogue_gramian_recurrence.py
#     Adapters/catalogue_manual_labels.py
#     Adapters/catalogue_minirocket.py
#     Adapters/catalogue_multiscale_entropy.py
#     Adapters/catalogue_shape_cluster.py
#     Adapters/catalogue_shape_families.py
#     Adapters/catalogue_snippets.py
#     Adapters/catalogue_window_images.py
#     Adapters/detection_cwt_ridges.py
#     Adapters/detection_deconvolve.py
#     Adapters/detection_dehshibi_spikes.py
#     Adapters/detection_drop_detection.py
#     Adapters/detection_fluss.py
#     Adapters/detection_freq_stft.py
#     Adapters/detection_impulse_events.py
#     Adapters/detection_matrix_profile.py
#     Adapters/detection_mp_motifs.py
#     Adapters/detection_noise_threshold.py
#     Adapters/detection_pan_matrix_profile.py
#     Adapters/detection_rupture.py
#     Adapters/detection_sax_csax.py
#     Adapters/detection_sax_dsax.py
#     Adapters/detection_sax_psax.py
#     Adapters/detection_seed_matches.py
#     Adapters/detection_signal_threshold.py
#     Adapters/detection_spike_v1.py
#     Adapters/detection_stage_encoding.py
#     Adapters/detection_summation_threshold.py
#     Adapters/detection_symbol_search.py
#     Adapters/detection_threshold.py
#     Adapters/detection_wavelet_scattering.py
#     Adapters/detection_wavelet_summation.py
#     Adapters/interrogation_cycle_shapes.py
#     Adapters/interrogation_event_families.py
#     Adapters/interrogation_event_shape.py
#     Adapters/interrogation_intervals.py
#     Adapters/interrogation_trains.py
#     Adapters/preprocessing_bandpass.py
#     Adapters/preprocessing_beads.py
#     Adapters/preprocessing_decompose.py
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
#     Working/Catalogue/cnn/window_scores.py
#     Working/Catalogue/dendrogram/__init__.py
#     Working/Catalogue/dendrogram/dendrogram_cluster.py
#     Working/Catalogue/event_windows.py
#     Working/Catalogue/gramian/__init__.py
#     Working/Catalogue/gramian/gramian_calc.py
#     Working/Catalogue/minirocket.py
#     Working/Catalogue/multiscale_entropy.py
#     Working/Catalogue/shape_families.py
#     Working/Detection/__init__.py
#     Working/Detection/aeon_features/__init__.py
#     Working/Detection/aeon_features/transformations.py
#     Working/Detection/analysis/__init__.py
#     Working/Detection/analysis/data_analysis.py
#     Working/Detection/analysis/dehshibi_authors.py
#     Working/Detection/analysis/dehshibi_detection_analysis.py
#     Working/Detection/analysis/entropy_analysis.py
#     Working/Detection/analysis/freq_analysis.py
#     Working/Detection/analysis/noise_level.py
#     Working/Detection/analysis/spike_analysis.py
#     Working/Detection/cwt_ridges.py
#     Working/Detection/deconvolution/__init__.py
#     Working/Detection/deconvolution/impulses.py
#     Working/Detection/deconvolution/oasis.py
#     Working/Detection/drop_motifs/__init__.py
#     Working/Detection/drop_motifs/cluster.py
#     Working/Detection/drop_motifs/detect.py
#     Working/Detection/drop_motifs/detect5.py
#     Working/Detection/drop_motifs/gradients.py
#     Working/Detection/drop_motifs/store.py
#     Working/Detection/matrix_profiling/__init__.py
#     Working/Detection/matrix_profiling/cost.py
#     Working/Detection/matrix_profiling/fluss.py
#     Working/Detection/matrix_profiling/motif_groups.py
#     Working/Detection/matrix_profiling/mp_chunks.py
#     Working/Detection/matrix_profiling/pan.py
#     Working/Detection/matrix_profiling/snippets.py
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
#     Working/Preprocessing/beads.py
#     Working/Preprocessing/decompose.py
#     Working/Preprocessing/detrend.py
#     Working/Preprocessing/manage_data/__init__.py
#     Working/Preprocessing/manage_data/load_data.py
#     Working/Preprocessing/window_matrix/__init__.py
#     Working/Preprocessing/window_matrix/build.py
#     Working/Preprocessing/window_matrix/cost.py
#     Working/Preprocessing/window_matrix/matrix_calc.py
#     Working/__init__.py
#     Working/background_null.py
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
#     Working/discovery/chain_job.py
#     Working/discovery/channels.py
#     Working/discovery/divergence.py
#     Working/discovery/fanout.py
#     Working/discovery/matching.py
#     Working/discovery/routing.py
#     Working/discovery/spans.py
#     Working/discovery/windowed.py
#     Working/distances.py
#     Working/execution.py
#     Working/hpc/__init__.py
#     Working/hpc/job_export.py
#     Working/interrogation/__init__.py
#     Working/interrogation/cycle_shapes.py
#     Working/interrogation/event_shape.py
#     Working/interrogation/intervals.py
#     Working/interrogation/trains.py
#     Working/library/__init__.py
#     Working/library/coherence.py
#     Working/library/dedupe.py
#     Working/library/features.py
#     Working/library/grouping/__init__.py
#     Working/library/grouping/bases.py
#     Working/library/grouping/engine.py
#     Working/library/grouping/methods/__init__.py
#     Working/library/grouping/methods/hdbscan.py
#     Working/library/grouping/methods/kshape.py
#     Working/library/grouping/methods/ward.py
#     Working/library/grouping/tree.py
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
#     Working/review/family_queue.py
#     Working/review/queue_state.py
#     Working/review/queues.py
#     Working/run_groups.py
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
#     HPC/Detection/generated/rq4_batch2/L_LM_Jul_26_J_raw/OASIS_Deconvolution__threshold_3_5ch_0-22892769_246d37.chain.json
#     DATA/derived/channels/L_LM_Jul_26_J_raw_fs10/CH0.npy
#     DATA/derived/channels/L_LM_Jul_26_J_raw_fs10/CH1.npy
#     DATA/derived/channels/L_LM_Jul_26_J_raw_fs10/CH2.npy
#     DATA/derived/channels/L_LM_Jul_26_J_raw_fs10/CH3.npy
#     DATA/derived/channels/L_LM_Jul_26_J_raw_fs10/CH4.npy
# outputs     : files the job writes (bring back):
#     HPC/Detection/generated/rq4_batch2/L_LM_Jul_26_J_raw/OASIS_Deconvolution__threshold_3_5ch_0-22892769_246d37_out/return/
# ---------------------------------------------------------------------------------------------

# Round A_2 (P2): a Discovery template run, one array task per channel (5 in all). Each task
# runs the real chain and its 1 null draw(s) on a scratch database and writes
#     HPC/Detection/generated/rq4_batch2/L_LM_Jul_26_J_raw/OASIS_Deconvolution__threshold_3_5ch_0-22892769_246d37_out/return/task<i>/   (result.json and step_cache/) -- bring that folder back.
# Wall 20 min on cpu (UNVERIFIED: the conservative floor until Working/config.py records this partition's limit). The task stops itself after 1020 s
# between steps, draws or profile blocks; `timeout` ends it at 1110 s inside a step. While its
# result reads incomplete it resubmits ITSELF (sbatch --array=<task>), at most 60 jobs; two
# jobs in a row that make no progress stop it with the reason.
CHAIN_INDEX="${1:-1}"
MAX_CHAIN=60
TASK="${SLURM_ARRAY_TASK_ID:-0}"

echo "========================================"
echo "Job ID       : $SLURM_JOB_ID (array task $TASK)"
echo "Job name     : $SLURM_JOB_NAME"
echo "Node         : $SLURMD_NODENAME"
echo "Chain        : $CHAIN_INDEX / $MAX_CHAIN"
echo "Started      : $(date)"
echo "Working dir  : $(pwd)"
echo "========================================"

mkdir -p logs

source ~/miniconda3/etc/profile.d/conda.sh
conda activate aeon-env

# numba (stumpy's engine) and BLAS would otherwise size their thread pools from the NODE's cores, not this
# job's allocation, and oversubscribe the 8 CPUs it was given
export NUMBA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"

timeout --signal=TERM 1110 python -m Working.discovery.chain_job --spec HPC/Detection/generated/rq4_batch2/L_LM_Jul_26_J_raw/OASIS_Deconvolution__threshold_3_5ch_0-22892769_246d37.chain.json --out HPC/Detection/generated/rq4_batch2/L_LM_Jul_26_J_raw/OASIS_Deconvolution__threshold_3_5ch_0-22892769_246d37_out --task "$TASK" --budget-s 1020
RC=$?

echo "========================================"
echo "Run finished : $(date) (exit $RC)"

if [ "$RC" -eq 124 ]; then
    echo ">>> The budget ran out inside a step: stopped before the wall. The next job continues from this task's cache."
elif [ "$RC" -ne 0 ]; then
    echo ">>> Task $TASK stopped (exit $RC) -- NOT resubmitting."
    if [ "$RC" -eq 2 ]; then
        echo ">>> Exit 2 is 'unrecognized arguments': the cluster's Working/discovery/chain_job.py is older than this script."
        echo ">>> Pull the repo on the cluster (git pull) or copy Working/ across, then: sbatch --array=$TASK HPC/Detection/generated/rq4_batch2/L_LM_Jul_26_J_raw/OASIS_Deconvolution__threshold_3_5ch_0-22892769_246d37.sh $CHAIN_INDEX"
    else
        echo ">>> Read HPC/Detection/generated/rq4_batch2/L_LM_Jul_26_J_raw/OASIS_Deconvolution__threshold_3_5ch_0-22892769_246d37_out/return/task$TASK/result.json ('error') and the .err log; when fixed: sbatch --array=$TASK HPC/Detection/generated/rq4_batch2/L_LM_Jul_26_J_raw/OASIS_Deconvolution__threshold_3_5ch_0-22892769_246d37.sh $CHAIN_INDEX"
    fi
    exit $RC
fi

python -m Working.discovery.chain_job --status --out HPC/Detection/generated/rq4_batch2/L_LM_Jul_26_J_raw/OASIS_Deconvolution__threshold_3_5ch_0-22892769_246d37_out --task "$TASK"
STATUS=$?

if [ "$STATUS" -eq 0 ]; then
    echo ">>> Task $TASK complete: HPC/Detection/generated/rq4_batch2/L_LM_Jul_26_J_raw/OASIS_Deconvolution__threshold_3_5ch_0-22892769_246d37_out/return/task$TASK/ -- bring HPC/Detection/generated/rq4_batch2/L_LM_Jul_26_J_raw/OASIS_Deconvolution__threshold_3_5ch_0-22892769_246d37_out/return/ back when every task is."
elif [ "$STATUS" -ne 1 ]; then
    echo ">>> Task $TASK cannot continue (status $STATUS): see 'error' in HPC/Detection/generated/rq4_batch2/L_LM_Jul_26_J_raw/OASIS_Deconvolution__threshold_3_5ch_0-22892769_246d37_out/return/task$TASK/result.json -- NOT resubmitting."
    exit $STATUS
elif [ "$CHAIN_INDEX" -ge "$MAX_CHAIN" ]; then
    echo ">>> Work remains but the chain cap ($MAX_CHAIN) is reached -- stopping."
    echo ">>> Resubmit by hand to continue from the cache: sbatch --array=$TASK HPC/Detection/generated/rq4_batch2/L_LM_Jul_26_J_raw/OASIS_Deconvolution__threshold_3_5ch_0-22892769_246d37.sh 1"
else
    NEXT=$((CHAIN_INDEX + 1))
    echo ">>> Work remains -- submitting job $NEXT of $MAX_CHAIN for task $TASK ..."
    sbatch --array="$TASK" HPC/Detection/generated/rq4_batch2/L_LM_Jul_26_J_raw/OASIS_Deconvolution__threshold_3_5ch_0-22892769_246d37.sh "$NEXT"
    echo ">>> Submitted. Monitor with: squeue -u $USER"
fi

echo "Finished     : $(date)"
echo "========================================"
