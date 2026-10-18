# W4-A — the four trained CNNs on real data: one whole channel, and the RQ1 blind labels

Run 2026-10-17/18, read only, by a side session of the manager. `catalogue.cnn_window_scores`'s core,
`Working.Catalogue.cnn.window_scores.score_windows`, was called directly (`resample_to = 600`, `positive_class = 0`,
`img_size = 224`), on `.npy` channels memory-mapped read only. The labels were read from a **copy** of
`DATA/db/annotations.sqlite` (with its WAL) in the session scratchpad. Nothing was written to `DATA/` or the database,
and no code changed. Scripts and raw results (not committed): the shared notes folder,
`side-session-notes/local_37199a7e-…/w4a-evaluation/` (`score_channel.py`, `score_blind.py`, `analyse_blind.py`,
`blind_metrics.json`, `blind_scores.parquet`, `timings.jsonl`).

## In plain words

The four CNNs were trained to look at a picture of a **10-minute** stretch of signal and say "interesting" or not.
The twelve templates also slide them along at 1 minute and at 1 hour, stretching or squeezing each window to the
10-minute shape first. That is like showing a reader a page enlarged ten times, or shrunk six times, and hoping they
still read it.

We checked them two ways. First, all four models went over one whole M2_aug channel at all three window lengths, to
see how often each says "interesting". Second, they were scored against the ~1,000 windows you labelled blind for
RQ1, to see whether they agree with you more often than a lazy guesser who always says "not interesting".

- **At 10 minutes (the training scale) every model clearly beats the lazy guesser.** On your blind labels they are
  right 90–92 % of the time where the lazy guess is right 81 %, and their balanced accuracy (the fair score when one
  answer is much rarer) is **0.78–0.83 at the 0.5 cut, and 0.86–0.88 at a cut near 0.05–0.1**. GASF and GADF are a
  little better than fusion and recurrence.
- **At 30 minutes (squeezed 3×) they still work:** balanced accuracy 0.82–0.84, and 0.86–0.87 on the out-of-sample
  M2 recording for GADF and GASF. Your 30-minute labels are the closest evidence there is for the 1-hour templates,
  which no label measures directly.
- **At 1 minute every model fails, completely.** On one channel each model calls **95–96 % of all 1-minute windows
  "interesting"**. On your blind 1-minute labels (6 % interesting) they are right only 18–28 % of the time, and their
  ranking is *worse than a coin toss* (AUC 0.30–0.46). This is not caused by the stretching: fed the 60 samples
  unstretched, as RQ1's reference line did, they fail the same way. A 1-minute window is simply not something these
  networks learned to read.

**Recommendation for the RQ4 sweep:**

1. **Drop the four `cnn_<model>_1min` templates from the read-out** (or keep one as a negative control). The
   overnight cluster sweep ran them; their results will be "detection almost everywhere" and should not enter the Map
   as a detector.
2. **10-minute templates: start the threshold at 0.1, not 0.5.** Balanced accuracy is flat from 0.05 to 0.2
   (0.85–0.88) and drops at 0.5 (0.78–0.83), because the scores pile up near 0 and 1 and the 0.5 cut misses a third
   of what you called interesting. Sweep 0.05 · 0.1 · 0.2 · 0.5.
3. **1-hour templates: keep 0.5 as the start**, sweep 0.3 · 0.5 · 0.9. There are no 1-hour labels. The 30-minute labels
   put the best cut at 0.2–0.5, but on the channel the 1-hour models already call 40–54 % of hours interesting at 0.5,
   so a lower cut would mark most of the recording.
4. **If one model is chosen, choose GASF** (`cnn_gasf_10min`), with GADF a close second. No model × scale beats
   another by more than its confidence interval, so this is a lean, not a verdict.

The caveats that matter: on M2_aug these scores are **not out-of-sample** (the models were trained on M2_aug windows).
The **only out-of-sample labels are M2_concat's** (332 windows), and at 10 minutes only 13 of them are interesting.
There the 0.5 cut is weak (balanced accuracy 0.63–0.68, its interval reaching down to ~0.5), and a cut near 0.01–0.05
does better (0.75–0.80). Even the best model × scale stays below **your own agreement with yourself**: you gave the
same answer on 94 % of the windows shown twice (98 pairs; balanced accuracy 0.91). No model can be expected to beat
that.

## Check 2 — the RQ1 blind labels

**Labels.** Queue 3 (`blind_test_review`, B.2 run 1613): 1,100 showings, of which 100 are repeats. Scored on the
1,000 first showings. Verdicts are mapped as `Working/training/blind.py` does (`SCORED = interesting /
not_interesting`); `unsure` (3) and `artifact` (11) are left out, which leaves **986 labels: 210 interesting, 776 not**.
Every annotation's span matched its sample window exactly (0 mismatches). No window held NaN or was flat.

**Feed.** Each window at its own length (60, 600 or 1,800 samples at 1 Hz) was resampled to 600 points. That is the
rule of `catalogue.cnn_window_scores`: 1,800 → 600 by block means of 3, and 60 → 600 by linear interpolation. P ≥ 0.5
counts as "interesting". The `as_is` rows of `blind_metrics.json` repeat the score with RQ1's reference line
(`blind_reference.parquet`, each window fed unresampled). At 10 minutes the two are **identical** to the last digit,
as they must be, since 600 samples are not resampled. This checks that the block encodes exactly as training and RQ1
did.

**Which labels fall on M2_aug.** 654 of the 986 (162 interesting) are on `M2_aug_concat_fs1`, the recording the
models were trained on, so they are **not out-of-sample**. 332 (48 interesting) are on `M2_concat_fs1`, a different
recording (RQ1's `blind.CONTAMINATION` note counts every M2_concat_fs1 window as unseen), so they are
**out-of-sample**. Of the M2_aug labels, 248
overlap an earlier human label (`blind.contaminated`, the label set the models were probably trained from). The other
406 do not. The models score **no better on the overlapping ones** (10-min balanced accuracy 0.79–0.84 overlapping,
0.82–0.89 not), so there is no sign that they recall their training windows.

**Baselines.** *Majority accuracy* is the plain accuracy of always answering "not interesting". *Balanced accuracy*
is the mean of the recall on each class: 0.5 for any constant answer, 1.0 for perfect. The 95 % intervals come from a
block bootstrap over 24-hour units of each recording (`blind._units` / `blind._boot`), 1,000 resamples.

### All labels, the 0.5 cut

| Scale (label) | Model | n | interesting | majority acc. | acc. @0.5 | **balanced acc. @0.5** [95 % CI] | AUC [95 % CI] | called interesting |
|---|---|---|---|---|---|---|---|---|
| 1 min | fusion_cnn_3 | 185 | 11 | 0.941 | 0.249 | **0.43** [0.24, 0.57] | 0.42 [0.24, 0.58] | 77 % |
| 1 min | GADF_cnn | 185 | 11 | 0.941 | 0.232 | **0.51** [0.36, 0.61] | 0.46 [0.28, 0.62] | 81 % |
| 1 min | GASF_cnn | 185 | 11 | 0.941 | 0.276 | **0.49** [0.31, 0.62] | 0.42 [0.25, 0.57] | 75 % |
| 1 min | recurrence_cnn | 185 | 11 | 0.941 | 0.178 | **0.39** [0.21, 0.53] | 0.30 [0.16, 0.43] | 84 % |
| 10 min | fusion_cnn_3 | 429 | 80 | 0.814 | 0.900 | **0.78** [0.72, 0.84] | 0.93 [0.89, 0.96] | 14 % |
| 10 min | GADF_cnn | 429 | 80 | 0.814 | 0.904 | **0.83** [0.76, 0.88] | 0.95 [0.91, 0.97] | 17 % |
| 10 min | GASF_cnn | 429 | 80 | 0.814 | 0.918 | **0.82** [0.76, 0.87] | 0.96 [0.94, 0.98] | 14 % |
| 10 min | recurrence_cnn | 429 | 80 | 0.814 | 0.907 | **0.79** [0.73, 0.85] | 0.95 [0.92, 0.97] | 14 % |
| 30 min | fusion_cnn_3 | 372 | 119 | 0.680 | 0.839 | **0.83** [0.78, 0.87] | 0.92 [0.89, 0.95] | 35 % |
| 30 min | GADF_cnn | 372 | 119 | 0.680 | 0.855 | **0.84** [0.80, 0.88] | 0.93 [0.90, 0.95] | 34 % |
| 30 min | GASF_cnn | 372 | 119 | 0.680 | 0.855 | **0.83** [0.79, 0.88] | 0.93 [0.90, 0.96] | 32 % |
| 30 min | recurrence_cnn | 372 | 119 | 0.680 | 0.839 | **0.82** [0.77, 0.86] | 0.92 [0.89, 0.95] | 33 % |
| all three | fusion_cnn_3 | 986 | 210 | 0.787 | 0.755 | 0.74 [0.70, 0.77] | 0.82 [0.78, 0.85] | 34 % |
| all three | GADF_cnn | 986 | 210 | 0.787 | 0.760 | 0.76 [0.72, 0.79] | 0.83 [0.80, 0.86] | 35 % |
| all three | GASF_cnn | 986 | 210 | 0.787 | 0.774 | 0.76 [0.72, 0.79] | 0.82 [0.79, 0.86] | 32 % |
| all three | recurrence_cnn | 986 | 210 | 0.787 | 0.744 | 0.73 [0.69, 0.76] | 0.78 [0.75, 0.82] | 34 % |

Pooled over scales, every model's plain accuracy falls **below** the majority baseline (0.74–0.77 against 0.79),
because of the 1-minute failure. This is why the scales must be read apart.

### Out-of-sample only (M2_concat), the 0.5 cut

| Scale | Model | n | interesting | majority acc. | balanced acc. @0.5 [CI] | AUC [CI] | recall @0.5 |
|---|---|---|---|---|---|---|---|
| 1 min | all four | 89 | **2** | 0.978 | 0.08–0.36 | 0.10–0.22 | 0–0.5 |
| 10 min | fusion_cnn_3 | 129 | 13 | 0.899 | 0.64 [0.52, 0.77] | 0.81 [0.62, 0.95] | 0.31 |
| 10 min | GADF_cnn | 129 | 13 | 0.899 | 0.63 [0.50, 0.76] | 0.90 [0.82, 0.96] | 0.31 |
| 10 min | GASF_cnn | 129 | 13 | 0.899 | 0.68 [0.54, 0.81] | 0.90 [0.82, 0.96] | 0.38 |
| 10 min | recurrence_cnn | 129 | 13 | 0.899 | 0.68 [0.53, 0.83] | 0.91 [0.84, 0.96] | 0.38 |
| 30 min | fusion_cnn_3 | 114 | 33 | 0.711 | 0.77 [0.68, 0.86] | 0.91 [0.85, 0.95] | 0.67 |
| 30 min | GADF_cnn | 114 | 33 | 0.711 | **0.87** [0.78, 0.94] | 0.91 [0.84, 0.97] | 0.82 |
| 30 min | GASF_cnn | 114 | 33 | 0.711 | **0.86** [0.77, 0.93] | 0.92 [0.84, 0.97] | 0.79 |
| 30 min | recurrence_cnn | 114 | 33 | 0.711 | 0.80 [0.71, 0.88] | 0.91 [0.85, 0.96] | 0.73 |

At 10 minutes the out-of-sample *ranking* is good (AUC 0.81–0.91), but the 0.5 cut sits too high. The M2_concat
interesting windows score lower (median P 0.04–0.27) than M2_aug's (0.71–0.93), and the 0.5 cut finds only a third
of them.

### Which cut (balanced accuracy at fixed cuts, resampled feed)

| Scale · labels | Model | 0.01 | 0.05 | **0.1** | 0.2 | 0.3 | 0.5 | 0.7 | 0.9 |
|---|---|---|---|---|---|---|---|---|---|
| 10 min · all | fusion_cnn_3 | 0.84 | 0.86 | **0.85** | 0.82 | 0.83 | 0.78 | 0.73 | 0.63 |
| 10 min · all | GADF_cnn | 0.87 | 0.87 | **0.86** | 0.86 | 0.85 | 0.83 | 0.81 | 0.76 |
| 10 min · all | GASF_cnn | 0.87 | 0.88 | **0.86** | 0.86 | 0.86 | 0.82 | 0.78 | 0.72 |
| 10 min · all | recurrence_cnn | 0.87 | 0.86 | **0.86** | 0.85 | 0.82 | 0.79 | 0.74 | 0.67 |
| 10 min · M2_concat | fusion_cnn_3 | 0.78 | 0.80 | 0.73 | 0.65 | 0.67 | 0.64 | 0.65 | 0.62 |
| 10 min · M2_concat | GADF_cnn | 0.80 | 0.72 | 0.73 | 0.74 | 0.67 | 0.63 | 0.64 | 0.61 |
| 10 min · M2_concat | GASF_cnn | 0.75 | 0.69 | 0.69 | 0.70 | 0.71 | 0.68 | 0.68 | 0.61 |
| 10 min · M2_concat | recurrence_cnn | 0.77 | 0.73 | 0.71 | 0.71 | 0.71 | 0.68 | 0.65 | 0.58 |
| 30 min · all | fusion_cnn_3 | 0.68 | 0.80 | 0.82 | 0.84 | 0.84 | 0.83 | 0.78 | 0.70 |
| 30 min · all | GADF_cnn | 0.74 | 0.82 | 0.84 | 0.85 | 0.86 | 0.84 | 0.83 | 0.78 |
| 30 min · all | GASF_cnn | 0.82 | 0.86 | 0.87 | 0.86 | 0.86 | 0.83 | 0.80 | 0.79 |
| 30 min · all | recurrence_cnn | 0.76 | 0.82 | 0.84 | 0.86 | 0.84 | 0.82 | 0.81 | 0.76 |

These cuts are read off the same labels they are judged on, so they are optimistic. The plateau is wide (0.05–0.3 at
10 min, 0.1–0.5 at 30 min), which makes the choice robust. With 13 interesting windows, M2_concat's 10-minute row is
too thin to pick a cut from by itself.

## Check 1 — one whole M2_aug channel at each scale

**Channel:** `M2_aug_concat_fs1` CH14 (recording 15, 2,595,600 samples = 721 h at 1 Hz, no NaN). CH14 holds the most
blind labels of any channel. Windows are those `preprocessing.sliding_windows` plans with `gap_s = 0`
(`plan_windows`): 43,260 one-minute, 4,326 ten-minute and 721 one-hour windows. **No window was skipped** (0 NaN,
0 flat) for any model or scale.

| Window | Model | q05 | q25 | median | q75 | q95 | **≥ 0.5** | ≥ 0.9 | ≥ 0.1 | merged detections @0.5 | wall | ms / window |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 min | fusion_cnn_3 | 0.538 | 0.982 | 0.999 | 1.000 | 1.000 | **95.2 %** | 87.8 % | 97.3 % | 912 | 34.6 min | 48.0 |
| 1 min | GADF_cnn | 0.686 | 0.995 | 0.998 | 0.999 | 1.000 | **96.1 %** | 92.5 % | 98.0 % | 875 | 16.8 min | 23.3 |
| 1 min | GASF_cnn | 0.709 | 0.999 | 1.000 | 1.000 | 1.000 | **96.0 %** | 93.2 % | 97.7 % | 868 | 17.0 min | 23.6 |
| 1 min | recurrence_cnn | 0.884 | 1.000 | 1.000 | 1.000 | 1.000 | **96.4 %** | 94.9 % | 97.6 % | 770 | 15.6 min | 21.6 |
| 10 min | fusion_cnn_3 | 0.000 | 0.001 | 0.005 | 0.051 | 0.715 | **9.8 %** | 2.1 % | 20.3 % | 271 | 6.2 min* | 86.6* |
| 10 min | GADF_cnn | 0.000 | 0.000 | 0.002 | 0.031 | 0.929 | **11.7 %** | 5.9 % | 19.7 % | 343 | 2.0 min | 28.4 |
| 10 min | GASF_cnn | 0.000 | 0.000 | 0.000 | 0.007 | 0.897 | **10.1 %** | 4.9 % | 16.2 % | 302 | 1.9 min | 26.0 |
| 10 min | recurrence_cnn | 0.000 | 0.000 | 0.001 | 0.017 | 0.857 | **9.4 %** | 4.3 % | 17.2 % | 253 | 1.7 min | 23.7 |
| 1 h | fusion_cnn_3 | 0.010 | 0.176 | 0.553 | 0.813 | 0.996 | **53.5 %** | 18.0 % | 81.0 % | 151 | 59 s | 81.9 |
| 1 h | GADF_cnn | 0.004 | 0.051 | 0.396 | 0.879 | 0.995 | **45.1 %** | 22.2 % | 68.9 % | 140 | 51 s | 70.0 |
| 1 h | GASF_cnn | 0.000 | 0.025 | 0.272 | 0.851 | 0.995 | **40.4 %** | 21.6 % | 61.2 % | 143 | 57 s | 78.5 |
| 1 h | recurrence_cnn | 0.003 | 0.091 | 0.457 | 0.897 | 0.998 | **47.9 %** | 24.7 % | 74.1 % | 150 | 37 s | 51.4 |

*"Merged detections"* counts runs of touching windows at or above 0.5, which is what the template's Threshold step
would report. *The 10-minute fusion run shared the CPU with the blind-label analysis, so its 87 ms/window is inflated;
the 1-minute fusion run, alone, gave 48 ms.

- **Wall time matches the brief's estimate:** fusion ≈ 48 ms a window, the other three ≈ 22–24 ms, on the CPU and
  while another session was working. One whole channel through all twelve templates took **≈ 1.6 h**; the 1-minute
  fusion template alone takes 35 min. The 1-hour windows cost more per window (51–82 ms): each window is block-meaned
  from 3,600 samples, and the model load is spread over only 721 windows.
- **The three scales disagree with one another.** Within a scale the four models rank windows alike (Spearman ρ
  0.63–0.75 at 10 min, 0.84–0.87 at 1 h; at 1 min 0.80–0.83, except recurrence at 0.22–0.46). Across scales, though,
  a 10-minute window's score is *anti*-correlated with the mean of its ten 1-minute scores (ρ = −0.54 fusion, −0.50
  GASF) and only weakly tied to its 1-hour parent (ρ = 0.24 / 0.21). The 1-minute templates fire where the 10-minute
  ones do not.
- **At 1 hour the models call 40–54 % of all hours interesting at 0.5**, against ~10 % of 10-minute windows. With no
  1-hour labels, whether that is a real property of long stretches or a squeezing artefact cannot be told yet.

## What else I would measure

1. **Label a few dozen 1-hour windows blind** (stratified by the 1-hour score). It is the only way to calibrate
   `cnn_*_60min`; the 30-minute labels are a proxy.
2. **Weight the blind metrics by the sample's stratum weights** (`blind_sample.parquet: weight`). The sample was drawn
   stratified by the B.2 forest's cluster and class, so the base rates above are the sample's, not the recording's.
   Balanced accuracy and AUC are less sensitive to this than plain accuracy, but not immune.
3. **More out-of-sample interesting labels at 10 minutes** (M2_concat has 13; the other datasets have none). This is
   the number that decides the threshold on recordings the models never saw.
4. **The Discovery null for the CNN templates** (surrogate draws): a model that calls 96 % of 1-minute windows
   interesting will also do so on noise. That would confirm the negative-control reading cheaply.

## Files

- Shared notes folder `w4a-evaluation/`: `score_channel.py` (check 1), `score_blind.py` (check 2, per-window scores →
  `blind_scores.parquet`), `analyse_blind.py` (all the tables above → `blind_metrics.json` / `.txt`) and
  `timings.jsonl`. Per-window channel scores (`chan_CH14/*.npz`) are in the session scratchpad.
