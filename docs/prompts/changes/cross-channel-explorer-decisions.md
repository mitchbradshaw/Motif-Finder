# Cross-channel explorer — decisions (the cross-channel workshop, 2026-10-26 → 27)

The prompt is `cross-channel-explorer.md`. This note records what the researcher decided, and why, so the prompt's
D-numbers can be traced. The questions (Q1–Q26) were asked in three grilling rounds in the cross-channel workshop
session. Each opened in plain language, then gave options and a recommendation.

## In plain words

When two electrodes show activity at about the same time, there are three explanations:
- **The wiring:** one disturbance picked up through the shared ground. Like a door slamming and every room shaking at
  once.
- **The fungus passing a signal along:** it arrives at the next electrode a little later, by the same delay each time,
  like a train that keeps to a timetable.
- **Both fungi doing their own thing**, or reacting to the same outside event.

The page is being rebuilt to tell these apart in two ways:
- **A census nobody picked.** Every detected event on every channel, with every co-occurrence tested against luck.
- **Tools to look at and measure** any stretch by eye. Those measurements are labelled "looked for", because the eye
  finds faces in clouds.

The page also becomes the site's multichannel explorer: scroll, zoom, slide traces, add channels from other
recordings, and later temperature and humidity.

## Decisions

| # | Decision | From |
|---|---|---|
| D1 | The question is **B4** (Chapter 10's list, fixed 27 Oct; B7 there is multiscale entropy), framed openly: *is there evidence of a propagation lag between channels that is not artefact?* | Q1 (the rule "match the skeleton"; the skeleton renumbered after the answer) |
| D2 | M2's A, B, C and D are **four separate mushroom packs**. Propagation is judged only within a pack, and a signal shared across packs is never propagation. What 1 and 2 mean (A1 vs A2) is not known yet: the researcher will check. Positions will be estimated from photos, for every dataset. | Q2 |
| D3 | **Three layers:** candidates (census) → measure on demand (labelled *looked for*) → the claim (census). B4's numbers come only from the census. | Q3, Q9 |
| D4 | **All seven datasets**: M2_aug, M2_concat, CO_fs2, LM_fs2, MJu26a_fs2, SH_fs2, SO_fs2. The researcher runs the detector on the last three (their 2 Hz copies were registered 27 Oct). | Q4 |
| D5 | Build the page as described, with no deadline pressure: round B is a nice-to-have. Slices run in parallel within the three-agent limit. | Q5 |
| D6 | **Re-measure on the real database.** RQ6's 64 / 123 / 97 came from a sandbox copy on g-05 (4–5 Oct) and are history. | Q6 |
| D7 | **Common mode** stays inside the artifact bin (Q40b). It is marked by **breadth** (the same waveform at \|lag\| ≤ 1 s on more than half the channels, amplitude ratios within ×2) or by spanning two or more packs. A **median-reference** toggle subtracts the across-channel median: an event that vanishes there was common to all. | Q7 |
| D8 | **Propagation needs a timetable:** one pair's co-occurrences share a lag more consistently than chance. Ordering along the layout comes from lag against distance once positions exist. | Q8 |
| D9 | A **cross-pack copy** is an artifact, and so is every within-pack copy at that instant (common mode). A **cross-pack co-occurrence that is not a copy** is a new label, **shared driver**: never propagation, listed for the environment work. Recurrence still excludes only what a human confirms (Round 12). Cross-pack copies come first in the by-instant Review queue. | Q10 (b) |
| D10 | **Pack, x mm and y mm** are per-channel settings in Settings › Channels & events, on the audited path, editable there or by dragging dots on the pack map. M2-style names default to the letter. Other datasets are one **unassigned** pack: propagation is allowed, and every result says "layout unknown". | Q11 |
| D11 | **Build now:** a pack map (draggable dots, in mm) and **lag against distance** (propagation is a sloped line through the origin, slope = 1/speed; common mode sits at lag 0; independent is a cloud). **Future** (stub `Z-spatial-propagation-playback.md`): arrows between electrodes, **arrival playback showing the event morphing as it travels between channels**, a plane-wave speed and direction, and a rose plot of directions. The researcher wants to explore the playback once results exist. | Q12 |
| D12 | **Timeline strip:** Signal's `Overview` showing the first bold channel, with candidate ticks and human-marked artifact regions; the box can be ~1 min up to the whole recording. **Scroll-wheel zoom** on the detail plot, as on Signal. Measure acts on the inner box, ≤ 2 h. `?window=motif-n` and `?pad=` go. | Q13 (c) + addendum |
| D13 | **Channels from other datasets** join with their own offset: wall clock when both datasets have start times, else elapsed time. They carry an offset handle and a "no shared clock" badge. **No lag or r is ever computed across recordings** (Q40a). Environment series follow the same rule, on their own units. Registering them is a later prompt (`Z-environment-series.md`). | Q14 (a) |
| D14 | **Lanes:** drag to move a baseline, double-click to snap onto the bold channel, reset, all kept in the URL. One shared gain plus a y-zoom; a channel gets its own gain (÷N) only when it cannot fit. × removes a channel; + adds one (by pack, or from another dataset). Pack chips; the default is every channel; at most 24 series. | Q15 |
| D15 | **A reference** stays: the channel you came from, changeable with "make reference". Align-by-lag uses it; Measure reports every bold pair. | Q16 (a) |
| D16 | **Census:** the detector is choosable, default `drop_detection_v1`; a detector is "full" only when every channel has a real run, and v5 is the cross-check where full. Two events co-occur when their onsets are within 50 s. Lag and r are measured from 60 s before to 180 s after the earlier onset, on the same absolute samples, **with the lag searched only within ±50 s**. A census event takes a Library family label (a selectable grouping, default g-11) when it overlaps a member by ≥ 50 %. Counts are of events. | Q17 (c) |
| D17 | **Leaves the page:** the stacked view and its y and align controls, the window picker, the pad, "lag on whole channel" and "open design questions". **Stays:** detrend (moved into Measure), the detections chip, the action strip, and *Apply a template*. The classification tiles become Measure's panel; the family-classify card becomes a family filter. | Q18 |
| D18 | **The nulls:** rotation for co-occurrence excess, breadth and shared driver (K 1,000, offset ≥ 1 h); random time for waveforms (K 100, 95th percentile) and for Measure's span. Benjamini–Hochberg at q 0.05 per recording. Draws are seeded from the census hash. The one-draw detector surrogates are not used. **Timetable: see X1.** | Q19 |
| D19 | **Marks:** *Mark as propagation* and *Mark shared driver* write verdict `interesting`, a `cross_channel:` tag and a note (lag, r, channels, looked-for or census). *Mark artifact* is unchanged. No sixth verdict word. | Q20 (a) |
| D20 | The census is stored in new machine-only tables `cross_census` and `cross_cooccurrence`; null draws go to `.npz` on disk. Each run has a hash, and the page says **stale** when the runs, rule or packs have changed. The page never computes the census on load. | Q21 (a) |
| D21 | Library's *Classify across channels* is **unchanged** (stub `Z-library-classifier-on-census.md` to re-point it later). Census flags get a **by-instant** Suspected-artifact queue: one verdict lands on every channel's event span, and an artifact verdict there also takes out Library members it covers. | Q22 (a) |
| D22 | **Speed:** an envelope pyramid per channel on disk; first paint ≤ 2 s for 16 channels × 721 h; the census ≤ 2 min per recording, as a job with real progress and an estimate; Measure ≤ 5 s for 8 channels × 2 h. MJu26a's census runs on its 2 Hz copy. | Q23 (a) |
| D23 | **Waves:** {S1 census, S2 overlay page, S3 packs and positions} → {S4 Measure, S5 by-instant queue and marks, S6 pyramid} → {S7 candidates, S8 pack map and lag against distance, S9 other datasets}. S0, the layout reader, is added before wave 1 (X2). | Q24 |
| D24 | **Thesis outputs:** `scripts/thesis/b4_cross_channel.py` writes tables and figures to `docs/thesis/data/ch10_b4/` from the stored census, with the hash printed on each. | Q25 (a) |
| D25 | **Where things go:** the prompt and this note in `docs/prompts/changes/`; `docs/rq_roundB/B4-cross-channel.md`; a log line in RQ6; stubs in `docs/prompts/fixup/future/`. **Chapter 10 is not edited here**: the paragraph to paste is below. | Q26 |

## Choices this note makes that the rounds did not settle

- **X1 — the timetable null is a random-time lag pool, not rotation** (Q19 said rotation). **Confirmed by the
  researcher, 2026-10-27: "keep the random-time lag pool for the timetable null, as written."**
  - **The problem.** Events are sparse: about 43 per channel over 721 h, so two channels share an onset within ±50 s
    about 0.07 times per rotation draw. Almost every rotated draw has no co-occurrence at all, and a spread of lags
    cannot be computed from nothing.
  - **What the prompt does instead.**
    - It keeps the pair's number of co-occurrences fixed.
    - It asks whether their lags cluster more than lags measured between the same channels at random other times. Each
      draw resamples n lags from a pool of ≥ 2,000.
    - The statistic is the largest number of co-occurrences sharing one lag within ±2 s (their median lag and MAD are
      reported).
  - In plain words: rotation still answers "do they co-occur more than luck?". The timetable now answers a separate
    question: "given that they co-occur, do they keep time?"
  - If you'd rather keep rotation, the timetable can only be judged on pairs with dozens of co-occurrences.
- **X2 — S0.** A small reader for a channel's pack and position (`Working/channel_layout.py` plus one route), written
  by the manager before wave 1, so that the census, the page and Settings share one definition.
- **X3 — the median-reference view** is built inside S4 (Measure), since both are span tools that touch the same
  routes.
- **X4 — between S2 and S4 the page has no lags.** S2 drops today's every-fetch lag measurement. Align-by-lag is
  disabled, with its reason, until Measure lands. Merge S4 soon after S2.
- **X5 — new census numbers are named constants**, recorded on every census and in its hash, not Settings keys: the
  onset window (−60, +180 s), the timetable's ±2 s, both K values, the 1 h minimum rotation, the breadth fraction, the
  ×2 band and q. The bin lines stay the existing Settings keys.

## Waiting on the researcher (none of it blocks the build)

- What A1 and A2 (two channels per label) mean on M2.
- Electrode positions, estimated from photos, for every dataset.
- `drop_detection_v1` runs on MJu26a_fs2, SH_fs2 and SO_fs2.
- Which MJu26 sensor sits with which pack, and MJu26a's start time (see `Z-environment-series.md`). The sensor log
  (`Sensor data[…](2026-07-01-2026-07-28).csv`, 12 devices at about one reading a minute) is in the researcher's
  Downloads, not in the repo.

## For Chapter 10 (paste into `sec:rb_channels`; the thesis session owns the file)

```latex
\begin{instructions}
\textbf{B4}: is there evidence of a propagation lag between channels that is not artefact? (The plan's RQ6.)
M2's sixteen electrodes sit on four separate mushroom packs (A--D, from the electrode names), so propagation is
judged only within a pack: a waveform copied across packs at the same instant is a shared-ground artefact, and a
co-occurrence across packs that is not a copy is a \emph{shared driver} (both packs reacting to one stimulus), never
propagation.

Method (Explore $\rightarrow$ Cross-channel, rebuilt 27 Oct; \src{docs/prompts/changes/cross-channel-explorer.md}):
a census of \texttt{drop\_detection\_v1} events on every channel; two events co-occur when their onsets are within
50\,s; lag and $r$ are measured on the same samples from 60\,s before to 180\,s after the earlier onset, with the lag
searched within $\pm$50\,s. Bins: artifact ($|\text{lag}|\le1$\,s, $|r|\ge0.98$, beats its random-time null, both
swings over the noise floor), propagation (within a pack, 1--50\,s, $|r|\ge0.5$, beats its null), shared driver,
independent. Nulls: circular-shift rotation of each channel's event train for co-occurrence, breadth and shared
driver ($K=1000$); random-time windows for waveforms ($K=100$); for the timetable (a consistent lag per electrode
pair) the pair's co-occurrence lags against lags at random other times. Benjamini--Hochberg at $q=0.05$ per recording.
Data: M2\_aug, M2\_concat, CO, LM, and MJu26a, SH and SO at 2\,Hz. The census hash goes in the study's ``chain and
data'' line; figures from \src{scripts/thesis/b4\_cross\_channel.py} into \src{docs/thesis/data/ch10\_b4/}.

Spans picked by eye on the page are reported as \emph{looked for} and only as examples. The 64 / 123 / 97 figures of
RQ6 came from a sandbox copy on grouping g-05 and are replaced by the census.
\end{instructions}
```
