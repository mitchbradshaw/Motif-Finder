# Catalogue statistics for the thesis (chapter 9), 2026-10-26

Made by `scripts/thesis/catalogue_stats.py` (read-only). Outputs in `docs/thesis/data/ch9_catalogue/`:
`events.csv` (one row per judged span with every measure), `catalogue_stats.json` (all the summaries below),
`intervals_by_channel.csv`, and plain quick-look plots `swing_hist.png`, `duration_hist.png`, `drop_share.png`,
`intervals_hist.png`.

## In plain words

The detectors proposed about three million candidate events; the researcher judged a fair random handful of them
blind (queues 25 and 28), plus the Library's members. This file describes what the *accepted* events look like: how
big their voltage swing is, how long they last, whether they go down or up, and how far apart they come. Think of a
birdwatcher's notebook: not "how many birds are there", but "of the birds I confirmed, how big, how long the song,
how often".

Two cautions come first. **(1) The events are spans a detector drew, not physical events**: a 10-minute OASIS or CNN
window and a 20-second trough are both "events" here, so a duration is partly the detector's framing. **(2) The two
blind queues are stratified samples**: they over-represent detector agreement and the selective detectors on purpose,
so a share below is a share of *this sample*, not of the recording. Intervals between sampled events are therefore
meaningless and are reported only for the seed-search censuses, where every match was judged.

## What was measured, and how

- **Events.** Queue 25 (M2_aug, 800 items) and queue 28 (CO_fs2, LM_fs2, M2_concat, L_LM fs2, 290 each; 1,160 in
  all); own looks only (a verdict with `carried_from` set is a copy and was left out: 1 + 2 such items). Accepted =
  interesting or seed; rejected = not_interesting; artifact (25) and unsure (95) kept apart. Second set: the Library's
  accepted members (`annotations.source = 'library_review'`, interesting/seed: 210 members = 152 distinct events by
  the audit's ≥ 50 %-overlap rule; M2_aug 162, Fig2A 34, Mushroom_260720 14). Third: the seed-search censuses (dip
  id010, run group 9, 263 matches all judged; long dip id020, run group 12, 104 of 115 judged).
- **Units → mV.** Every amplitude is read by `Working.units.read_as_mv(recordings.units)`: M2_aug, M2_concat, CO_fs2,
  LM_fs2, Fig2A and Mushroom_260720 are stored in **V (× 1000)**, L_LM fs2 in **mV (× 1)**. No undeclared unit was read.
- **Swing** = peak-to-peak of the samples inside the judged span (`span_ptp_mv` of `interrogation.event_shape`'s core,
  `Working.interrogation.event_shape.measure_events`). **Duration** = the judged span's length; event_shape's own
  onset-to-recovery duration is in `events.csv` (`event_duration_s`).
- **Drop or rise**, two rules: (a) the Library's `bases.polarity` (the excursion below the span's median against the
  one above it; negative = a fall); (b) event_shape's `polarity = "auto"` (the fastest edge decides). **Rule (b) is not
  fit for these spans:** it calls 98 % of the accepted dip-census matches "rises", although every one is a match to a
  dip seed and rule (a) calls 100 % of them falls. A dip here falls slowly and recovers fast, so its fastest edge is
  the recovery. Rule (a) is used below; rule (b) is in the JSON and the plot for the record.
- **Intervals**: `Working.interrogation.intervals` (the core of `interrogation.intervals`) on accepted onsets per
  channel.

## Accepted events in the blind queues (716 of 1,861 decided; 95 unsure left out)

| recording | accepted / decided | swing mV: min · median · p95 · max | > 95 mV | < 1 mV | duration s: p05 · median · p95 · max | falls (rule a) |
|---|---|---|---|---|---|---|
| M2_aug | 341 / 753 | 0.17 · 23.7 · 111 · 541 | 7.3 % | 3.5 % | 41 · 603 · 1,482 · 3,380 | 69 % |
| M2_concat | 79 / 272 | 3.1 · 30.1 · 180 · 299 | 22.8 % | 0 % | 223 · 604 · 1,705 · 2,931 | 67 % |
| CO_fs2 | 97 / 282 | 0.82 · 15.4 · 146 · 426 | 9.3 % | 3.1 % | 32 · 418 · 1,338 · 7,200 | 80 % |
| LM_fs2 | 113 / 282 | 0.92 · 16.0 · 106 · 491 | 8.8 % | 0.9 % | 40 · 602 · 1,018 · 1,800 | 57 % |
| L_LM fs2 | 86 / 272 | 0.23 · 14.0 · 57 · 99 | 1.2 % | 2.3 % | 142 · 606 · 1,535 · 3,178 | 64 % |
| **pooled** | **716 / 1,861** | **0.17 · 19.8 · 122 · 541** | **8.8 %** | **2.5 %** | **40 · 603 · 1,272 · 7,200** | **68 %** |

(decided = accepted + rejected + artifact.) Rejected events are much smaller and shorter: pooled median swing
0.66 mV (59 % under 1 mV), median duration 37 s, falls 51 % (a coin toss, as noise should be).

Which detectors the accepted events came from (the detection that was sampled): OASIS 241, wavelet_encoded 93,
drop_detection_v1 90, drop_detection_v5 85, BEADs 80, symbol_search 50, deconvolved_troughs 20, signal_threshold 19,
the 10-min CNNs 14, Wavelet prototype 13, noise_threshold 10, a 60-min CNN 1. 24 % of accepted spans are 590–610 s
long (OASIS and CNN framing); without them the pooled median duration is 420 s (p05 40 s, p95 1,703 s).

## The Library's accepted members (210; 152 distinct events)

Swing median 13.8 mV (distinct events 11.2 mV), p95 110 mV, max 140 mV; 13.8 % under 1 mV (all Fig2A, reishi 10 Hz,
median 0.55 mV). Duration median 246 s (distinct 151 s); falls 51 % (distinct 60 %). By recording: M2_aug swing median
14.6 mV, duration 351 s; Mushroom_260720 14.0 mV, 72 s; Fig2A 0.55 mV, 5 s.

## Intervals between accepted events on one channel (censuses only)

- **dip id010** (3 channels, 256 accepted): median interval 3,152 s (53 min), 5–95 % 202 s – 13.5 h; per-channel CV
  2.2–4.1 and LV 0.8–1.1: bursty, not regular (a clock would read CV ≈ 0, a random Poisson stream CV ≈ 1).
- **long dip id020** (16 channels, 94 accepted, 78 intervals): median 101,599 s (28 h), 5–95 % 31 min – 11 days.
- The Library's intervals (median 312 s) mix overlapping pieces of one event (intervals of 0 s), and the blind queues
  are samples: neither is a rate.

## The poster's figures against these numbers

| poster | here | verdict |
|---|---|---|
| "top 5 % are over 95 mV" | blind accepted p95 = 122 mV; 8.8 % exceed 95 mV (Library p95 110 mV, 9.5 %) | **reproduces** (in fact the top 8–9 %) |
| "median is 12–20 mV" | blind accepted 19.8 mV pooled, 14.0–30.1 per recording; Library 13.8 (distinct 11.2) | **partly**: pooled and Library fit; per recording the range is 14–30 mV (M2_aug 24, M2_concat 30). Say "median 14–30 mV per recording, 20 mV pooled" |
| "smallest are < 1 mV" | min 0.17 mV; 2.5 % of blind accepted < 1 mV (13.8 % of Library members, all Fig2A) | **reproduces** |
| "median about 10 minutes (5–95 %: 40 s to 21 min)" | 603 s median, p05 40 s, p95 1,272 s (21.2 min) | **reproduces exactly**, but it is detector framing (24 % are ≈ 600 s windows) |
| "from under a minute to several hours" | 1 s (rejected) / 32 s (accepted) up to 7,200 s (2 h, one 60-min-CNN span on CO_fs2); Library max 70 min | **overstated**: "up to two hours" |
| "73 % of accepted events are falls … on all five recordings (56–86 %)" | 68 % pooled, 57–80 % per recording (rule a); 9 % by rule (b) | **does not reproduce exactly**; the poster's rule is not recorded. A ±0.2 biphasic band gives 55 % (43–65 %). Quote "about two-thirds (57–80 %), by the median-excursion rule" |

## Not done

- No per-shape (sharkfin / trough) breakdown: no verdict carries a shape class (RQ1b).
- Accepted events were not merged into physical events across detectors (the fragments question); a long OASIS span
  and a short trough inside it both count.
