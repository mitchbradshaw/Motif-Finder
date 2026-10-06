# Report — Fixup AI: the site writes a SLURM script that trains a CNN on the cluster categories

Run 2026-10-06 on `main`, in the main checkout. Commit prefix `fixup-ai:`. **All six items of the ticket are built**:
the CNN arm in the core and its local smoke; *Create SLURM script* for it on Models › Launch; the label-shuffle null
as an array job (off by default); one import function for returned results; the full-pool Ward script from the
cluster block. Nothing was submitted to the cluster. Every bridge ran `--sandbox` on my own port with a private client
build of `git archive HEAD`; the shared `webui/client/dist` was not rebuilt; port 8765 was not used; the real `DATA/`
was only read; `M4_aug_concat_fs1.mat`, window set 1 and run 79 were not touched. The measurements below were made on a
**copy** of AH's walk sandbox (pool `712f477b262b2fd8`, its kept tree, the placeholder mapping at k = 8) in my
scratchpad.

## In plain words first

The forest learns the piles from 26 summary numbers of each window. The CNN learns them from a **picture** of each
window instead — the same pictures the old manual-label CNNs looked at (fusion: three ways of drawing a signal as a
square image, put in the red, green and blue channels). Everything else is the forest's: the same windows, the same
tree, the same cut, the same interesting / not mapping, the same exam windows. So if the CNN and the forest disagree,
the model is the only thing that differs.

Teaching a CNN on 30,000 pictures is a job for the university cluster, so the site now **packs a job for it**: a folder
holding every window's position in the raw recording, its pile, and the recipe; a list of the recording files the job
reads (with their sizes); and a SLURM script that draws the pictures, trains, and predicts the test and exam windows —
stopping every 20 minutes (your account's limit) and resubmitting itself until it is done. You copy the folder and the
recordings to the cluster, type `sbatch`, and copy the `out/` folder back. Then **one command**,
`python -m Working.training import-results <folder>`, checks that what came back is what was sent (by the recipe's
fingerprint) and files it as a run. The run then appears in Models › Results beside the forest run, and you can label
it blind exactly as you do the forest's (AH).

Before you spend a cluster hour, **Run the local smoke** does the whole round trip here on 480 windows for one epoch:
on the sandbox pool it took **5.8 minutes** and its run appears in Results. A second script, from the Shape clustering
page, runs **Ward on every training window** (29,370 here, 10 GB of memory) instead of the 20,000 sample this machine
can afford.

**Fusion is built**, not GASF: the fusion *training code* is the GASF code with three colour channels and is sound;
`fusion_cnn.pth`'s single output is a fact about the folder it was trained from (see §3).

## 1. The local smoke on the sandbox pool (run 401)

`webui/screenshots/fixup/AI/lab_smoke_and_full_pool.json`, `lab_smoke_log.txt`. Fusion, EfficientNet-B0 with ImageNet
weights, one epoch, batch 16, CPU (4 threads — the machine was shared), the cut k = 8 with **AH's placeholder mapping**
(clusters 1 and 2 interesting): the numbers prove the path, not the model.

| | |
|---|---|
| windows | **480** — 240 training (192 fitted for the diagnostic, 48 held back — the forest's seeded 20 %, the same rule) + 120 test + 120 exam windows, seeded |
| export (the pool's windows and re-cut bounds, the cut, the job directory) | 137 s (most of it Trace shape re-reading 60,000 windows to find their bounds) |
| **encode** (480 fusion images at 224 px, cached on disk) | **140 s** — per window: **1 min 74 ms · 10 min 80 ms · 30 min 695 ms** (the 30-minute fusion image is a 1,800 × 1,800 recurrence matrix resized with anti-aliasing) |
| diagnostic phase (1 epoch on 192 + scoring the 48) | 30 s |
| final phase (the refit on all 240) | 32 s |
| predict 240 windows | 8 s (29 images / s) |
| training rate on this CPU | **7.2 images / s** |
| the whole round trip (export → run → import) | **349 s** |
| diagnostic | accuracy 0.10, macro F1 0.10 against a largest-cluster 0.19 — one epoch on 192 pictures has learned nothing yet, as expected; *a diagnostic, not a result* |
| exam (i) · (ii) predicted | 120 (interesting 79 / not 41) · 120 (58 / 62), "predicted · not yet labelled" |
| imported as | run 401, `B.2 CNN fusion · pool_712f477b v1 · k=8 · smoke`, results in the forest's JSON + parquet shape; listed by `shape_forest.list_runs` with model *CNN · fusion · EfficientNet-B0 · 1 epoch · smoke* |

## 2. The full pool on the cluster: the job, what to copy, the estimate

The same recipe without the smoke (`c83b02ad`), exported in 155 s:

| | |
|---|---|
| windows | **54,281** (the 60,000 of the pool after the noise floor and the centring's near-duplicates): **29,370 training** · 24,911 predicted (validation, test, exam); 1 min 17,464 · 10 min 19,189 · 30 min 17,628 |
| what to copy | the job directory (**0.45 MB**: `recipe.json`, `job.json`, `windows.npz`, the scripts) + **32 channel arrays** (16 × 20.8 MB M2_aug, 16 × 8.1 MB M2) — **441 MB in all**, plus the code (git pull). The page lists every file and its size |
| image cache on the cluster | **8.2 GB** (54,281 × 224 × 224 × 3 bytes), in `<job>/cache/`, never copied back |
| **estimate** (labelled on the page as one) | **about 1.0 h of work → about 4 chained 20-minute jobs** (the chain is capped at 10) |
| · encode | 4.2 h of CPU (this machine's measured per-window times × the window counts), **31 min over the job's 8 CPUs** — assumed as fast per core as this machine |
| · train | 634,392 images (12 epochs × (23,496 diagnostic fit + 29,370 refit)) at **400 images / s on an A100 — ASSUMED, not measured**: 26 min. The first cluster run prints its own rate per epoch, and once its results are imported the estimate uses it |
| · predict | 95,399 images (the hold-back each epoch + the predicted windows): 1.3 min |
| on this CPU instead | the training alone would take ~24 h (7.2 images / s) — which is why it is a cluster job |
| the label-shuffle null (off by default) | 5 full trainings, one array task each, **~1.1 GPU-hours** in all (estimate); submitted after the main job (`--dependency=afterok:<id>`), it re-uses the image cache |

### How the estimate and the script are sized

- `--time` is the account's 20-minute ceiling (`HPC_MAX_WALLTIME_MINUTES`; the estimate × 3 is clamped to it);
  the run stops itself 3 minutes before that (`--deadline-min 17`) between encode chunks or epochs, with a
  checkpoint per epoch and the encoded images on disk, so the next job resumes where it stopped.
- `cnn-status`'s **exit code** decides the resubmit (0 complete, 1 work remains, ≥ 3 unreadable — never a text
  match), capped at twice the expected job count (≥ 6). **A crashed run stops the chain** instead of resubmitting a
  crash (found while reading the first script; fixed in `a33684b`).
- The GPU: `--partition=a100 --gres=gpu:a100`, `module load cuda/12.2`, `conda activate torch_env` — the existing HPC
  exports' lines. The first command checks the environment (`torch, torchvision, numpy, scipy, skimage, PIL,
  matplotlib`) and names a missing package before anything runs.

## 3. Which encoding, and the state of the fusion training path

**Built: fusion** (GASF, GADF and recurrence as R, G, B), with GASF, GADF and recurrence alone selectable on Launch.

**Is the fusion training code sound?** Yes — as sound as the GASF code, because it is the same code.
`Working/Catalogue/cnn/cnn_rangapur.py` trains all four encodings through one function; fusion differs only in
`is_rgb=True` (no grey-to-three-channel step). Two of the three fusion checkpoints in `MODELS/` are two-class and work
(AH). **`fusion_cnn.pth`'s one output class comes from the data folder, not the code**: the network's class count is
`len(ImageFolder(root).classes)` — the number of class sub-folders that exist — so a fusion folder holding one class
folder at the time (the file is 20 March, the oldest; the module's own docstring records an earlier folder layout that
fused class and encoding into one folder name) silently makes a one-output model. Nothing in the code warns about
that; my arm cannot hit it (the class count is the recipe's k and every cluster is checked).

What I did **not** reuse from that file, and why: its training loop reads PNG folders, splits at random (it cannot
keep the forest's hold-back), cannot stop at a deadline, and applies **single-axis flips** — a Gramian or recurrence
image flipped on one axis is not the image of any signal (flipping both is time reversal). My arm uses the same network
class (`EEG_CNN`, so the trained B.2 model loads with `apply_cnn.load_model` like the old ones), the same encoding
function (`apply_cnn._window_to_pil`) and the same transform (resize to 224, normalise 0.5 / 0.5), with its own loop:
cluster classes, the hold-back, a checkpoint per epoch, a deadline, no augmentation.

**The raw-input rule (2026-10-06)** is pinned: each window's raw samples at its re-cut bounds — 60, 600 or 1,800
samples — give the n × n image, and that **image** is resized to 224 × 224; the signal is never resampled
(`test_a_window_becomes_the_image_the_manual_label_cnns_were_fed`). The recipe says so in `inputs.images`.

**The CNN's own settings (mine to state):** EfficientNet-B0 with ImageNet weights, 224 px, 12 epochs, batch 128,
Adam lr 1e-3 with a cosine schedule (the manual-label CNNs' optimiser and rate), cross-entropy with **balanced class
weights** (the forest's `class_weight="balanced"`), seed 42, no early stopping (the hold-back stays a diagnostic), no
augmentation, **refitted on every training window** after the diagnostic phase — as the forest's final model is — so the
two arms train on the same windows. Mixed precision on the GPU.

## 4. A CNN run reads in Results and AH's blind view unchanged

The import writes the forest's results JSON (the same top-level keys, `exams` i and ii "predicted · not yet labelled",
the diagnostic, the tree, the mapping) and the forest's predictions parquet (the same twelve columns, one row per
non-training window). What changed in the readers is **which kinds count as B.2**: `shape_forest.B2_KINDS` (forest +
CNN) in `_runs` (so `list_runs` and `frozen_for` see a CNN run — a blind label on it freezes the pool for the forest
too), and one line in `blind._run_results`. Pinned by
`test_a_cnn_run_is_read_by_the_blind_queue_and_scores_unchanged_and_freezes_the_pool`: AH's `make_queue`,
`write_verdict` and `score` run on an imported CNN run unchanged, and the first label freezes the pool. In the browser:
Results' B.2 list gained a **model** column and *train a CNN on this* (Launch on the same template and pool, the CNN
chosen); a CNN run opens AH's blind view (smoke state 3).

## 5. The import function (what `AJ` calls)

```python
from Working.training.hpc_import import import_results, ImportRefused
import_results(conn, job_dir, *, root, tree_root=None, where=None) -> dict
#   {"kind", "run_id", "created", "config_hash", "results_path" | "tree_dir", "name", "message"}
```

CLI: `python -m Working.training import-results <job dir> [--db DATA/db/annotations.sqlite] [--root
DATA/derived/training] [--tree-root DATA/derived/shape_trees]` (exit 0 imported or already imported, 2 refused, 3
frozen). It dispatches on `recipe.json`'s kind (the B.2 CNN or the full-pool Ward) and **validates**:

1. `recipe.json`'s short hash = the hash the job was written with (`job.json`) = the hash the results were made from
   (`out/done.json`, status complete) — an edited recipe or another job's results are refused;
2. the windows are the recipe's (`windows.npz`'s content key is in the recipe, so it is covered by the hash);
3. the pool is in this database under the same key, and every recording the job names is the same file and channel;
4. the predictions are one row per non-training window of the job, probabilities over clusters 1..k, finite;
5. the cut and mapping are not a change on a pool that already has a test score (`CutFrozen`); a Ward tree is refused
   outright once the pool is scored (a new tree renumbers every cluster);
6. idempotent: the same recipe hash already imported returns that run (`created: false`).

It records a `configs` row (the recipe), a `runs` row and `artifacts` (results JSON, `model.pt`, the predictions; the
null's predictions when present), copying what it keeps out of the job directory into the training root. Pinned by
four tests (records, refuses × 4, frozen, CLI).

## 6. Ward over every training window

The Shape clustering page has *Create SLURM script · Ward over every training window*: it copies the Trace shape
vectors (`shapes.npz`, 52.7 MB here) into a job directory and writes a CPU script that runs **the same function**
(`shape.cluster_shapes` with `sample=None`) and writes **the same artifact** (`tree.npz` + `manifest.json`). The import
keeps it under the key the block computes for "sample = every training window" (`shape.tree_key(shapes, None, seed)`),
so setting the block's sample to 0 re-uses it instead of building it here; the cut and the mapping must then be chosen
again (a new tree numbers its clusters anew). Round trip pinned on a small synthetic pool
(`test_the_full_pool_ward_round_trip_lands_where_the_cluster_block_reads_it`, through `csc.tree_for`).

**Memory, and how I sized it:** the condensed distances of n windows are n(n − 1)/2 float64 values — about 4 n² bytes,
14.4 GB at 60,000 as the ticket said — but scipy's Ward works on a **copy**, so the peak holds two (AG measured 3.07 GB
at 20,000 against 3.2 GB predicted). Request = (2 × 8 × n(n − 1)/2 + n × 256 × 12 + 1.5 GB) × 1.2: **10 GB for this
pool's 29,370 training windows** (38 GB if a pool had 60,000). Time: AG's 57 s at 20,000 scaled by n² — about 2 min.
Partition **`largecpu`**, `--mem=10G`, `aeon-env`. **Unverified:** `--mem` was refused twice on `cpu` (HPC/README.md);
the script says what to do if `sbatch` answers *Memory specification can not be satisfied* (`sinfo -o "%P %m %c"`).

## 7. On the cluster, step by step (the researcher)

The Launch page prints these with the real paths after *Create SLURM script*. In PROJECT mode the job lands in
`HPC/Training/generated/b2cnn_<encoding>_<hash>/`.

1. **Code:** commit and push here; `git pull` in `/home/Student/s4699158/CNN`. (The job directory itself can travel by
   git too — its `cache/` and `out/` are ignored.)
2. **Data:** copy the job directory and the listed channel arrays to the same repo-relative paths on the cluster, e.g.
   `scp -r HPC/Training/generated/b2cnn_fusion_<hash> s4699158@rangpur.compute.eait.uq.edu.au:CNN/HPC/Training/generated/`
   and `DATA/derived/channels/M2_aug_concat_fs1/CH*.npy`, `DATA/derived/channels/M2_concat_fs1/CH*.npy` likewise
   (441 MB; skip any already there).
3. **Once, on the login node:** `conda activate torch_env && python -c "from torchvision.models import efficientnet_b0,
   EfficientNet_B0_Weights as W; efficientnet_b0(weights=W.DEFAULT)"` — caches the ImageNet weights (compute nodes
   may have no network; the job names this if they are missing).
4. From the repo root: **`sbatch HPC/Training/generated/b2cnn_fusion_<hash>/b2cnn_fusion_<hash>.sh`**. Optional, the
   null: `sbatch --dependency=afterok:<that job id> …_null.sh`.
5. Watch `squeue -u $USER` and `logs/b2cnn_fusion_<hash>_<jobid>.out` (each epoch prints its loss and images / s).
   The chain resubmits itself; *Complete* ends it.
6. Copy `HPC/Training/generated/b2cnn_fusion_<hash>/out/` back into the same folder here (not `cache/`).
7. Here: **`python -m Working.training import-results HPC/Training/generated/b2cnn_fusion_<hash>`** → the run is in
   Models › Results beside the forest run (same windows, same cut); label it blind there.

The Ward job is the same with its own folder and `sbatch HPC/Training/generated/ward_full_<hash>/ward_full_<hash>.sh`.

## 8. The scripts as written

Project-mode copies (paths repo-relative) in `webui/screenshots/fixup/AI/scripts/`: `b2cnn_fusion_c83b02ad.sh`, its
null `b2cnn_fusion_c83b02ad_null.sh`, `ward_full_ee39ae58.sh`. The CNN script's working part:

```bash
#SBATCH --time=00:20:00
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:a100
#SBATCH --partition=a100
# estimate: about 1.0 h of work in all, so about 4 chained job(s) of 20 min -- an estimate, not a measurement
CHAIN_INDEX="${1:-1}"
MAX_CHAIN=10
module load cuda/12.2
source ~/miniconda3/etc/profile.d/conda.sh
conda activate torch_env
python -c "import torch, torchvision, numpy, scipy, skimage, PIL, matplotlib; print('environment ok')" || { ...; exit 4; }
python -m Working.training cnn-run --job HPC/Training/generated/b2cnn_fusion_c83b02ad --workers "$SLURM_CPUS_PER_TASK" --deadline-min 17
RUN=$?
if [ "$RUN" -ne 0 ]; then ... exit "$RUN"; fi            # a crash stops the chain
python -m Working.training cnn-status --job HPC/Training/generated/b2cnn_fusion_c83b02ad
STATUS=$?                                                # 0 complete · 1 work remains -> resubmit · >=3 stop
...  sbatch HPC/Training/generated/b2cnn_fusion_c83b02ad/b2cnn_fusion_c83b02ad.sh "$NEXT"
```

The Ward script: `--partition=largecpu`, `--mem=10G`, `--cpus-per-task=4`, `--time=00:20:00`, `conda activate
aeon-env`, `python -m Working.training ward-run --job HPC/Training/generated/ward_full_ee39ae58`, then `ward-status`.

## 9. What was built

| where | what |
|---|---|
| `Working/training/shape_cnn.py` (new) | `make_recipe` (the forest's recipe, the CNN in place of the forest; `inputs.images`), `export_job` (the job directory, the copy list), `latest_measurements`, `estimate`, `run_local_smoke` |
| `Working/training/cnn_job.py` (new) | the cluster side, numpy-only at import: `encode_window`, the cached encode (chunks, workers), the diagnostic and final phases, predict, `job_status`, `run_null` / `null_status` |
| `Working/training/full_ward.py` (new) | `memory_estimate`, `export_job`, `run_job`, `job_status`, `full_tree_key` |
| `Working/training/hpc_import.py` (new) | `import_results`, `ImportRefused` |
| `Working/training/__main__.py` | `cnn-run`, `cnn-status`, `cnn-null`, `cnn-null-status`, `ward-run`, `ward-status` (no database), `import-results` |
| `Working/hpc/job_export.py` | `export_cnn_job`, `export_ward_job` |
| `webui/server/cnn_routes.py` (new) | `POST /api/models/b2/cnn/slurm` (a job), `POST /api/models/b2/cnn/smoke` (a job), `POST /api/shape/trees/{key}/ward-slurm`; the setup's `cnn` block |
| client | `models/B2Launch.tsx` (the model choice, CNN settings, *Run the local smoke*, *Create SLURM script* and its panel), `models/HpcScript.tsx` (new), `api/cnn.ts` (new), `analyse/views/TreePage.tsx` (the Ward card), `models/B2Blind.tsx` (model column, *train a CNN on this*) |
| smoke | `webui/smoke_pages/zzzzzzzz_ai_cnn_slurm.json` — three states (they run after AH's, which build the B.2 run; `--only zzzzzzz` walks both) |
| tests | `test_training_shape_cnn.py` (15), `test_job_export_cnn.py` (3), `test_webui_cnn_slurm.py` (4). Red commit `0a305e5` |

**Files outside the expected area, and why:**

| file | why |
|---|---|
| `Working/training/shape_forest.py` | `B2_KINDS` so one list / one freeze covers both models; `model_label` in `list_runs` |
| `Working/training/blind.py` | one line: `_run_results` accepts either B.2 kind |
| `webui/server/shape_routes.py`, `webui/server/app.py` | the setup's `cnn` block and its `slurm` text; one `include_router` |
| `webui/client/src/api/shape.ts`, `models/B2Blind.tsx`, `analyse/views/TreePage.tsx` | `B2Run.kind/model/smoke`, `B2Setup.cnn`; the Results strip; the Ward card on the cluster page |
| `.gitignore` | a job directory's `cache/` (GBs) and `out/` under `HPC/Training/generated/` |

No Jobs or Manifest-inbox page was touched (AJ), no `MODELS/` checkpoint was retrained or overwritten, the cut, the
mapping and the blind sample are untouched. The other session's files (`fixup-rq2:`) were not touched.

## 10. Items left

- **The real run:** nothing ran on the cluster. The GPU rate (400 images / s) is an assumption until then.
- **Encoding on a GPU node** holds the A100 for ~31 min while the CPUs draw pictures. A CPU job that encodes first,
  then the GPU job (`--dependency`), would free it; one more script. Not built.
- **The CNN on the forest's blind labels.** AH's sample is per run; a CNN run gets its own blind queue. Both models
  predict every test and exam window, so the CNN could be scored on the windows you already labelled for the forest
  (question 2).
- **The label-shuffle null's scoring:** the 5 shuffles' predictions are imported and listed, not yet scored against
  the blind labels (AH's score has no slot for them).
- **`--mem` on `largecpu`** is unverified (§6).
- The torch_env package list on the cluster is unknown (the script checks it first).
- **Export reads the pool's windows again** (Trace shape, ~2 min); AG's "cache the raw-window features per pool" item
  is unchanged (my image cache is per job, on the cluster).

## 11. The gate

1. **`npx tsc -b` clean; `vite build` green** — into a private directory from `git archive HEAD` (rebuilt after the
   last client commit `b3e643a`); the shared `client/dist` was not rebuilt.
2. **`pytest -n 4` (conda, 11 m 29 s): 2,397 passed, 33 skipped, 0 failed** — the failure set is empty.
   `tests/test_import_boundaries.py` passes; `test_the_core_imports_no_ui_library_and_no_torch_until_a_job_runs`
   pins that the four new modules and `job_export` import no UI library, no FastAPI **and no torch** at import time
   (the suite needs no GPU: the torch tests run on the CPU with an untrained 32-pixel network, and `importorskip`
   where torch is absent).
3. **Route tests (`webui/.venv`, every `tests/test_webui_*.py`, `-n 4`, 11 m): 454 passed, 3 xpassed, 1 failed** —
   the standing `test_the_scoreboard_cells_are_the_tables_own_numbers`. My 4 route tests pass.
4. **Smoke.** Before the full walk, AH's and my states alone (`--only zzzzzzz`, fresh sandbox bridge, port 8786):
   **9 screenshots, 0 failures, 0 console errors, 0 tracebacks** (`smoke/smoke-ah-ai-states.log`). Then **one full walk
   on a fresh `--sandbox` bridge** (port 8786, private build of HEAD, started after *stumpy JIT warm*; the process check
   found no other bridge, smoke or pytest, and the working tree held no other session's edits): **663 screenshots,
   23 failures. All 3 of my states pass, and all 6 of AH's** (`smoke/smoke-full.log`; my screenshots in `smoke/`):
   the Ward script from the cluster page (2 GB asked for the walk's 396-window pool; the frozen note shown because AH's
   states had scored it); Results → *train a CNN on this* → *Create SLURM script* (script, copy list with the
   channel arrays, estimate, steps, how results return); *Run the local smoke* → the CNN run (589) in Results' list
   with model *CNN* → AH's blind view.
   The 23, sorted, each re-walked warm against the same bridge (`smoke/rewalk_*.log`):
   - **the 5 standing** — `discovery.runs--default` and the four Settings registration Check states (as `EXC` click
     timeouts);
   - **4 Interrogation cold-start** (`--default`, `--fixup-d-sequence-rose`, two `.slope--fixup-k-…` and
     `--fixup-k-all-marks-…`): **Interrogation re-walked 58 / 0**;
   - **`AD`'s `database is locked` 500** on `POST /api/library/family/F-130/suspected-artifacts` — the 6 unexpected
     traceback lines, the browser console 500, and `AD`'s two states that wait on it. The same intermittent lock `AG`
     recorded on two of its walks; nothing of this ticket writes at that point (my states run last);
   - **still failing warm, on pages this ticket does not touch:** `discovery.seed--default`, `discovery.stages--default`,
     `discovery.compare--unpick-b` (the seed page was still *searching for the seed* at its allowance — Discovery's seed
     route was rewritten by the other session's `0152df5` minutes before my first commit), `library.grouping--frequency-
     content` (failed warm for `AG` too), `review.inspector--3-queue-rail` and `--queue-picker popover…` (the queue list
     depends on the store, which AH's blind queues and AD's artifact queue now fill), and the Settings states
     `datasets--held-out-locked`, `datasets--review-item-carries-its-source-file`, `analysis-defaults--default` (in the
     re-walk also `nulls--unsaved`, `storage-backups--default` — `AG` Part 2 saw the same Settings set fail warm). The
     warm re-walk also added `discovery.runs--modal-add-template` and `library.templates--page-2`, which count the
     templates — the full walk had just saved more (AH's *Train model*).
   **Said plainly:** this is not the five-failure baseline, and I did not walk a bridge without my commits to prove
   the rest are not mine. What I can say: none of the failing states is on a page or route I changed; the shared code I
   touched is the B.2 setup route (one more block), `app.py` (one router), `blind._run_results` (one line) and
   `shape_forest._runs` (two kinds) — all exercised by the AH and AI states, which pass.

## 12. Questions for you

**1. Train the CNN on all 29,370 training windows at 12 epochs, or first a cheaper trial?** *In plain words:* a full
run is about an hour of cluster time (4 chained jobs), most of it drawing 54,000 pictures; the second and later runs
of the same pool skip the drawing. Twelve passes over the pictures is my choice; too few and it underfits, too many
and it memorises the piles.

- **(a)** the full run as written (12 epochs) — recommended;
- **(b)** first a 3-epoch run to see the per-epoch hold-back curve, then decide;
- **(c)** fewer windows (a sample per cluster).

*My recommendation:* **(a)** — the hold-back curve per epoch is in `history.json` either way, and a second run re-uses
the cached pictures.

**2. Should the CNN be scored on the windows you already labelled for the forest?** *In plain words:* you will label
about 1,000 windows blind for the forest's run. The CNN predicted every one of those windows too, so its agreement
with you could be read from the same answers — a fairer side-by-side and no second hour of labelling. As built, a CNN
run gets its own blind sample.

- **(a)** score the CNN on the forest run's blind labels (a small addition to AH's score; one sample for both models);
- **(b)** keep a separate sample per run (as built).

*My recommendation:* **(a)** — the same windows, the same human, only the model differs, which is the point of the
comparison.

**3. Fusion repair: should `fusion_cnn.pth` be retired?** *In plain words:* the broken file is broken because of how
its picture folder was laid out when it was trained, not because the training code is wrong; `fusion_cnn_2` and `_3`
work. Nothing to repair in the code.

- **(a)** move `fusion_cnn.pth` out of `MODELS/` (it is already refused everywhere);
- **(b)** leave it, refused.

*My recommendation:* **(b)** for now — it costs nothing, and AH's rows already say why it is refused.
