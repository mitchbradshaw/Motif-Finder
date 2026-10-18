# edit-span — Review's "Edit span in Explore" opens a live span editor; saving writes a revision or an annotation

**Read first:** `CLAUDE.md`; `docs/prompts/fixup/UX-1015-common.md`; then this file. Commit prefix `edit-span:`; every
commit ends with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Test-first.

## Why (the researcher, 2026-10-18)

> Review → "edit span in Explore" functionality not implemented.

## Facts (2026-10-18)

- The button is `review/parts.tsx:105` (`ContextCard`, when `canEdit`), key `E` wired in `review/Inspector.tsx:207`
  and `review/ClusterView.tsx:233`. The handler (`parts.tsx:117`) navigates to
  `explore/span-edit/<detectionId ?? id>?from=review&queue=…&item=…`.
- The destination `explore/SpanEditPage.tsx:24` calls `getSpanEdit(memberId)`, which is
  `demo(spanEditDemo(memberId))` (`api/explore.ts:225`) and knows only `m-1846` (`fixtures/explore.ts:288`); any real
  id lands on "No span … in the demo data" (`:33`); saving (`:83-95`) is an in-memory `recordDemoWrite`. The page
  reads `queue`, `candidate`, `of`, `return` and ignores `from`/`queue`/`item`, so "back" goes to plain `review`.
  Its numeric start/end fields with steppers are a pattern worth keeping.
- The core has `Working/library/revisions.py:91 add_revision`, `current_revision`, `revision_list` — no bridge route
  (`library.py:1907 _revisions_for` is read-only, used by the family view).
- Detections are machine-only (CLAUDE.md rule 5): a human cannot overwrite a detection's span.

## Decided with the researcher (grilling, 2026-10-18)

- Saving writes **(a) a revision of the Library member's span** when the item is a member (history kept, the
  current revision is what the family page and the Library read); **(b) a human annotation with the corrected span
  and the item's verdict** when it is a plain detection. Never the detection row.
- The editor is live: it draws the item's channel around the span (the Review item's context, ±2 window lengths),
  with draggable handles AND the numeric start/end fields (seconds to three decimals, live-updating the plot, as the
  Explore span plot will also get), Save, Cancel, and "back to Review" to the same queue and item.

## The work

1. **Bridge:** `GET /api/explore/span-edit/{detection_id}` → `{recording_id, channel, fs, detection: {start_idx,
   end_idx}, member: {ref, current: {start_idx, end_idx, revision_no}} | null, verdict | null, context_trace (the
   envelope over ±2 lengths, as Review's context card gets it)}`; `POST /api/explore/span-edit/{detection_id}
   {start_idx, end_idx, note}` → for a member: `revisions.add_revision` and returns the new revision; otherwise:
   inserts the annotation (`Working/database/queries.insert_annotation`, source `review-span-edit`, the item's
   verdict, or **`interesting` if it has none** — the researcher, 2026-10-19: an unjudged correction saves
   `interesting`, not `seed`) and returns it. Refuses a span outside the channel, shorter than two samples,
   or on a held-out recording.
2. **Client:** `explore/SpanEditPage.tsx` reads the live route (delete the demo path and the fixture entry), draws
   the trace with the band and handles (reuse `SpanView`'s band and the `TimeRange` chip pattern, or the existing
   steppers), keeps the numeric fields in sync both ways, and returns to `review/queue/<queue>/<item>` on save or
   cancel using `from`/`queue`/`item`. The family page's revision list (`_revisions_for`) shows the new revision at
   once (it already reads the table).
3. Review's item re-reads after save (AR's counts path or `version` bump) so the context card draws the revised
   span for a member.

## Files

Yours: `webui/server/explore_routes.py` (the two routes), `Working/library/revisions.py` only if a lookup by
detection id is missing (say so), `webui/client/src/explore/SpanEditPage.tsx`, `webui/client/src/api/explore.ts`,
`webui/client/src/fixtures/explore.ts` (remove the span-edit fixture), `webui/client/src/review/parts.tsx` (the
URL it builds), `tests/`.

## Method and gate

- Tests (venv): GET returns the member when the detection is one, null otherwise; POST on a member writes a
  revision and `current_revision` changes while the detection row is byte-identical before and after; POST on a
  plain detection writes an annotation with the verdict and never touches `detections`; refusals as listed.
- `tsc -b`, `vite build`. Smoke in `webui/smoke_pages/zzzzzzzzzzz_edit_span.json` (sorted last: it writes): open an
  item, press E, the editor shows the trace and fields; change the end field, Save, land back on the same item.
- Run your files plus `tests/test_webui_review*.py`, `tests/test_webui_library.py`, `tests/test_import_boundaries.py`.

## Stop and report if

a Review item has no detection id (window queues): the button is then hidden with a reason, say so.

## Report

`docs/prompts/changes/reports/edit-span-report.md`: **Assumed**; the save rule; tests and interpreters; smoke
states; what is left.
