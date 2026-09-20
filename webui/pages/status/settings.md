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
- Theme `dark` writes but changes nothing visible (FE19, the caption says so); personal settings are
  in-memory, not `localStorage` (FE20). Density is wired as of fix round 1 (see below).
- The header's `M4 held out` chip does not follow the lock (request R2); the leave guard covers only the
  settings nav (R3).
- Audit entries written this session reset on reload (FE15).

## Orchestrator fixes (2026-09-20, after the builder was stopped by the weekly limit)

- Builder's last uncommitted diff landed: search modal and reset popover are deep-linkable (?search=1, ?reset=1)
  and close on hash change; the keyboard conflict banner is derived from ?state=conflict rather than seeded once;
  smoke selectors fill the input elements directly.
- DatasetsPage: the import-recording timer is owned by the open modal and stops when it closes, so a finishing
  import no longer navigates to M5_sep from under a later state (it closed the unlock modal in the smoke).
- NullsPage: the smallest-reportable-p check considers only null kinds that report a p (NullKind.p_value); the
  full-model shuffle (5 retrains, drawn as dots) and grouping stability no longer bound alpha, so Save is enabled
  on a valid draft.
- Manifest: settings.shell discard runs on analysis-defaults (a same-URL goto does not remount, so save then
  discard on one hash could not both pass). 107 states, 0 failures.

## Fix round 1 (2026-09-21) — critics' P1s on export, display, keyboard

**settings.export** (fidelity/function P1 · the save-bar consequence was a constant or a raw list diff)
- `fixtures/settings.ts`: `motifs.include` no longer returns one hard-coded sentence. A `listSentence`
  helper diffs the before/after list and says what changes about the files that leave the tool
  ("family exports now carry notes · exports already written are unchanged"), and every other export
  field — formats, layout, window-set format and include, carry-exemplars, weights, report layout,
  bundle contents — has its own P23 consequence instead of `genericConsequence`'s "applies to new runs"
  (exports have no runs). `SEED_SENTENCE.export` is deleted: the seeded edit now derives the same
  sentence, so the two cannot drift apart again.

**settings.display** (fidelity P1 + three function P1s)
- The report-figure preview is live: `strokeWidth` is bound, the grid is a `.s-fig::after` overlay at
  `--fig-grid`, the chosen font applies to the plot's tick text and the caption, and `transparent`
  clears the ground rect and shows a chequer instead of recolouring the trace.
- `density: compact` is real: `SettingsShell` writes `html[data-density]` and `settings.css` tightens
  `.k-table` rows, `.s-row` and `.k-nav-item` (keys table row 35 → 31 px, nav row 30 → 24 px).
- Units and time: the card no longer claims "every readout on every page". It carries one live example
  readout that follows time axis, amplitude and sample indices, and the prefs are published to the
  demo-store key `settings.display` for other workspaces to bind (request R7). The kit `Trace` cannot
  label µV or draw a grid — request R8.

**settings.keyboard** (fidelity P1 + three function P1s)
- Key capture takes focus for real (a `ref` callback; `autoFocus` is not honoured on a span), so the
  first key press after clicking a key cell registers.
- A conflict whose current owner is **locked** (the vocabulary's verdict and class keys) disables
  "Move <key> here" with its reason and offers Open Vocabulary, instead of binding the key twice and
  returning a green "no conflicts" badge.
- The leave guard is driven by `confirm before leaving unsaved settings`: with it off, navigating away
  leaves without asking and raises a toast naming the page that still holds the unsaved edits.

**Gate:** `npx tsc --noEmit -p tsconfig.app.json` clean for the unit; smoke `--only settings`
110 screenshots, 0 failures (three states added: `keyboard--capture-rebound`,
`keyboard--conflict-locked-owner`, `display--report-profile-transparent`).
Screenshots of the changed states: `webui/screenshots/build/settings/fix/`.

