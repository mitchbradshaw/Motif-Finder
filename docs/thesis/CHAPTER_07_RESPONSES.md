# Chapter 7 responses and chapter-end integration

Workflow requested by the author on 7 November 2026: record responses and move directly to the next section; review and integrate them together at the end of the chapter. Sections 7.1–7.3.3 were already integrated before this workflow change. The author has now supplied the final discussion response, and the chapter-end prose integration has been performed, including review of the earlier sections and the purple recommendations.

## The scale pilot — author's response (now section 7.3.5)

> Experimental tests were done to explore the validity of the seed search algorithms at different scales. Copies of a seed at 0.8x, 1x and 1.25x it's original duration were generated, and run through the same seed search process against the data and surrogates. The aim was to accommodate for events whose overall waveform remained similar while the duration changed. The pilot showed that for a 102-second trough seed, two matches at the 0.8x scale scored 0.96 and 1.43 after scale normalisation. The same two matches scored 11.8 and 11.9 on the original control length. [how many matches were found for this pilot? are there really only two cases of stretched that find new matches? if its 2 cases / 10 or so fine, if its 2 / 100, what was the point? scrap it] This implies that the duration change revealed a similar waveform that would otherwise be above the distance threshold to the original seed. Surrogate matches at the shorter event found 16.7 matches per draw, the longer event found X matches per draw against the original at 8.4 [ i thought average matches to the surrogate draws were like 0.01?], suggesting that shorter queries found chance matches more easily. [can you finish with emphasis on distinction, illustrative distance example here].

## Questions checked before presenting section 7.4

Source: `../prompts/fixup/reports/V-library-edges-and-scale.md`, sections 3–4. This is a sandbox implementation walk, not the researcher's judged experiment. Its scope was M2_aug, CH2_A1/CH6_B1/CH7_B2, 452–456 h. The run used the 102-second trough exemplar E-0697 and distance cut 7.

| Duration factor | Returned matches | Provisional accepting labels | Surrogate matches per draw, reported |
|---|---:|---:|---:|
| 0.8x | 4 | 2 | 16.68 |
| 1x | 1 | 0 | 8.36 |
| 1.25x | 2 | 1 | 10.38 |
| Total | 7 | 3 | — |

Six of the seven returned items received placeholder labels; one was left unjudged. The two shortened examples were therefore two of four returned at that length, out of seven returned across all three lengths, rather than two selected from hundreds. The accepting labels were supplied during an agent's implementation exercise, not by the author. Do not present 2/4 or 3/7 as human acceptance rates. The separate sharkfin demonstration returned 17 items and also used placeholder labels; do not combine its counts with this trough example.

The author's conditional instruction to scrap an example selected as two cases from a very large pool is not triggered by the recorded trough counts. Still keep the pilot brief and explicitly illustrative, or omit it at chapter-end if the interpretation would distract from the validated four-seed results. Do not claim that seven returned items establishes effective retrieval above chance: the loose-cut surrogate counts are larger than the corresponding real returns.

The missing longer-duration surrogate count is 10.38 (about 10.4) per draw. The original-duration figure is 8.36 (about 8.4). Shorter queries gave more null matches than either other factor in this demonstration; the three values do not establish a monotonic relationship between duration and chance matches.

The near-zero null means in the main seed experiment used seed-specific stringent null-derived cuts; this implementation walk used cut 7 and a different seed/scope. Raw counts are not interchangeable. Explain this distinction at integration rather than implying contradictory measurements.

Requested ending: the distance example shows that the normalised comparison can recognise waveform resemblance across a change in duration. It does not establish that a human would judge the retrieved windows to be the same event type. Independent human assessment against duration-specific controls is needed for that stronger claim. A mathematical shape match is not itself biological identification.

## 7.4 Discussion — author's response

> It was found that a seed search can find, automatically, unique events of interest that pass human judgement. Using a chosen exemplar event, the distance-profile algorithm with appropriate thresholds can return hundreds of similar candidates that match more closely than chance, and also pass human inspection. The drop query, for example, returned over 370 matches, and of the 100 reviewed matches, all 100 were accepted, further validified by the low acceptance rate on randomly selected windows of the same length - 9/40. This allows human review to be directed towards promising candidates, and reduces time spent examining the larger time-series dataset for the candidates themselves once a suitable exemplar is found. This conclusion is supported the comparison of detected events against the 200 surrogate draws per channel - events that match are more likely than a match by chance. Random-window controls also verify the human acceptance process, random windows have a low acceptance rate, and seed-search discovered candidates excel above that. Previously positively judged candidates also retain their positive judgement, in 100% of cases, further verifying the human acceptance process and the validity of the candidates. Further investigation with the seed-search algorithm may lead towards interrogating recurrence counts of particular events. For example, the Drop query found 372 matches across 721 hours and 16 channels, corresponding to, on average, 0.032 matches per channel-hour. Of the 372 events, X came from channel Y, and Z from channel K. [would be good to have a figure here showing distribution of the detected events for drop motifs across the 16 channels]. Future work with this algorithm may be used to determine certain timing and occurrence patterns of target motifs across a dataset. The remaining tests involve trialling the seed-search algorithm with the same seed across other datasets [I can run that now, if you give me the SLURM script for it, see repo for layout], assessing the outcomes of duration-changed seed searches, and comparing candidate acceptance rates against multiple reviewers. From the accepted matches from the seed search algorithm, and previously discussed multi-detector runs in Chapter 6, the library of event shapes extracted from mycelium signals help build the material needed to train and evaluate classifiers.

## Author's subsequent corrections

> where the drop matches were found actually seems like more of a results thing than a discussion inclusion. Maybe include a small section in chapter 7 that has a table outlining which channels detected events were found for each of the 4 seeds, then the image for the distribution of events for the drop query.

> m4 does not need to stay reserved

## Chapter-end integration decisions

- Added section 7.3.4, “Where the seed matches occurred”: all 16 channels against all four seeds at their common thresholds, with dashes for unsearched short-dip channels and zeros for searched channels with no passing match.
- Added a full 372-match drop-query time raster with per-channel counts. The requested counts are 111 on CH2_A1, 66 on CH4_A2 and 54 on CH1_A1. The new source data are `data/seed_drop_matches.csv`; the figure is `figures/new/ch7_drop_distribution.pdf`.
- The scale pilot is now 7.3.5. Retained it as an explicitly small implementation demonstration, with seven returns and placeholder labels, all three surrogate means, and the distinction between mathematical shape resemblance and human-validated identity.
- Preserved the discussion's practical argument and classifier transition, while distinguishing surrogate recurrence, matched-control acceptance and repeat-review consistency. Removed the claim that these checks independently validate biological events or an objective judgement process. The 372 returns include known catalogue members and the seed itself, so they are not all newly discovered unique events.
- Kept 0.032 matches per channel-hour as a query-dependent average. Channel counts and the distribution figure belong in Results, as the author requested.
- Prepared an additional fixed drop-seed transfer bundle for M2_concat, M4, LM, CO, MJu26a, SH and SO: seven recordings, 64 channels, 200 phase-randomised draws per channel. M4 is explicitly authorised for this follow-up after its original classifier exam. No new transfer result is included in the prose before computation and review.
- Use the existing seed-bank adapter to convert sampling rates (377 samples at 1 Hz; 754 at 2 Hz) while preserving a 377-second query and the original distance footing. The experiment distinguishes a frozen M2_aug cut from separately recalibrated target cuts. It creates no new judging queue and changes no database.
- No full thesis PDF is rebuilt. After verification, the next writing packet is Chapter 8, section 8.1 Aims, continuing the author's chapter-level collection/integration rhythm.
