# W3-F — Wave 3's UI: stop and follow a long step, cost every costed block before it runs, and draw what wave 3 found

Read [`00-common.md`](00-common.md) first — **this prompt hands you the files its "Deliver" list names** (the exception in
`00-common.md`'s "Do NOT touch"). Commit prefix **`w3-f:`**. **Round 2 of wave 3:** you start from a `main` holding
W3-A, W3-B and W3-C (and W3-D, MPdist, if it merged first — check `git log`; W3-E is not run). Read their reports in
`docs/prompts/blocks/reports/W3-*.md`: each one's "Integration snippets" are your input. Read `CLAUDE.md`'s "Web UI"
section and `docs/BLOCK_INTEGRATION.md` §2 (the drawing standard: payload-driven, never name-driven) and §3 (cost).

## In plain words

Two pieces of friction first, then three pictures. **A long step cannot be stopped:** the bridge checks *cancel*
between steps only, so on 2026-10-14 a FLUSS run over a whole recording had to be ended by killing the bridge. And **a
block whose cost model was never calibrated runs blind:** the bridge's routing calibrates the matrix-profile model on
first need but no other, so an uncalibrated MSE, snippets or MiniRocket step is routed "unknown" and starts, whatever
its size. Then the pictures: multiscale entropy's answer is a **curve**, cycle shapes' answer is a **stack of cycles**,
and the pan matrix profile's rows are **window lengths** that need labels. This is polish on working blocks under the
21 October priority (`CLAUDE.md`): **friction first, then legibility**.

## What to build

1. **Cancel and progress inside a step.** `webui/server/runs.py` calls `execute_recipe(…, on_progress=…,
   should_cancel=…)` and, for the null, `run_paired_recipe(…)`, but passes no `run_kwargs` — so a block that declares
   `should_cancel` / `on_progress` on its `_run` (`preprocessing.window_matrix`; now `catalogue.multiscale_entropy` and
   `detection.pan_matrix_profile`) never receives them (`Working/execution.py` forwards `run_kwargs` only to a `run` that
   declares them). Forward both, for the real run and the null draws (`_draw_null`). The job's status gains the in-step
   fraction, and the run panel shows it beside the step's name — real progress, never a simulated bar (the
   researcher's standing request). A step cancelled from inside ends the job as **cancelled**, not failed, and leaves no
   step-cache entry for that step. Settle one cancellation exception (read `Working.execution.RecipeCancelled` and
   window matrix's own in `Working/Preprocessing/window_matrix/build.py`) and check W3-A and W3-C raise it.
2. **Every costed block is calibrated before it is routed.** `webui/server/chain.py::route_local` calibrates the
   matrix-profile model on first need (`_calibrate_matrix_profile`, `_uses_mp_cost`) — extend it to `Working.block_cost`
   models (`calibrate([name])`, per model, recorded in the route's `calibration`). **Measure** each costed model's
   calibration time first (MiniRocket's took 61.5 s with its warm-up): if any would hold a `POST /api/chain/validate` for
   more than ~10 s, calibrate in the background at bridge start instead, and let the estimate say "calibrating" until it
   lands — your call, stated with the numbers. Extend `tests/test_webui_run_routing.py` (its fake-calibration fixture
   shows the pattern). **Skip this item if the manager's preflight found it done**, and say so.
3. **MSE curves.** On the Multiscale entropy block page: entropy against scale (log x) from `meta["curves"]`, one line
   per sampled window, the median bold, undefined scales left as gaps (never joined across — drawing rule 1), scales
   the collapse guard flagged marked. Wire it the way `DetectorFunnel` is wired in `analyse/views/registry.tsx`
   (`funnelOf(meta)` → a component): read off the payload, never the block's name. A grey band for the null's curves
   only if the null draws' outputs are reachable cheaply from the page (today the paired null is a count, `nullText` in
   `analyse/toolbar.tsx`) — otherwise skip it and say what it would need.
4. **The cycle stack.** On the Cycle shapes block page: `meta["cycle_stack"]` as two heat-maps, before and after
   alignment, one row per cycle in time order, a group-colour strip beside them and the change points marked; under
   them each group's medoid cycle (`exemplar_events`) as a member, in small multiples with per-panel domains and scale
   bars (drawing rule 4).
5. **Pan matrix profile rows.** The Encoding view labels the rows from `meta["lengths_s"]`. First check what the view
   does with the wavelet transform's `meta["freqs_hz"]`; use **one** convention for both (if it is new, add its row to
   `docs/BLOCK_INTEGRATION.md` §2's conventions table — that one row is handed to you). Show `suggested_window_s` with
   its rule on the face, or "no length stands out".
6. **(Optional, last) the scalogram with ridges** for `detection.cwt_ridges` (plan §7.1, "an optional
   scalogram-with-ridges drawing"). If its `meta` holds no scalogram, add a decimated one (at most 4096 columns × its
   scales) and its ridge lines to `meta` in `Adapters/detection_cwt_ridges.py` — meta only: no parameter, so no recipe
   hash moves — and draw them on its block page. Skip it if time is short, and say so.
7. **Glyphs** in `analyse/glyphs.tsx` `BY_NAME` for every wave-3 block, from the reports' sketches.
8. **Smoke states** in `webui/smoke_pages/zz_analyse_run.json`, one per wave-3 template that runs in seconds on the
   sandbox (short spans; read the w1/w2 states). The first MSE or pan run in a bridge process pays a numba compile —
   measure it from W3-A/C's reports and set the state's timeout to fit. One state that starts a long pan run, cancels it
   mid-step and expects the job to read *cancelled*.
9. **MPdist** (only if W3-D merged): whatever its report says the Family page's per-distance read-out still needs
   beyond the label it added.
10. `webui/client/src/api.ts` types for anything new the server sends.

## Gate (yours)

`npx tsc -b` and `npm run build` in `webui/client` (if your worktree has no `node_modules`, **do not** `npm install` —
report it; the manager builds in the main checkout). The Python tests you touched plus `tests/test_webui_block_views.py
tests/test_block_standard.py tests/test_webui_run_routing.py`. Tests that import FastAPI skip under the conda python:
run them with the main checkout's interpreter, `"/c/Users/mmebr/Documents/CNN/webui/.venv/Scripts/python.exe" -m pytest
<files> -q -p no:cacheprovider`, **from your worktree root** (the interpreter only — the tests read your worktree's
files and write only to temp directories). You cannot run smoke (no database in a worktree): write the states and say
exactly what each should show; the manager runs smoke on a sandbox bridge after merging.

## Deliver

`webui/server/runs.py`, `webui/server/chain.py`, `webui/server/serialize.py` (only if a payload needs a branch),
`webui/client/src/analyse/views/registry.tsx` and new components beside `DetectorFunnel.tsx` for items 3–4, the Encoding
view's component (item 5), `webui/client/src/analyse/glyphs.tsx`, the run panel's progress line (item 1),
`webui/client/src/api.ts`, `webui/smoke_pages/zz_analyse_run.json`, one row of `docs/BLOCK_INTEGRATION.md` §2 (item 5,
only if new), `Adapters/detection_cwt_ridges.py` (meta only, item 6), the Family page component (item 9, only if
needed), and their tests. Nothing else under `webui/`.

## Acceptance

- [ ] A fake slow adapter that declares `should_cancel` stops within one iteration of a cancel; the job reads
      *cancelled*; no step-cache entry is written for that step; null draws stop too.
- [ ] `on_progress` from inside a step reaches the job's status and the run panel.
- [ ] An uncalibrated `block_cost` step is calibrated (or reported "calibrating") before routing, and an over-limit
      chain with such a step is refused with a SLURM script, as an over-limit FLUSS run is.
- [ ] The three drawings render from their payloads; undefined MSE scales are gaps; pan rows carry their lengths.
- [ ] Every wave-3 block resolves to a view and a modifier (`tests/test_block_standard.py`) and has a glyph.
- [ ] `tsc -b` and `npm run build` clean; the Python tests green.
