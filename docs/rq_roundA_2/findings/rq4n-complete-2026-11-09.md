# The completed 2 Hz detector sweep: audit, counts, B5 timing and B11 agreement (9 November 2026)

## In plain words

Think of 43 smoke alarms, each tuned differently, fitted in three new houses: the recordings MJu26a, SH and SO.
Every alarm was also tested in a "dummy house". The dummy is a copy of the same house with the timing of
everything scrambled and the overall amount of activity kept; this is the phase-randomised surrogate. Three
questions:

1. **Did every alarm report back?** Yes. All 1,014 alarm-in-a-room jobs are complete, and their checksums match.
2. **Do the alarms get busy and quiet at the same times of day (B5)?** Yes, in all three houses. Busy stretches are
   shared far more than chance would give, and far more than in the dummy houses.
3. **When one alarm goes off, do several different kinds go off at the same moment (B11)?** Yes, and much more often
   than in the dummy houses. Broad agreement (7 or more kinds at once) is 3–9 times as common in the real recording
   as in its surrogate. The share of such events, 10–16 %, sits at the low end of the five older recordings in
   Chapter 6, which show 17–29 %.

**A warning about the earlier version of this note.** It was written this morning, when only 702 of the 1,014 jobs
had timings on the PC. It said that broad agreement was rare on 2 Hz (at most 5 % reaching 7+ families) and absent
on SH. That was an artefact of five classical families being missing. Once their timings were recomputed, the
picture changed to the one above. The partial outputs are kept, with a `_partial` suffix.

## Method

The script is `scripts/thesis/rq4n_complete_20261109.py`, with the stages `audit`, `counts`, `geom`, `b5`, `b11`
and `tables`. Its docstring says how to rerun each one. The recomputation is done by
`scripts/thesis/rq4n_recompute_missing_20261109.py` and checked by `scripts/thesis/rq4n_recompute_check_20261109.py`.

The live DB and every scratch.sqlite were opened with `?mode=ro`, and nothing was imported.

- **Audit.** This is `audit_recovery_return_20261108.py` re-pointed at `DATA/derived/hpc/recovery_20261108_latest/`.
  The manifest's `recovery_20261108/` paths are remapped to `_latest/`.
  - It checks the spec hash of every recovery task, the sha256 of the 440 runtime files and of the 4 CNN checkpoints,
    and the byte size of every returned cache folder.
  - It merges with the 8 Nov audit by (original out, task).
  - The seed half is unchanged: 64 channels × 200 draws.
- **Counts.** These come from `result.json`: `run.detections` for the real run and `draws.detections` for its single
  phase-randomised surrogate. Families come from `candidate_events.family_of`. The four CNN models of one scale form
  one family, and `mp_*` is `matrix_profile`.
- **Geometry index.** The spans are channel-absolute (`spans.absolute_bounds`; every run is whole-channel, 0..n).
  They come from these sources, in order:
  1. the recovery `work/task{N}/scratch.sqlite`, which holds the real run and its surrogate via `surrogate_of_run_id`;
  2. the original returns' scratch.sqlite copies, including the nested duplicate tree;
  3. the DB, sessions 13–15. This takes the longest-span, newest real template run per (channel, setting), as in
     `load_sweep_detections`, with its paired surrogate;
  4. the returned `spanset.json`, which gives real geometry only. This is the same reader as
     `diversity_review_20261108.py`;
  5. **a recomputation on this PC.**

  A source is accepted only when its count equals result.json.
- **The recomputation.** About 300 cheap classical tasks never had their timings returned: their result.json lists no
  cache entries, and their scratch.sqlite stayed on the cluster. Another ~80 were missing only the surrogate.
  - They were rerun with the cluster's own task runner, `chain_job.run_task`, using 3 workers.
  - Every write went into the session scratchpad. `_cluster_environment` redirects `STEP_CACHE_ROOT` into the task's
    own return folder and turns the persist hooks off, and the scratch DB lives in the task's `work/` folder.
  - A recomputed task is accepted only when its spec, config and prefix hashes match **and both its real and its
    surrogate counts equal the cluster's**.
- **B5.** This uses `b5_map_timing.bin_counts`, `comodulation` and `shift_null`: 3-h bins from each channel's start,
  200 circular shifts, seed 20261103, and channel bands from z-scored rates.
  - It runs per channel over all settings with real geometry. The 1-minute CNNs are included, as in the
    five-recording B5.
  - The surrogate is run over the settings that have surrogate geometry, and the real data is also rerun on exactly
    those settings.
- **B11.** This uses `candidate_events.build_events` and `add_agreement`. The rule is the one from Settings:
  reciprocal IoU 0.5, onset 0.25, and agreement when the overlap is at least half the shorter span.
  `NEGATIVE_CONTROLS` (the 1-minute CNNs) are left out.
  - Three tables are built per recording: real over all settings; surrogate; and real restricted to the surrogate's
    (channel, setting) pairs, which is the like-for-like comparison.
  - Chapter 6's saved tables (`DATA/derived/candidate_events/*/events.parquet`) were read, without changes, for
    comparison.

## 1. Audit: 1,014 / 1,014 complete, 129 / 129 whole settings

| check | result |
|---|---|
| recovery tasks | 285 / 285 complete (CPU 29, CNN 250, mpA 3, mpB 3); all have scratch.sqlite |
| spec-hash mismatches | 0 |
| runtime files (sha256) | 440 checked, 0 mismatches |
| CNN checkpoints (sha256) | 4 checked, 0 mismatches |
| returned cache folders, size ≠ result.json | 0 |
| all tasks | 1,014 complete (MJu26a 674/674, SH 170/170, SO 170/170) |
| whole settings | 129 / 129 (43 per recording) |

The 10 tasks refused in the 8 Nov audit and the 173 missing tasks are all among those recovered. Files:
`docs/thesis/data/recovery_latest_20261109/{audit.json, settings.csv, pending.csv}`. Nothing is pending.

## 2. Counts

All twelve Table 10.2 rows are confirmed exactly (`table10_2_check.csv`):

| detector | MJu26a | SH | SO |
|---|---|---|---|
| Drop v1 | 463/33 | 21/0 | 28/0 |
| OASIS default | 127,429/2,007 | 20,095/353 | 25,556/364 |
| OASIS threshold 5 | 2,453/68 | 859/19 | 400/11 |
| Wavelet encoded default | 1,883/38,714 | 21/7,241 | 12/7,286 |

The table below gives family totals over all 43 settings, real and surrogate, with one surrogate draw per task. It
comes from result.json and does not depend on geometry.

| family | settings | MJu26a real | MJu26a sur. | SH real | SH sur. | SO real | SO sur. |
|---|---:|---:|---:|---:|---:|---:|---:|
| BEADs_invert_detect_v1 | 3 | 2,439 | 25,118 | 1,135 | 12,599 | 574 | 6,918 |
| OASIS_Deconvolution | 3 | 358,284 | 7,175 | 53,380 | 1,218 | 70,066 | 1,211 |
| Wavelet_detection_prototype | 3 | 167,199 | 214,236 | 27,632 | 38,601 | 23,185 | 37,972 |
| cnn_10min | 4 | 26,648 | 22,377 | 2,993 | 3,444 | 2,394 | 3,014 |
| cnn_1min (negative control) | 4 | 226,525 | 467,918 | 17,618 | 99,610 | 10,446 | 81,817 |
| cnn_60min | 4 | 4,948 | 3,964 | 1,263 | 695 | 1,250 | 607 |
| deconvolved_troughs | 3 | 414,921 | 4,526 | 119,583 | 957 | 103,298 | 922 |
| drop_detection_v1 | 3 | 1,529 | 460 | 58 | 36 | 75 | 27 |
| drop_detection_v5 | 3 | 2,466 | 3,717 | 72 | 16 | 129 | 9 |
| matrix_profile | 1 | 62,527 | 7,248 | 22,148 | 6,015 | 80,053 | 10,042 |
| noise_threshold | 3 | 31,376 | 1,023 | 7,407 | 226 | 8,260 | 199 |
| signal_threshold | 3 | 3,911 | 116,630 | 3,635 | 76,986 | 1,519 | 37,931 |
| symbol_search | 3 | 111,312 | 443,710 | 1,808 | 85,295 | 17,244 | 86,093 |
| wavelet_encoded | 3 | 5,072 | 117,050 | 104 | 21,962 | 172 | 22,011 |
| **all (14 families)** | 43 | 1,419,157 | 1,435,152 | 258,836 | 347,660 | 318,665 | 288,773 |

Each matrix-profile setting ran on 2 channels per recording. Per-setting rows are in `counts_by_setting.csv`.

## 3. Geometry coverage

| | MJu26a | SH | SO | all | partial read (this morning) |
|---|---:|---:|---:|---:|---:|
| tasks | 674 | 170 | 170 | 1,014 | |
| real geometry | 664 | 168 | 169 | **1,001** | 702 |
| surrogate geometry | 646 | 165 | 168 | **979** | 619 |
| whole settings, real / surrogate | | | | 122 / 117 of 129 | 77 / 69 |

Where the geometry came from:

| | recomputed on PC | recovery scratch | original scratch | returned spanset | DB |
|---|---:|---:|---:|---:|---:|
| real | 299 | 285 | 267 | 78 | 72 |
| surrogate | 360 | 285 | 262 | — | 72 |

The recomputation (`recompute_check.csv`) produced 370 result files, 368 of them complete, and 360 were accepted.
Ten were not:

- **Eight BEADs tasks.** Their real or surrogate count is off by 1–2 from the cluster's, for example 446 against 445.
  This is the known BEADs ±1–3 cluster/PC difference. The affected tasks are:
  - MJu26a delta_mv_5 CH10, CH13, CH15 and CH16;
  - MJu26a delta_mv_25 CH13;
  - SH default CH3;
  - SH delta_mv_5 CH4;
  - SO delta_mv_5 CH3.

  None of these was accepted, so their geometry is missing.
- **Two Wavelet-prototype tasks** (SH default CH4, SO epsilon 0.1 CH2) ran out of memory on the PC, which could not
  allocate 1.96 GiB.
- The run was stopped at 11:50 to make the deadline. **Fourteen** surrogate-only Wavelet-prototype tasks had not been
  reached by then (MJu26a 12, SH 2).

Families still incomplete (tasks with geometry / tasks):

| recording | family | tasks | real | surrogate |
|---|---|---:|---:|---:|
| MJu26a | BEADs_invert_detect_v1 | 48 | 44 | 43 |
| MJu26a | Wavelet_detection_prototype | 48 | 48 | 36 |
| MJu26a | cnn_1min (excluded from B11) | 64 | 58 | 53 |
| SH | BEADs_invert_detect_v1 | 12 | 10 | 10 |
| SH | Wavelet_detection_prototype | 12 | 12 | 9 |
| SO | BEADs_invert_detect_v1 | 12 | 11 | 11 |
| SO | Wavelet_detection_prototype | 12 | 12 | 11 |

Every other family is complete for both real and surrogate. All 13 B11 families are now available on all three
recordings; in the partial read there were 12, 9 and 8.

**Writes outside the scratchpad.** None in the step cache: `DATA/derived/step_cache` holds 6,442 entries, and its
mtime is unchanged. `DATA/derived` and `DATA/db` mtimes are unchanged, and `DATA/Results` does not exist. One file
under DATA/ changed during the run: `DATA/db/annotations.sqlite-shm`. That is SQLite's WAL shared-memory index,
which read-only connections update; the researcher's bridge on port 8765 may also touch it. It is not data.

## 4. B5: do the detectors' rates rise and fall together?

The bins are 3 h wide: 212 per MJu26a channel and 160 per SH or SO channel. C is the mean pairwise Spearman
correlation of the settings' binned counts.

| recording | channels | settings / channel (median) | real C median | shift mean | channels beating shifts | surrogate settings / channel | surrogate C median | surrogate channels beating shifts | real C, surrogate's settings |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|
| MJu26a | 16 | 42 | **0.21** | 0.00 | 16/16 | 38–42 | 0.02 | 16/16 | 0.22 |
| SH | 4 | 42 | **0.26** | 0.00 | 4/4 | 40–42 | 0.02 | 4/4 | 0.27 |
| SO | 4 | 42 | **0.27** | 0.00 | 4/4 | 41–43 | 0.02 | 4/4 | 0.27 |

Channel bands ask whether the channels rise and fall together. Each cell is C, with the shift p in brackets:

| recording | real, all settings | real, surrogate's settings | surrogate |
|---|---|---|---|
| MJu26a | 0.14 (0.005) | 0.13 (0.005) | 0.25 (0.005) |
| SH | 0.07 (0.23) | 0.07 (0.27) | 0.25 (0.005) |
| SO | 0.41 (0.005) | 0.41 (0.005) | 0.17 (0.005) |

**No 3-hour bin goes silent.** Every bin on every channel has detections, and the lowest bin total is 25–27.

**What moved against the partial read.**
- The median real C rose on MJu26a (0.17 → 0.21) and SO (0.24 → 0.27), and stayed at 0.26 on SH.
- The surrogate stays at 0.02, with 3/4 → 4/4 SH channels beating shifts.
- The bands barely moved: MJu26a 0.15 → 0.14, SH 0.09 → 0.07 (still not significant), SO 0.38 → 0.41. The surrogate
  bands went from 0.27/0.17/0.18 to 0.25/0.25/0.17.

**Against earlier work.**
- The 5 Nov 31-setting read gave 0.33/0.46/0.42.
- The five main recordings gave real C of 0.21–0.35, against 0.00 shifted and 0.02–0.04 surrogate. The 2 Hz
  recordings (0.21–0.27) now sit inside that range, with the same separation from both nulls.
- The band pattern holds. SO's channels share a common time course; SH's do not. On MJu26a the real bands (0.14) are
  weaker than the surrogate's (0.25), because phase randomisation keeps each channel's slow trend, and those trends
  are shared.

Files: `b5_summary.json`, `b5_channels.csv`.

## 5. B11: do the detectors find the same events?

The table gives the share of candidates in each band of agreeing families, with the 1-minute CNNs excluded.

| recording | geometry | settings | families | detections | candidates | 1–2 | 3–4 | 5–6 | 7–8 | 9+ |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MJu26a | real, all settings | 39 | 13 | 1,191,443 | 852,607 | 14.4 % | 39.8 % | 29.5 % | 10.9 % | 5.3 % |
| MJu26a | real, surrogate's settings | 38 | 13 | 1,158,467 | 836,650 | 15.0 % | 41.4 % | 28.6 % | 10.9 % | 4.1 % |
| MJu26a | surrogate | 38 | 13 | 923,027 | 788,691 | 9.7 % | 65.3 % | 23.4 % | 1.5 % | 0.1 % |
| SH | real, all settings | 39 | 13 | 240,398 | 164,765 | 11.7 % | 38.2 % | 34.4 % | 12.2 % | 3.5 % |
| SH | real, surrogate's settings | 36 | 13 | 226,859 | 154,888 | 11.0 % | 39.2 % | 33.8 % | 12.7 % | 3.3 % |
| SH | surrogate | 36 | 13 | 227,014 | 203,168 | 7.7 % | 56.1 % | 32.5 % | 3.6 % | 0.1 % |
| SO | real, all settings | 39 | 13 | 308,078 | 235,575 | 18.9 % | 39.5 % | 31.6 % | 8.0 % | 2.0 % |
| SO | real, surrogate's settings | 34 | 13 | 305,409 | 235,023 | 19.2 % | 39.6 % | 31.6 % | 7.9 % | 1.7 % |
| SO | surrogate | 34 | 13 | 206,111 | 180,105 | 8.2 % | 61.6 % | 27.3 % | 2.8 % | 0.1 % |

The like-for-like comparison, real against surrogate on the same (channel, setting) pairs:

| recording | 5+ real | 5+ surrogate | ratio | 7+ real | 7+ surrogate | ratio | 7+ real, all settings | 9+ real, all settings |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MJu26a | 43.6 % | 25.0 % | 1.7 | 15.0 % | 1.6 % | 9.4 | 16.3 % | 5.3 % |
| SH | 49.8 % | 36.2 % | 1.4 | 16.0 % | 3.7 % | 4.3 | 15.7 % | 3.5 % |
| SO | 41.2 % | 30.2 % | 1.4 | 9.6 % | 2.9 % | 3.3 | 10.0 % | 2.0 % |

Chapter 6's saved tables (`DATA/derived/candidate_events/<key>/events.parquet`, read without changes) are given for
comparison. Each cell is the share of candidates at that level.

| recording | candidates | families | 1–2 | 3–4 | 5–6 | 7–8 | 9+ | 7+ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CO_fs2 | 229,807 | 13 | 18.7 % | 36.5 % | 27.6 % | 11.8 % | 5.4 % | 17.2 % |
| LM_fs2 | 295,239 | 13 | 11.0 % | 31.3 % | 29.1 % | 18.7 % | 9.9 % | 28.6 % |
| L_LM_Jul_26_J_raw_fs2 | 616,299 | 13 | 11.4 % | 35.1 % | 30.8 % | 14.9 % | 7.7 % | 22.6 % |
| M2_aug_concat_fs1 | 1,502,319 | 13 | 6.4 % | 33.8 % | 32.4 % | 20.0 % | 7.4 % | 27.4 % |
| M2_concat_fs1 | 455,907 | 12 | 15.7 % | 36.4 % | 26.2 % | 14.9 % | 6.8 % | 21.7 % |
| *five judged, total* | *3,099,571* | | | | | | | |
| M4_aug_concat_fs1 (held out) | 832,136 | 13 | 13.7 % | 48.6 % | 27.2 % | 6.8 % | 3.7 % | 10.5 % |
| Schizophyllum commune | 32,453 | 13 | 3.0 % | 35.2 % | 48.5 % | 13.1 % | 0.2 % | 13.3 % |

**Reading.**
- On all three 2 Hz recordings the detectors find the same events far more often than chance. Seven or more of 13
  families agree on 9.6–16.0 % of real candidates, against 1.6–3.7 % of surrogate candidates, a factor of 3.3–9.4.
  At 5+ families the excess is smaller, ×1.4–1.7.
- Over all settings, the 2 Hz distribution has 10–16 % of candidates at 7+ and 2.0–5.3 % at 9+. That is at or just
  below the low end of the five judged recordings (17–29 % at 7+, 5.4–9.9 % at 9+). It is closest to CO, the held-out
  M4_aug and *S. commune*.
- Read with Chapter 6's acceptance curve (0–5 % at 1–2 families, 40–63 % at 9+), the 2 Hz recordings have a usable
  9+ stratum: about 45,000 candidates on MJu26a, 5,700 on SH and 4,700 on SO. That curve was not measured on 2 Hz.

**What moved against the partial read.** Everything at the high levels changed:
- **MJu26a.** 7+ like-for-like went from 3.4 % against 0.19 % to 15.0 % against 1.6 %.
- **SH.** It went from no excess (5+: 3.2 % against 4.2 %) to a clear excess: 5+ 49.8 % against 36.2 %, and 7+
  16.0 % against 3.7 %.
- **SO.** 7+ went from 0.14 % against 0.02 % to 9.6 % against 2.9 %.
- **All settings.** 7+ went from 5.4/0.03/1.2 % to 16.3/15.7/10.0 %, and 9+ from at most 0.25 % to 5.3/3.5/2.0 %.

The partial read had only 8–12 families, and on SH and SO it was missing BEADs, drop v1/v5, noise threshold and
signal threshold. With fewer families, fewer of them can agree.

Files: `b11_summary.json`, `b11_events_{MJu26a_fs2,SH_fs2,SO_fs2}_real.parquet`, `tables.md`. The morning's versions
are `*_partial.*`.

## Uncertain or worth knowing

- B5 includes the 1-minute CNNs, as the five-recording B5 did. B11 excludes them.
- B11 detection ids are synthetic: geometry taken from scratch files has no DB ids. No human labels are attached, so
  this is a census and not a precision estimate.
- The geometry of 299 real tasks and 360 surrogate tasks comes from the PC recomputation. These were accepted only
  on exact count and hash agreement with the cluster, so the spans are the same computation. They were not compared
  span by span against the cluster, because the cluster spans never came back.
- MJu26a still lacks 12 Wavelet-prototype surrogate tasks. Its like-for-like table therefore uses 38 of 39 settings,
  with the Wavelet prototype on 36 of 48 channel-settings.
- The geometry index (~3.4 M rows) is a parquet in the session scratchpad, not in the repo. `geom` rebuilds it in
  about 10 s, given the recomputed scratch files (`RQ4N_RECOMPUTE`).
