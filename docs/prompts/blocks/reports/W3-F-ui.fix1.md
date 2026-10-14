> Filed by the manager session, 2026-10-15 — the final message of implementer agent `a9bcefee16fc666b3`, resumed for
> fix round 1 (decision 25) and the W3-C follow-up (merge of `617edc2`) on branch `worktree-agent-a9bcefee16fc666b3`
> (merge `f42dd35`, red `ff5bc21`, green `ea59ee6`), verbatim.

## W3-F fix round 1 report

I fixed the blocker and all six other items from the critic's report, and merged W3-C at `617edc2`. The branch is red `ff5bc21` → green `ea59ee6`, on top of the merge commit `f42dd35`. I could not run the browser smoke walk, so none of the smoke states have been run yet.

**The merge:** clean, no conflicts. The adapter count is 57 on both sides and all the `COSTED` lines are kept.

| # | Item | What changed |
|---|---|---|
| 1 | **Blocker: a cancelled null draw leaked its detections as real** | `Working/execution.py` now attaches the stopped run's `run_id` to the `RecipeCancelled` it re-raises. `draw_paired_null` uses it to link the half-finished draw to the run it belongs to (`surrogate_of_run_id`) before stopping. `null_summary` now counts completed draws only, since a half-finished draw covers only part of the chain. |
| 2 | **History said "failed" for a cancel inside a step** | A cancel's stored error text now always starts with "Cancelled". When a block wrote its own message it becomes "Cancelled: <block's words>". |
| 3 | **A run could start blind while its cost model was still being measured** | `app.py`'s run route answers 409 "calibrating: … try again in a few seconds" and starts no job. Every entry point is covered, the block page included. |
| 4 | **One slow measurement held up every other** | There is no longer a lock shared across models. Each model is measured by one thread, and different models are measured side by side. `block_cost.calibrate` holds a lock only around reading, merging and writing the file, never during the timing itself. |
| 5 | **The cancel smoke state was a race** | It now zooms out 13 times (about 389 h) and uses 3 h windows, about 130 of them. On a synthetic 389 h random walk the step took **14.9 s**, with the first progress mark at 0.13 s and a new one every 0.115 s. That should leave `step-fraction-3` visible for about 15 s, but I haven't confirmed the timing on a real bridge. I tried 1 h windows first: 259 windows finished in 3.3 s, too short. |
| 6 | **Nits** | The window-matrix comment now says what is true: an existing resume file is untouched, and the cancelled run's computed cells are discarded. `runtime._core_paths` now checks `block_cost.CALIBRATION_PATH`. |
| 7 | **W3-C follow-up** | The pan payload now carries the cleared band (`cleared_s`), `suggestion_rule`, `reasons`, and each length's `cut` and `reason_code`, plus W3-C's caveat that the suggestion is not the event's length. `approximate_note` is gone. The Encoding view leads with the band ("clears from A to B s"), shows the suggestion as "(strongest of the band)" with the caveat beside it, and shows the cut next to the gap per length. The two pan smoke states need no changes: the parameters they set still exist. |

**Tests**
- Red, `ff5bc21`, tests only:
  - `test_webui_run_cancel` (conda): 3 failed. The leaked count was 6 detections against the real run's 3, both calling `draw_paired_null` directly and through the run manager; there was no `run_id` and the text didn't start with "Cancelled".
  - `test_webui_run_routing` (venv): 3 failed (no 409, the fast model waited behind the slow one, History said not cancelled).
  - `test_webui_w3f_payloads`: 2 failed.
  - `test_webui_w3f_ui`: 3 failed.
- Green:
  - Conda, 4 workers: 324 passed, 7 skipped. This covers the w3f files, `test_execution`, `test_run_groups`, `test_surrogate_never_a_detection`, `test_block_standard`, `test_adapter_spec`, `test_import_boundaries` and `test_templates`.
  - Venv: 167 passed, covering `test_webui_run_routing`, `run_cancel`, `w3f_payloads`, `block_views`, `runtime`, `serialize`, `mpdist_edges`, `family_views`, `w2f_ui`, `job_estimate` and W3-C's two pan test files.
- `npx tsc -b` and `npm run build` are clean, built in a scratch copy. The junction was removed with `cmd /c rmdir` first, and the main checkout's `node_modules` is intact.
- One test changed after red: the cancel-state pin moved from `"3600"` to `"10800"` because 1 h windows measured too short. The commit message says so.

**What I could not do**
- **Other readers still count a half-finished draw as a draw.** Three places I didn't touch still count every linked null run, completed or not:
  - `Working/discovery/scoreboard.py::_null_runs`
  - `Working/library/matching.py` (~1309)
  - `webui/server/library.py` (~1709)

  After a mid-draw cancel in Discovery or a seed search, they would count the half-finished draw. They need a `status = 'completed'` filter. This mostly matters for Discovery: it passed `should_cancel` into its draws before this branch, so it could already leave half-finished, unlinked draws. Those are now linked as nulls rather than counted as real.
- **Nothing from the earlier full-suite run was re-run end to end.** The only failure there was `test_webui_discovery::test_the_scoreboard_cells_are_the_tables_own_numbers`, a known failure on main.

**Files outside the Deliver list, all of them**
- From round 0: `analyse/store.ts`, `analyse/useValidation.ts`, `analyse/InsertStageModal.tsx`, `webui/server/runtime.py`, `Working/block_cost.py`, `Adapters/preprocessing_window_matrix.py`, `discovery/AddMatches.tsx`, `analyse/views/GroupingView.tsx`, `library/Edges.tsx`.
- From round 0, in `serialize.py`: the `catalogue.cluster` −1 / `label_base` change. It serves W3-A's decision 7, not this prompt.
- From this round, handed over by decision 25: `Working/execution.py`, `Working/run_groups.py`, `webui/server/app.py`.

**Commits since round 0**
```
ea59ee6 w3-f: fix round 1 -- a cancelled draw stays a null, History reads cancelled, 409 while calibrating, no lock across models, the pan's final payload
ff5bc21 w3-f: fix round 1 tests (red) -- a cancelled draw leaks no detection, History reads cancelled, 409 while calibrating, one lock per model, the pan's final payload
f42dd35 Merge commit '617edc2' into worktree-agent-a9bcefee16fc666b3
```
