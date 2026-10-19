# map-overview-cache — the Map overview serves its last answer at once; the recompute runs off the request

**Read first:** `CLAUDE.md`; `docs/prompts/fixup/UX-1015-common.md` (isolated worktree, no `DATA/`, never a junction or
copy pointing at `C:\Users\mmebr\Documents\CNN\DATA`, the interpreters, the client toolchain through the junction, no
new dependencies); `docs/prompts/changes/corpus-map-off-the-request.md` and its report (the pattern this copies);
`docs/prompts/changes/reports/night-a-report.md` §"three worst" (the scorer thread). Commit prefix `map-cache:`; every
commit ends with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Why (measured on the live bridge, 2026-10-20)

`GET /api/discovery/map` (the Map overview, `webui/server/discovery_map.py:61` → `Working/discovery/detection_map.py`)
takes **17–21 s on every call, uncached** (16.7, 17.6, 20.7 s after the RQ4 batch 2 import; 11–15 s before it; the
same before batch 3). It grows with the number of Discovery runs — now **289 across 8 sessions** — and more are
coming. Demo is 2026-10-21. The per-recording routes (`/map/dataset`, `/map/channel`, runs, scoreboard, overview)
are 0.2–6 s and are NOT this prompt. The researcher's standing rule (2026-10-18): "the website runs quickly and
smoothly, regardless of the size of the data/detections".

## What to build (the corpus-map pattern, already on main as 43ee443)

1. **A read never computes.** `GET /api/discovery/map` returns the last computed overview at once. If none exists
   yet, it returns `{pending: true}` and schedules the compute; the page shows its existing `map-refreshing` chip
   (`discovery/MapPage.tsx:277`, `useMapRefresh`) and polls until the map lands. If the stored map is older than the
   database, it returns it with `stale: true` and `stale_since` and schedules a recompute. Fresh reads carry neither.
2. **The recompute runs in a worker process** — `ProcessPoolExecutor(max_workers=1)` with `__main__` hidden during
   spawn, a parent watcher, `shutdown_…()` from `Runtime.restore()`, a loud `MapFailed` on error, exactly as
   `Working/discovery/coverage_map.py:105 compute_fingerprinted` and `webui/server/corpus.py` do it. Reuse their helpers;
   do not write a second pool.
3. **Keyed by a fingerprint of what the overview reads**: `Working/discovery/scoreboard.py:555
   channels_fingerprint(conn, recording_ids, settings_keys=…, stable=True)` over every recording the overview covers,
   plus the run set (count + max run id + max detection id is NOT enough — a discarded run changes the map; hash the
   run ids and their statuses). The map is stored under the fingerprint the WORKER read (not the one the request
   computed), on disk under `<runtime root>/cache/map/` so a restart serves it at once.
4. **Running runs**: while any Discovery run is `running`, the page's 5 s poll must not trigger a recompute per poll;
   coalesce to one scheduled compute at a time per key (single flight), and a running run marks the served map
   `stale: true` with the chip's "re-counting · a run is still going".

Files: `webui/server/discovery_map.py`, `Working/discovery/detection_map.py` (a `compute(db_path, …)` entry point
usable from a worker; no browser imports), `webui/server/corpus.py` only to share the pool helpers (extract, do not
duplicate), `webui/client/src/discovery/MapPage.tsx` (+ `api.ts` if the response type changes), `tests/`. Do not
touch the per-recording map routes beyond what sharing the cache needs.

## Tests first (red before green)

- A read on a database with no stored map returns `pending: true` within 100 ms and schedules exactly one compute.
- A second read before the compute lands returns `pending: true` and schedules nothing.
- After the compute, a read returns the map, no `stale`, in under 50 ms (conda `tests/test_discovery_map_cache.py`,
  pure core + a `TestClient` in `tests/test_webui_discovery_map.py` under `webui/.venv`).
- A run added (or discarded) after the compute: the read returns the OLD map with `stale: true` at once and the next
  compute's result replaces it; the stored key is the worker's fingerprint.
- A worker exception reaches the read as a 500 with `MapFailed` in the body (never a blank map).
- `tests/test_import_boundaries.py` stays green.

## Gate and report

`tsc -b`, `vite build`, the tests above under both interpreters, then the `zzzzzzzzzzz_corpus_map`, `discovery` (full
walk only) and `zzzzzzzzzzz_a1_coverage` units on a fresh sandbox (`--sandbox --port <yours>`, never 8765/8766). Report
`docs/prompts/changes/reports/map-overview-cache-report.md`: Assumed; before/after timings on the sandbox copy of the
real database (cold, warm, stale-served); what you could not do.
