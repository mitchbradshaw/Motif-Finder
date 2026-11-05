# B1 final read: are the intervals between events regular, bursty or random? 2026-11-05

Made by `scripts/thesis/b1_intervals.py`, which only reads the database (opened `mode=ro`). M4 and *S. commune* are
refused. Outputs are in `docs/thesis/data/ch10_b1/`:
- `b1_channels.csv`: per channel;
- `b1_summary.csv`: per recording and pooled;
- `b1_lv.png`: the figure.

## In plain words

**The question.** Do a channel's events come like clockwork, in bursts, or at random? Two checks answer it.
- **Against random timing.** Drop the same number of events at random over the same span, and compare how regular
  that looks.
- **Against shuffled gaps.** Keep the channel's own gaps, shuffle their order, and compare.

**What we found.**
- **The timing looks random.** On almost every channel the gaps are as irregular as random timing gives. Only two
  channels are measurably more regular, by one of the two measures: M2_aug CH3 and LM CH1.
- **The rate drifts.** On 16 of 45 channels, and on every recording, neighbouring gaps are more alike than a
  shuffled order gives. Busy stretches follow busy stretches and quiet follows quiet: the rate drifts slowly, as B5's
  Maps show over hours and days.
- **One channel alternates.** On M2_concat CH6, long and short gaps tend to take turns.

**What it does not show.**
- **No rhythm is shown.** There is no evidence of a regular pacemaker, beyond the two channels above.
- **Thin channels carry little weight.** 13 channels have fewer than 10 events, so on those the test can hardly say
  anything.

## Method

The protocol was fixed before the read. It is B1's design in Chapter 10, run on the same runs as B12.
- **Unit:** one complete `drop_detection_v1` run per channel. That is the whole channel, not superseded, not a
  surrogate, and the longest and latest run per channel.
- **Onsets:** detection start ÷ fs.
- **Data:** M2_aug, M2_concat, CO_fs2, LM_fs2 and L_LM_fs2. L_LM_fs2 is MJu26a's channels, until the 2 Hz sweep is
  imported.
- **Measures:** LV (Shinomoto 2003) is primary; CV2 (Holt 1996) is its companion.
- **Nulls:** `Working.interrogation.intervals.interval_nulls`, the Intervals block's code, with 1,000 seeded draws per
  channel. One null is a rate-matched Poisson train on the channel's sampling grid; the other is the channel's own
  gaps, shuffled.
- **p values:** two-sided, +1 corrected. The direction is read from the null's 95 % band.
- **Correction:** Benjamini–Hochberg at 0.05 across all 45 channels, separately for each measure × null.

## Results

| recording | channels | median events | median LV | LV vs Poisson: p < 0.05 / after BH | LV vs shuffled: below after BH / above | CV2 vs Poisson after BH |
|---|---|---|---|---|---|---|
| M2_aug (oyster) | 16 | 40.5 | 0.99 | 2 / 0 | 9 / 0 | 1 (CH3, more regular) |
| M2_concat (lion's mane) | 16 | 13 | 1.42 | 4 / 0 | 2 / 1 (CH6) | 0 |
| LM_fs2 (lion's mane) | 4 | 34 | 0.82 | 2 / 0 | 2 / 0 | 1 (CH1, more regular) |
| CO_fs2 (chocolate oyster) | 4 | 6 | 1.06 | 0 / 0 | 1 / 0 | 0 |
| L_LM_fs2 (lion's mane) | 5 | 53 | 0.85 | 1 / 0 | 2 / 0 | 0 |
| **all** | **45** | 19 | 1.06 | **9 / 0** | **16 / 1** | **2** |

- **M2_aug CH3, against Poisson:** 127 events, LV 0.72 against a band of 0.82–1.20 (p 0.004, q 0.060), CV2 0.78
  (q 0.045). The first read called it borderline, and so does this one on LV.
- **LM CH1, against Poisson:** 30 events, LV 0.47, CV2 0.60 (q 0.045).
- **CV2 against shuffled gaps:** 17 below, 1 above, after BH. This agrees with LV.
- **The first read** (M2_aug only, 28 Oct) had 11 of 16 channels below the shuffled band. This read has 10 of 16 at
  p < 0.05 and 9 after correction. The runs are the same; the draws differ.

## Verdict

Supported: random-like timing with a slowly drifting rate, on every recording. It is the same on oyster and lion's
mane, though recording and species cannot be separated (B12).

Not run:
- **the chains:** the `chain_cycles` chains are trains already selected for regularity, so they are not a fair
  sample;
- **the 2 Hz copies:** MJu26a, SH and SO wait on the 2 Hz sweep.
