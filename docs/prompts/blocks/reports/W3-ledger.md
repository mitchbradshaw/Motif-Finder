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
| 5 | critic | W3-A | `a03f242747d328696` | (reads row 1's worktree) | — | `01cb8c3` | launched 22:01; reported 22:59: **merge after fixes** (1 template blocker, 4 should-fix, 4 nits; the declared statistic's null flawed) → `W3-A-multiscale-entropy.critic.md` |
| 1a | fixer (row 1 resumed) | W3-A fix round 1 | `a67442d9e04015d6a` | row 1's | row 1's | `01cb8c3` | sent 23:04; reported 23:37 (`ffe51b2`) → `W3-A-multiscale-entropy.fix1.md`; **merged as `5d6bb01`** |
| 2 | implementer | W3-B `interrogation.cycle_shapes` + `Working/background_null.py` | `a7834e530174e1643` | `.claude/worktrees/agent-a7834e530174e1643` | `worktree-agent-a7834e530174e1643` | `01cb8c3` | launched 21:26; reported 22:49 (`b94881b`, 83 min) → `W3-B-cycle-shapes.md` |
| 7 | critic | W3-B | `a5f632b4352ec10f8` | (reads row 2's worktree) | — | `01cb8c3` | launched 22:52; reported 23:15: **merge after fixes** (3 blockers, 6 should-fix, 3 nits) → `W3-B-cycle-shapes.critic.md` |
| 2a | fixer (row 2 resumed) | W3-B fix round 1 | `a7834e530174e1643` | row 2's | row 2's | `01cb8c3` | sent 23:17 (decision 13); re-critique to follow (behavioural blockers) |
| 3 | implementer | W3-C `detection.pan_matrix_profile` | `aeeb2080e0967a2d2` | `.claude/worktrees/agent-aeeb2080e0967a2d2` | `worktree-agent-aeeb2080e0967a2d2` | `01cb8c3` | launched 21:26; reported 23:04 (`925056a`, 99 min) → `W3-C-pan-matrix-profile.md` |
| 8 | critic | W3-C | `ad8d8aad71e6d533b` | (reads row 3's worktree) | — | `01cb8c3` | launched 23:06, seven manager questions |
| 4 | implementer | W3-D `mpdist` (fourth Library distance) | `a5a78efe8b36c0a92` | `.claude/worktrees/agent-a5a78efe8b36c0a92` | `worktree-agent-a5a78efe8b36c0a92` | `64db0da` | launched 21:30, early (decision 4; cut at `3cc2f62`, at `64db0da` by 21:31); reported 22:39 (`c88a236`, 68 min) → `W3-D-mpdist.md` |
| 6 | critic | W3-D | `a380d497100469282` | (reads row 4's worktree) | — | `64db0da` | launched 22:42; reported 23:02: **merge after fixes** (4 should-fix, 4 nits; arithmetic exact) → `W3-D-mpdist.critic.md` |
| 4a | fixer (row 4 resumed) | W3-D fix round 1 | `a5a78efe8b36c0a92` | row 4's | row 4's | `64db0da` | sent 23:06; reported 23:29 (`48710ae`) → `W3-D-mpdist.fix1.md`; **merged as `fe8e495`** |
| 9 | implementer | W3-G the quiet-stretch null for families; a trend-kept k-Shape null | `a17192b65fcf2dd72` | `.claude/worktrees/agent-a17192b65fcf2dd72` | `worktree-agent-a17192b65fcf2dd72` | `6bd3e40` (`wave3-round2-base`) | launched 23:33 (decision 14); stopped ~00:3x (API limit), resumed 02:01; reported 02:03 (`2a4ca0e`) → `W3-G-quiet-stretch-null.md` |
| 10 | critic | W3-G | `a8f15e6dcd6951107` | (reads row 9's worktree) | — | `6bd3e40` | launched 02:04, seven manager questions |

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

- **Correction, 23:03, still before any real data (decision 5): the null for `complexity_fingerprint` and for the
  species table is AAFT surrogates** (amplitude-adjusted phase randomisation, Theiler 1992: the recording's own sample
  values, rank-mapped onto a phase-randomised Gaussian version — same spectrum, approximately, and **the same value
  distribution**), 20 draws, seeds 0–19 — `preprocessing.surrogate` with method `aaft` once W3-A's fix adds it, else
  `Pipelines/drop_motifs/nulls1.py::aaft_surrogate` with the identical chain by direct adapter calls. The plain
  phase-randomised result (the app's default null) is reported **beside** it, not instead. Reason (W3-A critic Q6,
  measured, not a result on real data): plain phase randomisation Gaussianises the values, and sample entropy with a
  MAD-based r reads the value distribution, so a linear Gaussian process seen through a static non-Gaussian transform
  (AR(1) → exp) "beat" its plain-phase surrogates 20 / 20 at 24 h and 72 h (0.62 nats, ~60× the draws' spread),
  while with AAFT it beat 2 / 12 and real drop structure still beat 12 / 12; these channels are strongly non-Gaussian
  (`nulls1.py`'s own docstring). The statistic itself (the window-median curve's distance) is unchanged.

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
- 22:49 — **W3-B reported** (2 commits on `01cb8c3`; 387 tests green; 83 min) → `W3-B-cycle-shapes.md`. Points to judge:
  **SigClust rejected "one Gaussian" on every synthetic set, pure noise included**, so the implementer added a second
  gate (the split must also beat uniform samples along its own direction) and chose K by bisection (Kimes et al. 2017)
  rather than Calinski–Harabasz; the verdict became "eq. 17 below every background draw AND > 3 robust SDs below
  their median" (the Library's 0.9 × p05 failed a clean chain at z = 19: cycle eq. 17 sits at 0.86–0.96); where the
  two variants disagree, **eq. 17 fails two-shape chains at 50 % noise that σ² passes** (z 0.9 / 1.4 vs 4.6 / 7.2;
  never the reverse) — the re-measure decision 4 waits for; the background null avoids only the detector's event
  spans, so on a dense chain cycle-length windows rarely fit and fall back to random cuts ("phase-locked vs random
  phase"); out of scope: `SideInputSpec.required` in `Adapters/base.py` and unbound optional side inputs skipped in
  `Working/side_inputs.py` (needed for "unbound → cut from x"); six `BOOKKEEPING_COLUMNS` names, not two; the test file
  takes ~6 min under load. 22:52 — critic launched (row 7), eight questions: the mode gate's size/power and direction
  selection, SigClust on noise, the verdict rule and the per-draw values the evaluation needs, the background null on
  dense chains, the side-input contract, the gap/split rule under real jitter, the template at realistic size, scope
  and test cost.
- 22:55 — the readout session sent **"done"**: merged as `61fd50d`; its full smoke from main: 650 states, 56 failures,
  all timeouts outside its files with the CPU at 100 %, the heaviest process a `cal2.py` with multiprocessing workers
  (one of my critics' experiment scripts). **The hold on merges into `main` is lifted.** It now re-checks the failing
  units for ~20 min on its own worktree's code (port 8797). CPU at 22:54: 99 %. Asked my three critics and the W3-C
  implementer to cap themselves at 4 workers / 4 numba threads until ~23:20, so the polish session's re-checks get
  headroom (the researcher's priority until 21 October is the UI; wave 3 must not slow it).
- 22:59 — **W3-A critic: merge after fixes.** F1 (template blocker): 72 h windows give no window on 24 h spans —
  already met by the 22:01 span rule. F2: the collapse guard (ρ) misses 6 of 9 collapsed scales under a smooth drift
  and its advice ("or use r_scale = mad") is wrong; the critic's **inflation** rule separates them cleanly. F3:
  `mse_r` (stored units) and `mse_drift_share` reach clustering as features (unit-label silhouette 0.177 vs 0.079),
  and a left-out window's all-NaN row is median-imputed and clustered as a typical window. F4: the estimate
  under-runs by 2.1–2.7× with 6 h / 1 h windows. F5: interpolated samples never reach the face. **Q6, about my own
  declared statistic:** its size on Gaussian coloured noise is 7.5 % (nominal 4.8 %), its power 39/40 on 5 × SD drops
  — but a static non-Gaussian transform of a linear process "beats" plain phase surrogates 20/20 (the null tests the
  value distribution); AAFT fixes it. → the 23:03 correction (decision 5). 23:04 — fix round 1 sent to the
  implementer (row 1a), decisions 6–9.
- 23:02 — **W3-D critic: merge after fixes.** The MPdist arithmetic equals `stumpy.mpdist` and a brute-force P_ABBA to
  7e-15; the flat-piece exclusion changed 0 of 200 ordinary pairs. But: every MPdist edge reads "within the seed cut"
  through the route (F1; the symbolic distance too); *Add N matches* drops `edges_refused` (F2); the trend-kept null's
  `beyond_noise` is unusable as a verdict, per pair or per family (11 % false positives per pair, 50 % on random-walk
  pairs at 1,800 samples; troughs at their own null — the cubic-trend blind spot) (F3); at realistic noise MPdist
  barely tells drop from square (F4; percentage 0.25 helps); the "5 %" text is wrong by ~2× (F5). Latency is fine:
  the bridge already pre-warms `stumpy.stump` and the route runs in the threadpool. 23:06 — fix round 1 sent (row 4a),
  decisions 10–12.
- 23:04 — **W3-C reported** (2 commits on `01cb8c3`; 38 + 246 tests green; 99 min) → `W3-C-pan-matrix-profile.md`.
  Points to judge: its own verdict rule (gap = N^(1/3)·ln(z_K/r_K)/ln(z_med/z_K) ≥ 6 and r_K below every draw; a
  length judged only on spans ≥ 14 windows) with ~4 % false suggestions at one draw; a no-structure test seed changed
  7 → 8 after seed 7 gave a false suggestion; the 1 h rows are never judged on a 4 h span; scrump barely pays; the
  compile term in the estimate. 23:06 — critic launched (row 8), seven questions, including whether plain phase
  surrogates are biased for this template too (if so, the evaluation's null switches to AAFT before any data).
- 23:15 — **W3-B critic: merge after fixes, three blockers.** B1: on a random-walk background with chain-like timing
  the block reports K = 2 in 4–5 of 10 no-structure chains (z-normalised noise cycles are sign-bimodal, ±PC1; neither
  gate can see it); B2: SigClust's MAD floor (Liu et al.'s sparse-HDLSS estimate) makes it reject a true one-cluster
  Gaussian 12/12 at n ≥ 200 — an implementation issue, not the data; B3: on a span the chain fills, every pseudo-cycle
  falls back to a random-phase cut of the chain (fallback 1.00 for sharkfins), and eq. 17 then cannot clear it even
  for a perfect chain — with 10 h quiet margins the pseudo-cycles come from the margins and eq. 17 clears at z 24–68.
  Should-fix: the per-draw null values are not in meta (S1, needed by my evaluation); the per-group null favours the
  group (S2, σ² 9/36 false passes); **eq. 17 is the weak half of the declared statistic (S3: an 83-cycle trough chain
  σ² 0.37 vs 0.59 but eq. 17 0.87 vs 0.88)**; the gap rule loses 5.5–17.5 % of true cycles at interval jitter CV
  0.3–0.5 (S4); 12–19 cycles can never split (S5); an unbound waveform silently cuts from x (S6). The side-input
  contract change leaves every existing block, the recipe hash and the bridge unchanged (98 webui tests pass).
  23:17 — fix round 1 sent (row 2a), decision 13.
- 23:17 — **two refinements of the `chain_cycles` statistic, before any data:** (1) a span whose background null
  falls back for more than half its pseudo-cycles is **"untested"** (no verdict; the fallback share reported), the
  block's own rule after its fix; (2) the statistic stays as the brief fixed it — σ² **and** eq. 17 below every draw —
  although the critic measured eq. 17 as the weak half (S3): the brief fixed both knowingly, and the researcher's
  decision keeps the verdict on eq. 17 until re-measured; σ² alone is reported **beside** the verdict and the choice
  goes to the researcher. The brief's spans all have quiet margins (rec 3: drops 500–530 h in 490–540 h; rec 6: chain
  ~376–445 h in 370–470 h; rec 542: trains 398–474 h in 370–490 h; rec 2: 298.2–302.8 h in 294–304 h).
  (3, 23:2x) When a span holds several sequences (trains), **its verdict is its largest sequence's** (most cycles
  used); the others are reported. The app's phase-randomised null is run through the template on 5 draws as the
  further floor (events and cycles found).
- 23:2x — the readout session: all its smoke checks done, bridges 8797/8798 stopped; re-run alone, Interrogation,
  Explore, Library and Models pass; Settings, Review and Seed sources fail identically on the pre-change code
  (`64db0da`) — load or walk-order artifacts. My agents stay at ≤ 4 workers each (four agents share 16 cores).
- 23:29 — **W3-D fix round 1 reported** (red `e4ff42f` → green `48710ae`; 321 conda + 14 venv tests) →
  `W3-D-mpdist.fix1.md`: off-footing distances (MPdist **and symbolic** — SAX MINDIST without the √(n/w) factor was
  never on the cut's footing) show no cut and no "within"; `edgesRefused` + `refusalSummary` in the response (an
  exemplar under 16 samples said once); `mpdist_null` is context only with its bias stated; `percentage` 0.25
  (pool share 0.45–0.50, about the median closest-piece distance); `missing` split into `refused` / `not_computed`;
  the importer refuses MPdist in words. Reviewed by the manager (`git diff c88a236..48710ae` of `library.py`,
  `matching.py`, the importer): matches the instructions; no formal blocker was raised, so no re-critique.
  23:31 — dry run clean; **merged W3-D as `fe8e495`**; its tests + the standard five + end_to_end (conda) and the
  Library webui tests (venv) running.
- 23:33 — **W3-G launched early** (row 9, decision 14) from `wave3-round2-base` = `6bd3e40` (main `fe8e495` + W3-B at
  `b94881b`, built with `git merge-tree` + `commit-tree`; nothing changed on main). Launch notes: the sampler's
  contract and the fragmented-free-stretch case (W3-B critic B3), W3-B's compatible extension in progress, decision
  4's σ²-first (decision 3), the re-test that was run, g-05's fragility, W3-D merged in its base. W3-G's worktree
  was at `6bd3e40`, clean, by 23:33.
- 23:37 — W3-D's post-merge tests on main: **323 passed** (conda: its tests, distances, seed edges, library edges, the
  importer, the standard four, end_to_end); the venv Library tests (`test_webui_mpdist_edges`,
  `test_webui_library_edges`, `test_webui_library`): **69 passed, 3 xpassed** (23:45).
- 23:37 — **W3-A fix round 1 reported** (red `2eb9be9`: 40 failed → green `ffe51b2`; 559 conda tests) →
  `W3-A-multiscale-entropy.fix1.md`: the inflation guard (√t cases flag every scale on 3 seeds; detrended random walk
  0.96–1.10, AR(1) 1.00–1.02, raw pink none), `mse_r` / `mse_drift_share` / `mse_inflation` bookkeeping, cluster and
  classifier leave out all-NaN rows (label −1, counted; kept rows cluster exactly as alone), the costliest-tiling
  estimate (721 h: 72 h windows 0.31 of it, 6 h 0.92), > 5 % filled windows left out, AAFT as
  `preprocessing.surrogate` method `aaft` (nulls1 bit-identical; Settings › Nulls offers it via `seeded_search`).
  Deliberate test changes stated: the `BOOK` set, `SURROGATE_METHODS`, the offered-methods pin. Reviewed by the
  manager (the cluster / classifier / seeded-search / windowset diffs: behaviour identical when no row is all-NaN).
  No re-critique: the critic's only blocker (F1, the 72 h template on 24 h spans) was settled by decision 6 and the
  22:01 span rule, not by code. Its one venv failure, `test_webui_discovery::test_the_scoreboard_cells_are_the_tables_own_numbers`,
  **fails on main (`fe8e495`) too** — pre-existing, not wave 3's (a task chip was filed for it).
- 23:41 — dry run clean; **merged W3-A as `5d6bb01`**. `tests/test_end_to_end.py`'s module count 54 → 55 (W3-A
  bumped `test_adapter_spec` but not end_to_end) — an integration edit on main; post-merge: **466 passed**
  (committed `a608cc4`).
- 23:48 → 23:57 — **`complexity_fingerprint` evaluated** (sandbox, `eval3/eval_mse.py --part spans`, the declared
  statistic, 20 AAFT draws + 20 plain phase draws beside): rec 1 440–512 h **beats** (d 0.84 vs AAFT draws' max 0.18;
  phase 1.10 vs 0.14); rec 3 440–512 h **beats** (1.86 vs 0.35; phase 2.39 vs 0.09); rec 600 whole 73 h **beats**
  (1.05 vs 0.83 — the narrowest; phase 1.23 vs 0.18). 9 common scales (1–174 s) each, one 72 h window, no collapse
  flag, nothing left out; the only warning the 3 blank scales (> 4.3 min). Direction: M2_aug sits **below** its
  surrogates at every scale, increasingly with scale (rec 3: −0.11 nats at 1 s → −0.93 at 174 s: more regular than
  noise with its values and spectrum); S. commune sits **above** at 1–7 s (+0.49 to +0.61) and below past ~48 s.
  **3 of 3 → ships.** Now running: rec 385, the √t check, the species table (20 AAFT + 5 phase draws).
- 00:0x — **integrated `complexity_fingerprint` into CANONICAL** test-first (red `d521852` → `46480ce`; 13 + 8 venv
  passed). rec 385: the template **refuses in words** ("no window fits: the span has 14401 samples and one window is
  259200 … shorten window_s or widen the span"); with one 4 h window (information) 5 scales are defined and it beats
  all 20 AAFT draws (d 1.79). **The √t check** (S. commune CH0–CH6, raw, `r_scale="sd"`): mean entropy over the 9
  defined scales 0.197 / 0.053 / 0.052 / 0.021 / 0.161 / 0.494 / **0.014** (mean 0.14), against 0.58–1.18 through the
  template — **a partial collapse, not the preprint's 0.0028**: none below 0.01, so by the declared answers neither the
  collapse (< 0.01) nor the number (0.001–0.008) reproduces. **The guard fired on every defined scale of CH0–CH5 but
  not on CH6, the most collapsed:** CH6 holds a −71 mV spike (range −71.2…1.8 mV, p99.99 |x − median| 23.9), which
  inflates the SD before **and** after the 2 h detrend, so the inflation ratio stays near 1 — outlier-driven r
  inflation is a second route to collapse the inflation rule cannot see. Only `r_scale="sd"` is exposed (the
  template's MAD r is immune); a follow-up: flag SD ÷ (1.4826 × MAD) when `r_scale="sd"`.
- ~00:3x — **three agents stopped on an API session limit** (HTTP 429, "resets 2am"): the W3-B fixer (red `544ba34`
  committed, its fix uncommitted in 4 files), the W3-C critic (mid-sweep), W3-G (red `f36ef75` → green `2a4ca0e`
  committed; waiting on its cost measurement). The species evaluation (a local process) ran on. 02:01 — the limit had
  reset: all three resumed by `SendMessage` to their ids, each told where it stopped.
- 02:03 — **W3-G reported** (red `f36ef75` → green `2a4ca0e`; 556 conda + 85/12 venv tests) →
  `W3-G-quiet-stretch-null.md`. Its key finding: quiet windows cannot simply replace the trend-kept fakes, because a
  family was **selected** for being tight — so the test is selection-matched (a family of m among n must sit closer
  to its centre than the q = min(5 %, m/2n) quantile of quiet windows), with a **0.7 margin** (pure-noise families on
  AR(1) φ 0.98–0.99 reached 0.80×; 14 of 124 were below 0.9); humps and ramps now pass (0.01–0.54×; the trend-kept
  null called them noise at 1.15–3.0×); k-Shape gets a trend-kept null and is **offered in Event families again**
  (every no-structure family flagged at the defaults); σ² first in `variants` and summaries, eq. 17 keeps the verdict
  (σ² at 0.9 let 1 of 52 pure-noise families through); detections are not avoided (only Library members and
  sequences); a room guard (≥ 20 disjoint member-length windows) and borrowing, with a per-family fallback to the
  trend-kept null. Out of its list: `engine.py`'s `background=` pass-through, one line each in `_family_detail` and
  `run_grouping_job`. Costs: HDBSCAN regroup 41 → 57 s at 3,616, a 2,000-member Family page 7.2 s cold. 02:04 — critic
  launched (row 10), seven questions.

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
5. **The complexity evaluation's null is AAFT, not plain phase randomisation** (the declared-statistics correction
   above, 23:03, before any real data). Reason: a measured flaw in the null (it tests the value distribution), not a
   result.
6. **`complexity_fingerprint` keeps its 72 h window** (the W3-A critic recommended 24 h by default). Reasons: at 72 h
   the declared statistic has 4× the power on weak structure (drops at 2 × SD: 8/20 against 2/20) and reaches 174 s
   instead of 48 s; nearly every stored recording is ≥ 72 h (M2_aug 721 h, L_LM 636 h, the species 73–911 h); the
   evaluation spans follow the template by the rule fixed at 22:01 (440–512 h). The description tells a user with a
   shorter recording to set `window_s` to the longest whole multiple of 24 h it allows (24 h reaches ~50 s).
7. **Left-out windows never reach a fit:** `catalogue.cluster` and `catalogue.classifier` leave out (and count) a row
   whose features are all NaN instead of median-imputing it into a typical window; `mse_r` (stored units) and
   `mse_drift_share` join `BOOKKEEPING_COLUMNS`. Done by the W3-A fixer, out of its list, test-first; it changes
   shipped blocks only for all-NaN rows, which carry no information. Reason: honesty on the face (00-common, rule 7).
8. **`preprocessing.surrogate` gains method `aaft`** (moved from `Pipelines/drop_motifs/nulls1.py`, imported back
   there bit-identically), so the app's paired null can be fair for MSE; Settings › Nulls reads the block's own
   choices (`seeded_search.offered_methods`), so no page work is needed. Default unchanged, so no recipe hash moves.
9. **The collapse guard becomes the critic's inflation rule** (per window: the r rule's spread of the window as it
   arrives ÷ the same spread after a 2 h rolling mean is removed; > 1.5 flags every scale of that window), ρ kept in
   meta as information. Reason: ρ missed 6 of 9 collapsed scales under a smooth drift and sat inside the random-walk
   range at 1 s (a coin toss); inflation measured 0.95–1.10 on every stationary or template-detrended background and
   2.8–13 on the raw drifting ones.
10. **The MPdist fixer gets `webui/server/library.py::_edge_payload` and `post_run_matches`** (beyond its one handed
    line) and `Pipelines/import_drop_motifs/importer.py`: an off-footing distance shows no "within" (`threshold` and
    `within` None, its footing instead), the symbolic distance too if its value is not on the seed cut's footing, and
    the refusals reach the response. Reason: a wrong verdict must not reach the Family page between W3-D's merge and
    W3-F's; W3-G edits other functions of the same file.
11. **MPdist's `percentage` defaults to 0.25, not the paper's 0.05**, named as an adaptation. Reason: Library members
    are cut tight, and at realistic noise 0.25 cut drop/square confusion from 20–63 % to 3–33 % without hurting the
    extra-baseline case (critic F4). A question for the researcher in the final report.
12. **`mpdist_null` gives context, not a verdict** (`beyond_noise` removed). Reason: the trend-kept null is biased on
    coloured noise and blind to troughs (critic F3); the follow-up is an empirical null from the member's own
    recording, which W3-G's sampler makes possible.
13. **Cycle shapes' K gate is calibrated on nulls that reproduce noise's sign-bimodality**: the same 2-means on each
    background draw (per-cycle phase-randomised copies when the background falls back), K > 1 only below every draw,
    plus the mode test; SigClust is kept as a reported number without its floor, not as a gate. Reason: the critic's
    known-answer checks (B1, B2) — no gate against a Gaussian or a uniform can tell z-normalised noise's ±PC1 split
    from two shapes; its prototype passed 0/18 noise stacks and every two-shape case to 30 % noise.
14. **W3-G starts from a round-2 base branch** (`wave3-round2-base`: main + W3-B at `b94881b`) instead of waiting
    for W3-B's fix round and re-critique (~2 h). Reason: W3-G needs only the sampler, whose contract the critic did
    not fault (its fix adds one report key, compatibly); the brief allows this when a round-1 block's API is settled
    (wave 2's decision 16). main takes W3-B only after its re-critique; W3-G merges after W3-B's final branch.
3. **The Library side of decision 4 is folded into round 2**: W3-G puts σ² first in `shape_families`' summary lines and
   the coherence payload it returns, and measures both variants' verdicts against the quiet-stretch null (the verdict
   stays on eq. 17 unless the researcher moves it); W3-F puts σ² first on the Family page and the families table.
