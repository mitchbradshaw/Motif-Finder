# B5: when and where the detectors fire, read from the Discovery Maps (2026-11-03)

**Code:** `scripts/thesis/b5_map_timing.py`, test `tests/test_b5_map_timing.py`.
**Data:** `docs/thesis/data/ch10_b5/` (`summary.json`, `b5_timecourse.png`).
**Website screenshots:** `docs/thesis/figures/roundb/b5_*.png`, listed below.

Read-only. *S. commune* and M4 were not read. The real counts are the Map's own (see below); the paired surrogate runs,
which the Map does not draw, come from the database.

## In plain words

The Discovery Map shades how often each detector setting fires on each channel. Its channel level shows that again in
3-hour bins across a whole recording.

- **Detectors agree on *when*.** On every one of the 45 channels of the five swept recordings, the settings' rates rise
  and fall together. Co-modulation, the mean correlation between settings, is 0.21–0.35 (median per recording), and
  0.00 when each setting's series is moved to a random time. So the Map's bursts of activity and quieter stretches are
  shared across detectors, not one detector's noise.
- **A scrambled copy hardly does it.** Beside every real run the sweep ran the detector on a phase-randomised copy,
  which keeps the frequency content and loses the timing. Those copies co-modulate at only 0.02–0.04. So the bursts
  and quiet stretches are the recordings' own changes over hours and days, not something noise with the same spectrum
  produces.
- **Nothing is ever silent.** No 3-hour bin is silent across all settings: the loose detectors (noise threshold, the
  wavelet prototype, the hour-scale CNNs) fire everywhere. "Quiet" on the Map means quieter, not empty.
- **Channels rise and fall together** on M2_aug, CO and L_LM, as B4's shared driver predicts, but not on LM. On
  M2_concat the scrambled copies do it as strongly as the real signal. That is because channels 5–8 are copies of one
  another (B4), and identical channels get identical scrambled copies.
- **Whether the changes are biology or recording conditions** (drift, electrode settling, the room), this cannot say.
  The environment logs that could separate them are not on disk (Chapter 10, *Activity against environment*).

## What the website shows (screenshots)

| file | page | what it shows |
|---|---|---|
| `b5_map_overview.png` | Discovery › Map, all datasets | Where each setting fires: rows are settings and columns are channels of M2_aug, M2_concat and CO (viewport), shaded by detections per covered hour. The loose families (noise threshold, the wavelet prototype, the 60-min CNNs) are dense everywhere and the drop detectors sparse. A few channels carry much more for some families: M2_aug CH16 for the CNNs and troughs, M2_concat CH3 for BEADs and the signal thresholds, M2_concat CH8 for OASIS. The matrix profile ran on two channels of each recording only. |
| `b5_map_dataset_M2_aug_8chunks.png` | Map › M2_aug, 8 time chunks | The same in eight 90-hour chunks per channel (CH1–CH4 in view). Which chunks are busy differs between channels. Within a channel, the darker chunks line up down the rows: the drop detector's variants, for example, darken together in CH1's third and fourth chunks. That alignment is the co-modulation measured below. |
| `b5_map_channel_M2_aug_CH6.png` | Map › M2_aug › CH6, 3-h bins | Every setting over 30 days under the signal's hourly mean. Most settings fire densely in days 0–8 and around days 15–17 and thin out elsewhere; the hour-scale CNNs fire throughout. |
| `b5_map_channel_M2_concat_CH5.png` | Map › M2_concat › CH5 | One of the copied channels (B4). |
| `b5_map_channel_CO_CH1.png` | Map › CO › CH1 | The chocolate-oyster recording, 2 Hz, 480 h. |

## Protocol (fixed before the numbers)

- **Data:** the five recordings with a full sweep: M2_aug (oyster, 16 ch, 721 h), M2_concat (lion's mane, 16 ch,
  282 h), CO_fs2 (chocolate oyster, 4 ch, 480 h), LM_fs2 (lion's mane, 4 ch, 480 h) and L_LM_Jul_26_J_raw (lion's
  mane, 5 ch, 636 h).
- **Runs:** per channel and setting, the newest live real run that has a paired surrogate, with that surrogate (one
  phase-randomised draw). Seed searches and window parts are left out.
- **Bins:** detections by start sample in 3-hour bins from the recording's start, as `Working.discovery.detection_map
  .timeline_map` (the page's level 1) bins them.
  - **Check:** on M2_aug CH6, all 39 settings' binned counts are identical to the page's own payload
    (`/api/discovery/map/channel`).
- **Co-modulation per channel:** C is the mean pairwise Spearman correlation (average ranks) between the settings'
  binned counts, with flat series left out.
  - Null: 200 draws, each rolling every setting's series by its own random offset. That keeps each setting's own
    pattern and breaks only the alignment.
  - p = (1 + draws with C ≥ observed) / 201.
  - The same is computed for the surrogate runs.
- **Channel bands per recording:** each channel's settings are z-scored and averaged into one series. The statistic is
  the mean pairwise Spearman correlation between channels, against independent rolls per channel.

## Results

| recording (species) | channels | settings per channel | co-modulation, real | time-shifted | surrogate | channels beyond shifts, real / surrogate | channel bands, real (p) | surrogate (p) |
|---|---|---|---|---|---|---|---|---|
| M2_aug (oyster) | 16 | 38 | **0.35** [0.25–0.41] | 0.00 | 0.022 [0.013–0.029] | 16 / 16 | **0.29** (0.005) | 0.07 (0.005) |
| M2_concat (lion's mane) | 16 | 38 | **0.33** [0.18–0.50] | 0.00 | 0.045 [0.025–0.056] | 16 / 16 | 0.19 (0.005) | 0.18 (0.005) |
| CO_fs2 (chocolate oyster) | 4 | 44 | **0.26** [0.23–0.39] | 0.00 | 0.022 [0.018–0.030] | 4 / 4 | 0.20 (0.040) | 0.11 (0.005) |
| LM_fs2 (lion's mane) | 4 | 44 | **0.30** [0.27–0.32] | 0.00 | 0.022 [0.014–0.029] | 4 / 4 | 0.00 (0.46) | 0.07 (0.040) |
| L_LM (lion's mane) | 5 | 14 | **0.21** [0.10–0.36] | 0.00 | 0.041 [0.031–0.071] | 5 / 5 | **0.23** (0.005) | 0.08 (0.005) |

Medians, with the range over channels in brackets. The p floor is 1/201 ≈ 0.005.

**Silent bins:** 0 % of 3-hour bins are silent across all settings on any recording, real or surrogate (L_LM real
0.5 %).

**Time course:** `b5_timecourse.png` is the median over channels of the settings' mean z-scored rate, real against the
surrogate, for each recording.

## Reading it

- **"Bursts of agreement" are real and shared.** Every channel beats its time-shift null, and the surrogate's
  co-modulation is a tenth of the real one. The surrogates also beat their shifts, at about 0.02–0.04: a phase-randomised
  copy keeps some slow structure, so the shift null is stricter than "no alignment at all". The real-to-surrogate
  ratio is the measure to quote.
- **Detector variants are not independent.** A family's variants share most of their events, so part of each
  channel's co-modulation is the same events counted twice. The statistic says the settings agree on when; it is not a
  count of independent witnesses. Per-family co-modulation is left for later.
- **What a surrogate reproduces:** how dense the loose families are, which is their response to the spectrum (Chapter
  6), and on M2_concat the band between copied channels. What it does not reproduce: the timing of bursts and quiet
  stretches, and the bands on M2_aug, CO and L_LM.
- **Caveats:**
  - one surrogate draw per run (Chapter 6 found the ratios stable over 20 draws);
  - 3-hour bins only;
  - four of the five recordings have no human verdicts outside the blind queues, so the Map's human row is sparse;
  - recordings and species are confounded (one recording per species except lion's mane).
