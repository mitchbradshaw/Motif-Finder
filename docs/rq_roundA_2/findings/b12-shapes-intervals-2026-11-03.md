# B12: do spike and drop shapes and intervals differ between recordings and species? (2026-11-03)

## In plain words

Picture five rooms, each with a different clock ticking. You ask two questions. Do the ticks *sound* different from
room to room (the **shape** of each event)? And do they come at different *rhythms* (the **intervals** between
events)? The rooms are our five recordings. Some rooms hold the same kind of clock (the same species), so a second
question follows: if the rooms differ, is that because the clock is a different kind, or only because every room is
a little different?

- **Shapes: yes, the recordings differ.** The difference is real but small. It survives three checks for the fact
  that different detectors found events of different lengths.
- **Species: not shown.** Three lion's mane recordings differ from each other at least as much as oyster differs
  from lion's mane. A species difference has to be bigger than the differences inside one species, and this one is
  not. With one oyster recording and one chocolate-oyster recording, the data cannot separate "species" from "this
  particular recording".
- **Timing: no clear difference.** On complete runs of one detector (`drop_detection_v1`), how regular or bursty
  the drops are does not differ by species. The dataset difference is borderline (p ≈ 0.06) and does not survive
  correction. Most channels look random-like; a few are more regular than random, and a few are burstier.

**The website could not run this question as posed.** Interrogation's Event shape and Intervals pages read only
the 16 seed-store families (15 on M2_aug, one 4-hour L_LM excerpt). In the source picker, the *Review selection*
and *Prior run* sources are shown but are not wired, so accepted events cannot be fed into them per recording. The
screenshots show what the site does offer. Every test below ran in the backend on the tool's own core code (the
same functions the pages call).

## Protocol (declared before the results)

Script: `scripts/thesis/b12_shapes_intervals.py` (read-only DB, `mode=ro`). Outputs: `docs/thesis/data/ch10_b12/`.
Permutation seed 1203.

**Shape data.** Every accepted event (verdict *interesting* or *seed*) in the researcher's blind stratified queues
25 (M2_aug) and 28 (CO_fs2, LM_fs2, M2_concat, L_LM fs2). Only the researcher's own looks count: an adjudication with
`carried_from` set is a copy and is left out. Each judged span counts once. These are the same 716 events as ledger
E1–E4; the readers are imported from `scripts/thesis/catalogue_stats.py`, not copied. The L_LM events sit on the
fs2 copy `L_LM_Jul_26_J_raw_fs2.mat`, whose declared unit is mV; the other four are in V.

| recording | species | fs | n accepted |
|---|---|---|---|
| M2_aug | oyster | 1 Hz | 341 |
| CO_fs2 | chocolate oyster | 2 Hz | 97 |
| M2_concat | lion's mane | 1 Hz | 79 |
| LM_fs2 | lion's mane | 2 Hz | 113 |
| L_LM_fs2 | lion's mane | 2 Hz | 86 |

**Features.** Each event is measured with `Working.interrogation.event_shape.measure_events`, the core of
Interrogation › Event shape:

- `polarity="auto"`;
- `to_mv` from `Working.units.read_as_mv`;
- measured on the stored samples of the judged span.

The features:

- amplitude (|mV|);
- swing (peak-to-peak inside the span, mV);
- judged span length (s);
- event duration, from onset to half-recovery (s);
- onset → extremum time (s);
- 10–90 % rise time (s; spikes only);
- half-recovery time (s);
- FWHM (s);
- steepest slope (|mV/s|);
- peakedness;
- drop share (polarity).

Three features are duration-normalised (they carry no seconds):

- asymmetry: onset → extremum as a share of onset → recovery;
- width fraction: FWHM / duration;
- normalised slope: |slope| × duration / amplitude.

One multivariate shape: the judged span resampled to 64 points, minus its median, divided by its peak-to-peak.

**Statistics.**

- Scalar features: Kruskal–Wallis H, with ε² as the effect size.
- Normalised waveform: a PERMANOVA-style pseudo-F (Euclidean), with R² as the effect size.
- **Null:** group labels shuffled across events, each group keeping its count. 5,000 draws for the scalar features,
  2,000 for the waveform; p = (k+1)/(N+1).

**Duration control**, applied three ways:

- (a) the shuffle runs only within duration bands (quintiles of the judged span length);
- (b) each log feature is replaced by its residual after a pooled cubic in log(span length);
- (c) the duration-normalised features above.

**Levels.**

- recording (5 groups);
- species: oyster / chocolate oyster / lion's mane;
- sensitivity: oyster + chocolate oyster pooled vs lion's mane;
- yardstick: lion's mane's three recordings alone, i.e. how big a recording difference is *within* one species.

**Correction.** Benjamini–Hochberg (BH) at 0.05 over the features of one level × null. Pass or fail comes from the
project helper `Working.discovery.seeded_search.corrected_levels(…, correction="BH")`; the q-value is written beside
it.

**Interval data.** One complete `drop_detection_v1` run per channel, taken from the RQ4 sweep:

- the whole channel;
- completed, not superseded, not a surrogate;
- the longest span per channel.

That gives 16 + 16 + 4 + 4 + 5 = 45 channels. Onsets are detection start / fs. Per channel, LV and CV2 are measured
against two nulls with `Working.interrogation.intervals.interval_nulls` (the B1 code, 1,000 draws):

- a rate-matched Poisson null;
- a shuffled-interval null.

Across channels, Kruskal–Wallis is run on per-channel LV and CV2 by dataset and by species. The null shuffles dataset
labels across channels (10,000 draws), and BH is applied over LV and CV2.

**Why intervals do not use accepted events.** Gaps between the *sampled* accepted events belong to the stratified
sampler, not to the organism.

**Excluded:**

- *S. commune* (blind exam pending; never read);
- M4_aug (held out; never read);
- the 10 Hz L_LM file (it carries no accepted events and no `drop_detection_v1` run; its fs2 copy is used).

## Results

### Shape: per recording (medians)

| | M2_aug | CO_fs2 | M2_concat | LM_fs2 | L_LM_fs2 |
|---|---|---|---|---|---|
| n | 341 | 97 | 79 | 113 | 86 |
| drop share (auto rule) | 0.91 | 0.98 | 0.96 | 0.76 | 0.97 |
| amplitude, mV | 16.6 | 10.8 | 17.6 | 14.1 | 12.5 |
| swing, mV | 23.7 | 15.4 | 30.1 | 16.0 | 14.0 |
| judged span, s | 603 | 419 | 604 | 602 | 606 |
| duration (onset→half-recovery), s | 68 | 40 | 120 | 40 | 263 |
| onset → extremum, s | 24 | 10 | 30 | 18 | 62 |
| FWHM, s | 56 | 35 | 96 | 36 | 218 |
| steepest slope, mV/s | 1.44 | 2.04 | 1.93 | 2.07 | 0.46 |
| peakedness | 2.53 | 1.99 | 2.79 | 2.77 | 2.31 |
| asymmetry | 0.28 | 0.22 | 0.32 | 0.35 | 0.29 |
| width fraction | 0.87 | 0.89 | 0.87 | 0.89 | 0.90 |
| normalised slope | 7.9 | 9.3 | 10.3 | 8.6 | 7.8 |

Duration, half-recovery, FWHM, asymmetry, width fraction and normalised slope exist only where the event
half-recovers inside the rule's bound: 463 of 716 events (48–86 % per recording). Rise time exists only for the 65
spikes. A missing value is a recorded fact ("not recovered"), never 0.

### Shape: tests (Kruskal–Wallis ε² or PERMANOVA R²; permutation p; BH)

The shuffle-null results, with the most conservative duration control beside them:

| level | features that pass BH (shuffle) | within duration bands | duration residual | normalised waveform R² (p) |
|---|---|---|---|---|
| recording (5) | 11 of 15: swing, span, duration, onset→extremum, recovery, FWHM, steepest slope, peakedness, asymmetry, drop share, waveform | 9 of 14 (recovery drops out) | 7 of 10 | 0.020 (0.0005) |
| species (3) | 6 of 15: duration, onset→extremum, FWHM, peakedness, asymmetry, drop share | 5 of 14 (drop share drops out) | 4 of 10 | 0.005 (0.064, not significant) |
| oyster + CO vs lion's mane | 1 of 15: peakedness (ε² 0.013) | 3 of 14: duration, FWHM, peakedness | 5 of 10 | 0.004 (0.017; q 0.05–0.07) |
| lion's mane recordings only (3) | 7 of 15: swing, onset→extremum, recovery, steepest slope, peakedness, drop share, waveform | 6 of 14 | 4 of 10 | **0.035** (0.0005) |

Effect sizes are small throughout. The largest scalar effect at the recording level is ε² = 0.062
(onset → extremum time). At the species level the effects are smaller (largest ε² 0.045, R² 0.005). The yardstick is
the largest: the three lion's mane recordings differ among themselves by ε² up to 0.074 (steepest slope) and
waveform R² 0.035. That is seven times the species-level waveform R².

**What drives the recording effect.** The amplitude-free, duration-normalised measures do **not** separate the
recordings:

- width fraction: ε² 0.010, p 0.34;
- normalised slope: ε² 0.013, p 0.20.

What does separate them is timing: L_LM's events are slow (FWHM 218 s; steepest slope 0.46 mV/s) and CO's are fast
and small. Each recording also has a skew:

- LM_fs2 carries the most rises (24 %);
- the mean normalised waveforms show LM's events as a slow climb before the fall, where the others are a flat
  shoulder then a fall (`b12_mean_waveform.png`).

### Intervals: per dataset (complete `drop_detection_v1` runs)

| dataset | species | channels measured (of) | median events per channel | median LV | median CV2 | LV more regular than Poisson (p < 0.05) | LV burstier than Poisson |
|---|---|---|---|---|---|---|---|
| M2_aug | oyster | 16 (16) | 40.5 | 0.99 | 0.96 | 1 (CH3: LV 0.72, band 0.82–1.20) | 1 (CH14, 9 events) |
| CO_fs2 | chocolate oyster | 2 (4) | 6 | 1.06 | 1.02 | 0 | 0 |
| M2_concat | lion's mane | 15 (16) | 13 | 1.42 | 1.24 | 0 | 4 (CH5, 6, 7, 10) |
| LM_fs2 | lion's mane | 4 (4) | 34 | 0.82 | 0.87 | 2 (CH1 LV 0.47; CH3 0.58) | 0 |
| L_LM_fs2 | lion's mane | 3 (5) | 53 | 0.85 | 0.89 | 1 (CH3, 203 events) | 0 |

Five channels have fewer than 3 events and are not measured (CO CH1, CO CH3, M2_concat CH9, L_LM CH0, L_LM CH4).
These per-channel p-values are not corrected across channels. The M2_aug row reproduces B1: CH3 has LV 0.724, the
only regular channel.

| level | LV: ε², p, BH | CV2: ε², p, BH |
|---|---|---|
| dataset (5) | 0.22, 0.057, fails | 0.21, 0.070, fails |
| species (3) | 0.05, 0.38, fails | 0.07, 0.28, fails |
| oyster + CO vs lion's mane | 0.05, 0.18, fails | 0.06, 0.12, fails |
| lion's mane datasets only (3) | 0.29, 0.040, fails (q 0.058) | 0.26, 0.058, fails |

Intervals do not differ by species. The tendency between datasets comes from inside lion's mane: M2_concat leans
bursty and LM leans regular. The shuffled-interval null is rejected on most well-populated channels, in all five
datasets. Neighbouring gaps are more alike than shuffling would give, which points to slow drift in the rate,
as B1 found on M2_aug.

## Caveats

1. **Species is confounded with recording.** There is one oyster recording, one chocolate-oyster recording and
   three lion's mane recordings. An event-level species test cannot tell "species" from "this recording". The
   within-lion's-mane yardstick shows recordings of one species differing more than the species do. A defensible
   species claim needs several recordings per species, tested by permuting *recordings*. With 5 recordings that test
   has 10 possible splits for 2 v 3, so its p cannot fall below 0.1.
2. **Two queues, two detector mixes.** M2_aug's events come from queue 25; the other four recordings' events come
   from queue 28. Each queue was stratified over 36 detector variants, whose median spans run from 24 s
   (signal_threshold) to 7,200 s (cnn_fusion3_60min). The duration controls take out the length of the span, not
   which detector found it. A recording difference may still be partly a detector-mix difference (the crosstab is in
   `events_shape.csv`, column `detector`).
3. **Sampling rate.** The rate differs (1 Hz for M2_aug and M2_concat, 2 Hz for the rest). Onset → extremum time and
   steepest slope are measured on a 0.5–1 s grid, which coarsens the 1 Hz recordings' fast edges.
4. **L_LM is MJu26a.** L_LM is a copy of five channels of MJu26a, so it is not an independent culture from any other
   recording here. It also differs most (slowest events).
5. **Interval counts.** CO_fs2 has only 2 measurable channels, with 10 and 24 events. M2_concat channels have a
   median of 13 events, and many carry "fewer than 10 gaps: indicative only".
6. **A possible bug in chapter 9's figure (not fixed; out of scope).** In `scripts/thesis/catalogue_stats.py`,
   `polarity_auto = np.where(polarity < 0, "rise", "drop")` reverses the core's convention
   (`event_shape.DROP = -1`, `SPIKE = +1`). So the grey "fastest edge is a fall" bars in
   `docs/thesis/data/ch9_catalogue/drop_share.png` plot the *spike* share.
   - By the auto rule, 91 % of the 716 accepted events are falls (76–98 % per recording, table above).
   - Ledger E4 (68 %) uses the other rule, median excursion, and is not affected.
   - Worth checking before the chapter cites the grey bars.
7. **Site gap.** In Interrogation's source picker, the Review-selection and Prior-run tabs are shown but not wired
   (`getSourceChoices` returns `reviewSelections: []`; a prior-run click is `notWired`). The Event shape and Intervals
   cards therefore run only on the 16 seed families. On Analyse block pages, Event shape and Intervals need a fresh
   chain run (a run row). Interrogation's 02 Aggregate page says itself that it draws no null.

## What ran where

- **On the site** (`http://127.0.0.1:8765`, read-only GETs via `scripts/thesis/site_shots.py`): Interrogation
  02 Aggregate on two seed families, one oyster (id024, M2_aug CH2, 40 drops) and one lion's mane (id385, the 4-h
  L_LM/MJu26a excerpt, 24 drops), in both upstreams (Event shape; slope with the inter-event interval histogram).
  Also the Interrogation source picker's Review-selection tab.
  - Nothing was run, saved or changed.
  - No Analyse chain was run.
- **In the backend**: every test above. It used the same core functions the pages call
  (`event_shape.measure_events`, `intervals.interval_nulls`, `units.read_as_mv`).

## Screenshots (`docs/thesis/figures/roundb/`)

| file | what it shows |
|---|---|
| `b12_ig_source_picker_review.png` | Interrogation source picker, *Review selection* tab: empty. Accepted queue events cannot be chosen as an Interrogation source (the site gap). |
| `b12_ig_event_shape_page_id024_m2aug.png` | Interrogation › 02 Aggregate, upstream Event shape, family id024 (oyster, M2_aug CH2, 40 drops): amplitude / FWHM / recovery histograms, the timeline with Kendall τ, and the scaling card. Full page. |
| `b12_ig_event_shape_page_id385_llm.png` | The same for id385 (lion's mane, L_LM 4-h excerpt, 24 drops): amplitude median 9.56 mV, FWHM 5.49 s, recovery 2.97 s; "rise_time_s: 24 of 24 not measured" (a drop has no rise, Q19). Full page. |
| `b12_ig_intervals_page_id024_m2aug.png` | Interrogation › 02 Aggregate (slope upstream), id024: drop depth (median 53.9 mV), inter-event interval (median 1.44 h, n 39 of 40), max slope; "no null is drawn on this page". |
| `b12_ig_intervals_page_id385_llm.png` | The same for id385. |

Two cropped histogram-only shots (`element: hist-first`) failed and were not saved: the element was "not visible"
(a layout wrapper with no box). Full-page and viewport shots replace them.

Backend figures (`docs/thesis/data/ch10_b12/`):

- `b12_shape_by_recording.png`: six features by recording, boxes plus points;
- `b12_mean_waveform.png`: mean duration-normalised waveform per recording;
- `b12_intervals_lv_cv2.png`: per-channel LV and CV2 by dataset, Poisson line at 1.

Tables:

- `events_shape.csv`: 716 events × features, with detector, queue and units;
- `shape_tests.csv`, `shape_by_recording.csv`, `shape_by_species.csv`;
- `intervals_by_channel.csv`, `interval_tests.csv`;
- `waveforms_64.npy`, `mean_waveform_by_recording.json`.
