# Prompt 03 — Library: real motifs, sequences and groupings

Stage 3, 2026-09-21 → 22. Branch `main`, 15 commits prefixed `wire-library:`. Run in the main checkout
**alongside Prompt 04**, which was live in the same tree throughout (see "Sharing a checkout" below).

The Library was empty: `motif_entry`, `motif_member` and `motif_edge` held **zero rows** against 40 runs,
732 detections and 11,269 human annotations. It now holds **3,603 motifs across 149 shape families and 148
sequences**, and every Library page reads them.

---

## 1. What was imported on this machine

Run through `scripts/populate_library.py`, which exists so that "how this machine's library was populated"
is a file someone can read and re-run rather than a command that happened once. It refuses to run without
a backup newer than the database, and `--dry-run` reports everything while writing nothing (verified by
comparing row counts, not by trusting the flag).

| source | rows in | result |
|---|---|---|
| `DATA/library_seed/drop_motifs5/motifs` | 410 | **410 created**, 17 near-duplicates flagged |
| `Plots/drop_motifs10/motifs` | 3,511 | **3,189 created**, **61 exact duplicates** of seed events resolved onto their entries, 256 excluded (`reishi_1hz`), **5 span conflicts** counted, 420 flagged |
| `Plots/drop_motifs11/sequences.csv` | 118 | **118 of 118 resolved**, 1,646 member events in order |
| `DATA/catalogue/signal_catalog.xlsx` | 37 | 32 already imported, **5 unimportable**, each with a stated reason |
| the `annotations` table | 11,269 | **30 human sequences**, **4 type-specimen entries**, 11,234 triage rows correctly not imported, **1 refused as held out** |

**Final state:** 3,603 `motif_entry` / `motif_member` / `motif_member_revision`, 13,349 `motif_entry_tags`,
148 `sequences` (118 machine + 30 human), 1,646 `sequence_members`, 3 `groupings`, 7,324
`grouping_assignments`. **The 11,269 annotations are untouched.**

`3,511 = 3,189 created + 61 already present + 256 excluded + 5 span conflicts`, and
`3,603 = 410 + 3,189 + 4 type specimens`. Both verified by the data-truth critic from the source files.

### Duplicates found

- **61 exact duplicates** between the seed bundle and drop_motifs10 — same content hash, so one entry with
  two members, never a second entry.
- **437 near-duplicates flagged** (17 within the seed, 420 in drop_motifs10): reciprocal IoU ≥ 0.5 with
  onset agreement inside 0.25 × the candidate's duration. **Flagged, never merged** — they keep their own
  entries and the flag records both spans and the two thresholds it was judged under.
- **5 span conflicts**: two shapes claiming one `(recording_id, start_idx, end_idx)`. Counted with a
  warning and skipped rather than overwritten — two detectors disagreeing about what is at one place is a
  real disagreement, not a duplicate.

### Sequences flagged `needs_extraction`

**30 of 148** — every human-catalogued sequence. Their events were never extracted, so they are stored
with `needs_extraction = 1` and **no `sequence_members` rows**: the claim is recorded, the events are not
invented. `Working.library.importers.annotations.sequences_needing_extraction(conn)` returns them, and
`GET /api/library/sequences?needs_extraction=1` is the route **Prompt 05's "extract events" queue reads**.

The 118 machine sequences resolved all their events (1,646 members, positions contiguous from 0).

### Three deliberate exclusions

- **`Plots/drop_motifs12a` is not imported.** Both stores are marked `partial` (region A of the Lion's
  mane recording was never detected), 844 of 1,077 rows carry `recording_id = -1`, and its two floor
  policies are two views of one detection that would collide on `motif_entry`'s UNIQUE span. The importer
  reads it and refuses it by name (`PARTIAL_STORE_REFUSAL`); `--include-12a` runs it anyway.
- **`reishi_1hz` excluded** from drop_motifs10 (256 rows): the same organism as `reishi_10hz` at a second
  rate, sharing `(catalogue_id, channel)`. Sequence recovery reproduces **118/118 with it excluded and
  52/118 with it in**. A parameter, not a literal.
- **The 11,234 `imported_10min` annotations are not library content.** A ten-minute sort grid — every one
  exactly 600 samples — whose longest run of adjacent interesting windows is 3, so it encodes no
  sequences. Split by `source`, not by span length, because a future grid at another window size would
  break a length rule.

---

## 2. Tables added

All additive, each its own `_migrate_*` function, `init_db()` still idempotent. The migration test proves
the path the real 4 MB database took: an old-schema database with rows in it keeps them.

| table | one row is |
|---|---|
| `motif_member_revision` | one revision of a member's span; rev 1 is what the matcher compares against |
| `sequences` | a run of events in order, with `origin` choosing its rule-5 door |
| `sequence_members` | one event of a sequence, in position order, with its gap |
| `groupings` | one saved question asked of the catalogue |
| `grouping_assignments` | one member's place in one grouping; `family_id IS NULL` means omitted, with a reason |
| `hand_edits` | one edit, keyed by **content hash** so it survives a regroup |
| `window_sets` | a saved window set (spec P18); bulk bounds stay on disk |

Plus nullable columns: `motif_entry.{content_hash, channel, fs, source_kind, source_store, source_ref}`
and `motif_member.{content_hash, channel, current_revision_id}`.

`webui/server/writes.py` learned `groupings`, `grouping_assignments`, `hand_edits` (human) and
`window_sets` (machine). **`sequences` and `sequence_members` are deliberately on neither list** and the
docstring says why: they are the one pair whose side is decided per row by `origin`, so naming a side for
the table would make the wrong half a quiet crossing.

---

## 3. Routes and client

**20 routes** under `/api/library` (`webui/server/library.py`): counts, groupings, recurrence, families,
sequence-families, family/{id}, omitted, grouping-editor, windowsets, templates, sequences, grouping
run/save (as jobs), import dry-run/import (as jobs), import/bundles (read from the **registry**, not a
disk scan), hand-edits post/delete, and real family/atlas downloads in JSON and CSV.

**Client functions switched: all 11** `demo(FIXTURE)` reads in `src/api/library.ts` are now `live(...)`,
plus three new live reads (`getImportBundles`, `getRecordingGroups`, and the sequence-aware family read) —
14 `live()` call sites. **No read is left on `demo()`.** Every exported name, signature and return type is
unchanged, so no page changed its call sites.

The pages now draw **real decimated mV**. Until this ticket no Library page rendered a waveform that came
from the data — every trace was `motifShape(shape, amp, seed)` synthesis.

**Grouping methods available: three**, registered by name the way `Adapters/registry.py` registers blocks —
`ward` (the PRD default: Ward linkage on resampled, z-normalised vectors under the scale-invariant
distance), `feature_bins` (quantile / log-spaced / fixed edges) and `labels` (tag, provenance). Three
rather than the two asked for, because spec §8.2 names three basis *kinds* and each needs one.

### The default cut was measured, not inherited

The frontend fixture carried 0.42. On the real catalogue that omits **29%** of it, every one for
`group_too_small`:

| cut | families | assigned | omitted |
|---|---|---|---|
| 0.42 | 151 | 2,545 | 29% |
| **0.60** | **149** | **3,239** | **10%** |
| 0.80 | 115 | 3,480 | 3% |

The family count is flat from 0.42 to 0.60 while omission falls by two thirds, so the extra omission buys
no structure. Three groupings are saved, not one — spec §8.2 says earlier groupings stay saved, and it
gives the grouping bar real choices: **g-04** (cut 0.42), **g-05** (cut 0.60, the default) and **g-06**
(sequence families: 26 families over the 118 sequences with resolved events).

---

## 4. Critics

Three read-only critics on Opus at medium effort, disjoint scopes, driving the live bridge in `--project`
mode against the real database.

| critic | score | headline |
|---|---|---|
| **storage** (clarity + edge cases) | **7 / 10** | identity and dedupe hold; the document had two passages the code contradicts |
| **data truth** (arithmetic from the files) | **3 / 10** | every aggregate reconciled — and the one join that turns rows into what the Atlas draws was keyed on the wrong column |
| **function** (drove every page) | **4 / 10** | the recurrence matrix inverted its own legend; 97 of 149 cards were flat lines |

### The P0s, and what they were

**The groupings referenced entries where they must reference members.** `grouping_assignments.member_ref`
held `motif_entry.id`. The two tables' ids drift apart the moment an event resolves onto an existing entry
(3,608 vs 3,603), and **5,670 of 7,206 assignments pointed at a member whose content hash was not the one
the assignment recorded — 78.7% of the motifs the Atlas drew were not the motifs that had been
clustered.** Rebuilt: 151/149/26 families, *identical* to before, because the clustering was never at
fault. Zero dangling refs and zero hash mismatches now.

**The recurrence matrix lied in both directions.** A channel with no `reviewed_spans` row got no cell at
all, and the client renders a missing cell as "reviewed, no members" — so 2,122 never-looked cells read as
examined-and-empty, and 2,229 real members read as "no members found". That is exactly the distinction
spec §8.4 exists to preserve. The bridge now emits a cell for every channel of every non-held-out
recording, and the client renders four states including members-on-a-never-reviewed-channel, which had no
rendering at all.

**Sequence families were unreachable.** The family page passed the motif grouping id for both units and 19
of 26 sequence labels collide with motif labels, so "Open all 10 sequences" silently opened a *different
family*. `get_family` now takes an explicit unit and never substitutes across units.

**A rail printed "order kept 14 of 10".** Numerator counted the exemplar's events, denominator counted
member sequences, and an unfiltered join multiplied compositions by the number of saved groupings. Now
computed properly — and **absent, with a note, when the events do not resolve**.

**The import check inverted its own count**: "safe to run twice — 0 of 3,511 rows already describe a shape
this library holds", on the same response whose `creates` list said `already_present × 3250`.
`n_duplicate` counted only `MEMBER_ADDED` though its docstring promised both.

**97 of 149 atlas cards were flat lines** under a caption asserting the amplitudes compare — one shared
±3.8 mV domain over families whose median peak is 0.0009 mV. PRD Part 2 forbids normalising the cards, so
the domain is now a high percentile and clipped families are **marked**, not normalised.

**The sequence-family fix needed a second pass.** The bridge learned an explicit `unit`, but the client
never passed one — `FamilyPage` asked with the *motif* grouping id for both units — so the P0 was still
live after the fix wave and the smoke run caught it. Driven end to end: the sequences atlas's "Open all 10
sequences" on `F-31` landed on the *motif* `F-31`, different members, no indication of a substitution.
`unit` now threads `api.ts` → `api/library.ts` → `FamilyPage`, and the sequences atlas links with it.

**The amplitude histogram's axis stated a range the data does not occupy** — `AMP_DOMAIN` was the
fixture's (0.1, 0.4) mV where real depths run 0.006–0.015, so every member of every family clipped into
bin 0 under an axis labelled 0.1/0.25/0.4. Found by opening the Atlas and reading the payload behind a
card. The domain is now measured per family and echoed, so the bars and the axis cannot disagree.

### P1s fixed

Shape was "drop" on all 149 families (the live split is 121 trough / 28 sharkfin — the code read a legacy
empty column); reviewed-% summed overlapping spans instead of unioning (19.3% → the true 18.0%); "judged"
on a sequence counted who *drew* it; hand edits matched on a **recycled label** (g-04 and g-05 share 60
labels of which 59 have no shape in common, so an edit against one `F-06` silently joined the other — now
keyed by the family's medoid content hash, which also matches a family the re-clustering *renamed*); the
dry run could not report the span conflicts the real run hits; near-duplicate flags recorded the
candidate's span twice and lost the incumbent's; the omitted drawer stated one false reason for all 364
entries while the real one was already in the payload; `/omitted` never returned sequences; the Window
sets Import button was dead in the only state this installation can show; the four type-specimen entries
carried no tags though their annotations carry three each; four dangling assignments were dropped in
silence.

Two claims in the standard were **corrected rather than implemented**: §2.5 promised edges are "marked
stale" and nothing marks them (`stale_edges()` returns the ids; the caller owns the recompute), and §5.1
named `__raw_mv` as the hashed waveform where the code hashes `__detrended_mv` — identity is the one thing
in that document that has to be exactly right, because changing it re-hashes every entry.

---

## 5. Gates

- **pytest: 1,513 passed, 5 skipped, 0 failed** (baseline at the start of this ticket: 1,183 / 3 / 0). 226
  of those are `tests/test_library_*.py`. Compared as failure *sets*: the baseline's set was empty and so
  is this one.
- **`npx tsc -b`** clean; **`npm run build`** clean.
- **`webui/smoke.py --only library`**: **51 screenshots, 0 failures, 0 browser console errors, 0 server
  tracebacks**, against the bridge in `--project` mode on 8765. Screenshots in
  `webui/screenshots/wiring/03/`. The states were rewritten twice: once to live content (62 → 51 states,
  25 fixture-era ones deleted with reasons, the window-set surfaces kept as honest empty states), and
  again after the fix wave moved the pages on purpose.
- One regression this ticket caused in a file it does not own, fixed and reported:
  `tests/test_import_drop_motifs.py` asked for `SELECT m.*, rec.channel` over a
  `motif_member`/`recordings` join, and `motif_member` gained a `channel` column, so sqlite returned the
  member's (NULL on that importer's rows). Aliased.

---

## 6. Sharing a checkout with Prompt 04

Both agents ran in the main checkout on `main` with path-scoped commits, as the plan says. Two things
worth recording:

1. **Prompt 04's commit `6f77d2f` carried five of my client files** (`api.ts`, `api/library.ts`,
   `chrome.tsx`, `EmptyLibrary.tsx`, `RecurrencePage.tsx`) because it was path-scoped over a directory
   holding my uncommitted hunks. Content verified intact. The same thing happened to Prompt 01's
   `schema.py` hunk inside Prompt 02's `f1ecd4e`, so this is the second occurrence and the history should
   say so. **A path-scoped commit carries whatever is in the file, not whatever you wrote** — the only
   real defence is committing a shared file the moment your hunk is complete, which is what I did with
   `schema.py`, `app.py` and `writes.py`.
2. **`Working/library/dedupe.py` imports `Working/discovery/matching.py`** for `DEFAULT_IOU` and
   `DEFAULT_ONSET_FRACTION`. That is a Library → Discovery dependency on a module Prompt 04 owns, taken
   because spec §4.6 says the matching rule's default is editable in **one place only** and two literals
   that agree today would drift. It is committed code (`287e1e6`) and the request file tells 04 it is
   load-bearing — but the *right* one place is arguably Settings, and a later ticket should move it there.

`docs/prompts/wiring/requests/03-to-04.md` was published in the first hour with the table shapes, the
identity rule, and two data facts that would otherwise have cost 04 a day (sequences.csv binds to
drop_motifs10 and **not** to the tracked seed bundle; `reishi_1hz` double-counts under any
`(catalogue_id, channel)` grouping).

---

## 7. Requests to Prompt 05 (Review)

- **The "extract events" queue** reads `GET /api/library/sequences?needs_extraction=1` (30 sequences
  today, all human-catalogued). Each carries its span, its claimed `n_events` where the note stated one,
  and its `annotation_id`. Writing the extracted events back should go through
  `Working/library/revisions.py` so rev 1 stays "what the matcher compares against" (spec §4.2 rule 4).
- **P21 (`S` promotes to the Library)** writes `motif_entry` + `motif_member` + revision 1 in the same
  transaction as the verdict, and **Ctrl-Z must remove both** — spec §10.4 makes them one undoable unit.
  The exemplar keeps span, recording, channel, **content hash** and the run's recipe hash;
  `Working.library.identity.content_hash` is the one function that produces that hash.
- **Hand edits are keyed by content hash**, not by member id, and a family is named by its **medoid's**
  content hash. If Review offers "remove from family", write it through `Working/library/hand_edits.py`
  rather than deleting an assignment — a removal has to survive the next regroup.
- **437 near-duplicate flags** are in `audit_log` with kind `library_near_duplicate`. They are candidates
  for a Review queue and nothing surfaces them today.

---

## 8. Questions for the user, with the default taken

Each was decided so work could proceed; each is reversible.

1. **Which stores to import.** *Default taken:* the tracked seed bundle and `drop_motifs10`;
   `drop_motifs12a` read but refused (partial, `recording_id = -1` on 844 rows, two floor policies
   colliding on one span). *If you want 12a in:* `--include-12a`, and decide first whether to re-bind its
   Lion's mane rows to recording 542 or import them unbound.
2. **The `reishi_1hz` control corpus.** *Default taken:* excluded, because it double-counts one organism
   (118/118 sequences recover without it, 52/118 with it). *Reversible:* `exclude_corpora=()`.
3. **The default cut.** *Default taken:* **0.60**, measured (§3 above), not the fixture's 0.42. Both are
   saved as groupings so you can look at either. Spec §9.10 says this default belongs in Settings ›
   Library groupings; the `settings` table has no row for it yet, so it currently lives in
   `scripts/populate_library.py`.
4. **The onset-agreement coefficient in the matching rule (§4.6).** *Default taken:* **0.25 × the
   candidate's own duration.** The spec says "scaled to the candidate's own duration" and gives no
   coefficient. It is in one place (`Working/library/dedupe.py`) and recorded on every flag.
5. **The hashed waveform.** *Default taken:* `__detrended_mv`. Detection ran on the detrended trace, and
   hashing raw would let one drop on a drifting baseline and on a flat one become two entries.
6. **Species, corpus and morphology as tags rather than columns**, and the four feature-bin bases computed
   on demand rather than stored — spec §4.4 rejects measured features on Library rows outright. The cost:
   a tag belongs to the shape, not the occurrence, so an entry found in two species carries both
   (§3.4). A future ticket wanting per-occurrence labels should add `motif_member_tags`.
7. **Spike trains are defined and not populated.** `scale = 'train'` exists and `motif_edge` already
   carries what train-to-train edges need. Nothing on this machine writes one; §4 says what a future
   importer must provide.
8. **`judged` reads 0.0% on every family.** Verdicts are matched on exact span equality against a human
   row, and no human annotation shares a span endpoint-for-endpoint with a library member. Not wrong, but
   it is a zero nobody can interpret. Matching by the §4.6 IoU rule instead would make it meaningful —
   that is a change to what "judged" *means*, so it is yours to call.
9. **Template versions and per-run scores have no table anywhere.** Spec §4.5's "no second template store"
   is right, but the Library's Templates rail also wants version history and scores. The pages say "not
   recorded" rather than drawing an empty table that reads as "never scored". Either §4 should call those
   aspirational or a `template_versions` / `template_scores` pair is missing from it.
10. **The sequences atlas shows 1 of its 26 families.** The grouping bar's default `≥ 10 members` filter
    is applied to sequence *counts*, and `F-31` is the only sequence family with ten sequences in it. Not
    a defect — the filter is doing what it says — but the default is wrong for a unit whose families run
    2–10, and it makes the sequence atlas look empty. A per-unit default for that filter is the fix;
    it is a Settings › Library groupings decision, so it is yours.

---

## 9. What is left

Honest list of what this ticket did **not** finish.

- **Hand edits are never written from the UI.** `POST`/`DELETE /api/library/hand-edits` exist and work,
  `Working/library/hand_edits.py` is tested including survival across a regroup, and members carry the
  `contentHash` the route needs — but every hand-edit control on the Family page is still a
  `not wired yet:` toast writing to the in-memory store. `hand_edits` holds 0 rows.
- **`window_sets` holds 0 rows and nothing writes one.** The table, the route and the page are built;
  saving a set is Analyse's act (spec P18: "any block outputting `WindowSet` offers *Save window set*"),
  which is Prompt 01's surface.
- **The `custom` grouping basis cannot work end to end** — `_grouping_items` never puts `cluster_label`
  on an item, so every member omits as `no_label`. The clustering select is live; the parameter has
  nowhere to land.
- **437 near-duplicate flags are in `audit_log` and no surface shows them.**
- **The 437 existing flags keep the old, wrong span shape.** The fix names both spans correctly for new
  flags; re-flagging the existing ones needs a re-import.
- **The four type-specimen entries are still untagged in the live database.** The importer fix is right
  and tested, but it short-circuits on `already_imported`, so those four rows need dropping and
  re-importing to pick their tags up.
- **`motif_edge` is empty.** Nothing in this ticket computes edges; `match_span_to_entry` is the path and
  Discovery's seeded search is its most likely caller.
