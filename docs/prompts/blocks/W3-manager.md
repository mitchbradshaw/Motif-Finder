# W3 — Manager brief: build, critique, merge and evaluate wave 3

You are the **managing session** for wave 3 of the blocks-from-the-literature plan, run in the **main checkout**
(`C:\Users\mmebr\Documents\CNN`, branch `main`). You do not write the blocks yourself: you launch implementer sub-agents,
launch critic sub-agents on their branches, run fix rounds, merge, integrate, run the gate, evaluate the templates on
**real recordings**, and report to the researcher. Waves 1 and 2 were run exactly this way; their record is in
`docs/prompts/blocks/reports/` — read `W1-evaluation.md`, `W2-evaluation.md`, `W2-ledger.md` (every event and every
decision the wave-2 manager took) and the wave-2 `*.critic.md` files before you start.

Wave 3 is **exploratory** (plan §7.1). The researcher's priority until 21 October is a polished, reliable Pipeline UI
(`CLAUDE.md`): wave 3 must not slow that work. Its blocks touch `Working/`, `Adapters/`, `tests/` and templates; only
W3-F touches `webui/`, and only the files its prompt names.

The researcher may be away while you run. **Do not stop to ask** unless a decision is irreversible or outside this
brief; make the defensible call, write it in the ledger and in the final report.

## Read first

- `CLAUDE.md` — the non-negotiable rules, "Talking to the researcher" (plain language first, then options, then a
  recommendation), the UI gate, and **never point pytest, a bridge or an adapter at a junction to the real `DATA/`;
  unlink any junction before removing a worktree**.
- `docs/prompts/blocks/README.md`, `00-common.md` (both "Lessons" sections), `critic.md`, and the five wave-3 prompts
  you run: `W3-A`, `W3-B`, `W3-C`, `W3-D`, `W3-F`. **`W3-E` (wavelet features) is not run in this wave** — of the
  plan's two optional blocks the researcher chose MPdist only (2026-10-14); its prompt stays on file for later.
- `docs/research/analysis-blocks-from-literature.md` §4 A1–A2, §5 row 11, §6 (MPdist), §7, §8 (the researcher's
  decisions — above all Q4: **a template ships only if it beats its random-data null** on real recordings; it need not
  beat the drop detector), and `analysis-blocks-primary-sources.md` §1, §2, §4, §13b.
- `docs/prompts/blocks/reports/W1-retest-known-spans.md` if present (W3-B's prompt carries its numbers either way).

## Preflight (before any launch; write each answer in the ledger)

1. **Is wave 2 finished?** `git log` on `main`: W2-A…F merged, `W2-evaluation.md` filed. W3-B imports W2-B's
   `Working/library/coherence.py` and SBD functions — **if W2-B is not on `main`, hold W3-B** and launch A and C alone.
2. **What wave 2 shipped.** From `W2-evaluation.md`: which wave-2 templates are in `CANONICAL` and which in
   `EXPERIMENTAL`; the gate's pytest failure set and smoke failure set (your baseline). If `event_families` shipped with
   a detector other than `noise_threshold`, tell W3-B in its launch message which one, and why.
3. **Open items the wave-3 prompts assume are open** — check each, and strike the matching W3-F item if done:
   `webui/server/chain.py::route_local` calibrates only the matrix-profile model (W3-F item 2);
   `webui/server/runs.py` passes no `run_kwargs` (W3-F item 1).
4. **The detrend NaN fix** (`claude/magical-euler-829723`, 2026-10-14): merged or not
   (`git log --oneline -- Working/Preprocessing/detrend.py`). W3-A's gap handling and the templates' descriptions depend
   on it.
5. **Peers.** `ListAgents`: who else is live on this machine (the researcher's polish sessions, a wave-2 tail). Agree
   with each, by message, who runs `pytest -n` and smoke when, and which ports: **8765 is the researcher's `--project`
   bridge on the real database — never yours**; wave 2 used 8791, earlier sessions 8792–8793; take **8794**. Warn any
   polish session before W3-F merges into files it may be editing (`api.ts`, `registry.tsx`, the run panel,
   `runs.py`).
6. **Commit the wave-3 prompts** if they are not committed, and note the commit as round 1's base.

## Standing rules for every sub-agent

- `Agent` tool, `subagent_type: "general-purpose"`, **`model: "opus"`, `effort: "medium"`** — never Fable (the
  researcher's standing instruction, memory `subagent-model-policy`).
- Implementers and fixers: **`isolation: "worktree"`**. **The tool cuts the worktree from `origin/main`, which lags
  local `main`** (wave 2's four worktrees landed 52 commits behind, with no wave-1 blocks and no prompts). Every launch
  message names the base commit and says: *"First run `git log -1 --oneline`; if it is not `<base>`, run
  `git merge --ff-only <base>`, check again, then start."* Confirm with `git -C <worktree> log -1` within a few minutes.
- Critics: **no worktree**; they read the implementer's worktree and never edit it (`critic.md`).
- Sub-agents return their report as their final message; **you** file it verbatim as
  `docs/prompts/blocks/reports/W3-<X>-<name>.md` (implementer), `.critic.md`, `.fix<n>.md`, with a one-line header saying
  who filed it and when. A report sometimes arrives twice: check the branch has not moved, then ignore the copy.
- A launch message is short: the prompt path, `00-common.md`, the commit prefix, the base commit and the fast-forward
  instruction, (critics) the worktree path and branch, and any preflight finding that changes the prompt. Point at the
  committed prompt; never paste it.
- Tests that import FastAPI skip under the conda python; run them with
  `webui/.venv/Scripts/python.exe -m pytest <files> -q -p no:cacheprovider` (wave 2 nearly missed W2-B's family-detail
  tests this way).

## The ledger (first, and after every event)

`docs/prompts/blocks/reports/W3-ledger.md`, in `W2-ledger.md`'s shape: one row per agent (role, block, agent id,
worktree, branch, base, status: launched / reported / critic verdict / fix round n / merged as `<hash>`), a dated event
log, and every decision taken on the researcher's behalf with its reason. Take times from `date`, never guess them. A
resumed session reads the ledger and carries on: an interrupted implementer is resumed with `SendMessage` to its id if
alive, else relaunched **in its existing worktree** (told to read `git log` there and continue).

## The sequence

**Round 1 (parallel):** W3-A multiscale entropy · W3-B cycle shapes (if preflight 1 allows) · W3-C pan matrix profile.
**Round 2 (after round 1 is merged):** W3-F UI and W3-D MPdist, in parallel (the researcher chose MPdist, 2026-10-14;
W3-E is not run). W3-F can start once A–C are merged; tell it to leave anything MPdist needs on the Family page for a
short follow-up if D lands after it.

Expect, from wave 2: implementers 40–110 min, critics 15–25 min, fix rounds 15–30 min; every block so far needed a fix
round, and timings measured while other agents run read slow (judge ratios, not absolute seconds).

For each block:
1. Launch the implementer. When it reports, file the report, update the ledger.
2. Launch a critic on its branch (`critic.md` + the block's prompt), with your own questions from reading the report —
   wave 2's critics answered every manager question they were given, and those answers drove the fixes.
3. **`merge after fixes` or `do not merge`:** launch a fixer in the **same worktree** (or `SendMessage` the implementer
   if alive) with the critic report's path: fix every blocker and should-fix, test-first for each (a failing test, then
   the fix), report what changed. When you settle a disputed point for them, number it as a decision in the ledger and
   name it in the fix message. Re-critique the changed parts when a blocker was behavioural. At most two fix rounds;
   then merge as experimental with the open finding in the block's description, or do not merge — and say which.
4. **Merge** into `main` one branch at a time, `git merge --no-ff <branch>`, never while a peer's `pytest` or smoke runs
   from the main checkout. A dry run (`git merge --no-commit --no-ff <branch>`, then `git merge --abort`) predicts
   conflicts. Expected ones: the adapter-count asserts in `tests/test_adapter_spec.py` and `tests/test_end_to_end.py`
   (set the true count from `discover_adapters()`, keep both comments, never a duplicated assert) and neighbouring
   `COSTED` lines in `tests/test_block_standard.py`. A hunk two branches need identically can be shared with
   `git show <commit> -- <file> | git apply` so both merge cleanly (wave 2 did this for `Working/block_cost.py`). After
   each merge run the block's tests plus `tests/test_block_standard.py tests/test_adapter_spec.py
   tests/test_import_boundaries.py tests/test_templates.py tests/test_end_to_end.py` (conda python, `PYTHONIOENCODING=utf-8`).

## Integration (yours, after the merges; W3-F does the UI files)

- `webui/server/templates.py`: move a template constant from its test into `CANONICAL` **only once it has passed the
  evaluation below**; one that fails goes into `EXPERIMENTAL` and its block's description starts "EXPERIMENTAL: …" with
  the reason and a pointer to `W3-evaluation.md`. Each template test gains
  `test_the_shipped_template_is_the_one_tested_here` (`canonical(name) == TEMPLATE`, or `experimental(name)`).
- `tests/test_block_standard.py` `COSTED`: every block that declares a cost.
- `docs/research/analysis-blocks-primary-sources.md`: correct any fact an implementer or critic found wrong there (as
  wave 2 corrected snippets' knee rule), dated and attributed.
- RQ and round-B files: `docs/rq_roundA/RQ3` if MPdist lands (the rule is in `docs/rq_roundA/README.md`); a log line in
  `docs/rq_roundB/README.md` for what wave 3 makes possible — conditions and organisms (MSE), motif trains and the
  sharkfin plateau (cycle shapes), the window choice behind the spiking-families scale (pan matrix profile).

## Evaluation on real recordings (the researcher's bar, Q4)

Run in a **sandbox** runtime, never the real database: `server.runtime.Runtime("sandbox", runtime_root=<your scratch
dir>).setup()` … `.restore()` (`webui/server/runtime.py`). `Working.run_groups.run_paired_recipe(recipe,
db_path=rt.db_path, force=True, surrogate=True, surrogate_draws=20)` gives the real run plus 20 phase-randomised draws.
Write scripts and their outputs to your scratch directory, not the repo root (`Runtime.setup()` chdirs to the repo root,
so relative output paths land there — wave 1 left `w1_null_*.json` files behind that way). A template **beats its null**
on a recording when its statistic beats every draw (p = 1/21 ≈ 0.048); it **ships** when it does so on at least 2 of 3
recordings. Read each block's own warnings as well as the statistic — wave 1's deconvolution "passed" while its warnings
said it was splitting events.

| Template | Real-data statistic | Null | Recordings |
|---|---|---|---|
| `complexity_fingerprint` (W3-A) | distance of the window-median MSE curve from the mean of the 20 surrogate curves, over scales defined in every run, against each draw's distance from the mean of the other 19 | the 20 surrogate draws | M2_aug rec 1 and rec 3, 440–464 h (wave 1's 24 h spans); *S. commune* rec 600 (all 73 h); rec 385 (4 h — expect "too few scales", which is itself a check) |
| `chain_cycles` (W3-B) | aligned SVD entropy of the stacked cycles (eq. 17 **and** squared) | **shape null:** the same real event times, cycles cut from phase-randomised copies — 20 draws (the block's own `null_draws`, or computed beside it); the surrogate run is a floor (≈ 0 events expected) | the known chains: M2_aug rec 3 490–540 h, rec 6 370–470 h, L_LM_Jul_26_J rec 542 or 543 370–490 h; rec 2 294–304 h (13 events — a "few cycles" case) |
| `motif_lengths` (W3-C) | at the suggested length, the real median normalised nearest-neighbour distance below every draw's | the 20 surrogate draws | rec 385 (4 h): does it suggest ~1 min, the supervisor's finding? M2_aug rec 2 296–304 h, rec 6 400–408 h, rec 3 512–520 h |

For `chain_cycles` the shape null is a floor real chains should clear easily; **the findings are K, the change points,
the order test and the floor fraction** (sharkfins on rec 2 against sharp drops on rec 3) — report them as findings,
with the block's own nulls beside them.

Three more pieces the researcher will want more than any synthetic number:

1. **Species and conditions (MSE).** Only *S. commune* (recs 600–606) is registered. The other three species are
   derived (`DATA/derived/channels/Cordyceps_militaris_fs1`, `Flammulina_velutipes_fs1`, `Omphalotus_nidiformis_fs1`,
   memory `adamatzky-four-species-dataset`): register them **in the sandbox copy only**, through the same code path
   Settings › Datasets uses. Fingerprint 2–3 channels per species plus M2_aug: does the dataset label separate on the
   MSE features (silhouette) better than on the same windows' surrogate features? Use as many draws as the cost allows
   and state p's floor.
2. **The √t check.** `complexity_fingerprint` on *S. commune* without the detrend step and with `r_scale="sd"`: does the
   preprint's "mean MSE 0.0028" collapse reproduce, and does the block's collapse guard fire? A plain yes/no with the
   numbers settles a published claim.
3. **The FLUSS window.** If `motif_lengths` suggests a window on a known chain, re-run the experimental `fluss_regimes`
   with it on that chain (rec 6: at 300 s its strongest changes sat 10 h outside the chain's 383–445 h edges). Report
   only — FLUSS's status changes only by the Q4 bar — and cap it at about an hour of compute (`estimate_seconds` first).

**MPdist (W3-D)** has no template, so no ship-or-not verdict: put it beside the scale-invariant distance and the
native-length control on accepted RQ3 pairs if the sandbox holds any (`motif_edge`), else on five families' members
against their medoids, with coloured-noise pairs as the null — and say in plain words what it adds to RQ3's read-out.

Write `docs/prompts/blocks/reports/W3-evaluation.md` in the wave-1/2 format: plain words first, a results table per
template, verdicts, the warnings you read, and what the researcher should decide.

## The gate (after all merges and integration)

1. `pytest -n 4` from the main checkout root (conda python): compare the **failure set** with `W2-evaluation.md`'s gate —
   nothing that passed may fail (a wall-clock test under load may flake: rerun it alone three times before calling it).
2. `npx tsc -b` and `npm run build` in `webui/client`.
3. Smoke on **your own sandbox bridge, port 8794**: `PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1
   "/c/ProgramData/anaconda3/python.exe" webui/run_server.py --port 8794 --sandbox` in the background, then
   `PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" webui/smoke.py --url http://127.0.0.1:8794`. Traps
   (memory `webui-smoke-gate-traps`): never while `pytest -n` runs or `dist` is being rebuilt; restart the bridge after
   any Python edit; finish on the **full** walk, and wait for smoke's summary line, not a non-empty log;
   `git checkout -- webui/screenshots` afterwards. Compare failure **sets** with wave 2's baseline, and require every
   wave-3 state to pass.
4. Stop your bridge.

## Finishing

- Commit on `main` with prefix `blocks-w3:` and the attribution line from your session, with explicit paths (other
  sessions share the index — stage only at commit time); **do not push**.
- Worktrees under `.claude/worktrees/`: leave them (none should hold a junction; if one does, `cmd /c rmdir` the
  junction first — `CLAUDE.md`).
- Update the memory file `literature-blocks-plan.md` and its line in `MEMORY.md`: what shipped, what is experimental,
  what is left of the plan.
- **Final message to the researcher:** plain words first (what each new block does, as to a newcomer), then the table
  of templates — shipped / experimental and the evidence — then the species table, the √t answer, the cycle findings,
  the gate, the decisions you took for them, and the questions only they can answer (each: plain explanation → options
  → recommendation). Point at `W3-evaluation.md` and the ledger.
