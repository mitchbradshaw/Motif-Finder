# PAGES.md — every concept frame, the page it became, and how it scored

One row per page (a route/screen); a frame showing a state of that screen is a state of the page, not a
page of its own. Scores are the two independent critics' (design fidelity · function) ratings of the last
round; **the page's score is the lower of the two**, accepted at ≥ 8. Findings live in `webui/critique/<sub-unit>/`,
screenshots of every state in `webui/screenshots/pages/<unit>/`, builder notes in `webui/pages/status/<unit>.md`,
and each page's regions, interactions and fixtures in `webui/pages/inventory/`.

53 pages · 385 states · 93 frame references.

## Explore

| page | route | frames | states | fidelity | function | score | rounds | screenshots |
|---|---|---|---|---|---|---|---|---|
| `explore.corpus` | `#/explore/corpus` | explore-1-corpus · explore-1b-corpus-menus | 12: default, recordings-menu, recordings-menu-deeplink, map-legend, disagree-reviewed, runs-picker … | 9 | 9 | **9** | 1 | `screenshots/pages/explore/` |
| `explore.signal` | `#/explore/signal/4` | explore-2-signal · explore-2a-signal-popovers · explore-2b-signal-drawer · explore-2c-drawer-detections · explore-2d-drawer-shortcuts | 18: default, motif, motif-next-review, detections-picker, detections-picker-by-method, span-legend … | 8 | — | **8** | 1 | `screenshots/pages/explore/` |
| `explore.cross-channel` | `#/explore/cross-channel/4` | explore-3-cross-channel · explore-3b-cross-channel-aligned | 12: as-recorded, lag-aligned, align-click, channels-picker, detections-picker, questions-open … | 9 | — | **9** | 1 | `screenshots/pages/explore/` |
| `explore.span-edit` | `#/explore/span-edit/m-1846` | explore-4-span-edit | 9: pristine, edited, nudge, snap-trough, invalid, typed-invalid … | 9 | — | **9** | 1 | `screenshots/pages/explore/` |

**`explore.signal` — open findings after the last round**
- P1 (fidelity r1) overlay F-03 medoid flattens the live motif trace onto the top axis

## Analyse

| page | route | frames | states | fidelity | function | score | rounds | screenshots |
|---|---|---|---|---|---|---|---|---|
| `analyse.chain` | `#/analyse/chain` | chain-1-chain · chain-1b-run-history · chain-1c-empty-import-template · chain-1d-running · chain-1e-invalid-junction · chain-1f-failed-block · chain-1g-heavy-stage-hpc · chain-1h-scores-chain · chain-1i-paused-result-in-place · chain-2-insert-stage | 21: live, 1-chain, 1b-run-history, 1b-run-history-click, 1c-empty-import-template, 1c-import-apply … | 8 | 8 | **8** | 1 | `screenshots/pages/analyse/` |
| `analyse.block` | `#/analyse/block/1` | chain-3-block03-symbolic-encoding · chain-4-block04-drop-detection · chain-5-block01-baseline-removal · chain-6-block02-noise-floor · chain-7-block-matrix-profile-scores · chain-7b-block-threshold-to-spans · chain-8-block-model-stage | 18: live, 5-baseline-unapplied, 5-baseline-try-window, 5-baseline-apply-running, 6-noise-floor, 6-noise-floor-linear … | 8 | — | **8** | 1 | `screenshots/pages/analyse/` |
| `analyse.glyphs` | `#/analyse/glyphs` | chain-6b-algorithm-glyphs | 4: default, detail-drawer, card-click, filter-empty | 9 | — | **9** | 1 | `screenshots/pages/analyse/` |
| `analyse.interrogation` | `#/analyse/interrogation` | interrogation-1-family-block · interrogation-1b-source-picker | 13: default, source-picker, source-picker-by-click, picker-prior-run, picker-review, swapped … | — | — | **—** | 0 | `screenshots/pages/interrogation/` |
| `analyse.interrogation.slope` | `#/analyse/interrogation/block/1` | interrogation-2-block01-slope · interrogation-2b-slope-large-family · interrogation-2c-slope-stale-after-edit | 10: default, event-picked, jump-to-flagged, large-family, large-family-rose, upstream-spike-shape … | — | — | **—** | 0 | `screenshots/pages/interrogation/` |
| `analyse.interrogation.aggregate` | `#/analyse/interrogation/block/2` | interrogation-3-block02-aggregate · interrogation-3b-aggregate-colour-by-recording · interrogation-3c-aggregate-wired-from-spike-shape | 11: default, histograms, colour-by-recording, pair-by-click, linear-axes, wired-from-spike-shape … | — | — | **—** | 0 | `screenshots/pages/interrogation/` |
| `analyse.training` | `#/analyse/training` | training-0-training-chain · training-0b-human-window-source-ILLUSTRATIVE | 1: default | — | — | **—** | 0 | `screenshots/pages/training/` |
| `analyse.training.windows` | `#/analyse/training/block/1` | training-01-block01-sliding-windows | 1: default | — | — | **—** | 0 | `screenshots/pages/training/` |
| `analyse.training.matrix` | `#/analyse/training/block/2` | training-1-block02-window-matrix | 1: default | — | — | **—** | 0 | `screenshots/pages/training/` |
| `analyse.training.cluster` | `#/analyse/training/block/3` | training-2-block03-cluster · training-2b-block03-choose-k | 1: default | — | — | **—** | 0 | `screenshots/pages/training/` |
| `analyse.training.encode` | `#/analyse/training/block/4` | training-3-block04-encode | 1: default | — | — | **—** | 0 | `screenshots/pages/training/` |
| `analyse.training.model` | `#/analyse/training/block/5` | training-4-block05-model | 1: default | — | — | **—** | 0 | `screenshots/pages/training/` |

**`analyse.chain` — open findings after the last round**
- P1 (fidelity r1) Footer primary reads 'Pass  to Review' with the count blanked, and is disabled
- P1 (function r1) Footer button renders 'Pass  to Review' - the N is missing
- P1 (function r1) Run history 'result' column has a header but no values
- P1 (function r1) Save as template writes nowhere the page can see
- P1 (function r1) Paused footer stays 'Paused at 02' after Continue has finished

**`analyse.block` — open findings after the last round**
- P1 (fidelity r1) Primary action clipped off the right edge at 1440
- P1 (fidelity r1) 'What this change does downstream' is hard-coded and contradicts the page
- P1 (fidelity r1) Encoding tiles contradict the null-sweep caption and drop the frame's canon values
- P1 (fidelity r1) Spans strip under the scores goes blank while the table still reports spans
- P1 (fidelity r1) Failed state still presents a complete successful result

## Discovery

| page | route | frames | states | fidelity | function | score | rounds | screenshots |
|---|---|---|---|---|---|---|---|---|
| `discovery.runs` | `#/discovery/runs` | discovery-1-runs · discovery-1b-add-template · discovery-1c-many-channels | 12: default, modal-add-template, six-channels-page-2, modal-slurm, popover-history, confirm-discard … | — | — | **—** | 0 | `screenshots/pages/discovery/` |
| `discovery.seed` | `#/discovery/seed` | discovery-2-seed | 11: default, source-explore, source-medoid, change-seed, view-popover, running … | — | — | **—** | 0 | `screenshots/pages/discovery/` |
| `discovery.compare` | `#/discovery/compare` | discovery-3-compare | 10: default, empty-one-pick, unpick-b, swapped, filter-only-b, popover-roles … | — | — | **—** | 0 | `screenshots/pages/discovery/` |
| `discovery.stages` | `#/discovery/compare/stages` | discovery-3b-stages | 9: default, re-running, stepped, swapped, popover-first-differing, popover-stage-params … | — | — | **—** | 0 | `screenshots/pages/discovery/` |

## Models

| page | route | frames | states | fidelity | function | score | rounds | screenshots |
|---|---|---|---|---|---|---|---|---|
| `models.launch` | `#/models/launch` | models-1-launch · models-1b-launch-from-window-set | 16: signal-template, windowset-template, windowset-template-by-click, local-allowed, local-allowed-by-click, training-local … | — | — | **—** | 0 | `screenshots/pages/models/` |
| `models.results` | `#/models/results` | models-3-results | 8: arm-a, arm-b, arm-rf, arm-rf-by-click, target-precision-0.9, job-popover … | — | — | **—** | 0 | `screenshots/pages/models/` |
| `models.compare` | `#/models/compare` | models-4-compare · models-4b-compare-both-wrong | 11: only-a, both-wrong, both-wrong-by-cell, only-b, step-next, not-attributable … | — | — | **—** | 0 | `screenshots/pages/models/` |
| `models.registry` | `#/models/registry` | models-5-registry | 18: candidate, filter-registered, filter-retired, candidate-failing, registered, retired … | — | — | **—** | 0 | `screenshots/pages/models/` |

## Review

| page | route | frames | states | fidelity | function | score | rounds | screenshots |
|---|---|---|---|---|---|---|---|---|
| `review.inspector` | `#/review/queue/q-12` | review-1-candidate · review-1b-other-channels · review-3-queue-open · review-4-evidence-open · review-5-blind-verification · review-6-seed-promoted | 25: 1-candidate (redirect from review root), 1b-other-channels (deep link), 1b-other-channels (click, then Escape), 3-queue-rail (deep link), 3-queue-rail (click toggle, filter judged), 3-queue-rail channel filter … | — | — | **—** | 0 | `screenshots/pages/review/` |
| `review.cluster` | `#/review/queue/q-15/cluster/12` | review-2-cluster · review-7-batch-undone | 7: 2-batch-ready, alias review-cluster-12, member selected (click), 7-batch-undone then redo, include all then exclude flagged, sequence cluster 13 with queue rail … | — | — | **—** | 0 | `screenshots/pages/review/` |

## Library

| page | route | frames | states | fidelity | function | score | rounds | screenshots |
|---|---|---|---|---|---|---|---|---|
| `library.recurrence` | `#/library/recurrence` | library-1-recurrence | 7: selected, count, recordings-4-5, omitted-drawer, sequences, empty … | — | — | **—** | 0 | `screenshots/pages/library/` |
| `library.atlas` | `#/library/atlas` | library-2-atlas-motifs · library-2b-atlas-sequences | 7: motifs, sequences, family-selected, groupings-popover, omitted-drawer, no-scope … | 8 | — | **8** | 1 | `screenshots/pages/library/` |
| `library.family` | `#/library/family/F-03` | library-3-family | 10: member-selected, revisions-popover, hand-only, sort-time-page-2, tag-popover-invalid, class-popover … | 6 | — | **6** | 1 | `screenshots/pages/library/` |
| `library.grouping` | `#/library/grouping` | library-4-edit-grouping | 9: frequency-content, unchanged-shape-distance, invalid, applying, failed, unit-sequences … | — | — | **—** | 0 | `screenshots/pages/library/` |
| `library.import` | `#/library/import` | library-5-empty-import | 8: empty-dry-run, dry-run-populated, bundle-invalid, held-out-refused, importing, failed … | — | 9 | **9** | 1 | `screenshots/pages/library/` |
| `library.window-sets` | `#/library/window-sets` | library-6-window-sets | 10: set-selected, not-train-safe-selected, supplied-no-split, coverage-at-save, filter-not-train-safe, filtered-empty … | — | — | **—** | 0 | `screenshots/pages/library/` |
| `library.templates` | `#/library/templates` | library-7-templates | 11: template-selected, training-selected, unscored-selected, kind-training, model-stage, page-2 … | — | — | **—** | 0 | `screenshots/pages/library/` |

**`library.atlas` — open findings after the last round**
- P0 (fidelity r1) Open all members / double-click on F-01, F-02, F-09 crashes the family page

**`library.family` — open findings after the last round**
- P0 (fidelity r1) Family page crashes for F-01, F-02, F-09

## Jobs

| page | route | frames | states | fidelity | function | score | rounds | screenshots |
|---|---|---|---|---|---|---|---|---|
| `jobs.all` | `#/jobs` | jobs-1-all | 20: all, needs-you, paused, cluster, local, queues … | — | — | **—** | 0 | `screenshots/pages/jobs/` |
| `jobs.paused` | `#/jobs/run/a-0098` | jobs-2-paused-run | 9: result-arrived, waiting, a-0098-arrived, unknown-run, new-script-modal, looking … | — | — | **—** | 0 | `screenshots/pages/jobs/` |
| `jobs.upload` | `#/jobs/run/r-0431/upload` | jobs-3-upload-and-continue | 7: refused, no-file, passes, passes-no-nulls, held-out-refused, file-menu … | — | — | **—** | 0 | `screenshots/pages/jobs/` |
| `jobs.cluster` | `#/jobs/cluster/j-0217` | jobs-4-cluster-job-inbox | 10: running-overdue, running, finished-imported, failed, unknown-job, new-script-modal … | — | — | **—** | 0 | `screenshots/pages/jobs/` |

## Settings

| page | route | frames | states | fidelity | function | score | rounds | screenshots |
|---|---|---|---|---|---|---|---|---|
| `settings.datasets` | `#/settings/datasets` | settings-01-datasets · settings-01b-import-recording | 1: default | — | — | **—** | 0 | `screenshots/pages/settings/` |
| `settings.channels-events` | `#/settings/channels-events` | settings-02-channels-events | 1: default | — | — | **—** | 0 | `screenshots/pages/settings/` |
| `settings.vocabulary` | `#/settings/vocabulary` | settings-03-vocabulary | 1: default | — | — | **—** | 0 | `screenshots/pages/settings/` |
| `settings.nulls` | `#/settings/nulls` | settings-04-nulls | 1: default | — | — | **—** | 0 | `screenshots/pages/settings/` |
| `settings.analysis-defaults` | `#/settings/analysis-defaults` | settings-05-analysis-defaults | 1: default | — | — | **—** | 0 | `screenshots/pages/settings/` |
| `settings.compute-hpc` | `#/settings/compute-hpc` | settings-06-compute-hpc | 1: default | — | — | **—** | 0 | `screenshots/pages/settings/` |
| `settings.blocks` | `#/settings/blocks` | settings-07-blocks | 1: default | — | — | **—** | 0 | `screenshots/pages/settings/` |
| `settings.review-queues` | `#/settings/review-queues` | settings-08-review-queues | 1: default | — | — | **—** | 0 | `screenshots/pages/settings/` |
| `settings.models-registration` | `#/settings/models-registration` | settings-09-models-registration | 1: default | — | — | **—** | 0 | `screenshots/pages/settings/` |
| `settings.library-groupings` | `#/settings/library-groupings` | settings-10-library-groupings | 1: default | — | — | **—** | 0 | `screenshots/pages/settings/` |
| `settings.storage-backups` | `#/settings/storage-backups` | settings-11-storage-backups | 1: default | — | — | **—** | 0 | `screenshots/pages/settings/` |
| `settings.export` | `#/settings/export` | settings-12-export | 1: default | — | — | **—** | 0 | `screenshots/pages/settings/` |
| `settings.audit-log` | `#/settings/audit-log` | settings-13-audit-log | 1: default | — | — | **—** | 0 | `screenshots/pages/settings/` |
| `settings.about` | `#/settings/about` | settings-14-about | 1: default | — | — | **—** | 0 | `screenshots/pages/settings/` |
| `settings.display` | `#/settings/display` | settings-15-display | 1: default | — | — | **—** | 0 | `screenshots/pages/settings/` |
| `settings.keyboard` | `#/settings/keyboard` | settings-16-keyboard-behaviour | 1: default | — | — | **—** | 0 | `screenshots/pages/settings/` |
