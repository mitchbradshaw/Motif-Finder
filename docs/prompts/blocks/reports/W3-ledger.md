# Wave 3 — the manager's ledger

Kept by the managing session "Wave 3 analysis blocks manager" (main checkout `C:\Users\mmebr\Documents\CNN`, branch
`main`) under [`../W3-manager.md`](../W3-manager.md). One row per agent; updated after every event. A resumed session
reads this file and carries on: an interrupted implementer is resumed with `SendMessage` to its id if the id is alive,
else relaunched **in its existing worktree** (told to read `git log` there and continue).

Sub-agents: `general-purpose`, `model: opus`, `effort: medium` (memory `subagent-model-policy`). Implementers and
fixers in `isolation: worktree`; critics read the implementer's worktree and never edit it. Times are from `date`.

**Round 1 base commit:** the commit that adds this ledger on top of `b2ba60e` (named in the launch messages).

## Agents

| # | Role | Block | Agent id | Worktree | Branch | Base | Status |
|---|---|---|---|---|---|---|---|
| 1 | implementer | W3-A `catalogue.multiscale_entropy` | `a67442d9e04015d6a` | `.claude/worktrees/agent-a67442d9e04015d6a` | `worktree-agent-a67442d9e04015d6a` | `01cb8c3` | launched 21:26; reported 22:00 (`99b043f`, 33 min) → `W3-A-multiscale-entropy.md` |
| 5 | critic | W3-A | `a03f242747d328696` | (reads row 1's worktree) | — | `01cb8c3` | launched 22:01, seven manager questions |
| 2 | implementer | W3-B `interrogation.cycle_shapes` + `Working/background_null.py` | `a7834e530174e1643` | `.claude/worktrees/agent-a7834e530174e1643` | `worktree-agent-a7834e530174e1643` | `01cb8c3` | launched 21:26 (worktree at `01cb8c3`, clean, 21:26) |
| 3 | implementer | W3-C `detection.pan_matrix_profile` | `aeeb2080e0967a2d2` | `.claude/worktrees/agent-aeeb2080e0967a2d2` | `worktree-agent-aeeb2080e0967a2d2` | `01cb8c3` | launched 21:26 (worktree at `01cb8c3`, clean, 21:26) |
| 4 | implementer | W3-D `mpdist` (fourth Library distance) | `a5a78efe8b36c0a92` | `.claude/worktrees/agent-a5a78efe8b36c0a92` | `worktree-agent-a5a78efe8b36c0a92` | `64db0da` | launched 21:30, early (decision 4; cut at `3cc2f62`, at `64db0da` by 21:31); reported 22:39 (`c88a236`, 68 min) → `W3-D-mpdist.md` |
| 6 | critic | W3-D | `a380d497100469282` | (reads row 4's worktree) | — | `64db0da` | launched 22:42, seven manager questions |

## Preflight (2026-10-14 21:2x)

1. **New commits on `main` since `1019cf6`:** `0a6dab8` (wave-3 prompts adjusted), `8324d3d`, `ffecacf`, `a5bdeea`,
   `b2ba60e` (the wave-2 manager's decisions, re-test, g-05 comparison and ledger). **All docs only**: none touches a
   file a wave-3 prompt names, so no launch message carries a code change.
2. **Gate baseline.**
   - pytest: the drop-NaN session's gate on `1019cf6`, **3529 passed, 0 failed** — the failure set is empty. Only docs
     changed since.
   - Smoke: `W2-evaluation.md`'s full walk, **25 failures** (12 Discovery, 3 Review inspector, 5 Settings, explore
     corpus + max-lag-10, two that pass alone, one "database is locked" traceback in the sandbox copy). No later smoke
     run is recorded. The committed `webui/screenshots/smoke-result.json` lists 3 (Discovery), all inside those 25.
3. **The researcher's wave-2 answers** (`W2-evaluation.md`, "Decided by the researcher", 2026-10-14 evening):
   - Q1 (b): the `event_families` re-test was declared and run on fresh rec 543 / rec 2 (`ffecacf`) — no family on
     either; it stays experimental. **Nothing for wave 3; not re-run.** (W3-G's closing line and this brief's "Read
     first" call it "not chosen" — stale; it was chosen and is done.)
   - Q2 (a) now, (b) later: snippets' chooser — not wave 3.
   - Q3 (a) then (b): g-05 compared (`a5bdeea`): the waveforms moved about 3 % after the re-derivation, and Ward at
     cut 0.6 is fragile (a 1 % wobble → ARI 0.78–0.80). The fresh Ward save into the real database waits until wave 3
     merges (the wave-2 manager's). Passed to W3-G for its family judgements.
   - **Q4 (b): σ² leads wherever a family's coherence is shown, eq. 17 beside it; the beyond-noise verdict stays on
     eq. 17 until it is re-measured on σ².** `svd_entropy`'s code default is still `squared=False`. Changes W3-B
     (σ² first, explicitly — the prompt's "follows the default / open choice" is stale) and W3-G (its item 2 "do not
     change which variant heads the page" is stale). The wave-2 manager deferred the Library side of it (Family page,
     families table, `shape_families` summary lines) to wave 3: decision 3.
   - Q5 (a): the fairer noise test = W3-G.
   - Q6 (a): MiniRocket in Models › Launch — a separate small ticket, not wave 3.
4. **Peers** (`ListAgents`, 21:23):
   - "Agent manager setup" (the wave-2 manager): wave 2 closed; docs-only commits `a5bdeea`, `b2ba60e`; no pytest /
     smoke / bridge planned (port 8791 if ever); holds its RQ1/RQ3 log lines until wave 3 merges.
   - "Show block readouts on the block page": worktree `.claude/worktrees/peaceful-tesla-abc225`; new
     `webui/server/readout.py`, `analyse_routes.py` (derive route), **`api.ts` (small: `has_derive`, `getReadout`) —
     its one overlap with W3-F**, `BlockPage.tsx`, new `Readout.tsx`, `analyse.css`, a new smoke page,
     `BLOCK_INTEGRATION.md` (the `derive` row). Port 8797 with a private dist; never rebuilds the shared dist; merges
     before W3-F and says so. A block's `derive` will then receive the run's typed kwargs (`value`, side inputs).
   - "Time-series detection algorithms for mycelium analysis" (wave 1, the prompts' author): idle, no plans; sent the
     four stale-line corrections above and one hazard: until W3-F lands, `catalogue.multiscale_entropy` (a
     `block_cost` model) routes "unknown" on a bridge and cannot be cancelled mid-step — keep the evaluation headless
     and tell the researcher not to run long MSE spans on 8765 until then. No `W1-retest-known-spans.md` is coming:
     W3-B's table is the record (raw files in that session's scratchpad: `trains_known.json`,
     `fluss_known_w300.json`, `detectors_known.json`).
   - Protocol agreed with all three: message before any `pytest -n`, smoke or shared-dist rebuild; one at a time.
     **Mine: port 8794.** 8765 is the researcher's `--project` bridge — never touched.
5. **Prompts committed** (`0a6dab8`). Round 1's base is this ledger's commit.
6. **Keep-awake:** the host's `request_keep_awake` (`session_idle`) is held; because that hold lapses after ~5 min of
   session idleness — exactly while agents run in the background — a background process also holds a
   system-required execution state (`SetThreadExecutionState`, scratchpad `keep_awake.ps1`, 16 h, changes no
   setting, released when stopped).

## The evaluation's statistics, declared before any data are seen (21:4x)

The brief's table fixes each template's statistic. Where it leaves a detail open, it is fixed here, now, before any
real recording has been run through a wave-3 block (wave 2's decision 22: a statistic chosen after seeing it pass is
how a test fools itself). A different reading that looks better later is reported **beside** the verdict, never
instead of it.

- **`complexity_fingerprint` (W3-A).** Per run (the real one and 20 phase-randomised draws, seeds 0–19, the app's own
  `preprocessing.surrogate` prepend), the **window-median curve** is the per-scale median of `mse_<scale>s` over the
  run's windows that are not left out; a scale counts for a run only if every such window is defined there (the
  block's own `mse_ci` rule). The comparison uses the scales defined in **all 21** runs. Distance = Euclidean (root of
  the summed squared differences, in nats) over those scales. d_real = ‖real − mean(20 draws)‖; d_j = ‖draw j − mean
  (the other 19)‖. **Beats** when d_real > every d_j (p = (1 + #{d_j ≥ d_real}) / 21). Fewer than 2 common scales →
  "too few scales", no verdict for that recording (expected on rec 385). Ships on ≥ 2 of the 3 recordings that can
  be judged (rec 1 and rec 3 440–464 h, rec 600 0–73 h). If the template yields no window on a span, that recording
  is "no window", not a pass.
- **`chain_cycles` (W3-B).** As the brief: the aligned stack's SVD entropy, σ² **and** eq. 17, each below every one
  of 20 background-null draws (the block's own draws if it makes 20, else computed beside it through the identical
  pipeline, seeds 0–19). A span that yields fewer cycles than the block's `min_cycles` has no verdict (expected
  possibly on rec 2). Ships on ≥ 2 of the 3 long chains (rec 3 490–540 h, rec 6 370–470 h, rec 542 370–490 h).
- **`motif_lengths` (W3-C).** The length is the **real run's** `suggested_window_s`; every draw is scored at that same
  length (its median normalised nearest-neighbour distance there), never at its own suggestion. **Beats** when the
  real median is below every draw's. When the real run suggests no length ("no length stands out"), that recording
  **does not beat** (no statistic), and the per-length medians are reported for information. Ships on ≥ 2 of the 3
  chains (rec 2 296–304 h, rec 6 400–408 h, rec 3 512–520 h); rec 385 (4 h) is reported as the supervisor's check
  (does it suggest ≈ 1 min, and does that length beat all 20 draws?).
- **Species table (W3-A, not a ship verdict).** Features = the per-scale entropies of each window over the scales
  defined in every window of the comparison, each z-scored across all windows; label = dataset (S. commune,
  C. militaris, F. velutipes, O. nidiformis, M2_aug; 2–3 channels each). Statistic = the silhouette of the dataset
  labels (Euclidean). Null = the same windows' phase-randomised copies (each channel's span phase-randomised as the
  app's surrogate does, then the identical chain), silhouette of the same labels; as many draws as the cost allows,
  p's floor stated. Both silhouettes are reported: a surrogate that separates the species nearly as well says the
  difference is mostly the noise colour (the spectrum), not structure beyond it.
- **The √t check (W3-A).** S. commune channels through the template **without the detrend step and with
  `r_scale="sd"`**: the mean entropy over the defined scales, per channel and overall, against "0.0028"; plus the
  collapse guard's counts. Two plain answers: **the collapse reproduces** when that mean is below 0.01 (entropy
  near zero, where an uncollapsed curve of these signals sits at tenths to units); **the number reproduces** when it
  also lies within a factor of 3 of 0.0028 (0.001–0.008). The same numbers with the template's own settings beside
  them, and whether the guard fired on every collapsed scale.

## Events (chronological)

- 2026-10-14 21:2x — manager session started; read the brief, `00-common.md`, `critic.md`, `README.md`, W3-A/B/C/D/F/G,
  W1/W2 evaluations, the W2 ledger and critics, the plan's §4 A1–A2, §5 row 11, §6, §7, §8 and primary sources §1, §2,
  §4, §13b. Preflight above.
- 21:25 — committed this ledger as `01cb8c3` (round 1's base). 21:26 — **round 1 launched** (rows 1–3), each told to
  fast-forward to `01cb8c3`; all three worktrees were at `01cb8c3` with a clean tree at 21:26 (this time the tool cut
  them at the base). Launch notes: decision 1 (`RecipeCancelled`) to W3-A and W3-C, the shared `COSTED` lines; to W3-B
  the σ² headline (Q4) and decision 2, the re-test result, and the sampler's reuse by W3-G.
- 21:29 — the evaluation's statistics declared and committed (`64db0da`) before any data. The species registration
  tried in a throwaway sandbox (`eval3/try_register.py`): C. militaris, F. velutipes, O. nidiformis register through
  `scan` → `check` → `register` with the rule-5 writer and the sandbox's sidecar root (sandbox ids 615–621, 622–628,
  629–635; 1 warning each — the inferred 1 Hz); no sidecar reached the real `DATA/` tree (asserted).
- 21:30 — W3-D launched early (row 4, decision 4); its worktree was cut at `3cc2f62` and fast-forwarded to `64db0da`
  within seconds (checked 21:31, clean).
- 21:42 — the block-readout session asked for a targeted smoke on its own sandbox bridge (8797, private dist,
  `--only zzzzzzzzzz_ak` then the analyse states): agreed — nothing of mine runs in the main checkout; merges of
  round-1 code into `main` do not touch its bridge (it imports its worktree's code).
- 21:5x — the readout session's targeted smoke passed (its 3 states; 41/42 analyse states, the miss needs the full
  walk's Discovery session). It asked to merge `claude/peaceful-tesla-abc225` into `main` (readout.py, analyse_routes.py,
  `api.ts`, BlockPage.tsx, Readout.tsx, useReadout.ts, analyse.css, its smoke page, BLOCK_INTEGRATION.md, RQ4) and then
  run a **full smoke from the main checkout** (private dist, 8797, ~25–30 min). Agreed; **hold: no merge into `main`,
  no `pytest -n`, no smoke, no dist rebuild until its "done"** (a merge mid-walk could make its bridge import a
  half-new `Adapters/` tree). W3-F will start from a `main` that holds the readout work (its `api.ts` overlap).
- 22:00 — the readout session merged its branch into `main` (`61fd50d`) and is running its full smoke (8797).
  **W3-A reported** (2 commits on `01cb8c3`; 355 tests green; 33 min) → `W3-A-multiscale-entropy.md`. Points to
  judge: the template cuts **72 h windows**, so a 24 h span (the brief's evaluation spans) or a 4 h recording gets
  **no window**, refused in words; the collapse guard (ρ = r ÷ the coarse series' step MAD > 4, a measured
  placeholder) flags the 1 s scale of a detrended random walk, so it will likely fire on every real channel's
  smallest scales; `mse_r` is in stored units (V for M2_aug, mV for the species) and is not in
  `BOOKKEEPING_COLUMNS`; the estimate assumes 72 h windows (3× under with 6 h windows); the cap samples 10 template
  stretches, and RCMSE pools one offset on long series. Out of its list: the slicer moved to
  `Working/types/windowset.py::span_relative_starts` (MiniRocket now calls it) and `mse_n_scales` /
  `mse_n_collapsed` added to `BOOKKEEPING_COLUMNS` (W3-B adds two names to the same list: a merge conflict to
  expect). 22:01 — critic launched (row 5) with seven questions: the window length, the guard on realistic
  backgrounds, unit-bearing columns as features, the estimate's assumption, the cap's bias, the size and power of
  the declared statistic, the scope.
- 22:01 — **the declared evaluation spans for `complexity_fingerprint`, fixed now, before any data** (W3-A's 72 h
  window came after the brief named 24 h spans): rec 1 and rec 3 are judged on a span that **starts at 440 h (wave
  1's 24 h spans' start) and runs for one window of the template as it ships** — 440–512 h at 72 h; the 24 h spans
  as named only if the shipped window is ≤ 24 h. rec 600 stays 0–73 h; rec 385 (4 h) is reported as "no window"
  (refused in words), and the block is also run on it with one 4 h window, for information, as the brief's "too few
  scales" check. Reason: a template that refuses a span cannot be judged on it; the rule depends on the template's
  parameters, not on any result.
- 22:39 — **W3-D reported** (3 commits on `64db0da`; 339 + 11 (venv) tests green; 68 min) → `W3-D-mpdist.md`. Points to
  judge: its own MPdist (dense numpy engine up to j_A·j_B·s ≤ 1e8, `stumpy.stump` above, which compiles 40–106 s on
  first use); flat / gap pieces left out (an adaptation; plain stumpy reads a hump and its mirror on flat baselines as
  identical); `sub_frac` 0.5 (snippets uses 0.35, measured); footing raw/√(2s); a per-pair trend-kept null (5 draws,
  0.9 × p05) with 10–20 % false positives on pure noise; `_edge_payload`'s `within = value <= threshold` will read
  every MPdist edge "within" (a wrong verdict on the face until fixed). The manager's read-only query of the real
  Library: 3,616 members, median 38 samples, **760 (21 %) shorter than 16 samples — MPdist refuses them**, 231 longer
  than 900, max 324,000; `motif_edge` is **empty** (no accepted RQ3 pairs yet), so the MPdist read-out will use five
  families' members against their medoids (the brief's fallback). 22:42 — critic launched (row 6): fidelity, the
  per-pair null, `within` on the face, latency of the stumpy compile in the bridge, refusals at real proportions,
  the 5 % percentage, scope.

## Decisions taken on the researcher's behalf

1. **One cancellation exception for W3-A and W3-C: `Working.execution.RecipeCancelled`.** The executor re-raises it
   as a cancellation (`except RecipeCancelled` in `_execute_recipe_with_conn`), whereas any other exception raised
   inside a step — window matrix's `BuildCancelled` included — becomes `RecipeExecutionError`, a failure; raised
   before the step returns, it leaves no step-cache entry. W3-F settles the bridge side (the job reads *cancelled*,
   null draws stop).
2. **W3-B's coherence headline is σ² (wave-2 decision 4), eq. 17 beside it; its per-group verdict against the
   background null stays on eq. 17**, σ²'s own result against the same null reported beside it, and W3-B reports where
   the two disagree on its synthetic sets — the re-measure on σ² the researcher's decision waits for. (The template's
   evaluation statistic, fixed by the brief, requires both.)
4. **W3-D (MPdist) starts now, beside round 1, not after it.** It depends on none of round 1's code and touches none
   of its files (`Working/distances.py`, `tests/test_distances.py`, matching, one `DISTANCE_LABELS` line), so the
   brief's round-2 placement buys nothing but delay; started early, its critic and fix round overlap round 1's, and
   W3-F can then wire its Family-page read-out (item 10) instead of leaving it for a follow-up. Machine at 21:30: CPU
   ~36 %, 16 logical cores, 13.7 GB RAM with ~1.7 GB free — four implementers, as wave 2's round 1 ran.
3. **The Library side of decision 4 is folded into round 2**: W3-G puts σ² first in `shape_families`' summary lines and
   the coherence payload it returns, and measures both variants' verdicts against the quiet-stretch null (the verdict
   stays on eq. 17 unless the researcher moves it); W3-F puts σ² first on the Family page and the families table.
