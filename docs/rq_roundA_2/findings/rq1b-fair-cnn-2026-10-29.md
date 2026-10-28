# The fair CNN against R4, on R4's own folds (2026-10-29)

**Code:** `scripts/rq1b_cnn_vs_minirocket.py` (`export`, `encode`, `train`, `import`).

**Job:** `DATA/derived/hpc/rq1b_cnn_loro_20261026/`, 18 tasks. It was prepared 2026-10-25, trained on rangpur on the
evening of 2026-10-28 and imported here 2026-10-29.

**Outputs:** `DATA/derived/models/rq1b_cnn_vs_minirocket/fair/`, holding `fair_comparison.json` (copied beside this
file) and `fair_scores.parquet`.

R4 (`scripts/rq1b_minirocket.py`, model 20261020-2343) is unchanged. M4_aug was not read, and nothing was written to
the database.

## In plain words

R4, the MiniRocket model, beat the four picture-reading CNNs by a wide margin on the same 2,456 judged events: AUC
0.97 against 0.72–0.79 (`rq1b-minirocket-null-2026-10-26.md`). That comparison was not fair to the CNNs. They had
learned from an older labelling of 10-minute windows, not from these events: two students sitting the same exam,
only one of whom studied for it.

The fair arm trains the same kind of CNN, EfficientNet-B0, on exactly R4's rows with R4's folds, so both models study
the same material and sit the same papers.

**The CNN catches up completely.**
- **Pooled AUC:** 0.970–0.973 for the three picture types, against R4's 0.971.
- **The paired difference:** within ±0.007, and the 95 % interval includes zero for every picture type.
- **Balanced accuracy:** 0.915–0.916, against R4's 0.919.
- **Per recording:** no paired difference excludes zero.

So the large gap in the reference comparison came from what those CNNs were trained on, not from CNNs as such.

What this cannot say is whether the fair CNN would also hold up on a recording neither model has seen. It stays out
of the M4 exam by decision (Round 5 Q3), so only R4 was frozen and scored there.

## Protocol

- **Rows.** R4's 5,456 rows (`inputs.npz`, sha1 `e8d49cf2`): the 2,456 judged events and R4's windows. As in R4,
  windows only ever train. The import refuses a job whose rows are not R4's.
- **Folds.** R4's six recording groups, one held out at a time (`tasks.csv`).
- **Pictures.** Each row's 600-sample cut becomes a GASF picture, a GADF picture or their fusion, at 224 px.
- **Network.** EfficientNet-B0, ImageNet-pretrained:
  - 12 epochs, batch 64, learning rate 0.001, no weight decay, seed 42;
  - balanced class weights, no augmentation, no tuning;
  - "interesting" called at P > 0.5 (also reported at 0.1).
- **Scoring.** `compare`, per recording group and pooled:
  - AUC and balanced accuracy for R4 (decision > 0) and for the CNN;
  - a paired bootstrap of AUC(R4) − AUC(CNN): 2,000 resamples, within each group, seed 20261026.
- **Cost.** 18 tasks, each under a minute of A100 at 1,160–1,450 pictures a second. The job's estimate assumed 400 a
  second, or 1.6 GPU-hours. Training loss fell from about 0.3 to below 0.01 in every task.

## Results

AUC (95 % interval), and R4 minus the CNN with its paired interval. n is judged events, of which "yes" are interesting.

| Held out | n / yes | R4 | GASF | GADF | Fusion | R4 − GASF | R4 − GADF | R4 − fusion |
|---|---|---|---|---|---|---|---|---|
| CO_fs2 | 256 / 88 | 0.989 | 0.986 | 0.988 | 0.987 | +0.003 [−0.009, 0.014] | +0.001 [−0.008, 0.010] | +0.002 [−0.009, 0.012] |
| LM_fs2 | 294 / 139 | 0.995 | 0.997 | 0.998 | 0.998 | −0.002 [−0.006, 0.001] | −0.003 [−0.008, 0.000] | −0.003 [−0.007, 0.001] |
| L_LM | 371 / 157 | 0.984 | 0.979 | 0.978 | 0.983 | +0.005 [−0.007, 0.017] | +0.006 [−0.006, 0.018] | +0.001 [−0.011, 0.013] |
| rec. 385 | 12 / 11 | 1.000 | 0.909 | 1.000 | 1.000 | +0.091 [0.000, 0.273] | 0 | 0 |
| M2_concat | 253 / 72 | 0.961 | 0.960 | 0.971 | 0.946 | +0.002 [−0.022, 0.024] | −0.010 [−0.035, 0.011] | +0.016 [−0.010, 0.042] |
| M2_aug | 1,270 / 864 | 0.951 | 0.957 | 0.951 | 0.960 | −0.006 [−0.017, 0.005] | +0.000 [−0.012, 0.011] | −0.009 [−0.020, 0.000] |
| **Pooled** | 2,456 / 1,331 | **0.971** [0.965, 0.977] | **0.971** [0.965, 0.977] | **0.970** [0.964, 0.975] | **0.973** [0.967, 0.978] | −0.000 [−0.006, 0.006] | +0.001 [−0.005, 0.007] | −0.002 [−0.007, 0.004] |

Balanced accuracy, pooled: R4 0.919; GASF 0.916 (0.923 at a 0.1 cut); GADF 0.915 (0.912); fusion 0.916 (0.913).

Per recording, the CNNs are a little higher than R4 on LM_fs2 and M2_aug and a little lower on CO_fs2 and
M2_concat. The largest gaps are on the smallest folds.

## Reading it

- **No picture type differs from R4 beyond chance.** Pooled, every gap is 0.002 or less and every interval lies
  within ±0.007. Per recording, no interval excludes zero.
- **Training data, not architecture.** On the same events, the reference CNNs scored 0.72–0.79 pooled
  (`tab:cnnvsr4`). Training on these rows lifts the same network by 0.18–0.25 AUC, to R4's level. Chapter 8's
  reference comparison therefore measures what the older labelling taught, not a ceiling on CNNs.
- **R4 is still the exam model.** It is cheaper (no GPU) and it was frozen before M4 was judged. The fair CNN's
  equality here is on R4's folds only.

## Caveats

1. **L_LM and recording 385 are not independent folds.** Recording 385 is a 4 h excerpt of MJu26a CH14, and L_LM is
   MJu26a CH10 and CH13–16 (×1000 plus an offset; Chapter 5).
   - Holding out recording 385 leaves the same signal in training through L_LM, so that fold's AUC of 1.000 says
     nothing.
   - Holding out L_LM leaves recording 385's 12 events in training, 12 of 2,085 training events.
   - This holds for R4 too (ledger C1), so it does not bias the comparison. It flatters both models' L_LM figure
     slightly.
2. **Recording 385's balanced accuracy is 0.5 for both models.** Its fold holds one non-interesting event.
3. **One seed per task, no augmentation, no search over the CNN's settings.** R4 chose its ridge penalty by
   leave-one-out within each training fold. Neither model saw a held-out fold before it was scored.
4. **No unseen-recording result.** The fair CNN is not in the M4 exam (Round 5 Q3) or the *S. commune* exam.
