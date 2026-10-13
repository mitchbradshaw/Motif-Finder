# 00 — Common rules for every wave-1 block prompt

You are building one analysis block (or one small change) for the Underground Brains web app. A managing session
wrote this prompt and will critique, merge and evaluate your work. **You run alone and nobody can answer questions
while you work**: when the prompt leaves a choice open, make the defensible one and say so in your report.

## Where you are

- You run in an **isolated git worktree** on your own branch, created from `main`. Your current directory is that
  worktree's root. Commit there. Do not push, do not merge, do not switch branches, never run `git worktree remove`.
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
  tests/test_import_boundaries.py tests/test_templates.py`.

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
`docs/prompts/`, `docs/research/`. If your block needs a change there, describe it in your report instead.

Your **template** (if your prompt names one) is tested end to end in your own test file: define its steps as a
module-level constant in the test (e.g. `TEMPLATE = {"name": ..., "kind": ..., "version": 1, "description": ...,
"steps": [...]}`) and run them through `Working.execution.execute_recipe` on a synthetic recording in a temporary
database, as `tests/test_template_dehshibi.py` does. The manager moves the constant into `CANONICAL`.

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
