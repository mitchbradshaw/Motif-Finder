# PAGES_REPORT.md — what was built, how it scored, what is left

## Summary

| workspace | page | frames | fidelity | function | final | rounds | main remaining gaps | screenshots |
|---|---|---|---|---|---|---|---|---|
| Explore | `explore.corpus` | 2 | 9 | 9 | **9** | 1 | — | `screenshots/pages/explore/` |
| Explore | `explore.signal` | 5 | 8 | — | **8** | 1 | P1 (fidelity r1) overlay F-03 medoid flattens the live motif trace onto the top axis | `screenshots/pages/explore/` |
| Explore | `explore.cross-channel` | 2 | 9 | — | **9** | 1 | — | `screenshots/pages/explore/` |
| Explore | `explore.span-edit` | 1 | 9 | — | **9** | 1 | — | `screenshots/pages/explore/` |
| Analyse | `analyse.chain` | 10 | 8 | 8 | **8** | 1 | P1 (fidelity r1) Footer primary reads 'Pass  to Review' with the count blanked, and is dis | `screenshots/pages/analyse/` |
| Analyse | `analyse.block` | 7 | 8 | — | **8** | 1 | P1 (fidelity r1) Primary action clipped off the right edge at 1440 | `screenshots/pages/analyse/` |
| Analyse | `analyse.glyphs` | 1 | 9 | — | **9** | 1 | — | `screenshots/pages/analyse/` |
| Analyse | `analyse.interrogation` | 2 | — | — | **—** | 0 | not rated | `screenshots/pages/interrogation/` |
| Analyse | `analyse.interrogation.slope` | 3 | — | — | **—** | 0 | not rated | `screenshots/pages/interrogation/` |
| Analyse | `analyse.interrogation.aggregate` | 3 | — | — | **—** | 0 | not rated | `screenshots/pages/interrogation/` |
| Analyse | `analyse.training` | 2 | — | — | **—** | 0 | not rated | `screenshots/pages/training/` |
| Analyse | `analyse.training.windows` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/training/` |
| Analyse | `analyse.training.matrix` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/training/` |
| Analyse | `analyse.training.cluster` | 2 | — | — | **—** | 0 | not rated | `screenshots/pages/training/` |
| Analyse | `analyse.training.encode` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/training/` |
| Analyse | `analyse.training.model` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/training/` |
| Discovery | `discovery.runs` | 3 | — | — | **—** | 0 | not rated | `screenshots/pages/discovery/` |
| Discovery | `discovery.seed` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/discovery/` |
| Discovery | `discovery.compare` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/discovery/` |
| Discovery | `discovery.stages` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/discovery/` |
| Models | `models.launch` | 2 | — | — | **—** | 0 | not rated | `screenshots/pages/models/` |
| Models | `models.results` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/models/` |
| Models | `models.compare` | 2 | — | — | **—** | 0 | not rated | `screenshots/pages/models/` |
| Models | `models.registry` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/models/` |
| Review | `review.inspector` | 6 | — | — | **—** | 0 | not rated | `screenshots/pages/review/` |
| Review | `review.cluster` | 2 | — | — | **—** | 0 | not rated | `screenshots/pages/review/` |
| Library | `library.recurrence` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/library/` |
| Library | `library.atlas` | 2 | 8 | — | **8** | 1 | P0 (fidelity r1) Open all members / double-click on F-01, F-02, F-09 crashes the family pa | `screenshots/pages/library/` |
| Library | `library.family` | 1 | 6 | — | **6** | 1 | P0 (fidelity r1) Family page crashes for F-01, F-02, F-09 | `screenshots/pages/library/` |
| Library | `library.grouping` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/library/` |
| Library | `library.import` | 1 | — | 9 | **9** | 1 | — | `screenshots/pages/library/` |
| Library | `library.window-sets` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/library/` |
| Library | `library.templates` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/library/` |
| Jobs | `jobs.all` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/jobs/` |
| Jobs | `jobs.paused` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/jobs/` |
| Jobs | `jobs.upload` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/jobs/` |
| Jobs | `jobs.cluster` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/jobs/` |
| Settings | `settings.datasets` | 2 | — | — | **—** | 0 | not rated | `screenshots/pages/settings/` |
| Settings | `settings.channels-events` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/settings/` |
| Settings | `settings.vocabulary` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/settings/` |
| Settings | `settings.nulls` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/settings/` |
| Settings | `settings.analysis-defaults` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/settings/` |
| Settings | `settings.compute-hpc` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/settings/` |
| Settings | `settings.blocks` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/settings/` |
| Settings | `settings.review-queues` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/settings/` |
| Settings | `settings.models-registration` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/settings/` |
| Settings | `settings.library-groupings` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/settings/` |
| Settings | `settings.storage-backups` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/settings/` |
| Settings | `settings.export` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/settings/` |
| Settings | `settings.audit-log` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/settings/` |
| Settings | `settings.about` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/settings/` |
| Settings | `settings.display` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/settings/` |
| Settings | `settings.keyboard` | 1 | — | — | **—** | 0 | not rated | `screenshots/pages/settings/` |

## Statistics

- Pages: **53** over **93** frame references; **385** states walked by the smoke test.
- Rated: **10**; unrated (critic did not finish): **43**.
- Mean final score: **8.3**; accepted (≥ 8): **9** of 10.
- Below 8: **1**.

## Pages below 8, and why

### `library.family` — 6 (fidelity 6, function None, 1 round(s))
- P0 (fidelity r1) Family page crashes for F-01, F-02, F-09

## Not rated

These pages were built but their critics did not finish (the account's usage limit stopped the run twice).

- `analyse.interrogation` — 13 states in the smoke manifest; screenshots in `screenshots/pages/interrogation/`
- `analyse.interrogation.slope` — 10 states in the smoke manifest; screenshots in `screenshots/pages/interrogation/`
- `analyse.interrogation.aggregate` — 11 states in the smoke manifest; screenshots in `screenshots/pages/interrogation/`
- `analyse.training` — 1 states in the smoke manifest; screenshots in `screenshots/pages/training/`
- `analyse.training.windows` — 1 states in the smoke manifest; screenshots in `screenshots/pages/training/`
- `analyse.training.matrix` — 1 states in the smoke manifest; screenshots in `screenshots/pages/training/`
- `analyse.training.cluster` — 1 states in the smoke manifest; screenshots in `screenshots/pages/training/`
- `analyse.training.encode` — 1 states in the smoke manifest; screenshots in `screenshots/pages/training/`
- `analyse.training.model` — 1 states in the smoke manifest; screenshots in `screenshots/pages/training/`
- `discovery.runs` — 12 states in the smoke manifest; screenshots in `screenshots/pages/discovery/`
- `discovery.seed` — 11 states in the smoke manifest; screenshots in `screenshots/pages/discovery/`
- `discovery.compare` — 10 states in the smoke manifest; screenshots in `screenshots/pages/discovery/`
- `discovery.stages` — 9 states in the smoke manifest; screenshots in `screenshots/pages/discovery/`
- `models.launch` — 16 states in the smoke manifest; screenshots in `screenshots/pages/models/`
- `models.results` — 8 states in the smoke manifest; screenshots in `screenshots/pages/models/`
- `models.compare` — 11 states in the smoke manifest; screenshots in `screenshots/pages/models/`
- `models.registry` — 18 states in the smoke manifest; screenshots in `screenshots/pages/models/`
- `review.inspector` — 25 states in the smoke manifest; screenshots in `screenshots/pages/review/`
- `review.cluster` — 7 states in the smoke manifest; screenshots in `screenshots/pages/review/`
- `library.recurrence` — 7 states in the smoke manifest; screenshots in `screenshots/pages/library/`
- `library.grouping` — 9 states in the smoke manifest; screenshots in `screenshots/pages/library/`
- `library.window-sets` — 10 states in the smoke manifest; screenshots in `screenshots/pages/library/`
- `library.templates` — 11 states in the smoke manifest; screenshots in `screenshots/pages/library/`
- `jobs.all` — 20 states in the smoke manifest; screenshots in `screenshots/pages/jobs/`
- `jobs.paused` — 9 states in the smoke manifest; screenshots in `screenshots/pages/jobs/`
- `jobs.upload` — 7 states in the smoke manifest; screenshots in `screenshots/pages/jobs/`
- `jobs.cluster` — 10 states in the smoke manifest; screenshots in `screenshots/pages/jobs/`
- `settings.datasets` — 1 states in the smoke manifest; screenshots in `screenshots/pages/settings/`
- `settings.channels-events` — 1 states in the smoke manifest; screenshots in `screenshots/pages/settings/`
- `settings.vocabulary` — 1 states in the smoke manifest; screenshots in `screenshots/pages/settings/`
- `settings.nulls` — 1 states in the smoke manifest; screenshots in `screenshots/pages/settings/`
- `settings.analysis-defaults` — 1 states in the smoke manifest; screenshots in `screenshots/pages/settings/`
- `settings.compute-hpc` — 1 states in the smoke manifest; screenshots in `screenshots/pages/settings/`
- `settings.blocks` — 1 states in the smoke manifest; screenshots in `screenshots/pages/settings/`
- `settings.review-queues` — 1 states in the smoke manifest; screenshots in `screenshots/pages/settings/`
- `settings.models-registration` — 1 states in the smoke manifest; screenshots in `screenshots/pages/settings/`
- `settings.library-groupings` — 1 states in the smoke manifest; screenshots in `screenshots/pages/settings/`
- `settings.storage-backups` — 1 states in the smoke manifest; screenshots in `screenshots/pages/settings/`
- `settings.export` — 1 states in the smoke manifest; screenshots in `screenshots/pages/settings/`
- `settings.audit-log` — 1 states in the smoke manifest; screenshots in `screenshots/pages/settings/`
- `settings.about` — 1 states in the smoke manifest; screenshots in `screenshots/pages/settings/`
- `settings.display` — 1 states in the smoke manifest; screenshots in `screenshots/pages/settings/`
- `settings.keyboard` — 1 states in the smoke manifest; screenshots in `screenshots/pages/settings/`

## What needs your input

- `docs/wayfinder/fog-of-war.md` §Frontend design collects every question the pages raised;
  `webui/pages/fog/<unit>.md` holds each builder's raw notes.
- `webui/BUILD_PROGRESS.md` lists the shared-kit requests builders worked around, queued for a later pass.
