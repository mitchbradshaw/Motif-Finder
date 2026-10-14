> Filed by the manager session, 2026-10-14 09:14 — the final message of implementer agent `ab19ca872abbd930c`
> (branch `worktree-agent-ab19ca872abbd930c`), verbatim.

# W2-B report: Library methods `kshape` and `hdbscan`, the `sbd` distance, and `svd_entropy` coherence

Branch `worktree-agent-ab19ca872abbd930c`. My worktree started at 3cc2f62, so I fast-forwarded it to 04948e3 first. There are two commits on top of that.

## 1. In plain words

The Library sorts events into families of similar shape. Ward, the method it uses now, compares two events point by point. So two copies of one event, cut a few seconds apart, look like different shapes. It also has to put every event in some family.

- **Shape-based distance (`sbd`).** Before comparing two shapes, it slides one along the other until they line up best. It never wraps one end round to the other.
- **`kshape`.** Builds families with that sliding comparison. On synthetic data it recovered all three families almost perfectly; Ward did much worse:
  - The data: three shapes (a drop with a slow recovery, a sharkfin, a square pulse). Each copy was moved by up to 20 % of its window and rescaled, on four coloured backgrounds.
  - Agreement with the true families (adjusted Rand index, where 1 is perfect): k-Shape 0.93–1.0; Ward 0.21–0.44 on the same vectors.
- **`hdbscan`.** Looks for crowds of similar shapes and leaves stragglers out as "no family" (`not_in_a_dense_family`). You don't choose a number of families.
  - With 30 % pure-noise windows added, it found the three families exactly and left out 97–100 % of the noise.
  - On pure noise:
    - **White noise:** no family at all.
    - **Strongly coloured noise:** it can find two "families", made of windows that mostly drift up and windows that mostly drift down. Those are flagged unstable, never presented as confident.
- **`svd_entropy`.** One number per family: low means the members are copies of one shape, higher means a mixture. Amplitude does not enter.
  - Exact copies score 0.
  - A 50/50 mix of two shapes scores clearly higher.
  - Lining members up first lowers the score for shifted copies, from 0.47 to 0.04.
  - **Weak point:** with the paper's formula, background noise above a few per cent makes a pure family and a mixture score almost the same (measured in section 6).

## 2. Files

Created:
- `Working/library/grouping/methods/kshape.py`: the k-Shape algorithm (`kshape_fit`, `kshape_predict`, `choose_k`), the `KShapeMethod`, and helpers `hdbscan.py` reuses (`screen_rows`, `sample_positions`, `NormalisedSBD`).
- `Working/library/grouping/methods/hdbscan.py`: the `HDBSCANMethod`.
- `Working/library/coherence.py`: `svd_entropy`.
- `tests/test_sbd.py`, `tests/test_library_coherence.py`, `tests/_shape_families.py` (shared synthetic generator).

Modified:
- `Working/distances.py`: adds `sbd`, `sbd_shift`, `sbd_matrix`, `zero_pad_shift` and `DISTANCE_SBD`. SBD is not added to `DISTANCE_REGISTRY`, because `test_distances.py` pins that registry to the three edge distances.
- `Working/library/grouping/engine.py`: three new omission reasons only (`not_in_a_dense_family`, `infinite_values`, `missing_values`), each with its one-line meaning.
- `Working/library/grouping/methods/__init__.py`: docstring only. Registration is automatic, because each module calls `register()` at import and discovery finds it.
- `webui/server/library.py`: `_family_detail` gains `"coherence"`. To cache it I had to add one module-level helper, `_family_coherence`, and `_COHERENCE_CACHE` directly above `_family_detail`. That is the only code outside `_family_detail`.
- `tests/test_library_grouping_methods.py` (extended), `tests/test_webui_library.py` (two tests added).

## 3. The algorithm as implemented

**SBD (eq. 9 of the k-Shape paper)**
1. SBD = 1 − the best coefficient-normalised cross-correlation over all zero-padded shifts. It lies in [0, 2].
2. Shift convention: `shift = k` means `zero_pad_shift(b, k)` (b moved right by k, zeros behind) is the best match to `a`.
3. A flat input scores 1 against anything with shape, and 0 against another flat input.
4. The matrix has two engines that give the same numbers:
   - **FFT:** batched, padded to the next power of two ≥ 2m − 1, per the paper's Alg. 1.
   - **Per-lag:** one matrix product per lag. Measured about 3× faster at m ≤ 512, so `auto` uses it — except against a handful of rows (64 or fewer), where FFT wins.
5. `dtype=np.float32` is optional and accurate to about 1e-6. The matrix of a set against itself is exactly symmetric, which sklearn's HDBSCAN requires.
6. **Why not reuse `cross_channel.cross_correlate`:** it handles one pair at a time, resamples both inputs to a common length first, and reports no shift in the form a caller needs. The tests do pin that it agrees with SBD on equal-length spans.
7. **Why not aeon's `sbd_pairwise_distance`:** it calls scipy once per pair, which takes minutes at Library size.

**`kshape`**
1. Same vectors as Ward (`ward.shape_vectors`, 256 samples). Rows with a NaN or inf are screened out first.
2. **Deviation: aeon's `KShape` is reproduced, not called.** One aeon start (k = 6, 300 vectors) took 49 s on this machine; 3,603 items × 10 starts × 11 values of k would take most of a day.
   - My version keeps aeon's random-number sequence, step order, empty-cluster rule and both stopping rules. It batches the per-pair work: each member's shift comes from the assignment step's own cross-correlation.
   - The leading eigenvector comes from the small Gram matrix (or ARPACK) rather than a full `eigh`.
   - A test pins identical labels, centres (to 1e-15), summed distance and iteration count against aeon, from the same `random_state`.
   - The adapted code carries aeon's BSD-3 and kshape-python's MIT notices in the docstring.
3. Parameters: `k`, `n_init`, `seed`, `omit_d`, `min_group`, `sample`, `resample_length`.
   - `k = 0` (the default) tries k = 2…12 and picks the best silhouette under normalised SBD among the k that give at least two families of `min_group`+ members. That is the site's rule from `Working/training/shape.py`. If no k qualifies it falls back to the best overall and says so. Every k's score is recorded in `payload["k_scores"]`.
   - **Deviation:** each candidate k is fitted and scored on a seeded 2,000-row subsample; the chosen k is then refitted on all fitted rows. Calinski–Harabasz was not chosen because it assumes Euclidean centroids.
4. `omit_d` (default 0.5): a member whose normalised SBD to its own centroid exceeds it is omitted as `past_cut`.
5. `medoid` is the member nearest its centroid by SBD. `merge_heights` returns `[]` (no tree).
6. Sampling: at most `sample` (default 5,000) rows are fitted, seeded. The rest are assigned to the nearest centroid, which is what aeon's `predict` does. `payload` lists the fitted and assigned rows.
7. `fit.distances` is computed lazily, one column per family medoid, so 20,000 items never need a 20,000² matrix.
8. All reported distances are SBD / 2, so they sit on the editor's [0, 1] cut scale like Ward's.

**`hdbscan`**
1. `sklearn.cluster.HDBSCAN(metric="precomputed", copy=True, allow_single_cluster=False)`.
   - Distance is normalised SBD by default; `distance=euclidean` gives Ward's scale-invariant distance.
   - `min_cluster_size` defaults to 10; `min_samples = 0` means sklearn's default; `cluster_selection_method` is `eom` or `leaf`; `cut` maps to `cluster_selection_epsilon`.
2. Noise is omitted as `not_in_a_dense_family`. sklearn's −2 / −3 labels map to `infinite_values` / `missing_values`; NaN and inf rows are screened out before any distance is computed.
3. Rows beyond the sample join the family of their nearest fitted (non-noise) member if within that family's largest core distance; otherwise they are `not_in_a_dense_family`.
4. `assign(cut=…)` re-runs the selection on the stored matrix without recomputing distances.
5. `merge_heights` returns `[]`: the condensed tree's λ values are private in sklearn and are not on the cut scale.
6. **Added (not in the paper): a stability check.** sklearn exposes no cluster stability, so each family gets a "separation": median distance from its members to the rest, divided by median distance within the family. Families below `UNSTABLE_SEPARATION = 3.0` are flagged in `payload["unstable_families"]` but still returned. The 3.0 is a placeholder from synthetic data.

**`svd_entropy(member_matrix, align=True, *, medoid=None, squared=False, …)`**
1. Rows are resampled to 256 samples and z-normalised. NaN rows are dropped and counted.
2. With `align`, each row is shifted to its best SBD match against the medoid. The medoid is the member with the least summed SBD, unless the caller names it.
3. **Deviation:** the aligned rows are cut to the span every row still covers (if at least half the length remains), then re-z-normalised.
   - k-Shape keeps the zero padding instead. But in a z-normalised row the baseline is not 0, so the padding is a step of varying length.
   - That alone raised the score of 40 shifted exact copies from about 0 to 0.40.
4. p_i = σ_i / Σσ (not squared). I confirmed this against the paper's HTML on arXiv: eq. 17 normalises the singular values themselves.
5. H = −Σ p ln p; `svd_entropy_norm` = H / ln min(P, L).
6. At most 2,000 members are used, sampled with a seed; `sampled` says when.
7. Returns `svd_entropy`, `svd_entropy_norm`, `n_members`, `n_used`, `n_dropped`, `sampled`, `aligned`, `medoid_index`, `overlap`, `top_share`, `squared`, `rule`, `reason`.
8. `squared=True` (σ² weighting) is a labelled variant for comparison, not eq. 17.

**Bridge**
- `_family_coherence` reads each shown member's raw span in the stored unit, aligns to the family's medoid row, and caches by the tuple of spans (bounded at 512).
- A failure becomes `{"error": "Type: msg", "rule": …}` and is logged with its traceback; the rest of the Family page still renders.

## 4. Tests

- **Red commit `2d64d54`**, run at base:
  - `test_sbd.py`: ImportError (`sbd`).
  - `test_library_coherence.py`: ModuleNotFoundError.
  - `test_library_grouping_methods.py`: 38 failed, 22 passed (the 22 are the pre-existing tests).
  - `test_webui_library.py`: skipped.
- **Green (`ad160b4`):** the new tests together with `test_library_grouping.py`, `test_distances.py`, `test_block_standard.py`, `test_adapter_spec.py`, `test_import_boundaries.py` and `test_templates.py`: **360 passed, 1 skipped**.
  - Plus the other suites that use distances or grouping (cross_channel ×2, export, library_edges, identity, seed_edges, shape_chain, training_shape ×2): **122 passed**.
  - Ward's tests are unchanged and pass.
- What each file pins:
  - `test_sbd.py` (25 tests): a shifted copy scores 0 with the right shift; shifts are zero-padded, not cyclic; pair and matrix match a direct O(m²) loop to 1e-10 for both engines, including shifts; float32 is within 1e-5; exact symmetry; flat inputs are defined; agreement with `cross_correlate`; z-normalisation makes it offset- and scale-free.
  - Methods file, k-Shape: matches aeon start for start; recovers shifted families on 4 backgrounds with ARI ≥ 0.9 while Ward is at least 0.3 worse; auto k scores every k and follows the rule; `omit_d` gives `past_cut`; medoid; seeded sample plus assignment.
  - Methods file, HDBSCAN: three families plus 30 % noise with noise ≥ 80 % omitted; pure noise on 5 backgrounds × 3 seeds gives no confident family and never 3; sampled-row assignment; cut, leaf and euclidean are honoured; medoid.
  - Methods file, both: NaN/inf reasons; `run_grouping` end to end with a recipe hash that changes when a parameter does; neither serves `sequence-similarity`.
  - `test_library_coherence.py` (10 tests): copies near 0 and a mixture higher on white, AR(1) and random-walk backgrounds; alignment lowers the score; amplitude-blind; exactly eq. 17, plus the squared variant; NaN rows, too few rows, sampling, named medoid.
- **Family-detail tests not run:** the two tests in `tests/test_webui_library.py` skip under conda because FastAPI is only in `webui/.venv`, and my worktree has no `.venv`. I checked the helper with stubbed FastAPI in a scratch script (values, cache hit, `notOnDisk` count). **Run them with the main checkout's `webui/.venv`.**

**Timings** (synthetic, 80 % events with 15 % AR(1) noise plus 20 % pure-noise windows; this machine was heavily loaded by the other wave-2 agents, so read these as upper bounds):

| method / params | 3,603 items | 20,000 items (5,000 fitted) |
|---|---|---|
| `hdbscan` defaults | 20 s | 208 s |
| `kshape` k = 3 | 32 s | 45 s |
| `kshape` k = 0 (auto, 10 starts × 11 k) | **1,115 s (~19 min)** | not finished; stopped. The sweep is the same 2,000-row cost, so expect about 20 min plus a 5,000-row refit |

## 5. Integration snippets

- **Glyphs:** no template or adapter here, so no `BY_NAME` glyph is needed. If the grouping editor wants icons:
  - `kshape`: two grey humps offset horizontally, a blue arrow sliding one onto the other, one blue merged hump.
  - `hdbscan`: three tight blue dot clusters, a few loose grey dots outside, an amber ring around one cluster.
- **Client (W2-F):**
  - `OMIT_REASON_LABEL` in `webui/client/src/library/chrome.tsx` needs three entries: `not_in_a_dense_family`: "in no dense family"; `infinite_values`: "hold an infinite value"; `missing_values`: "hold missing values".
  - The Family page should read `detail.coherence` and draw `{error}` as a red card.
- **Smoke state suggestion:** Family page F-01 shows a coherence number with its rule, and the `.coherence.error` path renders red.
- **Cost:** please add a cost entry. `engine._recompute_cost` prices any distance basis at n² × 2 µs (about 13 s at 3,603). That under-states `kshape` k = 0 by about 85×, and the editor will offer it as a local run. It also ignores the 5,000-row sample cap on the 20,000 side. Suggested per-method cost:
  - `kshape`: about 0.6 s per k per start at 2,000 rows, plus refit.
  - `hdbscan`: min(n, 5,000)² × 1.5 µs, plus (n − 5,000) × 5,000 × 1 µs.

## 6. Open questions and risks

- **Prompt acceptance item "negative ≈ 1 on the normalised scale" cannot hold.**
  - SBD takes the best over shifts, so only the zero-shift correlation of a negative is −1.
  - A one-signed pulse against its negative scores SBD = 1, which is 0.5 normalised — "unrelated".
  - A z-normalised drop against its negative scores about 0.35 normalised, because some shift lines up the lobes.
  - Consequence: with the default `omit_d` 0.5, a drop is never omitted from a spike family. And on my synthetic noise, k-Shape omitted nothing at all, because noise windows sit 0.14–0.32 from the nearest centroid. **k-Shape therefore forces noise into families, as Ward does.** Choose `omit_d` around 0.1–0.15, or pair it with HDBSCAN. Please measure it on real families.
- **Auto k chooses 2 on the three-family set.** The silhouette prefers merging the sharkfin and the square (0.73 for k = 2 vs 0.70 for k = 3). That is the silhouette's known bias, not a bug. With the slow sweep, I'd suggest the editor default to an explicit k. I left the default at 0, following the prompt's "0 = auto"; changing it is the manager's call.
- **The SVD-entropy score loses its discrimination under noise** (paper's unsquared formula).
  - 40 copies of a resampled drop: 0 with no noise, about 0.30 at 1 % noise, 0.62–0.73 at 5 %, 0.76–0.86 at 10 %.
  - A drop/square 50/50 mixture at the same noise levels: 0.43–0.46, 0.67–0.76, 0.75–0.83.
  - The squared variant stays discriminating (copies 0.04 vs mixture 0.14 at 5 %).
  - **Researcher decision:** keep eq. 17 (the default), or switch to `squared=True`. Compare both on real families with very different amplitude spreads first.
- **HDBSCAN's stability threshold (3.0) is a placeholder with a thin margin.** Synthetic real families: 3.3–13.5. Noise crowds: up to 2.8. Check on real families and on phase-randomised surrogate recordings.
- **HDBSCAN merges similar shapes at higher noise.** At 15 % noise on 3,603 items it found 2 families (sharkfin and square merged), and some events were omitted as noise. `leaf` or a smaller `min_cluster_size` may suit the Library better. Check on the real 3,603.
- **Real-data checks I'd ask for** (whole-catalogue runs, which I could not do):
  - k-Shape at k ≈ 10–20 and HDBSCAN on the 3,603: family counts versus Ward's 149; omitted fraction by reason; separation distribution; per-family coherence alongside amplitude CV.
  - Whether drops and spikes stay in separate families (the sign-and-shift issue above).
- **Not done because 00-common forbids it** (CLAUDE.md asks for both; 00-common wins for this wave): `docs/rq_roundA/RQ1` not updated (it now gains `hdbscan` for clustering the unlabelled pool); `docs/LIBRARY_STORAGE.md` §6, which still says five omission reasons, not updated.
- The sklearn 1.7.2 HDBSCAN internals emit a numpy `DeprecationWarning` (`tree_to_labels`). It is harmless and not ours.

## 7. Commits

```
ad160b4 w2-b: sbd, kshape and hdbscan methods, svd_entropy coherence, family coherence
2d64d54 w2-b: tests (red) -- sbd, kshape, hdbscan, svd_entropy coherence, family coherence
```
