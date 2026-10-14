> Filed by the manager session, 2026-10-14 09:06 — the final message of critic agent `a69d2ce5bd86b27c0` on branch
> `worktree-agent-aa6497544feed7c56` (d497ca0), verbatim.

## Critic report: W2-C `catalogue.minirocket` (branch `worktree-agent-aa6497544feed7c56`, d497ca0 on 04948e3)

### 1. In plain words
The block does what it claims. It gives every 10-minute window a shape fingerprint, learns its cut-offs from training windows only, handles gaps and pools correctly, and refuses bad input in words. Shuffled labels score at chance.

Three things around it would mislead the researcher:
- **The run-time estimate is wildly too high.** Once the block is calibrated (the step that turns on its estimate), Analyse would send an 8-second run to the cluster.
- **The template's 1,000-feature fingerprint loses real accuracy on harder labels.** "Can this label be learned?" could come back "no" when it can.
- **The template's 10-minute windows catch only about a third of the real labels.** The labels sit on a grid that starts a new window every 200 s; the template's windows sit end to end.

The leak through the classifier's random holdout turned out small on my synthetic sets.

### 2. Verdict
**Merge after fixes.** Finding 1 is a fix on this branch (or a small `block_cost` hook). Findings 2 and 3 are template decisions the manager should settle before the template goes into `CANONICAL`.

### 3. Findings, most severe first

**1. should-fix (near blocker), `Adapters/catalogue_minirocket.py:40-60`: the cost model mostly times the aeon import, not the work.**
- `block_cost.calibrate` times `_time_once` once, on 20,000 samples: 33 windows taking about 0.2 s of real work.
- The timed call also includes the lazy aeon import, which took 13.7–44.7 s in a fresh process here. The numba cache is warm (the first transform takes 1.4 s, later ones 0.2 s).
- That fixed cost is then scaled linearly per span sample. Measured in `exp_cost.py` (scratch `CALIBRATION_PATH`):

| Calibration | Estimate, 2.6 M samples, 10k features | Actual run (4,333 windows) |
|---|---|---|
| fresh process, k = 2.45e-3 | 6,370 s | 8.4 s |
| warm process, k = 3.8e-5 | 98.6 s | 8.4 s |

- At 1,000 features the fresh-process estimate is 589 s against an actual 1.2 s.
- With the implementer's suggested `COSTED` + `calibrate`, `chain.route_local` on main (ceiling `CLUSTER_ROUTING_CEILING_S = 900`) would refuse the run and write a SLURM job for an 8-second step. Any null draws would multiply that.
- **Fix, either of:**
  - (a) Estimate from the work itself: windows × features × length, with the coefficient measured warm (about 1.9e-7 s per window·feature at 600 samples, including building the table), plus a stated import constant. The span-sample model is also wrong for a 600/200 grid (3× the windows) and for pools (the implementer flagged this).
  - (b) Add an untimed `warmup` callable to `register_cost_model` / `calibrate`. That touches `Working/block_cost.py`, so it is the manager's call. Also tile far more than 33 windows in `_time_once`.

**2. should-fix (template / manager), template `n_features: 1_000`: it costs accuracy, and the filter it works around does nothing here.**
- I scored a blocked split (train on split 0, score on split 2, balanced accuracy). The data: 400 windows, labels persisting in ~2 h runs, a weaker shape signal, a slowly changing AR(1) background with an oscillation and drift (`exp_nfeat.py`).

| Event size | Seed | 1,000 features | 10,000 features |
|---|---|---|---|
| 0.35 | 1 | 0.645 | 0.954 |
| 0.35 | 2 | 0.688 | 0.776 |
| 0.35 | 3 | 0.5 | 0.5 |
| 0.5 | 1 | 0.967 | 1.0 |
| 0.5 | 2 | 0.906 | 0.969 |
| 0.5 | 3 | 0.725 | 0.900 |

- The implementer's "lost little" came from easy sets.
- The classifier's correlation filter (`dendrogram_cluster._remove_correlated_columns`: `df.corr()` plus a Python double loop of `corr.at`) is confirmed quadratic: 924 columns 5.9 s, 1,932 24.3 s, 2,940 77.3 s, 3,948 163.7 s, on 60 windows, loaded machine. That extrapolates to roughly 15–17 min at 9,996, consistent with the reported 13 min.
- It **dropped 0 columns** at every width: it buys nothing for MiniRocket features.
- **Fix:** vectorise the filter, or skip it above N columns (a classifier-side change: it does not change the classifier's hash, but it does change its behaviour, so it is the manager's call). Then run the template at 10k. Until then, the `n_features` help and the template description should say a "no" at 1,000 is not a "no".

**3. should-fix (template / manager): Sliding windows cannot sit on the labels' 600/200 grid.**
- Checked through `catalogue.manual_labels`, both its `label_windows` and end to end via `execute_recipe` (Sliding windows → MiniRocket → Manual labels), in a temporary database (`exp_grid.py`).
- The setup: 321 labelled 600-sample spans spread over all three grid phases (102 / 112 / 107).

| Windows | Labelled windows kept |
|---|---|
| Template (Sliding windows, 600 s) | 102 (32 %); 112 when the span starts at +200 |
| 600/200 grid (Window matrix at step_frac 0.334), labelled-first non-overlap | 190 (59 %) |

- On real labels the gap is larger: `manual_labels`' own docstring measured 10,077 of 11,110 kept with the grid.
- **Recommendation:** for RQ1, build the MiniRocket arm on the same windows as `manual_labels_model` (Window matrix, 600 s, step_frac 0.334). The two arms then differ only in features.
  - Turn Window matrix's own feature families off. Otherwise Catch22/entropy columns ride through MiniRocket into the classifier, and the arms mix.
  - Accept that MiniRocket then fits on all windows, with its warning. The classifier's holdout is random anyway (finding 4).
  - The alternative is letting Sliding windows take a step shorter than the window, dropping windows that straddle a block boundary. That changes another block's P12 rule, so it is the researcher's decision.

**4. finding for the researcher (not a blocker): the random-holdout leak is small; reading plain accuracy is the bigger hazard.**
- `catalogue.classifier` scores on a stratified random holdout, not the `split` column. I tested labels in ~2 h runs, with **no shape difference**, over a slowly changing background (`exp_leak*.py`):

| Background | Windows | Random holdout (template's number) | Blocked split |
|---|---|---|---|
| AR(1) with wandering φ, oscillation, drift | 400 | balanced 0.55–0.63 | 0.48–0.61 |
| same | 1,000 | 0.51–0.58 | 0.51–0.54 |
| oscillation whose period wanders 60–300 s | 400 | 0.49–0.59 | 0.52–0.57 |

- Shuffled labels gave 0.39–0.52. With a real shape signal, random and blocked accuracies matched.
- So MiniRocket + forest learns time through texture only weakly here: at most about +0.1 balanced, and not repeatable across seeds.
- **The real trap:** the template reports plain accuracy on imbalanced labels. It showed 0.66 when the majority class was 0.67, meaning nothing was learned. `per_class_accuracy` reveals it; the headline does not.
- **Suggested (manager, classifier meta only, hash unchanged):** add a majority baseline and balanced accuracy, and a blocked-split score whenever the windows carry `split`.
- One more manager item: the numeric pool columns (`pool_recording_id`, `pool_start`, `shape_row`) become classifier features on the pool path. This was already true before this branch; MiniRocket makes the path likelier.

**5. nit, `Working/Catalogue/minirocket.py:67-69, 276-287`: the global-RNG save/restore is not thread-safe.**
- The bridge runs jobs on threads (`webui/server/runs.py:178`, `jobs.py:186`).
- With two MiniRocket jobs plus a third thread drawing from `np.random`, that thread's draws were disturbed in 1,992 of 2,000 cases (`exp_threads.py`). aeon's own `np.random.seed` does that, and the restore can roll back another thread's state.
- The fingerprints themselves stayed deterministic: 10 of 10 concurrent results equal the single-thread one. For one channel, aeon's numpy draws do not affect the result; the bias case choice uses numba's per-thread RNG. numba's threading layer is TBB, so concurrent `n_jobs=-1` transforms did not crash.
- **Fix:** reword the docstring's "never reseeds anything else in the process" to "within one thread", or put a module lock around fit.

**6. nit, `minirocket.py:261`:** the `max_cells` refusal suggests "e.g. 84" even when 84 features are still over the limit. Say "use fewer windows" in that case.

**7. nit, `tests/test_minirocket.py:239`:** the shuffled-label test uses windows in random order, so it cannot catch temporal leakage. A persistent-label case scored on the blocked split would pin finding 4.

**Runtime notes (manager's item 4):**
- The ~175 s numba compile is once per machine, and the cache is already warm here (`.nbc` files in aeon's `__pycache__`).
- The first MiniRocket step in each bridge process pays the aeon import: 14–45 s on this loaded machine. A first smoke state, or a first Analyse run, will be slow by that much. Check the smoke per-state timeout when adding the state.

**Axes that passed:**
- **Spec:** every acceptance item is met and tested so a wrong implementation would fail. Fit-on-train swaps the test windows; the pool test poisons `x` with NaN; the shuffled-label check is one-sided. The Catch22 comparison is reported honestly as not won.
- **Faithfulness:** aeon is used as is. z-normalisation, end-gap holding and the unchanged forest are all named in the docstring.
- **Edge cases**, all refused or counted in words, never a blank: constant signal (10 flat, counted), too-short span, 8-sample windows, a 20 s gap (filled), a 25 min gap (4 windows left out), all-NaN, volt-scale values with normalise off, `max_cells`.
- **Test-first and scope:** the first commit (edd59fd) touches only `tests/` and is red (the core module is absent in that tree). Nothing on the do-not-touch list is changed. The 49→50 count bumps will conflict with other wave-2 branches.

### 4. What I ran
Python: `"/c/ProgramData/anaconda3/python.exe"`. The machine was loaded by other agents, so every timing reads slow. Scripts are in `C:\Users\mmebr\AppData\Local\Temp\claude\C--Users-mmebr-Documents-CNN\9b41764a-ced2-4e05-857c-547103bce7fb\scratchpad\critic_w2c\`.

- **Implementer's tests**, from the worktree: `test_minirocket`, `test_adapter_minirocket`, `test_template_minirocket_manual_labels`, `test_block_standard`, `test_adapter_spec`, `test_import_boundaries`. **258 passed in 66 s.**
- `exp_threads.py`: TBB layer; concurrent runs equal; the other thread's RNG disturbed.
- `exp_leak.py`, `exp_leak2.py`, `exp_leak3.py`, `exp_leak4.py`: random against blocked holdout, time-only and shape labels, plus a Catch22 comparison (Catch22 shows the same small random-split inflation, 0.61–0.73).
- `exp_grid.py`: 600/200 capture, 102 against 190 of 321.
- `exp_nfeat.py`: the quadratic correlation filter (0 columns dropped), and 1k against 10k accuracy on a blocked split.
- `exp_cost.py`: calibration k against the actual 2.6 M-sample run (estimate 6,370 s, actual 8.4 s).
- `exp_first.py`: aeon import 13.7–44.7 s, first call 1.4 s, later calls 0.2 s.
- `exp_edge.py`: the edge cases above.

Nothing in the worktree or the repo was edited, and `DATA` was not touched.
