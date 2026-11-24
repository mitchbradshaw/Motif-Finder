# AS — Review momentum: report (2026-11-24)

Commits: `e8055fd0` (failing tests first) and `1c660d94` (the change). Not pushed. **Not live yet:** `webui/client/dist`
has not been rebuilt and the bridge on 8765 has not been restarted. Both wait for the researcher's yes.

## For the researcher, in plain words

**What was slow.** Picture a shop counter with one assistant. Each time you gave a verdict, the page put five errands
on the counter at once: save this verdict; recount the queue; fetch one little thumbnail; ask whether the copy to the
other runs is done yet; fetch the next candidate. At your pace (a verdict every third of a second) the assistant had
more errands than time. The queue at the counter grew, and *every* errand got slower, including "fetch the next
candidate". The page kept five candidates ready in advance, which is why the first five or six felt instant. Then that
stock ran out and every step waited on the counter, 0.4 to 4 seconds each.

**What changed.**
- The page now keeps **sixteen** candidates ready and restocks them **in one trip** when four are gone, instead of one
  trip per step.
- Verdicts wait in a short line and are **saved behind you**, always in the order you gave them, and they step aside
  while a candidate is being fetched.
- The recount, the thumbnails and the "is the copy done?" checks now happen a few times a minute, not once per verdict.
- The copying of a verdict to other runs waits for a quiet moment on the bridge (never longer than a second).

**What it feels like now.** On a copy of your database, 50 verdicts a third of a second apart: every next candidate was
drawn in 30–42 ms, the slowest 42 ms. 150 verdicts at a slower pace: the slowest was 50 ms. Every verdict was saved
exactly once, in order. The saves finished within 0.2 s of the last key press. You will see a small "4 saving…" in
the toolbar while verdicts are waiting, then "all saved".

- **Ctrl Z** still undoes exactly the last verdict and takes you back to it. If that verdict had not been sent yet, it
  is simply taken back and nothing is sent. Going back now takes 0.1–0.2 s, down from about 2 s.
- **A refused verdict** still takes you back to its candidate with its red card, even if you are several candidates
  further on. The verdicts after it are still saved.
- **Closing or reloading the page** while verdicts are waiting asks you first. If the page crashes anyway, the waiting
  verdicts are kept in the browser and saved the next time you open Review, never twice.

## Before and after

**Machine load.** From 18:00 on 24 Nov the drop auto-detect batch ran across all datasets. It used one or two Python
workers at up to about 1.8 GB each, until about 23:00, and free RAM was often under 1 GB.
- The "before" runs were taken 17:42–17:58, on sandbox `20261124-174240`, **without** the batch.
- Every "after" run was taken from 18:04 on (sandboxes `-180423` and `-182902`), **with** the batch running.

So the two sides were not measured under the same load, and the difference runs against the change: "after" had the
heavier machine. The improvement is not an artefact of a quieter box.

Scenario numbers are from a sandbox copy of the real database, queue 57, Playwright headless Chromium. "Step" means
key press to the next card's context trace drawn: the Inspector's `data-item` changed **and** its
`[data-testid="context-trace"] svg path` has a drawn `d`, checked once per animation frame. The marker is proven by
the before-run itself: its warm steps measured 19–40 ms and its cold steps 0.4–4.3 s.

| # | Scenario | Before (HEAD 9ccd3031) | After (1c660d94) | Bound |
|---|---|---|---|---|
| 1a | 50 verdicts × 300 ms, rail collapsed | p50 858, p95 1926, max 4277 ms; 43/50 over 150 | p50 31, p95 40, **max 42 ms**; 0 over 150 | p95 ≤ 50, none > 150 ✔ |
| 1b | the same, rail opened (`?rail=queue`) | p50 1076, p95 2612, max 2980 ms; 46/50 over 150 | p50 33, p95 45 ms; steps 3–50 max 45 ms; **steps 1–2: 1157, 243 ms** | ✘ for the first two steps; see below |
| 2 | 150 verdicts × 600 ms | (not run before; scenario 1 already failed) | p50 32, p95 42, **max 50 ms**; 0 over 150 | ✔ |
| 3 | catch-up after 1 | all answered 0.4–0.7 s after the burst (one POST per verdict) | "all saved" 0.0–0.2 s after the last key; carries done 0.3–0.4 s; no `carry_pending` row left | ≤ 30 s ✔ |
| 4 | exactness after 1 and 2 | 50/50 in order | 50/50 and 150/150: audit rows = the scripted verdicts, in order, once each; `test_review_carry_deferred.py` passes unchanged | ✔ |
| 5 | undo | (as today) | Ctrl Z straight after a 50-burst: back on the last item in 206 ms, its audit row undone. Ctrl Z on a verdict not yet sent: **0 POSTs for it**, back on it | ✔ |
| 6 | refusal (verdict 20 answered 409, 2 s late) | (n/a) | the page went back 8 items to item 20 (its red card); the other 49 verdicts saved in order; every step ≤ 46 ms | ✔ |
| 7 | loss (saves held, 10 verdicts, reload) | (n/a) | the `beforeunload` warning showed; after the reload each of the 10 was saved **exactly once** | ✔ |

**Scenario 1b and the open rail.** The open queue rail lives in the address (`?rail=queue`). The auto-advance navigates
to the next item's address without it, so **the rail closes on the first verdict**. That was already the case before
this change, and the before-run shows it too. The card then gets wider, so the candidates read at the narrow width are
the wrong size, and steps 1–2 are cold reads. From step 3 on, the rail is closed and every step is fast. Whether the
rail *should* stay open while judging is a question for the researcher (see What is left). In practice nobody reviews
with the rail open past the first verdict today.

**Requests per verdict** (during the 50 × 300 ms burst):

| Request | Before | After |
|---|---|---|
| save | 1.0 `POST …/verdict` | 1.0 `POST …/verdicts` (one verdict each at this pace; they batch when a read holds them back) |
| counts | 0.98 | 0.06 (a 5 s beat, and once when the backlog empties) |
| thumbnails | 0.98 (one id each) | 0.04 (the strip's next 30 units in one read) |
| carry polls | 0.96 (a poller per verdict, up to 7 reads each) | 0.24 (one poller, one request for all) |
| item reads | 0.9 single | 0.24 batched (≈ 4–6 items each) + ≈ 0.02 single |

**Where the time went before (confirmed, then corrected).** The brief's hypothesis was right about the window: it was
five deep and refilled one read per step after a 150 ms settle, so it emptied after five or six fast verdicts. What
the brief did not know is which part dominated.
- **Browser queueing was negligible:** Resource Timing `requestStart − fetchStart` had a p50 of about 0.5 ms.
- **The bridge's own time dominated.** An item read takes 0.11 s alone and took 1.0 s during the burst; the verdict
  POST 0.06 s alone, 0.6 s during the burst.
- **Why:** each verdict brought about 0.35 s of bridge work (item 0.11, thumbnails 0.09–0.19, counts 0.06, verdict
  0.06, carry and polls), against a 0.3 s gap.
- **And the biggest share of every item read was something else.** Profiled in-process, 80% of each item or
  thumbnail read is the queue's verdict overlay (`queues._judged_overlay`, about 0.08 s at 5,287 items). A batched read
  pays it once.
- **A second cause showed only after the fix.** The item cache evicted the **far end of the window**: it was fetched
  early and never landed on, while items already passed were kept because landing on them refreshed them. That left 13
  of 50 steps cold until `touchItems` kept the window as the cache's most recent entries.

**Undo after a burst.** The undo POST itself takes 0.09–0.12 s. The 2.0 s it used to take was the page emptying its
whole item cache and re-reading every row (1.2–1.8 s) before drawing the item again. For a plain verdict, the cached
card was read before the verdict was given, so it already shows what the undo restores. Undo and redo of such a verdict
now re-read the rows but keep the cache: 0.1–0.2 s. With saves still waiting, the toolbar says
"undoing — saving N earlier verdicts first" while the undo waits for them.

## Assumed

- **The bulk route writes each verdict in its own short transaction.** `write_verdict` commits per verdict, rather than
  the whole list in one transaction. A refused verdict then cannot roll back the ones before it, which is what separate
  POSTs did. At this pace each request carries one verdict anyway.
- **The client id lives in the audit payload** (`payload_json.client_id`) and is found with `json_extract` on the
  queue's audit rows (index `idx_review_audit_queue`). There is no schema change, so no full pytest run was needed. A
  bridge-wide lock makes the check and the write that follows one step. A verdict replayed after it was undone is
  **not** written again (its id is already in the audit).
- **When a whole save request fails without a 4xx** (the bridge did not answer, or a 5xx), the verdicts stay in the
  journal and are sent again by the next Review page. The client id makes that safe. The red card says so ("kept in
  this browser; sent again when Review is next opened"). A 4xx refuses them, as separate POSTs would have been refused.
- **Which tab may replay a verdict:** only one whose page is gone. Each page stamps itself alive every 2 s and removes
  its stamp on `pagehide`. A crashed page counts as gone once its stamp is 8 s old. An open Review page re-checks the
  journal every 5 s. A second open tab's waiting verdicts are therefore never replayed by the first.
- **A verdict key on a card not drawn yet is refused** with a toast. The before-run showed that a key pressed while the
  card still says "loading" wrote a verdict on an item nobody had seen. With the deep window this should almost never
  come up.
- **No new verdicts while a last visit's are being replayed** ("saving N verdicts from your last visit first").
- **A saved verdict counts as judged at once** for the window and the auto-advance, so the page never lands on an item
  already judged and waiting to be saved. Cards and counts still show only what the bridge accepted.
- **Redo after taking back an unsent verdict** works through the normal stack, but only until an earlier waiting save
  is answered (a new write clears the redo tail, as it always has).
- **R6, jumping back with a deep backlog:** kept as 9ccd3031 built it. In testing a refusal answered 2 s late took the
  page back 8 items. It was clear, but it is a jump. This is one of the questions below.
- **The carry worker's yield:** `QUIET_S = 0.12`, `MAX_YIELD_S = 1.0`, `CARRY_RUN = 8`. Carries finished 0.3–0.4 s
  after a 50-burst.
- **The window:** `PREFETCH_AHEAD = 16`, `REFILL_AT = 4`, `ITEM_LRU_MAX = 40`. One item is about 12.5 kB of JSON, so 40
  cached items are a few MB.
- **The counts beat is 5 s**, plus one re-read 1.5 s after the backlog empties.
- **The cliff when a carry lands in the queue on screen** (`invalidateAfterCarry` → `bumpReviewVersion`) was left as
  it is. In these runs no carry on queue 57 reached its own rows, so measurement gave no reason to change it.

## The gate

- `npx tsc -b` was clean, and a private `vite build` built (into the scratchpad, never `client/dist`).
- conda: the named suites, plus `test_as_review_momentum.py`, `test_review_momentum_core.py` and
  `test_ar_speed_core.py`: **154 passed**.
- venv: `test_webui_review.py`, `_review_carry.py`, `_review_archive.py`, `_ar_speed.py` and `_review_momentum.py`:
  **64 passed**.
- Smoke units, run on a fresh sandbox with the private build. Every failure is in `smoke-baseline-2026-10-21.txt`,
  there were 0 browser console errors and 0 unexpected server tracebacks.

  | Unit | Result |
  |---|---|
  | `review` | 10 failures, all in the baseline. They look for fixture items ("100", "102") the real DB does not have. |
  | `zzzzzzzzzzz_night_review` | 0 failures |
  | `zzzzzzzzzzz_review_carry` | 2 failures, both in the baseline |
  | `zzzzzzzzzzz_w2_archive` | 0 failures |
  | `zzzzzzzzzzz_explore_review` | 0 failures |

  Because the smoke's verdict states fail on this DB for data reasons, `scripts/review_burst.py` is the real test of
  the verdict path here.
- Tests changed on purpose, each named in the commit message:
  - `test_night_review.py`: the window size, the batched read, the carry ids from the save's ack.
  - `test_tq_review.py`: the window warm is one call.
  - `test_night_a_review.py`: the undo opening and the landing's guard.

## What is left

- **Going live** needs the researcher's yes. Then: `npm run build` in `webui/client`, and a restart of 8765, because
  bridge code changed (the new routes, the carry yield). Ask them first to pause and wait for "all saved". The carry
  worker re-queues pending carries at start.
- **Question: should the open queue rail stay open while judging?** Today the auto-advance closes it (scenario 1b). It
  is a one-line change to carry `rail` through `goUnit`.
- **Question: is the jump back to a refused verdict right with a deep backlog?** It is kept as it was.
- `scripts/review_burst.py` is committed as dev tooling. It refuses any bridge that is not a sandbox.
- The first step after **opening** a queue can still be a cold read: the first window read goes out after the first
  card. That was not part of the brief's scenarios.
