# W1-A — `preprocessing.beads`: baseline removal by BEADS (Ning, Selesnick & Duval 2014)

Read [`00-common.md`](00-common.md) first. Commit prefix **`w1-a:`**. Plan: `docs/research/analysis-blocks-from-literature.md`
§5 row 3; facts: `docs/research/analysis-blocks-primary-sources.md` §6.

## In plain words

A recording is a slow, wandering baseline (drift) plus sparse events (drops and spikes) plus noise. Today the app
removes drift with a rolling mean, which is dragged down by every big drop and leaves a fake overshoot beside it, and
whose window length has repeatedly been the wrong size. BEADS splits the trace into three layers at once — a smooth
low-frequency baseline, a sparse layer of events (mostly zero, with mostly-zero slopes) and noise — and lets each layer
explain only what it is good at. The block passes on the signal **with the baseline removed**.

## The algorithm (verify against the paper; the HAL preprint hal-01330608 may be reachable, the verifier could not)

y = f + x + w: f low-pass (the baseline), x sparse with sparse first and second differences, w noise. Minimise
F(x) = ½‖H(y − x)‖² + λ₀ Σ θ_ε(xₙ; r) + λ₁ Σ φ([D₁x]ₙ) + λ₂ Σ φ([D₂x]ₙ), with H a zero-phase high-pass filter built
from banded matrices (H = B A⁻¹, order d, cut-off fc in cycles/sample), θ an asymmetric penalty with ratio r (events
one-sided), φ a smoothed absolute value; majorisation–minimisation with banded solves, O(N) per iteration; baseline
f = y − x − H(y − x). Laurent Duval's MATLAB is BSD-3 and pybaselines' `beads` (BSD-3,
https://raw.githubusercontent.com/derb12/pybaselines/main/pybaselines/misc.py) is an adaptation of it — you may read
and adapt either, keeping the copyright notice in your docstring.

## Adaptations our data force (name each in the docstring)

1. **Parameters in our units:** `baseline_period_s` (default 7200; fc = 1 / (baseline_period_s · fs)), `polarity`
   (`drop` | `spike` | `both`; drops are handled by negating the signal, solving, negating back; `both` uses r = 1),
   `sparsity` (default 1.0, a unit-free multiplier on λ₀), `filter_order` (1 or 2, default 1). λ₁ and λ₂ are
   **derived** from `sparsity` (small λ₁ changes are reported to destabilise BEADS), not exposed.
2. **Unit-free:** scale the signal by a robust noise estimate before solving (e.g. the MAD of the first difference
   / (0.6745·√2)) and scale back, so the same `sparsity` means the same thing in volts and millivolts.
3. **Ends:** BEADS needs the signal near zero at both ends — remove a fitted line or parabola through the end regions
   first and add it back to the baseline (what pybaselines' `fit_parabola` does).
4. **Long spans:** M2_aug channels are 2.6 M samples. Use scipy.sparse banded systems (`scipy.sparse.linalg.spsolve`
   on `dia`/`csc` matrices or `scipy.linalg.solve_banded`) so memory and time stay linear; cap iterations
   (`max_iter` 30, tolerance on the cost change), and record convergence in `meta`.

## Deliver

- Core `Working/Preprocessing/beads.py` (or a better-fitting folder): `beads(y, *, fc, d, r, lam0, lam1, lam2, …) ->
  (x, f, info)` plus the unit-free wrapper the adapter calls.
- Adapter `Adapters/preprocessing_beads.py`: `preprocessing.beads`, Signal → Signal, `category="preprocess"`,
  `page_name="BEADS baseline"`. Output = y − f. `meta`: fc, r, the λs used, iterations, converged, the robust σ, the
  baseline's range, and the fraction of samples where |x| exceeds 3σ. `estimate` via `register_cost_model` (≈ linear).
- Tests `tests/test_beads.py` (core) and `tests/test_adapter_beads.py` (spec, defaults, bounds, a run, the error when
  the input is too short).

## Acceptance

- [ ] 48 h at 1 Hz: a 6-hour sinusoidal drift of 5 units + 20 drops (fall in ~20 s, exponential recovery τ ≈ 200 s,
      depth 1 unit) + white noise σ = 0.05. The returned signal's residual drift (the true baseline minus the
      estimated one) has RMS < 0.1 of the drop depth away from the drops, and every drop keeps ≥ 85 % of its depth.
- [ ] On the same trace, a 600 s rolling-mean detrend shows a larger overshoot next to the drops than BEADS does
      (pin the comparison numerically — it is the reason the block exists).
- [ ] Multiplying the input by 1000 multiplies the output by 1000 and nothing else changes (unit-free).
- [ ] `polarity` matters: on drops, `drop` preserves them better than `spike`.
- [ ] 2.6 M samples run in under ~2 minutes and stay within a few hundred MB (measure and report; mark the test slow
      or size it down if needed, but report the measured full-size figure).
- [ ] The block passes `tests/test_block_standard.py` and `tests/test_adapter_spec.py`.

No template of its own: it is the first step of the `deconvolved_troughs` and `fluss_regimes` templates (the manager
wires it after merging). Suggest in your report whether the `signal_threshold` template should also use it.
