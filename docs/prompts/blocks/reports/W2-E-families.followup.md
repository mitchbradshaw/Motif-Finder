> Filed by the manager session, 2026-10-14 14:49 — the final message of implementer agent `a5a91c3213452c835`,
> resumed for a follow-up (merge main after W2-B's fix round 2; the serializer's exemplar format; re-measure its two
> risks), verbatim.

# W2-E follow-up: merged main, exemplars in the serializer's format, both risks re-measured

**Status:** main is merged in, the exemplar format now matches what the serializer reads, and the two risks are re-measured under the new HDBSCAN rule. Both risks are fixed, but the new rule flags the template's sharkfin family as noise-like at the default window length (point 4).

## 1. What changed

- **Merge:** `git merge main` (`3fd0742`), no conflicts.
- **`catalogue.shape_families`:**
  - `meta["exemplar_windows"]` is now `{"<family>": <window index of the medoid member>}`, with labels as strings.
  - `meta["exemplar_rule"]` is a string.
  - The richer list `{family, window, start, start_s}` moved to `meta["exemplars"]`.
- **`interrogation.event_families`:** `meta["exemplar_events"]` is `{"<family>": <event index>}`, plus `exemplar_rule`. The richer list is under `meta["exemplars"]`.
- **Rule text:** the `noise_like` rule no longer describes W2-B's old size-and-separation test. It now describes the per-family surrogate comparison (HDBSCAN keeps a cubic trend) and points to `fit_summary.null.rule`.
- **One test changed:** `tests/test_shape_families.py` had pinned the null's `kind` as `"phase-randomised"`. After `2fd26b8` it is `"trend-kept phase-randomised"`, so the assertion now only checks that `"phase-randomised"` appears in it. This change is in the green commit.

## 2. Red → green

- **Red `2e98666`** (tests only): 2 failed. Both exemplar-meta tests got a list where they expected a dict.
- **Green `2c016e3`.** All passed:

| Run | Result |
|---|---|
| My four test files | all pass |
| My four files + `test_library_grouping_methods`, `test_library_coherence`, `test_block_standard`, `test_adapter_spec`, `test_end_to_end` (`-n 4`), before the null-kind fix | 387 passed, 1 failed (the pinned null kind) |
| The three family test files, after the fix | 52 / 52 |
| `test_template_event_families` | 4 / 4 |

## 3. Re-measured risks under the new rule (main `2fd26b8`)

**Risk 1 is fixed.** Setup: 200 phase-randomised AR(1) windows of 140 samples, HDBSCAN defaults.

| φ, seed | Placed | In a confident family | Families (size, flagged noise-like) |
|---|---|---|---|
| 0.95, 0 | 37 | 0 | (22, yes), (15, yes) |
| 0.95, 1 | 22 | 0 | (12, yes), (10, yes) |
| 0.95, 2 | 0 | 0 | none |
| 0.97, 0 | 0 | 0 | none |
| 0.97, 1 | 39 | 0 | (23, yes), (16, yes) |
| 0.97, 2 | 39 | 0 | (23, yes), (16, yes) |

Every noise crowd is now flagged, so `fraction_confident` is 0 in all six runs. Before, 3 of the 6 runs had 22–39 events in families that were not flagged. The `~noise_like` group key now marks these crowds in Intervals' table.

**Risk 2 is fixed.** The template's square family (16 events) is confident at every length tried: 140, 300 and 480 s. Before, it was flagged noise-like at 300–480 s. ARI is 1.00 at all three lengths.

## 4. New issue from the new rule

At **140 s**, which is the template's automatic window length, the **sharkfin family (72 events) is flagged noise-like**. The `why` text reads: "members' median distance to the medoid 0.003 is 2.18 × the 5th percentile 0.001 of trend-kept noise".

- In plain words: a 140 s window that starts partway down the sharkfin's slow descent holds mostly a straight ramp. The cubic trend kept in the surrogates reproduces a ramp almost exactly, so the null scores as tight as the real family. This is the "ramps can read noise-like" case you mentioned.
- At 300 s and 480 s the sharkfin family is confident: 0.16 × and 0.06 × the noise's 5th percentile.
- The template's acceptance still passes (ARI 1.0, both medians within 1 %). But the sharkfin's Intervals key is now `1~noise_like`, so the template marks a real family as noise.

**Options:**
- **(a)** Set `length_s: 300` on the template's `event_families` step, so a window covers the whole event and not just its ramp. The auto length is a placeholder anyway (W2-A).
- **(b)** Leave the template on the auto length and ask W2-B whether a cubic trend is too strong for short windows.

**Recommendation: (a).** It is one parameter in the template, and the measurement above supports it. I did not change it because you asked only for a re-measurement; it is your call.

## 5. Commits (`git log --oneline c2e6e05..HEAD`)

The list includes main's commits brought in by the merge. The W2-E ones are `e194e43`, `e7ef98b`, `3fd0742` (the merge), `2e98666` and `2c016e3`.

```
2c016e3 w2-e: exemplar_windows / exemplar_events in the serializer's format; rules follow W2-B's fix round 2
2e98666 w2-e: tests (exemplar format) - exemplar_windows / exemplar_events as {"<label>": index} + exemplar_rule
3fd0742 Merge branch 'main' into worktree-agent-a5a91c3213452c835
e7ef98b w2-e: catalogue.shape_families and interrogation.event_families - the Library's clustering inside a chain
2fd26b8 Merge branch 'worktree-agent-ab19ca872abbd930c': w2-b Library methods kshape and hdbscan, sbd, svd_entropy coherence
5a14f03 blocks-w2: MiniRocket asks aeon for numba's own thread cap, so a one-thread machine still fingerprints
c1736a5 blocks-w2: tests (red) -- MiniRocket must fingerprint when numba is capped at one thread
ddfc277 Merge branch 'claude/magical-euler-829723': detrend-nan follow-up, the drop detector's rolling_mean_nearest is NaN-aware too
0200240 w2-b: LIBRARY_STORAGE 6 -- the per-family trend-kept null (fix round 2)
787ac5d w2-b: fix round 2 -- HDBSCAN's per-family trend-kept null; the same surrogate for coherence; n_misaligned 0.4
0e5f20e w2-b: tests (red) -- fix round 2: per-family trend-kept null for HDBSCAN and coherence; n_misaligned; cheaper order
e194e43 w2-e: tests - catalogue.shape_families, interrogation.event_families and the event_families template
9c02982 detrend-nan: the drop detector's filter (rolling_mean_nearest) averages the finite samples too
496b40f detrend-nan: failing tests - the drop detector's filter (rolling_mean_nearest) must not blank the rest after one NaN either
```

Everything else in my first report still holds (the public function `Working.Catalogue.shape_families.shape_families`, the template dict, the glyphs, and `COSTED` for both blocks).
