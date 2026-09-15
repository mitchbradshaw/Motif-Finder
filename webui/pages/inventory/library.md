# Inventory — Library

Source frames: `prototyping/imgs/library/*.pdf` (8, all 1440 × 900, none scroll). Spec:
`prototyping/UI_FUNCTIONAL_SPEC.md` §8 (Library), §6.9 (saved window sets), §4.2 (motif identity and
revisions), §12 P8 (show-all caps ~10), P18 (window set is an artifact), P22 (Library computes its own
groupings; three sections). §0 canon wins on names, counts and ids. Backlog items read: B12, B16, B17,
B26–B30 and the Library sweep notes (`UI_REVIEW_BACKLOG.md` lines 32, 64–72, 100–128, 187–199).

Coordinates below are frame pixels at 1440 × 900: nav rail x 0–62, header y 0–42, content x 62–1440.

## Pages

| page id | route | frames covered | spec § | states (frame → state name → how reached) |
|---|---|---|---|---|
| library.recurrence | `#/library/recurrence` | library-1-recurrence.pdf | §8.1, §8.2, §8.4 | 1 → `selected` (3 channels selected, shared-ground warning) → default demo selection, or `?sel=M2_aug_fs1:CH3_A2,M2_aug_fs1:CH4_A2,M3_jul:CH2` · (derived) `no-selection` → *Clear* / `?sel=` · (derived) `count` → Seg *count* / `?cell=count` · (derived) `recordings 4–5` → pager › / `?rec=2` · (derived) `omitted-drawer` → *Show all 38* / `?drawer=omitted` · (derived) `empty` → `?library=empty` |
| library.atlas | `#/library/atlas` | library-2-atlas-motifs.pdf, library-2b-atlas-sequences.pdf | §8.2, §8.5 | 2 → `motifs` (g-07, scope 3 channels, F-03 in rail) → default, or *Browse 3 channels →* on recurrence, `?unit=motifs&family=F-03` · 2b → `sequences` (g-08, S-02 in rail) → grouping-bar Seg *sequences* / `?unit=sequences&family=S-02` · (derived) `omitted-drawer` → *Show omitted* / `?drawer=omitted` · (derived) `no-scope` → remove all scope chips / `?scope=all` · (derived) `empty` → `?library=empty` |
| library.family | `#/library/family/<familyId>` (canonical `F-03`) | library-3-family.pdf | §8.6, §4.2 | 3 → `member-selected` (m-1850 in rail, 3 selected, batch bar) → *Open all 112 members →* then click m-1850 / `#/library/family/F-03?member=m-1850&sel=E-0102,m-1843,m-1850` · (derived) `no-selection` (batch bar hidden) · (derived) `hand-only` → *hand edits only* / `?hand=1` · (derived) `sort-*` → Seg / `?sort=time` · (derived) `page-n` → pager / `?page=2` · (derived) `revisions-popover` → click revisions / `?popover=revisions` · (derived) confirm modals `?modal=remove` / `?modal=make-exemplar` |
| library.grouping | `#/library/grouping` | library-4-edit-grouping.pdf | §8.2, §8.3 | 4 → `frequency-content` (modal over dimmed atlas) → *Edit grouping* on any Motifs page, then basis *frequency content* / `#/library/grouping?from=atlas&basis=frequency-content` · (derived) `basis-<kind>` for the other 8 bases → `?basis=` · (derived) `invalid` (bad bins/range; Apply disabled) · (derived) `applying` (sim job) → *Apply grouping* / `?state=running` · (derived) `saved` → *Save as grouping g-09* |
| library.import | `#/library/import` | library-5-empty-import.pdf | §8.7 | 5 → `empty+dry-run` → *Import…* on the empty Motifs section / `#/library/import?library=empty` · (derived) `dry-run` on a populated library → toolbar *Import* on frames 1–3 / `#/library/import` · (derived) `bundle-invalid` → bundle select / `?bundle=no-provenance` · (derived) `importing` → *Import 410 motifs* / `?state=running` · (derived) `done` |
| library.window-sets | `#/library/window-sets` | library-6-window-sets.pdf | §8.8, §6.9, P18 | 6 → `set-selected` (ws_M2aug_3ch_600s in rail) → section Seg *Window sets* / `?set=ws_M2aug_3ch_600s` · (derived) `not-train-safe-selected` → click row 5 or 6 / `?set=ws_M2aug_1ch_60s` · (derived) `filter-*` → Seg / `?safe=not-train-safe` · (derived) `delete-confirm` → *Delete* on an unused set / `?modal=delete` · (derived) `coverage-at-save` → rail Seg / `?coverage=save` |
| library.templates | `#/library/templates` | library-7-templates.pdf | §8.9 | 7 → `template-selected` (mp_drops_v3 in rail) → section Seg *Templates* / `?template=mp_drops_v3` · (derived) `kind-*` → Seg / `?kind=training` · (derived) `model-stage` → toggle / `?model=1` · (derived) `page-2` → *next ›* / `?page=2` · (derived) `diff-modal` → *diff* / `?modal=diff&from=v2` · (derived) `export-json` → `?modal=export` · (derived) `import-json` → `?modal=import` · (derived) `archive-confirm` → `?modal=archive` |

"Derived" = a state the frames imply (a control is drawn) but no frame draws. Builders implement it with
the same kit, no fidelity target beyond this file.

**Decision — the empty library is a state, not a route; the import is a route.** Empty is a *data
condition* of the Motifs section, not a destination: `#/library/recurrence`, `#/library/atlas` and
`#/library/family/F-03` must all degrade to it when the catalogue holds 0 motifs (a deep link into an
empty atlas must not show a blank grid — the silently-blank-pane failure CLAUDE.md warns about). The demo
reaches it with `?library=empty` on any Motifs route; the flag is sticky in the in-memory library store
for the session. The import dry run *is* a destination: it has its own lifecycle (choose bundle → dry run →
import → queue), and it is reachable from two places — the empty state's *Import…* and the populated
toolbar's *Import* (frames 1–3). So `#/library/import` is its own route, whose left column is the empty
state when the library is empty (frame 5) and a compact "library now" card otherwise.

---

## Shared Library chrome (every page)

Not a page; every page below references it. Build once (`library/LibraryChrome.tsx`).

- **Header** (shell): workspace `Library`, page = section name (`Motifs` · `Window sets` · `Templates`),
  mono subtitle per page (given in each page's Copy), search placeholder `Search spans, runs, families`
  with `Ctrl K`, chips `● 3 need you` (blue) and `🔒 M4 held out`, plus the kit's `demo data` chip.
  Nav rail: Library active; foot `Jobs · 3`, `Settings`.
- **Section toolbar** (y 55–85, x 86–1366): left, a Seg with icons and counts — `Motifs 1,402` ·
  `Window sets 6` · `Templates 14` (x 86–438, 30 px tall; counts muted mono). Motifs shows `0` in the
  empty state. After a vertical divider, a Breadcrumb on Motifs pages: `Recurrence` (frame 1, black,
  current) · `Recurrence › Atlas` (frames 2, 2b, 4) · `Recurrence › Atlas › F-03 sharkfin` (frame 3); earlier
  crumbs are blue links. Right: page actions (outline buttons, 30 px) listed per page.
  - Seg click → `#/library/recurrence` (Motifs remembers its last Motifs route in the store), `#/library/window-sets`, `#/library/templates`.
- **Grouping bar** (Motifs pages only; card y 100–147, x 78–1374, 47 px): left to right —
  - muted label `group`, Seg `single motifs · sequences · spike trains` (grey track, white active pill);
  - basis chip (light-blue fill, blue text, ˅): `by shape distance  Ward · cut 0.42` (g-07) or
    `by cut 0.50  sequence similarity` (g-08, frame 2b word order); opens **Popover "Groupings"**;
  - divider; filter chips: `adjudicated only` (white outline = inactive toggle), `≥ 10 members` (light-blue
    = active), `artifact flagged` (light-blue; `flagged` bold), `+ filter` (outline; absent in frame 2b);
  - right: amber chip with flag icon `38 omitted · flagged` (g-07) / `1,035 omitted · flagged` (g-08),
    then outline button with sliders icon `Edit grouping`.
- **Grouping bar interactions**
  - unit Seg → switches to the most recent saved grouping for that unit: `single motifs` → g-07,
    `sequences` → g-08 (navigates to `#/library/atlas?unit=sequences` from atlas/recurrence; stays on
    recurrence if already there). `spike trains` has no saved grouping → navigates to
    `#/library/grouping?unit=spike-trains&from=<current>`. On the family page the Seg is inert with
    InfoTip "switch grouping from the atlas".
  - basis chip → Popover "Groupings": radio list of saved groupings `g-07 · single motifs · shape distance
    · cut 0.42 · 10 families (current)`, `g-08 · sequences · sequence similarity · cut 0.50 · 6 families`,
    `g-01 · single motifs · shape distance · cut 0.42 · first import` (and `g-09` once saved); picking one
    switches grouping in memory (toast `Grouping g-08 applied · scope cleared`); footer link
    `Edit grouping…`. Escape / outside click close.
  - `adjudicated only` → in-memory toggle (active styling); counts unchanged; toast
    `not wired yet: regroup filter adjudicated_only`.
  - `≥ 10 members` → Popover with Number field "minimum members" (integer 1–1000, message
    `whole number from 1 to 1000`); applying updates chip text.
  - `artifact flagged` → Popover, radio `flagged · kept visible` (selected) and `excluded` disabled with
    DisabledReason `cross-channel artifacts stay visible in the Library (§8.4)`.
  - `+ filter` → Popover listing `recording`, `class`, `tag`, `judged fraction`, `hand edits only`; picking
    adds a removable chip in memory; toast `not wired yet: regroup filter <kind>`.
  - omitted chip → opens **Drawer "Omitted from g-07"** (`?drawer=omitted`): SmallMultiples of omitted
    motif thumbnails, 10 per page with pager `1–10 of 38 ›`, each with nearest family and `d`; footer
    `Send omitted to Review as a queue` (toast, see below).
  - `Edit grouping` → `#/library/grouping?from=<recurrence|atlas|family/F-03>`.
- **"Send … to Review as a queue"** anywhere in the Library → Toast `Queue "Library · <name>" · N items ·
  not wired yet: POST /api/review/queues` with a `Open Review` action (→ `#/review`). Queue names follow P20:
  `Library · F-03 unjudged`, `Library · g-07 omitted`, `Library · import drop_motifs5`.

---

## library.recurrence

### Route & states
- `#/library/recurrence` — frame 1. Default demo store holds the canon selection (M2_aug fs1 CH3_A2,
  CH4_A2; M3_jul CH2), so the bare route reproduces the frame.
- `selected` (frame 1): 3 channel columns outlined; rail totals; amber shared-ground callout. Deep link
  `?sel=M2_aug_fs1:CH3_A2,M2_aug_fs1:CH4_A2,M3_jul:CH2`.
- `no-selection` (derived): *Clear* or `?sel=`. Rail "Selection" shows EmptyState line `Tick channels or
  recordings to build a selection`; *Browse* is DisabledReason `select at least one channel`.
- `selected, no warning` (derived): *Deselect CH4_A2* → callout disappears, totals update.
- `count` (derived): Seg `count` or `?cell=count`; cells show integers.
- `recordings 4–5 of 5` (derived): pager › or `?rec=2`: `M2_aug fs2` group and `M4_aug` group rendered
  locked (see Fog).
- `omitted-drawer` (derived): *Show all 38* / omitted chip / `?drawer=omitted`.
- `empty` (derived): `?library=empty` → the EmptyState of library.import's left column, full width.
- `unit=sequences` (derived): rows become S-01…S-06 from g-08 (same matrix).

### Regions
1. Header, section toolbar (breadcrumb `Recurrence`), grouping bar — see Shared chrome. Toolbar actions
   right: `Find by shape` (scan icon), `Import` (download icon), `Export` (upload icon).
2. **Matrix card** x 78–1042 (≈ 67 % width), y 158–693. White card, 12 px radius.
   - Title row (y 172–194): `Where each family occurs` + InfoTip (i); right: Seg `per hour · count`
     (x 736–850), then pager `‹  recordings 1–3 of 5  ›` (square icon buttons).
   - Column header block (y 200–265): for each recording group — checkbox + recording name (mono bold,
     e.g. `M2_aug fs1`), caption `45.2 h · 31% reviewed` (see conflicts: use `721 h`); under it one column
     per channel: checkbox + channel name (mono 10 px, truncates `CH1_A…`), then a 3 px reviewed-coverage
     bar (green fill on grey). Groups: M2_aug fs1 x 277–530 (6 cols), M3_jul x 550–716 (4 cols),
     L_LM_Jul26_J x 736–946 (5 cols); ≈ 20 px gap between groups. Column pitch 42 px, cell 38 × 30.
   - Row label column x 92–270: exemplar sparkline (36 × 24, black), family id in family colour (mono
     bold, `F-01`), name (`single drop`), second line blue caption `2 recordings`. Row pitch 34.7 px,
     10 rows y 278–620.
   - Cells (38 × 30, 4 px radius): value text mono 10 px centred. Fill = 5-step sequential blue ramp on
     members / h (legend 0 → 1.0), text white on the two darkest steps. Blank light-grey cell = reviewed,
     no members. `?` cell = white with grey border, `?` text = no reviewed coverage and no members.
     Artifact cell = light-red fill, red border, text `! 0.61` in red.
   - Selection outlines: 2 px blue rounded rectangle around each selected column, from the column header
     (checkbox ticked, channel name blue bold, header filled light blue) down through the last row.
   - Legend row (y 647): `members / h` + 5 swatches + `0 → 1.0` · `?` swatch `no reviewed coverage` ·
     red swatch `cross-channel artifact, kept visible` · dashed-blue swatch `selected`.
   - Reading-rule caption (y 670): `(i) dark in one recording and empty in the others → a property of that
     recording, not of the organism`.
3. **Omitted strip card** x 78–1042, y 705–805: amber flag icon, bold `38 motifs fit no family in this
   grouping`, mono caption `nearest family d > 0.50 · left out of counts, not deleted`; right blue links
   `Send to Review as a queue`, `Show all 38`. Row of 12 amber-tinted thumbnails (62 × 44, amber border,
   brown trace) x 92–1018.
4. **Right rail** x 1058–1374 (≈ 23 %), y 158–805, one white card:
   - `This grouping` (icon) + mono `g-07` right. KeyValue rows: `unit` single motifs · `basis` shape
     distance · Ward · `cut` 0.42 · `computed` 14 Sep 2026 · 1,402 motifs · `families` **10** · `omitted`
     Badge `flagged` + amber `38` · `hand edits` purple Badge `hand` + `14 kept`.
   - Divider; `Selection` (dashed-square icon). KeyValue: `recordings` 2 · `channels` `M2_aug fs1 CH3_A2,
     CH4_A2 · M3_jul CH2` · `hours` 128.4 h · `members` **412** · `reviewed` 26 %.
   - Amber callout (y 472–558): `⚠ CH3_A2 + CH4_A2 share ground for F-03` (amber bold) / `Browsing both
     double-counts that family.` / outline button `− Deselect CH4_A2`.
   - Bottom (y 735–790): primary `Browse 3 channels →`; blue links `Select all channels`, `Clear`.

### Controls & interactions
| control | kind | behaviour |
|---|---|---|
| `Find by shape` | Button | toast `not wired yet: shape query (sketch or span → nearest families)` |
| `Import` | Button | → `#/library/import` |
| `Export` | Button | toast `not wired yet: export grouping g-07 (families × channels CSV)` |
| (i) on title | InfoTip | P9 popover: reading rule + "cells are members per hour of recording; `?` means nobody has reviewed that channel, so absent and never-looked differ" |
| `per hour · count` | Seg | toggles cell text/ramp; `?cell=count` |
| `‹ recordings 1–3 of 5 ›` | pager | pages 3 recording groups at a time; ‹ disabled on page 1 (reason `first page`) |
| recording checkbox | Checkbox (tri-state) | selects/deselects all channels of that recording on this page; indeterminate when partial |
| channel checkbox | Checkbox | toggles column in selection; updates outline + rail totals; writes `?sel=` (replace, no history) |
| cell hover | tooltip | `F-03 · M2_aug fs1 · CH3_A2 · 27 members · 0.61 / h · cross-channel artifact (flagged)`; `?` cell: `no reviewed coverage on CH1 · no members found` |
| cell click | — | toggles that cell's channel selection (same as its column checkbox) |
| family row label | link | → `#/library/atlas?family=F-03` (keeps current scope) |
| `Send to Review as a queue` | link | toast queue `Library · g-07 omitted` · 38 |
| `Show all 38` | link | open Drawer omitted (`?drawer=omitted`) |
| omitted thumbnail | click | open Drawer omitted scrolled to that motif |
| `− Deselect CH4_A2` | Button | removes CH4_A2 from selection; callout hides |
| `Browse 3 channels →` | primary Button | label counts selected channels; → `#/library/atlas?scope=<sel>`; disabled with reason `select at least one channel` when 0 |
| `Select all channels` | link | selects every channel on the visible page (15) — shared-ground callouts for every pair in the fixture list |
| `Clear` | link | empties selection |

Shared-ground rule: fixture `sharedGround: [['M2_aug_fs1:CH3_A2','M2_aug_fs1:CH4_A2']]` (only pair that has
members of the same family in both — F-03 artifact cells). Callout text uses the family that is flagged
artifact on both.

### Plots
- **Recurrence matrix** (Raster/Matrix): x = channel columns grouped by recording (band scale with group
  gaps), y = families (band). Colour = quantize scale, 5 blues over [0, 1.0] members/h (frame domain;
  see Fog on reconciliation). Marks: cell rects, `?` cells, artifact cells, selection outlines. Legend
  under the plot. Cap P8: 10 family rows visible; more → row pager `families 1–10 of N ›` in the title row.
- **Row sparklines**: exemplar trace, 36 × 24, no axes, not normalised (shared y-scale across rows = the
  atlas mV domain).
- **Coverage bars**: 3 px, fraction of channel-hours reviewed.
- **Omitted thumbnails**: 12 on the strip (frame; P8 "~10" — accept 12, one row). Drawer: 10 per page.

### Fixtures
```ts
// shared canon (lives in shared fixture): Recording, Channel, Family colours/names
interface Recording { id: 'M2_aug_fs1'|'M2_aug_fs2'|'M3_jul'|'L_LM_Jul26_J'|'M4_aug'; label: string; fs: number; fsInferred?: boolean; channels: string[]; hours: number; start: string; heldOut?: boolean }
// §0: M2_aug fs1 1 Hz 16 ch 721 h start 2025-08-02 14:00; M2_aug fs2 2 Hz 721 h; M3_jul 1 Hz 8 ch 280 h;
//     L_LM_Jul26_J 10 Hz inferred 5 ch 22.4 h; M4_aug 1 Hz 16 ch 300 h heldOut+locked
interface Grouping { id: 'g-07'|'g-08'|'g-01'|'g-09'; unit: 'single motifs'|'sequences'|'spike trains'; basis: BasisKind; params: Record<string, number|string>; computedAt: string; motifs: number; families: number; omitted: number; handEditsKept: number; filters: string[] }
// g-07: single motifs · shape distance · Ward · cut 0.42 · 14 Sep 2026 · 1,402 motifs · 10 families · 38 omitted · 14 hand edits
interface RecurrenceRow { familyId: string; recordingsSpanned: number; cells: Record<string /*rec:ch*/, { perHour: number|null; count: number; artifact?: boolean; noCoverage?: boolean }> }
interface ChannelCoverage { key: string /*rec:ch*/; reviewedFraction: number }
interface RecordingCoverage { recording: string; reviewedPct: number } // M2_aug fs1 31, M3_jul 18, L_LM 5
interface OmittedMotif { id: string; nearestFamily: string; d: number; recording: string; channel: string; onsetH: number }  // 38 for g-07, all d > 0.50
```
Cell values (per hour, frame 1; `–` = reviewed, none; `?` = no coverage). Columns: M2_aug fs1 CH1_A1
CH2_A1 CH3_A2 CH4_A2 CH5_B1 CH6_B1 | M3_jul CH1–CH4 | L_LM CH1–CH5.
```
F-01 .70 .94 .21 .60 .65 .71 | – – – .17 | ? ? – – –
F-02 – – .18 .21 .21 .16 | .26 .68 .23 .88 | ? ? – – –
F-03 – – !.61 !.61 – – | .82 .80 .56 .23 | .54 .83 .76 .23 .94
F-04 .38 .65 .36 .43 .37 .94 | – .25 .24 – | ? ? – – –
F-05 .88 .55 .35 .70 .79 .38 | – – – .20 | ? ? – – –
F-06 – – .21 .14 – .16 | – – – – | ? ? – – –
F-07 .88 .60 .79 .75 .94 .30 | .20 – – .19 | .55 .67 .29 .97 .41
F-08 – .15 – .16 – – | – .25 .24 – | ? ? – – –
F-09 .63 .78 .47 .82 .35 .72 | .92 .67 .66 .28 | ? ? – – –
F-10 .53 .89 .90 .21 .73 .90 | – – – – | ? ? – – –
```
Coverage bars: M2 channels ≈ 0.31 each; M3_jul CH1 .20 CH2 .25 CH3 .10 CH4 .18; L_LM CH1 0, CH2 0, CH3–CH5 .08.
Family rows (id · name · recordings spanned): F-01 single drop 2 · F-02 fast burst 2 · F-03 sharkfin 3 ·
F-04 spike train 2 · F-05 slow ripple 2 · F-06 plateau 1 · F-07 slow drift 3 · F-08 long fall 2 · F-09
sharp peak 2 · F-10 notch 1. Colours from §0 D8.
Selection totals fixture (frame): recordings 2 · hours see conflicts · members 412 · reviewed 26 %.
Shared with other workspaces: recordings, channels, families (names, colours, exemplar/medoid ids),
grouping id g-07 (Settings › Library groupings), review queues.

### Copy
Header subtitle `recurrence · grouping g-07`. Title `Where each family occurs`. Pager `recordings 1–3 of 5`.
Legend `members / h`, `0 → 1.0`, `no reviewed coverage`, `cross-channel artifact, kept visible`, `selected`.
Caption `dark in one recording and empty in the others → a property of that recording, not of the organism`.
Strip `38 motifs fit no family in this grouping` / `nearest family d > 0.50 · left out of counts, not deleted`
/ `Send to Review as a queue` / `Show all 38`. Rail `This grouping`, `Selection`, `CH3_A2 + CH4_A2 share
ground for F-03`, `Browsing both double-counts that family.`, `Deselect CH4_A2`, `Browse 3 channels →`,
`Select all channels`, `Clear`.

### Frame ⟷ spec conflicts
1. **M2_aug fs1 hours**: frame caption `45.2 h · 31% reviewed`; §0 says **721 h**. Use `721 h · 31% reviewed`
   (canon wins; backlog line 195 already moved M3_jul to 280 h but missed M2).
2. **Selection hours** `128.4 h` reconciles with nothing (not 721×2+280 channel-hours = 1,722 h, not
   721+280 recording-hours = 1,001 h). Recommend computing from fixtures as channel-hours (`1,722 h`) and
   labelling the row `channel-hours`; flag for the user.
3. **Reading rule on the page**: P9 says explanatory text sits behind info icons; the frame shows both the
   (i) on the title *and* the caption line. Keep both (the caption is one line, which P9 allows).
4. **Only 6 of M2_aug fs1's 16 channels are drawn** (CH1_A1–CH6_B1). §8.4 says families × channels; see Fog 2.
5. **Omitted strip shows 12 thumbnails**; P8 caps show-all views at ~10. Keep 12 (one row, "~"), cap the drawer at 10/page.

### Fog
1. **Per-hour values do not reconcile with member counts.** F-03 has 112 members, yet 0.61/h on CH3_A2
   over 721 h would be ≈ 440 members on one channel. Recommendation: per-hour mode shows the frame values
   verbatim (design target); `count` mode shows a separate fixture `count` whose three scope-channel values
   equal the atlas in-scope split (below), others small seeded integers. Flag for a B28-style fix.
2. **16-channel recordings do not fit 3-per-page.** M2_aug fs1 (16 ch) + M3_jul (8 ch) + L_LM (5 ch) = 29
   columns × 42 px = 1,218 px > 950 px available. Frame shows 6 / 4 / 5. Recommendation: per recording show
   only channels with members or reviewed coverage in this grouping, plus a collapsed `+10 channels, no
   members` column that expands in place; M3_jul shows CH1–CH4 `+4`. Needs user decision.
3. **Recordings 4–5 of 5** = `M2_aug fs2` (a resample of fs1 — B30 says scopes must not mix fs1/fs2) and
   `M4_aug` (held out, locked, D6). Recommendation: M4_aug group renders a LockedCard column block `held out
   · locked in Settings › Datasets` with no cells; M2_aug fs2 renders cells but its channel checkboxes are
   DisabledReason `fs2 resamples M2_aug fs1 — already selectable as fs1` while any fs1 channel is selected.
4. The spec's "`?` when no reviewed coverage **and** no members" — a cell with members but zero coverage
   (F-03, F-07 on L_LM CH1/CH2) shows the value; frame agrees. No extra marker for "members, never
   reviewed" — possible gap.
5. Shared-ground pairs are channel metadata from Settings › Channels & events; the family naming in the
   callout ("for F-03") implies the warning is per family, which the data model does not obviously hold.

---

## library.atlas

### Route & states
- `motifs` (frame 2): `#/library/atlas` — grouping g-07, scope = store selection (default canon 3
  channels), rail = F-03. Deep link `#/library/atlas?unit=motifs&scope=M2_aug_fs1:CH3_A2,M2_aug_fs1:CH4_A2,M3_jul:CH2&family=F-03`.
  Reached by *Browse 3 channels →* (recurrence), breadcrumb `Atlas`, or a family row label.
- `sequences` (frame 2b): unit Seg `sequences` in the grouping bar, or picking g-08 in the Groupings
  popover, or `?unit=sequences&family=S-02`. Scope is **cleared** (spec §8.2 "Apply … clears the scope");
  no scope row; amber banner instead.
- `family-selected` (both frames): clicking a card moves the rail and writes `?family=` (replace). With no
  `family` param the first card in sort order is selected.
- `no-scope` (derived): removing every scope chip, or `?scope=all`; scope row shows a grey chip
  `all recordings` and caption `10 families · 1,364 members` (see Fog 1); card counts read `140 members`.
- `omitted-drawer` (derived): omitted chip / *Show omitted* / `?drawer=omitted`.
- `resampled` (derived): rail *resample* redraws the 10 sampled members with a new seed (kept in memory).
- `empty` (derived): `?library=empty`.

### Regions — `motifs` (frame 2)
1. Header, section toolbar (breadcrumb `Recurrence › Atlas`; actions `Find by shape`, `Import`, `Export`),
   grouping bar (g-07) — see Shared chrome.
2. **Scope row** y 160–187, x 78–1042 (no card): muted `scope`; three removable blue chips
   `M2_aug fs1 · CH3_A2 ×`, `M2_aug fs1 · CH4_A2 ×`, `M3_jul · CH2 ×`; blue link `‹ back to recurrence`;
   mono muted `10 families · 412 members in scope`; right, borderless Select `sort: members in scope ˅`.
3. **Card grid** x 78–1042, y 205–795: 4 columns (card 232 × 190, gap 12), rows at y 205 / 405 / 605;
   10 cards (4 + 4 + 2). Card:
   - title row: `F-01` (family colour, mono bold) + name (bold); right mono muted `61 of 140` (in scope of total);
   - badge row: `3 rec` (light blue; grey `1 rec` when 1), `3 hand` (purple), `artifact 2` (red);
   - plot 190 × 92 on light-grey ground, left axis labels `+0.4`, `mV`, `−0.4`, thin zero line; exemplar
     black 1.5 px + medoid family colour 1.5 px;
   - footer: mono `1.2 s  −0.34 mV` (duration, depth), judged bar 48 × 4 (green fill over amber-tint
     remainder) + mono `52% judged`.
   - selected card: 2 px blue border (F-03).
   - Legend to the right of row 3 (x 565–1040, y 611): black swatch `exemplar (human seed)`, grey swatch
     `medoid (computed, family colour)`, muted `shared mV scale on every card`.
4. **Detail rail** x 1058–1374, y 155–848 (one card):
   - `F-03` (family colour) + `sharkfin` bold 15 px; right light-blue chip `3 recordings`.
   - mono caption `112 members · 44 in scope · 3 hand edits`.
   - Plot "exemplar vs medoid" 280 × 100 (y 207–307): `+0.4 mV`, `−0.4`, x `0` … `21 s`.
   - legend `— exemplar E-0102  — medoid m-1846` + green chip `d 0.07`.
   - row `members · shared y · mV` · muted `10 of 44 sampled` · blue `⤮ resample`; overlay plot 280 × 76.
   - `peak-to-peak amplitude` + muted right `n per bin`; histogram 280 × 60, 12 bars (lilac; modal bar in
     family colour), ticks `0.1` `0.25` `0.4 mV`.
   - KeyValue: `duration` 21 s ± 4 · `mean member d` 0.24 · `SNR` 18.4 dB · `judged` amber `44 of 112` ·
     `channels` chips red `artifact 2`, amber `prop. 4`, green `ind. 1` · `edges` mono `z-norm Euclid · cut 0.42 · a7f3…9c`.
   - Actions (y 678–830): primary `Open all 112 members →`; outline `Seed search in Discovery →` (radar
     icon), `Interrogate in Analyse →` (chain icon), `Send 68 unjudged to Review →` (list-check icon); blue
     link `⤴ Export entry`.

### Regions — `sequences` (frame 2b), deltas from frame 2
1. Header subtitle `atlas · grouping g-08 · sequences`. Grouping bar: Seg `sequences` active; basis chip
   `by cut 0.50  sequence similarity ˅`; chips `adjudicated only`, `≥ 10 members`, `artifact flagged` (no
   `+ filter`); amber `1,035 omitted · flagged`; `Edit grouping`.
2. **Amber banner** (replaces the scope row) y 155–187, x 78–1042, amber-tint fill: flag icon + mono
   `Sequences only: 1,018 motifs in no sequence and 17 sequences that fit no family are left out of this
   round, not deleted.`; right blue link `Show omitted`.
3. **Card grid** 3 columns (card 313 × 206, gap 12), rows y 200 / 416; 6 cards. Card: `S-01` (colour) +
   name; right `34 sequences`; badges: composition chip (lilac) `F-01 · F-01 · F-01` or `F-02 × 4`, `3 rec`,
   `1 hand`; plot 270 × 105 (±0.4 mV, exemplar black + medoid colour); footer mono `~38 s  gaps 12 s ± 3` +
   judged bar + `41% judged`. Selected S-02 (blue border).
4. **Omitted card** x 78–1042, y 637–798: flag `Omitted from this round`; right link `Send omitted to Review
   as a queue`. Two halves: left `1,018 single motifs · not part of any sequence`, 7 amber thumbs (62 × 44),
   caption `switch the unit to single motifs to group these`; right `17 sequences · nearest family d > 0.50`,
   5 wider amber thumbs (86 × 44), caption `re-cut at a looser threshold, or leave them flagged`.
5. **Detail rail**: `S-02` + `sharkfin → peak`; chip `2 recordings`; caption `21 sequences · 42 motifs ·
   exemplar E-0311`; exemplar-vs-medoid plot (`0` … `22 s`); legend `— exemplar  — medoid` + `d 0.11`;
   `composition` — CompositionStrip on a pink band: box `F-03` —— `14 s ± 2` —— box `F-09`; KeyValue
   `order kept` 19 of 21 · `gap between events` 14 s ± 2 · `mean member d` 0.31 · `judged` amber `23 of 42
   motifs`; row `members, aligned on first event` + `⤮ resample`, overlay plot 280 × 66 (pink, ~6 members);
   actions: primary `Open all 21 sequences →`; **disabled** `Seed search in Discovery` + InfoTip `needs
   multi-seed`; `Interrogate in Analyse →`; `Send 21 unjudged motifs to Review →`; link `Export entry`.
   No amplitude histogram, SNR or channels rows for sequences.

### Controls & interactions
| control | kind | behaviour |
|---|---|---|
| scope chip `×` | Chip (removable) | removes channel from store selection (shared with recurrence); in-scope counts recompute from the split fixture; caption updates |
| `‹ back to recurrence` | link | → `#/library/recurrence` (selection preserved) |
| `sort: members in scope` | Select | options `members in scope`, `family id`, `judged fraction`, `duration`, `hand edits`; in-memory reorder |
| card | click / Enter | select → rail; `?family=` replace. Double-click → `#/library/family/<id>` (motifs only) |
| card badge `3 hand` | Chip | → `#/library/family/F-03?hand=1` |
| card badge `artifact 2` | Chip | InfoTip `2 channels where F-03 is a cross-channel artifact (flagged, kept)` |
| rail `resample` | link-button | new seed for the 10-member sample (P8) |
| rail histogram bar | hover | tooltip `0.22–0.25 mV · 23 members` |
| rail channels chips | Chip | InfoTip: `artifact` = cross-channel artifact, `prop.` = propagated copy on a neighbouring channel, `ind.` = independent occurrence (see Fog 4) |
| `Open all 112 members →` | primary | → `#/library/family/F-03` |
| `Open all 21 sequences →` | primary | → `#/library/family/S-02` (sequence family page; see Fog 5) |
| `Seed search in Discovery →` | Button | → `#/discovery/seed?seed=E-0102&family=F-03` (Discovery inventory owns the route; seed = exemplar, medoid alternative per §8.5) |
| `Seed search in Discovery` (sequences) | DisabledReason | reason `needs multi-seed — no seed-search algorithm takes several seeds yet (§7.6)` |
| `Interrogate in Analyse →` | Button | → `#/analyse/interrogation?source=family:F-03` (Analyse inventory owns the route; frame interrogation-1) |
| `Send 68 unjudged to Review →` | Button | toast queue `Library · F-03 unjudged` · 68 |
| `Export entry` | link | toast `not wired yet: export library entry F-03 (exemplar, medoid, members CSV, provenance)` |
| `Show omitted` / omitted chip | link / Chip | Drawer omitted (two tabs in sequences: `1,018 single motifs` · `17 sequences`) |
| `Send omitted to Review as a queue` | link | toast queue `Library · g-08 omitted` · 1,035 |
| omitted caption `switch the unit to single motifs` | (text) | make `single motifs` a link → switch to g-07 |
| keyboard | — | ←/→/↑/↓ move card selection; Enter opens family (matches Review's grid feel; not drawn) |

### Plots
- **Card plot** (Trace, ×10 motif cards, ×6 sequence cards): x = seconds from motif onset (0 → family
  duration), no x ticks on cards; y = **detrended mV on one shared domain for every card on the page**
  (frame labels ±0.4 mV); marks: exemplar line (black), medoid line (family colour), zero line. Never
  normalised (D5). This is the density test: 10 cards × 2 traces + rail 2 traces + rail overlay 11 traces
  + histogram — all on the same y-scale object.
- **Rail exemplar vs medoid** (Trace): x 0 → 21 s ticks at ends; y ±0.4 mV labelled; same shared domain.
- **Rail member overlay** (SmallMultiples overlay mode): 10 sampled members (family colour, 40 % opacity)
  + medoid (black); P8 cap 10 with *resample* (seeded).
- **Amplitude histogram** (Histogram): x peak-to-peak mV (0.1 → 0.4), y n per bin (no axis ticks drawn;
  add on hover), 12 bins; fixture = F-03 member amplitudes.
- **Sequence composition** (CompositionStrip): events as family-coloured boxes on a time line with gap
  labels `mean s ± sd`.
- **Sequence member overlay**: members aligned on first event, ≤ 10 with resample.
- **Omitted thumbnails** (MotifThumb, amber): 7 + 5 on the card; drawer 10 per page.

### Fixtures
```ts
interface FamilySummary {            // shared canon for F-03, F-04, F-07, F-11 (Review, Discovery, Analyse use them)
  id: string; name: string; colour: string; unit: 'single'|'sequence'
  members: number; recordingsSpanned: number; exemplarId: string; exemplarOrigin: 'human seed'; medoidId: string
  durationS: number; durationSdS?: number; depthMv: number; depthSign: '+'|'−'|'±'; judged: number; handEdits: number
  artifactChannels: number; propagatedChannels: number; independentChannels: number
  exemplarMedoidD: number; meanMemberD: number; snrDb?: number; edges: { metric: string; cut: number; recipeHash: string }
  inScopeByChannel: Record<string /*rec:ch*/, number>
  trace: { exemplar: number[]; medoid: number[]; fs: number }   // synthetic, seeded; mV
}
interface SequenceFamily extends Omit<FamilySummary,'snrDb'|'artifactChannels'|'propagatedChannels'|'independentChannels'> {
  sequences: number; motifs: number; composition: string[] /* ['F-03','F-09'] */; compositionLabel: string /* 'F-02 × 4' */
  gapS: { mean: number; sd: number }; orderKept: number
}
```
Motif families (g-07; in-scope · total · rec · hand · artifact · duration · depth · judged %):
F-01 single drop 61·140·2*·0·0·1.2 s·−0.34·52 | F-02 fast burst 22·42·2·0·0·0.8 s·±0.45·31 |
**F-03 sharkfin 44·112·3·3·2·21 s·±0.21·39** | F-04 spike train 37·58·2·0·0·4.2 s·−0.11·62 |
F-05 slow ripple 31·49·2·0·0·3.8 s·+0.65·20 | F-06 plateau 12·26·1·0·0·4.6 s·+0.31·75 |
**F-07 slow drift 58·212·3·1·0·38 s·±0.08·12** | F-08 long fall 19·22·2·0·0·44 s·−0.52·45 |
F-09 sharp peak 71·96·2·0·0·0.9 s·+0.48·66 | F-10 notch 57·81·1·0·0·2.1 s·−0.27·8.
(*frame card says `3 rec`; recurrence says 2 — use 2, see conflicts.) In-scope sum 412 ✓.
In-scope split across the three scope channels: proportional to the frame-1 per-hour cells on those
channels (blank = 0), rounded so each family's sum is exact. E.g. F-03 44 → CH3_A2 11, CH4_A2 11, M3_jul CH2 22.
F-03 rail: exemplar `E-0102` (human seed), medoid `m-1846`, d 0.07, duration 21 s ± 4, mean member d 0.24,
SNR 18.4 dB, judged 44 of 112, unjudged 68, channels artifact 2 · prop. 4 · ind. 1, edges `z-norm Euclid ·
cut 0.42 · a7f3…9c`, amplitude histogram 12 bins over 0.10–0.40 mV peaking at 0.22–0.25.
Sequence families (g-08; sequences · composition · rec · hand · ~duration · gap · judged %):
S-01 drop triplet 34 · F-01·F-01·F-01 · 3 · 0 · ~38 s · gaps 12 s ± 3 · 41 | **S-02 sharkfin → peak 21 ·
F-03·F-09 · 2 · 0 · ~22 s · gap 14 s ± 2 · 52** | S-03 burst run 18 · F-02 × 4 · 2 · 1 · ~30 s · gaps 6 s ± 1 · 28 |
S-04 ripple then fall 10 · F-05·F-08 · 1 · 0 · ~70 s · gap 31 s ± 9 · 67 | S-05 peak pair 27 · F-09·F-09 · 2 ·
0 · ~11 s · gap 8 s ± 1 · 59 | S-06 notch train 12 · F-10 × 5 · 1 · 0 · ~52 s · gaps 10 s ± 4 · 17.
Sequence colours: S-0n uses family palette slot F-0n. S-02 rail: 42 motifs, exemplar `E-0311`, d 0.11,
order kept 19 of 21, mean member d 0.31, judged 23 of 42. g-08: cut 0.50, 6 families, omitted 1,035 =
1,018 single motifs + 17 sequences.
Shared: families F-01…F-10 names/colours (F-11 `burst` exists in canon but is not in g-07 — keep it in
the shared fixture for other workspaces), exemplar/medoid ids, groupings.

### Copy
Subtitles `atlas · grouping g-07 · 3 channels` / `atlas · grouping g-08 · sequences`. `scope`,
`‹ back to recurrence`, `10 families · 412 members in scope`, `sort: members in scope`, `61 of 140`,
`3 rec`, `3 hand`, `artifact 2`, `52% judged`, `exemplar (human seed)`, `medoid (computed, family colour)`,
`shared mV scale on every card`, `112 members · 44 in scope · 3 hand edits`, `exemplar E-0102`,
`medoid m-1846`, `d 0.07`, `members · shared y · mV`, `10 of 44 sampled`, `resample`,
`peak-to-peak amplitude`, `n per bin`, `duration`, `mean member d`, `SNR`, `judged`, `channels`, `prop. 4`,
`ind. 1`, `edges`, `Open all 112 members →`, `Seed search in Discovery →`, `Interrogate in Analyse →`,
`Send 68 unjudged to Review →`, `Export entry`. Sequences: banner text above, `34 sequences`,
`gaps 12 s ± 3`, `Omitted from this round`, `Send omitted to Review as a queue`,
`1,018 single motifs · not part of any sequence`, `17 sequences · nearest family d > 0.50`,
`switch the unit to single motifs to group these`, `re-cut at a looser threshold, or leave them flagged`,
`21 sequences · 42 motifs · exemplar E-0311`, `composition`, `order kept`, `gap between events`,
`members, aligned on first event`, `Open all 21 sequences →`, `needs multi-seed`,
`Send 21 unjudged motifs to Review →` (see conflict 4).

### Frame ⟷ spec conflicts
1. **Shared y-domain vs stated depths.** Cards are labelled ±0.4 mV, yet F-05 is `+0.65 mV`, F-08 `−0.52 mV`,
   F-02 `±0.45 mV`, F-09 `+0.48 mV` — they would clip. D5 (never normalise, shared scale) is load-bearing;
   the tick label is not. Recommend: generate fixture traces that match their stated depth and compute one
   nice domain across every card in view (→ ±0.7 mV). Critic should accept ±0.7 labels. Alternative if the
   user prefers the frame look: clamp fixture depths to ≤ 0.4 and edit the copy.
2. **F-01 `3 rec`** on the atlas card vs `2 recordings` on recurrence (§8.4 row count). Use 2 (its third would
   be M2_aug fs2, the same recording — B30).
3. **Sort label vs order**: sort reads `members in scope`, but cards are in id order (F-09 with 71 would be
   first). Recommend the Select default to `family id` with the label `sort: family id`, or apply the sort
   and accept a different card order from the frame. Flag.
4. **S-02 unjudged**: rail says judged `23 of 42 motifs` but the button says `Send 21 unjudged motifs`
   (42 − 23 = 19). Use `Send 19 unjudged motifs to Review →`.
5. **Composition colours**: rail composition boxes draw F-03 purple and F-09 pink; D8 says family colours
   (F-03 #30B0C7, F-09 #F4A6C8). Use family colours; card composition chips stay neutral lilac.
6. **Judged bar colour**: F-06's bar is light blue; all others green. Use green (colour semantics §3).
7. **Spec §8.2 says 1,188 single motifs omitted** in the sequences grouping; frame and backlog (line 196)
   say 1,018 (reconciles: 1,402 − 384 motifs in sequences). Use 1,018 / 1,035; spec text is stale.
8. **Depth word**: spec §8.5 lists `depth`; frame footers show a signed amplitude (`±0.21 mV`). Keep the
   frame value, label it `depth` in the tooltip.

### Fog
1. **Family totals do not sum to the catalogue.** 140+42+112+58+49+26+212+22+96+81 = 838; + 38 omitted = 876,
   not 1,402. Perhaps the `≥ 10 members` filter hides small families (526 motifs) — but the rail says
   `families 10` and nothing is shown as hidden. Recommend: add a muted line under the grid `+ N small
   families hidden by ≥ 10 members` only if the user confirms; otherwise flag and use frame numbers.
2. **Sequence arithmetic**: S-03 `F-02 × 4` × 18 sequences needs 72 F-02 motifs but F-02 has 42; S-02 `~22 s`
   cannot hold a 21 s sharkfin + 14 s gap + a peak. Frame numbers used; flag (B28 class).
3. What `in scope` means for the rail's `judged 44 of 112` (whole family) vs `44 in scope` — identical
   numbers by coincidence in the frame; builders must keep them as separate fields.
4. `prop.` / `ind.` channel chips are not defined in the spec (cross-channel counts, §8.5). Glossary above is
   a guess; confirm.
5. **Sequence family page**: *Open all 21 sequences →* implies a family page for sequences; frame 3 only
   draws a single-motif family. Recommendation: same route `#/library/family/S-02` with member cards drawing
   a sequence (composition strip + aligned trace) — builders may ship an EmptyState `sequence family page
   not drawn yet` with the list of 21 sequence ids instead.
6. `spike trains` unit has no frame and no saved grouping (B17 says a spike-train unit is undefined).

---

## library.family

### Route & states
- `#/library/family/<familyId>` — canonical `F-03`. Unknown id → EmptyState `No family <id> in grouping
  g-07` with link `‹ back to atlas`. A family absent from the current grouping but present in another →
  EmptyState naming that grouping with a switch link.
- `member-selected` (frame 3): rail shows `m-1850`; checkboxes E-0102, m-1843, m-1850 ticked; batch bar
  `3 selected`. Deep link `#/library/family/F-03?member=m-1850&sel=E-0102,m-1843,m-1850`. Reached from atlas
  *Open all 112 members →*, then clicking cards / ticking boxes.
- default (derived): no `member` → rail shows the first card (medoid m-1846); no selection → batch bar
  replaced by muted hint `tick members to act on several`.
- `sort-<key>` (derived): Seg `distance to medoid` (default) · `time` · `amplitude` · `unjudged first`; `?sort=`.
- `hand-only` (derived): toggle `hand edits only` / `?hand=1` → only m-1850 (added) is listed; removed strip stays.
- `page-n` (derived): pager / `?page=2` → `11–20 of 112`.
- `revisions-popover` (derived): click rail `revisions` value / `?popover=revisions`.
- `confirm-remove` / `confirm-make-exemplar` (derived): Modal, `?modal=remove` / `?modal=make-exemplar`.
- `tag-popover`, `class-select-open` (derived).
- `all-judged` (derived, e.g. F-06 at 75 %… or any family with 0 unjudged): amber banner hidden.

### Regions
1. Header, section toolbar (breadcrumb `Recurrence › Atlas › F-03 sharkfin`; right, the only action:
   outline `⤴ Export entry`), grouping bar (g-07).
2. **Unjudged banner** y 155–190, x 78–1042, amber-tint fill: orange dot, bold `68 of 112 members have never
   been judged`, amber mono `a family of unjudged members is a proposal, not a finding`; right filled orange
   button (list icon) `Send 68 to Review as a queue →`.
3. **Summary card** y 200–342, x 78–1042 (white): three zones —
   - left plot 300 × 125 (x 90–380): exemplar (black) vs medoid (family colour); labels `+0.4 mV`, `−0.4`,
     x `0`, `21 s`;
   - middle (x 392–790): legend `— exemplar E-0102 (seed)  — medoid m-1846` + green chip `d 0.07`; two
     KeyValue columns — `members` **112** · `recordings` 3 · 5 channels · `judged` amber `44 of 112` ·
     `hand edits` purple `2 added · 1 removed` | `mean member d` 0.24 · `duration` 21 s ± 4 · `depth`
     0.21 mV ± 0.05 · `cross-channel` artifact 2;
   - right overlay 222 × 125 (x 806–1030): muted `10 of 112 sampled`, blue `resample`; 10 members (family
     colour, light) + medoid (black).
4. **Sort row** y 355–380: muted `sort`, Seg `distance to medoid · time · amplitude · unjudged first`, toggle
   button (hand icon) `hand edits only`; right: Checkbox `select page`, pager `‹  1–10 of 112  ›`.
5. **Member grid** y 390–690: 5 columns × 2 rows, card 185 × 145, gap 10. Card: Checkbox + id (mono bold)
   + right `d 0.12` (mono; **purple when d > cut 0.42**); optional badge (`medoid` lilac, `exemplar` green,
   `added by hand` purple); trace 165 × 55 on grey ground (black; red when verdict artifact); mono muted
   `CH4_A2 · 121.4 h`; verdict line: amber text `unjudged`, or dot + word (`● seed` green, `● interesting`
   green, `● not interesting` grey, `● artifact` red). Rail-selected card: 2 px blue border + light-blue fill.
   Under grid, muted mono `shared mV scale · ±0.4 mV · 21 s`.
6. **Removed-by-hand strip** y 708–763, x 78–1042: hand icon + bold `Removed by hand · 1`, caption `kept out
   when F-03 is regrouped`; a thumbnail (62 × 40); mono `m-1902 · d 0.39 · CH3_A2 · removed 13 Sep ·
   “propagated copy”`; right blue `↺ Restore`.
7. **Batch bar** y 775–820, x 78–1042 (white card): bold `3 selected`; right outline buttons `Send to Review`
   (list icon), `Add tag` (tag icon), `Assign class` (shapes icon), `Remove from family` (user-minus),
   `Export` (upload).
8. **Member rail** x 1058–1374, y 155–848:
   - `m-1850` (bold mono) + purple badge `added by hand`; right purple mono `d 0.47`.
   - Plot 280 × 100: member (black) over medoid (family colour), `+0.4 mV`, `−0.4`, `0`, `21 s`.
   - Context strip 280 × 36: ±30 s of signal around the span, the span shaded blue; labels `−30 s`, `+30 s`.
   - KeyValue: `recording · channel` M2_aug fs1 · CH4_A2 · `onset · duration` 196.6 h · 1.62 s (see conflict) ·
     `found by` r-0415 seed search.
   - Purple hand-edit record box: hand icon `added to F-03 · this installation · 14 Sep` + blue `Undo`
     (frame truncates to `Und`); second line mono `d 0.47 is past the cut; kept in F-03 when regrouped`.
   - `revisions` mono `rev 1 machine d-88402 · rev 2 edited`.
   - `verdict` green dot `interesting · 12 Sep` + blue `Open in Review` (read-only, P6).
   - `tags` chips `sharkfin` (blue), `clean` (grey), dashed `+ tag`.
   - `class` Select `burst`.
   - note TextArea (grey) `rise starts before the window does`.
   - Bottom actions (y 775–835): outline `☆ Make exemplar`, outline `✎ Redraw in Explore`; red-outline
     `Remove from family`.

### Controls & interactions
| control | kind | behaviour |
|---|---|---|
| `Export entry` | Button | toast `not wired yet: export library entry F-03` |
| `Send 68 to Review as a queue →` | Button (amber primary) | toast queue `Library · F-03 unjudged` · 68; in-memory flag `queued` shows chip `queued as Library · F-03 unjudged` in the banner |
| summary `resample` | link-button | new seeded 10-of-112 sample |
| `hand edits` value | link | same as `hand edits only` toggle |
| sort Seg | Seg | in-memory reorder of all 112 members (`time` = onset h; `amplitude` = peak-to-peak desc; `unjudged first` then distance) |
| `hand edits only` | toggle Button | filters to hand-edited members; pager recomputes `1–1 of 1` |
| `select page` | Checkbox (tri-state) | ticks/unticks the 10 visible cards |
| pager ‹ › | icon Buttons | 10 per page (P8); ‹ disabled on page 1 |
| card checkbox | Checkbox | toggles selection (persists across pages; count in batch bar) |
| card body | click | rail → that member; `?member=` replace. Keyboard ←/→ moves rail member |
| `Restore` | link-button | in-memory: m-1902 back into members (113), strip hides, hand edits `2 added · 0 removed`; toast `Restored m-1902 · not wired yet: DELETE hand edit` |
| batch `Send to Review` | Button | toast queue `Library · F-03 selection` · N |
| batch `Add tag` | Popover | TagInput: text, rule `lowercase letters, digits, hyphen; 2–32 chars` (message `tags are lowercase words, 2–32 characters`); suggestions from Settings vocabulary fixture (`sharkfin`, `biphasic`, `clean`, `noisy`); Apply → chips added in memory, each badged `hand` |
| batch `Assign class` | Popover | radio list of classes with keys `1 spike-train · 2 burst · 3 slow-drift · 4 plateau · 9 electrode artifact`; digit keys pick; Apply in memory |
| batch `Remove from family` | Modal confirm | `Remove 3 members from F-03?` / `They stay out of F-03 on every regroup until restored. Verdicts are untouched.` / `Cancel` · red `Remove 3`; in-memory move to Removed strip |
| batch `Export` | Button | toast `not wired yet: export 3 members (CSV + spans)` |
| rail `Undo` (hand-edit record) | link-button | in-memory: m-1850 leaves F-03 → list 111, rail moves to next card, hand edits `1 added · 1 removed`; toast `Undone · not wired yet: DELETE hand edit` with `Redo` action |
| rail `revisions` value | Popover | Table `rev · span · origin · run · role`: `1 · d-88402 · machine · r-0415 · what re-runs match` / `2 · a-2091 · human edit · — · current`; caption `a human edit writes a new annotation; the detection stays on its run (§4.2)` |
| rail `Open in Review` | link | → Review candidate route for this member (Review inventory owns it, e.g. `#/review/candidate/m-1850`) |
| rail tag chip | Chip (removable on hover ×) | in-memory remove; badge `hand` |
| rail `+ tag` | Popover | same TagInput as batch |
| rail `class` | Select | classes as above + `— none`; in-memory write; small `saved` tick |
| rail note | TextArea | max 500 chars (counter appears at 450); saves on blur in memory |
| `Make exemplar` | Modal confirm | `Make m-1850 the exemplar of F-03?` / `E-0102 (seed) stays a member. The exemplar is the human anchor; the medoid m-1846 is still computed.` / `Make exemplar`; in-memory badge swap, summary legend updates, hand edit `exemplar` recorded. Disabled with reason `already the exemplar` on E-0102, `artifact verdict — cannot anchor a family` on m-1847 |
| `Redraw in Explore` | Button | → `#/explore/span-edit/<spanId>?from=library/family/F-03&member=m-1850` (Explore inventory route; span id = current revision) |
| rail `Remove from family` | Modal confirm (red) | single-member variant of the batch modal |
| keyboard | — | `Space` toggles selection of rail member; `Esc` clears selection (not drawn; InfoTip on batch bar) |

### Plots
- **Exemplar vs medoid** (Trace): x 0–21 s, y ±0.4 mV (family shared domain), 2 lines.
- **Sampled overlay** (SmallMultiples overlay): 10 of 112 members + medoid; resample (P8).
- **Member cards** (Trace ×10 per page): shared domain ±0.4 mV · 21 s window (caption states it); line colour
  black, red for artifact verdict.
- **Removed strip thumbnail** (MotifThumb).
- **Rail member over medoid** (Trace, 2 lines) and **context strip** (Trace ±30 s around onset with a BandStrip
  highlight of the span). y in mV, not normalised.

### Fixtures
```ts
type Verdict = 'unjudged'|'seed'|'interesting'|'not interesting'|'artifact'
interface Revision { rev: number; spanId: string /* d-… detection | a-… annotation */; origin: 'machine'|'human edit'; runId?: string; role: 'what re-runs match'|'current'|'superseded' }
interface HandEdit { id: string; kind: 'add'|'remove'|'exemplar'|'tag'|'class'; memberId: string; familyId: string; actor: 'this installation'; at: string; note?: string }
interface Member {
  id: string; familyId: 'F-03'; role?: 'exemplar'|'medoid'; addedByHand?: boolean; removedByHand?: boolean
  d: number; recording: string; channel: string; onsetH: number; durationS: number; amplitudeMv: number
  verdict: Verdict; verdictAt?: string; foundBy: string /* 'r-0415 seed search' | 'run #128 drop_motifs9' */
  revisions: Revision[]; tags: string[]; class?: 'spike-train'|'burst'|'slow-drift'|'plateau'|'electrode artifact'; note?: string
  traceSeed: number
}
```
Page 1 (distance sort), exactly as drawn:
| id | d | badge | channel · onset | verdict | ticked |
|---|---|---|---|---|---|
| m-1846 | 0.00 | medoid | CH4_A2 · 121.4 h | unjudged | |
| E-0102 | 0.07 | exemplar | CH3_A2 · 112.0 h | seed | ✓ |
| m-1843 | 0.12 | | CH3_A2 · 130.8 h | unjudged | ✓ |
| m-1844 | 0.14 | | CH3_A2 · 140.2 h | interesting | |
| m-1845 | 0.16 | | CH4_A2 · 149.6 h | unjudged | |
| m-1847 | 0.21 | | CH3_A2 · 168.4 h | artifact (red trace) | |
| m-1848 | 0.23 | | CH4_A2 · 177.8 h | unjudged | |
| m-1849 | 0.25 | | CH4_A2 · 187.2 h | interesting | |
| m-1852 | 0.31 | | CH3_A2 · 215.4 h | not interesting | |
| m-1850 | 0.47 | added by hand | CH4_A2 · 196.6 h | interesting · 12 Sep | ✓ (rail) |
All on M2_aug fs1. m-1850: found by `r-0415 seed search`, revisions rev 1 machine `d-88402` · rev 2 edited
(annotation id not in frame — use `a-2091`, invented), hand edit `added to F-03 · this installation · 14 Sep`,
tags `sharkfin`, `clean`, class `burst`, note `rise starts before the window does`.
m-1846 revisions per §4.2 canon: rev 1 `d-0412` run `#128` machine (what re-runs match) · rev 2 `a-2077`
human edit (current).
Removed: `m-1902` d 0.39 CH3_A2 removed 13 Sep note `propagated copy`.
Remaining 102 members (pages 2–12): seeded generator — ids `m-1853…`, d ascending 0.31–0.60 (none past
0.42 except hand-added), spread over M2_aug fs1 (CH3_A2, CH4_A2), M3_jul (CH1–CH4) and L_LM_Jul26_J
(CH1–CH5) to match recurrence; verdict totals must hit **44 judged / 68 unjudged**; 2 artifact.
Family stats: 112 members, 3 recordings, judged 44, hand edits 2 added · 1 removed, mean member d 0.24,
duration 21 s ± 4, depth 0.21 mV ± 0.05, cross-channel artifact 2, exemplar–medoid d 0.07, cut 0.42.
Shared: F-03 identity (§0: sharkfin, 112 members, 3 recordings, exemplar E-0102 human seed, medoid m-1846,
~21 s), classes and keys, verdict vocabulary, r-0415 (Discovery seed search), actor `this installation`,
review queue naming.

### Copy
Subtitle `F-03 sharkfin · grouping g-07`. Breadcrumb `F-03 sharkfin`. Banner `68 of 112 members have never
been judged` / `a family of unjudged members is a proposal, not a finding` / `Send 68 to Review as a queue →`.
`exemplar E-0102 (seed)`, `medoid m-1846`, `members`, `recordings`, `3 · 5 channels`, `judged`, `hand edits`,
`2 added · 1 removed`, `mean member d`, `duration`, `depth`, `cross-channel`, `artifact 2`, `10 of 112
sampled`, `resample`, `sort`, `distance to medoid`, `time`, `amplitude`, `unjudged first`, `hand edits only`,
`select page`, `1–10 of 112`, `medoid`, `exemplar`, `added by hand`, `unjudged`, `seed`, `interesting`,
`not interesting`, `artifact`, `shared mV scale · ±0.4 mV · 21 s`, `Removed by hand · 1`, `kept out when F-03
is regrouped`, `Restore`, `3 selected`, `Send to Review`, `Add tag`, `Assign class`, `Remove from family`,
`Export`. Rail: `recording · channel`, `onset · duration`, `found by`, `added to F-03 · this installation ·
14 Sep`, `Undo`, `d 0.47 is past the cut; kept in F-03 when regrouped`, `revisions`, `verdict`,
`Open in Review`, `tags`, `+ tag`, `class`, `Make exemplar`, `Redraw in Explore`, `Remove from family`.

### Frame ⟷ spec conflicts
1. **m-1850 duration `1.62 s`** in a ~21 s family whose cards are drawn over 21 s. Use `21.6 s` (or any value
   within 21 s ± 4); flag as B28.
2. **`recordings 3 · 5 channels`**: recurrence shows F-03 on 2 + 4 + 5 = 11 channels. Compute from the member
   fixture (→ `3 · 11 channels`) or confirm what "5" counts.
3. **Card order in PDF text** lists E-0102 first; the image (and backlog line 194 "medoid m-1846 sorts
   first") put m-1846 first. Image wins.
4. **Spec §8.6 batch bar** lists "send to Review, add tag, assign class, remove from family, export" — matches.
   Spec member rail lists "±30 s context" — matches. Spec says tags and class **editable**, verdict read-only —
   frame matches (no verdict control).
5. `Und` truncation in the hand-edit box is a frame overflow (B29 class): render `Undo` fully.
6. `hand edits 2 added · 1 removed` vs atlas `3 hand` vs grouping `14 hand edits kept` — consistent (14 is
   catalogue-wide).

### Fog
1. **Undo semantics** for an *added* member are unspecified beyond "hand-edit record with Undo": whether undo
   deletes the hand edit (member leaves the family) or reverts to the pre-edit state of a moved member.
   Shell does the former.
2. **Make exemplar** consequences (§8.6 only names the action): does the old exemplar's seed verdict stay
   `seed`? Does the family's recipe hash change / become partially stale (§4.2 last rule)? Shell shows a
   stale chip `edges partially stale` on the summary after a make-exemplar.
3. §4.2's "recompute on save with a new recipe hash, or mark the family partially stale" — no stale state is
   drawn on the family page. Recommend Badge `stale` next to `mean member d` after any extent edit returns
   from Explore.
4. Sequence families (S-xx) reaching this route — not drawn (see atlas Fog 5).
5. Revision annotation id for m-1850 is not in the frame.

---

## library.grouping

### Route & states
The frame is a **Modal over the dimmed atlas**, so the route renders the page named by `from` (default
`atlas`) inert behind a scrim, with the Edit grouping modal open. Header subtitle becomes `atlas · editing
grouping`; breadcrumb `Recurrence › Atlas`. Cancel / × / Escape → `history.back()` if the previous entry is
a Library route, else `#/library/<from>`.
- `frequency-content` (frame 4): `#/library/grouping?from=atlas&basis=frequency-content`. Reached by
  *Edit grouping* on any Motifs page (opens with the current basis, shape distance), then clicking the
  `frequency content` basis.
- `basis-<kind>` (derived): `?basis=shape-distance|sequence-similarity|amplitude|timescale|frequency-content|polarity|tag|provenance|custom`.
  Parameters card (section 3) swaps; preview numbers swap.
- `unit-<unit>` (derived): `?unit=sequences|spike-trains` preselects section 1; bases that do not apply
  become disabled with reason.
- `invalid` (derived): any parameter fails validation → Preview shows `—` values and a red line naming the
  field; *Apply grouping* and *Save as grouping* are DisabledReason.
- `unchanged` (derived): settings equal g-07 → *Save as grouping* DisabledReason `same as g-07`; *Apply*
  label `Apply grouping` disabled `already the current grouping`.
- `applying` (derived): *Apply grouping* → modal footer swaps to a ProgressBar with sim job `l-0031`
  (steps `compute feature · bin · re-apply 14 hand edits · write grouping g-09`, ~900 ms each); Cancel
  becomes `Cancel job`; `?state=running` deep-links it mid-run. Done → modal closes, → `#/library/atlas`
  with grouping g-09 active, scope cleared, toast `Grouping g-09 applied · 5 groups · 21 omitted · scope
  cleared · g-07 stays saved`.
- `saved` (derived): *Save as grouping g-09* → toast `Saved g-09 · not applied`; modal stays; the button
  becomes disabled `saved as g-09`; g-09 appears in the Groupings popover.
- `over-limit` (derived): a basis whose recompute estimate exceeds the local limit (shape distance on
  sequences, fixture `~46 min`) → Apply label `Create SLURM script` + InfoTip; toast `not wired yet: export
  cluster job for regroup` (P4 pattern; see Fog 3).

### Regions
Background: the atlas page (frame 2) rendered inert under a 40 % grey scrim (frame shows the cards as blank
grey boxes — either is acceptable; render the real page for fewer code paths).
**Modal** x 290–1100 (810 px), y 125–813 (688 px), 12 px radius, white, 20 px padding.
1. Title row: sliders icon + bold `Edit grouping` + mono muted `from g-07 · shape distance`; right `×`.
2. **`1 What to group`** (y 173): three RadioCards in a row (each 250 × 50): `single motifs` / `one event
   each` / count `1,402` (selected: blue 2 px border, light-blue fill, blue title, filled radio);
   `sequences` / `events in order, with gaps` / `350`; `spike trains` / `a whole train as one entry` / `16`.
3. **`2 Group by`** (y 262): three columns (250 px each) with small icon headers — `distance`,
   `feature bins · no distance`, `labels`. Radio rows (250 × 34, grey fill, radio + mono title + tiny caption):
   - distance: `shape distance` / `z-norm, scale-invariant, Ward cut`; `sequence similarity` / `sequences
     only` (disabled, 40 % opacity);
   - feature bins: `amplitude` / `peak-to-peak mV`; `timescale` / `duration`; `frequency content` /
     `dominant frequency` (selected: blue border + fill); `polarity` / `up / down / biphasic`;
   - labels: `tag` / `morphology tags`; `provenance` / `recording · run · spike train`; `custom` /
     `clustering from Analyse`.
4. **`3 Frequency content`** (title = selected basis name; y 465): left column (x 310–620):
   `feature` label + Select `dominant frequency · Welch PSD`; `bins` + Seg `quantiles · log-spaced ·
   fixed edges` (log-spaced active); `number of bins` right-aligned value `6`; `range` right-aligned
   `0.002 – 0.5 Hz`. Right: plot card (x 633–1078, y 490–605, grey ground): muted `motifs per frequency ·
   log axis`; histogram of ~19 blue bars; vertical bin-edge lines (blue at the range ends, dark at the 5
   interior edges); last 2 bars amber past the upper edge with amber label `outside range`; x ticks
   `0.002`, `0.03`, `0.5 Hz`.
5. **`4 What does not fit`** (y 620): two Checkboxes in a row — `omit and flag motifs outside every bin` +
   amber `14 motifs`; `omit and flag groups under 10 members` + amber `7 motifs · 1 group`.
6. **Preview box** (grey fill, y 672–747): bold `Preview`, then muted-label/value pairs `groups` **5** ·
   `members` **1,381** · `omitted · flagged` amber **21** · `recompute` **~10 min, local**; purple line (hand
   icon) `14 hand edits: 11 apply · 3 point at families this grouping lacks → kept as the hand group
   “F-03 additions”`; muted line (i) `applying regroups the whole catalogue and clears the current scope;
   g-07 stays saved`.
7. **Footer** (y 770–800): left outline `Cancel`; right outline (save icon) `Save as grouping g-09`, primary
   (check icon) `Apply grouping`. Footer must not touch the modal edge (B29 fixed).

### Controls & interactions
| control | kind | behaviour |
|---|---|---|
| `×` / Escape / scrim click | Modal close | = Cancel (no discard confirm; nothing is written until Save/Apply) |
| unit RadioCards | RadioCard group | selects unit; re-evaluates basis availability: `sequence similarity` enabled only for `sequences` (reason `sequences only`); for `spike trains` disable `shape distance` and `sequence similarity` (reason `a spike train is a whole train, not one shape`, see Fog 2); if the selected basis becomes disabled, select the first enabled one |
| basis radio rows | Radio group (9) | selects basis; swaps section 3 and preview; section 3 title = basis name |
| `feature` | Select | per basis (frequency content: `dominant frequency · Welch PSD`, `spectral centroid`; timescale: `duration`, `rise time`; amplitude: `peak-to-peak mV`, `depth mV`) |
| `bins` | Seg | `quantiles` (range row hidden, edges at quantiles), `log-spaced` (range required, min > 0), `fixed edges` (shows Text field `edges` `0.002, 0.01, 0.03, 0.1, 0.5`) |
| `number of bins` | Number (inline-editable value) | integer 2–20; message `2 to 20 bins`; hidden for fixed edges (count derived) |
| `range` | RangeSlider + two Number fields on click | min < max; log-spaced needs min > 0 (`log-spaced bins need a range above 0`); within data extent 0.001–1 Hz (`outside the data: 0.001–1 Hz`) |
| `edges` (fixed edges) | Text | comma list of ≥ 3 strictly ascending numbers; message `edges must increase: 0.03 ≥ 0.01 at position 3` |
| omit checkboxes | Checkbox ×2 | unticking *outside every bin* → those 14 motifs go to the nearest edge bin, preview omitted 7; unticking *groups under 10* → small group kept, preview groups 6, omitted 14. Min size `10` is a Number (1–1000) opened by clicking the number |
| preview hand-edit line | InfoTip | lists the 3 hand edits that fall to `F-03 additions` (m-1850, m-2011, m-2012 — ids invented) |
| `Cancel` | Button | close (see Route) |
| `Save as grouping g-09` | Button | next free id (g-09); in-memory append; toast; disabled when unchanged/invalid |
| `Apply grouping` | primary Button | sim job `l-0031` (see `applying`); disabled when invalid / unchanged |

Section 3 per basis (derived; only frequency content is drawn — see Fog 1):
| basis | parameters | plot |
|---|---|---|
| shape distance | `linkage` Select `Ward` (only option); `cut` Slider 0.10–1.00 step 0.01 (default 0.42); `nearest family past` Number 0.50 | Histogram of merge heights, cut line; caption `10 families at 0.42` |
| sequence similarity (sequences only) | `cut` Slider (0.50); `max gap between events` Number s (default 360, placeholder per B16); `order` Toggle `events must keep order` | Histogram of pairwise similarity, cut line |
| amplitude | `feature` Select; `bins` Seg; `number of bins`; `range` mV | Histogram mV linear axis with edges |
| timescale | `feature` Select; `bins` Seg (log-spaced default); `number of bins`; `range` s | Histogram, log axis s |
| frequency content | as drawn | as drawn |
| polarity | no bins: fixed categories `up · down · biphasic`; `biphasic ratio` Number 0–1 (0.3) | Bars (3) |
| tag | `tag set` Select `morphology tags`; `several tags` Seg `first tag · one group per combination` | Bars per tag |
| provenance | `by` Seg `recording · run · spike train` | Bars per label |
| custom | `clustering` Select of exported Analyse clusterings (fixture `a-0098 · k = 6 · M2_aug fs1 CH4_A2 0–48 h`); scope line `scope: M2_aug fs1 · CH4_A2 · 0–48 h · 1,211 unassigned outside it` (§8.3) | Bars per cluster + grey `unassigned` bar |

### Plots
- **Feature distribution histogram** (Histogram): x = dominant frequency, log scale 0.002 → 0.5 Hz (ticks at
  0.002, 0.03, 0.5); y = motif count (no axis drawn; hover tooltip `0.011–0.015 Hz · 96 motifs`); marks:
  bars (blue inside range, amber outside), bin-edge rules, range-end rules in blue, `outside range` label.
  Recomputes edges live as bins/range change (in-memory, fixture distribution). No cap needed.

### Fixtures
```ts
type BasisKind = 'shape-distance'|'sequence-similarity'|'amplitude'|'timescale'|'frequency-content'|'polarity'|'tag'|'provenance'|'custom'
interface UnitOption { unit: 'single motifs'|'sequences'|'spike trains'; caption: string; count: number } // 1,402 · 350 (see conflict) · 16
interface BasisOption { kind: BasisKind; group: 'distance'|'feature bins · no distance'|'labels'; title: string; caption: string; units: UnitOption['unit'][] }
interface GroupingDraft { from: 'g-07'; unit: string; basis: BasisKind; params: Record<string, number|string|number[]>; omitOutside: boolean; omitSmall: boolean; minMembers: number }
interface GroupingPreview { groups: number; members: number; omitted: number; recompute: string /* '~10 min, local' */; handEdits: { total: 14; apply: number; orphaned: number; handGroup: 'F-03 additions' } }
interface FeatureDistribution { feature: string; unit: 'Hz'|'mV'|'s'; scale: 'log'|'linear'; bins: { lo: number; hi: number; n: number }[] } // 19 bins, 0.0015–0.8 Hz, total 1,402
```
Frame preview (frequency content, log-spaced, 6 bins, 0.002–0.5 Hz, both omits on): groups 5, members
1,381, omitted 21 (= 14 outside + 7 in one small group), recompute ~10 min local, hand edits 14 → 11 apply ·
3 orphaned → `F-03 additions`. Other bases: builder writes one plausible preview per basis in the fixture
(e.g. shape distance at 0.42 = g-07: 10 groups, 1,364 members, 38 omitted, ~4 min local).
Groupings shared with Settings › Library groupings (defaults, feature bases) and the atlas.
Job id prefix `l-` for Library regroups (§0).

### Copy
`Edit grouping`, `from g-07 · shape distance`, `1 What to group`, `single motifs`, `one event each`,
`sequences`, `events in order, with gaps`, `spike trains`, `a whole train as one entry`, `2 Group by`,
`distance`, `feature bins · no distance`, `labels`, `shape distance`, `z-norm, scale-invariant, Ward cut`,
`sequence similarity`, `sequences only`, `amplitude`, `peak-to-peak mV`, `timescale`, `duration`,
`frequency content`, `dominant frequency`, `polarity`, `up / down / biphasic`, `tag`, `morphology tags`,
`provenance`, `recording · run · spike train`, `custom`, `clustering from Analyse`, `3 Frequency content`,
`feature`, `dominant frequency · Welch PSD`, `bins`, `quantiles`, `log-spaced`, `fixed edges`,
`number of bins`, `range`, `motifs per frequency · log axis`, `outside range`, `4 What does not fit`,
`omit and flag motifs outside every bin`, `14 motifs`, `omit and flag groups under 10 members`,
`7 motifs · 1 group`, `Preview`, `groups`, `members`, `omitted · flagged`, `recompute`, `~10 min, local`,
`14 hand edits: 11 apply · 3 point at families this grouping lacks → kept as the hand group “F-03 additions”`,
`applying regroups the whole catalogue and clears the current scope; g-07 stays saved`, `Cancel`,
`Save as grouping g-09`, `Apply grouping`.

### Frame ⟷ spec conflicts
1. **Route vs modal**: the prescribed route is its own page; the frame is a modal. Resolved as above (route =
   modal state over `from`). Recommend also accepting `?modal=edit-grouping` on recurrence/atlas/family as
   an alias that redirects to `#/library/grouping?from=…`, so the Modal kit's query convention holds.
2. **`sequences 350`**: spec §8.2 / frame 2b give 6 sequence families holding 122 sequences + 17 unfitting =
   139 sequences, whose motifs total 350 + ~34. So `350` reads as a sequence count but is a motif count.
   Recommend `139` with caption `events in order, with gaps · 384 motifs`, or keep `350` and flag.
3. Spec §8.2 "Preview … groups, members, omitted, recompute cost, and what happens to hand edits" — frame matches.
4. Spec §8.2 "**Parameters** for the basis, with the feature's distribution and the bin edges or cut drawn
   on it" — frame matches for bins; the cut variant is not drawn.

### Fog
1. **Eight of nine parameter panels are undrawn**, and B17 says the bases themselves are undefined
   (sequence similarity, frequency content feature, timescale, spike-train unit, default cuts / bins /
   minimum size). The per-basis table above is an extrapolation for the shell; everything in it is a
   placeholder to confirm.
2. **What a `spike trains` unit groups by** is undefined (B17): which bases apply is a guess.
3. **Recompute cost vs local limits**: Settings has local limits for Analyse, Discovery, Models only (§0);
   a Library regroup has none. `~10 min, local` implies one. Shell treats Library as 20 min (same as
   Analyse) and flags it.
4. "Applying … clears the current scope" — whether it also clears filters (`adjudicated only`, `≥ 10
   members`) is unstated; shell keeps filters.
5. The feature-bin groupings (g-09) have no atlas frame: group names (e.g. `0.002–0.006 Hz`), exemplar and
   medoid for a non-distance group are undefined. Shell: name groups by bin label, medoid = member nearest
   the bin's feature median, exemplar `—` (no human anchor yet) with a muted `no exemplar` badge.

---

## library.import

### Route & states
(See the decision under Pages: empty = state of every Motifs route; import = this route.)
- `empty+dry-run` (frame 5): `#/library/import?library=empty`. Reached from the empty Motifs section
  (`#/library/recurrence?library=empty`) by *Import…* or the toolbar `Import`. Left column = empty state
  with the import option card highlighted; right = dry-run panel.
- `empty` (derived, not this route): any Motifs route with `?library=empty` → the left column alone,
  centred at max-width 600 px, neither option card highlighted, toolbar primary `Import`.
- `dry-run` on a populated library (derived): toolbar `Import` on frames 1–3 → `#/library/import`. Left
  column becomes a "library now" card (see Regions 2b); the dry run finds the bundle already imported (see
  Controls, "safe to run twice").
- `bundle-invalid` (derived): bundle Select → `DATA/library_seed/untitled_bundle` or `?bundle=no-provenance`.
- `importing` (derived): *Import 410 motifs* → sim job `l-0032`; `?state=running`.
- `done` (derived): success panel, then navigation.
- `failed` (derived): `?state=failed` → sim fails at step 3 with error `sample range 0:88,100 outside
  L_LM_Jul26_J CH4 (806,400 samples)`; panel shows a red ErrorCard with `Retry` and `nothing was written —
  imports are all-or-nothing`.

### Regions
1. Header: page `Motifs`, subtitle `empty`. Section toolbar: Seg `Motifs 0` · `Window sets 6` ·
   `Templates 14`; no breadcrumb; right primary (filled blue) `⤓ Import` (in the empty state only; outline on
   a populated library, as frames 1–3).
   No grouping bar (the empty state has nothing to group).
2. **Left column** x 78–675 (≈ 43 %):
   a. **Empty-state card** y 115–520 (white): icon tile 54 × 54 (library icon, light-blue ground); H2
      `The motif library is empty` (20 px bold); muted mono `No families, no exemplars yet. Two ways in:`;
      option card 1 (grey fill, x 116–637, y 290–381): list-check icon + bold `Judge candidates in Review`
      / mono muted `pressing S on a candidate creates an exemplar here` / outline `Open Review →`; option
      card 2 (selected: light-blue fill, blue 1 px border, y 393–486): download icon + bold `Import motifs
      you have already extracted` / `a bundle with provenance; safe to run twice` / primary `⤓ Import…`.
   b. **Groupings placeholder card** y 537–605 (white, muted): `Groupings appear once there is something to
      group` / mono `single motifs · sequences · spike trains, by distance, feature bins or labels`.
   2b (populated library, derived): one card `Library now` with KeyValue `motifs 1,402 · families 10 ·
      grouping g-07 · spike trains 16` and link `‹ back to recurrence`.
3. **Import panel** x 691–1374 (≈ 50 %), y 115–733 (white card):
   - Title: download icon + bold `Import motifs` + blue chip `dry run · nothing written yet`; right `×`.
   - `bundle` label; Select (x 710–1115) `DATA/library_seed/drop_motifs` + green chip `PROVENANCE.md found`.
   - 4 StatTiles in a row (152 × 50, grey): `motifs 410` · `spike trains 16` · `recordings 2` · `channels 7`.
   - **Checks** (bold): ChecksList rows, title left, mono muted detail right-aligned:
     ✓ `provenance complete` — `410 of 410 carry spike train, recording, channel, sample range`;
     ✓ `sample ranges inside their recordings` — `410 of 410`;
     ✓ `safe to run twice` — `content hash per motif · 0 already in the library · re-import skips`;
     ✓ `3 overlap an existing annotation` — `linked to it, not duplicated`;
     ⚠ (amber) `sampling rate inferred for L_LM_Jul26_J` — `10 Hz, not read from the file · durations provisional`.
   - **What the import creates** (bold): blue `+` rows: `410 single-motif entries, unjudged — imports are not
     verdicts`; `16 spike-train entries, each linked to its motifs`; `first grouping g-01 · single motifs ·
     shape distance · cut 0.42 · editable after`.
   - `Sample` bold + muted `9 of 410`; right blue `⤮ resample`. Row of 9 MotifThumbs (64 × 42, grey ground,
     black traces).
   - (empty region y 590–690 — B29 noted it; acceptable, or move the footer up.)
   - Footer y 690–718: Checkbox (ticked) `then send 410 to Review as a queue`; right outline `Cancel`, primary
     `⤓ Import 410 motifs`.

### Controls & interactions
| control | kind | behaviour |
|---|---|---|
| toolbar `Import` | Button | on this route: focuses the bundle Select |
| `Open Review →` | Button | → `#/review` (Review default page) |
| `Import…` | primary Button | opens/focuses the dry-run panel (already open on this route); from `?library=empty` on a Motifs route → `#/library/import?library=empty` |
| panel `×` / `Cancel` | Button | → previous Library route (empty state, or recurrence) |
| bundle Select | Select | options: `DATA/library_seed/drop_motifs` (valid, frame); `DATA/library_seed/untitled_bundle` (no PROVENANCE.md → `bundle-invalid`); divider; `Browse…` → toast `not wired yet: bundle picker (bridge would list folders under DATA/)`. Changing bundle re-runs the dry run: 600 ms skeleton rows `checking…` then results |
| `PROVENANCE.md found` | Chip | green; in `bundle-invalid` red `PROVENANCE.md missing` |
| check row | hover/click | expands detail: `3 overlap` lists `a-2077 ↔ motif 118`, `a-2102 ↔ motif 240`, `a-2140 ↔ motif 377` (invented ids); `sampling rate inferred` links `Settings › Datasets` → `#/settings/datasets?recording=L_LM_Jul26_J` |
| `resample` | link-button | new seeded 9-of-410 sample |
| sample thumb | hover | tooltip `motif 118 · L_LM_Jul26_J · CH3 · 14.2 h · 3.1 s (provisional)` |
| `then send 410 to Review as a queue` | Checkbox | default on; label count follows motifs |
| `Import 410 motifs` | primary Button | sim job `l-0032` steps `hash 410 motifs · link 3 annotations · write 410 + 16 entries · compute grouping g-01` (900 ms each); button → ProgressBar + `Cancel import` (cancel allowed before step 3: `nothing was written`); disabled with reason when any check is ✗ (`provenance incomplete: 410 motifs lack a sample range`) |
| done | — | panel shows ✓ `Imported 410 motifs · 16 spike trains · grouping g-01`; if the queue box was ticked, toast queue `Library · import drop_motifs` · 410; primary `Open the library →` → `#/library/recurrence` with `library=empty` cleared (demo then shows the canon catalogue g-07; toast note `demo: showing the canon catalogue`) |
| populated-library dry run | — | `safe to run twice` row reads `410 already in the library · re-import skips`; creates list reads `0 new entries — every motif hash is already present`; Import button DisabledReason `nothing new to import` |

### Plots
- **Sample thumbnails** (MotifThumb ×9): each on its own y-scale? **No** — shared mV domain across the 9 (D5),
  x = own duration; P8 cap: 9 with resample.

### Fixtures
```ts
interface ImportCheck { status: 'ok'|'warn'|'fail'; title: string; detail: string; items?: string[] }
interface ImportBundle {
  path: string; provenanceFile: 'PROVENANCE.md'; provenanceFound: boolean
  counts: { motifs: 410; spikeTrains: 16; recordings: 2; channels: 7 }
  recordings: string[] /* ['M2_aug_fs1','L_LM_Jul26_J'] */; channels: string[] /* CH3_A2, CH4_A2 + L_LM CH1–CH5 */
  alreadyInLibrary: number; overlaps: number; inferredFs: { recording: 'L_LM_Jul26_J'; fsHz: 10 }[]
  checks: ImportCheck[]; creates: string[]; firstGrouping: 'g-01'
  sample: { id: number; recording: string; channel: string; onsetH: number; durationS: number; traceSeed: number }[] // 410
}
interface LibraryDemoState { empty: boolean; lastMotifsRoute: string }
```
Canon: recordings and fs (L_LM_Jul26_J 10 Hz inferred, §0), actor `this installation`, job prefix `l-`.
Shared: recordings/channels, review queue naming, Settings › Datasets link.

### Copy
`empty`, `Motifs 0`, `The motif library is empty`, `No families, no exemplars yet. Two ways in:`,
`Judge candidates in Review`, `pressing S on a candidate creates an exemplar here`, `Open Review →`,
`Import motifs you have already extracted`, `a bundle with provenance; safe to run twice`, `Import…`,
`Groupings appear once there is something to group`, `single motifs · sequences · spike trains, by distance,
feature bins or labels`, `Import motifs`, `dry run · nothing written yet`, `bundle`, `PROVENANCE.md found`,
`motifs`, `spike trains`, `recordings`, `channels`, `Checks`, check strings above, `What the import creates`,
creates strings above, `Sample`, `9 of 410`, `resample`, `then send 410 to Review as a queue`, `Cancel`,
`Import 410 motifs`.

### Frame ⟷ spec conflicts
1. **Bundle path**: frame `DATA/library_seed/drop_motifs`; the tracked bundle in the repo is
   `DATA/library_seed/drop_motifs5/` (contains `PROVENANCE.md`, `motifs/`, `autoderive_summary.json`).
   Recommend `DATA/library_seed/drop_motifs5` so the fixture names a real path; counts stay fixture (not read).
2. Spec §8.7 lists the checks "provenance complete, sample ranges inside recordings, content hash per motif,
   overlaps linked not duplicated, inferred sampling rates flagged" — frame matches all five, in order.
3. Spec says "then send to Review as a queue" — frame makes it a checkbox on the import; matches.

### Fog
1. **Non-empty import** is undrawn; the "already in the library" variant above is an extrapolation.
2. After a demo import the catalogue should be 410 motifs in g-01 — there is no fixture for that catalogue.
   Shell switches to the canon 1,402 catalogue and says so in a toast. Needs acceptance.
3. Whether an import whose L_LM durations are provisional should block `Import` or only warn — frame warns.
4. Which 2 recordings / 7 channels the bundle covers is not stated; `M2_aug fs1` (CH3_A2, CH4_A2) +
   `L_LM_Jul26_J` (CH1–CH5) is a guess that fits the counts.

---

## library.window-sets

### Route & states
- `set-selected` (frame 6): `#/library/window-sets` — first row selected by default; deep link
  `?set=ws_M2aug_3ch_600s`. Reached by section Seg `Window sets`, or links from Models / Analyse (`used by`).
- `not-train-safe-selected` (derived): click `ws_M2aug_1ch_60s` or `ws_human_labelled_mixed`, `?set=`. Rail
  explains why, `Train in Models` DisabledReason, adds `Re-split in Analyse →`.
- `test-sample-selected` (derived): `ws_verif_cnn_cluster_v1`: split plan shows one test block; `Train in
  Models` DisabledReason `a test sample is never trained on`.
- `fs-inferred-selected` (derived): `ws_LLM_5ch_600s`: amber note `L_LM_Jul26_J fs 10 Hz is inferred —
  confirm it in Settings › Datasets before training`; Train DisabledReason `fs inferred`.
- `filter-*` (derived): Seg / `?safe=train-safe|not-train-safe`; chips `?rec=`, `?labelled=`, `?used=`.
- `filtered-empty` (derived): filters exclude everything → Table EmptyState `No window sets match ·
  Clear filters`.
- `delete-confirm` (derived): *Delete* on an unused set / `?modal=delete`.
- `coverage-at-save` (derived): rail labels Seg `now · at save` / `?coverage=save` (§6.9 live coverage).
- `none` (derived): `?sets=empty` → EmptyState `No saved window sets yet` / `Save one from any block whose
  output is a WindowSet (e.g. sliding windows in a training chain)` / `New from Analyse`.

### Regions
1. Header: page `Window sets`, subtitle `6 saved`. Section toolbar: Seg `Window sets` active; right outline
   `New from Analyse` (chain icon), `⤓ Import`. No grouping bar.
2. **Filter card** y 100–147, x 78–1042: Seg `all · train-safe · not train-safe`; filter chips (outline,
   label muted + value) `recording any`, `labelled any`, `used any`; right muted `sort` + Select `last used`.
3. **Table card** y 158–610, x 78–1042. Header row (muted, 12 px): `name` (x 92) · `source` (280) ·
   `window · stride · gap` (444) · `windows` (588) · `split` (656) · `labelled` (762) · `used by` (839) ·
   `check` (926). Row height ≈ 69 px. Cells:
   - name: mono bold `ws_M2aug_3ch_600s` / mono muted `12 Sep · this installation`;
   - source mono; window·stride·gap mono; windows mono bold;
   - split: SplitBar 88 × 10 (train blue · validation orange · test green) + muted `blocked` / full green
     `test only` / red text `no split`;
   - labelled: MiniBar 58 × 5 green + muted `14 %`;
   - used by: blue link `2 · Models` / `—`;
   - check: Badge `train-safe` (green) / `fs inferred` (amber) / `test sample` (blue) / `not train-safe`
     (red) / `gap < window` (red).
   - Selected row: light-blue fill.
4. **Legend** y 629 (under table, no card): swatches `train`, `validation`, `test`; (i) muted `train-safe =
   blocked split with gap ≥ window, checked when saved`.
5. **"Why not train-safe" card** y 655–772, x 78–1042: red shield icon + bold `Why two sets are not
   train-safe`; two mono lines (see Copy); blue link (chain icon) `Re-split in Analyse →`.
6. **Detail rail** x 1058–1374, y 100–848:
   - mono bold `ws_M2aug_3ch_600s` + Badge `train-safe`.
   - KeyValue: `made by` cnn_windows_v3 · sliding windows · `recipe hash` mono `5c1e…a07b` · `windows`
     15,660 over 3 channels.
   - `split plan · blocked by time` (muted); SplitPlan: one BandStrip per channel (`CH2_A1`, `CH4_A2`,
     `CH7_B2`), 255 × 20 each: train (blue, ~55 %) · gap · validation (orange ~8 %) · gap · test (green
     ~20 %) · gap · train (blue ~7 %); gaps are white/grey slivers; caption mono `grey = gap ≥ 600 s · 18
     straddling windows dropped`.
   - ChecksList (green ✓): `gap ≥ window on every boundary`, `no test window within 600 s of training`,
     `test windows unseen by any job`.
   - `labels · 2,140 windows · 14 % labelled` (muted); ClassBars (label left, bar 140 px, count right mono):
     `spike-train 410` (#5856D6), `burst 380` (#E85AAD), `slow-drift 330` (#30B0C7), `plateau 250`
     (#A2845E), `artifact · excluded 38` (red, short).
   - `used by` (muted); blue links with model icon: `Models · job j-0212 (paired arms)`, `Models · candidate
     cnn_windows_v3 · manual`.
   - Actions (y 710–835): primary `Use as source in Analyse →`; outline `Train in Models →`; outline
     `Send 13,520 unlabelled to Review`; blue link `⤴ Export`; right, disabled `🗑 Delete` + muted `used by 2`.

### Controls & interactions
| control | kind | behaviour |
|---|---|---|
| `New from Analyse` | Button | → `#/analyse/training` (training chain, sliding-windows block offers *Save window set*; Analyse inventory owns the route) |
| `Import` | Button | Modal `Import window set`: Text `bundle path` (required, must end `/windows.json` or be a folder; message `pick a window-set bundle`), dry-run check list (spacing, split, recordings exist, held-out M4 refused: `M4_aug is held out and locked`); primary `Import` → toast `not wired yet: POST /api/window-sets/import` |
| safety Seg | Seg | filter rows in memory |
| `recording any` | Popover | Checkbox list of the 5 recordings (M4_aug disabled `held out`), plus `Review verdicts` |
| `labelled any` | Popover | Seg `any · none · some · 100 %` |
| `used any` | Popover | Seg `any · used · unused` |
| `sort` | Select | `last used`, `name`, `windows`, `labelled`, `saved` |
| column header | Table sort | sortable name, windows, labelled |
| row | click / ↑↓ | select → rail; `?set=` replace |
| `used by` link in row | link | `2 · Models` → rail scrolls to used-by; `1 · Analyse` → `#/analyse/…?source=windowset:<id>`; `1 · Registry` → `#/models/registry?model=cnn_cluster_v1`; `1 · Review` → `#/review?queue=q-18` |
| check badge | InfoTip | reason text for the badge (same as the Why card lines) |
| `Re-split in Analyse →` | link | → `#/analyse/training/block/1?source=windowset:ws_M2aug_1ch_60s` (sliding-windows block, where the blocked split and gap live — P15) |
| rail BandStrip block | hover | tooltip `CH4_A2 · test · 540.0–690.0 h · 1,044 windows` |
| rail class bar | hover | `burst · 380 windows · train 262 · validation 41 · test 77` |
| rail coverage Seg (derived) | Seg `now · at save` | swaps class counts to the at-save fixture (§6.9) |
| `used by` rail links | link | `job j-0212` → `#/jobs/j-0212`; `candidate cnn_windows_v3 · manual` → `#/models/registry?candidate=cnn_windows_v3_manual` |
| `Use as source in Analyse →` | primary | → `#/analyse/training?source=windowset:ws_M2aug_3ch_600s` (frame training 0: WindowSet source feeds the window matrix — P15) |
| `Train in Models →` | Button | → `#/models/launch?windowSet=ws_M2aug_3ch_600s` (frame models-1b). DisabledReason for not-train-safe (`gap 30 s < 60 s window`), `no split`, `test sample`, `fs inferred` |
| `Send 13,520 unlabelled to Review` | Button | toast queue `Library · ws_M2aug_3ch_600s unlabelled` · 13,520; if > 20,000 (P13 cap) DisabledReason `queue cap 20,000` (ws_M2aug_1ch_60s has 17,848 unlabelled — under the cap) |
| `Export` | link | toast `not wired yet: export window set (bounds on disk + manifest)` |
| `Delete` | Button (danger) | DisabledReason `used by 2 — delete is blocked while anything uses the set` when used; enabled for `ws_LLM_5ch_600s` and `ws_human_labelled_mixed` → confirm Modal `Delete ws_LLM_5ch_600s?` / `670 window bounds are removed from disk. Runs that used it keep their record.` / `Cancel` · red `Delete` → in-memory remove, toast `not wired yet: DELETE /api/window-sets/ws_LLM_5ch_600s`, chip count `Window sets 5` |

### Plots
- **SplitBar** (Bars, stacked, per row): proportions of windows train / validation / test; no axis.
- **Labelled MiniBar**: fraction labelled.
- **SplitPlan** (BandStrip per channel): x = hours since recording start (0 → 721 h for M2_aug fs1; no ticks
  drawn, tooltip gives hours), bands = split blocks, gaps ≥ window shown as grey slivers. One strip per
  channel; cap P8 at 10 channels with `+N channels` expander (ws_LLM has 5, fine).
- **ClassBars** (Bars, horizontal): windows per class with class colours; artifact `excluded` in red.

### Fixtures
```ts
type SetCheck = 'train-safe'|'test sample'|'not train-safe'|'gap < window'|'fs inferred'|'no split'
interface SplitBlock { split: 'train'|'validation'|'test'|'gap'; fromH: number; toH: number; windows: number }
interface WindowSet {                       // shared canon (Models launch 1b, Analyse training source, Review queue source)
  id: string; version: number; savedAt: string; savedBy: 'this installation'|'Models'
  source: { kind: 'sliding windows'|'test block'|'supplied'; recordings: string[]; channels: string[]; label: string; parentSetId?: string }
  windowS: number|null; strideS: number|null; gapS: number|null; windows: number
  split: { train: number; validation: number; test: number } | null; splitRule: 'blocked by time'|'test only'|null
  labelledPct: number; labelledWindows: number; usedBy: { kind: 'Models'|'Analyse'|'Registry'|'Review'; label: string; href: string }[]
  check: SetCheck; checkReason?: string; madeBy?: string; recipeHash?: string
  splitPlan?: Record<string /*channel*/, SplitBlock[]>; droppedStraddling?: number
  spacingChecks?: { label: string; ok: boolean }[]
  classCounts: { now: Record<string, number>; atSave: Record<string, number>; artifactExcluded: number }
}
```
Rows (frame 6, in order): name · saved · source · window·stride·gap · windows · split · labelled · used by · check
1. `ws_M2aug_3ch_600s` (**§0: v1**, M2_aug fs1 · CH2_A1, CH4_A2, CH7_B2 · 600 s · 15,660 · 2,140 labelled ·
   train-safe) · 12 Sep this installation · `M2_aug fs1 · 3 ch` · 600·300·600 s · 15,660 · blocked ≈ 70/10/20 ·
   14 % · 2 · Models · train-safe. made by `cnn_windows_v3 · sliding windows`, recipe `5c1e…a07b`, 18
   straddling dropped, 3 checks ok, classes spike-train 410 · burst 380 · slow-drift 330 · plateau 250 ·
   artifact excluded 38, used by j-0212 (paired arms) + candidate `cnn_windows_v3 · manual`, unlabelled 13,520.
2. `ws_M2aug_fs2_300s` · 11 Sep · `M2_aug fs2 · CH1–CH4` · 300·150·300 s · 4,880 · blocked · 12 % · 1 · Analyse · train-safe.
3. `ws_LLM_5ch_600s` · 9 Sep · `L_LM_Jul26_J · 5 ch` · 600·600·600 s · 670 · blocked · 0 % · — · fs inferred.
4. `ws_verif_cnn_cluster_v1` · 14 Sep · Models · `test block · ws_M2aug_3ch` · 600 s · 40 · test only · 100 % ·
   1 · Registry · test sample (the verification sample of `cnn_cluster_v1`; §0 verification sample is 40).
5. `ws_human_labelled_mixed` · 8 Sep · `Review verdicts · 3 rec` · supplied · 1,312 · no split · 100 % · — · not train-safe.
6. `ws_M2aug_1ch_60s` · 6 Sep · `M2_aug fs1 · CH4_A2` · 60·30·30 s · 18,400 · blocked · 3 % · 1 · Review · gap < window.
Shared canon: window set `ws_M2aug_3ch_600s` v1 (and v2 created by a new Models launch), job `j-0212`,
models `cnn_windows_v3 · manual`, `cnn_cluster_v1`, classes + colours, queue `q-18` training windows.

### Copy
Subtitle `6 saved`. `New from Analyse`, `Import`, `all`, `train-safe`, `not train-safe`, `recording any`,
`labelled any`, `used any`, `sort`, `last used`, column headers above, `blocked`, `test only`, `no split`,
`supplied`, `this installation`, `2 · Models`, `fs inferred`, `test sample`, `gap < window`, legend
`train`, `validation`, `test`, `train-safe = blocked split with gap ≥ window, checked when saved`.
Why card: `Why two sets are not train-safe` / `ws_human_labelled_mixed — supplied Review windows,
overlapping, no split: fine for Review and interrogation, leaks if trained on (B7).` / `ws_M2aug_1ch_60s —
gap 30 s is shorter than the 60 s window, so neighbouring windows share samples across the split.` /
`Re-split in Analyse →`. Rail: `made by`, `recipe hash`, `windows`, `15,660 over 3 channels`,
`split plan · blocked by time`, `grey = gap ≥ 600 s · 18 straddling windows dropped`, the three check lines,
`labels · 2,140 windows · 14 % labelled`, `artifact · excluded`, `used by`, `Models · job j-0212 (paired
arms)`, `Models · candidate cnn_windows_v3 · manual`, `Use as source in Analyse →`, `Train in Models →`,
`Send 13,520 unlabelled to Review`, `Export`, `Delete`, `used by 2`.

### Frame ⟷ spec conflicts
1. **Version not shown**: §0 names `ws_M2aug_3ch_600s` **v1** and Models saves v2. Recommend a mono chip `v1`
   after the name in row and rail.
2. **Class counts do not sum to labelled**: 410+380+330+250+38 = 1,408 vs `2,140 windows` labelled. Keep
   2,140 (canon) and scale class counts to sum to 2,102 + 38 artifact (e.g. 612 · 568 · 492 · 430 · 38) —
   or keep frame bars and flag. Recommend canon-consistent numbers; flag for user.
3. **§6.9 "coverage now and at save time"** — the frame shows one set of numbers. Add the derived `now · at
   save` Seg.
4. **§8.8 lists a check badge `no split`**; frame row 5 uses `not train-safe` badge with `no split` in the
   split column. Keep the frame (one badge per row); `no split` reason lives in the split column and Why card.
5. **§8.8 filters "train-safety, recording, labelled, used"** — frame matches.
6. **§6.9 "human-annotated windows … badged so"** — frame's row 5 badge `not train-safe` + `supplied`; OK.
7. **Row 2 `M2_aug fs2 · CH1–CH4`** uses `CHn` naming, but M2_aug channels are `CHn_XY` (§0). Use
   `M2_aug fs2 · CH1_A1–CH4_A2`.

### Fog
1. **Delete** actually removing bounds from disk vs archiving is unspecified; confirm copy is a guess.
2. The split fractions of each row's SplitBar and the hour ranges of the rail SplitPlan are not in any
   spec; frame proportions used.
3. `ws_M2aug_fs2_300s` is a window set on fs2 — B30's rule (don't mix fs1 and fs2) would matter if a
   training job combined it with fs1 sets; no UI guard is drawn.
4. `Send unlabelled to Review` for sets with > 20,000 unlabelled windows (P13 cap) is not drawn.

---

<!-- NEXT -->
