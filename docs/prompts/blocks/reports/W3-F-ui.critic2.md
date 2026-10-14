> Filed by the manager session, 2026-10-15 — the final message of critic agent `ad9069dfbd66c843e`, resumed to
> re-critique W3-F's fix round 1 (`f42dd35..ea59ee6`, changed parts only; stopped once by the API session limit and
> resumed at 07:02), verbatim.

## W3-F fix round 1: re-critique (`f42dd35..ea59ee6`; red `ff5bc21`, green `ea59ee6`)

### In plain words
The blocker is fixed. Stopping a run while its noise comparison (the "null") is being drawn no longer turns those noise runs into real detections. I re-ran it through the real bridge code: the real count stayed exactly the real run's own, and the half-finished noise run is now tagged as noise.

One loose end is left, and the fixer named it. Three other pages still count a half-finished noise run as a full one: the Discovery scoreboard, the motif read-out and the family null. It is like averaging in a half-marked exam paper, which drags the noise average down. On the same run, the Analyse toolbar now says "2 draws, the null expects 34.5" while the scoreboard says "3 draws, 30.33". Everything else asked for is done and works.

### Verdict
**merge after fixes.** Three should-fix items, all small, and none is a leak into real detections:
1. One shared "completed null draws" rule used by every reader of null runs (finding 1).
2. A noise run that *fails* mid-chain still leaks, like the cancel did before (finding 2).
3. Rename the pan view's "suggested" to "strongest — not an event length" (finding 3).

### Findings, most severe first

**1. should-fix: three null readers still count a half-finished draw. Analyse and Discovery now disagree on the same run.**
- **Evidence:** through `RunManager` (the real path), on 200 k samples (AR(1) 0.98 with drops). Chain: detrend → noise_threshold (k 3) → cycle_shapes (`null_draws` 300), null of 3 draws, cancelled 2 s into draw 3.
- **Rows in `runs`:**

  | Run | Role | Status | Detections | Note |
  |---|---|---|---|---|
  | 1 | real | completed | 82 | |
  | 2 | null | completed | 13 | linked to run 1 |
  | 3 | null | completed | 56 | linked to run 1 |
  | 4 | null, half-finished | failed | 22 | linked to run 1; error text "Cancelled: Cycle shapes cancelled." |

- **The readers' numbers:**

  | Reader | Draws | Null expects | ×null |
  |---|---|---|---|
  | `null_summary` (fixed) | 2 | 34.5 | 2.38 |
  | `scoreboard.channel_score` via `_null_runs` | **3** | **30.33** | **2.70** |
  | `matching.py:1309` / `library.py:1709` pattern (every linked row) | 3 | 91 null dets, perDraw **30.3** | |
  | same, completed only | 2 | 69 null dets, perDraw 34.5 | |

  A half-finished draw usually holds *fewer* spans than a whole one, so the null comes out low and "beats noise" is overstated.
- **Is "completed only" right in `null_summary`?** Yes. A cancelled draw ran part of the chain, so it is not a draw of the null.
- **Fix:** one shared helper beside `dbq.not_surrogate`, e.g. `null_draw(alias)` meaning `alias.surrogate_of_run_id IS NOT NULL AND alias.status = 'completed'`, or `completed_null_runs(conn, run_ids)`. Use it in:
  - `scoreboard._null_runs` (`Working/discovery/scoreboard.py:144`)
  - `matching.py:1309` (the `nulls` query: draws, `nullCount`, `nullPerDraw`)
  - `library.py:1709` (`_family_null`: draws, `drawsTotal`, `perDraw`)
  - `run_groups.null_summary` (switch to the helper)
  - `Working/export.py:68` (`_surrogate_block` takes the first linked row with `LIMIT 1`, so the export can name the half-finished one as "the surrogate control"; it should prefer completed)
- **Other readers of `surrogate_of_run_id` are fine:**
  - `runs.py:124` (rename propagation): a cancelled draw should follow the rename;
  - `runs.py:437`: keeping surrogate spans out of the Library is now *stronger*;
  - `corpus.py:198`, `fanout.py:335/352`, `scoreboard.py:464`: these only separate real from null.

**2. should-fix (existed before this branch, same family as the blocker): a draw that *fails* mid-chain still leaks its detections as real.** `draw_paired_null` (`Working/run_groups.py:338-352`) catches only `RecipeCancelled`. A `RecipeExecutionError` raised in a later step of a draw (a block refusing surrogate data, say) propagates with the draw's row unlinked. Any spans its detector step already wrote then count under `not_surrogate()`.
- **Evidence:** read from the code; `execution.py` puts `run_id=…` in the message but sets no attribute.
- **Fix:** set `e.run_id = run_id` on the `RecipeExecutionError` path too. In `draw_paired_null`, catch it, link the row, and re-raise (or record the failure and stop).

**3. should-fix (wording): the pan view still sells the suggestion.** It does lead with the band ("clears from A to B s", `row-verdict-band`, bold). But:
- the headline goes on "· suggested C (strongest of the band)";
- the table cell says "· suggested";
- the "not the event's length" caveat is only an amber line under it.

There is no "use this window" button anywhere (grepped). The W3-C critic's request reads better as "strongest at C s — not an event length", with "suggested" dropped. That also matches W3-C's next round, which removes "suggested" from its own summary.

**4. nit: the caveat is a copy, not read from the block.** `serialize.SUGGESTION_CAVEAT` duplicates W3-C's caveat, so it will drift if W3-C rewords it. Read `meta`'s own caveat when the block sends one, and fall back to the constant.

### The six checks

**1. The blocker: fixed on every path that draws null runs.**
- **How:** `execution.py` attaches `run_id` to the re-raised `RecipeCancelled`, and `draw_paired_null` links that row before stopping.
- **Paths:** every null run is made by `draw_paired_null`, whether called directly, from the run manager (`runs.py::_draw_null`), or from Discovery (`fanout.start` → `run_paired_recipe` → `draw_paired_null`). Seed search makes no null *runs*: `seeded_search.null_distances` returns distances.
- **Bridge re-run:** real detections counted under `not_surrogate` = **82 = the real run's own**. In round 0 it was 95 against 82.
- **Status of the half-finished run:** `failed`, error text "Cancelled: …", `surrogate_of_run_id` set.

**2. The three readers:** measured above (finding 1). Fix with one shared completed-only helper; `export.py` has the same hole.

**3. Cancel text: fixed.** `execution.py` stores `text if text.startswith("Cancelled") else f"Cancelled: {text}"`, and `app.py:373`'s `startswith("Cancelled")` now flags it. Observed: "Cancelled: Cycle shapes cancelled."
- That function is the only place a cancel gets written to `runs`. The other cancel exceptions are `BuildCancelled` (the training paths' `features_at`) and `GroupingCancelled` (Library). Neither runs inside `execute_recipe`, so no recipe-run cancel reads as failed.
- Cosmetic: "Cancelled: Cycle shapes cancelled." says it twice.

**4. 409 while calibrating: fixed.**
- **Where:** `app.py` raises 409 after `route_local` and before `manager.start`. The Analyse chain page and the block page both POST `/api/runs` (`api.ts:162`), so both are covered. Null draws ride the same request, since the route counts draws.
- **Nothing half-made:** no job, no run row (only `execute_recipe` writes one), no lock taken.
- **Not costed by `block_cost` at all:** Discovery sweeps and seed search do not use `route_local`, so the 409 does not apply there. That was true before W3-F and is outside this branch.
- **Per-model calibration (my experiment):**
  - a fast model waited **0.02 s** behind a 4 s one (round 0: 3.8 s);
  - **12 models finishing at once** (a barrier) plus the slow, fast and duplicate ones: all **15 of 15** keys stored, so the merge under `_FILE_LOCK` loses nothing;
  - 5 concurrent asks for one model: timed **once**. Two threads time the same model only after `reset_block_calibration()`, which only tests call.

**5. The cancel smoke state, from the code: viable.**
- **Span and windows:** 13 zoom-outs give 2 h × 1.5¹³ ≈ 389 h, or the whole recording if `clampView` stops it sooner. With 3 h windows that is about 130 windows.
- **Timing:** the first `step_progress` is sent immediately, then at most one every 0.25 s, the last always. So `step-fraction-3` is on screen for the whole step, about 15 s, and the cancel lands within one window (about 0.1 s).
- **Real M2_aug at 1 Hz:** similar or slightly faster. MSE's cost is template pairs per window, which does not depend on the data. Windows with long NaN gaps are skipped, which only shortens the step. Even a whole recording (more windows) stays well inside the smoke timeouts and far under the Analyse limit.
- **Leftover risks:**
  - an earlier w3-mse state failing would leave MSE uncalibrated, but the 60 s `run-button:not([disabled])` wait covers about 2 s of calibration;
  - the view remembered from `w2-snippets` (`explore.view`) only makes the span longer.

**6. The pan view, against `617edc2`'s payload:**
- **Band first:** yes (`row-verdict-band`). "No window length stands out" when the band is empty.
- **No "use this window":** correct, none anywhere.
- **Every reason labelled:** each row prints the block's own `reason` text and "gap · cut". `cut` and `gap` are null for `too_long`, `no_null`, `too_few_windows` and `no_spread`, so those show "—".

  | `reason_code` | Example reason text | gap · cut |
  |---|---|---|
  | `clears` | "gap X >= cut and better than every draw" | e.g. 9.1 · 6.4, marked clears |
  | `below_cut` | "gap X < cut" | both numbers |
  | `not_every_draw` | "not better than every null draw" | gap ≥ cut, marked no |
  | `too_long` | "too long to judge … fewer than N windows" | — |
  | `no_null` | "no null draws" | — |
  | `too_few_windows` | "too few scorable windows" | — |
  | `no_spread` | "no spread to measure" | — |

  `reason_code` and `reasons` are shipped but not drawn, so a new code (W3-C's stalls) still reads correctly.
- **If W3-C's summary text changes:** nothing breaks.
  - The view never parses `summary` or `verdict`; the headline is built from `cleared_s` and `suggested_window_s`.
  - The payload tests use their own fixture meta (`test_webui_w3f_payloads.py:171-194`).
  - The smoke selectors are testids only.
  - The one dependency is `suggested_window_s` / `suggested_row`: if W3-C drops those fields, the "suggested" text and highlight just disappear (null-safe).

### What I ran
- **Venv** (`webui/.venv`), `-n 4`: run_cancel, run_routing, w3f_payloads, w3f_ui, webui_runtime, block_views: **122 passed**. My `ls tests | grep -i pan` matched nothing, so no pan test files were in either run.
- **Conda**, `-n 4`: run_groups, surrogate_never_a_detection, execution, discovery_fanout, import_boundaries, plus whatever matched `scoreboard`: **124 passed, 7 skipped**.
- **Client:** `npx tsc -b` exit 0 and `npm run build` exit 0, in a scratch copy with a junction to `node_modules`. The junction was removed with `cmd /c rmdir` first; the main `node_modules` is intact.
- **Experiments** (scratch `critic_w3f\`):
  - `cancel_real.py fix1`: the bridge-path cancel during draw 3 and the readers' numbers;
  - `calib2.py`: per-model locks, the 12-way simultaneous merge, the duplicate ask.
- No bridge was started, and nothing in the repo, the worktree or the real `DATA/` was written or read.
