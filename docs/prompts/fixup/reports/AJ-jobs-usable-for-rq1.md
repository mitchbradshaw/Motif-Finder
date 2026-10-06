# Report — Fixup AJ: the Jobs page, to the point where RQ1's cluster jobs can be run from it

Run 2026-10-07 on `main`, in the main checkout, beside the smoke-stability session. Commit prefix `fixup-aj:`. Every
bridge ran `--sandbox` on port 8796 with a private client build of `git archive HEAD`; the shared `webui/client/dist`
was not rebuilt, port 8765 was not used, the real `DATA/` was only read (channel sizes). The site never logged in to or
submitted anything to the cluster. `M4_aug_concat_fs1.mat` stays refused (the inbox refuses a path naming it, 423).

## In plain words first

Think of Jobs as the post room for long work. Before this ticket the room was a stage set: the parcels on the shelves
were props. Now three shelves are real.

1. **Running here** — everything this computer is doing for you, straight from the bridge's own logbook: training a
   model, building window sets and trees, the blind-label comparison, imports. Each row says what it is, how far it
   got, when it started, how long it took, and — if it broke — the error with the full technical trace.
2. **SLURM scripts written** — every job folder the site packed for the university cluster (the CNN on the cluster
   categories, and Ward over every training window). Each row says which recipe it was packed from (a short
   fingerprint), when, how much must be copied to the cluster and, opened, every file and its size and the exact
   `sbatch` line. Its state is one of: *written* → *results copied back* → *results imported* (with a link to the run)
   or *import refused* (with the reason).
3. **Manifest inbox** — when the cluster's `out/` folder has been copied back, hand the job folder to the inbox (or
   press *Import results* on its row). It is checked by **the very same function** as the command line
   `python -m Working.training import-results` — not a copy of it — and either recorded (the run opens in Models ›
   Results) or refused with a reason and nothing stored.

Below those, the rest of the page the specification describes — paused runs waiting on a stage's cluster result,
hand-marked cluster jobs, review queues, today's finished list — is still fixture data, under its own **demo data**
chip. Models' link now says *Jobs · running here, SLURM scripts, results inbox* instead of *Jobs (demo page)*.

## 1. The researcher's walk (sandbox, `webui/screenshots/fixup/AJ/`)

The sandbox was a copy of AI's lab database (pool `712f477b262b2fd8`, its kept tree, the forest run 399, AH's
placeholder mapping at k = 8) with AI's smoke run 401 taken out, so that handing back the smoke's folder is a first
import (`prep_db.py`). Scripts: `walk.py`, `reshoot.py`; results `walk-1b.json`, `walk-2-3.json`; 0 console errors.

| step | what happened | shot |
|---|---|---|
| 1 | Models › Launch, arm B.2, *Train locally* → Jobs: **job 64 · B.2 forest · running**, its progress message, started 00:43:21 | `01-jobs-forest-running.png` |
| 1 | the same row **finished** (run 402), took **33 min 21 s**; opened: started, finished, last message, no error; its link opens Models | `02-jobs-forest-finished.png` |
| 2 | Launch with the CNN chosen → *Create SLURM script* (job 65, 2 min 39 s) → Jobs lists **B.2 CNN · trained on the cluster categories, recipe `c83b02ad`, written 01:19:46, 441.4 MB to copy, *written***; opened: the job folder (442 KB, never `cache/` or `out/`) and the 32 channel arrays with their sizes, the `sbatch` line | `03-…`, `04-jobs-cnn-script-written-what-to-copy.png` |
| 2 | the Ward script, written by the cluster block's route (the Ward card's call): **Ward over every training window, `ee39ae58`, 50.3 MB, *written*** (29,370 windows) | `00-jobs-overview.png` |
| 3 | AI's smoke folder with its `out/` copied back "as if from the cluster" → its row turns **results copied back · not imported** | `05-jobs-results-copied-back.png` |
| 3 | Manifest inbox → *use this folder* → *Import* → job 66 → **Results imported · imported as run 403 · B.2 CNN fusion · pool_712f477b v1 · k=8 · smoke** → *Open in Models › Results* → `#/models/results/b2/403` (AH's blind view of the run) | `06-…`, `07-inbox-results-imported.png`, `08-models-results-the-imported-run.png` |
| 3 | back on Jobs the smoke row reads **results imported · run 403**, *Open in Results* | `09-jobs-row-results-imported.png` |
| 3 | **a folder from a different recipe**: the full CNN job's folder with the smoke's `out/` copied into it by mistake → *Import results* → job 67 → **import refused**: *"out/done.json was made from recipe b6489eeb (status complete), not this job's recipe c83b02ad: these are not this job's results"*; no configs or runs row carries `c83b02ad` | `10-jobs-wrong-recipe-refused.png`, `11-inbox-attempts.png` |
| — | the demo half under its chip | `12-jobs-the-demo-half-keeps-its-chip.png` |

**Said plainly:** the forest took 33 minutes here, against 10.5 minutes for the same training (run 61) yesterday. The
machine was shared with the other session's smoke walks against port 8791 for the whole of it (request file below); the
first walk script's 30-minute wait expired before the forest finished, so the *finished* shot was taken by a second
short run (`walk.py 1b`). A Ward import was not walked (nothing ran Ward on a cluster); its row's link to the Analyse
chain is built from the pool key and the latest B.2 template on that pool and is not exercised by a test.

## 2. What is real on Jobs now, and what still wears `demo data`

| part | state | read from |
|---|---|---|
| Running here — every local job (training, chain runs that build trees, window sets, blind comparison line, imports, Discovery sweeps, Library work): kind, stage, state, progress, started, duration, cancel (non-chain), link to its workspace, error + traceback | **live** | `GET /api/jobs` (the job table, restart-safe), polled every 2 s while something runs, 8 s otherwise |
| SLURM scripts written — CNN and full-pool Ward job folders, the local smoke's folder; recipe hash (and whether `recipe.json` still matches it), written-at, copy list and size, `sbatch` line, `out/done.json`, state | **live** | `GET /api/hpc/exported` → `Working.hpc.job_export.list_exported_jobs` (the folder's own `job.json` is the record — no new table) |
| Manifest inbox — path or *use this folder*, import, outcome, attempts | **live** | `POST /api/hpc/inbox/import` (a local `import` job calling `hpc_import.import_results`), `GET /api/hpc/inbox` |
| Paused runs waiting on a stage result; *Upload results and continue*; the paused-run page | demo | fixtures |
| Hand-marked cluster jobs (`j-02xx`), their page, *Mark…*, New SLURM script modal | demo | fixtures |
| Review queues on Jobs, *Finished and cancelled today* | demo | fixtures |
| The inbox's "stage results for paused runs" list | demo (own chip) | fixtures |

**Where the record of what was written lives:** AI's exporters already write `job.json` (`kind`, `recipe_hash`,
`created_at`, the channel arrays with their bytes) into every job folder, under `HPC/Training/generated/` in project
mode (`<runtime>/hpc/training/` in a sandbox; the local smoke under `smoke/`). Jobs reads those folders; whether a job
is imported is read from the database by its recipe hash (the identity `import_results` uses); a refusal is the inbox
job's error in the `jobs` table. So the CLI and the page see the same state, and nothing was added to the schema.

**One implementation, two callers:** the inbox job looks `hpc_import.import_results` up at call time; the route test
monkeypatches that one function and sees the page's import go through it. No check was reimplemented;
`hpc_import.py` was not changed.

**Came for free / did not:** Discovery's sweeps appear in *Running here* (they are jobs in the same table). Discovery's
seed-search SLURM scripts (`fixup-rq2`) do **not** appear among the scripts — they are written elsewhere in another
shape; left for the page's own prompt.

## 3. Built

| where | what |
|---|---|
| `Working/hpc/job_export.py` | `EXPORTED_KINDS`, `describe_job_dir`, `list_exported_jobs` (appended; headless) |
| `webui/server/jobs_routes.py` (new) | `GET /api/hpc/exported`, `GET /api/hpc/inbox`, `POST /api/hpc/inbox/import` |
| `webui/server/app.py` | one `include_router` (shared, append-only, own hunks) |
| `webui/client/src/jobs/LiveJobs.tsx` (new) | the three live parts and the shared import follower |
| `webui/client/src/jobs/AllPage.tsx`, `jobs.css` | the live half on top; *The rest of the Jobs page* with its demo chip; the fixture local rows (and the `local` filter) removed |
| `webui/client/src/api/jobs.ts` | live reads beside the fixture ones (`api.ts` untouched) |
| `webui/smoke_pages/zzzzzzzzz_aj_jobs.json` (new) | five states (after AI's): running here, the CNN script with what to copy, the smoke folder imported, the inbox refusal, the Models link |
| tests | `tests/test_hpc_exported_jobs.py` (4), `tests/test_webui_jobs_inbox.py` (5). Red commit `a8c29e6` (8 red; the local-jobs test passed on arrival — it pins the existing `/api/jobs` read the page relies on) |

**Files outside the expected area:** `webui/client/src/models/chrome.tsx` (the link's words, named by the ticket);
`docs/prompts/fixup/requests/AJ-to-smoke-stability.md`.

**Behaviour deliberately changed:** `webui/smoke_pages/jobs.json` (the other session's file, untouched) state
`jobs.all--local` expects the fixture local row `a-0101`; that row is replaced by the live list, so the state fails by
design until its expectation changes — the one-line replacement is in the request file.

## 4. The gate

1. **`npx tsc -b` clean; `vite build` green** — into a private directory from `git archive HEAD` (last client commit
   `f185a26`); `npm run build` was not run because it writes the shared `client/dist`.
2. **`pytest -n 4` (conda, 12 min): 2,407 passed, 35 skipped, 0 failed** — the failure set is empty;
   `tests/test_import_boundaries.py` passes (the new core code imports no UI or web library).
3. **Route tests (`webui/.venv`, every `tests/test_webui_*.py`, `-n 4`, 9 min): 460 passed, 3 xpassed, 1 failed** —
   the standing `test_the_scoreboard_cells_are_the_tables_own_numbers`. My 5 route tests pass.
4. **Smoke — one full walk on a fresh `--sandbox` bridge** (port 8796, private build, started after *stumpy JIT warm*,
   02:00–02:51; the process check found no other smoke or pytest, and none started during it): **658 screenshots, 60
   failures. All 5 AJ states pass, all 6 AH and all 3 AI states pass.** The 60, sorted:
   - **mine — 42 Jobs states and the walk's console-error check (2 errors, the same throw), one cause, fixed:** `?filter=local` threw on the label of a filter I had removed
     (`jobs.all--local` tripped the render-error card, 2 console errors), and because the walk moves by hash inside
     one document the tripped boundary blanked every Jobs state after it. Fixed in `f185a26`; the other session had
     already re-pointed `jobs.all--local` at the live table on my request (`b6d1837`). **Jobs re-walked on the fixed
     build: 46 / 0; AJ's states 5 / 0.**
   - **the 5 standing** — `discovery.runs--default` and the four Settings registration Check states;
   - **cold-start, clear warm:** Explore 2 (`corpus--default`, `cross-channel--as-recorded`) → **54 / 0**;
     Interrogation 6 → **58 / 0**;
   - **still failing warm, on pages this ticket does not touch** (the other session is working on exactly these):
     `library.window-sets--empty-or-listed` (14 rows, the table missing), `discovery.compare--unpick-b`,
     `zzz_surrogates: discovery.runs--fixup-t-chip-names-a-count-per-run-kind`, and Settings (`shell--discard` in the
     walk; `shell--save-writes-the-settings-table` and `nulls--unsaved` in the re-walk). **Said plainly:** the
     Discovery and surrogates re-walks overlapped the start of the other session's own walk (03:08), so their warm
     result is not clean; none of them is on a page or route I changed.

   Separately, before the walk: the researcher's walk above, 0 console errors.

## 5. Items left for Jobs' own prompt

- Paused runs and *Upload and continue* (`paused_run_id`, the paused-status vocabulary still a guess — `09-jobs.md` J3).
- Cluster-job status marks (submitted / running / finished by hand) for the exported rows; today the row's state is
  only what the folder and the database show.
- Discovery's seed-search SLURM scripts in the same list (they would need a `job.json` of the same shape).
- A between-target cancel for `fan_out_recipe` (J6); a chain run's cancel from Jobs (Analyse has it).
- The review-queue rows from the Review store.
- Watching a folder for returned results (the spec's "watching ./cluster_out every 5 min"): the inbox imports on demand.

## 6. Question for the researcher

**Where should the cluster's results land on this computer?** *In plain words:* when a cluster job finishes, you copy
its `out/` folder back. The inbox needs to be told which job folder it belongs to. Today you copy it back **into the
same job folder** the site wrote (`HPC/Training/generated/b2cnn_…/out/`), the row turns *results copied back*, and one
click imports it. The alternative is a single drop folder that the site sorts out by fingerprint.

- **(a)** keep it as built — copy `out/` into the job folder; the row shows it and *Import results* is one click;
- **(b)** add a drop folder (e.g. `HPC/returned/`) that the inbox scans and matches to its job by recipe hash.

*My recommendation:* **(a)** — it is what the scripts' own instructions already say, it needs no matching rule, and the
fingerprint check already refuses a wrong folder with the reason (step 3 above).
