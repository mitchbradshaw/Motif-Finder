# Report — Fixup H: a block shows its work

Run 2026-10-02 on `main`, in the main checkout, alone on the machine. Commit prefix `fixup-h:`. The first commit,
`2ddfbcc`, touches only `tests/` and fails 71 tests under conda (the four route tests it adds need `webui/.venv`
and fail there): no `webui/server/views.py`, no client registry, the generic caption still in `BlockPage.tsx`, and
none of the payload fields the views draw. Every bridge ran in `--sandbox` on a private client build
(`run_server.py --dist`, the `CLIENT = …` banner checked). Nothing wrote to the real `DATA/db/annotations.sqlite`;
the evidence script reads the tracked seed store and drives sandbox bridges only.

**What is true now, in one paragraph.** Every registered block is drawn from its type signature: its output type
picks one of seven views, its conversion one of twelve modifiers, and the block page never looks at a block's name.
`GenericProcess` and its caption — *"this signature has no bespoke process view yet"* — are deleted; **zero of
thirty-six blocks resolve to a generic view**, and a test fails the moment one would. Each view is one component
drawn at two tiers (the chain thumbnail and the settings page) with interaction as a flag. Any block that emits
spans gets the slideshow, on real samples, with the impurity flag. The Aggregate page's two fabricated nulls are
gone along with the P10 wording they wore. Rule 9 is measured in a real browser by the smoke gate.

No Round 8 was opened. Nothing found contradicted the prompt; where it left a choice I took a default and listed it
in §9 so it can be overturned.

---

## 1. The seven views, as built

`webui/client/src/analyse/views/` — one file per output type, `registry.tsx` binding them. Before/after of one
block per type at both tiers: `webui/screenshots/fixup/H/{before,after}-{thumbnail,settings}-<type>-<block>.png`.

| Output | n | settings page | thumbnail | photographed on |
|---|---|---|---|---|
| **Signal** | 6 | before and after overlaid, input grey beneath; hover reads both values at one time; a line saying what was drawn and what the block did to the range | the same overlay | `detrend` |
| **Scores** | 3 | the curve; the scored signal above it on the same x; the value histogram; the next stage's cut marked as a level when that stage has one | the curve alone | `matrix_profile`, `wavelet_summation` |
| **SpanSet** | 11 | every span on the trace, clickable; **the slideshow**; the duration distribution | every span on the trace — a density ribbon once spans outnumber pixels 1 : 3 | `threshold`, `summation_threshold`, `drop_detection` |
| **Encoding** | 12 | three sampled frames, a scan through the rest, a colour bar with the real range, no-data in grey, each frame located on the signal | three frames side by side with a locator bar on the shared time axis | `wavelet_transform`, `sax_dsax`, `window_images` |
| **WindowSet** | 2 | windows on the time axis and the whole feature matrix as a heatmap with a hover readout | the heatmap on the row's time axis, grey where no window | `window_matrix`, `sliding_windows` |
| **Grouping** | 1 | cluster of every window in time; when each cluster is active; sizes as bars; one exemplar per cluster | when each cluster is active, a row per cluster | `cluster` |
| **Model** | 1 | holdout accuracy per class as bars | the card, with the per-class line | `classifier` |

Three things about the views that were decisions rather than transcription:

- **Signal — one axis or two is measured, not declared.** Both traces share an axis unless that would give either
  one less than 35 % of the plot's height; then the original is on the left axis in grey and the new one on the
  right in blue. On the example span `detrend` takes the channel from −461.7 … −434.0 mV to −13.2 … +9.4 mV, so
  it draws two axes; a low-pass would draw one. A block does not have to say which kind it is.
- **Encoding — what "an image" is depends on the value's shape**, and the bridge decides it once
  (`serialize.py::_frames`): the k-th image of a stack; a 256-column chunk of a time-aligned image *at the image's
  own resolution*; or the whole of any other image. The wavelet transform is 87 × 7200 and was being block-averaged
  to 87 × 248 — a smear of what the block computed. It is now 29 chunks, three shown, all on **one** value range so
  the colour bar is true of every frame.
- **A symbolic Encoding keeps its strip as the thumbnail** rather than three images (it is already one picture of
  the whole span on the shared axis), and gets three sampled 48-symbol chunks on the settings page, each drawn
  against the signal it was cut from. Where symbols outnumber pixels a column is the *mix* of the symbols under it,
  stacked by share — a majority vote would erase the rare symbol (a fall) the encoding exists to find.

## 2. The twelve modifiers, as built

| Conversion | n | what the settings page adds | changed from the prompt? |
|---|---|---|---|
| signal → signal | 6 | the overlay; dual axes by the measured rule | no |
| signal → scores | 1 | the signal above the curve; a windowed score's window `m` drawn to scale at the lowest score and its neighbour | no |
| encoding → scores | 2 | the image above on the same x with the summed band boxed on it (`row_from` / `row_to`); a stack upstream shows its sampled frames instead | no |
| scores → spanset | 3 | the cut on the upstream curve, **draggable where the block has an absolute `threshold`**; the histogram and the spans-vs-cut curve beside it | **yes — see below** |
| encoding → spanset | 2 | the symbols (or the time-aligned image) with the spans that fired outlined on it | no |
| signal → spanset | 4 | spans on the trace | no |
| spanset → spanset | 2 | a histogram per measure, the rose, interval statistics; the per-event table folded away | no |
| signal → encoding | 11 | the frames and the chunk of signal each came from | no |
| windowset → encoding | 1 | the frames and the window each is | no |
| signal → windowset | 2 | by payload: a feature matrix → heatmap; no features → windows coloured train / validation / test | no |
| windowset → grouping | 1 | clusters over time and one exemplar per cluster | no |
| grouping → model | 1 | accuracy per class | no |

**The one I changed.** The prompt says to generalise `detection.threshold`'s draggable cut to all three
`scores → spanset` blocks. The view is generalised — all three draw the upstream curve with their spans — but
**only one of the three has a cut to drag.** `detection.threshold` cuts at one absolute level in the scores' units.
`detection.summation_threshold` cuts by extremum prominence *relative to each 3000 s window* and
`detection.mp_motifs` takes the k lowest groups; neither has a level that a horizontal line would be. Drawing a
draggable line for them would be drawing a control that does not exist. So the line is draggable when the block has
a `float` parameter named `threshold` (a convention now written in `BLOCK_INTEGRATION.md`), and otherwise the page
says, on its face, that this block's cut is not one absolute level, and shows its decisions instead — for the
Dehshibi stage, the funnel `J` built.

**Three views that were name-dispatched are now payload-driven.** `ThresholdProcess`, `MatrixProfileProcess` and
`DsaxProcess` were picked by `name === 'detection.…'`. Their content survives as the modifier of their conversion:
the PAA steps and learned cutlines draw for *any* symbolic encoder whose payload carries them, the window-`m` boxes
for any Scores that states an `m`.

## 3. How the two tiers share one component

`ViewCtx.interactive` is the whole difference. `Renderer.tsx::renderByType` (the chain row) calls
`VIEWS[type]` with it off; `registry.tsx::BlockProcess` (the block page) calls the same component with it on, at
full width and height, and adds the evidence around it. There is no second implementation of any picture. What
`interactive` turns on, per view: hover readouts (Signal, Scores, WindowSet), the scored signal above a Scores
curve, click-to-select on spans, the window-tick strip above a heatmap, the per-window strip above a Grouping,
frame captions and the bars of a Model.

## 4. The slideshow (U8)

`kit/Slideshow.tsx::EventSlideshow`, built on `SmallMultiples` — which gained a per-panel domain mode, selection
that drives the page, arrow-key movement and a default-to-sample option, all additive. One card per event carrying
its id, a chip, the trace, a scale bar, one line of facts, and what was drawn. Sorted by score / time / duration;
paged at ten, or opened on a seeded sample once there are more than thirty. Clicking a card marks the span on the
plot above; clicking a band selects its card and brings the page that holds it.

- **Real samples, real times.** The cards fetch each span's stretch of the source channel
  (`GET /api/channels/{id}/window`) and draw the samples where they are. Samples 3 px or more apart are dotted;
  past the pixel budget the card says *min/max envelope*.
- **The impurity flag.** A window holding more than one event is red and titled `[2 falls]`. The count is by
  **sample range** (`serialize.py::_span_anatomy`), never a window index. Where a detector names its falls
  (`meta["events"]`, or a feature block's `onset_idx` / `extremum_idx`) it counts *falls*, so overlapping windows —
  shared context — are not flagged and are not deduplicated.
- **Read-only.** The one action is **Send N to Review**, and it is real: it creates a Review queue over the
  detections the run wrote (`POST /api/review/queues`, `source_kind: discovery-run`, `filters: {run_id}`) and
  opens it. Verified on a sandbox bridge: `after-send-to-review.png`.

**On a real store.** The Interrogation source block's member grid is the same slideshow, fed the seed store's own
snippets (`after-slideshow-impurity-id024.png`): **12 of id024's 40 windows hold more than one fall** and are drawn
red with the store's own purity count. That grid used to resample every snippet to one value per second by linear
interpolation (`liveEventCurve`, deleted) and put every tile on one shared y.

**Per-panel domains and scale bars.** `after-slideshow-per-panel-scale-id025.png`. A correction to the evidence the
prompt asks for: **no seed family spans two orders of magnitude.** The widest is id025, 7.5 mV to 75.1 mV — one
order — and that is a ceiling by construction: the detector's own `min_depth_frac = 0.10` drops anything shallower
than a tenth of the deepest event on a span. Within that order the old shared y already failed: see §5.

## 5. Rule 9 in the gate, and what it caught

`webui/smoke.py::rule9`, opt-in per page state (`"rule9": true`). The thesis rule measures a figure's
height-to-width against its median event; a UI plot is not aspect-locked, so the port keeps what the rule is *for*.
Every view marks its plot (`svg[data-rule9]`) and its traces (`[data-trace] path`), and for each trace the browser
measures that it **varies** (more than one distinct y), is **not flattened** (its drawn height is at least 20 % of
its plot's), and is **not clipped** (every vertex inside the plot). A plot whose *data* is constant declares it
(`data-flat="1"`) and is exempt; a state with no trace to measure fails.

It is asserted on 16 page states: 15 of the 20 new Analyse states (five chains, every output type at both tiers — the five that draw no trace, such as the heatmap, the image frames and the model bars, do not ask for it) and the store slideshow.

**What it caught.** On the finished build, nothing — all 16 states pass, 71 traces. Measured against the build
this prompt started from (`rule9-member-grid.json`), it catches the defect Q15 predicted:

| member grid, ten tiles | old build, one shared y | new build, per-panel y |
|---|---|---|
| id024 — trace height as a share of its panel | median 37 %, lowest 23 % | 83 % on every tile |
| id025 | **two tiles at 8.5 % and 16.7 %** — below the 20 % floor | 83 % on every tile |

So on the old build rule 9 fails id025: two of ten members were drawn as near-flat lines because a 75 mV sibling
set the axis. It did *not* fail id024, and I am reporting that rather than tuning the floor until it did.

## 6. The two nulls deleted, and what the page says now

Both are gone from `AggregatePage.tsx` — `nullSample`, `nullPoints`, `nullFit`, the null-method selector, the
null-β tile — and `NullHistogram.tsx` is `CategoryHistogram.tsx` with no null series. The P10 claim went with them:
the toolbar chip on all three Interrogation pages read *"null matched random windows · 200×"* with a green dot; it
now reads **"no null"** with an amber one. `AGGREGATE_PARAMS.nulls` and `NULL_SPEC` are deleted from the fixtures.

**What the page says now**, once, on its face: *"no null is drawn on this page: every number below describes these
events and is not tested against chance"* — with the reason behind the icon. The scaling card's info says the
exponent *"is not compared with a null — none is built — so it describes these events and is not a test of a
relationship."* An old deep link (`?null=shuffled`) lands on that page and is ignored.

**The consequence the prompt asked to be stated.** The scatter null was each real point multiplied by independent
random factors on x and y. Independent noise on x attenuates a fitted slope, so that null's exponent was a
regression-diluted copy of the real one and sat below it by construction. `E`'s finding for id010 — **β 0.28
against a null of 0.25** — was therefore never a comparison: that null could be neither cleared nor failed. The
real one is `future/R-interrogation-null.md`; `kit/plots.tsx::NullBand` is still there for it.

## 7. How many blocks still resolve to a generic view

**Zero**, pinned by `tests/test_block_standard.py`, which grew a drawing clause (44 tests):

- every registered adapter resolves to one of seven views and one of twelve modifiers (36 parametrised cases);
- the twelve modifiers are *exactly* the registered conversions — no block without one, no modifier nobody uses;
- a conversion nobody has written yet still gets its type view, and a non-type is refused;
- the catalog card carries `view` and `modifier`;
- the client registry names a component for every key of the server's tables;
- no file under `webui/client/src` contains the generic caption, and `BlockPage.tsx` has no `GenericProcess`;
- `BlockPage.tsx` dispatches on no block name.

The written level is `docs/BLOCK_INTEGRATION.md` §2, rewritten as the drawing standard beside the block contract.

## 8. Which rose survived, and the capped edges

**The rose.** `kit/Rose.tsx` — the former `RoseFan`, which draws `gradients.rose_data` exactly as the core computed
it. `interrogation/Rose.tsx` is deleted. The block page, the Sequence page and the Slope page all draw the kit's.

This surfaced something worth knowing. The deleted rose computed its own angle in the browser,
`arctan(|slope| / 0.1 mV/s)`, while the core's rose uses a reference of 1 mV/s. So **the Slope page showed a
different angle for the same event than the Sequence page and the Analyse block page did**: for the default event
(`id001_r1_1216093`, steepest slope −0.70 mV/s) about −82° on one and −35.1° on the others. The Slope page's rose,
its table column and its readout now all show the core's served angle, and the radius-by-event-order drawing is
replaced by the binned wedges. If the 0.1 mV/s convention was the intended one for the thesis figures, that is a
one-parameter change to `rose_reference_mv_s` in the core — it should not be a second formula in a page.

**Capped edges (Q18).** `Working/Detection/drop_motifs/extent.py::capped_edges` reads it off a row: an edge sitting
exactly at `onset − 6 × fall` (or `trough + 6 × fall`), with the fall measured as the detector measures it (never
shorter than one encoding segment), and an edge the recording's own start stopped not counted. On the slideshow a
capped edge is a dashed amber line, shown only when the card draws the whole stored extent; the count is on the
face in a few words and in full behind the icon.

On the seed store (`capped-edges.md`): **185 of 410 left (45 %), 119 right (29 %), 90 both (22 %).** Round 7 quoted
46 % / 31 % / 24 %; mine are slightly lower because of the two exclusions above, and I have kept the stricter rule
since it is the detector's own arithmetic. By family it is all-or-nothing in the same way recovery was: id028
19 / 19 left-capped, id024 33 / 40, id385 21 / 24 — against id003, id021 and id029 with none.

**The sequence frame (Q19).** `extent.sequence_frames` is `drawing_rules.sequence_frames` as numbers: back to the
previous event's trough, capped at 14 falls, 1.8 falls after the trough, clipped to the stored snippet. It is a
`frame` option on the members-overlaid plot beside `E`'s context padding, which is unchanged and still the default.

## 9. Defaults taken

Each is a choice the prompt left open. None is load-bearing for the others.

| # | Default | Why |
|---|---|---|
| 1 | Image frames are defined by the value's shape (stack / 256-column time chunk / whole) | "3 sampled images" has no single meaning across twelve Encoding blocks; this is the reading under which a frame is always something the block computed |
| 2 | A symbolic Encoding's thumbnail is its strip, not three images | it is already on the shared time axis; three chunks would leave it |
| 3 | One axis or two for a Signal by a measured 35 % rule | so a new preprocessing block needs no declaration |
| 4 | "The threshold if one exists" = the next stage's `threshold` | the only threshold a Scores block has is its consumer's |
| 5 | A draggable cut only where the cut is an absolute level | §2 |
| 6 | A bare span is drawn with half its own length of context each side, never fewer than 20 samples | a fall cropped to onset → trough is not a picture of the event; spans the detector already bracketed are drawn as they are |
| 7 | Without named falls, impurity counts spans sharing samples | the only range-based count available |
| 8 | A cluster's exemplar is the member nearest its centroid in z-scored feature space | a member, never an average |
| 9 | The classifier now reports accuracy per class from its existing holdout | the bars need a number the adapter did not ship (`Adapters/catalogue_classifier.py`, additive) |
| 10 | Rule 9's floor is 20 % of the plot height | low enough that a real shallow trace passes, high enough that a shared-y flat line does not |
| 11 | The Kendall τ is computed by the core over values the page posts | keeps "the browser computes no statistic" while staying agnostic to which measure is plotted |
| 12 | The Review Shape card's medoid is drawn in its own panel, not stretched | no time axis is served for it; live bridges serve no medoid at all today, so this is visible only on fixtures |

## 10. Items left

- **Capped edges on a chain run's slideshow.** The marking is on the store slideshow only. A chain run's
  `drop_detection` spans could carry it too (the detector knows its own cap), but that is provenance the detector
  should record — `future/N-event-extent.md` step 1 — rather than something to re-infer in a second place.
- **The sequence frame is on the Source overlay only**, not the Slope page's overlay.
- **Colour graded by time** (drawing rule 5) is not applied anywhere: no view here is about order.
- **`gramian_*` (a non-time-aligned image, the "whole" frame) and `cnn_score` were not run in a browser** — the
  Gramians refuse the 7200-sample example span and `cnn_score` needs a trained model. The frame logic for both
  shapes is unit-tested (`tests/test_webui_serialize.py`); the stack case was run and photographed through
  `window_images`.
- **The demo block pages** (`analyse/demo/blocks/`, the `drop_motifs9` concept frames with six hard-coded
  detections) are untouched and still wear the `demo data` chip.
- **The block page's "This parameter against the null" side card** still says null sweeps are out of scope. It is
  an honest absence, so I left it; it belongs to `R-interrogation-null.md`.
- **`cnn_detection` end to end**, Jobs, Models, Training: out of scope, unchanged.
- The four standing Settings registration smoke failures and `discovery.runs--default` are not mine and are not
  touched.

## 11. Out-of-scope files touched

| File | Why |
|---|---|
| `Adapters/catalogue_classifier.py` | reports `per_class_accuracy` / `holdout_class_counts` from the holdout it already takes — additive `meta` |
| `Working/Detection/drop_motifs/extent.py` (new) | capped edges, sequence frames, snippet mismatch: reads rows, changes nothing, no UI import |
| `Working/interrogation/intervals.py` | `kendall_trend`, for `03` I8 |
| `webui/client/src/review/parts.tsx` | `07` R17, the medoid panel |
| `webui/client/src/kit/plots.tsx` | `SmallMultiples` (additive props); `Histogram` gains `xTicks` and its **count axis no longer prints half counts** — that one is a behaviour change for every histogram in the app (a small-count axis read "2 2 1 1 0") |
| `webui/smoke.py` | rule 9; an optional-click action (`click_if`); a run's event stream closed by the client on `run_end` is no longer reported as a failed request — it only showed once the walk ran chains short enough to lose that race |
| `webui/client/src/fixtures/interrogation.ts` | `NULL_SPEC`, `AGGREGATE_PARAMS.nulls` and `TIMELINE_TREND` deleted; member type extended |
| `tests/test_webui_block_views.py` | one pin reworded after the red commit: the kit's `SmallMultiples` is used through the kit's own slideshow, so the test names `EventSlideshow` in `analyse/views` and `SmallMultiples` in `kit/Slideshow.tsx` |

## 12. The gate

| gate | result |
|---|---|
| `npx tsc -b`, `npm run build` | clean. The gate bridge served a private build (`npx vite build --outDir …`, `CLIENT = …scratchpad\\dist-h (a private build, not the shared client/dist)` in the banner); `npm run build` rebuilt the shared `webui/client/dist` from the same sources |
| `webui/smoke.py`, full, against a `--sandbox` bridge started immediately beforehand on port 8765, alone on the machine | **602 screenshots, 5 failures, 0 browser console/page errors, 0 unexpected server tracebacks**, over 584 page states. The five are the standing ones the prompt names: the four Settings registration `Locator.click` timeouts and `discovery.runs--default`. The cold-bridge flake (`fixup-d-sequence-rose`) did not occur. All 21 Analyse run states and all 58 Interrogation states pass; rule 9 measured **71 traces across 16 states, none flat, clipped or constant** (`webui/screenshots/fixup/H/smoke-result.json`) |
| `pytest -n 4` (conda), after smoke had finished — never together | **1952 passed, 17 skipped, 0 failed** (5 m 48 s) against 1878 / 13 / 0 after `K` (the README's 1874 / 8 predates `K`): +74 passed, +4 skipped (the four route tests, which need FastAPI). The failure set is empty |
| `tests/test_webui_*.py` + `tests/test_block_standard.py` under `webui/.venv` | **468 passed, 1 failed, 3 xpassed**: `test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers`, the standing failure the prompt names. All 11 of `test_webui_block_views.py` pass there |

**The gate caught a bug of mine that the targeted walk could not.** The first full walk failed every chain-run state
— including `J`'s, which I had not touched — with `AttributeError: 'GenericJob' object has no attribute
'frame_sources'` on `POST /api/runs`. The bridge keeps Discovery's and Training's jobs in the same table as chain
runs, and the pruning I added for held image frames read the attribute off every job. Walking only the Analyse
states (`--only zz_`) passed, because no Discovery job existed yet; the full walk runs Discovery first. Fixed in
`runs.py::prune_frame_sources`, pinned by `test_pruning_held_frames_survives_jobs_that_are_not_chain_runs`, and the
full walk re-run from a fresh bridge. It is the argument for never substituting a partial walk for the gate.

**Two harness changes, both because of what the longer walk exposed.**

- *A stream the client closes is not a failed request.* The run's event stream is closed by the client on
  `run_end`; when that beats the server's own end-of-response Playwright reports `net::ERR_ABORTED`. It shows only
  on runs short enough to lose the race — the dSAX chain, 0.1 s — which the walk did not have before.
- *A screenshot write is retried.* On the second full walk eleven page states "failed" with
  `[Errno 22] Invalid argument` while writing their PNG into the tracked tree — a different handful each run, never
  in a scratch directory, every page having already rendered and passed its assertions. I did not find what holds
  the files. `smoke.py::write_shot` takes the picture once and retries the write; the final run had none.

The numbers above are the **third** full walk, on the final tree. The first two are accounted for above; I am
reporting them rather than only the clean one.

The tracked screenshots under `webui/screenshots/pages/interrogation/` and `pages/zz_analyse_run/` are this gate
run's (the 27 new states, the regenerated Interrogation pages, and `null-shuffled.png` removed with the state it
belonged to); the rest of the tracked set is restored untouched.

## 13. In short

Thirty-one of thirty-six blocks drew through one generic view. Now all thirty-six — and any block added next
year — are drawn from their type signature: seven views keyed on the output type, twelve modifiers keyed on the
conversion, one component per view at both tiers, and a test that fails if a block falls through. Spans get a
slideshow on real samples with the impurity flag and a real hand-off to Review. The two nulls on the Aggregate
page were the data with noise on it and a bell curve; both are deleted and the page says it has none. Rule 9 runs
in a real browser on every type view.

Three things the researcher should know that were not in the prompt: only one of the three `scores → spanset`
blocks has a cut that can be dragged; no seed family spans two orders of magnitude (one is the ceiling, by the
detector's own floor); and the Slope page had been computing its rose angle with a different reference from the
core's, so the same event read −82° on one page and −35° on two others.
