# Report — W1-B: `detection.deconvolve` + `detection.impulse_events` (implementer)

Filed by the manager, 2026-10-13. Branch `worktree-agent-af56adff6a9d0c6ef` (base e59ae67), commits `c423f10` (tests,
red) and `f9d0753` (implementation; the first implementer was interrupted, a resuming agent finished it). 64 block tests
and 203 gate tests pass.

## In plain words

A fungal trough is a sudden drop then a slow recovery; when a second drop starts before the first has recovered, a
threshold sees one blob. **Deconvolve** asks "what list of sudden jumps, each followed by the same fade, best explains
this trace?" and returns the jump size in noise SDs at every sample, almost always zero. **Impulse events** turns each
jump into one event, from 10 s before it to the next jump (or 600 s).

12 h synthetic, 30 troughs with 8 overlapping pairs: all 30 onsets within 2 samples, each pair as two events;
`signal_threshold` merges all 8 pairs; recovery half-time estimated 118 s vs 120 s true; ×1000 scaling changes nothing.

**Sharkfins:** an exponential fade cannot hold a floor, so OASIS rebuilds the plateau as a staircase of extra jumps —
about **36 events per fin** (255–298 for 7 fins), with a residual SD of only ~1.6 noise SDs. The misfit shows as many
events per fin, not in the residual; on sharkfin data the event count is the warning sign.

## Algorithm as implemented

Polarity by negation; σ = 1.4826 × MAD(first differences)/√2 (replacing the paper's PSD estimate: at 1 Hz drops put
power in every band); γ given (2^(−1/(half·fs))) or estimated (autocovariance guess, refined by minimising RSS as in the
paper; refuses when the autocovariance never halves); thresholded OASIS (pool-adjacent-violators, O(T), numba), jumps
≥ `min_jump_sigma`·σ (fixed, not raised until RSS = σ²T); AR(2) by its two roots; ℓ1 form via y − λw; output s/σ;
first sample of each run reported as `initial_levels`, scored 0; NaN splits runs.

**Beyond the prompt:** `baseline_window_s > 0`, a running baseline (two-pass running 15th percentile with a slope-bias
correction, refined by the running mean of y − c). Without it the template found **823 events for 30 troughs** — a
rolling-mean detrend upstream is dragged down by each trough, leaving 1–2 σ steps a constant baseline explains as
hundreds of small jumps.

Impulse events: impulses above `threshold` within `merge_within_s` form one event; onset = the sample before the first
impulse; extent = [onset − pre_s, next onset or onset + max_extent_s]; trough = largest |x − x[onset]|; score = sum of
impulses; `meta["events"]` with `onset_idx`, `trough_idx`, `right_capped`.

Speed, 2.6 M samples: 1.9 s (half-time given), 6.5 s (estimated); O(n), no cost model.

## Integration

Template `deconvolved_troughs` = detrend (rolling_mean 3600 s) → deconvolve (`baseline_window_s` 1800) → impulse_events
→ event_shape → intervals.

## Open questions

Keep `baseline_window_s` (default 0) and revisit the template once BEADS lands; heavy drift alone breaks the running
baseline (window must be ~15 recoveries); sharkfins fragment; fidelity checked against NNLS only, not the authors'
MATLAB fixture.

## Fix round (after the critic), commits `100aeef` (red) and `b5daaba`

- **F1:** the recovery is chosen by a BIC-style penalty (RSS/σ² + 2·ln T per jump) under the same baseline mode as the
  real fit, with the search recentred up to 3× when it lands on an edge; warnings for an edge estimate and for jumps
  faster than they recover. The template sets `recovery_half_s = 120`, and both descriptions name it as the first knob.
- **F2–F9:** a quiet channel returns zero scores with `recovery_estimated = False`; residual SD > 1.5 flagged
  (sharkfins); `meta["sigma_level"]` beside σ for coloured noise; running-baseline convergence on the mean step;
  greedy-approximation figures in the docstring; runs starting mid-event counted; `threshold` min 0 and the overlap
  stated; a cost model.

| True half | Half | Used | Events (30 true) | Residual SD | Warnings |
|---|---|---|---|---|---|
| 120 | given | 120 | 30 | 1.20 | — |
| 120 | estimated | 115.5 | 30 | 1.19 | — |
| 300 | estimated | 293.1 | 30 | 1.33 | — (was 48 s, 740 events) |
| 300 | 120 given | 120 | 187 | 1.73 | fragmentation, residual |
| 600 | estimated | 455.7 | 31 | 1.66 | residual, baseline not converged (was 51 s, 1,072) |
| 600 | 120 given | 120 | 356 | 1.91 | fragmentation, residual |

Sharkfins: 40–90 events per fin, every run warned. Event-free AR(1) φ = 0.95 noise: σ reads 0.224 of the true SD,
`sigma_level` 1.007; 23 jumps/h with 120 s given, warned. 2.6 M samples: 0.7–4.6 s. 281 tests pass. Merged into `main`
as `6f7f241`.
