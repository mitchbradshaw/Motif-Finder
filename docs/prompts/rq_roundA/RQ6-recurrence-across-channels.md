# RQ6 — Once contamination and propagation are separated out, does recurrence persist across channels and recordings?

**Status (2026-10-04, after the Q40d plots): not yet answerable — `W`'s bins do not beat chance; `AD` and the Library prompt come first.** ~~Answerable for any family whose members share a recording, not yet answered.~~ `W` built the
classification on simultaneous windows and the counts with the bins taken out. **One sub-decision is open (Q40d, below)
and it moves the answer a lot.** ~~Status (2026-10-03): not answerable. Classification never reaches an edge, and
`motif_edge` has 0 rows.~~

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

- **Built 2026-10-04 (fixup `W`, `docs/prompts/fixup/reports/W-cross-channel-onto-edges.md`):**
  - *Classify across channels* on Library › Family (and from Explore › Cross-channel when opened from a family) is a
    job with per-channel progress. Each member is compared with every other channel of its recording **over the same
    absolute samples**; a sibling member within 50 s is classified as a pair on the union of the two spans and the bin,
    lag (in seconds) and signed r are written onto their edge; no member there → a *co-occurrence without a member*,
    counted, never an edge.
  - The rule is the decided one, three Settings keys (Analysis defaults), printed beside every count.
  - Library › Recurrence counts *every member · excluding artifacts · propagation counted once*; artifact cells stay red.
  - Explore › Cross-channel on an edge's window recomputes the same lag, r and bin.
  - **Measured on three real families** (sandbox, default rule; mostly the 5-channel 10 Hz `Fig2A_dt0p1` recording):

    | family | members | pairs: artifact · propagation · independent | without a member: artifact · propagation | recurrence: all · excl. artifacts · propagation once |
    |---|---|---|---|---|
    | F-130 | 55 | 17 · 24 · 19 | 228 · 22 | 55 · 33 · 29 |
    | F-119 | 40 | 25 · 18 · 13 | 109 · 6 | 40 · 17 · 14 |
    | F-39 | 40 | 13 · 23 · 19 | 70 · 8 | 40 · 22 · 18 |

  - **No null exists for these families**: their members were imported, not found by a run, so no surrogate was drawn
    and the page says so. A recurrence count read against chance needs a family built from a run with paired surrogates
    (the runbook's step 1).

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
| ~~Edges exist (matches resolve onto members)~~ | `V`, done 2026-10-04 |
| ~~Classify a family across channels on simultaneous windows; bins stored on edges~~ | `W`, done 2026-10-04 |
| ~~The Q40 rule in named constants, printed on the page~~ | `W`, done 2026-10-04 |
| ~~Recurrence counted with artifacts excluded and propagation counted once~~ | `W`, done 2026-10-04 |
| ~~Q40d answered~~ — answered 2026-10-04 (Rounds 11–12): any sibling counts, but only behind a chance test | the researcher, done |
| **A match must beat chance** (per-pair random-time null), r ≥ 0.98 for a suspected artifact, both swings over the noise floor, members under 30 samples *too short to tell*; a human confirms artifacts in a Review queue | `AD` |
| **Build the Library** (the Library prompt): the per-dataset noise-floor view filter, so RQ6 is read on families whose members are real events | `AE` (∥ `AD`), **before RQ6 is answered** |
| A family built from a run with paired surrogates, so its count has a null beside it | the researcher (runbook step 1) |
| ~~True surrogate count per channel~~ — a template run draws 20 per channel; the row prints the count drawn | `T`, done 2026-10-03 |

## How it gets answered

Follow `RESEARCH_RUNBOOK.md` Q6:

1. Apply a template across channels, with paired surrogates.
2. Build the family's edges.
3. Run *Classify across channels*.
4. Read Recurrence with artifacts excluded and propagation counted once, against the surrogate count.

## Open decisions

None. **Q40d was settled 2026-10-04** after plots (`webui/screenshots/fixup/Q40d/`): `W`'s rule passed as often at
random times as at the same instant (91 % vs 90 % on Fig2A), because the Fig2A members are ~1 s, ~0.2 mV clips of
drift. So a match must now beat its own random-time null, and a human confirms each artifact (`QUESTIONS.md`
Rounds 11–12). **Fig2A's three families (F-130, F-119, F-39) are below or near the noise floor: cross-channel
classification is not meaningful at their scale.** Their counts in *What is known* are kept as the record of the
defect, not as a result.

## Log

- 2026-10-03 · grilling · file created; W Parts 1–2 measured; Q40a/b/c and Q-W5 recorded.
- 2026-10-04 · fixup-w · classification on simultaneous windows onto edges, the decided rule as Settings keys, recurrence
  with the bins taken out, Explore agreeing with the edge; measured on F-130 / F-119 / F-39; Q40d opened.
- 2026-10-03 · fixup-t · template runs draw 20 surrogates per channel and say so (`docs/prompts/fixup/reports/T-surrogates-one-null-never-a-detection.md`); surrogate spans can no
  longer be classified or counted as recurrence.
- 2026-10-04 · grilling · Q40d plots: the rule does not beat chance; Rounds 11–12 answered; `AD` written; *build the Library* added as a step before RQ6.
