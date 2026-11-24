# AS — Review momentum: the next candidate first, verdicts saved behind

**Read first.**
- `CLAUDE.md`. It binds you: the rules, "Talking to the researcher", the UI gate.
- These memory notes in `C:\Users\mmebr\.claude\projects\C--Users-mmebr-Documents-CNN\memory\`:
  - `review-carry-deferred.md`: today's two changes and their rules. This is the base you build on.
  - `webui-project-bridge-smoke-port.md`: the live bridge and the machine's memory pressure.
  - `webui-smoke-gate-traps.md`
  - `parallel-agents-shared-file-commits.md`
  - `bash-heredoc-patches.md`
  - `pure-ts-imports-under-node.md`
  - `cnn-python-interpreter.md`

Commit prefix `AS:`. The researcher can answer questions in this session, but they will be reviewing while you work. Batch your questions, and ask only what measuring cannot settle. When a choice is open and cheap to reverse, take the defensible one and record it under **Assumed** in your report.

## Why (the researcher, 2026-11-24)

They are working through queue 57 on the live bridge (port 8765), one key press per candidate. The queue is "Auto-detect · unreviewed drops and rises, 4 channels (24 Nov)", 5,291 events, built that morning. They sent two messages that day.

> "still too slow, im not sure if its the large queue size? ... still up to 500ms or so, noticeable load time between each candidate, load time after decision"

Commit 9ccd3031 (below) fixed that. Then:

> "great it is working faster for about 5 or 6 in a row, then it begins to lag again as verdicts catch up in the background. Is there any way to process verdicts faster? can you prioritise feeding the next candidate in faster over saving verdicts, so that momentum gain be gained, candidates can be done quickly and consistently, and the lag for verdicts to catch up can increase but still process slowly in the background?"

**The goal in one sentence.** At the researcher's pace, every next candidate appears at once, however many verdicts are still waiting to be saved. The saves catch up behind, in order, never lost and never doubled.

## Where things stand: build on this, do not redo it

Two changes went live on 2026-11-24. The memory note `review-carry-deferred.md` has the detail.

- **5e79d263: carries run in the background.**
  - A verdict is written and answered at once.
  - Copying it to the same event in other runs (the "carry") waits on its audit row, flagged `carry_pending` in the payload. One worker thread runs these carries in audit order: `CarryWorker` in `webui/server/review_carry.py`, on `app.state.carry`.
  - Undo, promote and unpromote call `carry.drain()` first.
  - The page polls `GET /queues/{qid}/carries/{audit_id}` (`whenCarried`, `api/review.ts:549`). It re-reads rows only when the carry reached its own queue.
  - Order is the correctness. `tests/test_review_carry_deferred.py` proves that deferred and at-once carries end identically.
- **9ccd3031: the page moves on at the key press.**
  - `Inspector.tsx:176-177` (`ahead`) advances before the write.
  - `store.ts:194 inOrder` sends writes one at a time, in gesture order.
  - Undo and redo wait for outstanding writes (`waitForWrites`, `store.ts:203`).
  - A refused write brings the page back to its item, which keeps its red card (matched by `itemId`).
  - Key press to next card fell from 145–554 ms to 17–23 ms, **when the next item is already in memory**.
- **The undo rule.** `POST …/undo` takes no id: `verdicts.undo_last` reverses the queue's latest audit row (`review.py:1195`). So the order of sends must equal the order of gestures. An undo must never be sent while an earlier verdict of the page is still unsent.

## What is known (measured 2026-11-24)

| What | Measured | Where |
|---|---|---|
| Key press → next card, next item already read | 17–23 ms (sandbox) | paints from `peekItem` (`api/review.ts:450`) |
| Item read `GET /api/review/queues/{qid}/items/{id}` | 0.15–0.23 s on the live bridge | `webui/server/review.py:1029 get_item` |
| Verdict `POST …/verdict` | 60–170 ms | `review.py:1134`; its answer already carries the queue counts (`_write_ack`, `:1152`) |
| Counts `GET …/counts` | 0.09 s | `review.py:993`; also computes `queue_pace_s` and `served_detections` |
| Thumbnails `GET …/thumbs?ids=<one>` | 100–150 ms | `review.py:967` |
| Queue list `GET /api/review/queues` | 2–3 s on the live bridge | `review.py:768 get_queues` |
| Queue rows `GET …/queues/{qid}` | 0.85–2.5 s on the live bridge | `review.py:823` |
| A verdict and its carry, quiet database copy | 0.01 s | slow on the live machine only because of RAM pressure |
| Requests per verdict (fetch log, rail collapsed) | POST verdict; GET counts; GET thumbs (one id); GET the next item ahead; GET carries polls | |

**The machine.** It has 13.7 GB of RAM, often with under 1.5 GB free: the researcher's Opera uses about 7.8 GB and Chrome about 3.9 GB. On the live bridge, database reads and writes therefore go to disk, so everything is slower than on a quiet sandbox. Do not close the researcher's apps. The fix must hold on this machine as it is.

## The likely mechanism: a hypothesis, so confirm it first

1. **The window is five deep and refills at most one item per step.**
   - `prefetch.ts:8` sets `PREFETCH_AHEAD = 5`.
   - `cursor.ts:41-52 land()` reads the window only after the landing has settled for `STEP_SETTLE_MS = 150` (`:16`) and the item's own read is in. It then reads one item at a time, nearest first (`:45-51`), and the next landing aborts the loop.
   - When a read takes longer than the gap between key presses, the window loses up to one item per verdict. After five or so fast verdicts it is empty: the researcher's "5 or 6 in a row".
   - From then on every step pays the 150 ms settle (an item not yet held is read only after it, `cursor.ts:43`) plus a cold read. That is the 0.3–0.5 s they feel.
2. **Reads slow down during a burst, because each verdict sets off other traffic.** All of it shares one bridge process (one GIL, one SQLite writer) and, in the browser, six connections per host.
   - `commitWrite` calls `bumpCountsVersion()` (`store.ts:228`), which triggers the toolbar's `GET …/counts` (`Shell.tsx:99`). The POST's answer already carries those counts.
   - With the left rail open on the queue list (`?rail=queue`, `Shell.tsx:358`), `QueueList` re-reads `GET /api/review/queues` (2–3 s on the live bridge) on every counts bump (`Shell.tsx:193`).
     - Superseded reads are not aborted: `useSourced` ignores its signal (`api/seam.ts:35`), and a sync route runs to the end anyway.
     - The toolbar's picker copy mounts only while it is open (`Popover` returns null when closed).
     - Find out which rail the researcher uses.
   - The collapsed rail's strip asks `GET …/thumbs?ids=<one>` for each unit that scrolls in (`Shell.tsx:267`).
   - `whenCarried` (`api/review.ts:549`) starts one poller **per verdict**. Each polls at +0.4, 1.2, 2.7, 5.7, 10.7, 20.7 and 40.7 s until its carry is done.
   - The carry worker (`review_carry.py:95-106 _loop`) runs carries back to back, with no regard for page reads. `corpus.REQUEST_CLOCK` and `corpus.wait_for_quiet` (`corpus.py:436-452`, kept up to date by the middleware in `app.py:88-101`) exist for exactly this case. The start-up warm uses them; the carry worker does not.
3. **A carry into the queue on screen is a cliff.**
   - `invalidateAfterCarry` (`api/review.ts:705`) calls `bumpReviewVersion` (`store.ts:167`). That empties the whole item cache and re-reads every row (0.85–2.5 s live), so the window is gone.
   - On queue 57, none of 54 measured carries landed in its own rows, so this is rare there.
   - A queue holding two runs of one channel would hit it on every verdict.

**Confirm before building.** Drive a burst that empties the window (see **How to measure**). For each request, log:
- the `fetch` start and end;
- the time spent queued in the browser (Resource Timing: `requestStart − fetchStart`);
- the bridge's own time.

Whichever of these dominates decides which fixes matter most. The requirements below stand whatever the answer.

## What to build, in the researcher's order

**R1. The next candidate never waits on a save.** At the researcher's pace, for a burst of any length, the next card paints from memory.
- **Deepen the window.** About 15–20 unjudged items ahead, say.
  - Raise `ITEM_LRU_MAX` (`api/review.ts:434`) with it; `tests/test_night_review.py` pins LRU ≥ ahead + 5.
  - Measure one item's size in memory at the card's `px`, and keep the total sensible.
- **Refill as fast as reads allow**, not one item per step. Options:
  - no settle for a landing that came from a verdict's advance (the settle exists for arrow-key scrubbing, night-a);
  - a refill that survives the next landing instead of restarting from the nearest item;
  - two reads in flight;
  - a batched read, `GET …/items?ids=a,b,c`: one request, one connection, one queue resolve.

  Choose by measurement.

**R2. Reads before writes, in the page and in the bridge.**
- **Page.** One scheduler for all of Review's traffic.
  - Order: the item on screen first, then the window nearest first, then everything else (verdict saves, counts, thumbnails, carry polls).
  - A save waits while an item read is waiting, up to a cap of a few seconds. Saves are the researcher's work and must not starve.
- **Bridge.** The carry worker yields to page requests.
  - Use `wait_for_quiet` with a short `quiet_s` and a `max_wait_s` cap. Carries then keep up at a normal pace and still run during a long burst.
  - `drain()` keeps running everything queued before an undo or a promotion.

**R3. Saving may lag, visibly, and goes faster in bulk.**
- **Show the backlog.** The researcher accepts that "the lag for verdicts to catch up can increase". Show it calmly with a small toolbar indicator: "4 saving…", then "all saved" (`data-testid="saves-pending"`). Never put a spinner over the card, and never block the next key press.
- **Save in bulk.** When several verdicts are queued, save them in one request.
  - **The route:** a new `POST /api/review/queues/{qid}/verdicts` that takes an ordered list.
  - **The core:** writes them in that order in one transaction, one audit row each, so undo still reverses one gesture at a time. Each carry is queued (`carry=False`, then `submit`).
  - **The answer:** one ack per verdict, plus the counts after the last.
  - Do **not** reuse `verdicts.write_batch` for this. It writes the SAME verdict to N items under ONE audit row (`Working/review/verdicts.py:724`). The likely shape is a loop over `write_verdict` (`:641`) inside one transaction.
  - A refused verdict in the list is refused alone; the ones after it are still written, in order. That is what separate POSTs do today.

**R4. Undo and redo stay exact.**
- Ctrl Z on a verdict not yet sent: take it out of the queue, send nothing, and return to its item.
- Ctrl Z on a verdict in flight, alone or inside a bulk save: wait for that save's answer, then send the undo.
- Ctrl Z on a saved verdict: as today. `commitUndo` sends `POST …/undo`, which drains the carries first.
- Redo is symmetric.
- Audit order must stay equal to gesture order (see the undo rule above). `tests/test_night_a_review.py` and `tests/test_review_carry_deferred.py` pin it.
- With a long carry backlog, `drain()` runs every queued carry before the undo. Measure an undo after a 50-verdict burst on the sandbox. If it takes more than about a second, say so on the page ("undoing — saving 12 earlier verdicts first"). Never hang silently.

**R5. Nothing lost, nothing doubled.** A verdict that lives only in the page can now be dozens deep.
- **Closing the page.** While any verdict is unsaved, `beforeunload` warns.
- **Surviving a crash.**
  - Journal each waiting verdict in `localStorage` as its key is handled (tiny and synchronous), and delete the entry on the ack.
  - On the next load of Review, replay the journal in order **before** accepting new verdicts ("saving 12 verdicts from your last visit…").
  - A replay the bridge refuses is shown loudly, never dropped.
- **Saving exactly once.**
  - Each verdict carries a client id (`crypto.randomUUID()`), sent with it and stored with its audit row. The audit payload JSON already holds flags such as `carry_pending`, so no schema change is needed.
  - A write whose id is already among the queue's audit rows is answered with the original ack, not written again.
  - Two tabs, or a replay racing a slow POST, then cannot double a verdict.
- **Keys.** The sandbox and 8765 are different origins, so their journals never mix. Key the journal by queue id.

If you find a simpler scheme that meets "never lost silently, never doubled", take it and say why.

**R6. Refusals stay loud.** A refused save still brings the page back to its item, with its red card (9ccd3031's rule). The saves after it keep their order and still go. If jumping back many items with a deep backlog feels wrong in your testing, ask the researcher before changing the rule.

**R7. Fewer requests per verdict.** Each one competes with the next candidate's read.
- **Counts:** take them from the save's answer. Re-read the full counts (pace, detections) at most every few seconds, and once when the backlog empties.
- **The queue list, when the rail is open:** re-read it on that same slow beat, not per verdict, and abort superseded reads (`useAbortableSourced`, `api/seam.ts`).
- **Thumbnails:** fetch the strip's thumbnails for the whole window in one request when the window is chosen, not one id per step.
- **Carry polls:** one poller for every waiting carry, with one request answering several audit ids. Not one poller per verdict.
- **A carry into the queue on screen:** patch the rows it judged and drop only their cached details, instead of calling `bumpReviewVersion`. Do this only if measurement shows it matters for real queues.

## Acceptance

Measure before any code change, then after, on the same machine, with a fresh sandbox each time.

| # | Scenario | Must show |
|---|---|---|
| 1 | Burst: 50 verdicts, 300 ms apart, on queue 57 with auto-advance on. Run it once with the queue rail collapsed and once with it open. | Key press → next card **painted**: p95 ≤ 50 ms, no step over 150 ms. Today: about 5 fast steps, then 0.3–0.5 s each. |
| 2 | Steady: 150 verdicts, 600 ms apart | The same bounds as 1. |
| 3 | Catch-up after 1 | "all saved" shows and no `carry_pending` audit row is left. Report the seconds; the target is ≤ 30 s on the sandbox. |
| 4 | Exactness after 1 and 2 | The copy's `review_audit` rows are exactly the scripted verdicts, in order, once each. The deferred-carry equivalence test passes unchanged. |
| 5 | Undo | Ctrl Z after a burst undoes the last verdict and returns to it. Ctrl Z on a verdict not yet sent sends nothing (check the fetch log) and returns to it. |
| 6 | Refusal | Wrap `fetch` so that verdict 20 of 50 gets a 409. Item 20 shows its red card, and verdicts 21–50 are saved in order. |
| 7 | Loss | Hold the saves (block the POST in the `fetch` wrapper), judge 10 items, and reload. The warning shows; after the reload, each of the 10 is saved exactly once (count the audit rows). |

"Painted" means the new item's traces are drawn, not merely that `data-item` changed. Find the marker in the DOM, and prove it works: a cold step must measure slower than a warm one.

## How to measure

- **Private client build.** Never run `npm run build` before going live: it rebuilds `webui/client/dist`, which 8765 serves to the researcher at once. In `webui/client`, run instead:
  - `npx tsc -b`
  - `npx vite build --outDir <your scratchpad>/dist_as --emptyOutDir`
- **Sandbox bridge.** Use your own port, never 8765 (8830, say). From the repo root:
  `webui/.venv/Scripts/python.exe webui/run_server.py --sandbox --port 8830 --no-warmup --dist <that dir>`
  - It copies the real database (≈ 0.8 GB) into `webui/runtime/<stamp>/`, and every write lands there.
  - `.claude/launch.json` holds similar entries (`archive-sandbox`). Add your own if you use `preview_start` in the Browser pane.
  - Restart it after any Python edit; it does not reload.
  - Run one sandbox at a time, because RAM is tight.
  - When you are done with a copy, check that `Get-ChildItem -Recurse -Attributes ReparsePoint <dir>` is empty, then delete the copy.
- **Driver.** Use Playwright through the conda python (`"/c/ProgramData/anaconda3/python.exe"`, with `PYTHONIOENCODING=utf-8`). Headless Chromium is not throttled the way a hidden tab is; a hidden Browser pane clamps its timers, which wrecks a 300 ms cadence. Write a burst script (worth committing as `scripts/review_burst.py`, as dev tooling) that does this:
  1. Read `GET /api/runtime`, and refuse to run unless the bridge is a sandbox. The script writes verdicts.
  2. Open `http://127.0.0.1:<port>/#/review/queue/57`. Routes are hash routes (`state.tsx:27`).
  3. Wrap `window.fetch` to log each request's URL, start and end, and read the Resource Timing entries.
  4. Press `n` (not interesting; the key map is at `review/keys.ts:36`) N times at the cadence, timing each key press to the painted card.
  5. Print p50, p95 and max, the requests per verdict by route, and the save backlog over time.
  6. Wait for "all saved", then count audit rows in the copy (`webui/runtime/<stamp>/annotations.sqlite`), read-only.
- **A closer look.**
  - In the page: use a Chrome trace (chrome-devtools MCP, `performance_start_trace` and `performance_stop_trace`). Its page ids change when the app restarts, so list the pages first.
  - In the bridge: add a temporary per-request timing log, and remove it before you commit.

## Files

- **Client** (`webui/client/src/`):
  - `review/Inspector.tsx`:
    - the landing, `:64-82`;
    - the `moveTo` effect, `:107`;
    - `write()`, `:147-212`, with `ahead` at `:176-177` and the carry follow-up at `:187-204`.
  - `review/store.ts`: the versions `:167-182`, `inOrder` `:194`, `commitWrite` `:219`, `commitUndo` and `commitRedo` `:236-262`.
  - `review/cursor.ts`, `review/prefetch.ts`: both are pure, with no imports, and the tests run them under Node.
  - `api/review.ts`:
    - `getQueueCounts` `:343`, `useThumbs` `:390`;
    - the item cache `:427-475`;
    - `WriteAck` `:532-539`, `whenCarried` `:549`;
    - `itemHeld` and `prefetchItemThen` `:673-680`;
    - `invalidateAfterCarry` `:705`.
  - `review/Shell.tsx`: the toolbar counts `:98-99`, `QueueList` `:186-193`, the rails `:69` and `:358`, `QueueRailCollapsed` `:252-267`.
  - `review/keys.ts`, `api/seam.ts`.
- **Bridge** (`webui/server/`):
  - `review.py`:
    - reads: `get_queues` `:768`, `get_queue_counts` `:993`, `get_item` `:1029`;
    - the verdict write: `post_verdict` `:1134`, `_write_ack` `:1152`, `get_carry` `:1165`;
    - other writes: the batch route `:1180`, and undo, promote and unpromote with `drain()` `:1195-1250`.
  - `review_carry.py` (126 lines).
  - `corpus.py:436-452`.
  - `app.py:88-101`.
- **Core:**
  - `Working/review/verdicts.py`: `write_verdict` `:641`, `write_batch` `:724`, `pending_carries` `:809`, `carry_status` `:819`, `run_pending_carry` `:828`.
  - `Working/review/overlap.py` (`carry`).

## Tests and the gate

- **Test-first.** Your first commit touches only `tests/` and fails on HEAD. Likely candidates:
  - a Node-run test of new pure scheduling or window logic. Keep that logic in a pure `.ts` with no imports, like `cursor.ts`; `tests/test_tq_review.py` shows how.
  - a bridge test of the ordered bulk route and of the client id's exactly-once rule, following `tests/test_webui_review_carry.py`. Call `client.app.state.carry.flush()` before checking carried rows.
  - a core test, if `verdicts.py` changes.
- **Tests that pin today's rules.** Update these on purpose, and name each one in the commit message:
  - `test_night_review.py`: window size, the LRU rule, advancing before the answer.
  - `test_night_a_review.py`: write order; undo and redo waiting.
  - `test_tq_review.py`: `STEP_SETTLE_MS`, `ADVANCE_MS = 60`, the landing.
  
  `test_review_carry_deferred.py` must pass **unchanged**.
- **Run with the conda python:**
  `"/c/ProgramData/anaconda3/python.exe" -m pytest tests/test_tq_review.py tests/test_night_review.py tests/test_night_a_review.py tests/test_review_verdicts.py tests/test_review_carry_core.py tests/test_review_carry_deferred.py tests/test_review_queue.py tests/test_import_boundaries.py`
- **Run with the bridge's venv:**
  `webui/.venv/Scripts/python.exe -m pytest tests/test_webui_review.py tests/test_webui_review_carry.py tests/test_webui_review_archive.py tests/test_webui_ar_speed.py`
- **A pre-existing failure that is not yours:** `tests/test_review_family_queue.py::test_an_extent_edit_moves_the_drawn_span_and_keeps_the_verdict` also fails on HEAD.
- **No full pytest run on this machine.** A change to `Working/database/schema.py` would need one, so if you find you need one, stop and say so first. R5 is designed to avoid it.
- **The UI gate** (CLAUDE.md), run on your sandbox with your private build:
  - Command: `PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" webui/smoke.py --url http://127.0.0.1:<port> --pages-only --only <unit>`.
  - Units: `review`, `zzzzzzzzzzz_night_review`, `zzzzzzzzzzz_review_carry`, `zzzzzzzzzzz_w2_archive`, `zzzzzzzzzzz_explore_review`. `--only` is a prefix match.
  - Compare by failure SET with `docs/prompts/fixup/reports/smoke-baseline-2026-10-21.txt`.
  - If a smoke state pins the old timing, change it in the same commit as the behaviour, and name it in the message.

## Working rules on this machine

- **Where to work.** In the main checkout, `C:\Users\mmebr\Documents\CNN`, on `main`. The sandbox needs the real database to copy; a worktree has only the fixture.
- **Other people's edits.** The tree holds uncommitted work that is not yours: thesis docs and `scripts/thesis/*`, `webui/client/src/analyse/captions.ts`, `Adapters/detection_signal_threshold.py`, two `tests/test_*signal_threshold.py`, and more. Never stage it.
  - Commit with explicit paths: `git commit -F <msgfile> -- <paths>`.
  - Never run `git add -A`, `git commit -a`, `git stash` (the index and the stash are shared), `git clean`, or `git checkout --` on a file you did not change.
- **Commit messages.**
  - Write the message file with the Write tool; heredocs with TS/JSX bodies break in the Bash tool.
  - Start it with `AS:`. Say what changed and the measured before and after.
  - End it with the Co-Authored-By line your session gives you.
  - Do not push.
- **Port 8765 is the researcher's live bridge, on the REAL database, and they are reviewing on it.**
  - Never send it a write, and never load it with tests.
  - Never restart it or rebuild `webui/client/dist` without the researcher's yes (see Going live).
- **The researcher.**
  - Questions follow "Talking to the researcher" in CLAUDE.md: a plain-language explanation first, with an everyday analogy where it helps; then the options; then your recommendation.
  - Never add a sixth verdict word, and never change what a verdict means.

## Going live (only on the researcher's yes)

1. Tell the researcher the before and after in plain words. Ask them to pause and wait for "all saved" before you switch over.
2. Run `npm run build` in `webui/client`. The live page picks it up on reload.
3. If bridge code changed, restart 8765:
   - stop the process listening on 8765;
   - from the repo root, start `.\webui\.venv\Scripts\python.exe .\webui\run_server.py --port 8765 --project --no-warmup` in a Terminal panel tab. The researcher's bridge runs in a tab titled "MycoWave bridge 8765".
   
   The carry worker re-queues pending carries when it starts.
4. Check that 8765 answers and that Review opens queue 57. Then ask the researcher to reload.

## Report

Write it in `docs/prompts/fixup/reports/AS-review-momentum-report.md`, in this order:
- a plain-language paragraph for the researcher: what was slow, what changed, and what it feels like now;
- a before/after table for scenarios 1–7, plus the requests per verdict and the undo time with a backlog;
- **Assumed**;
- what is left.

Then:
- Update the memory note `review-carry-deferred.md` with the new rules (the window, priority, bulk saves, the journal, exactly-once) and the tests that pin them. Keep its line in `MEMORY.md` accurate.
- Commit this prompt file in your docs commit.

No `docs/rq_roundA` change is expected: speed answers no research question.

## Out of scope

- The item read's own cost (0.15–0.23 s), unless it is still the bottleneck once R1 and R2 are in.
- What gets carried, queue building, archiving, the verdict vocabulary, and other pages.
- The researcher's apps and the machine's settings.
