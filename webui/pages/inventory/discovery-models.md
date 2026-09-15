# Inventory — Discovery and Models

Sources read: `prototyping/imgs/INDEX.md`; `UI_FUNCTIONAL_SPEC.md` §0, §3, §7 (513–673), §7b (674–775),
§12 P11 P14 P16 P17 P19 (+ P2, P8, P9, P18, P24 where the frames lean on them); every frame PDF
in `prototyping/imgs/discovery/` (6) and `prototyping/imgs/models/` (6); `UI_REVIEW_BACKLOG.md`
(Discovery / Models sweep notes, B7, B12, B14, B22, B24, B28, B29); `webui/client/src`
(`App.tsx`, `state.tsx`, `shell/*`, `kit/sim.ts`, `kit/store.ts`, `api/seam.ts`, `fixtures/canon.ts`).

Pixel figures below are for a 1440-wide viewport (the frames render at ~0.9 scale). "Content width"
= 1440 − 64 px nav rail − 2 × ~22 px page padding ≈ 1330 px.

**Tab bars.** Models has an in-page tab bar **Launch · Results · Compare · Registry** (icons: rocket,
bar-chart, arrows-compare, library) on every Models page, left-aligned under the toolbar, with a
right-aligned link that changes per page (`2 training jobs · open in Jobs ↗` on Launch / Registry,
`j-0212 · finished · open in Jobs ↗` on Results / Compare). **Discovery has no tab bar** in any
frame: the header page title changes (`Runs` / `Seed search` / `Compare` / `Compare every stage`)
and navigation is by in-page controls (runs list *Seed search* / *Compare*, `‹ all runs`,
`Compare every stage`, `‹ compare`). Do not invent Discovery tabs.

**Header.** Every page: `<Workspace> | <Page>  <subtitle>` left; search pill `Search spans, runs,
families  Ctrl K`, `● 3 need you` (blue), `🔒 M4 held out` (grey) right; plus the kit "demo data" chip.
Nav rail foot shows `Jobs · 3`.

## Pages

| page id | route | frames covered | spec § | states (frame → state → how reached) |
|---|---|---|---|---|
| discovery.runs | `#/discovery/runs` | discovery-1-runs, discovery-1b-add-template, discovery-1c-many-channels | §7.1–7.5, P17, P16, P8 | 1 → `default` (3 channels, drop_motifs9 picked A, browser 12/72) → nav rail Discovery / `#/discovery/runs` · 1b → `modal:add-template` → *Apply template* / `?modal=add-template` · 1c → `scope:six-channels page 2` → *+ channel* ×3 then pager ▲▼ / `?channels=CH2_A1,CH4_A2,CH7_B2,CH8_B2,CH9_C1,CH11_C2&chpage=2` · (no frame) `modal:slurm` → toolbar *Create SLURM script for 2* / `?modal=slurm` · (no frame) `popover:history` → *History* / `?popover=history` · (no frame) `confirm:discard` → *Discard run* / `?confirm=discard` · (no frame) `fires:spans` → Seg *spans* / `?fires=spans` |
| discovery.seed | `#/discovery/seed` (optional `/<draftId>`, default `seed_F03_native_2`) | discovery-2-seed | §7.6, P17 | 2 → `draft` (Library exemplar E-0102, threshold 2.8 → 3.1, 1 unapplied change) → *Seed search* button / `#/discovery/seed` · (no frame) `source:explore` / `source:medoid` → Seg / `?source=explore\|medoid` · (no frame) `running` → *Run seed search* / `?state=running` · (no frame) `done` → sim end / `?state=done` · (no frame) `modal:save-template` → *Save as template* / `?modal=save-template` |
| discovery.compare | `#/discovery/compare` | discovery-3-compare | §7.7 | 3 → `default` (A drop_motifs9 · B seed_F03_native, filter only A, 7/106) → pick two runs + *Compare* / `?a=drop_motifs9&b=seed_F03_native&only=a&i=7` · (no frame) `filter:all` / `filter:only-b` → Seg / `?only=all\|b` · (no frame) `swapped` → *Swap A / B* (swaps `a`/`b` params) · (no frame) `diff-popover` → info icon on "3 of 5 roles differ" / `?popover=roles` |
| discovery.stages | `#/discovery/compare/stages` | discovery-3b-stages | §7.8 | 3b → `default` (7/106, first differing role Score / estimate) → *Compare every stage* / `?a=drop_motifs9&b=seed_F03_native&only=a&i=7` · stepping ‹ › changes `i` |
| models.launch | `#/models/launch` | models-1-launch, models-1b-launch-from-window-set | §7b.1, P11, P18, P19 | 1 → `signal-template` (cnn_windows_v3, 3 channels, over 2 h → SLURM) → tab *Launch* / `#/models/launch` · 1b → `windowset-template` (cnn_windowset_v1, ws_M2aug_3ch_600s v1, split locked) → template select / `?template=cnn_windowset_v1` · (no frame) `local-allowed` (estimate ≤ 2 h → *Train locally* primary) → uncheck two channels / `?est=local` · (no frame) `training-local` → *Train locally* / `?state=running` · (no frame) `submitted` → *Create SLURM script* / `?state=submitted` · (no frame) `m4-refused` popover → click M4 toggle / `?popover=m4` · (no frame) `add-arm` popover → *Add arm* / `?popover=add-arm` |
| models.results | `#/models/results` (optional `/j-0212`) | models-3-results | §7b.3 | 3 → `arm:a` → tab *Results* / `?arm=a` · (no frame) `arm:b`, `arm:rf` → arm Seg / `?arm=b\|rf` · (no frame) `job-picker` popover → `j-0212 · test block ▾` / `?popover=job` |
| models.compare | `#/models/compare` | models-4-compare, models-4b-compare-both-wrong | §7b.4 | 4 → `filter:only-a-right i=7` → tab *Compare* or Results *Compare arms* / `?a=cnn_windows_v3.manual&b=cnn_windows_v3.cluster&filter=only-a&i=7` · 4b → `filter:both-wrong i=12` → Seg *both wrong 54* or click the 2×2 "both wrong" cell / `?filter=both-wrong&i=12` · (no frame) `filter:only-b` → `?filter=only-b` · (no frame) `not-attributable` → pick B = `cnn_windows_v2 · manual` / `?b=cnn_windows_v2.manual.v2` · (no frame) `picker` popover → *any two models* / `?popover=models` |
| models.registry | `#/models/registry` (optional `/<modelId>`, default `cnn_windows_v3.manual`) | models-5-registry | §7b.5, P19 | 5 → `candidate selected, verification 33/40, Register disabled` → tab *Registry* or Results *Send to registry* / `#/models/registry/cnn_windows_v3.manual` · (no frame) `filter:*` → Seg / `?filter=registered\|candidates\|retired` · (no frame) `verified` (40/40, Register enabled) → `?state=verified` · (no frame) `confirm:reject` / `confirm:retire` → *Reject* / `?confirm=reject` · (no frame) `why` popover on rejected row → *Why* / `?popover=why` · (no frame) `registered` model selected → click `cnn_windows_v2 · manual` row |

---

## discovery.runs

### Route & states
- **default** (frame 1, a scrolling page ~1050 px tall) — `#/discovery/runs`. Session `ch_screen_sep14`,
  scope `M2_aug_concat_fs1` × `CH2_A1 CH4_A2 CH7_B2` × section `112–286 h`; runs list with 5 runs + the
  human reference row; `drop_motifs9` selected (blue border) and picked as **A**; footer `1 of 2 picked`;
  browser on `drop_motifs9 · CH4_A2 · 12 / 72` (`d-0412`); where-each-run-fires in `density`; scoreboard
  with `drop_motifs9` expanded.
- **modal:add-template** (frame 1b) — click runs-list *Apply template* (or toolbar-less deep link
  `?modal=add-template`). Modal over the page; Escape / × / *Cancel* closes and removes the param.
  In-modal focus row `?tpl=mp_discord_v3` optional.
- **scope:six-channels** (frame 1c, a crop of frame 1) — six channels in scope, page 2 of the strip pager.
  Reached by *+ channel* adding `CH8_B2`, `CH9_C1`, `CH11_C2`, then ▼. Deep link
  `?channels=CH2_A1,CH4_A2,CH7_B2,CH8_B2,CH9_C1,CH11_C2&chpage=2`. Where-each-run-fires follows the pager.
- **modal:slurm** (no frame; §7.5 "same rule applies to the toolbar's run button") — toolbar
  *Create SLURM script for 2* opens a Modal with the script (same body as models.launch SLURM card).
- **toolbar:run-local** (no frame) — when the pending estimate ≤ Discovery limit 20 min the toolbar
  primary becomes blue `▷ Run N` and runs a simulation (`useSim('discovery.run.<runId>')`, stages
  from the template) → row shows `running` progress → `done`.
- **popover:history** (no frame) — *History* opens an anchored Popover (P2 pattern).
- **confirm:discard** (no frame) — *Discard run* opens a confirm Modal.
- **fires:spans** (no frame) — density · spans Seg switched to spans.
- **paused row** (in frame 1) — `mp_drops_v3 · r-0431` paused 3/4 (B22). Not a separate state.

### Regions (1440 × ~1050, top → bottom)
1. **Header** (48 px): `Discovery | Runs  apply saved templates and seed searches across channels`.
2. **Toolbar row** (~56 px, no card): left → `📁 ch_screen_sep14 ✎ saved` chip; `≋ M2_aug_concat_fs1 · 3
   channels · 112–286 h ▾` blue chip. Right → `● null circular shift 200× (i)` chip (green dot);
   `⌛ ≈ 38 min routes to cluster` amber chip; `⟲ History` button; `📄 Create SLURM script for 2`
   purple primary button.
3. **Scope card** (full content width, ~160 px): title `Scope (i)`; `recording M2_aug_concat_fs1.mat ▾`
   (grey select); channel chips `CH2_A1 ×` `CH4_A2 ×` `CH7_B2 ×` (blue); `+ channel` (outline pill);
   right: `section 112–286 h · 174 h × 3 ch = 522 h ▾` (blue chip) and `⚗ Preview on a 4 h sample`
   button. Below: three overview strips (~32 px each, light ground, dark trace, labels `CH2_A1`,
   `CH4_A2`, `CH7_B2` at left, ~90 % width) with **one shared brush** (translucent blue rectangle
   spanning all three strips, draggable edge handles on the middle strip) covering 112–286 h of 721 h;
   at far right a vertical pager: ▲ button, `1–3 of 3`, ▼ button (both disabled at 3 channels).
4. **Two columns** below the scope card:
   - **Left: Runs card** (~300 px wide ≈ 22 % of content, full remaining height ~740 px). Title
     `Runs (i)  5 in this session`; buttons row `⧉ Apply template` | `◎ Seed search` (two equal outline
     buttons). Run rows (cards, ~64 px each, left colour stripe 3 px, glyph thumbnail 40×28 left,
     compare checkbox right):
     1. `human annotations` · badge `reference` (grey) · `41 h reviewed` · green stripe · checkbox.
     2. `drop_motifs9` · badge `template` · `v9 · 4 stages` · `160 found · 3 ch · done 11:02` · blue stripe
        · selected (blue border, light-blue fill) · pick box shows **A** (solid blue square).
     3. `sharkfin_v2` · `template` · `v2 · 4 stages` · progress bar (blue fill 64 %) + `cluster 64 %`
        (blue) · teal stripe · checkbox.
     4. `seed_F03_native` · badge `seed` (purple) · `F-03 medoid · MASS` · `63 found · 3 ch · done 11:40` ·
        purple stripe · checkbox.
     5. `seed_E0102_bank` · `seed` · `E-0102 · 3 lengths` · `new · local` · rose stripe · checkbox.
     6. `mp_drops_v3 · r-0431` · `template` · `v3 · 4 stages` · amber progress bar (75 %) + `paused 3/4` ·
        `Open in Jobs ↗` link (blue) · amber border + pale amber fill · no checkbox.
     Card foot (pinned bottom): `1 of 2 picked` muted; `⇆ Compare` button (disabled).
   - **Right column** (~1017 px ≈ 76 %), stacked cards:
     a. **Where each run fires** (~240 px): title `Where each run fires (i)  detections per 3 h ·
        grouped by channel`; right: Seg `density | spans`, legend `reviewed hours` swatch + ramp
        `0 ▢▢▢▢■ 4+ per 3 h`. Body: three channel groups (`CH2_A1`, `CH4_A2`, `CH7_B2` bold at left,
        ~70 px column), each with 4 labelled rows (`■ human` green, `■ drop_motifs9` blue,
        `■ sharkfin_v2` teal, `■ seed_F03_native` purple; ~11 px rows, 2 px gap). Shared x-axis
        `112 h 141 170 199 228 257 286 h`.
     b. **Scoreboard** (~240 px): title `Scoreboard (i)  per run · expand a run for its channels`; right
        link `⟳ Refresh after reviewing`. Table (see Controls).
     c. **Browse detections** (~170 px): title `Browse detections (i)`; right: chip-select
        `run drop_motifs9 ▾` (blue), chip-select `channel CH4_A2 ▾` (grey), pager `‹ 12 / 72 ›`,
        `👁 browse only` muted. Body: left KeyValue column (~190 px) and a signal plot (rest).
     d. **Run acts footer bar** (~52 px card): `● drop_motifs9  160 detections · 3 channels · 8 already
        judged`; right: `🗑 Discard run` (outline), `⧉ Analyse events` (outline),
        `→ Send 110 unjudged to Review` (blue primary).

**1b modal** (frame 1b; ~950 × 710 px, centred, page behind dimmed/hidden): header `Add runs` + Seg
`Apply template | Seed search` + `×`. Body split: **left list** (~58 %) and **right detail** (~42 %,
divider). Footer bar full width.
- Left top: `🔍 Search templates` Text (~160 px); chip-toggle `fits Signal → SpanSet ✓` (blue, on);
  `kind all ▾`; right `sort last used ▾`.
- Notice bar (grey): `Models run inside detection templates — add a Model stage in Analyse` + link
  `↗ Open Analyse`.
- Template rows (~66 px cards): checkbox · name (bold) · type badge + signature (mono muted) ·
  subline · **glyph strip** right (2–4 glyph thumbs with `›` between):
  1. ☑ `mp_discord_v3` · `template` `Signal → Scores → SpanSet` · `not yet scored · saved 12 Sep` ·
     focused (blue border) · glyphs baseline › matrix-profile › threshold.
  2. ☑ `spike_shape_v1` · `template` `Signal → SpanSet` · `precision 31 % over 88 reviewed` · glyphs
     gaussian-shape › spike-mark › band-detect.
  3. ☐ disabled `drop_motifs9` · `template` `Signal → SpanSet` · `in this session` · 4 glyphs.
  4. ☐ disabled `sharkfin_v2` · `template` `Signal → SpanSet` · `in this session` · 4 glyphs.
  5. ☐ disabled `seed_F03_native` · `seed` `Signal + exemplar → SpanSet` · `already in this session ·
     runs from medoid m-1846` · glyphs seeded-search › threshold.
  6. ☐ `seed_sharkfin_rebind` · `seed` `Signal + exemplar → SpanSet` · `rebind · asks for an exemplar`.
- Right detail: `mp_discord_v3` + badge `template`; right link `↗ Open in Analyse`. `Stages` list rows
  (glyph 36×24, name bold, signature muted, locked param right with 🔒):
  `● Source — → Signal`; `01 Baseline removal Signal → Signal 🔒 window 3 h`; `02 Matrix profile
  Signal → Scores 🔒 m 600 s · STUMP`; `03 Threshold to spans Scores → SpanSet 🔒 below p5 of null`.
  Grey note `🔒 parameters come from the template (i)`. `Channels in scope`: ☑ `CH2_A1  174 h  ≈ 2.1 h`
  (estimate amber), ☑ `CH4_A2 …`, ☑ `CH7_B2 …`. Three StatTiles: `compute ≈ 6.4 h` (amber) `O(n²) per
  channel`; `disk 0.6 GB` `scores kept`; `null 200×` `circular shift`. Sample preview card:
  `⚗ Sample preview  4 h of CH4_A2` + badge `done` (green); `11 spans in 4 h · null gives 2 → ≈ 1,435
  over 522 h`; amber line `above the local ceiling → routes to cluster`.
- Footer: `2 templates selected  × 3 channels`; amber `≈ 6.5 h · cluster`; `Cancel`; `+ Add 2 runs`
  (outline); `▷ Add and run` (disabled); `📄 Create SLURM script` (purple primary).

**1c crop** (frame 1c): Scope card without the recording select / + channel / Preview (crop shows
chips row only): chips `CH2_A1 × CH4_A2 × CH7_B2 ×` (grey — not on the visible page) and
`CH8_B2 × CH9_C1 × CH11_C2 ×` (blue — visible page); section chip `section 112–286 h · 174 h × 6 ch =
1044 h`; strips `CH8_B2`, `CH9_C1`, `CH11_C2`; pager ▲ (enabled, blue outline) `4–6 of 6` ▼ (disabled).
Where-each-run-fires caption `channels 4–6 of 6 · follows the scope pager`; groups CH8_B2 / CH9_C1 /
CH11_C2, each human row `no reviewed hours in this section`.

### Controls & interactions
Toolbar
- `ch_screen_sep14 ✎ saved` — Chip with inline rename (Text). Rule: required, `^[A-Za-z0-9_\-]{3,40}$`
  → message `letters, digits, _ and - only (3–40)`. Editing flips `saved` → `unsaved` (amber) until
  Enter; Enter writes in memory (`useDemoState('discovery.session')`) + toast `not wired yet: save
  Discovery session`.
- `M2_aug_concat_fs1 · 3 channels · 112–286 h ▾` — Chip; click scrolls the Scope card into view and
  focuses the section chip (summary of scope; label recomputed from scope state).
- `null circular shift 200× (i)` — Chip + InfoTip popover: `Every run carries a null: circular shift,
  200×, same scope. "Null expects" and "× null" in the scoreboard come from it.` link `Settings › Nulls`
  → `#/settings/nulls`.
- `≈ 38 min routes to cluster` — cost Chip (amber when > 20 min Discovery limit, grey `≈ N min local`
  otherwise). Click → Popover breakdown per pending run (`seed_E0102_bank ≈ … `) + `local limit 20 min
  · Settings › Compute & HPC` link `#/settings/compute-hpc`.
- `History` — Popover (P2): past Discovery runs on this recording (`r-0412 mp_drops_v3`,
  `r-0415 seed search E-0102`, `r-0431 mp_drops_v3 paused`), each with `Open` (adds to session, in
  memory) disabled with reason `already in this session` where applicable.
- `Create SLURM script for 2` — primary purple while pending estimate > 20 min: opens `?modal=slurm`
  (CodeBlock script, Copy, Save .sh, note `Creating the script adds 2 jobs to Jobs · results return
  through Jobs › Manifest inbox`, buttons `Cancel` / `Create`). *Create* → in-memory jobs written,
  pending runs' badge → `on cluster`, toast `2 jobs added to Jobs` with link `#/jobs`, plus toast
  `not wired yet: POST /discovery/runs/slurm`. When estimate ≤ 20 min the same slot renders
  `▷ Run N` (blue) → simulated run.

Scope card
- `recording M2_aug_concat_fs1.mat ▾` — Select of the 5 canon recordings; `M4_aug` option disabled with
  reason `held out · locked (D6)`. Changing recording opens a confirm Popover `Changing the recording
  clears 3 channels and marks 5 runs stale` → *Change* resets channels (in memory).
- channel chips `×` — remove channel from scope; updates section maths (`174 h × 2 ch = 348 h`), strips,
  fires groups, scoreboard child rows, cost chip. Last chip cannot be removed: × disabled with tooltip
  `scope needs at least one channel`.
- `+ channel` — Popover checklist of the recording's channels (16 `CHn_XY`), in-scope ones checked;
  apply adds chips. At > 3 channels the pager enables.
- `section 112–286 h · … ▾` — Popover with RangeSlider (0–721 h) + two Number fields `from` / `to` (h,
  2 dp). Validation: `0 ≤ from < to ≤ 721` → `section must lie inside 0–721 h`; `to − from ≥ 1` →
  `section must be at least 1 h`. Kept in sync with the brush.
- Brush on strips — drag body to move, drag handles to resize; snaps to 1 h; writes section.
- Pager ▲ / ▼ + `1–3 of 3` — pages strips three at a time; disabled at ends; highlights chips of the
  visible page (blue) and greys the rest; drives where-each-run-fires (`chpage` param).
- `Preview on a 4 h sample` — `useSim('discovery.preview')` ~1.5 s (`queued → running → done`), then
  toast-like inline result under the button: `4 h of CH4_A2 · drop_motifs9 11 · sharkfin_v2 … ·
  extrapolated ≈ N over 522 h`; disabled with reason `nothing to preview — every run in this session has
  results` when no run is `new`/`draft`.

Runs card
- `Apply template` → open `?modal=add-template`.
- `Seed search` → navigate `#/discovery/seed`.
- Row click → selects run (blue border): sets browser run, footer run, highlights scoreboard row.
  Human row click → browser disabled with note `human annotations have no detections to browse`.
- Compare checkbox → first pick shows **A** (blue square), second **B** (purple square); a third pick
  replaces B. Drafts: checkbox absent. Paused row: no checkbox (frame). Running row: pickable.
- Footer `N of 2 picked` + `Compare` — DisabledReason until 2 picked: `pick two runs to compare`;
  with 2 → enabled → navigate `#/discovery/compare?a=<A>&b=<B>`.
- Paused row `Open in Jobs ↗` → `#/jobs/paused/r-0431` (Jobs inventory owns the exact route; frame
  jobs-2-paused-run).
- sharkfin_v2 progress `cluster 64 %` — static (on cluster; hand-marked status lives in Jobs).

Where each run fires
- Seg `density | spans` — `density` default. `spans` draws each detection as a 1 px tick per run row;
  at section scale > 24 h show an inline muted note `spans are thinner than a pixel at this scale ·
  zoom the section below 24 h` (spec: spans when zoomed in). Param `fires`.
- Cell hover → Tooltip `CH4_A2 · drop_motifs9 · 189–192 h · 4 detections`. Cell click → browser jumps
  to the first detection of that run/channel in the bin (updates run, channel, `i`).
- Current-detection marker (black ▼ + vertical line through the channel group) follows the browser.

Scoreboard
- Table columns: `run` · `found` · `already judged` · `reviewed` · `interesting` · `precision` ·
  `recall · reviewed overlap` · `null expects` · `× null`. Row chevron `›/⌄` toggles per-channel child
  rows (indented, muted). Rows: see Fixtures. Running row spans columns: `running on cluster · 64 % ·
  scores appear when it finishes`; new row: `new · local`. Colour dot before run name.
- Sort by header click (Table kit) on numeric columns; child rows stay with parent.
- `Refresh after reviewing` → `useSim('discovery.scores.refresh')` 600 ms → toast `scores refreshed ·
  no new verdicts since 11:40` (demo) + `not wired yet: GET /discovery/sessions/ch_screen_sep14/scores`.

Browse detections
- `run drop_motifs9 ▾` — Select of runs with results (human excluded; running/new disabled with reason
  `no detections yet`).
- `channel CH4_A2 ▾` — Select of channels in scope, option label `CH4_A2 · 72`.
- Pager `‹ 12 / 72 ›` — steps detections in time order; `‹` disabled at 1, `›` at N. Keyboard `←` / `→`
  when the card has focus (not shown in frame; optional).
- `browse only` — static muted chip with InfoTip `Verdicts are given in Review (P6).`
- `also found by ● seed_F03_native` — link: selects that run in the browser at the matched detection.

Run acts footer (acts on the selected run)
- `Discard run` → `?confirm=discard` Modal: title `Discard drop_motifs9?`, body `Marks the run
  superseded. Writes no adjudications — its 160 detections are not marked not_interesting.`
  (§7.4 rationale), buttons `Cancel` / `Discard run` (red). Confirm → in-memory status `superseded`,
  row greyed with badge `superseded`, removed from fires/scoreboard; toast `drop_motifs9 discarded`.
- `Analyse events` → navigate `#/analyse/chain` + toast `not wired yet: send SpanSet of drop_motifs9 to
  Analyse`.
- `Send 110 unjudged to Review` → in-memory: adds a Review queue entry (`q-12`-style, tagged run id)
  → toast `110 detections sent to Review · tagged drop_motifs9` + link `Open Review` → `#/review`.
  Button then reads `Sent 110 · refresh after reviewing` (disabled). N = found − reviewed. Disabled
  with reason `nothing unjudged` when N = 0; hidden-disabled for running/new runs `no detections yet`.

1b modal
- Seg `Apply template | Seed search` — *Seed search* closes the modal and navigates `#/discovery/seed`.
- `×`, Escape, `Cancel` — close (remove `modal` param).
- `Search templates` — Text filter on name (case-insensitive, live).
- `fits Signal → SpanSet ✓` — toggle chip. On: only fitting templates. Off: non-fitting templates
  (e.g. training templates `cnn_windows_v3` `Signal → … → Model`) appear disabled with reason
  `doesn't fit Signal → SpanSet — Discovery applies detection templates`.
- `kind all ▾` — Select all / template / seed. `sort last used ▾` — last used / name / precision.
- `Open Analyse ↗` (notice) → `#/analyse/chain`.
- Row click → focuses row (detail pane). Checkbox toggles selection. Disabled rows: checkbox disabled,
  subline is the reason (`in this session`, `already in this session · runs from medoid m-1846`).
- `seed_sharkfin_rebind` checked → detail pane shows a required Select `exemplar ▾` (E-0102 · exemplar
  of F-03, …); until chosen the footer add buttons are disabled with reason `seed_sharkfin_rebind needs
  an exemplar`.
- Detail `Open in Analyse ↗` → `#/analyse/chain` + toast `not wired yet: import template mp_discord_v3`.
- Locked params — read-only; 🔒 InfoTip `parameters come from the template · Open in Analyse to change them`.
- `Channels in scope` checkboxes — see Frame ⟷ spec conflicts; recommended read-only (checked, disabled
  with reason `a template runs across every channel in scope`).
- Footer counts recompute from selection: `N templates selected × 3 channels`, estimate `≈ X h ·
  cluster` (amber) or `≈ X min · local` (grey). Rule (§7.5, local limit 20 min):
  - estimate ≤ 20 min → `+ Add N runs` (outline) and `▷ Add and run` (blue primary) enabled; SLURM hidden.
  - estimate > 20 min → `▷ Add and run` disabled with DisabledReason `above the 20 min local limit ·
    create a SLURM script`; `📄 Create SLURM script` purple primary.
  - 0 selected → all add buttons disabled `select at least one template`.
- `+ Add N runs` → append runs (status `new`) to session (in memory), close, toast `2 runs added`.
- `▷ Add and run` → append + start sims.
- `Create SLURM script` → append runs with badge `on cluster` pending, open `?modal=slurm`.

### Plots
- **Scope strips** (3 visible × ~32 px): Trace, light ground, dark 1 px line, full recording 0–721 h on
  x (no axis labels shown), y auto per strip in mV (unlabelled overview — acceptable; never
  normalised: shared mV y-domain across strips). Brush overlay. Fixture: decimated synthetic trace per
  channel (~720 points, `syntheticTrace`).
- **Where each run fires**: Raster/Matrix of density bins. x = hours since recording start, domain =
  section (112–286 h), bin 3 h (58 bins); rows = run within channel group; mark = rect per bin, fill =
  run colour, opacity by count (0 → none, 4+ → full) with the grey ramp legend; human row: grey
  reviewed-hours underlay rects + green density; running run: bins after its progress point empty with a
  white outlined box `on cluster · 64 %`; human row with no review: full-width grey text
  `no reviewed hours in this section`. Channel groups capped at 3 visible (pager). Fixture
  `discoveryFires[channel][run] = number[58]`, `reviewedHours[channel] = number[58]` (0–3 h per bin).
- **Browse detections signal**: Trace, x `192.0 h … 192.8 h` (hours since start; frame shows only the
  two end labels), y mV (**add a small mV axis** — frame omits it, §3), blue translucent band on the
  detection (≈192.35–192.45 h). Fixture: synthetic trace ~2,900 samples at 1 Hz with a 0.38 mV drop.
- **1b glyphs**: Glyph registry thumbnails (chain 6b) — static.

### Fixtures (TypeScript sketch)
```ts
// shared canon (extend fixtures/canon.ts): runs, templates, recordings, channels, jobs, families
type RunKind = 'reference' | 'template' | 'seed' | 'draft'
type RunStatus = 'done' | 'on cluster' | 'new' | 'paused' | 'running' | 'draft' | 'superseded'
interface DiscoveryRun {
  key: string            // 'drop_motifs9' — unique in session; route param a/b
  id?: string            // 'r-0431' only where canon names one (see Fog)
  label: string; kind: RunKind; colour: string   // human #22A06B, drop_motifs9 blue #0A84FF, sharkfin_v2 teal, seed_F03_native purple #AF52DE, seed_E0102_bank rose, mp_drops_v3 amber
  template?: string; version?: number; stages?: number; seed?: { exemplar?: 'E-0102'; medoid?: 'm-1846'; family?: 'F-03'; algorithm: 'MASS'; lengths?: number }
  status: RunStatus; progress?: number /*0–1*/; pausedAt?: { stage: 3; of: 4; job: 'j-0217' }
  found?: number; channels: number; doneAt?: string /*'11:02'*/; reviewedHours?: number /*human: 41*/
  glyph: GlyphKey
}
const SESSION = { name: 'ch_screen_sep14', saved: true, recording: 'M2_aug_fs1', channels: ['CH2_A1','CH4_A2','CH7_B2'],
  section: [112, 286], null: { method: 'circular shift', n: 200 }, estimateMin: 38, localLimitMin: 20 }
const RUNS: DiscoveryRun[] = [
  { key: 'human', label: 'human annotations', kind: 'reference', reviewedHours: 41, … },
  { key: 'drop_motifs9', kind: 'template', version: 9, stages: 4, found: 160, channels: 3, doneAt: '11:02', status: 'done' },
  { key: 'sharkfin_v2', kind: 'template', version: 2, stages: 4, status: 'on cluster', progress: 0.64 },
  { key: 'seed_F03_native', kind: 'seed', seed: { medoid: 'm-1846', family: 'F-03', algorithm: 'MASS' }, found: 63, channels: 3, doneAt: '11:40', status: 'done' },
  { key: 'seed_E0102_bank', kind: 'seed', seed: { exemplar: 'E-0102', algorithm: 'MASS', lengths: 3 }, status: 'new' },
  { key: 'mp_drops_v3', id: 'r-0431', kind: 'template', version: 3, stages: 4, status: 'paused', progress: 0.75, pausedAt: { stage: 3, of: 4, job: 'j-0217' } },
]
interface ScoreRow { run: string; channel?: string; found: number; alreadyJudged: number; reviewed: number; interesting: number;
  precision: number; recall: { value: number; overH: number } | 'no reviewed overlap' | { tooFewH: number }; nullExpects: number; xNull: number }
// drop_motifs9: 160 · 8 · 50 · 12 · 24 % · 0.71 over 14 h · 26 · 6.2×
//   CH2_A1 41 · 2 · 12 · 3 · 25 % · no reviewed overlap · 7 · 5.9×
//   CH4_A2 72 · 5 · 30 · 8 · 27 % · 0.71 over 14 h · 11 · 6.5×
//   CH7_B2 47 · 1 · 8 · 1 · 13 % · "6 h · too few" · 8 · 5.9×
// seed_F03_native: 63 · 19 · 40 · 7 · 18 % · 0.52 over 14 h · 9 · 7.0×  (child rows: invent, sums must reconcile: found 30+28+5? see compare set overlap → CH2 14, CH4 31, CH7 18)
interface Detection { id: 'd-0412'; run: string; channel: string; atH: 192.4; depthMv: 0.38; score: 0.88; priorVerdict: null | string; alsoFoundBy: string[]; index: 12; ofChannel: 72 }
interface DiscoveryTemplate { name: string; kind: 'template' | 'seed'; signature: string; fits: boolean; lastScore: string /*'not yet scored · saved 12 Sep'*/;
  stages: { index: string; name: string; signature: string; locked?: string; glyph: GlyphKey }[];
  perChannelH: number /*2.1*/; computeH: number; diskGB: number; nullN: 200; preview?: { spans: 11; hours: 4; channel: 'CH4_A2'; nullGives: 2 };
  bind?: 'carry' | 'rebind'; inSession?: boolean; disabledReason?: string }
// mp_discord_v3 (computeH 6.4, disk 0.6), spike_shape_v1 (computeH ≈0.1 → Add and run allowed alone), drop_motifs9, sharkfin_v2, seed_F03_native, seed_sharkfin_rebind
```
Shared with other workspaces: recordings/channels (canon), templates (Library 7, Analyse import),
jobs `j-0217` / `r-0431` (Jobs), Review queue writes (Review `q-12`), families F-03 / E-0102 / m-1846
(Library, Review). Fires bins, detections and per-channel score rows are Discovery-local.
1c needs child score rows and fires bins for CH8_B2, CH9_C1, CH11_C2 (frame shows fires only).

### Copy
`apply saved templates and seed searches across channels` · `saved` · `null circular shift 200×` ·
`≈ 38 min routes to cluster` · `History` · `Create SLURM script for 2` · `Scope` · `recording` ·
`+ channel` · `section 112–286 h · 174 h × 3 ch = 522 h` · `Preview on a 4 h sample` · `1–3 of 3` ·
`Runs` `5 in this session` · `Apply template` · `Seed search` · `human annotations` `reference`
`41 h reviewed` · `160 found · 3 ch · done 11:02` · `cluster 64 %` · `new · local` · `paused 3/4` ·
`Open in Jobs ↗` · `1 of 2 picked` · `Compare` · `Where each run fires` `detections per 3 h · grouped by
channel` · `density` `spans` `reviewed hours` `0` `4+ per 3 h` · `no reviewed hours in this section` ·
`on cluster · 64 %` · `Scoreboard` `per run · expand a run for its channels` · `Refresh after reviewing`
· `no reviewed overlap` · `6 h · too few` · `running on cluster · 64 % · scores appear when it finishes` ·
`Browse detections` · `browse only` · `d-0412` `192.4 h · CH4_A2` `depth 0.38 mV · score 0.88`
`no prior verdict` `also found by` · `160 detections · 3 channels · 8 already judged` · `Discard run` ·
`Analyse events` · `Send 110 unjudged to Review`. 1b: `Add runs` · `Search templates` ·
`fits Signal → SpanSet` · `kind all` · `sort last used` · `Models run inside detection templates — add a
Model stage in Analyse` · `Open Analyse` · `not yet scored · saved 12 Sep` · `precision 31 % over 88
reviewed` · `in this session` · `already in this session · runs from medoid m-1846` · `rebind · asks
for an exemplar` · `Stages` · `parameters come from the template` · `Channels in scope` · `compute`
`O(n²) per channel` · `disk` `scores kept` · `null` `circular shift` · `Sample preview` `4 h of CH4_A2`
`done` · `11 spans in 4 h · null gives 2 → ≈ 1,435 over 522 h` · `above the local ceiling → routes to
cluster` · `2 templates selected` `× 3 channels` `≈ 6.5 h · cluster` · `Cancel` `Add 2 runs`
`Add and run` `Create SLURM script`. 1c: `channels 4–6 of 6 · follows the scope pager` · `4–6 of 6`.

### Live vs demo
Not applicable (Discovery is not a live workspace). Everything reads through `api/discovery.ts`
`demo(...)`; the page shows the demo-data chip. `App.tsx` currently renders `Inert` for `discovery`
with `page: 'Runs'` — replace with the Discovery router; NavRail `to: 'discovery'` should become
`discovery/runs`.

### Frame ⟷ spec conflicts
1. **Paused run missing from fires and scoreboard.** Frame 1 lists `mp_drops_v3 · r-0431` in Runs
   (5 in session) but no row in where-each-run-fires or the scoreboard. §7.2/§7.3 say a running or
   queued run "says so across the row". Recommend: add a scoreboard row `paused at stage 3 of 4 ·
   waiting on j-0217 · Open in Jobs ↗` and fires rows that are empty with outline `paused 3/4`.
2. **Runs count differs across frames**: frame 1 `5 in this session`; 1b / 2 / 3 underlays say `4`
   and omit mp_drops_v3 (frame 2 also omits seed_F03_native). Recommend one session fixture (frame 1's
   5 runs) on every Discovery page; seed page adds the draft row (6).
3. **1b per-channel checkboxes** vs §7.5 "each template becomes one run across all channels in scope".
   Recommend: render checked + disabled with the reason (keeps frame look, obeys spec).
4. **Toolbar run button**: frame 1 `Create SLURM script for 2`; the 1b underlay says `Run 2 queued`.
   Frame 1 wins (frame 1 is the page frame; §7.5 rule).
5. **Recording naming**: frames show `M2_aug_concat_fs1(.mat)`; §0 canon label is `M2_aug fs1` with that
   file. Not a real conflict — show the file stem where the frame does (it is the canon `source_file`).
6. **Run colours**: seed_E0102_bank's stripe is rose/red; §3 reserves red for artifact/destructive.
   Recommend a non-semantic categorical colour (e.g. `#E85AAD`-adjacent pink is F-02's family colour —
   pick a run palette distinct from both families and semantics; flag to kit owner).
7. **`spike_shape_v1` as `Signal → SpanSet`** in 1b; canon ties spike_shape_v1 to `#140 F-03 slope
   interrogation` (a Features chain). Frame wins for Discovery's picker fixture; flag to canon owner.

### Fog
- F1. Which two runs does `Create SLURM script for 2` cover? Only `seed_E0102_bank` is `new`;
  sharkfin_v2 is already on cluster. Recommend computing N from runs with status `new` and seeding the
  frame's `2` via a second pending fixture (or accept `for 1`). Needs a decision.
- F2. Run ids: canon names `r-0412 mp_drops_v3`, `r-0415 seed search E-0102`, `r-0431 mp_drops_v3`;
  frame 1 has two mp_drops_v3-like runs only once and gives no ids for drop_motifs9 / seed runs. Routes
  use run **keys** (names), not ids.
- F3. History popover content and the scope-chip click behaviour are not drawn.
- F4. Preview-on-sample result display on the runs page is not drawn (only in 1b's detail).
- F5. `recall · reviewed overlap` for the pooled run row ("0.71 over 14 h") equals CH4_A2 alone although
  CH7_B2 has 6 h reviewed ("too few") — plausible (too-few channels excluded) but unstated.
- F6. Where-each-run-fires `spans` mode is not drawn; zoom mechanism (section brush only) unspecified.
- F7. 1c needs score/fires numbers for CH8_B2, CH9_C1, CH11_C2 that no frame gives.
- F8. Changing recording with runs in session: consequence not specified.

---

## discovery.seed

### Route & states
- **draft** (frame 2, scrolling ~1060 px) — `#/discovery/seed` (= `#/discovery/seed/seed_F03_native_2`).
  Reached from runs-list *Seed search* (any Discovery page) or 1b's Seg *Seed search*; also from
  Library atlas / family "seed search" hand-offs (Library inventory) with `?exemplar=E-0102`. Seed
  source Seg on *Library exemplar*; `carry` selected; threshold moved 2.8 → 3.1 (1 unapplied change);
  distance profile on `CH4_A2 · 192.0–194.0 h`; matches page 1–8 of 41.
- **source:explore** (no frame) — Seg *Explore selection* / `?source=explore`. If app state
  `source` (the live `SourceSpan` handed from Explore, `state.tsx`) exists → seed card shows that span
  (`<channel> · <start>–<end> h · <n> samples`); else EmptyState `No span selected in Explore` + link
  `Select a span in Explore ↗` → `#/explore/corpus`.
- **source:medoid** (no frame) — `?source=medoid`: seed card shows `m-1846 · medoid of F-03` with the
  same provenance layout.
- **running** / **done** (no frame) — *Run seed search* → `useSim('discovery.seed.seed_F03_native_2')`
  (≈3 s local, steps `MASS CH2_A1`, `MASS CH4_A2`, `MASS CH7_B2`, `null 200×`). Deep links
  `?state=running|done` via `forceSim`.
- **modal:save-template** (no frame) — `?modal=save-template`.
- **revert** — *Revert to recommended* (threshold back to 2.8; bar shows `draft · no unapplied changes`).

### Regions (1440 × ~1060)
1. Header: `Discovery | Seed search  find more of a shape you already have`.
2. Toolbar: `ch_screen_sep14 ✎ saved`; `M2_aug_concat_fs1 · 3 channels · 112–286 h ▾`; right:
   `● null circular shift 200× (i)`; `⌛ ≈ 3 s local · 3 channels` (grey, no chip fill); `⟲ History`.
   **No primary button in the toolbar** (the run button is in the apply bar).
3. Scope card — identical to discovery.runs (shared component).
4. Left: **Runs card** (as runs page) with rows human annotations · drop_motifs9 · sharkfin_v2 ·
   **seed_F03_native_2** (selected, purple stripe, badge `draft` amber, `E-0102 exemplar · MASS`,
   `draft · not run` amber, no checkbox) · seed_E0102_bank. Foot: `drafts can't be compared` +
   `Compare` disabled.
5. Right column (~76 %):
   a. Row of two cards (~320 px tall):
      - **Seed** (~40 % of right column): title `Seed (i)  type Signal span`; Seg `Library exemplar |
        Explore selection | Family medoid`; thumbnail box (~130 × 90) of the seed in mV (purple
        line) with caption `21 samples · 21 s`; beside it KeyValue lines: `E-0102 · exemplar of F-03`
        (bold), `sharkfin family · 112 members`, `M2_aug_concat_fs1 · CH4_A2`, `825–846 s · hash 3b91e0`,
        link `change seed ›`. Below: disabled pill `+ seed` + muted `MASS takes one seed (i)`. Divider.
        `When saved as a template (i)`; two radio cards: `◉ carry  this exemplar travels with the
        template` (selected, blue border) and `○ rebind  ask for an exemplar when applied`.
      - **Parameters** (~60 %): title `Parameters (i)`; right link `↺ Revert to recommended`. Grid of
        3 columns × 2 rows of fields: `algorithm (i)` Select `MASS · z-norm Euclidean`; `window m (i)`
        Select `21 samples · native`; `scale bank (i)` Select `none`; `exclusion zone (i)` Slider with
        value `m/2 = 10 s` and green caption `= trivial-match guard`; `match threshold (i)` Slider
        (orange) value `d ≤ 3.1`, green recommended tick, caption `recommended 2.8 · null hits = 1`;
        `on overlap (i)` Select `keep lowest distance`. Below, full card width: the **where-to-cut
        histogram** (~150 px).
   b. **Distance profile** card (~220 px): title `Distance profile (i)  one channel at a time`; right:
      legend `■ new match` (purple) `■ already judged` (green), Select `channel CH4_A2 ▾`, chip-select
      `view 192.0–194.0 h ▾` (blue), Checkbox `☑ show already judged`. Three tracks on one x axis:
      `signal` (~60 px), `distance` with left label `— d 3.1` (~60 px), `matches` (~12 px bar track).
      x ticks `192.0 h 192.5 193.0 193.5 194.0 h`.
   c. **Matches** card (~125 px): title `41 matches (i)  3 channels · sorted by distance`; right: pager
      `‹ 1–8 of 41 ›`, legend `■ seed` (purple) `— match` (black). Row of 8 match cards (~130 × 70):
      header `m-101  d 1.84`, overlay plot, foot `CH4_A2 · 192.6 h` (green dot before channel when
      already judged).
   d. **Apply bar** (~48 px card): `● draft · 1 unapplied change` (amber dot, bold) + muted
      `threshold 2.8 → 3.1 · preview counts update live`; right: `🔖 Save as template` (outline),
      `▷ Run seed search` (blue primary).

### Controls & interactions
- Toolbar chips / History — as discovery.runs. Cost chip grey `≈ 3 s local · 3 channels` (under 20 min;
  recomputed from channel count).
- Runs card — as discovery.runs; the draft row is selected; clicking another run navigates to
  `#/discovery/runs` with that run selected (`?run=<key>`). If the draft has unapplied changes, a
  Popover confirms `Leave the draft? 1 unapplied change is kept in this session` (in-memory, so
  "kept" is true).
- Seed Seg `Library exemplar | Explore selection | Family medoid` — switches seed source (param
  `source`); changing seed resets matches/histogram to that seed's fixture (or EmptyState) and counts
  as an unapplied change.
- `change seed ›` — Popover list of exemplars / medoids (`E-0102 · exemplar of F-03 · 21 s`,
  `m-1846 · medoid of F-03`, others from Library fixture) → selects.
- `+ seed` — DisabledReason `MASS takes one seed` (InfoTip on the (i): `A search taking several seeds —
  e.g. every medoid of a family — appears when an algorithm supports it.`).
- `carry` / `rebind` radio cards — in-memory; InfoTip on header explains both.
- `algorithm` Select — options `MASS · z-norm Euclidean` (only enabled); others (e.g. `matrix profile
  join`) disabled with reason `not built`. Fog.
- `window m` Select — **locked** to native length: render disabled with 🔒 and reason `window is the
  exemplar's native length (21 samples)` (spec: locked; frame draws a select — see conflicts).
- `scale bank` Select — `none` (only option enabled; `3 lengths` disabled reason `needs a scale-bank
  algorithm` — seed_E0102_bank uses 3 lengths, fog).
- `exclusion zone` Slider — range 0 … m (0–21 s), default m/2 = 10 s. Validation: below m/2 shows amber
  message `below m/2 lets trivial matches through`; caption green `= trivial-match guard` only at m/2.
- `match threshold` Slider — range 0–8 d, step 0.1, recommended marker 2.8. Drives: histogram threshold
  line & label `N kept · null gives M`, distance-track threshold line + `— d X`, matches count
  `41 matches` / pager total, apply bar diff text `threshold 2.8 → X`, cost unaffected. Number entry by
  clicking the value `d ≤ 3.1` (Number field, validation `0 < d ≤ 8`).
- `on overlap` Select — `keep lowest distance` / `keep first` / `keep all (overlapping)`; changes kept
  count slightly (fixture: all same) — unapplied change.
- `Revert to recommended` — resets every parameter to its recommended value; disabled with reason
  `already at recommended values` when nothing differs.
- Histogram threshold line — draggable (pointer + ←/→ when focused), syncs with slider.
- Distance profile `channel ▾` — channels in scope. `view ▾` — Popover with RangeSlider inside section
  (validation: width 0.1–24 h `view must be 0.1–24 h wide`). `show already judged` — hides green match
  bars when off.
- Hover on distance/signal tracks → crosshair + readout `192.62 h · d 1.84` (kit crosshair).
- Match card click → sets distance profile channel + view centred on the match (±1 h), marks the match
  bar selected. Pager `‹ ›` pages by 8; disabled at ends. Keyboard none shown.
- `Save as template` → `?modal=save-template` Modal: Text `name` (default `seed_F03_native_2`; required,
  `^[a-z0-9_]{3,40}$`, must not collide with the 14 canon templates → `a template called … exists`),
  read-only summary (seed, carry/rebind, parameters), buttons `Cancel` / `Save template` → in-memory
  template (Library templates store) + toast `Saved seed_F03_native_2 · Library › Templates` +
  `not wired yet: POST /templates`.
- `Run seed search` → apply changes, start sim; bar shows ProgressBar + `running · CH4_A2 (2 of 3)` +
  `Cancel`; on done: draft row becomes `seed` badge `41 found · 3 ch · done HH:MM`, toast
  `seed_F03_native_2 finished · 41 matches · open in Runs` with link `#/discovery/runs?run=
  seed_F03_native_2`. Rediscoveries (§4.7) are not visualised beyond `already judged`. If the estimate
  exceeded 20 min the button would become `Create SLURM script` (§7.5 rule, shared hook).
- `failed` (sim `failAt`) — not drawn; show error in the apply bar `MASS failed on CH7_B2 (simulated)` +
  `Retry`.

### Plots
- **Seed thumbnail**: Trace in **mV** (shared y with matches), 21 samples, purple; axis ticks minimal
  (`mV` label). Frame draws a 3-vertex polyline — replace with a real 21-sample sharkfin shape
  (`syntheticTrace({n:21, events:[{shape:'sharkfin', depth:0.35…}]})`).
- **Where to cut histogram**: Histogram; x = match distance d (0–8, ticks `0 2 4 6 8 d`), y = `count`;
  bars: kept (d ≤ threshold) purple `#AF52DE`, not kept light purple, **surrogate/null distribution**
  grey bars behind (same bins); `self` bin shaded pale red at d≈0–0.5 with label `self`; recommended
  marker green tick on x at 2.8; threshold vertical orange line with round handle and label
  `41 kept · null gives 6`. Legend `■ kept ■ not kept ■ surrogate — recommended`. Fixture: 40 bins of
  match counts + null counts.
- **Distance profile**: three stacked tracks, x = hours since start (view 192.0–194.0 h). `signal` Trace
  (mV, detrended, black); `distance` line purple (z-norm Euclidean distance, unitless) with horizontal
  orange threshold line; `matches` track: purple bars (new) and green bars (already judged) where
  distance < threshold (duration ~21 s each). No marks on the signal (§7.6).
- **Match cards** (SmallMultiples, 8 per page — P8 cap ~10): overlay of match (black) on seed (purple),
  shared mV y across all cards, header distance, foot channel · hour; green dot = already judged.
  Fixture `matches[]` 41 entries sorted by d; first 8 as frame.

### Fixtures
```ts
interface SeedDraft {
  key: 'seed_F03_native_2'; status: 'draft'; source: 'library' | 'explore' | 'medoid'
  seed: { id: 'E-0102'; role: 'exemplar'; family: 'F-03'; familyName: 'sharkfin'; members: 112;
          recording: 'M2_aug_fs1'; channel: 'CH4_A2'; startH: number; endH: number /* see conflicts */; samples: 21; lengthS: 21; hash: '3b91e0'; traceMv: number[] }
  bind: 'carry' | 'rebind'
  params: { algorithm: 'MASS'; windowSamples: 21; windowLocked: true; scaleBank: 'none'; exclusionS: 10;
            threshold: 3.1; recommended: 2.8; overlap: 'keep lowest distance' }
  applied: { threshold: 2.8 }                   // → "1 unapplied change · threshold 2.8 → 3.1"
  histogram: { binEdges: number[]; kept: number[]; null: number[] }   // kept(3.1)=41, null(3.1)=6, null(2.8)=1
  profile: { channel: 'CH4_A2'; view: [192.0, 194.0]; signalMv: number[]; distance: number[] }
  estimate: { seconds: 3; channels: 3; local: true }
}
interface SeedMatch { id: string /* m-101…m-141 */; d: number; channel: string; atH: number; judged: boolean; traceMv: number[] }
// page 1: m-101 1.84 CH4_A2 192.6 · m-102 1.92 CH7_B2 140.2 · m-103 2.05 CH4_A2 192.1 (judged) · m-104 2.21 CH2_A1 231.7 ·
//         m-105 2.34 CH4_A2 193.6 · m-106 2.47 CH7_B2 118.9 (judged) · m-107 2.61 CH2_A1 266.0 · m-108 2.80 CH4_A2 250.3
```
Shared: E-0102 / m-1846 / F-03 (canon families; Library, Review); session + runs (discovery.runs);
templates store (Library 7) for *Save as template*; Explore `SourceSpan` (live app state).

### Copy
`Seed search` `find more of a shape you already have` · `≈ 3 s local · 3 channels` · `seed_F03_native_2`
`draft` `E-0102 exemplar · MASS` `draft · not run` · `drafts can't be compared` · `Seed` `type Signal span`
· `Library exemplar` `Explore selection` `Family medoid` · `21 samples · 21 s` · `E-0102 · exemplar of
F-03` · `sharkfin family · 112 members` · `M2_aug_concat_fs1 · CH4_A2` · `hash 3b91e0` · `change seed`
· `+ seed` `MASS takes one seed` · `When saved as a template` · `carry` `this exemplar travels with the
template` · `rebind` `ask for an exemplar when applied` · `Parameters` `Revert to recommended` ·
`algorithm` `MASS · z-norm Euclidean` · `window m` `21 samples · native` · `scale bank` `none` ·
`exclusion zone` `m/2 = 10 s` `= trivial-match guard` · `match threshold` `d ≤ 3.1` `recommended 2.8 ·
null hits = 1` · `on overlap` `keep lowest distance` · `self` · `41 kept · null gives 6` · `kept`
`not kept` `surrogate` `recommended` · `count` · `Distance profile` `one channel at a time` · `new match`
`already judged` · `channel CH4_A2` · `view 192.0–194.0 h` · `show already judged` · `signal` `distance`
`matches` · `41 matches` `3 channels · sorted by distance` · `1–8 of 41` · `seed` `match` ·
`draft · 1 unapplied change` · `threshold 2.8 → 3.1 · preview counts update live` · `Save as template` ·
`Run seed search`.

### Frame ⟷ spec conflicts
1. **Seed provenance time `825–846 s`** — §0 says times display in hours since recording start
   (durations in s). Recommend `0.23 h · 21 s` style (`start h · duration s`), or keep samples. Spec §0
   wins; flag for fidelity critic.
2. **`window m` drawn as an open Select**; §7.6 says locked at native length. Recommend disabled
   Select with 🔒 + reason (looks the same, obeys spec).
3. **Seed thumbnail not in mV / 3-vertex polyline** — §3 / D5: never normalised, detrended mV.
   Recommend real mV trace with a minimal mV axis.
4. **`exclusion zone m/2 = 10 s`** with m = 21 samples at 1 Hz → 10.5 s. Recommend display
   `m/2 ≈ 10 s` or `10.5 s`. Minor.
5. **Runs list** omits `seed_F03_native` and `mp_drops_v3` (see discovery.runs conflict 2).
6. Distance-profile match bars in the frame (≈192.35, 192.95, 193.55 h) don't sit on the listed match
   times (192.1, 192.6, 193.6 h). Recommend matches track derived from the match fixture so they agree.

### Fog
- F9. Explore-selection seed: the live `SourceSpan` holds sample indices, not hours; and it may be on a
  recording outside the Discovery scope — behaviour unspecified.
- F10. Seed-run cost for larger scopes (when would a seed search exceed 20 min?) — no numbers.
- F11. `seed_E0102_bank` ("3 lengths") implies a scale bank exists while this page says `scale bank none`
  and MASS takes one seed. Unclear which algorithm powers the bank.
- F12. *Save as template* naming/versioning rules and whether a draft must be run before saving are not
  specified.
- F13. What the null distribution in the histogram is computed on (circular shift of the signal, per
  channel pooled) is not stated — fixture only.

## discovery.compare

### Route & states
- **default** (frame 3, scrolling ~1060 px) — `#/discovery/compare?a=drop_motifs9&b=seed_F03_native&only=a&i=7`.
  Reached from runs-list *Compare* once two runs are picked. Missing/invalid `a`/`b` → EmptyState
  `Pick two runs in the runs list to compare` + button `‹ all runs`. `a === b` → same EmptyState with
  `pick two different runs`.
- **filter:all / filter:only-b** (no frame) — stepper Seg; `?only=all|a|b`; `i` resets to 1.
- **swapped** (no frame) — *Swap A / B* swaps params; all A/B colours, pills and counts swap
  (only A ↔ only B).
- **roles-popover** (no frame) — info icon next to `3 of 5 roles differ` / `?popover=roles`.
- **hover crosshair** (in frame) — transient, not a state.
- **human as a side** (no frame; §7.7 allows) — `?b=human`: B chain column shows `human annotations ·
  reference` with every role empty except Detect `human verdicts`; B precision tile `—`.

### Regions (1440 × ~1060)
1. Header: `Discovery | Compare  A drop_motifs9 · B seed_F03_native` (subtitle built from picks).
2. Toolbar: `‹ all runs` link; `ch_screen_sep14 ✎ saved`; scope chip `M2_aug_concat_fs1 · 3 channels ·
   112–286 h ▾`; right: `● null circular shift 200× (i)`; `🗄 cached` (grey text chip); `⇆ Swap A / B`
   button.
3. Scope card — shared component (as runs).
4. Left: Runs card — as runs page but `4 in this session`; drop_motifs9 pick box **A** (blue),
   seed_F03_native **B** (purple); foot `2 picked` + `⇆ Comparing` button (blue, active/pressed state).
5. Right column cards:
   a. **What differs** (~150 px): title `What differs (i)  stages aligned by role`; right amber badge
      `3 of 5 roles differ` + (i). Grid: row header column (~110 px: `A drop_motifs9`, `B seed_F03_nat.`
      with A/B squares) × 5 role columns with headers `Source · Preprocess · Score / estimate · Encode
      · Detect`. Each cell a stage card (~150 × 34): glyph + name + one-line param.
      A: `Source CH4_A2 · CH2_A1 · CH7_B2` (grey) · `Baseline removal window 3 h` (grey) · `Noise floor
      cut 8σ` (amber) · `Symbolic enc. SAX · 6 symbols` (amber) · `Drop detection min slope` (amber).
      B: `Source CH4_A2 · CH2_A1 · CH7_B2` (grey) · `Baseline removal window 3 h` (grey) · `Seeded search
      E-0102 · MASS` (amber) · `— no stage` (empty dashed card) · `Threshold d ≤ 3.1` (amber).
   b. **Where A and B fire** (~230 px): title `Where A and B fire (i)`; right legend `■ both` (grey)
      `■ only A` (blue) `■ only B` (purple); Select `channel CH4_A2 ▾`; chip-select `view 112–286 h ▾`.
      Body: `signal CH4_A2` label + clean signal trace (~90 px); three tick tracks `A`, `B`, `agreement`
      (~12 px each); x axis `112 h 141 170 199 228 257 286 h`. Hover crosshair (vertical line through
      signal and tracks) with dark tooltip `234.7 h ● both fire`; faint blue band behind the signal at
      the currently stepped disagreement.
   c. **Set overlap** (~125 px): title `Set overlap (i)  matched at IoU ≥ 0.5`. Left (~60 %): rows
      `all channels` (bold) / `CH2_A1` / `CH4_A2` / `CH7_B2`, each a proportional stacked bar with
      in-bar counts: blue only-A, grey both, purple only-B (`106 54 9`, `30 11 3`, `44 28 3`,
      `32 15 3`). Right: three StatTiles `A precision 24 % 50 reviewed` (blue value), `B precision 18 %
      40 reviewed` (purple value), `× null 6.2 · 7.0 A · B`.
   d. **Step through the disagreements** (~210 px): title `Step through the disagreements (i)`; right:
      Seg `all 115 | only A 106 | only B 9` (only A selected), pager `‹ 7 / 106 ›`, `☰ Compare every
      stage` (blue primary). Body: left text column (~150 px): `192.4 h · CH4_A2 · 40 s` (bold),
      `only A fired` (blue), gap, `B nearest d 3.6` (purple), `threshold 3.1 · near miss` (amber).
      Plot (rest): window signal (black) with pale blue band on the disagreement; below, track `A`
      with blue span bar labelled `d-0412 · score 0.88`; track `B` = B's distance profile (purple) with
      orange threshold line. x axis `192.39 h  192.40  192.41 h`.

### Controls & interactions
- `‹ all runs` → `#/discovery/runs` (keeps picks in session store).
- Toolbar session/scope/null chips — as runs. `cached` — static Chip, InfoTip `both runs' results are
  cached; nothing re-runs to compare`.
- `Swap A / B` → swaps `a`/`b` query params (history replace).
- Runs card — pick boxes editable here: unpicking one leaves `1 picked` and the right column shows
  EmptyState `pick a second run`; picking another replaces B and updates the route. `Comparing` button
  is a pressed toggle; clicking it returns to `#/discovery/runs`.
- `3 of 5 roles differ (i)` — Popover: `More than one role differs, so a difference in output cannot be
  attributed to any single stage.` (with exactly one differing role the badge is green `1 of 5 roles
  differs · attributable`).
- Stage cards in What differs — click → Popover with the stage's signature and locked params +
  `Open in Analyse ↗` (`#/analyse/chain`, toast `not wired yet: open <template> in Analyse`). Empty
  slot card — tooltip `seed_F03_nat. has no Encode stage`.
- Where A and B fire `channel ▾` (channels in scope), `view ▾` (Popover RangeSlider within section,
  validation as seed view but min 0.5 h). Hover → crosshair + readout `<h> · both fire | only A |
  only B | neither`. Click on a tick in the agreement track → jumps the stepper to that disagreement
  (sets `only` + `i`) if it is one; on a `both` tick → toast-free no-op with tooltip `both fire here`.
- Set overlap bars — click a segment → sets stepper filter (`only A` / `only B`; `both` has no stepper
  → tooltip `both runs agree here · nothing to step`) and channel.
- Stepper Seg `all 115 | only A 106 | only B 9`, pager `‹ n / N ›` (disabled at ends), keyboard `←/→`
  optional.
- `Compare every stage` → `#/discovery/compare/stages?a=…&b=…&only=…&i=…`.

### Plots
- **Where A and B fire**: Trace (mV, **clean — no marks over it**; add a compact mV y-axis) over the view
  (x hours since start, 112–286 h). Tracks: `A` blue ticks, `B` purple ticks, `agreement` grey (both) /
  blue (only A) / purple (only B). Crosshair + dark tooltip. Faint band = current disagreement.
  Fixture: `events[channel] = { atH, a: boolean, b: boolean }[]` for CH4_A2 = 44 only A + 28 both +
  3 only B (matches Set overlap).
- **Set overlap**: stacked proportional Bars (x = count, per row own proportion; all rows share scale
  with `all channels` longest). Fixture per channel: CH2_A1 30/11/3, CH4_A2 44/28/3, CH7_B2 32/15/3.
- **Disagreement window**: Trace mV, window 40 s centred on 192.40 h; A span track (bar + label); B
  distance profile line + threshold line (d 3.1), min marker at nearest d 3.6 (not drawn in frame 3
  but drawn in 3b). For a template-B case the B track would show B's own score vs its threshold.

### Fixtures
```ts
interface CompareRole { role: 'Source' | 'Preprocess' | 'Score / estimate' | 'Encode' | 'Detect' }
interface RoleCell { name: string; param: string; glyph: GlyphKey; stageIndex?: '01'|'02'|'03'|'04'; signature: string } | null
interface RunChainByRole { run: string; cells: Record<CompareRole['role'], RoleCell> }
// A drop_motifs9: Source(CH4_A2 · CH2_A1 · CH7_B2) · 01 Baseline removal(window 3 h) · 02 Noise floor(cut 8σ) · 03 Symbolic enc.(SAX · 6 symbols) · 04 Drop detection(min slope)
// B seed_F03_native: Source · 01 Baseline removal(window 3 h) · 02 Seeded search(E-0102 · MASS) · null · 03 Threshold(d ≤ 3.1)
interface OverlapRow { channel: 'all' | string; onlyA: number; both: number; onlyB: number }
interface Disagreement { index: number; kind: 'only A' | 'only B'; channel: string; atH: number; windowS: 40;
  a?: { detection: 'd-0412'; score: 0.88 }; b?: { nearestD: 3.6; threshold: 3.1; nearMiss: boolean }; signalMv: number[]; bDistance: number[] }
const COMPARE_TILES = { aPrecision: 0.24, aReviewed: 50, bPrecision: 0.18, bReviewed: 40, xNull: [6.2, 7.0] }
```
Totals must reconcile (they do in the frame): A found 160 = 106 + 54; B found 63 = 54 + 9;
disagreements 115 = 106 + 9. Runs, templates' stages, detections `d-0412` shared with discovery.runs
and discovery.stages. Glyph keys shared with the chain 6b registry.

### Copy
`Compare` `A drop_motifs9 · B seed_F03_native` · `all runs` · `cached` · `Swap A / B` · `2 picked` ·
`Comparing` · `What differs` `stages aligned by role` · `3 of 5 roles differ` · `Source` `Preprocess`
`Score / estimate` `Encode` `Detect` · `no stage` · `Where A and B fire` · `both` `only A` `only B` ·
`channel CH4_A2` · `view 112–286 h` · `signal` `A` `B` `agreement` · `234.7 h · both fire` ·
`Set overlap` `matched at IoU ≥ 0.5` · `all channels` · `A precision` `50 reviewed` · `B precision`
`40 reviewed` · `× null` `6.2 · 7.0` `A · B` · `Step through the disagreements` · `all 115` `only A 106`
`only B 9` · `7 / 106` · `Compare every stage` · `192.4 h · CH4_A2 · 40 s` · `only A fired` ·
`B nearest d 3.6` · `threshold 3.1 · near miss` · `d-0412 · score 0.88`.

### Frame ⟷ spec conflicts
1. **Role column order**: frame `Source · Preprocess · Score / estimate · Encode · Detect`; §7.7 text
   says `Source · Preprocess · Encode · Score / estimate · Detect`. The frame follows B24 / §0 chain
   order (Noise floor 02 before Encoding 03). **Recommend the frame** (§0 canon wins) and flag §7.7
   as stale text.
2. **Header chain for A** in the stage card uses `Symbolic enc.` truncation; 3b uses `Symbolic encoding`.
   Cosmetic.
3. Frame 3's runs list says `4 in this session` (see discovery.runs conflict 2).
4. The faint band on the where-A-and-B-fire signal sits near ~186 h while the stepped disagreement is at
   192.4 h. Recommend the band follow the stepper (spec: "faint band on the disagreement currently
   selected").

### Fog
- F14. IoU ≥ 0.5 matching rule's source (Settings › Analysis defaults "matching rule") — value only.
- F15. Comparing a running run (sharkfin_v2 64 %) — partial results behaviour not drawn.
- F16. How role assignment is derived for arbitrary chains (block contract §6.8 declares a role?) —
  assume each template stage carries `role` in the fixture.

## discovery.stages

### Route & states
- **default** (frame 3b, 1440 × ~1000) — `#/discovery/compare/stages?a=drop_motifs9&b=seed_F03_native&only=a&i=7`.
  Reached from discovery.compare *Compare every stage*. Same EmptyState rules as compare for bad params.
- **stepping** — `‹ ›` change `i` within the filter inherited from compare (`only`); every card and
  the table re-render for the new window; the first-differing chip recomputes.
- **re-running** (no frame) — on step, a short `useSim('discovery.stages.rerun')` (~1 s, matching the
  toolbar `≈ 1 s re-run on 40 s`) shows cards veiled with a small spinner, then `done`.
- **swapped** — *Swap A / B*.
- No scope card and no runs list on this page (full-width layout).

### Regions
1. Header: `Discovery | Compare  every stage · one window`.
2. Toolbar: `‹ compare` link; `ch_screen_sep14 ✎ saved`; scope chip; right: `● null circular shift
   200× (i)`; `⌛ ≈ 1 s re-run on 40 s` (grey); `⇆ Swap A / B`.
3. **Stepper bar card** (full width, ~52 px): `‹` `7 / 106` `›` · `192.4 h · CH4_A2 · 40 s` (bold) ·
   `only A fired` (blue); right: amber chip `first stage whose output differs · Score / estimate` + (i).
4. **Two columns** (each ~50 %, ~650 px): column headers `A drop_motifs9  template · v9` + `↗ Open in
   Analyse` | `B seed_F03_native  seed · E-0102` + `↗ Open in Analyse`. Five stage cards per column,
   rows aligned by role (row heights shared between columns):
   - **Source** (~88 px): label `Source` muted, title `Signal`, signature `— → Signal`, badge
     `identical` (green); signal thumbnail; caption `the same 40 s in both runs`. (Both columns.)
   - **Preprocess** (~98 px): `Preprocess 01` + glyph + `Baseline removal  Signal → Signal`, badge
     `identical`; thumbnail = output curve (blue) with input ghosted (grey); caption `window 3 h · slow
     rise removed`. (Both.)
   - **Score / estimate** (~140 px, amber border): A `Score / estimate 02` glyph `Noise floor  Signal →
     Signal + estimate`, badge `differs` (amber); thumbnail = segment bars (light blue / peach) with
     ±cut lines labelled `±0.077` and two dark-red segments beyond; caption `σ 0.0096 · cut ±0.077 ·
     2 segments qualify`. B `Score / estimate 02` glyph `Seeded search  Signal + exemplar → Scores`,
     badge `differs`; thumbnail = distance profile (purple) with orange threshold line `d 3.1`, minimum
     marker circle labelled `3.6`; caption `nearest d 3.6 at 192.402 h · threshold 3.1`.
   - **Encode** (~93 px): A (amber border) `Encode 03` glyph `Symbolic encoding  Signal → Encoding`, badge
     `A only` (amber); thumbnail = SAX symbol strip (~36 cells coloured blue→amber, a run of 5 dark-red
     cells at the fall); caption `SAX · 6 symbols · one long low run at the fall`. B (grey, dashed)
     `Encode  no Encode stage`, badge `absent` (grey); inner dashed box `— nothing to compare in this
     role`; caption `Seeded search reads the preprocessed signal directly`.
   - **Detect** (~110 px, amber border): A `Detect 04` glyph `Drop detection  Signal → SpanSet`, badge
     `differs`; thumbnail = signal with pale-blue band + blue span bar under it; caption `1 span · depth
     0.38 mV · score 0.88`. B `Detect 03` glyph `Threshold to spans  Scores → SpanSet`, badge
     `differs`; thumbnail = signal with an empty grey span track; caption `0 spans · d never reaches 3.1
     in this window`.
5. **What each stage decided here** card (full width, ~195 px): title + (i) + muted `same window, both
   runs`. Table columns `role` | `A · drop_motifs9` (blue header) | `B · seed_F03_native` (purple
   header). Rows (differing rows tinted pale amber): `Preprocess` · `slow rise removed (identical)` ·
   `slow rise removed (identical)`; `Score / estimate` · `2 segments beyond ±0.077` · `nearest d 3.6 ·
   threshold 3.1`; `Encode` · `one long low run at the fall` · `— no stage`; `Detect` · `1 span · score
   0.88` · `0 spans`.

### Controls & interactions
- `‹ compare` → `#/discovery/compare?…` (same a/b/only/i).
- Stepper `‹ ›` — step `i` (disabled at ends); keyboard `←/→` optional.
- First-differing chip (i) — Popover: `The first stage whose output differs here. This is not a causal
  claim: a later stage can differ for its own reasons.` (§7.8).
- `Swap A / B` — swaps columns and params.
- `Open in Analyse ↗` (per column) → `#/analyse/chain` + toast `not wired yet: open drop_motifs9 on
  CH4_A2 192.39–192.41 h in Analyse` (spec: opens that chain on this window).
- Stage card click → Popover with the stage's locked params (read-only), reusing the compare-page
  stage popover.
- Absent card — no controls.
- Table rows — hover highlights the corresponding row of cards (optional).

### Plots (all 40 s window, x = 192.39–192.41 h; axes omitted in thumbnails, shared mV y within a role)
- Source: Trace mV. Preprocess: Trace output (blue) + input ghost (grey) — contract `Signal → Signal`.
- Noise floor: Bars per segment (value = segment deviation in mV), horizontal lines at ±cut, bars beyond
  cut dark red — contract `Signal → Signal + estimate` (curve with estimate band; frame uses bars).
- Symbolic encoding: BandStrip / symbol strip, 6-symbol ordinal colour ramp (blue low … amber high,
  dark red for the lowest symbol run).
- Seeded search: line (distance, unitless) + threshold line + min marker.
- Drop detection: Trace mV + span band + span bar. Threshold to spans: Trace mV + empty span track.
- Fixture per disagreement `i`: `stages[role][side] = { thumb: {...}, caption, decided }`.

### Fixtures
```ts
interface StageWindowResult {
  role: 'Source' | 'Preprocess' | 'Score / estimate' | 'Encode' | 'Detect'
  side: 'A' | 'B'
  stage: { index?: '01'|'02'|'03'|'04'; name: string; signature: string; glyph: GlyphKey } | null   // null = absent
  badge: 'identical' | 'differs' | 'A only' | 'B only' | 'absent'
  thumb: { kind: 'trace' | 'transform' | 'segments' | 'symbols' | 'distance' | 'spans'; data: number[]; extras?: Record<string, number> }
  caption: string            // 'σ 0.0096 · cut ±0.077 · 2 segments qualify'
  decided: string            // table cell: '2 segments beyond ±0.077'
  absentNote?: string        // 'Seeded search reads the preprocessed signal directly'
}
interface StagesWindow { i: 7; of: 106; atH: 192.4; channel: 'CH4_A2'; windowS: 40; kind: 'only A fired'; firstDiffering: 'Score / estimate'; rows: StageWindowResult[] }
```
Provide fixtures for at least 3 values of `i` (e.g. 6, 7, 8) so stepping visibly changes something;
others fall back to a generated variant. Shares run/template/glyph data with discovery.compare.

### Copy
`Compare` `every stage · one window` · `compare` · `≈ 1 s re-run on 40 s` · `Swap A / B` · `7 / 106` ·
`192.4 h · CH4_A2 · 40 s` · `only A fired` · `first stage whose output differs · Score / estimate` ·
`drop_motifs9` `template · v9` · `seed_F03_native` `seed · E-0102` · `Open in Analyse` · `Source`
`Signal` `— → Signal` `identical` `the same 40 s in both runs` · `Preprocess 01` `Baseline removal`
`Signal → Signal` `window 3 h · slow rise removed` · `Score / estimate 02` `Noise floor`
`Signal → Signal + estimate` `differs` `σ 0.0096 · cut ±0.077 · 2 segments qualify` · `Seeded search`
`Signal + exemplar → Scores` `nearest d 3.6 at 192.402 h · threshold 3.1` · `Encode 03`
`Symbolic encoding` `Signal → Encoding` `A only` `SAX · 6 symbols · one long low run at the fall` ·
`no Encode stage` `absent` `nothing to compare in this role` `Seeded search reads the preprocessed
signal directly` · `Detect 04` `Drop detection` `1 span · depth 0.38 mV · score 0.88` · `Detect 03`
`Threshold to spans` `Scores → SpanSet` `0 spans · d never reaches 3.1 in this window` ·
`What each stage decided here` `same window, both runs` · `role`.

### Frame ⟷ spec conflicts
1. **Drop detection signature `Signal → SpanSet`** in 3b; §0 canon / B24 say `Encoding → SpanSet`.
   **Recommend canon** (`Encoding → SpanSet`).
2. **Text-layer vs image order**: the PDF text lists Encode before Score / estimate; the image shows
   Score / estimate (02) before Encode (03). The image follows B24 — **build the image order**.
3. **Threshold to spans thumbnail**: frame draws the signal with an empty span track; §6.8 contract row
   `Scores → SpanSet` says "interval overlay on the scores". Recommend the contract (draw B's scores
   with the threshold line and an empty interval overlay) — or accept the frame; low risk.
4. **Noise-floor units** (`σ 0.0096`, `±0.077`) are unitless in the frame; §3 wants mV. Recommend
   `σ 0.0096 mV · cut ±0.077 mV`.
5. The stage number of B's `Threshold to spans` is `03` while A's detection is `04` — correct for B's
   own chain (no Encode stage). Not a conflict; keep.

### Fog
- F17. `Signal + exemplar → Scores` (Seeded search as a chain stage) has no row in the §6.8 contract
  table, and B25 says seeded search is "a Discovery mode · not a chain block". The compare pages treat
  it as a stage. Needs a decision before a real renderer; the shell can fixture it.
- F18. "≈ 1 s re-run on 40 s" implies stages re-run per window on step; whether that is local compute or
  cached intermediates is not specified.

## Models — shared chrome (all four pages)
- Header: `Models | <Page>  <subtitle>`.
- Toolbar row (~56 px, no card) — varies per page (below).
- **Tab bar** (~40 px): Tabs `🚀 Launch` · `📊 Results` · `⇆ Compare` · `📚 Registry` (selected tab is a
  white raised pill; others plain). Routes `#/models/launch`, `#/models/results`, `#/models/compare`,
  `#/models/registry`. `#/models` redirects to `#/models/launch`. Tab switch keeps the last query of
  each tab in the session store.
- Right of the tab bar: link with list icon — `2 training jobs · open in Jobs ↗` (Launch, Registry) →
  `#/jobs?kind=training`; `j-0212 · finished · open in Jobs ↗` (Results, Compare) → `#/jobs?job=j-0212`
  (Jobs inventory owns the exact route/params; §7b "filtered to training jobs, or to the job a result
  came from").
- Arm colours in Models: **A = green** (manual labels are human-origin, §3), **B = purple**, **RF = grey**.
  (Discovery's A is blue — the ArmBadge component needs a per-workspace palette.)

## models.launch

### Route & states
- **signal-template** (frame 1, ~1000 px, slight scroll) — `#/models/launch` (default template
  `cnn_windows_v3`). Session `train_cnn_M2aug_sep14` unsaved; Sources = Channels (3 of 4 rows checked);
  Save window set on (`ws_M2aug_3ch_600s v2`); arms A, B, RF; estimate 5.6 h local > 2 h → *Train
  locally* disabled, *Create SLURM script* primary; before-launch 4 pass + 2 warn.
- **windowset-template** (frame 1b) — pick `cnn_windowset_v1 · v1` in the template Select, or
  `?template=cnn_windowset_v1`. Session name becomes `train_cnnws_M2aug_sep14`; Sources Seg switches to
  *Saved window set* (Channels disabled); radio table with `ws_M2aug_3ch_600s · v1` selected
  (`?windowset=ws_M2aug_3ch_600s@1`); Evaluation selects disabled with caption `split comes with the
  window set · locked here, change it by saving a new version`; stage references renumber (`01 Window
  matrix`, `02 Cluster`); SLURM script body changes.
- **local-allowed** (no frame; §7b.1 rule) — local estimate ≤ 2 h, e.g. only one channel checked
  (5.6 h × 1/3 ≈ 1.9 h) or `?est=local`: estimate chip grey `≈ 1.9 h local`, *Train locally* blue
  primary enabled, *Create SLURM script* becomes secondary outline; amber banner hidden; SLURM script
  card collapsed behind a `Show SLURM script` disclosure.
- **training-local** (no frame) — *Train locally* → `useSim('models.train.<session>')` with steps
  `arm A`, `arm B`, `RF baseline`, `RF null 200×`, `model null 5×` (queued → running → done); toolbar
  shows ProgressBar + `Cancel`; done → toast `Training finished (demo) · open Results` → link
  `#/models/results`. `?state=running` / `?state=failed` via `forceSim`.
- **submitted** (no frame) — *Create SLURM script* → in-memory job added; right-column "After
  submitting" rows get a green check; toast. `?state=submitted`.
- **m4-refused** popover (no frame) — click the M4 toggle; `?popover=m4`.
- **add-arm** popover (no frame) — *Add arm*; `?popover=add-arm`.
- **invalid** (no frame) — any failing before-launch check (e.g. gap < window, no sources, zero arms)
  turns that check red ✗ and disables both launch buttons with the failing check as the reason.

### Regions (1440 × ~1000)
1. Header: `Models | Launch  train a template across channels · paired label arms`.
2. Toolbar: left `🧠 train_cnn_M2aug_sep14 ✎ unsaved` chip. Right: `● null label shuffle · RF 200× +
   model 5× (i)`; amber chip `⌛ ≈ 5.6 h local above 2 h limit`; `▷ Train locally` (disabled outline);
   `📄 Create SLURM script` (purple primary).
3. Tab bar + `2 training jobs · open in Jobs ↗`.
4. Two columns: **left ~65 %** (≈ 860 px) stacked SectionCards 1–5; **right ~34 %** (≈ 455 px) one tall
   card (Before launch → Estimate → SLURM script → After submitting), same top as card 1, bottom
   aligned with card 5.
   - **1 Training template (i)  from Analyse** (~130 px): right link `↗ Open in Analyse`. Row: Select
     `⧉ cnn_windows_v3 · v3 ▾` (blue fill, ~260 px); chips `source Signal` (blue), `multi-class · 4
     classes` (purple); muted `EfficientNet-B0 · 224 px GASF+GADF+RP`. Below: GlyphStrip with labels
     `Source › 01 Sliding windows › 02 Window matrix › 03 Cluster › 04 Image encode › 05 CNN classifier`.
   - **2 Sources (i)  the template starts from Signal, so each channel is a source** (~180 px): right Seg
     `Channels | Saved window set` (Channels selected; other greyed). Table: checkbox · `recording ·
     channel` · `hours` · `windows` · `human verdicts` · `classes seen` · flag. Rows:
     ☑ `M2_aug_concat_fs1 · CH2_A1  721 h  5,220  640  4 / 4`;
     ☑ `M2_aug_concat_fs1 · CH4_A2  721 h  5,220  1,080  4 / 4`;
     ☑ `M2_aug_concat_fs1 · CH7_B2  721 h  5,220  420  3 / 4` + amber chip `no plateau verdicts`;
     ☐ greyed `L_LM_Jul26_J · CH1  92 h  —  0  —`.
     Foot row: Toggle (on) `Save window set` + name field `💾 ws_M2aug_3ch_600s v2` + muted `at 01 Sliding
     windows · 3 channels · 15,660 windows · split included`.
   - **3 Label arms (i)  paired — same windows, split and test block** (~170 px): right `+ Add arm`.
     Rows (grey fill, ~28 px): `[A] manual labels  Review verdicts · 4 classes … 2,140 windows labelled ×`;
     `[B] cluster labels  03 Cluster · k = 4 · criterion max silhouette … 15,660 windows labelled ×`;
     `[RF] random-forest baseline  02 Window matrix features · trained once per arm … always on 🔒`.
     Foot: `train every arm on` + Select (blue) `windows labelled in every arm · 2,140 ▾` + (i) `so the
     comparison is paired`.
   - **4 Evaluation (i)  test block set aside before training · blocked by time** (~220 px): Selects
     `test 20 % ▾`, `validation 10 % ▾`, `gap ≥ 600 s (1 window) ▾`; right Toggle (off, locked)
     `M4_aug locked · Settings › Datasets` + muted `held out`. Split strip: rows `CH2_A1`, `CH4_A2`,
     `CH7_B2`, each 10 blocks (train blue / validation amber / test green, 1 px gaps). Legend `■ train
     ■ validation ■ test — scored once, after training`. Count table `windows per class` × `spike-train
     plateau burst slow-drift`: `train 412 268 190 620`; `val 61 38 27 92`; `test 118 74 31 209` (31
     amber); right amber chip `burst: 31 test < 50`.
   - **5 Options (i)** (~80 px): Toggle (off) `repeat with different seeds` + disabled Number `3 seeds`;
     Select `epochs 30 ▾`; Select `batch 64 ▾`; Select `null RF 200× · model 5× ▾`.
   - Right card: **Before launch (i)** — checklist: ✓ `test block never seen in training, validation or
     early stopping`; ✓ `gap between blocks ≥ window length`; ✓ `label-derived features off in 02 Window
     matrix`; ✓ `every arm trains on the same 2,140 windows`; ⚠ `burst class: 31 test windows (≥ 50
     recommended)`; ⚠ `CH7 has no plateau verdicts`. Divider. **Estimate** — 3 StatTiles `local ≈ 5.6 h`
     (amber) `3 arms + 5 model nulls`; `disk 3.9 GB` `images + window set`; `HPC ≈ 1.4 h` `1 GPU node`.
     Amber banner `⌛ over the 2 h local limit · Train locally is off (i)`. **SLURM script** — dark
     CodeBlock (~230 px) with the script (see Copy), buttons `⧉ Copy`, `⬇ Save .sh`. **After
     submitting** — two grey rows: `👁‍🗨 Creating the script adds the job to Jobs  mark it submitted /
     running / finished there`; `📥 Results return through Jobs › Manifest inbox  checked against this
     launch, then imported`.

**1b differences** (frame 1b): session `train_cnnws_M2aug_sep14`; template Select `cnn_windowset_v1 · v1`,
chip `source WindowSet`; GlyphStrip `Source › 01 Window matrix › 02 Cluster › 03 Image encode › 04 CNN
classifier` (no sliding windows — P15 absent, not skipped); Sources caption `the template starts from
WindowSet, so the source is one saved set`; Seg `Saved window set` selected, Channels greyed; radio
table columns `window set · channels · windows · split · verdicts now (at save)` + badge:
◉ `ws_M2aug_3ch_600s · v1  3 channels  15,660 · blocked  2,140 (1,980)` `train-safe` (green);
○ `ws_M3jul_8ch_300s · v2  8 channels  22,400 · blocked  610 (610)` `train-safe`;
○ disabled `ws_verif_cnn_cluster_v1 · v1  CH4_A2  40 · none  33 (0)` `not train-safe` (red);
○ disabled `ws_humanlabel_frame0b · v1  all channels  4,812 · no split  4,812 (4,812)` `no split · B7` (amber);
foot caption `arrives with its split and spacing check · saved from 01 Sliding windows of cnn_windows_v3 ·
recipe a7f39c2e`; no Save-window-set row. Arms refer to `02 Cluster` and `01 Window matrix`. Evaluation
selects disabled + caption `split comes with the window set · locked here, change it by saving a new
version`. Check 2 reads `gap between blocks ≥ window length · checked at save`; check 3 `… off in 01 Window
matrix`. Script: `--template cnn_windowset_v1@1 --windowset ws_M2aug_3ch_600s@1 … --split from-windowset
… --verdicts-as-of launch`.

### Controls & interactions
Toolbar
- Session name chip — inline rename; rule `^[A-Za-z0-9_]{3,60}$` → `letters, digits and _ only`; `unsaved`
  stays until *Create SLURM script* / *Train locally* (launch saves it) — or a `Save` on Enter writes in
  memory.
- Null chip (i) — InfoTip: `Label shuffle: 200× on the RF baseline plus 5× on the full model — every
  full-model shuffle is a full retrain.` + `Settings › Nulls` link.
- Estimate chip — Popover breakdown: `arm A ≈ 1.6 h · arm B ≈ 1.6 h · RF ≈ 0.1 h · model nulls 5× ≈ 2.3 h ·
  local limit 2 h (Settings › Compute & HPC)`.
- `Train locally` — DisabledReason `over the 2 h local limit` (tooltip) when estimate > 2 h; else primary
  → simulated training (see states).
- `Create SLURM script` — primary when > 2 h: in-memory write to the jobs store (new cluster job id
  `j-0218`, title `<session> paired arms`, status `script created`), CodeBlock scrolls into view and
  flashes, toast `j-0218 added to Jobs · mark it submitted there` + link, plus `not wired yet: POST
  /models/launch`. Also writes the window set `ws_M2aug_3ch_600s v2` (if toggle on) to the shared
  window-sets store with `train-safe` pending. Disabled when any check fails (reason = failing check).

Card 1
- Template Select — options = Analyse templates with terminal type `Model`: `cnn_windows_v3 · v3`
  (source Signal), `cnn_windowset_v1 · v1` (source WindowSet). Switching changes sources mode, glyph
  strip, stage numbering in cards 2–4, SLURM script, session default name. Detection templates are not
  listed (P16).
- `Open in Analyse ↗` → `#/analyse/training` (Analyse inventory owns the route) + toast `not wired yet:
  open cnn_windows_v3 in Analyse`.
- Glyph strip items — tooltip with stage signature (e.g. `Signal → WindowSet`).

Card 2
- Seg `Channels | Saved window set` — the option that does not fit the template is disabled with
  DisabledReason `the template starts from Signal` / `the template starts from WindowSet` (§7b.1).
- Channel row checkbox — toggles source; recomputes: Save-window-set caption (`N channels · 5,220 × N
  windows`), arm A labelled count (sum of human verdicts), `train every arm on … · N`, split strip rows,
  class-count table (scaled fixture), checks (CH7 warning disappears when CH7 unchecked), estimate
  (5.6 h × N/3), SLURM `--sources`. Zero checked → check ✗ `pick at least one source`.
- `L_LM_Jul26_J · CH1` row — disabled with DisabledReason (not drawn in frame; recommended copy):
  `10 Hz (inferred) · the template's sliding windows expect 1 Hz`.
- Flag chip `no plateau verdicts` — static.
- `Save window set` Toggle — on: name field enabled; off: name disabled, check line removed, script drops
  `--save-windowset`. Name Text validation: required; `^ws_[A-Za-z0-9_]+$` → `window-set names start
  with ws_`; version auto = next free (`v2` because `v1` exists in the shared store) shown as a suffix
  chip; name equal to an existing set of different content → message `ws_M2aug_3ch_600s exists · this
  saves v2`.
- 1b radio rows — select window set; disabled rows carry reason: `not train-safe · spacing check
  failed` / `no split (B7) · a split filter is not built yet`. Selecting `ws_M3jul_8ch_300s · v2`
  swaps split strip (8 channels), gap `≥ 300 s (1 window)`, counts (fixture), arms counts `610`,
  estimate. Caption line reflects the selected set's provenance.

Card 3
- Arm row `×` — removes arm (A or B). RF row not removable (🔒 `always on`). Removing leaves one label
  arm → check `every arm trains on the same N windows` becomes n/a (grey) and a muted note `a single arm
  can't be compared in Compare`. Removing both → ✗ `add at least one label arm`.
- `+ Add arm` — Popover listing label sources: `manual labels · Review verdicts` and `cluster labels ·
  03 Cluster` (disabled with reason `already an arm` when present); a third option `labels from a window
  set` disabled with reason `not built`. (Fog: no other arm types specified.)
- `train every arm on` Select — `windows labelled in every arm · 2,140` (default) | `every window each
  arm labels`; choosing the second flips check 4 to ⚠ `arms are not paired · Compare can't attribute
  the difference`.

Card 4
- `test` Select (10 / 15 / 20 / 25 %), `validation` Select (5 / 10 / 15 %). Validation `test + validation
  ≤ 50 %` → message `test and validation leave too little to train`. Changing recomputes the split
  strip block colours and the count table (proportional fixture) and the burst warning.
- `gap` Select — `≥ 600 s (1 window)` (default), `≥ 1,200 s (2 windows)`, `0 s` → `0 s` shows field error
  `gap must be ≥ window length (600 s)` and check 2 ✗ (P12 leakage guard).
- `M4_aug locked` Toggle — disabled/off; click opens Popover `M4_aug is held out and locked (D6). It is
  refused in every workspace, Models included. Unlocking needs the recording name typed and is logged.`
  + link `Settings › Datasets` → `#/settings/datasets`.
- 1b: selects disabled with DisabledReason `split comes with the window set`.

Card 5
- `repeat with different seeds` Toggle → enables Number `seeds` (validation integer 2–10 → `2–10
  seeds`); estimate multiplies (arms × seeds) and the null line text; script gains `--repeats N`.
- `epochs` Select (10 / 20 / 30 / 50), `batch` Select (32 / 64 / 128), `null` Select (`RF 200× · model 5×`,
  `RF 200× · model 0×` → check ⚠ `no full-model null`). Each updates script lines.

Right card
- Check rows — info icon on header: Popover explaining pass/warn/fail (warnings don't block launch;
  failures do).
- Banner (i) — Popover `Local training is allowed when the estimate is ≤ 2 h (Settings › Compute &
  HPC › local limits).`
- `Copy` — clipboard write + toast `Script copied`.
- `Save .sh` — client-side Blob download `<session>.sh` (pure client; acceptable) or toast `not wired
  yet: save script` if downloads are blocked in the shell.

### Plots
- **Split strip**: blocked-by-time bars; x = time (blocks in order, no axis labels in frame; hours since
  start in a tooltip `CH2_A1 · block 4 · 288–360 h · test`), rows per channel, fill train blue / val amber
  / test green. Fixture: per channel 10 blocks = 7 train + 1 validation + 2 test (20 % / 10 %),
  placed at different positions per channel so no two channels share a test block. Frame (approx.):
  CH2_A1 test at blocks 4 and 9, val at 7; CH4_A2 test at 5 and 9, val at 8; CH7_B2 test at 6 and 8,
  val at 7. Changing test/val % regenerates blocks deterministically (seeded).
- **Glyph strip**: Glyph registry thumbnails.
- No other plots.

### Fixtures
```ts
interface TrainingTemplate { name: 'cnn_windows_v3' | 'cnn_windowset_v1'; version: 3 | 1; source: 'Signal' | 'WindowSet';
  classes: 4; multiClass: true; classifier: 'EfficientNet-B0 · 224 px GASF+GADF+RP';
  stages: { index: string; name: string; glyph: GlyphKey; signature: string }[] }
interface SourceChannelRow { recording: 'M2_aug_fs1' | 'L_LM_Jul26_J'; channel: string; hours: number; windows: number | null;
  humanVerdicts: number; classesSeen: [number, number] | null; flag?: 'no plateau verdicts'; disabledReason?: string; checked: boolean }
// CH2_A1 721 h 5,220 640 4/4 · CH4_A2 721 h 5,220 1,080 4/4 · CH7_B2 721 h 5,220 420 3/4 (flag) · L_LM_Jul26_J CH1 (hours: see conflict) disabled
interface WindowSetRow { id: string; version: number; channels: string[] | 'all'; windows: number; split: 'blocked' | 'none' | 'no split';
  verdictsNow: number; verdictsAtSave: number; badge: 'train-safe' | 'not train-safe' | 'no split · B7'; windowS: number;
  savedFrom?: { block: '01 Sliding windows'; template: 'cnn_windows_v3'; recipe: 'a7f39c2e' } }
// ws_M2aug_3ch_600s v1 (canon) · ws_M3jul_8ch_300s v2 · ws_verif_cnn_cluster_v1 v1 · ws_humanlabel_frame0b v1   ← SHARED with Library 6 window sets, Review queue sources, Analyse source chip
interface LabelArm { key: 'A' | 'B' | 'RF'; name: string; source: string; labelled: number | 'always on'; removable: boolean }
interface SplitPlan { testPct: 20; valPct: 10; gapS: 600; blocks: Record<string, ('train'|'val'|'test')[]>;
  perClass: Record<'train'|'val'|'test', Record<'spike-train'|'plateau'|'burst'|'slow-drift', number>>; warnBelow: 50 }
// train 412/268/190/620 (1,490) · val 61/38/27/92 (218) · test 118/74/31/209 (432 = canon test block) · total 2,140 = canon
interface LaunchCheck { text: string; state: 'pass' | 'warn' | 'fail' | 'na' }
interface Estimate { localH: 5.6; localNote: '3 arms + 5 model nulls'; diskGB: 3.9; diskNote: 'images + window set'; hpcH: 1.4; hpcNote: '1 GPU node'; limitH: 2 }
const TRAINING_JOBS = ['j-0212', 'j-0214']   // canon: "2 training jobs"
```
Shared: templates (Analyse training, Library 7), window sets (Library 6 / canon WINDOW_SET), recordings &
held-out lock (Settings 1), jobs store (Jobs), classes (canon CLASSES), local limits (canon LOCAL_LIMITS).

### Copy
`train a template across channels · paired label arms` · `unsaved` · `null label shuffle · RF 200× +
model 5×` · `≈ 5.6 h local above 2 h limit` · `Train locally` · `Create SLURM script` · `Launch`
`Results` `Compare` `Registry` · `2 training jobs · open in Jobs` · `Training template` `from Analyse` ·
`Open in Analyse` · `cnn_windows_v3 · v3` · `source Signal` · `multi-class · 4 classes` ·
`EfficientNet-B0 · 224 px GASF+GADF+RP` · `Sources` `the template starts from Signal, so each channel is
a source` · `Channels` `Saved window set` · `recording · channel` `hours` `windows` `human verdicts`
`classes seen` · `no plateau verdicts` · `Save window set` · `at 01 Sliding windows · 3 channels · 15,660
windows · split included` · `Label arms` `paired — same windows, split and test block` · `Add arm` ·
`manual labels` `Review verdicts · 4 classes` `2,140 windows labelled` · `cluster labels` `03 Cluster ·
k = 4 · criterion max silhouette` `15,660 windows labelled` · `random-forest baseline` `02 Window matrix
features · trained once per arm` `always on` · `train every arm on` `windows labelled in every arm ·
2,140` `so the comparison is paired` · `Evaluation` `test block set aside before training · blocked by
time` · `test 20 %` `validation 10 %` `gap ≥ 600 s (1 window)` · `M4_aug locked · Settings › Datasets`
`held out` · `train` `validation` `test — scored once, after training` · `windows per class` ·
`burst: 31 test < 50` · `Options` · `repeat with different seeds` `3 seeds` `epochs 30` `batch 64`
`null RF 200× · model 5×` · `Before launch` (6 check lines as Regions) · `Estimate` `local` `disk` `HPC` ·
`over the 2 h local limit · Train locally is off` · `SLURM script` · `Copy` `Save .sh` · `After
submitting` · `Creating the script adds the job to Jobs` `mark it submitted / running / finished there`
· `Results return through Jobs › Manifest inbox` `checked against this launch, then imported`.
Script (frame 1, verbatim):
```
#!/bin/bash
#SBATCH --job-name=train_cnn_M2aug_sep14
#SBATCH --gres=gpu:1  --time=04:00:00
#SBATCH --mem=32G

python -m pipeline.train \
  --template cnn_windows_v3@3 \
  --sources M2_aug_fs1:CH2_A1,CH4_A2,CH7_B2 \
  --arms manual,cluster --baseline rf \
  --paired-windows labelled-in-all \
  --split blocked:test=0.2,val=0.1,gap=600 \
  --null rf:200,model:5 \
  --save-windowset ws_M2aug_3ch_600s_v2 \
  --manifest inbox/
```
1b script: `--job-name=train_cnnws_M2aug_sep14`, `--template cnn_windowset_v1@1`, `--windowset
ws_M2aug_3ch_600s@1`, `--arms manual,cluster --baseline rf`, `--paired-windows labelled-in-all`,
`--split from-windowset`, `--null rf:200,model:5`, `--verdicts-as-of launch`, `--manifest inbox/`.
1b captions: `the template starts from WindowSet, so the source is one saved set` · `window set`
`channels` `windows · split` `verdicts now (at save)` · `train-safe` `not train-safe` `no split · B7` ·
`arrives with its split and spacing check · saved from 01 Sliding windows of cnn_windows_v3 · recipe
a7f39c2e` · `split comes with the window set · locked here, change it by saving a new version` ·
`gap between blocks ≥ window length · checked at save`.

### Frame ⟷ spec conflicts
1. **`L_LM_Jul26_J · CH1  92 h`** — §0 canon: L_LM_Jul26_J is **22.4 h**. **Canon wins** → `22.4 h`.
2. **Disabled L_LM row has no reason** — §7b.1 / kit DisabledReason: add the reason (see Controls).
3. **Class column order** `spike-train · plateau · burst · slow-drift` vs canon key order (1 spike-train,
   2 burst, 3 slow-drift, 4 plateau). Frame order is used consistently across Launch/Results/Registry;
   recommend keep frame order on Models pages (it is a display order, not a key change) but colour
   swatches must use canon class colours. Flag to critic.
4. **Save-window-set name** `ws_M2aug_3ch_600s v2` (chip) vs script `ws_M2aug_3ch_600s_v2`. Canon: "A new
   launch saves `v2`" → display `ws_M2aug_3ch_600s · v2`; script flag may keep `_v2`/`@2` — recommend
   `@2` to match 1b's `@1` syntax.
5. **Windows per channel 5,220 at 600 s over 721 h** implies ~500 s stride, i.e. overlapping windows,
   while the gap rule is between split blocks (not windows) — consistent with P12, but the frame never
   states stride. Not a conflict; note for the tooltip (`stride ≈ 497 s`) — better leave unstated.
6. **1b "verdicts now (at save)" `2,140 (1,980)`** while arms show `2,140 windows labelled` — consistent
   with §6.9 "coverage is live"; SLURM `--verdicts-as-of launch`. Keep.

### Fog
- F19. Other label-arm kinds for *Add arm* are not specified.
- F20. Estimate model (how 5.6 h scales with channels, seeds, epochs) — fixture maths only.
- F21. How a split applies to `ws_humanlabel_frame0b` (no split) is backlog **B7**, still open; row is
  disabled.
- F22. `ws_M3jul_8ch_300s` detail (split blocks, per-class counts) is not in any frame.
- F23. Launch-from-Jobs round trip (manifest inbox → Results) belongs to Jobs; Results fixture assumes
  `j-0212` already imported (canon: imported 13 Sep 21:40).
- F24. Where the `2 training jobs` count comes from (canon names j-0212 finished and j-0214 running) —
  fine, but "open in Jobs" filter param name is owned by Jobs.

## models.results
TODO

## models.compare
TODO

## models.registry
TODO

## Kit needs
TODO
