# Inventory — Review and Jobs

Status: in progress — Pages table and review.inspector written; the rest follows.

Sources read: `prototyping/imgs/INDEX.md`; `UI_FUNCTIONAL_SPEC.md` §0, §3, §4.1–4.3, §4.6, §4.7,
§7c, §9.6, §9.8, §9.16, §10, §12 (P6, P20, P21, P24); `UI_REVIEW_BACKLOG.md` (Review/Jobs rows,
B5, B15, B16, B22, B26–B29); all 8 review frames and all 4 jobs frames. For shortcut and queue
defaults I also read `settings/settings-16-keyboard-behaviour.pdf` and the text of
`settings-08-review-queues.pdf` and `chain-1i-paused-result-in-place.pdf` (read-only, for consistency).
Existing client read: `App.tsx`, `state.tsx` (route parser, `setQuery`), `shell/Header.tsx`,
`shell/NavRail.tsx`, `fixtures/canon.ts`, `kit/store.ts`, `kit/sim.ts`, `kit/notWired.ts`.

## Pages

| page id | route | frames covered | spec § | states (frame → state → how reached) |
|---|---|---|---|---|
| review.inspector | `#/review/queue/<queueId>/<itemId>` (e.g. `#/review/queue/q-12/c-0343`); `#/review` and `#/review/queue/<queueId>` redirect to the queue's current item | review-1-candidate, review-1b-other-channels, review-3-queue-open, review-4-evidence-open, review-6-seed-promoted, review-5-blind-verification (as the blind state) | §10.1–10.4, §10.6, §10.7, P6, P20, P21 | 1 → `rails-collapsed` (default) · 1b → `other-channels` popover (click *Other channels* / `?pop=other-channels`) · 3 → `queue-rail` (rail toggle / `\` / `?rail=queue`) · 4 → `evidence-rail` (rail toggle / `?rail=evidence`) · 6 → `seed-promoted` (press **S** / `?state=promoted`) · 5 → `blind` (any item of a blind queue, e.g. `#/review/queue/q-19/w-40211`) · extra: `verdict-given` (non-seed key, auto-advance off), `shortcuts` popover (`?pop=shortcuts`), `queue-picker` popover (`?pop=queues`), `blind-toggle` popover (`?pop=blind`), `queue-empty` (every item judged, `?state=empty`) |
| review.cluster | `#/review/queue/<queueId>/cluster/<clusterNo>` (e.g. `#/review/queue/q-15/cluster/12?member=c-0373`); alias `#/review/cluster/12` redirects (cluster numbers are unique across fixture queues) | review-2-cluster, review-7-batch-undone | §10.5 | 2 → `batch-ready` (default: 6 of 7 included, c-0377 excluded) · 7 → `batch-undone` (press a verdict key then **Ctrl Z** / `?state=undone`) · extra: `batch-written` (after a verdict key, auto-advance off), `include-all` (click *Include all*), `redone` (**Ctrl Shift Z** / *Redo*), rails and popovers as review.inspector |
| review.blind | **state of review.inspector, not a page** — `#/review/queue/q-19/w-40211` | review-5-blind-verification | §10.6, P20 | 5 → `blind-unjudged` (default for q-18, q-19) · extra: `blind-revealed` (after a verdict: the previous-window card updates; stays on page only when auto-advance is off), `blind-evidence-rail` (`?rail=evidence`, machine sections masked) |
| jobs.all | `#/jobs` (`?filter=all\|needs-you\|paused\|cluster\|local\|queues\|finished`, `?ws=<workspace>`, `?sel=<jobId>`, `?drawer=inbox`) | jobs-1-all | §7c.1, P24 | 1 → `all` with `sel=r-0431` (default) · extra: filter states (Seg click / `?filter=`), `filter-empty` (e.g. `?filter=finished&ws=explore`), `finished-expanded` (click the collapsed group), `rail-<kind>` (select a cluster / local / queue row), `inbox-drawer` (*Manifest inbox · 1* / `?drawer=inbox`), `continuing a-0098` (card *Continue*: simulated run) |
| jobs.paused | `#/jobs/run/<runId>` (frame: `#/jobs/run/r-0431?state=arrived`; also `#/jobs/run/a-0098`) | jobs-2-paused-run | §7c.2, P24, B22 | 2 → `result-arrived` (`?state=arrived`, or *Look again* from `waiting`) · extra: `waiting` (default for r-0431 per canon and jobs-1 rail), `continuing` (*Continue from stage 4*: sim), `finished` (sim done), `cancel-confirm` modal (*Cancel run* / `?modal=cancel`), `cancelled`, `new-script` modal (*New SLURM script* / `?modal=new-script`) |
| jobs.upload | `#/jobs/run/<runId>/upload` (`?file=mismatch\|ok-no-nulls\|ok\|none`) — renders jobs.paused behind a Modal | jobs-3-upload-and-continue | §7c.3, P24 | 3 → `refused` (`?file=mismatch`, default because it is the frame) · extra: `no-file` (`?file=none`), `checking` (after choosing a file: checks tick in), `passes-no-nulls` (`?file=ok-no-nulls`), `passes` (`?file=ok`), `file-menu` popover (*Choose another file*) |
| jobs.cluster | `#/jobs/cluster/<jobId>` (frame: `#/jobs/cluster/j-0214`; also j-0217, j-0212, j-0209) | jobs-4-cluster-job-inbox | §7c.4, §9.6 | 4 → `running-overdue` (j-0214 default: 3.3× estimate reminder) · extra: `running` (j-0217, within estimate), `finished-imported` (j-0212), `failed` (j-0209), `snoozed` (*Still running · remind me in 3 h*), `marked-finished` / `marked-failed` (buttons), `script-created` (a new job from *New SLURM script*), `inbox-arrived` (r-0431 row reads *result arrived 14:31* once the demo result has arrived) |

**Why blind is a state, not a page.** Frame 5 has the same regions, keys, rails and write path as
frame 1; only the queue's `blind` flag changes what the pills, micro-stats and second-row right
card show. Blind is stored **per queue and with every verdict** (§10.6), and the toggle is per queue —
so the sighted Discovery queue q-12 can be switched blind on the same page. A second page would
duplicate the single human write path P6 protects. Builders implement one `Inspector` that reads
`queue.blind`; review.blind gets its own H2 below only because the frame differs enough to need its
own fidelity notes.

**Why `<itemId>` rather than `<itemIndex>`.** Queue filters (channel, score, status, group) reorder
and shrink the queue, and auto-advance / undo move through it; an index would point at a different
item after each. Ids (`c-0343`, `w-40211`, `cluster/12`) are stable, are the title copy, and match
the up-next list. A builder may still accept a numeric segment and resolve it as a 1-based position
in the current filtered order.

**Why jobs.paused uses r-0431, not a-0098, for the frame.** jobs-2 draws r-0431 (Discovery,
mp_drops_v3) with its result arrived, and jobs-4 draws j-0214, not j-0217. The routes are generic, so
a-0098 and j-0217 render too; the screenshot routes are the ones the frames draw.

---

## review.inspector

### Route & states

| state | frame | reached by | query |
|---|---|---|---|
| rails-collapsed (default) | review-1-candidate | open `#/review` (redirects to `#/review/queue/q-12/c-0343`) or nav rail *Review* | — |
| other-channels popover | review-1b-other-channels | click *Other channels* (button turns blue/primary while open); Escape / × / outside click closes | `?pop=other-channels` |
| queue-rail open | review-3-queue-open | click the left rail toggle icon (top of the collapsed rail); `\` toggles both rails | `?rail=queue` (`?rail=both` for both) |
| evidence-rail open | review-4-evidence-open | click the right rail toggle icon | `?rail=evidence` |
| seed-promoted | review-6-seed-promoted | press **S** or click the *seed* verdict card on an unjudged item | `?state=promoted` (renders c-0343 as promoted to E-0217 without a keypress) |
| blind | review-5-blind-verification | open any item of a blind queue (q-18, q-19) or toggle blind on for the active queue | — (see review.blind) |
| verdict-given | not drawn | press I / N / A / U (or a class key) with auto-advance off — status pill shows the verdict, *previous* line updates | — |
| auto-advanced | not drawn | same with auto-advance on — after ~350 ms navigates to the next unjudged item id | — |
| shortcuts popover | not drawn | toolbar *Shortcuts* button | `?pop=shortcuts` |
| queue-picker popover | not drawn | toolbar queue chip (chevron) | `?pop=queues` |
| blind-toggle popover | not drawn | toolbar *machine opinion visible* chip | `?pop=blind` |
| queue-empty | not drawn | judge the last item, or open a queue with 0 left | `?state=empty` |
| edit-span hand-off | → explore.span-edit | *Edit span in Explore* or **E** | navigates to `#/explore/span-edit/<spanId>?from=review&queue=q-12&item=c-0343` (explore inventory owns that page; it returns here) |

### Regions (1440 × 900, frame 1; review frames are drawn at 1400 wide, so ×1.03)

Top → bottom, left → right. Page fits 900 px without scrolling when both rails are collapsed.

1. **Nav rail** (64 px, shared shell). *Review* active. Foot `Jobs · 3`, `Settings`.
2. **Header** (≈44 px, shared): `Review` | `Inspector` · subtitle mono `queue r-0412 · mp_drops_v3` ·
   search pill `Search spans, runs, families  Ctrl K` · chip `● 3 need you` (blue) · chip `🔒 M4 held out` ·
   plus the `demo data` chip.
3. **Queue toolbar** (full width right of nav, ≈52 px, white band with bottom border):
   left → right: queue chip (blue tint, source icon, `queue Discovery · r-0412 mp_drops_v3 ▾`);
   chip `👁 machine opinion visible (i)`; chip `🗄 writes adjudications`; spacer; progress block
   `342 / 1,284` with `~1.9 s each` right-aligned above a ≈165 px blue ProgressBar (26.6 %); vertical
   divider; Toggle `auto-advance` (on, green); button `⌨ Shortcuts`.
4. **Body row** (remaining ≈790 px), three columns:
   - **Left queue rail, collapsed** (≈56 px): square rail-toggle icon button; `942` bold over `left`;
     a vertical stack of 20 sparkline thumbnails (≈36 × 30, 6 px gap), the first two dimmed with a
     verdict dot top-right (green = interesting), the third (current, c-0343) with a 2 px blue outline;
     a purple vertical bracket on the left edge spans items belonging to a cluster (seen in frame 2).
   - **Main column** (≈1264 px incl. 14 px gutters), stacked cards with 12 px gaps:
     a. **Title row** (≈36 px): `c-0343` (22 px bold) + Badge-like chip `detection` (blue tint);
        right-aligned pills: `● status unadjudicated` · `◎ score 0.84 · 6.1× null` ·
        `● family F-03 d 0.19` (family-affinity dot) · `● artifact likelihood low` (green value).
        Under it, mono meta line: `M2_aug fs1 · CH4_A2 · 192.371 → 192.381 h · 35.0 s · run r-0412 · rank 37 of 1,284 by score`.
     b. **Card "Candidate in context"** (full width, ≈250 px): header row title + muted `padding` +
        Seg `±30 s | ±120 s | ±300 s` (±120 selected); right: buttons `▤ Other channels`,
        `✎ Edit span in Explore`. Plot fills the rest (Trace, see Plots).
     c. **Row, two cards side by side** (≈190 px tall, 50 / 50):
        - left **"Shape vs F-03 medoid · mV"** with legend top-right `— candidate` (blue) `— F-03 medoid` (family colour).
        - right **"Nearest families (i)"** with muted right caption `shape distance, 0 → 1`; three rows
          (≈40 px each, first row tinted): medoid sparkline (≈56 × 30) · id bold + name muted under it
          (`F-03` / `sharkfin`) · `112 members` muted · DistanceBar (≈245 px) with dot at d · `d 0.19` right.
          Rows: F-03 sharkfin 112 members d 0.19; F-11 burst 17 members d 0.37; F-07 slow-drift 212 members d 0.52.
          Footer link `Open F-03 in Library →`.
     d. **Card "Verdict"** (≈110 px): header `Verdict` + `‹` `›` icon buttons + muted
        `previous  c-0342 · interesting · 4 s ago`; right keycap `Ctrl Z` + `undo`.
        Six equal VerdictCards in a row (≈186 × 52 each): `[S] seed` / caption `promotes to Library` (green);
        `[I] interesting`; `[N] not interesting`; `[A] artifact` / caption `kept out of training`;
        `[U] unsure`; `[Space] skip` / caption `no write`.
        (Frames 3 and 4, narrower main column, drop the captions — responsive: hide captions under ≈150 px card width.)
     e. **Card "Annotate"** (≈105 px): header `Annotate` + muted `optional`; right `(i) a class implies interesting, unless the class is non-informative`.
        Row `class`: key chips `[1] spike-train` `[2] burst` `[3] slow-drift` `[4] plateau` `[9] electrode artifact`.
        Row `tags`: tag chips `spike-train` (selected, blue tint) `regular` `decaying` `+ tag` (dashed);
        divider; `note` + full-width Text `Add a note…`.
   - **Right evidence rail, collapsed** (≈56 px): rail-toggle icon; MicroStat stack, value bold over
     muted label: `0.84` score · `6.1×` × null · `0.19` F-03 d · `low` artifact (green) · `0` history.

**review-1b (other-channels popover).** Anchored below *Other channels*, right-aligned to the
context card, overlapping the context card and the Nearest families card (≈585 × 380). Header
`Other channels` + muted `same 192.338 → 192.405 h` + ×. Six rows (≈38 px): channel name (mono,
≈60 px) · mini trace with the span band (light blue) · `r 0.06` right. Current channel row
(`CH4_A2`) tinted blue, dark trace, right label `this channel` (frame clips it to "this chann" —
bug, do not reproduce). Rows: CH1_A1 r 0.06 · CH2_A1 r 0.11 · CH3_A2 r 0.04 · CH4_A2 this channel ·
CH5_B1 r 0.09 · CH6_B1 r 0.02. Divider, then `artifact likelihood` + green chip `low · 0.12` + (i)
+ right muted `not blinded in any queue`; line `coherence in span 0.08 (flag ≥ 0.5)  clipping none
step change none  electrode flag none`; link `Open all channels in Explore →`.

**review-3 (queue rail open).** Left rail expands to ≈352 px (main column shrinks; title pills
shorten `artifact likelihood low` → `artifact low`, meta line drops `by score`, verdict captions hidden).
Rail content top → bottom:
- header: rail-toggle icon + `Queues` (bold) + right link `+ New queue`.
- five queue rows (≈46 px, selected row blue tint + blue border): icon · title bold · mono subtitle · right count (bold), blind badge under count where blind:
  `Discovery · r-0412` / `mp_drops_v3 · 3 channels · adjudications` / `942` ·
  `Seed search · r-0415` / `exemplar E-0102 · clustered · adjudications` / `57` ·
  `Explore spans` / `taken for Review · annotations` / `12` ·
  `Training windows` / `cnn_windows_v3 · binary · cap 20,000` / `18,400` + `blind` ·
  `Model verification` / `cnn_windows_v3 · manual · test sample` / `7 / 40` + `blind`.
- `Filters` + muted `Discovery · r-0412` + right link `Reset`.
  Two Selects side by side: `run` = `r-0412 mp_drops_v3`; `method` = `all methods`.
  `channel` chip toggles `CH1_A1` (off, grey) `CH4_A2` (on, blue) `CH6_B1` (on, blue).
  `score` RangeSlider with value `0.62 – 1.00` right.
  `status` Seg `unjudged | judged | all` (unjudged selected).
  `group` Seg `none | sequence | family` (sequence selected) + (i).
- divider; `Up next` + muted `sorted by score` + right `942 left`. List rows (≈38 px): sparkline ·
  id bold · channel muted · score right · verdict dot for judged:
  `c-0342 CH4_A2 0.86 ●green` (dimmed) · `c-0343 CH4_A2 0.84` (selected, blue border) ·
  group header (purple tint, chevron) `Cluster 13  sequence · 3 within 6 min · CH4_A2` ·
  indented with purple left bar `c-0350 CH4_A2 0.83` · `c-0351 CH4_A2 0.83` · `c-0352 CH4_A2 0.82`.

**review-4 (evidence rail open).** Right rail expands to ≈352 px, scrolls internally. Header
`Evidence` + mono muted `c-0343 · d-88213` + rail-toggle icon. Sections (icon + bold title, KeyValue
rows label-left muted / value-right):
- **Origin** — `run` chip `template` + `r-0412`; `template  mp_drops_v3 · v3`; stage strip chips
  `Source › Bandpass › Matrix profile › Threshold`; `recipe hash  a91f…3c0e`; `ran  12 Sep 2026 · this installation`;
  `scope  M2_aug fs1 · 3 channels · 721 h`; link `Open run in Discovery →`.
- **Detection** — `score 0.84`; `threshold 0.62 · recommended 0.62`; `rank 37 of 1,284`;
  `null expects 210 on scope · run 6.1×`; `samples 51,726 → 51,761 · fs 1 Hz` (see Fog F3).
- **Also found by** — `r-0415 seed search` + chip `seed` + `match d 2.9`; `human annotations none overlapping`;
  `prior adjudication none · not a rediscovery`.
- **Family** + muted right `nearest by shape, not a verdict` — sparkline + `F-03 · sharkfin` /
  `d 0.19 · 112 members · medoid m-1846`.
- **Artifact likelihood** + muted right `not blinded` — `likelihood` green chip `low · 0.12`;
  `cross-channel coherence 0.08 · flag ≥ 0.5`; `clipping · step change none · none`.
- **History** — `span revisions none`; `verdicts none`; `in queues Discovery r-0412 · Seed r-0415`.
- footer box (grey, db icon): `Writes one adjudication row on d-88213.`

**review-6 (seed promoted).** Differences from frame 1: progress `343 / 1,284`; left rail `941 left`,
two green dots; auto-advance switch shows off (paused); title gains green chip `exemplar E-0217`;
status pill `● status seed · promoted` (green dot); history micro-stat `1`; the *seed* VerdictCard
is selected (green fill + green border). **The right card of row c is replaced by the promotion panel**
(green 2 px border, same size): header lib icon + `Promoted to Library` + green chip `exemplar E-0217` +
muted right `seed verdict · just now`; row `family` with a radio Seg: `● F-03 sharkfin · nearest, d 0.19`
(selected, blue) · `○ new family` · `○ no family yet`; link-icon line `keeps span, recording, channel,
content hash and the run's recipe hash`; amber banner `⏸ auto-advance paused until you confirm · Enter
confirms and moves on`; actions: `↶ Undo promotion` + keycap `Ctrl Z` (left), link `Open in Library`,
primary `✓ Confirm and next` (right).

### Controls & interactions

Keyboard map (active on the inspector and the cluster page; **suppressed while focus is in a text
input** — tag input, note, cluster job id; Escape blurs the input first). Source: frames, §10.3,
§10.4, §10.5, Settings › Keyboard & behaviour frame 16, Settings › Review queues frame 8.

| key | action | notes |
|---|---|---|
| **S** | verdict seed → promotes to Library (P21) | enters `seed-promoted`; auto-advance pauses |
| **I** | verdict interesting | |
| **N** | verdict not interesting | |
| **A** | verdict artifact (kept out of training) | |
| **U** | verdict unsure | |
| **Space** | skip, no write | moves to next item regardless of auto-advance; `preventDefault` so the page does not scroll |
| **1** / **2** / **3** / **4** | class spike-train / burst / slow-drift / plateau | implies `interesting` if no verdict yet (writes both) |
| **9** | class electrode artifact (non-informative) | implies `artifact` verdict |
| **Ctrl Z** | undo last write (verdict, class, promotion) | cluster-aware: one press reverses a whole batch; on `seed-promoted` removes exemplar and verdict |
| **Ctrl Shift Z** | redo | shown in frame 7 banner |
| **Enter** | confirm promotion and next | only in `seed-promoted` (otherwise no-op) |
| **→** / **←** | next / previous item in the queue | Settings 16 "next · previous candidate" |
| **E** | open in Explore (= *Edit span in Explore*) | not available in blind window queues (no *Edit span* button in frame 5) |
| **\\** | toggle both rails | opens both if either is closed, else closes both |
| **Ctrl K** | focus header search | shared shell |
| **Escape** | close open popover / modal | |

Toolbar:
- **queue chip** `queue Discovery · r-0412 mp_drops_v3 ▾` — Popover (`?pop=queues`) listing the five
  queues (same rows as the queue rail); click → navigate `#/review/queue/<id>` (redirects to that queue's
  current item). Footer link `Open in Jobs →` → `#/jobs?filter=queues`.
- **machine opinion visible (i)** chip — Popover (`?pop=blind`): InfoTip text "blind hides score,
  family affinity and model calls until the verdict · artifact likelihood is never hidden" + Toggle
  `blind for this queue` + caption "stored with every verdict from now on; earlier verdicts keep the
  state they were given under". Toggling is an in-memory write on the queue (`recordDemoWrite('review',
  'queue.blind', …)`) and immediately re-renders the page in the blind state.
- **writes adjudications** chip — InfoTip only: "each verdict writes one adjudication row on the
  detection (§4.1); Explore spans write annotations; windows write window verdicts (B15)".
- **progress** — read-only ProgressBar; recalculates after every write/undo.
- **auto-advance** Toggle — in-memory personal preference (`review.autoAdvance`, default on). While a
  promotion or undone batch is pending it renders off-looking with the amber "paused" note but the
  stored preference is not changed (see Conflicts C6).
- **Shortcuts** button — Popover (`?pop=shortcuts`) with the key table above (two columns: action,
  keycaps) and link `Change keys in Settings › Keyboard & behaviour →` → `#/settings/keyboard`
  (settings inventory owns the exact route).

Rails:
- **rail toggle icons** (left and right) — open/close the rail, write `?rail=` with `setQuery(…, true)`.
- **collapsed rail thumbnails** — click → navigate to that item id. Hover → tooltip `c-0344 · CH4_A2 · 0.84`.
- **micro-stats** (collapsed evidence rail) — click any → opens the evidence rail scrolled to that section.

Queue rail (open):
- **+ New queue** — Popover (no frame): "Queues are made where the items come from" with four links:
  `Discovery › Send N unjudged to Review` → `#/discovery/runs`; `Explore › Take span for Review` →
  `#/explore/corpus`; `Analyse training › Send unseen windows` → `#/analyse/training`;
  `Models › Registry verification sample` → `#/models/registry`. (Routes owned by those inventories.)
- **queue rows** — click → navigate to that queue.
- **run** Select — options: runs feeding this queue (fixture: `r-0412 mp_drops_v3` only). Disabled for
  single-run queues? No — shown enabled with one option (frame).
- **method** Select — `all methods` · `matrix profile` · `threshold` (fixture); filters up-next.
- **channel** chip toggles — CH1_A1 / CH4_A2 / CH6_B1 (the queue's 3 channels); at least one must stay
  on: clicking the last active chip shakes it and shows DisabledReason tooltip `at least one channel`.
- **score** RangeSlider — 0.00–1.00 step 0.01, default `0.62 – 1.00` (lower bound = run threshold);
  the handles cannot cross (min gap 0.01). In blind queues: disabled, DisabledReason `score is hidden in a blind queue`.
- **status** Seg — unjudged / judged / all; filters up-next; `judged` shows items with verdict dots.
- **group** Seg — none / sequence / family; `sequence` collapses sequence clusters into group rows
  (frame), `family` groups by nearest family id with a family-colour header. (i) InfoTip: "a sequence is
  detections from one run and channel within 6 min, at least 2 events (Settings › Review queues)".
- **Reset** — restores the queue's default filters.
- **Up next rows** — click → navigate to item; **cluster group header** chevron → collapse/expand;
  clicking the header label → navigate `#/review/queue/q-12/cluster/13`.
- **Filter result empty** — EmptyState in up-next: `No items match these filters` + `Reset filters`.

Main column:
- **padding Seg** `±30 s | ±120 s | ±300 s` — changes the context x-domain; personal default ±120 s
  (Settings › Display); in-memory, persists across items; `?pad=30|120|300`.
- **Other channels** — toggles the popover (button shows pressed/blue while open).
  In the popover: rows are not clickable except hover highlight; `Open all channels in Explore →` →
  `#/explore/cross-channel/<channelId>?h=192.338-192.405` (explore inventory owns route); × closes.
- **Edit span in Explore** — navigate to explore.span-edit with return params (above). Hidden for
  window units (frame 5) and cluster pages keep it for the shown member.
- **Nearest families (i)** — InfoTip: "Distance is shape only, 0 → 1; a longer bar is farther. Low
  distance is not a verdict." Family row click → selects that family as the medoid overlay in the shape
  plot (title changes to `Shape vs F-11 medoid · mV`) — in-memory view state.
- **Open F-03 in Library →** — navigate `#/library/family/F-03` (library inventory owns route).
- **Verdict ‹ ›** — step the *previous* line back/forward through this session's prior verdicts
  (`previous c-0342 · interesting · 4 s ago`); clicking the text navigates to that item (re-judging it
  writes a new verdict, the old one stays in History — see Fog F14). `‹` disabled with reason
  `no earlier verdict this session` at the start.
- **Ctrl Z undo** keycap — clickable; same as the shortcut. Disabled (muted) with tooltip `nothing to undo` when the stack is empty.
- **VerdictCards** S / I / N / A / U / Space — click = the key. In-memory write:
  `recordDemoWrite('review', 'verdict', { queue, item, verdict, blind: queue.blind, class?, tags, note })`;
  the item's status becomes the verdict; progress +1, left −1; the verdict card flashes selected (≈300 ms)
  for non-seed verdicts; *previous* line becomes this item; auto-advance → next unjudged id.
  Space: no write, next item, *previous* line unchanged.
- **class key chips** 1–4, 9 — toggle one class (single select; clicking the selected chip clears it).
  If no verdict yet: class 1–4 also writes `interesting`, class 9 writes `artifact`, and the implied
  verdict card shows selected; a Toast confirms `class burst · implies interesting`. If a verdict exists,
  class is written onto that verdict without changing it — except class 9 on a non-artifact verdict,
  which shows Toast `electrode artifact is non-informative — verdict changed to artifact (Ctrl Z reverts)`.
- **tag chips** — toggle on/off (multi). **+ tag** — turns into an inline Text input; Enter adds
  (validation: 1–32 chars, lowercase letters, digits and `-`, not a duplicate; message under input
  `tags are lowercase words joined by -`); Escape cancels. Suggestions from morphology tags
  (sharkfin, biphasic, plateau-top, ramp, notched, spike-doublet).
- **note** — Text, max 500 chars (counter appears past 400); saved on blur into the pending write for
  this item (in-memory).

Seed-promoted panel:
- **family radio Seg** — `F-03 sharkfin · nearest, d 0.19` (default because d ≤ 0.30, Settings 8) ·
  `new family` (reveals a Text `family name` with placeholder `F-12 · name`; validation: required,
  2–40 chars) · `no family yet`. If nearest d > 0.30, default is `no family yet` and the nearest option
  reads `F-xx · nearest, d 0.xx · above 0.30`.
- **Undo promotion** / Ctrl Z — removes exemplar E-0217 and the seed verdict; item back to
  unadjudicated; progress −1; panel closes, Nearest families card returns; Toast `promotion undone · exemplar E-0217 removed`.
- **Open in Library** — navigate `#/library/family/F-03?exemplar=E-0217` (or `#/library/atlas` when `no family yet`).
- **Confirm and next** / Enter — writes the family choice in memory
  (`recordDemoWrite('library', 'exemplar', { id:'E-0217', family, span, recording, channel, contentHash, recipeHash })`),
  closes the panel, resumes auto-advance, navigates to the next unjudged item. Exemplar ids count up
  from E-0217 in memory.

Disabled states and reasons:
- *Edit span in Explore* absent (not disabled) for window units.
- *Confirm and next* disabled while `new family` is chosen with an invalid name: `name the new family`.
- Verdict keys while the promotion panel is open: pressing another verdict key shows Toast
  `confirm or undo the promotion first (Enter / Ctrl Z)` and does nothing.
- M4_aug: no M4 item can appear in any queue (held out, D6) — nothing to render, but the fixture must not contain one.

### Plots

| plot | type | axes / units | marks | legend | cap | fixture |
|---|---|---|---|---|---|---|
| Candidate in context | Trace (d3 line in SVG) | x: hours since recording start, 5 ticks, 3 decimals (`192.338 h … 192.405 h` at ±120 s); y: mV, ticks `+0.4 / 0.0 / −0.4`, label `mV` bottom-left | black 1 px line; light-blue span band from 192.371 to 192.381 h with 1 px blue edges; label `c-0343 · 35.0 s` in blue **above the plot area, off the trace** (backlog: labels moved off traces); dashed zero gridline | none | 1 Hz: 35 + 2·pad samples (≤ 635) — no decimation needed | `candidate.trace(pad)`: `syntheticTrace({ n, seed: hash(itemId), noise 0.02, events: [{ at: pad, depth: 0.35, width: 35, shape: 'sharkfin' }] })`, y domain fixed ±0.45 mV |
| Shape vs F-03 medoid · mV | two-line overlay | x: `0 s` → `35 s` (candidate duration); y: mV `+0.4 mV / 0 / −0.4 mV` | candidate blue 2 px; medoid in family colour 2 px; **never normalised (D5)** | top-right `— candidate  — F-03 medoid` | — | candidate span slice + `families['F-03'].medoidTrace` resampled to the candidate length (Fog F6) |
| Nearest families sparklines | Sparkline | none (shared mV y within each family) | 1.5 px line in family colour | — | 3 rows | family medoid traces |
| Nearest families distance | DistanceBar | 0 → 1 | grey track, family-colour fill to d, dot at d | caption `shape distance, 0 → 1` | 3 | `nearest[]` |
| Collapsed queue rail | Sparkline thumbnails | none | 1 px dark line; dimmed at 45 % opacity when judged; verdict dot 6 px | — | as many as fit (20 at 900 px) | queue items |
| Up next | Sparkline in list rows | none | as above | — | virtualised list; fixture 942 left but only ~40 rows generated, then `… 902 more` | queue items |
| Other channels (popover) | small-multiples Trace stack | shared x = context domain; no y ticks, shared mV scale across channels | grey 1 px lines, current channel dark; span band per row | right `r 0.06` | 6 per view in the frame; paged at ≤ 10 (P8) for 16 channels (Fog F7) | `otherChannels(recording, itemId)` synthetic, seed per channel |
| Evidence › Family | Sparkline | none | family colour | — | 1 | medoid |

Colours: family colours from `FAMILY_COLOURS` (D8): F-03 `#30B0C7`, F-11 `#C97B63`, F-07 `#7A8FA6` — not
the purple/red/teal the frames still draw (Conflict C3). Candidate line and span band: blue (machine origin).

### Fixtures (TypeScript sketch)

Shared canon (extend `fixtures/canon.ts`, do not re-type): `RECORDINGS`, `CLASSES`, `VERDICTS`,
`FAMILIES` / `FAMILY_COLOURS`, `REVIEW_QUEUES`, `WINDOW_SET`, `MODELS`, `ACTOR`, `MORPHOLOGY_TAGS`.
Review-local fixtures live in `fixtures/review.ts`.

```ts
// shared canon — REVIEW_QUEUES needs extending (today it lacks counts, pace, writes, order, and the Explore spans queue)
type QueueSource = 'discovery-run' | 'seed-search' | 'explore-spans' | 'training-windows' | 'model-verification' | 'library-family'
interface ReviewQueue {
  id: 'q-12' | 'q-15' | 'q-16' | 'q-18' | 'q-19'
  source: QueueSource
  title: string            // 'Discovery · r-0412'
  subtitle: string         // 'mp_drops_v3 · 3 channels · adjudications'
  toolbarLabel: string     // 'Discovery · r-0412 mp_drops_v3'
  runId?: string; template?: string; exemplar?: string; model?: string
  unit: 'detection' | 'human span' | 'window'
  blind: boolean
  verdictKeys: 'full' | 'binary+classes' | 'full+classes'   // Settings › Review queues
  writes: 'adjudications' | 'annotations' | 'window verdicts'
  order: 'score, high first' | 'distance, near first' | 'time' | 'stratified by channel' | 'stratified by class'
  total: number; judged: number; paceS: number | null; cap?: number
  channels?: string[]
}
const QUEUES: ReviewQueue[] = [
  { id: 'q-12', source: 'discovery-run', title: 'Discovery · r-0412', subtitle: 'mp_drops_v3 · 3 channels · adjudications', toolbarLabel: 'Discovery · r-0412 mp_drops_v3', runId: 'r-0412', template: 'mp_drops_v3', unit: 'detection', blind: false, verdictKeys: 'full', writes: 'adjudications', order: 'score, high first', total: 1284, judged: 342, paceS: 1.9, channels: ['CH1_A1', 'CH4_A2', 'CH6_B1'] },
  { id: 'q-15', source: 'seed-search', title: 'Seed search · r-0415', subtitle: 'exemplar E-0102 · clustered · adjudications', toolbarLabel: 'Seed search · r-0415 E-0102', runId: 'r-0415', exemplar: 'E-0102', unit: 'detection', blind: false, verdictKeys: 'full', writes: 'adjudications', order: 'distance, near first', total: 118, judged: 61, paceS: 3.4 },
  { id: 'q-16' /* NOT in §0 canon — Fog F1 */, source: 'explore-spans', title: 'Explore spans', subtitle: 'taken for Review · annotations', toolbarLabel: 'Explore spans', unit: 'human span', blind: false, verdictKeys: 'full', writes: 'annotations', order: 'time', total: 12, judged: 0, paceS: null },
  { id: 'q-18', source: 'training-windows', title: 'Training windows', subtitle: 'cnn_windows_v3 · binary · cap 20,000', toolbarLabel: 'Training windows · cnn_windows_v3', template: 'cnn_windows_v3', unit: 'window', blind: true, verdictKeys: 'binary+classes', writes: 'window verdicts', order: 'stratified by channel', total: 20000, judged: 1600, paceS: 6, cap: 20000 },
  { id: 'q-19', source: 'model-verification', title: 'Model verification', subtitle: 'cnn_windows_v3 · manual · test sample', toolbarLabel: 'Model verification · cnn_windows_v3 · manual', model: 'cnn_windows_v3 · manual', unit: 'window', blind: true, verdictKeys: 'full+classes', writes: 'window verdicts', order: 'stratified by class', total: 40, judged: 33, paceS: 6 },
]

type Verdict = 'seed' | 'interesting' | 'not_interesting' | 'artifact' | 'unsure'
interface ReviewCandidate {
  id: string                    // 'c-0343'
  detectionId: string           // 'd-88213'
  queueId: 'q-12'
  recording: 'M2_aug fs1'; channel: 'CH4_A2'
  startH: 192.371; endH: 192.381; durationS: 35.0
  runId: 'r-0412'; rank: 37; rankOf: 1284
  score: 0.84; xNull: 6.1
  status: 'unadjudicated' | Verdict
  exemplarId?: string           // set on seed: 'E-0217'
  family: { id: 'F-03'; d: 0.19 }
  nearest: { id: string; name: string; members: number; d: number }[]
    // [{F-03,'sharkfin',112,0.19},{F-11,'burst',17,0.37},{F-07,'slow-drift',212,0.52}]
  artifact: { level: 'low' | 'medium' | 'high'; p: 0.12; coherence: 0.08; coherenceFlag: 0.5; clipping: 'none'; stepChange: 'none'; electrodeFlag: 'none' }
  origin: { template: 'mp_drops_v3'; version: 'v3'; stages: ['Source', 'Bandpass', 'Matrix profile', 'Threshold']; recipeHash: 'a91f…3c0e'; ran: '12 Sep 2026'; by: 'this installation'; scope: 'M2_aug fs1 · 3 channels · 721 h' }
  detection: { threshold: 0.62; recommended: 0.62; nullExpects: 210; samples: [number, number]; fsHz: 1 }
  alsoFoundBy: { runs: { run: 'r-0415'; kind: 'seed search'; badge: 'seed'; matchD: 2.9 }[]; humanOverlap: null; priorAdjudication: null }
  history: { revisions: []; verdicts: { verdict: Verdict; at: string; blind: boolean }[]; queues: ['Discovery r-0412', 'Seed r-0415'] }
  tags: ['spike-train']; className?: string; note: ''
  clusterNo?: number            // c-0350..c-0352 → 13
}
// q-12 item list: c-0001 … c-1284 generated lazily; hand-written neighbours:
//   c-0341 interesting (judged), c-0342 interesting (judged, 'previous … 4 s ago'), c-0343 current (above),
//   c-0344 … c-0349 unjudged scores 0.84 → 0.83, Cluster 13 (sequence · 3 within 6 min · CH4_A2): c-0350 0.83, c-0351 0.83, c-0352 0.82
// Up next order: score high first. Only ~40 rows are materialised; counts come from queue.total/judged.

interface SessionWrite {         // in-memory undo stack entry (kit/store.ts key 'review.writes')
  id: number; queueId: string; items: string[]   // >1 item = batch
  verdict?: Verdict; className?: string; tags?: string[]; note?: string
  blind: boolean; exemplarId?: string; family?: string | 'new' | null
  at: number; undone: boolean
}
```

Shared with other workspaces: recordings/channels (canon), families F-03/F-07/F-11 (Library),
classes (Settings › Vocabulary), queues q-12…q-19 (Jobs, Discovery send-to-Review, Models registry
q-19), runs r-0412/r-0415 (Discovery), template mp_drops_v3 (Discovery/Library templates), exemplar
E-0102 (Library, Discovery seed), medoid m-1846, model `cnn_windows_v3 · manual` (Models),
window set `ws_M2aug_3ch_600s` (Library, Models). New ids this page mints: exemplar `E-0217`
(first promotion), detection `d-88213`.

### Copy

- Header: `Review` · `Inspector` · subtitle `queue r-0412 · mp_drops_v3` · search `Search spans, runs, families`.
- Toolbar: `queue`, `Discovery · r-0412 mp_drops_v3`, `machine opinion visible`, `writes`, `adjudications`, `342 / 1,284`, `~1.9 s each`, `auto-advance`, `Shortcuts`.
- Rail: `942` / `left`; micro-stat labels `score`, `× null`, `F-03 d`, `artifact`, `history`.
- Title: `c-0343`, `detection`, `status unadjudicated`, `score 0.84 · 6.1× null`, `family F-03 d 0.19`, `artifact likelihood low`.
- Meta: `M2_aug fs1 · CH4_A2 · 192.371 → 192.381 h · 35.0 s · run r-0412 · rank 37 of 1,284 by score`.
- Cards: `Candidate in context`, `padding`, `±30 s`, `±120 s`, `±300 s`, `Other channels`, `Edit span in Explore`; `Shape vs F-03 medoid · mV` (frame text reads "F03" in one place — use `F-03`), `candidate`, `F-03 medoid`; `Nearest families`, `shape distance, 0 → 1`, `112 members`, `d 0.19`, `Open F-03 in Library →`.
- Verdict: `Verdict`, `previous`, `c-0342 · interesting · 4 s ago`, `undo`, `seed`, `promotes to Library`, `interesting`, `not interesting`, `artifact`, `kept out of training`, `unsure`, `skip`, `no write`.
- Annotate: `Annotate`, `optional`, `a class implies interesting, unless the class is non-informative`, `class`, `spike-train`, `burst`, `slow-drift`, `plateau`, `electrode artifact`, `tags`, `regular`, `decaying`, `+ tag`, `note`, `Add a note…`.
- Other channels: `Other channels`, `same 192.338 → 192.405 h`, `this channel`, `artifact likelihood`, `low · 0.12`, `not blinded in any queue`, `coherence in span 0.08 (flag ≥ 0.5)`, `clipping none`, `step change none`, `electrode flag none`, `Open all channels in Explore →`.
- Queue rail: `Queues`, `New queue`, `Filters`, `Reset`, `run`, `method`, `all methods`, `channel`, `score`, `0.62 – 1.00`, `status`, `unjudged`, `judged`, `all`, `group`, `none`, `sequence`, `family`, `Up next`, `sorted by score`, `942 left`, `Cluster 13`, `sequence · 3 within 6 min · CH4_A2`, `blind`.
- Evidence: section titles `Origin`, `Detection`, `Also found by`, `Family`, `Artifact likelihood`, `History`; `nearest by shape, not a verdict`, `not blinded`, `Open run in Discovery →`, `none · not a rediscovery`, `Writes one adjudication row on d-88213.`
- Promotion: `Promoted to Library`, `exemplar E-0217`, `seed verdict · just now`, `family`, `F-03 sharkfin · nearest, d 0.19`, `new family`, `no family yet`, `keeps span, recording, channel, content hash and the run's recipe hash`, `auto-advance paused until you confirm · Enter confirms and moves on`, `Undo promotion`, `Open in Library`, `Confirm and next`, status `seed · promoted`.
- Empty queue (not drawn): EmptyState title `Queue r-0412 is done` · body `1,284 of 1,284 judged · return to Discovery to refresh the run's score` · actions `Open run in Discovery →`, `Pick another queue`.

### Live vs demo

Not applicable (Review is demo-only tonight). Constraints from the existing client: `App.tsx` routes
`review` to the `Inert` placeholder — replace that branch; the NavRail *Review* item navigates to
`#/review` with no page segment, so `#/review` must redirect to `#/review/queue/q-12/c-0343` (use
`history.replaceState` so Back does not loop). The shell's live bridge poll (`listRuns` every 5 s,
feeding `Jobs · N` and `N need you`) must keep running on Review routes. The Explore span-edit
hand-off must carry `from=review` so explore.span-edit can return.

### Frame ⟷ spec conflicts (review.inspector)

- **C1 — Shape panel units.** §10.2 says "z-normalised over the nearest family's medoid, with σ axis";
  frames 1–6 draw mV. **Use mV** (D5 resolved 14 Sep, §3 "never normalised", backlog B27).
- **C2 — "F03" vs "F-03".** Plot title text in the PDF is "Shape vs F03 medoid"; the image shows
  `F-03`. Use `F-03`.
- **C3 — Family colours.** Frames draw F-03 purple, F-11 red, F-07 teal (backlog line 201: "Review needs a
  second pass"). **Use the D8 canon palette** (`FAMILY_COLOURS`). The title-row `family` pill dot should also
  be F-03's colour, not purple. Contrast note: F-03 `#30B0C7` beside the blue candidate line is close —
  keep line widths/dash distinct if needed.
- **C4 — F-07 name.** Frames: `slow-drift`; §0 canon: `slow drift` (the class is `slow-drift`). Use canon
  `slow drift` for the family name.
- **C5 — Evidence stage names.** Evidence strip `Source › Bandpass › Matrix profile › Threshold`; Jobs
  frames name the same template's stages `Bandpass filter`, `Threshold to spans` (Blocks registry, backlog
  "stage names match the Blocks registry"). Recommend the registry names everywhere; in the narrow rail
  the chips may abbreviate with the full name in a tooltip.
- **C6 — Auto-advance switch during a pause.** §10.4 "auto-advance pauses until Enter confirms"; frames 6
  and 7 draw the switch **off**. Recommend: render off-looking plus the amber paused note, but do not
  change the stored preference; it resumes on confirm / next.
- **C7 — Seed verdict colour.** Frame 6 draws seed selection green (human origin, §3); `canon.ts` `VERDICTS.seed`
  is blue. Recommend green for seed-promoted UI in Review (human verdict), flag `canon.ts` to the canon owner.
- **C8 — Collapsed-rail dots.** Frame 1 draws the two judged thumbnails with green then grey dots, but the
  *previous* line says c-0342 was interesting (green). Drive dots from the verdict data (both green, as frames 6/7).

### Fog (review.inspector)

- **F1** — The Explore spans queue has no id in §0 (only q-12, q-15, q-18, q-19). Proposed `q-16`. Jobs
  frame 1 lists 4 queues "· 1 idle" and omits it; which queue is "idle" is undefined.
- **F2** — `rank 37 of 1,284 by score` while 342 items are judged in a queue ordered by score (the current
  item would be rank 343). Keep the copy; flag to the canon owner.
- **F3** — `samples 51,726 → 51,761 · fs 1 Hz` does not match 192.371 h at 1 Hz (≈ 692,536 → 692,571).
  Recommend deriving samples from hours in the fixture (`Math.round(h·3600·fs)`), which changes the frame text.
- **F4** — `match d 2.9` for the seed-search match is off the 0 → 1 distance scale used everywhere else.
  Either a different metric (unnamed) or a typo; show as-is with an InfoTip "seed-search distance (not the 0 → 1 shape distance)".
- **F5** — Artifact likelihood `low · 0.12`: the level thresholds (low/medium/high) are in Settings ›
  Analysis defaults (artifact likelihood), not drawn in this group; fixture uses low < 0.33 ≤ medium < 0.66 ≤ high.
- **F6** — Candidate (35 s) is overlaid on F-03's medoid (~21 s per §0) on a 0–35 s axis; alignment and
  resampling are not specified. Shell: stretch the medoid to the candidate length and note it in the (i).
- **F7** — Other channels shows 6 of the recording's 16 channels with no pager; which 6 (neighbours? the
  run's scope?) and paging are unspecified. Shell: page 6 at a time with `‹ 1–6 of 16 ›` (P8 cap ~10).
- **F8** — Coherence `r` per channel "in the span" — method (correlation? coherence band?) undefined; fixture numbers only.
- **F9** — `method` filter options for a single-template run are undefined.
- **F10** — Re-judging an already-judged item (via ‹ › or the rail) — does it write a second adjudication
  or replace? §4.1/§4.7 imply append; shell appends and shows both in History.
- **F11** — *New queue* has no designed flow; the popover of hand-off links is a proposal.
- **F12** — Explore spans queue (unit human span, writes annotations): what the pills show (no score, no run) is not drawn.
- **F13** — Global search (Ctrl K) scope for Review is not designed; header uses the existing not-wired toast.
- **F14** — `‹ ›` beside *previous* (prior verdicts) and **← →** (next/previous candidate) are two different
  navigations with similar glyphs; confirm the distinction.

---

## review.cluster

A cluster is one item of a queue judged as a batch (§10.5). Same shell, toolbar, rails, verdict row,
annotate card and keymap as review.inspector; the title row, context card title, and the row below
the context (Members strip instead of Shape + Nearest families) differ, and the verdict card gains the
batch line.

### Route & states

| state | frame | reached by | query |
|---|---|---|---|
| batch-ready (default) | review-2-cluster | up-next cluster header / collapsed-rail bracket click, or auto-advance onto a cluster item | `#/review/queue/q-15/cluster/12` (`?member=c-0373` picks the shown member; the fixture default is `c-0373` because the frame shows it — see Fog F17) |
| batch-written | not drawn | press a verdict key with the batch box checked and auto-advance off — all 6 included members take the verdict; `previous  Cluster 12 · 6 × interesting · just now` | — |
| batch-undone | review-7-batch-undone | **Ctrl Z** (or the undo keycap) right after a batch write | `?state=undone` (renders the frame without a keypress) |
| redone | not drawn | *Redo* / **Ctrl Shift Z** in batch-undone — re-applies the 6 verdicts, banner disappears | — |
| include-all | not drawn | *Include all* — c-0377 checked, batch line `Verdict for the 7 included members`, excluded note gone, cohesion pill `mean d 0.27 (7 included) · worst 0.61` | `?include=all` |
| single-member verdict | not drawn | uncheck the batch box, then a verdict key writes only the shown member | — |
| sequence cluster | not drawn (same layout) | `#/review/queue/q-12/cluster/13` — badge `sequence`, members c-0350..c-0352, members strip titled `3 · detections within 6 min on CH4_A2` | — |
| rails / popovers | as frames 3, 4, 1b | as review.inspector | `?rail=`, `?pop=` |

### Regions (frame 2, drawn at 1372 wide → ×1.05)

1. Header subtitle `queue r-0415 · seed search E-0102`.
2. Toolbar: queue chip `queue Seed search · r-0415 E-0102 ▾` (seed-search icon); `machine opinion visible (i)`;
   `writes adjudications`; progress `61 / 118` `~3.4 s each` (51.7 %); auto-advance on; Shortcuts.
3. Left collapsed rail: `57` / `left`; two dimmed thumbnails with green dots; a **purple vertical bracket**
   running down the left edge beside the current thumbnail and the next six (the cluster's 7 members);
   current thumbnail outlined blue.
4. Main column:
   a. **Title row**: `Cluster 12` + chip `cluster` (purple tint) + chip `seed-search matches` (grey);
      pills `● status 7 unadjudicated` · `● cohesion mean d 0.21 (6 included) · worst 0.61` (amber dot, amber values) ·
      `● family F-03 d 0.19` · `● artifact likelihood low`.
      Meta: `M2_aug fs1 · CH4_A2 ×5, CH2_A1 ×2 · run r-0415 seed search, exemplar E-0102 · showing member c-0373`.
   b. **Card "Member in context"** (≈245 px) — identical controls to the candidate card (padding Seg,
      Other channels, Edit span in Explore); x `204.150 h … 204.217 h`; band label `c-0373 · 33.0 s · member 3 of 7`.
   c. **Card "Members"** (≈190 px, full width): header `Members` + muted `7 · seed-search matches of exemplar E-0102 · shared y · mV` + (i);
      right muted `sorted by distance to medoid` + link `Include all`.
      Seven MemberCards in one row (≈158 × 130 each, 8 px gap): Checkbox + id bold; thumbnail trace on grey
      ground (shared mV y); `d 0.12`; status Badge-chip `unadjudicated`. Shown member (c-0373) blue fill + blue
      border. Excluded member c-0377: unchecked, amber border and amber-tinted ground, amber trace, amber
      `d 0.61` + amber `least similar` on the same line.
   d. **Card "Verdict"**: header `Verdict ‹ › previous  cluster 11 · 5 × interesting · 1 min ago`; right
      `Ctrl Z undo · reverses the whole batch`. Six VerdictCards (with captions). Below them the **batch line**:
      Checkbox (checked) `Verdict for the 6 included members` + amber `1 excluded · c-0377 d 0.61, above the 0.45 limit`;
      right muted `auto-advance waits for the whole batch`.
   e. **Card "Annotate"** — as inspector (class chips, tags, note apply to every member written in the batch).
5. Right collapsed rail micro-stats: `0.24` mean d · `0.61` worst d (amber) · `0.19` F-03 d · `low` artifact (green) · `7` members.

**Frame 7 differences (batch-undone).** auto-advance switch off; status pill `↶ status 7 unadjudicated · batch undone`
(blue undo icon, blue value); **no family pill** (frame drops it — see C10); Verdict header reads
`undone  Cluster 12 · 6 × interesting · 2 s ago`; the batch-line row is replaced by a **blue Banner**
(full card width): `↶ Batch undone · 6 verdicts on Cluster 12 reversed in one step · members back to unadjudicated`
then right `⏸ auto-advance paused` (amber) · divider · `↷ Redo` link · keycap `Ctrl Shift Z`.
Member cards all `unadjudicated`; include boxes keep their state.

### Controls & interactions

All review.inspector controls and keys apply. Cluster-specific:

- **MemberCard click** (outside the checkbox) — shows that member in the context card (`?member=` via
  `setQuery(…, true)`); meta line `showing member c-0371`; band label `… member 1 of 7`. **← / →** step the
  shown member inside the cluster first, then leave the cluster at either end.
- **Member include Checkbox** — toggles inclusion; recalculates the batch count, excluded note and cohesion
  pill (mean over included, worst over all). Checking a member whose d > 0.45 is allowed (it is the override)
  and keeps its amber flag. At least one member must stay included: unchecking the last shows DisabledReason
  `a batch needs at least one member`.
- **Include all** — checks every member; link turns into `Exclude flagged` (restores the default exclusion).
- **Members (i)** — InfoTip: "Shapes on one shared mV scale. A member farther than 0.45 from the medoid is
  excluded from the batch by default (Settings › Review queues)."
- **Members pager** (not drawn: 7 < 10) — when a cluster has > 10 members show 10 per page with
  `‹ 1–10 of 23 ›` right of the header (P8); the batch still covers every included member on every page,
  and the batch line says so: `Verdict for the 21 included members (3 pages)`. Largest batch 50 members
  (Settings 8): above 50 the batch box is disabled with reason `batches are capped at 50 members — split the cluster or judge members singly`.
- **Batch Checkbox** `Verdict for the N included members` — on (default): a verdict key writes all
  included members as one SessionWrite (items[] > 1); off: writes the shown member only.
- **Verdict key with batch on** — simulated write: each included card's status chip flips in sequence
  (~60 ms stagger) while auto-advance waits; when the last one lands, if auto-advance is on, navigate to the
  next queue item; `previous` line `Cluster 12 · 6 × interesting · just now`; progress `67 / 118`, `51 left`.
  **S with batch on** — promotes **one** exemplar (the member nearest the medoid, c-0371) and writes seed only
  on it; the other included members get `interesting`, with Toast `seed promotes one exemplar (c-0371); 5 others marked interesting`
  (Fog F16 — spec does not say).
- **Ctrl Z after a batch** — reverses all 6 writes in one step → batch-undone state; progress back to `61 / 118`.
- **Redo** link / **Ctrl Shift Z** — re-applies the batch; banner closes; auto-advance resumes only on the next key.
- **Edit span in Explore** — for the shown member.
- **Collapsed-rail purple bracket** — click → opens this cluster page.

### Plots

| plot | type | axes | marks | cap | fixture |
|---|---|---|---|---|---|
| Member in context | Trace | x hours since start `204.150 h … 204.217 h` (±120 s), y mV ±0.4 | as candidate card; band 204.183 → 204.192 h | — | `member.trace(pad)` |
| Members strip | SmallMultiples of Trace thumbnails | no axis ticks; **shared y in mV across all members** (never normalised); x = each member's own duration | black line; excluded member amber | ~10 per page (P8) | `cluster.members[].trace` synthetic sharkfin with depth varying by d; c-0377 a different (slow) shape |

### Fixtures

```ts
interface ClusterMember {
  id: string                    // 'c-0371'
  d: number                     // distance to medoid, 0 → 1
  status: 'unadjudicated' | Verdict
  channel: 'CH4_A2' | 'CH2_A1'
  startH: number; durationS: number
  included: boolean             // default: d <= cohesionLimit
}
interface ReviewCluster {
  no: 12 | 13
  queueId: 'q-15' | 'q-12'
  kind: 'family set' | 'sequence'
  badge: 'seed-search matches' | 'sequence'
  recording: 'M2_aug fs1'; runId: 'r-0415' | 'r-0412'
  exemplar?: 'E-0102'
  family: { id: 'F-03'; d: 0.19 }
  artifact: 'low'
  cohesionLimit: 0.45            // Settings › Review queues (B16 placeholder)
  members: ClusterMember[]
  previousLine: string           // 'cluster 11 · 5 × interesting · 1 min ago'
}
const CLUSTER_12: ReviewCluster = {
  no: 12, queueId: 'q-15', kind: 'family set', badge: 'seed-search matches', recording: 'M2_aug fs1', runId: 'r-0415', exemplar: 'E-0102',
  family: { id: 'F-03', d: 0.19 }, artifact: 'low', cohesionLimit: 0.45, previousLine: 'cluster 11 · 5 × interesting · 1 min ago',
  members: [
    { id: 'c-0371', d: 0.12, channel: 'CH4_A2', startH: 203.412, durationS: 31.0, status: 'unadjudicated', included: true },
    { id: 'c-0372', d: 0.15, channel: 'CH2_A1', startH: 203.655, durationS: 34.0, status: 'unadjudicated', included: true },
    { id: 'c-0373', d: 0.19, channel: 'CH4_A2', startH: 204.183, durationS: 33.0, status: 'unadjudicated', included: true },
    { id: 'c-0374', d: 0.22, channel: 'CH4_A2', startH: 206.020, durationS: 30.0, status: 'unadjudicated', included: true },
    { id: 'c-0375', d: 0.26, channel: 'CH2_A1', startH: 207.941, durationS: 36.0, status: 'unadjudicated', included: true },
    { id: 'c-0376', d: 0.31, channel: 'CH4_A2', startH: 210.118, durationS: 29.0, status: 'unadjudicated', included: true },
    { id: 'c-0377', d: 0.61, channel: 'CH4_A2', startH: 212.506, durationS: 41.0, status: 'unadjudicated', included: false },
  ],
}  // channels ×5/×2 and start hours other than c-0373 are proposals (frame gives only the totals)
// CLUSTER_13 (q-12, sequence · 3 within 6 min · CH4_A2): c-0350 0.83, c-0351 0.83, c-0352 0.82 (scores; d values proposed 0.14/0.17/0.22)
```
Shared: q-15, r-0415, E-0102, F-03 (Library/Discovery). The cohesion limit and sequence rule are Settings values (shared with Library groupings).

### Copy

`Cluster 12`, `cluster`, `seed-search matches`, `status 7 unadjudicated`, `cohesion`, `mean d 0.21 (6 included) · worst 0.61`,
`M2_aug fs1 · CH4_A2 ×5, CH2_A1 ×2 · run r-0415 seed search, exemplar E-0102 · showing member c-0373`,
`Member in context`, `c-0373 · 33.0 s · member 3 of 7`, `Members`, `7 · seed-search matches of exemplar E-0102 · shared y · mV`,
`sorted by distance to medoid`, `Include all`, `least similar`, `unadjudicated`,
`previous  cluster 11 · 5 × interesting · 1 min ago`, `undo · reverses the whole batch`,
`Verdict for the 6 included members`, `1 excluded · c-0377 d 0.61, above the 0.45 limit`, `auto-advance waits for the whole batch`;
frame 7: `status 7 unadjudicated · batch undone`, `undone  Cluster 12 · 6 × interesting · 2 s ago`,
`Batch undone · 6 verdicts on Cluster 12 reversed in one step · members back to unadjudicated`, `auto-advance paused`, `Redo`, `Ctrl Shift Z`;
micro-stats `mean d`, `worst d`, `F-03 d`, `artifact`, `members`.

### Frame ⟷ spec conflicts (review.cluster)

- **C9 — Mean d.** Title pill `mean d 0.21 (6 included)`; collapsed rail `0.24 mean d`; mean of all 7 is 0.27.
  Recommend the rail shows the same included mean as the pill (0.21).
- **C10 — Family pill in frame 7.** Frame 7 drops the `family F-03 d 0.19` pill that frame 2 has; §10.2 says those
  pills are **always visible**. Keep it in both.
- **C11 — Brief suggested `#/review/cluster/<id>`.** Adopted as an alias only; the canonical route nests under the
  queue because the toolbar, progress and filters are the queue's.

### Fog (review.cluster)

- **F15** — B16: cohesion limit 0.45, sequence gap ≤ 6 min and ≥ 2 events are placeholders "values still to decide".
- **F16** — What **S** means for a batch (one exemplar? seed on every member?) is not specified.
- **F17** — Which member is shown by default when entering a cluster (frame shows member 3, not the nearest).
- **F18** — Frame 2 title says `status 7 unadjudicated` while the previous cluster line and rail suggest a mixed
  history; a cluster with some members already judged (prior verdict chip other than `unadjudicated`) is not drawn —
  whether judged members are included in a new batch is unspecified (shell: judged members default unchecked).

---

## review.blind (state of review.inspector)

### Route & states

| state | frame | reached by | query |
|---|---|---|---|
| blind-unjudged (default for blind queues) | review-5-blind-verification | open `#/review/queue/q-19/w-40211`, pick *Model verification* in the queue picker/rail, Jobs row q-19 *Open* | — |
| blind-revealed | not drawn separately | after a verdict with auto-advance off: stays on w-40211, status pill shows your verdict, model-call pill turns to `model call burst · p 0.81` with `agree`/`differs` chip; with auto-advance on the next window loads and the **Previous window, revealed** card shows w-40211 | — |
| blind-evidence-rail | not drawn | right rail toggle — machine sections masked | `?rail=evidence` |
| blind toggled on a sighted queue | not drawn | `?pop=blind` toggle on q-12 | — |
| training-windows (q-18) | not drawn (B5: "same layout as frame 5 without the reveal") | `#/review/queue/q-18/w-00001…` | — |

### Regions (frame 5; differences from review.inspector frame 1 only)

- Header subtitle `queue model verification · cnn_windows_v3 · manual`.
- Toolbar: queue chip `queue Model verification · cnn_windows_v3 · manual ▾` (model icon); the opinion chip is
  **purple**: `⊘👁 blind · hidden until verdict (i)`; `writes window verdicts`; progress `33 / 40` `~6 s each` (82.5 %).
- Left rail: `7` / `left`.
- Title row: `w-40211` + chip `window` (grey) + chip `test block` (purple tint); pills `● status unadjudicated` ·
  `⊘ model call hidden until verdict` (purple) · `● artifact likelihood low`. **No score, no family pill.**
  Meta: `M2_aug fs1 · CH2_A1 · 3.17 → 3.33 h · 600 s window · stratified test sample, 34 of 40 · candidate cnn_windows_v3 · manual`.
- Context card title `Window in context`; padding Seg; **only** `Other channels` (no *Edit span in Explore*).
  x ticks `3.13 h 3.19 h 3.25 h 3.31 h`; band spans most of the plot, label `w-40211 · 600 s` inside the band top-left.
- Row c left: **"Shape · mV"** with legend `— this window` (black); x `0 s` → `600 s`; y ±0.4 mV. No medoid.
- Row c right: **"👁 Previous window, revealed"** + (i) (purple eye icon). Inner grey card: thumbnail (≈70 × 50) ·
  `w-40210` bold · two KeyValue lines `you  burst` / `model  burst · p 0.81` · right green chip `agree`.
  Below: `The model's call on this window stays hidden until you press a key.` /
  `Running agreement is shown in Models › Registry, not here.` / muted `artifact likelihood is not blinded`.
- Verdict: `previous  w-40210 · burst (class) · 7 s ago`; six VerdictCards with captions (as frame 1).
- Annotate: as frame 1, but **no tag pre-selected** (tags all grey).
- Right collapsed rail micro-stats: eye-off icon over `model` · eye-off icon over `family` · `low` artifact (green) · `34/40` sample.

### Controls & interactions (blind-specific)

- **Blind chip** — Popover (`?pop=blind`): "Hidden until the verdict: score and × null, family affinity and nearest
  families, prior machine calls, the model's prediction, the evidence rail's machine sections. Never hidden: the
  signal, other channels, artifact likelihood." + Toggle `blind for this queue` (on). Turning it off in q-18/q-19
  opens a confirm Modal: `See machine opinion in Model verification?` / body `Verdicts from now on are stored as
  sighted. The registration sample expects blind verdicts.` / `Keep blind` (primary) · `Show machine opinion`.
- **Verdict keys** — write with `blind: true`; then reveal: the *Previous window, revealed* card animates to the
  just-judged window showing `you <verdict or class>` vs `model <class> · p`, chip `agree` (green) when your class /
  verdict matches, `differs` (amber) otherwise. **No running agreement count anywhere on this page** (§10.6).
- **Verdict keys per queue** (Settings 8): q-19 `full + classes` → S I N A U + 1–4, 9 (as the frame); q-18
  `binary + classes` → only **I**, **N** and the class keys are shown/active; S, A, U cards are hidden (not
  disabled) and pressing S/A/U shows Toast `this queue takes binary verdicts and classes`.
- **Other channels** — works unchanged (never hidden).
- **E / Edit span** — absent for windows.
- **Evidence rail** (not drawn) — Origin shows window set `ws_M2aug_3ch_600s v1`, `test block`, stratified sample
  `34 of 40`; **Detection / Model call / Family / Also found by** sections render collapsed with an eye-off icon and
  `hidden until verdict`; **Artifact likelihood** and **History** shown; footer `Writes one window verdict on
  ws_M2aug_3ch_600s · window 40211 (blind).` (B15 wording).
- **Queue rail** in a blind queue — up-next rows show thumbnails and ids without scores; score RangeSlider disabled
  with reason; group Seg `family` disabled with reason `family affinity is hidden in a blind queue`.

### Plots

| plot | type | axes | marks | cap | fixture |
|---|---|---|---|---|---|
| Window in context | Trace | x hours since start `3.13 h … 3.31 h` (visible domain ≈ 3.133 → 3.367 h at ±120 s; frame ticks end at 3.31), y mV ±0.4 | black line; blue band over the 600 s window; label inside band | 1 Hz → 840 samples | `window.trace(pad)` synthetic with 2–3 slow deflections |
| Shape · mV | Trace | x `0 s` → `600 s`, y mV `+0.4 mV / 0 / −0.4 mV` | black 2 px | — | the 600 samples of the window, lightly smoothed |
| Previous window thumbnail | Sparkline | none | black | 1 | previous window trace |

### Fixtures

```ts
interface ReviewWindow {
  id: string                      // 'w-40211'
  queueId: 'q-19' | 'q-18'
  windowSet: 'ws_M2aug_3ch_600s'; windowSetVersion: 1
  block: 'test' | 'train'
  recording: 'M2_aug fs1'; channel: 'CH2_A1' | 'CH4_A2' | 'CH7_B2'   // the window set's 3 channels
  startH: number; endH: number; lengthS: 600
  sampleIndex?: number; sampleOf?: 40   // q-19 stratified sample position
  candidateModel?: 'cnn_windows_v3 · manual'
  modelCall: { className: string; p: number }        // hidden until verdict
  artifact: 'low' | 'medium' | 'high'
  status: 'unadjudicated' | Verdict
  you?: { verdict?: Verdict; className?: string }
}
// q-19: 40 windows w-40178 … w-40217 (proposal); 33 judged with 28 agreeing (§0: 33 of 40 judged, 28 agree);
// w-40210 judged: you class burst, model burst p 0.81 → agree; current w-40211 CH2_A1 3.17 → 3.33 h, modelCall slow-drift p 0.64 (so a burst press shows `differs`).
// Remaining 6: w-40212 … w-40217, mixed channels/classes.
// q-18: 20,000 windows, 1,600 judged; generate lazily from ws_M2aug_3ch_600s train block, ids w-00001 …
```
Shared: window set (Library, Models, Analyse training), model `cnn_windows_v3 · manual` and verification counts
(Models › Registry shows 33/40 judged, 28 agree — the only place agreement is shown).

### Copy

`blind · hidden until verdict`, `writes window verdicts`, `33 / 40`, `~6 s each`, `7 left`, `w-40211`, `window`, `test block`,
`model call hidden until verdict`, `M2_aug fs1 · CH2_A1 · 3.17 → 3.33 h · 600 s window · stratified test sample, 34 of 40 · candidate cnn_windows_v3 · manual`,
`Window in context`, `w-40211 · 600 s`, `Shape · mV`, `this window`, `Previous window, revealed`, `w-40210`, `you`, `model`, `burst · p 0.81`, `agree`,
`The model's call on this window stays hidden until you press a key.`, `Running agreement is shown in Models › Registry, not here.`,
`artifact likelihood is not blinded`, `previous  w-40210 · burst (class) · 7 s ago`, micro-stats `model`, `family`, `artifact`, `34/40`, `sample`.

### Frame ⟷ spec conflicts (review.blind)

- **C12 — Seed on a window.** Frame 5 offers `S seed · promotes to Library` on a 600 s test-block window; §10.4
  says S creates a Library exemplar with span/recording/channel. A model-verification window as a motif exemplar is
  dubious. Settings 8 says model verification is `full + classes`, so keep S visible as drawn, but see Fog F19.
- **C13 — "34 of 40" vs "33 / 40".** Not a conflict: 33 judged, the current window is the 34th. Keep both.

### Fog (review.blind)

- **F19** — Whether S (seed/promote) should exist in window queues at all.
- **F20** — B15: where window verdicts are stored is undecided; the page only states `writes window verdicts`.
- **F21** — Which Origin fields count as "machine opinion" and are masked in the blind evidence rail.
- **F22** — Whether *you* in the reveal compares by verdict or by class when only a binary verdict is given
  (w-40210 was judged by class `burst`).
- **F23** — Training-windows queue (q-18) frame is not drawn; `binary + classes` key set is taken from Settings 8.

<!-- NEXT: jobs.* , kit needs -->

## jobs.*

Written by the Jobs builder (overnight build, 16 Sep). Sources: frames jobs-1 … jobs-4, spec §0, §3, §7c,
§9.6, P4, P24, canon `JOBS` / `REVIEW_QUEUES`. The Pages-table rows above stay authoritative for routes and
state names; this section adds regions, controls, fixtures and copy. All four pages share one in-memory Jobs
store (`jobs/store.ts`), so a mark, a continue or a cancel on one page shows on the others until reload.

### Shared model

- **Job kinds** (id prefix, §0): `j-` cluster job · `a-` Analyse run · `r-` Discovery run · `l-` Library regroup ·
  `q-` Review queue. Workspace icon per kind (Analyse `branch`, Discovery `target`, Models `layers`, Library
  `library`, Review `checklist`).
- **Groups** (§7c.1): Paused · waiting on cluster results → Cluster jobs · status marked by hand → Running locally →
  Review queues → Finished and cancelled today (collapsed).
- **Needs you** (P24): a paused run waiting on a result, a result that can continue, a cluster job past 3× estimate,
  a manifest waiting to import. The canon produces exactly three (r-0431, a-0098, j-0214) = header `3 need you`
  (`DEMO_NEED_YOU`) and nav `Jobs · 3`.
- **Cluster status is marked by hand**: script created (automatic) → submitted → running → finished | failed. Never
  changed automatically; *finished* is also set when the job's manifest is imported.
- **Paused-run result states**: `waiting` (not in its root yet) → `arrived` (found, checks run) → `continuing`
  (sim: stages N+1…) → `finished`; or `cancelled` (cached stages kept). r-0431 defaults to `waiting` (jobs-1 rail);
  a-0098 to `arrived` ("result in place").
- Jobs created elsewhere (`recordDemoWrite('jobs', 'add-job', …)` from Analyse chain-1g, Discovery, Models) are
  appended to the table, marked `new · this session`, and open on `#/jobs/cluster/<id>` as `script created`.

### jobs.all — `#/jobs`

**Regions.** Header (`Jobs | All jobs`, subtitle `3 need you · 2 local · 2 on hpc-1 · 4 queues`, search
`Search jobs, runs, queues`, demo chip). Title row: `Jobs` + count chips (amber `3 need you`, blue `2 running
locally`, purple `2 on hpc-1`, grey `4 review queues · 1 idle`) + *Manifest inbox · 1* button (right). Filter row:
Seg `all · needs you · paused · cluster · local · review queues · finished` + workspace Dropdown `all workspaces`.
Needs-you cards (3 across, amber/green/amber borders). `All jobs` table card (`sorted by what needs you first`;
columns id · job · where · status · time · action). Right rail (≈ 300 px) for the selected job.

**Controls.** Seg / `?filter=` (also `?kind=` alias from Models); Dropdown / `?ws=`; row click / `?sel=`; group bar
toggles (Finished collapsed by default, `?finished=1`); row actions: *Upload results* (→ upload), *Continue*
(sim), *Mark…* menu (submitted / running / finished / failed), *Open in Models*, *New script* (modal), *Cancel*
(local job → cancelled), *Open* (→ Review queue). Needs-you card buttons do the same. Rail per kind: paused run
(stages Stepper, waiting box with expected path, *Open run detail →*, *Look again* (sim → arrived), *Upload results
and continue*, *Run stage 3 locally* disabled `~6 h · over the 20 min limit`, *Cancel run* → confirm modal);
cluster job (status pills, marks, *Open job →*, Mark buttons); local (progress, *Cancel*); queue (left of total,
pace, blind badge, *Open in Review*); finished (summary). *Manifest inbox · 1* → Drawer `?drawer=inbox`.

**States.** `all` (sel r-0431) · `needs-you` · `paused` · `cluster` · `local` · `queues` · `finished` ·
`filter-empty` (`?filter=finished&ws=explore`) · `finished-expanded` · `rail-cluster` (`?sel=j-0214`) · `rail-local`
(`?sel=a-0101`) · `rail-queue` (`?sel=q-19`) · `inbox-drawer` · `new-script` modal (`?modal=new-script&job=j-0209`)
· `cancel-confirm` (`?modal=cancel&job=r-0431`) · `continuing` (card *Continue* on a-0098).

### jobs.paused — `#/jobs/run/<runId>`

**Regions.** `‹ All jobs` link; title `r-0431` + amber `paused at stage 3 of 4` + green `result arrived` (or amber
`waiting on j-0217`); *Open in Discovery* / *Open in Analyse* (right); meta line (`Discovery run · mp_drops_v3 v3 ·
M2_aug fs1 CH2_A1–CH4_A2 · 721 h · started 14 Sep 08:02`). **Where the run stopped** card: stage cards in a row
joined by chevrons (number, name, state badge, two caption lines; current stage green when arrived, amber when
waiting), timeline under them (dots + time + label). Two columns below: **Stage 3 result** (green border when
arrived: `found 14:31 · 1.9 GB` badge, `expected at` locked path + *Show in folder*, `checks before the run can
continue` list with right-aligned evidence, info strip, *Continue from stage 4* primary + *Look again*) and **Other
ways forward** (Upload results… · New SLURM script · Run locally (disabled, reason) · Cancel run (red)).

**States.** `result-arrived` (`?state=arrived`; a-0098 default) · `waiting` (r-0431 default: checks pending,
Continue disabled with reason) · `looking` (*Look again* sim) · `continuing` (sim: remaining stages tick) ·
`finished` · `cancel-confirm` (`?modal=cancel`) · `cancelled` · `new-script` (`?modal=new-script`) · `unknown-run`.

### jobs.upload — `#/jobs/run/<runId>/upload`

**Regions.** jobs.paused rendered underneath; Modal `Upload results and continue` (lg): subtitle `r-0431 · Discovery
run mp_drops_v3 · stage 3 of 4 · Matrix profile on M2_aug fs1 CH2_A1–CH4_A2`; file card (icon, name, `1.9 GB · from
Downloads · copied off hpc-1 by hand`, *Choose another file*); `will be placed at` locked path + `named by Storage`;
`checks` list (readable file · one profile per channel · length matches the signal · values finite · made with this
run's parameters · null draws); red refusal (`This file cannot continue r-0431` + *Choose another file* + *Start a new
run with m = 60 s*); amber note `When a file passes but has no null draws`; footer `nothing is placed until every
check passes` · *Cancel* · *Place file and continue* (disabled until every check passes).

**States.** `refused` (`?file=mismatch`, default) · `no-file` (`?file=none`) · `checking` (choose a file: checks tick
in) · `passes-no-nulls` (`?file=ok-no-nulls`) · `passes` (`?file=ok`) · `held-out` (`?file=held-out`: an M4_aug
file, refused D6) · `file-menu` popover. Place → closes, run `continuing` (or `null on the cluster` for no-nulls).

### jobs.cluster — `#/jobs/cluster/<jobId>`

**Regions.** `‹ All jobs`; title `j-0214` + amber `running · 3.3× estimate` + workspace line; *Open in Models ›
Results* (right). **Status** card: `marked by hand · the site cannot see the cluster queue`; pills script created ›
submitted › running › finished with times; amber reminder `Marked running for 3.3 h — 3.3× the 1 h estimate` with
*Mark finished* · *Mark failed* · *Still running · remind me in 3 h*; rows cluster job id (editable) · profile
(Dropdown) · results return from (locked) · estimate (locked) · script (*Copy*, *Save .sh*, dark code block).
**Manifest inbox** card: `1 imported`, `watching ./cluster_out every 5 min · last looked 2 min ago`, manifest card
(j-0212: contains · import checks · *Imported* disabled), `stage results for paused runs` with *Open*.

**States.** `running-overdue` (j-0214) · `running` (j-0217) · `finished-imported` (j-0212) · `failed` (j-0209) ·
`snoozed` · `marked-finished` · `marked-failed` · `script-created` (an added job, e.g. from New SLURM script) ·
`inbox-pending` (`?inbox=pending`: j-0214's manifest arrived, *Import results* sim) · `unknown-job`.

### Fixtures (`fixtures/jobs.ts`)

Canon ids and titles from `JOBS` / `REVIEW_QUEUES`; the rows the frames add (a-0101, l-0009, the q-12…q-19 counts,
the seven finished/cancelled rows, run stages, checks, paths, scripts, the j-0212 manifest) live in
`fixtures/jobs.ts` and are read only through `api/jobs.ts`. Invented rows are listed in `pages/fog/jobs.md`.

### Copy

Verbatim from the frames: `sorted by what needs you first`, `the site cannot see the queue — check the cluster`,
`Continue stores this file as stage 3's artifact, marks j-0217 finished, and runs stage 4 locally (~40 s).`,
`It was made with different parameters. Continuing with it would give the run a recipe it did not follow.`,
`Check the cluster. The site never changes a cluster job's status on its own.`, `nothing is placed until every check
passes`.
