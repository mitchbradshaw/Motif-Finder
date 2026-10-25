# tq-mapcache — one stale-while-revalidate cache for the Map; one snapshot-read in the core

Package id for commits: `tq-mapcache`. Read `docs/prompts/quality/00-common.md` first. The tq-worker package (merged
before you start) moved the bridge's worker pool out of `corpus.py` into `webui/server/worker.py`. Read that module.

## The findings

1. **`webui/server/discovery_map.py` holds two hand-written stale-while-revalidate caches, and
   `corpus.coverage` (`corpus.py:~251-420`) is a third.**
   - The overview cache: `_STATE`, `_LOCK`, `_IDLE`, `overview`, `_behind`, `_stale_since`, `_schedule`,
     `_recompute`, `map_status`, `wait_map_idle`, `reset_map_cache`.
   - The level cache: `_LV`, `_LV_LOCK`, `_LV_IDLE`, `_level`, `_keep_level`, `_schedule_level`,
     `_recompute_level`, `level_status`, `wait_levels_idle`, `reset_level_cache`.
   - Both are one algorithm: fingerprint, hit, recorded failure, `first_seen`, the `RUNNING_GAP_S` throttle, a
     single-flight recompute, record the error, `done_at`, an idle event.
   - The copies have already drifted:
     - The overview deep-copies (`copy.deepcopy(hit[1])`); the levels copy shallowly (`dict(hit[1])`).
     - In `_level`, `if busy and held is not None:` lets a view that is in flight but not yet held compute again on
       the request, beside the in-flight recompute.
     - The running-gap condition is written two different ways.
   - The bridge also reaches into corpus privates: `corpus._disk_read_any(key, "map")` and
     `corpus._disk_write(key, fp, out, "map")`.
2. **`Working/discovery/detection_map.py:~618-677` repeats the WAL-snapshot fingerprint block of
   `coverage_map.fingerprinted` (`Working/discovery/coverage_map.py:~76-100`), giving three copies.**
   - The repeated block:
     `wal = …journal_mode… == "wal"; if wal: BEGIN; fp = digest(); out = compute(); if not wal and digest() != fp: fp = None`.
   - `compute_level(db_path, level: str, source_file, args: dict, …)` validates `level` as a string and unpacks
     `int(args["chunks"])` or `args["channel"], float(args["bin_h"])`. That stringly-typed dispatch exists only
     because the bridge keys its cache on `(level, source_file, tuple(sorted(args.items())), exclude)`: a bridge
     concern in the core's signature.
   - `any_running` (~608-615) re-checks `PRAGMA table_info(discovery_runs)` for `removed_at`, which `init_db`
     guarantees (`schema.py:~726 _DISCOVERY_RUNS_NEW_COLUMNS`). The check is dead, and copies the same guard in
     `_discovery_runs` (~96).

## The remedy

- **One generic `snapshot_read(db_path, digest, compute) -> (fp | None, out)`** in the core (`coverage_map` or
  `Working/database`). `coverage_map.fingerprinted` and the detection-map paths become one-liners over it.
- **The bridge passes plain callables or explicit functions per level**, so `compute_level`'s string-and-dict
  protocol disappears. Levels run on threads (check), so the callables need not pickle. Anything that runs in the
  spawned worker must stay picklable.
- **Drop the dead `PRAGMA table_info` guards.** Check `init_db` really guarantees the column on every database the
  bridge opens, including old sandbox copies, which are migrated through `init_db` on open (verify).
- **One stale-while-revalidate class** (a small `webui/server/swr.py`, or inside `discovery_map.py` if it is only used
  there), parameterised by:
  - the runner (the worker for the overview, a thread for the levels);
  - an optional disk kind;
  - a size bound;
  - the copy policy;
  - the first-miss policy (the overview answers "pending"; a level computes on the request).

  `overview()` and `_level()` each shrink to a few lines. Make corpus's disk helpers public (`disk_read_any`,
  `disk_write`) or move them into the class. Moving `corpus.coverage` onto the class is optional. Do it only if it
  comes out clearly simpler and every corpus test passes unchanged.
- **Fix the in-flight-but-not-held duplicate compute in `_level`:** a request for a view whose recompute is already
  running waits for it, or answers like the overview, whichever matches the level's current "compute on the
  request" contract with fewer computations. Say which.

## Behaviour that must not change

- **Overview first miss** answers "pending" and computes in the worker. Levels compute on the request on a cold
  first miss.
- **A stale answer is served with its `stale_since`** while the recompute runs. The recompute is throttled by
  `RUNNING_GAP_S` while a discovery run is going.
- **A recorded failure** is served as a failure until the fingerprint moves.
- **The level cache stays byte-bounded and LRU.** `map_status`/`level_status`/`wait_*_idle`/`reset_*` keep their
  names and meaning: tests and the smoke prelude use them.
- **Fingerprints, cache keys, payload shapes and the disk cache files** stay identical. A cache-key change makes
  every warm map go cold on the researcher's next start.
- **Exclusions** (held-out files) keep reaching every read.

## Files

`webui/server/discovery_map.py`, a new `webui/server/swr.py` if used, `webui/server/corpus.py` (the disk helpers'
visibility, and coverage only if you take the optional step), `Working/discovery/detection_map.py`,
`Working/discovery/coverage_map.py`.

Tests: `tests/test_discovery_detection_map.py`, `tests/test_discovery_map_cache.py`, `tests/test_site_map_counts.py`,
`tests/test_webui_discovery_map.py`, `tests/test_webui_site_map_levels.py`, `tests/test_webui_heldout_switch.py`,
`tests/test_coverage_map_compute.py`, `tests/test_perf_scoring_reads.py`, `tests/test_windowed_detection.py`,
`tests/test_webui_discovery.py`, `tests/test_webui_routes.py` (three known coverage-route failures on main), and any
`grep -rln "discovery_map\|detection_map\|coverage_map\|_disk_read_any\|_disk_write" tests/`. Record the failure set
first. `Working/` is core: run every test file that imports the two core modules.

Smoke units for the manager: `zzzzzzzzzzz_a1_site_map`, `zzzzzzzzzzz_corpus_map`, `zzzzzzzzzzz_a1_coverage`, `explore`.
