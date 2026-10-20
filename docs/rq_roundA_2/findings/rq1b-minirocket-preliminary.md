# RQ1b, preliminary: can a shape classifier tell an interesting event from a dull one better than detector agreement? (2026-10-20)

**Not yet.** On your 722 blind yes/no verdicts from Review queue 25, a MiniRocket shape classifier ranks events
worse than simply counting how many detector families agree (AUC 0.79 against 0.83). Adding the shape to the count
gives nothing measurable (0.82). This is a preliminary check: it is not RQ1b's family classifier and it is not on
the exam recording.

- **Script:** `scripts/rq1b_minirocket_preliminary.py`. It is read-only on the database and takes 1–3 minutes on
  this machine.
- **Numbers:** `rq1b-minirocket-preliminary-q25-600s.json`, plus `-q25-200s` and `-q25-1200s` for the window-length
  check.
- **Figure:** `rq1b-minirocket-preliminary-q25-roc.png`.

**Re-running on more queues** (for example queue 25 plus the second blind queue, once judged):

    python scripts/rq1b_minirocket_preliminary.py --queues 25 <new id>

- **Queues.** It takes any queues whose `filters_json` lists `detection_ids`.
- **Finding each item.** Each detection is looked up in every candidate-event table under
  `DATA/derived/candidate_events/` for its span, recording and `n_agree`. A detection in no table is counted
  (`not_in_any_table`) and left out, because it has no agreement score. So L_LM_Jul_26_J_raw_fs2 needs its table
  built first.
- **Rates.** The window is in **seconds**, sliced at each recording's own rate (`recordings.fs`). It is then
  resampled to `--fs`, 1 Hz by default, with `scipy.signal.resample_poly`, so a 2 Hz trace is low-passed before it
  is halved. One common rate is needed because MiniRocket needs every window the same number of samples. A 1 Hz
  recording is not touched.
- **Splits.** Time blocks are cut within each dataset. With two or more datasets, a **leave-one-dataset-out** score
  is added, per dataset and pooled.
- **The held-out recording is refused.** M4_aug's table is skipped, and an item on it stops the run.
- **Row order.** Items are sorted into one canonical order. MiniRocket draws its biases from random training rows,
  so a different row order moved AUCs by about 0.01. That is a fair idea of the run-to-run wobble.

## In plain words

Think of 41 smoke alarms in one house. When one goes off, you can ask two questions. First, how many other alarms
went off at the same moment? Second, what did that alarm's own reading look like? The first question is the
**agreement count**. The second is the **shape classifier**: it looks only at the 10 minutes of signal around the
event and learns which wiggles you tend to call interesting.

On your 800 verdicts, the count already sorts the events about as well as the classifier, and slightly better.
Giving the classifier the count as well adds nothing you can measure. So with ~700 labels, the trace's shape alone
does not add information that the detectors' vote lacks.

That is a useful negative, not a dead end:

- **The labels are few.** MiniRocket usually needs thousands of examples per class. 722 is at the bottom of its range.
- **The question is coarse.** "Interesting or not" is exactly what agreement measures well. RQ1b's real question
  is *which kind* of event, and there agreement says nothing.
- **The shape score is not a copy of the count.** At the strictest settings (the bottom-left of the ROC), the shape
  classifier keeps up with the count. Where the count is blind (the selective-detector strata), the two are level.

**For the slide:** "On 722 blind verdicts, a shape-only classifier reaches AUC 0.79; detector agreement reaches 0.83.
Shape does not yet beat the vote. The family classifier needs class labels and more examples, and that is the next
step."

## What was done

- **Labels.** The latest adjudication on each of the 800 queue items: interesting 329, not interesting 393. Left
  out: unsure 46, artifact 19, seed 13. All 800 were judged.
- **Windows: 600 s centred on each event** (1 Hz, so 600 samples), shifted inside the recording at its ends,
  z-normalised per window as `Working/Catalogue/minirocket.py` does. No window had gaps.
  - **Why 600 s.** On these 722 events the length runs p10 15 s · p25 40 s · median 400 s · p75 607 s · p90 717 s.
    It is bimodal: a cluster of short spans (troughs, drops) and a cluster at about 10 minutes (the windowed
    detectors).
  - 600 s holds three quarters of the events whole and gives the short ones context. It is also the scale you judge
    at in Review.
  - The 200 s and 1200 s runs below check that the answer does not hinge on this choice.
- **Features and model.** aeon MiniRocket through `minirocket.fingerprint_matrix`: 9,996 features, seed 0, fitted on
  each fold's training windows only. Then standardise + `RidgeClassifierCV` (alpha 0.1 to 10⁵).
- **Split: blocked by time with a gap.** The 30-day recording is cut into 5 equal stretches of time, all 16
  channels together. Each stretch is tested by a model trained on the others, minus anything within 1 hour of the
  stretch's edges. Every item gets one out-of-fold score. A random split would let a model learn "this hour on this
  channel" from a neighbour of the test event; `RQ1-cluster-vs-manual-labels.md` measured that inflation.
  - A **forward check** trains on the first 80 % of time and tests on the last 20 % (145 items). Its results are
    given beside the main ones.
- **Baselines on the same items.**
  - **Agreement:** `n_agree` from the candidate-event table, used as the score directly (no training).
  - **Event length:** the anchor span's length in seconds, also used directly. It is a hidden confound, shown for
    honesty.
- **MiniRocket + agreement.** A logistic regression on two inputs, the MiniRocket score and `n_agree`. The
  MiniRocket scores it learns from come from an inner blocked CV inside each training fold.
- **Intervals.** Paired bootstrap over items, 2,000 draws.
- **Balanced accuracy thresholds.**
  - MiniRocket: ridge's own zero.
  - Agreement: the count cut with the best training-fold balanced accuracy.
  - Combination: probability 0.5.

## Results

### Main: 5 time blocks, out-of-fold, 722 items (329 interesting)

| Score | AUC [95 % CI] | Balanced accuracy [95 % CI] |
|---|---|---|
| **MiniRocket (shape only)** | **0.79** [0.75–0.82] | 0.70 [0.67–0.74] |
| **Detector agreement (count)** | **0.83** [0.80–0.86] | 0.76 [0.73–0.79] |
| MiniRocket + agreement | 0.82 [0.79–0.85] | 0.77 [0.74–0.80] |
| Event length alone | 0.77 [0.73–0.80] | — |

**Paired differences in AUC:**

| Comparison | Difference | 95 % CI | Verdict |
|---|---|---|---|
| Agreement − MiniRocket | +0.04 | [+0.01, +0.07] | **Agreement is better.** The interval excludes 0. |
| Agreement − (MiniRocket + agreement) | +0.00 | [−0.00, +0.01] | The combination adds nothing. |
| MiniRocket − event length | +0.02 | [−0.03, +0.07] | Shape is not clearly better than event length. |

**Per fold (AUC, MiniRocket / agreement):**

| Fold | Test items | Share interesting | MiniRocket | Agreement |
|---|---|---|---|---|
| 0 | 304 | 47 % | 0.74 | 0.78 |
| 1 | 145 | 53 % | 0.79 | 0.85 |
| 2 | 127 | 46 % | 0.85 | 0.91 |
| 3 | 93 | 40 % | 0.76 | 0.79 |
| 4 | 53 | 25 % | 0.92 | 0.90 |

Agreement leads in 4 of 5 folds. The folds are uneven because the events sit unevenly in time; the first 6 days
hold the most.

### Forward check: train on the first 80 % of time, test on the last 20 % (145 items)

| Score | AUC [95 % CI] | Balanced accuracy |
|---|---|---|
| MiniRocket | 0.82 [0.75–0.88] | 0.70 |
| Agreement | 0.83 [0.77–0.90] | 0.76 |
| MiniRocket + agreement | 0.85 [0.79–0.91] | 0.79 |
| Event length | 0.76 [0.68–0.84] | — |

The same order, with intervals too wide to separate anything (agreement − MiniRocket +0.01, [−0.05, +0.07]).

### Where each score works (out-of-fold, main run)

| Items | n | MiniRocket | Agreement | Combination |
|---|---|---|---|---|
| Agreement strata (1–2 … 9+) | 469 | 0.75 | 0.80 | 0.80 |
| Selective-detector strata (drop v1/v5, wavelet, symbol, BEADs, signal_threshold) | 253 | 0.74 | 0.74 | 0.72 |

Agreement wins where agreement varies by design. In the selective-detector strata, events are chosen for their
detector, not their count, and there the two are level.

### Window length (sensitivity)

The same run with 200 s and 1200 s windows (main split, AUC):

| Window | MiniRocket | Agreement | MiniRocket + agreement | Forward check (MiniRocket / agreement) |
|---|---|---|---|---|
| 200 s | 0.73 | 0.83 | 0.82 | 0.76 / 0.83 |
| **600 s** | **0.79** | **0.83** | **0.82** | 0.82 / 0.83 |
| 1200 s | 0.76 | 0.83 | 0.82 | 0.84 / 0.83 |

600 s is the best of the three, and agreement leads at every length on the main split. The 1200 s forward check
(0.84 against 0.83, on 145 items) is the only place where MiniRocket is ahead, and it is well inside the noise.

## Caveats

- **About 700 labels.** The intervals are ±0.03 on AUC, and the classifier is starved. With MiniRocket's ~10,000
  features and 720 rows, ridge's regularisation does most of the work. A few thousand verdicts, which you have
  offered, would be the fairer test.
- **The sample is stratified, not representative.**
  - 100 items per agreement level, plus 50 per selective detector. That flattens the agreement distribution against
    the population, where levels 3–8 dominate.
  - It over-represents the selective detectors. drop_detection_v1 was 100 % interesting here, wavelet 93 %.
  - So these AUCs describe *this sample*, not the 1.5 M events. They are not weighted by the stratum weights.
  - The earlier 0.87 for agreement was measured on 133,556 inherited, mostly window-level labels. 0.83 here, on blind
    event-level verdicts, is the fairer figure.
- **Event length is a confound.** Interesting events here are mostly ~10-minute spans; dull ones are often short.
  Length alone scores 0.77.
  - A 600 s window centred on a 15 s trough is mostly background, so MiniRocket can partly read "how much of the
    window is event" rather than the event's shape.
  - Agreement shares the confound: long spans overlap more families.
- **Agreement was never trained.** It is a fixed count, so it cannot overfit. MiniRocket is refitted per fold on
  about 420–670 items. Only the count's balanced-accuracy cut is learned, on the training folds.
- **The pooled AUC mixes five models' scores.** Each fold's ridge has its own scale. The per-fold table shows the
  same order, so the pooling does not create the result.
- **Your verdicts are noisy.** The candidate-events findings measured an ~11.5 % miss rate per look on "no"s. That
  caps any score's AUC below 1.
- **One recording (M2_aug).** M4_aug was not read: it is the exam.
- **The detectors' own families fed `n_agree`, and some of them learned from your older labels.** The CNN templates
  are counted. The 1-minute CNNs are left out as negative controls. So the agreement baseline is not wholly
  label-free.

## What would change the answer

1. **More verdicts.** The second sample (`rq1b_candidate_events.py queue --real --seed 1`), aimed at the 3–4 and
   5–6 levels.
2. **The real RQ1b question: which family, not whether interesting.** This is where a shape classifier has something
   agreement cannot give. It needs the shape tags on verdicts (none of these 800 carry a `class_label`).
3. **Windows fitted to the event.** For example, the event plus a fixed margin, resampled to one length. That
   removes the length confound and lets shape speak for itself.

## Log

- 2026-10-20 · rq1b-minirocket · first run on queue 25 (800/800 judged; 722 yes/no). Not committed.
