# Report — Prompt 01: Analyse and Explore, every backend algorithm runnable from the web UI

Run 2026-09-21 on `main`, in the main checkout, in parallel with Prompt 02 (`wire-settings:` commits interleave
with the `wire-analyse:` ones below). Ports used: bridge 8765 (sandbox, smoke and critics), 8767 (project mode,
the real-recording runs). Both servers were stopped at the end.

## What was wired

### The standard

`docs/BLOCK_INTEGRATION.md` — one page: what a block is (the spec, the seven types, `run`'s calling
convention, the hooks), what the UI needs from it (per-type payload and renderer, the glyph registry, names
and flags on the spec), cost (estimates, calibration files, ceilings), templates (rows, kinds, seeding,
"a multi-stage detector is a template"), the researcher's checklist, the worked example
(`detection.wavelet_summation`), long work (the job model), and reuse-vs-add. `tests/test_block_standard.py`
is the standard made checkable and runs over every registered block.

`AdapterSpec` gained `category`, `page_name` and `known_broken`; `input_kind` defaults to `'signal'` and
`None` is refused. The bridge's three side tables in `server/chain.py` are gone. Three old pins that encoded
"`None` means root signal" and "detectors are free" were retargeted, and say so in their commit.

### Blocks

| Block | Types | Category | Template(s) | Test module | Glyph | Cost |
|---|---|---|---|---|---|---|
| preprocessing.detrend (+ mode `rolling_mean_nearest`) | Signal → Signal | preprocess | drop_detection_v1, mp_*, dsax_*, symbol_search, gramian_gasf | test_t07_adapter_remap | own | free (O(n)) |
| **preprocessing.wavelet_transform** | Signal → Encoding (image 64 × n) | encode | dehshibi_spikes | test_adapter_wavelet_transform | own (new) | estimate (block_cost) |
| **detection.wavelet_summation** | Encoding → Scores | detect | dehshibi_spikes | test_adapter_wavelet_summation | own (new) | free |
| **detection.summation_threshold** | Scores → SpanSet | detect | dehshibi_spikes | test_adapter_summation_threshold | own (new) | free |
| detection.dehshibi_spikes (monolith) | Signal → SpanSet | control (deprecated) | — | test_t06_adapter_remap | own | estimate (block_cost) |
| **detection.stage_encoding** | Signal → Encoding (symbolic, 5) | encode | drop_detection_v1 | test_adapter_stage_encoding | own (new) | free |
| **detection.drop_detection** | Encoding → SpanSet | detect | drop_detection_v1 | test_adapter_drop_detection | own (new) | free |
| detection.matrix_profile (input_kind now explicit) | Signal → Scores | detect | mp_threshold, mp_motifs | test_matrix_profile_store | own | estimate + ceiling (calibrated) |
| detection.threshold | Scores → SpanSet | detect | mp_threshold, cnn_detection | test_t08… | own | free |
| **detection.mp_motifs** | Scores → SpanSet (groups) | detect | mp_motifs | test_adapter_mp_motifs | own (new) | free (stumpy.match per seed) |
| **detection.seed_matches** | Signal + exemplar → SpanSet | detect | (Discovery, Prompt 04) | test_adapter_seed_matches | own (new) | free |
| **detection.symbol_search** | Encoding → SpanSet | detect | symbol_search | test_adapter_symbol_search | own (new) | free |
| detection.sax_csax / psax / dsax | Signal → Encoding | encode | dsax_encoding, symbol_search | test_sax_adapters | own | free |
| detection.freq_stft, detection.rupture, detection.spike_v1 | as before | encode / detect | — | existing | own | free |
| detection.wavelet_scattering (**fixed**) | Signal → Encoding | encode | — | test_block_standard | own | estimate (block_cost) |
| preprocessing.window_matrix (input_kind now explicit) | Signal → WindowSet | cluster | windows_model | test_window_matrix_* | own | estimate + ceiling (calibrated) |
| **preprocessing.sliding_windows** | Signal → WindowSet (+ split) | cluster | cnn_detection | test_adapter_sliding_windows | own (new) | free |
| catalogue.cluster (+ estimate, persist, ignores `split`) | WindowSet → Grouping | cluster | windows_model | test_grouping_adapter | own | estimate (None: cost is in windows) |
| catalogue.classifier (+ persist kind=model, ignores `split`) | Grouping + windows → Model | model | windows_model | test_model_adapter | own | estimate (None) |
| **catalogue.window_images** | WindowSet → Encoding (stack) | encode | cnn_detection | test_adapter_cnn_score | own (new) | ceiling (max_windows) |
| **catalogue.cnn_score** | Encoding + windows → Scores | model | cnn_detection | test_adapter_cnn_score | own (new) | estimate (block_cost) |
| catalogue.gramian_gasf / gadf / recurrence / fusion | Signal → Encoding | encode | gramian_gasf | existing | own | ceiling 5000 |
| preprocessing.lowpass / highpass / bandpass / surrogate | Signal → Signal | preprocess / control | — | existing | own | free |

33 registered blocks (22 before). `detection.wavelet_scattering` runs again: kymatio's 1-D frontend is
imported by its own module path, bypassing the package `__init__` that pulls the 3-D frontend and its removed
`scipy.special.sph_harm`. No dependency was installed or changed.

**Fidelity checks.** `dehshibi_spikes` reproduces the monolithic `detect_spikes` span for span
(`tests/test_template_dehshibi.py`; the synthetic signal had to be a broad depolarisation with a sharp core —
a grid search found the monolith confirms nothing simpler, and it confirmed nothing on four real slices of
M2_aug either; that is the paper's Algorithm 4 nesting rule, reported as found). `drop_detection_v1` reproduces
`detect_drops5` event for event on a synthetic train and **reproduces the 17 seed events of span id001 onset
for onset and trough for trough** (`tests/test_template_drop_detection.py::test_template_reproduces_the_seed_events_of_span_id001`),
under the two detect5 flags the drop_motifs5 store predates (`bracket_on_fall_runs=False`,
`walk_onset_back=False`, both exposed as block parameters) — D1's check against the seed, passed on the
reference span. `detect5.py` was split into `stage_letters` / `morphology_from_letters` / `detect_from_letters`
with `detect_drops5` unchanged in behaviour (its 31 tests stay green); `detrend_window_s <= 0` now means
"already detrended".

### Templates seeded (`webui/server/templates.py::CANONICAL`, rows in `templates`)

| name | kind | chain |
|---|---|---|
| drop_detection_v1 | detection | detrend (rolling_mean_nearest) → stage_encoding → drop_detection |
| dehshibi_spikes | detection | wavelet_transform → wavelet_summation → summation_threshold |
| mp_threshold | detection | detrend → matrix_profile → threshold |
| mp_motifs | detection | detrend → matrix_profile → mp_motifs |
| dsax_encoding | encoding | detrend → sax_dsax |
| symbol_search | detection | detrend → sax_dsax → symbol_search |
| windows_model | training | window_matrix → cluster → classifier |
| cnn_detection | detection | sliding_windows → window_images → cnn_score → threshold |
| gramian_gasf | encoding | detrend → gramian_gasf |

`templates` gained `kind, version, builtin, description, created_at, updated_at` (additive; my hunk was
committed inside Prompt 02's `f1ecd4e` because both agents had uncommitted edits in `schema.py` and their
whole-file commit carried it — recorded here for provenance). Builtin rows are copied, never edited; a copy's
`version` increments per edit. The demo `DEMO_TEMPLATES` / `demo.*` blocks are **not** removed (see "Left").

### Routes added

| Route | What |
|---|---|
| `GET/POST /api/templates`, `GET/PUT/DELETE /api/templates/{id}`, `POST /api/templates/{id}/apply` | rows, CRUD with builtin protection (403), apply → validated recipe |
| `GET /api/jobs`, `GET /api/jobs/{id}`, `POST /api/jobs/{id}/cancel`, `GET /api/jobs/{id}/events` | the job model; `/api/runs…` unchanged and now persisted |
| `GET /api/corpus/{file}/coverage?run=&method=` | detection layers restricted to runs / a method |
| `GET /api/corpus/{file}/runs` | runs on a file with their algorithms, method, detections |
| `GET /api/channels/{id}/tags` | annotation tags, reviewed spans, reviewed %, vocabulary |
| `GET /api/channels/{id}/siblings`, `GET /api/cross/{id}?t0&t1&px` | real sibling channels; window + lag / r / classification per channel |
| `POST /api/annotations/seed` | "Take span for Review" → `annotations` verdict `seed` via `writes.write_human` |
| `GET /api/interrogation/families`, `…/{key}/members`, `…/slope`, `…/aggregate` | the 16 seed spans (marked `source: seed`), members + snippets, gradients + rose, distributions + timeline + β |
| `POST /api/windowsets`, `GET /api/windowsets` | Save window set → `windows.npz` + `manifest.json` in the registry's `window_set` shape, registered through `Working.registration` |

### Job model (`webui/server/jobs.py`)

`JobManager` grows `RunManager`: `jobs` table (additive), kinds `chain_run | sweep | import | regroup |
training`, `start_job(kind, fn, meta)` with `job.progress()` and cooperative cancel, SSE with full replay,
restart-safe snapshot from the row plus the `runs` row (a job the server lost mid-flight is reported failed
with `ServerRestart`, never "running" forever), ids that continue after persisted rows. Documented in
`BLOCK_INTEGRATION.md` §7. `tests/test_webui_jobs.py` (8 tests, conda pytest).

### Client functions switched demo → live

| module | switched | still demo |
|---|---|---|
| `api/explore.ts` | 4 of 6: `getCorpusLive` (was `getCorpusDemo`), `getSignalLive` (`getSignalDemo` kept as alias), `lookupChannel`, `getCrossChannel` | `getSpanEdit` (Prompt 05), `getShortcuts` (a static table) |
| `api/interrogation.ts` | 4 of 4: `getSourceBlock`, `getSourceChoices` (families + prior runs from the runs table), `getSlopeBlock`, `getAggregateBlock` | Review selections and Explore spans inside the picker are empty lists until Prompt 05 |
| `api/analyse.ts` | 0 of 5 (the demo chain machinery) | see "Left" |
| `api/training.ts` | 0 of 6 | see "Left" |

`api.ts` gained 20 functions (append only). The pages' components were not edited except the Corpus page's
one call site; the live reads keep the fixture shapes.

### Gate

- `npx tsc -b` and `npm run build`: clean.
- `pytest -n auto` (conda, final tree): **1177 passed, 3 skipped, 0 failed** (baseline after Prompt 00: 954 passed, the two Fig2A data-absent failures now pass because the channels were re-derived; +223 tests from this prompt). Two pins that counted 22 shipped adapters now say 33; three pins that encoded `input_kind=None` and 'detectors are free' were retargeted (commit messages say so).
- `webui/smoke.py --url http://127.0.0.1:8765` (sandbox; `PYTHONIOENCODING=utf-8`, see below): **{SMOKE}**
- Bridge tests under `webui/.venv` (`tests/test_webui_routes.py`, `test_webui_api.py`, `test_webui_runtime.py`,
  `test_webui_writes.py`): 54 passed.
- Project mode on the real recording: `webui/drive_templates.py --url http://127.0.0.1:8767 --recording 1 --span
  1209600 1216800` (M2_aug fs1 CH0, hours 336–338 — the reference span's first two hours). **All nine canonical
  templates completed and every row painted** (`webui/screenshots/wiring/01/summary.json`):

| template | s | detections | last step |
|---|---|---|---|
| drop_detection_v1 | 1.1 | 4 | 4 spans · mean 979 s |
| dehshibi_spikes | 1.2 | 0 | 0 spans (Algorithm 4 confirms nothing on this slice, as the monolith) |
| mp_threshold | 1.3 | 8 | 8 spans |
| mp_motifs | 6.4 | 15 | 5 groups × 3 |
| dsax_encoding | 1.2 | — | 360 symbols · alphabet 3 |
| symbol_search | 1.0 | 0 | 0 matches of `c+a+` at 20 s/symbol |
| windows_model | 5.2 | — | holdout accuracy 1.00 · 2 classes · 24 windows |
| cnn_detection | 11.3 | 1 | one span (every 600 s window scored > 0.5 by fusion_cnn.pth) |
| gramian_gasf (1 h) | 1.1 | — | 3600×3600 image |

The first CNN run failed with `UnicodeEncodeError` in the core's `load_model` print (`←`) on the server's
cp1252 console; two prints in `apply_cnn.py` are now ASCII. The same console encoding broke `smoke.py`'s own
progress printing on three checks; the smoke gate is run with `PYTHONIOENCODING=utf-8` and `start.ps1` should
set it (not done: `start.ps1` is shared with Prompt 02; request filed below).

## Critics

{CRITICS}

## Unfinished algorithms — propose, do not silently skip

| Algorithm | What it is | What is missing | Estimate | Recommendation |
|---|---|---|---|---|
| `Working/Detection/analysis/wavelet_analysis.py` (second wavelet detector: `compute_scalogram` → `detect_high_energy_regions` → `cluster_peaks[_poly]`) | Morse scalogram energy peaks clustered into events; presentation-oriented, untested | it shares the transform with the Dehshibi blocks, so it is one Scores → SpanSet block (`detection.energy_peaks`: peak picking + clustering over Ω(τ) or over the image's column energy) plus its polynomial clustering variant as a parameter; no tests exist for any of it, and `load_signal` reads `.mat` files directly | 4–6 h to the standard (block, tests on the Dehshibi synthetic, glyph) | finish — it is the natural third consumer of `preprocessing.wavelet_transform` |
| `comparison` stage | `Working/compare.py::compare_run_sets` (IoU matching of two runs' spans) and `StepDiff` | not a block: it takes two run ids, not a signal; the type system has no "two SpanSets" input. Discovery's compare page (Prompt 04) is its home as a route (`GET /api/compare?a=&b=`), not an adapter | 2 h as a route; a block would need a `SpanSet` side input bound to a prior run (`earlier_step` cannot reach another run) — 6 h with a new source kind | ignore for v1 as a block; route in Prompt 04 |
| FitzHugh–Nagumo | prose only (PRD): fit the FHN model to each event as a feature block `SpanSet → SpanSet + Features` | everything: the fit, the parameterisation, the null | 2–3 days | ignore for v1 |
| `spike_analysis.compute_spike_statistics` | a stub (duration/ISI statistics over spike locations) | the body is a comment; interrogation's aggregate route now computes depth / interval / slope distributions from the seed store, which covers the intent | 2 h to make it a `SpanSet → Features` helper the aggregate route calls | ignore for v1 |
| `Pipelines/motif_report`, `drop_motifs`, `dataset_build`, `fusion_prediction`, `cnn_scoring` | scripts | `cnn_scoring`'s per-window scoring is now `catalogue.cnn_score`; `fusion_prediction` (a second CNN head, `FusionPredictionCNN`) is a variant of it — a `model_kind` parameter, 2 h; the others are figure/report scripts, not blocks | 2 h | finish `fusion_prediction` as a parameter when a registered checkpoint needs it |
| Training 01–05 live, Analyse demo chain removal | see below | | | |

## Left (scaled down, and why)

- **Training 01–05 remain fixture-backed** (`api/training.ts`, six reads). The server side they need exists —
  `preprocessing.sliding_windows` with the P12 guards, the training chain, `POST /api/windowsets` — but the five
  pages are built on fixture shapes (dendrogram, contingency, stability, k-sweep) that no single run payload
  supplies; making them honest needs each page to attach to a `windows_model` job and draw the WindowSet /
  Grouping / Model payloads through `charts/`. Estimate 1–1.5 days. They still show the "demo data" chip.
- **The Analyse demo chain (`demo.*` blocks, `DEMO_TEMPLATES`, `?template=drop_motifs9&state=…`) was not
  removed.** The live chain page already imports the seeded templates and runs them (that is what the
  project-mode evidence used); the demo scenarios back 40 smoke states and the block-page concept pages
  (baseline / noise floor / encoding / drop detection frames). Replacing them with live block pages keyed on
  the new blocks' `meta` (event cards, removed breakdown, cutlines) is the same size as the Training item.
  Estimate 1.5 days. `?state=running|failed` therefore still come from the simulation, not a real run.
- **`Header` does not derive `demo` from the page's sourced reads**; each page passes `demo={read.source === 'demo'}`
  already, which is the same information with one line per page. Left as is.
- Explore's run/method filters are served (`coverage?run=&method=`, and the rail's run list is live) but the
  Corpus page still fetches the unfiltered map; the note beside the filters says so.
- `start.ps1`/`start.sh` should export `PYTHONIOENCODING=utf-8` (request `docs/prompts/wiring/requests/01-to-02.md`).

## Questions, with the default taken

| Question | Default taken |
|---|---|
| Should the drop template carry a separate "noise floor" block (spec §6.5) or is the floor the encoder's readout? | The encoder's readout (`derive`) and a parameter (`slope_sigma`) on both the encoder and the detector; the spec itself notes the floor is a control inside the encoder. A display-only identity block would carry no data downstream, since an Encoding carries no meta through the cache. |
| Drop-template defaults | The reference span's autoderived parameters (detrend 4916.67 s, segment 98.33 s); `autoparams.py` should become the blocks' `recommend` hook (2 h, not done). |
| Which detect5 flags does "the canonical detector" mean? | The block defaults are today's detect5 (both fixes on); the seed check runs with the drop_motifs5-era flags off, exposed as parameters. |
| Persisted artifacts for cluster / classifier | `artifacts(kind='csv')` for labels, `kind='model'` for the joblib; `execute_recipe` accepts `(kind, path)` from `persist`. |
| Where does "Save window set" register? | `registered_artifacts(kind='window_set')` through Prompt 02's registry (its documented shape), not a new table; `artifacts.kind` is a CHECK that cannot be widened additively. |
| Cross-channel window | the channel's first human span ± pad, else its first ten minutes; the page has no window control yet. |
| Seed-family "recovery" feature | measured on the stored snippet (trough back to within 10 % of the drop of the onset level); the store does not carry it. |

## How to start the app in project mode

    webui\.venv\Scripts\python.exe webui\run_server.py --project --port 8765
    # or: webui\start.ps1 -Project   (if start.ps1 gains the flag — request filed)

Prints `MODE = PROJECT`, writes `DATA/db/backups/<stamp>.sqlite`, opens the real database in WAL mode, seeds
the nine canonical templates once, and keeps step cache / results / models / saved window sets at their real
locations. Everything a chain run writes (runs, detections, jobs, artifacts) lands in the real database.

## Chat summary

{SUMMARY}
