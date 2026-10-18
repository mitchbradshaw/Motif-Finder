# seed-search — the page becomes four steps: pick a seed, preview, choose the cut, keep the matches

**Read first:** `CLAUDE.md`; `docs/prompts/fixup/UX-1015-common.md` (isolated worktree, no `DATA/`, interpreters,
client toolchain through the junction, no smoke in a worktree, no new dependencies); then this file. You run alone:
open choices go under **Assumed** in your report. Commit prefix `seed-search:`; every commit ends with
`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Test-first.

## Why (the researcher, 2026-10-18)

> Discovery's seed search page is confusing and needs some redesign. … It should be as simple as: select exemplar →
> run preview → use preview detections as detections on their own, or run with surrogates and use detections.

## What the code does today (facts, 2026-10-18)

- A **preview** (`POST /api/discovery/seed/results`, `webui/server/discovery.py:2115`) is already the full search:
  the whole scope, every channel, the top `SEED_K = 200` matches per channel (`seeded_search.candidates`, :1881),
  with a cheap null (surrogate copies of each channel, draws capped by `_preview_draws` :81, :1761). It writes no
  `runs`, no `detections`, no `discovery_runs` row: the result lives in the process dict `_results` (:84) and in
  `discovery_sessions.state_json["seed_result"]` (:2033, candidates capped at 5,000), until the server restarts.
- A **run** (`POST /api/discovery/seed/run`, :3023) does the search AGAIN through `fanout.start` (:2670), keeping
  matches at or below the cut (`max_distance = cut`, :3014), and writes real runs and detections and a `discovery_runs`
  row (:2954). In `nullMode: 'preview'` (the default, :1698) it borrows the preview's null draws (`_preview_null`
  :2062) or draws them first (`_preview_prelude` :2969, `drawsPreviewFirst`); `'paired'` draws 200 paired surrogate
  chain runs per channel (:2605); `'off'` draws none (:3065).
- **Save as template** (`POST /seed/template`, :3261) stores the recipe only — seed, cut, scale bank, exclusion,
  carry/rebind — never results; applying it later (`/templates/apply`, :2814) re-runs the search on the new scope
  with the paired null (:2491).
- Nothing turns a preview's matches into detections; the closest precedent is the HPC import (:3215), which stores
  a result and re-runs the real search with `surrogate=False`. The preview result shape is `_assemble_seed_result`
  (:2008): candidates `{index, d, channel, scale, length}`, `nullByChannel`, `recommendedCut`.
- The page (`webui/client/src/discovery/SeedPage.tsx`): toolbar; ScopeCard with the three-at-a-time channel pager;
  RunsCard in seed mode; SeedCard (source Seg, provenance, "change seed", a disabled "+ seed", carry/rebind radios);
  ParamsCard (algorithm, window, scale bank, exclusion zone, overlap, "Revert to recommended", per-length null, the
  cut histogram with a draggable threshold); NotPreviewed → SearchProgress → DistanceProfile + MatchesCard; the
  ApplyBar (null mode Seg, cost line, Import HPC result, Save as template, Create SLURM script, Run seed search,
  Open in Runs).

## Decided with the researcher (grilling, 2026-10-18)

- **Four steps, drawn as a strip across the top and walked in order:** 1 pick the exemplar → 2 run the preview →
  3 choose the cut on the histogram → 4 keep the matches. Each step's card is the only thing open at a time; the
  strip shows where you are and lets you go back.
- **Two ways to keep:** **"Use these as detections"** writes the preview's matches at or below the cut as a run —
  the preview's null is the run's null — with NO second search; and **"Run with the rigorous null"** does what
  `nullMode: 'paired'` does today (200 paired surrogate runs). **"No null" is dropped.**
- **Visible by default:** the exemplar card and the cut histogram with its handle (and the recommended cut). **Behind
  one "advanced" toggle:** algorithm, window, scale bank, exclusion zone, overlap, draw count, "Revert to
  recommended". "Save as template" stays, as a secondary action (muted blue), with one line that says what it saves.
- **The cluster route appears only over the local limit:** one button that replaces "Keep" and says why ("about 45
  min here, over the 10 min limit — run it on the cluster"); Import HPC result lives in that state and in the
  Runs card's row, not in the bar otherwise.
- **When the run is done:** the row appears on Runs as now, and the done state offers **"Send unjudged to Review"**
  (the same picked-queue mechanism Discovery's browser uses, `sendDetectionsToReview`, fixup-AL) and "Open in Runs".
- The researcher's words for the gap between preview and run were a question, not a wish: the preview IS the search.

## The work

1. **Bridge: `POST /api/discovery/seed/keep`** — given the cached preview key (or the candidates re-read from
   `state_json` after a restart) and the cut, write the `discovery_runs` row (kind seed, `nullSource = "preview"`),
   the `runs` rows and the `detections` rows for every candidate at or below the cut, per channel, reusing
   `fanout`'s writers so the rows are indistinguishable from a run's (same `run_group`, same config hash, so the
   scoreboard, fires, Review and the map read them unchanged). Refuse with a 409 and a plain sentence when no preview
   is cached for this scope/seed/params (the page then offers to run the preview). A second press with the same
   identity returns the existing row (as `_seed_row_for` does, :2923). Detections are machine-only (rule 5): this
   writes detections, never verdicts.
2. **Bridge: drop `'off'`** from the null modes (the Seg and the server's acceptance; an old session that still says
   `off` reads as `preview`). Keep `'paired'` as the rigorous button's mode.
3. **Client: the four-step strip** (`SeedPage.tsx`, new small components in `discovery/seed/`): step cards open one
   at a time; the strip's labels are the researcher's words; the preview's progress bar is the real job's (as now);
   the cut step is the histogram card with the handle and the recommended cut line; the keep step has the two
   buttons, the cost line, and the over-limit replacement. Advanced toggle as decided. Nothing in the old page is
   deleted that a step still needs; what is not reachable any more (the "+ seed" disabled button, the null Seg) goes.
4. **Done state:** "Send unjudged to Review" and "Open in Runs"; the toast says how many were added and how many
   were already judged.
5. **Remove the three-at-a-time channel pager's hard-coded 3 from this page's labels** if any remain (use
   `PAGE_SIZE`).

## Files

Yours: `webui/server/discovery.py` (the keep route, the null-mode change), `Working/discovery/fanout.py` only if a
writer must be exposed (say so), `webui/client/src/discovery/SeedPage.tsx` and a new `discovery/seed/` folder,
`webui/client/src/api/discovery.ts`, `webui/client/src/discovery/discovery.css`, `tests/`. Report, do not edit,
anything else; `webui/smoke_pages/discovery.json` has seed states that will change — update them in your own unit
file instead and list the old states your change retires.

## Method and gate

- Tests (`tests/test_webui_discovery.py` additions, venv interpreter): a keep after a preview writes exactly the
  candidates at or below the cut as detections, one run per channel, and the scoreboard/fires read them; a keep
  with no cached preview is a 409 with a sentence; a second keep returns the same row; `nullMode: 'off'` is no
  longer accepted and an old session with it reads as preview; the paired path is unchanged (existing tests).
- `tsc -b`, `vite build` through the junction. Smoke states in `webui/smoke_pages/zzzzzzzzzzz_seed_search.json`:
  the strip shows four steps; after the preview the cut card is open; "Use these as detections" produces a run row
  on Runs; the advanced toggle hides the six controls by default.
- Run your files plus `tests/test_webui_discovery.py`, `tests/test_import_boundaries.py`.

## Stop and report if

the keep route cannot reuse `fanout`'s writers without a change to the run-group semantics; the preview's cached
candidates are not enough to write detections (e.g. they lack the span end); or a step needs a server read that
does not exist (describe it).

## Report

`docs/prompts/changes/reports/seed-search-report.md`: **Assumed**; the strip with one sentence per step; the keep
route's contract; the retired states; tests and interpreters; smoke states; what is left.
