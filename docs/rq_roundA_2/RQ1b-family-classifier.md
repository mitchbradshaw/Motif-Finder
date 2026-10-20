# RQ1b — Can a CNN trained on the Library's verified families find those motifs across whole recordings?

**Status (2026-10-17): not started; the data are not ready and the training path needs code.** This is the "new RQ1".
*2026-10-18: the candidate-event table and its stratified review sample are built (branch `a2/rq1b-event-table`,
not merged): `findings/rq1b-candidate-events.md`. The next step is yours: merge, build, judge the 800-item queue.*
Round A's RQ1 (`../rq_roundA/RQ1-cluster-vs-manual-labels.md`) asked whether cluster labels beat manual labels for an
interesting / not classifier. RQ1b asks for a classifier of **motif families**, about 10 named classes plus a background
class, trained on the HPC and loaded back into the website to sift recordings.

## In plain words

You show the computer many checked examples of each kind of shape (sharkfin, trough, drop, dip…) and plenty of plain
background, and it learns to point at each kind in recordings it has never seen, with a confidence. Two things decide
whether that works. First, how many genuinely different checked examples each kind has. Second, whether the exam uses
data the model never saw in training. Today the Library looks bigger than it is (see the audit), and the website can
train a CNN on window-pool clusters but not yet on Library families.

## What is known

- **The Library audit** (`findings/library-fragments-and-duplicates.md`, re-run with `scripts/library_fragment_audit.py`):
  - 67 % of members are overlapping 2-second pieces of one 20-minute recording (`Fig2A_dt0p1.csv`, reishi, 10 Hz).
    They dominate 115 of the 149 families.
  - M2_aug events are often held twice, some four times.
  - The researcher's 197 accepted members are **142 distinct events** in ten families (4–41 each). Two of those
    families sit on a single channel.
- **The largest verified sets are seed-search matches:** id010 dip, 256 of 263 accepted; id020, 94 of 104 accepted.
  These are distinct events.
  - *Add N matches* would put them into the Library in one click, but it refuses these two runs. Their seeds came from
    the Seed page's catalogue "Family medoid" tab, which carries no Library entry.
  - P4 fixes that. Meanwhile, start seed searches from Library › Family › *Seed search in Discovery*.
- **Round B's note (2026-10-07) on what such a model needs:**
  - an explicit background class: noise and drift from stretches holding no member, several times the motif count,
    near-misses included;
  - classes that are the researcher's **verified named** families, not raw Ward families;
  - about 100–200 verified members per class to start and 500+ to be comfortable; classes under about 50 merged or
    dropped;
  - positives jittered and taken at the three scales;
  - a held-out pack and a blind check, as in RQ1;
  - confidences calibrated on validation.
- **What the code does today** (read 2026-10-17):
  - `catalogue.classifier` (random forest) is already multi-class on any Grouping.
  - The B.2 CNN (`Working/training/shape_cnn.py`, `cnn_job.py`) trains *k* classes on a window pool's Ward cut:
    EfficientNet-B0, fusion / GASF / GADF / recurrence images of the raw window resized to 224, 12 epochs, a
    self-resubmitting SLURM job, imported by `python -m Working.training import-results`.
  - Training on **Library family** labels needs four pieces, roughly 300–400 lines plus tests:
    - an exporter that writes family labels (with K + 1 = background) and a role split;
    - an import branch (`hpc_import._import_cnn` assumes a pool key and maps classes to interesting / not);
    - a multi-class scoring block (`catalogue.cnn_score` returns P(class 0) only, and W4-A's `cnn_window_scores`
      refuses anything but two classes);
    - a window-length rule. Members run 4–7,178 samples (median 37) at 1 and 10 Hz. Recurrence and fusion fail at
      8 samples or fewer, and B.2's rule is never to resample.
  - **A trained model is not registered automatically:** copy it into `MODELS/` or `DATA/derived/models/` and scan it
    in Settings › Models & registration. (Models › Registry is a demo page; it lists no real model.)
- **Negatives today:**
  - `not_interesting`: 8,773 ten-minute grid windows and 849 blind labels (1, 10 and 30 minutes), plus 35 Library and
    94 detection verdicts;
  - `artifact`: 128 + 13.

  They are 10–30× longer than family members, so they would be cut to member length. No `noise` class exists, and the
  `quality:noisy` tag is used 0 times.
- **Candidate events from the RQ4b sweep** (a2-rq1b, 2026-10-18, `findings/rq1b-candidate-events.md`; code
  `Working/discovery/candidate_events.py`, `scripts/rq1b_candidate_events.py`):
  - **The table.** M2_aug's 2,015,081 sweep detections (41 settings; the 1-minute CNNs left out) merge into
    1,502,319 candidate events under §4.6. Each event carries which families found it and which agree with it.
  - **What carries the information.** 97 % of events hold one detection, so the loose agreement does: AUC 0.874
    against the labels the table carries (0.847 on event-level labels alone). The interesting share runs from 0.3 %
    at one agreeing family to 99 % at twelve.
  - **Your verdicts, carried over:** 24,911 interesting, 108,645 not interesting, 3,758 artifact, 1,721 conflicts.
    Most come from the old 10-minute windows, so they are window-level judgements.
  - **The sample:** 800 unjudged events (100 per agreement level, 50 per selective detector), one blind queue served
    shuffled. Checked on a sandbox bridge.
  - **The estimate:** precision per agreement level, family and setting, with your earlier verdicts counted as a
    census.
- **Your misses, measured roughly** (same findings file): the blind repeats imply you miss about 11.5 % of
  interesting windows per look (95 % range 4.6–23 %). The better a queue's detections, the more of your "no"s are
  misses: about half of them at 90 % precision.
- **R4, a MiniRocket classifier of your verdicts** (2026-10-20, `findings/rq1b-minirocket-2026-10-20.md`; code
  `scripts/rq1b_minirocket.py`; model `DATA/derived/models/rq1b_minirocket/20261020-2343/`):
  - **Classes:** interesting versus not. No verdict carries a shape class, so there are no shape classes yet.
  - **Trained on:** 2,456 judged events from six recording groups, plus 3,000 judged windows.
  - **Held-out results:** leave one recording out, balanced accuracy 0.92 and AUC 0.97 (0.95–0.99 per recording).
    On the stratified queue candidates alone, AUC 0.97. Inside every detector family, AUC 0.88–0.99.
  - **Baselines on the same candidates:** detector agreement alone AUC 0.86; size and noise alone 0.84–0.90.
  - **Not yet:** the M4_aug exam, a free sliding scan, shape classes.

## Decisions already made

- **2026-10-17 (the researcher):**
  - about 10 families or fewer, each with as many valid adjudicated members as possible;
  - known not-interesting noise sections are the negative class;
  - the model is trained on the HPC and used in the website;
  - duplicates and fragments are handled **when RQ1b's training starts**, not before.
- **Order (the researcher, 2026-10-17): after the RQ4b detection sweep,** so the sweep's accepted detections can grow
  the Library first.
- **2026-10-18 (the researcher): M4_aug stays the held-out exam.**
  - **Why it still counts:** the Library holds no M4 motifs, so nothing trained or grouped has seen it, although M4 is
    open for the demos.
  - **Keeping it that way:**
    - Don't add M4 matches to the Library while the lock is off (*Add N matches* on an M4 seed run, or a Review
      promotion of an M4 span). The Library's importers refuse M4 by name whatever the switch says, and training
      always does.
    - Turn the lock back on after the demos.
- **2026-10-18 (the researcher): training data first.** Upload the further datasets, run the existing detectors on
  them, and review as many motifs as possible (up to about 10,000) to fill RQ1b's training data.
- **2026-10-18 (the researcher): what is already judged is training data and is never asked again.** A new sample
  draws only from events nobody has judged (`findings/rq1b-candidate-events.md`).
- **2026-10-18 (the researcher): the candidate-event decisions, all as recommended** (`findings/rq1b-candidate-events.md`):
  - keep the 800-item first sample, then judge more, up to about 3,000, with further seeds;
  - the shortest spans holding an event decide;
  - window-based labels (`label_basis` = window) teach event-versus-background only, never shape classes.
- **2026-10-18 (the researcher): your errors lean to misses.** You are more likely to call an interesting event not
  interesting than the reverse. So the plan is one look for a yes and two for a no, before a "no" becomes a training
  negative.

## What is still needed

| Step | Owner |
|---|---|
| A class list of 5–10 named shapes, each defined in words with 2–3 example events (a codebook, as RQ1 v2 asked) | researcher |
| Verified examples per class, counted as **distinct events on ≥ 3 channels**: accepted seed matches (*Add N matches*), Library family queues, the RQ4b sweep's accepted detections | researcher |
| De-duplicate: one member per twin set; reishi `sliding` pieces out (or merged per run); single-channel classes merged or topped up | an agent, when training starts (`findings/…` §"What it means") |
| A grouping filter by corpus / source, or a script around `run_grouping`, to make a clean "verified families" grouping | an agent |
| Background windows: random stretches holding no member, several times the motif count, near-misses included, cut to member length | an agent |
| The four training-path pieces above (exporter, import branch, multi-class scorer, window-length rule) | an agent (prompt to write when the class list exists) |
| HPC training (the B.2 job's self-resubmitting script is the pattern) and import | researcher |
| A held-out pack and a blind check; calibrated confidences | as RQ1 v2 |
| ~~The candidate-event table over the RQ4b sweep, your verdicts carried over, a stratified blind sample and its estimator~~ built 2026-10-18 (a2-rq1b, not merged) | ~~agent~~ |
| Merge `a2/rq1b-event-table`, restart the bridge, `build --real`, then `queue --real --apply` | researcher |
| Judge the 800-item sample in Review (unsure freely; a shape tag can ride along); then `estimate --real` | researcher |
| The label model: P(real \| families agreeing), fitted on the sample's answers and the census, giving every unjudged event a probability | an agent, after the answers |
| The second look for "no"s: a new Review queue kind (a `review_queues` rebuild, as fixup-FQ did) | an agent |
| Accepted proposals merged into physical events, each with one extent and one class (the fragments question) | an agent, when training starts |
| The same table for M2_concat and L_LM once their sweeps are imported (`build --file …`) | researcher |

## How it gets answered

1. Freeze the class list and the verified-event table, with counts per class and per channel.
2. Train on the cluster and import.
3. Score held-out channels or recordings, and blind-check a sample.
4. Report per-class balanced accuracy beside the background class's false-positive rate per hour.

## Open decisions

- **Which classes?** The ten reviewed families include near-duplicates of one shape at different lengths (troughs
  154 / 164 / 165). Merging by shape rather than by family id is the likely answer.
- **Window length per class:** fixed (resample every event to 600, as W4-A does), or per-class scale.
- **From the candidate-event table** (`findings/rq1b-candidate-events.md` › *Open decisions*, each with a
  recommendation):
  - the first sample's size (800, or 400 first);
  - which spans speak for an event (the shortest that hold it, as built);
  - what the 21,362 window-inherited "interesting" labels are worth (recommended: event-versus-background only, not
    shape classes).
- ~~**Is M4_aug still the held-out exam?** The researcher is using it for demos from 2026-10-17 (see P1). Once it is
  looked at, it is no longer an untouched exam for RQ1 or RQ1b. Choose another held-out pack (a whole M2 pack) before
  training.~~ Decided 2026-10-18: yes, M4_aug stays the exam (*Decisions already made*).

## Log

- 2026-10-17 · set up · file created from the Library audit and the code read; the researcher's decisions recorded.
- 2026-10-17 · a2-p1 · with Settings › Datasets' lock off, M4_aug opens in Explore, Analyse, Discovery, Review and
  Library (it stays refused by exam (iii) and by training); once looked at there it is no longer an untouched exam, so
  the open decision on the held-out exam above now matters before any RQ1b training.
- 2026-10-18 · the researcher · M4_aug stays the held-out exam (the Library holds no M4 motifs); the next step is
  training data: new datasets uploaded, the existing detectors run on them, and up to ~10,000 motifs reviewed.
- 2026-10-18 · a2-rq1b · candidate events built over the RQ4b sweep (M2_aug: 1.50 M events from 2.0 M detections;
  your verdicts carried over; a stratified 800-item blind sample; the precision estimator). The table was checked on
  a copy of the real database, the queue on a sandbox bridge. Not merged. `findings/rq1b-candidate-events.md`.
- 2026-10-20 · a2-rq1b · merged (57a42e0).
  - **Queue 25 (M2_aug) answered by the researcher:** 754 answered, 46 unsure. Its estimate is in
    `DATA/derived/candidate_events/M2_aug_concat_fs1_bf098c00/sample_seed0_l100_f50/estimate.json` (R3, read in RQ4b).
  - **Four new tables:** CO_fs2, LM_fs2, M2_concat and L_LM fs2 (the 10 Hz copy left out). 2.28 M detections make
    1.60 M candidate events.
    - The merge rules are rate-free (§4.6, half the shorter span, twice the shortest span).
    - Two detector settings count samples, so they cover half the time at 2 Hz: BEADs' `width` and the wavelet
      levels.
  - **Queue 28, for R3 and the MiniRocket training (R4):** 1,160 sampled events, 290 per recording (40 per agreement
    level, 15 per selective detector). The recordings are interleaved and the queue is blind. Review serves 1,153
    items, since 7 same-run pairs overlap. It was created through the project bridge's own route; each recording's
    sample is `<table>/sample_seed0_l40_f15_multi`.
- 2026-10-20 · a2-rq1b · R4: MiniRocket trained on the researcher's verdicts after queues 25 and 28 were judged.
  Interesting versus not; held out by recording, balanced accuracy 0.92 and AUC 0.97. Model in
  `DATA/derived/models/rq1b_minirocket/20261020-2343/`; `findings/rq1b-minirocket-2026-10-20.md`.
