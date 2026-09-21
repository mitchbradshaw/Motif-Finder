# Prompt 00 — Cleanup and foundations (run ALONE, before 01/02)

You are working in `C:\Users\mmebr\Documents\CNN` (Windows; the Bash tool runs Git Bash; python is
`"/c/ProgramData/anaconda3/python.exe"`, pytest lives in that conda base). Read `CLAUDE.md`, then
`docs/WIRING_PLAN.md` ("Cleanup decisions recorded for Prompt 00" is your scope), then `webui/DECISIONS.md` §1.4
(why `UI/` was not deleted last time — the two conditions you are now resolving properly). Work completely
autonomously; commit as you go with messages prefixed `cleanup:`; push `main` when the gate is green at the end.
Nobody else is running in parallel with you.

## Goal

Leave the repository containing only what the next stage (wiring the web UI to the core) needs: the core
(`Working/`, `Adapters/`, `Pipelines/`), the web UI (`webui/`), tests that test them, the docs that govern them,
and the tracked data seed. Remove the legacy Panel UI and everything that exists only for it. Add the two bridge
foundations both parallel wiring prompts depend on.

## Part A — retire the Panel tree

1. **Archive first.** `git tag archive/panel-ui <HEAD>` and push the tag, so the Panel app and its tests stay
   reachable by ref (fog L3).
2. **Move out what the next stage needs.** `UI/workspaces/review/queue_state.py` → `Working/review/queue_state.py`
   (it imports only `Working.database.*`; keep its 18 tests in `tests/test_review_queue.py`, retargeted). Port the
   min/max decimation assertions of `tests/test_plots_perf.py` to a new `tests/test_webui_decimate.py` against
   `webui/server/decimate.py` (the same algorithm copied from `UI/plots.py`). Keep `tests/test_ui_packages.py`'s
   `test_nothing_in_working_or_adapters_imports_from_ui` as the enforcement of rule 1, retargeted: no file outside
   `webui/` imports `UI`, and no file anywhere imports panel/holoviews/bokeh (matplotlib stays — 11 adapters and
   ~25 core modules use it).
3. **Delete** `UI/`, `tests/ui/`, `tests/_session_isolation.py` and `tests/_calibration_isolation.py` (check its
   importers first), `scripts/dev_serve.py`, `Working/Detection/sax/dsax_python/UI_snapshot_20260810-0512/`,
   `docs/UI_VERIFICATION.md`, the 30 test files that import `UI` at module scope, and the UI-only test functions
   in the 7 mixed files (`tests/test_export.py`, `test_import_drop_motifs.py`, `test_compare.py`,
   `test_run_groups.py`, `test_heldout_lock.py`, `test_manifest.py` and the one you find — keep every core
   assertion; grep `from UI\|import UI` to find the exact set). Remove the `ui` marker and `-m "not ui"` from
   `pytest.ini` (keep `--ignore=tests/test_analysis_modules.py`). Remove `pytest-playwright` from
   `environment.yml`'s pip block only if nothing else needs it (`webui/smoke.py` uses Playwright from conda —
   check before touching; do not install or uninstall anything).
4. **Prototypes.** In `ui-prototypes/` keep `REPORT.md` and `DECISIONS.md` (cited by `docs/adr/0001-web-ui-stack.md`
   and `docs/wayfinder/fog-of-war.md`); delete `A-react-fastapi/`, `B-panel/`, `.gitignore` entries that only served
   them, and screenshots. Grep both citing files for paths into the deleted trees and rewrite those citations to
   the surviving files or to `webui/` (do not delete a citation's claim).
5. **Clutter.** Delete `_to_delete/`; `flake.log` if untracked; `webui/PYTEST_GATE_TASK1.txt`;
   `webui/screenshots/{critique,build,kit}/` (gitignored, local, ~691 MB — confirm they are untracked first). Keep
   `runs/`, `webui/pages/`, `webui/critique/`, `webui/screenshots/pages/` (evidence).
6. **Docs.** `CLAUDE.md`: remove the `UI/`, `tests/ui/`, `scripts/dev_serve.py` rows and the "Panel surfaces
   (legacy UI/ only)" section; rule 1 becomes "the core imports no UI library and nothing in the repo imports the
   Panel family; React/d3 only under `webui/client/`, FastAPI/uvicorn only under `webui/server/`"; update the
   test-count sentence after your final pytest run; add one line under "What this repo is" pointing to
   `docs/WIRING_PLAN.md` for stage 3 (already added — check it survived). `docs/adr/0001` gets a one-line
   "Status: Panel tree removed 2026-09-xx, tag archive/panel-ui" note. Update `docs/wayfinder/fog-of-war.md`
   §Legacy tree items L1–L7 statuses to `decided` with one line each.
7. **Branches and worktrees** (the previous session's classifier blocked these; you have the user's instruction):
   `git worktree remove C:/Users/mmebr/Documents/CNN-dm6` (clean, on the merged branch `feat/drop-motifs-six`),
   `git worktree remove` each `.claude/worktrees/agent-*` (clean), `git worktree prune`; then delete local
   `feat/drop-motifs-six`, `worktree-agent-*` (merged, `-d`) and `research/*` (`-D`; their single files are
   identical on `main` under `docs/research/` — verify with `git diff <branch> main -- docs/research/<file>`
   before each); then `git push origin --delete` the remote `feat/*` and `research/*` branches. Leave `main` and
   the new tag.

## Part B — bridge foundations (small, both parallel prompts depend on them)

8. **`--project` mode** in `webui/run_server.py` / `webui/server/runtime.py` (fog C9, plan D4): opens the REAL
   `DATA/db/annotations.sqlite` in WAL mode after writing a timestamped backup to `DATA/db/backups/<stamp>.sqlite`
   (keep the last 10), leaves the step cache, adapter `RESULTS_DIR`s and `MODEL_ROOT` at their real locations, and
   prints the mode loudly at start and in `GET /api/runtime`. The existing copy-and-redirect behaviour becomes
   `--sandbox` and stays the default, so `webui/smoke.py` keeps running against a copy. `start.ps1`/`start.sh`
   gain a `-Project` / `--project` flag. Held-out refusal is identical in both modes. Test-first: a pytest that
   starts `Runtime` in project mode against a temporary copy of the DB and asserts the backup exists, WAL is on,
   and no path is redirected.
9. **`/api/*` never falls through to the SPA.** Any unknown `/api/...` path returns a JSON 404, not
   `index.html` (fog: the catch-all swallows typos). Test-first.
10. **Rule-5 guard at the seam.** Add `webui/server/writes.py` with two functions that every future write route
    must go through: `write_human(conn, table, row)` accepts only `annotations`, `annotation_tags`, `adjudications`,
    `adjudication_tags`, `motif_*`, `templates`, `tag_vocabulary`; `write_machine(conn, table, row)` accepts only
    `detections`, `runs`, `configs`, `artifacts`, `encodings`, `step_artifacts`, `recordings`. Each refuses the
    other's tables with a `PermissionError` naming rule 5. No route uses them yet; a test proves the refusal.

## Gate (all must be green before you push)

- `pytest -n auto` from the repo root: **zero failures** expected once the UI-importing files are gone (the 39
  pre-existing failures in `webui/PYTEST_GATE_FINAL.txt` were all in UI-importing files — confirm, and rewrite
  that file as the new baseline with the new count).
- `cd webui/client && npx tsc -b && npm run build`; then `webui\start.ps1` (sandbox) and
  `"/c/ProgramData/anaconda3/python.exe" webui/smoke.py --url http://127.0.0.1:8765` green; stop the server you
  started.
- `git status` clean; every deletion in a commit whose message says what it removed and why; `main` pushed.
- Never touch `DATA/` beyond reading (the backup in step 8 is written only by the test against a temp copy; do
  not run the bridge in `--project` mode yourself).

## Critique sub-agents (Opus, medium effort)

After Part A, spawn two read-only critics: one greps the whole repo for dangling references to deleted paths
(`UI/`, `dev_serve`, `UI_VERIFICATION`, `A-react-fastapi`, `B-panel`, `_session_isolation`, `UI_snapshot`) in
`.py`, `.md`, `.ps1`, `.sh`, `.ini`, `.yml`, `.json` and reports each with the line; the other reviews the test
surgery diff for core assertions that were lost (compare each deleted or edited test file's test names against
the tag `archive/panel-ui`). Fix what they find; record what you judged acceptable.

## Report

Write `docs/prompts/wiring/reports/00-cleanup.md`: what was removed (paths, line counts), what was moved, the new
pytest baseline, the bridge foundations with their tests, branches deleted, anything you left and why, and
questions for the user. End with the chat summary.
