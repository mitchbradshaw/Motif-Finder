# Report — Fixup AB: Models trains one paired job and reads its own results

Run 2026-10-03 on `main`, in the main checkout, **beside `Z`** (wave 2). Commit prefix `fixup-ab:`. All three seams
were built in this run; nothing was split off. The first commit, `44c11bd`, touches only `tests/` and fails (no
`Working.training`); each later seam opened with its own red tests-only commit (`7d559e8` the SLURM exporter,
`430f327` the routes, `2b827eb` two defects found on real data). Every bridge ran `--sandbox` on my own port **8772**
with a private client build (`--dist <scratchpad>/dist-ab`; the banner said `CLIENT = … a private build`). The CLI runs
used a **copy** of the database in the scratchpad (`sqlite3 … backup` from a `mode=ro` connection). Nothing wrote to
the real `DATA/db/annotations.sqlite`, and nothing read `M4_aug_concat_fs1.mat`.

## In plain words first

The question is whether a computer learns to spot interesting stretches of signal better from **your** sorting
(arm A) or from groups a **clustering** algorithm found by itself (arm B). The app can now run that contest fairly:
both "students" get the same windows, the same learning method, the same random seed — only the answer key differs —
and both sit the same exams on windows neither has seen. It also runs each student a few hundred times on a
**shuffled** answer key, to show what "learning nothing" scores, and puts an error bar on every score.

**The first real run (on a sandbox copy, with a cut I chose as a draft, not you):** on later hours of the same
channels, your labels win clearly — 0.88 against 0.65 (the 0–1 score is "macro F1"; 0.5 is roughly a coin toss here).
On four channels neither student ever saw, the gap shrinks to 0.62 against 0.60, and that difference is within the
noise. Both beat "learning nothing" (≈ 0.47) by a long way. Two cautions: the exam is marked in *your* vocabulary, so
it leans toward arm A by construction; and the later hours hold far fewer interesting windows than the training hours.

**What you need to decide before your own run:** where to cut the clustering tree (how many groups, *k*) and which
groups count as "interesting". The page proposes a draft; once a run has a test score, that choice is frozen on that
window set — choosing it after seeing the exam would be marking your own homework.

## 1. The real numbers (acceptance 3–5)

`python -m Working.training` on the sandbox copy; raw output `webui/screenshots/fixup/AB/cli_*` and the full results
JSON `cli_run_79_results.json`. The browser walk built the identical set (same 10,077 windows, same split counts, same
cut table) through Models › Launch.

**Window set** `m2_aug_pooled` (key `60da1c79e7485190`): `M2_aug_concat_fs1.mat`, 10-minute windows on the labels'
600/200 grid, labelled-first non-overlap (`AA`), **labelled windows only**, features catch22 + fast entropy (26 columns,
24 kept). Training channels CH1_A1–CH12_C2, exam (ii) channels CH13_D1–CH16_D2. Built and measured in **74 s**.

| role | windows | interesting | not_interesting |
|---|---|---|---|
| train | 5,267 | 1,425 | 3,842 |
| validation | 751 | 86 | 665 |
| test (exam i) | 1,496 | 158 | 1,338 |
| exam (ii) | 2,563 | 449 | 2,114 |

**Split:** each training channel cut into 10 equal blocks by time; the last 2 are its test block, the one before them
validation, the rest train; **gap ≥ 1 window** between roles (the windows of a later role closer than 600 samples to
the last window of the role before are dropped and counted). `M2_aug_concat_fs1` / `_fs2` cannot sit on opposite sides
(one source file per set; `check_leakage` refuses the pair).

**Arm B's cut (a draft, sandbox):** Ward on the 5,267 pooled training windows; k = 6 → 2,364 / 65 / 465 / 2,371 and two
single-window specks. Translation (majority on training windows): clusters 2, 3 (and the specks) → interesting, 1, 4 →
not_interesting. Contingency on training windows (not_interesting · interesting): 1 = 2,024 · 340; 2 = 21 · 44 (impure,
68 %); 3 = 126 · 339 (impure, 73 %); 4 = 1,671 · 700 (impure, 70 %).

**Classifier:** one random forest for both arms (300 trees, class_weight balanced, seed 42) — Q42's "RF for both arms
first". The arm's model *is* the RF, so the RF baseline coincides with it; the 5 full-model shuffles of §9.4 apply when
the CNN arm exists.

| | exam (i) — later time block, 1,496 windows | exam (ii) — channels never trained on, 2,563 windows |
|---|---|---|
| **arm A** (manual) macro F1 [95 % CI] | **0.879** [0.790, 0.918] · bal. acc 0.827 | **0.623** [0.587, 0.662] · bal. acc 0.598 |
| **arm B** (cluster) macro F1 [95 % CI] | **0.651** [0.559, 0.708] · bal. acc 0.609 | **0.597** [0.556, 0.650] · bal. acc 0.582 |
| label-shuffle null (200 ×, mean · q95) | A 0.474 · 0.484 · B 0.472 · 0.472; **p = 0.005 both** (the floor at 200) | A 0.453 · 0.458 · B 0.452 · 0.454; p = 0.005 both |
| **ΔF1 = A − B** [95 % CI] | **+0.228** [0.169, 0.290] | **+0.026** [−0.022, 0.071] — crosses zero |
| McNemar (only A right · only B right) | 80 · 5, p < 0.0001 | 133 · 64, p < 0.0001 |
| agreement (both right · only A · only B · both wrong) | 1,357 · 80 · 5 · 54 | 2,054 · 133 · 64 · 312 |
| interesting: P / R / F1 | A 0.954 / 0.658 / 0.779 · B 0.750 / 0.228 / 0.350 | A 0.829 / 0.205 / 0.329 · B 0.511 / 0.205 / 0.293 |
| bootstrap units | 78 × (24 h of one channel) | 122 × (24 h of one channel) |
| exam (iii) | locked — `M4_aug_concat_fs1.mat`, after the freeze, Settings › Datasets | |
| yardstick (B) | *not yet labelled* (the Review-behaviour prompt's) | |

**Reading it.** On later hours of the same channels the manual arm wins by a margin far outside its interval; on unseen
channels the difference is within the noise and both arms miss four in five interesting windows (recall 0.21). Yardstick
(A) marks arm B in arm A's language — the page says so once — so "A wins on (i)" is partly built in. McNemar is
significant on (ii) while ΔF1 is not: more windows flip to A than to B, but the flips are mostly in the big
`not_interesting` class and barely move the class-averaged score.

**Per channel, an honest caveat:** the later hours are 11 % interesting against 27 % in training, and unevenly so:
CH3_A2 holds 91 of the test block's 158 interesting windows, six channels hold 1–4 each, and **CH10_C1 holds none**. A
channel with a handful of interesting windows that both arms miss reads macro F1 ≈ 0.49 — a real miss. A channel with
**one class only** read 0.50 for no reason at all (half of a perfect score on the class present), so it now reports
"one class only" with each arm's accuracy (`acc9fd3`). *I first wrote "7 of 12 hold none" in a commit message
(`acc9fd3`, `2b827eb`); that was a misreading of the 0.50s, corrected in `2826d64` and here.*

**Reference line (trained differently, not an arm):** `catch22_rf_prelabeled` 0.972 / 0.967, `GASF_cnn` 0.954 / 0.910,
`GADF_cnn` 0.956 / 0.915, `recurrence_cnn` 0.945 / 0.889 (exam i / ii). An **upper bound, not an exam**: their manifests
record no training data, and they were very likely trained on these same 10-minute labels, so the exam windows are
probably among their training windows. Every row says so. **`fusion_cnn.pth` loads with one output class**, so its
softmax is 1.0 for every window; it scored 0.10 by calling everything interesting and is now refused with that reason.

**The same job from Models › Launch** (two browser walks, two fresh sandboxes) built the identical set and cut but took
the template's **100 trees** (`manual_labels_model`'s classifier) instead of the CLI's 300 — a different recipe
(`a756b882`), as it should be: exam (i) A **0.867** [0.775, 0.909] · B **0.651** [0.562, 0.707] · ΔF1 **+0.216**
[0.148, 0.281] · McNemar 77 vs 7. Both walks gave identical numbers (reproducible from the recipe); the job took **244 s**
on a quiet machine.

**The gap, checked on the real set:** at all 24 role boundaries of the 12 training channels the smallest distance
between the last window of one role and the first of the next is exactly 600 samples — one window — so the rule held
with **0 windows dropped**; the labels are sparse enough that no boundary needed thinning.

**Time locally:** save set 74 s; propose 9 s; the job 578 s (fit 2 s, clustering 1 s, **null 570 s** for 2 × 200 forest
refits); the reference line another ~11 min on CPU (~1.5 s per exam window for four CNNs + the forest). The Launch
estimate said ≈ 5 min for the job with 0.72 s per fit measured on the spot; the CLI run shared the machine with a second
job. Well inside the 2 h local limit — nothing needs the cluster for Q42's default.

## 2. What was built

### Seam (i) — the core job, UI-free, with a CLI (`Working/training/`)

| module | what |
|---|---|
| `windows.py` | `build_pooled_set`: the labels' grid per channel → `catalogue.manual_labels`' rule → labelled-first non-overlap → **labelled windows only** → `blocked_split` (role per window, gap enforced, dropped counted) → features at those exact starts. Guards that raise: the held-out file **even with `HELD_OUT_UNLOCK`**, a non-blocked or random split, gap < 1 window, label-derived feature stages (`cnn`, `rf`), the fs1/fs2 pair split across train/test. `PooledSet` saves/loads with a content key |
| `paired.py` | `make_recipe`, `validate` (the Before-launch checks), `propose` (silhouette, sizes, contingency, majority translation, purity per k — on training windows only), `run_paired`, `per_channel`, `estimate` (times a small forest fit here and scales) |
| `metrics.py` | macro F1, balanced accuracy, confusion, per class with n; **block bootstrap** (unit = 24 h of one channel); paired ΔF1 under the same resamples; exact McNemar; 2 × 2 agreement; permutation p; calibration (reliability, ECE, threshold at a target precision) |
| `store.py` | `save_window_set` (one `window_sets` row, recording/channel NULL, plus a `window_set_members` row per channel), `run_and_record` (`configs` = the recipe, `runs`, `artifacts`: results JSON `other` + two `model` joblibs), **`CutFrozen`**: a recipe that changes k / linkage / translation on a set already scored is refused |
| `reference.py` | the existing `MODELS/` applied as the window matrix applies them, at the exam windows' starts; "trained differently" on every row; a constant output refused |
| `__main__.py` | `python -m Working.training save-set · propose · run · show` |

Two arms trained identically: same windows (`window_ids` equal, pinned), same forest and seed; arm B's classifier learns
the k cluster classes and its predictions go through the translation table. Test, validation and exam windows take no
part in the clustering (pinned: changing their features changes no cluster). Reproducible: the same recipe gives the
same numbers, null draws and CIs (pinned).

### Seam (ii) — Launch and the multi-channel window set

Routes in `webui/server/training_routes.py`: `GET /api/models/setup`, `POST /api/models/windowsets` (a `training` job),
`/propose`, `/checks`, `/train` (a `training` job, per-stage progress: features · cluster · train · null · score ·
calibrate), `/slurm`, `GET /runs`, `/runs/{id}`, `/runs/{id}/compare`, `/runs/{id}/disagreements`. Held-out → 423;
changed cut → 409.

Models › Launch: the training template (its window matrix sets the geometry; `windows_model`'s 1-minute windows are
flagged **off the labels' grid**, because no 1-minute window can wholly contain a 10-minute label); a recording's
channels with hours, human verdicts, interesting / not and artifact, each **train / exam / off**; test %, validation %,
gap; *Save window set* (with progress); the saved sets; *Propose cuts* (silhouette, sizes, real clusters vs specks per k)
and the **translation table**, editable until a test score exists; options; Before-launch checks and the estimate
**from the bridge**; *Train locally* (off above 2 h) and *Create SLURM script*; the held-out recording as a locked switch
naming Settings › Datasets; the runs.

**The SLURM script** (`Working/hpc/job_export.py`): an absolute `out_dir` inside the repo is now baked **repo-relative**
(the bridge's `webui/runtime/<stamp>/hpc` was baked as `C:/Users/...`); one outside the repo is baked as given and the
result carries a warning. The generic template took its GPU lines from a constant; **a recipe with no CNN step now gets
the CPU partition, no GRES, no CUDA and the CPU environment**. Discovery's `/slurm` gets both fixes without a change to
`discovery.py` (it passes no `uses_gpu` and an in-repo `out_dir`). `export_training_job` writes the paired job's CPU
script. The page says an HPC job's results return only when Jobs › Manifest inbox is wired.

### Seam (iii) — Results and Compare

Results: one run · one arm · one exam: macro F1 with CI, balanced accuracy, the null (histogram with the arm's value
and CI band), confusion (row-normalised + counts), per class (P/R/F1 with CI, n, *few* flag), per channel (one-class
channels say so), calibration on the validation block, what each arm trained on (feature importances), the reference
line, the yardstick-(B) row, the tilt note once. Training curves: none — a forest has no epochs (said on the page).

Compare: what differs (template, window set, split, classifier, options all **=**, label source **≠** → *attributable*),
both arms' macro F1 with CI and null band, ΔF1 with CI and the resampled distribution, McNemar, per-class ΔF1 (grey
where the CI crosses zero), the 2 × 2 agreement (clickable), per channel, the cluster → class contingency with
translation, purity and *impure* flags, and a **step through the disagreements** (the window's trace, the human verdict,
both predictions, *Open the channel in Explore*).

**`demo data`:** gone from Launch, Results and Compare. **Registry** keeps its fixture data and chip — its registration
gate needs blind window-verdict queues that do not exist. **Jobs** stays a fixture page; Models links to it as
"Jobs (demo page)". Library › Window sets lists a set across channels with its channels and recounts its coverage live.

## 3. Q42

Answered in the 2026-10-03 grilling and built as decided: two arms, identical training, RF first; one clustering over
the pooled training windows; the cut and the translation in the recipe and frozen once a test score exists; three exams
never pooled, (iii) a locked slot; yardstick (B) left to the Review prompt with its row; `MODELS/` a reference line.
**Defaults I chose, said here:** (1) the set holds **labelled windows only**, so arm B clusters the human-labelled
training windows — "train every arm on the windows labelled in every arm" makes that the training set anyway, and Ward
over every window of sixteen 30-day channels would need tens of GB; a pool that also clusters unlabelled windows is a
later option. (2) The bootstrap unit is **24 h of one channel**. (3) A cluster under max(10, 0.5 % of windows) is a
**speck** and does not count toward the draft cut — measured: Ward splits off single-window outliers first and
k = 2 (5,266 + 1) has silhouette 0.95. (4) *Impure* below 75 % majority. (5) Default roles on a 16-channel recording:
the last four channels are exam (ii).

## 4. Analyse › Training's six fixture pages, against P11

P11: Analyse builds and trials the template; Models trains. My recommendation: **retire the overview and blocks 1, 2
and 5** — the live chain already shows WindowSet / Grouping / Model rows and block pages for a real run (`AA`); **replace
block 3 (cluster, the dendrogram and k-sweep drawn from a fixture)** by Launch's *Propose cuts*, which now draws the real
per-k silhouette and contingency — a live dendrogram would need `catalogue.cluster` to keep its linkage matrix (04's T3);
**keep block 4 (encode) as a fixture** until the CNN arm exists. Not wired here, as the prompt said.

## 5. Items left

- **The researcher's own cut** on the real database. My k = 6 lives in sandboxes only; the real database has no paired
  run, so nothing is frozen there.
- The CNN arm (a cluster job) and Jobs › Manifest inbox bringing results back; Registry's gate.
- Exam (iii): the job has the slot; the run is the researcher's, after the freeze. Unlocking M4 in Settings does **not**
  make this job read it — that is a deliberate second door for whoever builds the freeze-day run.
- Arm B clusters labelled windows only (§3 default 1). A "cluster every window" pool needs a subsample or a
  non-Ward method.
- `fusion_cnn.pth` (one output class) — the `fusion_prediction` checkpoint is 06's M4.
- *Open window in Review* (§7b.4) has no route for an arbitrary window; Compare opens the channel in Explore instead.
- The step-through trace's y axis prints the same tick twice (`-420`, `-420`) on a window whose range is under 1 mV —
  the kit `Trace`'s tick formatting, not this page; not changed.
- Library › Window sets says *"no split plan — these windows were supplied, not cut by a sliding-windows block"* for a
  pooled set; true but beside the point (its split is in the row and its check reads *train-safe*).
- A test block that holds one class on most channels is a property of these labels; a different split (e.g. more,
  shorter test blocks spread through time) would give per-channel exams both classes. Worth a question to the
  researcher before the real run.

## 6. Files

**Mine (declared):** `Working/training/` (new), `Working/hpc/job_export.py`, `webui/server/training_routes.py`,
`webui/client/src/models/` (Launch, Results, Compare rewritten; `chrome.tsx` one link), `webui/client/src/api/models.ts`
(live calls appended; I did not touch the shared `api.ts`), `webui/smoke_pages/models.json` (Launch/Results/Compare
states rewritten, Registry's kept), `webui/smoke_pages/zz_models_ab.json` (new), tests `test_training_paired.py`,
`test_job_export_paths.py`, `test_webui_training_paired.py`. `Working/manifest.py` was not needed.

**Out of scope, and why:**

| File | Why |
|---|---|
| `Working/database/schema.py` | `window_set_members` (additive, idempotent): a window set across channels (item 2) |
| `Working/Preprocessing/window_matrix/build.py` | `features_at`: the same stages at arbitrary starts — a pooled set has no regular grid |
| `Adapters/catalogue_manual_labels.py` | `human_spans` ignored `deleted_at`, so a **soft-deleted annotation still labelled windows** (AA's block; pinned by a test) |
| `webui/server/library.py` | Library › Window sets: a set across channels names its channels and recounts coverage |
| `webui/smoke.py` (shared) | a `wait_for` action, appended and committed alone (`72f45ca`) |
| `docs/rq_roundA/RQ1-cluster-vs-manual-labels.md` | the RQ rule |

None of `Z`'s files were edited; `discovery.py` was left alone (its `/slurm` is fixed through the exporter).

## 7. The gate

1. **`npx tsc -b`: clean. `npm run build`: green** (run once `Z`'s committed tree type-checked; while `Z` was mid-flight
   `tsc` was red only in `src/discovery/ComparePage.tsx`, never in the Models tree).
2. **`pytest -n 4`** (conda, 9 m 49 s): **2045 passed, 20 skipped, 0 failed** — failure set empty against the baseline
   (README: 1952 / 17 after `H`; `Y`, `AA`, `Z` and this ticket added the rest). `tests/test_import_boundaries.py` passes,
   and `test_training_paired.py` pins that nothing under `Working/training/` imports a UI library or FastAPI.
3. **Under `webui/.venv`**, every `tests/test_webui_*.py` (`-n 4`): **369 passed, 3 xpassed, 1 failed** — the README's
   standing `test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers`. My five route tests pass.
4. **`webui/smoke.py`, full walk, fresh `--sandbox` bridge (port 8772, private build of the committed tree) — NOT a
   clean gate, and I say so.** Two walks, both on a loaded machine:
   - **Run 1 (16:16–16:40): 594 screenshots, 30 failures.** `Z`'s bridge on 8771 burned as much CPU as mine
     throughout. One failure was mine — `models.launch--held-out-locked`: the lock was an `aria-disabled` switch, which
     Playwright will not click although a click is what opens its explanation; fixed in `91196f0`.
   - **Run 2 (16:44–17:20): 594 screenshots over 574 page states, 64 failures.** `Z`'s smoke walk overlapped mine
     16:45–16:55 (`Z` stopped it when it noticed; `other-load-run2.txt`), and **the machine sat at 88 % CPU throughout:
     Ableton Live (started 16:10) and the HDJ control panel were using several cores.** The first chain run's matrix
     profile took 72 s against stumpy's cold JIT and every later state queued behind slow routes.
   - **In both runs: 0 browser console/page errors and 0 unexpected server tracebacks.** Every failure outside Models is
     a *missing element* (a plot or table not yet painted at its allowance), the slow-load signature — plus the five
     standing failures and the two `review.inspector--padding ±… s` screenshot writes (`/` in the state name under a
     scratch `SMOKE_SHOTS`, as `AA` reported).
   - **All 14 Models states pass in run 2:** the five static ones (`models.json`) and the nine live ones
     (`zz_models_ab.json`): save a window set across channels → propose cuts → train locally (a real one-channel paired
     job) → Results arm A / arm B exam (ii) / exam (iii) locked → Compare A vs B / both wrong → Launch after the run with
     the cut frozen. Registry's 18 fixture states pass.
   - **Still owed: one clean full walk** with nothing else on the machine (`Z` is running its gate now and asked me to
     hold off; Ableton needs closing). Until then I cannot show that the non-Models failures are load and not a
     regression — though nothing I changed is on their paths except `library.py`'s window-set row (Library › Window
     sets) and `job_export.py` (Discovery's `/slurm`, not walked by those states).

**Machine use:** I took the machine for smoke twice (16:16 and 16:44). My `pytest -n 4` runs and two Playwright walks
(15:44–16:07) overlapped `Z`'s first smoke walk; I wrote that up for `Z` in `requests/AB-to-Z-smoke-overlap.md`.

**Evidence:** `webui/screenshots/fixup/AB/` — `smoke/` the 14 Models smoke states and both smoke logs; `01`–`14` the browser walk (Launch, saving, cut and translation,
Before launch, training, Results arm A / B / exam ii, Compare exam i / both-wrong / exam ii, Launch after the run with
the frozen cut and the SLURM script, Library › Window sets; `11b` the step-through); `cli_*` the real CLI run (save set,
propose, run summary, full results JSON).
