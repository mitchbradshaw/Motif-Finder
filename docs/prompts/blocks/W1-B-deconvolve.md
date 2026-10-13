# W1-B — `detection.deconvolve` + `detection.impulse_events`: OASIS deconvolution (Friedrich, Zhou & Paninski 2017)

Read [`00-common.md`](00-common.md) first. Commit prefix **`w1-b:`**. Plan: `docs/research/analysis-blocks-from-literature.md`
§5 row 1; facts: `docs/research/analysis-blocks-primary-sources.md` §5.

## In plain words

In calcium imaging every firing makes the trace jump and then fade slowly; when firings come close, the fades overlap
and a threshold sees one blob. Deconvolution asks "what list of sudden jumps, each followed by the same fade, best
explains this trace?" and answers with one number per sample — how big a jump happened there — almost all zero. A
fungal **trough** is that shape upside down: a sudden drop, then a recovery. It also encodes the researcher's decided
reading of a sharkfin (Q26d): the slow climb belongs to the **previous** event. Two blocks:

1. **`detection.deconvolve`** (Signal → Scores): the jump size at every sample, in units of the noise level.
2. **`detection.impulse_events`** (Scores → SpanSet): one span per jump above a cut, with a sensible extent — generic,
   so any impulse-like score (this one, a future energy operator, a derivative) can use it.

## The algorithm (from the paper — the authors' code is GPL-3.0: do not copy it, implement from the text)

y_t = b + c_t + noise; c_t = γ c_{t−1} + s_t (AR(1)) or c_t = γ₁c_{t−1} + γ₂c_{t−2} + s_t (AR(2), finite rise);
s_t ≥ 0. Solve with OASIS — the active-set generalisation of pool-adjacent-violators, O(T) — in its **thresholded**
form (every non-zero jump ≥ s_min; Friedrich et al. §"thresholded OASIS"), or the ℓ1 form if you can justify it. γ
from the autocovariance (the paper's initial estimate) or from a given recovery half-time; σ from the high-frequency
power (the paper) or a robust MAD estimate; b from a low percentile or optimised.

## Adaptations our data force (name each in the docstring)

1. **Polarity:** `polarity` = `drop` (default; the signal is negated so drops become positive jumps) or `spike`.
2. **Time constants in seconds:** `recovery_half_s` (0 = estimate γ from the data; else γ = 2^(−1/(half·fs))),
   `rise_s` (0 = AR(1); > 0 = AR(2) with that rise time). Report the γ actually used and its half-time in `meta`.
3. **Unit-free output:** the Scores are s_t / σ — **jump size in noise SDs** — and `min_jump_sigma` (default 3.0)
   sets s_min = min_jump_sigma · σ. σ in stored units goes to `meta`.
4. **Drift is not handled by OASIS** (the paper says so): `b` is one constant per span. The block's description says
   to put a long detrend or `preprocessing.beads` (being built in parallel, W1-A) first; your template uses
   `preprocessing.detrend` with a window much longer than the recovery.
5. **impulse_events** extent, computed from its own inputs only (never a parameter repeated in two blocks):
   `threshold` (float, in the score's units — the name matters: `BLOCK_INTEGRATION.md` §2 makes it draggable on the
   upstream curve; default 4.0), `merge_within_s` (impulses closer than this are one event; default 2),
   `pre_s` (context before the jump; default 10), `max_extent_s` (default 600). A span runs from `pre_s` before the
   jump to the next jump or `max_extent_s` after it, whichever is first, clipped to the span. Emit
   `meta["events"]` = one dict per span with span-relative `onset_idx` (the jump) and `trough_idx` (the sample of
   largest |x − x[onset]| within the span), so the slideshow counts falls per window (`BLOCK_INTEGRATION.md` §2).
   Scores = the impulse size; reuse `Adapters/detection_threshold.py` helpers where they fit.

## Deliver

- Core `Working/Detection/deconvolution/oasis.py` (AR(1) and AR(2), thresholded) and the extent logic as a plain
  function; adapters `Adapters/detection_deconvolve.py` (`category="detect"`, `page_name="Deconvolve (OASIS)"`) and
  `Adapters/detection_impulse_events.py` (`page_name="Impulse events"`).
- Tests: `tests/test_oasis.py`, `tests/test_adapter_deconvolve.py`, `tests/test_adapter_impulse_events.py`,
  `tests/test_template_deconvolved_troughs.py` with
  `TEMPLATE = {"name": "deconvolved_troughs", "kind": "detection", "version": 1, …}` =
  `preprocessing.detrend` (long window) → `detection.deconvolve` → `detection.impulse_events` →
  `interrogation.event_shape` → `interrogation.intervals`.

## Acceptance

- [ ] **Solver fidelity without the authors' code:** on small random AR(1) problems the thresholded/ℓ1 OASIS solution
      equals a generic solver's solution of the same optimisation (e.g. a non-negative least-squares or bounded QP
      formulation with scipy) to 1e-6. Noise-free input with known jumps is recovered exactly.
- [ ] 12 h at 1 Hz with 30 troughs (instant drop, exponential recovery, half-time 120 s), **including 8 pairs where the
      second trough starts before the first has half recovered**, + noise: every onset found within ±2 samples, each
      overlapping pair as **two** events. Show in the test that `detection.signal_threshold` on the same trace merges
      those pairs (the reason the block exists).
- [ ] `recovery_half_s = 0` estimates γ within 20 % of the truth on that trace.
- [ ] Scaling the input ×1000 leaves the Scores and the spans unchanged.
- [ ] Linear in length: 2.6 M samples in seconds (measure; report the figure).
- [ ] The template runs end to end through `execute_recipe` and writes its spans to `detections`.
- [ ] Both blocks pass `tests/test_block_standard.py` and `tests/test_adapter_spec.py`.

In your report, say how well an AR(1) kernel fits a **sharkfin** (drop → floor/plateau for half to two-thirds of the
interval → slow climb) on a synthetic example, and what the residual looks like — the plan expects the misfit to be
informative, not hidden.
