# Fixup G — Review: a real time axis, honest padding, and source resolution

**Ready to run. Prompt `M` is done** (`reports/M-migrate-legacy-detections.md`, 2026-09-28): the 115
legacy span-relative detections are channel-absolute in the real database and a second pass plans zero
rows. You still add Review's `absolute_bounds` shift (§4) — belt and braces, because a database
restored from an older backup still holds relative rows.

## Running in parallel

**Prompt `E` (`E-aggregate-stops-fabricating.md`) runs in the same checkout at the same time.** It owns
Analyse › Interrogation. You own Review. Read this before your first commit.

| | you (`G`) | `E` |
|---|---|---|
| client | `webui/client/src/review/**` | `webui/client/src/interrogation/**`, `api/interrogation.ts` |
| server | `webui/server/review.py`, `webui/server/decimate.py` | `webui/server/interrogation_routes.py` |
| core | `Working/review/queues.py`, `Working/database/queries.py` (`queue_candidates` only) | `Adapters/interrogation_event_shape.py` |
| smoke | `webui/smoke_pages/review.json` | `webui/smoke_pages/interrogation.json`, `analyse.json` |
| port / dist | **8766**, a private client build | 8765 |

**Shared files — small hunks, commit immediately with explicit `--` paths, never `git add -A`:**
`webui/client/src/api.ts` (append only), `webui/smoke.py` (extend only). A path-scoped commit can still
carry the other agent's hunks in a file you both touched, so commit the moment your hunk is green.

**The one real collision, and how it is avoided.** Your fix changes how a trace is given its x axis,
and `webui/client/src/kit/plots.tsx` (`Trace`, `MiniTrace`) plus `webui/client/src/charts/` are used
by `E`'s pages too. **Your change to those components must be ADDITIVE and OPTIONAL** — an existing
caller that passes no `t` keeps today's behaviour exactly. Do not change a signature `E` is calling.
If you find you cannot do it additively, **stop and say so** rather than breaking Interrogation
mid-flight.

**`charts/domain.ts` belongs to prompt `C`** (`reports/C-one-plot-domain-rule.md`). Neither of you
changes the y-domain rule. This prompt is about the **x** axis.

**Gates collide on this machine.** `pytest -n auto` and `webui/smoke.py` must not run together —
prompt `B`'s report §9 records 23 spurious smoke failures from exactly that (Chromium
`ERR_NETWORK_IO_SUSPENDED`, every workspace's first state timing out, no server traceback behind any).
With two agents: use `pytest -n 4`, and **announce in your report when you took the machine for smoke**.

---

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md`, `docs/prompts/fixup/QUESTIONS.md` §"Round 4
findings" (the diagnosis this implements, with the reproduction), and
`reports/M-migrate-legacy-detections.md`. Commit prefix `fixup-g:`. Test-first; first commit touches
only `tests/` and must fail.

## The defect, already diagnosed and reproduced

**`webui/server/review.py:111` `_trace` discards `env["t"]` and returns only `env["v"]`**, on a
docstring contract that *"the client's traces are values, the x axis is implied"*. The client honours
that literally: `webui/client/src/review/parts.tsx:70-75` treats `context.values` as **one value per
second**, and `kit/plots.tsx:105,111` maps index `i` → `t0 + i/fs` with `fs = 1`.

But `decimate.envelope` returns **fewer, non-uniformly spaced** points whenever `m > 2*px`. Reproduced
exactly against the researcher's screenshot, detection 102:

    context [2033, 2693) = 660 samples -> envelope at px=320 -> 440 points
    client draws 440 points at 1/s from t0=2033 -> 0.5647 h .. 0.6867 h   [screenshot: "0.565 .. 0.687"]
    the drop is DRAWN at 0.6294 h  [screenshot: "~0.626 h"]
    its TRUE position is 0.6619 h  -- INSIDE the highlight 0.6481-0.6647 h

Everything right of `t0` is compressed by 440/660 = **two thirds**. The highlight band is drawn in
**true absolute seconds** (`parts.tsx:74`). **Band and trace are on two different x-axes**, and the
researcher reasonably read that as the detector pointing at the wrong place. It was not; the detection
window contains the only large drop in its context.

Three symptoms, one root cause:

- **U2** the highlight appears to miss the event;
- **U1 (context card)** the trace zigzags — each envelope bucket emits its min **and** max, which are
  meant to land on nearly the same x and draw as a vertical tick; with `t` gone they are drawn a full
  "second" apart, so every bucket becomes a diagonal;
- **U3** the padding looks one-sided — `parts.tsx:71` computes `off = CONTEXT_PAD_MAX - pad` and slices
  **envelope points** as though they were seconds. At ±120 s that strips 180 of 440 points from each
  end. Same class at `parts.tsx:117` (`i0`/`i1` in seconds indexed against `values.length`).

## Work (test-first per seam)

### 1. Carry the time axis. Stop implying it.

The payload must say where each point is. Whatever shape you choose, the invariant is that **a trace
and anything drawn beside it — the band, the crosshair, the axis labels — are in one coordinate
system, and a test proves it.** The current contract is the defect; do not preserve it for
compatibility.

Pin it with a test that would have caught this: a span long enough to force decimation, asserting the
drawn position of a known feature equals its true position. `parts.tsx:70-75` and `:117` both need
rewriting in the same breath — they are the same mistake twice.

### 2. Size decimation to the rendered width

`review.py:52-53` `CONTEXT_PX = 320` and `SHAPE_PX = 60` are constants that never see the card's
actual width. Measured consequences:

- The context card renders at ~800–870 px and is served **440 points for 660 samples** — the server
  discards about a third of the samples that would have fitted, **for no benefit**.
- `SHAPE_PX = 60` caps a long candidate at 120 points. For a 3600 s window queue that is ~30 samples
  per point over ~380 px — genuinely under-sampled. It does not bite on a 60 s candidate, which is
  why nobody saw it.

Make the requested resolution follow the surface that will draw it. `charts/useSize.ts` exists.
**Never serve fewer points than the plot has pixels** unless the payload would be unreasonable, and if
you cap, say so in the payload rather than silently.

### 3. The Shape card's staircase is NOT a bug — do not "fix" it

Measured: `SHAPE_PX = 60` over a 60-sample candidate at **fs = 1 Hz** returns 60 raw samples,
undecimated, ~6 px between vertices at stroke width 2. That is real data resolution. Value
quantisation was ruled out — smallest non-zero step 2.2e-9 V, no plateaus, float64.

**Do not smooth, interpolate or spline it.** A drawn curve that implies samples the recording does not
have is a fabrication, and this stage has already had to remove one (prompt `E`'s). If anything, the
card should make the sample rate legible.

### 4. Review shifts a legacy row, like the other three readers

`Working/database/queries.py::queue_candidates` does not select `r.span_start`, and
`Working/review/queues.py::_resolve_detections` copies `start_idx` raw into the item.
`absolute_bounds` is imported in that file but used only in `_prior_verdicts`, for rediscovery
matching — never for the coordinates the item carries out. **Review is the fourth reader the wiring
stage missed.**

`M` migrated the data, so this is a no-op on this database today. Add it anyway: a restored backup
holds relative rows, and this defect has now been found twice in two readers.

Test it on a **synthetic** fixture with a legacy row — not on the real database, which no longer has
one.

### 5. Read the source recording when one exists (Q24: default ON)

Recording 385 is a **10:1 decimation** of `L_LM_Jul_26_J_raw` at 10 Hz; `recordings.parent_recording_id`
and `parent_offset` already point at it, and `webui/server/corpus.py:119-122` already resolves a
parent. Review has been judging event shape on a tenth of the detail that exists.

A **"source resolution" toggle on the Shape card, defaulted ON.** The researcher's call: few datasets
are decimated subsets, so it is an edge case and defaulting it on costs little.

**It must be honest about what it is showing.** The card has to say which recording and which rate it
drew, because "this event looks smooth" means something different at 1 Hz and 10 Hz. When no parent
exists — the common case — the toggle is absent or disabled with the reason, never present and inert.

**Units:** the parent is a different `recordings` row with its own `units`. Prompt `B` put the
conversion at one seam (`corpus.display_channel`); go through it. A parent read raw would be 1000x out
for a volts file, which is the bug `B` existed to kill.

## Explicitly NOT in scope

| Not in scope | Why |
|---|---|
| **The y-domain rule** (`charts/domain.ts`, the reference bar, `measuredDomain`) | Prompt `C`. This is the x axis |
| **Anything under `webui/client/src/interrogation/`, `api/interrogation.ts`, `webui/server/interrogation_routes.py`** | Prompt `E`, running in parallel |
| **Review classes (1/2/3/4/9), the extract-events editor, the rediscovery prior verdict, "sorted by score"** | `07-review.md` R3/R4/R7 — the Review *behaviour* prompt, not this one |
| **Re-running any detector, or changing any stored row** | `M` is done; this prompt writes no data |
| **Redesigning how blocks present results** | Prompt `H` |

## The gate

1. `npx tsc -b` and `npm run build` in `webui/client` — **into your own dist, not the shared one**
   (`E` has pages open against theirs);
2. `webui/smoke.py` against a `--sandbox` bridge on **port 8766**, restarted immediately beforehand,
   **and not while `E` is running `pytest`**;
3. `pytest -n 4` against the **1786 passed / 6 skipped / 0 failed** baseline (`M`'s report §9),
   comparing failure **sets**. FastAPI files under `webui/.venv`, where
   `test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers` fails pre-existing
   and is not yours.

**Evidence.** Re-create the researcher's screenshot: **detection 102**, queue
`drop_detection_v1 - Mushroom_260720 CH14`, before and after, into `webui/screenshots/fixup/G/`. After
your change the drop must sit **inside** the highlighted band. Put the measured drawn-position versus
true-position in your report as a table, for that item and for one long-span candidate. Also screenshot
the padding at ±30 / ±120 / ±300 s showing it symmetric, and the Shape card with source resolution on
and off.

## Report

`docs/prompts/fixup/reports/G-review-axis-and-resolution.md`: the payload shape you chose and why; the
drawn-vs-true table; how decimation now follows the width, with the numbers; what the source-resolution
toggle says when there is no parent; the `absolute_bounds` addition and its synthetic test; **whether
your `kit/plots.tsx` change stayed additive** (and if not, what you did instead); when you took the
machine for smoke; defaults taken; items left; out-of-scope files touched; the gate; a chat summary.

Then close `07-review.md` R1 and the U1/U2/U3 rows in `QUESTIONS.md`.
