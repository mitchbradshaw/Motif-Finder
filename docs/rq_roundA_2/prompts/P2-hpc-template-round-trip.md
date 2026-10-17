# P2 — HPC template runs come back to Discovery and the Map, cached and reusable; matrix profiles over the whole span

Read [`00-common.md`](00-common.md) first. Commit prefix **`a2-p2:`**. **The researcher calls this really important.**
It is the largest prompt of the round; take the design below unless you find it wrong, and say so if you do.

## In plain words

Heavy detection runs belong on the cluster, matrix profiles over whole recordings above all. Today a template run sent
there never comes back. The website cannot show it on Runs or the Map, cannot send its detections to Review, and the
next identical run recalculates everything.

Make a cluster run come back as a real Discovery run, exactly as if it had run here. Leave its heavy intermediate
results in the step cache, so any later run of the same algorithm on the same data reuses them. Let matrix-profile
chains take the entire span: the time limit is for running on this machine, not a reason to refuse.

## What is true today (read 2026-10-17)

### A local run: what an import must reproduce

- **The bridge writes the `discovery_runs` row,** not `fanout.py`.
  - `apply_templates` → `_insert_run` creates it with status `new` and `params.route` (`webui/server/discovery.py:2392-2402,
    2624-2639`).
  - If the plan routes to the cluster, nothing else happens (`2633-2645`).
  - Otherwise `_start_sweep` runs `fanout.start`, then writes `run_group_id`, `params.run_ids`, `reused_run_ids`,
    `null.drawn` and the status (`2479-2509`).
- **`fanout.start`** (`Working/discovery/fanout.py:247-317`):
  - creates one `run_groups` row;
  - per target, calls `materialize_target`, then sets `surrogate=bool(…)`;
  - then calls `run_paired_recipe`.
- **`run_paired_recipe`** (`Working/run_groups.py:271-273, 168-185, 332-359`):
  - writes `"surrogate": true|false` into the recipe;
  - null draws strip that key, prepend `preprocessing.surrogate` with seed + i, and link back by `surrogate_of_run_id`.
- **`execute_recipe`** (`Working/execution.py`):
  - `configs` are keyed by `short_hash`: the first 8 hex of the SHA-256 of canonical `{recording_id, span, steps[,
    surrogate]}`;
  - the whole run is reused if a completed run exists for (config, recording, span) (`376-387`);
  - detections are made channel-absolute (`505-519`);
  - `artifacts` are written only through an adapter's `persist`.
- **The step cache** (`_recipe_prefix_hash`, `122-142`):
  - The key is the SHA-256 of the recipe truncated after step i. It includes `recording_id`, the span, the prefix's
    params and side inputs, the `surrogate` key, and units for unit-reading blocks.
  - A step that took more than 1.0 s is saved to `STEP_CACHE_ROOT/<hash>/<i>/` with a `step_artifacts` row.
  - A hit restores the value only: `meta` is lost and `persist` is skipped.

### A cluster run today: what is broken

- `post_slurm` (`discovery.py:3061-3102`) → `Working/hpc/job_export.py::export_job` writes an array job, one channel per
  task:
  - it ships the whole 66 MB database;
  - it is not resumable, with `--time` clamped to 20 min (`job_export.py:116-140`);
  - it runs on CPU unless a step is a CNN;
  - it runs the real chain only, with no null.
- **Each task runs `Pipelines/run_recipe/run_recipe.py`:**
  - it re-normalises through `make_recipe`, which **drops `surrogate`**, so the hash differs from the local run's;
  - it executes against the cluster's database copy, with all tasks writing to it concurrently;
  - every task writes the same `Results/manifest.json` (or `Results/Detection/matrix_profile/manifest.json`), so the
    last writer wins.
- **Nothing marks the row.** The client's `SlurmModal` (`webui/client/src/discovery/chrome.tsx:564-584`) scripts only
  `runs[0]` and sets "on cluster" in browser state only. Its toast points at the Manifest inbox, which cannot import
  this job.
- **Jobs** lists the job as `detection_chain`, "no return path" (`webui/server/jobs_routes.py:54-56`).
- **The other importers do not fit:**
  - `Working/registration/kinds.py` `hpc_result` → `manifest.import_manifest` keeps the foreign `recording_id`, writes
    no `step_artifacts`, no `run_groups` and no Discovery row;
  - `Working/training/hpc_import.py` is training-shaped.

### The pattern that works: seed search (`Working/discovery/seed_job.py`, `discovery.py:2864-3007`, `jobs_routes.py:223-297`)

- **The spec carries content, not database ids:** the exemplar's samples, channels as source file / channel /
  repo-relative npy, span, params and null.
- **The job checkpoints atomically** (`os.replace`) after every channel and every 10 draws, stops on a time budget of
  0.85 × the wall, and resubmits itself while `--status` reads incomplete.
- **Export** stamps `params.hpc` (paths, `specHash`) and status `on cluster`.
- **Import** checks the version and source file, stores the result, finds the row by identity, and then **re-runs the
  cheap part locally with `_start_sweep`**, the one existing path that writes `runs` / `detections` / `run_groups` /
  `discovery_runs`.
- **Jobs** derives written / partial / returned / imported from the result file.

### The matrix profile

- **The span cap is calibrated, not fixed:** `max_span_samples = √(900 s / k)` from `DATA/db/mp_calibration.json`
  (k = 1.957e-9, 16 CPUs), which gives 678,125 samples (`detection_matrix_profile.py:140`, `cost.py:202-211`; FLUSS uses
  the same cap).
- **It is checked before the cache lookup** (`execution.py:427` before `440`), so even a cached over-cap profile is
  refused. The calibration key includes `cpu_count` and the stumpy version, so an uncalibrated cluster is uncapped.
- **A full 721-h, 1-Hz channel is about 3.7 h on this PC.**
- **`persist` writes `mp_v2_<stem>_CH<n>_WIN<w>min.npz`, a name with no span or key** (`run_matrix_profile.py:172-180`),
  so surrogate draws and other spans would overwrite it.
- `find_reusable_profile` (`seeded_search.py:678-749`) only fills the plan's `reuse` field, and nothing consumes it.
- `HPC/Detection/mp_job.sh` is hand-written: a100, 15 min, hard-coded channel and window, one npz, no database rows.

### The wall

- **`HPC_MAX_WALLTIME_MINUTES = 20` was measured on `a100-test`.** The `cpu` partition's own limit is unverified
  (`Working/config.py:286-303`).
- **`run_recipe.py` cannot checkpoint inside a step,** and a killed run's row stays `running`.

## The design (recommended)

**The cluster computes; the import restores the cache; the existing local path writes the rows.**

1. **Export** (`post_slurm` takes the run's key, and the modal sends **every** ticked run). A new
   `Working/discovery/chain_job.py::build_spec` writes, per target:
   - the exact recipe the local sweep would execute: `materialize_target` plus the `surrogate` flag;
   - the recording **content**: local id, source file, channel, units, npy path, a sha1 of the samples;
   - the expected `config_hash` and step-prefix hashes;
   - the null settings (draws, method, seed).

   The `discovery_runs` row gets `params.hpc` and status `on cluster` **server-side**, as the seed export does.
2. **Cluster:** `python -m Working.discovery.chain_job --spec … --out … --task i`.
   - It builds a **per-task scratch SQLite** with `init_db()` and inserts the recording rows with the **local ids**, so
     every hash equals the local one. Assert it against the spec.
   - It redirects `STEP_CACHE_ROOT` and the matrix-profile `RESULTS_DIR` into `out/task<i>/`.
   - It runs `run_paired_recipe`, null draws included: the block-shuffle block depends on the real run's detections,
     so the draws follow the real run in the same task.
   - It writes `result.json` atomically: the run summaries and the cache entries made.
   - A resubmitted task reuses its own cache and completed draws, and `--status` drives the self-resubmit, as
     `seed_job` does. Per-task directories end the manifest collision, and the scratch database ends the stale
     `running` rows.
3. **Import:** one function, called from Jobs › Waiting on the cluster and from a Discovery button.
   1. Verify the `specHash`, every expected hash, and the recording content against each local id; refuse on any
      mismatch.
   2. Copy the task's cache directories into `STEP_CACHE_ROOT` and insert their `step_artifacts` rows. Normalise `\`
      and `/` in paths.
   3. Run `_start_sweep` as for a local run. Heavy steps are cache hits, cheap steps recompute, and every row is
      written by the existing code.
   4. Import only complete tasks. Record the expected task count and say what is missing.
4. **Make cached results count.**
   - Move the `max_span_samples` check **into the compute branch, after the cache lookup**, so a cached profile is
     served whatever its length.
   - Stop the plan routing an already-cached step to the cluster: use `chain.cache_status` (`webui/server/chain.py:421-433`)
     in `fanout.plan` and in the Analyse pre-check (`webui/server/app.py:270-276`).
5. **Generalise the seed-only paths:** `_seed_rows` (Jobs) and the `hpc` parts of `_run_payload`
   (`discovery.py:498-500`), so a chain job shows written / partial / returned / imported.

## Matrix profile over the whole span (the researcher's decision)

- **The cap becomes a routing limit, not a refusal.** Over the cap locally → offered as a cluster job. On the cluster
  (`chain_job`) there is no cap. Once imported, the cached profile is served locally whatever its length.
- **The wall.**
  - Check the `cpu` partition's real limit (`sacctmgr show qos`, or a deliberately long test job, both done by the
    researcher on rangpur — write the steps in your report) and record limits per partition in `Working/config.py`.
  - For a full channel, prefer the a100 with `backend: gpu_stump`. `backend` is in the hash today; measure the
    stump vs gpu_stump difference on a synthetic span. If it is within float noise, treat `backend` as execution-only
    (excluded from the hash, recorded in meta); otherwise keep separate cache entries. Say which, and why.
  - If neither fits the wall, **chunk** the profile: AB-joins over blocks as separate checkpointed tasks, merged by the
    elementwise minimum, with indices kept. Prove on a synthetic span that it equals the one-shot profile.
- **Persist names carry the step's prefix hash**, as the window matrix does, so draws and other spans never overwrite
  a profile.
- **`find_reusable_profile`:** wire it into the run, or remove the dead `reuse` field now that the step cache does the
  job. Say which.

## Also fix on the way

- **`SlurmModal`** scripts every ticked run, not `runs[0]`. Its toast points at where the results really come back.
- **The chain job** honours Settings › Nulls draws (now allowed down to 1).
- **Store-reading steps** (ones that read the database: a `library_exemplar` side input, a window pool) are refused
  for export, named, because the cluster's database is a scratch copy.

## Tests (test-first)

- **Round trip, in-process, temp dirs:**
  1. A synthetic recording in database A: plan a cheap chain (detrend → noise_threshold) and a matrix-profile chain,
     export the spec.
  2. Run `chain_job` for every task against scratch databases.
  3. Import into database A.
  4. Check: the Discovery row is `done`; the `runs` / `detections` rows equal a local run of the same plan (same config
     hashes, same detections); the cache entries are present; a second local application **reuses them** (assert the
     heavy step is a cache hit and nothing recomputes).
- **Refusals:** recording content ≠ local id; `specHash` mismatch; incomplete tasks.
- **The cap:** an over-cap matrix-profile span locally routes to the cluster instead of refusing, and an over-cap
  profile in the cache is served.
- **Hash equality:** the `surrogate` flag survives the cluster recipe, and units-reading blocks hash the same.
- **Resume:** a task killed between steps resumes from its own cache.
- **Persist:** two spans and a surrogate draw of one matrix-profile chain write three different files.

## Acceptance

- [ ] **The full loop works:** a template run sent to the cluster comes back as a Discovery run on Runs, Compare,
      *Send to Review*, Scoreboard and the Map, indistinguishable from a local run.
- [ ] **No recalculation:** a later identical run, or a different threshold on the same profile, reuses the imported
      heavy steps.
- [ ] **Whole span:** a full-channel matrix-profile chain can be exported, run (within the wall, or chunked and
      resumable) and imported.
- [ ] **Jobs** shows chain jobs' states and imports them.
- [ ] **Smoke states** in `webui/smoke_pages/a2_p2_hpc.json`: a run marked "on cluster" after export; an imported
      chain run on Runs and on the Map.

**Report:** the researcher's step-by-step for one real export → rangpur → import, including what to copy each way.
