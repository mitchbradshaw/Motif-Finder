> Filed by the manager session, 2026-10-14 22:00 — the final message of implementer agent `a67442d9e04015d6a` on
> branch `worktree-agent-a67442d9e04015d6a` (`2aedf23`, `99b043f` on `01cb8c3`), verbatim.

## W3-A report: `catalogue.multiscale_entropy` and the `complexity_fingerprint` template

### 1. In plain words
The block gives every window (hours of signal) a "complexity curve". It blurs the signal by averaging 1 s, 2 s, 4 s … up to 20 min at a time. At each blur level it asks how surprising the next value is (sample entropy). White noise gets less surprising as it is blurred. Pink (1/f) noise stays flat. A signal with real structure at many time-scales differs from noise that has the same spectrum. On the synthetic data:

- **It reproduces Costa's two benchmark shapes.** White noise is within 0.06 nats of the closed form at every scale from 1 to 20. Pink noise stays flat, with a range under 0.25.
- **It finds structure where there is some.** Sharp drops with slow recovery on AR(1) (amplitude 5 × the background SD, one every 20–60 min, 24 h) lie outside the spread of their own 20 phase-randomised copies, at p = 1/21. Plain AR(1) does not separate (p > 0.1).
- **It has a limit.** At drop amplitude 2 × SD the curve is not separated from its null (p ≈ 0.52).
- **The √t "0.0028" collapse reproduces, and the guard fires.** An undetrended random walk with an SD-based r gives entropies of 0.016–0.34. The guard flags those scales.
- **Detrending first fixes it.** After a 2 h detrend, with a MAD-based r, drifting AR(1) windows get their drift-free curve back (within 0.06) and the guard is quiet.
- **A detrended random walk still flags its 1 s scale.** This is honest, not a bug: after any detrend that keeps the minute scales, it still wanders by about 4 steps, so r is the wander's, not the noise's.

### 2. Files
- created `Working/Catalogue/multiscale_entropy.py` — the core.
- created `Adapters/catalogue_multiscale_entropy.py` — the adapter, cost model and derive rows.
- created `tests/test_multiscale_entropy.py` (34 tests), `tests/test_adapter_multiscale_entropy.py` (7), `tests/test_template_complexity_fingerprint.py` (5).
- modified `tests/test_block_standard.py` — one `COSTED` line, on its own line under `# wave 3`.
- modified `Working/types/windowset.py` (outside the Deliver list):
  - **The one helper move:** MiniRocket's slicer bounds rule is now `span_relative_starts(ws, n_samples, t, fs, block=...)`.
  - `mse_n_scales` and `mse_n_collapsed` are added to `BOOKKEEPING_COLUMNS`.
- modified `Working/Catalogue/minirocket.py` (outside the Deliver list) — `_slice_x` now calls the shared helper. Its refusal text is unchanged and pinned by a test.
- modified `tests/test_adapter_spec.py` (outside the Deliver list) — the shipped-adapter count goes from 54 to 55. W3-C will touch the same line, so you will need to merge it.

### 3. The algorithm as implemented
1. **Windows.** Each window is sliced from `x`, one at a time (starts are channel-absolute). A Window pool is refused in words.
2. **Gaps.** Runs of missing samples up to `max_gap_s` (30 s, labelled a placeholder) are filled with straight lines and counted. A window with a longer run becomes a NaN row (`gap_over_max`). A zero-spread window is left out as `flat`.
3. **Tolerance.** r = `r_frac` (0.15) × spread of the window as it arrives, computed once and fixed across scales, as `mse.c` does.
   - `r_scale` is `mad` (1.4826 × MAD, the default) or `sd`.
   - The block never detrends.
4. **Scales in seconds.** Geometric from `scale_min_s` to `scale_max_s`: 1 s → 1200 s, `n_scales` = 12.
   - τ = round(s × fs), deduplicated; the reported scale is τ/fs.
   - Columns are named `mse_<τ/fs to 4 significant digits>s`.
5. **Coarse-graining.** Non-overlapping means (Costa eq. 16), from one cumulative sum.
6. **Sample entropy.** Richman–Moorman: N−m templates for both counts, Chebyshev distance ≤ r, no self-matches.
   - Counts are exact (numba, sorted-template trick) and pinned against a naive loop.
   - Deviation: the existing window-matrix `_sample_entropy` uses different template sets for its two counts; this block follows `mse.c`.
7. **`method`.**
   - `mse`: the offset-0 coarse series, as Costa.
   - `rcmse` (default): counts pooled over the offsets before the log, after Azami 2017's restatement. Wu 2014's own equation was not reached.
8. **Cost cap (our departure, for cost).** Each coarse series is scored on at most `max_points` = 20,000 templates (Costa's N).
   - When a series is longer, the templates come from 10 stretches spread evenly across the window, and every pair between them is compared.
   - RCMSE pools min(τ, ⌊(max_points/L)²⌋) evenly spaced offsets: all of them on short series, one on long ones. So every scale costs about max_points²/2 pairs.
   - Measured on AR(1) φ 0.97, 24 h, 8 realisations: the spread between realisations is 0.01–0.02 nats at caps of 5k, 20k and 60k alike. The cap adds no visible spread.
9. **Undefined scales are NaN, never extrapolated.** Reasons, counted per scale:
   - `too_short`: the coarse series is shorter than `min_coarse_len` (1000).
   - `no_m_match` and `no_m1_match`.
   - I did not lower `min_coarse_len` for RCMSE, because I took no bias measurement to justify it.
   - What I did measure: at N = 150 on white noise, MSE left 38 scales undefined across 10 series and RCMSE 4.
10. **Collapse guard (our rule).**
    - ρ = r ÷ (1.4826 × MAD of the coarse series' first differences), i.e. r against the step a coarse value typically takes, at the scale being judged. A flag is raised when ρ > `collapse_ratio`.
    - The default of 4 is a measurement: every scale with ρ near 4 had entropy 0.10–0.14 nats. Detrended AR(1) sits at ρ 0.2–1.1; the raw random walk reaches 21–27.
    - I did not use the "nearly every template matches" fraction (B / pairs). Under drift that stays small (about 0.09) while A/B → 1, so it would miss the √t case.
    - Values are kept and flagged, never blanked.
11. **Drift share.** The variance share of a straight-line fit, 1 − var(residual)/var(window).
12. **Columns.**
    - `mse_<s>s` per scale.
    - `mse_ci`: the sum over the scales defined in every kept window; NaN plus a warning when there are none, a warning below 4.
    - `mse_slope_small` / `mse_slope_large`: least-squares slope against log10 of seconds, over the lower ⌊n/2⌋ and the upper remaining common scales.
    - `mse_r` (stored units), `mse_n_scales`, `mse_drift_share`, `mse_n_collapsed`.
    - Upstream features pass through; earlier `mse_*` columns are replaced, with a warning.
13. **Cancel and progress.** `should_cancel()` is checked before each window and raises `Working.execution.RecipeCancelled` (imported inside the function). `on_progress(done, total, "multiscale_entropy")` fires once per window.
14. **`meta`.** It holds:
    - `scales_s`, `taus`, `columns`, `method`, `m`, `r_rule`, `r_median`
    - `defined_per_scale`, `undefined_per_scale{reason: [per scale]}`, `blank_scales_s`
    - `collapse` (per scale), `rho_median`, `n_offsets`, `n_templates`
    - `ci_scales_s`, `n_ci_scales`, the two slope scale lists
    - `left_out{reason: n}`, `n_interpolated`, `seconds`, `warnings`, `summary`, `rules`
    - `curves` — W3-F needs this exact form: `{scales_s, n_windows, sampled, seed, windows: [{index, start_s, values[], collapsed[]}], median[], form}`. It holds at most 64 windows (a seeded sample beyond that), with `null` where a scale is undefined. Meta is JSON-safe (`allow_nan=False` is tested).

**Reach and cost arithmetic.** A scale of s needs 1,000 coarse points, so reach = window_s / 1000, the same at 1 Hz and 10 Hz. Uncapped figures are 1 Hz; 10 Hz is 100× worse again.

| Window | Reach | Default scales defined | Points at τ = 1 (1 Hz / 10 Hz) | Uncapped pairs at τ = 1 (1 Hz) | Capped pairs per scale |
|---|---|---|---|---|---|
| 4 h | 14 s | 5 | 14,400 / 144,000 | 1.0e8 | ≤ 2e8 |
| 24 h | 86 s | 7 | 86,400 / 864,000 | 3.7e9 | ≤ 2e8 |
| 72 h | 4.3 min | 9 | 259,200 / 2.6 M | 3.4e10 (≈170× capped) | ≤ 2e8 |
| 721 h | 43 min | 12 | 2.6 M / 26 M | 3.4e12 | ≤ 2e8 |

So every window costs about (defined scales) × 2e8 pair-slots, or roughly 1–3 s.

**Cost — what W3-F needs.** The estimate assumes 72 h windows tile the span. Warm timings, this machine:

| Case | Estimate | Actual |
|---|---|---|
| 24 h, 1 Hz | 1.6 s | 1.3 s |
| 73 h, 1 Hz | 2.4 s | 2.0 s |
| 24 h, 10 Hz | 1.8 s | 2.1 s |
| raw random walk 24 h / 73 h (collapse case) | 1.6 / 2.4 s | 1.0 / 1.9 s |
| 6 h windows tiling 73 h | 2.4 s | 7.1 s (3× under) |

- Calibration takes 1.6 s timed, plus an untimed numba warm-up.
- Cold process: the first run takes about 1.3 s longer with numba's cache present, and about 1.5 s more again without it (cold 4.25 s against warm 2.7 s).
- Registry import was about 9–10 s, but that is all adapters, not this block.

### 4. Tests
- **Red:** `2aedf23`, tests only. Run on the tests-only tree:
  - `ImportError: cannot import name 'multiscale_entropy'` (collection errors in the core and template files)
  - 7 × `KeyError 'catalogue.multiscale_entropy'` in the adapter tests
  - `test_costed_blocks_declare_an_estimate_or_a_ceiling[catalogue.multiscale_entropy]` FAILED
- **Green:** `99b043f`. 355 passed across the block's three files, `test_block_standard`, `test_adapter_spec`, `test_import_boundaries`, `test_templates`, `test_minirocket`, `test_adapter_minirocket` and `test_types`. No test of this block imports FastAPI, so none skips.
- **What the tests pin:**
  - exact counts against a naive loop (m 1–3, three values of r, ties, a template subset, RCMSE offsets)
  - Costa white and pink noise
  - RCMSE leaves fewer undefined scales than MSE
  - 1 Hz vs 10 Hz within 0.03
  - the guard: SD on drift fires, MAD after detrend does not; the detrended random walk flags only the 1 s scale
  - drops against 20 surrogates at the defaults, plus an extra copy inside the spread, determinism, and plain AR(1) not separated
  - too-short and no-match reasons, gaps, flat windows, refusals
  - cancel and progress, the index over common scales only, slopes, `mse_r`, pass-through, the 64-curve payload, the cap, scale names
  - the template: end to end on 73 h; a 24 h recording refused in words; cancel through `execute_recipe(run_kwargs=…)` surfaces as `RecipeCancelled`, not as a failure; the 2 h detrend measurement

### 5. Integration snippets
- **Template, verbatim** (from `tests/test_template_complexity_fingerprint.py`, with `HOUR = 3600`):
```python
{"name": "complexity_fingerprint", "kind": "training", "version": 1,
 "description": "A complexity fingerprint per recording: the slow drift is removed (a 2 h rolling mean), the recording is cut into 72 h windows, and each window gets a multiscale-entropy curve — how surprising the next value is after blurring the signal over 1 s, 2 s, ... minutes. Tune the coarsest blur first (scale_max_s): a 72 h window reaches about 4 minutes, scales beyond are blank and say so. A curve shows how irregular the signal is at each time-scale and can tell recordings, species and conditions apart; it cannot show events, and coloured noise has a curve of its own — compare a curve with phase-randomised copies of the same recording before reading anything into it. A recording shorter than 72 h gets no window: shorten window_s.",
 "steps": [
   {"stage": "preprocessing", "algorithm": "detrend", "params": {"mode": "rolling_mean", "window_s": 7200.0}},
   {"stage": "preprocessing", "algorithm": "sliding_windows", "params": {"window_s": 259200.0, "gap_s": 0.0}},
   {"stage": "catalogue", "algorithm": "multiscale_entropy", "params": {}}]}
```
- **Why a 2 h detrend.** On 24 h AR(1) with dense drops it moves the curve by under 0.03 nats. It removes a drift 40 × the SD to within 0.06. A 6 h detrend left 0.7–1.1 nats of that drift; 1 h and 2 h both removed it. On 72 h signals all three move the curve by under 0.025.
- **Glyph for `BY_NAME["catalogue.multiscale_entropy"]`** (44 × 26):
  - three short grey window outlines along the bottom;
  - above them, a blue curve of about 6 dots rising and then flattening, left to right on a log-scale axis;
  - beside it, a dashed grey falling curve (the white-noise reference);
  - one amber dot at the far left, low, marking a flagged collapsed scale.
- **Smoke state:** run `complexity_fingerprint` on a recording of 72 h or more and open step 2. Expect `data-view="windowset"` with the `windowset->windowset` modifier, a heatmap whose columns include `mse_1s` and `mse_ci`, and the summary line.
- **`COSTED`:** `"catalogue.multiscale_entropy",` (already added under `# wave 3`).
- **W3-F / serializer:** `meta["summary"]` and `meta["warnings"]` (blank scales, collapse, left-out windows) need to reach the face. Today `serialize.py::_windowset` only shows `meta["summary"]` for anchored sets.

### 6. Open questions and risks
- **Departure from the acceptance list.** "MAD on the detrended window does not fire" holds for detrended AR(1) and drift, but not for a detrended random walk: its 1 s scale flags at ρ 4.2. Real fungal channels are random-walk-like, so expect the 1–2 s scales flagged on real data. I believe that is correct, but it is your call. The alternative is an r taken from the step scale, which would be a different measure from Costa's.
- **Two defaults are measurements or placeholders, not paper values.** `collapse_ratio` = 4 comes from my synthetic measurements; `max_gap_s` = 30 s is a placeholder.
- **Not handled by this block.** `min_coarse_len` was not lowered for RCMSE (no bias measurement). Rows with NaN reach Cluster or Classifier as they are; I did not check how those blocks treat NaN rows.
- **Please check on real data:**
  1. The guard's ρ by scale on M2_aug and the four species, after the template and raw with `r_scale="sd"` (does the 0.0028 reproduce, and does the guard fire?).
  2. The manager's 20-surrogate test per recording at the defaults.
  3. Whether 2 h detrending changes the curves of S. commune by more than about 0.03 against 6 h.
  4. Estimate vs actual timings for a 721 h channel at 1 Hz.
- **Files I did not touch.** RQ files (`docs/rq_roundA/`) are on the do-not-touch list. RQ3/RQ6, conditions and organisms, may want a line saying that MSE fingerprints now exist.
- **Conflicts with W3-C at merge:** the adapter count in `tests/test_adapter_spec.py` and the `COSTED` line in `tests/test_block_standard.py`.

### 7. Commits
```
99b043f w3-a: catalogue.multiscale_entropy -- a multiscale-entropy curve per window (Costa 2005, RCMSE)
2aedf23 w3-a: tests -- catalogue.multiscale_entropy, its core and the complexity_fingerprint template
```
(on base `01cb8c3`)
