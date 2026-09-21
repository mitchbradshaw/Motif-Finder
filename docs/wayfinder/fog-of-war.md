# Fog of war — carry-forward for the whole-project map

This file collects every question that is still open across the Underground Brains pipeline and its interface, as of **2026-09-16**, the night the map [Map: rebuild the Pipeline GUI interface on a stack chosen by evidence][map] closes. It seeds a future wayfinder map covering the whole pipeline and project, of which that map was one subsection. Items decided that night are not listed: the stack (React 19 + TypeScript + Vite + d3/SVG over a FastAPI bridge, `docs/adr/0001-web-ui-stack.md`), the tree at `webui/` against a throwaway runtime, its gates (`webui/smoke.py` + `tsc -b` + `vite build`), the HTTP JSON + SSE seam speaking the seven interchange types through one serialiser and one client renderer switch, and keeping `UI/` intact but ignored.

Cite items as "fog-of-war.md §Core seam C3". Each item carries one status:
- `ticketable now` — precise enough to open as a decision or task ticket today.
- `fog` — in scope, but not yet sharp enough to ticket; needs grilling, evidence or the researcher.
- `out of scope` — ruled out; listed only so it is not rediscovered as fog.
- `decided` — a builder of the page shells settled it for the shells (the decision is stated in the item); confirm or overturn, but it is no longer open.

Rows from `prototyping/UI_FUNCTIONAL_SPEC.md` §12 (decisions that depart from the PRD) appear as confirmation items, grouped under each area's "PRD departures to confirm" heading.

## Core seam and data

### C1 — Public read API for step outputs
- **Question** — What public core function returns a step's output (value plus adapter meta) for a given recipe prefix, so the bridge stops keeping payloads in server memory and a JSON meta sidecar per prefix hash?
- **Why it matters** — The only path today is private `_recipe_prefix_hash` → `get_step_artifact` → the type's `from_path`, and a cache-restored step loses `AdapterResult.meta` (SAX cutlines, MP window, model card) in the core; the bridge papers over both, and a server restart loses every finished job's payloads.
- **Source** — [Decide how the frontend reaches the core and the database][frontend-core] "concrete gaps" bullet 1; [Correct the four factual errors in UI_CONTEXT.md][ui-context] correction 4; `ui-prototypes/REPORT.md` §5 "Backend gaps wrapped or stubbed" bullet 1, §7 "carry into the build ticket".
- **Status** — `ticketable now`

### C2 — `init_db()` cost on every connection
- **Question** — Should `init_db()` split into a once-per-process migrate-and-rebuild and a cheap connect, given it runs additive migrations and a verdict-table rebuild on every call and the bridge calls it per job (`webui/server/runs.py:129`, `:150`)?
- **Why it matters** — Every opener pays for migrations and a rebuild; with job threads, or the old and new servers, opening the same file, repeated rebuilds are the likeliest source of writer contention once a real-database mode exists (C9).
- **Source** — [Decide how the frontend reaches the core and the database][frontend-core] gap 3 (`Working/database/schema.py:622-645`); [Decide where the new tree lives and how both trees are served][tree-location] "Whether they can run at the same time".
- **Status** — `ticketable now`

### C3 — Adapter self-description (the registry's shape)
- **Question** — What must an adapter declare so a non-Python caller can describe it without reading its code: its null (none is declared today), whether it reports within-step progress, which learned values it exposes, its span ceiling, and a calibrated cost estimate?
- **Why it matters** — The bridge infers or stubs each of these ("null · not declared", cutlines drawn "learned · not a parameter", "≤ N core est."), and every new page repeats the inference. What adapters compute is frozen; how they declare themselves is open. The sharp halves are C4, C5, A1 and A2.
- **Source** — [Map: rebuild the Pipeline GUI interface on a stack chosen by evidence][map] "Not yet specified" (adapter self-declaration); [Decide how the frontend reaches the core and the database][frontend-core] sub-question 5; `ui-prototypes/REPORT.md` §2 "The core's shape, not the frontend, set most limits", §5 D-A2, D-A3, D-A4, D-A14.
- **Status** — `fog`

### C4 — Within-step progress
- **Question** — Should adapters accept an `on_progress` fraction callback through `execute_recipe` (only `window_matrix` reports one today), or does the interface settle for per-step progress with an elapsed timer?
- **Why it matters** — The designed running frame ("64 % · 0.2 s left", chain-1d) cannot be honest without it, and a whole-channel matrix profile runs for hours behind an indeterminate bar.
- **Source** — `ui-prototypes/REPORT.md` §7 open question 5, §5 D-A4; `ui-prototypes/DECISIONS.md` §4 "Progress is per step"; [Correct the four factual errors in UI_CONTEXT.md][ui-context] correction 4 (four progress channels).
- **Status** — `ticketable now`

### C5 — Estimate calibration and per-block estimates
- **Question** — Should `estimate_recipe_seconds` be recalibrated (measured 70–230× pessimistic on short spans), and should the core estimate a hypothetical recipe so the insert modal can show an estimate on every card?
- **Why it matters** — Estimates drive local-versus-HPC routing and over-ceiling refusal (A3); a 70× overestimate refuses runs that take 0.1 s, and the modal currently shows "est. at run" on every card but the selected one.
- **Source** — `ui-prototypes/REPORT.md` §3 A run table ("core estimate vs actual"), §5 D-A12, D-A14 and "Backend gaps", §4 A rounds 1–2 "left open"; `ui-prototypes/DECISIONS.md` §6 "Not done".
- **Status** — `ticketable now`

### C6 — Run state across a reload or a server restart
- **Question** — Should live job state (event history, payloads, cancel handle) be recoverable from the database — the `runs.current_step` column already exists — so a restarted bridge re-attaches to, or honestly reports, an in-flight run?
- **Why it matters** — The bridge keeps jobs in server memory, replays SSE history to a late subscriber and the client re-attaches by job id; that survives a browser reload but not a server restart, which orphans a multi-hour run's `runs` row.
- **Source** — [Decide how the frontend reaches the core and the database][frontend-core] sub-question 4; `ui-prototypes/DECISIONS.md` §3 "Transport rules", §4 "Reload mid-run"; `ui-prototypes/REPORT.md` §7 (reload re-attach needs its own tests), §4 B round 1 "State".
- **Status** — `ticketable now`

### C7 — Detection/annotation write guard at the seam
- **Question** — When the new UI gains write paths (verdicts, tags, notes, span edits, hand edits), which Python-side module owns each write, and what structurally stops a human verdict reaching a machine row or the reverse?
- **Why it matters** — "The frontend never touches SQLite" is the precondition for enforcing the frozen separation, but the prototype has no annotation write path at all (Save span, tags and note are client-side stubs), so the guard has never been exercised.
- **Source** — [Decide how the frontend reaches the core and the database][frontend-core] gap 5 ("an argument for the seam"); `ui-prototypes/REPORT.md` §5 D-A11; `prototyping/UI_FUNCTIONAL_SPEC.md` §12 P6; `CLAUDE.md` non-negotiable rule 5.
- **Status** — `ticketable now`

### C8 — Signal reduction: where it lives, and never a chain step
- **Question** — Does bucketed min/max decimation move into `Working/` as a public "read this channel span at N points" function, explicitly a display read that can never enter a recipe hash, and who owns the point budget?
- **Why it matters** — It now exists twice: the verbatim `_minmax_decimate` in `UI/plots.py` (pinned by `tests/test_plots_perf.py`, which dies with the old tree) and a faster reshape/argmin copy with a NaN-aware fallback in `webui/server/decimate.py`. Open sub-questions: `MAX_RENDER_POINTS = 40000` versus the bridge's ≈2× plot width, and which other pure-numpy helpers are marooned in `UI/plots.py`.
- **Source** — [Decide where signal reduction lives, and whether it is a chain step][signal-reduction] (whole body); `ui-prototypes/DECISIONS.md` §4 "Decimation fast path"; `ui-prototypes/REPORT.md` §3 A zoom table note; `docs/adr/0001-web-ui-stack.md` "Inherited".
- **Status** — `ticketable now`

### C9 — When the new UI writes to the real database
- **Question** — The webui runs only against a copy under `webui/runtime/<stamp>/` with the step cache, two adapter `RESULTS_DIR`s and `MODEL_ROOT` redirected and the step-cache write threshold forced to 0.0; what is the route to a mode where runs, templates and verdicts persist, and which redirects and overrides survive into it?
- **Why it matters** — Until then nothing the researcher does in the new UI outlives a restart, and whether old and new servers may run side by side on one file is undecided.
- **Source** — `ui-prototypes/DECISIONS.md` §3 runtime isolation; `docs/adr/0001-web-ui-stack.md` "Consequences" (the bridge "must keep redirecting every writable path into a throwaway runtime"); `ui-prototypes/REPORT.md` §5 "Backend gaps" bullets 4–5; [Decide where the new tree lives and how both trees are served][tree-location] "Whether they can run at the same time".
- **Status** — `fog`

### C10 — Writable paths hardcoded in adapters and pipelines
- **Question** — Should every location an adapter or pipeline writes to (`detection_matrix_profile.RESULTS_DIR`, `preprocessing_window_matrix.RESULTS_DIR`, `catalogue_classifier.MODEL_ROOT`, the channels root in `Pipelines/materialize_channels`) resolve through `Working/config.py` at call time, so one override redirects them all?
- **Why it matters** — Each is a module-level constant, some written from inside a run body; `webui/server/runtime.py` rebinds three by hand and asserts none escapes, and an agent that ran the classifier "just to time it" wrote into the real `DATA/`. Same root cause as T1.
- **Source** — `ui-prototypes/REPORT.md` §2 ("adapters that write files from inside their run bodies"), §5 "Backend gaps" bullet 5; `ui-prototypes/DECISIONS.md` §4 "Three more writable paths", §7 lesson; `tests/test_materialize_channels.py:9-14`.
- **Status** — `ticketable now`

### C11 — Chain validation and insertion owned by the core
- **Question** — Should the core own full-chain validation (every bad junction reported, unknown adapters invalid) and a two-sided insert-at-position check, including side-input bindings, instead of the bridge reimplementing them in `webui/server/chain.py`?
- **Why it matters** — `validate_recipe_steps` reports only the first bad junction and accepts unknown adapters; `UI/analyse/chain_state.py` cannot be imported headless and its `to_recipe()` drops side-inputs, so the insert check now lives in both `UI/workspaces/analyse/builder.py` and the bridge.
- **Source** — `ui-prototypes/REPORT.md` §5 "Backend gaps" bullets 2–3; `ui-prototypes/DECISIONS.md` §4 "`UI/analyse/chain_state.py` not reused".
- **Status** — `ticketable now`

### C12 — Where the chain draft lives; one API surface or two
- **Question** — Is the draft recipe client state only, as the prototype keeps it, or does the core hold drafts; and is the bridge one API or a read side and an execute side with different guarantees?
- **Why it matters** — The prototype answered both by default rather than by decision, and they determine what a second tab, undo history and "Save template" mean.
- **Source** — [Decide how the frontend reaches the core and the database][frontend-core] sub-questions 1 and 3; `ui-prototypes/REPORT.md` §4 B round 1 "State" (A keeps the draft in the client).
- **Status** — `fog`

### C13 — Suffix re-execution and the step-cache write threshold
- **Question** — Is "re-run the whole recipe with `force=True` and rely on prefix-cache hits" the accepted execution model, and does the core's `STEP_CACHE_WRITE_THRESHOLD_S = 1.0` stay when the bridge's runtime sets it to 0.0?
- **Why it matters** — Without `force=True` a completed recipe returns `{reused: True}` and fires no callbacks; with the 1.0 s threshold a cheap chain caches nothing, so "cached · 0 s" badges would stop being true in a real-database mode.
- **Source** — [Correct the four factual errors in UI_CONTEXT.md][ui-context] correction 3; `ui-prototypes/DECISIONS.md` §4 "`force=True` on every run" and threshold bullet; `ui-prototypes/REPORT.md` §5 "Backend gaps" bullet 4.
- **Status** — `ticketable now`

### C14 — Cancelling a long step
- **Question** — Is cancel-between-steps acceptable for multi-hour steps, or must a long step run in a killable subprocess while keeping `execute_recipe`'s crash-safety?
- **Why it matters** — No transport can interrupt an in-flight numpy call; for a whole-channel matrix profile the honest "cancel checks between steps" means Cancel does nothing for hours.
- **Source** — [Map: rebuild the Pipeline GUI interface on a stack chosen by evidence][map] "Decisions so far" (transport survey); `ui-prototypes/REPORT.md` §5 D-A5; `ui-prototypes/DECISIONS.md` §4 "Cancel is honest".
- **Status** — `fog`

### C15 — Index frame of `SpanSet` on the wire
- **Question** — Should `SpanSet` producers emit absolute sample indices, as `WindowSet` starts already are, instead of span-relative indices that `serialize.py` shifts by `span_start`?
- **Why it matters** — The bridge handles it once, but every other consumer of a span run's `SpanSet` (export, Review, Library) must know the convention or place every span at the wrong hour.
- **Source** — `ui-prototypes/REPORT.md` §5 "Backend gaps" last bullet.
- **Status** — `ticketable now`

### C16 — Non-finite values in stored scores
- **Question** — Is `inf` in `detections.score` a deliberate sentinel or an upstream bug, and what does the wire contract send for it?
- **Why it matters** — JSON has no `inf`; the bridge maps it to null, which a renderer or an export can read as "no score".
- **Source** — `ui-prototypes/REPORT.md` §5 "Backend gaps" bullet 6.
- **Status** — `ticketable now`

### C17 — Matrix-profile JIT cold start
- **Question** — Should the ~30 s STUMPY numba warm-up be shown as a state in the UI, or taken out of the request path (cached compiled kernels), given a run started inside the warm-up silently waits?
- **Why it matters** — The first run of every server process took 31.9 s wall for a 0.1 s computation, which reads as a hang.
- **Source** — `ui-prototypes/REPORT.md` §3 A run table, §5 "Backend gaps" bullet 7, §8.1 note under the table.
- **Status** — `ticketable now`

### C18 — True sampling rates per source file
- **Question** — Are the rates fs1 = 1 Hz, fs2 = 2 Hz, and 10 Hz for Mushroom (M3_jul) and L_LM_Jul26_J correct, given L_LM's rate is inferred, not read from the file?
- **Why it matters** — Every sample-to-hours conversion, motif length and ± window in the pages and payloads depends on fs; Settings › Datasets marks each rate `read` or `inferred`, but none is confirmed.
- **Source** — `prototyping/UI_REVIEW_BACKLOG.md` "Open decisions" D3.
- **Status** — `ticketable now`

### C19 — Recording import in the new tree
- **Question** — Which UI-free core function does the new UI call to import a recording (dry run, fs read or entered, channel map, start time, link to an existing recording), given the only implementation is Panel-bound `UI/file_import.py`?
- **Why it matters** — Settings frame 1b designs the flow, but without a core import path the new tree cannot add data.
- **Source** — `prototyping/UI_FUNCTIONAL_SPEC.md` §11 (recording import; its "no designed flow" is stale); `prototyping/UI_REVIEW_BACKLOG.md` "Done" B20; [Correct the four factual errors in UI_CONTEXT.md][ui-context] correction 2 (`UI/file_import.py:131-135`).
- **Status** — `fog`

## Analysis semantics

### A1 — SAX cutlines: a parameter, or learned only
- **Question** — Should the SAX/dSAX adapters grow an explicit `cutlines` override parameter (a core change that enters the recipe hash), or does the Encoding block page keep the learned cutlines read-only, as the prototype draws them?
- **Why it matters** — Spec §6.8 asks for draggable cutlines, but the adapters learn them (Lloyd-Max, Mean-Shift, KDE) and expose them only in `meta.details`; dragging them would assert a parameter the core does not have.
- **Source** — `ui-prototypes/REPORT.md` §7 open question 3, §5 D-A2, §1 checklist 5; `prototyping/UI_FUNCTIONAL_SPEC.md` §6.8 row `Signal → Encoding`; see C3.
- **Status** — `ticketable now`

### A2 — What a null is, block by block
- **Question** — Is a block's null a per-adapter declaration, a paired `preprocessing.surrogate` run (the core's model today), or a per-analysis-kind method held in Settings › Nulls, and which views does each support (per-parameter null sweeps, "this parameter against the null", null bands behind histograms)?
- **Why it matters** — The pages put a null beside nearly every result, while the prototype had to show "no null" and "null · not declared" everywhere; the frames' null sweeps have no core source.
- **Source** — `ui-prototypes/REPORT.md` §5 D-A3, §3 A "Where the stack fought the design"; `prototyping/UI_FUNCTIONAL_SPEC.md` §12 P10, P23; `prototyping/UI_REVIEW_BACKLOG.md` "Design rules agreed" (interrogation null default).
- **Status** — `fog`

### A3 — Over-ceiling stage: refuse, or pause and hand to HPC
- **Question** — Is refusing a chain with a stage over its local ceiling (Run disabled with the reason, bridge answers 422) the right interim, until a core flow exists that pauses the run at that stage and continues once an uploaded result passes checks (recipe hash, per-channel shape, length, finite values)?
- **Why it matters** — P4 and P24 design per-stage pausing so cached cheap stages are never re-sent; the prototype refuses because pausing needs the manifest-inbox/SLURM flow, and running locally fails at once. The interim is ticketable; the pause flow itself is still fog.
- **Source** — `ui-prototypes/REPORT.md` §7 open question 4, §5 D-A13, §4 A round 1 P1; `prototyping/UI_FUNCTIONAL_SPEC.md` §12 P4, P24, §9.6; `prototyping/UI_REVIEW_BACKLOG.md` B22 (paused state drawn in chain 1i and Discovery).
- **Status** — `ticketable now`

### A4 — `Encoding` is terminal, yet the canonical chain consumes it
- **Question** — Does the core gain an `Encoding → SpanSet` drop-detection adapter so the designed default chain (baseline → noise floor → symbolic encoding → drop detection) can be composed, or is the canonical chain redrawn around adapters that exist?
- **Why it matters** — No registered adapter consumes `Encoding`, so the pages' headline chain cannot run; the prototype substituted detrend → matrix profile → threshold. B24 fixed the signatures (`Signal → Signal + estimate`, then `Encoding → SpanSet`) in the pages only.
- **Source** — `ui-prototypes/REPORT.md` §5 D-A1; `ui-prototypes/DECISIONS.md` §4 "Chain composed from real adapters"; `prototyping/UI_REVIEW_BACKLOG.md` B24 and "Sweep fixes applied" › Analyse › Chain.
- **Status** — `ticketable now`

### A5 — Motif pairs from the matrix profile
- **Question** — Should the matrix-profile adapter return its profile indices so motif pairs (M1a/M1b) come from the core, rather than being inferred client-side from equal profile values?
- **Why it matters** — Pairing by equal values can match the wrong subsequences, and the inference is invisible to export and Review.
- **Source** — `ui-prototypes/REPORT.md` §4 A round 1 and round 2 "Left open"; `ui-prototypes/DECISIONS.md` §6 "Not done".
- **Status** — `ticketable now`

### A6 — Values the pages draw that the core does not produce
- **Question** — For each designed view with no core source — per-parameter null sweeps, the slope strip, a per-query distance profile — is it a new adapter output, a derived read in the core, or dropped from the design?
- **Why it matters** — The prototype rendered these as labelled approximations or explicit empty states; left undecided, empty page shells on fixture data harden placeholders into apparent features.
- **Source** — `ui-prototypes/REPORT.md` §3 A "Where the stack fought the design", §5 D-A3.
- **Status** — `fog`

### A7 — Span ceiling of the image encoders
- **Question** — Do the gramian/image encoders keep their 5,000-sample `max_span_samples` cap (about 83 min at 1 Hz), or accept longer spans by windowing or downsampling?
- **Why it matters** — The cap refuses the 2 h example span, so the built-in gramian template works only on short spans and shows an over-ceiling card otherwise.
- **Source** — `ui-prototypes/REPORT.md` §1 checklist 4c, §5 "Backend gaps" (gramian cap); `ui-prototypes/DECISIONS.md` §6 (template renamed).
- **Status** — `ticketable now`

### A8 — Cross-channel and multi-channel analysis
- **Question** — What form do cross-channel viewing and multivariate analysis take in the new tree (the old tree's cross-channel peek and classification, Explore's lag-aligned frame, Discovery's multi-channel scope), and what must the core serve for them?
- **Why it matters** — Present in the old tree, parked in the spec and an inert button in the prototype; P3 keeps Analyse single-channel, so the question lands on Explore and Discovery.
- **Source** — [Map: rebuild the Pipeline GUI interface on a stack chosen by evidence][map] "Not yet specified" (cross-channel); `prototyping/UI_FUNCTIONAL_SPEC.md` §11 bullet 2, §12 P3; `ui-prototypes/REPORT.md` §1 checklist 8.
- **Status** — `fog`

### A9 — FitzHugh–Nagumo as a feature block
- **Question** — What does a FitzHugh–Nagumo fit block emit as features, with what null and what behaviour when the fit fails?
- **Why it matters** — It is permitted in interrogation as a feature-producing block but not designed, and one-block-per-analysis (P7) gives it its own page.
- **Source** — `prototyping/UI_FUNCTIONAL_SPEC.md` §11 bullet 3, §12 P7; `prototyping/UI_REVIEW_BACKLOG.md` "Design rules agreed".
- **Status** — `fog`

### A10 — Cluster selection criterion
- **Question** — Which criterion chooses the cluster count (fixed k, fixed cut, max silhouette, gap statistic, minimum class size), and what is its default?
- **Why it matters** — Nothing is pre-registered, and the choice shapes the cluster-label arm of the paired label comparison.
- **Source** — `prototyping/UI_REVIEW_BACKLOG.md` B4.
- **Status** — `fog`

### A11 — Splitting a supplied window set
- **Question** — When windows arrive as a source rather than from sliding windows, what applies the blocked split: a split filter on the source windows (blocked by recording and time, gap ≥ one window, straddling windows dropped), or a rule that only saved sets carrying their split are accepted?
- **Why it matters** — Human-labelled windows may be adjacent or overlapping, which is where leakage bites; P15 keeps the split inside the sliding-windows block, so nothing applies it to a supplied set.
- **Source** — `prototyping/UI_REVIEW_BACKLOG.md` B7; `prototyping/UI_FUNCTIONAL_SPEC.md` §12 P15, P18.
- **Status** — `fog`

### A12 — Saved window sets as stored artifacts
- **Question** — Where and how is a saved window set persisted (id, split, spacing check, verdict coverage, train-safe flag) so Analyse, Models and Review can pick it as a source?
- **Why it matters** — The Library shelf and the Models picker are drawn, but Save window set on the sliding-windows row, the Analyse source-chip picker and the Review queue source are not, and nothing in the core stores one.
- **Source** — `prototyping/UI_REVIEW_BACKLOG.md` B12, "Sweep fixes applied" › Models (frame 1b); `prototyping/UI_FUNCTIONAL_SPEC.md` §6.9, §12 P18.
- **Status** — `fog`

### A13 — Where window verdicts are stored
- **Question** — Are human verdicts on training and verification windows stored in a window-verdict table on the adjudication side, keyed by window-set id + window index, or by materialising each queued window as a detection row of a "windows" run?
- **Why it matters** — These windows are machine-produced with no detection row, yet the verdict is human judgement; either option must keep the machine/human separation (C7).
- **Source** — `prototyping/UI_REVIEW_BACKLOG.md` B15; `prototyping/UI_FUNCTIONAL_SPEC.md` §10.1, §12 P13; `CLAUDE.md` rule 5.
- **Status** — `ticketable now`

### A14 — Cluster grouping rule values
- **Question** — What defaults define a Review *sequence* cluster (maximum gap between detections, placeholder 6 min; minimum events, placeholder 2; same run and channel) and the cohesion limit (placeholder 0.45), and do they live in Settings › Analysis defaults?
- **Why it matters** — The placeholders already appear in Settings › Review queues and Library groupings, and sequence detection is shared with the Library's grouping bases (A15).
- **Source** — `prototyping/UI_REVIEW_BACKLOG.md` B16, "Sweep fixes applied" › Settings ("Not done, needs you").
- **Status** — `fog`

### A15 — Library grouping basis definitions
- **Question** — How are sequence similarity (events, order and gaps), the *frequency content* and *timescale* features, and a *spike train* unit that was not imported as one defined, with what default cuts, bins and minimum group size?
- **Why it matters** — Spec §8.2 names the bases and Settings shows placeholders, but nothing is pre-registered, and every Library grouping is computed from them.
- **Source** — `prototyping/UI_REVIEW_BACKLOG.md` B17, "Sweep fixes applied" › Settings; `prototyping/UI_FUNCTIONAL_SPEC.md` §8.2.
- **Status** — `fog`

### A16 — The key a Library hand edit binds to
- **Question** — What key does a hand edit (add, remove, exemplar, tag, class) bind to so it survives regrouping, given family ids are not stable across groupings?
- **Why it matters** — Hand edits must be stored apart from computed groupings and re-applied on regroup, under the "points at a family this grouping lacks → hand group" rule.
- **Source** — `prototyping/UI_REVIEW_BACKLOG.md` B18; `prototyping/UI_FUNCTIONAL_SPEC.md` §8.3, §12 P22.
- **Status** — `fog`

### A17 — Encoder versions
- **Question** — How does a new encoder or image size register as a version (today GASF / GADF / RP / fusion at 224 px) so templates and models record exactly which encoder they used?
- **Why it matters** — The pages keep an encoder-set selector for this, but the registry has no versioning scheme, so a changed encoder would silently alter reused templates.
- **Source** — `prototyping/UI_REVIEW_BACKLOG.md` B6, "Done" › Analyse › Training (04 encode, encoder versioning note).
- **Status** — `fog`

### A18 — Which HPC clusters and node profiles exist
- **Question** — Which clusters and nodes can the researcher actually submit to, and can a job use two nodes (the `gpu-multinode` profile)?
- **Why it matters** — Settings › Compute & HPC allows several clusters and job profiles; script generation and stage routing (A3) need the real list.
- **Source** — `prototyping/UI_REVIEW_BACKLOG.md` B19 (listed under "Done" but unresolved), "Sweep fixes applied" › Settings ("Not done, needs you").
- **Status** — `ticketable now`

### PRD departures to confirm (analysis)

Decisions recorded during the page review that override a PRD passage; each needs the researcher to confirm or reverse it. Source for all: `prototyping/UI_FUNCTIONAL_SPEC.md` §12 (row named). P4 is folded into A3.

- **A19 — P3: Analyse is single-channel**
  - **Question** — Confirm Analyse takes a span or one whole channel, never a channel or band list, with fan-out and multi-channel templates in Discovery.
  - **Why it matters** — Overrides PRD Part 1 stories 16–17 and the Analyse scope selector; B25 already rewrote the pages to it.
  - **Source** — §12 P3; `prototyping/UI_REVIEW_BACKLOG.md` B25.
  - **Status** — `ticketable now`
- **A20 — P6: verdicts are given in Review only**
  - **Question** — Confirm Explore offers *Take span for Review* / *Review this motif* instead of verdict buttons, while still saving tags and notes.
  - **Why it matters** — Overrides Part 1 stories 4–5 and Explore's seed verdict; keeps one write path into the human store (C7).
  - **Source** — §12 P6.
  - **Status** — `ticketable now`
- **A21 — P7: one block per analysis type**
  - **Question** — Confirm slope geometry, spike shape and a FitzHugh–Nagumo fit are separate blocks with their own pages, feeding a generic Aggregate block.
  - **Why it matters** — Overrides §6.6's single fixed interrogation chain; decides the block registry's granularity.
  - **Source** — §12 P7.
  - **Status** — `ticketable now`
- **A22 — P10: interrogation carries a null by default**
  - **Question** — Confirm matched random windows (200×) and shuffled onsets as the default interrogation nulls, with every fitted exponent shown beside the null exponent.
  - **Why it matters** — Extends the Part 1 surrogate protocol from runs to distributions and fits; depends on A2.
  - **Source** — §12 P10.
  - **Status** — `ticketable now`
- **A23 — P11: Analyse builds the training template, Models trains**
  - **Question** — Confirm the training chain is built and trialled on one channel in Analyse, and *Train in Models* runs it across channels with the paired cluster-label versus manual-label comparison on one split.
  - **Why it matters** — Overrides Part 1 story 16 / the RQ1 row, which put training and evaluation in Analyse.
  - **Source** — §12 P11.
  - **Status** — `ticketable now`
- **A24 — P12: leakage guards are parameters**
  - **Question** — Confirm sliding windows carry an editable gap (≥ window length) and a blocked-by-time split, random splits are marked leaking, and label-derived features (CNN scores) are off by default in the window matrix.
  - **Why it matters** — Part 1 is silent on split leakage; overlapping windows or label-trained features would contaminate the RQ1 comparison.
  - **Source** — §12 P12.
  - **Status** — `ticketable now`
- **A25 — P13: unreviewed windows go to Review from the training chain**
  - **Question** — Confirm *Send N unseen windows to Review* (queue cap 20,000, binary verdicts sufficient).
  - **Why it matters** — New relative to the PRD; the manual-label arm needs verdicts on the same windows, and where they are stored is A13.
  - **Source** — §12 P13.
  - **Status** — `ticketable now`
- **A26 — P15: a stage the source makes redundant is absent, not skipped**
  - **Question** — Confirm a `WindowSet` source feeds the window matrix directly with no greyed "skipped" row, and the split stays inside the sliding-windows block.
  - **Why it matters** — Overrides §6.2's "skipped rather than optional"; leaves the supplied-set split open (A11).
  - **Source** — §12 P15.
  - **Status** — `ticketable now`
- **A27 — P16: models reach Discovery only inside detection templates**
  - **Question** — Confirm Discovery never lists a bare model: detection with a model means a Model stage (`Model + WindowSet → Scores`) then a threshold stage, saved as a template.
  - **Why it matters** — One path, not two; the threshold turning scores into spans gets its own null.
  - **Source** — §12 P16.
  - **Status** — `ticketable now`
- **A28 — P17: a seed search is a run**
  - **Question** — Confirm Discovery has one page with *Apply template* and *Seed search* sharing one results area, any two runs compare pairwise, and scope is one recording × one or more channels.
  - **Why it matters** — Overrides §7's separate single-channel pages; comparing a seed to a template becomes possible.
  - **Source** — §12 P17.
  - **Status** — `ticketable now`
- **A29 — P18: a window set is a saved, reusable artifact**
  - **Question** — Confirm any `WindowSet` output offers *Save window set*, carrying its split, spacing check and verdict coverage, accepted as a source in Analyse, Models and Review.
  - **Why it matters** — Overrides Part 1's windows-as-intermediate; storage is A12.
  - **Source** — §12 P18.
  - **Status** — `ticketable now`
- **A30 — P19: blocked test portion and a registration gate**
  - **Question** — Confirm evaluation on a blocked test portion set aside before training, registration requiring held-out checks, human verification and sign-off, local training only at ≤ 2 h estimate, HPC status marked by hand, and M4 locked in Models too.
  - **Why it matters** — Overrides Part 1's held-out recording as the test set and adds a model lifecycle the PRD does not specify.
  - **Source** — §12 P19.
  - **Status** — `ticketable now`
- **A31 — P20: Review works in named, blindable queues**
  - **Question** — Confirm named queues with one source each, machine opinion hidden until the verdict in training-window and verification queues, the blind state stored with every verdict, and artifact likelihood never hidden.
  - **Why it matters** — Overrides Part 1's single filterable queue with the score always shown; adds a column to every verdict.
  - **Source** — §12 P20.
  - **Status** — `ticketable now`
- **A32 — P21: the seed verdict promotes to the Library automatically**
  - **Question** — Confirm pressing S promotes to the Library, a class is optional and implies `interesting` unless non-informative, and a binary verdict is the minimum for "annotated".
  - **Why it matters** — Overrides Part 1 story 32's separate explicit promotion step.
  - **Source** — §12 P21.
  - **Status** — `ticketable now`
- **A33 — P22: the Library computes its own groupings**
  - **Question** — Confirm three Library sections (Motifs, Window sets, Templates), groupings chosen by unit and basis, non-fitting entries omitted and flagged, hand edits surviving regroup, and no regroup comparison frame.
  - **Why it matters** — Overrides Part 1's thumbnail grid with a group-by selector; definitions are A15 and A16.
  - **Source** — §12 P22.
  - **Status** — `ticketable now`
- **A34 — P24: one global Jobs page; an over-limit stage pauses the run**
  - **Question** — Confirm Jobs lists every job across workspaces (Review queues included, replacing the Models Jobs tab) and a paused run continues from the next stage once its result passes checks, refusing a result made with other parameters.
  - **Why it matters** — Overrides Part 1 "Cluster routing" and the first §7b draft; the implementation question is A3.
  - **Source** — §12 P24.
  - **Status** — `ticketable now`

## Frontend design

### F1 — Time axis convention: hours or seconds
- **Question** — Confirm hours since recording start with span-adaptive decimals everywhere, falling back to absolute seconds only for spans ≤ 15 min, against frame chain-1's seconds on a 50 s span starting at t = 0.
- **Why it matters** — Every shared axis, crosshair, span hand-off and export inherits the convention; the pens have already moved Review and chain 1h / 7 from clock time to hours (X12).
- **Source** — `ui-prototypes/REPORT.md` §7 open question 2, §3 A "Where the stack fought the design" (last sentence), §5 D-A7; `ui-prototypes/DECISIONS.md` §6 (`fmtAxis`); `prototyping/UI_FUNCTIONAL_SPEC.md` §0; `prototyping/UI_REVIEW_BACKLOG.md` B26 (X12), "Sweep fixes applied" › Review and › Analyse › Chain.
- **Status** — `ticketable now`

### F2 — One state model for rows and jobs
- **Question** — What is the single state model for a chain row and a job (new, stale, running, computed, cached, failed, cancelled, invalid, on cluster, paused, render failed), which layer owns it (client store, bridge or core), and which transitions are legal?
- **Why it matters** — Row-state semantics (which badge, whether a payload is still the current step's, hiding another source's results) cost the prototype more than all seven renderers, the pens' badge words disagreed until B26, and Analyse, Discovery and Jobs all show the same states.
- **Source** — `ui-prototypes/REPORT.md` §2 "What building A taught" bullet 1, §3 A "Where the stack fought the design", §4 A round 2 fixes (computed versus cached wording); `prototyping/UI_REVIEW_BACKLOG.md` B26 (X15).
- **Status** — `fog`

### F3 — Block pages: a dispatch seam and the block contract
- **Question** — Should block pages get a per-adapter registry seam like the per-type renderer switch, replacing dispatch on the adapter name inside one ~550-line file, with the §6.8 block contract as its checklist; and can adding an eighth interchange type touch fewer than four files?
- **Why it matters** — The type seam held for seven types, but every new block page grows one file, and B11 requires each new type signature to gain a §6.8 row before its first block.
- **Source** — `ui-prototypes/REPORT.md` §4 A round 2 "Left open", §3 A "Lines of code" (what an eighth type touches); `prototyping/UI_REVIEW_BACKLOG.md` B11; `prototyping/UI_FUNCTIONAL_SPEC.md` §6.8, §12 P5.
- **Status** — `ticketable now`

### F4 — Keyboard operability of plots and handles
- **Question** — What keyboard model do the corpus heatmap, the draggable cut/threshold line and the span handles use, given only the handles and span SVG are operable today?
- **Why it matters** — Left open through both critique rounds; draggable controls with no keys make precise parameter values hard to set.
- **Source** — `ui-prototypes/REPORT.md` §4 A round 1 P2 ("left open") and round 2 "Left open".
- **Status** — `ticketable now`

### F5 — Labels and chips overprinting traces
- **Question** — How are y-axis labels and matrix-profile motif chips placed in chain rows so they never cover the trace (gutter, halo or collision avoidance)?
- **Why it matters** — Still present after round 2, and the same class as the pens' label-on-trace collisions, so it recurs on every row type the shells add.
- **Source** — `ui-prototypes/REPORT.md` §4 A round 2 "Left open"; `prototyping/UI_REVIEW_BACKLOG.md` B29 (label-on-trace collisions).
- **Status** — `ticketable now`

### F6 — Explore warns before sending an over-ceiling span
- **Question** — Should Explore warn when a dragged span exceeds the default chain's local ceiling, as Analyse already does?
- **Why it matters** — Today the researcher learns of the refusal only after the hand-off to Analyse (A3).
- **Source** — `ui-prototypes/REPORT.md` §4 A round 2 "Left open".
- **Status** — `ticketable now`

### F7 — Client type hygiene on the wire contract
- **Question** — Should run events get a discriminated-union `RunEvent` type (the analyse store carries about eight casts) and `staleFrom` move into the shared `ChainDraft`?
- **Why it matters** — Casts hide wire-contract drift from `tsc -b`, one of the new tree's three gates.
- **Source** — `ui-prototypes/DECISIONS.md` §6 "Not done".
- **Status** — `ticketable now`

### F8 — "Input ghosted behind" on its own y scale
- **Question** — Confirm that a `Signal → Signal` row draws the ghosted input on its own, labelled y scale rather than the output's.
- **Why it matters** — Raw input sits at −0.66 mV DC and the detrended output at ±0.003 mV, so one axis flattens one of them; it is a visible departure from §6.8, and waveforms are never normalised.
- **Source** — `ui-prototypes/REPORT.md` §5 D-A9, §3 A "Where the stack fought the design"; `prototyping/UI_FUNCTIONAL_SPEC.md` §6.8 row `Signal → Signal`.
- **Status** — `ticketable now`

### F9 — Header chips once jobs persist
- **Question** — What do "N need you" and "Jobs · N" count in the real app — the designed cross-workspace needs-you set (paused runs, overdue cluster jobs, review queues) — rather than failed and running jobs in the current server process?
- **Why it matters** — The prototype's honest counts reset on every restart; the designed chips need the persistent job state of C6.
- **Source** — `ui-prototypes/REPORT.md` §5 D-A6; `ui-prototypes/DECISIONS.md` §4 "Header chips are real"; `prototyping/UI_FUNCTIONAL_SPEC.md` §7c, §12 P24.
- **Status** — `fog`

### F10 — Which pages need the canvas escape hatch
- **Question** — Which designed pages must draw tens of thousands of marks at once (every detection across a recording, Library recurrence, a large recurrence matrix, the Library atlas), and is each renderer SVG, hand-written canvas or a small canvas library behind the same per-type seam?
- **Why it matters** — SVG degrades past roughly 10–20k elements, the chosen stack's one technical ceiling, untested at that density; deciding after pages exist means rewriting renderers. The export consequence is E5.
- **Source** — `ui-prototypes/REPORT.md` §8.2 "headroom for very dense plots", §8 "Additional findings" bullet 1; `docs/adr/0001-web-ui-stack.md` "Plotting approach".
- **Status** — `fog`

### F11 — Web fonts on a localhost-only tool
- **Question** — Should Inter and Geist Mono be bundled with the client instead of loaded from Google Fonts (`webui/client/index.html:8-10`)?
- **Why it matters** — The app is single-machine and localhost; offline it silently falls back to system fonts, which changes the smoke screenshots used as review evidence.
- **Source** — `ui-prototypes/DECISIONS.md` §4 "Fonts"; `webui/client/index.html`; [Map: rebuild the Pipeline GUI interface on a stack chosen by evidence][map] "Constraints settled while charting" (localhost).
- **Status** — `ticketable now`

### F12 — Review and Library workspaces in the new tree
- **Question** — How, and in what order, are Review (G7: adjudicate without contaminating ground truth) and Library (G8: browse along two independent axes) built on the new stack, given both have designed `.pen` forms?
- **Why it matters** — The slice did not touch them, and they carry the write paths (C7, A13, A16) and the densest plots (F10, E3).
- **Source** — [Map: rebuild the Pipeline GUI interface on a stack chosen by evidence][map] "Not yet specified" bullet 1; `prototyping/UI_FUNCTIONAL_SPEC.md` §8, §10.
- **Status** — `fog`

### F13 — Explore › Signal bottom ribbons versus drawer tabs (D1)
- **Question** — Should the bottom ribbons (Filters & search · Annotations · Detections · Keyboard shortcuts) mirror the drawer's three tabs (Annotations · Detections · Shortcuts) with filters inside each?
- **Why it matters** — The drawer was rebuilt as tabs with a collapsible filter section, so the page now has two disagreeing navigation schemes.
- **Source** — `prototyping/UI_REVIEW_BACKLOG.md` "Open decisions" D1.
- **Status** — `ticketable now`

### F14 — Span edit reachable from Explore (D2)
- **Question** — Should Explore offer "edit extent" on an annotation it already owns, or stay reachable only as a hand-off from Review?
- **Why it matters** — Spec §4.3 puts editing in Explore entered from Review; the answer adds or removes a human write path (C7).
- **Source** — `prototyping/UI_REVIEW_BACKLOG.md` "Open decisions" D2; `prototyping/UI_FUNCTIONAL_SPEC.md` §4.3.
- **Status** — `ticketable now`

### F15 — Arithmetic and state inside the reference frames (B28 remainder)
- **Question** — Fix the frame numbers that still do not reconcile: chain (baseline warning, scores markers, run-history interrogation row, 1c Save template enabled); interrogation (4c-b stacked histograms, 4c-c copied histograms, 4c "100 % one fall" versus a flagged event, 4b missing null panel); training (01 block and split counts, 5b class sizes 343 vs 543, 2b contingency sums, 5c window-time and image sums, 0 vs 5b cluster strips); Explore (drawer filters vs rows, MOTIF_233 box scale, span-edit px scale, corpus filter vs map).
- **Why it matters** — The `.pen` pages are the interface target; shells built on fixture data will copy inconsistent placeholders as though they were designed.
- **Source** — `prototyping/UI_REVIEW_BACKLOG.md` B28, and "Sweep fixes applied" "Not done (optional, B28)" under Analyse › Chain, › Interrogation, › Training and Explore; `prototyping/UI_SWEEP_2026-09-14.md`.
- **Status** — `ticketable now`

### F16 — Remaining layout defects in the reference frames (B29 remainder)
- **Question** — Fix the B29 defects not recorded as fixed: chain 6 disabled-reason text overrunning its cards, the chain 1e banner over a card edge, Explore 1b's overlapping popovers, Explore 1 label-on-trace collisions, and empty regions (Explore 1d, Library 5, chain 1c and 6 detail panels).
- **Why it matters** — As F15; the sweep fixed Models 3, Library 4, Review's labels and Settings' "differs" dots, but not these.
- **Source** — `prototyping/UI_REVIEW_BACKLOG.md` B29 and "Sweep fixes applied".
- **Status** — `ticketable now`

### F17 — Family colours still on the old hues
- **Question** — Move the remaining family colours to the canon palette in Review (nearest-families sparklines, F-03 pill dot), Discovery and Analyse.
- **Why it matters** — D8 took the family palette off semantic hues; stale hues in the reference pages would carry red and green families into the build.
- **Source** — `prototyping/UI_REVIEW_BACKLOG.md` "Sweep fixes applied" › Library "Follow-up, cross-file"; D8.
- **Status** — `ticketable now`

### F18 — Missing algorithm glyphs
- **Question** — Draw the missing glyphs in chain frame 6b's registry: Span dedupe, Top-k pairs, Peak picker, Spike shape.
- **Why it matters** — Glyphs identify blocks in the insert modal, Discovery's template picker and Library template cards (B9); a block without one has no card identity.
- **Source** — `prototyping/UI_REVIEW_BACKLOG.md` "Sweep fixes applied" › Analyse › Chain "Not done (optional)"; B9.
- **Status** — `ticketable now`

### PRD departures to confirm (frontend)

Source for all: `prototyping/UI_FUNCTIONAL_SPEC.md` §12 (row named).

- **F19 — P1: the chain page is vertical rows**
  - **Question** — Confirm each row carries its block's result plot, with the horizontal ribbon kept only for moving between block pages.
  - **Why it matters** — Overrides PRD Part 2 "Chain shape, revised" (horizontal canvas plus filmstrip), the very passage `CLAUDE.md` warns supersedes Part 1's vertical list; the prototype and `webui/` already follow P1.
  - **Source** — §12 P1; `CLAUDE.md` "What this repo is".
  - **Status** — `ticketable now`
- **F20 — P2: run history is a pop-up**
  - **Question** — Confirm run history sits behind a History button beside Import, with *Apply to source* disabled (with the reason) when the source type does not fit.
  - **Why it matters** — Overrides Part 2 stories 29–32 (collapsible sidebar).
  - **Source** — §12 P2.
  - **Status** — `ticketable now`
- **F21 — P5: block pages show process, chain rows show result**
  - **Question** — Confirm a block page shows internals (for SAX: signal + PAA, slope + cutlines, quantised and dSAX strips) and its chain row shows only the output.
  - **Why it matters** — Overrides Part 2 story 14's focus mode; shapes F3.
  - **Source** — §12 P5.
  - **Status** — `ticketable now`
- **F22 — P8: show-all views cap at about ten**
  - **Question** — Confirm strips slide with navigation and overlays draw a seeded random sample with *resample*.
  - **Why it matters** — New relative to the PRD; families run to hundreds of members, and it bounds what renderers must draw (F10).
  - **Source** — §12 P8; `prototyping/UI_REVIEW_BACKLOG.md` "Design rules agreed".
  - **Status** — `ticketable now`
- **F23 — P9: explanatory text behind info icons**
  - **Question** — Confirm explanations move into info icons and pop-overs, with plain-language captions kept to one line.
  - **Why it matters** — Overrides §3 "plain-language captions are load-bearing".
  - **Source** — §12 P9.
  - **Status** — `ticketable now`
- **F24 — P14: Models is a sixth workspace**
  - **Question** — Confirm Explore · Analyse · Discovery · Models · Review · Library, with Models launching training from Analyse templates, holding results and nulls, and keeping the registry.
  - **Why it matters** — Overrides §2's five workspaces and the decisions doc's rationale; fixes the nav rail every shell page builds.
  - **Source** — §12 P14.
  - **Status** — `ticketable now`
- **F25 — P23: Settings in project and personal scopes**
  - **Question** — Confirm Settings as sixteen pages in two scopes (project, recorded with runs; personal, this browser), per-workspace local limits (Analyse 20 min, Discovery 20 min, Models 2 h), several clusters, a timed event log, rule-based recommended values, and an append-only audit log.
  - **Why it matters** — Overrides §9's first draft (one ceiling, one surrogate setting, one SLURM template); "project" settings must enter run provenance, so it touches the core.
  - **Source** — §12 P23.
  - **Status** — `ticketable now`

### Found while building the page shells (2026-09-16)

Fog recorded by the builders of the ten workspace units in `webui/pages/fog/<unit>.md` (explore, analyse, review, library, discovery, models, jobs, interrogation, training, settings) while turning the concept frames in `prototyping/imgs/` into fixture-backed page shells, merged and deduplicated here; the raw notes stay in those files. Numbering continues from F26 because F19–F25 are the PRD-departure bullets above. A fourth status, `decided`, marks a question the builder had to answer to ship the shell: the decision is stated in the Question line and stands until the researcher confirms or reverses it. Frame ids are the `.pen` page names (`chain-1e`, `review-7`); "inventory" is the unit's `webui/pages/inventory/*.md`; "canon" is the fixture canon (`webui/client/src/fixtures/canon.ts`, spec §0); "spec" is `prototyping/UI_FUNCTIONAL_SPEC.md`.

#### Canon versus live data

### F26 — Canon channel ids versus live ids
- **Question** — Live `/api/recordings` numbers M2_aug fs1 1–16, fs2 17–32, `M2_concat_fs1` 33–48 and M4 49–64, while the fixture canon puts M3_jul at 33–40 and L_LM at 41–45 in the same range; which id space do routes such as `#/explore/signal/<id>` carry, and how does a page know which mode it is in?
- **Why it matters** — `/4` and `/52` open the same channel in both modes but ids 33–48 mean different recordings, so a deep link from a demo page into a live page can open the wrong channel, and every hand-off that carries a channel id inherits the ambiguity.
- **Source** — `webui/pages/fog/explore.md` (canon channel ids vs live ids); inventory `webui/pages/inventory/explore.md` F1; spec §0.
- **Status** — `ticketable now`

### F27 — Live recordings are not the canon
- **Question** — The live bridge serves six files (`M2_concat_fs1.mat`, `Fig2A_dt0p1.csv`, `Mushroom_…`, M4 included) with no `fs_source` field, while the canon has five recordings with `read` / `inferred` rates; does the bridge gain the canon's recording list and an `fs_source`, or do the pages keep two recording sets?
- **Why it matters** — Frame explore-1b's amber `fs inferred` / `10 Hz?` row can never appear live, the pager reads `1 / 6` against the frame's `1 / 5`, and every fs-dependent conversion (C18) has no live source of truth for whether a rate was read or guessed.
- **Source** — `webui/pages/fog/explore.md` (live recordings are not the canon; pager counts); frames explore-1, explore-1b; spec §0; see C18, C19.
- **Status** — `ticketable now`

### F28 — Filters the live database cannot answer
- **Question** — The Corpus rail's morphology-tag filter, its runs / method filter and the drawer's element, quality, structure, status, spike-train length, method, adjudication and nearest-family filters all rely on dimensions the live coverage payload and annotation rows do not carry. The shell enables the tag filter on demo counts (it re-dims rows and changes the readout, not the cell shades), labels the run / method chips "demo only — the live map counts every run", disables the drawer filters with "not in this database", and ticks only `seed` and `interesting` by default where the previous live default was all five verdicts. Which dimensions does the bridge grow, and which stay demo-only?
- **Why it matters** — A user can believe the map is filtered when it is not unless they read the note; the first Corpus screen now shows fewer spans than before; and the drawer is much thinner live than in the frames, which a critic reads as missing features rather than missing data.
- **Source** — `webui/pages/fog/explore.md` (morphology tags; runs / method filter; default verdict ticks; drawer on live channels); inventory explore F2/F5, F9; frame explore-1; spec §5.1.
- **Status** — `fog`

### F29 — One page mixing live and demo numbers
- **Question** — On the canon channel (live CH4_A2 has 0 detections) the header reads the live `0 detections` while the density ribbons and drawer count demo detections from checked runs; the drawer's annotation rows are demo canon at other times than the live annotations drawn in the span tier, so clicking a row centres the signal where no band is drawn; and no picker state produces the frame's `6 runs · 4 methods` (the chip reads checked runs · distinct methods, `3 of 6 runs · 3 methods`). May a page mix the two sources, and if so how is each number labelled?
- **Why it matters** — Two numbers on one page disagree and a row and its plot can disagree; until families and detections exist live the frames' picture cannot be honest, and a shell that hides the mixing hardens it (A6).
- **Source** — `webui/pages/fog/explore.md` (density ribbon; drawer rows vs span tier; picker chip copy); frames explore-2, explore-2b; inventory explore conflict 5 / F8.
- **Status** — `fog`

### F30 — The B24 detection chain runs only as demo blocks (A4 continued)
- **Question** — `Encoding` is terminal in the registry and the noise floor is a control inside the dSAX adapter, not a block, so the web UI shows the canonical chain as `demo.*` blocks with simulated runs while the live chain stays detrend → matrix profile → threshold; Discovery frame 3b additionally labels Drop detection `Signal → SpanSet` where the canon says `Encoding → SpanSet`, and its noise-floor numbers (`σ 0.0096`, `cut ±0.077`) carry no units (the shell uses the canon signature and adds mV). Until A4 is decided, what does a demo block promise that a live one does not, and how is the difference visible?
- **Why it matters** — The headline chain of Analyse, Discovery compare and the Library's templates is a simulation on every page; a reviewer cannot tell a simulated run from a cached one without reading the block id.
- **Source** — `webui/pages/fog/analyse.md` (the B24 detection chain cannot run in the core); `webui/pages/fog/discovery.md` F25; frames chain-1…1f, chain-3/4/6, discovery-3b; spec §0, §3, §6.5 B24; `ui-prototypes/REPORT.md` §5 D-A1; see A4.
- **Status** — `fog`

### F31 — Frame timescales impossible at 1 Hz
- **Question** — Chain frames 1/3/4 draw 0.2 s segments and 1.1–1.7 s drops, and interrogation frames 2/2b/2c draw 0.7–1.1 s falls, a 3-sample steepest window and −1 s … +2 s anatomy axes, on `M2_aug fs1` at 1 Hz, where a 1 s fall is one sample. The chain demo keeps the frame numbers on a 50 s span at a finer synthetic resolution; interrogation applies the inventory's mechanical rule (frame times ×10, slopes ÷10) so angles, depths and shapes stay as drawn and only the tick labels move. Which numbers are believed, and what does a real encoding block need (fs ≥ 5 Hz, or segments ≥ 1 s)?
- **Why it matters** — Every number on the interrogation pages is downstream of this and needs confirming against a real F-03 measurement; the segment sizes decide whether the designed chain can run on the 1 Hz recordings at all.
- **Source** — `webui/pages/fog/analyse.md` (sub-second segments on a 1 Hz recording); `webui/pages/fog/interrogation.md` (the frames' timescale cannot exist at 1 Hz); frames chain-1, chain-3, chain-4, interrogation-2/2b/2c; spec §0.
- **Status** — `ticketable now`

### F32 — Rows, ids and counts the canon does not carry
- **Question** — Jobs invents `a-0101`, `l-0009` and seven finished-or-cancelled rows to make its groups non-empty; interrogation frame 1b names `F-11 biphasic` and `F-12 burst` where the canon has `F-04 spike train` and `F-11 burst` (built with the canon's ids); the Models frame shows `rf_windows_v1 · manual` used by a template the canon lists nowhere (canon wins, so that row demonstrates Retire); `mp_drops_v3` is not among §0's named templates; the canon gives F-11 `members: null` where Review prints the frame's 17 from a local fixture and the Library shows a size too; and "4 review queues · 1 idle" never says which is idle (the shell picks q-18, the only one with no pace). Does the canon grow these rows and counts, or do units keep minting them?
- **Why it matters** — Ids are each page's primary key and `?sel=` deep links use them, so two units minting in one range collide; a family's size shown in Review and the Library must agree.
- **Source** — `webui/pages/fog/jobs.md` (rows §0 does not name; which queue is idle); `webui/pages/fog/interrogation.md` (frame 1b families); `webui/pages/fog/models.md` (registry rows); `webui/pages/fog/library.md` (templates: `mp_drops_v3`); `webui/pages/fog/review.md` (F-11 member count); frames jobs-1, interrogation-1b, models-5, review-1; spec §0.
- **Status** — `ticketable now`

### F33 — 45.2 h versus 721 h for M2_aug fs1
- **Question** — The frames give M2_aug fs1 45.2 h (the Library recurrence caption, Jobs-2's "162,600 samples each (45.2 h at 1 Hz, less m)" and its stage card, the Settings event timeline drawn 0–45 h) while §0 gives 721 h (Jobs-3's "2,595,481 samples per channel" for the same run, and the shells' choice everywhere). Which is right, and what did the 45.2 h frames mean — a channel subset, a span, or a placeholder?
- **Why it matters** — Jobs' two sample counts for one run mean one of the paused-run checks is checking the wrong scope, and that check protects the recipe; at 721 h the four canon events cluster in the first 6 % of the Settings timeline, legible but not what the frame shows.
- **Source** — `webui/pages/fog/library.md` (recurrence: M2_aug fs1 caption); `webui/pages/fog/jobs.md` (sample counts; scope 45.2 h vs 721 h); `webui/pages/fog/settings.md` FE10; frames library-1, jobs-2, jobs-3, settings event timeline; spec §0.
- **Status** — `ticketable now`

### F34 — Held-out M4 across workspaces: refusal states no frame draws, and the lock's commit
- **Question** — No frame shows a refusal for `M4_aug`, so each shell invented one: Review's api refuses any M4 item with the D6 reason and "New queue" lists `M4_aug · held out` disabled; Jobs adds a `held-out` file to the upload picker with a refusal naming D6; the Library recurrence draws M4 as a locked block; Explore invents member `m-0917` to reach span edit's held-out state; interrogation frame 1b's "F-07 · 5 recordings" can only be true if F-07 draws on M4 (built as 4). Settings builds the lock so the typed-name unlock modal *is* the commit (immediate, writing an audit entry) while turning the lock **on** goes through the save bar, so a Discard can never silently undo a logged act. Is the refusal one shared sentence, and is the unlock's immediate commit right?
- **Why it matters** — D6 is the evaluation-protection rule (O6); five refusal texts and an unconfirmed commit model for the one logged act in Settings are how a lock erodes.
- **Source** — `webui/pages/fog/review.md` (held-out M4_aug in Review); `webui/pages/fog/jobs.md` (a held-out upload); `webui/pages/fog/library.md` (recurrence: recordings 4–5 of 5); `webui/pages/fog/explore.md` (held-out member id); `webui/pages/fog/interrogation.md` (F-07 recordings); `webui/pages/fog/settings.md` FE1; spec §0 D6, §9, §12 P19.
- **Status** — `fog`

#### Cross-workspace hand-offs and shared demo writes

### F35 — Creating a Review queue from another workspace
- **Question** — Explore's *Review this motif* / *Take span for Review*, interrogation's *Stage 1 outlier for Review*, training's *Send N unseen windows* and the Models registry's *Add 20 more* verifications all write `recordDemoWrite('review', 'add-queue', …)`. Explore's spans land in an "Explore spans" queue with no canon id (Review proposes `q-16`, which Jobs' frame does not list), and a one-span interrogation outlier is a fourth source kind P20 does not name. What are the id, source kind and shape of a queue another workspace creates, and does Jobs' "4 review queues" count them?
- **Why it matters** — Review cannot show where a hand-off went; the header chip and the Jobs queue group disagree with Review the moment q-16 ships; and P20's one-source-per-queue rule is what the human write path (C7, A31) rests on.
- **Source** — `webui/pages/fog/explore.md` (Review this motif / Take span for Review queue); `webui/pages/fog/review.md` (Explore spans queue q-16); `webui/pages/fog/interrogation.md` (Stage 1 outlier for Review); `webui/pages/fog/models.md` (registry: verification progress); `webui/pages/fog/jobs.md` (which queue is idle); inventory explore F13, review-jobs F1/F12; spec §10.1, §12 P20; `webui/client/src/kit/README.md` cross-workspace demo writes contract.
- **Status** — `ticketable now`

### F36 — Creating a job from Analyse, Discovery or Models
- **Question** — *Create SLURM script* in Analyse (chain-1g), Discovery and Models must make a job appear in Jobs (P24). There is no shared jobs store key, so the shells write `recordDemoWrite('jobs', 'add-job', …)` (Analyse also `setDemo('analyse.hpcJobs', …)`), which gives the added job no estimate, profile or script of its own (Jobs fills in "not calibrated yet · from the stage estimate" and a generic script); Discovery's toolbar reads `for 1` (only the pending run) against the frame's `for 2`; Models writes the window set to the Library at script creation rather than when results are imported, and links `#/jobs?kind=cluster` with a filter parameter Jobs owns. What does a created job carry, and which side owns its estimate, profile, script and the window set it implies?
- **Why it matters** — The count is the promise of how many jobs get created; a job with no script of its own cannot be re-submitted; and write-at-creation decides when a window set becomes a Library artifact (A12).
- **Source** — `webui/pages/fog/analyse.md` (jobs store contract for an HPC job created in Analyse); `webui/pages/fog/jobs.md` (cross-workspace); `webui/pages/fog/discovery.md` F1; `webui/pages/fog/models.md` (Create SLURM script; open in Jobs); `webui/pages/requests/analyse.md`; frames chain-1g, discovery-1, models-1; spec §6.9, §7.5, §7b.1, §12 P24; kit README cross-workspace demo writes contract.
- **Status** — `ticketable now`

### F37 — A shared `FamilyMember` type
- **Question** — Library › Family, Review's cluster strips and interrogation all need `{ id, family, recording, channel, onset_h, d, verdict, fs_hz, trace }`; the inventory proposes it for the canon, and interrogation works around it with an `InterrogationMember` that extends the shape with slope features. Does the canon own the type?
- **Why it matters** — Three units drawing the same member from three local shapes is how member counts, verdict colours and distances drift between Library, Review and Analyse.
- **Source** — `webui/pages/requests/interrogation.md` item 11 (raised in the unit's requests file rather than its fog file); `webui/pages/fog/review.md` (F-11 member count).
- **Status** — `ticketable now`

### F38 — Hand-offs whose entry another unit owns or no frame draws
- **Question** — Interrogation's toolbar reads "arrived via Analyse events" but the live chain page's button is disabled ("out of slice scope") and owned by the chain unit, so the only way onto the page is the URL or the nav; training offers "Both, paired" as a label source whose own description says it runs in Models (built selectable with a blue callout carrying the Models hand-off); Jobs' "Start a new run with m = 60 s" on a rejected upload would have to open Discovery or Analyse with the template pre-filled from the rejected file's metadata, a flow no frame draws (not wired). Which side wires each, with what payload?
- **Why it matters** — A control that cannot act where it sits is a dead click by the brief's standard, and the rejected-file re-run is the likeliest real path out of a failed cluster job.
- **Source** — `webui/pages/fog/interrogation.md` (who owns "Analyse events"); `webui/pages/fog/training.md` item 8; `webui/pages/fog/jobs.md` ("Start a new run with m = 60 s"); frames interrogation-1, training-4, jobs-3; spec §12 P11.
- **Status** — `fog`

### F39 — Verification progress flowing back from Review to the Models registry
- **Question** — How does verification progress in queue q-19 reach the registry's gate? The page offers "simulate the last N judgements", and *Add 20 more* writes a queue entry; nothing carries a verdict back.
- **Why it matters** — Registration requires human verification and sign-off (A30); without the return path the gate can never open on real data.
- **Source** — `webui/pages/fog/models.md` (registry: how verification progress flows back from Review); frame models-5; spec §7b.5, §12 P19.
- **Status** — `fog`

#### Shared-kit gaps the builders worked around

### F40 — Header chips and the header search pill
- **Question** — `DEMO_NEED_YOU = 3` is a constant the header chip adds to the live count, while Jobs derives its own "N need you" from its rows (paused waiting + result arrived + overdue cluster job = 3 today); the two diverge the moment a demo write adds a fourth, such as a manifest waiting to import, which §7c.1 counts as needs-you. Jobs' `Manifest inbox · 1` counts imported manifests, not waiting ones, so it reads like a badge for attention when nothing needs doing. The frames also draw `Search settings  Ctrl K` in the shared header, but `webui/client/src/shell/Header.tsx` hard-wires that pill to a not-wired toast, so Settings intercepts the click in a capture-phase listener and binds Ctrl K itself. Does the header derive its chips from the workspaces' stores and expose an `onSearch` prop?
- **Why it matters** — The chips are the designed cross-workspace needs-you set (F9), and a capture-phase intercept on shared chrome breaks silently when the header changes.
- **Source** — `webui/pages/fog/jobs.md` (`DEMO_NEED_YOU`; "1 imported"); `webui/pages/fog/settings.md` FE4; `webui/pages/requests/settings.md`; frames jobs-1, settings header; spec §7c.1; see F9.
- **Status** — `ticketable now`

### F41 — The leave guard only guards the settings nav
- **Question** — Clicking another settings page with unsaved edits opens the guard modal, but the workspace nav rail and the browser back button do not, because the kit's `NavRail` is shared chrome the unit does not own and `beforeunload` cannot look like the frame's modal. Does the rail gain a leave hook?
- **Why it matters** — An unsaved project setting lost on a rail click is the failure the save bar exists to prevent.
- **Source** — `webui/pages/fog/settings.md` FE3; `webui/pages/requests/settings.md`; spec §9.
- **Status** — `ticketable now`

### F42 — One badge, two facts: `on cluster · cached`
- **Question** — Training frame 0's 02 row reads `on cluster · cached` — where it ran, and whether the result is reusable — but the kit `Badge` takes one status; the shell shows `on cluster` on the row (the stronger fact) and `cached` in the block page's compute card. Does the state model (F2) separate location from reusability?
- **Why it matters** — The ribbon badge is how a user sees what will re-run; hiding `cached` behind the block page makes a trial's cost unreadable from the chain.
- **Source** — `webui/pages/fog/training.md` item 5; frame training-0; spec §0 badge words; see F2.
- **Status** — `ticketable now`

### F43 — A shared multi-track time plot
- **Question** — Seed search's distance profile (signal · distance · matches) and Compare's *where A and B fire* (signal · A · B · agreement) both need a stack of tracks on one hour axis with one hover crosshair and one tooltip; the kit's `Trace` draws one series with its own padding, so both Discovery pages hand-roll an SVG to keep the tracks aligned. Does `kit/plots.tsx` gain a `tracks` prop or a `TrackedTrace`?
- **Why it matters** — Two builders re-implementing the same crosshair is how the two drift apart.
- **Source** — `webui/pages/requests/discovery.md` (raised in the unit's requests file rather than its fog file); spec §7.6, §7.7.
- **Status** — `ticketable now`

### F44 — Page registry versus frames
- **Question** — Decided for the shell: frame review-7 (batch undone) draws the cluster page though the registry lists it under `review.inspector`, so it renders at the cluster route (`#/review/queue/q-15/cluster/12?state=undone`) and sits in the smoke manifest under both pages; the frames print "Review | Inspector" on the cluster page where the registry titles are "Queue" and "Cluster", and the shell follows the frames; Library grouping is prescribed as a route while frame 4 is a modal over the atlas, so the route renders the page named by `?from=` behind the modal. Which is each page's name, and is a modal-over-page a route?
- **Why it matters** — Critics compare frames per page, and the smoke manifest is the gate's list of what must paint.
- **Source** — `webui/pages/fog/review.md` (frame review-7; header label); `webui/pages/fog/library.md` (grouping: route vs modal); `webui/client/src/shell/pages.ts`; frames review-1…7, library-4.
- **Status** — `decided`

#### Plot, axis and colour conventions

### F45 — Time formats per span (F1 continued)
- **Question** — The builders hit F1 at every scale: a 50 s chain span in hours reads "192.4000 h … 192.4139 h" where the frames print "825 s … 875 s" (which wins below ~20 min — hours with four decimals, or seconds since span start with the start hour in the chip?); Review prints two decimals above 450 s of context span and three below, unspecified; Explore's span-edit fields show `148.6019 h · #534,967` against the frame's clock `148:36:07`; Discovery's seed provenance reads `825–846 s` where the shell shows `0.23 h · 21 s` and keeps the sample count; chain frame 7b lists spans at 16.21 h and 20.10 h on a 6–12 h span with "9.15 h" as a duration (the demo keeps spans inside the span with durations in s). One rule is needed for axis decimals, short spans, durations and sample counts.
- **Why it matters** — A second time convention on one page is how a reader mis-reads an hour for a second; a sample index is how Explore finds a span; every hand-off carries the convention.
- **Source** — `webui/pages/fog/analyse.md` (time axis for a 50 s span; threshold 7b table); `webui/pages/fog/review.md` (context time axis); `webui/pages/fog/explore.md` (span edit time format); `webui/pages/fog/discovery.md` F13; frames chain-1, chain-7b, review-1, review-5, discovery-2; inventory explore conflict 1; spec §0; `ui-prototypes/REPORT.md` §5 D-A7; see F1.
- **Status** — `ticketable now`

### F46 — One never-normalised mV scale (D5) across cards, overlays and live traces
- **Question** — Library card axes read ±0.4 mV but four families are deeper (F-05 +0.65, F-08 −0.52, F-09 +0.48, F-02 ±0.45), so the shell computes one domain (±0.7 mV) for every card, rail plot, overlay and sparkline; in Explore the synthetic F-03 medoid (~0.34 mV deep) drawn over a live CH4_A2 motif window (~0.02 mV) squashes the live trace, so the overlay defaults off where the frame draws it on. How does a shared, never-normalised scale hold when families and live traces differ by 20×?
- **Why it matters** — D5 forbids normalising waveforms; on the frame either the tick label or the depths are wrong, and the frame's overlay cannot be honest with live data until families exist.
- **Source** — `webui/pages/fog/library.md` (atlas: card axes); `webui/pages/fog/explore.md` (medoid overlay on a live trace); frames library-2, explore-2; spec §3 D5.
- **Status** — `fog`

### F47 — Seed verdict colour: frames blue, canon green
- **Question** — Decided: the pages follow the canon (commit 6681ae3), which makes `seed` green as a human verdict under §3, where frames explore-1/2b and the interrogation legend draw it blue; interrogation uses two greens (seed darker), amber and red. The frames need redrawing.
- **Why it matters** — A blue dot on a member tile reads as "machine picked this".
- **Source** — `webui/pages/fog/explore.md` (seed colour); `webui/pages/fog/interrogation.md` (the frame draws the `seed` verdict blue); frames explore-1, explore-2b, interrogation-1; spec §3; see F17.
- **Status** — `decided`

### F48 — Categorical palettes the §3 semantics do not provide
- **Question** — §3 assigns meanings to blue / green / amber / red / purple, but the shells need colours that mean only "a different one": Discovery run stripes (seed_E0102_bank's rose is close to the reserved red; the shell uses a non-semantic #E2557E), six training cluster classes (built on a separate categorical ramp, status colours kept for badges and bands), interrogation feature histograms (frame 3 colours the max-slope histogram red; built blue / purple / teal) and Explore's cross-channel bins (green for independent, amber for propagation; kept as drawn and flagged). Does §3 gain a run palette and a categorical ramp distinct from verdict and family colours (D8)?
- **Why it matters** — A red class reads as "failed" and a green one as "human" to anyone who learnt §3; a red distribution reads as artifacts.
- **Source** — `webui/pages/fog/discovery.md` F6; `webui/pages/fog/training.md` item 4; `webui/pages/fog/interrogation.md` (frame 3 colours the max-slope histogram red); `webui/pages/fog/explore.md` (cross-channel colours); inventory explore conflict 2; frames discovery-1, training-2/3, interrogation-3; spec §3; see F17.
- **Status** — `ticketable now`

### F49 — Channel subsets in multi-channel views
- **Question** — Review's "Other channels" shows six rows per page with a pager `1–6 of 16`, opening on the page holding the item's channel; the Library recurrence cannot fit a 16-channel recording three per page (the frame draws 6 / 4 / 5 channels; the shell draws the first N with a `+10 ch` caption and no expander). Which channels are shown, in what order, and how are the rest reached?
- **Why it matters** — A hidden channel in a recurrence matrix is a member nobody sees, and the order decides what "nearest" means.
- **Source** — `webui/pages/fog/review.md` (other channels); `webui/pages/fog/library.md` (recurrence: 16-channel recordings); inventory review-jobs F7; frames review-1b, library-1; spec §8.4.
- **Status** — `fog`

### F50 — Fixture times are strings, not timestamps
- **Question** — Review's "4 s ago" / "1 min ago" previous lines and Jobs' "running for 3.3 h" / "since 11:40 / 2 h" are frame copy that never ticks (session writes do), so the 3× overdue rule is evaluated against a frozen number. Do fixtures carry timestamps so a page can age its own rows?
- **Why it matters** — A static "4 s ago" reads as live, and the overdue reminder is the one place the interface promises to notice time passing.
- **Source** — `webui/pages/fog/review.md` (relative times in fixture "previous" lines); `webui/pages/fog/jobs.md` (wall-clock strings, not timestamps); frames review-1, review-2, jobs-1; spec §0 Jobs.
- **Status** — `ticketable now`

#### Route, state and deep-link model

### F51 — Block index base differs between chains
- **Question** — `#/analyse/block/<i>` is 0-based (`block/1` = 02 Matrix profile; the smoke flows address it so), while `#/analyse/interrogation/block/<n>` and `#/analyse/training/block/<n>` are 1-based so the route matches the printed stage number. One workspace, two bases.
- **Why it matters** — A trap for deep links written by hand, and the dispatcher's asymmetry reads as a bug.
- **Source** — `webui/pages/fog/analyse.md` (block index in the URL); `webui/pages/fog/interrogation.md` (block index base); `webui/pages/fog/training.md` item 10; `webui/client/src/shell/pages.ts`; `webui/smoke.py` analyse flow.
- **Status** — `ticketable now`

### F52 — Ordinal deep links re-number
- **Question** — `?motif=233` walks the merged list (live annotations + live detections + demo detections from checked runs), so 233 lands on whatever is 233rd, not the frame's fixture motif at 277.312 h, and the list re-numbers when the picker changes; `?window=motif-<n>` on the cross-channel page only relabels the window (the fixture traces are always MOTIF_233). Should deep links carry stable ids rather than ordinals?
- **Why it matters** — A shared URL can open a different motif after a picker change, and entering cross-channel from another motif shows the wrong waveform under the right label.
- **Source** — `webui/pages/fog/explore.md` (`?motif=233`; cross-channel window from Signal); inventory explore F6; frame explore-2; spec §5.4.
- **Status** — `ticketable now`

### F53 — Deep-link parameters one unit owns and another uses
- **Question** — Models links `#/jobs?kind=cluster` with a filter parameter Jobs owns; Settings search navigates to `#/settings/<slug>?focus=<slugified field>` and pulses only fields that carry an id (a hit on an un-idded field navigates but does not pulse; ranking has no spec); Library derives its empty state from `?library=empty`, carried by the empty page's own links rather than a session-sticky flag; Jobs seeds `?state=arrived` and Settings `?state=unsaved`. Is there one registry of query parameters, and who owns each?
- **Why it matters** — A parameter renamed by its owner silently breaks another workspace's link, and the smoke manifest addresses pages by these.
- **Source** — `webui/pages/fog/models.md` (the "open in Jobs" filter parameter); `webui/pages/fog/settings.md` FE5, FE8; `webui/pages/fog/library.md` (import: the empty library); `webui/pages/fog/jobs.md` (two "result arrived" states); inventory settings F2.
- **Status** — `fog`

### F54 — Analyse chain editing semantics
- **Question** — Frame 1e keeps "04 Drop detection" after 03 is deleted while the demo renumbers (stable numbers until the next save, or live renumbering?); frame 6 (02 Noise floor) says "cut k 8 σ = chosen in 03's sweep" while frame 3 (03 Encoding) carries "noise floor 8 σ" in its parameters, so the demo stores k on 03 and lets 02's slider edit it (02 stays cached, 03 → 04 go stale); run history enables *Apply to source* on a surrogate run (#129), which would apply the surrogate generator as a block; and the interrogation ribbon offers `+ stage` although §6.4's type-contract modal is not specified for a chain whose terminal is Features (built as a swap between slope and spike shape, FitzHugh–Nagumo disabled).
- **Why it matters** — Renumbering changes which stage a deep link and a history row name; parameter ownership decides which rows go stale (F2); applying a surrogate recipe to a real span is a silent analysis error; two feature blocks into one Aggregate breaks P7.
- **Source** — `webui/pages/fog/analyse.md` (stage numbering after a delete; where the noise-floor multiplier lives; run history "Apply to source" for a surrogate run); `webui/pages/fog/interrogation.md` (`+ stage` on an interrogation chain); frames chain-1b, chain-1e, chain-3, chain-6, interrogation-1; spec §6.4, §6.5 B24, §12 P7.
- **Status** — `fog`

#### Persistence of settings, drafts and personal preferences

### F55 — Nothing in the shells survives a reload
- **Question** — Personal settings live in the same in-memory store as project settings (the inventory said `localStorage`); settings drafts survive leaving the workspace but not a reload, and the frames do not say whether a draft should survive leaving; audit entries written this session are prepended in memory, so the log is append-only within a session and resets on reload — the opposite of "kept for the life of the project"; Jobs' "Still running · remind me in 3 h" snooze is in-memory with no scheduler in the core; an imported recording row vanishes on reload; and Display's theme and density write to the personal store and raise "Applied to this browser" while the site has one light theme and one density. Which of these persist in the browser, which in the project (C9), and does the site gain a second theme?
- **Why it matters** — "Writes survive navigation but not a reload" is consistent across the empty frontend but contradicts the inventory and an audit log's purpose; controls honest about what they store and dishonest about what they change are a P23 promise the site cannot keep.
- **Source** — `webui/pages/fog/settings.md` FE2, FE15, FE16, FE19, FE20; `webui/pages/fog/jobs.md` ("Still running · remind me in 3 h"); inventory settings F4; spec §9, §12 P23; see C9.
- **Status** — `fog`

### F56 — Save-bar, reset and default rules the Settings shell invented
- **Question** — Decided for the shell: Save is instant with no `saving` → `saved` spinner (a fake delay would be theatre in a page that writes nothing); with several fields edited the bar shows the consequence of the last field touched, not a joined list; Reset applies immediately on a personal page and stages defaults as unsaved edits on a project page; turning informative off sets a class's `implies` to `artifact` so the Select always has a value; numbers render unformatted (`1`, not `1.00`); a key-binding conflict offers *Keep the old binding* / *Move ⟨key⟩ here*, leaving the loser at `—` with nothing offering to restore it. Each needs the researcher's confirmation.
- **Why it matters** — P23 wants one consequence sentence and a save that enters run provenance; a binding left at `—` is an unreachable shortcut.
- **Source** — `webui/pages/fog/settings.md` FE6, FE7, FE11, FE12, FE13, FE14; frames settings-16 and the save bar; spec §9, §12 P23.
- **Status** — `decided`

### F57 — Values shared between two Settings pages
- **Question** — `seq_gap` / `seq_events` are edited on Review queues and Library groupings; writing one writes the other's draft (`SHARED` in `webui/client/src/settings/store.ts`) so both pages show a save bar, and each then saves its own copy, so saving one does not clear the other's bar. The spec says only "shared with Library sequences": one value with two views, or two values kept equal?
- **Why it matters** — These are the sequence-cluster defaults of A14; two copies that can diverge are two definitions of a sequence.
- **Source** — `webui/pages/fog/settings.md` FE9; spec §9; see A14.
- **Status** — `ticketable now`

#### Numbers the shells had to reconcile

### F58 — Frame arithmetic the shells reconciled (F15 continued)
- **Question** — Beyond F15's list the builders found, and had to pick a side on: Review's c-0343 evidence `samples 51,726 → 51,761` where 192.371 h at 1 Hz is ≈ 692,536 (other items derive samples from hours); Library's family totals (838 members + 38 omitted ≠ 1,402), S-03 `F-02 × 4` × 18 needing 72 F-02 motifs of 42, S-02's ~22 s holding a 21 s sharkfin plus a 14 s gap, "Send 21 unjudged" against judged 23 of 42 (shell: 19), §8.2's 1,188 omitted against the frame's 1,018 (shell: 1,018), m-1850's 1.62 s in a ~21 s family (shell: 21.6 s), `recordings 3 · 5 channels` against 11 channels in recurrence, 0.61/h on CH3_A2 over 721 h ≈ 440 members for a 112-member family (per-hour keeps the frame; count mode sums to the atlas), rail `hours 128.4 h` matching no reading (shell: computed channel-hours), `sequences 350` reconciling only as a motif count, window-set class bars summing to 1,408 of 2,140 (shell: 612 · 568 · 492 · 430 · 38); Discovery's ~0.1 h band for a 40 s window on a 72 s axis (shell: 36 s in 40 s) and runs `5 in this session` against 4; Models' L_LM_Jul26_J CH1 at 92 h against the canon's 22.4 h and `ws_M3jul_8ch_300s` split counts in no frame; interrogation's `n 15` for 16 events across 3 recordings × 4 channels (built per recording × channel, n 12) and frame 2b's table `41–44 of 212` that cannot hold current event 45; training's six classes summing to 343 against 543 windows (rescaled to 260 / 180 / 51 / 32 / 13 / 7); Settings' `?state=unsaved` seed (noise floor 0.12 while the sentence reads `0.08 → 0.10 mV`) and an import footer of 138 MB (channels × samples × 8 B) against the frame's 8.2 GB. Which number is authoritative in each case?
- **Why it matters** — As F15: shells on fixture data copy inconsistent placeholders as though designed, and here the sums are in several cases the headline result (the interval CV, class sizes, recall, the family size).
- **Source** — `webui/pages/fog/review.md` (evidence samples); `webui/pages/fog/library.md` (atlas, family, recurrence, grouping, window sets); `webui/pages/fog/discovery.md` F4, F7; `webui/pages/fog/models.md` (L_LM_Jul26_J row; ws_M3jul split); `webui/pages/fog/interrogation.md` (inter-event interval n; frame 2b's table window); `webui/pages/fog/training.md` item 1; `webui/pages/fog/settings.md` FE8, FE16; inventory settings F3; `prototyping/UI_REVIEW_BACKLOG.md` B28; `prototyping/UI_SWEEP_2026-09-14.md`; see F15, F33.
- **Status** — `ticketable now`

### F59 — Estimates the shells fake (C5 continued)
- **Question** — The Analyse toolbar estimate ("≈ 0.6 s · 03 → 04") does not say whether the 200× surrogate run is included (frame 1d's footer says it is "queued after"; the demo halves the estimate when the surrogate is off); training's trial job derives its stage range and `--from-stage` from the ticked stages while the toolbar keeps frame 4's fixed "trial ≈ 2 h 40", so the two disagree by design; Models scales its local estimate with fixture maths (1.6 h per arm per 3 channels, RF 0.1 h, five model nulls 2.3 h); Library regroups have no local limit in Settings yet preview `~10 min, local` (shell: 20 min, and shape distance on sequences at ~46 min turns Apply into *Create SLURM script*); Jobs shows "1 h · calibrated 12 Sep" locked, and a job that runs 3.3× it feeds nothing back. What is the cost model, and where does calibration live?
- **Why it matters** — Estimates route local versus HPC (A3) and gate training (A30); an estimate and its script that disagree, or a calibration that never updates, are refusals and hours the researcher cannot predict.
- **Source** — `webui/pages/fog/analyse.md` (surrogate cost); `webui/pages/fog/training.md` item 7; `webui/pages/fog/models.md` (how the local estimate scales); `webui/pages/fog/library.md` (grouping: local limit); `webui/pages/fog/jobs.md` (the estimate is calibrated and locked); frames chain-1, chain-1d, training-4, models-1, library-4, jobs-4; spec §0, §6.3, §7b.1, §9.6; see C5.
- **Status** — `fog`

### F60 — Actions with no core write behind them
- **Question** — Settings' `open folder`, `pull`, manifest `import`, `export all`, `Export CSV`, `Export preferences`, `Copy diagnostics`' file, tag `merge`, tag / class `rename` and `Add a rule for a block parameter` raise a not-wired toast naming the call; the Compute & HPC profile cells (partition, nodes, gres, cpus, memory, time, array) render read-only where §9.6 describes inline editing, with only the editor below (environment, working directory, return paths, email) live; training frame 0's *Export run* has no destination, format or frame behind it (built as a toast naming the call). Which of these become core write paths (C7, C9, E4), and in what order?
- **Why it matters** — Each would need a core write that does not exist; a toast is honest today and a dead click the day the page is believed.
- **Source** — `webui/pages/fog/settings.md` FE17, FE18; `webui/pages/fog/training.md` item 6; frames training-0, settings Storage / Export / Channels & events / Compute & HPC; spec §9.6; see A18, E4.
- **Status** — `ticketable now`

#### Explore

### F61 — Cross-channel bins, thresholds and the prop. / ind. chips are undefined
- **Question** — Explore's cross-channel page proposes artifact at r ≥ 0.95 with |lag| < 0.5 s, propagation at r ≥ 0.6, independent below, and no match beyond max lag, on a seeded lag / r table that `computed on whole channel` merely perturbs — nothing about the page is a result; the Library rail's `prop. 4` / `ind. 1` channel chips are defined nowhere (the shell's InfoTip guesses "propagated copy" / "independent occurrence"). What computes and classifies cross-channel relations, and with what thresholds?
- **Why it matters** — The rail claims cross-channel counts without a glossary, and A8 has no core source yet.
- **Source** — `webui/pages/fog/explore.md` (cross-channel bins and thresholds); `webui/pages/fog/library.md` (atlas: `prop.` / `ind.` chips); inventory explore F16/F17; spec §5.4, §8.5; see A8.
- **Status** — `fog`

### F62 — Explore shell decisions awaiting confirmation
- **Question** — Decided for the shell: the drawer replaces the span / motif / action tiers (as frames 2b–2d draw it) rather than overlaying the lower screen as §5.3 says, so the span tier unmounts while it is open; the drawer's default scope is `whole channel` (96 matrix-profile detections in a 2 h span would crowd the span tier; `visible span` still filters honestly); span edit shows rev 2 as `current once saved` until Save; and span edit adds a fourth amber check line for §4.2's rule that an extent edit on the medoid invalidates F-03's distances, which the frame omits.
- **Why it matters** — Spec and frame disagree on each, and the fidelity critic needs to know which won.
- **Source** — `webui/pages/fog/explore.md` (`D` / `Esc` with the drawer; drawer scope default; span edit rev 2 status before save; span edit family staleness); inventory explore conflict 1, §4.2; frames explore-2b…2d, explore-2c; spec §4.2, §5.3; `prototyping/UI_REVIEW_BACKLOG.md` B28.
- **Status** — `decided`

#### Analyse (chain, interrogation, training)

### F63 — Registry size and the three blocks without glyphs (F18 continued)
- **Question** — Chain frame 2 says 21 blocks; frames 1g/1i add Span dedupe and 1h names Top-k motif pairs and Peak picker, so the demo registry has 24, and the glyph registry (6b) shows 21 with no glyph for those three (they draw their signature glyph). Do the three enter the registry and F18's glyph list?
- **Why it matters** — A block without a glyph has no card identity in the insert modal, Discovery's picker or Library template cards.
- **Source** — `webui/pages/fog/analyse.md` (registry size); frames chain-2, chain-1h, chain-6b; see F18.
- **Status** — `ticketable now`

### F64 — Steepest window: samples or seconds
- **Question** — Interrogation's rules say "3 samples", but members of one family sit on recordings at 1, 2 and 10 Hz, so 3 samples is 3 s, 1.5 s or 0.3 s; built as samples, as drawn, with no per-recording note.
- **Why it matters** — A family spanning recordings would be measured with three different windows, and the slope strip is the page's headline feature.
- **Source** — `webui/pages/fog/interrogation.md` (is the steepest window in samples or seconds?); frame interrogation-2 Rules; spec §0 recordings table.
- **Status** — `ticketable now`

### F65 — Interrogation statistics the frames leave undefined
- **Question** — Frame 3's β and null β carry 95 % CIs without saying whether they are OLS-analytic, bootstrapped over members or bootstrapped over the 200 null draws (fixture values only); Parameters says "views only · nothing here is stored", yet switching `interval defined as` or `outliers` changes what the null must be matched to; and the inter-event interval is built per recording × channel with an InfoTip where the frame's `n 15` treats 3 recordings × 4 channels as one sequence — confirm which the thesis wants.
- **Why it matters** — With n = 16 the three CIs differ a lot and P10 makes the CI the load-bearing number; a cached null matched to a different definition silently mis-states p; the interval CV and its null are that card's headline.
- **Source** — `webui/pages/fog/interrogation.md` (inter-event interval n; where do the exponent CIs come from; does the null re-run per view change); frame interrogation-3; spec §12 P10; see A2, A22.
- **Status** — `fog`

### F66 — The blocked split when the source is a window set (A11 continued)
- **Question** — Training frame 0b removes the sliding-windows stage (P15) and with it the stage that creates the split, yet the source's windows may already overlap; Models disables `ws_humanlabel_frame0b` with the reason. The training shell shows the amber B7 callout with a candidate — a split filter over the source windows, blocked by recording and time, gap ≥ one window length, block-edge windows dropped — implemented nowhere.
- **Why it matters** — It decides whether a saved window set can be trained from at all.
- **Source** — `webui/pages/fog/training.md` item 2; `webui/pages/fog/models.md` (how a split applies to a human-annotated window set); frames training-0b, models-1b; `prototyping/UI_REVIEW_BACKLOG.md` B7; spec §6.9, §12 P15; see A11.
- **Status** — `fog`

### F67 — The leakage gap: exact rule and allowed values
- **Question** — Is the gap `≥ window length` or `≥ window length − stride`? With 10 min windows on a 5 min stride a 10 min gap is exactly enough, and the frames show `gap 5 min` as the value before the edit, which leaks by half a window (built as `≥ window length`, the 5 min shown only as the pending edit's "was"); the Models frame's gap select offers no values, so "2 windows" and "0 s" are invented and 0 s fails the P12 check.
- **Why it matters** — The guard is the page's main safety claim (A24).
- **Source** — `webui/pages/fog/training.md` item 3; `webui/pages/fog/models.md` (the frame's "gap" select); frames training-01, models-1; spec §12 P12.
- **Status** — `ticketable now`

### F68 — Training-run states no frame draws
- **Question** — No frame shows a failed training run although a GPU job that dies is the likeliest outcome (built on the chain page only, `?state=failed`, since 05 itself never runs anything), and no frame shows a running training job in Models (built as an indeterminate bar with "results arrive through Jobs › Manifest inbox" and a link into Jobs).
- **Why it matters** — Loud failure is a house rule, and where the run "lives" decides which page reports it.
- **Source** — `webui/pages/fog/training.md` item 9; `webui/pages/fog/models.md` (results: a running training job); frames training-0…4, models-3; spec §7b.2, §12 P24.
- **Status** — `decided`

### F69 — Guarding a training job against mixed sampling rates
- **Question** — `ws_M2aug_fs2_300s` is an fs2 set and nothing guards a training job combining it with fs1 sets (B30); the Models frame gives L_LM_Jul26_J CH1 no disabled reason, so "10 Hz (inferred) · the template's sliding windows expect 1 Hz" is invented. What rule refuses or resamples a mixed-rate window set?
- **Why it matters** — Windows of different sample counts in one matrix are a silent shape error or a silent resample.
- **Source** — `webui/pages/fog/library.md` (window sets: `ws_M2aug_fs2_300s`); `webui/pages/fog/models.md` (L_LM_Jul26_J CH1 row); frames library-6, models-1; `prototyping/UI_REVIEW_BACKLOG.md` B30; spec §0; see C18.
- **Status** — `ticketable now`

#### Review

### F70 — Is the queue rail a small-multiple set under P8?
- **Question** — Frames 1–7 draw ~20 sparkline thumbnails in the collapsed queue rail; P8 caps small multiples at ~10; the shell shows 10 and a "+N" count.
- **Why it matters** — Decides whether the rail is a navigation list exempt from P8 or a small-multiple set bound by it (F22).
- **Source** — `webui/pages/fog/review.md` (P8 cap vs frame rail); frames review-1…7; spec §12 P8; `webui/client/src/kit/README.md`; see F22.
- **Status** — `ticketable now`

### F71 — What S means on a cluster batch
- **Question** — Decided for the shell: S on a batch promotes one exemplar (the member nearest the medoid, c-0371) and marks the other included members interesting, with a toast saying so; §10.4–10.5 are silent.
- **Why it matters** — A batch seed that promoted every member would flood the Library (A32).
- **Source** — `webui/pages/fog/review.md` (what S means on a cluster batch); inventory review-jobs F16; spec §10.4–10.5, §12 P21.
- **Status** — `decided`

### F72 — Blind cluster: are distances and cohesion machine opinion?
- **Question** — §10.6 lists only family affinity as hidden; the shell also masks member distances to the medoid and the cohesion pill until a verdict.
- **Why it matters** — A blind batch that shows d would anchor the verdict (A31).
- **Source** — `webui/pages/fog/review.md` (blind cluster); spec §10.6, §12 P20.
- **Status** — `decided`

### F73 — Verdict-flow mechanics the spec leaves open
- **Question** — Decided for the shell: Ctrl Z undoes the last live write in the queue (not only the item on screen) and navigates to it, a batch undo landing on the cluster with frame 7's banner; a class key on an already-judged item adds the class without advancing, class 9 on a non-artifact verdict switches it to artifact with a toast, and pressing the selected class clears it; re-judging an item reached from the rail advances to the next unjudged unit after it; under the default `unjudged` filter the unit immediately before the current one stays visible and other judged units are hidden; a batch write animates each included member's chip (writing… → verdict, 60 ms stagger) and advances only after the last lands.
- **Why it matters** — §10.3 / §10.5 say "undo" without scope and specify the implied-verdict rule only for an unjudged item; auto-advance after a re-judge could skip the reviewer's place.
- **Source** — `webui/pages/fog/review.md` (undo scope; class key on an already-judged item; auto-advance after re-judging; up next; batch writing); frames review-2, review-3, review-7; spec §10.1, §10.3, §10.5, §12 P21.
- **Status** — `decided`

### F74 — Queue kinds the frames never draw
- **Question** — For the seed-search queue (q-15) the score filter becomes a distance filter and single items carry "match d", but no frame draws a q-15 single item, so what the title-row score pill shows is open; for the training-windows queue (q-18) frame 5's "Previous window, revealed" has no model to reveal (B5), and the shell keeps the card with "no model yet · training windows" and no agree chip.
- **Why it matters** — Two of the four queue kinds have no designed single-item state.
- **Source** — `webui/pages/fog/review.md` (seed-search queue; training-windows queue); frames review-2, review-5; `prototyping/UI_REVIEW_BACKLOG.md` B5.
- **Status** — `fog`

#### Library

### F75 — Groupings beyond shape (A15 continued)
- **Question** — Eight of nine grouping parameter panels are undrawn and B17 says the bases themselves are undefined, so every per-basis control is an extrapolation; what a `spike trains` unit groups by is unknown (Apply disabled, "save it instead"); what the atlas shows for a feature-bin or label grouping (g-09 after Apply, g-01 on first import) is undrawn (shell: an EmptyState naming the grouping with `Switch back to g-07`); the sequence family page behind `Open all 21 sequences →` is undrawn (shell: `#/library/family/S-02` lists the sequence ids); whether Apply clears the filters as well as the scope is unstated (shell: filters kept).
- **Why it matters** — After Apply the user lands on a page no frame draws, and the primary action of frame 2b has no destination.
- **Source** — `webui/pages/fog/library.md` (grouping; atlas: feature-bin or label grouping; sequence family page); frames library-2b, library-4; spec §8.2, §8.6; `prototyping/UI_REVIEW_BACKLOG.md` B17; see A15.
- **Status** — `fog`

### F76 — Hand-edit consequences (A16 continued)
- **Question** — Decided for the shell: members kept past the cut by hand are pinned to the end of page 1 with an InfoTip (distance sort would put m-1850 at d 0.47 on page 12); Undo on an added member removes it (toast offers Redo) rather than restoring a moved member's previous family; Make exemplar leaves the family badged `edges partially stale`, with whether the old seed keeps its `seed` verdict and whether the recipe hash changes still open; the second of "2 added" lives on a later page (m-1971); m-1850's revision annotation is `a-2091`.
- **Why it matters** — §8.6 says only "hand-edit record with Undo", and §4.2's staleness rule has unstated consequences for the family's distances.
- **Source** — `webui/pages/fog/library.md` (family: distance sort; hand edits; undo on an added member; make exemplar; revision annotation id); frame library-3; spec §4.2, §8.6; see A16.
- **Status** — `decided`

### F77 — Recurrence semantics
- **Question** — The shared-ground warning names a family (`share ground for F-03`) although shared ground is channel metadata (per family, or per channel pair?); members found on a channel nobody reviewed (L_LM CH1/CH2) show a value with no marker, so "found but never looked at" is indistinguishable from reviewed; the sequences-unit matrix is undrawn (shell: S-01…S-06 reuse the F-01…F-06 cells); M2_aug fs2 is drawn with checkboxes disabled while fs1 is selected and vice versa (B30).
- **Why it matters** — The matrix is the Library's second axis (G8); an unreviewed cell that looks reviewed is a false ground-truth claim.
- **Source** — `webui/pages/fog/library.md` (recurrence); frame library-1; spec §8.4; Settings › Channels & events; `prototyping/UI_REVIEW_BACKLOG.md` B30.
- **Status** — `fog`

### F78 — Library import edge cases
- **Question** — Frame 5 names bundle `DATA/library_seed/drop_motifs` where the tracked bundle is `drop_motifs5` (shell: `drop_motifs5`); a demo import should yield 410 motifs in g-01 but no fixture exists for it (shell: a toast says the canon catalogue is shown); a dry run on a populated library is undrawn (shell: "410 already in the library · re-import skips", Import disabled "nothing new"); whether provisional durations from an inferred fs block the import or only warn is open (frame 5 warns); which 2 recordings / 7 channels the bundle covers is unstated (shell: M2_aug fs1 CH3_A2, CH4_A2 + L_LM_Jul26_J CH1–CH5).
- **Why it matters** — The importer's inputs are irreplaceable (`DATA/library_seed/` is tracked on purpose; see its provenance note), and a provisional fs in a motif's duration propagates into every grouping (C18).
- **Source** — `webui/pages/fog/library.md` (import); frame library-5; spec §8.7.
- **Status** — `fog`

### F79 — Window-set shelf semantics (A12 continued)
- **Question** — Does Delete remove bounds from disk or archive (§8.8)? Split fractions per row and the split plan's hour ranges are in no spec (shell: frame proportions); *Send unlabelled to Review* above the P13 cap of 20,000 is undrawn (shell: disabled with the cap as reason); the frame shows no version though §0 names `ws_M2aug_3ch_600s` v1 and Models saves v2 (shell: a `v1` chip in row and rail; Models keeps the frame's "v2" name chip beside a `_v2` script flag).
- **Why it matters** — A window set is the artifact Analyse, Models and Review share (A29); its delete and version semantics are its identity.
- **Source** — `webui/pages/fog/library.md` (window sets); `webui/pages/fog/models.md` (the Save-window-set name chip); frames library-6, models-1; spec §0, §8.8, §12 P13; see A12.
- **Status** — `fog`

### F80 — Template card semantics
- **Question** — What `× null` means on a template card (observed / null p95? mean?) is undefined (§4.8); "Latest score" is the most recent run or the widest scope (shell: most recent run); training templates score "jobs" (`1 job`) while the rail header says `run` (shell: `job` for training).
- **Why it matters** — A number without a definition sits on the card that picks a detection template.
- **Source** — `webui/pages/fog/library.md` (templates); frame library-7; spec §4.8, §8.9.
- **Status** — `fog`

#### Discovery

### F81 — One detection-matching rule, and where it is set
- **Question** — d-0412 is "also found by seed_F03_native" in the runs browser but "only A fired" with B's nearest d 3.6 in compare; the shell follows compare (IoU ≥ 0.5) and shows `also found by —` plus a muted near-miss line. The IoU rule is a caption with no way to see or change it (Settings › Analysis defaults is named nowhere on the page), and the pooled recall "0.71 over 14 h" equals CH4_A2 alone, so the shell assumes channels with too few reviewed hours are excluded from pooling.
- **Why it matters** — Every only-A / only-B count, "also found by" and the pooled recall depend on rules the page cannot show, and two rules for one pair of runs is a contradiction on screen.
- **Source** — `webui/pages/fog/discovery.md` F3, F11, F19; frames discovery-1, discovery-3; spec §7.3, §7.7.
- **Status** — `ticketable now`

### F82 — Scope changes with runs in the session
- **Question** — Frame 1c adds CH8_B2 / CH9_C1 / CH11_C2 to a finished run's scope with fires but no scores (the shell generates demo score rows; whether adding a channel should mark runs stale, since they did not run there, is unspecified); changing the recording with runs in the session has no specified consequence (shell: confirm, reset channels to the first three, mark runs stale); 1b draws per-channel checkboxes under "Channels in scope" while §7.5 makes each template one run across all channels (shell: checked and disabled with the reason).
- **Why it matters** — A scoreboard total silently growing with scope is a claim the run never made.
- **Source** — `webui/pages/fog/discovery.md` F8, F9, F12; frames discovery-1b, discovery-1c; spec §7.1, §7.5.
- **Status** — `fog`

### F83 — Run rows, labels and undrawn Discovery surfaces
- **Question** — Decided for the shell: `new · local` means "set up locally, not yet run", not where compute happens (seed_E0102_bank's ≈ 38 min routes to the cluster); "where each run fires" draws only runs with results or running and lists the rest in a one-line "not drawn" foot, with a paused row on the scoreboard; a running run (sharkfin_v2 at 64 %) may be picked for compare and counts what exists; human annotations as a side show `—` for precision and × null and `0 reviewed`, since "only B fired" against a human verdict is a machine miss, not a disagreement; History lists r-0431 / r-0415 / r-0412 / r-0398 with Open, the scope chip scrolls to the Scope card, and the preview result is an inline strip under the Scope header.
- **Why it matters** — A missing row looks like "fires nowhere"; a partial run's "only A" is unfinished work, not a disagreement; the frames do not cover the human-side case although §7.7 allows it.
- **Source** — `webui/pages/fog/discovery.md` F2, F5, F10, F20, F22; frames discovery-1, discovery-3; spec §7.1, §7.2, §7.3, §7.7.
- **Status** — `decided`

### F84 — Seed search: scale bank, locked window and the null's basis
- **Question** — The runs list promises "E-0102 · 3 lengths" while the seed page offers `scale bank none` and says MASS takes one seed — which algorithm runs a scale bank, and whether it is still MASS, is unspecified (shell: the option disabled with "needs a scale-bank algorithm"); `window m` is drawn as an open Select but §7.6 locks it to the exemplar's native length (shell: disabled with a lock and the reason); what the seed histogram's surrogate distribution is computed on (circular shift of the same channel, pooled over channels, per seed) is unstated (shell: one fixture null series for the scope).
- **Why it matters** — "null gives 6" is the number a threshold is chosen against (A2), and an editable-looking control that cannot be edited is a dead click.
- **Source** — `webui/pages/fog/discovery.md` F14, F15, F16; frames discovery-1, discovery-2; spec §7.6; see A2.
- **Status** — `fog`

### F85 — Aligning two chains in compare: contract rows the §6.8 table lacks
- **Question** — Role assignment (which stage is Score / estimate) is assumed to come from the block contract, but §6.8 declares no role per block (shell: maps by glyph); `Seeded search  Signal + exemplar → Scores` has no §6.8 row and B25 calls seeded search a Discovery mode, yet 3b renders it as a stage with a signature (shell: fixtured); §7.7's role order (`Score / estimate` after `Encode`) disagrees with frames 3/3b and the B24 chain order (shell: follows the frames); whether stepping re-runs both chains on the window or reads cached intermediates decides whether stepping is free (shell: simulates a ~1 s re-run).
- **Why it matters** — Without a declared role two chains cannot be aligned at all, and a renderer built from the contract table cannot draw the seeded-search card (F3).
- **Source** — `webui/pages/fog/discovery.md` F18, F21, F23, F24; frames discovery-3, discovery-3b; spec §6.8, §7.7; `prototyping/UI_REVIEW_BACKLOG.md` B25; see F3.
- **Status** — `fog`

### F86 — Template and model versioning, naming and archiving
- **Question** — Saving a Discovery draft as a template: must it have been run first, how are versions numbered, what happens on a name collision (shell: a unique name matching `^[a-z0-9_]{3,40}$`, unrun drafts allowed); Library templates: does archive mean hidden or deleted, and can an archived version be applied from an old run (§8.9); Models registry: what "version" means for an existing name (v2 of cnn_windows_v2 · manual) versus a new registered name (shell: v2 offered disabled, "v1 is not registered yet").
- **Why it matters** — Templates and models are the reproducibility handles (A17); a name collision or an ambiguous version silently reuses the wrong recipe.
- **Source** — `webui/pages/fog/discovery.md` F17; `webui/pages/fog/library.md` (templates: archive semantics); `webui/pages/fog/models.md` (registry: what "version" means); frames discovery-2, library-7, models-5; spec §7.6, §7b.5, §8.9.
- **Status** — `fog`

#### Models

### F87 — Results and compare semantics the Models shell decided
- **Question** — Decided for the shell: the suggested threshold at a target precision other than 0.8 moves the frame's four values deterministically (thr +0.55·Δ, precision +0.95·Δ, recall −1.3·Δ); arm B's calibration is shown on the cluster labels mapped onto manual classes, and a cluster arm's prediction is judged right or wrong through the majority cluster → class mapping (behind an InfoTip); the RF baseline's calibration, epochs and registration-gate cards say "unavailable for the RF baseline" with the reason; a pair that is not paired says "unavailable" for paired difference, agreement, per channel and the step-through; the GASF / RP tiles are computed from the window itself (GASF cos(φi+φj), RP 1−|xi−xj|) where the real ones would come from 04 Image encode's cache; clicking Seg or a 2×2 cell opens the filter at the frame's window (only A 7, only B 1, both wrong 12); the Used-by card shows the selected model's templates, falling back to the blocked model named in the lock note; a rejected model's calibration thresholds are unavailable.
- **Why it matters** — Each is a §3 "nothing claims more than it knows" call the frames did not make, and the mapping rule is the paired comparison's definition (A23).
- **Source** — `webui/pages/fog/models.md` (results; compare; registry); frames models-3, models-4, models-4b, models-5; spec §3, §7b.3, §7b.4, §7b.5.
- **Status** — `decided`

### F88 — Other label-arm kinds
- **Question** — Beyond manual and cluster labels, *Add arm* is unspecified; the popover offers "labels from a window set" as not built.
- **Why it matters** — The paired comparison's arms are the RQ1 design (A23).
- **Source** — `webui/pages/fog/models.md` (other label-arm kinds); inventory discovery-models F19; spec §7b.1.
- **Status** — `fog`

#### Jobs

### F89 — Where a paused run's result is expected, and who notices it arrive
- **Question** — §7c.2 recognises a result "already in its root or in the manifest inbox", but nothing says how often the root is polled or what happens if a file is half-written when the poll runs (*Look again* is the only manual trigger); the expected path `./PROFILES/M2_aug_fs1_CH2-4_1Hz_m120_9b24e1f0.npz` encodes recording, channel range, fs, `m` and the recipe hash by a grammar §9.11 is cited for but does not give, so a non-contiguous channel set (CH2, CH7, CH11) has no drawn form while the upload modal refuses anything placed elsewhere; and the frames draw r-0431 as both "not there yet" (jobs-1) and "result arrived 14:31" (jobs-2, jobs-4), which the shell resolves as `waiting` by default with `?state=arrived` for the jobs-2 deep link.
- **Why it matters** — This is the seam of A3's pause flow: the path grammar and the arrival check are core contracts, and arrival decides whether Continue is enabled.
- **Source** — `webui/pages/fog/jobs.md` (where the result is, and what "arrived" means); frames jobs-1, jobs-2, jobs-3, jobs-4; spec §7c.2, §9.6, §9.11; see A3.
- **Status** — `ticketable now`

### F90 — The result checks: two lists, and a file without null draws
- **Question** — In place (frame 2) the checks are place · recipe hash · one per channel · length · finite · null draws; uploaded (frame 3) they are readable · one per channel · length · finite · parameters · null draws — and P24 names one set. A file with no null draws passes and its null (200 circular shifts, ~25 min) "goes to the cluster" over the 20 min limit, but no new cluster job id is drawn and the run's state while that null is out is undesigned (shell: a demo write and a toast saying so).
- **Why it matters** — The check is the thing that protects the recipe (A3, A34), and the missing null is a second pause on the same run.
- **Source** — `webui/pages/fog/jobs.md` (checks and refusals); frames jobs-2, jobs-3; spec §7c.3, §12 P24; see A3.
- **Status** — `ticketable now`

### F91 — Cluster-job lifecycle
- **Question** — *Mark finished / Mark failed* are drawn only on the overdue reminder though §7c.4 makes them general (shell: a plain "running" note with the same two buttons); marking j-0217 failed does not say what happens to r-0431 waiting on it (the rail still reads "waiting on j-0217"; the only exit is *New SLURM script*); a new script "replaces" the old job (shell: the failed job kept with a `replaced by j-0218 →` link; whether the replacement inherits estimate, profile and calibration is unstated); the cluster job id is an editable field with no validation (SLURM ids are integers, an array job is `4418093_3`) and cannot be queried; cancelling a run cannot cancel its cluster job, which the shell says in the confirm modal and no frame draws.
- **Why it matters** — A failed cluster job is the most likely real path, a job that finished early must not be stuck, and the site cannot see the queue (C14).
- **Source** — `webui/pages/fog/jobs.md` (cluster jobs; cross-workspace: cancelling a run); frames jobs-1, jobs-2, jobs-4; spec §7c.4, §9.6; see C14.
- **Status** — `fog`

### F92 — The manifest inbox and a failed import
- **Question** — The inbox is drawn inside the cluster-job page and, implicitly, as a global `Manifest inbox · 1` button on jobs.all (shell: one component, a drawer on jobs.all and a card on jobs.cluster); import is all-or-nothing and its checks ("test windows identical across arms", "no test window in training") compare against the launch record, but a failed check is undrawn.
- **Why it matters** — The inbox is how training results re-enter the tool (A23, A30); a silent failed import is a lost training run.
- **Source** — `webui/pages/fog/jobs.md` (inbox); frames jobs-1, jobs-4; spec §7c.1, §7c.4.
- **Status** — `fog`

### F93 — "n runs marked stale" is arithmetic on a fixture
- **Question** — Channels & events builds every save-bar consequence itself and the run counts in them come from a five-entry table (`RUNS_ON` in `fixtures/settings.ts`: 3 runs on M2_aug fs1, 2 on fs2, 1 elsewhere; a channel-scoped change costs two thirds of an all-channel one). Which core query gives the real count of runs a recording/channel/span change makes stale?
- **Why it matters** — The number reproduces the frames (3 for the 31.1–31.5 h exclusion, 2 for the CH6_B1 gain) and is otherwise invented; a researcher will read it as a fact about their runs.
- **Source** — `webui/pages/fog/settings.md` FE21 (fix round, 2026-09-21); inventory F7; `prototyping/UI_FUNCTIONAL_SPEC.md` §9.2, §12 P23.
- **Status** — `fog`

### F94 — Channel status and the event log agree by construction, not by derivation
- **Question** — F8 recommends the event be the source of truth and the status cell a projection of it. The shell keeps a `status.<rec>.<ch>` draft value and stages both sides together (setting `bad from` stages the linked electrode event; reading a channel `ok` stages removal of the event that marked it bad), so the two cannot visibly disagree — but the cell is still a stored value. Which one does the core store?
- **Why it matters** — Two stored copies of one fact diverge the first time a write path touches only one of them (an import, a bulk edit, a script).
- **Source** — `webui/pages/fog/settings.md` FE22 (fix round, 2026-09-21); F8 above; `prototyping/UI_FUNCTIONAL_SPEC.md` §9.2.
- **Status** — `ticketable now`

### F95 — Per-channel noise floor and gain have no home in the schema
- **Question** — The excluded-spans count is now derived from live event effects, but `noise_floor` and `gain` per channel remain fixture columns with a draft over them; neither exists in the core schema (F7). Are they recording metadata, channel metadata, or recipe parameters?
- **Why it matters** — Analysis defaults' "the recording's noise floor (Datasets)" rule and the per-channel override both assume a stored value the core does not have.
- **Source** — `webui/pages/fog/settings.md` FE23 (fix round, 2026-09-21); inventory F7; `prototyping/UI_FUNCTIONAL_SPEC.md` §9.1–9.2, §9.5.
- **Status** — `ticketable now`

## Export and reporting

### E1 — The reporting and export surface, and its figure target
- **Question** — What does the reporting and export surface produce (today a folder of manifest + CSV + copied plots, goal G9), and which generations of the `Pipelines/` figure corpus are its visual target?
- **Why it matters** — Producing plots and reports of an analysis is a main downstream goal and was a stack criterion; the `.pen` pages cover only Settings › Export, and choosing the target figures needs the researcher present.
- **Source** — [Map: rebuild the Pipeline GUI interface on a stack chosen by evidence][map] "Not yet specified" bullet 2 and "Constraints settled while charting"; [Identify the visual target from the existing figure corpus][visual-target] (as summarised in the map's "Decisions so far").
- **Status** — `fog`

### E2 — Render path for publication figures
- **Question** — Are publication figures exported from the browser's SVG, or rendered on the Python side from the same serialised per-type payloads (for example with matplotlib), and for which figure kinds does each hold?
- **Why it matters** — SVG is exportable but matplotlib parity was never tested; a server-side path means a second, print implementation of the renderer switch, and `CLAUDE.md` rule 1 forbids matplotlib below `UI/`, so the rule would need restating for `webui/server/`.
- **Source** — `ui-prototypes/REPORT.md` §7 "Plotting" bullet; `docs/adr/0001-web-ui-stack.md` "Plotting approach" (last two sentences); `CLAUDE.md` rule 1.
- **Status** — `ticketable now`

### E3 — The Library atlas density test
- **Question** — Does the chosen stack pass the density test the visual-target ticket set: the Library atlas, about 22 line plots and a histogram on a shared y-scale, rendered interactively and exported as vectors?
- **Why it matters** — It was set as a stack criterion but neither prototype exercised it, and it is the cheapest single piece of evidence for both F10 and E2.
- **Source** — [Map: rebuild the Pipeline GUI interface on a stack chosen by evidence][map] "Decisions so far" (visual target); `ui-prototypes/REPORT.md` §8.2 dense-plot row ("Untested at that density").
- **Status** — `ticketable now`

### E4 — What a run export contains and where it lands
- **Question** — What does *Export run* write, and where, given the prototype writes only JSON (recipe, timings, payloads; no rendered figures) under `runtime/<stamp>/exports/` inside the throwaway runtime?
- **Why it matters** — An export written into a directory with no retention policy (T8) is buried or lost, and export is how the Library's findings leave the tool.
- **Source** — `ui-prototypes/REPORT.md` §1 checklist 7 ("partial"); `prototyping/UI_REVIEW_BACKLOG.md` "Done" › Settings (Export page).
- **Status** — `ticketable now`

### E5 — Vector export from canvas renderers
- **Question** — When a renderer falls back to canvas (F10), how does its export stay vector: a parallel SVG/PDF path, Python-side rendering, or accepting raster for those figures?
- **Why it matters** — Canvas has no vector output, so the escape hatch and the publication-export criterion collide on exactly the densest figures (recurrence, all detections across a recording), which are the likeliest report figures.
- **Source** — `docs/adr/0001-web-ui-stack.md` "Plotting approach" (escape hatch); `ui-prototypes/REPORT.md` §8 "Additional findings" bullet 1; [Map: rebuild the Pipeline GUI interface on a stack chosen by evidence][map] "Constraints settled while charting" (publication-quality static export).
- **Status** — `fog`

## Tooling, tests and safety

### T1 — Make pytest safe against the real DATA
- **Question** — Do tests redirect every write root to a temp directory through fixtures (`STEP_CACHE_ROOT`, `MODEL_ROOT`, the encodings root, `DATA/derived/channels`), or must every worktree get a copied, never junctioned, `DATA/`?
- **Why it matters** — The suite assumes a worktree-local fixture `DATA/`; run through a junction it re-wrote 5 step-cache files, added 5 encoding texts and 4 classifier joblibs, and overwrote an existing joblib in the real data. Writers: `tests/test_step_cache.py`, `tests/test_encoding_view*.py`, the classifier tests, and `tests/test_materialize_channels.py` (writes `DATA/derived/channels/<stem>/`). Root cause shared with C10.
- **Source** — `ui-prototypes/REPORT.md` §7 open question 1 ("Worth a ticket"), §4 "The pytest gate"; `ui-prototypes/DECISIONS.md` §10; `ui-prototypes/REAL_DATA_WRITES.md`; `tests/test_materialize_channels.py:9-14`.
- **Status** — `ticketable now`

### T2 — Files already written into the real DATA
- **Question** — Which files in `REAL_DATA_WRITES.md` does the researcher remove: the new ones (5 `UNITTEST_encoding_view*` texts, 4 pytest classifier joblibs, and the reader subagent's `catalogue_classifier_153815b9dea451b2.joblib`), and what is done about the overwritten `…f918586712c715e2.joblib` (present since 2026-09-04) and the 5 re-written step-cache files?
- **Why it matters** — Nothing was deleted, by rule; the stray joblibs sit in `DATA/derived/models` where a model picker could list them, and the overwritten joblib's original bytes are gone.
- **Source** — `ui-prototypes/REAL_DATA_WRITES.md`; `ui-prototypes/REPORT.md` §7 open question 1, §4 A round 1 P0 and round 2 P0; `ui-prototypes/DECISIONS.md` §7, §10, §14.
- **Status** — `ticketable now`

### T3 — A standing DATA write check
- **Question** — Should a before/after snapshot of every file under `DATA/` and `Results/` (the prototype's closing check) become a standard step for any agent session or smoke run that executes adapters, asserted by `webui/smoke.py`?
- **Why it matters** — "Read-only" in a brief is not enforced by the core: the first real-data write came from a reader subagent timing an adapter before any redirect existed, and the mid-way check covered only two paths.
- **Source** — `ui-prototypes/DECISIONS.md` §7 (lesson and extended closing check); `ui-prototypes/REPORT.md` §4 A round 1 P0.
- **Status** — `ticketable now`

### T4 — Tests for the bridge itself
- **Question** — Where do tests for `webui/server/` live and what runs them — SSE with its polling fallback, cancel between steps, reload re-attach, the meta sidecar on cache hits, 423 on every held-out route, the runtime redirect assertions — given pytest collects only `tests/`?
- **Why it matters** — The report names the bridge as the part that needs its own tests; the smoke gate reaches it only end-to-end through a browser.
- **Source** — `ui-prototypes/REPORT.md` §7 ("The bridge is the part that needs its own tests"), §4 "The pytest gate"; [Define the new tree's test gates][test-gates] "Where the gates run from".
- **Status** — `ticketable now`

### T5 — How the two gate sets relate, and a gate that cannot silently not-run
- **Question** — Does one command run the headless pytest suite and the webui gates (smoke, `tsc -b`, `vite build`), or are they deliberately separate; and does the smoke gate fail, rather than pass, when Playwright, chromium or the server is missing?
- **Why it matters** — "No tests ran" must never read as a pass; `CLAUDE.md` states that property for `pytest -m ui`, and nothing yet states it for the new gates.
- **Source** — [Define the new tree's test gates][test-gates] "How the two suites relate" and constraints; `CLAUDE.md` "Panel surfaces" (last paragraph).
- **Status** — `ticketable now`

### T6 — The import-boundary test at the new boundary
- **Question** — Should rule 1's enforcement test be extended so `Working/`, `Adapters/` and `Pipelines/` may not import FastAPI, uvicorn or Starlette, and `webui/server/` may not import `UI/` or Panel?
- **Why it matters** — "Nothing below the boundary may know a browser exists" is what makes the rebuild possible; it is enforced only for Panel, HoloViews, Bokeh and matplotlib below `UI/`, and "nothing in `webui/` imports `UI/`" is true by inspection, not by test.
- **Source** — `CLAUDE.md` non-negotiable rule 1; [Map: rebuild the Pipeline GUI interface on a stack chosen by evidence][map] "Standing preferences"; [Decide how the frontend reaches the core and the database][frontend-core] "Constraints".
- **Status** — `ticketable now`

### T7 — Provisioning the new toolchain in agent worktrees
- **Question** — How does a fresh worktree get `webui/client/node_modules` (~97 MB) and `webui/.venv` (FastAPI and uvicorn over conda via `--system-site-packages`): a per-worktree install, a shared cache, or a junction, without writing into the main checkout?
- **Why it matters** — Development runs in worktrees on a shared conda environment, a build-artefact directory that breaks provisioning was named as a real failure mode, and a junction is what caused the real-DATA writes (T1).
- **Source** — [Decide where the new tree lives and how both trees are served][tree-location] "Constraints"; `docs/adr/0001-web-ui-stack.md` "Consequences"; `ui-prototypes/REPORT.md` §8.1 footprint table.
- **Status** — `ticketable now`

### T8 — Retention of runtime directories
- **Question** — What retention policy applies to `webui/runtime/<stamp>/` (DB copy, step cache, results, models, logs, exports): keep the last N, age out, or clean on start?
- **Why it matters** — Nothing cleans them; after one night they held 772 MB for A and 502 MB for B, and a single 20 h matrix-profile session reached 285 MB.
- **Source** — `ui-prototypes/REPORT.md` §8.1 footprint table and following paragraph, §8 "Additional findings" bullet 2.
- **Status** — `ticketable now`

### T9 — Start scripts fail loudly on a busy port
- **Question** — Should `webui/start.ps1`, `webui/start.sh` and `webui/run_server.py` refuse to start when port 8765 is already bound?
- **Why it matters** — The benchmark found the default ports held by hand-started servers; a smoke run against a stale server tests old code and passes.
- **Source** — `ui-prototypes/REPORT.md` §8 "Additional findings" bullet 3; `ui-prototypes/DECISIONS.md` §15.
- **Status** — `ticketable now`

### T10 — Restore strict unused-code checks
- **Question** — When parallel builders stop sharing the client tree, should `noUnusedLocals` and `noUnusedParameters` be turned back on?
- **Why it matters** — They were relaxed deliberately so parallel builders would not break each other's build, and the loosening carried into `webui/` (`webui/client/tsconfig.app.json:21-22`).
- **Source** — `ui-prototypes/DECISIONS.md` §4 (TypeScript bullet); `webui/client/tsconfig.app.json`.
- **Status** — `ticketable now`

### T11 — `detection.wavelet_scattering` fails on this machine
- **Question** — Is the kymatio/scipy run-time failure an environment incompatibility to fix (a dependency change needing sign-off), or is the adapter withdrawn from the registry?
- **Why it matters** — It is listed and flagged "known broken" in the insert modal; a registered block that always fails erodes trust in every refusal reason.
- **Source** — `ui-prototypes/REPORT.md` §5 "Backend gaps" (wavelet scattering); `CLAUDE.md` "Environment".
- **Status** — `ticketable now`

### T12 — Apply the UI_CONTEXT.md corrections
- **Question** — Apply the four corrections (nothing rasterises; recordings are 282–721 h; the suffix is not executed selectively; the boundary leaks), the scale numbers and one-line type summaries, and G7's "z-normalised overlay" contradiction with §4.1.
- **Why it matters** — Every session loads `docs/agents/UI_CONTEXT.md` as required reading; as written it sends sessions hunting for a rasteriser and understates scale by about 60×.
- **Source** — [Correct the four factual errors in UI_CONTEXT.md][ui-context]; `prototyping/UI_REVIEW_BACKLOG.md` D5 and B27 (G7 handed to the correction ticket).
- **Status** — `ticketable now`

### T13 — Agent orchestration under usage limits
- **Question** — Should long agent tasks on this project standardise on incremental on-disk progress and resumable briefs, given usage limits cut off readers, fixers and critics during the prototype night?
- **Why it matters** — A wall-clock usage cap, not the stack, was the largest single delay, and one critique round's work was lost entirely.
- **Source** — `ui-prototypes/DECISIONS.md` §8, §9, §11; `ui-prototypes/REPORT.md` §2 "Orchestration friction".
- **Status** — `fog`

## Legacy tree

`UI/`, its tests and `tests/ui/` stay intact but ignored; nothing in `webui/` imports `UI/`. These items are the consequences of keeping it.

### L1 — The `LibraryGrid(conn)` versus `LibraryGrid(app)` contract mismatch
- **Question** — Is the test (`tests/test_ui_responsiveness.py::_empty_grid` calls `LibraryGrid(conn)`) or the code (`UI/workspaces/library/grid.py:74-76` expects an app exposing `.conn`) right, and is it fixed inside a frozen tree?
- **Why it matters** — It explains most of the 41 failures pre-existing on `main` @ 208e72c (library-grid, library-detail, motif-browser and responsiveness tests); "nothing that passed before now fails" is a weak gate with 41 reds, and no session may weaken a Panel test to pass.
- **Source** — `ui-prototypes/REPORT.md` §4 "The pytest gate"; `ui-prototypes/DECISIONS.md` §10; [Map: rebuild the Pipeline GUI interface on a stack chosen by evidence][map] "Standing preferences".
- **Status** — `ticketable now`

### L2 — Windows file locks at test teardown
- **Question** — Should tests that memory-map temp `.npy` files or hold `.sqlite` handles release them before teardown (`PermissionError [WinError 32]` in `test_library_grid` and `test_materialize_arbitrary_file`, reproduced serially)?
- **Why it matters** — The remainder of the 41 failures; they are test-hygiene bugs on the only platform this project runs on, not xdist artefacts, and they hide real regressions.
- **Source** — `ui-prototypes/REPORT.md` §4 "The pytest gate"; `ui-prototypes/DECISIONS.md` §10.
- **Status** — `ticketable now`

### L3 — Retirement trigger and the archival branch
- **Question** — The settled trigger ("the slice confirms the stack") has arguably fired, yet `UI/` stays because deletion is not trivial: what is the concrete trigger now, when is `archive/panel-ui` created (it does not exist yet), what is kept on `main`, and does `tests/ui/` move or die?
- **Why it matters** — Until this is sharp the old tree sits on `main` unmaintained but still inside the pytest gate, so every core change can break a tree nobody works on.
- **Source** — [Map: rebuild the Pipeline GUI interface on a stack chosen by evidence][map] "Constraints settled while charting" and "Not yet specified" (retirement mechanics); [Decide where the new tree lives and how both trees are served][tree-location] "The retirement mechanics".
- **Status** — `ticketable now`

### L4 — Tests that mix core assertions with UI imports
- **Question** — How are the `UI`-importing test files split so their core assertions survive deletion of `UI/` — notably `test_heldout_lock`, `test_manifest`, `test_export`, `test_import_drop_motifs`, `test_compare` and `test_run_groups` — and which purely UI tests die with it?
- **Why it matters** — A grep on 2026-09-16 finds 37 `tests/test_*.py` files plus `tests/ui/harness.py` and `tests/_session_isolation.py` importing `UI`; deleting without splitting drops core coverage of the held-out lock, manifests, export and imports, and `tests/test_plots_perf.py`'s decimator pin (C8).
- **Source** — grep of `tests/` for `from UI` / `import UI`; `docs/adr/0001-web-ui-stack.md` "Consequences" (last bullet).
- **Status** — `ticketable now`

### L5 — The UI snapshot inside `Working/`
- **Question** — Is `Working/Detection/sax/dsax_python/UI_snapshot_20260810-0512/` archived with the old tree, moved out of `Working/`, or deleted?
- **Why it matters** — Its `app.py:48-52` and `run_panel.py:38` import `UI.*` from inside the UI-free core's directory, so it breaks the moment `UI/` goes and contradicts rule 1 in spirit.
- **Source** — `Working/Detection/sax/dsax_python/UI_snapshot_20260810-0512/app.py`, `run_panel.py`; `CLAUDE.md` rule 1.
- **Status** — `ticketable now`

### L6 — Panel-era tooling and agent instructions
- **Question** — Which of `scripts/dev_serve.py`, `docs/UI_VERIFICATION.md`, `tests/ui/` and `CLAUDE.md`'s Layout table and "Panel surfaces" section are rewritten for `webui/`, archived or kept, and which general findings (construction is not painting; layered canvases fool naive paint checks) carry forward?
- **Why it matters** — `CLAUDE.md` is loaded by every agent and still defines "done" for a UI ticket as `pytest -m ui` plus Panel screenshots, which now points agents at the ignored tree.
- **Source** — [Define the new tree's test gates][test-gates] (reusability of `tests/ui/`); `ui-prototypes/REPORT.md` §8.2 "fit with the existing repo", §3 B (layered canvases); `CLAUDE.md` "Layout" and "Panel surfaces".
- **Status** — `ticketable now`

### L7 — Prototype B no longer runs
- **Question** — Is the runner-up kept runnable (for example, pinning its own copy of the service modules it imported by path from `ui-prototypes/A-react-fastapi/server/`), or accepted as frozen evidence only?
- **Why it matters** — The ADR names B as "the real alternative to start from" if the choice is refuted; since A was promoted to `webui/` and `ui-prototypes/` frozen (commit f0c8f13), a refutation would start from a fallback that does not start.
- **Source** — `ui-prototypes/DECISIONS.md` §5 (B imports A's service modules by path); `docs/adr/0001-web-ui-stack.md` "Considered Options" B.
- **Status** — `ticketable now`

## Out of scope (not fog)

Ruled out, not open. Listed so they are not rediscovered as fog; each returns only if its ruling is redrawn.

### O1 — Reimplementing anything under `Working/`
- **Question** — Should the rebuild change the algorithms it displays?
- **Why it matters** — No: the algorithms are the science and the rebuild only displays them (UI_CONTEXT §4.1). Adding public read or declaration surfaces (C1, C3, C8) is adding, not reimplementing.
- **Source** — [Map: rebuild the Pipeline GUI interface on a stack chosen by evidence][map] "Out of scope" bullet 1.
- **Status** — `out of scope`

### O2 — `Pipelines/` as code
- **Question** — Is `Pipelines/` part of the rebuild?
- **Why it matters** — Not as code; it is in scope only as the visual reference corpus for export and report output (E1).
- **Source** — [Map: rebuild the Pipeline GUI interface on a stack chosen by evidence][map] "Out of scope" bullet 2.
- **Status** — `out of scope`

### O3 — Multi-user, accounts, authentication, hosting, deployment
- **Question** — Does the interface support more than one researcher or run anywhere but localhost?
- **Why it matters** — No: single researcher, single machine, no auth. Every "who" records "this installation"; named accounts, per-user blind state and a second registration sign-off are recorded as future scope only.
- **Source** — [Map: rebuild the Pipeline GUI interface on a stack chosen by evidence][map] "Out of scope" bullet 3 and "Constraints settled while charting"; `prototyping/UI_FUNCTIONAL_SPEC.md` §11 bullet 1.
- **Status** — `out of scope`

### O4 — Schema changes without independent justification
- **Question** — Does the rebuild change the storage model?
- **Why it matters** — Not without a reason that serves the interface; additive migrations through an idempotent `init_db()` remain available (A12, A13 may need them), and the `recordings`-row-is-a-channel inversion is recorded, not renamed.
- **Source** — [Map: rebuild the Pipeline GUI interface on a stack chosen by evidence][map] "Out of scope" bullet 4 and "Vocabulary".
- **Status** — `out of scope`

### O5 — Feature development of the old `UI/` tree
- **Question** — Does the Panel tree gain features while it coexists?
- **Why it matters** — No: frozen, kept green, retired on the trigger (L3). Fixing its pre-existing test failures (L1, L2) is maintenance, not features.
- **Source** — [Map: rebuild the Pipeline GUI interface on a stack chosen by evidence][map] "Out of scope" bullet 5.
- **Status** — `out of scope`

### O6 — Relaxing evaluation protection
- **Question** — Can `M4_aug_concat_fs1.mat` be opened, or the two `M2_aug` sample rates split across train and test?
- **Why it matters** — No: M4 stays held out and refused without an explicit, typed and logged unlock, and the two `M2_aug` rates are one recording (B30 applied the same rule to Library scope).
- **Source** — [Map: rebuild the Pipeline GUI interface on a stack chosen by evidence][map] "Out of scope" bullet 6; `prototyping/UI_REVIEW_BACKLOG.md` D6, B30; `prototyping/UI_FUNCTIONAL_SPEC.md` §12 P19.
- **Status** — `out of scope`

### O7 — Human-labelled windows as a chain source
- **Question** — Can windows humans have already labelled be a chain source, skipping sliding windows?
- **Why it matters** — Sketched in training frame 0b but explicitly out of scope now; the related split question for supplied window sets (A11) stays open.
- **Source** — `prototyping/UI_REVIEW_BACKLOG.md` B3; `prototyping/UI_FUNCTIONAL_SPEC.md` §12 P13.
- **Status** — `out of scope`

### O8 — Text wrapping in the `.pen` mockups
- **Question** — Are the 14 caption paragraphs that overrun their containers a UI requirement?
- **Why it matters** — No: `.pen` text nodes have no width and do not wrap, so it is a mockup artifact; the copy is correct, the line breaks are not.
- **Source** — `prototyping/UI_FUNCTIONAL_SPEC.md` §11 bullet 5.
- **Status** — `out of scope`

### O9 — Discovery compare's heuristic explanatory sentence
- **Question** — Does the stage-by-stage compare explain divergence in prose?
- **Why it matters** — Replaced by stage pictures and divergence numbers; if ever reinstated it must be derived from both runs' cached stage artifacts, never a heuristic.
- **Source** — `prototyping/UI_FUNCTIONAL_SPEC.md` §11 bullet 6.
- **Status** — `out of scope`

### O10 — FitzHugh–Nagumo's interpretive claim
- **Question** — Does a FitzHugh–Nagumo fit claim anything about mechanism?
- **Why it matters** — No: its parameters are descriptors like peakedness; the block itself is fog (A9), the interpretation is out.
- **Source** — `prototyping/UI_FUNCTIONAL_SPEC.md` §11 bullet 3.
- **Status** — `out of scope`

### O11 — Prototype B's left-open fixes
- **Question** — Are B's unresolved items (RangeTool grips and move-drag, rich modal cards, whole-line threshold drag, row thumbnails versus §6.8, corpus rail details, per-session debug evidence, icon buttons' accessible names) carried forward?
- **Why it matters** — No: B lost and is frozen evidence (L7 covers whether it stays runnable).
- **Source** — `ui-prototypes/REPORT.md` §4 B round 1 "Fix pass" ("Left open"); `docs/adr/0001-web-ui-stack.md`.
- **Status** — `out of scope`

### O12 — Stacks ranked out before building
- **Question** — Are Dash/NiceGUI, Qt/PySide6 with pyqtgraph, or webview wrappers still candidates?
- **Why it matters** — No: ranked out before building (same family as B; no web output path with every renderer custom; answer no open question). A refutation of the chosen stack restarts from B.
- **Source** — `docs/adr/0001-web-ui-stack.md` "Considered Options"; `ui-prototypes/REPORT.md` §2 "Pre-build ranking".
- **Status** — `out of scope`

[map]: https://github.com/mitchbradshaw/CNN/issues/4
[visual-target]: https://github.com/mitchbradshaw/CNN/issues/9
[signal-reduction]: https://github.com/mitchbradshaw/CNN/issues/10
[ui-context]: https://github.com/mitchbradshaw/CNN/issues/11
[frontend-core]: https://github.com/mitchbradshaw/CNN/issues/13
[tree-location]: https://github.com/mitchbradshaw/CNN/issues/14
[test-gates]: https://github.com/mitchbradshaw/CNN/issues/15
