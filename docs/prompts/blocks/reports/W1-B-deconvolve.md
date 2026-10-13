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

## Noise-scale follow-up (branch `w1b-noise-scale`, 2026-10-13)

**In plain words.** The block counts a dip as a "jump" when it is bigger than a few noise steps. It used to judge "noise"
by how much the trace changes from one second to the next. Smooth fungal recordings wander slowly, like a boat bobbing
on a long swell: each second barely differs from the last, so that ruler read the noise as tiny (1/46, 1/38 and 1/3.4
of the real spread on rec 385, M2_aug CH0 and S. commune ch1) and every slow wobble counted as a jump (1,716 in 4 h on
rec 385). The ruler is now, by default, the height of the swell itself: how far the trace strays from its baseline,
with the troughs cut out (`noise_scale = level`). The old ruler stays as `noise_scale = diff`. Only the ruler changed;
the fit (least squares, which no noise SD enters) did not.

**What changed.**
- `noise_scale` (`level` default | `diff`): `scale` is the score's unit and s_min's, the residual SD's unit, the
  running baseline's tolerance and the recovery refinement's jump price. `sigma` (first differences) and `sigma_level`
  both stay in meta, with `noise_scale` and `scale` naming the one used; the summary prints it and the ratio.
- `sigma_level` is now measured BEFORE the fit (it sets the threshold): the samples minus a running floor (the running
  baseline's, or a 15th percentile over 15 recovery half-times for the constant baseline, so drift slower than that
  stays a misfit the residual SD reports), then median/1.4826 MAD with iterative 3-SD clipping (troughs removed).
- Two new warnings. **Follow-ons:** > 35 % of ≥ 10 jumps smaller than the fade they land on — a kernel faster than the
  troughs (with `level`, 120 s on 300 s troughs splits each ~2x, too few for the per-hour flag). **Level spread:**
  (P97.5 − P2.5)/(3.92 sigma_level) < 0.75 — the samples fill a band evenly, events with no quiet background (back-to-
  back sharkfins), which `level` then measures instead of noise; it names `noise_scale = diff`.
- Template `deconvolved_troughs` → version 2: `noise_scale: "level"` explicit, description says what the SD is.

**Numbers** (12 h, 30 troughs 2–6 mV, background SD 0.2 mV, template's first three blocks; events / jumps / residual):

| background | level, troughs | level, no troughs | diff, troughs | diff, no troughs |
|---|---|---|---|---|
| white 0.1 mV + drift | 30 / 30 / 0.84 | — | 30 / 30 / 1.20 | — |
| AR(1) φ 0.95 | 30 / 30 / 0.80 | 0 / 0 | 220 / 264 / 3.40 | 216 / 258 |
| AR(1) φ 0.99 | 30 / 31 / 0.76 | 0 / 1 | 570 / 672 / 4.24 | 604 / 700 |
| 1/f | 30 / 30 / 0.91 | 0 / 0 | 46 / 58 / 2.04 | 13 / 20 |

`level_sigma` reads AR(1)/1/f backgrounds within ~1 % of their SD (σ from differences: 0.10–0.4 of it) and the white
trough train at 1.2x (trough tails). At 0.5 mV background (troughs 4–12 SDs) level finds 22–30 of 30, none on noise
alone: below ~5 SDs a trough is noise-sized. Follow-on share: 0.03–0.28 with the right half-time, 0.44–0.48 with 120 s
on 300/600 s troughs (one seed at 0.10 is missed). Back-to-back sharkfins: `level` finds no jump (sigma_level 23x
sigma) and warns via the spread (0.56–0.59; Gaussian backgrounds 0.95–1.01, trough trains 4.6–8.5).

**Tests changed on purpose:** the noise-free OASIS test and the two sharkfin-residual tests pin `diff` explicitly (and
the sharkfin test now also pins the level-spread warning); s_min = min_jump_sigma × scale; the too-short-recovery
template test accepts the follow-on warning and n > 45 (was > 60). New: `tests/test_deconvolve_noise_scale.py`.

**Not done / open.** Real recordings not re-run here (no DATA in the worktree): the three channels above should be
re-run through the template to confirm the jump counts fall. The step cache keys on raw recipe params, so a cached
deconvolve step from a recipe without `noise_scale` can still be served with the old unit, and databases already seeded
keep the version-1 template row (`seed_canonical` never touches an existing row).
