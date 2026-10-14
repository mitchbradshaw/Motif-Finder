# Blocks from the literature — build prompts

The researcher confirmed the plan in `docs/research/analysis-blocks-from-literature.md` on 2026-10-13 (its §8) and
asked for wave 1 to be built the same day: one prompt per block, implementer sub-agents in parallel, critic
sub-agents, and a final evaluation by the managing session.

Every prompt here starts from [`00-common.md`](00-common.md) — read it first; it holds the rules that are the same for
every block (worktree safety, test-first, units, what not to touch, the shape of the report).

| Prompt | Block(s) | Types | Paper |
|---|---|---|---|
| `W1-A-beads.md` | `preprocessing.beads` | Signal → Signal | Ning, Selesnick & Duval 2014 |
| `W1-B-deconvolve.md` | `detection.deconvolve`, `detection.impulse_events` | Signal → Scores, Scores → SpanSet | Friedrich, Zhou & Paninski 2017 |
| `W1-C-cwt-ridges.md` | `detection.cwt_ridges` | Signal → SpanSet | Du, Kibbe & Lin 2006 |
| `W1-D-noise-threshold.md` | `detection.noise_threshold` | Signal → SpanSet | Quian Quiroga, Nadasdy & Ben-Shaul 2004 |
| `W1-E-trains.md` | `interrogation.trains` | SpanSet → SpanSet | Pasquale et al. 2010; Cotterill et al. 2016; Adamatzky 2022 |
| `W1-F-fluss.md` | `detection.fluss` | Signal → Scores | Gharghabi et al. 2017 |
| `W1-G-intervals-lv.md` | LV and CV2 in `interrogation.intervals` | SpanSet → SpanSet (existing) | Shinomoto et al. 2003; Holt et al. 1996 |

**The bar a chain must clear to ship as a template (researcher, Q4):** it beats its random-data (surrogate) null on
real recordings. It does not have to be choosier than the drop detector. A block that misses the bar ships as a block
whose description says "experimental". The managing session runs that evaluation after merging; implementers cannot
(their worktrees hold no real data).

Reports are returned by each sub-agent as text and filed by the manager under `reports/`.

## Wave 2 — families and categories (prompts written 2026-10-14, not yet run)

Run by a managing session from [`W2-manager.md`](W2-manager.md), the same way wave 1 was run. `00-common.md` and
`critic.md` now apply to every wave and carry wave 1's lessons (test on coloured backgrounds; a clustering block must
be shown to find nothing in pure noise).

| Round | Prompt | Block(s) | Types | Paper |
|---|---|---|---|---|
| 1 | `W2-A-event-windows.md` | `catalogue.event_windows` (+ the `spanset->windowset` view row) | SpanSet → WindowSet | — (the bridge) |
| 1 | `W2-B-library-methods.md` | Library methods `kshape`, `hdbscan`; `sbd`; `svd_entropy` on the Family page data | (Library) | Paparrizos & Gravano 2015; Campello et al. 2013; Colominas & Wu 2023 |
| 1 | `W2-C-minirocket.md` | `catalogue.minirocket` | WindowSet → WindowSet | Dempster, Schmidt & Webb 2021 |
| 1 | `W2-D-snippets.md` | `catalogue.snippets` | WindowSet → Grouping | Imani et al. 2018 |
| 2 | `W2-E-families.md` | `catalogue.shape_families`, `interrogation.event_families` | WindowSet → Grouping, SpanSet → SpanSet | as W2-B |
| 2 | `W2-F-ui.md` | the drawings, block-named exemplars, the Library's method choice, coherence, glyphs, smoke states | (UI) | — |

Templates proposed: `event_clusters` (W2-A), `minirocket_manual_labels` (W2-C), `recording_snippets` (W2-D),
`event_families` (W2-E). Each ships only if it beats its own null on real recordings; the nulls per template are in
`W2-manager.md`.

## Wave 3 — exploratory (prompts written 2026-10-14 while wave 2 was still running; not yet run)

Run by a managing session from [`W3-manager.md`](W3-manager.md), the same way as waves 1 and 2. `00-common.md` and
`critic.md` now carry wave 2's lessons as well as wave 1's.

| Round | Prompt | Block(s) | Types | Paper |
|---|---|---|---|---|
| 1 | `W3-A-multiscale-entropy.md` | `catalogue.multiscale_entropy` | WindowSet → WindowSet | Costa, Goldberger & Peng 2005; Wu et al. 2014 |
| 1 | `W3-B-cycle-shapes.md` | `interrogation.cycle_shapes` | SpanSet → SpanSet | Colominas & Wu 2023 (the back half) |
| 1 | `W3-C-pan-matrix-profile.md` | `detection.pan_matrix_profile` | Signal → Encoding | Madrid et al. 2019 |
| 2 | `W3-D-mpdist.md` | `mpdist`, a fourth Library distance | (Library) | Gharghabi et al. 2018 |
| not run | `W3-E-wavelet-features.md` | `catalogue.wavelet_features` | WindowSet → WindowSet | Quian Quiroga et al. 2004 (the sorter's features) |
| 2 | `W3-F-ui.md` | cancel and progress inside a step; every costed block calibrated before routing; MSE curves, the cycle stack, pan-MP row labels, an optional scalogram with ridges; glyphs; smoke states | (UI) | — |

Templates proposed: `complexity_fingerprint` (W3-A), `chain_cycles` (W3-B), `motif_lengths` (W3-C). The nulls per
template are in `W3-manager.md`.

**The researcher's choice of the plan's two optional blocks (2026-10-14): MPdist only.** W3-D runs in round 2; W3-E
(wavelet features) is not run — its features overlap what MiniRocket and Event shape already give the clustering
blocks — and its prompt stays on file for a later wave (re-check it against `main` before using it).

**What the results so far changed in these prompts** (against plan §7.1):

- **Cycle shapes takes its chains from MaxInterval at chain scale, with `noise_threshold` events, not from logISI.** The
  2026-10-14 re-test of the researcher's known chains: logISI saw one hump and called no train on every chain;
  MaxInterval with 1.5 h / 3 h gaps found each as one or a few trains; `noise_threshold` placed about one event per
  drop where the drop detector under-detected and deconvolution fragmented. The numbers are in `W3-B`.
- **Cycle shapes cuts its cycles from a side-input trace** — the detector's 600 s detrend flattens a 30–45 min climb —
  and measures the sharkfin plateau per cycle (round B), which nothing measured.
- **Every block that picks a number or groups things carries a colour-preserving null in the run** (wave 2: every fixed
  floor failed at some colour or span length); SVD entropy is reported squared and unsquared, each beside its null (W2-B's
  critic: the paper's version cannot tell one shape from a mixture at ≥ 5 % noise).
- **The pan matrix profile's suggested window must beat its null**, never default to the shortest length, and the
  manager re-runs FLUSS with it (FLUSS's changes sat 3–10 h from the known boundaries at 300 s).
- **W3-F fixes two frictions found on the way:** a long step cannot be cancelled (the bridge passes no in-step cancel to
  blocks), and only the matrix-profile cost model is calibrated before routing.
- **Process:** worktrees are cut from `origin/main` and must be fast-forwarded to the named base (wave 2's first launch);
  FastAPI tests skip under conda and must be run with `webui/.venv`.

**Before launch — to check and adjust once both rounds of wave 2 have finished:**

1. W2-B's final `svd_entropy` signature (null, squared variant, alignment rule) and whether it exported a
   phase-randomised member helper — W3-B imports both.
2. W2-E's category and shared clustering entry point — W3-B matches the category.
3. Which wave-2 templates shipped, and with which detector — W3-B's template starts from `noise_threshold`.
4. Whether W2-D exported gap handling or a pairwise MPdist kernel — W3-C and W3-D reuse them.
5. Whether `route_local` and `runs.py` were changed by anyone (W3-F items 1–2), and whether the detrend NaN fix merged
   (W3-A's gap handling).
6. Wave 2's gate: the pytest and smoke failure sets that become wave 3's baseline; any new lessons from round 2's
   critics, for `00-common.md`.
