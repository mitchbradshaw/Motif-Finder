# Fixup AL — send one detection from Discovery's browser to Review, not only "send all"

**Written 2026-10-13 from the researcher's list ("option to send an individual detection in discovery to review, as
well as 'send all'"). Not run yet.**

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python `"/c/ProgramData/anaconda3/python.exe"`).
Read `CLAUDE.md`, `webui/client/src/discovery/RunsPage.tsx` (the *Browse detections* card and the *Run acts* card —
`send`, `sendDiscoveryRunToReview`), `webui/server/discovery.py` (`send_to_review`, `ReviewBody`),
`Working/review/queues.py` (`create_queue`, `_resolve_detections`) and `Working/review/queue_state.py`
(`ReviewQueue.__init__` — note `detection_ids`), `webui/client/src/review/queue.ts`.

Commit prefix `fixup-al:`. Test-first; the first commit touches only `tests/` and must fail. **`--sandbox` only.**

## In plain words

Discovery's *Browse detections* lets the researcher step through what a run found, one at a time. When one of them
looks worth a verdict, the only button sends *every* unjudged detection of the run to Review — hundreds — when the
researcher meant *this one*. The queue machinery can already hold a list of chosen detections; the route and the
button are missing.

## Facts to build on

- A Review queue is a `review_queues` row that is a *filter*, never a copy of detections. `ReviewQueue` accepts
  `detection_ids=` already (`queue_state.py:54`); nothing in the bridge passes it.
- `POST /api/discovery/runs/{run_key}/review` takes only a `name` and filters by the run's run ids.
- The Review path is the one the supervisor reads; it must stay the most reliable in the app. Add, do not rework.

## Decide this way (do not open it again)

- **One per-session picked queue, appended to**, named `<session> · picked from Discovery`, rather than a queue per
  click: ten clicks must not make ten queues in Review's list. Sending a detection that is already in it is a no-op
  that says so.
- The queue's filter is `{"detection_ids": [...]}`; adding to it rewrites `filters_json` through `queues.py` (add an
  `extend_queue` there if none exists — never an inline UPDATE in the route).

## Work

1. `ReviewBody.detection_ids: list[int] | None`. With it, the route creates-or-extends the picked queue and answers
   `{queue_id, queue, added, already, total}`; without it, today's behaviour.
2. The browser card gets *Send this one to Review* (`variant="primary"`; the run-wide send stays the page's green
   `next` button) with a toast carrying *Open Review*. The detection's id is already on the browser payload
   (`browser-detection`); if it is not, add it on the bridge, do not derive it in the browser.
3. A sent detection shows a small "in Review" mark in the browser when stepped back to.

## Acceptance

- [ ] Sending one detection creates the picked queue with exactly one item; sending a second extends it to two; sending
      the first again adds nothing and says *already in the queue*.
- [ ] Review lists the picked queue and opens it to those detections; a verdict there moves Discovery's scoreboard like
      any other (the existing "Refresh after review" path).
- [ ] The run-wide send is unchanged and its tests still pass.
- [ ] `pytest` (FastAPI tests under `webui/.venv`), `tsc -b`, `npm run build`, smoke (walk: browse → send one → open
      Review) pass.

## Report

`docs/prompts/fixup/reports/AL-send-one-detection-to-review.md`.
