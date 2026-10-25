# Critic brief — one tq refactor branch, before it is merged

You review one implementer's branch from the 2026-10-25 code-quality wave. You **do not edit** their worktree or
any file in the repo. Read, run their tests, and run your own experiments in your scratchpad, outside the repo.
Python: `"/c/ProgramData/anaconda3/python.exe"` (core tests) and
`C:/Users/mmebr/Documents/CNN/webui/.venv/Scripts/python.exe` (`tests/test_webui_*`), both with
`PYTHONIOENCODING=utf-8`. Never read, write or link to `C:\Users\mmebr\Documents\CNN\DATA`. No installs, no servers,
no smoke, no `pytest -n`, no full suite. Never `git stash` or check out a branch in their worktree. To look at an older
commit, `git -C <worktree> archive <sha> | tar -x -C <scratch dir>` and work there.

You are told the worktree, the branch and the prompt file. Start with `git -C <wt> log --oneline main..HEAD`,
`git -C <wt> diff main...HEAD`, the prompt, and `docs/prompts/quality/00-common.md`.

## What to check — in this order

1. **Behaviour preserved.** This is the axis that matters most. For each function, hook or route the branch changes,
   list what the OLD code did (every branch: the error path, the empty case, the timing or TTL, cancellation, ordering,
   what is cached and when it is dropped, what a failed read shows), then check the new code does the same. Name each
   difference, however small, and say whether the researcher could notice it. A refactor that quietly changes a
   refusal into a wait, a TTL, a cache key, or what an error shows is a blocker unless the implementer flagged it and
   it is clearly an improvement.
2. **The simplification is real.** Fewer concepts, branches, flags or files, not the same ones moved. Is anything
   left half-migrated (an old helper still exported beside the new one, a comment still naming a deleted file)? Did
   the change add a new duplicate, wrapper or cast? Did a touched file cross 1000 lines?
3. **Test-first and the tests mean something.** The first commit touches only `tests/` (`git show --stat`). Export it
   and run its new test: it must fail. Would each new or edited test fail if the behaviour it pins were broken? Were
   pins in existing tests moved honestly, or loosened until they pass?
4. **It builds and passes.** Run `tsc -b` (command in 00-common.md), the build into your scratchpad, the test files
   the prompt names, and `tests/test_import_boundaries.py`. Grep `tests/` for every file and symbol the branch deleted
   or renamed, and run any test that names one.
5. **Scope.** Files outside the prompt's list, each justified or flagged.

## Your report — your final message

1. **In plain words** — two or three sentences: is the code simpler, and does it still behave the same?
2. **Verdict** — `merge as is` · `merge after fixes` · `do not merge`.
3. **Findings**, most severe first: severity (`blocker` / `should-fix` / `nit`), file:line, what is wrong, how you
   showed it (the command or snippet and its output), the concrete fix.
4. **What you ran** — the commands and their results.

Be specific and evidence-based. No praise padding, and no nits that change nothing.
