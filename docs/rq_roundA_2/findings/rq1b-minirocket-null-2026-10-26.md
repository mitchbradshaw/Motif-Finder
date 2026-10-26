# R4 against chance, its intervals, and R4 against the CNNs (2026-10-26)

Code: `scripts/rq1b_minirocket_null.py` (null, intervals), `scripts/rq1b_cnn_vs_minirocket.py` (CNNs). Tests:
`tests/test_rq1b_minirocket_null.py`. Outputs: `DATA/derived/models/rq1b_minirocket_null/20261026/` (`null.json`,
`ci.json`, `real_decisions.parquet`, `null_decisions.npy`, cached fold features), and
`DATA/derived/models/rq1b_cnn_vs_minirocket/reference_20261026/` (`reference_comparison.json`,
`reference_scores.parquet`). R4 itself (`scripts/rq1b_minirocket.py`, model 20261020-2343) is unchanged. M4_aug was
not read. Nothing was written to the database.

## In plain words

Three questions a reader of the thesis will ask about R4, the MiniRocket model that agrees with your verdicts on
about 9 recordings-it-never-saw candidates in 10.

1. **Could it be luck?** We shuffled your verdicts 200 times (each recording keeps its share of "interesting"),
   retrained each time, and scored again. Shuffled verdicts give a model that is no better than a coin; the real one
   is far above every shuffle. Think of a student who scores 97 % on an exam where students given the wrong answer
   key all score about 50 %: the 97 % is not luck.
2. **How precise is the 0.97?** Resampling the judged events gives a 95 % range of 0.96–0.98 for AUC, and 0.90–0.94
   for balanced accuracy. Per recording the ranges stay above 0.92 for AUC.
3. **Is a CNN better?** The four picture-reading CNNs already in `MODELS/`, shown exactly the same events, do much
   worse: AUC 0.72–0.79 pooled against R4's 0.97, and worse on every recording, including M2_aug, where the CNNs had
   the advantage of having been trained on it. This comparison is not fully fair to the CNNs (they learned from an
   older labelling of 10-minute windows, not from these events), so a fair one is prepared for the cluster: the
   same network trained on the same rows with R4's folds.

## 1. The label-shuffle null

**Protocol.** R4's own 5,456 rows (from its `predictions.parquet`, not re-collected) and its folds: one recording
group held out at a time, its events scored, windows only ever train. Each fold's MiniRocket transform is fitted on
the training rows (it uses no label), computed once and cached. Each shuffle permutes the labels within every
(recording group, kind) block and refits the standardisation and the ridge, with its penalty picked from R4's grid by
leave-one-out error. Platt calibration is a monotone map of the ridge score, so it cannot change AUC, nor balanced
accuracy at the ridge's cut, and is not refitted. p = (1 + shuffles at least as good) / (1 + shuffles).

**One simplification.** R4 weights its classes equally. Those weights move with the labels, so each shuffle would
need a fresh 5,000 x 5,000 decomposition per fold. The null instead uses the unweighted ridge, decomposed once per
fold. The real labels go through the same unweighted procedure, and that is the number the null is compared with.
The exact, weighted R4 procedure was also recomputed here on the real labels. It reproduces R4's stored held-out
scores on every fold to 1e-7, which checks that the cached features are R4's. (A first run in float32 drifted by up
to 1.0 on the 5,000-row folds; that run is kept in `float32_first_run/` and not used.) The alpha chosen was 1,000, the
top of R4's grid, for the real labels and for all 1,200 shuffled fits.

**Result, 200 shuffles (191 s):**

| Held out | Events | Real AUC | Null AUC: mean (97.5 %, max) | p | Real BA | Null BA: mean (max) | p |
|---|---|---|---|---|---|---|---|
| **pooled** | 2,456 | **0.971** | 0.420 (0.461, 0.495) | **0.005** | **0.915** | 0.443 (0.492) | **0.005** |
| CO | 256 | 0.989 | 0.509 (0.581, 0.639) | 0.005 | 0.951 | 0.507 (0.627) | 0.005 |
| LM | 294 | 0.995 | 0.498 (0.567, 0.592) | 0.005 | 0.959 | 0.500 (0.579) | 0.005 |
| L_LM_Jul_26_J | 371 | 0.984 | 0.499 (0.555, 0.635) | 0.005 | 0.927 | 0.499 (0.612) | 0.005 |
| M2_aug | 1,270 | 0.954 | 0.502 (0.534, 0.547) | 0.005 | 0.886 | 0.502 (0.534) | 0.005 |
| M2_concat | 253 | 0.961 | 0.496 (0.578, 0.605) | 0.005 | 0.913 | 0.495 (0.589) | 0.005 |
| Mushroom_260720 | 12 (11 interesting) | 1.000 | 0.481 (1.000, 1.000) | 0.11 | 0.500 | 0.483 (1.000) | 0.53 |

No shuffle reached the real score anywhere but Mushroom, so p = 1/201 ≈ 0.005 is the floor this many shuffles can
show. The real AUC is 26 null standard deviations above the null mean. Mushroom's 12 events, one of them "not",
cannot test anything and should be reported as such.

**Why the pooled null sits at 0.42, not 0.50.** Each held-out recording is fine alone (0.50). Pooling scores across
folds compares events scored by different models. A shuffled model's intercept follows its training base rate, which
runs opposite to the held-out recording's rate (M2_aug, mostly "interesting", is scored by a model trained mostly on
"not"). So pooled shuffled scores rank slightly backwards. The real model is free of this because it scores the events
themselves. The per-recording rows are the clean reading; the pooled row is conservative.

## 2. Bootstrap 95 % intervals (R4's stored held-out scores, 2,000 resamples)

| Held out | Events (interesting) | AUC [95 %] | Balanced accuracy [95 %] |
|---|---|---|---|
| **pooled, events resampled within each recording** | 2,456 (1,331) | **0.971 [0.965–0.977]** | **0.919 [0.907–0.930]** |
| pooled, whole channels resampled (46 channels) | | 0.971 [0.962–0.980] | 0.919 [0.902–0.935] |
| CO | 256 (88) | 0.989 [0.976–0.998] | 0.954 [0.923–0.981] |
| LM | 294 (139) | 0.995 [0.990–0.999] | 0.955 [0.931–0.977] |
| L_LM_Jul_26_J | 371 (157) | 0.984 [0.972–0.992] | 0.925 [0.895–0.950] |
| M2_aug | 1,270 (864) | 0.951 [0.938–0.963] | 0.886 [0.866–0.904] |
| M2_concat | 253 (72) | 0.961 [0.927–0.987] | 0.909 [0.869–0.947] |
| Mushroom_260720 | 12 (11) | 1.000 [–] | 0.500 [0.50–1.00] |

The channel-cluster interval is the cautious one to quote (events on one channel are not independent). Per recording
the intervals resample events. CO, LM and L_LM have only 4–5 channels, too few to resample channels.

## 3. The reference CNNs on exactly R4's events (quick version)

Each of R4's 2,456 events, cut as R4 cuts it (span + a quarter of its length each side, mV), resampled to 600 points
by the CNN block's own rule and scored by `window_scores`' own path (P(interesting) = softmax column 0). CPU,
sequential: 20–25 ms per event (fusion 50 ms), 5 minutes for all four models. All 2,456 events were scored; none was
left out. R4's numbers are its leave-one-recording-out scores. The CNNs' are their fixed checkpoints.

**Sample flags (for the CNNs):** M2_aug is **in-sample** (the CNNs were trained on M2_aug windows). M2_concat is
**probably out-of-sample**: RQ1's `blind.CONTAMINATION` counts it as unseen, but the training data is not recorded and
`M2_concat_fs1.mat` (2 Apr 2026) predates the GASF, GADF and recurrence checkpoints (12–13 Apr). CO, LM,
L_LM_Jul_26_J and Mushroom are **out-of-sample** (their files are dated Aug–Oct 2026, after every checkpoint).

AUC (R4 / CNN), and the paired bootstrap of R4 minus the CNN on the same events:

| Held out | Flag | R4 | GASF | GADF | recurrence | fusion_cnn_3 | R4 − best CNN [95 %] |
|---|---|---|---|---|---|---|---|
| CO | out | 0.989 | 0.740 | 0.803 | 0.684 | 0.785 | +0.19 [0.14–0.24] |
| LM | out | 0.995 | 0.676 | 0.720 | 0.586 | 0.636 | +0.28 [0.21–0.34] |
| L_LM_Jul_26_J | out | 0.984 | 0.791 | 0.869 | 0.766 | 0.783 | +0.12 [0.08–0.15] |
| M2_concat | probably out | 0.961 | 0.573 | 0.608 | 0.568 | 0.585 | +0.35 [0.29–0.42] |
| M2_aug | **in** | 0.951 | 0.796 | 0.838 | 0.801 | 0.801 | +0.11 [0.08–0.14] |
| Mushroom (12) | out | 1.000 | 0.818 | 1.000 | 0.818 | 1.000 | – |
| **pooled** | mixed | **0.971** | 0.737 | 0.790 | 0.722 | 0.738 | +0.18 [0.16–0.20] |

Balanced accuracy (R4 at its own cut / CNN at 0.5). W4-A's lower cut, 0.1, is lower pooled (0.70–0.73) and helps
only on M2_concat (by up to 0.04); it is in `reference_comparison.json`.

| Held out | R4 | GASF | GADF | recurrence | fusion_cnn_3 |
|---|---|---|---|---|---|
| CO | 0.954 | 0.769 | 0.758 | 0.698 | 0.732 |
| LM | 0.955 | 0.705 | 0.725 | 0.718 | 0.702 |
| L_LM_Jul_26_J | 0.925 | 0.816 | 0.800 | 0.808 | 0.795 |
| M2_concat | 0.909 | 0.628 | 0.656 | 0.624 | 0.645 |
| M2_aug (in-sample for CNNs) | 0.886 | 0.765 | 0.766 | 0.752 | 0.756 |
| pooled | 0.919 | 0.744 | 0.748 | 0.737 | 0.733 |

Every interval of the difference is above zero. GADF is the best CNN everywhere, as W4-A leaned.

**What this does and does not say.** It says the CNNs as they exist do not judge your events as you do, and R4 does.
It does not say a CNN *cannot*: these were trained on another labelling (10-minute windows of M2_aug, before the
event queues existed), at one scale, and an event cut stretched to 600 points is not what they learned to read. That
is what the fair version tests.

## 4. The fair version: prepared, not submitted

`DATA/derived/hpc/rq1b_cnn_loro_20261026/` (README.txt holds the steps): an EfficientNet-B0 (ImageNet weights,
`cnn_job.build_model`) on GASF, GADF and fusion pictures (`cnn_job.encode_window`) of the SAME 5,456 rows, cut and
resampled exactly as in §3, trained with R4's six leave-one-recording-out folds (events and windows train, held-out
events are scored). 12 epochs, batch 64, Adam 1e-3 cosine, balanced class weights, seed 42, no augmentation. 18 GPU
tasks (3 encodings x 6 folds), three at a time, after a CPU array that draws the pictures once.

- **Estimate:** 989,448 training images. At an *assumed* 400 images/s on an A100 (the AI arm's assumption; the first
  epoch prints the real rate), about 0.7 GPU-hours of compute, **about 1.6 GPU-hours with start-up**, three tasks at
  a time, so about 35 minutes of wall clock. Encoding is about 3 CPU-minutes per encoding.
- **Smoke, here:** the whole round trip ran on a 200-row copy (encode, 1 epoch on 24 pictures per fold on the CPU
  without ImageNet weights, status, import). The import reads partial returns and names what is missing. The
  1-epoch, untrained network gives a constant score (AUC 0.50), as an untrained EfficientNet in eval mode does. The
  same tensors give varied scores from a trained checkpoint, so the data path is sound. The GPU path itself has not
  run.
- **Import:** `python scripts/rq1b_cnn_vs_minirocket.py import --job DATA/derived/hpc/rq1b_cnn_loro_20261026` writes
  `DATA/derived/models/rq1b_cnn_vs_minirocket/fair/fair_comparison.json` (the §3 table with the fair CNNs). It refuses
  if the rows are not R4's, or a prediction file came from other inputs.

## 5. A second unseen recording: survey and proposal

**The survey (read-only):** no registered recording outside R4's six groups has a single detector run. SH, SO, F2B,
L_R_Aug_26_PD, MJu26a, MJu26a_fs10, M1, M100, M101_t, M2_aug_fs2, the three Adamatzky species and the four Dwij
`mfs2` files: 0 runs, 0 detections, 0 verdicts. `HPC/results/` holds nothing waiting to be imported. Every swept
recording (M2_aug, M2_concat, CO, LM, L_LM 10 and 2 Hz, Mushroom) is already judged and inside R4. M4 was excluded and
not read.

**Proposal: *Schizophyllum commune* (Adamatzky, Zenodo 5790768).**

- **Why this one.**
  - It is the smallest unswept recording that is a genuinely new test: 7 channels x ~73 h at 1 Hz, about 1.8 M
    samples, 4 % of M2_aug.
  - It is from another lab, another rig and another species, in mV at 1 Hz (rates and units R4 already met).
  - SH and SO (4 x 480 h at 10 Hz, 69 M samples), L_R_Aug_26_PD (50 M) and F2B (26 M) are 15–40 times larger to
    sweep.
  - The Dwij files are smaller still, but at 0.8 Hz with uneven timestamps: two new things at once.
- **The steps.**
  1. The RQ4 sweep on rangpur: `python scripts/rq4_overnight.py build-batch --db <copy> --source "Schizophyllum
     commune.txt" --units "Schizophyllum commune.txt=mV" --out <batch> --prefix rq4s`. Then the packs, then `adopt`
     (about 25 minutes of driver time locally, as batch 3). Cluster time is not measured for a recording this size;
     scaled by samples from M2_aug's overnight sweep, it should be under one pack cycle (an estimate). The
     Adamatzky NaN gaps follow the skip-the-gaps policy.
  2. A candidate-event table: `scripts/rq1b_candidate_events.py build --file …`. That code is owned by the M4-exam
     agent today; ask before running it.
  3. A stratified blind sample of **300 events**, drawn the way queue 28 drew per recording (by detector agreement and
     selective family). 300 matches CO, LM and M2_concat's 250–300 and gives an AUC interval about ±0.02 at R4's level.
- **Judging time.** Your measured pace on queues 25 and 28 is a median 1.4 s and a mean 2.0 s per verdict (1,157
  verdicts in 0.65 active hours). So about **10–15 minutes** for 300.
- **The test.** Score the saved R4 model (`model.joblib`, trained on all six groups) once, frozen, before anyone
  looks at its scores. Pre-register: AUC, balanced accuracy at the ridge's cut, the bootstrap interval, and detector
  agreement as the baseline.
- **Risk.** The Adamatzky channels may hold few events the sweep calls candidates, or few you call interesting. If
  the 300 hold fewer than about 30 "interesting", the AUC interval widens to about ±0.05. A second species (Enoki,
  300 h) is then the next cheapest.

## What is left

- The fair CNN run (researcher, about 1.6 GPU-hours), then its import.
- The second unseen recording (sweep, table, queue, judging), as above. No queue was built.
- The null used 200 shuffles. 1,000 would take about 5 minutes more and lower the p-value floor to 0.001, if a
  reader wants it.
