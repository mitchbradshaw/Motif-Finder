# UX-1015 — common rules for the seven usability prompts (AK, AL, AM, AN, AO, AP, AQ)

You are one of seven implementers. A managing session wrote your prompt, launches you, launches a **critic** on your
branch when you report, sends you the critic's findings for **one fix round**, then gates and merges your branch
itself. **You run alone and nobody can answer questions while you work**: when your prompt leaves a choice open, or
says to ask the researcher first, make the defensible choice (your prompt's "Recommendation" where it has one),
write it at the top of your report under **Assumed**, and build it.

`docs/prompts/blocks/00-common.md` is the parent of this file: its "Where you are", "How to work" and both "Lessons"
sections apply. What differs for this wave is below.

## Where you are

- An **isolated git worktree** on your own branch, cut from `main`. Your launch message names the base commit; run
  `git log -1 --oneline` first and `git merge --ff-only <base>` if you are behind it. Commit in the worktree. Never
  push, merge, switch branches or run `git worktree remove`.
- **No `DATA/` in your worktree** (only the tracked `DATA/library_seed/`). Tests are self-contained (synthetic signals,
  `tempfile`, a fresh `init_db()`). **Never create a junction, symlink or copy pointing at
  `C:\Users\mmebr\Documents\CNN\DATA`, and never read or write under `C:\Users\mmebr\Documents\CNN` except through
  your own worktree** (the two read-only exceptions are the interpreters named below). A deleted junction once
  destroyed the real database.
- Python: `PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" -m pytest <files> -q -p no:cacheprovider`.
  Tests that import FastAPI (`tests/test_webui_*`) skip under that interpreter; run them with
  `PYTHONIOENCODING=utf-8 "C:/Users/mmebr/Documents/CNN/webui/.venv/Scripts/python.exe" -m pytest <files> -q -p no:cacheprovider`
  from your worktree (it only reads that venv's packages; the tests write temp directories). A skipped test is not a
  passed one: say which interpreter ran each file.
- **Client work is in scope** for most prompts in this wave (unlike the block waves). Type-check and build **from
  `<your worktree>/webui/client`** with the main checkout's toolchain, never `npm install` or `npx`:
  - `node "C:/Users/mmebr/Documents/CNN/webui/client/node_modules/typescript/bin/tsc" -b`
  - `node "C:/Users/mmebr/Documents/CNN/webui/client/node_modules/vite/bin/vite.js" build`
  Both resolve `node_modules` through a junction the manager placed above the worktrees; the build lands in your own
  worktree's `webui/client/dist` (gitignored). Both must pass before you report.
- **You cannot run the browser smoke** (no database in a worktree). Write your smoke states into
  `webui/smoke_pages/<your unit>.json` (read two existing files for the format; a state that zooms or sends a span goes
  in a file sorted last) and say in your report, state by state, what each should show. The manager walks them on a
  sandbox bridge at the gate. Do not edit `webui/smoke.py` unless your prompt names it; if a new check kind is
  unavoidable, add it append-only and say so.
- No new dependencies, no `pip`/`conda`/`npm install`. Do not run the whole pytest suite (the manager runs the gate);
  run your own tests plus the files your prompt names, plus `tests/test_import_boundaries.py`.

## Scope and shared files

Your prompt's "Files" or "Work" section is your scope. These are the other prompts' files this wave — do not edit them;
if you need a change there, describe it in your report:

| Prompt | Owns |
|---|---|
| AK | `Adapters/detection_spike_v1.py`, `Working/Detection/analysis/spike_analysis.py`, its tests; the spike block's page text |
| AL | `webui/server/discovery.py` (`send_to_review`, `ReviewBody`), `Working/review/queues.py` (an `extend_queue`), `webui/client/src/discovery/RunsPage.tsx` (the Browse detections card only) |
| AM | `Working/training/shape.py`, `Adapters/preprocessing_trace_shape.py`, their tests |
| AN | `Working/library/grouping/*`, `webui/server/library.py` (grouping/tree routes), `webui/client/src/library/GroupingPage.tsx`; reads and reuses `webui/client/src/analyse/views/TreePage.tsx` (a minimal change there is allowed if named) |
| AO | new `Adapters/preprocessing_decompose.py` and its core module, `webui/client/src/analyse/views/SignalView.tsx`, `webui/client/src/analyse/ParamsPanel.tsx` |
| AP | captions on every page — runs **last**, alone, after the others merge |
| AQ | `webui/client/src/explore/CrossChannelPage.tsx`, `crossScale.ts`, `webui/server/explore_routes.py`, `Working/cross_channel.py` |

Files several prompts may need: `webui/client/src/api.ts`, `webui/client/src/api/*.ts`, `webui/client/src/kit/*`,
`webui/server/views.py`, `webui/server/serialize.py`, `webui/smoke.py`. Touch them **append-only** (new exports, new
cases; never reorder or rewrite an existing one) and list each such edit in your report so the manager can merge the
branches in any order.

Do not touch `docs/prompts/` (the manager keeps the ledger), `webui/screenshots/`, `webui/server/templates.py`
(unless your prompt names it), `CLAUDE.md`, or another prompt's files.

## How to work

1. **Test-first, verified.** First commit touches only `tests/`; its tests fail; paste the failure summary in the
   commit body. Then green, refactor, commit. Prefix every commit message with the prefix your prompt gives and end it
   with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
2. **Plain words on the face.** Every page or block you touch explains itself to someone new to the field in one
   sentence, with the rest behind an `InfoTip` (kit README P9). Numbers come from the bridge or the core, never
   recomputed in the browser.
3. **Loud failure.** Never catch an error into a blank; a refusal says why in words.
4. **Prefer an existing helper.** Grep before writing a second one; name the near-sibling and why not in a docstring.
5. **Time-box.** If one failing test has eaten a third of your effort, stop and report with it red rather than
   round-tripping; say exactly what you tried.

## Your report — your final message (write no report file)

1. **Assumed** — every choice your prompt left open and what you built (one line each).
2. **In plain words** — what changed for the researcher, two or three sentences.
3. **Files** — created / modified, one line each; append-only shared-file edits flagged.
4. **What was built** — numbered; deviations from your prompt and why.
5. **Tests** — the red commit (hash + failure summary), the green run (counts, per interpreter), what each test pins.
6. **Smoke states** — the file, each state's name and what it must show; anything the manager should check on real data.
7. **Gates you ran** — `tsc -b`, `vite build`, the test files.
8. **Open questions and risks.**
9. **Commits** — `git log --oneline main..HEAD`.
