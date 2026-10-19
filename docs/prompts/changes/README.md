# docs/prompts/changes — the prompts cut from the backlog after the 2026-10-18 grilling

Each file is one prompt for one implementer agent (Opus, medium effort, an isolated worktree cut from `main`), run by
the manager with a critic and one fix round, then gated and merged. The researcher's answers that shaped them are in
the manager's session of 2026-10-18 (rounds 1–4 of the grilling); each prompt repeats the decisions it rests on under
"Decided with the researcher", so an agent needs nothing outside the repo. Reports go in `reports/`.

## The gate, per prompt (decided with the researcher, 2026-10-18 — Q42)

A single feature was taking up to six hours, most of it the full pytest suite and the full smoke walk. From now on:

- **Per merge:** the prompt's own tests and the files it names (both interpreters as needed), `tests/
  test_import_boundaries.py`, `tsc -b`, `vite build`, and the smoke UNITS the change touches on a fresh sandbox
  bridge. Nothing else.
- **Once a day, by the manager, before the push:** the full pytest suite and the full smoke walk, compared by
  failure SET against the last good baseline. A regression found there is fixed the next morning, not at midnight.
- **The critic** reviews every prompt-sized change; a change under about forty lines done directly by the manager
  skips it.
- `CLAUDE.md`'s "UI gate" section says the same (the researcher confirmed Q42 on 2026-10-19).

**Demo day is 2026-10-21** (the researcher, 2026-10-19). Everything outstanding is meant to land by then; from
2026-10-20 evening nothing merges without the daily full walk being clean against the recorded baseline.
The researcher also confirmed Q43 (interval colouring rule (c)), Q44 (gauge: green interesting + seed, red
not-interesting + artifact, grey unsure) and Q46 (F2B included), so the three prompts' "assumed" lines are decisions.

## Order and dependencies

| # | prompt | size | depends on | status |
|---|---|---|---|---|
| 0 | `site-fixes.md` — module-load reload, runs shown-off by default, AM/AO defaults, cubic detrend, close §1 | S, direct | AR merged | to do |
| 1 | `explore-span-plot.md` — the pile at t = 0, six band toggles, two greens, editable edges (closes U4) | M | — | ready |
| 2 | `explore-review-actions.md` — send a span's unjudged motifs to Review; artifact per channel from Cross-channel | M | — | ready |
| 3 | `cross-channel-overlay.md` — the tall single-axis overlay, bold/faded, align by lag, box → action strip | M–L | 2 | ready |
| 4 | `review-carry-and-overlap.md` — one item per overlap set; verdicts carry across runs (R7); class label stored (R3) | M | AR merged | ready |
| 5 | `edit-span.md` — Review's Edit span opens a live editor; revision for a member, annotation otherwise | M | — | ready |
| 6 | `seed-search.md` — four steps; "use these as detections" without a second search; no "no null" | M | AR merged | ready |
| 7 | `discovery-coverage-and-gauge.md` — coverage strip + "run on the missing" (extend); the verdict gauge | M | AR merged | ready (Q44 colours as recommended) |
| 8 | `reports.md` — detection-run report, then the chain-run record; matplotlib, HTML + Markdown + PNG, snapshots | L | — | ready |
| 9 | `sequences.md` — join adjacent members into sequences (gap 0 + 10 %), preview → keep; the sequence family page | M–L | — | ready |
| 10 | `interval-event-pages.md` — three leads per page, the rest folds; trains figures; the labelled intervals timeline | M | — | ready (Q43 rule (c) as recommended) |
| 11 | `library-family-actions.md` — pick a trace; cluster → slideshow in place; the rose reference | M | — | ready |
| 12 | `datasets-derive.md` — MJu26a_fs10 as L_LM's parent; CO, LM, SH, SO, F2B, L_R_Aug_26_PD_raw into derived | M | manager runs the scripts | ready (L_R rate must be read or stated) |
| 13 | `polish-pass.md` — less grey, fewer warnings, one palette, the add-block "about" card | L, one commit per page | 6, 7, 10 merged | ready |
| 14 | `corpus-map-off-the-request.md` — the home page serves its last map at once; the recompute runs in a worker process (speed second pass, item 1) | M | AR merged | **merged 43ee443 (2026-10-19)**; its state passes on real data; the explore unit + daily walk followed |

**The whole wave merged 2026-10-19 as cdd6be3** (rows 0–13 and the "for drops" follow-up, via `changes/integration`
5d02ab4; corpus-map (row 14) as 43ee443 before it). Reports are in `reports/`. Still to run on the real data:
`datasets-derive`'s scripts (the Prompt manager session, 2026-10-19 night: MJu26a_fs10 without the L_LM link, SH, SO,
F2B, L_R at 10 Hz; CO and LM skipped). Owed: the first clean post-wave full walk on 2026-10-20 morning.
**AR (the speed pass) merged 2026-10-18 as 5a20070** — the "AR merged" dependencies above are satisfied; base on
5a20070 or later. A second session ("Prompt manager and examiner") runs these prompts; the two sessions agreed on
2026-10-18: at most three implementer agents at once on this machine (six saturated it and made every smoke unit and
timing meaningless), no smoke unit or timing while another agent's pytest or build runs, a message before each fast-
forward of main and before each smoke window.

Parallel-safe sets (different files): {1, 5, 8, 9, 11, 12} can run together; {2 then 3}; {4, 6, 7} after AR; 13 last.
Two Discovery prompts (6, 7) touch `discovery.py` and the Discovery pages: run them one after the other, not together.

## Still open (not written as prompts)

- The blind-labelling mode's cluster-vocabulary buttons (Q42 of the older rounds): "hide the guess" exists
  (`review/BlindTest.tsx`); per-cluster buttons do not. Needs the vocabulary decided first.
- Global search (dropped 2026-10-18), the phantom Ctrl-C (only if seen again), the Export page's provenance.
- A `fires`/`scoreboard` second pass and the detection map's cache (AR left them, measured, in its report).
