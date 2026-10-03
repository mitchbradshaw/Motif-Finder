# Fixup AB — Models trains one paired job and reads its own results

**Runs after `AA` — wave 2, beside `Z`. Q42 was answered in the 2026-10-03 grilling (below), so there is no grilling round to open; stop only if something contradicts it.** *(Original note:* opens with a grilling round — `QUESTIONS.md` Round 9 Q42 — and takes the default if
unanswered.** The largest remaining build of the six questions (`docs/RESEARCH_READINESS.md` §Q1); it
is what makes **Q1** answerable. Expect it to be more than one agent's run: §"If it splits" says where.

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md`, `docs/RESEARCH_READINESS.md` §Q1,
`prototyping/UI_FUNCTIONAL_SPEC.md` §7b.1–§7b.4 and §9.4 (the training rows), `docs/PIPELINE_PRD.md`
"Evaluation protection" and "Cut list", `docs/prompts/fixup/06-models.md`, `04-analyse-training.md`,
`09-jobs.md`, and `reports/AA-manual-labels-and-window-sets.md`.

Commit prefix `fixup-ab:`. Test-first; first commit touches only `tests/` and must fail.
**`--sandbox` only. The held-out recording stays locked; its unlock is the researcher's act on the
freeze day, never yours.**

## Decided — `QUESTIONS.md` Q42 and Round 10 (2026-10-03). Do not re-open these; build them.

- **The two arms are trained identically; only the label source differs.** Arm A: the human labels through `AA`'s `catalogue.manual_labels`. Arm B: a window-matrix **dendrogram clustering at a chosen cut** (classes may be morphological: sharkfin / trough / drop / noise). RF for both arms first, locally, this month; the CNN arm is a later cluster job once Jobs can bring results back.
- **One clustering over the pooled training windows of every training channel** (Q-W2), never one per channel. Test windows take no part in forming the clusters.
- **The cut is chosen on training windows only** (by eye, silhouette as a guide), **frozen into the recipe**, and the app refuses to change it once a test score exists.
- **Windows:** `AA`'s non-overlapping window set (stride 600 on the labels' grid). The blocked split still keeps a gap of at least one window between train and test.
- **Yardstick (A), the primary comparison:** the cluster classes are translated to the human vocabulary (e.g. sharkfin / trough / drop → `interesting`, noise → `not_interesting`) by a **translation table fixed in the recipe before any test score exists**; both arms are scored on windows neither saw. Say on the page, once, that (A) is marked in arm A's own language and so is tilted toward it.
- **Three exams, reported separately, never pooled:** (i) a later time block on the training channels; (ii) channels never trained on — the same mushroom; (iii) the held-out `M4_aug_concat_fs1.mat`, a different mushroom, once, after the freeze, unlocked by the researcher. Build (iii) as a slot that stays locked.
- **Yardstick (B), blind hand-labelling in the cluster vocabulary, is NOT yours** — it is the Review-behaviour prompt's, later. Leave room for its result on Results (a row that says *not yet labelled*).
- **The existing `MODELS/` (GADF, GASF, recurrence and fusion CNNs, `catch22_rf_prelabeled`) are a reference line** on Results, scored on the same exams where their inputs allow and labelled *trained differently* — not an arm. If one cannot be scored on an exam, say why on the row.

## Running in parallel (2026-10-03)

**Wave 2: you run beside `Z`** (`Z-band-scope-and-compare-by-verdict.md`), another agent in the same checkout. The README's **"Running two prompts at once"** rules apply in full: your own port and a private client build served with `run_server.py --dist`; `npx vite build --outDir <yours>` while working and `npm run build` only for the gate (the other agent's in-flight files may make it red — say so in the report); `pytest -n 4`, never `-n auto`, and announce in your report when you took the machine for smoke; shared files are **append-only and committed immediately with your own hunks only** (`git add -p`). If you need a file the other agent owns, stop and write to `requests/` rather than editing it.

| | files |
|---|---|
| **yours** | Models tree (`webui/client/src/models/`), the training-job core, `Adapters/catalogue_classifier.py`, `Working/hpc/job_export.py`, `Working/manifest.py`, `webui/server/training_routes.py` |
| **`Z`'s — do not edit** | `Working/run_groups.py`, `Working/recipes.py`, Discovery › Runs *Apply template* and Compare pages, `queries.queue_candidates`, Settings › Analysis defaults |
| **shared** | `webui/server/discovery.py` — **you touch only the `/slurm` script writer** (the baked Windows paths); `Z` touches the apply-template and compare routes. Also `webui/client/src/api.ts`, `webui/smoke.py` |

This prompt is large and may outlast `Z`. **`T` runs alone after this wave**, so if you split ("If it splits" below), finish and report a part before `T` starts rather than running through it.

**Talking to the researcher:** any question you put to them opens with a plain-language explanation, then the options, then your recommendation (`CLAUDE.md`). **Before you report, update** `docs/prompts/rq_roundA/RQ1-cluster-vs-manual-labels.md` per that folder's README.

## Where it stands, measured 2026-10-02/03

- **Models › Launch / Results / Compare / Registry, Analyse › Training and Jobs wear `demo data`.** The
  Results page's *macro F1 0.71*, Compare's *ΔF1 +0.09 · McNemar p = 0.04* are fixtures.
- **The cluster arm runs on one span** (`windows_model`: *"holdout accuracy 0.80 · 3 classes · 120
  windows · train/holdout 90/30"*), with a **stratified random** 25 % holdout of the same two hours
  (`Adapters/catalogue_classifier.py:165–170`) — not generalisation.
- **"Apply a cluster template across channels" is reachable from the bridge and not from a page**, and
  it is the wrong operation for Q1. Measured on template `window_matrix → cluster` (saved as
  `cluster_windows_k3`, kind `training`): Discovery's *Apply template* list hides it
  (`webui/server/discovery.py:527` keeps `kind == "detection"`), but `POST /api/discovery/plan`
  planned it (`fan_out {"kind": "channels", "targets": [2, 6, 7]}`), `POST /api/discovery/slurm` wrote
  `cluster_windows_k3_3ch_1627200-1641600.sh` with `#SBATCH --array=0-2`, and
  `POST /api/discovery/templates/apply` ran it — run group 3, one cluster-label CSV **per channel**.
  **Each channel was clustered on its own**: cluster 1 on CH2_A1 is not cluster 1 on CH6_B1. A label
  vocabulary for a classifier needs **one** clustering over the pooled windows, fitted on training
  windows only. That is what §7b.1 means by *Sources — channels*: pooling, not fan-out.
- **The SLURM script the bridge writes would not run on the cluster.** `discovery.py:1653–1657` hands
  `export_job` an absolute `out_dir`; the exporter assumes a repo-relative one
  (`Working/hpc/job_export.py:249–256`, *"the paths baked into the script are REPO-RELATIVE"*), so the
  script's `python - C:/Users/mmebr/Documents/CNN/webui/runtime/…/x.json` names a Windows path under a
  `--chdir=/home/Student/s4699158/CNN`. It also asks for `--gres=gpu:a100` for a CPU clustering. And
  results have no way back: Jobs › Manifest inbox is a fixture page.
- **`window_sets` is one recording and one channel per row**; a paired job wants one set across channels.
- Nothing in `Working/` trains two label arms on the same windows; `Working/Catalogue/` holds the CNN,
  the aeon classifiers, labelling and dendrogram code the arms will reuse.

## What to build

1. **The paired job, in the core, UI-free** (`Working/training/`, new): over one multi-channel window set
   and its feature matrix — **arm A** manual labels (`catalogue.manual_labels`, `AA`), **arm B** cluster
   labels (`catalogue.cluster` fitted on the **training** windows only, its classes mapped to manual
   classes by majority on training windows with the contingency and purity kept, §7b.4), and the
   random-forest baseline per arm; *train every arm on* the windows labelled in every arm. **Split
   blocked by time within each channel with a gap ≥ one window** — the manual windows overlap on a
   200-sample stride (`AA`), so a random split leaks by construction — test block scored once,
   validation for calibration; `M2_aug_concat_fs1` and `_fs2` never on opposite sides (PRD). Null:
   label shuffle on the RF 200×, on the full model 5× (§9.4). Out: macro F1 with a bootstrap CI over
   test blocks, balanced accuracy, confusion, per-class P/R/F1 with n, the paired ΔF1 CI and McNemar,
   the 2 × 2 agreement, per-channel F1. Results are a JSON artifact on disk plus `artifacts` rows (rule
   4); the job is reproducible from its recipe hash. Which classifier each arm trains is **Q42**.
2. **A window set across channels** — additive storage (a members table or a recordings list on the
   row), saved from Launch's channel sources with the split included, as §7b.1 step 2 says.
3. **Routes and a job kind** `training` (a `GenericJob` with per-stage progress, like a sweep).
4. **Models › Launch, Results and Compare read it** and lose `demo data`. Registry stays a fixture page
   and says so — the registration gate needs blind window-verdict queues that do not exist. Jobs stays
   a fixture page; link to it anyway.
5. **Where it runs.** Local when the estimate is ≤ 2 h, else *Create SLURM script* — with the exporter
   fed a repo-relative `out_dir` and a CPU profile for a CPU job. State on the page that an HPC job's
   results re-enter only when Jobs › Manifest inbox is wired; for Q42's default (RF) nothing needs the
   cluster.
6. **The held-out option** is on Launch, disabled, naming Settings › Datasets as where it is unlocked.
   Nothing you build may read `M4_aug_concat_fs1.mat`.

## If it splits

Natural seams, in order: (i) the core job and its tests with a CLI, no pages; (ii) Launch + the
multi-channel window set; (iii) Results + Compare. Each is reportable on its own; (i) alone lets the
researcher answer Q1 from the command line while (ii) and (iii) are built.

## Leave alone

| Leave alone | Why |
|---|---|
| Discovery's template-kind filter | clusters across channels are Models' job, not a Discovery sweep |
| Jobs, the manifest inbox, the HPC round trip | its own prompt; the PRD's manifest import exists in the core (`Working/manifest.py`) and is untested on a returned job |
| The CNN arm on the cluster | after Q42; it needs Jobs |
| Analyse › Training's six fixture pages | decide in your report which of them survive P11; do not wire them here |

## Acceptance — the researcher's walk for Q1

1. Analyse › Chain → ⤓ Import `windows_model` → ▢ Save template (or keep the builtin).
2. Models › Launch → template `windows_model` → *Sources · channels*: tick channels of
   `M2_aug_concat_fs1.mat` (the page shows hours, windows, human verdicts and classes seen per channel —
   from the real tables) → *Save window set* → arms A (manual) and B (cluster) ticked, RF baseline on →
   *Evaluation*: blocked split, gap, per-class × per-split counts, warnings → *Before launch* checks →
   *Train locally*.
3. Jobs (or the Launch row) shows it running; Models › Results shows arm A then B: macro F1 with CI,
   the RF baseline, the label-shuffle null, confusion, per-class rows.
4. Models › Compare → *A manual vs B cluster* → one difference (*label source*) marked attributable →
   ΔF1 with CI, McNemar, per-class, per-channel, the cluster→class contingency.
5. That page, with its null, is the answer to Q1 on the reviewed channels. The held-out run is a second
   act, once, after the freeze.

## The gate

`npx tsc -b` + `npm run build`; `webui/smoke.py` on a fresh `--sandbox` bridge, alone, finishing on the
**full** walk; `pytest -n 4` against the baseline in `README.md` (re-measure; compare failure sets);
`tests/test_import_boundaries.py` (nothing under `Working/training/` may import a UI library or FastAPI).

Evidence into `webui/screenshots/fixup/AB/`.

## Report

`docs/prompts/fixup/reports/AB-models-paired-job.md`: the real numbers of one paired job on the
reviewed channels — both arms, baseline, null, ΔF1 — with the window set, split and gap stated; what the
cluster→class mapping looked like; the time it took locally; Q42 as answered or defaulted; which seams
were split and which pages still wear `demo data`; items left; out-of-scope files touched; the gate.
