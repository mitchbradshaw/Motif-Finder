# Queue 47 scored: new proposals, background windows and repeat checks (2026-11-09)

Source: `scripts/thesis/reviews_queue47_20261109.py` (read-only; one read transaction, cutoff adjudications 65,284,
annotations 13,309, review_audit 8,148). Outputs: `docs/thesis/data/queue47_20261109/{summary.json, acceptance.csv}`
and the refreshed inventory `docs/thesis/data/accepted_catalogue_20261109/{summary.json, accepted_spans.csv}`.
Design: `docs/thesis/data/diversity_review_20261108/REPORT.md`.

## In plain words

**What the queue was.** Three kinds of item, shuffled together with their sources hidden, like a taste test where
the cups are unlabelled: 750 new detector proposals from the recordings with least material, 54 random windows of
the same length on the same channels (the "plain water" cups), and 46 items already judged in the drop-transfer panel,
shown again without warning to see whether the same answer comes back.

**What came back.**
- **New proposals:** 231 of 750 accepted (31 %), against 5 of 54 random windows (9 %). The selection found
  material three times as often as chance (Fisher's exact p = 0.0005). The rate is not a prevalence: the proposals
  were chosen for variety.
- **Repeats:** 44 of 46 got the same decision as the first time (96 %; Cohen's κ = 0.91). All 22 repeated matches
  were accepted again. Of 24 repeated random windows, one rejected window was now accepted and one accepted window
  was now "unsure". Unlike the earlier repeat check (51 positives only), this one could change in both directions.
- **The inventory** grows from 2,718 to 2,959 accepted spans. Queue 47 added 237; the other net 4 are M2_aug spans
  that boundary edits split (7 new, 3 replaced). SH grew from 27 to 79 spans and SO from 22 to 97.

**What it does not change.** No headline rate: these were selected proposals, not a stratified sample, so they are
kept apart from the detector precision estimates of Chapter 6. The 127-parent boundary review is still undone (no
checked extents in the database), so Chapter 9's event-level statistics use the binding fallback.

## Results

| Group | Recording | Accepted / reviewed | Rate (Wilson 95 %) | not | unsure | artefact |
|---|---|---|---|---|---|---|
| New proposals | CO | 35 / 75 | 46.7 % (35.8–57.8) | 23 | 16 | 1 |
| | LM | 14 / 25 | 56.0 % (37.1–73.3) | 8 | 3 | 0 |
| | M2_concat | 21 / 75 | 28.0 % (19.1–39.0) | 47 | 7 | 0 |
| | M4 | 4 / 25 | 16.0 % (6.4–34.7) | 21 | 0 | 0 |
| | MJu26a | 34 / 150 | 22.7 % (16.7–30.0) | 83 | 33 | 0 |
| | SH | 48 / 200 | 24.0 % (18.6–30.4) | 129 | 23 | 0 |
| | SO | 75 / 200 | 37.5 % (31.1–44.4) | 90 | 33 | 2 |
| | **all** | **231 / 750** | **30.8 % (27.6–34.2)** | 401 | 115 | 3 |
| Background windows | all | 5 / 54 | 9.3 % (4.0–19.9) | 48 | 0 | 1 |
| Repeats (queue 38) | all | 25 / 46 | 54.3 % | 18 | 3 | 0 |

"Accepted" is `interesting` or `seed` (four new seeds among the proposals). Unsure and artefact answers stay in the
denominators; excluding them the proposals give 231/632 (36.6 %). The researcher redrew the extent of 148
proposals, one background window and one repeat while judging.

Repeats against their frozen first answers (`earlier.verdict` in the private key):

| First answer → now | Matches | Controls |
|---|---|---|
| interesting → interesting | 21 | 2 |
| seed → interesting | 1 | 0 |
| not_interesting → not_interesting | 0 | 18 |
| not_interesting → interesting | 0 | 1 |
| not_interesting → unsure | 0 | 1 |
| interesting → unsure | 0 | 1 |
| unsure → unsure | 0 | 1 |

Same accept/not decision on 44 of 46 (95.7 %, Wilson 85.5–98.8 %), κ = 0.91.

## Inventory (thesis scope, after physical-copy and overlap reconciliation)

| | M2_aug | M2_concat | M4 | LM | CO | MJu26a | SH | SO | total |
|---|---|---|---|---|---|---|---|---|---|
| 8 Nov | 1,123 | 147 | 121 | 356 | 107 | 815 | 27 | 22 | 2,718 |
| 9 Nov | 1,127 | 168 | 126 | 370 | 143 | 849 | 79 | 97 | 2,959 |

Links: queue 38 534 spans, 45 509, 46 127, 47 261 (231 proposals, 5 background windows, 25 accepted repeats, which
were already in the inventory). Boundary status: 165 redrawn by hand during review, 175 machine-proposed train
members, 2,619 at their proposed extent.

## Thesis changes (9 Nov)

Table 5.2 (queue 47 row), Chapter 5 judging-protocol notes, Chapter 6 (repeat clause), Chapter 7 (repeat result in
the transfer section and discussion), Chapter 8 (limitation clause), Chapter 9 (inventory 2,959, new paragraph on
the diversity review, Figure 9.1 redrawn by `scripts/thesis/fig_combined_catalogue_20261109.py`), and the 2,718 → 2,959
count in Chapters 1, 8, 10, 11 and the abstract notes.
