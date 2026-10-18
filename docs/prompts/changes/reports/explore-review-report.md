# explore-review — report

WORKTREE: C:\Users\mmebr\Documents\CNN\.claude\worktrees\agent-adf64434b6cf66619
BRANCH: worktree-agent-adf64434b6cf66619 (base 9504e38)

## 1. Assumed

- **The queue's kind is `discovery-run`, not a new `explore-picked`.** `create_queue` refuses a kind outside `SOURCE_KINDS`, and adding one means editing `Working/review/queues.py`, which the AR speed pass is rewriting. `discovery-run` is the detection kind `extend_queue` accepts. The queue is named "Unjudged motifs · picked from Explore" and found by a fixed note (`find_open_queue_by_note`), the same way Discovery finds its picked queue. If the manager wants a separate kind after AR merges, it is one tuple entry in `queues.py` plus one string in `explore_routes.py`.
- **"One queue per Explore session" means one open queue for all of Explore.** Explore has no session row. Every send goes into the same open queue, from any channel, Signal or Cross-channel. Once it is closed in Review, the next send starts a new one.
- **On Signal, "the selection" is the span in view.** That is what the existing "Selected span" row already acts on; Signal has no separate brush. So Signal does not get a Zoom button (zooming to the view does nothing). The Zoom button is there for `cross-channel-overlay` to switch on with `onZoom`.
- **The artifact rows are written through `write_human`**, the rule-5 human door *Take span* already uses, not by calling `queries.insert_annotation` directly. They end up in the same table with the same columns.
- **The artifact `source`** is `explore-cross-channel` from Cross-channel and `explore-signal` from Signal (the body's `origin` field). The verdict is always `artifact`. There is no new verdict word.
- **An artifact's channels must all belong to one recording** (otherwise 422). A window given in seconds only means one place on one recording's clock.
- **Signal also gets Mark artifact.** The picker lists only the channel on screen, already ticked. Cross-channel lists every channel of the recording, all ticked, with the reference first and labelled.
- **The drawer's "Send selected to Review"**:
  - **Live detections tab:** it now works for real, through the same route with `detection_ids`.
  - **Live annotations tab:** the button is off, and the page says why: an annotation already carries a human verdict, and *Take span* is how a span reaches Review.
  - **Canon demo channel (CH4_A2):** it stays the demo write it was, because its rows have fixture ids. Its toast now says "(demo)".
- **Cross-channel's "Send unjudged" reads the channels shown** (the stack's selection). Mark artifact reads the channels ticked in its picker.
- **Open in Analyse on Cross-channel** sends the reference channel over the window as the chain source, the same way Signal's *Send span to Analyse* works.

## 2. In plain words

In Explore you can now pick a stretch of signal and, in one click, put every motif the detectors found there that nobody has judged yet into Review. They all collect in a single "picked from Explore" pile, and each new send adds to it. The message says how many were added and how many were skipped because they were already judged. On Cross-channel you can also mark the same stretch as an artifact (noise, not biology) on several channels at once. You tick the channels the way you would tick names off a list.

## 3. Files

- `webui/server/explore_routes.py`: two new routes in one contiguous block appended at the end. The `edit-span` routes can append after it.
- `webui/client/src/explore/SpanActions.tsx`:
  - New: the exported `SpanActionStrip` and `StripChannel`.
  - `SpanActions` now draws the strip in place of its three buttons, keeping the testids `send-span` and `take-span`.
  - `SpanActions` gains an optional `onWritten` prop.
- `webui/client/src/explore/SignalPage.tsx` (strip wiring only):
  - a `spansRev` counter that re-reads the spans after a write;
  - `onWritten` passed to the span row and `onSent` passed to the drawer;
  - `useViewport` called with the counter. No other line was touched.
- `webui/client/src/explore/SignalDrawer.tsx`: the live "Send selected" path and an optional `onSent` prop.
- `webui/client/src/explore/CrossChannelPage.tsx` (action row only):
  - the demo `act-review` row and `reviewAll` are replaced by the strip plus a one-line caption;
  - imports `useApp`;
  - `recordDemoWrite` is dropped from its imports.
- `webui/client/src/explore/useViewport.ts` (**outside the file list**): an optional fourth parameter, `reloadKey = 0`, added to the effect's dependencies. It is append-only and every existing caller is unchanged. It was needed because the viewport's spans otherwise re-read only when the view moves.
- `webui/client/src/api/explore.ts` (**shared, append-only**): a block at the end containing:
  - its own `ApiError` import alias;
  - a local `explorePost`;
  - `SpanReviewResult`, `sendSpanToReview`, `sendDetectionIdsToReview`, `ArtifactResult`, `markArtifact`.
- New: `tests/test_webui_explore_review.py` and `webui/smoke_pages/zzzzzzzzzzz_explore_review.json`.
- Not touched: `queues.py`, `corpus.py`, `discovery.py`, `api.ts`. `corpus.spans` and the `queues_mod` helpers are reused by import.

## 4. What was built (the two routes' contracts)

1. **`POST /api/explore/span-review`**
   - **Body:** `{recording_ids: int[], t0_s, t1_s, note?}` for a window, or `{detection_ids: int[]}` for the drawer.
   - **Which detections:**
     - Window form: the detections intersecting `[t0, t1]` on those channels, found with `corpus.spans(..., cap=10**9)`. That is the same SQL Explore draws with: legacy relative rows shifted, and surrogate and window-part runs left out. Detections of a superseded (discarded) run are also dropped, because Review never serves them.
     - Ids form: each id is checked to exist and to come from a real run, not a surrogate's or a window part's.
   - **Unjudged** means no `adjudications` row.
   - **Writes:** `find_open_queue_by_note` → `create_queue(name="Unjudged motifs · picked from Explore", source_kind="discovery-run", filters={"detection_ids": ...})`, or `extend_queue` when the queue already exists.
   - **Returns:** `{queue_id, queue, added, added_ids, already_queued, already_judged, total, unjudged_in_queue, message, note}`.
   - **Empty window:** 200 with `added: 0`, a sentence, and no queue created for nothing.
   - **Refusals:** 404 unknown recording; 423 held out, through `corpus.recording_row → is_held_out → held_out_refusal`, the same predicate and sentence as `_rec` and *Take span*; 422 for an empty window, no channels, or bad, surrogate or unknown ids. Every check runs before any write.
2. **`POST /api/explore/artifact`**
   - **Body:** `{recording_ids, t0_s, t1_s, note?, origin: "cross-channel"|"signal"}`.
   - **Writes:** one `annotations` row per channel (verdict `artifact`, source `explore-cross-channel` or `explore-signal`), with the window clamped to each channel. Nothing else is written.
   - **Returns:** `{ids, recording_ids, start_s, end_s, verdict, source, message}`.
   - **Refusals:** 423 held out; 404 unknown channel; 422 for an empty window, a window wholly outside the channel, no channels, mixed recordings, or a bad `origin`. Every channel is checked before the first row is written.
3. **`SpanActionStrip` props**, for `cross-channel-overlay`:
   - `window: [t0, t1]` in seconds.
   - `reviewChannels: number[]`: what *Send unjudged* reads.
   - `artifactChannels: {id, name}[]` and `referenceId`: the picker's list, with the reference first and always pre-ticked.
   - `defaultArtifactIds?`: defaults to every channel.
   - `origin: 'signal' | 'cross-channel'`; `note?`.
   - Optional actions: `onZoom?` (Zoom), `onOpenInAnalyse?` (Open in Analyse, green, testid `send-span`), `onTake?` and `taking?` (Take span, testid `take-span`). Each button appears only when its prop is passed.
   - Callbacks: `onSent?(SpanReviewResult)` and `onMarked?(ArtifactResult)`.
   - `extra?: ReactNode`: drawn after Open in Analyse. This is where *Open in Signal* goes, without editing the strip.
   - `disabledReason?`: switches every action off with a reason.
   - `testid?`: defaults to `span-action-strip`.
   - **Button order:** Zoom · Send unjudged to Review · Mark artifact (N channels…) · Open in Analyse · extra · Take span.
   - **Styling:** Send and Mark are `primary` (the muted blue). Open in Analyse stays `next` (green).
   - **Toasts:** carry *Open Review →* to `review/queue/<id>`. Errors are red toasts.
4. Signal re-reads both its viewport spans and its whole-channel list after any write, so a new artifact band appears straight away.
5. **Not done: the judged/queued look of the detection bands.** No per-detection "queued" state reaches the Signal bands. The spans payload carries no adjudication or picked state, and the band drawing (`SpanView`, verdict-keyed bands) belongs to `explore-span-plot`. The data to read it from does exist: `queues.queue_items` over the picked queue, as Discovery's `_picked_states` does.

## 5. Tests

- **Red commit `b8ecf39`:** `tests/test_webui_explore_review.py`, 8 tests, all failing (8 failed in 38 s). Six fail with "no such API route: POST /api/explore/span-review" or ".../artifact"; the malformed-window test fails on 404 ≠ 422, because the route did not exist yet.
- **Green, run with `webui/.venv` python:** `test_webui_explore_review.py` 8 passed. What the tests pin:
  - the route sends exactly the unjudged detections intersecting the window on the named channels: the judged one is counted and not added, the one outside the window and the surrogate's span are left out; the queue writes `adjudications`, and Review counts the right number remaining;
  - a second call appends to the same queue, and repeating a window adds 0 and reports `already_queued` (still only one `review_queues` row);
  - an empty window is a sentence, writes nothing and creates no queue;
  - the drawer's ids go through the same queue, and a surrogate's or an unknown id is refused without writing;
  - the held-out recording is refused (423) for windows and ids, with nothing written;
  - a malformed window is refused (422 / 404);
  - the artifact route writes exactly one artifact row per channel, with the right extent, source and note, and every other table is unchanged;
  - the artifact route refuses held-out, empty and out-of-range windows and an empty channel list, writing nothing.
- **The named files, also with the venv python:**
  - `test_webui_cross_page.py` + `test_webui_corpus.py` (with mine): 39 passed;
  - `test_webui_review.py` + `test_webui_review_axis.py`: 39 passed;
  - `test_webui_routes.py`: 12 passed.
- **Conda python:** `tests/test_import_boundaries.py` 4 passed.

## 6. Smoke states — `webui/smoke_pages/zzzzzzzzzzz_explore_review.json` (sorted last: it writes)

1. `er-strip-shows-new-buttons` (Signal 4): the span row's strip shows Send unjudged (the primary, muted-blue class), Mark artifact, Open in Analyse and Take span.
2. `er-send-unjudged-toast` (Signal 4): click Send unjudged; a toast appears and none of them is an error. **Writes:** it creates or extends the picked queue in the sandbox. On real data the toast should read like "… · N added to 'Unjudged motifs · picked from Explore' · M already judged (not added)", or "no detections in this window on 1 channel — nothing to send".
3. `er-signal-artifact-picker` (Signal 4): Mark artifact opens the picker with this channel ticked and a confirm button. Nothing is written.
4. `er-cross-strip-replaces-demo-row` (Cross 4): the strip is under Take it further with Send, Mark and Open in Analyse; `act-review` is gone; there is no Take span.
5. `er-cross-artifact-picker` (Cross 4): Mark artifact opens the picker with every channel ticked, all/none links and a confirm button that counts channels. Not confirmed, because that would write.

**Worth checking by hand on real data:**
- confirm an artifact on Cross-channel and see it as an artifact band on each channel's Signal page;
- send twice on the same span and see "N already in the queue".

## 7. Gates I ran

- `tsc -b`: clean.
- `vite build`: built, with only the existing Gallery dynamic-import warning.
- Tests: the files in §5.

## 8. Open questions and risks

- **Compare could adopt the Explore queue.** Discovery Compare's `send_remainder_to_review` skips only notes that start with Discovery's `PICKED_NOTE_PREFIX`. If the Explore queue's detection set ever exactly equals a Compare remainder, Compare would adopt it as its own. That needs an identical set, so it is very unlikely. The fix is one more prefix in Compare's skip, inside `discovery.py`, which AR owns.
- **Big windows.** The span-review route reads `corpus.spans` uncapped. A whole-recording window on a channel with hundreds of thousands of detections would put them all into one queue filter (`filters_json`). The strip acts on what the researcher selected, so this is by design, but a cap or a confirm step for very large sends may be wanted.
- **Superseded runs are still counted elsewhere.** `corpus.spans` does not drop them; I drop them only here, so `total` can be smaller than the count of detection bands on screen when a discarded run is shown.
- **Band state on Signal** (§4 item 5) is left for `explore-span-plot`.
- **RQ files:** none updated; no research question's answerability changes.

## 9. Commits

```
9ed1618 explore-review: the shared action strip on Signal and Cross-channel
ca8c7ca explore-review: span-review and artifact routes
b8ecf39 explore-review: failing tests for span-review and artifact routes
(+ this report)
```


## Critic round (2026-10-18)

**In plain words.** The two new buttons do what they say, and they write to the right tables. The test-first commit was red. There were two problems, both now fixed. First, a big window could pour tens of thousands of motifs into one Review pile and make Review crawl. Second, the toast could count a motif as "added" when Review would never actually ask about it. One merge-time note matters more than it looks: switching the queue's kind to `explore-picked` is a **database migration**, not a one-line change. The recommendation is to keep `discovery-run`.

### Findings

1. **Should-fix, FIXED: no cap on a send.**
   - Where: `explore_routes.py`, `send_span_to_review`.
   - Evidence: a synthetic database with 16 channels × 694 h, 52,000 detections, legacy span-relative runs and a discarded run.
     - A whole-recording send put 49,378 ids into one filter. Review then took **79 s** to open the queue and **8.2 s** to list queues.
     - A 1,561-id send took 4.4 s to open and 0.7 s to list.
   - Fix: `SPAN_REVIEW_MAX = 2000` unjudged detections per send. Above it, the route answers 422, writes nothing, and its sentence names the count and asks for a narrower window. The cap applies to both the window form and the ids form. The client shows the sentence as a red toast.
   - Not capped: the queue's cumulative size over many sends (see "For the manager").
2. **Should-fix, FIXED: the toast over-counted "added".**
   - A detection that is the same event as a span a person already judged (`prior_verdict`) goes into the filter, but Review never serves it.
   - The message now says "N not asked: a human verdict already covers it", the same way Discovery's `_send_picked` reports it. It reads `queue_items(include_prior_judged=True)`.
   - New response field: `not_asked`.
3. **Nit, FIXED: the artifact response echoed the requested window.** `start_s`/`end_s` now give the extent actually written, which is clamped at the channel's end.
4. **Nit, FIXED: the Send tooltip did not name the window.** It now gives the window in hours and, on Signal, says "(the span in view)". The toast already led with the range.
5. **Verified correct on the synthetic database.**
   - Counts are exact by hand: 1,822 in the window, 261 judged, 1,561 added. Legacy relative rows are shifted and included; the discarded run's rows are left out.
   - A second identical send adds 0 and reports 1,561 already queued.
   - The held-out recording gets 423.
   - An artifact window crossing a channel's end is clamped.
6. **Checked, true: "Signal has no brush".**
   - In `SpanView.tsx`, dragging pans and the wheel zooms. A clicked motif has its own *Take for Review* in `MotifView`.
   - So the span in view is the only selection on Signal. The tooltip and toast now name it.
7. **Checked, fine.**
   - `find_open_queue_by_note` is the shared helper in `queues.py`, not a second copy.
   - Rule 5 holds: span-review writes only `review_queues` (`writes_to = adjudications`), and the artifact route writes only `annotations` through `write_human`.
   - The `reloadKey` in `useViewport` only changes on a write, so it cannot loop.
   - The secondary buttons are `primary`, which is the muted blue.
   - The smoke unit is valid JSON, uses `explore/signal/4` and `explore/cross-channel/4` as the other smoke files do, and its testids exist.
8. **Not fixed, outside this prompt's files: the Signal run filter.**
   - The send reads every run on the channel, not only the runs the picker shows. The toast's counts are true, but they can exceed the bands drawn on screen.
   - The run filter belongs to `explore-span-plot`. If wanted, it would be an optional `run_ids` on the route plus a strip prop.
9. **Nit, not fixed: `SpanReviewBody.note` is accepted but unused.** It is harmless.

### Work item 3 (queued/judged bands after a send)

The re-read is done. The queued look is **not** possible inside this prompt's files: the bands are coloured in `SignalPage`'s band memo and in `SpanView`, both owned by `explore-span-plot`, and the spans payload (`corpus.py`) carries no picked state.

What is needed:
- a per-detection state (`judged` / `waiting` / `not-asked`) read from the open Explore picked queue with `queue_items(include_judged=True, include_prior_judged=True)`, exactly as `discovery._picked_states` does;
- that state served beside the spans;
- a band style for "queued".

### For the manager (merge time)

1. **Queue kind: recommend keeping `discovery-run`.** Switching to `explore-picked` is **not** one tuple entry. `review_queues.source_kind` has a SQL CHECK, so the switch needs:
   - in `schema.py`: the kind added to the `_REVIEW_SCHEMA` CHECK, and `_REVIEW_QUEUES_NEW_KIND` bumped to it, which **rebuilds `review_queues` on the real database** (with a backup);
   - in `queues.py`: `SOURCE_KINDS`, `_DEFAULTS["explore-picked"] = ("detection", "adjudications", 0)`, and `_DETECTION_KINDS`, which `extend_queue`, `create_queue`'s check and the resolver at :516 read;
   - in `webui/client/src/api/review.ts`: `ICONS`, `RANKS`, and the `runId` line, plus the `fixtures/review.ts` `QueueSource` type;
   - in `explore_routes.py`: the two `source_kind="discovery-run"` strings;
   - in `tests/test_webui_explore_review.py`: nothing, because it asserts `writes_to`, not the kind.
2. **Compare skip (only while the kind stays `discovery-run`).**
   - Where: `webui/server/discovery.py`, `send_remainder_to_review`.
   - Change: `skip_note_prefix=PICKED_NOTE_PREFIX` becomes `skip_note_prefix=(PICKED_NOTE_PREFIX, EXPLORE_PICKED_NOTE)`.
   - `str.startswith` takes a tuple, so `queues.py` needs no change. Import `EXPLORE_PICKED_NOTE` from `.explore_routes`.
3. **Cumulative size.** The cap is per send. Repeated sends can still grow the one open picked queue past what Review handles quickly; closing it in Review starts a new one. Recheck after AR's speed pass lands, which changes the timings above.
4. **Smoke states** (`zzzzzzzzzzz_explore_review.json`, sorted last, writes):
   - `er-strip-shows-new-buttons`: the strip has Send unjudged (`.primary`), Mark artifact, Open in Analyse and Take span.
   - `er-send-unjudged-toast`: a toast, not an error. On the real database's channel 4, a 2-hour view should hold far fewer than 2,000 motifs. If it is a dense channel, the toast is a red 422 refusal and this state fails; that means the cap fired, not a bug, so narrow the initial view or raise the cap.
   - `er-signal-artifact-picker`: the picker with one checkbox, ticked, and a confirm button.
   - `er-cross-strip-replaces-demo-row`: the strip is under Take it further, there is no `act-review`, and there is no Take span.
   - `er-cross-artifact-picker`: every checkbox ticked, all/none links, and the confirm button counting channels.
5. **By hand on real data:**
   - mark an artifact on Cross-channel and see the artifact band on each channel's Signal page;
   - send the same span twice: "N already in the queue";
   - send from a span with a human-judged event: "not asked".

### Gate after fixes

| Check | Interpreter | Result |
|---|---|---|
| `test_webui_explore_review.py` | venv | 11 passed |
| `test_webui_review.py` | venv | 32 passed |
| `test_webui_review_axis.py` | venv | 7 passed |
| `test_webui_corpus.py` | venv | 10 passed |
| `test_import_boundaries.py` | conda | 4 passed |
| `tsc -b` | — | clean |
| `vite build` | — | built, with the existing Gallery warning only |

Fix commit: `104bf66`.
