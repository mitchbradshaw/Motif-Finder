# seed-search — report

Branch `worktree-agent-a8911e43024244b47`, worktree `.claude/worktrees/agent-a8911e43024244b47`, base `32bef5b` (main, AR merged at `5a20070`).

## In plain words (for the researcher)

Think of the preview as a fishing trip that already brought the catch home. Before, keeping the fish meant
going out and catching them again. Now *Use these as detections* keeps the catch you are looking at: the
preview's matches at or below your cut become a run, in seconds, with nothing searched twice. The page is four
steps in a row — pick the exemplar, run the preview, choose the cut on the histogram, keep the matches — and only
one step's card is open at a time. *Run with the rigorous null* is still there for a result you will report
(200 paired surrogate runs per channel). "No null" is gone. When a run is done, *Send unjudged to Review* puts its
detections in your Discovery picked queue.

## Assumed

- **How "no second search" is done through fanout's writers.** Before the keep's sweep, each channel's one step
  (`detection.seed_matches`) is placed in the step cache under the recipe's own key, built from the preview's
  matches. The sweep is the ordinary `fanout.start` → `run_paired_recipe(surrogate=False)` → `execute_recipe`. It
  gets a cache hit, matches nothing, and writes the same `runs`, run group, config hash and `detections` a run of
  that recipe writes. After the sweep the entries are removed: `_start_sweep` has a new `on_exit` hook, which runs
  whether the sweep finished, was cancelled or failed. The step cache therefore only ever holds what a block
  computed.
  - Run-group semantics are unchanged.
  - `fanout.py` is not edited.
  - The recipe is the one the old `nullMode: 'preview'` run made, with `max_distance = cut`. Its identity is that
    run's too, so either one answers a second press of the other.
- **The keep cuts by the block's unrounded distance.** Candidates now carry `distance` beside the rounded `d`.
  Detections are scored with it.
  - For a native-length search, and for a scale bank under `lowest` or `all`, the preview's matches at or below the
    cut are exactly what the block returns with `max_distance = cut`.
  - Under a bank with overlap `first`, a far-off match found earlier can hide a closer one in the preview but not in
    a cut run. The keep then writes the preview's set, which is what the researcher asked for.
- **The keep waits for its own sweep** (up to `KEEP_WAIT_S = 60` s) and answers `done`, `found` and `detectionIds`.
  Past that, it answers the job and the page watches the run row.
- **A restored preview may be cut short.** After a restart the session row keeps only the 5,000 closest candidates.
  When the cut would keep all of them, the keep refuses with a 409 and asks for the preview to be run again.
- **A second press after the preview is gone** (restart, or another query run since) still answers the existing
  live row with the same identity. It does not refuse a keep that has already happened.
- **`off`.** A run asking for it gets a 422 that gives the reason. A read carrying it (the estimate) reads as
  `preview`. On the client, `?null=off` is simply ignored, because the Seg and its query key are gone. Old rows
  with `nullSource: 'off'` still display as before (chrome.tsx).
- **The page opens on:**
  - step 1 when a picker tab is named in the URL (`?source=`) or there is no seed;
  - otherwise step 4 if this seed and cut are already kept or run, step 3 if a preview is held, and step 2 if not.

  The session always remembers a seed, so the strip shows step 1 done with its name.
  - Picking a seed walks to step 2.
  - Choosing a picker tab stays on step 1.
  - A preview landing while `?step=2` opens step 3.
- **The six advanced controls** (algorithm, window, scale bank, exclusion zone, overlap, draw count) and *Revert to
  recommended* are in step 2, because each one changes the preview's query.
  - "Draw count" is the session's null chip (`NullChip`), moved there from the toolbar. Its count is still set on
    the scope or in Settings › Nulls; this page adds no new control.
  - Revert leaves the cut alone.
  - The toggle is `?adv=1`.
- **Carry / rebind** moved into *Save as template*, since it is a property of the template. The button is muted
  blue and has one line saying it saves the recipe, never the matches.
- **The cluster route replaces the *rigorous* button, not *Use these*.** The keep searches nothing and is never
  over a limit. The estimate the page reads is the paired run's (`nullMode=paired`); when its route is `cluster`,
  the rigorous button becomes *Run it on the cluster*, with this line: "about X here with the rigorous null, over
  the Y limit — run it on the cluster". *Import HPC result* is in that state, and in an `on cluster` run's state in
  step 4. The Runs card's row was not edited, because `chrome.tsx` is not mine (see Open questions).
- **Send unjudged to Review** uses `sendDetectionsToReview(runKey, ids)`, Discovery's picked queue (fixup-AL):
  - The ids come from the keep's answer, or else from the existing `/api/discovery/detections` read, per channel
    in scope.
  - The picked queue has no cap: `_send_picked` takes every id. One send is at most k × channels (200 × 16 = 3,200
    on the real session), all into the one picked queue.
  - The toast says how many were added, how many were already judged, how many a human verdict covers, and how many
    were already in the queue, with *Open Review*.
- **The distance profile** is behind "show the distance profile" in step 3 (`?profile=1`). The match cards are
  under the histogram.

## The strip — one sentence per step

1. **Pick the exemplar** — the seed card: the source tabs, provenance and *change seed*, with the picker. "+ seed"
   and carry/rebind are gone from it.
2. **Run the preview** — *Run preview* with its estimate, then its real job progress with Cancel. Once the preview
   is in, a summary (N matches · D-draw null per channel) and *Next*. Under it, the closed *advanced* toggle.
3. **Choose the cut** — the histogram with the orange draggable handle and the green recommended line (it used to
   draw the recommended line at the cut in force), the number field, "back to the recommended", the kept / null-per-draw
   line, the rule, the per-length null, the matches card and the optional distance profile.
4. **Keep the matches** — *Use these as detections* (primary) and *Run with the rigorous null* (or the cluster
   button over the limit), each with its cost line. Then *Save as template*. When done: *Send unjudged to Review*
   and *Open in Runs*.

## The keep route's contract — `POST /api/discovery/seed/keep`

- **Body:** the preview's query, `SeedBody`: `seedId`, `channels`, `t0`, `t1`, `k` (200), `scales`, `overlap`,
  `exclusion`, `maxDistance` (0), plus `cut` (null keeps every candidate) and `label`. `nullMode` is ignored; it is
  always the preview's.
- **200:** `{run_key, label, job_id, reused, started, status, done, found, detectionIds, nullFrom: 'preview', note}`.
  - It writes one `discovery_runs` row with kind `seed` and `params.null = {paired: false, imported: true, source:
    'preview', kept: true, draws, drawn, method, key, expectsByChannel}`, plus `params.kept`.
  - Through `fanout.start` it writes one `runs` row per channel, in one run group, and one `detections` row per kept
    match: channel-absolute start, end = start + length, score = distance.
  - It writes no surrogate runs and no verdicts.
  - `/runs` (status `done`, `found`, `nullSource: 'preview'`), `/fires` and `/scoreboard` read it on the next request
    (pinned). The scoreboard's null-expects comes from `expectsByChannel`.
- **409 `{message, needsPreview: true}`:**
  - no preview of the query is held;
  - the restored preview may be truncated;
  - the held preview covers another section.

  The page then goes back to step 2.
- **Second press with the same identity:** `reused: true`, the same `run_key`, and its `detectionIds`, even after
  the preview is gone.
- **422:** the same refusals as a run (unknown or held-out channel, scope not runnable).
- **500 with the traceback:** the keep's own sweep failed.

## Files

- **Modified, mine:**
  - `webui/server/discovery.py`. The `nullMode` change: `NULL_MODES`, `_null_mode(read=)`, the estimate, and the
    `off` branches of `run_seed_search` removed. Also `distance` on candidates, the `on_exit` kwarg on
    `_start_sweep` (small and additive), and the keep route with its helpers (`_kept_candidates`,
    `_lay_preview_steps`, `_take_back`, `_seed_row_existing`, `_kept_ids`, `_keep_answer`), placed before
    `/seed/slurm`.
  - `webui/client/src/discovery/SeedPage.tsx`, rewritten around the steps.
- **Created:**
  - `webui/client/src/discovery/seed/StepStrip.tsx`
  - `webui/client/src/discovery/seed/KeepCard.tsx` (also `ImportResultButton`, moved here)
  - `webui/smoke_pages/zzzzzzzzzzz_a1_seed_search.json`
  - this report
- **Shared, append-only:**
  - `webui/client/src/api.ts`: `DiscSeedKeepAck`, `keepDiscoverySeedMatches`, at the end. `DiscNullMode` still
    lists `'off'`; it was left alone under the append-only rule.
  - `webui/client/src/api/discovery.ts`: an import line, plus `keepSeedMatches` and `runDetectionIds` at the end.
  - `webui/client/src/discovery/discovery.css`: a block at the end.
- **Tests:**
  - `tests/test_webui_discovery.py`: five tests and helpers, at the end.
  - `tests/test_webui_seed_hpc_route.py`: the "null off" test, which encoded the retired behaviour, is now the keep
    that replaces that quick run.
- **Not edited:** `Working/discovery/fanout.py` (no writer had to be exposed), `chrome.tsx`.

## Tests

- **Red** (`0697060`, webui/.venv python):
  - `test_webui_discovery.py -k "keep or null_mode_off"`: 5 failed.
  - `test_webui_seed_hpc_route.py -k quick_run`: 1 failed (`off` accepted, 200 != 422).
- **Green** (webui/.venv python unless noted):
  - `tests/test_import_boundaries.py` (conda python): 4 passed
  - `tests/test_webui_seed_hpc_route.py`: 14 passed
  - `tests/test_webui_seed_on_demand.py`: 11 passed
  - `tests/test_webui_seed_page_repairs.py`: 9 passed
  - `tests/test_webui_seed_sources.py`: 18 passed
  - `tests/test_webui_discovery.py` (whole file): 73 passed (8 min 44 s)
- **What each pins:**
  - `test_keep_writes_the_previews_matches_at_or_below_the_cut_without_a_second_search`: the block's matcher and
    `seeded_search.candidates` are patched to raise, so no second search can happen. It checks:
    - exactly the matches at or below the cut, per channel, with their starts, ends and scores;
    - one run per channel in the row's run group, and no surrogate runs;
    - the null is `preview` with the preview's draw count;
    - `detectionIds` are the run's;
    - the step cache is unchanged and no adjudication is written;
    - `/runs`, `/fires` and `/scoreboard` read the run on the next request.
  - `test_a_keep_with_no_preview_is_a_409_that_says_so_and_writes_nothing`.
  - `test_a_second_keep_with_the_same_identity_returns_the_same_row` — also after the preview is gone.
  - `test_a_keep_after_a_restart_reads_the_preview_back_from_the_session` — from `state_json`.
  - `test_the_null_mode_off_is_gone_and_an_old_page_asking_for_it_reads_preview`.
  - `test_the_quick_run_is_now_the_previews_matches_kept_and_review_can_take_them` (seed_hpc_route): over a 1 s
    ceiling, `off` is refused, the keep works, the scoreboard shows a null, and the run-wide Review send takes it.
  - The paired path is unchanged; the existing tests in seed_hpc_route, seed_on_demand and seed_page_repairs pin it.

## Gates I ran

- `tsc -b` and `vite build` through the junction both pass (vite built `discovery-*.js`; only the existing
  INEFFECTIVE_DYNAMIC_IMPORT warning for Gallery).
- The test files above, one at a time.
- No browser smoke (no database in a worktree).

## Smoke states — `webui/smoke_pages/zzzzzzzzzzz_a1_seed_search.json`

This file sorts last, because one state writes a run.

1. **`seed-search-the-strip-shows-four-steps`.** The strip shows "Pick the exemplar", "Run the preview", "Choose
   the cut" and "Keep the matches". There is no null Seg, no apply bar and no "+ seed".
2. **`seed-search-advanced-is-hidden-by-default`** (`?step=2`). The params card has `data-open="0"`. The six
   controls (algorithm, window, scale bank, exclusion, overlap, the null chip) and Revert are absent.
3. **`seed-search-advanced-opens-the-six-controls`.** After the toggle, all six controls and Revert are present.
4. **`seed-search-after-the-preview-the-cut-card-is-open`.** The state presses Run preview (if no preview is held)
   or Next. The strip reads step 3, and the cut card, histogram, handle and matches card are present. The seed card
   and keep card are absent.
5. **`seed-search-use-these-as-detections-makes-a-run-row`.** The state chooses a cut if none is in force, walks to
   step 4 and presses *Use these as detections*. It expects the done line, *Send unjudged to Review*, *Open in
   Runs* and *Save as template* with its line.
6. **`seed-search-the-kept-run-is-on-runs`.** *Open in Runs* lands on the selected row with
   `data-status="done"`, "null from the preview".

**Which states need the full walk.** No state names a run that another unit's flow creates, and none waits on
`.dsc-toolbar`: each one waits for `seed-steps` or its own cards.
- States 1–3 judge the page alone.
- States 4–6 need the session's draft seed and scope. The walk's 80–84 h section keeps the preview to seconds, and a
  preview may already be held from `Smoke.seed_page_query`. State 4 presses Run preview when no preview is held.
- State 6 depends on state 5's kept run, inside this unit.
- So judge 4–6 in a full walk, or in a unit walk run after the walk's scope is set.

**On real data, please check:**
- that the keep on the 16-channel session answers well inside 60 s;
- that the toast counts look right after *Send unjudged to Review*.

## Retired and affected smoke states (not edited)

**`webui/smoke_pages/discovery.json`, retire:**

| State | Why |
|---|---|
| `default` | expected the seed card, cut histogram and match grid at once; replaced by state 4 above |
| `source-explore` | expects `apply-bar` |
| `running` | the simulated `?state=` strip is removed |
| `done` | the simulated `?state=` strip is removed |
| `failed` | the simulated `?state=` strip is removed |

**`webui/smoke_pages/discovery.json`, change the hash:**

| State | New hash |
|---|---|
| `source-medoid` | `discovery/seed?step=1` |
| `change-seed` | `discovery/seed?step=1` |
| `view-popover` | `discovery/seed?step=3&profile=1` |

`modal-save-template`, `save-template-invalid` and `held-out-refused` are unaffected.

**Other units, affected (not mine):**

| File | State | What to change |
|---|---|---|
| `library_edges.json` | `fixup-v-scale-bank-searches-every-length` | the bank control needs `?entry=697&step=2&adv=1`; `null-per-length` is in step 3 |
| `seed_sources.json` | `fixup-y-picker-pages-the-library`, `fixup-y-picker-filters-by-kind` | add `?step=1` |
| `seed_sources.json` | `fixup-y-seed-search-from-review` | the provenance (step 1) and the params card (step 2) are no longer on screen together: split it, or expect `[data-testid="seed-steps"]` and `params-card` |
| `zzzz_ad_suspected_artifact.json` | `fixup-ad-exclusion-zone-settable` | `discovery/seed?step=2&adv=1` |
| `zzzzzzzzzzz_a2_p4_seed.json` | `a2-p4-not-previewed-runs-nothing` | the exclusion slider is behind advanced (open it with `seed-advanced-toggle`), and `apply-no-cut` is gone (retire that expectation) |
| `zzzzzzzzzzz_a2_p4_seed.json` | `a2-p4-restore-the-walks-section-and-draft` | the bank control needs `&step=2&adv=1`; `null-per-length` is in step 3 |

`a2-p4-family-medoids-are-library-entries` (`?source=family` opens step 1) and `a2-p4-preview-cancelled` (no
preview opens step 2) should still pass.

## Open questions and risks

- **Prompt item 5.** `SeedPage.tsx` holds no hard-coded 3. The two "three" labels left are in `chrome.tsx`'s
  ScopeCard: line 291, "strips page three at a time", and line 322, "next three channels". Not edited, because
  the file is not mine; each is a one-word change to `${PAGE_SIZE}`.
- **The Runs card's on-cluster seed row** still says "import … on the Seed page". *Import HPC result* on the row
  itself needs `chrome.tsx` (RunRow, which `discovery-coverage-and-gauge` and `reports` also edit).
- **Overlap `first` with a scale bank:** the kept set is the preview's, which can differ from a fresh cut run (see
  Assumed).
- **A held preview pre-dating this change has no `distance`.** Its matches are cut by the 4-decimal `d`, so a match
  within 5e-5 of the cut can fall either way.
- **The first paint can move.** With a preview held and no `?step`, the page opens on 2 until the peek answers, then
  moves to 3 (or 4).

## Commits

- `0697060` seed-search: failing tests for keeping the preview's matches as a run
- `1da420d` seed-search: four steps; keep the preview's matches with no second search; no "no null"
- (this report)

## Critic round

**In plain words.** The keep is sound. To write the rows without a second search, it leaves a "pre-filled answer"
in the shared step cache while its own run reads it, then removes it. If the server stopped mid-keep, that
pre-filled answer could stay behind for good, and a later run of the same recipe could read it as if a block had
computed it. The keep's entries now sit in a folder of their own, and anything a lost keep left there is cleared
before the next keep and when the lost run is noticed.

**Verdict: merge after the fixes below.**

### Findings

1. **Should-fix, FIXED (`c2bf7c7`): the keep's step-cache entries could outlive a lost sweep.**
   - The entries were laid at the block's own cache path, `<root>/<prefix>/0`. When the server stopped mid-sweep,
     `on_exit` never ran.
   - A retry then found the entry "already there". `_lay_preview_steps` skipped it, so it was never in `laid` and
     never taken back.
   - From then on the entry was permanent. Any later run with that recipe prefix would be served the preview's
     matches as if a block had computed them, for example an Analyse chain that starts with
     `detection.seed_matches`, or a forced run.
   - **How serious.** For a native-length search, or a bank under `lowest` or `all`, the preview's set at or below
     the cut equals the block's output with `max_distance = cut`. The greedy exclusion picks closest-first, so a
     cut never changes which closer match survives. Also, `find_completed_run` reuses a finished kept run for an
     identical recipe anyway. Under a bank with overlap `first` the two sets can differ, and that is where a
     leftover entry would give a wrong answer.
   - **The fix.**
     - Entries are laid under `<root>/_kept_preview/<token>/<prefix>/0`.
     - The token is live in this process while its keep runs.
     - `_take_back_lost_keeps` removes any `_kept_preview` entry whose token is not live. It runs before each keep
       lays, and when `_fail_lost_runs` fails a lost keep.
     - The take-back no longer deletes a block's own entry for the same prefix written meanwhile (`INSERT OR
       REPLACE` with a different path).
   - **Test:** `test_a_keep_whose_take_back_never_ran_is_cleaned_up_by_the_next_keep`, red before the fix.
   - **Still open, accepted.** While a keep's sweep is in flight (seconds), a concurrent run of the identical recipe
     would read the laid entry. Its answer would be the same except under bank + `first`.
2. **Should-fix, FIXED (`c2bf7c7`): the page's kept count and the bridge's cut could disagree.**
   - The page counted `d` (rounded to 4 places) against the cut, while the bridge cuts by the unrounded `distance`.
   - So "N matches at d ≤ X" could become N−1 detections for a match within 5e-5 of the cut.
   - The page now counts by `distance` (`distance ?? d`), carried through `SeedMatch` / `DiscSeedMatch`.
3. **Should-fix, FIXED (`c2bf7c7`): button colours.**
   - *Run with the rigorous null* was the grey default, which the researcher reads as "do not click"
     (2026-10-13).
   - *Save as template* used a one-off CSS class, `dsc-btn-quiet-blue`.
   - Now *Use these as detections* is the step's green `next`. The rigorous run and *Save as template* are the
     kit's quieter blue `primary`. The custom class is removed.
4. **Checked, no change.**
   - A cut that keeps nothing on a channel still writes that channel's run, `completed` with 0 detections. This
     is pinned now by `test_a_cut_that_keeps_nothing_on_a_channel_still_writes_that_channels_run`.
   - The 5,000-candidate restore cap is sorted by distance, so the refusal "the cut keeps all of them" is the
     right test.
   - A scope or section change is a different preview key, so the keep answers 409.
   - The held-out lock applies (`_ids_for`).
   - Rule 5 holds: no adjudication is written (tested).
   - The keep route forces `route = local` and never plans windows, so no windowed fan-out bypasses the laid
     step.
   - The cache root is read at request time (`cfg.STEP_CACHE_ROOT`), so the sandbox redirect covers it.
   - The changed test in `test_webui_seed_hpc_route.py` is a real pin. `off` now gets a 422, the keep over a 1 s
     ceiling works, the null is the preview's, and the Review send takes it.
5. **Blocker, FIXED (`seed-search fix: the no-cut sentence…`): `tests/test_webui_seed_on_demand_client.py` was
   red, and the implementer had not run it.**
   - `test_the_seed_page_has_run_preview_cancel_and_says_what_a_run_without_a_cut_keeps` looked for `apply-no-cut`
     and "matches per channel kept" in `SeedPage.tsx`. Both went with the apply bar.
   - Step 4 now says it: `apply-no-cut` in `KeepCard.tsx`, "no cut · the rigorous run keeps all 200 matches per
     channel kept by the search". The test reads `SeedPage.tsx` and `KeepCard.tsx`. This deliberately changes the
     test, because the apply bar is gone.
   - **The unit's name.** The unit is renamed `zzzzzzzzzzz_a1_seed_search.json`, at the manager's instruction. A
     manifest that opens `discovery/` must sort before `zzzzzzzzzzz_a2_p4_seed.json`.
   - That test still fails on this base, but only for AR's `zzzzzzzzzzz_ar_speed.json`. Main renamed that file to
     `zzzzzzzzzzz_a1_ar_speed.json`, and the manager reconciles it at merge.
   - Because of the rename, the kept-run state now walks BEFORE the a2-p4 unit. The a2-p4 unit's first state
     changes the draft (family medoid, zone = m) before it presses anything, and its last state puts back the
     walk's section and draft, so its states are unaffected.
6. **Not fixed (low): two keeps racing.**
   - Two simultaneous presses can both miss `_seed_row_for`'s look-up and make two rows. The same race was
     already there for `/seed/run`.
   - The button is disabled while keeping, so only two tabs could do it.

### Smoke states (`c1c7136`)

- **`discovery.json`:**
  - The seed page's `default`, `source-explore`, `running`, `done` and `failed` states are retired.
  - `source-medoid` and `change-seed` now open `?step=1`.
  - `view-popover` now opens `?step=3&profile=1`.
- **The other units, as the table above listed them:**
  - `fixup-y-seed-search-from-review` is split into two states: the step it opens on, and
    `...-provenance`, which clicks step 1 of the strip.
  - The bank states walk to step 3 for the per-length null.
  - `a2-p4-not-previewed-runs-nothing` opens advanced before the slider and drops `apply-no-cut`.

### Gate after the fixes

Each file was run alone.

**webui/.venv python:**
- `test_webui_seed_hpc_route.py`: 14 passed
- `test_webui_seed_on_demand.py`: 11 passed
- `test_webui_seed_page_repairs.py`: 9 passed
- `test_webui_seed_sources.py`: 18 passed
- `test_webui_discovery.py`: 75 passed (73 before, plus the 2 critic tests)

**conda python:**
- `test_import_boundaries.py`: 4 passed
- `test_webui_seed_on_demand_client.py`: 15 passed, 1 failed. The failure is only AR's old unit name, which main's
  rename fixes.

**Client:** `tsc -b` and `vite build` pass.
