# Fixup L — *Send N unjudged to Review* makes a queue that opens

**Ready to run, and it runs first.** Small, one seam, no research decision. It unblocks Q2, Q4 and half
of Q5 (`docs/RESEARCH_READINESS.md`, "Three things that bear on more than one question", item 1).

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md`, `docs/RESEARCH_READINESS.md` §Q2 and §Q4,
`docs/prompts/wiring/requests/04-to-05.md`, `docs/prompts/wiring/reports/05-review.md` §1, and
`prototyping/UI_FUNCTIONAL_SPEC.md` §7.4 and §10.1.

Commit prefix `fixup-l:`. Test-first; first commit touches only `tests/` and must fail.
**`--sandbox` only. `--project` is the researcher's.**

## The defect

Two wiring prompts each built half of a hand-off and nobody joined them.

- Prompt 04 (Discovery) made *Send N unjudged to Review* record a **descriptor** in
  `discovery_sessions.state_json` (`webui/server/discovery.py:1760–1806`) and offered to add a table.
- Prompt 05 (Review) **took the table** — `review_queues`, resolved live by
  `Working/review/queues.py::_resolve_detections` (:382) — and lists only its rows.
- Nobody went back. Discovery still writes the descriptor and no row.

Measured 2026-10-02 on a sandbox bridge: the toast read *"5 of 5 unjudged in 'Discovery · seed a9147c
unjudged' · verdicts write adjudications"*; `GET /api/review/queues` still listed two queues; the toast's
*Open Review* is `navigate('review')` (`webui/client/src/discovery/RunsPage.tsx:401`) and landed on
`#/review/queue/1/119` — *"Library - extract events"*, a different queue of a different unit.

The one gesture that works is the Analyse block page's slideshow: `sendRunToReview`
(`webui/client/src/api.ts:133`, called from `analyse/views/registry.tsx:138`) posts
`{source_kind: 'discovery-run', filters: {run_id}}` to `POST /api/review/queues` and navigates to the
queue it gets back. **That is the shape to converge on.**

## What to build

1. **`send_to_review` creates a `review_queues` row** through `Working.review.queues.create_queue` and
   returns its id. `source_kind` is `discovery-run` for a template run and `seed-search` for a seed run
   (both exist in the table's `CHECK`). Sending the same run twice returns the same open queue rather
   than a second one.
2. **The queue covers exactly the runs the Discovery run is made of** — `_run_ids(conn, row)`
   (`discovery.py:329`), which already excludes surrogates. See the trap below.
3. ***Open Review* opens that queue**: `navigate('review/queue/<id>')`. The Runs page's *Sent N · refresh
   after reviewing* state links to it too.
4. **The Analyse chain footer's *Pass N to Review*** (`analyse/ChainPage.tsx:449`, disabled, *"out of
   slice scope"*) does what the slideshow's button on the same run already does. One call, two buttons.
5. **Retire the descriptor.** `GET /api/discovery/queues` either reads the table or goes; do not leave
   two records of one queue. `getDiscoveryQueues` (`api.ts:576`) has no caller.

## The trap — a run group holds the surrogates too

`ReviewQueue` and `queries.queue_candidates` (`Working/database/queries.py:448`) filter on **one**
`run_id` or on a `run_group_id`. A paired surrogate run joins the **same run group** as the run it
shadows and writes `detections` rows of its own. Measured in the sandbox copy
`webui/runtime/20261002-180621/annotations.sqlite`: run group 7 holds real runs 101 / 105 / 109 with
3 + 61 + 10 = **74** detections and surrogate runs 103 / 107 / 111 with 79 + 82 + 88 = **249**.

A queue built on `run_group_id` alone would put 249 detections of phase-randomised noise in front of the
researcher and write human verdicts against them. **So the filter must carry the run ids**
(`run_ids: [...]`, additive to `queue_candidates`), and a test must assert that a queue over a run with
a paired surrogate contains none of the surrogate's detections. `fixup-T` owns the wider question of
surrogate detections in other readers; you own this one filter.

## Leave alone

| Leave alone | Why |
|---|---|
| The seed picker, Explore's *Take span for Review*, the seed page's own defects | `Y-seed-sources.md` |
| Library › Family *Send N to Review as a queue* (`library/chrome.tsx:89`) | A Library member from an event store has no `detections` row; which table its verdict writes is undecided (rule 5). Not this prompt |
| Discovery › Compare | `Z-band-scope-and-compare-by-verdict.md` |
| Rediscoveries (`07-review.md` R7), classes and tags (R3) | the Review *behaviour* prompt, still waiting on Q-R2 / Q-R7 |

## Acceptance — the researcher's walk, in a browser

1. Discovery › Runs, a finished template run selected → *Send N unjudged to Review* → the toast names the
   queue → *Open Review* lands on **that** queue: its name, *writes adjudications*, `0 / N`.
2. `I` on the first item → `adjudications` gains one row for a detection of a **real** run;
   `annotations` is unchanged.
3. Back in Discovery › Runs → *Refresh after reviewing* → the run's *already judged* and *interesting*
   cells moved.
4. The same from a seed run, and from the Analyse chain footer.
5. *Discard run* on a sent run → its queue stops serving items (`runs.superseded_at`, already honoured by
   `_superseded_run_ids`).

## The gate

1. `npx tsc -b` and `npm run build` in `webui/client`. If another prompt is running in this checkout,
   build to your own `--outDir`, serve it with `run_server.py --dist` on your own port, and check the
   `CLIENT = …` banner before trusting a screenshot.
2. `webui/smoke.py` against a `--sandbox` bridge restarted immediately beforehand, alone on the machine
   (never beside `pytest -n auto`). Add states for steps 1–2 above. **Finish on the full walk** — a
   partial walk is not the gate.
3. `pytest -n 4`; the baseline after `H` is **1952 passed / 17 skipped / 0 failed**. Re-measure before you
   start and compare failure **sets**.

Standing failures that are not yours: the four Settings registration smoke states,
`discovery.runs--default`, the cold-bridge flake `analyse.interrogation--fixup-d-sequence-rose`, and under
`webui/.venv` `test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers`.

**Evidence** into `webui/screenshots/fixup/L/`: the toast, the queue it opened, the `adjudications` row.

## Report

`docs/prompts/fixup/reports/L-send-to-review-opens-a-queue.md`: what each of the three gestures did
before and does now; the surrogate test and what it counted; what happened to the descriptor; defaults
taken; items left; out-of-scope files touched; the gate; a short chat summary. Then mark
`RESEARCH_READINESS.md` cross-cutting item 1 closed, in place.
