# review-carry-and-overlap — report

Branch `worktree-agent-a899623af3c191ed1`, worktree `.claude/worktrees/agent-a899623af3c191ed1`, base `32bef5b`
(main with AR `5a20070` merged plus the ledger docs commit).

## In plain words (for the researcher)

Think of each event in a recording as a person, and each detection as a photograph of that person. Before this
change, Review showed you every photograph. If one detector took three overlapping photos of the same moment, you
judged the same person three times. If a second run photographed the same moment again, you judged them a fourth
time.

Now:

- **Overlapping photos from one run are one card.** The card says "covers 3 detections". Your verdict is written to
  all three. The detector's own output is not changed.
- **When you judge an event, every other run's photo of the same event gets your verdict too.** "The same event"
  uses the scoreboard's existing matching rule. The copy is a real row in the database. Its note says where it came
  from: "carried from detection 123 (rule …)". Review then never asks you about that photo again.
- A carried copy never overwrites a verdict you gave yourself. Ctrl Z takes back exactly the copies your verdict
  made.
- **The class key (1/2/3/4/9) is now saved** with the verdict. Before, it vanished when the page reloaded.

## The two rules

1. **Within a run (merge in Review, not on emit).** Two detections of the same run on the same channel are one item
   when they share at least one sample. Spans are `[start, end)`, so a span that ends where the next one starts
   does not count. Grouping is transitive: if A overlaps B and B overlaps C, then A, B and C are one item. The item
   is named after the set's first detection in queue order. It spans the whole event, from the earliest start to the
   latest end. A verdict on the item writes every detection in the set, under one audit row and one undo. Only the
   queue's own detections are grouped. Other detections of the run are reached by rule 2.
2. **Across runs (carry, and write it).** When a person writes a verdict on detection A, the verdict is carried to
   another detection B when all of these hold:
   - B is on the same channel. That means the same `recordings` row, which is one file and one channel.
   - B is in any real run. Paired surrogates are null draws and are never carried to.
   - `matching.spans_match(B, A)` is true. This is the scoreboard's §4.6 rule from `Working/discovery/matching.py`
     (IoU ≥ 0.5 and onset agreement), read from Settings. B is the candidate, as the scoreboard pairs a run's
     detections against earlier verdicts.
   - B has no adjudication row yet.

   B gets its own `adjudications` row: the same verdict, the same class label, `carried_from` = A's row, and the
   note `carried from detection A (rule reciprocal_iou_onset: IoU >= 0.50, onset within 0.25 x duration)`.

## Assumed

- **The structure fingerprint covers carried rows only.** It reads `COUNT(*), MAX(id)` over rows with
  `carried_from IS NOT NULL`, not the maximum id of every adjudication. The structure reads no adjudication at all,
  because verdicts are the overlay and are read fresh. Putting the maximum adjudication id in the fingerprint would
  rebuild every queue's structure after every new verdict, and that would undo AR's one-lookup step. A verdict that
  carries something invalidates the structure. One that carries nothing does not. Both are pinned.
- **A set is judged when any member has a row.** The event then has a verdict. A carried row can reach one member of
  a set and not another. The item shows its first judged member's verdict, class and "carried from".
- **A set is a rediscovery when any member is.** If a human span already covers any member, the whole item is not
  asked. Its score is the set's highest.
- **`seed` carries as `interesting`.** A seed is the one detection promoted to the Library (P21: seed implies
  interesting). The other detections of its set, and every carried row, are written `interesting`. Writing `seed`
  there would claim Library exemplars that do not exist. No other word is ever mapped.
- **First carry wins.** A detection that already holds a row carried from verdict X is not rewritten by a later,
  different verdict Y. Re-judging X rewrites X's own carried rows, and undo puts them back. Undoing X deletes them
  and does not re-carry from Y.
- **Carried rows do not carry on.** A carried row is not a judgement anybody made.
- **Superseded (discarded) runs are carried to.** Review never serves them, but if a run is restored its
  detections arrive already judged. Only surrogates are excluded.
- **The class label stored is the class name**, for example `burst`, not the key `2`. Keys are a keyboard binding
  and can be rebound. The label is validated as a string of at most 64 characters. A longer one is a 400, never
  truncated. The store holds what the latest write said. The Inspector always sends the class it shows, so a plain
  re-judgement keeps the class, and an undo restores it.
- **The class is stored only where the queue writes `adjudications`.** Window, annotation and member queues have no
  class column, so on those the class stays the session label it was, and the toast still says so. A class key
  pressed on a judged detection item now re-posts its verdict with the class: one audit row, undone by Ctrl Z.
- **A member's id opens its set.** A deep link or a POST naming a non-first member resolves to that member's item,
  both in the core (`item_view`, `detection_set`) and in the Inspector (the row whose `members` holds it).

## Columns added (additive, through `init_db()`)

`adjudications.carried_from INTEGER NULL` and `adjudications.class_label TEXT NULL`, plus
`idx_adjudications_carried_from`. `carried_from` is a plain INTEGER, not a REFERENCES: undo deletes carried rows
before their source, and a foreign key would turn that order into a constraint failure. A human write
(`insert_adjudication` with no `carried_from`) clears it, so a person's verdict over a carried row makes the row
theirs. Pinned: `init_db()` twice is clean.

## Files

Created:
- `Working/review/overlap.py` provides `overlap_sets`, `same_event`, `carry` / `carry_verdict`, `uncarry`,
  `undo_carry` and `carried_note`.
- `tests/test_review_carry_core.py` holds 16 tests (conda).
- `tests/test_webui_review_carry.py` holds 5 tests (venv).
- `webui/smoke_pages/zzzzzzzzzzz_review_carry.json`.

Modified:
- `Working/database/schema.py` adds the two columns and the index. The change is append-only: one new migration
  call at the end of `init_db`.
- `Working/database/adjudications.py`: `insert_adjudication` gains `class_label` and `carried_from`.
- `Working/review/queues.py`:
  - one structure entry per overlap set (`_as_overlap_sets`);
  - items carry `members`, `member_spans`, `class_label` and `carried_from_detection`;
  - counts are per set;
  - `detection_set` and `served_detections` are new;
  - the fingerprint covers carried rows;
  - `list_queues` adds `detections`.
- `Working/review/verdicts.py` is **not in the prompt's file list**. It is the one writer, so the member expansion,
  the carry after the write, the per-member audit entries and the exact undo live there, with `class_label` on
  `write_verdict` and `write_batch`.
- `Working/review/promotion.py` is **not in the list**. `_reverse_verdict` restores every member, with what each
  carried, when the verdict record lists them. This is a five-line branch.
- `webui/server/review.py`:
  - `class_label` on `VerdictBody` and `BatchBody`;
  - `carried` and `carriedIds` on the verdict and batch acks;
  - `memberBands`, `classLabel` and `carriedFrom` on the row;
  - `detections` on the queue payload, the listing, `/counts` and the item's queue.
- `webui/client/src/api/review.ts`:
  - `VerdictOpts.classLabel` becomes `class_label`;
  - `WriteAck.carried` and `carriedIds`;
  - `SrvQueue.detections`, with "N events from M detections" in the queue's subtitle and header subtitle;
  - new exports `MemberBand`, `CarryFields` and `carryOf`.

  These are append-only, except the `queueOf` subtitle line and `opt()`.
- `webui/client/src/review/Inspector.tsx`:
  - the "covers N detections · also …" line (with an InfoTip) and member bands on the context card;
  - the "carried from detection N" line and history text;
  - the toast "… carried to N other detections of the same event", with a full re-read when N > 0;
  - the class is posted and stored, and read back after a reload;
  - a member id opens its set.
- `webui/client/src/review/ClusterView.tsx` (verdict path only): the batch body carries the class.
- `webui/client/src/review/parts.tsx` is **not in the list but is shared with `edit-span`**. `ContextCard` gains an
  optional `memberBands` prop, drawn as grey bands. The change is localized to the signature and the `bands=`
  line, and it does not touch `editInExplore`.
- `webui/client/src/review/store.ts` is **not in the list**. `resend` (redo) re-sends the class. One line.
- `tests/test_webui_ar_speed.py` changes one assertion, deliberately (see Tests).
- `docs/rq_roundA/RQ5-…md` and `RQ2-…md` each get one Log line, per the rule in `docs/rq_roundA/README.md`.

## What was built

1. **Core.** `overlap_sets` is a sweep over one run and one channel. `same_event` delegates to
   `matching.spans_match`, and there is no second copy of the rule. `carry` reads candidates by index on
   `detections(run_id, start_idx)`:
   - the read is bounded by the rule (a match needs overlap, and its onset is at least `start - onset·dur/iou`);
   - it reads the shifted window too, for a legacy span-relative row;
   - it reports `created` and `updated` (with each prior) so undo can be exact.

   `uncarry(conn, adjudication_id)` deletes every row carried from the given adjudication.
2. **Queue items.** There is one item per overlap set; the item id is the first detection, with
   `members: [ids]`. `total`, `judged` and `remaining` count sets, and the header says "312 events from 340
   detections" when sets merged anything.
3. **Bridge.** `post_verdict` and `batch` carry in the core and return `carried: N`. `undo` reverses the carry in
   the core. The row and item show the members (`memberBands`) and, for a carried row, `carriedFrom`. The class
   label travels in the body and comes back as `classLabel`.
   - *Deviation:* carrying happens in the core writer (`verdicts.py`), not in the bridge. A promotion (the `seed`
     route) and every core caller then carry too, and an undo through any path, the promotion's included, finds the
     carry record in the audit entry it is reversing. Doing it in the bridge would have left `undo_last` deleting a
     source row while its carried rows stayed behind.
4. **Client.** The member bands are on the context card. "covers N detections" sits under the meta line. The toast
   reads "carried to N other detection(s) of the same event". The class is stored. No new verdict words and no new
   buttons.
5. **Scoreboard.** Nothing to change. Carried rows are `adjudications` rows, so `divergence` counts them. Pinned:
   a carried `interesting` gives the second run exactly the `precisions` a hand-written one does, and different
   ones from no verdict.

Non-detection queue kinds (window, explore-spans, sequences, family, artifact, blind test) are untouched. The set
logic is inside `_detection_structure` and the `adjudications` branch of the writer. Their test files all pass.

## Tests

**Red commit `55c0978`:**
- `tests/test_review_carry_core.py`: 15 failed. There was no `overlap` module, no `members`, no columns and no
  carry.
- `tests/test_webui_review_carry.py`: 5 failed. There were no `members`, `memberBands`, `detections`, `carried` or
  `classLabel`.

**Green, conda** (`/c/ProgramData/anaconda3/python.exe`), each file run alone:

| File | Passed |
|---|---|
| `test_review_carry_core.py` | 16 |
| `test_review_queues.py` | 48 |
| `test_review_verdicts.py` | 45 |
| `test_review_promotion.py` | 11 |
| `test_review_queue.py` | 18 |
| `test_review_queue_listed_order.py` | 10 |
| `test_review_schema.py` | 15 |
| `test_review_family_queue.py` | 11 |
| `test_review_suspected_artifact.py` | 9 |
| `test_review_window_verdicts.py` | 21 |
| `test_ar_speed_core.py` | 9 |
| `test_perf_scoring_reads.py` | 69 |
| `test_import_boundaries.py` | 4 |

Also passing: `test_band_scope.py` 18, `test_candidate_events.py` 38, `test_training_blind.py` 16.

**Green, venv** (`webui/.venv/Scripts/python.exe`):

| File | Passed |
|---|---|
| `test_webui_review_carry.py` | 5 |
| `test_webui_review.py` | 32 |
| `test_webui_review_axis.py` | 7 |
| `test_webui_ar_speed.py` | 12 (including `test_an_item_read_does_not_grow_with_the_queue`) |
| `test_webui_discovery.py -k "picked or review or verdict or send"` | 14 |

**What each new test pins (core):**
- Overlap sets are transitive. Touching spans are not overlapping.
- Sets never cross runs or channels.
- One item per set, with `members`, the event's extent, and counts per set.
- A verdict writes every member, and one undo takes it all back.
- A carry reaches exactly the detection(s) the rule matches. It does not reach another channel, a surrogate, a
  non-match, or a set member that is not the same event.
- An existing human row is never overwritten.
- A human verdict on a carried row makes it human, and the source's undo leaves it.
- Undo is exact through a re-judgement: the rewritten carried row is put back, then deleted on the next undo, and
  another source's carried row stays.
- A batch carries and its undo uncarries.
- The second run's queue no longer asks, and the item says `carried_from_detection`.
- The class label is stored, carried, served, cleared by a class-less re-judgement and restored by undo.
- A carried row invalidates the cached structure; a verdict that carries nothing does not (counted
  `queue_candidates` calls), and the cached answer equals a fresh one.
- Scoreboard parity: a carried `interesting` matches a hand-written one.
- A seed carries as interesting.
- Calling `carry_verdict` twice is idempotent.
- `init_db()` twice is clean.

**What each new test pins (bridge):**
- Rows carry `members` and `memberBands` in the trace's seconds.
- `detections` is served on the rows read, the item, the listing and `/counts`.
- A verdict returns `carried: 1`, the second run's queue drops the item, and the item shows `carriedFrom`. Undo
  clears members and the carried row.
- A batch returns `carried`.
- The class label round-trips on the row and the item. Over 64 characters is a 400.
- The route-level structure cache rebuilds on a carried row.

**Changed on purpose:** `test_webui_ar_speed.py::test_the_counts_read_is_the_queue_reads_counts`. It pinned
`judged + 1` after one verdict. On the scale fixture the verdict now also carries to a detection that is another
item of the same queue (16 → 18). The pin now counts exactly the newly judged items the ack's `carriedIds` reach,
plus the one asked about. The undo half is unchanged.

## Smoke states — `webui/smoke_pages/zzzzzzzzzzz_review_carry.json` (sorted last; it writes verdicts)

1. **`review-carry-one-item-per-event`**, at `review/queue/2/100`. It branches on
   `/api/review/queues/2?thumbs=0` for the row `{"id": "100", "members": [100]}`:
   - If item 100 is a single detection, the card shows the meta line and no `covers-line`.
   - If 100 heads an overlap set, the card shows `covers-line` ("covers N detections · also …") and the context
     trace with one grey band per member.
2. **`review-carry-class-label-is-stored`**, at `review/queue/2/101`. It presses `2` (burst). If 101 is unjudged,
   that writes `interesting` with the class; if it is judged, it re-posts its verdict with the class. The state then
   returns to 101 and **reloads**, so the session's in-memory records are gone. The Annotate card must show
   `class-2` pressed, read back from the stored `classLabel`. No `write-refused`.
3. **`review-carry-verdict-is-written-and-carried`**, at `review/queue/2/102`. It presses `u`. The write must be
   accepted (no `write-refused` or `item-error`), and the toast host is present.
   - **Check by eye on the screenshot:** the toast reads "unsure · written … · carried to N other detection(s) of
     the same event" only when another run on Mushroom CH14 found the same event as 102. Whether one did depends on
     the database; the ack's `carried` says so.
   - To find a queue that certainly carries, pick a channel with two completed Discovery runs of similar templates.
     Their detections of one event match by the scoreboard rule.

**On real data, also check:**
- whether queue 2's run 32 has overlapping detections. If 101 or 102 is a non-first member of a set, the older
  `review.json` states that expect `[data-item="101"]` or `[data-item="102"]` will show the set's first id instead.
  The page opens the set, but the `data-item` differs;
- how many rows a single verdict carries on a dense channel (see Risks).

## Gates I ran

- `tsc -b`: clean, run twice.
- `vite build`: built, after the last client change.
- The test files listed above, one at a time, with the interpreter named.

The whole pytest suite was not run, and neither was the smoke walk, as instructed.

## Open questions and risks

- **Discovery's "picked" marks.** `discovery._picked_states` (not my file) maps `queue_items` by `target_id`. A picked
  detection that is a non-first member of an overlap set therefore reads "not asked" where it should read
  waiting/judged with its set. The same applies to `explore-review-actions`' "not asked" count. The fix belongs in
  `discovery.py`: map each item's `members` to the item. I stayed out of `discovery.py` (seed-search owns it
  tonight).
- **A sliding-window detector can chain a whole run into one item.** Transitive closure of any overlap is what was
  decided, but a detector that emits densely overlapping windows (each overlapping the next) would make one huge
  item. Its bands, and a verdict, would then cover hours. If the researcher sees this on real data, the knob is a
  minimum overlap fraction in `overlap_sets`.
- **Carry volume.** One verdict on a channel with many runs of similar templates may write dozens of carried rows.
  That is the intended behaviour. The candidate read is bounded per run by index, but a channel with thousands of
  windowed runs reads once per run.
- **`Working/review/queue_state.py` (`ReviewQueue.adjudicate`)** writes adjudications without carrying. I did not
  find a live caller from the bridge's verdict routes.
- **Old audit rows** (written before this change) carry no `carried` record. Their undo still removes anything
  carried from the source when the source row goes (`uncarry`), and nothing was carried before this change.

## Commits

```
2ce738b review-carry: one Review item per overlap set; verdicts carry across runs; class label stored
55c0978 review-carry: failing tests - one item per overlap set, carried verdicts, class label
```
(plus this report as the last commit)
