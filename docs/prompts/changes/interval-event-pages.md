# interval-event-pages — three figures lead, the rest fold; the trains block gets its figures; intervals get a labelled timeline

**Read first:** `CLAUDE.md`; `docs/prompts/fixup/UX-1015-common.md`; then this file. Commit prefix `ig-pages:`;
every commit ends with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Test-first for anything in the
core or the bridge; the client work is gated by `tsc`, build and the smoke states.

## Why (the researcher, 2026-10-15 and 2026-10-18)

> Interval / event analysis pages: three headline figures, the rest behind a toggle; the slope page likewise. …
> For interval events show a timeline of labelled distances between events, with an option to colour-code events by
> similarity — e.g. small drops are purple, big drops are green — and then view intervals between those "families",
> e.g. between purple smalls, then between big greens.

## Facts (inventory, 2026-10-18)

- Routing `webui/client/src/interrogation/index.tsx:10-17`. The four interrogation blocks (`event_shape`,
  `intervals`, `trains`, `cycle_shapes`) are all drawn by `SpansToSpans` (`analyse/views/registry.tsx:415`) inside
  `SpanSetProcess` (`:181`): CycleStack (cycle_shapes only), feature histograms ("What was measured", `:439`), the
  slope rose (`:441`), the inter-event interval table (`:442`, `EventFeatures.tsx:74`, per group: events, median,
  mean, min, max, CV, R² trend, drift, LV, CV2), the per-event table (already in `<details>`), rules, the spans
  strip (`:214`), the slideshow (`:232`), the durations histogram (`:235`).
- Slope page `interrogation/SlopePage.tsx:59`: anatomy plot (`:338`), readout (`:382`), ten-thumbnail event strip
  (`:400`), rose (`:460`) or overlay for > 40 events (`:431`, Seg at `:435`), rules (`:470`), per-event table (`:508`).
- Aggregate page `interrogation/AggregatePage.tsx:108`: three rewireable histograms (`:416`), scaling scatter + β
  tile (`:458`, `:478`), event timeline (`:511`, `EventTimeline.tsx`, one lane per recording), parameters (`:519`),
  stat tiles (`:552`), measure rules in `<details>` (`:579`).
- Sequence page `interrogation/SequencePage.tsx:19`: rose, event table, rules.
- **Gap:** the trains adapter (`Adapters/interrogation_trains.py:142`) computes n_trains, the size distribution,
  the log-ISI density, its cut and LZ, but `serialize.py:279` passes only rules, rose and `interval_stats`, so a
  trains page shows only the generic histograms. `EventFeaturesPanel` (`EventFeatures.tsx:85`) is unused.

## Decided with the researcher (grilling, 2026-10-18)

- **Slope page leads with:** the anatomy plot, the rose (or overlay), the thumbnail strip. **Folds:** the per-event
  table, the readout.
- **Aggregate page leads with:** the histogram row (counts as one), the event timeline, the scaling scatter. The
  stat tiles stay as a thin strip. **Folds:** parameters, rules, wiring.
- **Block pages:** `cycle_shapes` leads with the stacked-cycle heatmap; `intervals` with the interval statistics
  table and the interval histogram; `event_shape` with the rose and the feature histograms; `trains` with the
  three train figures below. **Everything else folds** under one "more" toggle per page (the spans strip, the
  slideshow, the durations histogram, the per-event table, rules).
- **Trains figures, added:** the log-interval density with its cut line, the train-size histogram, and the
  timeline with trains marked as bars. The numbers already exist in the adapter; serialise them.
- **Intervals timeline (new):** a timeline of the events on the channel with the **distance between consecutive
  events written on the gap** (seconds or minutes, whichever reads), and a **colour-by-similarity** control:
  (a) the Library family label when the events are members, (b) otherwise bins of the detector's depth (thirds of
  the range: small, medium, large); a legend; and a **"intervals within"** selector that restricts the written
  distances and the interval statistics to one colour class (purple-to-purple, green-to-green) or shows all.
  (Recommendation (c) in the grilling, pending the researcher's confirmation of Q43 — build (c), note under Assumed.)

## The work

1. **Serialise the trains numbers** (`webui/server/serialize.py:279` and the adapter's payload contract in
   `docs/BLOCK_INTEGRATION.md`): `trains: {n_trains, sizes: [..], log_isi: {edges, density, cut}, lz}` — additive
   keys, old payloads still read.
2. **A `Headline` layout primitive** (`webui/client/src/kit/` or `analyse/views/common.tsx`): takes the lead
   figures and the folded ones, draws the leads full-width in order and a single "more (N)" toggle, remembered per
   page in `localStorage` so a researcher who opens the rest once keeps it open. Apply it on the four block pages,
   the slope page and the aggregate page as decided.
3. **Trains figures** in `SpansToSpans` when `p.trains` is present: the log-interval density (d3 line + cut rule),
   the size histogram (`Histogram` kit), trains marked on the spans strip.
4. **Intervals timeline** `analyse/views/IntervalTimeline.tsx` (new), used when the block is `intervals` or when
   `p.interval_stats` is present: events as ticks on a time axis, gap labels, colour-by control, within-class
   selector; the interval statistics table restricts to the selected class (compute in the client from the same
   event list the table already receives; if the table's numbers come only from the server, add
   `?within=<class>` to that read and say so). The class rule: family label if every event carries one, else depth
   thirds; the legend names the rule.
5. The sequence page keeps its rose first; nothing else changes there.

## Files

Yours: `webui/server/serialize.py`, `Adapters/interrogation_trains.py` only for the payload keys (no algorithm
change), `webui/client/src/analyse/views/registry.tsx`, `common.tsx`, new `IntervalTimeline.tsx`,
`webui/client/src/interrogation/SlopePage.tsx`, `AggregatePage.tsx`, `analyse/EventFeatures.tsx`, a kit primitive,
the pages' CSS, `tests/`. Do not change what any block computes.

## Method and gate

- Tests (conda, `tests/test_webui_block_readout.py` or a new `tests/test_serialize_trains.py`): a trains payload
  carries the three new keys with the adapter's numbers; an old payload without them still serialises.
- `tsc -b`, `vite build`. Smoke in `webui/smoke_pages/zzzzzzzzzzz_ig_pages.json`: each of the six pages shows its
  leads and the "more" toggle folded by default; opening it reveals the per-event table; the trains page draws the
  density with a cut line on the walk's trains run (seed one in your state as the AO/AK states do); the intervals
  timeline shows gap labels and the colour legend.
- Run your files plus `tests/test_webui_block_readout.py`, `tests/test_import_boundaries.py`.

## Stop and report if

the interval statistics per class need a server computation you cannot reach from the payload (describe the read).

## Report

`docs/prompts/changes/reports/ig-pages-report.md`: **Assumed**; per page the leads and the folds; the trains keys;
the timeline's class rule; tests; smoke states; what is left.
