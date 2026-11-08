# Individual events, parent observations and sequences — 8 November 2026

An accepted observation can contain one event, several events, or only a fragment. **It is not an event identity.**
This pass keeps those three levels separate, as requested by the author. It does not write automatic child
acceptance labels. The 2,718-entry inventory remains a snapshot of accepted observations/spans; it is not a
finished count of individually bounded waveforms.

## The 127 Library-review observations

The focused pass suggests:

| Parent role | Number |
|---|---:|
| One proposed individual event | 78 |
| Several proposed events: sequence parent | 35 |
| Unresolved | 14 |
| Total parent observations | 127 |

There are **229 distinct proposed individual extrema**, with up to 15 children supported by one parent. Each
child's identity uses canonical physical recording, extremum coordinate and polarity. Overlapping recovery
tails cannot merge two different extrema. Parent observations retain their own IDs, sources and ordered child
links; repeated observations of the same extremum share a child identity.

Method: existing fastest-edge polarity rule; 0.5-second Gaussian smoothing; prominence floor equal to the largest
of 0.1 mV, six noise estimates, or 20% of the smoothed parent's range; minimum 3-second extremum separation.
Every extremum inside the observation is linked; a fragment fallback requires at least half-span overlap with
the extremum's 95%-prominence interval and a peak no farther than min(120 s, span duration). These are operational
rules and are not a physiological event definition. A parent can therefore need further splits or edits.

Extent proposals use the existing steepest-fall shoulder/refinement functions, bounded after the preceding
extremum. Return through 95% of the amplitude is searched only until the following detected onset, with interrupted
recoveries censored. Positive excursions use the oriented waveform. Previous explicit human extent edits remain
the default selections rather than being overwritten by the new suggestions.

The focused HTML view now pre-fills separate unchecked selections. Saving is an explicit human check; export
and the existing validated importer apply it. A checked multi-event parent produces separate individual
annotations and a separate machine-assembled sequence container. Publishing links the sequence members to the
individual Library entries. No current human annotations were generated automatically by this preparation.

## The longer CH14 case

Source: physical MJu26a CH14, native 10 Hz, samples 13,770,245–17,034,004 (90.660 h), run 8750's completed reviews.
The 534 positive own source observations yield **530 supported individual trough proposals** at 1 mV prominence;
13 observations contain several retained extrema and 19 remain unresolved. All troughs at the extraction floor
are retained as recovery-search limits, including extrema outside the positive subset. The accepted-subset timing
is conditional on these selections, not a complete recording-wide census.

| Quantity | Value |
|---|---:|
| Median onset-to-trough depth | 9.220 mV |
| Depth, 5th–95th percentiles | 2.467–14.645 mV |
| Event-order-third depth medians | 6.572 / 9.126 / 10.081 mV |
| Median peak-to-peak interval | 602.9 s |
| Interval, 5th–95th percentiles | 51.28–1,358.98 s |
| Median trough-to-half-recovery | 2.491 s |
| Half recovery, 5th–95th percentiles | 0.829–17.443 s |
| Half recovery not reached within search | 1/530 |
| 95%-recovery censored at next detected onset | 25/530 |
| LV / CV2 of retained peak times | 0.708 / 0.785 |

At 1 mV, both local timing measures are below their 1,000-draw homogeneous-Poisson bands (two-sided p ≈0.002).
LV is also below the same-gaps-shuffled band (p ≈0.006). The latter result depends on smaller events:

| Prominence floor | Supported extrema | LV | Random-timing p | Shuffled-gap p |
|---|---:|---:|---:|---:|
| 0.5 mV | 542 | 0.712 | 0.002 | 0.002 |
| 1.0 mV | 530 | 0.708 | 0.002 | 0.006 |
| 2.0 mV | 503 | 0.682 | 0.002 | 0.885 |

This supports local regularity in the selected case across these extraction floors. It does not support a
threshold-independent claim about interval-order structure, a universal fungal clock, or a physiological mechanism.
The visually selected case and the historical complete-channel default-detector census answer different questions.
Half recovery is not full duration. Formal restitution requires checked identities, missing-event handling and
censoring controls; no new restitution or propagation claim is made here.

## Outputs and validation

- `family_hierarchy.json`: accepted parents, individual proposals and links, never a flat merge of a train.
- `family_individual_proposals.csv`, `family_parent_observations.csv`.
- `ch14_case.json`, `ch14_individual_proposals.csv`: measurements, sensitivity and nulls.
- New figures: `ch9_event_sequence_hierarchy`, `ch10_ch14_separate_events`, `ch10_ch14_event_measures`.
- The focused boundary HTML remains in main's ignored `DATA/derived/accepted_catalogue_review/`.
- Eleven focused tests passed across event identity, overlapping checked children, sequence/member linkage,
  source preservation, idempotent boundary import and CNN budget/retry handling.
- Focused headless browser check showed two separate pre-filled selections and green regions, zero automatically
  checked choices and no page errors. Original human judgements were not changed by that check.

The boundary importer now preserves explicitly checked overlapping children as distinct entries and stores their
ordered container separately. Its regression test checks both individual identity and onset-to-onset sequence gaps.
Those changes are saved in the thesis scripts; no boundary decisions were applied to the live research DB this turn.
