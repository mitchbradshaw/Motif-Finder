# Report — W1-C: `detection.cwt_ridges` (implementer)

Filed by the manager, 2026-10-13. Branch `worktree-agent-a158be5aa9862c601`, commits `fb889d9` (tests, red),
`5593535` (core), `7b7ae14` (adapter). A fresh start after the first attempt was interrupted.

## In plain words

A "Mexican hat" template slides along the trace at 40 sizes from 10 s to 2 h. A real event lights it up over a run of
neighbouring sizes; the bright points are joined across sizes into ridges, like tracing a mountain range from the summit
down, and the size where a ridge is brightest says how long that event lasts. One pass finds the 24 s, 8 min and 43 min
families, each with its own duration, and a straight drift cancels without a detrend window.

Synthetic 24 h days at 1 Hz (curved drift 10.6× the smallest event, noise, two-sided events of the three widths, a
sharkfin drop), 20 seeds: every event found, polarity right, duration within 1.18× at worst; one flagged extra a day (the
corner of the sharkfin's fall); drift and noise alone give no unflagged event (0.15 edge-flagged a day); a fast event on
a slow one gives two events at two scales. **Caveat:** random-walk-like wander gives ~50 events a day at the defaults
(white and AR(1) 0.95 noise give 0) — on real data `min_snr` or `max_scale_s` will need raising.

## Algorithm and deviations

Own Ricker (cut to ±5a, mean removed, FFT convolution) over geometric scales; local maxima per scale, both polarities;
ridges linked from the largest scale down (0.5a, ≤ 3 gaps); a peak needs ≥ 6 ridge points, an interior maximum of the
scale profile and SNR ≥ 3 (ridge maximum over the 95th percentile of |coefficients| at the smallest scale in a 3600 s
window); width from the best scale (parabola-refined); duration = 1.665 × best scale (FWHM of a matched Gaussian).
Deviations A0–A14 in the module docstring, notably **A0 1/a normalisation** (the paper's 1/√a missed 2 of the 43-min
troughs over 20 days, worst duration 1.45×; 1/a: 0 missed, 1.18×), **A12 a per-scale running-median baseline** (the hat
does not cancel curved drift), A3 chunking (2^21 samples, scale by scale), A6 nested events, A7 side-lobe veto, A14
step-pair flag. 2.6 M samples: 12 s, 212 MB, 2 chunks.

## Integration and open questions

Template `cwt_events` = cwt_ridges → event_shape (`polarity: auto`) → intervals; `COSTED` += `detection.cwt_ridges`.
Event shape's `auto` polarity agreed with the ridge's on only 5 of 9 synthetic events (amplitudes still right) — an
`upstream` polarity mode in event_shape is recommended (another file). Meta is ~3.5 MB per run (the 40 × 4096
scalogram). At 10 Hz the chunk overlap is large.
