# B6 and B12 with the corrected species labels (5 Nov)

**In plain words.** Two Chapter 10 studies asked whether shapes differ by species. They had been run with M2_concat
labelled lion's mane, and with chocolate oyster counted as its own species. Both labels were wrong (the researcher,
5 Nov): M2_concat is oyster, and chocolate oyster is a strain of the same species, *Pleurotus ostreatus*. Re-run with
nothing else changed, the answer is the same in kind and clearer: **recordings differ, and species do not differ
beyond what two recordings of one species already do.**

Script: `scripts/thesis/species_rerun_b6_b12.py` (reads the 3 Nov outputs in `docs/thesis/data/ch10_b6/` and
`ch10_b12/`; no database). Labels: species *P. ostreatus* = M2_aug, M2_concat, CO; *H. erinaceus* = LM and MJu26a's
five-channel copy. Strain: oyster = M2_aug, M2_concat; chocolate oyster = CO; lion's mane = LM, MJu26a copy.

## B6: do families recur across species? (g-11, 42 families, 804 members; 10,000 shuffles)

| Labelling | Families shared | Null mean | p (more specific) | MI bits | Null MI | p (MI) |
|---|---|---|---|---|---|---|
| recording (4) | 39 of 42 | 41.3 | 0.023 | 0.219 | 0.128 | 0.0001 |
| **species (2)** | **28 of 42** | 33.8 | **0.005** | 0.078 | 0.042 | 0.0002 |
| strain (3) | 38 of 42 | 39.9 | 0.14 | 0.155 | 0.085 | 0.0001 |
| recordings within *P. ostreatus* (3) | 36 | 38.8 | 0.07 | 0.156 | 0.094 | 0.0001 |

- 28 of 42 families hold members of both species; 39 of 42 hold two or more recordings.
- Families lean by species beyond chance (fewer shared than the null, p = 0.005), but the members are 728
  *P. ostreatus* against 76 *H. erinaceus* (LM only in g-11), so the species contrast is one lion's mane recording.
- Families lean by recording within one species about as much as by strain (MI 0.156 against 0.155 bits).
- **Replaces** "39 of 42 families on two or more recordings and species; the mix is not random (0.22 against
  0.13 bits)": the recording half stands; the species half becomes 28 of 42, leaning by species (p = 0.005) with
  one lion's mane recording.

## B12: do shapes and intervals differ by species? (716 judged events; 40 channels)

Shapes, plain shuffle null, Benjamini–Hochberg over 15 features:

| Level | Features passing BH | Normalised waveform |
|---|---|---|
| **species (2)** | **1 of 15** (drop share: 93 % against 85 %) | R² = 0.004, p = 0.03 (q = 0.13, fails BH) |
| strain (3) | 7 of 15 | R² = 0.005, p = 0.06 |
| recordings within *P. ostreatus* (3) | 7 of 15 | R² = 0.006, p = 0.13 |
| recordings within *H. erinaceus* (2) | 7 of 15 | R² = 0.039, p = 0.0005 |

- The one species difference, drop share, is one recording: LM 76 % drops against MJu26a's copy 97 %, CO 98 %,
  M2_concat 96 %, M2_aug 91 %. Within *H. erinaceus* the two recordings differ more (p = 0.0002) than the species do.
- With a duration control (within duration bands, or the duration residual) the species level passes 1 and 0
  features.
- Intervals (LV, CV2 per channel, `drop_detection_v1`): species p = 0.09 (LV) and 0.16 (CV2); strain 0.24 and 0.38;
  datasets **within** *P. ostreatus* p = 0.047 and 0.036 (pass BH at that level).
- **Replaces** "species not shown (R² = 0.005, p = 0.064)": species still not shown beyond recording; one feature
  (drop share) differs and is carried by one recording.

Outputs: `docs/thesis/data/ch10_b6/summary_species_5nov.json`, `families_species_5nov.csv`;
`docs/thesis/data/ch10_b12/shape_tests_5nov.csv`, `interval_tests_5nov.csv`, `events_by_species_5nov.csv`.
