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
| 2026-10-16 | The baseline full walk on main before AP: 704 screenshots, 42 failures (33 FAIL lines; the same pre-existing families seen on 10-13 plus the states that need the walk's flows). AP's build, bridge restart and full walk started; its failure set is diffed against this baseline. |
| 2026-10-16 | AP merged as aa7c97b: the full walk on the merged tree 708 screenshots, 18 failures (40 min); against the pre-AP baseline (704/42) no state failed that the baseline passed — the 18 are a subset of its 42 (the pre-existing families), the other 24 passed, every state of this wave among them; a second walk on the sandbox the discarded walk had used showed 6 extra failures that were all that sandbox's leftovers (a family already classified, artifacts already sent, settings already saved), so the gate walk ran on a fresh copy. The AO/AK first-state fix rode in the merge commit. Seven of seven merged; main pushed. |
| 2026-10-16 | AP's first full walk (685 screenshots, 55 failures, 1 h 50 min) is not a gate: `net::ERR_NETWORK_IO_SUSPENDED` hit the Analyse flow's job poll, the chain run never completed and every later state that needs it failed; no new server traceback (one plain-words refusal from the Decompose block on a one-sample span, under the wrong source). Two of the wave's own states (AO's first, AK's chain state) also fail in SEQUENCE though they pass alone: AM's file leaves the source on the window pool, where `use-example` is off screen; both now open the source chip and take the example span first. Keep-awake requested; the full walk re-run on the AP build with the fixed states. |
| 2026-10-16 | AP's fix round reported (9da51a7). A full smoke walk on main BEFORE AP started first as the baseline for the final diff; AP merged unsealed and type-checked meanwhile; its build, bridge restart and full walk follow the baseline. |
| 2026-10-16 | AP's critic: merge after fixes; the fix round sent to AP. |
| 2026-10-16 | AP reported (all 14 pages); its critic launched. |
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
| AP | `worktree-agent-aca4e2968061b942e` · `.claude/worktrees/agent-aca4e2968061b942e` | reported: 14 pages in the prompt's order, one commit each (0782c56 … b8f76d5); grey 578 → 467, InfoTips 132 → 203, never falling; the half target met on Explore › Signal and › Corpus only, the rest said to be data (absences, loading lines, numbers, field labels); no shared file touched; tsc + build after every page | merge after fixes: nothing lost (every removed sentence traced), every walk selector and text match intact, tsc clean; two next-steps went behind an ⓘ on the researcher's first pages (the motif pane blank), the Apply-clears-scope warning hidden, a hover-only cost breakdown, ~10 bare ⓘ icons, a few instructions left ("run the chain to see"); the "what remains is data" claim mostly holds | sent (empty state in the motif pane; the Apply warning visible; the cost breakdown into the popover; labels on the bare icons; the remaining instructions as actions; nits) → done (9da51a7: an EmptyState in the motif pane, the Apply warning visible in amber (`apply-clears-scope`), the cost breakdown as the popover's first line (`CostChip detail`, `cost-detail`) with "assumed" on the face, every bare ⓘ labelled or removed where it duplicated a note, `NoResult` and the three "not loaded" lines as EmptyStates with "Open the chain to run it", nits; grey 578 → 466, InfoTips 132 → 197) | tsc clean; build; the full walk on the merged tree 708 screenshots, 18 failures (40 min) against the pre-AP baseline 704/42: no state failed that the baseline passed — the 18 are a subset of its 42 (the pre-existing families), the other 24 passed, every state of this wave among them; a second walk on the sandbox the discarded walk had used showed 6 extra failures that were all that sandbox's leftovers (a family already classified, artifacts already sent, settings already saved), so the gate walk ran on a fresh copy | aa7c97b |

## Gates

(filled as they run)

## Evaluation

`docs/prompts/fixup/reports/UX-1015-evaluation.md`, written after the last merge.

## AR - the speed pass (launched 2026-10-18 evening, merged 2026-10-18 23:1x as 5a20070)

- Prompt `AR-speed-pass.md`; implementer on Opus in an isolated worktree; critic on the branch (no semantic drift over
  16 mutation steps, every cache invalidated; one blocker - cold thumbnails on a rows-only read - and seven should-fixes,
  closed in 1ff00ef); then main's a2-rq1b listed-order queue landed under it and the first gate merge raised
  `NameError: listed` (54 tests) - the implementer merged main into its branch (5c7994f) so the listed queue reads
  through the cached structure.
- Gate (per-merge rule, Q42): conda 324 passed (test_review_*, ar_speed_core, perf_scoring_reads, surrogate,
  candidate_events, rq1b script, import boundaries); venv 182 passed (webui_ar_speed, review, review_axis, corpus,
  discovery, listed_order, candidate_events, rq1b script); tsc clean; build. Smoke units ar_speed / review / discovery
  on a fresh sandbox: 0 console errors, 0 tracebacks in all three; the three review failures are the morning baseline's;
  the discovery cascade and the ar first-paint state failed on TIMING with the machine at 96 % CPU (another session's
  six parallel agents) - the same cascade reproduced on pre-AR code under that load earlier in the day.
- Realistic timings: BEFORE (19:04, fresh sandbox copy of the real DB, after the maps warm): queue 24 rows 5,257 ms /
  3.1 MB (3,195 items), item 382-872 ms, /runs 834 ms, picker > 240 s while scoring, fires (3 ch x 53 runs) 16.6 s,
  scoreboard 85 s, map L3 7.6 s. The AFTER run (23:0x) was taken on a used sandbox during the discovery unit's runs with
  the machine saturated and is NOT comparable (every route 5-50x slower, including untouched ones) - **owed: re-time on
  a quiet machine with `scratchpad/perf_before.py` and walk the three units; record here.** Scale-fixture numbers are
  in `AR-speed-report.md` (item read 28,702 -> 56 ms; verdict 16,948 -> 133 ms; coverage after restart ~116 s -> 1.3 s).
- Decisions recorded with the researcher the same evening: the per-merge gate (targeted tests + tsc + build + touched
  units; full pytest + full walk once a day by one manager; critic skipped under ~40 lines) - `docs/prompts/changes/README.md`.

### AR re-timed on a quiet machine (2026-10-19 02:33, load ~23 %, fresh sandbox copy, after the maps warm)

| read | before (18 Oct 19:04) | after (19 Oct 02:33) |
|---|---|---|
| bridge start: corpus maps warmed | 100-224 s (computed) | **1.0 s** (17 files read back from the disk cache) |
| review queue 24 rows, full (3,195 items) | 5,257 ms / 3.1 MB | 4,135 ms / 3.1 MB; the page's rows-only read (`?thumbs=0`) 3,361 ms / 1.7 MB |
| review item 1 / 2 / 3 | 382 / 872 / 704 ms | 153 / 222 / 372 ms |
| review item channels | 416 ms | 126 ms |
| review queues list / counts | 1,107 / 1,152 ms | 1,425 / 1,944 ms (first read builds the structure) |
| discovery runs | 834 ms | 635 ms |
| discovery templates (picker) | > 240 s while scoring | 528 ms |
| discovery fires (3 ch x 53 runs) | 16,632 ms | 1,808 ms |
| discovery scoreboard (10 runs, 3 ch) | 85,486 ms | 11,895 ms |
| discovery map L3 / L2 (untouched) | 7,602 / 3,010 ms | 9,198 / 3,603 ms |
| corpus coverage M2_aug (warm) | 555 ms | 925 ms |

Units on the same bridge: `review` 3 failures = the morning baseline's three; `zzzzzzzzzzz_ar_speed` 1 failure = the
first-paint state's fixed 150 ms wait (the Discovery chunk is lazy-loaded; state fixed the same night to wait for the
toolbar); `discovery` 34 failures = **a `--pages-only` artifact, not a regression**: the discovery states name the two
smoke runs the CORE FLOWS create (`smoke.py:1395`), and `--pages-only` skips the flows, so every state after
`runs--running` fails with "the state names a smoke run the walk could not find". The discovery unit can only be judged
in a walk that runs the flows (a full walk, or `--only discovery` without `--pages-only`).

## changes/integration (de3f472) — gate result 2026-10-19 03:25–04:40, merge ABORTED, for the Prompt manager session

Eight prompts (span-plot, explore-review, ig-pages, sequences, datasets, edit-span, site-fixes, review-carry) on top
of AR. Tests, tsc and build were green on the merged tree (conda 356, venv 253 + 3 xpassed). The flows passed once the
walker followed the new defaults (committed on main after 1ba7fef: runs hidden until chosen → the signal flow switches
them on through `detection-runs-chip` → `picker-all`; carried verdict rows accepted; an honest "Send 0 unjudged"
accepted; the routes prelude starts from `#/jobs`; `Refreshing` takes a `testid`). The FULL page walk is not clean:
**735 screenshots, 91 failures, 61 not in the 18 Oct baseline** — Analyse block pages (`fixup-h-*` block views
missing; every `ig-pages-*` state 60 s timeout), Analyse chain (insert-modal clicks timing out), the interrogation
slope page (`slope--default` missing anatomy-card / rose / per-event-table: the fold moved them, the old states were not
updated), Explore (`signal--default`, `--live-channel`, `--motif` missing `signal-overview`; four cross-channel states
missing `scale-note` / `cross-axis`), Library (`sequence-family-renders` expects the placeholder;
`sequences-keep-then-the-family-page-draws` 120 s), review-carry's and edit-span's own states timing out,
`ar-templates-open-under-a-second`, a2_p2 / a2_p3 states, `settings.datasets--discovery-scope-names-its-dataset`.
Full log kept by the WEBSITE CHANGES session (`smoke_full_integration4_keep.log`); the merge was aborted, main is
untouched by the branch.

**Caveat:** that walk took 75 min on a quiet box (norm 40), so part of the 61 may be the merged tree's own load (the AR
background scorer, the flows' runs). A full walk of MAIN alone (AR + the walker fixes) is running as the new baseline;
the diff of the integration walk against it — the branch's OWN regressions — will be appended below. Fix on the
branch after merging main into it (fd8cdfa and the walker commit are needed under it), prompt by prompt, and re-gate
with a full walk, not units: the discovery states need the flows' smoke runs.

**Product defect found by the walker, for the speed second pass:** after any run finishes, the home page's corpus map
recomputes (~100 s on the post-RQ4 database) and the heatmap does not paint for minutes; serve the last map at once
and recompute behind it (the pattern AR gave the picker).

### 2026-10-19 morning — what the full walks on MAIN found, and the new baseline

Main alone (AR + the walker fixes), full walk 04:44–05:43: **720 screenshots, 77 failures, 52 not in the 18 Oct
baseline** — so most of what the integration walk showed was already on main. Units re-run on a quiet fresh bridge
(no flows) reproduced the failures: deterministic, not interference. Two causes, both fixed as `9ac3d27`:
1. **AR's background template scorer** scored 73 templates back to back (3-4 min at every start and after every run the
   flows wrote) and held the interpreter; every page read under it stalled, and states with 2-3 s settles failed
   across Explore, Settings, Analyse and interrogation. It now waits for a quiet gap before each template (1.5 s, at
   most 6 s). Test: one quiet-wait per template.
2. **ux-1018's templates accordion** hid encoding / training / interrogation templates until their group was opened,
   so the ten smoke states that import one by clicking its row timed out and every block state behind them cascaded.
   The header click is idempotent now and those ten states open the group first.
After the fixes, quiet units: interrogation 0 (was 5), zz_analyse_run 0 (was 15), analyse 0, explore 8 (was 12),
settings 7. Main full walk 06:33–07:30 with the fixes: **728 screenshots, 61 failures, 33 not in the 18 Oct
baseline, 17 of the baseline's now pass.** Of the 33: five are **data drift** (the held-out lock is OFF in the real
database now — `explore.*--held-out`, `settings.*-locked` expect it locked; `settings.datasets--identity-fields`
expects a dataset that has since been named); two are `requestfailed` on the corpus-map read that outlived AR's
300 s read timeout from an earlier state (the home-page defect below) and were charged to whatever state was open;
the rest are **timing on a bridge still running the flows' jobs** (seed searches and chain runs now take minutes on
this database) — the interrogation and explore states among them passed in the quiet unit runs. The walker now waits
for the jobs to go idle (cap 5 min) before the page walk; the next full walk is the baseline to compare against.
Files: `scratchpad/smoke_full_main2.log`, failure set `base_main_0419b.txt` (WEBSITE CHANGES session).

**For the Prompt manager session, `changes/integration`:** merge main (≥ 9ac3d27) into the branch first — the
accordion and scorer fixes remove most of what its walk showed. Its own regressions, from the diff of its walk
against the fixed main (to be re-confirmed on a re-walk after the merge): the seven `analyse.block--ig-pages-*`
states (60 s timeouts) and `analyse.chain--ig-pages-event-trains-chain-runs`; `analyse.interrogation.slope--event-
picked`, `--fixup-k-padding-is-honoured`, `--not-recovered-is-not-zero`, `aggregate--feature-wiring` (the fold moved
what the old states expect); the Compare page (`compare--default` 30 s timeout, `--empty-one-pick`,
`--filter-only-b`, `--popover-roles`, `--remove-and-pick-apart`, `--swapped`, `fixup-z-band-set-as-side-b`) and
`runs--modal-slurm` — review-carry/explore-review changed what Compare reads; `explore.span-edit--…` (edit-span's own
state, 30 s); `library.family--sequence-family-renders` (expects the placeholder the prompt replaced — update the
state) and `--sequences-keep-then-the-family-page-draws` (120 s); `library.grouping--fixup-an-a-grouping-made-before-
trees-says-so`. The `fixup-h` block/chain states in that diff are the accordion (fixed on main), not the branch.

**Product defects for the speed second pass (BACKLOG):** (a) the home page's corpus map recomputes ~100 s after any
run finishes and the heatmap does not paint until it is done — serve the last map, recompute behind it; (b) the
300 s read timeout turns that into `requestfailed` console errors charged to unrelated pages. **Smoke debt:** the
held-out states must set the lock they assume (a `PUT` in their actions) instead of assuming the database's state.

**Baseline walk with the jobs-idle prelude (07:35–08:31): 728 screenshots, 65 failures, 35 not in the 18 Oct
baseline** (`base_main_0419c.txt`). The idle wait was 0.1 s — the flows' jobs were already done, so job-manager jobs
are not the interference. What distinguishes the full walk (fails) from the quiet unit runs (pass) is the corpus map:
the flows write runs, the next corpus read recomputes the map for ~100 s and holds the interpreter, and the states
visited in that window (interrogation aggregate/slope defaults, Explore signal and cross-channel, Library family,
Models launch clicks) time out. **First item of the speed second pass:** the corpus map must not recompute inside a
request — serve the last map (memory or disk, stale flagged), recompute behind it, and move the compute off the
interpreter (a worker process, or make `channel_divergence` incremental per run). Until then the full walk's baseline
on this database is ~65 failures and its comparison must be by SET against `base_main_0419c.txt`, not the 18 Oct 42.
Five of the 35 are held-out-lock drift; `discovery.seed--source-explore`, `library.templates--model-stage`, the two
a2_p2 states and `settings.datasets--discovery-scope-names…` are data/state drift to re-check by hand.

**Daily full pytest, 2026-10-19 08:48–09:36 (`pytest -n 4`, main at d679d1a): 4,666 passed, 51 skipped, 1 failed** —
`test_webui_seed_on_demand_client::test_the_smoke_walk_checks_the_seed_page_runs_nothing_on_its_own`: AR's smoke unit
`zzzzzzzzzzz_ar_speed.json` opens a Discovery page and sorted AFTER `zzzzzzzzzzz_a2_p4_seed.json`, which changes the
Discovery session and must walk after every other Discovery-opening manifest. Renamed to `zzzzzzzzzzz_a1_ar_speed.json`.
Rule for new units: a manifest that opens any `discovery/` page must sort before `zzzzzzzzzzz_a2_p4_seed.json`
(and `zzzzzzzzzzz_w3_cancel.json` stays last). The previous full run's one failure (`test_surrogate_never_a_detection`)
now passes.

## corpus-map-off-the-request — merged 2026-10-19 (speed second pass, item 1)

Branch `worktree-agent-a72dabecf5787addb` (prompt `docs/prompts/changes/corpus-map-off-the-request.md`, report
`docs/prompts/changes/reports/corpus-map-report.md`). A corpus-map read never computes: fresh / last map with
`stale: true` / `pending: true`; the recompute runs in one spawned worker process (`Working/discovery/coverage_map.py`),
byte-identical to the old `_coverage` (sha1-pinned against base 60d8c09, 3 fixtures, 21 questions). Critic: no
blockers, five should-fixes (orphaned worker, silent freeze on BaseException, red card beside the stale line, the
smoke state, map stored under the asking state) closed in fb8c655. Branch trailers say Opus 5.5 (the implementer's
model); the merge commit carries the repo's line.
Gate: conda 142 passed (coverage_map_compute, perf_scoring_reads, divergence, surrogate, windowed_explore,
seed_on_demand_client, import boundaries); venv 103 passed (webui_ar_speed, webui_corpus, coverage_map_compute,
webui_discovery); tsc; build; the `zzzzzzzzzzz_corpus_map` state on the real-database sandbox: PASS (stale line at
once, gone after 164 s and 177 s — two recomputes of 170–181 s each in the worker, under another session's units;
0 console errors, 0 tracebacks). Bridge start: "17 files, 16 current, 1 scheduled on the worker" — a restart no
longer blocks on the map. **Owed, after the other session's full walk ends (~15:30): the `explore` unit and the
daily full walk on this tree as the new baseline** (sealed before them because the other session's bridge keeps
paying the 5 min cold warm this removes).

### 2026-10-19 afternoon — baseline on main with corpus-map, and the first gate of the whole wave

- **Explore unit on main 43ee443 (13:57, quiet):** 54 screenshots, 9 failures — the three held-out-lock drift states,
  `signal--default` (span card not painted at 2.5 s — the Signal page's first paint is 3–5 s on this database:
  89,626 detections on CH4_A2 drawn in the overview; a speed-pass item), `signal--live-channel` (ribbons), four
  cross-channel states (`as-recorded`, `lag-aligned`, `max-lag-10` data drift, `y-absolute`).
- **Full walk on main 43ee443 (14:00–15:34): 714 screenshots, 79 failures** (`base_main_0419d.txt`). NOT clean: the
  other session's 39-min venv pytest and a build ran under its first half; 27 states not in the morning's set, click
  and wait timeouts in Discovery, Library and Settings; 13 of the morning's failures passed. Rule agreed both ways
  afterwards: nothing heavy on the box from either session during a full walk — no pytest, no build, no agents.
- **Wave gate, `changes/integration` 8b569cf** (all thirteen prompts + site-fixes + the "for drops" follow-up, each
  critic-reviewed, containing main 43ee443; the other session's combined gate: conda 763 passed, venv 405 + 3 xpassed,
  tsc, build). Merged unsealed, tsc clean, build, **full walk 15:38–16:54: 783 screenshots, 60 failures** — fewer than
  both baselines, every new state of the wave passing. Not sealed: 16 states fail in the wave walk and in neither
  baseline. `smoke-result.json` holds 23 browser errors with `net::ERR_NETWORK_CHANGED` and `requestfailed` on review,
  scoreboard, history, templates and seed reads — the box's network changed during the walk, which explains the review
  flow writing no verdict row (`[]`) and the discovery flow's timeout, and probably the consecutive Analyse chain demo
  states (`live`, `1-chain`, `1b-run-history`, `1c-*`). To triage on the branch: Library recurrence (four states) and
  the family grouping-url link; `settings.models-registration--default`; two `aq_cross_channel` states (bin-rule
  testid; `nothing-to-align` where shifted rows were expected); `discovery.seed--view-popover` (the old popover the
  strip replaced). Merge aborted; list sent to the other session; it re-walks the pages with units, fixes, and I
  re-walk in full before sealing. The warm now reports 20 files: the 2 Hz CO/LM registrations landed in the real
  database today (another agent, the researcher's note) — the datasets-derive run skips CO and LM.

**Data drift marker (from the other session's read-only query):** `LM_fs2.mat` (recordings rows 637–640) and
`CO_fs2.mat` (from row 641) were registered in the real database at 14:12 local on 2026-10-19 (the 2 Hz work); the
database now has 21 source files. The 14:00 baseline bridge copied the database before them; the 15:38 wave-gate
walk was the first sandbox carrying them, so Datasets/Settings states drift from that walk on; 8765 serves them live.
Datasets dry runs (same session, read-only): MJu26a → 22,892,769 samples at 10 Hz by linear interpolation (`t` in
seconds, span 635.9 h, dt 0.124/0.138/2.83 s); the **L_LM parent link was REFUSED** — the expected channels (MJu
10, 13, 14, 15, 16 one-based) sit at offset ≈ 0 but r per window is 0.96/0.77/0.94, 0.97/0.99/0.85, 0.43/0.18/0.38,
0.73/0.79/0.99, 0.70/0.63/0.51 — L_LM is not a plain ×1000 resample; question Q47 to the researcher. SH/SO at
17,280,001 × 4 and F2B at 5,184,001 × 5 infer 10 Hz from the sample count (V, V, mV); L_R_Aug_26_PD_raw refused
(3,851,550 samples, no round rate; the time axis is a MATLAB `duration` object) — question Q48. CO and LM skipped.

**Wave re-gate, `changes/integration` ddac35f (17:43–18:56, box idle, no network errors): 790 screenshots, 38
failures** (`wave2_fails.txt`) — against the morning baseline 7 not in it and 32 of its failures passing; against the
afternoon baseline 3 not in it and 42 passing; against the wave's own first walk 5 new and 25 fixed. Strictly new
against all three: `explore.signal--fixup-y-take-span-is-a-seed` (no `seed-option-explore:` in the seed picker after a
span is taken in Explore), `review.inspector--fixup-y-seed-names-the-entry` (no promotion panel naming the seed) — one
path, the Explore seed → Discovery seed picker → Review promotion, plausibly explore-review's queue/source change —
and `library.atlas--fixup-ae-floor-on-by-default` (0 traces measured, hidden-count missing). `a2-p3 window card` and
`a2-p4 restore` fail in earlier walks too. Merge aborted; the three states sent to the other session for a branch fix;
re-gate with the `seed_sources`, `zzzz_ae_library_view`, `explore` and `review` units instead of a fourth full walk,
unless the fix touches shared code.

## The 2026-10-18 wave — merged 2026-10-19 21:1x (changes/integration 5d02ab4)

Thirteen prompts + site-fixes + the "for drops" switch, each critic-reviewed with one fix round by the Prompt manager
session; its combined gate on 8b569cf: conda 763 passed, venv 405 + 3 xpassed, tsc, build. Here: tsc and build on the
merged tree; full walks 16:54 (783 / 60, a VPN network change mid-walk) and 18:56 (790 / 38, idle box, 0 network
errors) against main's baselines of 62 and 76 — fewer failures than main, every new state passing; the three states
strictly new against every walk (`explore.signal--fixup-y-take-span-is-a-seed`, `review.inspector--fixup-y-seed-names-
the-entry`, `library.atlas--fixup-ae-floor-on-by-default`) were fixed sleeps acting before paint and now wait for what
they act on (5d02ab4, states only; the same code passed them in the 16:54 walk). **Pages-only units cannot judge
`seed_sources` or `zzzz_ae_library_view` on a fresh sandbox:** for ~10 min after a bridge start the Discovery seed page
re-reads the templates list while the background scorer works (73 templates, yielding), so it never reaches
network-idle even at 90 s; the atlas unit's `[grouping g-05]` states need groupings earlier library states create; the
one console error seen there followed an aborted navigation. Three attempts (20:04 under another session's pytest,
20:20 and 20:49 quiet) failed the same way; both full walks passed those states. Walker: every network-idle `goto`
now has a 90 s budget (the per-state one at `smoke.py:1467` was the 30 s that bit). **Owed: tomorrow morning's daily
full walk on the sealed main (VPN off), compared by set against `wave2_fails.txt` (38) — the first clean post-wave
baseline.** Pre-existing, filed: the atlas page reads `/api/library/groupings` every 2 s on main too.

## Night of 2026-10-19 → 20 — the break-it pass and the morning walk's base

**Three night agents** (brief `docs/prompts/changes/night-pass-2026-10-19.md`, base 7d2d695, ports 8767/8768/8769,
each on its own fixture database): A Review+Discovery, B Explore+Library+Analyse, C polish and load site-wide.
By 00:17 A had 5 commits (scoreboard reads each run and each channel's human rows once; a finished queue says
"done"), B 18 (the atlas `groupings` read ten-fold → once per open; the Signal page's span list read once; block-page
folds per page; interval tables print integers; the Library crumb; Interrogation's Open in Library), C 6 (the header's
titles never wrap or shift; the kit barrel no longer ships the showcase; body min-width 1024). Reports owed in
`docs/prompts/changes/reports/night-<letter>-report.md`; gates per branch as they hand back.

**The researcher's 8765 died at about 22:47 with no traceback** (their own start of ~22:43). The HPC session
restarted it detached at 22:48 with `PYTHONFAULTHANDLER=1` (logs `webui/runtime/bridge-8765-20261019-224827.*.log`,
parent PID 74944); it runs 0ffadd5's code until the morning restart.

**The database is final for the walk at 00:09** (HPC session): batch 3 adopted, 129 jobs, none failed or refused,
sessions 3 (LM_fs2_rq4), 4 (CO_fs2_rq4) and 5 (L_LM_Jul_26_J_raw_fs2_rq4) with 46 runs each; Discovery back on session
2 (M2_aug, 52 runs, highest openSeq, so the walk opens there as before). DB 342 → 511 MB; step cache 9.2 GB. Main
4d3a4d8 (2ed3f49: many legacy-detection refusals are one warning line, schema.py + its test; then docs/HPC lists).
**Speed, filed:** `GET /api/discovery/map` (the Map overview) takes 11–15 s on every call on the live bridge, the same
on the pre-import backup (14.3 / 10.8 s) as after (14.6 / 11.9 s) — not the import; the detection map levels 2/3
recompute per read (BACKLOG speed row). The other pages returned 200 in 0.3–4 s, no tracebacks.

Morning: full walk at ~05:53 on a fresh sandbox copy of this database, compared by set with `wave2_fails.txt` (38);
then one restart of 8765 (the HPC session needs nothing from the 22:48 process).

**Night C merged 00:4x as 293a8fc** (polish and load, site-wide; report `docs/prompts/changes/reports/night-c-report.md`).
Gate on the merged tree: `tests/test_night_c_shell.py` + import boundaries (conda, 17 passed), tsc, build (entry
chunk 472.7 → 441.9 kB); units `review` (24 shots / 3 fails), `explore` (45 / 8), `analyse` (47 / 0), `jobs` (15 / 0),
`zzzzzzzzzzz_polish` (13 / 0) on a fresh 8766 sandbox of the final database (bridge started 00:34, warm 25 files,
22 current, 3 scheduled on the worker). Every failure is in `wave2_fails.txt` except `explore.corpus--held-out`,
`explore.signal--held-out` and `explore.cross-channel--held-out`, all "missing locked-card": `GET /api/held-out` on
the sandbox copy says `locked: false, on: false` (M4_aug_concat_fs1) — the held-out lock is OFF in the final database,
so no locked card can render; a data drift, not the shell (CSS and a shared header read cannot remove a data-driven
card). **Expect the same three in the morning walk and read them as drift.** C's three worst unfixed things, filed
and forwarded to A and B (their files): the Review queue open sends all rows (7.0 MB at 9,743; 7–17 s to the first
candidate); Explore › Signal awaits the whole channel's spans (526 kB, 153 s on a loaded bridge) before tier 2 and
`GET /api/channels/{id}` recomputes its ribbons every call (4.6 s in process); Discovery's run rows squash to 18 px
with 60 runs (`.dsc-run { flex: none; }`). The need-you chip is now at most 15 s stale between pages (assumed).

**Night B merged 01:2x as d1bf8e4** (Explore, Library, Analyse; report `docs/prompts/changes/reports/night-b-report.md`;
critic round f5a6736/5ff3f3c: a re-read after a span write no longer joins the earlier shared read, Interrogation's
"no family" card waits for its read to settle, ?template=<name> is an exact match first). Gate on the merged tree:
conda `test_serialize_interval_classes` + `test_webui_night_b_critic` + import boundaries (23 passed); venv the six
`test_webui_night_b_*`, `test_webui_library`, `test_webui_library_family_actions`, `test_library_background_null`
(135 + 3 xpassed on the first tip, 36 on the critic tip); tsc; build; fifteen units on a fresh 8766 sandbox of the
final database (01:00–01:23): `explore` 45 shots / 4 fails, `library` 61 / 4, `library_edges` 2 / 1, and
`library_grouping_url` 6, `analyse` 47, `interrogation` 58, `span_plot` 6, `aq_cross_channel` 12, `overlay` 5,
`sequences` 4, `family_actions` 7, `ig_pages` 14, `an_library_tree` 6, `explore_review` 5, `zzzz_ae_library_view`
12 — **all 0 fails**. Failures: the held-out drift (`explore.corpus/signal/cross-channel--held-out`,
`library.recurrence--held-out-recording`: the lock is off in the final database); two baseline states
(`explore.cross-channel--as-recorded`, `library.templates--model-stage`); and one strictly new one,
`discovery.seed--fixup-v-scale-bank-searches-every-length`: the scale-bank preview on seed entry 697 ran 01:05:46 →
01:13:11 (445 s, a 96-step sweep job, completed) against the state's 240 s wait — the final database (25 files, the
10 Hz multi-day recordings among them) makes the bank search slower; B's code is nowhere near the seed search. The
re-run in `library_edges` failed at its first wait because that sweep was still running. **Expect it in the morning
walk; it is a seed-search speed item (the researcher's redesign wanted a time estimate on exactly this) and the
state's budget.** Improvement: `explore.signal--default`, `explore.signal--live-channel`,
`explore.cross-channel--lag-aligned` and `--y-absolute` failed in C's run (and in the 18:56 baseline) and pass after
B's one-read-per-open change. Critic on A: merge after three fixes (Ctrl-Z during an in-flight write undoes the
previous item; a session-only class key on a seed-prior row counts it judged; a late flash on the next item) — sent
back 01:20.

**Night A merged 02:0x as e668995** (Review and Discovery; report `docs/prompts/changes/reports/night-a-report.md`;
critic round c8fece9/60944b2: undo and redo refuse while a write is in flight, a prior verdict is shown but never
counted as judged, the flash stays on its item). Gate on the merged tree: conda `test_night_a_review` + import
boundaries (19 passed); venv `test_webui_night_a`, `test_webui_review`, `test_webui_discovery`,
`test_webui_discovery_runlist`, `test_webui_ar_speed`, `test_perf_scoring_reads` (207 passed); tsc; build; eighteen
units on a fresh 8766 of the final database (01:33–01:54, after `template scores warmed` 32.6 s): `review` 24 shots
/ 3 fails (all baseline), and `ah_blind_test` 6, `review_carry` 3, `edit_span` 3, `a1_ar_speed` 3,
`a1_polish_discovery` 2, `a2_p3_windows` 7, `zz_analyse_run_ac` 3, `zzz_surrogates` 5, `polish` 13 — all 0 fails;
`a2_p4_seed`, `a2_p2_hpc`, `zzz_x_divergence` one baseline fail each. Strictly new, each explained: the four
"names a smoke run the walk could not find" states (`ux1015_zal_send_one` ×3, `band_scope`) are the pages-only
cascade (the flows create those runs); `discovery.seed--seed-search-after-the-preview-the-cut-card-is-open`
(240 s wait) is the sweep budget again (01:38:53 → 01:43:24, 96 steps, then a 3,216-step cut sweep 01:44:10 →
01:49:12); `discovery.runs--coverage-strip-on-every-run-row` (goto 90 s) **passes on the warm bridge** (cold
timing; `/api/discovery/runs` 0.37 s warm, the map 3.3 s); `library.family--fixup-ad-classify-against-chance`
ran while that cut sweep was still going and on the re-run had classified (`data-classified="yes"`) — the send
button was disabled because the first run had already sent the queue (used sandbox).

**A real defect found by those units, fixed on main (872ac75 red, then the fix): the seed page's cut card threw
`RangeError: Maximum call stack size exceeded` inside the Discovery workspace** (`discovery.seed--fixup-ad-
exclusion-zone-settable`, deterministic on the final database). Source-mapped to `SeedPage.tsx:576`:
`Math.max(0, ...candidates, ...nullDistances)` — a 3,216-step cut sweep holds ~10^5 distances and spreading them
into an argument list overflows the stack. `kit/extent.ts` (a loop; non-finite skipped) now serves the page's six
spread sites; `tests/test_seed_page_extent.py` runs it under Node over 300,000 values and forbids a spread on the
page. The wave's seed-search code, not the night agents' (A touched no seed file). About sixty other
`Math.max(...xs)` sites remain in the client on bins, counts and per-channel lists (grep in the commit message) —
a day item, the Discovery and Explore ones first. Browser console errors elsewhere tonight: two
`net::ERR_INTERNET_DISCONNECTED` during B's `library` unit (a network blip, not code).
Re-run of `zzzz_ad_suspected_artifact` and `zzzzzzzzzzz_a1_seed_search` on a fresh 8766 with the fix (02:04–02:12):
**0 browser console errors** in both; the exclusion-zone state passes; `seed-search-the-strip-shows-four-steps` hit
the 90 s goto budget inside the post-start window (the seed page re-reads the templates while the scorer warms —
the known `seed_sources` class); `library.family--fixup-ad-classify-against-chance` failed again on the fresh copy
although its `cross_channel` job completed in 5.5 s (02:06:19 → 02:06:24, 10 pairs across 8 channels, 55 members):
the state paused a fixed 1.5 s after the flag line. **f21001b (states only): it waits for `data-classified="yes"`.**
Main for the morning walk: f21001b (C 293a8fc, B d1bf8e4, A e668995, the extent fix 8dff9b0, this state).
`zzzz_ad_suspected_artifact` with f21001b on a fresh 8766 (02:14–02:15): 7 screenshots, **0 failures**, 0 console
errors. Box quiet from 02:16; the 8766 sandbox stopped; the full walk starts at ~05:53 on a fresh copy.
