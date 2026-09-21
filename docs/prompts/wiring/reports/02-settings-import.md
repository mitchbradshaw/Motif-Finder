# Report — Prompt 02: Settings, registering the data already in the repository

Date 2026-09-21. Commits prefixed `wire-settings:` on `main` (path-scoped; Prompt 01 ran in the same checkout).
Standard: `docs/DATA_REGISTRATION.md`. Code: `Working/registration/` (core), `webui/server/registration.py`
(bridge), `webui/client/src/{api.ts, api/settings.ts, settings/}` (client). Tests:
`tests/test_registration_{recording,artifacts,settings}.py`, `tests/test_webui_registration.py`.

## Kinds implemented

| kind | scan root(s) | checks | table row | UI surface | test |
|---|---|---|---|---|---|
| recording | `DATA/derived/channels/<stem>/` | exists · readable (1-D, finite head/tail) · shape (channels equal, = manifest) · fs (manifest or supplied → `inferred`) · held_out · **excerpt** (both directions, coarse-to-fine cross-correlation, r > 0.99, one-sample-sharp) · not_registered · hash | `recordings` × channels (`fs_source`, `registered_at/by`, `warnings_json`, `parent_recording_id`/`parent_offset`/`decimation`) | Datasets (rows, warnings, "excerpt of", unregister); Explore menu via `GET /api/recordings` (verified: no client change); Channels & events picker | `test_registration_recording.py` (19) |
| raw | `DATA/raw/*.mat, *.csv` | readable header (tolerant v5 walk: opaque MATLAB objects no longer break `whosmat`) · held_out · not_derived · fs · layout (matrix / flat / columns; variable + channel count) | derives `DATA/derived/channels/<stem>/` (staged, atomic) → recording rows | Datasets › Import a recording (fs / channels / variable inputs) | same file (2) |
| model | `MODELS/*.pth`, `DATA/derived/models/*.joblib` | readable (`torch.load` / `joblib.load` → summary) · format · hash | `registered_artifacts(kind=model)` | Models & registration › Registered models (check / register / unregister / manifest) | `test_registration_artifacts.py` (2) |
| matrix_profile | `Results/Detection/matrix_profile/mp_v2_*.npz` (`_legacy/` skipped) | readable · keys · recording **by content** · fs · span · length (`len(mp) == span − m + 1`) · finite · hash | `registered_artifacts(kind=matrix_profile)` + `recording_id, channel, span, fs, params{m, config_hash, backend}` | Storage › matrix profiles › scan → check → register | (2) |
| window_matrix | `Results/Preprocessing/window_matrix/wm_v1_*.npz`, legacy `MATRICES/*.csv` | readable · keys · shape · recording · fs · span · finite · incomplete → warning; csv: header, rows, recording named in the file name | `registered_artifacts(kind=window_matrix)` | Storage › window matrices / legacy matrices › scan | (2) |
| window_set | `DATA/derived/window_sets/<name>/{windows.npz, manifest.json}` | manifest kind · files · keys · recording · fs · shape · span | `registered_artifacts(kind=window_set)` | Storage › window sets › scan | (1) |
| encoding | `DATA/derived/encodings/*.npz` | readable · keys · recording · fs · span · finite | the existing `encodings` table (`active` added) | Storage › encodings › scan | (1) |
| drop_motif_store | `DATA/derived/drop_motifs/*`, `DATA/library_seed/**`, `Plots/**` (dirs with `events.csv`) | files · manifest · columns · **every event has its snippet** · unknown recording_id / fs mismatch → warnings | `registered_artifacts(kind=drop_motif_store)` + `params{n_events, detector, spans, recording_ids}` | Storage › library seed › scan | (1) |
| catalogue_spreadsheet | `DATA/catalogue/*.xlsx` | readable · required columns · typed parse; **unparseable cells listed, never guessed** | `registered_artifacts(kind=catalogue_spreadsheet)` + `params{n_rows, columns, unparseable}` | Storage › catalogue spreadsheets › scan | (2) |
| hpc_result | `HPC/results/<job>/` (`HPC/results/README.md`) | recipe · recipe_hash · recording (by content from the artifacts, else recipe id) · shape · length · finite · manifest · **paused run with the same hash → `paused_run_id`** | bundle row + one row per enclosed artifact under its own kind (`params.published`) + `import_manifest` when a run manifest is present | Storage › HPC results › scan; Jobs › Upload is Prompt 01's | (2) |

Common to all: the sidecar manifest (`<file>.manifest.json` / `<dir>/registration.manifest.json`; sandbox mode
writes it under `webui/runtime/<stamp>/sidecars/`), the audit entry (`kind = registration`), rows through
`writes.write_machine` (rule 5: a human writer is refused before any row lands — tested), soft unregister
(`active = 0`, rows and ids kept; `corpus.recordings()` and `list_registered` skip inactive rows).

Schema (additive, `init_db()` idempotent — tested on a legacy database): `recordings` += `parent_recording_id,
parent_offset, decimation, fs_source, registered_at, registered_by, warnings_json, active`; `encodings` +=
`active`; new `registered_artifacts`, `settings`, `audit_log`. The bridge calls `init_db()` on its database once
per app (the runtime copy in sandbox mode, the real file in project mode), so the migration happens on first use.

## The excerpt rule on the real data

`L_LM_Jul_26_J_raw_fs10` CH2 vs row 385 (`Mushroom_260720_0509_4hrs_CH14_fs1`, 1 Hz, 14,401 samples):
decimation 10, offset **15,777,590**, r = **0.99945**, neighbouring lags 0.9707 / 0.9791 — the same numbers
`Pipelines/drop_motifs/lionsmane12.py` measured. The first brute-force version took 240 s per recording
check (65 FFT correlations over 10.9 M points for M1); the coarse-to-fine search (both sides block-meaned
16:1 for the FFT, exact r at full rate within one coarse block) takes 26 s and finds the same peak. Row 385
keeps its id (6 runs, 217 detections) and gains the parent link; Datasets shows "excerpt of
L_LM_Jul_26_J_raw_fs10 CH2 · 10:1".

## Recordings, models, matrices registered on this machine (project mode)

One run, 2026-09-21 17:15–17:21, `webui/run_server.py --port 8766 --project`; the backup
`DATA/db/backups/20260921-171549.sqlite` (4,349,952 bytes) was verified before the first write. Log and
screenshots: `webui/screenshots/wiring/02/` (`RUN_LOG.md`, 01–11).

| what | rows | notes |
|---|---|---|
| **L_LM_Jul_26_J_raw_fs10** (through the Datasets import flow, screenshots 02–04) | `recordings` 540–544, fs 10 `inferred` | 8/8 checks; **row 385 linked**: `parent_recording_id 542` (CH2), `parent_offset 15,777,590`, `decimation 10`; Datasets shows it as "excerpt of L_LM_Jul_26_J_raw_fs10 CH2 · 10:1" (screenshot 05) |
| **M1**, **M100**, **M101_t** | 545–557, 558–570, 571–583, fs 10 `read` | `provenance.raw_file` M1_M100.mat / M101_t.mat, the time-vector fact in the sidecar notes |
| **MJu26a** | 584–599, fs 7.246 `read` | warning: sampling not uniform (dt 0.124–2.83, median 0.138) |
| matrix profiles | `registered_artifacts` 1–10 (10 of 13 mp_v2 files) | bound to rows 33, 35, 46, 385. **Refused** (length ≠ span − m + 1): `mp_v2_M2_aug_concat_fs1_CH0_WIN10min` (121 of 2,595,001 points), `…_WIN1min` (7,141 of 2,595,541), `mp_v2_Mushroom_…_WIN10min` (13,801 of 13,802 — one short) |
| window matrices | 11–18 (8 of 8) | the two `wm_v1` npz bound to rows 1 and 385; the six `MATRICES/*.csv` as legacy with warnings (`features*.csv` name no recording → `recording_id` null) |
| models | 19–36 (18 of 18) | 12 checkpoints, `catch22_rf_prelabeled.joblib`, 6 classifier joblibs (one, `…52520f7a…`, written by Prompt 01's tests during the day); all warn "no provenance sidecar yet" |
| catalogue spreadsheet | 37 | 37 rows, 26 columns, 0 unparseable cells |
| drop-motif seed store | 38 | 410 events, detector detect5, 16 spans; refused at first because the store writes three arrays per event (`__raw_mv`, `__detrended_mv`, `__t_s`) — fixed and registered on a second `--project` start (backup `20260921-172121.sqlite`) |

Not registered: **F2B.mat** (no rate in the file; one Import click once known), the three refused matrix
profiles above, the eight `_legacy/` profiles (old naming, skipped by design). Explore's menu now lists all
eleven recordings (screenshot 10).

Sampling rates were read from the raw files, not assumed (2026-09-21, `scipy.io.loadmat(variable_names=…)`):

| recording | fs | how |
|---|---|---|
| M1, M100 | 10 Hz, `read` | `M1_M100.mat::t1` is 10,868,600 timestamps in uniform 0.1 s steps (dt min 0.0999999999913, max 0.1000000000058) |
| M101_t | 10 Hz, `read` | `M101_t.mat::t101` likewise (10,860,035 samples) |
| L_LM_Jul_26_J_raw_fs10 | 10 Hz, `inferred` | no time vector in the file; verified by the excerpt match above (warning shown) |
| MJu26a | 7.246 Hz (1/median dt), `read` with a **non-uniform** warning | `t.npy` dt 0.124–2.83, median 0.138 |
| F2B | — | derivable from `DATA/raw/F2B.mat::F2B` (5,184,001 × 5) through Datasets › Import (raw kind); fs is not in the file and must be supplied — not registered in this run because no rate could be read or inferred |

## Settings pages switched demo → live

**17 of 17 reads** in `src/api/settings.ts` are `live()`; no `demo(` remains in the module. Fourteen project
pages read and write the `settings` table (`GET|PUT /api/settings/<page>`; every save is audited); the two
personal pages persist in `localStorage`. Real backing per page:

| page | what is real now |
|---|---|
| Datasets | the registry (rows, warnings, excerpt links, candidates), metadata values, the held-out lock (server-enforced typed name → 409, audited as `lock`) |
| Channels & events | registered recordings and their channel names; gains, floors, grounds, timed events as saved values |
| Vocabulary | verdict counts from `annotations` / `adjudications`; tags from `tag_vocabulary` when it has rows |
| Nulls, Review queues, Library groupings, Export | saved values (the row vocabularies are UI configuration) |
| Analysis defaults | the step cache size and root |
| Compute & HPC | the machine (cores, RAM, GPU) |
| Blocks | `GET /api/adapters` (22+ blocks, `known_broken`), templates that use each block, on/off saved |
| Models & registration | registered models + candidates (the registry) and the gate values |
| Storage & backups | real roots with sizes and file counts, the backups directory, Back up now (`POST /api/backups`), scan/check/register per root |
| Audit log | the `audit_log` table, kind filter, CSV export |
| About | git head/branch/dirty, schema and row counts, blocks, python and packages, mode, database and backup paths |

The header chip reads `settings.heldOut`, which the store mirrors from the SAVED value after every hydration
and every lock change.

## Gates

- `npx tsc -b`: my files clean; the tree reports errors only in Prompt 01's in-progress
  `explore/CrossChannelPage.tsx` and `interrogation/SlopePage.tsx`, so the last client build was
  `npx vite build` (the `build` script runs tsc first). Every earlier build in the day passed both.
- `webui/smoke.py --url http://127.0.0.1:8766 --pages-only --only settings`: **115 page states, all green, 0
  console/page errors** (`webui/screenshots/pages/settings/SMOKE_SETTINGS_2026-09-21.txt`). Two things the walk
  taught: a sandbox copy shared across runs makes a seeded edit equal an earlier save (run on a fresh bridge),
  and two agents' walks collide on the same screenshot files (`smoke.py` now honours `SMOKE_SHOTS`).
- `pytest -n auto`: **1169 passed, 3 skipped, 2 failed** — `test_adapter_spec.py::test_every_shipped_adapter_…`
  and `test_end_to_end.py::test_discover_adapters_…` pin 22 adapters and Prompt 01 has 33 in the tree; both
  files are theirs and were already failing before my first commit. The 43 registration tests and the 18
  bridge-route tests (`webui/.venv` python) pass. `tests/test_import_boundaries.py` passes: nothing under
  `Working/registration/` imports a UI library.

## Critics (Opus, medium effort, read-only, disjoint)

**Round 1.**

- *Doc critic* — **4/10**. P0: no interface path registered a matrix profile / window set / HPC bundle (only a
  POST the doc did not show); `hpc_result` bound its recording by the recipe's stored id; registering a bundle did
  not publish the enclosed `mp_v2`; a non-run `manifest.json` hard-failed. P1: the report link dangled; the
  KindSpec checklist was under-specified. P2: over-stated npz keys, 423 vs 422, `jsons[0]`, unregister scope.
  **All fixed** (`efb3ac5`): Storage's scan modal checks and registers every non-recording kind; HPC bundles bind
  by content and publish their artifacts; the doc has the "where in the interface" paragraph with the request
  body, the twelve `KindSpec` fields and `_art_kind`.
- *Function critic* — every flow on all sixteen pages completed, **no P0, zero console errors**. P1s fixed
  (`ac8cbfa`): audit lines said "None → value" on a first save (the PUT now carries the previous effective
  values); `registration`/`backup` had no filter chip; unregistering a model linked to Storage; the Storage scan
  modal kept one check result; rail dots appeared only after a visit (the shell prefetches every page's values);
  Compute said nothing about the GPU; recording-metadata consequences were generic. Left: the Display *theme*
  does not repaint (pre-existing shell behaviour, density does); Blocks shows no version / null declaration (the
  adapter contract has neither — request to Prompt 01) and no unbuilt "Model stage" row.
- *Data-truth critic* — P0: 70 pre-standard rows reported `fs_source = read` while the column is NULL → now
  `unrecorded` ("not recorded" on Datasets). P1s fixed (`7c123d7`): registered directories without a manifest
  contradicted their rows in `candidates[]`; Storage's roots pointed at the sandbox redirect dirs while the
  registry scanned the real ones; the sandbox derive root was never scanned; a 121-point matrix profile looked
  fine at scan (scan now reads `n_samples`, `m` and the `mp` member's shape from the npz header). Noted, not
  changed: 8 pre-existing `encodings` rows whose files were lost on 2026-09-21 (listed with `exists: false`);
  channel names for M2/M4 come from `corpus.M2_STYLE_NAMES`, not the database.

**Round 2** (after the fixes above; one function-critic attempt was cut off by the session limit and relaunched).

- *Doc critic* — **8/10** (from 4). Every round-1 P0/P1 verified resolved in code, not prose. Remaining P1s
  fixed (`5f105e6`): a stale "one window matrix" sentence; the add-a-kind step now names both files a scan
  button needs (the server root row and the client `KIND_OF` entry); the Storage scan modal has an "overrides
  (JSON)" box so `recording_id` etc. are reachable without curl. P2s folded in (three arrays per event, the
  window-matrix required keys, non-run manifests, job dirs without a recipe).
- *Function critic* — **all seven round-1 P1s verified resolved**, zero console/page errors in three browser
  contexts; the server's 409 on a wrong unlock name confirmed. New P2s: the unregister audit line named the
  table and row id (now names the file); an unset from-value read "—" (now "not set"); a fixed sleep in a
  driver can miss the Models table (a `wait_for_selector` note for `smoke.py`, not user-facing).
- *Data-truth critic* — every round-1 item resolved; all 38 registered rows verified (paths, sidecars, sha1
  recomputed from the files, matrix-profile headers against their rows, row 385's link on both routes, the seed
  store's 1230 arrays = 410 × 3). Remaining P1s fixed (`5f105e6`): `GET /api/recordings` (what Explore reads)
  now carries `fs_source`, `warnings` and `excerpt_of`; the three hand-corrected sidecars' embedded rows.
  Recorded, not changed: the excerpt link stores offset and decimation but not the ÷1000 units factor and the
  −0.30 mV DC shift the critic measured between row 385 and L_LM CH2 (the units note lives in L_LM's
  `manifest.json`); the seed's `source_file` column names `.npy` files, not `.mat` (binding is by
  `recording_id`, which is correct).

## Requests written

- `docs/prompts/wiring/requests/02-to-01.md`: Explore needs no change (verified); Analyse source picker
  should read `getRegistry(kind)`; Jobs › Upload → continue the paused run from `paused_run_id`; the paused
  status vocabulary; Blocks on/off in the settings table; Nulls defaults for `preprocessing.surrogate`.
- `docs/prompts/wiring/requests/02-to-03.md`: Library shelves read the registry (window sets, the drop-motif
  seed store, the catalogue row); the seed's `recording_id`s are this database's; the window-set convention;
  tags in `tag_vocabulary`; grouping defaults in the settings table.

## Questions, with the default taken

1. **Where do registered artifacts go?** The prompt says `artifacts(kind=…)`, but `artifacts.run_id` is NOT
   NULL and its `kind` CHECK allows only plot/encoding/model/csv/other; changing either is a destructive
   table rebuild. Default: a new additive table `registered_artifacts` (rule 3), `encodings` for encodings.
2. **The importer.** `Pipelines/materialize_channels.materialize_arbitrary_file` handles flat vectors and CSVs
   only, writes into the fixed `CHANNEL_DIR`, and inserts rows itself (not through the rule-5 door). Default:
   `Working.registration.kinds.derive_channels` mirrors its staging/manifest layout, adds the `(n × ch)` and
   `(ch × n)` matrix layouts the unregistered files actually have, takes a `channels_root` (sandbox mode
   derives under the runtime dir), and hands the rows to the recording kind. Not a second importer of the
   flat-vector case in spirit; reported here because the prompt said not to write one.
3. **Row 385's `source_file`** stays `Mushroom_260720_0509_4hrs_CH14_fs1.mat` and the raw scan lists that
   `.mat` as "already derived"; nothing re-derives it (default: keep the row exactly as it is).
4. **M1 / M100 source_file labels.** Both live in `M1_M100.mat`; `recordings.source_file` is unique per
   channel, so the rows are labelled `M1.mat` / `M100.mat` after their directories, with the raw file and
   variable in the sidecar (`source.raw_file`, provenance notes). Default taken; an override `source_file` exists.
5. **Backups on a schedule** are a setting only (nothing runs while the bridge is down); `Back up now` and
   the `--project` start write real backups. Restore stays a by-hand copy with the bridge stopped.
6. **Excerpt threshold for "short".** The prompt's rule tests "every registered channel whose span could
   contain it"; a same-length pair is a copy, not an excerpt, and comparing 13 × 16 full channels would take
   minutes. Default: the shorter side must be ≤ 200,000 samples (`EXCERPT_MAX_SAMPLES`).
7. **Paused-run status vocabulary** is a guess (`paused | waiting | pending | queued | hpc`) until Prompt 01's
   job model lands; one tuple to edit (request written).
8. **F2B** was not registered: its fs is not in the file, and inferring one without a time vector or an
   overlapping recording would be a guess. It is one Import click away once the rate is known.

## The project-mode run

See the table above and `webui/screenshots/wiring/02/RUN_LOG.md`. Two `--project` starts (17:15 and 17:21,
each writing its backup first); the second only to register the seed store after the store-contract fix. One
hand edit of the real database afterwards, recorded here: rows 545–583 (M1, M100, M101_t) carried the scan's
"fs unknown … recorded as inferred" warning although their rate was supplied as read from the time vector;
`warnings_json` on those 39 rows and the three sidecars now say "fs 10.0 Hz supplied at registration as read
from the raw file's time vector" (the check no longer carries an answered warning onto a row).

## Chat summary

Settings is live end to end. A registration standard (`docs/DATA_REGISTRATION.md`, scored 8/10 by a
researcher-facing critic after two rounds) with ten kinds in `Working/registration/`; scan → check → register →
sidecar manifest through the rule-5 door, soft unregister, additive tables (`registered_artifacts`, `settings`,
`audit_log`) and columns (`recordings.parent_recording_id/parent_offset/decimation/fs_source/…`). The bridge
gained the registry, settings, audit, about, storage and backup routes; all 17 Settings reads are `live()`,
fourteen project pages read and write the settings table (every save audited; the held-out unlock refused server-
side without the typed name), the two personal pages persist in `localStorage`. On the real database, in one
project-mode run with the backup verified first: the five unregistered recordings (L_LM through the import flow,
row 385 linked as its 10:1 excerpt at sample 15,777,590, r = 0.9995; M1/M100/M101_t at 10 Hz read from their
time vectors; MJu26a with its non-uniform-sampling warning), 10 of 13 matrix profiles (three refused for length,
honestly), 8 window matrices, 18 models, the catalogue and the drop-motif seed store — and Explore's menu shows
all eleven recordings with no client change. Gates: settings smoke 115/115 green with zero console errors;
pytest 1169 passed with the only two failures being Prompt 01's adapter-count pins. Requests written to Prompt
01 (Analyse source picker from the registry, Jobs › Upload continuing a paused run from `paused_run_id`, the
paused-status vocabulary, block versions) and Prompt 03 (Library shelves and imports from the registry).
Left: F2B's rate is not in its file; the Display theme does not repaint (pre-existing); block version/null
declarations need an adapter-contract field.
