# Fixup AI — the site writes a SLURM script that trains a CNN on the cluster categories

**Fourth of five for RQ1 version 2. Runs after `AG`; may run beside `AH`; `AJ` follows it.** Written 2026-10-05; nothing here is run
yet.

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python `"/c/ProgramData/anaconda3/python.exe"`).
Read `CLAUDE.md`, `docs/rq_roundA/RQ1-cluster-vs-manual-labels.md` ("New scope, version 2"),
`reports/AG-shape-clustering-and-dendrogram.md`, `reports/AB-models-paired-job.md` (§2 the SLURM script,
`export_training_job`, "Items left"), `docs/prompts/fixup/09-jobs.md`, `Working/hpc/job_export.py`,
`Working/Catalogue/cnn/` and `Working/Catalogue/gramian/`.

Commit prefix `fixup-ai:`. Test-first; the first commit touches only `tests/` and must fail. **`--sandbox` only. You do
not submit anything to the cluster; the researcher does.**

## In plain words

The forest proves the idea quickly on this machine. The researcher also wants the real thing: every clustered window
turned into an image and a CNN trained on the cluster categories, on the university cluster. The site should write the
job script for that, the cluster should be able to run it as written, and the trained model's results should come back
into the site so `AH`'s blind comparison can read them like any other run.

## Decided (the researcher, 2026-10-05). Build these; do not re-open them.

- **Forest first, CNN second** — but the CNN path is wanted now, as a **SLURM script the site writes**, to be tested on
  HPC.
- **Images by an existing encoding, fusion first.** "CNN" is the kind of model; "fusion" is one of four ways of
  turning a window into the picture it looks at (GASF, GADF and recurrence stacked as the three colour channels of one
  image; the other three use one of them alone). Same network, four kinds of picture.
- **A SLURM script for Ward over every window of the pool** is wanted too: the local tree is on a 20,000-window sample
  (`AG`); the cluster has the memory for all of them.
- **Same windows, same cluster categories, same frozen cut and mapping as the forest run** — only the model differs, so
  a difference between forest and CNN is attributable to the model.

## What to build

1. **The CNN arm in the core** (`Working/training/`, reusing `Working/Catalogue/cnn/` and `gramian/`; the core imports
   no UI library): encode each pool window as an image, train on the cluster categories, predict test and exam windows,
   write the same results JSON shape the forest run writes so Results and `AH` need no second reader. Three scales give
   three window lengths: resample to the encoder's input size as `AG` resamples for clustering, and say so in the
   recipe. **Fusion is the first target.** Its registered checkpoint loaded with one output class in `AB`; that is a fact about
   that file, so find out first whether the fusion *training* code is sound. If it is, build fusion; if it is not and
   the repair is more than small, build GASF so the path exists, and put the fusion repair to the researcher. Report
   which you built and why.
2. **A small local smoke** — a few hundred windows, one epoch, CPU — so the path is tested here before a cluster hour
   is spent. Images are bulk arrays: on disk, by path, in a cache directory (rule 4).
3. **Models › Launch → *Create SLURM script*** for this arm: repo-relative paths (as `AB` fixed), the GPU partition and
   GRES for a CNN job, an estimate (encoding + epochs) measured from the local smoke and labelled as an estimate, the
   environment lines the existing HPC exports use, resumable (a checkpoint per epoch; encoding skipped when cached).
   The page lists exactly what must be copied to the cluster (the pool, the tree's cut, the channel arrays) and how big
   it is.
4. **Bringing results back.** A CLI (`python -m Working.training import-results <dir>`) that validates the returned
   results against the recipe hash and records the run, the artifacts and the model — written as one function the
   Jobs page can call too, because **`AJ` puts it on Jobs › Manifest inbox**. A line on Launch says how results return.
5. **The full-pool Ward script.** From the `AG` chain's cluster block: *Create SLURM script* writes a CPU, high-memory
   job (state the memory it asks for and how you sized it: the pairwise distances of n windows take about 4 n² bytes —
   14 GB at 60,000) that runs the same Ward on every training window of the pool and writes the same linkage artifact
   `AG` reads. Imported by the same `import-results`, it replaces the sampled tree for that pool — refused, like any
   changed cut, once a run on that pool has a test score. A local smoke on a small pool proves the round trip.
6. **The label-shuffle null for a CNN** is 5 full-model shuffles (§9.4, as `AB` noted), each a full training: put them
   in the script as an array job, off by default, with their cost stated.

## Leave alone

| Leave alone | Why |
|---|---|
| Jobs and the manifest inbox pages | `AJ` |
| The existing `MODELS/` checkpoints | `AH` scores them as the comparison line; do not retrain or overwrite |
| The cut, the mapping, the sample for blind labelling | `AG`, `AH` |

## Acceptance — the researcher's walk

1. Models › Launch on an `AG` run's pool → model *CNN (GASF / …)* → *Create SLURM script* → a script and a list of
   what to copy.
2. The local smoke of the same recipe runs here and its (tiny) result appears in Models › Results.
3. On the cluster, by the researcher: `sbatch` the script as written. Back here: `import-results` → the run appears in
   Results beside the forest run, same windows, same cut.

## The gate

`npx tsc -b` + `npm run build`; `webui/smoke.py` on a fresh `--sandbox` bridge; `pytest` against the README baseline
(the suite must still pass on a machine with no GPU); `tests/test_import_boundaries.py`. Evidence into
`webui/screenshots/fixup/AI/`.

## Report

`docs/prompts/fixup/reports/AI-cnn-arm-slurm.md`, opening in plain words: the script as written (attach it), the local
smoke's numbers and timings, the estimate for the full pool, which encoding and why, the state of the fusion training
path, what the researcher must do on the cluster step by step, items left, the gate. **Before you report, update**
`docs/rq_roundA/RQ1-cluster-vs-manual-labels.md` per that folder's README. Any question to the researcher: plain
language first, then options, then a recommendation.
