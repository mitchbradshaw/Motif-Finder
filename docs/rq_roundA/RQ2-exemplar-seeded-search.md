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

- **Repaired 2026-10-06, after the researcher's third report ("5 hours for 4 h × 3 channels")** — the cost above was
  wrong, and so was the estimate built on it:
  - **The preview piled up.** The live server held twenty copies of the same 4 h × 3-channel preview, started
    seconds apart, each sharing one CPU with the others — so each read "6 h left". One copy alone takes **43 s**
    in the bridge, **11 s** headless. A POST for a query already running now joins that job (`_live_seed_jobs`),
    and the page re-asks after a server restart instead of polling nothing for four minutes. The 2026-10-05 rates
    were measured under the pile-up; the honest ones are about 100,000 (preview) and 50,000 (run) sample·draws/s.
  - **A seed search over the ceiling is a SLURM job.** `detection.seed_matches` declares no estimator, so a seed
    plan routed *unknown* and ran locally however large the scope. It is now costed by the measured rate against
    a **ten-minute** ceiling (Settings › Compute & HPC `limit.Discovery` overrides); over it, *Run seed search*
    is replaced by *Create SLURM script*. The script is `Working.discovery.seed_job`'s: the spec carries the
    exemplar's own samples, the channels by file and index, the section, the parameters and the session's null,
    and the job computes the candidates **and the 200 draws** (the chain exporter's script ran the real chain with
    no null — the whole cost). *Import HPC result* takes the result file back: the page's histogram and cut come
    from it, and the run row is finished locally with the real search alone (seconds), marked *null from the
    cluster*. The round trip (spec → headless compute → import → row done, 600 found) was walked in the sandbox.
  - **A run can be removed from the session** (the × on its card). The row is marked, not deleted; History lists
    it as *removed* and *open* puts it back; its runs and detections are untouched.
  - **2026-10-07, after the first real submission** (a drop exemplar over all of `M2_aug`): the job now writes
    its result after every channel and every ten draws and **resubmits itself** while it reads incomplete
    (a 20-minute wall would otherwise have killed a ~3.5 h search with nothing on disk); every generated
    SLURM script lists in its comments the code, the input files and the output it needs on the cluster; the
    spec names each channel's `DATA/derived/channels/<stem>/CHn.npy`, so the job needs no database there.
    The preview's bar jumped (27 → 32 → 22 %) because an older loader kept polling beside the new one; a
    failed run is retried on its own row instead of adding a card; *Save .sh* downloads the script.
  - **2026-10-09, the researcher's question "the page has already scored all the matches — why does the run take
    longer?"** It found the same matches; the time was the null, drawn again as 200 chain runs per channel.
    Now the run's null is the researcher's choice on the apply bar: **from the preview** (default — the draws
    the preview made, 5 over a long scope or 200 over a short one; drawn first inside the job if the page has
    none yet; the run then writes the matches alone, seconds), **rigorous** (200 paired chain runs, the old
    behaviour, hours), or **off**. All three are real run rows: *Send N unjudged to Review* and Compare work,
    and the scoreboard's *null expects* reads the preview's or the cluster's null at the cut (it read "no null
    run" for an imported one). Verified in the sandbox: 3 ch × 4 h, no cut — 600 found, null expects 598.9,
    about a minute. *Save as template* on a taken name updates that template. The Runs card in seed mode lists
    seed searches only, with *Seed search* pressed; the browsed detection's band was drawn half a window early
    (centred on the start) and now is the span the server sends.
  - What the HPC route does **not** do: move files. The spec and script are written under
    `HPC/Detection/generated/` (sandbox: `webui/runtime/<stamp>/hpc/`); syncing them to rangpur, `sbatch`, and
    bringing `<name>.result.json` back are by hand, as for every other generated job. The cluster needs the repo and
    a database whose `recordings` rows name the same source file and channel indices.

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
| A seed search over the whole recording, on the HPC, brought back and judged — the first real RQ2 answer at scale | the researcher, with the SLURM route of 2026-10-06 |
| ~~The exclusion zone is m/4 (stumpy's default), not §7.6's m/2~~ — a parameter, default m/2, settable (Round 11) | `AD`, done 2026-10-05 |

## How it gets answered

Follow `RESEARCH_RUNBOOK.md` Q2:

1. Promote an exemplar in Review (`S`); the toast names entry N.
2. *Seed search in Discovery →*, or Seed search › *change seed* › filter *review*.
3. Choose a cut against the null, and *Run seed search* — or, over ten minutes, *Create SLURM script*, run it on
   the cluster, and *Import HPC result*.
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
- 2026-10-06 · researcher's second report · the Seed page says what a search will cost before the button (work over a rate, measured once a search has finished here) and shows the job's own progress with time left; a cut can be chosen when the null gives none; a saved template's name becomes the next run's; Retry on a failed run is a real retry; a picked match is drawn large under the cards.
- 2026-10-06 · researcher's third report · the "5 hours" was twenty copies of one preview sharing the CPU (a POST now joins the running job; 43 s alone); a seed search is costed by the measured rate and, over ten minutes, is a SLURM job (`Working.discovery.seed_job`: spec with the exemplar's samples and the null, headless compute, result imported — histogram from the cluster, run row finished here); a run can be removed from a session (×) and brought back from History.
- 2026-10-07 · researcher's fourth report · the seed job checkpoints and resubmits itself; every SLURM script lists what it needs on the cluster; a failed run is retried on its own row; the preview's bar no longer jumps between two loaders; *Save .sh* and *Select all* channels.
- 2026-10-09 · fixup-jobs · a seed search sent to the cluster is a row on the Jobs board (*Waiting on the cluster*): *written* until its result file is back, *running on the cluster · checkpoint back* while the file reads incomplete (channels done of total), *results back · not imported* once complete, *results imported* after the import. Its result can be imported from that row by path (`POST /api/hpc/seed/import`, the Seed page's own import function), as well as from the Seed page's file picker.
- 2026-10-09 · researcher's fifth report · the run's null is a choice (preview / rigorous / off) and a preview-null run is seconds; the scoreboard scores an imported or preview null; Save as template updates; the Runs card follows the mode; the browse band is the detection's own span; × beside the pick box.
