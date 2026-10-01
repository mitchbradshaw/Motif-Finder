# Stage 4 — the Fixup Wave

Prompts for the round after wiring (`docs/prompts/wiring/`, prompts 00–05, all run). Wiring made the
pages read and write real data. This stage fixes what the live data then showed to be wrong, broken or
missing — from the wiring reports' own "Left" / "What is still not true" lists, from the critics'
unfixed findings, and from the user's and the supervisor's use of the running app.

The numbered files (`00`–`10`) are **skeletons**: they carry the *symptoms*, grouped by page and each
traced to its evidence, and nothing else. A lettered prompt is written only once the questions behind
its symptoms are answered in `QUESTIONS.md`, because most of them are one design decision away from
being either a bug or a spec change.

## Where the stage is, 2026-10-01

**Wave 1 is done.** `E` and `G` ran in parallel on 2026-09-30, both clean, and closed every row they
were given. **Wave 2 is `F` + `J`, written and ready** — `J` needs the researcher's PDF attached.
The suite baseline is now **1799 passed / 7 skipped / 0 failed**, failure set empty.

| File | State |
|---|---|
| **WAVE 2 — run together, next** | |
| `F-datasets-and-naming.md` | **ready.** A `datasets` table keyed by `source_file`; the editable columns Q23 names; the display name replaces the file name across the site through one seam; the `CH2`/`CH3` convention settled; the Settings channel-tab overflow (U5). Port **8765** |
| `J-dehshibi-vs-the-paper.md` | **scaffold — attach the paper.** Opens with its own grilling round before any code. Two implementations of the detector exist and nothing asserts they agree; 87 % of cells on a real span are honestly marked uncovered and that is the thread to pull (U6). Port **8766** |
| **WAVE 3 — alone** | |
| `H-blocks-show-their-work.md` | *(not written — the researcher wants a grilling round first)* U7/U8/U9: process views per block, span slideshows, figures instead of tables. Now also owns the Slope page's anatomy figure, which still draws its marks from fixtures over a real trace (`E` §8.2), and the `200×` null label (Q27). Cross-cutting; conflicts with everything |
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

The baseline is **1799 passed / 7 skipped / 0 failed**, failure set empty. Under `webui/.venv`,
`test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers` fails pre-existing.
**Five smoke states are standing failures**: the four Settings registration states
(`datasets--import-check-fails-fs-unknown`, `datasets--import-check-passes-MJu26a`,
`models-registration--check-a-joblib`, `storage-backups--scan-check-a-matrix-profile`) and, since
wave 1 measured it on both a pre-change and a post-change bridge, `discovery.runs--default`.

## The open decisions

`QUESTIONS.md` is the live list, with the answers recorded beside each question as they are given.
**Rounds 1–4 are answered. Round 5 (2026-10-01) is open** and holds the two that matter:

- **Q26** — the sharkfin morphology has no recovery and no FWHM under the current definition, across
  41 % of the seed store and 34 % of the Library. Measure to the next onset, lower the fraction, or
  accept it and say so? A research decision, and it is the supervisor-facing statistic.
- **Q27** — the Aggregate page's null still says "matched random windows · 200×" and is a seeded
  jitter. Relabel now, or build the real null?

Also open and blocking nothing written: **Q-B-CHAIN** (fan-out), **U4** (fine span adjustment),
**U12** (the phantom Ctrl-C, undiagnosed), **U13** (global search unwired).

Reports go in `reports/`, cross-agent requests in `requests/`, same convention as the wiring stage.
