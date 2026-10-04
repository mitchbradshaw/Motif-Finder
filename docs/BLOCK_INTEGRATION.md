# BLOCK_INTEGRATION.md — how to add an algorithm to the web UI

One page for the researcher who has a new detector, encoder or feature extractor next year and
wants it runnable from Analyse, composable into templates, and drawn on every page — without
touching the UI. Written 2026-09-21 (stage 3, wiring prompt 01). Where this page and the code
disagree, `tests/test_block_standard.py` is the arbiter: it is this page made checkable — the contract in
§1 and, since fixup-h, the drawing standard in §2.

## 1. What a block is

A block is one `AdapterSpec` (`Adapters/base.py`) registered from one file `Adapters/<stage>_<name>.py`.
The spec is the whole contract; the rest of the system (the executor, the bridge, the pages, the
SLURM export) reads it and never the wrapped function.

```python
SPEC = register(AdapterSpec(
    name="detection.summation_threshold",        # "<stage>.<short_name>"; stage ∈ Working.recipes.STAGES
    display_name="Summation threshold: regions, envelope, merge (Dehshibi stage 3)",
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
| `run(..., conn, recording)` | keywords on `run` itself | the block **reads the live store** (fixup-aa: `catalogue.manual_labels` reads the human verdicts). The executor hands it the run's connection and the recording row; because its output then depends on the store and not only on the recipe, **that step and every later one bypass the step cache, and a completed run of the same recipe is never reused** (`Working/execution.py::_first_store_reading_step`). It may only select — rule 5 |
| `persist(..., recipe_prefix)` | keyword on `persist` | the file `persist` names should be keyed on the recipe **through this step**, not on the whole chain (fixup-aa: the window matrix's `…_span<a>-<b>_<key>.npz`, so a run, its surrogate and a second span keep their own file) |

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

## 2. What the UI needs from it — the drawing standard

Nothing beyond the spec, because **a block's picture is a consequence of its type signature** (fixup-h,
`QUESTIONS.md` Round 7):

> **The OUTPUT type decides what kind of picture you get. The INPUT type decides what one "thing" is in
> that picture, and whether there is a before/after to show.**

So there are **seven type views**, keyed on the output type, and **twelve modifiers**, keyed on the
conversion `input->output`. The table lives in `webui/server/views.py`, rides on every catalog card
(`view`, `modifier`), and the client holds one component per key in
`webui/client/src/analyse/views/registry.tsx`. The bridge serialises every typed value through one seam
(`webui/server/serialize.py::to_payload`); the client draws every payload through one seam
(`analyse/Renderer.tsx::renderByType` → `VIEWS`). **No view is ever selected by a block's name.**

**Two tiers, one component.** Each view is drawn twice by the same component, with `ctx.interactive` as the
whole difference: the **chain thumbnail** (about 90 px, no interaction — *did this step do roughly what I
expected*) and the **block settings page** (full width, tall, hover / click / drag — *why did it decide
that*: the shape plus the evidence).

| Output | settings page, minimum | thumbnail | payload fields it draws |
|---|---|---|---|
| `Signal` | **before and after overlaid**, the input grey beneath; one axis when the block leaves the scale alone, **both axes (original left, new right)** when a shared axis would flatten either trace below 35 % of the plot | the overlaid plot | `envelope` (min/max, or every sample), `y_range`, `unit` |
| `Scores` | the curve, **the scored signal above it on the same x**, the value histogram, the next stage's cut if it has one | the curve alone | `envelope`, `value_range`, `histogram`, `top`, `m` |
| `SpanSet` | every span on the full trace (clickable), **the slideshow**, a duration distribution | every span on the full trace; a density ribbon when spans outnumber pixels | `start_s` / `end_s`, `scores`, `labels`, `marks`, `window_counts` |
| `Encoding` | **3 sampled images**, a scan through the rest, a colour bar with the real value range, no-data grey | 3 images side by side, each marked on the row's time axis | image: `frames`; symbolic: `symbols`, `paa`, `cutlines` |
| `WindowSet` | the windows on the time axis and the feature matrix **as a heatmap** | the heatmap on the source signal's time axis, grey where no window | `starts_s`, `features`, `split` |
| `Grouping` | clusters over time, cluster sizes, **one exemplar drawn per cluster** | when each cluster is active, as a heatmap | `labels`, `strip`, `clusters`, `exemplars` |
| `Model` | **accuracy per class** as bars | a card | `card.per_class_accuracy`, `card.holdout_class_counts` |

| Modifier | blocks | what the settings page adds |
|---|---|---|
| `signal->signal` | 6 | the before/after overlay; dual axes when the scale changes |
| `signal->scores` | 1 | the source signal above the curve; a windowed score's window `m` drawn to scale on it |
| `encoding->scores` | 2 | the image above, the curve below, same x, **the summed band marked on the image** |
| `scores->spanset` | 3 | **the cut drawn on the upstream score curve, draggable** |
| `encoding->spanset` | 2 | which cells / symbols fired, outlined on the encoding itself |
| `signal->spanset` | 4 | spans on the trace — no intermediate exists to show |
| `spanset->spanset` | 2 | **the features, not the spans**: a histogram per measure, the rose, the table folded away |
| `signal->encoding` | 11 | 3 sampled images and which chunk of signal each came from |
| `windowset->encoding` | 1 | 3 sampled images and which window each is |
| `signal->windowset` | 2 | a feature matrix draws the heatmap; a set with no features draws its windows by train / validation / test |
| `windowset->grouping` | 1 | clusters over time and one exemplar per cluster |
| `grouping->model` | 1 | accuracy per class |

**A new block with an existing conversion needs nothing.** A block whose conversion is new still draws —
its output type's view, with no modifier — and `tests/test_block_standard.py` fails until a row is added to
`views.py` and `registry.tsx`: one line each, on purpose, because what the input contributes to the picture
is a decision and not a default.

**Conventions a view reads off a block** (payload-driven, never name-driven — follow them and the view
lights up; ignore them and the block still draws):

| If the block … | … the view … |
|---|---|
| is `scores->spanset` and has a `float` parameter named **`threshold`** (an absolute level in the scores' units) | draws the cut on the upstream curve and makes it draggable |
| is `encoding->scores` and has **`row_from` / `row_to`** (fractions of the image height) | marks the summed band on the upstream image |
| emits a SpanSet and puts **`meta["events"]`** = one dict per span with `onset_idx` / `trough_idx` (span-relative) | marks each fall inside its window and counts **falls** per window |
| is a feature block whose table carries **`onset_idx` / `extremum_idx`** | the same, from the table |
| emits an image with **one column per sample of the span** | frames are chunks of columns at the image's own resolution, each located in time |
| emits a WindowSet whose table has a **`split`** column | ships it apart from the features and colours the windows by role |
| prints its rules in **`meta["rules"]`** (`[{name, rule}]`) | puts each rule behind the info icon of its measure |
| is `signal->signal`, passes **one layer of a decomposition** on, and puts **`meta["layers"]`** = one dict per layer (`name`, `level`, `low_hz` / `high_hz`, `label`, `chosen`, and an `envelope` of span-relative sample indices `i` with values `v`, at most 4096 points) beside `meta["wavelet"]` / `meta["levels"]` | draws every layer stacked under the before/after plot on the same time axis, the input first, each on its own y with a scale bar, the chosen one highlighted with its Hz range (fixup-ac, `preprocessing.wavelet_bands`). The envelope is the block's, small enough to survive the bridge's meta sidecar on a step-cache hit |

**The drawing rules** (the ones of `Pipelines/drop_motifs/drawing_rules.py` that carry over; the thesis
figure rules are for thesis figures):

1. **Never interpolate.** A drawn curve implying samples the recording does not have is a fabrication.
   Nothing is resampled on a settings page.
2. **Decimate by min/max envelope, and say so.** Each pixel column carries the true minimum and maximum of
   its samples (`decimate.envelope`); the view prints which it drew (*"7,200 samples · 1 Hz · every sample
   drawn"*) and **dots the vertices when samples are 3 px or more apart**. Never a stride: a stride deletes
   a narrow event.
3. **A drop must look like a drop** — rule 9. A drawn trace varies, is not flattened, and is not clipped by
   its axis. Mark the plot `data-rule9` and its trace `[data-trace]`; `webui/smoke.py` measures it.
4. **Small multiples: per-panel measured domain and an explicit scale bar**, never a shared y
   (`SmallMultiples domain="per-panel"`, `charts/ScaleBar.tsx`). Clustering is scale-invariant, so a shared
   axis draws most of a family as flat lines.
5. **Colour graded by time only where order is the subject.**
6. **Select by SAMPLE RANGE, never by a window index** (`DETECTION_AND_FIGURES.md` §5b). Overlapping
   windows are shared context, not double-counting: never deduplicate them visually.
7. **No-data is grey**, never the bottom of a colour ramp, and a colour bar carries the real value range.

**The text budget.** One short line on the face, the full definition behind an info icon — **but an
absence is never hidden.** *"half-width · FWHM"* on the face; the rule on hover; and *"17 of 17 events have
no recovery"* **stays on the face of the card**, because that is the result, not commentary.

**The slideshow** (`kit/Slideshow.tsx::EventSlideshow`, on `SmallMultiples`) is what any SpanSet-emitting
block gets: one card per span, sorted by score / time / duration, paged at ten or sampled with a seeded
shuffle, selection shared with the plot above, a window holding more than one event drawn **red with
`[2 falls]`**, an extent set by the detector's cap drawn with a **dashed edge**. It is **read-only**; its
one action is *send to Review*.

So **a block gets its chain-row thumbnail, its block-page view and its summary line for free** from its
type signature. It needs its own drawing only for a detail no view draws (the Dehshibi funnel). That drawing
is a **payload**: JSON the block puts in `meta` and a small client component draws — **never a matplotlib
figure sent to the browser**. `plot` on the spec exists for figure *export* (matplotlib is the one drawing
library the core keeps); the bridge does not call it. **How reports and exports are drawn inherits this
standard** rather than inventing a second one.

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
5. **Add a smoke state** for its block page to `webui/smoke_pages/zz_analyse_run.json` (run the template that
   contains it, open the block page; expect `[data-testid="block-view"]` with its `data-view` / `data-modifier`,
   the evidence its modifier adds, and set `"rule9": true` so the gate measures what was drawn).
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
from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.types import Scores

def band_rows(n_rows, row_from, row_to):
    return int(round(row_from * n_rows)), int(round(row_to * n_rows))

def _run(x, t, fs, row_from=0.0, row_to=1.0, value=None):
    if value is None:
        raise ValueError("detection.wavelet_summation requires an Encoding input from a prior step (input_kind='encoding').")
    if getattr(value, "kind", None) != "image":
        raise ValueError(f"… sums a rows × time image; got an Encoding of kind {value.kind!r}. Put Wavelet transform before it.")
    g = np.asarray(value.values)
    if g.ndim != 2 or g.shape[1] != len(x):
        raise ValueError(f"… expects an image with one column per sample (shape (rows, {len(x)})); got {g.shape}.")
    lo, hi = band_rows(g.shape[0], row_from, row_to)
    if hi <= lo:
        raise ValueError(f"… the band row_from={row_from:g} … row_to={row_to:g} holds no row of a {g.shape[0]}-row image.")
    omega = g[lo:hi].astype(float).sum(axis=0)  # NaN columns stay NaN
    return AdapterResult(output_kind="scores", value=Scores(values=omega, fs=float(fs)),
                         meta={"n_rows": int(g.shape[0]), "rows_used": [lo, hi], "n_nan": int(np.isnan(omega).sum())})

SPEC = register(AdapterSpec(
    name="detection.wavelet_summation", display_name="Wavelet summation Ω(τ) (Dehshibi stage 2)",
    stage="detection", category="detect", page_name="Wavelet summation",
    params=[ParamSpec("row_from", float, 0.0, "…", min=0.0, max=1.0), ParamSpec("row_to", float, 1.0, "…", min=0.0, max=1.0)],
    run=_run, input_kind="encoding", output_kind="scores",
    description="Ω(τ): sums a band of rows of a time-aligned image to one value per sample.",
))
```

What it *did not* need: an estimate (a column sum is O(n)), a glyph of its own to be usable (it drew with
the `encoding→scores` signature glyph until one was added), any change to the bridge or a page. Its test
(`tests/test_adapter_wavelet_summation.py`) checks the types, the sum, the band, NaN propagation and the
error messages. The template that uses it (`dehshibi_spikes`) is tested end to end in
`tests/test_template_dehshibi.py`, where it reproduces, span for span, what the authors' own MATLAB returned
on the same recording (`tests/fixtures/dehshibi/reference.json`; fixup-J).

**Two contracts this template taught** (fixup-J), which make its middle block replaceable:

- **A time-aligned image**: an `Encoding` of kind `image` with **one column per sample of the span and rows
  ordered low to high**. `preprocessing.wavelet_transform` emits one; `detection.wavelet_summation` accepts
  any. An `Encoding` carries no axis and a block does not see the previous block's `meta`, so a block that
  selects rows does it by **fraction of the image height**, and the block that made the image prints the
  fraction that matters in its own readout. (`detection.freq_stft` is *not* time-aligned — one column per
  hop — and cannot feed the summation as it stands.)
- **A block that consumes a `Scores` asks nothing about how it was made.** `detection.summation_threshold`
  needs one value per sample and the signal (`x`, which every block gets); it windows the score itself.
  Any `Encoding → Scores` block, or any `Signal → Scores` block replacing the first two stages, drops in
  front of it unchanged. If two blocks in a chain must agree on something (a window, a chunking), make
  each compute it from its own inputs — never a parameter the researcher has to keep equal in two places.

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
`detection.summation_threshold` was added because the Dehshibi regions need extrema pairs at a relative prominence
and the raw signal — same signature, different meaning. Write the "why not reuse" sentence in the new
block's docstring.
