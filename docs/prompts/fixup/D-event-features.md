# Fixup D — per-event features as analysis blocks

**The researcher's top-priority capability** (`QUESTIONS.md` Q-0.5): statistical measures of motif
trains and individual motif events. Wanted by both the researcher and the supervisor, which by Q-0.4
makes it the path that must be the most reliable in the app.

**Blocked on prompt `B` landing** — every amplitude-shaped measure here is 1000x wrong until the
volts-labelled-mV error is fixed, and this prompt *writes those numbers into a table*, so running it
first would persist the error rather than display it.

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md`, **`docs/BLOCK_INTEGRATION.md` in full**
(this prompt adds blocks and that document is the contract, enforced by
`tests/test_block_standard.py`), `docs/prompts/fixup/QUESTIONS.md` rounds 1–2, and
`docs/prompts/fixup/reports/B-units-and-amplitude.md`.

Commit prefix `fixup-d:`. Test-first; first commit touches only `tests/` and must fail.

## Vocabulary — get this right, it was corrected on purpose

- **A "spike train" is a MOTIF TRAIN.** The researcher and supervisor used "spike train" and "spike
  events" to mean *sequences of motifs of either polarity*. **Never write "spike train" in this work.**
- **Drops and spikes are different events, not one phenomenon under two names.** `drop_motifs` detects
  drops only (`signal_sign = 1` on all 3,511 rows of `drop_motifs10`).
- **Feature blocks are polarity-neutral.** Drop depth / rise height / recovery and spike amplitude /
  spike height / return time are the same measurements about opposite signs. **One block, polarity
  handled internally** — name the outputs neutrally (`event_depth`, not `drop_depth`).

## What already exists — reuse it, do not rebuild it

`CLAUDE.md`: *prefer importing an existing helper to writing a second one*. `BLOCK_INTEGRATION.md` §8
goes further — **write the "why not reuse" sentence in the new block's docstring**. Surveyed
2026-09-23; every line verified.

### The rose plot is already built, in the core, tested, and live

**`Working/Detection/drop_motifs/gradients.py`** (441 lines) is UI-free core (`:68` — *"No plotting
library - CLAUDE.md rule 1"*) and the live bridge already calls it at
`webui/server/interrogation_routes.py:108-109`. **This is the module the researcher remembers. Use it.**

- `slope_angle(slope, reference)` `:180` → `arctan(slope / reference)`, radians in `(-pi/2, 0]`.
  **`reference` is mandatory with no default**, and the module docstring `:22-45` is a sustained
  argument that `arctan(slope)` with an unstated reference is an artefact. Respect that.
- `reference_slope()` `:212`, four modes `SLOPE_SCALES = ("raw","recording","pooled","event")` `:75`.
- `rose_histogram()` `:359` — 18 bins over `[-pi/2, 0]`, angles **clipped not dropped**.
- `rose_data()` `:378` — pooled rose **plus** a per-group breakdown, `split_by="span_key"`.
- Circular statistics, all present and tested: `circular_mean` `:294` (arctan2 of mean sin/cos, not the
  arithmetic mean), `resultant_length` `:310`, `circular_sd_deg` `:325`, and `uniformity_p` `:338` —
  a **one-sample KS against uniform over `[lo, hi]`, deliberately not Rayleigh**, because a Rayleigh
  test is significant by construction when angles can only occupy one quadrant. Do not "improve" this.
- `scale_caption()` `:263` emits the mandatory "45° = …" line so the figure cannot drift from the
  reference actually used. Carry it into the payload.
- Tests: `tests/test_drop_motifs_gradients.py` — read before re-deriving anything.

**`GRADIENT_FIELDS` `:81` = `("max_slope_mv_s","onset_slope_mv_s","mean_slope_mv_s","peakedness")`.**

**Do NOT base anything on `Pipelines/drop_motifs/store11.py` / `figures11_s2.py`.** They are a second,
parallel implementation of the same angle (`store11.py:159` negates explicitly where `gradients.py`
relies on the stored slope already being negative). Report-figure code. One rose rule in the tree.

**One thing to lift from `store11.py` and nothing else** — `MAX_SLOPE_UNIT_NOTE` `:60`:

> `max_slope_raw` is V/s (`detect5.py:596` already multiplies the gradient by fs); mV/s =
> `max_slope_raw * 1000`, with no second fs factor.

That is a unit trap with a foot in prompt `B`'s territory. Get it wrong and every slope is off by `fs`.

### Measures that already exist per event

| Measure | Where | Note |
|---|---|---|
| depth | `detect5.py:759`, stored `:833` `× 1000.0` | `x[onset] - x[trough]` |
| rise height | `detect5.py:762-763`, stored `:834` | **0.0 unless `trigger == TRIGGER_RISE`** — and it is `0.000` for **85.8 %** of `drop_motifs10`. Do not build on it without saying so |
| peak-to-peak | `detect5.py:814`, stored `:836` | `np.ptp` over the bracketed window; denominator of `fall_dominance` |
| fall duration | `detect5.py:835` | `(trough - onset) / fs` — **onset→trough, NOT onset→recovery** |
| onset / trough index | `detect5.py:740,724`, stored `:826-827` | |
| max slope, onset slope | `detect5.py:831-832` | `max_slope_raw` = **min of `np.gradient(x)*fs` over `[onset, trough]`**, i.e. most negative sample |
| chord / mean slope, peakedness | `gradients.py:119,129` | |
| inter-event interval | `store11.py:276`, `clusterk1.py:184`, `interrogation_routes.py:145` | **three implementations — consolidate onto one** |

### Measures that do NOT exist and are yours to write

- **Recovery time.** Nothing measures the return leg anywhere. `fall_duration_s` stops at the trough,
  which is found by a knee rule (`detect5.py:724`, `trough_knee_frac=0.05`). The only `recovery_s` in
  the repo is a **UI mock fixture** (`webui/pages/inventory/interrogation-training.md:259`) whose
  neighbouring values are explicitly scaled for the prototype. **Do not take the fixture as a
  definition.** Define recovery explicitly, in the block's docstring, and print the rule in the payload
  the way `interrogation_routes.py:118-123` already prints its `rules` list.
- **Event width, polarity-neutral.** Numerically `fall_duration_s` for a drop; nothing does the
  general case.
- **Half-width.** The survey reported this missing; **it is not.** `Working/Detection/analysis/
  data_analysis.py:194` `half_width(w)` exists — but read it before reusing: it uses
  `scipy.signal.find_peaks` + `peak_widths(rel_height=0.5)` on the **most prominent peak**, and returns
  `min(left_hw, right_hw)` **in samples** — the narrower half, not the full width at half maximum, and
  peak-oriented so a drop needs inverting. It is a *related* measure, not the electrophysiological
  FWHM the researcher asked for. Either generalise it honestly or write FWHM beside it and say in the
  docstring why the existing one did not serve.

## The architecture decision, taken — and why it is not a spec violation

**There is no `Features` type and there must not be one.** `Working/types/__init__.py:5-6` states:
*"No eighth type is added; a method that fits none of these seven is out of scope."* `Adapters/base.py:25`
derives `TYPE_KINDS` from that `__all__`, so the vocabularies cannot drift.

**`SpanSet` is too thin for this work.** `Working/types/spanset.py:34-38` carries `starts`, `ends`,
one `label: str` per span and one `score: float` per span. Today `detection.drop_detection` works
around that by **packing anatomy into the label string**
(`Adapters/detection_drop_detection.py:84`: `f"onset={...};trough={...};{morphology}"`). That is the
pattern this prompt must not extend.

**`WindowSet` already solves exactly this problem.** `Working/types/windowset.py:54`
`features: Optional[pd.DataFrame]`, with the invariant *"WindowSet carries one feature row per window"*
enforced at `:56-61`, parquet serialisation at `:94-109`, and a `__eq__` that compares frames. The
client already renders it as a feature heatmap (`BLOCK_INTEGRATION.md:91`).

**So: add `features: Optional[pd.DataFrame] = None` to `SpanSet`, mirroring `WindowSet` exactly** —
same invariant (one row per span), same parquet serialisation, same `__eq__` treatment. **This adds no
eighth type and breaks no existing caller** (the field defaults to `None`). Your block signature is
then `SpanSet → SpanSet`, which the type system already allows.

`BLOCK_INTEGRATION.md:143-146` reserves template `kind = "interrogation"` for *"the feature chains
(`SpanSet → SpanSet + Features`), whose blocks do not exist yet, so no rule produces it today."*
**This prompt is what that reservation was waiting for.** Register your template under that kind.

**You will be the first `SpanSet` consumer.** None of the 34 registered adapters declares
`input_kind="spanset"`. Copy the missing-typed-input error message shape verbatim from
`Adapters/detection_summation_threshold.py:76`.

## Work (test-first per seam)

### 1. `SpanSet.features`

Additive field, `WindowSet`'s invariant and serialisation mirrored. Tests for: the one-row-per-span
refusal, round-tripping through `to_path`/`from_path`, `__eq__` over frames, and **every existing
`SpanSet` caller still working with `features=None`.** That last one is the regression risk.

### 2. One shape block: `interrogation.event_shape` (SpanSet → SpanSet)

Emits, per span, polarity-neutral: **event depth/amplitude, rise height / spike height, event width
(onset→extremum), duration (onset→recovery), half width (FWHM), recovery time, max slope, onset slope,
chord slope, peakedness.** One block, because the researcher asked to *see all measures from a single
block* rather than run three to characterise one event.

Reuse `detect5`'s definitions where they exist. **Where you must define a measure (recovery, FWHM,
polarity-neutral width), state the rule in the docstring AND in the payload**, following
`interrogation_routes.py:118-123`'s `rules` list — a measure whose rule is unstated cannot be argued
with, which is the same principle prompt `A` applied to the null marker.

### 3. `interrogation.intervals` (SpanSet → SpanSet)

Inter-event intervals and their statistics. **Three implementations exist; consolidate to one and
delete none of the callers without checking.** Carry over the hard-won rule from `store11.py:116-123`:

> Inter-event intervals are only meaningful inside one group, and the three species' intervals differ
> by two orders of magnitude, so nothing about timing may be pooled before it has been measured per
> group.

Also `sequences11.py`'s regularity gate (`cv` with `ddof=1`, `r2` of interval against index, drift
ratio of last third to first third) is real, tested thinking about when a train *is* a train. Reuse it.

### 4. The rose plot, over `gradients.rose_data`

A view over the per-event `max_slope` features. **The split key is the decision:** `rose_data`'s
default `split_by="span_key"` is an analysed span, **not** a sequence. The researcher wants slopes
compared *across the events in a sequence*, and the data is there:

    sequences        148 rows  (118 machine, 30 human)
    sequence_members 1646 rows, 1528 carrying gap_before (seconds from the previous onset)

`rose_data`'s per-group output shape accepts a sequence-derived key unchanged. **Note that
`motif_entry.scale` is `'event'` for all 3,603 rows and zero `'train'` entries exist** — trains live in
the `sequences` table, not as library entries, so key off `sequences`.

### 5. Persist per-event features; never persist comparisons

Q-I1/Q-I4, decided: **per-event features are stored on the motif** — a `motif_features` table keyed by
**content hash**, recomputable from the snippet, never authoritative (confirmed absent from the live
database's 37 tables). **Cross-event comparison results exist only in the analysis run and are never
stored.** That is what lets a researcher assemble a `SpanSet` of Library motifs **that share no
sequence**, run a comparison over it, and get a result — the comparison is a view, the features are the
data.

**One requirement that came out of the `drop_motifs10` investigation and is easy to miss:** the Library
import took span indices and **dropped every amplitude the detector computed.** Filtering the Library
by amplitude is therefore impossible today, and filtering on peak-to-peak over the stored span is the
*wrong* measure (the stored snippet is ~4x the onset-to-trough extent; a wider window just catches
drift). **`motif_features` must carry the detector's own `drop_depth_mv` where a detector produced
one**, so that Q-X2.5's floor filter has a correct number to filter on.

### 6. `preprocessing.invert` (Signal → Signal)

One block, near-trivial, high value: the researcher has already trialled running the drop-motif
algorithm on an inverted signal to find spikes, with some success, and `drop_motifs10`'s manifest
already carries an `inverted` pass flag (set false). **This makes every existing drop detector a spike
detector for one block's work.** Include it — it is the cheapest item here and it is what makes the
polarity-neutral features meaningful on real spike data.

## Explicitly NOT in scope

| Not in scope | Why |
|---|---|
| **An eighth interchange type** | Forbidden by `Working/types/__init__.py:5-6`. Use `SpanSet.features` |
| **Fan-out: applying two feature blocks to one train without re-running** | **Q-B-CHAIN, round 3, explicitly deferred by the researcher** — they want to think about it. **Assume one chain per analysis intent.** Do not build a fan-out node |
| **Filtering, re-running or re-importing `drop_motifs10`** | Q-X2.5 / Q-X2.7. You supply the number the filter needs; you do not build the filter |
| **A spike *detector*** | `preprocessing.invert` plus the existing drop detector is the route. A native spike detector is later work |
| **FitzHugh–Nagumo** | wiring's own verdict: 2–3 days, ignore for v1 |
| **The plot-domain rule, units, `DEFAULT_CHAIN`, the demo chain** | prompts `B`/`C`, unchanged |

## The gate

Per `BLOCK_INTEGRATION.md` §"checklist", for **each** new block: `tests/test_adapter_<name>.py`
(types + category, defaults and `validate_params` bounds, one run on a synthetic ~30 s signal, the
error when the typed input is missing); a `to_payload` case in `tests/test_webui_serialize.py` if the
output shape is new; `tests/test_template_<name>.py` if it joins a template in
`webui/server/templates.py::CANONICAL`; a glyph in `webui/client/src/analyse/glyphs.tsx` `BY_NAME`; a
smoke state in `webui/smoke_pages/analyse.json`. `tests/test_block_standard.py` picks blocks up
automatically — **add each to its `COSTED` list** and give it a real `estimate` via
`Working/block_cost.py::register_cost_model`, or return `None` *with the rationale*. Never a guessed
constant.

Then: `npx tsc -b` + `npm run build`; `webui/smoke.py` against a `--sandbox` bridge **restarted
immediately beforehand**; `pytest` against the **1660 passed / 6 skipped / 0 failed** baseline (not the
969 in `webui/PYTEST_GATE_FINAL.txt`), comparing failure **sets**. FastAPI files run under
`webui/.venv`, where `test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers`
fails pre-existing and is not yours.

**Evidence.** Run the shape block over the **410 `drop_motifs5` seed events** and put a table in your
report comparing your measures against `events.csv`'s own columns for the same events — depth against
`drop_depth_mv`, width against `fall_duration_s`, max slope against `max_slope_raw * 1000`. **Where
you disagree with the detector, explain which is right.** That comparison is the claim this prompt
exists to make. Then run the rose over one real sequence and screenshot it into
`webui/screenshots/fixup/D/`.

## Report

`docs/prompts/fixup/reports/D-event-features.md`: the measures implemented with **the exact rule for
each one you had to define**; the seed-store comparison table; what you reused and the "why not reuse"
sentence for anything you did not; the `SpanSet.features` change and what it might break; defaults
taken; items left; out-of-scope files touched; the gate; a short chat summary.

Then update `03-analyse-interrogation.md` I1–I3, `08-library.md` L11–L12, `00-cross-cutting.md` X3 and
`QUESTIONS.md` Q-I1/Q-I2/Q-I3/Q-X3.
