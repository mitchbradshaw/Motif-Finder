# Accepted catalogue reconciliation — 8 November 2026

An accepted label says that a person found something worth keeping. It does not, by itself, specify how many events are present or where each event begins and finishes. This inventory preserves those judgements while making those remaining boundary decisions visible. For future family classifiers, regroup the checked waveforms by shape; g-12's recording labels describe the inventory's sources.

## What is available

- [Accepted-only Library inventory, g-12](http://127.0.0.1:8765/#/library/atlas?grouping=g-12&floor=0): **1,762 accepted-span representatives**, grouped by recording. These eight groups are source groups, not eight waveform families. The Atlas's minimum-members display filter may hide SH/SO; set it to 1 to show every group. g-11 remains the historical morphology grouping.
- [Boundary editor](http://127.0.0.1:8767/boundary_review.html): 1,762 event spans, plus **2,595 labelled windows/regions** available for extraction. The generated waveform HTML is in the main checkout's ignored `DATA/derived/accepted_catalogue_review/`; the reusable template and generator are under `scripts/thesis/`.
- `accepted_spans.csv`: combined span, representative, source references, queue membership and boundary status.
- `accepted_observations.csv`: all positive source records, including fixed windows and wider-project recordings.
- `accepted_regions.csv`: fixed windows and known multi-event regions, kept out of event merging.
- `catalogue.json`: observations, canonical recording coordinates and event/source links.

| Thesis recording | Accepted-span entries |
|---|---:|
| M2_aug | 1,036 |
| M2_concat | 89 |
| M4 | 67 |
| LM | 187 |
| CO | 89 |
| MJu26a | 287 |
| SH | 4 |
| SO | 3 |
| **Total** | **1,762** |

The wider-project export contains another 55 span components: 34 Fig2A, 20 *S. commune*, and one legacy M2_aug_fs2 occurrence whose time correspondence has not been established here. That legacy occurrence also has both an artefact and a positive annotation; both are retained and flagged. They remain recorded and are outside this eight-recording thesis inventory. They have not been silently discarded or counted as independent thesis datasets. The separate window_verdicts store was checked and is empty; a future refresh refuses to overlook newly added rows there.

At cutoff adjudication 52,465 / annotation 12,834 / review audit 5,495, there are 4,938 positive records. This is **not** 4,938 independent events or human looks: it includes 2,568 fixed-window labels, repeated views of the same event, two train-region records and 175 train-member transcriptions of a bulk decision. The full queue-38 judgement set is still unfinished. Its saved progress was verified after the site restart: 164/916 presentations judged, 752 remaining.

## Why unjudged members were in the Library

The event-store importer admitted drop-motif proposals before individual review. Grouping those proposals did not supply human verdicts. In g-11, the current resolver reports 333 unjudged, 728 interesting, 31 not interesting and five artefacts. Some positive statuses are inferred from containing labelled windows, which is weaker than an individual event judgement. This explains why the older Library cannot simply be called a catalogue of accepted events.

g-12 selects explicit accepted event-span observations, plus the researcher's explicitly accepted train members. Fixed-window positives are retained as extraction material. A plausible waveform or membership of a family is never converted automatically into a human verdict.

## Identity and boundaries

1. Use the latest **own** adjudication of each detection. Carried copies are not additional looks. Deleted annotations and surrogate-derived detections are excluded.
2. Preserve all live annotation sources. Separate grid/blind-test windows and known sequences from event spans.
3. Map physical copies before comparing occurrences. The five L_LM channels correspond to zero-based MJu26a channels 9, 12, 13, 14 and 15. The CH14 excerpt has its registered parent offset and decimation. Two-Hz interval edges map to the coverage of five 10-Hz source samples; the block's sample centre is +0.2 s. Copies at different rates are not independent events.
4. Combine ordinary positive overlaps on one physical channel, preserving all source references. Merely touching spans remain separate. Different channels never merge on timing alone.
5. Separate train extrema and explicit human splits take precedence over their broad context. Overlapping recovery tails do not glue a train into one event. A later checked trim/extension is authoritative; its original observations remain provenance.
6. Display an original reviewed representative in the Library. The complete union is retained in the external catalogue. An algorithmic union is not described as a human redraw.

All 1,762 working entries still require boundary checks before they can support a final census of complete, individual waveforms. The initial automatic event-span audit flagged 962 entries, including 138 with multiple prominent extrema. Those flags are prompts to inspect, not validated splits. Lack of a flag does not certify an extent.

## Two MJu26a case studies

The author explicitly requested both trains and inclusion of their spikes. Their proposed members were recorded with **train-level acceptance** and **machine-proposed boundaries**. They are not new individually blinded decisions, and original positive, negative and unsure looks remain available unchanged.

| Case | Source coverage | Proposed members | Prominence floor | Earlier own detector look linked to member |
|---|---|---:|---:|---:|
| CH15 long train | 206–283 h | 143 | 2 mV | 117 |
| CH14 excerpt | Four hours; registered excerpt of the full recording | 32 | 1 mV | 7 |

The extraction smooths with a 0.5-second Gaussian sigma, finds negative local extrema separated by at least 15 seconds, and proposes widths at 95% of each extremum's prominence. This can distinguish adjacent extrema while still leaving ambiguous shoulders, interrupted recoveries and small secondary excursions for inspection.

Counts depend on the chosen floor. CH15 gives 167 / 143 / 106 extrema at 1 / 2 / 5 mV; the excerpt gives 42 / 32 / 25 at 0.5 / 1 / 2 mV. Thus **175 is a documented working extraction, not proof that every small spike has been enumerated**. Smaller features remain in the surrounding signal and can be added in boundary review. No physiological threshold is inferred from these choices.

The median spacing of the proposed extrema is 1,515.35 s (25.3 min) on CH15 and 298 s (5.0 min) in the excerpt. These are threshold-dependent **peak-to-peak** intervals, not final onset-to-onset results. Durations must wait for checked onset/recovery boundaries.

Suggested Chapter 10 aim: demonstrate how accepted activity is resolved into individual waveforms and how morphology and recurrence vary within a train. Show the complete train, enlarged examples, waveform overlays and interval/amplitude changes along it. Keep acceptance source and boundary method explicit. This is a selected-case description; it does not establish propagation, a universal fungal waveform, or an excitable-system model. The historical CH1 oscillation/B10 and earlier B3 cases are different selections.

Figures already available:

- `mju_trains_audit.png`: both trains and older own review spans; accepted spans can end before recovery.
- `mju_ch15_long.png`, `mju_ch14_excerpt.png`: numbered proposed extrema over the whole selected coverage.
- `boundary_review_preview.png`: the working editor with surrounding context.

For the final thesis figure, use a descriptive caption specifying recording/channel, absolute or excerpt-relative time, voltage units, any baseline difference between the legacy copy and canonical trace, shading/markers, smoothing, prominence/separation rules, and the distinction between train acceptance and checked individual boundaries.

## Checking and applying boundaries

In the editor, choose accepted spans, train members, or windows/regions to extract. Drag over one complete event; Shift-drag adds a separate event. Numeric start/end fields permit trimming or extension, and **More context** expands the view. Use **Open precise waveform in MycoWave** when the envelope or available context is insufficient. Save the checked selections and export the decisions. Browser choices do not write to the database until that export is explicitly applied.

The import validates the saved waveform snapshot, recording and interval bounds. It writes explicit human boundary-review annotations and one audit per decision. Original detector judgements are preserved, and the publisher refreshes the same g-12 grouping.

From PowerShell, refresh after queue 38 is finished:

```powershell
Set-Location C:/Users/mmebr/Documents/CNN
$cataloguePython = 'C:/ProgramData/anaconda3/python.exe'
$catalogueScripts = 'C:/Users/mmebr/Documents/CNN-thesis/scripts/thesis'
& $cataloguePython "$catalogueScripts/publish_accepted_catalogue.py" --project-root . --apply
& $cataloguePython "$catalogueScripts/accepted_catalogue.py" --project-root .
& $cataloguePython "$catalogueScripts/accepted_boundary_review.py" --project-root .
```

To apply a boundary export, add `--decisions 'C:/Users/mmebr/Downloads/accepted_boundary_decisions_<snapshot>.json'` to the publisher invocation. Preview without `--apply` first if desired. Each application takes a consistent SQLite backup, including the live WAL. Repeating a train import or the same boundary decision does not duplicate annotations or members; refresh reuses g-12.

The boundary viewer is served on loopback port 8767. If it needs restarting:

```powershell
& C:/ProgramData/anaconda3/python.exe -m http.server 8767 --bind 127.0.0.1 --directory C:/Users/mmebr/Documents/CNN/DATA/derived/accepted_catalogue_review
```

## Verification and thesis integration

- Pre-change SQLite backup: `C:/Users/mmebr/Documents/CNN/DATA/db/backups/accepted_catalogue_20261108_144554.sqlite`.
- Compared original annotations, entry metadata, saved groupings and grouping assignments against that backup: unchanged. Reused member import identities were preserved; source links are recorded as revisions. Foreign-key checks: zero issues before and after.
- Live Library API: eight source groups, all members judged. A review-status fix now follows an explicit current human-revision annotation before older machine judgements. The fix and regression tests are saved in both the thesis worktree and main checkout; the local site has restarted since that change.
- 25 targeted catalogue/revision/verdict tests pass, including repeat imports, preservation of source-store hashes, explicit split round trips, context/recording validation, legacy span-coordinate conversion and revision-verdict precedence. The main checkout's 20 verdict/revision tests also pass. Four import-boundary tests passed in the wider targeted run.
- Headless browser: train/region filtering, two waveform drags, save and export passed without page errors. Synthetic test choices were never applied to research data.
- Keep the historical 716 blind accepted spans for accepted/rejected comparisons. For Chapter 9's new catalogue overview, finish the transfer review, check/extract boundaries, freeze the inventory, and remake the statistics/gallery against that same population. Retain source-stratified summaries because seed retrieval and single-reviewer selection affect the pool.

Chapter 9 response notes and Chapter 10's purple instructions now carry these decisions. No full thesis PDF was rebuilt, no classifier was retrained, and historical classifier/blind-panel scores were not recomputed.
