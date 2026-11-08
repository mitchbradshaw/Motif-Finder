# Completed reviews and the combined catalogue — 8 November 2026

The drop search transferred well to the other recordings: 455/457 match presentations were accepted, against
79/459 random controls. The enlarged accepted collection now contains **2,718 spans across eight recordings**.
This is a traceable inventory of accepted material. Complete individual waveform boundaries still need checking;
adding context does not by itself establish whether a fragment belongs to one drop or several.

## Review cohorts

| Queue | Selection | Result and counting unit |
|---|---|---|
| 38 | Frozen-cut drop transfer, shuffled with duration/channel-matched random controls | All 916 frozen presentations have an own verdict; matches 455/457 (99.6%, Wilson 98.4–99.9%), controls 79/459 (17.2%, 14.0–20.9%). |
| 45 | Selected MJu26a CH14 chain, BEADS plus signal threshold | Current served view: 559/559 answered, 515 accepted; 43 rejected, one unsure. The audit covers 600 underlying detection targets, including grouped members and changed answers; that is not 600 independent presentations. Accepted observations link to 509 reconciled spans. |
| 46 | Previously unanswered g-11 proposals, including omitted shapes | 322/322 resolved: 280 interesting, 24 not, 17 unsure, one artefact. There were 294 distinct directly answered member targets; saved extent edits and earlier/overlapping human evidence also resolve members. New queue verdicts link to 127 combined spans. |

Queue 38's raw 918 detections became 916 presentations at preparation. Its live counter later became 915 when a
subsequent annotation excluded an already-reviewed unsure control as prior-labelled. Its original answer remains
in the frozen analysis. Underlying overlap-set members and carried verdict copies are not extra presentations.
The 46 repeats remain reserved and unjudged. No new repeatability statistic is asserted. The label `seed` counts
as accepted; unsure and artefact answers remain in the main denominators. Excluding both leaves 455/456 matches
and 79/436 controls, with the same interpretation. Full recording-specific data: `rq2_acceptance.csv`.

## Combined catalogue

| Recording | Previous incomplete snapshot | Completed-review snapshot |
|---|---:|---:|
| M2_aug | 1,036 | 1,123 |
| M2_concat | 89 | 147 |
| M4 | 67 | 121 |
| LM | 187 | 356 |
| CO | 89 | 107 |
| MJu26a | 287 | 815 |
| SH | 4 | 27 |
| SO | 3 | 22 |
| Total | 1,762 | 2,718 |

Physical copies are reconciled before overlap unions. MJu26a 2 Hz covers five native 10 Hz samples per block;
the L_LM channels map to zero-based physical channels 9, 12, 13, 14, 15. The four-hour CH14 excerpt additionally
has its registered parent offset and decimation. All sixteen 2 Hz copies exactly matched block means of the
10 Hz data in the sampled checks. On three distinctive high-change waveform windows per L_LM channel, the
one-second-smoothed old copies correlated at least **0.9999817** with their corresponding parent channels.
Native interpolation/noise differences remain; they do not create independent recordings. Quiet-window
high-pass correlations can be low because the residual differences are a large fraction of a tiny noise signal.
The earlier quiet-window diagnostics are retained under ignored DATA; event-window checks are in
`copy_event_checks.json`. No registration metadata or arrays were rewritten.

MJu26a's 1,068 accepted source-span observations reduce to 815 components; 165 components contain source
observations from multiple recording copies. Ordinary positive overlaps merge only on the same physical
channel. Separate train peaks and explicit human splits remain separate despite overlapping recoveries.
The wider project retains another 55 components outside thesis scope. Positive fixed windows (2,568) and
accepted regions (29) remain extraction material, not 2,597 automatically individual accepted events.

The g-12 Library inventory was refreshed to 2,718 representatives, grouped by recording. It is **not** a new
morphology grouping. Historical g-11 assignments remain unchanged. Their current resolved status is 1,014
accepted, 55 rejected, six artefacts, 17 unsure and five unresolved; 752 accepted assigned representatives occupy
all 42 families (mean 17.9, largest 60), and 262 accepted representatives are omitted shapes. This retrospective
label update does not replace the historical grouping experiments or classifier evaluation populations.

## Boundaries and context

Twenty-two accepted components contain saved human extent edits; those linked annotations are retained as the
Library display revisions. No automatic suggestion was represented as a human redraw. Prominence-based context
suggestions were generated separately and did not write to the database. Inspection shows why automatic expansion
can fail: a recovery may lead into another drop, and a broad prominence crossing can include several excursions.
Thus **2,718 must not be described as a finished census of complete, unique biological events**.

A smaller, self-contained boundary editor was generated specifically for the 127 combined spans linked to queue
46: `C:/Users/mmebr/Documents/CNN/DATA/derived/accepted_catalogue_review/family_context_review.html`.
It includes wider context and supports explicit trims, extensions and splits. Its existing audit flags 84 spans,
including 30 with multiple prominent extrema; these are inspection prompts, not validated failures or splits.
Keeping this view focused avoids loading the whole several-thousand-item catalogue into a memory-heavy tab.
The exported choices use the existing validated boundary-import mechanism. Merely opening or editing the view
does not write verdicts to the project DB.

## Reproducibility and checks

- Read snapshot: main `DATA/derived/review_completion_20261108/reviews_snapshot.sqlite` (SQLite backup includes WAL).
- Cutoff IDs: adjudications 62509, annotations 13155, review_audit 7246.
- Scripts: `reviews_completed_20261108.py`, `completed_review_figures.py`, `accepted_catalogue.py`,
  `publish_accepted_catalogue.py`, `accepted_boundary_review.py`.
- Corrected catalogue provenance extraction: family-review audit target IDs name members, whereas payload
  `row_id` names the annotation. A failing regression test demonstrated the lost queue link; it now passes.
- Publication backup: main `DATA/db/backups/accepted_catalogue_20261108_190005.sqlite`.
- All annotation, adjudication and review_audit rows exactly matched the pre-publication snapshot afterwards;
  historical g-11 assignments were unchanged; foreign-key errors: zero.
- Eight focused tests passed, including boundary/provenance invariants and operational recovery retry/cache guards.
- Four new scientific figures were rendered to PDF/PNG and visually inspected. No thesis PDF was rebuilt.

Thesis updates cover Chapters 6–10, with the cross-recording seed result in Chapter 7, current populations and
context caveats in Chapter 9, and the selected longer CH14 train in Chapter 10. Frozen classifier results retain
their original chronology. Recovery computation and the remaining CNN work are documented separately in
`../recovery_return_20261108/REPORT.md`.
