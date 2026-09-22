# Inventory — Shell + Explore

Build spec for the shared shell (nav rail, header) and the Explore workspace. Frames:
`prototyping/imgs/shell/*.pdf` (2), `prototyping/imgs/explore/*.pdf` (10). Spec: `prototyping/UI_FUNCTIONAL_SPEC.md`
§0 (canon), §2, §3, §4.1–4.3, §5.1–5.5, P6/P8/P9. Backlog: D1, D2, D3, B28, B29 (Explore rows).

Coordinates below are in the 1440 × 900 frame (the PDF images are 1389 × 868; multiply by 1.037). The nav rail
is 64 px and the header 44 px on every page, so the content area is x 64–1440, y 44–900. The page ground is
grey (`--bg #f5f6f8`) and every card is white with a 1 px border and a radius of about 10 px.

**Live vs fixture, the rule used throughout.** Corpus and Signal are live against the bridge today and must stay
live. Everything the bridge cannot provide (families, tags, methods, adjudications, templates, review coverage,
filter fields the DB does not carry) is added as **fixture-backed regions** inside those live pages. Each such
region carries a small `demo` Badge in its card head, and the header shows the `demo data` chip whenever any
fixture region is on screen. Cross-channel and Span edit are fully fixture pages. Fixture values follow §0,
not the live DB: the live DB has real recording names (e.g. `Mushroom_260720`) that differ from the canon.

## Pages

| page id | route | frames covered | spec § | states (frame → state name → how reached) |
|---|---|---|---|---|
| shell | every route (`App.tsx` chrome) | shell-nav-rail.pdf, shell-header.pdf | §2, §3, §0 (Jobs, M4 lock) | nav-rail → active workspace → route prefix · header → `need-you` popover → click chip (`?popover=need-you`) · header → `held-out` popover → click lock chip (`?popover=held-out`) · header → search open → click pill / `Ctrl K` (`?popover=search`) |
| explore.corpus | `#/explore/corpus` (`?rec=<recordingId>&ch=<channelId>&colour=<annotations\|detections\|both\|disagree>`) | explore-1-corpus.pdf, explore-1b-corpus-menus.pdf | §5.1 | 1 → `default` → route · 1b → `recordings-menu` → click recording selector (`?popover=recordings`) · 1b → `map-legend` → click (i) on the coverage card (`?popover=legend`) · (no frame) `held-out` → pick M4 (`?rec=<M4 id>`) · `no-selection` · `nothing-shown` (both Show boxes off) · `zero-match` · `loading` · `error` |
| explore.signal | `#/explore/signal/<channelId>` (`?popover=…&drawer=…&motif=<n>`) | explore-2-signal.pdf, explore-2a-signal-popovers.pdf, explore-2b-signal-drawer.pdf, explore-2c-drawer-detections.pdf, explore-2d-drawer-shortcuts.pdf | §5.2, §5.3, P6, P9 | 2 → `default` → route · 2a → `detections-picker` → click the `detections 6 runs · 4 methods` chip (`?popover=detections`) · 2a → `span-legend` → click (i) on the SPAN card (`?popover=span-legend`) · 2b → `drawer-annotations` → click the `Annotations 708` ribbon, `D`, or `1` (`?drawer=annotations`) · 2c → `drawer-detections` → click the `Detections 1284` ribbon or `2` (`?drawer=detections`) · 2d → `drawer-shortcuts` → click the `Keyboard shortcuts` ribbon, `3` or `?` (`?drawer=shortcuts`) · (no frame) `no-motif` · `held-out` (`#/explore/signal/52`) · `loading` · `error` · `tag-input` |
| explore.cross-channel | `#/explore/cross-channel/<channelId>` (`?align=recorded\|lag&pad=20\|60&maxlag=10\|30\|60&y=absolute\|centred\|per-channel&channels=4,3,1,2,5,6`; `y` defaults to `centred`) | explore-3-cross-channel.pdf, explore-3b-cross-channel-aligned.pdf | §5.4 | 3 → `as-recorded` → route / Seg (`?align=recorded`) · 3b → `lag-aligned` → click `lag-aligned` (`?align=lag`) · (no frame) `channels-picker` (`?popover=channels`) · `questions-open` (`?questions=open`) · `computing` (`?state=computing`) · `too-few-channels` · `held-out` · `unknown-channel` |
| explore.span-edit | `#/explore/span-edit/<spanId>` (`spanId` = member id, e.g. `m-1846`; `?queue=q-12&candidate=12&of=50`) | explore-4-span-edit.pdf | §4.2, §4.3, §5.5 | 4 → `edited` → route with the canned edit (`?state=edited`) · (no frame) `pristine` (the default on arrival, Save disabled) · `invalid` (end ≤ start) · `saving → saved` (Save click) · `held-out` · `unknown-span` |

---

## Shell

Frames `shell-nav-rail.pdf` (64 × 900 component) and `shell-header.pdf` (1376 × 44; this copy is from Explore ›
Corpus). Both already exist in `webui/client/src/shell/NavRail.tsx` and `Header.tsx`. The build refactors them
into the kit and keeps their testids (`nav-rail`, `header`, `nav-<workspace>`), because `webui/smoke.py` asserts both.

### Nav rail (`shell/nav-rail`)
- **Geometry.** 64 px wide and full height. White (`--card`) with a 1 px right border.
- **Logo tile.** At the top: about 38 × 38 px, radius about 10, fill `--blue #0a84ff`, with a white sprout
  (seedling) glyph. It is not a button in the frame. Recommendation: a click navigates to `#/explore/corpus`, with
  the tooltip "Underground Brains".
- **Workspace group.** Directly under the logo: six items, each a 54 × 50 button with a 22 px icon over a 10 px label.
  1. **Explore.** Icon: a vertical squiggle waveform. Opens `#/explore/corpus`.
  2. **Analyse.** Icon: two linked squares (a workflow). Opens `#/analyse/chain`.
  3. **Discovery.** Icon: a radar or target. Opens the Discovery landing page. **Discovery inventory owns this route.**
  4. **Models.** Icon: a brain circuit. Opens the Models landing page.
  5. **Review.** Icon: a list with two check marks. Opens the Review landing page.
  6. **Library.** Icon: books. Opens the Library landing page.
- **Active item.** The item whose workspace matches `route.workspace` gets a `--blue-100` rounded tile, with its
  icon and label in blue. Inactive items are muted grey and turn to a grey tile on hover.
- **Foot.** Pinned to the bottom, in this order:
  - **`Jobs · 3`.** The icon is a rounded rect with a gear inside. The label is `Jobs · N`, where N is the canon count
    of jobs needing attention. The frame reads `Jobs · 3`, and the **Jobs inventory owns** the exact definition.
    Today the shell counts live running bridge jobs and shows `Jobs` when there are none. Recommendation: show the
    fixture canon count (3) with a `demo` title, plus live running jobs.
  - **A hairline divider**, about 36 px wide.
  - **`Settings`.** Gear icon; opens the Settings landing page (`#/settings/datasets`).
- **Keyboard.** Each item is a focusable button with `aria-current="page"` when active. No shortcuts are shown in the frame.
- **Copy.** `Explore` `Analyse` `Discovery` `Models` `Review` `Library` `Jobs · 3` `Settings`.

### Header (`shell/header`)
- **Geometry.** 44 px tall, white, with a 1 px bottom border and 20 px side padding. Items are centred vertically.
- **Left cluster**, left to right:
  - the workspace name (bold, about 15 px, near-black);
  - a 1 px vertical divider about 16 px tall;
  - the page name (regular, about 14 px, `--text-2`);
  - the subtitle (monospace, about 11 px, muted, slightly letter-spaced).
- **Right cluster**, left to right, with 8 px gaps:
  1. **Search pill.** About 280–290 × 28 px, light grey fill, radius about 6 (a rounded rect, not a full pill), with
     a magnifier icon. The placeholder is supplied per page (Explore: `Search spans, runs, families`). A mono kbd
     `Ctrl K` sits at the right.
     - **Behaviour.** A click or `Ctrl K` opens a Popover under the pill, with a focused text input. Typing filters an
       in-memory index of canon entities: recordings, channels, runs `#128 …`, families `F-03 …`, members `m-1846`,
       templates. Picking one navigates to its route where a route exists.
     - **Enter with no match** raises the Toast `not wired yet: GET /api/search?q=<q>`. Escape or an outside click closes it.
     - Today the pill is inert (`aria-disabled`).
  2. **`demo data` chip** (a kit addition, not in the frame). A grey chip with a dashed outline, shown only while a
     fixture region is on screen. Its tooltip: "numbers in the marked cards are §0 placeholder canon, not your database".
  3. **`● 3 need you`.** A full pill in `--blue-100` with blue text and a leading blue dot.
     - **Behaviour.** A click opens a Popover listing the three canon items. The **Jobs inventory owns** the list;
       §0 candidates are `a-0098` paused at stage 2 of 5, `j-0214` at 3.3× its estimate and `j-0209` failed. Each row
       links into Jobs, and the popover footer says `Open Jobs →`.
     - **When zero,** the chip turns grey and reads `0 need you`.
     - **Today** the live count is failed runs started from this tab. Keep that as an additive live count.
  4. **`🔒 M4 held out`.** A grey pill with a lock icon and grey text. A click opens a Popover:
     - title `M4_aug is held out`;
     - body `Held out and locked (D6): every workspace refuses it — nothing from it is drawn, trained on or scored.`;
     - link `Settings › Datasets →` to `#/settings/datasets`.
- **Per-page header copy.** Each page sets its own. The Explore values:

| page / state | workspace | page | subtitle |
|---|---|---|---|
| corpus | Explore | Corpus | `bird's-eye across every channel` |
| signal | Explore | Signal | `CH4_A2 · 708 annotations · 1,284 detections` (live: `<name> · <n> annotations · <n> detections`) |
| signal, drawer open | Explore | Signal | `CH4_A2 · drawer, Annotations` / `… drawer, Detections` / `… drawer, Shortcuts` |
| cross-channel | Explore | Cross-channel | `CH4_A2 reference · 6 channels`; lag-aligned: `CH4_A2 reference · lag-aligned` |
| span edit | Explore | Editing a span | `m-1846 · opened from Review` |

- **Existing extras to keep.** The red `bridge unreachable` chip (a live poll failure); the ErrorBoundary per workspace.

---

## explore.corpus

### Route & states
- `default` (frame 1). Route `#/explore/corpus`.
  - **Recording.** The last one chosen (session state `explore.file`), otherwise the first open recording.
  - **Channel.** CH4_A2 is selected when present (live code already does this).
  - **Query overrides.** `?rec=` recording, `?ch=` channel id and `?colour=`. Write these back to the hash with
    `replaceState` so a screenshot URL reproduces the view.
- `recordings-menu` (frame 1b, left popover). Click the recording selector, or `?popover=recordings`.
- `map-legend` (frame 1b, right popover). Click the (i) at the top right of the COVERAGE MAP card, or `?popover=legend`.
  - Only one popover is open at a time; backlog B29 flags the frame's overlap as a defect.
  - For the frame-1b screenshot, take two shots.
- `held-out`. Pick `M4_aug` (live: a LockedCard replaces map and rail, and the bottom bar reads `held out · no channel can be opened`).
- `no-selection`. No row selected: the bottom bar reads `select a channel`, and `Open …` is disabled with the reason `select a channel first`.
- `nothing-shown`. Both Show checkboxes are off.
  - The map label reads `nothing shown`.
  - All cells are grey, and an EmptyState is overlaid: `Tick annotations or detections to colour the map.`
- `zero-match`. The filters match nothing.
  - The rail foot reads `0 spans · across 0 of 16 channels`.
  - The map is all grey, with the caption `no span matches these filters · clear filters`.
- `loading`: the map skeleton (live). `error`: an ErrorCard with the failed call (live).

### Regions (1440 × 900)
1. **Header**: y 0–44, per the Shell section.
2. **Toolbar row**: no card, y ≈ 54–86, x 89–1340, controls 32 px tall. Left to right:
   - the **recording selector**, a white bordered button ≈ 355 px wide. It holds a blue database icon, the bold
     mono file name `M2_aug_concat_fs1.mat`, the muted mono `16 ch · 721 h · 1 Hz`, and a chevron;
   - the **pager**, `‹ 1 / 5 ›`;
   - a vertical divider;
   - the muted label `time`, then a **RangeSlider** ≈ 130 px with two blue square handles at the ends, then the
     **value chip** `0 – 721 h` (white box);
   - the **bin select** `bin  auto · 12.6 h ▾` (white box);
   - a vertical divider;
   - the muted label `colour by`, then a **Seg** on a grey track with `annotations · detections · both · disagree`
     (`both` is selected and shows as a white pill).
3. **COVERAGE MAP card**: x 89–1087 (≈ 998 w, ≈ 73 % of content), y 109–807 (≈ 698 h).
   - **Head.**
     - Left: `COVERAGE MAP` in mono caps, muted; then `16 channels · 0 – 721 h · bin 12.6 h`.
     - Right: `both · spans per bin` over the ramp legend `low ▢▢▢▢▢▢ high`, which uses six swatches from grey to blue.
     - Far right: an (i) square button, ≈ 30 × 26.
   - **Column label** `channel` (mono, muted) above the row labels.
   - **Matrix.** 16 rows of about 39 px each, with a mono label column ≈ 64 px (`CH1_A1` … `CH16_D2`) and 57
     rounded cells per row, ≈ 15 × 32 px at radius 2. The selected row `CH4_A2` has a blue 1.5 px rounded outline
     and a blue label.
   - **X axis** `0 h 120 h 240 h 360 h 480 h 600 h 721 h`.
4. **Right rail card**: x 1112–1411 (≈ 299 w), y 109–807. Four sections, each a bold title with a grey (i) and a hairline rule under it.
   - `Show`: checkboxes `annotations` ✓, `detections` ✓, `reviewed coverage` ☐ and `unreviewed only` ☐.
     Unchecked labels are mono and muted.
   - `Detections from`: two full-width grey select fields, `runs  all · 34 ▾` and `method  any · 7 ▾`.
   - `Verdict`: checkboxes, each with a colour dot.
     - `seed` ✓, blue dot
     - `interesting` ✓, green dot
     - `not_interesting` ☐, grey dot
     - `artifact` ☐, red dot
     - `unsure` ☐, amber dot
   - `Morphology tag`: checkboxes `sharkfin` ✓, `spike-train`, `slow-drift`, `burst`, `plateau`, `biphasic`.
   - **Foot** (pinned to the bottom): the muted `matching (i)`, with the bold `412 spans` right-aligned, and the muted
     line `across 11 of 16 channels` under it.
5. **Bottom bar card**: x 89–1411, y 826–881 (≈ 55 h).
   - Left: `CH4_A2` in bold, then the muted mono `708 annotations · 1284 detections · 184 disagree · 62 % reviewed`.
   - Right: a secondary button with a table icon, `Cross-channel from CH4_A2`, then the primary blue `Open CH4_A2 →`.
6. **Recordings popover** (frame 1b), anchored under the selector: x 89–648, y 93–383 (≈ 560 × 290), radius 10, with a shadow.
   - **Search field.** A full-width grey field with a magnifier and the placeholder `filter recordings`.
   - **Table header** (mono, muted): `recording · ch · length · fs · status`.
   - **Rows** (≈ 34 px each, each with a database icon):
     - the selected row has a blue tint and a check in place of the icon;
     - the status column shows `⇄ linked fs2` or `⇄ linked fs1` in muted mono;
     - an inferred sampling rate shows `10 Hz?` in amber, with the status `fs inferred` in amber;
     - the held-out row has a lock icon, is muted overall and reads `held out · locked`.
   - **Footer** (after a hairline):
     - left, the blue link `+ Import a recording in Settings › Datasets`;
     - right, the muted mono `‹ › page through recordings`.
7. **Map legend popover** (frame 1b), anchored to the (i): x 736–1075, y 150–383 (≈ 340 × 235).
   - **Title:** `Reading the coverage map`.
   - **Three swatch rows:**
     - a ramp swatch: `Cell darkness is spans per bin, counted under 'colour by'. Grey cells hold none.`
     - a blue-outlined rect: `Outlined row is the selected channel. Click to select, double-click to open.`
     - a swatch: `Disagree mode: amber where a detection has no overlapping annotation or the reverse.`
   - **Footnote:** a hairline, then italic muted text: `A tag that clusters on two channels is a lead; one spread evenly is probably not.`

### Controls & interactions
| control | kind | behaviour in the shell |
|---|---|---|
| Recording selector | button → Popover | Opens the recordings popover. **Live today it is a native `<select>`** — replace it with the popover and keep `data-testid="recording-select"` on the trigger. |
| `filter recordings` | Text field | Substring filter over name or file. No match → `no recording matches "<q>"`. |
| Recording row | Table row (single select) | Selects the recording (live: `setExplore({file, channelId:null, view:null})`) and closes the popover. |
| M4 row | Table row, disabled | DisabledReason `held out · locked (D6) — Settings › Datasets`. The LockedCard stays for deep links (`?rec=`) and for the pager. |
| `⇄ linked fs2` | text + tooltip | `same recording resampled at 2 Hz — counts are not independent (B30)`. No action. |
| `+ Import a recording in Settings › Datasets` | link | Navigates to `#/settings/datasets?modal=import` (Settings inventory, frame settings-01b). |
| `‹` `›` (pager) | icon buttons | Previous or next recording across all 5, M4 included (it lands on the locked state). **Live counts only non-held-out files (`1 / 4`)** — change to all 5 to match the frame. Disabled at the ends. |
| `time` RangeSlider + `0 – 721 h` chip | RangeSlider + NumberField chip | Crops the drawn bins client-side to [t0, t1] (no core call); the axis and `0 – 721 h` in the card head update. Click the chip to type `a – b` (rule: 0 ≤ a < b ≤ duration, in h; message `range must be inside 0 – 721 h`). **Live: an inert placeholder.** |
| `bin auto · 12.6 h ▾` | Select | Options: `auto · 12.6 h` (57 bins), `25.8 h` (28), `6.3 h` (114). Live already works through `getCoverage(file, bins)`. |
| `colour by` Seg | Seg (4) | Switches the matrix (live, persisted). In `disagree` the ramp becomes **amber** (frame legend; §3 amber = differs). **Live uses the blue ramp for all four** — add an amber ramp. Keep the buttons' accessible names exactly `annotations` / `detections` / `both` / `disagree` (smoke.py clicks by exact role name). |
| (i) on the map | InfoTip → Popover | Opens `Reading the coverage map`. Move the live caption paragraph under the map into this popover (P9). |
| Matrix row | Table-like row | Click selects (live). **Double-click opens** `#/explore/signal/<id>` (legend copy; missing live). Enter or Space selects (live); add `Enter` on a selected row → open. Hover shows the tooltip `CH4_A2 · 341–354 h · 12 spans` (live). |
| `Show` checkboxes | Checkbox | `annotations` and `detections` are live. `reviewed coverage` overlays a hatched grey on unreviewed bins; `unreviewed only` counts only spans without a verdict. Both are fixture-backed (`demo`), in-memory. **Live: disabled.** |
| `runs all · 34 ▾` | Select (multi) | Checklist of the recording's runs (fixture canon + live `/api/runs?recording_id`). Changing it recolours the detections matrix in memory (fixture) and reads e.g. `runs 3 of 34`. **Live: a single-option select, inert.** |
| `method any · 7 ▾` | Select (multi) | The 7 methods (fixture). **Live: inert.** |
| Verdict checkboxes | Checkbox + colour dot | Live: the `verdicts=` query refetches coverage. Keep the live count column (not in the frame); render it muted. |
| Morphology tag checkboxes | Checkbox | Fixture-backed: filters the matching readout and the fixture matrix. **Live: disabled with `no tags in this database`** — keep that honest text when the live DB has no tags, and enable fixture filtering only in demo regions. |
| (i) on each rail section | InfoTip | P9 popovers (copy in Copy below). |
| `matching 412 spans · across 11 of 16 channels` | KeyValue readout | Recomputes on every filter change (live computes from the drawn matrix). |
| `Cross-channel from CH4_A2` | button (secondary, table icon) | Navigates to `#/explore/cross-channel/<channelId>`. **Live: inert.** Disabled with no selection (`select a channel first`) and on M4. |
| `Open CH4_A2 →` | button (primary) | Navigates to `#/explore/signal/<channelId>` (live, testid `open-channel`). Disabled reasons: `select a channel first`, `held out · locked`. |

Keyboard: none is shown on this frame. Add `Enter` (open the selected row) and `Esc` (close the popover).

### Plots
- **Coverage map** (Heatmap / Raster-Matrix). Rows are channels and columns are time bins, with x in **hours since
  recording start** (`0 h` … `721 h`, 7 ticks).
  - **Marks.** One rounded rect per (channel, bin).
  - **Colour.** A 6-step ramp: index 0 is grey `#F1F3F5` ("none"), then five blues to `#0A84FF`. The level is the
    quantile rank among non-zero cells (live).
    - In `disagree` mode, use an amber ramp with the same steps.
    - The frame legend reads `low … high`; drop the live extra word `· quantiles` from the chip and put it in the legend popover.
  - **Selection.** A blue rounded outline around the selected row.
  - **Feeds.** Live `/api/corpus/{file}/coverage` (`CoverageRow.annotations|detections|both|disagree`). Fixture
    fallback: `corpusCoverage[recordingId]` (16 × 57).
  - **Cap.** P8 does not apply (rows = channels ≤ 16). For more than 16 channels the card scrolls vertically.

### Fixtures
```ts
// SHARED canon (lives in the shared canon fixture)
interface Recording { id: string; name: string; file: string | null; fs: number; fsSource: 'read'|'inferred';
  nChannels: number; durationH: number; start: string; heldOut: boolean; linkedTo?: string }
// §0: M2_aug fs1 (file M2_aug_concat_fs1.mat, 1 Hz, 16 ch, 721 h, 2025-08-02 14:00, linkedTo fs2)
//     M2_aug fs2 (file M2_aug_concat_fs2.mat, 2 Hz, 16 ch, 721 h, linkedTo fs1)
//     M3_jul (1 Hz, 8 ch, 280 h) · L_LM_Jul26_J (10 Hz inferred, 5 ch, 22.4 h) · M4_aug (1 Hz, 16 ch, 300 h, heldOut)
interface Channel { id: number; recordingId: string; name: string; index: number }   // SHARED; names per §0
interface Run { id: string /* '#128' | 'r-0412' */; name: string; method: string; template?: string;
  surrogate?: boolean; recordingId: string; channelIds: number[]; detections: number }   // SHARED
type Verdict = 'seed'|'interesting'|'not_interesting'|'artifact'|'unsure'                // SHARED vocabulary
const VERDICT_COLOUR = { seed:'#0a84ff', interesting:'#22a06b', not_interesting:'#8a97a8', artifact:'#e5484d', unsure:'#e8900c' }
const MORPHOLOGY_TAGS = ['sharkfin','spike-train','slow-drift','burst','plateau','biphasic']  // SHARED

// Explore-local
interface ChannelCoverage { channelId: number; annotations: number[]; detections: number[]; both: number[];
  disagree: number[]; reviewed: boolean[]; counts: { annotations: number; detections: number; disagree: number; reviewedPct: number } }
interface CorpusFixture { recordingId: string; bins: 57; binH: 12.6; rows: ChannelCoverage[];
  runsTotal: 34; methodsTotal: 7; matching: { spans: 412; channels: 11; of: 16 } }
// CH4_A2 counts: annotations 708 · detections 1284 · disagree 184 · reviewedPct 62
```
- **Fixture ids.** Fixture channel ids should mirror the live DB's numeric ids, so the same routes work.
  `smoke.py` uses `4` = CH4_A2 of M2_aug fs1 and `52` = a held-out M4 channel. Proposed mapping: fs1 1–16,
  fs2 17–32, M3_jul 33–40, L_LM 41–45, M4 46–61 (so 52 = M4 CH7_B2). The order still needs checking against live `/api/recordings` (Fog).

### Copy
- **Toolbar.** `M2_aug_concat_fs1.mat` · `16 ch · 721 h · 1 Hz` · `1 / 5` · `time` · `0 – 721 h` · `bin` `auto · 12.6 h` · `colour by` · `annotations` `detections` `both` `disagree`.
- **Map card head.** `COVERAGE MAP` · `16 channels · 0 – 721 h · bin 12.6 h` · `both · spans per bin` · `low` `high` · `channel`.
- **Rail titles and options.**
  - `Show`: `annotations`, `detections`, `reviewed coverage`, `unreviewed only`.
  - `Detections from`: `runs all · 34`, `method any · 7`.
  - `Verdict`: `seed`, `interesting`, `not_interesting`, `artifact`, `unsure`.
  - `Morphology tag`: `sharkfin`, `spike-train`, `slow-drift`, `burst`, `plateau`, `biphasic`.
  - Foot: `matching` · `412 spans` · `across 11 of 16 channels`.
- **Bottom bar.** `CH4_A2` · `708 annotations · 1284 detections · 184 disagree · 62 % reviewed` · `Cross-channel from CH4_A2` · `Open CH4_A2 →`.
- **Recordings popover.** `filter recordings` · `recording` `ch` `length` `fs` `status` · `⇄ linked fs2` · `⇄ linked fs1` · `fs inferred` · `held out · locked` · `Import a recording in Settings › Datasets` · `‹ › page through recordings`.
- **Legend popover.** The title and three lines as quoted in Regions item 7, plus the italic footnote.
- **Rail InfoTip copy** (proposed; P9 content not in the frame):
  - Show: `What the map counts. Reviewed coverage shades bins someone has looked at.`
  - Detections from: `Only detections from these runs and methods are counted.`
  - Verdict: `Annotations with these verdicts are counted. Verdicts are given in Review.`
  - Morphology tag: `A tag that clusters on a few channels is a lead.`
  - matching: `Spans that pass every filter, and how many channels they fall on.`

### Live vs demo (Corpus)
| region / control | frame | live today | build action |
|---|---|---|---|
| Header, subtitle | 1 | present | keep |
| Recording selector | 1, 1b | **present but a native `<select>`**; no menu table, no linked or inferred status, no Import link | replace with the popover (1b) |
| Pager `1 / 5` | 1 | present; counts 4 (skips M4) | count all 5 |
| time RangeSlider | 1 | **inert** placeholder; the chip is static | client-side crop |
| bin select | 1 | **live** (28 / 57 / 114 bins) | restyle as a Select chip |
| colour-by Seg | 1 | **live** | add the amber disagree ramp |
| Coverage map | 1 | **live** (Heatmap SVG, quantile ramp, tooltip, click and keyboard select, selected outline) | add double-click → open; keep testids `corpus-heatmap`, `heatmap-cell`, `heatmap-row-<name>` |
| Map (i) + legend popover | 1b | **missing**; a caption paragraph is used instead | add; move the caption into it |
| Ramp legend | 1 | present, reads `… high · quantiles` | drop `· quantiles` |
| Show: annotations / detections | 1 | **live** | keep |
| Show: reviewed coverage / unreviewed only | 1 | **inert** (disabled) | fixture-backed (`demo`) |
| Detections from: runs | 1 | **inert** (one option, shows the live run count) | multi Select: live runs + fixture |
| Detections from: method | 1 | **inert** | fixture Select (`demo`) |
| Verdict checkboxes | 1 | **live** (refetch by `verdicts=`), with an extra count column | keep |
| Morphology tag | 1 | **inert** (`no tags in this database`) | fixture-backed filter (`demo`); keep the honest live text |
| (i) per rail section | 1 | title-attribute only | InfoTip popovers |
| matching readout | 1 | **live** | keep |
| Bottom bar counts | 1 | **live**; honest `— disagree (no detections)` | keep |
| `Cross-channel from …` | 1 | **inert** | navigate to cross-channel |
| `Open … →` | 1 | **live** (`open-channel`) | keep |
| Held-out LockedCard | — | **live** (server's refusal text) | keep; not in the frames |

### Frame ⟷ spec conflicts
1. **Frame 1b recording rows disagree with §0.**

   | frame 1b row | §0 canon |
   |---|---|
   | `Mushroom_260720 8 96 h 10 Hz` | `M3_jul` · 8 ch · 280 h · 1 Hz |
   | `L_LM_Jul_26_J 5 48 h 10 Hz?` | `L_LM_Jul26_J` · 5 ch · 22.4 h · 10 Hz inferred |
   | `M4_aug_concat_fs1.mat 16 721 h 1 Hz held out` | `M4_aug` · 16 ch · 300 h · 1 Hz · held out |

   **§0 wins** for fixtures. Live data shows whatever the DB holds.
2. **The map-legend swatch for Disagree is red, but its text says amber.** Draw it amber, since §3 makes amber the
   colour for "differs".
3. **The map card is titled `COVERAGE MAP` while the spec calls it a "density map".** Use the frame copy.
4. **The rail's morphology tags include class names** (`spike-train`, `slow-drift`, `burst`, `plateau`), while §0
   says morphology tags are separate from classes. §5.1 lists exactly this set, so keep the frame and spec list;
   see Fog.
5. **`runs all · 34` / `method any · 7` are recording-wide**, whereas the Signal page says `6 runs · 4 methods`
   for the channel. The two are consistent once the scopes are labelled that way.

---

### Fog (Corpus)
- **F1.** The live DB's recordings and channel ids are not the §0 canon. The fixture-id mapping (fs1 1–16 … M4 46–61)
  is a proposal: confirm the live `/api/recordings` order so `#/explore/signal/4` and `/52` mean the same thing in
  both modes.
- **F2.** `reviewed coverage`, `unreviewed only`, `method`, morphology tags and per-run filtering have no bridge
  endpoint (no core changes tonight), so they are fixture-only. The live coverage payload carries none of them.
- **F3.** `62 % reviewed`: the live `reviewed_pct` is frequently `null` (it shows `—`), and "reviewed" is undefined
  for detections without adjudications. The spec gives no definition.
- **F4.** The canon has no file names for `M3_jul`, `L_LM_Jul26_J` or `M4_aug`. The popover's `recording` column
  shows the display name for those.
- **F5.** Tag vocabulary: §0 says morphology tags are separate from classes, yet §5.1 and the frame list class names
  as tags. Settings › Vocabulary owns the answer.

## explore.signal

### Route & states
- `default` (frame 2). Route `#/explore/signal/<channelId>`.
  - **Viewport.** For CH4_A2 of M2_aug fs1, open on `276.4 – 278.4 h` (live seeds `[995040, 1002240]` s).
  - **Motif.** `MOTIF_233` selected, via `?motif=233`. Without it, the live default is no motif (`no-motif`).
- `detections-picker` (frame 2a). Click the `detections 6 runs · 4 methods` chip, or `?popover=detections`.
- `span-legend` (frame 2a). Click the (i) at the top right of the SPAN card, or `?popover=span-legend`.
  - The frame shows both popovers at once. Build them one at a time and take two screenshots.
- `drawer-annotations` (frame 2b). Reached by any of:
  - clicking the `Annotations 708` ribbon or the `Filters & search` ribbon (the latter also focuses the filters, see D1);
  - `D` (opens the last tab, Annotations by default) or `1`;
  - `?drawer=annotations`.
- `drawer-detections` (frame 2c). The `Detections 1284` ribbon, `2`, or `?drawer=detections`.
- `drawer-shortcuts` (frame 2d). The `Keyboard shortcuts` ribbon, `3`, `?`, or `?drawer=shortcuts`.
- `drawer-filters-collapsed` (no frame). The chevron beside `Filters` hides the filter grid (`&filters=closed`).
- `no-motif` (live). The MOTIF card head reads `no motif selected · click a band in the span, or use ‹ ›`; `Send motif to Analyse` and `Review this motif` are disabled with the reason `select a motif first`.
- `tag-input` (live). `+ tag` becomes an inline text input (Enter commits, Esc cancels).
- `held-out` (live). `#/explore/signal/52` shows a LockedCard with the server's 423 text. Smoke asserts "held out".
- `loading` (live skeletons) · `error` (live ErrorCard per tier; an ErrorBoundary per tier).

### Regions (1440 × 900, frame 2)
Content column x 89–1351 (≈ 1262 w; the Signal frames leave about 90 px free at the right, unlike Corpus). Cards are stacked with ≈ 14 px gaps; the page scrolls slightly (the ribbons are cut at y 900).
1. **Header**, per Shell.
2. **Top bar** (no card; y ≈ 55–85), left to right:
   - breadcrumb `Corpus › M2_aug_concat_fs1.mat › CH4_A2` (mono; `Corpus` a link; the current crumb darker);
   - a Seg centred at x ≈ 584–773: `Signal` (selected, white pill) · `Cross-channel`;
   - a Select chip ≈ 235 px: `detections  6 runs · 4 methods ▾`;
   - a Select chip ≈ 120 px: `display  raw ▾`;
   - a square (i) InfoTip button;
   - flush right, the blue mono link `‹ back to corpus`.
3. **CHANNEL card**: y 109–261 (≈ 152 h).
   - **Head.** `CHANNEL  0 – 721 h` (mono caps, muted), with a square (i) at the right.
   - **Trace area.** ≈ 62 px tall on a light grey ground, holding the black envelope.
   - **Selected-span box.** A translucent blue rect with a blue 1 px border, and two blue vertical **grip handles**
     (≈ 8 × 30, radius 3, white centre groove).
   - **Coverage ribbon** (8 px) under the trace: rounded segments of green, amber, green, red, amber and grey.
   - **Detection-density ribbon** (≈ 14 px): about 48 blue bars.
   - **Axis** `0 h 120 h 240 h 360 h 480 h 600 h 721 h`.
4. **SPAN card**: y 275–516 (≈ 241 h).
   - **Head.** `SPAN  276.4 – 278.4 h · 2.0 h`. At the right: `‹ 233 / 344 ›`, then three bordered icon buttons
     (zoom out, zoom in, fit/expand), then (i).
   - **Plot** ≈ 150 px, on a light grey ground with mV labels `+0.4 mV`, `0`, `−0.4 mV` at the left and a black trace.
   - **Six motif bands, left to right:**
     1. detected: translucent blue fill with a pale cap;
     2. annotated: translucent green fill with a solid green cap;
     3. selected: translucent orange fill with an orange outline and solid orange cap, labelled `MOTIF_233` in orange
        inside at the top left;
     4. annotated;
     5. detected, with a pale cap;
     6. annotated.
   - **Axis** `276.4 h 276.9 h 277.4 h 277.9 h 278.4 h`.
   - **Legend** under it: `● detected ● annotated ● selected`.
5. **MOTIF card**: y 531–733 (≈ 202 h).
   - **Head.** `MOTIF_233  277.312 – 277.318 h · 21.6 s · detected, unadjudicated`. At the right: a Select
     `context ±20 s ▾`, a teal-checked checkbox `overlay F-03 medoid`, then (i).
   - **Plot** ≈ 128 px with mV labels. It holds:
     - the orange trace;
     - a teal medoid trace over the motif region only;
     - the motif region tinted orange between two red vertical lines labelled `ONSET` and `END` in red mono;
     - the axis `−10 s  0 s  +10 s  +30 s  +40 s`.
   - **Footer.**
     - Left: `nearest family ` then the teal link `F-03 →`, then ` d 0.19 · tagged sharkfin · unadjudicated`.
     - Right: the secondary `Send motif to Analyse →` and the primary `Review this motif →`.
6. **Span-action card**: y 747–852 (≈ 105 h).
   - **Left block:**
     - line 1 (muted mono): `Selected span  276.4 – 278.4 h · 2.0 h · 6 motifs in view`;
     - line 2: `tags`, then the chips `sharkfin` (blue outline, selected), `burst` (grey) and `+ tag`;
     - line 3: `note`, then a grey input holding `recurs on CH3 at similar amplitude — check ground`.
   - **Right block:** the buttons `Save span`, `Send span to Analyse →` and primary `Take span for Review →`, with
     the caption under them `saving stores tags and note only · verdicts are given in Review`.
7. **Ribbon row**: y 866–900+. Four equal cards (≈ 305 w, 36 h), each a clickable row with a `›` chevron:
   `Filters & search` · `Annotations 708` · `Detections 1284` · `Keyboard shortcuts`.
8. **Detections picker popover** (frame 2a), anchored under the detections chip, right-aligned: x 858–1278, y 91–423 (≈ 420 × 330).
   - **Title row.** `Show detections from`, with the blue links `select all · none` at the right.
   - **Seg:** `by run` (selected) · `by method` · `by template`.
   - **Six rows**, each ≈ 37 px, holding a checkbox, a colour swatch, the bold mono name with the id, a muted
     sub-caption (the method) and a right-aligned count. The checked rows have a light blue tint.
   - **Footer** (after a hairline): checkboxes `colour by run` ✓ · `hide surrogates` ✓ · `unadjudicated only` ☐.
9. **Span legend popover** (frame 2a), anchored to the SPAN card's (i). The frame places it over the span plot at x 510–840, y 318–586 (≈ 330 × 270).
   - **Title:** `Reading the span`.
   - **Four swatch rows:** blue, green, orange, and a dark grey swatch for "cap only, no fill".
   - **Footnote:** a hairline, then the muted coverage-ribbon key.
10. **Drawer** (frames 2b–2d). An overlay card over the lower screen, anchored under the CHANNEL card at
    y 291–713 (≈ 422 h), x 89–1351. The overview stays put.
    - **Tab row:**
      - a `⌄` collapse chevron;
      - Tabs `Annotations 708` · `Detections 1,284` · `Shortcuts` (the active tab is a blue-tinted pill; counts are muted);
      - at the right, the bordered buttons `Export CSV ⤓` and `Export JSON ⤓` (these are absent on Shortcuts), then the blue link `collapse`.
    - **Below the drawer.** A compact `MOTIF_233` strip card (y 731–852): a mono label and the orange trace, with no
      axes or buttons. It is the motif tier peeking out; the span and action tiers sit under the overlay.
    - **Annotations tab** (2b):
      - **Filters header.** `⌄ Filters`, a blue pill `3 active`, the blue link `clear`; at the right, the muted `412 of 708 annotations match`.
      - **Filter grid.** 5 columns × 2 rows, each column ≈ 237 px. Each cell is a mono label with (i) over a
        full-width select, ≈ 26 h. Active filters get a blue tint and blue text.
        - row 1: `verdict` [`interesting`]* · `source` [`any`] · `element` [`any`] · `quality` [`any`] · `structure` [`any`]
        - row 2: `status` [`any`] · `spike-train length` [`any`] · `duration band` [`medium`]* · `id` [placeholder `e.g. 42, 108`] · `note / tags` [`sharkfin`]*
      - **Table.** A select-all checkbox, then the columns `id ⇅` · `start · sample ↓` (sorted, blue) ·
        `end · sample ⇅` · `duration ⇅` · `verdict ⇅` · `tags ⇅` · `source ⇅` · `note ⇅`. Six rows ≈ 25 h; the
        checked rows are blue-tinted. The verdict text is coloured (interesting green, seed blue,
        not_interesting grey, artifact red).
      - **Footer.**
        - Left: `2 selected`, then the bordered buttons `Add tag 🏷` and `Stage for Analyse ≋`.
        - Right: `1–6 of 412 ‹ ›`, then the primary `Send selected to Review →`.
    - **Detections tab** (2c). Same structure.
      - **Filters header.** `2 active`, `clear`, and at the right `96 of 1,284 detections match`.
      - **Filter grid.**
        - row 1: `run` [`all · 34`] · `method` [`matrix profile`]* · `score ≥` [`0.60`]* · `adjudication` [`any`] · `nearest family` [`any`]
        - row 2: `duration band` [`any`] · `overlaps annotation` [`either`] · `channel` [`CH4_A2 only`] · `id` [placeholder `e.g. 412`] · `scope` [`visible span`]
      - **Table.** Columns `id ⇅` · `run ⇅` · `method ⇅` · `start · sample ⇅` · `end · sample ⇅` · `score ↓`
        (sorted, blue) · `adjudication ⇅` · `family ⇅`. Adjudication colours: unadjudicated amber, interesting green,
        artifact red, not_interesting grey.
      - **Footer.**
        - Left: `2 selected` and the bordered `Analyse events →`, with the muted info line `ⓘ machine detections · indices are samples into the whole recording`.
        - Right: `1–6 of 96 ‹ ›`, then the primary `Send selected to Review →`.
      - **No tagging.** There is no `Add tag` or `Stage for Analyse` here: detections are machine-only (§4.1).
    - **Shortcuts tab** (2d):
      - **Top line.** Left, the muted `ⓘ verdict keys live in Settings › Vocabulary and apply in Review`; right, the
        blue link `Edit shortcuts in Settings › Keyboard & behaviour →`.
      - **Four columns**, each ≈ 290 px, with a bold title and a hairline under it: `Navigate` · `Select` · `Hand off` · `Panels`.
      - **Rows**, each ≈ 38 px: a grey keycap, then the description.
      - The lower ≈ 110 px of the drawer is empty (B29 flags this; acceptable).

### Controls & interactions
| control | kind | behaviour in the shell |
|---|---|---|
| `Corpus` crumb | link | `#/explore/corpus` (live, `crumb-corpus`). |
| `M2_aug_concat_fs1.mat` crumb | link | `#/explore/corpus?rec=<id>` (live: plain text). |
| `Signal` / `Cross-channel` Seg | Seg | `Cross-channel` navigates to `#/explore/cross-channel/<channelId>?window=motif-<n>` (live: inert). |
| `detections 6 runs · 4 methods ▾` | Select chip → Popover | Opens the picker (2a). **Live today:** it opens a runs *table* from `GET /api/runs?recording_id` (`detection-runs-chip` / `-popover`). Replace it with the checklist, fed by live runs (name, id, `n_detections`) merged with fixture methods and templates. The chip text recomputes: `<checked runs> runs · <distinct methods> methods`. |
| Picker Seg `by run / by method / by template` | Seg | Regroups the same rows: by method gives 5 method rows with summed counts; by template, template rows (`drop_motifs9`, `mp_drops_v3`, …). |
| Picker row checkbox | Checkbox | Shows or hides that run's bands in the SPAN tier and the density ribbon, as a client-side filter on `Detection.run_id` (no core change). |
| `select all` · `none` | links | Check or uncheck every row; with none checked the span shows annotations only. |
| `colour by run` | Checkbox | Detected bands take the run's swatch colour instead of blue (legend line 1). |
| `hide surrogates` | Checkbox | Hides runs flagged `surrogate` (#129) from the list and the plot. |
| `unadjudicated only` | Checkbox | Hides detected bands that have an adjudication (fixture adjudications). |
| `display raw ▾` | Select | Options `raw` (default) and `detrended (display only)` (proposed, see Fog). Live is inert, and raw mV is what is drawn. |
| (i) top bar | InfoTip | Page help: `Three tiers on one time axis: the channel, the span you chose, the motif you opened.` |
| Overview box body | draggable (DraggableSpanBox) | Drag moves the span; a click on the trace recentres it (live). `← →` nudge one bucket, Shift ×10 (live). |
| Overview grips | draggable handles | Drag resizes, with a minimum of 60 s (live, `span-handle-left/right`). |
| Overview (i) | InfoTip | `Drag the blue box or its grips to choose the span below. Ribbons: review coverage, then detection density.` Move the live caption here (P9). |
| `‹ 233 / 344 ›` | icon buttons | Previous or next motif, centring the viewport (live, `motif-prev/next`). `[` `]` too. |
| zoom out / zoom in / fit | icon buttons | Live `zoom-out` / `zoom-in` / `zoom-fit`; fit shows the whole channel. |
| SPAN plot | pan/zoom surface | Drag pans, the wheel zooms about the cursor, `← →` pan, `+ −` zoom (live). Clicking a band selects that motif (live). |
| SPAN (i) | InfoTip → Popover | `Reading the span` (2a). **Missing live.** |
| `context ±20 s ▾` | Select | ±10 / ±20 / ±60 s (live, `motif-context`). |
| `overlay F-03 medoid` | Checkbox | Draws the teal (#30B0C7) medoid trace from the fixture in mV. Enabled when the motif has a nearest family; otherwise disabled with the reason `no family near this motif`. **Live: disabled, `no families in this database`**, which stays the text when neither live nor fixture has a family. |
| MOTIF (i) | InfoTip | `The opened motif with context. Onset and end are the stored span edges.` |
| `F-03 →` | link | Library family page (the Library inventory owns the route, e.g. `#/library/family/F-03`). |
| `Send motif to Analyse →` | button | Live: `setSource` with the motif's sample range, a Toast, then `#/analyse/chain` (`send-motif`). |
| `Review this motif →` | button (primary) | In-memory: stage the motif into the `Explore spans` queue, then Toast `MOTIF_233 staged for Review · Explore spans queue` with the action `Open Review →`. Shortcut `Shift + R`. Live: inert. |
| `sharkfin` / `burst` chips | Chip (removable) | Clicking a chip toggles selected or removes it (live: × removes). |
| `+ tag` | Chip → inline input | Live (`add-tag` / `tag-input`). Autocompletes from the morphology tags. Validation: no duplicates, and 1–32 characters of `[a-z0-9-]` (message `tags are lower-case words joined by -`). Shortcut `T` focuses it. |
| `note` | Text field | Live (`span-note`). Up to 500 characters, with a counter from 400. |
| `Save span` | button | In-memory write of {range, tags, note} to `explore.savedSpans`, then Toast `span saved · tags and note only`. Live is a stub toast; keep `save-span`. |
| `Send span to Analyse →` | button | Live (`send-span`): source = viewport range, then navigate to Analyse. Smoke asserts the navigation. Shortcut `A`. |
| `Take span for Review →` | button (primary) | In-memory stage, then Toast `span staged for Review · Explore spans queue` with `Open Review →`. Shortcut `R`. Live: inert. |
| Ribbons ×4 | clickable cards | Each opens the drawer on its tab; `Filters & search` opens Annotations with the filters expanded and the first filter focused (D1). **Live today:** Annotations and Detections open inline tables of the spans *in view*, and the other two show "out of slice scope" notes. Keep the testids `ribbon-<key>`. |
| Drawer `⌄` / `collapse` | icon button / link | Close the drawer (also `D`, `Esc` when focus is inside). |
| Drawer Tabs | Tabs | Switch tab; the `1 2 3` keys; the URL `?drawer=`. The header subtitle updates. |
| `Export CSV` / `Export JSON` | buttons | Client-side Blob download of the **filtered** rows (every page, not just 1–6), named `CH4_A2_annotations.csv` or `CH4_A2_detections.json`. No core call. |
| `⌄ Filters` | disclosure | Collapse or expand the grid. |
| `3 active` | Badge | The count of non-default filters. |
| `clear` | link | Reset every filter to `any` (the id field empties). |
| `verdict` | Select (multi) | The 5 verdicts plus `any`. |
| `source` | Select | `any` · `manual_ui` · `imported_10min`. |
| `element` / `quality` / `structure` / `status` / `spike-train length` | Select | Fixture options (Fog: vocabulary undefined). Each is DisabledReason `not in this database` when the drawer is backed by live spans only. |
| `duration band` | Select | `any` · `short (< 60 s)` · `medium (60–900 s)` · `long (> 900 s)` (proposed bands; Fog). |
| `id` (annotations) | Text field | Comma-separated integers. Rule `/^\s*\d+(\s*,\s*\d+)*\s*$/`, message `ids are whole numbers separated by commas`. |
| `note / tags` | Text field with suggestions | Substring over note and tags. |
| `run` | Select (multi) | The recording's runs: `all · 34`, or `n of 34`. |
| `method` | Select (multi) | The 7 methods. |
| `score ≥` | Number field | Range 0–1, step 0.01. Message `score is between 0 and 1`. |
| `adjudication` | Select | `any` · `unadjudicated` · the verdicts. |
| `nearest family` | Select | `any` · `none` · F-03 · F-04 · F-07 · F-11. |
| `overlaps annotation` | Select | `either` · `yes` · `no`. |
| `channel` | Select | `CH4_A2 only` · `all channels`. |
| `id` (detections) | Text field | Same rule as the annotations `id`, placeholder `e.g. 412`. |
| `scope` | Select | `visible span` · `whole channel`. |
| Column headers | sortable Table | Click sorts (↓ ↑); one sort key. The frame defaults: annotations `start · sample ↓`, detections `score ↓`. |
| Row checkbox / header checkbox | selectable Table | Selection count in the footer; the header box selects the page, with a follow-up link `select all 412` (proposed). |
| Row click | Table row | Selects that span as the motif, centres the viewport and highlights the band (live already does this for the in-view tables). |
| `Add tag 🏷` | button → Popover | A tag input, applied in-memory to the selected annotations. Disabled with no selection: `select rows first`. |
| `Stage for Analyse ≋` | button | In-memory staging list, then Toast `2 annotations staged for Analyse`. Disabled with no selection. |
| `Analyse events →` | button | Toast `not wired yet: send 2 detections to Analyse as a SpanSet source (POST /api/chain/source)`. Disabled with no selection. |
| `‹ ›` pager | icon buttons | 6 rows per page in the frame. Recommendation: the drawer shows 6 rows at its fixed height; disabled at the ends. |
| `Send selected to Review →` | button (primary) | In-memory, then Toast `2 spans sent to Review · Explore spans queue` (annotations) or `2 detections sent to Review` (detections) with `Open Review →`. Disabled with no selection: `select rows first`. |
| `Edit shortcuts in Settings › Keyboard & behaviour →` | link | `#/settings/keyboard` (the Settings inventory owns the exact sub-route). |

**Keyboard shortcuts (frame 2d).** All are active on the Signal page, but not while typing in an input.

| column | key | action |
|---|---|---|
| Navigate | `← →` | pan the span (live) |
| Navigate | `+ −` | zoom (live) |
| Navigate | `F` | fit (Fog: "fit span to view") |
| Navigate | `[ ]` | previous / next motif |
| Navigate | `Home` | back to corpus |
| Select | `drag` | move the span box |
| Select | `Shift + drag` | resize from the nearest handle |
| Select | `Alt + click` | select a motif marker |
| Select | `Ctrl + A` | select all motifs in view: drawer rows in scope, a Toast with the count |
| Select | `Esc` | clear the selection |
| Hand off | `R` | take span for Review |
| Hand off | `Shift + R` | review the selected motif |
| Hand off | `A` | send span to Analyse |
| Hand off | `T` | add tag |
| Hand off | `C` | cross-channel from this span |
| Panels | `D` | toggle the drawer |
| Panels | `/` | open the drawer on Annotations and focus its first filter |
| Panels | `L` | toggle the span legend popover |
| Panels | `1 2 3` | drawer tabs |
| Panels | `?` | Shortcuts tab |

### Plots
- **Channel overview** (Trace + BandStrip ×2).
  - **X axis:** hours since recording start, 0–721 h. **Y:** the envelope in mV, unlabelled.
  - **Marks:** a min/max envelope path; the span box with grips; the coverage ribbon as rounded runs of equal colour; the density bars.
  - **Coverage-ribbon legend** (per the 2a footnote): green reviewed · amber partly reviewed · red artifact-dense ·
    grey never reviewed. **Live today** colours the ribbon by the verdict per bucket, which is a different meaning:
    keep live, and add the fixture coverage semantics behind `demo` (Fog F7).
  - **Feeds:** live `GET /api/channels/{id}/window?t0=0&t1=dur&px` and `Channel.ribbons`.
- **Span** (Trace + band layer).
  - **X:** hours (`276.4 h …`, adaptive decimals). **Y:** mV, never normalised, labelled `+0.4 mV / 0 / −0.4 mV`.
  - **Marks:** the envelope path, then the motif bands. Each band is a translucent fill for the full plot height plus
    a 6 px cap above.
    - **Colours:** detected blue, annotated green, selected orange with an outline; artifact red appears live but is
      not in the frame legend (keep it as a fourth legend entry).
    - **Cap only, no fill:** a detection already adjudicated.
    - **Colour by run:** each band takes its run's swatch.
  - **Legend:** `● detected ● annotated ● selected`.
  - **Feeds:** live `useViewport` (window + spans), and the fixture adjudication and run colours.
  - **Cap:** none. A band narrower than 2 px is still drawn (live `minPx=2`).
- **Motif** (Trace + overlay).
  - **X:** seconds relative to the onset (`−10 s … +40 s`). **Y:** mV.
  - **Marks:** the context trace in orange; the teal F-03 medoid overlay aligned at the onset, over the motif span
    only, on the same mV scale (§3, D5); the orange region; the red ONSET and END lines with mono labels.
  - **Feeds:** live `getWindow` for ±context; `families['F-03'].medoid.trace` from the fixture (mV samples, ~21 s).
- **Table cells**: no plots.

### Fixtures
```ts
// SHARED
interface Family { id: 'F-03'|'F-04'|'F-07'|'F-11'|string; name: string; members: number; recordings: string[];
  exemplar?: string; medoid?: string; lengthS?: number; colour: string; medoidTrace?: { dtS: number; mv: number[] } }
// F-03 sharkfin · 112 · [M2_aug fs1, M3_jul, L_LM_Jul26_J] · E-0102 · m-1846 · ~21 s · #30B0C7
// F-04 spike train (#A2845E) · F-07 slow drift 212 (#7A8FA6) · F-11 burst (#C97B63)
interface Run { id: string; name: string; method: string; template: string; surrogate: boolean; colour: string; detectionsOnChannel: number }
// CH4_A2 run list (2a):  #128 drop_motifs9 · matrix profile · 412 · blue      | #129 drop_motifs9 · surrogate · matrix profile · 38 · grey · surrogate
//                        #131 drop_motifs9 · 6σ floor · SAX + threshold · 306 · light blue | r-0415 seed search E-0102 · MASS seed · 92 · purple
//                        r-0412 mp_drops_v3 · drop detector · 410 · orange   | #97 banded_sax_lp · CNN classifier · 26 · grey   (sum 1,284 ✓)
interface ReviewQueue { id: 'q-12'|'q-15'|'q-18'|'q-19'|'explore-spans'; name: string }   // SHARED (Review owns)

// Explore-local
interface AnnotationRow { id: number; channelId: number; startSample: number; endSample: number; verdict: Verdict;
  tags: string[]; source: 'manual_ui'|'imported_10min'; note: string; element?: string; quality?: string;
  structure?: string; status?: string; spikeTrainLength?: string }
interface DetectionRow { id: number; runId: string; method: string; channelId: number; startSample: number; endSample: number;
  score: number; adjudication: Verdict | 'unadjudicated'; family?: { id: string; d: number } }
interface SignalFixture { channelId: 4; viewport: [995040, 1002240]; motifsTotal: 344; motifIndex: 233;
  motif: { label: 'MOTIF_233'; startS: number; endS: number; origin: 'detected'; adjudication: 'unadjudicated'; nearest: { family: 'F-03'; d: 0.19 }; tag: 'sharkfin' };
  spanTags: ['sharkfin','burst']; spanNote: 'recurs on CH3 at similar amplitude — check ground';
  annotations: AnnotationRow[] /* 708 */; detections: DetectionRow[] /* 1,284 */ }
```
- **Frame rows** (2b annotations, sample indices at 1 Hz):
  - 1835 · 50,400–51,000 · interesting · sharkfin · manual_ui · `clean onset`
  - 1578 · 53,400–54,000 · interesting · sharkfin, burst · manual_ui
  - 328 · 56,600–57,200 · seed · sharkfin · manual_ui · `exemplar for F-03`
  - 84 · 58,200–58,800 · interesting · — · imported_10min
  - 9753 · 61,000–61,600 · not_interesting · — · imported_10min
  - 7102 · 63,600–64,200 · artifact · — · imported_10min · `shared ground w/ CH3`
- **Frame rows** (2c detections):
  - 412 · #128 · matrix profile · 995,112–995,134 · 0.91 · unadjudicated · F-03 d 0.19
  - 413 · #128 · 995,410–995,436 · 0.88 · interesting · F-03 d 0.22
  - 418 · #128 · 996,020–996,041 · 0.84 · unadjudicated · —
  - 421 · #131 · SAX + threshold · 996,300–996,318 · 0.77 · artifact · F-07 d 0.41
  - 430 · #131 · 997,005–997,027 · 0.71 · unadjudicated · F-03 d 0.30
  - 433 · #128 · 997,440–997,466 · 0.66 · not_interesting · —
- **Generating the rest.** Fill the remaining rows deterministically (seeded) so the frame's filters yield exactly
  `412 of 708` and `96 of 1,284`, and so the first filtered page is plausible (see Conflicts 3).
- **Durations.** Display `duration` in s (`600 s`), per §0.
- **Shared vs local.** Recording, Channel, Run, Family, Verdict, Tag and ReviewQueue live in the shared canon.
  Annotation and detection rows are Explore-local, but Review and Discovery will want the same detection ids, so
  put `DetectionRow` in the shared canon too.

### Copy
- **Top bar.** `Corpus` `M2_aug_concat_fs1.mat` `CH4_A2` · `Signal` `Cross-channel` · `detections` `6 runs · 4 methods` · `display` `raw` · `‹ back to corpus`.
- **CHANNEL card.** `CHANNEL` `0 – 721 h`.
- **SPAN card.** `SPAN` `276.4 – 278.4 h · 2.0 h` · `‹ 233 / 344 ›` · `MOTIF_233` · `detected` `annotated` `selected`.
- **MOTIF card.** `MOTIF_233` `277.312 – 277.318 h · 21.6 s · detected, unadjudicated` · `context ±20 s` · `overlay F-03 medoid` · `ONSET` `END` · `nearest family F-03 → d 0.19 · tagged sharkfin · unadjudicated` · `Send motif to Analyse →` · `Review this motif →`.
- **Span actions.** `Selected span` `276.4 – 278.4 h · 2.0 h · 6 motifs in view` · `tags` `sharkfin` `burst` `+ tag` · `note` · `Save span` · `Send span to Analyse →` · `Take span for Review →` · `saving stores tags and note only · verdicts are given in Review`.
- **Ribbons.** `Filters & search` · `Annotations` `708` · `Detections` `1284` · `Keyboard shortcuts`.
- **Picker.**
  - `Show detections from` · `select all · none` · `by run` `by method` `by template`.
  - Rows: `drop_motifs9 #128 / matrix profile / 412` · `drop_motifs9 · surrogate #129 / matrix profile / 38` · `drop_motifs9 · 6σ floor #131 / SAX + threshold / 306` · `seed search E-0102 r-0415 / MASS seed / 92` · `mp_drops_v3 r-0412 / drop detector / 410` · `banded_sax_lp #97 / CNN classifier / 26`.
  - Footer: `colour by run` `hide surrogates` `unadjudicated only`.
- **Span legend.**
  - `Reading the span`
  - `detected — a machine detection from a checked run; colour follows the run when 'colour by run' is on`
  - `annotated — a human span from the annotation store`
  - `selected — the motif opened in the tier below`
  - `cap only, no fill — detection already has a verdict in Review`
  - `Coverage ribbon: green reviewed · amber partly reviewed · red artifact-dense · grey never reviewed`
- **Drawer.**
  - Tabs and actions: `Annotations 708` `Detections 1,284` `Shortcuts` · `Export CSV` `Export JSON` `collapse`.
  - Filters: `Filters` `3 active` `clear` · `412 of 708 annotations match` · `96 of 1,284 detections match`.
  - Filter labels, as listed in Regions item 10.
  - Footers: `2 selected` `Add tag` `Stage for Analyse` `1–6 of 412` `Send selected to Review →` · `Analyse events →` `machine detections · indices are samples into the whole recording`.
- **Shortcuts tab.**
  - Top line: `verdict keys live in Settings › Vocabulary and apply in Review` · `Edit shortcuts in Settings › Keyboard & behaviour →`.
  - The key and description pairs, exactly as in the shortcuts table above: `pan the span`, `zoom in / out`, `fit span to view`, `previous / next motif`, `back to corpus`, `move the span on the channel`, `resize from nearest handle`, `select a motif marker`, `select all motifs in view`, `clear selection`, `take span for Review`, `review selected motif`, `send span to Analyse`, `add tag`, `cross-channel from this span`, `toggle this drawer`, `focus filters`, `legend`, `Annotations · Detections · Shortcuts`, `show this tab`.

### Live vs demo (Signal)
| region / control | frame | live today (`webui/client/src/explore/*`) | build action |
|---|---|---|---|
| Header subtitle | 2 | **live** (name + counts) | add the drawer suffix (2b–2d) |
| Breadcrumb | 2 | **live** (`Corpus` link; the file is plain text) | make the file crumb a link |
| Signal / Cross-channel Seg | 2 | Signal on; **Cross-channel inert** | navigate |
| detections chip + popover | 2, 2a | **live but different:** a runs table from `/api/runs` (run, chain, status, wrote, started) | replace with the checklist (live runs + fixture methods, templates, colours); client-side band filtering by `run_id` |
| display chip | 2 | **inert** | Select (`raw` live; the other option `demo` or disabled) |
| Top-bar (i) | 2 | **missing** | InfoTip |
| CHANNEL tier | 2 | **live:** envelope, draggable box + grips, keyboard nudges, coverage and density ribbons, hour axis; extra stat line + caption | keep; caption → (i); keep testids `signal-overview`, `span-box`, `span-handle-*`, `coverage-ribbon`, `density-ribbon`, `overview-path` |
| CHANNEL (i) | 2 | **missing** | InfoTip |
| SPAN tier | 2 | **live:** range, `‹ N / M ›`, zoom −/+/fit, pan, wheel, keys, bands + caps, MOTIF label, mV labels, legend (+ artifact) | keep (`signal-span`, `envelope-path`, `span-bands`, `motif-nav`, `zoom-*`, `__zoomStats`); caption and stat line → (i) |
| SPAN (i) + `Reading the span` | 2a | **missing** | Popover |
| cap-only bands; colour by run | 2a | **missing** (no adjudications live) | fixture adjudications (`demo`) |
| MOTIF tier | 2 | **live:** head, context select, plot with region, ONSET/END, relative ticks, mV labels; honest dashes for family and tag; `Send motif to Analyse` live | keep (`signal-motif`, `motif-svg`, `send-motif`) |
| `overlay F-03 medoid` + teal trace | 2 | **inert** (disabled, no families) | fixture medoid (`demo`) |
| `nearest family F-03 → d 0.19` | 2 | **honest dashes** (`nearest family — `) | fixture value (`demo`) when the live motif matches a fixture detection; dashes otherwise |
| `Review this motif →` | 2 | **inert** | in-memory stage + Toast |
| MOTIF label | 2 | live title `Motif_<db id>` | show `MOTIF_<ordinal>` to match the frame and the `233 / 344` nav; keep the DB id in the tooltip |
| Span actions: tags, note | 2 | **live** (client-only); no default tags | keep; the fixture pre-fills `sharkfin`, `burst` and the note only on the fixture channel |
| `Save span` | 2 | stub toast | in-memory write + Toast |
| `Send span to Analyse →` | 2 | **live** | keep (`send-span`) |
| `Take span for Review →` | 2 | **inert** | in-memory + Toast |
| Ribbons | 2 | **live:** 4 cards; Annotations and Detections open in-view tables; Filters and Shortcuts show scope notes | open the drawer |
| Drawer (tabs, filters, export, sortable, selectable, pager, bulk, Send to Review) | 2b, 2c | **missing** | build: the rows combine live `getSpans(ch, 0, dur)` (id, start, end, verdict, tag, note, source; detections id, start, end, score, run_id) with fixture columns (method, adjudication, family, element…) marked `demo` |
| Shortcuts tab + global key map | 2d | **missing** (only `← → + −` on focused plots, grip nudges) | build |
| Held-out LockedCard, ErrorCards, skeletons | — | **live** | keep (smoke: `#/explore/signal/52` contains "held out") |

### Frame ⟷ spec conflicts
1. **§5.3 says the drawer overlays the lower screen.** Frames 2b–2d draw it as a card under the overview with a
   compact motif strip beneath. They agree in effect: build an overlay anchored under the overview that covers the
   span and action tiers, and render the compact motif strip below it as drawn.
2. **Frame 2a draws dark plot grounds.** D7 (resolved) and §3 say plots are on a light ground: use light. Frame 2a
   also draws the medoid checkbox purple where frame 2 draws it teal; use teal, F-03's canon colour.
3. **The drawer rows contradict the active filters** (backlog B28 "drawer filters vs rows"). The 2b table shows
   seed, not_interesting and artifact rows under `verdict = interesting`; the 2c table shows SAX rows under
   `method = matrix profile`. Recommendation: filters apply honestly. The frame's rows are seeded so they appear
   when filters are cleared, and the filtered first page shows matching rows. Keep the frame's filter values and
   match counts.
4. **`duration 10.0 min` in 2b.** §0 says event durations are in s, so show `600 s`.
5. **`6 runs · 4 methods` against the picker.** The picker lists 5 distinct methods, and only 3 runs are checked.
   Recommendation: the chip reads checked runs and distinct methods among them, e.g. `3 of 6 runs · 3 methods`.
   The frame's `6 runs · 4 methods` is then the all-checked state with surrogates hidden (Fog F8).
6. **The four ribbons against the three drawer tabs** (backlog D1, open). Recommendation: keep four ribbons as drawn,
   with `Filters & search` opening Annotations with the filters focused. D1 stays open for the owner.
7. **`MOTIF_233 … 21.6 s` is impossible at 1 Hz**, where samples are integers. The fixture uses 22 samples
   (998,323–998,345 s) and displays the computed value, `22 s`. §0 says F-03 is "~21 s".
8. **The overview's selected box in frame 2 spans about 270–330 h**, not 276.4–278.4 h (B28, "MOTIF_233 box
   scale"). Draw it from the data; at 2 h in 721 h it is about 3 px wide, which is why the live code widens the
   grips for narrow boxes.
9. **Motif-plot tick spacing is uneven** (the −10 s label sits too far right, and +20 s is missing). Use regular ticks.

### Fog (Signal)
- **F6. `344` in `233 / 344`.** Undefined whether it counts annotations plus detections from checked runs, unique
  motifs after overlap merging, or something else. Live counts annotations + detections on the channel, and the
  channel has 708 + 1,284 = 1,992 spans, not 344. The spec is silent.
- **F7. Coverage ribbon.** The "reviewed / partly reviewed / artifact-dense / never reviewed" semantics need
  review-coverage data that the bridge does not expose. Live draws verdict colours per bucket instead.
- **F8. Methods.** `banded_sax_lp #97` is labelled `CNN classifier` in 2a, while §0 lists it as an Analyse run and
  B25 says CNN classification is a `Model stage`. The recording-wide method count (`7`) and the channel count (`4`)
  are also unexplained.
- **F9. Missing filter vocabularies.** `element`, `quality`, `structure`, `status`, `spike-train length` and
  `duration band` are defined nowhere in the spec, so their option lists are proposals.
- **F10. `display raw ▾`.** No frame or spec lists the other display modes.
- **F11. `F fit span to view`.** Ambiguous against the live fit button, which fits the whole channel.
- **F12. `MOTIF_233` against detection `412`.** The motif shows `F-03 d 0.19 · unadjudicated` at 277.312 h, while
  detection 412 has the same family distance at 276.42 h (995,112). The fixture treats them as different spans.
- **F13. Review queues.** `Review this motif` and `Take span for Review` write to an `Explore spans` queue (§10.1),
  which has no canon id in §0 (`q-12`, `q-15`, `q-18` and `q-19` are the others). The Review inventory should name it.
- **F14. `Analyse events →`.** It implies sending a detection set as a SpanSet source to Analyse. Today's source
  model (`SourceSpan`) is a single signal span, so this stays a not-wired Toast.
- **F15. Shortcut clash.** `A` means "send span to Analyse" here and "artifact" in Review (§10.3). Settings ›
  Keyboard's conflict check should treat keys as per-workspace. The spec does not say.

## explore.cross-channel

Fully fixture-backed (the header shows `demo data`). §5.4 says: "Deliberately loose … Do not over-build it."

### Route & states
- `as-recorded` (frame 3). Route `#/explore/cross-channel/<channelId>`; the default is `?align=recorded`.
  - **Channel.** `<channelId>` is the reference (4 = CH4_A2).
  - **Defaults.** `window=motif-233`, and channels `CH4_A2, CH3_A2, CH1_A1, CH2_A1, CH5_B1, CH6_B1`.
  - **Entry points.** The Corpus bottom-bar button; the Signal Seg `Cross-channel`; `C` on Signal. When entered from
    Signal, the page carries `?window=motif-<n>`.
- `lag-aligned` (frame 3b). Click `lag-aligned` in the `align` Seg, or `?align=lag`.
  - Each non-reference trace shifts by `−lag`: CH1_A1 and CH2_A1 end early; CH5_B1 (−18.4 s) starts late, leaving
    the first ~19 s blank; CH6_B1 (no match) is unchanged.
  - The header subtitle becomes `CH4_A2 reference · lag-aligned`.
- `channels-picker` (no frame). Click `channels 6 of 16 ▾`, or `?popover=channels`.
- `questions-open` (no frame). Click the `Open design questions` row, or `?questions=open`.
- `computing` (no frame, simulated). After changing reference, channels, window, lag or max lag, for about 600 ms:
  - the readouts show `…`, the classification tiles dim, and a ProgressBar sits in the stack header reading `computing lag · 6 channels`;
  - reachable by `?state=computing`, which holds the state.
- `too-few-channels`. Only the reference is checked: the stack shows the reference row, then an EmptyState
  `Pick at least one more channel to compare against CH4_A2.` with the button `Choose channels`. The classification
  tiles all read `0`.
- `held-out`. A channel id in M4 shows the LockedCard (same component as Signal).
- `unknown-channel`. An id not in the fixture shows the EmptyState
  `No cross-channel view for channel <id> in the demo data.`, with the link `Open CH4_A2 →` to `#/explore/cross-channel/4`.

### Regions (1440 × 900, frames 3 / 3b)
Content column x 89–1351.
1. **Header**: `Explore | Cross-channel  CH4_A2 reference · 6 channels`.
2. **Top bar**: identical to Signal (breadcrumb `Corpus › M2_aug_concat_fs1.mat › CH4_A2`, Seg with
   `Cross-channel` selected, the `detections 6 runs · 4 methods ▾` chip, `display raw ▾`, (i), `‹ back to corpus`).
3. **Controls card**: y 109–159 (≈ 50 h). A single row, left to right:
   - Select `reference  CH4_A2 ▾`
   - Select `channels  6 of 16 ▾`
   - Select `window  MOTIF_233 ± 20 s ▾`
   - label `align`, then a Seg `as recorded | lag-aligned`
   - Select `lag  computed on window ▾`
   - Select `max lag  ±30 s ▾`
   - flush right, a square (i)
4. **Stack card**: y 176–626 (≈ 450 h).
   - **Head.** The mono caps `SAME WINDOW, EVERY SELECTED CHANNEL`, then `277.306 – 277.323 h · 61.6 s`. Column
     heads above the readouts: `lag` (x ≈ 1100), `r` (≈ 1170), `bin` (≈ 1220).
   - **Six rows**, each ≈ 56 px with ≈ 10 px gaps. Each row is a mono label (≈ 60 px), a `⠿` drag handle, a trace
     panel (x ≈ 178–1057, ≈ 880 w, light grey ground, rounded, thin border), a coloured dot, the lag, r, and a bin Badge:

     | channel | trace | dot | lag | r | bin badge |
     |---|---|---|---|---|---|
     | CH4_A2 | blue; motif region tinted orange from 0 s to ~+21 s | blue | `0.0 s` | (blank) | `reference` (blue) |
     | CH3_A2 | black | red | `+0.04 s` | `0.98` | `artifact` (red) |
     | CH1_A1 | black | amber | `+1.20 s` | `0.71` | `propagation` (amber) |
     | CH2_A1 | black | amber | `+2.85 s` | `0.64` | `propagation` (amber) |
     | CH5_B1 | black | green | `−18.4 s` | `0.31` | `independent` (green) |
     | CH6_B1 | black | grey | `— s` | `—` | `no match` (grey) |

   - **Grid lines.** Faint vertical lines at 0 s and +20 s run through every panel.
   - **Shared x axis** under the last row: `-20 s -10 s 0 s +10 s +20 s +30 s +40 s`.
5. **Classification card**: x 89–848 (≈ 760 w), y 645–819 (≈ 174 h).
   - **Head.** `Classification for this window (i)`, with the muted `pairs against CH4_A2 reference` at the right.
   - **Four tinted StatTiles** in a row (≈ 170 × 60 each): `1` / `artifact` (red tint, red numeral) · `2` /
     `propagation` (amber) · `1` / `independent` (green) · `1` / `no match` (grey).
   - **Warning line:** an amber ⚠, then `CH3_A2 ↔ CH4_A2 is a known shared-ground pair — excluded from recurrence counts`.
6. **Take it further card**: x 865–1351 (≈ 486 w), y 645–819. Title `Take it further`, then three ActionList rows
   (each ≈ 36 h, grey fill, with an icon at the left and `→` at the right):
   1. Library icon: `Classify every F-03 member in Library` / muted `runs across all channels and stores bins on edges`
   2. Analyse icon (the frame's choice; recommend the Discovery radar): `Apply a template across these 6 channels` / `opens Discovery with a channel scope`
   3. Review icon: `Review this window on all channels` / `stages 6 spans in Review`
7. **Open design questions**: a collapsible card at y 834–869 (≈ 35 h): `›  Open design questions  4 · multivariate direction parked`.

### Controls & interactions
| control | kind | behaviour |
|---|---|---|
| Top bar | (as Signal) | `Signal` navigates to `#/explore/signal/<refId>?motif=<n>`; `‹ back to corpus` → Corpus; the detections chip opens the same picker (filtering applies to the reference row only). |
| `reference CH4_A2 ▾` | Select | Any open channel of the recording. Changing it re-routes to `#/explore/cross-channel/<newId>` and recomputes (fixture: the reference row takes `0.0 s`, and the others swap values from a seeded table). |
| `channels 6 of 16 ▾` | Select (multi) → Popover | A 16-channel checklist with a `select none` link. The reference is checked and disabled (`the reference is always shown`). **P8 cap:** at most 10 checked; the rest become DisabledReason `at most 10 channels in one stack (P8)`. Shared-ground partners get a `shared ground` Chip. |
| `window MOTIF_233 ± 20 s ▾` | Select | `MOTIF_233 ± 20 s` · `MOTIF_233 ± 60 s` · `selected span 276.4 – 278.4 h`. The last is disabled: `longer than 10 min — cross-channel compares short windows` (proposed rule; Fog). |
| `align` Seg | Seg | `as recorded` / `lag-aligned` (the frame 3 ↔ 3b toggle). Shifts the traces; updates the URL and the header subtitle. |
| `lag computed on window ▾` | Select | `computed on window` · `computed on whole channel` (proposed; see Fog). Triggers `computing`. |
| `max lag ±30 s ▾` | Select | ±10 / ±30 / ±60 s. Lags beyond the bound become `— s` / `no match` (fixture: CH5_B1 at −18.4 s drops to `no match` under ±10 s). |
| (i) controls card | InfoTip | `Every selected channel over the reference's window. Lag is where the cross-correlation peaks within max lag; r is its height.` |
| Row `⠿` handle | drag reorder | Reorders rows in memory; the reference is pinned first. Keyboard: focus the handle, then `Alt + ↑/↓`. |
| Row label | link | `#/explore/signal/<id>` for that channel, with the window centred. |
| Trace panel hover | crosshair | A shared vertical crosshair across all rows showing `t = +3.2 s` (CrosshairLayer exists in `charts/primitives`). |
| Bin Badge | Badge + tooltip | artifact: `r ≥ 0.95 at ~0 lag — likely a shared electrical path`; propagation: `lagged match with r ≥ 0.6`; independent: `peak r < 0.6`; no match: `no peak within max lag`. The thresholds are proposed (Fog). |
| StatTile (×4) | clickable StatTile | Highlights the rows in that bin; the others dim. A second click clears. |
| (i) classification | InfoTip | `Each channel is paired with the reference and binned by lag and r. Shared-ground pairs come from Settings › Channels & events.` |
| ⚠ shared-ground line | text + link | `Settings › Channels & events` → `#/settings/channels`. |
| `Classify every F-03 member in Library →` | ActionList row | Toast `not wired yet: classify F-03 members across channels (Library edges job)`. |
| `Apply a template across these 6 channels →` | ActionList row | Navigates to `#/discovery/runs?modal=add-template&channels=4,3,1,2,5,6` (the Discovery inventory owns the exact route and param). |
| `Review this window on all channels →` | ActionList row | In-memory: stage 6 spans (one per channel, same window) into the Explore spans queue. Toast `6 spans staged for Review` with `Open Review →`. |
| `Open design questions` | disclosure | Expands inline to a numbered list of 4 questions (copy proposed below). |

### Plots
- **Channel stack** (SmallMultiples of Trace, one per channel, ≤ 10 per P8).
  - **X:** seconds relative to the window's motif onset (`−20 s … +40 s`), shared across rows.
  - **Y:** mV per row, **built 2026-09-22** — `explore/crossScale.ts`, three modes on `?y=`, default `centred`:
    `absolute` (one absolute mV domain across the stack), `centred` (one shared gain, each row about its own
    median) and `per-channel` (autoscaled per row, badged `normalised`). The `±0.4 mV` prescribed here was a
    fixture number and is impossible on live data — the sixteen M2_aug electrodes sit from −0.10 to −3.79 mV, so
    one absolute domain is ~3.9 mV tall and every row's 0.001–0.03 mV waveform drew as a flat line. The scale
    note is computed from the drawn rows, never a literal, and each row prints its own absolute extent in mV.
  - **Marks.**
    - The reference trace in blue, the others black.
    - The orange motif region on the reference only.
    - The 0 s and +20 s guides.
    - In lag-aligned mode, each series is translated by −lag and clipped to the panel. No data is drawn outside its recorded extent: blank, not padded.
  - **Feeds:** `crossChannel.rows[].trace` (fixture mV at 1 Hz, 62 samples; or smoother synthetic at 10 samples/s for display).
- **StatTiles:** counts only.

### Fixtures
```ts
interface CrossChannelRow { channelId: number; name: string; lagS: number | null; r: number | null;
  bin: 'reference'|'artifact'|'propagation'|'independent'|'no match'; sharedGroundWith?: string; trace: { t0S: number; dtS: number; mv: number[] } }
interface CrossChannelFixture { recordingId: 'M2_aug fs1'; referenceId: 4; window: { label: 'MOTIF_233 ± 20 s'; startH: 277.306; endH: 277.323; durS: 61.6; motifStartS: number; motifEndS: number };
  maxLagS: 30; lagMode: 'window'|'channel'; rows: CrossChannelRow[]; classification: { artifact: 1; propagation: 2; independent: 1; noMatch: 1 };
  openQuestions: string[] /* 4 */ }
// rows: CH4_A2 0.0/—/reference · CH3_A2 +0.04/0.98/artifact (sharedGroundWith CH4_A2) · CH1_A1 +1.20/0.71/propagation
//       CH2_A1 +2.85/0.64/propagation · CH5_B1 −18.4/0.31/independent · CH6_B1 null/null/no match
```
- **Shared canon:** Channel (names), Family F-03, the shared-ground pair (Settings › Channels & events owns it; also used by Review 1b), and the motif `MOTIF_233`.
- **Local:** the rows and lags.

### Copy
- `reference` `CH4_A2` · `channels` `6 of 16` · `window` `MOTIF_233 ± 20 s` · `align` `as recorded` `lag-aligned` · `lag` `computed on window` · `max lag` `±30 s`
- `SAME WINDOW, EVERY SELECTED CHANNEL` · `277.306 – 277.323 h · 61.6 s` · `lag` `r` `bin` · `reference` `artifact` `propagation` `independent` `no match`
- `Classification for this window` · `pairs against CH4_A2 reference` · `CH3_A2 ↔ CH4_A2 is a known shared-ground pair — excluded from recurrence counts`
- `Take it further` · the three rows as in Regions item 6
- `Open design questions` `4 · multivariate direction parked`
- **Proposed question copy** (not in the frame; the owner should confirm):
  1. `Is lag measured per window, or per channel pair across the whole recording?`
  2. `What r separates propagation from an independent match, and should it depend on distance between electrodes?`
  3. `Should a shared-ground pair be excluded from every count, or only from recurrence?`
  4. `Is a multivariate motif one span across channels or a set of linked single-channel spans? (parked)`

### Frame ⟷ spec conflicts
1. **The frame's text layer reads `Classify every F03 member`, while the image reads `F-03`.** Use `F-03` (§0).
2. **The frame's bin colours clash with §3.** `independent` is green and `propagation` amber, while §3 reserves green
   for human origin, above chance and cached, and amber for "needs attention". Recommendation: keep the frame
   colours; this is a placeholder page (§5.4). Flagged for the owner.
3. **The `Apply a template` row uses the Analyse icon but opens Discovery** (B25/P3 changed the copy). Use the Discovery icon.
4. ~~**The stack has no mV scale**, against §3 ("waveforms are never normalised on screen"). Add a shared y-scale note, e.g. `shared y · ±0.4 mV`.~~
   **Resolved 2026-09-22.** The note is in the stack head (`scale-note`) and is computed from the drawn rows; a
   literal `±0.4 mV` cannot be right for electrodes 3.9 mV apart. See **Y** above for the three modes and why
   `centred` is the default: PRD:523 asks for *detrended* mV, which is what an absolute domain does not draw.

### Fog (Cross-channel)
- **F16.** How lag, r and the bins are computed, and their thresholds, are unspecified. §5.4 parks it, and the bridge has no endpoint, so every value is fixture.
- **F17.** The `lag computed on …` options and the window cap are not given anywhere.
- **F18.** Where shared-ground pairs are declared: Settings › Channels & events (frame settings-02) is the likely owner; the exact field is unknown.
- **F19.** The four open design questions have no copy in the frame or the spec; the text above is proposed.
- **F20.** `stages 6 spans in Review`: which queue it stages into is unclear (same as F13).

---

## explore.span-edit

Fully fixture-backed (`demo data` chip). §4.2 revision model; §4.3 "Explore only, reached from Review"; §5.5.

### Route & states
- **Route** `#/explore/span-edit/<spanId>`, where `spanId` is the **motif member id** (`m-1846`).
  - **Query** carries the Review hand-off: `?queue=q-12&candidate=12&of=50&return=<encoded Review route>`.
  - **Entry.** Reached from Review's `Edit span in Explore →` (Review inventory). The frames give no in-Explore entry;
    backlog D2 is open on that. Recommendation: no Explore entry tonight.
- `pristine` (no frame; the arrival state). The extent equals the original.
  - `vs original` reads `start 0 s · end 0 s · duration 0 s` in muted text.
  - `Save and return to Review →` is disabled with the reason `nothing changed — drag a handle or nudge start / end`.
  - Only the grey original box is visible, with the blue extent on top of it.
- `edited` (frame 4). Reached by any edit, or `?state=edited`, which loads the canned edit: start #534,967, end
  #534,985, duration 18 s, `vs original start −4 s · end +2 s · duration +6 s` in amber.
- `invalid` (no frame). Reached when end ≤ start, the duration is under 2 samples, or the extent falls outside
  0–721 h.
  - The fields turn red with an inline message.
  - Save is disabled with the reason `fix the extent first`.
- `saving → saved` (no frame). Save click → the button shows a spinner `Saving…` for about 400 ms, then an in-memory write:
  - the member gains `rev 2 annotation a-2077 · human · current`, and `rev 1` becomes `kept`;
  - Toast `m-1846 saved as rev 2 · annotation a-2077`;
  - then navigate to `return` (or `#/review`) with `&edited=m-1846`.
- `leave-without-saving`. `Return without saving` navigates to `return` immediately, with no confirmation (the label is explicit).
  - **Proposed:** if `edited`, first show a Toast `edit discarded`.
- `held-out` (a member on M4 → LockedCard) · `unknown-span` (EmptyState `No span m-XXXX in the demo data.` with `Back to Review`).

### Regions (1440 × 900, frame 4)
Content x 89–1415. This page is wider than Signal and matches Corpus.
1. **Header**: `Explore | Editing a span  m-1846 · opened from Review`.
2. **Top bar**: y ≈ 55–85.
   - Left, the breadcrumb `Corpus › M2_aug fs1 › CH4_A2 › edit span` (the last crumb darker).
   - Right, the muted mono `span editing always happens here, so human geometry stays in the human store`.
   - No Seg, no detections chip, no back link.
3. **Amber banner**: y 108–151 (≈ 43 h), full width, amber-100 fill, a 1 px amber border, radius 8. It persists and does not scroll away (sticky under the header).
   - An amber dot, then the bold `Editing m-1846 for Review`, then amber-brown mono `candidate 12 of 50 · drop_motifs9 run 128`.
   - Right: the white secondary `Return without saving`, then the primary `Save and return to Review →`.
4. **CHANNEL card**: y 165–269 (≈ 104 h).
   - **Head:** `CHANNEL  CH4_A2 · 0 – 721 h`; right, the muted `the span being edited is highlighted`.
   - **Trace strip** ≈ 60 px on light grey, with a narrow **orange** highlight box marking the edited span.
5. **THE SPAN card**: y 283–532 (≈ 249 h).
   - **Head:** `THE SPAN  drag either handle · arrow keys nudge one sample (1 s at 1 Hz)`; right, `1 px = 0.2 s`.
   - **Plot** ≈ 185 px on a light ground, with a black trace. It holds:
     - the **original extent**, a grey 1 px outline box;
     - **your extent**, a translucent blue filled box with a blue border;
     - two blue grip handles (≈ 8 × 30, white groove) on the extent edges.
   - **Legend** under the plot, centred: `▢ original extent, from the detection` (grey) · `■ your extent` (blue).
6. **Extent card**: y 546–681 (≈ 135 h). Title `Extent`.
   - **Left: three fields** (≈ 195 w each, grey).
     - `start` [`148:36:07 · #534,967` ⬍]
     - `end` [`148:36:25 · #534,985` ⬍]
     - `duration` [`18 s · 18 samples`], read-only
     - Under the fields: muted `original onset rule: walk back from steepest while descending` with an (i).
   - **Right.**
     - `snap to`, then a single-select chip group: `steepest sample` (selected, blue tint) · `trough` · `zero crossing` · `free`.
     - Under it: muted `vs original`, then amber `start −4 s · end +2 s · duration +6 s`.
7. **What saving writes card**: y 695–819 (≈ 124 h).
   - **Head:** `What saving writes`, then the muted `a new revision of this motif, not a replacement` and an (i).
   - **Left, a revision list:**
     - `rev 1` · `detection d-0412` · `run 128 · machine` · green dot `kept`
     - `rev 2` · `annotation a-2077` · `this edit · human` · green dot, then blue text `current`
   - **Right, a check list** (each line starts with a green check-circle):
     - `run 128 still reproduces from its recipe — the detection is untouched`
     - `later runs that find the original extent resolve to this same motif`
     - `your geometry goes to the annotation store, never the detection table`

### Controls & interactions
| control | kind | behaviour |
|---|---|---|
| Breadcrumbs | links | `Corpus` → `#/explore/corpus`; `M2_aug fs1` → `#/explore/corpus?rec=…`; `CH4_A2` → `#/explore/signal/4`. If `edited`, navigating away shows Toast `edit discarded`. |
| `Return without saving` | button | → `return` route (see states). Shortcut `Esc` when no field is focused. |
| `Save and return to Review →` | button (primary) | Disabled reasons: `nothing changed…` / `fix the extent first`. Otherwise saving → in-memory rev 2 → Toast → navigate. Shortcut `Ctrl + Enter`. |
| Overview highlight | display | Click-through: none. The box marks the member's extent at the right hour position. |
| Extent grips | draggable handles (DraggableSpanBox, edge-only) | Drag moves start or end in 1-sample steps; with `snap to ≠ free`, snaps to the nearest candidate sample on release. `← →` when a grip is focused nudges one sample, `Shift` ×10. Updates the fields and `vs original` live. Minimum 2 samples. |
| Extent body | — | Not draggable (the frame says "drag either handle"). |
| `start` / `end` | Number field with Stepper (⬍) | Accepts `#534967`, `534,967` or `148.6019 h`; the display shows both. The up and down arrows (and ↑/↓ keys) nudge ±1 sample. **Rules:** integer sample; 0 ≤ start < end ≤ n_samples; end − start ≥ 2. **Messages:** `start must be before end`, `a span needs at least 2 samples`, `outside the recording (0 – 721 h)`. |
| `duration` | read-only KeyValue | `<n> s · <n> samples`. |
| (i) onset rule | InfoTip | `The detector found this onset by walking back from the steepest sample while the signal kept descending. Snapping to the same rule keeps your edit comparable with the rest of F-03.` |
| `snap to` chips | ChoiceChips (single) | `steepest sample` · `trough` · `zero crossing` · `free`. Changing it re-snaps both edges (fixture: a precomputed candidate list per rule). `free` disables snapping. |
| `vs original` deltas | KeyValue | Recomputed; amber when non-zero, muted when zero. |
| (i) What saving writes | InfoTip | `Revisions are spans, not edits to a span (§4.2). The member keeps both; the family shows one card.` |
| Revision rows | display | `rev 2` appears (muted, `pending`) as soon as the extent differs; it shows `current` after save. In `pristine`, only rev 1 shows, as `current`. |

### Plots
- **Channel overview** (Trace).
  - **X:** hours, 0–721 h, no tick labels in the frame (recommend the standard hour axis, muted). **Y:** mV, unlabelled.
  - **Marks:** the envelope, plus an orange box at the member's hour (148.60 h).
  - **Feeds:** the fixture envelope for CH4_A2.
- **The span** (Trace + extent overlays).
  - **X:** seconds. The frame has no ticks and shows `1 px = 0.2 s`. Recommend an `s` axis relative to the original onset.
  - **Y:** mV. The frame shows no labels; add `±mV` labels per §3.
  - **Marks:** the trace; the original extent as a grey outline drawn *behind*; your extent as a blue fill with a border in front; the grips on your extent.
  - **Window:** about 250 s centred on the member, which gives `1 px = 0.2 s` at about 1250 px.
  - **Feeds:** `spanEdit.trace`.
- No cap applies.

### Fixtures
```ts
// SHARED (Library + Review + Explore)
interface MotifMember { id: 'm-1846'; familyId: 'F-03'; recordingId: 'M2_aug fs1'; channelId: 4; currentRev: 1 | 2;
  revisions: Revision[] }
interface Revision { rev: number; kind: 'detection'|'annotation'; ref: 'd-0412'|'a-2077'; runId?: '#128'; origin: 'machine'|'human';
  startSample: number; endSample: number; status: 'kept'|'current'|'pending' }
interface ReviewHandoff { queueId: string; candidate: 12; of: 50; runLabel: 'drop_motifs9 run 128'; returnRoute: string }   // Review owns
// Explore-local
interface SpanEditFixture { member: MotifMember; fs: 1; nSamples: 2595600 /* 721 h at 1 Hz */;
  original: { start: 534971; end: 534983 };        // derived from frame deltas: yours −4 s / +2 s, 12 → 18 s
  edited:   { start: 534967; end: 534985 };        // frame 4 values
  onsetRule: 'walk back from steepest while descending'; snap: 'steepest sample';
  snapCandidates: Record<'steepest sample'|'trough'|'zero crossing', number[]>; trace: { t0Sample: number; mv: number[] } }
```
- **§0 / §4.2 canon used:**
  - member `m-1846` (F-03's medoid);
  - rev 1 `detection d-0412 · run 128 · machine`;
  - rev 2 `annotation a-2077 · human edit · current`;
  - run `#128 drop_motifs9`;
  - actor `this installation`, for any audit Toast.

### Copy
- **Top bar and banner:**
  - `Corpus` `M2_aug fs1` `CH4_A2` `edit span` · `span editing always happens here, so human geometry stays in the human store`
  - `Editing m-1846 for Review` · `candidate 12 of 50 · drop_motifs9 run 128` · `Return without saving` · `Save and return to Review →`
- **Cards:**
  - `CHANNEL` `CH4_A2 · 0 – 721 h` · `the span being edited is highlighted`
  - `THE SPAN` `drag either handle · arrow keys nudge one sample (1 s at 1 Hz)` · `1 px = 0.2 s` · `original extent, from the detection` · `your extent`
  - `Extent` · `start` `end` `duration` · `18 s · 18 samples` · `original onset rule: walk back from steepest while descending` · `snap to` `steepest sample` `trough` `zero crossing` `free` · `vs original` `start −4 s · end +2 s · duration +6 s`
  - `What saving writes` · `a new revision of this motif, not a replacement` · `rev 1` `detection d-0412` `run 128 · machine` `kept` · `rev 2` `annotation a-2077` `this edit · human` `current` · the three check lines as in Regions item 7

### Frame ⟷ spec conflicts
1. **Time format.** The frame shows `148:36:07`, a clock-style h:m:s. §0 and Settings › Display say hours since recording start. Recommendation: `148.6019 h · #534,967`; the sample index is the exact value.
2. **Box geometry against the numbers.** The frame draws your blue extent *inside* the grey original, which means
   narrower. The numbers say start −4 s, end +2 s and duration +6 s, which means wider. The grips sit on the grey
   box's edges instead of yours (B28 "span-edit px scale"). Recommendation: the numbers win. Draw your extent
   wider than the original, with the grips on your extent.
3. **`1 px = 0.2 s` against the drawn widths.** An 18 s box would be 90 px, but the frame draws about 260 px. The
   fixture scale wins.
4. **Overview highlight position.** It sits at about 47 % of 721 h (about 340 h), while the extent is 148.6 h.
   Place it at 148.6 h.
5. **Breadcrumb recording name.** The breadcrumb uses the short `M2_aug fs1` while Signal uses the file name
   `M2_aug_concat_fs1.mat`. Both are canon names (display vs file); keep each as drawn.
6. **Family staleness is not shown.** §4.2 says an extent edit invalidates `motif_edge` and may change F-03's medoid,
   which matters here because m-1846 *is* the medoid; recompute or mark the family partially stale. The frame's
   revision card omits this. Recommendation: add a fourth muted check line
   `F-03 is marked partially stale until its distances are recomputed` (spec wins; flag for the fidelity critic as
   an intentional addition).

### Fog (Span edit)
- **F21. Which queue.** `candidate 12 of 50 · drop_motifs9 run 128` names no §0 queue: `q-12` is `r-0412 mp_drops_v3`
  and none is run #128.
- **F22. `d-0412`.** It collides with detection `412` of run #128 in the Signal drawer, which sits at sample 995,112,
  not 534,967. It is unclear whether `d-0412` means detection 412.
- **F23. Snap rules.** `trough` and `zero crossing` need per-sample candidates that the core has no endpoint for
  (fixture only). The steepest-sample rule's parameters are not in the spec.
- **F24. Return target.** The Review inventory owns the route and the `edited=` parameter.
- **F25. Entry from Explore.** Whether Explore gets its own entry into span edit (D2) is open.

---

## Kit needs

These recur in this group beyond the listed kit (Chip, Badge, Seg, Tabs, Popover, Modal, Drawer, Table, SectionCard,
Stepper, Toast, Glyph, SmallMultiples, Field components, InfoTip, CodeBlock, KeyValue, EmptyState, StatTile,
ProgressBar, DisabledReason, ChainRibbon, and the plots).

| component | what it is | where it appears (and likely elsewhere) |
|---|---|---|
| **Breadcrumb** | A mono `A › B › C` trail: links plus a current crumb | Signal, Cross-channel, Span edit (Library family, Settings) |
| **TableMenuPopover** | A popover holding a filter field, a compact table with a selected check row, disabled rows with a lock, and a footer link plus hint | Corpus 1b recordings (Discovery or Models source pickers) |
| **ChecklistPopover** | A title with `select all · none`, a Seg regroup, checkbox rows with a colour swatch, name, id, sub-caption and count, and footer toggles | Signal 2a detections picker; Cross-channel channels (Discovery run pickers, Review queue filters) |
| **LegendPopover** | Swatch rows (fill, outline, ramp, cap-only), each with a sentence, then a hairline and an italic footnote | Corpus 1b, Signal 2a (every plot's InfoTip) |
| **RangeSlider + value chip** | A two-handle slider with an editable `a – b h` chip | Corpus toolbar |
| **SelectChip** | A compact bordered select rendered as `label value ▾` (muted label, bold value) | Corpus bin; Signal detections and display; Cross-channel ×5 (every toolbar) |
| **FilterRail** | A card of titled sections (title + InfoTip + rule) with checkbox lists, colour dots, optional counts and a pinned foot readout | Corpus right rail (Review queue rail) |
| **FilterGrid** | An N-column grid of label + InfoTip + Select/Text, with an active tint, a header showing `N active` Badge, `clear` and `X of Y match` | Signal drawer 2b/2c (Review queues, Discovery browser) |
| **BulkActionBar + TablePager** | `N selected` plus actions on the left; `1–6 of 412 ‹ ›` plus a primary action on the right | Signal drawer (Review, Library members) |
| **Kbd / ShortcutGrid** | Grey keycaps (`Shift + drag`, `1 2 3`) in titled columns of key → description | Signal 2d; header `Ctrl K` (Settings › Keyboard, Review) |
| **useHotkeys** | A page-scoped key map that is ignored while typing, with a registry the Shortcuts tab can render | Signal, Span edit (every page with shortcuts) |
| **Heatmap/Matrix with row selection** | Row labels, rounded cells, quantile ramp (blue or amber), selected-row outline, hover tooltip, click and double-click | Corpus (Library recurrence) |
| **DraggableSpanBox** | A translucent box with two grip handles (white groove), body drag, keyboard nudge and minimum span; edge-only variant | Signal overview; Span edit extent (Discovery scope brush) |
| **RibbonStrip** | A 1-row BandStrip of rounded colour runs (coverage) plus a bar row (density) | Signal overview (Discovery where-each-run-fires) |
| **SpanBandLayer** | Per-span full-height translucent fill plus a cap above; kinds detected, annotated, selected, artifact and cap-only; in-band label; colour-by-run | Signal span (Review context, Discovery browser) |
| **MotifTrace** | A trace with a tinted region, ONSET/END marker lines with labels, a relative-seconds axis and an optional overlay trace (medoid) | Signal motif (Review shape, Library family) |
| **ChannelStack** | Rows of label + drag handle + trace panel + readout columns (dot, lag, r, Badge), a shared x axis, crosshair, reorder and an align shift | Cross-channel (Review 1b other channels) |
| **TintedStatTile** | A big numeral plus a label on a status-tinted ground, clickable to filter | Cross-channel classification (Discovery scoreboards) |
| **ActionList** | Rows of icon, title, muted caption and `→` on a grey fill | Cross-channel "Take it further" (Library hand-offs, Jobs "other ways forward") |
| **Disclosure card** | A one-line collapsible card `› Title  n · caption` | Signal ribbons; Cross-channel open questions |
| **Banner (persistent)** | A tinted (amber) full-width bar with a dot, a bold title, mono context and right-aligned actions, sticky | Span edit (Review blind state, Jobs paused run, Chain 1e) |
| **StepperNumberField** | A number field with stacked ⬍ nudge buttons and a dual display (`148.6019 h · #534,967`) | Span edit extent (Settings numeric defaults) |
| **ChoiceChips** | A single-select chip group styled as outlined chips (distinct from Seg) | Span edit `snap to` (Review padding, class keys) |
| **RevisionList + CheckList** | `rev N · ref · origin · ● status` rows; green check-circle lines | Span edit (Library family hand edits, Jobs upload checks) |
| **TagInput** | Removable chips plus an inline `+ tag` input with autocomplete and validation | Signal span actions and the drawer's `Add tag` (Review tags, Library family) |
| **ColourDot / Swatch** | A 6–8 px dot or 10 px square in the verdict, run, family or class palette | Corpus rail, Signal picker and legend, Cross-channel readouts |
| **LockedCard** | The held-out state card (exists live) | Corpus, Signal, Cross-channel, Span edit (every workspace that can reach M4) |
| **DemoBadge + header `demo data` chip** | A small `demo` Badge in a card head for fixture regions; drives the header chip | Corpus and Signal fixture regions; whole Cross-channel and Span edit pages |

---

## Summary counts
- **Pages:** 4 Explore pages plus the shell.
- **Frames:** 12 read, 0 unreadable.
- **Fog:** 25 items (F1–F25).
- **Smoke-test contract to preserve:**
  - testids `nav-rail`, `header`, `corpus-heatmap`, `heatmap-cell`, `heatmap-row-CH4_A2`, `corpus-bottom-bar`, `open-channel`, `signal-overview` (with `path[d]`), `signal-span` / `envelope-path`, `span-bands`, `signal-motif`, `motif-next`, `send-span`;
  - exact-name buttons `detections` / `disagree` / `both`;
  - `window.__zoomStats`;
  - `#/explore/signal/52` rendering "held out".
