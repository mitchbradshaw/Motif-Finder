# Report — Fixup AH: a blind interesting / not queue over the model's test windows, and the page that reads it

Run 2026-10-06 on `main`, in the main checkout. Commit prefix `fixup-ah:`. **Both halves were built** — the sample and
the queue, and the Results view with the comparison line; nothing was split off. Every bridge ran `--sandbox` on my own
port (**8781** for the walk, **8782** for the gate) with a **private client build of `git archive HEAD`**; the shared
`webui/client/dist` was not rebuilt, no researcher bridge was running, the real `DATA/` was only read (`mode=ro`), and
`M4_aug_concat_fs1.mat`, window set 1 and run 79 were not touched.

## In plain words first

The B.2 model was trained on piles a clustering made, with no human labels. To find out whether what it calls
interesting is what *you* call interesting, you label some of its test windows **without seeing its answer** — like
marking an exam paper with the student's name and the answer key covered — and the page compares the two.

- **Models › Results** now lists the B.2 runs. Open one, press **Label test windows blind** (default 1,000 windows, a
  tenth shown twice), and Review opens on the first card.
- **The card** shows the window's raw trace in millivolts, shaded, with one window-length either side, and says how
  long it is ("a 10-minute window · 600 samples at 1 Hz"). Nothing else: no model call, no cluster, no score, no
  recording or channel, no time in the recording, no earlier label — and when a window comes back a second time your
  first answer is hidden. Keys: **I** interesting, **N** not interesting, **U** can't tell, **A** artifact, **Z**
  undo, arrows to move. Your answers are ordinary human labels; you can stop and come back, and it resumes.
- **Your first label freezes the pool's cut and mapping** (a blind label is a score): Analyse shows a red banner and
  Launch refuses a different cut.
- **Results › against a blind human** then shows, for each exam separately, how often the model agrees with you (with
  an error bar), kappa, how often **you agree with yourself** on the repeated windows (the ceiling — no model can
  beat that), per cluster (how many of each pile you called interesting: the check on your mapping), per scale, per
  recording, and what "agreeing by luck" would score.
- **The comparison line**: the old manual-label CNNs, scored on the same windows, **one row per scale** (1, 10, 30 min),
  the 1- and 30-minute rows marked *outside its training scale*, with a warning that they were probably trained on
  some of these very windows (so each is also scored on the windows with no earlier label).

**The walk here used PLACEHOLDER labels, not yours:** a rule ("interesting when the shaded window swings at least
1 mV peak to peak") pressed the keys. Every number below is therefore a demonstration that the machinery works, not a
finding. The real labelling is yours, in project mode (§8).

## 1. The walk with placeholder labels (sandbox, port 8781, run 399)

`webui/screenshots/fixup/AH/walk.txt`, screenshots `01`–`13`, `scores_run399.json`. **0 browser console / page errors.**

**The run.** A fresh sandbox; AF's six sets rebuilt (M2_aug 690,837 / 69,021 / 22,947; M2 271,184 / 27,104 / 9,024);
AG's chain at its defaults (pool key `712f477b262b2fd8`, 60,000; centre + linear, floor 0.1 mV; Ward on 20,000); the
cut at **k = 8 with AG's placeholder mapping** (clusters 1 and 2 interesting, 3–8 not); the forest: **run 399**
(diagnostic accuracy 0.66 — the same numbers as AG's run 400). 745 s end to end.

**The sample** (N = 100, 10 % shown twice, seed 0): 50 per exam, then evenly per predicted cluster — 7 · 7 · 6 · 6 · 6 ·
6 · 6 · 6 for clusters 1–8 in each exam. Weights (windows predicted / drawn) run from 67.5 (exam (i) cluster 5:
405 / 6) to 523.7 (exam (ii) cluster 8: 3,142 / 6) — rare piles are over-represented on purpose and the reweighted
line corrects for it. By scale: exam (i) 7 × 1 min · 16 × 10 min · 27 × 30 min; exam (ii) 14 · 17 · 19 (the scale mix
follows the clusters, not a quota). **10 windows shown twice**, the closest pair 30 showings apart; 110 showings.

**Labelling.** Card `03_blind_card.png`: its payload keys are only the window's length, rate, bounds and trace; no word
on the card names a cluster, prediction, class, exam or channel; no queue rail and no model pill are drawn. 40
answered by keyboard → left → reopened from Results: **it resumed at showing 41 with 40 judged** (`05_resumed.png`).
The rest answered (`06_queue_done.png`): 65 interesting, 45 not. **How long a window takes:** the machine round trip
(keypress → answer written → next card painted) is about 0.1–0.2 s, so the time per window is the labeller's own; at
the ticket's five seconds, 1,000 windows (1,100 showings) is about an hour and a half. A person's pace is not measured
here — the queue measures it once you label (`pace_s` on the page).

**Against a blind human (placeholder labels — meaningless as results):**

| | exam (i) later block | exam (ii) unseen channels |
|---|---|---|
| answered interesting / not | 50 | 50 |
| macro F1, model vs "human" [95 % CI] | 0.449 [0.316, 0.581] | 0.396 [0.253, 0.525] |
| the model's interesting: precision / recall | 0.57 / 0.28 | 0.57 / 0.25 |
| kappa [CI] | −0.01 [−0.24, 0.22] | −0.07 [−0.28, 0.14] |
| label-shuffle null mean · p | 0.450 · 0.59 | 0.435 · 0.84 |
| self-agreement | 6 pairs, 100 % | 4 pairs, 100 % |

The placeholder rule is a swing threshold, so it calls 24 of 27 thirty-minute windows interesting and 0 of 7
one-minute ones in exam (i) — a scale effect of the rule, not of the model; self-agreement is 100 % by construction.
The per-cluster rows (`07`, `08`) show the check working: e.g. exam (i) cluster 2 (mapped interesting) got 2 of 7
"interesting", cluster 6 (mapped not) 5 of 6.

**The comparison line** (`09_comparison_line.png`; 93 s for 100 windows × 7 checkpoints on CPU): 18 scored rows
(6 models × 3 scales) plus `fusion_cnn` refused. 25 of the 100 answered windows overlap an earlier human label.

**The freeze fired** (`11`–`13`): after the first label, the run's results say exam (i) / (ii) `scored`; Analyse's
Shape clustering page (the chain re-run on that pool) shows *"The cut and the mapping are frozen — run 399 … k = 8"*
and locks the classes; Launch shows the frozen card; a template at k = 9 on the same pool is refused —
**HTTP 409** *"run 399 already has a test score on this pool at k = 8 …"*, and its before-launch check is red.

## 2. Which reference models could be scored at which scale, and why not otherwise

| model | 1 min | 10 min | 30 min | why / note |
|---|---|---|---|---|
| `GASF_cnn`, `GADF_cnn` | scored, *outside its training scale* | scored | scored, *outside* | an n × n Gramian image of the raw window, resized to 224 — nothing resampled; no fixed-sample parameter, but each pixel covers n / 224 samples |
| `recurrence_cnn` | scored, *outside* | scored | scored, *outside* | **not scale-free**: its embedding (m = 3, τ = 4 samples) is fixed in samples — said on its rows |
| `fusion_cnn_2`, `fusion_cnn_3` | scored, *outside* | scored | scored, *outside* | the two-class fusion checkpoints; fusion carries the recurrence image, so not scale-free either |
| `fusion_cnn` | **refused** | **refused** | **refused** | one output class — its softmax is 1.0 for every window (AB's finding); the row says so |
| `catch22_rf_prelabeled` | scored, *outside* | scored | scored, *outside* | catch22 features are length-dependent; fed the raw window as it is |
| `fusion_prediction_cnn` | not listed | | | 14 classes: a different question's model |

**The usable fusion checkpoint, found** (`fusion_checkpoints.txt`): `fusion_cnn_2.pth` and `fusion_cnn_3.pth` both have
two classes, and on 120 human-labelled 10-minute M2_aug windows (read-only) class 0 is *interesting* for both, as for
GASF and recurrence: AUC 0.979 and 0.970 (GASF 0.987, recurrence 0.984). Those windows were very likely in their
training data — an upper bound — but it settles the orientation. Which of the two is "the" fusion model is recorded
nowhere, so both are scored (question 2 below).

**Contamination** is stated on every row and in a banner; each cell gives the score on **all** answered windows and on
those overlapping **no earlier human label** (any `annotations` / `window_verdicts` span not from a blind queue;
every M2_concat_fs1 window qualifies).

## 3. What was built

| where | what |
|---|---|
| `Working/training/blind.py` (new) | `draw_sample` (test + exam only, seeded, N ≤ 2,000 split equally between the exams then evenly per predicted cluster, a cluster smaller than its share taken whole, weights kept, a fraction shown twice at least a quarter of the queue apart, a seeded shuffle); `make_queue` (the sample on disk beside the run's results + `artifacts` rows **before** the first label; the same queue on a second press; a different sample refused, `SampleFixed`); `resolve_items` (where and how long — nothing else); `write_showing_verdict` (an `annotations` row over the window's exact span, `source = 'blind_test_review'`, a note naming the queue and run, linked to its showing); `mark_scored` (the first label marks the exam `scored` in the run's results — what `shape_forest.frozen_for` reads); `score` (per exam; §1's figures plus reweighted ones, per cluster / scale / recording); `disagreements`; the comparison line (`reference_image` / `reference_tensor`, `reference_probabilities`, `run_reference`, `score_reference`, `contaminated`) |
| `Working/training/metrics.py` | `cohen_kappa` |
| `Working/database/schema.py` | additive: `review_queues`' CHECK names `blind-test` / `test window` (AD's idempotent, backed-up rebuild, the marker moved to the new kind); `blind_test_labels` (showing → annotation; a link, not a verdict store) |
| `Working/review/queues.py`, `verdicts.py` | the kind (`blind-test`: unit `test window`, writes `annotations`, blind) and its dispatch |
| `webui/server/blind_routes.py` (new), `app.py` | `POST/GET /api/models/b2/runs/{id}/blind`, `…/blind/disagreements`, `POST …/blind/reference` (a job); the card's two reads `/api/models/b2/blind/{qid}` and `…/showings/{i}`. The answer goes through Review's own verdict route |
| `webui/server/review.py` | a test-window row carries no thumbnail (a sparkline list would let the eye find the repeat) |
| `webui/client/src/review/BlindTest.tsx` (new), `review/index.tsx` | the labelling page |
| `webui/client/src/models/B2Blind.tsx` (new), `ResultsPage.tsx`, `B2Launch.tsx`, `api/blind.ts` (new) | Results' B.2 list and the blind view; Launch's B.2 runs link to it |
| `webui/smoke.py` | a `select` action (appended alone, `c104d32`) |
| `webui/smoke_pages/zzzzzzz_ah_blind_test.json` (new) | six states (§5) |

**Rule 5:** the human's answers are `annotations` rows; the model's calls stay in the run's parquet; the sample file
(machine-made, with the predictions) is on disk only. A test pins that a label writes no `detections` /
`adjudications` row and that no note names a cluster or probability. **Found and fixed on the walk:** between a
keypress and the next card loading, the previous window's trace was drawn under the new showing number for a moment —
an answer pressed then would have gone to the window the eye was not on; the card is now keyed by its showing
(`c7f749c`).

## 4. Defaults I chose, and why

| default | why |
|---|---|
| N split **equally between the two exams**, then evenly per cluster | the figures are per exam, never pooled; an exam with few windows would otherwise have a handful |
| repeats at least **a quarter of the queue** apart | "far apart" made concrete; 10 % repeats of 1,000 → the second showing ≥ 250 windows later |
| the queue's words: **I / N primary, U (can't tell) and A secondary**; `seed` refused | Q45's five words; can't tell = `unsure`. Scores count interesting / not only; unsure and artifact are left out and counted |
| hidden: recording, channel, time in the recording | none tips the model's answer, but each can recall an earlier label of the same stretch; the queue rail is not drawn (a thumbnail would expose the repeat) |
| the first label freezes, **and undo does not unfreeze** | a window seen blind was still seen |
| label-shuffle null = your answers permuted against the model's fixed calls (1,000×) | the model is fixed here; retraining under shuffled cluster labels would test the clustering, not this check |
| the comparison line scores the **whole sample** once (a job) | 1,000 windows × 7 checkpoints is minutes on CPU (100 took 93 s); the table then reads it per scale and exam |
| context = one window-length either side; the y axis in absolute mV | the ticket's "true units with context either side" |

## 5. The gate

1. **`npx tsc -b` clean; `vite build` green** — into private directories from `git archive HEAD`.
2. **`pytest -n 4` (conda, 10 m 22 s): 2,375 passed, 31 skipped, 0 failed** — the failure set is empty.
   `tests/test_import_boundaries.py` passes and `test_training_blind.py` pins that `blind.py` imports no UI library.
3. **Route tests (`webui/.venv`, every `tests/test_webui_*.py`, `-n 4`):** **442 passed, 3 xpassed, 1 failed** — the standing
   `test_the_scoreboard_cells_are_the_tables_own_numbers`. My 3 route tests pass.
4. **Smoke, one full walk on a fresh `--sandbox` bridge (port 8782, private build of HEAD), quiet machine:** 
   - The process check before the walk found no other bridge, smoke or pytest; the bridge was started and the walk
     begun after its *stumpy JIT warm* line. The working tree held no other session's edits.
   - **663 screenshots, 5 failures — exactly the five standing:** `discovery.runs--default` and the four Settings
     registration Check states. **0 unexpected server tracebacks, 0 browser console or page errors.**
   - **All 6 AH states pass:** a small B.2 run of the walk's own (300 per scale, k = 2, a placeholder mapping, Train
     model → Train locally); *Label test windows blind* opens a card whose DOM and payload carry no cluster, class,
     probability, score, weight, exam, role or model key, no "cluster" / "predict" text, no model pill, reveal card or
     evidence rail; label 10, leave, reopen → resumes at 10 judged, finish 30; against a blind human and the comparison
     line (the CNNs scored as a job, `outside its training scale` rows present); the freeze banner in Analyse; Launch's
     frozen card. Evidence: `webui/screenshots/fixup/AH/smoke/`.

## 6. Items left

- **The real labelling** (yours, project mode, §8), and with it the real figures. Nothing in this report is a finding.
- The comparison line is scored on demand (a button, a job), not automatically when the queue is made.
- The model's *P(interesting)* is not used by the blind figures (they use its class); a threshold curve against the
  blind human is a possible later view.
- A five-category blind mode in the cluster names was set aside (2026-10-05); the queue's `verdict_options` and the
  sample's cluster column leave room for it.
- Results › Compare still reads paired runs only; B.2 is read on its own Results view.
- The researcher's project database gets the `review_queues` rebuild (backed up first) the next time a project
  bridge opens it, as with AD.

## 7. Questions for you

**1. How many windows, and what to do with "can't tell"?** *In plain words:* the more windows you label, the narrower
the error bars, but each costs about five seconds. The walk's 50 windows per exam gave an interval of about ± 0.13 on
macro F1; scaled by the square root of the count, 1,000 (500 per exam) gives about ± 0.04–0.05 and 600 about ± 0.06
(a rough scaling, not a measurement). "Can't tell" answers are left out of the scores and counted, so a lot of them shrinks the sample.

- **(a)** 1,000 (the default, ~1.5 h with the repeats); **(b)** 600 (~55 min), as the earlier note suggested;
  **(c)** 2,000 (~3 h).

*My recommendation:* **(a)**, in two or three sittings — the page resumes.

**2. Which fusion checkpoint is "the" fusion model?** *In plain words:* the folder holds three fusion files. One is
broken (one output), two work and agree on which output means interesting, but nothing records which one you trained
last or meant to keep.

- **(a)** keep both rows (as built); **(b)** tell me which, and the other is dropped; **(c)** `fusion_cnn_3` (the
  larger file, same date).

*My recommendation:* **(a)** until you remember; it costs one table row.

**3. Should an artifact answer count as "not interesting"?** *In plain words:* if a window is an electrode artifact,
it is arguably "not interesting" — but counting it that way rewards a model for ignoring artifacts it was never told
about. As built it is left out and counted.

- **(a)** leave out and count (as built); **(b)** count as not interesting.

*My recommendation:* **(a)**.

## 8. To label for real — PROJECT mode on the real database

Your bridge writes to the real database in this mode (a backup is written first, and the `review_queues` table is
rebuilt once to learn the new queue kind, backed up separately).

1. `webui\start.ps1` (PROJECT mode on 127.0.0.1:8765). Do AG Part 2 §8 and Part 3 first if not done: the six sets, the
   chain, **your** cut and mapping, *Train model* → *Train locally*.
2. **Models › Results** → *B.2 · cluster labels · trace shape* → your run → **against a blind human**.
3. **Label test windows blind**: windows 1000, shown twice 10 %, seed 0 → Review opens.
4. Label with **I / N** (U can't tell, A artifact, Z undo). Close any time; Results › *Open the queue in Review* resumes.
   **Your first answer freezes the cut and the mapping.**
5. Back on Results: the figures per exam; **Score the comparison line** (a few minutes for 1,000 windows); step through
   the disagreements.

## 9. Files

**In the ticket's area:** `Working/training/blind.py`, `webui/server/blind_routes.py`, `webui/client/src/review/BlindTest.tsx`,
`webui/client/src/models/B2Blind.tsx`, `webui/client/src/api/blind.ts`, the smoke file, tests
(`test_training_blind.py`, `test_webui_blind.py`), evidence.

**Outside it, and why:**

| file | why |
|---|---|
| `Working/database/schema.py` | the new queue kind in the CHECK (AD's rebuild, re-pointed) and the link table |
| `Working/review/queues.py`, `verdicts.py` | the kind's dispatch (the AD pattern) |
| `Working/training/metrics.py` | `cohen_kappa` beside the other scores |
| `webui/server/app.py`, `review.py` | one `include_router`; no thumbnails on a test-window row |
| `webui/client/src/review/index.tsx`, `models/ResultsPage.tsx`, `models/B2Launch.tsx` | routing to the new pages; Results lists B.2 runs; Launch's B.2 rows link to Results |
| `webui/smoke.py` | the `select` action |
| `docs/rq_roundA/RQ1-…`, `docs/prompts/fixup/README.md` | the RQ rule and the Stage 6 row |

`shape_forest.py` was **not** changed: the freeze reads the results file exactly as AG wrote it, and the first label
writes what it reads. No other session's file was touched.

**Commits:** `c764732` (red) · `562f34c` (core + bridge) · `53219df` (client) · `c104d32` (smoke action) · `c7f749c`
(card fix, smoke states) · the report commit.
