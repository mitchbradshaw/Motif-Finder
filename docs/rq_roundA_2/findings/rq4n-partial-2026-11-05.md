# The 2 Hz sweep, first part: imported, and what it changes (2026-11-05)

## In plain words

The cluster run for the three 2 Hz recordings (MJu26a, SH and SO) stopped partway, most likely on space. A job is one
detector setting on one recording; it can only go into the app when every channel of it is back.
- **31 of its 129 jobs came back whole**, and they are now in the app.
- **The other 702 tasks** are packed to run again (`docs/thesis/hpc/rq4_newsets_20261027/remaining_20261105/`).

**What the new runs change:**
- **B4 (do events travel between electrodes?)** now covers MJu26a. Its channels fire together more often than chance,
  but at the same instant, with no delay. That is the same answer as M2_aug: no evidence of propagation.
- **B5 (when do detectors fire?)** holds on all three new recordings. Detectors get busy and quiet together, far more
  than scrambled copies do. Only 9–13 settings ran, though, so this is weaker evidence.
- **B1 (are the gaps between events random?)** now uses MJu26a itself instead of its five-channel copy (L_LM). The
  answer is unchanged.
- **B11 (do detectors find the same events on the new recordings?)** still needs the whole sweep.

## The import

- **Returned:** 312 of 1,014 tasks were complete; the failure lists were empty, so nothing crashed. The returned
  folder was 15 GB. It was brought back to the repo root and moved into `docs/thesis/hpc/rq4_newsets_20261027/`
  (`*_out/return`, `*_out/work`, `state/`).
- **Per-job status:** `scripts/thesis/rq4n_status.py` writes `rq4n_status.json`.
  - **Whole jobs:**
    - MJu26a 13: OASIS ×3, deconvolved troughs ×3, `drop_detection_v1`, symbol search (base and 40 s), wavelet
      encoded ×3, and the Dehshibi wavelet prototype;
    - SH 9 and SO 9: OASIS ×3, deconvolved troughs ×3 and wavelet encoded ×3.
  - **Part-done jobs:**
    - MJu26a wavelet prototype ε 0.02: 14 of 16 channels;
    - `cnn_fusion3_1min`: 5 of 16;
    - symbol search 10 s: 13 of 16. Three were refused for memory: a 1.7 GiB array with eight tasks to a node.
- **Import route:** through the 8765 project bridge.
  - **Backup first:** `DATA/db/backups/20261105-124005.sqlite`.
  - **Sessions:** one Discovery session per recording (MJu26a_fs2_rq4 13, SH_fs2_rq4 14, SO_fs2_rq4 15).
  - **Adopt:** `rq4_overnight.py adopt --only <whole jobs> --apply --allow-project`. Logs are
    `adopt_<recording>.log` in the bundle folder.
  - **Result:** 31 of 31 imported.
- **One failure, fixed:** SO's `wavelet_encoded__level_3` failed once, part-way through restoring its cache, because a
  Windows file rename was refused.
  - **What made it worse:** the clean-up had already freed that job's restored entries.
  - **The repair:** put them back from the step cache (sizes checked against `result.json`), then imported again.
  - **The guard now:** `scripts/thesis/rq4n_free_returned.py` frees a task's returned cache only when all of its
    entries are in the step cache.
- **Space:** 12.7 GB of returned caches were freed once they duplicated the step cache, leaving 28 GB free on C:.
  Discovery is back on M2_aug (session 9).

## B4 on MJu26a (Explore › Cross-channel, census 5, hash `f83f97f2…`)

Run through the site (`POST /api/cross/census`); the tables come from `scripts/thesis/b4_cross_channel.py` on backup
`DATA/db/backups/20261105-130347.sqlite` (`docs/thesis/data/ch10_b4/`).
- **Counts:** 463 `drop_detection_v1` events on 16 channels. Packs are not set, so all 120 pairs count as one pack.
- **Co-occurrences:** 16, against 3.2 expected under rotation (95th percentile 7; p 0.001).
- **Pairs:** ten survive BH (q 0.004), on one to three co-occurrences each.
- **Bins:** 7 copies (artefact), 1 possible propagation and 8 independent recurrences.
- **Timetables:** CH1–CH2 and CH1–CH6 both have median lag 0 s, p 0.25 and 0.23 against the lag null. Neither beats
  it. The only co-occurrence with a lag (CH3–CH7, 3.5 s) is a single event, so no timetable can be made from it.
- **Verdict:** as on M2_aug, there is no evidence of propagation. Channels fire together more than chance, at the
  same instant. Without packs, a shared driver cannot be separated from the setup.

## B5 on the 2 Hz sets (`docs/thesis/data/ch10_b5_newsets/summary.json`)

`scripts/thesis/b5_map_timing.py` ran, unchanged, on the three recordings, with 200 draws, 3-hour bins and the Map's
binning.

| recording | channels | settings | co-modulation (median) | shifted | surrogate | channel bands, real (p) | surrogate (p) |
|---|---|---|---|---|---|---|---|
| MJu26a (2 Hz) | 16 | 13 | 0.33 | 0.00 | 0.08 | 0.15 (0.005) | 0.28 (0.005) |
| SH (2 Hz) | 4 | 9 | 0.46 | 0.00 | 0.13 | 0.07 (0.24) | 0.29 (0.005) |
| SO (2 Hz) | 4 | 9 | 0.42 | 0.00 | 0.13 | 0.40 (0.005) | 0.04 (0.16) |

- **Every channel beats its shifts.** That holds on all 24 channels, for the recording and its surrogate alike.
- **The surrogates co-modulate more here** (0.08–0.13, against 0.02–0.04 on the five main recordings). With only 9–13
  settings from three families, the settings share more events, so read the margin, not the p.
- **Channel banding is shown on SO only.** On MJu26a and SH the surrogate bands as much as the recording, or more.

**Screenshots** (Discovery › Map, dataset level, rows sorted by detections), in `docs/thesis/figures/roundb/`:
`b5_map_dataset_MJu26a_fs2.png`, `b5_map_dataset_SH_fs2.png` and `b5_map_dataset_SO_fs2.png`. They are dataset-level
views because the overview lists *S. commune*, which stays out of every picture until queue 37 is scored.

## B1, final read with MJu26a

See `b1-intervals-2026-11-05.md`.
- **Channels:** 56, of which 44 can be measured; MJu26a replaces L_LM.
- **Against random timing:** no channel's LV differs after BH. On CV2, M2_aug CH3 and LM CH1 are more regular.
- **Against shuffled gaps:** 18 channels have neighbouring gaps more alike than shuffled, including 4 of MJu26a's 7
  that can be measured. One M2_concat channel alternates.

## Still to come

- **The second cluster round:** 702 tasks, with the archive and instructions in
  `docs/thesis/hpc/rq4_newsets_20261027/remaining_20261105/README.md`.
- **Then, once it is back:**
  - B4 and B1 on SH and SO;
  - B5 on every setting;
  - B11;
  - the 2 Hz blind sample and g-12, if there is time.
