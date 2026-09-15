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
