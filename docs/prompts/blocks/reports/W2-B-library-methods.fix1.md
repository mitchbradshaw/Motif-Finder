> Filed by the manager session, 2026-10-14 11:07 — the final message of implementer agent `ab19ca872abbd930c`,
> resumed for fix round 1 against `W2-B-library-methods.critic.md`, verbatim.

# W2-B fix round 1 — report

Every item (1–8 and the docs) is fixed, test-first, in my worktree. I have not merged or rebased. The full gate passes.

**Before you merge:** at the Library's size and at 15 % background noise, the HDBSCAN null you specified flags real families as `noise_like` — the separation test is the cause, not the size test (details under the timings). The k-Shape null does not have this problem.

Gate, run with `webui\.venv` python, `-n 4`, 13 files: `test_sbd`, `test_library_coherence`, `test_library_grouping`, `test_library_grouping_methods`, `test_library_schema`, `test_database`, `test_review_schema`, `test_webui_library`, `test_distances`, `test_block_standard`, `test_adapter_spec`, `test_import_boundaries`, `test_templates`. Result: **516 passed, 3 xpassed, 0 failed**.

## What changed, by item (red → green)

| Item | Red | Green | Change |
|---|---|---|---|
| 1 + 2 (blockers) | `a83c0bb` (38 failed) | `7d805b7` | Surrogate null; flags carried to the editor and Library |
| 3 | `fe7fcb4` (8 failed) | `8accc92` | Cost estimate and refusal before the run |
| 4 + 5 | `4531cb1` (5 failed) | `808f742` | Coherence alignment, null and squared variant |
| 6 | `d723576` (1 failed) | `ae56c77` | HDBSCAN `cut` renamed `epsilon` |
| 7 + 8 | `096a2e7` (3 failed) | `cb48a89` | `_family_coherence` fixes; stale docstring |
| Docs | — | `d68f84d` | `LIBRARY_STORAGE.md` §6 / 6.1 / 6.2 |

Each red commit touches only `tests/` and its body shows the failures.

Test expectations I changed on purpose (each stated in a commit message):
- k-Shape's `omit_d` default is now 0.
- `groupings` gains a column, so the column-set test changed.
- The HDBSCAN three-family test reads the flags instead of the removed floor.
- The HDBSCAN confidence test accepts 2 families. HDBSCAN's default selection keeps the sharkfin and square together at 90 members; every family it finds must still be confident.
- `top_share` is now the σ² share.

**Items 1 + 2 — the surrogate null, and flags that reach the Library**
- **Surrogates:** `kshape.phase_randomised_rows` keeps each row's amplitude spectrum (its colour) and randomises the phases (its shape). It is seeded.
- **HDBSCAN:**
  - Repeats the fit on 3 surrogate draws of the fitted vectors, same distance and settings.
  - A family is confident only if its separation AND its fitted size beat the largest seen in any draw.
  - Otherwise `noise_like: true`; `unstable: true` when it is the separation that fails.
  - `UNSTABLE_SEPARATION` is gone. Separation is still reported, but no longer decides.
- **k-Shape:**
  - `omit_d` 0 = automatic, and 0 is the default.
  - Per family, the threshold is the 5th percentile of surrogate distances to that family's centroid. A surrogate counts toward the centroid it lands nearest; if fewer than 20 land, all surrogates are used.
  - Members beyond the threshold are omitted as `past_cut`.
  - A family is `noise_like` if its members' median distance is not below that 5th percentile, and `unstable` if not below the null's median.
  - A fixed `omit_d` > 0 still works; its help text says 0.5 almost never fires on the shape-distance scale.
- **Engine:**
  - `Family.flags` and `GroupingResult.fit_summary` (JSON-safe).
  - A method with no null (Ward) reports `tested: false` and says why.
  - The `omit_d` default now comes from each method (Ward 0.5, k-Shape 0).
- **Schema:** `groupings.fit_summary_json`, nullable, added through `init_db`. Idempotent, and tested on an old database.
- **Bridge:** see the payload fields below.
- **Tests:** pure noise (AR(1) φ 0.95 / 0.99, random walk, drift × 2 seeds × both methods) gives every family `noise_like`. Three shifted families on 4 backgrounds give confident families for both methods.

**Item 3 — cost before the run**
- `estimate(n, params, basis)` is on every method. Ward keeps the old formula; `feature_bins` and `labels` are linear.
- `_recompute_cost(n, basis, method, params)` calls it, and `engine.cheaper_settings` lists settings that would fit.
- `run_grouping_job` counts members by SQL and estimates before starting anything. Over 15 min it returns 422; the message says there is no cluster script for groupings, and no job is started.
- k-Shape's auto-k sweep now runs one start per candidate k on the 2,000-row subsample; only the chosen k gets `n_init` starts. This is a named adaptation, recorded as `k_scores[].starts` and `payload["final_starts"]`.
- `should_cancel` was cheap to thread through. k-Shape checks it between starts and between candidate k; HDBSCAN between null draws. It raises `engine.GroupingCancelled`, and the job returns as cancelled.
- Measured coefficients are stated in each module: k-Shape 8e-4 s per row × centre × start; HDBSCAN 2e-6 + 1e-6 per pair for the square matrix, 2.5e-6 per cross pair.

**Items 4 + 5 — coherence**
- Shifted rows are now padded with their own edge value instead of zeros. `n_misaligned` counts members whose shift exceeds ¼ of the length.
- The straggler case, re-measured (60 drops, shifts up to 20 %, 2 % AR(1) background noise, plus 3 noise members): 0.42–0.43 → 0.48–0.49. It was 0.36 → 0.57 under the old cut-to-common-span rule.
- New fields beside eq. 17:
  - `null_median` and `null_p05`: the same score on 5 seeded surrogates of the members.
  - `svd_entropy_squared_norm` and `null_squared_median`.
  - `top_share`, now the σ² share of the main component (labelled in `top_share_is`).
- Measured at 2 % noise (pure family / 50–50 mix / pure noise):

| Score | Pure family | 50–50 mix | Pure noise | Null |
|---|---|---|---|---|
| eq. 17 (unsquared) | 0.425 | 0.551 | 0.880 | p05 0.86–0.88 |
| σ² variant | 0.023 | 0.230 | 0.614 | median 0.59–0.62 |

**Item 6.** HDBSCAN's `cut` is renamed `epsilon` (`cluster_selection_epsilon`).
- `assign(cut=…)` ignores the editor's tree cut; `assign(epsilon=…)` re-selects on the stored distances.
- The test now asserts a strict drop: 3 families → fewer at 0.4.

**Item 7 — `_family_coherence`**
- The cache key includes each file's modification time.
- Held-out members are counted in `heldOut`; unknown recordings in `notOnDisk`.
- The alignment anchor is the medoid, else the exemplar, else the row with the least stored distance. No 2,000² search runs inside a GET.
- A one-member family returns `reason` as text.
- The cache test counts calls instead of comparing equal dicts.

**Item 8.** The `test_sbd.py` docstring is fixed.

## New payload fields

**Engine**
- `GroupingResult.fit_summary`: rows, screened out, fitted, assigned, sample, seed, `k`, `k_rule`, `k_scores`, `null`, `family_flags` by label. HDBSCAN adds `distance` and `epsilon`.
- `Family.flags` = `{noise_like, unstable, tested, why}` plus method numbers:
  - k-Shape: `median_distance`, `null_p05`, `null_median`.
  - HDBSCAN: `separation`, `size_fitted`, `null_max_separation`, `null_max_size`.
- `null`:
  - k-Shape: `kind`, `draws`, `rows_per_draw`, `percentile`, `omit_d_by_family`, `median_by_family`, `from`, `rule`.
  - HDBSCAN: `kind`, `draws`, `families_per_draw`, `draw_families`, `max_separation`, `max_size`, `rule`.
- New method params: k-Shape `null_draws`; HDBSCAN `null_draws` and `epsilon`.

**Bridge**
- Regroup job result: `fitSummary`, and `families[]` = `{id, label, size, medoid, flags}`.
- `POST /groupings` accepts `fit_summary`; the grouping payload returns `fitSummary` (null when absent).
- 422 detail: `{message, estimateSeconds, localLimitSeconds, members, cheaper:[{change, params, seconds}]}`.
- `detail.coherence` gains `null_median`, `null_p05`, `null_squared_median`, `null_draws`, `svd_entropy_squared_norm`, `top_share_is`, `n_misaligned`, `padding`, `heldOut`.

## What W2-F must wire

1. **"No better than noise" badge.** On the atlas tile, the Family page and the editor preview, when `flags.noise_like`; tooltip = `flags.why`. Show "not tested" when `flags.tested` is false.
   - After a regroup, flags come from `result.families[]`.
   - For a saved grouping, read `fitSummary.family_flags[label]`.
2. **Save.** Send the job's `fitSummary` unchanged as `fit_summary` in `POST /api/library/groupings`.
3. **Cost refusal.** On a 422 from `POST /groupings/run`, show `detail.message` and `estimateSeconds`, and offer `detail.cheaper[]` as one-click param sets. Do not offer a cluster script.
4. **HDBSCAN epsilon.** Never wire the tree-cut slider into HDBSCAN. Its threshold is `params.epsilon`, a separate input defaulting to 0.
5. **Family-page coherence.**
   - Show `svd_entropy_norm`, with `null_median` / `null_p05` beside it as "noise like these members' scores X".
   - If `svd_entropy_norm ≥ null_p05`, say "no more coherent than noise".
   - Show `svd_entropy_squared_norm` and `top_share` labelled.
   - Draw `reason` as text, `error` as a red card, and the `heldOut` / `notOnDisk` counts.
6. **Omission labels.** Add `not_in_a_dense_family`, `infinite_values` and `missing_values` to `OMIT_REASON_LABEL` in `webui/client/src/library/chrome.tsx`.

## Re-measured timings

Synthetic: 80 % events at 15 % AR(1) noise plus 20 % pure noise; the machine was loaded by other jobs.

| Run | Estimate | Actual | Families (noise_like?) | Omitted |
|---|---|---|---|---|
| 3,603 `hdbscan` (3 null draws) | 156 s | 270 s | 1,886 (yes), 365 (yes) | 1,352 `not_in_a_dense_family` |
| 3,603 `kshape` k = 3 | 87 s | 80 s | 975 / 881 / 806 (no) | 941 `past_cut` |
| 3,603 `kshape` auto k | 483 s (upper bound) | **181 s** (was 1,115 s) | k = 2, both confident | 1,042 `past_cut` |
| 20,000 `hdbscan` | 488 s | 291 s | 10,593 (yes), 2,622 (no) | 6,785 |
| 20,000 `kshape` k = 3 | 121 s | 47 s | all confident | 5,173 `past_cut` |
| 20,000 `kshape` auto k | 621 s | 104 s | k = 2, both confident | 6,118 `past_cut` |

**Why the HDBSCAN null flags real families at this scale:**
- The real families' separation (2.3–2.7) is lowered by HDBSCAN merging two shapes into one family.
- The surrogates' tightest small crowds (36–163 members) reach a separation of 2.85–3.33.
- The size test passes easily (e.g. 1,886 vs 163); it is the separation that fails.
- At 8 % noise all three families are confident (separation 4.7–8.4 against the null's 2.4).
- The ratio is size-sensitive, so comparing a large family against the maximum over small noise crowds is biased against large families.
- A size-matched comparison would fix it. I did not change the rule you set; this is your call.
- The k-Shape null behaves well at both sizes.

**HDBSCAN estimate:** about 1.7× low at 3,603 (156 s estimated, 270 s actual) and about 1.7× high at 20,000. It still keeps both runs under the limit.

## Squared or unsquared — the question for the researcher

The coherence number asks how far a family's members are copies of one shape. Picture a choir: if everyone sings the same note the sound is "one voice"; if two groups sing different notes it is "two voices". The paper's formula (eq. 17) also counts the hiss in the room — background noise — as many tiny extra voices, and with this many members the hiss adds up. So once background noise passes a few per cent, a pure family and a two-shape mixture score almost the same, and the number can't be compared between families with different noise levels.

The squared version weighs each voice by its loudness squared, so the hiss barely counts. It still separates pure from mixed at 5–10 % noise; for example 0.07 for a pure family against 0.41 for a mixture at 5 % noise, against a noise score near 0.6.

Options:
- (a) Keep eq. 17 as the headline. It is faithful to the paper and comes with its null beside it.
- (b) Make the squared score the headline and eq. 17 the faithful footnote.

**Recommendation: (b) for the Family page** — it answers "is this one shape?" on our data. Keep eq. 17 in the payload for fidelity. Both are returned today, with eq. 17 as the headline, until the researcher decides.

## Commits (`git log --oneline 04948e3..HEAD`)

```
d68f84d w2-b: LIBRARY_STORAGE 6 -- eight omission reasons, fit_summary and family flags, the surrogate null, estimate
cb48a89 w2-b: fix round 1 item 7 -- _family_coherence: mtime in the key, held-out counted, no medoid search in a GET
096a2e7 w2-b: tests (red) -- fix round 1 items 7-8: _family_coherence cache, held-out count, no medoid search in a GET
ae56c77 w2-b: fix round 1 item 6 -- HDBSCAN epsilon (was cut); the tree cut is ignored
d723576 w2-b: tests (red) -- fix round 1 item 6: HDBSCAN's cut becomes epsilon, and the tree cut is ignored
808f742 w2-b: fix round 1 items 4-5 -- edge-padded alignment, a noise null and the squared variant beside eq. 17
4531cb1 w2-b: tests (red) -- fix round 1 items 4-5: edge-padded alignment, a noise null beside the score
8accc92 w2-b: fix round 1 item 3 -- method estimates, a refusal before the job, one-start k sweep, cancel
fe7fcb4 w2-b: tests (red) -- fix round 1 item 3: each method estimates its cost before the run
7d805b7 w2-b: fix round 1 blockers -- a phase-randomised null, and flags that reach the Library
a83c0bb w2-b: tests (red) -- fix round 1 blockers: a surrogate null, and flags that reach the Library
ad160b4 w2-b: sbd, kshape and hdbscan methods, svd_entropy coherence, family coherence
2d64d54 w2-b: tests (red) -- sbd, kshape, hdbscan, svd_entropy coherence, family coherence
```

Files touched outside my first-round list:
- `Working/database/schema.py` (the additive column).
- `Working/library/grouping/methods/ward.py`, `feature_bins.py`, `labels.py` (an `estimate` method each).
- `docs/LIBRARY_STORAGE.md`.
- `tests/test_library_schema.py`.

In `webui/server/library.py` I touched `_family_detail` / `_family_coherence`, the regroup job, the save route, the grouping payload, and a new `_grouping_item_count`.
