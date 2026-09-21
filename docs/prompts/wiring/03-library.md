# Prompt 03 — Library: real motifs, sequences and groupings (parallel with 04)

You are working in `C:\Users\mmebr\Documents\CNN` (Windows; Bash tool = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md`, `docs/WIRING_PLAN.md` (D1, D4, D5 bind you),
`docs/BLOCK_INTEGRATION.md` and `docs/DATA_REGISTRATION.md` (written by Prompts 01 and 02 — read their reports in
`docs/prompts/wiring/reports/` too), `Working/database/schema.py` (the motif tables and their docstrings, lines
1–33, 218–283, 353–375), `Working/library.py`, `Working/Detection/drop_motifs/store.py`, `docs/PIPELINE_PRD.md`
Part 1 "Storage" and Part 2 "Library entries at two scales" / "Library import", `prototyping/UI_FUNCTIONAL_SPEC.md`
§4 (motif identity, revisions, matching rule), §8 (Library) and §12 P8, P18, P21, P22, `webui/pages/inventory/
library.md`, `webui/client/src/library/`, `src/api/library.ts`, `src/fixtures/library.ts`. Work autonomously;
defaults over questions; questions with the default taken go in your report. Commit prefix `wire-library:`. Push
`main` at the end.

**Another agent is running Prompt 04 (Discovery: seeded search and template application) in this checkout at the
same time.** It owns `webui/server/discovery*.py`, `webui/client/src/discovery/`, `src/api/discovery.ts`,
`src/fixtures/discovery.ts`, `Working/Detection/matrix_profiling/` additions. You do not edit those. Shared files
(small hunks, commit immediately with `--` paths): `webui/server/app.py` (router lines only),
`Working/database/schema.py` (additive), `webui/client/src/api.ts` (append), `fixtures/canon.ts`,
`webui/smoke.py` (extend). Ports **8765 / 5173** for you; 04 uses 8766 / 5174. Never `git add -A`, stash, reset
or checkout. Requests to 04 go in `docs/prompts/wiring/requests/03-to-04.md`. Discovery will read exemplars and
templates from the tables and routes you build — publish their shapes in `docs/LIBRARY_STORAGE.md` early (commit
the doc skeleton in your first hour so 04 can read it).

## Goal

Populate the Library with real data and make its pages live:
- **Singular motif events** from the drop-motif runs: `DATA/library_seed/drop_motifs5/motifs/` (410 events,
  tracked, canonical seed), `Plots/drop_motifs10/motifs/` (3,511, with species/corpus/framing columns) and
  `Plots/drop_motifs12a/motifs_PARTIAL/` (4,023) if present on this machine — imported once through the
  registration kind Prompt 02 built, into the motif tables, with provenance and a content hash per event.
- **Catalogue signals** from `DATA/catalogue/signal_catalog.xlsx` (37 rows) and the **human-annotated spans**
  (`annotations`: 11,269 rows, verdicts interesting / not_interesting / seed / artifact / unsure) — many are
  **sequences**, not single motifs. The Library distinguishes single motifs from sequences (spec §8.2 units:
  single motifs · sequences · spike trains) and stores them separately with a link from a sequence to the singular
  events extracted from it. `Plots/drop_motifs11/sequences.csv` (118 rows, keyed by start/end event id) is the only
  sequence data on disk — import it as the first sequence set.
- **Sequences whose singular events are not yet extracted are flagged** (`needs_extraction`), listed on the
  Library and offered to Review (Prompt 05) as a queue "extract events", so a human can mark the individual
  events later; until then they are compared only at sequence scale.
- **Consistent storage**: one identity rule (shape-first content hash + recording/channel/span, spec §4.1),
  duplicates detected at import and on every write (same hash → same `motif_entry`, a new member revision, never a
  second entry; near-duplicates by the matching rule §4.6 flagged for review, not merged), revisions (§4.2:
  a member carries a current span pointer and a revision list), hand edits keyed to the content hash so they
  survive regrouping (fog A16).
- **Adjustable, pluggable grouping**: the grouping engine takes a `unit × basis` (spec §8.2: distance / feature
  bins / labels / sequence similarity) and a clustering method with parameters (Ward on the scale-invariant
  distance is the default from PRD Part 2; feature-bin and label bases as in Settings › Library groupings); a
  new clustering algorithm is a class in `Working/library/grouping/methods/` registered by name, with the
  checklist in the doc. Saved groupings (a `groupings` table, additive) record method, parameters, cut and the
  member → family assignment; the recurrence page reads them.

## The standard (`docs/LIBRARY_STORAGE.md`) — skeleton in the first hour, complete by the end

Sections: the tables and what each row means (`motif_entry`, `motif_member`, `motif_edge`, tags; the additive
tables you add: `sequences`, `sequence_members`, `groupings`, `grouping_assignments`, `window_sets` if Prompt 01
did not already, `hand_edits`); identity and hashing (exact algorithm, resampling, z-normalisation, what is and is
not in the hash); duplicates and near-duplicates (rule, thresholds, where flagged); revisions; sequences vs single
motifs vs spike trains (spike trains: define the unit, store nothing yet, state what a future importer must
provide); import kinds and provenance (event store, catalogue, annotations) with the columns mapped; the grouping
engine's interface and the **checklist for adding a clustering method**; what the UI reads (routes and payload
shapes); a worked example (importing an event store, running a grouping, hand-editing an exemplar, regrouping and
seeing the edit survive).

## Work (test-first per seam)

1. **Core** `Working/library/` (UI-free): `identity.py` (hash), `importers/{event_store,catalogue,annotations,
   sequences}.py` through `writes.write_human` for human spans and `write_machine` for machine events (rule 5 —
   an extracted drop-motif event is a machine detection with its human verdict, if any, joined from
   `annotations`; decide and document which table each import writes), `dedupe.py`, `revisions.py`,
   `grouping/{engine,bases,methods/ward,methods/<one more>}.py`, `hand_edits.py`.
2. **Migrations** in `schema.py` (additive, each its own function, `init_db()` idempotent).
3. **Bridge** `webui/server/library.py`: counts, groupings (list/run/save — a run is a job through Prompt 01's
   `jobs.py`), recurrence, motif families, sequence families, family detail with members and revisions, omitted
   list, import (drives the importers; progress through the job model), window sets, templates (real
   `templates` table), hand edits (write routes through `write_human`), export of a family/atlas (JSON + CSV, a
   real download route).
4. **Client**: the 11 `demo(FIXTURE)` reads in `src/api/library.ts` → `live(...)`; the grouping editor's
   histograms and feature bins on real distributions; Atlas/Recurrence/Family/Grouping/Import/Window-sets/
   Templates pages live; `?state=` smoke states rewritten to live content.
5. **Populate this machine** once in `--project` mode after the tests pass (backup verified first): import the
   seed bundle, the larger stores if present, the catalogue, the sequences, run the default grouping, save it.

## Testing and critique

- Python: importers on fixture bundles (a 5-event store you write under `tests/fixtures/`), identity/hash
  stability, duplicate and near-duplicate detection, revision chains, grouping engine with each base and method,
  hand-edit survival across regrouping, rule-5 refusals. `pytest -n auto` at baseline.
- Client gate as in the plan (`--only library` on 8765), screenshots to `webui/screenshots/wiring/03/`; stop your
  servers.
- Critics on **Opus at medium effort**, read-only, disjoint: (a) *storage* critic reads `docs/LIBRARY_STORAGE.md`
  and the schema and tries to break identity/dedupe/revision rules with edge cases (same shape at two fs,
  overlapping spans, an event re-imported with one column changed), scoring clarity 1–10; (b) *function* critic
  drives every Library page live; (c) *data-truth* critic counts motifs, sequences, families and duplicates
  directly from the tables and the source files and diffs against the pages. Fix P0/P1; re-run once.

## Report

`docs/prompts/wiring/reports/03-library.md`: what was imported on this machine (counts per source, duplicates
found, sequences flagged `needs_extraction`), tables added, routes, client functions switched (count), grouping
methods available, critics' scores and fixes, requests to 04/05, questions with defaults taken. End with the chat
summary.
