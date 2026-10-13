# Critic report — W1-D: `detection.noise_threshold`

Filed by the manager, 2026-10-13. Verdict: **merge after fixes** (three should-fixes, in `noise_level.py` and the
adapter's warning logic).

## In plain words

The cut is "k times this channel's own noise", measured with a median ruler a few spikes hardly move. Whole-span mode is
correct: 30 / 30 synthetic slow-recovery drops on a 3-day 1 Hz trace, identical in V and mV, white-noise false
detections at the theoretical rate. Weak spots: the rolling mode has no sensible minimum window, and the
"events dominate" warning misses the case it exists for.

## Findings

1. **should-fix** — rolling mode with short windows over-detects (white noise, k = 4, 200 k samples: 3 s → 15,721 spans,
   10 s → 1,641, 60 s → 80, 300 s → 31, 3600 s → 13; whole-span 12); no warning. Enforce a minimum window in samples
   (~300) and test the false-positive rate there.
2. **should-fix** — σ = 0 windows are interpolated into neighbours (`noise_level.py:100`), so samples beside a flat
   stretch fire (69 spans vs 5). Exclude σ = 0 anchors; mark those samples unjudged.
3. **should-fix** — the > 20 % warning counts samples *past* the cut, so events that dominate inflate σ_n and hide
   themselves silently (40 % of samples as 5σ or 8σ drops → σ_n 2.84, 0 spans, no warning). State it; add a diagnostic
   σ_n / first-difference σ (white 1.0, 40 % 5σ events 2.75, AR(1) φ = 0.8 noise 2.1 — a number, not a hard warning).
4. **nit (manager)** — on realistic drops (20-min recovery, 600 s rolling-mean detrend) the template fragments: 733 spans
   for 30 drops untidied; with `merge_gap_s = 60, min_duration_s = 30`, 28 spans covering all 30. Consider tidying in
   the CANONICAL entry.
5. **nit** — default `direction` is `either` (the sibling's is `above`); defensible, mention it.
6. Out-of-scope edits justified: the adapter count is required; the `compare.py` glyph entry is redundant but harmless.

## Checked and fine

`robust_sigma` wrapped not copied; MAD around the median named and justified; span-relative indices; scores in σ_n
units; V → mV; zero-σ whole-span mode honest; edge cases (empty, 1–3 samples, all-NaN, NaN gaps, fs = 10); no `threshold`
param; tidy helpers imported; 2.6 M samples in 0.63 s whole-span; test-first commit tests-only (22 failed / 27 passed).
238 passed across the block's and siblings' tests.
