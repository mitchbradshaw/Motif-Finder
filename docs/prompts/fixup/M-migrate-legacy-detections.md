# Fixup M — migrate the 115 legacy span-relative detections, once and permanently

**Ready to run. Run this BEFORE prompt `G`.** `G` fixes Review's reader; this removes the thing every
reader has to remember. Small, self-contained, and it **writes to the real database**, which is why it
is its own prompt and nothing else is bundled into it.

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md` first — rules 2, 3 and 5 bind you, and so
does the `DATA/` junction warning. Commit prefix `fixup-m:`. Test-first: your first commit touches only
`tests/` and must fail.

## The defect

`detections` rows written before 2026-09-21 by a **spanned** run were stored **span-relative** while
every reader treats the table as **channel-absolute**. The wiring stage fixed the executor (it writes
absolute now) and taught **three** readers to shift a legacy row —
`Working/discovery/scoreboard.py`, `webui/server/discovery.py`, `webui/server/corpus.py` — using
`Working/discovery/spans.py::absolute_bounds`:

    if span_start and start_idx < span_start:  return start_idx + span_start, end_idx + span_start

**A fourth reader was missed: Review.** `Working/database/queries.py::queue_candidates` never selects
`r.span_start`, and `Working/review/queues.py::_resolve_detections` copies `start_idx` straight into
the queue item. `absolute_bounds` *is* imported in that file, but only for rediscovery matching in
`_prior_verdicts` — never for the coordinates the item carries out. So a legacy row in a Review queue
is drawn at the wrong hour, band and trace both, by up to 1.2 M samples.

Being found twice in two readers is what a latent data-format inconsistency does. **Fix the data, and
the class of bug goes away.** (`G` fixes Review's reader regardless, so the two are belt and braces —
that is deliberate, not redundant.)

## The audit, already done — re-run it, do not trust it

Measured read-only on the real database, 2026-09-24:

- **56 runs** have `span_start > 0`; **18** of those have detections; **8** hold legacy rows.
- **115 rows** would be rewritten.

| run | span | length | n | min start_idx |
|---|---|---|---|---|
| 3 | [747,652, 764,509) | 16,857 | 1 | 3,266 |
| 4 | [747,652, 764,509) | 16,857 | 11 | 3,266 |
| 34 | [1,134,497, 1,265,320) | 130,823 | 74 | 58,195 |
| 41 | [53,340, 54,060) | 720 | 1 | 0 |
| 42 | [1,209,600, 1,216,800) | 7,200 | 4 | 2,468 |
| 44 | [1,209,600, 1,216,800) | 7,200 | 8 | 136 |
| 45 | [1,209,600, 1,216,800) | 7,200 | 15 | 3,060 |
| 51 | [1,209,600, 1,216,800) | 7,200 | 1 | 0 |

**Two properties make this safe, and your migration must assert both rather than assume them:**

1. **No run is ambiguous.** A relative row is indistinguishable from an absolute one only if
   `span_length > span_start` (a relative index could then land above `span_start`). For all 18 runs,
   `span_length << span_start` — run 34 is the closest at 130,823 vs 1,134,497, still 8.7x clear.
   **Refuse to migrate any run where `span_length > span_start`** and report it instead.
2. **No run is mixed.** In each of the 8, *every* detection is below `span_start` and none is at or
   above it. A mixed run would mean the heuristic is wrong about that run. **Refuse a mixed run** and
   report it.

Re-run both checks as the first thing the migration does, against whatever the database holds at that
moment. The numbers above are from 2026-09-24 and the researcher has run jobs since.

## Work (test-first per seam)

### 1. The migration, in `Working/database/schema.py`, through `init_db()`

Rule 3: additive and **idempotent**. After it runs, every rewritten row has `start_idx >= span_start`,
so `absolute_bounds` leaves it alone and a second run rewrites nothing. **Assert that** — run it twice
in a test and check the second pass reports zero rows.

Migrations in this file are keyed so they run once; follow whatever mechanism the file already uses
(`_migrate_recordings_units` is the most recent example — read it before writing yours).

### 2. Record what was changed, in the database

The rewrite is not reversible from the rows alone once done. Write an `audit_log` entry — the table
exists — naming each run, its `span_start`, the row ids and the count, so a person in six months can
see that these 115 rows were rewritten and by what rule.

### 3. Do NOT remove `absolute_bounds` or the three readers' calls to it

It is tempting and it is wrong. The function is the definition of the rule, it is tested, and a
database restored from an older backup will still hold relative rows. Leave all four call sites (and
add Review's in `G`). After this migration they become a no-op on this database, which is the point.

### 4. Tests

- The ambiguity refusal and the mixed-run refusal, each on a synthetic fixture database.
- A legacy row is rewritten to `start + span_start`, `end + span_start`.
- A row already absolute is untouched.
- A whole-channel run (`span_start = 0`) is untouched.
- Idempotence: second pass rewrites nothing.
- **A round-trip through a reader**: a row that read wrong before reads right after, through one of
  the three shifting readers, proving the migration and `absolute_bounds` agree.

## Running it on the real database — the part to be careful about

**`CLAUDE.md`'s `DATA/` warning applies in full.** Never run anything here through a junction into the
real `DATA/`, and never `git clean -x` near it. The real database was destroyed once already on
2026-09-21 and recovered from a sandbox copy.

Order, and do not shorten it:

1. **Back up first, and verify the backup opens and passes `PRAGMA integrity_check`.** `--project`
   writes `DATA/db/backups/<stamp>.sqlite` on start; confirm the file exists and is sane *before* the
   migration touches anything. Say in your report where it is.
2. **Dry run.** Report exactly which runs and how many rows, and diff that against the table above.
   A difference is not necessarily wrong — the researcher has run jobs since — but it must be
   explained, not absorbed.
3. **Migrate.**
4. **Verify against the signal, not against the schema.** For a sample of migrated rows, load the
   channel and check the detection window now contains the extremum it is supposed to describe.
   A row whose indices moved but which now points at flat baseline means the shift was wrong.
   Put that check in your report as a table: run, row id, before hours, after hours, whether the
   window contains its extremum.

## Explicitly NOT in scope

| Not in scope | Why |
|---|---|
| **Review's reader** (`queue_candidates` not selecting `span_start`, `_resolve_detections` copying raw) | Prompt `G`. Belt and braces on purpose |
| **Any other table** — `annotations`, `motif_entry`, `motif_member`, `reviewed_spans` | Only `detections` had this defect. If you find evidence another table does, **report it, do not fix it** |
| **Removing `absolute_bounds` or any reader's call to it** | §3 |
| **Review's pixelation, padding, the trace x-axis** | Prompt `G` |

## The gate

`pytest` against the **1775 passed / 6 skipped / 0 failed** baseline, comparing failure **sets**.
FastAPI files under `webui/.venv`, where
`test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers` fails pre-existing and
is not yours. No client change is expected; if you make one, `npx tsc -b` and `npm run build` too.

**Never run `webui/smoke.py` while `pytest -n auto` is running** — prompt `B`'s report §9 records 23
spurious smoke failures from exactly that collision.

## Report

`docs/prompts/fixup/reports/M-migrate-legacy-detections.md`: the re-run audit against the table above
and any difference explained; the backup path and its integrity check; the dry-run counts; the
against-the-signal verification table; the `audit_log` entry; the idempotence proof; the gate; a short
chat summary.

Then update `07-review.md` and `QUESTIONS.md` Q25.
