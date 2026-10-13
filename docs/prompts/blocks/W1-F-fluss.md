# W1-F — `detection.fluss`: where the recording changes behaviour (matrix profile VIII, Gharghabi et al. 2017)

Read [`00-common.md`](00-common.md) first. Commit prefix **`w1-f:`**. Plan: `docs/research/analysis-blocks-from-literature.md`
§5 row 6; facts: `docs/research/analysis-blocks-primary-sources.md` §13a (read it: stumpy differs from the paper in
three places).

## In plain words

For every short stretch of the recording, the matrix profile knows which other stretch looks most like it. Draw an
arc from each stretch to its look-alike. Inside one "regime" of behaviour the arcs stay inside it; at a change of
behaviour few arcs cross. Count crossing arcs at every point, correct for the middle always getting more arcs than the
ends, and the dips are the changes. The block outputs a **regime-change score** — 1 − CAC, so 0 = no change and high
= a change — which the existing `detection.threshold` cuts into one span per change.

## The algorithm

1. Matrix profile **index** I for window m (z-normalised). Reuse the site's existing matrix-profile computation
   (`Adapters/detection_matrix_profile.py` imports it from `Pipelines/matrix_profile/run_matrix_profile.py`; its
   result carries `mpi`), or `stumpy.stump` directly if reuse is impractical — say which and why.
2. `stumpy.fluss(I, L=m, n_regimes, excl_factor, custom_iac)` → CAC. **Pass the index, not the distances** (stumpy's
   own docstring examples get this wrong).
3. Differences from the paper to set deliberately (a `iac` param: `parabola` = the paper's 2i(n−i)/n, default;
   `beta` = stumpy's fitted curve): stumpy blanks 5·L at each end (the paper L) — keep stumpy's and say so, or pass
   your own; document which.
4. Output Scores = 1 − CAC, one value per sample of `x` (CAC has n − m + 1 values: pad the tail with NaN as
   `detection.matrix_profile` pads, and check that `detection.threshold` treats NaN as "no span").
5. `meta`: m, the CAC minimum, FLUSS's own regime locations for `n_regimes` (the paper's extraction with its 5·L
   exclusion), the rules.

## Adaptations

- `window_s` (default 60 s — the 1-minute scale is the one that served spikes on rec 385), `n_regimes_readout`
  (default 3, readout only), `iac`, `excl_factor` (5).
- **Drift:** z-normalised drift ramps match anywhere, so arcs cross everywhere and the score goes flat — the block
  fails safe (no change found) rather than inventing one. The description says to detrend first.
- **Cost:** O(n²) like the matrix profile — declare `estimate` with the matrix-profile cost model
  (`Working/Detection/matrix_profiling/cost.py`, as `detection.matrix_profile` does) and refuse spans the
  interactive ceiling cannot hold the way that block does (`max_span_samples_for_background`).

## Deliver

- Core wrapper (e.g. `Working/Detection/matrix_profiling/fluss.py`) and `Adapters/detection_fluss.py`, Signal →
  Scores, `category="detect"`, `page_name="FLUSS regime change"`.
- Tests `tests/test_fluss.py`, `tests/test_adapter_fluss.py`, `tests/test_template_fluss_regimes.py` with
  `TEMPLATE = {"name": "fluss_regimes", …}` = `preprocessing.detrend` (`rolling_mean`, 600 s) → `detection.fluss`
  (60 s) → `detection.threshold` (a cut you calibrate on the synthetic regimes; use its `min_duration_s` /
  `merge_gap_s` if they help).

## Acceptance

- [ ] Two synthetic regimes of 2 h each at 1 Hz (regime A: sharkfin-like drops every ~15 min; regime B: symmetric
      bumps every ~5 min; plus noise): the score peaks within ±2·m of the boundary and the template returns exactly
      one span there.
- [ ] A single regime of 4 h: no span at the template's cut.
- [ ] A pure drift ramp + noise: the score stays low (fails safe) — pin it.
- [ ] `iac=parabola` and `iac=beta` both run; the docstring says how they differ.
- [ ] The estimate is declared; the block passes `tests/test_block_standard.py` and `tests/test_adapter_spec.py`;
      the template runs end to end.
