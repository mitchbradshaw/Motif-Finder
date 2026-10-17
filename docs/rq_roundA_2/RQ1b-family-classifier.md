# RQ1b — Can a CNN trained on the Library's verified families find those motifs across whole recordings?

**Status (2026-10-17): not started; the data are not ready and the training path needs code.** This is the "new RQ1".
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

## How it gets answered

1. Freeze the class list and the verified-event table, with counts per class and per channel.
2. Train on the cluster and import.
3. Score held-out channels or recordings, and blind-check a sample.
4. Report per-class balanced accuracy beside the background class's false-positive rate per hour.

## Open decisions

- **Which classes?** The ten reviewed families include near-duplicates of one shape at different lengths (troughs
  154 / 164 / 165). Merging by shape rather than by family id is the likely answer.
- **Window length per class:** fixed (resample every event to 600, as W4-A does), or per-class scale.
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
