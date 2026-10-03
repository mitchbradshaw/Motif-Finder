# RESEARCH_READINESS.md — can the app answer the six questions?

Research prompt 00 (`docs/prompts/research/00-six-questions-readiness.md`), run 2026-10-02 on `main` at
`e93e7d6`. Nothing was fixed and no tracked file other than this one was written.

*2026-10-03:* nine prompts were written from this report — `docs/prompts/fixup/README.md`, "Stage 5" —
with their open decisions in `docs/prompts/fixup/QUESTIONS.md` Round 9, and the per-question walk in
`docs/RESEARCH_RUNBOOK.md`.

**How it was run.** One `--sandbox` bridge on port 8765, runtime `webui/runtime/20261002-180621/` (a copy of
`DATA/db/annotations.sqlite`, every write redirected; gitignored). The shared `webui/client/dist` was current
with the sources and was served as is. Every page below was driven in a browser (Playwright/chromium at
1440 × 900, plus the app's browser pane) and every chain was started from the page's own buttons; the bridge's
JSON was read only to get a number exactly or to say which store it came from. **Run ids are the sandbox
copy's** — they do not exist in the real database. Screenshots and the driver scripts are in
`webui/runtime/20261002-180621/readiness/`. **0 browser console errors and 0 HTTP ≥ 400 across every page
state driven** (the three deliberate held-out probes returned 423, as designed), and the bridge log holds 0
tracebacks and one `ERROR` line — the `detection.seed_matches` failure reported under Q2.

**Scope actually used.** Analyse chains ran on the page's example span — `M2_aug_concat_fs1.mat · CH1_A1 ·
336.00–338.00 h` (recording 1, samples 1,209,600–1,216,800). Discovery ran on the saved session's scope —
`M2_aug_concat_fs1.mat · 3 channels · 452–456 h` (CH2_A1, CH6_B1, CH7_B2). Explore's *Send span to Analyse*
is live (`SignalPage.tsx:198`) but was not exercised.

## The six, ranked by how close each is to answerable

| # | Question | Today | First thing that stops it |
|---|---|---|---|
| 1 | **Q4** band decomposition + symbolic vs raw | The whole route runs by hand and produces a set overlap: *only A 3 · both 0 · only B 74* | The "only B" remainder cannot be handed to Review from Discovery; bands are one hand-saved template each |
| 2 | **Q2** exemplar-seeded search vs human acceptance | The search and its 200-draw surrogate run; Review's verdicts and seed promotion work | Matches cannot reach Review from Discovery, and no human-adjudicated exemplar can be chosen as the seed |
| 3 | **Q5** where human and machine diverge | Two live surfaces count disagreement | `adjudications` is empty; the live counts are blind to verdict and to where a detector actually ran; nothing tabulates divergence by tag |
| 4 | **Q6** recurrence across channels and recordings | Channel fan-out, a per-channel surrogate, the recurrence matrix and a one-window lag classification are all live | Classification never reaches an edge: the action is `notWired` and `motif_edge` has 0 rows |
| 5 | **Q3** identity under scale normalisation | One of the three distances is reachable; nothing could be run | The other two distances, search-at-other-scales and edges exist only in the core |
| 6 | **Q1** cluster labels vs manual labels | The cluster-label arm trains on one span | No block reads human labels; Models, Training and Jobs are fixture pages |

Q2 was run first (its route looked most complete, and it is the worked example); then Q1's live half, Q5, Q4,
Q3 and Q6. The ranking is by what is left, not by the order run.

## Three things that bear on more than one question

1. **Closed 2026-10-03 by `fixup-L`** (`docs/prompts/fixup/reports/L-send-to-review-opens-a-queue.md`): the route
   now creates a `review_queues` row through `Working.review.queues.create_queue`, filtered by the **run ids**
   the Discovery run is made of (never its run group alone — the group holds the paired surrogates' detections
   too; the sandbox's group 7 held 74 real against 249 surrogate), *Open Review* opens that queue, a second
   send returns the same open queue, the Analyse chain footer's *Pass N to Review* shares the slideshow's
   call, and the descriptor and `GET /api/discovery/queues` are gone. What was measured on 2026-10-02 stays
   below as the record of the defect.
   **Discovery's *Send N unjudged to Review* did not create a Review queue.** It wrote a descriptor into
   `discovery_sessions.state_json` (`webui/server/discovery.py:1790–1799`); no `review_queues` row is made, and
   the toast's *Open Review* is `navigate('review')` (`webui/client/src/discovery/RunsPage.tsx:401`). Measured:
   the toast read *"5 of 5 unjudged in 'Discovery · seed a9147c unjudged' · verdicts write adjudications"*,
   `GET /api/review/queues` still listed two queues, and *Open Review* landed on `#/review/queue/1/119` —
   *"Library - extract events"*. **This is the blocker for Q2 and Q4 and half of Q5.** The Analyse block page's
   slideshow *Send N to Review* does create a real queue, for one chain run on one span.
2. **Where a null exists.** Interrogation has none and says so: *"no null is drawn on this page: every number
   below describes these events and is not tested against chance"*. Analyse chains have none (*"surrogate · not
   in this slice"*, every run footer ends *"no null"*). **Discovery does draw a surrogate**
   (`preprocessing.surrogate`, phase-randomised): 200 draws per channel for a seeded search, and **one** paired
   surrogate run per channel for a template run — the scoreboard's *"null expects / draws"* column reads
   *"… / 3"* on three channels while the session chip reads *"null phase_randomize 200×"*. The marker is
   *"α = 0.01 per null draw · correction: none"*. **Nothing run in this pass came out ahead of its surrogate,
   and no number below should be read as beating chance.**
3. **`motif_edge` has 0 rows and nothing in the app writes one.** The writers are in the core and tested
   (`Working/library/matching.py`: `match_span_to_entry` :37, `search_entry_across_durations` :159,
   `classify_cross_channel_edges` :284) and no bridge route calls any of them. Q3 and Q6 both stand on edges.

The real database, for reference (read-only, `mode=ro`): `adjudications` 0 · `motif_edge` 0 · `window_sets` 0 ·
`window_verdicts` 0 · `hand_edits` 0 · `motif_entry` 3,603 (3,599 `event_store`, 4 `annotation`) ·
`annotations` 11,269.

---

## Q4 — Does band decomposition followed by symbolic encoding surface regions raw-signal methods miss?

**The route.** Analyse › Chain: `preprocessing.bandpass` → `preprocessing.detrend` → `detection.sax_dsax` →
`detection.symbol_search`, *Save template* → Discovery › Runs › *Apply template* across channels → Discovery ›
Compare (A a raw-signal run, B the band run) → Review for the remainder. Fan-out across bands does not exist
in the app; the route is one chain per band.

**What I ran.**
- Analyse, example span, template `symbol_search` as shipped (pattern `c+a+`, dSAX alphabet 3, 20 s per
  symbol): job 37 · db run #96.
- The same chain with `preprocessing.bandpass` inserted first (`low_hz 0.01 · high_hz 0.1 · order 4`, the
  block's defaults): job 38 · db run #97. Saved from the page as template 12 `band_symbol_search_0p01_0p1`
  (*"saved to the throwaway database copy (id 12)"*).
- Discovery, 452–456 h × 3 channels: *Apply template* with `symbol_search` and the band template ticked,
  *Add and run* — run groups 6 and 7, db runs 100–111 (six of them the paired surrogates).
- Compare: `drop_detection_v1` vs the band run, and `symbol_search` vs the band run.

**What came out.**
- Analyse (page rows): without the band *"0 spans · none found"*; with it *"5 spans · mean 44.0 s"*. For
  reference `drop_detection_v1` on the same span: *"4 spans · mean 979.0 s"* (db run #93).
- Discovery › Runs: *"symbol_search … 9 found · 3 ch"*, *"band_symbol_search_0p01_0p1 … 74 found · 3 ch"*.
- Compare, A `drop_detection_v1` · B band: *"Set overlap · matched at IoU ≥ 0.5"* — **only A 3 · both 0 ·
  only B 74** (*"all 77 · only A 3 · only B 74"*); by channel CH2_A1 3 / 0 / 3, CH6_B1 0 / 0 / 61, CH7_B2
  0 / 0 / 10. A `symbol_search` · B band: only A 5 · both 4 · only B 70, `attributable: true` (one role
  differs). Rule on the payload: `reciprocal_iou_onset`, IoU 0.5, onset 0.25. Store: `detections` of the two
  run groups, matched by `GET /api/discovery/compare`.
- Scoreboard rows (found · already judged · reviewed · interesting · precision · recall · null expects / draws
  · × null): `symbol_search` *"9 · 0 · 9 · 0 · 0 % · 0.00 over 6.033 h · 154 / 3 · 0.1×"*; band *"74 · 0 · 66 ·
  0 · 0 % · 0.00 over 6.033 h · 249 / 3 · 0.3×"*. **At these untuned defaults the single surrogate per channel
  produced more spans than the real signal did.** Store: `detections` against `annotations`, one surrogate run
  per channel.

**What stops it.** The question's last clause is *hand adjudication of the remainder*, and the 74 "only B"
spans cannot be sent to Review from Discovery (cross-cutting 1). Compare has no action on its disagreement
list. Second: **band fan-out is in the core and unreachable** — `Working/run_groups.py` (a `fan_out` of
`kind: "bands"` prepends a bandpass per target) has no caller in `webui/server/`, so each band is a chain
built, saved and applied by hand, and Compare takes two runs at a time.

**What it would take.** Make Discovery's send-to-review create a real queue; with that, Q4 is answerable today
for a handful of hand-built bands. A band scope on *Apply template* turns it into one action.

## Q2 — Does a human-adjudicated exemplar used as a matrix-profile seed recover instances a human also accepts?

**The route.** Review › Inspector (`S` promotes a detection to a Library exemplar) → Discovery › Seed search
(seed = *Library exemplar* | *Explore selection* | *Family medoid*; block `detection.seed_matches`,
*"MASS · z-norm Euclidean"*, *"window m 711 samples · native"*; null `preprocessing.surrogate`) → Discovery ›
Runs (scoreboard, *Send N unjudged to Review*) → Review › Inspector (verdicts → `adjudications`).

**What I ran.**
- Seed `library:1:1212809:1213520` — *"entry 1 · M2_aug_concat_fs1.mat · CH1_A1 · 336.89 h · 711 s · hash
  a9147c59db1010ca"* — over 452–456 h × 3 channels. With no cut: Discovery job j-29, run group 3. With a cut
  dragged to 14.5 on the histogram: job j-31, run group 5, db runs 85, 87, 89 (+ surrogates 86, 88, 90).
- The Review half, on a chain run because of the blocker below: `drop_detection_v1` on the example span (job
  36 · db run #95), the block page's slideshow *Send 4 to Review* → queue 3 *"drop_detection_v1 · run #95"*,
  then `I`, `N`, `S` on its first three detections.
- `detection.seed_matches` inserted into an Analyse chain after `preprocessing.detrend`: run #113.

**What came out.**
- No cut: *"197 found · 3 ch"*; *"no cut · nothing here is closer than the null gives · drag to choose one
  anyway"*; closest *"CH6_B1:1634712 d 12.67"*. The seed-results payload: 197 candidates at d 12.6693–50.524;
  `null.draws 200`, `drawChannels 600`, 39,437 null distances whose smallest is 6.5447.
- Cut 14.5: *"5 kept · the null gives 6.3 per draw"*. Scoreboard row `seed a9147c_3`: *"5 · 0 · 4 · 0 · 0 % ·
  0.00 over 6.033 h · 8 / 3 · 0.6×"*. The uncut run's row: *"197 · 12 · 168 · 6 · 4 % · 0.75 over 6.033 h ·
  201 / 3 · 1.0×"*.
- Review works. Sandbox `adjudications`: `(1629, interesting)`, `(1630, not_interesting)`, `(1631, seed)`;
  `annotations` unchanged at 11,269. `S` printed *"seed · exemplar E-0217 created in the Library"* and wrote
  `motif_entry` 3609 (`source_kind = 'review'`, `detection_id = 1631`).
- Analyse cannot run the block: *"02 Seeded search failed after <0.1 s · SideInputResolutionError: Side-input
  'exemplar': 'detection.seed_matches' declares this side input but the step has no binding for it."* Its
  block page offers `k` and `max_distance` and no way to bind an exemplar.

**What stops it.** Two things, in route order.
1. **The seed cannot be a human-adjudicated exemplar.** The picker is `motif_entry ORDER BY id LIMIT 24`
   (`webui/server/discovery.py:953`, `SEED_LIMIT = 24` at :63): the first 24 of 3,603 entries, all
   machine-extracted `event_store` rows. Entry 3609, promoted in Review minutes earlier, was not offered.
   *Explore selection* reads `annotations.verdict = 'seed'` (0 rows), and Explore's *Take span for Review* is
   a demo write (`webui/client/src/explore/SpanActions.tsx:39–42`): it toasted *"span staged for Review ·
   Explore spans queue"* and `annotations` stayed at 11,269 with 0 seeds. Explore › Signal wears `demo data`.
2. **The matches cannot reach Review** (cross-cutting 1) — and this is the one that makes the question
   unanswerable, because its outcome variable is a human verdict on each match.

**What it would take.** A real queue from Discovery's send-to-review, and a seed picker that can reach any
Library entry (at least those with `source_kind = 'review'`).

## Q5 — Where do human and analytical judgement diverge, and is the divergence structured?

**The route.** Explore › Corpus (*colour by · disagree*, verdict and morphology-tag filters) → Discovery ›
Runs scoreboard (precision and recall against the human record) → Discovery › Compare with *human
annotations* as run A → Review for the adjudication verdicts. The PRD's union view was withdrawn (ticket 02);
its replacement is two queries in `Working/database/queries.py` (:384, :414).

**What I ran.** Explore › Corpus on `M2_aug_concat_fs1.mat`; Compare `human` vs `drop_detection_v1` on the
Discovery scope. No chain: this question reads what is already stored.

**What came out.**
- Corpus page: *"Verdict · interesting 2,364 · not_interesting 8,773 · artifact 128"*. `GET
  /api/corpus/M2_aug_concat_fs1.mat/coverage` (stores `annotations`, `detections`): **11,265 annotations ·
  1,003 detections · 11,261 disagree** across the 16 channels in the sandbox copy (576 of those detections are
  in the real database; the rest are this pass's runs). Restricted to `verdicts=interesting`: 2,364
  annotations, 2,476 disagree.
- Compare `human` · `drop_detection_v1`: **only A 8 · both 0 · only B 3** over 452–456 h × 3 channels.

**What stops it.**
- **There are no adjudication verdicts.** `adjudications` has 0 rows in the real database, so "machine says
  yes, human says no" has no data. Review itself works (Q2), and queue 2 — 130 detections of
  `drop_detection_v1` on Mushroom_260720 CH14 — stands at 0 judged.
- **The live "disagree" number is not a divergence.** It counts every annotation with no overlapping
  detection plus the reverse, whatever the verdict and whether or not any run covered the span
  (`webui/server/corpus.py:279–281`). 10 of the 16 channels have 0 detections, so all of their annotations
  "disagree"; a `not_interesting` window where the detector found nothing counts as a disagreement.
- **The units differ.** 11,234 of the 11,269 annotations are 600-sample review windows; detections are
  events. A reciprocal IoU ≥ 0.5 between the two rarely holds — hence *both 0*.
- **"Structured" has no surface.** The two core divergence queries have no caller outside `tests/`. Morphology
  on the human side is 34 `element` tag links (`sharkfin` 17, `halfdome` 3, …) against 11,234
  `manually_sorted_for_cnn`; on the machine side it is the Library's `element` tags (`trough` 2,827,
  `sharkfin` 772) and nothing on `detections`. A class or tag given in Review is not stored
  (`docs/prompts/fixup/README.md`, R3).

**What it would take.** The researcher's adjudication hours on queues that open, and one page over the two
existing queries that conditions on verdict and on where a run actually ran.

## Q6 — Once contamination and propagation are separated out, does recurrence persist across channels and recordings?

**The route.** Discovery › Runs › *Apply template* (channel fan-out → `run_groups`, each run paired with a
surrogate) → scoreboard → Library › Recurrence (family × recording × channel) → Explore › Cross-channel (lag,
r and bin for one window) → the Library action that stores bins on edges.

**What I ran.** The two template applications of Q4 (run groups 6 and 7); Library › Recurrence on grouping
g-05; Explore › Cross-channel at `#/explore/cross-channel/4`.

**What came out.**
- Recurrence page: *"shape distance · cut 0.6 · min_group 10 · omit_d 0.5"*, *"364 omitted"*; 149 families.
  `GET /api/library/recurrence` (stores `groupings`, `grouping_assignments`, `motif_member`): 99 families
  occur in 2 recordings, 22 in 3, 28 in 1. **Every one of the 149 carries `"edges": "no edges"` and
  `artifactChannels`, `propChannels`, `indChannels` all 0.**
- Cross-channel page, CH4_A2 as reference, *"interesting span at 0.83 h ± 20 s"*, 640 s: lag *"0.0 s"* on
  all five pairs, r *"0.82"*, *"0.80"*, *"-0.76"*, *"-0.71"*, *"-0.70"*, each binned *"propagation"*;
  *"Classification for this window · 0 artifact · 5 propagation · 0 independent · 0 no match"*. Computed
  live by `Working.cross_channel.classify_waveforms`; stored nowhere.
- Surrogate counts: the scoreboard rows quoted under Q4 — one surrogate realisation per channel.

**What stops it.** *"Classify every F-03 member in Library — runs across all channels and stores bins on
edges"* is `notWired(...)` (`webui/client/src/explore/CrossChannelPage.tsx:317`). With `motif_edge` empty
there is nothing to classify (cross-cutting 3), so no recurrence count can have contamination or propagation
taken out of it.

**Worth knowing before it is built.** The rule (`Working/cross_channel.py:93–112`) calls a pair *artifact*
only at |lag| ≤ 1 sample **and** r ≥ 0.99; anything else within 50 samples is *propagation*. That is why five
zero-lag pairs at |r| 0.70–0.82, three of them negative, read *propagation* above. Whether a zero-lag pair at
r = 0.8 is contamination is the researcher's call, and Q6's answer turns on it. Separately, the Library's
cross-recording families span the import stores (entry tags: `reishi_10hz` 2,425, `oyster` 749, `sp385` 76).

**What it would take.** A route that runs `match_span_to_entry` and then `classify_cross_channel_edges` for a
family, so edges exist and carry a bin; the Recurrence page already has the fields to show them.

## Q3 — Is motif identity preserved under scale normalisation?

**The route.** Library › Edit grouping (basis *shape distance*) → Library › Family (members and their
durations) → Discovery › Seed search with a scale bank (search at other scales) → edges carrying the distance
function. Only the first two steps exist in the app.

**What I ran.** Nothing that bears on the comparison could be run. Read: the grouping editor, family F-141,
and the Seed page's *algorithm* and *scale bank* menus.

**What came out.**
- Grouping editor (`GET /api/library/grouping-editor`): nine bases. The only distance over single motifs is
  *"shape distance — z-normalised, scale-invariant, Ward cut"*; the rest are *"feature bins · no distance"*
  or sequence-only.
- F-141 under that distance: *"members 51 · recordings 3 · 10 channels · judged 0 of 51 · mean member d
  0.11 · duration 194.84 s ± 515.7"*, its exemplar m-718 at *"2154.0 s"*, shape mix *sharkfin 27 · trough 24*.
- Seed page: scale bank *"3 lengths · 0.8× 1× 1.25×"* disabled with *"needs a scale-bank algorithm"*;
  algorithm *"Matrix profile join"* disabled with *"not built"*.

**What stops it.** The capability is not in the app. All three distances exist in the core
(`Working/distances.py`: `scale_invariant_distance` :81, `native_length_distance` :96, `symbolic_distance`
:139) but the Library groups by the first alone and no page computes the other two on the same pairs; no edge
exists, so no distance function is recorded on one; search-at-other-scales is
`search_entry_across_durations` with no route. Per rule 4 this is where I stopped.

**Caveat from Q26.** Scale here is duration, and a sharkfin's extent is the open question (Q26d). The
*"194.84 s ± 515.7"* above is on a family that is more than half sharkfin; it is quoted to show what the page
prints, not as a spread to build a scale comparison on.

**What it would take.** A Library action over `search_entry_across_durations` that writes edges under all
three distances; the question then becomes a query on `motif_edge`.

## Q1 — Do cluster-derived labels produce a classifier that generalises better than manually-derived labels?

**The route.** Analyse › Chain, template `windows_model`: `preprocessing.window_matrix` → `catalogue.cluster`
→ `catalogue.classifier` (the cluster-label arm) → the same chain on manual labels → Models › Launch /
Results / Compare (paired arms, one test block) → the held-out recording, unlocked once.

**What I ran.** `windows_model` on the example span: job 33 · db run #92. `cnn_detection` on the same span:
job 43 · db run #112 — but its *Encode windows* and *Model stage (CNN)* rows came back *"cached · 0 s"*,
restored from the real `DATA\derived\step_cache` through the copied `step_artifacts` index (a read), so the
CNN was **not** executed in this pass. Three probes of the held-out recording.

**What came out.**
- Cluster arm (page rows): *"120 windows · 60 s each · 26 features"*; *"3 clusters · sizes 42, 6, 72"*;
  *"holdout accuracy 0.80 · classes 3 · windows 120 · features kept 16 of 19 · train/holdout 90/30"*;
  *"per class · 1: 1.00 · 2: 0.00 · 3: 0.72"*. Model file `catalogue_classifier_f8c9cbf46d3aba67.joblib`
  under the sandbox `models/`. **That holdout is a stratified random 25 % of the same two hours' windows**
  (`Adapters/catalogue_classifier.py:165–170`); it says nothing about generalisation.
- Held-out lock: `GET /api/channels/49/window`, `POST /api/runs` on recording 49 and the corpus map for
  `M4_aug_concat_fs1.mat` each returned **423** *"… is held out … the web UI refuses it"*. Left that way.
- Analyse › Training (the chain page and block 05 were opened; the fixup README says all six), Models ›
  Launch / Results / Compare / Registry and Jobs all wear the **`demo data`** chip. Their figures are
  fixtures and are not reported here. Library › Window sets: *"0 saved"*.

**What stops it.** **There is no manual-label arm.** No registered block reads `annotations` or
`window_verdicts`: `catalogue.classifier` takes a `Grouping`, and `catalogue.cluster` is the only block that
makes one. The classifier's own docstring says the comparison needs *"a manual-label step upstream"*
(`Adapters/catalogue_classifier.py:24–27`). After that: the Models workspace is fixtures, so nothing trains
across channels, pairs two arms on one test block, or scores them; `window_sets` has 0 rows and
`saveWindowSet` (`webui/client/src/api.ts:383`) has no caller.

**What it would take.** A block that turns the stored human verdicts into a `Grouping` over the same windows
(the 11,234 `manually_sorted_for_cnn` windows are the labels), and the Models pages attached to real
`windows_model` jobs with a time-blocked test split — the largest remaining build of the six.

---

## Met on the way — recorded, not fixed

- Seed page › *Open in Runs* navigates to `?run=seed_a9147c`; the run's key is `seed a9147c`. Runs answers
  *"No run named seed_a9147c in this session · Showing dehshibi_spikes instead."*
- Seed page, one cut, two figures: the Parameters card reads *"chosen 14.5 · the null gives 0 per draw"*
  beside the histogram's *"5 kept · the null gives 6.3 per draw"* (`SeedPage.tsx:341` prints the count at the
  recommended cut, and there is none). 6.3 is the payload's (1,269 null distances ≤ 14.5 over 200 draws).
- A cut dragged on the histogram is lost on reload until the search is re-run, and each re-run adds a run
  with the same label: three *"seed a9147c"* rows, keys `seed a9147c`, `_2`, `_3`.
- The promotion toast names *"exemplar E-0217"*; the row written is `motif_entry` 3609.
- The Analyse chain footer's *Pass N to Review* and *Analyse events* are disabled (*"out of slice scope"*)
  while the block page's slideshow *Send N to Review* works.
- Library › Family's *"Send 51 to Review as a queue"* was not pressed; `library/chrome.tsx:89` still carries
  *"not wired yet: POST /api/review/queues"*.

## Not exercised

A source span other than the example span; the Gramian encoders; a CNN executed rather than restored; HPC
export; Library import; Explore › Span edit; anything in `--project`.
