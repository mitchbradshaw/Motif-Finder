# RQ1 — Do cluster-derived labels produce a classifier that generalises better than manually-derived labels?

**Status (2026-10-03): not answerable.** No block reads a human label, and Models, Training and Jobs are fixture pages.
Owners: fixup `AA` then `AB`. **The researcher's first priority after the fixups is training a model.**

## In plain words

You can teach a computer to sort windows of signal in two ways. You can show it windows *you* sorted (interesting / not
interesting). Or you can let a clustering algorithm group similar-looking windows first (say sharkfin, trough, drop,
noise) and teach the computer those groups. Then give both the same exam on data neither has seen. The question is
which one does better on the exam.

## What is known

- **The cluster arm runs on one span** (readiness 2026-10-02): `windows_model` = `preprocessing.window_matrix` →
  `catalogue.cluster` → `catalogue.classifier`. *"3 clusters · sizes 42, 6, 72"*, *"holdout accuracy 0.80"*. **That
  holdout is a random 25 % of the same two hours**, so it says nothing about generalisation.
- **There is no manual arm.** `catalogue.classifier` takes a `Grouping`, and only `catalogue.cluster` makes one.
- **Applying the cluster template per channel is the wrong operation.** Cluster 1 on one channel is not cluster 1 on the
  next. RQ1 needs **one clustering over the pooled windows of several channels, fitted on training windows only**
  (`RESEARCH_RUNBOOK.md` Q1).
- **Existing models** (`MODELS/`): GADF, GASF, recurrence and fusion CNNs, plus `catch22_rf_prelabeled.joblib`, all
  trained on the human interesting / not-interesting set.
- **Human labels in the database:** 11,234 windows of 600 samples on a 200-sample stride (`interesting` 2,333 ·
  `not_interesting` 8,773 · `artifact` 128). There are also 31 Excel-catalogue spans and 4 hand-drawn spans, which run
  from 126 to 324,000 samples.
- **The held-out recording** `M4_aug_concat_fs1.mat` is refused by every route (423), as designed.
- `window_sets` has 0 rows. *Save window set* has no caller.

## Decisions already made (`docs/prompts/fixup/QUESTIONS.md`)

- **Q41 (2026-10-03):**
  - **Classes:** binary, `interesting` (with `seed`) vs `not_interesting`. `artifact` is excluded and counted.
  - **Label sources:** labels can come from **any human span of any length**.
  - **Matching rule:** a window takes a label only if it **wholly contains** at least one labelled span, and every span
    it wholly contains agrees. Windows whose contained spans disagree are left out and counted.
  - **Unlabelled is unlabelled.** Time nobody labelled is never "not interesting".
- **Q42 (2026-10-03):**
  - **Fair comparison:** both arms are trained identically, and only the label source differs.
  - **Cluster arm:** a window-matrix dendrogram clustering at a chosen cut. Its classes may be morphological.
  - **Yardstick (A), primary:** translate the cluster classes to interesting / not (noise → not), with the table fixed
    in the recipe before any test score exists. Score both arms on exams (i) later time, (ii) unseen channels and
    (iii) the held-out recording once after the freeze. Report each exam separately, never pooled.
  - **Yardstick (B), validation:** the researcher labels a sample of windows **blind** in the cluster vocabulary. This
    happens later, in the Review-behaviour prompt.
  - **The cut** is chosen on training windows only, frozen, and refused a change once a test score exists.
- **Round 10 (2026-10-03):**
  - **Q-W1:** a window inside a `not_interesting` span is `not_interesting`; a window inside a longer `interesting`
    span is unlabelled.
  - **Non-overlapping windows:** training windows sit on the 600/200 grid but no two overlap. The set is a stride-600
    subset, with the offset chosen to keep the most labels; what's dropped is counted.
  - **Q-W2:** one clustering over the pooled training windows of all training channels. Training is one mushroom;
    exam (iii) is a different one.
  - **Q-W4:** the existing `MODELS/` are a reference line, not an arm.
- **PRD one-way door:** machine labels never enter the human annotation store.

## What is still needed

| Step | Owner |
|---|---|
| `catalogue.manual_labels` block (`WindowSet → Grouping`) implementing Q41's containment rule | `AA` |
| *Save window set* on every WindowSet row | `AA` |
| Pooled clustering across channels, fitted on training windows only | `AB` |
| Paired training job: two arms, blocked split with a gap ≥ one window, RF baseline, label-shuffle null, paired difference | `AB` |
| Models › Launch / Results / Compare reading real jobs | `AB` |
| CNN arm on the cluster; Jobs bringing results back; SLURM script without baked Windows paths | `AB` / later |
| Blind labelling mode in Review with the cluster vocabulary as buttons (yardstick B) | Review-behaviour prompt, later |
| Non-overlapping training window set; labels on spans longer than a window | `AA` |

## How it gets answered

Follow `RESEARCH_RUNBOOK.md` Q1:

1. Tune `windows_model` on a span.
2. Save a window set over the training channels.
3. Launch both arms plus the RF baseline and the label-shuffle null.
4. Read Results and Compare: ΔF1 with CI, McNemar, per class and per channel, and the cluster→class contingency.
5. After the freeze, unlock the held-out recording once.

## Open decisions

None. Q-W1, Q-W2 and Q-W4 were answered 2026-10-03.

## Log

- 2026-10-03 · grilling · file created; Q41 and Q42 recorded.
- 2026-10-03 · grilling · Round 10: Q-W1, non-overlap, Q-W2 and Q-W4 decided; `AA` and `AB` prompts carry them.
