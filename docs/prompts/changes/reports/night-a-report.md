# night-a — Review and Discovery, driven on the scale fixture (2026-10-19/20)

Branch `worktree-agent-a81da0fe18f41b54d`, base `7d2d695`. Bridge: sandbox on 8767 over `tests/perf_fixture.py`
at full size (16 ch × 721 h, 60 Discovery runs, 5,001,200 detections, a 10 k review queue, 70 templates), own
`vite build`, Playwright through the conda python. Screenshots: `webui/runtime/night/*/` (gitignored).

## In plain words

Think of the site as a shop that opens at nine: tonight I walked in at scale and found the queue at the till
(Review took 26–53 s to show its first candidate), a clerk who answered the same question four times over (each
Discovery page re-scored every run), and a queue that said "closed" while 2,413 customers were still waiting. The
small ones are fixed; the big ones are listed with a one-line reproduction.

## Assumed

- **A carried or prior verdict on a row the bridge calls unjudged** (agent B's finding): the row is NOT judged; the
  verdict is shown prefilled as its prior. The bridge's `judged` flag decides; the counter and the page agree.
  (review-carry spec: a carried row is a written adjudication, so the bridge already sends `judged: true` for it;
  the rows that broke were explore-spans rows, human spans marked `seed` that the queue never asked about.)
- **"Pick another queue"** on a finished queue opens the queue picker of the queue on screen (`?pop=queues`), not a
  hard-coded queue.
- **A queue with no items** (zero detection ids) is allowed to exist (the core accepts it); the page now says it
  holds no items. Whether `create_queue` should refuse an empty set is left for the core owner.
- **Stepping settle time** 150 ms: an item not yet in the cache is read only after it has been on screen that long.
- Measurements were taken on a loaded machine (three night bridges, the RQ4 import): every wall-clock figure is
  noisy; the counts (requests, reads per channel, scorings per run) are what the tests pin.

## What I drove (`scripts/night/`)

- `night_a.py --url http://127.0.0.1:<port> --out <dir> --only load,keys,overlap,edges,discovery,visual` — the
  whole pass. `load` is read-only and safe on the real database; every other part writes verdicts through the
  bridge, so **sandbox only**.
- `trace_requests.py <url> [testid]` — every `/api/` request's start/end and when a testid paints.
- `run_bridge_sampled.py` — `run_server.py` with a stack sampler beside it (`webui/runtime/night/sampler.log`):
  how the busy-bridge cause was found.
- `profile_counts.py`, `profile_score.py`, `profile_route.py`, `probe_width.py` — one-off probes (copies only).

## Findings

| # | Page | Finding | Status | Where |
|---|---|---|---|---|
| 1 | Review | An explore-spans queue (2,413 left) opened on "Queue … is done": any row carrying a verdict counted as judged (B: 622 left, "No more items") | **fixed** `067b112` | `review/judged.ts` (new), `review/queue.ts:64,120,132`, `api/review.ts` rowOf (+`servedJudged`, appended) |
| 2 | Review | I then two quick arrows landed on the item after the judged one: the auto-advance timer (set after the POST returned) fired after the researcher moved | **fixed** `4f17bb0` | `review/Inspector.tsx` |
| 3 | Review | 40 fast arrow presses left 25–49 s of item reads queued on the bridge; verdicts pressed meanwhile re-wrote the same item (3 of 5 N presses on one item) | **fixed** `2b4cdb9` — settles in 3.5 s, 5 presses → 5 items | `review/Inspector.tsx` |
| 4 | Discovery | `/api/discovery/scoreboard` (every page asks it) took 54 s even with every score cached: no fingerprint memo, each channel's human rows re-read per run | **fixed** `c267f04` | `server/discovery.py` get_scoreboard + Compare band rows |
| 5 | Discovery | Identical scoreboard reads piled up: cold 492 s each, every page visit started its own copy (the bridge stayed busy 30 min after the browser left) | **fixed** `59f1bb2` — one lock per read in flight | `server/discovery.py` |
| 6 | Review | Finished queue read "No more items in the demo fixture … not in the fixture"; "Pick another queue" → fixture `q-12` (404); arrow toasts said "demo fixture" | **fixed** `90d3cef` | `review/common.tsx`, `Inspector.tsx`, `ClusterView.tsx`, `Shell.tsx` |
| 7 | Discovery | (C) 60 runs: rows squashed to 18 px | **fixed** `4b0b224` — rows 62/130 px | `discovery/discovery.css` |
| 8 | Review | (C) toolbar does not wrap at 1024 px | **fixed** `4b0b224` (wraps; at 1024 the page is still 1200 wide until C's `theme.css:64` min-width change lands) | `review/review.css` |
| 9 | Review | (C) bad queue id waits behind the queue list, red card flush to the edge | **fixed** `4b0b224` — unknown queue card in 52 ms | `review/index.tsx` |
| 10 | Discovery | (C) scoreboard: header, no body, no words | **fixed** `4b0b224` | `discovery/RunsPage.tsx` |
| 11 | Discovery | (C) unknown `?run=` shown as an amber ⚠ | **fixed** `4b0b224` (grey info) | `discovery/RunsPage.tsx` |
| 12 | Review | (C) `/api/review/queues` carries 9,743 detection ids per queue (78 kB) | **fixed** `4b0b224` — `detection_ids_count` | `server/review.py` get_queues |
| 13 | Discovery/all | The background template scorer holds the GIL ~7 s per template for 6–10 min after every bridge start (70 templates at scale); every request in that window is 3–35× slower (Review counts 6 s vs 0.17 s offline) | reported | `server/discovery.py:891` `_drain_scoring` runs `SB.score_runs` on a thread. Repro: start a sandbox bridge on the scale fixture, `curl /api/review/counts` in the first 5 min. Fix: score in the corpus worker process (needs a picklable Working-side entry point) or share the scoreboard's cache key |
| 14 | Discovery | Cold scoreboard for 60 runs × 16 ch is 8 min (492 s); the Runs page's score column waits that long on a fresh bridge, and the warm scorer computes the same scores under a different cache key (rule/span) | reported | `Working/discovery/scoreboard.py` `score_runs` (~7 s per run at scale) and the key at `:597` vs `discovery.py:1341` |
| 15 | Review | Queue open sends all 10 k rows (7 MB, ~2.4 s server) before the first candidate; with the header's repeated counts the inspector paints at ~8 s at scale | reported | `server/review.py:771` get_queue; a first-page read would cut it |
| 16 | Shell | `/api/review/counts` is re-read on every Header mount — Review mounts 3–4 Headers while opening (loading → queue → item), 4 counts reads per open, each 0.3–3 s at scale | reported (C's file) | `api/needYou.ts:13`, `review/index.tsx` loading branches |
| 17 | Shell | `/api/runs?limit=1` polled every 5 s on every page (1–2 s each under load) | reported (C's) | the jobs chip poll |
| 18 | Review | Ctrl Z pressed while a verdict POST is still in flight undoes the previous write (the in-flight one joins the stack only on its ack) — seen only while the bridge was starved | reported | `review/store.ts` commitWrite / Inspector `undo` |
| 19 | Discovery | Runs page: `where-fires` shrinks 388 → 315 px after its read lands; the scoreboard and browser below jump up 73 px | reported | `discovery/RunsPage.tsx:157` (Loading height 200 vs content) |
| 20 | Discovery | The template picker on a fresh bridge shows "scoring…" on 60 templates; ~4 land per 30 s (≈8 min to clear); it never blocks (paints in 55 ms) and re-reads every 3 s meanwhile | reported (by design; see #13) | `discovery/AddTemplateModal.tsx:39` |
| 21 | Review | `POST /api/review/queues` accepts `detection_ids: []`: a queue that can never hold anything | reported | `Working/review/queues.py` create_queue |


What held: no card ever showed an item other than the hash's (40 fast presses, sampled every press); a verdict
on an overlap set wrote every member, the class key stored `burst` on both, and Ctrl Z removed exactly them; undo
restores a prior verdict rather than blanking it; a one-item queue, an all-judged queue, a bad item, a bad cluster
and the cluster alias all render their cards with no console error.

Not driven tonight: the blind-test page (no blind queue in the fixture — `index.tsx` now picks it from the queue's
own read; the manager's walk covers `zzzzzzz_ah_blind_test`), a queue whose run was discarded, "Use these as
detections" twice, the seed strip's no-preview/no-cut states, the coverage strip's "run on the missing", the map's
poll during a running run.

## Load times (scale fixture, 1440×900, loaded machine)

Paint = the page's main card (`runs-list` for Runs, the inspector for Review); settled = no Discovery loading card
left. Before = first bridge (scorer running, old code); after = final code, scorer finished.

| Page | Paint before | Paint after | Settled after | API requests / 10 s after |
|---|---|---|---|---|
| Discovery runs | 1.2 s wrapper; runs list 7.6–20 s | 3.1–3.9 s | 12.5–15.6 s | 18 |
| Discovery seed | 0.9 s | 0.8 s | 0.9 s | 17 |
| Discovery compare | 0.9 s | 0.7–0.8 s | 0.8 s | 11 |
| Discovery map | 0.9 s | 0.8 s | 2.4–3.8 s | 6 |
| Review queue open (`#/review`) | 22–47 s | 7.5–8.2 s | — | 18 |
| Review inspector (deep link) | 26–53 s | 8.1–8.5 s | — | 16 |
| Scoreboard, 60 runs × 16 ch, cached | 54 s | (memo) | — | — |
| 40 fast arrow presses, settle | 25–49 s | 3.5 s | — | — |

## Tests (interpreter per file)

- `tests/test_night_a_review.py` — conda python (+ node for `review/judged.ts`): 12 passed. Pins the queue-end
  words and states, no fixture ids, run-row height, toolbar wrap, the queue route deciding from its own read, the
  scoreboard empty row, the info callout, the judged rule (run under node), the auto-advance guard, the step settle.
- `tests/test_webui_night_a.py` — webui/.venv: 3 passed. One channel read per channel per scoreboard read; two
  identical concurrent reads score each run once; the queue list carries a count, not the ids.
- Regression files run (webui/.venv): `test_webui_ar_speed`, `test_perf_scoring_reads`, `test_webui_discovery`,
  `test_webui_discovery_runlist` (172 passed), `test_webui_discovery` again after the lock (84 passed),
  `test_webui_review` (with night_a, 35 passed); conda: `test_import_boundaries` 4 passed.
- `tsc -b` and `vite build` pass from the worktree through the junction.

## The three worst I could not fix

1. **A fresh bridge is slow for its first 6–10 minutes** (#13): the template scorer holds the interpreter; at
   scale every page is 3–35× slower until it finishes. The morning walk on a just-started bridge will feel it.
2. **The cold scoreboard is 8 minutes at scale** (#14): the Runs page's score column, Compare and Seed all wait on
   it after any restart; the warm scorer computes the same thing under another key.
3. **Opening a 10 k queue ships 7 MB before the first candidate** (#15, with #16's repeated counts): the inspector
   paints at ~8 s at scale on a quiet bridge.
