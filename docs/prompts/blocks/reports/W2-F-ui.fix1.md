> Filed by the manager session, 2026-10-14 15:30 — the final message of implementer agent `adc5c4378118b320a`,
> resumed for fix round 1 against `W2-F-ui.critic.md`, verbatim.

# W2-F fix round 1: report

All twelve critic findings are fixed. The type-check, the production build and the Python gate (329 passed, 3 xpassed) are clean. Smoke has not been run: this worktree has no database, so all eight states below are written but unverified.

## In plain words

- **Coherence verdict.** The Family page now uses the core's own verdict: a family's score must be clearly below the noise's 5th percentile, by the 0.9 margin, to count as more coherent than noise. Pure noise sitting just under the noise score is no longer called coherent. When no noise null was drawn, it says "no null". The smooth-shape caveat sits beside the verdict.
- **Exemplars.** A block that hands its typical members over in the wrong format gets an error naming the expected form and the block. Gaps are now said on the cluster, not left blank.
- **Smoke.** Snippets and event clusters are experimental and not seeded, so no smoke state imports them by name any more.

## What changed

**Base**
- `git merge main` → `7738d27`: W2-B fix round 2, coherence `beyond_noise`, and the template decisions.

**The fixes**
1. **Family-page verdict.** `FamilyCoherence` reads `c.beyond_noise`:
   - `false` → amber "no more coherent than noise"
   - `true` → green "beyond noise"
   - `null` → grey "no null"

   The badge title says "not below 0.9 × p05", gives the resulting cut, and says the margin is a placeholder. The caveat (`coherence-caveat`) shows beside the verdict and is amber when the family is noise-like. `library.py` adds `smooth_caveat` and `misaligned_fraction` to the coherence payload from the core's constants. The types gain `beyond_noise`, `null_margin`, `null_kind`, `smooth_caveat` and `misaligned_fraction`.
2. **Ward smoke state.** `w2-method-ward-unchanged` now selects `ward` explicitly. I chose this over reordering or `"cold": true` because switching back to Ward is what the state is about.
3. **Exemplar format.** `exemplar_windows` must be `{"<label>": <window index>}`. Anything else raises a ValueError naming that form and the block. `runs.py` now passes `ctx["block"]` (one line; `runs.py` is outside my Deliver list).
4. **Exemplar edge cases.**
   - A label ≥ 0 the block named no exemplar for gets `exemplar_note` = "the block named no exemplar for this label" on its cluster (drawn as `exemplar-none`).
   - A named label not in the grouping raises.
   - A non-whole index (3.7) raises; 3.0 is accepted.
5. **Stale texts.** The misaligned count reads the fraction from the payload, so it says "0.4 of the length". The noise line names `null_kind`.
6. **`NoiseBadge`.** It shows a grey "verdict not saved" when the grouping's method draws a null (kshape, hdbscan; `METHODS_WITH_NULL`) but the family has no flags. It shows on the atlas tile and the Family page. The false comment is gone.
7. **`seedFromGrouping`.** It parses the method's declared `str`/`choice` params out of the params text. It now waits for the editor read so it knows which params those are.
8. **Smoke viability.** See the states below.
9. **`LibFamilyFlags`.** Gains `ratio` and `margin`; `null_max_*` are gone.
10. **Snippets' −1.** Now named "unlabelled · N of M mostly NaN".
11. **Event windows.** `EventWindowsKey` renders `notes`. An event with no window is outlined by set difference against `event_index` (`event-windowless`), so events past the `omitted_rows` cap are no longer drawn as plain bands. Zero windows shows `event-windows-none` with the reason.
12. **Refusal card.** It is cleared when the settings it refused change (`refusalSig`, `clearRefusal`).

**Red → green**
- **Red: `fccd446`, tests only.**
  - conda: 7 failed, 42 passed.
  - venv: 1 failed (`test_family_coherence_carries_its_caveat_and_misaligned_fraction`).
  - Deliberate change, stated in the commit: the smoke pin no longer requires `template-recording_snippets`.
- **Green: `574fd9d`.**
  - `tsc -b` and `vite build` clean.
  - venv `-n 4` over `test_webui_block_views`, `test_webui_library`, `test_block_standard`, `test_webui_serialize`, `test_webui_w2f_ui`, `test_import_boundaries`, `test_templates` and `test_webui_run_routing`: 329 passed, 3 xpassed.
  - The `node_modules` junction was only in the scratch copy and is removed; the real `node_modules` is intact.

## The smoke states as they now stand

**`webui/smoke_pages/zz_analyse_run.json`**

- **`w2-event-windows-thumbnails`** (chain)
  - Steps: noise_threshold template on the 2 h example span; Event shape at `insert-2`, Event windows at `insert-3`; run.
  - Should show: rows 2–3 as SpanSets and row 4 as a WindowSet. Rule 9 applies.
- **`w2-event-windows-around-their-events`** (`analyse/block/3`)
  - Should show: `spanset->windowset`, `svg[data-testid=event-windows]`, the key with the anchor legend, the fates line, and the rules. Rule 9 on the ghost trace.
  - The span may hold no events. I checked that Event shape and Event windows both run on an empty SpanSet (0 windows, anchor still in meta). With events there are amber `window-anchor` ticks; with none, `event-windows-none` says the detector found no events. The state asserts only what is drawn either way, so it does not expect `window-anchor`.
- **`w2-minirocket-thumbnails`** (chain)
  - Steps: the seeded `minirocket_manual_labels` with its classifier deleted (`delete-step-4`; 2 h cannot promise labels in both splits), on the example span.
  - Should show: row 1 as window_matrix's WindowSet, row 2 as MiniRocket's heatmap, row 3 as the labels Grouping.
- **`w2-minirocket-fingerprint-heatmap`** (`block/1`)
  - Should show: `windowset->windowset`, `feature-heatmap` and `windowset-key`.
- **`w2-snippets-thumbnails`** (renamed from `w2-recording-snippets-*`)
  - Steps:
    1. `explore/signal/1`, five `zoom-out` clicks → about 15.2 h, i.e. at least 12 one-hour pieces (2 × k_max), about 10 s of O(n²) work.
    2. `send-span`, then import noise_threshold for its detrend step and delete its detector (`delete-step-2`).
    3. Insert Sliding windows at `insert-1` and Snippets at `insert-2`.
    4. Set block 0 `window_s` = 21600 (6 h detrend) and block 1 `window_s` = 3600; back to the chain; run; wait up to 120 s.
  - Should show: signal, WindowSet, Grouping; no `run-refused-slurm`. Rule 9 applies.
- **`w2-snippets-block-exemplars`** (`block/2`)
  - Should show: `windowset->grouping`, `cluster-strip`, `cluster-exemplars`, `exemplar-rule` ("chosen by the block: …"), `exemplar-1` with a plot box, and `label-rules`. Rule 9 applies.

**`webui/smoke_pages/library.json`**

- **`w2-method-hdbscan-no-tree`**
  - Should show: `no-tree-line[data-method=hdbscan]`, `param-epsilon`, `param-min_cluster_size`, the omission line reading "in no dense family", `method-description`, `preview-uncomputed`; no histogram and no `param-cut`.
- **`w2-method-ward-unchanged`**
  - Selects `ward` back. Should show: `param-cut`, `param-nearest` and `feature-histogram`; no `no-tree-line`.

## Still open

- The families' glyph and their block-level smoke state wait for W2-E's final meta keys, as you asked.
- The serializer checks that each named exemplar window's own label equals the label it is named for. Please make sure W2-E's medoid indices satisfy that, or its view will error.

## `git log --oneline c2e6e05..HEAD`

```
574fd9d w2-f: fix round 1 -- the core's beyond_noise verdict, exemplar shapes and gaps, smoke viability, stale texts
fccd446 w2-f: tests (red) -- fix round 1: beyond_noise verdict, exemplar shapes and gaps, smoke viability, stale texts
7738d27 w2-f: merge main (W2-B fix 2, coherence beyond_noise, template decisions)
800d0d9 blocks-w2: minirocket_manual_labels ships; event_clusters and recording_snippets are experimental
55973f7 blocks-w2: tests (red) -- the wave-2 templates are the ones webui/server/templates.py ships
4db3684 blocks-w2: coherence's beyond_noise carries the 0.9 margin; both trend-kept nulls say smooth shapes are not judged fairly
cdcc3e7 blocks-w2: tests (red) -- coherence's verdict carries a margin; both nulls say smooth shapes are not judged fairly
2fd26b8 Merge branch 'worktree-agent-ab19ca872abbd930c': w2-b Library methods kshape and hdbscan, sbd, svd_entropy coherence
5a14f03 blocks-w2: MiniRocket asks aeon for numba's own thread cap, so a one-thread machine still fingerprints
c1736a5 blocks-w2: tests (red) -- MiniRocket must fingerprint when numba is capped at one thread
35b1528 w2-f: the wave-2 UI -- event windows on the trace, the editor's method choice, coherence and the noise badge, glyphs, smoke states
ddfc277 Merge branch 'claude/magical-euler-829723': detrend-nan follow-up, the drop detector's rolling_mean_nearest is NaN-aware too
0200240 w2-b: LIBRARY_STORAGE 6 -- the per-family trend-kept null (fix round 2)
787ac5d w2-b: fix round 2 -- HDBSCAN's per-family trend-kept null; the same surrogate for coherence; n_misaligned 0.4
0e5f20e w2-b: tests (red) -- fix round 2: per-family trend-kept null for HDBSCAN and coherence; n_misaligned; cheaper order
d2d2425 w2-f: block-named exemplars, event windows' anchor on the payload, the editor's registered methods
980a105 w2-f: tests (red) -- block-named exemplars, event windows' anchor, the editor's methods, the wave-2 UI pins
9c02982 detrend-nan: the drop detector's filter (rolling_mean_nearest) averages the finite samples too
496b40f detrend-nan: failing tests - the drop detector's filter (rolling_mean_nearest) must not blank the rest after one NaN either
```

The W2-F commits are `980a105`, `d2d2425`, `35b1528`, `7738d27`, `fccd446` and `574fd9d`; the rest arrived with the merge of main.
