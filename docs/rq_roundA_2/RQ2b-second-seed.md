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
- 2026-10-17 · a2-p4 · the Seed page computes only on *Run preview* / *Run seed search*; a preview can be cancelled and a
  cancelled one is never kept; every family of a grouping is a seed (*Family medoids*), the store's sixteen spans are
  *Catalogue spans*; the backfill that lets the two dip searches add their matches is written, not yet run on the real
  database.
- 2026-10-17 · a2-p4 fix round · a failed preview shows its error and traceback beside *Run preview again*; a run that
  draws the preview first is that query's preview (the page watches it, a second *Run preview* joins it); every family
  of the grouping is in the family filter; the backfill's dry run is read-only (would link 10 runs on the snapshot).
