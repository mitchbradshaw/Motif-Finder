# W2 — Manager brief: build, critique, merge and evaluate wave 2

You are the **managing session** for wave 2 of the blocks-from-the-literature plan, run in the **main checkout**
(`C:\Users\mmebr\Documents\CNN`, branch `main`). You do not write the blocks yourself: you launch implementer
sub-agents, launch critic sub-agents on their branches, run fix rounds, merge, integrate, run the gate, evaluate the
templates on **real recordings**, and report to the researcher. Wave 1 was run exactly this way on 2026-10-13/14; its
record is in `docs/prompts/blocks/reports/` — read `W1-evaluation.md` before you start, and the per-block
`*.critic.md` files to see what critics catch.

The researcher may be away while you run. **Do not stop to ask** unless a decision is irreversible or outside this
brief; make the defensible call, write it in the ledger (below) and in the final report.

## Read first

- `CLAUDE.md` — above all: the non-negotiable rules, "Talking to the researcher" (plain language first, then options,
  then a recommendation), the UI gate, and **never point pytest, a bridge or an adapter at a junction to the real
  `DATA/`; unlink any junction before removing a worktree**.
- `docs/prompts/blocks/README.md`, `00-common.md`, `critic.md`, and the six wave-2 prompts `W2-A … W2-F`.
- `docs/research/analysis-blocks-from-literature.md` §5 rows 7–10, §7, §8 (the researcher's decisions: Q2 FLUSS +
  snippets; Q3 clustering in Library **and** Analyse, one implementation; Q4 a template ships only if it **beats its
  random-data null** on real recordings — it need not be choosier than the drop detector).
- `docs/prompts/blocks/reports/W1-evaluation.md` and, if present, `W1-retest-known-spans.md` (FLUSS and trains re-run
  on spans the researcher knows hold drop chains — it says which detector finds those drops best, which matters for
  the families template).

## Standing rules for every sub-agent

- `Agent` tool, `subagent_type: "general-purpose"`, **`model: "opus"`, `effort: "medium"`** — never Fable (the
  researcher's standing instruction, memory `subagent-model-policy`).
- Implementers and fixers: **`isolation: "worktree"`**. A worktree is cut from the commit `main` is at **when the agent
  launches** — so commit every prompt and every merged round **before** launching agents that need it (wave 1 lost an
  hour to worktrees cut before the prompts were committed; the agents then read prompts with `git show <commit>:path`).
- Critics: **no worktree**; they read the implementer's worktree path and never edit it (see `critic.md`).
- Sub-agents cannot write report files reliably: each returns its report as its final message; **you** file it as
  `docs/prompts/blocks/reports/W2-<X>-<name>.md` (implementer) and `.critic.md` (critic), verbatim, with a one-line
  header saying who filed it and when.
- Give each sub-agent a short launch message: its prompt path, `00-common.md`, its commit prefix, the base commit,
  and (critics) the worktree path and branch. Do not paste the prompt into the message — point at the committed file.

## The ledger (do this first — wave 1 lost four agents to an interrupted session)

Keep `docs/prompts/blocks/reports/W2-ledger.md`: one row per agent — role, block, agent id/name, worktree path,
branch, base commit, status (launched / reported / critic verdict / fix round n / merged as `<hash>`), and every
decision you took on the researcher's behalf. Update it after every event. A resumed session reads it and continues;
an interrupted implementer is resumed with `SendMessage` to its id if the id is alive, else relaunched **in its
existing worktree** (tell it to read `git log` there and carry on).

## The sequence

**Round 1 (parallel):** W2-A event windows · W2-B Library methods · W2-C MiniRocket · W2-D snippets.
**Round 2 (after round 1 is merged):** W2-E families (needs A and B) · W2-F UI (needs A–D; better after E — launch it
when E's report is in, or in parallel with E and tell it to leave the families' glyph/smoke state for a short
follow-up).

For each block:
1. Launch the implementer. When it reports, file the report, update the ledger.
2. Launch a critic on its branch (`critic.md` + the block's prompt). File the critic report.
3. **Verdict `merge after fixes` or `do not merge`:** launch a fixer in the **same worktree** (or `SendMessage` the
   implementer if alive) with the critic report path and the instruction: fix every blocker and should-fix, test-first
   for each (a failing test, then the fix), report what changed. Re-critique only the changed parts when a blocker was
   behavioural. At most two fix rounds; after that, decide: merge as experimental with the open finding written into
   the block's description, or do not merge — and say which in the ledger.
4. **Merge** into `main` one branch at a time: `git merge --no-ff <branch>`. Expected conflicts (wave 1 had them every
   merge): the adapter count lines in `tests/test_adapter_spec.py` and `tests/test_end_to_end.py` — resolve by setting
   the true count (`discover_adapters()` and count) and concatenating the comments; never leave a duplicated assert.
   After each merge run the block's own tests plus `tests/test_block_standard.py tests/test_adapter_spec.py
   tests/test_import_boundaries.py tests/test_templates.py` (conda python: `"/c/ProgramData/anaconda3/python.exe" -m
   pytest … -q -p no:cacheprovider`, with `PYTHONIOENCODING=utf-8`).

## Integration (yours, after the merges; W2-F does the UI files)

- `webui/server/templates.py`: move each template constant from its test into `CANONICAL` **only once it has passed
  the evaluation below**; a template that fails goes into `EXPERIMENTAL` (as `fluss_regimes` / `event_trains` did) and
  its block's description starts "EXPERIMENTAL: …" with the reason and a pointer to the evaluation. Each template test
  gains `test_the_shipped_template_is_the_one_tested_here` (`canonical(name) == TEMPLATE`, or `experimental(name)`).
- `tests/test_block_standard.py` `COSTED`: add every block that declares a cost (the reports' snippets).
- RQ files: `docs/rq_roundA/RQ1…RQ6` — update any whose answerability changed (MiniRocket and HDBSCAN serve RQ1's
  "cluster the unlabelled pool, validate blind"; families serve the spiking-families report; snippets serve "where to
  look"). The rule is in `docs/rq_roundA/README.md`.

## Evaluation on real recordings (the researcher's bar, Q4)

Run in a **sandbox** runtime, never the real database: `server.runtime.Runtime("sandbox", runtime_root=<your scratch
dir>).setup()` … `.restore()` (see `webui/server/runtime.py`; wave 1's script did this —
`Working.run_groups.run_paired_recipe(recipe, db_path=rt.db_path, force=True, surrogate=True, surrogate_draws=20)`
gives the real run plus 20 phase-randomised draws). Rule: a template **beats its null** on a recording when its
statistic exceeds every draw (p = 1/21 ≈ 0.048); it ships when it beats the null on at least 2 of 3 recordings. Read
each block's own warnings too — wave 1's deconvolution "passed" while its warnings said it was splitting events.

The statistic and the null differ by template; use these (write any change and its reason in the evaluation):

| Template | Real-data statistic | Null |
|---|---|---|
| `event_clusters` | silhouette of `catalogue.cluster`'s clusters on the Event-shape features | the same chain on the surrogate draws (if draws yield < 10 events, use the shape null below) |
| `event_families` | fraction of events HDBSCAN places in a family, and the families' median `svd_entropy_norm` | **shape null:** the same real events, each waveform replaced by a phase-randomised copy of itself (same spectrum, no shared shape) — 20 draws; real must place more events in families **and** have lower SVD entropy than every draw |
| `minirocket_manual_labels` | classifier holdout accuracy on M2_aug's labelled windows (the interesting / not-interesting verdicts) | **label-permutation null:** 20 runs with the labels shuffled within the training split |
| `recording_snippets` | mean regime run length (windows) | the 20 surrogate draws (stationary: their regimes should flicker) |

Recordings: rec 385 (Mushroom_260720 CH14, the supervisor's spiking-families recording; its 1-min scale is the one
that served spikes), M2_aug rec 1 and rec 3 on 24 h spans (wave 1's), and the researcher's known chains — M2_aug rec 3
500–530 h, rec 6 380–460 h, L_LM_Jul_26_J (rec 542 / 543) 380–480 h — for the families and snippets templates, where a
right answer is visible by eye. Also run the two Library methods on the **real Library** (the 3,603 events, in the
sandbox copy): families, omitted share, adjusted Rand against the current Ward grouping, and the SVD-entropy spread —
the researcher will want that table more than any synthetic number.

Write `docs/prompts/blocks/reports/W2-evaluation.md` in wave 1's format: plain words first, a results table per
template, verdicts, the warnings you read, and what the researcher should decide.

## The gate (after all merges and integration)

1. `pytest -n 4` from the main checkout root (conda python): compare the **failure set** with the last gate in
   `W1-evaluation.md` (2904 passed, 0 failed then) — nothing that passed may fail.
2. `npx tsc -b` and `npm run build` in `webui/client` (main checkout).
3. Smoke on **your own sandbox bridge on a private port**, never the researcher's 8765 (`--project` = the real DB):
   `PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1 "/c/ProgramData/anaconda3/python.exe" webui/run_server.py --port 8791
   --sandbox` in the background, then `"/c/ProgramData/anaconda3/python.exe" webui/smoke.py --url
   http://127.0.0.1:8791` with `PYTHONIOENCODING=utf-8`. Traps (memory `webui-smoke-gate-traps`): never run smoke while
   `pytest -n` runs or while `dist` is being rebuilt; restart the bridge after any Python edit; finish on the **full**
   walk; `git checkout -- webui/screenshots` afterwards. Main's smoke baseline has known failures (Review inspector,
   Settings clicks, Discovery compare, cross-channel max-lag-10 — see `W1-evaluation.md` and memory
   `webui-smoke-baseline-2026-10-13`): compare **sets**, and require every wave-2 state to pass.
4. Stop your bridge.

## Finishing

- Commit on `main` with prefix `blocks-w2:` and the attribution line from your session; **do not push**.
- Worktrees under `.claude/worktrees/`: leave them (none should hold a junction; if one does, `cmd /c rmdir` the
  junction first — `CLAUDE.md`).
- Update the memory file `literature-blocks-plan.md` and its line in `MEMORY.md` (what shipped, what is experimental,
  what wave 3 needs).
- **Final message to the researcher:** plain words first (what each new block does, as to a newcomer), then the
  table of templates — shipped / experimental and the evidence — then the Library table, the gate, decisions you took
  for them, and the questions only they can answer (each: plain explanation → options → recommendation). Point at
  `W2-evaluation.md` and the ledger.
