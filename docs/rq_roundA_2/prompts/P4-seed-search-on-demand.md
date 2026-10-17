# P4 — Seed search computes only when asked, and offers every family as a seed

Read [`00-common.md`](00-common.md) first. Commit prefix **`a2-p4:`**. Can run beside P1.

## In plain words

Choosing a seed on Discovery › Seed search starts a search straight away, and so does changing a channel, the section,
the scale bank or the exclusion slider. Dragging the slider starts one search per step. Even the preview is heavy: up
to 200 random-noise copies per channel. Nothing should run until the researcher presses **Run preview**, which shows
its estimated time first, or **Run seed search**.

Separately, the list of seeds is narrower than the Library. Its "Family medoid" tab is 16 old catalogue spans, not the
Library's families. Its family filter reads the wrong grouping. And a seed taken from that tab cannot add its accepted
matches to the Library.

## What is true today (read 2026-10-17)

### A. What starts compute

- **The loader:** `webui/client/src/discovery/SeedPage.tsx:88-93`, a `useSourced` loader over `getSeedResults(seed.id,
  channels, bank, exclusion, section, …)`.
  - It runs on mount and on every change of seed, channels, section, bank scales/overlap or exclusion.
  - `seedResults` (`webui/client/src/api/discovery.ts:317`) **POSTs first**, and POSTs again when the job vanished after
    a restart (:327-333).
  - The exclusion slider is not debounced (`kit/forms.tsx:150`, `step={1}` at :469).
  - The cut is not a dependency: it filters on the client and PUTs the draft after 400 ms.
- **Server, `POST /api/discovery/seed/results`** (`webui/server/discovery.py:1948-2003`):
  - It returns a cached result or joins a running job with the same key (`_live_seed_jobs`, :1933-1945).
  - Otherwise it starts a job: MASS candidates per channel (k = 200), then null draws.
  - The draws are `min(want, max(5, 4,000,000 // n_samples))` (:1608). At 1 Hz that is 200 draws up to about 5.6 h of
    scope, falling to 5 draws from about 222 h.
- **`GET` of the same path** (:2006-2039) **never computes.** It returns the cached result, a running job's progress, or
  "no result for this query yet".
- **`GET /api/discovery/seed/estimate`** (:1651-1691) computes nothing. It gives the preview's and the run's draws,
  seconds and route. The page shows it in the CostChip (:198-201) and the apply bar (:896-904).
- **Cancel:**
  - `POST /api/jobs/{id}/cancel` exists, but cancel is checked only between draws
    (`Working/discovery/seeded_search.py:288-289`);
  - a cancelled preview is then **stored as if complete** (`_store_result`, :1987), and a run can reuse that short null.
- **A run without a preview:**
  - *Run seed search* with `nullMode='preview'` computes the preview inside the run job (`_preview_prelude`, :2743-2774),
    so it works.
  - But the page then has no recommended cut (`threshold = chosen ?? recommendedCut`, :118-120). The run sends
    `maxDistance` 0 and keeps all 200 matches per channel.

### B. Where the seeds come from (`GET /api/discovery/seeds`, `discovery.py:1354-1401`; picker `SeedPage.tsx:318-381`, 8 a page)

- **Library exemplar** (`_library_page`, :1242-1286): every `motif_entry` except the held-out recording. The family
  filter reads only **the newest single-motif grouping** (:1178). Today that is grouping 9, *motifs · amplitude* (6
  quantile bins), so 3,562 of 3,627 entries read "no family yet", and grouping 5's 149 shape families cannot be reached.
- **Explore selection** (`_explore_candidates`, :1326-1334): 10 annotations with verdict `seed`.
- **Family medoid** (`_medoid_candidates(_seed_store())`, :1311-1323):
  - it is **not** a Library grouping, but the drop-motif store `DATA/library_seed/drop_motifs5`: 410 events by
    catalogue span, 16 seeds, no paging or filters;
  - a `medoid:` seed gets **no `entryId`**, because `_seed_by_id` (:1144-1164) looks an entry up only for `library:`
    ids;
  - so *Add N matches* refuses it ("this run's seed is not a Library entry", `webui/server/library.py:3497-3499`).
  - **Both of the researcher's judged dip searches used such seeds:** discovery runs 9–11 (`dip_search`, 256 of 263
    accepted) and 13 (`dip_search_allch`, 94 of 104).
- **What already works:** Library › Family *Seed search in Discovery* (`library/FamilyPage.tsx:512-514`), the Atlas and
  Edges all link `discovery/seed?entry=<exemplarEntryId>` with a real entry. Any `source:rid:start:end` id is accepted
  by `/seed/setup?seed=`.

## The change

1. **Nothing computes until a button is pressed.**
   - `seedResults` peeks (GET) and never POSTs on its own: it returns a cached result, joins a running job, or reports
     "not run yet".
   - A **Run preview** button starts it and shows the estimate beside it: seconds, draws, channels, and whether the rate
     was measured or a default.
   - The controls (seed, channels, section, bank, slider) only change the query.
   - *Run seed search* is unchanged.
2. **Cancel a preview** from its progress view (`POST /api/jobs/{id}/cancel`). A cancelled job is never stored: add
   `if job.cancel_event.is_set(): return None` before `_store_result`.
3. **A run with no preview has no recommended cut.** Either require a typed cut or say on the apply bar "no cut: all
   k = 200 matches per channel kept". Choose one, and say which in your report.
4. **More seeds:**
   1. The Library-exemplar tab's family filter takes a **grouping** (a `grouping` parameter on `/api/discovery/seeds`,
      reusing `library._resolve_grouping`). By default it is the newest *shape-distance* single-motif grouping.
   2. A **Family medoids** list shows every family of that grouping by its medoid (`grouping_assignments.is_medoid = 1`
      → `library:` ids), paged and filterable.
   3. The 16 store medoids stay, renamed **Catalogue spans**, because they are not Library families.
   4. **A medoid seed whose span equals a Library entry's span resolves to that entry** (call `_entry_for_span` for
      `medoid` ids too), so *Add N matches* works for it.
   5. Backfill `entryId` on the existing medoid seed runs (discovery runs 9–13) with an idempotent, audited migration
      or script that changes nothing else, so their accepted matches can be added.
5. **Smoke:**
   - `webui/smoke_pages/library_edges.json:4` (`fixup-v-scale-bank-searches-every-length`) now needs a Run-preview
     click;
   - the seed states in `discovery.json:248-267` and `:323-340` pass only because `smoke.py:1163-1209` precomputes the
     preview under the page's key, so keep that working;
   - add states in `webui/smoke_pages/a2_p4_seed.json`: not previewed (estimate shown, nothing running), a preview
     cancelled, and the grouping-aware picker.

## Tests

- **The client computes nothing on load.** Run a smoke state plus the bridge's job count (`/api/health` `jobs`) before
  and after loading the Seed page with a seed and no cached result: the count does not change.
- **A cancelled preview leaves no cached result** (`tests/test_webui_*`, `webui/.venv`).
- **`/api/discovery/seeds?grouping=5`** lists every family's medoid as `library:` ids with their entries.
- **The backfill:**
  - a `medoid:` seed run with a matching Library span gets its `entryId`, and *Add N matches* becomes available;
  - running the backfill twice changes nothing the second time.

## Acceptance

- [ ] **Nothing runs on its own.** Picking a seed, moving a slider or changing scope runs nothing; Run preview shows its
      estimate first; Run seed search behaves as before.
- [ ] **Cancel works.** A preview can be cancelled, and a cancelled preview is never reused.
- [ ] **Every family is reachable.** The picker reaches every family of a chosen grouping, and the catalogue spans are
      labelled for what they are.
- [ ] **The dip searches can feed the Library.** The two judged dip searches can add their accepted matches to the
      Library.
