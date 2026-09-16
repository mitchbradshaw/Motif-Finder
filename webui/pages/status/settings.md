# Status — Settings (webui build)

Builder: settings unit. Sixteen concept pages behind one shell (`#/settings/<slug>`), all fixture-only
(spec §9, §12 P23). Frames: `prototyping/imgs/settings/*.pdf`. Inventory: `webui/pages/inventory/settings.md`
(covers the shell and pages 01–10; 11–16 are built from spec §9.11–§9.16 and their frames).

Owned files: `webui/client/src/settings/`, `src/api/settings.ts`, `src/fixtures/settings.ts`,
`webui/smoke_pages/settings.json`, `webui/pages/{status,fog,requests}/settings.md`,
`webui/screenshots/build/settings/`.

## Shell (all sixteen pages)

`settings/chrome.tsx` + `settings/store.ts` + `settings/settings.css`.

- SideNav: PROJECT · recorded with runs (Data / Analysis / Workspaces / Files / Record) and
  PERSONAL · this browser (Interface), amber "differs from default" dots **computed per page** from the
  store (B29 fix), legend line.
- Page title row: H1 + scope Badge + `Reset page to defaults` (Popover confirm; disabled with a reason
  when nothing differs).
- Draft model: project edits go to a draft, sticky save bar states the consequence (P23), Save writes
  the in-memory store + an audit entry + a toast; Discard reverts. Personal pages apply immediately with
  an "Applied to this browser" toast and no save bar.
- Leave guard on nav-rail clicks with unsaved edits; `?state=unsaved` seeds the frame's scripted edit;
  `?focus=<field>` pulses a field; Ctrl K / the header search pill open the settings search index.
- Invalid fields disable Save with a reason.

## Pages

| page | route | states | status |
|---|---|---|---|
| settings.datasets | `#/settings/datasets` | `default` · `unsaved` (`?state=unsaved`) · `selected:<rec>` (`?rec=`) · `locked` (M4_aug row) · `import` (`?modal=import`) · `import-failed` (`?modal=import&path=M4_aug_concat.mat`) · `unlock` (`?modal=unlock`) | done |
| settings.channels-events | `#/settings/channels-events` | — | todo |
| settings.vocabulary | `#/settings/vocabulary` | — | todo |
| settings.nulls | `#/settings/nulls` | — | todo |
| settings.analysis-defaults | `#/settings/analysis-defaults` | — | todo |
| settings.compute-hpc | `#/settings/compute-hpc` | — | todo |
| settings.blocks | `#/settings/blocks` | — | todo |
| settings.review-queues | `#/settings/review-queues` | — | todo |
| settings.models-registration | `#/settings/models-registration` | — | todo |
| settings.library-groupings | `#/settings/library-groupings` | — | todo |
| settings.storage-backups | `#/settings/storage-backups` | — | todo |
| settings.export | `#/settings/export` | — | todo |
| settings.audit-log | `#/settings/audit-log` | — | todo |
| settings.about | `#/settings/about` | — | todo |
| settings.display | `#/settings/display` | — | todo |
| settings.keyboard | `#/settings/keyboard` | — | todo |

## Gate

- `npx tsc --noEmit -p tsconfig.app.json` — clean for `src/settings`, `src/api/settings`, `src/fixtures/settings`.
- `smoke.py --pages-only --only settings` — see the smoke line at the end of this file.
