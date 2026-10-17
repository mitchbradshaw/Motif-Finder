# rq_roundA_2 — round A, second pass (2026-10-17)

Round A (`../rq_roundA/`) took the PRD's six research questions and made each answerable in the app. Round A_2 starts
from the researcher's plan of 2026-10-17, made after the first answers came in. It takes three of those questions
further, measures what the data really hold, and asks for the infrastructure the next answers need. Same shape and the
same rules as round A: one living file per question, kept current by every agent whose work changes what the question
can do.

## The questions

| File | The question | Status |
|---|---|---|
| [`RQ1b-family-classifier.md`](RQ1b-family-classifier.md) | Can a CNN trained on the Library's **verified families** find those motifs across whole recordings? (the "new RQ1") | data not ready; training path needs code; after RQ4b |
| [`RQ2b-second-seed.md`](RQ2b-second-seed.md) | Does seeded search hold up on a **second, different motif**? | first motif answered (97 % / 90 %); second planned |
| [`RQ4b-detector-sweep.md`](RQ4b-detector-sweep.md) | Across **every detector and its settings**, where do they agree, and which find what a human accepts? | 27 variant templates created; blocked on P2 / P3 for the full design |

## Findings

| File | What |
|---|---|
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

## Rules (as round A)

1. Move a step from *What is still needed* to *What is known*, with the date and your report's path.
2. Copy any decision the researcher made into *Decisions already made*.
3. Add one line to *Log*: `YYYY-MM-DD · prompt-id · what changed`.
4. Do not delete history; strike through and say why.
5. **Plain language first:** every question or finding put to the researcher opens with a simple explanation, then the
   options, then a recommendation (`CLAUDE.md`, "Talking to the researcher").
