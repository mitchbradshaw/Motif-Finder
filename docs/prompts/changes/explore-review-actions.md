# explore-review-actions — send a span's unjudged motifs to Review, and mark an artifact across channels

**Read first:** `CLAUDE.md`; `docs/prompts/fixup/UX-1015-common.md`; then this file. Commit prefix
`explore-review:`; every commit ends with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Test-first.
Runs BEFORE `cross-channel-overlay.md`, which reuses the action strip this prompt builds.

## Why (the researcher, 2026-10-18)

> It would be good in Explore, both normal and cross-channel, to "send unjudged motifs" in a region/span to Review.
> … Would be good to also use cross-channel to identify artifact regions, as Settings allows.

## Facts (2026-10-18)

- Explore › Signal "Take span" is real (`explore/SpanActions.tsx:44`, `POST /api/annotations/seed`,
  `explore_routes.py:221`: writes ONE `seed` annotation; verdict hard-coded). The drawer's "Send selected to Review"
  (`explore/SignalDrawer.tsx:161`) and Cross-channel's "Review this window on all channels"
  (`explore/CrossChannelPage.tsx:197`) are **demo-only** (`recordDemoWrite`).
- Queues take `filters.detection_ids` (`Working/review/queues.py:211`; `find_open_queue` :224, `create_queue` :118,
  `extend_queue` :269). Discovery's browser appends to ONE picked queue per session ("… · picked from Discovery",
  `discovery.py:4056 send_remainder_to_review`, `sendDetectionsToReview` in `api.ts`, fixup-AL) — the pattern to copy.
- The window query is `corpus.spans` (`corpus.py:462`; `GET /api/channels/{id}/spans?t0&t1`); "unjudged" is
  `NOT EXISTS (SELECT 1 FROM adjudications ad WHERE ad.detection_id = d.id)` (`queries.py:644`).
- An artifact region is an `annotations` row with verdict `artifact` (no region table; `schema.py:74`), written only
  by Review (`Inspector.tsx:115`, `ClusterView.tsx:182`, `BlindTest.tsx:32`). Settings only sets the cross-channel
  artifact thresholds (`AnalysisDefaultsPage.tsx:89`); "excluded spans" per channel exist in Settings › Channels
  (find the route and reuse its channel picker pattern).

## Decided with the researcher (grilling, 2026-10-18)

- **Queue:** one picked queue per Explore session, "… · picked from Explore", appended to from Signal and from
  Cross-channel; the toast says how many were added and how many were already judged (and so not added).
- **Artifact from Cross-channel:** writes one `artifact` annotation **per selected channel** over the window; the
  channel picker defaults to every channel of the recording, works like the excluded-spans picker in Settings, and
  the reference channel is pre-ticked. Never a sixth verdict word.
- **Signal page too:** the same "send unjudged motifs in this span to Review" on a selected span of a single signal.
- The action strip (the small row of buttons that appears after a selection on Signal) is the shared component:
  Zoom · Send unjudged to Review · Mark artifact (channels…) · Open in Analyse · Take span (existing). The overlay
  prompt adds "open in Signal" to it.

## The work

1. **Bridge:** `POST /api/explore/span-review {recording_ids: [..], t0_s, t1_s, note?}` → finds the detections
   whose span intersects `[t0, t1]` on those channels (`corpus.spans`' SQL with the shifts it already applies,
   excluding surrogate and window-part runs as it does) that have no adjudication, then `find_open_queue` /
   `create_queue(source_kind="explore-picked")` / `extend_queue` exactly as `send_remainder_to_review` does, and
   returns `{queue_id, added, already_judged, total, message}`. `POST /api/explore/artifact {recording_ids, t0_s,
   t1_s, note?}` → one annotation per channel (`queries.insert_annotation`, verdict `artifact`, source
   `explore-cross-channel`), returns the ids; refuses on a held-out recording and on an empty window.
2. **Client:** `explore/SpanActions.tsx` becomes the shared strip with the new buttons (muted blue; the primary
   stays what it is); Signal wires it to the selection; Cross-channel replaces its demo button with the strip over
   its window, with the channel picker popover for the artifact action; the drawer's demo "Send selected" goes
   live through the same route with the selected ids. Toasts with "Open Review".
3. After a send, the Signal page re-reads its spans so judged/queued bands update (the picked state is served by the
   bridge, as Discovery's browser does).

## Files

Yours: `webui/server/explore_routes.py`, `Working/review/queues.py` only if a helper is missing (say so),
`webui/client/src/explore/SpanActions.tsx`, `SignalPage.tsx`, `SignalDrawer.tsx`, `CrossChannelPage.tsx` (the
action row only — the overlay prompt owns the plot), `webui/client/src/api/explore.ts`, `tests/`.

## Method and gate

- Tests (venv, `tests/test_webui_explore*.py` or new): the span-review route returns exactly the unjudged
  detections intersecting the window on the named channels, appends on a second call, and reports
  `already_judged`; the artifact route writes one row per channel with verdict `artifact` and nothing else; held-out
  refused; a window with no detections returns `added: 0` and a sentence, not an error.
- `tsc -b`, `vite build`. Smoke in `webui/smoke_pages/zzzzzzzzzzz_explore_review.json` (sorted last: it writes):
  select a span on Signal, the strip shows the new buttons, Send shows the toast; on Cross-channel, Mark artifact
  opens the channel picker.
- Run your files plus `tests/test_webui_review*.py`, `tests/test_webui_corpus.py`, `tests/test_import_boundaries.py`.

## Report

`docs/prompts/changes/reports/explore-review-report.md`: **Assumed**; the two routes' contracts; tests; smoke
states; what is left.
