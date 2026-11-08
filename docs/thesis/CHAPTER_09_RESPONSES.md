# Chapter 9 responses — collection in progress

## Individual events and sequence parents — later 8 November steering

The author explicitly clarified that some of the 127 combined spans contain trains: separate waveforms must
remain individual events and a combined observation must become a parent train/sequence. The hierarchy pass
therefore retains 127 parent IDs and proposes 229 individual extrema: 78 single-event observations, 35 multi-event
parents and 14 unresolved. These are unchecked suggestions, not new positive judgements or a replacement for
the 2,718-observation snapshot. The focused boundary view pre-fills separate child selections and preserves
explicit saved human extents. Importing checked splits now creates individual annotations and separate sequence
containers/member links, including when checked recovery extents overlap.

Chapter 10 now contains a dedicated CH14 analysis (530 supported individual proposals, morphology/recovery,
timing nulls and threshold sensitivity). Queue 47 was prepared with 850 looks: 750 diverse proposals, 54 controls
and 46 planned RQ2 repeats. Its outcomes are pending completion; no new classifier was trained. Detailed reports:
`data/event_hierarchy_20261108/REPORT.md`, `data/diversity_review_20261108/REPORT.md`,
`data/roundb_extension_20261108/REPORT.md`.

## Completed-review integration — 8 November evening

The author completed queues 38, 45 and 46 and explicitly reiterated that MJu26a 10 Hz, MJu26a 2 Hz and L_LM
are physical copies. The combined accepted inventory is now **2,718 spans** across eight recordings, published
in g-12. Queue 38 gives 455/457 accepted matches against 79/459 controls; queue 45 links to 509 combined spans;
queue 46 resolves 280/322 proposals as interesting and its new verdicts link to 127 combined spans. Source-linked
counts can overlap. The old 716-span blind detector cohort retains its historical sampling meaning.

Incorporated the author's earlier 9.1 response and drafted the inventory/context parts of 9.2, with longer captions.
Saved extent edits remain linked; wider context is shown without automatically claiming that a neighbouring drop
belongs to the accepted fragment. Twenty-two components contain explicit saved edits. The focused family boundary
view has 127 items, 84 flagged for inspection including 30 multi-extremum flags. Boundaries remain unfinished;
no final duration census or newly clustered morphology taxonomy is asserted. Historical g-11 now has 752 accepted
assigned representatives in 42 families, while the full accepted inventory is grouped by recording.

Report: `data/reviews_completed_20261108/REPORT.md`. Current scientific figures include the source composition,
context examples, cross-recording acceptance, and the 90.7-hour CH14 train containing the older four-hour excerpt.
Recovery results are in `data/recovery_return_20261108/REPORT.md`: seed/CPU/MP finished, 183 CNN tasks remain.
The author prefers WinSCP folder paths, without collection commands. No thesis PDF build was requested or run.

## 9.1 Aims — author's response, 8 November 2026

> With the assistance of the MycoWave software, its subsequent detection algorithms, seed searches and trained models, a large library of event shapes, validated by human judgement, are assembled. The goal of this chapter is to evaluate the waveform shapes in this assembly, investigating amplitudes, durations and timing of the human-accepted events. Firstly, the accepted catalogue will be described in detail, examining its statistical measures, features, and broader distributions. Following this, specific spiking families within an individual recording, M2_aug, will be reviewed, to understand their occurrence patterns and any evidence of cross-channel replication. The variety of Library shape groups will subsequently be examined, to understand the effect of different clustering choices. Finally, this chapter will review the totality of unreviewed candidates that have been amassed with the MycoWave tool so far, totalling over 5 million (?) and explore strategies for effective filtration, prioritisation and even sampling of the unreviewed candidates to place them into human-review queues for eventual integration into the Library of accepted events. The observations in this Chapter specifically describe events from select recordings that pass the researchers acceptance criteria. Within that, there is an inherent bias which is acknowledged. These events provide the material for a morphology vocabulary and further investigation, and while they do not attempt to explain universal fungal event types, the structures of collection, analysis and identification potentially lay the groundwork for more rigorous and generalisable work to follow.

### Initial notes for chapter-end review

- Preserve the move from evaluating the tool to describing accepted waveform shapes and the stated single-reviewer selection bias.
- The existing single-recording case study is the four-hour MJu26a CH14 excerpt. The author now specifies M2_aug and cross-channel replication. At integration, use the M2_aug motif/seed evidence where appropriate and explicitly resolve the scope of the older case study.
- Distinguish raw detections, grouped candidates, overlap-filtered spans, Library members and human-accepted events. The five-recording Chapter 6 baseline is 4.82 million detections and 3.10 million candidates; “over five million unreviewed candidates” is not supported by that baseline. New partial 2 Hz outputs must not be silently pooled into its historical count.
- The later provisional machine-candidate library remains distinct from the accepted Library. Preserve review status and acknowledge that six-detector agreement alone does not establish human acceptance.
- Do not create new review queues or build/train the proposed larger-library classifier merely from this draft.
- The author explicitly permits postponing 9.2 while the 8.4 revision and HPC returns/restart bundle are processed. Defer full Chapter 9 integration to its end under the agreed workflow.


## 9.2 Accepted catalogue — author's partial response, 8 November 2026

> The following section examines the attributes of 716 accepted candidate spans across 5 different recording groups. It is intended to provide a sampled overview of the larger dataset at bay. Figure X shows a random sample of 24 accepted Library events, 6 from each dataset. It can be seen that while events vary in shape and size, a recurring theme is a sharp vertical drop followed by a recovery. Most events have narrow troughs with upward excursions, and many seem to be compound waveforms, with multiple smaller events superimposed amongst the larger one. [information about the band, scale on panels is information for figure description, my supervisor prefers longer, descriptive figure descriptions]. A detected event is not simply an isolated spike. The statistics in Table X describe the distribution of the 716 candidates [wait this differs from the library pop? why? why not perform statistics on a greater, larger set of all accepted events? pause here].

### Author's feedback and decisions

- Future context packets should retain the detailed explanations, relevant data and displayed images used for 9.2.
- The statistics figure has overlapping text and must be remade.
- Use longer descriptive figure captions, including shading, context, units and per-panel scales.
- Pause the writing loop at 9.2 while resolving the catalogue population. Do not proceed to 9.3 or finalise the statistics paragraph yet.

### Population audit notes

- The 716 accepted spans are the frozen detector-review cohort from queues 25 and 28, suitable for accepted/rejected comparisons, not a claim to contain every accepted event.
- The gallery selects accepted events from the separately assembled, deduplicated Library snapshot. Its g-11 table has 1,097 total events, 678 with an accepted part, and uses active-recording/exclusion rules different from the blind cohort.
- The promotion record shows 600 new Library entries, 30 skipped as duplicates and 86 refused on the inactive five-channel MJu26a copy, from the 716 blind accepted looks.
- These sets overlap substantially and must not be added together. A read-only half-of-shorter overlap check finds 606 of the 716 blind spans touching an accepted g-11 event; this coverage count is not a new deduplicated union census.
- For the chapter's catalogue-overview aim, a unified, provenance-preserving catalogue of accepted event spans is a coherent primary population. Keep the blinded cohort available for accepted/rejected comparison.
- A broader union needs consistent physical-recording mapping and event deduplication, removal of carried verdict copies, and separate treatment of old manually labelled fixed windows and long review regions. Seed retrieval can overrepresent a few waveforms, so source-stratified summaries should accompany pooled results.
- Keep the new transfer-review cohort distinct until its review is complete and a catalogue snapshot is frozen. No revised total is claimed from raw label counts.
- Describe compound shapes as multiple deflections within a span; the traces alone do not establish physically superimposed independent events.

## Catalogue reconciliation and event boundaries — author steering, 8 November 2026

### Later follow-up: review the remaining shape proposals

The author requested that the unjudged shape-family candidates also be reviewed and their accepted members included
in the statistical analysis. Queue **46**, “Library · unjudged shape candidates (g-11)”, now holds 322 deduplicated
g-11 representatives: 219 assigned family members and 103 omitted shapes. Five are resolved from existing human
labels, leaving 317 unanswered. All are M2_aug, separate from the ongoing transfer panel's recording groups.
Positive answers are `library_review` annotations already collected by the unified catalogue pipeline. Refresh
after the author finishes; retain this selected-proposal cohort's identity, combine repeated occurrences, and
check boundaries before final event-duration summaries. Do not pool its acceptance rate with the random blind
panel as though the sampling designs matched. Method and performance follow-up:
`data/review_followup_20261108/REPORT.md`.

The author requested an accepted catalogue spanning all human-reviewed queues, combining observations of the same occurrence. They also requested splitting spans containing several events and extending cropped spans to include the full waveform. Both the MJu26a CH15 long train (206–283 h) and the four-hour CH14 excerpt are explicitly included as accepted spike material, and are candidates for Chapter 10 case studies.

### Implemented inventory, awaiting boundary checks

- `data/accepted_catalogue/summary.json` and `catalogue.json` preserve the source observations and physical-recording mapping. The snapshot has **1,762 accepted-span entries across eight thesis recordings**: M2_aug 1,036; M2_concat 89; M4 67; LM 187; CO 89; MJu26a 287; SH 4; SO 3. This includes the partial positive judgements available from queue 38 at the saved cutoff; it is not a declaration that queue 38 is complete.
- Library **g-12** is an accepted-only inventory grouped **by recording**, not a morphology grouping. g-11's historical shape families remain available. Original entries, annotations and saved groupings were checked against the pre-change backup; original import metadata and identity hashes are preserved.
- **175 train members** are included under the author's explicit train-level acceptance: 143 on CH15 and 32 in the CH14 excerpt. Boundaries were proposed by a documented negative-peak/95%-prominence method. These are not 175 new blind judgements, not a claim of an exhaustive census at every amplitude, and not yet 175 human-checked extents.
- The Library previously admitted machine-store proposals without requiring a human verdict. Most unjudged members come from those imports. Their plausibility and family membership cannot be treated as acceptance.
- Positively labelled fixed windows (**2,568**) and longer known regions are retained separately for extraction. A 10-minute positive label is evidence about a window, not one precisely bounded event or acceptance of every deflection within it.
- Ordinary overlapping event-span observations are combined on the same physical channel. A checked split or separate train extremum takes precedence over broad overlapping context: a container cannot glue the train back together. The native source span remains the Library representative; the union and all judgement links remain in the manifest.
- `DATA/derived/accepted_catalogue_review/boundary_review.html` on the main PC supplies context, possible multi-extremum/edge flags, multiple selections, extension/trim controls and an export of explicit human choices. The generated waveform data stay in ignored DATA. Machine flags do not themselves split, accept, or reject events. The publisher validates the review export, writes traceable human annotations, and refreshes the inventory without rewriting old detector judgements.
- The new inventory is a working population of accepted spans. Do not substitute 1,762 for the old 716 and call it a final count of individually bounded events. Freeze the completed transfer queue, apply boundary decisions, then recompute Chapter 9's statistics/gallery with aligned populations and descriptive captions. No thesis PDF was rebuilt.
