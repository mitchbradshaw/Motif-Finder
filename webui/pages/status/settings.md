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
| settings.channels-events | `#/settings/channels-events` | `default` · `unsaved` · `rows-all` (`?rows=all`) · `rec:<id>` (`?rec=M3_jul`) · `rec-M4_aug-locked` · `add-event` (`?modal=add-event`) · `add-event-valid` · `event-added-staged` · `event-removed` · `event-selected` (`?event=e2`) · `status-popover` (`?pop=status:CH7_B2`) · `status-popover-by-click` · `spans-popover` (`?pop=spans:CH2_A1`) · `floor-invalid` · `timeline-all` (`?view=all`) · `add-kind` · `add-kind-valid` (`?pop=kind`) |
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

## Fix round 2 (2026-09-21) — critics' P1s on channels-events

**settings.channels-events** (fidelity P1 + six function P1s). The page was a table of live controls over
dead cells; every fix moves one of those cells into the same draft the save bar already reads.

- **Timeline readable.** M2_aug fs1 is 721 h and its four events sit in the first 50, so at full scale the
  markers were hairlines and the `40.1 h → end` exclusion painted 95 % of the strip. The strip now defaults
  to the window that holds every event (`0 – 50 h of 721 h · all 4 events`), with the whole recording one
  click or `?view=all` away — the inventory's own recommendation against drawing a 45 h recording. Spans
  are never thinner than a point marker and sit at 40 % alpha, so the 0.2 h exclusion is visible.
- **Consequences are derived, not tabulated.** `genericConsequence` now recognises the runtime key
  namespaces of this page (`gain.`, `floor.`, `status.`, `effect.`, `events.added.`, `events.removed.`)
  and builds the sentence from the event and channel themselves, so *every* event gives the frame's
  sentence (`excluding 31.1–31.5 h on all channels marks 3 runs on M2_aug fs1 stale`), never the row id
  `e1`. The two static entries for `CH6_B1` gain and `e3` are deleted — the builder reproduces both,
  with 2 dp.
- **Noise floor and gain validate.** A local `NumberCell` keeps the decimals ("1.00"), carries the
  placeholder `recording`, states one rule when it is broken (`Enter a floor between 0.01 and 5 mV`,
  `Gain must be a positive number`) and never commits a value outside it; Save is disabled with the count.
- **Event rows are drafts.** Added rows and staged removals live in the store under one key each
  (`events.added.<rec>`, `events.removed.<rec>`), so a new event raises the save-bar count with its own
  consequence and Discard takes it away again; a removal shows the row dimmed and struck, with an undo.
- **Status and excluded-spans cells open.** The status Badge is a button → Popover (Seg `ok` / `bad from`
  + time field); setting `bad from` stages the linked `electrode` event, and reading a channel `ok` again
  stages removal of the event that marked it bad (fog F8: the event is the record). The spans cell lists
  the spans that touch the channel, each a link to its event row (`?event=e2`), and the count is now
  derived from the live effects rather than fixture text.
- **`+ kind` accepts its own example.** `co2-pulse` is valid (`^[a-z][a-z0-9-]{1,19}$`).
- Every popover on the page is a URL state (`?pop=status:<ch>` / `spans:<ch>` / `kind`), so each is
  reachable by click **and** by query parameter and two cannot be open at once. This also makes the
  states order-independent in the manifest: a same-route goto does not remount, so a second state that
  clicked the same trigger used to toggle the popover shut.
- Cheap P2s with it: card captions and the timeline row use the display name `M2_aug fs1`, gain reads
  `1.00`, and the recording Seg moved into the Channels card header (it stays above the card on a failed
  read, or an unknown `?rec` would be a dead end).

**Gate:** `npx tsc --noEmit -p tsconfig.app.json` clean for the unit; smoke `--only settings` 0 failures
(nine states added). Screenshots of the changed states: `webui/screenshots/build/settings/fix/`
(`channels.default`, `channels.timeline-all`, `channels.floor-invalid`, `channels.floor-valid`,
`channels.effect-e1`, `channels.gain-invalid`, `channels.event-added`, `channels.event-discarded`,
`channels.event-removed`, `channels.status-popover`, `channels.status-ok`, `channels.status-badfrom`,
`channels.spans-popover`, `channels.add-kind`).

## Fix round 3 (2026-09-21) — critics' two remaining P1s on settings.keyboard

Both are the same hole from opposite sides: the capture cell read a key press as a bare letter and
nothing else, so anything the key map did not literally spell went through as "no conflicts".

- **A class key is a key.** The classes row is drawn as the range `1 – 9`, so the conflict check —
  which compared the pressed key against the literal cells — saw nothing owning `3` and bound skip to
  it under a green badge, while `S` (spelled out in the verdicts row) correctly raised the locked
  owner. `KeyBinding` now carries `covers`, the keys a range row really owns (`1`…`9` for classes),
  and the owner lookup reads `keys + covers`. Pressing `3` on `skip without writing` now gives the
  same locked-owner conflict as `S`: red `1 conflict`, "3 is bound to “classes”. A key does one
  thing.", the Vocabulary sentence, Open Vocabulary, and `Move 3 here` disabled with its reason.
- **A chord is one press.** `Ctrl K` in an open capture cell dropped the modifier, bound bare `K`, and
  *also* fired the global Ctrl K, so one press rebound a row and opened the search panel. Capture now
  composes the chord (`Ctrl` · `Alt` · `Shift` + base, the fixture's own spelling — `Ctrl Shift Z`),
  ignores a modifier pressed alone, and stops the event, and the global handler returns early while an
  element with `data-capturing` holds focus. `Ctrl K` there raises the conflict against `search`, the
  search panel does not open, and `Ctrl K` with no cell capturing still opens it. A free chord
  (`Ctrl J`) binds as one cap. Shift is only named inside a chord — with no modifier the shifted
  character is already the key.

**Gate:** `npx tsc --noEmit -p tsconfig.app.json` clean for the unit; smoke `--only settings`
122 screenshots, 0 failures (two states added: `keyboard--conflict-class-key`, `keyboard--capture-chord`).
Screenshots: `webui/screenshots/build/settings/fix/keyboard.conflict-class-key.png`,
`keyboard.capture-chord.png`, `keyboard.capture-rebound.png`.

## Fix round 4 (2026-09-21) — critics' P1s on settings.channels-events

Five P1s, four of them the same shape: a cell drawn as a control that nothing read or wrote.

- **Shared ground is editable.** The amber chip (and the dash on every unpaired row) is now the
  control: click it and it becomes a Select of the other channels of the recording (`?pop=ground:CH3_A2`
  deep-links it). The write is symmetric — pairing CH1_A1 with CH3_A2 writes both cells and clears the
  partner CH3_A2 left behind — and the bar says `CH1_A1 and CH3_A2 count once in Library recurrence on
  M2_aug fs1`. New draft key `ground.<rec>.<ch>`; M4_aug stays a read-only chip.
- **Timeline markers select.** `BandStrip` cannot take a click or draw a selection (kit is read-only,
  request R11), so the Event log draws `EventStrip` from the same primitives: an 8 px circle per event
  in its kind's colour, translucent bands for excluded spans, **round-hour ticks** (0/10/…/50 h, and
  0/200/400/600 h on the whole recording — fidelity P2), a blue ring on the selected event and a click
  (or Enter on the focused marker) that sets `?event=<id>` and highlights the row. Both directions now
  work: `?event=e2` rings the marker, clicking the marker highlights the row.
- **A new kind is staged, not committed.** `+ kind` wrote a demo-store key and survived navigation with
  no save bar and no undo. It is now the draft key `event.kinds` like every other edit: staged chip in
  amber, bar `co2-pulse joins the event kinds · it can be picked in Add event · no run is marked stale`,
  and Discard takes it back.
- **Channel status is read back from the events, in both directions.** There is no longer a `status.*`
  value at all: the badge is derived from the live mark-bad events (fog F8 — "the event is the record"),
  so setting the 12.5 h all-channels event to *exclude · mark channel bad* turns every channel red, and
  setting the 40.1 h → end event back to *show on plots* turns CH7_B2 green — the two could previously
  disagree forever. The popover lists the events it reads back, each a link to its row, and *ok* is
  disabled with its reason when an all-channels event is what marks the channel bad. A removal now
  carries the effect it had when it was removed (`events.removed` holds `{id, effect}`), so the sentence
  says what the removal actually undoes.
- **`?state=unsaved` is the frame's two changes.** The seed staged `effect.e3 = exclude span` over a
  saved value that was already `exclude span`, so it counted as one change and drew no diff. Canon for
  e3 is now `show on plots` (the inventory's own reading of frame 02: the exclusion is the seeded edit),
  so the bar reads `2 unsaved changes`, both the CH6_B1 gain and the 31.1–31.5 h effect Select carry the
  amber outline **and an amber dot** (new: a table cell has no label to dot), and the excluded-spans
  column reads exactly as the frame draws it. The 13 Sep audit line was reworded to match.
- Cheap P2s with it: add-event validation gives one reason per broken rule (reversed span, unparseable
  time, out of range) and prints it inline instead of only in a hover; Escape closes the add-event row;
  the effect Select no longer clips `exclude · mark channel bad`; a field error inside a table cell keeps
  to one line instead of tripling the row.

**Gate:** `npx tsc --noEmit -p tsconfig.app.json` clean for the unit; smoke `--only settings`
127 screenshots, 0 failures (five states added: `channels-events--ground-select`,
`ground-select-by-click`, `kind-staged`, `marker-selected`, `status-sources`).
Screenshots: `webui/screenshots/build/settings/fix/{default,unsaved,ground-paired,kind-staged,
marker-selected,ch7-ok,all-bad,floor-invalid,timeline-all}.png`.
