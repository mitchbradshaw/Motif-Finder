# Candidate events, 2026-10-18: the RQ4b sweep merged into events, your verdicts carried over, a sample to judge

**Read this before you judge RQ1b's stratified sample, build RQ1b's training set, or read a detector's precision
for RQ4b.** The rules are in `Working/discovery/candidate_events.py` (its docstring states each one once). The handle
is `scripts/rq1b_candidate_events.py` (`build` / `queue` / `estimate`). It is on branch `a2/rq1b-event-table`, not
yet merged.

## In plain words

Picture 41 witnesses watching the same 16 channels for a month. Each writes "something happened here", and many
write about the same moment in their own words, with their own idea of when it started and stopped. To find out which
witnesses to trust:

1. Group their notes into incidents.
2. Keep the incidents you have already checked.
3. Check a fair, random handful of the rest: a fixed number from each kind of incident.

The share you accept in each handful says how far to trust everything you will never check. That is what lets 1.5
million detections become training data from a few hundred verdicts.

Your existing verdicts are training data and are never asked about again (your decision, 2026-10-18). The new sample
is drawn only from events nobody has judged.

## What was measured first (a read-only copy of the real database, 2026-10-18)

- **The sweep on M2_aug** holds about 2.1 M real detections from 45 settings in 14 families.
  - Some settings fire almost everywhere: OASIS marks 61–65 % of all time, deconvolved_troughs at 60 s 46 %, the
    Dehshibi prototype at ε 0.02 38 %, and the 1-minute CNNs 90 %.
  - Only about 6 % of the recording is caught by no detector.
- **Agreement thins out fast.** Counted per second (families covering it, the 1-minute CNNs left out):
  - at least 5 families agree on 25,600 stretches (18 % of the time);
  - at least 7 on 12,700 (4 %);
  - at least 9 on 2,900.
- **Agreement alone predicts your labels** at AUC ≈ 0.8: 0.81 on the 11,106 old 10-minute labels and 0.79 on 718 blind
  labels. The CNN templates are left out of that count, since they learned from the old labels.
- **You miss more than you invent, roughly.** 98 windows of the blind queue were shown twice, and you changed 6
  answers: 4 yes → no, 2 no → yes.
  - If you never call noise interesting, that is a miss rate of **11.5 % per look** (95 % range 4.6–23 %). It rests
    on only 6 disagreements.
  - Separately: of 14 blind 30-minute windows holding a 10-minute window you had called interesting, you called 3 not
    interesting.
  - The better a queue's detections, the more of your "no"s are misses. With an 11.5 % miss rate:

    | Share of a queue's detections that are real | Share of your "no"s that are probably misses |
    |---|---|
    | 20 % | 3 % |
    | 50 % | 10 % |
    | 70 % | 21 % |
    | 90 % | 51 % |
    | 97 % (the dip seed search) | 79 % |
  - A re-look shortlist: 720 of the 8,773 old not-interesting windows, and 36 of the 539 blind ones, hold a spot where
    at least 5 non-CNN families agree.
- **Cheap proposers exist.** Of 518 verified M2_aug events (most of them matches from two seed searches, so two
  shapes dominate):
  - signal_threshold + noise_threshold catch 84 % while marking 9.6 % of the time;
  - adding BEADs gives 87 % (14.8 % of the time);
  - adding the 10-minute CNN gives 99 % (in-sample: it learned from M2_aug labels).

## The table on M2_aug

Built from a copy of the real database in about 3 minutes.

- **2,015,081 detections** from 41 settings on 16 channels. The four 1-minute CNNs are left out (W4-A's negative
  control). Seed searches are labels, not votes.
- **1,502,319 candidate events.** Event length: median 160 s, p10 14 s, p90 633 s.
- **97 % of events hold a single detection** (1,451,012). Settings rarely outline an event the same way under §4.6.
  - So the **loose agreement** carries the information: the families with a detection overlapping half the shorter
    span. Against the labels the table carries, it gives AUC **0.874** (133,556 labelled events), and **0.847** on
    event-level labels alone (Library reviews and adjudications, 4,090).
  - The strict "same extent" count gives 0.51.
  - The interesting share climbs with the loose count:

    | Families agreeing | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
    |---|---|---|---|---|---|---|---|---|---|---|---|---|
    | Interesting (labelled events) | 0.3 % | 0.6 % | 1.6 % | 4.1 % | 13 % | 25 % | 46 % | 65 % | 64 % | 78 % | 88 % | 99 % |
  - Events per agreement level: 1–2 95,605 · 3–4 507,792 · 5–6 487,326 · 7–8 300,682 · 9+ 110,914.
- **Your existing verdicts, carried over:**
  - interesting **24,911**, not interesting **108,645**, artifact **3,758**, unsure 11;
  - **1,721 conflicts**;
  - 1,364,994 unjudged (conflicts included), of which 161,211 sit inside a span you called interesting.
- **Where those labels come from.** Mostly the old 10-minute windows: 21,362 of the 24,911 "interesting" are events
  that §4.6 calls the same event as one of those windows. The rest: Library review 1,895, adjudications 1,206, blind
  labels 382.
  - These are **window-level judgements**: "this 10 minutes is interesting", not "this event is a sharkfin".
  - For a shape classifier, weigh them as such (see *Open decisions*).
- **Candidate events are proposals, not physical events.** A 10-minute OASIS window and a 19-s trough inside it are
  two candidates. Merging accepted proposals into one physical event, and choosing its class and extent, is a
  training-set step. This is the fragments question; nothing here does it yet.

## The sample (seed 0)

Drawn on the copy as a dry run. It is the same draw `queue --real` will make, as long as the labels have not changed.

| Stratum | Unjudged events | Sampled | Each answer stands for |
|---|---|---|---|
| agree 1–2 | 84,163 | 100 | 842 events |
| agree 3–4 | 449,449 | 100 | 4,494 |
| agree 5–6 | 440,142 | 100 | 4,401 |
| agree 7–8 | 260,528 | 100 | 2,605 |
| agree 9+ | 95,989 | 100 | 960 |
| drop_detection_v1 | 908 | 50 | 18 |
| drop_detection_v5 | 764 | 50 | 15 |
| wavelet_encoded | 732 | 50 | 15 |
| symbol_search | 2,260 | 50 | 45 |
| BEADs_invert_detect_v1 | 8,787 | 50 | 176 |
| signal_threshold | 21,272 | 50 | 425 |

800 items. An event goes to the first selective detector among its own detections, else to its agreement level.

**Checked on a sandbox bridge** (a copy of the real database, the bridge run from this branch):
- the queue held 800 items, blind (no score, family or template shown), served shuffled across all 16 channels;
- none was hidden as "already judged", so the table's rules and Review's own rediscovery check agree;
- one verdict landed in `adjudications`, and the page moved on to rank 2.

## How to use it

1. **Merge the branch and restart the project bridge first.** The queue is served in its shuffled order through a
   new `order` key on the queue. A bridge on older code fails on that key at every queue read, including the header's
   "N need you". `queue --real --apply` refuses until the main checkout has the code.
2. `python scripts/rq1b_candidate_events.py build --real`
   - Read-only on the database.
   - Writes `DATA/derived/candidate_events/M2_aug_concat_fs1_<key>/`.
3. `python scripts/rq1b_candidate_events.py queue --table <that folder> --real` is a dry run that prints the strata.
   Add `--apply` to save the sample beside the table and create the queue.
4. **Judge it in Review:** *RQ1b candidate events · M2_aug_concat_fs1.mat · stratified sample · seed 0*.
   - Use **unsure** freely: an unsure item stays out of the estimate, and out of training.
   - A shape tag (element: sharkfin, trough…) can ride along with each verdict. It costs one click and is the start of
     RQ1b's class labels.
5. `python scripts/rq1b_candidate_events.py estimate --sample <table folder>/sample_seed0_l100_f50 --real`, at any
   point. It gives the precision per agreement level, per detector family and per setting, with 95 % intervals. Your
   earlier verdicts count as known, and the sample stands in for the rest. Unanswered and unsure items are counted
   and left out.

M4_aug is refused by name, whatever Settings › Datasets' lock says: it is RQ1b's exam. M2_concat and L_LM take the
same commands with `--file` once their sweeps are imported.

## Not built yet

- **The second look for your "no"s** ("one look for a yes, two for a no"). Re-asking a detection that already has an
  adjudication needs a new Review queue kind. Adding one means rebuilding `review_queues`, whose CHECK lists the
  kinds, as fixup-FQ did for `library-family`. The blind-test kind cannot carry it: it belongs to a B.2 run and
  freezes the run on its first answer.
- **The label model.** Once the sample is answered: fit P(real | which families agree) on the answers and the census,
  to give each of the 1.36 M unjudged events a probability. This is the step that turns the table into training data.
- **Physical events and classes.** Merge accepted proposals that are one event, pick its extent, attach its class.
- **The two other recordings,** once their sweeps are in.

## Open decisions

Each comes in plain words first, then a recommendation.

1. **How big a first sample.** Each answer in the big strata stands for thousands of events, so their precision will
   be known to about ±10 points from 100 answers. That is enough to rank detectors, though not to split hairs.
   - 800 items is perhaps one to two hours at your Review pace.
   - **Recommended:** keep 800. If time is short, `--per-level 50 --per-family 25` gives 400 first, and a second seed
     can top it up later.
2. **Which spans speak for an event.** Rule 5 lets the shortest spans holding an event decide, and any at most twice
   as long. A 90-hour catalogue region marked seed does not overrule a 10-minute window you judged "not interesting"
   around the event.
   - This turned 6,405 of the first build's 8,126 conflicts into labels, mostly "not interesting".
   - **Recommended:** keep it. The alternative, any interesting span anywhere means "conflict", throws away direct
     judgements.
3. **What the inherited window labels are worth.** 21,362 events are "interesting" because a 10-minute window you
   liked covers them.
   - Options: (a) use them as event labels everywhere; (b) use them only to teach event-versus-background, not shape
     classes; (c) leave them out.
   - **Recommended: (b).** A window says something happened in those 10 minutes, not what shape it was.

## Log

- 2026-10-18 · a2-rq1b · first measured and built. Table key `M2_aug_concat_fs1_8f4af0ad` on the copy; the real
  build's key depends on the database's runs.
