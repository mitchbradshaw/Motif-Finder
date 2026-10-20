# night-analyse — the Event shape and Intervals pages, and the span-set slideshow band (2026-10-20 night)

Branch `night/analyse` (cut from main f1f1109). Commit prefix `night-analyse:`.

## In plain words

The Event shape page now leads with pictures instead of a wall of histograms. At the top, every event's shape is
drawn on top of the others, like tracing many signatures on one sheet of paper so that you can see whether they
share a shape. They are lined up on the moment each event changes fastest and coloured from early (blue) to late
(amber). Below that is the rose, as before. Then comes the signal the events came from. Under it, on the same time
axis, is one scatter plot of the measures. You choose which measures it shows with checkboxes, and pointing at a
dot gives its real value and marks that event on the signal. The Intervals page now draws the signal with every
detected region coloured by its class. In place of the histogram it has a scatter of "how long until the next event
of the same class". A small table answers "after a small event, what comes next?". In every span slideshow on the
Analyse block pages, the detection is now one blue band with a little context either side, and the blue and red
lines are gone.

## Assumed

- **The histograms are folded, not deleted.** On the Event shape page the measure histograms moved behind the page's
  "more" toggle, beside the table and the rules. They are off the face, and the states that open "more" still find
  them.
- **The overlay's waveforms are read from the recording.** They come from the same window route the slideshow
  uses. The page does not read them from the block's input trace, because the bridge holds no trace for a payload,
  and tonight's rules forbid core or cache changes. Each waveform is z-scored on its own, so a baseline offset does
  not matter. When the block is told the chain inverted the signal (`upstream_inverted`, as in
  `spike_event_features`), the overlay is drawn upside down so that it reads like the inverted signal beneath it,
  and the key says so. The signal panel IS the block's input: the nearest upstream Signal, the page's ghost.
- **One read when it can.** A span of up to 16,000 samples (W1's 4 h at 1 Hz is 14,400) comes back sample for sample
  in one request, and every event is cut from it, up to 300 drawn and evenly sampled through time. A longer span is
  read one event at a time, four at once, with at most 100 drawn. The page says how many it drew and why.
- **The steepest slope** is the largest |np.gradient| inside onset → extremum when the bridge names them (`marks`:
  the fall the rose measures). Otherwise it is taken over the whole span.
- **An event's time** on the shared axis is its onset (`marks.onset_s`), else its span's start.
- **The scatter shows three measures by default:** amplitude, duration and max slope, or the first three present.
  Every other measure has a checkbox. A measure with no value on any event gets no series.
- **"Time until the next event of the same class"** is a new append-only payload field,
  `interval_classes.next_within_gap_s`. For each event it holds the `within_gap_s` of the next event of its class in
  its group, None for the last. That is the block's own timing read one event later, not a new measure. A payload
  without the field falls back to "time since the previous", and the title says so.
- **One set of class checkboxes** drives both the signal's regions and the scatter's series.
- **How the classes relate:** the recommended transition matrix. It shows counts and row percentages with a blue
  heat shade, and an InfoTip whose example sentence uses the page's own busiest row. It counts transitions in time
  order, inside one group only, the Intervals block's rule.
- **Slideshow scope:** every span-set slideshow on the Analyse block pages. Interrogation › Store's slideshow
  (`interrogation/SourcePage.tsx`) still draws onset and extremum lines. It is a store browser, not an Analyse span
  set, and it is outside my file list. Library's member slideshow already drew a band.
- **Smoke unit name:** `zzzzzzzzzzz_night_analyse.json`, as the brief names it. It sorts AFTER
  `zzzzzzzzzzz_a2_p4_seed.json` ('n' > 'a'), not before as the brief says. Its first state builds its own chain, so
  the order does not matter.

## Item 1 — Event shape (`interrogation.event_shape`)

**Found.** The page led with the rose and one histogram per measure, about a dozen cards. The bridge sends the
feature table, `marks` and the spans, but no waveforms. The upstream Signal is already on the page (the ghost).

**Changed.** New `analyse/views/EventShapeFigures.tsx` is the Event shape lead, top to bottom:
1. **The events' shapes, overlaid** (`motif-overlay`). Each waveform is z-scored and aligned on its steepest sample
   (`eventFigures.ts::alignOnSteepest`), coloured early → late with a key ("early ▬ late", the first and last
   times), and the number drawn and the cap are said in words. The event marked below is drawn in black.
2. **The rose**, unchanged.
3. **The input signal** (`event-shape-signal`: SpanSetView over the ghost) and, beneath it on the same x scale,
   **the measure scatter** (`measure-scatter`, new `views/MultiScatter.tsx`). There is one series per numeric
   measure, each drawn 0..1 over its own range, and the legend gives each series' real range. Checkboxes pick the
   series. Hovering shows the real value, its unit, the time and the event number. Hovering or clicking marks the
   event on the signal (amber outline and caret), on every series (a ring) and in the overlay.
4. The fold still holds the spans, slideshow, durations, table and rules, plus the histograms.

**On real data.** I drove `spike_event_features` on the example span (CH1_A1, 336–338 h) on the main-checkout
sandbox (way 2) with this client. The overlay was ready 0.25 s after the page opened (5 events, one read); the
machine was loaded by MiniRocket training, so timings are noisy. The hover tooltip read "event amplitude: 14.4 mV ·
at 336.899 h · event #1", with no console errors. Two fixes came from this drive and are in commit 45f220b:
- The overlay was drawn in the recording's frame while the signal below was the inverted input. It is now flipped
  when `upstream_inverted` is set.
- The σ labels were clipped at the left edge.

**Proof.** `tests/test_night_analyse_helpers.py` (conda python; Node runs `eventFigures.ts`):
- the steepest sample matches np.gradient, restricted to onset → extremum, and is lo for a flat trace;
- z-scoring;
- the per-series normalisation (a flat series sits at 0.5, a gap stays a gap);
- even sampling;
- the early → late ramp;
- source checks that the page draws the overlay, the signal and the scatter.

## Item 2 — Intervals (`interrogation.intervals`)

**Changed.** New `analyse/views/IntervalFigures.tsx` is the Intervals lead:
1. **The input signal, regions coloured by class** (`interval-signal`), with one checkbox per class
   (`interval-class-legend`). Clicking a region marks the event.
2. **The interval timeline**, unchanged, with its histogram off on this page. `IntervalTimeline` gains an optional
   `histogram` prop that defaults to on, so the other callers are unchanged.
3. **The per-class scatter** (`interval-scatter`). x = the event's time on the timeline's own scale (the same 8 px
   margins); y = the time until the next event of the same class in its group, each series 0..1. Hovering shows
   the real interval, e.g. "small: 11 min · at 337.090 h · event #2".
4. **Which class comes next** (`class-transitions`), e.g. "small → small 2 · 67 %, small → medium 1 · 33 %"
   (`eventFigures.ts::transitionMatrix`).

**Bridge (append-only).** `webui/server/serialize.py::_interval_classes` adds `next_within_gap_s`. There is no core
change and no cache-key change. Main's server code does not have the field yet, so the way-2 drive showed the
labelled fallback, "time since the previous event of the same class". With this branch's server the page reads
"until the next".

**Proof.**
- `tests/test_night_analyse_payload.py` (conda and webui/.venv): the next-of-class values on the depth-thirds
  fixture and inside groups, with the existing fields untouched.
- The transition-matrix tests in the helpers file: time order, not index order; an untimed event skipped; no
  transition across groups; a row with no successor has no percentages.
- `test_serialize_interval_classes.py` is still green.

## Item 3 — span-set slideshow

**Changed.** `SpanSetView.tsx::spanEvents` gives every span `band: [start, end]` with `highlight: true` and
`window: slideWindow(...)`, which is 15 % of the span's width either side, at least 3 samples, clipped to the run's
span. `onset` and `extremum` are null, so there are no vertical lines. `kit/Slideshow.tsx` adds an append-only
optional `SlideEvent.highlight`, drawn as a `var(--blue)` band at 16 % with a 3 px blue top edge (`slide-band`). The
frame note and the span legend say so. This covers every Analyse span-set page: SpanSetProcess, which serves
signal/scores/encoding → spans and the detectors, and the feature pages' fold. The two unused helpers
(`MIN_CONTEXT_SAMPLES`, `marksCoincide`) are removed. The `slideWindow` rule is pinned in the helpers test.

## Smoke states

**New unit `webui/smoke_pages/zzzzzzzzzzz_night_analyse.json`.** All 8 states pass on the way-2 sandbox (8767)
with this client, with 0 console errors and 0 server tracebacks:
1. `night-analyse-chain-runs`: `drop_event_features` is built and run on the example span; rows 4 and 5 draw.
2. `night-analyse-event-shape-motifs-rose-signal-scatter` (block 3): the overlay is ready with motif lines and its
   key, the rose is there, the signal shows its bands, and the scatter shows its series and checkboxes. No
   histograms are on the face.
3. `night-analyse-event-shape-pick-marks-everywhere`: clicking event 1 on the signal shows the caret, a ring on the
   scatter, the black line in the overlay, and "event #1 … marked".
4. `night-analyse-event-shape-pick-what-to-plot`: ticking FWHM adds the `fwhm_s` series.
5. `night-analyse-intervals-signal-scatter-transitions` (block 4): the class-coloured regions, the checkboxes, the
   timeline, the scatter, the transition table with its InfoTip and the stats table are all present. There is no
   histogram.
6. `night-analyse-intervals-hide-a-class`: unticking "small" removes the small regions and the small series.
7. `night-analyse-intervals-pick-marks-the-signal`: clicking a region shows "event #… marked".
8. `night-analyse-slideshow-band-not-lines` (block 2, the drop detector): the slideshow cards show `slide-band` and
   no red extremum line.

**Edited in place in `zzzzzzzzzzz_ig_pages.json`.** I changed the `_why`, `expect` and `expect_absent` fields and
kept the state names:
- `ig-pages-event-shape-leads-rose-and-histograms` now expects the overlay, the signal and the scatter beside the
  rose, and expects `feature-histograms` ABSENT on the folded face, because they moved into the fold.
- `ig-pages-intervals-timeline-gap-labels-and-legend` now expects `interval-signal`, `interval-scatter` and
  `class-transitions`, and expects `interval-histogram` ABSENT, because the scatter replaces it.

`zz_analyse_run`'s `fixup-h-features-not-spans` and `fixup-h-intervals-are-plotted` open "more" first, still find
the histograms in the fold, and are unchanged.

## Tests and gates (all from the worktree)

- **Red:** 955b7e9 (tests only). It was verified red after the pause: 13 failed. The 11 helper tests failed
  because `eventFigures.ts` and the new figure files did not exist; the 2 payload tests failed with a KeyError on
  `next_within_gap_s`.
- **Green, conda python:** `test_night_analyse_helpers.py`, `test_night_analyse_payload.py`,
  `test_serialize_interval_classes.py`, `test_import_boundaries.py` and `test_block_standard.py`: 250 passed.
- **Green, webui/.venv:** `test_webui_serialize.py` and `test_night_analyse_payload.py`: 43 passed.
- **Builds:** `tsc -b` passes; `vite build` passes.
- **Smoke, `--pages-only --only <unit>` on 8767** (the main checkout's sandbox, this client's dist):

  | unit | result |
  |---|---|
  | `analyse` | 47, 0 failures |
  | `zz_analyse_run` (with `_aa` and `_ac`) | 52, 0 failures |
  | `zzzzzzzzzzz_span_plot` | 6, 0 failures |
  | `zzzzzzzzzzz_ig_pages` | 14, 0 failures |
  | `zzzzzzzzzzz_night_analyse` | 8, 0 failures |
  | `interrogation` | 58, 1 failure |

  The `interrogation` failure is `fixup-d-sequence-rose`: the Sequence page was still "measuring the events of
  sequence 1…" when the 4 s settle ran out, on a machine loaded by MiniRocket training. I reloaded it on its own and
  the rose, the table and the rules painted in 1.4 s with no page error. That page uses `EventFeatures.tsx`, which
  this branch does not change. Treat it as a timing flake, but the manager should re-judge it at the gate.

## Open / for the manager

- The way-2 drive ran main's server, so `next_within_gap_s` was seen only in the unit tests. Walk
  `night-analyse-intervals-*` on a bridge with this branch's `serialize.py`; the scatter's title should then read
  "Time until the next event of the same class".
- The demo's W1 (`spike_event_features` on 12640, CH4_A2 377–381 h) was not driven. I drove the same template on the
  example span instead.
- Shared-stash incident (23:21). My `git stash pop` picked up REVIEW's stash, because the stash list is shared
  across worktrees. It applied nothing but one conflicted file, which I took back out of my worktree; a copy is in my
  scratchpad. The manager checked REVIEW's tree. I used no stash after that.
