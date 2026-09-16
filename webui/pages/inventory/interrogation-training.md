# Inventory — Analyse › Interrogation and Analyse › Training

Build spec for the empty-shell pages built from `prototyping/imgs/analyse-interrogation/*.pdf` (8 frames)
and `prototyping/imgs/analyse-training/*.pdf` (8 frames). All 16 frames were read (text + image).
Sources: spec §0, §3, §6.1–6.3, §6.6–6.9, §12 P7 P8 P10 P11 P12 P13 P15 P18 (+ P3, P4, P19, P24 where the
frames lean on them); `UI_REVIEW_BACKLOG.md` (B3, B4, B6, B7, B12, B28) and `UI_SWEEP_2026-09-14.md`
(the per-frame arithmetic defects); live code in `webui/client/src/analyse/` and the in-progress shared kit
(`fixtures/canon.ts`, `kit/sim.ts`, `kit/store.ts`, `kit/notWired.ts`).

Code lives in `webui/client/src/interrogation/` and `webui/client/src/training/`. Every page passes
`demo` to `Header` (the "demo data" chip). Nothing on these pages calls the bridge.

Frame coordinates below are in the 1440 × 900 frame: nav rail 0–62 px, header 0–42 px, content column
x ≈ 86–1366 (≈ 1280 px wide). "≈ 60 %" means share of that content column.

## Pages

| page id | route | frames covered | spec § | states (frame → state name → how reached) |
|---|---|---|---|---|
| analyse.interrogation | `#/analyse/interrogation` | interrogation-1-family-block, interrogation-1b-source-picker | §6.2, §6.6, §6.8, P8, P10 | 1 → `default` (F-03, 16 of 17 in scope) → route · 1b → `source-picker` → click the source chip, or `?popover=source` (`&tab=family\|run\|review\|explore`) · (derived) `swapped` → pick another family in the picker, or `?family=F-07` · (derived) `stale` → untick a member / change a source setting · (derived) `running` → click Run chain, or `?state=running` · (derived) `empty-scope` → click "none" |
| analyse.interrogation.slope | `#/analyse/interrogation/block/1` | interrogation-2-block01-slope, interrogation-2b-slope-large-family, interrogation-2c-slope-stale-after-edit | §6.6, §6.8 `SpanSet → SpanSet + Features`, P8, P10 | 2 → `default` (F-03, rose) → route · 2b → `large-family` (F-07, 212 events, overlay) → pick F-07 in the source picker, or `?family=F-07` · 2c → `stale-after-edit` (steepest window 3 → 5, preview) → drag the steepest-window slider, or `?state=stale` · (derived) `running` → Re-run from 01 · (derived) `upstream-spike-shape` → `?upstream=spike-shape` renders the Spike shape block page placeholder (see fog) |
| analyse.interrogation.aggregate | `#/analyse/interrogation/block/2` | interrogation-3-block02-aggregate, interrogation-3b-aggregate-colour-by-recording, interrogation-3c-aggregate-wired-from-spike-shape | §6.6, §6.8 `Features → views`, P7, P10 | 3 → `default` (slope features, depth ~ duration) → route · 3b → `colour-by-recording` → Parameters › colour by = recording and Scaling Seg = depth ~ max slope, or `?colour=recording&pair=depth-maxslope` · 3c → `wired-from-spike-shape` (+ Feature wiring popover) → `?upstream=spike-shape&popover=wiring`; by click: Import template `spike_shape_v1` (chain page) or the "+ stage" swap row, then "+ custom" in the Scaling Seg opens the popover |
| analyse.training | `#/analyse/training` | training-0-training-chain, training-0b-human-window-source-ILLUSTRATIVE | §6.1, §6.2, §6.3, §6.7, P11, P13, P15, P18 | 0 → `default` (Signal · CH4_A2 · span 0–45.2 h) → route · 0b → `illustrative-human-windows` → source chip › "Human-labelled windows (illustrative)", or `?source=human-labelled` · (derived) `source-popover` → click source chip / `?popover=source` · (derived) `queued-to-review` → Send 412 unseen windows to Review · (derived) `stage-deleted` (invalid junction) → row delete icon |
| analyse.training.windows | `#/analyse/training/block/1` | training-01-block01-sliding-windows | §6.7, §6.8 `Signal → WindowSet`, §6.9, P12, P13, P18 | 01 → `edited` (gap 5 → 10 min pending) → `?state=edited`, or drag the gap slider · `default` (no unapplied changes, gap 10 min) → route · (derived) `invalid-gap` → gap < window length · (derived) `random-split` → Seg "random" · (derived) `running` → Apply & re-run from 01 |
| analyse.training.matrix | `#/analyse/training/block/2` | training-1-block02-window-matrix | §6.7, §6.8 `WindowSet → WindowSet`, P4, P12 | 1 → `edited` (Random Forest exclusion pending) → `?state=edited`, or untick/tick a feature group · `default` (no unapplied changes) → route · (derived) `label-derived-included` → tick CNN scores or Random Forest · (derived) `running`/`paused` → Apply & re-run from 02 |
| analyse.training.cluster | `#/analyse/training/block/3` | training-2-block03-cluster, training-2b-block03-choose-k | §6.7, §6.8 `WindowSet → Grouping`, B4 | 2 → `default` → route · 2b → `choose-k` → "Choose k →", or `?view=choose-k` · (derived) `cut-dragged` (pending) → drag the cutline · (derived) `merge-pending` → Merge C5 + C6, or `?merge=C5,C6` · (derived) `save-grouping-modal` → Save grouping, or `?modal=save-grouping` · (derived) `criterion-locked` → Lock (choose-k) |
| analyse.training.encode | `#/analyse/training/block/4` | training-3-block04-encode | §6.7, §6.8 `WindowSet → Encoding`, B6 | 3 → `default` (window 118, fusion unticked) → route (`?window=118`) · (derived) `edited` → tick Fusion / change a parameter · (derived) `new-encoder-version` → change image size or encoder set · (derived) `running` → Apply & re-run from 04 |
| analyse.training.model | `#/analyse/training/block/5` | training-4-block05-model | §6.7, §6.8 `Encoding + labels → Model`, P11, P19, P24 | 4 → `default` → route · (derived) `script-copied` → Copy script · (derived) `trial-job-created` → Download trial job · (derived) `labels-manual` → labels-from radio · (derived) `focus-trial` → `?focus=trial` (scrolls to the trial-job card; used by the chain row's "Trial job on this channel") |

Frames with a pending edit (training-01, training-1) are block pages whose chain row already shows the
change as applied (sweep: "block pages that open with changes their chain already shows as applied").
Resolution used throughout: **the route opens clean; the frame's pending state is the `?state=edited`
deep link** (and is also reachable by making the edit by hand). See each page's conflicts.

## Group conventions (read before any page below)

### Moving between the detection, interrogation and training chains (spec §6.1, §6.2)

§6.1: detection, interrogation and training are **not modes**. They are what a chain's terminal type makes
it (`SpanSet` → detector, features over a `SpanSet` → interrogation, `Model` → training chain). The three
names survive only as **filters over saved templates**. So the shell gets **no mode switcher, no tabs, no
sub-nav** inside Analyse. The route prefix is just a consequence of the chain in hand, and each of the three
routes holds its own in-memory draft.

| chain | route root | draft lives in | source block kind (§6.2) | terminal |
|---|---|---|---|---|
| detection (live) | `#/analyse/chain`, `#/analyse/block/<i>` (0-based) | `state.tsx` `chain` (sessionStorage) | signal span (from Explore) | SpanSet |
| interrogation (demo) | `#/analyse/interrogation`, `…/block/1`, `…/block/2` | `useDemoState('analyse.interrogation.draft')` | SpanSet: Library family · prior run · Review selection · Explore spans | Features (→ View) |
| training (demo) | `#/analyse/training`, `…/block/1…5` | `useDemoState('analyse.training.draft')` | Signal span (sliding windows) · WindowSet (illustrative, 0b) | Model |

Ways in and across. Every path below is either a hash navigation or an in-memory write:

1. **Nav rail › Analyse** → `#/analyse/chain` (unchanged; the live detection chain stays the landing page).
2. **"→ Analyse events"** is the universal verb that sends a SpanSet into Analyse (§6.2). On the live chain
   footer and the live Threshold block page it is currently `disabled` ("out of slice scope"). Recommended
   (owned by the chain inventory, noted here for the hand-off): enable it as
   `navigate('analyse/interrogation?popover=source&tab=run')`, which opens the interrogation source picker on
   its *Prior run* tab. It is a navigation only, so no live behaviour changes. Library (family / atlas rail),
   Discovery runs and Review use the same verb with `?family=F-03` (Library), `?tab=run&run=r-0412`
   (Discovery) or `?tab=review&queue=q-12` (Review). The interrogation toolbar then reads
   "arrived via Analyse events".
3. **Import template** (chain page popover, P2). Add a template-kind filter Seg `all · detection ·
   interrogation · training` (the §6.1 "filters over saved templates"). Picking a template whose terminal
   is not SpanSet leaves the detection page: `spike_shape_v1` → `#/analyse/interrogation/block/2?upstream=spike-shape`,
   `cnn_windows_v3` → `#/analyse/training`. `cnn_windowset_v1` is disabled in the picker with reason "source
   WindowSet · a saved window set spans 3 channels · Analyse is single-channel (P3) · launch it in Models".
   A toast confirms: "imported cnn_windows_v3 · training chain (terminal Model)". The training chain page's
   own Import popover does the reverse for detection templates (→ `#/analyse/chain`).
4. **History** (chain page and training page popover). Run `#140 F-03 slope interrogation` → *Apply to
   source* → `#/analyse/interrogation`. Detection runs `#128 / #131 / #97` listed on the training page are
   disabled with reason "terminal SpanSet · this is a training chain" (P2's disabled-with-reason rule).
5. **Models › Launch** "Open template in Analyse" → `#/analyse/training`. Training chain "Train in Models"
   → `#/models/launch?template=cnn_windows_v3`.
6. **Inside a chain**, the ribbon chips navigate between that chain's block pages. The Source chip goes to
   the chain's root (`#/analyse/interrogation` is itself the source-block page; `#/analyse/training` is the
   rows page). `‹ full chain` goes to the root. Nothing in a ribbon ever jumps to another chain.
7. **Terminal-type readout** (ribbon right edge on interrogation pages: "terminal type Features · this chain
   is an interrogation"; training footer chip "terminal Model → training template"). Each carries an InfoTip
   with the §6.1 table, so the user can see *why* the page looks the way it does.

`webui/client/src/analyse/index.tsx` today renders `ChainPage` for **any** `analyse/<page>` that is not
`block`, so `#/analyse/interrogation` would silently show the live detection chain. The dispatcher must
test `route.parts[0] === 'interrogation' | 'training'` first, then `block`, then fall back to `ChainPage`.
Block index for the new chains: `route.parts[2]` (1-based, equal to the displayed stage number). The live
detection route keeps its 0-based `analyse/block/<i>` (`block/0` = "01 Baseline"). The mismatch is
recorded under Fog.

### Shared toolbar (every page in this group)

Left to right, one row (y ≈ 55–85, 30 px tall), same classes as the live `an-toolbar`:

- `‹ full chain` ghost button (block pages only; the training root has none). On
  `training/block/3?view=choose-k` it reads `‹ cluster` and clears `view`.
- Name chip (training only): `cnn_windows_v3 ✎ unsaved`. Click → inline rename (live `NameChip` shape).
  Validation: required; `^[a-z0-9_]+$`, message "lowercase letters, digits and _ only"; ≤ 40 chars. The
  interrogation frames draw **no** name chip (see conflicts).
- Source chip (blue; green when the source is human-origin, 0b): icon + text + ▾. Interrogation:
  `source [library icon] Library family · F-03 sharkfin ▾`. Training: `〜 Signal · CH4_A2 · span 0–45.2 h ▾`.
- Muted note (interrogation only, when arrived by hand-off): `arrived via Analyse events`.
- spacer
- Null chip (white pill, green dot): `● null matched random windows · 200× ⓘ` (interrogation, P10) /
  `● null label shuffle ⓘ` (training). The ⓘ opens an InfoTip. The chip is **not** a toggle: every
  result carries a null (P10, P23). The InfoTip ends with "Settings › Nulls →" (`#/settings/nulls`).
- Estimate text (mono, muted; amber when something is stale; purple when it names the cluster). Copy per
  page.
- Secondary buttons (per page): `History`, `Import`, `Save template` / `Save as template`.
- Primary button (per page): `▶ Run chain` · `↻ Re-run from 01` · `↻ Apply & re-run from NN` ·
  `✓ Apply k = N` · `Train in Models`.

`Save template` / `Save as template` (every page) → kit `SaveTemplateModal`: Text field "Template name"
(prefilled with the draft name; interrogation default `sharkfin_slope_v1`). Validation: required,
`^[a-z0-9_]+$`. A name already in the canon's 14 templates shows the note "saves a new version of
<name>" rather than an error. A read-only KeyValue shows "kind: interrogation template · terminal Features"
or "training template · terminal Model", with "stages" listing the ribbon. `Save` →
`recordDemoWrite('analyse','save-template',…)`, the name chip flips to `saved`, and a toast reads
"saved <name> · in memory (demo) · Library › Templates" with the action "Open in Library"
(`#/library/templates`).

### Shared ribbon (every block page; card y ≈ 105–165, full width, 56 px tall)

Kit `ChainRibbon`. Label `chain`, then chips joined by `›`. Each chip is about 190 px wide (interrogation,
3 chips) or 180 px (training, 6 chips). A chip holds: a number (`01`, muted), the title (bold), a status
Badge at the top right, and the type signature underneath (mono, muted). The current chip has a blue border
and light-blue fill. The Source chip is prefixed `●`. After the last chip: `+ stage` (interrogation, text
button) or a square `+` (training). Interrogation only, at the right edge: `terminal type  Features` over
`this chain is an interrogation` (mono, muted, InfoTip).

- Interrogation chips: `● Library family [cached] — → SpanSet` · `01 Resolve spans [cached] SpanSet → Features`
  (3c: `01 Spike shape`) · `02 Aggregate [cached] Features → View`.
- Training chips: `● Source [cached] — → Signal` · `01 Sliding windows Signal → WindowSet` ·
  `02 Window matrix WindowSet → WindowSet` · `03 Cluster WindowSet → Grouping` · `04 Encode WindowSet → Encoding` ·
  `05 Model Encoding + labels → Model`.
- Badge words only from §0: `cached · stale · new · running · paused · failed · on cluster · invalid`.
  Every chip is clickable (navigates). A running stage's chip shows `running · 1.2 s`.
- Training `+` → toast `not wired yet: insert a stage into the training chain (type-contract modal §6.4)`.
  Interrogation `+ stage` → see analyse.interrogation controls (the insert/swap popover).

### Shared block-page footer (training 01–04; frames draw it, y ≈ 770–815, full width)

Kit `UnappliedChangesBar`: status dot + bold state (`1 unapplied change` / `No unapplied changes`) + muted
consequence line + `↶ Revert to recommended` + primary `↻ Apply & re-run from NN`. Rules:
- the dot is amber only when changes are pending, grey otherwise (sweep: an amber dot beside "No unapplied
  changes" is a defect);
- with nothing pending but downstream stages stale, the primary reads `↻ Re-run from <first stale>`;
  with nothing pending and nothing stale it is disabled with DisabledReason "no unapplied changes";
- `Revert to recommended` is disabled with reason "already at the recommended values" when the pending set
  equals the recommended set.

### Draft stores and simulated runs (kit)

- `useDemoState('analyse.interrogation.draft', seed)` holds `{ source, inScope: Record<memberId, boolean>,
  sourceSettings, rules: {applied, pending}, upstream: 'slope' | 'spike-shape', aggregateView, staleFrom: 1 | 2 | null }`.
- `useDemoState('analyse.training.draft', seed)` holds `{ name, saved, source, params: {windows, matrix,
  cluster, encode, model} each {applied, pending}, staleFrom, queuedToReview, deletedStage }`.
- Runs use `useSim('analyse.interrogation.run')` / `useSim('analyse.training.run')`. Step labels are the
  stage names, `stepMs` 600. A stage whose "runs on" is the cluster makes the sim `pauseAt` it. Its chip
  badge then shows `on cluster`, and a toast carries the action "Open in Jobs" (`#/jobs`) (P4, P24). While
  a sim is busy, the primary button becomes `■ Cancel` (`sim.cancel()`), parameter controls are disabled
  with reason "wait for the run", and the process card gets the live `bp-run-veil` look.
- Every save, queue, lock or merge calls `recordDemoWrite('analyse', kind, detail)`.
- A control whose real behaviour would need the core or bridge, where the frame shows no result, calls
  `useNotWired()` → toast `not wired yet: <call>`.

### Shared fixture additions to `fixtures/canon.ts` (proposed; other workspaces need them)

```ts
// families: the frames add F-01; canon §0 lists F-03/F-04/F-07/F-11 only
{ id: 'F-01', name: 'single drop', members: 64, recordings: ['M2_aug fs1', 'M3_jul'], colour: FAMILY_COLOURS['F-01'] }
// fields the source picker needs for the existing entries:
// F-03 sharkfin    112 members · 3 recordings · 11 adjudicated of the 17 within d ≤ 0.35
// F-04 spike train   9 members · 1 recording (M3_jul) · 0 adjudicated
// F-07 slow drift  212 members · 4 recordings (M2_aug fs1, M2_aug fs2, M3_jul, L_LM_Jul26_J) · 48 adjudicated
// F-11 burst        31 members · 3 recordings (M2_aug fs1, M3_jul, L_LM_Jul26_J) · 12 adjudicated

export interface FamilyMember {              // shared with Library › Family and Review cluster strips
  id: string                                  // s-NNNN (M2_aug), m-NNNN (M3_jul), l-NNNN (L_LM): frame prefixes
  family: string; recording: string /* canon label */; channel: string
  onset_h: number                             // hours since recording start
  d: number                                   // scale-invariant distance to the family medoid
  verdict: 'seed' | 'interesting' | 'not_interesting' | 'artifact' | null   // null = unadjudicated
  fs_hz: number; trace_mV: number[]           // syntheticTrace(), detrended mV, never normalised
}
export const TEMPLATES_BY_KIND = {            // §6.1: the three names are filters over the 14 saved templates
  detection: ['drop_motifs9', 'sharkfin_v2', 'mp_discord_v3', 'cnn_detect_cluster_v1', 'drop_cnn_v1', 'sharkfin_cnn_v2' /* … */],
  interrogation: ['spike_shape_v1', 'sharkfin_slope_v1'],
  training: ['cnn_windows_v3', 'cnn_windowset_v1'],
}
export const TRAINING_CHAIN = { /* cnn_windows_v3 stages + params, see analyse.training fixtures */ }
// shared with Models › Launch and Library › Templates
```

`canon.ts` today maps `#140 F-03 slope interrogation` to template `spike_shape_v1`. But the run's name says
*slope*, and frame 3c presents Spike shape as "a different analysis". Recommended: #140 → `sharkfin_slope_v1`
(an interrogation template using the Resolve spans block), with `spike_shape_v1` kept as the Spike shape
interrogation template.

### The one timescale decision that affects every interrogation number

The frames draw F-03 falls lasting **0.7–1.1 s**, a "steepest window 3 samples", anatomy axes of −1 s to
+2 s, and slopes around −0.7 mV/s. Canon §0: F-03 is **~21 s long**, and M2_aug and M3_jul are sampled at
**1 Hz**. A 1 s fall at 1 Hz is one sample, so the frame numbers cannot exist. §0 wins. Mechanical rule
for every interrogation fixture: **multiply every frame time by 10 and divide every frame slope by 10.**
Falls become 7–11 s and recoveries 10–13 s (fall + recovery ≈ 21 s). Anatomy axes run −10 s … +20 s, the
source-page overlay −20 s … +40 s. Slopes become −0.033 … −0.073 mV/s. The `units` Select defaults to
`mV · 10 s` and the rose caption reads "−45° = −0.1 mV/s", so every **angle, depth and shape in the frames
stays exactly as drawn**. Only time and slope tick labels change. Spike shape (3c) half-widths and rise
times scale the same way (×10).

## analyse.interrogation — source block (frames 1, 1b)

**Route & states.** `#/analyse/interrogation`. `default` (route) · `source-picker` (`?popover=source`,
`&tab=family|run|review|explore`) · `swapped` (`?family=F-07`, or pick in the picker) · `stale` (untick a
member / change a source setting) · `running` (`?state=running`, or Run chain) · `failed`
(`?state=failed`) · `empty-scope` (click `none`).

**Regions** (`data-testid`): `interrogation-toolbar` (‹ full chain · source chip · "arrived via Analyse
events" · null chip · estimate · Save as template · Run chain) · `chain-ribbon-card` (ChainRibbon chips
`● Library family` / `01 Resolve spans` / `02 Aggregate`, `+ stage`, terminal-type readout) ·
`source-block` (title `● Library family — → SpanSet`, clustering chip, the one-line family fact row,
filter row, selection row, `member-grid` of ≤ 10 tiles, verdict legend + `member-pager`) ·
`members-overlaid` · `scope-card` (recording × channel matrix with an `excluded` row) ·
`source-settings` · `provenance-card` ("Where this family came from", Open in Library).

**Controls.** adjudicated only / exclude artifacts checkboxes · distance ≤ · recording · channel · sort
dropdowns (recording lists `M4_aug` disabled, reason "held out (D6)") · select all / none / invert ·
per-tile include checkbox (unticking makes 01 and 02 stale) · resample + align dropdown on the overlay ·
four Source-settings dropdowns · source chip → the 4-tab picker (Library family table, Prior run —
detection runs disabled with reason, Review selection, Explore spans) · Run chain → `useSim` queued →
running → done · Save as template → modal → `recordDemoWrite('analyse','save-template',…)`.

**Fixtures.** `fixtures/interrogation.ts`: 17 F-03 members (16 in scope, `s-0348` artifact/excluded),
212 F-07 members, the F-01/F-04/F-11 picker rows, clustering `Ward · t 10.1 · v3`, provenance
(`run 114 · 2 Sept`, exemplar `E-0102`, threshold 0.35, recipe `a7f39c`).

**Copy.** Header `Analyse | Library family | F-03 sharkfin · 16 of 17 members in scope`. Estimate
`≈ 6 s · 3 of 3 cached`. Footnote `swapping a SpanSet source keeps 01 and 02; they re-run on the new
members`. Source settings footnote `members keep identity by file · channel · sample range`.

## analyse.interrogation.slope — 01 Resolve spans (frames 2, 2b, 2c)

**Route & states.** `#/analyse/interrogation/block/1`. `default` (F-03, rose) · `large-family`
(`?family=F-07`: strip pages to 41–50, sampled overlay replaces the rose) · `stale-after-edit`
(`?state=stale`, or move the steepest-window slider) · `running` (`?state=running` / Re-run from 01) ·
`upstream-spike-shape` (`?upstream=spike-shape` — the block is titled `01 Spike shape`).

**Regions.** `interrogation-toolbar` · `chain-ribbon-card` · `anatomy-card` (`01 Resolve spans — slope
analysis`, units/marks dropdowns, the annotated event curve, mark legend, `rules resolved cleanly`
chip, `event-readout`, `event-strip` of ≤ 10 thumbnails + `jump to flagged`) · `rose-card` (F-03) /
`overlaid-card` (F-07, `overlay | rose` Seg, seeded resample, sample size) · `rules-card` (four rule
controls + flagged-events warning, and in the stale state the preview strip + `discard`) ·
`per-event-table` (16 / 212 rows, CSV).

**Controls.** units (`mV · 10 s` default) · marks (`minimal | all | none`) · strip ‹ › · jump to flagged ·
row click selects the event above · steepest-window Slider (3 → 5 marks the chain stale and shows the
preview) · onset/trough/σ dropdowns · rose colour-by · sample-size dropdown + resample (P8) ·
`Re-run from 01` runs the sim and clears stale.

**Fixtures.** per-event features on every member (`depth_mV`, `max_slope`, `angle`, `peakedness`,
`duration_s`, `recovery_s`, `flags`) plus the anatomy curve. Frame times ×10 and slopes ÷10 (see the
timescale decision): `−0.0725 mV/s`, `10.0 s`, σ `MAD · 0.000958 mV/s`, rose caption `−45° = −0.1 mV/s`.

**Copy.** `these three rules define every number on this page` · `1 event flagged · two troughs within
window` · stale preview `preview on cached spans: mean angle −28° → −25° · 3 of 16 events shift > 10 % ·
depth unchanged` · veil `showing last run · results are stale until re-run`.

## analyse.interrogation.aggregate — 02 Aggregate (frames 3, 3b, 3c)

**Route & states.** `#/analyse/interrogation/block/2`. `default` (`depth ~ duration`, colour none) ·
`colour-by-recording` (`?colour=recording&pair=depth-maxslope`) · `wired-from-spike-shape`
(`?upstream=spike-shape`) · `wiring` (`?upstream=spike-shape&popover=wiring`, also from `+ custom`) ·
`running` / `empty` (`?family=F-04`, 9 members, 0 adjudicated → too few to fit).

**Regions.** three `hist-*` cards (depth/interval/max slope, or amplitude/half-width/rise) each with its
null behind in grey and a one-line verdict · `scaling-card` (pair Seg + `+ custom`, axes dropdown,
Scatter with fit band, `exponent β` tile with CI, `null β` tile, per-recording βs in 3b) ·
`timeline-card` ("When events happened", height = depth, τ per recording) · `parameters-card` (six
dropdowns, `views only · nothing here is stored`) · `summary-card` (4 stat tiles + CSV / Figures /
Stage 1 outlier for Review) · `wiring-popover` (P7: the Aggregate block is generic and wired from the
upstream block's declared Features).

**Controls.** colour by · null (`no null` disabled, reason P10) · binning · interval defined as ·
outliers · purity check · scaling-pair Seg · axes log–log/linear · CSV and Figures (not wired toasts) ·
`Stage 1 outlier for Review` → `recordDemoWrite('review','add-queue',…)` + toast "Open in Review" ·
wiring dropdowns rewire each histogram/timeline/pair from the upstream feature list.

**Fixtures.** `AGGREGATE[upstream]`: per-feature domains, null medians/CVs, β with CI and null β,
per-recording βs, timeline τ, and the upstream feature schema (`amplitude_mV half_width_s rise_s
decay_s isi_s onset_h`) that drives the wiring popover.

**Copy.** `dip test p 0.21 · n too small to call modes` · `CV 0.31 · null CV 0.98 [0.71–1.22] · p < 0.01`
· `depth ∝ duration^β · R² 0.81 · n 16` · `figures export with parameters and recipe hash beneath` ·
`any block emitting Features over a SpanSet can feed Aggregate`.

<!-- END -->

