# W3-B — `interrogation.cycle_shapes`: stretch every cycle of a chain to one length, sort the cycles into shapes, find where the shape changes (Colominas & Wu 2023, the back half)

Read [`00-common.md`](00-common.md) first, including **both** "Lessons" sections. Commit prefix **`w3-b:`**. Plan:
`docs/research/analysis-blocks-from-literature.md` §4 A2 ("accept the back half, replace the front"); facts:
`docs/research/analysis-blocks-primary-sources.md` §2. Round 1 of wave 3. The authors' MATLAB
(github.com/macolominas/WarpingWSF) carries **no licence**: write from the paper, never port it.

You build on wave 2, which is merged. **Import, do not rewrite:**
- `Working.library.coherence.svd_entropy(member_matrix, align=True, *, medoid=None, resample_length, max_members,
  seed, squared, null_draws)`. It returns eq. 17 (`svd_entropy_norm`), the σ² variant (`svd_entropy_squared_norm`),
  `top_share`, and its own null (`null_median`, `null_p05`; `beyond_noise` = score < 0.9 × `null_p05`), and it aligns
  by SBD with edge-replicate padding. Read its docstring, above all `SMOOTH_CAVEAT`.
- The SBD functions in `Working/distances.py` (`sbd`, `sbd_shift`, `zero_pad_shift`, `sbd_matrix`).
- The surrogates in `Working/library/grouping/methods/kshape.py` (`phase_randomised_rows`, `trend_kept_surrogates`,
  `null_rng`).
- The group-key helper `Working/interrogation/intervals.py::write_group_columns`, Trains' use of it, and the Intervals
  anchor (`Adapters/interrogation_trains.py`, `Adapters/interrogation_intervals.py`).
- The key suffixes `NOISE_LIKE_SUFFIX` / `UNTESTED_SUFFIX` in `Working/Catalogue/shape_families.py`.

Read `docs/prompts/blocks/reports/W2-B-library-methods*.md`, `W2-E-families*.md` and `W2-evaluation.md` before you
design. They measured what SVD entropy can tell apart at realistic noise, and which noise tests are blind to which
shapes. **Your cycles are exactly the shapes wave 2's coherence null cannot judge**, as item 9 explains.

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
- **What wave 2 found on the same chains** (`W2-evaluation.md`, `event_families`: a 600 s window from each event's span
  start, HDBSCAN). Two families on rec 6's chain (53 and 13 events), and two on rec 542's (131 and 11). None on rec 3's
  chain, and none on 24 h M2_aug spans.
  - On rec 6 both families passed their own noise test, but HDBSCAN also crowded phase-randomised copies of the same
    events in 17 of 20 draws.
  - On rec 542 the larger family failed the coherence margin: its members share a broad, window-filling shape, which
    the trend-kept null keeps.
  - Cycle shapes asks the same question of whole cycles: put your answers on these chains beside theirs.

## The block

`interrogation.cycle_shapes`, **SpanSet → SpanSet**: a feature block (`page_name="Cycle shapes"`, `category="cluster"`
as `interrogation.event_families`). Core `Working/interrogation/cycle_shapes.py`; adapter
`Adapters/interrogation_cycle_shapes.py`.

1. **Sequences and cycles.** Event times are the Intervals anchor (Event shape's `onset_idx` when present, else the span
   start — import it as Trains does). Sequences: by `train_id` when the column exists (events in no train open no
   cycle); else by `group`; else the whole span is one sequence. Cycle k runs from event k's anchor to event k+1's,
   inside one sequence. A cycle longer than `max_cycle_s` (0 = auto; propose the rule, e.g. 3 × the sequence's median
   interval, and justify it) is a gap, not a cycle: left out and counted. An automatic value is a selection rule:
   sweep it across colours and span lengths, as wave 2's critics did.
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
   re-cut, re-warp. Repeat while the entropy falls **by more than its own sampling noise**: the spread of the same
   entropy over a few seeded bootstrap resamples of the cycles, never a fixed epsilon (wave 2's lesson). Stop after at
   most `max_iter` iterations (default 8; the paper's examples needed 1–8). Record the entropy at every iteration.
5. **Align** the final stack by zero-padded cross-correlation to the medoid — not the paper's cyclic shifts, because a
   fungal cycle does not wrap around (plan §4 A2) — and record each cycle's shift.
6. **Cluster** as the paper does: k-means, 50 replicates, K by Calinski–Harabasz over K = 2…`k_max` (default 6). The
   paper has no K = 1 outcome; this block does, and the question that decides it is not "noise or not" but **"one
   family that varies, or several families?"**. A chain whose plateau lengthens steadily is one family. k-means will
   still split it, and a noise null would call the split real.
   - So **K > 1 is claimed only if the best two-way split beats a single Gaussian with the stack's own covariance**:
     SigClust (Liu, Hayes, Nobel & Marron 2008, *JASA* 103:1281–1293). Compare the real stack's 2-means cluster index
     (within-cluster over total sum of squares) with draws from a Gaussian whose eigenvalues match the stack's, the
     background-noise floor estimated robustly as the paper does. `null_draws`: measure the cost and pick.
   - Read the paper; it is not in the primary-sources file, so name it in the docstring as this block's adaptation.
   - If the split does not beat that Gaussian, K = 1, said so. If it does, CH chooses K among 2…`k_max`.
   - Wave 2 found "families" in pure noise under every surrogate it tried; a matched-covariance Gaussian asks the
     question a continuum of shapes raises.
7. **Change points.** In time order within a sequence, a change is a cycle whose group differs from the previous
   cycle's. Report the run lengths, and whether groups come in runs more than chance: the number of runs against
   `n_perm` shuffles of the cycle order within the sequence (cycles do not overlap, so shuffling their order is a fair
   null for *order*; say what it does not test — a slow drift of shape would also make runs).
8. **Plateau measures** (round B). On each warped, chord-detrended cycle: `cycle_floor_frac` — the fraction of the
   cycle after the drop's extremum during which the signal stays within the lowest `floor_band` (default 0.25 of the
   cycle's range, a labelled placeholder) before it climbs out; `cycle_half_recovery_frac` — where in the cycle (0–1)
   the signal first recovers half the drop. Rules in `meta["rules"]`. Make the two synthetic shapes land where the
   researcher's words say: a trough's half recovery ≤ 0.25; a sharkfin's floor fraction 0.5–0.67.
9. **Coherence, and which null.** Report the stack's SVD entropy at three points, and per group too: before warping
   (fixed-length cuts from each anchor, the plain baseline), after warping, and after alignment. Give **both** eq. 17
   (`svd_entropy_norm`) **and** the σ² variant, each beside its null. W2-B's critic measured that eq. 17 cannot tell one
   shape from a 50/50 mixture at ≥ 5 % noise, while σ² separates them up to ~10 %. Which one heads the summary follows
   `svd_entropy`'s own default (`squared`), which is the researcher's open choice (W2-evaluation, question 4).

   **The nulls matter more than the score.** A cycle is the case wave 2 named its blind spot for: a smooth shape that
   fills its window. So:
   - **Do not use `svd_entropy`'s built-in null for the verdict.** It keeps a cubic trend per member, which keeps a
     cycle's drop-floor-climb curve in its own fake noise (`SMOOTH_CAVEAT`). Show it beside the others, with that
     caveat, or call `svd_entropy` with `null_draws=0` and say why.
   - **The verdict null is a background null.** Cut pseudo-cycles from the same `waveform` where no event lies — the
     recording's own quiet stretches, wave 2's recommendation for smooth shapes. Use random anchors, draw the lengths
     from the real cycles' lengths, and pass them through the identical warp, align and cluster pipeline, seeded.
   - If the span holds too little event-free signal, cut from the whole span at random anchors, and say so. Report how
     many seconds of background there were.
   - **Write the sampler once, for everyone:** `Working/background_null.py`, generic. It takes a trace, the sample
     ranges to avoid, the window lengths wanted, a count and a seed, and returns the windows plus a report (seconds of
     background available, how many windows were cut, whether it fell back). It knows nothing of cycles. W3-G (round 2,
     chosen by the researcher) reuses it as the Library's fairer noise test for families, so keep its contract small
     and state it in your report.
   - **Beside it, plain phase-randomised copies of each cycle** (`phase_randomised_rows`, no trend kept): it destroys a
     smooth curve's shape, unlike the trend-kept one.
   - A group whose coherence does not beat the background null is marked: see item 11.

   `svd_entropy` aligns by SBD with edge padding. Your stack is already aligned (item 5): decide whether its alignment
   should run again (`align=False`?), and say why.
10. **Columns added** (the event that opens cycle k carries cycle k): `cycle_index` (position in its sequence; −1 = opens
    no cycle), `cycle_length_s`, `cycle_amplitude`, `cycle_group` (1…K; −1 = none), `cycle_change`, `cycle_shift_s`,
    `cycle_corr` (correlation with its group's medoid after alignment), `cycle_floor_frac`,
    `cycle_half_recovery_frac`. `cycle_index` and `cycle_group` say where a cycle sits and what this block decided, not
    what it looks like: add both to `Working/types/windowset.py::BOOKKEEPING_COLUMNS` (wave 2's lesson), so a later
    Event windows → Cluster never clusters on them.
11. **`write_group`** (default false, as Trains): `group = cycle_group`, prefixing an upstream group with
    `Working/interrogation/intervals.py::write_group_columns` (`"<upstream>/<g>"`, the original in `group_upstream`). The
    template turns it on so Intervals times each cycle shape separately. **A group that failed its background test
    reaches Intervals keyed `<g>~noise_like`**, and one never tested is keyed `~untested`. Use the families block's
    suffixes, so no per-shape timing is read as confident when the shape is not.
12. **`meta`**, per sequence:
    - cycles used, and those left out by reason;
    - the entropy at every iteration;
    - the SigClust p and K, with the CH curve;
    - each group's coherence beside its three nulls, and its verdict;
    - run lengths and the order p;
    - `exemplar_events` = each group's medoid cycle, a member and never an average, with an `exemplar_rule`. Use the
      form `interrogation.event_families` uses, `{"<group>": <event index into the SpanSet>}`, which
      `webui/server/serialize.py` checks loudly against `EVENT_EXEMPLAR_FORM`;
    - timing, and `rules`;
    - a **drawing payload for W3-F**, `meta["cycle_stack"]`: at most 200 cycles (a seeded sample beyond that) × 128
      points, before and after alignment, each row with its group and time. This is the paper's stacked-cycles picture;
      state its exact form in your report.
13. **Too few cycles** (fewer than `min_cycles`, default 10): say so, add the columns as NaN / −1, and never report a K.
14. **Cost:** measure on 400 cycles with the null; declare an estimate only if it is not seconds.

## The template `chain_cycles`

In `tests/test_template_chain_cycles.py`: the `noise_threshold` template's two steps (read
`webui/server/templates.py`; do not edit it) → `interrogation.event_shape` (`polarity` drop) → `interrogation.trains`
(`rule` maxinterval with the chain-scale values above) → `interrogation.cycle_shapes` (`write_group` true; bind
`waveform` to the root signal with chord detrend, or to an earlier long-detrended step — choose with your synthetic
test and say why) → `interrogation.intervals`.

**How the manager will judge it.** The statistic is fixed here, before any data are seen; wave 2 learned not to change
one after seeing a result.
1. **The verdict:** the real stack's aligned SVD entropy (σ² and eq. 17) is below every one of 20 background-null draws.
   This is a floor that real chains should clear, not a finding.
2. **Findings:** K with its SigClust p, the change points, and the order test.
3. **Findings:** the floor fraction on M2_aug rec 2 (sharkfins) against rec 3 (sharp drops).
4. Everything beside wave 2's `event_families` families on rec 6 and rec 542.

Recordings: the chains in the table.

## Deliver

`Working/interrogation/cycle_shapes.py`, `Working/background_null.py`, `Adapters/interrogation_cycle_shapes.py`,
`tests/test_cycle_shapes.py`, `tests/test_background_null.py`, `tests/test_adapter_cycle_shapes.py`,
`tests/test_template_chain_cycles.py`, and two names added to `Working/types/windowset.py::BOOKKEEPING_COLUMNS` (with
their one-line reasons in its comment).

## Acceptance

- [ ] On each coloured background (detrended random walk, AR(1) φ 0.95–0.99, slow drift), a chain of 120 cycles whose
      period drifts from 20 to 60 min — 60 sharkfin cycles, then 60 trough cycles: K = 2, groups agree with the truth
      (adjusted Rand ≥ 0.9), the change point within ±1 cycle, the order p small.
- [ ] Warping helps: on the same chain, the entropy after warping is below the fixed-length cuts'.
- [ ] Floor fractions: sharkfin cycles 0.5–0.67 within your stated tolerance; trough half recovery ≤ 0.25.
- [ ] One family that varies: 120 sharkfin cycles whose floor fraction drifts steadily from 0.3 to 0.7 → K = 1 (the
      SigClust gate), with the drift visible in `cycle_floor_frac`, not invented as two families.
- [ ] No structure, **at the defaults, with 400 and 1,000 cycles**: Poisson event times on coloured noise → K = 1, an
      entropy inside the background null, and no Intervals key without a suffix. Cycles cut from a phase-randomised
      signal at real event times → inside the null too.
- [ ] The choice of null, shown: on sharkfin cycles and on cycles of a broad smooth hump (the case `SMOOTH_CAVEAT`
      names), pseudo-cycles from a quiet stretch score clearly worse than the real cycles. Report what the trend-kept
      and the plain phase nulls say on the same two sets — where one cannot tell them from noise is the reason for the
      choice.
- [ ] The same chain at 1 Hz and at 10 Hz gives the same groups and floor fractions.
- [ ] Too few cycles, over-long gaps, NaN inside a cycle: counted and said, never a blank.
- [ ] An upstream `group` survives as `group_upstream`; `write_group` false leaves `group` alone.
- [ ] `exemplar_events` are members; `meta["cycle_stack"]` respects its caps.
- [ ] The template runs end to end; `tests/test_block_standard.py` and `tests/test_adapter_spec.py` pass.
