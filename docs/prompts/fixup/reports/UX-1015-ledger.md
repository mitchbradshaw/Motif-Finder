# UX-1015 — the manager's ledger (the researcher's 2026-10-13 list, run 2026-10-15)

The researcher asked (2026-10-15, then away): push main, start the small list, and run prompts AK–AP and AQ with a
sub-agent each, a separate critic per prompt, one fix round, and the manager's own evaluation and gate at the end.
Nobody answers questions during the run; every open choice is decided here and recorded.

## The plan

| Wave | Prompts | Why this order |
|---|---|---|
| A (now) | AK spike block · AM peak alignment · AN library dendrogram · AO decompose block · AQ cross-channel finish | disjoint files; none touches the small list's files |
| B | AL send one detection to Review | shares Discovery's Browse card with small item 1 (loading bar); starts after that lands |
| C | AP grey-text sweep | touches every page; runs alone after every other merge |
| manager | the small list: browser loading bar · no default chain · delete a block from its page · legacy-detections log once · slideshow paging | done directly on main, each with its test and gate |

Per prompt: implementer (Opus, medium effort, own worktree from main, `docs/prompts/fixup/UX-1015-common.md`) →
critic (Opus, medium, `docs/prompts/blocks/critic.md` adapted to UI work) → one fix round by the same implementer →
manager's gate (its tests under both interpreters, `tsc -b`, `vite build`, its smoke states walked on a sandbox
bridge, then the relevant page units) → merge into main. After the last merge: the full pytest suite, the full smoke
walk, the evaluation, the push.

## Decisions

| # | Decision | Why |
|---|---|---|
| D1 | `AJ-cross-channel-finish.md` renamed `AQ-…` (67746fc) | another session had taken AJ for the Jobs prompt |
| D2 | A `node_modules` junction at `.claude/worktrees/node_modules` → `webui/client/node_modules`, outside every worktree | agents can type-check and build their client changes; `git worktree remove` cannot reach it |
| D3 | AM is built on its own recommendation (`align ∈ {grid, centre, peak, trough}` + `anchor_frac`, defaults unchanged) | the prompt opens with a question; the researcher is away and asked for no interruptions |
| D4 | AP runs last and alone | it edits captions on every page the others touch |
| D5 | Agents cannot smoke; they write states, the manager walks them | no database in a worktree; the wave-3 precedent |
| D6 | Agents' client gates use the main checkout's toolchain through the junction, never `npm install`/`npx` | the environment is shared; nothing may be installed |

## Timeline

| When | What |
|---|---|
| 2026-10-15 | main pushed (3cc2f62 → 33add7f: the two 10-13 merges, waves 1–3, the units fix). |
| 2026-10-15 | 67746fc AJ→AQ; 3810555 the brief and this ledger (the base every implementer cuts from); wave A launched: AK, AM, AN, AO, AQ. |
| 2026-10-15 | small list on main: 255e08e/e330768 legacy-detections refusal warned once per process (test red then green, 12 pass); e7bde55/22d0b5e no default chain (empty canvas: import · add · example · restore last), delete a block from its page (`analyse/deleteStep.ts`), browser loading bar, slideshow pager free; smoke flow takes the Example start, the page walk seeds the old chain (`SMOKE_CHAIN`, `empty_chain` states). tsc + build pass. |
| 2026-10-15 | AK reported; its critic launched. The real DB holds no template naming `spike_v1` with `delta`, so the rename refuses nothing saved. |

## Agents

| Prompt | Branch / worktree | Implementer | Critic | Fix round | Gate | Merged |
|---|---|---|---|---|---|---|
| AK | `worktree-agent-a644f595894c2c76a` · `.claude/worktrees/agent-a644f595894c2c76a` | reported (cf28cc2 red, 3f93c92; 25 tests green both interpreters; assumed: undeclared unit read as volts with a note, `delta`→`delta_mv`, default 1 mV placeholder; one edit outside scope in `views/registry.tsx`) | launched | | | |
| AM | | | | | | |
| AN | | | | | | |
| AO | | | | | | |
| AQ | | | | | | |
| AL | | | | | | |
| AP | | | | | | |

## Gates

(filled as they run)

## Evaluation

`docs/prompts/fixup/reports/UX-1015-evaluation.md`, written after the last merge.
