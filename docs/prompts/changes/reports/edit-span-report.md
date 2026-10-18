# edit-span — report

WORKTREE: C:\Users\mmebr\Documents\CNN\.claude\worktrees\agent-a120ecc869c11ab52
BRANCH: worktree-agent-a120ecc869c11ab52

## 1. Assumed

- **The route key is `{ref}`: a detection id, or `m-<member id>`.** The prompt names `{detection_id}`, but a Library
  family queue's items are members and carry no detection id (their `target_id` is the member id). Building the
  URL from `entry.id` there would have opened, and saved against, an unrelated detection with the same number.
  `m-<id>` covers them, and it also makes the Family page's existing "Redraw in Explore"
  (`explore/span-edit/m-<id>?from=library/family/<F>`) work, without touching `FamilyPage.tsx`.
- **A member edit writes an annotation too.** `revisions.add_revision` refuses a human revision without an
  `annotation_id` (a redrawn extent is a person's claim and the annotation is the claim), so the member path is:
  annotation (source `review-span-edit`, the item's verdict or `seed`) → human revision pointing at it, in one
  transaction.
- **The item's verdict** is read from the store, not from the queue: a member's Review verdict
  (`family_queue.member_verdicts`) first, then the adjudication on its detection. A verdict word that is not an
  annotation verdict falls back to `seed` and the note says so.
- **Detection → member** link: a `motif_member_revision` naming the detection (newest member wins), else a member of
  an entry whose `motif_entry.detection_id` is this detection, on the same channel and overlapping it. No change to
  `Working/library/revisions.py` was needed.
- **A member with no revision rows** (written before revisions existed): its own `motif_member` span is first
  written as a machine rev 1, so the matcher keeps comparing against what the machine found. Reported back as
  `seeded_rev1`.
- **Context** is ±2 lengths of the span the item shows now (the member's current revision, else the detection),
  computed once at load; the handles clamp to that window, the fields do not (a span past the window is drawn
  clipped, with a callout).
- **Units without a detection or member** (human span, sequence): the Edit-span button is disabled with the reason
  "a <unit> has no detection or Library member behind it to redraw". Windows already hide it.
- `stale_edges` (revisions.py says the extent-edit route owns that call) is returned and named in the save toast;
  nothing recomputes the distances.

## 2. In plain words

Pressing **Edit span in Explore** (or `E`) in Review now opens a real editor: the channel is drawn around the event,
with the machine's span in grey and yours in blue. Drag either edge, or type the start and end in seconds; the two
stay in step. Saving never changes what the detector found. If the event is in the Library, the correction becomes
a new version of that member's span (the old versions are kept); otherwise it is saved as your own labelled span.
Save or Cancel takes you back to the same Review item.

## 3. Files

- `webui/server/explore_routes.py` — modified, **append-only**: one contiguous block at the end with its own header
  comment and its own imports (`os`, `revisions`, `family_queue`, `decimate`), so the header is untouched for
  `explore-review-actions`.
- `webui/client/src/explore/SpanEditPage.tsx` — rewritten (live).
- `webui/client/src/api/explore.ts` — shared: `getSpanEdit` demo replaced by the live call, `saveSpanEdit` and three
  types appended; one appended import line (`ApiError`); the removed fixture's names taken out of the import and
  re-export lists (`spanEditDemo`, `SpanEditDemo`, `Revision`, `SnapRule`), and the header comment's "still demo"
  line updated.
- `webui/client/src/fixtures/explore.ts` — the span-edit fixture block removed.
- `webui/client/src/review/parts.tsx` — `editInExplore` builds the new URL; a new `spanEditRef(d)`; the button gets
  `disabled`/`disabledReason` (one line). Nothing else in `review/`.
- `webui/smoke_pages/explore.json` — the nine demo `explore.span-edit` states (all on the `m-1846` fixture) removed.
- `webui/smoke_pages/zzzzzzzzzzz_edit_span.json` — new.
- `tests/test_webui_span_edit.py` — new.

## 4. What was built

1. **GET `/api/explore/span-edit/{ref}`** →
   `{recording_id, channel, source_file, fs, n_samples, unit, detection_id, detection: {start_idx, end_idx} | null,
   member: {ref, current: {start_idx, end_idx, revision_no}} | null, verdict | null, context_trace}`.
   `context_trace` is the envelope over ±2 lengths, `t` in absolute seconds beside `v` in mV, the shape Review's
   context card gets (`decimate.envelope` + `corpus.display_channel`). It does not import `review._trace_env`,
   because AR is rewriting `review.py`. 404 for an unknown ref, 423 for the held-out recording (the same `_rec`
   refusal as every Explore read).
2. **POST `/api/explore/span-edit/{ref}` `{start_idx, end_idx, note}`**. The save rule is under §1 and the module
   comment. It refuses with 422: shorter than two samples (also inverted), outside the channel, a member span not
   overlapping rev 1 (`add_revision`'s `ValueError`, rolled back so nothing is written). It refuses with 423 on the
   held-out recording, before anything is written.
3. **Client**: `SpanEditPage` reads the live route. It draws the trace, the original extent (dashed grey) and yours
   (blue), with two draggable handles (arrow keys nudge one sample, Shift ten). The start and end fields are in
   seconds to three decimals, with ±1-sample steppers; typing a valid number updates the plot live, and `#n` takes
   a sample index. It shows the deltas, an optional note, and a "What saving writes" sentence that differs for a
   member and a detection. Save, Cancel, Esc and Back return to `review/queue/<queue>/<item>`. A non-Review `from`
   (the Family page's) is returned to as given. 404 shows an empty state, 423 the LockedCard, and anything else the
   ErrorCard. A failed save shows a red callout with the server's sentence.
4. **Review re-reads after save**: by remount. Returning to `review/queue/<q>/<item>` mounts the Review workspace
   afresh, and the item is fetched again. **Not done, and needs a change in Review's core (described, not built):**
   a Library family queue's item is drawn from `motif_member.start_idx/end_idx`
   (`Working/review/artifact_queue._members`, used by `family_queue.resolve_items`), not from the current revision.
   So Review's context card still draws the member's original span after a revision. The hook is to give
   `resolve_items` the current revision's span for display, while the verdict key stays on the member span
   (`_review_rows` matches verdict annotations on `(recording, start, end)`, so moving the key would un-judge
   members). For a plain detection the card correctly keeps drawing the detection; the corrected span is a separate
   human row.
5. Deviation: the snap-to rules, overview strip and revision list of the demo page were dropped. Nothing computes
   snap candidates, and the family page already lists revisions (`_revisions_for` reads the table, so a new
   revision shows at once).

## 5. Tests

- **Red**: `36fcb96`. webui/.venv python: 13 failed. Every route answered
  `404 "no such API route: GET /api/explore/span-edit/1"`.
- **Green** (webui/.venv python): `tests/test_webui_span_edit.py` 13 passed.
- What the new tests pin down:
  - GET on a plain detection: no member, its verdict, and a context window of exactly ±2 lengths.
  - GET on a member's detection: the member and its current revision.
  - GET by `m-<id>`: the same member.
  - Unknown refs give 404; held-out gives 423.
  - POST on a member: revision 2 becomes current, rev 1 is kept, the human revision carries an `annotation_id` and
    no `detection_id`, and the annotation is `seed` / `review-span-edit` with the note. **The detections table is
    identical, every column of every row, before and after.** GET then reads rev 2.
  - POST on a plain detection: an annotation with verdict `interesting` and source `review-span-edit`. **The
    detections table is identical**, and no revision is written.
  - An unjudged detection gives `seed`.
  - Four bad spans are refused with 422 and write nothing.
  - Held-out POST gives 423 and writes nothing.
  - A member span that does not overlap rev 1 gives 422, with no annotation and no revision written (the
    transaction is rolled back).

## 6. Smoke states — `webui/smoke_pages/zzzzzzzzzzz_edit_span.json` (sorted last: the third state writes)

All three open `review/queue/2/101`, the live detection item `review.json` already uses.

1. **E on a Review item opens the live editor.** Press `e`. It must show the span-edit page with the trace
   (`span-edit-trace`), the original and your extent, both grips, the start and end fields, and the saving sentence.
   Save is disabled (nothing changed). The hash must contain `explore/span-edit/`, `from=review`, `queue=2` and
   `item=101`. There is no not-found card and no save-failed callout.
2. **Cancel returns to the same item without writing.** Click the button, step the end up one sample, then Cancel.
   The inspector shows item 101 and the hash is `review/queue/2/101`.
3. **Change the end field, Save, land back on the same item.** Step the end up three samples; Save becomes enabled;
   click it. The inspector shows item 101 and the hash is `review/queue/2/101`. This writes one `annotations` row
   (source `review-span-edit`). If item 101 is unjudged its verdict is `seed`, so the span then also appears in the
   Explore spans queue.

For the manager on real data: open a Library family queue item (unit `member`) and check that the button opens
`m-<id>`. Also check the Family page's "Redraw in Explore". After a save, the family page's revision list should
show the new revision.

## 7. Gates run

- `tsc -b`: clean. `vite build`: built.
- webui/.venv python: `tests/test_webui_span_edit.py` 13 passed. `tests/test_webui_review.py` together with
  `test_webui_span_edit.py`: 45 passed. `tests/test_webui_review_axis.py` + `tests/test_webui_library.py`: 66 passed,
  3 xpassed. `tests/test_webui_routes.py`: 12 passed.
- Conda python: `tests/test_import_boundaries.py` 4 passed.

## 8. Open questions and risks

- **A `seed` annotation from an unjudged span edit enters the Explore spans queue.** `_resolve_spans` takes every
  `verdict = 'seed'` annotation, whatever its source. That follows the prompt's "or `seed` if it has none", but it
  may surprise; a dedicated source filter there would be a Review-core change.
- **Review's context card does not draw a member's revised span.** See §4 item 4; this needs a `family_queue` /
  `artifact_queue` display change. AR or `review-carry-and-overlap` should own it.
- `review-carry-and-overlap` will make an item cover a SET of detections (`members: [ids]`). `spanEditRef` then
  needs to pick one (the item's representative detection); the route takes a single ref.
- `shell/pages.ts` still lists `explore/span-edit/m-1846` as the page's canonical route. It is not my file, and
  under the live route that id is a 404 not-found card.
- The `E` key on a human-span or sequence item does nothing silently (the button says why). `Inspector.tsx` is AR's,
  so the `say(...)` was not added there.
- Stale family distances are reported in the toast but not marked anywhere persistent (`motif_edge` has no
  staleness column).

## 9. Commits

See `git log --oneline main..HEAD` (the red test commit, the implementation, this report).
