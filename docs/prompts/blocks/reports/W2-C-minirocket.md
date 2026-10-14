> Filed by the manager session, 2026-10-14 08:40 — the final message of implementer agent `aa6497544feed7c56`
> (branch `worktree-agent-aa6497544feed7c56`), verbatim.

## W2-C — `catalogue.minirocket`: report

Note first: my worktree started at 3cc2f62, behind the base. I fast-forwarded it to 04948e3 (`git merge --ff-only`; 04948e3 is a descendant) before starting.

### 1. In plain words
The block runs every window through about 10,000 tiny fixed pattern detectors. For each detector it records the fraction of the window where that detector fires. The resulting list of numbers is a fingerprint of the window's shape, and the fingerprint columns are added to the window table. It tests whether a label can be learned from the raw shape at all, cheaply. The numbers mean nothing one by one.

- **Leakage guard:** the detectors' cut-offs are taken from training windows only, never from labels.
- **Shape, not level:** each window is rescaled first (z-normalised).

**What it found on the synthetic data.** Three window classes with the same mean and variance but different shapes: drop with a slow recovery, symmetric dip, step.
- The site's forest on the fingerprint reaches holdout accuracy of 0.84 on an AR(1) background, 1.00 on a random walk and 1.00 on a slow drift.
- With the labels shuffled it falls to chance: 0.36, 0.24, 0.33 against chance 0.33 (sd 0.07).
- **The acceptance comparison did not come out as hoped.** The forest on the windows' Catch22 features is *not* clearly worse:

| Background | Noise | Forest, MiniRocket 10k | Forest, MiniRocket 924 | Forest, Catch22 | Ridge (aeon `MiniRocketClassifier`) |
|---|---|---|---|---|---|
| AR(1) φ=0.97 | 1.0 | 0.844 | 0.822 | **0.911** | 0.867 |
| AR(1) | 1.5 | 0.711 | 0.667 | **0.867** | 0.667 |
| random walk | 1.0 | **1.000** | 1.000 | 0.933 | 0.978 |
| random walk | 1.5 | 0.867 | 0.822 | 0.956 | **0.978** |
| drift | 1.0 | **1.000** | 1.000 | 0.933 | 1.000 |
| drift | 1.5 | **1.000** | 0.933 | 0.933 | **1.000** |

These are 180 windows (135 train, 45 test). MiniRocket wins on the drift and random-walk backgrounds, and Catch22 wins on AR(1). A time-reversed-drop class set gave the same picture in prototyping (Catch22 1.0 against MiniRocket 0.76–0.91).

**Forest vs ridge**, as asked instead of changing the classifier: on these sets they are about level. Ridge is better on random walk at higher noise (0.978 vs 0.867); the forest is better or equal elsewhere.

**Timings** (the block end to end, 600-sample windows, default 9,996 features, this machine, warm numba cache):
- 1,000 windows: 0.48 s (fit 0.13, transform 0.27), 40 MB.
- 20,000 windows: 13.8 s (fit 0.24, transform 5.9; the rest is building the 10k-column table), 800 MB.
- At the default `max_cells` the 20,000-window case is refused.
- The very first MiniRocket call on a machine compiles numba code: about 175 s once, cached afterwards.

### 2. Files
- Created `Working/Catalogue/minirocket.py` — the core: `fingerprint`, `fingerprint_matrix`, `real_feature_count`, `window_vectors`, `repair_gaps`, `train_mask`, `znormalise`, `RULES`.
- Created `Adapters/catalogue_minirocket.py` — the adapter (WindowSet → WindowSet, category `encode`, `page_name="MiniRocket"`), with a cost model, `estimate` and `derive`.
- Created `tests/_minirocket_synthetic.py` — the three shape classes on AR(1), detrended random-walk and drift backgrounds.
- Created `tests/test_minirocket.py` — core tests (30).
- Created `tests/test_adapter_minirocket.py` — adapter tests (6).
- Created `tests/test_template_minirocket_manual_labels.py` — the `TEMPLATE` constant and the end-to-end run (3).
- Modified `tests/test_adapter_spec.py` and `tests/test_end_to_end.py` — adapter counts 49 → 50.

### 3. The algorithm as implemented
1. **Source of the windows.**
   - If the WindowSet has a `shape_file` column, read the vectors with `Working.training.shape.ShapeSet.load` (which checks the file's key) and index them by `shape_row`.
   - Otherwise slice `x` at `starts − round(t[0]·fs)`. This is inline, as in `catalogue.window_images`; there is no helper to import.
   - A pool (`tshape.is_pool`) without `shape_file` is refused, naming Trace shape. A window outside the span, or a missing file, is refused in words.
2. **Gaps.** A window with ≤ 5 % non-finite samples is filled by `np.interp`; an end gap holds the nearest value (deviation: the prompt said linear, and `np.interp` holds ends flat). Windows with more are left out and counted (`n_left_out = {"gaps_over_5pct": k}`); upstream columns are kept on the rest. If every window is left out, it is refused.
3. **Fit set.**
   - Training windows are rows with `split == 0` or `"train"`, else `pool_role == "train"`.
   - With no split column it fits on all windows and puts a warning in `meta["warnings"]` that a downstream held-out score is optimistic.
   - A split with no training window is refused.
4. **Normalise** (default on): per-window z-normalisation. A flat window becomes zeros and is counted (`n_flat`).
5. **Transform.** aeon `MiniRocket(n_kernels=n_features, max_dilations_per_kernel=max_dilations, n_jobs=-1, random_state=seed)` is fit on the training rows, then transforms every kept window in chunks of 4,096.
   - aeon calls `np.random.seed` globally; the block saves and restores numpy's global RNG state around it. This is my addition, and it is tested.
6. **Checks before reading.** Windows shorter than 9 samples are refused in words. A table over `max_cells` windows × features is refused, naming `n_features` and suggesting a value.
7. **Output.** Upstream columns plus `mr_0000…` (float32). Any old `mr_*` columns are replaced, with a warning.
   - `meta` holds: `n_features` (the real count) and `n_features_asked`; `n_windows_in`, `n_kept`, `n_fit_windows`, `fit_on`, `split_column`; `n_left_out`, `n_interpolated`, `n_flat`; `seed`, `max_dilations`, `normalise`, `source`; `table_mb`; `seconds` {read, fit, transform, total}; `warnings`, `rules`, `summary`.

Other deviations from the paper: z-normalisation is a parameter (the paper's UCR data are already normalised). The ridge pairing is not used, because the classifier is unchanged.

### 4. Tests
- **Red:** `edd59fd`. `test_minirocket.py` failed to collect (ImportError: no `Working.Catalogue.minirocket`). The adapter tests gave 6 errors (unknown adapter). The template gave 2 failures (Unknown adapter 'catalogue.minirocket'). Both count tests failed on 49 ≠ 50. Totals: 4 failed, 2 passed, 6 errors, plus 1 collection error.
- **Green:** `d497ca0`.
  - `test_minirocket.py` + `test_adapter_minirocket.py`: 36 passed, 33 s.
  - The template test plus `test_block_standard`, `test_adapter_spec`, `test_import_boundaries`, `test_templates` and `test_end_to_end`: 231 passed, 116 s.
- **What the tests pin:**
  - Feature count rounded to multiples of 84 (10,000→9,996; 1,000→924; 50→84) and reported as the table's real width; float32; names.
  - Determinism for a fixed seed, and a different seed differs; the global RNG is restored.
  - Fit on train: changing only the test windows leaves the train rows' features identical, and changing the train windows changes the test rows' features.
  - Fit on all, with the warning, when there is no split; a string split and a pool role are read; a split with no training window is refused.
  - The three classes on all three backgrounds reach ≥ 0.8. Catch22 is measured and printed, not asserted greater; both are asserted ≥ 0.8.
  - Shuffled labels: the maximum stays below chance + 3 sd and the mean below chance + 2 sd.
  - Normalise: invariant to per-window gain and offset when on, sensitive when off.
  - Flat window; channel-absolute slicing with a 5,000-sample span offset; a window outside the span refused.
  - Pool: read from a real `ShapeSet` file by `shape_row`, stored in reverse order, with `x` all-NaN, and equal to `fingerprint_matrix` on the vectors directly. A pool without `shape_file` is refused naming Trace shape; a missing file is refused.
  - NaN at 2 % and 1 % interpolated, 10 % left out, upstream `tag`/`split` kept on the rest; all windows NaN-heavy refused; length 8 refused; over `max_cells` refused naming `n_features`; empty set refused; rules and meta keys present.
  - Adapter: types, category, page name, defaults and bounds, `validate_params` refusing `n_features=10`, a run on Sliding-windows output, missing value refused, derive rows (error over the ceiling), cost model registered, estimate `None` uncalibrated and scaled by feature count once calibrated.
  - Template: kind `training` equals `kind_for_steps`; runs end to end with holdout 0.95 (per class 0.90 / 1.00, 60 train / 20 holdout, 19.5 s); the classifier saw 924 `mr_` features; the MiniRocket step fitted on the training block only.

### 5. Integration snippets
**Template** (the `CANONICAL` entry, from the test):
```python
{
    "name": "minirocket_manual_labels", "kind": "training", "version": 1,
    "description": "10-minute windows with a blocked split → MiniRocket (a shape fingerprint per window, fitted on "
                   "the training windows only) → manual labels (human verdicts, containment, non-overlapping) → "
                   "classifier on the fingerprint: can this label be learned from the raw shape at all?",
    "steps": [
        _step("preprocessing", "sliding_windows", {"window_s": 600.0, "split_rule": "blocked_by_time"}),
        _step("catalogue", "minirocket", {"n_features": 1_000}),
        _step("catalogue", "manual_labels", {"non_overlapping": True}),
        _step("catalogue", "classifier", {"n_estimators": 100},
              side_inputs={"windows": {"source_kind": "earlier_step", "step_index": 1}}),
    ],
}
```
`n_features` is 1,000 in the template on purpose: see risk 1.

**Glyph** (`BY_NAME["catalogue.minirocket"]`, 44 × 26):
- a short grey wiggly window trace across the left half;
- three tiny blue 9-tap combs (short vertical ticks, spaced 1×, 2× and 4× apart) over it;
- a column of blue/white cells on the right (the feature vector), a few cells filled;
- one amber horizontal tick across a comb (the bias cut).

**Smoke state** (`zz_analyse_run.json`): run `minirocket_manual_labels` on a 10-min-labelled channel and open block 02 (MiniRocket). Expect `[data-testid="block-view"]` with `data-view="windowset"` and `data-modifier="windowset->windowset"`, the heatmap, and the split colouring; `"rule9": true`.

**COSTED:** add `"catalogue.minirocket"` to `tests/test_block_standard.py::COSTED`. Then run `python -c "from Working.block_cost import calibrate; calibrate(['catalogue.minirocket'])"`.

### 6. Open questions and risks
1. **The classifier is very slow on a 10,000-column table** (not changed, per the prompt). `catalogue.classifier` runs `preprocess_window_matrix`, whose correlation filter is `df.corr()` plus a Python double loop, quadratic in columns. Measured on 60 windows: 840 features 4.6 s, 2,520 features 38.6 s, 9,996 features **777.6 s (13 min)**, keeping 9,906 columns. I therefore kept the block default at the paper's 10,000 and set the template to 1,000. The `n_features` help text states the measured times.
   - **For the researcher, plainly:** the block can make a 10,000-number fingerprint quickly, but the classifier's clean-up step then compares every column with every other one. At 10,000 columns that is 13 minutes for 60 windows.
   - **Options:** (a) keep 1,000 in the template; on synthetic data it lost little — 0.82 vs 0.84 on AR(1), equal on the others. (b) The manager lets the classifier skip the correlation filter above N columns; this changes the classifier's behaviour but not its hash.
   - **Recommendation:** (a) now, (b) later if 10k is wanted.
2. **The "clearly beats Catch22" criterion did not hold** on my synthetic sets (table above). Check on real data: the same forest on MiniRocket and on Catch22 over M2_aug's 10-minute labelled windows, same split.
3. **The classifier's holdout is a random stratified split over all labelled windows**, not the blocked `split` column. So its holdout windows include some windows whose content set the biases. The leak is label-free and therefore small, but the classifier's number is not a blocked-split score.
4. **Real labels sit on a 600/200 grid** (three phases). Sliding windows forces gap ≥ window, so its tiling only catches labels on one phase — about a third, depending on where the span starts. `manual_labels_model` uses Window matrix for exactly this reason. Worth checking how many labelled windows the template keeps on a real channel; Window matrix has no `split` column, so MiniRocket would fit on all windows, with the warning.
5. **Pool path quirks:**
   - A pool fed to the classifier would train on the pool metadata columns (`pool_recording_id`, `pool_start`, …). That is pre-existing classifier behaviour, made more likely here.
   - If MiniRocket leaves pool windows out, a downstream `catalogue.shape_cluster` would refuse on the count mismatch.
   - `estimate` scales with span length, which is meaningless for a pool.
6. **Payload size:** a 10k-column WindowSet goes through the step cache (parquet) and the WindowSet heatmap serializer. `serialize.py` may need a column cap for `mr_*`; I did not touch it.
7. **RQ file:** RQ1 gains a second feature arm. I did not edit `docs/rq_roundA/`, because 00-common forbids it; the manager should note it there.

### 7. Commits
```
d497ca0 w2-c: catalogue.minirocket -- a MiniRocket shape fingerprint per window (Dempster, Schmidt & Webb 2021)
edd59fd w2-c: tests (red) -- catalogue.minirocket, a MiniRocket shape fingerprint per window, and the minirocket_manual_labels template
```
