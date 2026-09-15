# Inventory — Settings

Frames: `prototyping/imgs/settings/*.pdf` (17 = 16 pages + 01b import modal), exported from
`UI_settings_v1.pen`. Spec: `UI_FUNCTIONAL_SPEC.md` §9 (lines 988–1193), §12 P23, §0 canon, §3.
All frames are 1440×900 at the design, but several pages are taller than the viewport and
**scroll** inside the content column (06 Compute & HPC ≈ 1.3× height, 09, 05, 03, 11, 12 ≈ 1.1×).
The PDF images are rendered at a reduced scale (1060–1390 px wide); proportions below are given
against a 1440×900 viewport.

Settings is **not a live workspace**: nothing under `#/settings/*` is wired to the bridge today
(`App.tsx` renders it through `Inert`). Every page is an empty shell on fixture data. Two bridge
calls already exist that a builder may *optionally* read for the Datasets and Blocks pages
(`GET /api/recordings`, `GET /api/adapters`), but the fixture canon wins on screen (see those pages).

## Pages

| page id | route | frames covered | spec § | states (frame → state name → how reached) |
|---|---|---|---|---|
| settings.shell | (layout for every `#/settings/*`) | all 17 | §9 "Shape", P23 | dirty → `unsaved` (edit any project field; save bar appears) · personal page → `applied` (toast "applied to this browser") · reset → `confirm-reset` popover (click *Reset page to defaults*) · search → `search-open` (Ctrl K / click search pill) |
| settings.datasets | `#/settings/datasets` (default for bare `#/settings`) | settings-01-datasets, settings-01b-import-recording | §9.1, D6, B20 | 01 → `default` + `unsaved` (3 changes shown) · row click → `selected:<recording>` (`?rec=M2_aug_fs1`) · 01b → `import` modal (click *Import a recording…*; `?modal=import`) · import sub-states `import:checking` / `import:checks-ok` / `import:check-failed` / `import:importing` / `import:done` · lock → `unlock-confirm` modal (toggle held-out off; `?modal=unlock`) |
| settings.channels-events | `#/settings/channels-events` | settings-02-channels-events | §9.2 | 02 → `default` + `unsaved` (2 changes) · recording Seg (`?rec=M4_aug` etc.) · `expanded` (click *8 more channels*; `?rows=all`) · `add-event` popover/row (click *Add event*; `?modal=add-event`) · `add-kind` popover (click *+ kind*) · M4_aug tab → `locked` (held-out banner) |
| settings.vocabulary | `#/settings/vocabulary` | settings-03-vocabulary | §9.3 | 03 → `rename-inline` (click *rename* on interesting; `?rename=interesting`) + `unsaved` · `rekey-inline` · `add-verdict` (role required) · `add-class` · `add-tag` · `merge-tag` popover · delete blocked on core five (locked) |
| settings.nulls | `#/settings/nulls` | settings-04-nulls | §9.4 | 04 → `differs` (training baseline draws + Holm differ; no save bar) · `unsaved` after any edit · `invalid` (draws < 1 or α out of range) |
| settings.analysis-defaults | `#/settings/analysis-defaults` | settings-05-analysis-defaults | §9.5, D4 | 05 → `unsaved` (bandpass rule edited) · `history` popover per rule (click *history*; `?history=bandpass`) · `add-rule` row · `clear-cache` confirm (click *Clear cache*; `?modal=clear-cache`) → simulated clearing → done toast |
| settings.compute-hpc | `#/settings/compute-hpc` | settings-06-compute-hpc | §9.6, B19 | 06 → `differs` (Analyse limit) · `benchmark:running` → `benchmark:done` (click *Run benchmark*; `?state=benchmark`) · profile row select (`?profile=gpu-single`) · editor Seg `guided` / `raw` (`?editor=raw`) · `add-cluster` modal (`?modal=add-cluster`) · `unsaved` |
| settings.blocks | `#/settings/blocks` | settings-07-blocks | §9.7, B13, B24 | 07 → `unsaved` (Symbolic encoding toggled off) · *N templates* popover (click link; `?usedby=sax`) · not-built row disabled |
| settings.review-queues | `#/settings/review-queues` | settings-08-review-queues | §9.8, P20, P21, B16 | 08 → `differs` (training-window cap) · `unsaved` after edit |
| settings.models-registration | `#/settings/models-registration` | settings-09-models-registration | §9.9, P19 | 09 → `differs` (warn-below field) · seed repeats toggle on → repeats field enabled · `unsaved` · `invalid` (test + validation ≥ 100 %) |
| settings.library-groupings | `#/settings/library-groupings` | settings-10-library-groupings | §9.10, P22, B16, B17 | 10 → `differs` (omit d) · unit Seg changes basis options · `unsaved` · `invalid` (weights ≠ 1.0) |
| settings.storage-backups | `#/settings/storage-backups` | settings-11-storage-backups | §9.11 | 11 → `unsaved` (keep 7 → 14) · `backup:running` → `backup:done` (click *Back up now*; `?state=backup`) · `restore` modal (click *Restore…*; `?modal=restore`) · `add-token` popover · `scan:running` per root · low-disk warning (`?state=low-disk`) |
| settings.export | `#/settings/export` | settings-12-export | §9.12 | 12 → `unsaved` (hand edits chip on) |
| settings.audit-log | `#/settings/audit-log` | settings-13-audit-log | §9.13 | 13 → `all` · kind filter (`?kind=lock`) · `empty-filter` · entry link → navigates |
| settings.about | `#/settings/about` | settings-14-about | §9.14 | 14 → `default` · *Copy diagnostics* → toast · version mismatch variant (`?state=mismatch`) |
| settings.display | `#/settings/display` | settings-15-display | §9.15 | 15 → `default` (personal; changes apply immediately, no save bar) · theme/density/units live preview |
| settings.keyboard | `#/settings/keyboard` | settings-16-keyboard-behaviour | §9.16 | 16 → `default` · `capture` (click a key cell; "press a key…") · `conflict` (captured key already bound; `?state=conflict`) |

Route aliases: `#/settings` → redirect to `#/settings/datasets`. Unknown slug → EmptyState "No settings page called `<slug>`" with a link back to Datasets.

---

## settings.shell (shared by all 16 pages)

### Route & states
- Every page is `#/settings/<slug>`. The workspace header shows **Settings** as the workspace
  and the page name (e.g. `Datasets`) with a mono muted scope word (`project` or `personal`).
- Shell-level states (apply to every page):
  - `clean` — no unsaved edits; no save bar.
  - `unsaved` (project pages only) — ≥ 1 edit held in memory; sticky save bar visible at the
    bottom of the content column; the rail item keeps its amber dot; edited fields get an amber
    outline and an amber dot before their label. Reached by editing any field. Deep link for
    screenshots: `?state=unsaved` loads the frame's pre-baked edit (each page section names it).
  - `saving` → `saved` — *Save changes* disables for ~600 ms (spinner on the button, label
    "Saving…"), then the bar slides away, toast "Saved · <consequence sentence>" and an in-memory
    audit-log entry of kind `settings` is appended (see settings.audit-log).
  - `confirm-reset` — Popover anchored to *Reset page to defaults*: "Reset <page> to defaults?
    <N> values differ. Project pages: nothing is written until you save." Buttons *Cancel* /
    *Reset*. On a project page Reset stages the default values as unsaved edits (save bar shows
    them); on a personal page it applies immediately.
  - `leave-guard` — navigating away (rail item, nav rail, browser hash change) with unsaved
    edits opens a Modal "Leave with 3 unsaved changes?" *Stay* / *Discard and leave* (driven by
    the Keyboard & behaviour toggle "confirm before … leaving unsaved settings", default on).
  - `search-open` — Popover under the header search pill listing matching settings
    (page › card › field), Enter navigates and scrolls/highlights the field. Fixture: an index of
    every field label on the 16 pages.
  - Personal pages have no save bar; each change fires Toast "Applied to this browser" (throttled,
    one per 2 s) and persists to `localStorage` (try/catch).

### Regions (1440×900)
Top→bottom, left→right:
1. **Nav rail** (shared kit, 64 px): Explore · Analyse · Discovery · Models · Review · Library;
   foot `Jobs · 3`, separator, **Settings** highlighted (blue-100 tile).
2. **Header** (shared kit, ~42 px tall, full width right of the rail): left `Settings` (bold) ·
   vertical divider · page name (e.g. `Channels & events`) · muted mono scope word `project` /
   `personal`. Right: search pill placeholder **`Search settings`** with `Ctrl K`, chip
   `● 3 need you` (blue), chip `🔒 M4 held out` (grey). No "demo data" chip is drawn in the
   frames; the kit header adds it (keep it, right of the search pill).
3. **Settings nav** (left column, ~230 px wide ≈ 16 % of 1440, white card ground, full height,
   right border). Content top→bottom:
   - Scope header row: folder icon + `PROJECT · recorded with runs` (blue, mono, 10–11 px).
   - Group label `Data` (muted, 10 px): `Datasets` · `Channels & events` · `Vocabulary`.
   - Group `Analysis`: `Nulls` · `Analysis defaults` · `Compute & HPC` · `Blocks`.
   - Group `Workspaces`: `Review queues` · `Models & registration` · `Library groupings`.
   - Group `Files`: `Storage & backups` · `Export`.
   - Group `Record`: `Audit log` · `About`.
   - Scope header row: monitor icon + `PERSONAL · this browser` (muted mono).
   - Group `Interface`: `Display` · `Keyboard & behaviour`.
   - Legend line: amber dot + `differs from default` (muted, 10 px).
   - Items are ~28 px rows, 13 px text; the current page is a blue-100 filled row with blue text
     (rounded 6 px, inset 8 px). An amber 6 px dot sits right-aligned on items whose page
     differs from default. In every frame the dots are on: Nulls, Analysis defaults, Compute &
     HPC, Review queues, Models & registration, Library groupings, Storage & backups (7).
4. **Content column** (≈ 1080 px wide, padding 22 px, light grey ground `--bg`), scrolls:
   - **Page title row**: H1 page name (22 px bold) + scope Badge `project · recorded with runs`
     (blue-100 pill, mono 10 px) or `personal · this browser` (grey pill); right-aligned ghost
     link-button with reset icon `Reset page to defaults` (blue).
   - **Lede**: one mono muted sentence under the title (per page, see Copy).
   - **Cards**: stacked SectionCards (white, 1 px border, 10 px radius, 12 px gap). Card title
     row = bold 13 px title + muted mono sub-caption inline (e.g. `Recordings  5 recordings ·
     61 channels`), optional right-side action button or status chip. Settings cards are **not
     numbered** (no "1 Title (i)"); the numbered form appears only inside the import modal.
   - **Row grammar** inside cards (two kinds):
     - *Form rows*: label (mono 11 px, left, ~300 px column) · control (~180–320 px) · right-aligned
       muted mono consequence caption (P23 "consequence beside the control").
     - *Tables*: mono lowercase column headers (muted 10 px), 34–38 px rows, selected row blue-100.
   - **Save bar** (project pages, `unsaved` only): sticky at the bottom of the content column,
     white card, ~52 px tall, full content width: amber dot · bold `N unsaved changes` · amber
     mono consequence sentence · right *Discard* (secondary) + *Save changes* (primary blue).

### Controls & interactions (shell)
| control | kit | behaviour |
|---|---|---|
| Nav rail items | NavRail | navigate `#/<workspace>`; Settings stays highlighted on every settings page; leave-guard if unsaved |
| Header search `Search settings` `Ctrl K` | Header search → Popover | Ctrl K / click opens a fixture search over field labels; Enter → `#/settings/<slug>?focus=<fieldId>` scrolls to and pulses the field (2 s amber ring); Escape closes |
| `3 need you` chip | Chip | navigate `#/jobs` (shared shell behaviour) |
| `M4 held out` chip | Chip (lock icon) | navigate `#/settings/datasets?focus=held-out` |
| Settings nav item (×16) | SettingsNav item | navigate `#/settings/<slug>`; `aria-current="page"` on the current one; leave-guard if unsaved |
| Amber dot on nav item | DiffDot | computed: page's in-memory values ≠ fixture defaults. **Fix B29:** dots must be computed per page, not follow the open page |
| `Reset page to defaults` | ghost Button → Popover confirm | see `confirm-reset`; disabled with DisabledReason "Nothing differs from default" when the page has no differing value (About, Audit log have none — hide the link on those two, see page sections) |
| Save bar *Discard* | Button | reverts in-memory edits to last saved; toast "Discarded 3 changes" |
| Save bar *Save changes* | primary Button | `saving` → `saved`; disabled with reason when any field on the page is `invalid` ("Fix 1 invalid value first" + scroll-to link) |
| Field-level amber dot + outline | FieldDiff | shown when the field differs from default OR is unsaved; unsaved fields use the solid amber outline, saved-but-differing fields show only the dot before the label |
| Locked control | LockedField (lock glyph, grey fill, pale toggle) | not editable; hover/focus InfoTip "Enforced by the tool: <rule>". Never shows the amber diff dot |
| `(i)` next to labels | InfoTip | Popover with the one-paragraph explanation (P9) |
| Keyboard | — | `Ctrl K` search (shown in the header and in Keyboard & behaviour) · `Esc` closes any popover/modal. No save shortcut is drawn or listed in frame 16 — do not invent one |

### Fixtures (shell)
```ts
type Scope = 'project' | 'personal'
interface SettingsPageMeta { slug: string; title: string; group: 'Data'|'Analysis'|'Workspaces'|'Files'|'Record'|'Interface'; scope: Scope; lede: string }
interface SettingsStore {              // in-memory, per page
  defaults: Record<string, unknown>    // fixture defaults (spec §9)
  saved: Record<string, unknown>       // what the frames show as current (may differ from defaults)
  draft: Record<string, unknown>       // edits not yet saved
}
interface PendingChange { fieldId: string; from: unknown; to: unknown; consequence: string }  // save-bar sentence
```
The consequence sentence is looked up per field from a fixture table (examples in each page's
Copy); a generic fallback is `"<label> <from> → <to> · applies to new runs"`.

Shared canon used by Settings (lives in the shared canon fixture, not here): recordings (5),
channels (61, CHn_XY names), classes (1–4, 9), verdicts (core five), families (F-03 etc.),
models (`cnn_windows_v2 · manual`, `rf_windows_v1 · manual`, `cnn_cluster_v1`), templates (14),
window sets (`ws_M2aug_3ch_600s`), jobs (`j-0212`, `j-0214`, `j-0217`, `j-0209`), actor
`this installation`, local limits (Analyse 20 min · Discovery 20 min · Models 2 h), cluster `hpc-1`.

### Copy (shell)
- Header: `Settings` · `<Page>` · `project` / `personal`; search `Search settings` `Ctrl K`.
- Nav scope headers: `PROJECT · recorded with runs`, `PERSONAL · this browser`; group labels
  `Data`, `Analysis`, `Workspaces`, `Files`, `Record`, `Interface`; legend `differs from default`.
- Title badges: `project · recorded with runs`, `personal · this browser`.
- `Reset page to defaults`; save bar `N unsaved change(s)` · `Discard` · `Save changes`.

### Frame ⟷ spec conflicts (shell)
- Rail dots: the frames draw the same 7 dots on every page, and Datasets / Channels / Vocabulary /
  Blocks / Export show a save bar but **no** dot on their own item (B29 "differs dots follow the
  open page"). Recommend: compute dots per page from the store; the open page shows its dot like
  any other.
- Pages 04, 06, 08, 09, 10 show an amber-outlined field but no save bar. Recommend reading these
  as "saved value differs from default" (dot + outline) and reserving the save bar for unsaved
  edits; `?state=unsaved` reproduces the save-bar look on any page.
- The header in the frames has no "demo data" chip; the kit adds it — keep it.

### Fog (shell)
- F1. Project settings "are snapshotted into every export and backup" (§9) — no core API reads or
  writes a project settings file today; all saves are in-memory + toast "not wired yet:
  PUT /api/settings/<slug>".
- F2. Search index across settings is a UI-only fixture; no spec for ranking.

### Demo-state convention (all project pages)
Each project frame that shows a save bar is a **scripted edit on top of the canonical saved
values**, not the canonical values themselves. A clean load shows the saved canon; `?state=unsaved`
seeds exactly the frame's draft and its save-bar sentence. This keeps cross-page canon consistent
(e.g. Analysis defaults reads the recording noise floor as 0.10 mV; the audit log already records
the 31.1–31.5 h exclusion as saved on 13 Sep). Each page section lists its seeded draft.

---

## settings.datasets

### Route & states
| state | frame | reached by |
|---|---|---|
| `clean` | 01 (minus the three amber fields and the save bar) | `#/settings/datasets`; row M2_aug fs1 selected by default |
| `unsaved` | 01 | edit a metadata field; `?state=unsaved` seeds: species `P. ostreatus` → `Pleurotus ostreatus`, start time `2025-08-02 13:00` → `2025-08-02 14:00`, noise floor `0.08` → `0.10` mV; sentence `noise floor 0.08 → 0.10 mV marks 4 runs on M2_aug fs1 stale` |
| `selected:<rec>` | 01 (row highlight) | click a table row; `?rec=M2_aug_fs2` / `M3_jul` / `L_LM_Jul26_J` / `M4_aug` |
| `selected:M4_aug` (read-only) | derived from 01 | click the M4_aug row: metadata card fields read-only, DisabledReason banner inside the card `M4_aug is held out · locked — metadata is read-only while the lock is on` |
| `selected:L_LM_Jul26_J` (inferred fs) | derived | sampling-rate field editable with amber `inferred` badge; species empty placeholder `not set`; start `2026-07-26` time `—` |
| `import` modal | 01b | click *Import a recording…*; `?modal=import` |
| `import:reading` → `import:checked` | 01b | type/paste a path and press Enter or blur: 400 ms "reading header…" then fields fill |
| `import:check-failed` | derived from 01b | path is an already-registered file or the held-out file; `?modal=import&path=M4_aug_concat.mat` |
| `import:importing` → `import:done` | derived | click *Import* when no check fails |
| `unlock-confirm` modal | derived (spec §9.1, D6) | click the held-out Toggle while on; `?modal=unlock` |
| `unlocked` | derived | after a confirmed unlock; `?state=unlocked` |

### Regions (1440×900, content column ≈ 1080 px)
1. Title row: `Datasets` + `project · recorded with runs` badge · right `Reset page to defaults`.
   Lede: `The recording registry. Metadata travels with every export.`
2. **Recordings** card (full width, ≈ 30 % of height). Title `Recordings`, sub `5 recordings · 61
   channels`; right secondary button with file-plus icon `Import a recording…`. Table (9 cols,
   widths ≈ name 14 % · file 17 % · sampling rate 12 % · ch 4 % · duration 7 % · start 13 % ·
   species 10 % · linked 8 % · status 11 %), 5 rows ≈ 36 px, selected row blue-100:
   | name | file | sampling rate | ch | duration | start | species | linked | status |
   |---|---|---|---|---|---|---|---|---|
   | M2_aug fs1 | M2_aug_concat_fs1.mat | 1 Hz `read` | 16 | 721 h | 2025-08-02 14:00 | P. ostreatus | 🔗 fs2 | `in use` |
   | M2_aug fs2 | M2_aug_concat_fs2.mat | 2 Hz `read` | 16 | 721 h | 2025-08-02 14:00 | P. ostreatus | 🔗 fs1 | `in use` |
   | M3_jul | M3_jul_concat.mat | 1 Hz `read` | 8 | 280 h | 2025-07-10 09:30 | P. ostreatus | — | `in use` |
   | L_LM_Jul26_J | L_LM_Jul26_J.csv | 10 Hz `inferred` | 5 | 22.4 h | 2026-07-26 — | not set | — | `provisional` |
   | M4_aug | M4_aug_concat.mat | 1 Hz `read` | 16 | 300 h | 2025-08-20 11:00 | P. ostreatus | — | `held out · locked` |
   Badges: `read` green-100, `inferred` amber-100, `in use` green, `provisional` amber,
   `held out · locked` grey. Name column bold mono; file mono.
3. **`<name>` metadata** card (≈ 22 % height). Title = recording name bold + muted `metadata ·
   travels with every export`. 4-column field grid × 3 rows (label above input, 11 px mono label):
   - row 1: `display name` [M2_aug fs1] · `species` [Pleurotus ostreatus] · `substrate` [hardwood
     sawdust block] · `electrode config` [sub-dermal pairs · 12 mm]
   - row 2: `start time` [2025-08-02 14:00] · `time zone` Select [Europe/London] · `sampling rate`
     LockedField [🔒 1 Hz · read from file header] · `noise floor (i)` Number [0.10] unit `mV`
   - row 3: `temperature` [21.4 ± 0.8] unit `°C` · `humidity` [88 – 94] unit `% RH` · `linked
     recordings` Chip `🔗 M2_aug fs2` + amber mono caption `never split train/test` · `notes`
     placeholder `timed events → Channels & events`
   In `unsaved`, `species`, `start time`, `noise floor` show the amber dot before the label and
   an amber outline.
4. **Held-out recording** card (≈ 10 % height). Title with lock icon `Held-out recording`; right
   Chip blue `on · M4_aug held out`. One form row: label `hold out a recording (i)` + sub
   `kept from every workspace` · Toggle (on, green) · Select [M4_aug] (≈ 150 px) · right muted
   caption `when on, every workspace refuses it · turning off needs the name typed · logged`.
5. Save bar (`unsaved`): `3 unsaved changes` · `noise floor 0.08 → 0.10 mV marks 4 runs on
   M2_aug fs1 stale` · Discard · Save changes.

**Import modal (01b)** — Modal ≈ 810 × 750 px centred (56 % × 83 %), backdrop dims the page and
covers the save bar. Header `Import a recording` + amber Badge `dry run · nothing written yet` +
close ×. Five numbered sub-cards (grey `--grey-50` ground, 8 px radius), each titled
`<n>  <Title>  <muted caption>`:
1. `File` — `read, not copied · stays where it is`: `path` Text (≈ 65 %) [D:/recordings/M5_sep_concat_fs1.mat] ·
   `format` read-only Text [MATLAB v7.3 · 16 variables].
2. `Sampling rate` — `read from the file header when present; entered rates are marked inferred`:
   `fs` Text [1 Hz] with green `read` badge inside · `samples per channel` read-only [1,080,000] ·
   `duration` read-only [300 h] (three equal columns).
3. `Channel map` — `16 variables → 16 channels · names follow CHn_XY`: table `variable` · `channel`
   (editable Text) · `electrode · position` · `shared ground` (Select) · `include` (Checkbox,
   checked). Rows: `ch01 CH1_A1 A1 tip · 0 mm —` · `ch02 CH2_A1 A1 base · 12 mm —` ·
   `ch03 CH3_A2 A2 tip · 0 mm CH4_A2`; expander `… 13 more`.
4. `Start time and link` — `a linked recording is the same signal at another rate`: `start`
   [2025-09-01 10:00] · `time zone` Select [Europe/London] · `link to existing` Select [none].
5. `Checks` — `must pass before Import`: icon rows —
   ✓ `samples = duration × fs for every channel (1,080,000 = 300 h × 1 Hz)` ·
   ✓ `channel names unique and not already used by this recording` ·
   ✓ `not the held-out recording · M4_aug is locked in this page` ·
   ⚠ `species not set · allowed, marks the recording provisional`.
Footer: mono muted `will create 1 recording · 16 channels · 16 .npy files · 8.2 GB on disk · no
runs affected` · `Cancel` · `Import` (primary).

### Controls & interactions
| control | kit | behaviour / validation |
|---|---|---|
| `Import a recording…` | Button | opens import Modal (`?modal=import`) |
| Recording row | Table (single-select) | selects; metadata card re-binds; `?rec=` updated |
| `linked` cell 🔗 fs2 | link Chip | selects the linked recording's row |
| `display name` | Field Text | required; unique across recordings (case-insensitive) → "Another recording is already called M3_jul"; ≤ 40 chars. Consequence: `display name changes in every page and in new exports; existing exports keep the old name` |
| `species` | Field Text | optional; clearing it → status becomes `provisional`, consequence `species cleared · M2_aug fs1 becomes provisional` |
| `substrate`, `electrode config` | Field Text | optional, ≤ 80 chars; consequence `travels with new exports` |
| `start time` | Field Text (datetime) | `YYYY-MM-DD HH:MM` else "Use YYYY-MM-DD HH:MM"; consequence `clock-time readouts shift by <Δ>; hours since start are unchanged` |
| `time zone` | Select | options Europe/London · UTC · Europe/Berlin · America/New_York; consequence as start time |
| `sampling rate` | LockedField when `read`; Number (Hz, > 0) when `inferred` | locked tooltip `read from the file header — cannot be edited`; for L_LM_Jul26_J editing gives consequence `fs 10 → <x> Hz re-times every span on L_LM_Jul26_J · <n> runs marked stale` and the badge stays `inferred` |
| `noise floor (i)` | Field Number + unit mV | > 0 and ≤ 5 mV, 2 dp → "Enter a floor between 0.01 and 5 mV"; InfoTip `Every detector reads the noise floor from here; a channel can override it in Channels & events.` Consequence `noise floor 0.08 → 0.10 mV marks 4 runs on M2_aug fs1 stale` |
| `temperature` / `humidity` | Field Text + unit | free text; pattern hint `21.4 ± 0.8` / `88 – 94`; consequence `travels with new exports` |
| `linked recordings` | Chip list with × + `+ link` Select | Select lists other non-held-out recordings with equal duration (M2_aug fs1 ↔ fs2 only); removing a link: consequence `M2_aug fs1 and fs2 could land on different sides of a split` (amber); M4_aug never offered |
| `notes` | Textarea + link | placeholder link `timed events → Channels & events` navigates `#/settings/channels-events?rec=<rec>` |
| Held-out Toggle (on → off) | Toggle | opens **unlock-confirm Modal**: title `Turn off the held-out lock?`; body `M4_aug becomes selectable in every workspace — Explore, Analyse, Discovery, Models, Review, Library. Evaluation on it is no longer protected. This is written to the audit log.`; Field `Type M4_aug to confirm`; buttons `Cancel` · `Turn off lock` (danger) disabled with DisabledReason `type the recording name exactly` until the text equals the selected recording name (case-sensitive, trimmed). Confirm = immediate write (see conflicts): toggle off, chip → grey `off · no recording held out`, M4_aug status → `available`, header chip `M4 held out` hidden, audit entry `lock · Held-out lock turned off · M4_aug selectable · Datasets · this installation`, Toast `Held-out lock off · logged` |
| Held-out Toggle (off → on) | Toggle | staged as an unsaved change: `M4_aug will be refused in every workspace · logged`; on save → audit `Held-out lock turned on · M4_aug held out` |
| Held-out Select | Select | disabled while the lock is on, DisabledReason `turn the lock off to choose another recording`; when off, lists the 5 recordings |
| `(i)` on hold out | InfoTip | `A held-out recording is kept from every workspace so evaluation on it stays honest (D6).` |
| Import · `path` | Field Text | Enter/blur → 400 ms `reading header…`. Rules: extension `.mat` `.csv` `.npy` `.h5` else "Unsupported format"; fixture lookup: `D:/recordings/M5_sep_concat_fs1.mat` → frame values; `D:/recordings/M3_jul_concat.mat` → check fails `already registered as M3_jul`; any `…/M4_aug_concat.mat` → check fails `M4_aug is held out · locked`; `…/*.csv` without header → fs empty, required; unknown → "File not found (demo: try D:/recordings/M5_sep_concat_fs1.mat)" |
| Import · `fs` | Field Text/Number | > 0; typing a value replaces `read` with `inferred` (amber) and caption stays; duration and check 1 recompute (`samples / fs / 3600`) |
| Import · channel name cells | Field Text | unique within the map → "Duplicate channel name CH3_A2"; warn (not block) if not matching `CH<n>_<A-Z><n>` or `CH<n>` |
| Import · shared ground | Select | options `—` + other channel names; symmetric (setting CH3_A2 → CH4_A2 also sets CH4_A2 → CH3_A2) |
| Import · include | Checkbox | ≥ 1 included else check fails `no channel included`; footer counts update |
| Import · `… 13 more` | disclosure | expands to all 16 rows (`ch04 CH4_A2 A2 base · 12 mm CH3_A2`, …, `ch16 CH16_D2`) |
| Import · `start`, `time zone` | Field Text / Select | datetime rule as above |
| Import · `link to existing` | Select | `none` + non-held-out recordings; linking to a recording whose duration or channel count differs fails check `a linked recording must be the same signal: 300 h vs 721 h` |
| Import · `Checks` | CheckList | live; ✓ green, ⚠ amber (allowed), ✕ red (blocks) |
| Import · `Cancel` / × / Esc | Button | closes; nothing to confirm (dry run) |
| Import · `Import` | primary Button | disabled with DisabledReason `<n> checks fail` when any ✕; else `importing` ProgressBar `writing 16 .npy files… 7 / 16` (~2 s) → modal closes, new row `M5_sep` with `new` Badge and status `provisional` (in memory only), Toast `Imported M5_sep (demo) · not wired yet: POST /api/recordings/import` |

### Plots
None.

### Fixtures
```ts
interface Recording {                       // SHARED canon (recordings)
  id: 'M2_aug_fs1'|'M2_aug_fs2'|'M3_jul'|'L_LM_Jul26_J'|'M4_aug'
  name: string; file: string; fs_hz: number; fs_source: 'read'|'inferred'
  n_channels: number; duration_h: number; start: string | null; time_zone: string
  species: string | null; substrate: string | null; electrode_config: string | null
  noise_floor_mV: number; temperature: string | null; humidity: string | null
  linked: string[]; notes: string
  status: 'in use'|'provisional'|'available'|'held out · locked'
}
interface HeldOutLock { on: boolean; recording: 'M4_aug' }   // SHARED (header chip, Models Launch, every picker)
interface ImportDryRun {
  path: string; format: string; fs_hz: number | null; fs_source: 'read'|'inferred'
  samples_per_channel: number; duration_h: number
  channel_map: { variable: string; channel: string; electrode_position: string; shared_ground: string | null; include: boolean }[]
  start: string; time_zone: string; link_to: string | null
  checks: { text: string; level: 'ok'|'warn'|'fail' }[]
}
```
Canon values (§0): the five recordings above; 61 channels; M2_aug/M4_aug 16 ch with CHn_XY names,
M3_jul 8 ch, L_LM_Jul26_J 5 ch; M2_aug fs1 saved noise floor 0.10 mV (0.08 only in the seeded
unsaved state). Metadata for recordings other than M2_aug fs1 is not drawn: fill M2_aug fs2 as a
copy of fs1 with `sampling rate 2 Hz`; M3_jul `species Pleurotus ostreatus`, noise floor 0.10 mV;
L_LM_Jul26_J species/substrate/electrode `not set`; M4_aug as M2_aug fs1 with its own start.
Dry-run fixture: `M5_sep_concat_fs1.mat` channel map with the 16 CHn_XY names, pairs
(CH1_A1,CH2_A1 none; CH3_A2↔CH4_A2 as in Channels).

### Copy
`The recording registry. Metadata travels with every export.` · `Recordings` `5 recordings · 61
channels` · `Import a recording…` · `metadata · travels with every export` · `1 Hz · read from file
header` · `never split train/test` · `timed events → Channels & events` · `Held-out recording` ·
`hold out a recording` · `kept from every workspace` · `on · M4_aug held out` · `when on, every
workspace refuses it · turning off needs the name typed · logged`. Import: `Import a recording` ·
`dry run · nothing written yet` · the five sub-card titles and captions and four check lines as in
Regions · `will create 1 recording · 16 channels · 16 .npy files · 8.2 GB on disk · no runs
affected` · `Cancel` · `Import`.

### Live vs demo
Demo only. `GET /api/recordings` (webui/client/src/api.ts `getRecordings`) returns `source_file,
fs, n_samples, duration_h, n_channels, held_out, held_out_reason` for the real worktree database;
it has no species/start/metadata/status fields and may list other file names. Do **not** render it
here — canon wins on screen (§0 "No other recording names"). The header `M4 held out` chip already
exists in `shell/Header.tsx`; bind it to the shared `HeldOutLock` fixture so `unlocked` hides it.

### Frame ⟷ spec conflicts
- **Lock default.** §9.1 text says the lock "is **off** with M4_aug selectable"; §0, D6, B27 and
  frame 01 say **on**, M4_aug `held out · locked`. §0 wins → on.
- **Unlock commit.** §9 says project settings write on save; D6 says unlocking needs the name
  typed and is logged. Recommend the typed-name modal *is* the commit (immediate, logged), so the
  save bar's Discard can never silently undo a logged act. Turning the lock **on** goes through
  the save bar.
- **Dirty fields.** Frame 01 shows 3 unsaved changes while the rail item has no dot (B29). Follow
  the shell rule.

### Fog
- F3. Import footer `8.2 GB on disk` does not reconcile: 16 × 1,080,000 float64 samples ≈ 138 MB.
  Recommend computing `channels × samples × 8 B` (→ `138 MB`) rather than copying the frame.
- F4. `M5_sep` is not a canon recording (§0 allows five). Recommend the imported row lives in memory
  only, tagged `new`, and disappears on reload.
- F5. The core has no recording-import API, no species/substrate/temperature fields and no time
  zone on recordings; "4 runs marked stale" has no data source (fixture count).
- F6. Whether metadata of the held-out recording may be edited in Settings is unspecified
  (Settings is not a workspace). Recommend read-only while locked.

---

## settings.channels-events

### Route & states
| state | frame | reached by |
|---|---|---|
| `clean` | 02 without amber outlines / save bar | `#/settings/channels-events` (recording tab M2_aug fs1) |
| `unsaved` | 02 | `?state=unsaved` seeds: CH6_B1 gain `1.00` → `0.98`; event 31.1–31.5 h effect `show on plots` → `exclude span`; sentence `excluding 31.1–31.5 h on all channels marks 3 runs on M2_aug fs1 stale` |
| `rec:<id>` | 02 Seg | click a recording segment; `?rec=M3_jul` |
| `rec:M4_aug` locked | derived | click `M4_aug`: tables read-only, banner `M4_aug is held out · locked — channels and events are read-only` |
| `rows:all` | derived | click `8 more channels`; `?rows=all` (toggles to `show 8 channels`) |
| `add-event` | derived | click *Add event*; `?modal=add-event` — inline new row at the top of the table in edit mode |
| `add-kind` | derived | click `+ kind` → Popover with name Text + colour swatch Select |
| `event-selected` | derived | click a timeline marker or table row: both highlight (blue ring on the marker, blue-100 row) |

### Regions
1. Title `Channels & events` + project badge · `Reset page to defaults`. Lede `Per-channel
   metadata and timed events. Excluded spans are skipped by every new run.`
2. **Channels** card (≈ 42 % height). Title `Channels`; right Seg (5 segments) `M2_aug fs1` ·
   `M2_aug fs2` · `M3_jul` · `L_LM_Jul26_J` · `M4_aug`. Table columns: `ch` (bold mono) · `name` ·
   `electrode · position` · `gain` (inline Number with unit `mV / u`) · `shared ground` (amber
   link Chip or `—`) · `status` (Badge `ok` green / `bad from 40.1 h` red) · `excluded spans` ·
   `noise floor` (muted `recording` or a value). 8 rows, zebra grey-50:
   `CH1_A1 A1 tip A1 · 0 mm 1.00 — ok 1 · all channels recording` ·
   `CH2_A1 A1 base A1 · 12 mm 1.00 — ok 2 · 28.9–29.1 h + all recording` ·
   `CH3_A2 A2 tip A2 · 0 mm 1.00 CH4_A2 ok 1 · all channels recording` ·
   `CH4_A2 A2 base A2 · 12 mm 1.00 CH3_A2 ok 1 · all channels recording` ·
   `CH5_B1 B1 tip B1 · 0 mm 1.00 — ok 1 · all channels recording` ·
   `CH6_B1 B1 base B1 · 12 mm 0.98 — ok 1 · all channels recording` (gain amber outline in unsaved) ·
   `CH7_B2 B2 tip B2 · 0 mm 1.00 — bad from 40.1 h 2 · 40.1 h → end + all recording` ·
   `CH8_B2 B2 base B2 · 12 mm 1.00 — ok 1 · all channels recording`.
   Footer row: left blue disclosure `⌄ 8 more channels`; right muted `(i) shared-ground pairs drive
   the Library's double-count warning`.
3. **Event log** card (≈ 36 % height). Title `Event log` + muted `M2_aug fs1 · 4 events`; right
   secondary `+ Add event`. BandStrip timeline (full width, ≈ 40 px): axis ticks `0 h 10 h 20 h
   30 h 40 h`, caption top-right `shaded = excluded from analysis`; markers coloured by kind; shaded
   bands for excluded spans (grey band at 28.9–29.1, amber band at 31.1–31.5, red band 40.1 → end).
   Table: `time` · `kind` (dot + name) · `channels` · `effect` (Select) · `note` · `added`:
   `12.5 h ● watering all [show on plots] 5 ml water added to substrate 12 Sep` ·
   `28.9 – 29.1 h ● unknown CH2_A1 [exclude span] amplitude excursion, no lab-book entry 12 Sep` ·
   `31.1 – 31.5 h ● mechanical all [exclude span] chamber door opened 13 Sep` (amber outline in unsaved) ·
   `40.1 h → end ● electrode CH7_B2 [exclude · mark channel bad] electrode detached 14 Sep`.
   Kinds legend row: `kinds` + Chips `● watering` (blue) `● mechanical` (orange) `● unknown` (grey)
   `● electrode` (red) `● light` (yellow) `● stimulus` (purple) + outline chip `+ kind`.
4. Save bar (`unsaved`): `2 unsaved changes` · `excluding 31.1–31.5 h on all channels marks 3 runs
   on M2_aug fs1 stale`.

### Controls & interactions
| control | kit | behaviour / validation |
|---|---|---|
| Recording Seg | Seg | switches both cards to that recording; M4_aug read-only (see states); L_LM/M3 show `CH1`…`CHn` names, no electrode letters |
| `gain` | Field Number + unit | > 0 and ≤ 100, 2 dp → "Gain must be a positive number"; consequence `gain on CH6_B1 1.00 → 0.98 rescales mV on CH6_B1 · <n> runs marked stale` |
| `shared ground` chip | link Chip + Select on click | Select `—` + other channels of the recording; symmetric pair update; consequence `CH3_A2 and CH4_A2 count once in Library recurrence` |
| `status` | Badge + Popover on click | Popover: Seg `ok` / `bad from` + time Field (`h`, 0 ≤ t ≤ duration). Setting `bad from` adds a linked `electrode` event row |
| `excluded spans` cell | text + Popover | lists the spans affecting that channel, each linking to its event row |
| `noise floor` | Field Number (placeholder `recording`) | empty = recording's floor; value must be > 0 ≤ 5 mV; consequence `CH4_A2 overrides the recording floor · <n> runs marked stale` |
| `8 more channels` | disclosure | expands CH9_C1 … CH16_D2 (all `ok`, `1 · all channels`, pairs none) |
| `(i)` shared-ground | InfoTip | `Channels on one ground see the same events; the Library warns before counting them twice.` |
| `+ Add event` | Button | inserts an edit row: `time` Field (`12.5 h` or `28.9 – 29.1 h` or `40.1 h → end`; parse h; start < end; within 0–duration → "Time must be inside 0–721 h"), `kind` Select, `channels` multi-Select (`all` or channel list), `effect` Select, `note` Text (required, ≤ 120), `added` auto `16 Sep`; Save row / Cancel row icons. Staged in the save bar |
| Timeline markers / bands | BandStrip | hover tooltip `31.1 – 31.5 h · mechanical · all · exclude span`; click selects the row |
| `effect` Select | Select | `show on plots` · `exclude span` · `exclude and mark channel bad`; consequence for exclude: `excluding <span> on <channels> marks <n> runs on <rec> stale`; for mark bad: also sets channel status `bad from <t>` |
| Row delete (hover ×) | IconButton | staged removal; consequence `removing the exclusion lets new runs read <span> again · <n> runs marked stale` |
| `+ kind` | Chip → Popover | name Text (unique, lowercase, ≤ 20 → "Kind already exists") + colour Select (non-semantic swatches); staged |

### Plots
- **Event timeline** (BandStrip): x = hours since recording start, domain **0 → recording
  duration** (721 h for M2_aug fs1; see conflict), ticks in `h`; point markers (8 px circles, kind
  colour) at event start; excluded spans as translucent bands (kind colour at 20 % or red for
  mark-bad), extending to the end for `→ end`. No y axis. Fixture: `events[rec]`.

### Fixtures
```ts
interface ChannelMeta {                    // SHARED canon (channels) + settings fields
  recording: string; ch: string; name: string; electrode: string; position_mm: number
  gain_mV_per_unit: number; shared_ground: string | null
  status: { kind: 'ok' } | { kind: 'bad_from'; t_h: number }
  noise_floor_mV: number | null            // null = recording's
}
type EventEffect = 'show on plots' | 'exclude span' | 'exclude and mark channel bad'
interface TimedEvent { id: string; recording: string; t0_h: number; t1_h: number | 'end' | null
  kind: string; channels: 'all' | string[]; effect: EventEffect; note: string; added: string }
interface EventKind { name: string; colour: string; builtin: boolean }
```
Canon: M2_aug fs1 channels CH1_A1…CH16_D2 (electrode letter pairs A1…D2; odd = tip 0 mm, even =
base 12 mm); shared ground pairs CH3_A2↔CH4_A2 only; CH7_B2 bad from 40.1 h; CH6_B1 gain 1.00 saved
(0.98 seeded). Four events as in Regions. Kinds: watering, mechanical, light, temperature,
electrode, stimulus, unknown (spec lists 7; the frame's legend omits `temperature` — include it).
Other recordings: no events (EmptyState `No events on M3_jul · Add event`).

### Copy
`Per-channel metadata and timed events. Excluded spans are skipped by every new run.` ·
`Channels` · `8 more channels` · `shared-ground pairs drive the Library's double-count warning` ·
`Event log` `M2_aug fs1 · 4 events` · `Add event` · `shaded = excluded from analysis` · event notes
as above · `kinds` · `+ kind` · `mV / u`.

### Frame ⟷ spec conflicts
- Timeline axis in 02 runs 0–45 h, but M2_aug fs1 is **721 h** (§0). Recommend the full 0–721 h
  domain with a brush/zoom (or ticks every 100 h and the four markers clustered near the start);
  do not draw a 45 h recording.
- The 31.1–31.5 h exclusion is an unsaved change in 02 but a saved audit entry on 13 Sep (frame 13).
  Canon = saved; 02's look is the `?state=unsaved` seed (effect changed from `show on plots`).
- Spec kinds include `temperature`; the frame legend omits it. Spec wins.
- Spec effect wording `exclude and mark channel bad`; frame Select shows `exclude · mark channel
  bad`. Use the frame's short label in the Select, spec wording in tooltips.

### Fog
- F7. Per-channel gain, electrode position and shared-ground data do not exist in the core schema
  (fixture only). "3 runs marked stale" has no data source.
- F8. Channel status `bad from t` vs an event with effect `exclude and mark channel bad` are two
  ways to express one fact; spec does not say which is the source of truth. Recommend the event is
  the source and the status cell is derived.

---

## settings.vocabulary

### Route & states
| state | frame | reached by |
|---|---|---|
| `clean` | 03 without the rename row and save bar | `#/settings/vocabulary` |
| `rename:<verdict>` + `unsaved` | 03 | click `rename` on a verdict row; `?rename=interesting&to=noteworthy` seeds the frame: inline row under the table `rename interesting → [noteworthy]` + amber warning `rewrites 3,424 rows across both stores atomically · existing exports keep the old name`; interesting row tinted amber-100; save bar `1 unsaved change` `rename interesting → noteworthy rewrites 3,424 rows in both stores` |
| `rekey:<verdict>` | derived | click `rekey`: the key cell becomes a capture box `press a key…` |
| `add-verdict` | derived | click `+ Add a verdict · needs a role`: inline row (name, key, colour, role Select required) |
| `add-class` | derived | click `+ Add class`; `?modal=add-class` inline row |
| `rename-class:<key>` | derived | click class `rename` |
| `add-tag` | derived | click `+ Add tag` inline row |
| `merge-tag:<tag>` | derived | click `merge` → Popover `Merge <tag> into [Select]` |

### Regions
1. Title `Vocabulary` + project badge · Reset. Lede `One vocabulary across annotations and
   adjudications — no translation table, so none can drift.`
2. **Verdicts** card (≈ 33 % height). Title `Verdicts` + muted `keys, roles, counts in both
   stores`; right grey Chip with lock `core five · rename or rekey, never remove`. Table: `verdict`
   (bold mono) · `key` (KeyCap box) · `colour` (swatch) · `role` · `in annotations` · `in
   adjudications` · actions `rename` `rekey` (blue links) + lock glyph:
   `seed S blue exemplar · promotes to Library 412 96` ·
   `interesting I green accept 1,284 2,140` ·
   `not_interesting N grey reject 3,901 5,772` ·
   `artifact A red flag · kept out of training 211 318` ·
   `unsure U orange defer 88 144`.
   Under it the rename row (in `rename`) and a blue link `+ Add a verdict · needs a role`.
3. **Classes** card (≈ 25 %). Title `Classes` + muted `optional class keys in Review · classes for
   multi-class models`; right `+ Add class`. Table `key` (box) · `class` (bold) · `colour` · 
   `informative` (Toggle + label) · `implies` (Select; LockedField `🔒 interesting` when informative)
   · `labels` · `used by models` (blue link) · `rename`:
   `1 spike-train #5856D6 on informative 🔒interesting 410 cnn_cluster_v1` ·
   `2 burst #E85AAD on informative 🔒interesting 380 cnn_cluster_v1` ·
   `3 slow-drift #30B0C7 on informative 🔒interesting 330 cnn_cluster_v1` ·
   `4 plateau #A2845E on informative 🔒interesting 250 cnn_cluster_v1` ·
   `9 electrode artifact red off non-informative [artifact] 38 —`.
   Footnote `(i) an informative class implies interesting; a non-informative class names the verdict
   it implies · renaming a class rewrites its labels, models keep their own snapshot`.
4. **Morphology tags** card (≈ 30 %). Title `Morphology tags` + muted `many-to-many on library
   entries, never a primary key`; right `+ Add tag`. Table `tag` (bold mono) · `definition` ·
   `example` (sparkline ≈ 60×24, grey box) · `families` · `members` · `aliases` (grey chip) ·
   `rename` `merge`:
   `spike-train | regular train of sharp drops, 3 or more events | 3 | 412 | spike-train-short (merged)` ·
   `biphasic | rise then fall of similar depth within about 2 s | 3 | 210 | —` ·
   `sharkfin | single steep fall then slower recovery, within about 30 s | 2 | 112 | —` ·
   `slow-drift | baseline movement over more than 10 min, no events | 4 | 188 | —` ·
   `burst | 3 or more fast oscillations within 5 s | 2 | 77 | —` ·
   `plateau | sustained level shift, then return | 1 | 26 | —`.
5. Save bar (`unsaved`).

### Controls & interactions
| control | kit | behaviour / validation |
|---|---|---|
| verdict `rename` | link → inline row | Text; rules: lowercase `[a-z_]{2,24}`, unique across verdicts and classes → "`artifact` is already a verdict"; the warning line computes rows = annotations + adjudications (`1,284 + 2,140 = 3,424`); Enter stages; Esc cancels |
| verdict `rekey` | link → KeyCapture | single key A–Z; must not collide with another verdict key, a class key (1–9) or a Keyboard & behaviour binding (Space, E, R, `\`) → "`E` opens in Explore (Keyboard & behaviour)"; consequence `interesting key I → K · Review keys change for every queue` |
| lock glyph / no delete | LockedField | the core five have no delete; tooltip `Review keys, seed promotion and training exclusions depend on the core five` |
| `+ Add a verdict · needs a role` | link → inline row | name (rules above), key (capture), colour (swatch Select, non-semantic warn), role Select `accept` · `reject` · `flag` · `defer` (required → "A new verdict needs a role"); new verdicts get a delete × until saved |
| class `informative` Toggle | Toggle | on → `implies` locks to `interesting`; off → `implies` becomes a Select of verdicts (default `artifact`); consequence `plateau no longer implies interesting · 250 labels keep their verdict` |
| class `implies` Select | Select | enabled only when non-informative |
| class `rename` | link → inline Text | unique; consequence `rename burst → bursting rewrites 380 labels · models keep their own class-map snapshot` |
| class `used by models` link | link | navigate `#/models/registry?model=cnn_cluster_v1` |
| `+ Add class` | Button → inline row | key Select of unused 5–8; name; colour; informative Toggle; `labels 0` |
| tag `rename` | link → inline Text | unique; consequence `rename sharkfin → shark-fin updates 112 members · the old name is kept as an alias` |
| tag `merge` | link → Popover | `Merge sharkfin into [Select tag]` + preview `112 members move · alias sharkfin kept`; *Merge* stages |
| tag definition cell | inline Textarea on click | required, ≤ 140 chars |
| `+ Add tag` | Button → inline row | name + definition required; example blank `no example yet` |
| example sparkline | Trace (mini) | hover tooltip `example from F-03 · E-0102` (sharkfin) |

### Plots
- **Tag example sparklines** (6): mini Trace, ~60×24 px, no axes, detrended mV on a per-sparkline
  scale is acceptable for a glyph, but label the tooltip `mV, not normalised`; fixture synthetic
  shapes per tag (spike-train = 5 sharp drops; biphasic = up then down; sharkfin = steep fall then
  slow recovery; slow-drift = smooth arc; burst = 4 fast oscillations; plateau = step up then back).

### Fixtures
```ts
interface Verdict { name: 'seed'|'interesting'|'not_interesting'|'artifact'|'unsure'|string; key: string
  colour: string; role: string; core: boolean; n_annotations: number; n_adjudications: number }  // SHARED
interface ClassDef { key: 1|2|3|4|9|number; name: string; colour: string; informative: boolean
  implies: string; n_labels: number; used_by_models: string[] }                                 // SHARED
interface MorphTag { name: string; definition: string; example: number[]; n_families: number
  n_members: number; aliases: string[] }                                                        // SHARED (Library)
```
Canon (§0): classes `1 spike-train #5856D6 · 2 burst #E85AAD · 3 slow-drift #30B0C7 · 4 plateau
#A2845E · 9 electrode artifact (red)`; verdict counts as in frame; model `cnn_cluster_v1`.

### Copy
Lede and card titles/captions above; `core five · rename or rekey, never remove`; `rename`,
`rekey`, `merge`; `+ Add a verdict · needs a role`; `Add class`; `Add tag`; rename warning line;
classes footnote.

### Frame ⟷ spec conflicts
- The sharkfin example sparkline in 03 is a symmetric hump, not the "steep fall then slower
  recovery" its definition gives (and F-03's shape). Draw to the definition.
- Classes "used by models" lists only `cnn_cluster_v1`; §0 also has `cnn_windows_v2 · manual`
  (binary). Keep the frame (only the cluster model is multi-class) — note for the Models inventory.

### Fog
- F9. Atomic rename across `annotations` and `adjudications` is a core write that does not exist;
  toast `not wired yet: POST /api/vocabulary/rename`. Counts are fixtures.
- F10. Tag families counts (sharkfin 2 families) vs §0 (sharkfin = F-03, one family). Minor; keep
  frame numbers or set to 1 — Library inventory should decide.

---

## settings.nulls

### Route & states
| state | frame | reached by |
|---|---|---|
| `clean` (differs) | 04 | `#/settings/nulls`; multiple-channel correction `Holm` differs from the spec default `none` → rail dot, field dot |
| `unsaved` | derived (04 shows the amber outline on Training · baseline draws but no save bar) | edit any field; `?state=unsaved` seeds Training · baseline draws `200` → `500`, sentence `Training · baseline 200 → 500 draws · new recipe hash for training templates cnn_windows_v3, cnn_windowset_v1 · estimates ×2.5` |
| `invalid` | derived | draws outside range or α below the smallest reportable p; Save disabled |

### Regions
1. Title `Nulls` + project badge · Reset. Lede `Every result carries a null. Method, count and seed
   travel into the recipe hash; whether a null runs is not a setting.`
2. **Null per analysis kind** card (≈ 45 % height). Title; right grey locked Chip `🔒 always on`.
   Table columns (≈ kind 20 % · used in 13 % · method 20 % Select · draws 9 % Number · seed 12 % Select
   · shown as 20 % muted):
   | analysis kind | used in | method | draws | seed | shown as |
   |---|---|---|---|---|---|
   | Detection chains | Analyse · Discovery | circular shift | 200 | per recipe | null expects · × null |
   | Seed search | Discovery | circular shift of the channel | 200 | per recipe | distances behind the histogram |
   | Interrogation · distributions | Analyse | matched random windows | 200 | per recipe | null histogram · null β |
   | Interrogation · intervals | Analyse | shuffled onsets | 200 | per recipe | null interval distribution |
   | Training · baseline | Models | label shuffle · random forest | 200 | per job | null band · p |
   | Training · full model | Models | label shuffle · full retrain | 5 | per job | shuffle dots |
   | Library groupings | Library | bootstrap resample of members | 100 | per grouping | group stability |
   Footnote `(i) each method is chosen per kind because the thing that must be destroyed differs:
   timing for detection, labels for training, membership for groupings`.
3. **Significance** card (≈ 18 %). Rows: `significance level α (i)` Number [0.01] · caption `with 200
   draws the smallest reportable p is 0.005`; `multiple channels` + sub `correction when a result is
   tested per channel` · Seg `none` `Holm` `Benjamini–Hochberg` (Holm on); `show × null beside
   counts` · Toggle on · caption `Discovery scoreboard, templates, run reports`.
4. **Running nulls** card (≈ 12 %). `reuse null draws while the recipe is unchanged` Toggle on ·
   caption `a changed parameter invalidates the cached draws`; `null draws count toward local
   limits` LockedToggle (pale green + lock) · caption `estimates include them, so a 200× null can
   route a stage to the cluster`.

### Controls & interactions
| control | kit | behaviour / validation |
|---|---|---|
| `always on` chip | LockedChip | InfoTip `Whether a null runs is not a setting (P10).` No toggle exists anywhere on the page |
| method Select (×7) | Select | options per kind (fixture): detection `circular shift` · `phase randomisation` · `block shuffle`; seed search `circular shift of the channel` · `phase randomisation`; distributions `matched random windows` · `random windows`; intervals `shuffled onsets` · `Poisson onsets`; training baseline `label shuffle · random forest`; full model `label shuffle · full retrain`; groupings `bootstrap resample of members` · `jackknife`. Consequence `Detection chains circular shift → phase randomisation · cached null draws for 9 detection templates invalidated` |
| draws Number (×7) | Field Number | integer; 20–10,000 (full model 1–50, warn > 20 `each draw is a full retrain`) → "Draws must be a whole number between 20 and 10,000"; consequence as seeded |
| seed Select (×7) | Select | `per recipe` · `per job` · `per grouping` · `fixed` → reveals Number field (0–2³¹) |
| `significance level α (i)` | Field Number | 0 < α ≤ 0.10 → "α must be between 0 and 0.10"; caption recomputes `with <min draws> draws the smallest reportable p is <1/min draws>`; if α < that p → invalid "α 0.001 is below the smallest reportable p (0.005) — raise draws to at least 1,000"; InfoTip `Results with p below α are marked significant.` |
| `multiple channels` | Seg | consequence `none → Holm · per-channel p values in Discovery shown corrected; runs are not re-run` |
| `show × null beside counts` | Toggle | consequence `× null hidden from Discovery scoreboard, templates and run reports` |
| `reuse null draws…` | Toggle | off → consequence `every run re-draws its null · estimates grow` |
| `null draws count toward local limits` | LockedToggle | tooltip `Enforced: estimates include null draws (Compute & HPC)` + link |

### Plots
None.

### Fixtures
```ts
interface NullSpec { kind: string; used_in: string[]; method: string; method_options: string[]
  draws: number; seed: 'per recipe'|'per job'|'per grouping'|{ fixed: number }; shown_as: string }
interface Significance { alpha: number; correction: 'none'|'Holm'|'Benjamini–Hochberg'; show_x_null: boolean }
interface RunningNulls { reuse_draws: boolean; count_toward_limits: true }
```
Defaults = spec §9.4 table; α 0.01; correction `none` (saved canon `Holm`, so the page differs).
Templates referenced in consequences come from the shared canon (14 templates).

### Copy
Lede, card titles, table text and captions exactly as Regions; `always on`.

### Frame ⟷ spec conflicts
- Spec §9.4 lists the correction default as `none`; frame 04 selects `Holm` with the page marked
  differing. Keep: saved = Holm, default = none.
- Frame outlines Training · baseline draws (200, equal to the default) with no save bar. Treat it
  as the seeded `unsaved` state; the clean load has no outline on that field.

### Fog
- F11. Alternative methods per kind are not specified anywhere; the option lists above are
  placeholders and should be marked as such (InfoTip "placeholder options").
- F12. "Recipe hash" propagation of null settings is a core concern; no API.

---

## settings.analysis-defaults

### Route & states
| state | frame | reached by |
|---|---|---|
| `clean` | 05 without the amber rule outline / save bar | `#/settings/analysis-defaults` |
| `unsaved` | 05 | `?state=unsaved` seeds Bandpass filter band `0.01 – 0.1 Hz` → `0.005 – 0.1 Hz`, sentence `bandpass rule changed · 6 cached stages will re-run next time their chains run` |
| `history:<rule>` | derived | click `history`; `?history=bandpass` — Popover anchored to the link |
| `add-rule` | derived | click `+ Add a rule for a block parameter` → inline row |
| `context:<rec>/<ch>` | derived | change the evaluation context (see controls); `?ctx=M3_jul/CH2` |
| `clear-cache` confirm → `clearing` → `cleared` | derived | click *Clear cache*; `?modal=clear-cache` |
| `invalid` | derived | band upper edge above Nyquist, low ≥ medium, etc. |

### Regions
1. Title `Analysis defaults` + project badge · Reset. Lede `These travel into every recipe hash.`
2. **Matching rule** card (≈ 14 %). Title + muted `what counts as the same event · §4.6`. Rows:
   `reciprocal overlap (IoU) (i)` · Slider (≈ 170 px) · bold value `0.50` · caption `every precision
   and recall figure is a function of this`; `onset tolerance` · Slider · `0.25 × duration`;
   `seed-search exclusion zone` · Select [m / 2] · caption `the trivial-match guard`.
3. **Recommended values** card (≈ 38 %). Title + muted `Settings holds the rule · each block
   evaluates it on its span`; right (i). Table: `block` (bold) · `parameter` (mono) · `rule` (Text ≈
   300 px; locked rows grey with lock) · `evaluated on` (muted) · `on M2_aug fs1 CH4_A2` (green 3 px
   recommended bar + bold value) · `history` (blue link):
   | block | parameter | rule | evaluated on | on M2_aug fs1 CH4_A2 |
   |---|---|---|---|---|
   | Sliding windows | window | 3 × longest expected event | the span | 600 s |
   | Sliding windows | gap | 🔒 ≥ window | — | 600 s |
   | Matrix profile | m | exemplar native length, else 2 × median event | the span | 120 s |
   | Threshold to spans | threshold | model calibration, else null 99th percentile | null run | 0.62 |
   | Noise floor | floor | 🔒 the recording's noise floor (Datasets) | recording | 0.10 mV |
   | Bandpass filter | band | 0.005 – 0.1 Hz | fixed | — |
   | Symbolic encoding | alphabet | 5 symbols · Gaussian breakpoints | fixed | — |
   Link row `+ Add a rule for a block parameter`.
4. **Artifact likelihood** card (≈ 22 %). Title + muted `shown in Review, never blinded`. Rows:
   `cross-channel coherence flag` · `≥ [0.50]` · caption `coherence in the span across channels
   sharing a clock`; `clipping` · `≥ [98] % range`; `step change` · `> [5] × floor within [1] s`;
   `bands` + sub `likelihood from the weighted factors` · `● low < [0.30]  ● medium < [0.60]  ● high`
   (green / amber / red dots).
5. **Step cache** card (≈ 16 %). `write stage artifacts slower than` · Slider · `2.0 s`; `keep stale
   artifacts for` · `[14] days`; `location` · Text [./artifacts/steps] · secondary `🗑 Clear cache` ·
   caption `14.2 GB in use`.
6. Save bar (`unsaved`).

### Controls & interactions
| control | kit | behaviour / validation |
|---|---|---|
| IoU Slider | Slider (0.05–1.00, step 0.05) | value label updates; consequence `IoU 0.50 → 0.60 · precision and recall recomputed for every comparison · scoreboards on 4 Discovery runs marked stale`; InfoTip `Two spans are the same event when their overlap divided by their union is at least this.` |
| onset tolerance Slider | Slider (0–1 × duration, step 0.05) | consequence as IoU |
| exclusion zone Select | Select `m / 4` · `m / 2` · `m` | consequence `seed-search exclusion m/2 → m · seed searches r-0415 marked stale` |
| rule Text (editable rows) | Field Text | free text parsed per parameter: band `a – b Hz` requires 0 < a < b and b ≤ Nyquist of the context recording (0.5 Hz at 1 Hz) → "Upper edge 0.8 Hz is above Nyquist (0.5 Hz) on M2_aug fs1"; alphabet `n symbols · …` with 3 ≤ n ≤ 20; unparseable → amber hint `rule kept as text · the block evaluates it` |
| locked rule | LockedField | tooltip `This rule encodes a guarantee and cannot be changed: gap ≥ window` / `every detector reads the recording's noise floor` + link `Datasets` |
| recommended value cell | RecommendedValue (green bar + value) | read-only; InfoTip `Blocks show this value with the green recommended marker on their page` |
| column header `on M2_aug fs1 CH4_A2` | Select (recording · channel) | changes the evaluated example column from fixture (M3_jul CH2: `window 600 s · m 90 s · threshold 0.58 · floor 0.10 mV`); M4_aug disabled `held out · locked` |
| `history` | link → Popover | list: `0.005 – 0.1 Hz · draft` / `0.01 – 0.1 Hz · saved 12 Sep · this installation` / `0.01 – 0.2 Hz · 2 Sep`; each older row has `restore` (stages it) |
| `+ Add a rule…` | link → inline row | block Select (from Blocks fixture; not-built Model stage disabled `not built · B13`), parameter Select (block params), rule Text required; duplicate block+parameter → "A rule for Matrix profile · m already exists" |
| coherence / clipping / step / within | Field Number | coherence 0–1; clipping 50–100 %; step 1–50 × floor; within 0.1–60 s |
| bands low / medium | Field Number | 0 < low < medium < 1 → "low must be below medium" |
| cache Slider | Slider (0–30 s, step 0.5) | consequence `stages faster than 5.0 s stop writing artifacts · they re-run on every chain run` |
| keep days | Field Number | integer 1–365 |
| location | Field Text | non-empty path; consequence `new stage artifacts are written to <path> · existing ones stay where they are` |
| `Clear cache` | Button → confirm Modal | `Clear the step cache?` body `14.2 GB · cached stages re-run the next time their chains run. Runs, templates and exports are kept.` · Cancel · `Clear cache` (danger) → ProgressBar ~1.5 s → caption `0 GB in use`, Toast `Step cache cleared (demo) · not wired yet: DELETE /api/cache/steps`. Immediate action, not staged |

### Plots
None (the green bar is a marker glyph).

### Fixtures
```ts
interface MatchingRule { iou: number; onset_tolerance_x_duration: number; seed_exclusion: 'm/4'|'m/2'|'m' }
interface RecommendRule { block: string; parameter: string; rule: string; locked: boolean
  evaluated_on: 'the span'|'null run'|'recording'|'fixed'|'—'
  example: Record<string /* "M2_aug_fs1/CH4_A2" */, string | null>
  history: { rule: string; when: string; by: 'this installation' }[] }
interface ArtifactLikelihood { coherence_ge: number; clipping_ge_pct: number; step_gt_x_floor: number; step_within_s: number; band_low_lt: number; band_medium_lt: number }
interface StepCache { min_stage_s: number; keep_stale_days: number; location: string; in_use_gb: number }
```
Shared: block names (Blocks page / chain glyph registry), recordings/channels, noise floor read
from `Recording.noise_floor_mV` (0.10 mV). Step cache location/size shared with Storage & backups
(`./artifacts/steps`, 14.2 GB).

### Copy
Lede, card titles and captions, table text exactly as Regions; `Add a rule for a block parameter`;
`Clear cache`; `14.2 GB in use`.

### Frame ⟷ spec conflicts
- Spec §9.5 matches the frame. The evaluation-context header is plain text in 05; making it a
  Select is a recommendation (a dependent panel), not drawn.

### Fog
- F13. `Sliding windows · window = 3 × longest expected event → 600 s` does not reconcile with
  ~21 s events (F-03); and "longest expected event" has no data source. Keep 600 s (window set
  canon `ws_M2aug_3ch_600s`).
- F14. The saved "from" value of the bandpass rule is not drawn; `0.01 – 0.1 Hz` is invented for
  the seeded edit. "6 cached stages" is a fixture count.
- F15. D4 option (c) needs every block to evaluate a rule string; there is no rule grammar. Parsing
  above is UI-only validation.

---

## settings.compute-hpc

### Route & states
| state | frame | reached by |
|---|---|---|
| `clean` (differs) | 06 | `#/settings/compute-hpc` (page scrolls ≈ 1.7× viewport); Analyse limit field outlined |
| `unsaved` | derived | edit; `?state=unsaved` seeds Analyse limit `10` → `20` min, sentence `Analyse local limit 10 → 20 min · 2 stages in saved chains now run locally instead of offering Create SLURM script` (matches audit entry 14 Sep 16:02) |
| `benchmark:running` → `benchmark:done` | derived | click *Run benchmark*; `?state=benchmark` |
| `cluster:<name>` | 06 (hpc-1 selected) | click a cluster row |
| `profile:<name>` | 06 (gpu-single selected) | click a profile row; `?profile=cpu-array` |
| `editor:guided` / `editor:raw` | 06 guided | Seg; `?editor=raw` |
| `add-cluster` modal | derived | click *Add cluster*; `?modal=add-cluster` |
| `add-profile` | derived | `+ Add profile` link under the profiles table (recommended; not drawn) |

### Regions
1. Title `Compute & HPC` + project badge · Reset. Lede `Where work runs. Estimates include null draws.`
2. **This machine** card (≈ 7 % of the 1560 px page). Title; right secondary `⟳ Run benchmark`.
   Rows: `detected` · bold mono `16 cores · RTX 4070 12 GB · 64 GB RAM` · caption `estimates
   calibrated 12 Sep 2026`; `local jobs at once` · Number [2].
3. **Local limits per workspace** card (≈ 13 %). Title + muted `above a limit the work goes to the
   cluster`. Table `workspace` (bold) · `what is estimated` · `run locally up to` (Number + unit) ·
   `above the limit` (muted):
   `Analyse | one stage on one channel | 20 min | the stage offers Create SLURM script · downstream stages wait` ·
   `Discovery | one run across its channels | 20 min | Add and run disabled · Create SLURM script is primary` ·
   `Models | one training job · all arms and nulls | 2 h | Train locally disabled · Create SLURM script is primary` ·
   `Library | one grouping computation | 10 min | runs in the background with progress` ·
   `Review | building a queue | 5 min | runs in the background with progress`.
4. **Clusters** card (≈ 9 %). Title; right `+ Add cluster`. Table `name` · `login host` · `scheduler`
   · `account` · status: row `● hpc-1 | login.hpc-1.example | SLURM | a_myco | in use · 3 profiles`
   (green chip; row blue-100). Below: amber-outlined note with `(?)` `A second cluster? Add it here if
   you submit to more than one — each cluster keeps its own profiles and return path.`
5. **Job profiles · hpc-1** card (≈ 30 %). Title + muted `which profile each kind of job uses`.
   Table `profile` · `partition` · `nodes` · `gres` · `cpus` · `memory` · `time` · `array` · `used for`:
   `gpu-single gpu_short 1 gpu:1 8 32 G 04:00:00 — Models training · image encoding` (selected) ·
   `gpu-multinode gpu_long 2 gpu:1 per node 8 32 G 12:00:00 — [amber chip: check the job can use 2 nodes]` ·
   `cpu-array cpu 1 — 4 16 G 08:00:00 16 matrix profiles · per-channel stages`.
   Divider, then the editor: bold `gpu-single` + Seg `guided` | `raw template` · caption `guided
   keeps the script valid`. Rows: `environment setup` [module load cuda/12.1 && conda activate cnn];
   `working directory` [/scratch/$USER/cnn]; `results come back from` [/scratch/$USER/cnn/out] → 
   [./cluster_out] · caption `copied into the manifest inbox · Storage`; `email on finish` Toggle on.
   CodeBlock (dark, full card width, 7 lines):
   ```
   #!/bin/bash
   #SBATCH --account=a_myco --partition=gpu_short --nodes=1
   #SBATCH --gres=gpu:1 --cpus-per-task=8 --mem=32G --time=04:00:00
   #SBATCH --mail-type=END
   module load cuda/12.1 && conda activate cnn
   cd /scratch/$USER/cnn
   python -m pipeline.run --recipe {{recipe}} --out /scratch/$USER/cnn/out/{{job}}
   ```
6. **Job status** card (≈ 12 %). `cluster job status` · LockedChip `🔒 marked by hand` · caption `the
   site cannot see the queue · the researcher marks submitted, running, finished`; `remind to check a
   running job after` · `[3] × estimate`; `watch the manifest inbox every` · `[5] min`.

### Controls & interactions
| control | kit | behaviour / validation |
|---|---|---|
| `Run benchmark` | Button | `benchmark:running`: button disabled (`benchmark running…`), inline ProgressBar `benchmarking · 3 of 5 kernels` ~3 s → caption `estimates calibrated 16 Sep 2026`, Toast `Benchmark done (demo) · not wired yet: POST /api/compute/benchmark`. Immediate, not staged |
| `local jobs at once` | Field Number | integer 1–16 (detected cores) → "At most 16 (detected cores)"; consequence `local jobs at once 2 → 4 · local runs share 16 cores` |
| limit Number (×5) | Field Number + unit | Analyse/Discovery 1–240 min; Models 0.5–48 h; Library 1–120 min; Review 1–60 min → "Enter 1–240 min"; consequence (Analyse) as seeded; (Models) `Models limit 2 → 4 h · Train locally enabled for jobs estimated ≤ 4 h`. Saving writes an audit `settings` entry |
| `+ Add cluster` | Button → Modal | fields `name` (`[a-z0-9-]{2,20}`, unique → "hpc-1 already exists"), `login host` (hostname pattern → "Enter a host name like login.cluster.example"), `scheduler` Select `SLURM` (others disabled `not supported yet`), `account` Text required; *Add* stages a new row `0 profiles` and selects it (profiles card shows EmptyState `No profiles on <name> · Add profile`) |
| cluster row | Table select | re-binds the profiles card title and rows |
| `(?)` second-cluster note | InfoTip | B19: `Confirm which clusters you actually submit to.` |
| profile row | Table select | binds the editor; each cell editable inline on click: partition Text required; nodes 1–64; gres `—` or `gpu:<n>[ per node]`; cpus 1–256; memory `<n> G` (1–2048); time `HH:MM:SS` (≤ 168:00:00) → "Use HH:MM:SS"; array `—` or 1–10,000; used for read-only (derived) |
| gpu-multinode chip | amber Chip + InfoTip | `Two nodes only help if the job is written for it — check before using (B19).` |
| editor Seg `guided` / `raw template` | Seg | raw → CodeBlock becomes an editable mono textarea with tokens `{{recipe}}` `{{job}}` highlighted and an amber note `raw templates are not validated`; guided after raw edits → Popover `Discard raw edits and go back to guided?` |
| environment setup / working directory | Field Text | required; working directory must be absolute (`/…` or `$VAR/…`) → "Use an absolute path on the cluster" |
| results return path → local path | Field Text ×2 | remote absolute; local relative or absolute; caption links: `manifest inbox` → `#/jobs` (Jobs › Manifest inbox), `Storage` → `#/settings/storage-backups?focus=manifest-inbox` |
| `email on finish` | Toggle | adds/removes `#SBATCH --mail-type=END` in the preview |
| CodeBlock | CodeBlock (Copy / Save) | live preview from table row + editor fields; Copy → Toast `Script copied`; Save → Toast `not wired yet: download slurm_gpu-single.sh` |
| `marked by hand` | LockedChip | tooltip `The site cannot see the cluster queue; job status is marked by hand in Jobs.` link `Jobs` |
| remind × estimate | Field Number | 1–20 → consequence `j-0214 (3.3× its estimate) would no longer be flagged` when raised above 3.3 |
| watch inbox every | Field Number | 1–60 min |

### Plots
None.

### Fixtures
```ts
interface MachineInfo { cores: 16; gpu: 'RTX 4070 12 GB'; ram_gb: 64; calibrated: '12 Sep 2026'; local_jobs_at_once: 2 }
interface LocalLimit { workspace: 'Analyse'|'Discovery'|'Models'|'Library'|'Review'; estimated: string
  value: number; unit: 'min'|'h'; above: string }                               // SHARED (§0 local limits)
interface Cluster { name: 'hpc-1'; login_host: string; scheduler: 'SLURM'; account: 'a_myco'; status: string }  // SHARED (Jobs)
interface JobProfile { cluster: string; name: string; partition: string; nodes: number; gres: string | null
  cpus: number; memory_g: number; time: string; array: number | null; used_for: string[]; flag?: string
  env_setup: string; workdir: string; return_remote: string; return_local: string; email_on_finish: boolean }
interface JobStatusPolicy { marked_by_hand: true; remind_x_estimate: 3; watch_inbox_min: 5 }
```
Canon: local limits Analyse 20 min · Discovery 20 min · Models 2 h (§0); Library 10 min · Review 5 min
(§9.6); cluster `hpc-1` (Jobs uses it: `j-0214` running on hpc-1).

### Copy
All row labels, captions, table text and the script exactly as Regions; `Run benchmark`; `Add
cluster`; `A second cluster? …`; `guided keeps the script valid`.

### Frame ⟷ spec conflicts
- Caption `copied into the manifest inbox · Storage`: B26 moved the manifest inbox to **Jobs ›
  Manifest inbox** (the root path still lives in Storage). Recommend `copied into Jobs › Manifest
  inbox · path in Storage`, both linked.
- Audit log 14 Sep 16:02 records `Analyse local limit 10 → 20 min` while the spec default is 20 min,
  yet 06 outlines the field as differing. Treat 20 as saved and default; the outline is the seeded
  unsaved state from 10.

### Fog
- F16. Hardware detection, benchmark calibration and per-workspace estimate routing have no API.
- F17. B19: which clusters/partitions exist is unconfirmed; `pipeline.run` CLI in the script
  preview is illustrative.
- F18. Spec says profiles are "per cluster" with "which jobs use it"; how a job kind is assigned to
  a profile (the `used for` column) is not editable anywhere in the frames. Recommend read-only.

---

## settings.blocks

### Route & states
| state | frame | reached by |
|---|---|---|
| `clean` | 07 with Symbolic encoding on and no save bar | `#/settings/blocks` |
| `unsaved` | 07 | toggle a block; `?state=unsaved` seeds Symbolic encoding `on` → `off` (row tinted amber-100), sentence `disabling Symbolic encoding hides it from Insert · 2 templates still use it and stay readable` (see conflict) |
| `usedby:<block>` | derived | click `N templates`; `?usedby=symbolic-encoding` — Popover |

### Regions
1. Title `Blocks` + project badge · Reset. Lede `Read from Adapters/ at start · code a7f3c1e. Each
   block follows the contract in §6.8.`
2. **Registered blocks** card (≈ 75 % height). Title + muted `15 registered · 1 not built`. Table
   `block` (bold, ≈ 15 %) · `signature` (mono, ≈ 16 %) · `version` · `adapter` (muted mono, ≈ 15 %) ·
   `null` · `used by` (blue link) · `on` (Toggle). 16 rows ≈ 36 px:
   | block | signature | version | adapter | null | used by | on |
   |---|---|---|---|---|---|---|
   | Baseline removal | Signal → Signal | 1.2 | adapters/baseline.py | — | 6 templates | on |
   | Bandpass filter | Signal → Signal | 1.0 | adapters/bandpass.py | — | 5 templates | on |
   | Noise floor | Signal → Signal + estimate | 1.1 | adapters/noise_floor.py | surrogate estimate | 3 templates | on |
   | Symbolic encoding | Signal → Encoding | 2.1 | adapters/sax.py | — | 2 templates | on (off in `unsaved`) |
   | Drop detection | Encoding → SpanSet | 1.4 | adapters/drop_detect.py | surrogate count | 6 templates | on |
   | Matrix profile | Signal → Scores | 3.0 | adapters/matrix_profile.py | circular shift | 4 templates | on |
   | Threshold to spans | Scores → SpanSet | 1.0 | adapters/threshold.py | inherited | 7 templates | on |
   | Seeded search | Signal + exemplar → Scores | 1.4 | adapters/mass.py | circular shift | 2 templates | on |
   | Sliding windows | Signal → WindowSet | 2.0 | adapters/windows.py | split checks | 2 templates | on |
   | Window matrix | WindowSet → WindowSet | 1.3 | adapters/window_matrix.py | — | 2 templates | on |
   | Hierarchical cluster | WindowSet → Grouping | 1.1 | adapters/cluster.py | bootstrap | 2 templates | on |
   | Image encode | WindowSet → Encoding | 1.0 | adapters/gramian.py | — | 2 templates | on |
   | CNN classifier | Encoding + labels → Model | 0.9 | adapters/cnn.py | label shuffle | 1 template | on |
   | Resolve spans · slope | SpanSet → Features | 1.0 | adapters/slope.py | matched windows | 1 template | on |
   | Aggregate | Features → views | 1.0 | adapters/aggregate.py | null β | 1 template | on |
   | Model stage (muted) | Model + WindowSet → Scores | — | `not built · B13` (amber) | — | 3 templates | off, disabled |
   Footnote `(i) a disabled block is hidden from the insert modal; runs and templates that used it
   stay readable`.
3. Save bar (`unsaved`).

### Controls & interactions
| control | kit | behaviour / validation |
|---|---|---|
| `on` Toggle | Toggle | stages enable/disable; consequence `disabling <block> hides it from Insert · <n> templates still use it and stay readable`; enabling: `<block> appears in Insert again` |
| Model stage Toggle | DisabledReason | disabled, reason `not built · B13 — the block has no adapter yet` |
| `N templates` | link → Popover | lists the template names using that block (each a link to `#/library/templates?template=<name>`), footer `Open in Library ›`; `0 templates` shows plain muted text |
| adapter path | mono text | hover title `webui cannot open files` (no action) |
| signature | text | InfoTip with the §6.8 contract type names (Signal, SpanSet, WindowSet, Encoding, Grouping, Model, Scores, Features) |
| `Reset page to defaults` | shell | default = every built block on |

### Plots
None.

### Fixtures
```ts
interface BlockRow { id: string; name: string; signature: string; version: string | null; adapter: string | null
  null_kind: string | null; used_by_templates: string[]; enabled: boolean; built: boolean; backlog?: 'B13' }  // SHARED (Analyse insert modal, chain glyph registry, Library templates)
```
Template usage must reproduce the frame counts from the 14-template canon. Suggested map:
Baseline removal → drop_motifs9, sharkfin_v2, mp_discord_v3, spike_shape_v1, drop_cnn_v1, sharkfin_cnn_v2 ·
Symbolic encoding → drop_motifs9, sharkfin_v2 · Drop detection → drop_motifs9, sharkfin_v2 + 4 others ·
Model stage → drop_cnn_v1, sharkfin_cnn_v2, cnn_detect_cluster_v1 · CNN classifier → cnn_windows_v3 ·
Sliding windows / Window matrix / Image encode / Hierarchical cluster → cnn_windows_v3, cnn_windowset_v1.
The remaining 5 unnamed templates are for the Library inventory to name; do not invent recordings.

### Copy
Lede, title, sub-caption, all 16 rows, footnote, `not built · B13`.

### Live vs demo
Settings is not live, but `GET /api/adapters` already returns `AdapterCard[]` (`display_name`,
`signature`, `category`, `known_broken`, …) and Analyse's insert modal is built on it. A later
wiring could list real adapters here; tonight render the canon rows (the live registry names and
counts differ from §0 and the frame). If a builder wants a hint of liveness, a muted footer
`bridge reports <n> adapters` is acceptable but optional.

### Frame ⟷ spec conflicts
- Save-bar sentence says templates "stay **runnable**"; spec §9.7 and the frame's own footnote say
  "stay **readable**". Recommend "readable" (a template whose block is disabled can be opened, not
  necessarily run).
- B24 fixed Noise floor as `Signal → Signal + estimate` and Drop detection `Encoding → SpanSet`;
  frame 07 agrees (the backlog's "Settings › Blocks says a third thing" is resolved).

### Fog
- F19. Enabling/disabling a block has no core setting (the registry is code). Toast
  `not wired yet: PUT /api/blocks/<id>`.
- F20. Five of the 14 templates are not named in §0; per-block template lists are partial.

---

## settings.review-queues

### Route & states
| state | frame | reached by |
|---|---|---|
| `clean` (differs) | 08 | `#/settings/review-queues`; training-windows cap outlined |
| `unsaved` | derived | edit; `?state=unsaved` seeds Training windows cap `10,000` → `20,000`, sentence `training-window queues cap at 20,000 · q-18 keeps its current cap` |
| `unblind-warning` | derived | turn blind off on Training windows or Model verification: inline amber note under the row |
| `invalid` | derived | out-of-range values |

### Regions
1. Title `Review queues` + project badge · Reset. Lede `Defaults for new queues. The blind state is
   stored with every verdict.`
2. **Queue defaults by source** card (≈ 42 %). Table `source` (icon + bold) · `blind` (Toggle +
   `visible`/`blind`) · `verdict keys` (Select ≈ 190 px) · `cap` (Field ≈ 95 px) · `order` (Select ≈
   160 px) · `writes` (muted):
   | source | blind | verdict keys | cap | order | writes |
   |---|---|---|---|---|---|
   | ◎ Discovery run | off · visible | full · S I N A U | — | score, high first | adjudications |
   | ⌖ Seed search | off · visible | full · S I N A U | — | distance, near first | adjudications |
   | ∿ Explore spans | off · visible | full · S I N A U | — | time | annotations |
   | ▥ Library family | off · visible | full · S I N A U | — | distance to medoid | adjudications |
   | ▦ Training windows | on · blind | binary + classes | 20,000 | stratified by channel | window verdicts |
   | 🧠 Model verification | on · blind | full + classes | 40 | stratified by class | window verdicts |
   Footnote `(i) blind hides score, family affinity and model calls until the verdict · artifact
   likelihood is never hidden`.
3. **Clusters** card (≈ 22 %). Title + muted `batch verdicts in Review`. Rows: `cohesion limit (i)` ·
   [0.45] · caption `a member farther than this from the medoid is excluded from the batch by
   default`; `a sequence is` + sub `shared with Library sequences` · `same run and channel, gap ≤ [6]
   min  at least [2] events`; `largest batch` · `[50] members`; `undo reverses the whole batch` ·
   LockedToggle.
4. **Promotion** card (≈ 12 %). Title + muted `the seed verdict`. `S promotes to the Library` ·
   LockedToggle · caption `a separate promote step would duplicate the seed key`; `suggest the
   nearest family when d ≤` · [0.30] · caption `otherwise the panel suggests no family yet`.

### Controls & interactions
| control | kit | behaviour / validation |
|---|---|---|
| blind Toggle (×6) | Toggle + label | label flips `visible`/`blind`; turning **off** on Training windows or Model verification shows amber inline note `the human verdict is the measurement here — showing the machine's call first anchors it (P20)` and consequence `new model-verification queues show scores before the verdict · verdicts stored as not blind` |
| verdict keys Select | Select | `full · S I N A U` · `binary · I N` · `binary + classes` · `full + classes`; key letters read from Vocabulary (a rekey there updates these labels) |
| cap | Field Text/Number | `—` or empty = no cap; else integer 1–100,000 → "Cap must be a whole number up to 100,000, or —" |
| order Select | Select | `score, high first` · `score, low first` · `distance, near first` · `time` · `distance to medoid` · `stratified by channel` · `stratified by class` · `random (seeded)` |
| `writes` | text | read-only; InfoTip `Detections are machine-only; annotations and adjudications are human-only (write target, P20).` |
| `cohesion limit (i)` | Field Number | 0.05–1.00 → "Enter 0.05–1.00"; consequence `cohesion 0.45 → 0.35 · more members excluded from batches by default` |
| gap ≤ / at least | Field Number ×2 | gap 0.5–120 min; events integer 2–100; **shared value** with Library groupings › Sequences — editing here updates that page's store too; consequence `sequence gap 6 → 10 min · also changes Library sequences (Library groupings)` with link |
| `shared with Library sequences` | link | `#/settings/library-groupings?focus=sequence-gap` |
| largest batch | Field Number | 2–500 |
| `undo reverses the whole batch` / `S promotes to the Library` | LockedToggle | tooltips `Enforced: undo reverses a whole batch` / `Enforced: pressing S is the promotion (P21)` |
| nearest family d ≤ | Field Number | 0.05–1.00; must be ≤ Library groupings `omit motifs with nearest family d >` (0.50) → amber warning "suggested families would be ones the Library omits" |

### Plots
None.

### Fixtures
```ts
interface QueueDefault { source: 'Discovery run'|'Seed search'|'Explore spans'|'Library family'|'Training windows'|'Model verification'
  icon: string; blind: boolean; verdict_keys: string; cap: number | null; order: string
  writes: 'adjudications'|'annotations'|'window verdicts' }
interface ClusterRules { cohesion: 0.45; seq_gap_min: 6; seq_min_events: 2; largest_batch: 50; undo_whole_batch: true }  // seq_* SHARED with Library groupings
interface PromotionRules { s_promotes: true; suggest_family_d_le: 0.30 }
```
Shared: verdict keys from Vocabulary; queue ids in consequences (`q-12`, `q-15`, `q-18`, `q-19`).

### Copy
Lede, table text, footnote and captions exactly as Regions.

### Frame ⟷ spec conflicts
None material. Spec §9.8 matches.

### Fog
- F21. B16: cohesion 0.45 and gap ≤ 6 min / ≥ 2 events are placeholders "still to decide".
- F22. Verification sample size appears twice — Review queues cap `40` and Models & registration
  `human verification sample 40`. Spec does not say whether they are one value. Recommend one
  shared value, edited on Models & registration, shown here read-only with a link.

---

## settings.models-registration

### Route & states
| state | frame | reached by |
|---|---|---|
| `clean` (differs) | 09 | `#/settings/models-registration` (scrolls ≈ 1.15×); `warn below` field outlined |
| `unsaved` | derived | edit; `?state=unsaved` seeds `warn below N test windows per class` `30` → `50`, sentence `classes with fewer than 50 test windows warn at launch · plateau (43 test windows in j-0212) now warns` |
| `seed-repeats:on` | derived | Toggle on → repeats Number enabled |
| `invalid` | derived | test + validation ≥ 60 % etc. |

### Regions
1. Title `Models & registration` + project badge · Reset. Lede `Defaults for new training jobs and the
   checks a model must pass to be registered.`
2. **Evaluation split** card (≈ 20 %). Title + muted `set aside before training`. Rows:
   `test portion` · `[20] %  validation [10] %`; `split` · LockedChip `🔒 blocked by time within each
   channel` · caption `never a random sample of windows`; `gap between blocks` · `≥ window + [0] s` ·
   caption `the minimum is one window and cannot go lower`; `linked recordings` · LockedChip `🔒 never
   split across sides` · caption `fs1 and fs2 of one recording stay on one side`; `warn below N test
   windows per class` · [50].
3. **Training** card (≈ 16 %). `label arms` · Chips `manual` (green) `cluster` (purple) + LockedChip
   `🔒 RF baseline` · caption `the random-forest baseline is always trained`; `train on windows
   labelled in every arm` · Toggle on; `repeat with different seeds` · Toggle off + disabled Number
   `[3] repeats`; `early stopping patience` · `[10] epochs`.
4. **Calibration** card (≈ 11 %). Title + muted `per class, on the validation block`.
   `suggested threshold at precision` · [0.80] · caption `shown in the Threshold stage as its
   recommended value`; `reliability bins` · [10].
5. **Registration gate** card (≈ 32 %). Title + muted `the researcher has the final say`. Table
   `check` (bold) · `threshold` · `if it fails` (Badge):
   | check | threshold | if it fails |
   |---|---|---|
   | beats the label-shuffle null | p < [0.01] | `blocks registration` (red) |
   | beats the random-forest baseline | ΔF1 CI excludes [0] | `blocks registration` |
   | test windows unseen in training | 🔒 always | `blocks registration` |
   | calibration per class | ECE ≤ [0.10] | `warning · needs a reason` (amber) |
   | human verification sample | stratified by class, [40] | `—` (grey) |
   | agreement with the human sample | ≥ [80 %] | `warning · needs a reason` |
   | sign-off recorded with the model | 🔒 always | `required` (red) |
   Final row outside the table: `retiring a model a template still uses` · LockedChip `🔒 blocked` ·
   caption `the list of templates is shown instead`.

### Controls & interactions
| control | kit | behaviour / validation |
|---|---|---|
| test portion / validation | Field Number % ×2 | integers 5–40 each; test + validation ≤ 60 → "Leave at least 40 % of windows for training"; consequence `test portion 20 → 25 % · applies to new training jobs · registered models keep their split` |
| split / linked recordings / RF baseline / unseen test / sign-off / retiring | LockedChip | tooltips with the rule: `Enforced (P12, P19)`; `Enforced: linked recordings are never split` |
| gap extra seconds | Field Number | integer 0–86,400 s; negative → "The gap cannot go below one window" |
| warn below N | Field Number | integer 1–1,000 |
| label arm chips `manual` / `cluster` | toggle Chips | at least one of the two on → "A training job needs at least one label arm"; consequence `cluster arm off · new jobs train on manual labels only · the paired comparison (Models › Compare) is unavailable` |
| train on windows labelled in every arm | Toggle | off → amber note `arms would train on different windows; the comparison is no longer paired` |
| repeat with different seeds | Toggle | enables repeats Number (2–10); disabled Number shows DisabledReason `turn on seed repeats to set a count` |
| early stopping patience | Field Number | 1–100 epochs |
| precision | Field Number | 0.50–0.99 |
| reliability bins | Field Number | 5–50 |
| gate thresholds | Field Number inline | p 0.001–0.10; ΔF1 CI excludes −0.20–0.20; ECE 0.01–0.50; sample 10–500 (integer); agreement 50–100 %; consequence `ECE limit 0.10 → 0.15 · cnn_cluster_v1's accepted warning (ECE 0.12) would now pass` |
| `if it fails` Badges | Badge | read-only (see fog) |

### Plots
None.

### Fixtures
```ts
interface SplitDefaults { test_pct: 20; validation_pct: 10; blocked_by_time: true; gap_extra_s: 0; linked_never_split: true; warn_below_test_windows: 50 }
interface TrainingDefaults { arms: { manual: boolean; cluster: boolean; rf_baseline: true }; intersect_labelled: boolean; seed_repeats: { on: boolean; n: number }; patience_epochs: number }
interface CalibrationDefaults { precision: 0.80; bins: 10 }
interface GateCheck { id: string; label: string; threshold_label: string; value: number | null; locked: boolean; on_fail: 'blocks registration'|'warning · needs a reason'|'required'|'—' }
```
Shared canon: verification sample 40 (33 of 40 judged, 28 agree — Models), test block 432 windows,
models `cnn_windows_v2 · manual`, `rf_windows_v1 · manual`, `cnn_cluster_v1`, templates using models
(`drop_cnn_v1`, `sharkfin_cnn_v2`, `cnn_detect_cluster_v1`).

### Copy
Lede, all row labels, captions, table and badges exactly as Regions.

### Frame ⟷ spec conflicts
- Spec §9.9 lists "gap ≥ window plus an optional extra" and "class warning below 50 test windows";
  frame matches. The frame draws the seed-repeats Number with a lock glyph while its Toggle is off;
  that is a disabled state, not a locked rule — render as DisabledReason, not LockedField.

### Fog
- F23. Whether `if it fails` consequences are editable is unspecified (spec: "each check's threshold
  and consequence"). Render read-only.
- F24. The seeded "from" value (30) and "plateau 43 test windows" are invented for the demo sentence.

---

## settings.library-groupings

### Route & states
| state | frame | reached by |
|---|---|---|
| `clean` (differs) | 10 | `#/settings/library-groupings`; `omit motifs … d >` outlined |
| `unsaved` | derived | edit; `?state=unsaved` seeds omit d `0.40` → `0.50`, sentence `omit motifs past d 0.50 · fewer omitted at the next regroup · existing groupings keep their settings` |
| `unit:<unit>` | derived | unit Seg; basis Select options change |
| `invalid` | derived | weights not summing to 1, bad ranges |

### Regions
1. Title `Library groupings` + project badge · Reset. Lede `Defaults for new groupings. Every grouping
   is saved with its settings.`
2. **Default grouping** card (≈ 13 %). Title + muted `used for imports and new catalogues`. `unit` ·
   Seg `single motifs` | `sequences` | `spike trains`; `basis` · Select [shape distance · Ward] (≈ 200 px)
   · muted `cut` · [0.42].
3. **What does not fit** card (≈ 17 %). Title + muted `omitted from that grouping round`. `omit motifs
   with nearest family d >` · [0.50] · caption `omitted entries are flagged and listed`; `omit groups
   smaller than` · `[10] members`; `omitted entries are deleted` · LockedChip `🔒 never`.
4. **Sequences** card (≈ 12 %). Title + muted `shared with Review clusters`. `events belong to one
   sequence when` · `same run and channel, gap ≤ [6] min  at least [2] events`; `sequence similarity
   weights` · `event shapes [0.6]  gaps [0.4]`.
5. **Feature bases** card (≈ 24 %). Title + muted `bins, no distance`. Table `basis` (bold) · `feature`
   (Select ≈ 250 px) · `bins` (Select ≈ 150 px) · `count` (Number) · `range` (Text ≈ 200 px):
   `amplitude | peak-to-peak | quantiles | 5 | —` ·
   `timescale | duration | log-spaced | 6 | 0.5 s – 10 min` ·
   `frequency content | dominant frequency · Welch PSD | log-spaced | 6 | 0.002 – 0.5 Hz` ·
   `polarity | up / down / biphasic | fixed | 3 | ratio threshold 0.2`.
6. **Hand edits** card (≈ 11 %). `re-apply hand edits when regrouping` · LockedToggle; `orphaned hand
   edits` · Seg `keep as a hand group` | `hold` · caption `orphaned = pointing at a family the new
   grouping lacks`.

### Controls & interactions
| control | kit | behaviour / validation |
|---|---|---|
| unit Seg | Seg | dependent: `single motifs` → basis options `shape distance · Ward` · `shape distance · average` · `feature bins · amplitude` · `feature bins · timescale` · `feature bins · frequency content` · `feature bins · polarity` · `labels · class` · `labels · provenance`; `sequences` → `sequence similarity · Ward` + the feature-bin options; `spike trains` → same as single motifs plus amber note `what a spike train is when not imported as one is undecided (B17)` |
| basis Select | Select | distance bases show `cut` Field (0.05–2.00); feature-bin and label bases hide `cut` and show muted link `bins set in Feature bases ↓` (scrolls to the card) |
| omit d > | Field Number | 0.05–2.00; consequence as seeded; must be ≥ Review queues `suggest nearest family d ≤` (0.30) → amber warning |
| omit groups smaller than | Field Number | integer 2–1,000 |
| `never` | LockedChip | `Enforced: omitted entries are flagged, never deleted` |
| gap / at least | Field Number | **shared** with Review queues › Clusters (same store); link in consequence `also changes Review clusters` |
| weights shapes / gaps | Field Number ×2 | 0–1, one decimal; editing one auto-sets the other to `1 − value` with caption `weights sum to 1`; direct invalid entry → "Weights must sum to 1.0" |
| feature Select (per basis) | Select | amplitude: `peak-to-peak` · `depth below baseline` · `RMS`; timescale: `duration` · `rise time` · `fall time`; frequency: `dominant frequency · Welch PSD` · `spectral centroid`; polarity: `up / down / biphasic` |
| bins Select | Select | `quantiles` (range disabled `—`, count 2–20) · `log-spaced` (range `a – b unit`, 0 < a < b, count 2–20) · `linear` · `fixed` (polarity only; count locked to 3, range `ratio threshold x`, 0 < x < 1) |
| frequency range | Field Text | upper edge above 0.5 Hz warns `above Nyquist for 1 Hz recordings (M2_aug fs1, M3_jul, M4_aug)` |
| `re-apply hand edits` | LockedToggle | `Enforced: hand edits survive regrouping (P22)` |
| orphaned Seg | Seg | consequence `orphaned hand edits are held for review instead of forming a hand group` |

### Plots
None.

### Fixtures
```ts
interface GroupingDefaults { unit: 'single motifs'|'sequences'|'spike trains'; basis: string; cut: number | null
  omit_d_gt: number; omit_groups_lt: number; seq_gap_min: number; seq_min_events: number   // seq_* SHARED with Review queues
  weights: { shapes: number; gaps: number }
  feature_bases: { basis: string; feature: string; bins: 'quantiles'|'log-spaced'|'linear'|'fixed'; count: number; range: string | null }[]
  orphaned: 'keep as a hand group'|'hold' }
```
Shared: families (F-03 etc.) are referenced only in consequences.

### Copy
Lede, card titles and captions, table text exactly as Regions.

### Frame ⟷ spec conflicts
None material; spec §9.10 matches.

### Fog
- F25. B17: sequence similarity, frequency-content feature, timescale feature, spike-train unit and
  default cuts/bins are placeholders with no pre-registration. Alternate feature options above are
  UI placeholders.
- F26. `cut 0.42` units (Ward linkage height on z-normalised shape distance?) unspecified.

---

## Kit needs

(pending — filled at the end)
