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

## Events (chronological)

- 2026-10-14 21:2x — manager session started; read the brief, `00-common.md`, `critic.md`, `README.md`, W3-A/B/C/D/F/G,
  W1/W2 evaluations, the W2 ledger and critics, the plan's §4 A1–A2, §5 row 11, §6, §7, §8 and primary sources §1, §2,
  §4, §13b. Preflight above.

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
3. **The Library side of decision 4 is folded into round 2**: W3-G puts σ² first in `shape_families`' summary lines and
   the coherence payload it returns, and measures both variants' verdicts against the quiet-stretch null (the verdict
   stays on eq. 17 unless the researcher moves it); W3-F puts σ² first on the Family page and the families table.
