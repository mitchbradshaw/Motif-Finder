# Report — Fixup V: the Library gets its edges

Run 2026-10-04 on `main`, in the main checkout, **beside `X`** (wave 4). Commit prefix `fixup-v:`.

The first commit, `5ea4ee1`, touches only `tests/` (`tests/test_library_seed_edges.py`,
`tests/test_webui_library_edges.py`). On arrival the core file failed at import (`match_exemplar_bank` did not exist)
and all 11 route tests failed, each for the reason it names (no bank on the setup, no `exemplarEntryId`, `_edges_label`
reading `(1, 1, 0)` where the core's bins give `(1, 1, 2)`, …).

Every bridge ran `--sandbox` on **port 8772**, serving a **private client build** (`--dist <scratchpad>/dist-v`). Nothing
wrote to the real `DATA/db/annotations.sqlite`. Sandbox of the walk: `webui/runtime/20261004-111803`.

**In plain words.** The Library can say "these two spans are the same motif" in two ways. A *grouping* is like sorting
a drawer of photos into piles: redo it with a different rule and the piles change. An *edge* is like a note pinned
between two photos saying "I found this one by looking for that one, and here is how alike they measured". Until now
the Library had piles and no notes. Now a seed search's matches that a person accepted are pinned to the exemplar with
three measurements each — one that ignores how stretched the shape is, one symbolic, and one control that does not —
and the search can look for the shape at stretched and squashed lengths. Comparing the first measurement with the
control, length by length, is the Q3 question.

---

## 1. What was built

| Prompt item | What exists now |
|---|---|
| **1. Matches resolve onto the Library** | Discovery › Runs › ***Add N matches to E-xxxx*** (`AddMatches.tsx`, `POST /api/library/runs/{key}/matches`) calls `Working.library.matching.resolve_run_matches`: for each match a person accepted, `match_span_to_entry` **once per distance function** (scale-invariant, symbolic SAX, native-length). The real `entry_id` was already threaded into the binding by `Y`; the run row carries it. A match that re-finds an existing member — any entry's, on the same channel, under §4.6 — **resolves onto it** (`dedupe.find_near_duplicates`, `04-to-03.md` §3); otherwise a new member with its content hash, channel and a machine revision 1 pointing at the detection. The seed finding itself is not an edge. Idempotent; audited. |
| **2. The scale bank** | `detection.seed_matches` gains `scales` and `overlap`. The exemplar is resampled to `round(m·s)` for each factor and `stumpy.match` runs at each length; every distance is put on the **native length's footing**, `d·√(m/L)` (a 1× distance is unchanged), so one cut means one thing across lengths; matches of two lengths that overlap are reduced by the Seed page's policy (lowest / first / all — it was a decorative dropdown before). **The scale factor is on each match** (label `match3@1.25x`, the page's `scale`, and the edge's `scale_factor` and recipe). **The null is drawn per length** (`null_distances(..., scales=)` → `byScale`; the paired null runs execute the same banked block). **The lengths come from one Settings key**, `analysis-defaults · seed.scale_bank`, default `0.8 1 1.25`. A one-length bank is today's search byte for byte, and a recipe that does not name `scales` hashes as before. |
| **3. Show the edges** | Library › Family: every member's **edge list in the rail** (distance, value, threshold, scale, run, recipe hash with the recipe on hover — §8.5's edge provenance); the **members seed searches added or re-found**, each with its edges, listed apart from the grouping's members (a grouping and an edge are different facts); *Seed search in Discovery →* opens the exemplar's entry. Recurrence's `edges` reads real rows, counted per pair: *"3 pairs · 9 edges · unclassified 3"*. |
| **4. The Q3 read-out** | The Family page's ***Does E-xxxx keep its identity at other scales?*** card: per seed run that searched for the exemplar, per scale factor — found · judged · accepted · members, the accepted pairs' scale-invariant and native-length (and symbolic) distance as median with *n within the cut*, and **the null per draw beside each row**. It names the exemplar's morphology and prints the Q26d caveat on a sharkfin. No test is run and none is printed (a test asserts the word "significan…" appears nowhere in the payload). |

**`_edges_label`** read `"independent"` and `"propagating"`; the core writes `"independent_recurrence"` and
`"propagation"` (`Working/cross_channel.py:26`). It now reads the core's constants, and counts pairs rather than rows
(three edges on one pair are one pair). Pinned by `test_the_edges_label_reads_the_cores_bin_spelling`.

`motif_edge` gains four additive, nullable columns: `scale_factor`, `detection_id`, `recipe_json`, `created_at`.

## 2. `search_entry_across_durations` — measured, and still not routed

On one hour of M2_aug CH2_A1 (3,600 samples at 1 Hz, 452–453 h), exemplar E-0697 (102 samples), lengths 82 / 102 / 128,
scale-invariant threshold 5, in a scratch database:

| | |
|---|---|
| calls to `match_span_to_entry` | **10,491** (every start at every length, each a disk read and a database write) |
| time | **16.4 s**, 1.56 ms per call (the machine was also running a seed run) |
| what it wrote | 29 matches → **30 members, 29 edges**, almost all overlapping windows of the same few events (no exclusion zone) |
| extrapolated to the whole channel (2,595,600 samples) | **7.8 million calls, ≈ 3.4 h, ≈ 21,600 members** — per channel, per exemplar, per threshold |

The banked seed search answers the same question on the same exemplar over three channels × four hours, with a 200-draw
null per length, in **30 s**. No route calls `search_entry_across_durations`; its docstring and the module's now say so.

## 3. Members and edges one real seed run produced

Two banked seed runs over the session scope (M2_aug, CH2_A1 · CH6_B1 · CH7_B2, 452–456 h). **The verdicts were mine,
written in the sandbox to exercise the path, by a stated rule: a match with d < 2 (where the null gives ≈0 per draw)
*interesting*, every other *not interesting*, the last left unjudged.** They are not the researcher's and nothing below is
a finding.

| run | exemplar | matches | judged · accepted | *Add N* wrote | edges per distance (SI · SAX · NL) |
|---|---|---|---|---|---|
| `seed_90cc37` (cut 7, 48 s, 600 null runs) | E-0697 · F-173 · trough · 102 s | 7 | 6 · 3 (in Review, by keyboard) | **3 new members** | 3 · 3 · 3 |
| `seed_056a5d` (cut 6, 71 s) | E-0191 · F-30 · sharkfin · 364 s | 17 | 16 · 3 (through the Review route) | **1 new member, 2 resolved onto existing Library members** | 3 · 3 · 3 |

`motif_edge`: 0 → **18 rows**. `motif_member`: 3,603 → 3,607. A second press of *Add* writes nothing and the button reads
*Add 0 matches to E-0697*.

## 4. The scale read-out

**Trough exemplar E-0697** (F-173), run `seed_90cc37`, bank 0.8× 1× 1.25× (82 · 102 · 128 samples), cut d ≤ 7, 200 null
draws per channel:

| scale | found | judged | accepted | members | scale-invariant d (median, within cut) | native-length d | symbolic d | null per draw |
|---|---|---|---|---|---|---|---|---|
| 0.8× | 4 | 4 | 2 | 2 | **1.19** (2/2) | **11.88** (0/2) | 0.00 (2/2) | 16.68 |
| 1× | 1 | 1 | 0 | 0 | — | — | — | 8.36 |
| 1.25× | 2 | 1 | 1 | 1 | **2.19** (1/1) | **9.36** (0/1) | 1.12 (1/1) | 10.38 |

**Sharkfin exemplar E-0191** (F-30), run `seed_056a5d`, bank 0.8× 1× 1.25× (291 · 364 · 455 samples), cut d ≤ 6:

| scale | found | judged | accepted | members | scale-invariant d | native-length d | symbolic d | null per draw |
|---|---|---|---|---|---|---|---|---|
| 0.8× | 11 | 10 | 1 | 1 | **0.32** (1/1) | **2.00** (1/1) | 0.00 | 7.39 |
| 1× | 2 | 2 | 0 | 0 | — | — | — | 3.20 |
| 1.25× | 4 | 4 | 2 | 2 | **0.83** (2/2) | **6.72** (1/2) | 0.00 | 3.85 |

**The caveat that travels with these.** Scale here is duration, and the native length is the exemplar's *stored* extent.
On a sharkfin that extent is the open question (Q26d: whether the slow rise belongs to this event or the next), so the
second table says the instrument works and nothing about sharkfins; the page prints that beside it. With placeholder
verdicts, the first table says only the same. What it does show is the shape of the answer: on the accepted pairs the
scale-invariant distance stayed small off 1× while the control was five to ten times larger.

**Two things the numbers showed about the instrument:**
- **The null depends on the length.** At one cut, the null gives about twice as many matches per draw at 0.8× as at 1×
  (16.7 vs 8.4; 7.4 vs 3.2). A shorter copy finds chance matches more easily even on the normalised footing. A scale
  comparison has to read each length against its own null, which is why it is printed per row.
- **The symbolic distance barely discriminates here.** At word length 16 it was 0.0 on four of six accepted pairs:
  SAX's minimum distance counts neighbouring symbols as zero apart. It is recorded (the PRD asks for it), but the
  scale-invariant/control pair is what carries the comparison.

## 5. Q39 — answered, built as decided

A match becomes a member only with `interesting` / `seed`, on the explicit *Add N matches to E-xxxx* act; *include
unjudged* is a checkbox, off. A rejected match is untouched: its distance stays on its `detections.score`
(`test_a_rejected_match_keeps_its_distance_on_the_detection_row`).

**One decision of mine, for the researcher to confirm or change.**

*In plain words:* every edge has a "threshold" column — the line a distance had to be under. For an edge written from a
seed search, what decided membership was your verdict, not a distance. So what number goes in that column?

- **(a) What I built:** the seed run's cut (the line the search used to propose the match), on all three edges of a pair,
  and the edge is written whatever its own distance. "Within" then reads as *would the control have kept this pair at
  the same line?* — which is the recall comparison the PRD asks for. The recipe on each edge says this in words.
- (b) A separate threshold per distance function from Settings, edges written only within it. Closer to the old
  `match_span_to_entry` behaviour, but it would drop exactly the control's out-of-threshold distances Q3 needs.
- (c) No threshold (NULL). Honest but the column is NOT NULL today and every reader would special-case it.

**Recommendation: (a).** The one caveat is the symbolic edge, whose units are not the cut's; its "within" is printed and
should not be read.

## 6. Left

- **The researcher's verdicts.** The route is built; the table needs their judgements on a few trough exemplars.
- **No Settings control for `seed.scale_bank`.** It is read from the key and printed on the page; set it today with
  `PUT /api/settings/analysis-defaults {"values": {"seed.scale_bank": [...]}}`.
- **The SLURM route** takes `scales` in its body, but the Seed page's SLURM path does not send it.
- **The exclusion zone** is still `stumpy.match`'s m/4, per length (unchanged, as `Y` left it).
- **A pair re-found by two runs gets two sets of edges** — one per run's evidence (the recipe hash names the detection).
  That is deliberate; a reader wanting one number per pair takes the newest.
- **Cross-channel bins** (`lag`, `waveform_correlation`, `classification_bin`) are untouched — `W`'s.
- **Hand edits and *Send N to Review as a queue* on Family** — untouched, as told.

## 7. Files

**Declared:** `webui/server/library.py`, `Working/library/matching.py`, `Working/database/schema.py` (`motif_edge`),
Library › Family (`FamilyPage.tsx`, new `library/Edges.tsx`), the Seed page's scale bank (`SeedPage.tsx`).

**Shared, my hunks only, committed at once:** `webui/client/src/api.ts` (appended, `0fa4f0b`, `4f12451`),
`webui/server/discovery.py` (seed hunks, `7a7873e`), `webui/client/src/discovery/RunsPage.tsx` (an import and one
line; the component is `AddMatches.tsx`). `webui/smoke.py` was not edited; my states are
`webui/smoke_pages/library_edges.json`.

**Out of the declared list — the reviewer should justify each:**

| file | why |
|---|---|
| `Adapters/detection_seed_matches.py` | The bank is a block parameter (`scales`, `overlap`), so the seed run, its paired null and the page all search the same way; `tests/test_block_standard.py` stays green |
| `Working/discovery/seeded_search.py` | The Settings key, per-length candidates and null, the step params |
| `webui/client/src/api/discovery.ts` | The Discovery adapter: `scales` on runs, matches and results; the banked poll |
| `webui/client/src/library/AtlasPage.tsx` | Its *Seed search in Discovery* passed a member id (`m-718`) as a seed id; it now opens the entry |
| `docs/RESEARCH_READINESS.md`, `docs/prompts/fixup/08-library.md`, `docs/rq_roundA/RQ3-…` | Closed in place / updated as the README asks |

None of `X`'s files was edited (`corpus.py`, `queries.py`, Explore › Corpus, the scoreboard cells). `queries.not_surrogate`
is imported, not changed.

## 8. The gate

| check | result |
|---|---|
| `npx tsc -b` | clean (whole tree, `X`'s in-flight files included) |
| `npm run build` | built (writes the shared `client/dist`; the gate smoke served my private build of the same tree) |
| `pytest -n 4` (conda) | **2131 passed, 21 skipped, 0 failed** in 8 m 48 s — failure set empty, as the baseline's. `T` left 2091 / 20; the rise is `X`'s tests and my 23 core tests (my 11 route tests are among the venv-only skips) |
| route tests under `webui/.venv` | `test_webui_library_edges.py` **11 passed**; with `test_webui_discovery.py`, `test_webui_library.py`, `test_webui_seed_sources.py`, `test_webui_block_views.py`: 122 passed, 3 xpassed, **1 failed — `test_the_scoreboard_cells_are_the_tables_own_numbers`, the documented pre-existing venv failure** |
| `tests/test_block_standard.py` | green with `detection.seed_matches`' two new parameters |
| `webui/smoke.py`, full walk, fresh `--sandbox` bridge (`webui/runtime/20261004-114012`) | **611 screenshots, 7 failures, 0 browser console/page errors, 0 unexpected server tracebacks.** My three states pass. Five failures are the standing five (the four Settings registration states, `discovery.runs--default`). The other two are not page failures — see below |

**I took the machine for smoke from 11:40 to 12:02** (no pytest ran during it; `X`'s bridge on 8771 stayed up but idle as far
as I could see).

**Found: two smoke states only pass in the tracked screenshot tree.** `review.inspector--padding +/-30 s is symmetric` and
`… +/-120 s …` (`fixup-g`) contain a `/`, so their screenshot path is a sub-directory. The tracked `webui/screenshots/`
already holds a directory literally named `review.inspector--padding +`, so the default walk writes into it; pointing
`SMOKE_SHOTS` anywhere else (I used the scratchpad, as the README suggests for the `[Errno 22]` writes) makes both
`EXC: [Errno 2] No such file or directory`. Re-walked with a short `SMOKE_SHOTS`: both states' checks pass (*renders ·
every trace inside its plot box · padding symmetric*) and the write still fails. The fix is one filename sanitiser in
`smoke.py`, which is shared; I did not make it.

Evidence: `webui/screenshots/fixup/V/` — `01` the Family page before, `02`–`03` the Seed page with the bank (null per
length, match cards carrying their scale), `04` Runs with *Add 0 matches* before review, `05` the Review queue, `06` Runs
after adding, `07`–`09` the Family page: the exemplar's edges in the rail, the scale read-out and the matched members,
one matched member's edge list.
