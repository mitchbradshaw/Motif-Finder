> Filed by the manager session, 2026-10-14 09:39 — the final message of implementer agent `aa6497544feed7c56`,
> resumed for fix round 1 against `W2-C-minirocket.critic.md`, verbatim.

## W2-C fix round 1: report

All seven decisions are done, each as a red-then-green pair. The requested gate passes: 375 passed, 4 skipped, 0 failed. I did not merge or rebase; the branch still sits on 04948e3.

**In plain words.** The time estimate now measures the real work, so a run of about 18 s is estimated at about 24 s instead of over an hour. The template now uses the same 10-minute windows on the labels' 200 s grid as `manual_labels_model`, so the MiniRocket arm and the Catch22 arm of RQ1 differ only in their features. On a synthetic set of 90 labels spread over the grid's three positions, the new template keeps all 90; the old Sliding-windows version keeps under half. The classifier now also reports balanced accuracy and the majority-class share, so a run that only learned "always say the common class" can be spotted.

### What changed
1. **Cost model (finding 1)** — 1424a1f (red) → 6e8a812 (green).
   - `Working/block_cost.py`: W2-D's 8075b8d hunk applied verbatim with `git show 8075b8d -- Working/block_cost.py | git apply`. No other edit to that file.
   - The adapter registers `warm_up=_warm_up`: it imports aeon and runs one 84-feature transform on four 64-sample windows.
   - `_time_once` now times 120 windows per 600 samples of the calibration signal (stride 5), i.e. 3,881 windows at the default 10,000 features.
   - `_estimate` converts back to seconds per window-sample. It assumes the labels' 600/200 grid (`GRID_OVERLAP = 3`), because the estimate only sees the span length. A set of windows laid end to end costs a third of the estimate.
   - Red: `AttributeError` on `CAL_WINDOWS_PER_LENGTH` and on `WARM_UPS`.
   - Tests: the warm-up is registered and runs before the timed call; the timed call gets 3,881 windows of 600 samples at 10,000 features. No timing is asserted.
2. **Correlation filter (finding 2)** — 62eceb2 → d1b5bf2.
   - `dendrogram_cluster.py` gets `CORRELATION_FILTER_MAX_COLUMNS = 2_000`. Above it `_remove_correlated_columns` is skipped, and the new field `PreprocessResult.correlation_filter_skipped` (default `None`) records the width.
   - `correlation_filter_note()` gives `catalogue.classifier` and `catalogue.cluster` a `meta["correlation_filter"]` line: "applied", or "skipped: N columns (over 2,000; the filter is quadratic in columns)".
   - No existing producer reaches 2,000 columns: `test_no_existing_window_matrix_reaches_the_ceiling` adds up `STAGE_COLUMNS` over all five Window matrix families and stays below it.
   - Existing tests pass unedited. Red: 6 failed (attribute missing; the duplicate column was dropped).
3. **Label grid (finding 3)** — 9acd5eb → 632ea99.
   - MiniRocket gains `keep_upstream_features` (bool, default `True` = old behaviour). With `False` it keeps the fingerprint plus `split`, `pool_*`, `shape_file`, `shape_row`, `shape_orig_start`, `shape_clamped`. Measured columns are dropped and counted in `meta["upstream_dropped"]`, and there is a matching rule.
   - The `n_features` help and the description now say: a "no" at 1,000 is not a "no"; the decisive run is 10,000 on a shorter span; a fit on all windows is acceptable on the grid because it is label-free.
   - New template test: it fits on all windows with the warning, and no Catch22 column reaches the classifier.
   - Grid vs Sliding windows on 90 labels over phases {0,1,2}: the grid keeps all 90, Sliding windows under 45 (the assertion is `< 0.5 × 90`).
   - Red: 6 failed (unknown param `keep_upstream_features`; the help text). I loosened one pin from my own earlier test in the green commit: `n_features_in == 924` became 900–924, because the classifier's clean-up drops one constant or correlated column on the grid recording (923).
4. **Classifier meta (finding 4)** — b8c8c5a → 3bdf558. `balanced_accuracy` (mean of the per-class accuracies) and `majority_baseline` (the holdout's majority-class share) sit beside `holdout_accuracy`; both are `None` without a holdout. Only the meta block of `_run` changed; the imports and `_feature_matrix` are untouched. Red: `KeyError` ×2.
5. **Thread safety (finding 5)** — 1624658 → 88613a1. `_AEON_LOCK` wraps the fit, the transform and the RNG save/restore. The docstring now says the state is restored within the calling thread and another thread drawing from numpy's global RNG during a fit is disturbed (the fingerprint is not). Red: `AttributeError: _AEON_LOCK`.
6. **max_cells wording (nit 6)** — same pair. It suggests an `n_features` value only when a multiple of 84 fits; otherwise it says "use fewer windows" alone. Red: the message still offered "e.g. 84".
7. **Persistent-label null (nit 7)** — in 1624658; it passed on arrival because it pins existing behaviour. Setup: runs of 12 ten-minute windows, no shape difference, φ drifting from 0.90 to 0.995, scored on the blocked split. Balanced accuracy 0.479 / 0.472 / 0.479 (sd 0.065).

### Estimate vs actual
2.6 M samples, run in a fresh process with a temporary `CALIBRATION_PATH`. Calibration took 61.5 s (the warm-up absorbs the slow first aeon call); k = 3.614e-4.

| n_features | Estimate | Actual, 600/200 grid (12,998 windows) | Actual, end-to-end windows (4,333) |
|---|---|---|---|
| 10,000 | 23.5 s | 18.2 s | 5.1 s |
| 1,000 | 2.2 s | 3.0 s | 1.0 s |

Before this fix the critic measured an estimate of 6,370 s against 8.4 s actual.

### The template as it now stands (verbatim)
```python
TEMPLATE = {
    "name": "minirocket_manual_labels", "kind": "training", "version": 1,
    "description": "RQ1's manual-label arm on a shape fingerprint: 10-minute windows on the labels' 600/200 grid "
                   "(the same windows as manual_labels_model) → MiniRocket (1,000 features, only the fingerprint "
                   "kept) → manual labels → classifier. Can this label be learned from the raw shape at all? A 'no' "
                   "at 1,000 features is not a 'no': fewer features lose real accuracy on weak shapes, and a whole "
                   "channel at 10,000 is over MiniRocket's memory guard — the decisive run is 10,000 features on a "
                   "shorter span. MiniRocket fits on every window here (Window matrix carries no split): its fit "
                   "never sees a label, so that cannot leak a label into the score. Read balanced accuracy against "
                   "the majority baseline, not plain accuracy.",
    "steps": [
        _step("preprocessing", "window_matrix", {"window_min": 10.0, "step_frac": 0.334, "slow_entropy": False,
                                                 "fast_entropy": False}),
        _step("catalogue", "minirocket", {"n_features": 1_000, "keep_upstream_features": False}),
        _step("catalogue", "manual_labels", {"non_overlapping": True}),
        _step("catalogue", "classifier", {"n_estimators": 100},
              side_inputs={"windows": {"source_kind": "earlier_step", "step_index": 1}}),
    ],
}
```
Window matrix refuses to run with every family off ("No stages selected"), so Catch22 stays on in step 1 as you specified. `keep_upstream_features=False` then drops it.

### Notes for merging
- Files touched outside the original list, each by your decision: `Working/block_cost.py` (the identical W2-D hunk), `Working/Catalogue/dendrogram/dendrogram_cluster.py`, `Adapters/catalogue_classifier.py` (the meta block plus a small `_correlation_filter_note` helper placed before `_derive`), `Adapters/catalogue_cluster.py` (`_cluster_window_set` now carries `correlation_filter_skipped` on its result).
- New test files: `tests/test_correlation_filter_ceiling.py`, `tests/test_classifier_baseline_meta.py`.
- The new `keep_upstream_features` parameter changes the defaults-filled recipe hash of MiniRocket recipes. None exist on main yet. The 632ea99 commit body has a garbled half-sentence about this; I left it unamended.
- The red message in 9acd5eb names `KeyError` / `TypeError` for two of the failures. I did not paste those two tracebacks, so treat the exact exception names there as unchecked.
- Gate run: my three test files, `test_correlation_filter_ceiling`, `test_classifier_baseline_meta`, the cluster/classifier/dendrogram users (`catalogue_manual_labels`, `grouping_adapter`, `model_adapter`, `discovery_compare`, `hpc_job_dependencies`, `registration_artifacts`, `adapter_sliding_windows`, `webui_block_views`), plus `block_standard`, `adapter_spec`, `import_boundaries`, `templates`, `end_to_end`.

### `git log --oneline 04948e3..HEAD`
```
88613a1 w2-c: fixes 5-6 -- aeon runs under a module lock; the max_cells refusal names only what can help
1624658 w2-c: tests (red) -- fixes 5-7: a module lock around aeon, the max_cells wording, a persistent-label null
3bdf558 w2-c: fix 4 -- the classifier's meta carries balanced_accuracy and majority_baseline
b8c8c5a w2-c: tests (red) -- fix 4: balanced accuracy and the majority baseline in the classifier's meta
632ea99 w2-c: fix 3 -- keep_upstream_features; the template on the labels' 600/200 grid
9acd5eb w2-c: tests (red) -- fix 3: the template moves onto the labels' 600/200 grid; keep_upstream_features
d1b5bf2 w2-c: fix 2 -- the correlation filter is skipped above 2,000 columns; the classifier and cluster say so
62eceb2 w2-c: tests (red) -- fix 2: the correlation filter is skipped above 2,000 columns, and said so
6e8a812 w2-c: fix 1 -- the cost model warms up untimed and times 3,881 windows, not the aeon import
1424a1f w2-c: tests (red) -- fix 1: the cost model warms up untimed and times thousands of windows
d497ca0 w2-c: catalogue.minirocket -- a MiniRocket shape fingerprint per window (Dempster, Schmidt & Webb 2021)
edd59fd w2-c: tests (red) -- catalogue.minirocket, a MiniRocket shape fingerprint per window, and the minirocket_manual_labels template
```
