# RQ3 — Is motif identity preserved under scale normalisation?

**Status (2026-10-04, after fixup `V`): answerable in the app; not yet answered.** The whole route exists and was walked
on real data in a sandbox: a seed search with a scale bank, the matches judged in Review, *Add N matches to E-xxxx*
writing an edge per distance function, and the scale read-out on the Family page filled from those rows. What is
missing is the researcher's own verdicts on enough exemplars (the walk's verdicts were placeholders), and the sharkfin
extent (Q26d) before any sharkfin row is read as a result. ~~Status (2026-10-03): not answerable. Only one of the three
distances is reachable, `motif_edge` has 0 rows, and the search across scales has no route. Owners: fixup `Y`, then
`V`.~~ (superseded by `V`.)

## In plain words

Is a slow, stretched-out version of a motif "the same motif" as a fast, squashed one? The Library assumes yes: it groups
motifs after stretching them all to the same length. If that assumption is wrong, the Library's families are wrong. So a
"no" here is a real finding, not a failure.

## What is known

- **Three distances exist in the core** (`Working/distances.py`): scale-invariant (:81), native-length (:96) and
  symbolic (:139). The Library groups by the first alone.
- ~~No page compares those distances on the same pairs.~~ **The Family page does (2026-10-04, `V`,
  `docs/prompts/fixup/reports/V-library-edges-and-scale.md`):** every accepted pair carries one `motif_edge` per
  distance function, and the scale read-out puts the scale-invariant distance beside the native-length control per
  scale factor.
- ~~The scale bank has no route.~~ **The scale bank is built (`V`):** Discovery › Seed search › *scale bank* searches
  the exemplar resampled to each length in Settings › Analysis defaults `seed.scale_bank` (default 0.8× 1× 1.25×),
  every distance on the native length's footing (`d·√(m/L)`), cross-length overlaps reduced by the page's policy, the
  scale factor on each match and on its edge, and **the null drawn per length**. `search_entry_across_durations` is
  still not routed, on purpose: measured on one hour of M2_aug CH2_A1 it made 10,491 calls in 16.4 s and wrote 30
  overlapping members, which is ≈3.4 h and ≈21,600 members per channel.
- ~~No edges exist.~~ **Edges are written (`V`)** by *Add N matches to E-xxxx* (Discovery › Runs) — only for matches
  with an accepting verdict (Q39) — each carrying the distance function, value, threshold (the run's cut), scale factor,
  detection and recipe. A match that re-finds an existing Library member resolves onto it.
- **The first real read-outs (`V`, sandbox, placeholder verdicts — not findings).** Trough exemplar E-0697 (F-173,
  102 s): accepted pairs at 0.8× had scale-invariant distance 0.96 / 1.43 against a native-length control of
  11.8 / 11.9; at 1.25×, 2.19 against 9.36. Sharkfin exemplar E-0191 (F-30, 364 s): 0.8× 0.32 vs 2.00, 1.25× median
  0.83 vs 6.72 — and the sharkfin caveat below applies to all of it. The verdicts were a rule applied by the agent
  (d < 2 accepted), so these numbers show the instrument works, not what the answer is.
- **The null differs by length.** At the same cut the null gives about twice as many matches per draw at 0.8× as at 1×
  (E-0697 at d ≤ 7: 16.7 vs 8.4 per draw; E-0191 at d ≤ 6: 7.4 vs 3.2). A shorter copy finds chance matches more easily,
  so a scale comparison must read each length against its own null — which the read-out prints beside each row.
- **The symbolic distance is a blunt instrument here:** at word length 16 it was 0.0 on most accepted pairs (SAX's
  MINDIST counts adjacent symbols as zero apart). It is recorded, but the scale-invariant/control pair carries the
  comparison.
- **Caveat (Q26d):** for sharkfins, the motif's *own length* is in question. The detector may be attaching each event's
  slow recovery to the next event. A sharkfin family's duration spread is not yet a safe basis for a scale claim. See
  `docs/prompts/fixup/future/N-event-extent.md`.

- **Nothing surrogate-derived can reach the Library by any route** (`T`, 2026-10-03, `docs/prompts/fixup/reports/T-surrogates-one-null-never-a-detection.md`): Review's
  promotion refuses a surrogate run's detection by name, as `insert_motif_entry` already did, and no queue serves one.
  So an edge `V` writes can only ever be over real matches.

- **Families are filterable above the noise floor** (`AE`, 2026-10-04, `docs/prompts/fixup/reports/AE-library-floor-and-indexes.md`).
  The Library hides members under their dataset's noise floor by default (961 of 3,239 in g-05, all `drop_motifs10`),
  and filters by the detector's **fall duration** (a range, globally comparable) and by **pure windows only** (one
  fall per window). That is the axis RQ3 is about: a family can now be read at one timescale at a time, e.g. falls of
  10–300 s (705 of 3,239 members shown with *pure only* as well). The detector's `scale_band` is shown on a card as
  provenance only — it is a within-span octave (band 1 is 174 s in one span and 4 s in another), never a filter.
  Clicking a family shows its members' real waveforms in place, so a scale question can be looked at member by member.

## Decisions already made

- **Q39:** only accepted matches become members, on an explicit act.
- **Q-X2.1:** plots use a per-card measured domain with a shared reference bar.

## What is still needed

| Step | Owner |
|---|---|
| ~~Seed search from a family / exemplar~~ | `Y` — done; the Family page's *Seed search in Discovery →* opens the exemplar's entry (`V`) |
| ~~Matches resolve onto members, **one edge per distance function**~~ | `V` — done 2026-10-04 |
| ~~Scale bank (search at 0.8× / 1× / 1.25×, or chosen factors)~~ | `V` — done 2026-10-04 |
| ~~Family page: per scale factor, matches · judged · accepted, and each distance on the same pairs~~ | `V` — done 2026-10-04 |
| The researcher's verdicts on a handful of trough exemplars' banked searches | the researcher (`RESEARCH_RUNBOOK.md` Q3) |
| A Settings control for `seed.scale_bank` (today: `PUT /api/settings/analysis-defaults`) | unowned, small |
| Sharkfin extent settled (re-hashes Library rows) | `future/N-event-extent.md` |

## How it gets answered

Follow `RESEARCH_RUNBOOK.md` Q3:

1. Pick a family.
2. Seed-search with the scale bank.
3. Judge the matches.
4. Add the accepted ones as members, with an edge per distance.
5. Read the scale read-out. The answer is that table: does acceptance hold across scale factors under the
   scale-invariant distance where the native-length control drops off?

Prefer trough families until Q26d is settled. The read-out says which morphology the exemplar is, and on a sharkfin it
says the comparison is not settled.

**One choice `V` made that the researcher may want to revisit:** an edge written from a seed search records the run's
cut as its *threshold*, and is written whatever its own distance, because the person's verdict decided membership (Q39).
So "within the cut" under the native-length control is a reading, not a gate. The read-out shows both the medians and
how many pairs sit within the cut under each function.

## Open decisions

None. **Q26d was decided 2026-10-03:** the slow rise is the *previous* event's recovery, built after the fixups
in `future/N-event-extent.md`.

## Log

- 2026-10-03 · grilling · file created; Q26d decided.
- 2026-10-03 · fixup-t · promotion from Review refuses surrogate spans; no change to what RQ3 still needs.
- 2026-10-04 · fixup-v · scale bank, *Add N matches to E-xxxx* (edges per distance), Family edge lists and the scale
  read-out built and walked; status → answerable, not yet answered.
- 2026-10-04 · fixup-ae · families filterable above the noise floor, by fall duration and by purity; scale band shown
  as provenance only; members viewable in place from the Atlas.
