# tq-reads — one shared-read primitive instead of five

Package id for commits: `tq-reads`. Read `docs/prompts/quality/00-common.md` first.

## The finding

The night wave wrote the same idea, "many callers want the same read at once, so share it", three more times, by
three agents in one night. Two of the copies export an interface with the same name and different shapes:

- `webui/client/src/shell/sharedRead.ts` (night-c): `makeSharedRead(fetcher, {ttlMs, initial})` →
  `SharedRead<T> { get, error, subscribe, refresh(force) }`. Keeps the last value, joins the read in flight, does not
  re-ask within `ttlMs`, keeps the last value and reports `error()` on a failure. One user: `shell/needYouShared.ts`
  (the header's "N need you", 15 s TTL).
- `webui/client/src/library/groupingsRead.ts` (night-b): `sharedRead(fetcher, {ttlMs, now})` →
  `SharedRead<T> { read, version, invalidate, subscribe }`. A promise cache: callers within `ttlMs` (2 s) share one
  read, `invalidate()` bumps a version and tells subscribers, a failed read is dropped and never served again. One
  user: `library/chrome.tsx` (`useAllGroupings`, ~line 160–180), which hand-rolls the subscription with
  `useState(GROUPINGS.version)` + `useEffect(() => GROUPINGS.subscribe(...))` and overrides `useSourced`'s `reload`.
- `webui/client/src/explore/coalesce.ts` (night-b): `coalesced(read, keyOf)` — keyed, in-flight only, the key
  dropped when the read settles. Users: `api/explore.ts:93-98` (`wholeSpans`, `getChannelShared`, plus a second name
  `getWholeChannelSpans` for an existing read) and `explore/SignalPage.tsx:144`
  (`spansRev === 0 ? getWholeChannelSpans(...) : getSpans(...)`). The api layer imports from `explore/`.
- Older siblings the comments themselves name: `shell/heldOutLock.ts` (module-level `inflight` + `answeredAt`) and
  `analyse/useAdapters.ts` (module-level `inflight` + `cache`). Each new file's header cites a "near-sibling" and then
  writes another one anyway.

Also: `api/needYou.ts` (`useReviewNeedYou`) is now dead. Its replacement's comment says it is "kept for its other
callers", but it has none: `shell/Header.tsx` uses `useSharedNeedYou`. And `tests/test_webui_header_counts.py::
test_the_header_reads_the_live_review_count` is **red on main** because it still pins `useReviewNeedYou` in
`Header.tsx` (logged in `docs/prompts/fixup/BACKLOG.md:128`, "accept the shared need-you read").

## The remedy

One pure module (keep it at `shell/sharedRead.ts`, or move it to `api/sharedRead.ts` if that reads better, since
the api layer is its main user; your call, say why) holding one primitive that covers all of these:

- joins the read in flight;
- optional TTL (0 = in-flight only, like `coalesced`);
- an optional key (the keyed form replaces `coalesced`);
- `invalidate()` + `subscribe()` + `version()`;
- a last-value read for synchronous display (`get()`, used by the header) with the failure rule chosen per use.
  The header keeps its last count on a failure; groupings never serve a failed read twice. Make that one explicit
  option, not two code paths.

Add one React hook (in a separate small file, since the primitive must stay pure for Node) built on
`useSyncExternalStore`, so `useSharedNeedYou` and `useAllGroupings` stop hand-rolling subscriptions.

Then:

1. Migrate `needYouShared.ts`, `useAllGroupings` (chrome.tsx), and `api/explore.ts`'s two coalesced reads onto it.
   Delete `library/groupingsRead.ts` and `explore/coalesce.ts`.
2. Migrate `heldOutLock.ts` and `useAdapters.ts` if each maps onto the primitive with its behaviour intact.
   If one does not, leave it and say why.
3. Delete `api/needYou.ts`. Re-point `tests/test_webui_header_counts.py` at the shared read: the header must still
   read `/api/review/counts`, the route's `need_you` key, start at 0, and never throw on a failed read. That test goes
   green.
4. Remove the second name `getWholeChannelSpans` if it is only an alias. Collapse SignalPage's
   `spansRev === 0 ? … : …` if the shared read makes it unnecessary (a re-read after a write must still be fresh).

## Behaviour that must not change

- **Header count:** 15 s TTL across every header; a remount shows the last answer at once (no "0 need you" flash); a
  failed read logs `console.warn('review counts unavailable for the header chip', …)` and keeps the last count (0
  before any answer).
- **Groupings:** callers within 2 s share one read; a later open reads fresh; `invalidate()` refreshes every
  subscriber with ONE read; a failed read is never served again.
- **Explore:** only the read in flight is shared; once it settles the key is dropped, so a re-read after a write is a
  fresh read; a failure is never served twice.
- **heldOutLock / useAdapters:** whatever they do now, read them first.

## Files

`webui/client/src/shell/sharedRead.ts`, `shell/needYouShared.ts`, `shell/Header.tsx` (only if needed),
`api/needYou.ts` (delete), `library/groupingsRead.ts` (delete), `library/chrome.tsx` (only `useAllGroupings` and
imports; another package will split the Grouping editor next, so stay out of the rest of the file),
`explore/coalesce.ts` (delete), `api/explore.ts`, `explore/SignalPage.tsx`, `shell/heldOutLock.ts`,
`analyse/useAdapters.ts`, one new hook file.

Tests that pin these files: `tests/test_night_c_shell.py`, `tests/test_webui_header_counts.py`,
`tests/test_webui_night_b_critic.py`, `tests/test_webui_night_b_groupings_read.py`,
`tests/test_webui_night_b_spans_once.py` (all `webui/.venv` python except test_night_c_shell.py, which is conda;
check each file's header), plus `tests/test_import_boundaries.py`. Run them all before your first change and record
the failure set (expect exactly the header-count failure above); compare by set at the end.

Smoke units for the manager: `library`, `explore`, `a2_p1_held_out`, `review`.
