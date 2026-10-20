# site-night-2026-10-20 — the researcher's second list, implemented overnight before the full walk (three agents)

**Read first:** `CLAUDE.md`; `docs/prompts/fixup/UX-1015-common.md` (worktree, no `DATA/`, interpreters, the client
toolchain through the junction, test-first, loud failure, no new dependencies); the "How you work against
real-sized data" section of `docs/prompts/changes/site-changes-2026-10-20.md` (fixture, the backup-API copy, the
main-checkout sandbox for real signals). Then your section. You run alone and the researcher is asleep: make the
choice your section recommends and write it under **Assumed**. Commit prefix is your section's; every commit ends
with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Why (the researcher, 2026-10-20 ~22:50, going to bed)

> some more changes for you to implement overnight, before your run. Some of these are essential to get right for
> the demo day tomorrow.

The demo (2026-10-21) is a LIVE walk of the site on the real database (`docs/DEMO_DAY.md`): W1 Explore › Signal →
Analyse chain (spike events: event shape, intervals, spike-train statistics) → Report; W2 a detection chain →
template → Discovery › Apply template → Review; W3 Library family → Seed search → Review; R1 the Map, R2 the
scoreboard. Main freezes at **09:00**; the full walk runs before that. **Hard rules tonight:**

- **No change under `Working/` or `Adapters/`, and no cache key changes.** The demo's runs are pre-computed and must
  be reused. Everything here is the client (`webui/client/`) and, where a page needs data the bridge does not send
  yet, an APPEND-ONLY field in a bridge payload (`webui/server/views.py`, `serialize.py`, a route's response) computed
  from what the bridge already reads. If an item cannot be done that way, report it; do not touch the core.
- **Hand back by 02:15** with what is done, committed and green; unfinished items go in the report. The manager runs
  a critic, then the gate, then the walk.
- Free RAM is 1–3 GB: ONE bridge of yours at a time, stopped when idle; one Playwright browser at a time; never
  `pytest -n`; never ports 8765 (the live demo bridge), 8766 (the manager's) or 8800.
- Ports: ANALYSE **8767**, DISC **8768**, REVIEW **8769**.

## ANALYSE — the event-shape and intervals pages, and the span-set slideshow (`night-analyse:`, port 8767)

Files: `webui/client/src/analyse/EventFeatures.tsx`, `webui/client/src/analyse/views/IntervalTimeline.tsx`,
`webui/client/src/analyse/views/SpanSetView.tsx`, `webui/client/src/analyse/views/ShapeViews.tsx`, the event-shape /
intervals / span-set entries of `webui/client/src/analyse/views/registry.tsx`, new files under
`webui/client/src/analyse/views/`, `webui/server/views.py` (append-only payload fields), `tests/`, a new smoke unit
`webui/smoke_pages/zzzzzzzzzzz_night_analyse.json` (sorted before `zzzzzzzzzzz_a2_p4_seed.json`; existing analyse
states edited in place only where your change alters them, each named in the report). `EventFeatures.tsx` is also
drawn by Interrogation › Sequence: keep that page working (check it).

1. **Event shape (`interrogation.event_shape`): fewer histograms, more picture.** The researcher: "too many
   histograms". Build, top to bottom:
   - **Above the rose plot, an overlay of the events' motifs:** every event's waveform normalised (z-scored per
     event) and aligned on its steepest-slope sample (the same slope the rose plot reads), coloured on a gradient
     through time (earliest → latest event, a sequential ramp with a small legend "early → late"). Cap the number
     drawn (for example 300, evenly sampled, said in words) so a 5,000-event span stays fast.
   - **The rose plot** as now.
   - **Below it, the original signal** of the span the events came from (the block's input trace, decimated as the
     signal views already do), and **beneath it on the SAME time axis a scatter plot**: one series per measure that
     used to be a histogram (amplitude, duration, slopes, …), each its own colour, x = the event's time, y = the
     measure. The series are normalised for display (each to 0–1 over its own range, said in the legend) so they
     can share one plot; a legend of checkboxes shows / hides each series ("pick what to plot together"); hovering
     a point shows the measure's REAL value with its unit and the event's time. Hovering or clicking a point marks
     that event on the signal above.
   - The collapsible "more information" section at the bottom stays as it is (the table, the rules).
   Numbers come from the payload; the page never re-derives a measure. If the bridge does not send per-event
   waveforms or the input trace for this view, add them append-only in `views.py` from what the step already
   produced (the step's input signal and the SpanSet / feature table), decimated and capped.
2. **Intervals (`interrogation.intervals`):** the interactive interval plot stays. Add:
   - **The original signal above it** (same time axis), with the detected regions highlighted on it, coloured by
     interval class (small / medium / large, whatever classes the payload has), each class toggleable.
   - **Instead of the histogram, a multi-series scatter in the event-shape style:** one series per class, x = the
     event's time, y = the time until the next event of the SAME class (normalised per series for display, real
     value and unit on hover), the same show/hide legend and hover-marks-the-signal behaviour.
   - **How classes relate:** the researcher invites something better than a scatter for "the intervals between
     classes and how they relate across classes". Recommendation: keep the per-class scatter AND add a small class
     transition matrix — for each class, what class the next event is, as counts and row percentages (a heat-shaded
     table, plain words in an InfoTip: "after a small event, the next one is small 62 % of the time"). If you have a
     clearly better idea, build it and say why under Assumed.
3. **Span-set slideshows: the blue vertical lines confuse.** In every span-set slideshow on the analysis block
   pages (and the span-set view's event thumbnails), draw the detection as a blue HIGHLIGHTED BAND across the whole
   span, with a little context either side (about 15 % of the detection's width, at least a few samples), instead of
   vertical lines at its edges. Check every place the slideshow component is used.

Gate units: `analyse`, `zz_analyse_run`, `zz_analyse_run_ac`, `zzzzzzzzzzz_span_plot`, `interrogation`,
`zzzzzzzzzzz_night_analyse`. Tests: a node-run test of any new pure helper (alignment on the steepest slope, the
per-series normalisation, the transition matrix), plus the payload fields under `webui/.venv`.

## DISC — the Discovery runs list (again), the seed-search cards, the map's top scrollbar (`night-disc:`, port 8768)

Files: `webui/client/src/discovery/chrome.tsx` (`RunRow`, `BandSetRow`, `CoverageStrip`), `webui/client/src/discovery/
RunsPage.tsx`, `webui/client/src/discovery/SeedPage.tsx`, `webui/client/src/discovery/seed/KeepCard.tsx`,
`webui/client/src/discovery/MapPage.tsx` (the level-3 scroll only), `webui/client/src/discovery/discovery.css`,
`webui/server/discovery.py` only for item 3's investigation if it finds a bridge bug (append-only, and say so),
`tests/`, new smoke unit `webui/smoke_pages/zzzzzzzzzzz_night_disc.json` (before `zzzzzzzzzzz_a2_p4_seed.json`).

1. **The runs list, exactly as the researcher drew it.** "Reports button should be just the report icon, each
   template box should contain, and be clearly fully visible — left column icon, then under the tag, e.g. 'seed',
   then under that the '1 of 3 ch' etc indicator but without the grey text; then middle column title as is, below
   bare info (how many found, etc); then right column 'x' close button in utmost right corner, beneath is select
   button, then report button beneath." So each run box is three columns:
   - **left:** the glyph; under it the kind tag (`seed` / `template` / `reference` / `draft`); under that the
     coverage cells with "1 of 3 ch" in the body text colour (not grey);
   - **middle:** the run's name (as now), under it the bare facts (found, channels, done time; the status line for a
     running / paused / failed run), and the extra actions a run can have (Run on the missing N, Import results,
     Retry, Open in Jobs) as small buttons here;
   - **right:** the × in the top-right corner; beneath it the A/B select box; beneath that the Report button as an
     ICON ONLY (file icon, with "Report" as its title and aria-label).
   Nothing is clipped at the 296 px column or at a 1024 px window: every box shows all of itself. The band-set row
   and the Seed page's draft row (with its rename pencil) follow the same three columns. Keep the smoke test ids
   (`run-row-*`, `report-*`, `pick-*`, `remove-*`, `run-missing-*`, `coverage-*`) or update every manifest and
   `webui/smoke.py` line that reads them.
2. **Seed search, the cards' text is cut off.** On *Choose the cut* the histogram's y-axis label "count" is clipped
   at the left edge; on *Keep the matches* "Turn the matches you choose …" and the buttons below it are squished.
   Fix both at the 1376 px page and at a 1024 px window; nothing overlaps, nothing is cut.
3. **"I get 49 matches, not 155, based on the recommended cut."** `docs/DEMO_DAY.md` W3 step 4 says the F-30 seed
   search in session "demo · talk" (M2_aug, 5 channels, 0–721 h) shows "1000 matches, the null's recommended cut,
   155 kept", and its kept run is `seed 056a5d`. The researcher, walking W3, got 49 at the recommended cut. Find why
   on the main-checkout sandbox (way 2; it copies the database, so the session's state and the kept run are there):
   is the preview on screen the same query as the kept run's (seed, channels, section, scale bank, exclusion, null
   draws)? Does the recommended cut come from a different null (the preview's 5-draw null versus the kept run's)? Did
   Settings › Nulls' α / correction change? Is it the page opening a different draft? Report the cause in plain
   words. If it is a client or bridge bug, fix it (no core change). If it is a real difference, make the page say
   which null and which cut the number comes from, so the talk's figure is reproducible, and write the exact steps
   that give 155 for the Demo instance session's click script.
4. **The map's level 3 (all datasets): the horizontal scrollbar at the TOP of the block**, above the dataset names
   (a thin scrollbar synced both ways with the table's own horizontal scroll), and the algorithm names stay pinned
   on the left while scrolling sideways (main already makes the row labels sticky — check it holds at level 3 with
   the top bar, and at levels 2 and 1).

Gate units: `discovery` (full walk), `zzzzzzzzzzz_site_runs`, `zzzzzzzzzzz_a1_coverage`, `zzzzzzzzzzz_a1_seed_search`,
`zzzzzzzzzzz_site_map`, `zzzzzzzzzzz_night_disc`.

## REVIEW — no lag between items, and the grouping tree by default (`night-review:`, port 8769)

Files: `webui/client/src/review/**`, `webui/client/src/api/review.ts` (append-only), `webui/server/review.py`
(append-only, and only if a cheap batch read is needed), `webui/client/src/library/GroupingPage.tsx` and its Library
grouping editor files for item 2, `tests/`, new smoke unit `webui/smoke_pages/zzzzzzzzzzz_night_review.json`.

1. **Review: "no noticeable lag between items in the queue at all — perhaps pre-load the 5 items ahead at all
   times".** Measure first on a 10 k-item queue (`tests/perf_fixture.py`) and on the backup copy of the real database
   (queue 28, 1,153 items; queue 31, the demo's): the time from a verdict key press (and from the next arrow) to the
   next item's card painted, and what it waits for (the item read, thumbnails, evidence, the 150 ms settle in
   `Inspector.tsx`, counts re-reads). Then keep the next FIVE items' reads warm at all times (and the previous one),
   so stepping renders from memory; drop the settle when the item is already in hand; never send a read for an item
   passed by fast stepping (night-a's rule, `review/store.ts`); bound the cache; keep the verdict-correctness rules
   of `review/judged.ts` and `writesInFlight()` intact (a verdict never lands on the wrong item; undo waits for a
   write in flight). Target: under 100 ms from key to next card, cold queue open aside. If the full change is too big
   or risky for tonight, land the safe part (the prefetch window) and report the rest.
2. **Library: the dendrogram grouping tree "on by default in add new grouping".** When the researcher adds a new
   grouping in Library (the grouping editor), the tree (Ward with the kept tree, its dendrogram panel and cut line)
   is the default and visible at once, not an option to discover. Check what "add new grouping" does today, make the
   tree the default there, and say in the report exactly what changed. (The manager will ask the Demo instance
   session to show the tree in W3.)

Gate units: `review`, `zzzzzzzzzzz_review_carry`, `zzzzzzz_ah_blind_test`, `zzzzzzzzzzz_an_library_tree`, `library`,
`zzzzzzzzzzz_night_review`.

## Report (each agent) — your final message, plus the file

`docs/prompts/changes/reports/night-<analyse|disc|review>-report.md`: **Assumed**; **In plain words** first; per item:
what you found, what you changed, the test that proves it and its interpreter; before/after numbers where an item is
about speed; smoke states added or edited, each with what it should show; `tsc -b` and `vite build` pass from your
worktree. Hand back with the branch, the commit list, and anything unfinished.
