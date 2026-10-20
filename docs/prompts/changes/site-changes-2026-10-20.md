# site-changes-2026-10-20 — the researcher's list on the eve of the demo (three agents, one brief)

**Read first:** `CLAUDE.md`; `docs/prompts/fixup/UX-1015-common.md` (worktree, no `DATA/`, interpreters, the client
toolchain through the junction, test-first, loud failure, no new dependencies). Then your section. You run alone: an
open choice is made the way your section recommends and written under **Assumed** at the top of your report. Commit
prefix is your section's; every commit ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Why (the researcher, 2026-10-20 afternoon, with screenshots)

> discovery needs adjusting, home page runs look messy, select algorithms messy, scoreboard list needs scrollbar and
> max items viewed at once · can map load speed be improved? datasets map view cuts off · for single channel map
> view, option to plot signal over detection map · map: option to hide algorithm row / hide channel column · map: on
> viewed detection algorithm cells, option to cluster/sort by for rows, columns at all scales · explore cross channel
> overlaid signals is great, apply template in discovery gives errors · cross channel: make overlay plot by default ·
> cross channel plotting errors? · pulled span into analyse, loading forever, whole website lagging, working again
> after ~2 minutes · all detections say grey button "send 0 unjudged to review" · seed search: get rid of "run the
> preview first" next to steps 3 and 4, don't jump to step 2 by default, easy to rename a seed from "seed 4e67g",
> "drag the handle" under choose cut is misaligned · once queues in review get to 0 they should be removed · project
> startup first try always cancels with a phantom ctrl-c · session naming convention should change when the dataset
> changes · Discovery changes are most urgent.

Demo day is **2026-10-21**. The examiners' demo runs from a separate copy (`CNN-demo`, port 8800), so main is free to
move today, but every change must leave the existing flows working: a fix that breaks a smoke state the manager has
to chase tonight costs more than it saves.

The manager takes: the Review queue list (finished queues hidden), the four seed-search items, the startup Ctrl-C.
Do not edit `webui/client/src/review/**`, `webui/client/src/discovery/SeedPage.tsx`, `discovery/seed/**`,
`webui/start.ps1`, `webui/run_server.py`.

## How you work against real-sized data (in addition to the common rules)

- **A fixture first.** `tests/perf_fixture.py` builds a 16-channel database with runs, detections, annotations,
  review queues and small synthetic `.npy` traces (see how `tests/test_webui_ar_speed.py` and
  `scripts/perf_routes.py` call it). Your own bridge: `PYTHONIOENCODING=utf-8
  "C:/Users/mmebr/Documents/CNN/webui/.venv/Scripts/python.exe" webui/run_server.py --sandbox --port <yours> --db
  <fixture sqlite> --dist <worktree>/webui/client/dist`, from your worktree root.
- **Timings on the real shape — allowed read-only, two ways and no others.** (1) Copy the real database with SQLite's
  backup API (`sqlite3.connect('file:C:/Users/mmebr/Documents/CNN/DATA/db/annotations.sqlite?mode=ro', uri=True)
  .backup(dst)`) into your worktree's `webui/runtime/`, and run YOUR bridge on that copy (`--sandbox --db <copy>`);
  signal reads fail there (no `.npy`), counts and maps do not. (2) To reproduce something that needs real signals,
  run the MAIN checkout's bridge in sandbox mode, which copies the database and redirects every cache: from
  `C:/Users/mmebr/Documents/CNN`, `webui/.venv/Scripts/python.exe webui/run_server.py --sandbox --port <yours> --dist
  <your worktree>/webui/client/dist`. That serves main's server code with your client. Stop it when done. Never
  `--project`, never a junction, never write under the main checkout.
- Ports: MAP **8767**, RUNS **8768**, X **8769**. Never 8765 (the researcher's, on the real database), 8766 (the
  manager's gate) or 8800 (the demo).
- Drive pages with Playwright through the conda python (headless chromium): click, read the DOM, collect console
  errors and timings. Screenshots under your worktree's `webui/runtime/site/`. Never `pytest -n`; no `npm install`.
- Smoke: add your states to `webui/smoke_pages/<your unit>.json` (one state per line, like the files beside it) and
  list in the report what each should show. Existing states that your change legitimately alters are edited in
  place, each named in the report with why. The manager walks your units at the gate.

## MAP — the detection map (`site-map:`, port 8767)

Files: `webui/client/src/discovery/MapPage.tsx`, the map rules in `webui/client/src/discovery/discovery.css`
(`.dsc-map*` only), `webui/server/discovery_map.py`, `Working/discovery/detection_map.py`, the map readers in
`webui/client/src/api/discovery.ts` and `webui/client/src/api.ts` (append-only), `tests/`, `webui/smoke_pages/`
(new unit `zzzzzzzzzzz_site_map.json`; the map states in `discovery.json` only if your change alters them).

1. **Speed.** Level 3 (all datasets) is cached since 7ceea4f (served at once, recomputed in the worker). Levels 2
   (one dataset's channels, in 1/2/4/8 slices) and 1 (one channel's timeline) are computed on every read. Time all
   three on the backup copy (cold, warm, after a change), find where the time goes, and make levels 2 and 1 answer
   in under a second warm — the same fingerprint-keyed cache and stale-while-recomputing pattern as level 3
   (`discovery_map.py`), or derived from one pass. Also time the CLIENT: first paint of level 3 with ~50 rows and
   ~70 columns of `<button>` cells. Report before/after in a table.
2. **The datasets view cuts off on the right** (screenshot: `L_LM_Jul_26_J_ra…` clipped, no way to reach it). The
   table scrolls horizontally inside the card with the row labels and the header rows sticky, and the page width is
   used: no column is ever unreachable.
3. **Hide a row / hide a column.** Each algorithm row and each channel column (and a whole dataset at level 3) can be
   hidden from its label (a small × or eye on hover). Hidden ones are listed on one line above the table ("hidden: …
   · show all"), each a button that brings it back. Kept in the URL (`hide=` / `hidecols=`), so a link reproduces the
   view; the human row can be hidden too.
4. **Sort / cluster rows and columns, at every level.** A `rows` control: *as listed* (today's order) · *name* ·
   *most detections* · *cluster*. A `columns` control at levels 3 and 2: *as recorded* · *name* · *most detections* ·
   *cluster* (at level 3 the channels sort within their dataset; at level 2 a channel's time slices stay in time
   order and move as one; level 1's columns are time and do not sort). *Cluster* orders by similarity of the shaded
   values: average-linkage hierarchical clustering on correlation distance of the rate vectors, rows (or columns)
   in dendrogram leaf order, the human row pinned first. Compute it in the browser from the cells already drawn
   (it is ordering, not a new number); no new dependency, a small helper with its own test. In the URL (`rsort=`,
   `csort=`). Sorting reads only the cells shown (hidden rows and columns are left out).
5. **The signal under the single-channel map (level 1).** A `signal` toggle in the level-1 header (default on): the
   channel's own trace drawn on the same time axis as the rows, as a strip above the first row, about 60 px tall,
   from the bridge's decimated overview (reuse the read the Discovery scope strips use, `getOverview` /
   the corpus overview route, at the level's width; no new full-resolution read). Mouse readout extends to it (the
   value range in that bin). A held-out recording refuses it in words.

Gate units: `discovery` (map states), `zzzzzzzzzzz_corpus_map`, `zzzzzzzzzzz_site_map`.

## RUNS — the Discovery Runs page (`site-runs:`, port 8768)

Files: `webui/client/src/discovery/RunsPage.tsx`, `webui/client/src/discovery/chrome.tsx`,
`webui/client/src/discovery/session.ts`, `webui/client/src/discovery/AddTemplateModal.tsx`, the non-map rules of
`webui/client/src/discovery/discovery.css`, `webui/server/discovery.py` (scoreboard, session, apply), the Discovery
readers in `webui/client/src/api/discovery.ts` (append-only), ONE line of `webui/client/src/explore/CrossChannelPage.tsx`
(the *Apply a template across these N channels* link, item 5), `tests/`, `webui/smoke_pages/` (new unit
`zzzzzzzzzzz_site_runs.json`; existing Runs states edited in place where your change alters them).

1. **The runs list is messy** (screenshot: in the 296 px column the name is cut to `dip_se…` or vanishes, *Report*
   and *Run on the missing 14* overlap the text and each other, the coverage cells wrap under a ragged edge). Lay a
   run row out as: line 1 the glyph, the run's name (two lines at most, then an ellipsis with the full name on hover)
   and the A/B pick box and × at the right; line 2 the kind badge and its detail; line 3 the status line; line 4 the
   coverage strip; line 5, only when there is one, a row of small actions left-aligned (Report, Run on the missing N,
   Import results, Retry, Open in Jobs). Nothing overlaps at 296 px or at 1024 px window width; every name is
   readable. Look at the band-set row and the draft row on Seed search with the same eye.
2. **The algorithm picker in "Where each run fires" is messy** (screenshot: a wall of ~50 eye-off links under the
   rows). Replace the wall with one button in the card head, *Runs drawn: 6 of 52 ▾*, opening a popover: a search
   box, the runs grouped by kind (templates, seed searches; band sets folded), each a checkbox with its colour swatch
   and found count, *show all* / *hide all* inside. The drawn rows keep their eye to hide them. Keep the existing
   test ids that smoke uses (`fires-eye-<key>`, `fires-show-all`, `fires-hide-all`, `fires-hidden`) on the new
   controls, or update every manifest line that reads them.
3. **The scoreboard needs a scrollbar and a limit.** At most ten run rows visible; the table body scrolls past that
   with the header row sticky; an expanded run's channel rows scroll with it. Sorting still works.
4. **"Send 0 unjudged to Review" on every run.** The count is `found − judged` from the scoreboard, and the
   scoreboard printed *no finished run on this scope yet* while the browser was showing that run's detections — so
   the scoreboard's answer was empty or not in yet. Find which (suspects: the first read goes out with no run keys
   before the runs load and its `[]` stays on screen while the real read takes minutes on 16 channels x 52 runs; or
   the read itself drops the runs). Fix the cause; then: while the scores are being worked out the table and the
   button say so ("working out the scores…", the button disabled with that reason), never "0" or "no finished
   run". If the cold scoreboard on the backup copy takes more than ~10 s, time it and make the button's count come
   from a cheap read of its own (the queue route already counts unjudged on send), so sending never waits for the
   whole scoreboard.
5. **Apply template from Cross-channel errors.** *Explore › Cross-channel › Take it further › Apply a template across
   these N channels* opens `discovery/runs?modal=add-template&channels=667,668,669,666` — channel IDS, and no
   recording — so the session (still on M2_aug) asked M2_aug for channels named `667…` (screenshot: "no channel(s)
   ['667', '668', '669', '666'] on M2_aug_concat_fs1" on three cards). Fix the link to pass `recording=<key>` and the
   channel NAMES, and make a deep-linked scope (`?recording=` / `?channels=`) become the session's scope through the
   same `putScope` write the Scope card uses (so the template is applied where the page says it will be), with the
   section clamped to the new recording and the query keys cleared after the write. A name that is not a channel of
   the recording is refused in words, not sent.
6. **The session's name.** Every session is named `<recording stem> screen` by the bridge (one session per
   recording; changing the recording opens that recording's session). The page kept the OLD name after a change of
   recording because `setScope` merges the patch into the client's copy and never takes the bridge's answer. Take the
   session from `putScope`'s response (name, scope, null). Rename the default to `<dataset display name>` without
   "screen" for NEW sessions only (existing rows keep their names). The scope summary chip beside it has a chevron
   that promises a menu and only scrolls: drop the chevron (it stays a button that jumps to the Scope card).

Gate units: `discovery`, `zzzzzzzzzzz_a1_coverage`, `zzzzzzzzzzz_a1_polish_discovery`, `zzzzzzzzzzz_a1_ar_speed`,
`zzzzzzzzzz_ux1015_zal_send_one`, `zzzzzzzzzzz_site_runs`.

## X — Cross-channel and the Analyse lag (`site-x:`, port 8769)

Files: `webui/client/src/explore/CrossChannelPage.tsx` (not the *Apply a template* link — RUNS owns that line),
`webui/client/src/explore/Overlay.tsx`, `crossScale.ts`, `webui/server/explore_routes.py` (cross-channel),
`Working/cross_channel.py`, the Analyse span-import path (find it: the *Open in Analyse* / *Take span → Analyse*
links into `analyse/chain`, `webui/client/src/analyse/**`, `webui/server/analyse_routes.py`, `chain.py`) for item 3
only, `tests/`, `webui/smoke_pages/` (new unit `zzzzzzzzzzz_site_x.json`; the cross-channel manifests edited for item 1).

1. **Overlay by default.** Cross-channel opens on the overlay (every channel on one axis); `?view=stacked` is the
   stacked rows. Every existing smoke state that opens `explore/cross-channel/...` without a `view=` and checks the
   stacked view gets `view=stacked` added (a script over the manifests, one line each, layout preserved; list them).
   One new state shows the default is the overlay.
2. **Plotting errors.** Screenshot: `CO_fs2.mat` CH1, *window #1 · detection 6236294 · span at 0.00 h · 60 s*, pad
   20 s, detrend linear, overlay, four channels: CH2 drew no trace — a flat orange line across the window and one
   near-vertical orange stroke at about +33 s — and every channel carries a straight horizontal line at the top of
   its band. Reproduce it on real data (way 2 above), find the cause (NaN or a step in CH2? a clamp drawn as a line?
   an envelope with one point? the detrend on a window that starts at 0?), and fix it so a channel that cannot be
   drawn says why in words and one that can is drawn right. Check the stacked view on the same window. Then try the
   overlay on two more recordings and a 16-channel scope, and fix what else breaks.
3. **"Pulled a span into Analyse, loading forever, the whole website lagging, working again after ~2 minutes."**
   Reproduce: send a span to Analyse from Explore (Signal › Take span, and Cross-channel › Open in Analyse) on the
   main-checkout sandbox (way 2), within the first ten minutes after its start and after. Measure what the bridge is
   doing while the site lags (py-spy is not installed: use timings per route, `threading` stacks via a debug route
   you add only in your sandbox run and do not commit, the log). Known suspects: the corpus-map warm and the
   template-score warm run in the bridge after a start (`template scores warmed (64–140 s)`); a heavy span read on
   the request thread holding the GIL; the chain page reading a whole channel. Fix the cause if it is under ~80
   lines, test-first; otherwise report it with the file:line and the fix you would make.

Gate units: `explore` (cross-channel states), `zzz_w_cross_channel`, `zzzzzzzzzzz_aq_cross_channel`,
`zzzzzzzzzzz_overlay`, `zzzzzzzzzzz_explore_review`, `zzzzzzzzzzz_site_x`, and the analyse unit your item 3 touches.

## Report (each agent) — your final message, plus the file

`docs/prompts/changes/reports/site-<map|runs|x>-report.md` (this wave's exception to "write no report file"):
**Assumed**; **In plain words** (what changed for the researcher, two or three sentences, first); per item: what you
found, what you changed, the test that proves it and the interpreter that ran it; timings before/after where an item
is about speed; the smoke states added or edited, each with what it should show; `tsc -b` and `vite build` pass from
your worktree. Hand back with the branch, the commit list and anything you could not finish.

## The researcher's answers, after the brief (2026-10-20, ~14:40) — these override the sections above

- **MAP 3, hidden rows and columns:** "for a cleaner look, make hidden detection algorithm rows in the discovery map
  fall to the bottom rows on the map". A hidden row sinks below every shown row, dimmed and thin, its label readable
  with a button to bring it back; a hidden column sinks to the right end of its dataset (level 3) or of the table
  (level 2), narrow and dimmed. **Restoring a row or column puts it back in its original position** in the current
  order, not at the end. All three levels.
- **MAP 5, the level-1 signal:** a strip above the rows, at the **same height as the trace on Explore's Signal page**,
  "so that it is easier to see structure".
- **RUNS 6, the session name:** new sessions are named after the dataset (no "screen"); existing ones keep theirs.
- **The manager's Review item:** a finished queue is hidden under a fold and kept in the database, not deleted.
