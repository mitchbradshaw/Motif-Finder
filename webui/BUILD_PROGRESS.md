# BUILD_PROGRESS.md — resume point for the overnight build

Read this first on resume; continue from "Next action". Do not restart finished steps.
Scratchpad (session): `C:/Users/mmebr/AppData/Local/Temp/claude/C--Users-mmebr-Documents-CNN/08616d91-3198-4e54-a453-92e3fff331d1/scratchpad/`
(BRIEF.md = the overnight brief; DATA_MTIMES_START.txt = the start snapshot; issues.md = map + child issue bodies).

- **Session start:** 2026-09-15 23:50 +10:00. annotations.sqlite mtime 1789297374 (2026-09-13 11:02:54 UTC), size 4349952.
- **Servers I started:** bridge `webui/run_server.py --port 8765` (bg task), Vite dev `npx vite` on 5173 (bg task). Stop both before finishing.
- **Temp worktree:** `C:/Users/mmebr/Documents/CNN-pytest` (detached, real copied DATA subset ~1.25 GB) — reuse for the final pytest, then `git worktree remove --force` it (may be blocked by the classifier; then leave + log).
- **Old worktree** `CNN-ui-proto`: junction removed; `git worktree remove --force` blocked by classifier → left for the user (DECISIONS 1.7).

## Task 1
| step | status | commit |
|---|---|---|
| 1a merge ff | done | e81b486 |
| 1b promote A → webui, archive README, delete brief | done | f0c8f13 |
| 1c old tree: not trivial, UI/ kept; CLAUDE.md | done | ca9e30d |
| 1d pytest (39 pre-existing failures) + smoke green; junction removed; push #1 | done (worktree removal blocked) | pushed ca9e30d |
| 1e ADR 0001 + tracker: #12 #14 #15 #13 #10 #11 commented+closed; map #4 body edited, commented, closed | done | |
| 1f docs/wayfinder/fog-of-war.md (115 items) | done | c0ed7f5 pushed |

Tracker plan once fog file is committed + pushed (push #2): comment+close Select-the-stack (#12, link ADR + REPORT),
where-tree-lives (#14), test gates (#15), frontend↔core (#13, resolved part + carry-forward §Core seam), signal
reduction (#10) and UI_CONTEXT corrections (#11) ("carried forward to docs/wayfinder/fog-of-war.md §…"), then map #4:
append Decisions-so-far lines (name-linked), replace "Not yet specified" with pointer, closing comment, close.
gh = "/c/Program Files/GitHub CLI/gh.exe" (authenticated as mitchbradshaw). Refer to tickets by name.

## Task 2
**05:05 session restart**: the previous session died ~00:30 (≈4.5 h lost); kit agent, inventory workflow and both
servers were stopped. Restarted bridge (8765, bg task b4a771xfl) and Vite (5173, bg bq1b5jetv). Kit agent resumed via
SendMessage (id af963bf1d4fd434ea). Inventory: explore complete; discovery complete; library/review/models/settings
partial; interrogation-training conventions only; chain empty → builders finish their own group's inventory first.

| step | status |
|---|---|
| foundations (me) | done e2a7940 |
| inventory (7 groups) | partial, committed e2a7940; builders complete their own |
| kit agent → src/kit/** + #/kit gallery | done 3667ed0 |
| skeleton: 49 routes, lazy workspaces, smoke walks smoke_pages/*.json (49 states, 0 failures) | done e2a7940 |
| PAGES.md assembled | todo (after depth) |
| depth workflow wf_91ff8a51-7e6 (task wb058misp): 10 units, ≤4 builders, 2 critics per sub-unit, ≤2 fix rounds | RUNNING since ~05:45 — on crash resume with Workflow({scriptPath: <session>/workflows/scripts/webui-pages-depth-wf_91ff8a51-7e6.js, resumeFromRunId: "wf_91ff8a51-7e6"}) |
| final pass | todo |

### Depth plan (decided)
Units in order: explore, analyse(chain+blocks+glyphs), review, library, discovery, models, jobs, interrogation,
training, settings. Builders own src/<unit>/, src/api/<unit>.ts, src/fixtures/<unit>.ts, webui/smoke_pages/<unit>.json,
webui/pages/{status,fog,requests}/<unit>.md. Critics: fidelity + function per sub-unit → webui/critique/<sub>/r<N>-<lens>.json,
screenshots webui/screenshots/critique/<sub>/r<N>-<lens>/. Page score = min; accept ≥8; ≤2 re-ratings.

## Next action
Depth workflow running. Poll webui/pages/requests/*.md and status/*.md; apply shared-file requests serially; check servers alive. When it finishes: PAGES.md + PAGES_REPORT.md from hist + critique JSON, merge pages/fog/*.md into fog-of-war.md, final pass.

### Shared-file requests log
- 06:2x review.md: applied canon seed colour green, F-11 = 17 members, review-7 → review.cluster (6681ae3; my sed broke canon.ts syntax for ~2 min, fixed 18c61b9 — use Edit + tsc for shared files).
- QUEUED for after builders (additive kit props, workarounds exist): Trace tickDigits/tickFormat; Trace unit label vs bottom tick with timeUnit="none"; Trace bands[].edges + label lane; Popover header actions slot; RangeSlider disabledReason; canon REVIEW_QUEUES totals/judged + q-16 Explore spans queue.
- 06:3x analyse.md: added cross-workspace demo-write contract to kit/README.md (unstarted builders read it); QUEUED: Popover width beyond 560 px, Modal footerStart slot.
- 06:4x explore.md: applied Header demo tooltip copy. QUEUED: charts/useSize callback ref; IconButton forwardRef; controlled InfoTip; MultiPick; Seg role=button mode; Table pageSize sort-then-page + cross-page select-all; Breadcrumb item testids; canon q-16 Explore spans queue (coordinate with Review fixture).
- 06:5x library.md: applied disabled danger button CSS. QUEUED: Histogram log x + bin edges; useForcedSim/deep-link reset key; rail button font; createReviewQueue in api/review.ts (Review-owned).
- 06:5x analyse.md + explore.md: fixed charts/useSize re-bind (blank-pane trap).
- 07:0x discovery.md: QUEUED: Button disabledReason warning inside DisabledReason; Table expandable child rows; Histogram draggable threshold + background null series. Glyph gaps = Analyse builder's 6b task (then kit/glyphs aliases resolve).

### 07:15 usage limit → 11:10 resume
The account's session limit stopped 59 agents (reset 10am). Survived: explore, analyse, review, library built and
committed; discovery.runs and models.launch built; jobs inventory written; settings/interrogation/training not started;
critics r1 completed only for review (and partial JSON for explore/chain/library). Both servers stayed up.
Resumed the SAME run (wf_91ff8a51-7e6, task wsro31ury) from the copied script
scratchpad/depth.js with resumeFromRunId, so finished builds replay from cache; a RESUME paragraph was added ONLY to the
six unfinished units (so the finished units' prompts stay byte-identical and keep their cache). Critic pool 8 → 5.
Re-resume the same way if the limit hits again.
- 11:3x models.md: added smoke allow_console_error.
- 11:4x jobs.md: applied CanonJob submitted/cancelled + j-0209 title. QUEUED: Table collapsible-group deep link; Stepper 'cached' state; Modal subtitleBelow; ProgressBar percent suffix; canon queue counts/pace/eta; demoNeedYou helper.
- 12:0x interrogation.md: applied ANALYSE_RUNS #140 template rename. QUEUED: LineChart bands + x clipping; Rose/polar plot; variable-height event rail; Histogram overlay opacity + stacked mode; DisabledReason asChild; Slider changed tone; canon family extras + shared FamilyMember type; Header state chip slot.
- 12:4x discovery.md (2nd): applied StatTile string-info fix. QUEUED: multi-track Trace with one crosshair; Bars stacked-proportional with in-bar clickable segments; Pager keyboard stepping; Button warning inside DisabledReason.

### 13:00 second usage limit → 16:20 resume
Limit hit again (reset 4pm). Built and committed by then: explore, analyse, review, library, discovery, models, jobs,
interrogation (8 of 10 units). Settings and Training never started. Rated so far (r1): explore 9/9/8/9, analyse.chain 8,
analyse.block 8, analyse.glyphs 8, review.inspector 9, review.cluster 8 — all ≥ 8 except unrated ones.
Now running a build-only workflow for settings + training (run wf_14dda958-dd7, task w98kbae15), then a critique-only
workflow for the unrated units, then the final pass. Both servers still up.

### 2026-09-20 weekly limit (Sep 20, 6pm Brisbane) -> resume
The weekly limit killed all 38 critics of wf_d9eb5e5f-315 and the Settings builder's last phase; 14 orphaned
shell tasks (incl. both servers) were marked stopped by the harness. On resume: restarted bridge 8765 (bg task
b2bowbvyt) and Vite 5173 (bg task b4ohd6pyj) - stop both before finishing. tsc clean. Settings builder's
uncommitted diff (deep-linkable search/reset, keyboard conflict derivation, manifest selector fixes) verified by
the settings smoke and committed with two orchestrator fixes in src/settings/: the import-recording timer kept
running after its modal closed and navigated to M5_sep from under the unlock modal (race); the Nulls alpha check
counted the full-model null (5 retrains, no p) so Save was always disabled (NullKind.p_value). Discard smoke state
moved to analysis-defaults (same-URL goto does not remount, so save then discard on one hash cannot both pass).
Critique round 2: workflow wf_7c08bb14-c18 (task wxbg465dd) from scratchpad/critique2.js - 10 sub-units, both
lenses (training fidelity re-run because its r1 file had score 8 with zero findings), sem 5, per-unit lock on
fix builders, up to two re-ratings. Resume: Workflow({scriptPath: scratchpad/critique2.js, resumeFromRunId:
"wf_7c08bb14-c18"}). Fog merge delegated to a subagent editing only docs/wayfinder/fog-of-war.md (F19+).
Committed r1 critique JSON for explore/chain/blocks/review-fidelity (a860984).
Then: commit critique/, make_reports.py, DECISIONS 2.8+, full smoke (5173 pages + 8765 flows), npm run build,
DATA mtime check vs scratchpad/DATA_MTIMES_START.txt, stop servers, push, final report.
