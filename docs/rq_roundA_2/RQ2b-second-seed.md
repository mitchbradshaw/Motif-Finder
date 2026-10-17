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
- **The Seed page computes as soon as a seed is chosen.** The researcher wants nothing to run until a button is pressed,
  and a wider choice of seeds (P4).

## Decisions already made

- 2026-10-17 (the researcher): run the second motif and adjudicate it like the first.
- **The second seed is a different shape from a dip:** both seeds so far are dips (recommendation, 2026-10-17).

## What is still needed

| Step | Owner |
|---|---|
| Choose the seed. Recommended: **family 30's exemplar** (falls that do not recover inside the snippet; 41 accepted distinct events on 7 channels; about 9 min). The harder alternative is a sharkfin family (37 or 108). **Start it from Library › Family 30 › *Seed search in Discovery*,** not from the Seed page's "Family medoid" tab, so the run carries a Library entry and its matches can be added | researcher |
| Preview the cut against the null on a short section, then run over all channels (SLURM above the ceiling) and import | researcher |
| *Send N unjudged to Review*, judge them (cap about 100–150 under the cut), read precision (containment and extent) and × null | researcher |
| *Add N matches* for the new search, and for both dip searches once P4 links their catalogue-medoid seeds to Library entries (today the button refuses them), to grow the Library (it feeds RQ1b) | researcher, after P4 |
| Optional, cheap blinded control: mix 30–50 random windows of the seed's length into the same queue | researcher |
| The Seed page runs nothing until asked, and offers more seeds | P4 |

## How it gets answered

Round A's RQ2 walk, unchanged. Report each seed's precision (both figures) with its null beside the 22 % base rate, and
say whether the second shape behaves like the first.

## Open decisions

- Which second seed (the recommendation above).
- Whether the blinded control is worth an hour of judging.

## Log

- 2026-10-17 · set up · the two dip searches' verdicts counted from the database; second-seed recommendation and base
  rate recorded.
