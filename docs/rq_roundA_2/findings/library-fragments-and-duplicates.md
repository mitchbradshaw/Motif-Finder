# Library audit, 2026-10-17: families hold pieces and copies of events, not only events

**Read this before building anything that trains on, counts or scores Library families** (the RQ1 family classifier
above all, `../RQ1b-family-classifier.md`). The researcher's decision on 2026-10-17: duplicates and fragments are
handled when RQ1's training starts, not before. Nothing here was changed in the database.

Re-measure with `python scripts/library_fragment_audit.py [--grouping N]`. It is read-only: a backup-API snapshot plus
memory-mapped channels. It reproduces every number below in about a second.

## In plain words

Picture filming one dive and cutting the film into overlapping two-second clips, then filing each clip by what it looks
like. The "falling", "bottom" and "climbing" folders all fill up, yet there was only ever one dive. That is what
happened to two-thirds of the Library.

Separately, many oyster (M2_aug) events were filed twice, so a family can look twice as big as the number of real
events in it. A model trained on families as they stand would learn to tell the first half of a rise from its second
half, mostly from one 20-minute recording. Its test set would hold near-copies of its training set.

## What was measured

Snapshot of `DATA/db/annotations.sqlite`, 2026-10-17. Ward grouping **5** (cut 0.60, 149 families, 3,239 of 3,627
members assigned). Definitions are in the script's docstring:

- **twin**: the same span ±10 %;
- **nested**: inside a member at least 1.5× longer;
- **piece**: overlapping a member of another family by at least 20 %;
- **distinct events**: members merged when they overlap by at least 50 %.

| corpus (tag) | file | members | median length | twin | nested | piece |
|---|---|---|---|---|---|---|
| `reishi_10hz` (framing `sliding`) | `Fig2A_dt0p1.csv` — **5 channels × 20 min at 10 Hz** | 2,425 (67 %) | 2.4 s | 0 % | 16 % | **61 %** |
| `oyster` (`drop_motifs10`) | M2_aug | 749 | 195 s | 26 % | 72 % | 36 % |
| none (`drop_motifs5`, the seed store) | M2_aug, 13 on Mushroom | 349 | 205 s | **55 %** | 86 % | 52 % |
| `sp385` | `Mushroom_260720_…_CH14_fs1` | 76 | 68.5 s | 0 % | 5 % | 32 % |
| Review-promoted entries | M2_aug (23), Mushroom (1) | 24 | 816 s (up to ~9 h) | 0 % | 17 % | 0 % |
| annotation type specimens | M2_aug | 4 | 328 s | 50 % | 75 % | 50 % |

### 1. Pieces: one 20-minute recording, cut into overlapping clips

- `Fig2A_dt0p1.csv` was imported with a **sliding** frame. Consecutive members overlap: on each channel they form runs
  with a median of 8 members over about 21 s. Those runs span a median of **8 families**.
- **Example**, Fig2A CH0 at 266.6–280.2 s, is six members in five families: drop (family 150) → trough (194) → rise (134)
  → trough (150) → rise (141) → rise (121). This is the researcher's question exactly: a sharkfin filed as its drop, its
  turn and its rise.
- **These pieces dominate 115 of the 149 families** (by dominant corpus: reishi 115, oyster 23, seed store 10, sp385 1).
- Families 117, 119 and 128 are about 1-second rises (10 samples at 10 Hz).
- In this corpus, a piece's shape is followed most often by: rise → rise (262), trough → trough (237), trough → rise
  (232), rise → trough (147), drop → trough (119).

### 2. Copies: M2_aug events imported twice (sometimes four times)

- 382 of the 1,098 M2-side members have a **twin**: the same event from both `drop_motifs5` and `drop_motifs10`, with
  spans a few samples apart. Their content hashes therefore differ, so `LIBRARY_STORAGE.md` §5.2 resolved only the 61
  exact duplicates and *flagged* the rest. Example: members 147 and 588, both CH0 at 291.689 h.
- **Some events are held four times**, because catalogue ids `id003` and `id021` label the same stretch: CH0
  314.655–316.83 h, families 17 and 109.
- Twins usually land in the same family, which inflates its size.

### 3. Nesting, and why most of it is not the problem

- 72–86 % of M2 members sit inside a longer member. Most of those containers are the **24 Review-promoted entries**
  (median 816 s, up to ~9 h). These are whole trains or regions promoted as single entries, and they are in no grouping.
- Among event-store members themselves, nesting is about 16 %. Example: CH0 314.52–314.67 h, a 545 s member (family
  109) containing 7 shorter members from families 12, 18 and 140.

### 4. What the researcher's own verdicts cover

- **Verdicts given:** 234 `library_review` verdicts (2026-10-16: 26, 2026-10-17: 208), over ten families — Review queues
  9–18. They split 197 interesting, 35 not, 1 unsure, 1 artifact. 31 of the 35 "not interesting" were Fig2A pieces.
- **The 197 accepted members are 142 distinct events.**

| family | accepted members | distinct events | channels | shape (rough rule) |
|---|---|---|---|---|
| 30 | 58 | 41 | 7 | drop, median 533 s |
| 166 | 22 | 12 | **1** (one train, CH0 291.7–293.3 h) | trough |
| 17 | 21 | 8 | **1** | peak/sharkfin, 431 s |
| 154 | 19 | 18 | 6 | trough, 44 s |
| 63 | 17 | 12 | 3 | trough |
| 164 | 17 | 15 | 5 | trough, 5 s (reishi) |
| 37 | 14 | 10 | 2 | peak/sharkfin |
| 165 | 12 | 11 | 6 | trough, 5 s (reishi) |
| 108 | 11 | 11 | 5 | peak, ~35 min |
| 109 | 6 | 4 | 2 | peak |

- **The largest human-verified sets are seed-search matches, not families.** These are distinct by construction,
  because the exclusion zone is m/2:
  - id010 dip (family 24's medoid, 105 s, 3 channels): **256 of 263 accepted**;
  - id020 (family 23's medoid, 816 s, 16 channels): **94 of 104 judged accepted**;
  - 240 and 81 of those accepted matches overlap no Library member.
- **Neither dip search can feed the Library yet.** Discovery › Runs › *Add N matches to E-xxxx* only adds matches for a
  seed picked as a Library entry. Both dip searches used the Seed page's "Family medoid" tab: 16 catalogue spans read
  from `DATA/library_seed/drop_motifs5`, which are not Library families. Such a seed carries no `entryId`
  (`webui/server/discovery.py::_seed_by_id`), and the button refuses with "this run's seed is not a Library entry".
  `../prompts/P4-seed-search-on-demand.md` links medoid seeds to the Library entry with the same span and backfills
  the two runs. Until then, start a seed from Library › Family › *Seed search in Discovery*, which carries an entry.

### 5. What a ≤ 10-family grouping would look like

- No saved shape grouping has ≤ 10 families; groupings 7 and 9 are sequences and amplitude bins.
- Rebuilding grouping 5's tree and cutting at k = 10 merges the ten reviewed families into 5 coarse clusters of 223–515
  members each. The other 5 clusters hold 3 direct "yes" between them.
- A coarser cut does not make clean classes. Named, verified classes do (`../RQ1b-family-classifier.md`).

## What it means for RQ1b (and anything else that counts families)

1. **Count distinct events, not members.** Report both.
2. **Keep the reishi `sliding` pieces out of a classifier**, or merge each run of pieces into one event first. Their
   corpus tag (`reishi_10hz`, framing `sliding`) selects them in one query.
3. **Collapse twins:** keep one member per twin set (the `drop_motifs10` one, whose spans the newer detector drew).
4. **Split train and test by channel or by time block, never by member**, or near-copies sit on both sides.
5. **Single-channel classes** (166, 17) cannot show generalisation. Merge them, or add events from other channels
   (seed-search matches).
6. `POST /api/library/groupings/run` cannot filter by corpus or source today (its body has `limit` only,
   `webui/server/library.py::GroupingRunBody`). A clean grouping needs that filter, or a script around
   `Working.library.grouping.engine.run_grouping` (as `scripts/populate_library.py` does).

The shape labels come from a rough rule on raw slices and are for orientation only. Every overlap, twin and count above
is exact arithmetic on the stored sample indices.
