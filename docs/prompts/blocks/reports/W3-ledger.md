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
| 2a | fixer (row 2 resumed) | W3-B fix round 1 | `a7834e530174e1643` | row 2's | row 2's | `01cb8c3` | sent 23:17 (decision 13); stopped ~00:3x (API limit), resumed 02:01; reported 02:3x (`af4a8cf`) → `W3-B-cycle-shapes.fix1.md` |
| 7a | re-critic (row 7 resumed) | W3-B fix round 1, changed parts only (`b94881b..af4a8cf`) | `a5f632b4352ec10f8` | row 2's | — | — | launched 02:37; reported 02:48: **merge after fixes** (B1–B3 hold; S-A, S-B should-fix) → `W3-B-cycle-shapes.critic2.md` |
| 2b | fixer (row 2 resumed) | W3-B fix round 2 (the last) | `a7834e530174e1643` | row 2's | row 2's | `01cb8c3` | sent 02:48; reported 03:28 (`bc2c0b1`) → `W3-B-cycle-shapes.fix2.md`; **merged as `4ab274d`** |
| 3 | implementer | W3-C `detection.pan_matrix_profile` | `aeeb2080e0967a2d2` | `.claude/worktrees/agent-aeeb2080e0967a2d2` | `worktree-agent-aeeb2080e0967a2d2` | `01cb8c3` | launched 21:26; reported 23:04 (`925056a`, 99 min) → `W3-C-pan-matrix-profile.md` |
| 8 | critic | W3-C | `ad8d8aad71e6d533b` | (reads row 3's worktree) | — | `01cb8c3` | launched 23:06; stopped ~00:3x (API limit), resumed 02:01; reported 03:5x: **merge after fixes** (3 blockers, 3 should-fix, 2 nits) → `W3-C-pan-matrix-profile.critic.md` |
| 3a | fixer (row 3 resumed) | W3-C fix round 1 (merge main first) | `aeeb2080e0967a2d2` | row 3's | row 3's | `01cb8c3` → main | sent 03:53; reported 04:40 (`617edc2`; merged main as `56a23f4`) → `W3-C-pan-matrix-profile.fix1.md` |
| 8a | re-critic (row 8 resumed) | W3-C fix round 1, changed parts only | `ad8d8aad71e6d533b` | row 3's | — | — | launched 04:41 (the blockers were behavioural; asked to keep it to ~30–40 min); reported 05:1x: **merge after fixes** (3 should-fix, no blocker) → `W3-C-pan-matrix-profile.critic2.md` |
| 3b | fixer (row 3 resumed) | W3-C fix round 2 (the last) | `aeeb2080e0967a2d2` | row 3's | row 3's | main | sent 05:1x: stalls detected on what the template hands the block, `stall_s` (60 s) apart from `max_fill_s`, no "suggested" on the summary line; stopped ~05:4x (API limit), resumed 07:02; reported 07:06 (red `87f4ffc` → green `cd177d6`, `5a77f67`) → `W3-C-pan-matrix-profile.fix2.md`; **merged as `e068669`** |
| 4 | implementer | W3-D `mpdist` (fourth Library distance) | `a5a78efe8b36c0a92` | `.claude/worktrees/agent-a5a78efe8b36c0a92` | `worktree-agent-a5a78efe8b36c0a92` | `64db0da` | launched 21:30, early (decision 4; cut at `3cc2f62`, at `64db0da` by 21:31); reported 22:39 (`c88a236`, 68 min) → `W3-D-mpdist.md` |
| 6 | critic | W3-D | `a380d497100469282` | (reads row 4's worktree) | — | `64db0da` | launched 22:42; reported 23:02: **merge after fixes** (4 should-fix, 4 nits; arithmetic exact) → `W3-D-mpdist.critic.md` |
| 4a | fixer (row 4 resumed) | W3-D fix round 1 | `a5a78efe8b36c0a92` | row 4's | row 4's | `64db0da` | sent 23:06; reported 23:29 (`48710ae`) → `W3-D-mpdist.fix1.md`; **merged as `fe8e495`** |
| 9 | implementer | W3-G the quiet-stretch null for families; a trend-kept k-Shape null | `a17192b65fcf2dd72` | `.claude/worktrees/agent-a17192b65fcf2dd72` | `worktree-agent-a17192b65fcf2dd72` | `6bd3e40` (`wave3-round2-base`) | launched 23:33 (decision 14); stopped ~00:3x (API limit), resumed 02:01; reported 02:03 (`2a4ca0e`) → `W3-G-quiet-stretch-null.md` |
| 10 | critic | W3-G | `a8f15e6dcd6951107` | (reads row 9's worktree) | — | `6bd3e40` | launched 02:04; reported 02:3x: **merge after fixes** (5 should-fix, 3 nits) → `W3-G-quiet-stretch-null.critic.md` |
| 11 | implementer | W3-F the wave-3 UI | `a9bcefee16fc666b3` | `.claude/worktrees/agent-a9bcefee16fc666b3` | `worktree-agent-a9bcefee16fc666b3` | `a5baf8b` (main) | launched 03:45 (decision 20); reported 04:35 (`d1dc46c`, 50 min) → `W3-F-ui.md` |
| 12 | critic | W3-F | `ad9069dfbd66c843e` | (reads row 11's worktree) | — | `a5baf8b` | launched 04:39; reported 05:00: **merge after fixes** (1 blocker, 4 should-fix, 3 nits) → `W3-F-ui.critic.md` |
| 11a | fixer (row 11 resumed) | W3-F fix round 1 + the W3-C follow-up (merge `617edc2`) | `a9bcefee16fc666b3` | row 11's | row 11's | `a5baf8b` | sent 05:01 (decision 25); reported 05:2x (merge `f42dd35`, red `ff5bc21` → green `ea59ee6`) → `W3-F-ui.fix1.md` |
| 12a | re-critic (row 12 resumed) | W3-F fix round 1, changed parts only (`f42dd35..ea59ee6`) | `ad9069dfbd66c843e` | row 11's | — | — | launched 05:28 (the blocker was behavioural), with the three null readers the fixer left; stopped ~05:4x (API limit), resumed 07:02; reported 07:04: **merge after fixes** (3 should-fix, 1 nit; the blocker holds) → `W3-F-ui.critic2.md` |
| 11b | fixer (row 11 resumed) | W3-F fix round 2 (the last) | `a9bcefee16fc666b3` | row 11's | row 11's | `a5baf8b` | sent 07:05 (decision 27); reported 07:25 (red `f102dee` → green `0de9e6e`) → `W3-F-ui.fix2.md`; merges without a third critique (decision 28) |
| 9a | fixer (row 9 resumed) | W3-G fix round 1 | `a17192b65fcf2dd72` | row 9's | row 9's | `6bd3e40` | sent 02:35; reported 03:14 (`84e8326`) → `W3-G-quiet-stretch-null.fix1.md`; merges after W3-B's final branch |

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

- **Correction, 03:55, still before any real data (decision 21): the `motif_lengths` null is AAFT too** — the 20
  draws are `preprocessing.surrogate` method `aaft`, seeds 0–19, scored at the real run's suggested length; the plain
  phase draws are reported beside. Reason (W3-C critic F1, measured): a linear Gaussian process through a static
  non-Gaussian transform (AR(1) → exp) got a suggestion 10/10 and beat all 20 plain-phase draws under this statistic
  10/10, and 0/10 with AAFT; AAFT kept the planted-motif power (10/10). The statistic stays conditional on the real
  run's suggestion (no suggestion → does not beat), which the critic found is what keeps it sound under AAFT.

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
  (4, 03:3x, before any data) A span whose block reports `tested: False` for the whole stack — a background that fell
  back, or **`background_colour_mismatch`** (W3-B fix round 2: the margins differ in colour from the noise under the
  chain) — is **"untested"**, no verdict; the reason is reported.
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
- 02:3x — **W3-G critic: merge after fixes**, no blocker. The selection-matched quantile is sound and no pure-noise
  family was confident in any real-engine run at Library scale; humps and ramps now pass (0.13–0.39 at 10 % noise);
  k-Shape re-offered is safe (no unmarked Intervals key in 37 no-structure runs); borrowing's bias is negligible
  (±0.04). Should-fix: coherence's quiet null scores fewer rows than the family when n_set > 2,000 (F1); the Family
  page passes the view-filtered row count as n_set, so the verdict moves with the filter (F2); **"detections are not
  avoided … only makes the null tighter" is false both ways** — other-shape uncatalogued events loosen the null
  (10-member noise families reached 0.643), own-shape ones make real sharp families fail (1.29–1.31× where
  trend-kept gave 0.20–0.37×) (F3); σ²'s `beyond_noise` field is True on pure noise (F4); the 0.7 margin is thin for
  10–20-member families (0.714 worst clean) (F5). 02:35 — fix round 1 sent (row 9a), decisions 15–16.
- 02:3x — **W3-B fix round 1 reported** (red `544ba34`: 15 failed → green `af4a8cf`; 361 passed, 7 skipped) →
  `W3-B-cycle-shapes.fix1.md`: the K gate calibrated on the background draws (or per-cycle phase copies when the
  background falls back), with the mode test and 2-means on the top 32 PCs — chain-timed noise K = 2 in 0/30, two
  shapes 9/9 on both nulls; SigClust unfloored and reported only; span-filling chains `~untested` with the
  longest-free-stretch warning (`sample_background` gains `longest_free_samples` / `longest_free_s`, compatibly);
  the 20 per-draw values in meta; the per-group null matched to the selection (1 of 24 noise groups passed, was σ²
  9/36); one whole-stack eq. 17 false positive in 30 random-walk runs (z 3.16). The block's tests take 481 s.
  02:37 — re-critique of the changed parts sent to the W3-B critic (row 7a): the blockers were behavioural.
- 02:48 — **W3-B re-critique: merge after fixes.** B1–B3 hold at the defaults on the critic's own cases (K > 1 in
  0/66 stationary noise runs; two shapes found at 15–30 % noise; 10 Hz fine); the 32-PC projection is sound; the
  rank-matched group null is fair; S1 has every value the evaluation needs. New: **S-A** — when the quiet margins
  differ in colour from the noise under the chain, chain-timed noise reads "beyond noise" 10/10 (z 14–24) and K = 2–3
  in 2/10; a per-cycle phase null on σ² separates it (noise inside 5/5, real chains beat it 9/9). **S-B** — one
  stationary false pass in 76 passed on eq. 17 but not σ², leaving an unmarked key. Power given up for size: random
  walk at 30 % noise with an 80/20 or 90/10 mix now K = 1. 02:48 — fix round 2 (the last) sent (row 2b), decisions
  17–18; test-cost cuts as the critic proposed.
- 03:14 — **W3-G fix round 1 reported** (red `a4a2a6f`: 26 + 3 failed → green `84e8326`; 541 conda; webui 87 + 3
  xpassed before two deliberate assertion updates, the subset 8/8 after) → `W3-G-quiet-stretch-null.fix1.md`: either
  null passes (`passed_by` names it; a drop family on a recording with 448 uncatalogued drops: noise-like → confident
  via trend-kept 0.06; the hump in the same recording via quiet 0.02; pure noise with 150 uncatalogued drops: none
  confident); margin 0.6 with the small-family worst case pinned; coherence like-for-like (pool = n_set up to 4,000,
  `take` ≥ 10); the Family page's n_set is the grouping's item count, unmoved by view filters; σ²'s verdict-shaped
  field removed (`squared_vs_null_ratio`); free-stretch and span caches; `why` names borrowed windows and the
  detection-overlap share. A 2,000-member Family page: 23–40 s cold (32 s without the background: the members' own
  coherence dominates), ~0.95 s cached. Reviewed by the manager; no blocker was raised, so no re-critique. Merges after
  W3-B's final branch (its base holds W3-B at `b94881b`).
- 03:28 — **W3-B fix round 2 reported** (red `f39ff2d`: 5 failed → green `bc2c0b1`; 365 passed, 7 skipped; the
  block's 4 files 216 s) → `W3-B-cycle-shapes.fix2.md`: the colour check (σ² against 20 per-cycle phase copies;
  mixed-colour noise flagged 10/10 and K = 1 10/10; real two-shape chains K = 2 in 24/24, not flagged on mixed colour,
  σ² beats the copies at z 17–51), **K gated on both nulls**; an unmarked key needs eq. 17 and σ² both; the rules
  text corrected; the power given up named; the 1,000-cycle test dropped (size pinned by the multi-seed test). One new
  conservative false alarm: a real two-shape chain on a slow-drift background at 30 % noise keyed `~untested` (2 of
  2) — never a false pass. This was the last fix round the brief allows; S-A and S-B were the re-critique's only
  should-fixes, and both are done, so it merges (decision 19).
- 03:29 — **merged W3-B as `4ab274d`**: conflicts in `BOOKKEEPING_COLUMNS`, the `BOOK` pin and the adapter count,
  each resolved by keeping both sides (count 56). Integration: `COSTED` gains `interrogation.cycle_shapes`;
  `test_end_to_end`'s module count 56. Post-merge: **454 passed** (committed `880c5ee`).
- 03:35 — **merged W3-G as `b81fa9c`** (no conflict: `background_null.py` auto-merged — W3-B's
  `longest_free_*` keys and W3-G's `MemberBackground` side by side). Post-merge conda: **618 passed**; the venv
  Library tests running.
- 03:35 → 03:38 — **`chain_cycles` evaluated** (`eval3/eval_cycles.py`, the declared statistic: the block's own 20
  background draws, σ² and eq. 17 both below every draw; the largest sequence; untested on fallback > 0.5 or a colour
  mismatch):

  | Chain | Cycles used | σ² real (draws' min) | eq. 17 real (draws' min) | Fallback / colour | K | Verdict |
  |---|---|---|---|---|---|---|
  | rec 3 490–540 h | 77 of 115 | 0.169 (0.445) | 0.652 (0.839) | 0 / no | 1 | **beats** |
  | rec 6 370–470 h | 104 of 113 | 0.097 (0.298) | 0.457 (0.648) | 0 / no | 1 | **beats** |
  | rec 542 370–490 h (10 Hz) | 120 of 155 (sequence 1) | 0.460 (0.795) | 0.918 (0.944) | 0 / no | 1 | **beats** |
  | rec 2 294–304 h | 9 of 12 | — | — | — | — | no verdict: 9 usable cycles < 10 |

  **3 of 3 long chains → ships** (`chain_cycles` moved into CANONICAL test-first, red `f84d335` → `6f07cff`, 18
  passed; its description gained one sentence on reading the marks). Surrogate floor: the app's phase draws found 0
  events on 19 of 20 draws (one draw: 1 event). Findings: **K = 1 on every chain** (SigClust p 0.10 / 0.10 / 0.90,
  reported only; mode test p 0.23 / 0.79 / 0.70) — one cycle shape per chain, no change points, so no order test;
  wave 2's `event_families` found two families on rec 6 (53, 13) and rec 542 (131, 11) from 600 s windows — the
  whole-cycle view sees one shape (an 80/20 mixture at 30 % noise is where the K gate gave up power, so this does not
  rule out a minority shape). Gaps: rec 3 lost 21 % of cycles as `gap_long` (the warning fired: the longest cycles).
  **Floor fractions** (per cycle, median [p25–p75]): rec 3 0.109 [0.06–0.17], half recovery 0.25 — a trough, "mostly
  back by the quarter point"; rec 6 0.205, half recovery 0.16; rec 542 0.016, half recovery 0.023; **rec 2's
  labelled sharkfins (298.2–299.2 h, cycles 0–4) 0.02–0.03, half recovery 0.04–0.06**. The raw trace explains it:
  each is a 50–78 mV drop that recovers half its depth within ~40 s, then sits 2–15 % of the depth below its starting
  level until the next drop (10 bins: −0.43, −0.07, −0.03 … +0.01 of the depth). The block's floor band (the lowest
  25 % of the cycle's range) cannot see a plateau that shallow — either these events are not sharkfins at the cycle
  scale, or "the floor" should be measured against the pre-drop level. A question for the researcher.
- 03:4x — **the species table** (`eval_mse.py --part species`; S. commune 600–602, C. militaris / F. velutipes /
  O. nidiformis CH0–CH2 registered in the sandbox only, M2_aug rec 1–3; 72 h windows: 3 / 21 / 12 / 36 / 30): the
  dataset-label silhouette on the 9 common scales is **0.428**, against **20 AAFT draws 0.22–0.37 (mean 0.29) — beats,
  p = 1/21 (the floor)**; the plain-phase draws run on. Per-dataset median curves: the four Adamatzky species fall with
  scale (S. commune 1.38 → 0.79, C. militaris 1.78 → 0.68, F. velutipes 1.68 → 0.55, O. nidiformis 1.36 → 0.07, the
  steepest), M2_aug rises (0.03 → 0.73). Most of the separation is already in the surrogates (same values and
  spectrum); the rest is structure beyond them. Caveat: M2_aug comes from another setup (stored in V, smoother at 1 s),
  so "M2_aug vs the species" mixes organism and instrument. The species run logged one `TypeError` per later chain
  run (`SideInputSpec(required=…)`): W3-B's merge at 03:29 put `interrogation_cycle_shapes.py` on disk while the
  process held the old `Adapters/base.py`; `discover_adapters` skipped that one module and the run continued — no MSE
  result is affected (lesson: no merge into main while an evaluation that discovers adapters runs).
- 03:44 — W3-G's post-merge venv Library tests: **89 passed, 3 xpassed**.
- 03:45 — **W3-F launched** (row 11, decision 20) from main `a5baf8b` (W3-A, B, D, G merged; W3-C's critic still
  running). Launch notes: the reports' "for W3-F" sections; σ² first on the Family page and families table (decision 3)
  with W3-G's `passed_by` / fallback / context line; MPdist's `within: null`, read-out column and refusal line; cycle
  shapes' `cycle_stack`, `t<train>:<g>` exemplar keys and `chain.py`'s `required`; MSE's curves and the windowset
  summary/warnings; cluster's −1; decision 1's cancellation; calibration measurements; the readout session's `api.ts`
  on its base; the scratch-copy build pattern (a junction only to `node_modules`, removed with `cmd /c rmdir` first).
- 03:47 — **MPdist read-out** (`eval3/eval_mpdist.py`; `motif_edge` is empty, so the brief's fallback: the five
  largest families of the stored Ward g-05 whose medoid MPdist can compare, members against their medoid; all
  distances on one footing, √(1 − r); nulls: AR(1) φ 0.99 and random-walk pairs at the same lengths, and
  `mpdist_null`'s trend-kept context):

  | Family (members; medoid / member length median) | MPdist median [p10–p90] | Scale-invariant | Native length | Noise pairs (AR / RW median) | Below noise p10 | Refused |
  |---|---|---|---|---|---|---|
  | F-30 (79; 364 / 552) | 0.064 [0.014–0.22] | 0.064 | 0.63 | 0.53 / 0.50 | 100 % | 0 |
  | F-130 (55; 1,014 / 31) | **0.68** [0.18–0.73] | **0.13** | 0.70 | 0.51 / 0.51 | 27 % | 10 too short |
  | F-141 (51; 2,154 / 32) | 0.22 [0.13–0.28] | 0.15 | 0.27 | 0.49 / 0.44 | 100 % | 4 too short |
  | F-01 (49; 1,312 / 1,317) | 0.19 [0.11–0.42] | 0.14 | 0.58 | 0.65 / 0.54 | 91 % | 1 too short |
  | F-88 (43; 24 / 34) | 0.22 [0.12–0.36] | 0.20 | 0.77 | 0.53 / 0.51 | 90 % | 0 |

  Plainly: where a family's members share their duration with the medoid, MPdist agrees with the scale-invariant
  distance and both sit far below noise, while the native-length control (sample for sample from the start) reads
  large — MPdist does not count a shifted start or extra baseline. Where the members are ~30× shorter than the
  medoid (F-130), MPdist reads at noise level while the scale-invariant distance calls them close: the family is
  held together **only after stretching** — RQ3's own question, now visible per family. Refusals at real lengths:
  15 of 271 pairs (members under 16 samples).
- 03:4x — **`event_families` per-family verdicts under the new null** (`eval3/eval_families3.py`, the experimental
  template as shipped): **rec 6** — 2 families (53, 13), both confident, passed by both nulls (quiet-stretch ratios
  0.03× and 0.01×), coherence beyond noise (σ² 0.02 vs 0.30 / 0.32; eq. 17 0.30 vs 0.73, 0.35 vs 0.74) — unchanged
  from wave 2; **rec 542** — 2 families (131, 11), both confident **by the trend-kept null only** (quiet-stretch
  0.79× and 1.20×: the chain's own quiet stretches crowd as tightly as the families), and the 131-member family's
  coherence is still not beyond noise (eq. 17 0.82 vs 0.81) — **unchanged from wave 2: the quiet null does not rescue
  rec 542's large family**; its "smooth-shape blind spot" was not the trend-kept null's alone; **rec 543** — no
  family (175 windows, none in a dense crowd), so nothing to judge. No family changed verdict.
- 03:56 — **the Library table under the new null** (`eval3/eval_library3.py`, the grouping job's own items and loader
  — `_grouping_items`, `_library_background`, `run_grouping(..., background=)` — and the Family page's
  `_family_coherence(conn, n_set=3,616)` per family):

  | Method | Families | Placed | Noise-like, either null (trend-kept alone) | Passed by: both / quiet only / trend only / none | Coherence beyond noise, either (trend alone) | eq. 17 median |
  |---|---|---|---|---|---|---|
  | Ward (cut 0.6, min 10, omit 0.5) | 151 | 3,296 | not tested | — | 116 of 151 (116) | 0.568 |
  | HDBSCAN eom | 19 | 687 | **1 (3)** | 14 / 2 / 2 / 1 | 19 of 19 (19) | 0.337 |
  | HDBSCAN leaf | 23 | 582 | **0 (2)** | 17 / 2 / 4 / 0 | 23 of 23 (23) | 0.317 |
  | k-Shape k = 20 | 20 | **2,701** (915 past cut) | **11 (17)** | 3 / 6 / 0 / 11 | 19 of 20 (19) | 0.492 |

  Against wave 2's table: HDBSCAN flagged 3 of 19 noise-like then (trend-kept) and 1 now — two families rescued by the
  quiet stretches; leaf 2 → 0; k-Shape placed 1,996 then (plain-phase `omit_d`) and 2,701 now (the quiet windows' p05
  as its cut), with 11 of 20 noise-like (8 under the plain phase null; 17 if the trend-kept null judged alone — the
  quiet stretches rescue 6). The coherence verdict moved for **no** family: every family beyond noise by the quiet
  null was also beyond by the trend-kept one. **Analyse offers k-Shape again** in `interrogation.event_families`
  (`EVENT_FAMILIES_EXCLUDED` emptied; no unmarked Intervals key in the critic's 37 no-structure runs).
- 04:00 — the species run finished its plain-phase draws: 0.350–0.363 (5 draws, p's floor 1/6), all below the real
  0.428. The peer sessions are gone from `ListAgents` (no one left to coordinate the gate with; checked again before
  it). RQ3 updated and committed (`9e1502e`); `W3-evaluation.md` drafted (`ef701ea`).
- 04:35 — **W3-F reported** (red `027561d` → green `d1dc46c`; 298 conda + 258 / 615 venv; `tsc -b` / `npm run build`
  clean in a scratch copy) → `W3-F-ui.md`: in-step cancel and progress through `run_kwargs` (window matrix now raises
  `RecipeCancelled` instead of returning a partial table the executor cached as whole); every `block_cost` model
  calibrated in a background thread on first need (≤ 10 s wait, then "calibrating"; rupture's calibration takes
  **447 s** — filed as a separate task chip), the estimator's own words instead of "uncalibrated"; the sandbox now
  redirects block_cost's calibration file into its runtime (it would have written the checkout's
  `DATA/db/block_calibration.json`); MSE curves, the cycle stack, pan row labels + per-length verdicts (built on
  W3-C's `925056a` form), the wavelet transform's rows labelled in Hz; σ²-first and MPdist on the Library pages; 9
  smoke states (the pan two need W3-C); the event-loop warning fixed; the CWT scalogram skipped. Out of its list:
  `store.ts`, `useValidation.ts`, `InsertStageModal.tsx`, `runtime.py`, `Working/block_cost.py`,
  `Adapters/preprocessing_window_matrix.py`. 04:39 — critic launched (row 12), seven questions.
- 04:40 — **W3-C fix round 1 reported** (merged main `56a23f4`: adapter count 57, all `COSTED` lines kept, end_to_end
  57; red `85951ea` → green `617edc2`; 44 + 257 tests) → `W3-C-pan-matrix-profile.fix1.md`: AAFT null by default
  (exp(AR) 0/10 suggestions); 3 null draws and a cut rising from 6 (≥ 24 windows) to 8.5 (14 windows) — 0 of 150
  no-structure spans suggest, planted 5/6 within a rung (`MIN_WINDOWS` 20 would have cost the 20 min motif);
  `cleared_s` band, with the strongest gap kept as the suggestion — of three rules it lands within a rung of the
  planted scale most often (20/38 vs 16 and 15; "shortest cleared" gave 30 s on every 90 s-motif span) — and its bias
  stated on the face; stalls → long gaps; scrump removed; no null draws on unjudgeable lengths; `reason_code` per
  length. 04:41 — focused re-critique sent (row 8a).
- 04:4x — primary sources: dated notes on SigClust's sparse-HDLSS premise (W3-B critic), the √t number re-tested, and
  MPdist's k (W3-D critic) (`e3df8f9`).
- 05:00 — **W3-F critic: merge after fixes.** In-step cancel works through the real bridge path for MSE, cycle shapes
  and window matrix (job *cancelled*, no cache for the stopped step, earlier steps kept); background calibration is
  single-threaded per ask and a sandbox never writes the checkout's calibration file; the drawings read every verdict
  as given. **Blocker:** a cancel during a null draw leaves the half-finished draw unlinked
  (`surrogate_of_run_id` NULL), so its detections count as real (95 "real" detections where the run found 82).
  Should-fix: the cancel smoke state races (the MSE step lasts 1.35 s); an in-step cancel reads "failed" in History
  (the stored text does not start with "Cancelled"); one slow calibration holds every other; a run from the block
  page is not held while calibrating. 05:01 — fix round 1 sent (row 11a), decision 25, with W3-C's `617edc2` to merge
  for the pan view.
- 05:1x — **W3-C re-critique: merge after fixes, no blocker** → `W3-C-pan-matrix-profile.critic2.md`. The AAFT null
  holds (exp(AR) 0/10); false suggestions at the defaults ~0.9 % (2 of 236 spans at 2, 4 and 8 h, against 1.2–5.8 %
  before); the rising cut costs no power at the 976 s rung (10/10, gaps 9.4–17.0 against a cut of 8.31 — three
  within ~1.3). Should-fix: (1) the stall rule never fires through the template — the 2 h detrend turns a held value
  into a gentle curve, so a raw 3–20 min flatline still gives a confident suggestion (`n_stalled` 0 in all four
  cases); (2) stalls share `max_fill_s` (5 s) and blank real slow signal fed straight in (24.7 % at an ADC step of
  ~1/5 SD); (3) the summary line still says "suggested", and on new seeds the suggestion lands within a rung of either
  planted motif in 2/10, while the cleared band covers every judged rung in 8/10 — only the picture localises. On
  FLUSS: feed it nothing from this block at 8 h (a chain's ~30 min unit is beyond the 34 min judged reach there or at
  its edge); re-run on ≥ 24 h at the band's top beside 300 s, declared first, or record "pan gave no event-scale
  window". Fix round 2 (the last) sent (row 3b) on all three; the FLUSS piece declared now (decision 26), before any
  pan or FLUSS data.
- 05:2x — **W3-F fix round 1 reported** (merged W3-C's `617edc2` cleanly as `f42dd35`; red `ff5bc21` → green
  `ea59ee6`; conda 324 passed / 7 skipped, venv 167; `tsc -b` and `npm run build` clean in a scratch copy; smoke not
  run) → `W3-F-ui.fix1.md`. The blocker: `execution.py` attaches the stopped run's id to `RecipeCancelled`, and
  `draw_paired_null` links the half-finished draw (`surrogate_of_run_id`) before stopping; `null_summary` counts
  completed draws only. History stores "Cancelled[: <block's words>]"; the run route answers 409 while calibrating;
  one thread per model, the file lock only around read-merge-write; the cancel smoke state zooms out 13× with 3 h
  windows (14.9 s on a synthetic 389 h walk); the pan view leads with `cleared_s` and shows each length's cut and
  `reason_code`. Left open, by its own account: three readers still count every linked null run, finished or not
  (`scoreboard._null_runs`, `matching.py` ~1309, `library.py` ~1709). 05:28 — re-critique sent (row 12a), those
  three readers in its scope; they go to the fixer's second (last) round with its findings.
- ~05:4x — **the API session limit stopped the W3-C fixer (row 3b) and the W3-F re-critic (row 12a)** mid-task. W3-C
  had its red tests committed (`87f4ffc`) and the code uncommitted, with one test still failing: a raw 20 min hold
  through the template's detrend is now counted as stalled, but 976 s still cleared (gap 11.1). 07:02 — both resumed.
  The fixer was told to settle that failure by comparing against the same span with the hold blanked: if the blanked
  twin clears too, the clearance is the background's and the test pins "a stall behaves like a gap"; otherwise the
  detrend's reach around a hold becomes part of the stall.
- 07:04 — **W3-F re-critique: merge after fixes; the blocker holds** → `W3-F-ui.critic2.md`. Through `RunManager`,
  a cancel during draw 3 left real detections at exactly the real run's 82 (95 in round 0); the half-finished draw is
  `failed`, linked, "Cancelled: …". Cancel text, 409 while calibrating (no job, run row or lock left half-made),
  per-model calibration (a fast model waited 0.02 s behind a slow one; 15 of 15 keys kept when 12 finished at once;
  one timing for 5 concurrent asks) and the cancel smoke state (about 15 s on screen, from the code) all hold.
  Should-fix: (1) three readers count the half-finished draw — on the same run Analyse says 2 draws / null expects
  34.5 and the Discovery scoreboard 3 / 30.33 (the null is understated, so "beats noise" is overstated), and
  `export.py::_surrogate_block` can name the half-finished draw as "the surrogate control"; (2) a draw that *fails*
  mid-chain (a `RecipeExecutionError`) still leaves its row unlinked, its detections counted as real — older than
  W3-F, the blocker's twin; (3) the pan view still says "suggested" in its headline and table. Nit: the caveat is a
  copy of W3-C's. 07:05 — fix round 2 (the last) sent (row 11b), decision 27.
- 07:06 — **W3-C fix round 2 reported** (red `87f4ffc`: 7 failed, 1 passed → green `cd177d6` + `5a77f67`; 304 passed)
  → `W3-C-pan-matrix-profile.fix2.md`. Stalls are now found after the detrend by their second differences (a run of
  at least `stall_s`, default 60 s, a placeholder, where every one stays under 1 % of the span's 75th percentile —
  inside a detrended hold 3.7–5.1e-4, the flattest real 60 s never below 1.14); a raw 20 min hold gives `n_stalled`
  ≈ 1200. The failure left at the API stop was the background's: the same span with the hold blanked cleared 976 s
  too (gap 10.5 vs 11.1; seeds 12–15 cleared nothing either way), so the test now pins "a stall behaves like a gap",
  and a length is judged on its usable samples only. A quantised 1 Hz logger now loses 0–0.13 % (was 1.3–71 %). The
  summary and verdict say "strongest gap at C s (not an event length)"; `suggested_window_s` keeps its name. Its own
  risk: a genuinely smooth 60 s stretch would be counted stalled — read `n_stalled` on real recordings.
- 07:08 — dry run clean (9 files; adapter count 57 and end-to-end 57 carried by the branch); **W3-C merged as
  `e068669`**. 07:10 — the post-merge test set started (conda, `-n 3`), and the `motif_lengths` evaluation on the four
  declared spans, one sandbox per recording (`eval_pan.py --only <rid> --tag pan<rid>`). The real run is the template
  exactly; each draw is scored on the **image row** at the real run's strongest-gap length, which does not depend on
  the block's own null draws, so the draws run with `null_draws` 0 (picture only) — the script checks on every real run
  that the picture-only rows equal the full run's before it relies on that, else it runs the full template. No merge
  into main until the evaluation finishes; the FLUSS piece runs after W3-F's merge, on the merged main.
- 07:25 — **W3-F fix round 2 reported** (red `f102dee` → green `0de9e6e`; conda 213 + 277 passed, venv 206 passed,
  3 xpassed, 1 failed — the known Discovery scoreboard string on main; `tsc -b` / `npm run build` clean) →
  `W3-F-ui.fix2.md`. `queries.completed_null_draw(alias)` is the one rule, used by `null_summary`, the scoreboard,
  the Library scale read-out, the family null and the export (which now never names a stopped draw as the control);
  a draw that fails part-way is linked before the error is re-raised; the pan view reads "clears from A to B s ·
  strongest at C s — not an event length" and takes its caveat from the block's own rule text. The doubled
  "Cancelled: Cycle shapes cancelled." is left (no one-line fix keeps History's check). Decision 28: merges without a
  third critique.
- 07:27 — **`motif_lengths` evaluated → ships (2 of 3 chains).** At the real run's strongest-gap length, median
  normalised nearest-neighbour distance against 20 AAFT draws (picture-only rows identical to the full run's on all
  four spans): rec 6 400–408 h **0.018** vs 0.204–0.264 at 976 s (beats); rec 3 512–520 h **0.110** vs 0.280–0.319 at
  976 s (beats); rec 2 296–304 h 0.265 vs 0.142–0.151 at 30 s (**does not beat**, p 1.0, though its gap, 40.9, is the
  largest anywhere: its drops match closely, its typical window — quiet jitter between 13 drops — does not, while the
  AAFT copies spread the drops' slow swing evenly). The plain phase draws agree on every span. Supervisor's check, rec
  385: strongest gap at **30 s**, not ≈ 1 min (46 s and 72 s close behind), and 0.143 vs 0.209–0.216 beats. Every
  judged length cleared on all four spans (30–1508 s at 8 h, 30–976 s at 4 h), so the band picks no window; no stalls.
  07:30 — test-first into `CANONICAL`: red `c43e43c` (KeyError) → green `64b2995` (11 + 8 passed); the description
  gains one sentence on what the band did here. Found on the way: chain_cycles' shipped-template test failed when run
  alone (`server` not importable; 6f07cff passed only beside `test_templates`) — fixed by putting webui on its path
  (`eef63e7`).
- 07:34 — W3-C's post-merge set on `e068669`: **304 passed** (25 min at `-n 3` beside the evaluation). W3-F dry run
  clean (35 files) → **W3-F merged as `8186e97`**. 07:35 — the FLUSS piece started on the merged main (decision 26,
  8 numba threads, its own sandbox). No bridge listens on 87xx (the researcher's 8765 is down), but the gate's client
  build goes to a private directory all the same (`vite build --outDir <scratch>/dist_w3gate`), served to my sandbox
  bridge with `--dist`: `npx tsc -b` exit 0, the build exit 0. The UI tests with the venv python started beside the
  FLUSS run; the conda `pytest -n 4` waits for FLUSS to finish (the timing tests fail under load), the smoke for
  pytest.
- 07:49 — **the FLUSS piece (decision 26), report only.** `motif_lengths` on rec 6 400–424 h cleared 30–2330 s (11 of
  12; 3600 s gap 5.5 vs cut 6.0), strongest gap 30 s; so FLUSS ran on 370–470 h at **2330 s** (detrend 4660 s) and at
  300 s. 2330 s: changes at 424.9 h and 421.7 h (arc-curve 0.29, 0.31), mid-chain, 20–23 h from the 383/445 h edges;
  300 s: 469.5 h and 469.1 h (0.53, 0.54), at the span's end. Neither finds the chain. `estimate_seconds` was None
  (uncalibrated in a fresh sandbox); actual 516 + 144 + 129 s. Aside, one span only: the band's top (39 min) is the
  first rung above rec 6's median cycle (37 min).
  **Correction, 07:5x (read from the retest's own script and output, `fluss_known.py` / `fluss_known_w300.json` in
  the "Agent manager setup" session's scratchpad):** the 2026-10-14 retest ran rec 6 on **372–456 h**, not 370–470 h
  as decision 26 says, with the same readout (`regime_locs`); its 455.5 h and 372.5 h are each ~0.5 h inside that
  span's ends, as 469.5 h is inside this one's. So at 300 s FLUSS's strongest changes follow the span's ends — an edge
  effect seen twice — and the piece ran on 370–470 h as declared.
- 08:03 — **the UI tests with the venv python on `8186e97`: 617 passed, 3 xpassed, 3 failed** (26 min at `-n 3`
  beside the FLUSS piece): the known Discovery scoreboard string (fails on main before wave 3; task chip) and two
  route tests, `test_detections_of_a_spanned_run_are_channel_absolute` and `test_runs_methods_and_coverage_filters`
  (`KeyError: 'job_id'`) — W3-F's 409 holding a rupture run while its ~447 s calibration runs in the fresh sandbox
  (the fixer's own venv run had not included `test_webui_routes`). Decision 29: the fixture seeds rupture's entry in
  its sandbox (`637b3d5`; both pass; nothing reached `DATA/db`), and the 409 says how long (`caa2ad0`;
  `test_webui_run_routing` 22 passed). 08:06 — a peer session ("Fix drop detector mV/s on mV-stored recordings",
  branch `claude/awesome-cori-5e53bd`) asked to run its gate; told to wait for mine (pytest, then the smoke walk,
  ~09:30) and to merge main first — its files overlap W3-F's (`execution.py`, `chain.py`, `runs.py`,
  `serialize.py`). 08:07 — **the gate's `pytest -n 4` started on `caa2ad0`** (conda).
- 11:11 — **the gate's pytest on `caa2ad0`: 3877 passed, 42 skipped, 1 failed** — in **3 h 03 min** (the machine
  loaded: ~0.7 GB RAM free, the researcher's controller software, Word). The failure,
  `test_side_inputs::test_execute_recipe_raises_naming_the_binding_when_unresolved`, is real and W3-F's: its
  assertions pass, but cleanup hits WinError 32 (its `.npy` still open), reproducibly alone. W3-F fix round 2 built
  the `RecipeExecutionError` in a local, which with the traceback forms a reference cycle keeping the failing frame
  and its memory-mapped recording alive until the next garbage collection. Fixed by passing `run_id` to the
  constructor (`96c9e8f`; the five execution / null-draw files 62 passed, 1 skipped, conda; 16 passed, venv). Every
  other test passed: against wave 2's gate (3353 / 0 failed) the failure set is otherwise empty. The peer that was
  waiting had left by then (`ListAgents` empty; its inbox stale), so the smoke walk runs alone. 11:15 — my sandbox
  bridge up on **8794** (database copy `webui/runtime/20261015-111453/`, the private client build), the full smoke
  walk started.
- 03:5x — **W3-C critic: merge after fixes, three blockers.** F1: plain phase surrogates are biased here too
  (exp(AR) noise got a suggestion 10/10; AAFT 1/10 → 0/10 at 20 draws, keeping planted-motif power) → the 03:55
  correction; F2: one null draw gives 1.2–5.8 % false suggestions at 1 Hz, three gave 0 in 544 spans, the false
  alarms gathering at the longest judged rung; F3: `suggested_window_s` is not the event's scale — a 90 s motif got
  264–976 s (never within a rung), 60 s spikes 30–976 s, drop chains their 30–72 s fall edge; should-fix: a flatline
  gives a confident false suggestion (F4), scrump's global-RNG lock races (F5), null profiles for unjudgeable lengths
  (F6). Cost within 2× everywhere (8 h × 20 draws ≈ 7–8 min at 4 threads). 03:53 — fix round 1 sent (row 3a),
  decisions 21–24, after merging main.

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
15. **A family is confident when it passes EITHER null** — the quiet-stretch null (selection-matched) or the
    trend-kept null (0.9) — and coherence's `beyond_noise` likewise; `null_kind` / `why` name the null(s) passed with
    both ratios. Reason: their blind spots are opposite and measured (trend-kept: smooth window-filling shapes; quiet:
    sharp families on recordings whose quiet stretches hold uncatalogued events of the same shape), and each null's
    size on pure noise is small, so the union's is too. Detections stay un-avoided (they cover most of a recording);
    the share of quiet windows overlapping a detection is reported per family.
16. **The quiet-stretch margin is 0.6, not 0.7** (W3-G critic F5: densest 10-member noise families reached 0.714
    clean and 0.643 with uncatalogued events; real families at 10 % noise scored 0.13–0.39, so 0.6 costs no power
    measured).
17. **Cycle shapes checks the background's colour against a per-cycle phase null on σ²**: when the stack beats the
    background but not that null, `background_colour_mismatch` is set, said in the summary, and the groups are keyed
    `~untested`. eq. 17 never judges against the phase null (real chains fail it 4 of 9). Reason: the re-critique's
    S-A — quiet margins of another colour made chain-timed noise read "beyond noise" every time.
18. **A cycle group's key is unmarked only when eq. 17 AND σ² both beat the background null** (refines decision 2:
    eq. 17 stays in the verdict and σ² is added, so it is never looser). Reason: the one stationary false pass in 76
    passed eq. 17 but not σ²; it is also the evaluation's own rule.
19. **W3-B merges after its second (last) fix round without a third critique.** Reason: the re-critique's verdict
    was "merge after fixes" with two should-fixes and no blocker; both are done test-first with before → after
    measurements; the one new behaviour (a conservative `~untested` on a slow-drift background at 30 % noise) can
    only withhold a verdict, never give a false one. The real-recording evaluation reads the block's own `tested`,
    `fallback_share` and `background_colour_mismatch` before any number.
20. **W3-F starts from main without W3-C**, and W3-C's final branch is merged into it as a follow-up (as wave 2's
    W2-F took W2-E's families). Reason: W3-C's critic has run 3 h (an API-limit stop included); W3-F's other ten
    items need only what is merged, and the pan rows (item 5) read a payload whose form is in W3-C's report.
21. **Pan matrix profile's null is AAFT** (a `null` parameter, `aaft` default, `phase` kept for comparison), and the
    evaluation's draws are AAFT (the 03:55 correction). Reason: the critic's exp(AR) case — the same flaw W3-A's
    critic found.
22. **`null_draws` defaults to 3**, with the longest-rung false alarms handled by a larger `MIN_WINDOWS` or a cut
    that grows near it (the fixer's measurement decides). Reason: 1 draw gave 1–7 % false suggestions; 3 gave 0 in
    544 spans at 1 Hz for twice the cost.
23. **`suggested_window_s` is chosen by measurement on the critic's power cases** (strongest gap vs shortest cleared
    within a fraction of the best vs shortest cleared), and the cleared band is reported beside it. Reason: the
    strongest gap leaned to the longest judged window (a 90 s motif → 264–976 s); the brief's FLUSS re-run needs a
    length that means the event's scale.
24. **Pan matrix profile drops `percentage` < 1 (scrump).** Reason: its global-RNG save/restore races with other
    threads (20/20 runs differed beside another `np.random` user) and it saved only ~20 %. MiniRocket's own
    global-RNG use is older and left as a follow-up.
25. **W3-F's fixer gets the core files its blocker lives in** (`Working/run_groups.py::draw_paired_null`,
    `Working/execution.py`'s cancellation record) and `webui/server/app.py`'s run route (refuse 409 while calibrating),
    beyond its Deliver list. Reason: the leak and the History status are core / route behaviour that only appeared
    because W3-F made null draws cancellable mid-step; fixing them where they live covers every entry point.
26. **The FLUSS re-run reads pan's cleared band, never `suggested_window_s`, and runs on a span long enough to judge a
    chain's unit** — fixed at 05:2x, before any pan or FLUSS output on real data. Pan (the `motif_lengths` template as
    merged, its defaults) runs once on rec 6 **400–424 h** (24 h inside the chain's 383–445 h edges; every ladder
    length up to an hour judged). If any length clears, the experimental `fluss_regimes` runs on rec 6 **370–470 h**
    (the span of the 2026-10-14 known-span retest, whose 300 s run put the strongest changes at 372.5 h and 455.5 h)
    at the **longest cleared length** and at 300 s, side by side; the 300 s twin is the template exactly, and the long
    window keeps the template's own 2 : 1 ratio of detrend to window (a 600 s rolling mean would remove the scale a
    longer window is meant to see), every other setting unchanged; reported: each run's strongest changes
    (`regime_locs`, the paper's readout) and their distance (h) to 383 h and 445 h. `estimate_seconds` first, and the whole piece capped
    at about an hour of compute (cut the 300 s twin first if the estimate overruns; its answer is on file). If nothing clears, FLUSS is not run and the evaluation records
    "pan gave no event-scale window on rec 6". Report only — FLUSS's status changes only by the Q4 bar. Reason: W3-C's
    re-critique (F3) — the suggestion leans to the longest judged rung or a chain's fall edge, so it is not an event
    length; the band's top is the only reading that tracked a chain unit (1508 s on random-walk drops at SNR 5), and an
    8 h span judges only up to 34 min.
27. **W3-F's last fix round gets every reader of null draws**: one shared rule for "a completed null draw" in
    `Working/database/queries.py` (beside `not_surrogate`), used by `scoreboard._null_runs`, `matching.py`'s null
    counts, `library.py::_family_null`, `run_groups.null_summary` and `export.py::_surrogate_block`; and a draw that
    fails mid-chain is linked before the failure is re-raised. Reason: the re-critique measured Analyse and the
    Discovery scoreboard disagreeing on the same run once a draw is cancelled, which W3-F made possible mid-step; one
    rule in one place keeps every page on the same null. No wave-3 branch in flight touches these files (W3-D's and
    W3-G's edits to `library.py` are merged).
28. **W3-F merges after its second (last) fix round without a third critique** (as W3-B, decision 19). Reason: the
    re-critique found the blocker fixed on every path and left three should-fixes and a nit, no blocker; each is done
    test-first with before → after numbers on the critic's own case (Analyse and the scoreboard both 2 draws / 34.5; a
    failed draw linked, real detections at the real run's count); the one behaviour added — only finished draws count
    — can only make a null larger, never a real count. The gate (full pytest, the client build, the smoke walk on my
    sandbox bridge) checks the merged whole.
29. **The 409 while a cost model is being timed stays; its words say how long, and the route tests start from a
    calibrated rupture.** The gate's UI run found two route tests failing on `8186e97` (`KeyError: 'job_id'`): in a
    fresh sandbox a rupture run is refused until rupture's model is timed, and that takes ~447 s (Pelt on the
    calibration's 20,000-sample walk). Starting such a run blind instead would undo why runs are routed before they
    start — a rupture step cannot be stopped inside the step, and a days-long FLUSS had to be killed by hand on
    2026-10-14 — so the hold stays: the message now says "once per machine; most take seconds, rupture about 7
    minutes" instead of "a few seconds" (`caa2ad0`), and the route tests seed rupture's entry in their own sandbox's
    calibration file (`637b3d5`), as a machine calibrated once has it. The root fix is the rupture-calibration task
    chip (time it in seconds, not minutes). Neither smoke walk nor any smoke state runs rupture.
3. **The Library side of decision 4 is folded into round 2**: W3-G puts σ² first in `shape_families`' summary lines and
   the coherence payload it returns, and measures both variants' verdicts against the quiet-stretch null (the verdict
   stays on eq. 17 unless the researcher moves it); W3-F puts σ² first on the Family page and the families table.
