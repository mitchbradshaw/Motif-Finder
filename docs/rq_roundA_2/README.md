# rq_roundA_2 — round A, second pass (2026-10-17)

Round A (`../rq_roundA/`) took the PRD's six research questions and made each answerable in the app. Round A_2 starts
from the researcher's plan of 2026-10-17, made after the first answers came in. It takes three of those questions
further, measures what the data really hold, and asks for the infrastructure the next answers need. Same shape and the
same rules as round A: one living file per question, kept current by every agent whose work changes what the question
can do.

## The questions

| File | The question | Status |
|---|---|---|
| [`RQ1b-family-classifier.md`](RQ1b-family-classifier.md) | Can a CNN trained on the Library's **verified families** find those motifs across whole recordings? (the "new RQ1") | data not ready; training path needs code; after RQ4b. *Candidate events and an 800-item stratified sample built 2026-10-18 (not merged): judge it next* |
| [`RQ2b-second-seed.md`](RQ2b-second-seed.md) | Does seeded search hold up on a **second, different motif**? | first motif answered (97 % / 90 %); second planned |
| [`RQ4b-detector-sweep.md`](RQ4b-detector-sweep.md) | Across **every detector and its settings**, where do they agree, and which find what a human accepts? | 27 variant templates created; ~~blocked on P2 / P3 for the full design~~ P2 and P3 built (2026-10-18); the window bound at the short scales is the researcher's decision (RQ4b) |

## Findings

| File | What |
|---|---|
| [`findings/rq1b-minirocket-2026-10-20.md`](findings/rq1b-minirocket-2026-10-20.md) | R4: a MiniRocket classifier of the researcher's verdicts (interesting versus not), trained on 2,456 judged events and 3,000 judged windows. Held out by recording: balanced accuracy 0.92, AUC 0.97, against 0.86 for detector agreement. Retrain with `scripts/rq1b_minirocket.py train --real`. |
| [`findings/rq1b-candidate-events.md`](findings/rq1b-candidate-events.md) | The RQ4b sweep merged into candidate events (M2_aug: 1.50 M from 2.0 M detections). Your verdicts are carried over and never re-asked; a stratified 800-item blind sample gives each detector's precision. Also measured: agreement predicts your labels (AUC 0.87), and your misses (≈ 11.5 % per look). Rebuild with `scripts/rq1b_candidate_events.py`. |
| [`findings/library-fragments-and-duplicates.md`](findings/library-fragments-and-duplicates.md) | The Library audit. Two-thirds of the members are overlapping pieces of one 20-minute recording, and M2_aug events are held twice or four times. The researcher's 197 accepted members are 142 distinct events. **Read it before training on families.** Re-measure with `scripts/library_fragment_audit.py`. |

## Prompts (build work the researcher asked for on 2026-10-17)

Common rules: [`prompts/00-common.md`](prompts/00-common.md). It includes who owns which files, so prompts can be
merged in any order.

| Prompt | What | Why |
|---|---|---|
| [`prompts/P1-held-out-lock-honours-settings.md`](prompts/P1-held-out-lock-honours-settings.md) | Every refusal of M4_aug obeys Settings › Datasets' lock switch | The researcher turned the lock off (15:02, audit 519) and nothing changed. The switch is not wired to the ~130 refusals. **Urgent: M4_aug is for the demos.** |
| [`prompts/P2-hpc-template-round-trip.md`](prompts/P2-hpc-template-round-trip.md) | Cluster template runs come back as real Discovery runs, their heavy steps cached for reuse; matrix profiles take the whole span | Today they never come back. "Really important" (the researcher) |
| [`prompts/P3-windowed-detection.md`](prompts/P3-windowed-detection.md) | Window length and overlap as a run setting; windows stitched into one result | Whole-span detection can miss events in quiet stretches |
| [`prompts/P4-seed-search-on-demand.md`](prompts/P4-seed-search-on-demand.md) | Seed search computes only on *Run preview* / *Run seed search*; every family as a seed; medoid seeds can add their matches to the Library | It starts a heavy preview on every seed pick and slider step, and its seed list misses most families |
| [`../prompts/blocks/W4-A-cnn-window-scores.md`](../prompts/blocks/W4-A-cnn-window-scores.md) | `catalogue.cnn_window_scores` and the 12 CNN detection templates (4 models × 1 / 10 / 60 min) | The existing CNN chain cannot run on whole recordings |

**Order:**

1. P1 and P4 together: urgent, with disjoint hunks.
2. P2.
3. P3, whose windows are ordinary runs that P2's import carries.

W4-A can run beside any of them.

**Launching one:** a new session in `C:\Users\mmebr\Documents\CNN`, in its own worktree, with:

> Read `docs/rq_roundA_2/prompts/00-common.md`, then carry out `docs/rq_roundA_2/prompts/<P…>.md`. Base commit:
> `<the main commit that holds this folder>`. Run `git log -1 --oneline` and fast-forward to it before anything else.

Whoever merges a branch runs the full gate in the main checkout (`pytest -n auto`; for client changes `tsc -b`, the
build, and the branch's smoke states on a sandbox bridge).

## Done on 2026-10-17, outside the prompts

- **27 variant templates** (ids 31–57) were created in the real database by `scripts/create_rq4_variants.py`, which
  dry-runs by default, refuses a project-mode bridge without `--allow-project`, and undoes with `--remove`. Commit
  `a5ed060`.
- **The null floor:** Settings › Nulls accepts 1 draw (the floor was 20), in `webui/client/src/settings/NullsPage.tsx`.
  It was verified on a sandbox bridge: 1 saved, no invalid state, no browser errors. A kind that reports a p is still
  bounded by the α check.
- **`scripts/library_fragment_audit.py`,** the read-only Library audit behind the findings file.

## Built and merged, 2026-10-17/18 (the managing session's ledger)

Each prompt was built by its own implementer in its own worktree, reviewed by one critic, fixed in one round, gated
(the full suite against the baseline's failure set; `tsc -b` and the build) and merged into `main`, not pushed.

| Prompt | Merge commit | Critic → fixed | Checked beyond the tests |
|---|---|---|---|
| P1 held-out lock | `25d0590` | 1 blocker (a training window set saved on M4 with the lock off), 1 major, 3 minor | Sandbox browser: the amber *M4 unlocked* chip, Explore opening M4's map, the toggle re-locking it |
| P4 seed on demand | `1b9b750` | 1 major (a failed preview was a dead end), 5 minor | Sandbox browser: *Family medoids* on g-05 (149 families); a seed pick starts no job; the backfill's dry run on a copy (10 runs, both dip searches) |
| P2 HPC round trip | `bdf94d3` | 2 major, 4 minor; the overnight sweep's 43 specs pinned by `tests/test_rq4_overnight_specs.py` | Sandbox rehearsal: export → both tasks run here → *Import results* → Runs ("computed on the cluster, its counts agree"), Jobs, the Map |
| P3 windowed detection | `7cd0454` | 2 major (window runs counted on Explore; 0 % overlap double count), 10 minor | Sandbox, noise_threshold over 80–84 h × 2 channels: 1-h windows planned 7 per channel and ran as one stitched run (5 kept, 1 duplicate dropped), its own Map row ("1 h windows · 50 %"); Explore gained the 2 stitched runs, not the 14 window runs; 10-minute windows refused naming step 01 (40 min) |

Integration commits (`a2-int:`), each test-first: the seed-results read refuses M4 once re-locked; the Seed page says
why its seed moved off M4; P2's held-out checks follow P1's lock; the block-classification test reads only shipped
blocks. The sandbox browser walk (`webui/smoke.py`) cannot finish on a copy of the real database:
`GET /api/discovery/templates` takes about 4.5 minutes there (it was 2.5–3 before this round), so pages that wait
on it time out. The states were checked by hand instead.

**Waiting for the researcher:**
1. ~~**The short scales** (RQ4b): when a window is shorter than 4 × a template's own averaging (10-minute windows
   on the 600 s templates, 1-hour windows on the drop detectors): refuse (default), fit the chain, or run it as it
   is, warned.~~ Decided 2026-10-18: as recommended (RQ4b, *Decisions already made*).
2. **The overnight `auto` profiles** (RQ4b): `mp_threshold`'s variants and `mp_motifs` use `backend: stump`, so they do
   not read the overnight profiles; `auto` variants, or an alias once `scripts/measure_gpu_stump.py` has run on the
   A100. *Measured 2026-10-18: the backends agree within float rounding (no sample changes side), so the alias is
   now the recommendation (RQ4b).*
3. ~~**The windowed null and the rescue** (RQ4b, "The stitch, the null and Explore").~~ Decided 2026-10-18: the
   rescue is kept.
4. **The backfill** for the dip searches' *Add N matches*:
   `python scripts/backfill_seed_entry_ids.py --real`, then `--real --apply`.
5. ~~**A new held-out exam for RQ1b**: M4_aug is open for the demos.~~ Decided 2026-10-18: M4_aug stays the exam,
   because the Library holds no M4 motifs (RQ1b).

## The M4 held-out exam (2026-10-26)

- 2026-10-26 · m4-exam · **M4 exam manifest frozen before any sample was drawn**: `DATA/derived/exam/M4/manifest.json` (copy `docs/rq_roundA_2/exam/M4-exam-manifest.json`), sha256 `db32fdc7ff42aa46ddfd0198993853e138e9fb958c3d4dcf83a65e5f3317e0b6`; detector list `detectors.json` sha256 `f112decdffbdc7c04529cc5687823e5e85885ec858101be680496b55502c9b80`. Held-out lock back ON (audit_log 536); freeze recorded as audit_log 537.
- 2026-10-26 · m4-exam · sample drawn and blind queue made: Review queue **36** (290 items; audit_log 538), from table `DATA/derived/candidate_events/M4_aug_concat_fs1_ae545821/` sample `sample_seed20261026_l40_f15`. Code: `scripts/m4_exam_freeze.py`, `scripts/m4_exam_score.py`, the exam door in `Working/discovery/candidate_events.py` (+ `--exam-manifest`/`--exam-sha256` on `scripts/rq1b_candidate_events.py`); tests `tests/test_candidate_events_exam.py`, `tests/test_m4_exam_score.py`.
- 2026-10-26 · rq1b-null · **M4 exam amended (1) before any judging**: the four reference CNNs (GASF, GADF, recurrence, fusion_cnn_3; same sha256 as the frozen manifest) are scored on the same answered exam events as MiniRocket R4, with the same cut-and-resample as the 2026-10-26 quick comparison, AUC and balanced accuracy at 0.5 with the within-stratum bootstrap, and the paired AUC difference against MiniRocket. `DATA/derived/exam/M4/amendment-1.json` (copy `docs/rq_roundA_2/exam/M4-exam-amendment-1.json`), sha256 `5286bac396f99c524c4e53a926ec2318e42313156aa333188d6407f962e25d14`, audit_log **539** (queue 36 had 0 review rows). The frozen manifest is not edited. `scripts/m4_exam_score.py --real` now also verifies the amendment (hash, audit row older than every exam verdict) and refuses a changed CNN checkpoint; tests in `tests/test_m4_exam_score.py`.

**How the researcher sits the exam** (Review hides M4 while the lock is on, and has no exam exemption:
`webui/server/review.py` `_held_out_ids`; with the lock on, queue 36 shows 0 items):

1. Settings › Datasets: turn the held-out lock **off** (type `M4_aug_concat_fs1`). Audited.
2. Review: open **only** queue 36, *Held-out exam · M4 · blind sample* (290 items). Judge every item once; open no
   other page or queue that shows M4 while the lock is off.
3. Settings › Datasets: turn the lock back **on** straight after. Audited.
4. `python scripts/m4_exam_score.py --real` (read-only): writes `DATA/derived/exam/M4/results.json` and
   `findings/m4-exam-<date>.md`. Only now are the model's scores computed on the sample.

## Rules (as round A)

1. Move a step from *What is still needed* to *What is known*, with the date and your report's path.
2. Copy any decision the researcher made into *Decisions already made*.
3. Add one line to *Log*: `YYYY-MM-DD · prompt-id · what changed`.
4. Do not delete history; strike through and say why.
5. **Plain language first:** every question or finding put to the researcher opens with a simple explanation, then the
   options, then a recommendation (`CLAUDE.md`, "Talking to the researcher").
