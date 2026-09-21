# Report — Prompt 04: Discovery, seeded search and template application on real data

Run 2026-09-21 → 22 on `main`, in the main checkout. Prompt 03 (Library) had **not** started when this began
— no `docs/LIBRARY_STORAGE.md`, no `Working/library/`, `motif_entry` at 0 rows — and started partway through;
its `wire-library:` commits interleave with the `wire-discovery:` ones below. Ports: bridge **8766** for the
whole of this prompt after 03 appeared (8765 for the first hours, when nothing else was running), Vite not
used — the client was built and served from the bridge. The server was stopped at the end.

## What runs for real

### 1. Seeded search (§7.6)

A seed is taken **by content** — `"<source>:<recording>:<start>:<end>"`, resolved through
`Working.discovery.seeded_search.seed_from_content`, which hashes the samples themselves — so it needs no
`motif_entry` row, which matters because that table is empty. The three sources §7.6 names all exist:

| Source | What it is here | Count on this machine |
|---|---|---|
| Library exemplar | `motif_entry` rows when there are any; **otherwise** the 24 deepest pure events of `DATA/library_seed/drop_motifs5/motifs` | 24 |

| Family medoid | one per `span_key` of that store, the member closest to the family's median depth | 16 |
| Explore selection | `annotations` with verdict `seed` (Explore's *Take span for Review*) | 0 today |

Every payload says which source it used, and the seeds route carries a note naming the store while the
library is empty. **Prompt 03 filled `motif_entry` while this prompt was running — 3 603 entries — and the
Library-exemplar source switched to it with no edit here**, which is what the content-addressed seed id and
the `motif_entry`-first lookup were for. The note disappeared at the same moment, because it only claims the
fallback when the fallback is what is being used. The search itself is the block's own function (`Adapters.detection_seed_matches.
match_exemplar`, imported, not reimplemented) so the candidates the page lists and the `detections` a run
writes come from one function with one trivial-match guard. The **distance profile** is computed here with
`stumpy.mass` — the block returns only the kept matches, and there is no matrix profile behind it.

The **null** is N surrogate realisations of the same section put through the same match function, because
`preprocessing.surrogate` has no `draws` parameter: one call is one realisation at one seed. It is
reproducible from that seed, and a method the block does not implement is **refused out loud** rather than
substituted (see "Questions").

The **cut** re-thresholds distances already in hand; the recommended marker is the largest observed match
distance at which the null is still expected to give at most α matches per draw.

### 2. Template application over a fan-out (§7.1, §7.5)

`Working.discovery.fanout.plan` checks the scope, costs it and routes it **before anything runs**; `start`
runs one target per channel through `run_paired_recipe`, linking them to one `run_groups` row, with the
cancel checked *between* targets so a cancelled sweep leaves a readable partial group. Each run is paired
with its surrogate null (`runs.surrogate_of_run_id`), which is what fills §7.3's *null expects*.

### 3. The scoreboard (§7.3)

Computed from `detections` × `annotations` × `reviewed_spans` under the §4.6 rule, per channel and pooled,
with the hours it pooled stated. Every absent cell is a sentence, never a zero.

### 4. Compare and Compare-every-stage (§7.7, §7.8)

Two chains aligned **by role** from each block's declared category and output type — never from a glyph or a
name — plus set overlap, the disagreement list, and the window pushed through both chains
(`Working.discovery.window_chain`, which uses `execution.py`'s calling convention and writes nothing: no run
row, no detections, no step cache).

### 5. The runs page

Real Discovery runs and jobs, with superseded/discarded handled by real writes (`runs.superseded_at`), and
*Send N unjudged to Review* recording a named queue that is a **filter** over the run's unadjudicated
detections, not a copy of them.

## The core (`Working/discovery/`, UI-free)

| Module | Lines | What it owns |
|---|---|---|
| `matching.py` | 184 | Spec §4.6, both halves, with its own name (`reciprocal_iou_onset`) and its default read from Settings |
| `scoreboard.py` | 411 | §7.3's nine columns, per channel and pooled, and the shape-mismatch warning below |
| `fanout.py` | 434 | The plan (pre-flight, route, ceiling), the run, the per-channel status, the discard |
| `seeded_search.py` | 432 | The seed, the matches, the profile, the null, the cut, matrix-profile reuse |
| `compare.py` | 422 | Role alignment, span comparison, overlap rows, the recipe diff rendered for the wire |
| `window_chain.py` | 189 | §7.8's window pushed through a chain, writing nothing |
| `spans.py` | 70 | The span arithmetic, including the legacy span-relative detections repair |
| `channels.py` | 30 | The electrode-name table, in one place |

## Tables and routes

**Additive migrations** (`Working/database/schema.py`, committed immediately as a shared file):

- `discovery_sessions` — the scope, the null settings, and the page's own state. `run_groups` carries only an
  id and a timestamp by design, so nothing recorded which channel was target 3, which seed a search used or
  where the cut was; and a non-chain job's `result` is `None` after a restart, so the seeded search's
  distances live in this row rather than in the job.
- `discovery_runs` — one row per run in a session: its key, kind, label, colour, template, run group, job,
  parameters and superseded mark.
- `runs.superseded_at`, `runs.superseded_by_run_id` — §7.4's *Discard run*.

**29 routes**, all under `/api/discovery/`:

| Group | Routes |
|---|---|
| session | `GET/PUT /session` |
| runs | `GET /runs`, `GET /history`, `GET /queues` |
| templates | `GET /templates`, `POST /templates/apply` |
| scope | `GET /overview`, `GET /signal`, `GET /fires` |
| scoring | `GET /scoreboard`, `GET /detections`, `GET /detections/{id}/window` |
| seed | `GET /seeds`, `GET /seed/setup`, `PUT /seed/draft`, `POST+GET /seed/results`, `GET /seed/profile`, `POST /seed/run` |
| cost | `POST /plan`, `POST /preview`, `POST /slurm` |
| acts | `POST /runs/{key}/discard`, `/restore`, `/review` |
| compare | `GET /compare`, `/compare/window`, `/compare/stages` |

## Client

**18 of 18 reads live**, zero `demo(` left in `src/api/discovery.ts` (the prompt said 17; there were 18 call
sites, the extra being `getRebindExemplars`, which no component called — it is now served by
`GET /api/discovery/seeds` and the modal reads it). `api.ts` gained the typed call for each route, append
only.

`getSeedResults` is the one that is not a plain read: a seeded search over a section is a job, so the
function POSTs the query, polls the GET form of the same query and resolves when it is ready — the page
still awaits one promise.

Wiring widened three kinds of field to `| null`, and the pages now say what the absence is rather than
drawing a zero: a template's `preview` / `perChannelMin` / `diskGB` (null until a measured Preview has run,
and the card prints the server's note), a disagreement's `otherNearest` (a per-window computation the
stepper reads when it steps there), and `recall` (a value with its hours, or the server's own words).

The three `?state=` deep links named fixture runs no live session has, so they silently did nothing.
`?state=running` now starts a **real** run over the first fifteen minutes of the section; `discarded` and
`failed` target the session's first real run, and the failed row says in its own text that it is the deep
link's doing.

## The one real search

`webui/drive_discovery.py --url http://127.0.0.1:8766` — M2_aug_concat_fs1, **80–84 h** on **CH1_A1** and
**CH8_B2**, seeded from the drop-motif family `id035`'s medoid (`medoid:16:289550:289686`, 136 samples,
content hash `5269afbf4e402963`, on CH16_D2 at the same wall time). The section was chosen for what is in
the database, not for a round number: both channels carry annotations of **both** verdicts there, so
precision has real negatives in it.

| | |
|---|---|
| matches | 400 candidates (200 per channel), z-normalised distance 2.221 – 16.897, 0 already judged |
| null | `phase_randomize`, **50 draws per channel**, 20 000 pooled distances, smallest 3.715 |
| recommended cut | **3.582** — below every null distance, so the null gives nothing at it |
| distance profile | 1 665 distances over 1 800 samples, m = 136 |
| plan | 2 channels, route **unknown** (`detection.seed_matches` declares no estimator), ceiling 1 200 s |
| preview | 1 h sample on CH1_A1, **measured** 0.06 s → 0.2 s per channel, 3 spans → ≈ 24 over the scope, local |
| seed run | `seed_id035`, 2 runs, **4 detections** |
| template run | `drop_detection_v1`, 2 runs, **6 detections** |
| where each run fires | CH1_A1 reviewed 1.50 h (human 4, seed 1, template 1); CH8_B2 reviewed 1.39 h (human 6, seed 3, template 5) |
| scoreboard, seed | found 4 · judged 0 · reviewed 1 · interesting 0 · **precision 0.00** · recall 0.00 over 2.89 h |
| scoreboard, template | found 6 · judged 2 · reviewed 3 · interesting 1 · **precision 0.33** · recall 0.10 over 2.89 h |
| compare | **3 roles differ** (Preprocess, Encode, Detect) → not attributable to one stage; overlap only-A 6 / both 0 / only-B 4; 10 disagreements |
| compare every stage | first differing role Preprocess; A `Source identical · Preprocess A only · Score absent · Encode A only · Detect differs`, B `Source identical · Preprocess absent · Score absent · Encode absent · Detect differs` |
| vs human | only-A 5 / both 1 / only-B 9, against 10 accepted human spans in the section |
| SLURM | `drop_detection_v1_2ch_288000-302400.sh`, a 1 752-character array job over 2 channels |
| discard | 2 runs superseded, **0 adjudications and 0 annotations written**; restore puts them back |
| send to Review | 6 of 6 unjudged into `Discovery · drop_detection_v1 unjudged`, writes `adjudications` |
| the whole drive | 64 calls, **0 unexpected errors** |

The section's default null is 200 draws (Settings › Nulls); the drive used 50 so it finishes in minutes, and
the budget cap (`NULL_SAMPLE_BUDGET`) would allow 277 on a 14 400-sample section before it starts cutting
draws and saying so.

Evidence: `webui/screenshots/wiring/04/summary.json`, and the smoke screenshots under
`webui/screenshots/wiring/04/smoke/`.

## The finding this run produced: a precision of 0.00 that is not about the algorithm

Both runs scored **precision 0.00** on that section. The arithmetic is right and the reason is worth more
than the number:

**11,234 of this project's 11,269 annotations are fixed 600-sample windows** (`source = 'imported_10min'`,
the 10-minute CNN window set). They are *window labels*, not event spans. A real drop, measured on the same
data by the detector that produced the seed store, runs **21 to 4,875 samples, median 179**
(`fall_duration_s` median 28 s). Two spans nested as well as they can be reach an IoU of `min/max`, so a
179-sample event against a 600-sample window reaches **0.30** — under §4.6's 0.5 it can never be counted,
however well it is placed. The `drop_detection_v1` detections in this section are 2 158 samples at the
median, which against a 600-sample window reaches 0.28.

So precision against this ground truth is 0 **by construction** for any detector whose spans are not
between **300 and 1 200 samples** — the band `min/max ≥ 0.5` allows around a 600-sample window. The
statistics critic ran the §4.6 rule over all 732 real detections in the database against every annotation on
their recording: **80 (10.9 %) are even width-compatible with one, and 0 of 732 match one.** Not ~0 — 0. `Working.discovery.scoreboard.shape_mismatch` now detects that case and the
scoreboard states it beside the number:

> the spans cannot match: this run's detections are 2158 samples long at the median and the reviewed
> annotations are 600, so the best reachable overlap is IoU 0.28, below the rule's 0.50. Precision here is a
> statement about the two span shapes, not about the algorithm

This is a question for the researcher, not something to fix by loosening the rule — see "Questions".

## Testing

| Suite | Tests | How to run |
|---|---|---|
| `tests/test_discovery_matching.py` | 16 | conda `pytest` |
| `tests/test_discovery_scoreboard.py` | 29 | conda `pytest` |
| `tests/test_discovery_fanout.py` | 16 | conda `pytest` (runs real fan-outs; ~2 min) |
| `tests/test_discovery_seeded_search.py` | 29 | conda `pytest` |
| `tests/test_discovery_compare.py` | 15 | conda `pytest` |
| `tests/test_discovery_window_chain.py` | 4 | conda `pytest` |
| `tests/test_webui_discovery.py` | 35 | `webui/.venv/Scripts/python.exe -m pytest` (skips under conda — no FastAPI) |

144 tests. The first commit of the prompt was tests only and red
(`0e15af2`, `ModuleNotFoundError: No module named 'Working.discovery'`).

## Three defects the live drive found that no unit test would have

1. **Compare drew five absent cells and reported "0 roles differ"** over two chains that share nothing. A
   recipe step carries its stage and algorithm apart (`{"stage": "detection", "algorithm": "threshold"}`)
   while the registry is keyed `"detection.threshold"`; the bare lookup found nothing, and because an unknown
   block is deliberately *skipped* rather than raised on — an old recipe must still render — the failure was
   silent. `compare.qualified()` builds the name; three regression tests.
2. **Applying the same template twice emptied the first run.** `execute_recipe` is idempotent, so the second
   fan-out is *made of* the first one's runs, and re-pointing their `run_group_id` moved them out of the
   earlier group: a run that had results a minute earlier read "0 found". A run now keeps the first group it
   joined, and a Discovery run records the run ids it is made of.
3. **Discard 500'd** — `supersede()` still keyed its reason update on a `run_group_id` that is None when the
   caller names run ids.

Plus: the scoreboard's null column was always empty because the fan-out ran without its paired surrogate;
the symbolic stage thumbnail read `Encoding.data`, which is `Encoding.values`; and the core's copy of the
electrode-name table had already drifted from the bridge's — it named CH1_A1 `CH0_A1` — which is why the
table now lives in `Working/discovery/channels.py` and `webui/server/corpus.py` delegates to it.

## Critics

Read-only, disjoint scopes, Opus at medium effort, every finding carrying a number the critic computed
itself.

### Statistics critic — **6/10**, all P0s and P1s fixed

| | Finding | Fixed by |
|---|---|---|
| P0 | The seed page's "null gives N" was a raw pooled count, not a per-draw expectation — ten-fold too big on a ten-draw search. Invisible at the recommended cut, which sits below every null distance and reads 0 either way. | The wire carries the per-channel draw count; the page divides by it. `cut_counts` was wrong by the same factor and is now right. |
| P0 | The run total's recall was an hours-weighted mean of per-channel ratios. Ten positives found in one hour and ten missed over ten gave **0.09** where the run found **10 of 20**. Precision on the same row was count-pooled, so two cells under one heading used two rules. | Counts are pooled; `pooled_h` still states the scope. The pinning test could not tell the two rules apart (equal positive density per hour) and was rewritten with a fixture that can. |
| P1 | The total's × null divided every channel's `found` by only the channels carrying a surrogate: **4.0** under four rows that each read **2.0**. | Numerator restricted to the same channels, with `x_null_scope` when the null is partial. |
| P1 | "Null expects" was one surrogate realisation presented as an expectation; §9.4 asks for 200 draws. | Every paired null is averaged and the row states `null_draws`. |
| P1 | Both × null paths went silent exactly when the null result is strongest (a null that found nothing). | `cut_counts` carries the note the scoreboard row already had. |
| P2 | `alpha` and §9.4's multiple-comparison correction never reach `recommended_cut`. | **Not fixed** — see "Left". |
| P2 | `shape_mismatch` fired only at exactly zero precision and hid bimodality. | Fires whenever the typical pair cannot match, and names how many detections are outside the feasible band. |
| P2 | The report said the feasible band is 400–900 samples; it is **300–1 200** (`min/max ≥ 0.5` around 600). | Corrected above. |

It also verified as correct: every §4.6 boundary (IoU == 0.5 passes, onset gap == tolerance passes), that
the candidate owns the onset scale and that swapping the arguments changes that and nothing else, that the
onset half is not vacuous given IoU ≥ 0.5, the one-to-one matching and the duplicate case, every cell of a
hand-built scoreboard fixture, "already judged" being genuinely time-gated on both branches, the null's
reproducibility from its seed, `recommended_cut` against its own definition at five draw counts, and
`shape_mismatch`'s arithmetic at its boundary.

### Data-truth critic — **8/10**, all P1s fixed

| | Finding | Fixed by |
|---|---|---|
| P1 | The report's cited `summary.json` was never written — the drive had aborted at the stages step — so the headline table was unverifiable. | The drive was fixed and re-run to completion; `summary.json` is committed and the table regenerated from it. |
| P1 | A row could print "no detections in the reviewed overlap" beside a recall of 0.167 **derived from exactly such a detection**: precision gated on the detection's onset, recall on the annotation's. | One criterion for both halves, stated in `reviewed_criterion`. This is why the template run's precision moved from 0.00 to 0.33 between drives. |
| P2 | The seeded-search cache key named neither the recording nor the matching rule; four registered files share the channel names CH1…CH5. | Both are in the key. |
| P2 | `discovery_sessions` and `discovery_runs` were on neither rule-5 list. | Added to `MACHINE_TABLES` with the reason. |
| P2 | Send-to-Review keyed on one run group while every other route uses the run ids a Discovery run records. | Counts the union over the run's own runs, and the descriptor carries them. |
| P2 | "the 35 excel_catalog annotations" is 31 `excel_catalog` + 4 `manual_ui`. | Corrected above. |

It re-derived, with its own `stumpy.match` and its own SQL and its own implementation of §4.6 written from
the spec text: the 400 candidates and their distance range; the exclusion gap (35 samples = ⌈m/4⌉+1, so the
`exclusion_note` is true and a locked "m/2" would have been a false label); every `judged` flag; the
recommended cut on two different searches; every scoreboard cell of both live runs; that `atH` is
channel-absolute; that all 50 runs' index frames are handled and none is double-shifted; that the held-out
file's 12 detections reach no payload through any of ten routes; that no Discovery write path touches a
human table; and that the content hash is the SHA-1 of the seed's 136 samples.

## Questions, with the default taken

| Question | Default taken |
|---|---|
| Settings › Nulls names *circular shift of the channel* for the seed-search kind; `preprocessing.surrogate` implements `phase_randomize` and `block_shuffle` only. | **Refuse it out loud.** `resolve_null` returns `supported: false` with a sentence naming the block and what it does implement, and the page prints that instead of a method and a draw count. Falling back silently would put "circular shift 200×" over a different computation and make × null unfalsifiable. Note also that a circular shift is a *degenerate* null for a shape search: shifting a channel leaves the multiset of its z-normalised subsequences unchanged except at the wrap, so the distance distribution would be the original's by construction. **The chip on the page should probably change rather than the block.** |
| Precision is ~0 against the 10-minute window labels for any detector whose spans are not window-shaped. | **Keep §4.6 and say so.** The rule is the spec's and changing it is a versioned act (§4.6). The scoreboard states the mismatch beside the number (above). The alternatives, for the researcher: (a) treat `imported_10min` rows as *window* labels and score them with a containment criterion rather than IoU; (b) re-cut the ground truth as event spans; (c) scope precision to the 35 non-window annotations (31 `excel_catalog`, 4 `manual_ui`), which are event-shaped. |
| §7.6 locks the trivial-match guard to m/2; the block runs under `stumpy.match`'s m/4. | **Say what really ran.** `recommended_params` returns an `exclusion_note` and the page prints it rather than drawing a locked "m/2" over a search that used something else. Request filed to Prompt 01 to add the parameter. |
| `detection.seed_matches` declares no estimator, so a plan containing it costs 0 s and would route local. | **Report `unknown`,** naming the uncosted steps, and let §7.1's *Preview on a sample* supply a measured number. |
| A disagreement's "how close did the other side come". | **Computed per window, not per list.** The list says how it is ordered rather than implying a margin it has not computed; the stepper reads the real curve from `/compare/window`. |
| How wide is a "reviewed" detection? | **Its onset inside the reviewed coverage.** Stated on every row as `reviewed_criterion`. The reviewed spans here are ~600 s windows and detections run from seconds to hours, so "the human saw most of it" would score almost nothing and "overlaps at all" would credit a detection that brushed the edge. |
| Does a Discovery queue get its own table? | **No** — a descriptor on the session row, contents by `run_group_id` through `ReviewQueue`. Offered to Prompt 05 as a table if it wants one. |
| Matrix-profile reuse in a seeded search. | **There is none to make.** `detection.seed_matches` calls `stumpy.match` directly and cannot consume a profile; `USES_MATRIX_PROFILE = False` records it and the plan says so. Reuse is implemented for the matrix-profile *template* path (`find_reusable_profile`, matched by recording, window and span). Nothing on M2_aug is reusable in any case — all ten registered profiles are on M2_concat, M2_concat CH2/CH13 and Mushroom_260720. |
| The first session's scope. | **The four hours these channels have reviewed most of**, not the whole 721-hour recording: every read would scan the lot and a seeded search over it with 200 draws is hours of work nobody asked for. |

## Left, with estimates

| What | Why it is left | Estimate |
|---|---|---|
| §9.4's `alpha` and the multiple-comparison correction never reach `recommended_cut` | They are Settings keys (`nulls`) that the seeded search does not read; the marker is computed over the pooled cross-channel null at a hard-coded α = 0.01 with no correction. The page should say "correction: none" rather than leave the setting silently inert. | 2 h |
| The seed page's progress strip is still `kit/sim` | The search itself is a real job with real per-channel progress on `GET /api/jobs/{id}/events`; the page polls the result rather than subscribing, so the strip's *timing* is simulated while its *outcome* is not. `subscribeJob` exists in `api.ts`. | 3 h |
| `?state=failed` is a display state | A real failure cannot be provoked from a URL. The row says so in its own text, and a real failure is covered by the route tests and by the loud-failure card. | — |
| *Analyse events →* and *Open in Analyse* | Cross-workspace: they need Analyse's source picker to accept a SpanSet from a Discovery run, which is Prompt 01's surface. | 3 h once the picker takes one |
| A paired null per Discovery run is **one** surrogate realisation | `run_paired_recipe` writes one; §9.4 asks for 200. The row states `null_draws` so the number is not read as an expectation, and `channel_score` already averages N. | 3 h (N runs per target, and the cost is N× the sweep) |
| The Analyse flow's chain-run checks fail in the smoke on this machine | Four checks in `smoke.py::analyse` (`all rows completed`, `every result row painted`, the threshold line, the stale marking) time out waiting for a matrix-profile row while another agent's work loads the machine. Not a Discovery surface, and Discovery's own flow and page states pass in the same run. | Prompt 01's, and a timing question rather than a defect |

## Requests filed

- `docs/prompts/wiring/requests/04-to-01.md` — the seeded-search exclusion parameter, its missing estimator,
  a between-target cancel for `fan_out_recipe`, a fan-out pre-flight for the held-out lock, and the `/api`
  guard's 405 not reaching router-mounted paths.
- `docs/prompts/wiring/requests/04-to-03.md` — what "Library exemplar" means until `motif_entry` is filled,
  threading a real `entry_id`, resolving a match onto a member, and §4.8 on the Library's template cards.
- `docs/prompts/wiring/requests/04-to-05.md` — the queue is a filter not a copy, superseded runs must not
  reach a queue, and the §4.6 rule Review should share.

## Out-of-scope files touched, with the reason

| File | Why |
|---|---|
| `Working/database/schema.py` | Additive migrations (named in the prompt as shared). Committed immediately. |
| `webui/server/app.py` | One import and one `include_router`, in the Prompt 01 block before the `/api` guard (named in the prompt as shared). |
| `webui/server/corpus.py` | The electrode-name table moved to the core and `channel_name` delegates to it. Behaviour identical; done because a second copy in the core had already drifted and produced wrong channel names on the first live drive. |
| `webui/smoke.py` | Extended with the Discovery flow (named in the prompt as shared). |
| `webui/client/src/api.ts` | Appended only (named in the prompt as shared). |

`webui/client/src/fixtures/canon.ts` was not touched.
