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
all four clean, each closing every row it was given. **Wave 3: `K` ran 2026-10-02 and is
reported; `H` is ready and runs alone.** `H` came out of the Round 7 grilling (`QUESTIONS.md`), which produced the
standard it implements and corrected two of my own recommendations by measurement.

**Everything that grilling found and could not scope is written down** in `future/` — seven stubs,
each carrying its evidence, so none of it has to be rediscovered.

**The suite baseline is 1874 passed / 8 skipped / 0 failed**, failure set empty, verified on the
merged tree after both wave-2 prompts landed (neither agent could run it on the final state, because
each had the other's tests in flight). `pytest -n auto`, conda, 5 m 45 s.

| File | State |
|---|---|
| **WAVE 2 — run and reported 2026-10-01** | |
| `F-datasets-and-naming.md` | **run and reported 2026-10-01** (`reports/F-datasets-and-naming.md`). Closes `10` S1, `00` X4, U5, Q23's build and the Round 5 channel-label row. One-based channel names won. Found in passing: the four standing Settings registration smoke failures name candidates that have since been registered (report §7). *As written:* A `datasets` table keyed by `source_file`; the editable columns Q23 names; the display name replaces the file name across the site through one seam; the `CH2`/`CH3` convention settled; the Settings channel-tab overflow (U5). Port **8765** |
| `J-dehshibi-vs-the-paper.md` | **run and reported 2026-10-01** (`reports/J-…`). The detector diverged from the paper in four places and the paper diverges from its authors' code; the blocks are now a port of that code, checked against MATLAB. 17 of 20 known synthetic events found; on M2_aug CH0 it is faithful and unselective (Q34). *Was:* **scaffold — attach the paper.** Opens with its own grilling round before any code. Two implementations of the detector exist and nothing asserts they agree; 87 % of cells on a real span are honestly marked uncovered and that is the thread to pull (U6). Port **8766** |
| **WAVE 3 — `K` done, `H` next and alone** | |
| `K-slope-anatomy-figure.md` | **run and reported 2026-10-02** (`reports/K-slope-anatomy-figure.md`). The figure draws the store's own marks inside the context-padding window; `eventMarks` is deleted; `gradients.fall_gradients` now returns the sample its steepest slope was measured at and the slope route serves it. **Measured: the steepest sample is a median 5 % into the fall on the 410 seed events (372 in the first quarter), and it was drawn at 50 % on every one.** Smoke gains an `anatomy_marks` check and six Slope states. *As written:* Small: the Slope page's anatomy figure draws its chord, tangent and "steepest" marker from `fixtures/interrogation.ts::eventMarks` over a real trace ("steepest" is `duration / 2`). The same lie `E` removed from the numbers, surviving on the figure beside them. `D` measured the real values and `E` built the route that serves them |
| `H-blocks-show-their-work.md` | **ready.** U7/U8/U9 + Q27. **Seven type views and twelve input-driven modifiers**, so all 36 blocks — and future ones — are drawn from their type signature; today 31 of 36 fall through to a view captioned *"this signature has no bespoke process view yet"*. Two tiers (chain thumbnail / settings page, one component, interaction as a flag), the span slideshow wired to real data with the impurity flag, the two fabricated nulls deleted. Enforced by a test and by a rule-9 check in the smoke gate. Cross-cutting; **runs alone** |
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

The baseline is **1874 passed / 8 skipped / 0 failed**, failure set empty (verified on the merged
tree, 2026-10-02). The eighth skip is `tests/test_webui_dataset_naming.py`, which needs FastAPI and
so runs only under `webui/.venv`. Under `webui/.venv`,
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

**The clean gate run, 2026-10-02** — client rebuilt, every earlier bridge and browser stopped, a
fresh `--sandbox` bridge alone on the machine: **573 screenshots, 6 failures** (the five standing
plus the flake above), **0 browser console/page errors, 0 unexpected server tracebacks**. The
tracked screenshot set in `webui/screenshots/` is that run's output (`cd18360`); the sets the
wave-2 agents left behind were taken with two browsers and two bridges running at once.

## The open decisions

`QUESTIONS.md` is the live list, with the answers recorded beside each question as they are given.
**Rounds 1–4, 6 and 7 are answered; Round 5 is still open** and holds the two that matter — both are
research decisions rather than engineering ones, and both now have the measurement behind them:

- **Q26** — the sharkfin morphology has no recovery and no FWHM under the current definition, across
  41 % of the seed store and 34 % of the Library. Measure to the next onset, lower the fraction, or
  accept it and say so? A research decision, and it is the supervisor-facing statistic.
- **Q27** — the Aggregate page's null still says "matched random windows · 200×" and is a seeded
  jitter. Relabel now, or build the real null?

**Q34** is answered (2026-10-02): keep the Dehshibi detector as an untuned baseline. `J` made it
faithful to its authors' code and measured it as weak on these recordings — on M2_aug CH0 its spans
cover 53 % of the labelled time and hit 91 % of *interesting* windows against 86 % of *not
interesting* ones. Whether to tune `epsilon_factor` / `min_separation_s` / `window_s` is a later
research question, not a fixup.

Also open and blocking nothing written: **Q-B-CHAIN** (fan-out), **U4** (fine span adjustment),
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
| **Review behaviour** — `07` R3 (a class 1/2/3/4/9 is never stored), R4 (no extract-events editor), R7 (a rediscovery can be put twice), R8's "sorted by score" wording, R16 coherence | Needs Q-R1…Q-R4 answered. R3 and R7 are the two that cost the researcher real time |
| **Library** — the filters Q21/Q22 settled (noise floor as a view filter, `fall_duration_s` not `scale_band`, `is_pure`), the window-sets unblock, `RULE_VERSION` and the `rise_time_s` backfill | The decisions are made; nobody has written the prompt |
| **Jobs, Models, Training** | Still fixture pages wearing the `demo data` chip. `F` noted their labels must come from `corpus.dataset_name` when they are wired |
| **`I`** — U4, Explore's fine span adjustment | Small and self-contained |
| **U13** global search; **U12** the phantom Ctrl-C | U13 needs a design; U12 needs reproduction, not a guess |

Reports go in `reports/`, cross-agent requests in `requests/`, same convention as the wiring stage.
