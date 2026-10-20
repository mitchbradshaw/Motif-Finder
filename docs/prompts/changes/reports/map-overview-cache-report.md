# map-overview-cache — report

Branch `claude/festive-joliot-d2d522`, base `ff02112`. Commits: `6ed9040` (tests, red), `45afa02` (implementation),
then this report.

## In plain words (for the researcher)

Think of the Map overview as a big tally sheet: every time anyone looked at it, the bridge re-counted every
Discovery run from scratch before showing anything. On the real database that took 17–21 s, and it would keep
growing with every run. Now the bridge keeps the last finished tally sheet and hands it over at once. When
something has changed since (a run finished, one was discarded), you still see the old sheet straight away, with a
small grey line over it saying "re-counting · this map is from before the last change". A separate worker process
does the re-count without slowing the rest of the site, and the page swaps in the new sheet when it is ready. While
a run is still going the line says "re-counting · a run is still going". If the re-count fails you get a red card,
never a blank map. On a copy of the real database a fresh read now takes about 0.1–0.3 s instead of 7–21 s. The
numbers drawn are the same ones as before.

**One thing to do before the demo:** after the 8765 bridge is restarted on the new main, open Discovery › Map once
(or wait about a minute after start). The very first read on a new bridge has nothing stored yet. It shows
"counting every session's runs for the first time" and the map appears about 30–100 s later. Every read after that
is quick, and so is the first read after any later restart, because the overview is kept on disk.

## Assumed

- **The prompt's fingerprint (`scoreboard.channels_fingerprint` over every recording) is not used.** On the copy of
  the real database it measured **19–23 s**, which is slower than the overview itself (7.5–13 s in-process), because
  it reads every channel's adjudications and every run on every channel. A read that pays that is no faster than
  today. Instead `detection_map.overview_fingerprint` digests exactly the rows `dataset_map` reads:
  - the Discovery runs whole (status, discard, removal, params, which name their runs) with their sessions' names;
  - each run they hold, with its span, status, discard and detection id range (detections are append-only);
  - those runs' recipes;
  - every verdict and reviewed span, read whole because verdicts are edited in place;
  - the recordings and the datasets' display names.

  It costs **0.42–0.5 s warm and 1.0–1.8 s cold** there. It covers the prompt's run-set rule (run ids with their
  statuses, so a discard moves it). The test `tests/test_discovery_map_cache.py` changes each input in place and
  expects the digest to move, and changes a setting the overview never reads and expects it to stay.
- **The fingerprint itself is skipped while nothing was committed.** SQLite's `PRAGMA data_version`, read on one
  connection the module keeps, moves whenever any other connection commits. While it stands, the last fingerprint
  is reused, which takes the warm read from ~0.75 s to ~0.1–0.3 s. The counter is read before the fingerprint, so
  a write landing between the two costs one extra fingerprint, never a stale answer. The connection is closed by
  `corpus.shutdown_coverage_pool()`, which `Runtime.restore()` already calls, through a new `corpus.on_worker_stop`
  hook. That keeps `runtime.py` untouched, and the sandbox copy is still released on restore.
- **One pool, extracted rather than duplicated.**
  - `corpus.run_in_worker(fn, *args, fallback=, what=)` is the body of the old `corpus._run`: pool or thread
    fallback, the 1 h timeout, the broken-pool restart, and `_Stopped` on a deliberate stop. `_run` now calls it.
  - One behaviour changed there: a future cancelled by `shutdown_coverage_pool` (`cancel_futures=True`) now raises
    `_Stopped`, not a recorded failure. A map waiting behind another job when the bridge stops is abandoned, not
    turned into a red card.
  - The disk helpers `_disk_path` / `_disk_write` / `_disk_read_any` take a `kind` subfolder (`coverage` by
    default), and the overview uses `map`.
- **The overview waits behind at most one corpus map.** The pool has one worker, and the corpus queue submits one
  map at a time, so an overview scheduled during a corpus recompute starts when that one finishes (≤100–260 s on
  the real database, in the worst case of a corpus warm after a change). On the measured fresh sandbox this is why
  the first-ever overview took 98 s to land instead of ~30 s.
- **The single-flight rule is per key, and polls during a recompute do not fingerprint.** A read while the
  recompute is in flight answers the last overview marked stale (or pending) without fingerprinting, as the corpus
  map does. The first read after it lands fingerprints as usual, so a change made meanwhile is still noticed.
- **A running run.** While any Discovery run is `running` or `queued` (not discarded, not removed), the served
  overview carries `stale: true` and `running: true`. A recompute is scheduled at most every 30 s
  (`RUNNING_GAP_S`), so the page's 5 s poll does not keep the worker busy for the whole run.
  - A run `on cluster` is not "running here": its results arrive by import, which moves the fingerprint like any
    other write. Otherwise the real database's one `on cluster` run would mark the map stale for days.
- **The key** is `("overview", held-out files excluded)`. The held-out lock's state is part of it, as in the corpus
  map.
- **The session bit** (`_session_bit`, which every map level returns) now reads one row's rate instead of
  `_file_for_key`'s full recordings listing. That saves ~0.2 s on every map read, levels 1 and 2 included. It falls
  back to `_file_for_key` if the row is missing.
- **The timing field.** The route returns `read_ms`, the overview read's own time, excluding the connection and the
  first request's schema check. The tests' 100 ms / 50 ms budgets are on it, not on the HTTP round trip: a
  wall-clock budget on the round trip failed twice under load (190 ms, the first request's `init_db`).
- **Not done (outside the named files):**
  - The overview is **not warmed at bridge start**. `discovery.warm_last_scores` owns the warm, and `discovery.py`
    is not in this prompt's files. A one-line `discovery_map.overview(c, db_path)` before `warm_coverage` there
    would make the first read after a fresh restart fresh. Until then, open the page once (above).
  - `discovery._session` costs ~100 ms per call on the real database and is now the floor of every map read (and of
    every Discovery route). It is untouched here.
- **Commit trailer.** The prompt asks for "Claude Fable 5.1". I used the model I am, as the session's attribution
  rule states: `Co-Authored-By: Claude Opus 5.5`.

## The state machine

1. A read checks whether the overview's recompute is in flight. If it is, the read answers the last overview
   (memory, else disk) marked `stale` (or the empty shape marked `pending`) without fingerprinting.
2. Otherwise it fingerprints (skipped while `data_version` stands). If the held overview, from memory or else from
   disk, has that fingerprint, it is **fresh**, plus `stale` + `running` while a run is going.
3. If the last recompute of this fingerprint failed, the read raises `MapFailed` (a 500 with the sentence).
4. Otherwise it schedules one recompute (unless one is in flight, or a run is going and the last one finished
   < 30 s ago). It answers the last overview with `stale: true` + `stale_since`, or `pending: true` with empty
   layers.
5. The worker returns `(the fingerprint it READ, overview)`, both from one WAL snapshot. The parent stores the
   overview under that fingerprint, in memory and in `<runtime root>/cache/map/`, so a restart serves it at once.

## Timings — sandbox bridge (`--sandbox --port 8791`) on a copy of the real database

The copy was taken with SQLite's backup API at 12:40 on 2026-10-20: 222 recordings, 305 Discovery runs (289 live),
2,618 runs held, 54 map rows, 7 datasets. Times are the HTTP round trip from a local client, with the route's own
`read_ms` in brackets. The machine was shared (another session imports HPC results through 8765), so expect spread.

| what | before | after |
|---|---|---|
| a read, old route body (`dataset_map` + keying + session), in-process on the copy | **13.2 s cold, 7.5–8.8 s warm** (live bridge under load: 17–21 s, prompt) | — |
| first-ever read on a new sandbox (nothing stored) | — | **3.0 s** (2.6 s), `pending` (cold fingerprint + first-request costs) |
| polls while the first overview computes | — | 0.13–0.26 s, `pending` |
| time to the first overview (queued behind the corpus warm's map in flight) | — | 98 s |
| first read after a bridge restart (overview on disk) | — | **0.8–0.9 s** (0.5–0.77 s), fresh |
| warm fresh reads | 7.5–13 s | **0.15–0.75 s** (0.1–0.57 s), median ~0.3 s |
| the read right after a change (stale-served) | 7.5–13 s | **0.72–0.86 s** (0.52–0.64 s), `stale: true` |
| polls while the recompute runs | 7.5–13 s each | 0.31 s (0.26 s) |
| time to the fresh overview after the change (worker idle) | — | **11.3 s** |

Before the `data_version` skip and the session-bit fix, warm reads measured 0.8–0.93 s (0.71–0.84 s). The split
then was fingerprint 0.42–0.5 s, `_session_bit` 0.17–0.39 s, keying and copying ~50 ms.

## Tests and interpreters

- Red commit `6ed9040` (tests only):
  - conda `tests/test_discovery_map_cache.py`: 14 failed, 1 passed;
  - webui/.venv `tests/test_webui_discovery_map.py`: 1 failed, 8 errors (AttributeError: the new entry points do
    not exist).
- `tests/test_discovery_map_cache.py` (conda, 15): compute equals `dataset_map` and returns its fingerprint;
  exclusion; the fingerprint moves for each of 10 kinds of change and stays for an unread setting; `any_running`;
  the module imports no UI module (subprocess).
- `tests/test_webui_discovery_map.py` (webui/.venv, 8):
  - pending within 100 ms and exactly one compute; a second read schedules nothing; fresh after, within 50 ms;
  - the fresh overview equals the core's;
  - a change (detections added; a Discovery run discarded) serves the OLD overview stale at once, and the next
    compute replaces it, stored under the WORKER's fingerprint (a second change lands while the compute is held);
  - a running run: stale + running on every poll, ≤1 compute over 6 polls;
  - a raising compute is a 500 naming `MapFailed`;
  - the overview survives a restart from disk;
  - by default it runs in the worker process.
- Green at `45afa02`:
  - conda `test_discovery_map_cache`, `test_discovery_detection_map`, `test_coverage_map_compute`,
    `test_perf_scoring_reads`, `test_import_boundaries`: **120 passed**;
  - webui/.venv `test_webui_discovery_map`, `test_webui_ar_speed`, `test_webui_corpus`, `test_coverage_map_compute`:
    **43 passed**.
  - Rerun after the `data_version` / `on_worker_stop` edits (the committed code): conda **120 passed**, webui/.venv
    **43 passed**. `test_webui_discovery_map` alone was also rerun five times: 8 passed each time.
- Client: `tsc -b` and `vite build` pass (through the main checkout's toolchain).

## Gate (smoke)

The units ran `--pages-only` on a fresh `--sandbox` bridge from this worktree (port 8791, the copy of the real
database). This worktree has **no `DATA/derived/channels/*.npy`**: no junction or copy of the real DATA was made, as
the rules require. So every state that reads a signal fails here for that reason alone.

- **`zzzzzzzzzzz_corpus_map`: 0 failures.** The stale notice went away after 64.5 s and 71.8 s; no server traceback,
  no console error. The shared pool (`run_in_worker`) carries the corpus map as before.
- **`discovery` (pages only): all three Map states pass.**
  - `discovery.map--datasets` painted its covered cells after 1.1 s;
  - `dataset-chunks` and `channel-day-bins` pass too.
  - 37 other failures. Every server traceback in the bridge log is a `FileNotFoundError` for a channel `.npy`, on
    `/api/discovery/detections`, `/overview`, `/seeds` and `/seed/setup`. None is on a map route, and none is
    `MapFailed`. The unit also needs a full walk to be judged (its states name runs the flows create).
- **`zzzzzzzzzzz_a1_coverage`: 3 failures, all from one Runs-page state whose reads hit the missing `.npy`**
  (`DATA/derived/channels/M2_aug_concat_fs1/CH6.npy`, `LM_fs2/CH0.npy`).

**Still to do at merge: the `discovery` and `a1_coverage` units on a bridge that has `DATA/`** (the main checkout's
sandbox, or the daily full walk).

## Files

- `Working/discovery/detection_map.py`: `overview_fingerprint`, `any_running`, `compute` (appended; nothing
  existing changed).
- `webui/server/discovery_map.py`: the route, `overview`, the single-flight scheduler, `MapFailed`, `map_status`,
  `wait_map_idle`, `reset_map_cache`, the `data_version` probe, the `_session_bit` row read.
- `webui/server/corpus.py`: `run_in_worker` (extracted from `_run`), the `kind` argument on the disk helpers,
  `on_worker_stop`.
- `webui/client/src/discovery/MapPage.tsx`: level 3 polls while pending or stale, the `map-refreshing` chip, the
  first-time line.
- `webui/client/src/api.ts` (shared; append-only: five optional fields on `DiscMap`).
- Tests: `tests/test_discovery_map_cache.py`, `tests/test_webui_discovery_map.py` (both new).
