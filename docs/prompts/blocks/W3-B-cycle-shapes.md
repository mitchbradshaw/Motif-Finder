# W3-B — `interrogation.cycle_shapes`: stretch every cycle of a chain to one length, sort the cycles into shapes, find where the shape changes (Colominas & Wu 2023, the back half)

Read [`00-common.md`](00-common.md) first, including **both** "Lessons" sections. Commit prefix **`w3-b:`**. Plan:
`docs/research/analysis-blocks-from-literature.md` §4 A2 ("accept the back half, replace the front"); facts:
`docs/research/analysis-blocks-primary-sources.md` §2. Round 1 of wave 3. The authors' MATLAB
(github.com/macolominas/WarpingWSF) carries **no licence**: write from the paper, never port it.

You build on wave 2. **Import, do not rewrite:** `Working.library.coherence.svd_entropy` and the SBD functions in
`Working/distances.py` (`sbd`, `sbd_shift`, `zero_pad_shift` — W2-B), Trains' group-prefix helper and the Intervals
anchor (`Adapters/interrogation_trains.py`, `Adapters/interrogation_intervals.py`), and W2-B's phase-randomised member
surrogates if its fix round exported them (grep `phase` under `Working/library/`). Read
`docs/prompts/blocks/reports/W2-B-library-methods.md`, `.critic.md` and its fix report before you design: the critic
measured what SVD entropy can and cannot tell apart at realistic noise.

## In plain words

Picture a drummer whose tempo drifts. To compare one beat with another you first stretch every beat to the same length,
then stack them and sort them into piles of "the same beat". The paper does this for heartbeats and voices. In our
recordings the beats are drops: chains of drops every 20–60 minutes, for days. Each stretch from one drop to the next
is a **cycle** — the drop, the floor, the slow climb back, then the next drop. This block stretches every cycle to one
length, stacks the cycles, lines them up, and asks: do all the cycles share one shape, or are there a few kinds — and
where in the chain does the kind change? Per cycle it also measures how long the signal sits on its floor before it
climbs: the sharkfin **plateau**, which nothing in the app measures yet (`docs/rq_roundB/README.md`, "The sharkfin
plateau"; a trough is "mostly back by the quarter point", a sharkfin sits on its floor for ½–⅔ of the interval).

## What is known about chains on real data (wave-1 re-test, 2026-10-14, sandbox)

The researcher named spans that hold long drop chains. Each was run through the shipped detectors and both train rules,
with 20 surrogate draws:

| Span (recording) | `noise_threshold` events | logISI (the Trains default) | MaxInterval at chain scale |
|---|---|---|---|
| M2_aug rec 3, 490–540 h (sharp drops 500–530 h) | 116 | none — one hump (intra-train peak 1,858 s) | one train, 490.2–539.7 h, 116 events |
| M2_aug rec 6, 370–470 h (scalloped chain ~383–445 h) | 115 | none — no run reached 3 events | one train, 375.9–444.6 h, 114 events |
| L_LM_Jul_26_J rec 542, 370–490 h (10 Hz) | 163 | 3 short trains (10 events) | 398.0–400.4 h (6), 403.4–474.1 h (156) |
| L_LM_Jul_26_J rec 543, 370–490 h (10 Hz) | 176 | none — one hump (2,614 s) | 370.0–452.2 h (129), 457.0–473.6 h (25), 476.8–489.8 h (21) |
| M2_aug rec 2, 294–304 h (sharkfins 298.2–299 h) | 13 | two trains (10 + 3) | one train, 298.2–302.8 h, 13 events |

- **logISI cannot see a chain.** A dense run with few long silences has one hump in its log-gap histogram, so the
  default rule says "no trains". MaxInterval with chain-scale gaps (begin 1.5 h, end 3 h, trains < 3 h apart merge, no
  minimum duration: `mi_begin_gap_s 5400, mi_end_gap_s 10800, mi_min_ibi_s 10800, mi_min_duration_s 0`) finds each
  chain as one or a few trains.
- **Whether a chain exists is the detector's question, not the train rule's.** Every detector's surrogate draws found
  ≈ 0 events, so each chain beats the surrogate null; an interval-shuffle null cannot fail on a dense chain (any order of
  its gaps is still a chain). This block asks the next question: what do the cycles look like?
- **Which detector:** `noise_threshold` places about one event per drop on these chains (rec 6: 106 in the chain;
  rec 542: 163). `drop_detection_v1` under-detects (19–28 per chain), `deconvolved_troughs` fragments each drop
  (260–1,565 events per chain), `cwt_events` lies between.
- **Cycle lengths:** the log-gap peak sits at ~1,500–2,600 s (25–45 min), so a cycle is ~1,500–2,600 samples at 1 Hz and
  ten times that on L_LM_Jul_26_J (10 Hz, provisional).

## The block

`interrogation.cycle_shapes`, **SpanSet → SpanSet** — a feature block (`page_name="Cycle shapes"`; `category="cluster"`
unless W2-E's `interrogation.event_families` chose otherwise — match it). Core `Working/interrogation/cycle_shapes.py`;
adapter `Adapters/interrogation_cycle_shapes.py`.

1. **Sequences and cycles.** Event times are the Intervals anchor (Event shape's `onset_idx` when present, else the span
   start — import it as Trains does). Sequences: by `train_id` when the column exists (events in no train open no
   cycle); else by `group`; else the whole span is one sequence. Cycle k runs from event k's anchor to event k+1's,
   inside one sequence. A cycle longer than `max_cycle_s` (0 = auto; propose the rule, e.g. 3 × the sequence's median
   interval, and justify it) is a gap, not a cycle: left out and counted.
2. **The waveform.** A side input `waveform` (a Signal; sources `root_signal` and `earlier_step` —
   `Adapters/base.py::SideInputSpec`, `Working/side_inputs.py`) supplies the trace the cycles are cut from; unbound, they
   are cut from `x`, the chain's current signal. Why: the detector usually runs on a short-detrended trace (600 s in the
   `noise_threshold` template) that flattens a 30–45-minute climb, so a cycle's shape must come from a trace whose
   baseline removal is longer than the cycle. `cycle_detrend`: `"chord"` (default — subtract the straight line between
   the cycle's two ends, each the median of its first / last few samples: the pre-drop level at both ends) or `"none"`.
   Show in a test that the 600 s detrend distorts a synthetic sharkfin cycle and that the side input restores it.
3. **Warp and demodulate.** Resample each cycle to `n_points` (default 256) with the Library's own preparation
   (`Working.distances.resample_to_length`, as `ward.shape_vectors` does), so a cycle and a Library member are prepared
   alike; z-normalise. The size and duration the warp removes stay as columns (`cycle_amplitude` in stored units,
   `cycle_length_s`): the warp separates shape from duration and size, it does not discard them.
4. **Iterate — the paper's refinement, adapted.** The paper re-estimates the phase until the SVD entropy stagnates.
   Here the phase comes from the anchors, so an iteration refines the anchors: align each cycle to the current template
   (the stack's medoid by SBD; a median may serve as a working template but is never drawn) with a zero-padded
   cross-correlation shift bounded by `max_shift_frac` (default 0.1) of its length, move its start anchor by that shift,
   re-cut, re-warp. Repeat while the entropy falls **by more than its own noise** — judged against the spread of the
   same entropy over a few seeded phase-randomised copies of the stack, never a fixed epsilon (wave 2's lesson) — and at
   most `max_iter` times (default 8; the paper's examples needed 1–8). Record the entropy at every iteration.
5. **Align** the final stack by zero-padded cross-correlation to the medoid — not the paper's cyclic shifts, because a
   fungal cycle does not wrap around (plan §4 A2) — and record each cycle's shift.
6. **Cluster** as the paper does: k-means, 50 replicates, K by Calinski–Harabasz over K = 2…`k_max` (default 6). The
   paper has no K = 1 outcome; this block does. **K > 1 is claimed only if its CH beats what the same procedure reaches
   on phase-randomised copies of the cycles** (each cycle's own spectrum kept, seeded, `null_draws` — measure the cost
   and pick the default); otherwise K = 1, said so. Wave 2 found two "families" in every pure-noise set handed to
   HDBSCAN; this is how that is avoided here.
7. **Change points.** In time order within a sequence, a change is a cycle whose group differs from the previous
   cycle's. Report the run lengths, and whether groups come in runs more than chance: the number of runs against
   `n_perm` shuffles of the cycle order within the sequence (cycles do not overlap, so shuffling their order is a fair
   null for *order*; say what it does not test — a slow drift of shape would also make runs).
8. **Plateau measures** (round B). On each warped, chord-detrended cycle: `cycle_floor_frac` — the fraction of the
   cycle after the drop's extremum during which the signal stays within the lowest `floor_band` (default 0.25 of the
   cycle's range, a labelled placeholder) before it climbs out; `cycle_half_recovery_frac` — where in the cycle (0–1)
   the signal first recovers half the drop. Rules in `meta["rules"]`. Make the two synthetic shapes land where the
   researcher's words say: a trough's half recovery ≤ 0.25; a sharkfin's floor fraction 0.5–0.67.
9. **Coherence.** The stack's SVD entropy before warping (fixed-length cuts from each anchor — the plain baseline),
   after warping, and after alignment; per group too. **Both** eq. 17 (unsquared, the paper's) **and** the squared
   variant, **each beside its null** (the same score on phase-randomised copies): W2-B's critic measured that eq. 17
   cannot tell one shape from a 50/50 mixture at ≥ 5 % noise and sometimes ranks the mixture purer, while the squared
   variant separates up to ~10 %. Read `svd_entropy`'s docstring on `main`: your stack is already aligned, so decide
   whether its own alignment should run (`align=False`?) and say why.
10. **Columns added** (the event that opens cycle k carries cycle k): `cycle_index` (position in its sequence; −1 = opens
    no cycle), `cycle_length_s`, `cycle_amplitude`, `cycle_group` (1…K; −1 = none), `cycle_change`, `cycle_shift_s`,
    `cycle_corr` (correlation with its group's medoid after alignment), `cycle_floor_frac`,
    `cycle_half_recovery_frac`. `cycle_index` and `cycle_group` say where a cycle sits and what this block decided, not
    what it looks like: add both to `Working/types/windowset.py::BOOKKEEPING_COLUMNS` (wave 2's lesson), so a later
    Event windows → Cluster never clusters on them.
11. **`write_group`** (default false, as Trains): `group = cycle_group`, prefixing an upstream group the way Trains does
    (`"<upstream>/<g>"`, the original in `group_upstream`) — import that helper. The template turns it on so Intervals
    times each cycle shape separately.
12. **`meta`**, per sequence: cycles used and left out by reason, the entropy at every iteration, K with the CH curve
    and its null, run lengths and the order p, `exemplar_events` = each group's medoid cycle (`{"<group>": <event
    row>}` — a member, never an average; `exemplar_rule`), timing, `rules`; and a **drawing payload for W3-F**,
    `meta["cycle_stack"]`: at most 200 cycles (a seeded sample beyond that) × 128 points, before and after alignment,
    each row with its group and time — the paper's stacked-cycles picture.
13. **Too few cycles** (fewer than `min_cycles`, default 10): say so, add the columns as NaN / −1, and never report a K.
14. **Cost:** measure on 400 cycles with the null; declare an estimate only if it is not seconds.

## The template `chain_cycles`

In `tests/test_template_chain_cycles.py`: the `noise_threshold` template's two steps (read
`webui/server/templates.py`; do not edit it) → `interrogation.event_shape` (`polarity` drop) → `interrogation.trains`
(`rule` maxinterval with the chain-scale values above) → `interrogation.cycle_shapes` (`write_group` true; bind
`waveform` to the root signal with chord detrend, or to an earlier long-detrended step — choose with your synthetic
test and say why) → `interrogation.intervals`.

**How the manager will judge it:** (1) the shape null — the real stack's aligned SVD entropy (both variants) below every
one of 20 phase-randomised copies cut at the real event times: a floor real chains should clear easily, not a finding;
(2) K, the change points and the order test, as findings; (3) the floor fraction on M2_aug rec 2 (sharkfins) against
rec 3 (sharp drops). Recordings: the chains in the table.

## Deliver

`Working/interrogation/cycle_shapes.py`, `Adapters/interrogation_cycle_shapes.py`, `tests/test_cycle_shapes.py`,
`tests/test_adapter_cycle_shapes.py`, `tests/test_template_chain_cycles.py`, and two names added to
`Working/types/windowset.py::BOOKKEEPING_COLUMNS` (with their one-line reasons in its comment).

## Acceptance

- [ ] On each coloured background (detrended random walk, AR(1) φ 0.95–0.99, slow drift), a chain of 120 cycles whose
      period drifts from 20 to 60 min — 60 sharkfin cycles, then 60 trough cycles: K = 2, groups agree with the truth
      (adjusted Rand ≥ 0.9), the change point within ±1 cycle, the order p small.
- [ ] Warping helps: on the same chain, the entropy after warping is below the fixed-length cuts'.
- [ ] Floor fractions: sharkfin cycles 0.5–0.67 within your stated tolerance; trough half recovery ≤ 0.25.
- [ ] No structure: Poisson event times on coloured noise → K = 1 and an entropy inside its null; cycles cut from a
      phase-randomised signal at real event times → inside the null too.
- [ ] The same chain at 1 Hz and at 10 Hz gives the same groups and floor fractions.
- [ ] Too few cycles, over-long gaps, NaN inside a cycle: counted and said, never a blank.
- [ ] An upstream `group` survives as `group_upstream`; `write_group` false leaves `group` alone.
- [ ] `exemplar_events` are members; `meta["cycle_stack"]` respects its caps.
- [ ] The template runs end to end; `tests/test_block_standard.py` and `tests/test_adapter_spec.py` pass.
