# Report — W1-F: `detection.fluss` (implementer)

Filed by the manager, 2026-10-13. Branch `worktree-agent-a400c4d610819d5e4` (base e59ae67), commits `9da0002`
(tests, red: 4 failed / 28 passed / 16 errors) and `86190d5` (implementation). The first implementer was interrupted
after writing the code uncommitted; a resuming agent verified it against the tests, prompt and §13a and committed it
unchanged.

## In plain words

Every one-minute stretch points at the stretch elsewhere that looks most like it. While the fungus keeps doing the same
kind of thing, those pointers stay within that period; where its behaviour changes, almost none cross — like two
neighbourhoods with no friendships across the street. The block counts pointers passing over each moment, corrects for
the middle always getting more, and scores 0 (no change) to near 1 (a clear change).

Synthetic: two 2-h regimes → the score peaks within two windows of the boundary and the template gives exactly one span;
one 4-h regime → no span; a drifting ramp → the score stays low (fails safe).

## Algorithm as implemented

Index from the site's own `run_matrix_profile.matrix_profile(x, t, m, backend="auto")`; the int index passed to
`stumpy.fluss` (a float array is refused, naming stumpy's docstring mistake); `iac` = `parabola` (paper, default) or
`beta` (stumpy; agrees to ~1–2 %); stumpy's 5·L edge blanking kept, blanked samples NaN ("not scored"); Score = 1 − CAC,
NaN tail; meta: `m`, `cac_min`, `regime_locs` + `regime_cac` (paper's Table II readout), counts, rules; refusals for too
short a window or span and above `max_span_samples_for_background()`. Cost: the matrix-profile model.

## Integration

Template `fluss_regimes` = detrend (rolling_mean 600 s) → fluss (60 s, parabola) → threshold (0.38, merge_gap 600 s,
min_duration 60 s). `COSTED` += `detection.fluss`.

## Open questions

The 0.38 cut is calibrated on synthetic data only (two-regime peaks 0.475–0.546, one regime ≤ 0.281, ramp ≤ 0.212);
the estimate uses the `stump` calibration even when the GPU is used; the readout always names n−1 locations (show
`regime_cac` beside them); 5 minutes at each end of a span are never scored at the 60 s default.

## Fix round (after the critic), commits `9569d81` (red) and `1dd5264`

- Template recalibrated on jittered and noisy regimes and event-free nulls: **window 300 s, cut 0.46, merge_gap 1500 s**.
  The block's own default window stays 60 s (the only real-data evidence, rec 385); the description says to set the
  window to about one event period and that the cut depends on it.
- NaN windows: FLUSS runs on the compressed valid index with its own IAC; windows without a neighbour score NaN. A
  4000-sample NaN gap that scored 0.93 now leaves no span. Readout padding dropped (`n_regimes_found`); span checks
  aligned; beta IAC cost stated.

| Recording (300 s window, after 600 s detrend) | Peak score per seed |
|---|---|
| two regimes, jittered, noise 0.05 | 0.65–0.82 — one span in all 12 seeds |
| two regimes, jittered, noise 0.3 | 0.49–0.68 — one span in all 12 seeds |
| one regime, jittered (noise 0.05 / 0.3) | 0.05–0.43 / 0.02–0.44 |
| pink noise, random walk, sinusoidal drift, ramp | ≤ 0.37 |

**Caveats on the face of the template:** the margin around the 0.46 cut is ~0.02–0.03 on either side; it holds for 4 h
spans only (a 2.8 h single regime peaked at 0.53); check NaN gaps (the detrend spreads them). 282 tests pass. Merged
into `main` as `6ecf3d3`.
