# Report — Fixup M: migrate the 115 legacy span-relative detections, once and permanently

Run 2026-09-28 on `main`, in the main checkout (`C:\Users\mmebr\Documents\CNN`, the real `DATA/`, no
junction). Commit prefix `fixup-m:`. The first commit, `ad1b088`, touches only `tests/` and fails on
import (the migration did not exist). The migration **was applied to the real database** — that is what
this prompt is for — after a verified backup, and nothing else in this prompt writes anywhere.

**What exists now, in one paragraph.** `detections` is channel-absolute in fact, not only by convention:
the 115 rows across 8 runs that a spanned run wrote span-relative before 2026-09-21 have been shifted by
their run's `span_start`, once, through `init_db()` (`Working/database/schema.py::migrate_legacy_detections`),
recorded as `audit_log` row 482. The migration is keyed on the data — a legacy row is one whose
`start_idx` lies below its run's `span_start` — so a second pass plans nothing, and it refuses any run
where that rule cannot be trusted (ambiguous: `span_length > span_start`; mixed: rows on both sides of
`span_start`). `absolute_bounds` and its three callers are untouched, and prompt `G` still adds Review's:
a database restored from an older backup holds relative rows again, and `init_db()` now migrates it on
open. `scripts/migrate_legacy_detections.py` sequences the real-database run (backup → integrity check →
dry run → migrate → verify) and can re-run the verification alone.

---

## 1. The audit, re-run against the database as it was on 2026-09-28

Read-only, before anything was written (`plan_legacy_detections` on a `mode=ro` connection):

| measure | 2026-09-24 audit | 2026-09-28 re-run |
|---|---|---|
| runs with `span_start > 0` | 56 | **56** |
| of those, with detections | 18 | **18** |
| holding legacy rows | 8 | **8** |
| rows to rewrite | 115 | **115** |
| ambiguous runs (`span_length > span_start`) | 0 | **0** |
| mixed runs | 0 | **0** |

| run | span | length | n | min `start_idx` | row ids |
|---|---|---|---|---|---|
| 3 | [747,652, 764,509) | 16,857 | 1 | 3,266 | 1 |
| 4 | [747,652, 764,509) | 16,857 | 11 | 3,266 | 2..12 |
| 34 | [1,134,497, 1,265,320) | 130,823 | 74 | 58,195 | 630..703 |
| 41 | [53,340, 54,060) | 720 | 1 | 0 | 704 |
| 42 | [1,209,600, 1,216,800) | 7,200 | 4 | 2,468 | 705..708 |
| 44 | [1,209,600, 1,216,800) | 7,200 | 8 | 136 | 709..716 |
| 45 | [1,209,600, 1,216,800) | 7,200 | 15 | 3,060 | 717..731 |
| 51 | [1,209,600, 1,216,800) | 7,200 | 1 | 0 | 732 |

**Identical to the 2026-09-24 table, row for row.** The researcher's jobs since then (runs 57 and
69–78, all spanned, all with detections) were written by the fixed executor and are absolute — every
one of their rows sits at or above its `span_start`, so they are neither legacy nor mixed and the plan
does not list them. The closest ambiguity margin is still run 34: length 130,823 against `span_start`
1,134,497, 8.7x clear. Nothing had to be explained away.

## 2. The backup, and its integrity check

Made with the sqlite backup API (the same call `webui --project` uses, so a WAL database another
process holds open is copied whole), into the same folder the bridge writes its own:

| | |
|---|---|
| path | `DATA/db/backups/20260928-211406-fixup-m.sqlite` |
| size | 34,152,448 bytes (identical to the live file) |
| `PRAGMA integrity_check` | `ok` |
| rows | 77 runs, 1,205 detections |

Verified **before** the migration touched anything: the script refuses to continue if the copy is
missing, empty, or fails the check. A first backup, `20260928-211341-fixup-m.sqlite`, was written by the
dry run four minutes earlier and is identical; both are kept. (Each has a zero-byte `-wal` sidecar from
being opened read-only for the check; the copies are WAL-mode like their source. Harmless.)

## 3. The dry run

    runs with span_start > 0: 56; of those with detections: 18; to migrate: 8; refused: 0; rows: 115

— the table in §1, exactly. `scripts/migrate_legacy_detections.py --dry-run` prints it and writes
nothing but the backup.

## 4. The migration

Applied through `init_db(DATA/db/annotations.sqlite)` — the application path, not a side door — at
2026-09-28T11:14:07Z. One transaction for all eight runs; per run the `UPDATE`'s rowcount is asserted
equal to the planned ids and a `COUNT(*)` of rows still below `span_start` is asserted zero, or the
whole thing rolls back. Rowcounts matched: 1 + 11 + 74 + 1 + 4 + 8 + 15 + 1 = 115.

**The `audit_log` entry** (id 482, kind `migration`, actor `init_db (fixup M)`,
`where_ = Working/database/schema.py::_migrate_legacy_detections`):

> Rewrote 115 legacy span-relative detections to channel-absolute across 8 runs (start_idx <
> span_start on a run with span_start > 0 → start_idx + span_start, end_idx + span_start)

`detail_json` carries `rule`, `n_rows: 115`, `refused: []`, and one object per run with `run_id`,
`span_start`, `span_end`, `span_length`, `n`, `n_legacy` and the full list of `ids` — the eight rows of
§1 with every id spelled out — so the rewrite is reconstructible from the row alone (before =
after − `span_start`), which is exactly how `--verify` and `--redetect` below reconstruct it.

## 5. Idempotence

* Immediately after the rewrite, in the same process: `plan_legacy_detections` plans **0 rows**.
* `--verify` and `--redetect`, each a fresh process calling nothing that writes, ran afterwards against
  the same file; `audit_log` still holds one `migration` row.
* In the suite: `test_a_second_pass_rewrites_nothing` and
  `test_init_db_applies_it_on_reopen_and_only_once` (one audit row after two opens).

Every touched row now has `start_idx >= span_start`, so `absolute_bounds` returns it unchanged — proved
per row in the round-trip test (§8) and on the real data by `--redetect`, whose comparison goes through
the raw columns.

## 6. Verification against the signal, not the schema

Two checks, both on the raw channel arrays (`DATA/derived/channels/<file>/CH0.npy`, memory-mapped,
read-only). The prompt asks for the first; the second is the one that settles it.

### 6.1 Does the window sit on an event? (heuristic, per row)

For every window, before and after the shift: **rank** = the window's peak-to-peak range ranked against
every same-length window across its run's span (the population its detector chose from; ≥ 0.90 called
"event-like"), and **holds extremum** = after a straight-line detrend of the window widened 4x each
side (≥ 120 samples), the sample of largest |residual| lies inside the window. Three rows per run
(first, middle, last id); `--verify` prints all 115.

| run | row id | length | before (h) | after (h) | before: rank / holds extremum | after: rank / holds extremum |
|---|---|---|---|---|---|---|
| 3 | 1 | 66 | 0.9072–0.9256 | 208.5883–208.6067 | 0.43 / yes | 0.65 / no |
| 4 | 2 | 62 | 0.9072–0.9244 | 208.5883–208.6056 | 0.46 / yes | 0.63 / no |
| 4 | 7 | 99 | 1.6619–1.6894 | 209.3431–209.3706 | 0.06 / no | 0.56 / no |
| 4 | 12 | 87 | 4.5547–4.5789 | 212.2358–212.2600 | 0.03 / no | 0.16 / no |
| 34 | 630 | 356 | 16.1653–16.2642 | 331.3033–331.4022 | 0.58 / no | 0.06 / no |
| 34 | 667 | 251 | 21.3186–21.3883 | 336.4567–336.5264 | 0.32 / no | 0.11 / no |
| 34 | 703 | 164 | 32.4975–32.5431 | 347.6356–347.6811 | 0.11 / no | 0.68 / no |
| 41 | 704 | 121 | 0.0000–0.0336 | 14.8167–14.8503 | 1.00 / yes | 0.00 / no |
| 42 | 705 | 1084 | 0.6856–0.9867 | 336.6856–336.9867 | 0.26 / no | 0.70 / yes |
| 42 | 707 | 1008 | 1.4428–1.7228 | 337.4428–337.7228 | 0.20 / no | 0.68 / no |
| 42 | 708 | 1014 | 1.7150–1.9967 | 337.7150–337.9967 | 0.20 / no | 0.88 / no |
| 44 | 709 | 1 | 0.0378–0.0381 | 336.0378–336.0381 | 0.92 / no | 0.50 / no |
| 44 | 713 | 1 | 0.4647–0.4650 | 336.4647–336.4650 | 0.75 / no | 0.68 / no |
| 44 | 716 | 6 | 0.7067–0.7083 | 336.7067–336.7083 | 0.51 / no | 0.60 / no |
| 45 | 717 | 60 | 0.8500–0.8667 | 336.8500–336.8667 | 0.44 / no | 0.99 / yes |
| 45 | 724 | 60 | 1.2697–1.2864 | 337.2697–337.2864 | 0.55 / no | 0.99 / no |
| 45 | 731 | 60 | 1.6292–1.6458 | 337.6292–337.6458 | 0.14 / no | 0.96 / no |
| 51 | 732 | 7200 | 0.0000–2.0000 | 336.0000–338.0000 | n/a / yes | n/a / no |

Over all 115: after the shift 15 of 114 rankable windows are event-like (before: 2); the detrended
extremum lies inside 7 (before: 18); **115 of 115 lie inside their run's span after, 0 of 115 before**.

**This heuristic is inconclusive on its own and I am not going to pretend otherwise.** It is decisive
for run 45 (15 of 15 at rank ≥ 0.96) and for the span containment, and it is meaningless or misleading
for the rest, for reasons the recipes explain: runs 3, 4 and 34 are `dehshibi_spikes`, whose ROIs are
wavelet-defined regions, not peak-to-peak extremes, on a channel with large slow drift; run 44's rows
are one-sample **matrix-profile discord positions** (the anomalous 60-sample subsequence *starts*
there — a one-sample window has no extremum to hold); run 41's single row is the whole 121-point
profile above a threshold of 0, i.e. the whole span; run 51's is a 7,200-sample catalogue window equal
to its span. "Before: holds extremum = yes" for rows 1, 2, 704 and 732 is the channel's settling
transient at hour 0, which is where every relative row pointed. So I did the check that does not depend
on guessing what each detector's window means:

### 6.2 Does the detector itself produce these rows today? (decisive, every row)

`--redetect` re-runs **each migrated run's own recipe on its own span** through the adapters alone —
no run row, no step cache, no persist, nothing written — and compares the detector's fresh spans,
shifted by `span_start` exactly as the executor writes them since 2026-09-21, with the rows the table
holds now:

| run | recipe | migrated rows | fresh rows | exact matches | within 2 samples |
|---|---|---|---|---|---|
| 3 | dehshibi_spikes | 1 | 1 | **1** | 1 |
| 4 | dehshibi_spikes | 11 | 11 | **11** | 11 |
| 34 | dehshibi_spikes | 74 | 74 | **74** | 74 |
| 41 | detrend → matrix_profile → threshold | 1 | 1 | **1** | 1 |
| 42 | detrend → stage_encoding → drop_detection | 4 | 4 | **4** | 4 |
| 44 | detrend → matrix_profile → threshold | 8 | 8 | **8** | 8 |
| 45 | detrend → matrix_profile → mp_motifs | 15 | 15 | **15** | 15 |
| 51 | sliding_windows → window_images → cnn_score → threshold | 1 | not re-runnable headlessly (binds side inputs, needs the CNN) | | |

**114 of 115 rows are, sample for sample, what their detector produces on that span today.** The
115th (run 51, row 732) is [1,209,600, 1,216,800) after the shift — exactly its run's span, which is
what a whole-span catalogue window is; before the shift it was [0, 7,200), the first two hours of a
channel the run never looked at. The shift is right for every row it touched, and it is right for the
reason the prompt gives: a relative row plus its run's offset *is* the absolute row, and the detector
agrees.

## 7. What was NOT changed, on purpose

| left alone | why |
|---|---|
| `Working/discovery/spans.py::absolute_bounds` and its calls in `scoreboard.py`, `webui/server/discovery.py`, `webui/server/corpus.py` | prompt §3: the function is the rule, it is tested, and a restored older backup holds relative rows. They are no-ops on this database now — checked by `--redetect` through the raw columns |
| Review's reader (`queue_candidates` not selecting `span_start`; `_resolve_detections` copying raw) | prompt `G`, belt and braces |
| `annotations`, `motif_entry`, `motif_member`, `reviewed_spans` | only `detections` had the defect. I looked for the same signature while auditing — a spanned run's child rows below its `span_start` — and `detections` is the only table whose rows are keyed to a run's span at all; the others are keyed to a recording and were always written absolute. No evidence of a second table; none fixed |

## 8. Tests

`tests/test_legacy_detections_migration.py`, eleven, on a scratch database with one of everything
(a legacy spanned run with a mid-span row *and* a start-0 whole-span row, a post-fix spanned run whose
rows are absolute, a whole-channel run):

* the ambiguity refusal (`span [5,000, 100,000)`, a row at 100 — refused, reported `ambiguous`,
  untouched) and the mixed-run refusal (rows at 2,468 and 1,210,000 under `span_start` 1,209,600 —
  refused, reported `mixed` with `n_legacy 1 of 2`, untouched);
* the plan names each run, its `span_start`, its row ids and count;
* a legacy row becomes `start + span_start, end + span_start`; a start-0 row becomes the span itself;
* an already-absolute row and a whole-channel run's row are untouched;
* idempotence: the second pass plans and rewrites zero rows and leaves every coordinate as the first
  pass left it;
* through `init_db()`: re-opening the file migrates it; opening it again writes no second audit row;
* the `audit_log` record: one row, `n_rows`, the rule, each run's id, `span_start`, ids; a refusal alone
  writes no audit row;
* **the round trip through a shifting reader**: `Working.discovery.scoreboard._detections` returns the
  same coordinates before and after; the raw row was wrong before and equals the reader after;
  `absolute_bounds` on the migrated row is the identity.

## 9. The gate

| check | result |
|---|---|
| `pytest -n auto` (conda), full suite | **1786 passed / 6 skipped / 0 failed** (baseline 1775 / 6 / 0; +11 are this prompt's). No test that passed before fails |
| FastAPI files under `webui/.venv` (`tests/test_webui_*.py -n auto`) | 259 passed, 3 xpassed, **1 failed** — `test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers`, the pre-existing one the prompt names |
| client (`npx tsc -b`, `npm run build`) | not run — no client file changed |
| `webui/smoke.py` | not run — no `webui/` file changed, and nothing ran while `pytest -n auto` was running |

## 10. Files

| file | in the prompt's list? |
|---|---|
| `Working/database/schema.py` — `LEGACY_DETECTIONS_RULE`, `plan_legacy_detections`, `migrate_legacy_detections`, `_migrate_legacy_detections` in `init_db()`, docstring | yes |
| `tests/test_legacy_detections_migration.py` | yes |
| `scripts/migrate_legacy_detections.py` — **out of list.** The real-database procedure (backup → integrity → dry run → migrate → verify → re-detect), kept so it is reproducible on a restored backup rather than living only in this report. Dev tooling under `scripts/`, imported by nothing | no — reported |
| `docs/prompts/fixup/07-review.md` (R15), `QUESTIONS.md` (Q25), `README.md` (M row), this report | yes |

## Chat summary

The 115 legacy span-relative `detections` rows across runs 3, 4, 34, 41, 42, 44, 45 and 51 are now
channel-absolute in the real database, rewritten once through `init_db()` after a verified backup
(`DATA/db/backups/20260928-211406-fixup-m.sqlite`, `integrity_check ok`). The re-run audit matched the
2026-09-24 table row for row: no run ambiguous, none mixed, 115 rows. `audit_log` row 482 records
every run, offset and row id; a second pass plans zero rows. Verified against the signal the decisive
way: re-running each run's own recipe on its span reproduces the migrated rows exactly for 114 of 115,
and the 115th is a whole-span window now equal to its span. `absolute_bounds` and its three readers
stay; `G` still adds Review's. Suite 1786 / 6 / 0.
