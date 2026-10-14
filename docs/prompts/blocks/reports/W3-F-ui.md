> Filed by the manager session, 2026-10-15 04:37 — the final message of implementer agent `a9bcefee16fc666b3` on
> branch `worktree-agent-a9bcefee16fc666b3` (`027561d` red, `d1dc46c` on `a5baf8b`), verbatim.

## W3-F report: wave 3's UI (branch `worktree-agent-a9bcefee16fc666b3`, base `a5baf8b`)

### 1. In plain words

**What was fixed.** Two everyday problems are fixed and three new pictures are added.

- **A long step can now be stopped from inside.** Before, a run checked for "stop" only between steps, like a lift that only answers between floors. Now a block that checks for a stop as it works will stop within one of its own iterations. These blocks are window matrix, multiscale entropy, the pan matrix profile and cycle shapes. The job then reads *cancelled*, not *failed*, and nothing half-done is cached. The run panel shows the block's own real progress ("12 of 40 windows, 30 %"). Before, it showed a spinner.
- **Every costed block is timed before a run is routed.** Before, a block whose speed had never been measured on this machine ran blind, whatever its size. Now the bridge measures it on first need, in the background.
  - Most blocks finish measuring within the request.
  - The slow ones read "calibrating", and Run waits until the measurement lands.
  - An estimate that fails now shows its own words instead of a bare "uncalibrated".
- **The three new pictures:**
  - **MSE curves:** one complexity curve per window, with undefined scales left as gaps.
  - **The cycle stack:** every drop-to-drop cycle as a row, before and after lining them up, with the block's verdicts and each group's typical cycle.
  - **Pan matrix profile rows:** labelled with their window lengths, plus the block's verdict per length. The wavelet transform's rows now get frequency labels the same way.

**Synthetic checks.**
- A fake slow block stopped within one iteration of a cancel. This held for the real run and for a null draw.
- The real cycle-shapes block's output, with two trains, serialised and drew its `t1:1` / `t2:1~noise_like` keys.
- The real MSE block on 2 × 1 h windows gave curves defined at 1–2 s. The other 10 scales were blank and the block warned about them on the page.

### 2. Files

**Server (Deliver list)**
- `webui/server/runs.py`: `run_kwargs` (cancel and progress) passed to the run and to the null draws. Adds `steps[i].progress`, a `step_progress` event, the draw's progress on `null_progress`, `null.cancelled`, and a guard that stops `_emit` raising once the event loop is closed.
- `webui/server/chain.py`: the background block-cost calibration, the `calibrating` and `errors` fields on the estimate and the route, and `required` on side inputs.
- `webui/server/serialize.py`:
  - MSE: `curves` and `curve_flags`; a non-anchored WindowSet now shows its block's summary and warnings.
  - Cycle shapes: `cycle_stack`, `cycle_sequences`, `cycle_exemplars`.
  - Image rows: `row_axis` and `row_verdict`.
  - Families table: more `FAMILY_KEYS`.
  - `catalogue.cluster`: −1 named "no label", and `label_base` counts real labels only.
- `webui/smoke_pages/zz_analyse_run.json`: 9 `w3-*` states.

**Client (Deliver list)**
- `webui/client/src/api.ts`: types for everything new.
- New `analyse/MseCurves.tsx` and `analyse/CycleStack.tsx`.
- `analyse/views/registry.tsx`: wiring and a warnings strip.
- `analyse/views/EncodingView.tsx`: row labels and the per-row verdict table.
- `analyse/glyphs.tsx`: three glyphs.
- `analyse/ChainPage.tsx`: the run panel's real progress bar, the cancel wording, the estimate's own words, and Run held while calibrating.
- `library/Edges.tsx`, `discovery/AddMatches.tsx`, `library/FamilyPage.tsx`, `analyse/views/GroupingView.tsx`: MPdist and σ²-first (item 10, decision 3).

**Docs:** `docs/BLOCK_INTEGRATION.md` §2 gains one row, the row-axis convention.

**Out of the Deliver list (each needed):**
- `analyse/store.ts`: the `step_progress` case, so the run panel can show progress.
- `analyse/useValidation.ts`: asks again every 3 s while a step is calibrating.
- `analyse/InsertStageModal.tsx`: one line that reads `required`.
- `webui/server/runtime.py`: the sandbox now redirects block_cost's relative calibration path into its runtime. Unredirected, a sandbox would write the checkout's `DATA/db/block_calibration.json`.
- `Working/block_cost.py`: `calibrate(..., path=None)`, additive. The background thread writes the file it started with, and the function re-reads the file before writing.
- `Adapters/preprocessing_window_matrix.py`: raises `RecipeCancelled` when cancelled (7 lines). See item 1 below.

**Tests:** new `tests/test_webui_run_cancel.py`, `tests/test_webui_w3f_payloads.py` and `tests/test_webui_w3f_ui.py`; `tests/test_webui_run_routing.py` extended.

### 3. What was built, item by item

1. **Cancel and progress inside a step.**
   - The one cancellation exception is `RecipeCancelled`. W3-A, W3-B and W3-C already raise it.
   - Window matrix used to return a partial table with `meta.cancelled`, and the executor cached it as if it were whole. It now raises, and a resumable build's saved file is untouched.
   - Progress events are throttled to one per 0.25 s; the last one always goes out.
   - Fixed on the way: `null_progress` was emitted but the client never subscribed to it.
2. **Calibration.**
   - Calibration times I measured in a fresh process after the registry import:

     | Model | Calibration |
     |---|---|
     | rupture | **447 s** |
     | snippets | 19.8 s (1.8 s warm) |
     | MiniRocket | 7.5 s (61.5 s if aeon is not yet imported) |
     | cycle shapes | 4.6 s |
     | deconvolve | 2.9 s |
     | MSE | 2.1 s |
     | all others | under 1.5 s |
     | cnn_score | fails: no model file; the error now shows in words |

   - The decision: calibrate in a background thread on first need, not at bridge start. Before `Runtime.setup()` the calibration file still points at the real `DATA/db`, and `app.py` is not mine.
   - `route_local` waits up to `CALIBRATION_WAIT_S` = 10 s, then answers "calibrating".
   - One calibration runs at a time. A failed one is retried after 60 s.
   - The routing tests now pass with the webui venv's Python, including the case where a block-cost chain over the limit is refused with a SLURM script.
   - What the manager's preflight already covered: matrix-profile calibration was already in place, so nothing else was skipped.
3. **MSE curves.**
   - Scale is on a log x axis, one line per window, the median bold.
   - `polylinePath` breaks the line at a null, and a lone defined point is drawn as a dot.
   - Collapse flags are amber rings, with a count per scale. Scales undefined in every window are shaded.
   - The MSE bookkeeping columns leave the heatmap.
   - **No grey null band.** The paired null is only a count today. A band would need the bridge to keep each null draw's step payload or meta.
4. **Cycle stack.**
   - Two canvases (before and after alignment), rows in time order, and a group-colour strip.
   - The block's own `change_points_s` are drawn as amber lines.
   - A verdicts table shows `whole_verdict` and each group's `verdict` and `key` as given, σ² first. Nothing compares a score with a null.
   - Each group's medoid cycle is drawn from the recording, as anchor to anchor + `cycle_length_s`, with a scale bar.
   - The cycle groups do not reuse the Event families drawing: the payload has no `families`, and making those rows up would mean re-deriving verdicts.
5. **Pan matrix profile rows.**
   - One convention for any image whose rows are not pixels: `meta.lengths_s` (s) or `meta.freqs_hz` (Hz), one value per row, row 0 at the top.
   - A list whose length does not match the image's rows is refused loudly.
   - `per_length` is shown as given, with `suggested_window_s` and the `verdict` sentence or "no length stands out".
   - Built against W3-C's branch `925056a` form: `per_length[].{judged, clears, gap, reason}`, `suggested_row`, `approximate_note`.
6. **The CWT scalogram with ridges (optional): skipped** for time. Nothing in `detection_cwt_ridges.py` was touched.
9. **"Event loop closed":** it was a one-liner, and it is fixed.
10. **MPdist.**
    - An edge with `within === null` prints "—" in a neutral colour, with its `footing` as the tooltip. Only `within === false` is purple.
    - The read-out table gains an MPdist column, with "k could not be compared" and "k added before MPdist — run Add N matches again" (`missing_rule` as the tooltip).
    - *Add N matches* shows `refusalSummary` as a neutral, expandable line with one row per refused pair.
    - `MPDIST_TOOLTIP` is copied verbatim into `Edges.tsx`; the server does not send it.
    - No `mpdist_null` reaches any payload today, so there is nothing to show for it.
11. **σ² first.**
    - Family page: σ² from `variants[0]` as a number (its ratio and note), eq. 17 below it with the verdict badge.
    - The badge says which null passed: "beyond noise (quiet stretches / trend-kept / both)".
    - The fallback shows on the badge itself: "judged on trend-kept noise only: <reason>".
    - A context line gives `background_s`, borrowed windows, detection-overlap share and `family_scored_on`.
    - The families table gets the same, with a σ² column before eq. 17.
    - k-Shape's "null not trusted" branch is **left dormant** and commented: it no longer fires, and it guards any future method that sets `confident` to None.

### 4. Tests

- **Red: `027561d`**, tests only.
  - `test_webui_run_cancel.py`: 5 failed, 1 passed (the control).
  - `test_webui_run_routing.py`: 2 failed, 7 errors.
  - `test_webui_w3f_payloads.py`: 13 failed.
  - `test_webui_w3f_ui.py`: 11 failed.
- **Green: `d1dc46c`.**
  - Conda: 298 passed (the w3f files, `test_webui_serialize`, `test_webui_w2f_ui`, `test_webui_job_estimate`, `test_block_standard`).
  - Venv: `test_webui_run_routing` 19 passed. With `test_webui_block_views`, `test_block_standard` and others: 258 passed.
  - The whole `tests/test_webui_*.py` plus `test_execution` and `test_adapter_multiscale_entropy` under venv, `-n 4`: 615 passed, 2 failed.
    - `test_webui_discovery::test_the_scoreboard_cells_are_the_tables_own_numbers` fails before my change too (W3-A reported it).
    - A routing test failed from cross-test lock contention under xdist. I fixed that (reset gives a fresh lock and ignores stale threads) and the file now passes. I did not re-run the whole 13-minute set after the fix.
- **One test changed after red:** in `test_webui_w3f_ui.py` the scale-bar pin now checks for `<ScaleBar` (the shared component owns the testid), and the panel testids are checked as strings.
- **What the tests pin:**
  - A cancel lands within one iteration; the job reads cancelled; no cache entry (against a control that does write one).
  - Progress reaches the job and the stream; null draws stop.
  - Window matrix raises; `_emit` survives a closed loop.
  - Background calibration, "calibrating", calibration failure in words, estimator errors in words, over-limit routed to the cluster, the sandbox path, the thread writing the path it started with.
  - Every payload form; loud refusals for a bad exemplar or a row count mismatch.
  - Source pins: payload-driven, no block names.
- `npx tsc -b` and `npm run build` are clean. They were run in a scratch copy with a junction to the main checkout's `node_modules`; the junction was removed with `cmd /c rmdir`, and the main `node_modules` is intact.

### 5. Integration notes and what each smoke state should show

**Smoke states** (sandbox, 2 h example span unless noted). Order: MSE → cycle → wavelet → pan → cancel. Each chain state rebuilds its chain from the `noise_threshold` template, so hashes never repeat.

| State | What it should show |
|---|---|
| `w3-mse-thumbnails` | detrend → Sliding windows (`window_s` 3600) → MSE. Row 3 paints a windowset. Run waits for the button to enable; MSE calibrates in about 2 s. |
| `w3-mse-curves` | block/2: `[data-view=windowset][data-modifier="windowset->windowset"]`, `mse-curves svg[data-render=curves]`, two `mse-curve` lines, `mse-median`. Lines defined at 1–2 s, 10 scales shaded blank, amber warnings strip. |
| `w3-cycle-shapes-thumbnails` | noise_threshold → Cycle shapes. Row 3 paints a spanset. Allow up to 180 s: 20 background draws plus about 4.6 s calibration. |
| `w3-cycle-shapes-stack` | block/2: `cycle-stack`. If fewer than 2 cycles are found, it shows its own empty state, which is still `cycle-stack`. Otherwise the two heat-maps, the group strip, the verdict table and the medoid panels. |
| `w3-row-axis-wavelet-*` | the wavelet transform. block/1 shows `row-axis[data-unit=Hz]` and `row-axis-caption`, and no `row-verdict`. |
| `w3-pan-thumbnails` / `w3-pan-rows-and-verdict` | **need W3-C merged; they fail without it.** `n_lengths` 6, `max_window_s` 900. Expect `row-axis[data-rows="6"][data-unit=s]`, `row-verdict`, the headline and `row-verdict-0`. The first run pays stumpy's 35–46 s compile; the timeout is 180 s. |
| `w3-cancel-inside-a-step` | zoom out 5× and send the span; Sliding windows `window_s` 21600 → MSE. Waits for `step-fraction-3`, clicks Cancel, then expects `chain-row-3[data-status=cancelled]` and row 2 cached, never failed. If the zoomed span is short enough that MSE finishes before Cancel, lengthen it. |

**Glyphs:** in `BY_NAME`, from the reports' sketches (cycle shapes uses W3-B's own TSX).

**When W3-C merges:** if its field names change from `925056a` (`per_length`, `suggested_row`, `verdict`, `approximate_note`, `lengths_s`), update `serialize._row_axis` and its payload test.

### 6. Decisions to confirm and risks

- **Calibration in the background:** I chose this from the numbers above. The researcher was not asked.
- **Rupture's calibration takes 447 s.** Pelt on block_cost's tiny-amplitude random walk finds no change points, so it never prunes. Its route reads "calibrating" for about 7 minutes and one CPU is busy. Fixing it means a better calibration signal in `Adapters/detection_rupture.py`; that is a ticket for the manager.
- **Out-of-list files:** six are listed under Files. The `Working/block_cost.py` and window-matrix changes touch the core and should be reviewed.
- **Colour changes:** −1 is now grey and `label_base` ignores −1, so snippets' unlabelled cluster and a cluster grouping with −1 change colour.
- **Summary text:** a non-anchored WindowSet now prefixes its block's summary, so MiniRocket's and sliding windows' row captions change wording.
- **Not run by me:** the browser smoke walk. The manager runs it.
- **Docs not written:** the `curves` and `cycle_stack` payload conventions deserve rows in `BLOCK_INTEGRATION.md` §2, but only one row was handed to me.

### 7. Commits

```
d1dc46c w3-f: stop and follow a long step, calibrate every costed block before routing, draw what wave 3 found
027561d w3-f: tests (red) -- cancel and progress inside a step, every costed block calibrated before routing, wave 3's drawings
```
