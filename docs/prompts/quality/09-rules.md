# tq-rules — server-side rules written once: the legacy span shift, the Send-N count, the queue listing

Package id for commits: `tq-rules`. Read `docs/prompts/quality/00-common.md` first. The tq-worker package (merged
before you start) moved the worker pool out of `webui/server/corpus.py`.

These are core and bridge reads of the researcher's detections. A wrong shift misplaces every legacy detection by its
span start. Correctness first, then fewer copies.

## The findings

1. **A third SQL copy of the legacy-shift rule.**
   - `webui/server/library.py:~1438` `_library_detections` restates `Working/discovery/spans.py:~25 absolute_bounds`
     as SQL. `webui/server/corpus.py:~882` and `webui/server/discovery.py:~1101` do the same.
   - The rule: a spanned run's legacy row whose start lies below its run's `span_start` is shifted. CLAUDE.md memory:
     detections were written span-relative before 2026-09-21.
   - `_library_detections` also hand-rolls a numpy interval merge beside `Working.database.queries.merge_intervals`.
     Touching spans merge in both today.
   - **Remedy:** one SQL fragment builder, e.g. `spans.absolute_sql(d_alias, r_alias) -> (a_expr, b_expr)`, in
     `Working/discovery/spans.py`, used by all three, with a test that it agrees with `absolute_bounds` on legacy
     and non-legacy rows. Add a numpy `merge_intervals` variant beside the existing one if the library path needs
     arrays, and leave `merge_intervals` itself untouched (many callers).
2. **`unwritten_counts` copies `queue_counts`' detection branch.** In `Working/review/queues.py:~448-464`, lines are
   copied from `~437-442`: `_cached_structure`, `_structure_views(...)["served_members"]`,
   `SELECT detection_id FROM adjudications`, `_set_judged`.
   - **Remedy:** a `_detection_counts(conn, q, exclude, cache_key=None)` called by both.
   - Report separately, and do NOT change it: both "Send N" paths pass no held-out exclusion while Review's own
     listing does. Say whether the counts can therefore differ.
3. **The queue listing strips `filters` by hand in the route.** `webui/server/review.py:~751-758` strips
   `detection_ids` itself, while `_queue_payload` already has a `filters=` switch whose docstring (around line 286)
   now falsely says "the queue listing still carries it".
   - **Remedy:** make `filters` a mode inside `_queue_payload` (`'full' | 'summary' | 'none'`, or whatever the callers
     actually need), so the route asks for what it wants.

## Behaviour that must not change

Every detection's absolute position, every count ("Send N unjudged", queue totals, judged), and every queue
listing's fields, for legacy span-relative rows, absolute rows, unspanned runs and surrogate runs. The response
shapes stay identical.

## Files

`Working/discovery/spans.py`, `Working/review/queues.py`, `webui/server/library.py` (`_library_detections` only),
`webui/server/corpus.py` (the span read only), `webui/server/discovery.py` (the one span SQL only),
`webui/server/review.py` (the listing route and `_queue_payload` only).

Tests: `tests/test_span_plot_absolute.py`, `tests/test_legacy_detections_migration.py`, `tests/test_review_queues.py`,
`tests/test_review_queue.py`, `tests/test_review_queue_listed_order.py`, `tests/test_review_carry_core.py`,
`tests/test_webui_library.py`, `tests/test_webui_review.py`, `tests/test_webui_review_carry.py`,
`tests/test_webui_routes.py` (three known coverage-route failures on main), `tests/test_webui_explore_review.py`,
`tests/test_site_map_counts.py`, `tests/test_webui_span_plot.py`, `tests/test_database.py`, plus any test file that
imports `Working.discovery.spans` or `Working.review.queues`. Record the failure set first. These are core modules:
run every test file that imports them.

Smoke units for the manager: `review`, `library`, `zzzzzzzzzzz_span_plot`, `zzzzzzzzzzz_review_carry`,
`zzzzzzzzzzz_a1_site_runs`.
