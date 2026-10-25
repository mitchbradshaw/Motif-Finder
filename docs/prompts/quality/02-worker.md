# tq-worker — the bridge's worker process in one module; block-cost timing as a public core API

Package id for commits: `tq-worker`. Read `docs/prompts/quality/00-common.md` first.

## The findings

1. **Calibration rebuilds the core from its private parts.** Files: `webui/server/calibrate_child.py:17-44`,
   `webui/server/chain.py:340-395`.
   - `Working/block_cost.py::calibrate()` can only write a file. So the child process times into a scratch dir
     (`tempfile.mkdtemp`), reads the JSON back, and pulls `json.load(f)[block_cost._key(name)]` out of it.
   - It repeats calibrate's warm-up: `if name in block_cost.WARM_UPS: …` plus one synthetic call.
   - The parent re-does calibrate's read-merge-write with privates:
     `with block_cost._FILE_LOCK: merged = block_cost._load(path); merged[key] = entry; block_cost._save(merged, path)`.
   - That is four private names of the core used from the bridge.
2. **Test seams wired into the production path.** Files: `chain.py:34, 340-344, 406`.
   - `_REAL_CALIBRATE = _block_cost.calibrate` is captured at import, then dispatched on identity:
     `if CALIBRATION_WORKER == "process" and block_cost.calibrate is _REAL_CALIBRATE:`. That means "if a test
     monkeypatched the core, quietly use the thread path instead".
   - `_child_call()` exists only so a test can swap the child function.
   - `calibrate_in_child(hold_s=…)` is unused: the test that wanted a slow child (`tests/test_webui_site_x_calibration.py`
     ~line 182) swaps `_child_call` instead.
   - So there are three overlapping ways to fake one thing.
3. **A second copy of corpus.py's spawn-pool lifecycle that reaches into corpus privates.** File: `chain.py:344-395`.
   - It copies the set-up: `ProcessPoolExecutor(max_workers=1, mp_context=spawn, initializer=coverage_map.watch_parent)`.
   - It copies the `threading._register_atexit` dance with a hand-rolled `_BC_ATEXIT = {"registered": False}` flag,
     and no `atexit` fallback, unlike corpus.
   - It uses `corpus._MainHidden()`, `corpus._terminate(pool)` and `corpus._POOL_LOCK`.
4. **Generic worker plumbing lives in the corpus-coverage module.** Files: `webui/server/corpus.py:592-850`.
   - `run_in_worker`, `on_worker_stop`/`_ON_STOP`, `coverage_pool`, `_terminate`, `shutdown_coverage_pool`,
     `_MainHidden` and `_Stopped` are bridge-wide infrastructure. Their docstring says the corpus maps and
     Discovery's Map overview "both come through here".
   - `webui/server/discovery_map.py` therefore imports `corpus.run_in_worker` and catches the private
     `corpus._Stopped`.
   - Log lines already say `worker:`.
   - corpus.py grew 959 → 992 lines.
5. **A third per-key lock registry.** `webui/server/discovery.py:~1328-1350` `_SB_LOCKS` (setdefault + a reference
   count) re-implements `corpus._coverage_lock` (`corpus.py:~233`, a bounded registry). Each evicts differently.

## The remedy

- **Core:** split `Working/block_cost.py::calibrate` into public pieces:
  - `time_model(name, n=CALIBRATION_N, fs=1.0, *, prewarm=False) -> (key, entry)`: pure. It times and returns, and
    `prewarm` runs the block's warm-up plus one untimed synthetic call (fix round F1's cold-start rule, now in
    the core).
  - `store_entries(entries: dict, path=None)`: the locked read-merge-write.
  - `calibrate()` becomes a loop over those, with identical results and file contents.
  - Keep `_key`/`_load`/`_save`/`_FILE_LOCK` private, and add no new users of them.
- **`webui/server/worker.py` (new):** move the generic pool here:
  - the spawned single-worker pool, `__main__` hidden on submit, `watch_parent` as initializer;
  - `terminate(pool)`, `shutdown()`, `run_in_worker(...)`, `on_stop(fn)`, a public `Stopped`;
  - one atexit registration made once at import (with corpus's `atexit` fallback);
  - a `one_shot()` (or similarly named) context manager for a throwaway single-task process, which calibration uses.
  - corpus.py keeps only coverage. Update every caller and test to the new names; do not leave aliases unless a
    caller outside this package needs one. `runtime.py` (~line 288) calls the shutdown.
- **Calibration:**
  - `calibrate_child.py` becomes about `import module; return os.getpid(), *block_cost.time_model(name, prewarm=True)`,
    with no tempfile and no `_key`.
  - chain.py gets one strategy attribute, e.g. `CALIBRATOR: Callable[[str, str], int]`, defaulting to the in-process
    route, with a `_calibrate_on_thread` alternative.
  - Delete `_REAL_CALIBRATE`, the identity check, the `CALIBRATION_WORKER` string, `_child_call`, `hold_s` and
    `_BC_ATEXIT`.
  - Tests set the strategy, or the child function, directly.
  - The parent stores the entry with `block_cost.store_entries`.
- **One keyed-lock helper** for `_SB_LOCKS` and `corpus._coverage_lock`, if their eviction semantics can be
  reconciled without changing behaviour (one flight per key, bounded registry). If they cannot, leave them and say
  why.
- **Minor:** `chain.py:~470-476`, where `wait_s` is both an optional float and a mode switch (None means "validate").
  If it can be made one comprehension without changing behaviour, do it.

## Behaviour that must not change

- **One calibration child at a time** (`_BC_PROCESS_SLOT`, F6), never queued behind the corpus maps' worker.
- **Timeout:** a child is stopped after `CALIBRATION_TIMEOUT_S`, and the model reads "failed" with that message (F2).
- **The child ends with the bridge** (`watch_parent`).
- **The shared calibration file** is written only in the bridge's process, under the file lock, to the path resolved
  when the request started (a sandbox's runtime copy).
- **Every calibration process is stopped at interpreter exit**, before concurrent.futures joins its workers.
- **The calibrated state records the child's `pid`.**
- **The corpus maps and the Map overview** keep exactly their current worker, fallback, `Stopped` and on-stop
  behaviour.
- **calibrate()'s on-disk JSON** is byte-for-byte the same for the same timings.

## Files

`Working/block_cost.py`, `webui/server/worker.py` (new), `webui/server/corpus.py`, `webui/server/chain.py`,
`webui/server/calibrate_child.py`, `webui/server/runtime.py`, `webui/server/discovery.py` (only `_SB_LOCKS` and its
users), `webui/server/discovery_map.py` (ONLY the lines that import or call corpus's worker names and `_Stopped`;
another package rewrites that file's caches next, so change nothing else there).

Tests: `tests/test_webui_site_x_calibration.py`, `tests/test_webui_discovery_map.py`, `tests/test_coverage_map_compute.py`,
`tests/test_webui_routes.py`, `tests/test_webui_run_routing.py`, `tests/test_webui_w3f_ui.py`, every
`tests/test_block_cost*.py`, and `grep -rln "coverage_pool\|run_in_worker\|_Stopped\|_MainHidden\|_terminate\|block_cost\._" tests/`.
Run them all before your first change and record the failure set: `test_webui_routes` has three known coverage-route
failures on main (BACKLOG, 2026-10-21 table). Compare by set at the end. `Working/block_cost.py` is core: run every
test file that imports it.

Smoke units for the manager: `zzzzzzzzzzz_site_x`, `zzzzzzzzzzz_corpus_map`, `zzzzzzzzzzz_a1_site_map`, `analyse`.
