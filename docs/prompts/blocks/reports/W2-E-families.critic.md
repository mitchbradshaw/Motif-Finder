> Filed by the manager session, 2026-10-14 15:16 — the final message of critic agent `a313e63b52f0fea0e` on branch
> `worktree-agent-a5a91c3213452c835` (W2-E's own changes after merging main `2fd26b8`), verbatim.

# Critic report: W2-E `catalogue.shape_families` and `interrogation.event_families`

## 1. In plain words

Both blocks really do run the Library's own clustering code, so a family found here is the same family the Library would find. With HDBSCAN and pure noise, every crowd it finds carries the noise mark. That part holds.

The weak point is how long a window each event gets by default. The block reads that length off Event shape's measured duration, and that measurement is fragile. On clean drops it jumps to a 2-hour window holding about three events each. The block then reports confident families that mix different shapes, with the wrong rhythm, and gives no warning. Separately, two of the three method choices (k-Shape and Ward) produce unmarked "families" in pure noise, and Intervals then times them as if they were real.

## 2. Verdict

**merge after fixes**

## 3. Findings (most severe first)

### F1 — blocker — the automatic window length (`length_s=0`, the default) gives confident, wrong family rhythms with no warning
- **Where:** `Adapters/interrogation_event_families.py:151` (the default) and `:111-117` (meta carries no W2-A coverage warning).
- **What is wrong:** the auto length is 2 × Event shape's median `duration_s`, which is fragile on these shapes:
  - **Clean drops** (τ = 300 s, SNR ≈ 40): 63 of 88 durations come back "unmeasured". The length goes to the 7,200 s ceiling, so each window holds about 3 events.
  - **Same drops at SNR ≈ 10:** the median duration is 11 s, so the length goes to the 60 s floor.
- **How shown** (`autolen.py`), drop + square at 7,200 s:
  - Result: "3 families (sizes 32, 28, 24) … SVD entropy 0.62 (noise 0.96) …", none flagged.
  - `warnings: []`, `notes: []`.
  - Intervals then reports key `1` (unmarked) with median 2,025 s. Truth is 2,400 s for drops and 10,800 s for squares (−16 % / −81 %).
- **Anchor × length sweep** (`defaults.py`, `agg.py`): the real chain (detrend → noise_threshold → event_shape → event_families → intervals) through `execute_recipe`. 48 h; pairs shark+square, drop+square, drop+shark; AR(1) φ 0.97, AR(1) φ 0.99, random walk; 2 seeds; SNR 40 and 10. "ok" means both shapes in distinct, unmarked keys with medians within 10 %.

| anchor / length | auto (0) | 300 s | 600 s | 1200 s |
|---|---|---|---|---|
| start, SNR 10 | 5/18 | 18/18 | 18/18 | 8/18 |
| start, SNR 40 | 4/18 | 16/18 | **18/18** | 16/18 |
| onset (best length) | 7/18 at 300 s (SNR 10) | | 12/18 at 600 s (SNR 40) | |
| extremum (best length) | 6/18 at 300 s (SNR 10) | | 11/18 at 600 s (SNR 40) | |

  Mean ARI for start + 600 s: 0.87 at SNR 10, 1.00 at SNR 40.
- **Answer to the manager's question 3:**
  - `anchor="start"` is a defensible default: it beats onset and extremum in every cell.
  - `length_s=0` is not defensible. W2-A's own docstring says a waveform consumer such as families should set `length_s`.
- **Fix:**
  - Default `length_s` to 600 s in `event_families`, called a placeholder in the docstring.
  - Set it explicitly in the template.
  - When the length comes from auto, warn in `meta.warnings` and the summary if:
    - it was clamped to the floor or the ceiling;
    - more than about a quarter of windows overlap the next (`EW.overlaps_next`);
    - more than a quarter have their recovery outside the window (`EW.recovery_outside`). W2-A's adapter already warns on this; this block drops it.

### F2 — blocker for the `kshape` choice, should-fix for `ward` — unmarked "families" in pure noise reach Intervals' per-family table
- **Where:** `Working/Catalogue/shape_families.py:215-222` (`group_key` marks only `noise_like`) and the `method` choices.
- **How shown** (`nostruct.py`): phase-randomised events with Poisson-like timing, at the block's defaults, then Intervals. HDBSCAN (the default) never left an unmarked key:

| background | n | HDBSCAN placed | HDBSCAN marked `~noise_like` |
|---|---|---|---|
| AR(1) φ 0.95 / 0.97 | 80, 200, 1000 | 0–6 % | all |
| AR(1) φ 0.99 | 80, 200, 1000 | 0–30 % | all |
| random walk | 80, 200, 1000 | 36–62 % | all |

  k-Shape and Ward did leave unmarked keys. Every one is a family reported in pure noise:

| method | background | n | unmarked families (sizes) | fraction_confident |
|---|---|---|---|---|
| kshape | random walk | 1000 | 132 and 108 (`1`, `2`) | 0.24 |
| kshape | random walk | 200 | 30 and 29 | 0.295 |
| kshape | random walk | 80 | 12 + 10, and 14 + 11 + 10 | |
| kshape | AR(1) φ 0.99 | 80, 200 | 22 at n = 200, plus pairs of 10 | |
| ward | random walk | 1000 | 7–8 untested families (`1`…`8`) | None |

  For Ward on white noise with `ward_cut=1.0`, the summary reads "1 family (sizes 37) … not tested against noise", and Intervals keys it `1`.
- **Fix:**
  - Ward: give an untested family a suffix too (e.g. `<n>~untested`, through `group_key(family, noise_like, tested)`), and say so in the group rule.
  - k-Shape: its null is W2-B's, so the fix belongs there (hand it to W2-B). Until then, either leave `kshape` out of `event_families`' choices or key its families `~untested`.

### F3 — should-fix — `coherent_beyond_noise` is re-derived without main's margin and says "coherent" for pure noise
- **Where:** `Working/Catalogue/shape_families.py:393` (`bool(norm < p05)`), `:468` (warnings) and `:423` (rule text).
- **What is wrong:** main `4db3684` added `beyond_noise = score < 0.9 × null_p05` to `svd_entropy`. This branch merged `2fd26b8`, so it predates that commit and re-derives the verdict itself.
- **How shown:** across every family found in my no-structure runs, 37 of 46 read `coherent_beyond_noise = True`. Their score / p05 ratios were 0.945–0.999, so none would pass the 0.9 margin.
- **Fix:** merge main, read `c["beyond_noise"]`, and print coherence's own `RULE` (which carries the margin and the smooth-shape caveat) in place of the local sentence. This is the one place where something is re-derived that should be read off W2-B.

### F4 — should-fix — the template marks its real sharkfin family as noise, and its test cannot notice
- **Where:** `tests/test_template_event_families.py:57` (no `length_s`) and `:128-138` (never checks the key suffix).
- **How shown:**
  - Reproduced the follow-up: at the auto window (150 s here) the summary reads "1 noise-like … family 1", family 1 having 72 members (2.10 × the null's p05).
  - In my sweep the template case at start + auto gave key `1~noise_like` in 2 of 6 SNR-40 runs.
  - At 300 and 600 s the families are unmarked in every run.
- **Fix:** add `"length_s": 600.0` to the template step. Assert that neither family's key contains `~noise_like`.

### F5 — should-fix — the no-structure tests do not cover defaults, larger n or Intervals' keys
- **Where:** `tests/test_adapter_event_families.py:184-196` and `tests/test_shape_families.py:129-139`.
- **What is wrong:**
  - The adapter test uses non-default `length_s=140, pre_frac=0`, at n = 80 only.
  - The prompt's "HDBSCAN puts most in no family" is false for random-walk events at defaults: 54–62 % placed at n = 200, 46–53 % at n = 1000. Those families are all flagged, so the downstream claim holds.
- **Fix:**
  - Test at defaults, at n = 200 and 1000, across AR(1) φ 0.95–0.99 and a random walk.
  - Assert "no Intervals key without `~noise_like` / `~untested`" rather than a placed fraction.
  - Run the same check for each method offered.

### F6 — nit — `family_omit_reason = "no_window"` hides the cutter's reason
- **Where:** `shape_families.py:351`.
- **How shown:** with 14 % NaN, all 37 events are `no_window`. The summary does not say "too much NaN"; only `meta.window.omitted` does.
- **Fix:** use `no_window:<cutter reason>` in the column, or name the reasons in the summary.

### F7 — nit — the estimate
- **Ward past its cap:** the estimate returns 96.7 s at 722 h (8,664 assumed events), while `run` refuses past 5,000.
- **The one-event-per-300 s assumption over-estimates sparse chains**, which is the safe direction. At 120 h, 1 Hz, with the machine loaded:

| method | events | estimate | fresh | warm |
|---|---|---|---|---|
| hdbscan | 1,432 | 10.0 s | 11.4 s | 8.4 s |
| hdbscan | 179 | 10.0 s | 2.1 s | 0.2 s |
| ward | 1,432 | 5.7 s | 1.8 s | 1.4 s |

  The estimate tracks the actual cost at 1,432 events. At 179 it over-estimates 5–50×, which is acceptable. Import is 20–74 s depending on load, and is not counted.
- **Fix:** have `_estimate` raise or return the refusal for Ward past `WARD_MAX_ITEMS`.

### F8 — nit — param bounds
- `ward_cut` max is 1000 on a roughly 0–1 distance.
- `hdbscan_min_cluster_size` and `kshape_n_init` have min 0. The methods clamp these silently (probed: 0 and 1 run without error).
- Tighten to ward_cut ≤ 2, min_cluster_size ≥ 2, n_init ≥ 1.

### Checked and fine (the manager's question 4 and the rest)
- **One implementation, two surfaces:** `shape_families` calls `engine.run_grouping(items, unit="single_motifs", basis="shape-distance")` with honest item dicts. Flags, `fit_summary`, medoids and distances are read off the engine. `test_ward_reproduces_run_grouping_exactly` pins partition, omission reasons, medoids and distances, so it would fail on a wrong implementation. The only re-derivation is F3. The NaN gap-filling adaptation is stated in the docstring.
- **`write_group_columns` refactor:** behaviour is identical to the old inline code (`str(g)` and `.astype(str)` give the same strings; same `group_upstream`). `test_adapter_trains` passes 16/16 alone. Its linear-time test failed once under `-n 4` load (1.73 s against a 1.5 s limit), the same flake the implementer saw.
- **`BOOKKEEPING_COLUMNS`:** the five additions are correct; all are answers or labels, not features.
- **`~noise_like` suffix:** a sound idea. It needs the untested counterpart (F2).
- **Exemplars:** `{"<label>": index}` plus `exemplar_rule`, each the medoid member. `labels[index] == label` holds. Note that the serializer in this branch still picks its own exemplar (nearest centroid in feature space) until W2-F's `_named_exemplars` lands.
- **Flattened `<method>_<param>` ParamSpecs:** they mirror the registry's params and choices.
- **Edge cases** (empty, single event, events at the span edges, constant, NaN 5 % / 14 %, inf, mostly-events): all give honest summaries and `omitted` counts. `json.dumps(meta, allow_nan=False)` passes.
- **Process state:** no global RNG and no numba state touched in the new code.
- **Test-first:** `e194e43` and `2e98666` touch only `tests/`, and their messages show the red state. Out-of-list files (`intervals.py`, `interrogation_trains.py`, `windowset.py`, the three test pins) are justified. Nothing from the do-not-touch list is edited.

## 4. What I ran
Everything ran from the worktree or scratch with the conda python. The machine was loaded throughout (my sweeps ran in parallel), so timings are indicative.

- **Tests:** `pytest -n 4` on the four W2-E test files plus trains, intervals, event_windows, block_standard, adapter_spec, import_boundaries and templates: **346 passed, 1 failed** (the trains timing flake) in 152 s. `test_adapter_trains.py` alone: 16 passed.
- **`nostruct.py`:** phase-randomised events (AR(1) φ 0.95, 0.97, 0.99, random walk) × n = 80 and 200 (3 seeds) and n = 1000 (2 seeds) × hdbscan, kshape and ward, at defaults, then Intervals. 96 runs; results in F2, F3 and F5.
- **`defaults.py`:** 432 chain runs through `execute_recipe`: 3 shape pairs × 3 backgrounds × 3 anchors × 4 lengths × 2 seeds × 2 SNRs. Results in F1 and F4.
- **`autolen.py`:** the auto window length and the meta warnings per pair (F1).
- **`edge.py`, `bounds.py`, `specs.py`:** edge cases, param bounds, the ParamSpec dump.
- **`est.py`, `timing.py`:** estimates at 12, 48, 120 and 722 h, and estimate against actual at 120 h (F7).
- Scratch files are in `C:\Users\mmebr\AppData\Local\Temp\claude\C--Users-mmebr-Documents-CNN\9b41764a-ced2-4e05-857c-547103bce7fb\scratchpad\critic_w2e`.
