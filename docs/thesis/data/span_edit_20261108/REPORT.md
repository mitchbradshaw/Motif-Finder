# Review boundary replacement — 8 November 2026

Request: after editing an event's boundary in Explore, return to the same Review
item showing the saved extent, automatically accepted as interesting, with one
current event rather than original and edited overlapping entries.

## Cause and implementation

Plain detections previously gained an unlinked human annotation. Review continued
to read the immutable detection extent; repeated edits produced further live
annotations. The client also retained prefetched details after the Explore save.
Library revisions already stored edited geometry, but cached Review details and
older verdict annotations could conceal it.

Added an idempotent `review_span_edits` link table through `init_db`. A detection
has one current human annotation; a later redraw soft-supersedes the earlier edit.
The machine detection stays unchanged and Library members keep their revision
history. Saving explicitly accepts the event as interesting. Queue rows, context,
shape and reopening Explore read that current extent. Edited overlap sets remain
served after a cold resolver rebuild. The save invalidates client geometry, stale
session verdicts and counts. Family re-review reuses the current annotation.

Catalogue compilation uses edited extents, retains source evidence, and keeps
distinct redraws separate even when recovery tails overlap. Read-only historical
snapshots without the additive table remain readable. Old unlinked plain-detection
edits cannot be assigned automatically by spatial guessing.

## Evidence

- The first regression commit reproduced three failures: original Review geometry,
  rejection retained after redraw, and zero answered items after an unjudged edit.
- Initial API/Review/Explore/startup run: 74 passed. Final span-edit run including
  overlap-set, family re-review and catalogue replacement: 23 passed.
- TypeScript checking and production Vite build passed against the main checkout's
  existing dependencies. No dependency installation was required.
- Synthetic sandbox Playwright: detection edited twice (including a shrink), then
  Library member edited; all three returned to Review with the saved shape, selected
  interesting verdict and current bounds on reopening Explore. Zero page/console
  errors. Screenshot inspected; tests never wrote research labels.
- Local evidence is under ignored `DATA/derived/review_speed/`: `span_edit_*` logs,
  `span_edit_browser_result.json` and `span_roundtrip_*.png`.
- Full-suite and final research checks are recorded below after completion.

The user explicitly authorised merging the chat's thesis/code/results/figure work
to main and pushing. Raw DBs, arrays, private review keys and upload archives remain
local. No thesis PDF was rebuilt.
