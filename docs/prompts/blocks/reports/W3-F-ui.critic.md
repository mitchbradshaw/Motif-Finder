> Filed by the manager session, 2026-10-15 — the final message of critic agent `ad9069dfbd66c843e` on branch
> `worktree-agent-a9bcefee16fc666b3` (`027561d`, `d1dc46c` on `a5baf8b`), verbatim.

## W3-F critic report: wave 3's UI (branch `worktree-agent-a9bcefee16fc666b3`, `027561d` red → `d1dc46c`, base `a5baf8b`)

### 1. In plain words
Most of this works. A long step can now be stopped from inside: on the real bridge code, multiscale entropy, cycle shapes and window matrix each stopped within one iteration. Each job read *cancelled*, nothing was cached for the stopped step, and the steps before it kept their cache. Background calibration also does what it says: one at a time, and a sandbox never writes the checkout's file. The three drawings take their verdicts from the block and never work one out themselves.

There is one serious new hole. Stopping a run while its **null** (the noise comparison runs) is being drawn now leaves that half-finished noise run unmarked as noise. Its detections then count as real detections, like rehearsal results ending up in the final scores. Smaller problems:
- the cancel smoke state is a race it will usually lose;
- a stopped run shows as "failed" in History;
- one slow calibration (rupture, 7.5 min) holds up all the others.

### 2. Verdict
**merge after fixes.** Finding 1 must be fixed before merge. Finding 2 should be fixed, otherwise the manager's smoke run of this state will probably fail.

### 3. Findings

**1. blocker: a cancel during a null draw leaks the draw's surrogate detections into real detections.** `webui/server/runs.py:229-234` now passes `should_cancel=should_cancel` and `run_kwargs` to `run_groups.draw_paired_null`. That function links a draw (`surrogate_of_run_id`) only after the draw completes (`Working/run_groups.py:338-345`; on `RecipeCancelled` it just `break`s). A draw cancelled between or inside its steps keeps its `runs` row with `surrogate_of_run_id = NULL`, so `not_surrogate()` treats it as real. Anything a detector step of that draw already wrote then shows up in:
- Explore's coverage (`corpus.py:268`, `342`, `364`), which does not filter on status;
- Review, divergence and the History list.

Before this branch a draw could not be cancelled midway (only `should_cancel_draws`, between draws), so the path is new.
- **Shown:** the chain detrend → noise_threshold → cycle_shapes on a 200 k-sample AR(1)+drops trace, with `draw_paired_null` called with runs.py's exact new wiring and cancelled inside draw 1. Result: runs `[{id 1, completed, 82 det}, {id 2, failed, surrogate_of_run_id None, 'Cancelled before step 3 (interrogation.c…', 13 det}]`. Detections counted as real: **95** (the real run found 82).
- **Fix:**
  - in `draw_paired_null`, on `RecipeCancelled`, link the partial draw row to `original_run_id` before breaking (have `execute_recipe` attach `run_id` to the exception it re-raises, or find the row by the draw's config hash);
  - add a test that cancels mid-draw and asserts zero extra `not_surrogate` detections.

  This touches the core (`run_groups.py` / `execution.py`), which is the right place.

**2. should-fix: smoke state `w3-cancel-inside-a-step` races and will usually fail.** The span is 2 h × 1.5⁵ = 15.2 h, with `window_s` 21600, which gives **2 windows**.
- **Shown:** I timed MSE on exactly that geometry (54,675 samples at 1 Hz, numba warm). The whole step takes **1.35 s**. The first progress mark arrives at 0.70 s, so `step-fraction-3` exists for about 0.6 s. Smoke then has to notice it, click `cancel-button`, and the POST has to land before the second window ends. If it misses, the run completes and the cancel button disappears. The click then times out (Playwright's 30 s), or `chain-row-3[data-status=cancelled]` never appears. It fails loudly rather than hanging, but it fails.
- **Fix:** make the step long and finely grained. For example, `window_s` 3600 over the whole recording (dozens of windows, many seconds), or window matrix with `slow_entropy` on the zoomed span. Either keeps `step-fraction-*` alive for several seconds.

**3. should-fix: a step cancelled from inside shows as "failed" in History.** `webui/server/app.py:373` flags a run as cancelled only when `error_text.startswith("Cancelled")`. The in-step messages are:
- "Multiscale entropy cancelled after 3 of 55 windows"
- "Cycle shapes cancelled."
- "window matrix cancelled with 29 of 333 windows computed"

The job snapshot reads *cancelled*, but History says *failed*. I observed exactly those error texts on the run rows.
- **Fix (either):** prefix the stored error text in `execution.py`'s `except RecipeCancelled` (e.g. `"Cancelled: " + str(e)` when it does not already start with that); or start each block's message with "Cancelled". Add a History test.

**4. should-fix: one calibration at a time means rupture (447 s by the implementer's measurement) holds every other model.** `_BC_RUN_LOCK` (`chain.py`, in `_calibrate_block_cost`) is held for the whole timing. Meanwhile:
- MSE, snippets and the rest read "calibrating" and **Run is disabled** (`ChainPage.tsx`, `canRun … && !calibratingTitle`) for up to about 7.5 min;
- every validate request blocks 10 s, and the page re-asks every 3 s.

**Shown:** a fake 4 s model followed by a fast one: the fast one waited **3.8 s** behind it.

**Fix:**
- hold the lock only around the read-merge-write in `calibrate` (the merge already makes concurrent timings safe), or give each model its own lock;
- separately, fix rupture's calibration signal (implementer's follow-up).

Related: timings taken while a run executes in the same process are inflated by CPU contention. That errs toward refusing runs, so it is acceptable, but it is worth a comment.

**5. should-fix: a run started from the block page is not held while calibrating.** `webui/client/src/analyse/BlockPage.tsx:56` `canRun` does not include `calibrating`. `POST /api/runs` → `route_local` waits 10 s, then returns `route: "unknown"` and the run **starts blind**. That is what acceptance item 3 says should not happen ("calibrated, or reported 'calibrating', before routing").
- **Fix:** refuse server-side, so every entry point is covered. In `app.py`'s run route, when `routed["calibrating"]` is non-empty, answer 409 with "calibrating, try again in a few seconds". Alternatively, gate `BlockPage` the same way `ChainPage` is.

**6. nit: the window-matrix comment is wrong.** `Adapters/preprocessing_window_matrix.py:125-127` says "A resumable build (`resume_path`) has already saved what it computed". It has not. `build_window_matrix` never writes, and saving happens in `_persist`, which no longer runs once the adapter raises.
- **Shown:** after a cancel at 29 of 333 windows, no `.npz` was written.
- **What is true:** an existing resume file is untouched, and the cancelled run's computed cells are discarded.
- **No caller relied on the partial return:**
  - the bridge, Discovery (`fanout`, `discovery.py`), Models/training routes and HPC `run_recipe.py` pass no `should_cancel` to this adapter;
  - `Pipelines/window_matrix_build` calls `build_window_matrix` directly, and its `timed_out` partial path is unchanged.
- **Fix:** correct the comment, or persist the partial matrix on cancel when `resume_path` is set.

**7. nit: `runtime.py` redirects `block_cost.CALIBRATION_PATH` but does not add it to `_core_paths`.** The startup refuse-if-outside / refuse-if-redirected check therefore does not cover it, though `mp_cost.CALIBRATION_PATH` is covered.
- **Fix:** add `("block_cost.CALIBRATION_PATH", _bc.CALIBRATION_PATH)` to `_core_paths`.

**8. nit: scope is under-reported.** Besides the six out-of-list files named in the report, these are also outside the Deliver list:
- `webui/client/src/discovery/AddMatches.tsx` (Discovery);
- `webui/client/src/analyse/views/GroupingView.tsx` (the Analyse families table, plus the −1 grey change);
- `library/Edges.tsx` (arguably part of the Family page).

The `catalogue.cluster` −1 and `label_base` change in `serialize.py` serves W3-A's decision 7, not an item of this prompt. All are small and justified; they should be listed.

### Answers to the manager's questions

**1. Cancel inside a step: yes for all three.** Tested through `RunManager` with a temp DB and the step cache at threshold 0, on a 200 k-sample AR(1) φ=0.98 trace with drops:

| Step | Stopped | Job | Step statuses | Cache (per step) |
|---|---|---|---|---|
| MSE | 0.07 s after the cancel ("cancelled after 3 of 55 windows") | cancelled | `[done, done, cancelled]` | `[true, true, false]` |
| cycle shapes | 0.17 s | cancelled | — | `[true, true, false]` |
| window matrix | 0.05 s ("29 of 333") | cancelled | — | `[true, false]` |

- **Null draws stop:** with the null on (3 draws), a cancel mid-draw stopped draw 1 inside its MSE step. The real run stayed *completed* and cached, `null.cancelled = true` and `null_draws = 0`. The leak in finding 1 comes with this.
- **Window matrix callers:** none relied on the partial return (finding 6). An existing resume file is untouched, but nothing from the cancelled run is saved.

**2. Background calibration:**
- **Thread safety:** five concurrent asks gave **1** calibration and 1 thread. A failure reads `{state: failed, error: 'ZeroDivisionError…'}` and is not retried within 60 s (an immediate re-ask started no thread).
- **What validate returns while calibrating:** `route: "unknown"`, `estimate.calibrating: [i]`, `per_step_s[i]: null`, after up to 10 s.
- **Sandbox (temp root, Runtime with a temp DB):** the path became `<runtime>/critic/block_calibration.json` and the file was written there. The checkout's `DATA/db/block_calibration.json` was never created.
- **Project mode:** I pointed `runtime.REPO_ROOT` at a temp "checkout". The path stayed relative, `DATA\db\block_calibration.json`, and was written at `<temp repo>/DATA/db/`, as before.
- **Two processes:** the re-read-then-`os.replace` merge leaves only a millisecond window; the worst case is one lost entry, re-timed later. The 8765 project bridge and a sandbox write **different files** (the sandbox copies the real one at start), so they never race each other. Race-free enough.

**3. Drawings are payload-driven: yes.**
- **MSE:** `polylinePath` breaks the line at a null, and an isolated point is drawn as a dot.
- **Cycle stack:** reads `whole_verdict`, each group's `verdict` (`tested`, `beyond_noise`, `background_colour_mismatch`) and `key` as given.
- **Pan rows:** the per-length rows show `judged`/`clears` as given.
- **Family page:**
  - the σ² number comes from `variants[0]`;
  - `passed_by` is mapped to words;
  - the fallback check is `background.reason && null_kind` not starting with "quiet", as W3-G's report instructs.
- **MPdist:** `within === null` gives a neutral "—" with the footing as tooltip; only `within === false` is purple.
- **k-Shape badge:** left dormant and commented.
- **Grep of the client:** no score-against-null comparison in the new code (the only `null_p05` references are tooltip text and the existing comment).

**4. Existing pages:** no test or smoke state asserts colours or windowset caption text. The `has-text` selectors are all on Library, Interrogation and surrogate pages. `clusterColour` is used only inside `GroupingView`. The serialize, w2f_ui and block_views tests pass. Nothing would fail.

**5. Smoke states:**
- **Selectors:** I checked each one against the code: `step-fraction-${i+1}`, `chain-row-N[data-status]` (done maps to "cached"), `mse-curves`/`mse-curve`/`mse-median`, `cycle-stack`, `row-axis[data-unit]`/`row-axis-caption`/`row-verdict*`, `modal-card-*`, and block/N indices 0-based.
- **No same-hash navigation.**
- **The wavelet row axis is real:** 87 rows and 87 `freqs_hz` at both 7,200 and 54,675 samples.
- **MSE states:** 2 × 1 h windows take 0.2 s after a 1.8 s numba warm-up, so the timeouts are ample.
- **Pan states without W3-C:** they fail loudly at the 20 s `wait_for` on `modal-card-detection.pan_matrix_profile`; they do not hang.
- **Cancel state:** not viable as written (finding 2).
- **Earlier states:** many click `run-button` without waiting for it to be enabled. They click before the first validate answers, so they still run (route "unknown"). A cold MiniRocket or snippets calibration (61.5 s / 19.8 s) can add up to 10 s per request to those states.

**6. Scope:** the six declared files are justified and minimal:
- `store.ts`, `useValidation.ts`, `InsertStageModal.tsx` (one line);
- `runtime.py` (needed);
- `block_cost.py` (additive `path=`);
- window matrix (7 lines).

Three more are undeclared (finding 8).

**7. UI gate:**
- `npx tsc -b` exit 0, and `npm run build` exit 0 (built in 7 s), in a scratch copy with a junction to `node_modules`. The junction was removed with `cmd /c rmdir`, and the main `node_modules` is intact.
- Venv tests and conda tests: all green apart from the known Discovery failure (counts under "What I ran").

### 4. Five axes
- **Spec:** acceptance is met, apart from finding 5 (a Run from the block page is not held while calibrating) and finding 2 (the cancel smoke state). The tests would fail on a wrong implementation: the cancel test has a cached control, and routing uses a fake calibration with a delay.
- **Faithful:** not applicable (UI work).
- **Correct on our data:** findings 1, 3 and 4.
- **Standards:** no UI imports in `Working/` or `Adapters/` (`test_import_boundaries` passes), and errors are shown in words.
- **Test-first:** confirmed. `027561d` touches only `tests/` (4 files). I extracted it with `git archive`: `test_webui_run_cancel` + `test_webui_w3f_ui` gave **16 failed, 1 passed** (the control).

### What I ran
- **Venv** (`webui/.venv`), `-n 4`: run_cancel, run_routing, w3f_payloads, w3f_ui, block_views, serialize, library*, family_views, w2f_ui, block_standard, discovery. **465 passed, 3 xpassed, 1 failed:** `test_webui_discovery::test_the_scoreboard_cells_are_the_tables_own_numbers`, the known failure on main.
- **Venv:** test_webui_runtime, seed_hpc_route, run_routing: **38 passed.**
- **Conda**, `-n 4`: run_cancel, w3f_payloads, w3f_ui, test_execution, adapter MSE and cycle shapes, block_standard, import_boundaries, window_matrix_resume/artifact_name, job_export, hpc_exported_jobs, webui_job_estimate, discovery_fanout, webui_serialize: **381 passed, 7 skipped.**
- **Red check** on `027561d`: 16 failed, 1 passed.
- **Experiments** (scripts and outputs in the scratch dir `critic_w3f\`):
  - `cancel_real.py`: real-path cancels, the null cancel, and the leak proof `leak2`;
  - `calib_modes.py`: sandbox and project paths, thread behaviour;
  - `mse_time.py`: smoke-span timing;
  - `wt.py`: wavelet row axis;
  - `models.py`: all 16 `block_cost` models map to their adapters through `_block_cost_models`;
  - `smoke_scan.py`: which smoke states click Run.

No bridge was started, and nothing in the repo, the worktree or `DATA` was read for data or written.
