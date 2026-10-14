# Critic brief — reviewing one block (any wave) before it is merged

You review one implementer's branch. You **do not edit** their worktree or any file in the repo: read, run their tests,
and run your own experiments in a scratch directory outside the repo (your session's temp/scratch directory). Python:
`"/c/ProgramData/anaconda3/python.exe"` with `PYTHONIOENCODING=utf-8`. Never create links to, read or write
`C:\Users\mmebr\Documents\CNN\DATA`. No package installs.

You are told the worktree path, the branch and the prompt file. Start with
`git -C <worktree> log --oneline main..HEAD`, `git -C <worktree> diff main...HEAD`, the prompt
(`docs/prompts/blocks/<file>` and `00-common.md`), the block's sections of
`docs/research/analysis-blocks-from-literature.md` and `docs/research/analysis-blocks-primary-sources.md`,
`docs/BLOCK_INTEGRATION.md` and `docs/CODING_STANDARDS.md`.

## What to check — five axes

1. **Spec.** Every acceptance item in the prompt: met, and *tested so that the test would fail if it were not*. A test
   that passes on a trivially wrong implementation does not count. Anything the prompt asked for that is missing.
2. **Faithful to the paper.** Compare the code with the algorithm as the primary-sources file states it (formulas,
   defaults, stopping rules). Every deviation must be named in the module docstring with its reason; flag any that is
   not, and any that changes the method's meaning without saying so.
3. **Correct on our data.** Try it yourself on synthetic traces that look like fungal recordings (1 Hz, events of
   tens of seconds to an hour, drops with slow recovery, drift, noise) and on the edge cases: empty / very short
   span, constant signal, NaN samples, a span with no events, a span that is mostly events, very long input (time a
   1–2.6 M-sample run if the prompt claims a figure). **Always include coloured backgrounds** — a detrended random
   walk and an AR(1) with φ ≈ 0.95–0.99 — because wave 1's blockers were almost all yardsticks that assume white noise
   (`00-common.md`, "Lessons from wave 1"). For a clustering or categorising block, also run it on inputs with **no
   structure** (windows of phase-randomised noise, shuffled labels) and say what it reports there: a block that finds
   confident families, or a high accuracy, in pure noise is a blocker. **Sweep every selection rule** (a knee, a number
   of groups, a floor, a "suggested" value) **across span lengths, 12 h to 120 h,** as well as across colours — wave 2's
   snippets knee held at 24 h and failed at 12 h and 120 h. Hundreds of null runs are cheap on a decimated proxy (0.1 Hz
   with the real durations, which proved conservative against 1 Hz in wave 2); confirm a few at 1 Hz. Check that every
   warning or flag reaches `meta` and the summary line, not only an internal payload (wave 2's "unstable family" flag
   never reached the page). Time the block's `estimate` against the actual run on a realistic span, in a fresh process
   and a warm one: an import or a JIT compile timed as work makes the bridge refuse an 8-second run. The bridge runs
   jobs on threads: flag process-wide state (numpy's global RNG, numba's thread count) changed without a lock. Run
   the no-structure case **at the block's defaults, on hundreds to a thousand items, and through the next block** —
   wave 2's families test passed at non-default settings on 80 events while the defaults placed half of all
   random-walk events in "families". Ask what the block's null cannot see (a trend-kept surrogate keeps a smooth
   shape's curve; phase-randomised copies of cut events crowd under HDBSCAN) and whether that blind spot is the
   block's own subject. Check index conventions (SpanSet starts/ends and `*_idx`
   columns span-relative; Scores one value per sample), unit handling (unit-free or stored units, as the prompt
   says; ×1000 scaling), and the drawing conventions of `BLOCK_INTEGRATION.md` §2 (a float param named `threshold`
   only where a draggable absolute cut is meant; `meta["events"]` with `onset_idx`/`trough_idx`; `meta["rules"]`).
4. **Standards.** `docs/CODING_STANDARDS.md` and `BLOCK_INTEGRATION.md` §1/§5: no UI import in `Working/`/`Adapters/`;
   the core is a plain function, the adapter thin; `ParamSpec` bounds and defaults sensible; `category`, `page_name`,
   a `description` a newcomer can act on (plain words, the first knob to turn); `estimate` declared if not O(n);
   honest `meta` (absences counted, nothing caught into a blank); no duplicated helper where one exists (grep).
5. **Test-first and scope.** The first commit touches only `tests/` (`git show --stat <first>`), and its message shows
   a failure. No file outside the prompt's scope is touched (the "do not touch" list in `00-common.md`).

## Your report — your final message (no report file)

1. **In plain words** — two or three sentences on whether this block does what it claims, as if to someone new to the
   field.
2. **Verdict** — `merge as is` · `merge after fixes` · `do not merge`.
3. **Findings**, most severe first, each: severity (`blocker` / `should-fix` / `nit`), file:line, what is wrong, how
   you showed it (the command or snippet and its output), and the concrete fix.
4. **What you ran** — the commands and their results (test counts, timings, your experiments).

Be specific and evidence-based; do not pad with praise or with nits that do not change behaviour.
