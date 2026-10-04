# Fixup AE — the Library hides what is under the noise floor, filters by what matters, and every plot is an index

**Ready to run. Runs in parallel with `AD`** (see *Running in parallel* below). Written 2026-10-04. Every decision
here was already made in earlier rounds and is copied in below. **RQ6 waits on this prompt** (`QUESTIONS.md`
Round 12 Q5): recurrence is to be read on families whose members are real events, not drift.

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read these first:
- `CLAUDE.md`;
- `docs/prompts/fixup/08-library.md` (the symptom table, L0–L18);
- `QUESTIONS.md` **Q-X2.5, Q21, Q22, Round 10** (the rose reference and Q-L6/Q-E6) and **Round 12**;
- `docs/LIBRARY_STORAGE.md` §3.4 (`motif_features`);
- `reports/D-event-features.md`, `reports/E-aggregate-stops-fabricating.md` §8.4, `reports/H-blocks-show-their-work.md` §4
  (the slideshow);
- `reports/X-divergence-read-properly.md` §"What was built" item 1 (the one verdict resolver);
- `webui/server/library.py`.

Commit prefix `fixup-ae:`. Test-first: your first commit touches only `tests/` and must fail. **`--sandbox`
only.**

## In plain words (the researcher asked for this framing)

The Library is an album of motifs sorted into families. Most of it (`drop_motifs10`, 88 %, and the 10 Hz Fig2A
families) is full of tiny wiggles at or under the instrument's noise floor. Looking at those is like looking at
static. Cross-channel classification (`AD`'s measurement) showed that drift clips of that size "match" anything.

This prompt does three things:
1. **Hides sub-floor motifs from view** without deleting them.
2. **Lets you filter by the things that actually separate motifs**: how long the fall is, and whether a window
   holds one event or several.
3. **Makes every plot clickable**, so clicking a family shows its real waveforms.

## Decided (do not re-open)

1. **The noise floor is a VIEW filter, never a gate** (Q21). Rows stay in the database; the Library hides them and
   says how many.
   - **The floor:** Settings › Datasets › *noise floor* for that dataset (the field exists, `DatasetsPage.tsx:305`);
     where it is empty, **0.1 mV** (Q-X2.5).
   - **What is compared with it:** the **detector's own `drop_depth_mv`** from `motif_features`
     (`source = 'detector'`), not peak-to-peak over the stored span (Q-X2.5: the span measure is the wrong one).
     Where a member has no detector depth, use `interrogation.event_shape`'s depth from `motif_features`. Where it has
     neither, it is *unmeasured*: shown, counted and badged, never silently passed or hidden.
   - **On by default** on Atlas, Family and Recurrence, with one toggle *show sub-floor (n)*.
   - **Family cards and counts are computed after the filter.** A family whose every member is sub-floor is hidden
     from the Atlas and counted in *n families entirely under the floor*.
   - Measure and report what the filter removes per import store and per dataset. Expected from Q-X2.5: about a third
     of `drop_motifs10`, 0 of the seed store.
2. **Two more filters** (Q22):
   - **`fall_duration_s`** is a range filter (globally comparable; in `motif_features` for every entry).
   - **`is_pure`** is a toggle (a global flag: 2,960 of 3,511 in `drop_motifs10`).
   - **`scale_band` is NOT a filter.** It is a within-span octave index (band 1 is 174 s in one span and 4 s in
     another). Show its label (the duration range from `scale_band_labels`) on a card as provenance only.
3. **Every plot is an index** (Q-L6 / Q-E6). Clicking a family on the Atlas, or a cell of the Recurrence raster,
   opens that family's (or that cell's) members **in place**, in `kit/Slideshow.tsx` (`H`'s component: real samples,
   per-panel y with a scale bar, the `[2 falls]` flag), with *Open family page →*. It does not navigate away. Explore's
   maps (E6) get the same if it is a small step from the same component; otherwise list it under *Left*.
4. **"Judged" means the one verdict resolver** (L7). A member's verdict comes from
   `Working/discovery/divergence.py`'s order: a Review verdict first, then the event row it matches, then the reviewed
   windows it falls in (centre rule, Settings' containment mode). That replaces exact span equality, which matched
   nothing (0.0 % on every family). Print the rule beside the figure. Import it; do not write a second resolver.
5. **The rose reference** (Round 10): the slope that reads 45° is **the median steepest slope over human-accepted
   Library motifs** (accepted by item 4's resolver), so sharp noise and artifacts do not skew it.
   - **Where it lives:** computed by one core function, stored as a Settings › Analysis defaults key with the
     population it came from (*n accepted motifs, computed on <date>*), recomputed on an explicit act. Every rose
     prints it. `interrogation.event_shape`'s `rose_reference_mv_s` default reads it.
   - **The fallback:** the real database has **0** accepted motifs today. Until there are at least N (a Settings key,
     default 30), fall back to the median over all Library motifs above the noise floor, and **every rose says which
     population it used**. Never silently use 1.0 mV/s (`gradients.py:89`).
6. **Hand edits are written** (L4). The routes (`POST` / `DELETE /api/library/hand-edits`) and `hand_edits.py` are
   tested; wire the Family page's *Remove from family*, *Make exemplar* and `+ tag` to them, replacing the
   `not wired yet:` toasts. Removing noise members by hand is part of building the Library. The class select waits
   for the Review-behaviour prompt's classes: leave it and say so on it.
7. **`RULE_VERSION` and `rise_time_s`** (`E` §8.4): `Working/library/features.py::RULE_VERSION` names
   `rise_time_frac`. The backfill stores `rise_time_s` (null for a drop) so the route stops measuring it per request.

## Leave alone

| Leave alone | Why |
|---|---|
| Polar / cube plots (L5) | dropped for this stage (Round 10) |
| The `custom` basis (L9), near-duplicate flags (L10), type-specimen re-import (L13), the default cut's home (L14), template versions (L15), the excluded stores (L17) | not on the research path; list under *Left* if touched by accident |
| Cross-channel classification, the chance test, the suspected-artifact queue, `family_recurrence`'s body | `AD`, beside you |
| The seed search's exclusion zone | `AD` |

## Running in parallel (2026-10-04)

**You run beside `AD`** (`AD-cross-channel-against-chance.md`), another agent in the same checkout. The README's
**"Running two prompts at once"** rules apply in full:
- **Your own build:** use your own port and a private client build served with `run_server.py --dist`. Use
  `npx vite build --outDir <yours>` while working, and `npm run build` only for the gate (the other agent's in-flight
  files may make it red — say so in the report).
- **Tests:** `pytest -n 4`, never `-n auto`. Announce in your report when you took the machine for smoke.
- **Shared files** are **append-only and committed immediately with your own hunks only** (`git add -p`).
- If you need a file `AD` owns, stop and write to `requests/` rather than editing it.

| | files |
|---|---|
| **yours** | `webui/client/src/library/AtlasPage.tsx`, `GroupingPage.tsx`, the Library filter bar in `chrome.tsx`, `Working/library/features.py`, the rose-reference function (new, `Working/library/`), Settings › Analysis defaults' rose keys, `Adapters/interrogation_event_shape.py`'s default only |
| **`AD`'s — do not edit** | `Working/cross_channel.py`, `Working/library/matching.py` (`classify_family_across_channels`, `family_recurrence`), `webui/client/src/library/CrossChannel.tsx`, `Edges.tsx`, `Adapters/detection_seed_matches.py`, `Working/discovery/seeded_search.py`, the Seed page, `Working/review/` queue code |
| **shared** | `webui/client/src/library/FamilyPage.tsx` and `RecurrencePage.tsx` (you add the filter, the in-place slideshow and hand edits; `AD` adds its classify / flagged lines — keep to your own components and mount points), `webui/server/library.py` (new routes and helpers appended, no edits to `AD`'s), `webui/client/src/api.ts` / `api/library.ts`, `webui/smoke.py` (your states in your own `smoke_pages` file), Settings pages |

**One seam to agree, not to fight over.** Recurrence must count only members above the floor. **Do not edit
`family_recurrence`.** Pass it the filtered member ids from the caller (`library.py::_recurrence_cells`), which
already hands it `member_ids`. If that turns out not to be enough, write to `requests/` for `AD`.

**Talking to the researcher:** any question you put to them opens with a plain-language explanation, then the
options, then your recommendation (`CLAUDE.md`). **Before you report, update** `docs/prompts/rq_roundA/RQ6-*.md`
(the *Build the Library* step) and `RQ3-*.md` (families are now filterable above the floor) per that folder's README.

## Acceptance (check these in a browser)

1. **The floor on the Atlas:** it hides sub-floor members and says how many, by store. *Show sub-floor* brings them
   back. A family made only of sub-floor members is gone from the grid and counted.
2. **Filters:** set *fall duration* 10–300 s and *pure only*. The cards and counts change and the filter is printed.
   A card shows its scale-band label as provenance.
3. **Clicking:** click a family card → its members in a slideshow in place → *Open family page →*. Click a
   Recurrence cell → that cell's members.
4. **Family page:** *judged* reads the resolver's figure with its rule. Remove a member by hand → `hand_edits` gains
   a row → the member is gone after a reload and after a regroup.
5. **The rose:** it prints its reference and population (*fallback: all above-floor motifs, n = …*, since nothing is
   accepted yet).

## The gate

1. `npx tsc -b` + `npm run build` (own `--outDir` and `--dist`).
2. `webui/smoke.py` on a fresh `--sandbox` bridge, finishing on the full walk.
3. `pytest -n 4` against the baseline (2,212 passed / 22 skipped / 0 failed on 2026-10-04; compare failure sets).
4. In particular: `tests/test_import_boundaries.py` and `tests/test_block_standard.py`.

Evidence into `webui/screenshots/fixup/AE/`.

## Report

Write `docs/prompts/fixup/reports/AE-library-floor-and-indexes.md`. Open with a plain-language summary. Then cover:
- what the floor hides per store and per dataset;
- families before → after;
- the rose reference and its population;
- *judged* before → after;
- items left;
- out-of-scope files touched;
- the gate.

Then mark `08-library.md`'s rows closed in place.
