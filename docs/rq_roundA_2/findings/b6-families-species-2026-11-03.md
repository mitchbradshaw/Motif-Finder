# B6: do the same shape families occur across recordings and species? (2026-11-03)

**Code:** `scripts/thesis/b6_families_species.py`, test `tests/test_b6_families_species.py`.
**Data:** `docs/thesis/data/ch10_b6/` (`family_by_recording.csv`, `summary.json`).
**Website screenshots:** `docs/thesis/figures/roundb/b6_*.png`.

**Read from the website:**
- `GET /api/library/recurrence?grouping=g-11`, the Recurrence page's own payload: each family's member count per
  recording and channel, noise floor on, as drawn;
- `GET /api/datasets`, the species set in Settings › Datasets.

Read-only. g-11 holds no *S. commune* member.

**Species (the researcher, 3 Nov):** M2_aug oyster; CO_fs2 chocolate oyster; M2_concat and LM_fs2 lion's mane.

## In plain words

The Library sorts events into shape families (g-11: 42 families, 804 members shown).

- **The question:** if shapes belonged to one recording or one species, most families would sit on one recording.
  If shapes were shared, families would mix recordings as freely as random labels would.
- **The test:** keep every family's size and every recording's member count, shuffle which recording each member
  came from (10,000 times), and compare.
- **Shapes are shared.** 39 of the 42 families hold members of at least two recordings, 14 hold all four, and 39 hold
  at least two of the three species. 36 hold both oyster-type and lion's mane.
- **But not at random.** Random labels would leave 41 of 42 families mixed; the real families mix a little less (39,
  p 0.023). More telling, a member's family says about twice as much about where it came from as chance allows: mutual
  information 0.22 bits against 0.13 for recordings, and 0.17 against 0.08 for species, p 0.0001 for both.
- **So** families cross recordings and species, and each recording leans towards some of them.
- **The three families on one recording only** (F-35, F-53, F-80; 11–22 members) are all M2_aug.

## What the website shows (screenshots)

| file | page | what it shows |
|---|---|---|
| `b6_recurrence_g11_counts_p1.png` | Library › Recurrence, g-11, counts | Every family (rows, with its shape, recordings and member count) against the channels of M2_aug, M2_concat and CO. |
| `b6_recurrence_g11_counts_p2.png` | the same, the next recordings | LM_fs2's channels, beside two Adamatzky species with no members. |
| `b6_atlas_g11.png` | Library › Atlas, g-11 | The 42 family shapes. |

## Protocol (fixed before the numbers)

- **Table:** the page's cells summed per family and recording (`count`, every member).
- **Labellings:** recording (4); species (3: oyster, chocolate oyster, lion's mane); and kind (2: oyster-type, meaning
  oyster and chocolate oyster, against lion's mane).
- **Statistics:**
  - shared families: families holding two or more labels;
  - mutual information I(family; label) in bits.
- **Null:** labels shuffled across members, 10,000 seeded draws.
  - p_fewer_shared = (1 + draws ≤ observed) / 10,001;
  - p_mi_higher = (1 + draws ≥ observed) / 10,001.

## Results

| labelling | labels | members per label | shared families: real | shuffled (range) | p (fewer shared) | MI real (bits) | shuffled | p (MI higher) |
|---|---|---|---|---|---|---|---|---|
| recording | 4 | M2_aug 603 · LM 76 · CO 68 · M2_concat 57 | **39** / 42 | 41.3 | 0.023 | **0.219** | 0.128 | 0.0001 |
| species | 3 | oyster 603 · lion's mane 133 · chocolate oyster 68 | **39** / 42 | 41.3 | 0.024 | **0.165** | 0.083 | 0.0001 |
| kind | 2 | oyster-type 671 · lion's mane 133 | **36** / 42 | 39.4 | 0.032 | **0.083** | 0.041 | 0.0001 |

- On all four recordings: 14 families.
- On all three species: 26.
- On exactly two species: 13.
- On one recording: 3 (F-35, F-53, F-80, all M2_aug).

## Caveats

1. **Species is confounded with recording.** There is one oyster and one chocolate-oyster recording, and two lion's
   mane recordings. A "species" leaning cannot be told from a recording leaning. B12 found the lion's mane recordings
   differ from each other in shape more than oyster from lion's mane.
2. **Members differ by source.** M2_aug's 603 members include Library seeds and seed-search matches. Every member on
   CO, LM and M2_concat is an accepted detector event from the blind queues, and a detector's choice shapes its events.
3. **Members are not independent.** Events on one channel and in one burst resemble each other, so the shuffle null
   is too narrow and the p-values are optimistic. The effect sizes (MI about twice its null) are the measure.
4. **One grouping, one cut** (g-11, shape distance 0.6, at least 10 members). It is rebuilt once as g-12 after the
   2 Hz sweep, which adds MJu26a, SH and SO.
5. **Sampling rate differs:** 1 Hz (M2) against 2 Hz (CO, LM).
