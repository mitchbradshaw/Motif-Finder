# Report — Fixup Y: a seed the researcher chose

Run 2026-10-03 on `main`, in the main checkout, **beside `AA`** (wave 1). Commit prefix `fixup-y:`.

The first commit, `12b16f0`, touches only `tests/` (`tests/test_webui_seed_sources.py`). It fails 16 of its 18 tests
on arrival under `webui/.venv`. The two that passed on arrival:
- the server already persisted the draft (the client never wrote it);
- a taken span was already a human row.

Every bridge ran in `--sandbox` on **port 8769**, serving a **private client build** (`--dist <scratchpad>/dist-y`; the
banner said `CLIENT = … (a private build, not the shared client/dist)`). Nothing wrote to the real
`DATA/db/annotations.sqlite`.

**In plain words.** A seed search is "find me more of this shape". Before this fixup, the three places a seed could
come from all skipped the person:
- the Library list showed only the first 24 of 3,603 machine-made entries;
- Explore's *take this span* button only pretended to save;
- the exemplar you had just promoted in Review was invisible to the picker.

Now all three reach what you chose, and the Seed page's run is one run you can find again.

---

## 1. The three seed sources — before and after

| Source | Before (measured 2026-10-02) | Now |
|---|---|---|
| ***Library exemplar*** | `motif_entry ORDER BY id LIMIT 24`: the first 24 of 3,603 rows, every one `event_store`. The entry Review had just promoted (3609, `source_kind = 'review'`) was not offered | `GET /api/discovery/seeds?source=library` pages and filters the whole table. Filters: `kind` (review · annotation · event_store), `family` (current grouping), `recording`, `channel`, `entry`, `offset`/`limit`, and it reports `total`. Order: `review`, then `annotation` (newest first), then the rest in id order. On the real copy: **total 3,603; the first four are the four `annotation` entries 3608, 3607, 3606, …**, each saying its family (*"from a human annotation · family F-126"*) or *"no family yet"*. After `S` in Review, the promoted entry is first |
| ***Explore selection*** | Read `annotations.verdict = 'seed'` (0 rows). Explore's *Take span for Review* was a demo write: `annotations` stayed at 11,269 | *Take span for Review* and the selected motif's *Review this motif* both `POST /api/annotations/seed` (one door, `explore/SpanActions.tsx::takeSpanForReview`). The span becomes a human `annotations` row with verdict `seed` (rule 5 holds). It is put in an *Explore spans* Review queue (one open queue, reused on each take) and offered at once under *Explore selection*, newest first, titled *"span N"* |
| ***Family medoid*** | 16 medoids of the seed store | Unchanged (not a human choice); reachable from the same picker |

**The binding names the entry.** A library seed id stays content-addressed (`library:<rec>:<start>:<end>`,
`04-to-03.md` §2), and `_seed_by_id` now finds the `motif_entry` row it is and passes its id to
`seed_from_content(entry_id=…)`. So the step's `library_exemplar` binding carries the real `entry_id`, and the
Discovery run row records it (`params.entryId`, served as `entryId`).

**What does not carry it, on purpose:** the stored `configs` row. `Working/recipes.py::_normalize` strips `entry_id`
from a `library_exemplar` binding so the recipe hash is content-addressed (ticket 14): the same shape on another
machine is the same recipe. I did not change that, and the test says so. (The first test asserted the config
carried it; it was amended in `7bbed7e` with that reason.)

## 2. A promoted exemplar is named by what was written

| | Before | Now |
|---|---|---|
| Toast on `S` | *"seed · exemplar E-0217 created in the Library"*, a number minted in the browser (`review/store.ts::mintExemplar`) | *"seed · Library entry 3610 created · auto-advance paused"*, from the bridge's promote reply (`entry_id`). A recurrence reads *"already in the Library as entry N"* |
| Promotion card | chip *"exemplar E-0217"* | chip **entry 3610**; the header badge reads *exemplar entry 3610* |
| *Open in Library* | `library/family/<nearest>?exemplar=E-0217` | Opens the family that holds the entry in the current grouping, with its member selected (`?member=m-<id>`). A freshly written entry is in **no** family until the next regroup, so the button is disabled and says *"entry 3610 is in no family of the current grouping yet — the next regroup places it"*, rather than opening something else |
| *Seed search in Discovery →* | did not exist | `discovery/seed?entry=3610`; the Seed page opens with that entry as the seed and makes it the draft |

The cluster view's seed batch takes its id the same way. The minted id is no longer used.

## 3. The Seed page's own defects — before and after

| Defect | Before | After |
|---|---|---|
| *Open in Runs* lands elsewhere | Navigated to `?run=seed_a9147c` while the key was `seed a9147c`: *"No run named seed_a9147c … Showing dehshibi_spikes instead"* | Run keys are URL-safe slugs (`seed_c61395`). The page finds **its** run by seed and cut (both now on the run row), not by label prefix, and *Open in Runs* carries that run's own key. Walk: → `#/discovery/runs?run=seed_c61395`, run selected, *Browse detections · run seed c61395* |
| One cut, two figures | Parameters card *"chosen 14.5 · the null gives 0 per draw"* (the null at the **recommended** cut) beside the histogram's *"5 kept · the null gives 6.3 per draw"* | Both read one number at the cut in force. Walk: card *"chosen 5 · 4 kept · the null gives 20.6 per draw"*, histogram *"4 kept · the null gives 20.6 per draw"* |
| A dragged cut lost on reload | The draft lived in tab memory only | Written to the session row (`PUT /api/discovery/seed/draft`, 400 ms after the last change). Walk: drag to 5 → reload → *"chosen 5"* |
| Re-running adds a same-label run | Three rows *"seed a9147c"*, keys `seed a9147c`, `_2`, `_3` | An unchanged search (seed, channels, span, k, cut) returns the run already made (`reused: true`). *Run seed search* is disabled with *"already run with this seed and cut — seed c61395"*. A changed cut is a new run whose label says how it differs (e.g. *"seed x · d ≤ 2.5"*). A seed change drops the old seed's cut |
| Match cards drew the seed alone | `"trace": []` for every candidate | Every candidate carries its match's own 60-point trace in display units. The card overlays it on the seed, each centred on its own mean (MASS compares z-normalised shapes, so a match hours away can sit millivolts off). Pinned by `test_every_kept_candidate_carries_the_matchs_own_trace`. Walk: every card has two paths, `var(--trace)` and the seed's purple |

**Found and fixed along the way:**
- **A chosen seed never took effect.** The page took *the first seed of the `?source=` kind*, and `?source` defaulted
  to `library`, so *change seed* set the draft and the card still showed the first entry. The seed is now the draft's
  own (`setup.seed`). Switching to another source's tab lists that source inline; it does not silently swap the seed.
- **The run used no cut when the cut was the recommended one.** *Run seed search* sent `cut: undefined` unless a line
  had been dragged, so the run kept all k matches. It now sends the cut in force.
- **A "No matches" flash.** The previous seed's empty result read *"No matches · the search returned nothing"* while a
  new search ran. It now shows *searching for the seed*.
- **A spurious toast.** Remounting the page after a finished search toasted *"seed c61395 finished · 0 matches"*. Now
  only a search that finishes while the page is open says so.
- **Review's seed-search queue meta line** read *"run undefined seed search, exemplar undefined · match d undefined"*.
  A clause is now printed only when it has a value.

## 4. The walk for Q2 (sandbox `webui/runtime/20261003-112502`)

1. Review › queue 2 (*drop_detection_v1 - Mushroom_260720 CH14*) → `S` on detection 101. Toast: *"seed · Library
   entry 3610 created"*. Card: **entry 3610**. ✔
2. *Seed search in Discovery →* → the seed card reads *entry 3610 · promoted in Review · no family yet ·
   Mushroom_260720_0509_4hrs_CH14_fs1.mat · CH14 · 1.52 h · 60 s · hash c6139581b6761003*. ✔
3. Drag the cut to 5 → reload (kept) → *Run seed search* → *"seed c61395 · 4 found"* → *Open in Runs* lands on
   `seed_c61395`. ✔
4. *Send 4 unjudged to Review* → *Open Review* → queue 3 *"Discovery · seed_c61395"* → judged: 1206 interesting,
   1222 not, 1223 interesting, 1224 not. ✔
5. Runs › *Refresh after reviewing* → **✘ not as asked.** Row: *"seed_c61395 · 4 found · 0 already judged · 3 reviewed
   · 0 interesting · 0 % · 0.00 over 6.033 h · 23 / 3 · 0.2×"*. Two of four were accepted, and the row says 0. The
   verdicts are in `adjudications`, and the scoreboard's *interesting* reads `annotations` only. This is exactly what
   `L` found and handed to **`X`** ("precision means what it says"). I did not touch the scoreboard.
6. Explore › Signal (CH2_A1) → select MOTIF_1 → *Review this motif* → *"MOTIF_1 taken for Review · annotation 11303 ·
   in the Explore spans queue and offered as a seed in Discovery"*. Then the span row's *Take span for Review* →
   annotation 11304. Discovery › Seed search › *Explore selection* lists *span 11304* (7,200 samples) and *span
   11303* (590 samples). Picking 11303 → `?seed=explore:2:0:590`, provenance *CH2_A1 · 0.00 h · 590 s · hash
   d7d3a8fd23958989*. ✔

**Rows the walk wrote in that sandbox:**

| table | rows |
|---|---|
| `motif_entry` | 3609 (rec 385, 2380–2440, detection 100, `review`); 3610 (rec 385, 5470–5530, detection 101, `review`) |
| `annotations` | 11303 (rec 2, 0–590, `seed`, `explore.take_for_review`); 11304 (rec 2, 0–7200, same). Total 11,269 → 11,271 |
| `adjudications` | 100 seed, 101 seed; 1206 interesting, 1222 not_interesting, 1223 interesting, 1224 not_interesting |
| `review_queues` | 3 *Discovery · seed_c61395* (`seed-search`, run ids 79, 81, 83); 4 *Explore spans* (`explore-spans`) |
| `discovery_runs` | `seed_c61395` / *seed c61395*, `seedId library:385:5470:5530`, `cut 5.0`, `entryId 3610`, identity recorded |

Evidence screenshots are in `webui/screenshots/fixup/Y/`.

## 5. Left, and raised

- **Step 5 of the walk is `X`'s** (above).
- **The exclusion zone: m/4 served, §7.6 asks m/2.** Not changed, as told. The plain version: when the search finds a
  match, it ignores near-copies of that match within a "keep-out" distance, so one bump is not counted three times
  over. The spec asks for a keep-out of half the seed's length; the block uses stumpy's default of a quarter.
  - **Options:**
    - (a) leave it, and keep printing it (today);
    - (b) give `detection.seed_matches` an exclusion parameter and set m/2. That changes every stored seed result,
      and so their recipe hashes.
  - **Recommendation:** (b), once `T` and `X` have landed, so the counts it changes are counts that mean something.
- **SignalDrawer's *Send selected to Review*** (`explore/SignalDrawer.tsx:161`) is a different act: existing rows
  into a queue, not a new span. It is still a demo write; the page still wears its `demo data` chip.
- **Analyse cannot bind an exemplar** for `detection.seed_matches` (`SideInputResolutionError`). It is untouched;
  Discovery is the route for Q2.
- **A new Library entry is in no family** until a regroup, so *Open in Library* is honestly disabled for it. Whether
  `S` should place it in a family at once is §10.4's panel, which is still a demo write (`exemplar.family`).
- The empty-queue state in Review says *"No more items in the demo fixture"* on a live queue. That is Review's
  wording, not touched.

## 6. Files

**Declared and touched:** `webui/server/discovery.py`, `webui/client/src/discovery/SeedPage.tsx`,
`webui/client/src/explore/SpanActions.tsx`, `SignalPage.tsx`. `SignalDrawer.tsx` was read and left (§5).

**Shared, append-only, committed at once with my hunks only:**
- `webui/client/src/api.ts` (`9b3075f`, `ff90892`);
- my own smoke file `webui/smoke_pages/seed_sources.json` (`051a308`, five states). `webui/smoke.py` was not edited.

**Out of the declared list — the reviewer should justify each:**

| file | why |
|---|---|
| `webui/server/explore_routes.py` | The take route gets or creates the Explore spans queue and returns its id (item 2, "is in Review's explore-spans queue": no such queue existed) |
| `webui/client/src/api/discovery.ts` | The Discovery adapter: seed page query, `setup.seed`, run `seedId`/`cut`, `saveSeedDraft` |
| `webui/client/src/review/Inspector.tsx`, `ClusterView.tsx`, `parts.tsx`, `store.ts` | Item 3: the toast and card name the written entry; the card's two links; the meta line |
| `tests/test_webui_seed_sources.py` | New, the test-first commit |

None of `AA`'s files was edited. `AA` committed its own `api.ts` hunks while I worked, and my two `api.ts` commits
carry only mine.

## 7. The gate

**I took the machine for the full smoke walk at about 11:30 and ran nothing else beside it; `pytest` came after it
finished.**

1. **`npx tsc -b`: clean. `npm run build`: green.** Both ran at the end, with `AA`'s files in the tree. Earlier in the
   day `tsc -b` was red for a while on `analyse/ChainPage.tsx` (`template_kind`), which was `AA`'s in-flight work and
   cleared when it landed. The smoke walk served the private build of the same sources.
2. **`webui/smoke.py`**: run on a fresh `--sandbox` bridge (port 8769), alone, the **full** walk.
   - **611 screenshots over 589 page states; 0 browser console/page errors; 0 unexpected server tracebacks; 7
     failures:**
     - **the five standing** (`discovery.runs--default` and the four Settings registration Check states, as the
       README lists them);
     - **two that are not render failures:** `review.inspector--padding +/-30 s` and `+/-120 s`. Both printed `ok:
       … renders · … padding symmetric`, then failed to *write* their screenshot. Their state names contain a `/`, so
       the file lands in a sub-directory `padding +/` that exists in the tracked `webui/screenshots/` tree but not in
       the fresh scratch directory I pointed `SMOKE_SHOTS` at. It is an artifact of where I wrote the screenshots.
   - **New failures: none.**
   - All 11 `discovery.seed` states and my 5 `seed_sources` states pass.
   - The screenshots went to the scratchpad, not the tracked tree, because `AA` was working in the same checkout. The
     Seed-page and fixup-y set is copied to `webui/screenshots/fixup/Y/smoke/`, and the walk's screenshots to
     `…/Y/walk/`.
3. **`pytest -n 4`** (conda, 6 m 15 s): **1988 passed, 19 skipped, 2 failed.** Failure set:
   `test_end_to_end.py::test_discover_adapters_registers_the_expected_count` and
   `test_adapter_spec.py::test_every_shipped_adapter_registers_without_modification`. Both assert 36 shipped
   adapters and find 37; the 37th is `catalogue_manual_labels`, committed by `AA` in `84b51e1`. **Neither is from
   this fixup**, which touches no adapter; it is `AA`'s to update.
   - Under `webui/.venv`: `tests/test_webui_seed_sources.py` 18/18 passed. `test_webui_discovery.py` has 41 tests,
     of which 40 passed; the one failure is the standing
     `test_the_scoreboard_cells_are_the_tables_own_numbers` (README).

**Commits:** `12b16f0` (red tests) · `7bbed7e` (server) · `9b3075f`, `ff90892` (`api.ts`, appended) · `811480c`
(Seed page) · `776e0d0` (Explore) · `c60f022` (Review) · `051a308` (smoke states) · this report.

`docs/rq_roundA/RQ2-exemplar-seeded-search.md` is updated per that folder's README. The folder is still
untracked in this checkout (the researcher's working docs), so the update is on disk and not committed.
