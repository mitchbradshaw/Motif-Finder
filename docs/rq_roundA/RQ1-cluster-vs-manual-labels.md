# RQ1 — Do cluster-derived labels produce a classifier that generalises better than manually-derived labels?

**Status (2026-10-03, after `AB`): answerable on exams (i) and (ii) for the random-forest arms; exam (iii) waits for
the freeze; yardstick (B) waits for the Review-behaviour prompt.** A paired job — one window set pooled across a
recording's channels, arm A the human labels, arm B one clustering of the pooled training windows, the same random
forest for both, a blocked split with a gap, the label-shuffle null — runs from Models › Launch or
`python -m Working.training`, and Models › Results / Compare read it. A first run is below; its cut (k = 6) was a draft
chosen in a sandbox, not the researcher's.

**Scope redirected (2026-10-05, the researcher):** the paired job above is kept and run once as the **baseline**; the
main RQ1 result becomes *cluster the unlabelled pool, validate blind* — see "New scope" below. Two builds are needed
for it.

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
- ~~`window_sets` has 0 rows. *Save window set* has no caller.~~ Fixed by `AA` (below).
- **The manual arm exists (2026-10-03, `AA`, `docs/prompts/fixup/reports/AA-manual-labels-and-window-sets.md`).**
  `catalogue.manual_labels` (`WindowSet → Grouping`) labels each window from `annotations` + `window_verdicts` by Q41 and
  Q-W1; unlabelled, conflicting, artifact and overlap-dropped windows are label −1 and counted, and
  `catalogue.classifier` trains on the labelled windows only and says how many it left out. Template
  **`manual_labels_model`**: 10-minute windows on the labels' 600/200 grid → manual labels → classifier.
- **Coverage it found on three real 24 h spans** (M2_aug, 10-min windows on a 200 step, 430 windows each, labelled-first
  non-overlap): CH1 0–24 h · 18 labelled (4 interesting · 14 not) · 118 unlabelled · 294 dropped for overlap;
  CH5 120–144 h · 13 (4 · 9) · 126 unlabelled · 2 artifact; CH13 360–384 h · 25 (0 · 25) · 111 unlabelled. **About one
  label per hour per channel, and a day of one channel can hold a single class** — so a per-span classifier is a smoke
  test, not an arm. The arms need the whole recording's labels pooled across channels (`AB`).
- **A window must wholly contain a label, so only windows on the labels' own grid take labels from the 10-minute set**:
  `windows_model`'s 1-minute windows can only take `not_interesting` (by lying inside one), never `interesting`. The
  span must start on a multiple of 200 samples too; the labels block says so when no window contains a label it overlaps.
- **Save window set** writes a real `window_sets` row (split and rule, spacing check, coverage per split and class at
  save, recipe hash; bounds on disk, readable with `WindowSet.from_path`). Library › Window sets lists it, with
  coverage now and at save.
- **Non-overlap across the whole dataset, measured:** one grid phase would keep 3,906 of the 11,110 labelled windows;
  labelled-first keeps 10,077. Only 1,135 labels overlap a neighbour at all.

- **The paired job exists (2026-10-03, `AB`, `docs/prompts/fixup/reports/AB-models-paired-job.md`).** `Working/training/`
  (UI-free): pooled set (`window_sets` row + a `window_set_members` row per channel), split blocked by time within each
  training channel (10 blocks: last 2 test, 1 validation, gap ≥ 1 window), arm B = Ward on the pooled TRAINING windows
  only, cut and translation table in the recipe and frozen once a test score exists, RF (300 trees, seed 42) for both,
  200 label shuffles per arm, a 24-hour-per-channel block bootstrap, McNemar, per class / per channel, calibration on
  the validation block; the existing `MODELS/` as a reference line. Exam (iii) is a locked slot; nothing reads M4.
- **First real paired run (sandbox, 2026-10-03):** M2_aug_concat_fs1, train CH1–CH12, exam (ii) CH13–CH16; 10,077
  windows (train 5,267 · validation 751 · test 1,496 · exam 2,563); arm B Ward k = 6 (2,364 / 65 / 465 / 2,371 + two
  single-window specks), majority translation. **Exam (i):** A 0.879 [0.790, 0.918] · B 0.651 [0.559, 0.708] ·
  ΔF1 +0.228 [0.169, 0.290] · McNemar 80 vs 5, p < 0.0001; both far above their nulls (≈ 0.47, p = 0.005, the floor
  at 200 shuffles). **Exam (ii):** A 0.623 [0.587, 0.662] · B 0.597 [0.556, 0.650] · ΔF1 +0.026 [−0.022, 0.071] —
  the interval crosses zero. Both arms find under a quarter of the interesting windows on unseen channels (recall
  0.21 / 0.21). The later time block is far poorer in `interesting` (11 % vs 27 % in training): CH3_A2 holds 91 of its
  158 interesting windows, six channels hold 1–4 each and CH10_C1 none. On yardstick (A) — which is tilted toward arm A — manual labels win clearly on the same
  channels and do not clearly win on unseen channels.
- **Ward splits off single-window outliers first**: k = 2 (5,266 + 1) has silhouette 0.95. The draft cut ignores
  clusters under max(10, 0.5 %) windows.
- **The existing MODELS/ score 0.89–0.97 on both exams**, an upper bound: their training data was never recorded and
  was very likely these labels. `fusion_cnn.pth` loads with one output class and cannot be scored.

- **A surrogate run's spans are no longer counted as detections anywhere** (`T`, 2026-10-03, `docs/prompts/fixup/reports/T-surrogates-one-null-never-a-detection.md`). This
  does not touch the paired training job or its label-shuffle null. It does mean the detection counts Explore shows
  beside the labelled windows are the real runs' only (M2_aug: 576 → 546).

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
  - **Non-overlapping windows:** training windows sit on the 600/200 grid but no two overlap. ~~The set is a stride-600
    subset, with the offset chosen to keep the most labels~~ — **revised 2026-10-03 during `AA`**: the researcher chose
    **labelled-first** (keep every labelled window unless it overlaps one already kept, then fill gaps with unlabelled
    windows), because one phase kept 35 % of the labels and labelled-first 91 % (`QUESTIONS.md`, Q-W1 revised).
    What's dropped is counted.
  - **Q-W2:** one clustering over the pooled training windows of all training channels. Training is one mushroom;
    exam (iii) is a different one.
  - **Q-W4:** the existing `MODELS/` are a reference line, not an arm.
- **PRD one-way door:** machine labels never enter the human annotation store.

## What is still needed

| Step | Owner |
|---|---|
| ~~`catalogue.manual_labels` block (`WindowSet → Grouping`) implementing Q41's containment rule~~ | done, `AA` |
| ~~*Save window set* on every WindowSet row~~ | done, `AA` |
| ~~Pooled clustering across channels, fitted on training windows only~~ | done, `AB` |
| ~~Paired training job: two arms, blocked split with a gap ≥ one window, RF baseline, label-shuffle null, paired difference~~ | done, `AB` |
| ~~Models › Launch / Results / Compare reading real jobs~~ | done, `AB` |
| ~~SLURM script without baked Windows paths~~ (repo-relative, CPU profile for a CPU job) | done, `AB` |
| ~~**The researcher's cut** for arm B (k and translation) on the real database~~ | done 2026-10-05, run 79 (k = 4, frozen on window set 1) |
| CNN arm on the cluster; Jobs › Manifest inbox bringing HPC results back | later (Jobs prompt) |
| Exam (iii), once, after the freeze (Settings › Datasets unlock; the job has a locked slot for it) | researcher, after freeze |
| Blind labelling mode in Review with the cluster vocabulary as buttons (yardstick B) | Review-behaviour prompt, later |
| ~~Non-overlapping training window set; labels on spans longer than a window~~ | done, `AA` |
| A saved window set as an Analyse **source** (§6.9 frame 0b) — a validator change; `AA` stopped at saving and listing | later |
| ~~A window set over **several channels / the whole recording**~~ | done, `AB` (Models › Launch) |

| **New scope:** a pooled set that also holds **unlabelled** windows (> 10,000 across all M2_aug channels, test regions and artifact regions left out) for arm B to cluster — today the set is labelled windows only (`AB` report §3, default 1) | to build |
| **New scope:** blind labelling in Review with the cluster names as buttons, plus "can't tell" (this is yardstick (B), now the main yardstick) | to build |
| **New scope:** the researcher's codebook — one page, each category defined with 2–3 example windows, written before labelling | researcher |

## New scope (2026-10-05): cluster the unlabelled pool, validate blind

**Why.** Under yardstick (A) arm B's answer key is arm A's with some answers changed: the clusters are translated to
interesting / not by majority on the human labels, then scored against the human labels. Pure clusters would reproduce
arm A's key exactly; in `AB`'s draft (k = 6) the two keys differed on 1,187 of 5,267 training windows (23 %). So arm B
can tie or lose but hardly win, and the paired job measures *the cost of cluster labels when marked in the human's
vocabulary* — narrower than the question. It also clusters only windows a human already labelled, so clustering's real
advantage (unlabelled data) is untested.

**The question now.** Do the groups a clustering finds over unlabelled windows match the categories a blind human
sees, and does a classifier trained on them find the windows a human calls interesting?

**The design (the researcher's proposal, with the agreed cautions):**

1. Hold out the test regions (later time blocks, exam (ii) channels) and artifact regions **first**.
2. Cluster > 10,000 windows from all training channels of M2_aug, labelled or not. Name the clusters after looking at
   them (the hope: sharkfin, trough, spike, train, noise — the draft gave two large mixed groups, two small ones and
   specks, so the names follow the clusters, not the reverse; clusters that cannot be named are a finding).
3. Fix the mapping to interesting / not (e.g. noise → not, the rest → interesting) and the codebook **before any score**.
4. Train the classifier on the cluster categories.
5. **Against existing labels:** where a held-out window already has a human label, tabulate predicted category against
   it (the collapsed interesting / not agreement).
6. **Against a blind human:** a sample of about 50–60 held-out windows per predicted category (250–300 in all, about an
   hour), random order, the classifier's answer hidden, labelled in the cluster vocabulary plus "can't tell"; a rule
   for windows holding two things (label the dominant event); 50 labelled a second time for self-agreement.
7. **Keep arm A:** collapse to interesting / not and score both arms on the same held-out windows, so "better than
   manual" still has a comparison.

**Not a score:** the classifier against the cluster labels themselves — that only shows a forest can imitate the
clustering.

**The baseline.** The paired job as built (`AB`) is run once on the real database and reported as the baseline, with
its tilt stated.

## Baseline run: written down before any score (2026-10-05, the researcher)

Recorded before the paired job was launched on the real database. The researcher had seen `AB`'s sandbox draft
(k = 6) and its numbers.

- **Prediction (the researcher's words):** "classifier A will outperform classifier B in accuracy for both exam types
  as classifier B will cluster windows into 'interesting' categories that have been labelled 'not-interesting',
  however it will perform better on exam ii) because the general range of events across a channel will be more varied
  than the range of events at the end of a channel."
- **Primary exam:** (ii), channels never trained on.
- **Primary score:** macro F1 (the average of the per-class F1 scores).
- **Rule for the cut:** the highest silhouette among cuts with two real (non-speck) clusters; the majority
  translation left as proposed.
- **Confirmed by the researcher before launch (2026-10-05):** "it" in the prediction is **arm B** (arm B scores higher
  on exam (ii) than on exam (i)); the cut rule is **at least two** real (non-speck) clusters; a difference counts when
  the **95 % interval of ΔF1 excludes zero**. "Accuracy" in the prediction is read as the primary score, macro F1.

### The baseline result (run 79, real database, 2026-10-05)

Read from `DATA/derived/training/paired_68f57f69_run79/results.json` (recipe `68f57f69`).

- **Window set** `ws_M2_aug_concat_fs1_12tr4ex` v1 (key `158a86478d8df618`): 10,077 labelled windows; train 5,281
  (1,271 interesting) · validation 717 (67) · test 1,549 (134) · exam 2,530 (646). **Exam (ii) channels chosen by the
  researcher: CH4_A2, CH8_B2, CH12_C2, CH16_D2 — one from each of the four mushroom packs (A–D; same species, climate
  and period, grown adjacent).** So exam (ii) here is *an unseen channel of a pack that was trained on*, not an unseen
  pack; `AB`'s draft held out pack D whole (CH13–CH16), and the two are not the same exam.
- **Cut:** Ward, k = 4 → 2 (a speck) / 2,757 / 2,093 / 429; silhouette 0.153. Majority translation, unedited:
  clusters 1, 4 → interesting; 2, 3 → not_interesting. Purity 0.85 / 0.73 (*impure*) / 0.68 (*impure*). The translated
  key differs from the human key on 1,118 of 5,281 training windows (21 %); **979 of the 1,271 interesting training
  windows (77 %) sit in clusters translated to not_interesting.**
- **Classifier:** random forest, 100 trees, balanced class weights, seed 42, on 24 features (catch22 + entropies).
- **Exam (ii), primary:** A 0.793 [0.764, 0.819] · B 0.635 [0.594, 0.674] · **ΔF1 +0.159 [0.120, 0.197]** — excludes
  zero. Interesting: A precision 0.72 / recall 0.66; B 0.58 / 0.32. McNemar 320 (only A right) vs 117. Nulls ≈ 0.43,
  p = 0.005 (the floor at 200) for both. A ahead on all four channels (A 0.70–0.84, B 0.55–0.69).
- **Exam (i):** A 0.884 [0.798, 0.922] · B 0.607 [0.524, 0.662] · **ΔF1 +0.276 [0.203, 0.347]**. Interesting: A recall
  0.65, B 0.16 (21 of 134). McNemar 75 vs 1. The block is 9 % interesting and CH3_A2 holds 91 of the 134; CH10_C1 holds
  none.
- **Against the prediction:** A ahead of B on both exams — as predicted. Arm B higher on (ii) than (i) — 0.635 vs 0.607,
  the predicted direction, but the intervals overlap and the two exams have different class mixes (26 % vs 9 %
  interesting), so this is not established. The predicted mechanism (B calling not-interesting windows interesting) was
  the smaller error: 139 training windows went that way, 979 the other.
- **Limits:** yardstick (A) is tilted toward arm A; one recording; labelled windows only; exam (ii) packs were all
  trained on; no reference line (off for this run).
- **The cut followed the written rule (the researcher, 2026-10-05):** every cut had at most one speck; k = 4 was the
  highest silhouette among cuts with at least two real clusters (three real clusters and one speck of 2 windows).
- **What the run shows, and what it does not.** The headline (A ahead of B) was close to built in and is not a
  finding about clustering. Three things are worth keeping: (1) **the manual-label forest carries to unseen channels**
  — 0.79 macro F1 on 24 simple features, two in three interesting windows found — which is the bar any later arm has
  to be compared with; (2) **Ward on catch22 + entropy features of 10-minute windows does not carve the researcher's
  interesting / not line** — silhouette 0.15, and 77 % of interesting windows fall in majority-not clusters — so the
  next version's clusters need different features, a different window length, or both, if they are to be shapes;
  (3) **cluster 4 (429 windows, 68 % interesting) is one separable kind of "interesting"** — arm B, taught only that
  cluster, still found a third of the interesting windows on unseen channels at precision 0.58. What cluster 4 looks
  like has not been examined.

## New scope, version 2 (2026-10-05, the researcher, after the baseline)

Supersedes the design list in "New scope" above where they differ; the reasoning there still stands.

**The question.** Can a classifier trained only on algorithmic clusters — no human labels in training — recognise the
windows a blind human calls interesting on data it has not seen? The trained model is then a reusable grouping of its
own (a library class).

**The design as the researcher put it:**

1. **A large window set, existing manual labels ignored:** 50–60 thousand windows or more, from `M2_aug_concat_fs1` and
   `M2_concat_fs1` (both oyster; different data, not crops of one another — 16 channels × 721 h and 16 × 282 h, about
   96,000 non-overlapping 10-minute windows in all). Test regions and artifact regions are left out before clustering.
2. **Ward clustering** of those windows.
3. **A dendrogram on the Models page; clicking a cluster at a cut shows what it looks like**, so the groups at cut k
   can be judged by eye.
4. **Every clustered window encoded as an image** (an existing encoding; fusion first was the wish) **and a CNN trained
   on the cluster categories.**
5. **The researcher decides which clusters are interesting / not interesting.**
6. **A human labels the model's test windows (up to 2,000) interesting / not, blind,** and that is compared with the
   model's calls.

**Points raised in discussion (2026-10-05) — recommendations, not yet decisions:**

- **A comparison line.** One agreement number cannot be read alone. Score the manual-label model (arm A) and the
  label-shuffle null on the same freshly labelled test windows; that keeps "better than manual" answerable.
- **What the clustering looks at decides the groups.** The baseline's 24 summary features gave texture groups, not
  shapes. Open: cluster on shape (the normalised trace), on other features, and at which window length.
- **"Centroid" on click:** in feature space a centroid is not a trace. Show the medoid (the most typical real window)
  and a handful of random members.
- **Ward at this size:** memory grows with the square of the window count (about 1.6 GB at 20,000, 14 GB at 60,000).
  Cluster a sample and assign the rest, or pre-group; no new dependency assumed.
- **Stage the model:** run the whole design with the random forest first (built, minutes), then the CNN. Changing
  labels and model together makes a difference unattributable; the CNN arm, its encoding at this scale and bringing
  HPC results back are not built, and `fusion_cnn.pth` is unusable (one output class).
- **The blind sample:** drawn evenly per predicted cluster, random order, predictions hidden; the cluster → interesting
  mapping fixed before labelling; some windows labelled twice for self-agreement. 600–1,000 may be enough.
- **Hold out a whole pack** (and M4 stays locked): the baseline's exam channels each had pack-mates in training.

**To build:** the unlabelled pool across two recordings; clustering that scales and keeps its tree; the dendrogram
with members on click; a blind interesting / not queue over test windows in Review; then the CNN arm.

**Decided by the researcher (2026-10-05, later the same day):**

- **Cluster on trace shape.**
- **Three scales — 1, 10 and 30 minutes — compared by shape:** windows are normalised so a short and a long instance
  of one shape can share a cluster. **One window set object per recording per scale** (three for M2_aug, three for M2),
  **combined at model setup** with duplicates and overlaps removed.
- **Forest first; and the site must write a SLURM script that trains a CNN**, to be tested on HPC.
- **The comparison line is the manual-label models** — fusion, recurrence, GADF, GASF; the checkpoint versions
  registered in the site may be ignored.

- **Windows under the noise floor are left out by default.**
- **Ward on a 20,000-window sample locally; a SLURM script for Ward over every window** as well.
- **The window set → categories workflow is edited in Analyse as chain blocks**; the dendrogram is the cluster block's
  page; Models reads the result as arm **B.2 cluster labels · trace shape** and its *Open in Analyse* is wired.
- **The manual-label models are scored at every scale** (1, 10, 30 minutes), to learn whether they generalise away from
  the 10-minute windows they were trained on.
- **Fusion images first** for the CNN. **Jobs is finished as far as this question needs.**

**Known risk (2026-10-05):** the shape clustering is the Library's own method (Ward on resampled, z-normalised
vectors), which works well there on **detected motifs**, each aligned to its event. Pool windows sit on a grid, so one
shape can fall anywhere in a window; `AG` measures whether the piles gather by shape or by position before the piles
are trusted.

**Tickets (`docs/prompts/fixup/`, written 2026-10-05, none run):** `AF-multiscale-window-pools.md` →
`AG-shape-clustering-and-dendrogram.md` → `AH-blind-test-labelling.md`, with `AI-cnn-arm-slurm.md` beside `AH`, then
`AJ-jobs-usable-for-rq1.md`.

## How it gets answered

Follow `RESEARCH_RUNBOOK.md` Q1:

1. Tune `windows_model` (cluster arm) and `manual_labels_model` (manual arm) on a span; both must use the same windows.
2. Save a window set over the training channels.
3. Launch both arms plus the RF baseline and the label-shuffle null.
4. Read Results and Compare: ΔF1 with CI, McNemar, per class and per channel, and the cluster→class contingency.
5. After the freeze, unlock the held-out recording once.

## Open decisions

None. Q-W1, Q-W2 and Q-W4 were answered 2026-10-03.

## Log

- 2026-10-03 · grilling · file created; Q41 and Q42 recorded.
- 2026-10-03 · grilling · Round 10: Q-W1, non-overlap, Q-W2 and Q-W4 decided; `AA` and `AB` prompts carry them.
- 2026-10-03 · fixup-aa · manual-label block, `manual_labels_model`, Save window set → `window_sets`, window-matrix
  names carry span + key; non-overlap revised to labelled-first by the researcher after measurement.
- 2026-10-03 · fixup-ab · paired training job (`Working/training/`, CLI), window set across channels, Models › Launch /
  Results / Compare live; first real run: exam (i) ΔF1 +0.228 [0.169, 0.290], exam (ii) ΔF1 +0.026 [−0.022, 0.071].
- 2026-10-03 · fixup-t · surrogate spans are out of every detection count; nothing in the training path changed.
- 2026-10-05 · researcher · scope redirected: the paired job becomes the baseline (to be run on the real database
  now); the main result is *cluster the unlabelled pool, validate blind* ("New scope"). Two builds added to *What is
  still needed*. Folder moved from `docs/prompts/rq_roundA/` to `docs/rq_roundA/`.
- 2026-10-05 · researcher · baseline run's prediction, primary exam, primary score and cut rule written down before
  launch ("Baseline run"); the three open points confirmed the same day.
- 2026-10-05 · researcher · baseline paired run on the real database (run 79, k = 4, exam channels CH4/8/12/16):
  exam (ii) ΔF1 +0.159 [0.120, 0.197], exam (i) ΔF1 +0.276 [0.203, 0.347]; the cut is frozen on window set 1.
- 2026-10-05 · researcher · baseline written up (cut rule confirmed; what it shows); RQ1 reframed as "New scope,
  version 2": a large unlabelled pool from M2_aug and M2, Ward, a dendrogram to judge the cut, a CNN on the cluster
  categories, a blind human interesting / not check on up to 2,000 test windows.
- 2026-10-05 · researcher · version 2 decided: shape clustering, three scales as six window sets combined at setup,
  forest first with a CNN SLURM script, manual-label CNNs as the comparison line; tickets `AF`–`AI` written.
- 2026-10-05 · researcher · tickets revised: noise floor on by default, the workflow in an Analyse chain with arm B.2
  on Launch, manual-label models scored at every scale, fusion first, a full-pool Ward SLURM script, `AJ` (Jobs) added.
- 2026-10-05 · researcher · confirmed before `AF`: the *Window pool* chain block (`AG`) picks from the library of all
  saved window sets and combines them; `AF` builds the six sets and the combine function; the train / test fence is
  laid over the pool, not stored on a set; the chain ends in *Train model*, which opens Models › Launch prefilled.
