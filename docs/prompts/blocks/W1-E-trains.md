# W1-E — `interrogation.trains`: trains (bursts, "words") of events (Pasquale et al. 2010; Cotterill et al. 2016; Adamatzky 2022)

Read [`00-common.md`](00-common.md) first. Commit prefix **`w1-e:`**. Plan: `docs/research/analysis-blocks-from-literature.md`
§5 row 5; facts: `docs/research/analysis-blocks-primary-sources.md` §8 (read it — the benchmark recommends MaxInterval
first, logISI as the high-performing alternative; Adamatzky's settings differ by species).

## In plain words

If events come in trains, the gaps between them are of two kinds — short gaps inside a train, long gaps between
trains — and a histogram of the gaps on a log scale has two humps. logISI finds the valley between the humps and uses
it as the cut. If there is only one hump it says so — no trains — instead of inventing some. Two more rules sit beside
it so results can be compared: **MaxInterval** (fixed thresholds; the benchmark's first choice in neurons, but its five
thresholds are unknown for fungi) and **Adamatzky's words** (θ = the mean gap, or 2×).

## The block

`interrogation.trains`, SpanSet → SpanSet, a **feature block** (`BLOCK_INTEGRATION.md` §1): the spans pass through
unchanged, keeping every column they came with; it adds `train_id` (−1 = in no train), `train_size`,
`position_in_train`, `gap_before_s`. It never overwrites an upstream `group` column; an option `write_group`
(default false) sets `group = train_id` so that `interrogation.intervals` downstream measures timing **within** trains.

Event times: the `onset_idx` column when `interrogation.event_shape` ran upstream, else the span start — **import**
the anchor logic from `Adapters/interrogation_intervals.py` / `Working/interrogation/intervals.py`, do not rewrite it.

Rules (`rule` param):
1. **`logisi`** (default) — Pasquale, Martinoia & Chiappalone 2010 as restated by Cotterill et al. 2016: a smoothed
   histogram of log10 gaps (with tens to hundreds of events, use a kernel density on log-gaps and state the bandwidth
   rule); the intra-train peak is the largest peak at or below `max_core_gap_s` (the neuronal 100 ms; **0 = auto =
   the median gap**, a stated fungal adaptation); the first minimum after it whose void parameter
   1 − g(min)/√(g(p₁)g(p₂)) **exceeds** 0.7 sets the cut; a train is ≥ `min_events` (3) events with gaps below the
   cut; if the cut exceeds `max_core_gap_s`, find cores with `max_core_gap_s` and extend them with the cut.
   No valley → **no trains**, said in `meta`.
2. **`maxinterval`** — the five thresholds in seconds (`mi_begin_gap_s`, `mi_end_gap_s`, `mi_min_ibi_s`,
   `mi_min_duration_s`, `min_events`), with defaults stated as placeholders until fungal values exist.
3. **`adamatzky`** — consecutive events form a word while their gap ≤ θ = `theta_mult` × the mean gap (default 1.0;
   the paper also used 2.0); words of one event are allowed (`min_events` applies to what is called a train).

`meta`: the rule, the cut found (s), the void value, the log-gap density curve (≤ 512 points, for a drawing), the
number of trains, the fraction of events in trains, the train-size distribution, and a Lempel–Ziv complexity of the
train-size sequence (reuse `compute_lempel_ziv_complexity` in `Working/Detection/analysis/dehshibi_detection_analysis.py`
or the Kaspar–Schuster routine beside it if it fits; print the rule). **Honesty:** fewer than 10 gaps → the histogram
rules refuse in words; a found within-train gap near 200 s gets a warning that a ~0.005 Hz cycle appeared on no-fungus
control channels in Buffi et al. 2025 — check another channel.

## Deliver

- Core `Working/interrogation/trains.py`; adapter `Adapters/interrogation_trains.py` (`category="control"` like the
  other interrogation blocks — check — `page_name="Trains"`).
- Tests `tests/test_trains.py`, `tests/test_adapter_trains.py`, `tests/test_template_event_trains.py` with
  `TEMPLATE = {"name": "event_trains", "kind": "interrogation", …}` = the three `drop_detection_v1` steps (copy them
  from `webui/server/templates.py` — read it, do not edit it) → `interrogation.event_shape` → `interrogation.trains`
  → `interrogation.intervals`.

## Acceptance

- [ ] Poisson event times (a few hundred): `logisi` reports no trains (no valley), not a spurious split.
- [ ] Clear trains (gaps ~30 s inside, ~3000 s between): `logisi` finds every train with the right members.
- [ ] `adamatzky` reproduces a hand-computed example exactly; `maxinterval` likewise.
- [ ] Fewer than 10 gaps: refuses in words, passes the spans through with `train_id = −1`.
- [ ] Upstream columns (including `group`) survive; `write_group` works and `interrogation.intervals` downstream then
      groups by train.
- [ ] The template runs end to end; the block passes `tests/test_block_standard.py` and `tests/test_adapter_spec.py`.
