# RQ2 — Does a human-adjudicated exemplar used as a matrix-profile seed recover instances a human also accepts?

**Status (2026-10-03): not answerable.** The search runs, but no human-chosen exemplar can be picked as the seed.
`L` landed, so matches now reach Review. Owner of the rest: fixup `Y`. `T` (true null counts) and `X` (precision that
means what it says) are needed to read the result.

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
- **The seed picker can't choose that exemplar.** It shows only the first 24 of 3,603 entries, all machine-made.
  *Explore selection* is empty because Explore's *Take span for Review* is a demo write.
- **Matches now reach Review:** `fixup-L`, 2026-10-03.
- In Analyse, `detection.seed_matches` fails with `SideInputResolutionError`, because the exemplar can't be bound.

## Decisions already made

- **Q35:** a seed search draws **200** surrogates (Settings key). Every surface prints the count actually drawn.
- **Q36 / Q-Null-1:** the null is phase randomisation. Block shuffle keeps shapes intact, so it is not a shape null.
- **Q39 (2026-10-03):** a match becomes a Library member only if it is accepted (`interesting` / `seed`) and someone
  presses an explicit *Add N matches* button. *Include unjudged* is a flag that is off by default.
- **Q-D2:** precision is reported as two numbers, each printing its own rule: containment over the window labels, and
  extent over the event rows.

## What is still needed

| Step | Owner |
|---|---|
| Seed picker reaches any Library entry, at least `source_kind = 'review'` | `Y` |
| Explore's *Take span for Review* writes a real seed | `Y` |
| *Open in Runs* uses the right key; the Seed page's defects | `Y` |
| The null count printed is the count drawn; surrogate detections are never detections | `T` |
| Precision means what it says | `X` |

## How it gets answered

Follow `RESEARCH_RUNBOOK.md` Q2:

1. Promote an exemplar in Review.
2. Seed a search from it.
3. Choose a cut against the null.
4. Send the matches to Review and judge every one.
5. Read the seed run's scoreboard row (precision, recall, × null) with its null.

## Open decisions

None right now.

## Log

- 2026-10-03 · grilling · file created; `L` already landed.
