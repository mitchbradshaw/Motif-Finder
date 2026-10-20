# A MiniRocket classifier of your own verdicts (R4), 2026-10-20

**Read this before using the model, or quoting R4.** The code is `scripts/rq1b_minirocket.py`; its docstring states
each rule once. The model, its manifest and every held-out score are in
`DATA/derived/models/rq1b_minirocket/20261020-2343/` (`model.joblib`, `manifest.json`, `predictions.parquet`). (The 20261020-2332 folder is the first run, whose saved model is the events-only variant; its evaluation is the same.)

## In plain words

You judged about 2,600 events and some 12,000 windows. For each one the computer takes a short picture of the signal:
the span itself plus a quarter of its length on each side, in millivolts, squeezed to 512 points. MiniRocket turns
that picture into about 5,000 yes/no-ish answers to "does this little pattern occur here", a fingerprint. Four plain
measures come along with it: how long the span is, how big, how noisy, and big-over-noisy. A simple linear model then
learns which fingerprints you call interesting.

The fair test is a recording the model has never seen, like an exam on a chapter that was never taught. Train on four
recordings, ask about the fifth, and repeat so that each recording takes a turn as the exam.

**The answer:** on recordings it never saw, it agrees with you on about 9 in 10 candidates. Ranked by its score, an
interesting candidate sits above a not-interesting one 97 times in 100 (AUC 0.97). That is far better than counting
how many detectors agree (AUC 0.86 on the same candidates), and far better than size and noise alone (0.90).

## What it learned from

- **Classes: interesting (with seed) versus not interesting.** No shape classes: not one verdict carries a class
  label, and RQ1b's shape classes need named, verified families (decision of 2026-10-18), not clusters nobody checked.
  "Unsure" (108) and "artifact" (168, which Review says is kept out of training) are left out.
- **Only your own judgements.** Review's carried copies of a verdict (34,968 rows, the same events again in other
  runs) are left out, or one judgement would count many times. M4_aug (the exam) and the Fig2A pieces are left out
  (65 rows).
- **One event once.** 177 duplicate spans merged; 133 spans dropped because two of your verdicts on one event
  disagree; 26 spans left out for missing samples.
- **What was used:** 2,456 events and 3,000 windows (1,500 per class drawn from the old 10-minute labels and the
  blind test; RAM tonight did not allow all 12,000).

| Recording (group) | Events | Windows | Interesting | Not |
|---|---|---|---|---|
| M2_aug | 1,270 | 2,917 | 2,334 | 1,853 |
| M2_concat | 253 | 83 | 102 | 234 |
| CO_fs2 | 256 | 0 | 88 | 168 |
| LM_fs2 | 294 | 0 | 139 | 155 |
| L_LM_Jul_26_J (10 Hz and 2 Hz, one group) | 371 | 0 | 157 | 214 |
| Mushroom_260720 | 12 | 0 | 11 | 1 |

## How well it does on recordings it never saw

Leave one recording out, scored on the 2,456 events (windows only ever help train):

| Variant | Balanced accuracy | AUC | Precision (interesting) | Recall (interesting) |
|---|---|---|---|---|
| **events + windows · MiniRocket + side (the saved model)** | **0.92** | **0.97** | 0.93 | 0.92 |
| events · MiniRocket + side | 0.91 | 0.97 | 0.93 | 0.90 |
| events · MiniRocket only | 0.91 | 0.97 | 0.94 | 0.90 |
| events · side features only | 0.78 | 0.84 | 0.80 | 0.80 |

Each recording held out in turn (the saved model's variant):

| Held out | Events | Balanced accuracy | AUC |
|---|---|---|---|
| CO_fs2 | 256 | 0.95 | 0.99 |
| LM_fs2 | 294 | 0.96 | 0.99 |
| L_LM_Jul_26_J | 371 | 0.93 | 0.98 |
| M2_aug | 1,270 | 0.89 | 0.95 |
| M2_concat | 253 | 0.91 | 0.96 |

Five folds by channel give the same picture (balanced accuracy 0.92, AUC 0.97).

**The honest population.** Your two stratified queues (25 and 28) are random draws from what the detectors propose.
On those 1,689 candidates alone:

- the saved model has balanced accuracy 0.92 and AUC 0.97;
- size and noise alone give 0.85 and 0.90.

The other judged events, mostly seed-search matches of a few shapes, score lower (AUC 0.89–0.91).

**Does it judge the shape, or only recognise which detector proposed the span?** Detectors outline spans in typical
ways, and their precision ranges from 7 % to 96 %. Within each detector family (queue candidates, events-only
variant), it still separates interesting from not:

| Family | Candidates | Interesting | Balanced accuracy | AUC |
|---|---|---|---|---|
| deconvolved_troughs | 495 | 20 | 0.77 | 0.95 |
| OASIS_Deconvolution | 377 | 200 | 0.85 | 0.93 |
| Wavelet_detection_prototype | 116 | 13 | 0.79 | 0.95 |
| BEADs_invert_detect_v1 | 111 | 79 | 0.81 | 0.91 |
| symbol_search | 99 | 50 | 0.76 | 0.88 |
| wavelet_encoded | 99 | 87 | 0.94 | 0.99 |
| drop_detection_v5 | 85 | 78 | 0.90 | 0.96 |
| signal_threshold | 51 | 19 | 0.74 | 0.92 |
| noise_threshold | 32 | 10 | 0.86 | 0.91 |

**Against detector agreement** (how many families fire on the stretch: context only, the model never sees it), on
the same held-out candidates:

| Held out | Candidates | AUC, detector agreement | AUC, MiniRocket |
|---|---|---|---|
| CO_fs2 | 256 | 0.86 | 0.99 |
| LM_fs2 | 257 | 0.90 | 0.99 |
| L_LM_Jul_26_J | 236 | 0.87 | 0.98 |
| M2_aug | 687 | 0.83 | 0.96 |
| M2_concat | 253 | 0.88 | 0.96 |
| all | 1,689 | 0.86 | 0.97 |

## What it means, and what it does not

- **It answers R4's first question:** a MiniRocket classifier trained only on your verdicts carries to recordings,
  rates and species it never saw (1 Hz and 2 Hz; V and mV).
- **Your windows tie with events alone** (AUC 0.971 against 0.973; balanced accuracy and recall a little higher).
  The saved model uses them, as you asked.
- **It judges candidates, not a free scan.** It was trained on spans the detectors proposed, each with its own
  context. Scanning a raw recording with sliding windows is a different input and would need its own test.
- **The queues are stratified**: they oversample detector agreement and the selective detectors. The scores above are
  on that mix. The false alarms per hour on a detector's raw output would be read by weighting the strata, as the
  candidate-event estimator does.
- **The labels are yours, with your misses** (about 11 % per look, `rq1b-candidate-events.md`). Some "false alarms"
  of the model will be your misses.
- **Not yet tested on M4_aug,** the held-out exam: it has no labels, and it is to be used once.

## Using the model

```python
import importlib.util
spec = importlib.util.spec_from_file_location("mr", "scripts/rq1b_minirocket.py")
mr = importlib.util.module_from_spec(spec); spec.loader.exec_module(mr)
model = mr.load_model("DATA/derived/models/rq1b_minirocket/20261020-2343/model.joblib")
M, side, keep = mr.extract(conn, spans)          # spans: recording_id, start, end (samples)
p = mr.probability(model, M[keep], side[keep])   # P(interesting); the ridge's own cut is mr.decision(...) > 0
```

## Next steps

1. Score the 1.6 M unjudged candidate events, and blind-check a sample of the top and the bottom. That turns the model
   into a filter for the next queues.
2. Give each accepted event a shape in a family-grid pass. That gives RQ1b its named classes, and a second model.
3. The M4_aug exam, once.
4. The model as a block in the app (Models › Registry): after the demo, not before.
