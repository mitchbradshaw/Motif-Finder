# Code-quality review of the 19–21 Oct wave — findings and what was done (2026-10-25)

**In plain words.** The overnight passes of 19–21 October fixed real problems quickly, but several agents working
in parallel each solved the same small problem in their own way. The result works, and it carries four main kinds
of debt:

- **The same helper written several times.** Five "share one read" caches, three "stale answer while a fresh one
  computes" caches, two functions called `extentOf` that disagree about an empty list.
- **State spread over flags and timers** where one small model would do: the Review inspector's advance and
  prefetch logic, the Grouping editor's job, Discovery's deep-link handling.
- **The bridge reaching into private parts of the core** instead of the core offering a proper function: block-cost
  calibration.
- **One file pushed past 1000 lines:** `library/GroupingPage.tsx`.

Think of a kitchen where three cooks each brought their own whisk: nothing is broken, but the next cook has to work
out which whisk does what. The fixes below keep what the tool does exactly the same and take the duplicates away.

Scope: `git diff 7d2d695..16b05d2`, application code under `webui/` and `Working/` (113 files, +7083 / −543). Throwaway
tooling under `scripts/night/` was not reviewed. Three read-only reviewers covered Discovery, Analyse/Explore and
Review/Library; the manager checked each headline claim against the code before acting on it.

## Findings, most severe first

| # | Finding | Where | Verified | Package |
|---|---|---|---|---|
| 1 | Five hand-rolled "share one read" caches. Two export an interface named `SharedRead<T>` with different shapes; each file's header cites a "near-sibling" and writes another anyway. The old header hook is kept "for its other callers" but has none, and the test pinning it is red on main (BACKLOG:128) | `shell/sharedRead.ts`, `library/groupingsRead.ts`, `explore/coalesce.ts`, `shell/heldOutLock.ts`, `analyse/useAdapters.ts`, `api/needYou.ts` | yes, and the red test re-run | tq-reads |
| 2 | Review's advance, prefetch and write ordering is seven interacting mechanisms (two settle timers, a `live` flag, `onItem`/`timers` refs cleared in three places, a module-level counter, four copies of the "try again" guard). The F1–F4 fix round patched interactions between them | `review/Inspector.tsx`, `store.ts`, `ClusterView.tsx` | read | tq-review |
| 3 | `QueueRow.judged` still computes the bug night-a fixed (`… \|\| !!base`). A second field (`servedJudged`) plus `baseJudged()` reconstruct the right answer | `api/review.ts:250-251`, `review/judged.ts` | yes | tq-review |
| 4 | The carry/invalidate policy rests on a bare cast (`(e ?? {}) as CarryFields`) and an undeclared `detection_id`, mixes row ids and detection ids in one set, and sits in the middle of `write()` | `api/review.ts:~605`, `Inspector.tsx`, `queue.ts` | read | tq-review |
| 5 | Calibration rebuilds `block_cost.calibrate` from four private names (`_key`, `_load`, `_save`, `_FILE_LOCK`), through a scratch file, because the core has no "time it and return" function | `webui/server/calibrate_child.py`, `chain.py:340-395` | yes | tq-worker |
| 6 | The production dispatch depends on whether a test monkeypatched the core (`block_cost.calibrate is _REAL_CALIBRATE`). There are three overlapping test seams, one unused (`hold_s`) | `chain.py:34, 406` | yes | tq-worker |
| 7 | A second copy of corpus's spawn-pool lifecycle in chain.py, using corpus privates (`_MainHidden`, `_terminate`, `_POOL_LOCK`). Generic worker plumbing (`run_in_worker`, `_Stopped`) lives in the coverage module, so the Map imports corpus privates | `chain.py`, `corpus.py:592-850` | yes | tq-worker |
| 8 | Two stale-while-revalidate caches in `discovery_map.py` (overview, levels), already drifted (deep vs shallow copy; a level in flight but not yet held is computed twice). corpus.coverage is a third | `webui/server/discovery_map.py` | yes (structure) | tq-mapcache |
| 9 | The WAL-snapshot fingerprint block is written three times in the core, and `compute_level(level: str, args: dict)` is a stringly-typed protocol shaped by the bridge's cache key | `Working/discovery/detection_map.py:618-677`, `coverage_map.py:76-100` | read | tq-mapcache |
| 10 | `GroupingPage.tsx` crossed 1000 lines (976 → 1013). It mixes four concerns and shadows the app's `extentOf` with a private one. The new `treeSource.ts` re-declares `DISTANCE_BASES`, `groupingNum` and `newestGrouping` | `library/GroupingPage.tsx`, `treeSource.ts` | yes (line count) | tq-grouping |
| 11 | The grouping job has four refs for one cancellation; the auto-build is a seven-term predicate feeding a child ref read during render | `GroupingPage.tsx:252-337, 735-779` | read | tq-grouping |
| 12 | Two exported `extentOf`s, one returning null on an empty list and one `[Infinity, -Infinity]`, plus three more private copies of the scan | `kit/extent.ts`, `charts/domain.ts`, `eventFigures.ts`, `common.tsx`, `kit/plots.tsx` | yes | **tq-quick (merged)** + tq-analyse |
| 13 | Session writes in three copies (`putScope`/`putScopeLink`/`putRecording`), which grew a `bare` branch and three `heldOut ?` branches | `api/discovery.ts:134-161`, `session.ts`, `chrome.tsx` | read | tq-scope |
| 14 | The deep-link state is spread over refs, identity-compared state, an effect keyed on a string, and a three-way ternary | `discovery/session.ts:95-147` | read | tq-scope |
| 15 | "Is this answer for the current request?" is written twice (`scoreRead.ts`, `RunActs`) as a workaround for `useSourced` keeping stale data | `scoreRead.ts`, `RunsPage.tsx:514` | read | tq-scope |
| 16 | MapPage's hide/sort layout is copied between levels; `arrange` returns keys, so callers rebuild lookups with `!`. SignalStrip pushes a closure up to its parent, and hover uses a magic `'__signal'` key | `discovery/MapPage.tsx` (403 → 675) | read | tq-mappage |
| 17 | Formatters copied because of the "no imports, so Node can run it" rule (`fmtNum` = `fmtN`; `short` = `shortName`). The rule is stricter than needed: Node 25 resolves `.ts` imports, and `review/axis.ts` already does it | `analyse/fmtNum.ts`, `pickTemplate.ts` | yes (precedent) | tq-analyse |
| 18 | The marked-event and legend-toggle state is written twice with opposite models; a re-sort duplicates `useMotifs`' order; `path` re-implements `polylinePath` | `IntervalFigures.tsx`, `EventShapeFigures.tsx` | read | tq-analyse |
| 19 | The legacy span-shift rule is written in SQL three times; `unwritten_counts` copies `queue_counts`; the queue listing strips `filters` in the route while `_queue_payload`'s docstring says it still carries them | `library.py:1438`, `corpus.py:882`, `discovery.py:1101`, `queues.py:448`, `review.py:751` | read | tq-rules |
| 20 | `_SB_LOCKS` is a third per-key lock registry; `RunRow.hasActions` repeats its four render conditions by hand | `discovery.py:1328`, `chrome.tsx:575` | read | tq-worker / tq-scope |
| 21 | Dead mode: IntervalTimeline's `histogram` prop (the only caller passes `false`) | `IntervalTimeline.tsx` | yes | **tq-quick (merged)** |

### Rejected or left alone, with the reason

- **IntervalFigures' fallback for a payload without `next_within_gap_s` is not dead.** Restored jobs carry payloads
  persisted before 2026-10-20 (`app.py:570`, the job persist).
- **`vite.config.ts`'s `build:demo`** hides Cross-channel through test ids and an inline redirect script. That is
  brittle, but whether the demo build is still wanted is the researcher's call; it is untouched.
- **`registry.tsx`'s `p.rose || isEventShapeTable(...)`** keys on the payload, not the block name. That is acceptable;
  the root cause is a cache restore that loses its meta sidecar.
- **`IntervalFigures`' `Math.max(...m.rowTotal)`** spreads over a handful of classes. It is harmless.
- **SeedPage and other files already over 1000 lines** before the wave (SeedPage 1120, `discovery.py` 5.9k,
  `library.py` 4.4k) were not split. Only the file this wave pushed over the line is in scope.

## Outcomes

Every package ran the same loop:
- an implementer agent in its own worktree, test-first (a red commit, verified by the critic from an export);
- a separate critic agent (`critic.md`), told to prove behaviour unchanged against the old code rather than trust
  the implementer;
- one fix round when the critic asked for it;
- the manager's gate: `tsc -b`, the build, the named tests, and smoke units walked on a fresh sandbox, compared by
  failure SET against the same units walked on unmodified main.

| Package | What is simpler | Critic | Fix round found |
|---|---|---|---|
| tq-quick (manager) | one `extentOf` (`charts/domain.ts`); `kit/extent.ts` gone; the dead interval-histogram mode gone | merge as is | — |
| tq-reads | one shared-read primitive (`api/sharedRead.ts` + `useSharedRead`) replacing five caches; dead `api/needYou.ts` gone; the red header-count test (BACKLOG:128) green | merge as is | a ttl-0 read kept a ~90k-detection spans object alive after the page closed |
| tq-review | the Inspector's seven timers/refs/flags → `review/cursor.ts`; one "try again" refusal in the store; `judged` computed once; typed carry fields | merge as is | — (two old bugs fixed on the way: the warm-ahead window was thrown away after an undo, and an undo left the verdict flash stuck) |
| tq-worker | the bridge's worker pool in `webui/server/worker.py`; `block_cost.time_model` / `store_entries` public; no test seam in the production path; one keyed-lock helper; corpus.py 992 → 824 | merge after fixes | a test made flaky by the (intended) end of calibration queueing behind the corpus worker's start |
| tq-grouping | `GroupingPage.tsx` 1013 → 446 lines across five files; one AbortController per job; `treeSource.ts` gone | merge after fixes | **a real regression caught:** on the polling path a job could settle twice and Save/Apply write the grouping twice |
| tq-analyse | one formatter, one short name, one extent rule; `useMarkedEvent` / `useSeriesToggle` shared by the two figure pages; a dead overlay branch gone | merge as is | — |
| tq-mappage | `MapPage.tsx` 675 → 122 lines (`discovery/map/`); hide/sort written once; no closure in state, no `'__signal'` sentinel | merge as is | — |
| tq-scope | one `writeSession`; the deep-link state in one hook; "is this answer current" once in the seam (`useSourcedFor`, pure rule in `api/keyedRead.ts`) | merge after fixes | **a visible regression caught:** every scope edit fired a hashchange that wiped toasts older than 1 s |
| tq-mapcache | one stale-while-revalidate `_Cache` for the Map; one `snapshot_read` in the core; no stringly-typed `compute_level` | merge as is | — |
| tq-rules | the legacy span-shift SQL written once (`spans.absolute_sql`); one `_detection_counts`; `_queue_payload(filters=…)` | merge as is | — |

### On main (local, not pushed)

`79ed030` tq-quick · `146abb2` wave 1 (reads, review, worker, grouping, analyse, mappage) · `23e16d7` the smoke-state
fix · `b7fea24` wave 2 (scope, mapcache, rules) · `4c03b95` tq-polish (the renderer's last private extent loop, two
critic nits). Every `tq/*` branch is kept.

**Full suite on `4c03b95`** (a worktree, `webui/.venv`, `-n 4`, 48 min, 0.5 GB free RAM): 5630 passed, 15 skipped,
3 xpassed, 7 failed.
- Five fail on main too and are already in the BACKLOG 2026-10-21 table: the surrogate-predicate guard,
  `test_webui_discovery_windows`, and the three `test_webui_routes` coverage tests.
- One is the worktree-only absent `Plots/` file (`test_drop_motifs_nulls1`).
- One is new to the list and not reproduced:
  `test_perf_scoring_reads::test_concurrent_reads_of_a_stale_map_schedule_one_recompute`. It passed 3/3 alone,
  12/12 under four parallel copies, and 156/156 across two `-n 4` runs of its file. The pre-wave base passes the
  same stress 12/12. Its `all(... stale)` assertion assumes all six reader threads finish before the worker's
  recompute does. It is logged in the BACKLOG as a timing-dependent test.
- The header-count test that was red on main is green.

### Found on the way: for the researcher

1. **"Send N unjudged to Review" can count more than Review then shows.** The count includes detections on
   held-out recordings while that lock is ON; Review's own queue page leaves them out. With the lock off the numbers
   always agree. The cause is `discovery.py::get_run_unjudged` → `queue_counts` / `unwritten_counts` with no held-out
   exclusion. Not changed: whether Send N should exclude held-out recordings is a research decision.
2. **The Library's quiet-window null counts surrogate detections as real ones.** `library.py::_library_detections`
   has no `not_surrogate` / `not_window_part` filter. So a surrogate run's detections count as "touches a detection"
   in that null. Not changed; it needs its own look.
3. **A smoke state that could never prove what it checked.** `zzzzzzzzzzz_an_library_tree`'s "build the tree then
   apply it" waited for the atlas grid, which sits under the editor the whole time. It passed on main only because the
   atlas behind loaded slowly. Fixed in the manifest: it now waits for Apply's own navigation.
