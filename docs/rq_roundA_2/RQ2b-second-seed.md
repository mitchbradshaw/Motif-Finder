# RQ2b — Does seeded search hold up on a second, different motif?

**Status (2026-10-17): the first motif is answered; the second is planned.** It extends round A's RQ2
(`../rq_roundA/RQ2-exemplar-seeded-search.md`), whose walk and machinery are unchanged.

## In plain words

You point at one checked shape and ask the computer for more like it, then check what it finds. One shape has been
tried, and you agreed with nearly everything it found. One success could be luck, or a property of that shape. So try a
clearly different shape, and compare how often you agree with how often you call a *random* window interesting.

## What is known

| Search | Seed | Scope | Matches | Accepted / judged |
|---|---|---|---|---|
| `dip_search` (run group 9; its runs were removed from the session, verdicts kept) | id010 medoid, family 24 (Ward g5), 105 s, CH4_A2 | 3 channels, 721 h | 263 | **256 / 263 (97 %)** |
| `dip_search_allch` (discovery run 13, live) | id020 medoid, family 23, 816 s, CH1_A1 | 16 channels, 721 h | 115 | **94 / 104 (90 %)**, 1 unsure |
| `trough_search` (discovery run 19, live) | id022 medoid, family 166, 327 s | 2 channels | 9 | not judged |

- **A base rate to read against:** in RQ1's blind labelling the researcher called **235 of 1,084** random 1-, 10- and
  30-minute windows interesting (about 22 %). That is not a matched control: those windows were judged blind, while
  seed matches are judged knowing where they came from.
- **Recall** is still round A's §4.6 rule (0 by construction), so read precision (both figures) and × null.
- **The cluster route round-trips for seed searches:** *Create SLURM script*, one channel per job, resubmitting itself,
  then *Import HPC result*. Template runs do not round-trip yet (`RQ4b`, P2).
- ~~**The Seed page computes as soon as a seed is chosen.** The researcher wants nothing to run until a button is pressed,
  and a wider choice of seeds (P4).~~ Done by P4 (below), 2026-10-17.
- **The Seed page runs nothing until asked** (2026-10-17, P4: branch `a2/p4-seed-on-demand`). Choosing a seed, a
  channel, the section, the scale bank or the exclusion zone only changes the query; *Run preview* starts the preview
  and shows its estimate (seconds, draws, channels, measured or assumed rate) first; a preview can be cancelled from its
  progress view, and a cancelled preview is never kept or reused by a run. *Run seed search* is unchanged; with no
  preview and no typed cut, the apply bar says the run keeps all k = 200 matches per channel.
- **Every Library family can be the seed** (P4). The Seed page's *Family medoids* tab lists every family of a grouping
  (by default the newest shape-distance one, so grouping 5's families) by its medoid, each a Library entry, so its
  run can add its matches. The old "Family medoid" tab is renamed *Catalogue spans*: the drop-motif store's sixteen
  spans, which are not Library families. One whose span is a Library entry's now resolves to that entry.
- **The two dip searches can feed the Library once one command is run** (P4, needs the researcher's go-ahead):
  `scripts/backfill_seed_entry_ids.py --real` lists what it would change (dry run), `--real --apply` links every
  catalogue-span seed run with no entry to the entry at its seed's span, audited (Settings › Audit, kind `library`),
  idempotent, changing nothing else. Then *Add N matches* works for them.
  - 2026-10-17 · a2-p4 fix round: the dry run opens the database read-only and runs no migration. The manager's dry
    run on a read-only snapshot of the real database would link **10 runs**: 4–7 and 9–12 to entry 113, 13 to entry
    125 and 19 (`trough_search`) to entry 148; none unmatched. Not applied.

## Decisions already made

- 2026-10-17 (the researcher): run the second motif and adjudicate it like the first.
- **The second seed is a different shape from a dip:** both seeds so far are dips (recommendation, 2026-10-17).

## What is still needed

| Step | Owner |
|---|---|
| Choose the seed. Recommended: **family 30's exemplar** (falls that do not recover inside the snippet; 41 accepted distinct events on 7 channels; about 9 min). The harder alternative is a sharkfin family (37 or 108). **Start it from Library › Family 30 › *Seed search in Discovery*,** not from the Seed page's "Family medoid" tab, so the run carries a Library entry and its matches can be added. (Since P4 the Seed page's *Family medoids* tab also lists family 30, by its medoid, as a Library entry; the old tab is now *Catalogue spans*.) | researcher |
| Preview the cut against the null on a short section, then run over all channels (SLURM above the ceiling) and import | researcher |
| *Send N unjudged to Review*, judge them (cap about 100–150 under the cut), read precision (containment and extent) and × null | researcher |
| *Add N matches* for the new search, and for both dip searches once P4 links their catalogue-medoid seeds to Library entries (today the button refuses them), to grow the Library (it feeds RQ1b). P4 links new runs as they are made; the two existing dip searches need `scripts/backfill_seed_entry_ids.py --real --apply` once (dry run first, without `--apply`) | researcher, after P4 |
| Optional, cheap blinded control: mix 30–50 random windows of the seed's length into the same queue | researcher |
| ~~The Seed page runs nothing until asked, and offers more seeds~~ — done, 2026-10-17 (see *What is known*) | P4 |

## How it gets answered

Round A's RQ2 walk, unchanged. Report each seed's precision (both figures) with its null beside the 22 % base rate, and
say whether the second shape behaves like the first.

## Open decisions

- Which second seed (the recommendation above).
- Whether the blinded control is worth an hour of judging.

## Log

- 2026-10-17 · set up · the two dip searches' verdicts counted from the database; second-seed recommendation and base
  rate recorded.
- 2026-10-17 · hpc-script · SLURM job for the second seed written, not yet submitted:
  `HPC/Detection/generated/drop30_allch_16ch_0-2595600.{sh,spec.json}` (spec hash `772d402f5d05`). Seed: Library
  entry 185, `library:2:1553283:1553660`. That is family 30 (Ward grouping 5), CH2_A1 at 431.5 h, 377 s, accepted by
  the researcher, and 0.002 from the family medoid. The medoid itself (entry 191) was never judged, which is why it was
  not used. Settings match the dip searches: 16 channels, 721 h, k 200, native length, exclusion m/2, phase
  randomisation × 200. The spec carries no cut, so the import's run keeps 200 per channel; re-run at the imported
  recommended cut. Checked locally on CH2_A1 400–460 h: the seed is found at d 0, its siblings at 0.10–0.27, and the
  null minima are about 3.2.
- 2026-10-17 · hpc-script · the same search split into 16 one-channel jobs that run side by side
  (`..._parts/submit_all.sh`, written by `scripts/seed_job_parallel.py split`). The chained script runs one channel
  per job on one node. `seed_job_parallel.py merge` writes the one result the Seed page imports. On a 2-channel test,
  split then merge gave candidates and nulls identical to the chained run, with the same spec hash.
- 2026-10-17 · hpc-script · rangpur runs only 3 jobs at once, so `..._parts/submit_packs.sh` runs the same 16 parts
  as 3 jobs of 6, 5 and 5 channels, one core per channel (`seed_job_parallel.py pack`). The packs continue the parts'
  own checkpoints. Tested: a finished part is skipped, a half-done one resumes, and a merge after packing equals the
  straight run.
- 2026-10-17 · drop30 results · the 16 parts came back (18:54–19:19) and were merged into
  `HPC/Detection/generated/drop30_allch_16ch_0-2595600.result.json`. It is complete, 200 draws per channel, spec hash
  `772d402f5d05`; not yet imported or judged.
  - Against the null: every channel beats its own (p < 0.01). The page's line (α 0.01, no correction, the strictest
    channel's cut) is d ≤ 2.208, which keeps 372 matches. Each channel's own cut would keep about 669.
  - Recall on the seed's channel: on CH2_A1, 60 of the 65 family-30 members (41 of the 46 accepted) are among the
    matches under the line.
  - Recall elsewhere: the family's 6 members on CH1_A1, CH7_B2 and CH16_D2 are missed. They are a different length
    or shape (182–1443 s).
  - Not a common-mode artefact: 366 of the 372 matches have no match on another channel within 60 s.
  - Shapes: the matches look like the seed (flat, sharp fall, slow decay). The match is shape-only, so the falls range
    from under 1 mV to about 100 mV.
  - Judging: 372 is above the 100–150 cap, so judge a capped sample.
- 2026-10-17 · hpc-script · a third shape, a spike: `HPC/Detection/generated/spike37_allch_16ch_0-2595600_parts/
  submit_packs.sh` (spec hash `f6aab3cfb594`), not yet submitted.
  - Seed: Library entry 289, `library:1:894328:894476`, family 37's medoid. CH1_A1 at 248.4 h, 148 s, accepted. It
    is a fast rise of about 14 mV with an exponential decay.
  - Why this seed: the family is one burst on CH1_A1 (248.0–248.5 h), all 13 members accepted and within 0.18 of
    the medoid. It has the opposite polarity to the dips and the drop, and it is the shape the spike statistics need.
  - Settings: the same as the others.
  - Local preview with 10 draws: on CH1_A1 the seed finds all 10 spikes of its own burst (d 0–2.5), and 18 matches
    beat the null minimum; on CH4_A2, one does. It is far more selective than the drop, and the k = 200 cap does not
    bind.
- 2026-10-17 · a2-p4 · the Seed page computes only on *Run preview* / *Run seed search*; a preview can be cancelled and a
  cancelled one is never kept; every family of a grouping is a seed (*Family medoids*), the store's sixteen spans are
  *Catalogue spans*; the backfill that lets the two dip searches add their matches is written, not yet run on the real
  database.
- 2026-10-17 · a2-p4 fix round · a failed preview shows its error and traceback beside *Run preview again*; a run that
  draws the preview first is that query's preview (the page watches it, a second *Run preview* joins it); every family
  of the grouping is in the family filter; the backfill's dry run is read-only (would link 10 runs on the snapshot).
- 2026-10-18 · spike37 results · the 16 parts came back and were merged into
  `HPC/Detection/generated/spike37_allch_16ch_0-2595600.result.json`. It is complete, 200 draws per channel, spec
  hash `f6aab3cfb594`; not yet imported or judged.
  - Against the null: 8 of 16 channels beat their own null (p < 0.01). On the other 8 the closest match is no
    better than chance.
  - The page's line (α 0.01, the strictest passing channel's cut) is d ≤ 2.52, set by CH1_A1, the seed's own
    channel. It keeps **16 matches, all on CH1_A1**, 8 of which overlap the burst's 13 family-37 members (the
    members include duplicate copies).
  - Each channel's own cut would keep 34: the 16, plus 18 on CH2_A1, CH4_A2, CH9_C1, CH10_C1, CH12_C2, CH15_D2 and
    CH16_D2.
  - No match coincides with one on another channel within 60 s.
  - Reading it: the spike seed is far more selective than the drop (372 under the line). Under one line it
    effectively searches its own channel, so judge the 34 per-channel matches if the cross-channel question
    matters.
