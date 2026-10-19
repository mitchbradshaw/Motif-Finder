# night-pass-2026-10-19 — try to break the site before the morning walk (three agents, one brief)

**Read first:** `CLAUDE.md`; `docs/prompts/fixup/UX-1015-common.md` (isolated worktree, NO `DATA/`, never a junction or
copy pointing at `C:\Users\mmebr\Documents\CNN\DATA`, the interpreters, the client toolchain through the junction,
no new dependencies); then your section below. You run alone; open choices go under **Assumed**. Commit prefix
`night-<letter>:`; every commit ends with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Why (the researcher, 2026-10-19 evening, going away for the night)

> Complete all necessary tasks tonight autonomously, make sure the website runs well. Send agents on a final pass to
> try and break the website, test edge cases, critique polish and load times, and implement fixes before the smoke
> walk in the morning.

Demo day is 2026-10-21. Main (0ffadd5) holds today's whole wave: the speed pass, the corpus-map worker, thirteen
feature prompts, the small fixes. Nothing has been used in anger yet. Your job is to USE it like a tired researcher
would, find what breaks or lags, fix what is small, and report the rest with reproductions.

## How you drive the real site from a worktree (the AR agent did this)

- Build the scale fixture: `tests/perf_fixture.py` (from AR) builds a database with 16 channels, runs, detections,
  annotations, a 10 k review queue and templates, with small synthetic `.npy` traces — look at how
  `tests/test_webui_ar_speed.py` and `scripts/perf_routes.py` call it; a smaller variant is fine for interaction
  tests, the full one for load times. Build it under your worktree's `webui/runtime/` or a temp dir.
- Build your client once: `node "C:/Users/mmebr/Documents/CNN/webui/client/node_modules/vite/bin/vite.js" build`
  from `<worktree>/webui/client` (your own `dist`).
- Start your own bridge: `"C:/Users/mmebr/Documents/CNN/webui/.venv/Scripts/python.exe" webui/run_server.py
  --sandbox --port <your port> --db <fixture sqlite> --dist <worktree>/webui/client/dist` from your worktree root,
  `PYTHONIOENCODING=utf-8`. Ports: A 8767, B 8768, C 8769. Never 8765 (the researcher's) or 8766 (the manager's).
- Drive it with Playwright through the conda python (`"/c/ProgramData/anaconda3/python.exe"`, `from playwright.sync_api
  import sync_playwright`, headless chromium): navigate, click, type, read the DOM, collect `console` errors,
  `requestfailed`, and timings (`performance.now()` around navigations; `page.on("request")` counts). Screenshots go
  under your worktree's `webui/runtime/night/` (never the shared `webui/screenshots`).
- Measure load times as: time to the page's main card painted (its `data-testid`), and the number of API requests
  in the first 10 s. Anything over 2 s to paint, or a page that keeps requesting with nothing changing, is a finding.
- Rules while you work: never `pytest -n`; never run anything against 8765/8766; no `npm install`; a fix is
  test-first and under ~60 lines, in your section's files only; a bigger problem is a REPORT item with a one-line
  reproduction and the file:line, not a fix. Fixes outside your files: report, do not touch.

## A — Review and Discovery (port 8767)

Files: `webui/client/src/review/**`, `webui/client/src/discovery/**`, `webui/server/review.py`, `webui/server/discovery.py`,
`Working/review/**`, `tests/`.
Break: a queue of 10 k items stepped fast with the arrow keys (does a stale prefetched item ever show? does a verdict
land on the wrong item?); a verdict on an overlap set (every member written; undo removes exactly them; the carried
rows on other runs); the class label; an empty queue, a queue whose run was discarded, a queue with one item; the
blind-test page; the Discovery first paint (skeleton to content with no jump), runs hidden by default then shown,
the coverage strip and "run on the missing", the gauge with zero verdicts and with only seeds, the seed strip with
no preview / no runs / a preview but no cut, "Use these as detections" twice, Compare with a band set, the map's
poll while a run is going, the templates picker while the background scorer works (does it ever block? does
"rescoring" clear?). Load times for Runs, Seed, Compare, Map, Review inspector, Review queue open.

## B — Explore, Library, Analyse (port 8768)

Files: `webui/client/src/explore/**`, `webui/client/src/library/**`, `webui/client/src/analyse/**`,
`webui/client/src/interrogation/**`, `webui/server/explore_routes.py`, `webui/server/library.py`, `webui/server/corpus.py`
(`spans` only), `webui/server/serialize.py`, `tests/`.
Break: the Signal page on a channel with 90 k detections (first paint; the six band toggles; the editable edges with
nonsense, negative, reversed and out-of-range values; arrow-key steps), Take span → the seed picker → Review's
promotion panel (the path that worried the walk), send unjudged motifs with zero / many; Cross-channel: the overlay
with 16 channels, bold/faded, align by lag with zero lags, a box across it and every action; mark artifact on
selected channels; Library: build sequences with no members / with a tolerance of 0 / keep twice, the sequence
family page, pick a trace and each action, cluster into the slideshow, the rose reference with no accepted motifs,
the atlas's two-second groupings re-read (`/api/library/groupings` ×10 in 20 s — find the cause and fix it if it is
under 60 lines); Analyse: the templates accordion with search, the chain page import states, the block pages' fold
toggle persistence, the trains figures with one event, the intervals timeline with 0 / 1 / 2 events and equal
depths, the span-set outline. Load times for Signal, Cross-channel, Atlas, Family, the chain page, three block pages.

## C — Polish and load, site-wide, report first (port 8769)

Files you may EDIT: `webui/client/src/kit/**`, `webui/client/src/shell/**`, `webui/client/src/theme.css`,
`webui/client/src/*.css` at the workspace level, `webui/client/src/App.tsx`, `tests/`. Every other page: REPORT only
(A and B own them tonight; a page fix you want goes in your report with the diff you would make).
Do: walk every route in the app (the list is in `webui/client/src/App.tsx` and each workspace's `index.tsx`) on the
fixture bridge at 1440×900 and at 1024×700; for each page record: time to its main card, API requests in the first
10 s, console warnings/errors, any element that moves after first paint (compare two screenshots 1 s apart), any
`⚠`, the number of `.muted` text nodes in the main card, grey buttons that are enabled, text that overflows its box,
a list with no empty state, a failure path with no red card (navigate to a bad id on each page), and the add-block
pop-up's right-hand text. Then rank the findings by how often the researcher's workflow passes the page (Review
inspector, Discovery runs, Explore signal, Analyse chain first) and fix in your files what is site-wide (a kit
primitive, the shell, the theme, a layout jump the shell causes); everything else goes in the report as a table:
page · finding · severity · the one-line fix · the file.

## Report (each agent)

`docs/prompts/changes/reports/night-<letter>-report.md`: **Assumed**; what you drove (the script is committed under
`scripts/night/` so the manager can re-run it against the real database); the findings table (fixed / reported);
the load-time table; tests added and the interpreter that ran each; `tsc -b` and `vite build` from your worktree
must pass before you report. Hand back with the branch, the commit list, and the three worst things you could not
fix.
