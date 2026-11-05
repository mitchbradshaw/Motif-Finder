# B1 final read: are the intervals between events regular, bursty or random? 2026-11-05

Made by `scripts/thesis/b1_intervals.py` (read-only, database opened `mode=ro`; M4 and *S. commune* refused).
Outputs: `docs/thesis/data/ch10_b1/` (`b1_channels.csv` per channel, `b1_summary.csv` per recording and pooled,
`b1_lv.png`).

Re-run the same day after the first part of the 2 Hz sweep was imported. MJu26a's own 2 Hz `drop_detection_v1` run
replaces L_LM, which is five of MJu26a's channels, so they are never counted twice. A channel with fewer than three
events has no measure and is not counted as a test. The earlier 45-channel version is in git history; its findings
were the same.

## In plain words

**The question.** Do a channel's events come like clockwork, in bursts, or at random? There are two checks:
- **Against random timing.** Drop the same number of events at random over the same span. Does the channel look more
  regular, or burstier, than that?
- **Against shuffled gaps.** Keep the channel's own gaps but shuffle their order. Are neighbouring gaps more alike
  than the shuffle gives?

**What we found.**
- **The timing looks random.** On almost every channel the gaps are as irregular as random timing gives. Two channels
  are more regular by one measure: M2_aug CH3 and LM CH1.
- **The rate drifts.** On 18 of 44 channels, and on every recording, neighbouring gaps are more alike than a
  shuffled order gives. Busy stretches follow busy stretches and quiet follows quiet, which matches B5's Maps over
  hours and days.
- **One channel alternates.** On M2_concat CH6, long and short gaps tend to take turns.

**What it does not show.**
- **No regular pacemaker** beyond those two channels.
- **Not much from thin channels.** 20 of the 56 channels have fewer than 10 events, including nine of MJu26a's 16
  (at most two at 2 Hz), so the test can say little there.

## Method

The protocol was fixed before the read; it is B1's design in Chapter 10, on the same kind of runs as B12.
- **Unit:** one complete `drop_detection_v1` run per channel: the whole channel, not superseded, not a surrogate, and
  the longest, latest run per channel. Onsets are detection start ÷ fs.
- **Data:** M2_aug, M2_concat, CO_fs2, LM_fs2 and MJu26a_fs2. SH and SO have no `drop_detection_v1` run yet.
- **Measures:** LV (Shinomoto 2003) is primary; CV2 (Holt 1996) is its companion.
- **Nulls:** `Working.interrogation.intervals.interval_nulls`, the Intervals block's code, with 1,000 seeded draws
  per channel:
  - a rate-matched Poisson train on the channel's sampling grid;
  - the channel's own gaps, shuffled.
- **p values:** two-sided, +1 corrected. The direction is read from the null's 95 % band.
- **Correction:** Benjamini–Hochberg at 0.05 across the 44 channels that have the measure, separately for each
  measure × null.

## Results

| recording | channels (measurable) | median events | median LV | LV vs Poisson: p < 0.05 / after BH | LV vs shuffled after BH: below / above | CV2 vs Poisson after BH |
|---|---|---|---|---|---|---|
| M2_aug (oyster) | 16 (16) | 40.5 | 0.99 | 2 / 0 | 9 / 0 | 1 (CH3, more regular) |
| M2_concat (lion's mane) | 16 (15) | 13 | 1.42 | 4 / 0 | 2 / 1 (CH6) | 0 |
| LM_fs2 (lion's mane) | 4 (4) | 34 | 0.82 | 2 / 0 | 2 / 0 | 1 (CH1, more regular) |
| CO_fs2 (chocolate oyster) | 4 (2) | 6 | 1.06 | 0 / 0 | 1 / 0 | 0 |
| MJu26a_fs2 (lion's mane) | 16 (7) | 1.5 | 0.84 | 1 / 0 | 4 / 0 | 0 |
| **all** | **56 (44)** | 14.5 | 1.04 | **9 / 0** | **18 / 1** | **2** |

- **M2_aug CH3 against Poisson:** 127 events. LV is 0.72 against a band of 0.82–1.20 (q 0.059), and CV2 is 0.78
  (q 0.044). The first read called it borderline, and so does this one on LV.
- **LM CH1 against Poisson:** 30 events, LV 0.47, CV2 0.60 (q 0.044).
- **MJu26a's busy channels** are CH15 (235 events, LV 0.84), CH13 (66), CH2 (50) and CH6 (45). Four of its seven
  measurable channels have neighbouring gaps more alike than shuffled.
- **CV2 against shuffled gaps:** 19 below and 1 above after BH, which agrees with LV.

## Verdict

**Supported:** timing is random-like at the scale of single gaps, and the rate drifts slowly, on every recording. The
picture is the same for oyster and lion's mane, though recording cannot be separated from species (B12).

**Not run:**
- **the `chain_cycles` chains,** because those trains were selected for regularity;
- **SH and SO,** because their `drop_detection_v1` runs are in the second cluster round.
