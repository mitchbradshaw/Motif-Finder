# B9: do CWT event durations cluster at preferred scales? 2026-11-03

Round-B question B9, thesis Chapter 10 (`10_roundb.tex`, "Time scales and methods from other fields"). Made by
`scripts/thesis/b9_cwt_durations.py` (the events) and `scripts/thesis/b9_modes.py` (the test), plus site runs of the
`cwt_events` template for the screenshots. M4_aug was never read; S. commune was never run, viewed or exported.

## In plain words

Think of a smoke alarm that is meant to go off for fires of three typical sizes. To know whether it is really
detecting fires, you test it in a room with no fire but with the same kind of steam and dust. If it goes off just as
often there, and for the same "sizes", its sizes describe the alarm and the room, not the fires.

Here the "alarm" is the CWT-ridge detector of the `cwt_events` template. It finds drops in the fungal voltage and
gives each a duration (`best_scale_s`). The question was whether those durations bunch at a few preferred lengths,
as Adamatzky's three time scales would suggest. The "room with no fire" is an AAFT copy: the same recording's own
values, shuffled so that their slow wandering and their spread survive but no real event does.

**Answer: no evidence of preferred durations that belong to the fungi.**
- **The copies give more events than the real recordings.** Over 20 one-day spans on five recordings, the real spans
  gave 632 drops (260 clean) and their AAFT copies gave 1,087 (517 clean). Only 6 of 20 spans beat their copy.
- **The durations look the same.** Real and copy both pile up at the shortest scales (about 15–20 s) and thin out
  towards a few minutes, with a long tail. A test cannot tell real from copy on four of five recordings.
- **The "modes" belong to the detector.** A mixture model does prefer two or three groups (around 18 s, 70–90 s and
  several minutes). But it prefers them just as strongly on the copies. So the groups describe how this detector
  reads noise of this colour, not three kinds of fungal event.
- **Why the template once "beat its null".** The W1 evaluation used phase-randomised copies. These also reshape the
  recording's lopsided values into a bell curve, and they give almost no events here either (5 in 20 spans). The
  detector reacts to the lopsided values, so it beats that null without finding any structure.
- **One exception worth a look.** On M2_concat the real durations are longer than the copy's (median 59 s against
  35 s, KS p < 0.001), although the real count is still below the copy's.

**Recommendation:** report B9 as a negative result. On 24 h spans, `cwt_events` shows no preferred event durations
beyond AAFT noise. Its "beats the null" status from W1 holds only against the phase-randomised null; re-judge it
against AAFT before the template supports a claim.

## Protocol (declared before any duration was read)

**Detector.** The `cwt_events` template's detector, `detection.cwt_ridges` with `polarity: drop` and every other
parameter at the template's default (scales 10 s to 2 h, 40 log-spaced; min SNR 3; noise window 1 h). The
template's later blocks (Event shape, Intervals) measure each event but never add or remove one, so the events and
their `best_scale_s` are the detector's. In the backend the detector is called directly on the memory-mapped channel
array (`Working.Detection.cwt_ridges.detect`); nothing is written to the database or the step cache.

**Spans.** 24 h each (the W1 evaluation found 0-2 events on 4 h spans). Recordings M2_aug (oyster), M2_concat (lion's
mane), CO_fs2 (chocolate oyster), LM_fs2 (lion's mane), MJu26a_fs2 (lion's mane). Every channel of the 4-channel
recordings; channels 0, 4, 8, 12 of the 16-channel ones. One span per channel, starting at 50 % of
(length - 24 h). A span more than 10 % NaN is skipped.
- *The cut, stated:* the declared plan was three spans per channel (at 20 %, 50 %, 80 %) on every even channel. A
  four-span pilot ran at about 150 s a span on the loaded machine (it would have taken about 4 h), so it was cut to
  the rule above before any duration was looked at. The pilot's counts are in `docs/thesis/data/ch10_b9/pilot_run.log`;
  they agree with the main run on the span both share.

**Null.** One AAFT copy of each span (`Adapters.preprocessing_surrogate.aaft_surrogate`: the span's own values, its
spectrum approximately, no shapes), seed fixed per span. NaN samples are bridged linearly for the surrogate only and
set back to NaN after it, so the copy keeps the real span's gaps. One phase-randomised copy per span ("PR", the null
the W1 evaluation used) is run alongside, to explain the difference from W1.

**Which events.** "Clean" events (no `edge_flag`, no `step_pair`, the reading of the template's own test) are the
primary set; all events are reported alongside.

**Multimodality test.** On log10(`best_scale_s`), pooled per recording and over all recordings:
- Gaussian mixtures with 1, 2 and 3 components (sklearn, 10 restarts, seed 0); the BIC-best K, and
  ΔBIC = BIC(1) − BIC(best). ΔBIC > 10 is read as strong evidence for more than one mode.
- The scales lie on a 40-step log grid, so each value is jittered uniformly within ± half a grid step first (seed 0);
  otherwise a mixture can fit the grid's spikes.
- A component counts as a mode only if it holds at least 10 % of the events. Nothing is fitted on fewer than 20.
- Hartigan's dip test was skipped: the `diptest` package is not installed and no package may be installed today.
- Real against AAFT: a two-sample Kolmogorov-Smirnov test on the log durations, and the positions of the modes.

**What would answer the question.** "Durations cluster at preferred scales" needs (a) real events beyond the AAFT copy
in number, (b) a real mixture with more than one mode, and (c) modes the AAFT events do not share. If the AAFT copies
give almost no events, the counts are the comparison and the modes cannot be compared.

## Results

**Backend run:** 20 spans × (real + 1 AAFT + 1 phase-randomised) = 60 detector runs, 492 s in all (8–23 s a span
once the machine was quiet). No span was skipped for NaN.

### Counts: real against AAFT

| Recording | spans (channels) | span (h from start) | real (clean) | AAFT (clean) | PR (clean) | spans real > AAFT |
|---|---|---|---|---|---|---|
| M2_aug | 4 (ch 0, 4, 8, 12) | 348.5–372.5 | 144 (68) | 243 (133) | 1 (1) | 1 of 4 |
| M2_concat | 4 (ch 0, 4, 8, 12) | 129.2–153.2 | 137 (54) | 357 (147) | 0 (0) | 1 of 4 |
| CO_fs2 | 4 (all) | 228–252 | 124 (58) | 144 (56) | 2 (1) | 1 of 4 |
| LM_fs2 | 4 (all) | 228–252 | 178 (51) | 190 (100) | 0 (0) | 2 of 4 |
| MJu26a_fs2 | 4 (ch 0, 4, 8, 12) | 306–330 | 49 (29) | 153 (81) | 2 (0) | 1 of 4 |
| **pooled** | 20 | | **632 (260)** | **1,087 (517)** | **5 (2)** | **6 of 20** |

Per span (`spans.csv`):
- The real count ranges 0–93; the AAFT count 7–114.
- Two MJu26a spans (ch 0, ch 8) gave no real event, against 17 and 24 on their copies.
- The span the pilot and the main run share (M2_aug ch 0) gave 93 real events in both. Its AAFT count differs (82 vs
  77) only because the seed rule changed.

### Durations: mixture fits on log10(best_scale_s)

ΔBIC = BIC(1 component) − BIC(best); above 10 is strong evidence for more than one component. KS compares each copy
with the real events of the same recording.

| Recording | events | kind | n | median (s) | best K | ΔBIC | components: mean (weight) | KS vs real |
|---|---|---|---|---|---|---|---|---|
| CO_fs2 | clean | real | 58 | 20 | 3 | 32.7 | 16 s (64%); 40 s (26%); 279 s (10%) | |
| CO_fs2 | clean | aaft | 56 | 22 | 3 | 25.4 | 19 s (76%); 114 s (22%); 3881 s (2%) | 0.12 (p 0.74) |
| LM_fs2 | clean | real | 51 | 36 | 1 | 0.0 | 45 s (100%) | |
| LM_fs2 | clean | aaft | 100 | 28 | 2 | 36.4 | 20 s (60%); 123 s (40%) | 0.15 (p 0.39) |
| M2_aug | clean | real | 68 | 27 | 3 | 21.1 | 19 s (61%); 91 s (37%); 4762 s (1%) | |
| M2_aug | clean | aaft | 133 | 28 | 2 | 46.2 | 19 s (58%); 120 s (42%) | 0.09 (p 0.83) |
| M2_concat | clean | real | 54 | 54 | 2 | 2.0 | 19 s (31%); 94 s (69%) | |
| M2_concat | clean | aaft | 147 | 33 | 3 | 31.1 | 15 s (34%); 46 s (52%); 167 s (14%) | 0.26 (p 0.007) |
| MJu26a_fs2 | clean | real | 29 | 46 | 1 | 0.0 | 59 s (100%) | |
| MJu26a_fs2 | clean | aaft | 81 | 36 | 2 | 1.7 | 23 s (54%); 98 s (46%) | 0.17 (p 0.49) |
| **pooled** | clean | real | 260 | 30 | 2 | 79.2 | 17 s (46%); 87 s (54%) | |
| **pooled** | clean | aaft | 517 | 29 | 3 | 171.6 | 19 s (54%); 67 s (36%); 393 s (10%) | 0.06 (p 0.59) |
| pooled | all | real | 632 | 30 | 3 | 294.3 | 18 s (52%); 77 s (39%); 760 s (9%) | |
| pooled | all | aaft | 1,087 | 29 | 3 | 472.1 | 19 s (56%); 68 s (33%); 459 s (11%) | 0.04 (p 0.56) |

The all-events rows per recording are in `modes.csv`. They agree: KS p is 0.20–0.89 on every recording except
M2_concat (p 0.0002). The phase-randomised copies gave too few events (0–2 per recording) to fit.

### Reading against the three conditions

- **(a) fails.** Real events do not outnumber the AAFT copy's on any recording, per recording or pooled.
- **(b) passes only formally.** Pooled, the real durations prefer two components (ΔBIC 79). But the histograms
  (`docs/thesis/data/ch10_b9/durations_hist.png`) show one pile at the shortest scales falling off towards minutes,
  not separate humps. A Gaussian mixture splits a skewed distribution with a hard floor into components even when it
  has one mode. The dip test, which tells "skewed" from "multimodal", was not available.
- **(c) fails.** The AAFT events prefer as many components, in the same places (about 19 s and 70–120 s), with a
  larger ΔBIC. KS cannot tell real from copy on CO, LM, M2_aug or MJu26a.

**Why W1 saw a pass.** Against the phase-randomised copy the real spans win 632 to 5, as in W1. Both kinds of copy
keep the spectrum; only AAFT also keeps the skewed values. So the detector's events follow the value distribution,
and the W1 margin measured that, not events.

**M2_concat** is the one recording whose real durations differ from its copy's: they are longer (clean median 54 s,
against 33 s). That could be slower real drops, or drift slower than the copy reproduces. One recording and four
spans cannot say which.

## Caveats

- **Cut spans.** One 24 h span per channel and four channels per recording, instead of the planned three spans on
  eight channels. The pilot's three other spans (M2_aug ch 0 at 20 % and 80 %, ch 2 at 20 %) agree: 26, 12 and 19
  real events against 75, 20 and 84 on AAFT (`pilot_run.log`).
- **One AAFT draw per span.** Draws vary a lot (75 and 33 on one pilot span). Pooled over 20 spans, though, the excess
  is large: 517 clean events on the copies against 260 real.
- **Backend, not the chain.** The detector was called directly with the template's parameters. The site runs below
  check that the chain gives the same count on the shared span.
- **Grid.** `best_scale_s` takes 40 values. The jitter keeps the grid out of the fits, but a component narrower than
  one grid step (about 18 %) cannot be resolved.
- **No dip test.** The package is not installed and nothing could be installed today.
- **Drops only.** The template is the drop variant; spikes were not tested.

## On the website

Three Analyse-page runs (bridge `/api/runs`, project mode, machine runs only), all on M2_aug ch 0 (recording 1),
over 348.5–372.5 h (samples 1,254,600–1,341,000). This is the same span as the backend's first span.

| Chain | job | db run | time | drops |
|---|---|---|---|---|
| `cwt_events` (real) | 841 | 8090 | 6.1 s | **93**, the same as the backend |
| `preprocessing.surrogate` (aaft, seed 0) → `cwt_events` | 842 | 8091 | 6.1 s | **51** |
| `preprocessing.surrogate` (phase_randomize, seed 0) → `cwt_events` | 843 | 8092 | 3.1 s | **0** |

On this span the real recording beats its site AAFT copy (93 against 51). The backend's AAFT draw gave 77. So this
span is one of the six of 20 that beat their copy, and one AAFT draw scatters widely. The phase-randomised copy gives
nothing, as in W1.

The AAFT copy's trace (`b9_cwt_m2aug_aaft_copy.png`) shows the mechanism. The recording's few deep, long excursions
(a value range of about 160 mV) become bursts of deep, short drops in the copy, because AAFT puts the same low values
back in at random times. The detector counts those bursts as events.

### Screenshots (`docs/thesis/figures/roundb/`)

| File | What it shows |
|---|---|
| `b9_cwt_m2aug_real.png` | The CWT ridges block page for job 841: 93 drops marked on the 24 h span, sample event cards, the span-duration histogram and the parameters (template defaults, polarity drop). |
| `b9_cwt_m2aug_real_trace.png` | The chain page's source row for the same run: the real 24 h trace. |
| `b9_cwt_m2aug_aaft.png` | The CWT ridges block page for job 842 (the AAFT copy): 51 drops. |
| `b9_cwt_m2aug_aaft_copy.png` | The chain page's surrogate row for job 842: the AAFT copy (blue) over the real span (grey) on one axis, with the bursts of deep drops it creates. |
| `b9_cwt_m2aug_phase.png` | The CWT ridges block page for job 843 (phase-randomised copy): no drops. |
| `b9_cwt_m2aug_phase_copy.png` | The chain page's surrogate row for job 843: the phase-randomised copy against the real span. |

The shots were taken with `scripts/thesis/site_shots.py` and no page or console error. Each shot seeds the Analyse
source and chain (`ub-proto-a:source`, and `ub-proto-a:chain` with `lastRunJobId`) in sessionStorage, so the page
attaches to the finished job and nothing is re-run. The shot list is
`docs/thesis/data/ch10_b10/site_shots.json` (shared with B10; in it, the `_chain` shots are the files renamed
`_trace` and `_copy` here). The jobs live in the bridge's memory, so the shots can be retaken only until the bridge
restarts; the run rows (db runs 8090–8092) stay.

## Files

- `scripts/thesis/b9_cwt_durations.py`: the backend events (real, AAFT and PR per span).
- `scripts/thesis/b9_modes.py`: the mixture fits, KS tests, counts and histogram.
- `scripts/thesis/b9_cwt_site.py`: the site runs.
- `docs/thesis/data/ch10_b9/`:
  - `events.csv` (one row per event, real and copies) and `spans.csv` (counts and seconds per span);
  - `modes.csv` and `counts.csv`;
  - `durations_hist.png` (a backend histogram, not a site screenshot);
  - `run.log` and `pilot_run.log`;
  - `site_runs.json` and `site_job*_cwt_payload.json`.
