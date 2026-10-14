> Filed by the manager session, 2026-10-14 22:49 — the final message of implementer agent `a7834e530174e1643` on
> branch `worktree-agent-a7834e530174e1643` (`8ac94c3`, `b94881b` on `01cb8c3`), verbatim.

## W3-B report: `interrogation.cycle_shapes`

### 1. In plain words

**What the block does.** Picture a drummer whose tempo drifts. A chain of drops is that drummer, and each stretch from one drop to the next is a beat, or "cycle". The block:
- cuts every cycle out of the raw recording;
- removes the slow drift under it by subtracting a straight line between the level just before this drop and the level just before the next one;
- stretches every cycle to the same length and lines them up;
- asks one question: is this one kind of beat that varies, or several kinds? If several, it reports where in the chain the kind changes.

For each cycle it also measures two things:
- how long the trace sits on its floor (the sharkfin plateau);
- where in the cycle it is half way back up.

Finally it checks the whole stack against pseudo-cycles cut from the recording's own quiet stretches. That is the "is this better than noise?" test.

**What it found on synthetic data.** The noise was coloured (a random walk, AR(1) and slow drift) at 15 % of the drop size.
- **60 sharkfins then 60 troughs, period drifting 20 → 60 min:** two groups every time (adjusted Rand 0.90–1.00). The change was at cycle 60, order test p = 0.001, and both entropies beat the background.
- **One sharkfin whose plateau lengthens steadily (0.3 → 0.7):** one group, with the drift visible in the floor fraction (Kendall τ > 0.4).
- **Poisson events on noise (400 and 1,000 cycles), and a phase-randomised chain at the real event times:** one group, no better than noise, every key marked.
- **Floor fraction:** sharkfins 0.56–0.58 (median), troughs half back by 0.06.

**The most important finding.** SigClust, the gate the prompt prescribed, rejected "one Gaussian" on every synthetic set, including pure noise and the steadily drifting plateau. On its own it would have invented families everywhere. I added a second gate, which every split must also pass: the split has to show two modes along its own direction. That gate is what decides K here.

### 2. Files

Created:
- `Working/interrogation/cycle_shapes.py` — the core.
- `Working/background_null.py` — the generic sampler.
- `Adapters/interrogation_cycle_shapes.py` — the adapter.
- `tests/test_cycle_shapes.py` (39 tests), `tests/test_background_null.py` (7), `tests/test_adapter_cycle_shapes.py` (13), `tests/test_template_chain_cycles.py` (4).
- `tests/_cycle_synthetic.py` — the shapes and backgrounds (outside the deliver list; a test helper, as wave 2's were).

Modified:
- `Working/types/windowset.py` — six names added to `BOOKKEEPING_COLUMNS`, not two:
  - `cycle_index` and `cycle_group`, as the prompt asked;
  - `cycle_change`, `cycle_omit_reason` and `cycle_corr`, which are this block's decisions (`cycle_corr` plays the part of `family_distance`);
  - `cycle_shift_s`, which is geometry, like `anchor_offset`.
- **Out of scope:**
  - `Adapters/base.py`: `SideInputSpec.required` (default True).
  - `Working/side_inputs.py`: an optional side input left unbound is skipped. Without this the brief's "unbound → cut from x" cannot run, because the executor fails loudly on any unbound side input.
  - `tests/test_adapter_spec.py`: the shipped-adapter count goes 54 → 55.
  - `tests/test_adapter_event_windows.py`: its exact `BOOK` set now includes the six names.

### 3. The algorithm as implemented

1. **Event times, sequences and cycles.**
   - Event times: `onset_idx` when present (`anchor="onset"`), else the span start.
   - Sequences: by `train_id`, else `group`, else the whole span. Events in no train open no cycle.
   - Cycle k runs from anchor k to anchor k+1.
2. **Gaps and splits (`max_cycle_s` / `min_cycle_s`, 0 = auto).**
   - A cycle longer than 1.6 × the running median of the 11 cycle lengths around it is a gap (`gap_long`).
   - One shorter than 0.4 × that median, or under 8 samples, is a split drop (`too_short`).
   - Both are left out and counted.
   - Why local and not the brief's suggested 3 × the sequence median: on a 20 → 60 min chain, 3 × the median keeps a missed detection (about 2 × the local length) anywhere.
   - Sweep: chains of 30 and 120 cycles, each with 5 missed detections and one split: every double and the split were caught, and no true cycle was lost. Poisson events lose about 53 % of their cycles — by design, because they are not a chain.
3. **Waveform and chord detrend.**
   - The waveform comes from the side input, else from x.
   - **Departure from the brief:** the chord's end levels are the median of the 2 % just *before* each anchor, not the cycle's own first and last samples. An onset anchor sits 20–40 s into the drop, so the cycle's first samples are mid-drop, not pre-drop.
   - A cycle more than 10 % NaN is left out; less is interpolated.
4. **Warp.** `resample_to_length` to 256 points, then z-normalised. `cycle_amplitude` (stored unit) and `cycle_length_s` are kept as columns.
5. **Refinement.**
   - Each round lines every cycle up with the median template, a shift of at most 10 % of its length, moves its anchor by that shift, then re-cuts and re-warps.
   - No anchor moves more than 10 % of its cycle in total.
   - A round is kept only if the entropy (eq. 17) falls by more than its bootstrap SD (5 resamples). At most 8 rounds.
   - On every synthetic set it stopped after round 1: the anchors already were the phase.
6. **Align.**
   - Bounded zero-padded cross-correlation, first to the median template and then to the medoid (highest summed correlation). Vacated samples are filled with the row's edge value.
   - After grouping, each group is lined up again to its own medoid.
7. **Grouping.** Each part is a departure from the paper, with a measurement behind it:
   - **k-means runs on the warped, unaligned stack.** Aligning a two-shape mixture to one template split the troughs into shifted and unshifted subgroups (44/16, 47/13).
   - **Gate:** the 2-means split (50 replicates) must pass both:
     - **SigClust:** the split's cluster index against a Gaussian with the stack's eigenvalues, floored at σ_N² = (MAD/0.6745)². The null has the stack's rank, min(n−1, d), not d. 100 draws.
     - **Mode test:** the cycles' positions along the split direction must split better than uniform samples of the same size (the uniform is the least favourable one-mode shape, as in the dip test's calibration). 200 draws.
   - **K by bisection, not Calinski–Harabasz.** A group is split again only if the split passes both tests at α·(n_node−1)/(n−1) (Kimes et al. 2017) and both halves hold at least `min_cycles`; at most `k_max`; then one Lloyd pass.
   - CH is still reported (`k_ch`). On a random walk CH chose 3 (ARI 0.71) where the bisection kept 2.
   - The k-means is a plain numpy Lloyd. sklearn's took about 7 ms per run in thread start-up.
8. **Change points.** A change is a group change from the previous used cycle. Run lengths are reported, and the order test is runs against 1,000 shuffles. It tests order, not shape; the meta and rules say so.
9. **Plateau.** Measured on the warped, chord-detrended cycle after a 5-point running median.
   - `cycle_floor_frac`: from the first sample in the lowest 25 % of the cycle's range to the last one before the climb's top.
   - The "before the climb's top" limit exists because with late anchors the next drop sits at the cycle's end and was being read as more floor (floor = 1.0 on the template test).
   - `cycle_half_recovery_frac`: the first point half way back to the chord. NaN (counted) when it never gets there.
10. **Coherence.**
    - σ² is shown first and eq. 17 beside it, at three points: fixed cuts, after warping, after alignment.
    - `svd_entropy` runs with `align=False`: the stack is already aligned, and its unbounded SBD alignment would line noise up more than the nulls get.
    - Three nulls:
      - background (20 draws through the same chord, warp, refinement and alignment; per group, random subsets of the group's size);
      - trend-kept, shown with `SMOOTH_CAVEAT`;
      - plain phase.
    - **Verdict departure.** The verdict stays on eq. 17, as decided. But `beyond_noise` is now: eq. 17 below every draw AND more than 3 robust SDs below the draws' median.
    - Why: the Library's rule (score < 0.9 × null p05) failed a clean two-shape chain at z = 19, because cycle eq. 17 values sit at 0.86–0.96. That margin is kept in meta as `beyond_noise_margin`.
    - Group keys follow `~noise_like` / `~untested`. With several trains the key is `t<train>:<g>`.

**Where σ² and eq. 17 disagree** (the re-measure the researcher is waiting for). Whole-stack verdicts against the same background null:

| Set (noise) | eq. 17 | σ² |
|---|---|---|
| two shapes, AR(1), 0.5 | fails (z 0.9) | passes (z 4.6) |
| two shapes, drift, 0.5 | fails (z 1.4) | passes (z 7.2) |
| two shapes, drift, 0.3 — trough group only | fails | passes |

- There was no case where eq. 17 passed and σ² failed.
- Both fail on Poisson noise (z −1.8 to 0.6) and on the phase-randomised chain (z −2.5 / −2.7).
- The 0.9-margin rule failed nearly every structured set (it passed only on the random walk).

**The choice of null** (AR(1), 30 % noise, real stack against each null's median):

| Shape | real eq17 / σ² | background | trend-kept | plain phase |
|---|---|---|---|---|
| sharkfin | 0.916 / 0.531 | 0.956 / 0.838 | 0.922 (p05 0.921) / 0.563 | 0.920 / 0.684 |
| hump | 0.911 / 0.496 | 0.953 / 0.825 | 0.913 (p05 0.912) / 0.530 | 0.908 / 0.577 |

The trend-kept null calls both shapes noise, and the plain phase null calls the hump noise. Only the background null sees either.

**Other measured facts:**
- σ² falls after warping on every background. **eq. 17 does not:** on AR(1) and drift it rises (0.863 → 0.874).
- Whole-stack alignment of a two-shape mixture raises σ² slightly (0.449 → 0.488). The per-group alignment is the meaningful one.

**Background sampler contract** (`Working/background_null.py`):
- `sample_background(trace, avoid, lengths, count, seed, *, fs=None) -> BackgroundSample(starts, lengths, windows, report)`.
- `avoid`: half-open `(start, end)` ranges in the trace's frame. NaN samples are avoided automatically.
- Each window length is drawn uniformly, with replacement, from `lengths`. The start is uniform over every placement that fits entirely in a free stretch.
- A window that fits nowhere free is cut at a uniform place in the whole trace and counted. One longer than the trace is not cut.
- Windows may overlap one another. The generator is seeded and never touches numpy's global state.
- `report`: `n_wanted, n_cut, n_fallback, fell_back, n_too_long, background_samples, background_s (None without fs), trace_samples, rule`.

**`meta["cycle_stack"]` form:**
`{"n_points": 128, "n_rows": ≤200, "n_cycles": int, "sampled": bool, "seed": int, "time_unit": "seconds from the span start", "rows": [{"event": int, "sequence": key, "group": int, "start_s": float, "length_s": float, "before": [128 floats], "after": [128 floats]}]}`
- "before" is the warped, unaligned z-normalised cycle; "after" is the same cycle lined up to its group's medoid.

**Exemplars:** `meta["exemplar_events"] = {"<group key without suffix>": <event index>}` plus `exemplar_rule` (the group's medoid, a member). It is not routed through the families serializer: the meta has no `families` key.

**Where a page should show the flags:**
- `meta.summary` (σ² first);
- `meta.warnings` (background fallback);
- `meta.omitted`;
- per sequence:
  - `sigclust.p` and `sigclust.bimodality.p`;
  - `splits`;
  - `whole.verdict` and `whole.nulls` (trend-kept carries its caveat);
  - each group's `key`, `coherence.verdict`, `floor_trend`;
  - `n_half_recovery_unmeasured`.
- `meta` is plain JSON with no NaN (a test pins this).

### 4. Tests

- **Red commit `8ac94c3`:** two collection errors (`Working.background_null` and `cycle_shapes` missing); 9 errors and 1 failure in the adapter tests (unknown adapter, bookkeeping); 3 template failures (unknown adapter); the event-windows bookkeeping set failed.
- **Green:** 387 passed (my 63 plus `test_block_standard`, `test_adapter_spec`, `test_import_boundaries`, `test_templates`, event_families, trains, side_inputs, event_windows).
- **What the tests pin:**
  - every acceptance item above, on all three backgrounds;
  - the uniform being the least favourable shape for the mode test;
  - the fast entropy matching `svd_entropy` to 1e-9;
  - bounded shifts;
  - cancel raises `RecipeCancelled`;
  - the template end to end, with the waveform bound and unbound.
- Checked against broken implementations:
  - without the mode gate, the plateau test fails (it asserts SigClust < 0.05 with K = 1);
  - with an always-true verdict, the Poisson tests fail;
  - with the waveform ignored, the waveform test fails.
- `tests/test_webui_*` were not run; none were changed.

### 5. Integration snippets

**Template** (`webui/server/templates.py::CANONICAL`, using the server's `_step`):
```python
{"name": "chain_cycles", "kind": "interrogation", "version": 1,
 "description": "The shape of every cycle of a chain of drops, and where it changes: baseline removal → noise threshold (every stretch more than 4 σ_n below the detrended trace's median, as the noise_threshold template) → Event shape (drops) → Trains (MaxInterval at chain-scale gaps: a train begins at a gap ≤ 1.5 h, continues while gaps ≤ 3 h, trains < 3 h apart merge) → Cycle shapes (each drop-to-drop cycle cut from the raw recording, its drift removed by the chord between its two pre-drop levels, stretched to one length, lined up and sorted into shapes; more than one shape only when the split is two modes, not one shape that varies; each shape becomes its group, marked ~noise_like when no more coherent than pseudo-cycles cut from the recording's quiet stretches) → Intervals (the rhythm of each cycle shape). Read each group's mark before its rhythm. Tune Cycle shapes' max_cycle_s first if many cycles are left out as gaps.",
 "steps": [_step("preprocessing", "detrend", {"mode": "rolling_mean", "window_s": 600.0}),
           _step("detection", "noise_threshold", {"k_sigma": 4.0, "direction": "below", "min_duration_s": 30.0, "merge_gap_s": 60.0}),
           _step("interrogation", "event_shape", {"polarity": "drop"}),
           _step("interrogation", "trains", {"rule": "maxinterval", "mi_begin_gap_s": 5400.0, "mi_end_gap_s": 10800.0, "mi_min_ibi_s": 10800.0, "mi_min_duration_s": 0.0}),
           _step("interrogation", "cycle_shapes", {"write_group": True}, side_inputs={"waveform": {"source_kind": "root_signal"}}),
           _step("interrogation", "intervals", {})]}
```
- Waveform choice: the root signal with the chord, not an earlier long-detrended step. The chord already removes the drift per cycle, and a rolling mean as long as the longest cycles still bends their floors.
- Measured: from the 600 s trace, sharkfins read half back at 0.16 of the cycle (as troughs); from the raw trace, 0.69.

**Glyph** (`BY_NAME`):
```tsx
'interrogation.cycle_shapes': () => <g><polyline points="2,4 4,11 12,11 17,4 19,11 25,11 34,4 36,11 38,6 42,4" fill="none" stroke={G} strokeWidth={1} strokeLinejoin="round" />{[2, 17, 34].map(x => <line key={x} x1={x} x2={x} y1={2} y2={13} stroke={AM} strokeWidth={0.8} />)}<polyline points="4,16 6,23 22,23 38,16" fill="none" stroke={B} strokeWidth={1.3} strokeLinejoin="round" /><polyline points="4,16 6,22 18,22 38,16" fill="none" stroke={B} strokeWidth={0.8} opacity={0.55} /><rect x={39} y={15} width={3} height={4} fill={GR} /><rect x={39} y={20} width={3} height={4} fill={B} /></g>,
```
In words: a grey chain of unequal cycles, with amber anchor ticks; below it, two cycles stretched to one width and overlaid in blue; green and blue group swatches.

**Smoke states** (`zz_analyse_run.json`): the same shape as `w2-event-families-*`:
- a chain state that imports `template-chain_cycles`, runs, and waits for `[data-testid="row-plot-4"] svg[data-render="spanset"]`;
- a block state on `analyse/block/4` expecting `[data-testid="block-view"]` and `[data-view="spanset"][data-modifier="spanset->spanset"]`, absent `generic-process` and `render-error`, with `"rule9": true`.

**COSTED:** add `"interrogation.cycle_shapes"`.
- It declares a `register_cost_model` with exponent 1.4, scaled to an assumed one cycle per 1,800 s of span.
- Measured on 400 cycles at the defaults: 55 s fresh, 53 s warm; imports took 21 s on a loaded machine.
- 1,000 Poisson events took 20–83 s depending on load.
- The estimate with exponent 1 said 29 s; 1.4 fits the measurement.

### 6. Open questions and risks

- **Merges and integration (manager):**
  - `webui/server/chain.py:56` should pass `"required": s.required`, so the insert modal stops showing "needs waveform" as mandatory.
  - The adapter count in `test_adapter_spec.py` and the `BOOK` set will conflict with sibling wave-3 merges.
- **Please check on real recordings:**
  1. The share left out per reason (`gap_long` / `too_short`) on rec 3, rec 6, rec 542, rec 543 and rec 2. If it is above about 20 %, the 1.6 / 0.4 factors are too tight for real jitter.
  2. `background.fallback_share`. Dense chains filling the span force random cuts, and the verdict then means "phase-locked versus random phase", not "versus quiet".
  3. The floor fraction on rec 2 against rec 3.
  4. Whether SigClust ever accepts on real data. I expect it never does, which would leave the mode test carrying K.
  5. Cost on the 10 Hz chains.
- **Detector fact:** at 10 % AR(1) noise, the 600 s `noise_threshold` found only 20 of 60 synthetic sharkfins. The template test therefore uses 5 % noise. Real sharkfin chains may under-detect the same way.
- **Defaults that are placeholders:** `floor_band` 0.25; the gap / split factors; `VERDICT_SPREADS` 3; `min_cycles` 10, which is also the smallest group a split may make.
- **For the researcher:**
  - Accept or veto the second gate (two modes along the split), which goes beyond SigClust.
  - Accept or veto the spread-based verdict in place of the 0.9 margin.
  - The per-group background null is a random subset, which favours the group (stated in the rules).
  - `should_cancel` raises `RecipeCancelled`; there is no `on_progress`.
- **Run-time warning:** the test file takes about 6 minutes under load (the 1,000-cycle test about 80 s).

### 7. Commits

```
b94881b w3-b: interrogation.cycle_shapes and the background-null sampler
8ac94c3 w3-b: tests - cycle shapes, the background-null sampler, the chain_cycles template
```
