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
| 2 | `W3-G-quiet-stretch-null.md` | the Library's families judged against the recording's own quiet stretches; a trend-kept null for k-Shape | (Library, families) | — (wave 2's follow-up) |

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

**Adjusted after wave 2 finished** (checked against `main` at `1019cf6`, 2026-10-14, after wave 2's gate and
`W2-evaluation.md`):

1. **W3-B (cycle shapes) changed its nulls.** Wave 2 measured that the Library's trend-kept noise null keeps a smooth
   window-filling shape's curve, and that HDBSCAN crowds phase-randomised copies of real events. A cycle is exactly such
   a shape. So W3-B's verdict null is now a **background null**: pseudo-cycles from the recording's own event-free
   stretches, which was wave 2's recommendation for smooth shapes. And K > 1 is now gated by a **matched-covariance
   Gaussian (SigClust)**, which asks "one family that varies, or several?" rather than "noise or not". W3-B also names
   wave 2's merged helpers exactly: `svd_entropy` with its σ² variant, null and `beyond_noise`; the surrogates in
   `kshape.py`; `write_group_columns`; the `~noise_like` / `~untested` key suffixes; the `exemplar_events` form.
2. **What shipped:** only `minirocket_manual_labels`; `event_clusters`, `recording_snippets` and `event_families` are
   experimental. `noise_threshold` stays W3-B's detector. Wave 2's families on the same chains (rec 6, rec 542) are
   put beside W3-B's findings.
3. **Still open, so they stay in W3-F:** cost calibration before routing, in-step cancel and progress, and two wave-2
   bridge follow-ups (the "uncalibrated" wording, and the event-loop warning). W3-F's smoke states avoid wave 2's traps:
   templates not yet seeded, and identical-hash navigation.
4. **Merged upstream:** the NaN-aware detrend and the gap-skipping drop detector. W3-A and W3-C now import snippets'
   `fill_nan`, and W3-D reuses snippets' `sub_length`.
5. **The manager brief:**
   - the preflight is narrowed to what can still move;
   - the statistics are fixed before any data are seen (wave 2's decision 22);
   - the bridge starts on `webui/.venv` (conda has no FastAPI);
   - the machine is kept awake;
   - a round-2 base branch is allowed when one block's fix round lags.
6. `00-common.md` and `critic.md` gained round 2's lessons: test at the defaults, at realistic sizes and through the next
   block; automatic lengths are selection rules; choose the null for your shapes; mark what failed its own test; never
   re-derive a verdict; agree payload forms.

**Wave 2's follow-ups for wave 3** (`W2-evaluation.md`, "What the researcher should decide"). The researcher chose one
on 2026-10-14: the **fairer noise test**, i.e. a null from the recording's own quiet stretches and a trend-kept null
for k-Shape. That is `W3-G`, in round 2, reusing W3-B's sampler. Not chosen for wave 3:
- re-tuning snippets' chooser;
- re-testing `event_families` on fresh spans;
- MiniRocket in Models › Launch.
