# Research prompt 01: neuron models on long drop trains, with phase-response curves

**Follows:** round-B question B3, `docs/rq_roundA_2/findings/b3-restitution-tracking-2026-10-28.md`.

**Written:** 2026-11-03, the experiments-freeze day. Whether its results go into Chapter 10 is the researcher's call.
Until they say so, treat this as post-freeze work.

## Why, in plain words

Fungal recordings often show **trains of drops**: the voltage falls sharply, recovers, and falls again, tens or
hundreds of times. Neuroscience has small models of things that fire repeatedly:
- **FitzHugh–Nagumo (FHN)**, a two-variable "neuron";
- **Izhikevich**;
- **Morris–Lecar** and **van der Pol** oscillators;
- **Hindmarsh–Rose**, a bursting model.

Earlier work fitted the first two to a few short trains. The verdict was: **not beyond noise.**
- **On mean cycles** (`fhn-fit-2026-10-26.md`), FHN fits oyster cycles no better than it fits averaged quiet
  stretches. A plain fall-plus-recovery shape does better.
- **On individual cycles** (B3), no model predicts a held-out cycle better than the average of its neighbours.

Those runs used 16–42 cycles per sequence, plus three chains of about 50–110 cycles. **This prompt asks the same
question on the longest trains we have, with more model types.** It adds **phase-response curves (PRCs)**, so that any
difference from the earlier runs comes from the trains and the models, not from a changed method.

**What a PRC is, and what it can and cannot show here.** A PRC answers one question: if the rhythm is nudged at
this moment of its cycle, does the next event come early, late, or on time? Think of pushing a child on a swing. A
push just after the top speeds the next swing; a push at the wrong moment slows it; at some moments it barely matters.
For a fungal drop train a PRC would say three things:

1. **Is the drop train a self-sustaining rhythm or a mousetrap?**
   - **Type II** (an oscillator): nudges can either advance or delay the next drop.
   - **Type I** (an excitable system near threshold): a nudge can only bring the next drop sooner.
2. **Should separate patches synchronise?** Whether two coupled rhythms lock together follows from the PRC's shape.
   This bears on B4 and B5, which found channels rising and falling together through a shared driver, not
   propagation.
3. **When would a stimulus shift the rhythm most?** Light, touch or chemicals delivered at a given point in the
   cycle would shift it by an amount the PRC predicts.

**What the PRC plots showed so far: nothing about the fungus.** They were the PRCs of the *fitted model* only.
- Nobody nudged a fungus.
- The fitted model did not beat noise on oyster cycles.
- The curve changed by a factor of ten or more depending on which hidden variable is assumed fixed during the nudge.
  That is Wilshin, Kvalheim & Revzen's (2024) central point.

So a model PRC is "what this model would do". A **measured** PRC needs timed stimulation.

Long trains allow one more, weaker thing: a **spontaneous phase–timing estimate**. Do the signal's own small wiggles
at particular phases of a cycle predict that the next drop comes early or late? That is a correlation, not a measured
PRC. Report it as such.

## What you produce

1. **Code** in `Pipelines/fhn/`, test-first:
   - new modules `van_der_pol.py`, `morris_lecar.py`, `hindmarsh_rose.py`, `empirical_prc.py`;
   - a runner `run_long.py`;
   - tests in `tests/test_fhn_<module>.py`.

   Your first commit touches only `tests/` and contains failing tests (CLAUDE.md's rule). Edit existing
   `Pipelines/fhn/` modules only where a new train needs it, and keep their old behaviour pinned by their tests.
2. **Data and figures** in `docs/thesis/data/ch10_fhn_long/`:
   - `results.json`;
   - per train, PNG + PDF of `fit_<train>`, `track_<train>`, `prc_models_<train>` (the Fig. 1 style below),
     `prc_spont_<train>` and `returnmap_<train>`.
3. **Findings:** `docs/rq_roundA_2/findings/b3-long-trains-<date>.md`, in this order:
   - plain words first, including what the PRC shows and does not show here;
   - the regression check against the earlier runs;
   - the tables;
   - every figure, with one line on what it shows;
   - what can and cannot be claimed.

**Do not edit** thesis chapters, `docs/thesis/numbers_ledger.md`, `docs/thesis/TASKS.md` or any log. The manager
integrates.

## Read first

**Code, in `Pipelines/fhn/`:**
- `data.py`: the sequence loader; cycle cutting (onset to onset, drop at `PRE_FRAC` = 0.1, chord-detrended,
  `N_POINTS` = 200, `GAP_RULE` = 0.6–1.6× the median gap); `quiet_null_means`, `phase_randomise` and
  `surrogate_null_means`.
- `b3_data.py`: `CHAINS`, `chain_events` (the `chain_cycles` template's first steps), `sequence_events` and the
  census.
- `model.py`: the FHN model, `prc_perturbation`, `prc_adjoint` and `isochron_ticks`.
- `fit.py`: FHN oscillatory and excitable, the jump + exponential kernels and the sinusoid.
- `izhikevich.py`.
- `track.py`: `blocks`, `heldout` and `drift_test`.
- `figures.py`: `fig_cycle_isochrons` (the paper's Fig. 1 style) and the Fig. 4 style.
- `run_ch10.py`: the mean-cycle fits, nulls and PRC figures.
- `run_b3.py`: per-cycle tracking.

**Findings:**
- `docs/rq_roundA_2/findings/fhn-fit-2026-10-26.md`: what was fitted, the nulls, the PRC section and its coordinate
  caveat, what can be claimed.
- `docs/rq_roundA_2/findings/b3-restitution-tracking-2026-10-28.md`: the tracking design, the nulls, the drift
  tests, and why the warm-started drift tests were miscalibrated.
- `docs/rq_roundA_2/findings/b9-cwt-durations-2026-11-03.md`: why an AAFT null is needed beside phase
  randomisation.
- `docs/rq_roundA_2/findings/b10-scales-2026-11-03.md`: the MJu26a oscillation below.

**Paper:** Wilshin, Kvalheim & Revzen (2024), *Biol. Cybern.* 118:311–330 (bib key `wilshin2024prc`).

**Thesis:** Chapter 10's B3 section, `docs/thesis/chapters/10_roundb.tex` (read only).

## Keep it comparable (do not change these)

- **Cycles:** cut exactly as before. Use `N_POINTS` 200 for mean-cycle fits and 100 for tracking (as B3), the same
  gap rule, the same chord detrend, and the drop at τ = 0.1.
- **Units:** mV through the declared units, as `data.load_mv` does (V × 1,000; mV as is).
- **Models already run:** keep their settings. These are the jump + exponential + rise kernel (k = 6), the sinusoid
  (k = 3), FHN oscillatory (k = 7, z fixed at −0.4, so only α = a + b·z is identifiable), FHN excitable (k = 8) and
  Izhikevich 2003 (k = 9).
- **Nulls:**
  - quiet windows (no event within a quarter cycle) and phase-scrambled copies cut at the real onsets, as before;
  - **add AAFT** (the value distribution kept, the timing scrambled) and report it in its own column, so that old and
    new numbers stay comparable.
- **Held-out tracking:**
  - cycle i is predicted by the mean of the fitted curves of the blocks on either side of its own block;
  - the score is that error over the neighbours'-mean error (below 1 means the model is better);
  - blocks are 3 cycles for sequences and 5 for chains and long trains.
- **PRC figures:** `fig_cycle_isochrons` as before, in recorded units (rad/mV). Show these curves:
  - w held fixed;
  - the delayed voltage held fixed at the paper's delay (0.1 model units);
  - a quarter-period delay;
  - a linear change of hidden coordinate.
- **Regression check first.** Re-run seq 3, 7 and 22 and the three W3 chains. The earlier numbers must reproduce
  within fit noise:
  - FHN R² 0.873 / 0.971 / 0.997 (oscillatory) and 0.931 / 0.981 / 0.996 (excitable);
  - the B3 held-out ratios, e.g. rec 6: kernel 1.08, FHN excitable 1.34, FHN oscillatory 1.29, Izhikevich 1.46.

  Report any difference before doing anything new.

## The trains (where to look)

**Stored sequences.** These are the `sequences` table's rows; their events are the drop-motif store's rows, read by
`b3_data.sequence_events`. Recording ids are `recordings.id`; "stored ch" is the 0-based channel column.

| seq | key | recording | span | events | note |
|---|---|---|---|---|---|
| **20** | `reishi_id903_ch3_606s` | 469, Fig2A (stored ch 3), 10 Hz, V | 0.17–0.25 h | **114** | the longest stored train; Fig2A is inactive (deactivated 26 Oct) but its arrays are on disk |
| **122** | `human_r1_ch0_1749416s` | 1, M2_aug CH1 | 485.95–488.52 h | **100** | origin `annotation`: a train you marked by hand |
| **1** | `oyster_id10_ch3_1362824s` | 4, M2_aug CH4 | 378.55–379.70 h | **67** | drop-motif id10's train |
| 21 | `reishi_id901_ch1_724s` | 467, Fig2A | 0.20–0.23 h | 59 | |
| 22 | `reishi_id901_ch1_461s` | 467, Fig2A | 0.13–0.16 h | 57 | earlier run (42 cycles) |
| 2 | `oyster_id33_ch15_119520s` | 16, M2_aug CH16 | 33.20–34.60 h | 40 | |
| 3 | `oyster_id28_ch5_1394131s` | 6, M2_aug CH6 | 387.12–407.49 h | 29 | earlier run (27 cycles, 44 min) |
| 6 | `oyster_id28_ch5_1517760s` | 6, M2_aug CH6 | 420.93–434.80 h | 20 | the same chain, later |
| 7 | `oyster_id35_ch15_288397s` | 16, M2_aug CH16 | 80.10–80.80 h | 18 | earlier run (16 cycles, 130 s) |

**Long chains.** These are `b3_data.CHAINS`, cut by the `chain_cycles` template's first steps:
600 s detrend, `noise_threshold` 4σ, minimum 30 s, merge 60 s, train gap 3 h.

| chain | recording | span | events (W3) | cycles (B3) |
|---|---|---|---|---|
| `rec6_370_470h` | 6, M2_aug CH6 | 370–470 h (train between about 383 and 445 h; holds seq 3) | 115 | 103 |
| `rec3_490_540h` | 3, M2_aug CH3 | 490–540 h | 116 | 47 (77 under W3's own rule) |
| `rec542_370_490h` | 542, L_LM CH3, 10 Hz, mV | 370–490 h | 163 | 110 |

**New long trains.** Find each one's extent by the same chain rule before looking at any fit. Write the rule and the
resulting spans into the findings first.

- **MJu26a's steady oscillation.** Recording 692 (MJu26a_fs2 CH1, 2 Hz, V, lion's mane). B10 found a steady ~20-min
  oscillation at 314–322 h that AAFT keeps. Extend it to its contiguous extent with the chain rule. At a 20-min period,
  every 10 h holds about 30 cycles. It is the best candidate for an oscillator model and for the spontaneous PRC
  estimate.
  - L_LM is a copy of five MJu26a channels (rec 542 is MJu26a CH14 × 1000 plus an offset). Do not count a span twice
    across the two.
- **Chain extensions.** Where the chain rule finds a W3 chain continuing past its span, take the longer train. The rule
  decides, not the eye.

**Never read:**
- `Schizophyllum commune.txt`: its blind exam, queue 37, is open;
- `M4_aug_concat_fs1.mat`: held out;
- L_R and F2B.

## Models

Every new model has the FHN oscillator's free gain, offset, time scale and phase, and its own module and tests. Report
any parameter on a bound, and only identifiable combinations.

| model | variables | extra free parameters | why |
|---|---|---|---|
| van der Pol | 2 | μ (relaxation) | the simplest relaxation oscillator; a sanity bar between the sinusoid and FHN |
| Morris–Lecar | 2 | applied current, φ (and a class switch) | it has standard Type I (saddle-node on invariant circle) and Type II (Hopf) parameter sets, so where the fit lands decides the PRC type |
| Hindmarsh–Rose | 3 | r (slow time scale), applied current | bursting; fit it only where a train has bursts (check seq 122 and seq 20), and say where it was skipped and why |

Fit the earlier five models as well: the kernel, the sinusoid, FHN oscillatory and excitable, and Izhikevich.
`scipy.integrate.solve_ivp` is available. Install nothing.

## Analyses

**A. Mean-cycle fits per train**, as in `run_ch10.py`.
- Report R² and ΔAIC (a ranking, not a test).
- Nulls: quiet, phase-scrambled and AAFT, 10 draws each on trains under 60 cycles and 5 on longer ones.
- Report the height statistic (real against null mean-cycle height), which was the one that separated real from noise.

**B. Per-cycle held-out tracking**, as in `run_b3.py`.
- Report the ratio to the neighbours' mean, real against 2 draws of each null.
- **Drift tests.** Use the kernel's recovery fraction and FHN's α, and the new models' identifiable parameters. Use
  **cold starts** or calibrate the test on the fake trains: warm starts made B3's FHN-oscillatory and Izhikevich drift
  tests invalid.

**C. Phase-response curves.**
1. **Model PRCs.** For every fit that oscillates (FHN oscillatory, van der Pol, Morris–Lecar, Izhikevich where
   periodic, and Hindmarsh–Rose per burst):
   - compute the PRC by perturbation and by the adjoint, and report their agreement;
   - show the coordinate spread (w fixed against the delayed voltage fixed);
   - convert to rad/mV;
   - classify each as Type I (one-signed) or Type II (two-signed), per model and train.
2. **The spontaneous phase–timing estimate** (a PRC proxy), on trains with 60 or more cycles.
   - **Timing:** ΔTᵢ is cycle i's length minus a running median over ±5 cycles, to remove drift.
   - **Wiggles:** rᵢ(φ) is cycle i's shape minus the same running mean cycle, in 20 phase bins.
   - **Estimate:** fit ΔTᵢ ≈ Σₖ Z(φₖ)·rᵢ(φₖ) by ridge regression, with λ chosen by leave-one-out. Bootstrap over
     cycles for bands.
   - **Nulls:** ΔT shuffled across cycles (500 draws), and the same estimator run on quiet, phase-scrambled and AAFT
     fake trains cut at the real onsets.
   - **Reporting:** give Z(φ) only where it clears both nulls, and plot it beside the model PRCs on its own axis. The
     units differ: a model PRC is per mV of kick, the proxy per mV of spontaneous deviation.
   - **The return map:** add Tᵢ₊₁ against Tᵢ, the simplest dynamical signature, with its shuffle null.
   - **State in the findings:** without stimulation this is a correlation. Drift, noise and the detector's onset
     placement can each produce it. Only a timed stimulus measures a PRC, and even then the hidden coordinate matters.

## Rules

- **Run in the main checkout.** `Pipelines/fhn/data.py` reads `DATA/` by a repo-relative path. A worktree has no
  `DATA/`, and a junction to the real one is forbidden.
- **Read-only.** Open the database read-only (`data._ro()`, `mode=ro`) and memory-map the channels. Write nothing to
  the database, the step cache or `DATA/`.
- **Commits:**
  - commit only your own paths, with explicit pathspecs;
  - never `git add -A` or `git stash`; do not push;
  - messages start with `b3-long:` and end with the session's attribution line.
- **Python:** `"/c/ProgramData/anaconda3/python.exe"`, with `PYTHONIOENCODING=utf-8`. In the Bash tool, heredocs
  collapse double backslashes, so write scripts with the Write tool.
- **Budget:** about 4 hours of wall time with 2 worker processes. Earlier, 96 fit tasks took 64 CPU-minutes, and an
  FHN-oscillator block fit takes 16–30 s.
  - Order: the regression check, then the new long trains, then the new models, then the PRCs.
  - If you run over, cut null draws first and then Hindmarsh–Rose, and say what was cut.
- **Stop and report** if the regression check does not reproduce, if a new train's extent depends on judgement rather
  than the rule, or if a model needs a package that is not installed.

## Report back

- The headline per train and model, in plain words.
- The regression check.
- Each PRC's type, and whether the spontaneous estimate cleared its nulls anywhere.
- Every file created.
- What was cut.
- Run times.
