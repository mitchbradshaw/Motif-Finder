> Filed by the manager session, 2026-10-14 09:19 — the final message of critic agent `a5c440b67361d69dd` on branch
> `worktree-agent-acd4686fda90646ab` (04948e3..8075b8d), verbatim.

## Critic report: W2-D `catalogue.snippets` (branch `worktree-agent-acd4686fda90646ab`, 04948e3..8075b8d)

### 1. In plain words
The block does what it says. It finds the few typical one-hour pieces of a recording and colours every hour by the piece it most resembles. The rewritten distance engine is faithful to stumpy and in fact more accurate. On a 24–120 h span of pure coloured noise it correctly says "only one kind of behaviour". The weak point is the "how many kinds?" rule, which judges with a fixed cut. Think of a fixed bar height in a high-jump contest whose ground level moves with the length of the recording:
- **Short spans (12–14 h):** noise clears the bar and is reported as two kinds of behaviour.
- **Long spans (72–120 h):** a real but brief behaviour (8–12 h of 120 h) fails to clear it.

The template also inherits a pre-existing detrend bug: a single missing sample blanks the whole recording.

### 2. Verdict
**Merge after fixes.** Findings 1 and 2 are the fixes. Finding 3 must be fixed before the *template* ships, but the fix belongs in another file.

### 3. Findings

**1. Blocker: the knee finds k > 1 in stationary coloured noise on short spans.**
- Where: `Working/Detection/matrix_profiling/snippets.py:123` (`KNEE_MIN_CHANGE = 0.25`) and `:387` (`knee`).
- What is wrong: `change_k` on a null scales with the number of pieces W. Each added snippet zeroes about 1/W of the area at its own position, so the 0.25 floor is only safe for W ≳ 16. The block accepts W = 12 (`2·k_max`), and the smoke suggestion says "≥ 12 h".
- How I showed it: `knee.py`, which runs the template's 6 h rolling-mean detrend, then 1 h pieces, then `find_snippets(k=0)`:

  | Rate | Span | Null | Runs with k > 1 | max change_k |
  |---|---|---|---|---|
  | 1 Hz (real scale) | 12 h | detrended random walk | **6/12** | up to 0.349 |
  | 1 Hz | 12 h | AR(1) φ = 0.999 | 1/12 | up to 0.348 |
  | 1 Hz | 14 h | random walk | 1/10 | up to 0.279 |
  | 1 Hz | 14 h | AR(1) φ = 0.999 | 0/10 | 0.251 (on the floor) |
  | 0.1 Hz proxy | 12 h | random walk | 12/30 | up to 0.39 |
  | 0.1 Hz proxy | 12 h | AR(1) φ = 0.999 | 8/30 | — |
  | 0.1 Hz proxy | 12 h | AR(1) φ = 0.9995 | 11/30 | — |
  | 0.1 Hz proxy | 12 h | pink noise | 11/30 | — |
  | 0.1 Hz proxy | 16 h | random walk, AR(1) | 0/30 | up to 0.239 |

  - At 24 h or longer the floor holds everywhere I tried (0 false positives). The nulls were AR(1) φ = 0.99, 0.995, 0.999 and 0.9995 at 1 Hz, a random walk, AR(1) on a slow drift, pink noise and AR(1) plus white noise, at 24, 48 and 120 h, detrended and raw. The largest change_k was 0.226 (random walk, 24 h) and 0.09 at 120 h.
  - Real 1 Hz at 24 h agrees: max change_k 0.164 (random walk), 0.133 (AR 0.999), 0.095 (drift).
- Fix, either of:
  - Make the cut relative to the curve's own tail, e.g. accept the knee only if `change_k ≥ c · median(change_{k+1..k_max+1})` with c ≈ 3, which works at every W I tried.
  - Or raise the minimum for automatic k to about 24 pieces, refusing or forcing a fixed k below that in words.

  Add a 12 h null test at k = 0.

**2. Should-fix: the same absolute floor misses a real minority regime on long spans.**
- How I showed it: `minority.py`. Drops with an 8 h slow-wave stretch, drift added, then detrended:

  | Span | Minority | k | change_2 | Background change_3+ |
  |---|---|---|---|---|
  | 48 h | 8 h | 2 (correct) | 0.37 | — |
  | 72 h | 8 h | **1** | 0.237 | — |
  | 120 h | 8 h | **1** | 0.14 | ≈ 0.02 |
  | 120 h | 12 h | **1** | 0.21 | ≈ 0.02 |
  | 120 h | 24 h | 2 | 0.41 | — |

  The 120 h runs were 3/3 seeds each. The 120 h minorities still stand out 7–10× above their own background. The researcher's dense stretches are 30–100 h within 3–5 day spans, so this matters.
- Fix: the same relative rule as finding 1 fixes both.

**3. Blocker for the template (pre-existing code, outside scope): one NaN blanks the whole recording.**
- Where: `Working/Preprocessing/detrend.py:18–30`. `_rolling_mean` uses a cumsum.
- How I showed it: `quiet.py`. One NaN at sample 100 gave 17 280 of 17 280 NaN after `rolling_mean`. Snippets then refuses ("all NaN"). One NaN at hour 30 gave 21 −1 windows.
- Status: the implementer found this. Their report says "every later sample", but in fact every sample is lost. The template description understates it ("spreads a NaN").
- Fix: a separate ticket, a NaN-aware rolling mean (cumsum over `nan_to_num` with a count cumsum). Correct the FLUSS docs at the same time. Do not ship `recording_snippets` or `fluss_regimes` on real data before that.

**4. Should-fix: the paper does give a knee rule, and the block deviates from it without saying so.**
- Where: `snippets.py:72–73` ("The paper takes k 'at the knee' … without a formula") and report §3.5.
- What is wrong:
  - The paper (§III.B, read from the authors' 10-page PDF) says a small change_k means "adding the kth did not add much explanatory power; thus, we should use a value of k corresponding to a peak". That is k = argmax change_k.
  - The implementer's "largest drop change_k − change_{k+1}" changes the outcome on the acceptance set itself. Over seeds 0–3 the paper's peak rule gives **k = 2** every time (for example change_2 0.425 vs change_3 0.413). The block's rule gives 3.
  - The paper also has no k = 1 outcome (its Fig. 13 marks change_1 "undefined"); the floor is an addition.
  - Primary-sources §13c says only "k at the knee", so the research file is incomplete here too.
  - The block's rule is the better one for this data; it is just not the paper's.
- Fix: name both as adaptations in the docstring, with the measurement that justifies each. Ask the manager to correct §13c.

**5. Should-fix: the quiet-regime acceptance test was changed, and the finding behind the change is right.**
- How I showed it: `quiet.py`, using the prompt's own order (drops / quiet AR(1) / wave, ×2).
  - Auto k = 2, with change_2 ≈ 0.30–0.32 and change_3 ≈ 0.07.
  - At forced k = 3, agreement is 0.69–0.73.
  - The quiet hours are absorbed into the drops label with sporadic flicker, e.g. `222222221222212111…`.
- Is the finding right: yes. Z-normalised MPdist has no amplitude, so pure noise has no shape of its own. The paper says the same about random-walk distractors (§IV.B: random-walk subsequences "tend to be closer" to anything).
- Is the changed test fair: it is fair for what the block can do. "Quiet with brief spikes" still differs from the others by shape. But it no longer tests the spec's literal claim, and on fungal data the most common regime contrast is quiet versus active.
- Fix: keep the spiky test. Add the pure-quiet case as an explicit *expected-limitation* test (assert k ≤ 2, document it). Make the template description say plainly that quiet and active periods differing only in amplitude are not separated. The adapter description already says so.

**6. Nit: the exemplar acceptance item is true by construction.**
- Where: `snippets.py:584–587`.
- What is wrong: the snippet's own window is force-relabelled, so "the exemplar is one of its label's windows" cannot fail. `n_exemplar_relabelled` was 0 in every run I made (4 regime seeds, 3 quiet seeds), so it is harmless today.
- Fix: assert `n_exemplar_relabelled == 0` in the regime test, and show a non-zero count in the summary.

**7. Nit: `runs` and `runs_by_k[str(k)]` can disagree.**
- Where: `snippets.py:589–598`.
- What is wrong: `runs_by_k` skips the exemplar override. They matched in all my runs (relabelled = 0).
- Fix: say so in the meta rule. The manager should use `runs_by_k` on both the real recording and the surrogates, which is consistent either way.

**8. Nit: a constant span reports a misleading reason.**
- Where: `snippets.py:396–397`.
- What is wrong: a constant span gives areas of 0, change_k = inf and the drop = nan. The reason then reads "too few snippets to read a knee".
- Fix: say "constant signal: every distance is 0".

**9. Nit: the memory notes understate the peak.**
- What is wrong:
  - The real peak is about D + qt_rows (the same size as D) + the 1.5 GB kernel budget. Measured peak working set: 1.80 GB at 48 h and 1.95 GB at 72 h. At 7 days that is about 3.3 GB.
  - At the 2 GB `PROFILE_MEMORY` edge with short pieces it is 5.5–6 GB: `greedy_snippets` copies `D[:, cols]` and allocates a W×P temporary per iteration.
- Fix: state the true peak, or count 2·D in the refusal.

### The manager's six questions

**1. The rewritten MPdist kernel: it equals stumpy and is often more accurate.** `equiv.py` compared against `_get_all_profiles` at mpdist_percentage 0.05 and 0.3.
- Agreement to ≤ 3.5e-11 on: AR(1) φ = 0.99, drift + noise, odd m (101 with s 37; 77 with s 76), s = m − 2, s = m (odd), quantised plateaus, an interpolated ramp, n not a multiple of m, and a constant tail.
- Agreement to 2.8e-11 on a long series (n = 60 000, m = 60), so the streamed recurrence does not drift.
- Greedy indices and areas equal `stumpy.snippets` (relative error 2e-15).
- Two cases differ, and stumpy is the one that is wrong:
  - **Volt-scale offset** (AR(1) × 1e-3 + 1000): stumpy is off by 1.8e-3. The rewrite matches a brute-force float64 computation to 4e-14, because of its global standardisation.
  - **Sub-pieces with σ ≈ 1e-9** (3 of 21 015 entries): both are inaccurate. Brute force gives 5.92; the rewrite 5.74; stumpy 0.00.
- Memory claim, true: stumpy holds a j × (n − s + 1) matrix, 1.59 GB per piece at 24 h. Speed: stumpy took 1179 s against the rewrite's 35 s on the n = 60 000 case (loaded machine).

**2. The knee and its floor.**
- "The paper gives no formula" is false; see finding 4.
- The floor is robust for spans of 24 h or more at real scale (1 Hz, 6 h detrend, AR(1) φ 0.99–0.9995, random walk, drift: no false k > 1).
- It fails at 12–14 h (finding 1, blocker) and is too strict at 72–120 h (finding 2).

**3. The changed acceptance test:** the finding is right and the test is fair for the block's real ability; see finding 5.

**4. The `Working/block_cost.py` warm-up:**
- No textual or behavioural conflict with 8ee3cd4. That commit warms stumpy inside `matrix_profiling/cost.calibrate`; this branch adds an optional warm-up to the generic `block_cost.calibrate`. They are two models in two modules, and the idea is duplicated rather than shared.
- Integration gap: on main, `webui/server/chain.py::route_local` calibrates only the matrix-profile model (`_uses_mp_cost`). An uncalibrated snippets step is therefore routed as `unknown` and runs, capped only by `max_span_samples` (7 days, about 20 min).
- Suggested fix at merge: have `route_local` also call `block_cost.calibrate([name])` for unknown `block_cost` models. Or have snippets estimate from the MP cost model.

**5. `numba.set_num_threads` with concurrent chain jobs: safe.**
- The threading layer here is **tbb**, where `set_num_threads` is thread-local.
- `threads.py` ran two snippet runs, one `stumpy.stump` and a thread calling `set_num_threads(2)`, all concurrently. Results were bit-identical to the serial reference, other threads still reported 16, and there was no crash.
- Residual risk only if numba falls back to the workqueue layer, which is not thread-safe.

**6. Run-length statistic:**
- Arithmetic is correct. `shuffled_mean = n/(1+(n−1)(1−Σp²))` matched 20 000-shuffle simulations to within 2 % for counts [16,16,16], [40,8], [20,3,1], [100,10,10] and [12,12]. It is closer to the simulated E[mean run] than the exact n/E[R] is.
- On every null, `runs_by_k["3"].ratio` stayed between about 1.05 and 1.82. Of 245 null runs, 233 were ≤ 1.48; the 1.82 was one 12 h pink-noise run.
- Fairness: the statistic is fair **only at a fixed k against phase-randomised surrogates**, as the implementer says.
  - At auto k, a surrogate that picks k = 1 has a single run, so it can never be beaten.
  - Shuffled labels are not a null for coloured data: adjacent windows' votes share half a piece of data.
  - Use `runs_by_k["3"]` (or ["2"]) on the real recording and each of the 20 surrogates.
  - The span must be ≥ 24 h, or finding 1 also contaminates the surrogates' k.

### Other checks (pass)
- **Test-first:**
  - The first commit 7a754f0 touches only `tests/`, and its message carries the red summary.
  - The second red commit, 93a9279, is tests-only.
- **Scope:**
  - Out of scope: `Working/block_cost.py`, which is additive and declared.
  - `test_block_standard.py` touched only for COSTED, which the prompt hands over.
- **Standards:** no UI imports, a thin adapter, sensible ParamSpec bounds, `page_name`, category, `estimate` and `max_span_samples`. `meta` is honest about NaN counts and refusals.
- **Edge cases:**
  - Refused in words: an all-NaN span, too few pieces (11 of 12), every window more than 50 % NaN.
  - Handled: a leading NaN plus a 2 h gap gives −1 windows; an inf sample is filled.
  - Interpolated gaps of 20–29 min did not produce spurious k (8 seeds, 24 and 48 h).

### 4. What I ran
- Branch gate: the 3 snippets test files plus `test_block_standard`, `test_adapter_spec`, `test_import_boundaries`, `test_templates` and `test_end_to_end` gave **277 passed** in 81 s.
- Experiment scripts are in `C:\Users\mmebr\AppData\Local\Temp\claude\C--Users-mmebr-Documents-CNN\9b41764a-ced2-4e05-857c-547103bce7fb\scratchpad\critic_w2d\`, results inline above:
  - `equiv.py`, `brute.py` (kernel equivalence and ground truth)
  - `knee.py`, `summ.py` (null sweeps, about 330 runs: 0.1 Hz at 12/16/24/48/120 h, 1 Hz at 12/14/24 h)
  - `minority.py`, `paperknee.py`, `quiet.py`, `edges.py`, `gap.py`, `runs.py`, `threads.py`
  - `peak.py` (timing and memory)
- Timings at 1 Hz with m = 3600, on a machine loaded by other agents:
  - 24 h: 34–45 s per null run.
  - 48 h: 76 s.
  - 72 h: 206 s (the implementer reported 228 s).
- Paper: the authors' 10-page PDF (cs.ucr.edu/~eamonn/Time_Series_Snippets_10pages.pdf), §III.B and §IV.B.
- I edited nothing in the repo or the worktree, and nothing touched `DATA/`.
