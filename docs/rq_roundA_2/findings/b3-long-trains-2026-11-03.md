# B3 follow-up: neuron models on the longest drop trains, with phase-response curves. 2026-11-03

Made by `Pipelines/fhn/run_long.py` (research prompt `docs/prompts/research/01-b3-long-trains-neuron-models.md`).
It is read-only: the database is opened `mode=ro`, the channels are memory-mapped, and nothing was written to the
database, the step cache or `DATA/`. M4_aug, Schizophyllum commune, L_R and F2B were never read; no Review queue was
opened and no verdict was written.

Outputs are in `docs/thesis/data/ch10_fhn_long/`: `results.json` (the summary), `trains.json`, `regression.json`
(+ `b3_track.json`, the re-run of B3's tracking), `fits.json`, `track.json`, `prc.json`, the run logs, and per train
the figures `fit_`, `track_`, `prc_models_`, `prc_spont_` (trains of 60+ cycles) and `returnmap_`, each PNG + PDF.

This is post-freeze work. Whether any of it goes into Chapter 10 is the researcher's call.

## In plain words

**The question.** Fungal recordings often show trains of drops: the voltage falls sharply, recovers, and falls
again. Neuroscience has small "toy neurons" that fire over and over. Earlier we asked whether two of them
(FitzHugh–Nagumo, Izhikevich) describe the drop cycles better than noise does, and on short trains the answer was
no. Here we asked again on the longest trains we have, with three more toy neurons: van der Pol (the simplest
"relaxation" oscillator), Morris–Lecar (which comes in a Type I and a Type II flavour) and Hindmarsh–Rose (a
bursting model).

**Answer: still no.** The longer trains do not change the verdict.
- **The average cycle.** Every model can be bent into the shape of an average drop cycle: R² is 0.9 or more for
  most of them. But the same models bend just as well into "average cycles" cut from noise, so a good fit on its
  own means nothing. What does separate real trains from noise is simpler: **the real average cycle is far taller**
  than any fake one on 9 of the 11 trains, often ten to a hundred times.
- **The best description is still the plainest.** A sudden fall followed by an exponential recovery (the "kernel")
  ranks first on 6 of 11 trains. FitzHugh–Nagumo ranks first on the 5 fast or smooth ones. None of the three new
  models ranks first anywhere. Morris–Lecar comes close on four trains, and van der Pol does no better than a plain
  sine wave.
- **Forecasting a cycle it has not seen.** We hide one cycle and ask each model, fitted to the cycles around it, to
  forecast it. The yardstick is the plain average of those same neighbouring cycles. **No model beats that
  yardstick on any train** (all 77 scores are 1.00 or worse to two decimals, where below 1 would mean "better"; the
  three a hair under 1, at 0.997–0.999, do worse than every one of their own fake trains). The models forecast the
  *fake* cycles slightly better than the yardstick, because they smooth noise, but not the real ones.
- **Do the cycles change along a train?** On the long oyster and lion's mane chains, the share of each cycle that
  the kernel's recovery takes grows steadily along the train (rec 6, rec 542, and the 10 Hz reishi train seq 20). This time the drift test was
  checked on the fake trains first, and there it is right about as often as it should be. So the drift is real,
  but it is a slow change in recovery time, not evidence for any neuron model.

**What a phase-response curve (PRC) is.** Think of pushing a child on a swing. A push at one moment speeds the
next swing, a push at another slows it, and at some moments it barely matters. A PRC is that curve for a rhythm:
nudge it at this point in its cycle, and does the next beat come early or late?
- If nudges can only ever bring the next beat *sooner*, the curve is **Type I**. That is a "mousetrap": a system
  that waits near a threshold and fires when pushed over it.
- If nudges can bring it sooner *or* later depending on when they land, the curve is **Type II**. That is a true
  self-sustaining oscillator, like a swing.

**What the PRCs here show: what the fitted *models* would do, not what the fungus does.** Nobody nudged a fungus.
- **The model curves are almost all Type II.** But the call depends on bookkeeping. If the "hidden" variable we
  cannot record is defined differently (for example, as the voltage a moment ago), 8 of the 33 smooth-model curves
  flip from Type II to Type I. The size of the curve changes by a factor of 1 to 50 as well. That is exactly the
  warning of Wilshin, Kvalheim & Revzen (2024): a PRC depends on which coordinates you hold fixed. The fungus does
  not tell us which ones.
- **The models also lose the forecasting test.** So their PRCs describe the models, not the fungus.

**The "spontaneous" estimate: a weaker thing the long trains allow.** The signal wobbles a little on its own. Do
those wobbles, at a particular point of a cycle, go with the next drop coming early or late? We looked on the four
trains with 60 or more cycles.
- **A first pass looked like a yes on three trains.** But one of the five nulls is a trap of the method itself. A
  long cycle and a short one are both squeezed onto the same 0-to-1 phase axis, so a long cycle's shape *looks*
  different at any given phase even when nothing links shape and timing.
- **We built a fake train to measure that trap:** one fixed drop-and-recovery shape restarted at the real drop
  times, plus noise. It reproduces the reishi result exactly, and more.
- **One train survives every null: the oyster chain rec 6.** There, a cycle whose fall lags its detected start
  (the voltage still a little high just after the onset, then lower) goes with the next drop coming sooner.
  - **A later check shrinks this** (main session, 4 Nov; see C2's check). Cut in plain seconds after each drop
    instead of stretched to a common length, the pattern at the drop is no longer significant, so most of it was
    the stretch trap after all. A weaker link remains, 10–15 minutes into the recovery.
  - **The proper test:** a stimulus delivered at that phase. This is a hint that such a test could be aimed there,
    not evidence that it would work.

**Options and a recommendation.**
1. **Report this as a negative result that confirms B3 on longer trains and more models.** Add the rec 6
   correlation (weak, and in the recovery rather than at the drop once the stretch is removed) as one hint that
   needs a stimulation experiment.
2. **Spend more compute** (Hindmarsh–Rose, more null draws, MJu26a with a different detector).
3. **Drop it from Chapter 10.**

**Recommendation: 1.** The verdict is the same as B3's, now on trains three to six times longer and with five more
nulls and models; more compute would not change a verdict that every model loses at the first test. MJu26a would
need a detector chosen by judgement (below), which is a new study, not this one.

## The trains: the rule first, then the spans

The rule, written before any fit was looked at, is in `trains.json` (`rule`):
- **Chain rule** (the `chain_cycles` template's first steps, `b3_data.CHAIN_STEPS`):
  - rolling-mean detrend over 600 s;
  - `noise_threshold` at 4 σ below, with σ taken over the whole run span;
  - minimum event 30 s, merge gap 60 s, Event shape onsets;
  - a train ends where a gap exceeds 3 h.
- **When a W3 chain "continues past its span":** only when its own-span train comes within 3 h of a span edge.
  - It is then re-run on a span widened by 48 h each side, up to 4 times. The extension stops once the train ends at
    least 3 h inside both edges *and* two successive widenings agree on where it ends.
  - The agreement check was added after rec 3's first widening. The reason is that σ is computed over the whole run
    span, so a wider run moves the cut itself.
- **New trains (seq 122, MJu26a)** are the chain rule's train around their seed span. Fewer than 20 events counts
  as no train.

| train | recording | span (h) | events | cycles (gap rule) | median cycle | decision |
|---|---|---|---|---|---|---|
| seq 20 | 469, Fig2A CH3, 10 Hz, V | 0.17–0.25 | 114 | 86 | 2.7 s | stored sequence |
| seq 1 | 4, M2_aug CH4 | 378.56–379.69 | 67 | 55 | 54 s | stored sequence |
| seq 21 | 467, Fig2A CH1 | 0.20–0.23 | 59 | 47 | 1.9 s | stored sequence |
| seq 22 | 467, Fig2A CH1 | 0.13–0.16 | 57 | 42 | 2.0 s | stored sequence |
| seq 2 | 16, M2_aug CH16 | 33.20–34.59 | 40 | 29 | 147 s | stored sequence |
| seq 3 | 6, M2_aug CH6 | 387.26–407.42 | 29 | 27 | 2631 s | stored sequence |
| seq 6 | 6, M2_aug CH6 | 421.60–434.09 | 20 | 17 | 2090 s | stored sequence |
| seq 7 | 16, M2_aug CH16 | 80.11–80.77 | 18 | 16 | 131 s | stored sequence |
| rec6_370_470h | 6, M2_aug CH6 | 373.88–444.57 | 115 | 103 | 2277 s | **kept** as W3 cut it: the train ends > 3 h inside its span |
| rec3_490_540h_ext | 3, M2_aug CH3 | **481.38–572.63** | 188 | 78 | 1320 s | **extended** (W3: 490–540 h, 116 events, 47 cycles) |
| rec542_370_490h | 542, L_LM CH3, 10 Hz, mV | 387.54–474.13 | 163 | 110 | 1419 s | **kept** as W3 cut it |
| seq 122 | 1, M2_aug CH1 | 485.95–488.52 | — | — | — | **not a train under the rule**: 5 events in a 3.6 h run, 1 in the hand-marked span |
| MJu26a | 692, MJu26a_fs2 CH1, 2 Hz | 314–322 | — | — | — | **not a train under the rule**: 9 events in 266–370 h, 1 in the seed span |

Notes:
- **rec 3's extension.** The successive widenings found trains of 481.4–587.7 h (242 events, running into the run's
  edge), 394–636 h (536 events, the whole run), then 481.4–572.6 h twice (199 and 188 events). The last two agree,
  so the rule takes 481.4–572.6 h. That the second widening briefly swallowed the whole run is the σ effect above;
  read this train's extent as rule-defined but sensitive.
- **seq 122** is a span marked by hand ("a regular sequence of 100 ...", origin `annotation`, `needs_extraction = 1`):
  its 100 events were never stored. The chain rule sees one drop in it. Its "caterpillars" are not 4 σ drops of
  30 s or more.
- **MJu26a.** B10's ~20-minute oscillation is a smooth, symmetric wave. A 600 s rolling mean removes much of it, and
  it rarely dips 4 σ for 30 s.
  - **What it would take:** a detector chosen for that wave (for example downward zero crossings of a band-passed
    trace). That is a judgement, so by the prompt's stop rule it was not done here.
  - **Its double:** L_LM rec 542 is MJu26a CH14, not CH1, so no span is counted twice.
- **Bursts (for Hindmarsh–Rose).** The rule (`hindmarsh_rose.burst_structure`, fixed before looking) splits a train
  wherever a gap exceeds 3× the median gap. A train is bursting when it gives at least 3 groups of at least 3 drops
  and the long gaps are at least 5 % of all gaps.
  - **seq 20** is one regular group: no bursts.
  - **seq 122** is not a train.
  - **rec3_490_540h_ext** is the only train the rule calls bursting. Its 19 groups hold 1–58 drops, and the burst
    "periods" run from 1.2 to 20 h.
  - **rec542** comes close (long gaps 4.9 % of gaps).

## The regression check (run first)

`run_long.py regress` re-runs `run_ch10.fit_all` on seq 3, 7 and 22 (8 restarts) and `run_b3.run_track` (B3's
warm-started fitters) on the real cycles of the six B3 datasets. `regression.json`: every number reproduces within
fit noise.

| | before | now |
|---|---|---|
| FHN oscillatory R², seq 3 / 7 / 22 | 0.873 / 0.971 / 0.997 | 0.873 / 0.971 / 0.997 |
| FHN excitable R², seq 3 / 7 / 22 | 0.931 / 0.981 / 0.996 | 0.931 / 0.981 / 0.996 |
| B3 held-out ratio, rec 6: kernel / FHN exc / FHN osc / Izhikevich | 1.084 / 1.337 / 1.294 / 1.46 | 1.084 / 1.337 / 1.293 / 1.46 |
| B3 held-out ratio, the other 20 dataset × model cells | — | identical to 3 decimals, except seq 3 FHN osc 1.628 → 1.601 and seq 22 FHN osc 0.995 → 0.992 (multi-start fit noise) |

## A. Mean-cycle fits

200 points per cycle, as `run_ch10`. Real fits: FHN 8 restarts, budget 300; Izhikevich 5/200; van der Pol 4/200;
Morris–Lecar 3 starts per class/150. Nulls:
- **Draws:** quiet, phase-scrambled and AAFT, each 10 draws on trains under 60 cycles and 5 on longer ones.
- **Cut 1:** the five slow models were fitted to the first 3 draws of each kind only, at the null budgets (FHN 2
  restarts/60, Izhikevich 3/100, van der Pol 2/80, Morris–Lecar 1/60).

Each cell is R², then whether the real R² beats **every** draw of the quiet / phase-scrambled / AAFT null (✓/✗); a
slow model is judged against its 3 draws per kind. The last column is the height statistic: the real mean cycle's
peak-to-peak height and whether it exceeds every null mean cycle's.

| train | kernel | jump_exp | sinusoid_1 | FHN osc | FHN exc | Izhikevich | van der Pol | Morris–Lecar | height |
|---|---|---|---|---|---|---|---|---|---|
| seq20 | 0.970 ✓✓✓ | 0.775 ✗✓✓ | 0.863 ✗✗✗ | 0.982 ✗✓✓ | **0.992** ✓✓✓ | 0.660 ✗✗✓ | 0.904 ✗✗✗ | 0.980 ✓✓✓ | 0.46 mV ✓✓✓ |
| seq1 | **0.985** ✓✓✓ | 0.918 ✓✓✓ | 0.625 ✗✗✗ | 0.885 ✗✗✗ | 0.884 ✗✓✗ | 0.772 ✗✓✗ | 0.731 ✗✗✗ | 0.901 ✗✗✗ | 2.26 mV ✓✓✓ |
| seq21 | 0.986 ✓✓✓ | 0.717 ✗✗✗ | 0.948 ✗✗✗ | **0.997** ✓✓✓ | 0.996 ✗✓✓ | 0.761 ✗✗✓ | 0.951 ✗✗✓ | 0.975 ✗✓✓ | 0.182 mV ✓✓✓ |
| seq22 | 0.986 ✓✓✓ | 0.737 ✗✗✗ | 0.941 ✓✗✗ | **0.997** ✓✓✓ | 0.996 ✓✓✓ | 0.748 ✗✓✓ | 0.941 ✓✓✗ | 0.973 ✓✓✓ | 0.223 mV ✓✓✓ |
| seq2 | **0.994** ✓✓✓ | 0.893 ✓✓✓ | 0.697 ✗✗✗ | 0.914 ✗✗✗ | 0.926 ✓✓✓ | 0.781 ✓✓✓ | 0.778 ✗✗✗ | 0.967 ✓✓✓ | 4.15 mV ✓✓✓ |
| seq3 | **0.957** ✓✗✓ | 0.841 ✓✓✓ | 0.748 ✗✗✗ | 0.873 ✗✗✗ | 0.931 ✗✓✓ | 0.773 ✗✓✗ | 0.786 ✗✗✓ | 0.948 ✗✓✓ | 19.3 mV ✓✓✗ |
| seq6 | 0.981 ✓✓✓ | 0.854 ✓✓✓ | 0.839 ✗✗✗ | **0.989** ✓✓✓ | 0.988 ✓✓✓ | 0.811 ✓✓✓ | 0.857 ✓✗✗ | 0.987 ✓✓✓ | 6.69 mV ✓✓✓ |
| seq7 | **0.984** ✓✓✓ | 0.840 ✓✓✓ | 0.802 ✗✗✗ | 0.971 ✓✓✗ | 0.981 ✓✓✓ | 0.718 ✓✗✗ | 0.830 ✗✗✗ | 0.981 ✓✓✓ | 6.76 mV ✗✓✓ |
| rec6_370_470h | **0.976** ✓✓✓ | 0.832 ✓✓✓ | 0.800 ✗✗✗ | 0.895 ✗✗✗ | 0.963 ✓✓✓ | 0.724 ✓✗✓ | 0.823 ✗✗✗ | 0.962 ✓✓✓ | 10.3 mV ✓✓✓ |
| rec3_490_540h_ext | 0.932 ✓✓✓ | 0.963 ✓✓✓ | 0.702 ✗✗✓ | 0.888 ✗✗✓ | **0.986** ✓✓✓ | 0.655 ✗✓✓ | 0.775 ✗✗✓ | 0.907 ✗✓✓ | 9.52 mV ✓✓✓ |
| rec542_370_490h | **0.950** ✓✓✓ | 0.946 ✓✓✓ | 0.113 ✗✗✗ | 0.246 ✓✗✗ | 0.812 ✓✓✓ | 0.626 ✓✓✓ | 0.131 ✗✗✗ | 0.432 ✓✗✓ | 10.8 mV ✓✓✓ |

Bold is the best by AIC. ΔAIC to the best (a ranking, not a test; the 200 points are not independent):

| train | kernel | jump_exp | sinusoid | FHN osc | FHN exc | Izh | vdP | M–L |
|---|---|---|---|---|---|---|---|---|
| seq20 | 261 | 663 | 562 | 163 | 0 | 756 | 494 | 189 |
| seq1 | 0 | 343 | 646 | 418 | 421 | 559 | 583 | 387 |
| seq21 | 277 | 882 | 542 | 0 | 30 | 858 | 533 | 403 |
| seq22 | 292 | 880 | 578 | 0 | 25 | 881 | 584 | 431 |
| seq2 | 0 | 577 | 783 | 539 | 511 | 730 | 724 | 349 |
| seq3 | 0 | 260 | 349 | 220 | 100 | 340 | 321 | 42 |
| seq6 | 98 | 503 | 521 | 0 | 13 | 565 | 500 | 30 |
| seq7 | 0 | 461 | 503 | 123 | 46 | 585 | 476 | 40 |
| rec6_370_470h | 0 | 386 | 419 | 298 | 90 | 495 | 398 | 92 |
| rec3_490_540h_ext | 317 | 194 | 609 | 422 | 0 | 650 | 557 | 385 |
| rec542_370_490h | 0 | 16 | 572 | 548 | 272 | 412 | 572 | 491 |

Height (mV; the real mean cycle, then each null's median / max over its draws):

| train | real | quiet | phase-scrambled | AAFT |
|---|---|---|---|---|
| seq20 | 0.46 | 0.026 / 0.032 | 0.060 / 0.093 | 0.038 / 0.115 |
| seq1 | 2.26 | 0.104 / 0.132 | 0.377 / 0.632 | 0.47 / 0.771 |
| seq21 | 0.182 | 0.030 / 0.055 | 0.038 / 0.066 | 0.050 / 0.117 |
| seq22 | 0.223 | 0.025 / 0.042 | 0.060 / 0.082 | 0.067 / 0.151 |
| seq2 | 4.15 | 1.08 / 2.69 | 1.67 / 2.47 | 2.11 / 2.97 |
| seq3 | 19.3 | 1.97 / 3.63 | 6.52 / 12.2 | **17.6 / 28.4** |
| seq6 | 6.69 | 2.54 / 3.77 | 2.29 / 2.73 | 3.21 / 4.73 |
| seq7 | 6.76 | 1.93 / **18.4** | 2.91 / 3.88 | 3.96 / 6.12 |
| rec6_370_470h | 10.3 | 0.141 / 0.171 | 1.91 / 2.68 | 3.65 / 4.42 |
| rec3_490_540h_ext | 9.52 | 0.421 / 0.564 | 2.00 / 3.07 | 2.16 / 2.44 |
| rec542_370_490h | 10.8 | 0.205 / 0.291 | 0.976 / 1.19 | 3.06 / 3.97 |

What A shows:
- **R² is no test.** Even the sinusoid reaches 0.6–0.95 on real cycles and on fake ones. The kernel beats every
  draw of all three nulls on 10 of 11 trains, which is the strongest R² result here. But its fake-cycle R² is itself
  0.9 or more on most trains.
- **Height is the statistic that separates.** It does so on 9 of 11 trains, outright and by a wide margin.
  - **seq 3:** AAFT reaches the real height (median 17.6 vs 19.3 mV). Its ~44 min cycles carry the channel's big
    excursions, and an AAFT copy keeps the excursions' values.
  - **seq 7:** one quiet window (18.4 mV) exceeds the real height.
- **The new models.** Morris–Lecar is the best of them: second or third by AIC on seq 3, 6 and 7, but never first.
  Van der Pol is no better than the sinusoid on most trains; it and FHN oscillatory collapse on rec 542, whose
  cycle is a 5 s drop in a 24 min flat recovery that no smooth limit cycle can make. Izhikevich is last or near
  last everywhere.
- **Morris–Lecar's class.** It lands in its Hopf (Type II) class on 8 trains and its SNIC (Type I) class on seq 3,
  rec 6 and rec 542. On seq 20 and rec 6 only one class could be fitted (the other's starts all failed).
- **Parameters on a bound** (reported, not identifiable there):
  - Izhikevich: b and d on seq 20; b, d and time_ratio on seq 3; all five shape parameters on seq 6 and 7.
  - van der Pol: μ on seq 22 and rec 542 (at 12, its stiff limit).
  - Only identifiable combinations are reported: FHN's α = a + b z (z fixed at −0.4) as before. For van der Pol,
    μ (its gain absorbs the amplitude). For Morris–Lecar, I and φ within its class.

Figures `fit_<train>`: the mean cycle with every fit (left), each model's R² on the recording against the null
draws (middle), and the height statistic (right).

## B. Per-cycle held-out tracking

100 points per cycle, blocks of 3 cycles (sequences) or 5 (chains and long trains), cycle i predicted by the mean of
the fitted curves of the blocks either side of its own; the score is that error over the neighbours'-mean error
(pooled; below 1 means the model is better). **Cold starts:** every block's fit starts from the same point, the
train's own mean-cycle fit from A, so no block's estimate leans on its predecessor's.
- **Budgets:** FHN oscillatory 1 start/80, FHN excitable 1/100, Izhikevich 2/150, van der Pol 1/80, Morris–Lecar
  1/80 in its A class.
- **Null sets:** 2 draws each of quiet, phase-scrambled and AAFT; the kernel and the sinusoid ran on all of them.
- **Cut 2:** the slow models ran first on the real cycles only. Their null sets (draw 0 of each kind) were then run
  where the real ratio was below 1, the one case in which a null can change the verdict; that was FHN oscillatory
  on seq 22 only. The remaining slow-model null sets were run afterwards as a supplement; see the note under the
  table.

Real pooled ratio [range over the null sets]:

| train | cycles | kernel | sinusoid | FHN exc | FHN osc | Izhikevich | van der Pol | Morris–Lecar |
|---|---|---|---|---|---|---|---|---|
| seq20 | 86 | 1.02 [0.98–1.00] | 1.16 [0.98–0.99] | 1.19 [0.98–1.00] | 1.01 | 1.21 [0.98–0.99] | 1.10 | 1.02 |
| seq1 | 55 | 1.06 [0.97–1.00] | 2.46 [0.97–1.01] | 1.47 | 1.48 | 1.46 | 2.06 | 1.33 |
| seq21 | 47 | 1.00 [0.99–1.00] | 1.00 [0.98–1.00] | 1.01 | 1.00 | 1.03 | 1.00 | 1.00 |
| seq22 | 42 | 1.00 [0.99–1.00] | 1.01 [0.98–0.99] | 1.04 | 1.00 [0.98–0.99] | 1.05 | 1.01 | 1.01 |
| seq2 | 29 | 1.00 [0.97–1.00] | 1.49 [0.88–0.99] | 1.20 | 1.13 | 1.19 | 1.34 | 1.04 |
| seq3 | 27 | 1.14 [0.95–1.00] | 2.44 [0.92–1.00] | 2.06 | 1.61 | 1.81 | 2.24 | 1.31 |
| seq6 | 17 | 1.03 [0.96–0.99] | 1.99 [0.96–0.99] | 1.05 | 1.03 | 1.87 | 1.77 | 1.07 |
| seq7 | 16 | 1.03 [0.98–1.00] | 1.28 [0.95–1.00] | 1.03 | 1.05 | 1.26 | 1.24 | 1.03 |
| rec6_370_470h | 103 | 1.08 [0.98–1.00] | 1.76 [0.98–0.99] | 1.34 [0.97–1.00] | 1.45 [0.99–1.00] | 1.60 [0.98–1.00] | 1.68 [0.98–1.00] | 1.16 [0.98–1.00] |
| rec3_490_540h_ext | 78 | 1.01 [0.98–0.99] | 1.04 [0.97–1.00] | 1.03 | 1.01 | 1.01 | 1.03 | 1.01 |
| rec542_370_490h | 110 | 1.00 [0.94–0.97] | 1.67 [0.92–0.96] | 1.05 [0.94–0.96] | 1.54 [0.94–0.95] | 1.17 [0.94–0.96] | 1.65 [0.94–0.96] | 1.21 [0.94–0.96] |

**The supplement** ran the slow models' remaining draw-0 null sets, the longest trains first, and was stopped after 34 of 162 tasks for time: every slow model on rec 542 and rec 6, and FHN excitable and Izhikevich on seq 20. Those cells are filled in above; the others show the real ratio only. Every supplement null set scored 0.94–1.00, below its real ratio, as everywhere else. `track.json` says `complete: false` for that reason; its results are final for what they cover.

- **No model on any train beats the neighbours' mean.** The best real ratios (1.00) are on the 10 Hz reishi trains,
  whose cycles are so alike that every fitted curve and the neighbours' mean are the same curve. The three values
  below 1 before rounding are each beaten by every one of their null sets: FHN oscillatory on seq 22 (0.9966;
  nulls 0.982–0.994), and the kernel on seq 21 (0.9988; 0.987–0.999) and rec 542 (0.9988; 0.942–0.970).
- **The fake trains reproduce B3's pattern.** Every model predicts a fake cycle a little *better* than the fake
  neighbours' mean (0.88–1.00), because smoothing helps on noise. On real cycles it does not.
- **Cold starts against B3's warm starts.** The cold-start ratios differ from B3's warm ones. On rec 6: FHN
  oscillatory 1.45 cold vs 1.29 warm, Izhikevich 1.60 vs 1.46, kernel and FHN excitable unchanged (they never used
  warm starts). A cold block fit is a worse fit, which raises the ratio but leaves the verdict as it was.

**Drift tests** (`track.drift_test`, 1000 shuffles of the block order; |Spearman ρ| for a trend, the von Neumann
ratio for any slow wander). With cold starts the tests are calibrated where the fake trains could check them: on
the 66 kernel fake-train series, 5 (decay_frac), 6 (rise_frac) and 3 (amplitude) reach p < 0.05 on either test,
against ~6.5 expected for two tests at 5 %. The slow models' own fake-train series (from the supplement, 6–9 each) are just as quiet for FHN oscillatory α (0 of 9), FHN excitable α (1 of 9), van der Pol μ (1 of 6) and Morris–Lecar I and φ (0 of 6). The exception is Izhikevich's gain (4 of 9), which is therefore not counted.

The drifts on real trains that clear both their own shuffle and the fake-train calibration:

| train | parameter | ρ (p) | von Neumann (p) | fake trains with p < 0.05 |
|---|---|---|---|---|
| rec542_370_490h | kernel recovery fraction (decay_frac) | +0.83 (0.001) | 0.96 (0.001) | 0 / 6 |
| rec6_370_470h | kernel recovery fraction | +0.55 (0.024) | 0.21 (0.001) | 0 / 6 |
| seq20 | kernel recovery fraction | +0.50 (0.006) | 2.19 (0.49) | 0 / 6 |
| rec6_370_470h | FHN oscillatory α | +0.60 (0.005) | 0.66 (0.001) | 0 / 3 |
| rec542_370_490h | Morris–Lecar I | +0.80 (0.001) | 1.07 (0.027) | 0 / 3 |

- **seq 1's kernel drifts too** (ρ −0.79), but 4 of its 6 fake-train series drift as well (its stretch has a slow
  baseline wander), so it is not counted.
- **The model parameters that drift** (FHN α, Morris–Lecar I, Izhikevich d and I, and every model's gain on rec 6)
  move together with the kernel's recovery. They say the same thing in each model's own terms: the recovery slows
  along the train (decay_frac, a fraction of the cycle, grows).
- **seq 6 and 7** have only 5 blocks; their p = 0.014 is the smallest a 5-point series allows, and it is not
  counted.

Figures `track_<train>`: the pooled ratios against the nulls (left), and the z-scored parameter series of each
model's identifiable parameter with its drift p-values (right).

## C. Phase-response curves

### C1. Model PRCs

For every oscillating fit (FHN oscillatory, van der Pol, Morris–Lecar, Izhikevich), from its mean-cycle fit:
- **Computation:** by perturbation (Wilshin et al. Sect. 6.1: a voltage kick of ε, 5 periods, phase change over
  2ε, 100 base phases), and by the adjoint as an independent check, except Izhikevich, which is hybrid (it resets)
  and so has no adjoint.
- **Coordinates:** with the hidden variable held fixed, with the delayed voltage held fixed (the paper's delay of
  0.1 model units, and a quarter period), and with a linear change of the hidden coordinate.
- **Units:** converted to rad per mV of kick by the fit's gain.
- **Type:** one-signed = I, two-signed = II, by the minority sign's share of the curve's area (< 5 % = I).

| train | FHN osc | van der Pol | Morris–Lecar (class) | Izhikevich |
|---|---|---|---|---|
| seq20 | II → II (13.5) [adj ✗] | II → II | II → II (hopf) [adj ✗] | II (0.06) |
| seq1 | II → **I** | II → II | II → II (hopf) [adj ✗] | II |
| seq21 | II → II [adj ✗] | II → II | II → II (hopf) | II |
| seq22 | II → II [adj ✗] | II → II [adj ✗, μ on bound] | II → II (hopf) | II |
| seq2 | II → **I** | II → II | II → II (hopf) [adj ✗] | II |
| seq3 | II → II | II → II | II (0.08) → **I** (snic) | II (0.08) |
| seq6 | II → **I** | II → II | II → II (hopf) [adj ✗] | **I** (params on bounds) |
| seq7 | II → **I** | II → II | II → II (hopf) [adj ✗] | **I** (params on bounds) |
| rec6_370_470h | II → II | II → II | II (0.08) → **I** (snic) | II |
| rec3_490_540h_ext | II → **I** | II → II | II → II (hopf) [adj ✗] | II |
| rec542_370_490h | II → **I** | II → II [adj ✗, μ on bound] | **I** → I (snic; R² 0.43) | II |

Reading the table:
- Each cell is the type with the hidden variable held fixed → the type with the delayed voltage held fixed (the
  paper's delay).
- The number in parentheses is the minority-sign share where it is near the 5 % line.
- [adj ✗] means the adjoint and the perturbation estimate differ by more than 10 % of the curve's size. There the
  type rests on the perturbation curve alone (the adjoint's backward integration is unreliable on stiff or slowly
  attracting cycles: van der Pol at μ = 12, Morris–Lecar near its bifurcations). Full numbers are in `prc.json`
  (`agreement`).

What C1 shows:
- **With the model's own hidden variable held fixed, 41 of 44 model PRCs are Type II** (two-signed). The exceptions
  are not credible: Morris–Lecar on rec 542 is a poor fit (R² 0.43), and Izhikevich on seq 6 and 7 has every shape
  parameter on a bound.
- **The call depends on the coordinates.** Holding the delayed voltage fixed instead turns 8 of the 33 smooth-model
  PRCs into Type I. Six of the 11 FHN curves flip; none of the van der Pol curves does, because a symmetric
  relaxation cycle stays two-signed in any coordinates. The curve's largest value changes by a factor of 1.2 to 51
  between the two coordinate choices (`coordinate_spread_ratio`). This is Wilshin, Kvalheim & Revzen's point, now
  on fitted models of fungal cycles: the type is not a property of the voltage trace.
- **Sizes**, with the hidden variable fixed:
  - fast reishi trains: 2–40 rad/mV (FHN), up to ~280 (Morris–Lecar, seq 20);
  - oyster chains (rec 6, seq 3): 0.2–0.9 rad/mV;
  - rec 542: 2–13 rad/mV.
- **All of it describes the fitted models.** They do not forecast held-out cycles better than the neighbours'
  mean (B).

Figures `prc_models_<train>`, in the paper's Fig. 1 style:
- one row per oscillating model;
- left: the limit cycle in (hidden, voltage) with isochron ticks coloured by phase;
- right: the PRC in rad/mV in each coordinate system, plus the adjoint.

### C2. The spontaneous phase–timing estimate (a PRC proxy; trains with 60+ cycles)

Method (`empirical_prc.estimate`):
- **Timing:** ΔT_i is cycle i's length minus the running median over ±5 cycles.
- **Wiggles:** r_i(φ) is cycle i's shape minus the running mean cycle, in 20 phase bins.
- **Fit:** ΔT ≈ Σ Z(φ_k) r_i(φ_k) by ridge regression, λ chosen by leave-one-out, scored by the leave-one-out R²
  (cv R²); 500 bootstrap draws for bands.
- **Edges:** the first and last 5 cycles are left out. There the centred window is one-sided, and a one-sided median
  keeps a drift's slope.
- **Nulls:**
  - ΔT shuffled across cycles (500 draws);
  - 20 draws each of quiet, phase-scrambled and AAFT fake trains cut at the real onsets, paired with the real ΔT;
  - **added here, a time-warp null** (20 draws, `run_long.timewarp_cycles`), described below.
- **The time-warp null:** one fixed drop-and-recovery waveform in *absolute* time, restarted at every real onset on
  the real onset levels, plus the recording's residual phase-scrambled.
  - **Why it is needed:** its cycles have the real lengths and no shape–timing link, except the one the method makes
    itself. Each cycle is resampled to a fixed number of points, so a longer cycle is a stretched view of the same
    waveform and looks different at any given phase.
  - **Why the other nulls miss it:** none of them has the real drop in it, so none can show this.
- **Clearing:** a train clears when its cv R² exceeds every null's 95th percentile. A bin is reported when the
  train clears and the bin's |Z| exceeds every null's 95th percentile.

| train | cycles used | cv R² | shuffle q95 | quiet q95 | phase-scr. q95 | AAFT q95 | **time-warp q95 (median)** | clears |
|---|---|---|---|---|---|---|---|---|
| seq20 | 78 | 0.356 | 0.047 | 0.061 | 0.228 | 0.165 | **0.636 (0.516)** | **no** |
| rec6_370_470h | 94 | **0.518** | 0.044 | 0.050 | 0.050 | 0.079 | 0.183 (0.037) | **yes** |
| rec3_490_540h_ext | 74 | 0.058 | 0.073 | 0.254 | 0.121 | 0.174 | 0.223 (0.068) | no |
| rec542_370_490h | 104 | 0.079 | 0.039 | 0.026 | 0.038 | 0.055 | 0.146 (0.057) | no |

- **seq 20 is the stretch artefact.** The time-warp null's *median* (0.52) is above the real 0.36. The four standard
  nulls alone would have called it a clear result (p ≤ 0.05 on each). Without the time-warp null this report would
  have claimed three trains (seq 20, rec 6, rec 542) instead of one.
- **rec 6 clears every null.** Five bins pass every null; the two whose bootstrap band excludes zero sit at the drop
  itself:
  - phase 0.10–0.15 of the cycle: Z = +0.82 rad/mV, band 0.46 to 1.10;
  - phase 0.15–0.20: Z = −0.44, band −0.70 to −0.03.
  - **Sign:** Z > 0 is an advance per mV of *upward* deviation.
  - **In words:** on this oyster chain, a cycle that is higher than its neighbours just after its detected onset
    (phase 0.10–0.15, the fall lagging) and lower just after that (0.15–0.20) tends to end early: the next drop
    comes sooner.
  - **Why that points at the detector:** a +/− pair either side of the onset is what a fall shifted slightly
    against its detected onset looks like, so the detector's onset placement is the first suspect (below).
    *Corrected by the check below:* onset jitter gives the opposite sign (a late-placed onset makes the signal lower
    just after it *and* the cycle shorter), and the stretch trap gives this one.
  - Sizes: ΔT has an SD of 219 s on a 2277 s cycle; the wiggles have an SD of 1.8 mV.
- **This is a correlation, not a PRC.** Three things can each produce it:
  - **slow drift** that a ±5-cycle median does not remove (rec 6's recovery does drift, B);
  - **noise;**
  - **the detector:** a deeper drop's onset may be placed differently, and the bins that carry the effect are exactly
    the bins around the onset the timing is measured from.

  Only a timed stimulus measures a PRC, and even then the hidden coordinate matters (C1).
- **Check: rec 6 in absolute time (main session, 2026-11-04).** The phase estimate stretches each cycle to a common
  length, the trap the time-warp null was built for. Cutting each cycle instead as a fixed window of plain seconds
  removes the stretch outright (`scripts/thesis/b3_long_rec6_abs_time.py`, `rec6_abs_time.json`). The window runs
  from 228 s before the onset to 1139 s after it: −0.1 to +0.5 of the median cycle, in 12 bins of 114 s. The gap rule
  keeps cycles of at least 0.6 medians, so every window ends before the next drop.
  - **The phase estimate reproduces:** cv R² 0.518.
  - **In absolute time cv R² falls to 0.208** (shuffle q95 0.043). The fake-train nulls were not rerun this way; in
    the phase version none had a q95 above 0.08.
  - **The onset pair goes:** 0–114 s after the onset, Z = +0.37 (band −0.03 to 0.65); 114–228 s, Z = −0.12 (band
    −0.47 to 0.26).
  - **What remains sits in the recovery:** 569–683 s, Z = −0.92 (band −1.32 to −0.26); 797–911 s, Z = +0.52 (band
    0.10 to 0.80).
  - **So most of the onset pair was the stretch.** Its sign is the stretch's: a longer cycle's first phase bins reach
    further into the trough. The time-warp null under-represents the stretch on this train (median cv R² 0.04 here,
    against 0.52 on seq 20).
  - **What survives:** a weaker link between the recovery's course 10–15 min after a drop and the next drop's
    timing. It is still a correlation.
- **The model PRCs** are drawn beside it on their own axis (other units, other phase origin). They are not
  comparable to it.

Figures `prc_spont_<train>`: Z(φ) with its bootstrap band and every null's 95 % |Z| envelope, with the cleared bins
marked (left), and the fitted models' PRCs (right).

### C3. The return map (T_{i+1} against T_i)

Spearman ρ over consecutive cycle pairs, against 500 shuffles. "Drift removed" is on ΔT, the interior cycles only.

| train | pairs | raw ρ (p) | drift removed ρ (p) |
|---|---|---|---|
| seq20 | 63 | +0.02 (0.88) | **−0.34 (0.008)** |
| seq1 | 53 | +0.95 (0.002) | +0.09 (0.55) |
| seq21 | 38 | −0.19 (0.27) | −0.25 (0.14) |
| seq22 | 30 | +0.36 (0.06) | +0.26 (0.22) |
| seq2 | 22 | +0.49 (0.03) | +0.39 (0.14) |
| seq3 | 25 | +0.87 (0.002) | **+0.57 (0.02)** |
| seq6 | 14 | +0.56 (0.03) | (too few interior pairs) |
| seq7 | 15 | +0.74 (0.006) | (too few interior pairs) |
| rec6_370_470h | 93 | +0.71 (0.002) | **+0.23 (0.04)** |
| rec3_490_540h_ext | 33 | −0.11 (0.54) | −0.19 (0.29) |
| rec542_370_490h | 90 | +0.66 (0.002) | +0.01 (0.90) |

- **The raw maps rise on most trains.** That is slow drift of the beat: neighbouring cycles share a slowly changing
  length. Taking the drift out removes most of it.
- **What remains:**
  - **seq 20 alternates** a little (a long cycle tends to be followed by a short one, ρ −0.34);
  - **seq 3 and rec 6** keep a small positive memory.
- None of this needs a neuron model. Alternation is what any refractory process with noise in its onset placement
  gives.

Figures `returnmap_<train>`.

## Every figure

All are in `docs/thesis/data/ch10_fhn_long/`, as `<name>.png` and `<name>.pdf`.

| figure | what it shows |
|---|---|
| `fit_seq20` | 10 Hz reishi, 86 cycles of 2.7 s: FHN excitable best; every model > 0.9 except Izhikevich and van der Pol; height 0.46 mV against fakes ≤ 0.12 |
| `fit_seq1` | oyster, 54 s cycles: the kernel best (0.985) and beats every null; the smooth oscillators sit inside the null clouds |
| `fit_seq21`, `fit_seq22` | 2 s reishi cycles: FHN oscillatory 0.997, but sinusoid and van der Pol 0.94–0.95; the fakes reach 0.9+ too |
| `fit_seq2` | oyster, 147 s: the kernel 0.994 beats every null; the sinusoid (0.70) does not beat any |
| `fit_seq3` | oyster, 44 min: the kernel best; AAFT reaches the real height (the only train where it does) |
| `fit_seq6`, `fit_seq7` | 17 and 16 cycles: FHN / the kernel best; Izhikevich's parameters all on bounds |
| `fit_rec6_370_470h` | the 103-cycle oyster chain: the kernel best; FHN oscillatory inside its nulls |
| `fit_rec3_490_540h_ext` | the extended rec 3 chain: FHN excitable 0.986 beats every null; the smooth oscillators do not |
| `fit_rec542_370_490h` | lion's mane at 10 Hz: a 5 s drop in a 24 min recovery; only the kernel and jump fit (0.95), the oscillators fail (0.11–0.43) |
| `track_<train>` (11) | pooled held-out ratios, all ≥ 1.00 on the recording against 0.88–1.00 on the fakes; the cold-start parameter series beside them (rec 6, rec 542: the recovery fraction climbs) |
| `prc_models_<train>` (11) | each oscillating fit's limit cycle with isochron ticks and its PRC in rad/mV in four coordinate systems, with the type in each panel's title |
| `prc_spont_seq20` | the estimate looks structured, but the time-warp null's own cv R² (0.52 median) is above the recording's (0.36): the resampling stretch |
| `prc_spont_rec6_370_470h` | clears every null (cv R² 0.52 vs ≤ 0.18): a +/− pair of bins either side of the onset, most of which is the stretch (C2's check) |
| `prc_spont_rec3_490_540h_ext`, `prc_spont_rec542_370_490h` | do not clear (cv R² 0.06, 0.08 against time-warp q95 0.22, 0.15) |
| `returnmap_<train>` (11) | T_{i+1} on T_i and the drift-removed ρ: drift dominates the raw maps; seq 20 alternates; seq 3 and rec 6 keep a small memory |

## What can and cannot be claimed

**Can be claimed:**
- On every train available under the chain rule, up to 110 cycles, eight cycle models describe the mean drop cycle
  with R² mostly above 0.9. Fake cycles get the same, so the fit itself is not evidence. The mean cycle's height is
  what separates real from noise (9 of 11 trains; AAFT and one quiet window reach it on the other two).
- No model, old or new, forecasts a held-out cycle better than the average of its neighbours, on any train
  (B3's verdict, now with five more models and trains three to six times longer).
- On rec 6, rec 542 and seq 20 the recovery slows along the train: a calibrated drift test with cold starts,
  silent on the fake trains.
- The fitted models' PRCs are mostly Type II in their own coordinates, and their type and size depend on the hidden
  coordinate, which the recordings cannot fix.
- On one oyster chain (rec 6), the recovery's course 10–15 min after a drop correlates weakly with the next drop's
  timing, measured in plain seconds after the drop (cv R² 0.21 against a shuffle q95 of 0.04). The stronger pattern
  at the drop itself in the phase estimate was mostly the stretch artefact (C2's check).

**Cannot be claimed:**
- that any neuron model describes the fungus, or that the drop trains are Type I or Type II rhythms. The model PRCs
  are the models', and the type flips with the coordinates;
- that the rec 6 correlation is a phase response. It is a correlation, explainable by drift, noise or onset
  placement;
- anything about MJu26a's oscillation or seq 122. Neither is a train under the chain rule. Using them needs a
  detector chosen for them, which is a judgement the stop rule kept out of this run;
- anything from Hindmarsh–Rose: it was not fitted.

## What was cut, and the run times

**Cut:**
- **seq 122 and MJu26a:** not trains under the rule (5 and 1 events).
- **Hindmarsh–Rose:** the model and the burst rule are built and tested (`hindmarsh_rose.py`), but it was fitted
  nowhere. The rule fires only on rec3_490_540h_ext, whose "bursts" are 19 irregular groups of 1–58 drops with
  periods of 1.2–20 h. It was cut, first on the prompt's list, as irregular groups that a periodic bursting orbit
  cannot represent.
- **Null draws for the slow models:**
  - in A, 3 per kind instead of 10 or 5;
  - in B, draw 0 only (as B3), and in the main run only where the real ratio was below 1. The supplement then
    covered rec 542, rec 6 and part of seq 20 before it was stopped; the other 128 slow-model null sets were not run.
- **PRC base points:** 100 instead of run_ch10's 150.
- **Izhikevich:** no adjoint and no delay-coordinate PRC (it is a hybrid model).

**Added beyond the prompt:**
- the time-warp null for the spontaneous estimate;
- an extension stability check in the chain rule (two successive widenings must agree).

**Run times** (2 worker processes, on a machine with ~1 GB of free memory):

| step | wall | CPU |
|---|---|---|
| regression check | 13 min | — |
| A: mean-cycle fits with nulls (1393 fits) | 71 min | 141 min |
| A: the real fits again, alone, so B and C could start early (identical results; file removed) | 19 min | 36 min |
| B: tracking (212 tasks) | 35 min | 67 min |
| B: supplement (34 of 162 remaining slow-model nulls, then stopped) | 21 min | 42 min |
| C: model PRCs, spontaneous estimate and return maps | 11 min | — |
| C: spontaneous estimate again, with the time-warp null | 6 min | — |

## Files

- **Code:** `Pipelines/fhn/`
  - `van_der_pol.py`, `morris_lecar.py`, `hindmarsh_rose.py`, `empirical_prc.py`;
  - `oscfit.py` (the shared planar-oscillator fit, PRC bundle, Type call and Izhikevich PRC; not in the prompt's
    list, so that the three model modules share one fitter);
  - `run_long.py`, `long_figures.py`.
- **Tests:** `tests/test_fhn_van_der_pol.py`, `test_fhn_morris_lecar.py`, `test_fhn_hindmarsh_rose.py`,
  `test_fhn_empirical_prc.py`, `test_fhn_run_long.py`.
- **Data and figures:** `docs/thesis/data/ch10_fhn_long/`.
- No existing `Pipelines/fhn/` module was edited.
