# Report — Fixup AA: the manual-label arm exists, and a window set can be saved

Run 2026-10-03 on `main`, in the main checkout, **beside `Y`** (wave 1). Commit prefix `fixup-aa:`. The first commit,
`0169923`, touches only `tests/` and fails 29 tests under conda (no `catalogue.manual_labels`, no
`window_matrix_store.matrix_key`, no `template_kind`, `rowState.ts` without it) and 3 under `webui/.venv` (no
`window_sets` row written by *Save window set*). Every bridge ran in `--sandbox` on my own port **8771** with a private
client build (`--dist <scratchpad>/dist-aa`; the banner said `CLIENT = … a private build`). Nothing wrote to the real
`DATA/db/annotations.sqlite`; the real database was only opened read-only (`mode=ro`) to measure.

## In plain words first

You have about 11,000 ten-minute stretches of signal that you sorted by hand. The app could not use any of them to
train a model: nothing turned your verdicts into the "answer key" a classifier learns from. Now a block does —
*Manual labels* — and it is strict in the way you asked: a stretch gets your verdict only if it holds the whole of
something you labelled. Stretches you never looked at stay "don't know", never quietly "not interesting". You can now
also **save** a set of stretches (a "window set") with a note of how many of each verdict it holds, and the Library
lists it.

One thing changed on the way, **with your say-so**: keeping no two overlapping stretches in a training set was going
to throw away about two thirds of your labels. The fix keeps 91 % of them under the same guarantee (§3).

## 1. What is true now

| | Before | Now |
|---|---|---|
| A block that reads a human label | none (`grep` found nothing) | **`catalogue.manual_labels`**, `WindowSet → Grouping`, category *cluster*, page name *Manual labels*. Reads `annotations` (every source) and `window_verdicts` (via each saved set's bounds on disk); selects only |
| Classifier on a labelled Grouping | trained on every label it got | **trains on labels ≥ 0 only** and says so: model card *"trained on 5 labelled, 29 excluded"*, `n_excluded`, `excluded_reason` |
| Save window set | route existed, no caller, wrote only `registered_artifacts` (Library reads `window_sets`: *"0 saved"*) | button on the chain row **and** the block page of every WindowSet block (`sliding_windows`, `window_matrix`); writes the **`window_sets` row** with split + rule, spacing check, coverage per split and class at save, recipe hash; files on disk include `windowset.npz` + `features.parquet` (`WindowSet.from_path`) |
| Library › Window sets | 0 rows | lists the set; coverage **now** is recounted live from today's labels, **at save** is frozen; the split bar now draws shares (it was drawing counts as percentages) |
| Window-matrix file name | `wm_v1_<stem>_CH<n>_WIN<w>min_STEP<p>pct.npz` — a run and its surrogate wrote the same file | `…_STEP<p>pct_span<a>-<b>_<key8>.npz`, `key8` = hash of the recipe through the window-matrix step minus `resume_path`/`timeout_s` |
| Grouping-terminal footer | *"terminal Grouping — add a stage to reach a template type"* while saved as `training` | the validate payload carries `template_kind` (= `templates.kind_for_steps`) and the footer prints it: *"terminal Grouping → training template"* |

### The rule as built (Q41 + Q-W1)

- **Classes:** 1 = `interesting` (`seed` counts, and is counted as its subset), 0 = `not_interesting`, −1 = excluded.
- **Containment:** a window takes a label only if it wholly contains ≥ 1 labelled span and every contained span agrees.
  Partial overlap labels nothing.
- **Longer spans:** inside a longer `not_interesting` span → `not_interesting`; inside a longer `interesting` span →
  unlabelled. **Two defaults I chose, printed in the rules:** inside a longer `artifact` span → excluded as artifact
  (the artifact could be in it); and what a window contains and what it lies inside must agree, else *conflicting*
  (a small `interesting` span inside a long `not_interesting` one is a contradiction, not an `interesting` window).
  `unsure` labels nothing.
- **Every window has one fate**, so the line adds up: *34 windows · 5 labelled (interesting 2 · not_interesting 3) ·
  unlabelled 6 · conflicting 0 · artifact 0 · dropped for overlap 23 (no two windows overlap · labelled-first)*.
- **A grid hint:** when spans the windows overlap are never wholly contained, the rules say the windows are off the
  labels' grid and how to put them on it.

### How the store-reading step stays honest (core change, `Working/execution.py`)

A cached manual-label result would be stale the moment a verdict changes, and so would the classifier after it. A step
whose `run` declares `conn` now gets the run's connection and recording row, **and that step and every later one
bypass the step cache; a completed run of the same recipe is never reused**. Pinned by
`test_a_new_human_label_reaches_the_next_run_never_a_stale_cache` (cache threshold forced to 0). Documented in
`BLOCK_INTEGRATION.md` §1 beside the other hooks, with `persist(..., recipe_prefix)`.

## 2. Label coverage the block found on three real spans

Run through the sandbox bridge (`POST /api/runs`), `manual_labels_model` geometry (10-minute windows, step 200, catch22 +
fast entropy), labelled-first non-overlap; 24 h each, M2_aug_concat_fs1. Raw output:
`webui/screenshots/fixup/AA/three_spans_coverage.txt`.

| Span | windows | labelled | interesting | not_interesting | unlabelled | artifact | conflicting | dropped for overlap | classifier |
|---|---|---|---|---|---|---|---|---|---|
| CH1 · 0–24 h (job 28) | 430 | **18** | 4 | 14 | 118 | 0 | 0 | 294 | trained on 18, 412 excluded; holdout 5 |
| CH5 · 120–144 h (job 29) | 430 | **13** | 4 | 9 | 126 | 2 | 0 | 289 | trained on 13, 417 excluded; holdout 4 |
| CH13 · 360–384 h (job 31) | 430 | **25** | 0 | 25 | 111 | 0 | 0 | 294 | **refused**: one class only |

And in the browser (acceptance 1), CH1 450–452 h: 34 windows · **5 labelled (2 · 3)** · 6 unlabelled · 23 dropped.

**What this says:** about one label per hour per channel. A day of one channel can hold a single class (CH13), and
then the classifier refuses with its own sentence rather than training on nothing. A per-span classifier in Analyse
is a smoke test of the arm, not the arm: the arms need every labelled window of the recording pooled across channels,
which is `AB`'s job.

## 3. Non-overlap: decided one way, measured, changed with the researcher

Q-W1 said: a stride-600 subset of the 600/200 grid, on the phase that keeps the most labels. Measured over all 16
M2_aug channels (real DB, read-only):

| | windows |
|---|---|
| labelled windows on the full 600/200 grid | 11,110 |
| kept by the single best phase | **3,906** (35 %) |
| kept by labelled-first (keep a labelled window unless it overlaps one kept; fill gaps with unlabelled) | **10,077** (91 %) |
| labels that overlap a neighbouring label at all | 1,135 |

The labels are sparse and spread evenly over the three phases, so one phase throws away two labels in three that
overlap nothing. Put to the researcher in plain words with both numbers (2026-10-03); **they chose labelled-first.**
Recorded in `QUESTIONS.md` under Q-W1 (*REVISED*), in RQ1, and in the block's rules. The set records
`non_overlap_rule: labelled-first` instead of a phase offset. Tests that pinned the phase were changed on purpose
(commit `84b51e1` says so).

## 4. The saved window set's row (acceptance 2)

Analyse › Chain → `manual_labels_model` on CH1 450–452 h → ▶ Run → row 01 *⤓ Save window set* → name
`ws_CH1_450h_grid`, *Training set — keep no two overlapping windows* ticked → toast *"ws_CH1_450h_grid · 11 windows
saved of 34 · 5 labelled (interesting 2 · not_interesting 3) · unlabelled 6 · conflicting 0 · artifact 0 · dropped for
overlap 23 (labelled-first)"* → *Open in Library*. The row:

| column | value |
|---|---|
| name / version | `ws_CH1_450h_grid` / 1 |
| recording_id / channel / fs | 1 / 0 / 1.0 |
| window_length / stride / gap | 600 / 600 / 600 (gap = smallest start-to-start distance) |
| n_windows | 11 (of 34 offered) |
| split_json | `{"rule": "none", "note": "this block assigns no split; a blocked split is applied where the set is trained on"}` |
| spacing_json | `{"no two windows overlap": true}` |
| coverage_json | `labelled_windows 5` · `class_counts_at_save {interesting 2, not_interesting 3}` · `by_split.all {interesting 2, not_interesting 3, unlabelled 6, conflicting 0, artifact 0}` · `dropped_for_overlap 23` · `non_overlap_rule labelled-first` · `n_windows_offered 34` · `n_spans 708` · `rules` |
| labels_source | *human verdicts (annotations + window verdicts) · Analyse › step 01 window_matrix · job 29* |
| recipe_hash | `88b5ce41` (the producing prefix) |
| path | `webui/runtime/20261003-115314/window_sets/ws_CH1_450h_grid` (sandbox) |

Library › Window sets shows it (screenshot 04): *not train-safe* — honestly, because a window-matrix set carries no
split — with the reason *"no split recorded … — the windows do not overlap (labelled-first); a blocked split is applied
where it is trained on"*, the spacing check ✓, *5 windows · 45 % labelled*, interesting 2 / not_interesting 3, now and
at save. A sliding-windows set carries its blocked split and the per-split coverage.

## 5. The artifact name, and what it did to existing registrations (acceptance 3)

`artifact_name(..., span=, key=)`; `matrix_key(recipe)` hashes the recipe through the first window-matrix step without
`resume_path`/`timeout_s` and without the control keys `fan_out`/`surrogate`. The executor hands `persist` that prefix.
The HPC exporter computes the same key **before** baking `resume_path` into the recipe — the key ignores it, so the
resubmit chain still names one file (pinned by `test_an_hpc_export_names_the_file_the_run_will_write`).

- **Four distinct files**: `test_a_run_its_surrogate_and_a_second_span_each_keep_their_own_file` runs two spans of one
  channel, each paired with its surrogate through `run_paired_recipe`, and finds four artifact rows, four distinct
  files on disk. (Analyse has no surrogate run of its own; Discovery's is `T`'s to rework, so this is pinned headless.)
- **A downstream change does not rename the matrix** (k = 2 → 3 on the cluster after it: one file).
- **Existing registrations untouched.** No row is rewritten; `init_db()` is unchanged. The real DB holds 3 `artifacts`
  rows over 2 window-matrix paths — **two of them already share one file**, the collision this fixes — and 8
  `registered_artifacts(kind='window_matrix')`. The registry scanner's `_WM_NAME` reads both forms (pinned).
- `test_job_export.py`'s resume-path expectation changed with the name (on purpose, in the red commit).

## 6. Template kind (item 4)

§6.1 names SpanSet → detection and Model → training; BLOCK_INTEGRATION §4 extends training to WindowSet/Grouping, which
is what `kind_for_steps` saves. The footer now prints the server's kind (`template_kind` on `/api/chain/validate`),
so the two cannot disagree; an invalid chain reads *"not a template until the chain validates"*. No new kind.

## 7. Acceptance in a browser

1. **As written** — `windows_model`, delete *Hierarchical cluster*, insert *Manual labels* from *Show blocks that fit*,
   CH1 450–452 h, ▶ Run: the labels row reads *"120 windows · 30 labelled (interesting 0 · not_interesting 30) ·
   unlabelled 90 …"* and the classifier **refuses** — *"the Grouping puts every window in one class"*. Correct, and the
   reason is the rule: a 1-minute window can never wholly contain a 10-minute label, so it can only be
   `not_interesting` by lying inside one. **So I added the canonical template `manual_labels_model`** (10-minute
   windows, step 200, on the labels' grid → manual labels → classifier). On it: *"34 windows · 5 labelled …"*, and the
   classifier *"model · 2 classes · 34 windows · trained on 5 labelled, 29 excluded"* (screenshot 01; block page 05).
2. Save window set → Library (§4; screenshots 02–04).
3. Four files: pinned headless (§5).

**The source.** Explore's span viewer has no typed range and two hours are about one pixel on its 721 h overview, so I
set the exact source Explore's *send* writes (`CH1_A1 · 450.0–452.0 h`, start a multiple of 200) in session storage.
That is friction worth a line in `I` (U4): **a manual-label chain needs a span that starts on a multiple of 200
samples**, and nothing in Explore helps you pick one.

## 8. Q41

Answered before the run (Q41 + Round 10) and built as decided, with Q-W1's non-overlap revised by the researcher (§3)
and the two printed defaults in §1.

## 9. Items left

- **A saved set as an Analyse source** (§6.9 frame 0b): a chain-root validator change; stopped at saving and listing,
  as the prompt allowed. `AB` needs the set as a Models input, and `WindowSet.from_path(row.path)` reads it.
- **A set over several channels / the whole recording.** Save window set saves one chain's span of one channel; `AB`'s
  pooled training needs a multi-channel set.
- **Explore cannot place a span on the 200-sample grid** (§7) — `I`/U4.
- **"computed · now cached"** is printed for every computed step, including steps the cache skipped (below the 1 s
  threshold, and now store-reading steps). Pre-existing wording in `ChainPage.tsx:251`; not changed.
- **Cold reload of a block page** showed *"no result for this stage yet"* for a completed job until re-run — seen once,
  not chased.
- The classifier's one-class refusal still says *"Cluster into at least two groups, or adjudicate a second class"*;
  for a manual-label arm, *"widen the span"* is the likelier fix.
- Library's other rail acts (*Use as source in Analyse*, *Send N unlabelled to Review*, *Train in Models*) are as
  they were.

## 10. Files

**Mine (declared):** `Adapters/catalogue_manual_labels.py` (new), `Working/database/window_matrix_store.py`,
`webui/server/training_routes.py`, `webui/server/templates.py`, Analyse chain/block-page WindowSet rows
(`ChainPage.tsx`, `ChainRow.tsx`, `BlockPage.tsx`, new `SaveWindowSet.tsx`), Library › Window sets
(`webui/server/library.py`, `WindowSetsPage.tsx`), shared `api.ts` (appended, committed alone twice:
`6327768`, `f906dd1`), own smoke file `webui/smoke_pages/zz_analyse_run_aa.json`.

**Out of scope, and why:**

| File | Why |
|---|---|
| `Working/execution.py` | the block must read the store and must not be cached (§1); `persist` needs the recipe prefix (§5) |
| `Adapters/catalogue_classifier.py` | acceptance 1: *trains on the labelled windows only and says so* |
| `Adapters/preprocessing_window_matrix.py` | its `persist` names the file (§5) |
| `Working/hpc/job_export.py` | the resume path must be the name `persist` writes (§5) |
| `Working/registration/kinds.py` | "the importer that reads them keeps working": the scanner regex reads both names |
| `webui/server/chain.py` | `template_kind` on the validate payload (§6) |
| `webui/server/serialize.py` | a labelled Grouping names its classes and carries coverage/rules; the model card carries the exclusion |
| `webui/client/src/analyse/rowState.ts`, `captions.ts`, `views/GroupingView.tsx`, `views/registry.tsx` | footer wording; captions; class names, coverage tiles and rules on the Grouping view |
| `webui/client/src/fixtures/library.ts` | one optional field on `WindowSetRow` (`coverageNote`) |
| `docs/BLOCK_INTEGRATION.md` | the two new hooks |
| `tests/test_job_export.py` | the name it pinned changed on purpose |

None of `Y`'s files were touched.

## 11. The gate

**I took the machine for both smoke walks after `Y` had reported and gone idle; nothing else ran beside them.**

1. **`npx tsc -b`: clean. `npm run build`: green** (812 modules), with `Y`'s committed work in the tree.
2. **`pytest -n 4`** (conda, 12 m 27 s): **1988 passed, 19 skipped, 2 failed** — the failure set was
   `test_end_to_end.py::test_discover_adapters_registers_the_expected_count` and
   `test_adapter_spec.py::test_every_shipped_adapter_registers_without_modification`, both pinning 36 shipped adapters;
   the 37th is this ticket's block, so the pins became 37 (`4674b7e`, said so in the message). Re-run with
   `test_block_standard.py` and `test_import_boundaries.py`: 177 passed. **Failure set against the baseline: empty.**
   (Baseline in README: 1952 / 17 after `H`; `Y` and this ticket added the rest.)
3. **Under `webui/.venv`**, every `tests/test_webui_*.py` (`-n 4`): **356 passed, 3 xpassed, 1 failed** — the README's
   standing `test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers`. My three route tests pass.
4. **`webui/smoke.py`, full walk, fresh `--sandbox` bridge (port 8765), shared `client/dist`:**
   - **First walk: 613 screenshots, 9 failures.** One was **mine**: my smoke file was named `zz_analyse_aa.json`,
     which sorts *before* `zz_analyse_run.json`; my states leave a source set, so that file's first state
     (`fixup-j-dehshibi-funnel`, an unconditional `use-example` click) timed out. Renamed to
     `zz_analyse_run_aa.json`. The other eight: the five standing; the two `review.inspector--padding +/-… s` states,
     whose checks printed `ok` and whose screenshot *write* failed under my scratch `SMOKE_SHOTS` (the `/` in the name —
     the same artifact `Y` reported); and `review.inspector--3-queue-rail (click toggle)`, which did not recur.
   - **Second walk (the gate): 616 screenshots over 592 page states, 5 failures — exactly the five standing**
     (`discovery.runs--default` and the four Settings registration Check states). **0 browser console/page errors,
     0 unexpected server tracebacks.** My three `fixup-aa` states pass, and so does `fixup-j-dehshibi-funnel` after
     them. Screenshots went to the scratchpad (not the tracked tree); mine are copied to
     `webui/screenshots/fixup/AA/smoke/`.

**Evidence:** `webui/screenshots/fixup/AA/` — `01` the chain on `manual_labels_model`, `02` the save dialog, `03` the
saved toast, `04` Library › Window sets, `05` the Manual labels block page, `smoke/` the three gate states,
`three_spans_coverage.txt` the raw output behind §2.

**Commits:** `0169923` (red tests) · `6327768`, `f906dd1` (`api.ts`, appended) · `84b51e1` (implementation) ·
`4674b7e` (adapter-count pins) · the report commit.
