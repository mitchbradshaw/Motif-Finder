# The 24 Nov drop pool: auto-detect over every dataset

Built 24–25 Nov 2026, at the researcher's request (24 Nov): run the auto-detect over all the datasets and channels,
filter with queue 57's prioritisation, confidence scoring and thresholds, update the filter from the candidates marked
not interesting or unsure, drops only, at least 100,000 new candidates that nobody has seen or judged (up to 1M), and
feed them into the NeurIPS drop plots to see what a much larger pool shows. Not for human review.

## In plain words

Think of the auto-detect as a sieve. In queue 57 you shook about 200 candidates out of it and liked almost all of
them. I put every recording we have through the same sieve, with the same mesh. Before doing that, I checked the mesh
against everything you have ever marked "not interesting" or "unsure". One change came out of that check: slow
declines are thrown out, because you accepted none of the ones you judged at the core's level.

**What came out:**

* **131,669 drops** that pass queue 57's own thresholds. Nobody has judged them or been shown them in any queue. This
  is the **core**, and it is what the plots draw.
* **99,853 more** that only just miss those thresholds: confidence 0.5–0.6, or clarity 10–15. This is the
  **extended** tier, kept apart.

**How many are real?** The honest answer is about 7 in 10. Your past verdicts on drops passing the core's thresholds
were 86% "interesting". But the queues showed you the clearest drops first, so the drops left over are fainter on
average than the ones you judged.

* A model of your 4,794 past verdicts on drops like these puts the core at **about 70%**. In every band of clarity,
  depth, confidence and the new "fast rises" measure, its prediction matches your verdicts to within 4 points. The
  same model puts the extended tier at **about 49%**, a coin toss.
* So read the plots as mostly real drops with some noise.
* There is also a cleaner subset to check any pattern against: the 46,558 core drops the model puts at 0.8 or more,
  drawn separately.

**One surprise from the bigger pool.** On Cordyceps and Enoki, and on split gill, most "drops" are not drops. They are
down-swings of a steady oscillation, a wave that rises as fast as it falls every 10–20 s (`sheets/Cordyceps.png` in the
plots). Every swing passes the rules, so those three datasets give thousands of candidates. I measured it for every
drop, as `fast_rises`. Your verdicts say such drops are accepted less often, but still more than half the time, so it
is not a rule. Instead it is part of the acceptance model, which puts those datasets at about half.

**Why not 1M?** The detector found 830,648 drops in all 144 channels, so even with no filter there would be fewer than
a million. Queue 57's thresholds keep 131,669 of them. Loosening the thresholds is what the extended tier does, and
about half of what it adds would be noise.

**Balance.** M1 (species unknown) is the biggest single source, with 27% of the core. M1 and MJu26a together hold 43%.
Six datasets have no verdicts at all, so how good their drops are has never been checked: M1, L_R_Aug_26_PD,
Cordyceps, Enoki, F2B and the Dwij loggers. Their core drops are 54% of the core.

## What was run

The v4 auto-detect (`Working/autodetect/`; see `docs/autodetect/20261123_v4/`), with the same line-up as queue 57:

* **Detectors:** `drop_detection_v1`, `drop_detection_v5`, `wavelet_encoded`, `BEADs_invert_detect_v1`, the two 6-hour
  window runs (`drop_detection_v1__w6h`, `drop_detection_v5__w6h`) and `beads_sigma`.
* **Seeds:** 64 seed families (family line 0.95).
* **Finder:** the researcher's event rule as a finder.
* **Scoring:** R4 MiniRocket scores every box, and the v4 blend gives the confidence.

Three changes for the size of the job. The pool's numbers depend on them:

* **Drops only.** Only the normal pass was run. The inverted pass, which finds sharp rises, was not, because the
  researcher said to ignore rises. 26,235 sharp rises met on the way are in `raw/` but not used.
* **No R4 window scan.** It is the costliest step. What it adds on its own is vouched for by R4 alone, which the
  queue's rules leave out anyway ("R4 alone").
* **At most 2 Hz.** Channels stored at 10 Hz (M1, L_R_Aug_26_PD, F2B) were searched as block means of five samples.
  Long channels were searched in stretches that overlap by 2 hours. A candidate belongs to the stretch it is central
  in, so none is counted twice.

**What it covered:** 144 physical channels in 17 datasets, 54,551 channel-hours, each physical channel once.

**What was left out, and why** (copies of data that is searched anyway, and two short files):

* `MJu26a.mat`, `MJu26a_fs10.mat`, `L_LM_Jul_26_J_raw(_fs2).mat` and `Mushroom_260720_0509_4hrs_CH14_fs1.mat`: copies of
  MJu26a_fs2.
* `SH.mat` and `SO.mat`: 10 Hz copies of the 2 Hz files, where the verdicts are.
* `M2_aug_concat_fs2.mat`: a copy whose joins do not line up.
* `M100.mat` and `M101_t.mat`: M1 detrended, and M1 detrended and shifted (r 0.99–1.00, `checks/copies_check.out.txt`).
* `Fig2A_dt0p1.csv`: a 20-minute figure trace.
* One 16-minute Dwij file.

**How long it took:** 17.2 worker hours on three workers, 6.3 h of wall clock (24 Nov 18:04 to 25 Nov 00:21).

* The slowest channels were MJu26a's: up to 40 minutes each for 636 hours of recording.
* L_R_Aug_26_PD was the slowest per hour. Its box-fitting step took about 9 minutes per stretch, because it has so
  many candidates.

**The check before the run** (`checks/compare_m4.out.txt`): on M4 CH1_A1 the drops-only pass finds 100% of v4's drops,
and v4's verdicts there are reproduced (44 of 47 accepted, as in v4).

## The rules

**Queue 57's rules, imported from `scripts/autodetect/build_review_queue.py` rather than copied.** A drop is kept when
all of these hold:

* confidence ≥ 0.6;
* a detector, a seed or a rule vouched for it (not R4 alone);
* it is not the recovery of the event just before it;
* its box is no longer than the channel allows;
* its box does not run into a bigger event the other way;
* its window is clean: no gap, no flat dropout, no span judged an artifact, no unexplained jump;
* it is at least 15× the noise of its own window ("clarity");
* where boxes overlap, the better one is kept;
* M4-like runs rank 0.1 higher.

**Unjudged:** no judged event span, on any copy of the channel, matches it. **Unseen:** no item of any review queue
matches it, whether the queue is open, closed or archived, queue 57 included. Both are checked against a snapshot of
the database taken 24 Nov at 18:00 (`reference_spans.parquet`: 36,563 spans).

**Updated from the verdicts:**

* **Rises are out.** Four of queue 57's nine not accepted were rises, and the researcher said to ignore rises.
* **Slow declines are out**: a drop whose fall never steps further in a second than the channel's own step noise
  (sharpness ≤ 1). Queue 57's #184 was one, and on the first 38 channels every such drop judged before was rejected
  or unsure. The re-check on all 144 channels is below. This rule removes 37,640 drops, 97% of them on Cordyceps and
  Enoki.

**Tested and not made rules** (`checks/core_verdicts.out.txt`; `calibration.csv` has every band). Each was checked
against the 4,556 judged drops that pass the core's thresholds:

* **Drops only the event-rule finder vouched for:** 77% accepted, against 87% for the rest. That is lower, but most of
  them are real, so they stay, flagged `finder_only` (30% of the core).
* **Clarity 15–20**, the weakest band: 56% accepted (n 59). Cutting it would remove 26.5% of the core, taking it below
  100,000, and raise the likely-accepted share only from 70% to 73%. Clarity ≥ 30 would keep 65,736 at 78%.
* **Depth ≤ 0.25 mV:** 55% (n 30). Too few judged to set a rule; the acceptance model accounts for it instead.
* **A dip small against the slow wander around it** (`prominence`): the lowest band was 88% accepted.
* **The slow lead-in of a deeper drop** (`shoulder`): 83%.
* **Down and back within two samples** (`glitch`): none of the judged drops passing the core's thresholds was one, so
  there is nothing to test it on. 31 core drops are, flagged.
* **A drop in a stretch that goes up and down all the time** (`fast_rises`, 25 Nov, `scripts/autodetect/pool_rhythm.py`):
  the number of times, within ±150 s, the trace climbs back by half the drop's depth as fast as the drop fell.
  * Judged drops with 0–1 such climbs were accepted 88–93%; with 3, 71%; with 6 or more, about 60%.
  * That is lower but still more than half, so it is not a rule. It is a measure of the acceptance model instead
    (below).
  * It catches the oscillation swings of Cordyceps and Enoki (median 7–9 in their core) and tiny blips on a slope or
    on noise elsewhere. A train of sharp drops with slow recoveries scores 0, as it should.
* **The slow-decline rule, re-checked on all 144 channels.**
  * Seven judged drops are slow declines. The 5 at the core's confidence and clarity were all rejected or unsure,
    though they come from a single 20-minute stretch of M4. The 2 accepted are both on split gill, at the extended
    tier's level.
  * So the rule stands for the core. But it is backed by little, and it removes 37,640 drops, 97% of them on
    Cordyceps and Enoki: 23,104 of them would otherwise be core.
  * They are very clear (median clarity 316). They are kept in `flags/`, and `MIN_SHARPNESS = 0` plus `choose` would
    bring them back.

**Tiers.** The core is every drop passing all the rules above. The extended tier passes the same rules but only at
confidence ≥ 0.5 and clarity ≥ 10: it is "go for gold", flagged apart. In `pool.parquet`, `rank` puts the core first,
by priority (confidence, plus 0.1 when M4-like), then confidence, then sharpness.

## The pool

**231,522 drops: 131,669 core, 99,853 extended**, on 142 of the 144 channels. Two Dwij channels have none.

| dataset | species | channels | drops found | core | extended | share of core | likely accepted (core) |
|---|---|---|---|---|---|---|---|
| M1 | unknown | 13 | 176,961 | 35,212 | 28,358 | 26.7% | 70% |
| MJu26a | lion's mane | 16 | 215,797 | 21,956 | 27,636 | 16.7% | 58% |
| M2_aug | oyster | 16 | 47,173 | 20,678 | 2,111 | 15.7% | 82% |
| L_R_Aug_26_PD | unknown | 13 | 119,060 | 18,303 | 20,202 | 13.9% | 74% |
| Cordyceps | Cordyceps | 7 | 138,560 | 11,115 | 12,024 | 8.4% | 52% |
| Enoki | enoki | 7 | 75,919 | 5,022 | 6,435 | 3.8% | 53% |
| CO | chocolate oyster | 4 | 7,791 | 4,230 | 626 | 3.2% | 82% |
| LM | lion's mane | 4 | 6,639 | 4,114 | 271 | 3.1% | 83% |
| M2_concat | oyster | 16 | 9,747 | 3,896 | 570 | 3.0% | 71% |
| M4 | oyster | 16 | 17,944 | 2,272 | 585 | 1.7% | 78% |
| SH | Asian shiitake | 4 | 6,849 | 2,058 | 454 | 1.6% | 74% |
| F2B | unknown | 5 | 2,968 | 1,580 | 238 | 1.2% | 82% |
| SO | snow oyster | 4 | 2,545 | 1,053 | 226 | 0.8% | 79% |
| S_commune | split gill | 7 | 2,604 | 150 | 109 | 0.1% | 46% |
| Dwij_B, C, D | unknown | 12 | 91 | 30 | 8 | 0.0% | 62–74% |

"Likely accepted" is the acceptance model's average over that dataset's core drops (see below).

**Why the rest were left out.** Each drop is counted under the first rule it fails (`reasons.csv`):

| reason | drops |
|---|---|
| below 0.6 confidence | 422,932 |
| not clear against the noise around it | 102,895 |
| a slow decline (new, from the verdicts) | 37,640 |
| R4 alone | 12,664 |
| already in a review queue | 9,016 |
| already judged | 5,338 |
| box longer than the channel's cap | 3,848 |
| the recovery of the event just before it | 3,746 |
| its box overlaps a better candidate's | 781 |
| runs into a bigger event the other way, a judged artifact or a jump in its window | 266 |

**Why some datasets give far more drops than others.** Core drops per 100 channel-hours run from 28 on M4 to 1,316 on
L_R_Aug_26_PD, almost fifty-fold:

* **Fast, small drops dominate M1, L_R_Aug_26_PD, Cordyceps and Enoki.** Their median core drop falls in 5.5–10 s
  and is 13–18 s wide. M2_aug, M2_concat, M4, SH and SO are slower: their median drop falls in 18–52 s and is 43–113 s wide
  (`summary.md`, the shapes table). CO and LM sit between.
* **The sampling rate is only part of it.** M2_aug, M2_concat and M4 were recorded at 1 Hz, where a drop of a few
  seconds cannot be resolved. But Cordyceps and Enoki are 1 Hz too and still give fast drops, and SH and SO are
  searched at 2 Hz and give slow ones. So the difference is mostly in the recordings themselves.
* **The noise floor lets shallow drops through.** A drop shallower than the dataset's noise floor is gated out.
  MJu26a's floor is set at 0.03 mV in Settings › Datasets, against 0.1–0.3 mV elsewhere. That is why its median core
  drop is only 0.33 mV deep, and why the model puts it at only 58%.

## How good the drops are likely to be

**Your verdicts on drops like the pool's** (`calibration.csv`): the run's candidates that land on a span you judged,
4,794 drops on nine datasets.

| dataset | judged drops |
|---|---|
| M2_aug | 2,319 |
| MJu26a | 1,204 |
| LM | 334 |
| CO | 270 |
| M2_concat | 264 |
| M4 | 216 |
| SO | 93 |
| SH | 86 |
| S_commune | 8 |

* Of the 4,556 that pass the core's thresholds, 86% were accepted.
* Of the 238 that pass only the looser ones, 50% were accepted.

**These verdicts flatter the pool.** The queues put the clearest, most confident drops first, so what was judged is far
clearer than what is left. Clarity 15–20 is a quarter of the core but 1% of the judged drops.

**The re-weighted estimate** (`summary.md`, `pool_summary.acceptance_model`). A model of the verdict, accepted against
rejected or unsure, was fitted to the 4,794 judged drops using the measures the pool keeps for every drop: clarity,
confidence, R4's probability, depth, sharpness, the number of sources, whether only the finder vouched, and
`fast_rises`. The model is shallow gradient-boosted trees. It was then averaged over the pool's own drops.

* **The result:** core 70%, extended 49%. 46,558 core drops (35%) are predicted at 0.8 or more.
* **How well it fits:** cross-validated AUC 0.79. In every band of fast rises, clarity, depth and confidence it
  predicts the accepted share to within 4 points.
* **Why this model:** a straight logistic model over-predicted faint and shallow drops by up to 28 points, and a spline
  model by up to 10 (`checks/acceptance_models.out.txt`). Adding `fast_rises` raised the AUC from 0.787 and corrected
  an over-prediction of up to 9 points where the trace climbs back fast.
* **What it assumes:** a drop is judged by how it looks, whatever dataset it is on. For the six datasets with no
  verdicts, that is an extrapolation.
* Each drop's prediction is in `DATA/derived/autodetect/pool_20261124/p_accept.parquet`. Use it to re-weight or to
  choose a cleaner subset, not as a verdict.

## What the plots show

The plots are in `docs/library_analysis/20261124_pool_plots/`. Open `index.html` there. They are the NeurIPS session's
23 Nov drop plots (`scripts/library_analysis/drop_plots_20261123.py`, imported unchanged), drawn over the core, every
drop alike. Beside them, `docs/library_analysis/20261124_pool_plots_p80/` draws the same figures over the cleaner
subset: the 46,558 core drops the model puts at 0.8 or more.

Read the plots folder's README first: it has seven warnings for reading the figures. What came out:

1. **Every species' drop has the same form.**
   * In the cleaner set, each species' typical drop is a fall, then a slow, partial climb back: a third to a half of
     the way within six fall-times (`species_typical_shape.png`). F2B alone climbs back almost fully.
   * In the full core, Cordyceps, enoki and split gill instead rise into the top and rebound after the bottom. That is
     their oscillation, and it vanishes in the cleaner set, which keeps only 5–7% of their drops.
2. **Two speeds, by recording.**
   * *Fast group:* M1, L_R_Aug_26_PD, CO, F2B, MJu26a, Cordyceps, enoki and split gill. Their median drop falls in
     5.5–10.5 s and is 13–24 s wide.
   * *Slow group:* M2_aug, M2_concat, M4, Asian shiitake and snow oyster. Their median drop falls in 18–52 s and is
     43–113 s wide.
   * LM falls fast (9 s) but recovers slowly (44 s wide).
   * Both groups contain oysters, so speed is not a species trait here. It may be the recording setup.
3. **A drop that falls slowly comes back slowly, on every species.** In `species_fingerprints.png`, fall time against
   recovery is a single diagonal band for all of them, in the full core and in the cleaner set. "Fast down, slow up"
   is a matter of degree that the species share.
4. **No typical size.** Each species' amplitudes spread over one to three decades with no hump
   (`extra/size_distributions.png`).
   * The smallest drops are on split gill (median 0.16 mV), Cordyceps (0.30) and MJu26a (0.33).
   * The biggest are on M2_concat (3.5 mV) and LM (2.6).
   * MJu26a's small drops come with its 0.03 mV noise floor.
5. **Where the drops are** (`extra/drop_raster.png`):
   * L_R_Aug_26_PD and M1 have drops on every channel for the whole recording.
   * MJu26a's CH3 and CH5 carry dense runs of small drops.
   * M4's channels drop together at a few moments (about 190 h and 320 h), the kind of shared moment the B4 census
     found elsewhere.
   * Gaps are stretches the rules emptied: already judged or queued, noisy, or quiet.
6. **Cliff-like falls belong to the 10 Hz recordings**, in both sets, and about two-thirds of that is the rate (the
   plots README, warning 3).
7. **M1's second kind of drop:** 5% of its core drops are slides over 10 minutes, about 33 mV deep: its drift, read as
   drops. They are gone from the cleaner set, because the model rates them low.

## Files

**In git, in this folder:**

* This README.
* `summary.md` and `summary.json`: every number above, from `scripts/autodetect/pool_summary.py`.
* `plan.json`: the choice's settings and counts.
* `reasons.csv`, `by_dataset.csv` and `by_channel.csv`.
* `runs.csv`: one row per channel: its rate, stretches, time, memory and counts. It is a copy of the provenance
  record's.
* `calibration.csv`: the judged drops by band.
* `sequences_m4_likeness.csv`.
* `pool_compact.parquet`: the whole pool, 231,522 drops with the columns needed to find, rank and redraw each one.
  It is rounded, 16 MB. It is the git copy of the pool in case the data folder is lost.
* `checks/`: the side checks and what they printed.

**The data**, gitignored and the only copy, about 520 MB: `DATA/derived/autodetect/pool_20261124/`.

* Its `README.md` is the data dictionary: every file and column, the index frames and the commands to redo each stage.
* It holds every candidate unfiltered (`raw/`), every rule and measure (`flags/`), the reference-span snapshot, the full
  pool, `rhythm.parquet` (`fast_rises`, `rhythm_r`), `p_accept.parquet`, the NeurIPS event tables (`events.csv`,
  `events_p80.csv`), the drop waveforms and `provenance/`.
* `provenance/` records the git commit, every imported code file with its fingerprint, copies of the files that were
  not committed, the fingerprints of the inputs (seed bank, R4 model, the 144 channel files) and the package versions.
* **Never `git clean -x` it.**

**The code**, all in `scripts/autodetect/`:

* `run_pool.py`: detection.
* `build_pool.py`: the `flags` and `choose` stages.
* `pool_rhythm.py`: `fast_rises` and `rhythm_r` for every pool drop and judged drop.
* `pool_summary.py`: the numbers and the acceptance model.
* `pool_plots.py`: the plots.
* `pool_provenance.py`: the provenance record.
* `pool_checks/`: the side checks.

## Doing it again

The commands are in the data folder's README. The stages run in this order: `run_pool.py detect`,
`build_pool.py flags`, `build_pool.py choose`, `pool_rhythm.py`, `pool_summary.py`, `pool_plots.py` (and with
`POOL_MIN_P_ACCEPT=0.8` for the cleaner set), then `pool_provenance.py`. To re-choose with other thresholds (minutes,
no re-detection), change `B.MIN_CONFIDENCE`, `B.CLARITY_MIN`, `MEASURE_FROM` or `MIN_SHARPNESS` in `build_pool.py`,
run `choose` and every stage after it. To filter against the database as it is now rather than as it was at 24 Nov
18:00, move `reference_spans.parquet` aside first and run `flags` again.
