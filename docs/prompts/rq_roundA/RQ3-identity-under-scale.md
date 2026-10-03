# RQ3 — Is motif identity preserved under scale normalisation?

**Status (2026-10-03): not answerable.** Only one of the three distances is reachable, `motif_edge` has 0 rows, and the
search across scales has no route. Owners: fixup `Y`, then `V`.

## In plain words

Is a slow, stretched-out version of a motif "the same motif" as a fast, squashed one? The Library assumes yes: it groups
motifs after stretching them all to the same length. If that assumption is wrong, the Library's families are wrong. So a
"no" here is a real finding, not a failure.

## What is known

- **Three distances exist in the core** (`Working/distances.py`): scale-invariant (:81), native-length (:96) and
  symbolic (:139). The Library groups by the first alone.
- **No page compares those distances** on the same pairs.
- **The scale bank has no route.** It is `search_entry_across_durations` in the core, and the Seed page shows
  *"3 lengths"* disabled.
- **No edges exist.** `motif_edge` has 0 rows, so no edge records which distance it used.
- **Caveat (Q26d):** for sharkfins, the motif's *own length* is in question. The detector may be attaching each event's
  slow recovery to the next event. A sharkfin family's duration spread is not yet a safe basis for a scale claim. See
  `docs/prompts/fixup/future/N-event-extent.md`.

## Decisions already made

- **Q39:** only accepted matches become members, on an explicit act.
- **Q-X2.1:** plots use a per-card measured domain with a shared reference bar.

## What is still needed

| Step | Owner |
|---|---|
| Seed search from a family / exemplar | `Y` |
| Matches resolve onto members, **one edge per distance function** | `V` |
| Scale bank (search at 0.8× / 1× / 1.25×, or chosen factors) | `V` |
| Family page: per scale factor, matches · judged · accepted, and each distance on the same pairs | `V` |
| Sharkfin extent settled (re-hashes Library rows) | `future/N-event-extent.md` |

## How it gets answered

Follow `RESEARCH_RUNBOOK.md` Q3:

1. Pick a family.
2. Seed-search with the scale bank.
3. Judge the matches.
4. Add the accepted ones as members, with an edge per distance.
5. Read the scale read-out. The answer is that table: does acceptance hold across scale factors under the
   scale-invariant distance where the native-length control drops off?

Prefer trough families until Q26d is settled.

## Open decisions

None. **Q26d was decided 2026-10-03:** the slow rise is the *previous* event's recovery, built after the fixups
in `future/N-event-extent.md`.

## Log

- 2026-10-03 · grilling · file created; Q26d decided.
