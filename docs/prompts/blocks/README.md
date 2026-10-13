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
