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
