# Prompt 04 — Discovery: seeded search and template application on real data (parallel with 03)

You are working in `C:\Users\mmebr\Documents\CNN` (Windows; Bash tool = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md`, `docs/WIRING_PLAN.md` (D1–D4 bind you),
`docs/BLOCK_INTEGRATION.md` and its report (Prompt 01 — especially `detection.seed_matches`, `detection.mp_motifs`,
the templates it seeded and the job model `webui/server/jobs.py`), `docs/DATA_REGISTRATION.md` (matrix profiles
already on disk under `Results/Detection/matrix_profile/`), `prototyping/UI_FUNCTIONAL_SPEC.md` §7 (Discovery)
and §12 P16, P17, `webui/pages/inventory/discovery.md`, `webui/client/src/discovery/`, `src/api/discovery.ts`,
`src/fixtures/discovery.ts`, `Working/Detection/matrix_profiling/{segments,motif_groups}.py`,
`Pipelines/matrix_profile/run_matrix_profile.py`, `Working/compare.py`. Work autonomously; defaults over
questions; questions with the default taken go in your report. Commit prefix `wire-discovery:`. Push `main` at
the end.

**Another agent is running Prompt 03 (Library storage and groupings) in this checkout at the same time.** It owns
`Working/library/`, `webui/server/library.py`, `webui/client/src/library/`, `src/api/library.ts`,
`docs/LIBRARY_STORAGE.md`. You do not edit those; you **read** its exemplars and templates through the routes and
shapes it publishes in `docs/LIBRARY_STORAGE.md` (it commits the skeleton in its first hour — until then, take a
library exemplar as any `motif_entry` row or, if the table is still empty, a span from
`DATA/library_seed/drop_motifs5/motifs/`). Shared files (small hunks, commit immediately with `--` paths):
`webui/server/app.py` (router lines only), `Working/database/schema.py` (additive), `webui/client/src/api.ts`
(append), `fixtures/canon.ts`, `webui/smoke.py` (extend). Ports **8766 / 5174** for you; 03 uses 8765 / 5173.
Never `git add -A`, stash, reset or checkout. Requests to 03 go in `docs/prompts/wiring/requests/04-to-03.md`.

## Goal

1. **Seeded search works on real recordings** (spec §7.6): pick a seed (Library exemplar, an Explore selection,
   a family medoid), choose the recordings/channels to search (fan-out is Discovery's, P3), run
   `detection.seed_matches` (Prompt 01's block) across them as one job with per-channel progress, reuse a matrix
   profile that already exists on disk when the window matches (registry kind from Prompt 02) and compute one
   otherwise (routing over the ceiling to *Create SLURM script*), show the distance profile with the null behind
   it (Settings › Nulls defaults through `preprocessing.surrogate`, D6), let the researcher drag the cut, and send
   the matches to Review as a queue (P20 — the queue row shape is Review's, coordinate through `schema.py`
   additively and `docs/prompts/wiring/requests/04-to-05.md`).
2. **Applying a detection template to selected spans works** (spec §7.2–7.4): choose a template (the real
   `templates` table: `drop_detection_v1`, `dehshibi_spikes`, `mp_threshold`, …), choose spans/channels, run it as
   a fan-out job (one recipe per channel through `execute_recipe`, grouped in `run_groups`), and populate the
   scoreboard with real precision/recall against reviewed overlap (§7.3: precision labelled precision, recall
   scoped to reviewed spans, an "already judged" column) computed by `Working/compare.py::compare_run_sets` and the
   matching rule of spec §4.6 (implement it in the core if absent).
3. **Compare and Compare-every-stage** read real runs: set overlap, where A and B fire, per-stage diffs
   (`diff_recipes`), disagreements stepper on real detections.
4. **Runs page** lists real Discovery runs/jobs (from the `jobs` and `runs` tables), with superseded/discarded
   handled by real writes.

## Work (test-first per seam)

1. **Core** `Working/discovery/` (UI-free): `seeded_search.py` (fan-out plan → recipes; matrix-profile reuse
   by window/fs/recording; null by surrogate draws), `scoreboard.py` (precision/recall/judged per channel from
   detections × annotations with the §4.6 matching rule), `fanout.py` (run groups, per-channel status). Anything
   generic about fan-out that Analyse could reuse goes in `Working/` with a one-line request to 01 if it touches
   its files.
2. **Bridge** `webui/server/discovery.py`: sessions (a `discovery_sessions` table, additive), seed choice, plan
   estimate (from block estimates), start (job kind `sweep`), progress SSE (through `jobs.py`), results (distance
   profiles serialised as Scores payloads through `serialize.py`, matches as SpanSets), cut update (re-threshold
   without recompute), send-to-Review, template application, scoreboard, compare, discard/supersede writes.
3. **Client**: the 17 `demo(FIXTURE)` reads in `src/api/discovery.ts` → `live(...)`; the seed card, the
   histogram with the draggable cut on the real distribution, the per-channel stepper, the scoreboard table, the
   compare views, all on server payloads through `charts/` renderers; `?state=running|failed|held-out-refused`
   made honest with real jobs on short spans.

## Testing and critique

- Python: seeded search on two synthetic channels with a planted motif (recall of the plant), matrix-profile
  reuse (a fixture npz is picked up, a mismatched window is not), null draws deterministic by seed, scoreboard
  arithmetic on a hand-built detections/annotations fixture, fan-out run grouping, held-out refusal. `pytest -n
  auto` at baseline.
- Client gate (`--only discovery` on 8766), one real seeded search in `--project` mode on M2_aug fs1 (two
  channels, a 4 h span, seed from the Library or the seed bundle), screenshots to `webui/screenshots/wiring/04/`;
  stop your servers.
- Critics on **Opus at medium effort**, read-only, disjoint: (a) *statistics* critic checks the scoreboard and
  null semantics against spec §7.3/§7.6 and `Working/compare.py` with hand-computed cases; (b) *function* critic
  drives the four Discovery pages live end to end; (c) *data-truth* critic re-derives one search's match count
  and one scoreboard row from the tables. Fix P0/P1; re-run once.

## Report

`docs/prompts/wiring/reports/04-discovery.md`: what runs for real (seeded search, template application,
compare), tables and routes, client functions switched (count), the one real search's numbers, critics' scores and
fixes, requests to 03/05, questions with defaults taken. End with the chat summary.
