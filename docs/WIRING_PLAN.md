# WIRING_PLAN.md — stage 3: wiring the web UI to the core

Frontend v1 (every concept page as a working shell on fixture data, `webui/`) shipped on 2026-09-21
(`webui/PAGES_REPORT.md`: 53 pages, all ≥ 8). This document plans the next stage: making those pages read and
write the real core. It is the shared context for the agent prompts in `docs/prompts/wiring/` and says what is
decided, what is assumed, and who owns what. The open-questions register stays `docs/wayfinder/fog-of-war.md`.

## What is true today (recon, 2026-09-21)

- **Bridge.** `webui/server/` has 23 routes over the untouched core, covering only Explore (recordings, coverage,
  channel, window, spans) and Analyse chain/block (adapters, validate, compatible, params, templates, runs + SSE).
  Serialisation is one seam per side: `webui/server/serialize.py::to_payload` over the seven interchange types and
  `webui/client/src/analyse/Renderer.tsx::renderByType`. Runs are in-process daemon threads (`runs.py::RunManager`),
  ids from a counter, lost on restart. Only one write route exists (`POST /api/templates`). The SPA catch-all
  returns `index.html` for unknown `/api/*` paths. The bridge runs against a **copy** of the database under
  `webui/runtime/<stamp>/` with the step cache, two adapter `RESULTS_DIR`s and `MODEL_ROOT` redirected.
- **Client seam.** `webui/client/src/api/seam.ts` (`Sourced<T> = {data, source: 'demo'|'live'}`); **85 read
  functions across ten `src/api/<workspace>.ts` modules are all `demo(FIXTURE)`, zero `live()`**. Only Explore and
  Analyse chain/block call the bridge, through `src/api.ts` (19 functions). Writes on unwired pages go to
  `kit/store.ts` (in-memory), `kit/sim.ts` (simulated runs) or `kit/notWired.ts` (toast). Two chart kits exist:
  `charts/` + `Renderer.tsx` consume server envelope payloads; `kit/plots.tsx` consumes plain arrays.
- **Blocks.** 22 registered adapters (`Adapters/registry.py`; contract `Adapters/base.py::AdapterSpec`): 6
  preprocessing (lowpass, highpass, bandpass, detrend, surrogate, window_matrix), 12 detection (threshold,
  spike_v1, dehshibi_spikes, rupture, matrix_profile, sax_csax, sax_psax, sax_dsax, freq_stft,
  wavelet_scattering [broken: scipy `sph_harm`], and the gramian encoders), 4 catalogue (gramian_gasf/gadf/
  recurrence/fusion → cluster → classifier). **No adapter consumes an `Encoding`** (nine produce one); the
  `comparison` stage has no adapters. Outside the adapter system: the drop-motif detector family
  (`Working/Detection/drop_motifs/`, detect5 output already SpanSet-shaped), matrix-profile motif extraction and
  seed matching (`Working/Detection/matrix_profiling/{motif_groups,segments}.py`), the CNN train/apply stack
  (`Working/Catalogue/cnn/`), the aeon classifier, `wavelet_analysis.py` (a second wavelet detector, untested),
  `Working/compare.py`. FitzHugh–Nagumo exists only in prose.
- **Data.** `DATA/db/annotations.sqlite`: 11,269 human span annotations (verdicts seed/interesting/
  not_interesting/artifact/unsure; 11,234 are fixed 600-sample windows on M2_aug fs1 tagged
  `manually_sorted_for_cnn`), 704 detections over 40 runs, 70 recording rows over 6 files; **every motif-library
  table is empty** (motifs, motif_entry, motif_member, motif_edge), templates and adjudications empty; no
  groupings, window-set, family or sequence tables. Extracted singular drop-motif events live on disk:
  `DATA/library_seed/drop_motifs5/motifs/` (410 events, tracked, `PROVENANCE.md`: not regenerable),
  `Plots/drop_motifs10/motifs/` (3,511 events, species/corpus columns, gitignored),
  `Plots/drop_motifs12a/motifs_PARTIAL/` (4,023); sequences only in `Plots/drop_motifs11/sequences.csv` (118).
  Signal catalogue: `DATA/catalogue/signal_catalog.xlsx` (37 rows, 26 columns, several free-text). Unregistered
  recordings on disk: M1, M100, M101_t, MJu26a (non-uniform sampling), L_LM_Jul_26_J_raw_fs10 (fs inferred).
  `MODELS/` 13 checkpoints (~326 MB), `DATA/derived/models/` 10 classifier joblibs, `MATRICES/` 6 CSVs,
  `Results/Detection/matrix_profile/` 12 matrix-profile npz, one window matrix, no HPC results returned.
- **Docs.** No block-integration standard and no library storage convention exist as documents; both are spread
  over `docs/PIPELINE_PRD.md`, `prototyping/UI_FUNCTIONAL_SPEC.md` §4/§6.8/§8, `Adapters/base.py` and
  `Working/database/schema.py`. Spec §12 lists 24 departures from the PRD; the spec wins for the UI.

## Decisions taken (user, 2026-09-21)

1. **Sub-agents run on Opus at medium effort, never Fable.** Main agents may be Fable. (Memory: subagent-model-policy.)
2. **The Dehshibi detector is a detection TEMPLATE of blocks** (wavelet transform → summation → detection), not the
   single `detection.dehshibi_spikes` adapter. The same principle applies to every multi-stage detector: expose the
   stages as blocks with standard types and save the composition as a template.
3. **Cross-workspace writes need no ownership registry in v1** (fog F35/F36 marked out of scope, kept as a
   possible future implementation).
4. `origin` is `https://github.com/mitchbradshaw/Motif-Finder.git`.

## Decisions needed before Prompt 1 runs (defaults the agent takes if unanswered)

These are the "simulated canonical chain" gap (fog A4, F30, F31) and the persistence gap (C7, C9). Each has a
default so work can proceed; overriding one means editing the prompt's "Answers from the researcher" block.

- **D1 — Canonical detection chain.** Default: the v1 canonical *drop detection* template is the existing
  drop-motif detector decomposed into blocks (detrend → slope-noise σ → candidate onsets → trough/merge →
  SpanSet), because its output is already SpanSet-shaped and it is what the extracted events came from; the
  designed B24 chain (baseline → noise floor → symbolic encoding → Encoding→SpanSet detection) is built only if the
  researcher wants symbol search (D2). Matrix profile → threshold stays a second template.
- **D2 — Encoding consumers.** Default: none added in v1; symbolic and image encodings stay terminal display
  blocks. The alternative is an `Encoding → SpanSet` symbol-search block (regex over SAX strings) and/or
  `Encoding → Scores` CNN scoring from `Working/Catalogue/cnn/apply_cnn.py`.
- **D3 — Timescales (F31).** Default: pages show the real numbers from the data (drops are 3–236 s falls at
  1 Hz); the ×10 rule and the sub-second frame numbers are dropped.
- **D4 — Persistence (C9).** Default: the bridge gains a `--project` mode that opens the real
  `DATA/db/annotations.sqlite` (WAL, a timestamped backup under `DATA/db/backups/` on every start, held-out lock
  on) and writes machine outputs to their real locations; the current copy-and-redirect mode becomes `--sandbox`
  and stays the smoke default. The rule-5 guard (detections machine-only, annotations human-only) is enforced at
  the bridge's write seam.
- **D5 — Human writes (C7).** Default: a Review verdict on a machine detection writes `adjudications`; a verdict on
  a human span writes `annotations`; promotion to the Library writes `motif_entry`/`motif_member` (spec P21: S
  promotes). Tags/notes write `annotation_tags`/`annotations.note`.
- **D6 — Nulls (A2).** Default: `preprocessing.surrogate` stays the mechanism; Settings › Nulls holds the per-kind
  defaults (method, draws) that the pages pass to it. No per-adapter null declaration in v1.

## Sequencing and parallelism

Two agents at most at once; each prompt says who else may be running and which files are shared.

| Stage | Prompts | Why this order |
|---|---|---|
| A (alone) | **00 cleanup and foundations** | Deletes `UI/` and the Panel tests, the prototypes' code trees, stale branches; adds the `--project` bridge mode and the `/api/*` 404 — both parallel prompts depend on these and would collide editing `app.py`/`runtime.py`. |
| B (parallel) | **01 analyse/explore blocks** ∥ **02 settings import** | Disjoint: 01 owns adapters, the run/job model, `analyse/`, `explore/`; 02 owns registration of datasets/models/matrices/window sets, `settings/`. Shared: `app.py` router list, `schema.py` additive migrations, `api.ts` — small, committed immediately, named in both prompts. |
| C (parallel) | **03 library** ∥ **04 discovery** | Both need 01's block contract and job model; 03 owns library storage and grouping; 04 owns seeded search and template application. Shared: `schema.py`, `app.py`, `canon.ts`. |
| D (alone) | **05 review** | Needs 03's storage (promotion writes motif tables) and 04's queues. |

Ports: the first agent of a pair uses bridge 8765 / Vite 5173, the second 8766 / 5174 (`WEBUI_PORT`,
`npx vite --port`). Both work in the main checkout on `main` with path-scoped commits (`git commit -- <paths>`),
exactly as the ten page builders did; never `git add -A`, never stash or reset. A worktree with a copied `DATA/`
is not practical at 13 GB, and a junction to `DATA/` is forbidden (pytest and adapters would write into it).

## Standards every wiring prompt shares

- **Test-first, verified red.** A seam's first commit is a failing test (`tests/` for Python; `webui/server`
  tests are pytest too; client logic tests via `vitest` only if already present — otherwise the smoke manifest).
- **The gate.** `npx tsc -b` + `npm run build` in `webui/client`; `webui/smoke.py --url http://127.0.0.1:<port>`
  green; `pytest` with no new failures (compare failure sets; after Prompt 00 the baseline should be zero
  failures). A page that goes live keeps its `smoke_pages/<unit>.json` states, rewritten to assert live content;
  fixture states that no longer exist are removed, not left asserting fixtures.
- **Loud failure.** A bridge error is a 500 with the traceback; a render error is a red card; never a blank.
- **Rule 1** (UI libraries in UI trees), **rule 3** (plain SQL, additive migrations through `init_db()`), **rule 4**
  (bulk arrays on disk, referenced by path), **rule 5** (detections machine-only, annotations human-only) as in
  `CLAUDE.md`.
- **Held out.** `M4_aug_concat_fs1.mat` is refused on every route in both modes.
- **Sub-agents.** Critique and testing sub-agents run on Opus at medium effort with disjoint, read-only scopes;
  the main agent alone edits shared files.
- **Docs are deliverables.** `docs/BLOCK_INTEGRATION.md` (Prompt 01), `docs/DATA_REGISTRATION.md` (02),
  `docs/LIBRARY_STORAGE.md` (03) are written for a researcher adding an algorithm, a dataset or a grouping method
  next year: one page each of contract, checklist, worked example, and "what the UI needs from you".
- **Report.** Each prompt ends with a written report in `docs/prompts/wiring/reports/<nn>-<name>.md` (what was
  wired, what was left, questions for the user with the default taken) and a chat summary.

## Cleanup decisions recorded for Prompt 00

**Done 2026-09-21** — see `docs/prompts/wiring/reports/00-cleanup.md` for what was removed, moved and left.

- Tag `archive/panel-ui` at the last commit that still contains `UI/`, then delete `UI/`, `tests/ui/`,
  `scripts/dev_serve.py`, `Working/Detection/sax/dsax_python/UI_snapshot_20260810-0512/`, the 30 tests that
  import `UI` at module scope and the UI-only functions of the 7 mixed test files, `tests/_session_isolation.py`,
  `docs/UI_VERIFICATION.md` (rewrite its three inbound citations), the `ui` marker in `pytest.ini`.
- Keep and move: `UI/workspaces/review/queue_state.py` → `Working/review/queue_state.py` with its 18 tests
  (Review wiring needs it); `UI/analyse/chain_state.py` is superseded by `webui/server/chain.py` (delete, keep its
  19 tests only where they pin core behaviour); port `tests/test_plots_perf.py`'s decimation assertions to
  `webui/server/decimate.py`; keep the one test in `tests/test_ui_packages.py` that asserts the core never imports
  the Panel family (retarget it to "no Panel-family import outside `webui/`", i.e. nowhere).
- `ui-prototypes/`: keep `REPORT.md` and `DECISIONS.md` (cited ~40 times by the ADR and the fog file), delete the
  `A-react-fastapi/` and `B-panel/` code trees and screenshots; fix any citation that pointed into them.
- Delete `_to_delete/`, `flake.log` if untracked, `webui/screenshots/{critique,build,kit}` (gitignored, ~691 MB
  local), `webui/PYTEST_GATE_TASK1.txt` (superseded); keep `runs/` (orchestrator evidence) unless the user says
  otherwise.
- Branches: delete `research/*` (their single docs are on `main` in `docs/research/`), `worktree-agent-*`,
  `feat/drop-motifs-six` after `git worktree remove C:/Users/mmebr/Documents/CNN-dm6`; delete the matching remote
  branches. The 5/6-series drop-motif code was merged to `main` and later removed on `main` (commit 5b7f1fa);
  it is recoverable from history, not only from those branches.
- `CLAUDE.md`: drop the legacy `UI/`, `tests/ui/`, `scripts/dev_serve.py` rows and the "Panel surfaces" section;
  rule 1 becomes "the core imports no UI library, and nothing in the repo imports the Panel family".
