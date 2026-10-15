# UX-1015 — the manager's ledger (the researcher's 2026-10-13 list, run 2026-10-15)

The researcher asked (2026-10-15, then away): push main, start the small list, and run prompts AK–AP and AQ with a
sub-agent each, a separate critic per prompt, one fix round, and the manager's own evaluation and gate at the end.
Nobody answers questions during the run; every open choice is decided here and recorded.

## The plan

| Wave | Prompts | Why this order |
|---|---|---|
| A (now) | AK spike block · AM peak alignment · AN library dendrogram · AO decompose block · AQ cross-channel finish | disjoint files; none touches the small list's files |
| B | AL send one detection to Review | shares Discovery's Browse card with small item 1 (loading bar); starts after that lands |
| C | AP grey-text sweep | touches every page; runs alone after every other merge |
| manager | the small list: browser loading bar · no default chain · delete a block from its page · legacy-detections log once · slideshow paging | done directly on main, each with its test and gate |

Per prompt: implementer (Opus, medium effort, own worktree from main, `docs/prompts/fixup/UX-1015-common.md`) →
critic (Opus, medium, `docs/prompts/blocks/critic.md` adapted to UI work) → one fix round by the same implementer →
manager's gate (its tests under both interpreters, `tsc -b`, `vite build`, its smoke states walked on a sandbox
bridge, then the relevant page units) → merge into main. After the last merge: the full pytest suite, the full smoke
walk, the evaluation, the push.

## Decisions

| # | Decision | Why |
|---|---|---|
| D1 | `AJ-cross-channel-finish.md` renamed `AQ-…` (67746fc) | another session had taken AJ for the Jobs prompt |
| D2 | A `node_modules` junction at `.claude/worktrees/node_modules` → `webui/client/node_modules`, outside every worktree | agents can type-check and build their client changes; `git worktree remove` cannot reach it |
| D3 | AM is built on its own recommendation (`align ∈ {grid, centre, peak, trough}` + `anchor_frac`, defaults unchanged) | the prompt opens with a question; the researcher is away and asked for no interruptions |
| D4 | AP runs last and alone | it edits captions on every page the others touch |
| D5 | Agents cannot smoke; they write states, the manager walks them | no database in a worktree; the wave-3 precedent |
| D6 | Agents' client gates use the main checkout's toolchain through the junction, never `npm install`/`npx` | the environment is shared; nothing may be installed |

## Timeline

| When | What |
|---|---|
| 2026-10-15 | main pushed (3cc2f62 → 33add7f: the two 10-13 merges, waves 1–3, the units fix). |
| 2026-10-15 | 67746fc AJ→AQ; 3810555 the brief and this ledger (the base every implementer cuts from); wave A launched: AK, AM, AN, AO, AQ. |
| 2026-10-15 | small list on main: 255e08e/e330768 legacy-detections refusal warned once per process (test red then green, 12 pass); e7bde55/22d0b5e no default chain (empty canvas: import · add · example · restore last), delete a block from its page (`analyse/deleteStep.ts`), browser loading bar, slideshow pager free; smoke flow takes the Example start, the page walk seeds the old chain (`SMOKE_CHAIN`, `empty_chain` states). tsc + build pass. |
| 2026-10-15 | small-list gate: the four new states 4/0, the Analyse unit 47/0 on the seeded chain. |
| 2026-10-15 | AO reported; its critic launched. |
| 2026-10-15 | AM reported; its critic launched. |
| 2026-10-15 | AK's critic: merge after fixes (the halo blocker); the fix round sent to AK. AQ reported; its critic launched. |
| 2026-10-15 | AN reported (both halves); its critic launched. |
| 2026-10-15 | AO's critic: merge after fixes; the fix round sent to AO. |
| 2026-10-16 | AQ's critic: merge after fixes (curved drift); the fix round sent to AQ. |
| 2026-10-16 | AM merged as eb2c57a after its gate (298 + 13 tests, tsc, build, smoke 3/0 incl. the trough@0.33 Ward build on the real pool). AO's gate started. |
| 2026-10-16 | Full pytest on main after six merges (`-n 4`, 21 min, 1.46 GB free): 4107 passed, 44 skipped, 1 failed — the repo-wide guard `test_every_reader_of_detections_goes_through_the_predicate`: AL's `extend_queue` validated ids with a bare read of `detections`, so a paired surrogate's span could have been picked. Fixed on main: the read joins `runs` under `queries.not_surrogate`, a surrogate's id now reads as unknown; guard and queue tests green. The dedicated core test followed (11d3f29, passed on arrival; it pins the fix). AP launched from d2eed66; the usage limit stopped it mid-sweep (after Discovery › Runs, "next Discovery › Seed") and it was resumed on the reset with its worktree intact. |
| 2026-10-16 | AL merged as bf40695 after its gate. Six of seven merged; AP launched from this main. |
| 2026-10-16 | AN merged as 5078370 after its re-run gate (450 + 95 tests, tsc, build, smoke 6/0 incl. the real regroup). The stale scoreboard test (expected the pre-Q-D2 wording) now reads the server's `REVIEWED_CRITERION`. AL's gate started: tests, tsc, build, then its smoke with the flows. |
| 2026-10-16 | AN's first gate failed one conda test, `test_the_cancel_state_is_the_last_the_walk_runs`: the four merged prompts' smoke files (twelve z's) sorted AFTER `zzzzzzzzzzz_w3_cancel.json`, so the walk would have run them after the cancel state zooms Explore to the whole recording — a latent fault on main since AK's merge, which no earlier gate ran that test file for. Fixed on main: the four files renamed to eleven z's (before `w3_cancel`), the one test that named AQ's file updated; the w3f and cross-page tests green. AN's gate re-run. |
| 2026-10-16 | AL's fix round reported; its gate queued behind AN's. |
| 2026-10-16 | AN's fix round reported; its gate started. |
| 2026-10-16 | AQ's X3 confirmed on the real channels through the merged bridge (recording 2 = CH2_A1, the researcher's window 0.772–0.950 h): as recorded CH7_B2, CH8_B2, CH9_C1, CH10_C1 and CH11_C2 all read lag 0.0 and r −0.96…−0.98 — the screenshot's six rows; with each channel's straight-line trend out they read |r| 0.45–0.72 at lags −313…+221 s, binned independent, `drift_suspect` False on every row. The six zero lags were a shared linear drift over the window, not a curved one and not simultaneous pickup. |
| 2026-10-16 | AQ merged as aee1dcc after its gate (126 + 53 tests, tsc, build, smoke 11/0 incl. lag-aligned rows on the real channels). |
| 2026-10-16 | AL's critic: merge after fixes; the fix round sent to AL. |
| 2026-10-16 | AO merged as 868795d after its gate (371 + 75 tests, tsc, build, smoke 3/0). AQ's fix round reported; its gate started. |
| 2026-10-16 | AN's critic: merge after fixes; the fix round sent to AN. |
| 2026-10-16 | AL reported; its critic launched. |
| 2026-10-16 | AK merged as 06f94db after its gate (360 + 103 tests, tsc, build, smoke 2/0). AM's and AO's fix rounds reported; AM's gate started, AO's queued. |
| 2026-10-16 | AK's fix round reported; its gate started. AM's critic: merge after fixes (the smoke states); the fix round sent to AM. |
| 2026-10-15 → 16 | The account's usage limit stopped every running agent mid-task (the AK and AO fix rounds, the AM, AN and AQ critics, the AL implementer); their worktrees kept their work. All six resumed on 2026-10-16 from where they stopped, with their context intact. |
| 2026-10-15 | small-list hand check (Playwright on the sandbox, the example chain at threshold 2, 33 spans): after a card is picked, resample shows a different set and keeps it, show-in-order + next page moves and stays — 9/0, no console errors. The browser loading bar is wired to `dets.loading`; the sandbox re-reads a run's detections in under 25 ms so it cannot be caught on camera there. |
| 2026-10-15 | AK reported; its critic launched. The real DB holds no template naming `spike_v1` with `delta`, so the rename refuses nothing saved. |

## Agents

| Prompt | Branch / worktree | Implementer | Critic | Fix round | Gate | Merged |
|---|---|---|---|---|---|---|
| AK | `worktree-agent-a644f595894c2c76a` · `.claude/worktrees/agent-a644f595894c2c76a` | reported (cf28cc2 red, 3f93c92; fix round 3771e20 red, 0be45c0: one spike per cluster placed against the raw samples outside it, a δ-vs-deviation readout row amber below 4×, counts and unit note on the chain row, nits; 40 + 420 conda, 103 venv green; 25 tests green both interpreters; assumed: undeclared unit read as volts with a note, `delta`→`delta_mv`, default 1 mV placeholder; one edit outside scope in `views/registry.tsx`) | merge after fixes: BLOCKER the keep-first refractory rule misplaces a dip's spike and mislabels its direction (halo); should-fix a noise-relative readout row and `units_note`/up-down counts in the payload; two nits | sent (cluster candidates within d, keep max |x−a|, sign from it; readout row; payload pass-through; nits) → done (3771e20 red, 0be45c0) | OK: 360 conda + 103 venv, tsc, build, smoke 2/0 | 06f94db |
| AM | `worktree-agent-af4e07def4f10c2cc` · `.claude/worktrees/agent-af4e07def4f10c2cc` | reported (d8bc3cc red, c919001; 291+38 conda, 33 venv green; built D3: peak/trough + anchor_frac, defaults bit-for-bit; `allowed_interval` left as is by design; edits outside scope in `shape_forest.py` (recipe carries the anchor), `catalogue_shape_cluster.py`, `ShapeViews.tsx`, one line in `TreePage.tsx`, one existing line in `api/shape.ts`) | merge after fixes: the core is right and bit-for-bit at the defaults (8 combinations against main; keys move for peak, trough, any anchor ≠ 0.5); the smoke states assume a chain earlier files replace (blocker for the UI gate); the shared-file in-place edits and the out-of-scope edits judged necessary | sent (states rebuild their own chain) → done (a228520) | OK: 298 conda + 13 venv, tsc, build, smoke 3/0 | eb2c57a |
| AN | `worktree-agent-a9632a24a2cd9cf2b` · `.claude/worktrees/agent-a9632a24a2cd9cf2b` | reported, AN-1 and AN-2 both built (82c648d red, a3be71a, 7b4b4dc, 7129a9b, c9fec2d; 16+189 conda, 8+79 venv green; assumed: key = refs + content hashes + waveform digest + basis/method/params minus cut/omit_d/min_group/omit_small; tree as `.npz` under `DATA/derived/library/grouping_trees/` (sandbox: under the runtime); two additive `groupings` columns `tree_path`/`tree_key` (schema.py + its exact-column test, outside scope); `TreePage.tsx` exports its Dendrogram with optional cutHeight/leafWord; `LIBRARY_STORAGE.md` §6.4; one RQ1 line) | merge after fixes: results exact at every cut (300 and 3,000 members), rule 4 holds, schema additive, reuse calls linkage once; the preview takes 3–6 s at low cuts (the `omit_d` loop in `ward.assign`), the linear tree axis squeezes 0.1–1.0 into a few pixels, the file self-check skips the arrays (a tree for other members was reused) | sent (vectorise the omit rule + in-flight skip; a height transform or yMax on the dendrogram, slider 0.1–1; a digest over the arrays, key and length checks on reuse; nits) → done (6d546ff red, 69e21be: `assign` vectorised and pinned against main's loop — a warm cut on 3,000 members 0.06–0.26 s, was 0.5–6 s; one request in flight; a blake2b digest over the arrays, key and count checks on reuse, `_tree_state` compares the row's key; a √ height axis in the Library only, 100 drawn merges, slider 0.1–1; defaults filled before hashing; save and GET /tree read the tree only; 214 conda + 90 venv) | OK: 450 conda + 95 venv, tsc, build, smoke 6/0 on the real catalogue (api.ts append conflict: both kept) | 5078370 |
| AO | `worktree-agent-a7a1320a778cbd172` · `.claude/worktrees/agent-a7a1320a778cbd172` | reported (8b1ef3d red, 9290502; 406 conda + 74 venv green; assumed: running median baseline (`make_smooth`), noise = highpass(input − baseline) at fs/8 auto, NaN refused; edits outside scope in `views/registry.tsx` (the layer click) and `glyphs.tsx`; wavelet rows now clickable too) | merge after fixes: the 600 s help understates how much of a slow drop the baseline takes (60 s/600 s drop → 0.86 in baseline); the median's edge mechanism is end-sample padding, not a shrinking window (17 % of a 1 h span); the wavelet-row click sends the wrong layer when `levels` is auto; three nits | sent (half-window rule in help + description + a test; reflect-pad the median; revert the wavelet click; nits) → done (50473a2 red, 3ff6cbc: a cut-off drop keeps 0.996 of its depth; 412 conda + 75 venv) | OK: 371 conda + 75 venv, tsc, build, smoke 3/0 (api.ts append conflict with AK: both kept) | 868795d |
| AQ | `worktree-agent-aee352466a1bbd4ff` · `.claude/worktrees/agent-aee352466a1bbd4ff` | reported (cea65b3 red, dfb7a7b; 116 conda + 46 venv green; assumed: `?window=motif-n` = the n-th span in time order; page windows classified detrended (`detrend=linear`), edge windows and the Library as recorded; default channels = top 5 by |r| with no floor; X1 explained: the note printed a padded domain, 2 × reach × 1.12; `api/explore.ts` cross-channel section rewritten, not appended; RQ6 note added) | merge after fixes: a curved drift beats the linear detrend and bins as artifact with nothing on the row (exponential recovery: 100/100 artifact; a cubic detrend: 99/100 independent); a window reopened as `?t0=&t1=` is treated as an edge's (as recorded, unpadded); ~1 in 6 random-walk pairs bin as propagation (disclosure); X1, the bit-identity of `detrend=None`, the removed fallback and the no-floor selection all held | sent (rule wording, a `drift_suspect` flag on the row, edge-only as-recorded, RQ6 wording, nits) → done (03f7c9e red, 11fb009: `drift_suspect` on every compared row, `cubic` in DETRENDS on the bridge, edge-only as-recorded windows via `crossDetrendFor`, flat residuals read undefined, the picker tip, `getCross` removed; 126 conda + 53 venv) | OK: 126 conda + 53 venv, tsc, build, smoke 11/0 on the real recordings (api.ts append conflict: both kept) | aee1dcc |
| AL | `worktree-agent-ac300ca1248d4e989` · `.claude/worktrees/agent-ac300ca1248d4e989` | reported (99ee0e0 red, 8c0b955, ec9acf0; 66 conda, 94 venv green + the pre-existing scoreboard-wording failure; assumed: the picked queue is found by an exact note carrying the session id, kind discovery-run for template and seed runs alike, only the run's own detections, `picked` on the detections payload) | merge after fixes: the queue, the no-op repeat, rule 5 and the run-wide send all held; the green "in Review" tick shows for picks Review will never serve (a discarded run, an already-adjudicated detection, a human-covered one); the smoke states take whichever run is selected; `extend_queue` messages and id checks; a client-side id fallback; a possible Compare-queue collision | sent (refuse a discarded run; `picked` as a state waiting/judged/not-asked with the row text per state; `?run={run:a}` in the states; messages and id checks; nits) → done (644840f red, c82bf58: `picked` is Review's own state (waiting / judged · verdict / not-asked), the client re-reads after a send, a discarded run 422s before any write, `served` beside `total`, `extend_queue` validates ids and names each reason, Compare skips picked-note queues, states pinned to `{run:a}`; 69 conda + 98 venv) | queued (after AN; OK: 73 conda + 99 venv, tsc, build; its 3 states 3/0 with the flows (the walk's 2 other failures predate the wave) | bf40695 |
| AP | | | | | | |

## Gates

(filled as they run)

## Evaluation

`docs/prompts/fixup/reports/UX-1015-evaluation.md`, written after the last merge.
