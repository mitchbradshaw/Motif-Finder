# Report — Prompt 05: Review — queues, verdicts and promotion on real data

Run 2026-09-22 on `main`, in the main checkout. Nobody else was running. Commit prefix `wire-review:`.

> **Stages 1 and 2 are both complete.** Stage 1 (§1–§10) landed the storage, the core write paths and the
> seam, under a hard ~40-minute clock, and was honest that the seeding, the browser gate and the critics had
> not been run. **Stage 2 (§11–§12) ran them, and they found a great deal** — including one place where this
> report's own §4 was false, corrected in place with the correction left visible. Read §11 and §12 as the
> authoritative account; §1–§10 are accurate except where a correction says otherwise.

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

> **CORRECTION (stage 2).** As this section was originally written it was **false**, and the paragraph below
> replaces what it said. Stage 1 claimed the crossing was refused in both directions and that the tests proved
> it. The check asked *"does a row with this id exist in the table I am about to write to"* and returned as
> soon as it did — so the refusal branch was **unreachable for any id that exists in both tables**, which on
> this database is every detection id (detections run 1..732, annotations 1..11269). The stage-1 tests passed
> only because they used synthetic ids that happened not to collide. A check that holds only when ids do not
> collide is not a check. Found by the write-safety critic; see
> [`05-review-critics.md`](05-review-critics.md) and commit `bf0f2fd`.

`write_verdict` resolves the target through **the queue's `unit`** — what the queue is *made of* — and refuses
anything else. The question is not "does this id exist somewhere" but "is this the id of the thing this queue
is putting to a person", and `review_queues.unit` already answers it.

| `unit` | the id names a row in | the verdict lands in |
|---|---|---|
| `detection` | `detections` | `adjudications` |
| `human span` | `annotations` | that same annotation |
| `sequence` | `sequences` | **that sequence's `annotation_id`** |
| `window` | an index into the queue's window set | `window_verdicts` |

An id belonging to a different store is a `PermissionError` naming rule 5; an id belonging to no store is a
`ValueError`. A queue whose `unit` and `writes_to` disagree is itself the crossing and is refused twice — at
`create_queue` (a `ValueError`, nothing was written) and again at the write seam (a `PermissionError`, a door
was forced).

**The tests now use ids that collide on purpose**, because a test with non-colliding ids re-creates the hole
this correction is about. They assert that after each refusal **neither table gained a row and no audit row was
written**.

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

## 7. What stage 2 had to do (all of it now done — see §11)

Stage 1 listed six items here. Every one has been run: the queues were seeded on the real database (§11.1),
the client gate and the Playwright smoke are green (§11.4), the three critics ran and their 26 findings are
fixed (§11.2), the `?state=` smoke states were rewritten to live content, and the push decision is the last
thing outstanding. What is genuinely still not true is in **§12**, not here.

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

## 10. Gate (stage 1 — superseded by §11.4)

Kept for the record of what stage 1 could claim at the time. The current numbers are in §11.4 and below.

| Gate | Stage 1 | **Stage 2 (current)** |
|---|---|---|
| Review core suite | 95 passed, 1 skipped | **147 passed, 0 skipped** |
| Bridge (`tests/test_webui_review.py`) | never actually ran | **21 passed** |
| Full headless suite | 1504 passed, 1 failed | **1638 passed, 6 skipped, 0 failed** |
| `npx tsc -b` / `npm run build` | not run | **both exit 0** |
| `webui/smoke.py --only review` | not run | **19 states, 0 failures, 0 console errors** |
| Critics | not run | **run, 26 findings, all fixed or in §12** |

Two notes on that table. The bridge tests **never ran at all** before stage 2: `fastapi` lives only in
`webui/.venv`, so `tests/test_webui_review.py` skipped silently under the conda interpreter in every gate to
that point — which is how a `/extract` route that created zero annotations survived. Run them with
`webui/.venv/Scripts/python.exe`. And stage 1's one failure
(`test_window_matrix_resume.py::test_timeout_produces_a_partial_matrix_that_resumes_to_completion`) was
correctly diagnosed as contention from concurrent pytest runs: it has passed in every full-suite run since,
on a quiet machine.

## 11. Stage 2 — what was run, what it found, what changed

Stage 1 ended with the storage, the core write paths and the seam committed, and the real-data seeding, the
browser gate and the critics **not run**. Stage 2 ran all three. It should be read as the part of this report
that knows what it is talking about: nearly everything below was found by exercising the thing rather than by
reasoning about it.

### 11.1 The seeded queues

Both created through `POST /api/review/queues` on a bridge in `--project` mode — the real
`DATA/db/annotations.sqlite` — after a backup taken with sqlite's own backup API (safe against a concurrent
writer, unlike a file copy over a WAL database) and verified `integrity_check = ok`.

| id | queue | source | unit | writes | items |
|---|---|---|---|---|---|
| 1 | `Library - extract events` | `sequences WHERE needs_extraction = 1` | sequence | `annotations` | **30** |
| 2 | `drop_detection_v1 - Mushroom_260720 CH14` | run 32 / recording 385 | detection | `adjudications` | **130** |

Header "N need you" = **160**, which is 30 + 130 and matches an independent SQL count. The seeding wrote
**exactly two rows** and nothing else: `annotations` 11 269 → 11 269, `detections` 732 → 732, `adjudications`
0. That is §1's "a queue is a filter, not a copy" verified on real data rather than asserted.

**The detections queue points at a run, not a run group**, and that is a finding about this machine rather
than a compromise. `run_groups`, `discovery_runs` and `discovery_sessions` are all **empty** in the project
database — Prompt 04 ran against the sandbox, so nothing it created persisted here — and every one of the 16
runs carrying detections has `run_group_id IS NULL`. The queue therefore resolves through the `filters` dict
that `queue_items` already passes to `ReviewQueue`, which has accepted `run_id` since ticket 20. When a real
Discovery fan-out writes a run group here, a `source_ref` queue resolves it with no code change.

### 11.2 The critics

Three, Opus at medium effort, disjoint briefs. Their full record with reproduce steps is
[`05-review-critics.md`](05-review-critics.md).

| Critic | Score | Findings |
|---|---|---|
| Write-safety | **3 / 10** | 11 (3×P0) |
| Function | **1 / 10** | 7 (3×P0) |
| Data-truth | **4 / 10** | 8 (1×P0) |

They were run against a **sandbox** copy rather than `--project`. Two of the three must write verdicts to do
their job, and `adjudications` is empty on this machine: machine-generated critic verdicts in the real table
would be indistinguishable from genuine ones afterwards and would poison the RQ5 divergence measurement — the
same failure mode `requests/04-to-05.md` §2 raises about bulk discards. The sandbox copies the real database,
so they still exercised real queues over real detections and real sequences.

All 26 findings are fixed or listed in §12. The three that mattered most:

1. **The rule-5 guard was decorative** — see the correction in §4.
2. **The `extract events` queue corrupted the human record.** It hands out `sequences.id`; the writer took it
   for an `annotations.id`; sequence ids 119–148 all exist as annotation ids, so a verdict on the queue the
   researcher is meant to work through first silently rewrote an unrelated human observation and left the
   intended one untouched.
3. **`POST /extract` discarded the reviewer's work entirely** — zero annotations created, each event
   serialised into the wrong row's `note` and overwritten by the next, `needs_extraction` never cleared so the
   item could never leave the queue, and three audit rows for one gesture. Now `Working/review/extraction.py`,
   where an extraction is its own act: one new annotation per event with `parent_annotation_id` set, the
   parent's note untouched, one audit row, reversible.

What the critics **verified correct** is not a small list, and it is the part of stage 1 that survived an
adversary: batch is one atomic act (a batch containing a crossing writes nothing at all), undo restores a
prior verdict rather than deleting, promotion is idempotent, eight concurrent writes lost nothing, blinding
withholds the score on the wire, the superseded-run filter works, the prior-verdict rule genuinely uses the
onset term (IoU 0.579 with onset gap 16 > 15 correctly did **not** match), the cap is honoured, and all 130
served rows matched their `detections` row field for field.

### 11.3 The browser gate found five things no test could

`npx tsc -b`, 147 core tests and 21 bridge tests all passed against a Review workspace that **rendered nothing
at all**. This is the second time this repo has learned that a surface which constructs has not necessarily
painted, and it is why `webui/smoke.py` is a gate in its own right.

| # | Defect | Why no test saw it |
|---|---|---|
| 1 | The landing defaulted to the fixture queue id `q-12` and **persisted it in `localStorage`**, so the first visit 404'd and every later one did too. The escape button from "no such queue" navigated back to `q-12` — the only way out of the error was into it. | No test drives the router with a stale browser store |
| 2 | `d.nearest[0]` dereferenced unguarded while the bridge always sends `nearest: []` | The function critic *predicted* this before it was reachable |
| 3 | `.toFixed` on the artifact fields stage 2 had just made null | Making the bridge honest about what it has not computed made every consumer that assumed presence reachable |
| 4 | `f.id` in the evidence rail — same cause, different consumer | — |
| 5 | The rail showed **"129 left"** and **"No items match these filters"** at the same time: its channel filter is `f.channels.includes(r.channel)` and the live queue header carried `channels: []`, so it excluded every row while the count beside it said 129 were waiting | A page contradicting itself is not a thrown error |

(3) and (4) are consequences of a stage-2 change of ours, and the change was still right: a fabricated
artifact likelihood beside a real waveform is a finding that is not there. But an honest absence has to be
followed through to every reader, and the gate is what found the readers.

### 11.3b The critics again, after the fixes

Re-run on the fixed build, as the prompt asks ("fix P0/P1; re-run once"). Round 1 scores in brackets.

| Critic | Score | Findings |
|---|---|---|
| Write-safety | **3 / 10** (was 3) | 9 (3×P0) |
| Function | **4 / 10** (was 1) | 9 (1×P0) |
| Data-truth | **8 / 10** (was 4) | 4 (0×P0) |

Data-truth moving 4 → 8 is the count path being verified honest row-for-row with no discrepancy findable
anywhere. Write-safety staying at 3 is the more useful number: the detections path it had faulted is now
confirmed sound — batch atomic, priors restored exactly, a 130-item batch and its undo leaving the table
byte-identical — and everything that remained was on the **annotations** side.

**One of those P0s was a regression of our own making**, and it is worth naming rather than folding into a
list. `promotion._reverse_verdict` carried the identical `target_id`/`row_id` confusion that commit `bf0f2fd`
had fixed in `verdicts.py` an hour earlier: `promotion.resolve_target` was pointed at the shared resolver and
the rest of that module was not audited. Unpromoting a sequence-queue promotion therefore wrote the intended
row's prior verdict and note onto **a different annotation**, left the real one judged, deleted the Library
entry that justified it, and recorded nothing about the row it damaged — through the one route whose entire
purpose is to take a judgement back. Fixing a bug class in one module and not grepping for it in its siblings
is how that happens.

The other four, all fixed in `0bc63bc`: prior **tags** were never carried in the audit payload, so a tagged
verdict destroyed the existing tags irreversibly and undo restored verdict and note and left the loss
standing; the `human span` membership exemption added in `bf0f2fd` was too broad and turned a one-item queue
into a licence to write any of the 11 302 annotations; the held-out (D6) write guard covered only
`unit == 'detection'`, leaving a held-out recording's annotations and sequences writable; and `undo_last` was
a read-then-write with no guard, so a held Ctrl-Z reported success six times for one reversal — it now claims
the audit row with a conditional stamp before reversing anything.

Two round-2 P1s about the UI are also closed: an item the database had a verdict for displayed
"unadjudicated · no verdict yet in this queue" (`queue_items` served `judged: true` with no verdict), and the
header's "N need you" was the fixture constant **3** while `/api/review/counts` — a route that exists and is
tested — said **160** and was never called.

### 11.4 The claim this prompt exists to make, observed

`webui/smoke.py --only review`: **19 states, 0 failures, 0 browser console errors, 0 server tracebacks**.
Screenshots in `webui/screenshots/wiring/05/`.

The states worth naming are the keyboard ones — *verdict given (I) writes to the database and advances*,
*Ctrl-Z undoes through the server*, *Space skips without writing* — and afterwards the sandbox database held
**exactly one adjudication (detection 102)**, with 103's verdict written and then reversed. "Review runs on
real queues and writes real verdicts" is a thing that was watched happening, not a thing that was asserted.

## 12. What is still not true, stated plainly

None of this is hidden behind a green gate.

| # | Not done | Why it matters |
|---|---|---|
| 1 | **Tags never reach the database from the UI.** The write functions send them, but no component passes them, and the vocabulary category has to be resolved per term. The Annotate card's tags are a session label. | The core and bridge paths ARE fixed and tested (a bare list is routed to the category that defines each term); it is the component that does not call them |
| 2 | **There is no extract-events editor in the client.** `postExtract` is exported and called nowhere, so queue 1 renders as generic items and nobody can mark individual events in the browser. | The core and the route work and are tested; the UI for the gesture does not exist |
| 3 | **Cluster review is unreachable on this data.** No resolver emits a cluster number for either seeded queue, so the three cluster routes 404 by design, saying so in words. | Cluster review needs a queue built from a **Grouping**, which nothing creates yet |
| 4 | **A cluster seed is two audit rows** (batch, then promote), so it takes two undos rather than one | The core has no promote-with-batch door |
| 5 | **The promotion panel's family choice and the exemplar id are still session-local** | `postPromote` mints the real entry at the S keypress; nothing updates its family afterwards |
| 6 | **No window queue exists on this machine** — `window_sets` has **zero rows** — so `training-windows` and `model-verification` are covered by unit tests only, never on real data | P20 blinding is asserted at the payload level in `tests/test_webui_review.py`, not in a browser |
| 7 | **No `explore-spans` queue is possible here** — no annotation has `verdict = 'seed'`, because Explore's *Take span for Review* has never been used on this machine | — |
| 8 | **`clusterQueue(no)` still reads the fixture** — it is synchronous and every caller would have to become async | Named in §6 since stage 1 |

### The smoke states that were removed, and why

Eight fixture-era states are gone from `webui/smoke_pages/review.json`, each with its reason recorded in the
file itself so a shorter file does not read as a passing one: the blind/training-window states (no
`window_sets` rows), the explore-spans state (no `seed` annotations), the promotion and cluster states (items
2–5 above), and `?state=empty` (a demo-store affordance with no live equivalent). One more was dropped during
the gate: *queue not found* produces a red card **and** a console error, which is exactly the loud failure
CLAUDE.md asks for — but the page walk fails any state that logs a console error, so asserting it there would
mean making the failure quiet. It stays covered by `tests/test_webui_review.py` and by `smoke.py`'s own
`loud_failure` step.
