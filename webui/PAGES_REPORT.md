# PAGES_REPORT.md — what was built, how it scored, what is left

## Summary

| workspace | page | frames | fidelity | function | final | rounds | main remaining gaps | screenshots |
|---|---|---|---|---|---|---|---|---|
| Explore | `explore.corpus` | 2 | 9 | 9 | **9** | 1 | P1 (function r1) 'matching' readout ignores the Verdict and Show filters | `screenshots/pages/explore/` |
| Explore | `explore.signal` | 5 | 8 | 9 | **8** | 1 | P1 (fidelity r1) overlay F-03 medoid flattens the live motif trace onto the top axis | `screenshots/pages/explore/` |
| Explore | `explore.cross-channel` | 2 | 9 | 9 | **9** | 1 | — | `screenshots/pages/explore/` |
| Explore | `explore.span-edit` | 1 | 9 | 9 | **9** | 1 | — | `screenshots/pages/explore/` |
| Analyse | `analyse.chain` | 10 | 8 | 8 | **8** | 1 | P1 (fidelity r1) Footer primary reads 'Pass  to Review' with the count blanked, and is dis | `screenshots/pages/analyse/` |
| Analyse | `analyse.block` | 7 | 8 | 8 | **8** | 1 | P1 (fidelity r1) Primary action clipped off the right edge at 1440 | `screenshots/pages/analyse/` |
| Analyse | `analyse.glyphs` | 1 | 9 | 8 | **8** | 1 | P1 (function r1) 'Find it in Insert a stage' does not find it | `screenshots/pages/analyse/` |
| Analyse | `analyse.interrogation` | 2 | 9 | 8 | **8** | 1 | P1 (function r1) Run chain / Re-run from 01 completes instantly — no queued → running → do | `screenshots/pages/interrogation/` |
| Analyse | `analyse.interrogation.slope` | 3 | 9 | 9 | **9** | 2 | P1 (function r1) 'units' changes only the caption text — no number, axis or angle is recom | `screenshots/pages/interrogation/` |
| Analyse | `analyse.interrogation.aggregate` | 3 | 8 | 8 | **8** | 2 | P1 (fidelity r1) F-04 reports F-03's numbers verbatim | `screenshots/pages/interrogation/` |
| Analyse | `analyse.training` | 2 | 8 | 9 | **8** | 2 | P1 (fidelity r1) failed badge lands on 03 Cluster, not 04 Encode | `screenshots/pages/training/` |
| Analyse | `analyse.training.windows` | 1 | 8 | 9 | **8** | 2 | P1 (fidelity r1) Split strip missing labels, gap markers and window ticks while the legend | `screenshots/pages/training/` |
| Analyse | `analyse.training.matrix` | 1 | 8 | 8 | **8** | 2 | P1 (function r1) Unapplied bar says 'Random Forest excluded' whatever you changed | `screenshots/pages/training/` |
| Analyse | `analyse.training.cluster` | 2 | 8 | 8 | **8** | 2 | P1 (fidelity r1) Cutline sits above the tree instead of cutting it into six | `screenshots/pages/training/` |
| Analyse | `analyse.training.encode` | 1 | 8 | 8 | **8** | 2 | P1 (function r1) Image size and PAA do not change the disk or time estimate | `screenshots/pages/training/` |
| Analyse | `analyse.training.model` | 1 | 9 | 9 | **9** | 2 | P1 (function r1) Stage-05 row contradicts the architecture you selected | `screenshots/pages/training/` |
| Discovery | `discovery.runs` | 3 | 9 | 8 | **8** | 2 | P0 (function r1) Confirming Discard run crashes the Discovery workspace | `screenshots/pages/discovery/` |
| Discovery | `discovery.seed` | 1 | 8 | 8 | **8** | 1 | P1 (fidelity r1) Done state reports two different found counts for the same run | `screenshots/pages/discovery/` |
| Discovery | `discovery.compare` | 1 | 9 | 9 | **9** | 1 | — | `screenshots/pages/discovery/` |
| Discovery | `discovery.stages` | 1 | 8 | 8 | **8** | 1 | P1 (fidelity r1) Source row badged 'differs' while its own caption says the signal is iden | `screenshots/pages/discovery/` |
| Models | `models.launch` | 2 | 9 | 9 | **9** | 1 | — | `screenshots/pages/models/` |
| Models | `models.results` | 1 | 8 | 9 | **8** | 1 | P1 (function r1) The failed-job state logs a console error | `screenshots/pages/models/` |
| Models | `models.compare` | 2 | 9 | 8 | **8** | 1 | P1 (function r1) An unrecognised query parameter crashes the whole Models workspace | `screenshots/pages/models/` |
| Models | `models.registry` | 1 | 9 | 9 | **9** | 1 | P1 (function r1) The sign-off confirmation arrives pre-ticked | `screenshots/pages/models/` |
| Review | `review.inspector` | 6 | 9 | 9 | **9** | 1 | P1 (function r1) group = family interleaves headers instead of grouping | `screenshots/pages/review/` |
| Review | `review.cluster` | 2 | 8 | 8 | **8** | 1 | P1 (fidelity r1) Title pills are truncated and clipped when the queue rail is open | `screenshots/pages/review/` |
| Library | `library.recurrence` | 1 | 8 | 9 | **8** | 1 | P1 (fidelity r1) ?sel= deep link is ignored entirely | `screenshots/pages/library/` |
| Library | `library.atlas` | 2 | 9 | 9 | **9** | 1 | — | `screenshots/pages/library/` |
| Library | `library.family` | 1 | 9 | 9 | **9** | 1 | P1 (function r1) Toast overlay covers the batch bar and swallows its clicks | `screenshots/pages/library/` |
| Library | `library.grouping` | 1 | 9 | 9 | **9** | 1 | P1 (function r1) Switching the unit to 'spike trains' lands in an invalid form | `screenshots/pages/library/` |
| Library | `library.import` | 1 | 9 | 9 | **9** | 1 | — | `screenshots/pages/library/` |
| Library | `library.window-sets` | 1 | 9 | 9 | **9** | 1 | — | `screenshots/pages/library/` |
| Library | `library.templates` | 1 | 8 | 9 | **8** | 1 | P1 (fidelity r1) 'Open in Analyse' disappears on a training template | `screenshots/pages/library/` |
| Jobs | `jobs.all` | 1 | 8 | 8 | **8** | 1 | P1 (fidelity r1) blind badge missing from review-queue table rows | `screenshots/pages/jobs/` |
| Jobs | `jobs.paused` | 1 | 9 | 8 | **8** | 1 | P1 (function r1) New SLURM script: changing the profile does not change the script | `screenshots/pages/jobs/` |
| Jobs | `jobs.upload` | 1 | 9 | 9 | **9** | 1 | — | `screenshots/pages/jobs/` |
| Jobs | `jobs.cluster` | 1 | 8 | 8 | **8** | 1 | P1 (fidelity r1) snooze reminder survives the job becoming finished and contradicts it | `screenshots/pages/jobs/` |
| Settings | `settings.datasets` | 2 | 9 | 8 | **8** | 1 | P1 (fidelity r1) Save-bar consequence contradicts the field it describes | `screenshots/pages/settings/` |
| Settings | `settings.channels-events` | 1 | 9 | 9 | **9** | 3 | P1 (fidelity r1) Event timeline drawn at full 721 h scale, so events and exclusions are un | `screenshots/pages/settings/` |
| Settings | `settings.vocabulary` | 1 | 9 | 8 | **8** | 1 | P1 (function r1) Tag 'Merge' is a dead click | `screenshots/pages/settings/` |
| Settings | `settings.nulls` | 1 | 9 | 9 | **9** | 1 | P1 (function r1) seed = 'fixed' does not reveal the seed Number field | `screenshots/pages/settings/` |
| Settings | `settings.analysis-defaults` | 1 | 8 | 8 | **8** | 1 | P1 (fidelity r1) history link missing on four of the seven recommended-value rows | `screenshots/pages/settings/` |
| Settings | `settings.compute-hpc` | 1 | 9 | 8 | **8** | 1 | P1 (function r1) Script preview emits '--gres=none' for a profile with no gres | `screenshots/pages/settings/` |
| Settings | `settings.blocks` | 1 | 9 | 9 | **9** | 1 | P1 (function r1) Disabling a block gives 'on true -> false' instead of its consequence | `screenshots/pages/settings/` |
| Settings | `settings.review-queues` | 1 | 8 | 8 | **8** | 1 | P1 (fidelity r1) Invalid cap shows no reason and the save bar restates the invalid value | `screenshots/pages/settings/` |
| Settings | `settings.models-registration` | 1 | 8 | 8 | **8** | 1 | P1 (fidelity r1) Save-bar consequence is a raw field-id restatement | `screenshots/pages/settings/` |
| Settings | `settings.library-groupings` | 1 | 8 | 8 | **8** | 1 | P1 (fidelity r1) Weights and unit edits produce a raw field-id consequence | `screenshots/pages/settings/` |
| Settings | `settings.storage-backups` | 1 | 8 | 8 | **8** | 1 | P1 (fidelity r1) Token edits break the save bar: raw list diff, truncated, label wraps | `screenshots/pages/settings/` |
| Settings | `settings.export` | 1 | 9 | 9 | **9** | 2 | P1 (fidelity r1) Include-row consequence is a constant, wrong for notes and omitted list | `screenshots/pages/settings/` |
| Settings | `settings.audit-log` | 1 | 8 | 9 | **8** | 1 | — | `screenshots/pages/settings/` |
| Settings | `settings.about` | 1 | 9 | 10 | **9** | 1 | — | `screenshots/pages/settings/` |
| Settings | `settings.display` | 1 | 8 | 9 | **8** | 2 | P1 (fidelity r1) Report-figure preview ignores line width, grid opacity and background | `screenshots/pages/settings/` |
| Settings | `settings.keyboard` | 1 | 9 | 8 | **8** | 3 | P1 (fidelity r1) Key capture does not take focus; first key press is ignored | `screenshots/pages/settings/` |

## Statistics

- Pages: **53** over **93** frame references; **549** states walked by the smoke test.
- Rated: **53**; unrated (critic did not finish): **0**.
- Mean final score: **8.4**; accepted (≥ 8): **53** of 53.
- Below 8: **0**.

## What needs your input

- `docs/wayfinder/fog-of-war.md` §Frontend design collects every question the pages raised;
  `webui/pages/fog/<unit>.md` holds each builder's raw notes.
- `webui/BUILD_PROGRESS.md` lists the shared-kit requests builders worked around, queued for a later pass.
