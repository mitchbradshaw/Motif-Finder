# Code-quality wave (tq), 2026-10-25 — common brief for every implementer

The researcher asked for a strict code-quality review of the 19–21 Oct overnight wave (`git diff 7d2d695..16b05d2`:
night-a/b/c, night-disc/analyse/review, site-map/runs/x, the demo fixes) and for the findings to be fixed. Your prompt
file (`docs/prompts/quality/<NN>-<name>.md`) names your package: the findings, the remedy, the files. Read it, this
file, and CLAUDE.md's "rules that are not negotiable". Do not read the other packages' prompts.

**The aim is fewer concepts with the same behaviour.** Delete duplicate helpers, wrappers, flags and branches. Do not
move the same complexity into a new place. If a remedy in your prompt would change anything the researcher can see or
rely on (a number, a refusal, a wait, an order, a timing budget, a cache hit), do not make that change: keep the
behaviour, and report the remedy you left out and why. The prompt's remedy is a strong suggestion, not a spec. If you
find a simpler route to the same deletion, take it and say so.

## Where you work

- Only in the worktree your launch message names (under `C:\Users\mmebr\Documents\CNN\.claude\worktrees\`), on its
  branch. Never edit the main checkout `C:\Users\mmebr\Documents\CNN` or another worktree.
- **Never `git stash`**: the stash is shared across worktrees, and another agent's stash pop takes yours. Never check
  out another branch, rebase, or reset past your own commits.
- Never read, write or link to `C:\Users\mmebr\Documents\CNN\DATA` (the real database). Your worktree has no `DATA/`;
  data-guarded tests skip there, which is expected.
- No package installs, and no servers or smoke runs (the manager walks the smoke units at the merge gate). Run no
  `pytest -n` and no full suite: run your own test files and the ones your prompt names.
- Write TSX/TS edits with the Edit/Write tools, not shell heredocs (they mangle quotes and JSX in this environment).

## Commands (run from your worktree)

- Type-check: `cd webui/client && node C:/Users/mmebr/Documents/CNN/webui/client/node_modules/typescript/bin/tsc -b`
  (resolves through the `node_modules` junction that sits above every worktree; never `npm install`/`npx`).
- Build: `cd webui/client && node C:/Users/mmebr/Documents/CNN/webui/client/node_modules/vite/bin/vite.js build --outDir <your scratchpad>/tq-<pkg>/dist`.
  The scratchpad is SHARED with the manager and the other agents: always write under your own `tq-<pkg>/`
  subfolder, never to `<scratchpad>/dist` or another bare name (the manager's gate serves `dist-*` from there).
- Core and `tests/test_*` (not webui): `PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" -m pytest tests/<file> -q -p no:cacheprovider`.
- Bridge tests `tests/test_webui_*`: `PYTHONIOENCODING=utf-8 C:/Users/mmebr/Documents/CNN/webui/.venv/Scripts/python.exe -m pytest tests/<file> -q -p no:cacheprovider`.
- Always also `tests/test_import_boundaries.py` (conda).
- Find every test that pins a file you change: `grep -rln "<file or symbol>" tests/` — many tests read client source
  as text or load a pure `.ts` file under Node by path, and a rename or deletion breaks them.

## Pure `.ts` files and Node

Several night-wave files say "no imports, so the tests run it under Node" and copy a helper for that reason. That rule
is stricter than it needs to be: Node 25 strips types and resolves relative imports that carry an explicit extension,
and `tsconfig.app.json` has `allowImportingTsExtensions`. `review/axis.ts` already does
`import { … } from '../charts/timeAxis.ts'`. So a pure file MAY import another pure file (no React, no runtime
imports of its own beyond pure siblings) with the `.ts` extension written out. Use that to delete a copy instead of
making another.

## Test-first (CLAUDE.md, verified by the manager)

Your first commit touches only `tests/` and contains a test that FAILS, and its message quotes the failure. For a
refactor the red test pins the new seam: the unified module's behaviour run under Node, a public core function, or a
source pin that the duplicate is gone. Then make it pass, refactor, and commit per step. Update the existing tests that
pin the old shape in the same commit as the code that changes it, and say in the message which pins moved and why.

## Style

Read like the surrounding code. The codebase writes a short dated header comment on each module saying why it exists
(`/* tq-<pkg> (2026-10-25): … */`). When you delete a duplicate, fix every comment that names it as a "near-sibling".
No file you touch may go from under 1000 lines to over; prefer leaving touched files shorter than you found them.

Commit messages start with `tq-<pkg>:` and end with:

    Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

Use `git commit -F <file>` for a message with quotes in it.

## Your final message (the manager sees only this)

1. Plain words first: two or three sentences on what is simpler now, as if to someone new to the code.
2. Each finding in your prompt: done / partly / skipped, and why.
3. Files changed with `git diff --stat main...HEAD`, and the net line change.
4. Tests run (exact commands) and results; `tsc -b` and the build result.
5. Any behaviour difference, however small, and anything a critic should look at hardest.
6. The smoke units the manager should walk (names from `webui/smoke_pages/`).
