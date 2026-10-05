# Fixup X — divergence between the human record and a run, counted so that it means something

**Runs after `L` and `T`** (it needs verdicts that can be written, and surrogate detections out of the
count). No new research decision: the rule was decided on 2026-09-23 (`QUESTIONS.md` **Q-D2**, answered
*(a) and (c) together*) and never built — `grep -ri containment Working/discovery webui/server` returns
nothing. It is what **Q5** needs, and it makes the precision column mean something for Q2 and Q4.

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md`, `docs/RESEARCH_READINESS.md` §Q5,
`docs/prompts/fixup/QUESTIONS.md` "Ground truth (D2)" **in full, including its caveat**,
`docs/prompts/fixup/05-discovery.md` D2, `prototyping/UI_FUNCTIONAL_SPEC.md` §4.6, §5.1, §7.3 and §7.7,
and `Working/database/queries.py:371–440`.

Commit prefix `fixup-x:`. Test-first; first commit touches only `tests/` and must fail.
**`--sandbox` only.**

## Running in parallel (2026-10-03)

**Wave 4: you run beside `V`** (`V-library-edges-and-scale.md`), another agent in the same checkout. The README's **"Running two prompts at once"** rules apply in full: your own port and a private client build served with `run_server.py --dist`; `npx vite build --outDir <yours>` while working and `npm run build` only for the gate (the other agent's in-flight files may make it red — say so in the report); `pytest -n 4`, never `-n auto`, and announce in your report when you took the machine for smoke; shared files are **append-only and committed immediately with your own hunks only** (`git add -p`). If you need a file the other agent owns, stop and write to `requests/` rather than editing it.

| | files |
|---|---|
| **yours** | `webui/server/corpus.py`, `Working/database/queries.py` (divergence queries), Explore › Corpus, the Discovery scoreboard's precision cells and Compare's disagreement breakdown |
| **`V`'s — do not edit** | `webui/server/library.py`, `Working/library/matching.py`, `Working/database/schema.py` (`motif_edge`), Library › Family, the Seed page |
| **shared** | `webui/client/src/discovery/RunsPage.tsx` (`V` adds *Add N matches*; you change scoreboard cells — touch only your own component), `webui/server/discovery.py`, `webui/client/src/api.ts`, `webui/smoke.py` |

`Working/database/schema.py` is `V`'s for this wave: if you need a column, request it.

**Talking to the researcher:** any question you put to them opens with a plain-language explanation, then the options, then your recommendation (`CLAUDE.md`). **Before you report, update** `docs/rq_roundA/RQ5-human-vs-machine-divergence.md` per that folder's README.

## What is wrong today

1. **Explore › Corpus's *disagree* is not a divergence.** `webui/server/corpus.py:279–281` counts every
   annotation with no overlapping detection, plus the reverse, **whatever the verdict and whether or not
   any run covered the span**. Measured on `M2_aug_concat_fs1.mat`: 11,261 "disagreements" against
   11,265 annotations. A `not_interesting` window where the detector found nothing counts as a
   disagreement; so does every annotation on the 10 of 16 channels no run has ever touched.
2. **The units differ.** 11,234 of the 11,269 annotations are 600-sample review windows
   (`imported_10min`, on a 200-sample stride — starts fall on 0, 200 and 400 mod 600); detections are
   events. Under §4.6's reciprocal IoU a 179-sample event can never match a 600-sample window, so
   Compare with *human annotations* as a side reads *both 0* and the scoreboard's precision is 0 by
   construction (`05-discovery.md` D2).
3. **The two core divergence queries have no caller** outside `tests/`
   (`divergence_rejected_detections` :384, `divergence_annotations_without_detection` :414), and the
   second has the same blindness as item 1.
4. **Nothing breaks divergence down** by channel, time or morphology, which is the "is it structured"
   half of the question.

## What to build

1. **Q-D2's two numbers, in the core, each printing its own rule.**
   **(a) Containment over the window labels** — *does the detector fire where a human saw something*: a
   detection is scored by the reviewed window it falls in. **(c) Extent agreement over the event-shaped
   rows** — §4.6's rule, over the 35 rows that are not 600-sample windows, **with the width distribution
   of its denominator printed beside the number** (they run 126 to 324,000 samples; Q-D2's caveat). One
   module, read by the scoreboard, Compare and Explore; the rule's name and parameters travel in the
   payload and are drawn where the number is.
2. **A divergence that conditions on what it must.** Four cells for a run on a scope, and a fifth that
   is not a cell: machine yes / human yes · machine yes / human no · machine no / human yes · machine
   no / human no · **not comparable** (no run covered it, or no human reviewed it). "Human no" is a
   `not_interesting` or `artifact` verdict or a rejecting adjudication; "machine no" requires that the
   run's own span covered the place. Surrogate detections are never machine findings (`T`, Part A).
3. **Explore › Corpus *disagree* uses it**, scoped by the page's existing *Detections from · runs*
   picker; with no run chosen it says what it is pooling. The bottom bar's *N disagree* becomes the two
   real cells, with the not-comparable count beside them.
4. **The breakdown.** For one run against the human record: the two disagreement cells by channel, by
   time bin, and by morphology where a side has one — `annotation_tags` of category `element` on the
   human side (34 links today, say so on the page), the detector's own morphology on the machine side.
   A table and the existing density map; **no test of structure and no null** — there is none to draw,
   and the page must say so the way Interrogation does. Put it where the researcher already is
   (Discovery › Compare with *human annotations* as a side, or Explore › Corpus); do not add a workspace.
5. **Adjudications count.** A detection a human rejected in Review is "machine yes / human no" even when
   no annotation overlaps it; one a human accepted is "yes / yes".

## Leave alone

| Leave alone | Why |
|---|---|
| Storing a class or tag given in Review (`07-review.md` R3; wiring `05-review.md` §12 item 1) | the Review *behaviour* prompt, waiting on Q-R2. Until it lands the machine side's morphology is the detector's, and the page says so |
| Re-cutting the ground truth by hand | Q-D2 option (b), explicitly not taken |
| Settings › Analysis defaults' `iou` / `onset` keys | §4.6 says changing them is a versioned act; read them, do not move them |

## Acceptance — the researcher's walk

1. Explore › Corpus, `M2_aug_concat_fs1.mat`, *colour by · disagree*, one run picked → the map shows only
   places that run covered and a human reviewed; the bar reads the two cells and the not-comparable count.
2. Discovery › Runs → the scoreboard shows two precision figures per run, each with its rule on hover and
   the denominator's width distribution for (c).
3. Discovery › Compare, *human annotations* as A → the overlap is no longer *both 0* by construction; the
   breakdown table is below it.
4. Judge five detections of that run in Review (`L`) → refresh → the cells move by exactly those five.

## The gate

`npx tsc -b` + `npm run build`; `webui/smoke.py` on a fresh `--sandbox` bridge, alone, finishing on the
**full** walk; `pytest -n 4` against the baseline in `README.md` (re-measure; compare failure sets).
`test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers` already fails under
`webui/.venv` before you touch anything; if your change makes it pass or changes how it fails, say which.

Evidence into `webui/screenshots/fixup/X/`.

## Report

`docs/prompts/fixup/reports/X-divergence-read-properly.md`: the old *disagree* count beside the new cells
for three channels; both precision figures for every run in the sandbox session with their denominators;
the breakdown for one run; what the morphology column could and could not show; items left; out-of-scope
files touched; the gate. Then close `05-discovery.md` D2 in place.
