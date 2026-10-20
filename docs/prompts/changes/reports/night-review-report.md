# night-review: Review with no lag between items, and the grouping tree by default (2026-10-20/21)

Branch `night/review`, base `f1f1109`. Port 8769, one bridge at a time. **All timings were taken under load**:
another session was training MiniRocket on this machine, and the two other night agents were running too.

## In plain words

Think of Review as a deck of cards that you turn over one at a time. Before tonight the page fetched the next
card from the back room only after you had turned the current one over. Worse, after most verdicts it threw
away every card it had laid out and re-read the whole deck, so on the demo's queue a verdict took 1–8 s to
reach the next card. Now the next five cards (and the one before) are laid out ahead of time. A verdict no
longer clears the table unless it actually changed a card in this deck. On queue 31 a verdict now reaches the
next card in about 0.2 s, and an arrow key takes about 25 ms.

In Library, *Edit grouping* used to open on the newest grouping. On the real database that is g-09, amplitude
bins, which has no tree, so the dendrogram was nowhere on the page. The editor now opens on a Ward (tree)
grouping, and if that grouping has no kept tree, it builds the tree straight away.

## Assumed

- **"Five ahead"** means the next five *unjudged* items (where a run of verdicts lands), plus the very next unit
  (where → lands, judged or not), plus the previous one (←). Clusters are skipped: they are read through the
  cluster route. The reads go one at a time, nearest first. They start only from an item the researcher stopped
  on (night-a's 150 ms rule), and they stop the moment the researcher moves.
- **The advance after a verdict still waits for the bridge's accept.** Moving on before the accept would mean a
  refusal shows up on the next item. A verdict on the wrong item is worse than a lag, so I kept the wait. I cut
  the flash pause after the accept from 350 ms to 60 ms; the "previous" line names the write that landed.
- **"Add new grouping" is *Edit grouping*.** No separate "new grouping" control exists; every apply saves a new
  grouping. With no `?basis=` in the address (or a tree basis named there), the editor opens on the current
  grouping if it is Ward on a distance basis. Otherwise it opens on the newest such grouping of the unit.
- **The tree is built automatically only for motifs on shape distance.** On the sandbox walk the automatic build
  for a sequence grouping (g-06, sequence similarity) failed in the core with "tree.tree_key and tree.from_fit
  disagree" (job 727, a server traceback). Sequences keep the *Build the tree* button.

## Item 1: Review, no lag

**What I found** (measured with `webui/runtime/night-review/time_review.py`). It times key press → next card
painted, using a keydown dispatched in the page and polling animation frames until the new item's inspector,
verdict card and context card are all there.

1. The biggest cost was not the item read. Every verdict on these queues is **carried** to other runs'
   detections of the same event. On a carry the Inspector called `bumpReviewVersion()`, which empties the item
   cache **and** re-reads every row (1.6 s and 6 MB at 8,700 rows). The next card then waited for a cold read
   behind that re-read. The carried detections were in no row of the queue (for example 177361 on the fixture,
   4995371 on queue 31).
2. The auto-advance waited a further 350 ms after the accept.
3. Only three neighbours were kept warm (the next unjudged item and one either side). An item whose prefetch was
   still in flight waited the 150 ms settle anyway (night-a #24).

**What changed** (all client code; no bridge, core or cache-key change):

- `review/prefetch.ts` (new, pure): `prefetchIds()`, the window described under Assumed.
- `review/Inspector.tsx`:
  - the window is read with `prefetchItemThen` one item at a time, from a settle timer that the next item cancels;
  - an item already held or in flight joins its read with no settle (`itemHeld`);
  - `ADVANCE_MS` is 60;
  - a carry re-reads the rows only when `queueHoldsAny(data, carriedIds)` says it reached a row of this queue. An
    ack that names no ids re-reads as before. Counts are still re-read on every accepted write.
- `review/queue.ts`: `queueHoldsAny()`, an index of row ids, detection ids and overlap members, built once per
  queue read.
- `api/review.ts` (append-only): `itemHeld()`, `prefetchItemThen()`. `ITEM_LRU_MAX` stays 12, which holds the
  window (7) plus the item on screen.
- Unchanged: `judged.ts`, `writesInFlight()` and undo/redo waiting for it, the verdict closure bound to the item
  it was pressed on, and the advance only from the item the verdict was given on.

**Before → after** (key press → next card painted, median (min–max), ms):

| queue | key | before (f1f1109 client) | after |
|---|---|---|---|
| scale fixture, 8,707 items (`perf_fixture.build`, 4 ch × 721 h, 400 k detections) | → after 3 s on an item | 31 (24–51) | 32 (20–43) |
| same | **I (verdict)** | **3,656 (2,413–4,650)** | **180 (145–316)** |
| same | → past the warm window (cold) | 284 (261–296) | 261 (259–262) |
| queue 31 on a backup copy of the real database (148 items, all unjudged on the copy) | → after 3 s | 31 (24–1,525) | 23 (8–30) |
| same | **I (verdict)** | **2,170 (1,245–7,912)** | **212 (177–391)** |
| same | → past the warm window (cold) | 445 (428–877) | 445 (26–644) |

What the remaining ~200 ms per verdict is made of:

- the POST round trip: 80 ms on the fixture and 170 ms on queue 31, most of it the `queue_counts` the bridge
  adds to the ack;
- the 60 ms flash;
- one paint.

Reaching under 100 ms would need either an advance before the accept (not done, see Assumed) or a lighter POST
that sends no counts (a bridge change). A cold step past the window is 150 ms of settle plus the read, which is
night-a's rule for fast stepping.

On the backup copy, signal reads have no `.npy` files, so item reads are lighter than on the live bridge. The
real-copy numbers measure the carry and the cache, not the trace read.

## Item 2: the grouping tree by default

**What happened before:**

- The editor seeded from the current grouping, which is the newest one unless another was picked. On the real
  database that is g-09 (amplitude, feature bins), so the draft opened on amplitude and there was no tree panel.
- Even after switching to shape distance, the panel was drawn only for a *current* Ward grouping, so it stayed
  absent.
- On g-05 (Ward, made before trees were kept) the panel was an amber "No tree to draw" with a *Build the tree*
  button.

**What changed** (`library/GroupingPage.tsx`, new `library/treeSource.ts`):

- The editor opens on `treeSource(all, unit, current)`: the current grouping if it is a tree grouping, else the
  newest Ward grouping of that unit on a distance basis. A `?basis=` naming a non-tree basis keeps the old
  behaviour, so a feature-bin link still opens on its bins.
- When that grouping has no kept tree, the panel starts the same regroup that *Build the tree* runs: at the
  grouping's own settings, nothing saved until Apply. It does this once per editor, only on an untouched draft,
  only for motifs on shape distance, and never on a `?state=` deep link. The panel says "building the tree at
  g-05's settings …" while the job runs. When the job lands the dendrogram and its amber cut line are drawn,
  marked "built … not saved", and Apply saves a new grouping with the tree.
- A refused or failed build falls back to the button.
- Cost on the real-database sandbox: the build took about 12–21 s under load.

## Tests (interpreter per file)

- Red commit `29ca769`: 10 failed, 14 passed (conda python, node on PATH). Summary is in the commit body.
- `tests/test_night_review.py`, conda + node: 11 passed. It pins:
  - the window, run under node: next five unjudged, the next unit, the previous one, clusters skipped, queue ends;
  - that `ITEM_LRU_MAX` holds the window;
  - that the Inspector reads the window sequentially from a cancelled settle timer;
  - no settle for an item that is held or in flight;
  - `ADVANCE_MS <= 80` and the advance still after `commitWrite`;
  - that a carry re-reads the rows only when it reached this queue;
  - `treeSource`, run under node;
  - that the editor seeds from the tree source and the automatic build is guarded and motif-shape only.
- `tests/test_night_a_review.py`, conda: 19 passed. Its `test_stepping_fast_…` regex pinned the old three-
  neighbour loop and was edited to pin the same rule against the new window; the commit says so.
- `tests/test_import_boundaries.py`, conda: passed.
- `tests/test_webui_review.py`, `webui/.venv`: 32 passed.
- `tsc -b` and `vite build` pass from the worktree.

## Smoke states

Walked on the main checkout's sandbox bridge serving this client, under load.

New unit `webui/smoke_pages/zzzzzzzzzzz_night_review.json` (3 states, 0 failures):

1. `night-review-an-arrow-lands-on-a-warm-item`: queue 2 item 103, 3 s dwell, then →. The next item's card is
   there within 500 ms, with no item error. Read-only.
2. `night-review-five-arrows-stay-inside-the-warm-window`: item 104, 4 s dwell, then five → presses. The card
   moves off 104 within 500 ms with no item error. Read-only.
3. `night-review-the-editor-opens-on-the-tree`: the atlas pinned on g-09, then *Edit grouping*. Shape distance is
   checked and the tree panel draws a dendrogram with its cut handle; no "No tree to draw", no load or regroup
   failure.

Edited in place:

- `library.json` `shape-distance-default` (g-05): now waits for the automatic build's `preview-tree-note`, then
  expects shape distance and motifs checked, the preview computed, and Apply enabled. It used to expect
  "preview uncomputed".
- `zzzzzzzzzzz_an_library_tree.json` `fixup-an-a-grouping-made-before-trees-says-so`: the panel now builds and
  draws the tree, with `data-saved="0"`, `tree-unsaved`, the job note and the cut handle; no `tree-missing`. It
  used to expect the amber callout and the button.
- `zzzzzzzzzzz_an_library_tree.json` `fixup-an-build-the-tree-then-apply-it`: no click on `tree-build`; it waits
  for the automatic job's note, then applies.

Gate units on that bridge:

| unit | result |
|---|---|
| `zzzzzzzzzzz_night_review` | 3 / 0 |
| `zzzzzzzzzzz_an_library_tree` | 6 / 0 |
| `zzzzzzz_ah_blind_test` | 6 / 0 |
| `library` | 61 shots, 5 failures, none on the grouping editor (details below) |
| `review` and `zzzzzzzzzzz_review_carry` | 12 and 2 failures, the same set as the f1f1109 client on the same bridge (details below) |

- **`library` failures:** `family--member-selected` (cold load), `recurrence--held-out-recording` (the held-out
  lock is off in this DB), `templates--template-selected` and `templates--model-stage` (baseline), and an atlas
  reload timeout. All are outside the editor, and every `library.grouping` state passed.
- **`review` failures:** they are the same set with the before client (13 + 2). The cause is the database, not
  this change: the researcher's review this evening means queue 2 no longer serves items 100 and 102 as rows, and
  those states are pinned to them. They need re-pinning to items the queue still serves, in the manager's files.

## Not done, or for later

- **Under 100 ms per verdict.** It needs the ack's `queue_counts` cut or made cheaper (bridge, `review.py`
  `post_verdict`), or an optimistic advance (rejected tonight, see Assumed).
- **The cluster page** (`ClusterView.tsx`) keeps its own flow; it does not prefetch and its batch carry is
  unchanged.
- **Core bug:** a sequence-similarity Ward regroup fails with "tree.tree_key and tree.from_fit disagree"
  (`Working/library/grouping/tree.py`). Out of scope (no core change tonight).
- **Smoke-walk cost:** each `library.grouping` state that opens the editor on g-05 now runs a regroup, about 5
  jobs per walk at 3–20 s each. Once a grouping with a kept tree is applied (the fixup-an apply state does this),
  later opens draw it with no job.

## Fix round (the critic, 2026-10-21 00:40): red `87faf9c`, green in the next commit

- **F1, carry fields went stale.** A carry that reaches no row of this queue no longer empties the item cache, so
  an item of another queue read before the carry was served without its `carriedFrom`. The carried line
  vanished and the evidence rail said "earlier session". Now the carry fields are `{ ...carryOf(d?.entry),
  ...carryOf(row) }`. The row is re-read on every queue open and wins, and the bridge sends `carriedFrom` /
  `classLabel` only when set. Also, the no-re-read branch now drops every other queue's cached items
  (`clearItemCacheExcept(q)`, append-only in `api/review.ts`).
- **F2, the grouping job kept running after leaving the editor.** The job hook now:
  - remembers the job it started (`liveJob`);
  - moves a generation counter on every start, cancel and reset;
  - cancels the live job on unmount (browser back, a nav link, a hash change);
  - cancels at once a job whose id arrives after it was abandoned (a close before `runLibraryGrouping` answered).

  `cancel()` falls back to the remembered id when the view has none yet.
- **F3, undo raced the pending advance.** `undo` clears the pending advance timers before sending, so the 60 ms
  advance cannot move off the item being undone. It then navigates only when `onItem.current !== w.items[0]`.
- **F4, wrong field name.** The detection index reads the bridge's `detection_id` (the dead `r.detectionId`
  check is gone).

Gates:
- `tests/test_night_review.py` (15) and `tests/test_night_a_review.py` (15): 30 passed, conda python + node.
- `tsc -b` and `vite build` pass.
- Smoke `zzzzzzzzzzz_night_review` on the main checkout's sandbox bridge with this client: 3/0, no tracebacks.
