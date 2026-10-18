# review-carry-and-overlap — one judgement per event: overlaps merge in Review, verdicts carry across runs

**Read first:** `CLAUDE.md`; `docs/prompts/fixup/UX-1015-common.md`; then this file. You run alone: open choices go
under **Assumed**. Commit prefix `review-carry:`; every commit ends with
`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Test-first.

## Why (the researcher, 2026-10-18)

> Overlapping / joined detections: only the two threshold blocks merge gaps today; other detectors emit overlapping
> spans and Review shows the same event twice. … If I have reviewed an event once, the same event will earn the same
> review later. It is not writing anything that I haven't adjudicated as a human.

Two faces of one problem: within a run, overlapping windows of one detector are shown as two items; across runs,
the same event found twice is asked twice. The researcher wants to judge each event once.

## Decided with the researcher (grilling, 2026-10-18)

- **Within a run: merge in Review, not on emit.** The detector's output stays as emitted (honest, reproducible);
  Review shows an overlapping SET of a run's detections as ONE item, and the verdict given to it is written to every
  detection in the set. The set is the transitive closure of pairwise overlap (any overlap in samples) among
  detections of the same run on the same channel.
- **Across runs: carry automatically, and write it.** When a human verdict is written on detection A, every
  OTHER detection (any run, same channel) that is "the same event" by the scoreboard's existing matching rule
  (reciprocal overlap on the onset — `Working/discovery/matching.py`, the rule `queries`/the scoreboard already
  read, never a second copy) receives the same verdict as a written adjudication row with a note
  `carried from detection <A> (rule <name>)`. Review then never asks about it ("picked · not asked — a human
  verdict already covers it" is the existing wording). The five verdict words are fixed; nothing new is invented.
  This is the R7 item of the older backlog, closed.
- **R3 too:** a class label (1/2/3/4/9) given in Review is stored today nowhere — find where the class is captured
  (`review/Inspector.tsx`, the verdict POST body) and store it on the adjudication row (an additive column
  `class_label` through `init_db()`), shown on the row and in the history.
- An undo of the human verdict undoes the carried rows it created (they reference their source).

## What the code has today (facts)

- `webui/server/review.py:779 post_verdict`, `:796 batch`, `:813 undo`; `Working/review/queues.py` builds the
  items (`queue_items`, `queue_candidates` in `Working/database/queries.py:555`, with the NOT EXISTS adjudication
  test at `:644`); the browser's "not asked" state exists (`discovery/RunsPage.tsx` `det.picked === 'not-asked'`).
- `Working/discovery/matching.py` holds the span matching used by the scoreboard (bisected onsets after the
  2026-10-18 perf round); `REVIEWED_CRITERION` is the rule text the client shows.
- AR (the speed pass, merged or about to be) caches each queue's structure under a fingerprint of its inputs:
  anything you add that changes which items a queue serves (merged sets, carried rows) must be in that fingerprint
  — read `Working/review/queues.py` on main before you start and add your inputs to it, with a test that proves a
  carried row invalidates the structure.

## The work

1. **Core:** `Working/review/overlap.py` (new): `overlap_sets(detections) -> list[set[int]]` for one run on one
   channel; `same_event(a, b, rule)` delegating to `matching`; `carry_verdict(conn, adjudication_id) -> list[int]`
   that finds the matching unjudged detections and writes the carried rows (same verdict, same class label, note,
   `carried_from`), skipping any detection that already has a human row; `uncarry(conn, adjudication_id)`.
   Additive columns on `adjudications`: `carried_from INTEGER NULL`, `class_label TEXT NULL` (idempotent
   `init_db()` migration).
2. **Queue items:** a detection queue serves one item per overlap set (the item id is the set's first detection
   id; the item carries `members: [ids]`); `post_verdict` on it writes every member; counts and `total` count sets,
   not detections — say so in the queue header ("312 events from 340 detections"). The structure fingerprint
   includes the carried-row count and the max adjudication id.
3. **Bridge:** `post_verdict` and `batch` call `carry_verdict` after the human write and return `carried: N`;
   `undo` calls `uncarry`; the item payload shows "also covers detections …" and, for a carried row, "carried
   from …" in the history; the class label travels in the verdict body and comes back on the row.
4. **Client:** the Inspector shows the set's members as small bands on the context card and the "covers N
   detections" line; the toast after a verdict says "carried to N other detections" when N > 0; the class label is
   stored, not only displayed. No new verdict words, no new buttons beyond what exists.
5. **Scoreboard:** carried rows count as human verdicts (that is the point); add a test that a carried
   `interesting` raises the second run's precision exactly as a hand-written one would.

## Files

Yours: `Working/review/overlap.py` (new), `Working/review/queues.py`, `Working/database/queries.py` (the set-aware
candidate read), `Working/database/schema.py` (two additive columns), `Working/database/adjudications.py`,
`webui/server/review.py`, `webui/client/src/review/Inspector.tsx`, `ClusterView.tsx` (verdict path only),
`webui/client/src/api/review.ts`, `tests/`. Do not touch the detectors or `matching.py`'s rule.

## Method and gate

- Core tests (conda): overlap sets are transitive and per run/channel; a carried verdict reaches exactly the
  detections the scoreboard rule matches and no other; an existing human row is never overwritten; undo removes
  only the rows it created; `init_db()` twice is clean.
- Bridge tests (venv, `tests/test_webui_review*.py`): a queue over a run with overlapping windows serves one item
  per set with `members`; a verdict writes every member; `carried` is returned and the second run's queue no
  longer asks; the class label round-trips; the structure cache invalidates on a carried row.
- `tsc -b`, `vite build`. Smoke in `webui/smoke_pages/zzzzzzzzzzz_review_carry.json` (sorted last: it writes
  verdicts on the sandbox): an item shows "covers N detections"; after a verdict the toast says "carried to".
- Run your files plus all `tests/test_review_*.py`, `tests/test_webui_review*.py`,
  `tests/test_perf_scoring_reads.py`, `tests/test_import_boundaries.py`.

## Stop and report if

the overlap-set item breaks a queue kind that is not detection-based (window, explore-spans, family): leave those
kinds as they are and say so; or carrying would require a verdict word that does not exist.

## Report

`docs/prompts/changes/reports/review-carry-report.md`: **Assumed**; the two rules in plain words; the columns added;
tests and interpreters; smoke states; what is left.
