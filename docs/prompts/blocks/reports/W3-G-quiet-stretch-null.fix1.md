> Filed by the manager session, 2026-10-15 — the final message of implementer agent `a17192b65fcf2dd72`, resumed for
> fix round 1 on branch `worktree-agent-a17192b65fcf2dd72` (`a4a2a6f` red, `84e8326`), verbatim.

## W3-G fix round 1 report

All eight of the critic's findings are fixed and decisions 15 and 16 are applied. Nothing was left undone.

- **Red commit `a4a2a6f`.** `tests/test_library_background_null.py`: 26 failed, 15 passed. The webui subset (venv python): 3 failed.
- **Green commit `84e8326`.** On top of `f36ef75` / `2a4ca0e`, base `6bd3e40`; main not merged.

### What changed, per item

**F3 / decision 15 — a family passes on either null.**
- The rule lives in `kshape.either_verdict`, used by HDBSCAN and k-Shape. Coherence `beyond_noise` is eq. 17 below 0.9 × the 5th percentile of either null.
- `null_kind` is "quiet-stretch or trend-kept phase-randomised" wherever the quiet null is usable, and the trend-kept null alone otherwise. A new `passed_by` field lists which null passed. `why` gives both ratios; `nulls` keeps both results.
- Detections are still not avoided. The "only makes the null tighter" claim is corrected in the docstrings, the rules and `why`: an uncatalogued event loosens the null for other shapes and tightens it for its own.
- New `MemberBackground(mark_of=...)` reports `detection_overlap_share`. The bridge counts every machine detection on the recording, mapped to absolute indices with `absolute_bounds`.
- **Pinned, before → after.**
  - A drop family on a random walk whose quiet stretches hold 448 uncatalogued drops: noise-like (quiet ratio about 0.70) → confident, passed by the trend-kept null (0.06).
  - The hump family in the same recording: passed by the quiet null (0.02); the trend-kept ratio is 1.38.
  - Pure noise with 150 uncatalogued drops (random walk, AR(1) 0.99): no family confident, no coherence beyond noise.

**F5 / decision 16 — `QUIET_MARGIN` 0.7 → 0.6.**
- Labelled a placeholder, with the critic's worst cases (0.714 clean, 0.643 contaminated) and the real-family range (0.13–0.39).
- New test of the critic's small-family worst case: the 10 and 20 nearest windows around the 3 densest centres among 3,600 quiet windows, on random walk and AR(1) 0.99. Every such crowd fails both nulls. This test already passed at 0.7; it pins the worst case rather than the change.

**F1 — like-for-like coherence.**
- Pool = n_set up to 4,000 (was capped at 2,000), so the null scores as many rows as the family. At n_set 3,600 a 100-member family is now scored on 100 rows on both sides.
- Above 4,000, the family is scored on random subsets of the null's row count (median of 5). This is said in `background.family_scored_on` and in `why`.
- The number of rows taken (`take`) is floored at 10 instead of 2.

**F2 — the Family page's n_set.**
- New `_grouping_n_set`: the grouping's assignment rows, omitted ones included, minus `missing_values`, `infinite_values` and `not_in_a_sequence`. Never the view-filtered rows.
- Route test (venv): with and without `?pure=1&floor=1`, n_set was 4 (the shown rows) before and is 6 (the items that took part) after, the same under both views.

**F4 — no verdict-shaped field on σ².**
- `variants[0]["beyond_noise"]` is now None, with `squared_vs_null_ratio` and a note: "reported, not judged; would need a margin of about 0.7; eq. 17 judges".
- `beyond_noise_squared` is removed, and so is `svd_entropy_squared_beyond_noise` from the family summary.

**F6 — caches and fewer draws.**
- New `_FREE_STRETCH_CACHE` (free stretches per recording) and `_SPANS_CACHE` (Library spans), keyed on path, mtime and a fingerprint of members, sequences and detections. Bounded at 64 entries.
- The coherence's quiet null now takes 3 draws (was 5); the trend-kept null keeps 5.
- Re-measured with the venv python on a heavily loaded machine: 8 synthetic recordings of 2 M samples, n_set 3,616, a DB connection, detections present.

| Family | Before (critic) | First request | Cached |
|---|---|---|---|
| 20 members | 2.0 s | 2.0–2.6 s (pool now 3,616 rather than 2,000, at 3 draws) | 4–15 ms |
| 20 members, second family on the same recordings | — | 2.0–2.4 s | — |
| 2,000 members | 13.6–21.7 s | 23–40 s | ~0.95 s |

- The 2,000-member family is dominated by the members' own work: the same call with no background took 32 s in the same run. The free-stretch cache spares the per-recording work on later families. The ~0.95 s cached time is building the cache key: one file stat per member.

**F7.** `smooth_caveat` is now set only when the trend-kept null judged alone.

**F8.** `why` names borrowed windows when there are any ("N borrowed windows"), and the detection-overlap share.

**Deliberate test updates.**
- Fix-round test file: `null_kind` values now read "quiet-stretch or trend-kept", plus `passed_by` checks.
- `test_webui_library`: the smooth-caveat test now expects the caveat only when the trend-kept null judged alone; the quiet-stretch Family test expects the either-null `null_kind`.
- The new free-stretch cache test now passes a DB connection. Without a database the avoidance is the shown family's own spans, so its key cannot be shared between families.

### Test counts
- **Conda python** (`-n 3`, `NUMBA_NUM_THREADS=2`): **541 passed.** Covers `test_library_background_null` (41), `test_library_grouping_methods`, `test_library_coherence`, `test_shape_families`, `test_adapter_shape_families`, `test_adapter_event_families`, `test_template_event_families`, `test_template_event_clusters`, `test_background_null`, `test_cycle_shapes`, `test_adapter_cycle_shapes`, `test_block_standard`, `test_adapter_spec`, `test_import_boundaries`, `test_templates`, `test_grouping_adapter`.
- **Webui, venv python:**
  - Full run of `test_webui_library`, `test_webui_family_views`, `test_webui_w2f_ui`, `test_webui_library_edges`, `test_webui_mpdist_edges`: 87 passed, 3 xpassed, 2 failed.
  - The 2 failures were the two assertions under "Deliberate test updates" above (the caveat, `null_kind`). After updating them, the coherence / quiet / cache / n_set subset passed 8 of 8.
  - The whole webui set was not re-run after those test-only edits; it is ~12 minutes, so worth one run in your gate.

### For W3-F: what a family that fell back should show
Today a confident Library family shows nothing on its face; `why` only appears as a tooltip on noise-like badges. Suggested display:
- **Show which null passed on every tested family.** Use `passed_by`: "beyond noise (quiet stretches)", "(trend-kept)" or "(both)".
- **Mark the fallback on the badge itself.** When `null_kind` is "trend-kept phase-randomised" and `background.reason` is set, show something like "judged on trend-kept noise only: <reason>". Show `smooth_caveat` (now present only in that case).
- **Context line.** Show `background_s`, `n_borrowed` and `detection_overlap_share`, plus `background.family_scored_on` when the family was scored on subsets.
- **σ² first, as a number only.** From `variants[0]`: score, `squared_vs_null_ratio` and its note, with no badge.

### Commits
```
84e8326 w3-g: fix round 1 — either null passes, margin 0.6, like-for-like coherence, the page's n_set, caches
a4a2a6f w3-g: fix round 1 tests — either null passes, margin 0.6, like-for-like coherence, the page's n_set, caches
2a4ca0e w3-g: the recording's own quiet stretches as the families' null; a trend-kept null for k-Shape
f36ef75 w3-g: tests — the quiet-stretch null for families, and a trend-kept null for k-Shape
```
