# RQ2 — Does a human-adjudicated exemplar used as a matrix-profile seed recover instances a human also accepts?

**Status (2026-10-04, after `X`): answerable in the app; not yet answered.** Promote an exemplar, search for it, send the
matches to Review, judge them, and the scoreboard's *interesting* and *precision* now count a verdict given in Review
first (`X`'s `divergence.py`: adjudication → extent → containment). **Recall is still the old §4.6 rule** (0 by
construction on window labels), so read precision and × null, not recall. ~~(2026-10-03, after `Y`: the scoreboard did
not count Review verdicts on the matches.)~~

## In plain words

You point at one wiggle you have checked yourself and say "find me more like this". The computer searches the
recordings for look-alikes. Then you check each look-alike by hand. The question is whether most of what it finds are
things you also agree with, and whether it finds more than it would by chance.

## What is known

- **The search runs:** Discovery › Seed search, `detection.seed_matches` (MASS, z-normalised Euclidean), with a
  200-draw phase-randomised null. On the readiness run, seed entry 1 over 452–456 h × 3 channels:
  - without a cut: *"197 found"*;
  - with a cut at 14.5: *"5 kept · the null gives 6.3 per draw"*.
- **Review works.** `S` promotes a detection to a Library exemplar (`source_kind = 'review'`).
- ~~The seed picker can't choose that exemplar. It shows only the first 24 of 3,603 entries, all machine-made.
  *Explore selection* is empty because Explore's *Take span for Review* is a demo write.~~ Fixed by `Y`, 2026-10-03
  (`docs/prompts/fixup/reports/Y-seed-sources.md`):
  - **The picker reaches every Library entry.** It pages and filters by how the entry was made (review / annotation /
    machine), by family, by recording and by channel. Your own exemplars come first.
  - **`S` names the entry it wrote:** the toast reads *"seed · Library entry 3610 created"*. The card's *Seed search in
    Discovery →* opens the Seed page with that entry as the seed.
  - **A seed run records which entry it searched for:** `entryId` on the Discovery run row. The stored recipe stays
    content-addressed on purpose.
  - **Explore's *Take span for Review* writes:** an `annotations` row with verdict `seed`, in an *Explore spans* Review
    queue, and offered at once under *Explore selection*.
- **The Seed page:**
  - It reads one null figure for one cut.
  - It keeps a dragged cut across a reload.
  - Re-running an unchanged search returns the same run; a changed cut is a new run whose label says how it differs.
  - *Open in Runs* lands on that run.
  - Match cards draw the match over the seed.
  (`Y`, 2026-10-03.)
- **Matches now reach Review:** `fixup-L`, 2026-10-03.
- **The walk, 2026-10-03, sandbox:**
  - `S` on detection 101 → entry 3610.
  - Seed search over M2_aug 452–456 h × 3 ch, cut 5.0 → *"4 kept · the null gives 20.6 per draw"* (a 60-sample seed,
    so the null is generous).
  - Sent to Review, judged 2 interesting / 2 not.
  - Scoreboard row *"4 found · 0 already judged · 3 reviewed · 0 interesting · 0 %"*. **The verdicts are in
    `adjudications`, and the row's *interesting* reads `annotations` only.**
- In Analyse, `detection.seed_matches` fails with `SideInputResolutionError`, because the exemplar can't be bound there.
  Not touched by `Y`; Discovery is the route.

- **The null a seed run is scored against is the null it drew** (`T`, 2026-10-03, `docs/prompts/fixup/reports/T-surrogates-one-null-never-a-detection.md`):
  - A seed run is paired with **200** surrogate runs per channel (Settings › Nulls, *Seed search*). The scoreboard row
    reads *"null expects 0 / 200 draws"* and Compare's *× null* tile says *"over 200 draws"*. Sandbox: 34.5 s for
    4 h × 3 channels.
  - **The recommended cut is computed per channel**, each channel's closest match against its own null, under
    Settings' α and correction (none / Holm / Benjamini–Hochberg). The sentence beside the cut says which, e.g.
    *"α = 0.01 per null draw · correction: none · each of 3 channels against its own null · 2 of 3 channels have a
    match under it"*.
  - A surrogate run's matches can never be sent to Review, judged, promoted or counted by Explore.
- **Built 2026-10-05 (fixup `AD`, `docs/prompts/fixup/reports/AD-cross-channel-against-chance.md` §4): the seed search's
  exclusion zone is a parameter, default m/2.** `detection.seed_matches` takes `exclusion` (a fraction of m) and passes
  it to `stumpy.match`; the search had run under stumpy's own m/4 while the Seed page printed §7.6's m/2 beside it. The
  Seed page's slider is live, the search's result key and the run's identity carry the zone, and the run's recipe
  records it (a sandbox run at 32 s of a 126-sample seed stored `exclusion: 0.254`). Every seed recipe's hash changed;
  the real database held 0 seed runs, so nothing stored was orphaned.

- **Repaired 2026-10-05, after the researcher's first real attempt** (seed runs `seed_7606fd`, `seed_8576e5`):
  - **A changed recording, channel list or section is written to the session.** It lived in the page's memory only,
    so after a change of recording every read asked the old recording for the new one's channels (*"no channel(s)
    ['CH3', 'CH1', 'CH4'] on M2_aug_concat_fs1"*), and the Seed page previewed the section the server still held
    (452–456 h) while *Run seed search* ran the one on screen (8–557 h).
  - **A run whose job died with the server reads *failed*, with the reason, and can be run again.** Both runs read
    *running* for a day after a restart, which held *Run seed search* shut ("already run with this seed and cut").
  - ***Save as template* writes a template** (`POST /api/discovery/seed/template`); Library › Templates lists it
    under *seed search*. It wrote nothing before. A *rebind* template is stored; applying one is not exercised.
  - **Cost, measured in the sandbox:** medoid seed (1,313 samples), 4 h × 3 channels, 200 paired draws: about
    2 minutes, 47 found, *Send 47 unjudged to Review* offered. The same search over 549 h is about 140 times that,
    and does not survive a server restart: keep the section to hours, not the recording.
  - *Send N unjudged to Review* is on Discovery › Runs (*Open in Runs*), not on the Seed page.

## Decisions already made

- **Q35:** a seed search draws **200** surrogates (Settings key). Every surface prints the count actually drawn.
- **Q36 / Q-Null-1:** the null is phase randomisation. Block shuffle keeps shapes intact, so it is not a shape null.
- **Q39 (2026-10-03):** a match becomes a Library member only if it is accepted (`interesting` / `seed`) and someone
  presses an explicit *Add N matches* button. *Include unjudged* is a flag that is off by default.
- **Q-D2:** precision is reported as two numbers, each printing its own rule: containment over the window labels, and
  extent over the event rows.
- **Round 11, exclusion zone (b) (2026-10-04):** `detection.seed_matches` gets an exclusion parameter, default **m/2**
  (§7.6), shown on the Seed page and settable; done while the real database holds no seed results.

## What is still needed

| Step | Owner |
|---|---|
| ~~Seed picker reaches any Library entry, at least `source_kind = 'review'`~~ | `Y`, done 2026-10-03 |
| ~~Explore's *Take span for Review* writes a real seed~~ | `Y`, done 2026-10-03 |
| ~~*Open in Runs* uses the right key; the Seed page's defects~~ | `Y`, done 2026-10-03 |
| ~~The scoreboard counts a Review verdict on the run's own detection as accepted~~ | `X`, done 2026-10-04 |
| ~~The null count printed is the count drawn; surrogate detections are never detections~~ | `T`, done 2026-10-03 |
| ~~Precision means what it says~~ (two figures, each with its rule) | `X`, done 2026-10-04 |
| Recall under the same containment rule (still §4.6, 0 by construction) | unowned, small (`X` report, *Left*) |
| ~~The exclusion zone is m/4 (stumpy's default), not §7.6's m/2~~ — a parameter, default m/2, settable (Round 11) | `AD`, done 2026-10-05 |

## How it gets answered

Follow `RESEARCH_RUNBOOK.md` Q2:

1. Promote an exemplar in Review (`S`); the toast names entry N.
2. *Seed search in Discovery →*, or Seed search › *change seed* › filter *review*.
3. Choose a cut against the null, and *Run seed search*.
4. *Open in Runs* → *Send N unjudged to Review* → judge every one.
5. Read the seed run's scoreboard row — precision (both figures) and × null — with its null.

## Open decisions

- ~~**The exclusion zone (m/4 vs m/2)**: see `Y`'s report. It is not blocking, but it changes which neighbouring
  matches are kept.~~ Decided (Round 11: m/2, a parameter) and built by `AD` 2026-10-05.

## Log

- 2026-10-03 · grilling · file created; `L` already landed.
- 2026-10-03 · fixup-y · the seed picker pages the whole Library, `S` names its entry and links to a seed search,
  Explore's take writes a seed, the Seed page's four defects are fixed. The walk reaches step 5; step 5's count waits
  on `X`.
- 2026-10-03 · fixup-t · a seed run draws 200 paired surrogates and every surface prints that count; the cut reads
  Settings' α and correction per channel; surrogate spans are refused by Review, promotion and Explore.
- 2026-10-04 · post-fixup summary · `X` made the scoreboard count Review verdicts first (this file had not been updated by `X`); recall still §4.6.
- 2026-10-05 · fixup-ad · the seed search's exclusion zone is `detection.seed_matches`' own parameter, default m/2, settable on the Seed page and recorded in the run's recipe; seed recipe hashes changed (0 seed runs in the real database).
- 2026-10-05 · researcher's bug report · scope changes reach the session; a run lost in a restart reads failed and can be re-run; *Save as template* writes a row the Library lists as *seed search*; a 4 h × 3 ch run walked to *Send 47 unjudged to Review* in the sandbox.
