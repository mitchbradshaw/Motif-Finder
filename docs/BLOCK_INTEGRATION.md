# BLOCK_INTEGRATION.md — how to add an algorithm to the web UI

One page for the researcher who has a new detector, encoder or feature extractor next year and
wants it runnable from Analyse, composable into templates, and drawn on every page — without
touching the UI. Written 2026-09-21 (stage 3, wiring prompt 01). Where this page and the code
disagree, `tests/test_block_standard.py` is the arbiter: it is this page made checkable.

## 1. What a block is

A block is one `AdapterSpec` (`Adapters/base.py`) registered from one file `Adapters/<stage>_<name>.py`.
The spec is the whole contract; the rest of the system (the executor, the bridge, the pages, the
SLURM export) reads it and never the wrapped function.

```python
SPEC = register(AdapterSpec(
    name="detection.summation_threshold",        # "<stage>.<short_name>"; stage ∈ Working.recipes.STAGES
    display_name="Summation threshold (Dehshibi stage 3)",
    stage="detection",
    category="detect",                           # insert-modal tab: preprocess·encode·detect·cluster·model·control
    page_name="Summation threshold",             # what the concept pages call it (defaults to display_name)
    params=[ParamSpec("epsilon_factor", float, 0.05, "…", min=0.0, max=1.0), …],
    run=_run,                                    # run(x, t, fs, **params[, value][, <side input names>]) -> AdapterResult
    input_kind="scores",                         # exactly one of the seven types — never None
    output_kind="spanset",                       # exactly one of the seven types
    side_inputs=[…],  estimate=…,  max_span_samples=…,  recommend=…,  derive=…,  persist=…,  known_broken=None,
    description="one paragraph a newcomer can act on",
))
```

**The seven interchange types** (`Working/types/`): `signal`, `scores`, `spanset`, `windowset`, `encoding`,
`grouping`, `model`. A block declares **exactly one `input_kind` and one `output_kind`**. The chain's root is
the recording's signal and is spelled `'signal'` — `input_kind=None` is refused at registration, so the type
system has one vocabulary and no "unset" state. (`detection.matrix_profile` and `preprocessing.window_matrix`
used to rely on the old `None` default; they now say `'signal'`.)

**`run(x, t, fs, **params, …)`** is always called with the chain's *current* signal `x` (after any upstream
`Signal → Signal` block), its absolute time axis `t` and the sample rate. A block whose `input_kind` is not
`signal` also receives the previous step's typed value as the keyword `value` (a `Scores`, an `Encoding`, …),
and every declared side input under its own name. It returns `AdapterResult(output_kind, value=<typed object>,
meta={...})`. `value` is the only payload; anything else a plot or a page wants goes in `meta` (the SAX blocks
put their cutlines there, the matrix profile its raw `mp`, the drop detector its counts and diagnostics).

**Parameters** are `ParamSpec`s: typed (`int | float | str | bool`), bounded (`min`/`max`/`choices`), with a
default. Defaults are filled by `validate_params` *before* hashing, so the recipe hash — and therefore the
step cache and run history — is the same whether the researcher typed the default or not. A parameter is a
tunable input; a read-only readout beside the controls is a `derive` row, never a parameter.

**Optional hooks**, all read off the spec:

| Hook | Signature | When to declare it |
|---|---|---|
| `side_inputs` | `[SideInputSpec(name, type_kind, sources)]` | the block needs a second typed input: an earlier step, the root signal or a library exemplar (`detection.seed_matches` binds an exemplar; `catalogue.classifier` binds the window set) |
| `estimate` | `(x, t, fs, **params) -> float \| None` | see §3 Cost |
| `max_span_samples` | `int` | the block is O(n²) or worse (the Gramian images) — the executor refuses a longer span before allocating |
| `recommend` | `(x, t, fs) -> {param: value}` | a default depends on the span (seconds per symbol) |
| `derive` | `(x, t, fs, params, **typed_inputs) -> [(label, value, severity)]` | a read-only readout for the span in hand ("Symbols produced: 256"), served by `POST /api/blocks/derive`; the block page does not draw it yet (the page's own `rowState.deriveRows` reads the payload instead) — declare it for the route and for the Panel-era CLI, not for a control you can see today. A block whose readout needs an upstream typed value receives none from the route and says so in its own rows |
| `persist` | `(conn, run_id, config_hash, recording, span_start, span_end, params, result) -> path \| (kind, path) \| None` | the output must land on disk and be registered as an `artifacts` row even from a headless run (matrix profile, window matrix, cluster labels, the classifier's joblib). Return `(kind, path)` to name the `artifacts.kind`; a bare path means `'encoding'` |
| `known_broken` | `str` | the block is registered but cannot run here; the reason is shown on its card and beside it in the insert modal (it can still be inserted — the run then fails loudly at that step) |

**Index conventions — the trap a new block falls into.** `x` is the *span* the chain ran over, index 0 =
the span's first sample; `t` is its absolute time axis (`t[0] * fs` is the span's channel offset). The
types differ on purpose:

| Type | `starts` / index 0 means | who shifts |
|---|---|---|
| `Signal`, `Scores` | sample `i` of the value is channel sample `span_start + i` | the bridge, when drawing |
| `SpanSet` | **span-relative** (`x[start:end]` is the span); so are the `*_idx` columns of its `features` table | the executor adds `span_start` when it writes `detections`; the bridge adds it when drawing |
| `WindowSet` | **channel-absolute** (`starts` index the whole channel); producers add `t[0] * fs`, consumers that slice `x` subtract it | nobody else |
| `Encoding`, `Grouping`, `Model` | no time of their own; a symbolic Encoding's segment `k` covers `x[k*sps:(k+1)*sps]` with `sps = len(x) // n_symbols` | — |

`preprocessing.sliding_windows` and `preprocessing.window_matrix` both emit absolute starts;
`catalogue.window_images` and `catalogue.cnn_score` subtract `t[0] * fs` before slicing `x`. A block that
mixes the two conventions draws every window in the wrong place and raises nothing.

**A SpanSet can carry measures** (fixup-d): `SpanSet.features` is an optional DataFrame, one row per span,
mirroring `WindowSet.features` (parquet beside the JSON, compared by `__eq__`). A **feature block** is
`SpanSet → SpanSet`: it passes the spans through and adds columns (`interrogation.event_shape`,
`interrogation.intervals`), keeping any columns it was given. The executor writes a SpanSet to
`detections` only when the block that produced it did not take a SpanSet in — a feature block measures
the detector's events, it does not detect them again, so a detector's spans are written once however
many feature blocks follow. A block that had to *define* a measure prints the rule in `meta["rules"]`
(`[{name, rule}]`), which the page shows beside the numbers.

**Rules that are not negotiable** (from `CLAUDE.md`): a block imports no UI library and never learns a
browser exists; bulk arrays never enter the database (persist writes a file and registers its path); a
`SpanSet` a block emits is written to `detections` by the executor — machine-only; no block writes
`annotations`.

## 2. What the UI needs from it

Nothing beyond the spec, because the pages are keyed on the **output type**, not on the algorithm. The
bridge serialises every typed value through one seam (`webui/server/serialize.py::to_payload`) and the
client draws every payload through one seam (`webui/client/src/analyse/Renderer.tsx::renderByType`):

| Output type | Server payload (`serialize.py`) | Client renderer (`Renderer.tsx`) |
|---|---|---|
| `Signal` | peak-preserving envelope sized to the viewport, y-range, summary | curve, upstream signal ghosted behind, mV axis |
| `Scores` | envelope, value range, NaN tail, top-k low/high, 40-bin histogram, `m` if known | series with motif/discord marks |
| `SpanSet` | absolute seconds per span (capped at 5000), labels, scores; `features` (columns, capped matrix, column ranges) and, from meta, `rules` / `rose` / `interval_stats` | tinted bands over the ghosted signal; with features, the block page adds the per-event table, the rose, the interval statistics and the rules (`analyse/EventFeatures.tsx`) |
| `WindowSet` | starts, length, capped feature matrix + column ranges | window ticks + feature heatmap |
| `Encoding` symbolic | symbols, letters, samples per symbol, cutlines, PAA | symbol strip (3-letter = amber/grey/blue) |
| `Encoding` image | block-averaged uint8 image (≤ 256 px a side), value range; a 4-D stack ships a contact sheet of its first 16 images plus `n_images` | canvas, viridis |
| `Grouping` | labels, cluster sizes, a time strip when the upstream WindowSet is at hand | class-per-window strip |
| `Model` | a card (accuracy, classes, windows, features) — never the joblib | text card |

So **a block gets its chain-row thumbnail, its block-page output and its summary line for free** from its
output type. It needs its own drawing only for a detail the type renderer cannot draw (the drop detector's
per-event anatomy, the noise floor's histogram). That drawing is a **payload**: JSON the block puts in
`meta` and a small client component draws — **never a matplotlib figure sent to the browser**. `plot` on
the spec exists for figure *export* (matplotlib is the one drawing library the core keeps); the bridge does
not call it.

**The glyph** — the static thumbnail of *the algorithm* on every card — lives in the client registry
`webui/client/src/analyse/glyphs.tsx`, `BY_NAME`, keyed by the adapter name. A block without an entry gets
the type-signature glyph (`BY_SIG`, e.g. `scores→spanset`) so it is never blank, and the glyphs page marks
it "signature" until you draw one. Colour key: grey input/context · blue what the block emits · green
found/kept · amber cut/threshold · red discord/excluded · purple exemplar/second input; 44 × 26 box.

**Names on the card** (`page_name`), **the insert-modal tab** (`category`) and **the broken flag**
(`known_broken`) are on the spec. The bridge (`webui/server/chain.py`) keeps no side table; an unknown
category is a `ValueError` at import.

## 3. Cost

Every block that is not O(n)-cheap declares how long it will take, so the chain page can show an estimate
and route a long stage to the cluster instead of a spinner:

- **`estimate(x, t, fs, **params)`** returns seconds for *this* span, or `None` meaning "not calibrated on
  this machine" — never a guessed constant. Calibration is per machine and lives in a JSON file under
  `DATA/db/`: `Working/Detection/matrix_profiling/cost.py` (O(n²), per backend) and
  `Working/Preprocessing/window_matrix/cost.py` (per window, per measure) for the two big ones;
  **`Working/block_cost.py`** for everything else — declare `register_cost_model(name, exponent, run_once)`
  next to the spec and `estimate` becomes one line (`detection_dehshibi_spikes`, `preprocessing_wavelet_transform`,
  `detection_wavelet_scattering`, `detection_rupture`, `catalogue.window_images`, `catalogue.cnn_score` do this). Run
  `python -c "from Working.block_cost import calibrate; calibrate()"` once to time them.
- A block whose cost is not a function of the span (a linkage tree costs O(w² log w) in *windows*, a forest
  fit in windows × features) declares `estimate` returning `None` with that rationale
  (`catalogue.cluster`, `catalogue.classifier`). The bridge's `POST /api/chain/validate` then reports that
  step as `null` in `estimate.per_step_s`, lists it in `estimate.unknown` and sets `estimate.route =
  "unknown"` — never 0.0 (the chain page names the uncalibrated stages beside the estimate). A block with
  no `estimate` at all is free.
- **`max_span_samples`** refuses a span above a ceiling before any allocation (the four Gramian images at
  5 000). The executor checks it; the bridge reports the offending stage as `over_ceiling`.
- The interactive ceiling comes from Settings › Compute (`LOCAL_LIMITS`); a stage over it gets *Create
  SLURM script* on the chain page (P4). `tests/test_block_standard.py::COSTED` names the blocks that must
  declare a cost; add yours there.

## 4. Templates

A **template is a named, versioned chain** — a row of `templates` (`name`, `steps_json`, `kind`, `version`,
`builtin`, `description`, timestamps; `Working/database/schema.py::_migrate_templates_columns`). Its `kind`
is a consequence of the chain's terminal type (spec §6.1): `spanset | scores | signal` → **detection**,
`encoding` → **encoding**, `windowset | grouping | model` → **training**; **interrogation** is a chain whose
terminal block is in stage `interrogation` — the feature chains (`SpanSet → SpanSet` + features). Since
fixup-d two ship: `drop_event_features` (the drop detector → Event shape → Intervals) and
`spike_event_features` (Invert → the drop detector → Event shape told the chain inverted → Intervals).

The canonical templates **ship as code** in `webui/server/templates.py::CANONICAL` and are **seeded into
the table on the first `--project` (or sandbox) start** by `seed_canonical`, by name, never overwriting.
A builtin row is copied, not edited; a saved copy is editable and its `version` increments on every edit.
Apply a template with `Working/templates.py::apply_template` — it builds an ordinary recipe, so a template
run is hashed, cached and recorded exactly like a hand-built chain.

**A multi-stage detector is a template, not a block** (stage-3 decision 2). The Dehshibi detector is
`preprocessing.wavelet_transform → detection.wavelet_summation → detection.summation_threshold`; the drop
detector is `preprocessing.detrend → detection.stage_encoding → detection.drop_detection`. Each stage is a
typed block the researcher can inspect, swap and sweep. The monolithic `detection.dehshibi_spikes` stays
registered (deprecated, tab *control*) so an old recipe still runs.

## 5. Checklist

1. **Write `Adapters/<stage>_<name>.py`.** Wrap the core function; declare types, params, category,
   page_name, cost. Put everything a page might want in `meta`. No UI imports.
2. **Register it** — the file self-registers on import; `discover_adapters()` finds it.
3. **Unit-test the adapter** in `tests/test_adapter_<name>.py`: types and category, defaults and
   `validate_params` bounds, one run on a synthetic signal (30 s is enough), the error message when the
   typed input is missing. If the output is a **new shape** within its type (see §5's closing note), add a
   `to_payload` case to `tests/test_webui_serialize.py` too — the serializer is the seam the page trusts. If it belongs to a template, add the template to `CANONICAL` and a test that runs
   the template end to end through `execute_recipe` (`tests/test_template_<name>.py`).
4. **Add its glyph** to `BY_NAME` in `webui/client/src/analyse/glyphs.tsx`.
5. **Add a smoke state** for its block page to `webui/smoke_pages/analyse.json` (open the block page with
   the template that contains it; expect the params panel and a painted output).
6. **Run the gate**: `pytest -n auto` (zero new failures; `tests/test_block_standard.py` now includes your
   block), `npx tsc -b` + `npm run build` in `webui/client`, `webui/smoke.py` against a running bridge.

Nothing else changes anywhere — no route, no page, no serializer, no renderer — **for a block whose output
has a shape the type already ships**: a Signal, a Scores, a SpanSet, a symbolic Encoding, a 2-D or 3-D image,
a WindowSet, a Grouping, a Model. A new *shape* inside a type (the first 4-D image stack needed a contact-sheet
branch in `serialize.py::_encoding`) needs one serializer branch, and the renderer only if the payload shape
is new too. If the output fits none of the seven types at all, it needs a row in spec §6.8 before the block
is built.

## 6. Worked example — the Dehshibi summation stage

`Adapters/detection_wavelet_summation.py`, the whole file minus its docstring:

```python
import numpy as np
from Adapters.base import AdapterResult, AdapterSpec
from Adapters.registry import register
from Working.types import Scores

def _run(x, t, fs, value=None):
    if value is None:
        raise ValueError("detection.wavelet_summation requires an Encoding input from a prior step (input_kind='encoding').")
    if getattr(value, "kind", None) != "image":
        raise ValueError(f"… sums a scales × time image; got an Encoding of kind {value.kind!r}. Put Wavelet transform before it.")
    g = np.asarray(value.values, dtype=float)
    if g.ndim != 2 or g.shape[1] != len(x):
        raise ValueError(f"… expects an image with one column per sample (shape (scales, {len(x)})); got {g.shape}.")
    omega = g.sum(axis=0)                       # NaN columns (a skipped chunk) stay NaN
    return AdapterResult(output_kind="scores", value=Scores(values=omega, fs=float(fs)),
                         meta={"n_scales": int(g.shape[0]), "n_nan": int(np.isnan(omega).sum())})

SPEC = register(AdapterSpec(
    name="detection.wavelet_summation", display_name="Wavelet summation Ω(τ) (Dehshibi stage 2)",
    stage="detection", category="detect", page_name="Wavelet summation",
    params=[], run=_run, input_kind="encoding", output_kind="scores",
    description="Ω(τ) = Σ_s g(τ, s): collapses the normalised Morse coefficients to one value per sample.",
))
```

What it *did not* need: an estimate (a column sum is O(n)), a glyph of its own to be usable (it drew with
the `encoding→scores` signature glyph until one was added), any change to the bridge or a page. Its test
(`tests/test_adapter_wavelet_summation.py`) checks the types, the sum, NaN propagation and the two error
messages. The template that uses it (`dehshibi_spikes`) is tested end to end in
`tests/test_template_dehshibi.py`, where it reproduces the monolithic `detect_spikes` span for span.

## 7. Long work — the job model

Anything longer than a page should wait for runs through **`webui/server/jobs.py`**: a persisted `jobs`
table (kinds `chain_run | sweep | import | regroup | training`), one worker thread per job, progress as
Server-Sent Events on `GET /api/jobs/{id}/events` (replayed for late subscribers), cooperative cancel on
`POST /api/jobs/{id}/cancel`, and a restart-safe snapshot: a job the server no longer holds in memory is
rebuilt from its `jobs` row and, for a chain run, the `runs` row the core wrote. The Analyse run routes
(`/api/runs…`) are thin wrappers over a `chain_run` job. Prompts 02–05 create their own kinds through
`JobManager.start(kind, fn, meta)`; see the module docstring for the API.

## 8. Reusing versus adding

Before adding a block, grep the registry. Reuse when the *semantics* match, not just the types:
`detection.threshold` cuts any Scores at an absolute value and any Scores-producing block may feed it;
`detection.summation_threshold` was added because Algorithms 1–4 need extrema pairs at a relative prominence
and the raw signal — same signature, different meaning. Write the "why not reuse" sentence in the new
block's docstring.
