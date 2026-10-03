# Fixup AA — the manual-label arm exists, and a window set can be saved

**Ready to run — wave 1, beside `Y`. Q41 is answered (below).** The researcher's first priority after the fixups is training a model, so this line matters most. First of two prompts for
**Q1** (`AB-models-paired-job.md` follows and depends on this one). It is core and Analyse work; it
touches no Models page.

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md`, `docs/BLOCK_INTEGRATION.md` §1,
`docs/RESEARCH_READINESS.md` §Q1, `prototyping/UI_FUNCTIONAL_SPEC.md` §6.7 and §6.9,
`docs/prompts/fixup/QUESTIONS.md` **Q-T4** and "Ground truth (D2)" (the table of what the labels are), and
`Adapters/catalogue_classifier.py:1–60`.

Commit prefix `fixup-aa:`. Test-first; first commit touches only `tests/` and must fail.
**`--sandbox` only.**

## Decided — `QUESTIONS.md` Q41 and Round 10 Q-W1 (2026-10-03). Build exactly this.

- **Classes:** `interesting` (with `seed`, a subset of it) vs `not_interesting`. `artifact` windows are excluded from training and **counted**.
- **Label sources:** any human-labelled span of any length — the 600-sample `imported_10min` set, the Excel catalogue, spans drawn in Review or Explore. Machine labels never enter the human store.
- **The matching rule (containment, not overlap):** a window takes a label only if it **wholly contains at least one labelled span and every span it wholly contains agrees**. A span the window only partly overlaps does not label it (an `interesting` span whose event sits at its far end must not label a window that misses the end). A window whose contained spans disagree is left out and counted.
- **Spans longer than the window (Q-W1):** a window lying wholly inside a `not_interesting` span is `not_interesting` (nothing is anywhere in it); a window inside a longer `interesting` span is **unlabelled** (the event could be anywhere in it).
- **Unlabelled is unlabelled.** Time nobody labelled is never `not_interesting`; excluded and counted.
- **Non-overlapping training windows.** RQ1's windows sit on the labels' own 600/200 grid, but a window set saved for training keeps **no two overlapping windows**: a stride-600 subset of the grid, the phase offset (0, 200 or 400) chosen to keep the most labelled windows. The set records the offset and counts what was dropped for overlap and what was unlabelled. Make non-overlap a property of the saved window set (on by default for a training set) so `AB` reads it rather than re-deriving it.
- `meta["rules"]` prints all of the above in words: *n windows · k labelled · by class · unlabelled · conflicting · dropped for overlap*.

## Running in parallel (2026-10-03)

**Wave 1: you run beside `Y`** (`Y-seed-sources.md`), another agent in the same checkout. The README's **"Running two prompts at once"** rules apply in full: your own port and a private client build served with `run_server.py --dist`; `npx vite build --outDir <yours>` while working and `npm run build` only for the gate (the other agent's in-flight files may make it red — say so in the report); `pytest -n 4`, never `-n auto`, and announce in your report when you took the machine for smoke; shared files are **append-only and committed immediately with your own hunks only** (`git add -p`). If you need a file the other agent owns, stop and write to `requests/` rather than editing it.

| | files |
|---|---|
| **yours** | `Adapters/catalogue_manual_labels.py` (new), `Working/database/window_matrix_store.py`, `webui/server/training_routes.py`, `webui/server/templates.py`, the Analyse chain/block-page WindowSet rows, Library › Window sets |
| **`Y`'s — do not edit** | `webui/server/discovery.py`, `webui/client/src/discovery/SeedPage.tsx`, `webui/client/src/explore/` (`SpanActions.tsx`, `SignalPage.tsx`, `SignalDrawer.tsx`) |
| **shared** | `webui/client/src/api.ts`, `webui/smoke.py` (your states in your own `smoke_pages` file) |

`Y` makes Explore's *Take span for Review* write real `annotations` rows (seeds). Your block reads `annotations`; that is fine — read whatever is there, and do not assume the count is fixed while you run.

**Talking to the researcher:** any question you put to them opens with a plain-language explanation, then the options, then your recommendation (`CLAUDE.md`). **Before you report, update** `docs/prompts/rq_roundA/RQ1-cluster-vs-manual-labels.md` per that folder's README.

## What is missing, measured

- **No block reads a human label.** `grep -ln "annotation\|verdict" Adapters/*.py` finds nothing that
  consumes one. `catalogue.classifier` takes a `Grouping`; `catalogue.cluster` is the only block that
  makes one. The classifier's own docstring names the gap: the comparison Q1 asks for needs *"a
  manual-label step upstream"* (`catalogue_classifier.py:24–27`).
- **The labels exist.** 11,234 `annotations` rows of `source = 'imported_10min'` on
  `M2_aug_concat_fs1.mat` (recordings 1–16, ≈ 700 per channel): `interesting` 2,333 ·
  `not_interesting` 8,773 · `artifact` 128, every one **600 samples** long, starting on a **200-sample
  stride** (starts fall on 0, 200 and 400 mod 600 in roughly equal thirds). So adjacent labelled windows
  share two thirds of their samples — the leakage the PRD's blocked split exists for.
- **No window set can be saved.** `window_sets` has 0 rows; Library › Window sets reads *"0 saved"*;
  `POST /api/windowsets` (`webui/server/training_routes.py:65`) and `saveWindowSet`
  (`webui/client/src/api.ts:383`) exist and nothing calls the latter. Neither the WindowSet row on the
  chain page nor its block page offers the act (measured on `window_matrix` and `sliding_windows`).
- **A window matrix overwrites its own surrogate's — and any other span's.** The artifact is named
  `wm_v1_<stem>_CH<n>_WIN<w>min_STEP<p>pct` (`Working/database/window_matrix_store.py:189–196`): no span,
  no recipe hash. Measured in `webui/runtime/20261003-072048/annotations.sqlite`: run 80 and its paired
  surrogate run 81 both registered
  `results/window_matrix/wm_v1_M2_aug_concat_fs1_CH1_WIN1min_STEP100pct.npz` (artifacts 23 and 25) —
  the second write replaced the first's matrix on disk.

## What to build

1. **A block: `catalogue.manual_labels`, `WindowSet → Grouping`.** For each window it looks up the human
   verdict that covers it and emits a label; a window with no verdict is **unlabelled and counted**, never
   guessed. The conversion `windowset -> grouping` already has a view and a modifier
   (`BLOCK_INTEGRATION.md` §2), so it draws without UI work; `tests/test_block_standard.py` must stay
   green. The rule that maps a window to a verdict (exact grid match; else containment or an overlap
   fraction, as a parameter) and the label vocabulary are **Q41**. It reads `annotations` and
   `window_verdicts` and writes nothing (rule 5). Its `meta["rules"]` prints the rule and the coverage:
   *n windows · k labelled · by class*.
2. ***Save window set*, everywhere a `WindowSet` is produced** (§6.9): the chain row and the block page
   of `preprocessing.sliding_windows` and `preprocessing.window_matrix`. The saved row carries what §6.9
   lists — split assignment and rule, spacing check, verdict coverage per split and class **at save
   time**, recipe hash; bounds on disk, path in the row (rule 4). Library › Window sets lists it. §6.9
   also wants it as the **source** of a chain (the frame-0b case); the chain's root is spelled `signal`
   today (`BLOCK_INTEGRATION.md` §1), so a `WindowSet` root is a validator change — scope it, and if it
   is more than a day, stop at saving and listing: `AB` needs the set as a Models input, not as an
   Analyse root. Q-T4 asked whether this was the first thing in the stage; it is the first thing in this
   prompt.
3. **The window-matrix artifact name carries the span and the recipe prefix hash**, so a run, its
   surrogate and a second span of the same channel each keep their own file. Existing registered matrices
   keep their names; `init_db()` stays idempotent; the importer that reads them keeps working.
4. **A template whose terminal is `Grouping` is a template.** Today the chain footer says *"terminal
   Grouping — add a stage to reach a template type"* yet saves it as kind `training`
   (`webui/server/templates.py::kind_for_steps`). Make the footer and the kind agree, in whichever
   direction the spec's §6.1 supports; do not invent a new kind.

## Leave alone

| Leave alone | Why |
|---|---|
| Training across channels, paired arms, test blocks, Models pages, SLURM | `AB` |
| The six Analyse › Training fixture pages | spec P11: Analyse builds the template, Models trains it. They stay `demo data` until `AB` decides what of them survives |
| `catalogue.cluster`'s criterion and `k` | the cluster arm is already live; its parameters are the researcher's |
| The held-out lock | never |

## Acceptance — in a browser

1. Analyse › Chain → ⤓ Import `windows_model` → delete *Hierarchical cluster* → `+ insert` *Manual
   labels* in its place → source: an Explore span on `M2_aug_concat_fs1.mat` (not the example span;
   choose one with reviewed windows) → ▶ Run chain → the Grouping row reads the class sizes and the
   unlabelled count; *Classifier (model)* trains on the labelled windows only and says so.
2. The *Sliding windows + features* row → *Save window set* → name it → Library › Window sets shows it
   with its split rule, spacing check and verdict coverage.
3. Two chains on different spans of one channel, each with a paired surrogate (after `T`) → four
   distinct window-matrix files on disk.

## The gate

`npx tsc -b` + `npm run build` (own `--outDir` and `--dist` if another prompt is in the checkout);
`webui/smoke.py` on a fresh `--sandbox` bridge, alone, finishing on the **full** walk; `pytest -n 4`
against the baseline in `README.md` (re-measure; compare failure sets); `tests/test_import_boundaries.py`
and `tests/test_block_standard.py` in particular.

Evidence into `webui/screenshots/fixup/AA/`.

## Report

`docs/prompts/fixup/reports/AA-manual-labels-and-window-sets.md`: the label coverage the new block found
on three real spans (windows · labelled · per class · unlabelled); the saved window set's row; the
artifact-name fix and what it did to existing registrations; Q41 answered or defaulted; items left;
out-of-scope files touched; the gate. Then close `QUESTIONS.md` Q-T4 in place.
