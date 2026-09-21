# PAGES.md — every concept frame, the page it became, and how it scored

One row per page (a route/screen); a frame showing a state of that screen is a state of the page, not a
page of its own. Scores are the two independent critics' (design fidelity · function) ratings of the last
round; **the page's score is the lower of the two**, accepted at ≥ 8. Findings live in `webui/critique/<sub-unit>/`,
screenshots of every state in `webui/screenshots/pages/<unit>/`, builder notes in `webui/pages/status/<unit>.md`,
and each page's regions, interactions and fixtures in `webui/pages/inventory/`.

53 pages · 549 states · 93 frame references.

## Explore

| page | route | frames | states | fidelity | function | score | rounds | screenshots |
|---|---|---|---|---|---|---|---|---|
| `explore.corpus` | `#/explore/corpus` | explore-1-corpus · explore-1b-corpus-menus | 12: default, recordings-menu, recordings-menu-deeplink, map-legend, disagree-reviewed, runs-picker … | 9 | 9 | **9** | 1 | `screenshots/pages/explore/` |
| `explore.signal` | `#/explore/signal/4` | explore-2-signal · explore-2a-signal-popovers · explore-2b-signal-drawer · explore-2c-drawer-detections · explore-2d-drawer-shortcuts | 18: default, motif, motif-next-review, detections-picker, detections-picker-by-method, span-legend … | 8 | 9 | **8** | 1 | `screenshots/pages/explore/` |
| `explore.cross-channel` | `#/explore/cross-channel/4` | explore-3-cross-channel · explore-3b-cross-channel-aligned | 12: as-recorded, lag-aligned, align-click, channels-picker, detections-picker, questions-open … | 9 | 9 | **9** | 1 | `screenshots/pages/explore/` |
| `explore.span-edit` | `#/explore/span-edit/m-1846` | explore-4-span-edit | 9: pristine, edited, nudge, snap-trough, invalid, typed-invalid … | 9 | 9 | **9** | 1 | `screenshots/pages/explore/` |

**`explore.corpus` — open findings after the last round**
- P1 (function r1) 'matching' readout ignores the Verdict and Show filters

**`explore.signal` — open findings after the last round**
- P1 (fidelity r1) overlay F-03 medoid flattens the live motif trace onto the top axis
- P1 (function r1) ?motif=<n> deep link opens a different motif than the URL names, and a reload changes it again

## Analyse

| page | route | frames | states | fidelity | function | score | rounds | screenshots |
|---|---|---|---|---|---|---|---|---|
| `analyse.chain` | `#/analyse/chain` | chain-1-chain · chain-1b-run-history · chain-1c-empty-import-template · chain-1d-running · chain-1e-invalid-junction · chain-1f-failed-block · chain-1g-heavy-stage-hpc · chain-1h-scores-chain · chain-1i-paused-result-in-place · chain-2-insert-stage | 21: live, 1-chain, 1b-run-history, 1b-run-history-click, 1c-empty-import-template, 1c-import-apply … | 8 | 8 | **8** | 1 | `screenshots/pages/analyse/` |
| `analyse.block` | `#/analyse/block/1` | chain-3-block03-symbolic-encoding · chain-4-block04-drop-detection · chain-5-block01-baseline-removal · chain-6-block02-noise-floor · chain-7-block-matrix-profile-scores · chain-7b-block-threshold-to-spans · chain-8-block-model-stage | 18: live, 5-baseline-unapplied, 5-baseline-try-window, 5-baseline-apply-running, 6-noise-floor, 6-noise-floor-linear … | 8 | 8 | **8** | 1 | `screenshots/pages/analyse/` |
| `analyse.glyphs` | `#/analyse/glyphs` | chain-6b-algorithm-glyphs | 4: default, detail-drawer, card-click, filter-empty | 9 | 8 | **8** | 1 | `screenshots/pages/analyse/` |
| `analyse.interrogation` | `#/analyse/interrogation` | interrogation-1-family-block · interrogation-1b-source-picker | 13: default, source-picker, source-picker-by-click, picker-prior-run, picker-review, swapped … | 9 | 8 | **8** | 1 | `screenshots/pages/interrogation/` |
| `analyse.interrogation.slope` | `#/analyse/interrogation/block/1` | interrogation-2-block01-slope · interrogation-2b-slope-large-family · interrogation-2c-slope-stale-after-edit | 11: default, event-picked, jump-to-flagged, large-family, large-family-rose, upstream-spike-shape … | 9 | 9 | **9** | 2 | `screenshots/pages/interrogation/` |
| `analyse.interrogation.aggregate` | `#/analyse/interrogation/block/2` | interrogation-3-block02-aggregate · interrogation-3b-aggregate-colour-by-recording · interrogation-3c-aggregate-wired-from-spike-shape | 16: default, histograms, colour-by-recording, pair-by-click, linear-axes, wired-from-spike-shape … | 8 | 8 | **8** | 2 | `screenshots/pages/interrogation/` |
| `analyse.training` | `#/analyse/training` | training-0-training-chain · training-0b-human-window-source-ILLUSTRATIVE | 15: default, source-popover, source-popover-by-click, illustrative-human-windows, history, import … | 8 | 9 | **8** | 2 | `screenshots/pages/training/` |
| `analyse.training.windows` | `#/analyse/training/block/1` | training-01-block01-sliding-windows | 9: default, edited, invalid-gap, random-split, boundary, verdicts … | 8 | 9 | **8** | 2 | `screenshots/pages/training/` |
| `analyse.training.matrix` | `#/analyse/training/block/2` | training-1-block02-window-matrix | 8: default, edited, group-open, label-derived-on, readout, slurm … | 8 | 8 | **8** | 2 | `screenshots/pages/training/` |
| `analyse.training.cluster` | `#/analyse/training/block/3` | training-2-block03-cluster · training-2b-block03-choose-k | 10: default, occupancy, choose-k, choose-k-by-click, criterion-locked, merge-pending … | 8 | 8 | **8** | 2 | `screenshots/pages/training/` |
| `analyse.training.encode` | `#/analyse/training/block/4` | training-3-block04-encode | 7: default, window, window-by-pager, edited, new-encoder-version, browse-gadf … | 8 | 8 | **8** | 2 | `screenshots/pages/training/` |
| `analyse.training.model` | `#/analyse/training/block/5` | training-4-block05-model | 9: default, labels-manual, labels-both, trial-job-created, focus-trial, send-review … | 9 | 9 | **9** | 2 | `screenshots/pages/training/` |

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
- P1 (function r1) cut k edits bypass the draft/apply machinery and cannot be undone
- P1 (function r1) failed state still presents results and offers to pass 6 spans to Review
- P1 (function r1) generic block parameters accept any text with no validation

**`analyse.glyphs` — open findings after the last round**
- P1 (function r1) 'Find it in Insert a stage' does not find it

**`analyse.interrogation` — open findings after the last round**
- P1 (function r1) Run chain / Re-run from 01 completes instantly — no queued → running → done
- P1 (function r1) Swapping the family leaves 01 and 02 'cached' and the estimate unchanged

**`analyse.interrogation.slope` — open findings after the last round**
- P1 (function r1) 'units' changes only the caption text — no number, axis or angle is recomputed
- P1 (function r1) Parameter controls stay editable while the run veil is up
- P1 (function r1) 'Re-run from 01' clears stale with no visible run
- P1 (fidelity r2) prev fixed: 'units' now recomputes the whole page
- P1 (fidelity r2) prev fixed: parameter controls lock while the run veil is up
- P1 (fidelity r2) prev fixed: 'Re-run from 01' really runs
- P1 (function r2) prev fixed: 'units' recomputes the whole page
- P1 (function r2) prev fixed: parameters lock while the run veil is up
- P1 (function r2) prev fixed: 'Re-run from 01' really runs

**`analyse.interrogation.aggregate` — open findings after the last round**
- P1 (fidelity r1) F-04 reports F-03's numbers verbatim
- P1 (fidelity r1) colour-by drops the null behind the histograms and re-bins them
- P1 (function r1) Feature-wiring selects are dead — the page never rewires
- P1 (function r1) Four of six Parameters dropdowns change nothing; 'null' only relabels
- P1 (function r1) colour by = recording / channel / verdict removes the null from every histogram
- P1 (function r1) ?state=running renders no running state
- P1 (function r1) Small-family state reuses F-03's fit verbatim
- P1 (fidelity r2) prev fixed: colour-by keeps the null and the bins
- P1 (fidelity r2) prev fixed: F-04 no longer reports F-03's fit
- P1 (fidelity r2) prev fixed: the wiring selects rewire the page
- P1 (fidelity r2) prev fixed: every Parameters control recomputes, null included
- P1 (fidelity r2) prev fixed: ?state=running renders a running state

**`analyse.training` — open findings after the last round**
- P1 (fidelity r1) failed badge lands on 03 Cluster, not 04 Encode
- P1 (fidelity r1) 0b keeps the default header, toolbar and hand-off card
- P1 (fidelity r1) Encode row badged cached while its own caption says stale
- P1 (function r1) Inline rename cannot be cancelled or committed once invalid
- P1 (function r1) Send to Review accepts an invalid count - cap 20,000 not enforced
- P1 (function r1) Row bypass is a dead click - the row does not change
- P1 (function r1) Invalid junction after deleting a stage offers no fix action
- P1 (function r1) A deleted stage is still in the block-page chain ribbon
- P1 (function r1) Human-windows source: Model row still cites '03 cluster' and 'split from 01'
- P1 (fidelity r2) Invalid-junction fix buttons overlap the row caption

**`analyse.training.windows` — open findings after the last round**
- P1 (fidelity r1) Split strip missing labels, gap markers and window ticks while the legend claims them
- P1 (fidelity r1) 'At a boundary' close-up is drawn wrong
- P1 (fidelity r1) Checks card keeps green ticks that the current settings falsify
- P1 (fidelity r1) ?state=edited does not produce the frame's pending change
- P1 (function r1) Unapplied-changes bar always describes a gap change, whatever you edited
- P1 (function r1) Split strip and verdict bars ignore the split ratio and block count
- P1 (function r1) Toolbar primary runs the chain while the gap field is invalid
- P1 (function r1) Toolbar primary and unapplied-bar primary disagree in every state
- P1 (function r1) Bar primary stays enabled with nothing pending and nothing stale
- P1 (function r1) Save window set opens with a default id its own validator rejects
- P1 (fidelity r2) Boundary card still certifies safety on the leaking random split

**`analyse.training.matrix` — open findings after the last round**
- P1 (function r1) Unapplied bar says 'Random Forest excluded' whatever you changed
- P1 (function r1) normalise and clip are effectively dead - heatmap and legend do not respond
- P1 (function r1) Clicking a matrix column does not select a window
- P1 (fidelity r2) 'CNN rows greyed = excluded from 03' persists after CNN scores are included
- P1 (function r2) Toolbar primary offers 'Apply & re-run from 02' with nothing to apply

**`analyse.training.cluster` — open findings after the last round**
- P1 (fidelity r1) Cutline sits above the tree instead of cutting it into six
- P1 (function r1) Criterion RadioCards show no selection
- P1 (function r1) Locking the criterion does not lock it
- P1 (function r1) Save grouping records the wrong scope
- P1 (fidelity r2) Windows-per-class bars are all blue while the caption claims the class palette
- P1 (function r2) Changing the cut never reaches the class cards, occupancy strip or per-class bars

**`analyse.training.encode` — open findings after the last round**
- P1 (function r1) Image size and PAA do not change the disk or time estimate
- P1 (function r1) Window 283 contradicts the matrix readout that opens it
- P1 (function r1) A browse class card opens a window of a different class
- P1 (fidelity r2) Unapplied bar names the encodings, not the change that was made
- P1 (fidelity r2) Toolbar wraps onto a second row, pushing the page down
- P1 (function r2) The unapplied bar never names the parameter you changed

**`analyse.training.model` — open findings after the last round**
- P1 (function r1) Stage-05 row contradicts the architecture you selected
- P1 (function r1) No cost changes when stages are ticked or unticked
- P1 (function r1) Copy script, Download trial job and Train in Models stay enabled with no stage ticked

## Discovery

| page | route | frames | states | fidelity | function | score | rounds | screenshots |
|---|---|---|---|---|---|---|---|---|
| `discovery.runs` | `#/discovery/runs` | discovery-1-runs · discovery-1b-add-template · discovery-1c-many-channels | 14: default, modal-add-template, six-channels-page-2, modal-slurm, popover-history, confirm-discard … | 9 | 8 | **8** | 2 | `screenshots/pages/discovery/` |
| `discovery.seed` | `#/discovery/seed` | discovery-2-seed | 11: default, source-explore, source-medoid, change-seed, view-popover, running … | 8 | 8 | **8** | 1 | `screenshots/pages/discovery/` |
| `discovery.compare` | `#/discovery/compare` | discovery-3-compare | 11: default, empty-one-pick, unpick-b, swapped, filter-only-b, popover-roles … | 9 | 9 | **9** | 1 | `screenshots/pages/discovery/` |
| `discovery.stages` | `#/discovery/compare/stages` | discovery-3b-stages | 10: default, re-running, stepped, swapped, popover-first-differing, popover-stage-params … | 8 | 8 | **8** | 1 | `screenshots/pages/discovery/` |

**`discovery.runs` — open findings after the last round**
- P0 (function r1) Confirming Discard run crashes the Discovery workspace
- P1 (fidelity r2) prev fixed: confirming Discard run no longer crashes the workspace
- P1 (function r2) Scoreboard chevron for drop_motifs9 can expand but never collapse (dead click)
- P1 (function r2) Retry on the failed run row is a dead click
- P1 (function r2) 'also found by' link jumps to the wrong detection

**`discovery.seed` — open findings after the last round**
- P1 (fidelity r1) Done state reports two different found counts for the same run
- P1 (function r1) Forced running state prints 'running - undefined (2 of 1)'

**`discovery.stages` — open findings after the last round**
- P1 (fidelity r1) Source row badged 'differs' while its own caption says the signal is identical
- P1 (function r1) The re-running state is not rendered

## Models

| page | route | frames | states | fidelity | function | score | rounds | screenshots |
|---|---|---|---|---|---|---|---|---|
| `models.launch` | `#/models/launch` | models-1-launch · models-1b-launch-from-window-set | 16: signal-template, windowset-template, windowset-template-by-click, local-allowed, local-allowed-by-click, training-local … | 9 | 9 | **9** | 1 | `screenshots/pages/models/` |
| `models.results` | `#/models/results` | models-3-results | 8: arm-a, arm-b, arm-rf, arm-rf-by-click, target-precision-0.9, job-popover … | 8 | 9 | **8** | 1 | `screenshots/pages/models/` |
| `models.compare` | `#/models/compare` | models-4-compare · models-4b-compare-both-wrong | 11: only-a, both-wrong, both-wrong-by-cell, only-b, step-next, not-attributable … | 9 | 8 | **8** | 1 | `screenshots/pages/models/` |
| `models.registry` | `#/models/registry` | models-5-registry | 18: candidate, filter-registered, filter-retired, candidate-failing, registered, retired … | 9 | 9 | **9** | 1 | `screenshots/pages/models/` |

**`models.results` — open findings after the last round**
- P1 (function r1) The failed-job state logs a console error

**`models.compare` — open findings after the last round**
- P1 (function r1) An unrecognised query parameter crashes the whole Models workspace
- P1 (function r1) The render-error boundary never resets, so one bad link breaks every Models tab

**`models.registry` — open findings after the last round**
- P1 (function r1) The sign-off confirmation arrives pre-ticked

## Review

| page | route | frames | states | fidelity | function | score | rounds | screenshots |
|---|---|---|---|---|---|---|---|---|
| `review.inspector` | `#/review/queue/q-12` | review-1-candidate · review-1b-other-channels · review-3-queue-open · review-4-evidence-open · review-5-blind-verification · review-6-seed-promoted | 25: 1-candidate (redirect from review root), 1b-other-channels (deep link), 1b-other-channels (click, then Escape), 3-queue-rail (deep link), 3-queue-rail (click toggle, filter judged), 3-queue-rail channel filter … | 9 | 9 | **9** | 1 | `screenshots/pages/review/` |
| `review.cluster` | `#/review/queue/q-15/cluster/12` | review-2-cluster · review-7-batch-undone | 7: 2-batch-ready, alias review-cluster-12, member selected (click), 7-batch-undone then redo, include all then exclude flagged, sequence cluster 13 with queue rail … | 8 | 8 | **8** | 1 | `screenshots/pages/review/` |

**`review.inspector` — open findings after the last round**
- P1 (function r1) group = family interleaves headers instead of grouping

**`review.cluster` — open findings after the last round**
- P1 (fidelity r1) Title pills are truncated and clipped when the queue rail is open
- P1 (function r1) Verdict keys are silently dead after unchecking the batch box

## Library

| page | route | frames | states | fidelity | function | score | rounds | screenshots |
|---|---|---|---|---|---|---|---|---|
| `library.recurrence` | `#/library/recurrence` | library-1-recurrence | 7: selected, count, recordings-4-5, omitted-drawer, sequences, empty … | 8 | 9 | **8** | 1 | `screenshots/pages/library/` |
| `library.atlas` | `#/library/atlas` | library-2-atlas-motifs · library-2b-atlas-sequences | 7: motifs, sequences, family-selected, groupings-popover, omitted-drawer, no-scope … | 9 | 9 | **9** | 1 | `screenshots/pages/library/` |
| `library.family` | `#/library/family/F-03` | library-3-family | 10: member-selected, revisions-popover, hand-only, sort-time-page-2, tag-popover-invalid, class-popover … | 9 | 9 | **9** | 1 | `screenshots/pages/library/` |
| `library.grouping` | `#/library/grouping` | library-4-edit-grouping | 9: frequency-content, unchanged-shape-distance, invalid, applying, failed, unit-sequences … | 9 | 9 | **9** | 1 | `screenshots/pages/library/` |
| `library.import` | `#/library/import` | library-5-empty-import | 8: empty-dry-run, dry-run-populated, bundle-invalid, held-out-refused, importing, failed … | 9 | 9 | **9** | 1 | `screenshots/pages/library/` |
| `library.window-sets` | `#/library/window-sets` | library-6-window-sets | 10: set-selected, not-train-safe-selected, supplied-no-split, coverage-at-save, filter-not-train-safe, filtered-empty … | 9 | 9 | **9** | 1 | `screenshots/pages/library/` |
| `library.templates` | `#/library/templates` | library-7-templates | 11: template-selected, training-selected, unscored-selected, kind-training, model-stage, page-2 … | 8 | 9 | **8** | 1 | `screenshots/pages/library/` |

**`library.recurrence` — open findings after the last round**
- P1 (fidelity r1) ?sel= deep link is ignored entirely
- P1 (function r1) ?sel= deep link is ignored and the selection is never written to the URL

**`library.family` — open findings after the last round**
- P1 (function r1) Toast overlay covers the batch bar and swallows its clicks

**`library.grouping` — open findings after the last round**
- P1 (function r1) Switching the unit to 'spike trains' lands in an invalid form

**`library.templates` — open findings after the last round**
- P1 (fidelity r1) 'Open in Analyse' disappears on a training template
- P1 (fidelity r1) Scores table overflows the rail card; the 'x null' column is cut off

## Jobs

| page | route | frames | states | fidelity | function | score | rounds | screenshots |
|---|---|---|---|---|---|---|---|---|
| `jobs.all` | `#/jobs` | jobs-1-all | 20: all, needs-you, paused, cluster, local, queues … | 8 | 8 | **8** | 1 | `screenshots/pages/jobs/` |
| `jobs.paused` | `#/jobs/run/a-0098` | jobs-2-paused-run | 9: result-arrived, waiting, a-0098-arrived, unknown-run, new-script-modal, looking … | 9 | 8 | **8** | 1 | `screenshots/pages/jobs/` |
| `jobs.upload` | `#/jobs/run/r-0431/upload` | jobs-3-upload-and-continue | 7: refused, no-file, passes, passes-no-nulls, held-out-refused, file-menu … | 9 | 9 | **9** | 1 | `screenshots/pages/jobs/` |
| `jobs.cluster` | `#/jobs/cluster/j-0217` | jobs-4-cluster-job-inbox | 10: running-overdue, running, finished-imported, failed, unknown-job, new-script-modal … | 8 | 8 | **8** | 1 | `screenshots/pages/jobs/` |

**`jobs.all` — open findings after the last round**
- P1 (fidelity r1) blind badge missing from review-queue table rows
- P1 (fidelity r1) Mark... popover stays open across navigation and covers the cancel modal
- P1 (fidelity r1) time column overlaps the row action in the Finished group
- P1 (function r1) Nav 'Jobs 3' and header '3 need you' never recompute after a write
- P1 (function r1) Hand-marking a cluster job finished says 'imported', at a clock time before its own marks
- P1 (function r1) blind badge missing from the q-18 / q-19 review-queue rows
- P1 (function r1) Header search pill and its Ctrl K keycap are dead

**`jobs.paused` — open findings after the last round**
- P1 (function r1) New SLURM script: changing the profile does not change the script
- P1 (function r1) The replacement script writes to the replaced job's output directory

**`jobs.cluster` — open findings after the last round**
- P1 (fidelity r1) snooze reminder survives the job becoming finished and contradicts it
- P1 (fidelity r1) purple used as the primary-action colour
- P1 (function r1) Changing the profile leaves the script targeting the old partition
- P1 (function r1) Mark finished renders as 'finished - imported' at a time before the job started running

## Settings

| page | route | frames | states | fidelity | function | score | rounds | screenshots |
|---|---|---|---|---|---|---|---|---|
| `settings.datasets` | `#/settings/datasets` | settings-01-datasets · settings-01b-import-recording | 13: default, unsaved, selected-M3_jul, selected-by-click, held-out-locked, invalid-noise-floor … | 9 | 8 | **8** | 1 | `screenshots/pages/settings/` |
| `settings.channels-events` | `#/settings/channels-events` | settings-02-channels-events | 24: default, unsaved, rows-all, rows-all-by-click, rec-M3_jul, rec-M4_aug-locked … | 9 | 9 | **9** | 3 | `screenshots/pages/settings/` |
| `settings.vocabulary` | `#/settings/vocabulary` | settings-03-vocabulary | 9: default, rename, rename-by-click, rekey, add-verdict, add-class … | 9 | 8 | **8** | 1 | `screenshots/pages/settings/` |
| `settings.nulls` | `#/settings/nulls` | settings-04-nulls | 4: default, unsaved, invalid-alpha, method-changed | 9 | 9 | **9** | 1 | `screenshots/pages/settings/` |
| `settings.analysis-defaults` | `#/settings/analysis-defaults` | settings-05-analysis-defaults | 7: default, unsaved, history, context-M3_jul, invalid-band, clear-cache … | 8 | 8 | **8** | 1 | `screenshots/pages/settings/` |
| `settings.compute-hpc` | `#/settings/compute-hpc` | settings-06-compute-hpc | 9: default, unsaved, benchmark-running, benchmark-done, profile-cpu-array, editor-raw … | 9 | 8 | **8** | 1 | `screenshots/pages/settings/` |
| `settings.blocks` | `#/settings/blocks` | settings-07-blocks | 4: default, unsaved, used-by, disable-by-click | 9 | 9 | **9** | 1 | `screenshots/pages/settings/` |
| `settings.review-queues` | `#/settings/review-queues` | settings-08-review-queues | 5: default, unsaved, unblind-warning, invalid-cap, suggest-warning | 8 | 8 | **8** | 1 | `screenshots/pages/settings/` |
| `settings.models-registration` | `#/settings/models-registration` | settings-09-models-registration | 6: default, unsaved, repeats-on, invalid-split, no-arm, unpaired-arms | 8 | 8 | **8** | 1 | `screenshots/pages/settings/` |
| `settings.library-groupings` | `#/settings/library-groupings` | settings-10-library-groupings | 5: default, unsaved, unit-spike-trains, omit-warning, weights | 8 | 8 | **8** | 1 | `screenshots/pages/settings/` |
| `settings.storage-backups` | `#/settings/storage-backups` | settings-11-storage-backups | 8: default, unsaved, low-disk, scanning, token-removed, add-token … | 8 | 8 | **8** | 1 | `screenshots/pages/settings/` |
| `settings.export` | `#/settings/export` | settings-12-export | 4: default, unsaved, include-notes, layout-per-family | 9 | 9 | **9** | 2 | `screenshots/pages/settings/` |
| `settings.audit-log` | `#/settings/audit-log` | settings-13-audit-log | 4: all, kind-lock, kind-by-click, no-reset-link | 8 | 9 | **8** | 1 | `screenshots/pages/settings/` |
| `settings.about` | `#/settings/about` | settings-14-about | 4: default, mismatch, lock-file, copy-diagnostics | 9 | 10 | **9** | 1 | `screenshots/pages/settings/` |
| `settings.display` | `#/settings/display` | settings-15-display | 4: default, applied-immediately, report-profile-transparent, sample-indices-on | 8 | 9 | **8** | 2 | `screenshots/pages/settings/` |
| `settings.keyboard` | `#/settings/keyboard` | settings-16-keyboard-behaviour | 8: default, conflict, capture-rebound, capture, conflict-locked-owner, conflict-class-key … | 9 | 8 | **8** | 3 | `screenshots/pages/settings/` |

**`settings.datasets` — open findings after the last round**
- P1 (fidelity r1) Save-bar consequence contradicts the field it describes
- P1 (function r1) ?state=unsaved seeds values that contradict the save-bar sentence
- P1 (function r1) Header 'M4 held out' chip survives an unlock
- P1 (function r1) No toast after the held-out lock is turned off
- P1 (function r1) display name and start time go invalid with no message

**`settings.channels-events` — open findings after the last round**
- P1 (fidelity r1) Event timeline drawn at full 721 h scale, so events and exclusions are unreadable
- P1 (function r1) Per-channel noise floor accepts any value and produces a mangled consequence
- P1 (function r1) Changing an event's effect gives a fixture-id consequence, not the frame's sentence
- P1 (function r1) A saved new event is not staged in the save bar
- P1 (function r1) Channel status and excluded-spans cells are inert
- P1 (function r1) No way to remove an event row
- P1 (function r1) + kind rejects the very name its placeholder suggests
- P1 (fidelity r2) prev fixed: Event timeline drawn at full 721 h scale
- P1 (fidelity r2) prev fixed: per-channel noise floor now validates
- P1 (fidelity r2) prev fixed: effect change gives the frame's sentence
- P1 (fidelity r2) prev fixed: a saved new event is staged in the save bar
- P1 (fidelity r2) prev fixed: status and excluded-spans cells open popovers

**`settings.vocabulary` — open findings after the last round**
- P1 (function r1) Tag 'Merge' is a dead click
- P1 (function r1) Tag definition cell is not editable
- P1 (function r1) Rename accepts an uppercase name its own error rejects

**`settings.nulls` — open findings after the last round**
- P1 (function r1) seed = 'fixed' does not reveal the seed Number field

**`settings.analysis-defaults` — open findings after the last round**
- P1 (fidelity r1) history link missing on four of the seven recommended-value rows
- P1 (function r1) '+ Add a rule for a block parameter' is a dead click

**`settings.compute-hpc` — open findings after the last round**
- P1 (function r1) Script preview emits '--gres=none' for a profile with no gres
- P1 (function r1) Job-profile table cells cannot be edited
- P1 (function r1) Adding a cluster writes immediately instead of staging

**`settings.blocks` — open findings after the last round**
- P1 (function r1) Disabling a block gives 'on true -> false' instead of its consequence

**`settings.review-queues` — open findings after the last round**
- P1 (fidelity r1) Invalid cap shows no reason and the save bar restates the invalid value
- P1 (function r1) Locked 'undo reverses the whole batch' and 'S promotes' give no reason
- P1 (function r1) Queue consequences are the generic fallback

**`settings.models-registration` — open findings after the last round**
- P1 (fidelity r1) Save-bar consequence is a raw field-id restatement
- P1 (function r1) Registration-gate thresholds accept any text
- P1 (function r1) Leave guard does not fire on the nav rail (shell-wide)

**`settings.library-groupings` — open findings after the last round**
- P1 (fidelity r1) Weights and unit edits produce a raw field-id consequence
- P1 (function r1) Saving a shared sequence field leaves Review queues with an unsaved edit the user never made

**`settings.storage-backups` — open findings after the last round**
- P1 (fidelity r1) Token edits break the save bar: raw list diff, truncated, label wraps

**`settings.export` — open findings after the last round**
- P1 (fidelity r1) Include-row consequence is a constant, wrong for notes and omitted list
- P1 (fidelity r1) Other export edits produce raw list-diff consequences
- P1 (function r1) Include-row sentence claims 'hand edits now included' for any include change
- P1 (fidelity r2) prev fixed: include-row consequence is a constant
- P1 (fidelity r2) prev fixed: other export edits produce raw list-diff consequences
- P1 (function r2) prev fixed: include-row consequence is a constant
- P1 (function r2) prev fixed: other export edits produced raw list-diff consequences
- P1 (function r2) prev fixed: Saved toast misdescribed the change

**`settings.display` — open findings after the last round**
- P1 (fidelity r1) Report-figure preview ignores line width, grid opacity and background
- P1 (function r1) Density 'compact' changes nothing
- P1 (function r1) Units and time selections have no effect, not even on the preview beside them
- P1 (function r1) Report figure preview does not reflect line width, grid opacity or font
- P1 (fidelity r2) prev fixed: report-figure preview ignores line width, grid opacity and background
- P1 (fidelity r2) prev fixed: density 'compact' changes nothing
- P1 (fidelity r2) prev NOT fixed (now disclosed): units still change nothing outside this page
- P1 (fidelity r2) Family palette's last swatch is the run-A blue, against D8
- P1 (function r2) prev fixed: density 'compact' changed nothing
- P1 (function r2) prev fixed: report preview ignored line width, grid and font
- P1 (function r2) prev fixed: units selections had no effect

**`settings.keyboard` — open findings after the last round**
- P1 (fidelity r1) Key capture does not take focus; first key press is ignored
- P1 (function r1) Key capture never receives focus — pressing a key after clicking a cell does nothing
- P1 (function r1) Moving a key off a locked verdict binds it twice under 'no conflicts'
- P1 (function r1) 'confirm before leaving unsaved settings' toggle has no effect
- P1 (fidelity r2) prev fixed: key capture does not take focus
- P1 (fidelity r2) prev fixed: moving a key off a locked verdict bound it twice
- P1 (fidelity r2) prev fixed: 'confirm before leaving unsaved settings' toggle had no effect
- P1 (function r2) Rebinding onto a class key (1-9) is accepted with 'no conflicts'
- P1 (function r2) Ctrl K during capture binds bare 'K' and opens the search panel at once
- P1 (function r2) prev fixed: key capture did not take focus
- P1 (function r2) prev fixed: moving a key off a locked verdict bound it twice
- P1 (function r2) prev fixed: 'confirm before leaving unsaved settings' toggle had no effect
