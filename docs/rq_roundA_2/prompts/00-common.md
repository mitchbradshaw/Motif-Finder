# Round A_2 prompts — common rules (P1–P4)

`docs/prompts/blocks/00-common.md` is the parent of this file. Its "Where you are", "How to work", both "Lessons"
sections and "Your report" apply. `docs/prompts/fixup/UX-1015-common.md` holds the client-work rules (toolchain, smoke
states, append-only shared files), and they apply too. What is specific to this round is below.

**Why these prompts exist:** the researcher's requests of 2026-10-17, made while planning RQ1b / RQ2b / RQ4b
(`../README.md`). Each prompt carries its own evidence, measured that day on `main` at `a5ed060` / `6a53e2e`. Re-check
any file:line you rely on: the code may have moved.

## Where you are

- An isolated git worktree on your own branch, cut from `main`. Your launch message names the base commit. Run
  `git log -1 --oneline` first, and `git merge --ff-only <base>` if you are behind it.
- Commit only in the worktree; never push, merge, switch branches or run `git worktree remove`.
- **No `DATA/` in your worktree.** Never create a junction, symlink or copy pointing at
  `C:\Users\mmebr\Documents\CNN\DATA`, and never read or write under `C:\Users\mmebr\Documents\CNN` except through
  your worktree (the interpreters and the client toolchain named in the parent files are read-only exceptions).
- Python:
  - conda: `PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" -m pytest <files> -q -p no:cacheprovider`;
  - FastAPI tests (`tests/test_webui_*`) skip under conda, so run them with
    `"C:/Users/mmebr/Documents/CNN/webui/.venv/Scripts/python.exe"`;
  - say which interpreter ran each file. A skipped test is not a passed one.
- **Client work:**
  - type-check and build with the main checkout's toolchain, as `UX-1015-common.md` says (`node …/tsc -b`,
    `node …/vite.js build`), never `npm install`;
  - write smoke states into `webui/smoke_pages/a2_<prompt>.json`, which the person merging walks them on a sandbox
    bridge;
  - if `node_modules` does not resolve from your worktree, say so in the report rather than working around it.
- No new dependencies. Run your own tests, the files your prompt names, and `tests/test_import_boundaries.py`. The full
  suite is run at the merge.
- Commit messages start with your prompt's prefix (`a2-p1:` …) and end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Test-first:** your first commit touches only `tests/` and its tests fail. Paste the failure summary in its body.

## Who owns what (so P1–P4 can be merged in any order)

| Prompt | Owns | Touches only the named hunks of |
|---|---|---|
| P1 held-out lock | `Working/registration/settings.py` (a new predicate) and the held-out helpers in `webui/server/{corpus,app,discovery_map,explore_routes,library,review,jobs_routes,shape_routes,blind_routes,analyse_routes}.py`; the top-bar held-out chip | `Working/execution.py` (the guard at ~349), `Working/discovery/fanout.py` (~158), `Working/discovery/seeded_search.py` (~550), `webui/server/discovery.py` (`_refuse_held_out` and its callers) |
| P2 HPC round trip | `Working/hpc/job_export.py`, `Pipelines/run_recipe/run_recipe.py`, a new core module for the chain job and its import, `webui/server/jobs_routes.py` (the `detection_chain` row), `webui/client/src/discovery/chrome.tsx` (`SlurmModal`) | `Working/execution.py` (the span-cap check), `webui/server/discovery.py` (`post_slurm` plus a new import route) |
| P3 windowed detection | a new core module for windows and stitching, the window scope in `webui/client/src/discovery/AddTemplateModal.tsx` | `Working/recipes.py` (a fan-out kind), `Working/discovery/fanout.py` (window targets), `webui/server/discovery.py` (the apply route), `Working/discovery/detection_map.py` (the row key) |
| P4 seed on demand | `webui/client/src/discovery/SeedPage.tsx`, `seedResults` in `webui/client/src/api/discovery.ts` | `webui/server/discovery.py` (the seed routes: the results job's cancel guard, `/api/discovery/seeds`, `_seed_by_id`) |

`webui/server/discovery.py` is shared by all four, and `Working/execution.py` and `fanout.py` by two each:

- keep your edits inside the named functions;
- add new routes at the end of the file;
- never reformat or reorder code you did not change;
- list every hunk you touched in your report.

**Suggested order:** P1 and P4 together (urgent for the demos, and their hunks are disjoint), then P2, then P3 (its
windows are ordinary runs, so P2's import carries them). `docs/prompts/blocks/W4-A-cnn-window-scores.md` is independent
and can run beside any of them.

## Talking to the researcher

Open your report with **In plain words**, as `CLAUDE.md` asks: what changed for someone new to the field, then what
they will see in the app.
