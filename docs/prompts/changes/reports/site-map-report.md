# site-map — the detection map (Discovery › Map), 2026-10-20

Branch `site/map`, cut from `main` f445468. Commit prefix `site-map:`. Port 8767 (my sandbox bridges only).

## In plain words

The map now fits the screen: it scrolls inside its card in both directions with the algorithm names on the left and
the dataset/channel headers on top staying put, so the right-hand datasets (`L_LM_Jul_26_J_ra…`) can be reached.
Any algorithm row, channel column or whole dataset can be hidden with the × on its label — it does not vanish, it
slides to the bottom (rows) or the right (columns), drawn thin and faded with a button to bring it back — and rows and
columns can be ordered by name, by most detections, or "clustered" so that algorithms (or channels) that fire alike
sit next to each other. The single-channel view draws the channel's own signal above the rows. The map opens much
faster: levels 2 and 1 answer in about 0.2–0.4 s once seen (they took 1.3–6.8 s every time), and the all-datasets
count itself went from 15 s to 1.8 s.

## Assumed

- **researcher, 2026-10-20 (via the manager):** a hidden algorithm row does not vanish — it sinks below every shown row,
  drawn short (7 px cells / a 5 px timeline strip) and dimmed, its label still readable, with a `show` button on it.
  Sorting and clustering order only the shown rows; hidden ones keep their listed order at the bottom. All three
  levels (level 1's timeline rows too).
- **researcher, 2026-10-20:** hidden columns sink to the right in the same spirit. What I built: a hidden channel moves
  to the far right **of its dataset** (level 3) or of the table (level 2), drawn as a narrow (≈10 px) dimmed column of
  small cells keeping their shade, its header a `+` button above the channel name in small grey. A whole dataset
  hidden at level 3 becomes ONE narrow dimmed column at the far right of the table with its name and a `+`.
- **researcher, 2026-10-20:** restoring a hidden row/column puts it back where the CURRENT order places it (as listed /
  name / most detections / cluster), not at the end — the order is recomputed over the shown set every render.
- **researcher, 2026-10-20:** the level-1 signal strip is ABOVE the rows at the height Explore › Signal draws its main
  trace (`SpanView.tsx` `H = 150`), on the rows' time axis.
- The one-line "hidden: …" list above the table names counts ("1 row (at the bottom) · 2 columns (at the right)")
  and has one `show all` button; each hidden item is restored from its own button in the table (the brief's per-item
  buttons on the line became redundant once hidden items stay in the table).
- URL keys: `hide=` row keys, `hidecols=` `<dataset key>` or `<dataset key>/<channel>` (shared by levels 3 and 2, so a
  channel hidden at one level is hidden at the other), `rsort=` / `csort=` (`listed|name|count|cluster`), `signal=0`
  turns the strip off (default on). `recording` / `channels` stay untouched (session.ts).
- *Most detections* sums the counts over the shown cells; *cluster* reads the shaded rate per shown cell (detections
  per covered hour; a cell with no rate reads 0); at level 1 rows cluster on their per-bin counts. Columns cluster on
  their values over the shown rows (the human row included). The human row is pinned first only among shown rows.
- Shading (per row / whole map) is unchanged and still reads every cell, hidden ones included — hiding is a view, not a
  re-normalisation.
- Level 2/1 cache: a view never seen is computed ON the request (no `pending` the page would have to learn); an older
  view is served at once with `stale: true` and recomputed once on a thread (not the worker process: one level read is
  ~1–2 s and would queue behind a corpus-map warm of minutes). Memory only, 48 views LRU.
- The signal readout gives the range of the hourly means inside the hovered bin, unitless (`getOverview` drops the
  route's `unit`; adding it was not worth touching RUNS's reader).

## Items

### 1. Speed

**Found:** on a backup copy of the real database (way 1; 57 rows, 23 datasets, 11.6 M detections) level 2 of M2_aug
took 6.1–6.8 s per read and level 1 1.3–3.5 s, every read. cProfile: 1.25 s of a 1.8 s `channel_map` was `_starts`,
which fetched every counted detection row into Python 896 times (56 rows × 16 channels) to histogram it.
After that, the route itself spent ~0.5 s per 1 h timeline in `copy.deepcopy` + FastAPI's `jsonable_encoder` of a
2.6 MB payload.

**Changed:**
- `detection_map._counts`: an indexed `COUNT(*)` on `(run_id, start_idx)` per (owned range × cell), stated exactly as
  `_starts` states its two ranges (absolute rows, legacy span-relative rows); a range spanning more than 16 cells
  (long level-1 rows) is still fetched once and histogrammed. Identical answers: `dataset_map`, `channel_map` (1, 8)
  and `timeline_map` (1/3/24 h) compared old-vs-new on the real copy for M2_aug, CO_fs2 and L_LM_raw_fs2 — all equal.
- `detection_map.compute_level(db_path, level, source_file, args, exclude)` → `(fingerprint, payload)` on a read-only
  connection (as `compute` does for the overview).
- `discovery_map._level`: each view kept under the overview fingerprint (`_fingerprint`, skipped while
  `PRAGMA data_version` stands); stale-while-recomputing, single flight per view, `RUNNING_GAP_S` while a run is going;
  a recompute failure is a `MapFailed` 500. Level routes return a shallow copy as a plain `JSONResponse`.
- The overview warms at bridge start right after the corpus-map warm (one line in `webui/server/discovery.py`, see
  Files). Log on my bridge: `corpus maps warmed (25 files, 24.0 s)` then `map overview recomputed (1.6 s, in a process)`.

**Timings** (my sandbox bridge on the backup copy, HTTP round trip, ms; "after change" = a detection inserted):

| read | before: cold | before: warm | before: after change | after: cold (first view) | after: warm | after: after change |
|---|---|---|---|---|---|---|
| L3 overview | 629 | 357 | 954 (stale) | 386 | 316–435 | 1151 (stale, old map at once) |
| L3 recompute (core, worker) | 14 900 | — | — | 1 800 | — | — |
| L2 ×1 | 6 513 | 6 384 | 6 087 | 2 025 | 212–237 | 272 (stale) → 233 fresh |
| L2 ×8 | 6 515 | 6 498 | 6 347 | 2 032 | 217–251 | 293 (stale) → 258 fresh |
| L1 3 h | 1 615 | 1 330 | 1 301 | 1 819–2 025 | 261–317 | 340 (stale) → 263 fresh |
| L1 1 h | 2 931 | 2 649 | 2 539 | 2 421–2 687 | 307–373 | 526 (stale) → 328 fresh |

Core alone (conda, same copy): `channel_map` 3.15 s → 0.44 s; `timeline_map` 3 h 0.63 → 0.26 s, 1 h 1.45 → 0.42 s.
The remaining cold cost is the fingerprint (~0.5 s) plus the gather and the read-only connection.

**Client** (Playwright, 1440×900, first `map-cell` painted after navigation to level 3, 57 rows × 66 columns = 3 762
button cells): before 1 808 ms, after 1 283–1 700 ms (the route dominates; no client change was needed for paint).

### 2. The datasets view cut off

**Found:** the table did scroll horizontally (scrollWidth 2 476 in a 1 334 px card) but the wrap had no height
limit, so its horizontal scrollbar sat below 57 rows, off-screen — nothing to grab. **Changed:** the wrap is
`max-height: calc(100vh - 240px)` and scrolls both ways; `thead` is sticky (top), row labels and the corner are
sticky (left); header cells close the border-spacing gaps so scrolled rows don't show through; the page's max-width
1600 is lifted. Checked: scrolled to the far right and down, label left = wrap left (99 px), headers in view.

### 3. Hide a row / a column / a dataset — see Assumed. Restoring puts it back in its place in the current order.

### 4. Sort / cluster — `rows` control at every level, `columns` at levels 3 and 2 (channels within their dataset at
level 3; a channel's time slices move as one at level 2). `mapOrder.ts`: average-linkage, correlation distance, leaf
order, deterministic; naive O(n³), fine for ≤ ~100 items.

### 5. The signal under (above) the single-channel map — `SignalStrip`: the scope strip's read (`getOverview`, one
mean per hour, no new full-resolution read) drawn on the rows' time axis, 150 px; a NaN hour breaks the line; hover
reads the bin's range; a 423 (held out) is "signal not drawn: <the bridge's reason>"; any other failure is a red
load-failed card in the strip (the copy has no `.npy`, so on it the strip shows that card — loud, as intended).
Checked drawn on a perf-fixture bridge with synthetic traces (readout "CH2 · signal · 21.0 h–22.0 h · hourly means
from 1.031 to 1.031"; `signal=0` removes it).

## Files

- created `webui/client/src/discovery/mapOrder.ts` (new helper beside MapPage — not in the brief's list, the brief
  asked for "a small helper with its own test")
- modified `webui/client/src/discovery/MapPage.tsx`, `webui/client/src/discovery/discovery.css` (appended `.dsc-map*`
  rules only), `webui/server/discovery_map.py`, `Working/discovery/detection_map.py` (map-only module; no run, cache or
  run-key reader touched)
- **append-only shared:** `webui/client/src/api.ts` — `stale?` / `stale_since?` / `read_ms?` added to
  `DiscMapDatasetLevel` and `DiscMapTimeline`
- **out of list, one line, at the manager's request:** `webui/server/discovery.py` (RUNS's file), in
  `warm_last_scores` right after `corpus maps warmed`: `discovery_map.overview(c, db_path)` starts the overview's
  first count in the worker
- tests: `tests/test_site_map_counts.py`, `tests/test_webui_site_map_levels.py`, `tests/test_webui_site_map_order.py`
- smoke: `webui/smoke_pages/zzzzzzzzzzz_site_map.json` (new); `discovery.json` map states unchanged (they still pass:
  no hide/sort keys, signal strip additive)

## Tests

- Red commit 31395ac: counts 4 failed (no `_counts`/`compute_level`, level 2 fetched rows), levels 6 errors (no
  `reset_level_cache`), order 9 failed (no `mapOrder.ts`, no URL keys/test ids).
- Green, conda: `test_site_map_counts` 4, `test_webui_site_map_order` 9 (node), `test_discovery_detection_map` +
  `test_discovery_map_cache` + `test_import_boundaries` — 45 passed.
- Green, `webui/.venv`: `test_webui_site_map_levels` 6, `test_webui_discovery_map` 8 — 14 passed.
- Pre-existing on f445468 and unchanged by this branch (checked by stashing my changes):
  `test_webui_discovery::test_the_map_lists_the_applied_run_as_one_row_over_every_channel_of_the_dataset` and
  `test_webui_heldout_switch::test_discovery_scopes_plans_and_maps_the_held_out_recording_only_while_unlocked` fail —
  both read level 3 once and get `pending` since 7ceea4f (map-overview-cache); they need a wait for the recompute.

## Smoke states (`zzzzzzzzzzz_site_map.json`)

Walked with `--pages-only --only zzzzzzzzzzz_site_map` on my bridge over the backup copy: 6 of 7 ok; the signal state
times out there only because the copy has no `.npy` (the 500 + console error it logs are the same cause).

1. `site-map-datasets-scroll-to-the-last-column` — level 3 scrolled to the far right and down; rows/columns controls,
   sticky row labels and corner present.
2. `site-map-hide-the-human-row-from-its-label` — hover + × on the human row: it sits at the bottom with `show`, the
   hidden line appears, the URL has `hide=human`.
3. `site-map-hidden-and-sorted-from-a-link` — `hide=human&hidecols=M2_aug_concat_fs1/CH1_A1&rsort=cluster&csort=count`:
   human at the bottom, CH1_A1 narrow at the right of M2_aug with `+`, muted cells drawn.
4. `site-map-show-all-brings-everything-back` — M2_aug hidden as a whole (far-right narrow column) and the human row;
   *show all* restores both, no hidden line.
5. `site-map-dataset-level-hidden-channel-clustered` — level 2, 2 slices, CH2_A1 hidden at the right with `+`, columns
   clustered, rows by most detections.
6. `site-map-channel-signal-above-the-rows` — level 1 (M2_aug CH1_A1, 1 d bins): the strip drawn (`data-state=drawn`),
   hover reads "hourly means …". Needs real signals: check on the manager's sandbox.
7. `site-map-channel-hidden-row-sorted-signal-off` — level 1 with the human timeline row thin at the bottom, rows by most
   detections, no signal strip.

Note for the gate: the existing `discovery` state `channel-day-bins` now also draws the signal strip (default on), so on
a bridge without the channel's `.npy` it would log the read's 500; on a normal sandbox it reads like the scope strip.

## Gates run

`tsc -b` and `vite build` pass from the worktree (main checkout's toolchain). The test files above.

## Open questions and risks

- The level-1 cold read (a view never seen, ~2 s on the real copy) still runs on the request; it is now under a third of
  what every read cost. A first open after a restart pays it once per view.
- Level-3 columns of a dataset with few channels and a long name stretch to fit the name (pre-existing; e.g. CO_fs2, 4 ch).
- Unit of the signal strip is not shown (see Assumed).

## Fix round (critic: "merge after fixes", no blockers)

1. **The level cache is bounded by size.** `LEVEL_CACHE_BYTES = 16_000_000` of summed compact JSON (memory runs ~3–4×
   the JSON, so ~50–60 MB held), plus the old cap of 48 views. Least recently read views go first. A view bigger than the
   whole budget is served and not kept. `level_status()` now reports `bytes`. The old "~0.3-1 MB" comment is corrected
   (a 1 h level-1 timeline of M2_aug is ~2.9 MB of JSON, ~10 MB in memory). Test:
   `test_the_level_cache_never_exceeds_its_byte_budget` (red in a35b844).
2. **The stale-then-fresh test checks the new answer.** It now also asserts the fresh payload differs from the old one
   and the totals move: a detection added to the newest run on the first channel raises the machine total by 1, and an
   `interesting` verdict raises the human row by 1, at both levels (4 cases). These passed on the existing code: they
   pin behaviour, they did not expose a bug.
3. **The map warm has its own `try`** in `webui/server/discovery.py` `warm_last_scores` (the same single site), logged
   with `log.exception("warming the map overview failed; …")`, so a failure there can no longer skip the template-score
   warm.
4. **No fingerprint while a recompute is in flight.** `_level` answers the held view marked stale without
   fingerprinting while that view's recompute is in flight, as `overview` does.
5. **The level-2 wrap marks stale.** Its `data-stale` reads `m.loading || data.stale`.
6. **No array spreads into `Math.min` / `Math.max`.** `SignalStrip` uses `extentOf` and the timeline uses `maxOf`, both
   from `kit/extent.ts`. Source checks added (red in fa731e7).

Gates: `tsc -b` and `vite build` pass. Conda: 47 passed (counts, order, detection_map, map_cache, import boundaries).
`webui/.venv`: `test_webui_site_map_levels` 9 passed. `test_webui_discovery_map` (level 3, code unchanged here) has
`read_ms < 100` asserts that flaked on this loaded machine (101–167 ms). In separate runs a different case failed each
time, and the same failure shows on the pre-fix HEAD. Worth re-running on a quiet machine at the gate.
