# Library — build status

| page | route | status | states (smoke) | what's left | last commit |
|---|---|---|---|---|---|
| library.atlas | `#/library/atlas` | done | motifs, sequences, family-selected, groupings-popover, omitted-drawer, no-scope, empty | atlas cards for feature-bin / label groupings (g-09, g-01) are not drawn — honest EmptyState | bafe9db |
| library.family | `#/library/family/F-03` | done | member-selected, revisions-popover, hand-only, sort-time-page-2, tag-popover-invalid, class-popover, confirm-make-exemplar, confirm-remove, sequence-family, unknown-family | sequence family page is a placeholder (not drawn in any frame) | bafe9db |
| library.recurrence | `#/library/recurrence` | done | selected, count, recordings-4-5, omitted-drawer, sequences, empty, no-selection | hidden channels (+10 ch) have no expander (fog) | 8453867 |
| library.grouping | `#/library/grouping?from=atlas&basis=frequency-content` | done | frequency-content, unchanged-shape-distance, invalid, applying, failed, unit-sequences, over-limit, basis-custom, saved | per-basis panels other than frequency content are extrapolations (fog) | 8453867 |
| library.import | `#/library/import?library=empty` | done | empty-dry-run, dry-run-populated, bundle-invalid, held-out-refused, importing, failed, done, check-expanded | post-import g-01 catalogue has no fixture (toast says so) | bc7f8d0 |
| library.window-sets | `#/library/window-sets` | done | set-selected, not-train-safe-selected, supplied-no-split, coverage-at-save, filter-not-train-safe, filtered-empty, recording-popover, import-modal-refused, delete-confirm, none | — | 4767b94 |
| library.templates | `#/library/templates` | done | template-selected, training-selected, unscored-selected, kind-training, model-stage, page-2, filtered-empty, diff-modal, export-json, import-json-invalid, archive-confirm | — | 53d8dc5 |

Gate: `npx tsc --noEmit -p tsconfig.app.json` clean for library files; `smoke.py --pages-only --only library` → 62 screenshots, 0 failures.
Fog: `pages/fog/library.md` · shared-code requests: `pages/requests/library.md` · build screenshots: `webui/screenshots/build/library/`.
