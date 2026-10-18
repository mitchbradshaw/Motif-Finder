# ig-pages: report (interval-event-pages)

WORKTREE: C:\Users\mmebr\Documents\CNN\.claude\worktrees\agent-ab8a5d6761b1bcafd
BRANCH: worktree-agent-ab8a5d6761b1bcafd (base 9504e38)

## 1. Assumed

- **Q43, the intervals colouring rule:** I built recommendation (c) as the prompt states it. If every event has a
  family (a `family` column, every value >= 0), the events are coloured by family. If not, they are coloured by depth
  in thirds of its range (small / medium / large). If there is no depth, everything is one class and the legend says
  there is nothing to colour by. The legend always names the rule that was used.
- **"Family label" comes from the payload, not the Library database.** The class is the `family` column that
  `interrogation.event_families` writes and that later blocks carry through, shown as `family <n>`. The serializer
  has no database handle, so a Library family's display name (`library_label`) is not looked up. Events that are
  Library members but were never put through Event families fall back to depth.
- **"The detector's depth":** `|event_amplitude_mv|` (Event shape) when that column is present; otherwise the
  absolute value of the detector's span score.
- **The class statistics are computed on the server, not in the browser.** The table's numbers come only from the
  server (`interval_stats` in meta). Rather than add a `?within=` read, the serializer computes each class's
  statistics when it builds the payload. It runs the intervals block's own `measure()` with the group key
  `<upstream group>/<class>`, and that calls the core's `interval_statistics`. All classes ship in one payload, so
  switching class needs no extra request. The "Stop and report" condition did not trigger: everything needed is
  available from the SpanSet and its meta.
- **The distances written on the gaps are the server's** (`gap_s`, `within_gap_s`). The browser only places them.
  A label is drawn only when the gap is wide enough to hold it. The number of labels left out is printed, and every
  gap has a hover title.
- **Slope page folds the rules card as well as the readout and the per-event table.** The decision named only the
  table and the readout, but "the rest behind a toggle; the slope page likewise" covers the rules too. The anatomy
  card's rules-verdict chip stays on the face.
- **Aggregate's "wiring" fold is the generic-note callout** (the "Feature wiring →" link). The wiring popover itself
  still opens from the scaling card's "custom" button, which is a lead, so the feature-wiring smoke states are
  unaffected.
- **Which figures lead is decided by what the payload carries, never by the block's name** (the drawing standard
  in `registry.tsx`). A cycle stack means Cycle shapes, `trains` means Trains, `interval_stats` means Intervals, a
  rose means Event shape, and anything else gets the measure histograms. The Event-families lead (`families`) still
  comes first wherever it appears.
- **The timeline has at most six lanes.** With more groups than that (Trains with `write_group` gives one group per
  train), all events share one lane. Distances are still measured inside each group, and the histogram's subtitle
  says how many groups share the lane.
- **Trains `sizes` on an old cached run:** a run made before `train_sizes` existed rebuilds its sizes from
  `train_size_distribution`, in ascending order. The histogram does not need the time order.
- **Per-group and non-logISI trains:** when Trains runs per group, or uses the maxinterval or adamatzky rule, there
  is no single density to draw, so `log_isi` is null and `log_isi_note` says why. The page prints that note in place
  of the plot.

## 2. In plain words

Each interval or event page now opens on its two or three main figures, with everything else behind one "more"
button. The page remembers if you opened it. The Trains page finally draws what the Trains block calculates: how far
apart the events are, with the cut it chose; how big each train is; and where the trains fall in time. The Intervals
page has a new timeline that writes the gap between each pair of events on the gap itself. It can colour the events
by type (small drops purple, big drops green), and a selector restricts the gaps and the statistics to one type, for
example only small-to-small.

## 3. Files

Created:
- `webui/client/src/kit/Headline.tsx`: the Headline layout primitive.
- `webui/client/src/analyse/views/IntervalTimeline.tsx`: the intervals timeline, its controls, legend, statistics
  table and histogram.
- `webui/client/src/analyse/views/TrainsView.tsx`: the three trains figures. This file is not on the prompt's
  list; it is new and only mine.
- `tests/test_serialize_trains.py`, `tests/test_serialize_interval_classes.py`.
- `webui/smoke_pages/zzzzzzzzzzz_ig_pages.json`.

Modified:
- `Adapters/interrogation_trains.py`: one new meta key, `train_sizes`. No change to the algorithm.
- `webui/server/serialize.py` **(shared)**: `_trains` and `_interval_classes` are new functions, plus a
  `DEPTH_CLASSES` constant. In `_spanset` I added two lines after the `cycle_stack` branch. Nothing existing was
  reordered.
- `webui/client/src/api.ts` **(shared, append-only)**: `TrainsPayload`, `IntervalClasses`, and a merged
  `SpansetPayload` declaration at the end of the file.
- `webui/client/src/kit/index.ts` **(shared, append-only)**: one export line after `KitGallery`.
- `webui/client/src/kit/kit.css` **(shared, append-only)**: the `.k-headline*` rules at the end.
- `webui/client/src/analyse/views/registry.tsx`: a `fold` prop on `SpanSetProcess`, and the body of `SpansToSpans`
  rewritten. The `<Rose rose={p.rose} testid="rose-fan" />` expression is unchanged; it now sits inside the `rose`
  constant.
- `webui/client/src/interrogation/SlopePage.tsx`: the page wrapped in Headline and the readout moved into its own
  card. Both `<Rose …/>` call sites are untouched (`theRose`).
- `webui/client/src/interrogation/AggregatePage.tsx`: wrapped in Headline. The timeline now comes before scaling,
  stacked, and the tiles are one row of four.
- `docs/BLOCK_INTEGRATION.md`: one new row in the conventions table, for the trains payload.
- `webui/smoke_pages/interrogation.json` **(another unit)**: 14 slope and aggregate states now begin with
  `click_if headline-toggle[aria-expanded=false]` and a 300 ms wait. The elements they expect have moved behind
  "more". No expectation changed.
- `webui/smoke_pages/zz_analyse_run.json` **(another unit)**: `fixup-h-features-not-spans` and
  `fixup-h-intervals-are-plotted` get the same click_if prefix. The second state also expects `interval-timeline`.
- `analyse/EventFeatures.tsx`: not changed. The unused `EventFeaturesPanel` is still there.

## 4. What was built

1. **Trains payload.** `trains: {n_trains, sizes, log_isi: {edges, density, cut} | null, log_isi_note, lz, rule}`.
   It is emitted whenever meta carries both `n_trains` and `train_size_distribution`. `edges` are the log10-second
   points the adapter's KDE was evaluated on: a grid, not histogram bin edges; the name is kept from the prompt's
   contract. `cut` is `cut_s`, in seconds. `lz` is `lz_complexity`.
2. **Interval classes payload.** `interval_classes: {rule, rule_words, column, edges, classes[{key,label,n}],
   event_class[], event_t_s[], event_group[]|null, gap_s[], within_gap_s[], stats[class][group]}`. It is emitted
   whenever meta carries `interval_stats`. The per-event lists are capped the same way as the spans.
3. **Headline** (kit). Takes `page`, `leads` and `folded: {key, node}[]`, and draws a single "more (N)" toggle.
   Open or closed is stored under `localStorage['ub-headline:<page>']`, with try/catch around every read and write.
   Testids are `headline`, `headline-leads`, `headline-more[data-open]`, `headline-toggle[aria-expanded]` and
   `headline-folded`; each folded item is `[data-fold=<key>]`.
4. **Per page, leads and folds:**

| Page | Leads | Folded under "more" |
|---|---|---|
| Analyse › Event shape (`rose`) | the rose, then the feature histograms | the per-event table, rules, spans strip (+ legend, explain), funnel, slideshow, durations |
| Analyse › Intervals (`interval_stats`) | the timeline (gap labels, colour control, "intervals within", legend), the interval statistics table (class-restricted), the interval histogram (class-restricted) | the measures, the rose (if any), table, rules, spans, slideshow, durations |
| Analyse › Trains (`trains`) | log-interval density + cut, train-size histogram (+ LZ), the timeline with trains as bars | measures, table, rules, spans, slideshow, durations |
| Analyse › Cycle shapes (`cycle_stack`) | the stacked-cycle heatmap (its warnings and verdicts as before) | measures, table, rules, spans, slideshow, durations |
| Interrogation › Slope | anatomy plot (marks, notes, verdict chip), rose (or the overlay for a large family), ten-thumbnail strip | the readout (now its own card "Event … in numbers", with the units note), the rules card, the per-event table |
| Interrogation › Aggregate | the three histograms (one row), the event timeline, the scaling scatter + β; the stat tiles stay as a thin strip of four with CSV / Figures / Stage outlier | parameters, how each measure is defined, the feature-wiring note |
| Interrogation › Sequence | unchanged (rose first) | — |

   The page key for an Analyse block is `analyse-block:<stage>.<algorithm>`, so each block type keeps its own memory.
5. **Trains figures** (`TrainsView.tsx`). The density is drawn with kit `LineChart`; its x axis is labelled in
   seconds or minutes from the log10 grid, and the cut is an amber marker. The size histogram uses kit `Histogram`
   with one bin per integer size. The timeline draws each train as a bar from its first event's start to its last
   event's end, taken from the block's own `train_id` column; ticks in no train are grey.
   **Deviation:** the prompt says "trains marked on the spans strip". The spans strip is folded, so the trains
   timeline is a separate lead figure instead, and the strip itself is left alone.
6. **Intervals timeline** (`IntervalTimeline.tsx`). Events are drawn as ticks coloured by class. Small is purple
   `#8e5cf7`, medium amber, large green `#22a06b`. Families get a palette with purple and green first. A checkbox
   turns colouring off. The "intervals within" buttons are `all` plus `<class> to <class>`. Picking a class dims
   the other events, writes only within-class distances and underlines them, and switches the table to
   `stats[class]` (`interval-stats-within`) and the histogram to the within-class distances.

## 5. Tests

- Red 1: `3f7585d`, `tests/test_serialize_trains.py` (conda). 4 failed and 1 passed: three `KeyError: 'trains'`
  and one `KeyError: 'train_sizes'`. The passing test is the "no trains key on other payloads" case, which held
  already.
- Green 1: `e3dc0ab`. 5 passed (conda). `test_adapter_trains.py` and `test_webui_serialize.py`: 57 passed (conda).
- Red 2: `2109ad3`, `tests/test_serialize_interval_classes.py` (conda). 7 failed and 1 passed, every failure
  `KeyError: 'interval_classes'`.
- Green 2: `769dffb`. 8 passed (conda). `test_webui_serialize.py` and `test_serialize_trains.py`: 46 passed (conda).
- What the tests pin:
  - The trains key carries the adapter's numbers exactly (n, sizes, lz, density grid, cut).
  - Sizes come in time order.
  - An old meta without `train_sizes` still serialises.
  - Per-group trains have `log_isi` null, and the note says why.
  - Other spansets get no key.
  - Depth thirds, with their cut points and per-event classes.
  - Within-class distances skip the other classes.
  - The class statistics equal the core's `interval_statistics` over those distances.
  - The family rule, and its fall-back to depth when one event has no family.
  - Groups keep their own distances.
  - The no-depth case is a single class.
  - Payloads with no `interval_stats` get no key.
- Final runs:
  - webui venv: `test_webui_block_readout.py`, `test_serialize_trains.py` and `test_serialize_interval_classes.py`,
    27 passed.
  - conda: `test_import_boundaries.py`, `test_block_standard.py`, `test_adapter_trains.py` and
    `test_webui_serialize.py`, 282 passed and 1 failed. The failure was
    `test_adapter_trains.py::test_many_groups_and_many_events_run_in_linear_time`, a wall-clock budget. Re-run on
    its own it passed in 18 s. It failed under the shared machine's load; it is not caused by the change. The only
    adapter change is building a list of ints that already existed.

## 6. Smoke states (`webui/smoke_pages/zzzzzzzzzzz_ig_pages.json`, 14 states)

Every state closes or opens the fold with a `click_if` first, so it does not depend on the localStorage left behind
by earlier states.

1. `ig-pages-slope-leads-anatomy-rose-strip-rest-folded`: the slope page shows the anatomy plot, the rose card and
   the event strip, with "more (3)" folded. The per-event table, the readout and the rules card are absent.
2. `ig-pages-slope-more-reveals-the-table-readout-rules`: after opening, the per-event table, events table, readout
   and rules card are present.
3. `ig-pages-aggregate-leads-histograms-timeline-scaling`: hist-first, timeline card, scaling card and the tile
   strip are shown, with "more (3)" folded. Parameters, rules and the generic note are absent.
4. `ig-pages-aggregate-more-reveals-parameters-rules-wiring`: after opening, parameters, measure-rules and
   open-wiring are present.
5. `ig-pages-event-trains-chain-runs`: imports `event_trains` onto the example span and runs it. Waits up to 5 min
   for row-plot-6; rows 4, 5 and 6 should draw as spansets.
6. `ig-pages-trains-leads-density-sizes-timeline` (block/4): shows `trains-density[data-has-cut="1"]` with its
   plot, the sizes, and the timeline svg. The fold is closed and the table is absent.
   **Check on the walk:** if the example span's gaps have only one hump, logISI finds no valley and this reads
   `data-has-cut="0"`. That would be the data, not a fault; read the run before calling it one.
7. `ig-pages-trains-more-reveals-the-per-event-table`: after opening, the feature table is inside the fold, along
   with the spans, slideshow, durations and rules folds.
8. `ig-pages-event-shape-leads-rose-and-histograms` (block/3): the rose and the feature histograms are shown, the
   fold is closed, and there is no table.
9. `ig-pages-event-shape-more-reveals-the-table`: after opening, the table and the measure rules are present.
10. `ig-pages-intervals-timeline-gap-labels-and-legend` (block/5): the timeline has `data-rule="depth"` and
    `data-within="all"`, with at least one `interval-gap-label`, the legend rule, legend swatches, the stats table
    and the histogram. The fold is closed. **Check:** gap labels are drawn only where they fit. Trains groups make
    the timeline a single shared lane, but between-train gaps should be wide enough for a label.
11. `ig-pages-intervals-within-one-class`: clicks the second "within" button. The timeline's `data-within` should
    no longer be `all`, and either the class stats table or the empty note should show.
12. `ig-pages-intervals-more-reveals-the-table`: after opening, the table and the measures fold are present.
13. `ig-pages-cycle-shapes-chain-runs`: noise_threshold with Cycle shapes inserted at position 2, the same recipe
    as `w3-cycle-shapes-thumbnails`. Waits up to 3 min.
14. `ig-pages-cycle-shapes-leads-the-stack` (block/2): the cycle stack is shown and the fold starts closed. After
    opening, the feature table is inside the fold.

Existing states I changed (see section 3): `interrogation.json`, the 12 slope states and the 2 aggregate states
listed there, and `zz_analyse_run.json`, `fixup-h-features-not-spans` and `fixup-h-intervals-are-plotted`.

## 7. Gates run

- `tsc -b` passes. `vite build` passes; its only warning is the existing Gallery `INEFFECTIVE_DYNAMIC_IMPORT`.
- Python test files and interpreters are listed in section 5. I did not run the full suite or a browser smoke,
  as instructed.

## 8. Open questions and risks

- **Q43 is still with the researcher.** If they choose (a) or (b) alone, only `_interval_classes`'s rule branch
  changes. The page reads `rule` and `rule_words` and draws whatever they say.
- **Family names.** Events that are Library members but carry no `family` column are coloured by depth. Reading
  Library membership would need a database lookup in the serializer, which it does not have today.
- **Trains `edges`.** The name comes from the prompt's contract, but the values are KDE evaluation points, not
  histogram edges. A reader expecting bins should be aware of that.
- **Smoke states 6 and 10 depend on the walk's data:** whether the example span has a logISI valley, and whether
  any gap is wide enough to write on.
- **`polish-pass` restyles these pages next.** The fold toggle is a plain mono link, and the `.k-headline*` rules
  live in `kit.css`.
- **`library-family-actions` merges after this branch.** The three `<Rose …/>` call expressions are intact (two in
  `SlopePage` via `theRose`, one in `SpansToSpans`'s `rose` constant), so its one-prop edit should merge cleanly.
- **Research-question files.** No RQ file was updated. The change is display plus the within-class interval
  statistics, and it does not change what any RQ1 to RQ6 can answer.

## 9. Commits

See `git log --oneline 9504e38..HEAD`. This report is the last commit.
