# Fixup Y — a seed the researcher chose: the picker reaches the Library, and Explore can hand it a span

**Ready to run after `L`.** No research decision. With `L`, it makes **Q2** answerable end to end:
*a human-adjudicated exemplar → seeded search → matches a human also accepts*.

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md`, `docs/RESEARCH_READINESS.md` §Q2 and "Met on
the way", `prototyping/UI_FUNCTIONAL_SPEC.md` §7.6, §10.4 and §5.2, and
`docs/prompts/wiring/requests/04-to-03.md` §1–§2.

Commit prefix `fixup-y:`. Test-first; first commit touches only `tests/` and must fail.
**`--sandbox` only.**

## Running in parallel (2026-10-03)

**Wave 1: you run beside `AA`** (`AA-manual-labels-and-window-sets.md`), another agent in the same checkout. The README's **"Running two prompts at once"** rules apply in full: your own port and a private client build served with `run_server.py --dist`; `npx vite build --outDir <yours>` while working and `npm run build` only for the gate (the other agent's in-flight files may make it red — say so in the report); `pytest -n 4`, never `-n auto`, and announce in your report when you took the machine for smoke; shared files are **append-only and committed immediately with your own hunks only** (`git add -p`). If you need a file the other agent owns, stop and write to `requests/` rather than editing it.

| | files |
|---|---|
| **yours** | `webui/server/discovery.py`, `webui/client/src/discovery/SeedPage.tsx`, `webui/client/src/explore/SpanActions.tsx`, `SignalPage.tsx`, `SignalDrawer.tsx` |
| **`AA`'s — do not edit** | `Adapters/catalogue_manual_labels.py` (new), `Working/database/window_matrix_store.py`, `webui/server/training_routes.py`, `webui/server/templates.py`, Analyse WindowSet rows, Library › Window sets |
| **shared** | `webui/client/src/api.ts`, `webui/smoke.py` (your states in your own `smoke_pages` file) |

**Talking to the researcher:** any question you put to them opens with a plain-language explanation, then the options, then your recommendation (`CLAUDE.md`). **Before you report, update** `docs/rq_roundA/RQ2-exemplar-seeded-search.md` per that folder's README.

## The defect — all three seed sources miss the human

§7.6 names three seed sources. Measured 2026-10-02:

| Source | What it offers today | Why |
|---|---|---|
| *Library exemplar* | the **first 24** of 3,603 entries, every one a machine-extracted `event_store` row | `motif_entry ORDER BY id LIMIT ?` with `SEED_LIMIT = 24` (`webui/server/discovery.py:953`, `:63`) |
| *Explore selection* | nothing | it reads `annotations.verdict = 'seed'` (0 rows), and Explore's *Take span for Review* is a demo write — `recordDemoWrite(...)` and a toast (`webui/client/src/explore/SpanActions.tsx:39–42`). It toasted *"span staged for Review · Explore spans queue"* and `annotations` stayed at 11,269 |
| *Family medoid* | 16 medoids of the seed store | fine, and not a human choice |

And the one human-made exemplar there is cannot be picked: pressing `S` in Review wrote `motif_entry`
3609 (`source_kind = 'review'`), the toast called it *"exemplar E-0217"*, and the picker did not list it.

## What to build

1. **The picker reaches every Library entry.** Search and paging over `motif_entry`, with the
   researcher's own exemplars first: filter by `source_kind` (`review`, `annotation`, `event_store`), by
   family in the current grouping, by recording and channel. A seed id stays content-addressed
   (`04-to-03.md` §2); thread the real `entry_id` into the binding so the run records which entry it
   searched for.
2. ***Take span for Review* writes.** `takeSpanForReview` already exists (`webui/client/src/api.ts:345`,
   `POST /api/annotations/seed`) and has no caller. Call it; the span becomes an `annotations` row with
   verdict `seed` (a human row in the human table — rule 5 holds), appears under *Explore selection* at
   once, and is in Review's `explore-spans` queue. The same for the Signal page's other two copies of the
   toast (`SignalPage.tsx:205`, `SignalDrawer.tsx:163`) where they mean the same act.
3. **A promoted exemplar is named by what was written.** The toast and the promotion card print the real
   `motif_entry` id; *Open in Library* opens it; *Seed search in Discovery →* (§8.5) opens the Seed page
   with it as the seed (wiring `05-review.md` §12 item 5).
4. **The Seed page's own defects, each small and each measured:**
   - *Open in Runs* navigates to `?run=seed_a9147c`; the run's key is `seed a9147c`. Runs answered
     *"No run named seed_a9147c in this session · Showing dehshibi_spikes instead."*
   - One cut, two figures: the Parameters card read *"chosen 14.5 · the null gives 0 per draw"* beside
     the histogram's *"5 kept · the null gives 6.3 per draw"*. `SeedPage.tsx:341` prints `nullAtRec`,
     the count at the *recommended* cut, and there was none. 6.3 is right (1,269 null distances ≤ 14.5
     over 200 draws).
   - A dragged cut is lost on reload, and re-running an unchanged search adds a second run with the same
     label — three rows all reading *"seed a9147c"*, keys `seed a9147c`, `_2`, `_3`. An unchanged search
     is the same run; a changed cut is a new one whose label says how it differs.
   - The results payload served `"trace": []` for every candidate. Confirm each match card draws the
     **match** over the seed, as §7.6 says, and not the seed alone.

## Leave alone

| Leave alone | Why |
|---|---|
| The scale bank, *Matrix profile join*, multi-seed search | `V` builds the scale bank; the other two are *"not built"* by design |
| The exclusion zone (m/4 served, §7.6 asks m/2) | the page already says so; changing it changes every stored result. Raise it in your report, do not change it |
| The rest of Explore › Signal's `demo data` regions (*Save span*, tags, notes) | `01-explore.md`. Wire the one gesture and leave the chip honest about the rest |
| The null's draw count, method and correction | `T` |

## Acceptance — the researcher's walk for Q2

1. Review › any detection queue → `S` on a span worth searching for → the toast names entry N.
2. *Seed search in Discovery →* (or Discovery › Seed search › *change seed* › filter *review*) → entry N
   is the seed, with its recording, channel, time and content hash.
3. *Run seed search* → drag the cut → run → *Open in Runs* lands on **that** run.
4. *Send N unjudged to Review* → *Open Review* (`L`) → judge them.
5. Back in Runs → *Refresh after reviewing* → the scoreboard row for the seed run reports how many of
   its matches a human accepted.
6. The same from Explore: brush a span on Explore › Signal → *Take span for Review* → it is offered
   under *Explore selection*.

## The gate

`npx tsc -b` + `npm run build` (own `--outDir` and `--dist` if another prompt is in the checkout);
`webui/smoke.py` on a fresh `--sandbox` bridge, alone, finishing on the **full** walk; `pytest -n 4`
against the baseline in `README.md` (re-measure; compare failure sets).

Evidence into `webui/screenshots/fixup/Y/`.

## Report

`docs/prompts/fixup/reports/Y-seed-sources.md`: what each seed source offered before and offers now; the
`annotations` and `motif_entry` rows the walk wrote in the sandbox; each Seed-page defect with its before
and after; items left; out-of-scope files touched; the gate.
