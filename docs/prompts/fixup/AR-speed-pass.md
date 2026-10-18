# AR — the speed pass: the web UI stays quick and smooth whatever the size of the data

**Read first:** `docs/prompts/fixup/UX-1015-common.md` (where you are, how to work, the interpreters, the client
toolchain through the junction, no smoke in a worktree, no `DATA/`) and `CLAUDE.md`. Everything there binds you. You
run alone; nobody answers questions. When a choice is open, take the defensible one, write it under **Assumed** at the
top of your report, and build it. Commit prefix `AR:`; every commit ends with
`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Why (the researcher, 2026-10-18)

> It is important the website runs quickly and smoothly, regardless of the size of the data/detections (more are
> coming!). I also noticed lag when going between items in the review queue — THIS needs to be snappy: reviewing
> 10,000 windows will otherwise take much, much longer than it needs to and be much more frustrating. When loading the
> Discovery page there is also a big "session loading" block, which disappears once the page loads, but makes all the
> icons jump and looks laggy.

The database today: 5.0 M detections, 3,313 runs, 68 Discovery runs, 73 templates, 12.6 k annotations, 687
adjudications, a Discovery session of 16 channels × 721 h with 52 runs. It will grow by an order of magnitude. Every
fix below must hold at that size: **O(items on screen) per interaction, never O(everything in the table)**.

## What is already known (measured 2026-10-18 on a sandbox copy of the real database, machine loaded)

| Route / interaction | Measured | Why (file:line) |
|---|---|---|
| Review: step to the next item | laggy at a few hundred items; will be worse at 10 k | `webui/server/review.py:708 get_item` runs `queues_mod.queue_items` over the WHOLE queue twice per request — `_item_or_404` (:371) to find one item, `_ranks` (:311) to number it — plus `_index` (:111, every recording) and `_queue_payload`. The client bumps `version` on every accepted verdict (`review/store.ts:161-179`), and `review/index.tsx:62` then re-reads `GET /queues/{qid}` — EVERY row with a thumbnail trace (`_entry_payload`, `THUMB_PX`) — after each verdict. Nothing prefetches the next item. |
| `GET /api/discovery/runs` | 10–13 s | `discovery.py:425 _run_payload` calls `fanout.group_status` per run (`Working/discovery/fanout.py:388`: `get_run` + `get_recording_by_id` + `COUNT(*) detections WHERE run_id` + `list_recordings(source_file)` per member run) |
| `GET /api/discovery/fires` (three channels, 52 runs) | 147 s before `ux-1018` moved the status read out of the channel loop; the per-channel `_regions_for` → `_run_detections` reads remain | `discovery.py:867-930` |
| `GET /api/discovery/templates` | > 60 s while the bridge's warm was rescoring; 0.2 s warm | `discovery.py:696` scores every detection template on each open (`_last_score`, `SB.score_runs_cached`); the warm (`discovery.py:666 warm_last_scores`, started by `run_server.py:107`) runs maps then scores in a daemon thread and competes with requests |
| `GET /api/corpus/<file>/coverage` (home page) | 100–224 s cold for M2_aug, 0.7 s from memory | `corpus.py:276 coverage` / `:346 _coverage` (`channel_divergence` over every channel × run); cache is memory only, lost on restart, keyed by `SB.channels_fingerprint` which any settings change invalidates for every file |
| Home page network-idle | > 30 s after a restart or after any run is written | the coverage recompute above; the smoke's `routes` step fails on it |
| Discovery first paint | a 600 px "loading the session" card, then the real layout: icons jump | `discovery/RunsPage.tsx:61` (`Loading height={600}`), the same pattern on `SeedPage.tsx:226` and `MapPage.tsx` |
| Client requests | no timeout, no abort | `client/src/api.ts:25 req()`; only jobs cancel |

Earlier perf work and its lessons: memory of the merged round is in `tests/test_perf_scoring_reads.py` (the
fingerprint caches in front of `score_runs` and `corpus.coverage`; **a read added to `channel_score` /
`channel_divergence` / `_coverage` must be added to the fingerprint or results go stale**; detections are
fingerprinted by id range on the assumption they are append-only; pass one `memo` per request when fingerprinting
many templates). Build on those, do not replace them.

## The work, in order of the researcher's pain

1. **Review stepping is snappy at 10,000 items.**
   - `get_item` must not scan the queue: find the one item by id (SQL), and number it with ONE `COUNT(*)` of items
     before it in the queue's own order (`queries.queue_candidates` orders by detection id) — or carry the rank from
     the queue listing the client already holds. Same for `get_item_channels` and `get_cluster`.
   - A verdict must not re-read the whole queue. Give the client a cheap **delta**: either `POST /verdict` returns the
     updated counts + the row it changed, or add a light `GET /queues/{qid}/counts` the client re-reads instead of
     the rows. The rows list is re-read only when the SET changes (promote, extract, batch, undo), and even then
     page it: rows without thumbnails first, thumbnails in a second, paged read (`?thumbs=…` or a separate
     `/thumbs?ids=`). The queue rail must still show every item; it may render virtually (only the rows in view).
   - **Prefetch the next item** (and the previous) the moment the current one is on screen, with the same `px`/`pad_s`
     the card will ask for, so the step is a cache hit. Keep a small LRU in the client (`api/review.ts`).
   - Target, server time on the sandbox copy at 10 k items: `get_item` < 150 ms, a verdict round-trip < 300 ms, the
     next item painted from cache < 100 ms after the key press.
2. **Discovery opens fast and does not jump.**
   - `/api/discovery/runs`: one cheap status read per run (status + progress + channels done, one or two queries over
     `runs` and `detections` grouped by run_id — never `list_recordings` per member run); the full `group_status` only
     where its channel detail is actually shown.
   - `/api/discovery/templates`: never rescore on open. Serve the cached score when the fingerprint matches, and a
     "not scored yet" placeholder with the LAST known score otherwise; score in the background job the warm already is,
     and let the client re-read when it lands (the runs list already polls while something runs).
   - `/api/discovery/fires`: one SQL per channel × run that returns the per-bin histogram (`GROUP BY` on
     `(start_idx - first) / bin_samples`), not every span materialised in Python; or one query per channel over all
     the session's run ids. Measure both; keep the faster.
   - First paint: **no 600 px placeholder that is then replaced.** Either a skeleton with the final layout (toolbar
     row, scope card at its real height, two columns with grey blocks) so nothing moves when data lands, or render
     the chrome immediately and fill the cards in place with the `Refreshing` pattern (`discovery/chrome.tsx:27`).
     The same on Seed and Map. A page whose data takes longer than ~1 s shows a determinate bar where the server can
     report progress and the indeterminate one otherwise — never a blank, never a jump.
3. **The home page and the corpus maps.**
   - The coverage cache survives a restart: write each computed map to disk under the runtime (a JSON or `.npz`
     beside the step cache — a path, never a blob in the database; rule 4) keyed by the fingerprint, and read it back
     on a miss before recomputing. Narrow the fingerprint's settings part to the keys the divergence reads, so a
     settings change elsewhere does not throw every map away (list which keys; add a test that changes an unrelated
     setting and expects a cache hit, and one that changes a read key and expects a miss).
   - The warm must not fight the page: lower its priority (compute the first file, then yield between files; or run
     it only when no request has been served for a few seconds), and log one line per file as `ux-1018` added.
4. **Everything else that makes the site feel slow**, cheapest first, each with a measurement:
   - `req()` gets an `AbortController` with a sensible timeout and cancels a superseded read (a page that navigated
     away, a new item requested before the old one answered).
   - Any list that can reach thousands of rows renders virtually or pages (the review rail, the runs list, the
     Library atlas grid, the jobs board): say which you did and which you measured as fine.
   - SQL: for every query you touch, check `EXPLAIN QUERY PLAN` on a database with the scale fixture below; add the
     index it needs through `init_db()` (additive, idempotent, `CREATE INDEX IF NOT EXISTS`; an index on a migrated
     column goes in that column's migration block, as `idx_runs_surrogate_of` does, or it breaks old databases).

## Method — measure first, prove with tests, measure again

- **A scale fixture** (`tests/perf_fixture.py` or inside the test files): a fresh `init_db()` with 16 recordings,
  ~60 runs × 16 channels, **5 M detections** (bulk `executemany`, random but plausible spans over 721 h at 1 Hz),
  12 k annotations, a review queue of **10,000** items, 70 templates. It must build in under a minute and be reused
  across tests (module-scoped tmp file). Channel `.npy` files are small synthetic traces (the traces' content does not
  matter for timing the routes, their length does).
- **A timing harness** `scripts/perf_routes.py` (dev tooling, not imported by the app): given a bridge URL, hits each
  route in the table above the way the pages do (same query strings), N times, and prints a table of median and p95
  in ms. Run it against a bridge serving the scale fixture (`webui/run_server.py --sandbox --port 8767
  --db <fixture sqlite> --dist <your worktree's webui/client/dist>` — the manager will run the same harness on the
  sandbox copy of the real database before and after your branch; your report carries your numbers, the manager's
  go in the ledger).
- **Tests are about complexity, not wall-clock** (wall-clock tests fail under load — see
  `tests/test_webui_decimate.py`'s history): count queries with `sqlite3.Connection.set_trace_callback`, count
  calls with a monkeypatched helper, assert "one item read touches O(1) rows" by building the queue at two sizes and
  asserting the query count does not grow. Every server change starts with a failing test of that kind (the first
  commit touches only `tests/`).
- **No semantic drift.** A verdict is written exactly as before; the five verdict words are fixed; what Review asks
  about, the queue's order and `total`, the scoreboard's numbers, the corpus map's cells are byte-for-byte what they
  were (assert equality between the old path and the new on the fixture where you replace a computation).
- Run your tests with the interpreters `UX-1015-common.md` names; `tests/test_webui_review*.py`,
  `tests/test_webui_discovery.py`, `tests/test_webui_corpus.py`, `tests/test_perf_scoring_reads.py`,
  `tests/test_import_boundaries.py` plus your own, and say which interpreter ran each. Type-check and build the client
  from your worktree through the junction. Write smoke states for any new UI state into
  `webui/smoke_pages/zzzzzzzzzzz_ar_speed.json` (a review step that must show the prefetched item without a loading
  card; Discovery's first paint without the placeholder; the templates popover opening under a second with a
  "scoring…" placeholder).

## Files

Yours: `webui/server/review.py`, `webui/server/discovery.py`, `webui/server/corpus.py`, `webui/server/app.py`
(`req` timeouts are client-side; server-side only the coverage route), `webui/server/runtime.py` (a disk cache dir
under the runtime), `Working/review/queues.py` and `Working/database/queries.py` (the one-item and count reads),
`Working/discovery/fanout.py` (a cheap status read beside `group_status`, not instead of it), `Working/discovery/
scoreboard.py` (fingerprint narrowing), `Working/database/schema.py` (indexes only), the client under
`webui/client/src/review/`, `webui/client/src/discovery/`, `webui/client/src/api.ts`, `webui/client/src/api/review.ts`,
`webui/client/src/api/seam.ts`, `webui/client/src/kit/` (a skeleton primitive if none exists), `scripts/perf_routes.py`,
`tests/`. Report, do not edit, anything else.

## Stop and report instead of guessing if

a fix needs a new dependency; a schema change beyond an index; a route whose meaning would change; the scale fixture
cannot be built under a minute without a trick you would not defend; or you have spent a third of your effort on one
route without a measured improvement — move to the next item and say so.

## Report

`docs/prompts/fixup/reports/AR-speed-report.md`: **Assumed**; a before/after table from `scripts/perf_routes.py` on
the scale fixture (median, p95, query counts); per item of the work list what changed and the test that pins it;
the indexes added; what you measured and left alone (with the number that justified leaving it); the smoke states
and what each should show; what remains for a later pass. Plain language first, as for the researcher.
