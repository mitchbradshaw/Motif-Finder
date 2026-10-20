# BACKLOG — the large outstanding changes (consolidated 2026-10-18)

The one file that holds every outstanding change too large to do directly: items from the researcher's lists of
2026-10-13, 2026-10-15 and 2026-10-18, the follow-ups the UX-1015 wave left behind, and the older "after wave 3"
table. Each row is meant to become one prompt under `docs/prompts/fixup/`. When a prompt is written, replace the row
with the prompt's name; when it merges, delete the row. Small items are not kept here: they are done directly and
recorded in the commit log (`ux-1013:`, `ux-1018:` prefixes) and in `README.md`'s dated triage tables.

Standing rules for any prompt cut from this file: the question to the researcher opens in plain language, then the
options, then a recommendation (CLAUDE.md, "Talking to the researcher"); the five verdict words are fixed; buttons are
never demoted to grey (`--blue-muted` is the muted colour); the UI gate is `tsc -b`, `npm run build`, the smoke walk
against a sandbox bridge (never the researcher's 8765), and `pytest` if Python outside `webui/` changed.

Sizes: **M** = a new route or component, one agent, a day; **L** = a design decision first, or several prompts.

## 1. Decisions waiting on the researcher

One open, a follow-up to AM (raised by `ux-1019`, 2026-10-19):

| Decision | Options | Recommendation |
|---|---|---|
| AM follow-up: switch drop alignment automatically? A pool chain has no detector in it, so nothing says "drop work" | (a) as built — set trough / 0.333 on the Trace shape block; Launch shows the anchor and names the setting · (b) an explicit "for drops" switch on the Window pool or chain that Analyse and Launch both read | (a) now; (b) if the researcher wants it automatic |

The six that closed rows in `reports/UX-1015-evaluation.md` were all resolved on 2026-10-18 as the
recommendations stood (built by `ux-1019`, `docs/prompts/changes/site-fixes.md`):

- **AK spike threshold δ:** keep 1 mV; a per-recording noise multiple is a later block.
- **AK recording with no declared unit:** read as volts, warn once; the declaration belongs in Datasets.
- **AM alignment for drop work:** trough at ⅓ for drop work, centre at 0.5 otherwise. As built (`ux-1019`): Launch's
  setup line shows the anchor and names the drop setting; it is not switched automatically, because a B.2 pool chain
  holds no detector (a Window pool is a source block) and so carries nothing that says it is drop work — set
  `trough` / 0.333 on the Trace shape block.
- **AO baseline window:** 600 s stays, shown on the Decompose card with its default; no code change until a case needs it.
- **AP "half the grey per page":** instruction lines only; the 12 pages still over are data-heavy.
- **Header path strip (`ux-1013`):** kept as built.

## 2. From the 2026-10-15 list — no prompt yet

| Item | What is known | Decision needed | Size |
|---|---|---|---|
| **Pick a trace in the family overlay and act on it** | the overlay draws every member; the remove-member edit exists on the family page; wanted: click a trace → it is highlighted, its detection named, remove / send to Review from there | none | M |
| **Reports** | three surfaces: a chain run and its block pages; detection runs and comparisons; the Export page with provenance. Nothing is drawn yet | format (printable HTML? PDF via matplotlib? Markdown?) and scope before the three prompts | L (three prompts) |
| **Interval / event analysis pages, design pass** | the pages show every figure at once; wanted: three headline figures, the rest behind a toggle; the slope page likewise | which three figures per page — ask with the current figure list | M |
| **Sequence family page** | `library/FamilyPage.tsx` renders `SequenceFamilyPlaceholder`; `GET /api/library/sequences` (`server/library.py:2428`, client `api.ts:917 getLibrarySequences`) exists and nothing calls it; `atlas?unit=sequences` is a working family grid | what a sequence family shows (member order, gaps, the shape of each element, the train statistics?) | M–L |
| **Overlapping / joined detections policy** | only the two threshold blocks merge gaps today; other detectors emit overlapping spans that Review shows twice | open with the options in plain words: merge on emit, merge in Review, keep both and mark the overlap | M after the decision |

## 3. From the 2026-10-18 list — the large items (code facts from the 2026-10-18 searches)

**Status 2026-10-19 evening: every row below, and §2's rows, became a prompt in `docs/prompts/changes/` and merged
to main as cdd6be3 (the wave) or 43ee443 (corpus-map), except the §2 Reports row's third surface (the Export page's
provenance) and the interval/event page pass's slope-page part, which the `interval-event-pages` prompt covered.
The datasets scripts run on the real data separately (CO and LM skipped: another agent derives them at 2 Hz).
The rows stay until the first clean post-wave full walk confirms them; delete then.**

| Item | What the code says | Decision needed | Size |
|---|---|---|---|
| **Review › `Edit span in Explore`** | `review/parts.tsx:105-118` navigates to `explore/span-edit/<detectionId>?from=review&queue=…&item=…`; `explore/SpanEditPage.tsx:24` calls `getSpanEdit`, which is `demo(spanEditDemo(id))` (`api/explore.ts:225`) and knows only `m-1846` (`fixtures/explore.ts:288`); saving is an in-memory demo write; the page ignores `from`/`queue`/`item` and reads `queue`/`candidate`/`of`/`return`. The core has `Working/library/revisions.py:91 add_revision`, `current_revision`, `revision_list` and no bridge route (`library.py:1907 _revisions_for` is read-only). Explore's own span comes from app state `explore.view` (`state.tsx:57`); sessionStorage `ub-proto-a:source` carries a span from Explore to Analyse, not into Explore | none | M |
| **Discovery: which detector ran on which channel; "run on CH2"** | `WhereFires` (`discovery/RunsPage.tsx:103-173`) reads `GET /api/discovery/fires` (`discovery.py:871`), which returns zero counts for a channel a run never touched — the same as "ran, found nothing". `/api/discovery/map/dataset` → `Working/discovery/detection_map.py:462 channel_map` already has `cells[row][channel].state ∈ covered/not_run/running/failed/discarded`. `RunRow` shows "2 ch" (`chrome.tsx:497`) not which. Launch is `POST /api/discovery/templates/apply` (`discovery.py:2806`; callers `RunsPage.tsx:42`, `chrome.tsx:542`, `AddTemplateModal.tsx:136`) and mints a new run key `<name>_2` (`_next_key`) | is "run on CH2" an extension of the existing run (same key, more channels) or a sibling run? | M |
| **Templates: share of `interesting` adjudications** | no route groups adjudications by template (the only verdict GROUP BYs are global: `registration.py:393`, `training_routes.py:323`); the scoreboard's `reviewed`/`interesting` (`Working/discovery/scoreboard.py:239-247`) counts detections inside reviewed coverage, a different measure; the card's score is `_last_score` (`discovery.py:647-663`) → `lastScore` in `_template_payload` (`discovery.py:592`), shown at `AddTemplateModal.tsx:229`. Needs adjudications → detections → runs → `discovery_runs.template_name` | which of the five verdicts count as "interesting" (accepted only? accepted + seed?) | M |
| **Explore + Cross-channel: send unjudged motifs in a span to Review** | Explore › Signal "Take span" is real (`explore/SpanActions.tsx:44`, `POST /api/annotations/seed` `explore_routes.py:221`, writes one `seed` annotation, never detections). The drawer's "Send selected to Review" (`SignalDrawer.tsx:161`) and Cross-channel's "Review this window on all channels" (`CrossChannelPage.tsx:197`) are demo-only. Queues take `filters.detection_ids` (`Working/review/queues.py:211`; `find_open_queue`, `create_queue`, `extend_queue`); the window query is `corpus.spans` (`corpus.py:432`, `GET /api/channels/{id}/spans`); "unjudged" is `NOT EXISTS adjudications` (`queries.py:644`). Copy `discovery.py:4056 send_remainder_to_review` | none; route shape `POST /api/explore/span-review {recording_ids[], t0, t1}` | M |
| **Cross-channel: artifact regions; a single-axis view** | an artifact region is an `annotations` row with verdict `artifact` (no region table; `schema.py:74 VERDICTS`), written only by Review (`Inspector.tsx:115`, `ClusterView.tsx:182`, `BlindTest.tsx:32`); Explore's take-span hardcodes `seed`; Settings only sets `cross_channel.artifact_max_lag_s` / `artifact_min_abs_r` (`AnalysisDefaultsPage.tsx:89`). Cross-channel is one `<svg>` per channel on one x scale with per-row y (`CrossChannelPage.tsx:268-367`; modes absolute / centred / per-channel; ~3.9 V of DC offset between channels) | one artifact annotation per channel or one per window? overlay as a fourth y-mode or a separate view? | M–L |
| **Website speed pass — prompt `AR-speed-pass.md`, MERGED 2026-10-18 as 5a20070** (ledger `reports/UX-1015-ledger.md`, report `reports/AR-speed-report.md`). Left for a second pass. ~~First: the home page's corpus map recomputes inside a request~~ **done 2026-10-19 as `corpus-map-off-the-request` (43ee443): a read never computes; the map recomputes in a worker process, 0.5–0.8 s read after a change.** Next in that line, from its report: the `channels_fingerprint` floor (173–295 ms warm: adjudications CROSS JOIN 49 %, annotations 27 %, runs 17 % — per-file reads split per channel, or per-channel SQL aggregates; the `MAX(id)` probe is unsafe); the detection map levels 2/3 with the same `compute(db_path)` worker pattern; the template scorer still on a thread in the parent. Then, measured by AR: the detection map levels 2/3 recompute per read (`discovery_map.py`, `detection_map.py`, not AR's files; the 5 s poll needs a cache keyed by `channels_fingerprint(settings_keys=…, stable=True)`); the picker's 0.5 s warm read (batch the per-template score fingerprint); the rows read on queue open (0.8 s / 5 MB at 10 k — paging it needs the rail to work on partial rows); the scoreboard's remaining 2 s (`channel_score` itself); the Library atlas grid and the Jobs board unmeasured; **`GET /api/discovery/map` (the Map overview) 11–15 s on every call on the live bridge, the same before and after the batch 3 import (HPC session, 2026-10-20 00:09) — the levels 2/3 recompute above, now with a number;** **the quiet-machine re-timing and the three smoke units are owed** | the warm (`run_server.py:107` → `discovery.py:666 warm_last_scores`) runs in a daemon thread at startup: `corpus.warm_coverage` (462 s for 17 files on 2026-10-18) then `_last_score` per template. No lock; it competes for the GIL and SQLite. Caches are memory-only and rebuilt every restart: `corpus._COVERAGE_CACHE` (64 entries FIFO, key `(source_file, bins, verdicts, run_ids, method)` validated by `SB.channels_fingerprint`) and `scoreboard._SCORE_CACHE`. The fingerprint (`scoreboard.py:555`) hashes the settings rows (global — any settings change invalidates every file), each channel's human rows and every run's config/stitched/MIN-MAX detection id; a new run forces a full `_coverage` (`corpus.py:346`, `DIV.channel_divergence` over every channel × run). `GET /api/discovery/templates` (`discovery.py:696`) rescores every template on each open. The client `req()` (`api.ts:25`) has no timeout or AbortController; only jobs cancel (`POST /api/runs/{id}/cancel`). Memory `scoring-reads-perf-2026-10-18` has the earlier findings (quadratic matcher in the picker, corpus coverage as the home-page blocker). **Measured 2026-10-18 evening on the sandbox copy of the real database** (session of 16 channels, 52 runs, 721 h; machine loaded): `GET /api/discovery/runs` 10–13 s (`fanout.group_status` per run, itself several rows per member run); `GET /api/discovery/fires` 147 s for THREE channels before `ux-1018` hoisted the status read out of the channel loop (the per-channel span reads remain); `GET /api/discovery/templates` > 60 s while the warm rescored; the M2_aug corpus map 100–140 s cold. The home page cannot reach network-idle in 30 s while the warm runs, which is why `routes` fails in a smoke walk started right after a bridge restart | disk cache keyed on the fingerprint vs incremental coverage per run; what the per-request budget is ("load times over X are blocked / cancellable"); a cheap `group_status` (status + progress only, one query) for the runs list and the fires card | L — dedicated agent |
| **Polish / readability pass** | page by page after the speed pass; AP's per-page caption rule is the standard | none | L — dedicated agent |
| **MJu26a at a uniform 10 Hz, parent of L_LM** | `scripts/rederive_channels.py:204 do_mju26a` writes the 16 raw rows as-is, `fs = 1/median(dt)`, `t.npy` saved and read by nothing; L_LM (`:241`) is 5 columns at an inferred 10 Hz, mV. Rows come from `Working/registration/kinds.py:503 _register_recording`. Detections, annotations, reviewed_spans and runs are all in **sample indices** (`schema.py:91-157`); the step cache key (`execution.py:122`) has no content hash, so overwriting the npy under the same ids serves stale results silently; matrix-profile and window-matrix stores flag staleness by `data_sha1`; HPC import (`chain_job.py:12-37`) checks the npy sha1 and would refuse the rq4 batch-2 results if the files changed. Lineage: `parent_recording_id`/`parent_offset`/`decimation` (`schema.py:490`) set only by the excerpt rule (`kinds.py:456`, child ≤ 200 000 samples, one channel); UI at `settings/DatasetsPage.tsx:166`; Review's shape code maps through it (`review.py:214-254`, needs `fs_parent == decimation × fs_child`). Resampler to reuse: `scripts/derive_dwij_mfs2.py:152 resample` (linear `np.interp` onto a 0, dt, 2dt… grid; manifest template at `:198`). MJu26a's unit is undeclared (`Working/units.py:137`) | linear vs nearest (linear flattens one-sample spikes); remap or retire the old MJu26a detections; **register a new source_file rather than overwrite** (keeps every id and the HPC hashes valid); how to write a whole-recording parent on all 5 L_LM rows (decimation 1, per-channel offset) or a `datasets`-level link; declare MJu26a as V; confirm MJu26a's span covers L_LM's 636 h | M |
| **Library sequences — page and joiner** | `library/index.tsx:20-28` has no `sequences` case ("No Library page called…"); `atlas?unit=sequences` works; the family page is `SequenceFamilyPlaceholder` (`FamilyPage.tsx:146,159`); `getLibrarySequences` unused. Nothing joins adjacent detections into `sequences` rows: sequences arrive only via importers (`library/importers/sequences.py:170`, `catalogue.py:474`, `annotations.py:217`). Candidate joiners: `Working/interrogation/trains.py:395 find_trains` (gap rules logisi / maxinterval / adamatzky, emits `train_id`), `cycle_shapes.py:853 sequences_of`, `drop_motifs/detect.py:455 merge_up_runs` | the joining rule and its parameters; whether a joined sequence is a Library unit or an interrogation result (RQ1 precursor) | M page, L joiner |
| **Seed-search page redesign** | `discovery/SeedPage.tsx`: toolbar (session, scope, null, cost, History); ScopeCard with the 3-at-a-time channel pager; left RunsCard in seed mode; SeedCard (source Seg, provenance, change-seed picker, disabled "+ seed", carry/rebind radios); ParamsCard (algorithm, window, scale bank, exclusion zone, overlap, revert, per-length null, cut histogram with a draggable threshold); NotPreviewed → SearchProgress → DistanceProfile + MatchesCard; ApplyBar (null mode, cost, Import HPC result, Save as template, Create SLURM script, Run seed search, Open in Runs) | the researcher's brief on what is confusing | L |
| **Review item carries onset/extremum** | the medium half of the span-set highlight fix: Review draws the whole emitted window (`review/parts.tsx:75`, from `start_idx`/`end_idx` at `review.py:344`); Analyse's core is `marks.onset_s→extremum_s` (`SpanSetView.tsx:62`). Storing the marks on the review item lets Review draw the same core | none | M |

## 4. Older — "what is left after wave 3" (predates this session; verify before cutting a prompt)

| Item | Status |
|---|---|
| **Review behaviour** — R3 (a class 1/2/3/4/9 is never stored), R7 (a rediscovery can be put twice; carry the prior verdict), R8 "sorted by score" wording, R16 coherence; the blind-labelling mode for RQ1's yardstick (Q42) | decided (Q16, Q42); no prompt written; R3 and R7 cost the researcher real time |
| **Library** — click a cluster → its members in place in the `H` slideshow (Q-L6/Q-E6); the rose reference = median steepest slope over human-accepted motifs | decisions made; no prompt |
| **Jobs, Models, Training** — fixture pages wearing the `demo data` chip; labels must come from `corpus.dataset_name` | partly wired since; check each page |
| **`I` U4** — Explore's fine span adjustment | small and self-contained |
| **U13** global search | needs a design |
| **U12** the phantom Ctrl-C | needs reproduction |

## 5. Small follow-ups still open (do directly when passing)

None open (the Launch anchor and the Cross-channel cubic control were done by `ux-1019`).

## 6. Housekeeping

- The matrix-profile persist fix `fd0143b` (null draws overwrote the real run's `mp_v2_*.npz`) is on `claude/peaceful-sutherland-22bdf8`, not main — memory `mp-persist-null-collision`.
- Unmerged local branches from other sessions: `claude/admiring-rubin-6854f1`, `claude/peaceful-sutherland-22bdf8`, `claude/wonderful-engelbart-da8936`.
- The seven UX-1015 agent worktrees under `.claude/worktrees/` and the 8766 sandbox bridge are still in place (unlink any DATA junction with `cmd /c rmdir` before `git worktree remove`).

## 2026-10-20 — the night pass's findings, reported and not fixed (reports in `docs/prompts/changes/reports/night-{a,b,c}-report.md`)

Three break-it agents (A Review+Discovery, B Explore/Library/Analyse, C polish+load) on the scale fixture (16 channels
× 721 h, 5.0 M detections, a 10 k queue); their fixes are on main (293a8fc, d1bf8e4, e668995). What they could not
fix, ranked by how often the researcher's path crosses it; the per-item file:line is in each report.

| item | measured | the fix as proposed | size |
|---|---|---|---|
| **Review queue open sends every row** (`GET /api/review/queues/{id}?thumbs=0`: 7.0 MB at 9,743 rows, 8.8–12.5 s cold in process, 7–17 s to the first candidate) | A, C | page the rows around the current item, or a slim row until one is opened (`webui/server/review.py:771`) | M |
| **Explore › Signal waits for the whole channel's spans** before tier 2 (526 kB, 153 s on a loaded bridge; tier 2 at 33.7 s fresh) and `GET /api/channels/{id}` recomputes its ribbons every call (4.6 s in process) | B, C | read spans for the viewport (`api/explore.ts` `getSignalLive`), cache the ribbons by (recording, detections fingerprint) (`server/app.py:209`, `corpus.py:899`); Cross-channel has the same wait | M |
| **The template scorer runs on a thread in the bridge**: every request 3–35× slower for the first 6–10 min after a start (`discovery.py` `_drain_scoring`) | A | score in a worker process, like the corpus map (`corpus-map-off-the-request`) | M |
| **The cold scoreboard is 8 min at scale** (60 runs × 16 channels, ~7 s per run in `Working/discovery/scoreboard.py score_runs`); the warm scorer computes the same scores under a different cache key | A | one cache key for both; a worker | M |
| **`GET /api/discovery/map` (the Map overview) 17–21 s per call on the live bridge after batch 2 (11–15 s before; 289 runs across 8 sessions; grows with the run count) — DEMO RISK; prompt `docs/prompts/changes/map-overview-cache.md`** | HPC session | the `compute(db_path)` worker pattern, served-at-once + `stale` | M |
| ~60 `Math.max(...xs)` / `Math.min(...xs)` spread sites in `webui/client/src` on bins, counts and per-channel lists (the seed page's six are fixed, 8dff9b0 — a 10^5-value spread is a stack overflow) | manager | `kit/extent.ts` at every site that can see a data-sized list: Discovery and Explore first | S |
| The scale-bank seed preview is a 445 s sweep on the October database (`fixup-v-scale-bank-searches-every-length`); the walk's state waits 240 s | manager | the seed-search redesign's time estimate and the > 10 min SLURM route; the state's budget | S |
| A family's cold open is still 5–19 s at scale (coherence draw; the library fingerprint counts 5 M detections, ~1 s) | B | — | M |
| Signal's default run picker shows the three newest runs, so scratch Analyse runs hide the Discovery runs | B | a product decision (`explore/signalModel.ts:24`) | S |
| `/api/runs?limit=1` is polled every 5 s on every page (`App.tsx`) — the one read that never stops | B, A | poll only while a run is live | S |
| Review: an item whose prefetch is in flight still waits the 150 ms settle (`Inspector.tsx:69`); the blind-test page is chosen from the general queue read, whose rows carry earlier labels in the payload (`index.tsx:62,80`) | A's critic | `itemHeld()`; drop `verdict` for `source_kind == 'blind-test'` on the bridge | S |
| Corpus counts read 0 while the map computes; 16 `/api/channels/<n>/tags` reads on open; Library › Templates 30 grey captions; Jobs and Training block 2 shift after first paint; Settings › Channels & events defaults to the fixture recording (a console error per open); the global search pill is dead outside Settings | C, B | each a one-liner in C's table | S |
| `create_queue` accepts an empty detection set; the "where each run fires" card shrinks 73 px after its read lands | A | — | S |

## 2026-10-20 — after the demo (found by the site-changes agents; NOT to be fixed before 2026-10-21 09:00)

| item | found by | the fix as proposed | why it waits |
|---|---|---|---|
| **Apply template's time estimate leaves out the null draws** — `Working/discovery/fanout.py` `preview()` (~l. 639) returns `per_channel * n_channels` for an unwindowed run; the windowed branch (~l. 619) multiplies by `1 + draws`. A 20-draw null on 5 ch × 721 h ran 2.5 min against a 31 s estimate | site-runs, Demo instance session | multiply by `1 + draws` as the windowed branch does, and check `overLimit` against it | the estimate decides local vs cluster: a corrected estimate can push tomorrow's live W2 Apply template over the local ceiling into "Create SLURM script" |
| A Scope-card change of recording can still send reads already in flight to the new session | site-runs | abort in-flight Discovery reads on a scope write (the deep-link path already holds the cards back) | small, off the demo path |
| The first open of a map level-2 / level-1 view after a restart computes in the request (~2 s on the real copy) | site-map | warm the session's dataset level at start, or serve `pending` like level 3 | ~2 s once per view |
| d-309 (`cnn_gadf_1min`, session LM_fs2_rq4) reads failed: the 14:14 8765 restart killed it mid-run; the page offers a re-run that keeps its finished channels | Demo instance session | the researcher's call | — |
