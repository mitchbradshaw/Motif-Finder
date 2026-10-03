# RQ6 — Once contamination and propagation are separated out, does recurrence persist across channels and recordings?

**Status (2026-10-03): not answerable.** Classification never reaches an edge, and `motif_edge` has 0 rows. Owners:
fixup `V`, then `W`. The rule `W` stores is fully decided (Q40, Q-W5).

## In plain words

If the same motif shows up on many electrodes, that could mean three things:
- **Contamination (artifact):** one wire picking up another's noise. The motif appears on several electrodes at exactly
  the same instant.
- **Propagation:** the signal travelling through the mushroom, like a ripple. It appears on the next electrode a little
  later.
- **Real independent recurrence:** the mushroom doing the same thing again in different places or at different times.

The question is: after you remove the first two, is there still recurrence left?

## What is known

- **Recurrence is shown but unclassified.** Library › Recurrence shows 149 families: 99 occur in 2 recordings, 22 in 3,
  28 in 1. Every one has `artifactChannels` / `propChannels` / `indChannels` = 0.
- **Explore classifies one window live and stores nothing.**
- **Measured 2026-10-03** (fixup `W` Parts 1–2; numbers in `QUESTIONS.md` "Q40, measured"):
  - **The Library's classifier compares cut-out snippets, not simultaneous windows.** It returns lag 0 for events an
    hour apart, so it can't measure lag.
  - **On 4,500 real channel pairs, today's rule calls 1,412 simultaneous pairs "propagation".** These are pairs at
    |lag| ≤ 1 with 0.5 ≤ |r| < 0.99. The rule also misses 5 inverted copies, because it tests the signed r.
  - **The propagation bin has no r floor.** One pair at r = 0.16 was binned propagation.
  - **Lag ±1 is almost always negative r** (184 of 185).
- The Library's cross-recording families span import stores (`reishi_10hz`, `oyster`, `sp385`).

## Decisions already made

- **Q40a (2026-10-03): lag is measured on the same absolute window on both channels, always.** Motifs on sibling
  channels far apart in time are not "lag".
- **Q40b (2026-10-03): three bins.**
  - **Artifact:** events at the exact same time, whatever the sign of r. Common-mode is folded in.
  - **Propagation:** lag over 1 s. Sub-second propagation is out of reach at 1 Hz.
  - **Independent:** everything else.
  - The sign of r is stored on the edge.
- **Q-W5 (2026-10-03):** the thresholds are in seconds, with an r floor:
  - **artifact:** |lag| ≤ 1 s and |r| ≥ 0.5;
  - **propagation:** 1 s < |lag| ≤ 50 s and |r| ≥ 0.5;
  - **independent:** everything else.

  All three numbers are Settings keys.
- **Q40c:** co-occurrence on a sibling channel with no family member there is counted on the family, never written as
  an edge.
- **Q35 / Q36:** template runs draw 20 phase-randomised surrogates per channel, and the count drawn is printed.

## What is still needed

| Step | Owner |
|---|---|
| Edges exist (matches resolve onto members) | `V` |
| Classify a family across channels on simultaneous windows; bins stored on edges | `W` |
| The Q40 rule in named constants, printed on the page | `W` |
| Recurrence counted with artifacts excluded and propagation counted once | `W` |
| True surrogate count per channel | `T` |

## How it gets answered

Follow `RESEARCH_RUNBOOK.md` Q6:

1. Apply a template across channels, with paired surrogates.
2. Build the family's edges.
3. Run *Classify across channels*.
4. Read Recurrence with artifacts excluded and propagation counted once, against the surrogate count.

## Open decisions

None.

## Log

- 2026-10-03 · grilling · file created; W Parts 1–2 measured; Q40a/b/c and Q-W5 recorded.
