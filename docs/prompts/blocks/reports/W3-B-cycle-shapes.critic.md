> Filed by the manager session, 2026-10-14 23:20 — the final message of critic agent `a5f632b4352ec10f8` on branch
> `worktree-agent-a7834e530174e1643` (`8ac94c3`, `b94881b` on `01cb8c3`), verbatim.

## Critic report: W3-B `interrogation.cycle_shapes` (worktree `agent-a7834e530174e1643`, commits 8ac94c3 red, b94881b)

### 1. In plain words
The block cuts every drop-to-drop cycle, stretches the cycles to one length and sorts them into shapes. On clean synthetic chains it finds the right shapes and plateaus. It has three problems:
- **It invents two families in pure noise.** On a random-walk background with chain-like event timing it reports "K = 2" in about half the runs. Z-normalising noise cycles turns them into "hump up" and "hump down", and neither gate can tell that apart from two real shapes.
- **The SigClust gate is broken by its noise floor, not by the data.** It rejects a true one-cluster Gaussian 12 times in 12.
- **On a chain that fills its whole span, the "is this better than noise?" test breaks down.** With no quiet stretch to sample, it compares the cycles with misaligned cuts of the same chain. A perfect sharkfin chain then reads "no better than noise" on eq. 17.

### 2. Verdict
**Merge after fixes.** The fixes are local: the K gate, the fallback verdict, and exposing the per-draw null values in meta.

### 3. Findings, most severe first

**B1 — blocker. No-structure chains get K = 2 on random-walk backgrounds** (`Working/interrogation/cycle_shapes.py:601-665`, `_split_modes` 570).
- **Measured on stacks:** the block's own `prepare_cycle` plus `choose_groups(seed=0)` (`exp_size2.py`), 10 data seeds each. Rate of K = 2 at the defaults:
  - random walk, regular times (lognormal CV 0.3): 4/10 at n≈95 and 5/10 at n≈378;
  - random walk, Poisson times: 2/10 at n≈205;
  - AR(1) φ 0.95 and 0.99: 0/60.
- **Confirmed through the full `cycle_shapes`** (`exp_full_rw.py`, 120 cycles on a random walk): K = 2 in 2 of 6 seeds. The summary then reads "K = 2 (SigClust p 0.010) … 57 change point(s)". The keys are marked `~noise_like`, so Intervals is protected, but K, the change points and the order test are reported as findings.
- **Cause** (`exp_sign.py`): the 2-means split is the sign of PC1.
  - The two group means correlate at −0.82 to −0.97.
  - The split agrees with sign(PC1) at 0.67–0.98.
  - Z-normalising a cycle dominated by one smooth component maps it to roughly ±that component, which really is two modes.
- **The gate cannot see this.**
  - The mode test compares the projection with *uniform* samples, and its null draws do not re-select a direction.
  - On true Gaussian clouds with smooth covariance this was harmless: 0/12 rejections at n = 60, 200, 400.
  - It cannot know that z-normalised noise is sign-bimodal.
  - SigClust rejects anyway (B2), so the mode test alone carries K.
- **Fix: calibrate the split on the background null the block already draws.** Run 2-means on each of the 20 background draws. Claim K > 1 only if the real 2-means cluster index is below every draw's, and keep the mode test against one family that varies. Prototype (`exp_fix.py`):
  - **noise:** passed 0/18 (random walk and AR(0.99), n 95–387);
  - **one family that varies:** the plateau drift passes the background test on rw/AR/drift, but the mode test keeps it at K = 1 (p 0.96–0.99);
  - **two shapes:** passed in every case with background or AR(1) noise up to 30 %, at 50/50, 80/20 and 90/10, and n = 20;
  - **n = 30 at 30 % noise:** AR(1) and drift now reach K = 2, where the shipped gate said K = 1. On the random walk at n = 30 the mode test still fails (p 0.10).
- **Not enough:** SigClust without the floor plus the mode test still gave K = 2 on 3 of 5 random-walk stacks at n≈380.
- Add a multi-seed random-walk no-structure test. The shipped test uses one seed per background, which is why it passed.

**B2 — blocker (correctness of a named method). The SigClust floor makes it reject a true Gaussian** (`sigclust`, 520-521).
- σ_N² = (MAD of all centred entries / 0.6745)² is Liu et al.'s estimate for sparse HDLSS data, where most coordinates are pure noise.
- On z-normalised smooth cycles every coordinate carries the curve, so σ_N² ≈ the per-coordinate total variance. Flooring every eigenvalue up to it inflates the null's total variance by 1.4–2.1× on our stacks (`size.jsonl`: "floor x var").
- **Known-answer check** (`exp_gauss2.py`). A true one-cluster Gaussian with AR-Toeplitz covariance, d = 256, 12 runs each; how many times each version rejects:

  | | n = 60 | n = 200 | n = 400 |
  |---|---|---|---|
  | block's SigClust, φ 0.97 | 0/12 | 12/12 | 12/12 |
  | block's SigClust, φ 0.995 | 5/12 | 12/12 | 12/12 |
  | sample eigenvalues, no floor | 0/12 | 0/12 | 0/12 |
  | true eigenvalues | — | 0–1/12 | 0–1/12 |

  - My Huang et al. 2015 soft threshold, built on the same MAD σ_N, also rejected 12/12: the σ_N estimate is the problem, not hard versus soft.
  - On a spiked Gaussian where most coordinates are noise, the block's SigClust behaves (0/20 rejections, `exp_gauss.py`).
- So "SigClust rejects pure noise everywhere" is an implementation issue. The docstring's conclusion that "our cycles are never one Gaussian" (lines 105-111) is wrong as stated.
- Without the floor, SigClust's p was 0.06–0.83 on most noise stacks. It still rejected some random-walk stacks at n≈380 (p 0.01) and AR(0.99) at n = 1,000, so part of the rejection is real non-Gaussianity.
- **Fix:** replace the gate (B1). If SigClust stays as a reported number, drop the floor and say why in the docstring.
- `test_a_plateau_that_lengthens…` asserts `sigclust p < 0.05` (test_cycle_shapes.py:136). It pins the defect and must change with the fix.

**B3 — blocker for the manager's evaluation. On a span the chain fills, the background null is a misaligned-copy null, and eq. 17 cannot clear it** (`cycle_shapes.py:1005-1040`, `background_null.py`).
- **Setup** (`exp_bg.py`): 80 h dense chains, one drop every 25–45 min (136 cycles), detector spans covering the drop and floor only (52 % of a sharkfin cycle, 10 % of a trough cycle).
- **Sharkfins with no margins:**
  - fallback share is 1.00; 38.6 h is "free", but in pieces of about 48 % of a cycle, so no cycle-length window fits;
  - the pseudo-cycles are therefore random-phase cuts of the chain, i.e. shifted copies of the same shape, which are themselves low-rank;
  - eq. 17 on AR(1): real 0.840 against background median 0.842 at 15 % noise (z 0.6), and 0.895 against 0.891 at 30 % (z −1.8);
  - the broad hump: 0.891 against 0.888 (z −2.5);
  - σ² still passes (0.21 against 0.475);
  - result: a perfect chain reads "no better than noise", keyed `~noise_like`.
- **With 10 h quiet margins** (rec 3's 490–540 h layout):
  - fallback 0; 100 % of sharkfin windows and 84 % of trough windows come from the margins;
  - z 24–68 on eq. 17, a clear pass;
  - the background median equals a separate pure-quiet null (e.g. 0.927 against 0.928).
- **Troughs, no margins:** fallback 0.26, the rest cut from in-chain recoveries. eq. 17 z 8.5 at 15 % noise but 2.4 (a fail) at 30 % on AR(1).
- **The warning is misleading:** it says "too little event-free signal (138,930 s free)" when the free signal is ample but fragmented.
- **Fix:**
  - when fallback_share > ~0.5, set the verdict to `tested: False` with the reason, key the groups `~untested` rather than `~noise_like`, and word the warning "no free stretch as long as a cycle; pseudo-cycles are random-phase cuts of the chain";
  - in the evaluation, use spans with quiet margins of several hours each side. Rec 3, rec 6, rec 542 and rec 2 have them; rec 543's 370–490 h span is nearly all chain and will fall back.

**S1 — should-fix. The per-draw background values are not in meta** (`_null_summary` 789).
- Meta carries median, p05, min, spread and draws, plus `below_every_draw` and `below_every_draw_squared`. It does not carry the 20 values.
- **Fix:** keep `bg17` and `bgsq` as lists, e.g. `whole["nulls"]["background"]["eq17"]["values"]` and `["squared"]["values"]` (json_safe turns NaN into None), and the same per group.
- Note that draws with fewer than 2 preparable windows are silently dropped (`continue` at 1019). Count them, so "20 draws" is checkable.

**S2 — should-fix. The per-group background null favours the group, mostly on σ²** (1069-1077).
- **Setup** (`exp_group.py`): 120 noise cycles on rw/AR/drift, a forced 2-means split, groups judged against random subsets the block's way.
  - eq. 17 `beyond_noise`: 1/36 groups; σ² `beyond_noise_squared`: 9/36; σ² below every draw: 17/36.
  - Against a selection-matched null (2-means on each background draw, lower group matched to lower), all of these fell to 0/36 except below-every-draw: eq. 17 3/36 (B3 explains that level) and σ² 2/36.
  - The whole-stack verdict was false in 18/18 on eq. 17 and on σ² (no selection).
- **Fix:** match the selection, by running the same 2-means on each background draw. Until then σ² heads the summary, so do not show a per-group σ² "beyond noise".

**S3 — should-fix. eq. 17 is the weak half of the manager's verdict on real-like chains.**
- Besides B3: in the template run with under-detection (below), a trough chain of 83 cycles read σ² 0.37 against background 0.59 but eq. 17 0.87 against 0.88, so "no better than noise".
- The manager's rule (σ² AND eq. 17 below every draw) will fail on chains that σ² clearly passes. Flag this to the manager and researcher; it is not a code change.

**S4 — should-fix. The gap rule loses true cycles at realistic jitter** (`_local_median` with 1.6× / 0.4×; `exp_gap.py`, 300 chains per row). The rule uses event times only, so noise colour does not enter it.

| jitter CV | 0.2 | 0.3 | 0.4 | 0.5 |
|---|---|---|---|---|
| true cycles lost (30, 100 and 300 cycles; drift makes no difference) | 1 % | 5.5 % | 11 % | 17.5 % |

- At CV 0.5 with 30 cycles, the 90th percentile is 27 %.
- Correlated log-intervals (AR φ 0.8): 0.5 % lost at CV 0.3, 4.9 % at CV 0.5.
- The trade-off for catching a missed detection (two cycles merged into one):

  | factor | 1.6 | 1.8 | 2.0 |
  |---|---|---|---|
  | missed detections caught, CV 0.3 / 0.5 | 80 % / 69 % | 62 % / 58 % | 44 % / 46 % |
  | true cycles lost, CV 0.3 / 0.5 | 4.8 % / 13.6 % | 2.2 % / 9.3 % | 0.8 % / 6.1 % |

- The lost cycles are the longest ones, a bias against long-plateau cycles.
- **Fix:** keep 1.6, but add a meta warning plus a summary note when `gap_long` exceeds 10 % of cycles. Put this table in the docstring in place of the "60 % jitter" sentence.

**S5 — should-fix. Chains of 12–19 cycles can never split** (`min_size` check at 633). With rec 2's 12 cycles, K = 1 is by construction. Say so in the sequence's reason and the summary: "a split needs ≥ 2 × min_cycles".

**S6 — should-fix (integration). An unbound waveform cuts from x.**
- The UI has no way to bind a side input; only templates can.
- So a hand-inserted block always cuts from the 600 s-detrended x, which the block's own test shows misreads sharkfins as troughs.
- The insert modal shows "needs waveform" as if it were mandatory.
- **Fix:** add a meta warning when unbound: "cycles cut from the chain's signal; if the detector ran on a short-detrended trace, bind waveform". Also make `chain.py:56` pass `required`, which the implementer already proposed.

**N1 — nit. Several trains give non-integer exemplar keys.**
- `exemplar_events` keys become "t0:1" with several trains.
- `serialize._event_families` sorts the keys with `int(k)` and checks them against a `family` column, so W3-F cannot reuse that path as is.
- Members are correct (I checked the code path and the test).

**N2 — nit. The cost estimate cannot see a dense detector** (`_estimate` assumes one cycle per 1,800 s). See Q7 for the figures; the absolute cost stays under a minute.

**N3 — nit. The side-input contract change has no unit test** in `tests/test_side_inputs.py` (optional unbound is skipped; required unbound still raises). It is only exercised through the template.

### Answers to the manager's questions
1. **The mode gate.** The uniform is safe for Gaussian clouds, even with the direction chosen on the same data: 0/12 rejections at n 60–400, and 0/20 on spiked clouds. It is not safe for z-normalised noise cycles, which are genuinely sign-bimodal. The null draws do not re-select a direction. Size and power at the defaults:
   - **No structure:** K = 2 in 4–5 of 10 random-walk chains and 0 of 60 AR(1) chains (B1). The 1,000-cycle random-walk chain also gave K = 2.
   - **One family that varies:** plateau, amplitude and period drift gave K = 1 in 27 of 27.
   - **Two shapes, 120 cycles:** K = 2 with ARI 0.93–1.0 at 15–30 % noise on AR(1) and drift, at 50/50, 80/20 and 90/10. On the random walk ARI was only 0.72–0.84 at 30 %.
   - **50 % noise:** K = 1 on AR(1). Drift: 50/50 gave K = 2 (ARI 0.78) and 80/20 gave K = 1. Random walk: K = 2 (ARI 0.46–0.71) except at 90/10.
   - **Few cycles:** n = 20–40 at 15 % gave K = 2. At 30 % on AR(1) or drift it gave K = 1, because SigClust fails at small n. Rec 2's 13 events can never split (S5).
2. **SigClust.** The rejection is an implementation issue, the MAD floor (B2). A direct reimplementation on a known Gaussian gives 0/12 rejections without the floor and 12/12 with it. The rank truncation is conservative, not the cause.
3. **The verdict rule.**
   - Whole stack on noise: 0 false passes in 24 runs (18 forced-split stacks and 6 full runs). Real-like chains with margins: z 8–68.
   - Per group, the random-subset null favours the group: σ² 9/36 false passes (S2).
   - The per-draw values are not exposed; add `values` lists (S1).
4. **Dense chains.** Fallback is 100 % for sharkfins and 26 % for troughs. The verdict then means "phase-locked versus random phase", and eq. 17 cannot clear it. This is not a fair floor for "real chains clear it easily". With 10 h margins the pseudo-cycles come from the margins, 84–100 % of them (B3).
5. **The side-input change.**
   - The default `required=True` leaves every existing block unchanged.
   - Recipe hash: an unbound side input normalises to `{}`, so the hash is unchanged.
   - `webui/server/chain.py` never refused unbound side inputs, required or optional; it only lists them on the card. The executor refuses an unbound required one at run time, and an unbound optional one now runs on x.
   - Tests: side_inputs, execution, recipes, adapter_spec, block_standard and event_windows pass (conda). 7 webui test files pass under the venv (98 passed).
6. **The gap rule.** 5.5 / 11 / 17.5 % of true cycles lost at CV 0.3 / 0.4 / 0.5, independent of chain length and drift (S4).
7. **The template end to end** (`exp_e2e.py`, `exp_cost.py`; CPU ~99 %, 4 threads; calibration k written to scratch):
   - **1 Hz, 106 h, 160 events:** block 6.3 s against an estimate of 9.0 s. K = 2: sharkfin floor 0.59 and half recovery 0.64; trough half recovery 0.05. Beyond noise. Peak RSS 257 MB.
   - **10 Hz, 30 h, 48 cycles:** 2.9 s against an estimate of 1.7 s. Peak 333 MB.
   - **Under-detection (10 % AR(1) noise):** 116 of 160 events found. Sharkfins split into trains of 15 and 6 cycles; 8 gaps; the main 83-cycle trough train was `~noise_like` on eq. 17. Nothing says "the detector missed events". The omitted counts are the only clue, and the user must notice them.
   - **Imports:** 7.7 s, not timed by the estimate (correct). A fresh second run took 3.2 s against 3.7 s.
8. **Scope and test cost.**
   - Six bookkeeping names: justified (decisions and geometry, as `family_distance` and `anchor_offset` are).
   - The changed `BOOK` set is stated in the red commit's message, and the adapter count change in the green commit's.
   - Test-first verified: 8ac94c3 touches only tests/.
   - Test cost: the full run took 398 s; the 1,000-cycle test alone 58 s; the three 400-cycle Poisson tests 12–21 s each; each two-family fixture about 18 s.
   - Recommendation: once B1 is fixed, the cost falls by itself (100 SigClust draws times bisection replaced by 20 background 2-means). Keep one 1,000-cycle no-structure test, on the random walk (the background that fails), and make the random-walk no-structure test multi-seed on about 100 cycles rather than more 400-cycle runs.

### Five axes (other)
- **Spec:**
  - Met: every acceptance item on the implementer's seeds; 1 Hz = 10 Hz (ARI 1.0); NaN (> 10 % omitted, less filled); too few cycles; exemplars are members; `cycle_stack` ≤ 200 × 128, sampled and seeded.
  - "No structure → K = 1" fails across seeds on the random walk (B1).
- **Paper:** the departures are named: anchors as the phase, bisection instead of Calinski–Harabasz, chord from the samples before each anchor, unaligned clustering. The SigClust σ_N departure from its sparse-HDLSS premise is not named and is wrong (B2).
- **Standards:**
  - Core and adapter are cleanly split; no global RNG (`null_rng` and seeded `default_rng` throughout).
  - Meta is JSON-safe; warnings reach the summary.
  - Out-of-scope files: `Adapters/base.py` and `Working/side_inputs.py`, both needed and reported.

### What I ran
- Conda: the block's 4 test files plus side_inputs, execution, recipes, adapter_spec, block_standard, event_windows, import_boundaries and templates: **377 passed, 7 skipped, 398 s**.
- Venv: test_webui_templates, routes, api, block_views, serialize, run_routing and job_estimate: **98 passed, 119 s**.
- Experiments, all in `…/scratchpad/critic_w3b/`, at most 4 processes after the manager's request:
  - `exp_gauss.py`, `exp_gauss2.py`: known-answer SigClust and mode gate;
  - `exp_gate.py`: 93 size runs and 48 power runs;
  - `exp_size2.py`: 120 runs at the block's seed;
  - `exp_full_rw.py`: full block on the random walk;
  - `exp_sign.py`: the sign-of-PC1 cause;
  - `exp_bg.py`: the dense-chain background null;
  - `exp_group.py`: per-group null favour;
  - `exp_gap.py`, `exp_gap2.py`: gap rule sweep;
  - `exp_e2e.py`: template end to end, estimate and memory;
  - `exp_cost.py`: 115–1,500 cycles;
  - `exp_fix.py`: prototype of the background-calibrated gate.
