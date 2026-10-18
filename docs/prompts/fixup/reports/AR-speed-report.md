# AR — the speed pass: report

Branch `worktree-agent-a2d21b600a4eb3301`, worktree `.claude/worktrees/agent-a2d21b600a4eb3301`, base `a24a4f1`.

## In plain words (for the researcher)

Think of the review queue as a long stack of index cards. Before this, every time you turned a card, the site
re-counted the whole stack three times to work out which number the card was, and after every verdict it reprinted
every card, pictures included. Now it remembers how the stack is laid out (and checks, cheaply, that nothing under it
has changed), so turning a card is one lookup. It also fetches the next card while you look at the current one, so it
is already there when you press the key. On the scale copy (10,000 items, 5 million detections) stepping went from
29 s to about 0.06 s per item on the server, a verdict from 17 s to 0.13 s, and the page no longer re-reads 9 MB of
rows after each verdict.

Discovery now draws its own layout in grey while it loads, so nothing jumps. The template picker never waits on
scoring: it shows the last score it knows, marks it "rescoring…", and fills in the new number when the background
scoring finishes. The home page's corpus map is saved to disk, so after a restart it comes back in about a second
instead of two to four minutes. Changing a setting the map does not use no longer throws it away.

## Assumed

- **Scale fixture size in the tests.** `tests/perf_fixture.py` builds the full database (5.0 M detections, 960 runs,
  16 ch × 721 h, a 10 k queue, 70 templates, 12 k annotations) in about 60 s when the machine is loaded. The test files
  build it small (60 k detections; queues of 150, 600 and 1,500) because they compare two sizes. The full build is
  what `scripts/perf_routes.py` was measured against.
- **"Rank" comes from the server's cached structure, not from the client.** I did not use the "carry the rank from
  the listing" option. The rank stays the server's position in the served list, equal to the old `_ranks` (pinned).
- **Light versus full re-read after a write.** A single verdict or class on a queue that writes `adjudications` or
  `window_verdicts` re-reads only the counts. A promotion, a batch, an undo or redo, and any write on a queue that
  writes `annotations` still re-read the rows. A human span can change any queue's set of items.
- **Timeouts.** Reads time out after 300 s with a loud `ApiError` that names the route. Writes never time out, because
  a POST may already have landed. A cold corpus map on the real database has taken minutes, so the read limit is
  generous.
- **Abort.** A new hook, `useAbortableSourced`, aborts a superseded read. `useSourced` is unchanged: forty existing
  reads are passed by reference, and handing them a signal could have been mistaken for one of their own arguments.
  Only the Review queue read uses abort. Cached and prefetched item reads are shared on purpose and are never aborted.
- **The disk cache lives in `<runtime root>/cache/coverage/`, not inside the per-start stamp directory.** A project
  start gets a new stamp every time. Entries are keyed on a content fingerprint, so a sandbox copy of the same
  database reuses them and a changed database never does.
- **Payload trims (no meaning change).** `filters_json` is no longer served; it was a string copy of `filters`. An
  item's queue header leaves out the `filters` list, because a Discovery picked queue's filter is 10,000 ids and
  nothing on the item card reads it. The queue listing still carries `filters` (smoke reads it).
- **The Shape card's queue-wide reference bar** reads only the smallest positive and the largest row peak. Rows no
  longer carry thumbnails, so the bridge sends those two ends (`thumbPeaks`). They are computed by
  `review.baseline_peak`, a line-for-line port of `charts/domain.ts::baselinePeak`.

## Before / after (`scripts/perf_routes.py` on the scale fixture, ms at the client, n = 5, `--writes`)

"Before" is base `a24a4f1` (the bridge just past its corpus warm, with template scoring in flight, machine loaded).
"After" is the branch head (warm finished, machine quieter). **Caution:** `/map` and `/map/dataset` were not touched,
yet they read 354/384 ms before and 177/184 ms after. The machine was about 2× busier during the baseline, so
discount the small ratios by that much. The big ones are structural.

| route (as the page issues it) | before median / p95 | after median / p95 | kB before → after |
|---|---|---|---|
| GET /api/review/queues | 12,717 / 14,780 | 76 / 330 | 162 → 76 |
| GET /api/review/counts | 7,781 / 8,359 | 63 / 93 | 0.1 |
| GET /api/review/queues/1 (with thumbnails, 9,779 rows) | 26,900 / 27,286 | 2,845 / 4,408 | 8,721 → 8,635 |
| GET /api/review/queues/1?thumbs=0 (what the page now reads) | 35,980 (param ignored) | 768 / 1,018 | 8,721 → 5,225 |
| GET /api/review/queues/1/counts (new) | 404 | 68 / 294 | 0.1 |
| GET /api/review/queues/1/thumbs?ids=<10> (new) | 404 | 49 / 59 | 3.6 |
| GET …/items/<id>?px=900&pad_s=120 (consecutive) | 28,702 / 29,908 | **56 / 64** | 170 → 18 |
| GET …/items/<id>/channels | 8,826 / 9,028 | 80 / 107 | 76 |
| POST …/verdict (then undo) | 16,948 / 17,941 | **133 / 175** | 0.2 |
| GET /api/corpus/…/coverage (warm, memory) | 357 / 448 | 164 / 174 | 22 |
| coverage, first read after a restart | 116,400 (the warm's cold compute) | **1,286** (read back from disk; the warm took 0.2–1.2 s) | — |
| GET /api/discovery/session | 14 / 29 | 31 / 39 | 1.2 |
| GET /api/discovery/runs | 1,289 / 1,439 | 171 / 447 | 18 |
| GET /api/discovery/templates (warm finished) | 1,001 / 1,139 | 528 / 644 | 78 → 80 |
| GET /api/discovery/templates **while the warm is scoring** | > 240,000 on the real DB (manager) | **70–240** (60 of 70 marked "scoring") | — |
| GET /api/discovery/fires (3 ch, 60 runs) | 10,633 / 11,886 | 724 / 806 | 114 |
| GET /api/discovery/scoreboard (10 runs, 3 ch) | 34,693 / 66,528 | 2,031 / 3,788 | 64 |
| GET /api/discovery/map (untouched) | 354 / 570 | 177 / 178 | 4.3 |
| GET /api/discovery/map/dataset (untouched) | 384 / 516 | 184 / 230 | 10.8 |

**Query and complexity counts** (the tests, not wall-clock):
- Two item reads cost 3,044 vs 19,412 ×100 SQLite VM steps at 150 vs 1,500 items on the base. That is 6.4× for 10×
  the items: the read scanned the queue. After the fix round, the pin is `big <= 1.1·small + 20` at 150 vs 6,000 items
  (`test_an_item_read_does_not_grow_with_the_queue`). The critic measured the branch at 376 / 378 / 378 ×100 steps at
  150 / 1,500 / 6,000 items.
- A repeated queue read runs the candidate query **once**, not once per read.
- The thumbnail-less rows read draws 0 traces, where the base drew 532. Since the fix round (B1) this holds **cold**,
  after a restart, with nothing remembered: the pin clears the thumbnail and peak caches before the read. Before the
  fix, the read drew every thumbnail to find the reference bar's two ends, so it was 0 only when warm.
- `/runs` calls `group_status` 0 times, where the base called it 6 times (its light replacement makes a fixed handful of
  queries per Discovery run).
- The picker scores 0 templates on open, where the base scored 6.
- `/fires` builds 0 detection dicts for plain runs, where the base built them 18 times.
- The scoreboard scores 6 channels to show 6, where it used to score every channel of every run.

**The 52 s first `GET /api/review/queues` in the first after-run is explained (the critic's diagnosis).** Several cold
reads of the same queue built the same 10 k structure side by side, the rows-only read drew every thumbnail (B1), and
the warm scorer was on the GIL. The fix round adds one flight per queue structure (S2) and drops the thumbnail drawing
from the rows read (B1).

**Twenty open queues (fix round S3).** I added 19 queues to a copy of the fixture: 10 exact detection sets of about 490
items and 9 run-set queues of 4 k–38 k items, about 180 k items in all. The page re-reads `GET /api/review/queues` and
`GET /api/review/counts` after every verdict.

| read | during the template-scoring warm | warm finished |
|---|---|---|
| `/queues` | 1.4–2.3 s | **0.35–0.38 s** |
| `/counts` | 1.9–3.2 s | **0.34–0.37 s** |

- The first cold read built all 20 structures and took 22 s (four concurrent cold reads finished together, one flight
  each).
- Counting now runs on the remembered structure without building an item per row (`queue_counts` fast path, pinned
  against the item-by-item count).
- `get_queues` no longer counts each queue twice when a held-out set is locked.
- Non-detection queue kinds are still resolved on every count; they are small today.

## Per item of the work list

### 1. Review stepping (done; targets met on the fixture)

- **The core keeps the queue's structure** (`Working/review/queues.py`). The structure is a detection queue's live
  candidates in order, with absolute bounds and rediscoveries. It is kept against `_structure_fingerprint`, which
  covers every row it reads:
  - the queue's filters;
  - the runs it names (for a run-group queue, every run in the group *now*), with recording, recipe, span start,
    group, surrogate pairing and superseded-or-not;
  - each run's detection id range (the append-only assumption `scoreboard` already states); an exact detection set
    reads none, because its rows are fixed by id;
  - the `stitched_windows` id range;
  - every recording's channel;
  - the human spans on its channels, read whole;
  - the matching rule.

  The cache is keyed by database file (path + inode + ctime). An in-memory database is never cached. Verdicts and tags
  are laid over the structure fresh on every call.
  - *Pinned:* `test_the_cached_resolver_answers_exactly_what_a_fresh_resolve_does`. It changes each input in place (19
    mutations, three queue shapes, four views each) and expects the fresh answer. A mutation check that drops each
    fingerprint part in turn (runs, detections, stitched windows, recordings, annotations, rule) is caught by that test
    every time. Also `test_two_databases_never_share_a_remembered_queue` and
    `test_a_repeated_read_does_not_re_resolve_the_queue`.
- **`queue_snapshot`, `item_view` and `item_views`.** One resolve per read. `item_view` answers item, rank and counts
  from the structure without building every item.
  - *Pinned:* `test_snapshot_agrees_with_the_three_reads_it_replaces` and
    `test_item_view_agrees_with_the_snapshot_for_every_item`, which covers every target, held-out sets, cap,
    rediscoveries and absent ids.
- **`queue_candidates` over an exact detection set reads detections first** (`CROSS JOIN`). SQLite had started from
  `runs` and probed all 10 k ids once per run. That took 8.3 s, against 0.05 s.
- **`queue_pace_s` reads the ledger's tail.** It gives the same answer as the whole ledger (pinned).
- **Bridge (`webui/server/review.py`):**
  - `?thumbs=0`, `GET /queues/{qid}/thumbs?ids=` and `GET /queues/{qid}/counts` are new; `thumbPeaks` is added.
  - Thumbnails are kept per (file, mtime, unit, rate, span), and a recording row is read once per request.
  - Item, channels and cluster reads resolve once.
  - *Pinned:* `test_rows_without_thumbnails_read_no_channel_and_lose_nothing_else`,
    `test_thumbnails_are_paged_and_equal_the_full_reads`, `test_the_counts_read_is_the_queue_reads_counts` and
    `test_an_items_rank_is_its_place_in_the_listing`.
- **Client:**
  - A verdict bumps a counts version only (store.ts).
  - The queue list reads headers, not every queue's rows with thumbnails. The base re-read **all queues' rows** after
    every verdict (`getAllQueues` in Shell).
  - The toolbar's pace comes from `/counts`.
  - Both rails page in only the thumbnails on screen.
  - A 12-entry item cache with `prefetchItem` and `peekItem` serves steps. The Inspector prefetches the next unjudged
    item and J/K either side at the card's px/pad, and paints a step from the cache in the same frame.
  - `queue.ts` builds a row index and unit lists once per read. They were `data.rows.find` per unit, which is
    quadratic at 10 k.
  - RevealCard's walk is linear.

- **Fix round:**
  - **B1.** `?thumbs=0` draws no thumbnail. `thumbPeaks` is `null` until known. The new `GET /queues/{qid}/peaks`
    works the range out in the background, once per row set, and the Inspector asks every 2 s until it lands
    (`useQueuePeaks`); the Shape card falls back meanwhile.
  - **S2.** One flight per queue structure, with a per-key lock as in `corpus._coverage_lock`. Pinned:
    `test_concurrent_cold_reads_build_the_structure_once`.
  - **S3.** As in the twenty-queue table above.
  - **S4.** `_THUMB_CACHE` is capped at 20 k entries, ~36 MB at ~1.8 KB each (100 k was ~180 MB).
  - **S6.** `get_cluster` and the cluster accept/reject answer "no clusters" for detection kinds without resolving.
    No resolver emits a cluster number, so the 404 is identical.
  - **S7.** Two new pins: `test_the_request_clock_advances_on_a_request` and
    `test_the_warm_waits_for_the_pages_to_go_quiet`.
  - **Paged thumbnails.** A failed chunk is retried one id at a time, so one refused id no longer blanks its chunk; a
    row that still fails is drawn blank and not asked for again.

### 2. Discovery (done)

- **`fanout.group_status_light`.** It gives `group_status`'s answer key for key (pinned by equality, including after a
  detection is appended) in a fixed handful of queries. Detection counts are remembered against id ranges. Used by
  `/runs`, `/history` and the fires status loop. `group_status` itself is unchanged for its other callers.
- **`/templates` never scores.**
  - `SB.score_runs_peek` serves the remembered score when its fingerprint stands. Otherwise it serves the last known
    score, or `SCORING_TEXT`, with `scoring: true`, and queues the template on one background scorer that the
    start-up warm also drains.
  - The client marks "rescoring…" and re-reads every 3 s while anything is scoring.
  - *Pinned:* `test_the_template_picker_never_scores_on_open`.
- **`/fires`.** A plain run's row is a histogram of starts read by one SQL per channel × run (`_run_starts`, with the
  absolute-bounds shift stated in SQL). I took the "starts + `np.histogram`" variant over SQL `GROUP BY`. It is
  byte-identical by construction (same edges, same float histogram), and at 724 ms for 3 ch × 60 runs it is not worth
  the float-boundary risk of an SQL bin expression. Band-set keys keep the old union path.
  - *Pinned:* `test_fires_counts_by_sql_and_match_the_span_histogram`.
- **`/scoreboard`** (the manager's item 3, the same family) scores only the runs on the channels asked for. A channel's
  score reads its own run alone, and the rows kept were always just those. Measured 34.7 s → 2.0 s.
  - *Pinned:* `test_the_scoreboard_scores_only_the_channels_it_shows`, equal to the old computation.
- **First paint.** Runs, Seed, Compare and Stages first paint `DiscoverySkeleton`: the reload line, then the toolbar
  row, the Scope card and the two columns, in grey. Content no longer renders underneath a placeholder; the base
  rendered both once the session arrived, which is what made the icons jump. The Map page already draws its chrome at
  once and fills the level card in place, and I left it.

### 3. Home page and corpus maps (done)

- **The coverage fingerprint is narrowed.** Its settings part is only `analysis-defaults` / `iou`, `onset`,
  `containment` (`corpus.COVERAGE_SETTINGS`). Those are the keys `matching.rule_from_settings` and
  `divergence.containment_from_settings` read. The held-out lock's answer is part of the cache key.
- **Maps are kept on disk.** Each computed map is written to `<runtime root>/cache/coverage/<sha1(key)>.json`
  together with a stable SHA-1 fingerprint, and read back on a memory miss. A memory hit compares the cheap in-process
  digest.
  - *Pinned:* `test_the_coverage_map_survives_a_restart_and_ignores_unrelated_settings`. It clears memory and expects
    no recompute, expects an unrelated setting to hit, and expects a change to `iou` to miss.
- **The warm no longer fights the pages.** It computes the first file at once. Each later file waits until no request
  has been in flight for 2 s, for at most 30 s, using a plain ASGI request clock in `app.py`. Each file still gets its
  log line, plus a line when it waited.

### 4. Request hygiene

- **Done:**
  - `fetchBridge` gives every `api.ts` read and every `api/review.ts` read a timeout.
  - A superseded Review queue read is aborted.
  - The Review up-next rail was already paged at 10 per page and now pages its thumbnails. The collapsed rail shows at
    most 10.
- **Measured as fine and left alone:** the Discovery runs list (60 rows; the whole `/runs` read is 171 ms).
- **Not touched (outside my files):** the Library atlas grid and the Jobs board. Report only: I did not measure them.

## Indexes added

- `idx_runs_run_group ON runs(run_group_id)`. It is created in the runs column-migration block
  (`_migrate_runs_columns`), idempotently. A run-group queue's fingerprint and `list_run_group_runs` both scanned the
  table.
  - *Pinned:* `test_the_reads_an_item_step_makes_use_indexes`. It runs EXPLAIN QUERY PLAN on the run-group,
    detection-id-range, pace-tail and human-span reads, after a second `init_db`.

## Tests and interpreters

- **Red commit `7629d44`:**
  - conda `tests/test_ar_speed_core.py`: 3 failed, 1 passed, as the critic re-ran it on the commit. An earlier draft
    of this report said 4 failed; that count came from a working-tree run, not from the commit.
  - venv `tests/test_webui_ar_speed.py`: 8 failed, 1 passed (the rank pin).
- **webui/.venv** (FastAPI):
  - `tests/test_webui_ar_speed.py`: 10 tests.
  - `tests/test_webui_review.py`, `tests/test_webui_review_axis.py`, `tests/test_webui_corpus.py`.
  - `tests/test_webui_discovery.py`, `tests/test_webui_discovery_windows.py`, `tests/test_webui_heldout_switch.py`:
    101 passed plus the 2 updated tests passing, on `6bc2775`.
  - Fix-round run at the branch head: `test_webui_ar_speed.py` (12 tests), `test_webui_review.py`,
    `test_webui_review_axis.py`, `test_webui_corpus.py` and `test_webui_discovery.py`: **129 passed**.
- **conda, fix-round run at the branch head:** `test_ar_speed_core.py` (8 tests), `test_perf_scoring_reads.py`,
  `test_import_boundaries.py`, all eight `test_review_*` files and `test_surrogate_never_a_detection.py`:
  **270 passed, 1 skipped** (the skip is `test_webui_ar_speed.py`, which needs FastAPI).
- **conda:** `tests/test_ar_speed_core.py` (7), `tests/test_perf_scoring_reads.py` (69), `tests/test_import_boundaries.py`,
  and the review core files (`test_review_*`, `test_surrogate_never_a_detection.py`): 197 passed at `f75575c`.
  `test_webui_*` files skip under conda.
- **Tests deliberately changed** (each named in its commit):
  - `test_webui_discovery::test_a_run_templates_score_carries_its_scope`: the first read now says "scoring"; the score
    is asserted after the background scoring.
  - `test_webui_discovery::test_the_fires_grid_reads_a_runs_status_once_per_run…`: it counts the light status read,
    still once per run.
  - `test_perf_scoring_reads::test_two_concurrent_reads…`: the fingerprint stub takes keyword arguments.
- **Client:** `tsc -b` and `vite build` both pass from the worktree through the junction.

## Smoke states — `webui/smoke_pages/zzzzzzzzzzz_ar_speed.json`

1. **`review.inspector` / `ar-step-paints-from-the-prefetch`** (`review/queue/2/100`). Wait for item 100, then 2.5 s
   for the prefetch, press →, and check 100 ms later. Must show an inspector whose `data-item` is not 100, with its
   context card. Must not show `review-loading` or `item-error`.
2. **`discovery.runs` / `ar-first-paint-no-placeholder`.** Checked 150 ms after load. Must show `.dsc-toolbar` (the
   skeleton's or the real one) and the reload line. Must never show `discovery-loading` (the 600 px card).
3. **`discovery.runs` / `ar-templates-open-under-a-second`.** Click *Apply template*. Within 1.5 s the modal shows
   `template-score-<name>` cells. A template whose score is not current reads "rescoring…" or the scoring placeholder.

On real data, please check:
- that the skeleton's heights roughly match the real Scope card and columns (they are estimates; I could not measure
  them without a browser);
- the first `GET /api/review/queues` after a restart;
- that the picker's "rescoring…" clears once the warm finishes.

## Notes from the critic, recorded

- **The template score fingerprint is not narrowed.** Any settings save marks every template "rescoring" until the
  background scorer catches up. The prompt asked for narrowing only on the coverage map.
- **`/fires` histograms SQL-read starts with `np.histogram`** rather than binning with SQL `GROUP BY`. It is identical
  by construction and measured 724 ms.

## Left for a later pass

- **The Discovery map's level 2 and 3** (the manager's item 4: 7.6 s and 3 s on the real database). They are in
  `webui/server/discovery_map.py` and `Working/discovery/detection_map.py`, which are not my files. A cache keyed by
  `SB.channels_fingerprint` (now with `settings_keys`/`stable`) beside `channel_map` is the obvious next step. The
  5 s poll needs it.
- **The picker's warm read is 0.5 s on the fixture** (it was 1.9 s under load). It is the `inputs_fingerprint` per
  template: about 4 queries per member run × 16 runs × 60 templates. Batching that read is next.
- **Two other pages:**
  - The rows read is still 0.8 s and 5 MB at 10 k rows. It happens on queue open and on set changes only; paging it is
    possible but needs the queue rail and units to work on partial rows.
  - The scoreboard is 2 s for 10 runs × 3 channels; `channel_score` itself is the remaining cost.
- **The Library atlas grid and the Jobs board** are unmeasured.
