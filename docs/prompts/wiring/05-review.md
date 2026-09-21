# Prompt 05 — Review: queues, verdicts and promotion on real data (run ALONE, after 03 and 04)

You are working in `C:\Users\mmebr\Documents\CNN` (Windows; Bash tool = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md`, `docs/WIRING_PLAN.md` (D5 binds you: a verdict on a
machine detection writes `adjudications`, on a human span writes `annotations`, promotion writes the motif
tables), `docs/LIBRARY_STORAGE.md`, `docs/BLOCK_INTEGRATION.md`, the reports of Prompts 01–04 and their
`requests/*-to-05.md` files, `Working/review/queue_state.py` (moved out of the Panel tree by Prompt 00, with its
18 tests), `Working/database/{adjudications,queries}.py`, `prototyping/UI_FUNCTIONAL_SPEC.md` §10 (Review) and
§12 P6, P20, P21, `webui/pages/inventory/review.md`, `webui/client/src/review/`, `src/api/review.ts`,
`src/fixtures/review.ts`. Nobody runs in parallel with you. Commit prefix `wire-review:`. Push `main` at the end.
Ports 8765 / 5173.

## Goal

Review runs on real queues and writes real verdicts:
- **Queue kinds** (spec §10.1, P20 — one source per queue): detections of a run/template application (from
  Discovery), seeded-search matches, Explore spans taken for review, training/verification windows (from
  Training/Models — a window-verdict target keyed by window-set id + window index; fog A13: implement it as an
  additive `window_verdicts` table), and Library's `extract events` queue for sequences flagged
  `needs_extraction` (Prompt 03). A `review_queues` table (additive) with per-queue blinding, verdict options,
  cap, source kind and source id; the Jobs page's queue group and the header's "N need you" read it.
- **Verdicts** write through `writes.write_human` only: S/I/N/A/U as in the vocabulary, tags and notes; undo
  (Ctrl-Z) reverses the last write; blind queues hide the machine score until the verdict is given; batch actions
  with confirmation; the queue's progress and pace are real.
- **Promotion** (P21): S on a candidate writes the verdict and creates/updates the Library entry through Prompt
  03's importer path (identity hash → existing entry gets a member; new hash → new entry), with revisions; Enter
  confirms, Ctrl-Z removes both.
- **Cluster review** (review.cluster): a Grouping's clusters against human verdicts on real data; accept/reject a
  cluster writes verdicts for its members with one audit row.
- **Extract events** queue: the inspector shows the sequence with its span; the reviewer marks individual events
  (span edits write a new singular annotation linked to the parent sequence, `parent_annotation_id`); the sequence
  loses `needs_extraction` when the reviewer says it is complete.

## Work (test-first per seam)

1. **Core** `Working/review/`: `queues.py` (create from each source kind, next/skip/back, blinding, caps),
   `verdicts.py` (write, undo, batch; rule 5), `promotion.py` (calls the Library importer's identity path),
   `window_verdicts.py`. Migrations additive.
2. **Bridge** `webui/server/review.py`: queues list/create/detail, item (with the Signal payload through
   `serialize.py` and neighbours), verdict/undo/batch/skip, promote, cluster accept/reject, extract-events writes;
   header counts route.
3. **Client**: the 6 `demo(FIXTURE)` reads in `src/api/review.ts` → `live(...)`; keyboard verdicts, the inspector
   on real payloads, the cluster page on a real grouping; `?state=` smoke states rewritten to live content.
4. **Seed a real queue** on this machine in `--project` mode once the tests pass (backup verified): the
   `extract events` queue from Prompt 03's flagged sequences and one detections queue from Prompt 04's template
   application.

## Testing and critique

- Python: queue creation per source kind, blinding, verdict writes land in the right table and never the wrong
  one (rule 5 both directions), undo restores, promotion creates or extends an entry deterministically, window
  verdicts, extract-events linkage. `pytest -n auto` at baseline.
- Client gate (`--only review` on 8765), screenshots to `webui/screenshots/wiring/05/`; stop your servers.
- Critics on **Opus at medium effort**, read-only, disjoint: (a) *write-safety* critic tries every verdict path
  and checks the tables (rule 5, audit rows, undo); (b) *function* critic drives both Review pages live with the
  keyboard; (c) *data-truth* critic diffs queue counts and header counts against the tables. Fix P0/P1; re-run
  once.

## Report

`docs/prompts/wiring/reports/05-review.md`: queue kinds implemented, tables and routes, verdict/promotion write
paths with their tests, client functions switched, the seeded queues' counts, critics' scores and fixes, what
remains before the whole UI is live (a table of any `demo(FIXTURE)` left in `src/api/`), questions with defaults
taken. End with the chat summary.
