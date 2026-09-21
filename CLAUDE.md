# CLAUDE.md — Underground Brains / Pipeline GUI

Repo context loaded for **every** agent working a ticket. This file carries what is true for all
tickets. Your ticket file carries what is unique to yours. If the two disagree, the ticket wins for
scope; this file wins for standards.

## What this repo is

A Panel/HoloViews application for analysing fungal bio-electric recordings, plus the UI-free core
underneath it. It is thesis instrumentation on a hard deadline: **feature freeze 28 August 2026**.

The work in progress is the Pipeline GUI, specified in `docs/PIPELINE_PRD.md` — the authority on what
is being built and why. Read the section relevant to your ticket; do not read the whole thing.

That file now holds **two parts**. Part 1 specifies the pipeline itself (tickets T01–T49, all merged
bar T49). **Part 2 — The Usability Wave** specifies the Analyse/Library rework (T50+) and supersedes
Part 1 wherever a Part 1 passage carries a `[SUPERSEDED by Part 2]` marker. If your ticket is T50 or
above, read Part 2's section for your ticket **and** any Part 1 passage it points you at — and treat
an unmarked Part 1 passage as still authoritative. The trap this is guarding against is real: Part 1
describes the chain builder as a vertical staged list, which is exactly what Part 2 replaces.

**Stage 3 — wiring the web UI to the core** (2026-09-21 →) is planned in `docs/WIRING_PLAN.md`; the agent prompts for it are `docs/prompts/wiring/0N-*.md`. Frontend v1 (every concept page as a working shell on fixture data) is complete: `webui/PAGES_REPORT.md`.

## Layout

| Path | What lives there |
|---|---|
| `Working/` | The UI-free core: config, execution, recipes, database, detection, catalogue, HPC |
| `Working/database/` | Plain-SQL layer. `schema.py` holds the whole schema and its migrations |
| `Adapters/` | The analysis block registry. `base.py` is the adapter contract |
| `webui/` | **The web UI** (ADR `docs/adr/0001-web-ui-stack.md`): `client/` React + TypeScript + Vite, `server/` FastAPI bridge over the untouched core, `run_server.py`, `start.ps1`/`start.sh`, `smoke.py`. See "Web UI" below |
| `Working/review/` | Headless Review-workspace state (`queue_state.py`), moved out of the retired Panel tree |
| `ui-prototypes/` | Frozen evidence of the stack prototypes: `REPORT.md` (decision evidence) and `DECISIONS.md` (build log). The prototype code trees live only at tag `archive/panel-ui` |
| `tests/` | pytest, headless. The default gate |
| `scripts/` | Dev tooling, not imported by the app |
| `docs/` | PRD, coding standards, ticket backlog, `WIRING_PLAN.md`, ADRs, agent prompts |
| `DATA/`, `MODELS/`, `MATRICES/`, `Plots/` | Gitignored. Provisioned into your worktree, not committed |
| `DATA/library_seed/` | The **exception**: tracked on purpose. Irreplaceable inputs to the library importer — its generator was deleted. See its `PROVENANCE.md` |

## The rules that are not negotiable

1. **The core imports no UI library, and nothing in the repo imports the Panel family.** The Panel/
   HoloViews/Bokeh tree was retired on 2026-09-21 (tag `archive/panel-ui`); no file anywhere may import
   `panel`, `holoviews` or `bokeh`, or the old `UI` package. React, d3 and every other browser library
   live only in `webui/client/`; FastAPI/uvicorn only in `webui/server/` and `webui/run_server.py`.
   `Working/`, `Adapters/` and `Pipelines/` import none of them and must never know a browser exists
   (matplotlib for figure export is the one drawing library the core keeps). This is what makes cluster
   execution, headless tests and the reproducibility claim possible. Enforced by
   `tests/test_import_boundaries.py`.
2. **The suite must pass with no regressions.** `pytest` from your worktree root: 969 tests as
   of 2026-09-21 (after the Panel tree was retired), **zero** of which fail before you touch anything —
   the baseline is `webui/PYTEST_GATE_FINAL.txt`; compare failure *sets*, not counts. About three and a half minutes
   serial (`pytest -n auto` — needs `pytest-xdist`, see Environment — cuts this to about two;
   most of the wall-clock is numpy/aeon/stumpy import cost paid per worker, so the speedup is real but
   not linear in core count). Do not chase a fixed number —
   every merged ticket adds tests, so the gate is "nothing that passed before now fails", not "N
   tests pass". If your change breaks one, either your change is wrong or the test encodes a
   behaviour your ticket is deliberately changing — and if it is the latter, say so explicitly in
   your commit message. For a change scoped to one module, running just its matching
   `tests/test_<module>.py` first (seconds, not minutes) is the faster feedback loop — the full
   suite is still the actual gate before calling anything done, especially for a change to
   widely-shared code (`Working/config.py`, `execution.py`, the DB schema).
3. **Plain SQL, no ORM.** Schema changes are additive and applied through `init_db()`, which must stay
   idempotent.
4. **Bulk arrays never enter the database.** They live on disk, referenced by path.
5. **Detections are machine-only; annotations are human-only.** They are separate tables on purpose.
   No code path may write a human verdict into a machine row or the reverse.

## Working a ticket

**Test-first, and it is verified rather than trusted.** Your first commit must touch only `tests/` and
must contain a test that *fails*. The orchestrator checks out that commit and runs the test to confirm
it is red. A ticket whose first test passes on arrival is quarantined before implementation begins,
because a test that never failed asserts nothing.

The loop, per seam: write the failing test → make it pass with the simplest change → refactor → commit.

**Stay inside your declared file list.** Your ticket names the files/modules it expects to touch.
Editing something outside that list is not forbidden, but every out-of-scope file is reported and
handed to the reviewer to justify. If you find yourself needing to change a file another ticket owns,
that is a signal to stop and say so, not to change it.

**Commit messages** start with your ticket id: `T14: bind side-inputs by content, not row id`.

**Do not read other tickets.** You have the one you were given. Reading neighbours produces scope
creep and duplicate implementations of the same helper.

**Prefer importing an existing helper to writing a second one.** Before adding a utility, grep for it.
Your ticket's merge-risk field names the siblings most likely to already own what you are about to
write.

## Environment

Windows, PowerShell, conda. The environment is shared across worktrees — **do not install packages or
change dependencies.** A ticket that genuinely needs a new dependency should stop and report it.
`pytest-xdist` (`pytest -n auto`) was added 2026-08-31 with the user's explicit sign-off for this
reason — it is now available, not an example to follow silently for the next dependency.
`playwright` plus a chromium binary (`python -m playwright install chromium`) was added the same day,
on the same sign-off, originally for the Panel browser suite; `webui/smoke.py` is what uses it now. Both
are dev tooling: nothing under `Working/`, `Adapters/` or `Pipelines/` may import either, and the
headless suite must keep passing on a machine where neither is present.

The web UI adds a second toolchain, signed off with the stack choice on 2026-09-15 (ADR 0001): Node + npm
for `webui/client` (project-local `node_modules`, never `npm -g`) and a project-local `webui/.venv` for
FastAPI/uvicorn. Neither touches the conda environment.

Run tests with `pytest` from your worktree root. Your worktree has its own `DATA/` fixture database;
it is not the real one and you cannot reach the real one. That is deliberate.

## Web UI (`webui/`)

**Start it** (from the repo root, in the main checkout — it needs `DATA/db/annotations.sqlite`):

    webui\start.ps1            # builds the client once, serves http://127.0.0.1:8765
    webui\start.ps1 -Dev       # bridge on 8765 + Vite dev server with HMR on 5173

(`webui/start.sh [port]` from Git Bash.) The first start creates `webui/.venv` (`--system-site-packages`,
fastapi + uvicorn) and runs `npm install` in `webui/client`; both are project-local and gitignored. The
bridge copies the database into `webui/runtime/<stamp>/` and redirects `STEP_CACHE_ROOT`, both adapter
`RESULTS_DIR`s and the classifier `MODEL_ROOT` there before any run, refuses to start if one escapes, and
refuses a busy port. `M4_aug_concat_fs1.mat` is refused on every route. **Never point it, pytest or an
adapter at a junction to the real `DATA/`.**

**The UI gate.** A change under `webui/` is done when all three pass:

1. `npx tsc -b` in `webui/client` (type-check) and `npm run build` (production build);
2. `"/c/ProgramData/anaconda3/python.exe" webui/smoke.py --url http://127.0.0.1:8765` against a running
   bridge — Playwright via the conda python; it fails on any browser console or page error, any pane that
   did not paint, any unexpected server traceback, and a broken core flow, and writes screenshots to
   `webui/screenshots/`;
3. the headless `pytest` suite, if the change touched anything Python outside `webui/`.

Loud failure is structural here: a render error is a red card plus a console error; a server error is a
500 with the traceback. Keep it that way — never catch an error into a blank.

## The Panel tree is gone

The legacy Panel/HoloViews app (`UI/`), its browser suite (`tests/ui/`), `scripts/dev_serve.py` and
`docs/UI_VERIFICATION.md` were removed on 2026-09-21 and are reachable only at tag `archive/panel-ui`.
Two findings from that era still apply to `webui/` and are why `webui/smoke.py` is a gate: a surface
that *constructs* has not necessarily *painted*, and a pane that is present can still throw in the
browser. Do not resurrect Panel code; port the behaviour to the web UI.

## When to stop

Stop and report rather than guessing if: the ticket contradicts the PRD; a blocking ticket's work is
not present in your base; you need a file another ticket owns; you need a new dependency; or you have
been round-tripping the same failing test for more than a third of your time budget.
