# RQ4b — Across every detection algorithm and its settings, where do they agree, and which find what a human accepts?

**Status (2026-10-17): the 27 variant templates exist; the sweep has not run; four pieces of infrastructure are
asked for.** This widens round A's RQ4 (`../rq_roundA/RQ4-bands-and-symbols.md`, which compared bands and symbols with
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

### What blocks the full design today

1. **Template runs on the HPC never come back.**
   - *Create SLURM script* scripts only the first ticked run, has no null, and is capped at a 20-minute wall with no
     resume.
   - Jobs lists `detection_chain` results as having "no return path".
   - Only seed searches round-trip. → **P2.**
2. **Matrix-profile and wavelet blocks refuse long spans:**
   - matrix profile: over 678,125 samples (≈ 188 h at 1 Hz), enforced in `Working/execution.py` even on the cluster;
   - wavelet transform: over 320,000 samples.
   → **P2.**
3. **Detectors see one span at a time:** no sliding window, and most fit their thresholds to the span they are given.
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
  cache.
- **The account runs three jobs at once, CPU and A100 together.** The sweep is therefore packed into two CPU and
  two A100 jobs; the fourth queues.

## What is still needed

| Step | Owner |
|---|---|
| ~~The held-out lock honours Settings › Datasets~~ — done 2026-10-17, a2-p1 (branch `a2/p1-held-out-lock`) | ~~P1~~ |
| HPC template runs return as real Discovery runs, cached and reusable; matrix profile over the whole span on the cluster | P2 |
| Windowed detection: window length + overlap as a run setting, results stitched and de-duplicated | P3 |
| The CNN window-score block and its 12 templates | W4-A |
| Declare units for M1, M100, M101_t, MJu26a | researcher |
| The sweep: null draws 1, apply every variant per dataset (M2_aug, M2, Schizophyllum and L_LM first) | researcher |
| The read-out: Map level 3 → 2 → 1 on M2_aug against the human row; Compare best variants against drop_detection_v1 and against verdicts; one variant per template re-run with 20 null draws | researcher |

## How it gets answered

1. For each detector, pick the variant that best matches the human row on M2_aug (hits on accepted spans per false
   alarm per hour).
2. Show how much the detectors agree across all datasets (Compare's union / only-A / only-B).
3. Report each chosen variant against its 20-draw null.

## Open decisions

- **Which single figure picks the "best" variant:** a hit rate against accepted human spans; a precision at a fixed
  alarm rate; or the agreement with the other detectors (no ground truth needed, but it rewards the herd).
- **Whether windowed runs (P3) become the default for drop detection,** or stay a choice beside the whole-span run.

## Log

- 2026-10-17 · set up · 27 variant templates created (ids 31–57); null floor 20 → 1; the four infrastructure prompts
  (P1–P4) and W4-A written; measurements recorded.
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
