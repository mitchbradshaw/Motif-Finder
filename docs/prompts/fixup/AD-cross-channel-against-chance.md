# Fixup AD — a cross-channel match must beat chance, and a human decides what is an artifact

**Ready to run. Runs in parallel with `AE`** (see *Running in parallel* below). Written 2026-10-04 from
`QUESTIONS.md` **Round 11** and **Round 12**, which are both answered. It replaces how `W` bins a pair, not where
the bins are stored. It also carries one unrelated small change, the seed search's exclusion zone (Round 11), because
that change is cheapest now, while the real database holds no seed results.

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read these first:
- `CLAUDE.md`;
- `reports/W-cross-channel-onto-edges.md` §3 and §5–7;
- `webui/screenshots/fixup/Q40d/README.md` (the measurement this prompt rests on);
- `QUESTIONS.md` Rounds 11–12;
- `Working/cross_channel.py`;
- `Working/library/matching.py::classify_family_across_channels` (:433) and `::family_recurrence` (:624);
- `Working/review/queues.py::create_queue`;
- `docs/prompts/rq_roundA/RQ6-recurrence-across-channels.md`.

Commit prefix `fixup-ad:`. Test-first: your first commit touches only `tests/` and must fail. **`--sandbox`
only.**

## In plain words (the researcher asked for this framing)

`W` called two electrodes "the same event" whenever their clips looked alike at the same moment. But the clips were
about 1 second long and mostly slow drift. The agent then compared the same electrodes at **random other moments**,
and the clips looked just as alike there (91 % vs 90 % on Fig2A). So the rule was finding coincidence, not
contamination.

The fix has three parts:
1. **Only flag a match that is better than chance**, by checking the same pair of electrodes at many random moments.
2. **Refuse clips too short to judge.**
3. **Let a human make the final call** on anything flagged as a suspected artifact.

## Decided (do not re-open)

1. **A per-pair chance test.** For each member × sibling channel, compute the same statistic `classify_waveforms`
   computes on the **same sibling at K random other times**.
   - The random windows are the member's length, at least 60 s from the member, inside the recording, and not over a
     human-marked artifact region.
   - K is a Settings key, default **100**, and the draw is seeded from the member id so a re-run reproduces it.
   - A match counts only if its |r| exceeds the **95th percentile** of that pair's random |r|. The percentile is a
     Settings key too.
   - Store the null's percentile and K beside the result.
2. **The thresholds** (Settings › Analysis defaults, `cross_channel.*`):
   - **suspected artifact** = |lag| ≤ 1 s **and |r| ≥ 0.98** (raised from 0.5 by the researcher) **and** beats the
     chance test **and** both the member's and the sibling's peak-to-peak (mV, by `recordings.units`) clear the
     dataset's noise floor (Settings › Datasets, default 0.1 mV).
   - **propagation** = 1 s < |lag| ≤ 50 s **and** |r| ≥ the existing floor (0.5) **and** beats the chance test **and**
     both clear the noise floor. The 0.98 applies to the artifact test, not to propagation (an assumption flagged in
     `QUESTIONS.md` Round 12; ask if it reads wrong).
   - **independent** = everything else.
   - The twin need not be a family member: a member judged against any sibling channel (Q40d-1 (b), now behind the
     chance test).
3. **Minimum length.** A member shorter than **30 samples** (a Settings key) is not classified. It reads
   **too short to tell**, is counted, and is never binned. Do not pad to reach the length: padding adds shared drift.
4. **A human decides.** The machine only *flags*.
   - Suspected-artifact members go to a Review queue, **"Suspected artifact · F-xxx"**, made through `create_queue`.
     It shows every channel of the recording over the member span plus padding on **one shared true-mV axis**, the
     member bold, the sibling's r, lag, amplitude ratio and the chance percentile printed. (`webui/screenshots/fixup/Q40d/examples_gallery_mV.png`
     is the picture to match.)
   - The verdicts are *artifact* / *not artifact* / *unsure*.
   - **The verdict is a human row (rule 5).** Decide whether it lives in `annotations` over the member's span or in an
     adjudication, by what the member is: a member from a run has a detection, an imported one does not. **Never write
     it on `motif_member`, `motif_edge` or `motif_member_cooccurrence`.** Say in your report which you chose and why.
5. **Recurrence** (`family_recurrence`, one definition, every reader):
   - *excluding artifacts* removes only members **a human marked artifact**.
   - Beside it, *machine-flagged: n · confirmed: k · rejected: j · unjudged: u*.
   - *Propagation counted once* uses only propagation that beat chance.
   - In a member–member artifact pair confirmed by a human, **both** members are artifacts (Round 11 Q40d-2).
6. **The seed search's exclusion zone.** Give `detection.seed_matches` an exclusion parameter (as a fraction of m),
   default **m/2** (§7.6), passed to `stumpy.match`. Then:
   - the Seed page shows it and lets it be set;
   - `seeded_search.py:588–607`'s "the block and the spec differ" note goes;
   - `exclusionSettable` becomes true.
   This changes seed recipes' hashes. The real database holds 0 seed runs, so nothing stored is orphaned. Say so in the
   commit.

## Re-measure, and put it in the report

On `W`'s three families (F-130, F-119, F-39) and on the M2_aug members, give **before (`W`'s rule) → after**:
- counts per bin, and the too-short count;
- machine-flagged suspected artifacts;
- recurrence counts.

The agent's measurement predicts a large fall: say whether it happened. Re-use
`webui/screenshots/fixup/Q40d/measure.py` / `analyse.py` where they help, and do not duplicate them into `Working/`.

## Leave alone

| Leave alone | Why |
|---|---|
| Where edges and co-occurrence rows are stored | `W` built it; add fields additively through `init_db()` |
| The Library noise-floor view filter | the Library prompt; RQ6 waits on it (Round 12 Q5) |
| The scale bank, the three distances | `V` |

## Running in parallel (2026-10-04)

**You run beside `AE`** (`AE-library-floor-and-indexes.md`), another agent in the same checkout. The README's
**"Running two prompts at once"** rules apply in full: your own port and a private client build served with
`run_server.py --dist`; `npx vite build --outDir <yours>` while working and `npm run build` only for the gate (the other
agent's in-flight files may make it red — say so in the report); `pytest -n 4`, never `-n auto`, and announce in your
report when you took the machine for smoke; shared files are **append-only and committed immediately with your own
hunks only** (`git add -p`). If you need a file `AE` owns, stop and write to `requests/` rather than editing it.

| | files |
|---|---|
| **yours** | `Working/cross_channel.py`, `Working/library/matching.py` (`classify_family_across_channels`, `family_recurrence`), `webui/client/src/library/CrossChannel.tsx`, `Edges.tsx`, `Adapters/detection_seed_matches.py`, `Working/discovery/seeded_search.py`, the Seed page, the suspected-artifact queue in `Working/review/` |
| **`AE`'s — do not edit** | `webui/client/src/library/AtlasPage.tsx`, `GroupingPage.tsx`, the Library filter bar in `chrome.tsx`, `Working/library/features.py`, the rose-reference function, `Adapters/interrogation_event_shape.py` |
| **shared** | `webui/client/src/library/FamilyPage.tsx` and `RecurrencePage.tsx` (you add the classify / *send suspected artifacts* / flagged-confirmed lines; `AE` adds the floor filter, in-place slideshow and hand edits — keep to your own components and mount points), `webui/server/library.py` (append; do not edit `AE`'s helpers), `webui/client/src/api.ts` / `api/library.ts`, `webui/smoke.py` (own `smoke_pages` file), Settings pages |

**One seam to keep stable:** `AE` filters members by the noise floor **in the caller** and passes the surviving ids
to `family_recurrence(conn, member_ids)`. Keep that signature working; if you must change it, write to `requests/`
first.

**Talking to the researcher:** any question you put to them opens with a plain-language explanation, then the
options, then your recommendation (`CLAUDE.md`). **Before you report, update**
`docs/prompts/rq_roundA/RQ6-recurrence-across-channels.md` and `RQ2-exemplar-seeded-search.md` (the exclusion zone)
per that folder's README.

## Acceptance (check these in a browser)

1. **Classify, then review on F-130:**
   - Library › Family F-130 → *Classify across channels*. Short members read *too short to tell*; bins carry their
     chance percentile.
   - *Send suspected artifacts to Review* opens a queue whose cards match the gallery.
   - Mark two artifact and one not. Recurrence moves by exactly the confirmed ones and prints the flagged / confirmed
     line.
2. **Seed search:** Discovery › Seed search shows the exclusion zone at m/2, it can be changed, and a run's recipe
   records it.

## The gate

1. `npx tsc -b` + `npm run build`.
2. `webui/smoke.py` on a fresh `--sandbox` bridge, finishing on the full walk.
3. `pytest -n 4` against the baseline (2,212 passed / 22 skipped / 0 failed on 2026-10-04; compare failure sets).

Evidence into `webui/screenshots/fixup/AD/`.

## Report

Write `docs/prompts/fixup/reports/AD-cross-channel-against-chance.md`. Open with a plain-language summary. Then cover:
- the before → after table;
- where the human verdict lives and why;
- the exclusion change;
- items left;
- out-of-scope files touched;
- the gate.
