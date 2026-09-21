# Report — Prompt 00: cleanup and foundations

Run 2026-09-21 on `main`, from `ded0381` to `HEAD`. Tag `archive/panel-ui` = `ded0381` (pushed). Six
`cleanup:` commits plus one for this report; nothing else ran in parallel.

## What was removed

Totals against the tag: **298 files changed, +1,630 / −38,843 lines.** Every deletion is reachable at
`archive/panel-ui`.

| Path | Files | Lines | Why |
|---|---|---|---|
| `UI/` | 54 | 14,154 | The Panel/HoloViews app. Superseded by `webui/`. |
| `tests/` — 28 files that imported `UI` at module scope or tested only Panel surfaces | 28 | 11,213 | See the list below. The 39 pre-existing failures in the old baseline were all in these files. |
| `tests/ui/` | 6 | 651 | The Panel browser suite; `webui/smoke.py` is the successor. |
| `tests/_session_isolation.py` | 1 | 44 | Existed only to protect the old UI's session file. |
| `Working/Detection/sax/dsax_python/UI_snapshot_20260810-0512/` | 8 | 6,171 | A copy of the Panel app that imported `UI.*` from inside the UI-free core (fog L5). |
| `scripts/dev_serve.py`, `docs/UI_VERIFICATION.md` | 2 | ~560 | Panel-only tooling and its guide. |
| `Experimentation/wm_stage3_visual_check.py`, `Experimentation/Detection experiments/build_ui_previews.py` | 2 | ~560 | One-off Panel visual checks; the only Panel importers outside `UI/` and `tests/`. |
| `ui-prototypes/A-react-fastapi/` (screenshots), `ui-prototypes/B-panel/`, `ui-prototypes/.gitignore` | 23 | 5,317 | A was promoted to `webui/`; B no longer ran; the ignore file served only them. |
| `_to_delete/` (6 stale lock files), `webui/PYTEST_GATE_TASK1.txt` | 7 | 43 | Clutter; the gate file was superseded. |
| Local only, untracked: `flake.log`, `webui/screenshots/{critique,build,kit}/` (~691 MB) | — | — | Confirmed gitignored/untracked before deletion. |

Deleted test files: `test_chain_builder test_chain_state test_encoding_panels test_encoding_view
test_encoding_view_dsax test_filters test_library_detail test_library_grid test_motif_browser
test_overlay_density test_plots_perf test_review_keyboard test_review_surface test_reviewed_coverage
test_ribbon_panes test_run_panel test_run_panel_matrix_profile test_run_surface test_seed_exemplar
test_session_persistence test_shortcuts_and_view_controls test_ui_packages test_ui_responsiveness
test_ui_selection test_value_rendering test_window_matrix_coverage_ribbon test_window_matrix_panel
test_workspaces`.

Surgery on the eight mixed files, keeping every core assertion (critic 2 confirmed no helper or
fixture breakage and no altered core body): `test_export` (2 surface tests + `_FakeApp`),
`test_import_drop_motifs` (1 + `_FakeLibraryApp` + Panel/HoloViews imports), `test_compare` (7
`CompareSurface` tests, three fakes, two helpers; its single-implementation walk now covers
`Working` + `webui`), `test_run_groups` (1), `test_heldout_lock` (2 viewer tests; the `execute_recipe`
lock tests are untouched), `test_manifest` (1), `test_cross_channel` (1 + `_FakeApp`),
`test_library_edges` (1).

Config: `pytest.ini` lost the `ui` marker and `-m "not ui"` (the `--ignore` stays). `environment.yml`
now declares `playwright` instead of `pytest-playwright` because `webui/smoke.py` uses the runtime;
nothing was installed or uninstalled.

## What was moved or re-homed

- `UI/workspaces/review/queue_state.py` → `Working/review/queue_state.py` (new package); all 18
  tests in `tests/test_review_queue.py` retargeted unchanged.
- `tests/test_plots_perf.py`'s decimation pins → `tests/test_webui_decimate.py` against
  `webui/server/decimate.py` (loop oracle, ties/plateaus, spike survival, scaling), plus two checks
  on the `envelope()` the bridge actually serves.
- Twelve UI-free dSAX assertions from `tests/test_encoding_view_dsax.py` → `tests/test_dsax_diagnostics.py`,
  verbatim, plus (after critic 2) the even-alphabet `SAME band` warn row and the encoder contract that
  only dSAX declares `cutline_domain`.
- `tests/test_ui_packages.py`'s rule-1 test → `tests/test_import_boundaries.py`: nothing in the repo
  imports `UI`; nothing imports `panel`/`holoviews`/`bokeh`; the core does not import
  fastapi/uvicorn/starlette; and the walk proves it covered the trees it protects. Red before the
  deletion commit, green after.
- After critic 2, `tests/test_webui_corpus.py` re-homes the channel-cache pins (mmap reused per file,
  re-keyed on mtime; y-extent equals a full scan, memoised, re-keyed, NaN-safe), the verdict vocabulary
  (`webui/server/corpus.py` now imports `VERDICTS` from the schema instead of carrying a copy), the
  `z → aa → ab` letter rollover that `motifs.sax_string` persists, and `cache_status` treating a row
  whose directory is gone as not cached. The two invalidation pins touch the mtime instead of
  rewriting a mapped file — that rewrite is why their Panel-era versions were permanent `WinError 32`
  failures on Windows.

## New pytest baseline

`webui/PYTEST_GATE_FINAL.txt` is rewritten. `pytest -n auto` from the repo root, `main @ 6218904`:

| | |
|---|---|
| collected | 969 |
| passed | 954 |
| skipped | 13 |
| failed | 2 |
| wall-clock, `-n auto` | 131 s |
| wall-clock, serial | 209 s (same result) |

The failure set attributable to the code is **empty**. The 13 skips are `tests/test_execution.py`'s
`_channel_available()` guards and the two failures are `tests/test_drop_motifs_defects10.py` reading
Fig2A channel `.npy` files without a guard — both because **this checkout has no
`DATA/derived/channels/` and no `DATA/db/annotations.sqlite`** (the `DATA/db` directory was emptied at
12:27 on 2026-09-21, before this session started; `DATA/raw/` and `DATA/fixture/` are present). With
the derived channels present those two tests passed in the previous baseline run. `CLAUDE.md` rule 2
now carries the new count and timings.

`tests/test_webui_api.py` needs FastAPI, which lives only in `webui/.venv`; it skips under the conda
pytest with a message and passes (12 tests) under `webui/.venv/Scripts/python.exe -m pytest`.

## Bridge foundations (Part B), test-first

The failing tests were committed first (`f829b35`), confirmed red under both interpreters, then
implemented (`dd030c5`).

1. **Runtime modes** — `webui/server/runtime.py`: `Runtime(mode="sandbox"|"project", db_source=,
   runtime_root=, client_dist=)`. Sandbox (default, unchanged behaviour) copies the database under
   `webui/runtime/<stamp>/` and redirects `STEP_CACHE_ROOT`, both adapter `RESULTS_DIR`s and
   `MODEL_ROOT` there, refusing to start if one escapes. Project writes
   `DATA/db/backups/<stamp>.sqlite` through the sqlite backup API (last ten kept), puts the real file
   into WAL, and redirects nothing — refusing to start if any core path is under the runtime dir.
   `describe()` (served at `GET /api/runtime`) carries `mode`, `banner`, `redirected`, `db_backup`,
   `journal_mode`; `restore()` undoes the redirects. `run_server.py` takes `--sandbox | --project`
   (env `WEBUI_MODE`) and `--db PATH` (env `WEBUI_DB`), and prints the mode banner to stderr and the
   log. `start.ps1 -Project` / `start.sh --project`. Tests: `tests/test_webui_runtime.py` (5) —
   backup exists and is a real database, WAL on, no path redirected, pruning to ten, sandbox still
   redirects, restore works, unknown mode refused. The held-out refusal is untouched and proven in
   both modes by the API tests.
2. **`/api/*` never falls through** — `webui/server/app.py` registers `/api/{rest:path}` for every
   method before the SPA catch-all: unknown paths are a JSON 404 naming the path; a wrong method on a
   real `/api` route is a JSON 405 with `Allow`; non-API paths still serve `index.html`. Static dist
   comes from `rt.client_dist`. Verified live with `curl` as well. Tests: `tests/test_webui_api.py`
   (12, parametrised over both modes).
3. **Rule-5 seam** — `webui/server/writes.py`: `write_human` accepts `annotations`,
   `annotation_tags`, `adjudications`, `adjudication_tags`, `motif_*`, `templates`, `tag_vocabulary`;
   `write_machine` accepts `detections`, `runs`, `configs`, `artifacts`, `encodings`,
   `step_artifacts`, `recordings`. Each refuses the other's tables — and a table on neither list —
   with a `PermissionError` naming rule 5; identifiers are validated before any SQL is built; inserts
   are plain SQL, return the row id, and leave the commit to the caller. No route uses them yet.
   Tests: `tests/test_webui_writes.py` (24).

## UI gate

- `npx tsc -b` and `npm run build` in `webui/client`: both exit 0.
- `webui/smoke.py` against the bridge in sandbox mode: **not green on this machine, and every failure is
  the machine's, not the code's.** `webui\start.ps1` refuses to start without `DATA/db/annotations.sqlite`,
  so the bridge ran as `run_server.py --sandbox --db DATA/fixture/annotations.sqlite` (the sandbox copied
  the fixture; mode banner and `GET /api/runtime` verified; the live `GET /api/nope` is a JSON 404). The
  page walk rendered 518 of 553 states; the 35 failures (log:
  `webui/runtime/smoke-20260921-fixture-only.log`) are: every Explore/Signal and Analyse flow and state,
  because `/api/channels/<id>` 500s with `FileNotFoundError` on `DATA/derived/channels/M2_aug_concat_fs1/CH*.npy`
  (16 server tracebacks, four 500 console errors); the corpus heatmap "1 distinct fill" and the missing
  held-out card, because the fixture database has no annotations and no M4 recording; the two 404 console
  errors, which are route-level id lookups the fixture cannot satisfy (I checked every `/api/...` literal in
  the client against the server's routes — none is unserved, so the new `/api` catch-all is not involved);
  the loud-failure red card, which mounts inside a rendered step and so needs a channel; and nine
  `[Errno 22]` screenshot writes, a transient lock from the earlier run's browsers (the files are writable
  now). The tracked screenshots and `smoke-result.json` were restored from git so the evidence is not
  degraded by a data-less run. The smoke gate needs re-running once `DATA/` is back (question 1).

## Branches and worktrees

Step 7 had already been done before this session: `git worktree list` showed only the main checkout
and `git branch -a` only `main` / `origin/main`. Nothing to delete. The orchestrator's own
`test_a_real_provisioned_worktree_can_import_the_application` left a `ticket/acceptance-T99` worktree
and branch behind when I ran it (it fails at provisioning here because the junction source
`DATA/derived/channels/M2_aug_concat_fs1` is absent); both were removed.

## Critics

Two read-only Opus critics ran after Part A.

**Critic 1 (dangling references)** found two runtime breaks, both fixed in `6218904`:
`tests/test_channel_guards_are_honest.py` listed nine deleted files in `GUARDED_FILES` (would have
raised `FileNotFoundError` in ~36 parametrised cases) — now lists `test_execution.py`, asserts the list
matches the files that actually carry a guard, and shells out to a surviving guarded test;
`orchestrator/tests/test_worktree.py` probed provisioned worktrees with `import UI.app` — now imports
the core and adapter registry, opens the fixture DB at `DB_PATH` and memory-maps the first recording
it names. Agent-facing docs it flagged were fixed: the root `README.md` (Layout row, install line,
both `panel serve` commands, the workspaces section), `docs/agents/UI_CONTEXT.md` (dated supersession
note; constraints 1/3/5 amended), `FOLLOWUPS.md` (thread-leak item closed by deletion; the
`UI/viewer/` revisit trigger marked moot), `orchestrator/config.toml` comments and
`orchestrator/README.md`, `tests/test_wm_cost.py`'s docstring, and dated notes on
`docs/ORCHESTRATOR_SPEC.md`, `RUNNER_BUILD_PROMPT.md`, `RUNNER_FIX_PROMPT.md`, `RUNNER_STATUS.md`,
`Working/Detection/sax/dsax_python/UI_INTEGRATION_NOTES.md`, `webui/DECISIONS.md` §1.4 and
`docs/WIRING_PLAN.md` (Prompt 00 marked done).

**Critic 2 (lost core assertions)** classified all 376 test functions that exist at the tag and not on
`main`: 356 genuinely UI-only, 20 (B)/(C). Re-homed as described above: the four channel-cache pins,
the verdict-vocabulary pin (and the duplicated tuple it caught in `corpus.py`), the letter rollover,
the `cache_status` stale case, the `SAME band` warn row, the `cutline_domain` contract.

**Judged acceptable, left as is** (all listed by the critics):

- Provenance comments in core and bridge code naming `UI/plots.py` etc. as the origin of a copied
  function or a "keep in sync" partner (`Working/config.py` section headers, `Adapters/_sax_common.py`,
  `dsax.py`, `queries.py`, `window_matrix_store.py`, `decimate.py`, `chain.py`, `runtime.py`). They are
  attribution, still true as history; rewriting them buys nothing.
- Build/decision logs and research docs written before the decision (`ui-prototypes/DECISIONS.md`,
  `REPORT.md`, `webui/DECISIONS.md` beyond §1.4, `docs/research/*`, `docs/tickets/*`,
  `ClaudeSkills/work-orders/*`, `runs/`).
- `ui-prototypes/bench_ab.py` points into the deleted prototype trees and cannot run; kept beside its
  `bench_result.json` as the record of how the benchmark was produced (the README says so).
- `docs/wayfinder/fog-of-war.md` undecided items (C8, C-chain, lines ~936–992) that cite `pytest -m ui`
  or the old rule-1 wording as precedent — questions, not instructions; only the C8 pointer to the
  moved decimator pin was updated.
- Critic 2's two "not losses": seed-promotion writing a `motif_entry` with `detection_id IS NULL`, and
  the viewer's sub-sample snapping — both were `ViewerApp` behaviours with no core producer, so nothing
  on `main` implements them yet. Worth a pin when the web UI regains them (prompts 02/05).
- Critic 2's optional items not done: a bucket-vs-summary agreement test for the reviewed-coverage
  ribbon against `corpus.py`, and a `chain.estimate` composition test.

## Left, and why

- The two `test_drop_motifs_defects10.py` tests read real data without a `_channel_available()` guard.
  Adding one is the honest-guard convention, but it is a drop-motifs file outside this prompt's list;
  left for the user to decide.
- `run_groups` and `reviewed_spans` are on neither list in `writes.py` (the prompt's lists are
  explicit), so both doors refuse them. `run_groups` is plainly machine-side; `reviewed_spans` is
  human-side. Add them when a route needs them.
- The suite still writes `DATA/derived/step_cache/` when run from the main checkout (pre-existing
  behaviour of the recipe-executing tests, documented in `webui/DECISIONS.md` §1.6); it did so here.
  Not touched.
- `webui/screenshots/pages/` (521 tracked files) and `runs/` were kept as the prompt asked.

## Questions for the user

1. **Where did the real database and the derived channels go?** `DATA/db/` was emptied and
   `DATA/derived/channels/` is absent in this checkout (12:27, 2026-09-21). `webui\start.ps1` refuses
   to start without `DATA/db/annotations.sqlite`; the smoke gate and the two real-data tests need the
   channels. If they were moved deliberately for safety, the wiring prompts 01–05 need to know the
   path, or `--db` / `WEBUI_DB` to point at a copy.
2. Should `tests/test_drop_motifs_defects10.py` gain the channel guard (and join `GUARDED_FILES`)?
3. Should `run_groups` (machine) and `reviewed_spans` (human) be added to the rule-5 lists now?
4. `ui-prototypes/bench_ab.py`: keep as evidence (current) or delete with the trees it targeted?

## Chat summary

The Panel tree is gone from `main` and archived at tag `archive/panel-ui`: 298 files, −38,843 lines,
six commits. What stage 3 needs was moved first (`Working/review/queue_state.py`, the decimation and
dSAX pins, the rule-1 boundary test), the eight mixed test files were cut function by function, and
two critics then caught two real breaks and six lost core pins, all fixed. The suite is 969 tests
with an empty code-attributable failure set; the two failures and thirteen skips on this machine are
missing real data. Part B adds `--project`/`--sandbox` runtime modes with backup + WAL, a JSON 404
for unknown `/api` paths, and the rule-5 `writes.py` seam, all test-first. The client type-checks and
builds. The smoke gate could not be made green here because the derived channels and the real database are absent from this checkout; its 35 failures are all data-dependent (518 of 553 page states render), and the tracked screenshots were restored. The one thing to decide is question 1: the real database and derived channels
are not in this checkout.
