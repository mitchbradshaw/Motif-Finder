# tq-review — the Review inspector's cursor as one state model

Package id for commits: `tq-review`. Read `docs/prompts/quality/00-common.md` first.

Review is the researcher's most-used surface and the one CLAUDE.md asks to be the most reliable. Be conservative:
every behaviour listed below must survive, and the smoke units below will be walked at the gate.

## The findings

1. **The advance, prefetch and write ordering is a set of flags and timers, not a state model.**
   Files: `webui/client/src/review/Inspector.tsx:70-77, 93-99, 111-125, 196-197, 256-260, 273`;
   `store.ts:173-207`; `ClusterView.tsx:189, 203`.

   One concept, "where the researcher is and what is pending for that spot", is spread over seven mechanisms:
   - a settle timer inside the item read;
   - a second settle timer plus a `live` flag for the prefetch chain;
   - an `onItem` ref mirroring `id`;
   - a `timers` ref cleared in three places: unmount, the id-change effect, and inside `undo` (the F3 patch);
   - `onItem.current === id` guards inside the flash and advance callbacks;
   - a module-level `inFlight` counter in `store.ts`;
   - the "try again" guard copy-pasted four times across Inspector and ClusterView.

   Each F-round fix (night-review, commit 222e8eb) patched one interaction:
   - F3 exists because the advance timer is owned by nothing that undo touches.
   - `onItem` exists because the timer is scheduled after `await commitWrite` and can outlive the item.

   Also:
   - `peekItem(q,id,opts) || itemHeld(q,id,opts)` (line ~74) is just `itemHeld`, since `SETTLED`'s keys are a subset
     of `ITEMS`'s (`api/review.ts:~422-431`). Verify that.
   - `store.ts:~173` leaves `commitWrite`'s doc comment stranded above the new `let inFlight`.
2. **`QueueRow.judged` is a wrong flag kept alive beside a corrected one.** Files: `api/review.ts:35-37, 250-251`;
   `review/judged.ts`; `queue.ts:65, 127, 139`.
   - `rowOf` sets `judged: raw?.judged === true || raw?.judged === 1 || !!base`, which is exactly the bug night-a fixed,
     plus `servedJudged`.
   - `baseJudged` reduces to `servedJudged ?? !!baseVerdict`.
   - If nothing else reads `row.judged` (verify, including spreads into other components), compute the one truth in
     `rowOf` (`judged = raw.judged != null ? raw.judged === true || raw.judged === 1 : !!base`), delete `servedJudged`,
     and delete `judged.ts` or make it trivial.
3. **The carry/invalidate policy (F1/F4) rests on an unchecked cast and lives in the wrong layer.** Files:
   `api/review.ts:~605, ~631-633`; `Inspector.tsx:~141, ~186-192`; `queue.ts:~152-171`.
   - `carryOf = (e: unknown) => (e ?? {}) as CarryFields` is a bare cast. F1's `{ ...carryOf(d?.entry), ...carryOf(row) }`
     therefore spreads every field (thumbnails included), typed as four.
   - F4's `(r as unknown as { detection_id?: unknown }).detection_id` exists because `QueueRow` never declared the field.
   - `queueHoldsAny` mixes row ids and detection ids in one `Set<string>`.
   - The which-caches-to-drop decision (`bumpReviewVersion` vs `clearItemCacheExcept(q)`) is a branch in the middle of
     `write()`, with its index in `queue.ts`, whose header says it owns order, units, counts and navigation.
4. **Smaller items.**
   - `index.tsx`: `(d.queue.source as string) === 'blind-test'` appears twice because `QueueSource`
     (`fixtures/review.ts:~8`) lacks `'blind-test'`.
   - `index.tsx`: `(data.error as {status?}).status` should be `instanceof ApiError` (`api.ts:~13`).

## The remedy

- **A small `review/cursor.ts`** (or another name that fits) owning, per queue:
  - **Navigation.** `land(id)` aborts the previous landing's AbortController, waits one settle delay, reads `id`, then
    reads `prefetchIds(...)` one at a time on the same signal. One controller and one timer replace `live`, the second
    `STEP_SETTLE_MS` and the `itemHeld` special case. Keep "a held item skips the settle" (night-review).
  - **Pending advance.** `pending: {from: id} | null`, set when a verdict is acknowledged and cleared by any `land` or
    `undo`. This replaces the `onItem` ref, the `timers` ref and the F3 patch. A check right after the `await`, not
    inside the timer, decides whether to schedule.
  - **Writes.** KEEP the current "try again" refusal semantics: do NOT turn a refused undo into a queued one, since that
    is a behaviour change. Move the refusal inside `store.ts` (`commitUndo`/`commitRedo` return or throw a typed
    refusal), so the four call-site copies become one.
  - Inspector and ClusterView call the cursor and hold no timer or ref bookkeeping of their own.
  - Keep `prefetch.ts` (pure, tested) as the window rule.
- Finding 2 and finding 3:
  - typed `carry` and `detectionId` on `QueueRow`, produced by `rowOf` and `detailOf`;
  - `carryOf` picks fields explicitly;
  - index detection ids only;
  - the invalidate decision as one function next to the caches in `api/review.ts` (for example
    `invalidateAfterCarry(...)`), so `write()` keeps only the toast.
- Finding 4 as stated.

## Behaviour that must not change

- **The next five unjudged items, the very next unit and the previous one are kept warm, nearest first** (prefetch).
- **A held item paints at once** with no settle.
- **The advance after a verdict takes one frame**, and undo cancels a pending advance (F3).
- **Moving to another item** cancels the old item's read and prefetch chain, and nothing from the old item lands on the
  new one (no flash, no advance).
- **Carry:**
  - Carry fields come from the fresh row (F1).
  - Other queues' cached items are dropped when a carry reaches them.
  - A carry that reaches no row of this queue does not re-read every row.
  - `detection_id` is used for the carry match (F4).
- **The "try again" refusals** fire in exactly the same situations, with the same text.
- **Judged / unjudged counts** and "No more items" match the current code for every row shape (served flag present,
  absent, prior verdict present).
- **Blind-test routing** goes through `QueueRoute`.

## Files

`webui/client/src/review/Inspector.tsx`, `review/store.ts`, `review/ClusterView.tsx`, `review/queue.ts`,
`review/judged.ts`, `review/prefetch.ts`, `review/index.tsx`, `review/Shell.tsx` (only if a shared predicate needs it),
`api/review.ts`, `fixtures/review.ts` (the union only), one new cursor file.

Tests: `tests/test_night_review.py`, `tests/test_night_a_review.py`, `tests/test_webui_night_a.py`,
`tests/test_webui_review.py`, `tests/test_webui_review_carry.py`, `tests/test_webui_ar_speed.py`,
`tests/test_webui_blind.py`, `tests/test_webui_family_queue.py`, `tests/test_review_queue.py`, and
`grep -rln "Inspector\|store\.ts\|judged\.ts\|baseJudged\|servedJudged\|carryOf\|queueHoldsAny\|commitWrite\|STEP_SETTLE_MS\|prefetchIds" tests/`.
Run them before your first change and record the failure set; compare by set at the end.

Smoke units for the manager: `review`, `zzzzzzzzzzz_night_review`, `zzzzzzzzzzz_review_carry`,
`zzzzzzzzzzz_explore_review`, `zzzzzzzzzzz_edit_span`, `zzzzzzzzzzz_family_actions`, `zzzzzzz_ah_blind_test`.
