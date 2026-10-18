# corpus-map-off-the-request — report

Branch `worktree-agent-a72dabecf5787addb`, worktree `.claude/worktrees/agent-a72dabecf5787addb`, base `60d8c09`.

## In plain words (for the researcher)

Think of the home page's map as a wall chart that someone has to redraw by hand whenever a run adds new marks.
Before this change, the bridge stopped serving every other page while it redrew the chart. On the big database that
took up to two minutes: "the site hangs after a run finishes". Now the old chart stays on the wall with a small grey
note saying "updating · the map is from before the last run; recomputing…". A separate worker (its own process, so
it does not slow the bridge down) redraws the chart, and the new one replaces the old when it is ready. The page
checks every 3 s. The numbers on a finished chart are exactly the ones you got before.

## Assumed

- **A read with `db_path` never computes. A library call without it computes in place, as before.** The route
  (`app.py`) and the start-up warm pass the database path, so neither computes in the bridge's own interpreter.
  Direct calls such as `corpus.coverage(conn, ...)` from scripts and about twenty core tests, often on an in-memory
  database that no worker process could open, keep the old synchronous behaviour.
- **A poll of a map whose recompute is queued or running does not fingerprint again.** This goes slightly past the
  prompt (see the numbers). Such a poll answers the last map, still marked stale, in about 4 ms, where a
  fingerprinting read costs 300–500 ms of interpreter time. The first read after the worker finishes fingerprints as
  usual, so a change made during the recompute is still noticed and recomputed. Pinned by
  `test_a_poll_while_the_recompute_is_queued_does_not_fingerprint_again`.
- **`warm_coverage` schedules every file, then waits for the worker** (at most 30 min, `WARM_WAIT_S`) before it
  returns. That keeps the warm's log line in `discovery.warm_last_scores` true, and keeps the template-score warm
  starting after it, as today. `discovery.py` is not in my files.
- **The held-out answer is passed to the child** (`compute(..., held_out=)`). The parent's key already carries it,
  and a script's `Working.config.HELD_OUT_UNLOCK` override lives only in the parent's memory.
- **A pending answer's rows are not drawn as counts.** The page treats them as "no rows" and shows the skeleton with
  "computing the map for the first time…" (`coverage-pending`), so a zero is never shown as if it were a count.
- **Failure.** When the last recompute of the current state failed, the read raises `CoverageFailed` ("the corpus
  map for X could not be computed: …"), and the app's loud handler turns it into a 500 and a red card. A changed
  state schedules a fresh attempt. A failure is never served as the old map.
- **Commit trailer.** The prompt asked for "Claude Fable 5.1". I used the model I am, as the session's attribution
  rule and `UX-1015-common.md` both state: `Co-Authored-By: Claude Opus 5.5`.
- **`webui/smoke.py` got two append-only action kinds**, `eval` (run a script in the page and wait for it) and
  `wait_gone` (wait for a selector to detach). The state needs both: a Settings API call, and "the notice goes away
  within 180 s". No action kind existed for either.

## The state machine (five lines)

1. A read computes the key and the in-process fingerprint. A memory entry with that fingerprint is **fresh**.
2. If the key is already queued or computing, the read answers the last map **stale** (or empty and **pending**)
   without fingerprinting.
3. Otherwise it computes the stable fingerprint, sharing the first one's row memo. A disk copy with that fingerprint
   is **fresh** and goes into memory. A failure recorded for that fingerprint raises `CoverageFailed`.
4. Otherwise it **schedules** the recompute (one de-duplicated queue, one job at a time, on one spawned worker
   process) and answers the last map from memory or disk marked `stale: true` + `stale_since`. With no map at all
   it answers the empty shape marked `pending: true`.
5. When the worker finishes, the map goes to disk and memory under the fingerprints taken when it was scheduled, so
   a change made during the run shows as stale next time. If no process can start, the queue drains on a daemon
   thread that runs `wait_for_quiet` between channels, and the log says so.

## The numbers

Scale fixture: `tests/perf_fixture.py` FULL (16 ch × 721 h, 5,000,000 detections, 12,000 annotations), conda
interpreter, machine loaded (other agents' suites running). Scripts are in my scratchpad: `measure.py` and
`fptime.py`.

| what | value |
|---|---|
| first read after a change (answers stale) | **507–769 ms**: ~300–460 ms in-process fingerprint + ~75–90 ms stable (shared memo) + disk read |
| each poll while the recompute runs (3 s apart) | **4 ms** median (50 polls) |
| a fresh read, memory hit | 386–476 ms: the fingerprint alone, the same cost as at base |
| time to a fresh map (worker) | **148–219 s** (the old in-request compute measured 171 s wall here, under the same load) |
| parent CPU while the child computed (148 s window, polling every 3 s) | **1.16 s total, 1.12 s of it the reads' own, 0.03 s anything else** |
| the old in-request compute, for comparison | 171 s wall, **140.8 s parent CPU**, all of it holding the interpreter |
| worker start (spawn, first use) | parent CPU 0.12 s |

**Target missed: the read after a change is 0.5–0.8 s, not < 200 ms.** The floor is
`scoreboard.channels_fingerprint` itself, which costs 300–460 ms on 5 M detections. It reads every run's
`MIN/MAX(d.id)` and stitched-window count, and that runs query is not memoised. The fingerprint functions are
out of my scope. One read now shares one memo between its two digests (the stable one fell from 288–413 ms to
74–93 ms), and polls of a queued key skip fingerprinting. Before those two changes the first stale read measured
1.1 s with polls ~1.1 s each, and the parent spent 127 s of CPU on 136 back-to-back reads.
The next step is a `memo` key for the runs part in `channels_fingerprint`, or a cheaper "has anything changed"
probe (`MAX(id)` over runs, detections and annotations, plus the settings rows) in front of it. Both are
scoreboard changes.

## Tests and interpreters

- Red commit `56e577c` (tests only).
  - conda `test_coverage_map_compute.py` + `test_perf_scoring_reads.py`: 20 failed, 61 passed, 15 teardown errors.
  - venv `test_webui_ar_speed.py -k coverage`: 2 failed.
- `tests/test_coverage_map_compute.py` (new, 6 tests):
  - the moved `compute` and the bridge's thin `_coverage` match sha1 digests of base `60d8c09`'s `_coverage`
    answers on 7 questions over the scored fixture and the legacy span-relative fixture;
  - the read-only connection refuses a write;
  - the channel yield hook runs n−1 times;
  - **the worker child imports no `webui`/`server`/`fastapi`/`starlette`/`uvicorn` module** under a `__main__`
    that imports the bridge;
  - a control proves a plain spawned pool under that `__main__` *does* import `webui.server.corpus`.
  - Passed under **conda (6) and webui/.venv (6)**; under the venv FastAPI is importable, so the check is not
    vacuous.
- `tests/test_perf_scoring_reads.py` (conda): the scored and legacy builders take a connection.
  - `test_any_change_on_the_channels_redraws_the_corpus_map` (9 cases) is extended: pending first; fresh after the
    worker; stale with its marker right after the change; fresh after the worker; the in-place call agrees.
  - New:
    - `test_a_routed_read_never_computes_in_the_request` (the parent's compute is made to raise; mode is
      "process");
    - `test_concurrent_reads_of_a_stale_map_schedule_one_recompute` (6 readers → 1 compute);
    - `test_the_start_up_warm_goes_through_the_worker`;
    - `test_the_thread_fallback_yields_between_channels`;
    - `test_a_failed_recompute_is_a_loud_error_not_a_blank`;
    - `test_a_pending_answer_has_the_maps_shape_with_empty_layers`;
    - `test_a_poll_while_the_recompute_is_queued_does_not_fingerprint_again`.
- `tests/test_webui_ar_speed.py` (venv):
  - the restart test is rewritten for the new model; recomputes are counted by the worker
    (`coverage_status()["computed"]`), because a monkeypatched `_coverage` is invisible to the child;
  - `test_the_coverage_route_answers_at_once_and_never_computes_in_the_bridge`;
  - `test_a_failed_recompute_reaches_the_page_as_a_loud_error`.
- Green runs at the branch head:
  - conda `test_coverage_map_compute`, `test_perf_scoring_reads`, `test_import_boundaries`, `test_divergence`,
    `test_surrogate_never_a_detection`, `test_windowed_explore`: **120 passed**.

  - venv `test_webui_ar_speed`, `test_webui_corpus`, `test_coverage_map_compute`: **31 passed**.

- Client: `tsc -b` and `vite build` pass through the junction.

## The smoke state — `webui/smoke_pages/zzzzzzzzzzz_corpus_map.json`

**`explore.corpus` / `corpus-map-stale-at-once-then-fresh`** (`explore/corpus?rec=M2_aug_concat_fs1.mat`):

1. Wait for the heatmap, then wait for any `coverage-stale` left from the flows to go.
2. `eval`: read `analysis-defaults`, keep `iou` in `window.__ubSmokeIou`, and PUT `iou` 0.49 (or 0.48 if it was
   already 0.49).
3. Reload.
4. Within 2 s: **`coverage-stale` present and `corpus-heatmap` present.**
5. Within 180 s: **`coverage-stale` gone.**
6. `eval`: PUT the old `iou` back.
7. Expect the heatmap; expect no `coverage-stale`, `coverage-pending` or `render-error`.

On real data the 180 s may be tight: M2_aug's recompute measured ~100 s on the post-RQ4 database and 148–219 s on
the loaded fixture. If the iou had never been saved, the restore writes 0.5 explicitly, so the settings row now
exists and the home map recomputes once more after the walk (behind the page, marked).

## Files

- `Working/discovery/coverage_map.py` (new, UI-free).
- `webui/server/corpus.py`:
  - `coverage(..., db_path=)`, the worker, queue and pool, `coverage_status`, `wait_coverage_idle`,
    `clear_coverage_cache`, `reset_coverage_worker`, `shutdown_coverage_pool`, `CoverageFailed`;
  - `_coverage` is a thin call to the core;
  - `run_methods` and `_runs_matching` are aliases of the core's;
  - `corpus.spans` and `_absolute` are untouched.
- `webui/server/app.py` (the coverage route passes `rt.db_path`).
- `webui/client/src/explore/CorpusPage.tsx` (notice, pending line, 3 s poll).
- `webui/client/src/api.ts` (shared; append-only: three optional fields on `Coverage`).
- `webui/smoke.py` (shared; append-only: `eval` and `wait_gone` action kinds).
- `webui/smoke_pages/zzzzzzzzzzz_corpus_map.json`.
- Tests: `tests/test_coverage_map_compute.py` (new), `tests/test_perf_scoring_reads.py`, `tests/test_webui_ar_speed.py`.

## What is left

- **The read's fingerprint floor** (~0.3–0.5 s at 5 M detections), see above. It is the next candidate. Every
  memory-hit read of this map pays it too, as at base.
- **The detection map's levels 2 and 3** (`webui/server/discovery_map.py`, `Working/discovery/detection_map.py`:
  7.6 s and 3 s on the real database) are the next candidate for the same treatment. The pattern is a key, the last
  answer marked stale, and one worker. `coverage_map.py`'s split (`compute(db_path)` versus `compute_conn`) and the
  `_MainHidden` spawn guard can be reused as they are.
- **The template scorer** (`discovery._drain_scoring`) still scores on a thread in the parent.
- **No `Runtime.restore()` hook stops the worker.** It is a daemon process the pool's atexit joins. Tests call
  `wait_coverage_idle` before tearing a database down. `runtime.py` is not in my files.
