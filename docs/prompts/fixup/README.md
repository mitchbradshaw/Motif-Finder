# Stage 4 — the Fixup Wave

Prompts for the round after wiring (`docs/prompts/wiring/`, prompts 00–05, all run). Wiring made the
pages read and write real data. This stage fixes what the live data then showed to be wrong, broken or
missing — from the wiring reports' own "Left" / "What is still not true" lists, from the critics'
unfixed findings, and from the user's and the supervisor's use of the running app.

The numbered files (`00`–`10`) are **skeletons**: they carry the *symptoms*, grouped by page and each
traced to its evidence, and nothing else. A lettered prompt is written only once the questions behind
its symptoms are answered in `QUESTIONS.md`, because most of them are one design decision away from
being either a bug or a spec change.

## Where the stage is, 2026-10-02

**Waves 1 and 2 are done.** `E` + `G` ran in parallel on 2026-09-30 and `F` + `J` on 2026-10-01,
all four clean, each closing every row it was given. **Wave 3 is done too: `K` and then `H` ran 2026-10-02,
both reported.** `H` came out of the Round 7 grilling (`QUESTIONS.md`), which produced the standard it
implements; it ran through without opening a Round 8, and the three findings it made along the way are recorded
there under that heading.

**The readiness pass of 2026-10-02 produced the nine Stage 5 prompts below** (`L`, `T`, `V`, `W`, `X`, `Y`,
`Z`, `AA`, `AB`), none run yet.

**Everything that grilling found and could not scope is written down** in `future/` — seven stubs,
each carrying its evidence, so none of it has to be rediscovered.

**The suite baseline is 1952 passed / 17 skipped / 0 failed**, failure set empty, after `H` (`pytest -n 4`,
conda, 5 m 48 s). It was 1874 / 8 after wave 2 and 1878 / 13 after `K`; ten of the skips are route tests that
need FastAPI and run only under `webui/.venv`.

| File | State |
|---|---|
| **WAVE 2 — run and reported 2026-10-01** | |
| `F-datasets-and-naming.md` | **run and reported 2026-10-01** (`reports/F-datasets-and-naming.md`). Closes `10` S1, `00` X4, U5, Q23's build and the Round 5 channel-label row. One-based channel names won. Found in passing: the four standing Settings registration smoke failures name candidates that have since been registered (report §7). *As written:* A `datasets` table keyed by `source_file`; the editable columns Q23 names; the display name replaces the file name across the site through one seam; the `CH2`/`CH3` convention settled; the Settings channel-tab overflow (U5). Port **8765** |
| `J-dehshibi-vs-the-paper.md` | **run and reported 2026-10-01** (`reports/J-…`). The detector diverged from the paper in four places and the paper diverges from its authors' code; the blocks are now a port of that code, checked against MATLAB. 17 of 20 known synthetic events found; on M2_aug CH0 it is faithful and unselective (Q34). *Was:* **scaffold — attach the paper.** Opens with its own grilling round before any code. Two implementations of the detector exist and nothing asserts they agree; 87 % of cells on a real span are honestly marked uncovered and that is the thread to pull (U6). Port **8766** |
| **WAVE 3 — run and reported 2026-10-02** | |
| `K-slope-anatomy-figure.md` | **run and reported 2026-10-02** (`reports/K-slope-anatomy-figure.md`). The figure draws the store's own marks inside the context-padding window; `eventMarks` is deleted; `gradients.fall_gradients` now returns the sample its steepest slope was measured at and the slope route serves it. **Measured: the steepest sample is a median 5 % into the fall on the 410 seed events (372 in the first quarter), and it was drawn at 50 % on every one.** Smoke gains an `anatomy_marks` check and six Slope states. *As written:* Small: the Slope page's anatomy figure draws its chord, tangent and "steepest" marker from `fixtures/interrogation.ts::eventMarks` over a real trace ("steepest" is `duration / 2`). The same lie `E` removed from the numbers, surviving on the figure beside them. `D` measured the real values and `E` built the route that serves them |
| `H-blocks-show-their-work.md` | **run and reported 2026-10-02** (`reports/H-blocks-show-their-work.md`). All 36 blocks are drawn from their type signature — seven views, twelve modifiers, zero falling through to a generic view, pinned by `tests/test_block_standard.py`; the slideshow is on real samples with the impurity flag and a real *Send to Review*; both Aggregate nulls are deleted; rule 9 is in the smoke gate. Closes U7/U8/U9, Q27, `03` I7/I8, `07` R17 and the two Round 5 rows it was given. **Found:** only one of the three `scores → spanset` blocks has a draggable cut; no seed family spans two orders of magnitude; the Slope page computed its own rose angle against a different reference from the core's. *As written:* U7/U8/U9 + Q27. **Seven type views and twelve input-driven modifiers**, so all 36 blocks — and future ones — are drawn from their type signature; today 31 of 36 fall through to a view captioned *"this signature has no bespoke process view yet"*. Two tiers (chain thumbnail / settings page, one component, interaction as a flag), the span slideshow wired to real data with the impurity flag, the two fabricated nulls deleted. Enforced by a test and by a rule-9 check in the smoke gate. Cross-cutting; **runs alone** |
| **DONE** | |
| `E-aggregate-stops-fabricating.md` | **run and reported 2026-09-30** (`reports/E-…`). Interrogation reads every measure from the core — the three constants (`×0.84`, `×0.31`, `×4.2`) and the browser's recovery are gone, and not-measured is null, counted and explained. `spike-shape` → `event-shape` = `interrogation.event_shape`, a block that really differs, the upstream carried on every walk. `rise_time_frac` on the shape block, null for a drop. The overlays draw the stored context on a measured y. **Found: 41 % of the seed store and 34 % of the Library have no recovery and no FWHM under the current definition — all of it sharkfin morphology (Q26)** |
| `G-review-axis-and-resolution.md` | **run and reported 2026-09-30** (`reports/G-…`). Every Review trace carries `t` beside `v`; detection 102's drop was drawn at 0.629 h and is at 0.662 h, inside its band — the detector was right. Decimation follows the card's measured width (660 samples come back raw where 440 points used to); padding is symmetric by time; the Shape card dots its samples rather than smoothing them; source resolution reads the 10 Hz parent, default ON, and says so; Review shifts a legacy row. The `kit/plots.tsx` change stayed additive |
| `M-migrate-legacy-detections.md` | **run and reported 2026-09-28** (`reports/M-…`). 115 legacy span-relative `detections` rows across 8 runs rewritten to channel-absolute through `init_db()`, `audit_log` id 482, backup `DATA/db/backups/20260928-211406-fixup-m.sqlite` verified; re-running each run's own recipe reproduces the migrated rows exactly for 114 of 115. A second pass plans zero. Q25 |
| `D-event-features.md` | **run and reported 2026-09-23** (`reports/D-…`). The researcher's top-priority capability: `interrogation.event_shape`, `interrogation.intervals`, `preprocessing.invert`, `motif_features` keyed by content hash, the max-slope rose over the existing `gradients.py`. Adds `SpanSet.features` mirroring `WindowSet.features` — **no eighth type**. The `--real` backfill was run by the researcher 2026-09-24: 71,980 values over 3,599 hashes |
| `C-one-plot-domain-rule.md` | **run and reported 2026-09-23** (`reports/C-…`). One rule in `charts/domain.ts`: per-card measured domains with the shared scale as a reference bar, replacing PRD D5, across Review + Library + Explore. 66 clipped traces → 0 |
| `B-units-and-amplitude.md` | **run and reported 2026-09-23** (`reports/B-…`). The derived channels are volts and the whole UI labelled them mV; every amplitude ever shown was 1000× too small. The unit now lives on `recordings.units` (54 V / 5 mV / 71 undeclared) and the conversion is one seam, `corpus.display_channel` |
| `A-no-decision-fixes.md` | **run and reported 2026-09-22** (`reports/A-…`). The seventeen defects with a known cause, a known line and exactly one defensible fix |
| **SKELETONS** | |
| `00-cross-cutting.md` | the shell, the `demo` chip, shared chart primitives, naming, workflow |
| `01-explore.md` | Corpus, Signal, Cross-channel, Span edit (U4 lives here) |
| `02-analyse-chain.md` | Chain, Block, Algorithm glyphs |
| `03-analyse-interrogation.md` | Interrogation, Slope, Aggregate — I1/I4 closed by `E`, I2/I3 by `D` |
| `04-analyse-training.md` | Training chain, blocks 01–05 |
| `05-discovery.md` | Runs, Seed search, Compare, Compare every stage |
| `06-models.md` | Launch, Results, Compare, Registry |
| `07-review.md` | Queue (inspector), Cluster — R1 closed by `C` (y) and `G` (x); R3/R4/R7 are the Review *behaviour* prompt |
| `08-library.md` | Recurrence, Atlas, Family, Edit grouping, Import, Window sets, Templates |
| `09-jobs.md` | All jobs, Paused run, Upload and continue, Cluster job |
| `10-settings.md` | the sixteen settings pages — S1 is `F`'s |

## Stage 5 — prompts from the readiness pass (written 2026-10-03, none run)

Research prompt 00 (`docs/prompts/research/00-six-questions-readiness.md` → `docs/RESEARCH_READINESS.md`)
drove the app on real data and found that **none of the six PRD questions can be answered in it today**.
Nine prompts were written from that report. Three fix seams that several questions share; six are keyed
to one question each. Their decisions are `QUESTIONS.md` **Round 9 and Round 10, all answered in the 2026-10-03
grilling** and copied into each prompt's *Decided* section; a tenth prompt, `AC`, came out of it. The explicit per-question walk the
researcher follows once they land is `docs/RESEARCH_RUNBOOK.md`.

| File | Unblocks | Runs after | One line |
|---|---|---|---|
| `L-send-to-review-opens-a-queue.md` | Q2, Q4, Q5 | — (**first**) | **run and reported 2026-10-03** (`reports/L-send-to-review-opens-a-queue.md`). *Send N unjudged to Review* makes a `review_queues` row filtered by the run ids the Discovery run is made of (a queue over run group 7 would have carried 249 surrogate detections beside 74 real); *Open Review* opens that queue; a second send returns it; the chain footer's *Pass N to Review* shares the slideshow's hook; the descriptor and `GET /api/discovery/queues` are gone. **Found:** a verdict Review writes on the run's own detection moves neither *already judged* (pre-run by definition) nor *interesting* (annotations only) — handed to `X` with *precision means what it says*. *As written:* Discovery's *Send N unjudged to Review* writes a descriptor and no `review_queues` row; *Open Review* lands on another queue. Also the Analyse footer's *Pass N to Review*. The queue must filter by **run ids**, because a run group holds the paired surrogates' detections too |
| `T-surrogates-one-null-never-a-detection.md` | all | `L`; **alone** | **run and reported 2026-10-03** (`reports/T-surrogates-one-null-never-a-detection.md`). One predicate (`queries.not_surrogate`) and every reader through it: Explore's M2_aug total 576 → 546, eight annotations were "found" only by a null draw; a paired run draws N surrogates (20 template, 200 seed search), costed in the plan, and every surface prints the count that run drew; Settings offers the block's two methods; block shuffle's block is twice the motif and under 2 samples is refused; α and none/Holm/BH reach the cut per channel; the Analyse toggle is a real switch, default off. **Left:** the SLURM job draws no null; `runs` grows a row per draw. Gate: pytest 2091 passed / 20 skipped; smoke 608 shots, the 5 standing failures. *As written:* Surrogate runs' detections are counted as detections by Explore, Review and the divergence queries (30 of 1,205 in the real database); a template run is scored against one draw while the chip says 200×; Settings offers a null method the block lacks; α and the correction never reach the cut. Q35–Q38 |
| `Y-seed-sources.md` | Q2 | `L` | The seed picker is the first 24 Library entries; *Explore selection* is empty because Explore's *Take span for Review* is a demo write; a promoted exemplar cannot be chosen; four Seed-page defects |
| `V-library-edges-and-scale.md` | Q3 (and `W`) | `L`, `Y` | `motif_edge` has 0 rows and no route writes one. Matches resolve onto members with an edge per distance function; the scale bank is built; the Family page shows edges and the scale read-out. Explains what an edge is. Q39 |
| `W-cross-channel-onto-edges.md` | Q6 | `V`; **waits for Q40** | Classification reaches an edge; the Library function compares snippets, not simultaneous windows — measure first; recurrence counted with the bins taken out |
| `X-divergence-read-properly.md` | Q5 | `L`, `T` | Explore's *disagree* ignores verdict and coverage; Q-D2's two-number rule (answered 2026-09-23) was never built; the two core divergence queries have no caller; a breakdown by channel, time and morphology |
| `Z-band-scope-and-compare-by-verdict.md` | Q4 | `L` | **run and reported 2026-10-03** (`reports/Z-band-scope-and-compare-by-verdict.md`). *Apply template* has a Bands scope (Settings › Analysis defaults' named list, Q43; seeded third band 0.1–0.45 Hz, not 0.5 — Nyquist at 1 Hz): one run per band across the channels in scope, each recording exactly the hand-built chain's recipe (same hash, same runs) and paired with a bandpassed null; a band is a typed entry for `AC`. Compare takes a band set as one side (its union, de-duplicated by the matching rule, per-band rows beneath), splits the overlap by verdict live from `adjudications`, and *Send only-B unjudged to Review* queues exactly the remainder (`detection_ids`). Sandbox: union 92 regions vs `drop_detection_v1` only A 3 · both 0 · only B 92; the bands' nulls expect 297. **Found:** Compare read "0 of 5 roles differ" for a template against its banded twin (fixed). *As written:* A band scope on *Apply template* (the core's band fan-out has no caller); Compare takes a set of runs as one side; set overlap split by verdict and *Send only-B unjudged to Review*. Q43 |
| `AA-manual-labels-and-window-sets.md` | Q1 (1 of 2) | — | **run and reported 2026-10-03** (`reports/AA-manual-labels-and-window-sets.md`). `catalogue.manual_labels` labels windows from the human store by Q41 containment; the classifier trains on labelled windows only and says so; template `manual_labels_model` sits on the labels' 600/200 grid; *Save window set* writes `window_sets` rows the Library lists, coverage now and at save; window-matrix files carry span + recipe-prefix key; the footer prints the server's template kind. **Found and decided with the researcher:** one grid phase kept 3,906 of 11,110 labels, labelled-first non-overlap keeps 10,077 (Q-W1 revised). *As written:* No block reads a human label; `catalogue.manual_labels` (`WindowSet → Grouping`); *Save window set* on every WindowSet row (`window_sets` has 0 rows); the window-matrix artifact name collides with its own surrogate's. Q41 |
| `AC-wavelet-bands.md` | Q4 | `Z` | Written 2026-10-03 from Q-W3: `preprocessing.wavelet_bands` (stationary wavelet transform, Signal → Signal, the user picks which level goes on), its every-layer view, and a wavelet kind in `Z`'s band scope |
| `AB-models-paired-job.md` | Q1 (2 of 2) | `AA`; may split in three | A paired training job in the core (two label arms, blocked split, RF baseline, label-shuffle null, paired difference) and Models › Launch / Results / Compare reading it; the SLURM script the bridge writes bakes Windows paths. Q42 |

**Every Stage 5 prompt also updates its research question's file** in `docs/prompts/rq_roundA/` (`L`/`Y` → RQ2,
`V` → RQ3, `Z` → RQ4, `X` → RQ5, `W` → RQ6, `AA`/`AB` → RQ1, `T` → all), per that folder's README.

**Waves — what can run now (2026-10-03).** Two at a time, never more; each prompt carries a *Running in
parallel* section naming its partner and the file split.

| wave | prompts | why together |
|---|---|---|
| **1 — now** | **`AA` ∥ `Y`** | disjoint (Analyse/training core vs Discovery seed + Explore); the researcher's first priority is a trained model, so `AA` starts now |
| 2 | `AB` ∥ `Z` | `AB` needs `AA`; `Z` needs only `L`. Share `discovery.py` — `AB` the `/slurm` writer only |
| 3 | `T` **alone** | cross-cutting; touches every count |
| 4 | `V` ∥ `X` | `V` needs `Y` (and `T` for true nulls); `X` needs `T`. Share `RunsPage.tsx` — separate components |
| 5 | `W` ∥ `AC` | `W` needs `V`'s edges; `AC` needs `Z`'s band scope |

**Order and parallelism (as first written).** Two independent lines: the Discovery/Library line `L` → (`Y` ∥ `Z`) → `T`
(alone) → (`V` ∥ `X`) → `W`; and the Q1 line `AA` → `AB`, which touches Adapters, `training_routes.py` and
the Models tree and can run beside any of the others under the two-prompt rules below. `L` is a day;
`AB` is the largest and should start early. Each prompt names its own owned files and what it leaves to
its neighbours.

## Running two prompts at once

Wave 1 proved it works and showed where it chafes (`QUESTIONS.md` Round 5). The rules both wave-2
prompts carry:

1. **Disjoint page trees, disjoint server modules, separate `smoke_pages` files.** Each prompt
   carries an ownership table naming the other agent's files.
2. **A private port and a private client build.** **`run_server.py --dist DIR` exists as of
   2026-10-01** (`addb4f0` red → `fc08257` green; env `WEBUI_DIST`). Build with
   `npx vite build --outDir <yours>` in `webui/client` and serve that, so the shared
   `webui/client/dist` is never anyone's working bundle — without it, whoever builds last owns it,
   and in wave 1 that cost `G` its before/after baseline mid-run. A relative `--dist` is made
   absolute before `Runtime.setup()` chdirs, a `--dist` that is not a directory is refused the way
   a busy port is, and a bridge on a private build **says so in its banner** (`CLIENT = …`) and in
   `/api/runtime`.
3. **`npm run build` is `tsc -b && vite build`** and type-checks the whole tree, so the other
   agent's in-flight files can make it red. Run it for the gate at the end; `npx vite build
   --outDir …` to get something to serve meanwhile.
4. **`pytest -n auto` and `webui/smoke.py` cannot run together on this machine** (prompt `B` §9: 23
   spurious smoke failures). `pytest -n 4`, and announce in the report when the machine was taken
   for smoke.
5. **Shared files are append-only and committed immediately, path-scoped** — `webui/client/src/api.ts`,
   `webui/smoke.py`. A path-scoped commit can still carry the other agent's hunks.

## Standing gate facts

The baseline is **1952 passed / 17 skipped / 0 failed**, failure set empty (after `H`, 2026-10-02). Ten of
the skips need FastAPI and so run only under `webui/.venv` (`test_webui_dataset_naming.py`, five route tests
of `test_webui_slope_anatomy.py`, four of `test_webui_block_views.py` — the last file skips them one by one). Under `webui/.venv`,
`test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers` fails pre-existing.
**Five smoke states are standing failures**: the four Settings registration states
(`datasets--import-check-fails-fs-unknown`, `datasets--import-check-passes-MJu26a`,
`models-registration--check-a-joblib`, `storage-backups--scan-check-a-matrix-profile`) and, since
wave 1 measured it on both a pre-change and a post-change bridge, `discovery.runs--default`.
**`F` found the cause of the four** (report §7) and did not fix them: each state names a specific
*unregistered* candidate and clicks its Check button, and every one of those candidates has since
been registered in the real database the sandbox copies — so the button is disabled and
`Locator.click` waits 30 s. The first is a one-word fix (`path=F2B`); the "passes" state has no
candidate left that passes without typed input, so it needs a fixture candidate or a different
assertion. Whoever takes them should say so in their own report rather than quietly re-pointing a
standing failure.

**A sixth state flakes on a cold bridge.** `analyse.interrogation--fixup-d-sequence-rose` was still
showing *"measuring the events of sequence 1…"* at its 4000 ms allowance on the clean gate run of
2026-10-02, and passed — with all 49 interrogation states — on a re-walk against the same bridge
once warm; the route it waits on answers 200 in 20–55 ms. That is cold-start cost, the same class as
`discovery.runs--default`, and the allowance was deliberately **not** raised, because it measures the
page's first paint. Two cold-start flakes is a pattern: whoever next owns `smoke.py` should look at
the first-touch allowance across the whole walk rather than at these two states.

**The clean gate run, 2026-10-02, after `H`** — a fresh `--sandbox` bridge alone on the machine: **602
screenshots over 584 page states, 5 failures** (the five standing; the flake above did not occur), **0 browser
console/page errors, 0 unexpected server tracebacks**. The tracked set in `webui/screenshots/` is the
`cd18360` run's, with the Interrogation and Analyse-run pages replaced by this one's.

**Three things `H` learned about the gate itself**, for whoever runs it next:

- **A partial walk is not the gate.** `--only zz_` passed while the full walk failed every chain run: the
  bridge keeps Discovery's jobs in the same table as chain runs, and a bug that only shows once another kind of
  job exists cannot be seen by walking Analyse alone.
- **A state that runs a chain after another state has set a source cannot click `use-example`** (the button
  is only there with no source). `{"click_if": selector}` is an optional click.
- **Screenshot writes into the tracked tree fail now and then with `[Errno 22]`** — a different handful each
  run, never in a scratch directory, cause not found. `smoke.py` retries the write; point `SMOKE_SHOTS` at the
  scratchpad if it comes back.

## The open decisions

`QUESTIONS.md` is the live list, with the answers recorded beside each question as they are given.
**Rounds 1–4, 6 and 7 are answered; Round 5 still holds one open decision** — a research decision rather
than an engineering one, with the measurement behind it. (Q27 was the other; `H` closed it by deleting both
nulls. Building the real one is `future/R-interrogation-null.md`.)

- **Q26 — mostly dissolved, 2026-10-02, by the researcher's reframe.** It was "the sharkfin morphology
  has no recovery and no FWHM, across 41 % of the seed store and 34 % of the Library". The researcher's
  reading — a sharkfin is a *trough whose slow rise back up is its recovery*, which the detector has
  attributed to the next fall as its precursor — is **measured and correct**
  (`scripts/q26_sharkfin_recovery.py`, `QUESTIONS.md` "Q26, REVISED"): searching from the trough to the
  **next onset** on the real channel instead of to the end of the stored snippet, **121 of 154 sharkfins
  reach half recovery** (113 reach 90 %) at a median **199 s** — against a stored post-context of
  **121 s**. Exactly one of 154 genuinely fails. The 41 % is an artifact of the stored window, and on two
  families also of a **detrend window shorter than the recovery** (id029 110 s vs 40 s, id024 780 s vs
  476 s), which subtracts part of it from the stored values. What survives is a *timing* difference,
  which nothing measures: a sharkfin sits on its floor — drifting slightly lower — for half to
  two-thirds of the interval, then climbs. **The live question is now Q26d: does the slow rise belong to
  the event before it (its recovery) or the event after it (its precursor)?** Both cannot be true of the
  same samples, so one event's extent is wrong today. That is `future/N-event-extent.md`, not a fixup.
**Q34** is answered (2026-10-02): keep the Dehshibi detector as an untuned baseline. `J` made it
faithful to its authors' code and measured it as weak on these recordings — on M2_aug CH0 its spans
cover 53 % of the labelled time and hit 91 % of *interesting* windows against 86 % of *not
interesting* ones. Whether to tune `epsilon_factor` / `min_separation_s` / `window_s` is a later
research question, not a fixup.

**Q-B-CHAIN** is out of scope (2026-10-03) and parked in `docs/prompts/rq_roundB/` with multivariate analysis.
Also open and blocking nothing written: **U4** (fine span adjustment),
**U12** (the phantom Ctrl-C, undiagnosed), **U13** (global search unwired).

## Recorded for later, not scoped

`future/` holds seven stubs from the Round 7 grilling, each with the finding and the evidence that
created it: `N-event-extent` (the `6 × fall` cap beats the morphology bracket on ~half of catalogue
events, and re-defining extent re-hashes 3,603 Library rows), `R-interrogation-null` (build P10
properly), `P-persist-recovery-index` (`recovery_idx` is computed and dropped one line before it
could be stored), `Q-extent-corrections` (the human-correction path is written and called by
nothing), `S-reports` (**inherits `H`'s standard, never a second one**), `U12-bridge-sigint`,
`U13-global-search`.

## What is left after wave 3

Not prompts yet, in rough order of how much friction each removes:

| | why it is not written |
|---|---|
| **Review behaviour** — `07` R3 (a class 1/2/3/4/9 is never stored), R7 (a rediscovery can be put twice — carry the prior verdict), R8's "sorted by score" wording, R16 coherence; **plus the blind-labelling mode for RQ1's yardstick (B)** (Q42: hides the model's guess, the cluster vocabulary as buttons). R4's extract-events editor is its own later prompt (Q16) | Decided (Q16, Q42); nobody has written the prompt. R3 and R7 are the two that cost the researcher real time |
| **Library** — the filters Q21/Q22 settled (noise floor as a view filter, `fall_duration_s` not `scale_band`, `is_pure`), `RULE_VERSION` and the `rise_time_s` backfill; **click a cluster → its members in place in the `H` slideshow** (Q-L6/Q-E6); **the rose reference = the median steepest slope over human-accepted Library motifs, printed on every rose** (Round 10) | The decisions are made; nobody has written the prompt. Q-L5 (polar / cube plots) is dropped for this stage |
| **Jobs, Models, Training** | Still fixture pages wearing the `demo data` chip. `F` noted their labels must come from `corpus.dataset_name` when they are wired |
| **`I`** — U4, Explore's fine span adjustment | Small and self-contained |
| **U13** global search; **U12** the phantom Ctrl-C | U13 needs a design; U12 needs reproduction, not a guess |

Reports go in `reports/`, cross-agent requests in `requests/`, same convention as the wiring stage.
