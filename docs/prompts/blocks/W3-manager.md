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
- `docs/prompts/blocks/README.md`, `00-common.md` (both "Lessons" sections), `critic.md`, and the six wave-3 prompts
  you run: `W3-A`, `W3-B`, `W3-C`, `W3-D`, `W3-F`, `W3-G`.
  - **`W3-E` (wavelet features) is not run in this wave.** Of the plan's two optional blocks the researcher chose MPdist
    only (2026-10-14); its prompt stays on file for later.
  - **`W3-G` (the fairer noise test for families) was added by the researcher** from wave 2's follow-ups (2026-10-14,
    `W2-evaluation.md` question 5 (a)). The other follow-ups were not chosen: snippets' chooser, the `event_families`
    re-test, and MiniRocket in Models.
- `docs/research/analysis-blocks-from-literature.md` §4 A1–A2, §5 row 11, §6 (MPdist), §7, §8 (the researcher's
  decisions — above all Q4: **a template ships only if it beats its random-data null** on real recordings; it need not
  beat the drop detector), and `analysis-blocks-primary-sources.md` §1, §2, §4, §13b.
- `docs/prompts/blocks/reports/W1-retest-known-spans.md` if present (W3-B's prompt carries its numbers either way).

## Preflight (before any launch; write each answer in the ledger)

The prompts were checked against `main` at `1019cf6` on 2026-10-14, after wave 2's gate. That check found:
- **Wave 2 is finished**: all six branches merged, `W2-evaluation.md` filed.
- **What shipped**: `minirocket_manual_labels`. **Experimental**: `event_clusters`, `recording_snippets` and
  `event_families`.
- **Still open**: `route_local` calibrates only the matrix-profile model, and `runs.py` passes no `run_kwargs`. Both
  are W3-F's.
- **Merged**: the NaN-aware detrend (`e4a5373`) and the gap-skipping drop detector (`1019cf6`).

Re-check only what may have moved since:

1. **New commits on `main` since `1019cf6`**: `git log 1019cf6..main`. If one touches a file a prompt names
   (`Working/library/coherence.py`, `Working/library/grouping/methods/kshape.py`, `Working/interrogation/intervals.py`,
   `webui/server/chain.py`, `webui/server/runs.py`, `webui/server/serialize.py`, `Working/Detection/matrix_profiling/`),
   tell the affected agent what changed, in its launch message.
2. **The gate baseline**: the latest gate recorded on `main`.
   - pytest: the drop-NaN session's gate on `1019cf6`, 3529 passed, 0 failed (2026-10-14).
   - Smoke: `W2-evaluation.md`'s 25 failures, all on pages wave 2 did not touch, unless a later smoke run was recorded.
   - Their failure **sets** are your baseline.
3. **The researcher's wave-2 questions** (`W2-evaluation.md`, "What the researcher should decide"). Note any answer
   that changes wave 3. Question 4 (σ² or eq. 17 as the coherence headline) sets what W3-B puts first.
4. **Peers.** `ListAgents`: who else is live on this machine (the researcher's polish sessions, a wave-2 tail). Agree
   with each, by message, who runs `pytest -n` and smoke when, and which ports: **8765 is the researcher's `--project`
   bridge on the real database — never yours**; wave 2 used 8791, earlier sessions 8792–8793; take **8794**. Warn any
   polish session before W3-F merges into files it may be editing (`api.ts`, `registry.tsx`, the run panel,
   `runs.py`).
5. **Commit the wave-3 prompts** if they are not committed, and note the commit as round 1's base.
6. **Keep the machine awake** while agents run: ask the host with its keep-awake tool (`request_keep_awake`). Wave 2
   lost two hours to a critic that ran on while the machine slept.

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

**Round 1 (parallel):** W3-A multiscale entropy · W3-B cycle shapes · W3-C pan matrix profile.
**Round 2 (after round 1 is merged):** W3-F UI, W3-D MPdist and W3-G the fairer noise test, in parallel (the
researcher's choices, 2026-10-14; W3-E is not run). W3-G needs W3-B's `Working/background_null.py` on `main`. W3-F can
start once A–C are merged; tell it to leave anything MPdist needs on the Family page for a short follow-up if D lands
after it. W3-D (one `DISTANCE_LABELS` line) and W3-G (`_grouping_items`, `_family_coherence`) both edit
`webui/server/library.py`, in different functions: dry-run the second merge. If one round-1 block is stuck in a fix
round whose API is already settled, round 2
can start from a base branch (main + that block's settled code) rather than wait: wave 2 did this
(`wave2-round2-base`, W2-ledger decision 16), and merged the block's final branch underneath later.

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

**The statistics below are fixed now, before any data are seen.** Wave 2's families template failed on the statistic
its brief had fixed, though another reading would have passed it. The manager kept the fixed one, because choosing the
statistic after seeing it pass is how a test fools itself (W2-ledger decision 22). Do the same:
- if a different reading looks better once the results are in, report it **beside** the verdict, never instead of it;
- propose that reading to the researcher with a re-test on spans not used here.

| Template | Real-data statistic | Null | Recordings |
|---|---|---|---|
| `complexity_fingerprint` (W3-A) | distance of the window-median MSE curve from the mean of the 20 surrogate curves, over scales defined in every run, against each draw's distance from the mean of the other 19 | the 20 surrogate draws | M2_aug rec 1 and rec 3, 440–464 h (wave 1's 24 h spans); *S. commune* rec 600 (all 73 h); rec 385 (4 h — expect "too few scales", which is itself a check) |
| `chain_cycles` (W3-B) | aligned SVD entropy of the stacked cycles (σ² **and** eq. 17); beats only if both are below every draw | **background null:** 20 draws of pseudo-cycles cut at random anchors, with the real cycles' lengths, from the same recording's event-free stretches, through the block's identical pipeline (its own `null_draws`, or computed beside it). Not the trend-kept or per-member phase null: wave 2 showed both are blind to smooth window-filling shapes, and a cycle is one. The surrogate run is a further floor (≈ 0 events expected) | the known chains: M2_aug rec 3 490–540 h, rec 6 370–470 h, L_LM_Jul_26_J rec 542 370–490 h (10 Hz); rec 2 294–304 h (13 events, a "few cycles" case) |
| `motif_lengths` (W3-C) | at the suggested length, the real median normalised nearest-neighbour distance below every draw's | the 20 surrogate draws | rec 385 (4 h): does it suggest ~1 min, the supervisor's finding? M2_aug rec 2 296–304 h, rec 6 400–408 h, rec 3 512–520 h |

For `chain_cycles` the background null is a floor that real chains should clear easily. **The findings are K with its
SigClust p, the change points, the order test and the floor fraction** (sharkfins on rec 2 against sharp drops on
rec 3). Report them as findings with the block's own nulls beside them. Put them next to wave 2's `event_families`
families on the same chains: two on rec 6 (53, 13) and two on rec 542 (131, 11). Those were found from 600 s windows,
and these from whole cycles.

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

**The fairer noise test (W3-G)** has no template either. Re-run two things with the quiet-stretch null:
- `W2-evaluation.md`'s Library table, in the sandbox: families beyond noise per method (Ward, HDBSCAN eom and leaf,
  k-Shape at k = 20), against the trend-kept null's column;
- the per-family verdicts of `event_families` on rec 6's and rec 542's chains, where wave 2 met the smooth-shape blind
  spot.

Say plainly which families change verdict and why, and whether Analyse now offers k-Shape. `event_families`' template
status is not re-judged: the researcher chose not to re-test it.

Write `docs/prompts/blocks/reports/W3-evaluation.md` in the wave-1/2 format: plain words first, a results table per
template, verdicts, the warnings you read, and what the researcher should decide.

## The gate (after all merges and integration)

1. `pytest -n 4` from the main checkout root (conda python): compare the **failure set** with the baseline from
   preflight 2 — nothing that passed may fail (a wall-clock test under load may flake: rerun it alone three times before
   calling it). The machine is often loaded (wave 2's gate ran beside the researcher's controller software at ~85 % CPU):
   judge timings as ratios.
2. `npx tsc -b` and `npm run build` in `webui/client`.
3. Smoke on **your own sandbox bridge, port 8794**. Start the bridge with the venv's interpreter — the conda python has
   no FastAPI, which wave 2's gate found the hard way: `PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1
   webui/.venv/Scripts/python.exe webui/run_server.py --port 8794 --sandbox` in the background. Smoke itself runs
   on the conda python, which has Playwright:
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
  the Library's families under the fairer noise test (W3-G), MPdist's read-out,
  the gate, the decisions you took for them, and the questions only they can answer (each: plain explanation → options
  → recommendation). Point at `W3-evaluation.md` and the ledger.
