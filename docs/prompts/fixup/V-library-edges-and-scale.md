# Fixup V — the Library gets its edges: a match becomes a member with its distance written down

**Runs after `L` and `Y`** (it needs a queue that opens and a seed picker that reaches the Library, and it
edits the same Seed page `Y` does). **Wave 4, beside `X`.** Q39 is answered (below).
It is what **Q3** needs, and `W` (Q6) cannot start without it.

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md`, `docs/RESEARCH_READINESS.md` §Q3 and
cross-cutting item 3, `docs/PIPELINE_PRD.md` "Distances", `prototyping/UI_FUNCTIONAL_SPEC.md` §4.2, §7.6,
§8.5 and §8.6, `docs/LIBRARY_STORAGE.md`, `docs/prompts/fixup/08-library.md` **L11**, and
`docs/prompts/wiring/requests/04-to-03.md` §2–§3.

Commit prefix `fixup-v:`. Test-first; first commit touches only `tests/` and must fail.
**`--sandbox` only.**

## Decided — `QUESTIONS.md` Q39 (2026-10-03)

A seed-search match becomes a Library member **only with an accepting verdict (`interesting` / `seed`)**, on an explicit ***Add N matches to E-xxxx*** act; *include unjudged* is a flag that is **off**. Rejected matches keep their distance on the detection row, so accepted-versus-rejected distance stays a query.

## Running in parallel (2026-10-03)

**Wave 4: you run beside `X`** (`X-divergence-read-properly.md`), another agent in the same checkout. The README's **"Running two prompts at once"** rules apply in full: your own port and a private client build served with `run_server.py --dist`; `npx vite build --outDir <yours>` while working and `npm run build` only for the gate (the other agent's in-flight files may make it red — say so in the report); `pytest -n 4`, never `-n auto`, and announce in your report when you took the machine for smoke; shared files are **append-only and committed immediately with your own hunks only** (`git add -p`). If you need a file the other agent owns, stop and write to `requests/` rather than editing it.

| | files |
|---|---|
| **yours** | `webui/server/library.py`, `Working/library/matching.py`, `Working/database/schema.py` (`motif_edge`), Library › Family, the Seed page's scale bank |
| **`X`'s — do not edit** | `webui/server/corpus.py`, `Working/database/queries.py` (the divergence queries), Explore › Corpus, the Discovery scoreboard's precision cells and Compare's disagreement breakdown |
| **shared** | `webui/client/src/discovery/RunsPage.tsx` (you add *Add N matches*; `X` changes scoreboard cells — touch only your own component), `webui/server/discovery.py`, `webui/client/src/api.ts`, `webui/smoke.py` |

**Talking to the researcher:** any question you put to them opens with a plain-language explanation, then the options, then your recommendation (`CLAUDE.md`). **Before you report, update** `docs/prompts/rq_roundA/RQ3-identity-under-scale.md` per that folder's README.

## What an edge is, and why its absence matters

The Library says "these spans are the same motif" in two different ways.

- **A grouping** (`groupings`, `grouping_assignments`) is a clustering of *everything already in the
  Library* under one distance — today the 149 "shape families" at Ward cut 0.6. It is recomputable and
  carries no evidence about any single pair.
- **An edge** (`motif_edge`, `Working/database/schema.py:277`) is a persisted fact about **one pair** of
  members: which **distance function** compared them, the **threshold**, the **distance value**, the
  **recipe hash** that produced it, and — for a pair on two channels of one recording — the **lag**,
  **waveform correlation** and **classification bin**. It is the row that says *"this span was found by
  searching for that exemplar, measured this way"*.

`motif_edge` has **0 rows** in the real database and no bridge route writes one. So nothing in the app can
answer *under which distance* two spans are the same motif (Q3), and there is nothing for a cross-channel
classification to be stored on (Q6). The Recurrence payload says it on every one of 149 families:
`"edges": "no edges"`.

The core is written and tested: `Working/distances.py` holds the three distances
(`scale_invariant_distance` :81, `native_length_distance` :96, `symbolic_distance` :139; names at
:38–40), and `Working/library/matching.py::match_span_to_entry` (:37) writes a member and an edge
idempotently. **No route calls it.**

## What to build

1. **Resolve a seed run's matches onto the Library.** An explicit act on a finished seed run in
   Discovery › Runs — *Add N matches to E-xxxx* — calls `match_span_to_entry` for each chosen match,
   **once per distance function**, so each pair carries up to three edges and the three numbers can be
   compared on the same pair. Thread the real `entry_id` into the seed binding (`04-to-03.md` §2); a
   match that re-finds an existing member resolves onto it (§4.2, `04-to-03.md` §3) instead of making a
   second one. Which matches qualify is Q39.
2. **Search at other scales.** The Seed page's *scale bank* reads *"3 lengths · 0.8× 1× 1.25× — needs a
   scale-bank algorithm"*. Build it: the exemplar resampled to each length, the existing
   `detection.seed_matches` search at each, overlapping matches across lengths reduced by the page's
   existing overlap policy, and **the scale factor recorded on each match** and on its edge's recipe. The
   null is drawn per length. The lengths come from one Settings key.
3. **Show the edges.** Library › Family: an edge list per member — distance function, value, threshold,
   scale factor, recipe — and §8.5's *edge provenance* in the rail. Library › Recurrence's
   `"edges"` field reads real rows.
4. **The Q3 read-out, on the Family page.** For one exemplar: per scale factor, matches found · judged ·
   accepted; and beside it the same pairs' distance under the scale-invariant function and under the
   native-length control. That table *is* the PRD's query — *"search at durations the exemplar was never
   defined at, and compare recall between the scale-invariant distance and the control"*. No test of
   significance is implied and none may be printed; the null count per length goes beside each row.

## Two things the code will tell you if you ask it first

- **`search_entry_across_durations` (`matching.py:159`) cannot be pointed at a real channel.** It loops
  over every start index at every duration and calls `match_span_to_entry` — a disk read and a database
  write — for each, with no exclusion zone. On a 2,595,600-sample channel that is millions of calls and
  would write a member for every overlapping window under the threshold. It is correct on the synthetic
  spans its tests use. **Measure it on a one-hour span before you decide anything**, report the number,
  and do not call it from a route on real data. Item 2 above is the affordable route to the same
  question; `stumpy.match` on this data runs in seconds per channel.
- **`_edges_label` (`webui/server/library.py:678`) reads bins the core never writes.** It counts
  `"independent"` and `"propagating"`; the core persists `"independent_recurrence"`
  (`Working/cross_channel.py:26`). It has never been wrong only because there has never been a row. Fix
  the reader to the core's spelling and pin it with a test; the bins themselves are `W`'s.

## The caveat that travels with every number here

Scale is duration, and a sharkfin's stored extent is the open question (`QUESTIONS.md` "Q26, REVISED",
Q26d; `future/N-event-extent.md`). An exemplar whose extent is wrong is searched for at the wrong native
length. **Say on the page which morphology the exemplar is, and do not present a scale comparison on a
sharkfin exemplar as settled.** Do not touch extents — re-defining one re-hashes Library rows.

## Leave alone

| Leave alone | Why |
|---|---|
| `lag`, `waveform_correlation`, `classification_bin`, Explore › Cross-channel | `W-cross-channel-onto-edges.md` |
| The grouping engine and its nine bases | groupings and edges are different facts; do not make one feed the other here |
| Hand edits (`hand_edits`, 0 rows), Family's *Send N to Review as a queue* | the Library prompt in `README.md` "What is left" |
| Event extents | `future/N-event-extent.md` |

## Acceptance — the researcher's walk

1. Library › Family for an exemplar → *Seed search in Discovery →* → the Seed page opens with that entry
   as the seed.
2. Scale bank → *3 lengths* → *Run seed search* → the histogram and the match cards carry each match's
   scale factor; the null is stated per length.
3. Drag the cut → run → Discovery › Runs → *Send N unjudged to Review* → judge them (`L`).
4. Back in Runs → *Add N matches to E-xxxx* → `motif_member` and `motif_edge` gain rows; each pair has an
   edge per distance function.
5. Library › Family → the new members, each with its edge list; the scale read-out table is filled from
   those rows.

## The gate

`npx tsc -b` + `npm run build` (own `--outDir` and `--dist` if another prompt is in the checkout);
`webui/smoke.py` on a fresh `--sandbox` bridge, alone, finishing on the **full** walk; `pytest -n 4`
against the baseline in `README.md` (re-measure; compare failure sets). `tests/test_block_standard.py`
must stay green if `detection.seed_matches` gains a parameter.

Evidence into `webui/screenshots/fixup/V/`.

## Report

`docs/prompts/fixup/reports/V-library-edges-and-scale.md`: the measured cost of
`search_entry_across_durations`; how many members and edges one real seed run produced, per distance; the
scale table for one trough exemplar and one sharkfin exemplar, with the caveat; Q39 answered or
defaulted; items left; out-of-scope files touched; the gate. Then close `08-library.md` L11 in place.
