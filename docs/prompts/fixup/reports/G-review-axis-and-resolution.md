# Report — Fixup G: Review draws on a real time axis, pads honestly, and can read the source recording

Run 2026-09-30 on `main`, in the main checkout, from base `faaefca` (the commit that wrote this prompt; `M`'s
migration already in). Commit prefix `fixup-g:`. The first commit, `9daab76`, touches only `tests/` and fails
fourteen tests; the implementation is `eaeffef` (bridge + core) and `5e78003` (client). Prompt `E` ran in
parallel in the same checkout the whole time (its interrogation files were uncommitted and mid-edit throughout);
the two prompts shared no source file, I built the client into a private dist and served it from a private
bridge on **8766**, and every commit was path-scoped.

**The defect, confirmed in the browser before anything changed.** Detection 102 (queue 2, `drop_detection_v1 -
Mushroom_260720 CH14`, `[2333, 2393)`), re-created at 1440 px: the context trace's minimum was **drawn at
2266 s = 0.629 h**, the band at 2333–2393 s, the axis 0.565–0.687 h — the researcher's screenshot to the pixel
(`webui/screenshots/fixup/G/before-q2-item-102.png`). The true minimum is **2383 s = 0.662 h**, inside the band.
After: drawn at 2383.0 s, inside the band, axis 0.565–0.748 h (`after-q2-item-102.png`). The detector was right
all along.

---

## 1. The payload shape, and why

Every trace the Review bridge serves is now a **`TimeTrace`** — `webui/server/review.py::_trace_env`,
`webui/client/src/api/review.ts::TimeTrace`:

| field | meaning |
|---|---|
| `t`, `v` | seconds (absolute in the item's recording) and mV, same length; a `null` in `v` is an all-NaN envelope bucket |
| `t0_s`, `t1_s` | the window's own edges (the exclusive end in seconds) — the x extent to draw, whatever the points cover |
| `fs` | the rate of the recording the points came from |
| `n_source`, `n_points`, `decimated` | samples in the window, points served, and whether the points are a min/max envelope |
| `px`, `capped` | the pixel budget served at, and whether the bound cost points |
| `unit` | `mV`, or null for an undeclared unit (nothing is drawn, as before) |
| `source` | which recording, which channel, what rate, and whether it is the item's own (`self`) or its parent (`parent`, with the decimation and offset) |
| `reason` | why the trace is empty, when it is |

It replaces `context: {values, t0_s}`, `shape: number[]` and the other-channels `values: number[]`. **The old
contract was the defect, so it is gone rather than kept beside the new one**: `api/review.ts::traceOf` turns a bare
value list from an old bridge into an empty trace *with a reason*, never a trace on a guessed axis, and
`tests/test_webui_review_axis.py` greps that the index slice and the bare-list types no longer exist.

Why interleaved `t`/`v` and not, say, a uniform `fs` plus a start: because `decimate.envelope` is **not uniform**
once a window exceeds 2 × px — each pixel-bucket emits its min and its max at their own sample times — and a
uniform axis would have to lie about where those points are. Why the window's edges travel separately from the
points: a context clipped at the recording's start, or one whose first bucket's extreme is not its first sample,
must still draw the band where the event is. Why `source` is on the trace and not on the item: the Shape card can
draw two different recordings for one item, and the card must say which one it drew.

**The one invariant, and where it is proved:** a trace and everything drawn beside it — the band, the crosshair,
the axis labels — are in one coordinate system, absolute seconds.

* `tests/test_webui_review.py::test_the_context_trace_carries_its_own_time_axis_under_decimation` — a synthetic
  channel with one unique minimum planted at sample 3055, a 660-sample context asked for at `px=100` (forced
  decimation): the served `t` at `argmin(v)` is 3055.0, inside the entry's own band. This is the test that would
  have caught U2.
* `tests/test_webui_review_axis.py` runs the client's slice under Node with a simulated 220-bucket envelope
  whose minimum is at 2382 s: after slicing, the minimum keeps its time and sits inside `[2333, 2393]`, and
  `t0 + index` — the old contract — is somewhere else.
* `webui/smoke.py` now measures it in a real browser on every run: `feature_in_band` (the context trace's lowest
  vertex lies inside the band rect) and `band_centred` (the band is the same distance from both plot edges), on
  the 102 states in `smoke_pages/review.json`.

The thumbnails (`QueueRow.thumb`) stay a bare value list on purpose: a sparkline with nothing drawn beside it has
no second coordinate system to disagree with (a default, §7).

## 2. Drawn versus true, measured in the DOM

`webui/screenshots/fixup/G/evidence.json`, produced by a Playwright script against the pre-change bridge (a
detached worktree at `faaefca` with a client built from the same commit, port 8767) and the after bridge (8766),
both sandboxes of the same database. "Drawn" is the x of the trace path's lowest vertex mapped back through the
plot's x extent; "true" is the time of the minimum of the raw samples (the after bridge at a wide `px`, where the
window comes back undecimated).

| item | window | context samples | | points served | axis drawn | minimum drawn at | true minimum | band | inside? | padding left / right (px) |
|---|---|---|---|---|---|---|---|---|---|---|
| **102**, q2, Mushroom CH14 | 2333–2393 s (60 s) | 660 | before | 440 | 2033–2472 s | **2266.0 s** (0.629 h) | 2383.0 s (0.662 h) | 2333–2393 | **no** | 785 / 207 |
| | | | after | 660, raw | 2033–2693 s | **2383.0 s** (0.662 h) | 2383.0 s | 2333–2393 | **yes** | 522 / 522 |
| **13**, run 28, Mushroom CH14 (600 s candidate) | 10095–10695 s | 1200 | before | 600 | 9795–10394 s | **10239.0 s** | 10685.0 s | 10095–10695 | **no** — the band ran off the axis | 575 / **0** |
| | | | after | 1200, raw | 9795–10995 s | **10684.0 s** | 10685.0 s | 10095–10695 | **yes** | 287 / 287 |

(The after positions are quantised by the 1200-px plot to about ±0.3 s for 102 and ±0.5 s for 13.) The long
candidate is the U3 symptom in the flesh: the old client drew 600 envelope points at one per second from `t0`,
so the axis ended at 10394 s and the band's right half — and the drop inside it — were off the right edge. That is
what "the padding is one-sided" was.

Padding at the three settings, item 102, after (`after-q2-item-102-pad{30,120,300}.png`):

| pad | axis | left / right (px) | points |
|---|---|---|---|
| ±30 s | 2303–2423 s | 287.0 / 287.0 | 119 |
| ±120 s | 2213–2513 s | 459.2 / 459.2 | 299 |
| ±300 s | 2033–2693 s | 521.8 / 521.8 | 659 |

## 3. Decimation follows the width

`CONTEXT_PX = 320` and `SHAPE_PX = 60` are gone. The client measures the column that will draw the traces
(`charts/useSize.ts` on a zero-height div inside the Review shell — `review/axis.ts::plotPx`: the column width
less 60 px of card padding and axis gutter, times `devicePixelRatio`, rounded up to 64 px so a resize by a few
pixels does not refetch, clamped to 320–4096) and sends it as `px`, with the padding shown as `pad_s`, on
`/items/{id}`, `/items/{id}/channels` and `/cluster/{no}`. **Nothing is fetched at a guessed width**: the first
fetch waits one frame for the measurement. The other-channels popover asks for 480 px (its plots are ~400 css px).

The bridge serves `decimate.envelope(px)` — up to 2 × px points — so a plot is never served fewer points than it
has pixels, bounded by `MAX_PX = 4096` (about 8 200 points, ~130 KB of JSON) with **`capped: true`** whenever the
width asked for exceeded the bound *and* the window had more samples than the bound serves. The card prints it
(`ResolutionNote`: "660 samples · 1 Hz · every sample drawn", or "1,200 samples · 2,432 points", or "capped at
4096 px" in amber).

Measured:

| window | before | after, at the 1440-px viewport (`px=1216`) |
|---|---|---|
| 102's context, 660 samples | 440 points (a third discarded for no benefit) | 660, raw, `decimated: false` |
| a 600 s candidate's context, 1200 samples | 600 points | 1200, raw |
| detection 985's shape, 45 221 samples (the latent `SHAPE_PX = 60` case; a run-71 queue made in the sandbox) | 120 points over ~380 px | 2 382 points at `px=1216`; 7 538 at the 4096 cap; `capped: true` when 100 000 px is asked for |
| 102's shape, 60 samples at 1 Hz | 60, raw | 60, raw — and dotted (§4) |

`tests/test_webui_review.py::test_the_resolution_follows_the_requested_width` pins the three regimes: raw when the
samples fit, at least one point per pixel when they do not, and `capped` with the served `px` below the request on
an absurd width.

## 4. The Shape card's staircase, dotted rather than smoothed

Not changed as a curve. A 60-sample candidate at 1 Hz is drawn as its 60 samples, and `Trace`'s new
`sampleDots` puts a dot on every vertex when they are at least 3 px apart, so the eye reads "one sample per
second" rather than "a rendering fault" (`after-q2-item-102-shape-source-off.png`). The InfoTip says so. Nothing
interpolates or splines: a curve implying samples the recording does not have is a fabrication, and `E` has just
removed one.

## 5. Source resolution (Q24, default ON)

`review.py::_shape_source`: when `recordings.parent_recording_id` links the item's recording to the one it was
decimated from, the Shape card is also served `shapeSource` — the parent's samples over the same window
(`parent_offset + start × decimation` to `parent_offset + end × decimation`), at the parent's rate, **in the
child's seconds** (shifted by `-offset / fs_parent`, so it lines up with the context card and the seconds axis
reads 0–60 s either way), converted through **`corpus.display_channel`** on the parent's own row. The parent is a
different `recordings` row with its own `units`; the test stores the parent in microvolts and the child in volts
and asserts both come out in millivolts (a 50 mV dip reads 50 mV from the parent and 46 mV block-averaged from the
child, not 50 000 or 0.05). The bridge refuses to offer a parent whose rate is not `decimation × fs` and says why.

The card (`parts.tsx::ShapeCard`): a `Toggle` "source resolution", persisted (`useDemoState`, default on), and a
line that says what was drawn —

* on: **drawn from L_LM_Jul_26_J_raw CH3 · 10 Hz · 600 samples · the 10:1 source of this recording**
  (`after-q2-item-102-shape-source-on.png` — a smooth 13.8 mV drop);
* off: **drawn from Mushroom_260720_0509_4hrs_CH14_fs1 CH14 · 1 Hz · 60 samples** (the dotted staircase, 13.5 mV).

**When there is no parent** — the common case — the toggle is present but **disabled, carrying the bridge's
reason** as its tooltip: "no higher-resolution source is registered for this recording"
(`after-q1-shape-no-parent.png`, the Library queue's first sequence on `M2_aug_fs1 CH1_A1`). Never present and
inert: `data-source-available="0"` and `[data-disabled-reason]` are what the smoke state asserts.
`test_the_shape_source_is_an_explicit_absence_without_a_parent` pins the payload half.

Only one recording in the database has a parent (385 → 542), so this is the edge case Q24 said it was; it costs
one 600-point trace on 130 items.

## 6. Review shifts a legacy row

`Working/review/queues.py::_resolve_detections` now passes each candidate through `absolute_bounds` with its
run's `span_start` (`_run_span_starts`, which `_prior_verdicts` already used — so the item now carries the same
coordinates its rediscovery check matched on). `queue_candidates` was not changed: the helper it needed was
already in the file. A no-op on today's database (`M` rewrote the 115 rows); a restored backup holds relative
rows again, and this class of defect has now been found in four readers.

`tests/test_review_queues.py::test_a_legacy_span_relative_detection_is_shifted_into_channel_indices`: an
in-memory database, a run spanning 5000–6000, a legacy row at 100–200 and an absolute one at 5300–5400; the
queue item for the first is 5100–5200 and the second is untouched. Synthetic on purpose — the real database no
longer has such a row, and `init_db()` would migrate one on open before a route could read it.

## 7. `kit/plots.tsx` stayed additive

Yes. `Trace` gained `t?: number[]`, `xDomain?`, `sampleDots?`, and overlays may carry `t?`; `MiniTrace` gained
`t?: number[]`. **A caller passing no `t` keeps today's behaviour exactly**: point `i` at `t0 + i / fs`, the axis
`[t0, t0 + (n − 1) / fs]`, the crosshair by index, MiniTrace's points spread evenly and its `band` in indices —
the code paths are the same expressions as before, chosen by `timed`. With `t`, every point sits at its own time,
the crosshair finds the nearest point by time (`charts/timeAxis.ts::nearestIndex`), and an overlay without a `t` of
its own is stretched across the x extent (the Shape card's medoid semantics, which `ShapeCard` already documented).
Interrogation's `MiniTrace` calls (`SlopePage.tsx:285`, `SourcePage.tsx:248`) and every other page's `Trace` call
pass no `t` and were not touched; `tests/test_webui_review_axis.py::test_the_kit_traces_take_a_time_axis_additively`
asserts `values`, `fs` and `t0` are still the props they were. The svg carries `data-t0`, `data-t1`, `data-timed`
so the smoke gate can measure the axis; nothing reads them at runtime.

## 8. When I took the machine

* **Evidence (Playwright, two bridges):** 13:33–13:41 — no pytest running.
* **Smoke, full run on 8766, bridge restarted immediately beforehand:** started **13:41:40**, finished
  **13:58:26** (16 min 46 s). No pytest of mine ran during it; I saw no `pytest` process of `E`'s in that window
  (`tasklist` showed none), and no `ERR_NETWORK_IO_SUSPENDED` in the log.
* **`pytest -n 4`:** started after smoke finished, **13:58:56–14:12:07** (13 min 11 s at `-n 4`; nothing else of mine ran, and no browser was driving either bridge).

## 9. The gate

1. **`npx tsc -b`** — **exit 0** at the end of the run, and zero errors in any file this prompt touched at every
   point. While `E`'s interrogation files were mid-edit (13:20–14:10) `tsc -b` reported four errors in them
   (`api/interrogation.ts:158`, `interrogation/SlopePage.tsx:183,414`, `interrogation/SourcePage.tsx:361`), which
   blocked `npm run build` (`tsc -b && vite build`) for everyone; I built the bundle I served with
   **`npx vite build --outDir <scratch>/dist-g`** (the same production build without the type-check step).
   `E` closed them before I finished, and **`npm run build -- --outDir <scratch>/dist-g-final`** — the gate's own
   script — **passes**.
   `webui/client/dist` was not touched by me. (It was rebuilt at 13:37 by `E`, and now carries my committed client
   code; see §10.)
2. **`webui/smoke.py --url http://127.0.0.1:8766`** against a `--sandbox` bridge on my private dist:
   **562 screenshots, 11 failures, 0 unexpected server tracebacks, 0 browser console/page errors.** All 25 Review
   states pass. The 11: `discovery.runs--default` (missing `browser-trace svg`), which **fails identically against
   the pre-change bridge** (`smoke.py --pages-only --only discovery --url :8767`, where it also misses the
   `where-fires` cells) — pre-existing; **six `analyse.interrogation*` states** whose testids
   (`overlay-window-note`, `upstream-event-shape`, `not-recovered`…) are prompt `E`'s, in flight in the same
   working tree my dist was built from — `E`'s to close; and the **four Settings `Locator.click` timeouts**
   (`datasets--import-check-*`, `models-registration--check-a-joblib`, `storage-backups--scan-check-a-matrix-profile`),
   the known registration-state failures every fixup report since `B` has carried. The six new Review states (`context axis: 102's drop sits inside its band`, the three
   padding states, and the three Shape-card states) pass; the smoke evidence records the measured band/vertex
   positions under `context_axis`.
3. **`pytest -n 4`**: **1799 passed, 7 skipped, 0 failed** (791 s) against `M`'s baseline of 1786 passed / 6 skipped /
   0 failed. Failure set before and after: empty. The +13 are this prompt's 8 conda-visible tests (the six bridge
   tests in `test_webui_review.py` run only under `webui/.venv`, where the whole file is **32 passed**) plus
   `E`'s; the extra skip is not in a file I touched. `test_webui_decimate.py::test_decimation_is_not_quadratically_slow`,
   the wall-clock test that fails under load, passed.

## 10. Defaults taken

* **`DEFAULT_PX = 1200`, `MAX_PX = 4096`** on the bridge; 320–4096 on the client; 64-px quantisation of the
  request. The bound is a payload bound (about 130 KB per trace at the cap), not a rendering one.
* **The pad travels to the bridge and a pad change refetches the item** (a ~50 ms round trip; the inspector keeps
  the previous data and dims while it loads). The alternative — serve ±300 s once and slice on the client — would
  have left a ±30 s view at a tenth of the point density on a decimated window. The client still slices by time
  (`sliceContext`), so a bridge serving more than asked is fine.
* **The thumbnail stays a bare value list** (§1). Its `MiniTrace` has no band and nothing beside it.
* **The toggle is persisted across items and sessions** (`useDemoState('review.sourceResolution')`), default on.
  Persisting it per queue seemed like a state nobody asked for.
* **The parent's channel is named by `corpus.channel_name`** — "CH3" for `recordings.channel = 2` of a
  five-channel file, the app's convention on Explore and in the other-channels popover. Settings › Datasets prints
  the same link as "CH2" (the raw index). That inconsistency predates this prompt and is noted, not fixed, here.
* **Block-mean alignment:** child sample `i` is the mean of parent samples `[off + 10i, off + 10i + 10)`, so the
  parent trace is placed at `(j − off) / 10` s and the child's sample `i` at `i` s — the child's sample sits at
  the *start* of its block rather than its centre, a 0.5 s question on a 60 s card. Not corrected: the context
  card and the band are drawn from the child only, so nothing on one card is offset against anything else.
* **`ResolutionNote` and `drawnFrom` print counts with `fmtInt`** and rates as integers when whole.
* **The other-channels `r` column** used to be `r.r!.toFixed(2)` on a value the bridge serves as `null` for every
  row; it now says "r not computed" rather than being one non-current row from a TypeError. Coherence in the span
  is still not computed (`07-review.md`'s artifact factors), and the card still says so.
* **The `E` collision that did happen:** `E` rebuilt the shared `webui/client/dist` at 13:37 from the working tree,
  after my client commit, so that dist now contains this prompt's client. I had been using it as the pre-change
  client for the "before" evidence (it dated from 2026-09-23 and no Review client file had changed since); when it
  changed under me I built the pre-change client from `faaefca` in a scratch directory instead (a temporary
  `node_modules` junction, unlinked straight after the build, never inside a git worktree). The pre-change Python
  ran from a detached worktree at `faaefca` with no junctions in it; it is removed at the end (§12).

## 11. Items left

* **Coherence `r` in the other-channels popover** is still not computed (not this prompt's; it now says so
  instead of throwing).
* **The parent's channel label** ("CH3" vs Datasets' "CH2", §10) — one convention should win, in a prompt that
  owns both pages.
* **The Shape card's medoid overlay is still index-stretched** across the candidate's duration (unchanged
  semantics); a medoid with its own `t` would now be honoured if a bridge ever sent one.
* The cluster page's `ContextCard` and member thumbnails take the same payload and are drawn the same way, but no
  queue on this database resolves a cluster (`07-review.md` R5), so it is exercised only by the type-checker and
  the shared code path.

## 12. Files

**In scope (the prompt's list):** `webui/server/review.py`, `Working/review/queues.py`,
`webui/client/src/review/{parts.tsx, Inspector.tsx, ClusterView.tsx, axis.ts (new)}`,
`webui/client/src/api/review.ts`, `webui/client/src/kit/plots.tsx` (additive, §7), `webui/smoke_pages/review.json`,
`webui/smoke.py` (extended: two checks and one hook line), `tests/test_webui_review.py`,
`tests/test_review_queues.py`, `tests/test_webui_review_axis.py` (new), `webui/screenshots/fixup/G/`, this report,
`07-review.md` R1, `QUESTIONS.md` U1/U2/U3.

**Out of scope, touched:** `webui/client/src/charts/timeAxis.ts` — **new** file in `charts/`, pure and import-free
(`nearestIndex`, `sliceWindow`, `drawable`), because the kit needs the nearest-point lookup and `review/axis.ts`
needs the slice and neither may import the other; `charts/domain.ts` (prompt `C`'s) is untouched and no y-domain
rule changed. `Working/database/queries.py` was **not** touched although the prompt allowed it (§6).

**Not touched:** anything under `interrogation/`, `api/interrogation.ts`, `interrogation_routes.py`,
`charts/domain.ts`, `decimate.py`, `corpus.py`, the fixtures, the stored rows.

**Cleanup:** both private bridges stopped; the detached worktree `scratchpad/before` removed with
`git worktree remove` after confirming it held no junction; the scratch `before-client` and the private dists are
session scratch.

---

## Chat summary

U1, U2 and U3 were one defect and it is fixed: the bridge served Review's decimated traces without their time
axis and the page drew the points one per second, so the trace was compressed against a band drawn in true
seconds. Detection 102's drop was drawn at 0.629 h and is at 0.662 h, inside its band — the detector was right.
Every Review trace now carries `t` beside `v`, is served at the width the card measured (660 samples come back
raw where 440 points used to), and is padded by time on both sides (287/287 px at ±30 s where a long candidate's
band used to run off the edge). The Shape card dots its samples instead of smoothing them and, with the new
source-resolution toggle (default on), draws recording 385's events from the 10 Hz parent and says so; without a
parent the toggle is disabled with the reason. Review also shifts a legacy span-relative row now, tested on a
synthetic one. The kit change is additive — Interrogation's calls are untouched. Fourteen new tests, six new smoke
states with a real-browser band/vertex measurement, before/after screenshots and the measured table in
`webui/screenshots/fixup/G/`. The gate: `tsc -b` clean, `npm run build` passes, smoke 562 screenshots / 11 failures none of them Review's (1 pre-existing Discovery state, 6 of `E`'s in-flight Interrogation states, the 4 known Settings timeouts), pytest 1799 / 7 / 0 with an empty failure set against the 1786 / 6 / 0 baseline.
