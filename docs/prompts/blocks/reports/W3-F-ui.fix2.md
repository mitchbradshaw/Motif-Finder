> Filed by the manager session, 2026-10-15 — the final message of implementer agent `a9bcefee16fc666b3`, resumed for
> fix round 2 (the last; decision 27) on branch `worktree-agent-a9bcefee16fc666b3` (red `f102dee`, green `0de9e6e`),
> verbatim.

## W3-F fix round 2 report

**In plain words.** Every page that reports "what the noise comparison expects" now uses one shared rule: a noise run counts as a draw only if it finished. In the critic's case, Analyse and the Discovery scoreboard now agree on the same run: 2 draws, null expects 34.5. A noise run that fails part-way (for example, a block that refuses surrogate data) is now tagged as noise, so its spans can no longer be counted as real detections. The pan view no longer presents one window length as the one to use. It reads "clears from A to B s · strongest at C s — not an event length", all on one line. Items 1–4 are done; the optional item 5 is not.

**Commits:** red `f102dee` (tests only) → green `0de9e6e`.

### Per item

1. **One shared rule for "a completed null draw".**
   - New: `Working/database/queries.py::completed_null_draw(alias)`, which reads `alias.surrogate_of_run_id IS NOT NULL AND alias.status = 'completed'`. It sits beside `not_surrogate`.
   - Every reader now uses it:
     - `run_groups.null_summary`
     - `scoreboard._null_runs`
     - the `nulls` query in `matching.scale_readout`
     - `library._family_null`
     - `export._surrogate_block`
   - The export now picks a completed draw. If only half-finished draws exist, its block reads `run_id: None`, `completed: False`, `stopped_run_ids`, plus a note: "no completed surrogate draw: the paired null was stopped part-way … no surrogate control for this run". It never names a half-finished draw as the control.
   - Before → after on the critic's case (real run 82 spans; completed draws of 13 and 56; a stopped draw of 22):

     | Reader | Before | After |
     |---|---|---|
     | Discovery scoreboard | 3 draws / 30.33 | 2 draws / 34.5 |
     | `null_summary` | 2 / 34.5 | 2 / 34.5 (pinned to agree with the scoreboard) |
     | Library scale read-out (`nullDraws`) | 2 | 1 |
     | Family null (`drawsTotal`) | 2 | 1 |
     | Export, lowest-id draw stopped | named the stopped draw as the control | picks the completed one |

   - `test_webui_discovery::test_the_scoreboard_cells_are_the_tables_own_numbers` still fails, with the same coverage-rule string mismatch as on main. Its failure is unchanged.

2. **A draw that fails part-way no longer leaks.**
   - `execution.py` now sets `run_id` on `RecipeExecutionError`, as it already did on `RecipeCancelled`.
   - `draw_paired_null` catches the error, links the draw's run row, and re-raises.
   - The job still reads failed, and the block's own words are kept as the cause.
   - The test is a chain whose second block refuses surrogate data. Before, the error carried no `run_id` and the row stayed unlinked. After, real detections stay at the real run's 3, and the failed draw's row is linked.

3. **The pan view never presents a length as the one to use.**
   - Headline: "clears from A to B s · strongest at C s — **not an event length**", on the same line as the number. The amber caveat stays below it.
   - The table cell reads "strongest".
   - No "suggested" text and no "use this window" anywhere in the view; a source pin enforces this.

4. **The caveat comes from the block.** The caveat is now the text of the block's own `meta["rules"]` entry named "suggested window". `SUGGESTION_CAVEAT` is used only when the block sends none.

5. **Not done (cosmetic, optional).** The text still reads "Cancelled: Cycle shapes cancelled." No one-line fix keeps History's "starts with Cancelled" check and also drops the repeat, so I left it.

### Tests
- **Conda:** 213 passed, 8 skipped across:
  - `test_null_draws_completed` (new)
  - `test_webui_run_cancel`, `test_webui_w3f_ui`, `test_webui_w3f_payloads`
  - `test_run_groups`, `test_surrogate_never_a_detection`, `test_execution`, `test_import_boundaries`
  - `test_discovery_scoreboard`, `test_export`, `test_library_seed_edges`, `test_library_edges`, `test_discovery_fanout`, `test_divergence`, `test_analyse_null_toggle`, `test_null_draws_methods_cut`
- **Conda, the other discovery, library and review test files:** 277 passed.
- **Venv:** 206 passed, 3 xpassed, 1 failed (the known Discovery failure above). This run covered:
  - `test_null_draws_completed`, including the family-null test, which needs FastAPI
  - `test_webui_discovery`, `discovery_runlist`
  - `test_webui_library`, `library_edges`, `library_view`
  - `run_routing`, `run_cancel`, and the two w3f files
- **Client:** `npx tsc -b` and `npm run build` are clean, built in the scratch copy. The junction was removed with `cmd /c rmdir`, and the main checkout's `node_modules` is intact.

### Files outside the Deliver list
- **This round, handed over by decisions 25 and 27:**
  - `Working/database/queries.py`, `Working/discovery/scoreboard.py`, `Working/library/matching.py`
  - `webui/server/library.py` (`_family_null` only), `Working/export.py` (`_surrogate_block` only)
  - `Working/execution.py`, `Working/run_groups.py`
- **New test file:** `tests/test_null_draws_completed.py`. It reuses the `Lib` fixture from `test_library_seed_edges`.
- **Earlier rounds, unchanged:**
  - `analyse/store.ts`, `useValidation.ts`, `InsertStageModal.tsx`
  - `webui/server/runtime.py`, `webui/server/app.py`
  - `Working/block_cost.py`, `Adapters/preprocessing_window_matrix.py`
  - `discovery/AddMatches.tsx`, `analyse/views/GroupingView.tsx`, `library/Edges.tsx`
  - the `catalogue.cluster` −1 / `label_base` change in `serialize.py`

### Commits on the branch since round 1
```
0de9e6e w3-f: fix round 2 -- one rule for a completed null draw, a failed draw is linked, the pan view never sells the suggestion
f102dee w3-f: fix round 2 tests (red) -- one rule for a completed null draw, a failed draw is linked, the pan view never sells the suggestion
```
