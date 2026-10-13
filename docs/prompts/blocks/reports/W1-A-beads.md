# Report — W1-A: `preprocessing.beads` (implementer)

Filed by the manager, 2026-10-13. Branch `worktree-agent-a817077087c32ec33`, commits `12d5dae` (tests, red) and
`85b6764` (implementation; a fresh start after the first attempt was interrupted). 224 passed with the gate suites.

## In plain words

A recording is like a road: a slow rise and fall of the land (drift), potholes (drops) and gravel (noise). A rolling
average is pulled down near a big pothole and leaves a fake bump beside every drop. BEADS splits the trace into a smooth
baseline, a sparse layer of events and noise, so a drop stays a drop. The block passes on the trace minus the baseline.

Test trace (48 h at 1 Hz, ±5-unit 6-hour drift, 20 one-unit drops, noise 0.05): drift residual 0.045 RMS away from the
drops (limit 0.1); every drop keeps ≥ 1.037 of its depth; fake bump beside a drop ~0.04–0.06 vs ~0.34 with the 600 s
rolling mean; a 2.6 M-sample channel in 0.5 s and 108 MB.

## Algorithm as implemented

`beads()` is a line-for-line port of Laurent Duval's BSD-3 `beads.m` (copyright kept), stored as diagonals and solved by
banded Cholesky (LU fallback), checked against a dense transcription to 1e-6. Parameters: `baseline_period_s` (7200),
`polarity` (drop: negate, r = 6; spike: r = 6; both: r = 1), `sparsity` (×λ in the paper's ratio 0.5 : 5 : 4, ×3), and
`filter_order`. Unit-free by dividing by a robust noise level (MAD of first differences); ε = 1e-4 in noise units.

**Deviations:**
1. **Coarse grid.** At fc = 1.4e-4 the filter matrix is ill-conditioned (~1e15 for order 2) and the solve becomes noise
   (40-unit errors on a drift-only trace), so BEADS runs on block means of q samples (fc = 0.02 per grid point; q = 144 s
   at defaults); the baseline is interpolated back; the output keeps every sample's own detail; only the event layer x
   is at grid resolution.
2. **`filter_order` defaults to 2**, not the prompt's 1: order 1 lets ~10 % of a drift three times slower than the period
   through (0.37 units left, failing the 0.1 limit at any sparsity); order 2 lets ~1 % through.
3. Ends: one period of point-reflection padding plus a line through the end-region medians (edge error 1.3 → 0.05).
4. 30 iterations max, stop at < 0.1 % cost change; NaNs interpolated for the solve and restored; refusals under 64
   samples or a period ≤ 2 samples.

Polarity: on the acceptance trace `drop` beats `spike` by only 6 % on the corrected signal (fast drops are separated by
the filter alone), but the event layer is 12 % of samples with `drop` vs 46 % with `spike`; with slower drops
(τ = 1200 s): drop 0.074, both 0.086, spike 0.154.

## Integration

No template of its own; first step of `deconvolved_troughs` / `fluss_regimes`; recommended for `signal_threshold` too
(its absolute cut is shifted by the rolling-mean overshoot). `COSTED` += `preprocessing.beads` (linear in grid points).

## Open questions

Confirm `filter_order` = 2; x is at grid resolution (a future `beads_events` needs a full-rate x); λ scale from one
synthetic trace; drops come out 4–8 % deeper (baseline sag); small baseline periods are slower (grid factor 1: 500 k
samples in 21 s); an event as slow as the period is removed with the drift (stated).

## Fix round (after the critic), commits `0f9393a`, `deeedac` (red) and `a0985a1`

- **F1 (blocker):** the scale is now the robust level of the high-passed grid H(grid) (what the fit term weighs),
  floored at σ/√q, and `LAMBDA_RATIOS` drops to (0.15, 1.5, 1.2). The critic's suggested scale (MAD of the grid's first
  differences) was tried and rejected: on a random walk it still put 38–54 % of the span in the event layer; the new
  scale puts 0.5 %. A warning fires when the event fraction exceeds 0.8.
- **F2:** order 1 withdrawn from the adapter's choices (it leaks 0.36 RMS on the acceptance trace whatever λ).
- **F3:** NaN at the ends is trimmed (bit-identical to the shorter span); interior gaps > period/10 warn; an event
  within a quarter period of either end warns (the end padding mirrors it — documented, not fixed).
- **F4:** documented — absolute levels unreliable on event-dominated spans (+0.30 vs the rolling mean's +0.68).

| σ | Drift period | A | Old error (event fraction) | New error (event fraction) |
|---|---|---|---|---|
| 0.05 | 3 h | 5 | 97.8 % (0.995) | 12.0 % (0) |
| 0.05 | 4 h | 20 | 84.8 % (0.998) | 4.2 % (0) |
| 0.01 | 4 h | 5 | 88.3 % (0.998) | 4.2 % (0) |
| 0.002 | 6 h | 20 | 63.1 % (1.0) | 0.88 % (0) |
| 0.001 | 4 h | 20 | 101 % (1.0) | 4.2 % (0) |

The remaining error is the order-2 filter's own leak. AR(0.95) noise + drift + troughs: BEADS 0.047 vs rolling mean
0.081. Limit: a large drift only ~2× slower than the period is tracked better by a 600 s rolling mean (0.17 vs 2.1).
237 tests pass. Merged into `main` as `f7a727d`.
