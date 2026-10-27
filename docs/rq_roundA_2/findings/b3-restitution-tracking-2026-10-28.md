# B3: does a drop's recovery depend on the gap before it, and does a neuron model track the cycles? 2026-10-28

Made by `Pipelines/fhn/run_b3.py`. It is read-only: the database is opened `mode=ro` and the channels are
memory-mapped. M4_aug (recordings 49–64) was never read, no Review queue was opened and no verdict was written.

Outputs are in `docs/thesis/data/ch10_fhn/`:
- `b3_restitution.json` and `b3_track.json`;
- the figures `b3_restitution_rho`, `b3_restitution_scatter`, `b3_track_ratio` and `b3_track_params`, each as PNG
  and PDF.

This is round-B question B3, thesis Chapter 10, "Modelling common motifs". It follows
`fhn-fit-2026-10-26.md`.

## In plain words

**The restitution question.** Think of a toilet cistern. After a flush, it refills. Flush again before it is full,
and the next flush is weaker or behaves differently. The heart does the same: a beat that comes soon after the last
one is shorter. Cardiologists call this "restitution".

We asked whether fungal drops behave like that. Within a train of drops, is a drop's recovery (how long it takes to
climb halfway back) longer or shorter when the wait before it was longer?

**Answer: not within the drop trains. There is a weak "yes" across the hours-long gaps of the detector census.**
- **Trains.** Raw correlations do lean positive: a longer wait goes with a longer recovery. But the lean disappears
  once we allow for two boring explanations:
  - deeper drops take longer to recover;
  - the recording drifts slowly, so neighbouring gaps and recoveries move together.
- **The stronger control.** Recovery tracks the gap *after* a drop even more closely than the gap before it. A
  recovery cannot be caused by a wait that has not happened yet. So this is a property of how recovery is measured
  (its search stops at the next drop), not restitution.
- **The census.** Here drops are hours apart, and the measurement cut-off almost never bites. On M2_aug and
  M2_concat, a longer quiet spell before a drop does go with a longer recovery. The effect is modest (pair-weighted
  ρ ≈ 0.2–0.3) and survives depth, slow drift and the gap after. It weakens once the drop's fall time is allowed for.

**The model question.** A model of the drop cycle is useful only if it forecasts a cycle it has not seen better than a
plain template does. The template here is the average of the neighbouring cycles. That is the bar each model must
clear.

**Answer: none of the four models clears it on real cycles.** Every model forecasts the fake cycles (cut from quiet
stretches, or from a scrambled copy of the recording) slightly *better* than the template, because it smooths their
noise. On real cycles every model is equal to the template or worse. The best is the simple fall-plus-recovery
kernel, and even it only ties.
- Real cycles carry sharp, recurring detail that the models cannot draw and the template keeps.
- So the neuron-style models describe the cycles less well than the cycles' own neighbours do.
- FHN and Izhikevich do not describe fungal drop cycles beyond what noise gives.

**Do the fitted parameters drift along a chain?**
- **The trustworthy fits.** For the fits whose drift test passed its own check on fake cycles (the kernel and FHN
  excitable), a few parameters drift. The clearest is the kernel's recovery time, which lengthens along two of the
  three long chains.
- **The untrustworthy fits.** The FHN oscillatory and Izhikevich parameter tracks cannot be trusted. Their fits were
  warm-started from the previous block to save time, and that alone makes even fake cycles look like they drift.

## B. The restitution test

### Method

**What is measured.**
- **Recovery** is Event shape's `recovery_time_s`: from the extremum to the first return to half the depth. It is
  searched up to the next event and for at most 10 event widths.
- **Gaps** are `intervals.inter_event_intervals` of the onsets.
- Both are imported from `Working/interrogation/`; `intervals.py` is untouched.

**Where the onsets come from.**
- **Sequences.** The 117 machine sequences of the `sequences` table, with the retired Mushroom_260720 run left out.
  Their events are the drop-motif store's rows, read through `Pipelines/fhn/data.py`. Event shape is given the store's
  onset and trough as anchors, as the Library does, and measures on the raw channel in mV.
- **Chains.** The `chain_cycles` template's own first steps, re-run on each chain's span:
  - a 600 s rolling-mean detrend;
  - `detection.noise_threshold` (4 σ below, minimum 30 s, merge 60 s), called through the block's own `_run`;
  - Event shape with the anatomy search and no anchors.

  The detector counts match W3 exactly: 115 (rec 6), 116 (rec 3) and 163 (rec 542). Pairs across a gap longer than
  3 h are dropped; that is Trains' end gap.
- **Census.** The latest `drop_detection_v1` run with the template's exact parameters, per channel. The event counts
  are 688 (M2_aug), 309 of 310 (M2_concat), 125 (LM_fs2) and 34 of 37 (CO_fs2).
  - The stored start is a padded window. The onset was found inside it by Event shape's anatomy search, on the
    detector's own detrended trace (`rolling_mean_nearest` 4916.67 s).
  - The median onset lies 504–591 s after the window start. That confirms the padding noted in B4.

**The statistic.**
- **Per train.** Spearman ρ of (gap before event i, recovery of event i), with a p from 1,000 seeded permutations of
  the gaps within the train. A train needs at least 5 pairs.
- **Partial ρ.** The same ρ controlling, one at a time and in pairs, for:
  - depth;
  - fall width (onset → extremum);
  - event index (slow drift);
  - **the gap after**.
- **The gap-after control.** The same ρ against the *next* gap.

**Combining trains.** The primary test is a **signed Stouffer** z, from the one-sided "ρ > 0" permutation p and
weighted by √pairs. It keeps both the direction and the strength, and it lets long trains count for more. Two others
are reported beside it:
- the **sign count** of ρ < 0 against Binomial(n, ½), which is robust but blind to strength;
- **Fisher** on the two-sided p, which is direction-blind. It is significant when half the trains go one way and half
  the other, so it is not primary.

A positive ρ is restitution in the cardiac sense: a shorter gap goes with a shorter recovery.

### Results

Z is the Stouffer z. In the sign column, the number of trains with ρ < 0 is out of all trains scored, with its
two-sided binomial p. The ρ̄ column is the pair-weighted mean ρ.

| set | trains (pairs) | raw: Z (p) · sign ρ<0 (p) · ρ̄ | given depth | given index | given gap after | control: vs gap AFTER |
|---|---|---|---|---|---|---|
| sequences, all | 74 (987) | +2.94 (0.003) · 35/74 (0.73) · +0.11 | +0.60 (0.55) | +0.70 (0.49) | +1.18 (0.24) | **+9.88 (5e-23)**, ρ̄ +0.36 |
| — oyster | 15 | +3.18 (0.0015) · 5/15 (0.30) · +0.24 | +0.97 (0.33) | −0.15 (0.88) | +0.13 (0.90) | +3.38 (7e-4) |
| — reishi | 59 | +1.55 (0.12) · 30/59 (1.0) · +0.07 | +0.13 (0.90) | +0.89 (0.37) | +1.30 (0.19) | +9.46 (3e-21) |
| chains | 3 (377) | +2.93 (0.003) · 1/3 · +0.17 | +2.65 (0.008) | +2.50 (0.012) | +0.53 (0.59) | +2.99 (0.003), ρ̄ +0.27 |
| census M2_aug | 15 channels | **+5.02 (5e-7)** · 4/15 (0.12) · +0.29 | **+5.27** | **+4.59** | **+3.84 (1e-4)** | +4.37 |
| census M2_concat | 11 | **+3.08 (0.002)** · 1/11 (0.012) · +0.24 | +3.06 | +2.80 | **+2.51 (0.012)** | +3.81 |
| census LM_fs2 | 3 | +1.75 (0.08) | +2.05 | +1.49 | +0.56 | +1.88 |
| census CO_fs2 | 2 | +0.33 (0.74) | +0.58 | −0.06 | −0.64 | +2.53 |

**The census given fall width.** Controlling for fall width weakens the census result: M2_aug Z +2.46 (p 0.014),
M2_concat +1.14 (0.25).

**Per chain.**

| chain | ρ (p) | given depth | given gap after | vs gap after |
|---|---|---|---|---|
| rec 6, 370–470 h | +0.29 (0.001) | +0.11 (0.24) | +0.08 (0.40) | +0.40 (0.001) |
| rec 3, 490–540 h | −0.10 (0.27) | 0.00 (0.98) | −0.11 (0.28) | −0.12 (0.20) |
| rec 542, 370–490 h | +0.27 (0.002) | +0.29 (0.001) | +0.07 (0.35) | +0.46 (0.001) |

**Per sequence, for the three FHN sequences and the longest oyster sequence.**

| sequence | ρ (p) | given depth + index | vs gap after |
|---|---|---|---|
| seq 1 (oyster id10, 64 pairs) | +0.51 (0.001) | −0.00 | +0.62 (0.001) |
| seq 3 (id28) | −0.33 (0.10) | −0.49 (0.014) | −0.17 (0.43) |
| seq 7 | +0.27 (0.33) | | |
| seq 22 | +0.21 (0.18) | | +0.47 (0.001) |

Seq 3 is the only train with a *negative* relation that survives depth and index: the cistern direction reversed.
One train of 27 pairs is not a finding.

**Not scored.** 43 of the 117 sequences had fewer than 5 pairs with a recovery. A recovery is missing (NaN) when the
drop does not climb halfway back before the next drop starts. That happened to 339 of 1,298 reishi events and 68 of
343 oyster events.
- This censoring is itself the problem with the raw positive ρ. A long recovery is measurable only when the next
  gap is long, and consecutive gaps are alike. That is why the gap-after control is stronger than the effect itself.

**Read on the site.** The recoveries here equal the Library's own route (`library.features.measure_snippet` on the
channel samples with the store's anchors) wherever the snippet reaches the recovery. They do **not** match the values
stored in `motif_features`: only 33 of 968 sequence-member values agree within 1 %, with a median difference of 0.13 s
on reishi and 38 s on oyster. The stored values look computed from different snippet values. This needs a check
before the Library's stored recovery column is quoted anywhere.

## A. Per-cycle model tracking

### Design

The design was chosen after timing single fits. On one 3-cycle block of 100 points:
- the FHN oscillator took 16–30 s;
- FHN excitable 3–6 s;
- Izhikevich 2 s;
- the kernel 0.1 s.

**Data.**
- seq 3, 7 and 22 (27, 16 and 42 cycles), from `data.sequence_cycles`.
- The three W3 chains, with cycles cut at the Event shape onsets by `data.cycles` (gap rule 0.6–1.6× the median):
  - rec 6: 103 cycles;
  - rec 3: 47 cycles (68 left out by the gap rule; W3's own rule kept 77);
  - rec 542: 110 cycles.
- All cycles are 100 points, chord-detrended, with the drop at τ = 0.1.

**Blocks.**
- Contiguous, non-overlapping blocks: 3 cycles for the sequences and 5 for the chains. That gives 9, 5, 14, 20, 9 and
  22 blocks.
- One fit per block, to the block's mean cycle. A block's cycles share every shape parameter.
- Disjoint blocks give independent parameter estimates, which the drift test needs. A sliding window would correlate
  neighbouring estimates.

**Held-out prediction.**
- Cycle i is predicted by the mean of the fitted curves of the blocks on either side of its own block.
- The baseline is the mean of those same blocks' mean cycles.
- The score is the mean squared error over the cycle. The ratio is model error over baseline error; below 1 means
  the model is better.
- No fit ever saw the cycle it predicts (tested).

**Models.**

| model | k | settings |
|---|---|---|
| fall + recovery kernel | 6 | `fit_jump_exp`, rise=True |
| FHN excitable | 8 | 1 start, 100 evaluations |
| FHN oscillatory | 7 | warm-started from the previous block; 2 starts on the first block, 80 evaluations |
| Izhikevich (2003) | 9 | new, `Pipelines/fhn/izhikevich.py`; warm start plus 2 canonical classes, 150 evaluations |

The Izhikevich fit has the same free gain, offset, time scale and phase as the FHN oscillator.

**Nulls**, with the same pipeline and the same number of cycles:
- 2 quiet draws: windows with no event within a quarter cycle, in random order. For the chains they come from the
  same detector run over the span widened by 48 h.
- 2 phase-scrambled draws, cut at the real onsets.
- The FHN fits ran on draw 0 of each null only, to stay inside the budget.

**Cost.** 96 fit tasks took 3,841 s of fit CPU (64 min) over 2 workers, and 32 min of wall time. The restitution run
took 19 s.

### Held-out-cycle error relative to the mean of the other cycles

The table gives the pooled ratio; below 1 means the model is better. Each cell reads real / quiet (draw 0, draw 1) /
scrambled (draw 0, draw 1).

| dataset | kernel | FHN excitable | FHN oscillatory | Izhikevich |
|---|---|---|---|---|
| seq 3 | **1.14** / 0.97, 0.98 / 0.95, 1.00 | **2.06** / 0.95 / 0.93 | **1.63** / 0.98 / 0.95 | **1.79** / 0.99, 0.91 / 0.94, 0.98 |
| seq 7 | 1.03 / 1.00, 0.98 / 0.99, 0.99 | 1.03 / 1.04 / 1.03 | 1.05 / 1.01 / 0.99 | **1.33** / 1.00, 0.96 / 1.01, 0.98 |
| seq 22 | 1.00 / 0.99, 1.00 / 1.00, 1.00 | 1.04 / 0.98 / 0.99 | 0.995 / 0.99 / 0.99 | 1.06 / 0.98, 0.99 / 0.99, 1.00 |
| rec 6 chain | 1.08 / 1.00, 1.00 / 0.99, 0.99 | **1.34** / 1.00 / 0.98 | **1.29** / 1.00 / 0.99 | **1.46** / 1.00, 0.98 / 0.98, 0.98 |
| rec 3 chain | 1.00 / 1.00, 0.99 / 0.98, 0.99 | 1.00 / 1.03 / 0.96 | 1.02 / 1.01 / 0.98 | 1.01 / 1.01, 1.00 / 0.96, 0.98 |
| rec 542 chain | 1.00 / 0.97, 0.96 / 0.96, 0.96 | 1.05 / 0.96 / 0.94 | 1.55 (did not converge) / 0.95 / 0.96 | 1.17 / 0.96, 0.94 / 0.96, 0.96 |

**No model beats the baseline on real cycles.**
- The best real ratio is 0.995 (FHN oscillatory on seq 22, which is noise-sized).
- Every null draw of every model sits at 0.93–1.04.
- So the models do *better* against the template on fake cycles than on real ones. This is the same finding as on
  26 Oct, now in a test that cannot be passed by flexibility: noise is smooth, and real cycles have sharp shared
  features (the fall, a floor) that no fitted shape reproduces as well as the neighbours' average.

**The ranking on real cycles.**
- The kernel comes first everywhere: it ties on 4 datasets and loses by 3–14 % on 2.
- FHN excitable and FHN oscillatory come next; Izhikevich comes last.
- The Izhikevich block fits reach a median R² of only 0.65–0.89. Its reset waveform (a slow ramp, a sharp upstroke,
  then the reset) is not the shape of a fungal drop.

**Fits that did not converge.** The FHN oscillatory fit on rec 542 did not converge (block R² median 0.2). The warm
start locked onto a bad first fit, and one start per block could not escape it. That is reported as a result, not
tuned further.

### Parameter drift

**Method.** Each parameter's series over the real blocks is tested against 1,000 shuffles of the block order, by two
statistics:
- |Spearman ρ with block index|, which detects a trend;
- the von Neumann ratio, which detects slow wander.

**Calibration on the fake-cycle tracks** (fraction of tests with p < 0.05; the target is about 0.05):

| model | ρ test | von Neumann | verdict |
|---|---|---|---|
| kernel | 0.06 | 0.03 | **calibrated** |
| FHN excitable | 0.02 | 0.02 | **calibrated** |
| FHN oscillatory | 0.17 | 0.17 | invalid |
| Izhikevich | 0.15 | 0.25 | invalid |

The warm start carries each block's answer into the next fit, so the track is smooth by construction. **The FHN
oscillatory and Izhikevich drift results are therefore not evidence.** Among them is FHN α on rec 3 (ρ −0.78,
p 0.02), whose fake track drifts as well (ρ −0.88). Re-running them with cold starts would cost about 3× the CPU.

**Calibrated models on real cycles.**
- **Kernel.** The recovery time (`decay_frac`, as a fraction of the cycle) lengthens along rec 542 (ρ +0.83,
  p 0.001; von Neumann p 0.001) and rec 6 (ρ +0.55, p 0.024; von Neumann p 0.001). It does not change on rec 3 or on
  the three sequences (p ≥ 0.08).
  - This agrees with the restitution study's slow-drift term: on these chains, recovery and gap drift together.
- **FHN excitable.** α (= a + b·z) does not drift anywhere (p ≥ 0.11). The time scale (`span`) wanders on rec 542
  (von Neumann p 0.016) but shows no trend. The gain trends on rec 542 (ρ +0.48, p 0.023), and c on rec 542
  (p 0.027).
  - On seq 7, gain and c move with |ρ| = 0.9, but with 5 blocks the smallest p a shuffle can give is about 0.008, and
    the observed p was 0.07–0.08.
- **Counting the tests.** Across 18 + 30 real tests, the ρ test fired at 11 % and 7 %. That is a little above the 5 %
  floor, and it is concentrated on rec 542 and rec 6.
- **Identifiability.** Only α is identifiable for FHN (with w hidden, a and z enter only as a + b·z). For Izhikevich,
  the free time scale and gain trade off I, a and the voltage scale, so a, b, c and d are poorly identified jointly.
  - d sat on its bound in 56 % of seq 3 blocks and 30 % of rec 6 blocks; b sat on its bound in 25 % of rec 6 blocks.

## What can be claimed, and what cannot

**Can be claimed.**
- "Within drop trains (117 sequences, three W3 chains), a drop's half-recovery time does not depend on the gap before
  it once depth or slow drift is allowed for. The raw positive association is matched or exceeded by the association
  with the gap *after*, which points to censoring of the recovery measure at the next drop, not restitution."
- "Across the hours-long gaps of the `drop_detection_v1` census on M2_aug and M2_concat, a longer quiet spell before a
  drop goes with a longer recovery (Stouffer z +5.0 and +3.1). This survives depth, event order and the gap after,
  and is about halved by fall width." That is restitution-like in the cardiac direction, at hours, on oyster. On
  LM_fs2 and CO_fs2 there are too few channels to say.
- "No cycle model tested (fall + recovery kernel, FHN excitable, FHN oscillatory, Izhikevich 2003) predicts a held-out
  drop cycle better than the mean of the neighbouring cycles. On fake cycles every model does slightly better than
  that baseline. So these models do not describe fungal drop cycles beyond what noise gives."
- "The kernel's recovery fraction lengthens along two of the three long chains (permutation p ≤ 0.024, with a drift
  test calibrated on fake cycles)."

**Cannot be claimed.**
- That fungal drops are excitable, oscillatory or Izhikevich-like as biology.
- Any drift in FHN oscillatory or Izhikevich parameters: those drift tests are miscalibrated by the warm start.
- That the census effect is restitution in a mechanistic sense. The census mixes event families. Its windows are
  padded, so its onsets come from an anatomy search. And a slow, non-monotone modulation of both gaps and recoveries
  is not removed by an index term.
- Anything about the 43 sequences with fewer than 5 recoverable pairs, or about Lion's mane sequences (not imported).
- Seq 3's negative relation (one train).

## Files and how to reproduce

**New modules.**
- `Pipelines/fhn/restitution.py`: pairs (before/after), ρ with a vectorised permutation null, partial Spearman, and
  combine (sign / Stouffer / Fisher).
- `Pipelines/fhn/izhikevich.py`: the model (numba RK4 with an adaptive step near the peak), its periodic orbit and the
  fitter.
- `Pipelines/fhn/track.py`: blocks, held-out prediction and the drift test.
- `Pipelines/fhn/b3_data.py`: the event inputs (sequences, chains, census), read-only.
- `Pipelines/fhn/b3_figures.py`: the figures.
- `Pipelines/fhn/run_b3.py`: the runner.

**Tests.** All written first and run red before the code existed. 21 tests in all:
- `tests/test_restitution.py`: 9 tests;
- `tests/test_fhn_izhikevich.py`: 5 tests;
- `tests/test_fhn_track.py`: 7 tests.

**Outputs.** `docs/thesis/data/ch10_fhn/b3_restitution.json`, `b3_track.json`, and
`b3_restitution_rho|b3_restitution_scatter|b3_track_ratio|b3_track_params .png/.pdf`.

**Commands** (from the repo root):

    "/c/ProgramData/anaconda3/python.exe" -m pytest -q tests/test_restitution.py tests/test_fhn_izhikevich.py tests/test_fhn_track.py tests/test_fhn_fit.py tests/test_fhn_model.py tests/test_import_boundaries.py
    "/c/ProgramData/anaconda3/python.exe" Pipelines/fhn/run_b3.py restitution            # ~20 s
    "/c/ProgramData/anaconda3/python.exe" Pipelines/fhn/run_b3.py track --workers 2      # ~32 min wall, ~64 min CPU
    "/c/ProgramData/anaconda3/python.exe" Pipelines/fhn/run_b3.py figures

## What Chapter 10's B3 section should say

> **Restitution.** We asked whether a drop recovers faster when the gap before it was shorter. Recovery was Event
> shape's half-recovery time, the gap was the onset-to-onset interval, and each train had its own seeded permutation
> null (1,000 shuffles). Results were combined by a √n-weighted signed Stouffer z.
>
> Within trains the answer is no. Over 74 scorable sequences the raw lean (z = +2.9) vanishes given depth (+0.6) or
> event order (+0.7). It is dwarfed by the same correlation with the gap *after* each drop (+9.9), which is an
> artefact of censoring the recovery at the next drop. The three long chains behave the same way.
>
> Across the hours-long gaps of the drop-detector census, oyster recordings show a modest restitution-like relation
> (M2_aug z = +5.0, M2_concat +3.1, pair-weighted ρ ≈ 0.25). It survives depth, order and the next gap, but is halved
> by the fall's duration.
>
> **Models.** Judged by held-out-cycle prediction against the mean of the neighbouring cycles, none of the four models
> (the fall + recovery kernel, FHN excitable, FHN oscillatory, Izhikevich 2003) beats that baseline on real cycles.
> All of them beat it slightly on quiet and phase-scrambled fake cycles. The excitable-system models therefore do not
> describe the drop cycle beyond what noise gives; the simple kernel ties and the neuron models lose.
>
> Only the kernel's recovery fraction drifts measurably along two long chains. The FHN oscillatory and Izhikevich
> parameter tracks were not testable, because their warm-started fits drift even on fake cycles.

**`docs/rq_roundB/README.md` should record:**
- B3 has been answered, with the negative and the census-only positive above.
- The open follow-up: a censoring-aware recovery, for example by survival analysis with the next onset as the
  censoring time.
- The unexplained mismatch between `motif_features.recovery_time_s` and Event shape on the channel.

**Caveats.**
1. The FHN fits were cut to one start per block and run on one draw of each null.
2. The rec 542 FHN oscillatory fit did not converge.
3. The gap rule removed 68 of rec 3's 115 cycles.
4. Reishi cycles have about 20 samples each.
5. The quiet null for seq 3 had 94 candidate windows.
