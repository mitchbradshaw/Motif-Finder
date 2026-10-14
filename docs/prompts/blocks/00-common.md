# 00 — Common rules for every block prompt (all waves)

You are building one analysis block (or one small change) for the Underground Brains web app. A managing session
wrote this prompt and will critique, merge and evaluate your work. **You run alone and nobody can answer questions
while you work**: when the prompt leaves a choice open, make the defensible one and say so in your report.

## Where you are

- You run in an **isolated git worktree** on your own branch, created from `main`. Your current directory is that
  worktree's root. Commit there. Do not push, do not merge, do not switch branches, never run `git worktree remove`.
- **Check your base before anything else.** The worktree tool may cut your worktree from `origin/main`, which can lag
  the local `main` by dozens of commits (wave 2's worktrees started 52 commits behind, without wave 1's blocks or the
  prompts). Your launch message names the base commit: run `git log -1 --oneline`; if it is not that commit, run
  `git merge --ff-only <base>` and check again before reading or writing anything.
- Windows, Git Bash. Python is the conda base: `"/c/ProgramData/anaconda3/python.exe"`; always set
  `PYTHONIOENCODING=utf-8`. Run tests with
  `PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" -m pytest <files> -q -p no:cacheprovider`.
- **Your worktree has no `DATA/` (except the tracked `DATA/library_seed/`).** That is deliberate. Your tests must be
  self-contained: synthetic signals, `tempfile` directories, a fresh `init_db()` database where a test needs one
  (see `tests/test_template_dehshibi.py` for the pattern). **Never create a junction, symlink or copy pointing at
  `C:\Users\mmebr\Documents\CNN\DATA`, and never read or write anything under `C:\Users\mmebr\Documents\CNN`
  except through your own worktree.** A deleted junction once destroyed the real database.
- **No new dependencies.** Do not run `pip`, `conda` or `npm install`. Installed and usable: numpy 2.1.3, scipy
  1.17.1, stumpy 1.14.1, scikit-learn 1.7.2, aeon 1.4.0, tslearn 0.8.1, pywt 1.8.0, statsmodels, numba. Do not
  download and run other people's code. Reading papers and documentation on the web is fine.
- Do not run the whole suite (environmental failures without `DATA/` are expected and the manager runs the full gate
  in the main checkout). Run your own tests plus `tests/test_block_standard.py tests/test_adapter_spec.py
  tests/test_import_boundaries.py tests/test_templates.py`. Tests that import FastAPI (`tests/test_webui_*`) **skip**
  under the conda python — FastAPI lives only in the main checkout's `webui/.venv`. If your change is tested by one, say
  so in your report so the manager runs it with that interpreter; a skipped test is not a passed one.

## Read first

`CLAUDE.md` (the rules that are not negotiable, the test-first rule), `docs/BLOCK_INTEGRATION.md` (the whole contract:
§1 the spec, §2 the drawing conventions a view reads off a block, §3 cost, §5 the checklist, §6 the worked example),
`docs/CODING_STANDARDS.md`, `Adapters/base.py`, `Working/types/`, one existing adapter with the same conversion as
yours, and **your block's sections** in `docs/research/analysis-blocks-from-literature.md` (the evaluation and the
chain) and `docs/research/analysis-blocks-primary-sources.md` (what the paper and the installed code really say —
where it contradicts the plan, it wins).

## How to work

1. **Test-first, verified.** Your first commit touches only `tests/` and contains tests that **fail**; run them and
   paste the failure summary into the commit message body. Then make them pass, refactor, commit. Commit messages
   start with your prefix (given in your prompt) and end with the line
   `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
2. **Core in `Working/`, thin adapter in `Adapters/`.** The algorithm is a plain function in `Working/…` that imports
   no UI library; the adapter wraps it (`AdapterSpec`, `ParamSpec` with bounds, `page_name`, `category`, a
   `description` a newcomer can act on, in plain words, naming the one parameter to tune first). Put everything a page
   might want in `meta`; a measure the block had to define gets its rule in `meta["rules"]` (`[{name, rule}]`).
3. **Prefer importing an existing helper to writing a second one** — grep first. Write the "why not reuse" sentence in
   your module docstring when a near-sibling exists.
4. **Cost.** A block that is not O(n)-cheap declares `estimate` (`Working/block_cost.py::register_cost_model`, or the
   matrix-profile cost model for O(n²) work). A block that cannot run on very long spans says so with
   `max_span_samples` or processes in chunks.
5. **Units.** Prefer parameters that are unit-free (multiples of the signal's own noise level, seconds, fractions). If
   a parameter must be an absolute amplitude, it is in the signal's **stored** units (volts for M2), exactly as
   `detection.signal_threshold` does, and its help text says so. Never assume a unit the recording did not declare.
6. **Index conventions** (`BLOCK_INTEGRATION.md` §1): a SpanSet's `starts`/`ends` and its `*_idx` feature columns are
   span-relative; a Scores has one value per sample of `x`.
7. **Honesty on the face.** An absence is never hidden: a block that found nothing, or refused part of the input, says
   how much and why in `meta` (and in its summary numbers). Never catch an error into a blank.
8. **Faithful to the paper, adapted only where our data force it.** Every adaptation is named in the module docstring
   with its reason (1 Hz sampling, minutes-long events, drift). Licences: OASIS (GPL-3.0), Wave_clus (non-commercial)
   and WarpingWSF (no licence) are **not** to be copied — implement from the papers. BSD/MIT code may be read and
   adapted with its copyright notice kept in the docstring.

## Do NOT touch (the manager integrates these after merging)

`webui/server/templates.py`, anything under `webui/client/`, `webui/smoke_pages/`, `webui/server/views.py`,
`webui/server/serialize.py`, `tests/test_block_standard.py`, `docs/BLOCK_INTEGRATION.md`, `docs/rq_roundA/`,
`docs/prompts/`, `docs/research/`. If your block needs a change there, describe it in your report instead. **The one
exception:** a prompt that names one of these files in its own "Deliver" list hands you that file, and only the part
it names.

Your **template** (if your prompt names one) is tested end to end in your own test file: define its steps as a
module-level constant in the test (e.g. `TEMPLATE = {"name": ..., "kind": ..., "version": 1, "description": ...,
"steps": [...]}`) and run them through `Working.execution.execute_recipe` on a synthetic recording in a temporary
database, as `tests/test_template_dehshibi.py` does. The manager moves the constant into `CANONICAL`.

## Lessons from wave 1 (read before you design your tests)

Every wave-1 block needed a fix round after its critic, and most of the blockers had one cause: **a yardstick that
assumes white noise.** Fungal recordings at 1 Hz are strongly *coloured* — slow wander, drift, random-walk-like
stretches — so the sample-to-sample (first-difference) noise is 3–46× smaller than the level's own spread, and a
"k × noise" cut measured that way fires on every wiggle. Concretely:

- **Test on coloured backgrounds, not only white noise.** Every synthetic test set includes at least a random walk
  (cumulative sum of white noise, then detrended), an AR(1) background with φ ≈ 0.95–0.99, and a slow sine/drift
  under the events. A block that only ever saw white noise has not been tested.
- **Measure noise at the scale you judge at** (a robust MAD of the quantity being thresholded, at its own scale) and
  never let the events themselves raise the yardstick (median-based, not percentile-based).
- **Real events come in dense stretches.** A chain of drops every 20–60 min for 30–100 h is common (the researcher's
  known examples: M2_aug rec 3 500–530 h, rec 6 380–460 h; L_LM_Jul_26_J 380–480 h). Test the "mostly events" case.
- **Defaults are claims.** Every default is either from the paper, from a measurement you state, or labelled a
  placeholder in its help text. A default that only works on your synthetic set is a bug the manager will find on real
  data.
- **The manager can run things on real recordings; you cannot.** Say in your report exactly what you would want
  checked on real data and why — the manager runs it.

## Lessons from wave 2 (read before you design your tests)

Every wave-2 block needed a fix round too. The wave-1 lesson came back in new places, and a few new ones appeared.
The critic reports in `docs/prompts/blocks/reports/W2-*.critic.md` hold the measurements.

- **No fixed yardstick, anywhere.** Every wave-2 blocker was a constant that was right at one noise colour or span
  length and wrong at another. HDBSCAN's separation floor of 3.0: noise crowds reached 3.09 and a real noisy family
  scored 2.47. k-Shape's `omit_d` 0.5: it never fires on the SBD scale, and coloured noise sits *closer* to a centroid
  than noisy real members do. Snippets' knee floor of 0.25: two kinds of behaviour "found" in 12 h of pure noise, an
  8 h regime missed in 120 h. What worked: a **colour-preserving null computed in the run** — phase-randomised copies of
  the block's own input (each window's or the span's spectrum kept), a few seeded draws — or a cut **relative to the
  run's own curve** (snippets now asks whether change_k stands out from the median of the changes after it, by a margin
  that grows like √(number of pieces)). Test every selection rule (a knee, a k, a floor) **across span lengths, 12 h to
  120 h**, as well as across colours.
- **A warning nobody sees does not exist.** HDBSCAN's "unstable family" flag stayed in an internal payload and never
  reached the editor, the job result or a saved grouping. Every flag goes into `meta` and the summary line, and your
  report says where a page should show it.
- **A count is not a result without its quality, and the quality needs its null.** `catalogue.cluster` reported
  "3 clusters, sizes …" identically on noise and on real classes (silhouette 0.19–0.30 against 0.62). A block that
  groups, picks a number, or scores coherence reports its quality figure *and* what noise of the same colour scores.
- **Bookkeeping is not shape.** Identifiers, positions and the detector's own score (`train_id`, `word_id`,
  `span_score`) rode into clustering as features. `Working/types/windowset.py::BOOKKEEPING_COLUMNS` lists the columns
  every consumer drops; a block that adds an identifier, an index or a label column adds it there.
- **Say exactly what an automatic value covers.** Event windows' automatic length was described as holding "the whole
  event" but covered onset to half recovery, and the events too slow to measure (NaN durations — the longest ones)
  silently left the median. A NaN measurement means "longer than measurable": count it; never drop it from a statistic
  unannounced.
- **Cost models time the work, not the import.** MiniRocket's first calibration timed aeon's import (14–45 s) and
  estimated 6,370 s for an 8 s run — which the bridge's routing (a run over the Analyse limit is refused and written as
  a SLURM job) would have sent to the cluster. Use `register_cost_model(name, exponent, run_once, warm_up=…)` (the
  warm-up is not timed: imports, numba compiles), time enough work that the per-unit cost dominates, and report
  estimate against actual on a realistic span, in a fresh process and a warm one. `estimate` sees the span and your
  parameters, not the upstream windows: state what you assume about them.
- **A test that cannot fail asserts nothing.** "The exemplar is one of its label's windows" was true by construction
  (the window had been relabelled), and "merged ≤ base" passed for an implementation that ignored its parameter.
  Assert what could go wrong, and check the test fails on a broken implementation.
- **Read the paper's own rule even where the research file is silent.** The snippets paper does give a knee rule (k at
  the peak of change_k); the primary-sources file had missed it. The block's different rule was better on our data,
  but unnamed. Name every departure with the measurement that justifies it.
- **Amplitude-blind methods cannot see quiet against active.** z-normalised comparisons (MPdist, SBD, SVD entropy) give
  pure noise no shape of its own; say so on the face wherever a user would expect a separation.
- **Plain accuracy misleads on imbalanced labels** (0.66 with a majority class of 0.67): report balanced accuracy
  beside the majority baseline.
- **The bridge runs jobs on threads.** Never change process-wide state (numpy's global RNG, numba's thread count)
  without a lock. A first call's cost (aeon's import, a numba compile) lands on the first run in each bridge process:
  measure it and say how long.

## Your report — your final message (do NOT write a report file)

Return, as your final message, in this order:

1. **In plain words** — what the block does and what it found on the synthetic data, as if to someone new to the
   field (CLAUDE.md "Talking to the researcher").
2. **Files** — created / modified, one line each.
3. **The algorithm as implemented** — numbered steps; every deviation from the paper and why.
4. **Tests** — the red commit (hash + failure summary), the green run (counts), what each test pins.
5. **Integration snippets** for the manager, verbatim: the template dict (if any); a glyph suggestion for
   `webui/client/src/analyse/glyphs.tsx` `BY_NAME` (a 44 × 26 SVG sketch: grey input, blue output, amber cut, green
   kept — describe it in words if you are unsure of the TSX); a smoke-state suggestion; a `COSTED` entry if your block
   declares a cost.
6. **Open questions and risks** — anything the manager or researcher must decide, and anything you are unsure of.
7. **Commits** — `git log --oneline main..HEAD`.
