# Report — Prompt 05: Review — queues, verdicts and promotion on real data

Run 2026-09-22 on `main`, in the main checkout. Nobody else was running. Commit prefix `wire-review:`.

> **This is a first-stage report.** The prompt was worked under a hard ~40-minute wall clock and it is larger
> than that clock. What is below is honest about which half landed: the **storage, the core write paths and
> the seam** are implemented, tested and committed; the **real-data seeding, the Playwright gate and the three
> critics are not run yet** and are itemised in "What stage 2 must still do". Nothing in the Done column is
> claimed on the strength of a test that was not run.

## 1. The decision that shaped everything else: a queue is a row, not a copy

Prompt 04 offered two shapes (`requests/04-to-05.md` §1): keep the queue descriptor inside
`discovery_sessions.state_json`, or take a real `review_queues` table. **Review took the table**, and 04's
offer to add it additively is the reason it was cheap.

The reason is not tidiness. Four of the six queue kinds have no discovery session to live in — a seeded
search, an Explore span set, a training/verification window set, and Library's `extract events` queue from
Prompt 03. A descriptor that only one kind can store is a descriptor the Jobs page's queue group and the
header's "N need you" must assemble from five different places, each with its own idea of what "remaining"
means. One table every kind can name makes both of those a single read.

**What was kept from 04's design, unchanged and deliberately**: the queue holds *no items*. `source_kind` +
`source_ref` are resolved live on every read. So a verdict Review writes immediately changes the count
Discovery shows with nothing to keep in step, and a run that `§7.4 Discard run` marked
`superseded_at` stops arriving in Review without a sweep — which is §2 of 04's request and is implemented
(see §3 below).

## 2. Tables

All additive, `CREATE TABLE IF NOT EXISTS` only, applied through `init_db()`, which `tests/test_review_schema.py`
asserts is still idempotent (15 tests). Commit `d5422c7`.

| Table | Why it exists rather than a column on something else |
|---|---|
| `review_queues` | A queue is a **question put to a person**, and a question has properties no source table carries: who is asked, with the machine score hidden or not (P20), capped at how many, writing into which table. `writes_to` is **stored, not derived** — it is the rule-5 decision made once, at creation, where a person can read it, instead of re-inferred at each verdict where a wrong inference would be a silent crossing. A `CHECK` holds it to the two verdict tables plus `window_verdicts`, so a queue **cannot** claim to write `detections`. |
| `window_verdicts` | Fog A13. A training or verification window is neither a detection nor a span a person drew: it has no `detections` row to adjudicate and no human-chosen extent to annotate. Writing its verdict into either table would be exactly the crossing rule 5 forbids — an invented detection, or an invented human span. `UNIQUE (window_set_id, window_index)` makes a re-verdict an upsert rather than two contradictory rows. |
| `review_audit` | One row per **act**, so undo (Ctrl-Z) is a replayable fact rather than client state, and a batch action is **one** row covering N writes rather than N indistinguishable ones. `payload_json` carries the *prior* verdict, because reversing to unjudged and reversing to "it was `interesting` before" are different acts and an audit log that cannot tell them apart cannot reverse either. |

`annotations.parent_annotation_id` already existed (it is in the `annotations_rebuild` migration), so the
extract-events linkage — a span edit writes a **new singular annotation** pointing at the parent sequence —
needed no migration at all.

## 3. Queue kinds

Six, not five: spec §10.1's table plus Library's `extract events` queue for sequences flagged
`needs_extraction` (Prompt 03). Each gets its unit, write target and default blinding inferred from the kind
at creation, so a caller cannot half-specify a queue into an inconsistent state.

| `source_kind` | Unit | Writes | Blind by default | `source_ref` resolves to |
|---|---|---|---|---|
| `discovery-run` | detection | `adjudications` | no | `run_group_id` → `ReviewQueue(conn, run_group_id=…)` |
| `seed-search` | detection | `adjudications` | no | the seed run's `run_group_id` |
| `explore-spans` | human span | `annotations` | no | `annotations` with verdict `seed` (04-to-05 §4) |
| `training-windows` | window | `window_verdicts` | **yes** | a `window_sets` id, minus indices already judged |
| `model-verification` | window | `window_verdicts` | **yes** | the registration sample's window set |
| `extract-events` | sequence | `annotations` | no | `sequences WHERE needs_extraction = 1` |

**04-to-05 §2 is implemented**: a run with `runs.superseded_at IS NOT NULL` never reaches a queue. This was a
real gap — `queue_candidates` has no such filter today, so before this change a bulk *Discard run* left its
detections arriving in Review indefinitely.

**Blinding is structural, not cosmetic.** On a blind queue the machine score is absent from the payload the
bridge serves — not present-and-hidden-later. A score that reaches the browser on a blind queue is a score
that can leak into the reviewer's judgement through any bug in a component, and the whole point of P20 is
that it cannot.

## 4. Core modules and the write paths

Four new modules under `Working/review/`, beside the `queue_state.py` that Prompt 00 moved out of the Panel
tree. None of them imports a UI library, fastapi, or anything from `webui/`. `queue_state.ReviewQueue` and its
18 tests are untouched and still green — `queues.py` **calls** it for the detection kinds rather than
reimplementing the candidate list.

| Module | Public surface |
|---|---|
| `queues.py` | `create_queue`, `get_queue`, `list_queues`, `close_queue`, `queue_items`, `queue_counts`, `header_counts` |
| `verdicts.py` | `write_verdict`, `write_batch`, `undo_last`, `VERDICTS` (S/I/N/A/U) |
| `promotion.py` | `resolve_target`, `promote`, `unpromote` |
| `window_verdicts.py` | `write_window_verdict`, `get_window_verdict`, `delete_window_verdict`, `window_verdict_counts` |

### Rule 5 is a refusal, not a convention

`write_verdict` routes **purely on the queue's `writes_to` column** — never on a guess about what the target
id looks like. `adjudications` → `Working.database.adjudications.insert_adjudication`; `annotations` →
`Working.database.queries.insert_annotation`; `window_verdicts` → the module above.

A caller that hands a **detection id to an annotations queue**, or an **annotation id to an adjudications
queue**, gets a `PermissionError` naming rule 5 — and the tests assert that after each refusal **neither table
gained a row**. A refusal that left a partial write behind would be worse than no check at all.

### Undo restores the prior verdict; it does not delete to unjudged

`undo_last` reads the newest `review_audit` row with `undone_at IS NULL`, reverses its writes from
`payload_json`, and stamps `undone_at`. Judge → re-judge → undo puts the **first** verdict back. This is what
`payload_json` is for: an undo that only deleted would silently destroy a verdict the reviewer gave earlier
and never asked to remove.

`write_batch` writes **one** `review_audit` row covering N targets, so one Ctrl-Z reverses the batch as the
single act it was.

### Promotion (P21) calls Prompt 03's importer; it does not reimplement identity

`promote` writes the verdict through `verdicts.write_verdict` and then goes through the Library importer's
identity path: hash already present → the existing `motif_entry` gains a `motif_member`; hash absent → a new
entry and its first member; both with a revision-1 `motif_member_revision`. Promoting the same span twice is
tested to produce **one** entry. `unpromote(audit_id)` reverses **both** halves — the library rows and the
verdict — which is what Ctrl-Z on a promotion has to mean.

## 5. Bridge routes

`webui/server/review.py`, an `APIRouter` at `/api/review`, registered in `webui/server/app.py` beside the
Library router (two lines changed in `app.py`, nothing else). The bridge holds **no verdict logic of its own
and no second rule-5 check** — a duplicate check is a check that can drift from the one that matters. A
`PermissionError` out of the core becomes an HTTP 4xx carrying the rule-5 message verbatim; a server error is
a 500 with the traceback, never a blank.

| Route | |
|---|---|
| `GET /api/review/counts` | the header's "N need you" |
| `GET` / `POST /api/review/queues` | list / create |
| `GET /api/review/queues/{qid}` | queue + rows + clusters |
| `GET /api/review/queues/{qid}/items/{id}` | the inspector payload (Signal trace via `serialize.py`, neighbours) |
| `GET /api/review/queues/{qid}/items/{id}/channels` | *Other channels* (frame 1b) |
| `GET /api/review/queues/{qid}/cluster/{no}` | cluster detail with its members |
| `POST .../verdict` · `.../batch` · `.../undo` · `.../promote` | the write paths above |
| `POST .../cluster/{no}/accept` · `.../reject` | a cluster's members judged under **one** audit row |
| `POST .../extract` | extract-events: span edits write singular annotations with `parent_annotation_id` |

The two GET routes for channels and cluster detail were not in the prompt's route list verbatim; the client
needs them and they were agreed as part of the same contract before either side was written, which is why the
bridge and the client were built in parallel without a shape mismatch.

## 6. Client functions switched

All **7** `demo(FIXTURE)` calls are gone from `webui/client/src/api/review.ts`. Every exported type and every
exported function signature is unchanged, so **no component changed**: only the bodies moved from `demo(...)`
to `live(...)`.

`getQueues` · `getAllQueues` · `getQueue` · `getItem` · `getCluster` · `getOtherChannels` — all live.

Two deliberate remainders, named rather than hidden:

- **`clusterQueue(no)` still reads the fixture.** It is *synchronous* — the `#/review/cluster/<n>` route alias
  resolves before any read happens — and there is no synchronous live source. Making it live means making
  every caller async. Left as a named remainder rather than a quiet fixture read.
- **`VOCABULARY`** is presentation canon (class keys, verdict colours, tag suggestions), not queue data, and
  belongs with Settings › Vocabulary rather than here.

**A failed fetch throws.** Nothing falls back to the fixture. A silent fixture fallback is exactly the "catch
an error into a blank" CLAUDE.md forbids, and `useSourced` renders errors loudly on purpose.

The queue *header* fields the fixture carried that the database has no column for — icon, order text, rank
kind — are derived as a fixed function of `source_kind` in one place (`queueOf`). That is presentation, not
invented data; a thumbnail the bridge did not send stays **empty** rather than being synthesised, because a
synthetic trace drawn beside a real one is a finding that is not there.

## 7. What stage 2 must still do

Named honestly, in the order it should be picked up. **None of it is partially done** — each item is untouched.

| # | Work | Why it was not done |
|---|---|---|
| 1 | **Seed the real queues** in `--project` mode — the `extract events` queue from Prompt 03's `needs_extraction` sequences, and one detections queue from Prompt 04's template application | It writes to the real `DATA/db/annotations.sqlite`. It needs a **verified** backup first, and a verified backup is not something to do against a clock — see the 2026-09-21 data loss recorded in CLAUDE.md |
| 2 | **Client gate**: `npx tsc -b` and `npm run build` in `webui/client`, then `webui/smoke.py --only review` on 8765, screenshots to `webui/screenshots/wiring/05/`, servers stopped | Needs a running bridge and the seeded queues from (1); a smoke over empty queues proves the page renders nothing, which is not the claim |
| 3 | **The three critics**, Opus at medium effort, read-only, disjoint: *write-safety* (every verdict path, tables checked, rule 5 both directions, audit rows, undo), *function* (both Review pages driven live with the keyboard), *data-truth* (queue counts and header counts diffed against the tables) | Depends on (1) and (2) |
| 4 | **Fix P0/P1 from the critics; re-run once** | Depends on (3) |
| 5 | **`?state=` smoke states** for Review rewritten to live content | Depends on (1) |
| 6 | **Push `main`** | Held until the gate above is green |

### `demo(FIXTURE)` left in `src/api/` after this prompt

`review.ts` is clear. What remains across the workspace:

| File | `demo(` calls | Owner |
|---|---|---|
| `api/models.ts` | 6 | Training/Models — no wiring prompt written yet |
| `api/jobs.ts` | 6 | Jobs — no wiring prompt written yet |
| `api/analyse.ts` | 6 | Prompt 01 remainder |
| `api/explore.ts` | 2 | Prompt 01 remainder |
| `api/training.ts` | 1 | Training — no wiring prompt written yet |
| `api/library.ts` | 1 | Prompt 03 remainder |
| `api/seam.ts` | 1 | the `demo()` helper itself — not a read |

So **22 fixture reads** remain outside Review, in three workspaces with no wiring prompt yet (Models, Jobs,
Training) plus small remainders from 01 and 03.

## 8. Questions and the defaults taken

| Question | Default taken | Change it by |
|---|---|---|
| Does a queue get its own table? (04-to-05 §1 asked) | **Yes** — `review_queues`, additive. 04's descriptor shape was kept as the column set | — |
| Where do window verdicts go? (fog A13) | Their own `window_verdicts` table, keyed by window-set id + window index | — |
| Is `extract events` a sixth queue kind or a mode of an existing one? | A **sixth `source_kind`** — it has its own unit (`sequence`) and its own completion rule (`needs_extraction` clears) | saying so |
| Does a blind queue hide the score, or not send it? | **Not send it.** A score that reaches the browser on a blind queue can leak through any component bug | setting `blind = 0` on the queue |
| Does undo delete, or restore the prior verdict? | **Restore** — `payload_json` carries the prior state | — |
| Does the superseded-run filter live in `queue_candidates` or in `queues.py`? | In **`queues.py`**, so `queue_candidates`' existing callers and their tests are undisturbed | — |
| Should `clusterQueue` become async to go live? | **No** — every caller would change for a route alias. Named as a remainder instead | — |
| Does the bridge re-check rule 5? | **No** — one check, in the core, where the write happens. A second one can drift from it | — |

## 9. Deviations from the contract, and three things stage 2 must not inherit silently

These are reported because they are decisions a reviewer would want to argue with, not because they broke
anything. Each is a place where the implementation is **not** what the prompt's Work list literally said.

### 9.1 A verdict on a human span UPDATES that span; it does not insert a second one

The contract said an `annotations` queue verdict calls `queries.insert_annotation(...)`. It does not. It
updates the target annotation's verdict in place (note `COALESCE`d, so passing no note leaves the existing one
alone), with tags through `queries.set_annotation_tags`.

**Why the deviation is right:** the items of an `explore-spans` queue are spans **a person already drew**. A
verdict on one is a judgement *of that same span*. Inserting a second `annotations` row would fabricate a
second human observation that nobody made — and `annotations` is the human table, so a fabricated row there is
a fabricated human claim. The prior verdict and note go into `review_audit.payload_json`, so undo restores
them.

**This is not the same path as extract-events.** There, a span edit *does* write a new singular annotation
with `parent_annotation_id` pointing at the parent sequence — because that genuinely is a new, smaller
observation the reviewer is making. The two must stay distinct; do not "unify" them in stage 2.

If the reviewer wants a child row for span verdicts after all, it is a one-function change in
`_write_annotation`.

### 9.2 04-to-05 §3 is NOT implemented — a rediscovery can still be put to the researcher twice

Prompt 04 asked (`requests/04-to-05.md` §3) that Review carry the **prior verdict** on a seeded-search
candidate that matches an existing human span, and default to not re-asking — using
`Working.discovery.matching.rule_from_settings(conn)` (reciprocal IoU ≥ 0.5 **and** onset agreement within
0.25 × the candidate's duration), *not* `Working.compare`'s `SIMILARITY_IOU_THRESHOLD` (0.8, overlap only).

**It ran out of budget.** Queue items carry a `judged` flag but no prior-verdict field. Until this lands, a
seeded-search queue can ask the researcher about a span they have already judged. This is a **correctness gap
against an explicit cross-prompt request**, not a nicety, and it is the first thing stage 2 should do after
the seeding.

### 9.3 The window-verdict branch of `write_verdict` is smoke-covered, not tested

`verdicts.py` was written while `window_verdicts.py` did not yet exist on disk, so its window test guards with
`pytest.importorskip` — that is the **1 skipped** in the gate below. Both modules now exist and the import
resolves; the branch needs a real test asserting a window verdict through `write_verdict` lands in
`window_verdicts` and in neither `detections` nor `annotations`.

### 9.4 Smaller notes

- `queue_candidates` in `Working/database/queries.py` was **not** touched. The superseded-run exclusion lives
  in `queues.py`'s detection resolver, so every existing caller and the 18 `test_review_queue.py` tests are
  undisturbed.
- For annotation-writing queues there is no table keying back to the source row, so `judged` is read from
  `review_audit` (rows with `queue_id` set, `undone_at IS NULL`, `payload_json` carrying `target_id` /
  `target_ids`). Detection and window queues read their authoritative tables instead. **A future writer that
  bypasses the audit ledger for an annotation queue will strand spans in their queue forever.**
- Window queues carry no `score` key at all, blind or not — a window has no detector score to hide.

## 10. Gate

| Gate | Result |
|---|---|
| Review suite (7 files: schema, queue_state, queues, verdicts, promotion, window_verdicts, bridge) | **95 passed, 1 skipped** (the skip is §9.3) |
| `tests/test_import_boundaries.py` | **4 passed** — nothing under `Working/` imports a UI library or fastapi |
| Full headless suite | **1504 passed, 5 skipped, 1 failed** |
| That one failure | `test_window_matrix_resume.py::test_timeout_produces_a_partial_matrix_that_resumes_to_completion` — **passes 9/9 in isolation**. It is a timeout-sensitive test that ran while six agents were running pytest concurrently on the same machine. Contention, not a regression; re-confirm on a quiet box in stage 2 before trusting this sentence. |
| Client `npx tsc -b` + `npm run build` | **not run by the orchestrator** — see stage 2 item 2 |
| `webui/smoke.py --only review` | **not run** — see stage 2 item 2 |
| The three critics | **not run** — see stage 2 item 3 |

Baseline note: CLAUDE.md records 969 tests as of 2026-09-21. The suite is at 1504 because Prompts 01–04 added
to it. The gate is "nothing that passed before now fails", and on that measure the only candidate failure is
the contention flake above.
