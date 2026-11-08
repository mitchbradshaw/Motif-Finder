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
shape and reopening Explore read that current extent. Older linked member revisions
are also recognised as superseded history, even when an old app left their annotation
rows live. Edited overlap sets remain
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
  overlap-set, family re-review, legacy history and catalogue replacement: 24 passed.
- TypeScript checking and production Vite build passed against the main checkout's
  existing dependencies. No dependency installation was required.
- Synthetic sandbox Playwright: detection edited twice (including a shrink), then
  Library member edited; all three returned to Review with the saved shape, selected
  interesting verdict and current bounds on reopening Explore. Zero page/console
  errors. Screenshot inspected; tests never wrote research labels.
- Local evidence is under ignored `DATA/derived/review_speed/`: `span_edit_*` logs,
  `span_edit_browser_result.json` and `span_roundtrip_*.png`.
- The repository-wide run was cancelled at the author's explicit request after
  the targeted checks passed. It is not reported as a full-suite pass.

Research/core focused checks: 21 passed (catalogue, event hierarchy, CNN continuation,
Library verdicts and import boundaries). The initial broad run found the thesis
worktree lacked `Plots/drop_motifs9_fig2a/run_summary.json`; the unchanged detector
null test passes after copying the actual existing main-checkout metadata (SHA256
`73cd18f84eedfb010eca9b1687395817f3fb0f2ed7628e26e52c5a6c35443d98`).
The isolated end-to-end tests pass (2). Broad runs were stopped after numerical-library
thread contention; the subsequent two-worker run was cancelled at the author's
request. Targeted checks, build and synthetic browser verification are the final
validation scope; no clean repository-wide result is claimed.

Production restarted on port 8765 with `--no-warmup`. Health is OK, no running
analysis jobs, annotation/adjudication/review-audit row hashes match before restart,
and `PRAGMA foreign_key_check` returns no errors. Queue 47 remains 0/850 answered.
The 30 unrelated local main-checkout edits have identical blobs to before the merge;
they were preserved outside the thesis commits. The earlier staged wave-1 files were
identical to the incoming branch and are now included by that history.

The user explicitly authorised merging the chat's thesis/code/results/figure work
to main and pushing. Raw DBs, arrays, private review keys and upload archives remain
local. No thesis PDF was rebuilt.
