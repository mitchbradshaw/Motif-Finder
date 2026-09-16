# Status — Settings (webui build)

Builder: settings unit. Sixteen concept pages behind one shell (`#/settings/<slug>`), all fixture-only
(spec §9, §12 P23). Frames: `prototyping/imgs/settings/*.pdf`. Inventory: `webui/pages/inventory/settings.md`
(covers the shell and pages 01–10; 11–16 built from spec §9.11–§9.16 and their frames).

Owned files: `webui/client/src/settings/`, `src/api/settings.ts`, `src/fixtures/settings.ts`,
`webui/smoke_pages/settings.json`, `webui/pages/{status,fog,requests}/settings.md`,
`webui/screenshots/build/settings/` (gitignored).

## Shell (all sixteen pages) — `settings/chrome.tsx`, `settings/store.ts`, `settings/settings.css`

- SideNav: `PROJECT · recorded with runs` (Data / Analysis / Workspaces / Files / Record) and
  `PERSONAL · this browser` (Interface); amber "differs from default" dots **computed per page** from the
  store (B29 fix), legend line.
- Title row: H1 + scope Badge + page actions + `Reset page to defaults` (Popover confirm; disabled with a
  reason when nothing differs; hidden on Audit log and About).
- Draft model: project edits go to a draft; the sticky save bar states the consequence (P23) and Save
  writes the in-memory store, an audit entry and a toast. Discard reverts. Personal pages have no bar —
  every change applies immediately with "Applied to this browser".
- Invalid fields disable Save with a reason. Leave guard on settings-nav clicks with unsaved edits.
- `?state=unsaved` seeds the frame's scripted edit · `?focus=<field>` pulses a field · Ctrl K and the
  header search pill open the settings search index.

## Pages — all sixteen built

| page | route | states (query parameter / click) |
|---|---|---|
| settings.datasets | `#/settings/datasets` | `default` · `unsaved` · `selected:<rec>` (`?rec=M3_jul`) · `held-out-locked` (`?rec=M4_aug`) · `invalid-noise-floor` · `import` (`?modal=import`) · `import-expanded` · `import-check-failed` (`&path=M4_aug_concat.mat`) · `import-running` · `unlock-confirm` (`?modal=unlock`) · `unlock-typed` |
| settings.channels-events | `#/settings/channels-events` | `default` · `unsaved` · `rows-all` (`?rows=all`) · `rec:<id>` (`?rec=M3_jul`) · `rec-M4_aug-locked` · `add-event` (`?modal=add-event`) · `add-event-valid` · `add-kind` |
| settings.vocabulary | `#/settings/vocabulary` | `default` · `rename` (`?rename=interesting&to=noteworthy`) · `rekey` (`?rekey=seed`) · `add-verdict` / `add-class` / `add-tag` (`?add=…`) · `merge-tag` · `class-non-informative` |
| settings.nulls | `#/settings/nulls` | `default` (differs: Holm) · `unsaved` · `invalid-alpha` · `method-changed` |
| settings.analysis-defaults | `#/settings/analysis-defaults` | `default` · `unsaved` · `history` (`?history=band`) · `context-M3_jul` (`?ctx=`) · `invalid-band` · `clear-cache` (`?modal=clear-cache`) · `clearing` |
| settings.compute-hpc | `#/settings/compute-hpc` | `default` · `unsaved` · `benchmark-running` / `benchmark-done` · `profile:<name>` (`?profile=cpu-array`) · `editor-raw` (`?editor=raw`) · `email-off` · `add-cluster` (`?modal=add-cluster`) · `add-cluster-empty-profiles` |
| settings.blocks | `#/settings/blocks` | `default` · `unsaved` · `used-by` (`?usedby=sax`) · `disable-by-click` |
| settings.review-queues | `#/settings/review-queues` | `default` (differs) · `unsaved` · `unblind-warning` · `invalid-cap` · `suggest-warning` |
| settings.models-registration | `#/settings/models-registration` | `default` (differs) · `unsaved` · `repeats-on` · `invalid-split` · `no-arm` · `unpaired-arms` |
| settings.library-groupings | `#/settings/library-groupings` | `default` (differs) · `unsaved` · `unit-spike-trains` · `omit-warning` · `weights` |
| settings.storage-backups | `#/settings/storage-backups` | `default` · `unsaved` · `low-disk` (`?state=low-disk`) · `scanning` · `token-removed` · `add-token` · `backup-running` · `restore` (`?modal=restore`) |
| settings.export | `#/settings/export` | `default` · `unsaved` · `include-notes` · `layout-per-family` |
| settings.audit-log | `#/settings/audit-log` | `all` · `kind:<kind>` (`?kind=lock`) · `kind-by-click` · `no-reset-link` (Export CSV replaces it) |
| settings.about | `#/settings/about` | `default` · `mismatch` (`?state=mismatch`) · `lock-file` (`?modal=lock`) · `copy-diagnostics` |
| settings.display (personal) | `#/settings/display` | `default` · `applied-immediately` (no save bar) · `sample-indices-on` |
| settings.keyboard (personal) | `#/settings/keyboard` | `default` · `conflict` (`?state=conflict`) · `capture` · `behaviour-off` |
| settings.shell | any | `search` · `search-hit` · `search-empty` · `leave-guard` · `confirm-reset` · `reset-stages-defaults` · `save` · `discard` · `unknown-slug` |

## Gate

- `npx tsc --noEmit -p tsconfig.app.json` — clean for `src/settings`, `src/api/settings`,
  `src/fixtures/settings` (the only errors in the project are another unit's `src/training/*`).
- `smoke.py --url http://127.0.0.1:5173 --pages-only --only settings` — see the run line in the final
  report; 103 states listed in `webui/smoke_pages/settings.json`.
- Build screenshots (one per page, gitignored): `webui/screenshots/build/settings/`.

## Known gaps

- Job-profile table cells are read-only (fog FE17); only the editor below them is editable.
- Theme / density write but change nothing visible (FE19); personal settings are in-memory, not
  `localStorage` (FE20).
- The header's `M4 held out` chip does not follow the lock (request R2); the leave guard covers only the
  settings nav (R3).
- Audit entries written this session reset on reload (FE15).
