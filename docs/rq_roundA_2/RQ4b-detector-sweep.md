# RQ4b — Across every detection algorithm and its settings, where do they agree, and which find what a human accepts?

**Status (2026-10-17): the 27 variant templates exist; the sweep has not run; four pieces of infrastructure are
asked for.** *2026-10-18: P1, P2 and P3 are built (P3: windowed detection, below); the window bound at the sweep's
short scales waits on the researcher's decision.* This widens round A's RQ4 (`../rq_roundA/RQ4-bands-and-symbols.md`, which compared bands and symbols with
raw-signal methods) into a comparison of every detector in the app, each at up to five settings of its key parameter,
over every dataset and channel, read on Discovery › Map.

## In plain words

Every detector has a knob that decides how picky it is. You run each detector at a few knob settings over all the
recordings and look at the map of where each one fires. Where several agree, and where the places you have checked by
hand agree too, you learn which detectors and settings to trust. A detector that fires everywhere, or never, shows up
at once.

## What is known

### Variants

- **27 variant templates were created 2026-10-17** in the real database (ids 31–57) by `scripts/create_rq4_variants.py`.
  - Each is `<template>__<parameter>_<value>` with a description starting `[rq4-sweep]`. Base values are the existing
    templates themselves.
  - Undo: `--remove --apply --allow-project`.
  - They were checked in a sandbox first: valid chains, only the intended parameter changed, Discovery lists them.

| Template | Parameter | Values (base in bold) |
|---|---|---|
| drop_detection_v1 | slope_sigma (on stage_encoding *and* drop_detection) | 4 · **8** · 12 |
| drop_detection_v5 | same_fraction | 0.5 · **0.58** · 0.7 |
| wavelet_encoded | level | 3 · **4** · 5 |
| dehshibi_spikes, Wavelet_detection_prototype | epsilon_factor | 0.02 · **0.05** · 0.1 |
| mp_threshold | threshold | 6 · **8** · 10 |
| symbol_search | seconds_per_symbol | 10 · **20** · 40 |
| noise_threshold | k_sigma | 3 · **4** · 6 |
| signal_threshold | threshold, in the file's stored units: V copies (M2) and mV copies (L_LM, Schizophyllum, Dwij) | V: −0.002 · **−0.005** · −0.01; mV: −2 · −5 · −10 |
| deconvolved_troughs | recovery_half_s | 60 · **120** · 240 |
| OASIS_Deconvolution | impulse threshold | 3 · **3.848** · 5 |
| BEADs_invert_detect_v1 | delta_mv | 5 · **15** · 25 |

### Measured

- **Knobs (sandbox, M2_aug CH0, 452–456 h):**
  - `noise_threshold` k = 3 / 4 / 6 found 8 / 6 / 3 spans;
  - `drop_detection_v1` slope_sigma = 4 / 8 / 12 found **0 / 1 / 0**. That knob is not a simple sensitivity dial;
    read it on longer spans.
- **Local cost** (past runs, 2 channels × 721 h, 20 null draws each):
  - drop_detection_v5 ≈ 1 min, symbol_search ≈ 2 min, deconvolved_troughs ≈ 12 min, Wavelet_detection_prototype
    ≈ 32 min;
  - most detection blocks declare no cost estimate, so Discovery runs them locally whatever the size.
- **Discovery's template list** takes about 2.5–3 min to load on the real data, with or without the variants: it
  scores each template's last run. It will slow further as variants gain runs.

### Data and units

- 13 usable recordings, 129 channels, about 52,000 channel-hours.
  - The 7–10 Hz sets (L_LM, M1/M100/M101_t, MJu26a) hold over 90 % of the samples.
  - M2_aug_fs2 is the same experiment as M2_aug.
  - M1, M100, M101_t and MJu26a have **undeclared units**, so they are read as volts: declare them before any mV
    threshold means anything there.
- **Only M2_aug is densely human-labelled**, so the Map's human row, and therefore "right", can be read there.
  Elsewhere the Map shows rates and agreement only.

### The Map

- One row per distinct executed chain (a variant is its own row), read across every session.
- A cell is detections per covered hour. Where runs overlap, the newest run wins, so sections stitch without double
  counting.

### The held-out lock (a2-p1, 2026-10-17)

- **M4_aug follows Settings › Datasets' lock switch** (branch `a2/p1-held-out-lock`; live once it is merged and the
  bridge restarted). Off: Explore, Analyse, Discovery (scope, apply, seed search, the Map) and Review and Library use
  it like any other recording. On: every one of those refuses it again (423), and each refusal says how to unlock.
  No restart either way: every route reads the switch on every request.
- The real database has had the lock **off** since 2026-10-17 15:02 (audit 519), so M4_aug can join the sweep.
- RQ1's exam (iii) and the Library importers keep their own lock whatever the switch says.

### HPC template runs come back (P2, built 2026-10-17; report: the a2-p2 branch's report to the managing session)

- **The loop, built and tested here (not yet run on rangpur).** *Create SLURM script* writes one array job per ticked
  run (`Working/discovery/chain_job.py`): one task per channel, each running the real chain **and its null draws**
  (Settings › Nulls, 1 allowed) on a scratch database keyed to this machine's recording ids, resubmitting itself while
  its result reads incomplete. The run row is marked *on cluster* on the server. *Import results* (on the run's row,
  or Jobs › Waiting on the cluster) checks the spec, every hash and each recording's content, restores the step cache,
  and runs the chain here: the matrix profile is read from the cache, so the run lands on Runs, Compare, Review, the
  Scoreboard and the Map as a local run, in seconds. A missing or incomplete task is refused by name.
- **No recalculation:** an identical run reuses the imported run; a different threshold on the same profile reads
  the imported profile from the cache (the plan now counts only uncached steps, real run and draws alike).
- **Whole span:** the matrix-profile cap (678,125 samples here) is now checked only where the step computes: a
  cached profile is served at any length, an uncached one over the cap is routed to the cluster (not refused), and
  the cluster has no cap. A CPU profile too long for one job is computed in blocks (AB-joins, merged by the
  elementwise minimum; equal to the one-shot within float rounding), checkpointed per block.
- **Still to verify on rangpur (the researcher):** the `cpu` and `a100` partitions' real wall (only `a100-test`'s
  20 min is measured; `Working/config.py` `HPC_WALLTIME_MINUTES_BY_PARTITION`), and stump vs gpu_stump on the a100
  (`scripts/measure_gpu_stump.py`; `backend` stays in the cache key until then).
- **Not shared with Analyse yet:** Discovery runs hash a template's params as stored (the canonical templates store
  only the params they set), Analyse fills every default first, so the two do not share cache entries for the same
  chain unless the template stores every param.

### Windowed detection (P3, built 2026-10-18; report: the a2-p3 branch's report to the managing session)

- **What it is.** *Apply template* has **Windows** beside Channels and Bands: a length (10 min … 168 h, or any) and an
  overlap (50 % recommended, the default). Each window is an ordinary run of the chain over its own span, with its own
  null draws (Settings › Nulls), cached and reused when the same scope is applied again. Each channel's windows are
  then stitched into one result, and the stitch rule is written on the run (`meta`-style rules on the plan and the
  row). An event counts when one of its detections starts in its own window's core, the middle part that no
  neighbouring window sees more centrally. Detections of the same event from different windows are merged by
  Compare's matching rule. The extent kept is the view no window edge cut.
- **What reads it.** An application is **one Discovery run**, named by its scale (`noise_threshold · 1 h windows ·
  50 %`), made of one stitched run per channel. Runs, Compare, Review, the Scoreboard and the Map read the stitched
  set, so nothing is counted twice where windows overlap. The window length and overlap join the Map's row key: each
  scale is its own row, its own version of the algorithm.
- **What each window fitted** (noise σ, cutlines, the drop detector's slope floor) is kept per window run
  (`window_fits`), and the provenance of every stitched run is kept per window (`stitched_windows`).
- **The bound.** A window must be at least 4 × the chain's longest *context* window. That is a stretch the block
  reads around every point (a rolling mean, a baseline, a subsequence, a filter's period); near a window's edge the
  block sees half of it. A block that cuts its input into pieces (the Dehshibi scalogram's 3000 s pieces, SAX
  segments, Sliding windows) needs one whole *piece* instead. A shorter window is refused, and the refusal names the
  step. There are two explicit opt-ins. *Fit* scales those windows down to the window: a different chain, its own row.
  *Run it as it is* keeps the chain, and the run says so. What the bound means for the sweep's scales:

  | Template | Shortest window | Set by | 10 min | 1 h |
  |---|---|---|---|---|
  | mp_threshold, noise_threshold, signal_threshold, symbol_search | 40 min | detrend 600 s | refused (fit: 150 s) | runs |
  | drop_detection_v1, drop_detection_v5 | 5.5 h | detrend 4,917 s | refused (fit: 150 s) | refused (fit: 900 s) |
  | deconvolved_troughs | 4 h | detrend 3,600 s | refused (fit: 150 s, 150 s) | refused (fit: detrend 900 s, baseline 900 s) |
  | OASIS_Deconvolution | 8 h | BEADS baseline 7,200 s | refused (fit: 150 s) | refused (fit: 900 s) |
  | BEADs_invert_detect_v1 | 8.9 h | spike_v1 width 2,000 (a local average of 8,001 s) | refused (fit: 150 s, width 37) | refused (fit: baseline 900 s, width 224) |
  | dehshibi_spikes (and its two epsilon variants) | 50 min | 3000 s pieces | refused (fit: 600 s pieces) | **runs** |
  | Wavelet_detection_prototype | 50 min | the monolithic block's fixed 3000 s pieces | refused (cannot be fitted) | runs |
  | wavelet_encoded | 7.1 min | the level-4 wavelet's reach | runs | runs |
  | cnn_*_1min, cnn_*_10min | 1 / 10 min | their sliding window | runs | runs |
  | cnn_*_60min | 1 h | its sliding window | refused (fit: 600 s) | runs |

- **dehshibi_spikes runs in 1-hour windows** (3,600 samples, far inside the scalogram's 320,000-sample memory cap that
  keeps it off the whole signal): tested end to end.
- **The cluster.** A windowed run goes out through the same *Create SLURM script*, as one task per channel. Its spec
  names every window and its config hash; its result carries every window's detections. The import checks every
  window and writes the window runs; the local sweep then reuses them all and stitches. Measured: 16 channels of
  M2_aug in 1-hour windows are a 2 MB spec of 16 tasks (23,056 windows); in 10-minute windows, 12 MB (138,416). One
  target per window would have been 23,056 / 138,416 array tasks. See `HPC/README.md` › *Windowed chain jobs*.
- **Cost.** A run's own bookkeeping is about 0.33 s here, on top of the chain. A windowed application is thousands of
  runs, so that floor decides its route even where the blocks declare no estimate. 16 channels of M2_aug with one
  null draw: 1-hour windows are 46,112 runs (about 4 h of bookkeeping), 10-minute windows 276,832 runs (about 25 h).
  Both go to the cluster.
- **Measured on synthetic data** (`scripts/measure_window_defaults.py`; tables in *Decision: the window bound at the
  sweep's short scales* below).

### The CNN templates on real data (2026-10-18, `docs/prompts/blocks/reports/W4-A-evaluation.md`)

In plain words: the four CNNs read 10-minute windows well, 30-minute windows nearly as well, and 1-minute windows not
at all. They call almost every minute "interesting".

- **Blind labels (RQ1 queue 3, 986 interesting / not labels, each window resampled to 600 points):**
  - **10 min:** balanced accuracy **0.78–0.83 at 0.5 and 0.86–0.88 at 0.05–0.1** (AUC 0.93–0.96). Plain accuracy is
    0.90–0.92 against a majority baseline of 0.81.
  - **30 min:** 0.82–0.84 at 0.5 (AUC 0.92–0.93). Out-of-sample (M2_concat): GADF 0.87, GASF 0.86.
  - **1 min:** **0.39–0.51, AUC 0.30–0.46**: no better than a constant answer, and ranked backwards.
  - **Out-of-sample at 10 min:** M2_concat holds 13 interesting windows. The scores rank them well (AUC 0.81–0.91),
    but the 0.5 cut finds only a third of them.
  - **The ceiling:** the human agrees with themself on 94 % of 98 repeat pairs.
  - **No sign of recall:** M2_aug windows that overlap an earlier label score no better than the ones that do not.
- **One whole channel (M2_aug CH14, 721 h), share of windows ≥ 0.5:**
  - **1 min: 95–96 %.** That is 770–912 merged detections, covering nearly the whole recording.
  - **10 min: 9–12 %**, 253–343 detections.
  - **1 h: 40–54 %.**
  - No window was skipped. A 10-minute score is *anti*-correlated with its ten 1-minute scores (ρ ≈ −0.5).
- **Cost:** fusion ≈ 48 ms a window, the others ≈ 22–24 ms. One channel through all twelve templates takes ≈ 1.6 h on
  the PC; `cnn_fusion3_1min` alone takes 35 min.
- **Read-out consequence:** the four `cnn_*_1min` results from the overnight sweep are a negative control, not a
  detector. Start the 10-minute templates at **threshold 0.1** (sweep 0.05 · 0.1 · 0.2 · 0.5) and the 1-hour ones at
  0.5 (sweep 0.3 · 0.5 · 0.9; no 1-hour labels exist). If one model is picked, lean GASF, with GADF close.

### Agreement on M2_aug, and an instrument for "which find what a human accepts" (a2-rq1b, 2026-10-18)

In plain words: the overnight sweep's detections were grouped into candidate events. A blind, stratified sample of
them is ready to judge. Its answers give each detector family and each setting a precision with an interval. That is
step 1 of *How it gets answered*, measured on events nobody chose by hand. Details: `findings/rq1b-candidate-events.md`.

- **Coverage.** Some settings mark most of the recording: OASIS 61–65 % of the time, deconvolved_troughs at 60 s
  46 %, Wavelet_detection_prototype at ε 0.02 38 %, the 1-minute CNNs 90 %. Only about 6 % of M2_aug is caught by
  no detector.
- **Agreement predicts your labels.** The number of families covering a stretch gives AUC ≈ 0.8 against the old
  10-minute labels and the blind labels (CNNs left out). Over the 1.50 M candidate events the loose agreement gives
  AUC 0.874.
- **The sample** is 800 items: 100 per agreement level and 50 per selective family (drop_detection_v1 / v5,
  wavelet_encoded, symbol_search, BEADs, signal_threshold).
  - `scripts/rq1b_candidate_events.py estimate` reports precision per level, per family (the events it found) and per
    setting.
  - Your earlier verdicts count as known; the sample stands in for the rest.
- **What it is not:** the Map's hits per false alarm per hour. It is the share of a detector's events you would
  accept. Both can be read together.

### What blocks the full design today

1. ~~**Template runs on the HPC never come back.**~~ Built 2026-10-17 (P2, above); waits for the first real round trip.
   - *Create SLURM script* scripts only the first ticked run, has no null, and is capped at a 20-minute wall with no
     resume.
   - Jobs lists `detection_chain` results as having "no return path".
   - Only seed searches round-trip. → **P2.**
2. **Matrix-profile and wavelet blocks refuse long spans:**
   - ~~matrix profile: over 678,125 samples (≈ 188 h at 1 Hz), enforced in `Working/execution.py` even on the
     cluster;~~ no longer refused: routed to the cluster, uncapped there, served from the cache here (P2, 2026-10-17);
   - wavelet transform: over 320,000 samples — a memory limit, unchanged (P3's windows are the way round it).
     *Built 2026-10-18 (P3): dehshibi_spikes and its variants run in 1-hour windows.*
   → **P2.**
3. ~~**Detectors see one span at a time:** no sliding window, and most fit their thresholds to the span they are
   given.~~ Built 2026-10-18 (P3, *Windowed detection* above). The window bound at the sweep's short scales is the
   researcher's decision (below).
   → **P3.**
4. **The CNN template cannot run on whole recordings:**
   - it holds every image at once, and the run failed on 13 Oct at 651 MB > 2000 windows;
   - it never resamples;
   - its default model has one class.

   → **`docs/prompts/blocks/W4-A-cnn-window-scores.md`** (12 CNN templates: 4 models × 1 / 10 / 60 min).
5. ~~**M4_aug cannot be used** although the lock was turned off in Settings › Datasets at 15:02 today. → **P1.**~~
   Done by a2-p1 (2026-10-17): every refusal now obeys the switch; see *The held-out lock* above.

## Decisions already made (the researcher, 2026-10-17)

- The sweep covers every detection template plus new combinations, each at up to 5 values of its critical parameter,
  over every dataset and channel, compared on Discovery › Map.
- **Drop detection should run over sliding windows with overlap.** Looking only at the whole-span scale risks missing
  events. Window size and overlap become a step of setting up a detection run, with overlap recommended. (P3)
- **HPC template runs must come back to the Map,** to be viewed and verified in the website. Later reviews of the same
  algorithm reuse cached results instead of recalculating, above all for matrix profiles. (P2)
- **Matrix-profile algorithms take the entire span.** The time limit only governs local runs, and the researcher will
  run most matrix-profile algorithms through SLURM. (P2)
- **A null of 1 draw is allowed** for sweeps (Settings › Nulls; the floor was 20). Changed in
  `webui/client/src/settings/NullsPage.tsx` on 2026-10-17. A kind that reports a p is still bounded by the α check.
- **M4_aug is used for demos from now on** (P1); see RQ1b's open decision on the held-out exam.
- **2026-10-17, evening: the first sweep runs overnight on the cluster, before P2 merges.** It covers M2_aug, all 16
  channels, the whole signal, 1 null draw.
  - What runs: the 13 base templates and the 24 volts variants, plus the 12 W4-A CNN templates.
  - Results come back later: an adoption step registers each job as a waiting Discovery run once P2 is merged.
- **Scales:** 10-minute and 1-hour windows plus the whole signal, each scale treated as its own version of the
  algorithm (its own Map row). Windows wait for P3, and the decision is written into P3's brief.
- **Matrix profile, first look:** the real signal on CH1_A1 and CH2_A1 on the A100. It is run as one
  `mp_threshold` with `backend: auto` and its null, so the other three MP templates can read the profiles from the
  cache. *(Correction, 2026-10-18, P2 fix round: as things stand they cannot. They say `backend: "stump"`, which
  keys apart. The decision is under* What is still needed*.)*
- **The account runs three jobs at once, CPU and A100 together.** The sweep is therefore packed into two CPU and
  two A100 jobs; the fourth queues.
- **2026-10-18, the window bound at the short scales: as recommended** (the *Decision* below).
  - *Refuse* stays the default.
  - The drop detectors run their 1-hour scale *as they are* (warned).
  - The 10-minute scale is run only for the 600 s threshold family, *as it is*: not `drop_detection_v1`, and
    `dehshibi_spikes` fitted or not at all.
- **2026-10-18, the stitch's rescue: kept, as recommended.** A windowed run's × null is read within one scale only.

## What is still needed

| Step | Owner |
|---|---|
| ~~The held-out lock honours Settings › Datasets~~ — done 2026-10-17, a2-p1 (branch `a2/p1-held-out-lock`) | ~~P1~~ |
| ~~HPC template runs return as real Discovery runs, cached and reusable; matrix profile over the whole span on the cluster~~ built 2026-10-17 (see *HPC template runs come back*) | P2 |
| The first real round trip on rangpur (export → copy → sbatch → bring `return/` back → Import results); read the `cpu` / `a100` walls; run `scripts/measure_gpu_stump.py` on the a100 | researcher |
| ~~Windowed detection: window length + overlap as a run setting, results stitched and de-duplicated~~ built 2026-10-18 (see *Windowed detection*) | P3 |
| Decide the window bound at the sweep's short scales: refuse, fit, or run as it is (below) | researcher |
| Pick each drop detector's window length (measured below: drop_detection_v1 24 h, drop_detection_v5 12 h, wavelet_encoded 12 h on synthetic data), then check on M2_aug against the human row: `scripts/measure_window_defaults.py --db <sandbox copy> --recording-ids …` | researcher / manager |
| The windowed sweep on rangpur: *Create SLURM script* on a windowed run, bring `return/` back, *Import results* | researcher |
| Explore's run list folds a windowed application's window runs under its stitched run (46,112 window runs make `corpus.run_methods` take 8.5 s; the whole windowed RQ4 sweep on M2_aug would add about 2 million) | follow-up (Explore) |
| The CNN window-score block and its 12 templates | W4-A |
| Declare units for M1, M100, M101_t, MJu26a | researcher |
| The sweep: null draws 1, apply every variant per dataset (M2_aug, M2, Schizophyllum and L_LM first) | researcher |
| The read-out: Map level 3 → 2 → 1 on M2_aug against the human row; Compare best variants against drop_detection_v1 and against verdicts; one variant per template re-run with 20 null draws | researcher |
| Decide how the overnight matrix profiles serve the other MP templates (below) | researcher |

### Decision: the overnight matrix profiles and the other matrix-profile templates (P2 fix round, 2026-10-18)

**In plain words.** The overnight sweep computes the matrix profile once, as `mp_threshold` with `backend: "auto"`.
The plan was that `mp_threshold` at thresholds 6 and 10, and `mp_motifs`, would then read the same profiles from the
cache. They will not. Those three templates say `backend: "stump"`, and the cache key holds every parameter, the
backend included. So after the import they still need their own profile, and on the whole signal that means the
cluster again. Both backends are exact, so the two profiles should be the same within float rounding. That has not
been measured on the A100 yet.

**Why the key is not simply changed.** Every overnight matrix-profile spec carries step keys (prefix hashes) that
include the backend. The import recomputes them and refuses a result whose keys moved. Taking the backend out of the
key would refuse the overnight results. `tests/test_rq4_overnight_specs.py` now guards those keys.

**Options.**

1. **`backend: "auto"` variants of the other matrix-profile templates (data, no code).**
   - What: `mp_threshold__threshold_6`, `mp_threshold__threshold_10` and `mp_motifs`, each copied with
     `backend: "auto"`. Their detrend → profile steps are then the overnight ones.
   - What it gives: their runs over the same whole-signal section, with the same null (phase randomisation, seed 0,
     1 draw), read the imported profiles. Only the threshold or motif step computes, in seconds.
   - Cost: three more templates, each its own Map row beside the `stump` ones. More null draws would compute their
     own profiles.
2. **A read-only cache alias across the exact backends.**
   - What: a chain that asks for `stump` is served a cached `auto` (or `gpu_stump`) profile of the same prefix.
   - When: only after `scripts/measure_gpu_stump.py` confirms on the A100 that the backends agree (the profile
     within rounding, the same spans at thresholds 6, 8 and 10).
   - The key stays as it is, so the overnight imports are untouched; the alias works at lookup.
   - Cost: code in the step cache's lookup and in the plan's cache status, and provenance has to say "profile served
     from `auto`".
3. **Leave them separate.** The `stump` templates get their own profiles from the cluster in a later sweep. They
   share one detrend → profile prefix, so that is a second set of four profiles (two channels, real and draw), read
   by all four `stump` templates.

**Recommendation.** Take (1) now. It costs no code and keeps every hash. The three readings come from the overnight
profiles within seconds of the import, and the Map's own rows say how they were computed. Consider (2) only once the
A100 measurement shows the backends agree, and only if the `stump` templates' history should join up. Until then a
profile served across backends would be a claim nobody has checked. Neither is built.

**Measured on the A100, 2026-10-18** (the researcher ran `HPC/Detection/measure_gpu_stump.sh`; the files are in
`findings/gpu-stump-2026-10-18/`).

- **The backends agree.** Job 671107 on a100-1 (stumpy 1.14.1, 8 CPUs) compared `stump` with `gpu_stump` on coloured
  synthetic series:

  | n | m | largest relative difference | nearest neighbours the same | samples changing side at 6 / 8 / 10 |
  |---|---|---|---|---|
  | 50,000 | 60 | 6.5e-11 | 100 % | 0 / 0 / 0 (spans 145 = 145) |
  | 50,000 | 600 | 7.1e-12 | 100 % | 0 / 0 / 0 (spans 8, 23, 67 on both) |
  | 200,000 | 60 | 2.3e-10 | 100 % | 0 / 0 / 0 (spans 269 = 269) |
  | 200,000 | 600 | 3.3e-11 | 100 % | 0 / 0 / 0 (spans 16, 135, 252 on both) |

  That is float rounding: no cut reads a different span. Option 2 is no longer an unchecked claim.
- **A whole channel fits one a100 job.** Job 671109 timed `gpu_stump` alone on 2,596,000 samples (one 721-h
  channel) at m = 60: **736 s, 12.3 min.** (It was then stopped by the 20-minute `--time` it was given, during the
  m = 600 run.) On this PC's 16 CPUs the same profile is about 3.7 h, so the A100 is about 18 times faster.
  - The `a100` partition runs 5 hours: the 20-minute limit met before was `a100-test`'s own. This is recorded in
    `Working/config.py` (`HPC_WALLTIME_MINUTES_BY_PARTITION`).
  - So a whole-channel profile is one a100 task, with room for about 20 draws of the null at 12 minutes each.
  - Computing in blocks is only needed on the CPU.
  - At 50,000–200,000 samples the GPU was slower than the CPU (8 against 1 s, 32 against 17 s), because it is
    starting up; the A100 pays off only on long spans.

**Recommendation, updated.** The measurement makes (2) safe. (2) is the better answer:
- Your existing `stump` templates, with their history and their own Map rows, read the overnight profiles.
- No new templates are needed.
- Provenance says the profile was served from `auto`, with this measurement as the reason.
- It is code (the step cache's lookup and the plan's cache status), so it is built test-first and gated like the round's
  prompts.

(1) is still the zero-code route if the profiles are needed before that lands.

### Decision: the window bound at the sweep's short scales (P3, 2026-10-18)

**In plain words.** Most detectors first look at a stretch of signal around every point: a rolling average that takes
out slow drift, a baseline, a filter. Near the edge of a window a detector sees only half of that stretch, so what it
computes there is off, like reading a page with its margins torn away. The rule built in asks a window to be at least
four times that stretch, so that at most a quarter of each window is affected.

- Most of your templates average over 10 minutes, so the rule sets a 40-minute minimum and refuses the 10-minute
  scale.
- The two drop detectors average over 82 minutes, so the rule refuses their 1-hour scale too.
- The BEADS, OASIS and deconvolution templates need 4 to 9 hours (table under *Windowed detection*).

**The options.** All three are built; the first is the default.

1. **Refuse.** The scale does not run; the refusal names the step and the minimum. Nothing distorted is ever computed.
2. **Fit the chain to the window.** The averages that are too long shrink to a quarter of the window (600 s → 150 s at
   10 minutes; 82 min → 15 min at 1 hour) and are written into the recipe. It is a different algorithm, with its own
   row on the Map. The cost: events slower than the shortened average are partly averaged away.
3. **Run it as it is, with a warning.** The chain is unchanged; the plan and the run say which step overruns the
   window's edges. The cost: the edges are distorted, and nobody has yet measured by how much on real data.

**Measured.** Synthetic recordings at 1 Hz, 48 h long: `scripts/measure_window_defaults.py --short-scales`, no null.
Each cell is the share found of the two kinds of event. Pure AR(1) noise gave no detections, with three exceptions:
noise_threshold at 10 minutes as it is found 0.04 an hour; drop_detection_v5 at 10 minutes found 0.02 an hour, fitted
or as it is; and wavelet_encoded fires on noise at 3.3–3.9 an hour at every scale, the whole span included (its own
null fires as often).

| Chain | Events | Whole span | 1 h | 10 min, fitted | 10 min, as it is |
|---|---|---|---|---|---|
| noise_threshold (600 s detrend) | 60-s dips · 30-min drops | 100 % · 28 % | 100 % · 28 % (within the bound) | 49 % · 4 % | 94 % · 6 % |
| drop_detection_v1 (82-min detrend) | weak drops in a quiet stretch · deep drops in a loud one, one an hour | 0 % · 88 % | 100 % · 100 % (fitted and as it is alike) | 0 % · 0 % | 0 % · 0 % |
| drop_detection_v5 | the same | 22 % · 100 % | 100 % · 100 % (both; 20 % more detections than drops) | 100 % · 100 % | 100 % · 96 % |
| wavelet_encoded (within the bound at both) | the same | 0 % · 100 % | 56 % · 100 %, but 2.9 detections an hour for 0.9 drops | 6 % · 23 % | (the same) |

In 6-hour windows (within every drop detector's bound): drop_detection_v1 67 % · 69 %, drop_detection_v5
100 % · 100 %, wavelet_encoded 33 % · 100 %.

**The drop detectors' window length** (the prompt's 12 / 24 / 72 / 168 h; `scripts/measure_window_defaults.py`, 336 h at
1 Hz, one null draw per window). The recording is a loud background (five times the noise, a deep 0.3 drop every hour)
holding quiet stretches of 6, 12, 24, 48 and 96 h, with a weak drop every hour. The weak drops are 0.02 deep (under the
drop detector's 10 % depth gate against a deep drop in the same span) or 0.04 (above it). AR(1) and random-walk
recordings hold nothing. Weak drops found, per quiet-stretch length:

| Detector | Scale | weak 0.02: 6 · 12 · 24 · 48 · 96 h (all) | weak 0.04 (all) | deep | off-event / h | noise / h (its null) |
|---|---|---|---|---|---|---|
| drop_detection_v1 | whole | 0 · 0 · 0 · 0 · 0 (0 %) | 67 % | 93 % | 0 | 0 (0) |
| | 12 h | 0 · 36 · 52 · 57 · 62 (56 %) | 66 % | 83 % | 0 | 0 (0) |
| | **24 h** | 0 · 0 · 0 · 38 · 57 (40 %) | **82 %** | 91 % | 0 | 0 (0) |
| | 72 h | 0 · 0 · 0 · 0 · 23 (12 %) | 69 % | 90 % | 0 | 0 (0) |
| | 168 h | 0 (0 %) | 68 % | 94 % | 0 | 0 (0) |
| drop_detection_v5 | whole | 0 (0 %) | 100 % | 100 % | 0 | 0 (0) |
| | **12 h** | 0 · 55 · 78 · 89 · 95 (**86 %**) | 100 % | 100 % | 0 | 0 (0) |
| | 24 h | 0 · 0 · 0 · 51 · 76 (53 %) | 100 % | 100 % | 0 | 0 (0) |
| | 72 h | 0 · 0 · 0 · 0 · 38 (20 %) | 100 % | 100 % | 0 | 0 (0) |
| | 168 h | 0 (0 %) | 100 % | 100 % | 0 | 0 (0) |
| wavelet_encoded | whole | 0 (0 %) | 0 % | 100 % | 0 | 3.7 (3.9) |
| | **12 h** | 0 · 0 · 65 · 36 · 38 (38 %) | **87 %** | 100 % | 0.37 / 0.04 | 3.6 (3.8) |
| | 24 h | 0 · 0 · 0 · 45 · 30 (28 %) | 62 % | 100 % | 0.25 / 0 | 3.6 (3.8) |
| | 72 h | 0 · 0 · 0 · 0 · 17 (9 %) | 22 % | 100 % | 0.07 / 0 | 3.6 (4.0) |
| | 168 h | 0 (0 %) | 0 % | 100 % | 0 | 3.7 (3.9) |

- No window length raised detections on pure noise above the whole span's.
- Windows help only where a window fits inside a quiet stretch without a deep drop in it. The 6-hour stretches were
  missed at every length; the weak-under-the-gate drops in the 12-hour ones were found only by 12-hour windows.
- drop_detection_v1 loses deep drops in short windows (93 → 83 % at 12 h). The window whose core holds a drop's onset
  sometimes misses it, because its own refitted cutlines judge it so; its neighbour found it, but the core rule lets
  the owner decide.
- Recommended: **drop_detection_v1 24 h, drop_detection_v5 12 h, wavelet_encoded 12 h.**
- On the 48-hour recording with a drop every hour (the table above), 1-hour windows did better still for both drop
  detectors, which is why 1-hour windows are recommended for the sweep.

**Recommendation.**

- Keep *refuse* as the default. A short window should never run distorted unless someone chose it.
- **1-hour scale:** run the two drop detectors *as they are*. On this synthetic it was the best of every scale for
  both, equal to fitted. The chain stays the algorithm you named, which matches "each scale is a new version of the
  detection algorithm". For BEADS / OASIS / deconvolved_troughs, measure on M2_aug first: their 1–2 h baselines would
  cut every recovery. Treat wavelet_encoded's 1-hour windows with care: its quiet windows add noise detections.
- **10-minute scale:**
  - the 600 s threshold family *as it is* (fast events 94 %, against 49 % fitted);
  - drop_detection_v5 either way;
  - wavelet_encoded and the 1- and 10-minute CNNs as they are (within their bound);
  - dehshibi_spikes fitted (600 s pieces), or not at all;
  - drop_detection_v1 not at all: a drop and its recovery outlast the window, 0 % either way.
- Before trusting a short scale, check one template per family on M2_aug against the human row:
  `scripts/measure_window_defaults.py --db <sandbox copy> --recording-ids … --scales 1,0.1667 --allow-short` (and
  again with `--fit`).

### The stitch, the null and Explore (P3 fix round, 2026-10-18)

*In plain words.* Four things changed in how a windowed run is joined up and read. An event that a window boundary
cuts in two is now one event, not two. An event that the deciding window missed, but its neighbour saw whole, is now
kept. Explore, the run history and the disagreement counts show a windowed application once (its stitched run), not
once per window. A block-shuffle null is now drawn in every window, with one block length per channel.

- **The rule, as the run states it** (`Working/discovery/windowed.py` `RULES`, shown on the window card and the run):
  1. *windows*: windows of one length, a new one every length × (1 − overlap), the last moved back to the end.
  2. *core*: the window whose core holds an event's onset decides whether it is there.
  3. *rescue* (new): if that window found nothing there at all, the event is kept from a neighbour that saw it whole,
     at least half the chain's longest context window inside its own edges. It is marked *rescued*.
  4. *duplicates* (extended): two detections from different windows are one event by Compare's rule; or when one is
     a view a window edge cut short, lying inside the other with its uncut edge where the other's is; or when they
     are the two halves of an event cut at one boundary (at 0 % overlap the halves only touch). An event holds at
     most one detection from each window. It is kept once: as the view no edge cut, or as the union of the pieces
     (marked *merged*).
  5. *provenance*, 6. *refit*, 7. *bound*, 8. *null* as before (8 now says what × null compares, below).
- **What the owner rule lost, and what the rescue gives back.** The critic's probe signal: 24 h at 1 Hz, 66 planted
  dips and drops, a loud 6 h; noise_threshold (600 s baseline, 4 σ) in 1-hour windows. The same window runs stitched
  with the rescue off and on:

  | Overlap | Planted events a window saw | Lost by the owner rule | Lost with the rescue | Kept (off → on) | Kept twice |
  |---|---|---|---|---|---|
  | 0 % | 50 | 0 | 0 | 50 → 50 | 0 (1 before the fix) |
  | 25 % | 51 | 3 | 2 | 48 → 49 | 0 |
  | 50 % | 54 | 4 | 2 | 50 → 52 | 0 |
  | 75 % | 57 | 7 | 1 | 50 → 56 | 0 |
  | 90 % | 60 | 9 | 3 | 51 → 57 | 0 |

  Nothing kept lies off the planted events, and no two kept spans overlap, at any overlap. The whole-span run finds
  48 of the 66. On pure noise (24 h, a sensitive cut, 3 null draws) the run with the rescue finds less than its null:
  × null 0.56 and 0.55 (AR(1), 1-h and 4-h windows; 0.67 and 0.85 without), 0.45 and 0.62 (random walk; 0.65 and
  0.67 without). The rescue is the rule (`RESCUE`).
- **The null compares within one scale, not across scales.** Each window draws its own null, so × null says how a
  scale's run compares with the same scale's null. A 1-hour application's × null and a 10-minute one's are not on one
  footing. And each window's null is its own surrogate, so neighbouring windows' nulls do not share their overlap:
  the rescue keeps more null spans than real ones. That makes × null cautious (it reads low), never generous.
- **Block shuffle, one block per channel.** A block shuffle's block is twice the longest motif under test. Sized per
  window, a window that found nothing had no block and drew no null, and the stitched null counted nothing there.
  Measured on pure noise (scratchpad `block_bias.py`): that left out 16 % of the null (AR(1), 1-h windows, 22 of 47
  windows empty), 26 % (random walk, 1 h) and 8 % (AR(1), 4 h), so × null read high. Now the block is twice the
  longest detection any window of the channel found, and every window draws. A channel where no window found
  anything draws no null, and says so. Phase randomisation (the default) is unchanged.
- **Explore shows a windowed application once.** Its window runs are parts of its stitched run
  (`queries.not_window_part`). Explore's spans, ribbons, counts, run list and coverage, the disagreement counts with
  no run picked, a review queue over a run group, and the run history read the stitched run only. A window run is
  still read when asked for by its id.
- **Before the 10-minute sweep: try it on a subset, or in a separate database.** Every window is a run with its
  detections and its draws. The critic measured about 1.5 KB per window and its draw (31 MB for 20,000). 13
  templates in 10-minute windows over 16 channels of 721 h are 1.8 million windows: about 3 GB more database. Run
  one or two channels over a day first, or the sweep in a copy of the database.
- **Planning is fast enough to stay where it is.** Planning, exporting and re-planning a windowed run hashed every
  window's whole recipe. Now each channel's chain is hashed once. Warm, 16 channels × 721 h, one null draw: 10-minute
  windows plan in 3.9 s (was 45.7 s), export in 0.8 s (19.7 s), re-plan on import in 4.1 s (67.2 s); 1-hour windows
  0.4 s, 0.3 s, 0.8 s (9.1, 2.7, 10.2 s). Applying 13 templates at 10 minutes is still about a minute.
- **Windowed chain-job specs are version 2.** Plain specs stay version 1, hash for hash. Cluster code from before P3
  refuses a version-2 spec when the task starts. Update the code on the cluster before sending a windowed run.
- **Small fixes.** A fitted chain is one run whichever way it was reached. "Fit" or "run as it is" that changes
  nothing is not recorded. The shortest window is never rounded down: 66.7 min, not "1.1 h". The window card plans
  with the chosen bands, and a band whose filter needs a longer window is named.

## How it gets answered

1. For each detector, pick the variant that best matches the human row on M2_aug (hits on accepted spans per false
   alarm per hour). *Since 2026-10-18 (a2-rq1b), a precision per setting with an interval comes from the stratified
   candidate-event sample: `findings/rq1b-candidate-events.md`.*
2. Show how much the detectors agree across all datasets (Compare's union / only-A / only-B).
3. Report each chosen variant against its 20-draw null.

## Open decisions

- **The CNN templates' thresholds, and whether the 1-minute ones stay in the sweep** (W4-A evaluation, 2026-10-18).
  In plain words: the 0.5 cut was a guess. Against the blind labels, 0.1 suits the 10-minute models better, and no
  cut rescues the 1-minute ones. Options:
  (a) change the 10-minute templates' default to 0.1 and drop or retire the 1-minute ones;
  (b) keep every default and only sweep the cut;
  (c) keep the 1-minute templates as a labelled negative control.
  **Recommended:** (a) for 10 minutes, plus (c) for 1 minute. Label a few dozen 1-hour windows blind before trusting
  `cnn_*_60min`.

- **Which single figure picks the "best" variant:** a hit rate against accepted human spans; a precision at a fixed
  alarm rate; or the agreement with the other detectors (no ground truth needed, but it rewards the herd).
- **Whether windowed runs (P3) become the default for drop detection,** or stay a choice beside the whole-span run.
  *Measured 2026-10-18 (P3, the tables above): on synthetic recordings windows recover weak drops the whole span misses
  (drop_detection_v1 0 → 40–82 %, v5 0 → 86 %) and add no noise detections; on M2_aug it is not measured yet.
  Recommendation: a choice, beside the whole-span run, until M2_aug's human row agrees.*
- ~~**The window bound at the sweep's short scales** (refuse, fit, or run as it is): *Decision* above.~~ Decided
  2026-10-18, as recommended (*Decisions already made*).
- ~~**The rescue** (P3 fix round, 2026-10-18): it is the stitch rule now (the table in *The stitch, the null and
  Explore*). *Options:* keep it (recommended: no event kept twice, up to six more planted events at 75–90 % overlap,
  and × null on noise only reads lower); keep it for the run but not the null (× null would read higher than it
  should); or drop it (3–9 of about 55 events lost at 25–90 % overlap). *Recommendation: keep it.*~~ Kept, 2026-10-18
  (*Decisions already made*).

## Log

- 2026-10-17 · set up · 27 variant templates created (ids 31–57); null floor 20 → 1; the four infrastructure prompts
  (P1–P4) and W4-A written; measurements recorded.
- 2026-10-17 · a2-p2 · template runs round-trip to the cluster (chain job, import into the step cache, the local
  sweep writes the rows); the matrix-profile cap is routing, not a refusal; profile files named by span and key;
  chunked profiles; walls per partition recorded (only a100-test's measured).
- 2026-10-17 · overnight sweep · 43 P2 chain jobs, 674 tasks, packed as `rq4_cpu1/2` (cpu, 8 cores, 20-min wall,
  chained) and `rq4_gpuA/B` (a100, 8 cores, no `--time`).
  - Where it lives: branch `rq4/sweep-code` (main + `a2/p2-hpc-round-trip`, not main), in the worktree
    `.claude/worktrees/rq4-sweep`. The generator is `scripts/rq4_overnight.py` there; it writes
    `HPC/Detection/generated/rq4_overnight/`.
  - Checked locally: the merged tree passes `tests/test_chain_job.py` and `tests/test_template_cnn_window_scores.py`
    (55). Four packs on a 5.5 h section ran 50 tasks with no crash. P2's `verify_results` and `restore_cache`
    accepted every result.
  - Measured locally, one whole-signal task (real run + 1 draw, one channel), the PC loaded: 133–415 s and
    18–56 MB per CPU task. About 20 GB comes back in all.
  - Not yet: run on the cluster, imported, or read.
- 2026-10-17 · a2-p1 · the held-out lock obeys Settings › Datasets everywhere but exam (iii) and the Library importers;
  with the lock off (as it is in the real database) M4_aug can be swept like any other recording.
- 2026-10-18 · a2-p2 fix round · main merged into the branch. The overnight specs are now a committed guard
  (`tests/test_rq4_overnight_specs.py`: every spec, config, prefix and draw hash, and the local plan's recipes).
  - The other MP templates do not read the `auto` profiles; decision above.
  - Import fixes: a held-out (M4) target exported with the lock off runs on the cluster; a task that crashes writes
    a result saying why; a restore that fails part-way reads failed with its reason; the restore can be cancelled
    between entries.
  - Analyse no longer writes the old one-way SLURM job for an over-cap profile; it points to Discovery's chain job.
- 2026-10-18 · a2-p3 · windowed detection built: the window scope on *Apply template* (50 % overlap recommended),
  each window an ordinary cached run with its own null, the windows stitched into one Discovery run, its scale its own
  Map row. The bound refuses short windows by step, with two opt-ins: fit the chain, or run it as it is, warned.
  Windowed runs export as one chain-job task per channel; the import writes the window runs. dehshibi_spikes runs in
  1-hour windows. Measured the drop detectors' window length and the short scales (tables above). `init_db` no longer
  rescans every run for legacy rows on every open; thousands of window runs had made that 0.2–1.4 s per open.
- 2026-10-18 · a2-p3 fix round · the stitch joins the halves of an event cut at a boundary (0 % overlap counted
  one twice), matches a cut view inside a whole one, pairs one detection per window, and rescues an event its
  owner missed (measured, adopted). Explore, the divergence, group queues and the run history read a windowed
  application once. A block-shuffle null uses one block per channel (the per-window block left 8–26 % of the null
  out). Windowed specs are version 2. Planning 10-minute windows over 16 channels: 46 s → 4 s. The legacy scan's
  mark is kept per database file.
- 2026-10-18 · W4-A evaluation · the four CNNs on real data (`docs/prompts/blocks/reports/W4-A-evaluation.md`): on
  the RQ1 blind labels they work at 10 min (balanced accuracy 0.78–0.83 at 0.5, 0.86–0.88 at 0.1) and at 30 min
  (0.82–0.84), and fail at 1 min (0.39–0.51, AUC < 0.5). On M2_aug CH14 they call 95–96 % of 1-minute windows
  interesting. Recommended: 10-minute threshold 0.1; 1-minute templates read as a negative control. Read only; no
  code changed.
- 2026-10-18 · the researcher · the short scales as recommended (drop detectors at 1 h as they are; 10 min only for
  the 600 s threshold family, as it is); the stitch's rescue kept.
- 2026-10-18 · the researcher · the A100 check: `stump` and `gpu_stump` agree within float rounding (≤ 2.3e-10, no
  sample changing side at 6, 8 or 10); one whole channel's profile takes 12.3 min on the A100; the `a100` partition
  runs 5 h (recorded in `Working/config.py`). The matrix-profile decision now recommends the cross-backend alias.
- 2026-10-18 · a2-rq1b · the M2_aug sweep merged into 1.50 M candidate events, each carrying which families agree.
  Agreement predicts the human labels (AUC 0.874). A stratified 800-item blind sample and the estimator give
  precision per family and setting. Not merged. `findings/rq1b-candidate-events.md`.
- 2026-10-18 · batch 2 · the sweep extended to three more recordings, one submission
  (`HPC/Detection/generated/rq4_batch2/submit_rq4b.sh`, `scripts/rq4_overnight.py build-batch`):
  - **Recordings:** M2_concat (16 ch, 1 Hz, V), M4_aug (16 ch, 1 Hz, undeclared, read as V) and L_LM_Jul_26_J
    (5 ch, 10 Hz, mV). That is 125 chain jobs and 1,543 tasks.
  - **MJu26a was swapped for L_LM by the researcher:** MJu26a is unevenly sampled (dt 0.124–2.83 s; at 7.25 Hz it
    reads as 564 h against about 636 h of real time). L_LM looks like five of its channels retimed to 10 Hz and
    ×1000: block profiles correlate 0.87–0.97 and the spread ratio is 981–1029.
  - **MJu26a's units:** it is declared mV but looks like volts. It was not built, so nothing depends on that yet.
  - **Same settings as M2_aug:** whole signal, 1 phase-randomise draw, all CPU and CNN templates; a millivolt
    recording runs the three mV `signal_threshold` copies instead of the V ones.
  - **Matrix profile:** on the first two channels of M2_concat and M4_aug; left out of L_LM, where a whole-channel
    profile would take about 16 h on the A100.
  - **Left out of L_LM:** the three `Wavelet_detection_prototype` runs. `dehshibi_spikes` needs a 99 × n array
    (16.9 GB there; measured, the allocation failed). They wait for windows.
  - **Memory:** L_LM tasks measured locally at up to 5.3 GB (`wavelet_encoded`, 9 min) and 3.75 GB
    (`deconvolved_troughs`), so L_LM's CPU tasks get their own pack, 3 at a time. M2_concat and M4_aug run 8 at a
    time.
  - **M4_aug is the held-out exam (RQ1b):** its results are for the Map and the detector comparison only. Keep M4
    detections out of Review promotions and *Add N matches*. The import needs the held-out lock still off.
  - Not yet run on the cluster.
