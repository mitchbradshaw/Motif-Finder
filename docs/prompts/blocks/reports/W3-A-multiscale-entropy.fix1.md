> Filed by the manager session, 2026-10-14 23:40 — the final message of implementer agent `a67442d9e04015d6a`,
> resumed for fix round 1 on branch `worktree-agent-a67442d9e04015d6a` (`2eb9be9` red, `ffe51b2`), verbatim.

## W3-A fix round 1 — fix report

All seven items are done, test-first. Red `2eb9be9` → green `ffe51b2`, on the same branch and base `01cb8c3`; main was not merged.

**Red (tests only, `NUMBA_NUM_THREADS=4`): 40 failed, 96 passed.**
- Inflation guard tests: 6 √t cases and 12 "must not flag" cases.
- Bookkeeping, more than 5 % filled, MAD = 0, RCMSE = MSE naming, readable lengths.
- 2 costliest-tiling tests, and the block and template description tests.
- All 5 of the new `tests/test_all_nan_feature_rows.py`.
- 5 surrogate tests, 1 method-list test, 1 seeded-search test.

**Green:** 559 passed with conda across:
- all three block test files;
- `test_block_standard`, `test_adapter_spec`, `test_import_boundaries`, `test_templates`;
- every cluster, classifier, surrogate and seeded-search test file (event windows, sliding windows, manual labels, classifier baseline, correlation filter, discovery compare, grouping, HPC dependencies, model, registration artifacts, event-clusters template, MiniRocket template, `test_minirocket`, `test_types`).

**Two failures remain, neither from this change:**
- **Venv python:** `test_webui_registration`, `test_webui_discovery` and `test_webui_block_views` gave 87 passed, 1 failed. The failure is `test_webui_discovery::test_the_scoreboard_cells_are_the_tables_own_numbers`, a Discovery coverage-rule string mismatch in code I did not touch.
- **`tests/test_drop_motifs_nulls1.py`:** all AAFT tests pass. One test fails because `Plots/drop_motifs9_fig2a/run_summary.json` is absent in the worktree (environmental, as you expected).

### Per item

**1. Collapse guard now uses the inflation rule.**
- Inflation = the r rule's spread of the window as it arrives ÷ the same spread after a centred 2 h rolling mean is taken out. The rolling mean is `make_detrend_filter`, which is NaN-aware, and the data the block measures is unchanged.
- Inflation > 1.5 flags every defined scale of that window. It shows in `meta.collapse`, `meta.warnings` and the summary.
- New: an `mse_inflation` column, plus `inflation_median`, `inflation_max` and `inflation_limit` in meta, and a per-window `inflation` in `curves`.
- The parameter `collapse_ratio` is replaced by `inflation_limit` (1.5). 1.5 and 2 h are labelled placeholders with the critic's numbers in the help text and the rule.
- ρ stays in `meta.rho_median` with a "smooth" rule, and is no longer a warning. The warning no longer suggests `r_scale = mad`.
- Tests run on seeds 1–3:
  - √t cases (raw random walk, and raw AR(1) φ 0.97 + smooth drift, both with `r_scale="sd"`) flag every defined scale.
  - Template-detrended random walk, AR(1) φ 0.95, AR(1) φ 0.99 and raw pink noise flag none.
- The old single-seed random-walk test is removed on purpose (it encoded a coin toss); the commit says so.

Measured inflation at 24 h, seeds 1–3:

| Case | Inflation |
|---|---|
| Raw random walk, SD | 6.42, 5.32, 4.33 |
| Raw AR(1) + drift, SD | 8.36–8.44 |
| Detrended random walk | 0.96–1.10 |
| AR(1) φ 0.95 / 0.99 | 1.00–1.02 |

**2. Bookkeeping, and left-out rows in cluster and classifier.**
- `mse_r`, `mse_drift_share` and `mse_inflation` joined `BOOKKEEPING_COLUMNS`, each with its reason.
- **Existing test changed deliberately:** `tests/test_adapter_event_windows.py::BOOK` pins that set. It now lists all five `mse_*` columns. Round 1 had already broken it with `mse_n_scales` / `mse_n_collapsed`; I missed that test then.
- `catalogue.cluster`: rows with all features NaN (after the bookkeeping drop) are left out and labelled **-1**, the value `manual_labels` uses and the classifier already skips. Cluster labels start at 1. They are counted in `n_left_out`, `left_out_reason`, `n_clustered` and the summary, and the derive row warns. The kept rows cluster exactly as they would alone (tested).
- `catalogue.classifier`: those rows are never fitted or scored. They are counted apart from the Grouping's own exclusions (`n_no_features`, `no_features_reason`, `summary`). If every row is empty the run is refused in words. `_feature_matrix` now returns five values; its two callers in `test_adapter_event_windows.py` unpack with `*_` and are unaffected.

**3. The estimate assumes the costliest tiling.**
- It is n × the largest pairs(W)/W over every breakpoint (±1 sample) and a 600-point geometric grid (`costliest_pairs`, adapter `estimate_pairs`).
- Pinned: tilings of 1, 2, 6, 24 and 72 h at 1 Hz and 10 Hz never exceed the estimate in pair units.

Measured on 721 h at 1 Hz (detrended AR(1), freshly calibrated, loaded machine):

| Windows | Estimate | Actual | Tiling pairs ÷ estimate |
|---|---|---|---|
| 72 h (10 windows) | 116.7 s | 28.9 s | 0.31 |
| 6 h (120 windows) | 116.7 s | 83.2 s | 0.92 |

**4. Interpolation shows on the face.** A window more than 5 % filled is left out as `filled_over_5pct`; the 5 % is a labelled placeholder. Any interpolated windows produce a warning ("N of M windows had missing samples filled …") and "· N filled" in the summary.

**5. Nits.**
- The rule "rcmse = mse" names the scales where only one offset is pooled. They are also in `meta.rcmse_equals_mse_scales_s`, and the summary shows "(= MSE up to X s)".
- New reason `mad_zero` ("MAD = 0 (mostly constant…)"), separate from `flat` (SD = 0); the window is still left out.
- `readable_seconds` gives "10 min", "5.6 h" and "72 h", used in warnings and the summary.

**6. Template keeps 72 h.** Its description (in the test's `TEMPLATE` constant, for you to move into `CANONICAL`) now says:
- A recording shorter than 72 h gets no window and the run stops at Sliding windows.
- Set `window_s` to the longest whole multiple of 24 h the recording allows; a 24 h window reaches about 50 s.
- Judge a curve against amplitude-adjusted (aaft) copies.

**7. AAFT as an app null.**
- `aaft_surrogate` moved into `Adapters/preprocessing_surrogate.py`, and `preprocessing.surrogate` gains method `aaft`. The default stays `phase_randomize`, so no recipe hash moves.
- `Pipelines/drop_motifs/nulls1.py` imports it back. It is bit-identical: tested against a verbatim copy of the old function, through `nulls1.aaft_surrogate` and `make_surrogate`.
- `seeded_search`: `_LABELS` ("amplitude-adjusted phase randomisation"), `_NOTES` (`AAFT_NOTE`), aliases, `BLOCK_METHODS`, and the refusal text, which now lists all three methods.
- **Tests changed deliberately:** `test_surrogate.py::SURROGATE_METHODS` and `test_null_draws_methods_cut.py::test_every_method_on_offer_is_one_the_block_runs` now pin `[phase_randomize, block_shuffle, aaft]`.
- The block's and template's descriptions say to use aaft copies, not plain phase-randomised ones.

### For you to integrate
- **Template:** move the updated `TEMPLATE` from `tests/test_template_complexity_fingerprint.py` into `CANONICAL` (I did not touch `webui/server/templates.py`).
- **Serializer:** the cluster and classifier `meta["summary"]` / reason strings, and multiscale entropy's `meta.summary` and `meta.warnings`, do not reach the face until `serialize.py` reads them.
- **Pages:** check that the Grouping view draws label -1 as "no label" (grey).

### Not done
Nothing from the list was skipped. The one webui failure above is outside this change.
