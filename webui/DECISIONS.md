# webui/DECISIONS.md — decisions from the overnight build (2026-09-15 → 16)

Every non-trivial call made while landing prototype A as `webui/` (Task 1) and building every concept page as
a working, empty shell (Task 2). Newest at the bottom of each part. The prototype night's own log is
`ui-prototypes/DECISIONS.md`.

## Part 1 — landing A, retiring the old tree, closing the map

### 1.1 Fast-forward merge
`main` had not moved since `proto/ui-stack-slices` was cut (merge base = `main` = `208e72c`), so
`git merge --ff-only` succeeded and no merge commit or conflict resolution was needed.

### 1.2 A's screenshots stay in the archive, not in `webui/`
The brief's default was `git mv ui-prototypes/A-react-fastapi webui`, but it also said the screenshots stay in
`ui-prototypes/` as evidence. Moving the whole directory would have carried A's night-of screenshots into
`webui/` and broken every path in REPORT.md §6. I moved the directory and then moved `screenshots/` back to
`ui-prototypes/A-react-fastapi/screenshots/`, so the archive's references resolve and `webui/screenshots/`
holds only the product's own smoke output.

### 1.3 Path fixes, and one addition
`runtime.py` now takes the repo root as the parent of `webui/` (`WEBUI_DIR`; `PROTO_DIR` kept as an alias so
`app.py` did not need a second edit). Environment variables became `WEBUI_PORT` / `WEBUI_URL`. Titles and log
names lost "prototype A". I added one behaviour: `run_server.py` refuses to start on a busy port with a clear
message, because REPORT §8 found stale prototype servers silently occupying 8765/8766 and recommended exactly
this. `.gitignore` rules moved into `webui/.gitignore` (node_modules, .venv, dist, runtime, logs, *.big.png);
`ui-prototypes/.gitignore` is left for B. Smoke passed on the first run in the main checkout (19 screenshots,
0 failures).

### 1.4 The old Panel tree `UI/` stays (deletion is not trivial)
Assessed in ~10 minutes against the brief's two conditions. **Condition 1 fails:**
`Working/Detection/sax/dsax_python/UI_snapshot_20260810-0512/{app.py,run_panel.py}` imports `UI`, and that
path is under `Working/`, which this night may not edit. **Condition 2 fails:** 39 files under `tests/` import
`UI`, and at least six mix core assertions with UI imports in the same file — `test_heldout_lock.py`
(`execute_recipe` raising `HeldOutRecordingLocked`, beside `UI.viewer.ViewerApp`), `test_manifest.py`
(`Working.manifest` beside `UI.admin.ManifestImport`), `test_export.py`, `test_import_drop_motifs.py`,
`test_compare.py` and `test_run_groups.py` — plus `tests/_session_isolation.py`, which ten test files import.
Deleting them would lose core assertions; splitting them is test surgery beyond "trivial". So `UI/`, its
tests and `tests/ui/` are left exactly as they are, no `archive/panel-ui` tag was created, and CLAUDE.md marks
them legacy. `webui/` imports nothing from `UI/` (checked by grep).

### 1.5 CLAUDE.md
Layout table gains `webui/` and `ui-prototypes/` and marks `UI/`, `tests/ui/` and `scripts/dev_serve.py`
legacy. Rule 1 now says which tree may import which UI libraries (Panel family → `UI/` only; browser libraries
→ `webui/client/` only; FastAPI → `webui/server/` only; core → none). A new "Web UI" section gives the start
commands and the gate (type-check + build + `webui/smoke.py`, plus pytest when Python outside `webui/`
changed). The Panel-surfaces section is kept but headed "legacy `UI/` only", matching 1.4.

### 1.6 Running pytest without touching the real DATA
The previous night's pytest run wrote into the real `DATA/` through a junction. The tests read
`DATA/derived/channels/{M2_aug_concat_fs1, Fig2A_dt0p1, L_LM_Jul_26_J_raw_fs10}`, the fixture and seed
directories and `DATA/db/*.json`, and write `DATA/derived/{step_cache, encodings, models, channels}`. Those
reads total ~1.2 GB, under the brief's 2 GB bound, so the suite ran in a temporary detached worktree
(`C:/Users/mmebr/Documents/CNN-pytest`) whose `DATA/` is a **real copy** of exactly those paths (verified not
to be a reparse point). Nothing collected by pytest differs from `208e72c`.

**Result.** 41 failed / 1296 passed. Two failures were my copy missing an input (`Plots/drop_motifs9_fig2a/`,
46 MB, and `DATA/derived/channels/Mushroom_260720_0509_4hrs_CH14_fs1/`); after copying them, both pass. The
other 39 are the two pre-existing classes the prototype night documented: the `LibraryGrid(conn)` test/code
mismatch and Windows `WinError 32` file locks at teardown (the lock failures in `test_plots_perf.py` and
`test_library_edges.py` reproduce serially). The baseline file only listed its last 14 failures, so a full
set comparison was not possible; instead every failure was classified, and none is attributable to this
night because no collected file changed. The failure list is `webui/PYTEST_GATE_TASK1.txt`.
`test_materialize_arbitrary_file` failed in the baseline and passed here — a lock flake, not a fix.

### 1.7 Old worktree: junction removed, worktree and branch left for you
Before touching the old worktree I listed every reparse point in it (only `CNN-ui-proto\DATA`, a junction
to the real `DATA/`) and every process whose command line mentions it (none; the only listener on 8765 was
my own bridge). I removed the link with `cmd /c rmdir` (no `/s`) and confirmed
`DATA/db/annotations.sqlite` still exists with its mtime (2026-09-13 11:02:54 UTC) and size unchanged.
**`git worktree remove --force C:/Users/mmebr/Documents/CNN-ui-proto` was then blocked by this session's
permission classifier**, and the non-force form refuses because the worktree holds untracked files
(`.venv`, `node_modules`, runtime DB copies). I did not work around it. The worktree directory and the
branch `proto/ui-stack-slices` (fully merged into `main`) are still there; with the junction gone, removing
them can no longer reach the real data. To finish:
`git worktree remove --force C:/Users/mmebr/Documents/CNN-ui-proto` then `git branch -d proto/ui-stack-slices`.

### 1.8 Tracker writes after the carry-forward file
The brief orders 1e (close the tickets) before 1f (write `docs/wayfinder/fog-of-war.md`). The resolution
comments on the signal-reduction, UI_CONTEXT-corrections and frontend↔core tickets must cite sections of
that file, so I wrote and pushed it first and posted every comment afterwards, so no comment links a file
that is not on `main` yet.

## Part 2 — every concept page as a working, empty shell

### 2.1 Route structure
Hash routes `#/<workspace>/<page>[/<id>][/<sub>…]?query`, one route per screen; a frame that shows a state of
a screen (popover open, drawer tab, modal, running, failed, empty) is reached by the click that opens it and,
wherever a critic or the smoke test needs to land on it directly, by a query parameter (`?drawer=detections`,
`?modal=import`, `?state=running`). `Route` gained `parts` (every segment after the workspace) and `query`, and
`setQuery()` edits the query in place; the original `page` and `params.id` are unchanged, so Explore and Analyse
kept working without edits. Analyse keeps one workspace with three families of routes
(`analyse/chain|block|glyphs`, `analyse/interrogation/…`, `analyse/training/…`) so the nav rail stays at six
workspaces (spec §2, §6.1 "modes are not modes").

### 2.2 One data seam, fixture-backed, marked demo
Every new read is a typed async function in `src/api/<workspace>.ts` returning `Sourced<T>` =
`{ data, source: 'demo' | 'live' }` (`src/api/seam.ts`). Until wired, the body is `demo(FIXTURE)`, which resolves
on the next macrotask so loading states exist; a later ticket swaps the body for a bridge call and components do
not change. `useSourced()` returns errors instead of swallowing them. Fixtures live in
`src/fixtures/<workspace>.ts` and import shared facts from `src/fixtures/canon.ts`, a transcription of spec §0
(recordings, channel names, classes, verdicts, family colours, families, the B24 chain, runs, jobs, queues, the
window set, models, templates, local limits), plus a seeded synthetic trace generator so screenshots are stable.
Where §0 is silent I invented the least surprising value and marked it in canon.ts: `M3_jul`'s file name and
start time, `L_LM_Jul26_J`'s file name and start, M4's start.

### 2.3 In-memory writes and simulated runs
`kit/store.ts` is a module-level store (`useDemoState`, `recordDemoWrite`): writes survive navigation and vanish
on reload, and a `window.__demoStore` hook lets critics read what a page "wrote". `kit/sim.ts` runs a named
simulation through queued → running → done (or failed / paused / cancelled) on a timer in a module-level
registry, so a run keeps going while you navigate away, like a real job; `forceSim` lets `?state=` deep links
land on running or failed frames. Controls that would need the core and have no sensible simulation raise the
toast `not wired yet: <what it would call>` (`kit/notWired.ts`); every other control does something visible.

### 2.4 Header counts
The frames print "3 need you" and "Jobs · 3". Prototype A showed only live counts (0 on a fresh start), which
would now contradict the Jobs page's own fixture cards. The chips now show live + demo: `DEMO_NEED_YOU = 3` and
`DEMO_JOBS_ACTIVE = 3` from canon.ts, with a tooltip that splits the two. The "demo data" chip sits next to the
page title on any page that rendered a demo read. The search pill and both chips became buttons (search →
"not wired yet", need-you → Jobs, held-out → Settings › Datasets) so the header has no dead clicks.

### 2.5 Smoke test walks every page state from per-workspace manifests
`smoke.py` gained a `routes` step that reads `webui/smoke_pages/<workspace>.json` (owned by that workspace's
builder, so parallel builders never edit one shared file) and, for each state, loads the route, performs its
actions, asserts the header, a non-blank main area, the expected selectors, no render-error card and no console
error, and writes `screenshots/pages/<workspace>/<page>--<state>.png`. `--pages-only` and `--only` narrow it.
The original live flows (corpus → signal → chain run → suffix re-run → failure → cancel → loud failure) still run.

### 2.6 Parallel builders, disjoint directories, per-unit side files
Builders own `src/<workspace>/` (Analyse is split into `src/analyse/` for the chain and block pages,
`src/interrogation/` and `src/training/`), their `api/` and `fixtures/` modules, their smoke manifest, and
three side files under `webui/pages/`: `status/<unit>.md` (progress, so a killed agent's work survives),
`fog/<unit>.md` (frontend-design fog, merged into `docs/wayfinder/fog-of-war.md` by the orchestrator at the
end — one file per builder avoids concurrent appends to one document) and `requests/<unit>.md` (changes they
need in shared files, which only the orchestrator makes). Critic screenshots stay local
(`screenshots/critique/`, gitignored); their findings JSON (`webui/critique/`) is committed.

### 2.7 The pytest gate at the end of the night
Re-run at `main` in the same copied-DATA worktree (`pytest -n auto`, 365 s): **39 failed, 1298 passed**, and the
failure set is **identical, line for line, to the Task 1 gate** (`webui/PYTEST_GATE_TASK1.txt`) — the
`LibraryGrid(conn)` contract mismatch and the Windows `WinError 32` teardown locks. Two more tests pass than in
Task 1 because that run was missing two inputs from the copy, not because anything changed. Nothing tonight is
collected by pytest (`webui/` holds no tests), so "nothing that passed before now fails" holds.

### 2.8 The weekly limit, and how the critique was resumed
At 16:2x on the 16th the account's weekly limit ("resets Sep 20, 6pm Australia/Brisbane") killed all 38 critics of
the critique workflow and the Settings builder's last phase; the harness later marked every orphaned shell task,
including both servers, stopped. On resume (the 20th) the servers were restarted, the Settings builder's
uncommitted diff was verified by its own smoke and committed, and the critique was re-run from a fresh workflow
rather than resumed: a failed agent leaves nothing to replay, so a resume would have been the same work. Two
changes from the first script: a per-unit lock so the two Settings and the two Library fix builders can never edit
one directory at the same time (the brief's disjoint-directories rule), and Training's fidelity lens re-run,
because its surviving round-one file scored 8 with an empty findings list while its rationale named three
deductions — a rating with nothing for a fix round to act on. Already-rated pages (Explore, Analyse chain/block/
glyphs, Review's fidelity lens) kept their round-one scores; nothing was re-rated that did not need it.

### 2.9 Two Settings defects fixed by the orchestrator, not a builder
The Settings smoke had two red states when the builder died. Both were real page bugs rather than manifest
mistakes, and the builder's directory was idle, so I fixed them and committed under the `settings` unit rather
than wait for a fix round: (1) the import-recording simulation's timer outlived its modal, and when it finished
it navigated to the new recording — from under whatever the user had opened since (the smoke saw it close the
unlock modal); the timer now belongs to the open modal and stops on close. (2) The Nulls page's α rule took the
smallest reportable p over every null kind, including the full-model shuffle (5 retrains drawn as dots, no p),
so α = 0.01 was "below the smallest reportable p (0.200)" and Save was disabled on every draft; `NullKind`
gained `p_value` and only kinds that report a p bound α. A third red state was a manifest artefact: a `goto` to
the URL already loaded does not remount the page, so "save" then "discard" on one hash cannot both find a draft;
discard now runs on Analysis defaults.

### 2.10 Sub-agents on Opus at medium effort
Instruction from the user on the 21st, after the second critique run lost 39 of 41 agents to the session limit:
sub-agents run on Opus at medium effort, never on Fable. The third critique script pins `model: 'opus',
effort: 'medium'` on every critic, fix builder and re-rater, and the two Settings-B lenses that had completed
before the limit were handed to it through the workflow's `args` rather than re-run, so Settings-B started at its
fix round. Everything else — eight sub-units, both lenses — was rated fresh by Opus. Recorded as a standing rule
in memory.

### 2.11 Final scores
Fifty-three pages, each rated by two independent critics (design fidelity, function); a page's score is the lower
lens of its last round, accepted at 8 or more. Round one left nine pages below 8 (channels-events, keyboard,
export, display, interrogation slope and aggregate, training 01–05 as one unit, discovery runs); each got a fix
round by its unit's builder and a re-rating by fresh critics, two pages (channels-events, keyboard) needing the
second re-rating the brief allows. Result: **0 below 8, mean 8.4** (17 pages at 9, 36 at 8; About scored 10 on
function). No page was rated by fewer than two lenses. The reports are generated by `webui/make_reports.py` from
the critique JSON, the smoke manifests and the page registry — nothing in PAGES.md is typed by hand.
