# Stage 4 — the Fixup Wave

Prompts for the round after wiring (`docs/prompts/wiring/`, prompts 00–05, all run). Wiring made the
pages read and write real data. This stage fixes what the live data then showed to be wrong, broken or
missing — from the wiring reports' own "Left" / "What is still not true" lists, from the critics'
unfixed findings, and from the user's and the supervisor's use of the running app.

**These files are skeletons.** They carry the *symptoms* — grouped by page, each traced to its evidence
(a report section, a source line, or a screenshot) — and nothing else. The prompt body, the file list,
the test-first work plan and the gate are written only after the questions in
`QUESTIONS.md` are answered, because most of the symptoms below are one design decision away from
being either a bug or a spec change.

| File | Workspace / pages |
|---|---|
| **WAVE 1 — run together** | |
| `E-aggregate-stops-fabricating.md` | **run 2026-09-30** (`reports/E-aggregate-stops-fabricating.md`). Interrogation reads every measure from the core (the three constants and the browser recovery are gone; not-measured is null, counted and explained); `spike-shape` → `event-shape` = `interrogation.event_shape`, the upstream carried on every walk; `rise_time_frac` on the shape block, null for a drop; the overlay window is the stored context on a measured y. Port **8765** |
| `G-review-axis-and-resolution.md` | **ready.** Review's trace gets a real x axis (the cause of U1/U2/U3); decimation follows the rendered width; source-resolution toggle, default ON; Review shifts a legacy row. Port **8766** |
| **WAVE 2 — run together, after wave 1** | |
| `F-datasets-and-naming.md` | *(not written)* editable dataset metadata + display name across the site, and the Settings channel-list overflow |
| `J-dehshibi-vs-the-paper.md` | *(not written)* needs the researcher's PDF and a grilling round of its own |
| **WAVE 3 — alone** | |
| `H-blocks-show-their-work.md` | *(not written)* U7/U8/U9/U11 — process views per block, span slideshows, figures instead of tables. Cross-cutting; conflicts with everything |
| **DONE** | |
| `M-migrate-legacy-detections.md` | **run 2026-09-28** (`reports/M-…`; 115 rows rewritten on the real database, backup verified, second pass plans zero, suite 1786/0) |
| `B-units-and-amplitude.md` | **written and ready to run — the highest-priority item in the stage.** The derived channels are in volts and the whole UI labels them mV; every amplitude ever shown is 1000x too small. Blocks the plot-domain prompt `C` |
| `C-one-plot-domain-rule.md` | **run and reported 2026-09-23** (`reports/C-one-plot-domain-rule.md`; one rule in `charts/domain.ts`, suite 1775/0). Per-card measured domains with the shared scale as a reference bar, replacing PRD D5, across Review + Library + Explore. Acceptance test: no motif clipped in its own thumbnail |
| `D-event-features.md` | **run and reported 2026-09-23** (`reports/D-event-features.md`: `interrogation.event_shape`, `interrogation.intervals`, `preprocessing.invert`, `motif_features`, the sequence rose; the Library backfill ran on the sandbox only — `--real` is the researcher's call).** The researcher's top-priority capability. Polarity-neutral per-event feature blocks, inter-event intervals, the max-slope rose over `Working/Detection/drop_motifs/gradients.py` (which already exists), `preprocessing.invert`, and `motif_features` keyed by content hash. Adds `SpanSet.features` mirroring `WindowSet.features` — **no eighth type** |
| `M-migrate-legacy-detections.md` | **run and reported 2026-09-28** (`reports/M-migrate-legacy-detections.md`; 115 legacy span-relative `detections` rows across 8 runs rewritten to channel-absolute through `init_db()`, `audit_log` id 482, verified by re-running each run's recipe; suite 1786/0). Q25. Runs before `G`, which still adds Review's `absolute_bounds` call |
| `A-no-decision-fixes.md` | **run and reported 2026-09-22** (`reports/A-no-decision-fixes.md`; all seventeen done, suite 1660/0) — the seventeen defects across six workspaces that have a known cause, a known line and exactly one defensible fix. Carries an explicit not-in-scope table so it cannot widen into the decisions still open |
| `00-cross-cutting.md` | the shell, the `demo` chip, shared chart primitives, naming, workflow |
| `01-explore.md` | Corpus, Signal, Cross-channel, Span edit |
| `02-analyse-chain.md` | Chain, Block, Algorithm glyphs |
| `03-analyse-interrogation.md` | Interrogation, Slope, Aggregate |
| `04-analyse-training.md` | Training chain, blocks 01–05 |
| `05-discovery.md` | Runs, Seed search, Compare, Compare every stage |
| `06-models.md` | Launch, Results, Compare, Registry |
| `07-review.md` | Queue (inspector), Cluster |
| `08-library.md` | Recurrence, Atlas, Family, Edit grouping, Import, Window sets, Templates |
| `09-jobs.md` | All jobs, Paused run, Upload and continue, Cluster job |
| `10-settings.md` | the sixteen settings pages |

`QUESTIONS.md` is the live list of what must be decided before a prompt can be written, with the
answers recorded beside each question as they are given. **Rounds 1 and 2 are answered (2026-09-23);
round 3 is open.**

**The order of work, as it stands:** `A` (done) → **`B` (units — everything amplitude-shaped waits on
it)** → `C` (plot domains) and the window-sets unblock, in parallel → `D` (event features, the
researcher's top-priority capability) → the page prompts.

Reports go in `reports/`, cross-agent requests in `requests/`, same convention as the wiring stage.
