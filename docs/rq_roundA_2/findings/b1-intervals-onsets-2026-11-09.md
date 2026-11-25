# B1 re-read on true fall onsets (and B12's intervals with it), 2026-11-09

Supersedes the event times of `b1-intervals-2026-11-05.md`; the protocol, runs, nulls and correction are unchanged.

## In plain words

**What was wrong.** The drop detector draws a box around each drop, and the box starts on a fixed time grid
(98.33 s steps), usually several minutes before the fall itself. The 5 Nov read timed every event from the left
edge of its box, like timing runners from when they reached the start line instead of when they started running.

**What was done.** The detector writes the true moment each fall begins into a label the database does not keep. So
every one of the 56 runs was recomputed from its own saved settings, on its own channel file, and checked against the
database before its onsets were used: all 56 matched window for window and depth for depth. Then B1 was run again,
unchanged except for the event times.

**What changed.** Very little. The box usually starts about the same distance before each fall, so when one gap is
measured box-to-box instead of fall-to-fall, most of the error cancels. A typical gap (1.8 h) moved by 3.5 min, and
LV moved by +0.004 at the median, sometimes up and sometimes down.

- **Against random timing:** still none of 44 channels differs after correction. The same two channels are more
  regular by CV2 (M2_aug CH4_A2, LM CH2).
- **Against shuffled gaps:** 15 of 44 channels (was 18) have neighbouring gaps more alike than shuffled, still on
  every recording. Three borderline channels moved just past q = 0.05. One M2_concat channel (CH7) alternates, as
  before.
- **Troughs instead of onsets** give the same counts.

**Verdict.** B1's reading stands: from one event to the next the timing is close to random, but the rate drifts
over hours to days, on every recording. The thesis can say so without the "window start" caveat.

**One knock-on change, in B12.** B12 compared interval statistics between recordings and species using the same
window starts. On onsets nothing passes correction, as before, but the one difference that did pass, between the
three *P. ostreatus* recordings (p = 0.047 and 0.036), is now at the margin (p = 0.053 and 0.055). Do not report it as
a difference.

## Method

- `scripts/thesis/b1_onsets.py` recomputes each `drop_detection_v1` run in memory: its own config from the database
  (detrend rolling mean 4,916.67 s → five-stage encoding, 98.33 s segments, same fraction 0.6, slope sigma 8 → drop
  detection defaults), on the channel's `npy_path` read the way `Working.execution._load_signal` reads it, with the
  recording's declared units. Every recomputed window must match the run's database rows (start, end and depth), or
  it stops. A run can hold two detections with one window (L_LM CH3, run 4023); they are paired by depth. Output:
  `docs/thesis/data/ch10_b1/b1_onsets.csv` (61 runs: B1's 56 and B12's five L_LM channels; 1,948 detections).
- `scripts/thesis/b1_intervals.py` now reads those onsets (`--times onset`, default). `--times trough` is the
  sensitivity read; `--times window_start` reproduces the 5 Nov files exactly (checked against git HEAD) and is
  kept as `*_windowstarts.csv`.
- `scripts/thesis/b12_intervals_onsets.py` repeats B12's interval tests (3 Nov and 5 Nov levels) on B12's own 45
  channels with onsets; the window-start versions are kept as `*_windowstarts.csv` in `docs/thesis/data/ch10_b12/`.
- Read-only throughout: the database is opened `mode=ro` and nothing is written under `DATA/`.

## How far the window start sat from the fall

| | value |
|---|---|
| onset after window start, median (IQR) | 582 s (194–591 s) |
| maximum | 4,632 s (77 min) |
| gaps between consecutive events | 1,567; median 1.8 h |
| change in each gap, median | 213 s |
| gaps changed by more than 10 % | 26 % (mostly gaps under an hour) |

## Results (onsets; window starts in brackets)

| recording | measurable | median LV | LV vs Poisson after BH | LV vs shuffled after BH: below / above | CV2 vs Poisson after BH: below / above |
|---|---|---|---|---|---|
| M2_aug | 16 | 0.99 (0.99) | 0 (0) | 7 / 0 (9 / 0) | 1 / 1 (1 / 0) |
| M2_concat | 15 | 1.40 (1.42) | 0 (0) | 2 / 1 (2 / 1) | 0 / 1 (0 / 0) |
| LM_fs2 | 4 | 0.83 (0.82) | 0 (0) | 2 / 0 (2 / 0) | 1 / 0 (1 / 0) |
| CO_fs2 | 2 | 1.14 (1.06) | 0 (0) | 1 / 0 (1 / 0) | 0 / 0 (0 / 0) |
| MJu26a_fs2 | 7 | 0.84 (0.84) | 0 (0) | 3 / 0 (4 / 0) | 0 / 0 (0 / 0) |
| **all** | **44** | 1.02 (1.04) | **0 (0)** | **15 / 1 (18 / 1)** | **2 / 2 (2 / 0)** |

- Uncorrected, LV leaves the Poisson band on 9 of 44 channels, as before; the closest to passing correction are three
  channels at q = 0.059 (LM CH2, more regular; M2_aug CH15_D2 and M2_concat CH7, burstier).
- The two CV2 "burstier" channels (M2_aug CH15_D2, 9 events; M2_concat CH7, 24 events) sit at q = 0.044 on onsets
  and q ≈ 0.07 on troughs, so they are not reported.
- The three channels that left the shuffled-gap count: M2_aug CH8_B2 (q 0.065), M2_aug CH12_C2 (0.054), MJu26a CH5
  (0.052).
- Channel names are 1-based; the CSVs index channels from 0.

B12 intervals (45 channels, Kruskal–Wallis permutation, onsets vs window starts): by dataset LV p 0.060 (0.057), CV2
0.11 (0.070); by species LV 0.09 (0.09), CV2 0.19 (0.16); by strain 0.26 (0.24), 0.43 (0.38); datasets within
*P. ostreatus* LV 0.053 (0.047), CV2 0.055 (0.036), no longer passing BH; within *H. erinaceus* 0.63 / 0.85 (0.63 /
0.85).

## Not changed

- The CH14 train (Chapter 10) is timed on troughs, and B4's census on the steepest fall, so neither used window
  starts.
- Figures 5.3 (anatomy of a train) and the B1 train figure already used recomputed onsets (8 Nov).
- SH and SO still have no `drop_detection_v1` run in the database (`roundb_extension_20261108/missing_geometry.json`).
  `b1_onsets.py` could regenerate them locally from the cluster specs, but only their detection counts could be
  checked, not their windows, so they are left out.
