# Prompt 02 — Settings: registering the data already in the repository (parallel with 01)

You are working in `C:\Users\mmebr\Documents\CNN` (Windows; Bash tool = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md`, then `docs/WIRING_PLAN.md` in full (defaults D4–D5
bind you), then `webui/server/{app,runtime}.py`, `webui/client/src/settings/` (all sixteen pages and
`chrome.tsx`/`store.ts`), `webui/client/src/api/settings.ts`, `webui/client/src/fixtures/settings.ts`,
`Working/database/schema.py`, `Working/catalogue/` (if present) and `Working/manifest.py`,
`prototyping/UI_FUNCTIONAL_SPEC.md` §9 (Settings) and §12 P23, and `webui/pages/inventory/settings.md`. Work
autonomously; defaults over questions; questions with the default taken go in your report. Commit prefix
`wire-settings:`. Push `main` at the end.

**Another agent is running Prompt 01 (Analyse/Explore blocks and the job model) in this same checkout at the same
time.** It owns `Adapters/`, `Working/Detection/`, `Working/Catalogue/`, `webui/server/{chain,runs,jobs,
serialize,templates}.py`, `webui/client/src/{analyse,explore,interrogation,training}/`, their `src/api/*.ts`,
`docs/BLOCK_INTEGRATION.md`. You do not edit those. Shared files (small hunks, commit immediately with `--` paths):
`webui/server/app.py` (add `app.include_router(...)` lines only), `Working/database/schema.py` (additive
migrations, one function each), `webui/client/src/api.ts` (append only), `webui/client/src/fixtures/canon.ts`,
`webui/smoke.py` (extend only). Use ports **8766 / 5174** (`WEBUI_PORT=8766`, `npx vite --port 5174`); the other
agent uses 8765 / 5173. Never `git add -A`, stash, reset or checkout; never touch the other agent's files; requests
to it go in `docs/prompts/wiring/requests/02-to-01.md`, worked around locally. If Prompt 01's job model
(`webui/server/jobs.py`) exists when you need progress for a long import, use it; otherwise run imports
synchronously behind a route and record that as a follow-up.

## Goal

A researcher can go to Settings and make data that already exists in the repository — but is not yet reachable
from the interface — available: raw recordings (`DATA/raw/*.mat`, and channel arrays already under
`DATA/derived/channels/` with no `recordings` row), trained models (`MODELS/*.pth`, `DATA/derived/models/*.joblib`),
window matrices (`MATRICES/*.csv`, `Results/Preprocessing/window_matrix/*.npz`), matrix profiles
(`Results/Detection/matrix_profile/*.npz`), window sets, encodings, and later HPC results. The process is
**generalisable**: a future artifact of a known kind, dropped into its conventional directory by an HPC script or
by hand, appears in a scan, can be checked, registered with provenance, and is then offered wherever that kind is
consumed (Explore recording menu, Analyse source, Models registry, Library shelves). Every project setting the
sixteen pages show that has a real backing (held-out lock, vocabulary, nulls defaults, analysis defaults, compute
limits, block enable/disable, review-queue defaults, storage roots, export options, audit log, about) reads and
writes the database; personal settings persist in `localStorage`.

## The standard (`docs/DATA_REGISTRATION.md`) — write it first

One page: **kinds** (recording, channel array, model, window matrix, matrix profile, window set, encoding,
drop-motif event store, catalogue spreadsheet, HPC result bundle), for each: conventional directory, file naming
(cite the real names: `mp_v2_<stem>_CH<n>_WIN<len>min[_span<a>-<b>].npz`, `wm_v1_<stem>_CH<n>_WIN<len>min_STEP<pct>pct.npz`,
`catalogue_classifier_<hash>.joblib`, `<recording>/CH<n>.npy` + `manifest.json`), the **manifest sidecar** every
registered artifact gets (`<file>.manifest.json`: kind, source recording/channel/span, fs, parameters, producer
(recipe hash or script), created_at, code version, checks passed), the **checks** run at registration (exists,
readable, shape/dtype, fs consistent with the recording, span inside the recording, held-out refusal, hash),
which table row it becomes (`recordings`, `artifacts(kind=…)` with `path` — bulk arrays never enter the
database, rule 4), and **where it shows up** in the UI. Then the checklist for adding a new kind: a `KindSpec`
in `Working/registration/kinds.py` (scan pattern, parser, checks, table target), one test, one row in the doc.

## Work (test-first per seam; commit per seam)

1. **`Working/registration/`** (core, UI-free): `scan(kind, roots) → [Candidate]`, `check(candidate) → Report`,
   `register(conn, candidate, provenance) → row id` through `writes.write_machine` (rule 5), `unregister`
   (soft: `artifacts.active=0`, additive column). Kinds first: recording (from `DATA/derived/channels/<stem>/`
   with `manifest.json` — the five unregistered recordings M1, M100, M101_t, MJu26a, L_LM_Jul_26_J_raw_fs10 must
   register, with MJu26a's non-uniform sampling and L_LM's inferred fs surfaced as warnings the UI shows;
   `F2B.mat` (5 channels x 5,184,001, never derived) is a sixth - its channels come from `.mat` import below).
   **A candidate that is a subset of a registered recording is an excerpt, not a new recording** (user
   decision 2026-09-21): `Mushroom_260720_0509_4hrs_CH14_fs1` (row 385) is a 10:1-decimated four-hour
   excerpt of `L_LM_Jul_26_J_raw_fs10` CH2 at sample 15,777,590 (`Pipelines/drop_motifs/lionsmane12.py`
   measured it: r = 0.9995, single-sample peak). The check at registration: block-mean to the candidate's rate
   and cross-correlate against every registered channel of the same species/setup whose span could contain
   it; a single-sample-sharp peak with r > 0.99 marks the candidate an excerpt. Store the link additively
   (`recordings.parent_recording_id`, `parent_offset`, `decimation`), keep the existing row and id (six runs
   and 217 detections reference 385), surface it in Datasets as "excerpt of …", and refuse to *derive* a
   second copy of a span that a parent already covers unless the researcher says so. Document the rule in
   `docs/DATA_REGISTRATION.md`. Channels are rebuilt by `scripts/rederive_channels.py` after the 2026-09-21
   loss (see `docs/WIRING_PLAN.md`, Data) - reuse its per-file facts rather than re-reading the `.mat`s. The remaining kinds:
   raw `.mat` → channel arrays (reuse the existing importer in `Working/` — find it; do not write a second
   one), model, matrix profile, window matrix, window set, drop-motif event store (`events.csv + snippets.npz +
   manifest.json`, the `Working/Detection/drop_motifs/store.py` contract — registration only; Prompt 03 imports its
   contents into the library), catalogue spreadsheet (`DATA/catalogue/signal_catalog.xlsx` — parse its 37 rows,
   report the unparseable cells rather than guessing).
2. **Bridge routes** in `webui/server/registration.py`: `GET /api/registry/{kind}` (registered + scan
   candidates), `POST /api/registry/{kind}/check`, `POST /api/registry/{kind}/register`, `DELETE …/{id}`,
   `GET /api/settings/{page}` / `PUT /api/settings/{page}` for project settings (a `settings` table, additive:
   page, key, value_json, updated_at, actor), `GET/POST /api/audit` (an `audit_log` table), the held-out lock as a
   setting with the typed-name confirmation enforced server-side, `GET /api/about` (versions, paths, mode).
   In sandbox mode all of these write to the runtime copy; in project mode to the real database.
3. **Settings pages live.** Replace the 17 `demo(FIXTURE)` reads in `src/api/settings.ts` one by one with
   `live(...)`; the import-recording modal becomes the registration flow (scan → check → register with progress);
   Datasets shows registered recordings with their warnings; Models & registration lists real checkpoints and
   joblibs with their manifests; Storage & backups shows real roots, sizes and the backups the `--project` mode
   writes; Audit log reads the table; About reads `/api/about`. The `settings.heldOut` demo-store key that the
   header chip reads must now mirror the saved setting.
4. **Consumers.** Where a registered kind is consumed by a page another prompt owns (Explore's recording menu,
   Analyse's source picker, Library's shelves), do not edit that page: expose the read through `api.ts`
   (`getRegistry(kind)`) and write the one-line request in `docs/prompts/wiring/requests/02-to-01.md` (and
   `02-to-03.md` for the Library). Explore's recording list already comes from `GET /api/recordings` — a newly
   registered recording must appear there without any client change (verify).
5. **HPC results.** A result bundle dropped under `HPC/results/<job>/` (create the convention) with the job's
   `.json` is scanned like any other kind; registering it creates the artifact rows and, if the job's recipe hash
   matches a paused run, the checks Jobs › Upload shows (recipe hash, per-channel shape, length, finite values).
   Implement the checks and the registration; leave the "continue the paused run" step to Prompt 01's job model
   (write the request).

## Testing and critique

- Python: `tests/test_registration_*.py` per kind (scan on a temp tree with fixture files, checks that fail
  loudly, register writes the right row and manifest, held-out refusal, rule-5 refusal); settings and audit
  round-trips. `pytest -n auto` stays at the baseline (zero failures after Prompt 00).
- Client: `npx tsc -b`, `npm run build`, `smoke.py --url http://127.0.0.1:8766 --only settings` green with the
  states rewritten to live content; one manual run in `--project` mode registering L_LM_Jul_26_J_raw_fs10 and one
  matrix profile, screenshots to `webui/screenshots/wiring/02/`; stop your servers. **In project mode you are
  writing the real database — run it exactly once, after the tests pass, and verify the backup was written first.**
- Critics on **Opus at medium effort**, read-only, disjoint: (a) a *doc* critic scores `docs/DATA_REGISTRATION.md`
  for a researcher registering a new HPC output next year (1–10, P0/P1/P2); (b) a *function* critic drives all
  sixteen Settings pages on the live server (invalid input, save/discard, audit entries, the lock flow, an import
  dry run) as in `webui/critique/`; (c) a *data-truth* critic diffs the registry pages against `ls` of the real
  directories and `SELECT` on the tables. Fix P0/P1; re-run once.

## Report

`docs/prompts/wiring/reports/02-settings-import.md`: kinds implemented (table: kind, scan root, checks, table
row, UI surface, test), recordings/models/matrices actually registered on this machine, settings pages switched
demo → live (count), critics' scores and fixes, requests written to 01/03, questions with defaults taken. End with
the chat summary.
