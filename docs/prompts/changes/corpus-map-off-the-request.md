# corpus-map-off-the-request — the home page serves its last map at once and recomputes behind it, off the interpreter

**Read first:** `CLAUDE.md`; `docs/prompts/fixup/UX-1015-common.md`; `docs/prompts/fixup/AR-speed-pass.md` (the speed
pass this continues) and its report `docs/prompts/fixup/reports/AR-speed-report.md`; then this file. Commit prefix
`corpus-map:`; every commit ends with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Test-first.

## Why (measured 2026-10-19, ledger `docs/prompts/fixup/reports/UX-1015-ledger.md`)

After any run is written on a recording, the next read of `GET /api/corpus/<file>/coverage` recomputes the corpus
map: ~100 s on the post-RQ4 database (5 M detections) for M2_aug, inside the request, holding the interpreter —
the home page's heatmap does not paint until it is done, and every OTHER page read in that window stalls (the
divergence is Python-heavy; numpy releases the GIL only inside its calls). In the full smoke walk that is ~30 states
timing out after the flows write their runs; for the researcher it is "the site hangs for minutes after a run
finishes". The disk cache AR added (`<runtime root>/cache/coverage/`) helps only for an UNCHANGED fingerprint.

## Facts

- `webui/server/corpus.py:294 coverage()`: key `(source_file, bins, verdicts, run_ids, method, held_out)`;
  memory cache `_COVERAGE_CACHE` keyed by `SB.channels_fingerprint(conn, rec_ids, settings_keys=COVERAGE_SETTINGS)`;
  per-key single-flight `_coverage_lock`; on a miss: the stable fingerprint → `_disk_read` → else `_coverage(...)` →
  `_disk_write`. `_coverage` (`:456`) reads ONLY the database: `q.list_recordings`, `_runs_matching`, and
  `DIV.channel_divergence(conn, rid, keep_runs)` per channel (`Working/discovery/divergence.py`), then bins. No
  `.npy` is touched. `warm_coverage` (`:433`) computes every file's home map at start through the same function,
  yielding between files with `wait_for_quiet` (`:418`).
- Route: `webui/server/app.py:168 get_coverage` (sync def → threadpool). Client: `explore/CorpusPage.tsx:87`
  `useSourced(() => getCorpusLive(...))`, a skeleton until data (`:239`), `ErrorCard` on failure; the payload carries
  `compute_ms`. `webui/client/src/api.ts` `req()` times reads out at 300 s (AR) — a recompute that outlives it
  surfaces as a `requestfailed` console error charged to whatever page is open.
- Tests to keep green and extend: `tests/test_perf_scoring_reads.py` (`test_an_unchanged_corpus_map_is_not_recomputed`,
  `test_two_concurrent_reads_of_one_corpus_map_compute_it_once`, `test_any_change_on_the_channels_redraws_the_corpus_map`),
  `tests/test_webui_ar_speed.py::test_the_coverage_map_survives_a_restart_and_ignores_unrelated_settings`.

## Decided (manager, from the researcher's standing rules: loud failure, no silent staleness, bulk arrays never in
the database)

1. **A read never computes.** `coverage()` answers at once: the fresh map when the fingerprint matches (memory or
   disk); otherwise the **last known map for that key** (memory, else disk, whatever its fingerprint) with
   `stale: true` and `stale_since` (the time the newer fingerprint was first seen), and it **schedules** the recompute;
   when NO map exists for the key yet (first ever request on a fresh sandbox), it returns `{pending: true}` with the
   same shape's empty layers so the page can draw its skeleton with a real "computing…" line, and schedules.
2. **The recompute runs in a worker PROCESS**, not a thread: `Working/discovery/coverage_map.py` (new, UI-free —
   move `_coverage`'s body there as `compute(db_path, source_file, bins, verdicts, run_ids, method) -> dict`, opening
   its own read-only sqlite connection; `corpus._coverage` becomes a thin call to it). The bridge owns ONE
   `concurrent.futures.ProcessPoolExecutor(max_workers=1)` created lazily (spawn; the child imports `Working` only —
   never `webui.server`, never FastAPI; assert that in a test by checking `sys.modules` inside the child), a queue of
   pending keys de-duplicated, one in flight at a time, results written to memory and disk on completion. The
   start-up warm (`warm_coverage`) goes through the same queue, so the parent never computes a map again. If the pool
   cannot start (a sandbox that forbids processes, a test), fall back to a daemon THREAD with `wait_for_quiet` between
   channels — but say so in the log line.
3. **The client shows the truth.** The Corpus page draws the stale map immediately with a one-line notice over the
   heatmap ("updating · the map is from before the last run; recomputing…", muted, `data-testid="coverage-stale"`),
   re-reads every 3 s while `stale` or `pending`, and drops the notice when a fresh map lands; a failed recompute is a
   red card as always (the route returns `error` with the sentence, never a blank).
4. **Nothing else changes:** the cells, keys and numbers of a fresh map are byte-identical to today's (pin it); the
   fingerprint rules stay (AR's tests); the held-out refusal stays; `compute_ms` stays and now means the read's own
   time (tens of ms).

## The work

1. `Working/discovery/coverage_map.py` with `compute(...)` (the moved body) and a tiny `main`-free entry the pool
   calls; `tests/test_coverage_map_compute.py` (conda): equals the old `_coverage` output on the `scored` fixture of
   `test_perf_scoring_reads.py` (import that fixture or copy its builder), and the child imports no UI module.
2. `webui/server/corpus.py`: the pool + queue (`_schedule(key, args)`), `coverage()` as decided, `warm_coverage`
   through the queue, `wait_for_quiet` kept for the thread fallback; a `coverage_status()` for tests
   (`{pending: [...], in_flight: key | None}`).
3. `webui/server/app.py`: the route unchanged except it passes the db path the pool needs (the runtime's sandbox
   copy, `request.app.state` or `_rt(request).db_path` — read how other routes reach it).
4. Client: `CorpusPage.tsx` notice + polling while stale/pending; `api.ts` types gain `stale?`, `stale_since?`,
   `pending?`.
5. Smoke: `webui/smoke_pages/zzzzzzzzzzz_corpus_map.json` (sorted last — it writes a run? No: it changes an
   analysis-default setting that the map reads, `iou`, through the Settings API in its actions, then opens the home
   page and expects `coverage-stale` within 2 s and the heatmap present; then waits for `coverage-stale` to go away
   within 180 s on the sandbox). Restore the setting in a final action.

## Files

Yours: `Working/discovery/coverage_map.py` (new), `webui/server/corpus.py`, `webui/server/app.py` (route body
only), `webui/client/src/explore/CorpusPage.tsx`, `webui/client/src/api.ts` (types), `tests/`. Do NOT touch
`corpus.spans`/`_absolute` (another branch owns them), the fingerprint functions in `scoreboard.py`, or the Discovery
pages.

## Method and gate

- Tests: conda `tests/test_coverage_map_compute.py`, `tests/test_perf_scoring_reads.py` (its two concurrency and
  change tests must still hold: a stale answer is allowed only WITH `stale: true`, and the next read after the
  worker finishes is fresh — extend `test_any_change_on_the_channels_redraws_the_corpus_map` accordingly, with a
  `coverage_status()`/`wait` so the test is not timing-based); venv `tests/test_webui_ar_speed.py` (the restart
  test), `tests/test_webui_corpus.py`; `tests/test_import_boundaries.py`.
- `tsc -b`, `vite build` through the junction. The smoke state above.
- Numbers for the report: on your scale fixture (`tests/perf_fixture.py` from AR), the read's latency after a
  change (target < 200 ms), the time to a fresh map, and the parent's CPU while the child computes (print the parent
  process's CPU seconds across the window — it should not grow).

## Stop and report if

the pool cannot be made to start under the sandbox's path redirections (then ship the thread fallback with the
per-channel yield and say how far it gets); or moving `_coverage` breaks a reader that imported it from
`webui.server.corpus` (grep first; keep a thin alias).

## Report

`docs/prompts/changes/reports/corpus-map-report.md`: **Assumed**; the state machine in five lines; the numbers; the
tests and interpreters; the smoke state; what is left (the detection map levels, the next candidate for the same
treatment).
