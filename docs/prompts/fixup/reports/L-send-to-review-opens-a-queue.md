# Report — Fixup L: *Send N unjudged to Review* makes a queue that opens

Run 2026-10-03 on `main`, in the main checkout, alone on the machine. Commit prefix `fixup-l:`. The first commit,
`e15beee`, touches only `tests/` and fails 4 tests under conda (`queue_candidates` had no `run_ids`;
`queues.find_open_queue` did not exist) and 5 under `webui/.venv` (the Discovery route returned no `queue_id`,
wrote a descriptor, and the Review bridge had nothing to open). Every bridge ran in `--sandbox`; nobody else was
running, so the shared `webui/client/dist` was built from the sources and served as is (`client_dist = …\dist`
in the bridge banner). Nothing wrote to the real `DATA/db/annotations.sqlite`.

**What is true now, in one paragraph.** Discovery's *Send N unjudged to Review* creates a `review_queues` row
through `Working.review.queues.create_queue` — `source_kind` `discovery-run` for a template run, `seed-search`
for a seed run — whose filter is the **run ids** the Discovery run is made of, never its run group; the toast
names that queue and its *Open Review* opens it (`review/queue/<id>`); a second send of the same run returns
the same open queue; the Runs page's *Sent N* state links to it; the Analyse chain footer's *Pass N to Review*
is the slideshow's *Send N to Review* on the same run, behind one hook; and the descriptor in
`discovery_sessions.state_json`, its `GET /api/discovery/queues` and the client's `getDiscoveryQueues` are gone.
A queue over a run with a paired surrogate holds none of the surrogate's detections, and a test says so.

---

## 1. The three gestures — what each did before, and does now

| Gesture | Before (measured 2026-10-02, `RESEARCH_READINESS.md` cross-cutting 1) | Now |
|---|---|---|
| **Discovery › Runs · *Send N unjudged to Review*** | `POST /api/discovery/runs/{key}/review` counted the unadjudicated candidates and wrote a descriptor into `discovery_sessions.state_json` (`discovery.py:1760–1806`); **no `review_queues` row**. The toast read *"5 of 5 unjudged in 'Discovery · seed a9147c unjudged' · verdicts write adjudications"*; `GET /api/review/queues` still listed two queues; *Open Review* was `navigate('review')` and landed on Review's landing queue — `#/review/queue/1/119`, *"Library - extract events"* | The route makes the row (`create_queue`, filters `{"run_ids": [...]}`, `note` carrying run key, label, session and run ids), returns `queue_id`, `queue` (its name), `reused`, `unjudged / judged / total` from `queue_counts`, `source_kind`, `run_ids`, `writes`. Toast: *"3 unjudged in 'Discovery · mp_threshold' · verdicts write adjudications"* — *Open Review* → `#/review/queue/3/1206`, the queue named *Discovery · mp_threshold*, *writes adjudications*, **0 / 3**. Sent twice → the same queue, toast prefixed *already sent ·*. The acts then read *Sent 3 · open in Review · then refresh* and open the queue |
| **Analyse › block page slideshow · *Send N to Review*** | Already real: `POST /api/review/queues` with `{source_kind: 'discovery-run', filters: {run_id}}`, then `navigate('review/queue/<id>')` (`api.ts:133`, `registry.tsx:138`) | The same call, now made through `analyse/sendToReview.ts::useSendRunToReview` — the one hook both Analyse buttons share |
| **Analyse › chain footer · *Pass N to Review*** | A disabled button titled *"out of slice scope"* (`ChainPage.tsx:449`) | The same hook. Enabled after a completed run whose terminal is a SpanSet with N > 0; otherwise disabled with the reason on the button (*needs a completed run with a SpanSet terminal* / *needs a completed run* / *these spans are from a stale run · re-run first* / *no spans to review*). Clicking it opens the queue it made |

The queue's name is `Discovery · <run_key>`, not the label: a seed run's label repeats across its re-runs
(`seed a9147c`, `seed a9147c_2`, `seed a9147c_3` all carry the label *seed a9147c*) and the run key is what the
Runs page and the scoreboard show.

## 2. The trap, and the test that pins it

A paired surrogate run joins the **same run group** as the run it shadows and writes `detections` rows of its
own. Measured in the 2026-10-02 sandbox copy (`webui/runtime/20261002-180621/annotations.sqlite`, read-only):

| run group 7 | runs | detections |
|---|---|---|
| real (`surrogate_of_run_id IS NULL`) | 101, 105, 109 | 3 + 61 + 10 = **74** |
| paired surrogates (`surrogate_of_run_id` = 101 / 105 / 109) | 103, 107, 111 | 79 + 82 + 88 = **249** |

A queue keyed on the group would have put 249 detections of phase-randomised noise in front of the researcher
and written human verdicts against them. So:

- `queries.queue_candidates` takes `run_ids` (additive; `[]` is a queue over nothing, not over everything;
  composes with the other filters) — `tests/test_adjudications.py::test_queue_filters_by_a_set_of_run_ids`;
- `ReviewQueue` accepts `run_ids` (and `_FILTER_KEYS` lists it), so a `review_queues` row whose `filters_json`
  carries `run_ids` resolves through the existing `_resolve_detections` with no change to the resolver;
- `tests/test_review_queues.py::test_a_queue_over_run_ids_holds_none_of_the_paired_surrogates_detections`
  builds one real run (1 detection) and its surrogate (3 detections) in **one** group, makes a `discovery-run`
  queue with `filters={"run_ids": [real]}`, and asserts the items are exactly the real detection, none of the
  surrogate's reach it even with `include_judged`, and the counts are `{total 1, judged 0, remaining 1}`.
  `test_a_seed_search_queue_takes_run_ids_too` does the same for `seed-search`;
- the route test `test_webui_discovery.py::test_send_to_review_makes_a_review_queue_over_the_runs_real_runs_only`
  runs a real fan-out on the synthetic fixture (whose Settings › Nulls default pairs a surrogate per channel),
  asserts the surrogates wrote detections at all (so the exclusion is being tested), and that every row of the
  queue the route made is on a real run and none on a surrogate.

The route takes the ids from `_run_ids(conn, row)` (`discovery.py:329`), which already excludes surrogates and
already covers a fan-out that reused runs across more than one group. `source_ref` is left NULL on purpose:
`_resolve_detections` ANDs `run_group_id = source_ref` onto the filter when it is set, and that would silently
shorten exactly the reused-runs case `_run_ids` exists for. The Review bridge's item payload already reads the
run off the item when `source_ref` is NULL (fixup-a item 7), so the inspector subtitle still names the run.

What the surrogate exclusion is **not**: a resolver-level `surrogate_of_run_id IS NULL`. A queue made some
other way with `run_group_id` alone still sees the surrogates; that is `fixup-T`'s question and this prompt
owns only this filter.

## 3. What happened to the descriptor

Gone, on both sides. The route no longer writes `review_queues` into `discovery_sessions.state_json`, and a
session that still carries the pre-fixup-L list loses the key on its next send (the 2026-10-02 sandbox copy's
session 2 held one — `seed a9147c_3`, `run_ids [85, 87, 89]`, `n 5` — beside no row at all: the two records of
one queue the prompt describes). `GET /api/discovery/queues` is removed; `api.ts`'s `getDiscoveryQueues` and
the `DiscQueue` type with it (no caller). `ReviewBody.limit` is removed too: the old route reported
`queued = min(n, limit)` and did nothing with it, and a real `cap` on the row would have been worse — the cap
truncates the *resolved* list, so once the first N were judged the rest would never be served.

## 4. Defaults taken

| Decision | Taken | Why |
|---|---|---|
| Queue name | `Discovery · <run_key>` | unique within a session; the label is not (seed re-runs) |
| Cap | none | §10.1 caps only training-window queues; a cap here would hide items forever once the first N were judged |
| Where the run ids live | `filters_json.run_ids`, `source_ref` NULL | `source_ref` would AND a single group onto the filter; a fan-out that reused runs spans more than one |
| Second send of the same run | `queues.find_open_queue(source_kind, filters)` → the same open queue, `reused: true` | two open queues over one run would show two progress counts for one set of verdicts; the match is on what the queue *is* (kind + filters, `run_ids` compared as a set) |
| The *Sent N* state on the Runs page | in-memory, keyed by run key, carries the queue id; the button opens the queue | the server dedupes, so losing it on a reload costs nothing |
| The footer button | the slideshow's hook; disabled with its reason rather than hidden | the reason is the thing a researcher needs to read when it is grey |
| Blind | no (the kind's default) | §10.1: Discovery and seed queues are not blind |

## 5. Found on the way, and left

- **A verdict given in Review does not move the scoreboard's *already judged* or *interesting* cell**
  (acceptance step 3 as written). Not a defect of this seam: *already judged* is defined as a verdict that
  existed **before the run started** (`scoreboard.py` module docstring, §7.3), and *interesting* counts
  detections matching an **annotation** in `ACCEPTED_VERDICTS` (`scoreboard.py:216–226`) — an `adjudications`
  row on the run's own detection is read by neither. Measured in the gate: the `mp_threshold` row read
  *3 · 0 · 0 · 0 · no detections in the reviewed overlap* before and after the verdict, and *Refresh after
  reviewing* re-read it (*"scores re-read from the tables"*). The runbook already assigns *"precision means
  what it says"* to **`X`** (`RESEARCH_RUNBOOK.md` Q2 step 6, Q5 step 2); it should take this with it: a
  precision that cannot see the verdicts Review writes on the run's own detections cannot answer Q5.
- **Pass to Review on the smoke's default chain is grey** — `mp_threshold` at `threshold 8.0` finds 0 spans on
  the smoke span (recording 4, samples 1002725–1003475; so does the 7.261 the drag step leaves it at), and
  0 spans is *no spans to review*. The smoke now asserts the grey button carries that reason, then sets the
  threshold to one that finds spans (measured through `POST /api/runs`: 6.0 → 2 spans, 5.0 → 5, 4.0 → 6;
  `SMOKE_PASS_THRESHOLD = 6.0`) and presses it (§7).
- **The threshold block page threw the first time a chain found exactly two spans of one duration.**
  `DurationHistogram` over two 9 s spans gave `kit/plots.tsx::binValues` the domain `[9, 9]`, a bin width of
  0, a bin index of `NaN`, and `bins[NaN].count++` — a red *block 03 process failed to render* card, two browser
  console errors and no draggable threshold line (the run's result is kept as
  `webui/screenshots/fixup/L/smoke-result-run2-histogram-crash.json`: 608 screenshots, 8 failures, the two
  console errors). Not this ticket's seam, but the smoke's new step stands on that page and the slideshow's
  *Send N to Review* lives there, so it is fixed in place: `widenDegenerate` gives a zero-width domain half a
  unit each side, for the bins and the x scale alike (commit `fixup-l: a histogram over equal values…`).
  Every `Histogram` caller in the kit inherits it.
- Left alone, as instructed: the seed picker and Explore's *Take span for Review* (`Y`); Library › Family's
  *Send N to Review as a queue* (its members have no `detections` row; rule 5); Discovery › Compare (`Z`);
  rediscoveries, classes and tags (the Review behaviour prompt).
- `webui/smoke.py`'s *discovery → review* walk reads the bridge's sandbox copy (`/api/runtime` → `db_path`,
  `mode=ro`) to see the `adjudications` row the verdict wrote and which run its detection belongs to; the
  smoke was already reading `/api/runtime` for the log path.

## 6. Files touched outside the prompt's named list

| File | Why |
|---|---|
| `webui/client/src/analyse/sendToReview.ts` (new) | the one hook behind the slideshow's and the footer's button ("one call, two buttons") |
| `webui/client/src/analyse/views/registry.tsx` | `useSendToReview` now calls that hook; four imports dropped |
| `Working/database/queries.py`, `Working/review/queue_state.py` | the prompt's "`run_ids`, additive to `queue_candidates`" needs the filter key accepted by `ReviewQueue` too |
| `Working/review/queues.py` | `find_open_queue` (+ `_normalised_filters`) for the same-run-twice rule |
| `tests/test_adjudications.py` | the `queue_candidates` test lives beside its siblings |
| `webui/smoke.py` | the walk (§7) and the footer check |
| `docs/RESEARCH_READINESS.md`, `docs/prompts/fixup/README.md` | item 1 closed in place; the Stage 5 row |

## 7. The gate

| Step | Result |
|---|---|
| `npx tsc -b`, `npm run build` in `webui/client` | clean; the bridge banner read `client_dist = …\webui\client\dist`, serving `index-Drfaffmh.js` (the build with the histogram fix) |
| `webui/smoke.py`, full, against a `--sandbox` bridge restarted immediately beforehand, alone on the machine (`PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1`) | **608 screenshots, 5 failures, 0 browser console/page errors, 0 unexpected server tracebacks** (the one `ERROR` line is the walk's own deliberate failed block, *window (m=30000 samples) must be shorter than the span*). The five are exactly the standing ones: `discovery.runs--default` and the four Settings registration states. Three full runs were needed: run 1 found the footer button correctly grey on a 0-span chain (my check was wrong, not the button); run 2 found the histogram crash of §5 (kept as `fixup/L/smoke-result-run2-histogram-crash.json`); run 3 is the gate |
| `pytest -n 4` under conda | **1956 passed, 17 skipped, 0 failed** (4 m 56 s). Baseline measured before the first edit: 1952 passed, 17 skipped, 0 failed — the four new core tests and no new failure |
| `webui/.venv` — `tests/test_webui_discovery.py`, `test_webui_review.py`, `test_webui_routes.py` | **85 passed, 1 failed** (4 m 05 s): the one is the standing `test_the_scoreboard_cells_are_the_tables_own_numbers`. Baseline before the first edit: 81 passed, the same 1 failed — five route tests added, one (the descriptor's) replaced |

**The walk, as the smoke drove it** (`webui/screenshots/fixup/L/`, numbers from `evidence.json`):

1. Discovery › Runs, `mp_threshold` selected → *Send 3 unjudged to Review* → toast *"3 unjudged in 'Discovery ·
   mp_threshold' · verdicts write adjudications"* (`discovery-4-send-to-review-toast.png`). One `review_queues`
   row named *Discovery · mp_threshold*, `discovery-run`, `filters {"run_ids": [84, 86]}`. Run group 3 holds runs
   84 / 86 (1 + 2 real detections) **and** their surrogates 85 / 87 (1 + 0): queue 4 serves 3 items, not 4.
2. *Open Review* → `#/review/queue/4/1208`: toolbar *queue Discovery · mp_threshold*, *writes adjudications*,
   **0 / 3** (`discovery-5-review-opens-that-queue.png`). `I` → `adjudications` row 1:
   detection 1208, run 84, `surrogate_of_run_id` NULL, verdict `interesting`; progress **1 / 3**
   (`discovery-6-review-verdict-written.png`; `adjudications.md`). `annotations` untouched.
3. Back in Runs: the acts read *Sent 3 · open in Review · then refresh* with `data-queue="4"`; *Refresh after
   reviewing* re-read the scoreboard — the row is unchanged, as §5 explains (`discovery-7-refresh-after-reviewing.png`).
4. The seed run `smoke_seed` → *Send N unjudged to Review* → queue 5 *Discovery · smoke_seed*, `seed-search`,
   `run_ids [88, 90]`, 110 items — group 4's surrogates 89 / 91 (68 + 68 detections) excluded
   (`discovery-8-seed-run-sent.png`). The Analyse chain footer, after a run at threshold 6.0: *last run · 2 spans*,
   *→ Pass 2 to Review* enabled → queue 3 *mp_threshold · run #80*, *writes adjudications*, **0 / 2**, the toast
   *"queue 'mp_threshold · run #80' created over the 2 detections of run #80"* (`chain-8-pass-to-review-queue.png`).
5. *Discard run* on a sent run → its queue serves nothing: `test_a_discarded_runs_queue_serves_nothing`
   (route-level; `runs.superseded_at` is honoured by `_superseded_run_ids`, unchanged).

## 8. In short

Discovery's *Send N unjudged to Review* now makes the queue Review opens, filtered by the run ids the run is
made of so the paired surrogates' detections never reach a verdict; *Open Review* opens it; the same run sent
twice is the same queue; the Analyse chain footer's *Pass N to Review* shares the slideshow's call; the
descriptor is gone. Found on the way: a Review verdict on the run's own detection moves no scoreboard cell
(`X`'s), and a histogram over equal values crashed the threshold block page (fixed). `RESEARCH_READINESS.md`
cross-cutting item 1 is closed in place; Q2, Q4 and the Review half of Q5 are unblocked at this seam.
