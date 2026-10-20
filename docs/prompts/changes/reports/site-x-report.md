# site-x report — Cross-channel overlay by default, Cross-channel plotting errors, the Analyse lag

Branch `site/x` (cut from `main` f445468). Port 8769. Every commit prefixed `site-x:`.

## In plain words (first)

- **Cross-channel now opens on the overlay**, every channel on one axis. The stacked rows are one click away
  (or `?view=stacked` in the address).
- **The "plotting errors" were two drawing faults, not bad data.** Think of a group photo where one person
  stands much closer to the camera than everyone else. To fit everyone, the photographer either shrinks the
  others to dots or crops the close one off. On CO_fs2 window #1, CH2 drifts about 35 mV while the other three
  move about 0.2 mV. The overlay used one shared scale, so CH2 ran off the plot except for one near-vertical
  stroke. CH2 is now drawn at its own scale, with "÷143" beside its name so nobody compares its height with the
  others. The "straight line at the top of every band" was the channel's **detections**. The window sits inside
  detections that are minutes to hours long, and each one was drawn as a solid bar in the trace's colour. They
  now draw as dashed brackets, merged where they overlap and open-ended where they run past the window, and a
  "╌ detections" legend says what they are. In the stacked view, a row squashed under 2 px by a much wider row
  now says so in words ("flat at this gain … y: per channel draws its shape").
- **The Analyse lag.** I could not reproduce "loading forever" by pulling a span into Analyse. That path answers
  in under half a second, cold or warm, from Signal or Cross-channel, with or without a chain or a run. What did
  reproduce a site-wide slowdown with a chain page stuck loading was a chain holding a block that has not yet
  been timed on this machine. Before Analyse can estimate how long a block will take, it times the block once
  ("calibrating"). That timing ran inside the bridge and competed with every other request. The worst case is
  rupture, about 7 minutes. While it ran, each validation took 10 s and other pages slowed two to five times.
  The timing now runs in a separate process. Only the request that starts it waits; later checks answer
  "calibrating" at once. Nine of the eighteen blocks that have a cost model are still untimed in the real
  database, including spike-train statistics (`interrogation.trains`) and cycle shapes. So this was a live risk
  for the demo walk, though not proven to be the researcher's exact incident.

## Assumed

- **Overlay gain rule.** A channel whose range would not fit the whole block at the shared gain is drawn at its
  own gain, with the factor printed. That is the stack's "per channel" rule, applied only to the row that needs
  it. I did not detrend the drawing in the browser: the brief says numbers come from the bridge, and the page
  says traces are drawn as recorded.
- **Detections in the overlay** still come from every run (unchanged) but are merged and dashed. Filtering them
  by the detections chip, which today filters the reference row only, is left as is.
- **Smoke states.** Every existing state that opens `explore/cross-channel/…` without `view=` got `view=stacked`
  (33 states). That includes states that don't strictly check the stack, so each one behaves exactly as before.
- **Item 3.** The cause I fixed is the one I could reproduce. The researcher's own incident is not proven to be
  it (see "Item 3" below for the other candidate). Per the manager's demo-path rule, nothing in `Working/` or
  `Adapters/` changed, and no estimate or cache key changed.
- **Reading the researcher's log.** I read (and did not write) the researcher's bridge logs under
  `webui/runtime/` of the main checkout, to look for the incident's timeline.

## Item 1 — overlay by default

- `CrossChannelPage.tsx`: `overlay = viewQ !== 'stacked'`. The view switch writes `?view=stacked` and clears it
  for the overlay. The header doc names the new deep link.
- Smoke manifests, `view=stacked` added (scripted, layout preserved):
  - `explore.json`: 15 states
  - `zzz_w_cross_channel.json`: 2
  - `zzzzzzzzzzz_aq_cross_channel.json`: 12
  - `zzzzzzzzzzz_explore_review.json`: 2
  - `zzzzzzzzzzz_overlay.json`: 1. This state is also **renamed** `overlay-stacked-is-default` →
    `overlay-stacked-on-request`, with its `_why` updated.
  - `zzzzzzzzzzz_polish.json`: 1
- Test (conda python): `tests/test_webui_site_x_cross.py::test_the_page_opens_on_the_overlay…`,
  `…every_smoke_state_on_the_page_names_its_view…`.

## Item 2 — plotting errors

**Reproduced** on the main-checkout sandbox bridge, real signals: `CO_fs2.mat` CH1 (id 641), window #1 (0–80 s),
detrend linear, overlay, 4 channels.

| Channel | Range over the window |
|---|---|
| CH1 | 0.15 mV |
| CH2 | 34.97 mV (−409 → −444 mV) |
| CH3 | 0.19 mV |
| CH4 | 0.24 mV |

- **The near-vertical stroke.** The overlay's shared gain is set so the median channel's range fills 1.6 lanes.
  At that gain CH2 was about 145 lanes tall.
- **The horizontal lines.** Each channel carries detections spanning the whole window: CH1 has 17, several from
  0 s to 128–7860 s; CH2 has 235. Each was drawn as a solid 2.5 px bar in the trace colour at the top of its lane.
- **Stacked view, same window.** The centred gain is CH2's 34.97 mV, so CH1, CH3 and CH4 draw 0.2–0.4 px tall:
  flat, with nothing said.

**Changes:**

- New `webui/client/src/explore/overlayModel.ts` (import-free, run by Node in the tests):
  - `overlayGains`: per-channel gain; own scale plus factor when a channel cannot fit the block.
  - `mergeDetectionMarks`: overlapping detections become one mark, clipped to the window, with open ends.
  - `drawnRowPx`, `FLAT_PX = 2`.
- `Overlay.tsx`:
  - per-channel gain, with `÷N` beside the name (`ov-own-scale-<name>`);
  - detections as dashed brackets (`ov-detection`, `data-n`);
  - a lane that cannot draw (read failed, nothing finite) says why in the lane (`ov-lane-note-<name>`).
- `CrossChannelPage.tsx`:
  - `╌ detections` legend in the overlay head (`ov-det-legend`);
  - the stacked row's "flat at this gain" note (`xrow-flat-<name>`, `data-px`).
- `explore.css`: the two new labels. The overlay axis frame label moves under the ticks; it collided with the
  last tick ("s from onse+80 s").

**Checked after the fix on real data** (screenshots in the worktree's `webui/runtime/site/`):

| Recording | Channels | Result |
|---|---|---|
| CO_fs2 (641) | 4 | CH2 ÷143 |
| MJu26a (584) | 16 | CH13 ÷55 |
| M2_aug_concat_fs1 (1) | 16 | no own-scale rows |
| L_R_Aug_26_PD_raw (679) | 13 | no own-scale rows |
| SH (666) | 4 | no own-scale rows |

No console errors and no lane notes on any of them. Stacked on CO: the three flat rows say so.

**Tests:** `tests/test_webui_site_x_cross.py` (conda python), 10 tests: gains, merge, legend and source pins, the
stacked flat note, the default view, and the smoke manifests.

## Item 3 — the Analyse lag

### What I measured

**Main-checkout sandbox (port 8769, real database copy).** Timed from the click to the chain source chip:

| Case | Result |
|---|---|
| Signal (M2_aug CH4_A2) › Open in Analyse, warm | every read ≤ 0.2 s |
| Same, cold (20 s after start) | ≤ 0.1 s after the click |
| Same, drop or spike_event_features chain seeded | same |
| Whole-recording span (2.6 M samples) | same |
| Cross-channel (CO CH1) › Open in Analyse, then Run | run 4.4 s |
| Discovery › Runs open first | same |

- A stale `lastRunJobId` changed nothing.
- `/api/runtime` pings never passed 0.33 s.
- Validate on L_LM_Jul_26_J_raw, MJu26a_fs10 and CO with whole spans took 0.06 s.
- The heaviest Signal-page reads during the start-up warm: `/api/review/counts` 18.7 s and the whole-channel
  `/spans` 9 s, both in the first minute only.
- `corpus.warm_coverage` plus template scores take 132–142 s after a start. Route timings during that warm,
  sampled every 5 s: review/counts 0.5–3.5 s, everything else ≤ 2 s.

**Reproduced.** A chain with an uncalibrated `Working.block_cost` model.
`webui/server/chain.py::_ensure_block_calibration` timed it on a bridge thread, and
`route_local` waited `CALIBRATION_WAIT_S` = 10 s on every validate. The page re-validates every 3 s while a step
reads "calibrating" (`analyse/useValidation.ts:20-26`). Validating detrend → rupture:

| Measure | Before (main code) | After (this branch) |
|---|---|---|
| Each validate | 10.0 s (14 in a row) | 10.1 s once, then 0.01–0.06 s |
| `/api/review/counts` | 2.5–7.3 s | 0.7–2.0 s (idle 1.0–1.5 s) |

- Quick models (invert, event_shape, intervals) still land inside the first validate: 2.8 s.
- trains + cycle_shapes: 9.0 s, against 7.9 s on the thread.
- Uncalibrated in the real `DATA/db/block_calibration.json`: rupture, trains, cycle_shapes, snippets,
  cnn_score, cnn_window_scores, window_images, wavelet_scattering, wavelet_transform.

### The fix (bridge only)

- `chain._calibrate_block_cost` times the model in a spawned process (`_calibrate_in_process`). The child runs
  `webui/server/calibrate_child.py`, which imports only `Working.block_cost` and the one adapter module that
  registered the model; the child starts in about 1.4 s.
  - The child watches the bridge (`coverage_map.watch_parent`) and is terminated at interpreter exit
    (`_stop_block_calibrations`). I checked: stopping the bridge left no child behind.
  - A stand-in `calibrate` (the tests' fakes) runs on the thread as before. `CALIBRATION_WORKER = "thread"`
    turns the process off.
- `route_local` waits only for timings it starts. A re-validate that finds one already running answers
  "calibrating" at once.

**How the child hands its timing back.** The child writes no database row, no cache and not the shared file. It
times into a scratch file of its own (deleted afterwards) and returns `(pid, key, entry)`. The bridge merges that
entry into the shared `block_calibration.json` under `block_cost._FILE_LOCK`, the same read-merge-write and atomic
`os.replace` that `calibrate` does. So only the bridge process ever replaces the file every validate reads, and two
children timing two models cannot drop each other's entry. Key and entry fields are unchanged.

Tests:

| File | Interpreter | Result |
|---|---|---|
| `tests/test_webui_site_x_calibration.py` (5 tests) | conda | 5 passed |
| same, plus `tests/test_webui_run_routing.py` | `webui/.venv` | 27 passed |

The 5 tests pin: timed in another pid; a stand-in stays on the thread; a failure says why; a re-validate does not
wait; the bridge alone writes the shared file.

### Other candidate, reported, not fixed

`webui/server/corpus.py` (`_drain` → `run_in_worker`, about lines 718–800): any write to M2_aug (a run, a verdict,
an annotation) makes the next corpus read recompute M2_aug's whole map in the worker process. The researcher's
bridge log shows **179.9 s** at 13:30 and **179.8 s** at 14:49 today, against 79 s at its start. On my sandbox a
134 s recompute only doubled review/counts (0.7 → 1.4 s). On a box with about 1 GB free RAM, a 16-channel
recompute in a second process may page hard. Fixing that is outside this brief: incremental per-channel maps, or
deferring the recompute while pages are active.

## Smoke states

New unit `webui/smoke_pages/zzzzzzzzzzz_site_x.json`:

| State | What it should show |
|---|---|
| `site-x-overlay-is-default` (`explore/cross-channel/4`) | The overlay, `ov-trace-*`, the view switch and the detections legend; no `reference-trace` or `y-select`. |
| `site-x-stacked-on-request` (`?view=stacked`) | The stacked rows, `y-select` and `align-seg`; no overlay. |
| `site-x-co-own-scale` (`explore/cross-channel/641?detrend=linear&view=overlay`, real DB) | 4 channels; `ov-own-scale-CH2` (factor over 100); `ov-detection` brackets and legend; CH1 not own-scale; no lane notes; `traces_in_box`. |
| `site-x-co-stacked-flat-says-so` (641, stacked, 4 channels, real DB) | `xrow-flat-CH1/CH3/CH4` present; CH2 absent. |

Gate units: `explore`, `zzz_w_cross_channel`, `zzzzzzzzzzz_aq_cross_channel`, `zzzzzzzzzzz_overlay`,
`zzzzzzzzzzz_explore_review`, `zzzzzzzzzzz_polish`, `zzzzzzzzzzz_site_x`, plus `analyse` and `zz_analyse_run`
for item 3. The calibration now starts about 1.4 s later than on a thread; a state that needed a quick model
calibrated inside its first validate still has 10 s.

## Gates run

- `tsc -b` and `vite build` pass, from the worktree.
- conda python:
  - `tests/test_webui_site_x_cross.py`, `test_webui_cross_page.py`, `test_webui_night_b_links.py`,
    `test_import_boundaries.py`: 43 passed;
  - `tests/test_webui_site_x_calibration.py` plus `test_import_boundaries.py`: 9 passed.
- `webui/.venv`:
  - `tests/test_webui_cross_channel.py`, `test_webui_cross_window.py`, `test_webui_cross_page.py`: 37 passed;
  - `tests/test_webui_site_x_calibration.py` plus `test_webui_run_routing.py`: 27 passed.

## Runtime folders for the manager to delete

Main checkout `webui/runtime/`: `20261020-143548`, `20261020-145245`, `20261020-145719`. These are three starts of
the main-checkout sandbox bridge; each was stopped. My worktree's own DB copy and runtime folders are already
deleted.

## Fix round (the critic, 2026-10-20: "merge after fixes", one blocker)

Red: 7fae1ae (7 failed, 16 passed, conda). Fixes: c77a20c (F1), d14d4c2 (F2 + F6), 8dd1f2b (F3 + F4 + F5).

- **F1 (blocker): cold timing.**
  - The problem: a fresh child paid the model's lazy imports and numba compile inside the one timed call, and the
    inflated k was kept in the calibration file permanently.
  - The fix: `calibrate_child.calibrate_in_child` runs the model untimed first (its `WARM_UPS` entry if it has
    one, then one call on a 1000-sample synthetic series).
  - Result for `interrogation.trains`: child k 5.1e-7 against a warm in-process 5.06e-7, in the same test run (it
    was 3.57e-4). `detection.deconvolve` in the child gives 1.31e-5; the real database holds 2.14e-5.
  - Test: `test_f1_the_child_times_a_warm_model_not_its_first_cold_call`, which requires the child's k to be
    within 5× of the warm one.
- **F2: timeout.**
  - `fut.result(timeout=CALIBRATION_TIMEOUT_S)`, set to 900 s.
  - On timeout the pool is terminated, and the model reads "failed", with the message "timing <name> timed out
    after N s; the child was stopped". The next try comes after `CALIBRATION_RETRY_S`.
  - Test: a stand-in child that sleeps 120 s, with a 3 s timeout.
- **F6: one child at a time.**
  - `_BC_PROCESS_SLOT` is a semaphore of one, taken on the calibration's own thread. A queued model reads
    "calibrating".
  - The request that starts a timing only joins that thread with the `CALIBRATION_WAIT_S` deadline. The submit,
    including the wait on `corpus._POOL_LOCK`, is never on a request thread.
  - Tests: the peak number of live calibration children is 1 with two models started together; and with
    `_POOL_LOCK` held, `route_local` answers in under 2 s (a guard: this already held).
  - `_child_call` is the seam the tests use for a stand-in child.
- **F3: lower median and flat lanes.**
  - `overlayGains` takes the shared gain from the lower median. [0.2, 35] and [0.2, 0.3, 30, 35] now draw every
    narrow channel at full height, and only the wide ones at their own gain.
  - Each lane carries `px` and `flat`. A lane under `FLAT_PX` prints "flat at this gain …"
    (`ov-lane-flat-<name>`).
- **F4: help text.** The overlay InfoTip and `Overlay.tsx`'s header now say one shared gain, except a channel too
  wide for the block, which is drawn at its own gain and marked ÷N. They also name the flat note and the dashed
  detection brackets.
- **F5: no ÷1.0.** The shared gain is capped at 0.9 of the block, so a single channel fits it. `ownScale` is set
  only when there is more than one channel and the factor is over 1.

Gates after the fix round:

| Check | Interpreter | Result |
|---|---|---|
| `test_webui_site_x_calibration`, `test_webui_site_x_cross`, `test_webui_cross_page`, `test_import_boundaries` | conda | 48 passed |
| `test_webui_site_x_calibration`, `test_webui_run_routing`, `test_webui_cross_channel`, `test_webui_cross_page` | `webui/.venv` | 61 passed |
| `tsc -b`, `vite build` | — | pass |

No bridge was started in this round. On CO the lower median changes the gain from CH4's 0.244 mV to CH3's 0.19 mV.
CH2 is still drawn at its own gain, so the `site-x-co-own-scale` smoke state still holds. The critic's runtime folder
`webui/runtime/20261020-182838/` in my worktree is deleted.

## Gate round (merged main d3ce03c into the branch first: 3a4d5c8)

Red: 21cfb3b. Fixes: b700907 (G1), 0d483fb (G2).

- **G1: `zz_analyse_run › fixup-j-dehshibi-funnel`, a 409 on the first Run.**
  - The dehshibi_spikes template's `preprocessing.wavelet_transform` is uncalibrated in the real
    `block_calibration.json`. The validate after *use example* started its timing in a child process. The Run click
    found that timing running and, since 0d0fd84, did not wait for it, so the run answered 409.
  - Fix: `route_local(wait_s=…)` waits for every timing the chain needs, whether this request started it or it is
    already in flight. `POST /api/runs` passes `RUN_CALIBRATION_WAIT_S`, a new constant of 60 s.
  - A validate is unchanged. A slow model (rupture, about 447 s) still answers 409 in words after the 60 s.
  - The client already says so in words on a 409: a refusal card and a toast ("run refused · calibrating: …").
    While a validate reads calibrating, the Run button is disabled with that reason in its title. It does not
    retry by itself, and with the 60 s wait it rarely needs to.
  - Test: a stand-in child that holds 12 s (`calibrate_in_child(hold_s=…)`) is routed `local` with no
    "calibrating".
  - Deliberate behaviour change: `test_webui_run_routing`'s 409 test now shortens `RUN_CALIBRATION_WAIT_S` too.
- **G2: `site-x-co-own-scale`, a trace 46 px out of the plot box.**
  - After F3's lower median, CO CH4 fits the block at the shared gain. But centred on the bottom lane, it ran 46 px
    below the block. Smoke measures path geometry, which a clipPath does not change.
  - Fix: `overlayModel.ts::fitCentre` nudges that lane's drawing origin toward the middle, just enough that its
    whole extent stays in the block. The gain is unchanged and the name stays on its lane. The help text now says
    this instead of "clipped".
  - Model test: every shared-gain and own-gain lane on CO-like extents stays inside [0, block], and a lane that
    fits keeps its centre.

Gates:

| Check | Interpreter | Result |
|---|---|---|
| `site_x_calibration`, `site_x_cross`, `cross_page`, `import_boundaries` | conda | 51 passed |
| `site_x_calibration`, `run_routing`, `site_x_cross`, `cross_page` | `webui/.venv` | 69 passed |
| `tsc -b`, `vite build` | — | pass |

No bridge was started.
