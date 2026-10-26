# The RQ4b sweep's detectors against their phase-randomised copies, 2026-10-26

Made by `scripts/thesis/detectors_vs_surrogates.py` (read-only). Outputs in
`docs/thesis/data/detectors_vs_surrogates/`: `tasks.csv` (one row per variant × channel: real detections, each
draw's count), `by_variant_recording.csv`, `by_family.csv`, `by_family_recording.csv`,
`family_recording_pivot.csv`, `summary.json`. M4_aug (session 7) was never read.

## In plain words

Every detector was run twice on every channel: once on the real recording, and once on a scrambled copy that keeps
the recording's "pitch content" (its power spectrum) but destroys its shapes. A detector that finds real events
should find more on the real recording than on the scramble, like a metal detector that should beep more on a beach
with coins than on an identical beach without them.

**The surprise is that some of the detectors the researcher trusts most beep *less* on the real recording.**
wavelet_encoded (judged events 86–100 % accepted on four of five recordings) and symbol_search (64 %) find 10–100 times
*fewer* events on the real signal than on its scramble, on every recording; the drop detectors sit near 1 (0.13–2.4).
The loose detectors (OASIS, deconvolved_troughs, noise_threshold), whose judged events are mostly rejected, find
40–280 times *more*. So "real beats its null" measures something other than precision here. A possible reason, not
tested here: a phase-randomised copy of a slowly drifting, heavy-tailed signal is Gaussian-like, with many small,
sharp, symmetric wiggles that encoders of fast falls fire on, while the real signal's long smooth stretches give them
nothing; detectors that subtract a slow baseline and count excursions above the noise do the opposite. With **one
draw per task**, each count also carries its own noise.

## The statement in RQ4b, reproduced

"In 255 of 552 tasks the real signal gave no more detections than its phase-randomised copy" (RQ4b log,
2026-10-19, **batch 3: LM_fs2, CO_fs2 and L_LM fs2**, 1 draw each). Recomputed from the database: **552 cluster
tasks, 255 with real ≤ surrogate. It reproduces exactly.** It is a batch-3 figure, not the whole sweep. By family:

| family | tasks | real ≤ surrogate | | family | tasks | real ≤ surrogate |
|---|---|---|---|---|---|---|
| symbol_search | 39 | **39** | | cnn_60min | 52 | 20 |
| wavelet_encoded | 39 | **39** | | drop_detection_v1 | 39 | 11 |
| cnn_1min | 52 | 36 | | drop_detection_v5 | 39 | 9 |
| BEADs_invert_detect_v1 | 39 | 27 (3 both zero) | | OASIS_Deconvolution | 39 | 0 |
| signal_threshold (mV copies) | 39 | 27 | | deconvolved_troughs | 39 | 0 |
| Wavelet_detection_prototype | 39 | 26 | | noise_threshold | 39 | 0 |
| cnn_10min | 52 | 21 | | matrix profile (2 ch each) | 6 | 0 |

By recording: CO_fs2 79 / 170, LM_fs2 84 / 170, L_LM fs2 92 / 212.

Across every session read (M2_aug, M2_concat, the three batch-3 recordings, L_LM 10 Hz): 1,880 tasks, 849 with
real ≤ surrogate (1,862 tasks at 1 draw; 17 older M2_aug runs at 20; 1 at 2).

## Real ÷ surrogate, by family and recording

Each cell: total real detections ÷ total surrogate detections, then (tasks where real ≤ surrogate / tasks). The
matrix-profile row excludes the three local copies made from the cached profiles.

| family | M2_aug | M2_concat | CO_fs2 | LM_fs2 | L_LM fs2 | L_LM 10 Hz |
|---|---|---|---|---|---|---|
| deconvolved_troughs | 238 (0/34) | 172 (0/48) | 156 (0/12) | 222 (0/12) | 283 (0/15) | 247 (0/15) |
| OASIS_Deconvolution | 126 (0/48) | 78 (0/48) | 39 (0/12) | 76 (0/12) | 173 (0/15) | — |
| noise_threshold | 54 (0/48) | 58 (0/48) | 48 (0/12) | 71 (0/12) | 45 (0/15) | — |
| matrix profile | 0/0 (2/2) | 0/0 (2/2) | 3.9 (0/2) | 91 (0/2) | 17 (0/2) | — |
| cnn_10min | 2.67 (8/64) | 1.84 (13/64) | 0.84 (8/16) | 1.20 (5/16) | 1.18 (8/20) | 1.15 (9/20) |
| drop_detection_v1 | 1.52 (12/48) | 2.44 (11/48) | 0.78 (4/12) | 1.13 (3/12) | 2.40 (4/15) | — |
| cnn_60min | 1.05 (32/64) | — | 1.42 (5/16) | 0.78 (11/16) | 1.45 (4/20) | 1.49 (4/15) |
| drop_detection_v5 | 1.98 (4/34) | ∞ (0/48: null found none) | 0.13 (3/12) | 0.29 (3/12) | 1.18 (3/15) | — |
| Wavelet_detection_prototype | 0.78 (18/34) | 0.80 (32/48) | 0.62 (8/12) | 0.54 (8/12) | 0.61 (10/15) | — |
| cnn_1min | 0.40 (39/64) | 0.41 (50/64) | 0.26 (13/16) | 0.64 (9/16) | 0.26 (14/20) | 0.91 (7/20) |
| BEADs_invert_detect_v1 | 0.09 (40/48) | 0.09 (38/48) | 0.11 (7/12) | 0.12 (10/12) | 0.13 (10/15) | — |
| signal_threshold | 0.03 (40/48) | 0.06 (39/48) | 0.06 (7/12) | 0.09 (11/12) | 0.05 (9/15) | — |
| symbol_search | 0.01 (34/34) | 0.11 (47/48) | 0.00 (12/12) | 0.00 (12/12) | 0.05 (15/15) | — |
| wavelet_encoded | 0.01 (48/48) | 0.07 (48/48) | 0.02 (12/12) | 0.02 (12/12) | 0.03 (15/15) | — |

Per template variant and recording (240 cells), real exceeds surrogate in 116. Every OASIS, deconvolved_troughs
and noise_threshold variant exceeds on every recording; no symbol_search or wavelet_encoded variant does on any;
signal_threshold exceeds in 2 of 16 cells, BEADs in 2 of 15, the Wavelet prototype only at ε 0.1 (5 of 5). The per-variant table is
`by_variant_recording.csv`.

**Read beside precision** (R3, the blind stratified queues, `findings/rq1b-candidate-events.md` and the ledger):
drop_detection_v1 92–100 %, drop_detection_v5 81–100 %, wavelet_encoded 31–100 %, BEADs 68 %, symbol_search 64 %,
OASIS 44 %, deconvolved_troughs 1–7 %, matrix profile 0 %. The ordering by "× null" is roughly the reverse of the
ordering by precision. For the thesis: **a count against one phase-randomised draw is not evidence that a detector
finds real events**, and the RQ4b read-out's step 3 (each chosen variant against a 20-draw null) is still owed.

## The 20-draw bundle (prepared, NOT submitted)

`scripts/thesis/surrogates20_bundle.py` built it on a sandbox copy of the database in the session scratchpad (the
step cache, RESULTS_DIRs, MODEL_ROOT and cost calibrations redirected there; the copy deleted afterwards), through
the overnight sweep's own machinery (`scripts/rq4_overnight.py` → P2's `Working.discovery.chain_job` specs →
packed pack scripts; `Working/hpc/job_export.py` supplies the repo-relative paths and partition walls). Folder:
**`docs/thesis/hpc/surrogates20_M2_aug/`** (406 KB: six specs, four pack scripts, `submit_th20.sh`, `manifest.json`).

**What runs:** M2_aug, all 16 channels, the whole 721 h, phase randomisation seed 0, **20 draws** per channel, on the
six most precise variants of four families (per-setting precision from queue 25's estimate):

| variant | precision (95 % CI) on M2_aug | spec hash | pack |
|---|---|---|---|
| drop_detection_v1__slope_sigma_4 | 0.99 (0.99–0.99, n 38) | e6f9baf8 | cpu |
| drop_detection_v1 | 0.94 (0.86–0.99, n 35) | 0c9abde6 | cpu |
| wavelet_encoded__level_5 | 0.92 (0.84–0.99, n 39) | 9e9dfc75 | cpu |
| drop_detection_v5__same_fraction_0p7 | 0.81 (0.72–0.90, n 57) | ffe0c77a | cpu |
| cnn_gadf_10min | 0.97 (0.73–0.99, n 15) | 2613f163 | a100 |
| cnn_recurrence_10min | 0.96 (0.70–0.99, n 13) | 69aa5daa | a100 |

96 tasks: `th20_cpu1`/`th20_cpu2` (32 each, 8 at a time, 20-min wall, self-chaining) and `th20_gpuA`/`th20_gpuB`
(16 each, a100, 5 h wall).

**Cost estimate.** Each task is 21 chain runs (real + 20 draws). Using the overnight script's per-task figures (real +
1 draw on a loaded PC, halved: drop detectors 70 s, wavelet_encoded 165 s, a 10-min CNN 220 s) scaled × 10.5:
CPU ≈ 48 × 735 s + 16 × 1,733 s ≈ **17.5 core-hours** (≈ 1.1 h wall per CPU pack at 8 cores); a100 packs ≈ 32 ×
2,310 s ≈ **20.5 core-hours of CPU-bound image making, ≈ 1.3 h wall each, so ≈ 2.6 A100-hours**. The overnight
sweep ran at about 0.3 × its estimates, so the low end is ≈ 5 CPU core-hours and ≈ 1 A100-hour. The pack scripts'
own balancing figure (3,000 / 3,520 core-s per pack) counts one draw and is too low.

**Disk:** batch 1 brought back about 30 MB per real + 1 draw task; 20 draws could bring back ten times that,
**≈ 10–30 GB**. The home quota filled at ~16 GB in batch 2: free space first (`cleanup_copied.sh`), or submit the CPU
and GPU halves separately and copy back in between.

**To send it** (the researcher, by hand): copy `docs/thesis/hpc/surrogates20_M2_aug/` to the same path in the
cluster checkout (`/home/Student/s4699158/CNN`), update the cluster's code to main (the chain-job runner and
`scripts/rq4_overnight.py`), check the 16 `DATA/derived/channels/M2_aug_concat_fs1/CH*.npy` are there, then
`bash docs/thesis/hpc/surrogates20_M2_aug/submit_th20.sh`. Progress:
`python scripts/rq4_overnight.py report --out docs/thesis/hpc/surrogates20_M2_aug`.

**To bring it back:** copy every `docs/thesis/hpc/surrogates20_M2_aug/*_out/return/` folder home, keeping the paths;
dry-run, then import through the bridge:

    python scripts/rq4_overnight.py adopt --url http://127.0.0.1:8765 --out docs/thesis/hpc/surrogates20_M2_aug
    python scripts/rq4_overnight.py adopt --url http://127.0.0.1:8765 --out docs/thesis/hpc/surrogates20_M2_aug --apply --allow-project

`adopt` registers each job as a waiting run in the *open* M2_aug Discovery session: check it is session 2
("M2_aug_concat_fs1 screen"), not session 9 ("demo · talk", which DEMO_DAY says opens first while it exists).
The six imports are new configurations (20 draws), so they land as new Map rows beside the 1-draw ones.
