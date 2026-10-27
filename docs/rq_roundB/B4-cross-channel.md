# B4 — Is there evidence of a propagation lag between channels that is not artefact?

**Status (2026-10-27): designed, not built, not answered.** The plan's RQ6
(`docs/rq_roundA/RQ6-recurrence-across-channels.md`), asked again as round-B question B4. Chapter 10 lists it in
`tab:roundb`, fixed 27 Oct. The page that answers it is specified in `docs/prompts/changes/cross-channel-explorer.md`;
the decisions behind it are in `cross-channel-explorer-decisions.md`.

## In plain words

When two electrodes show activity at about the same time, there are three explanations:
- **The wiring.** One disturbance picked up through the shared ground: the same shape at the same instant, like a
  door slam shaking every room.
- **A signal travelling through the mycelium.** It reaches the next electrode a little later, with the same delay
  every time, like a train that keeps a timetable.
- **Independent activity**, or two mushrooms reacting to the same outside event.

M2's sixteen electrodes sit on four separate mushroom packs. A signal shared *between* packs therefore cannot have
travelled through mycelium, which gives a built-in control for the wiring explanation.

## What is known

- **Nothing measured on the real database yet.** `motif_edge` and `motif_member_cooccurrence` have 0 rows.
  - RQ6's 64 flagged / 123 near-copies / 97 beating chance came from a sandbox copy on grouping g-05 (4–5 Oct).
  - "No propagation survives on the current families" is from the same sandbox, on Library members.
- **A full event census exists** on four datasets. `drop_detection_v1` has one real run per channel, covering the
  whole recording:

  | Dataset | Events | Channels |
  |---|---|---|
  | M2_aug | 688 | 16 |
  | M2_concat | 310 | 16 |
  | CO_fs2 | 37 | 4 |
  | LM_fs2 | 125 | 4 |

  MJu26a_fs2, SH_fs2 and SO_fs2 (registered 27 Oct) have no runs yet.
- **Chance co-occurrence is rare.** At ~43 events per channel over 721 h, two channels share an onset within ±50 s
  about 0.07 times per pair by chance. A real excess will stand out.
- **The events are long:** v1's median is ~19 min. Their stored start is a padded window, not the onset.
- **On today's page a "propagation" badge is not evidence.** It searches every lag over a long window; 49 of 300
  pairs of unrelated random walks bin propagation (RQ6, 2026-10-16).

## Decisions

The full list is in `docs/prompts/changes/cross-channel-explorer-decisions.md` (D1–D25, X1–X5). In short:

- **The physical model.**
  - Packs A–D are separate, and propagation is judged only within a pack.
  - A cross-pack copy is an artifact, and so is every copy at that instant (common mode).
  - A cross-pack co-occurrence that is not a copy is a **shared driver**.
- **The census.**
  - The unit is the detector **census** (default `drop_detection_v1`), not Library members. Members were chosen by
    where people looked, or by which blind samples were accepted, so a co-occurrence rate built on them measures
    attention. Since the 27 Oct promotion they reach every M2_aug channel (1,451 members), CO and LM (4 of 4) and
    M2_concat (14 of 16); they enter as family labels.
  - Co-occurrence means onsets within 50 s. Lag and r are measured from 60 s before to 180 s after the earlier onset,
    with the lag searched within ±50 s.
  - Bins: artifact, propagation, shared driver, independent.
- **The nulls.**
  - Rotation for co-occurrence, breadth and shared driver.
  - Random time for waveforms.
  - For the **timetable**, lags at random times with n fixed (X1, confirmed 27 Oct).
  - Benjamini–Hochberg at q 0.05 per recording.
- **Where the answer comes from.** Only the census; spans measured by eye are reported as *looked for*.
- **Data:** all seven good datasets.

## What is still needed

| Step | Owner |
|---|---|
| S0 layout reader; S1 census (core, tables, job, card, thesis script) | manager; agent (wave 1) |
| S2 overlay page; S3 packs and positions in Settings | agents (wave 1) |
| v1 runs on MJu26a_fs2, SH_fs2, SO_fs2 | the researcher |
| What A1 and A2 mean; electrode positions from photos | the researcher |
| Census on the seven datasets; `scripts/thesis/b4_cross_channel.py` on a bridge backup | manager, after S1 |
| Judge the by-instant suspected artifacts (S5's queue) | the researcher |
| Lag against distance (S8), once positions exist | agent (wave 3) |

## How it gets answered

1. Run the census on each dataset (Explore › Cross-channel, the census card).
2. Read, per within-pack electrode pair:
   - whether co-occurrence beats rotation;
   - whether a timetable lag beats its null (after BH);
   - its lag and speed against distance, once positions exist.
3. Read the artifact instants (breadth, cross-pack) and the shared-driver rows. Judge the instants in Review.
4. The B4 claim: "a consistent propagation lag exists between electrodes … of pack …, at … s (… mm/s), beyond its
   null", or "none beyond chance on any pack". Either way, report it with the artifact and shared-driver counts beside
   it.

## Open decisions

- What A1 and A2 mean, which may split a pack into two sites.

(X1, the timetable null, was settled on 27 Oct: a random-time lag pool, because rotation is too sparse on these
events.)

## Log

- 2026-10-27 · cross-channel workshop · file created; three grilling rounds (Q1–Q26) settled the design; prompt
  `docs/prompts/changes/cross-channel-explorer.md` (S0–S9) written; v1 census counts measured read-only.
