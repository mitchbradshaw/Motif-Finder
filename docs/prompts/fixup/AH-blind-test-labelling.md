# Fixup AH — a blind interesting / not queue over the model's test windows, and the page that reads it

**Third of five for RQ1 version 2. Runs after `AG`; `AI` may run beside it.** Written 2026-10-05; nothing here is run
yet. This is the piece the RQ1 file has called "yardstick (B)" since 2026-10-03, now the main yardstick.

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python `"/c/ProgramData/anaconda3/python.exe"`).
Read `CLAUDE.md`, `docs/rq_roundA/RQ1-cluster-vs-manual-labels.md` ("New scope, version 2"),
`reports/AG-shape-clustering-and-dendrogram.md`, `reports/AB-models-paired-job.md` (§2 Results / Compare,
`reference.py`), `reports/AD-cross-channel-against-chance.md` (how a purpose-made Review queue was built) and
`docs/prompts/fixup/07-review.md`.

Commit prefix `fixup-ah:`. Test-first; the first commit touches only `tests/` and must fail. **`--sandbox` only.**

## In plain words

A model has been trained on piles a clustering made, with no human labels. To find out whether what it calls
interesting is what a person calls interesting, a person has to label the same test windows **without seeing the
model's answer**. This prompt builds that labelling queue, and the Results view that compares the two.

## Decided (the researcher, 2026-10-05). Build these; do not re-open them.

- **A human labels the model's test windows interesting / not interesting, blind** — up to 2,000.
- **That is compared against the model's calls** (its cluster category through the frozen interesting / not mapping).
- **The comparison line is the manual-label models:** fusion, recurrence, GADF and GASF (`MODELS/`). The checkpoint
  versions registered in the site's Registry may be ignored.
- **The verdict vocabulary is fixed** (`QUESTIONS.md` Q45): the five words and a note, no sixth. The queue's primary
  buttons are interesting / not interesting; anything else the card needs maps onto the existing words.
- **Rule 5 holds:** the human's labels go to the human store; the model's calls stay in machine artifacts. Neither is
  written into the other.

## What to build

1. **The sample** (core, `Working/training/`): from a run's test and exam windows, a seeded sample of up to N (default
   1,000, max 2,000) drawn **evenly per predicted cluster**, so rare clusters are not swamped by noise; each window's
   sampling weight is kept so population figures can be reweighted. A fraction (default 10 %) appears **twice**, far
   apart, for self-agreement. Fixed and stored with the run before the first label; the same sample for every model.
2. **The queue in Review:** *Models › Results → Label test windows blind* makes a `review_queues` row (as `L` / `AD`
   did). The card shows the window's trace in true units with context either side, and **nothing else that could tip
   the answer**: no prediction, no cluster, no score, no earlier human label on that span, no order that tracks the
   model (seeded shuffle). The three scales look different in length — show the duration plainly. Keyboard-first: at
   five seconds a window, 1,000 is about an hour and a half; progress and resume across sessions.
3. **Where the labels live:** the human store the paired job already reads (`window_verdicts` / `annotations`, per
   `AA`), tagged with the queue so they can be told apart from the 2025–26 labels. They are ordinary human labels
   afterwards.
4. **Models › Results — "against a blind human":** per exam, never pooled: the confusion of model vs human; precision,
   recall and macro F1 of the model's *interesting* with the block-bootstrap CI (`metrics.py`); Cohen's kappa;
   per-cluster rows (how many of each cluster the human called interesting — the check on the researcher's own
   mapping); per scale and per recording; the label-shuffle null; **self-agreement** on the repeated windows, shown
   beside every figure because no model can be expected to agree with the human more than the human does.
5. **The comparison line, at every scale:** the four manual-label CNNs scored on the same blind-labelled windows. They
   were trained on 10-minute windows, but nothing in them requires 600 samples: a window of any length becomes an
   n × n image that is resized to the network's 224 × 224 input (`Working/Catalogue/cnn/apply_cnn.py`), so a 1-minute
   or 30-minute window can be given to them as it is and a confidence read off. **Whether that confidence means
   anything away from 10 minutes is not known, and the researcher wants to know** ("models that can pick out interest
   at any scale"). So: score each model at 1, 10 and 30 minutes, **one row per scale, never pooled**, the 1- and
   30-minute rows marked *outside its training scale*; say exactly how the window reached the model (as it is, image
   resized — the default — and nothing resampled silently). The recurrence image's embedding (m = 3, τ = 4 samples) is
   fixed in samples and so is not scale-free: say so on its rows. `catch22_rf_prelabeled` likewise, its features being
   length-dependent. **Contamination, stated on the row:** they were very likely trained on M2_aug's 2025–26 labels,
   so a blind window that overlaps one of those labels is not unseen for them; report their score on all windows and on
   the windows with no earlier label (all of `M2_concat_fs1` qualifies). `fusion_cnn.pth` loaded with one output class
   in `AB`; find the working fusion checkpoint or refuse it with the reason.
6. **Step through the disagreements** (model yes · human no, and the reverse), as Compare does today.

## Leave alone

| Leave alone | Why |
|---|---|
| The cut, the mapping, the tree | `AG`; frozen once any score exists — and a blind label is a score |
| The baseline's yardstick-(A) pages | they stay as they are, for the baseline run |
| Registry and its gate | fixture page; not needed here |
| A five-category blind mode in the cluster's own names | considered 2026-10-05 and set aside for interesting / not; leave room, do not build |

## Acceptance — the researcher's walk

1. Models › Results on an `AG` run → *Label test windows blind* → Review opens the queue; a card shows a trace and no
   hint of the model.
2. Label a few dozen, close, reopen: it resumes. Finish (in the sandbox walk, a short queue).
3. Models › Results → *against a blind human*: the model's agreement with CI, kappa, self-agreement, per-cluster rows,
   the null, and the four CNNs' rows with their contamination note.

## The gate

`npx tsc -b` + `npm run build`; `webui/smoke.py` on a fresh `--sandbox` bridge (a test that the card's DOM carries no
prediction, cluster id or earlier label); `pytest` against the README baseline; `tests/test_import_boundaries.py`.
Evidence into `webui/screenshots/fixup/AH/`.

## Report

`docs/prompts/fixup/reports/AH-blind-test-labelling.md`, opening in plain words: the walk with placeholder labels
(said to be placeholders — the real labelling is the researcher's), the sample's make-up, which reference models could
be scored on what, items left, the gate. **Before you report, update**
`docs/rq_roundA/RQ1-cluster-vs-manual-labels.md` per that folder's README. Any question to the researcher: plain
language first, then options, then a recommendation.
