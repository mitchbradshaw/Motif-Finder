> Filed by the manager session, 2026-10-14 23:00 — the final message of critic agent `a03f242747d328696` on branch
> `worktree-agent-a67442d9e04015d6a` (`2aedf23`, `99b043f` on `01cb8c3`), verbatim.

## W3-A critic report: `catalogue.multiscale_entropy` and the `complexity_fingerprint` template
(worktree `agent-a67442d9e04015d6a`, commits `2aedf23` red, `99b043f` green, base `01cb8c3`)

### 1. In plain words
The block works. It gives each window a complexity curve (how surprising the signal is at each level of blur), the counts are exact, and making it cheap to compute costs almost nothing in accuracy. Four things go wrong around it:
- **The template's 72 h window gives no curve on 24 h spans.** Two of the three spans you declared for the evaluation are 24 h, so the template cannot pass its own evaluation.
- **The collapse guard misses part of the √t collapse it was built for, and its advice is wrong.** It misses most collapsed scales when the drift is a smooth trend, and it tells users that switching to a MAD-based r fixes drift. It does not.
- **Two columns that aren't complexity reach clustering.** One is in storage units; the other is a drift measure.
- **Your declared statistic has a flaw.** With plain phase randomisation, any signal whose values are not bell-shaped (Gaussian) "beats" its surrogates, even when its dynamics hold nothing beyond a coloured process (a "linear process").

### 2. Verdict
**Merge after fixes.** Before any real data are run, the evaluation's surrogate needs correcting (Q6) and the template's window needs deciding (Q1).

### 3. Findings, most severe first

**F1. Blocker for the template: 72 h windows give "no window" on 2 of the 3 evaluation spans.**
- Where: `tests/test_template_complexity_fingerprint.py:74`.
- What: the ledger judges rec 1 and rec 3 on 440–464 h, which are 24 h spans. `sliding_windows` refuses a span shorter than its window, so both are "no window", and the template cannot reach "≥ 2 of 3".
- Fix: either set `window_s` to 24 h (Q1 has the trade-off), or move the ledger's spans to ≥ 72 h now, before any data are seen.

**F2. Should-fix (serious): the collapse guard misses collapsed scales, and its advice is wrong.**
- Where: `Working/Catalogue/multiscale_entropy.py:333-336` (the rule) and `:562-565` (the warning text).
- Measured: a raw AR(1) φ 0.97 under a smooth drift, with r from SD, has entropies of 0.12–0.22 at scales 4–9. The same signal through the template gives 1.7–2.2 there. ρ at those scales is only 2.2–3.7, so 6 of 9 collapsed scales go unflagged (72 h). On a raw random walk the guard flags 7 of 9 scales and misses 91 s and 174 s (0.18 and 0.28 nats, against 1.3 and 1.6 after the template).
- The warning says "Detrend upstream or use r_scale = mad". MAD does not help: the drifting window gives 0.043 with MAD against 0.044 with SD (ρ 7.7 against 7.5).
- Fix: see Q2. Judge inflation directly, and drop "or use r_scale = mad" from the warning.

**F3. Should-fix: unit-bearing and non-complexity columns reach clustering and classification as features, and left-out windows are clustered as if they were average windows.**
- Where: `Working/types/windowset.py:50-52`.
- `catalogue.cluster` used `mse_r` and `mse_drift_share` as features at its defaults (its `feature_names`).
- Two same-process datasets, one stored in V and one in mV: the silhouette of the storage-unit label is 0.177 with `mse_r` and 0.079 without it. So `mse_r` doubles how well the clustering separates by unit.
- Within one recording, `mse_r` alone splits a 3× louder half perfectly (0.57–0.61 against 1.74–1.92), although MSE itself is designed to ignore amplitude.
- A left-out window (gap) is an all-NaN row. `preprocess_window_matrix` median-imputes it, it is clustered like a typical window (it got label 2), and nothing says so.
- Fix:
  - add `mse_r` and `mse_drift_share` to `BOOKKEEPING_COLUMNS`;
  - have cluster and classifier drop all-NaN feature rows and count them (or have this block add a bookkeeping `mse_left_out` column those consumers honour). That is a small out-of-list change the manager should own.

**F4. Should-fix: the estimate under-runs whenever windows are shorter than 72 h.** Details in Q4. Fix: a conservative window rule.

**F5. Should-fix: interpolated data are invisible on the face.**
- A window with every other sample NaN (50 % of it filled by straight lines) is kept with no warning; `n_interpolated` appears only in meta.
- Fix: cap the missing fraction per window (e.g. a window more than 5 % filled is left out with its reason), and put the interpolated count in the warnings and the summary line.

**Nits.**
- RCMSE is exactly MSE wherever only one offset is pooled: 24 h at τ ≤ 4, 72 h at τ ≤ 13 (difference 0.000 measured). Only `meta["n_offsets"]` says so; the summary says "RCMSE". Add a rule line naming the scales where it equals MSE.
- A mostly constant channel with rare steps (MAD = 0, SD > 0) is left out as "flat". Say "MAD = 0" instead, or fall back to the SD.
- Window-length text renders as "0.166667 h" and "5.55556 h".
- `mse_ci` and the two slopes are linear combinations of the per-scale columns. In clustering they double-weight those directions; the 0.99 correlation filter catches only some of them.

### Answers to the manager's questions

**Q1. The 72 h window against 24 h.** Size and power of your statistic through the template (20 realisations × 20 draws each, 1 Hz). "Pure noise" is the four null rows (φ 0.97, φ 0.99, random walk, pink, all Gaussian):

| Case | 24 h span, 24 h window | 72 h span, 72 h window |
|---|---|---|
| AR(1) φ 0.97 | 1 / 20 beat | 3 / 20 |
| AR(1) φ 0.99 | 0 / 20 | 0 / 20 |
| Random walk (detrended by the template) | 3 / 20 (p ≤ 0.1 in 8 / 20) | 1 / 20 |
| Pink noise | 2 / 20 | 2 / 20 |
| **Pure noise, pooled** | **6 / 80 = 7.5 %** (expected 4.8 %) | **6 / 80 = 7.5 %** |
| Drops 5×SD on AR(1) | 19 / 20 | 20 / 20 |
| Drops 5×SD on random walk | 20 / 20 | 20 / 20 |
| Drops 2×SD on AR(1) | 2 / 20 | **8 / 20** |
| Scales defined | 7 (reach 48 s) | 9 (reach 174 s) |

- So 72 h buys reach and power against weak structure (40 % against 10 % at 2×SD). It costs:
  - windows per recording: S. commune 1 against 3; the other species 4–12 against 12–37; M2_aug 10 against 30;
  - no window at all on any span under 72 h, including the 24 h evaluation spans (F1) and every 4 h recording (24 h gives none there either).
- **Recommendation:**
  - The template defaults to 24 h windows (it works on the declared spans and on every species' channels).
  - Ship a second variant at 72 h for whole-recording fingerprints of ≥ 72 h channels, or let the description say "set window_s to the longest whole multiple of 24 h your recording allows".
  - If the manager prefers 72 h, the evaluation spans must change to ≥ 72 h before any data are run.

**Q2. The collapse guard.**
- **Cry wolf?** Not on every channel, but the threshold sits right inside the random-walk range:

  | Background (through the template) | ρ at 1 s | Flag at 1 s |
  |---|---|---|
  | AR(1) φ 0.95–0.99 | 0.46–1.06 | never |
  | Pink noise | 0.24–0.29 | never |
  | Detrended random walk | 3.5–3.8 | not on my seeds |
  | Drops on random walk | 4.2–4.5 | flags |

  So on random-walk-like real channels the 1 s flag is a coin toss. The implementer's test `test_a_detrended_random_walk_collapses_only_at_the_smallest_scales` passes on its seed (5); my seeds 1 and 2 sit at 3.5–3.7, so it encodes that coin toss.
- **Every collapsed scale of the √t case?** No (F2).
- **Separating drift from smoothness.** ρ judged against the window's phase-randomised copy does **not** separate them: the copy keeps the drift's spectrum, so ρ matches (3.63 against 3.23 for the random walk, 1.04 against 1.04 for AR(1) φ 0.99).
- What does separate them is **inflation** = spread(window as it arrives, the r rule's own spread) ÷ spread(the same window minus a 2 h rolling mean):

  | Window | Inflation |
  |---|---|
  | Every stationary or template-detrended background, 24 h and 72 h, 3 seeds each | 0.95–1.10 |
  | Raw random walk, SD | 4.0–8.4 |
  | Raw drops on random walk | 2.8–5.8 |
  | Raw AR(1) + drift, SD or MAD | 11.5–13.0 |
  | Raw pink noise | 1.11–1.22 |

  (AR(1) and pink noise did not collapse in the raw runs.)
- **Recommend:**
  - The collapse warning fires per window when inflation > 1.5 (r inflated by slow content), on every scale.
  - Keep ρ as an informational "smooth at this scale" figure in meta, not a warning.

**Q3. Unit-bearing columns.**
- Consumers at defaults (`Adapters/catalogue_cluster.py:60`, `catalogue_classifier.py:101`) drop only `BOOKKEEPING_COLUMNS`. They then z-score, drop columns more than 50 % NaN, and median-impute the rest.
- So `mse_r` and `mse_drift_share` are used as features, and a NaN row is imputed and clustered (F3).
- Join both columns to `BOOKKEEPING_COLUMNS`.
- An in-app cross-dataset clustering cannot happen today, because the block refuses Window pools. But a species table built from these columns would partly separate by storage unit (silhouette 0.177 against 0.079).

**Q4. The estimate.** The machine was 91–100 % loaded (other agents plus mine), so read the ratios:

| Case | Estimate | Actual | Actual ÷ estimate |
|---|---|---|---|
| 721 h, 1 Hz, 72 h windows (10 windows) | 65.2 s | 46.4 s | 0.71 |
| 721 h, 1 Hz, 6 h windows (120 windows) | 65.2 s | 139.2 s | **2.14** |
| 636 h, 10 Hz, 1 h windows (60 timed, extrapolated) | 52.2 s | 139.9 s | **2.68** |
| 636 h, 10 Hz, 72 h windows (1 timed, ×8) | 52.2 s | 27.2 s | 0.52 |
| 24 h, 1 Hz, cold process | 4.4 s | 10.1 s | 2.28 |
| 24 h, 1 Hz, warm | 4.4 s | 3.8 s | 0.85 |

- The cold run pays about 6 s more under load (numba cache load); the 13 s import is separate.
- The pair-count model predicts the worst windows are around 2 h at 10 Hz (9.75×) and 6 h at 1 Hz (2.9×); measured time has run about half the pair ratio.
- Crossing 15 minutes on one channel would need an estimate of roughly 3–6 min at 10 Hz with 1–4 h windows. None of our channels is that long today, but a loaded machine or a multi-channel run could get there.
- **Rule:** estimate n_samples × max over window lengths W of (pairs(W) ÷ W) — in other words, assume the costliest tiling. It over-estimates a 72 h run by up to about 3× at 1 Hz (harmless) and never under-estimates.
- Alternatively, have `estimate` read the upstream window length once W3-F passes `value`.

**Q5. The cap** (6 realisations, 2 h template detrend):
- Bias against the uncapped value is ≤ 0.003 nats at every scale.
- The spread of (capped − uncapped) is ≤ 0.007, against a realisation-to-realisation spread of 0.005–0.074. The cap costs nothing measurable.
- Speed: 24–40× at 72 h (5.1 s against 209 s on AR(1) φ 0.99), 5–7× at 24 h.
- **RCMSE equals MSE exactly** where one offset is pooled: 24 h scales 1–4 s, 72 h scales 1–13 s (difference 0.000). The whole RCMSE − MSE difference is ≤ 0.01 everywhere, because each coarse series is ≥ 1,000 points.
- The face does not say so (nit above).

**Q6. Your declared statistic.**
- **Size on Gaussian coloured noise** is 7.5 % at both lengths (6 / 80), against a nominal 4.8 %. That is slightly liberal and acceptable, except for the random walk at 24 h (p ≤ 0.1 in 8 / 20, against about 2 expected).
- **Power:** drops 5×SD 39 / 40; drops 2×SD 2 / 20 (24 h) and 8 / 20 (72 h).
- **The flaw:** the null "a linear Gaussian process seen through a static non-Gaussian transform" (AR(1) φ 0.97, z-scored, passed through exp()) **beats 20 / 20 at 24 h and 20 / 20 at 72 h**.
  - The real curve sits 0.62 nats below its surrogates' mean, about 60× the draws' spread. By comparison, real drops shift it only +0.055.
  - Plain phase randomisation makes the surrogates Gaussian, and SampEn with a MAD-based r is very sensitive to the shape of the value distribution.
  - The project's own `Pipelines/drop_motifs/nulls1.py::aaft_surrogate` docstring says these channels are "strongly non-Gaussian", so every real recording would likely "beat" on its value distribution alone.
- **With AAFT surrogates** (same statistic, 12 realisations, 24 h): the exp() process beats 2 / 12, drops 5×SD beat 12 / 12 on AR(1) and 12 / 12 on random walk, AR(1) φ 0.97 beats 1 / 12. The random walk stays a little liberal (3 / 12).
- **Recommend:** correct the ledger now to AAFT (or IAAFT) surrogates, reusing `aaft_surrogate` or a `preprocessing.surrogate` method. Report the plain-phase result beside it. The block's description ("compare with phase-randomised copies") should say amplitude-adjusted.
- Proxy note: the template chain was run directly (rolling-mean detrend → tiled windows → core), not through `execute_recipe`.

**Q7. Scope.**
- MiniRocket's behaviour is unchanged. `test_minirocket.py` and `test_adapter_minirocket.py` pass (inside the 355), and the refusal text is identical apart from the block name, pinned by `test_minirocket_still_refuses_windows_outside_its_span_in_its_own_name`.
- `span_relative_starts` is a clean one-function promotion, as the brief allowed.
- The two `BOOKKEEPING_COLUMNS` (`mse_n_scales`, `mse_n_collapsed`) are justified; `mse_r` and `mse_drift_share` should join them (F3).
- The `test_adapter_spec.py` count (54 → 55) is required, and it will conflict with W3-C at merge.

### The five axes
- **Spec:** every acceptance item is met and tested. The named departure (the detrended random walk flags 1 s) holds only on the test's seed (Q2).
- **Faithful to the paper:**
  - r is fixed from the original window, as `mse.c` does.
  - Sample entropy uses N − m templates for both counts.
  - RCMSE follows Azami's restatement, named as such.
  - The cap and the collapse rule are named departures.
- **Correct on our data:**
  - It handles empty, short, constant, all-NaN, ties and outliers loudly.
  - Gaps are handled, except that the interpolated share never reaches the face (F5).
  - No process-wide state is touched (a seeded `default_rng`; numba `nogil`, thread count untouched).
- **Standards:** thin adapter, sensible bounds, plain description, estimate declared, every flag reaches `meta["warnings"]` and the summary line.
- **Test-first and scope:** the first commit touches only `tests/` and shows the failures in its message. Scope as in Q7.

### 4. What I ran
- **Tests** (from the worktree, conda python): the block's three test files, plus `test_block_standard`, `test_adapter_spec`, `test_import_boundaries`, `test_templates`, `test_minirocket`, `test_adapter_minirocket`, `test_types`. **355 passed in 142 s.**
- **Experiments**, in `C:\Users\mmebr\AppData\Local\Temp\claude\C--Users-mmebr-Documents-CNN\22c30530-4ff1-428e-9402-a0b4d395d67c\scratchpad\critic_w3a\`, with numba's cache and the cost calibration redirected there:

  | Script | What it measured |
  |---|---|
  | `size_power.py` | 8 signal kinds × 20 realisations × 21 runs, at 24 h and 72 h; plus an AAFT variant (5 kinds × 12) |
  | `guard.py`, `inflation.py` | ρ, flags and inflation, 24 h and 72 h |
  | `q3.py`, `q3b.py` | cluster features, NaN rows, unit silhouette |
  | `cap.py` | capped against uncapped, 36 windows |
  | `timing.py` | calibration, estimate against actual |
  | `edge.py` | edge cases |

- **Load and the manager's cap:** the machine ran at 91–100 % CPU throughout, so all timings are ratios. My pools had all finished before the manager asked for at most 4 workers; my last check ran with `NUMBA_NUM_THREADS=4` and `OMP_NUM_THREADS=4`.
- Nothing in the repo or the worktree was edited, and `DATA/` was never touched.
