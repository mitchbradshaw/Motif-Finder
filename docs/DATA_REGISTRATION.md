# DATA_REGISTRATION.md — making data on disk reachable from the interface

Written for the researcher who, next year, drops an HPC output (or a checkpoint, a spreadsheet, a
raw `.mat`) into the working tree and needs it to appear in Explore, Analyse, Models or the Library.
The rule is one sentence: **nothing is reachable until it is registered, and registration is
scan → check → register with provenance, the same for every kind.** The code is
`Working/registration/` (UI-free); the routes are `webui/server/registration.py`; the page is
Settings › Datasets (recordings) and Settings › Models & registration / Storage & backups (the rest).

## The four verbs

| verb | what it does | where |
|---|---|---|
| **scan** `scan(kind, roots)` | walks the kind's conventional directories and returns every candidate, registered or not, with the facts it can read *without loading bulk data* (manifest fields, file names, npz headers) and the warnings those facts raise | `GET /api/registry/{kind}` |
| **check** `check(candidate, conn)` | runs the kind's checks against the file **and** the database; never raises — a broken file is a failed check whose `detail` says why | `POST /api/registry/{kind}/check` |
| **register** `register(conn, candidate, provenance)` | refuses unless every check passes; writes the row(s) through the rule-5 door (`writes.write_machine`), writes the **sidecar manifest**, appends an audit entry | `POST /api/registry/{kind}/register` |
| **unregister** `unregister(conn, kind, id)` | soft: `active = 0`. The row, its id and everything that references it stay. For a recording, every channel row of the same `source_file` goes inactive together | `DELETE /api/registry/{kind}/{id}` |

**Where in the interface.** Recordings and raw files: Settings › Datasets › *Import a recording…* (it asks for
what the file cannot say: fs, channel count, variable). Models: Settings › Models & registration › *Registered
models*. **Every other kind** (matrix profile, window matrix, window set, encoding, drop-motif store, catalogue
spreadsheet, HPC result bundle): Settings › Storage & backups › the root's *scan* → *check* → *register*. Jobs ›
Upload is Prompt 01's surface and is not wired yet (`docs/prompts/wiring/requests/02-to-01.md`). From a script,
the same thing is one request:

```
curl -X POST http://127.0.0.1:8765/api/registry/hpc_result/register -H "content-type: application/json" -d "{\"path\": \"HPC/results/mp_M1_CH3_WIN5min_ab12cd34\", \"overrides\": {}, \"provenance\": {\"producer\": \"sbatch 4418093\"}}"
```

`path` must be a path the scan lists (`GET /api/registry/{kind}` → `candidates[].path`); `overrides` is per kind
(`fs`, `fs_source`, `source_file`, `n_channels`, `variable`, `allow_excerpt` for recordings; `recording_id` for an
HPC bundle whose recipe was exported from another database) — the Datasets import modal has fields for the
recording ones, the Storage scan modal has an "overrides (JSON)" box for the rest; a failing check comes back as
**422** with the checks in the body; the held-out file is refused the same way (the 423 is the Explore/Analyse
routes' refusal). A job directory with no `.json` at all is not a candidate (nothing to check); one whose
artifacts are not `mp_v2_*` / `wm_v1_*` registers as a bundle only, and `params_json.published` says which
enclosed artifacts were registered under their own kind and which failed their checks.

In **sandbox** mode (the default, what `smoke.py` runs against) every write lands in the runtime
copy: the database copy, sidecars under `webui/runtime/<stamp>/sidecars/`, derived channels under
`webui/runtime/<stamp>/derived/channels/`. In **project** mode (`--project`) the real database and
the real directories are written. The scan is read-only in both.

## Kinds

| kind | conventional directory | file naming (real names) | checks beyond the common ones | becomes | shows up in |
|---|---|---|---|---|---|
| **recording** | `DATA/derived/channels/<stem>/` | `CH<n>.npy` (one per channel, 1-D float64) + `manifest.json` (`source_file`, `fs`, `n_channels`, `n_samples_per_channel`, `dtype`, `fs_note`, `time_base`, `units`); the one-channel excerpt is `<stem>_CH00.npy` | readable (1-D, finite head/tail), shape (all channels equal, = manifest), fs known, held-out refusal, **excerpt** (below) | `recordings`, one row per channel (`fs_source`, `registered_at/by`, `warnings_json`) | Settings › Datasets; Explore's recording menu (`GET /api/recordings`, no client change); Analyse source; Channels & events |
| **raw** | `DATA/raw/` | `<stem>[_fs<N>].mat` \| `.csv`: a flat vector (16 channels end to end, e.g. `M2_aug_concat_fs1.mat`), an `(n_samples × n_channels)` matrix (`M1_M100.mat::M1`, `M101_t.mat::M101`), a `(16 × N)` v7.3 matrix (`MJu26a.mat::M`), a `(5 × 5,184,001)` matrix (`F2B.mat`), one column per channel (`Fig2A_dt0p1.csv`) | header readable, held-out refusal, **not already derived**, fs known (`_fs<N>` or supplied), layout resolvable (variable + channel count) | derives `DATA/derived/channels/<stem>/` (staged, atomic swap) then registers it as a **recording** | Settings › Datasets › Import a recording |
| **model** | `MODELS/`, `DATA/derived/models/` | `<name>.pth` (PyTorch checkpoint: `fusion_cnn.pth`, `GASF_checkpoint.pth`), `catalogue_classifier_<hash16>.joblib` (sklearn) | loads (`torch.load` / `joblib.load`) → summary (keys, epoch, n_params / class, n_features, classes) | `registered_artifacts(kind='model')` | Settings › Models & registration › Registered models; Models registry (request to its owner) |
| **matrix_profile** | `Results/Detection/matrix_profile/` (`_legacy/` is skipped) | `mp_v2_<stem>_CH<n>_WIN<len>min[_span<a>-<b>].npz` — required keys `mp, m, fs, n_samples, source_file, channel`; the adapter also writes `mpi, recording_id, config_hash, backend, created_at` (read when present) | keys, **recording bound by content** (`source_file`, `channel`), fs = recording fs, span inside the recording, `len(mp) == span − m + 1`, no NaN | `registered_artifacts(kind='matrix_profile')` with `recording_id, channel, span, fs, params_json{m, config_hash, …}` | Settings › Storage; Analyse `matrix_profile` resume; Discovery |
| **window_matrix** | `Results/Preprocessing/window_matrix/`, legacy `MATRICES/` | `wm_v1_<stem>_CH<n>_WIN<len>min_STEP<pct>pct.npz` — required keys `values, computed, start_idx, m, fs, source_file, channel, n_samples`; the adapter also writes `columns, step, span_start, span_end, complete, config_hash` (read when present); legacy `MATRICES/*.csv` (header only, no manifest fields → warning) | keys, shape (`values.shape[0] == len(start_idx) == computed.shape[0]`), recording, fs, span, finite computed cells; incomplete → warning | `registered_artifacts(kind='window_matrix')` | Settings › Storage; Analyse source; Models › Launch |
| **window_set** | `DATA/derived/window_sets/<name>/` | `windows.npz` (`starts, length, fs, source_file, channel[, labels]`) + `manifest.json` (`kind: "window_set", name, recording, channel, fs, length, n_windows, labels_source`) | manifest kind, files, keys, recording, fs, shape (`n_windows`), span | `registered_artifacts(kind='window_set')` | Library › Window sets; Models › Launch |
| **encoding** | `DATA/derived/encodings/` | `enc_<type>_<stem>_CH<n>_<hash8>.npz` — keys `values, encoding_type, source_file, channel, fs, span_start, span_end, config_hash` | keys, recording, fs, span, finite | the existing **`encodings`** table (`recording_id, span, encoding_type, config_hash, path`) | Analyse (Encoding consumers, D2); Settings › Storage |
| **drop_motif_store** | `DATA/derived/drop_motifs/<run>/`, `DATA/library_seed/*/motifs/`, `Plots/drop_motifs*/motifs/` | `events.csv` + `snippets.npz` + `manifest.json` — the `Working/Detection/drop_motifs/store.py` contract (`EVENT_TABLE_COLUMNS`; indices absolute in the source channel; amplitudes in mV; `snippets.npz` holds **three arrays per event**, `<snippet_key>__raw_mv`, `__detrended_mv`, `__t_s`) | the three files, required columns (`event_id, recording_id, source_file, channel, fs`), **every event has its snippet**, manifest parses; unknown `recording_id` and fs mismatch are warnings (said, not guessed) | `registered_artifacts(kind='drop_motif_store')` with `params_json{n_events, detector, spans, recording_ids}` | registration only here; Prompt 03 imports the events into the Library |
| **catalogue_spreadsheet** | `DATA/catalogue/` | `signal_catalog.xlsx` — 37 rows, 26 columns; required `ID_Number, ID_Name, Channel, StartTime_h, StopTime_h, DATASET, STATUS` | required columns; typed parse of the numeric columns; **every unparseable cell is listed** (`row, column, value`) and left empty, never guessed | `registered_artifacts(kind='catalogue_spreadsheet')` with `params_json{n_rows, columns, unparseable}` | registration only here; Prompt 03 imports the rows into the Library |
| **hpc_result** | `HPC/results/<job>/` (`HPC/results/README.md`) | `<job>.json` (the recipe, the shape `Working/hpc/job_export.py` writes; with several JSONs the one named after the directory wins) + the artifacts the job produced (`mp_v2_*.npz`, `wm_v1_*.npz`, …) + optionally `manifest.json` (`Working/manifest.py`, written by `Pipelines/run_recipe`; any other `manifest.json` is left where it is, warned about, and nothing is read from it) | recipe parses, **recipe hash** (`Working.recipes.short_hash`), the recording **bound by content** when an artifact carries `source_file` + `channel`, else by the recipe's `recording_id` (this database's id — `overrides.recording_id` for a recipe exported elsewhere), per-artifact **shape** (`n_samples` = recording), **length** (`len(mp) == span − m + 1`), **finite**; a run manifest whose `config_hash` differs is a warning; **a paused run with the same recipe hash** is reported as `paused_run_id` | `registered_artifacts(kind='hpc_result')` for the bundle **and one row per enclosed artifact under its own kind** (an `mp_v2_*.npz` is registered as a `matrix_profile` in place, so Analyse/Discovery see it without a copy; `params_json.published` lists them) + `import_manifest` when a run manifest is present; continuing the paused run is the job model's step (Prompt 01) | Settings › Storage › HPC results › scan; Jobs › Upload (Prompt 01) |

Common checks every kind gets from `core.check`: `exists`, `not_registered` (a second registration
of the same path is refused), `hash` (sha1 of the file, or a fingerprint of a directory: per file
its name, size and the sha1 of its first and last 4 MB).

## The sidecar manifest

Every registered artifact gets one, written by `register`: `<file>.manifest.json` beside a file,
`<dir>/registration.manifest.json` inside a directory. It is the provenance the database row points
at (`registered_artifacts.manifest_path`) and what "Show manifest" opens.

```json
{
  "manifest_version": 1, "kind": "matrix_profile", "name": "mp_v2_M2_concat_fs1_CH0_WIN5min.npz",
  "path": "Results/Detection/matrix_profile/mp_v2_M2_concat_fs1_CH0_WIN5min.npz",
  "source": {"recording": "M2_concat_fs1.mat", "recording_id": 33, "channel": 0, "span": [0, 1016952], "raw_file": null},
  "fs": 1.0, "fs_source": null,
  "parameters": {"m": 300, "window_min": 5.0, "config_hash": "9a1c…", "backend": "stump", "created_at": "2026-08-15T…"},
  "producer": "Adapters/detection_matrix_profile.py (mp_v2)", "recipe_hash": "9a1c…",
  "created_at": "2026-09-21T…", "registered_by": "this installation", "code_version": "63db8d9",
  "checks_passed": ["exists", "readable", "keys", "recording", "fs", "span", "length", "finite", "not_registered", "hash"],
  "warnings": [], "sha1": "…40 hex…", "row": {"…the row as inserted…"}
}
```

`producer` is the recipe hash, the script, or the job that made the file — pass it as
`provenance={"producer": …, "notes": …}`; the checkers fill it for kinds that can tell.

## Units: what the samples are stored in (fixup-b)

`recordings.units` is `V`, `mV` or `uV`; NULL means **undeclared**, and `units_note` says where the unit came from
or why it is unknown. The vocabulary and the one factor to mV are `Working/units.py`. A recording's unit comes from
its manifest's `units` key (free text is read by its first word, so `"millivolts as stored …"` is `mV`), or from
`overrides.units` at registration, or from Settings › Datasets afterwards (`PUT /api/registry/recording/{id}/units`,
audited, every channel together). An undeclared unit is a **warning, never a guess**: the pages draw such a recording
as stored and say "unit undeclared" instead of "mV", and the Library and Review withhold its traces. An unreadable
unit fails the `units` check. `init_db()` backfills the per-file evidence measured on 2026-09-23 onto rows that carry
no unit and no note, so a declared unit is never overwritten.

**The core never converts.** Detection code expects volts and multiplies by 1000 itself; the bridge converts only
what it draws (`webui/server/corpus.py::display_channel`), and hands the core the stored samples
(`corpus.load_native`). A producer writing channels should write `units` in the manifest — both writers here do.

## Excerpts: a subset of a registered recording is not a new recording

User decision 2026-09-21. `Mushroom_260720_0509_4hrs_CH14_fs1` (row 385; six runs and 217 detections
reference it) is a 10:1 block-mean-decimated four-hour excerpt of `L_LM_Jul_26_J_raw_fs10` CH2 at
sample 15,777,590 (`Pipelines/drop_motifs/lionsmane12.py`: r = 0.9995, single-sample peak,
neighbours 0.979 / 0.971).

**The check** (`Working/registration/excerpt.py`, run inside the recording kind's checks): for every
registered channel whose sampling rate is an integer multiple (or divisor) of the candidate's and whose
span could contain the shorter side (the shorter side ≤ 200,000 samples — an excerpt is short; a
same-length pair is a copy, not an excerpt), block-mean the longer side to the shorter side's rate
and slide the shorter along it under a normalised cross-correlation (FFT). A peak with **r > 0.99**
that beats both neighbouring lags by max(0.001, 10 × (1 − r)) marks an excerpt.

**What happens.** Two directions:

- A registered channel is an excerpt of the candidate (the 385 ↔ L_LM case): the candidate registers
  as a new recording and the *existing* row is linked — `recordings.parent_recording_id`,
  `parent_offset` (in the parent's samples), `decimation` — keeping its row and id. Datasets shows it
  as "excerpt of L_LM_Jul_26_J_raw_fs10 CH2 @ 15,777,590 · 10:1".
- The candidate is an excerpt of a registered recording: the `excerpt` check **fails** ("a subset of a
  registered recording is an excerpt, not a new recording") and registration is refused — unless the
  researcher says so (`overrides={"allow_excerpt": true}`), in which case it registers linked to its
  parent. The same rule stops the raw kind deriving a second copy of a span a parent already covers.

## Held out

`M4_aug_concat_fs1.mat` is refused by the recording and raw kinds' `held_out` check in both modes (a
registration attempt is a 422 with that check failed), and the Explore/Analyse routes refuse its rows with
423 whatever the lock setting says. The **lock** itself
(`settings.datasets.heldout.on`) governs whether the *pages* offer it; turning it off needs the
recording's display name typed exactly (`PUT /api/settings/datasets` with `confirm_name`, refused with
409 otherwise) and writes an audit entry of kind `lock`.

## Settings and the audit log

Project settings live in the `settings` table (`page, key, value_json, updated_at, actor`):
`GET|PUT /api/settings/{page}`. Every save appends an audit entry of kind `settings` naming the page and
the changed keys. The `audit_log` table (`at, kind, what, where_, route, actor, detail_json`) is
append-only — there is no update or delete anywhere in the codebase; `GET /api/audit`,
`POST /api/audit`, `GET /api/audit.csv`. Personal settings (Display, Keyboard) never reach the server:
`localStorage`.

## Adding a new kind — the checklist

1. **Decide the convention** and write it in the table above: directory, file naming, the manifest
   fields the producer must write (a kind that carries `source_file`, `channel`, `fs`, `span_start`,
   `span_end` and `config_hash` in the file needs no separate manifest).
2. **One `KindSpec` in `Working/registration/kinds.py`**, added to the `KINDS` dict at the bottom of the file
   (a spec not in `KINDS` is invisible to every route). For a kind that lands in `registered_artifacts` — every
   kind without a table of its own — call the helper:
   `KINDS["my_kind"] = _art_kind("my_kind", "My kind", ["DATA/derived/my_kind"], "<where the UI offers it>",
   "<file naming>", _scan_my_kind, _check_my_kind)`; it fills `register`, `registered_ids`, `unregister` and
   `list_registered`. The two functions you write: `_scan_my_kind(roots, conn, **kw) -> [Candidate]` (facts
   from headers only, never bulk data) and `_check_my_kind(candidate, conn, report, overrides, **kw)` (append
   `report.add(name, ok, detail)` and `report.warn(...)`; bind the recording with `_bind_recording(conn,
   report, source_file, channel)` — by content, never by a stored id; set `report.facts["parameters"]` — it
   becomes `params_json` and the sidecar's `parameters`; set `report.facts["span"]`, `["fs"]`, `["producer"]`
   when known). A kind with its own table (like `encoding` → `encodings`) fills all twelve `KindSpec` fields
   itself: `name, label, roots, table, ui, naming, scan, check, register, registered_ids, unregister,
   list_registered`.
3. **One test** in `tests/test_registration_<kind>.py` or `test_registration_artifacts.py`: scan on a
   temp tree, a broken file fails the right check, register writes the right row and the sidecar.
4. **Expose it**: it is already on `GET /api/registry/{kind}`. A *scan* button on Settings › Storage &
   backups needs two edits: a root row in `webui/server/registration.py::get_storage` (`roots = [...]`,
   id / label / path / actions) **and** the id → kind entry in `KIND_OF` at the top of
   `webui/client/src/settings/StoragePage.tsx` — without the second the modal says "this root has no
   registry kind". Then write the one-line request to the workspace that consumes it
   (`docs/prompts/wiring/requests/`).
5. **Producers write the manifest**: an HPC script that produces the kind writes the fields the checks
   read; a job that goes through `Pipelines/run_recipe` already writes `manifest.json`.

## What this machine registered on 2026-09-21

See `docs/prompts/wiring/reports/02-settings-import.md` for the list (the five recordings M1, M100,
M101_t, MJu26a, L_LM_Jul_26_J_raw_fs10 with their warnings, the excerpt link on row 385, 18 models,
10 of 13 matrix profiles — three refused for length —, 8 window matrices including the six legacy CSVs,
the catalogue spreadsheet and the drop-motif seed store) and the sampling-rate facts that
were read from the raw files rather than assumed: `M1_M100.mat::t1` and `M101_t.mat::t101` both step
0.1 s uniformly (10 Hz, read); `L_LM_Jul_26_J_raw.mat` has no time vector (10 Hz inferred);
`MJu26a.mat::t` is non-uniform (dt 0.124–2.83, median 0.138 → 7.25 Hz from the median).
