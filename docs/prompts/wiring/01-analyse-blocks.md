# Prompt 01 — Analyse and Explore: every backend algorithm runnable from the web UI (parallel with 02)

You are working in `C:\Users\mmebr\Documents\CNN` (Windows; Bash tool = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md`, then `docs/WIRING_PLAN.md` in full (the "Decisions
needed" defaults D1–D6 bind you unless the block below overrides them), then `Adapters/base.py`,
`webui/server/{app,chain,runs,serialize,runtime}.py`, `webui/client/src/analyse/Renderer.tsx`,
`webui/client/src/api.ts`, `webui/client/src/api/{analyse,explore,interrogation,training}.ts` and
`prototyping/UI_FUNCTIONAL_SPEC.md` §6 (Analyse), §6.8 (the block contract table) and §3 (plot rules). Work
autonomously; prefer a defensible default over a question; questions you cannot reasonably decide go in your
report with the default you took. Commit prefix `wire-analyse:`. Push `main` at the end.

**Another agent is running Prompt 02 (Settings import/registration) in this same checkout at the same time.**
It owns `webui/server/registration*.py`, `webui/client/src/settings/`, `src/api/settings.ts`,
`src/fixtures/settings.ts`, `docs/DATA_REGISTRATION.md` and `Working/registration/` (new). You do not edit those.
Shared files you may both touch — edit in small, self-contained hunks and commit immediately with `--` paths:
`webui/server/app.py` (add your routers as `app.include_router(...)` lines only; put routes in your own modules),
`Working/database/schema.py` (additive migrations only, each in its own function, applied by `init_db()`),
`webui/client/src/api.ts` (append functions; never reorder), `webui/client/src/fixtures/canon.ts`,
`webui/smoke.py` (only to extend, never to change existing checks). Use ports **8765 / 5173**; the other agent
uses 8766 / 5174. Never `git add -A`, stash, reset or checkout; never touch the other agent's files; if you must,
write the request to `docs/prompts/wiring/requests/01-to-02.md` and work around it.

## Answers from the researcher

(Empty means: take the plan's defaults D1–D6. If the user pastes answers here, they override the defaults.)

## Goal

1. **Every algorithm the backend has is available as a block in the web UI, wired to the real function**, with
   the right input/output types, parameters, plots and thumbnails — including the ones that are not adapters
   today. The Dehshibi detector (decision 2) and every multi-stage detector are exposed as blocks and composed into
   saved detection **templates**, not single blocks.
2. **A written standard** for wiring an algorithm: `docs/BLOCK_INTEGRATION.md`.
3. **Analyse and Explore read and write live**: chain runs against real recordings in project mode, block pages
   with real parameter sweeps, Interrogation and Training blocks on real events/windows where the data exists,
   Explore's demo regions (tags, reviewed coverage, run/method filters, cross-channel) reading the database.

## The standard (`docs/BLOCK_INTEGRATION.md`) — write it first, then make every block obey it

One page a researcher can follow to add an algorithm next year. Sections, in this order:
- **What a block is.** One `AdapterSpec` (`Adapters/base.py`), `run(x, t, fs, **params) → AdapterResult`, exactly
  one `input_kind` and one `output_kind` from the seven interchange types, parameters as `ParamSpec`s (typed,
  bounded, with defaults that enter the recipe hash), optional `side_inputs`, `estimate`, `recommend`, `derive`,
  `persist`, `max_span_samples`. Say explicitly: **no `input_kind=None`** — every root-signal block declares
  `'signal'` (normalise `detection.matrix_profile` and `preprocessing.window_matrix`).
- **What the UI needs from it.** Per output type, what the server serialises (`serialize.py`) and what the client
  renders (`Renderer.tsx`): Signal (envelope), Scores (envelope + top-k + histogram), SpanSet (bands), WindowSet
  (starts + features), Encoding symbolic/image, Grouping, Model card. A block gets a plot and a thumbnail for free
  from its output type; a block needs its own `plot` only for a block-page detail the type renderer cannot draw,
  and then it is a **payload** (JSON the client draws), never a matplotlib figure sent to the browser. Say where
  the block's **glyph** comes from (`webui/client/src/analyse/glyphs.tsx` registry keyed by adapter name — remove
  the hard-coded `_CATEGORY`, `_PAGE_NAME`, `_KNOWN_BROKEN` dicts in `webui/server/chain.py` by moving
  `category` and `page_name` onto `AdapterSpec`, and make an unknown category loud).
- **Cost.** Every block declares `estimate` (seconds for n samples at fs, from a calibration file the way
  `matrix_profile` and `window_matrix` do) or is refused above `max_span_samples` with the reason; the interactive
  ceiling is read from Settings › Compute (`LOCAL_LIMITS`), over-ceiling stages get *Create SLURM script* (P4).
- **Templates.** A template is a named, versioned chain (`templates` table) with a kind (detection / encoding /
  training / interrogation). The canonical templates ship as code (`webui/server/templates.py`), seeded into the
  table on first `--project` start, editable copies thereafter.
- **Checklist** (the researcher's steps): write `Adapters/<stage>_<name>.py`; register; unit test the adapter
  (types, defaults, `validate_params`, one run on a synthetic signal); add its glyph; add a smoke state for its
  block page; run the gate. Nothing else changes anywhere — that is the contract, and the doc says why.
- **Worked example**: the block you add for the Dehshibi summation stage.

## Blocks to wire (do them in this order; each is test-first, then a commit)

1. **Normalise the 22 registered adapters** to the standard (input kinds, estimates where missing — dehshibi,
   cluster, classifier; `persist` for classifier and cluster; glyphs; category/page_name on the spec). Fix or
   quarantine `detection.wavelet_scattering` (scipy `sph_harm` import error): try the kymatio-free path in
   `Working/Detection/wavelet/` first; if it needs a dependency change, do not install anything — mark it
   `known_broken` with the reason shown on its card and list it in your report with an estimate.
2. **Dehshibi as a template.** Split `Working/Detection/analysis/dehshibi_detection_analysis.py` into blocks:
   `preprocessing.wavelet_transform` (Signal → Signal or Scores — choose by what the paper's next step consumes),
   `detection.wavelet_summation` (→ Scores), `detection.summation_threshold` (Scores → SpanSet, reuse
   `detection.threshold` if the semantics match). Save `dehshibi_spikes` as a template of those blocks; delete or
   deprecate the monolithic adapter (keep its tests by pointing them at the template run).
3. **Drop detection as blocks + the canonical template (D1).** Wrap `Working/Detection/drop_motifs/detect5.py`
   into separable blocks (detrend/slope-noise σ → candidate onsets → trough & merge → SpanSet with onset/trough
   labels and depth/slope scores in `meta`), register the composition as template `drop_detection_v1`. This is the
   chain the Analyse frames call "the canonical chain" — the demo `demo.*` blocks and `DEMO_TEMPLATES` go away.
4. **Matrix-profile motifs.** `Working/Detection/matrix_profiling/motif_groups.py` → `detection.mp_motifs`
   (Scores → SpanSet with group ids) and `segments.seed_matches` → `detection.seed_matches` (Signal + a
   library-exemplar side input → Scores/SpanSet). Discovery's seeded search (Prompt 04) will call the latter — keep
   its signature simple and document it in the standard.
5. **Encoding consumers (D2 default: none)** — if the answers block asks for symbol search or CNN scoring, add
   `detection.symbol_search` (Encoding → SpanSet) and/or `catalogue.cnn_score` (Encoding → Scores, from
   `apply_cnn.py`, model path from the registry Prompt 02 builds — read its `docs/DATA_REGISTRATION.md` if present,
   else take the model path as a parameter).
6. **Training chain.** `preprocessing.window_matrix` → `catalogue.cluster` → `catalogue.classifier` is the real
   training chain; make Training 01–05 read live: sliding windows from the real `windows` payload, the window
   matrix from the real features, clustering from `catalogue.cluster`, encode from the gramian blocks, model card
   from `catalogue.classifier`; **P12 leakage guards** (gap ≥ window, blocked-by-time split) implemented as
   parameters of the sliding-windows block, validated in the core. "Save window set" writes an artifact row
   (`kind='windowset'`, npz on disk) — coordinate the table with Prompt 03 through `schema.py` additively.
7. **Interrogation.** Slope and aggregate blocks read real events: the slope features from
   `Working/Detection/drop_motifs/` (onset, steepest, trough, depth, recovery) over the family's members
   (members come from the event store Prompt 03 imports; until then, from `DATA/library_seed/drop_motifs5/motifs/`
   read directly, clearly marked as the seed).
8. **Explore live regions.** Tags and reviewed coverage from `annotation_tags`/`reviewed_spans`; run/method
   filters on coverage (`GET /api/corpus/{file}/coverage?run=&method=`); cross-channel from real channels of the
   same recording; "Take span for Review" writes an `annotations` row with verdict `seed` through
   `writes.write_human` (rule 5).
9. **Job model.** Grow `RunManager` into `webui/server/jobs.py`: persisted `jobs` table (additive), kinds
   `chain_run | sweep | import | regroup | training`, SSE per job at `/api/jobs/{id}/events`, cancel, restart-safe
   snapshot from the `runs` row. Keep the existing run routes working (they become thin wrappers). Prompts 02–05
   will use it; document its API in `docs/BLOCK_INTEGRATION.md` under "Long work".

## Client

- Replace every `demo(FIXTURE)` in `src/api/{analyse,explore,interrogation,training}.ts` with `live(...)` calls
  one function at a time; the `Sourced.source` flag drives the header's demo chip automatically (make `Header`
  derive `demo` from the page's sourced reads if any is still demo — a shared file, small edit, commit alone).
- Pages built on `kit/plots.tsx` that now receive server payloads render them through the `charts/` renderers; do
  not decimate in the browser what the server already decimated.
- Deep links and smoke states stay; rewrite each state's `expect` to live content. Keep `?state=running|failed`
  reachable by starting a real short run on a synthetic-length span, or drop the state if it cannot be honest.

## Testing and critique

- Python: one test module per new adapter (`tests/test_adapter_<name>.py`), a test per template that runs it on a
  30 s synthetic signal end to end through `execute_recipe`, tests for the job table and the SSE replay. Run
  `pytest -n auto`; the baseline after Prompt 00 is zero failures — keep it there.
- Client: `npx tsc -b`, `npm run build`, `smoke.py --url http://127.0.0.1:8765` (sandbox) green; in addition run
  the bridge once in `--project` mode on a real recording (M2_aug fs1, one channel, a 2 h span) and drive one
  chain run of each template with Playwright, screenshot the results to `webui/screenshots/wiring/01/`, and stop
  the servers you started.
- After the blocks and again after the client, spawn critics on **Opus at medium effort**, read-only, disjoint
  scopes: (a) a *contract* critic that checks every registered adapter against `docs/BLOCK_INTEGRATION.md` and
  the standard's checklist and scores the doc's clarity for a newcomer 1–10; (b) a *function* critic that drives
  Analyse chain, three block pages, Training 01–05 and Interrogation on the live server and reports P0/P1/P2 as in
  `webui/critique/`; (c) a *data-truth* critic that compares what a live page shows against a direct query of the
  database or the artifact file. Fix P0/P1; re-run the critics once.

## Unfinished algorithms — propose, do not silently skip

For each algorithm you could not wire (wavelet_scattering, `wavelet_analysis.py`'s second detector, the
`comparison` stage, FitzHugh–Nagumo which has no implementation, `compute_spike_statistics` stub, anything in
`Pipelines/` you judged a real block), write in the report: what it is, what is missing, an hour estimate to
finish it to the standard, and the options *finish* / *ignore for v1*. Do not spend more than 1 h on any one of
them before writing it up.

## Report

`docs/prompts/wiring/reports/01-analyse-blocks.md`: blocks wired (table: name, types, template, tests, glyph,
estimate), templates seeded, routes added, client functions switched demo → live (count per module), critics'
scores and what you fixed, unfinished algorithms with estimates, questions with the default taken, how to start
the app in project mode. End with the chat summary.
