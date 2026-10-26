# Drop-motif sequences: candidates for round-B questions

*Notes, 2026-10-26. Read-only fact-finding. Sources: `Plots/drop_motifs12b/FIGURES.md` (S3.1–S3.3, the
artefact banner, "The sequence extraction, for the record"), `Plots/drop_motifs12b/PROVENANCE.md` (§1, §3, §8,
§9), `Plots/drop_motifs12b/sequences.csv` / `sequences.json`, the fifteen
`Plots/drop_motifs12b/S3_1_sequence_morph_*.json` manifests, `Plots/drop_motifs12b/S3_2_morph_across_scales.json`,
`Plots/drop_motifs12b/run_report.json`, `Plots/drop_motifs10/CLAIMS.md` (rows 5, 18), and
`Pipelines/drop_motifs/DETECTION_AND_FIGURES.md`. Database columns were read through
`DATA/db/annotations.sqlite` opened `mode=ro`.*

## In plain words

Think of a dripping tap. One drip is an *event*. A *sequence* is a stretch where the drips keep coming at a
roughly steady beat, with no long silence in between. In the August–September drop-motif study an event is one
detected **drop** (a fall in voltage and its recovery) and a sequence is a run of at least **5** drops on one
channel where no gap is longer than **2×** that channel's own typical gap, and the run is either **regular**
(the gaps vary little: coefficient of variation ≤ 0.5, the `constant_gap` arm) or **steadily speeding up or
slowing down** (a straight-line trend in the gaps with R² ≥ 0.7, the `trend` arm). "Drift" is the last third's
gaps over the first third's: 1 means the beat held. The study then asked a second question of fifteen of
them: as the drops go by, does their *shape* change step by step in one direction (it **morphs**, like a word
slowly changing letter by letter into another word), or does it jitter around and end up near where it started
(it **wanders / returns**)? The test is simple: a run morphs if most step-to-step shape changes are smaller
than the change between its first and last drop.

Thresholds are recorded in `sequences.json → thresholds` (`gap_multiple 2.0`, `min_run_events 5`, `cv_max 0.5`,
`r2_min 0.7`, `drift_mark 0.2`, split per (catalogue id, channel) on that group's own median interval).
242 candidate runs, 117 rejected, **125 qualifying, 1,686 events**: Oyster 19 runs / 343 events (longest 67),
Reishi 98 / 1,298 (longest 114), Lion's mane 8 / 45 (longest 7). 117 runs qualify on the regular arm, 14 on the
trend arm, 8 on the trend arm only.

## Where they come from

| key prefix | species | recording in the app | catalogue ids |
|---|---|---|---|
| `oyster_*` | Oyster (*Pleurotus ostreatus*) | `M2_aug_concat_fs1.mat`, 1 Hz, recordings 1–16 | 1, 10, 20, 21, 22, 24, 25, 28, 33, 34, 35 |
| `reishi_*` | Reishi | `Fig2A_dt0p1.csv`, 10 Hz, recordings 466–470 | 900–904 = CH1–CH5 |
| `lionsmane_*` | Lion's mane (*Hericium erinaceus*) | `L_LM_Jul_26_J_raw.mat`, 10 Hz, region B = stored channel index 2 (recording 542) | 912 |

The `chN` in a key is the **stored, zero-based** channel index (the app prints it one-based: `ch3` on M2_aug is
`CH4_A2`). Start times are the first event's onset in seconds from the start of the recording. 117 of the 125
are already rows of the database's `sequences` table (imported 2026-09-21 from `Plots/drop_motifs11/sequences.csv`,
`source_kind = 'sequence_csv'`; event counts match for all 117); the 8 Lion's mane runs are **not imported**
(they were found by `drop_motifs12a` after the import), and the table also holds one retired run
(`sp385_id385_ch0_6140s`, Mushroom_260720) and 30 human sequences.

## Every sequence

"morph or return" is filled only for the fifteen S3.1 runs, which are the only ones the study measured for it
(`steps_below_endpoint_distance` / `n_steps` and `first_family`→`last_family` from each manifest). The
remaining 110 are "not measured". ⚠ = the detection artefact below.

| # | key | species / corpus | recording · stored ch | start (s · h) | n | duration (s) | median gap (s) | median fall (s) · depth (mV) | arm · drift | morph or return | DB `sequences.id` | figure |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `lionsmane_id912_ch2_1636467s` | Lion's mane / L_LM | L_LM_Jul_26_J_raw (10 Hz, region B) · 2 | 1,636,467 · 454.6 | 7 | 2,427 | 409.1 | 2.5 · 9.77 | constant_gap | returns (wanders): 3/6 steps < ends (0.50); F7->F9 | not imported | `Plots/drop_motifs12b/S3_1_sequence_morph_lionsmane_id912_ch2_1636467s.png` |
| 2 | `lionsmane_id912_ch2_1670017s` | Lion's mane / L_LM | L_LM_Jul_26_J_raw (10 Hz, region B) · 2 | 1,670,017 · 463.9 | 7 | 2,240 | 374.8 | 1.8 · 10.33 | constant_gap | returns (wanders): 2/6 steps < ends (0.33); F7->F9 | not imported | `Plots/drop_motifs12b/S3_1_sequence_morph_lionsmane_id912_ch2_1670017s.png` |
| 3 | `lionsmane_id912_ch2_1424772s` | Lion's mane / L_LM | L_LM_Jul_26_J_raw (10 Hz, region B) · 2 | 1,424,772 · 395.8 | 6 | 3,193 | 646.8 | 1.1 · 3.52 | constant_gap+trend | returns (wanders): 2/5 steps < ends (0.40); F3->F7 | not imported | `Plots/drop_motifs12b/S3_1_sequence_morph_lionsmane_id912_ch2_1424772s.png`; S3.2 row |
| 4 | `lionsmane_id912_ch2_1478675s` | Lion's mane / L_LM | L_LM_Jul_26_J_raw (10 Hz, region B) · 2 | 1,478,675 · 410.7 | 5 | 397 | 80.3 | 1 · 2.17 | trend · high drift | not measured | not imported | - |
| 5 | `lionsmane_id912_ch2_1485161s` | Lion's mane / L_LM | L_LM_Jul_26_J_raw (10 Hz, region B) · 2 | 1,485,161 · 412.5 | 5 | 1,519 | 418.3 | 0.9 · 2.91 | constant_gap · high drift | returns (wanders): 1/4 steps < ends (0.25); F7->F2 | not imported | `Plots/drop_motifs12b/S3_1_sequence_morph_lionsmane_id912_ch2_1485161s.png` |
| 6 | `lionsmane_id912_ch2_1531900s` | Lion's mane / L_LM | L_LM_Jul_26_J_raw (10 Hz, region B) · 2 | 1,531,900 · 425.5 | 5 | 1,053 | 323.5 | 1.2 · 4.55 | trend · high drift | not measured | not imported | - |
| 7 | `lionsmane_id912_ch2_1561744s` | Lion's mane / L_LM | L_LM_Jul_26_J_raw (10 Hz, region B) · 2 | 1,561,744 · 433.8 | 5 | 1,015 | 178.6 | 1.7 · 7.03 | trend · high drift | not measured | not imported | - |
| 8 | `lionsmane_id912_ch2_1626607s` | Lion's mane / L_LM | L_LM_Jul_26_J_raw (10 Hz, region B) · 2 | 1,626,607 · 451.8 | 5 | 817 | 162.5 | 2.4 · 9.85 | trend · high drift | not measured | not imported | - |
| 9 | `oyster_id10_ch3_1362824s` | Oyster / M2_aug | M2_aug_concat_fs1 (1 Hz) · 3 | 1,362,824 · 378.6 | 67 | 4,053 | 55.5 | 6 · 2.39 | constant_gap · high drift | returns (wanders): 25/66 steps < ends (0.38); F4->F4 same family | 1 | `Plots/drop_motifs12b/S3_1_sequence_morph_oyster_id10_ch3_1362824s.png`; S3.2 row |
| 10 | `oyster_id33_ch15_119520s` | Oyster / M2_aug | M2_aug_concat_fs1 (1 Hz) · 15 | 119,520 · 33.2 | 40 | 5,001 | 145.0 | 20 · 4.51 | constant_gap · high drift | returns (wanders): 18/39 steps < ends (0.46); F2->F3 | 2 | `Plots/drop_motifs12b/S3_1_sequence_morph_oyster_id33_ch15_119520s.png` |
| 11 | `oyster_id28_ch5_1394131s` | Oyster / M2_aug | M2_aug_concat_fs1 (1 Hz) · 5 | 1,394,131 · 387.3 | 29 | 72,581 | 2618.5 | 229 · 16.75 | constant_gap | **morphs**: 28/28 steps < ends (1.00); F9->F2 | 3 | `Plots/drop_motifs12b/S3_1_sequence_morph_oyster_id28_ch5_1394131s.png` |
| 12 | `oyster_id34_ch15_171006s` | Oyster / M2_aug | M2_aug_concat_fs1 (1 Hz) · 15 | 171,006 · 47.5 | 26 | 2,388 | 114.0 | 22.5 · 5.89 | constant_gap · high drift | returns (wanders): 11/25 steps < ends (0.44); F9->F2 | 4 | `Plots/drop_motifs12b/S3_1_sequence_morph_oyster_id34_ch15_171006s.png` |
| 13 | `oyster_id22_ch0_1049724s` ⚠ | Oyster / M2_aug | M2_aug_concat_fs1 (1 Hz) · 0 | 1,049,724 · 291.6 | 20 | 2,823 | 114.0 | 39 · 14.71 | constant_gap · high drift | returns (wanders): 0/19 steps < ends (0.00); F9->F3 | 5 | `Plots/drop_motifs12b/S3_1_sequence_morph_oyster_id22_ch0_1049724s.png` |
| 14 | `oyster_id28_ch5_1517760s` | Oyster / M2_aug | M2_aug_concat_fs1 (1 Hz) · 5 | 1,517,760 · 421.6 | 20 | 44,979 | 2110.0 | 215 · 5.12 | constant_gap · high drift | not measured | 6 | - |
| 15 | `oyster_id35_ch15_288397s` | Oyster / M2_aug | M2_aug_concat_fs1 (1 Hz) · 15 | 288,397 · 80.1 | 18 | 2,385 | 131.0 | 27 · 6.65 | constant_gap | **morphs**: 17/17 steps < ends (1.00); F9->F4 | 7 | `Plots/drop_motifs12b/S3_1_sequence_morph_oyster_id35_ch15_288397s.png` |
| 16 | `oyster_id24_ch1_1447810s` | Oyster / M2_aug | M2_aug_concat_fs1 (1 Hz) · 1 | 1,447,810 · 402.2 | 17 | 24,352 | 1472.0 | 52 · 10.88 | constant_gap · high drift | not measured | 8 | - |
| 17 | `oyster_id1_ch0_1212656s` | Oyster / M2_aug | M2_aug_concat_fs1 (1 Hz) · 0 | 1,212,656 · 336.8 | 14 | 16,351 | 992.0 | 132 · 22.26 | constant_gap+trend · high drift | not measured | 9 | - |
| 18 | `oyster_id22_ch0_1046790s` | Oyster / M2_aug | M2_aug_concat_fs1 (1 Hz) · 0 | 1,046,790 · 290.8 | 13 | 1,590 | 126.5 | 26 · 4.76 | constant_gap · high drift | not measured | 10 | - |
| 19 | `oyster_id22_ch0_1054092s` | Oyster / M2_aug | M2_aug_concat_fs1 (1 Hz) · 0 | 1,054,092 · 292.8 | 12 | 1,852 | 110.0 | 42.5 · 13.59 | constant_gap | not measured | 11 | - |
| 20 | `oyster_id28_ch5_1481382s` | Oyster / M2_aug | M2_aug_concat_fs1 (1 Hz) · 5 | 1,481,382 · 411.5 | 11 | 30,172 | 2913.5 | 252 · 8.38 | constant_gap | not measured | 12 | - |
| 21 | `oyster_id21_ch0_1137612s` | Oyster / M2_aug | M2_aug_concat_fs1 (1 Hz) · 0 | 1,137,612 · 316.0 | 10 | 1,584 | 197.0 | 12 · 0.16 | constant_gap | not measured | 13 | - |
| 22 | `oyster_id28_ch5_1358554s` | Oyster / M2_aug | M2_aug_concat_fs1 (1 Hz) · 5 | 1,358,554 · 377.4 | 10 | 21,382 | 2169.0 | 204 · 6.75 | constant_gap · high drift | not measured | 14 | - |
| 23 | `oyster_id25_ch1_1102685s` | Oyster / M2_aug | M2_aug_concat_fs1 (1 Hz) · 1 | 1,102,685 · 306.3 | 9 | 10,514 | 1134.0 | 38 · 3.81 | constant_gap · high drift | not measured | 15 | - |
| 24 | `oyster_id34_ch15_165960s` | Oyster / M2_aug | M2_aug_concat_fs1 (1 Hz) · 15 | 165,960 · 46.1 | 8 | 787 | 123.0 | 39 · 7.04 | constant_gap · high drift | not measured | 16 | - |
| 25 | `oyster_id10_ch3_1368603s` | Oyster / M2_aug | M2_aug_concat_fs1 (1 Hz) · 3 | 1,368,603 · 380.2 | 7 | 412 | 66.0 | 12 · 3.31 | constant_gap | not measured | 17 | - |
| 26 | `oyster_id10_ch3_1370457s` | Oyster / M2_aug | M2_aug_concat_fs1 (1 Hz) · 3 | 1,370,457 · 380.7 | 7 | 329 | 51.0 | 9 · 2.72 | constant_gap · high drift | not measured | 18 | - |
| 27 | `oyster_id20_ch0_1215838s` | Oyster / M2_aug | M2_aug_concat_fs1 (1 Hz) · 0 | 1,215,838 · 337.7 | 5 | 1,188 | 274.0 | 27 · 0.14 | constant_gap | not measured | 19 | - |
| 28 | `reishi_id903_ch3_606s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 3 | 606 · 0.2 | 114 | 279 | 2.6 | 0.7 · 0.57 | constant_gap | returns (wanders): 32/113 steps < ends (0.28); F3->F1 | 20 | `Plots/drop_motifs12b/S3_1_sequence_morph_reishi_id903_ch3_606s.png`; S3.2 row |
| 29 | `reishi_id901_ch1_724s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 724 · 0.2 | 59 | 105 | 1.8 | 0.7 · 0.20 | constant_gap | returns (wanders): 18/58 steps < ends (0.31); F4->F4 same family | 21 | `Plots/drop_motifs12b/S3_1_sequence_morph_reishi_id901_ch1_724s.png` |
| 30 | `reishi_id901_ch1_461s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 461 · 0.1 | 57 | 108 | 2.0 | 0.6 · 0.23 | constant_gap · high drift | **morphs**: 44/56 steps < ends (0.79); F9->F3 | 22 | `Plots/drop_motifs12b/S3_1_sequence_morph_reishi_id901_ch1_461s.png` |
| 31 | `reishi_id904_ch4_107s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 4 | 107 · 0.0 | 38 | 77 | 1.9 | 0.7 · 0.66 | constant_gap | **morphs**: 25/37 steps < ends (0.68); F8->F4 | 23 | `Plots/drop_motifs12b/S3_1_sequence_morph_reishi_id904_ch4_107s.png` |
| 32 | `reishi_id903_ch3_342s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 3 | 342 · 0.1 | 36 | 87 | 2.5 | 0.7 · 0.15 | constant_gap | returns (wanders): 17/35 steps < ends (0.49); F4->F1 | 24 | `Plots/drop_motifs12b/S3_1_sequence_morph_reishi_id903_ch3_342s.png` |
| 33 | `reishi_id901_ch1_640s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 640 · 0.2 | 30 | 57 | 1.7 | 0.7 · 0.26 | constant_gap · high drift | not measured | 25 | - |
| 34 | `reishi_id900_ch0_580s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 0 | 580 · 0.2 | 29 | 58 | 2.1 | 0.7 · 0.14 | constant_gap · high drift | not measured | 26 | - |
| 35 | `reishi_id901_ch1_971s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 971 · 0.3 | 27 | 51 | 2.0 | 0.7 · 0.19 | constant_gap | not measured | 27 | - |
| 36 | `reishi_id903_ch3_530s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 3 | 530 · 0.1 | 26 | 70 | 2.3 | 0.75 · 0.29 | constant_gap | not measured | 28 | - |
| 37 | `reishi_id901_ch1_121s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 121 · 0.0 | 24 | 53 | 2.2 | 0.7 · 0.49 | constant_gap | not measured | 29 | - |
| 38 | `reishi_id903_ch3_1136s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 3 | 1,136 · 0.3 | 24 | 61 | 2.6 | 0.7 · 0.39 | constant_gap | not measured | 30 | - |
| 39 | `reishi_id900_ch0_727s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 0 | 727 · 0.2 | 23 | 51 | 2.3 | 0.6 · 0.12 | constant_gap · high drift | not measured | 31 | - |
| 40 | `reishi_id901_ch1_1074s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 1,074 · 0.3 | 22 | 39 | 1.7 | 0.7 · 0.18 | constant_gap · high drift | not measured | 32 | - |
| 41 | `reishi_id901_ch1_413s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 413 · 0.1 | 21 | 35 | 1.4 | 0.7 · 0.18 | constant_gap | not measured | 33 | - |
| 42 | `reishi_id904_ch4_0s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 4 | 0 · 0.0 | 21 | 45 | 2.5 | 0.7 · 0.08 | constant_gap | not measured | 34 | - |
| 43 | `reishi_id900_ch0_889s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 0 | 889 · 0.2 | 19 | 46 | 2.3 | 0.7 · 0.16 | constant_gap · high drift | not measured | 35 | - |
| 44 | `reishi_id901_ch1_1036s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 1,036 · 0.3 | 19 | 33 | 1.7 | 0.7 · 0.20 | constant_gap | not measured | 36 | - |
| 45 | `reishi_id901_ch1_178s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 178 · 0.0 | 17 | 27 | 1.4 | 0.6 · 0.27 | constant_gap · high drift | not measured | 37 | - |
| 46 | `reishi_id901_ch1_25s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 25 · 0.0 | 16 | 36 | 2.5 | 0.7 · 0.67 | constant_gap · high drift | not measured | 38 | - |
| 47 | `reishi_id901_ch1_241s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 241 · 0.1 | 16 | 28 | 1.9 | 0.8 · 0.30 | constant_gap · high drift | not measured | 39 | - |
| 48 | `reishi_id901_ch1_340s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 340 · 0.1 | 16 | 28 | 1.8 | 0.6 · 0.28 | constant_gap | not measured | 40 | - |
| 49 | `reishi_id901_ch1_853s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 853 · 0.2 | 16 | 33 | 2.2 | 0.85 · 0.23 | constant_gap · high drift | not measured | 41 | - |
| 50 | `reishi_id904_ch4_701s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 4 | 701 · 0.2 | 16 | 41 | 2.5 | 1.05 · 0.11 | constant_gap | not measured | 42 | - |
| 51 | `reishi_id904_ch4_1065s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 4 | 1,065 · 0.3 | 16 | 35 | 2.2 | 0.85 · 0.08 | constant_gap | not measured | 43 | - |
| 52 | `reishi_id904_ch4_1137s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 4 | 1,137 · 0.3 | 16 | 44 | 3.0 | 1 · 0.13 | constant_gap · high drift | not measured | 44 | - |
| 53 | `reishi_id901_ch1_210s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 210 · 0.1 | 15 | 27 | 1.9 | 0.7 · 0.20 | constant_gap · high drift | not measured | 45 | - |
| 54 | `reishi_id902_ch2_98s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 2 | 98 · 0.0 | 15 | 16 | 0.9 | 0.4 · 0.16 | constant_gap · high drift | not measured | 46 | - |
| 55 | `reishi_id902_ch2_575s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 2 | 575 · 0.2 | 15 | 22 | 1.7 | 0.6 · 0.02 | constant_gap | not measured | 47 | - |
| 56 | `reishi_id900_ch0_415s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 0 | 415 · 0.1 | 14 | 28 | 2.0 | 0.6 · 0.11 | constant_gap · high drift | not measured | 48 | - |
| 57 | `reishi_id901_ch1_612s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 612 · 0.2 | 13 | 21 | 1.7 | 0.6 · 0.16 | constant_gap · high drift | not measured | 49 | - |
| 58 | `reishi_id902_ch2_117s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 2 | 117 · 0.0 | 13 | 16 | 1.2 | 0.6 · 0.21 | constant_gap | not measured | 50 | - |
| 59 | `reishi_id900_ch0_538s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 0 | 538 · 0.1 | 12 | 25 | 2.3 | 0.7 · 0.21 | constant_gap | not measured | 51 | - |
| 60 | `reishi_id900_ch0_974s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 0 | 974 · 0.3 | 12 | 24 | 2.1 | 0.7 · 0.11 | constant_gap · high drift | not measured | 52 | - |
| 61 | `reishi_id901_ch1_67s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 67 · 0.0 | 12 | 23 | 2.1 | 0.8 · 0.39 | constant_gap | not measured | 53 | - |
| 62 | `reishi_id904_ch4_460s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 4 | 460 · 0.1 | 12 | 33 | 3.1 | 0.8 · 0.59 | constant_gap | not measured | 54 | - |
| 63 | `reishi_id900_ch0_364s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 0 | 364 · 0.1 | 11 | 28 | 3.1 | 0.9 · 0.17 | constant_gap | not measured | 55 | - |
| 64 | `reishi_id902_ch2_877s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 2 | 877 · 0.2 | 11 | 18 | 1.7 | 0.6 · 0.02 | constant_gap | not measured | 56 | - |
| 65 | `reishi_id900_ch0_312s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 0 | 312 · 0.1 | 10 | 17 | 1.9 | 0.6 · 0.13 | constant_gap · high drift | not measured | 57 | - |
| 66 | `reishi_id900_ch0_454s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 0 | 454 · 0.1 | 10 | 20 | 2.1 | 0.7 · 0.11 | constant_gap | not measured | 58 | - |
| 67 | `reishi_id900_ch0_502s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 0 | 502 · 0.1 | 10 | 17 | 1.7 | 0.7 · 0.10 | constant_gap | not measured | 59 | - |
| 68 | `reishi_id900_ch0_1022s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 0 | 1,022 · 0.3 | 10 | 13 | 1.4 | 0.6 · 0.07 | constant_gap · high drift | not measured | 60 | - |
| 69 | `reishi_id901_ch1_96s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 96 · 0.0 | 10 | 21 | 2.3 | 0.6 · 0.71 | constant_gap · high drift | not measured | 61 | - |
| 70 | `reishi_id901_ch1_1157s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 1,157 · 0.3 | 10 | 19 | 2.0 | 0.7 · 0.20 | constant_gap | not measured | 62 | - |
| 71 | `reishi_id902_ch2_2s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 2 | 2 · 0.0 | 10 | 10 | 1.1 | 0.5 · 0.16 | constant_gap | not measured | 63 | - |
| 72 | `reishi_id903_ch3_966s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 3 | 966 · 0.3 | 10 | 26 | 2.7 | 0.7 · 0.17 | constant_gap | not measured | 64 | - |
| 73 | `reishi_id904_ch4_531s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 4 | 531 · 0.1 | 10 | 25 | 2.7 | 0.9 · 0.19 | constant_gap · high drift | not measured | 65 | - |
| 74 | `reishi_id900_ch0_263s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 0 | 263 · 0.1 | 9 | 20 | 2.8 | 0.8 · 0.09 | constant_gap | not measured | 66 | - |
| 75 | `reishi_id903_ch3_213s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 3 | 213 · 0.1 | 9 | 19 | 2.5 | 0.7 · 0.32 | constant_gap | not measured | 67 | - |
| 76 | `reishi_id904_ch4_379s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 4 | 379 · 0.1 | 9 | 22 | 2.9 | 0.8 · 0.29 | constant_gap · high drift | not measured | 68 | - |
| 77 | `reishi_id900_ch0_122s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 0 | 122 · 0.0 | 8 | 22 | 3.4 | 0.7 · 0.15 | constant_gap · high drift | not measured | 69 | - |
| 78 | `reishi_id900_ch0_1051s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 0 | 1,051 · 0.3 | 8 | 13 | 1.7 | 0.65 · 0.08 | constant_gap | not measured | 70 | - |
| 79 | `reishi_id900_ch0_1156s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 0 | 1,156 · 0.3 | 8 | 15 | 2.1 | 0.85 · 0.07 | constant_gap · high drift | not measured | 71 | - |
| 80 | `reishi_id901_ch1_924s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 924 · 0.3 | 8 | 13 | 1.7 | 0.8 · 0.19 | constant_gap | not measured | 72 | - |
| 81 | `reishi_id901_ch1_1181s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 1,181 · 0.3 | 8 | 14 | 2.1 | 0.7 · 0.12 | constant_gap · high drift | not measured | 73 | - |
| 82 | `reishi_id902_ch2_276s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 2 | 276 · 0.1 | 8 | 12 | 1.7 | 0.5 · 0.04 | constant_gap | not measured | 74 | - |
| 83 | `reishi_id903_ch3_256s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 3 | 256 · 0.1 | 8 | 18 | 2.0 | 0.75 · 0.10 | constant_gap · high drift | not measured | 75 | - |
| 84 | `reishi_id904_ch4_436s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 4 | 436 · 0.1 | 8 | 17 | 2.2 | 0.8 · 0.37 | constant_gap · high drift | not measured | 76 | - |
| 85 | `reishi_id904_ch4_773s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 4 | 773 · 0.2 | 8 | 17 | 2.6 | 0.75 · 0.17 | constant_gap · high drift | not measured | 77 | - |
| 86 | `reishi_id904_ch4_966s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 4 | 966 · 0.3 | 8 | 16 | 2.1 | 0.75 · 0.12 | constant_gap · high drift | not measured | 78 | - |
| 87 | `reishi_id904_ch4_1106s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 4 | 1,106 · 0.3 | 8 | 16 | 2.2 | 1 · 0.09 | constant_gap · high drift | not measured | 79 | - |
| 88 | `reishi_id900_ch0_825s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 0 | 825 · 0.2 | 7 | 17 | 2.8 | 0.8 · 0.12 | constant_gap · high drift | not measured | 80 | - |
| 89 | `reishi_id901_ch1_574s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 574 · 0.2 | 7 | 12 | 1.8 | 0.7 · 0.29 | constant_gap | not measured | 81 | - |
| 90 | `reishi_id901_ch1_833s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 833 · 0.2 | 7 | 10 | 1.7 | 0.6 · 0.24 | constant_gap · high drift | not measured | 82 | - |
| 91 | `reishi_id902_ch2_80s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 2 | 80 · 0.0 | 7 | 9 | 1.5 | 0.6 · 0.10 | constant_gap · high drift | not measured | 83 | - |
| 92 | `reishi_id903_ch3_92s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 3 | 92 · 0.0 | 7 | 18 | 2.9 | 0.8 · 0.34 | constant_gap | not measured | 84 | - |
| 93 | `reishi_id903_ch3_1103s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 3 | 1,103 · 0.3 | 7 | 15 | 2.6 | 0.8 · 0.43 | constant_gap · high drift | not measured | 85 | - |
| 94 | `reishi_id904_ch4_810s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 4 | 810 · 0.2 | 7 | 18 | 2.9 | 1 · 0.08 | constant_gap | not measured | 86 | - |
| 95 | `reishi_id904_ch4_930s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 4 | 930 · 0.3 | 7 | 14 | 2.2 | 0.8 · 0.16 | constant_gap · high drift | not measured | 87 | - |
| 96 | `reishi_id900_ch0_17s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 0 | 17 · 0.0 | 6 | 18 | 3.4 | 1 · 0.21 | constant_gap · high drift | not measured | 88 | - |
| 97 | `reishi_id900_ch0_148s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 0 | 148 · 0.0 | 6 | 14 | 3.0 | 0.65 · 0.15 | constant_gap · high drift | not measured | 89 | - |
| 98 | `reishi_id900_ch0_297s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 0 | 297 · 0.1 | 6 | 10 | 1.7 | 0.65 · 0.12 | constant_gap · high drift | not measured | 90 | - |
| 99 | `reishi_id900_ch0_1087s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 0 | 1,087 · 0.3 | 6 | 10 | 2.2 | 0.5 · 0.05 | constant_gap · high drift | not measured | 91 | - |
| 100 | `reishi_id901_ch1_701s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 701 · 0.2 | 6 | 8 | 1.3 | 0.9 · 0.33 | constant_gap · high drift | not measured | 92 | - |
| 101 | `reishi_id901_ch1_1133s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 1,133 · 0.3 | 6 | 8 | 1.3 | 0.65 · 0.14 | constant_gap · high drift | not measured | 93 | - |
| 102 | `reishi_id902_ch2_53s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 2 | 53 · 0.0 | 6 | 8 | 1.4 | 0.75 · 0.12 | constant_gap · high drift | not measured | 94 | - |
| 103 | `reishi_id902_ch2_255s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 2 | 255 · 0.1 | 6 | 7 | 1.4 | 0.65 · 0.03 | constant_gap | not measured | 95 | - |
| 104 | `reishi_id902_ch2_1121s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 2 | 1,121 · 0.3 | 6 | 6 | 1.3 | 0.2 · 0.02 | constant_gap · high drift | not measured | 96 | - |
| 105 | `reishi_id903_ch3_68s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 3 | 68 · 0.0 | 6 | 8 | 1.4 | 0.75 · 0.10 | trend · high drift | not measured | 97 | - |
| 106 | `reishi_id903_ch3_280s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 3 | 280 · 0.1 | 6 | 8 | 1.7 | 0.65 · 0.07 | trend · high drift | not measured | 98 | - |
| 107 | `reishi_id903_ch3_307s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 3 | 307 · 0.1 | 6 | 10 | 1.8 | 0.8 · 0.06 | constant_gap · high drift | not measured | 99 | - |
| 108 | `reishi_id904_ch4_78s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 4 | 78 · 0.0 | 6 | 8 | 1.7 | 0.75 · 0.11 | constant_gap · high drift | not measured | 100 | - |
| 109 | `reishi_id904_ch4_754s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 4 | 754 · 0.2 | 6 | 14 | 3.0 | 0.6 · 0.25 | constant_gap | not measured | 101 | - |
| 110 | `reishi_id900_ch0_403s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 0 | 403 · 0.1 | 5 | 8 | 1.6 | 0.7 · 0.15 | trend · high drift | not measured | 102 | - |
| 111 | `reishi_id900_ch0_950s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 0 | 950 · 0.3 | 5 | 12 | 2.9 | 1 · 0.14 | constant_gap+trend · high drift | not measured | 103 | - |
| 112 | `reishi_id901_ch1_452s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 452 · 0.1 | 5 | 5 | 1.2 | 0.6 · 0.27 | constant_gap · high drift | not measured | 104 | - |
| 113 | `reishi_id901_ch1_713s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 713 · 0.2 | 5 | 6 | 1.6 | 0.8 · 0.26 | constant_gap+trend · high drift | not measured | 105 | - |
| 114 | `reishi_id901_ch1_1119s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 1 | 1,119 · 0.3 | 5 | 4 | 1.1 | 0.7 · 0.17 | constant_gap · high drift | not measured | 106 | - |
| 115 | `reishi_id902_ch2_196s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 2 | 196 · 0.1 | 5 | 6 | 1.5 | 0.7 · 0.22 | constant_gap · high drift | not measured | 107 | - |
| 116 | `reishi_id902_ch2_617s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 2 | 617 · 0.2 | 5 | 7 | 1.9 | 0.7 · 0.09 | constant_gap+trend · high drift | not measured | 108 | - |
| 117 | `reishi_id903_ch3_27s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 3 | 27 · 0.0 | 5 | 10 | 1.9 | 0.6 · 0.10 | constant_gap · high drift | not measured | 109 | - |
| 118 | `reishi_id903_ch3_118s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 3 | 118 · 0.0 | 5 | 11 | 3.0 | 0.7 · 0.34 | constant_gap · high drift | not measured | 110 | - |
| 119 | `reishi_id903_ch3_510s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 3 | 510 · 0.1 | 5 | 15 | 4.3 | 0.8 · 0.31 | constant_gap | not measured | 111 | - |
| 120 | `reishi_id904_ch4_55s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 4 | 55 · 0.0 | 5 | 11 | 2.6 | 0.6 · 0.07 | constant_gap | not measured | 112 | - |
| 121 | `reishi_id904_ch4_561s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 4 | 561 · 0.2 | 5 | 13 | 3.7 | 1.1 · 0.38 | constant_gap+trend · high drift | not measured | 113 | - |
| 122 | `reishi_id904_ch4_593s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 4 | 593 · 0.2 | 5 | 9 | 2.2 | 0.9 · 0.33 | constant_gap · high drift | not measured | 114 | - |
| 123 | `reishi_id904_ch4_686s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 4 | 686 · 0.2 | 5 | 9 | 2.5 | 0.8 · 0.76 | constant_gap | not measured | 115 | - |
| 124 | `reishi_id904_ch4_878s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 4 | 878 · 0.2 | 5 | 8 | 1.6 | 0.6 · 0.08 | trend · high drift | not measured | 116 | - |
| 125 | `reishi_id904_ch4_997s` | Reishi / Fig2A | Fig2A_dt0p1 (10 Hz) · 4 | 997 · 0.3 | 5 | 10 | 2.2 | 0.7 · 0.15 | constant_gap · high drift | not measured | 117 | - |

## Caveats

1. **`oyster_id22_ch0_1049724s` is half artefact.** Stored as 20 events, it is really **10 cycles**: ten `base`
   pass rows (the sharkfins, 25.3–28.0 mV, falls of 54–132 s) strictly alternating with ten `fine` pass rows
   (2.3–4.1 mV, 19–24 s) sitting on each recovery shoulder. Its `n`, median interval and duty cycle are wrong by
   about ×2, its S3.1 waterfall mixes two populations, and its "0 of 19 steps smaller" morph score is an
   artefact of the alternation. The same `fine` pass ran over every Oyster span, so other Oyster runs may carry
   the same contamination — unmeasured. The fix (a depth floor relative to the span's own events, or a
   `fall_dominance` gate) belongs to the detector, not the figures. `FIGURES.md` banner; `PROVENANCE.md` §8.8, §9.
2. **The Lion's mane store is partial.** The store read is `Plots/drop_motifs12a/motifs_PARTIAL/` (4,023 events:
   Oyster 754, Reishi 2,425, Lion's mane 844 from **region B only**). `drop_motifs12a` stopped at its checkpoint on
   region A (stored index 3, 350 h) because the 10 Hz scale probe found the detector measuring noise there. Every Lion's mane
   count is a lower bound; all 8 runs are 5–7 events on one channel and "cannot settle the question either way".
   Re-run with `python Pipelines/drop_motifs/run_drop12b_figures.py --store Plots/drop_motifs12a/motifs --out
   Plots/drop_motifs12b` once region A lands. `PROVENANCE.md` §1, §8.1; `Plots/drop_motifs12a/PROVENANCE.md`.
3. **The family labels come from a Ward tree below the cophenetic floor.** The F1–F10 ids in "morph or return"
   are a cut at k = 10 of a pooled Ward tree (`figures11_s3._families_of` → `tree10.build`) whose cophenetic
   correlation is **0.585** (`run_report.json → family_cut`), below the 0.70 floor; `drop_motifs10` found every
   such tree below it (pooled 0.577, oyster 0.473; only reishi_10hz cleared it at 0.769), and round two found
   average linkage more faithful (0.839 vs 0.638). So "13 of 15 end in a different family" is a statement about
   an arbitrary cut, not a discovered partition. The step-vs-ends **morph count does not use the tree** — it is a
   direct Euclidean distance over 200-point z-normalised phase frames — and is the more trustworthy of the two.
   `CLAIMS.md` row 18 and its replacement sentence.
4. **The shape vector is not pure shape.** `CLAIMS.md` row 9: the 200-point normalised vector still decodes
   samples-per-event at 0.753 balanced accuracy (chance 0.25), so a "morph" along a run whose fall durations drift
   could be partly a resolution change. Check fall duration along the run before calling a morph biological.
5. **Rate and units.** Oyster comes from the 1 Hz M2_aug export; a 6 s fall is six samples. Reishi falls are
   ~0.7 s at 10 Hz (7 samples). S3.2's three rows cover about one order of fall duration (0.7–6 s), not three.
6. **S3.3 (Lion's mane close-pair depth ratio) has no effect** on the 10 Hz corpus (421 pairs, ratio 1.16×,
   permutation p = 0.111); round 11's p = 0.031 on 37 pairs did not survive. Not a seed.

## Best seeds for round B

1. **`oyster_id28_ch5_1394131s`** (DB id 3; M2_aug CH6, from 387 h, 29 events over 20 h, gap ~44 min, CV 0.19,
   drift 0.91). The clearest morph: **28 of 28** steps smaller than the ends (first-to-last 1.465, the largest),
   F9→F2. Regular beat, low drift, long-period sharkfins — exactly the shape an excitable-system (FHN) fit or
   `chain_cycles` would be tried on, and a slow morph is a testable claim (shape vs position in the run against
   shuffled order).
2. **`oyster_id35_ch15_288397s`** (DB id 7; M2_aug CH16, 18 events over 40 min, CV 0.26, drift 1.09). **17 of
   17** steps smaller; a second, independent channel showing the same continuous morph, at a much faster beat
   (131 s) — the pair lets a question ask whether morphing depends on tempo.
3. **`reishi_id901_ch1_461s`** (DB id 22; Fig2A CH2, 57 events in 108 s, 0.79 steps smaller, drift 1.29, flagged
   high drift). The only long run that morphs *while its beat drifts*: the natural seed for "does shape track
   rhythm?" within a sequence. Pair with **`reishi_id904_ch4_107s`** (DB id 23, 38 events, 0.68) as the
   second Reishi morph.
4. **Controls that return rather than morph:** **`oyster_id10_ch3_1362824s`** (DB id 1; M2_aug CH4, the longest
   Oyster run, 67 events, F4→F4, 0.38) and **`reishi_id903_ch3_606s`** (DB id 20; the longest run of all, 114
   events, 0.28). Long, regular, and stable in shape — the right null-like comparison for any "morph" question,
   and both are S3.2 rows. `oyster_id10` also overlaps a human sequence on the same channel
   (`human_r4_ch3_1362600s`), so it can anchor a human-vs-machine check.

**Avoid as seeds:** `oyster_id22_ch0_*` (artefact), every `lionsmane_*` run (partial store, ≤ 7 events, not in
the database), and any claim resting on the family ids alone.
